from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .services import PulsewayAPI
from .manageengine_service import ManageEngineAPI
from .company_matcher import CompanyMatcher
from .forms import SiteForm, GroupForm, ScriptForm, PatchForm, AutomationTaskForm
from .models import PulsewayAction
import json


@login_required
def dashboard(request):
    """Pulseway dashboard showing overview"""
    try:
        from django.core.cache import cache
        import time
        
        # Check if we have cached data (cache for 5 minutes)
        cache_key = 'pulseway_dashboard_data'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            context = cached_data
        else:
            api = PulsewayAPI()
            
            # Get real data from APIs
            all_devices = api.get_all_devices()
            all_sites = api.get_all_sites()
            all_groups = api.get_all_groups()
            
            # Get recent items for display
            recent_devices = all_devices[:5] if all_devices else []
            recent_sites = all_sites[:5] if all_sites else []
            recent_actions = PulsewayAction.objects.filter(user=request.user)[:10]
            
            # Balanced approach: Get real status for 100 devices, extrapolate
            sample_size = min(100, len(all_devices))
            sample_online = 0
            sample_offline = 0
            
            for i in range(sample_size):
                device = all_devices[i]
                try:
                    device_details = api.get_device_details(device.get('Identifier'))
                    if device_details and 'Data' in device_details:
                        uptime = device_details['Data'].get('Uptime', 'Offline')
                        if 'Offline' in uptime:
                            sample_offline += 1
                        else:
                            sample_online += 1
                    else:
                        sample_offline += 1
                except Exception as e:
                    sample_offline += 1
                    if '429' in str(e):
                        time.sleep(0.5)  # Brief pause for rate limiting
            
            # Calculate ratio and apply to total
            if sample_size > 0:
                online_ratio = sample_online / sample_size
                online_devices = int(len(all_devices) * online_ratio)
                offline_devices = len(all_devices) - online_devices
            else:
                online_devices = 0
                offline_devices = len(all_devices)
            
            context = {
                'total_devices': len(all_devices),
                'online_devices': online_devices,
                'offline_devices': offline_devices,
                'total_sites': len(all_sites),
                'total_groups': len(all_groups),
                'recent_devices': recent_devices,
                'recent_sites': recent_sites,
                'recent_actions': recent_actions,
            }
            
            # Cache the data for 5 minutes (300 seconds)
            cache.set(cache_key, context, 300)
        
        return render(request, 'pulseway/dashboard.html', context)
    except Exception as e:
        messages.error(request, f"Error loading dashboard: {str(e)}")
        return render(request, 'pulseway/dashboard.html', {
            'total_devices': 0, 'online_devices': 0, 'offline_devices': 0,
            'total_sites': 0, 'total_groups': 0, 'recent_devices': [],
            'recent_sites': [], 'recent_actions': []
        })


@login_required
def devices(request):
    """List all devices with pagination and search"""
    try:
        api = PulsewayAPI()
        # Get basic device list first
        all_devices = api.get_all_devices()
        
        # Get detailed info for each device (limit to prevent API overload)
        for device in all_devices[:20]:  # Limit to first 20 for performance
            try:
                details = api.get_device_details(device.get('Identifier'))
                if details and 'Data' in details:
                    device_data = details['Data']
                    # Update device with real API data
                    device.update(device_data)
            except:
                pass  # Keep basic data if details fail
        
        # Search functionality
        search_query = request.GET.get('search', '').strip()
        if search_query:
            all_devices = [
                device for device in all_devices
                if search_query.lower() in device.get('Name', '').lower() or
                   search_query.lower() in device.get('SiteName', '').lower() or
                   search_query.lower() in device.get('OrganizationName', '').lower() or
                   search_query.lower() in device.get('GroupName', '').lower() or
                   search_query.lower() in device.get('Description', '').lower() or
                   search_query.lower() in device.get('ExternalIpAddress', '').lower()
            ]
        
        # Pagination
        from django.core.paginator import Paginator
        paginator = Paginator(all_devices, 20)
        page_number = request.GET.get('page')
        devices_page = paginator.get_page(page_number)
        
        context = {
            'devices': devices_page,
            'search_query': search_query,
            'total_devices': len(all_devices),
        }
        return render(request, 'pulseway/devices.html', context)
    except Exception as e:
        messages.error(request, f"Error loading devices: {str(e)}")
        return render(request, 'pulseway/devices.html', {'devices': [], 'search_query': '', 'total_devices': 0})


@login_required
def sites(request):
    """List all sites with device counts"""
    try:
        api = PulsewayAPI()
        sites = api.get_all_sites()
        devices = api.get_all_devices()
        
        # Calculate device count for each site
        for site in sites:
            site_devices = [d for d in devices if d.get('SiteId') == site.get('Id')]
            site['DeviceCount'] = len(site_devices)
        
        return render(request, 'pulseway/sites.html', {'sites': sites})
    except Exception as e:
        messages.error(request, f"Error loading sites: {str(e)}")
        return render(request, 'pulseway/sites.html', {'sites': []})


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
        api = PulsewayAPI()
        groups = api.get_all_groups()
        devices = api.get_all_devices()
        
        # Calculate device count for each group
        for group in groups:
            group_devices = [d for d in devices if d.get('GroupId') == group.get('Id')]
            group['DeviceCount'] = len(group_devices)
            # Add site name for display
            group['SiteName'] = group.get('ParentSiteName', 'N/A')
        
        return render(request, 'pulseway/groups.html', {'groups': groups})
    except Exception as e:
        messages.error(request, f"Error loading groups: {str(e)}")
        return render(request, 'pulseway/groups.html', {'groups': []})
        
        # Calculate device count for each group
        for group in groups:
            group_devices = [d for d in devices if d.get('GroupId') == group.get('Id')]
            group['DeviceCount'] = len(group_devices)
            # Add site name for display
            group['SiteName'] = group.get('ParentSiteName', 'N/A')
        
        return render(request, 'pulseway/groups.html', {'groups': groups})
    except Exception as e:
        messages.error(request, f"Error loading groups: {str(e)}")
        return render(request, 'pulseway/groups.html', {'groups': []})


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
    """Run script on device"""
    device_id = request.GET.get('device_id', '')
    
    if request.method == 'POST':
        form = ScriptForm(request.POST)
        if form.is_valid():
            try:
                api = PulsewayAPI()
                script_data = {
                    'Content': form.cleaned_data['script_content'],
                    'Type': form.cleaned_data['script_type'],
                }
                result = api.run_script(form.cleaned_data['device_id'], script_data)
                
                PulsewayAction.objects.create(
                    user=request.user,
                    action_type='script',
                    target_id=form.cleaned_data['device_id'],
                    target_name=f"Device {form.cleaned_data['device_id']}",
                    description=f"Executed {form.cleaned_data['script_type']} script",
                    status='completed',
                    result=result
                )
                
                messages.success(request, "Script executed successfully!")
                return redirect('pulseway:dashboard')
            except Exception as e:
                messages.error(request, f"Error running script: {str(e)}")
    else:
        initial_data = {'device_id': device_id} if device_id else {}
        form = ScriptForm(initial=initial_data)
    
    return render(request, 'pulseway/run_script.html', {'form': form})


@login_required
def install_patches(request):
    """Install patches on device"""
    device_id = request.GET.get('device_id', '')
    
    if request.method == 'POST':
        form = PatchForm(request.POST)
        if form.is_valid():
            try:
                api = PulsewayAPI()
                patch_ids = [pid.strip() for pid in form.cleaned_data['patch_ids'].split('\n') if pid.strip()]
                patch_data = {
                    'PatchIds': patch_ids,
                    'RebootRequired': form.cleaned_data.get('reboot_required', False),
                }
                result = api.install_patches(form.cleaned_data['device_id'], patch_data)
                
                PulsewayAction.objects.create(
                    user=request.user,
                    action_type='patch',
                    target_id=form.cleaned_data['device_id'],
                    target_name=f"Device {form.cleaned_data['device_id']}",
                    description=f"Installed {len(patch_ids)} patches",
                    status='completed',
                    result=result
                )
                
                messages.success(request, f"Patches installed successfully on device!")
                return redirect('pulseway:dashboard')
            except Exception as e:
                messages.error(request, f"Error installing patches: {str(e)}")
    else:
        initial_data = {'device_id': device_id} if device_id else {}
        form = PatchForm(initial=initial_data)
    
    return render(request, 'pulseway/install_patches.html', {'form': form})


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
    """List automation tasks with pagination"""
    try:
        api = PulsewayAPI()
        
        # Get page number
        page = int(request.GET.get('page', 1))
        per_page = 10
        
        # Try to get tasks with pagination
        try:
            tasks = api.get_automation_tasks(top=per_page, skip=(page-1)*per_page)
        except Exception as e:
            print(f"Error getting automation tasks: {e}")
            tasks = []
        
        # Handle both dict and list responses
        if isinstance(tasks, dict) and 'Data' in tasks:
            tasks_list = tasks['Data']
        elif isinstance(tasks, list):
            tasks_list = tasks
        else:
            tasks_list = []
        
        # Try to get total count for pagination
        try:
            all_tasks = api.get_all_automation_tasks()
            total_tasks = len(all_tasks) if all_tasks else 0
        except Exception as e:
            print(f"Error getting total tasks count: {e}")
            total_tasks = len(tasks_list)
        
        # Calculate pagination info
        from django.core.paginator import Paginator
        paginator = Paginator(range(max(total_tasks, 1)), per_page)
        page_obj = paginator.get_page(page)
        
        context = {
            'tasks': tasks_list,
            'page_obj': page_obj if total_tasks > per_page else None,
            'total_tasks': total_tasks
        }
        
        return render(request, 'pulseway/automation_tasks.html', context)
    except Exception as e:
        messages.error(request, f"Error loading automation tasks: {str(e)}")
        return render(request, 'pulseway/automation_tasks.html', {'tasks': [], 'page_obj': None, 'total_tasks': 0})


@login_required
@require_http_methods(["POST"])
def run_automation_task(request, task_id):
    """Run an automation task"""
    try:
        api = PulsewayAPI()
        result = api.run_automation_task(task_id)
        
        # Get task details to show execution status
        try:
            all_tasks = api.get_all_automation_tasks()
            task = next((t for t in all_tasks if str(t.get('Id')) == str(task_id)), None)
            task_name = task.get('Name', f'Task {task_id}') if task else f'Task {task_id}'
            
            # Get target devices count
            target_devices = task.get('TargetDevices', []) if task else []
            device_count = len(target_devices) if target_devices else 0
            
        except:
            task_name = f'Task {task_id}'
            device_count = 0
        
        PulsewayAction.objects.create(
            user=request.user,
            action_type='automation_run',
            target_id=task_id,
            target_name=task_name,
            description=f"Executed automation task on {device_count} devices",
            status='completed',
            result=result
        )
        
        return JsonResponse({
            'success': True, 
            'message': f'Automation task "{task_name}" started on {device_count} devices. Check Actions History for progress.',
            'device_count': device_count,
            'task_name': task_name
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
@require_http_methods(["POST"])
def run_automation_task(request, task_id):
    """Run automation task manually"""
    try:
        api = PulsewayAPI()
        result = api.run_automation_task(task_id)
        
        PulsewayAction.objects.create(
            user=request.user,
            action_type='automation_run',
            target_id=task_id,
            target_name=f"Task {task_id}",
            description=f"Manually executed automation task {task_id}",
            status='completed',
            result=result
        )
        
        return JsonResponse({'success': True, 'message': 'Automation task executed successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def actions_history(request):
    """View action history"""
    actions = PulsewayAction.objects.filter(user=request.user)
    return render(request, 'pulseway/actions_history.html', {'actions': actions})

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
    """Delete a site"""
    try:
        api = PulsewayAPI()
        site = api.api.sites(site_id).get()
        site_data = site.get('Data', site) if isinstance(site, dict) else site
        site_name = site_data.get('Name', f'Site {site_id}')
        
        result = api.delete_site(site_id)
        
        PulsewayAction.objects.create(
            user=request.user,
            action_type='site_delete',
            target_id=site_id,
            target_name=site_name,
            description=f"Deleted site: {site_name}",
            status='completed',
            result=result
        )
        
        return JsonResponse({'success': True, 'message': f'Site "{site_name}" deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


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
        
        return render(request, 'pulseway/company_dashboard.html', context)
        
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
