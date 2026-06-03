import logging
from datetime import date

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

import requests

from rbac.models import (
    UserProfile, Company, Package, UserPackageAccess,
    CompanyLicense, LicenseRenewalNotification,
)

logger = logging.getLogger('rbac.license_renewal')

FROM_EMAIL = getattr(settings, 'GRAPH_FROM_EMAIL', 'Gajendra.N@wepsol.com')


def _graph_token():
    resp = requests.post(
        f"https://login.microsoftonline.com/{settings.GRAPH_TENANT_ID}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": settings.GRAPH_CLIENT_ID,
            "client_secret": settings.GRAPH_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
        }, timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _send_graph_mail(token, to_emails, subject, html_body):
    resp = requests.post(
        f"https://graph.microsoft.com/v1.0/users/{FROM_EMAIL}/sendMail",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": html_body},
                "toRecipients": [{"emailAddress": {"address": e}} for e in to_emails],
            },
            "saveToSentItems": True,
        }, timeout=15,
    )
    resp.raise_for_status()


def _renewal_recipients(company):
    recipients = set()
    if company.contact_email:
        recipients.add(company.contact_email)
    else:
        for email in User.objects.filter(
            userprofile__company=company, is_active=True
        ).exclude(email='').values_list('email', flat=True):
            recipients.add(email)
    for email in User.objects.filter(
        is_superuser=True, is_active=True
    ).exclude(email='').values_list('email', flat=True):
        recipients.add(email)
    return sorted(recipients)


def _renewal_html(lic, days_left):
    from rbac.management.commands.send_license_renewal_reminders import _build_email
    return _build_email(lic, days_left)

@login_required
def license_dashboard(request):
    """Show license details for user's accessible packages"""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    user_role = user_profile.get_role()
    
    if user_role == 'admin':
        # Admin sees all companies so new ones appear before any license is assigned
        companies = Company.objects.all().order_by('name')
        licenses = CompanyLicense.objects.select_related('company', 'package').filter(is_active=True)
        
        context = {
            'licenses': licenses,
            'companies': companies,
            'user_role': user_role,
            'user_company': user_profile.company,
        }
        return render(request, 'rbac/admin_license_dashboard.html', context)
    else:
        # Customer/Technician sees only their company's licenses for accessible packages
        user_packages = UserPackageAccess.objects.filter(
            user=request.user, is_enabled=True
        ).values_list('package', flat=True)
        
        if user_packages.exists():
            licenses = CompanyLicense.objects.filter(
                company=user_profile.company,
                package__in=user_packages,
                is_active=True
            ).select_related('package')
        else:
            licenses = CompanyLicense.objects.none()
        
        context = {
            'licenses': licenses,
            'companies': None,
            'user_role': user_role,
            'user_company': user_profile.company,
            'accessible_packages': user_packages.count(),
        }
        
        return render(request, 'rbac/user_license_dashboard.html', context)

@login_required
def manage_company_licenses(request, company_id):
    """Admin view to manage licenses for a specific company"""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    if user_profile.get_role() != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('rbac:user_license_dashboard')

    company = get_object_or_404(Company, id=company_id)
    packages = Package.objects.filter(is_active=True)

    if request.method == 'POST':
        action = request.POST.get('action', 'update_license')

        # ---- Update contact email ----
        if action == 'update_contact_email':
            company.contact_email = request.POST.get('contact_email', '').strip()
            company.save(update_fields=['contact_email'])
            messages.success(request, 'Contact email updated.')
            return redirect('rbac:manage_company_licenses', company_id=company_id)

        # ---- Add / update a license ----
        package_id = request.POST.get('package_id')
        package = get_object_or_404(Package, id=package_id)

        license, created = CompanyLicense.objects.get_or_create(
            company=company,
            package=package,
            defaults={
                'total_licenses': int(request.POST.get('total_licenses', 0)),
                'used_licenses': int(request.POST.get('used_licenses', 0)),
                'expiry_date': request.POST.get('expiry_date'),
                'license_type': request.POST.get('license_type', 'Standard'),
            }
        )

        if not created:
            license.total_licenses = int(request.POST.get('total_licenses', 0))
            license.used_licenses = int(request.POST.get('used_licenses', 0))
            license.expiry_date = request.POST.get('expiry_date')
            license.license_type = request.POST.get('license_type', 'Standard')
            license.save()

        messages.success(request, f'License updated for {package.display_name}')
        return redirect('rbac:manage_company_licenses', company_id=company_id)

    licenses = CompanyLicense.objects.filter(
        company=company
    ).select_related('package').prefetch_related('renewal_notifications')

    # Recent notification history for this company (latest 20)
    notifications = LicenseRenewalNotification.objects.filter(
        license__company=company
    ).select_related('license__package').order_by('-sent_at')[:20]

    context = {
        'company': company,
        'packages': packages,
        'licenses': licenses,
        'notifications': notifications,
        'today': date.today(),
    }

    return render(request, 'rbac/manage_company_licenses.html', context)


@login_required
def trigger_renewal_email(request, license_id):
    """
    Admin-only: manually fire a renewal email for a specific license
    regardless of the threshold window. Does NOT set idempotency record
    (so it won't block the automatic reminders).
    """
    user_profile = get_object_or_404(UserProfile, user=request.user)
    if user_profile.get_role() != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('rbac:user_license_dashboard')

    if request.method != 'POST':
        return redirect('rbac:user_license_dashboard')

    lic = get_object_or_404(CompanyLicense, id=license_id)
    today = date.today()
    days_left = (lic.expiry_date - today).days

    recipients = _renewal_recipients(lic.company)
    if not recipients:
        messages.error(request, f'No recipients found for {lic.company.name}.')
        return redirect('rbac:manage_company_licenses', company_id=lic.company_id)

    subject, html_body = _renewal_html(lic, max(days_left, 0))

    try:
        token = _graph_token()
        _send_graph_mail(token, recipients, subject, html_body)
        messages.success(
            request,
            f'Renewal email sent for "{lic.package.display_name}" '
            f'to: {", ".join(recipients)}'
        )
        logger.info(f"Manual renewal email sent: {lic} → {recipients}")
    except Exception as exc:
        messages.error(request, f'Failed to send email: {exc}')
        logger.error(f"Manual renewal email failed: {lic} — {exc}")

    return redirect('rbac:manage_company_licenses', company_id=lic.company_id)


@login_required
def renewal_notification_log(request):
    """Admin: view all renewal notification history across all companies."""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    if user_profile.get_role() != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('rbac:user_license_dashboard')

    notifications = LicenseRenewalNotification.objects.select_related(
        'license__company', 'license__package'
    ).order_by('-sent_at')[:100]

    return render(request, 'rbac/renewal_notification_log.html', {
        'notifications': notifications,
    })
