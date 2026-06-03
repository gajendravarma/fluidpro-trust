from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.core.paginator import Paginator
from rbac.decorators import require_package_access
from rbac.models import UserProfile, Company
from .models import MdmCustomer, Device, SecurityEvent, InstalledApp, DeviceGroup, AppPolicy, Profile, MdmUser
from .manageengine_mdm_service import ManageEngineMDMService, MANAGED_STATUS_MAP
from .live_service import (
    fetch_live_devices as _fetch_live_devices_shared,
    normalize_device, get_mdm_stats, _STATUS_DISPLAY, _epoch_ms as _epoch_ms_shared,
)
from functools import wraps
import datetime

# ─────────────────────────────────────────────────────────────────────────────
# Live-API helpers — all normalization / fetching lives in live_service.py.
# These local aliases keep existing call-sites in this file working unchanged.
# ─────────────────────────────────────────────────────────────────────────────

def _epoch_ms(value):
    return _epoch_ms_shared(value)

def _normalize_device(raw: dict, mdm_customer=None) -> dict:
    return normalize_device(raw, mdm_customer)

def _fetch_live_devices(customers) -> list:
    return _fetch_live_devices_shared(customers)

def require_admin_or_technician(view_func):
    """Decorator to require admin or technician role"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user_profile = get_object_or_404(UserProfile, user=request.user)
        user_role = user_profile.get_role()
        if user_role not in ['admin', 'technician']:
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('mdm:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def _scoped_devices(user_profile):
    """Return Device queryset scoped to role.
    Admin/Technician → all devices.
    Customer         → their company only.
    """
    role = user_profile.get_role()
    if role in ('admin', 'technician'):
        return Device.objects.all()
    # customer
    if user_profile.company:
        return Device.objects.filter(mdm_customer__company=user_profile.company)
    return Device.objects.none()


def _scoped_customers(user_profile):
    """Return MdmCustomer queryset scoped to role."""
    role = user_profile.get_role()
    if role in ('admin', 'technician'):
        return MdmCustomer.objects.all()
    if user_profile.company:
        return MdmCustomer.objects.filter(company=user_profile.company)
    return MdmCustomer.objects.none()


def _scoped_companies(user_profile):
    """Return Company queryset scoped to role."""
    role = user_profile.get_role()
    if role in ('admin', 'technician'):
        return Company.objects.all()
    if user_profile.company:
        return Company.objects.filter(id=user_profile.company.id)
    return Company.objects.none()

def require_admin_only(view_func):
    """Decorator to require admin role only"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user_profile = get_object_or_404(UserProfile, user=request.user)
        user_role = user_profile.get_role()
        if user_role != 'admin':
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('mdm:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@login_required
@require_package_access('mdm')
def mdm_dashboard(request):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    user_role = user_profile.get_role()

    if user_role == 'admin':
        return redirect('mdm:admin_dashboard')

    mdm_customers = list(_scoped_customers(user_profile))
    companies = _scoped_companies(user_profile)

    # Fetch live device data from API
    devices = _fetch_live_devices(mdm_customers)

    total_devices   = len(devices)
    active_devices  = sum(1 for d in devices if d['status'] == 'active')
    pending_devices = sum(1 for d in devices if d['status'] in ('enrollment_pending', 'staged'))
    retired_devices = sum(1 for d in devices if d['status'] == 'retired')
    recent_devices  = sorted(
        [d for d in devices if d['last_contact_time']],
        key=lambda d: d['last_contact_time'], reverse=True
    )[:5]

    context = {
        'user_role':       user_role,
        'total_devices':   total_devices,
        'active_devices':  active_devices,
        'pending_devices': pending_devices,
        'retired_devices': retired_devices,
        'security_events': 0,
        'recent_devices':  recent_devices,
        'recent_events':   [],
        'mdm_customers':   mdm_customers,
        'companies':       companies,
        'total_companies': companies.count(),
        'total_customers': len(mdm_customers),
    }
    return render(request, 'mdm/dashboard.html', context)

@login_required
@require_package_access('mdm')
def device_list(request):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    user_role = user_profile.get_role()

    # Determine which customers to query
    company_filter = request.GET.get('company', '')
    customers = list(_scoped_customers(user_profile))
    if company_filter and user_role in ('admin', 'technician'):
        customers = [c for c in customers if str(c.company_id) == company_filter]

    # Fetch live from API
    devices = _fetch_live_devices(customers)

    # In-memory search & filter
    search      = request.GET.get('search', '')
    device_type = request.GET.get('device_type', '')
    status      = request.GET.get('status', '')

    if search:
        sl = search.lower()
        devices = [d for d in devices if
                   sl in d['device_name'].lower() or
                   sl in d['username'].lower() or
                   sl in d['user_email'].lower()]
    if device_type:
        devices = [d for d in devices if d['device_type'] == device_type]
    if status:
        devices = [d for d in devices if d['status'] == status]

    # Sort by last contact time descending
    devices.sort(key=lambda d: d['last_contact_time'] or datetime.datetime.min, reverse=True)

    total_count    = len(devices)
    active_count   = sum(1 for d in devices if d['status'] == 'active')
    pending_count  = sum(1 for d in devices if d['status'] in ('enrollment_pending', 'staged'))
    inactive_count = sum(1 for d in devices if d['status'] == 'retired')

    paginator   = Paginator(devices, 20)
    page_obj    = paginator.get_page(request.GET.get('page', 1))
    companies   = Company.objects.all() if user_role in ('admin', 'technician') else Company.objects.none()

    status_choices = [
        ('', 'All Status'),
        ('active', 'Active / Enrolled'),
        ('enrollment_pending', 'Pending Enrollment'),
        ('staged', 'Staged'),
        ('retired', 'Retired'),
    ]

    context = {
        'devices':        page_obj,
        'page_obj':       page_obj,
        'paginator':      paginator,
        'user_role':      user_role,
        'search':         search,
        'device_type':    device_type,
        'status':         status,
        'company_filter': company_filter,
        'device_types':   Device.DEVICE_TYPES,
        'status_choices': status_choices,
        'companies':      companies,
        'total_count':    total_count,
        'active_count':   active_count,
        'pending_count':  pending_count,
        'inactive_count': inactive_count,
    }
    return render(request, 'mdm/device_list.html', context)

@login_required
@require_package_access('mdm')
def device_detail(request, device_id):
    """Fetch a single device live from the MDM API."""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    user_role = user_profile.get_role()

    svc = ManageEngineMDMService()
    device = None
    installed_apps = []

    # Find which customer owns this device_id (try all scoped customers)
    for customer in _scoped_customers(user_profile):
        raw = svc.get_device(str(device_id), customer_id=customer.customer_id)
        if raw:
            device = _normalize_device(raw, customer)
            # Fetch installed apps live
            try:
                apps_raw = svc.get_device_apps(str(device_id), customer_id=customer.customer_id)
                installed_apps = apps_raw or []
            except Exception:
                installed_apps = []
            break

    if not device:
        messages.error(request, 'Device not found.')
        return redirect('mdm:device_list')

    context = {
        'device':         device,
        'installed_apps': installed_apps,
        'security_events': [],   # not available without DB sync
        'user_role':      user_role,
    }
    return render(request, 'mdm/device_detail.html', context)

@login_required
@require_package_access('mdm')
@require_admin_or_technician
def customer_list(request):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    user_role = user_profile.get_role()
    
    mdm_customers = _scoped_customers(user_profile).order_by('company__name')

    # Search functionality
    search = request.GET.get('search', '')
    if search:
        mdm_customers = mdm_customers.filter(
            Q(company__name__icontains=search) |
            Q(customer_id__icontains=search)
        )

    context = {
        'mdm_customers': mdm_customers,
        'user_role': user_role,
        'search': search,
    }
    
    return render(request, 'mdm/customer_list.html', context)

@login_required
@require_package_access('mdm')
def customer_detail(request, customer_id):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    user_role = user_profile.get_role()
    
    # Only admin and technician can access customer details
    if user_role == 'customer':
        messages.error(request, 'You do not have permission to access customer details.')
        return redirect('mdm:dashboard')

    # Technician can only access their own company's customer record
    if user_role == 'technician' and user_profile.company:
        mdm_customer = get_object_or_404(MdmCustomer, id=customer_id, company=user_profile.company)
    else:
        mdm_customer = get_object_or_404(MdmCustomer, id=customer_id)
    # Fetch live devices from MDM API for this customer
    devices = _fetch_live_devices([mdm_customer])

    total_devices  = len(devices)
    active_devices = sum(1 for d in devices if d['status'] in ('active', 'managed'))

    context = {
        'mdm_customer':  mdm_customer,
        'devices':       devices[:10],
        'total_devices': total_devices,
        'active_devices': active_devices,
        'security_events': 0,
        'user_role':     user_role,
    }
    return render(request, 'mdm/customer_detail.html', context)

@login_required
@require_package_access('mdm')
def user_list(request):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    user_role = user_profile.get_role()

    # Only admin and technician can access user management
    if user_role == 'customer':
        messages.error(request, 'You do not have permission to access user management.')
        return redirect('mdm:dashboard')

    from .models import MdmUser
    scoped_customers = _scoped_customers(user_profile)
    mdm_users = MdmUser.objects.filter(
        mdm_customer__in=scoped_customers
    ).order_by('mdm_customer__company__name', 'user__username')

    context = {
        'mdm_users': mdm_users,
        'user_role': user_role,
    }

    return render(request, 'mdm/user_list.html', context)

@login_required
@require_package_access('mdm')
def app_policies(request):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    user_role = user_profile.get_role()

    if user_role == 'customer':
        messages.error(request, 'You do not have permission to access app policies.')
        return redirect('mdm:dashboard')

    from .manageengine_mdm_service import ManageEngineMDMService
    svc = ManageEngineMDMService()

    # Pull live blacklist & repository from MDM API
    api_blacklist   = svc.get_blacklist_apps()   or []
    api_app_repo    = svc.get_all_apps()          or []

    # Also keep local DB policies as fallback / reference
    local_policies = AppPolicy.objects.all().order_by('app_name')

    # Build set of blacklisted identifiers for quick lookup in template
    blacklisted_ids = {
        str(a.get('appgroupid') or a.get('app_group_id') or a.get('app_id', ''))
        for a in api_blacklist
    }

    context = {
        'user_role':       user_role,
        'api_blacklist':   api_blacklist,
        'api_app_repo':    api_app_repo,
        'local_policies':  local_policies,
        'blacklisted_ids': blacklisted_ids,
        'api_available':   bool(api_blacklist or api_app_repo),
    }

    return render(request, 'mdm/app_policies.html', context)

@login_required
@require_package_access('mdm')
def profiles_list(request):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    user_role = user_profile.get_role()

    if user_role == 'customer':
        messages.error(request, 'You do not have permission to access profiles.')
        return redirect('mdm:dashboard')

    from .manageengine_mdm_service import ManageEngineMDMService
    svc = ManageEngineMDMService()

    # Pull live profiles from MDM API
    api_profiles    = svc.get_all_profiles() or []
    # Local DB profiles as fallback
    local_profiles  = Profile.objects.all().order_by('name')

    context = {
        'user_role':      user_role,
        'api_profiles':   api_profiles,
        'local_profiles': local_profiles,
        'api_available':  bool(api_profiles),
    }

    return render(request, 'mdm/profiles_list.html', context)

@login_required
@require_package_access('mdm')
def reports_dashboard(request):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    devices = _fetch_live_devices(list(_scoped_customers(user_profile)))

    total_devices        = len(devices)
    active_devices       = sum(1 for d in devices if d['status'] == 'active')
    devices_with_storage = sum(1 for d in devices if d.get('storage_gb', 0) > 0)

    context = {
        'total_devices':        total_devices,
        'active_devices':       active_devices,
        'devices_with_storage': devices_with_storage,
        'security_events':      0,
        'total_apps':           0,
    }
    return render(request, 'mdm/reports_dashboard.html', context)

@login_required
@require_package_access('mdm')
def device_storage_report(request):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    all_devices = _fetch_live_devices(list(_scoped_customers(user_profile)))
    # Only devices with capacity info, sorted descending
    devices = sorted(
        [d for d in all_devices if d.get('storage_gb', 0) > 0],
        key=lambda d: d.get('storage_gb', 0), reverse=True
    )
    context = {
        'devices':      devices,
        'total_count':  len(all_devices),
        'storage_count': len(devices),
    }
    return render(request, 'mdm/storage_report.html', context)

@login_required
@require_package_access('mdm')
def installed_apps_report(request):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    devices = _fetch_live_devices(list(_scoped_customers(user_profile)))
    context = {
        'devices':    devices,
        'total':      len(devices),
        'apps':       [],   # per-device app detail requires separate API calls per device
        'note':       'Per-device app details are available on each device\'s detail page.',
    }
    return render(request, 'mdm/apps_report.html', context)

@login_required
@require_package_access('mdm')
def location_report(request):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    devices = _fetch_live_devices(list(_scoped_customers(user_profile)))
    context = {
        'devices':    devices,
        'total':      len(devices),
        'note':       'Real-time location data is available via the "Locate" action on each device.',
    }
    return render(request, 'mdm/location_report.html', context)

@login_required
@require_package_access('mdm')
def sync_customer_data(request, customer_id):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    if user_profile.get_role() == 'customer':
        messages.error(request, 'You do not have permission to sync customer data.')
        return redirect('mdm:dashboard')

    from .manageengine_mdm_service import ManageEngineMDMService
    mdm_customer = get_object_or_404(MdmCustomer, id=customer_id)
    svc = ManageEngineMDMService()
    created, updated, skipped = svc.sync_devices_for_customer(mdm_customer)

    if created == 0 and updated == 0 and skipped == 0:
        messages.warning(request, f'No devices returned from MDM API for {mdm_customer.company.name}. '
                                   f'Check MDM_API_BASE_URL / MDM_API_KEY settings.')
    else:
        messages.success(request, f'Synced {mdm_customer.company.name}: '
                                   f'{created} new, {updated} updated, {skipped} skipped (removed).')

    return redirect('mdm:customer_detail', customer_id=customer_id)

@login_required
@require_package_access('mdm')
def enrollment_settings(request, customer_id):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    if user_profile.get_role() == 'customer':
        messages.error(request, 'You do not have permission to access enrollment settings.')
        return redirect('mdm:dashboard')
    
    mdm_customer = get_object_or_404(MdmCustomer, id=customer_id)
    
    from .models import EnrollmentSettings
    settings, created = EnrollmentSettings.objects.get_or_create(
        mdm_customer=mdm_customer,
        defaults={
            'allow_personal_apps': True,
            'require_passcode': True,
            'auto_enrollment': False,
        }
    )
    
    context = {
        'mdm_customer': mdm_customer,
        'settings': settings,
    }
    
    return render(request, 'mdm/enrollment_settings.html', context)

@login_required
@require_package_access('mdm')
def security_report(request):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    user_role = user_profile.get_role()
    severity = request.GET.get('severity', '')

    # Get live device IDs so we can scope security events from DB
    live_devices = _fetch_live_devices(list(_scoped_customers(user_profile)))
    live_device_ids = [d['device_id'] for d in live_devices]

    security_events = SecurityEvent.objects.filter(
        device__device_id__in=live_device_ids
    ).order_by('-created_at')
    if severity:
        security_events = security_events.filter(severity=severity)

    total_events    = security_events.count()
    critical_events = security_events.filter(severity='critical').count()
    unresolved_events = security_events.filter(resolved=False).count()

    context = {
        'security_events':  security_events[:50],
        'total_events':     total_events,
        'critical_events':  critical_events,
        'unresolved_events': unresolved_events,
        'severity':         severity,
        'severity_levels':  SecurityEvent.SEVERITY_LEVELS,
        'user_role':        user_role,
        'total_devices':    len(live_devices),
    }
    return render(request, 'mdm/security_report.html', context)

@login_required
@require_package_access('mdm')
def add_customer(request):
    """Add new customer"""
    if request.method == 'POST':
        try:
            customer = MdmCustomer.objects.create(
                customer_id=request.POST['customer_id'],
                name=request.POST['name'],
                email=request.POST['email'],
                phone=request.POST.get('phone', ''),
                address=request.POST.get('address', ''),
                company=request.user.userprofile.company
            )
            messages.success(request, f'Customer {customer.name} added successfully')
            return redirect('mdm:customer_list')
        except Exception as e:
            messages.error(request, f'Error creating customer: {str(e)}')
    
    return render(request, 'mdm/add_customer.html')

@login_required
@require_package_access('mdm')
def edit_customer(request, customer_id):
    """Edit existing customer"""
    customer = get_object_or_404(MdmCustomer, id=customer_id)
    
    if request.method == 'POST':
        try:
            customer.customer_id = request.POST['customer_id']
            customer.name = request.POST['name']
            customer.email = request.POST['email']
            customer.phone = request.POST.get('phone', '')
            customer.address = request.POST.get('address', '')
            customer.save()
            
            messages.success(request, f'Customer {customer.name} updated successfully')
            return redirect('mdm:customer_list')
        except Exception as e:
            messages.error(request, f'Error updating customer: {str(e)}')
    
    return render(request, 'mdm/edit_customer.html', {'customer': customer})

@login_required
@require_package_access('mdm')
def delete_customer(request, customer_id):
    """Delete customer"""
    customer = get_object_or_404(MdmCustomer, id=customer_id)
    
    if request.method == 'POST':
        name = customer.name
        customer.delete()
        messages.success(request, f'Customer {name} deleted successfully')
        return redirect('mdm:customer_list')
    
    return render(request, 'mdm/delete_customer.html', {'customer': customer})

@login_required
@require_package_access('mdm')
def add_user(request):
    """Add new user"""
    if request.method == 'POST':
        try:
            from django.contrib.auth.models import User
            user = User.objects.create_user(
                username=request.POST['username'],
                email=request.POST['email'],
                first_name=request.POST.get('first_name', ''),
                last_name=request.POST.get('last_name', '')
            )
            messages.success(request, f'User {user.username} added successfully')
            return redirect('mdm:user_list')
        except Exception as e:
            messages.error(request, f'Error creating user: {str(e)}')
    
    return render(request, 'mdm/add_user.html')

@login_required
@require_package_access('mdm')
def edit_user(request, user_id):
    """Edit existing user"""
    from django.contrib.auth.models import User
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        try:
            user.username = request.POST['username']
            user.email = request.POST['email']
            user.first_name = request.POST.get('first_name', '')
            user.last_name = request.POST.get('last_name', '')
            user.save()
            
            messages.success(request, f'User {user.username} updated successfully')
            return redirect('mdm:user_list')
        except Exception as e:
            messages.error(request, f'Error updating user: {str(e)}')
    
    return render(request, 'mdm/edit_user.html', {'user': user})

@login_required
@require_package_access('mdm')
def delete_user(request, user_id):
    """Delete user"""
    from django.contrib.auth.models import User
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'User {username} deleted successfully')
        return redirect('mdm:user_list')
    
    return render(request, 'mdm/delete_user.html', {'user': user})

@login_required
@require_package_access('mdm')
def add_device_group(request, customer_id):
    """Add device group"""
    customer = get_object_or_404(MdmCustomer, id=customer_id)
    
    if request.method == 'POST':
        try:
            group = DeviceGroup.objects.create(
                name=request.POST['name'],
                description=request.POST.get('description', ''),
                customer=customer
            )
            messages.success(request, f'Device group {group.name} added successfully')
            return redirect('mdm:customer_detail', customer_id=customer_id)
        except Exception as e:
            messages.error(request, f'Error creating device group: {str(e)}')
    
    return render(request, 'mdm/add_device_group.html', {'customer': customer})

@login_required
@require_package_access('mdm')
def create_profile(request):
    """Create new profile"""
    if request.method == 'POST':
        try:
            profile = Profile.objects.create(
                name=request.POST['name'],
                description=request.POST.get('description', ''),
                profile_type=request.POST['profile_type'],
                configuration=request.POST.get('configuration', '{}')
            )
            messages.success(request, f'Profile {profile.name} created successfully')
            return redirect('mdm:profiles_list')
        except Exception as e:
            messages.error(request, f'Error creating profile: {str(e)}')
    
    return render(request, 'mdm/create_profile.html')

@login_required
@require_package_access('mdm')
@require_admin_or_technician
def add_to_blacklist(request):
    """
    POST /mdm/policies/add-blacklist/
    Adds an app to the MDM blacklist via API.
    Expects: app_group_id (from app repository), app_name, package_name
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    from .manageengine_mdm_service import ManageEngineMDMService
    svc = ManageEngineMDMService()

    app_group_id = request.POST.get('app_group_id', '').strip()
    app_name     = request.POST.get('app_name', '').strip()
    package_name = request.POST.get('package_name', '').strip()

    if not app_group_id:
        return JsonResponse({'status': 'error', 'message': 'app_group_id required'}, status=400)

    result = svc.add_app_to_blacklist(app_group_id)

    if result is None:
        # API unreachable — fall back to local DB record
        try:
            mdm_customer = MdmCustomer.objects.first()
            policy, created = AppPolicy.objects.get_or_create(
                package_name=package_name or app_group_id,
                mdm_customer=mdm_customer,
                defaults={
                    'app_name': app_name or app_group_id,
                    'policy_type': 'block',
                }
            )
            return JsonResponse({
                'status': 'warning',
                'message': f'MDM API unreachable. Saved "{app_name}" locally only.',
            })
        except Exception as exc:
            return JsonResponse({'status': 'error', 'message': str(exc)}, status=500)

    return JsonResponse({
        'status': 'success',
        'message': f'"{app_name}" added to blacklist.',
        'api_response': result,
    })


@login_required
@require_package_access('mdm')
@require_admin_or_technician
def remove_from_blacklist(request, app_id):
    """
    POST /mdm/policies/remove-blacklist/<app_id>/
    app_id here is the app_group_id from the MDM API.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    from .manageengine_mdm_service import ManageEngineMDMService
    svc = ManageEngineMDMService()

    result = svc.remove_app_from_blacklist(app_id)

    if result is None:
        # Try removing local DB record as fallback
        AppPolicy.objects.filter(package_name=str(app_id)).delete()
        return JsonResponse({
            'status': 'warning',
            'message': 'MDM API unreachable. Removed local record only.',
        })

    return JsonResponse({
        'status': 'success',
        'message': f'App {app_id} removed from blacklist.',
        'api_response': result,
    })


@login_required
@require_package_access('mdm')
@require_admin_or_technician
def api_blacklist_apps(request):
    """GET /mdm/api/blacklist-apps/ — live blacklist from MDM API as JSON."""
    from .manageengine_mdm_service import ManageEngineMDMService
    svc = ManageEngineMDMService()
    apps = svc.get_blacklist_apps()
    return JsonResponse({
        'status': 'success' if apps is not None else 'error',
        'apps': apps or [],
        'count': len(apps or []),
    })


@login_required
@require_package_access('mdm')
@require_admin_or_technician
def api_app_repository(request):
    """GET /mdm/api/apps/ — full app repository from MDM API as JSON."""
    from .manageengine_mdm_service import ManageEngineMDMService
    svc = ManageEngineMDMService()
    apps = svc.get_all_apps()
    return JsonResponse({
        'status': 'success' if apps is not None else 'error',
        'apps': apps or [],
        'count': len(apps or []),
    })


@login_required
@require_package_access('mdm')
@require_admin_or_technician
def api_profiles_list(request):
    """GET /mdm/api/profiles/ — profiles from MDM API as JSON."""
    from .manageengine_mdm_service import ManageEngineMDMService
    svc = ManageEngineMDMService()
    profiles = svc.get_all_profiles()
    return JsonResponse({
        'status': 'success' if profiles is not None else 'error',
        'profiles': profiles or [],
        'count': len(profiles or []),
    })

@login_required
@require_package_access('mdm')
def blacklist_devices(request):
    """Manage blacklisted devices"""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    devices = _fetch_live_devices(list(_scoped_customers(user_profile)))
    return render(request, 'mdm/blacklist_devices.html', {'devices': devices})

@login_required
@require_package_access('mdm')
def blacklist_groups(request):
    """Manage blacklisted groups"""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    scoped_customers = _scoped_customers(user_profile)
    groups = DeviceGroup.objects.filter(customer__in=scoped_customers)
    return render(request, 'mdm/blacklist_groups.html', {'groups': groups})

@login_required
@require_package_access('mdm')
@require_admin_or_technician
def device_action(request, device_id):
    """
    POST /mdm/devices/<id>/action/
    Sends a remote command to a device via ManageEngine MDM API.
    Body params: action (lock|wipe|restart|locate|ring|clear_passcode), message (optional)
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    user_profile = get_object_or_404(UserProfile, user=request.user)
    action = request.POST.get('action', '').strip()
    if not action:
        return JsonResponse({'status': 'error', 'message': 'action parameter required'}, status=400)

    allowed_actions = {
        'lock': 'Lock', 'wipe': 'Wipe', 'restart': 'Restart',
        'locate': 'Locate', 'ring': 'Ring', 'clear_passcode': 'Clear Passcode',
    }
    if action not in allowed_actions:
        return JsonResponse({'status': 'error', 'message': f'Unknown action: {action}'}, status=400)

    # Find the customer that owns this device for proper X-Customer header
    customer_id_header = request.POST.get('customer_id')
    if not customer_id_header:
        customer_id_header = next(
            (str(c.customer_id) for c in _scoped_customers(user_profile)), None
        )

    svc = ManageEngineMDMService()
    dispatch = {
        'lock':          lambda: svc.lock_device(str(device_id), customer_id=customer_id_header,
                                                  message=request.POST.get('message')),
        'wipe':          lambda: svc.wipe_device(str(device_id), customer_id=customer_id_header),
        'restart':       lambda: svc.restart_device(str(device_id), customer_id=customer_id_header),
        'locate':        lambda: svc.locate_device(str(device_id), customer_id=customer_id_header),
        'ring':          lambda: svc.ring_device(str(device_id), customer_id=customer_id_header),
        'clear_passcode': lambda: svc.clear_passcode(str(device_id), customer_id=customer_id_header),
    }
    result = dispatch[action]()

    if result is None:
        return JsonResponse({
            'status': 'error',
            'message': 'MDM API unreachable. Check MDM_API_BASE_URL / MDM_API_KEY in settings.',
        }, status=502)

    return JsonResponse({
        'status': 'success',
        'action': action,
        'action_label': allowed_actions[action],
        'device_id': device_id,
        'api_response': result,
    })


@login_required
@require_package_access('mdm')
@require_admin_or_technician
def device_command_history(request, device_id):
    """GET /mdm/devices/<id>/history/ — command history from MDM API."""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    svc = ManageEngineMDMService()
    # Try all scoped customers until we get a result
    history = []
    for customer in _scoped_customers(user_profile):
        h = svc.get_command_history(str(device_id), customer_id=customer.customer_id)
        if h:
            history = h
            break
    return JsonResponse({'status': 'success', 'device_id': device_id, 'history': history})


@login_required
@require_package_access('mdm')
@require_admin_or_technician
def device_sync(request, device_id):
    """POST /mdm/devices/<id>/sync/ — no-op since data is always fetched live."""
    # MDM data is now fetched live from the API on every page load.
    # This endpoint is kept for backwards compatibility but does nothing.
    return JsonResponse({'status': 'success', 'message': 'MDM data is always live — no sync needed.'})


@login_required
@require_package_access('mdm')
def api_test(request):
    """API test endpoint"""
    return JsonResponse({'status': 'success', 'message': 'MDM API is working'})

@login_required
@require_package_access('mdm')
def live_status(request):
    """Live status endpoint — fetches from MDM API."""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    customers = list(_scoped_customers(user_profile))
    all_devices = _fetch_live_devices(customers)

    customer_data = []
    for customer in customers:
        cdevs = [d for d in all_devices if d['customer_id_str'] == str(customer.customer_id)]
        customer_data.append({
            'customer_id':   customer.customer_id,
            'name':          customer.company.name,
            'device_count':  len(cdevs),
            'active_devices': sum(1 for d in cdevs if d['status'] == 'active'),
            'status':        'online',
        })

    return JsonResponse({
        'status':        'success',
        'total_devices': len(all_devices),
        'active_devices': sum(1 for d in all_devices if d['status'] == 'active'),
        'customers':     customer_data,
        'timestamp':     timezone.now().isoformat(),
    })

@login_required
@require_package_access('mdm')
@require_admin_only
def admin_dashboard(request):
    """Admin-only dashboard — live data fetched from MDM API."""
    all_customers = list(MdmCustomer.objects.select_related('company').all())
    all_devices   = _fetch_live_devices(all_customers)

    total_devices   = len(all_devices)
    active_devices  = sum(1 for d in all_devices if d['status'] == 'active')
    pending_devices = sum(1 for d in all_devices if d['status'] in ('enrollment_pending', 'staged'))
    retired_devices = sum(1 for d in all_devices if d['status'] == 'retired')

    # Per-customer live stats
    customer_stats = []
    for customer in all_customers:
        cdevs = [d for d in all_devices if d['customer_id_str'] == str(customer.customer_id)]
        tot = len(cdevs)
        act = sum(1 for d in cdevs if d['status'] == 'active')
        customer_stats.append({
            'customer':        customer,
            'total_devices':   tot,
            'active_devices':  act,
            'pending_devices': sum(1 for d in cdevs if d['status'] in ('enrollment_pending', 'staged')),
            'retired_devices': sum(1 for d in cdevs if d['status'] == 'retired'),
            'active_pct':      round(act * 100 / tot) if tot else 0,
        })

    # Device type breakdown
    from collections import Counter
    type_counter = Counter(d['device_type'] for d in all_devices)
    device_types = [{'device_type': t, 'count': c} for t, c in type_counter.most_common()]

    # Most recently seen devices
    recent_devices = sorted(
        [d for d in all_devices if d['last_contact_time']],
        key=lambda d: d['last_contact_time'], reverse=True
    )[:10]

    context = {
        'total_companies':  Company.objects.filter(mdm_customer__isnull=False).count(),
        'total_customers':  len(all_customers),
        'total_devices':    total_devices,
        'total_users':      MdmUser.objects.count(),
        'active_devices':   active_devices,
        'pending_devices':  pending_devices,
        'retired_devices':  retired_devices,
        'security_events':  0,
        'company_stats':    [],
        'customer_stats':   customer_stats,
        'recent_devices':   recent_devices,
        'recent_events':    [],
        'device_types':     device_types,
        'license_usage':    [],
        'user_role':        'admin',
    }
    return render(request, 'mdm/admin_dashboard.html', context)

@login_required
@require_package_access('mdm')
@require_admin_only
def admin_company_management(request):
    """Admin view for managing companies and their MDM access (live API device counts)."""
    # Fetch ALL live devices once, then aggregate per company
    all_customers = list(MdmCustomer.objects.select_related('company').all())
    all_devices   = _fetch_live_devices(all_customers)

    # Build a customer_id → device stats map
    customer_stats = {}
    for d in all_devices:
        cid = d['customer_id_str']
        if cid not in customer_stats:
            customer_stats[cid] = {'total': 0, 'active': 0}
        customer_stats[cid]['total'] += 1
        if d['status'] == 'active':
            customer_stats[cid]['active'] += 1

    # Build per-company summary
    company_list = []
    for company in Company.objects.filter(mdm_customer__isnull=False).order_by('name'):
        company_customers = [c for c in all_customers if c.company_id == company.id]
        total  = sum(customer_stats.get(str(c.customer_id), {}).get('total', 0) for c in company_customers)
        active = sum(customer_stats.get(str(c.customer_id), {}).get('active', 0) for c in company_customers)
        company_list.append({
            'id':               company.id,
            'name':             company.name,
            'customer_count':   len(company_customers),
            'device_count':     total,
            'active_device_count': active,
        })

    context = {
        'companies': company_list,
        'user_role': 'admin',
    }
    return render(request, 'mdm/admin_company_management.html', context)

@login_required
@require_package_access('mdm')
@require_admin_only
def admin_user_management(request):
    """Admin view for managing all MDM users across companies"""
    mdm_users = MdmUser.objects.select_related('user', 'mdm_customer__company').order_by('mdm_customer__company__name', 'user__username')
    
    # Search functionality
    search = request.GET.get('search', '')
    if search:
        mdm_users = mdm_users.filter(
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search) |
            Q(mdm_customer__company__name__icontains=search)
        )
    
    context = {
        'mdm_users': mdm_users,
        'search': search,
        'user_role': 'admin',
    }
    
    return render(request, 'mdm/admin_user_management.html', context)

@login_required
@require_package_access('mdm')
@require_admin_only
def admin_system_settings(request):
    """Admin view for system-wide MDM settings"""
    from .models import EnrollmentSettings
    
    # Get enrollment settings for all customers
    enrollment_settings = EnrollmentSettings.objects.select_related('mdm_customer__company').order_by('mdm_customer__company__name')
    
    context = {
        'enrollment_settings': enrollment_settings,
        'user_role': 'admin',
    }
    
    return render(request, 'mdm/admin_system_settings.html', context)
@login_required
@require_package_access('mdm')
def no_access(request):
    """View for users without proper access"""
    return render(request, 'mdm/no_access.html')

@login_required
@require_package_access('mdm')
@require_admin_or_technician
def sync_all_data(request):
    """POST /mdm/api/sync-all/ — sync customers from ManageEngine MDM API.
    Admin syncs all; technician syncs only their company.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    from .manageengine_mdm_service import ManageEngineMDMService
    svc = ManageEngineMDMService()

    user_profile = get_object_or_404(UserProfile, user=request.user)
    customers_qs = _scoped_customers(user_profile).select_related('company')

    total_created = total_updated = 0
    results = []

    for mdm_customer in customers_qs:
        try:
            created, updated, skipped = svc.sync_devices_for_customer(mdm_customer)
            total_created += created
            total_updated += updated
            results.append({
                'company': mdm_customer.company.name,
                'customer_id': mdm_customer.customer_id,
                'created': created,
                'updated': updated,
                'skipped': skipped,
            })
        except Exception as exc:
            results.append({
                'company': mdm_customer.company.name,
                'error': str(exc),
            })

    return JsonResponse({
        'status': 'success',
        'total_created': total_created,
        'total_updated': total_updated,
        'results': results,
        'timestamp': timezone.now().isoformat(),
    })
