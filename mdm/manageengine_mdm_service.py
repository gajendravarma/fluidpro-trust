"""
ManageEngine MDM API Service — On-Premises
==========================================
Real endpoint  : https://mdm.wepsol.com:9041
Auth header    : Authorization: <api-key>
Customer header: X-Customer: <customer_id>   (601, 301, etc.)

Actual device response fields (from live API):
  device_id          string   "2138"
  device_name        string   "DIGI-PUN-L045"
  platform_type      string   "android" | "ios" | "windows"
  platform_type_id   string   "1"=iOS "2"=Android "3"=Windows
  device_type        string   "3"
  product_name       string   "Dell Inc."      → manufacturer
  model              string   "Latitude 3450"
  os_version         string   "11.0.26200.7462"
  serial_number      string   "9JBCB94"
  udid               string   "1E19051C..."    → fallback for serial
  wifi_mac           string   "00-00-00-00-00-00"
  imei               string   (mobile only)
  last_contact_time  string   epoch-ms "1775063235229"
  is_supervised      bool     false
  is_lost_mode_enabled bool   false
  is_removed         string   "true" | "false"
  managed_status     string   "2"=active "10"/"11"=retired
  owned_by           string   "1"
  device_capacity    string   "473.98242"  GB → storage_total (bytes)
  customer_id        string   "601"
  customer_name      string   "Digtinctive"
  user               object   {user_name, user_id, user_email}
  delta-token        string   for incremental sync (top-level response key)
"""

import requests
import logging
import datetime
from django.conf import settings
from django.utils import timezone

urllib3_imported = False
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    urllib3_imported = True
except ImportError:
    pass

logger = logging.getLogger(__name__)

MDM_BASE = getattr(settings, 'MDM_API_BASE_URL', 'https://mdm.wepsol.com:9041').rstrip('/')
MDM_KEY  = getattr(settings, 'MDM_API_KEY', '')

# managed_status → Device.status mapping
MANAGED_STATUS_MAP = {
    '1':  'enrollment_pending',
    '2':  'managed',
    '3':  'staged',
    '4':  'active',
    '10': 'retired',
    '11': 'retired',
}


class ManageEngineMDMService:
    """
    Client for the ManageEngine MDM On-Premises REST API.
    X-Customer header is set per-request so one service instance
    can query multiple customers.
    """

    def __init__(self):
        self.base_url = MDM_BASE
        self.api_key  = MDM_KEY
        self.timeout  = 20

    def _headers(self, customer_id=None):
        h = {
            'Authorization': self.api_key,
            'Content-Type':  'application/json',
        }
        if customer_id:
            h['X-Customer'] = str(customer_id)
        return h

    # ──────────────────────────────────────────────────────────────
    # Internal HTTP helpers
    # ──────────────────────────────────────────────────────────────

    def _get(self, path, params=None, customer_id=None):
        url = f"{self.base_url}{path}"
        try:
            resp = requests.get(
                url,
                headers=self._headers(customer_id),
                params=params,
                timeout=self.timeout,
                verify=False,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            logger.error("MDM API connection error: %s", url)
        except requests.exceptions.Timeout:
            logger.error("MDM API timeout: %s", url)
        except requests.exceptions.HTTPError as exc:
            logger.error("MDM API HTTP %s: %s", exc.response.status_code, url)
        except Exception as exc:
            logger.error("MDM API error (%s): %s", url, exc)
        return None

    def _post(self, path, data=None, customer_id=None):
        url = f"{self.base_url}{path}"
        try:
            resp = requests.post(
                url,
                headers=self._headers(customer_id),
                json=data or {},
                timeout=self.timeout,
                verify=False,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            logger.error("MDM API connection error: %s", url)
        except requests.exceptions.Timeout:
            logger.error("MDM API timeout: %s", url)
        except requests.exceptions.HTTPError as exc:
            logger.error("MDM API HTTP %s: %s", exc.response.status_code, url)
        except Exception as exc:
            logger.error("MDM API error (%s): %s", url, exc)
        return None

    def _delete(self, path, data=None, customer_id=None):
        url = f"{self.base_url}{path}"
        try:
            resp = requests.delete(
                url,
                headers=self._headers(customer_id),
                json=data or {},
                timeout=self.timeout,
                verify=False,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError:
            logger.error("MDM API connection error: %s", url)
        except requests.exceptions.Timeout:
            logger.error("MDM API timeout: %s", url)
        except requests.exceptions.HTTPError as exc:
            logger.error("MDM API HTTP %s: %s", exc.response.status_code, url)
        except Exception as exc:
            logger.error("MDM API error (%s): %s", url, exc)
        return None

    # ──────────────────────────────────────────────────────────────
    # Devices   GET /api/v1/mdm/devices
    #
    # Response: {"devices": [...], "delta-token": "..."}
    # Each device has all fields listed at top of this file.
    # ──────────────────────────────────────────────────────────────

    def get_devices(self, customer_id=None, delta_token=None):
        """
        GET /api/v1/mdm/devices
        Returns (devices_list, delta_token_string).
        Pass delta_token from previous call for incremental sync.
        """
        params = {}
        if delta_token:
            params['delta-token'] = delta_token

        data = self._get('/api/v1/mdm/devices', params=params,
                         customer_id=customer_id)
        if data is None:
            return [], None

        devices     = data.get('devices', [])
        next_token  = data.get('delta-token')
        return devices, next_token

    def get_device(self, device_id, customer_id=None):
        """GET /api/v1/mdm/devices/{device_id}"""
        data = self._get(f'/api/v1/mdm/devices/{device_id}',
                         customer_id=customer_id)
        if data is None:
            return None
        # Response may be {"device": {...}} or the dict directly
        return data.get('device', data) if isinstance(data, dict) else None

    # ──────────────────────────────────────────────────────────────
    # Device remote actions
    # POST /api/v1/mdm/devices/{device_id}/actions/{action_name}
    # ──────────────────────────────────────────────────────────────

    def execute_action(self, device_id, action_name, payload=None, customer_id=None):
        return self._post(
            f'/api/v1/mdm/devices/{device_id}/actions/{action_name}',
            data=payload or {},
            customer_id=customer_id,
        )

    def lock_device(self, device_id, customer_id=None, message=None):
        return self.execute_action(device_id, 'lock',
                                   {'message': message} if message else {},
                                   customer_id=customer_id)

    def wipe_device(self, device_id, customer_id=None):
        return self.execute_action(device_id, 'wipe', customer_id=customer_id)

    def restart_device(self, device_id, customer_id=None):
        return self.execute_action(device_id, 'restart', customer_id=customer_id)

    def locate_device(self, device_id, customer_id=None):
        return self.execute_action(device_id, 'updateLocation', customer_id=customer_id)

    def ring_device(self, device_id, customer_id=None):
        return self.execute_action(device_id, 'ring', customer_id=customer_id)

    def clear_passcode(self, device_id, customer_id=None):
        return self.execute_action(device_id, 'clearPasscode', customer_id=customer_id)

    def get_command_history(self, device_id, customer_id=None):
        """GET /api/v1/mdm/devices/{device_id}/commandhistory"""
        data = self._get(f'/api/v1/mdm/devices/{device_id}/commandhistory',
                         customer_id=customer_id)
        if data is None:
            return []
        return data if isinstance(data, list) else \
               data.get('commandHistory', data.get('commands', []))

    # ──────────────────────────────────────────────────────────────
    # Location
    # ──────────────────────────────────────────────────────────────

    def get_device_location(self, device_id, customer_id=None):
        """GET /api/v1/mdm/devices/{device_id}/locations"""
        data = self._get(f'/api/v1/mdm/devices/{device_id}/locations',
                         customer_id=customer_id)
        if data is None:
            return None
        return data.get('location', data) if isinstance(data, dict) else None

    def get_device_location_with_address(self, device_id, customer_id=None):
        """GET /api/v1/mdm/devices/{device_id}/locations_with_address"""
        return self._get(f'/api/v1/mdm/devices/{device_id}/locations_with_address',
                         customer_id=customer_id)

    # ──────────────────────────────────────────────────────────────
    # Apps   GET /api/v1/mdm/apps
    # ──────────────────────────────────────────────────────────────

    def get_all_apps(self, customer_id=None):
        """GET /api/v1/mdm/apps — full app repository"""
        data = self._get('/api/v1/mdm/apps', customer_id=customer_id)
        if data is None:
            return []
        return data if isinstance(data, list) else data.get('apps', [])

    def get_device_apps(self, device_id, customer_id=None):
        """GET /api/v1/mdm/devices/{device_id}/apps"""
        data = self._get(f'/api/v1/mdm/devices/{device_id}/apps',
                         customer_id=customer_id)
        if data is None:
            return []
        return data if isinstance(data, list) else data.get('apps', [])

    def refresh_app_status(self, device_id, customer_id=None):
        """POST /api/v1/mdm/devices/{device_id}/apps/refreshstatus"""
        return self._post(f'/api/v1/mdm/devices/{device_id}/apps/refreshstatus',
                          customer_id=customer_id)

    # ──────────────────────────────────────────────────────────────
    # Blacklist   GET /api/v1/mdm/blacklist/apps
    # ──────────────────────────────────────────────────────────────

    def get_blacklist_apps(self, customer_id=None):
        """GET /api/v1/mdm/blacklist/apps  (scope: MDMOnDemand.MDMDeviceMgmt.GET)"""
        data = self._get('/api/v1/mdm/blacklist/apps', customer_id=customer_id)
        if data is None:
            return []
        return data if isinstance(data, list) else \
               data.get('blacklist_apps', data.get('apps', []))

    def add_app_to_blacklist(self, app_group_id, customer_id=None):
        """POST /api/v1/mdm/blacklist/apps"""
        return self._post('/api/v1/mdm/blacklist/apps',
                          data={'app_group_id': app_group_id},
                          customer_id=customer_id)

    def remove_app_from_blacklist(self, app_group_id, customer_id=None):
        """DELETE /api/v1/mdm/blacklist/apps/{appgroupid}"""
        return self._delete(f'/api/v1/mdm/blacklist/apps/{app_group_id}',
                            customer_id=customer_id)

    # ──────────────────────────────────────────────────────────────
    # Profiles   GET /api/v1/mdm/profiles
    # ──────────────────────────────────────────────────────────────

    def get_all_profiles(self, customer_id=None):
        """GET /api/v1/mdm/profiles  (scope: MDMOnDemand.MDMDeviceMgmt.READ)"""
        data = self._get('/api/v1/mdm/profiles', customer_id=customer_id)
        if data is None:
            return []
        return data if isinstance(data, list) else data.get('profiles', [])

    def get_device_profiles(self, device_id, customer_id=None):
        """GET /api/v1/mdm/devices/{device_id}/profiles"""
        data = self._get(f'/api/v1/mdm/devices/{device_id}/profiles',
                         customer_id=customer_id)
        if data is None:
            return []
        return data if isinstance(data, list) else data.get('profiles', [])

    # ──────────────────────────────────────────────────────────────
    # Groups
    # ──────────────────────────────────────────────────────────────

    def get_all_groups(self, customer_id=None):
        """GET /api/v1/mdm/groups"""
        data = self._get('/api/v1/mdm/groups', customer_id=customer_id)
        if data is None:
            return []
        return data if isinstance(data, list) else data.get('groups', [])

    # ──────────────────────────────────────────────────────────────
    # Users
    # ──────────────────────────────────────────────────────────────

    def get_all_users(self, customer_id=None):
        """GET /api/v1/mdm/users"""
        data = self._get('/api/v1/mdm/users', customer_id=customer_id)
        if data is None:
            return []
        return data if isinstance(data, list) else data.get('users', [])

    # ──────────────────────────────────────────────────────────────
    # Sync — pull real API data into local Device model
    #
    # Field mapping from live API response:
    #   API field             → Device model field
    #   device_id             → device_id  (CharField, keep as str)
    #   device_name           → device_name
    #   platform_type         → device_type + platform
    #   product_name          → manufacturer
    #   model                 → model
    #   os_version            → os_version
    #   serial_number         → serial_number (fallback: udid)
    #   udid                  → imei field (unique device identifier)
    #   wifi_mac              → phone_number field (reused for MAC)
    #   last_contact_time     → last_contact_time + last_seen (epoch ms str)
    #   is_supervised         → is_supervised
    #   is_removed            → skip device if "true"
    #   managed_status        → status  (see MANAGED_STATUS_MAP above)
    #   device_capacity (GB)  → storage_total (bytes)
    #   user.user_name        → username
    #   user.user_email       → user_email
    #   user.user_id          → display_name (stored as ref)
    #   customer_id           → mdm_customer (matched by customer_id)
    # ──────────────────────────────────────────────────────────────

    def sync_devices_for_customer(self, mdm_customer):
        """
        Pull all devices for a customer from ManageEngine MDM API
        and upsert into the local Device model.
        Uses X-Customer: {mdm_customer.customer_id} header.
        Returns (created_count, updated_count, skipped_count).
        """
        from .models import Device

        raw_devices, delta_token = self.get_devices(
            customer_id=mdm_customer.customer_id
        )
        if not raw_devices:
            return 0, 0, 0

        created = updated = skipped = 0

        for d in raw_devices:
            # Skip devices that have been removed from MDM
            if str(d.get('is_removed', 'false')).lower() == 'true':
                skipped += 1
                continue

            device_id = str(d.get('device_id', '') or '')
            if not device_id:
                skipped += 1
                continue

            user_obj = d.get('user') or {}

            # device_capacity is total storage in GB (string)
            storage_total_bytes = _gb_str_to_bytes(d.get('device_capacity'))

            defaults = {
                'mdm_customer':      mdm_customer,
                'device_name':       d.get('device_name', 'Unknown Device'),
                'device_type':       _map_platform_type(d.get('platform_type', ''),
                                                        d.get('platform_type_id', '')),
                'platform':          d.get('platform_type', ''),
                'model':             d.get('model', ''),
                'manufacturer':      d.get('product_name', ''),
                'os_version':        d.get('os_version', ''),
                # serial_number from API, fall back to udid if blank
                'serial_number':     d.get('serial_number') or d.get('udid', ''),
                # udid stored in imei field as unique device identifier
                'imei':              d.get('udid', ''),
                # wifi_mac reused in phone_number (no dedicated field)
                'phone_number':      d.get('wifi_mac', ''),
                'status':            MANAGED_STATUS_MAP.get(
                                         str(d.get('managed_status', '2')), 'managed'),
                'is_supervised':     bool(d.get('is_supervised', False)),
                'is_encrypted':      bool(d.get('is_encrypted', False)),
                'storage_total':     storage_total_bytes,
                'username':          user_obj.get('user_name', ''),
                'user_email':        user_obj.get('user_email', ''),
                'display_name':      user_obj.get('user_name', ''),
                'last_contact_time': _epoch_ms_to_dt(d.get('last_contact_time')),
                'last_seen':         _epoch_ms_to_dt(d.get('last_contact_time')),
            }

            device_obj, was_created = Device.objects.update_or_create(
                device_id=device_id,
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1

            # Fetch per-device apps and profiles counts
            try:
                apps_list = self.get_device_apps(device_id, customer_id=mdm_customer.customer_id)
                if apps_list:
                    device_obj.apps_count = len(apps_list)
                    device_obj.save(update_fields=['apps_count'])
                    # Persist installed apps
                    from .models import InstalledApp
                    InstalledApp.objects.filter(device=device_obj).delete()
                    app_objs = []
                    for app in apps_list:
                        name = app.get('app_name') or app.get('name', '')
                        pkg  = app.get('package_name') or app.get('bundle_id') or name
                        if name and pkg:
                            app_objs.append(InstalledApp(
                                device=device_obj,
                                app_name=name,
                                package_name=pkg,
                                version=str(app.get('version') or app.get('app_version', '')),
                            ))
                    if app_objs:
                        InstalledApp.objects.bulk_create(app_objs, ignore_conflicts=True)
            except Exception as exc:
                logger.debug("Could not fetch apps for device %s: %s", device_id, exc)

            try:
                profiles_list = self.get_device_profiles(device_id, customer_id=mdm_customer.customer_id)
                if profiles_list:
                    device_obj.profile_count = len(profiles_list)
                    device_obj.save(update_fields=['profile_count'])
            except Exception as exc:
                logger.debug("Could not fetch profiles for device %s: %s", device_id, exc)

        # Update device_count on the customer record
        mdm_customer.device_count = Device.objects.filter(
            mdm_customer=mdm_customer
        ).count()
        mdm_customer.save(update_fields=['device_count'])

        return created, updated, skipped


# ──────────────────────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────────────────────

def _map_platform_type(platform_type_str, platform_type_id_str=''):
    """
    Map real API platform_type / platform_type_id to Device.DEVICE_TYPES choice.
    platform_type   : "android" | "ios" | "windows"
    platform_type_id: "1"=iOS  "2"=Android  "3"=Windows
    """
    pt = (platform_type_str or '').lower()
    if 'android' in pt or str(platform_type_id_str) == '2':
        return 'android'
    if 'ios' in pt or 'iphone' in pt or 'ipad' in pt or str(platform_type_id_str) == '1':
        return 'ios'
    if 'windows' in pt or str(platform_type_id_str) == '3':
        return 'windows'
    return 'android'


def _gb_str_to_bytes(value):
    """Convert GB string (e.g. '473.98242') to bytes as integer."""
    try:
        return int(float(value) * 1024 * 1024 * 1024)
    except (TypeError, ValueError):
        return None


def _epoch_ms_to_dt(value):
    """Convert epoch-milliseconds string/int to naive local datetime (USE_TZ=False)."""
    if not value:
        return None
    try:
        ms = int(value)
        return datetime.datetime.fromtimestamp(ms / 1000.0)
    except (TypeError, ValueError):
        return None


# Keep these exported for use in views.py
_map_status    = lambda s: MANAGED_STATUS_MAP.get(str(s or '2'), 'managed')
_safe_int      = lambda v: int(v) if v is not None else None
_parse_ts      = _epoch_ms_to_dt
