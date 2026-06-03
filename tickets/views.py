from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import models
from .models import Ticket
from .services import ManageEngineService
from .forms import TicketForm
import json
from datetime import datetime

@login_required
def dashboard(request):
    from .local_service import LocalTicketService
    from rbac.utils import find_company_for_name
    from rbac.models import UserProfile

    # Get all data from local database - super fast!
    local_service = LocalTicketService()

    # Determine role and company scope
    try:
        profile = request.user.userprofile
        user_role = profile.get_role()
        user_company = profile.company
    except Exception:
        user_role = 'technician'
        user_company = None

    # Get filters from request
    company_filter    = request.GET.get('company')
    technician_filter = request.GET.get('technician')

    # Customer: force filter to their own company, resolved via fuzzy match
    if user_role == 'customer' and user_company:
        matched = local_service.find_company_in_cache(user_company.name)
        company_filter    = matched
        technician_filter = None

    # Technician with company restrictions: limit to their allowed companies
    elif user_role == 'technician':
        from rbac.utils import get_technician_companies
        allowed = get_technician_companies(request.user)
        if allowed is not None:
            # Technician is restricted — honour their manual filter only within allowed set
            if company_filter and company_filter in allowed:
                pass   # keep the user's chosen filter
            else:
                # Default: show all allowed companies (multi-company filter applied below)
                company_filter = None   # handled via allowed_companies kwarg
            # Pass the restriction set into the service
            dashboard_data = local_service.get_dashboard_data(
                company_filter, technician_filter, allowed_companies=allowed
            )
            # Skip second call below
            allowed_companies_applied = True
        else:
            allowed_companies_applied = False
    else:
        allowed_companies_applied = False
    
    # Get dashboard data from local database
    if not locals().get('allowed_companies_applied'):
        dashboard_data = local_service.get_dashboard_data(company_filter, technician_filter)
    
    # Format recent tickets for template
    recent_tickets = []
    for ticket in dashboard_data['recent_tickets']:
        formatted_ticket = {
            'id': ticket['ticket_id'],
            'manage_engine_id': ticket['ticket_id'],
            'title': ticket['subject'],
            'status': ticket['status'],
            'priority': ticket['priority'],
            'created_at': ticket.get('created_at'),
            'created_by': ticket.get('requester_name', 'Unknown'),
            'company': ticket.get('company_name', ''),
            'technician': ticket.get('technician_name', ''),
        }
        recent_tickets.append(formatted_ticket)
    
    # Get statistics from local database (FAST) - using actual status values
    status_counts = dashboard_data['status_counts']
    total_tickets = dashboard_data['total_tickets']
    
    # Map to actual local database status values
    open_tickets = status_counts.get('Open', 0)
    pending_tickets = status_counts.get('Pending', 0)
    in_progress_tickets = status_counts.get('In Progress', 0)
    
    # Sum all hold variations from local database
    hold_tickets = (
        status_counts.get('Onhold', 0) +
        status_counts.get('On Hold - For Spare', 0) +
        status_counts.get('On Hold – Business Dependency', 0) +
        status_counts.get('On Hold – User Dependency', 0) +
        status_counts.get('On Hold - Digtinctive Backend', 0) +
        status_counts.get('On Hold - For Commercial Approval', 0) +
        status_counts.get('Under Observation', 0)
    )
    
    # Use exact local database status names
    resolved_tickets = status_counts.get('Resolved', 0)
    closed_tickets = status_counts.get('Closed', 0)
    cancelled_tickets = status_counts.get('Cancelled', 0)
    
    # Calculate percentages
    open_percentage = (open_tickets * 100 / total_tickets) if total_tickets > 0 else 0
    pending_percentage = (pending_tickets * 100 / total_tickets) if total_tickets > 0 else 0
    progress_percentage = (in_progress_tickets * 100 / total_tickets) if total_tickets > 0 else 0
    resolved_percentage = (resolved_tickets * 100 / total_tickets) if total_tickets > 0 else 0
    cancelled_percentage = (cancelled_tickets * 100 / total_tickets) if total_tickets > 0 else 0
    hold_percentage = (hold_tickets * 100 / total_tickets) if total_tickets > 0 else 0
    
    # Get sync status
    sync_info = dashboard_data['last_sync']
    
    # Technician list for filter dropdown (scoped to same company restriction)
    from .models import TicketCache
    tech_qs = TicketCache.objects.exclude(
        technician_name__isnull=True
    ).exclude(technician_name='').values_list('technician_name', flat=True).distinct().order_by('technician_name')
    technician_list = list(tech_qs)

    context = {
        'tickets': recent_tickets,
        'total_tickets': total_tickets,
        'open_tickets': open_tickets,
        'pending_tickets': pending_tickets,
        'in_progress_tickets': in_progress_tickets,
        'resolved_tickets': resolved_tickets,
        'cancelled_tickets': cancelled_tickets,
        'closed_tickets': closed_tickets,
        'hold_tickets': hold_tickets,
        'open_percentage': open_percentage,
        'pending_percentage': pending_percentage,
        'progress_percentage': progress_percentage,
        'resolved_percentage': resolved_percentage,
        'cancelled_percentage': cancelled_percentage,
        'hold_percentage': hold_percentage,
        'sync_info': sync_info,
        'company_filter': company_filter,
        'technician_filter': technician_filter,
        'technician_list': technician_list,
        'user_role': user_role,
    }
    return render(request, 'tickets/dashboard.html', context)

@login_required
def create_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.created_by = request.user
            
            # Get attachment file if provided
            attachment_file = form.cleaned_data.get('attachment')
            
            # Validate file size (10MB limit)
            if attachment_file and attachment_file.size > 10 * 1024 * 1024:
                messages.error(request, 'File size must be less than 10MB.')
                return render(request, 'tickets/create_ticket.html', {'form': form})
            
            # Map Django form priority choices → ManageEngine priority names
            _priority_map = {
                'low': 'Low', 'medium': 'Normal',
                'high': 'High', 'critical': 'Urgent',
            }
            me_priority = _priority_map.get((ticket.priority or '').lower(), 'Normal')

            # Create ticket in ManageEngine
            me_service = ManageEngineService()
            me_response = me_service.create_ticket(
                title=ticket.title,
                description=ticket.description,
                priority=me_priority,
                requester_email=request.user.email,
                attachment_file=attachment_file
            )

            me_ticket = None
            if me_response:
                me_ticket = me_response.get('request') or me_response.get('Request')

            if me_ticket:
                ticket.manage_engine_id = me_ticket.get('id') or me_ticket.get('Id', '')
                requester_info = me_ticket.get('requester', {})
                used_email = requester_info.get('email_id', '') if isinstance(requester_info, dict) else ''

                success_msg = 'Ticket created successfully!'
                if ticket.manage_engine_id:
                    success_msg += f' (ID: {ticket.manage_engine_id})'
                if used_email and used_email != request.user.email:
                    success_msg += f' — submitted as {used_email}'

                if attachment_file:
                    if me_response.get('attachment_uploaded'):
                        success_msg += f' — attachment "{attachment_file.name}" uploaded.'
                    else:
                        success_msg += f' — note: attachment could not be uploaded (not supported by this ManageEngine instance).'

                messages.success(request, success_msg)
            else:
                # Provide a more specific message for common failure modes
                import logging
                logger = logging.getLogger(__name__)
                logger.error(
                    f"Ticket creation failed for user {request.user.email}. "
                    f"ME response: {me_response}"
                )
                messages.error(
                    request,
                    'Could not create the ticket in ManageEngine. '
                    'This is usually caused by a network/connectivity issue or an expired API token. '
                    'Please check the server logs or contact your administrator.'
                )
                return render(request, 'tickets/create_ticket.html', {'form': form})
            
            ticket.save()
            return redirect('dashboard')
    else:
        form = TicketForm()
    
    return render(request, 'tickets/create_ticket.html', {'form': form})

@login_required
def view_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id, created_by=request.user)
    
    # Sync with ManageEngine if we have the ID
    if ticket.manage_engine_id:
        me_service = ManageEngineService()
        me_ticket = me_service.get_ticket(ticket.manage_engine_id)
        if me_ticket and 'request' in me_ticket:
            # Update local ticket with ManageEngine data
            me_data = me_ticket['request']
            if 'status' in me_data and 'name' in me_data['status']:
                ticket.status = me_data['status']['name']
                ticket.save()
    
    return render(request, 'tickets/view_ticket.html', {'ticket': ticket})

@login_required
def technicians(request):
    from .models import ManageEngineUser
    from rbac.models import Company

    qs = ManageEngineUser.objects.filter(is_technician=True, is_active=True).order_by('name')

    # Build a list that matches the template's expected field names
    technicians_list = [
        {
            'id': u.me_id,
            'name': u.name,
            'email_id': u.email or '',
            'phone': u.phone,
            'department': u.department or 'IT Support',
            'company': u.company_name,
            'last_login': None,
        }
        for u in qs
    ]

    companies = list(Company.objects.values('name').order_by('name'))

    # If local DB is empty, trigger a background sync and show a notice
    if not technicians_list:
        from django.core.management import call_command
        try:
            call_command('sync_me_users', verbosity=0)
            qs = ManageEngineUser.objects.filter(is_technician=True, is_active=True).order_by('name')
            technicians_list = [
                {
                    'id': u.me_id,
                    'name': u.name,
                    'email_id': u.email or '',
                    'phone': u.phone,
                    'department': u.department or 'IT Support',
                    'company': u.company_name,
                    'last_login': None,
                }
                for u in qs
            ]
        except Exception:
            pass

    return render(request, 'tickets/technicians.html', {
        'technicians': technicians_list,
        'companies': companies,
    })


@login_required
def all_users(request):
    from .models import ManageEngineUser
    from rbac.models import Company

    page = int(request.GET.get('page', 1))
    search = request.GET.get('search', '').strip()
    per_page = 50

    qs = ManageEngineUser.objects.filter(is_active=True).order_by('name')
    if search:
        qs = qs.filter(name__icontains=search) | ManageEngineUser.objects.filter(
            is_active=True, email__icontains=search
        )
        qs = qs.order_by('name')

    total_users = qs.count()
    start = (page - 1) * per_page
    page_qs = qs[start:start + per_page]

    def _build_user(u):
        return {
            'id': u.me_id,
            'name': u.name,
            'email_id': u.email or '',
            'phone': u.phone,
            'department': u.department or 'N/A',
            'company': u.company_name,
            'last_login': u.last_synced,  # best available proxy for "last seen in system"
        }

    users_list = [_build_user(u) for u in page_qs]

    # If local DB is empty, trigger a one-time sync inline
    if total_users == 0:
        from django.core.management import call_command
        try:
            call_command('sync_me_users', verbosity=0)
            qs = ManageEngineUser.objects.filter(is_active=True).order_by('name')
            total_users = qs.count()
            page_qs = qs[start:start + per_page]
            users_list = [_build_user(u) for u in page_qs]
        except Exception:
            pass

    has_next = (start + per_page) < total_users
    has_prev = page > 1
    total_pages = max(1, (total_users + per_page - 1) // per_page)
    companies = list(Company.objects.values('name').order_by('name'))

    context = {
        'technicians': users_list,
        'show_all_users': True,
        'current_page': page,
        'total_pages': total_pages,
        'has_next': has_next,
        'has_prev': has_prev,
        'next_page': page + 1 if has_next else None,
        'prev_page': page - 1 if has_prev else None,
        'total_users': total_users,
        'current_page_count': len(users_list),
        'current_page_start': start + 1 if users_list else 0,
        'current_page_end': start + len(users_list),
        'search_query': search,
        'companies': companies,
    }
    return render(request, 'tickets/technicians.html', context)

@login_required
def update_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id, created_by=request.user)
    
    if request.method == 'POST':
        form = TicketForm(request.POST, instance=ticket)
        if form.is_valid():
            updated_ticket = form.save()
            
            # Update in ManageEngine
            if ticket.manage_engine_id:
                me_service = ManageEngineService()
                updates = {
                    'subject': updated_ticket.title,
                    'description': updated_ticket.description,
                    'priority': {'name': updated_ticket.priority}
                }
                me_response = me_service.update_ticket(ticket.manage_engine_id, updates)
                if me_response:
                    messages.success(request, 'Ticket updated successfully in both systems!')
                else:
                    messages.warning(request, 'Ticket updated locally but failed to sync with ManageEngine')
            else:
                messages.success(request, 'Ticket updated successfully!')
            
            return redirect('view_ticket', ticket_id=ticket.id)
    else:
        form = TicketForm(instance=ticket)
    
    return render(request, 'tickets/update_ticket.html', {'form': form, 'ticket': ticket})

@login_required
@require_http_methods(["POST"])
def delete_ticket(request, ticket_id):
    """Delete a ticket"""
    try:
        ticket = get_object_or_404(Ticket, id=ticket_id, created_by=request.user)
        ticket_title = ticket.title
        
        # Delete from ManageEngine if it has an external ID
        if ticket.manage_engine_id:
            try:
                service = ManageEngineService()
                service.delete_ticket(ticket.manage_engine_id)
            except Exception as e:
                # Log error but continue with local deletion
                pass
        
        ticket.delete()
        return JsonResponse({'success': True, 'message': f'Ticket "{ticket_title}" deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_http_methods(["POST"])
def add_technician(request):
    """Add a new technician — creates in ManageEngine then caches locally."""
    try:
        name    = request.POST.get('name', '').strip()
        email   = request.POST.get('email', '').strip()
        phone   = request.POST.get('phone', '').strip()
        company = request.POST.get('company', '').strip()

        if not name or not email:
            return JsonResponse({'success': False, 'message': 'Name and email are required'})

        # 1. Create in ManageEngine (raises on failure)
        service   = ManageEngineService()
        user_data = {'name': name, 'email_id': email, 'phone': phone, 'company': company}
        result    = service.create_user(user_data)

        # 2. Store in local cache so the page shows the new user immediately
        from tickets.models import ManageEngineUser
        me_id = str(result.get('user', {}).get('id', '') or result.get('id', ''))
        if me_id:
            ManageEngineUser.objects.update_or_create(
                me_id=me_id,
                defaults={
                    'name': name,
                    'email': email or None,
                    'phone': phone,
                    'company_name': company,
                    'is_technician': True,
                    'is_active': True,
                }
            )

        return JsonResponse({'success': True, 'message': f'User "{name}" added successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_http_methods(["POST"])
def edit_technician(request, user_id):
    """Edit a technician — updates ManageEngine then syncs local DB."""
    try:
        name    = request.POST.get('name', '').strip()
        email   = request.POST.get('email', '').strip()
        phone   = request.POST.get('phone', '').strip()
        company = request.POST.get('company', '').strip()

        if not name or not email:
            return JsonResponse({'success': False, 'message': 'Name and email are required'})

        # 1. Push change to ManageEngine
        service   = ManageEngineService()
        user_data = {'name': name, 'email_id': email, 'phone': phone, 'company': company}
        result    = service.update_user(user_id, user_data)

        # update_user raises on non-200; if we reach here the API call succeeded.
        # 2. Mirror the change into the local ManageEngineUser cache so the page
        #    reflects the new values immediately after reload.
        from tickets.models import ManageEngineUser
        ManageEngineUser.objects.filter(me_id=str(user_id)).update(
            name=name,
            email=email or None,
            phone=phone,
            company_name=company,
        )

        return JsonResponse({'success': True, 'message': f'User "{name}" updated successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_technician(request, user_id):
    """Delete a technician from ManageEngine and local cache."""
    try:
        service = ManageEngineService()
        service.delete_user(user_id)

        # Remove from local cache so the page no longer lists this user
        from tickets.models import ManageEngineUser
        ManageEngineUser.objects.filter(me_id=str(user_id)).delete()

        return JsonResponse({'success': True, 'message': 'User deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def historical_tickets_api(request):
    """API endpoint to get historical ticket data for the last 2 months"""
    try:
        months = int(request.GET.get('months', 2))
        service = ManageEngineService()
        data = service.get_historical_tickets(months=months)
        
        print(f"DEBUG API: Historical data returned: {data.get('total_tickets', 0) if data else 0} tickets")
        
        if data:
            return JsonResponse({
                'success': True,
                'data': data
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Failed to fetch historical data'
            })
    except Exception as e:
        print(f"DEBUG API: Error in historical_tickets_api: {e}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@login_required
def reports_dashboard(request):
    """Reports dashboard — shows report sections for every package the user has access to."""
    from .fast_reports import FastReportService
    from rbac.models import UserPackageAccess

    report_service = FastReportService()

    user_role = 'technician'
    user_company = None
    company_obj = None
    try:
        profile = request.user.userprofile
        user_role = profile.get_role()
        if profile.company:
            user_company = profile.company.name
            company_obj = profile.company
    except Exception:
        pass

    # Admin sees all data — no company label in the header
    is_admin = request.user.is_superuser or user_role == 'admin'
    header_company = user_company if user_role == 'customer' else None

    # Resolve which packages this user has access to
    if request.user.is_superuser or user_role in ('admin', 'technician'):
        pkg_names = {'manageengine', 'pulseway', 'mdm'}
    else:
        pkg_names = set(
            UserPackageAccess.objects.filter(
                user=request.user, is_enabled=True, package__is_active=True
            ).values_list('package__name', flat=True)
        )

    has_manageengine = bool(pkg_names & {'manageengine', 'tickets'})
    has_pulseway     = 'pulseway' in pkg_names
    has_mdm          = bool(pkg_names & {'mdm', 'mobile device management', 'mobile_device_management'})
    has_office365    = bool(pkg_names & {'office365', 'office 365', 'microsoft365'})

    # ── ManageEngine ──────────────────────────────────────────────────────────
    companies, technicians = [], []
    if has_manageengine:
        companies    = report_service.get_available_companies()
        technicians  = report_service.get_available_technicians()

    # ── Pulseway ──────────────────────────────────────────────────────────────
    pulseway_stats, pulseway_devices, pulseway_os_dist, pulseway_companies = None, [], {}, []
    if has_pulseway:
        try:
            from pulseway.models import PulsewayDevice
            from django.db.models import Sum, Q
            from django.db.models import Q as DQ

            if is_admin:
                # Admin / superuser — all companies, no restriction
                qs_pw = PulsewayDevice.objects.all().order_by('organization_name', 'device_name')
                pulseway_companies = list(
                    PulsewayDevice.objects.values_list('organization_name', flat=True)
                    .exclude(organization_name__isnull=True).exclude(organization_name='')
                    .distinct().order_by('organization_name')
                )

            elif user_role == 'technician':
                # Use the existing technician company restriction logic
                from rbac.utils import get_technician_companies
                allowed = get_technician_companies(request.user)
                if allowed is None:
                    # Unrestricted technician — sees all companies
                    qs_pw = PulsewayDevice.objects.all().order_by('organization_name', 'device_name')
                    pulseway_companies = list(
                        PulsewayDevice.objects.values_list('organization_name', flat=True)
                        .exclude(organization_name__isnull=True).exclude(organization_name='')
                        .distinct().order_by('organization_name')
                    )
                else:
                    # Restricted technician — only their allowed companies
                    q = DQ()
                    for co in allowed:
                        q |= DQ(organization_name__icontains=co)
                    qs_pw = PulsewayDevice.objects.filter(q).order_by('organization_name', 'device_name') if allowed else PulsewayDevice.objects.none()
                    pulseway_companies = []  # already scoped, no dropdown needed

            else:
                # Customer — scoped to their company only
                if user_company:
                    qs_pw = PulsewayDevice.objects.filter(
                        organization_name__icontains=user_company
                    ).order_by('device_name')
                    pulseway_companies = []
                else:
                    qs_pw = PulsewayDevice.objects.none()

            total_pw  = qs_pw.count()
            online_pw = qs_pw.filter(is_online=True).count()
            patches_pw = qs_pw.aggregate(p=Sum('pending_patches'))['p'] or 0

            if total_pw:
                pulseway_stats = {
                    'total_devices':    total_pw,
                    'online_devices':   online_pw,
                    'offline_devices':  total_pw - online_pw,
                    'pending_patches':  patches_pw,
                    'up_to_date_patches': qs_pw.filter(pending_patches=0).count(),
                }

            for d in qs_pw:
                pulseway_devices.append({
                    'name':     d.device_name,
                    'company':  d.organization_name or '—',
                    'status':   d.status,
                    'is_online': d.is_online,
                    'ip':       d.ip_address or '—',
                    'os':       d.operating_system or '—',
                    'uptime':   d.uptime or '—',
                    'patches':  d.pending_patches or 0,
                    'last_seen': d.last_seen.strftime('%d %b %Y %H:%M') if d.last_seen else '—',
                })
                if d.operating_system:
                    os_raw = d.operating_system
                    os_key = ('Windows' if 'windows' in os_raw.lower() else
                              'Linux'   if 'linux'   in os_raw.lower() else
                              'macOS'   if 'mac'     in os_raw.lower() else os_raw[:25])
                    pulseway_os_dist[os_key] = pulseway_os_dist.get(os_key, 0) + 1
        except Exception as _e:
            pulseway_stats = None

    # ── Office 365 ────────────────────────────────────────────────────────────
    o365_license_summary, o365_breakdown = [], {}
    if has_office365:
        try:
            from office365.services import Office365API
            api365 = Office365API()
            o365_license_summary = api365.get_license_summary()
            o365_breakdown = api365.get_license_breakdown()
        except Exception:
            o365_license_summary = []

    # ── MDM (live API) ────────────────────────────────────────────────────────
    mdm_stats, mdm_devices, mdm_type_dist, mdm_companies = None, [], {}, []
    if has_mdm:
        try:
            from mdm.models import MdmCustomer
            from mdm.live_service import fetch_live_devices

            if is_admin:
                # Admin — all MDM customers
                mdm_customers = list(MdmCustomer.objects.select_related('company').all())
                mdm_companies = sorted({c.company.name for c in mdm_customers if c.company})

            elif user_role == 'technician':
                from rbac.utils import get_technician_companies
                allowed = get_technician_companies(request.user)
                if allowed is None:
                    # Unrestricted technician
                    mdm_customers = list(MdmCustomer.objects.select_related('company').all())
                    mdm_companies = sorted({c.company.name for c in mdm_customers if c.company})
                else:
                    # Restricted — only their allowed companies
                    mdm_customers = list(
                        MdmCustomer.objects.select_related('company')
                        .filter(company__name__in=allowed)
                    )
                    mdm_companies = []  # already scoped

            elif company_obj:
                # Customer — their company only
                mdm_customers = list(MdmCustomer.objects.filter(company=company_obj))
                mdm_companies = []
            else:
                mdm_customers = []
                mdm_companies = []
            if mdm_customers:
                live = fetch_live_devices(mdm_customers)

                def _type_label(device_type):
                    t = (device_type or '').lower()
                    if t in ('ios',) or 'iphone' in t: return 'iOS / iPhone'
                    if t == 'android':                  return 'Android'
                    if t == 'windows':                  return 'Windows'
                    if 'mac' in t:                      return 'macOS / Mac'
                    if 'laptop' in t:                   return 'Laptop'
                    return t.title() or 'Other'

                total   = len(live)
                active  = sum(1 for d in live if d['status'] == 'active')
                retired = sum(1 for d in live if d['status'] == 'retired')

                for d in live:
                    type_label = _type_label(d['device_type'])
                    mdm_devices.append({
                        'name':       d['device_name'],
                        'company':    d['customer_name'] or '—',
                        'type':       type_label,
                        'platform':   d['device_type'].title() or '—',
                        'model':      d['model'] or '—',
                        'os_version': d['os_version'] or '—',
                        'status':     d['status_display'],
                        'user_email': d['user_email'] or '—',
                        'last_contact': d['last_contact_time'].strftime('%d %b %Y %H:%M')
                                        if d['last_contact_time'] else '—',
                        'battery':    '—',
                        'encrypted':  d['is_encrypted'],
                        'serial':     d['serial_number'] or '—',
                        'storage_gb': d['storage_gb'] or '—',
                    })
                    mdm_type_dist[type_label] = mdm_type_dist.get(type_label, 0) + 1

                mdm_stats = {
                    'total':    total,
                    'active':   active,
                    'inactive': total - active - retired,
                    'retired':  retired,
                }
        except Exception:
            mdm_stats = None

    # Show company filter dropdown only for admin and unrestricted technicians
    from rbac.utils import get_technician_companies
    _tech_allowed = get_technician_companies(request.user) if user_role == 'technician' else None
    show_company_filter = is_admin or (user_role == 'technician' and _tech_allowed is None)

    return render(request, 'tickets/reports_content.html', {
        'companies':             companies,
        'technicians':           technicians,
        'today':                 datetime.now().strftime('%Y-%m-%d'),
        'user_role':             user_role,
        'user_company':          header_company,   # None for admin → no company label
        'is_admin_tech':         show_company_filter,
        'has_manageengine':      has_manageengine,
        'has_pulseway':          has_pulseway,
        'has_mdm':               has_mdm,
        'has_office365':         has_office365,
        'pulseway_stats':        pulseway_stats,
        'pulseway_devices':      pulseway_devices,
        'pulseway_os_dist':      pulseway_os_dist,
        'pulseway_companies':    pulseway_companies,
        'mdm_stats':             mdm_stats,
        'mdm_devices':           mdm_devices,
        'mdm_type_dist':         mdm_type_dist,
        'mdm_companies':         mdm_companies,
        'o365_license_summary':  o365_license_summary,
        'o365_breakdown':        o365_breakdown,
    })

@login_required
def generate_report(request):
    """Generate fast report from database cache"""
    from django.http import JsonResponse
    from .fast_reports import FastReportService
    from datetime import datetime
    
    try:
        print(f"🔍 Report request received: {request.GET}")
        
        report_service = FastReportService()
        
        # Get parameters
        report_type = request.GET.get('report_type', 'daily')
        company = request.GET.get('company', '')
        technician = request.GET.get('technician', '')
        start_date = request.GET.get('start_date', '')
        end_date = request.GET.get('end_date', '')
        
        print(f"📊 Processing {report_type} report with dates: {start_date} to {end_date}")
        
        # Generate report based on type
        if report_type == 'daily':
            if start_date:
                date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                report_data = report_service.get_daily_report(date_obj)
            else:
                report_data = report_service.get_daily_report()
                
        elif report_type == 'weekly':
            if start_date:
                date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                report_data = report_service.get_weekly_report(date_obj)
            else:
                report_data = report_service.get_weekly_report()
                
        elif report_type == 'monthly':
            if start_date:
                date_obj = datetime.strptime(start_date, '%Y-%m-%d')
                report_data = report_service.get_monthly_report(date_obj.year, date_obj.month)
            else:
                report_data = report_service.get_monthly_report()
                
        elif report_type == 'company':
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
            report_data = report_service.get_company_report(company if company else None, start_date_obj, end_date_obj)
            
        elif report_type == 'technician':
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
            report_data = report_service.get_technician_report(technician if technician else None, start_date_obj, end_date_obj)
            
        else:
            report_data = report_service.get_daily_report()
        
        print(f"✅ Report generated: {report_data.get('total_tickets', 0)} tickets found")
        
        # Format response for frontend
        response_data = {
            'report_type': report_data.get('report_type', report_type),
            'generated_at': report_data.get('generated_at', datetime.now()).strftime('%Y-%m-%d %H:%M:%S'),
            'total_tickets': report_data.get('total_tickets', 0),
            'status_breakdown': report_data.get('status_breakdown', {}),
            'priority_breakdown': report_data.get('priority_breakdown', {}),
            'daily_breakdown': report_data.get('daily_breakdown', {}),
            'tickets': report_data.get('tickets', []),
            'filters': {
                'company': company,
                'technician': technician,
                'start_date': start_date,
                'end_date': end_date
            }
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"❌ Error generating report: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def export_report_csv(request):
    """Export report data as CSV — filters must match what generateReport() uses."""
    from django.http import HttpResponse
    from .models import TicketCache
    from datetime import datetime, timedelta
    import csv

    try:
        report_type = request.GET.get('report_type', 'daily')
        period_label = ''   # goes in filename

        if report_type == 'daily':
            start_date = request.GET.get('start_date', datetime.now().strftime('%Y-%m-%d'))
            tickets = TicketCache.objects.filter(created_at__date=start_date)
            period_label = start_date

        elif report_type == 'weekly':
            start_date = request.GET.get('start_date')
            if start_date:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end   = start + timedelta(days=6)
                tickets = TicketCache.objects.filter(created_at__date__range=[start, end])
                period_label = f"{start}_to_{end}"
            else:
                tickets = TicketCache.objects.none()
                period_label = 'unknown_week'

        elif report_type == 'monthly':
            # Accept both: ?month=4&year=2026  OR  ?start_date=2026-04-01
            year_param  = request.GET.get('year')
            month_param = request.GET.get('month')
            start_date  = request.GET.get('start_date')

            if year_param and month_param:
                # Explicit month + year (sent by generateReport / fixed downloadReport)
                year  = int(year_param)
                month = int(month_param)
            elif start_date:
                # Fallback: parse from start_date=YYYY-MM-DD
                d     = datetime.strptime(start_date, '%Y-%m-%d')
                year  = d.year
                month = d.month
            else:
                # Nothing provided — refuse to default to "today" silently
                return HttpResponse(
                    'Missing month/year parameters. Please generate the report first, then export.',
                    status=400,
                )

            tickets = TicketCache.objects.filter(
                created_at__year=year, created_at__month=month
            )
            month_name = datetime(year, month, 1).strftime('%B')
            period_label = f"{month_name}_{year}"

        elif report_type == 'company':
            company    = request.GET.get('company', '')
            start_date = request.GET.get('start_date', '')
            end_date   = request.GET.get('end_date', '')
            tickets = TicketCache.objects.all()
            if company:
                tickets = tickets.filter(company_name__icontains=company)
            if start_date:
                tickets = tickets.filter(created_at__date__gte=start_date)
            if end_date:
                tickets = tickets.filter(created_at__date__lte=end_date)
            period_label = (company or 'all') + (f"_{start_date}" if start_date else '')

        elif report_type == 'technician':
            technician = request.GET.get('technician', '')
            start_date = request.GET.get('start_date', '')
            end_date   = request.GET.get('end_date', '')
            tickets = TicketCache.objects.all()
            if technician:
                tickets = tickets.filter(technician_name__icontains=technician)
            if start_date:
                tickets = tickets.filter(created_at__date__gte=start_date)
            if end_date:
                tickets = tickets.filter(created_at__date__lte=end_date)
            period_label = (technician or 'all') + (f"_{start_date}" if start_date else '')

        else:
            tickets = TicketCache.objects.none()
            period_label = 'unknown'

        tickets = tickets.order_by('-created_at')

        # Build filename that clearly shows the selected period
        safe_label = period_label.replace(' ', '_').replace('/', '-')
        filename = f"{report_type}_report_{safe_label}.csv"

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow([
            'Ticket ID', 'Subject', 'Status', 'Priority',
            'Company', 'Technician', 'Requester', 'Created At',
        ])
        for ticket in tickets[:5000]:
            writer.writerow([
                ticket.ticket_id,
                ticket.subject,
                ticket.status,
                ticket.priority,
                ticket.company_name,
                ticket.technician_name,
                ticket.requester_name,
                ticket.created_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.created_at else '',
            ])

        return response

    except Exception as exc:
        from django.http import JsonResponse
        return JsonResponse({'error': str(exc)}, status=500)

    except Exception as e:
        return HttpResponse(f"Error exporting CSV: {str(e)}", status=500)

@login_required
def get_companies_api(request):
    """Get list of companies for dropdown"""
    from django.http import JsonResponse
    from .models import TicketCache
    from .simple_reports import _customer_company_filter

    qs = TicketCache.objects.exclude(company_name='')
    customer_company = _customer_company_filter(request)
    if customer_company:
        qs = qs.filter(company_name__iexact=customer_company)

    companies = list(qs.values_list('company_name', flat=True).distinct().order_by('company_name'))
    return JsonResponse(companies, safe=False)

@login_required
def get_technicians_api(request):
    """Get list of technicians for dropdown"""
    from django.http import JsonResponse
    from .models import TicketCache
    from .simple_reports import _customer_company_filter

    qs = TicketCache.objects.exclude(technician_name='')
    customer_company = _customer_company_filter(request)
    if customer_company:
        qs = qs.filter(company_name__iexact=customer_company)

    technicians = list(qs.values_list('technician_name', flat=True).distinct().order_by('technician_name'))
    return JsonResponse(technicians, safe=False)


# ====================================================================== #
#  HELPERS                                                               #
# ====================================================================== #
def _require_tech_or_admin(request):
    """Return user_role string or None if customer (forbidden)."""
    try:
        role = request.user.userprofile.get_role()
    except Exception:
        role = 'technician'
    return None if role == 'customer' else role


def _clean_str(val):
    if isinstance(val, dict):
        return val.get('name') or val.get('content') or val.get('display_value') or ''
    return str(val) if val else ''


def _display_val(val):
    if isinstance(val, dict):
        return val.get('display_value') or val.get('name') or ''
    return str(val) if val else ''


def _process_ticket_for_detail(raw):
    req = raw.get('requester') or {}
    tech = raw.get('technician') or {}
    acct = raw.get('account') or {}
    desc = raw.get('description') or ''
    if isinstance(desc, dict):
        desc = desc.get('content') or ''
    return {
        'id': raw.get('id', ''),
        'subject': raw.get('subject', ''),
        'description': desc,
        'status': _clean_str(raw.get('status')),
        'priority': _clean_str(raw.get('priority')),
        'category': _clean_str(raw.get('category')),
        'requester_name': _clean_str(req) if isinstance(req, dict) else _clean_str(req),
        'requester_email': req.get('email_id', '') if isinstance(req, dict) else '',
        'technician_name': _clean_str(tech) if isinstance(tech, dict) else '',
        'technician_id': tech.get('id', '') if isinstance(tech, dict) else '',
        'company': _clean_str(acct) if isinstance(acct, dict) else '',
        'created_at': _display_val(raw.get('created_time')),
        'updated_at': _display_val(raw.get('last_updated_time')),
        'resolved_at': _display_val(raw.get('resolved_time')),
    }


def _process_notes(raw_list):
    out = []
    for n in (raw_list or []):
        desc = n.get('description') or ''
        if isinstance(desc, dict):
            desc = desc.get('content') or ''
        cb = n.get('created_by') or {}
        out.append({
            'id': n.get('id', ''),
            'description': desc,
            'is_public': n.get('is_public', False),
            'created_by': cb.get('name', '') if isinstance(cb, dict) else '',
            'created_at': _display_val(n.get('created_time')),
        })
    return out


def _process_worklogs(raw_list):
    out = []
    for w in (raw_list or []):
        ts = w.get('time_spent') or {}
        tech = w.get('technician') or {}
        out.append({
            'id': w.get('id', ''),
            'description': w.get('description', ''),
            'hours': ts.get('hours', 0) if isinstance(ts, dict) else 0,
            'minutes': ts.get('minutes', 0) if isinstance(ts, dict) else 0,
            'technician': tech.get('name', '') if isinstance(tech, dict) else '',
            'executed_at': _display_val(w.get('executed_time')),
        })
    return out


def _process_tasks(raw_list):
    out = []
    for t in (raw_list or []):
        owner = t.get('owner') or t.get('assigned_to') or {}
        out.append({
            'id': t.get('id', ''),
            'title': t.get('title', ''),
            'description': t.get('description', ''),
            'status': _clean_str(t.get('status')),
            'owner': owner.get('name', '') if isinstance(owner, dict) else '',
        })
    return out


def _process_approvals(raw_list):
    out = []
    for a in (raw_list or []):
        approver = a.get('approver') or {}
        out.append({
            'id': a.get('id', ''),
            'status': _clean_str(a.get('status')),
            'approver': approver.get('name', '') if isinstance(approver, dict) else '',
            'comments': a.get('comments', ''),
            'created_at': _display_val(a.get('created_time')),
        })
    return out


# ====================================================================== #
#  ME TICKET DETAIL                                                       #
# ====================================================================== #
@login_required
def me_ticket_detail(request, me_ticket_id):
    user_role = _require_tech_or_admin(request)
    if user_role is None:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    me_service = ManageEngineService()

    raw = me_service.get_ticket(me_ticket_id)
    if not raw or 'request' not in raw:
        messages.error(request, f'Ticket {me_ticket_id} not found in ManageEngine.')
        return redirect('dashboard')

    ticket = _process_ticket_for_detail(raw['request'])

    notes_raw = me_service.get_ticket_notes(me_ticket_id)
    worklogs_raw = me_service.get_ticket_worklogs(me_ticket_id)
    tasks_raw = me_service.get_ticket_tasks(me_ticket_id)
    approvals_raw = me_service.get_ticket_approvals(me_ticket_id)

    notes = _process_notes((notes_raw or {}).get('notes', []))
    worklogs = _process_worklogs((worklogs_raw or {}).get('worklogs', []))
    tasks = _process_tasks((tasks_raw or {}).get('tasks', []))
    approvals = _process_approvals((approvals_raw or {}).get('approvals', []))

    from .models import ManageEngineUser
    technicians = list(
        ManageEngineUser.objects.filter(is_technician=True, is_active=True)
        .values('me_id', 'name', 'email').order_by('name')
    )

    # Find current user's ME ID for self-assign (pickup)
    current_user_me_id = None
    me_user = ManageEngineUser.objects.filter(
        email__iexact=request.user.email).first()
    if me_user:
        current_user_me_id = me_user.me_id

    return render(request, 'tickets/me_ticket_detail.html', {
        'ticket': ticket,
        'me_ticket_id': me_ticket_id,
        'notes': notes,
        'worklogs': worklogs,
        'tasks': tasks,
        'approvals': approvals,
        'technicians': technicians,
        'user_role': user_role,
        'current_user_me_id': current_user_me_id,
        'closure_codes': ['Resolved', 'Unable to Reproduce', 'Not a Bug',
                          'Duplicate', 'Workaround Provided', 'User Error', 'Other'],
    })


# ====================================================================== #
#  NOTE ACTIONS                                                           #
# ====================================================================== #
@login_required
@require_http_methods(["POST"])
def me_ticket_add_note(request, me_ticket_id):
    if _require_tech_or_admin(request) is None:
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
    description = request.POST.get('description', '').strip()
    is_public = request.POST.get('is_public', 'false').lower() == 'true'
    if not description:
        return JsonResponse({'success': False, 'message': 'Note description is required'})
    result = ManageEngineService().add_ticket_note(me_ticket_id, description, is_public)
    if result:
        return JsonResponse({'success': True, 'message': 'Note added successfully'})
    return JsonResponse({'success': False, 'message': 'Failed to add note. Check ManageEngine API.'})


@login_required
@require_http_methods(["POST"])
def me_ticket_edit_note(request, me_ticket_id, note_id):
    if _require_tech_or_admin(request) is None:
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
    description = request.POST.get('description', '').strip()
    is_public = request.POST.get('is_public', 'false').lower() == 'true'
    if not description:
        return JsonResponse({'success': False, 'message': 'Note description is required'})
    result = ManageEngineService().edit_ticket_note(me_ticket_id, note_id, description, is_public)
    if result:
        return JsonResponse({'success': True, 'message': 'Note updated successfully'})
    return JsonResponse({'success': False, 'message': 'Failed to update note'})


@login_required
@require_http_methods(["POST"])
def me_ticket_delete_note(request, me_ticket_id, note_id):
    if _require_tech_or_admin(request) is None:
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
    ok = ManageEngineService().delete_ticket_note(me_ticket_id, note_id)
    if ok:
        return JsonResponse({'success': True, 'message': 'Note deleted'})
    return JsonResponse({'success': False, 'message': 'Failed to delete note'})


# ====================================================================== #
#  WORKLOG ACTIONS                                                        #
# ====================================================================== #
@login_required
@require_http_methods(["POST"])
def me_ticket_add_worklog(request, me_ticket_id):
    if _require_tech_or_admin(request) is None:
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
    description = request.POST.get('description', '').strip()
    hours = request.POST.get('hours', '0')
    minutes = request.POST.get('minutes', '0')
    technician_id = request.POST.get('technician_id', '').strip()
    if not description:
        return JsonResponse({'success': False, 'message': 'Description is required'})
    try:
        hours = max(0, int(hours))
        minutes = max(0, min(59, int(minutes)))
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid hours/minutes'})
    if hours == 0 and minutes == 0:
        return JsonResponse({'success': False, 'message': 'Time spent must be greater than 0'})
    result = ManageEngineService().add_ticket_worklog(
        me_ticket_id, description, hours, minutes, technician_id or None)
    if result:
        return JsonResponse({'success': True, 'message': 'Worklog added successfully'})
    return JsonResponse({'success': False, 'message': 'Failed to add worklog'})


@login_required
@require_http_methods(["POST"])
def me_ticket_delete_worklog(request, me_ticket_id, worklog_id):
    if _require_tech_or_admin(request) is None:
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
    ok = ManageEngineService().delete_ticket_worklog(me_ticket_id, worklog_id)
    if ok:
        return JsonResponse({'success': True, 'message': 'Worklog deleted'})
    return JsonResponse({'success': False, 'message': 'Failed to delete worklog'})


# ====================================================================== #
#  TASK ACTIONS                                                           #
# ====================================================================== #
@login_required
@require_http_methods(["POST"])
def me_ticket_add_task(request, me_ticket_id):
    if _require_tech_or_admin(request) is None:
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    assigned_to_id = request.POST.get('assigned_to_id', '').strip()
    if not title:
        return JsonResponse({'success': False, 'message': 'Task title is required'})
    result = ManageEngineService().add_ticket_task(
        me_ticket_id, title, description, assigned_to_id or None)
    if result:
        return JsonResponse({'success': True, 'message': 'Task added successfully'})
    return JsonResponse({'success': False, 'message': 'Failed to add task'})


@login_required
@require_http_methods(["POST"])
def me_ticket_update_task(request, me_ticket_id, task_id):
    if _require_tech_or_admin(request) is None:
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
    action = request.POST.get('action', '')
    updates = {}
    if action == 'complete':
        updates = {'status': {'name': 'Completed'}}
    elif action == 'reopen':
        updates = {'status': {'name': 'Open'}}
    else:
        title = request.POST.get('title', '').strip()
        desc = request.POST.get('description', '').strip()
        if title:
            updates['title'] = title
        if desc:
            updates['description'] = desc
    if not updates:
        return JsonResponse({'success': False, 'message': 'Nothing to update'})
    result = ManageEngineService().update_ticket_task(me_ticket_id, task_id, updates)
    if result:
        return JsonResponse({'success': True, 'message': 'Task updated successfully'})
    return JsonResponse({'success': False, 'message': 'Failed to update task'})


@login_required
@require_http_methods(["POST"])
def me_ticket_delete_task(request, me_ticket_id, task_id):
    if _require_tech_or_admin(request) is None:
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
    ok = ManageEngineService().delete_ticket_task(me_ticket_id, task_id)
    if ok:
        return JsonResponse({'success': True, 'message': 'Task deleted'})
    return JsonResponse({'success': False, 'message': 'Failed to delete task'})


# ====================================================================== #
#  ASSIGN / PICKUP / CLOSE                                               #
# ====================================================================== #
@login_required
@require_http_methods(["POST"])
def me_ticket_assign(request, me_ticket_id):
    if _require_tech_or_admin(request) is None:
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
    technician_id = request.POST.get('technician_id', '').strip()
    if not technician_id:
        return JsonResponse({'success': False, 'message': 'Please select a technician'})
    try:
        result = ManageEngineService().assign_technician(me_ticket_id, technician_id)
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {e}'})
    if result is not None:
        # Check for API-level error in the response body
        if isinstance(result, dict) and result.get('response_status'):
            msgs = result['response_status'].get('messages', [])
            err = msgs[0].get('message') if msgs else None
            if err:
                return JsonResponse({'success': False, 'message': f'ManageEngine: {err}'})
        return JsonResponse({'success': True, 'message': 'Technician assigned successfully'})
    return JsonResponse({'success': False, 'message': 'Failed to reach ManageEngine API — check server logs.'})


@login_required
@require_http_methods(["POST"])
def me_ticket_pickup(request, me_ticket_id):
    if _require_tech_or_admin(request) is None:
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
    from .models import ManageEngineUser
    me_user = ManageEngineUser.objects.filter(email__iexact=request.user.email).first()
    if not me_user:
        return JsonResponse({
            'success': False,
            'message': 'Your account is not linked to a ManageEngine technician. '
                       'Ensure your portal email matches your ManageEngine email.'
        })
    result = ManageEngineService().pickup_ticket(me_ticket_id, me_user.me_id)
    if result:
        return JsonResponse({'success': True,
                             'message': f'Ticket picked up by {me_user.name}'})
    return JsonResponse({'success': False, 'message': 'Failed to pick up ticket'})


@login_required
@require_http_methods(["POST"])
def me_ticket_close(request, me_ticket_id):
    if _require_tech_or_admin(request) is None:
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
    resolution = request.POST.get('resolution', '').strip()
    closure_code = request.POST.get('closure_code', 'Resolved').strip()
    result = ManageEngineService().close_ticket(me_ticket_id, resolution, closure_code)
    if result:
        return JsonResponse({'success': True, 'message': 'Ticket closed successfully'})
    return JsonResponse({'success': False, 'message': 'Failed to close ticket'})


# ====================================================================== #
#  ATTACHMENT                                                             #
# ====================================================================== #
@login_required
@require_http_methods(["POST"])
def me_ticket_add_attachment(request, me_ticket_id):
    if _require_tech_or_admin(request) is None:
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
    attachment = request.FILES.get('attachment')
    if not attachment:
        return JsonResponse({'success': False, 'message': 'No file selected'})
    if attachment.size > 10 * 1024 * 1024:
        return JsonResponse({'success': False, 'message': 'File must be under 10 MB'})
    result = ManageEngineService().add_ticket_attachment(me_ticket_id, attachment)
    if result:
        return JsonResponse({'success': True, 'message': f'"{attachment.name}" attached successfully'})
    return JsonResponse({'success': False, 'message': 'Failed to upload attachment'})


# ====================================================================== #
#  APPROVAL ACTIONS                                                       #
# ====================================================================== #
@login_required
@require_http_methods(["POST"])
def me_ticket_send_approval(request, me_ticket_id):
    if _require_tech_or_admin(request) is None:
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
    approver_id = request.POST.get('approver_id', '').strip()
    if not approver_id:
        return JsonResponse({'success': False, 'message': 'Please select an approver'})
    result = ManageEngineService().send_for_approval(me_ticket_id, approver_id)
    if result:
        return JsonResponse({'success': True, 'message': 'Ticket sent for approval'})
    return JsonResponse({'success': False, 'message': 'Failed to send for approval'})


@login_required
@require_http_methods(["POST"])
def me_ticket_approve_reject(request, me_ticket_id, approval_id):
    role = _require_tech_or_admin(request)
    if role is None:
        return JsonResponse({'success': False, 'message': 'Access denied'}, status=403)
    action = request.POST.get('action', '').strip()  # 'Approved' or 'Rejected'
    comments = request.POST.get('comments', '').strip()
    if action not in ('Approved', 'Rejected'):
        return JsonResponse({'success': False, 'message': 'Invalid action'})
    result = ManageEngineService().approve_reject_ticket(
        me_ticket_id, approval_id, action, comments)
    if result:
        return JsonResponse({'success': True, 'message': f'Approval {action.lower()} successfully'})
    return JsonResponse({'success': False, 'message': f'Failed to {action.lower()} approval'})


@login_required
def tickets_by_status_api(request):
    """Return paginated tickets filtered by status for the dashboard modal."""
    from .models import TicketCache
    from .simple_reports import _customer_company_filter
    from django.core.paginator import Paginator

    status = request.GET.get('status', '')
    page = int(request.GET.get('page', 1))
    search = request.GET.get('search', '').strip()
    order = request.GET.get('order', 'desc')  # desc or asc
    per_page = 50

    qs = TicketCache.objects.all()

    # Customer: restrict to their company
    customer_company = _customer_company_filter(request)
    if customer_company:
        qs = qs.filter(company_name__iexact=customer_company)

    # Status filtering - map to exact local database status values
    if status and status.lower() != 'all':
        if status.lower() == 'onhold':
            # All hold variations from local database
            qs = qs.filter(status__in=[
                'Onhold', 'On Hold - For Spare', 'On Hold – Business Dependency',
                'On Hold – User Dependency', 'On Hold - Digtinctive Backend',
                'On Hold - For Commercial Approval', 'Under Observation'
            ])
        elif status.lower() == 'closed':
            # Exact local database "Closed" status
            qs = qs.filter(status='Closed')
        elif status.lower() == 'cancelled':
            # Exact local database "Cancelled" status  
            qs = qs.filter(status='Cancelled')
        elif status.lower() == 'open':
            # Exact local database "Open" status
            qs = qs.filter(status='Open')
        elif status.lower() == 'resolved':
            # Exact local database "Resolved" status
            qs = qs.filter(status='Resolved')
        else:
            qs = qs.filter(status__iexact=status)

    # Search filtering
    if search:
        qs = qs.filter(
            models.Q(ticket_id__icontains=search) |
            models.Q(subject__icontains=search) |
            models.Q(requester_name__icontains=search) |
            models.Q(company_name__icontains=search) |
            models.Q(technician_name__icontains=search)
        )

    # Ordering
    order_field = '-created_at' if order == 'desc' else 'created_at'
    qs = qs.order_by(order_field)

    total_count = qs.count()
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(page)

    tickets = list(page_obj.object_list.values(
        'ticket_id', 'subject', 'status', 'priority',
        'company_name', 'technician_name', 'requester_name', 'created_at'
    ))

    for t in tickets:
        if t['created_at']:
            t['created_at'] = t['created_at'].strftime('%d %b %Y')

    return JsonResponse({
        'tickets': tickets,
        'total': total_count,
        'page': page,
        'per_page': per_page,
        'total_pages': paginator.num_pages,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'search': search,
        'order': order
    })


@login_required
def dashboard_tickets_api(request):
    """
    Paginated + searchable ticket list for the dashboard Recent Tickets table.
    Respects company scoping (customer sees only their own company's tickets).

    GET params:
        page       — page number (default 1)
        per_page   — rows per page: 10 / 25 / 50 (default 25)
        search     — free-text search across ID, subject, requester, company, status, priority
        status     — filter by exact status (optional)
        priority   — filter by exact priority (optional)
    """
    from .models import TicketCache
    from .simple_reports import _customer_company_filter
    from django.core.paginator import Paginator
    from django.db.models import Q

    page         = max(1, int(request.GET.get('page', 1)))
    per_page     = min(int(request.GET.get('per_page', 10)), 100)
    search       = request.GET.get('search', '').strip()
    status_f     = request.GET.get('status', '').strip()
    priority_f   = request.GET.get('priority', '').strip()
    technician_f = request.GET.get('technician', '').strip()

    qs = TicketCache.objects.all()

    # Customer: restrict to own company only
    company = _customer_company_filter(request)
    if company:
        qs = qs.filter(company_name__iexact=company)
    else:
        # Technician with company restrictions
        try:
            role = request.user.userprofile.get_role()
        except Exception:
            role = 'admin'
        if role == 'technician':
            from rbac.utils import get_technician_companies
            allowed = get_technician_companies(request.user)
            if allowed is not None:
                qs = qs.filter(company_name__in=allowed)

    # Free-text search
    if search:
        qs = qs.filter(
            Q(ticket_id__icontains=search) |
            Q(subject__icontains=search) |
            Q(requester_name__icontains=search) |
            Q(company_name__icontains=search) |
            Q(technician_name__icontains=search) |
            Q(status__icontains=search) |
            Q(priority__icontains=search)
        )

    if status_f:
        qs = qs.filter(status__iexact=status_f)

    if priority_f:
        qs = qs.filter(priority__iexact=priority_f)

    if technician_f:
        qs = qs.filter(technician_name__iexact=technician_f)

    qs = qs.order_by('-created_at')
    total = qs.count()

    paginator = Paginator(qs, per_page)
    page_obj  = paginator.get_page(page)

    tickets = []
    for t in page_obj.object_list:
        tickets.append({
            'id':         t.ticket_id,
            'subject':    t.subject or '',
            'status':     t.status or '',
            'priority':   t.priority or '',
            'requester':  t.requester_name or '',
            'company':    t.company_name or '',
            'technician': t.technician_name or '',
            'created_at': t.created_at.strftime('%d %b %Y %H:%M') if t.created_at else '',
        })

    return JsonResponse({
        'tickets':     tickets,
        'total':       total,
        'page':        page,
        'per_page':    per_page,
        'total_pages': paginator.num_pages,
        'has_next':    page_obj.has_next(),
        'has_prev':    page_obj.has_previous(),
    })


# ── Export views ──────────────────────────────────────────────────────────────

def _csv_response(filename, headers, rows):
    """Helper: return an HttpResponse with CSV content."""
    import csv
    from django.http import HttpResponse
    from datetime import datetime
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = f'attachment; filename="{filename}_{ts}.csv"'
    w = csv.writer(resp)
    w.writerow(headers)
    for row in rows:
        w.writerow(row)
    return resp


@login_required
def export_manageengine_csv(request):
    """Export ManageEngine ticket data as CSV (company-scoped for customers)."""
    from .models import TicketCache
    from .simple_reports import _customer_company_filter

    qs = TicketCache.objects.all().order_by('-created_at')
    company = _customer_company_filter(request)
    if company:
        qs = qs.filter(company_name__iexact=company)

    rows = []
    for t in qs:
        rows.append([
            t.ticket_id,
            t.subject or '',
            t.status or '',
            t.priority or '',
            t.requester_name or '',
            t.company_name or '',
            t.technician_name or '',
            t.created_at.strftime('%d %b %Y %H:%M') if t.created_at else '',
        ])
    return _csv_response('manageengine_tickets', [
        'Ticket ID', 'Subject', 'Status', 'Priority',
        'Requester', 'Company', 'Technician', 'Created At',
    ], rows)


@login_required
def export_pulseway_csv(request):
    """Export Pulseway device data as CSV (company-scoped for customers)."""
    from pulseway.models import PulsewayDevice
    from rbac.utils import get_technician_companies

    try:
        profile = request.user.userprofile
        role = profile.get_role()
        user_company = profile.company.name if profile.company else None
    except Exception:
        role = 'admin'
        user_company = None

    qs = PulsewayDevice.objects.all().order_by('organization_name', 'device_name')

    if role == 'customer' and user_company:
        from pulseway.local_service import PulsewayLocalService
        svc = PulsewayLocalService()
        qs = svc.get_company_devices(user_company)
    elif role == 'technician':
        allowed = get_technician_companies(request.user)
        if allowed is not None:
            qs = qs.filter(organization_name__in=allowed)

    rows = [[
        d.device_name, d.organization_name, d.site_name,
        d.status, d.uptime, d.ip_address, d.operating_system,
        d.pending_patches, d.mac_address,
        d.last_seen.strftime('%d %b %Y %H:%M') if d.last_seen else '',
    ] for d in qs]

    return _csv_response('pulseway_devices', [
        'Device Name', 'Organisation', 'Site', 'Status', 'Uptime',
        'IP Address', 'Operating System', 'Pending Patches', 'MAC Address', 'Last Seen',
    ], rows)


@login_required
def export_mdm_csv(request):
    """Export MDM device data as CSV from live API (company-scoped)."""
    try:
        profile = request.user.userprofile
        role = profile.get_role()
        company_obj = profile.company
    except Exception:
        role = 'admin'
        company_obj = None

    from mdm.models import MdmCustomer
    from mdm.live_service import fetch_live_devices

    if role == 'customer' and company_obj:
        customers = list(MdmCustomer.objects.filter(company=company_obj))
    elif role in ('admin', 'technician'):
        customers = list(MdmCustomer.objects.select_related('company').all())
    else:
        customers = []

    devices = fetch_live_devices(customers)
    devices.sort(key=lambda d: (d['customer_name'].lower(), d['device_name'].lower()))

    rows = [[
        d['device_name'],
        d['customer_name'],
        d['device_type'].title(),
        d['model'],
        d['os_version'],
        d['serial_number'],
        d['status_display'],
        d['username'],
        d['user_email'],
        'Yes' if d['is_encrypted'] else 'No',
        f"{d['storage_gb']} GB" if d['storage_gb'] else '',
        d['last_contact_time'].strftime('%d %b %Y %H:%M') if d['last_contact_time'] else '',
    ] for d in devices]

    return _csv_response('mdm_devices', [
        'Device Name', 'Company', 'Type', 'Model', 'OS Version',
        'Serial Number', 'Status', 'Username', 'User Email',
        'Encrypted', 'Storage', 'Last Contact',
    ], rows)


@login_required
def export_o365_users_csv(request):
    """Export Office 365 user + license details as CSV."""
    from office365.services import Office365API
    from rbac.utils import has_package_access

    if not has_package_access(request.user, 'office365') and \
       not has_package_access(request.user, 'office 365') and \
       not has_package_access(request.user, 'microsoft365'):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('No Office 365 access.')

    try:
        api = Office365API()
        users = api.get_all_users_detailed()
    except Exception as exc:
        from django.http import HttpResponse
        return HttpResponse(f'Error fetching O365 data: {exc}', status=502)

    rows = [[
        u.get('display_name', ''),
        u.get('upn', ''),
        u.get('department', ''),
        u.get('job_title', ''),
        u.get('usage_location', ''),
        'Active' if u.get('account_enabled') else 'Disabled',
        u.get('user_type', 'Member'),
        str(u.get('license_count', 0)),
        u.get('licenses', 'No License'),
        u.get('last_sign_in', ''),
        u.get('created', ''),
    ] for u in users]

    return _csv_response('o365_users', [
        'Display Name', 'Email (UPN)', 'Department', 'Job Title',
        'Usage Location', 'Account Status', 'User Type',
        'License Count', 'Assigned Licenses',
        'Last Sign-In', 'Created Date',
    ], rows)


@login_required
def o365_users_api(request):
    """JSON API — returns O365 user+license list for the reports page table."""
    from office365.services import Office365API
    from rbac.utils import has_package_access

    if not has_package_access(request.user, 'office365') and \
       not has_package_access(request.user, 'office 365') and \
       not has_package_access(request.user, 'microsoft365'):
        return JsonResponse({'error': 'No access'}, status=403)

    search  = request.GET.get('search', '').lower().strip()
    page    = max(1, int(request.GET.get('page', 1)))
    per_page = 25

    try:
        api   = Office365API()
        users = api.get_all_users_detailed()
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=502)

    if search:
        users = [u for u in users if
                 search in u.get('display_name', '').lower() or
                 search in u.get('upn', '').lower() or
                 search in u.get('department', '').lower() or
                 search in u.get('licenses', '').lower()]

    total      = len(users)
    start      = (page - 1) * per_page
    page_users = users[start:start + per_page]
    total_pages = max(1, (total + per_page - 1) // per_page)

    return JsonResponse({
        'users':       page_users,
        'total':       total,
        'page':        page,
        'total_pages': total_pages,
        'has_next':    page < total_pages,
        'has_prev':    page > 1,
    })
