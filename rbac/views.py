from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count
from .models import Package, UserPackageAccess, LicenseConfig, Role, Company, TechnicianCompanyAccess
from .utils import has_package_permission, get_user_packages, is_admin_user, has_package_access, company_name_match
from .license_service import LicenseDashboardService

@login_required
@user_passes_test(is_admin_user)
def admin_dashboard(request):
    """Admin dashboard for managing user access"""
    from .models import Role, Company
    from django.db.models import Count

    roles = {r.name: r for r in Role.objects.all()}
    admin_role     = roles.get('admin')
    tech_role      = roles.get('technician')
    customer_role  = roles.get('customer')

    context = {
        'total_users':      User.objects.count(),
        'total_packages':   Package.objects.filter(is_active=True).count(),
        'total_accesses':   UserPackageAccess.objects.filter(is_enabled=True).count(),
        'total_companies':  Company.objects.count(),
        'admin_count':      User.objects.filter(userprofile__role=admin_role).count() if admin_role else 0,
        'tech_count':       User.objects.filter(userprofile__role=tech_role).count() if tech_role else 0,
        'customer_count':   User.objects.filter(userprofile__role=customer_role).count() if customer_role else 0,
        'recent_assignments': UserPackageAccess.objects.filter(is_enabled=True)
                                .select_related('user', 'package', 'assigned_by')
                                .order_by('-assigned_at')[:8],
        'packages': Package.objects.filter(is_active=True).annotate(
            user_count=Count('userpackageaccess', filter=__import__('django.db.models', fromlist=['Q']).Q(userpackageaccess__is_enabled=True))
        ),
    }
    return render(request, 'rbac/admin_dashboard.html', context)

@login_required
def license_dashboard(request):
    """License dashboard showing usage for all services"""
    license_service = LicenseDashboardService()
    licenses = license_service.get_all_licenses()
    license_configs = LicenseConfig.objects.all()
    return render(request, 'rbac/license_dashboard.html', {
        'licenses': licenses,
        'license_configs': license_configs
    })

@login_required
@user_passes_test(is_admin_user)
def edit_license_config(request, service_name):
    """Edit license configuration"""
    if request.method == 'POST':
        total_licenses = request.POST.get('total_licenses')
        license_type = request.POST.get('license_type')
        expiry_date = request.POST.get('expiry_date')
        
        config, created = LicenseConfig.objects.get_or_create(service_name=service_name)
        config.total_licenses = total_licenses
        config.license_type = license_type
        config.expiry_date = expiry_date
        config.alert_sent_one_month = False
        config.alert_sent_one_week = False
        config.save()
        
        messages.success(request, f'License configuration for {service_name} updated successfully')
        return redirect('rbac:license_dashboard')
    
    return redirect('rbac:license_dashboard')

@login_required
@user_passes_test(is_admin_user)
def manage_users(request):
    """Manage user package access"""
    from .models import Role
    users = User.objects.all().prefetch_related('userpackageaccess_set__package', 'userprofile')
    packages = Package.objects.filter(is_active=True)
    roles = Role.objects.all()
    return render(request, 'rbac/manage_users.html', {
        'users': users, 
        'packages': packages,
        'roles': roles
    })

@login_required
@user_passes_test(is_admin_user)
def assign_package_access(request):
    """Assign package access to user"""
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        package_id = request.POST.get('package_id')
        can_create = request.POST.get('can_create') == 'on'
        can_read = request.POST.get('can_read') == 'on'
        can_update = request.POST.get('can_update') == 'on'
        can_delete = request.POST.get('can_delete') == 'on'
        
        try:
            user = User.objects.get(id=user_id)
            package = Package.objects.get(id=package_id)
            
            access, created = UserPackageAccess.objects.get_or_create(
                user=user,
                package=package,
                defaults={
                    'assigned_by': request.user,
                    'can_create': can_create,
                    'can_read': can_read,
                    'can_update': can_update,
                    'can_delete': can_delete,
                }
            )
            
            if not created:
                access.is_enabled = True
                access.can_create = can_create
                access.can_read = can_read
                access.can_update = can_update
                access.can_delete = can_delete
                access.save()
                
            messages.success(request, f'Access to "{package.display_name}" assigned to {user.username}')
                
        except (User.DoesNotExist, Package.DoesNotExist):
            messages.error(request, 'Invalid user or package')
    
    return redirect('rbac:manage_users')

@login_required
@user_passes_test(is_admin_user)
def remove_package_access(request):
    """Remove package access from user"""
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        package_id = request.POST.get('package_id')
        
        try:
            access = UserPackageAccess.objects.get(user_id=user_id, package_id=package_id)
            access.is_enabled = False
            access.save()
            messages.success(request, 'Package access removed successfully')
        except UserPackageAccess.DoesNotExist:
            messages.error(request, 'Access not found')
    
    return redirect('rbac:manage_users')

@login_required
@user_passes_test(is_admin_user)
def manage_technician_access(request):
    """List all technicians with their current company access assignments."""
    from .models import TechnicianCompanyAccess, Role, Company
    tech_role = Role.objects.filter(name='technician').first()
    technicians = (
        User.objects.filter(userprofile__role=tech_role)
        .prefetch_related('company_accesses__company', 'userprofile')
        .order_by('username')
    )
    companies = Company.objects.all().order_by('name')
    return render(request, 'rbac/technician_access.html', {
        'technicians': technicians,
        'companies': companies,
    })


@login_required
@user_passes_test(is_admin_user)
def set_technician_company_access(request):
    """POST: replace a technician's company access list."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'})

    from .models import TechnicianCompanyAccess, Company
    try:
        user_id     = int(request.POST.get('user_id', 0))
        company_ids = request.POST.getlist('company_ids')  # list of int strings
        user = User.objects.get(pk=user_id)

        # Validate role
        try:
            if user.userprofile.get_role() not in ('technician',):
                return JsonResponse({'success': False,
                                     'message': 'User is not a technician'})
        except Exception:
            pass

        # Replace access set atomically
        TechnicianCompanyAccess.objects.filter(user=user).delete()
        for cid in company_ids:
            try:
                company = Company.objects.get(pk=int(cid))
                TechnicianCompanyAccess.objects.create(
                    user=user, company=company, granted_by=request.user
                )
            except (Company.DoesNotExist, ValueError):
                pass

        count = TechnicianCompanyAccess.objects.filter(user=user).count()
        scope = f'{count} company/companies' if count else 'unrestricted (all companies)'
        return JsonResponse({
            'success': True,
            'message': f'Access updated for {user.get_full_name() or user.username}: {scope}',
            'count': count,
        })
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def user_dashboard(request):
    """Technician/admin dashboard — shows only accessible packages with company-scoped stats."""
    user_role = 'technician'
    profile = None
    try:
        profile = request.user.userprofile
        user_role = profile.get_role()
    except Exception:
        messages.warning(request, 'Your user profile is not configured. Please contact administrator.')

    # Redirect customer role to their company dashboard
    if user_role == 'customer':
        return redirect('rbac:company_dashboard')

    user_packages = get_user_packages(request.user)
    company = profile.company if profile else None

    # Gather per-package stats scoped to this technician's company
    package_stats = {}
    package_names = [pkg.name for pkg, _ in user_packages]

    if 'mdm' in package_names and company:
        try:
            from mdm.models import MdmCustomer
            from mdm.live_service import get_mdm_stats
            customers = list(MdmCustomer.objects.filter(company=company))
            stats = get_mdm_stats(customers)
            package_stats['mdm'] = {
                'total_devices':  stats['total'],
                'active_devices': stats['active'],
            }
        except Exception:
            pass

    if 'pulseway' in package_names and company:
        try:
            from pulseway.models import PulsewayDevice
            pw_devices = PulsewayDevice.objects.all()
            matched = [d for d in pw_devices if company_name_match(company.name, d.organization_name or '')]
            package_stats['pulseway'] = {'total_devices': len(matched)}
        except Exception:
            pass

    return render(request, 'rbac/user_dashboard.html', {
        'user_packages': user_packages,
        'user_role': user_role,
        'company': company,
        'package_stats': package_stats,
    })

@require_http_methods(["GET"])
@login_required
def check_permission(request):
    """API endpoint to check user permissions"""
    package_name = request.GET.get('package')
    permission_name = request.GET.get('permission')
    
    has_permission = has_package_permission(request.user, package_name, permission_name)
    
    return JsonResponse({'has_permission': has_permission})

@login_required
@user_passes_test(is_admin_user)
def assign_role(request):
    """Assign role to user"""
    if request.method == 'POST':
        from .models import Role, UserProfile
        user_id = request.POST.get('user_id')
        role_id = request.POST.get('role_id')
        
        try:
            user = User.objects.get(id=user_id)
            role = Role.objects.get(id=role_id)
            
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.save()
            
            messages.success(request, f'Role "{role.get_name_display()}" assigned to {user.username}')
        except (User.DoesNotExist, Role.DoesNotExist):
            messages.error(request, 'Invalid user or role')
    
    return redirect('rbac:manage_users')

@login_required
@user_passes_test(is_admin_user)
def admin_dashboard_detail_api(request):
    """Paginated AJAX API for admin dashboard detail popups."""
    from django.core.paginator import Paginator
    from .models import UserProfile

    detail_type = request.GET.get('type', 'users')
    page        = int(request.GET.get('page', 1))
    search      = request.GET.get('search', '').strip()
    per_page    = 10

    rows = []
    columns = []
    title = ''
    paginator = None
    page_obj  = None

    if detail_type == 'users':
        title   = 'All Users'
        columns = ['Username', 'Full Name', 'Email', 'Role', 'Company', 'Joined']
        qs = User.objects.select_related('userprofile__role', 'userprofile__company').all()
        if search:
            qs = qs.filter(
                Q(username__icontains=search) | Q(email__icontains=search) |
                Q(first_name__icontains=search) | Q(last_name__icontains=search)
            )
        qs = qs.order_by('username')
        paginator = Paginator(qs, per_page)
        page_obj  = paginator.get_page(page)
        for u in page_obj:
            profile = getattr(u, 'userprofile', None)
            rows.append([
                u.username,
                u.get_full_name() or '—',
                u.email or '—',
                profile.role.get_name_display() if (profile and profile.role) else ('Superuser' if u.is_superuser else '—'),
                profile.company.name if (profile and profile.company) else '—',
                u.date_joined.strftime('%d %b %Y'),
            ])

    elif detail_type == 'admins':
        title   = 'Admin Users'
        columns = ['Username', 'Email', 'Superuser', 'Last Login']
        admin_role = Role.objects.filter(name='admin').first()
        qs = User.objects.filter(
            Q(is_superuser=True) | Q(userprofile__role=admin_role)
        ).select_related('userprofile__role').distinct()
        if search:
            qs = qs.filter(Q(username__icontains=search) | Q(email__icontains=search))
        qs = qs.order_by('username')
        paginator = Paginator(qs, per_page)
        page_obj  = paginator.get_page(page)
        for u in page_obj:
            rows.append([
                u.username,
                u.email or '—',
                'Yes' if u.is_superuser else 'No',
                u.last_login.strftime('%d %b %Y %H:%M') if u.last_login else 'Never',
            ])

    elif detail_type == 'technicians':
        title   = 'Technicians'
        columns = ['Username', 'Email', 'Company Access', 'Packages', 'Last Login']
        tech_role = Role.objects.filter(name='technician').first()
        qs = User.objects.filter(userprofile__role=tech_role).select_related(
            'userprofile__role', 'userprofile__company'
        ).prefetch_related('company_accesses__company', 'userpackageaccess_set__package')
        if search:
            qs = qs.filter(Q(username__icontains=search) | Q(email__icontains=search))
        qs = qs.order_by('username')
        paginator = Paginator(qs, per_page)
        page_obj  = paginator.get_page(page)
        for u in page_obj:
            ca_list = list(u.company_accesses.all())
            access_str = ', '.join(ca.company.name for ca in ca_list) if ca_list else 'All Companies'
            pkgs = [upa.package.display_name for upa in u.userpackageaccess_set.filter(is_enabled=True)]
            rows.append([
                u.username,
                u.email or '—',
                access_str,
                ', '.join(pkgs) or '—',
                u.last_login.strftime('%d %b %Y %H:%M') if u.last_login else 'Never',
            ])

    elif detail_type == 'customers':
        title   = 'Customers'
        columns = ['Username', 'Email', 'Company', 'Mobile', 'Packages']
        customer_role = Role.objects.filter(name='customer').first()
        qs = User.objects.filter(userprofile__role=customer_role).select_related(
            'userprofile__role', 'userprofile__company'
        ).prefetch_related('userpackageaccess_set__package')
        if search:
            qs = qs.filter(Q(username__icontains=search) | Q(email__icontains=search))
        qs = qs.order_by('username')
        paginator = Paginator(qs, per_page)
        page_obj  = paginator.get_page(page)
        for u in page_obj:
            profile = getattr(u, 'userprofile', None)
            pkgs = [upa.package.display_name for upa in u.userpackageaccess_set.filter(is_enabled=True)]
            rows.append([
                u.username,
                u.email or '—',
                profile.company.name if (profile and profile.company) else '—',
                profile.mobile_number if profile else '—',
                ', '.join(pkgs) or '—',
            ])

    elif detail_type == 'companies':
        title   = 'Companies'
        columns = ['Company Name', 'Code', 'Contact Email', 'Users', 'Created']
        qs = Company.objects.annotate(user_count=Count('users')).all()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(code__icontains=search))
        qs = qs.order_by('name')
        paginator = Paginator(qs, per_page)
        page_obj  = paginator.get_page(page)
        for c in page_obj:
            rows.append([
                c.name,
                c.code,
                c.contact_email or '—',
                str(c.user_count),
                c.created_at.strftime('%d %b %Y'),
            ])

    elif detail_type == 'accesses':
        title   = 'Active Package Accesses'
        columns = ['User', 'Package', 'Permissions', 'Assigned By', 'Date']
        qs = UserPackageAccess.objects.filter(is_enabled=True).select_related('user', 'package', 'assigned_by')
        if search:
            qs = qs.filter(Q(user__username__icontains=search) | Q(package__display_name__icontains=search))
        qs = qs.order_by('-assigned_at')
        paginator = Paginator(qs, per_page)
        page_obj  = paginator.get_page(page)
        for a in page_obj:
            perms = []
            if a.can_create: perms.append('Create')
            if a.can_read:   perms.append('Read')
            if a.can_update: perms.append('Update')
            if a.can_delete: perms.append('Delete')
            rows.append([
                a.user.username,
                a.package.display_name,
                ', '.join(perms) or '—',
                a.assigned_by.username if a.assigned_by else 'System',
                a.assigned_at.strftime('%d %b %Y'),
            ])

    elif detail_type.startswith('package_'):
        try:
            pkg_id = int(detail_type.split('_', 1)[1])
            pkg    = Package.objects.get(id=pkg_id)
            title   = f'Users with {pkg.display_name} Access'
            columns = ['Username', 'Email', 'Company', 'Permissions', 'Assigned']
            qs = UserPackageAccess.objects.filter(package=pkg, is_enabled=True).select_related(
                'user', 'user__userprofile__company', 'assigned_by'
            )
            if search:
                qs = qs.filter(Q(user__username__icontains=search) | Q(user__email__icontains=search))
            qs = qs.order_by('user__username')
            paginator = Paginator(qs, per_page)
            page_obj  = paginator.get_page(page)
            for a in page_obj:
                profile = getattr(a.user, 'userprofile', None)
                perms = []
                if a.can_create: perms.append('C')
                if a.can_read:   perms.append('R')
                if a.can_update: perms.append('U')
                if a.can_delete: perms.append('D')
                rows.append([
                    a.user.username,
                    a.user.email or '—',
                    profile.company.name if (profile and profile.company) else '—',
                    ', '.join(perms) or '—',
                    a.assigned_at.strftime('%d %b %Y'),
                ])
        except (Package.DoesNotExist, ValueError):
            return JsonResponse({'error': 'Package not found'}, status=404)

    else:
        return JsonResponse({'error': 'Unknown type'}, status=400)

    return JsonResponse({
        'title': title,
        'columns': columns,
        'rows': rows,
        'page': page_obj.number if page_obj else 1,
        'total_pages': paginator.num_pages if paginator else 1,
        'total_count': paginator.count if paginator else 0,
        'has_previous': page_obj.has_previous() if page_obj else False,
        'has_next': page_obj.has_next() if page_obj else False,
    })


@login_required
def customer_dashboard(request):
    """Customer dashboard — company-scoped stats for each package they have access to."""
    try:
        profile = request.user.userprofile
        user_role = profile.get_role()
    except Exception:
        messages.warning(request, 'Your user profile is not configured. Please contact administrator.')
        return render(request, 'rbac/user_dashboard.html', {
            'user_packages': get_user_packages(request.user),
            'user_role': 'technician',
        })

    # Non-customer roles go to the standard user dashboard
    if user_role != 'customer':
        return redirect('rbac:user_dashboard')

    company = profile.company
    if not company:
        messages.error(request, 'No company assigned to your account. Please contact administrator.')
        return render(request, 'rbac/customer_dashboard.html', {
            'company': None, 'user_packages': [], 'package_stats': {}, 'user_role': user_role,
        })

    user_packages = get_user_packages(request.user)
    package_names = [pkg.name for pkg, _ in user_packages]
    package_stats = {}

    # MDM stats — live API
    if 'mdm' in package_names:
        try:
            from mdm.models import MdmCustomer
            from mdm.live_service import get_mdm_stats
            customers = list(MdmCustomer.objects.filter(company=company))
            stats = get_mdm_stats(customers)
            package_stats['mdm'] = {
                'total_devices':  stats['total'],
                'active_devices': stats['active'],
            }
        except Exception:
            pass

    # ManageEngine/Tickets stats — local DB, fuzzy company name match
    if 'manageengine' in package_names or 'tickets' in package_names:
        try:
            from tickets.local_service import LocalTicketService
            svc = LocalTicketService()
            matched_name = svc.find_company_in_cache(company.name)
            data = svc.get_dashboard_data(company_filter=matched_name)
            package_stats['manageengine'] = {
                'total_tickets': data['total_tickets'],
                'status_counts': data['status_counts'],
            }
        except Exception:
            pass

    # Pulseway stats — local DB, fuzzy organization name match
    if 'pulseway' in package_names:
        try:
            from pulseway.local_service import PulsewayLocalService
            pw = PulsewayLocalService()
            stats = pw.get_company_stats(company.name)
            package_stats['pulseway'] = {
                'total_devices': stats['total_devices'],
                'online_devices': stats['online_devices'],
                'offline_devices': stats['offline_devices'],
                'pending_patches': stats['pending_patches'],
            }
        except Exception:
            pass

    # Office 365 stats — live summary (lightweight)
    if 'office365' in package_names:
        try:
            from office365.customer_config import resolve_customer_key
            from office365.services import Office365API
            key = resolve_customer_key(company.name)
            if key:
                api = Office365API(customer_key=key)
                summary = api.get_license_summary()
                package_stats['office365'] = {
                    'total': sum(s['total'] for s in summary),
                    'used': sum(s['consumed'] for s in summary),
                }
        except Exception:
            pass

    context = {
        'company': company,
        'user_packages': user_packages,
        'package_stats': package_stats,
        'user_role': user_role,
    }
    return render(request, 'rbac/customer_dashboard.html', context)
