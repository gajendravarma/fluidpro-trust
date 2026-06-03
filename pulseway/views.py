import csv
import io
import json
import re
from datetime import datetime, timezone

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, redirect

from .services import PulsewayAPI
from .manageengine_service import ManageEngineAPI
from .company_matcher import CompanyMatcher
from .forms import SiteForm, GroupForm, ScriptForm, PatchForm, AutomationTaskForm, PolicyForm, DeviceEditForm
from .models import PulsewayAction


@login_required
def dashboard(request):
    """Pulseway dashboard showing overview"""
    try:
        from .local_service import PulsewayLocalService
        from .models import PulsewayDevice

        service = PulsewayLocalService()

        try:
            profile = request.user.userprofile
            user_role = profile.get_role()
            user_company = profile.company.name if profile.company else None
        except Exception:
            user_role = 'admin'
            user_company = None

        # Determine device queryset scope
        from rbac.utils import get_technician_companies
        if user_role == 'technician':
            allowed_orgs = get_technician_companies(request.user)
        else:
            allowed_orgs = None  # admin = unrestricted

        if user_role in ('admin', 'technician'):
            all_devices = PulsewayDevice.objects.all()
            if allowed_orgs is not None:
                all_devices = all_devices.filter(organization_name__in=allowed_orgs)
            company_stats = {
                'total_devices': all_devices.count(),
                'online_devices': all_devices.filter(status='online').count(),
                'offline_devices': all_devices.filter(status='offline').count(),
                'pending_patches': sum(d.pending_patches for d in all_devices),
                'up_to_date_patches': all_devices.filter(pending_patches=0).count(),
            }
            recent_device_list = [
                {
                    'Name': d.device_name,
                    'Identifier': d.device_id,
                    'OrganizationName': d.organization_name,
                    'Status': d.status,
                }
                for d in all_devices[:10]
            ]
        else:
            # Fetch LIVE from API so status is always current for the customer
            live_devices = _fetch_live_company_devices(user_company)
            online_count  = sum(1 for d in live_devices if d['status'] == 'online')
            offline_count = sum(1 for d in live_devices if d['status'] == 'offline')
            patches_total = sum(d['pending_patches'] for d in live_devices)
            company_stats = {
                'total_devices':    len(live_devices),
                'online_devices':   online_count,
                'offline_devices':  offline_count,
                'pending_patches':  patches_total,
                'up_to_date_patches': sum(1 for d in live_devices if not d['pending_patches']),
            }
            recent_device_list = [
                {
                    'Name': d['device_name'],
                    'Identifier': d['device_id'],
                    'OrganizationName': d['organization_name'],
                    'Status': d['status'],
                }
                for d in live_devices[:10]
            ]

        # Recent actions from DB (fast, no API call)
        recent_actions = list(PulsewayAction.objects.filter(
            user=request.user
        ).order_by('-created_at')[:5])

        context = {
            'total_devices': company_stats['total_devices'],
            'online_devices': company_stats['online_devices'],
            'offline_devices': company_stats['offline_devices'],
            'pending_patches': company_stats['pending_patches'],
            'up_to_date_patches': company_stats['up_to_date_patches'],
            'total_sites': 0,   # sites come from API; not cached locally
            'recent_devices': recent_device_list,
            'recent_sites': [],
            'recent_groups': [],
            'recent_actions': recent_actions,
            'company_name': user_company,
            'user_role': user_role,
        }

        return render(request, 'pulseway/dashboard.html', context)
    except Exception as e:
        messages.error(request, f"Error loading dashboard: {str(e)}")
        return render(request, 'pulseway/dashboard.html', {
            'total_devices': 0, 'online_devices': 0, 'offline_devices': 0,
            'total_sites': 0, 'total_groups': 0, 'recent_devices': [],
            'recent_sites': [], 'recent_actions': [], 'user_role': 'admin',
        })


@login_required
def devices_by_status_api(request):
    """Return devices filtered by status for dashboard modal, respecting company scope."""
    from .models import PulsewayDevice
    from .local_service import PulsewayLocalService

    status = request.GET.get('status', '')  # empty = all

    try:
        profile = request.user.userprofile
        user_role = profile.get_role()
        user_company = profile.company.name if profile.company else None
    except Exception:
        user_role = 'admin'
        user_company = None

    if user_role in ('admin', 'technician') or not user_company:
        from rbac.utils import get_technician_companies
        qs = PulsewayDevice.objects.all()
        if user_role == 'technician':
            allowed_orgs = get_technician_companies(request.user)
            if allowed_orgs is not None:
                qs = qs.filter(organization_name__in=allowed_orgs)
        if status and status.lower() != 'all':
            qs = qs.filter(status__iexact=status)
        devices = list(qs.order_by('device_name').values(
            'device_id', 'device_name', 'organization_name', 'status',
            'operating_system', 'pending_patches', 'last_seen'
        )[:500])
        for d in devices:
            if d['last_seen']:
                d['last_seen'] = d['last_seen'].strftime('%d %b %Y %H:%M')
    else:
        # Customer: use live API data for accurate status
        live = _fetch_live_company_devices(user_company)
        if status and status.lower() != 'all':
            live = [d for d in live if d['status'].lower() == status.lower()]
        devices = [
            {
                'device_id':       d['device_id'],
                'device_name':     d['device_name'],
                'organization_name': d['organization_name'],
                'status':          d['status'],
                'operating_system': d['operating_system'],
                'pending_patches': d['pending_patches'],
                'last_seen':       d['last_seen'],
                'ip_address':      d['ip_address'],
            }
            for d in live
        ]

    return JsonResponse({'devices': devices, 'total': len(devices)})


@login_required
def devices(request):
    """List all devices with pagination and search"""
    try:
        from .local_service import PulsewayLocalService
        from .models import PulsewayDevice
        from django.core.paginator import Paginator
        
        service = PulsewayLocalService()
        
        try:
            profile = request.user.userprofile
            user_role = profile.get_role()
            user_company = profile.company.name if profile.company else None
        except Exception:
            user_role = 'admin'
            user_company = None

        search_query = request.GET.get('search', '').strip()

        if user_role in ('admin', 'technician') or not user_company:
            # Admins/technicians: read from DB, applying company restriction if set
            from rbac.utils import get_technician_companies
            devices_queryset = PulsewayDevice.objects.all()
            if user_role == 'technician':
                allowed_orgs = get_technician_companies(request.user)
                if allowed_orgs is not None:
                    devices_queryset = devices_queryset.filter(organization_name__in=allowed_orgs)
            if search_query:
                devices_queryset = devices_queryset.filter(
                    device_name__icontains=search_query
                ) | devices_queryset.filter(
                    organization_name__icontains=search_query
                ) | devices_queryset.filter(
                    site_name__icontains=search_query
                ) | devices_queryset.filter(
                    ip_address__icontains=search_query
                )
            paginator = Paginator(devices_queryset, 20)
            devices_page = paginator.get_page(request.GET.get('page'))
            devices_list = []
            for device in devices_page:
                devices_list.append({
                    'Identifier': device.device_id,
                    'Name': device.device_name,
                    'OrganizationName': device.organization_name,
                    'SiteName': device.site_name,
                    'Status': device.status,
                    'IPAddress': device.ip_address,
                    'OperatingSystem': device.operating_system,
                    'Uptime': device.uptime,
                    'CPUUsage': f"{device.cpu_usage}%" if device.cpu_usage else "N/A",
                    'MemoryUsage': f"{device.memory_usage}%" if device.memory_usage else "N/A",
                    'DiskUsage': f"{device.disk_usage}%" if device.disk_usage else "N/A",
                    'PendingPatches': device.pending_patches,
                })
            devices_page.object_list = devices_list
            total = devices_queryset.count()
        else:
            # Customers: fetch LIVE from API so status is always accurate
            live_devices = _fetch_live_company_devices(user_company)
            if search_query:
                q = search_query.lower()
                live_devices = [
                    d for d in live_devices
                    if q in d['device_name'].lower()
                    or q in d['organization_name'].lower()
                    or q in d['ip_address'].lower()
                    or q in d['operating_system'].lower()
                ]
            total = len(live_devices)
            paginator = Paginator(live_devices, 20)
            devices_page = paginator.get_page(request.GET.get('page'))
            devices_list = []
            for d in devices_page:
                devices_list.append({
                    'Identifier': d['device_id'],
                    'Name': d['device_name'],
                    'OrganizationName': d['organization_name'],
                    'SiteName': d['site_name'],
                    'Status': d['status'],
                    'IPAddress': d['ip_address'] or 'N/A',
                    'OperatingSystem': d['operating_system'] or 'N/A',
                    'Uptime': d['uptime'] or 'N/A',
                    'CPUUsage': d['cpu_usage'] or 'N/A',
                    'MemoryUsage': d['memory_usage'] or 'N/A',
                    'DiskUsage': d['disk_usage'] or 'N/A',
                    'PendingPatches': d['pending_patches'],
                })
            devices_page.object_list = devices_list

        context = {
            'devices': devices_page,
            'search_query': search_query,
            'total_devices': total,
            'user_role': user_role,
        }
        return render(request, 'pulseway/devices.html', context)
    except Exception as e:
        messages.error(request, f"Error loading devices: {str(e)}")
        return render(request, 'pulseway/devices.html', {'devices': [], 'search_query': '', 'total_devices': 0, 'user_role': 'technician'})


@login_required
def sites(request):
    """List all sites with device counts"""
    try:
        user_role = _require_tech_or_admin(request)
    except Exception:
        try:
            user_role = request.user.userprofile.get_role()
        except Exception:
            user_role = 'admin'

    try:
        api = PulsewayAPI()
        sites_list = api.get_all_sites()
        devices = api.get_all_devices()

        for site in sites_list:
            site_devices = [d for d in devices if d.get('SiteId') == site.get('Id')]
            site['DeviceCount'] = len(site_devices)

        return render(request, 'pulseway/sites.html', {'sites': sites_list, 'user_role': user_role})
    except Exception as e:
        messages.error(request, f"Error loading sites: {str(e)}")
        return render(request, 'pulseway/sites.html', {'sites': [], 'user_role': user_role})


@login_required
def group_devices(request, group_id):
    """Show all devices within a specific group"""
    try:
        api = PulsewayAPI()
        groups = api.get_all_groups()
        devices = api.get_all_devices()
        
        # Convert group_id to int for comparison since API returns integer IDs
        try:
            group_id_int = int(group_id)
        except ValueError:
            messages.error(request, "Invalid group ID")
            return redirect('pulseway:groups')
        
        # Find the specific group
        group = next((g for g in groups if g.get('Id') == group_id_int), None)
        if not group:
            messages.error(request, "Group not found")
            return redirect('pulseway:groups')
        
        # Filter devices for this group
        group_devices = [d for d in devices if d.get('GroupId') == group_id_int]
        
        # Get detailed info for each device in the group
        for device in group_devices:
            try:
                details = api.get_device_details(device.get('Identifier'))
                if details and 'Data' in details:
                    device_data = details['Data']
                    # Update device with real API data
                    device.update(device_data)
                    
                    # Set status based on real uptime data
                    uptime = device.get('Uptime', 'Offline')
                    device['IsOnline'] = 'Offline' not in uptime
                    device['StatusClass'] = 'success' if device['IsOnline'] else 'danger'
                    device['StatusText'] = 'Online' if device['IsOnline'] else 'Offline'
                    device['LastSeen'] = uptime
            except:
                # Fallback for devices without detailed info
                device['IsOnline'] = False
                device['StatusClass'] = 'danger'
                device['StatusText'] = 'Offline'
                device['ExternalIpAddress'] = 'N/A'
                device['Description'] = 'Unknown'
                device['LastSeen'] = 'Unknown'
        
        # Pagination
        from django.core.paginator import Paginator
        paginator = Paginator(group_devices, 10)  # 10 devices per page
        page_number = request.GET.get('page')
        devices_page = paginator.get_page(page_number)
        
        context = {
            'group': group,
            'devices': devices_page,
            'device_count': len(group_devices)
        }
        
        return render(request, 'pulseway/group_devices.html', context)
    except Exception as e:
        messages.error(request, f"Error loading group devices: {str(e)}")
        return redirect('pulseway:groups')


@login_required
def groups(request):
    """List all groups with device counts"""
    try:
        user_role = _require_tech_or_admin(request)
    except Exception:
        try:
            user_role = request.user.userprofile.get_role()
        except Exception:
            user_role = 'admin'

    try:
        api = PulsewayAPI()
        groups_list = api.get_all_groups()
        devices = api.get_all_devices()

        for group in groups_list:
            group_devices = [d for d in devices if d.get('GroupId') == group.get('Id')]
            group['DeviceCount'] = len(group_devices)
            group['SiteName'] = group.get('ParentSiteName', 'N/A')

        return render(request, 'pulseway/groups.html', {'groups': groups_list, 'user_role': user_role})
    except Exception as e:
        messages.error(request, f"Error loading groups: {str(e)}")
        return render(request, 'pulseway/groups.html', {'groups': [], 'user_role': user_role})


@login_required
def organizations(request):
    """List all organizations"""
    try:
        api = PulsewayAPI()
        orgs = api.get_all_organizations()
        return render(request, 'pulseway/organizations.html', {'organizations': orgs})
    except Exception as e:
        messages.error(request, f"Error loading organizations: {str(e)}")
        return render(request, 'pulseway/organizations.html', {'organizations': []})


@login_required
def create_site(request):
    """Create a new site"""
    # Get organizations for dropdown
    try:
        api = PulsewayAPI()
        organizations = api.get_all_organizations()
    except:
        organizations = []
    
    if request.method == 'POST':
        form = SiteForm(request.POST, organizations=organizations)
        if form.is_valid():
            try:
                api = PulsewayAPI()
                site_data = {
                    'Name': form.cleaned_data['name'],
                    'Description': form.cleaned_data.get('description', ''),
                    'Address': form.cleaned_data.get('address', ''),
                    'ParentId': form.cleaned_data['parent_id'],
                }
                result = api.create_site(site_data)
                
                PulsewayAction.objects.create(
                    user=request.user,
                    action_type='site_create',
                    target_id=str(result.get('Id', 'unknown')),
                    target_name=form.cleaned_data['name'],
                    description=f"Created site: {form.cleaned_data['name']}",
                    status='completed',
                    result=result
                )
                
                messages.success(request, f"Site '{form.cleaned_data['name']}' created successfully!")
                return redirect('pulseway:sites')
            except Exception as e:
                messages.error(request, f"Error creating site: {str(e)}")
    else:
        form = SiteForm(organizations=organizations)
    
    return render(request, 'pulseway/create_site.html', {'form': form})


@login_required
def create_group(request):
    """Create a new group"""
    # Get sites for dropdown
    try:
        api = PulsewayAPI()
        sites = api.get_all_sites()
    except:
        sites = []
    
    if request.method == 'POST':
        form = GroupForm(request.POST, sites=sites)
        if form.is_valid():
            try:
                api = PulsewayAPI()
                group_data = {
                    'Name': form.cleaned_data['name'],
                    'Description': form.cleaned_data.get('description', ''),
                    'ParentId': form.cleaned_data['parent_id'],
                }
                result = api.create_group(group_data)
                
                PulsewayAction.objects.create(
                    user=request.user,
                    action_type='group_create',
                    target_id=str(result.get('Id', 'unknown')),
                    target_name=form.cleaned_data['name'],
                    description=f"Created group: {form.cleaned_data['name']}",
                    status='completed',
                    result=result
                )
                
                messages.success(request, f"Group '{form.cleaned_data['name']}' created successfully!")
                return redirect('pulseway:groups')
            except Exception as e:
                messages.error(request, f"Error creating group: {str(e)}")
    else:
        form = GroupForm(sites=sites)
    
    return render(request, 'pulseway/create_group.html', {'form': form})


@login_required
def run_script(request):
    """Run script on a selected device."""
    from .models import PulsewayDevice

    preselect_id = request.GET.get('device_id', '')

    try:
        profile = request.user.userprofile
        user_role = profile.get_role()
        user_company = profile.company.name if profile.company else None
    except Exception:
        user_role = 'admin'
        user_company = None

    if user_role in ('admin', 'technician') or not user_company:
        devices_qs = PulsewayDevice.objects.order_by('organization_name', 'device_name')
    else:
        from .local_service import PulsewayLocalService
        devices_qs = PulsewayLocalService().get_company_devices(user_company).order_by('device_name')

    if request.method == 'POST':
        device_id = request.POST.get('device_id', '').strip()
        script_type = request.POST.get('script_type', 'powershell')
        script_content = request.POST.get('script_content', '').strip()
        device_name = request.POST.get('device_name', device_id)

        if not device_id or not script_content:
            messages.error(request, "Please select a device and enter script content.")
        else:
            try:
                api = PulsewayAPI()
                result = api.run_script(device_id, {
                    'Name': f'Ad-hoc {script_type} — {device_name[:30]}',
                    'Content': script_content,
                    'Type': script_type.capitalize(),
                })
                PulsewayAction.objects.create(
                    user=request.user,
                    action_type='script',
                    target_id=device_id,
                    target_name=device_name,
                    description=f"Executed {script_type} script on {device_name}",
                    status='completed',
                    result=result if isinstance(result, dict) else {},
                )
                messages.success(request, f"Script queued for {device_name}. Check Actions History for result.")
                return redirect('pulseway:actions_history')
            except NotImplementedError:
                # Pulseway API does not support ad-hoc task creation
                return render(request, 'pulseway/run_script.html', {
                    'devices': devices_qs,
                    'preselect_id': preselect_id,
                    'user_role': user_role,
                    'api_not_supported': True,
                    'submitted_script': script_content,
                    'submitted_type': script_type,
                    'submitted_device': device_name,
                })
            except Exception as e:
                messages.error(request, f"Error running script: {e}")

    return render(request, 'pulseway/run_script.html', {
        'devices': devices_qs,
        'preselect_id': preselect_id,
        'user_role': user_role,
    })


@login_required
def install_patches(request):
    """Install patches on a selected device."""
    from .models import PulsewayDevice

    preselect_id = request.GET.get('device_id', '')

    try:
        profile = request.user.userprofile
        user_role = profile.get_role()
        user_company = profile.company.name if profile.company else None
    except Exception:
        user_role = 'admin'
        user_company = None

    if user_role in ('admin', 'technician') or not user_company:
        devices_qs = PulsewayDevice.objects.order_by('organization_name', 'device_name')
    else:
        from .local_service import PulsewayLocalService
        devices_qs = PulsewayLocalService().get_company_devices(user_company).order_by('device_name')

    if request.method == 'POST':
        device_id = request.POST.get('device_id', '').strip()
        device_name = request.POST.get('device_name', device_id)
        reboot_required = request.POST.get('reboot_required') == 'on'
        # Accept blank patch_ids → install all pending
        patch_ids_raw = request.POST.get('patch_ids', '').strip()
        patch_ids = [p.strip() for p in patch_ids_raw.splitlines() if p.strip()]

        if not device_id:
            messages.error(request, "Please select a device.")
        else:
            try:
                api = PulsewayAPI()
                result = api.install_patches(device_id, {
                    'PatchIds': patch_ids,
                    'RebootRequired': reboot_required,
                })
                PulsewayAction.objects.create(
                    user=request.user,
                    action_type='patch',
                    target_id=device_id,
                    target_name=device_name,
                    description=f"Queued {len(patch_ids) if patch_ids else 'all pending'} patches on {device_name}",
                    status='completed',
                    result=result if isinstance(result, dict) else {},
                )
                messages.success(request, f"Patch installation queued for {device_name}.")
                return redirect('pulseway:actions_history')
            except Exception as e:
                messages.error(request, f"Error installing patches: {e}")

    return render(request, 'pulseway/install_patches.html', {
        'devices': devices_qs,
        'preselect_id': preselect_id,
        'user_role': user_role,
    })


@login_required
@require_http_methods(["POST"])
def reboot_device(request, device_id):
    """Reboot a device"""
    try:
        api = PulsewayAPI()
        result = api.reboot_device(device_id)
        
        PulsewayAction.objects.create(
            user=request.user,
            action_type='reboot',
            target_id=device_id,
            target_name=f"Device {device_id}",
            description=f"Rebooted device {device_id}",
            status='completed',
            result=result
        )
        
        return JsonResponse({'success': True, 'message': 'Device reboot initiated'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_http_methods(["POST"])
def create_automation_task(request):
    """Create a new automation task"""
    try:
        # Get form data
        name = request.POST.get('name')
        description = request.POST.get('description')
        script_content = request.POST.get('script_content')
        
        if not name or not script_content:
            return JsonResponse({'success': False, 'message': 'Name and script content are required'})
        
        # Create task data
        task_data = {
            'Name': name,
            'Description': description,
            'Script': script_content
        }
        
        try:
            api = PulsewayAPI()
            result = api.create_automation_task(task_data)
            
            PulsewayAction.objects.create(
                user=request.user,
                action_type='automation_create',
                target_id=str(result.get('Id', 'unknown')),
                target_name=name,
                description=f"Created automation task: {name}",
                status='completed',
                result=result
            )
            
            return JsonResponse({'success': True, 'message': f'Automation task "{name}" created successfully'})
            
        except Exception as api_error:
            # Handle API limitation
            if '405' in str(api_error):
                return JsonResponse({
                    'success': False, 
                    'message': 'Task creation is not supported by the Pulseway API. Please create automation tasks directly in the Pulseway dashboard.'
                })
            else:
                return JsonResponse({'success': False, 'message': f'API Error: {str(api_error)}'})
            
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def automation_tasks(request):
    """List automation tasks with pagination and device list for targeting."""
    from .models import PulsewayDevice

    try:
        profile = request.user.userprofile
        user_role = profile.get_role()
        user_company = profile.company.name if profile.company else None
    except Exception:
        user_role = 'admin'
        user_company = None

    # Device list for "run on specific device" selector
    if user_role in ('admin', 'technician') or not user_company:
        devices_qs = PulsewayDevice.objects.order_by('organization_name', 'device_name')
    else:
        from .local_service import PulsewayLocalService
        devices_qs = PulsewayLocalService().get_company_devices(user_company).order_by('device_name')

    api = PulsewayAPI()
    tasks_list = []
    api_error = None
    try:
        all_tasks = api.get_all_automation_tasks()
        if isinstance(all_tasks, dict) and 'Data' in all_tasks:
            tasks_list = all_tasks['Data']
        elif isinstance(all_tasks, list):
            tasks_list = all_tasks
    except Exception as e:
        api_error = str(e)

    paginator = Paginator(tasks_list, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'pulseway/automation_tasks.html', {
        'tasks': page_obj,
        'total_tasks': len(tasks_list),
        'devices': devices_qs,
        'user_role': user_role,
        'api_error': api_error,
    })


@login_required
@require_http_methods(["POST"])
def run_automation_task(request, task_id):
    """Run an automation task, optionally targeting specific device IDs."""
    try:
        # Optional: user may pass device_ids[] from the run modal
        device_ids = request.POST.getlist('device_ids')
        payload = {}
        if device_ids:
            payload['DeviceIds'] = device_ids

        api = PulsewayAPI()
        # Run with payload (empty dict if no device override)
        result = api.automation.tasks(task_id).run.post(payload) if device_ids else api.run_automation_task(task_id)

        # Try to get task name
        task_name = f'Task {task_id}'
        try:
            all_tasks = api.get_all_automation_tasks()
            task = next((t for t in all_tasks if str(t.get('Id')) == str(task_id)), None)
            if task:
                task_name = task.get('Name', task_name)
        except Exception:
            pass

        device_count = len(device_ids) if device_ids else 0
        desc = f"Ran on {device_count} specific device(s)" if device_ids else "Ran on task's default scope"

        PulsewayAction.objects.create(
            user=request.user,
            action_type='automation_run',
            target_id=task_id,
            target_name=task_name,
            description=desc,
            status='completed',
            result=result if isinstance(result, dict) else {},
        )
        return JsonResponse({
            'success': True,
            'message': f'Task "{task_name}" started. {desc}. See Actions History for progress.',
            'device_count': device_count,
            'task_name': task_name,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_http_methods(["POST", "GET"])
def edit_automation_task(request, task_id):
    """Edit an automation task"""
    try:
        api = PulsewayAPI()
        
        if request.method == 'POST':
            # Handle form submission
            name = request.POST.get('name')
            description = request.POST.get('description')
            script_content = request.POST.get('script_content')
            
            if not name:
                return JsonResponse({'success': False, 'message': 'Name is required'})
            
            # Update task data
            task_data = {
                'Name': name,
                'Description': description,
                'Script': script_content
            }
            
            result = api.update_automation_task(task_id, task_data)
            
            PulsewayAction.objects.create(
                user=request.user,
                action_type='automation_update',
                target_id=task_id,
                target_name=name,
                description=f"Updated automation task {task_id}",
                status='completed',
                result=result
            )
            
            return JsonResponse({'success': True, 'message': 'Automation task updated successfully'})
        
        else:
            # GET request - return task details for editing
            try:
                all_tasks = api.get_all_automation_tasks()
                task = None
                
                # Find the task by ID
                for t in all_tasks:
                    if str(t.get('Id')) == str(task_id):
                        task = t
                        break
                
                if task:
                    # The basic task API doesn't include script content
                    # Available fields: Id, Name, Description, IsEnabled, ScopeId, ScopeName, 
                    # UpdatedAt, IsScheduled, TotalScripts, IsBuiltIn, ContinueOnError, ExecutionState, FolderPath
                    
                    return JsonResponse({
                        'success': True,
                        'task': {
                            'id': task.get('Id'),
                            'name': task.get('Name', ''),
                            'description': task.get('Description', ''),
                            'script': 'Script content not available in API response.\n\n# Note: The Pulseway automation tasks API does not return\n# the actual script content in the task list.\n# You can update the name and description, but the\n# script content needs to be entered manually.',
                            'is_builtin': task.get('IsBuiltIn', False),
                            'total_scripts': task.get('TotalScripts', 0)
                        }
                    })
                else:
                    return JsonResponse({'success': False, 'message': f'Task with ID {task_id} not found'})
            except Exception as e:
                print(f"Error fetching task details: {e}")
                return JsonResponse({'success': False, 'message': f'Unable to fetch task details: {str(e)}'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_automation_task(request, task_id):
    """Delete an automation task"""
    try:
        api = PulsewayAPI()
        
        # Get task name before deletion
        try:
            all_tasks = api.get_all_automation_tasks()
            task = next((t for t in all_tasks if str(t.get('Id')) == str(task_id)), None)
            task_name = task.get('Name', f'Task {task_id}') if task else f'Task {task_id}'
        except:
            task_name = f'Task {task_id}'
        
        result = api.delete_automation_task(task_id)
        
        PulsewayAction.objects.create(
            user=request.user,
            action_type='automation_delete',
            target_id=task_id,
            target_name=task_name,
            description=f"Deleted automation task {task_id}",
            status='completed',
            result=result
        )
        
        return JsonResponse({'success': True, 'message': f'Automation task "{task_name}" deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def actions_history(request):
    """View action history with pagination."""
    qs = PulsewayAction.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'pulseway/actions_history.html', {
        'actions': page_obj,
        'total_actions': qs.count(),
    })

@login_required
def edit_site(request, site_id):
    """Edit a site"""
    try:
        api = PulsewayAPI()
        site = api.api.sites(site_id).get()
        site_data = site.get('Data', site) if isinstance(site, dict) else site
        organizations = api.get_all_organizations()
        
        if request.method == 'POST':
            form = SiteForm(request.POST, organizations=organizations)
            if form.is_valid():
                try:
                    update_data = {
                        'Name': form.cleaned_data['name'],
                        'Description': form.cleaned_data.get('description', ''),
                        'Address': form.cleaned_data.get('address', ''),
                        'ParentId': form.cleaned_data['parent_id'],
                    }
                    result = api.update_site(site_id, update_data)
                    
                    PulsewayAction.objects.create(
                        user=request.user,
                        action_type='site_update',
                        target_id=site_id,
                        target_name=form.cleaned_data['name'],
                        description=f"Updated site: {form.cleaned_data['name']}",
                        status='completed',
                        result=result
                    )
                    
                    messages.success(request, f"Site '{form.cleaned_data['name']}' updated successfully!")
                    return redirect('pulseway:sites')
                except Exception as e:
                    messages.error(request, f"Error updating site: {str(e)}")
        else:
            initial_data = {
                'name': site_data.get('Name', ''),
                'description': site_data.get('Description', ''),
                'address': site_data.get('Address', ''),
                'parent_id': site_data.get('ParentId', ''),
            }
            form = SiteForm(initial=initial_data, organizations=organizations)
        
        return render(request, 'pulseway/edit_site.html', {
            'form': form, 
            'site': site_data
        })
    except Exception as e:
        messages.error(request, f"Error loading site: {str(e)}")
        return redirect('pulseway:sites')


@login_required
@require_http_methods(["POST"])
def delete_site(request, site_id):
    """Delete a site — not supported by Pulseway API (only GET/POST/PUT allowed)."""
    return JsonResponse({
        'success': False,
        'message': 'Site deletion is not supported by the Pulseway API. Please delete the site directly from the Pulseway web console.'
    }, status=405)


@login_required
def edit_group(request, group_id):
    """Edit a group"""
    try:
        api = PulsewayAPI()
        group = api.api.groups(group_id).get()
        group_data = group.get('Data', group) if isinstance(group, dict) else group
        sites = api.get_all_sites()
        
        if request.method == 'POST':
            form = GroupForm(request.POST, sites=sites)
            if form.is_valid():
                try:
                    update_data = {
                        'Name': form.cleaned_data['name'],
                        'Description': form.cleaned_data.get('description', ''),
                        'ParentId': form.cleaned_data['parent_id'],
                    }
                    result = api.update_group(group_id, update_data)
                    
                    PulsewayAction.objects.create(
                        user=request.user,
                        action_type='group_update',
                        target_id=group_id,
                        target_name=form.cleaned_data['name'],
                        description=f"Updated group: {form.cleaned_data['name']}",
                        status='completed',
                        result=result
                    )
                    
                    messages.success(request, f"Group '{form.cleaned_data['name']}' updated successfully!")
                    return redirect('pulseway:groups')
                except Exception as e:
                    messages.error(request, f"Error updating group: {str(e)}")
        else:
            initial_data = {
                'name': group_data.get('Name', ''),
                'description': group_data.get('Description', ''),
                'parent_id': group_data.get('ParentId', '') or group_data.get('ParentSiteId', ''),
            }
            form = GroupForm(initial=initial_data, sites=sites)
        
        return render(request, 'pulseway/edit_group.html', {
            'form': form, 
            'group': group_data
        })
    except Exception as e:
        messages.error(request, f"Error loading group: {str(e)}")
        return redirect('pulseway:groups')


@login_required
@require_http_methods(["POST"])
def delete_group(request, group_id):
    """Delete a group"""
    try:
        api = PulsewayAPI()
        group = api.api.groups(group_id).get()
        group_data = group.get('Data', group) if isinstance(group, dict) else group
        group_name = group_data.get('Name', f'Group {group_id}')
        
        result = api.delete_group(group_id)
        
        PulsewayAction.objects.create(
            user=request.user,
            action_type='group_delete',
            target_id=group_id,
            target_name=group_name,
            description=f"Deleted group: {group_name}",
            status='completed',
            result=result
        )
        
        return JsonResponse({'success': True, 'message': f'Group "{group_name}" deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def company_dashboard(request):
    """Company-level dashboard with device, patch, and ticket status"""
    try:
        api = PulsewayAPI()
        
        # Define companies - using actual ManageEngine company names
        companies = [
            'MarketXcel',
            'CG Logistics', 
            'Digtinctive',
            'Aiqmen',
            'FIICC',
            'SOC'
        ]
        
        selected_company = request.GET.get('company', companies[0])
        
        # Get all data
        all_devices = api.get_all_devices_with_details(max_devices=1000)
        all_sites = api.get_all_sites()
        all_organizations = api.get_all_organizations()
        
        # Filter data by company using fuzzy matching
        company_devices = []
        company_sites = []
        
        # Get all Pulseway organizations for matching
        pulseway_orgs = set()
        for device in all_devices:
            org_name = device.get('OrganizationName', '')
            if org_name:
                pulseway_orgs.add(org_name)
        
        # Find best matching Pulseway organization
        matched_pulseway_org = CompanyMatcher.match_company(selected_company, list(pulseway_orgs))
        
        # Filter devices using fuzzy matching
        for device in all_devices:
            org_name = device.get('OrganizationName', '')
            site_name = device.get('SiteName', '')
            
            if (CompanyMatcher.similarity(selected_company, org_name) > 0.6 or
                CompanyMatcher.similarity(selected_company, site_name) > 0.6 or
                CompanyMatcher.similarity(matched_pulseway_org, org_name) > 0.8):
                company_devices.append(device)
        
        # Filter sites using fuzzy matching
        for site in all_sites:
            site_name = site.get('Name', '')
            if CompanyMatcher.similarity(selected_company, site_name) > 0.6:
                company_sites.append(site)
        
        # Calculate device status using same logic as main dashboard
        total_devices = len(company_devices)
        online_devices = len([d for d in company_devices if d.get('Uptime') and 'Offline' not in d.get('Uptime', '')])
        offline_devices = total_devices - online_devices
        
        # Calculate patch status (mock data - replace with actual API calls)
        pending_patches = int(total_devices * 0.3)  # 30% need patches
        up_to_date = total_devices - pending_patches
        
        # Calculate ticket status using real ManageEngine API data
        me_api = ManageEngineAPI()
        ticket_stats = me_api.get_ticket_stats(selected_company)
        
        open_tickets = ticket_stats['open_tickets']
        resolved_tickets = ticket_stats['closed_tickets'] + ticket_stats['resolved_tickets']
        pending_tickets = ticket_stats['pending_tickets']
        in_progress_tickets = ticket_stats['in_progress_tickets']
        
        context = {
            'companies': companies,
            'selected_company': selected_company,
            'total_devices': total_devices,
            'online_devices': online_devices,
            'offline_devices': offline_devices,
            'total_sites': len(company_sites),
            'pending_patches': pending_patches,
            'up_to_date_patches': up_to_date,
            'open_tickets': open_tickets,
            'resolved_tickets': resolved_tickets,
            'pending_tickets': pending_tickets,
            'in_progress_tickets': in_progress_tickets,
            'company_devices': company_devices[:10],  # Show first 10 devices
            'company_sites': company_sites[:5],  # Show first 5 sites
        }
        
        template = 'pulseway/company_dashboard_embed.html' if request.GET.get('embed') else 'pulseway/company_dashboard.html'
        return render(request, template, context)
        
    except Exception as e:
        messages.error(request, f"Error loading company dashboard: {str(e)}")
        companies = ['MarketXcel', 'CG Logistics', 'Digtinctive Pune', 'Aiqmen', 'FIICC']
        return render(request, 'pulseway/company_dashboard.html', {
            'companies': companies,
            'selected_company': companies[0],
            'total_devices': 0,
            'online_devices': 0,
            'offline_devices': 0,
            'total_sites': 0,
            'pending_patches': 0,
            'up_to_date_patches': 0,
            'open_tickets': 0,
            'resolved_tickets': 0,
            'pending_tickets': 0,
            'in_progress_tickets': 0,
            'company_devices': [],
            'company_sites': [],
        })


@login_required
def get_company_data(request):
    """AJAX endpoint to get company data"""
    company = request.GET.get('company')
    if not company:
        return JsonResponse({'error': 'Company parameter required'})
    
    try:
        api = PulsewayAPI()
        
        # Get all data
        all_devices = api.get_all_devices_with_details(max_devices=1000)
        all_sites = api.get_all_sites()
        
        # Filter by company (organization name and site name)
        company_devices = []
        for device in all_devices:
            org_name = device.get('OrganizationName', '')
            site_name = device.get('SiteName', '')
            if (company.lower() in org_name.lower() or 
                company.lower() in site_name.lower()):
                company_devices.append(device)
        
        company_sites = [s for s in all_sites if company.lower() in s.get('Name', '').lower()]
        
        # Calculate stats using same logic as main dashboard
        total_devices = len(company_devices)
        online_devices = len([d for d in company_devices if d.get('Uptime') and 'Offline' not in d.get('Uptime', '')])
        
        # Get real ticket data from ManageEngine
        me_api = ManageEngineAPI()
        ticket_stats = me_api.get_ticket_stats(company)
        
        data = {
            'total_devices': total_devices,
            'online_devices': online_devices,
            'offline_devices': total_devices - online_devices,
            'total_sites': len(company_sites),
            'pending_patches': int(total_devices * 0.3),
            'up_to_date_patches': int(total_devices * 0.7),
            'open_tickets': ticket_stats['open_tickets'],
            'resolved_tickets': ticket_stats['closed_tickets'] + ticket_stats['resolved_tickets'],
            'pending_tickets': ticket_stats['pending_tickets'],
            'in_progress_tickets': ticket_stats['in_progress_tickets'],
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)})


@login_required
def remote_desktop(request, device_id):
    """Initiate remote desktop connection to a device"""
    try:
        api = PulsewayAPI()
        
        # Get device details
        device = api.get_device_details(device_id)
        if not device or 'Data' not in device:
            messages.error(request, "Device not found")
            return redirect('pulseway:devices')
        
        device_data = device['Data']
        device_name = device_data.get('Name', 'Unknown Device')
        
        # Check if device is online
        uptime = device_data.get('Uptime', 'Offline')
        if 'Offline' in uptime:
            messages.warning(request, f"Device '{device_name}' is currently offline. Remote desktop may not be available.")
        
        # Get remote desktop URL (web console)
        remote_url = api.get_remote_desktop_url(device_id)
        
        # Log the action
        PulsewayAction.objects.create(
            user=request.user,
            action_type='remote_desktop',
            target_id=device_id,
            target_name=device_name,
            description="Initiated remote desktop connection via web console",
            status='completed',
        )
        
        messages.success(request, f"Opening remote desktop for '{device_name}' in Pulseway web console...")
        
        # Redirect to Pulseway web console
        return redirect(remote_url)
        
    except Exception as e:
        messages.error(request, f"Error initiating remote desktop: {str(e)}")
        return redirect('pulseway:devices')

@login_required
def pulseway_devices_api(request):
    """API for paginated pulseway devices (company-scoped for customers)."""
    from .models import PulsewayDevice
    from .local_service import PulsewayLocalService

    page = int(request.GET.get('page', 1))
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', 'all')
    order = request.GET.get('order', 'desc')

    try:
        profile = request.user.userprofile
        user_role = profile.get_role()
        user_company = profile.company.name if profile.company else None
    except Exception:
        user_role = 'admin'
        user_company = None

    if user_role in ('admin', 'technician') or not user_company:
        qs = PulsewayDevice.objects.all()
    else:
        svc = PulsewayLocalService()
        company_devices = svc.get_company_devices(user_company)
        ids = [d.id for d in company_devices]
        qs = PulsewayDevice.objects.filter(id__in=ids)
    
    if status == 'online':
        qs = qs.filter(status='online')
    elif status == 'offline':
        qs = qs.filter(status='offline')
    
    if search:
        qs = qs.filter(
            models.Q(device_name__icontains=search) |
            models.Q(organization_name__icontains=search) |
            models.Q(ip_address__icontains=search) |
            models.Q(operating_system__icontains=search)
        )
    
    order_field = '-last_updated' if order == 'desc' else 'last_updated'
    qs = qs.order_by(order_field)
    
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(page)
    
    devices = []
    for device in page_obj:
        devices.append({
            'device_name': device.device_name,
            'status': device.status,
            'organization_name': device.organization_name or 'N/A',
            'ip_address': device.ip_address or 'N/A',
            'operating_system': device.operating_system or 'N/A',
            'pending_patches': device.pending_patches or 0,
            'uptime': device.uptime or 'N/A',
            'last_updated': device.last_updated.strftime('%d %b %Y') if device.last_updated else 'N/A'
        })
    
    return JsonResponse({
        'devices': devices,
        'total': paginator.count,
        'page': page_obj.number,
        'total_pages': paginator.num_pages,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'search': search,
        'status': status,
        'order': order
    })


@login_required
def debug_device_fields(request, device_id):
    """Debug view: show all raw API fields for a device — superuser only."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Superuser only'}, status=403)
    api = PulsewayAPI()
    result = {}
    try:
        basic = api.get_all_devices()
        result['basic_list_sample'] = next((d for d in basic if d.get('Identifier') == device_id), None)
    except Exception as e:
        result['basic_list_error'] = str(e)
    try:
        detail = api.get_device_details(device_id)
        result['device_detail_raw'] = detail
    except Exception as e:
        result['device_detail_error'] = str(e)
    return JsonResponse(result, json_dumps_params={'indent': 2})


@login_required
def trigger_device_sync(request):
    """Manually trigger a Pulseway device sync — admin role only."""
    try:
        role = request.user.userprofile.get_role()
    except Exception:
        role = 'admin' if request.user.is_superuser else 'customer'
    if role not in ('admin',) and not request.user.is_superuser:
        return JsonResponse({'error': 'Admin only'}, status=403)

    sync_type = request.POST.get('sync_type', 'all') if request.method == 'POST' else request.GET.get('sync_type', 'all')
    try:
        from .local_service import PulsewayLocalService
        from .models import PulsewayDevice, PulsewaySync
        service = PulsewayLocalService()
        if sync_type == 'devices':
            service.sync_devices()
        elif sync_type == 'organizations':
            service.sync_organizations()
        elif sync_type == 'status':
            # Per-device detail sync — can take several minutes for large device counts
            service.sync_device_status(delay_seconds=2.0)
        else:
            service.sync_all_data()
        count = PulsewayDevice.objects.count()
        online = PulsewayDevice.objects.filter(status='online').count()
        last_sync = PulsewaySync.objects.filter(sync_type='devices').order_by('-last_sync').first()
        return JsonResponse({
            'success': True,
            'devices_in_db': count,
            'devices_online': online,
            'last_sync': last_sync.last_sync.strftime('%d %b %Y %H:%M:%S') if last_sync else 'N/A',
            'sync_type': sync_type,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_vs_db_compare(request):
    """
    Admin-only diagnostic page.
    Fetches all devices live from the Pulseway API, compares their IsOnline /
    status against what is stored in the local DB, and highlights mismatches.
    Optional ?org=<name> to filter by organisation name.
    """
    try:
        role = request.user.userprofile.get_role()
    except Exception:
        role = 'admin' if request.user.is_superuser else 'customer'
    if role != 'admin' and not request.user.is_superuser:
        messages.error(request, 'Admin access required.')
        return redirect('pulseway:dashboard')

    from .models import PulsewayDevice
    from .services import PulsewayAPI

    filter_org = request.GET.get('org', '').strip()
    rows = []
    api_error = None
    summary = {'total': 0, 'api_online': 0, 'api_offline': 0,
               'db_online': 0, 'db_offline': 0, 'mismatches': 0, 'missing_in_db': 0}

    try:
        api = PulsewayAPI()
        all_api_devices = api.get_all_devices()

        # Build a quick DB lookup by device_id
        db_map = {d.device_id: d for d in PulsewayDevice.objects.all()}

        # Collect all org names for the filter dropdown
        org_names = sorted({(d.get('OrganizationName') or '').strip()
                            for d in all_api_devices if d.get('OrganizationName')})

        for dev in all_api_devices:
            org_name = (dev.get('OrganizationName') or '').strip()
            if filter_org and filter_org.lower() not in org_name.lower():
                continue

            device_id   = dev.get('Identifier', '')
            device_name = dev.get('Name', '')
            uptime      = dev.get('Uptime', '')

            # Determine API online status robustly
            if 'IsOnline' in dev and dev['IsOnline'] is not None:
                raw_online = dev['IsOnline']
                # Handle string "True"/"False" in case API sends strings
                if isinstance(raw_online, str):
                    api_online = raw_online.lower() in ('true', '1', 'yes', 'online')
                else:
                    api_online = bool(raw_online)
                online_source = f"IsOnline={dev['IsOnline']!r}"
            elif uptime:
                api_online = 'offline' not in uptime.lower()
                online_source = f"Uptime={uptime!r}"
            else:
                api_online = False
                online_source = "no IsOnline, no Uptime → offline"

            db_device = db_map.get(device_id)
            db_status = db_device.status if db_device else None
            db_online  = (db_status == 'online') if db_device else None

            mismatch = db_device and (api_online != db_online)
            missing  = db_device is None

            summary['total'] += 1
            if api_online:
                summary['api_online'] += 1
            else:
                summary['api_offline'] += 1
            if db_device:
                if db_online:
                    summary['db_online'] += 1
                else:
                    summary['db_offline'] += 1
            if mismatch:
                summary['mismatches'] += 1
            if missing:
                summary['missing_in_db'] += 1

            rows.append({
                'device_id':     device_id,
                'device_name':   device_name,
                'org_name':      org_name,
                'api_online':    api_online,
                'online_source': online_source,
                'db_status':     db_status or '— not in DB —',
                'mismatch':      mismatch,
                'missing':       missing,
                'raw_fields': {
                    k: v for k, v in dev.items()
                    if k in ('IsOnline', 'Uptime', 'Status', 'Online',
                             'IPAddress', 'OperatingSystem', 'PendingPatches', 'LastSeen')
                },
            })

        # Sort: mismatches first, then missing, then alphabetical
        rows.sort(key=lambda r: (0 if r['mismatch'] else (1 if r['missing'] else 2),
                                  r['org_name'].lower(), r['device_name'].lower()))

    except Exception as e:
        api_error = str(e)
        org_names = []

    return render(request, 'pulseway/api_vs_db_compare.html', {
        'user_role':  role,
        'rows':       rows,
        'summary':    summary,
        'filter_org': filter_org,
        'org_names':  org_names,
        'api_error':  api_error,
    })


@login_required
def sync_control(request):
    """Admin sync control panel — view sync status and trigger manual syncs."""
    try:
        role = request.user.userprofile.get_role()
    except Exception:
        role = 'admin' if request.user.is_superuser else 'customer'
    if role != 'admin' and not request.user.is_superuser:
        messages.error(request, 'Admin access required.')
        return redirect('pulseway:dashboard')

    from .models import PulsewayDevice, PulsewaySync
    syncs = {s.sync_type: s for s in PulsewaySync.objects.all()}
    pulseway_device_count = PulsewayDevice.objects.count()
    pulseway_online = PulsewayDevice.objects.filter(status='online').count()
    # MDM devices are fetched live from API (no DB sync), so count is not available here
    mdm_device_count = 'live (no DB)'

    # Scheduler status — check via DB token (new self-terminating scheduler)
    from pulseway.scheduler import SYNC_INTERVAL_MINUTES as pw_interval, STATUS_SYNC_MINUTES as pw_status_interval, _token_is_current, _token
    pw_running = bool(_token) and _token_is_current(_token) if _token else False

    # Estimate how long a status sync will take (2s per device)
    status_sync_estimate = max(1, round(pulseway_device_count * 2 / 60))

    context = {
        'user_role': role,
        'syncs': syncs,
        'pulseway_device_count': pulseway_device_count,
        'pulseway_online': pulseway_online,
        'mdm_device_count': mdm_device_count,
        'pw_scheduler_running': pw_running,
        'mdm_scheduler_running': False,
        'pw_interval': pw_interval,
        'pw_status_interval': pw_status_interval,
        'mdm_interval': 0,
        'status_sync_estimate': status_sync_estimate,
    }
    return render(request, 'pulseway/sync_control.html', context)


@login_required
def software_report(request):
    """
    Pulseway software/apps inventory report.
    Two modes:
      - device view  : ?mode=device&device_id=<uuid>   — all software on one device
      - org view     : ?mode=org&org=<name>             — aggregated across an org
    The org report fetches software per device on demand (with rate-limit delay),
    so it may take a few seconds for large orgs.
    """
    try:
        role = _require_tech_or_admin(request)
    except PermissionError:
        messages.error(request, "Access denied.")
        return redirect('pulseway:dashboard')

    from .services import PulsewayAPI
    from .models import PulsewayDevice, PulsewayOrganization

    api  = PulsewayAPI()
    mode = request.GET.get('mode', '')           # 'device' or 'org'
    org  = request.GET.get('org', '').strip()
    device_id = request.GET.get('device_id', '').strip()

    # Dropdowns
    orgs    = PulsewayOrganization.objects.order_by('name').values_list('name', flat=True)
    devices = PulsewayDevice.objects.order_by('organization_name', 'device_name')

    context = {
        'user_role':  role,
        'orgs':       orgs,
        'devices':    devices,
        'mode':       mode,
        'org':        org,
        'device_id':  device_id,
        'report':     None,
        'device_software': None,
        'selected_device': None,
        'error':      None,
    }

    if mode == 'device' and device_id:
        try:
            dev_obj = PulsewayDevice.objects.filter(device_id=device_id).first()
            software = api.get_device_software(device_id)
            context['device_software'] = sorted(software, key=lambda s: (s.get('Name') or '').lower())
            context['selected_device'] = dev_obj
        except Exception as e:
            context['error'] = f"Could not fetch software for device: {e}"

    elif mode == 'org':
        try:
            report = api.get_org_software_report(org_name=org or None, max_devices=50)
            context['report'] = report
        except Exception as e:
            context['error'] = f"Could not fetch org software report: {e}"

    return render(request, 'pulseway/software_report.html', context)


def _require_tech_or_admin(request):
    """Return user_role or raise PermissionError if customer."""
    try:
        role = request.user.userprofile.get_role()
    except Exception:
        role = 'admin'
    if role == 'customer':
        raise PermissionError("Customers cannot perform this action.")
    return role


def _parse_is_online(dev: dict) -> bool:
    """Robustly determine if a Pulseway API device dict represents an online device."""
    raw = dev.get('IsOnline')
    if raw is not None:
        if isinstance(raw, str):
            return raw.lower() in ('true', '1', 'yes', 'online')
        return bool(raw)
    uptime = dev.get('Uptime', '')
    return bool(uptime) and 'offline' not in uptime.lower()


def _fetch_live_company_devices(company_name: str) -> list:
    """
    Return devices for company from the local DB (accurate status, fast).
    The DB is kept up to date by the scheduler which calls sync_devices() every
    30 minutes using get_all_devices_with_details() — which fetches per-device
    detail so online/offline status is always correctly written to DB.
    """
    from .local_service import PulsewayLocalService
    try:
        svc = PulsewayLocalService()
        qs = svc.get_company_devices(company_name)
        result = []
        for dev in qs:
            last_seen_str = dev.last_seen.strftime('%Y-%m-%d %H:%M') if dev.last_seen else ''
            result.append({
                'device_id':        dev.device_id,
                'device_name':      dev.device_name or 'Unknown',
                'organization_name': dev.organization_name or '',
                'site_name':        dev.site_name or '',
                'status':           dev.status or 'offline',
                'ip_address':       dev.ip_address or '',
                'operating_system': dev.operating_system or '',
                'uptime':           dev.uptime or '',
                'cpu_usage':        dev.cpu_usage or '',
                'memory_usage':     dev.memory_usage or '',
                'disk_usage':       dev.disk_usage or '',
                'pending_patches':  dev.pending_patches or 0,
                'last_seen':        last_seen_str,
            })
        return sorted(result, key=lambda d: d['device_name'].lower())
    except Exception:
        return []


@login_required
def device_detail(request, device_id):
    """Detailed view of a single Pulseway device — technician/admin only."""
    try:
        role = _require_tech_or_admin(request)
    except PermissionError:
        messages.error(request, "Access denied.")
        return redirect('pulseway:devices')

    from .models import PulsewayDevice

    # Try local DB first for fast load
    try:
        local_device = PulsewayDevice.objects.get(device_id=device_id)
    except PulsewayDevice.DoesNotExist:
        local_device = None

    # Live API data
    api = PulsewayAPI()
    live_data = {}
    patches = []
    notifications = []

    try:
        resp = api.get_device_details(device_id)
        if isinstance(resp, dict):
            live_data = resp.get('Data', resp)
    except Exception as e:
        messages.warning(request, f"Could not load live device data: {e}")

    try:
        patches = api.get_device_patches(device_id)
    except Exception:
        patches = []

    try:
        notifications = api.get_device_notifications(device_id)
    except Exception:
        notifications = []

    # Merge local + live
    device_info = {}
    if local_device:
        device_info = {
            'Identifier': local_device.device_id,
            'Name': local_device.device_name,
            'OrganizationName': local_device.organization_name,
            'SiteName': local_device.site_name,
            'Status': local_device.status,
            'IPAddress': local_device.ip_address,
            'MACAddress': local_device.mac_address,
            'OperatingSystem': local_device.operating_system,
            'Uptime': local_device.uptime,
            'CPUUsage': local_device.cpu_usage,
            'MemoryUsage': local_device.memory_usage,
            'DiskUsage': local_device.disk_usage,
            'PendingPatches': local_device.pending_patches,
            'LastSeen': local_device.last_seen,
        }
    if live_data:
        # Live data takes precedence — map API field names to display keys
        if live_data.get('Name'):
            device_info['Name'] = live_data['Name']
        if live_data.get('OrganizationName'):
            device_info['OrganizationName'] = live_data['OrganizationName']
        if live_data.get('Uptime'):
            device_info['Uptime'] = live_data['Uptime']
        # OS: API returns as 'Description'
        if live_data.get('Description'):
            device_info['OperatingSystem'] = live_data['Description']
        # IP: API returns as 'ExternalIpAddress'
        if live_data.get('ExternalIpAddress'):
            device_info['IPAddress'] = live_data['ExternalIpAddress']
        # Device type for icon
        if live_data.get('Type'):
            device_info['Type'] = live_data['Type']
        # Notification counts from detail response
        device_info['CriticalNotifications'] = live_data.get('CriticalNotifications', 0)
        device_info['ElevatedNotifications'] = live_data.get('ElevatedNotifications', 0)
        # Status from Uptime
        uptime = live_data.get('Uptime', '')
        if uptime:
            device_info['Status'] = 'offline' if uptime.lower() == 'offline' else 'online'

    if not device_info:
        messages.error(request, "Device not found.")
        return redirect('pulseway:devices')

    pending_patches = [p for p in patches if p.get('Status', '').lower() in ('pending', 'available', '')]
    installed_patches = [p for p in patches if p.get('Status', '').lower() == 'installed']

    context = {
        'device': device_info,
        'device_id': device_id,
        'patches': patches,
        'pending_patches': pending_patches,
        'installed_patches': installed_patches,
        'notifications': notifications,
        'user_role': role,
    }
    return render(request, 'pulseway/device_detail.html', context)


@login_required
@require_http_methods(["POST"])
def device_install_patches(request, device_id):
    """Install pending patches on a device — technician/admin only."""
    try:
        _require_tech_or_admin(request)
    except PermissionError:
        return JsonResponse({'success': False, 'message': 'Access denied.'}, status=403)

    patch_ids = request.POST.getlist('patch_ids')
    reboot = request.POST.get('reboot_after', 'false').lower() == 'true'

    try:
        api = PulsewayAPI()
        result = api.install_patches(device_id, {'PatchIds': patch_ids, 'RebootRequired': reboot})
        PulsewayAction.objects.create(
            user=request.user,
            action_type='patch',
            target_id=device_id,
            target_name=f"Device {device_id}",
            description=f"Installed {len(patch_ids)} patches",
            status='completed',
            result=result
        )
        return JsonResponse({'success': True, 'message': f'{len(patch_ids)} patch(es) queued for installation.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_http_methods(["POST"])
def device_reboot(request, device_id):
    """Reboot a device from device detail page — technician/admin only."""
    try:
        _require_tech_or_admin(request)
    except PermissionError:
        return JsonResponse({'success': False, 'message': 'Access denied.'}, status=403)

    try:
        api = PulsewayAPI()
        result = api.reboot_device(device_id)
        PulsewayAction.objects.create(
            user=request.user,
            action_type='reboot',
            target_id=device_id,
            target_name=f"Device {device_id}",
            description="Rebooted device from device detail page",
            status='completed',
            result=result
        )
        return JsonResponse({'success': True, 'message': 'Reboot command sent successfully.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def notifications(request):
    """List all Pulseway notifications/alerts — technician/admin only."""
    try:
        role = _require_tech_or_admin(request)
    except PermissionError:
        messages.error(request, "Access denied.")
        return redirect('pulseway:dashboard')

    api = PulsewayAPI()
    try:
        all_notifications = api.get_all_notifications(top=200)
    except Exception as e:
        messages.warning(request, f"Could not load notifications: {e}")
        all_notifications = []

    # Pagination
    search = request.GET.get('search', '').strip()
    severity_filter = request.GET.get('severity', '')

    filtered = all_notifications
    if search:
        filtered = [n for n in filtered if search.lower() in str(n).lower()]
    if severity_filter:
        filtered = [n for n in filtered if n.get('Priority', '').lower() == severity_filter.lower()]

    paginator = Paginator(filtered, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'notifications': page_obj,
        'total': len(filtered),
        'search': search,
        'severity_filter': severity_filter,
        'user_role': role,
    }
    return render(request, 'pulseway/notifications.html', context)


@login_required
@require_http_methods(["POST"])
def acknowledge_notification(request, notification_id):
    """Acknowledge a Pulseway alert — technician/admin only."""
    try:
        _require_tech_or_admin(request)
    except PermissionError:
        return JsonResponse({'success': False, 'message': 'Access denied.'}, status=403)

    try:
        api = PulsewayAPI()
        api.acknowledge_notification(notification_id)
        return JsonResponse({'success': True, 'message': 'Notification acknowledged.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


# ---------------------------------------------------------------------------
# Report downloads  (admin / technician only)
# ---------------------------------------------------------------------------

def _assert_tech_or_admin(request):
    """Raise PermissionError if current user is not admin/technician."""
    try:
        profile = request.user.userprofile
        role = profile.get_role()
    except Exception:
        role = 'admin'
    if role not in ('admin', 'technician'):
        raise PermissionError("Access denied")


def _csv_response(filename, headers, rows):
    """Return an HttpResponse with CSV content."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    writer.writerows(rows)
    return response


@login_required
def report_device_inventory(request):
    """
    Download all 468 devices as a CSV.
    Columns: Device Name, Type, OS, IP Address, Organization, Site, Group,
             Agent Installed, MDM Enrolled, Status, Critical Alerts, Elevated Alerts

    NOTE: Fetching full details for every device hits the API once per device.
    For 468 devices this can take ~30-60 s.  We use the DB cache (PulsewayDevice)
    for the bulk of data and only fall back to the live API if needed.
    """
    try:
        _assert_tech_or_admin(request)
    except PermissionError:
        messages.error(request, 'Access denied.')
        return redirect('pulseway:devices')

    try:
        from .models import PulsewayDevice
        from .local_service import PulsewayLocalService

        # Filter by org if requested
        org_filter = request.GET.get('org', '').strip()

        qs = PulsewayDevice.objects.all().order_by('organization_name', 'site_name', 'device_name')
        if org_filter:
            qs = qs.filter(organization_name__icontains=org_filter)

        headers = [
            'Device Name', 'Operating System', 'IP Address',
            'Organization', 'Site',
            'Status', 'Uptime', 'Pending Patches',
            'CPU %', 'Memory %', 'Disk %',
        ]

        rows = []
        for dev in qs:
            rows.append([
                dev.device_name,
                dev.operating_system or '',
                dev.ip_address or '',
                dev.organization_name or '',
                dev.site_name or '',
                dev.status or '',
                dev.uptime or '',
                dev.pending_patches,
                f'{dev.cpu_usage:.1f}' if dev.cpu_usage is not None else '',
                f'{dev.memory_usage:.1f}' if dev.memory_usage is not None else '',
                f'{dev.disk_usage:.1f}' if dev.disk_usage is not None else '',
            ])

        ts = datetime.now().strftime('%Y%m%d_%H%M')
        org_suffix = f'_{org_filter.replace(" ", "_")}' if org_filter else ''
        filename = f'pulseway_device_inventory{org_suffix}_{ts}.csv'
        return _csv_response(filename, headers, rows)

    except Exception as e:
        messages.error(request, f'Report generation failed: {e}')
        return redirect('pulseway:devices')


@login_required
def report_alert_log(request):
    """
    Download the Pulseway notification/alert log as CSV.
    Fetches up to 2000 most-recent alerts from the API.
    Columns: DateTime, Priority, Organization (parsed), Message

    Optional GET params:
      ?priority=critical|elevated|normal   (filter)
      ?org=<name>                          (org name substring filter)
      ?limit=<n>                           (max alerts to fetch, default 500)
    """
    try:
        _assert_tech_or_admin(request)
    except PermissionError:
        messages.error(request, 'Access denied.')
        return redirect('pulseway:notifications')

    try:
        import requests as req_lib

        api = PulsewayAPI()
        base = api.api._store['base_url']
        auth = api.api._store['session'].auth

        priority_filter = request.GET.get('priority', '').lower().strip()
        org_filter = request.GET.get('org', '').strip().lower()
        limit = min(int(request.GET.get('limit', 500)), 2000)

        # Fetch paginated notifications
        all_notifs = []
        skip = 0
        top = 200
        while len(all_notifs) < limit:
            r = req_lib.get(
                f'{base}/notifications', auth=auth,
                params={'$top': top, '$skip': skip}, timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            batch = data.get('Data', [])
            if not batch:
                break
            all_notifs.extend(batch)
            if len(batch) < top:
                break
            skip += top

        all_notifs = all_notifs[:limit]

        # Org name extractor: messages often say "in group 'OrgName > Site > Group'"
        # or "in organization 'OrgName'"
        _in_group_re = re.compile(r"in group '([^>]+?)(?:\s*>|')", re.IGNORECASE)
        _in_org_re = re.compile(r"organization '([^']+)'", re.IGNORECASE)

        def _parse_org(msg):
            m = _in_group_re.search(msg)
            if m:
                return m.group(1).strip()
            m = _in_org_re.search(msg)
            if m:
                return m.group(1).strip()
            return ''

        headers = ['DateTime (UTC)', 'Priority', 'Organization (parsed)', 'Message']
        rows = []
        for n in all_notifs:
            priority = n.get('Priority', '')
            if priority_filter and priority.lower() != priority_filter:
                continue
            org = _parse_org(n.get('Message', ''))
            if org_filter and org_filter not in org.lower():
                continue
            rows.append([
                n.get('DateTime', ''),
                priority.capitalize(),
                org,
                n.get('Message', ''),
            ])

        ts = datetime.now().strftime('%Y%m%d_%H%M')
        filename = f'pulseway_alerts_{ts}.csv'
        return _csv_response(filename, headers, rows)

    except Exception as e:
        messages.error(request, f'Report generation failed: {e}')
        return redirect('pulseway:notifications')


@login_required
def report_patch_alerts(request):
    """
    Download a Patch Pending report derived from alert messages.

    The Pulseway REST API has NO dedicated patch endpoint — patch status is
    exposed only as alert messages like:
      '1 important update is available on computer DESKTOP-X in group CG Logistics > ...'
      '3 important updates are available on ...'

    We filter the full notification log for these messages and produce a
    device-level patch summary.

    Columns: Organization, Device Name, Pending Updates Count, First Alert Date,
             Latest Alert Date, Alert Message
    """
    try:
        _assert_tech_or_admin(request)
    except PermissionError:
        messages.error(request, 'Access denied.')
        return redirect('pulseway:devices')

    try:
        import requests as req_lib

        api = PulsewayAPI()
        base = api.api._store['base_url']
        auth = api.api._store['session'].auth

        org_filter = request.GET.get('org', '').strip().lower()
        limit = min(int(request.GET.get('limit', 2000)), 5000)

        # Fetch notifications
        all_notifs = []
        skip = 0
        top = 200
        while len(all_notifs) < limit:
            r = req_lib.get(
                f'{base}/notifications', auth=auth,
                params={'$top': top, '$skip': skip}, timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            batch = data.get('Data', [])
            if not batch:
                break
            all_notifs.extend(batch)
            if len(batch) < top:
                break
            skip += top

        all_notifs = all_notifs[:limit]

        # Patterns matching patch-related notifications
        # "N important update(s) is/are available on computer 'DEVICE' in group 'ORG > ...'"
        _patch_re = re.compile(
            r'(\d+)\s+important\s+update[s]?\s+(?:is|are)\s+available\s+on\s+'
            r"(?:computer\s+)?['\"]?([^'\"]+?)['\"]?\s+in\s+group\s+['\"]([^'\"]+)['\"]",
            re.IGNORECASE
        )
        _patch_simple = re.compile(
            r'update[s]?\s+(?:is|are)\s+available|patch|windows\s+update',
            re.IGNORECASE
        )

        # Aggregate per device: keep latest alert + count
        device_map = {}  # device_name -> dict

        for n in all_notifs:
            msg = n.get('Message', '')
            dt = n.get('DateTime', '')

            m = _patch_re.search(msg)
            if m:
                count_str, device, group_path = m.group(1), m.group(2).strip(), m.group(3).strip()
                # Parse org from group path (first segment)
                org = group_path.split('>')[0].strip()
                if org_filter and org_filter not in org.lower():
                    continue
                key = device.lower()
                if key not in device_map:
                    device_map[key] = {
                        'org': org, 'device': device,
                        'count': int(count_str),
                        'first_dt': dt, 'latest_dt': dt,
                        'message': msg,
                    }
                else:
                    existing = device_map[key]
                    # Keep highest count and latest date
                    if int(count_str) > existing['count']:
                        existing['count'] = int(count_str)
                        existing['message'] = msg
                    if dt > existing['latest_dt']:
                        existing['latest_dt'] = dt
                    if dt < existing['first_dt']:
                        existing['first_dt'] = dt
            elif _patch_simple.search(msg):
                # Generic patch mention — parse org from group reference
                _in_group_re = re.compile(r"in group '([^']+)'", re.IGNORECASE)
                gm = _in_group_re.search(msg)
                org = gm.group(1).split('>')[0].strip() if gm else ''
                if org_filter and org_filter not in org.lower():
                    continue
                # Use message as device key (no structured device name)
                key = msg[:60].lower()
                if key not in device_map:
                    device_map[key] = {
                        'org': org, 'device': '(see message)',
                        'count': 0, 'first_dt': dt, 'latest_dt': dt,
                        'message': msg,
                    }

        # Sort by org then device
        sorted_entries = sorted(device_map.values(), key=lambda x: (x['org'], x['device']))

        headers = [
            'Organization', 'Device Name', 'Pending Updates',
            'First Alert (UTC)', 'Latest Alert (UTC)', 'Alert Message',
        ]
        rows = [
            [
                e['org'], e['device'], e['count'] or '',
                e['first_dt'], e['latest_dt'], e['message'],
            ]
            for e in sorted_entries
        ]

        ts = datetime.now().strftime('%Y%m%d_%H%M')
        filename = f'pulseway_patch_alerts_{ts}.csv'
        return _csv_response(filename, headers, rows)

    except Exception as e:
        messages.error(request, f'Report generation failed: {e}')
        return redirect('pulseway:devices')


# ---------------------------------------------------------------------------
# Device edit  (admin / technician only)
# ---------------------------------------------------------------------------

@login_required
def edit_device(request, device_id):
    """Edit device name/description/group assignment."""
    try:
        role = _require_tech_or_admin(request)
    except PermissionError:
        messages.error(request, "Access denied.")
        return redirect('pulseway:devices')

    from .models import PulsewayDevice as _PulsewayDevice

    try:
        local = _PulsewayDevice.objects.get(device_id=device_id)
    except _PulsewayDevice.DoesNotExist:
        local = None

    if request.method == 'POST':
        form = DeviceEditForm(request.POST)
        if form.is_valid():
            try:
                api = PulsewayAPI()
                update_data = {'Name': form.cleaned_data['name']}
                if form.cleaned_data.get('description'):
                    update_data['Description'] = form.cleaned_data['description']
                if form.cleaned_data.get('group_id'):
                    update_data['GroupId'] = form.cleaned_data['group_id']
                api.update_device(device_id, update_data)

                if local:
                    local.device_name = form.cleaned_data['name']
                    local.save(update_fields=['device_name'])

                PulsewayAction.objects.create(
                    user=request.user,
                    action_type='device_update',
                    target_id=device_id,
                    target_name=form.cleaned_data['name'],
                    description=f"Updated device {device_id}",
                    status='completed',
                    result=update_data,
                )
                messages.success(request, f"Device '{form.cleaned_data['name']}' updated successfully.")
                return redirect('pulseway:device_detail', device_id=device_id)
            except Exception as e:
                messages.error(request, f"Error updating device: {e}")
    else:
        initial = {}
        if local:
            initial['name'] = local.device_name
        form = DeviceEditForm(initial=initial)

    return render(request, 'pulseway/edit_device.html', {
        'form': form,
        'device_id': device_id,
        'device_name': local.device_name if local else device_id,
        'user_role': role,
    })


# ---------------------------------------------------------------------------
# Policies  (admin / technician only)
# ---------------------------------------------------------------------------

@login_required
def policies(request):
    """List all Pulseway monitoring policies."""
    try:
        role = _require_tech_or_admin(request)
    except PermissionError:
        messages.error(request, "Access denied.")
        return redirect('pulseway:dashboard')

    api = PulsewayAPI()
    try:
        all_policies = api.get_all_policies()
    except Exception as e:
        messages.warning(request, f"Could not load policies: {e}")
        all_policies = []

    search = request.GET.get('search', '').strip()
    if search:
        all_policies = [p for p in all_policies if search.lower() in str(p.get('Name', '')).lower()]

    paginator = Paginator(all_policies, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'pulseway/policies.html', {
        'policies': page_obj,
        'total': len(all_policies),
        'search': search,
        'user_role': role,
    })


@login_required
def create_policy(request):
    """Create a new Pulseway monitoring policy."""
    try:
        role = _require_tech_or_admin(request)
    except PermissionError:
        messages.error(request, "Access denied.")
        return redirect('pulseway:policies')

    if request.method == 'POST':
        form = PolicyForm(request.POST)
        if form.is_valid():
            try:
                api = PulsewayAPI()
                policy_data = {
                    'Name': form.cleaned_data['name'],
                    'Description': form.cleaned_data.get('description', ''),
                    'Scope': form.cleaned_data['scope'],
                }
                if form.cleaned_data.get('scope_id'):
                    policy_data['ScopeId'] = form.cleaned_data['scope_id']
                rules = []
                if form.cleaned_data.get('cpu_threshold'):
                    rules.append({'Type': 'CPU', 'Threshold': form.cleaned_data['cpu_threshold']})
                if form.cleaned_data.get('memory_threshold'):
                    rules.append({'Type': 'Memory', 'Threshold': form.cleaned_data['memory_threshold']})
                if form.cleaned_data.get('disk_threshold'):
                    rules.append({'Type': 'Disk', 'Threshold': form.cleaned_data['disk_threshold']})
                if rules:
                    policy_data['Rules'] = rules

                result = api.create_policy(policy_data)
                PulsewayAction.objects.create(
                    user=request.user,
                    action_type='policy_create',
                    target_id=str(result.get('Id', 'unknown')) if isinstance(result, dict) else 'unknown',
                    target_name=form.cleaned_data['name'],
                    description=f"Created policy: {form.cleaned_data['name']}",
                    status='completed',
                    result=result,
                )
                messages.success(request, f"Policy '{form.cleaned_data['name']}' created successfully.")
                return redirect('pulseway:policies')
            except Exception as e:
                messages.error(request, f"Error creating policy: {e}")
    else:
        form = PolicyForm()

    return render(request, 'pulseway/create_policy.html', {'form': form, 'user_role': role})


@login_required
def edit_policy(request, policy_id):
    """Edit an existing Pulseway monitoring policy."""
    try:
        role = _require_tech_or_admin(request)
    except PermissionError:
        messages.error(request, "Access denied.")
        return redirect('pulseway:policies')

    api = PulsewayAPI()
    try:
        policy_data = api.get_policy(policy_id)
    except Exception as e:
        messages.error(request, f"Could not load policy: {e}")
        return redirect('pulseway:policies')

    if not policy_data:
        messages.error(request, "Policy not found.")
        return redirect('pulseway:policies')

    if request.method == 'POST':
        form = PolicyForm(request.POST)
        if form.is_valid():
            try:
                update_data = {
                    'Name': form.cleaned_data['name'],
                    'Description': form.cleaned_data.get('description', ''),
                    'Scope': form.cleaned_data['scope'],
                }
                if form.cleaned_data.get('scope_id'):
                    update_data['ScopeId'] = form.cleaned_data['scope_id']
                rules = []
                if form.cleaned_data.get('cpu_threshold'):
                    rules.append({'Type': 'CPU', 'Threshold': form.cleaned_data['cpu_threshold']})
                if form.cleaned_data.get('memory_threshold'):
                    rules.append({'Type': 'Memory', 'Threshold': form.cleaned_data['memory_threshold']})
                if form.cleaned_data.get('disk_threshold'):
                    rules.append({'Type': 'Disk', 'Threshold': form.cleaned_data['disk_threshold']})
                if rules:
                    update_data['Rules'] = rules

                result = api.update_policy(policy_id, update_data)
                PulsewayAction.objects.create(
                    user=request.user,
                    action_type='policy_update',
                    target_id=str(policy_id),
                    target_name=form.cleaned_data['name'],
                    description=f"Updated policy: {form.cleaned_data['name']}",
                    status='completed',
                    result=result,
                )
                messages.success(request, f"Policy '{form.cleaned_data['name']}' updated successfully.")
                return redirect('pulseway:policies')
            except Exception as e:
                messages.error(request, f"Error updating policy: {e}")
    else:
        rules = policy_data.get('Rules', [])
        cpu_rule = next((r for r in rules if r.get('Type') == 'CPU'), {})
        mem_rule = next((r for r in rules if r.get('Type') == 'Memory'), {})
        disk_rule = next((r for r in rules if r.get('Type') == 'Disk'), {})
        form = PolicyForm(initial={
            'name': policy_data.get('Name', ''),
            'description': policy_data.get('Description', ''),
            'scope': policy_data.get('Scope', 'Organization'),
            'scope_id': policy_data.get('ScopeId', ''),
            'cpu_threshold': cpu_rule.get('Threshold'),
            'memory_threshold': mem_rule.get('Threshold'),
            'disk_threshold': disk_rule.get('Threshold'),
        })

    return render(request, 'pulseway/edit_policy.html', {
        'form': form,
        'policy': policy_data,
        'policy_id': policy_id,
        'user_role': role,
    })


@login_required
@require_http_methods(["POST"])
def delete_policy(request, policy_id):
    """Delete a Pulseway monitoring policy."""
    try:
        _require_tech_or_admin(request)
    except PermissionError:
        return JsonResponse({'success': False, 'message': 'Access denied.'}, status=403)

    try:
        api = PulsewayAPI()
        try:
            pd = api.get_policy(policy_id)
            policy_name = pd.get('Name', f'Policy {policy_id}') if pd else f'Policy {policy_id}'
        except Exception:
            policy_name = f'Policy {policy_id}'

        api.delete_policy(policy_id)
        PulsewayAction.objects.create(
            user=request.user,
            action_type='policy_delete',
            target_id=str(policy_id),
            target_name=policy_name,
            description=f"Deleted policy: {policy_name}",
            status='completed',
            result={},
        )
        return JsonResponse({'success': True, 'message': f'Policy "{policy_name}" deleted.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
