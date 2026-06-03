from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import models
from django.core.paginator import Paginator
from django.http import JsonResponse
from datetime import timedelta
from pulseway.services import PulsewayAPI
from pulseway.manageengine_service import ManageEngineAPI
import json
from pulseway.company_matcher import CompanyMatcher
from office365.services import Office365API
from office365.customer_config import get_customer_config


@login_required
def company_dashboard(request):
    user = request.user
    
    # Get company from query parameter (for admin/tech users)
    requested_company_name = request.GET.get('company')
    
    # Get user role and company
    try:
        user_profile = user.userprofile
        user_role    = user_profile.get_role()
        user_company = user_profile.company
    except Exception:
        user_role    = 'admin' if user.is_superuser else 'technician'
        user_company = None

    is_admin = user.is_superuser or user_role == 'admin'

    # Non-admin with no company assigned — cannot proceed
    if not is_admin and not user_company:
        messages.error(request, 'No company assigned to your profile.')
        return redirect('home')

    # Resolve which company to show
    if requested_company_name:
        # Customers/technicians can only view their own company
        if not is_admin and user_company and requested_company_name != user_company.name:
            messages.error(request, 'You are not authorised to view this company.')
            return redirect('rbac:company_dashboard')
        company_name = requested_company_name
    elif user_company:
        company_name = user_company.name
    else:
        # Admin with no company in profile and no ?company= param:
        # show a company picker so they can choose
        from rbac.models import Company
        companies = Company.objects.all().order_by('name')
        if not companies.exists():
            messages.error(request, 'No companies found in the system.')
            return redirect('rbac:admin_dashboard')
        # If only one company exists, go straight to it
        if companies.count() == 1:
            company_name = companies.first().name
        else:
            return render(request, 'rbac/company_picker.html', {
                'companies': companies,
                'user_role': user_role,
            })
    
    # Admins see all modules; others are gated by UserPackageAccess
    from rbac.models import UserPackageAccess
    if is_admin:
        has_pulseway_access    = True
        has_manageengine_access = True
        has_office365_access   = True
        has_mdm_access         = True
    else:
        user_packages = UserPackageAccess.objects.filter(
            user=user, is_enabled=True
        ).select_related('package')
        has_pulseway_access     = user_packages.filter(package__name__icontains='pulseway').exists()
        has_manageengine_access = user_packages.filter(package__name__icontains='manage').exists()
        has_office365_access    = user_packages.filter(package__name__icontains='office').exists()
        has_mdm_access          = user_packages.filter(package__name='mdm').exists()
    
    context = {
        'company_name': company_name,
        'user_role': user_role,
        'has_pulseway_access': has_pulseway_access,
        'has_manageengine_access': has_manageengine_access,
        'has_office365_access': has_office365_access,
        'has_mdm_access': has_mdm_access,
        'all_devices': json.dumps([]),  # Default empty
        'all_tickets': json.dumps([]),  # Default empty
    }
    
    # --- Pulseway (local DB, guarded by package access) ---
    if has_pulseway_access:
        try:
            from pulseway.local_service import PulsewayLocalService

            pw_svc = PulsewayLocalService()
            pulseway_stats = pw_svc.get_company_stats(company_name)
            
            # Get all devices data for frontend — same matcher as get_company_stats
            devices = pw_svc.get_company_devices(company_name)
            all_devices = []
            for device in devices:
                all_devices.append({
                    'device_name': device.device_name,
                    'status': device.status,
                    'organization_name': device.organization_name or '-',
                    'site_name': device.site_name or '-',
                    'ip_address': device.ip_address or 'N/A',
                    'operating_system': device.operating_system or 'N/A',
                    'uptime': device.uptime or '-',
                    'pending_patches': device.pending_patches or 0,
                    'last_updated': device.last_updated.strftime('%d %b %Y') if device.last_updated else 'N/A'
                })
            
            context.update({
                'total_devices': pulseway_stats['total_devices'],
                'online_devices': pulseway_stats['online_devices'],
                'offline_devices': pulseway_stats['offline_devices'],
                'pending_patches': pulseway_stats['pending_patches'],
                'up_to_date_patches': pulseway_stats['up_to_date_patches'],
                'pulseway_sync_info': pw_svc.get_last_sync_info(),
                'recent_devices': pw_svc.get_recent_devices(company_name, limit=5),
                'all_devices': json.dumps(all_devices),
            })
        except Exception as e:
            context['device_error'] = str(e)

    # --- ManageEngine / Tickets (local DB, guarded by package access) ---
    if has_manageengine_access:
        try:
            from tickets.local_service import LocalTicketService
            from tickets.models import TicketCache
            from datetime import timedelta
            
            tk_svc = LocalTicketService()
            matched_company = tk_svc.find_company_in_cache(company_name)
            thirty_days_ago = timezone.now() - timedelta(days=30)
            company_tickets = tk_svc.get_tickets_for_reports({
                'company': matched_company or company_name,
                'date_from': thirty_days_ago.date(),
            })
            
            # Get all tickets data for frontend
            all_tickets = []
            for ticket in company_tickets:
                all_tickets.append({
                    'ticket_id': ticket.ticket_id,
                    'subject': ticket.subject,
                    'status': ticket.status,
                    'priority': ticket.priority,
                    'requester_name': ticket.requester_name,
                    'technician_name': ticket.technician_name,
                    'created_at': ticket.created_at.strftime('%d %b %Y') if ticket.created_at else 'N/A'
                })
            
            # Known status groups
            open_c       = company_tickets.filter(status__iexact='Open').count()
            progress_c   = company_tickets.filter(status__icontains='Progress').count()
            pending_c    = company_tickets.filter(status__iexact='Pending').count()
            resolved_c   = company_tickets.filter(status__iexact='Resolved').count()
            closed_c     = company_tickets.filter(status__iexact='Closed').count()
            cancelled_c  = company_tickets.filter(status__iexact='Cancelled').count()
            onhold_c     = company_tickets.filter(
                models.Q(status__iexact='Onhold') |
                models.Q(status__icontains='On Hold')
            ).count()
            # BUG-01/BUG-05 fix: capture any ticket not matched by the above groups
            accounted    = open_c + progress_c + pending_c + resolved_c + closed_c + cancelled_c + onhold_c
            total_c      = company_tickets.count()
            other_c      = total_c - accounted  # e.g. "Under Observation", custom On Hold variants

            context.update({
                'total_tickets':       total_c,
                'open_tickets':        open_c,
                'in_progress_tickets': progress_c,
                'pending_tickets':     pending_c,
                'resolved_tickets':    resolved_c,
                'closed_tickets':      closed_c,
                'cancelled_tickets':   cancelled_c,
                'onhold_tickets':      onhold_c,
                'other_tickets':       other_c,   # non-standard statuses
                'sync_info':           tk_svc.get_last_sync_info(),
                'all_tickets':         json.dumps(all_tickets),
            })
        except Exception as e:
            context['ticket_error'] = str(e)

    # --- Office 365 (live lightweight summary, guarded by package access) ---
    if has_office365_access:
        try:
            from office365.customer_config import resolve_customer_key, O365_CUSTOMER_KEYS_WITH_DATA
            customer_key = resolve_customer_key(company_name)
            if customer_key and customer_key in O365_CUSTOMER_KEYS_WITH_DATA:
                # BUG-04 fix: only call API when tenant has real (non-demo) credentials
                api = Office365API(customer_key=customer_key)
                license_summary = api.get_license_summary()
                total = sum(lic['total'] for lic in license_summary)
                consumed = sum(lic['consumed'] for lic in license_summary)
                context.update({
                    'total_licenses': total,
                    'consumed_licenses': consumed,
                    'available_licenses': total - consumed,
                })
            elif customer_key:
                context['license_error'] = 'Office 365 data not yet configured for this company'
            else:
                context['license_error'] = 'No Office 365 configuration found for this company'
        except Exception as e:
            context['license_error'] = str(e)

    # --- MDM (live API, guarded by package access) ---
    if has_mdm_access:
        try:
            from mdm.models import MdmCustomer
            from mdm.manageengine_mdm_service import ManageEngineMDMService, MANAGED_STATUS_MAP
            from rbac.utils import find_company_for_name
            company_obj = find_company_for_name(company_name) or user_company
            mdm_total = mdm_active = mdm_retired = mdm_pending = 0
            if company_obj:
                customers = list(MdmCustomer.objects.filter(company=company_obj))
                if customers:
                    svc = ManageEngineMDMService()
                    for customer in customers:
                        try:
                            raw_list, _ = svc.get_devices(customer_id=customer.customer_id)
                            for d in (raw_list or []):
                                if str(d.get('is_removed', 'false')).lower() == 'true':
                                    continue
                                _internal = MANAGED_STATUS_MAP.get(
                                    str(d.get('managed_status', '2')), 'managed')
                                status = 'active' if _internal in ('managed', 'active') else _internal
                                mdm_total += 1
                                if status == 'active':
                                    mdm_active += 1
                                elif status == 'retired':
                                    mdm_retired += 1
                                else:
                                    mdm_pending += 1
                        except Exception:
                            pass
            context.update({
                'mdm_total_devices':   mdm_total,
                'mdm_active_devices':  mdm_active,
                'mdm_retired_devices': mdm_retired,
                'mdm_pending_devices': mdm_pending,
                'mdm_security_alerts': 0,
            })
        except Exception as e:
            context['mdm_error'] = str(e)
            context.update({
                'mdm_total_devices': 0, 'mdm_active_devices': 0,
                'mdm_retired_devices': 0, 'mdm_pending_devices': 0,
                'mdm_security_alerts': 0,
            })
    
    return render(request, 'rbac/company_dashboard.html', context)


@login_required
def device_details_popup(request):
    """Get device details for popup from database"""
    company_name = request.GET.get('company')
    status = request.GET.get('status', 'all')
    page = int(request.GET.get('page', 1))

    # Enforce company restriction for customers and technicians
    try:
        user_role = request.user.userprofile.get_role()
        user_company = request.user.userprofile.company
        if user_role in ('customer', 'technician') and company_name != (user_company.name if user_company else None):
            return JsonResponse({'error': 'Access denied'}, status=403)
    except Exception:
        pass

    try:
        from django.core.paginator import Paginator
        from pulseway.local_service import PulsewayLocalService

        # Use same company→device resolution as get_company_stats
        pw_svc = PulsewayLocalService()
        devices = pw_svc.get_company_devices(company_name)

        # Filter by status
        if status == 'online':
            devices = devices.filter(status='online')
        elif status == 'offline':
            devices = devices.filter(status='offline')

        devices = devices.order_by('device_name')
        
        # Paginate - 15 per page
        paginator = Paginator(devices, 15)
        page_obj = paginator.get_page(page)
        
        # Build response data
        devices_data = []
        for device in page_obj:
            devices_data.append({
                'device_name': device.device_name,
                'status': device.status,
                'organization_name': device.organization_name or 'N/A',
                'site_name': device.site_name or 'N/A', 
                'uptime': device.uptime or 'N/A',
                'last_updated': device.last_updated.strftime('%Y-%m-%d %H:%M') if device.last_updated else 'Never'
            })
        
        return JsonResponse({
            'devices': devices_data,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'current_page': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def ticket_details_popup(request):
    """Get ticket details for popup from database"""
    company_name = request.GET.get('company')
    status = request.GET.get('status', 'all')
    page = int(request.GET.get('page', 1))
    
    try:
        from tickets.models import TicketCache
        from django.core.paginator import Paginator
        
        # Get tickets from last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        tickets = TicketCache.objects.filter(created_at__gte=thirty_days_ago)
        
        # Filter by company using the same mapping logic as LocalTicketService
        if company_name:
            from tickets.local_service import LocalTicketService
            local_service = LocalTicketService()
            
            # Use the service's mapping logic
            company_tickets = local_service.get_tickets_for_reports({
                'company': company_name,
                'date_from': thirty_days_ago.date()
            })
            
            # Get the ticket IDs to filter the main queryset
            ticket_ids = company_tickets.values_list('id', flat=True)
            tickets = tickets.filter(id__in=ticket_ids)
        
        # Filter by status
        if status != 'all':
            if status == 'Hold':
                tickets = tickets.filter(models.Q(status__iexact='Onhold') | models.Q(status__icontains='On Hold'))
            elif status == 'Progress':
                tickets = tickets.filter(status__icontains='Progress')
            else:
                tickets = tickets.filter(status__iexact=status)
        
        tickets = tickets.order_by('-created_at')
        
        # Paginate - 15 per page
        paginator = Paginator(tickets, 15)
        page_obj = paginator.get_page(page)
        
        # Build response data
        tickets_data = []
        for ticket in page_obj:
            tickets_data.append({
                'ticket_id': ticket.ticket_id,
                'subject': ticket.subject[:80] + '...' if len(ticket.subject) > 80 else ticket.subject,
                'status': ticket.status,
                'priority': ticket.priority or 'Normal',
                'technician_name': ticket.technician_name or 'Unassigned',
                'requester_name': ticket.requester_name or 'Unknown',
                'created_at': ticket.created_at.strftime('%Y-%m-%d %H:%M') if ticket.created_at else 'N/A'
            })
        
        return JsonResponse({
            'tickets': tickets_data,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'current_page': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_count': paginator.count
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def company_tickets_by_status(request):
    """Show tickets filtered by status for company dashboard"""
    from tickets.local_service import LocalTicketService
    from datetime import timedelta
    
    # Get parameters
    status = request.GET.get('status', '')
    company_name = request.GET.get('company', '')
    
    if not company_name:
        # Get user's company
        user_profile = request.user.userprofile
        user_company = user_profile.company
        company_name = user_company.name
    
    # Get last 30 days tickets
    thirty_days_ago = timezone.now() - timedelta(days=30)
    local_service = LocalTicketService()
    
    # Get company tickets from last 30 days
    filters = {
        'company': company_name,
        'date_from': thirty_days_ago.date()
    }
    
    # Add status filter
    if status:
        filters['status'] = status
    
    tickets = local_service.get_tickets_for_reports(filters)
    
    context = {
        'tickets': tickets[:100],  # Limit to 100 for performance
        'total_count': tickets.count(),
        'status_filter': status,
        'company_name': company_name,
        'page_title': f'{status.title()} Tickets' if status else 'All Tickets'
    }
    
    return render(request, 'rbac/company_tickets_list.html', context)


@login_required
def company_devices_by_status(request):
    """Show devices filtered by status for company dashboard"""
    from pulseway.local_service import PulsewayLocalService
    
    # Get parameters
    status = request.GET.get('status', '')
    company_name = request.GET.get('company', '')
    page = int(request.GET.get('page', 1))
    per_page = 20
    
    if not company_name:
        # Get user's company
        user_profile = request.user.userprofile
        user_company = user_profile.company
        company_name = user_company.name
    
    pulseway_service = PulsewayLocalService()
    
    # Get devices by status
    devices = pulseway_service.get_devices_by_status(company_name, status)
    
    # Pagination
    start = (page - 1) * per_page
    end = start + per_page
    paginated_devices = devices[start:end]
    
    total_pages = (devices.count() + per_page - 1) // per_page
    
    context = {
        'devices': paginated_devices,
        'total_count': devices.count(),
        'status_filter': status,
        'company_name': company_name,
        'page': page,
        'total_pages': total_pages,
        'has_previous': page > 1,
        'has_next': page < total_pages,
        'previous_page': page - 1 if page > 1 else None,
        'next_page': page + 1 if page < total_pages else None,
        'page_title': f'{status.replace("_", " ").title()} Devices' if status else 'All Devices'
    }
    
    return render(request, 'rbac/company_devices_list.html', context)


@login_required
def company_devices_api(request):
    """API endpoint for fetching devices by status"""
    from django.http import JsonResponse
    from django.core.paginator import Paginator
    from pulseway.local_service import PulsewayLocalService

    # Get parameters
    status = request.GET.get('status', '')
    company_name = request.GET.get('company', '')
    page = int(request.GET.get('page', 1))

    # Enforce company restriction for customers and technicians
    try:
        user_role = request.user.userprofile.get_role()
        user_company = request.user.userprofile.company
        if user_role in ('customer', 'technician') and company_name != (user_company.name if user_company else None):
            return JsonResponse({'error': 'Access denied'}, status=403)
    except Exception:
        pass

    # Use get_company_devices — same path as get_company_stats, guaranteed correct match
    pw_svc = PulsewayLocalService()
    devices_qs = pw_svc.get_company_devices(company_name)

    if status == 'online':
        devices_qs = devices_qs.filter(status='online')
    elif status == 'offline':
        devices_qs = devices_qs.filter(status='offline')
    elif status == 'patches_pending':
        devices_qs = devices_qs.filter(pending_patches__gt=0)
    elif status == 'patches_updated':
        devices_qs = devices_qs.filter(pending_patches=0)
    # 'all' or '' — no extra filter

    devices_qs = devices_qs.order_by('device_name')

    # Paginate
    paginator = Paginator(devices_qs, 15)
    page_obj = paginator.get_page(page)

    devices_data = []
    for device in page_obj:
        devices_data.append({
            'device_name': device.device_name,
            'status': device.status,
            'organization_name': device.organization_name or '-',
            'site_name': device.site_name or '-',
            'operating_system': device.operating_system or 'N/A',
            'ip_address': device.ip_address or 'N/A',
            'uptime': device.uptime or '-',
            'pending_patches': device.pending_patches or 0,
            'last_updated': device.last_updated.strftime('%Y-%m-%d') if device.last_updated else '-',
        })

    return JsonResponse({
        'devices': devices_data,
        'total': paginator.count,
        'page': page_obj.number,
        'total_pages': paginator.num_pages,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'status': status,
        'company': company_name
    })

@login_required
def company_tickets_api(request):
    """API for paginated tickets in company dashboard.
    Uses IDENTICAL company-matching and date logic as company_dashboard view
    so the modal totals always match the dashboard cards.
    """
    from tickets.local_service import LocalTicketService

    company_name = request.GET.get('company', '').strip()
    status       = request.GET.get('status', 'all').strip()
    page         = int(request.GET.get('page', 1))
    search       = request.GET.get('search', '').strip()
    order        = request.GET.get('order', 'desc')

    # ── Use EXACT same query as company_dashboard view ────────── #
    # date() gives midnight → matches dashboard card counts exactly
    thirty_days_ago = timezone.now() - timedelta(days=30)
    local_service = LocalTicketService()
    qs = local_service.get_tickets_for_reports({
        'company':   company_name,
        'date_from': thirty_days_ago.date(),   # same as dashboard
    })

    # ── Status filter ─────────────────────────────────────────── #
    _KNOWN_STATUSES = ('Open', 'In Progress', 'Pending', 'Resolved', 'Closed', 'Cancelled')
    if status and status.lower() != 'all':
        if status.lower() == 'hold':
            qs = qs.filter(
                models.Q(status__iexact='Onhold') |
                models.Q(status__icontains='On Hold')
            )
        elif status.lower() == 'progress':
            qs = qs.filter(status__icontains='Progress')
        elif status.lower() == 'other':
            # BUG-05 fix: "Other" = everything not covered by the named cards
            qs = qs.exclude(status__iexact='Open') \
                   .exclude(status__icontains='Progress') \
                   .exclude(status__iexact='Pending') \
                   .exclude(status__iexact='Resolved') \
                   .exclude(status__iexact='Closed') \
                   .exclude(status__iexact='Cancelled') \
                   .exclude(models.Q(status__iexact='Onhold') | models.Q(status__icontains='On Hold'))
        else:
            qs = qs.filter(status__iexact=status)

    # ── Search ────────────────────────────────────────────────── #
    if search:
        qs = qs.filter(
            models.Q(ticket_id__icontains=search) |
            models.Q(subject__icontains=search) |
            models.Q(requester_name__icontains=search) |
            models.Q(technician_name__icontains=search)
        )

    qs = qs.order_by('-created_at' if order == 'desc' else 'created_at')

    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(page)

    tickets = []
    for ticket in page_obj:
        tickets.append({
            'ticket_id':       ticket.ticket_id,
            'subject':         ticket.subject[:60] + '…' if len(ticket.subject) > 60 else ticket.subject,
            'status':          ticket.status,
            'priority':        ticket.priority or 'Normal',
            'requester_name':  ticket.requester_name or 'Unknown',
            'technician_name': ticket.technician_name or 'Unassigned',
            'created_at':      ticket.created_at.strftime('%d %b %Y') if ticket.created_at else 'N/A',
        })

    return JsonResponse({
        'tickets':      tickets,
        'total':        paginator.count,
        'page':         page_obj.number,
        'total_pages':  paginator.num_pages,
        'has_next':     page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'status':       status,
        'company':      company_name,
    })

@login_required
def company_mdm_devices_api(request):
    """API for paginated MDM devices from live API (company-scoped)."""
    from mdm.models import MdmCustomer
    from mdm.live_service import fetch_live_devices
    from rbac.utils import find_company_for_name

    company_name = request.GET.get('company', '')
    page         = max(1, int(request.GET.get('page', 1)))
    per_page     = 20
    search       = request.GET.get('search', '').strip().lower()

    # Resolve company → MDM customers
    company_obj = find_company_for_name(company_name) if company_name else None
    if company_obj:
        customers = list(MdmCustomer.objects.filter(company=company_obj))
    else:
        customers = list(MdmCustomer.objects.select_related('company').all())

    all_devices = fetch_live_devices(customers)

    # In-memory search
    if search:
        all_devices = [
            d for d in all_devices
            if search in d['device_name'].lower()
            or search in d['username'].lower()
            or search in d['device_type'].lower()
        ]

    total = len(all_devices)
    start = (page - 1) * per_page
    page_devices = all_devices[start:start + per_page]
    total_pages  = max(1, (total + per_page - 1) // per_page)

    return JsonResponse({
        'devices': [{
            'device_name':  d['device_name'],
            'platform':     d['device_type'].title(),
            'user_name':    d['username'],
            'status':       d['status_display'],
            'model':        d['model'],
            'last_contact': d['last_contact_time'].strftime('%d %b %Y') if d['last_contact_time'] else 'N/A',
        } for d in page_devices],
        'total':        total,
        'page':         page,
        'total_pages':  total_pages,
        'has_next':     page < total_pages,
        'has_previous': page > 1,
    })
