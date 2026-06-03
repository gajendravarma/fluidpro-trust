"""
Extra views appended to site24x7/views.py — imported there.
These are defined here separately and then appended via import.
"""
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .site24x7_client import Site24x7Platform, MONITOR_TYPE_LABELS
from .views import _get_role, _require_tech_or_admin, _INFRA_TYPES


def _resolve_customer(p, zaaid):
    try:
        for c in p.get_customers().get('data', []):
            if str(c.get('zaaid')) == str(zaaid):
                return c.get('name', zaaid)
    except Exception:
        pass
    return zaaid


def _base_ctx(request, zaaid, p=None):
    if p is None:
        p = Site24x7Platform()
    return {
        'user_role': _get_role(request),
        'zaaid': zaaid,
        'cust_name': _resolve_customer(p, zaaid),
        'type_labels': MONITOR_TYPE_LABELS,
    }


@login_required
def monitor_list(request, zaaid):
    try:
        _require_tech_or_admin(request)
    except PermissionError:
        messages.error(request, 'Access denied.')
        return redirect('rbac:user_dashboard')

    p = Site24x7Platform()
    ctx = _base_ctx(request, zaaid, p)
    ctx.update({'monitors': [], 'error': None})

    try:
        raw = p.get_monitors(zaaid=zaaid)
        all_monitors = raw.get('data', []) if isinstance(raw, dict) else []

        raw_cs = p.get_current_status(zaaid=zaaid)
        cs_data = raw_cs.get('data', {})
        cs_list = cs_data.get('monitors', []) if isinstance(cs_data, dict) else []
        groups = cs_data.get('monitor_groups', []) if isinstance(cs_data, dict) else []
        status_map = {m['monitor_id']: m.get('status', -1) for m in cs_list if m.get('monitor_id')}
        group_map = {g.get('group_name', ''): g.get('status', -1) for g in groups}

        for m in all_monitors:
            mid = m.get('monitor_id')
            code = status_map.get(mid)
            if code is None:
                mtype = m.get('type', '')
                domain = m.get('display_name', '').split(' - ', 1)[-1]
                code = group_map.get(f'{mtype}-{domain}')
                if code is None:
                    code = next((v for k, v in group_map.items() if domain in k), -1)
            m['live_status'] = code if code is not None else -1
            m['type_label'] = MONITOR_TYPE_LABELS.get(m.get('type', ''), m.get('type', ''))
            # Pre-compute host/url so the template never accesses a missing key
            m['host_display'] = (
                m.get('website') or m.get('hostname') or m.get('domain_name')
                or m.get('host_name') or m.get('ip_address') or m.get('ipaddress') or '—'
            )

        ctx['monitors'] = all_monitors
    except Exception as e:
        ctx['error'] = str(e)

    return render(request, 'site24x7/monitor_list.html', ctx)


@login_required
def monitor_detail(request, zaaid, monitor_id):
    try:
        _require_tech_or_admin(request)
    except PermissionError:
        messages.error(request, 'Access denied.')
        return redirect('rbac:user_dashboard')

    p = Site24x7Platform()
    ctx = _base_ctx(request, zaaid, p)
    ctx.update({'monitor': None, 'live': None, 'live_status': -1,
                'report': None, 'outages': [], 'error': None, 'monitor_id': monitor_id})

    try:
        raw = p.get_monitor_details(monitor_id, zaaid=zaaid)
        monitor = raw.get('data', {})
        ctx['monitor'] = monitor
        ctx['type_label'] = MONITOR_TYPE_LABELS.get(monitor.get('type', ''), monitor.get('type', ''))

        raw_cs = p.get_current_status(zaaid=zaaid)
        cs_data = raw_cs.get('data', {})
        cs_list = cs_data.get('monitors', []) if isinstance(cs_data, dict) else []
        live = next((m for m in cs_list if m.get('monitor_id') == monitor_id), None)
        ctx['live'] = live
        ctx['live_status'] = live.get('status', -1) if live else -1

        raw_rep = p.get_monitor_summary(monitor_id, period=7, zaaid=zaaid)
        if 'error_code' not in raw_rep:
            rep_data = raw_rep.get('data', {})
            ctx['report'] = rep_data.get('summary_details')
            outage_detail = rep_data.get('outage_details', [])
            ctx['outages'] = outage_detail[0].get('outages', []) if outage_detail else []
    except Exception as e:
        ctx['error'] = str(e)

    return render(request, 'site24x7/monitor_detail.html', ctx)


@login_required
def monitor_create(request, zaaid):
    try:
        _require_tech_or_admin(request)
    except PermissionError:
        messages.error(request, 'Access denied.')
        return redirect('rbac:user_dashboard')

    p = Site24x7Platform()
    ctx = _base_ctx(request, zaaid, p)
    ctx.update({'api_error': None, 'form_data': {}, 'editing': False,
                'monitor_types': ['URL', 'ISP', 'SSL_CERT', 'DOMAINEXPIRY']})
    ctx['location_profiles']     = p.get_location_profiles(zaaid=zaaid).get('data', [])
    ctx['notification_profiles'] = p.get_notification_profiles(zaaid=zaaid).get('data', [])
    ctx['threshold_profiles']    = p.get_threshold_profiles(zaaid=zaaid).get('data', [])
    ctx['user_groups']           = p.get_user_groups(zaaid=zaaid).get('data', [])

    if request.method == 'POST':
        mtype = request.POST.get('type', 'URL')
        form_data = {
            'type': mtype,
            'display_name': request.POST.get('display_name', '').strip(),
            'check_frequency': request.POST.get('check_frequency', '5'),
            'timeout': int(request.POST.get('timeout', 15)),
            'location_profile_id': request.POST.get('location_profile_id', ''),
            'notification_profile_id': request.POST.get('notification_profile_id', ''),
            'threshold_profile_id': request.POST.get('threshold_profile_id', ''),
            'user_group_ids': request.POST.getlist('user_group_ids'),
        }
        if mtype == 'URL':
            form_data.update({
                'website': request.POST.get('website', '').strip(),
                'http_method': request.POST.get('http_method', 'G'),
                'http_protocol': request.POST.get('http_protocol', 'H1.1'),
                'ssl_protocol': 'Auto',
                'follow_redirect': True,
                'ignore_cert_err': request.POST.get('ignore_cert_err') == 'on',
            })
        elif mtype == 'ISP':
            form_data.update({
                'hostname': request.POST.get('hostname', '').strip(),
                'protocol': request.POST.get('protocol', '1'),
                'port': int(request.POST.get('port', 443)),
            })
        elif mtype == 'SSL_CERT':
            form_data.update({
                'domain_name': request.POST.get('domain_name', '').strip(),
                'protocol': 'HTTPS', 'port': '443',
                'expire_days': int(request.POST.get('expire_days', 30)),
            })
        elif mtype == 'DOMAINEXPIRY':
            form_data.update({
                'host_name': request.POST.get('host_name', '').strip(),
                'expire_days': int(request.POST.get('expire_days', 30)),
            })

        ctx['form_data'] = form_data
        result = p.create_monitor(form_data, zaaid=zaaid)

        if result.get('code') == 0:
            messages.success(request, f'Monitor "{form_data["display_name"]}" created.')
            return redirect('site24x7:monitor_list', zaaid=zaaid)
        else:
            ctx['api_error'] = re.sub(r'<[^>]+>', '', result.get('message', 'Unknown error'))

    return render(request, 'site24x7/monitor_form.html', ctx)


@login_required
def monitor_edit(request, zaaid, monitor_id):
    try:
        _require_tech_or_admin(request)
    except PermissionError:
        messages.error(request, 'Access denied.')
        return redirect('rbac:user_dashboard')

    p = Site24x7Platform()
    ctx = _base_ctx(request, zaaid, p)
    ctx.update({'api_error': None, 'monitor_id': monitor_id, 'editing': True,
                'monitor_types': ['URL', 'ISP', 'SSL_CERT', 'DOMAINEXPIRY', 'NETWORKDEVICE']})
    ctx['location_profiles']     = p.get_location_profiles(zaaid=zaaid).get('data', [])
    ctx['notification_profiles'] = p.get_notification_profiles(zaaid=zaaid).get('data', [])
    ctx['threshold_profiles']    = p.get_threshold_profiles(zaaid=zaaid).get('data', [])
    ctx['user_groups']           = p.get_user_groups(zaaid=zaaid).get('data', [])

    existing = p.get_monitor_details(monitor_id, zaaid=zaaid).get('data', {})
    ctx['form_data'] = existing

    if request.method == 'POST':
        form_data = dict(existing)
        for field in ('display_name', 'check_frequency', 'location_profile_id',
                      'notification_profile_id', 'threshold_profile_id',
                      'website', 'hostname', 'domain_name', 'host_name', 'http_method', 'protocol'):
            if field in request.POST:
                form_data[field] = request.POST.get(field, '').strip()
        if 'timeout' in request.POST:
            form_data['timeout'] = int(request.POST.get('timeout', 15))
        if request.POST.get('port'):
            form_data['port'] = int(request.POST.get('port'))
        if request.POST.getlist('user_group_ids'):
            form_data['user_group_ids'] = request.POST.getlist('user_group_ids')

        ctx['form_data'] = form_data
        result = p.update_monitor(monitor_id, form_data, zaaid=zaaid)

        if result.get('code') == 0:
            messages.success(request, 'Monitor updated.')
            return redirect('site24x7:monitor_detail', zaaid=zaaid, monitor_id=monitor_id)
        else:
            msg = re.sub(r'<[^>]+>', '', result.get('message', 'Unknown error'))
            ctx['api_error'] = f'{msg} (error {result.get("error_code", "")})'

    return render(request, 'site24x7/monitor_form.html', ctx)


@login_required
def monitor_delete(request, zaaid, monitor_id):
    if _get_role(request) != 'admin':
        messages.error(request, 'Only admins can delete monitors.')
        return redirect('site24x7:monitor_list', zaaid=zaaid)

    if request.method == 'POST':
        p = Site24x7Platform()
        result = p.delete_monitor(monitor_id, zaaid=zaaid)
        if result.get('code') == 0:
            name = result.get('data', {}).get('resource_name', monitor_id)
            messages.success(request, f'Monitor "{name}" deleted.')
        else:
            msg = re.sub(r'<[^>]+>', '', result.get('message', 'Delete failed'))
            messages.error(request, msg)

    return redirect('site24x7:monitor_list', zaaid=zaaid)


@login_required
def maintenance_view(request, zaaid):
    try:
        _require_tech_or_admin(request)
    except PermissionError:
        messages.error(request, 'Access denied.')
        return redirect('rbac:user_dashboard')

    p = Site24x7Platform()
    ctx = _base_ctx(request, zaaid, p)
    ctx.update({'windows': [], 'monitors': [], 'error': None})

    if request.method == 'POST':
        action = request.POST.get('action', 'create')
        if action == 'delete' and _get_role(request) == 'admin':
            result = p.delete_maintenance(request.POST.get('maintenance_id'), zaaid=zaaid)
            if result.get('code') == 0:
                messages.success(request, 'Maintenance window deleted.')
            else:
                messages.error(request, result.get('message', 'Delete failed'))
        elif action == 'create':
            monitor_ids = request.POST.getlist('monitor_ids')
            payload = {
                'display_name': request.POST.get('display_name', '').strip(),
                'description': request.POST.get('description', '').strip(),
                'maintenance_type': int(request.POST.get('maintenance_type', 1)),
                'start_date': request.POST.get('start_date', ''),
                'end_date': request.POST.get('end_date', ''),
                'start_time': request.POST.get('start_time', ''),
                'end_time': request.POST.get('end_time', ''),
                'resource_type': 1,
                'monitors': [{'monitor_id': mid} for mid in monitor_ids],
            }
            result = p.create_maintenance(payload, zaaid=zaaid)
            if result.get('code') == 0:
                messages.success(request, 'Maintenance window created.')
            else:
                msg = re.sub(r'<[^>]+>', '', result.get('message', 'Create failed'))
                messages.error(request, msg)
        return redirect('site24x7:maintenance', zaaid=zaaid)

    try:
        ctx['windows'] = p.get_maintenance(zaaid=zaaid).get('data', [])
        all_mon = p.get_monitors(zaaid=zaaid).get('data', [])
        ctx['monitors'] = [m for m in all_mon
                           if m.get('state') == 0 and m.get('type') not in _INFRA_TYPES]
    except Exception as e:
        ctx['error'] = str(e)

    return render(request, 'site24x7/maintenance.html', ctx)


@login_required
def profiles_view(request, zaaid):
    try:
        _require_tech_or_admin(request)
    except PermissionError:
        messages.error(request, 'Access denied.')
        return redirect('rbac:user_dashboard')

    p = Site24x7Platform()
    ctx = _base_ctx(request, zaaid, p)
    ctx['error'] = None

    try:
        ctx['location_profiles']     = p.get_location_profiles(zaaid=zaaid).get('data', [])
        ctx['notification_profiles'] = p.get_notification_profiles(zaaid=zaaid).get('data', [])
        ctx['threshold_profiles']    = p.get_threshold_profiles(zaaid=zaaid).get('data', [])
        ctx['user_groups']           = p.get_user_groups(zaaid=zaaid).get('data', [])
        ctx['tags']                  = p.get_tags(zaaid=zaaid).get('data', [])
        ctx['monitor_groups']        = p.get_monitor_groups(zaaid=zaaid).get('data', [])
    except Exception as e:
        ctx['error'] = str(e)

    return render(request, 'site24x7/profiles.html', ctx)
