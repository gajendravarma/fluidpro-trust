import slumber
import itertools
import time
import requests
from django.conf import settings


class _TimeoutSession(requests.Session):
    """requests.Session that enforces a default (connect, read) timeout."""
    def __init__(self, connect=10, read=45):
        super().__init__()
        self._default_timeout = (connect, read)

    def request(self, method, url, **kwargs):
        kwargs.setdefault('timeout', self._default_timeout)
        return super().request(method, url, **kwargs)


class PulsewayAPI:
    def __init__(self):
        session = _TimeoutSession(connect=10, read=45)
        session.auth = (settings.PULSEWAY_TOKEN_ID, settings.PULSEWAY_TOKEN_SECRET)
        self.api = slumber.API(
            settings.PULSEWAY_ENDPOINT,
            session=session,
        )

    def _paginated_get(self, endpoint, top=100):
        """Generic method for paginated API calls"""
        all_items = []
        for skip in itertools.count(0, top):
            params = {'$top': top, '$skip': skip}
            response = getattr(self.api, endpoint).get(**params)
            rows = response.get("Data") if isinstance(response, dict) else response
            if not rows:
                break
            all_items.extend(rows)
            if len(rows) < top:
                break
        return all_items

    def get_devices(self, top=50, skip=0):
        """Get devices with pagination"""
        params = {'$top': top, '$skip': skip}
        return self.api.devices.get(**params)

    def get_all_devices(self):
        """Get all devices"""
        return self._paginated_get('devices')

    def get_device_details(self, device_id, _retries=3):
        """Get detailed information for a specific device.

        Retries on transient failures (429 rate-limit, read timeout, connection
        reset) with exponential backoff. Re-raises 404 so callers can remove
        stale DB records. Returns None for any non-retryable error so the caller
        can preserve the device's last-known status instead of corrupting it.
        """
        for attempt in range(_retries + 1):
            try:
                return self.api.devices(device_id).get()
            except Exception as e:
                err = str(e)

                # Stale device — let caller delete it from DB
                if '404' in err:
                    raise

                # Transient errors worth retrying
                is_rate_limit = '429' in err
                is_timeout    = 'timed out' in err.lower() or 'timeout' in err.lower()
                is_conn_reset = 'connectionreset' in err.lower() or '10054' in err

                if (is_rate_limit or is_timeout or is_conn_reset) and attempt < _retries:
                    wait = 5 * (2 ** attempt)   # 5 s, 10 s, 20 s
                    reason = ('rate-limited' if is_rate_limit
                              else 'timed out' if is_timeout
                              else 'connection reset')
                    print(f"Device {device_id} {reason} (attempt {attempt+1}/{_retries+1}), retrying in {wait}s")
                    time.sleep(wait)
                    continue

                print(f"Error getting device details for {device_id}: {err}")
                return None

    def get_device_system_info(self, device_id):
        """Get system information for a specific device"""
        try:
            # Try different endpoints for system info
            endpoints_to_try = [
                f'devices/{device_id}/systeminfo',
                f'devices/{device_id}/system',
                f'devices/{device_id}/info',
                f'devices/{device_id}/details'
            ]
            
            for endpoint in endpoints_to_try:
                try:
                    response = self.api.get(endpoint)
                    if response and 'Data' in response:
                        return response['Data']
                except:
                    continue
            
            # Fallback to device details
            return self.get_device_details(device_id)
        except Exception as e:
            print(f"Error getting system info for device {device_id}: {str(e)}")
            return None

    # Fields we consider "rich enough" from the list endpoint — if all present,
    # skip the per-device detail call to avoid hitting Pulseway's rate limit.
    _DETAIL_FIELDS = ('OperatingSystem', 'IPAddress', 'IsOnline')

    def get_all_devices_with_details(self, max_devices=1000):
        """Get all devices with their detailed information.

        Strategy:
        1. Fetch the full device list (one paginated call).
        2. For devices already carrying rich fields from the list response,
           skip the individual detail call entirely.
        3. For devices missing key fields, fetch details one-by-one with a
           small inter-request delay to stay under Pulseway's rate limit.
        """
        devices = self.get_all_devices()[:max_devices]
        detailed_devices = []
        DETAIL_CALL_DELAY = 1.5   # 1.5 s — ~40 req/min, matches Pulseway's actual rate limit

        for device in devices:
            try:
                device_id = device.get('Identifier')
                if not device_id:
                    detailed_devices.append(device)
                    continue

                # If the list endpoint already returned all key detail fields, use as-is.
                if all(device.get(f) for f in self._DETAIL_FIELDS):
                    detailed_devices.append(device)
                    continue

                # Missing fields — fetch individual detail with rate-limit delay.
                time.sleep(DETAIL_CALL_DELAY)  # 500 ms → ~120 req/min, safely under Pulseway limit
                details = self.get_device_details(device_id)
                if details:
                    detail_data = details.get('Data', details) if isinstance(details, dict) else {}
                    if isinstance(detail_data, dict):
                        device_data = device.copy()
                        device_data.update(detail_data)
                        detailed_devices.append(device_data)
                        continue

                detailed_devices.append(device)
            except Exception as e:
                if '404' not in str(e):
                    print(f"Error processing device {device.get('Name', 'Unknown')}: {str(e)}")
                detailed_devices.append(device)

        return detailed_devices

    def get_device_patches(self, device_id):
        """Get patches for a specific device"""
        try:
            response = self.api.devices(device_id).patches.get()
            return response.get('Data', []) if isinstance(response, dict) else response
        except Exception as e:
            print(f"Error getting patches for device {device_id}: {str(e)}")
            return []

    def get_device_software(self, device_id):
        """
        GET /api/v3/devices/{device_id}/software
        Returns list of installed software on a device.
        Each item: {Name, Version, Publisher, InstallDate, Size}
        """
        try:
            response = self.api.devices(device_id).software.get()
            data = response.get('Data', response) if isinstance(response, dict) else response
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"Error getting software for device {device_id}: {str(e)}")
            return []

    def get_org_software_report(self, org_name=None, max_devices=50):
        """
        Build a software report aggregated across devices.
        If org_name is given, only includes devices from that organisation.
        Returns:
          {
            'devices':   [{device_id, device_name, org, software_count}],
            'software':  [{name, publisher, version, device_count, devices:[...]}],
            'total_devices': int,
            'api_errors': int,
          }
        Fetches software per device with 300ms inter-request delay to avoid 429.
        """
        all_devices = self.get_all_devices()
        if org_name:
            all_devices = [d for d in all_devices
                           if org_name.lower() in (d.get('OrganizationName') or '').lower()]
        all_devices = all_devices[:max_devices]

        device_rows = []
        # app_key → {name, publisher, version (most common), devices:[name,...]}
        software_map: dict = {}
        api_errors = 0

        for i, dev in enumerate(all_devices):
            device_id   = dev.get('Identifier', '')
            device_name = dev.get('Name', 'Unknown')
            org         = dev.get('OrganizationName', '')
            if not device_id:
                continue
            if i > 0:
                time.sleep(0.3)   # 300 ms delay — ~3 req/s stays under rate limit
            apps = self.get_device_software(device_id)
            if apps is None:
                api_errors += 1
                apps = []
            device_rows.append({
                'device_id':      device_id,
                'device_name':    device_name,
                'org':            org,
                'software_count': len(apps),
            })
            for app in apps:
                name      = (app.get('Name') or '').strip()
                publisher = (app.get('Publisher') or '').strip()
                version   = (app.get('Version') or '').strip()
                if not name:
                    continue
                key = name.lower()
                if key not in software_map:
                    software_map[key] = {
                        'name':         name,
                        'publisher':    publisher,
                        'version':      version,
                        'device_count': 0,
                        'devices':      [],
                    }
                software_map[key]['device_count'] += 1
                software_map[key]['devices'].append(device_name)

        software_list = sorted(software_map.values(),
                               key=lambda x: x['device_count'], reverse=True)
        return {
            'devices':       device_rows,
            'software':      software_list,
            'total_devices': len(device_rows),
            'api_errors':    api_errors,
        }

    def get_sites(self, top=50, skip=0):
        """Get sites with pagination"""
        params = {'$top': top, '$skip': skip}
        return self.api.sites.get(**params)

    def get_all_sites(self):
        """Get all sites"""
        return self._paginated_get('sites')

    def get_groups(self, top=50, skip=0):
        """Get groups with pagination"""
        params = {'$top': top, '$skip': skip}
        return self.api.groups.get(**params)

    def get_all_groups(self):
        """Get all groups"""
        return self._paginated_get('groups')

    def get_organizations(self, top=50, skip=0):
        """Get organizations with pagination"""
        params = {'$top': top, '$skip': skip}
        return self.api.organizations.get(**params)

    def get_all_organizations(self):
        """Get all organizations"""
        return self._paginated_get('organizations')

    def get_reports(self, top=50, skip=0):
        """Get reports with pagination"""
        try:
            params = {'$top': top, '$skip': skip}
            return self.api.reports.get(**params)
        except Exception as e:
            print(f"Error getting reports: {str(e)}")
            return {'Data': []}

    def get_all_reports(self):
        """Get all reports"""
        try:
            return self._paginated_get('reports')
        except Exception as e:
            print(f"Error getting all reports: {str(e)}")
            return []

    def create_site(self, data):
        """Create a new site"""
        return self.api.sites.post(data)

    def update_site(self, site_id, data):
        """Update a site"""
        return self.api.sites(site_id).put(data)

    def delete_site(self, site_id):
        """Not supported — Pulseway API only allows GET/POST/PUT on /sites/."""
        raise NotImplementedError("Pulseway API does not support site deletion.")

    def create_group(self, data):
        """Create a new group"""
        return self.api.groups.post(data)

    def update_group(self, group_id, data):
        """Update a group"""
        return self.api.groups(group_id).put(data)

    def delete_group(self, group_id):
        """Delete a group — use requests directly to avoid slumber trailing-slash 405."""
        url = f"{settings.PULSEWAY_ENDPOINT}/groups/{group_id}"
        resp = requests.delete(
            url,
            auth=(settings.PULSEWAY_TOKEN_ID, settings.PULSEWAY_TOKEN_SECRET)
        )
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def run_script(self, device_id, script_data):
        """
        Run a script on a device.
        Pulseway v3 API does not have a standalone /devices/{id}/scripts endpoint.
        Instead we create a one-time automation task and immediately run it
        targeting the specific device.
        """
        name = script_data.get('Name', 'Ad-hoc Script')
        content = script_data.get('Content', '')
        script_type = script_data.get('Type', 'Powershell')

        # Step 1: create automation task
        task_payload = {
            'Name': name,
            'Description': 'Created via portal — ad-hoc run',
            'Scripts': [{'Type': script_type, 'Content': content}],
        }
        create_url = f"{settings.PULSEWAY_ENDPOINT}/automation/tasks"
        resp = requests.post(
            create_url,
            auth=(settings.PULSEWAY_TOKEN_ID, settings.PULSEWAY_TOKEN_SECRET),
            json=task_payload,
            timeout=30,
        )

        if resp.status_code in (405, 501):
            raise NotImplementedError(
                "The Pulseway API does not support creating automation tasks via REST (HTTP 405). "
                "Please create the automation task in the Pulseway web console, then use the "
                "Automation Tasks page to run it on a specific device."
            )
        resp.raise_for_status()

        task_data = resp.json() if resp.content else {}
        task_id = (task_data.get('Data') or task_data).get('Id') if isinstance(task_data.get('Data'), dict) else task_data.get('Id')

        if not task_id:
            raise ValueError("Automation task created but no ID returned from Pulseway API.")

        # Step 2: run task on specific device
        run_url = f"{settings.PULSEWAY_ENDPOINT}/automation/tasks/{task_id}/run"
        run_resp = requests.post(
            run_url,
            auth=(settings.PULSEWAY_TOKEN_ID, settings.PULSEWAY_TOKEN_SECRET),
            json={'DeviceIds': [device_id]},
            timeout=30,
        )
        run_resp.raise_for_status()
        return {'task_id': task_id, 'run': run_resp.json() if run_resp.content else {}}

    def install_patches(self, device_id, patch_data):
        """Install patches on device"""
        return self.api.devices(device_id).patches.post(patch_data)

    def get_device_status(self, device_id):
        """Get device status"""
        return self.api.devices(device_id).get()

    def reboot_device(self, device_id):
        """Reboot device"""
        return self.api.devices(device_id).reboot.post({})
    def get_automation_tasks(self, top=50, skip=0):
        """Get automation tasks"""
        try:
            params = {'$top': top, '$skip': skip}
            return self.api.automation.tasks.get(**params)
        except Exception as e:
            # If automation.tasks doesn't work, try alternative endpoints
            print(f"Automation tasks API error: {e}")
            return []

    def get_all_automation_tasks(self):
        """Get all automation tasks"""
        try:
            return self._paginated_get('automation/tasks')
        except Exception as e:
            print(f"Get all automation tasks error: {e}")
            # Try alternative approach
            try:
                return self.api.automation.tasks.get()
            except:
                return []

    def create_automation_task(self, data):
        """Create automation task"""
        return self.api.automation.tasks.post(data)

    def run_automation_task(self, task_id):
        """Run automation task"""
        return self.api.automation.tasks(task_id).run.post({})

    def update_automation_task(self, task_id, data):
        """Update automation task"""
        return self.api.automation.tasks(task_id).put(data)

    def delete_automation_task(self, task_id):
        """Delete automation task"""
        return self.api.automation.tasks(task_id).delete()

    def get_device_notifications(self, device_id):
        """Get notifications/alerts for a specific device"""
        try:
            response = self.api.devices(device_id).notifications.get()
            return response.get('Data', []) if isinstance(response, dict) else (response or [])
        except Exception as e:
            print(f"Error getting notifications for device {device_id}: {e}")
            return []

    def get_all_notifications(self, top=100, skip=0):
        """Get all system notifications/alerts"""
        try:
            response = self.api.notifications.get(**{'$top': top, '$skip': skip})
            return response.get('Data', []) if isinstance(response, dict) else (response or [])
        except Exception as e:
            print(f"Error getting notifications: {e}")
            return []

    def acknowledge_notification(self, notification_id):
        """Acknowledge a notification/alert"""
        try:
            return self.api.notifications(notification_id).acknowledge.post({})
        except Exception as e:
            print(f"Error acknowledging notification {notification_id}: {e}")
            raise

    def get_remote_desktop_url(self, device_id):
        """Generate remote desktop web console URL for a device"""
        # Pulseway remote desktop is accessed through their web console
        # Format: https://{instance}.pulseway.com/devices/{device_id}/remote
        base_url = self.api._store['base_url'].replace('/api/v3', '')
        return f"{base_url}/devices/{device_id}/remote"

    def initiate_remote_session(self, device_id):
        """Get remote session information"""
        # Return web console URL for remote access
        return {
            'url': self.get_remote_desktop_url(device_id),
            'type': 'web_console',
            'message': 'Remote access via Pulseway web console'
        }

    # ------------------------------------------------------------------
    # Device update
    # ------------------------------------------------------------------

    def update_device(self, device_id, data):
        """Update device properties (Name, Description, GroupId)."""
        return self.api.devices(device_id).put(data)

    # ------------------------------------------------------------------
    # Policies
    # ------------------------------------------------------------------

    def get_all_policies(self):
        """Get all monitoring policies."""
        try:
            return self._paginated_get('policies')
        except Exception as e:
            print(f"Error getting policies: {e}")
            return []

    def get_policy(self, policy_id):
        """Get a single policy by ID."""
        try:
            resp = self.api.policies(policy_id).get()
            return resp.get('Data', resp) if isinstance(resp, dict) else resp
        except Exception as e:
            print(f"Error getting policy {policy_id}: {e}")
            return None

    def create_policy(self, data):
        """Create a new monitoring policy."""
        return self.api.policies.post(data)

    def update_policy(self, policy_id, data):
        """Update an existing policy."""
        return self.api.policies(policy_id).put(data)

    def delete_policy(self, policy_id):
        """Delete a policy."""
        url = f"{settings.PULSEWAY_ENDPOINT}/policies/{policy_id}"
        resp = requests.delete(
            url,
            auth=(settings.PULSEWAY_TOKEN_ID, settings.PULSEWAY_TOKEN_SECRET)
        )
        resp.raise_for_status()
        return resp.json() if resp.content else {}
