import time as _time
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from .models import PulsewayDevice, PulsewayOrganization, PulsewayPatch, PulsewayReport, PulsewaySync
from pulseway.company_matcher import CompanyMatcher
from .services import PulsewayAPI
import logging

logger = logging.getLogger(__name__)


class PulsewayLocalService:
    """Service for managing Pulseway data in local database"""
    
    def __init__(self):
        # Enable API calls
        self.api = PulsewayAPI()
    
    def sync_all_data(self):
        """Sync all data from Pulseway API"""
        try:
            logger.info("Starting full Pulseway sync...")
            
            # Sync organizations first
            self.sync_organizations()
            
            # Sync devices with details
            self.sync_devices()
            
            # Update sync record
            self._update_sync_record('all', 'success')
            logger.info("Full Pulseway sync completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Full sync failed: {str(e)}")
            self._update_sync_record('all', 'failed', str(e))
            return False
    
    def sync_organizations(self):
        """Sync organizations from Pulseway API"""
        try:
            logger.info("Syncing organizations...")
            orgs_data = self.api.get_all_organizations()
            
            synced_count = 0
            with transaction.atomic():
                for org_data in orgs_data:
                    org_id = org_data.get('Identifier')
                    name = org_data.get('Name')
                    if org_id and name:
                        PulsewayOrganization.objects.update_or_create(
                            org_id=org_id,
                            defaults={'name': name}
                        )
                        synced_count += 1

            self._update_sync_record('organizations', 'success', records_synced=synced_count)
            logger.info(f"Synced {synced_count} organizations")
            return True
            
        except Exception as e:
            logger.error(f"Organization sync failed: {str(e)}")
            self._update_sync_record('organizations', 'failed', str(e))
            return False
    
    def sync_devices(self):
        """Sync devices from Pulseway API with OS and IP details"""
        try:
            logger.info("Syncing devices with details...")
            
            # Test API connectivity first
            try:
                devices_data = self.api.get_all_devices_with_details()
            except Exception as api_error:
                logger.warning(f"API call failed: {str(api_error)}")
                # If API fails, just update sync record and return success
                # This prevents constant error logging when API is down
                self._update_sync_record('devices', 'api_unavailable', f"API Error: {str(api_error)}")
                return True
            
            # Build the full list of records to upsert before touching the DB,
            # so the write transaction is as short as possible (avoids SQLite lock).
            records = []
            # Devices whose detail call was rate-limited (429) or failed — they land
            # here with no Uptime and no IsOnline key.  We track them separately so
            # we can preserve their last-known status from the DB instead of
            # incorrectly marking them offline.
            no_detail_ids = set()

            for device_data in devices_data:
                device_id = device_data.get('Identifier')
                if not device_id:
                    continue

                uptime = device_data.get('Uptime', '')
                has_is_online = 'IsOnline' in device_data
                has_detail = has_is_online or bool(uptime)  # either key signals a real detail response

                if not has_detail:
                    # Detail API failed for this device (likely 429 rate-limit).
                    # Mark for status preservation from DB — do NOT default to offline.
                    no_detail_ids.add(device_id)

                if has_is_online:
                    is_online = bool(device_data['IsOnline'])
                else:
                    is_online = bool(uptime) and 'offline' not in uptime.lower()

                operating_system = (
                    device_data.get('OperatingSystem') or
                    device_data.get('Description') or
                    device_data.get('OSDescription') or
                    ''
                )
                ip_address = (
                    device_data.get('IPAddress') or
                    device_data.get('ExternalIpAddress') or
                    device_data.get('IpAddress') or
                    ''
                )
                records.append({
                    'device_id':        device_id,
                    'is_online':        is_online,
                    'has_detail':       has_detail,
                    'operating_system': operating_system,
                    'ip_address':       ip_address,
                    'device_info': {
                        'device_id':        device_id,
                        'device_name':      device_data.get('Name', ''),
                        'organization_name': device_data.get('OrganizationName', ''),
                        'site_name':        device_data.get('SiteName', ''),
                        'status':           'online' if is_online else 'offline',
                        'uptime':           uptime,
                        'operating_system': operating_system,
                        'ip_address':       ip_address,
                        'mac_address':      device_data.get('MACAddress', ''),
                        'cpu_usage':        self._parse_percentage(device_data.get('CPUUsage')),
                        'memory_usage':     self._parse_percentage(device_data.get('MemoryUsage')),
                        'disk_usage':       self._parse_percentage(device_data.get('DiskUsage')),
                        'pending_patches':  device_data.get('PendingPatches', 0) or 0,
                        'last_seen':        self._parse_date(device_data.get('LastSeen')),
                    },
                })

            # Prefetch existing DB data for:
            # a) offline devices — to preserve last-known OS/IP
            # b) no-detail devices — to preserve last-known status (avoid false offline)
            preserve_ids = {r['device_id'] for r in records if not r['is_online'] or not r['has_detail']}
            existing_map = {
                d['device_id']: d
                for d in PulsewayDevice.objects.filter(device_id__in=preserve_ids)
                    .values('device_id', 'status', 'operating_system', 'ip_address', 'mac_address', 'uptime')
            } if preserve_ids else {}

            # Write in small batches (50 at a time) so each transaction is short
            # and doesn't hold the SQLite write lock long enough to conflict with
            # the ManageEngine auto-sync that runs concurrently every 5 minutes.
            synced_count = 0
            BATCH = 50
            for batch_start in range(0, len(records), BATCH):
                batch = records[batch_start:batch_start + BATCH]
                with transaction.atomic():
                    for rec in batch:
                        device_info = rec['device_info']
                        ex = existing_map.get(rec['device_id'], {})

                        # If detail API failed (429/rate-limit) — no Uptime, no IsOnline —
                        # preserve the last-known status and uptime from DB.
                        if not rec['has_detail'] and ex.get('status'):
                            device_info['status'] = ex['status']
                            if ex.get('uptime'):
                                device_info['uptime'] = ex['uptime']

                        # For offline/no-detail devices, preserve last-known OS/IP/MAC
                        if not rec['is_online'] or not rec['has_detail']:
                            if not rec['operating_system'] and ex.get('operating_system'):
                                device_info['operating_system'] = ex['operating_system']
                            if not rec['ip_address'] and ex.get('ip_address'):
                                device_info['ip_address'] = ex['ip_address']
                            if not device_info['mac_address'] and ex.get('mac_address'):
                                device_info['mac_address'] = ex['mac_address']

                        PulsewayDevice.objects.update_or_create(
                            device_id=rec['device_id'],
                            defaults=device_info,
                        )
                        synced_count += 1

            # Remove DB records for devices no longer in the Pulseway API (decommissioned)
            api_ids = {r['device_id'] for r in records}
            stale = PulsewayDevice.objects.exclude(device_id__in=api_ids)
            stale_count = stale.count()
            if stale_count:
                logger.info(f"Removing {stale_count} stale devices no longer in Pulseway API")
                stale.delete()

            # Update organization counts (separate transaction — read-heavy)
            self._update_organization_counts()

            self._update_sync_record('devices', 'success', records_synced=synced_count)
            logger.info(f"Synced {synced_count} devices, removed {stale_count} stale")
            return True

        except Exception as e:
            logger.error(f"Device sync failed: {str(e)}")
            self._update_sync_record('devices', 'failed', str(e))
            return False

    def sync_device_status(self, delay_seconds=2.0):
        """
        Fetch per-device detail for every device in DB and update:
          status (IsOnline), uptime, IP, OS, CPU/memory/disk usage, pending patches.

        Uses delay_seconds between each API call to stay under Pulseway rate limits
        (~30 req/min at 2s delay).  This is intentionally slow — run it every 30 min,
        not every 5 min.

        Returns (synced, errors) counts.
        """
        devices = list(PulsewayDevice.objects.values_list('device_id', flat=True))
        logger.info(f"[Status sync] Starting per-device detail sync for {len(devices)} devices...")
        synced = 0
        errors = 0

        for i, device_id in enumerate(devices):
            if i > 0:
                _time.sleep(delay_seconds)
            try:
                detail = self.api.get_device_details(device_id)
                if not detail:
                    errors += 1
                    continue

                # get_device_details returns the raw API response dict or {'Data': ...}
                if isinstance(detail, dict) and 'Data' in detail:
                    detail = detail['Data']

                raw_online = detail.get('IsOnline')
                if raw_online is not None:
                    is_online = str(raw_online).lower() in ('true', '1', 'yes', 'online') \
                                if isinstance(raw_online, str) else bool(raw_online)
                else:
                    uptime_val = detail.get('Uptime', '')
                    is_online = bool(uptime_val) and 'offline' not in uptime_val.lower()

                updates = {
                    'status':          'online' if is_online else 'offline',
                    'uptime':          detail.get('Uptime', ''),
                    'ip_address':      (detail.get('IPAddress') or detail.get('IpAddress') or ''),
                    'operating_system': (detail.get('OperatingSystem') or
                                         detail.get('OSDescription') or ''),
                    'mac_address':     detail.get('MACAddress', ''),
                    'cpu_usage':       self._parse_percentage(detail.get('CPUUsage')),
                    'memory_usage':    self._parse_percentage(detail.get('MemoryUsage')),
                    'disk_usage':      self._parse_percentage(detail.get('DiskUsage')),
                    'pending_patches': detail.get('PendingPatches', 0) or 0,
                    'last_seen':       self._parse_date(detail.get('LastSeen')),
                }
                PulsewayDevice.objects.filter(device_id=device_id).update(**updates)
                synced += 1
            except Exception as e:
                err_str = str(e)
                if '404' in err_str:
                    # Device no longer exists in Pulseway — remove stale DB record
                    PulsewayDevice.objects.filter(device_id=device_id).delete()
                    logger.info(f"[Status sync] Removed stale device {device_id} (404)")
                else:
                    logger.warning(f"[Status sync] device {device_id}: {e}")
                    errors += 1

        self._update_sync_record('device_status', 'success' if not errors else 'partial',
                                 records_synced=synced,
                                 error_message=f'{errors} errors' if errors else '')
        logger.info(f"[Status sync] Done — {synced} updated, {errors} errors.")
        return synced, errors

    def sync_patches(self):
        """Sync patches from Pulseway API"""
        try:
            logger.info("Syncing patches...")
            devices = PulsewayDevice.objects.all()
            synced_count = 0
            
            for device in devices:
                try:
                    patches_data = self.api.get_device_patches(device.device_id)
                    for patch_data in patches_data:
                        patch_info = {
                            'device': device,
                            'patch_id': patch_data.get('Identifier', ''),
                            'patch_name': patch_data.get('Name', ''),
                            'status': patch_data.get('Status', 'pending'),
                            'severity': patch_data.get('Severity', ''),
                            'category': patch_data.get('Category', ''),
                            'install_date': self._parse_date(patch_data.get('InstallDate'))
                        }
                        
                        PulsewayPatch.objects.update_or_create(
                            device=device,
                            patch_id=patch_info['patch_id'],
                            defaults=patch_info
                        )
                        synced_count += 1
                except Exception as e:
                    logger.warning(f"Failed to sync patches for device {device.device_name}: {str(e)}")
            
            self._update_sync_record('patches', 'success', records_synced=synced_count)
            logger.info(f"Synced {synced_count} patches")
            return True
            
        except Exception as e:
            logger.error(f"Patch sync failed: {str(e)}")
            self._update_sync_record('patches', 'failed', str(e))
            return False
    
    def sync_reports(self):
        """Sync reports from Pulseway API"""
        try:
            logger.info("Syncing reports...")
            reports_data = self.api.get_all_reports()
            synced_count = 0
            
            for report_data in reports_data:
                report_info = {
                    'report_id': report_data.get('Identifier', ''),
                    'report_name': report_data.get('Name', ''),
                    'organization_name': report_data.get('OrganizationName', ''),
                    'report_type': report_data.get('Type', ''),
                    'report_data': report_data,
                    'generated_date': self._parse_date(report_data.get('GeneratedDate'))
                }
                
                PulsewayReport.objects.update_or_create(
                    report_id=report_info['report_id'],
                    defaults=report_info
                )
                synced_count += 1
            
            self._update_sync_record('reports', 'success', records_synced=synced_count)
            logger.info(f"Synced {synced_count} reports")
            return True
            
        except Exception as e:
            logger.error(f"Report sync failed: {str(e)}")
            self._update_sync_record('reports', 'failed', str(e))
            return False
    
    def _update_sync_record(self, sync_type, status, error_message='', records_synced=0):
        """Update sync record in database"""
        try:
            sync_record, created = PulsewaySync.objects.update_or_create(
                sync_type=sync_type,
                defaults={
                    'status': status,
                    'error_message': error_message,
                    'records_synced': records_synced
                }
            )
        except Exception as e:
            logger.error(f"Failed to update sync record: {str(e)}")
    
    def _parse_percentage(self, value):
        """Parse percentage value from string"""
        if not value:
            return None
        try:
            # Remove % sign and convert to float
            return float(str(value).replace('%', ''))
        except:
            return None
    
    def _parse_date(self, date_str):
        """Parse date string to datetime"""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None
    
    def get_company_devices(self, company_name):
        """Get devices for a specific company using fuzzy matching"""
        # Get all organization names for matching
        org_names = list(PulsewayDevice.objects.values_list('organization_name', flat=True).distinct())
        
        # Find best matching organization
        matched_org = CompanyMatcher.match_company(company_name, org_names)
        
        # Get devices using fuzzy matching
        devices = PulsewayDevice.objects.filter(
            organization_name__icontains=matched_org
        ) if matched_org else PulsewayDevice.objects.none()
        
        # Also try direct matching and partial matching
        if not devices.exists():
            # Try exact match
            devices = PulsewayDevice.objects.filter(organization_name__iexact=company_name)
            
        if not devices.exists():
            # Try partial match
            devices = PulsewayDevice.objects.filter(organization_name__icontains=company_name)
            
        if not devices.exists():
            # Try reverse partial match (company name contains org name)
            for org_name in org_names:
                if org_name.lower() in company_name.lower() or company_name.lower() in org_name.lower():
                    devices = PulsewayDevice.objects.filter(organization_name=org_name)
                    break
                    
        if not devices.exists():
            # Try removing special characters and matching
            clean_company = ''.join(c.lower() for c in company_name if c.isalnum())
            for org_name in org_names:
                clean_org = ''.join(c.lower() for c in org_name if c.isalnum())
                if clean_company == clean_org or clean_company in clean_org or clean_org in clean_company:
                    devices = PulsewayDevice.objects.filter(organization_name=org_name)
                    break
        
        return devices
    
    def get_company_stats(self, company_name):
        """Get statistics for a specific company"""
        devices = self.get_company_devices(company_name)
        
        return {
            'total_devices': devices.count(),
            'online_devices': devices.filter(status='online').count(),
            'offline_devices': devices.filter(status='offline').count(),
            'pending_patches': sum(d.pending_patches for d in devices),
            'up_to_date_patches': devices.count() - devices.filter(pending_patches__gt=0).count()
        }
    
    def get_devices_by_status(self, company_name, status):
        """Get devices filtered by status for popup display"""
        devices = self.get_company_devices(company_name)
        
        if status == 'online':
            return devices.filter(status='online')
        elif status == 'offline':
            return devices.filter(status='offline')
        elif status == 'patches_pending':
            return devices.filter(pending_patches__gt=0)
        elif status == 'patches_updated':
            return devices.filter(pending_patches=0)
        
        return devices
    
    def get_last_sync_info(self):
        """Get information about last sync"""
        sync_info = {}
        for sync_type in ['organizations', 'devices', 'patches', 'reports']:
            try:
                sync = PulsewaySync.objects.get(sync_type=sync_type)
                sync_info[sync_type] = {
                    'last_sync': sync.last_sync,
                    'status': sync.status,
                    'records_synced': sync.records_synced,
                    'error_message': sync.error_message
                }
            except PulsewaySync.DoesNotExist:
                sync_info[sync_type] = {
                    'last_sync': None,
                    'status': 'never',
                    'records_synced': 0,
                    'error_message': ''
                }
        
        return sync_info
    
    def _update_organization_counts(self):
        """Update device counts for organizations"""
        for org in PulsewayOrganization.objects.all():
            devices = PulsewayDevice.objects.filter(organization_name=org.name)
            org.device_count = devices.count()
            org.online_devices = devices.filter(status='online').count()
            org.offline_devices = devices.filter(status='offline').count()
            org.pending_patches = sum(d.pending_patches for d in devices)
            org.save()
    
    def _parse_percentage(self, value):
        """Parse percentage value from string"""
        if not value:
            return None
        try:
            # Remove % sign and convert to float
            return float(str(value).replace('%', ''))
        except:
            return None
    
    def _parse_date(self, date_str):
        """Parse date string to datetime"""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None
    
    def get_recent_devices(self, company_name, limit=5):
        """Get recent devices for a company"""
        try:
            # Map company name to organization name
            org_name = self._map_company_to_org(company_name)
            
            devices = PulsewayDevice.objects.filter(
                organization_name__icontains=org_name
            ).order_by('-last_updated')[:limit]
            
            return [
                {
                    'device_name': device.device_name,
                    'status': device.status,
                    'organization_name': device.organization_name,
                    'last_seen': device.last_seen.strftime('%Y-%m-%d %H:%M') if device.last_seen else 'Never',
                    'operating_system': device.operating_system
                }
                for device in devices
            ]
        except Exception as e:
            logger.error(f"Error getting recent devices for {company_name}: {str(e)}")
            return []
    
    def get_devices_by_status(self, company_name, status):
        """Get devices by status for a company"""
        try:
            org_name = self._map_company_to_org(company_name)
            
            devices = PulsewayDevice.objects.filter(
                organization_name__icontains=org_name,
                status__iexact=status
            ).order_by('device_name')
            
            return [
                {
                    'device_name': device.device_name,
                    'status': device.status,
                    'ip_address': device.ip_address or 'N/A',
                    'operating_system': device.operating_system or 'N/A',
                    'last_seen': device.last_seen.strftime('%Y-%m-%d %H:%M') if device.last_seen else 'Never',
                    'cpu_usage': device.cpu_usage or 0,
                    'memory_usage': device.memory_usage or 0,
                    'disk_usage': device.disk_usage or 0
                }
                for device in devices
            ]
        except Exception as e:
            logger.error(f"Error getting {status} devices for {company_name}: {str(e)}")
            return []
    
    def get_all_devices(self, company_name):
        """Get all devices for a company"""
        try:
            org_name = self._map_company_to_org(company_name)
            
            devices = PulsewayDevice.objects.filter(
                organization_name__icontains=org_name
            ).order_by('device_name')
            
            return [
                {
                    'device_name': device.device_name,
                    'status': device.status,
                    'ip_address': device.ip_address or 'N/A',
                    'operating_system': device.operating_system or 'N/A',
                    'last_seen': device.last_seen.strftime('%Y-%m-%d %H:%M') if device.last_seen else 'Never',
                    'cpu_usage': device.cpu_usage or 0,
                    'memory_usage': device.memory_usage or 0,
                    'disk_usage': device.disk_usage or 0
                }
                for device in devices
            ]
        except Exception as e:
            logger.error(f"Error getting all devices for {company_name}: {str(e)}")
            return []
    
    def _map_company_to_org(self, company_name):
        """Resolve a canonical Company name to the best-matching Pulseway
        organisation_name stored in PulsewayDevice, using fuzzy matching so
        that minor spelling differences are tolerated.
        Falls back to the original name if no match is found.
        """
        from rbac.utils import normalize_company_name
        from difflib import SequenceMatcher

        norm_input = normalize_company_name(company_name)
        org_names = list(
            PulsewayDevice.objects.values_list('organization_name', flat=True)
            .exclude(organization_name='')
            .distinct()
        )

        best_org, best_ratio = company_name, 0.0
        for org in org_names:
            norm_org = normalize_company_name(org)
            if not norm_org:
                continue
            if norm_input in norm_org or norm_org in norm_input:
                return org  # substring hit — return immediately
            ratio = SequenceMatcher(None, norm_input, norm_org).ratio()
            if ratio > best_ratio and ratio >= 0.55:
                best_ratio = ratio
                best_org = org
        return best_org
