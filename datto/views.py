import csv
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages

from .datto_client import DattoClient

# Only users belonging to this company (by name, case-insensitive) can access Datto.
DATTO_COMPANY_NAME = 'wepsol'


def _get_role(request):
    try:
        return request.user.userprofile.get_role()
    except Exception:
        return 'admin'


def _is_wepsol_user(request):
    """Return True if the user belongs to the Wepsol company or is a superuser."""
    if request.user.is_superuser:
        return True
    try:
        company = request.user.userprofile.company
        return company and company.name.lower() == DATTO_COMPANY_NAME
    except Exception:
        return False


def _require_wepsol_tech_or_admin(request):
    """Raise PermissionError if user is not a Wepsol admin/technician."""
    if not _is_wepsol_user(request):
        raise PermissionError('Datto access is restricted to Wepsol staff only.')
    role = _get_role(request)
    if role not in ('admin', 'technician'):
        raise PermissionError('Access denied — admin or technician role required.')


@login_required
def dashboard(request):
    """Main Datto dashboard — server-side rendered with live data."""
    try:
        _require_wepsol_tech_or_admin(request)
    except PermissionError as e:
        messages.error(request, str(e))
        return redirect('rbac:user_dashboard')

    client = DattoClient()
    context = {
        'user_role': _get_role(request),
        'storage_pools': [],
        'bcdr_devices': [],
        'bcdr_device_error': None,
        'storage_error': None,
    }

    # Storage pool — this endpoint works
    try:
        raw = client.get_dtc_storage_pool()
        pools = raw if isinstance(raw, list) else [raw]
        enriched = []
        for p in pools:
            total = (p.get('availableStorage', 0) or 0) + (p.get('usedStorage', 0) or 0)
            used = p.get('usedStorage', 0) or 0
            pct = round((used / total) * 100, 1) if total else 0
            enriched.append({
                'name': p.get('poolName', 'Default Pool'),
                'available_gb': round(p.get('availableStorage', 0), 2),
                'used_gb': round(used, 2),
                'total_gb': round(total, 2),
                'usage_pct': pct,
            })
        context['storage_pools'] = enriched
    except Exception as e:
        context['storage_error'] = str(e)

    # BCDR devices — may return 0 items if not subscribed
    try:
        raw = client.get_devices()
        devices = raw.get('items', raw) if isinstance(raw, dict) else raw
        context['bcdr_devices'] = devices or []
        context['bcdr_total'] = raw.get('pagination', {}).get('count', len(devices)) if isinstance(raw, dict) else len(devices)
    except Exception as e:
        context['bcdr_device_error'] = str(e)
        context['bcdr_total'] = 0

    # DTC assets — retry once on 500, then surface a clear diagnostic message
    import time as _time
    dtc_loaded = False
    for attempt in range(2):
        try:
            raw = client.get_dtc_assets()
            assets = raw.get('items', raw) if isinstance(raw, dict) else raw
            context['dtc_assets'] = assets or []
            context['dtc_total'] = len(context['dtc_assets'])
            dtc_loaded = True
            break
        except Exception as e:
            err_str = str(e)
            if attempt == 0 and '500' in err_str:
                _time.sleep(1)   # brief pause before retry
                continue
            context['dtc_assets'] = []
            context['dtc_total'] = 0
            # Provide a specific message for the known 500 error on this endpoint
            if '500' in err_str:
                context['dtc_error'] = (
                    'The Datto API returned an internal server error (HTTP 500) for '
                    'the Direct-to-Cloud assets endpoint. This is a known intermittent '
                    'issue on Datto\'s side. Your backup devices are still protected — '
                    'storage usage is shown below. Try refreshing in a few minutes.'
                )
            else:
                context['dtc_error'] = err_str

    return render(request, 'datto/dashboard.html', context)


@login_required
def api_data(request):
    """JSON API for JS-driven data (kept for backward compat)."""
    try:
        _require_wepsol_tech_or_admin(request)
    except PermissionError:
        return JsonResponse({'error': 'Access denied'}, status=403)

    api_type = request.GET.get('type', 'all')
    client = DattoClient()
    data = {}

    if api_type in ['all', 'bcdr_devices']:
        try:
            data['bcdr_devices'] = client.get_devices()
        except Exception as e:
            data['bcdr_devices'] = {'items': [], 'error': str(e)}

    if api_type in ['all', 'bcdr_agents']:
        try:
            data['bcdr_agents'] = client.get_agents()
        except Exception as e:
            data['bcdr_agents'] = {'clients': [], 'error': str(e)}

    if api_type in ['all', 'dtc_assets']:
        try:
            data['dtc_assets'] = client.get_dtc_assets()
        except Exception as e:
            data['dtc_assets'] = {'items': [], 'error': str(e)}

    if api_type in ['all', 'dtc_storage']:
        try:
            storage_data = client.get_dtc_storage_pool()
            data['dtc_storage'] = storage_data if isinstance(storage_data, list) else [storage_data]
        except Exception as e:
            data['dtc_storage'] = {'error': str(e)}

    return JsonResponse(data)


@login_required
def api_diagnostic(request):
    """Raw API status check — shows exactly what Datto returns for each endpoint."""
    try:
        _require_wepsol_tech_or_admin(request)
    except PermissionError:
        return JsonResponse({'error': 'Access denied'}, status=403)

    import time as _time
    client = DattoClient()
    results = {}
    endpoints = {
        'bcdr_device':  client.get_devices,
        'bcdr_agent':   client.get_agents,
        'dtc_assets':   client.get_dtc_assets,
        'dtc_storage':  client.get_dtc_storage_pool,
    }
    for name, fn in endpoints.items():
        t0 = _time.time()
        try:
            data = fn()
            results[name] = {
                'status': 'ok',
                'response_ms': round((_time.time() - t0) * 1000),
                'data': data,
            }
        except Exception as e:
            results[name] = {
                'status': 'error',
                'response_ms': round((_time.time() - t0) * 1000),
                'error': str(e),
            }
    return JsonResponse(results, json_dumps_params={'indent': 2})


@login_required
def dtc_client_assets(request, client_id):
    try:
        _require_wepsol_tech_or_admin(request)
    except PermissionError:
        return JsonResponse({'error': 'Access denied'}, status=403)

    client = DattoClient()
    try:
        data = client.get_dtc_client_assets(client_id)
        return JsonResponse({'assets': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def download_storage_report(request):
    """CSV download of Datto storage pool data."""
    try:
        _require_wepsol_tech_or_admin(request)
    except PermissionError as e:
        messages.error(request, str(e))
        return redirect('rbac:user_dashboard')

    client = DattoClient()
    try:
        raw = client.get_dtc_storage_pool()
        pools = raw if isinstance(raw, list) else [raw]
    except Exception as e:
        messages.error(request, f'Failed to fetch storage data: {e}')
        return redirect('datto:datto_dashboard')

    ts = datetime.now().strftime('%Y%m%d_%H%M')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="datto_storage_report_{ts}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Pool Name', 'Used (GB)', 'Available (GB)', 'Total (GB)', 'Usage %'])
    for p in pools:
        used = round(p.get('usedStorage', 0) or 0, 2)
        avail = round(p.get('availableStorage', 0) or 0, 2)
        total = round(used + avail, 2)
        pct = round((used / total) * 100, 1) if total else 0
        writer.writerow([p.get('poolName', 'Unknown'), used, avail, total, pct])
    return response


@login_required
def download_device_report(request):
    """CSV download of BCDR device list."""
    try:
        _require_wepsol_tech_or_admin(request)
    except PermissionError as e:
        messages.error(request, str(e))
        return redirect('rbac:user_dashboard')

    client = DattoClient()
    try:
        raw = client.get_devices()
        devices = raw.get('items', raw) if isinstance(raw, dict) else (raw or [])
    except Exception as e:
        messages.error(request, f'Failed to fetch device data: {e}')
        return redirect('datto:datto_dashboard')

    ts = datetime.now().strftime('%Y%m%d_%H%M')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="datto_devices_{ts}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Serial Number', 'Model', 'Status', 'Internal IP', 'Last Seen'])
    for d in devices:
        writer.writerow([
            d.get('name') or d.get('hostname', ''),
            d.get('serialNumber', ''),
            d.get('model') or d.get('smbiosName', ''),
            'Online' if (d.get('online') or d.get('status') == 'paired') else 'Offline',
            d.get('internalIpAddress', ''),
            d.get('lastSeenDate', ''),
        ])
    return response
