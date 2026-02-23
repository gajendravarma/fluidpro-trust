from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Package, UserPackageAccess, LicenseConfig
from .utils import has_package_permission, get_user_packages, is_admin_user, has_package_access
from .license_service import LicenseDashboardService

@login_required
@user_passes_test(is_admin_user)
def admin_dashboard(request):
    """Admin dashboard for managing user access"""
    context = {
        'total_users': User.objects.count(),
        'total_packages': Package.objects.filter(is_active=True).count(),
        'total_accesses': UserPackageAccess.objects.filter(is_enabled=True).count(),
        'recent_assignments': UserPackageAccess.objects.filter(is_enabled=True).order_by('-assigned_at')[:10]
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
def user_dashboard(request):
    """User dashboard showing accessible packages"""
    # Get user role
    user_role = 'technician'
    try:
        profile = request.user.userprofile
        user_role = profile.get_role()
    except Exception as e:
        # If no profile exists, show error and stay on this page
        messages.warning(request, 'Your user profile is not configured. Please contact administrator.')
        user_role = 'technician'
    
    # Redirect customer role to customer dashboard
    if user_role == 'customer':
        return redirect('rbac:customer_dashboard')
    
    user_packages = get_user_packages(request.user)
    
    return render(request, 'rbac/user_dashboard.html', {
        'user_packages': user_packages,
        'user_role': user_role
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
def customer_dashboard(request):
    """Customer dashboard with company-specific data and reports"""
    try:
        profile = request.user.userprofile
        user_role = profile.get_role()
        
        # Allow access for customer role only
        if user_role != 'customer':
            messages.warning(request, 'This dashboard is only for customer users.')
            return render(request, 'rbac/user_dashboard.html', {
                'user_packages': get_user_packages(request.user),
                'user_role': user_role
            })
        
        company = profile.company
        if not company:
            messages.error(request, 'No company assigned to your account')
            return render(request, 'rbac/customer_dashboard.html', {
                'company': None,
                'total_tickets': 0,
                'datto_devices': 0,
                'user_role': user_role
            })
        
        # Get company-specific stats
        from tickets.services import ManageEngineService
        me_service = ManageEngineService()
        
        # Get tickets for this company
        historical_data = me_service.get_historical_tickets(months=2)
        
        # Filter tickets by company
        company_tickets = []
        if historical_data and 'recent_tickets' in historical_data:
            for ticket in historical_data['recent_tickets']:
                requester = ticket.get('requester', {})
                requester_name = requester.get('name', '') if isinstance(requester, dict) else ''
                if company.name.lower() in requester_name.lower():
                    company_tickets.append(ticket)
        
        # Get Datto devices count
        datto_devices = 0
        try:
            from datto.datto_client import DattoClient
            datto_client = DattoClient()
            devices = datto_client.get_devices()
            if devices:
                datto_devices = len(devices)
        except:
            pass
        
        context = {
            'company': company,
            'total_tickets': len(company_tickets),
            'datto_devices': datto_devices,
            'user_role': user_role
        }
        
        return render(request, 'rbac/customer_dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading dashboard: {str(e)}')
        # Render a basic dashboard instead of redirecting
        return render(request, 'rbac/user_dashboard.html', {
            'user_packages': get_user_packages(request.user),
            'user_role': 'technician'
        })
