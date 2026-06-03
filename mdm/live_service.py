"""
mdm/live_service.py
Shared helpers for fetching live MDM device data from the ManageEngine API.
Import from here instead of from mdm.views to avoid circular imports.
"""
import datetime
import logging
from .manageengine_mdm_service import ManageEngineMDMService, MANAGED_STATUS_MAP

logger = logging.getLogger(__name__)

_STATUS_DISPLAY = {
    'managed':            'Active',
    'active':             'Active',
    'staged':             'Staged',
    'enrollment_pending': 'Pending',
    'retired':            'Retired',
}


def _epoch_ms(value):
    try:
        if value:
            return datetime.datetime.fromtimestamp(int(value) / 1000)
    except Exception:
        pass
    return None


def normalize_device(raw: dict, mdm_customer=None) -> dict:
    """Convert a raw ManageEngine API device dict to a flat display dict."""
    user_obj = raw.get('user') or {}
    platform = raw.get('platform_type', '').lower()
    if not platform:
        pid = str(raw.get('platform_type_id', ''))
        platform = {'1': 'ios', '2': 'android', '3': 'windows'}.get(pid, 'unknown')

    _internal = MANAGED_STATUS_MAP.get(str(raw.get('managed_status', '2')), 'managed')
    status = 'active' if _internal in ('managed', 'active') else _internal
    status_display = _STATUS_DISPLAY.get(_internal, _internal.replace('_', ' ').title())

    try:
        storage_gb = round(float(raw.get('device_capacity') or 0), 1)
    except (ValueError, TypeError):
        storage_gb = 0.0

    company_name = raw.get('customer_name') or (
        mdm_customer.company.name if mdm_customer else '')

    return {
        'id':               raw.get('device_id', ''),
        'device_id':        raw.get('device_id', ''),
        'device_name':      raw.get('device_name', 'Unknown'),
        'device_type':      platform,
        'status':           status,
        'status_display':   status_display,
        'model':            raw.get('model', ''),
        'manufacturer':     raw.get('product_name', ''),
        'os_version':       raw.get('os_version', ''),
        'serial_number':    raw.get('serial_number') or raw.get('udid', ''),
        'imei':             raw.get('imei', ''),
        'wifi_mac':         raw.get('wifi_mac', ''),
        'username':         user_obj.get('user_name', ''),
        'user_email':       user_obj.get('user_email', ''),
        'display_name':     user_obj.get('user_name', ''),
        'last_contact_time': _epoch_ms(raw.get('last_contact_time')),
        'last_seen':         _epoch_ms(raw.get('last_contact_time')),
        'is_supervised':    str(raw.get('is_supervised', 'false')).lower() == 'true',
        'is_encrypted':     str(raw.get('is_encrypted', 'false')).lower() == 'true',
        'storage_gb':       storage_gb,
        'enrolled_at':      None,
        'mdm_customer':     mdm_customer,
        'customer_name':    company_name,
        'customer_id_str':  str(raw.get('customer_id',
                               mdm_customer.customer_id if mdm_customer else '')),
    }


def fetch_live_devices(customers) -> list:
    """
    Fetch live devices for a list of MdmCustomer objects.
    Returns a list of normalized dicts sorted by device_name.
    """
    svc = ManageEngineMDMService()
    results = []
    for customer in customers:
        try:
            raw_list, _ = svc.get_devices(customer_id=customer.customer_id)
            for d in (raw_list or []):
                if str(d.get('is_removed', 'false')).lower() == 'true':
                    continue
                results.append(normalize_device(d, customer))
        except Exception as exc:
            logger.error('MDM live fetch error for customer %s: %s',
                         customer.customer_id, exc)
    results.sort(key=lambda d: d['device_name'].lower())
    return results


def get_mdm_stats(customers) -> dict:
    """
    Fetch live devices and return aggregate stats dict.
    Keys: total, active, pending, retired, devices (full list)
    """
    devices = fetch_live_devices(customers)
    return {
        'total':   len(devices),
        'active':  sum(1 for d in devices if d['status'] == 'active'),
        'pending': sum(1 for d in devices if d['status'] in ('enrollment_pending', 'staged')),
        'retired': sum(1 for d in devices if d['status'] == 'retired'),
        'devices': devices,
    }


def get_customers_for_company(company_obj):
    """Return list of MdmCustomer objects for a given Company instance."""
    from .models import MdmCustomer
    return list(MdmCustomer.objects.filter(company=company_obj).select_related('company'))


def get_all_customers():
    """Return all MdmCustomer objects."""
    from .models import MdmCustomer
    return list(MdmCustomer.objects.select_related('company').all())
