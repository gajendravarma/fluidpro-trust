import requests
import base64
from django.conf import settings
from .token_manager import TokenManager

# Site24x7 monitor status codes  (1=Up, 0=Down — confirmed from live API)
STATUS_UP           = 1
STATUS_DOWN         = 0
STATUS_TROUBLE      = 2
STATUS_SUSPENDED    = 5
STATUS_MAINTENANCE  = 7
STATUS_CONFIG_ERROR = 9

STATUS_LABELS = {
    STATUS_UP:           'Up',
    STATUS_DOWN:         'Down',
    STATUS_TROUBLE:      'Trouble',
    STATUS_SUSPENDED:    'Suspended',
    STATUS_MAINTENANCE:  'Maintenance',
    STATUS_CONFIG_ERROR: 'Config Error',
}

STATUS_BADGE = {
    STATUS_UP:           'bg-success',
    STATUS_DOWN:         'bg-danger',
    STATUS_TROUBLE:      'bg-warning text-dark',
    STATUS_SUSPENDED:    'bg-secondary',
    STATUS_MAINTENANCE:  'bg-info text-dark',
    STATUS_CONFIG_ERROR: 'bg-dark',
}

# Monitor type → human label
MONITOR_TYPE_LABELS = {
    'URL':                'Website (URL)',
    'ISP':                'ISP / Network',
    'NETWORKDEVICE':      'Network Device',
    'SERVER':             'Server',
    'SSL_CERT':           'SSL Certificate',
    'DOMAINEXPIRY':       'Domain Expiry',
    'PROBE':              'On-Premise Poller',
    'POLLER_DASHBOARD':   'Poller Dashboard',
    'METRICS':            'Log / Metrics',
    'BRANDREPUTATION':    'Brand Reputation',
    'HOMEPAGE':           'Homepage Speed',
    'WEBSITEDEFACEMENT':  'Website Defacement',
    'WINUPDATE':          'Windows Update',
    'IISSERVER':          'IIS Server',
    'NCM':                'Network Config',
    'PORT-SMTP':          'SMTP Port',
}

# Fields that must never be sent in POST/PUT payloads
_READ_ONLY_FIELDS = frozenset([
    'monitor_id', 'numeric_status', 'last_polled_time', 'state',
    'created_time', 'last_updated_time', 'uptime_monitor',
])

# Empty list fields that cause validation errors in PUT/POST
_EMPTY_LIST_FIELDS = frozenset(['locations'])


class Site24x7Platform:
    def __init__(self):
        self.token_manager = TokenManager()
        self.api_domain = settings.SITE24X7_API_DOMAIN
        self._refresh_headers()

    def _refresh_headers(self):
        """Fetch (or re-fetch) a valid token and update the Authorization header."""
        self.access_token = self.token_manager.get_valid_token()
        self.headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Accept": "application/json; version=2.0",
            "Content-Type": "application/json;charset=UTF-8",
        }

    @staticmethod
    def encode_zaaid(zaaid):
        return base64.b64encode(str(zaaid).encode()).decode()

    @staticmethod
    def decode_zaaid(encoded_zaaid):
        try:
            return base64.b64decode(encoded_zaaid).decode()
        except Exception:
            return encoded_zaaid

    @staticmethod
    def parse_monitor_status(monitor):
        """Return integer status code. Uses monitor-level 'status' as primary."""
        mon_status = monitor.get('status')
        if mon_status is not None:
            return int(mon_status)
        locations = monitor.get('locations', [])
        primary = next((l for l in locations if l.get('primary_location')), locations[0] if locations else {})
        loc_status = primary.get('status')
        return int(loc_status) if loc_status is not None else -1

    @staticmethod
    def clean_payload(data):
        """Strip read-only and problematic fields before POST/PUT."""
        return {k: v for k, v in data.items()
                if k not in _READ_ONLY_FIELDS
                and not (k in _EMPTY_LIST_FIELDS and v == [])}

    def _request(self, method, endpoint, zaaid=None, data=None):
        sep = "&" if "?" in endpoint else "?"
        url = f"{self.api_domain}{endpoint}{sep}zaaid={zaaid}" if zaaid else f"{self.api_domain}{endpoint}"
        try:
            # Proactively refresh headers if token is near expiry
            self._refresh_headers()
            resp = requests.request(method, url, headers=self.headers, json=data, timeout=15)
            if resp.status_code == 401:
                # Token expired mid-request — force refresh and retry once
                new_token = self.token_manager.handle_401_error()
                if new_token:
                    self.access_token = new_token
                    self.headers["Authorization"] = f"Zoho-oauthtoken {new_token}"
                    resp = requests.request(method, url, headers=self.headers, json=data, timeout=15)
            return resp.json() if resp.content else {}
        except Exception as e:
            return {"error": str(e)}

    def call_api(self, endpoint, zaaid=None, method="GET", data=None):
        return self._request(method, endpoint, zaaid=zaaid, data=data)

    # ── Customers ─────────────────────────────────────────────────────────────
    def get_customers(self):
        return self._request("GET", "/api/short/msp/customers")

    # ── Monitors ──────────────────────────────────────────────────────────────
    def get_monitors(self, zaaid=None):
        return self._request("GET", "/api/monitors", zaaid=zaaid)

    def get_monitor_details(self, monitor_id, zaaid=None):
        return self._request("GET", f"/api/monitors/{monitor_id}", zaaid=zaaid)

    def create_monitor(self, data, zaaid=None):
        payload = self.clean_payload(data)
        return self._request("POST", "/api/monitors", zaaid=zaaid, data=payload)

    def update_monitor(self, monitor_id, data, zaaid=None):
        payload = self.clean_payload(data)
        return self._request("PUT", f"/api/monitors/{monitor_id}", zaaid=zaaid, data=payload)

    def delete_monitor(self, monitor_id, zaaid=None):
        return self._request("DELETE", f"/api/monitors/{monitor_id}", zaaid=zaaid)

    def get_current_status(self, zaaid=None):
        return self._request("GET", "/api/current_status", zaaid=zaaid)

    def get_monitor_groups(self, zaaid=None):
        return self._request("GET", "/api/monitor_groups", zaaid=zaaid)

    # ── Profiles & Configuration ───────────────────────────────────────────────
    def get_location_profiles(self, zaaid=None):
        return self._request("GET", "/api/location_profiles", zaaid=zaaid)

    def get_notification_profiles(self, zaaid=None):
        return self._request("GET", "/api/notification_profiles", zaaid=zaaid)

    def get_threshold_profiles(self, zaaid=None):
        return self._request("GET", "/api/threshold_profiles", zaaid=zaaid)

    def get_user_groups(self, zaaid=None):
        return self._request("GET", "/api/user_groups", zaaid=zaaid)

    def get_tags(self, zaaid=None):
        return self._request("GET", "/api/tags", zaaid=zaaid)

    # ── Maintenance Windows ───────────────────────────────────────────────────
    def get_maintenance(self, zaaid=None):
        return self._request("GET", "/api/maintenance", zaaid=zaaid)

    def create_maintenance(self, data, zaaid=None):
        return self._request("POST", "/api/maintenance", zaaid=zaaid, data=data)

    def delete_maintenance(self, maintenance_id, zaaid=None):
        return self._request("DELETE", f"/api/maintenance/{maintenance_id}", zaaid=zaaid)

    # ── Reports ───────────────────────────────────────────────────────────────
    def get_summary_report(self, period=7, zaaid=None):
        return self._request("GET", f"/api/reports/summary?period={period}", zaaid=zaaid)

    def get_monitor_summary(self, monitor_id, period=7, zaaid=None):
        return self._request("GET", f"/api/reports/summary/{monitor_id}?period={period}", zaaid=zaaid)

    def get_reports(self, monitor_id, period=1, zaaid=None):
        return self._request("GET", f"/api/reports/summary/{monitor_id}?period={period}", zaaid=zaaid)

    # ── Alerts ────────────────────────────────────────────────────────────────
    def get_alert_logs(self, zaaid=None):
        return self._request("GET", "/api/alert_logs", zaaid=zaaid)
