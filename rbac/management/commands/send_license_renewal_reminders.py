"""
Management command: send_license_renewal_reminders

Sends renewal reminder emails at 15 days, 7 days, and 1 day before expiry.

Idempotency:
  Each sent notification is recorded in LicenseRenewalNotification keyed by
  (license_id, days_before, license_expiry_date).  If the same (license,
  days_before, expiry) triple already exists the email is skipped, so the
  command is safe to run multiple times per day (e.g. via cron every hour).

  When a license is renewed the expiry_date changes, so a fresh set of
  reminders will be sent automatically for the new expiry date.

Recipient logic:
  1. Use company.contact_email if set.
  2. Otherwise collect email addresses of all active users in that company.
  3. Always CC admin users (superusers) for visibility.

Usage:
  python manage.py send_license_renewal_reminders
  python manage.py send_license_renewal_reminders --dry-run
  python manage.py send_license_renewal_reminders --days 15 7 1
"""
import logging
from datetime import date, timedelta

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from rbac.models import CompanyLicense, LicenseRenewalNotification

logger = logging.getLogger('rbac.license_renewal')

# Reminder thresholds (days before expiry)
DEFAULT_THRESHOLDS = [15, 7, 1]

FROM_EMAIL = getattr(settings, 'GRAPH_FROM_EMAIL', 'Gajendra.N@wepsol.com')


# ---------------------------------------------------------------------------
# Graph API helpers (uses Wepsol app registration credentials from settings)
# ---------------------------------------------------------------------------

def _get_access_token():
    token_url = (
        f"https://login.microsoftonline.com/{settings.GRAPH_TENANT_ID}"
        "/oauth2/v2.0/token"
    )
    resp = requests.post(token_url, data={
        "grant_type": "client_credentials",
        "client_id": settings.GRAPH_CLIENT_ID,
        "client_secret": settings.GRAPH_CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _send_via_graph(access_token, to_emails, subject, html_body):
    """Send a single mail via Microsoft Graph /sendMail."""
    url = f"https://graph.microsoft.com/v1.0/users/{FROM_EMAIL}/sendMail"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": html_body},
            "toRecipients": [
                {"emailAddress": {"address": e}} for e in to_emails
            ],
        },
        "saveToSentItems": True,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# Email content builder
# ---------------------------------------------------------------------------

def _build_email(license_obj, days_left):
    company = license_obj.company
    package = license_obj.package
    expiry = license_obj.expiry_date

    if days_left == 1:
        urgency_color = "#dc3545"
        urgency_label = "FINAL NOTICE — Expires Tomorrow"
    elif days_left <= 7:
        urgency_color = "#fd7e14"
        urgency_label = f"Expires in {days_left} Days"
    else:
        urgency_color = "#ffc107"
        urgency_label = f"Expires in {days_left} Days"

    subject = f"[License Renewal] {package.display_name} — {urgency_label} ({company.name})"

    html = (
        "<html><body style='font-family:Arial,sans-serif;line-height:1.6;"
        "color:#333;max-width:640px;margin:0 auto;padding:20px;'>"

        # Header
        f"<div style='background:linear-gradient(135deg,{urgency_color},{urgency_color}cc);"
        "padding:30px;border-radius:10px 10px 0 0;text-align:center;'>"
        "<h2 style='color:white;margin:0;font-size:22px;'>"
        f"&#9888; License Renewal Reminder</h2>"
        f"<p style='color:white;margin:8px 0 0;opacity:.9;'>{urgency_label}</p>"
        "</div>"

        # Body
        "<div style='background:#fff;padding:30px;border:1px solid #e0e0e0;'>"
        f"<p style='font-size:16px;'>Dear <strong>{company.name}</strong> Team,</p>"
        "<p>This is a reminder that the following license is approaching its expiry date. "
        "Please arrange for renewal at the earliest to avoid service interruption.</p>"

        # Details table
        "<table style='width:100%;border-collapse:collapse;margin:20px 0;"
        "background:#f8f9fc;border-radius:8px;overflow:hidden;'>"
        "<tr style='background:#e9ecef;'>"
        "<th style='padding:10px 16px;text-align:left;'>Field</th>"
        "<th style='padding:10px 16px;text-align:left;'>Details</th>"
        "</tr>"
        f"<tr><td style='padding:10px 16px;color:#666;border-top:1px solid #dee2e6;'>Company</td>"
        f"<td style='padding:10px 16px;font-weight:bold;border-top:1px solid #dee2e6;'>{company.name}</td></tr>"
        f"<tr><td style='padding:10px 16px;color:#666;border-top:1px solid #dee2e6;'>Package</td>"
        f"<td style='padding:10px 16px;font-weight:bold;border-top:1px solid #dee2e6;'>{package.display_name}</td></tr>"
        f"<tr><td style='padding:10px 16px;color:#666;border-top:1px solid #dee2e6;'>License Type</td>"
        f"<td style='padding:10px 16px;border-top:1px solid #dee2e6;'>{license_obj.license_type}</td></tr>"
        f"<tr><td style='padding:10px 16px;color:#666;border-top:1px solid #dee2e6;'>Total Seats</td>"
        f"<td style='padding:10px 16px;border-top:1px solid #dee2e6;'>{license_obj.total_licenses}</td></tr>"
        f"<tr><td style='padding:10px 16px;color:#666;border-top:1px solid #dee2e6;'>Used Seats</td>"
        f"<td style='padding:10px 16px;border-top:1px solid #dee2e6;'>{license_obj.used_licenses}</td></tr>"
        f"<tr><td style='padding:10px 16px;color:#666;border-top:1px solid #dee2e6;'>Expiry Date</td>"
        f"<td style='padding:10px 16px;font-weight:bold;color:{urgency_color};"
        f"border-top:1px solid #dee2e6;'>{expiry.strftime('%d %B %Y')}</td></tr>"
        f"<tr><td style='padding:10px 16px;color:#666;border-top:1px solid #dee2e6;'>Days Remaining</td>"
        f"<td style='padding:10px 16px;font-weight:bold;color:{urgency_color};"
        f"border-top:1px solid #dee2e6;'>{days_left} day{'s' if days_left != 1 else ''}</td></tr>"
        "</table>"

        # CTA
        "<div style='text-align:center;margin:30px 0;'>"
        "<a href='http://192.168.5.150:8000/rbac/licenses/' "
        f"style='background-color:{urgency_color};color:white;padding:14px 36px;"
        "text-decoration:none;border-radius:8px;font-size:16px;font-weight:bold;"
        "display:inline-block;'>View License Details</a>"
        "</div>"

        "<p style='color:#666;font-size:13px;'>To renew, please contact your FluidTrust account manager "
        "or visit the portal link above.</p>"
        "<p style='color:#999;font-size:12px;margin-top:20px;'>This is an automated reminder. "
        "You will receive reminders at 15 days, 7 days, and 1 day before expiry.</p>"
        "</div>"

        # Footer
        "<div style='background:#f8f9fc;padding:15px;border-radius:0 0 10px 10px;"
        "text-align:center;font-size:12px;color:#999;'>"
        "FluidTrust Portal &mdash; License Management"
        "</div>"
        "</body></html>"
    )

    return subject, html


# ---------------------------------------------------------------------------
# Recipient resolution
# ---------------------------------------------------------------------------

def _get_recipients(company):
    """
    Returns a list of email addresses to notify.
    - company.contact_email if set
    - otherwise all active users belonging to the company
    Always includes superuser emails for CC-style awareness (merged into to-list).
    """
    recipients = set()

    if company.contact_email:
        recipients.add(company.contact_email)
    else:
        # All active users in this company
        company_emails = (
            User.objects.filter(
                userprofile__company=company, is_active=True
            ).exclude(email='')
            .values_list('email', flat=True)
        )
        recipients.update(company_emails)

    # Always include superusers (admin awareness)
    admin_emails = (
        User.objects.filter(is_superuser=True, is_active=True)
        .exclude(email='')
        .values_list('email', flat=True)
    )
    recipients.update(admin_emails)

    return sorted(recipients)


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Send license renewal reminder emails at 15, 7, and 1 day before expiry.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print what would be sent without actually sending.'
        )
        parser.add_argument(
            '--days', nargs='+', type=int, default=DEFAULT_THRESHOLDS,
            metavar='N',
            help='Reminder thresholds in days (default: 15 7 1).'
        )
        parser.add_argument(
            '--company', type=int, default=None,
            metavar='COMPANY_ID',
            help='Only process licenses for this company ID.'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        thresholds = sorted(set(options['days']), reverse=True)
        today = date.today()

        self.stdout.write(
            self.style.HTTP_INFO(
                f"[license_renewal] Running for thresholds={thresholds}, "
                f"dry_run={dry_run}, today={today}"
            )
        )

        # Fetch active licenses that are not yet expired
        qs = CompanyLicense.objects.filter(
            is_active=True, expiry_date__gte=today
        ).select_related('company', 'package')

        if options['company']:
            qs = qs.filter(company_id=options['company'])

        # Acquire Graph token once (skip in dry-run)
        access_token = None
        if not dry_run:
            try:
                access_token = _get_access_token()
                self.stdout.write(self.style.SUCCESS("Graph token acquired."))
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(f"Cannot get Graph token: {exc}")
                )
                return

        sent_count = 0
        skip_count = 0

        for lic in qs:
            days_left = (lic.expiry_date - today).days

            for threshold in thresholds:
                if days_left > threshold:
                    continue  # not yet in this reminder window

                # Check idempotency record
                already_sent = LicenseRenewalNotification.objects.filter(
                    license=lic,
                    days_before=threshold,
                    license_expiry_date=lic.expiry_date,
                ).exists()

                if already_sent:
                    skip_count += 1
                    self.stdout.write(
                        f"  SKIP  {lic} — {threshold}d reminder already sent "
                        f"(expiry={lic.expiry_date})"
                    )
                    continue

                recipients = _get_recipients(lic.company)
                if not recipients:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  SKIP  {lic} — no recipients found for {lic.company.name}"
                        )
                    )
                    continue

                subject, html_body = _build_email(lic, days_left)

                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  DRY   {lic} | threshold={threshold}d | "
                            f"to={recipients} | subject={subject}"
                        )
                    )
                    sent_count += 1
                    continue

                # Send
                success = True
                error_msg = ''
                try:
                    _send_via_graph(access_token, recipients, subject, html_body)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  SENT  {lic} — {threshold}d reminder → {recipients}"
                        )
                    )
                    sent_count += 1
                except Exception as exc:
                    success = False
                    error_msg = str(exc)
                    self.stderr.write(
                        self.style.ERROR(
                            f"  FAIL  {lic} — {threshold}d reminder: {exc}"
                        )
                    )

                # Record notification (even on failure, so we can see it in log)
                LicenseRenewalNotification.objects.create(
                    license=lic,
                    days_before=threshold,
                    license_expiry_date=lic.expiry_date,
                    recipients=', '.join(recipients),
                    success=success,
                    error_message=error_msg,
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Sent={sent_count}, Skipped={skip_count}."
            )
        )
