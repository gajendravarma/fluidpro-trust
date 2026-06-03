import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect

from .site24x7_client import (Site24x7Platform, STATUS_UP, STATUS_DOWN,
                               STATUS_LABELS, STATUS_BADGE, MONITOR_TYPE_LABELS)
from .token_manager import TokenManager

# Monitor types that are infrastructure/internal — excluded from user-facing counts
# (matches Site24x7 web dashboard behaviour)
_INFRA_TYPES = {'PROBE', 'POLLER_DASHBOARD'}


def _get_role(request):
    try:
        return request.user.userprofile.get_role()
    except Exception:
        return 'admin'


def _require_tech_or_admin(request):
    if _get_role(request) not in ('admin', 'technician'):
        raise PermissionError('Access denied')


def _count_status(monitors):
    """Count up/down/trouble/other from a list of monitor dicts using monitor-level status."""
    up = down = trouble = other = 0
    for m in monitors:
        code = Site24x7Platform.parse_monitor_status(m)
        if code == STATUS_UP:
            up += 1
        elif code == STATUS_DOWN:
            down += 1
        else:
            trouble += 1
    return up, down, trouble


def _extract_monitors(raw_status):
    """Pull monitors list out of a current_status API response."""
    if 'error_code' in raw_status:
        return None, raw_status.get('message', 'Could not load status.')
    data_block = raw_status.get('data', {})
    if isinstance(data_block, dict):
        return data_block.get('monitors', []), None
    if isinstance(data_block, list):
        return data_block, None
    return [], None


@login_required
def dashboard(request):
    """Site24x7 monitoring dashboard — server-side rendered."""
    try:
        _require_tech_or_admin(request)
    except PermissionError:
        messages.error(request, 'Access denied.')
        return redirect('rbac:user_dashboard')

    role = _get_role(request)
    context = {
        'user_role': role,
        'token_valid': False,
        'customers': [],
        'customer_error': None,
        'monitors': [],
        'monitor_error': None,
        'monitors_up': 0,
        'monitors_down': 0,
        'monitors_trouble': 0,
        'customer_summaries': [],
        'status_labels': STATUS_LABELS,
        'status_badge': STATUS_BADGE,
    }

    try:
        p = Site24x7Platform()

        # Customers
        raw = p.get_customers()
        if 'error_code' in raw:
            context['customer_error'] = raw.get('message', 'Token invalid or expired.')
        else:
            context['token_valid'] = True
            customers = raw.get('data', raw) if isinstance(raw, dict) else raw
            context['customers'] = customers if isinstance(customers, list) else []

        # Customer-wise status: combine /api/monitors (total) + /api/current_status (live status)
        if context['token_valid'] and context['customers']:
            customer_summaries = []
            total_up = total_down = total_trouble = 0

            for cust in context['customers']:
                zaaid = cust.get('zaaid')
                cname = cust.get('name', 'Unknown')
                summary = {
                    'name': cname,
                    'zaaid': zaaid,
                    'up': 0, 'down': 0, 'trouble': 0, 'total': 0,
                    'monitors': [],
                    'error': None,
                }
                try:
                    # 1. Full monitor list for correct total (excludes PROBE/POLLER_DASHBOARD)
                    raw_mon = p.get_monitors(zaaid=zaaid)
                    all_monitors = raw_mon.get('data', []) if isinstance(raw_mon, dict) else []
                    visible = [m for m in all_monitors
                               if m.get('state') == 0 and m.get('type') not in _INFRA_TYPES]

                    # 2. Current status for live Up/Down/Trouble
                    raw_status = p.get_current_status(zaaid=zaaid)
                    status_list, err = _extract_monitors(raw_status)
                    if err:
                        summary['error'] = err

                    # Build monitor_id → current_status entry map
                    status_map = {}
                    if status_list:
                        for s in status_list:
                            mid = s.get('monitor_id')
                            if mid:
                                status_map[mid] = s

                    # Build group_name → status map for SSL/domain fallback
                    # group_name format: "{TYPE}-{domain}"  e.g. "SSL_CERT-example.com"
                    raw_cs_data = raw_status.get('data', {})
                    groups = raw_cs_data.get('monitor_groups', []) if isinstance(raw_cs_data, dict) else []
                    group_status_map = {g.get('group_name', ''): g.get('status', -1) for g in groups}

                    # Merge: annotate each visible monitor with live status
                    merged = []
                    for m in visible:
                        mid = m.get('monitor_id')
                        live = status_map.get(mid)
                        if live:
                            # Use richer current_status data (has locations, last_polled_time)
                            entry = dict(live)
                        else:
                            # Try group fallback for SSL/DomainExpiry monitors
                            # pattern: "{type}-{domain}" e.g. SSL_CERT-datum.jsdelivr.com
                            entry = dict(m)
                            mtype = m.get('type', '')
                            display = m.get('display_name', '')
                            domain = display.split(' - ', 1)[-1] if ' - ' in display else display
                            # Try exact match first, then any group with same type prefix + domain
                            group_key = f'{mtype}-{domain}'
                            group_status = group_status_map.get(group_key)
                            if group_status is None:
                                # Partial: find any group containing the domain
                                for gname, gstatus in group_status_map.items():
                                    if domain in gname:
                                        group_status = gstatus
                                        break
                            entry['status'] = group_status if group_status is not None else -1
                        merged.append(entry)

                    summary['monitors'] = merged
                    summary['total'] = len(merged)

                    # Count by status
                    for m in merged:
                        code = m.get('status', -1)
                        if code == STATUS_UP:
                            summary['up'] += 1
                        elif code == STATUS_DOWN:
                            summary['down'] += 1
                        elif code == -1:
                            pass   # no live data — don't count as trouble
                        else:
                            summary['trouble'] += 1

                except Exception as e:
                    summary['error'] = str(e)

                customer_summaries.append(summary)
                total_up += summary['up']
                total_down += summary['down']
                total_trouble += summary['trouble']

            context['customer_summaries'] = customer_summaries
            context['monitors_up'] = total_up
            context['monitors_down'] = total_down
            context['monitors_trouble'] = total_trouble

        # Monitors table — reuse first customer's merged list from summaries above
        if context['token_valid'] and context['customer_summaries']:
            first = context['customer_summaries'][0]
            context['monitors'] = first['monitors']
            context['monitors_zaaid'] = first['zaaid']
            context['monitors_customer'] = first['name']

    except Exception as e:
        context['customer_error'] = str(e)

    return render(request, 'site24x7/dashboard.html', context)


@login_required
def customer_report(request, zaaid):
    """Availability + outage summary report for a specific customer."""
    try:
        _require_tech_or_admin(request)
    except PermissionError:
        messages.error(request, 'Access denied.')
        return redirect('rbac:user_dashboard')

    period = int(request.GET.get('period', 7))
    p = Site24x7Platform()

    # Resolve customer name
    cust_name = zaaid
    try:
        raw_custs = p.get_customers()
        for c in raw_custs.get('data', []):
            if str(c.get('zaaid')) == str(zaaid):
                cust_name = c.get('name', zaaid)
                break
    except Exception:
        pass

    PERIOD_CHOICES = [(1, 'Today'), (7, '7 Days'), (30, '30 Days'), (90, '90 Days')]
    context = {
        'user_role': _get_role(request),
        'zaaid': zaaid,
        'cust_name': cust_name,
        'period': period,
        'period_choices': PERIOD_CHOICES,
        'summary': None,
        'outages': [],
        'availability_details': [],
        'alert_logs': [],
        'monitor_groups': [],
        'error': None,
        'status_labels': STATUS_LABELS,
        'status_badge': STATUS_BADGE,
    }

    try:
        # Summary report
        raw_report = p.get_summary_report(period=period, zaaid=zaaid)
        if 'error_code' not in raw_report:
            data = raw_report.get('data', {})
            context['summary'] = data.get('summary_details')
            context['outages'] = data.get('outage_details', [])
            context['availability_details'] = data.get('availability_details', [])
            context['report_info'] = data.get('info', {})
        else:
            context['error'] = raw_report.get('message', 'Could not load report.')

        # Alert logs
        raw_alerts = p.get_alert_logs(zaaid=zaaid)
        if 'error_code' not in raw_alerts:
            context['alert_logs'] = raw_alerts.get('data', [])

        # Monitor groups
        raw_groups = p.get_monitor_groups(zaaid=zaaid)
        if 'error_code' not in raw_groups:
            context['monitor_groups'] = raw_groups.get('data', [])

        # Current status for inline monitor list
        raw_status = p.get_current_status(zaaid=zaaid)
        status_list, _ = _extract_monitors(raw_status)
        context['monitors'] = status_list or []

    except Exception as e:
        context['error'] = str(e)

    return render(request, 'site24x7/customer_report.html', context)


@login_required
def api_data(request):
    """JSON API endpoint for JS-driven interactions."""
    try:
        _require_tech_or_admin(request)
    except PermissionError:
        return JsonResponse({'error': 'Access denied'}, status=403)

    data_type = request.GET.get('type', 'customers')
    zaaid = request.GET.get('zaaid')
    platform = Site24x7Platform()

    try:
        if data_type == 'customers':
            data = platform.get_customers()
        elif data_type == 'monitors':
            data = platform.get_monitors(zaaid=zaaid)
        elif data_type == 'current_status':
            data = platform.get_current_status(zaaid=zaaid)
        elif data_type == 'monitor_groups':
            data = platform.get_monitor_groups(zaaid=zaaid)
        elif data_type == 'alert_logs':
            data = platform.get_alert_logs(zaaid=zaaid)
        elif data_type == 'summary_report':
            period = int(request.GET.get('period', 7))
            data = platform.get_summary_report(period=period, zaaid=zaaid)
        elif data_type == 'reports':
            monitor_id = request.GET.get('monitor_id')
            period = request.GET.get('period', 7)
            data = platform.get_monitor_summary(monitor_id, period=int(period), zaaid=zaaid)
        else:
            data = {'error': 'Invalid data type'}
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def customer_monitors(request, customer_id):
    try:
        _require_tech_or_admin(request)
    except PermissionError:
        return JsonResponse({'error': 'Access denied'}, status=403)

    platform = Site24x7Platform()
    try:
        decoded_zaaid = Site24x7Platform.decode_zaaid(customer_id)
        monitors = platform.get_monitors(zaaid=decoded_zaaid)
        return JsonResponse({'monitors': monitors})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def monitor_details(request, monitor_id):
    try:
        _require_tech_or_admin(request)
    except PermissionError:
        return JsonResponse({'error': 'Access denied'}, status=403)

    zaaid = request.GET.get('zaaid')
    platform = Site24x7Platform()
    try:
        details = platform.get_monitor_details(monitor_id, zaaid=zaaid)
        return JsonResponse({'details': details})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def update_token(request):
    """Admin-only: update the Site24x7 access token in the .env file."""
    if _get_role(request) != 'admin':
        messages.error(request, 'Only admins can update API tokens.')
        return redirect('site24x7:site24x7_dashboard')

    if request.method == 'POST':
        new_token = request.POST.get('access_token', '').strip()
        if not new_token:
            messages.error(request, 'Access token cannot be empty.')
            return redirect('site24x7:site24x7_dashboard')

        env_path = '.env'
        try:
            with open(env_path, 'r') as f:
                lines = f.readlines()

            updated = False
            new_lines = []
            for line in lines:
                if line.startswith('SITE24X7_ACCESS_TOKEN='):
                    new_lines.append(f'SITE24X7_ACCESS_TOKEN={new_token}\n')
                    updated = True
                else:
                    new_lines.append(line)

            if not updated:
                new_lines.append(f'SITE24X7_ACCESS_TOKEN={new_token}\n')

            with open(env_path, 'w') as f:
                f.writelines(new_lines)

            settings.SITE24X7_ACCESS_TOKEN = new_token
            messages.success(request, 'Site24x7 access token updated.')
        except Exception as e:
            messages.error(request, f'Failed to update token: {e}')

        return redirect('site24x7:site24x7_dashboard')

    return redirect('site24x7:site24x7_dashboard')


@login_required
def token_status(request):
    """JSON endpoint: check if current token is valid."""
    try:
        _require_tech_or_admin(request)
    except PermissionError:
        return JsonResponse({'valid': False, 'error': 'Access denied'}, status=403)

    p = Site24x7Platform()
    result = p.get_customers()
    if 'error_code' in result:
        return JsonResponse({'valid': False, 'message': result.get('message', 'Token invalid')})
    return JsonResponse({'valid': True, 'message': 'Token is valid'})
