"""
Management command: full_sync_from_api

Fetches EVERY Pulseway device's detail from the live API one by one,
compares with the current DB value, and updates any that differ.

Usage:
    python manage.py full_sync_from_api
    python manage.py full_sync_from_api --delay 1.5   (seconds between API calls)
    python manage.py full_sync_from_api --org "CG Log"  (one org only)
"""
import time
from django.core.management.base import BaseCommand
from django.db import transaction
from pulseway.models import PulsewayDevice
from pulseway.services import PulsewayAPI
from pulseway.local_service import PulsewayLocalService


class Command(BaseCommand):
    help = 'Compare live Pulseway API data with DB and update all discrepancies'

    def add_arguments(self, parser):
        parser.add_argument('--delay', type=float, default=1.5,
                            help='Seconds between API calls (default 1.5)')
        parser.add_argument('--org', type=str, default='',
                            help='Filter by org name substring (default: all orgs)')

    def handle(self, *args, **options):
        delay = options['delay']
        org_filter = options['org']

        api = PulsewayAPI()
        svc = PulsewayLocalService()

        qs = PulsewayDevice.objects.all()
        if org_filter:
            qs = qs.filter(organization_name__icontains=org_filter)

        devices = list(qs.values('device_id', 'device_name', 'organization_name',
                                  'status', 'uptime', 'ip_address', 'operating_system'))

        self.stdout.write(self.style.SUCCESS(
            f'\n=== Pulseway Full Sync: {len(devices)} devices'
            f'{f" ({org_filter})" if org_filter else ""} | {delay}s delay ===\n'
        ))

        changed = 0
        skipped_429 = 0
        skipped_404 = 0
        errors = 0
        total = len(devices)

        for i, dev in enumerate(devices):
            device_id = dev['device_id']
            device_name = dev['device_name']
            old_status = dev['status']
            old_uptime = dev['uptime']

            if i > 0:
                time.sleep(delay)

            if i % 20 == 0:
                self.stdout.write(f'  [{i+1}/{total}] processing...')

            try:
                detail = api.get_device_details(device_id)
                if not detail:
                    skipped_429 += 1
                    continue

                data = detail.get('Data', detail) if isinstance(detail, dict) else {}
                uptime = data.get('Uptime', '')
                has_is_online = 'IsOnline' in data
                has_detail = has_is_online or bool(uptime)

                if not has_detail:
                    skipped_429 += 1
                    continue

                if has_is_online:
                    is_online = bool(data['IsOnline'])
                else:
                    is_online = bool(uptime) and 'offline' not in uptime.lower()

                new_status = 'online' if is_online else 'offline'
                ip = data.get('IPAddress') or data.get('IpAddress') or ''
                os_val = data.get('OperatingSystem') or data.get('OSDescription') or ''
                mac = data.get('MACAddress', '')
                cpu = svc._parse_percentage(data.get('CPUUsage'))
                mem = svc._parse_percentage(data.get('MemoryUsage'))
                disk = svc._parse_percentage(data.get('DiskUsage'))
                patches = data.get('PendingPatches', 0) or 0
                last_seen = svc._parse_date(data.get('LastSeen'))

                updates = {
                    'status': new_status,
                    'uptime': uptime,
                    'ip_address': ip or dev['ip_address'],
                    'operating_system': os_val or dev['operating_system'],
                    'mac_address': mac,
                    'pending_patches': patches,
                }
                if cpu is not None: updates['cpu_usage'] = cpu
                if mem is not None: updates['memory_usage'] = mem
                if disk is not None: updates['disk_usage'] = disk
                if last_seen: updates['last_seen'] = last_seen

                PulsewayDevice.objects.filter(device_id=device_id).update(**updates)

                if old_status != new_status or old_uptime != uptime:
                    changed += 1
                    new_label = 'ONLINE' if new_status == 'online' else 'offline'
                    msg = (f'  CHANGED: {device_name:40} '
                           f'{(dev["organization_name"] or "")[:24]:24} '
                           f'{old_status} -> {new_label}  [{uptime}]')
                    self.stdout.write(msg)

            except Exception as e:
                err_str = str(e)
                if '404' in err_str:
                    PulsewayDevice.objects.filter(device_id=device_id).delete()
                    skipped_404 += 1
                    self.stdout.write(f'  REMOVED (404): {device_name}')
                elif '429' in err_str:
                    skipped_429 += 1
                else:
                    errors += 1
                    self.stdout.write(self.style.WARNING(f'  ERROR: {device_name}: {err_str[:80]}'))

        # Final summary
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS(
            f'Done: {total} checked  |  {changed} updated  |  '
            f'{skipped_429} still rate-limited  |  '
            f'{skipped_404} removed (404)  |  {errors} errors'
        ))

        # Show final counts per org
        self.stdout.write('\nFinal status by org:')
        from django.db.models import Count, Q
        orgs = PulsewayDevice.objects.values('organization_name').annotate(
            total=Count('id'),
            online=Count('id', filter=Q(status='online')),
            no_uptime=Count('id', filter=Q(uptime=''))
        ).order_by('-total')
        for o in orgs:
            warn = ' [!] rate-limited' if o['no_uptime'] > 0 else ''
            self.stdout.write(
                f"  {(o['organization_name'] or 'Unknown')[:34]:34} "
                f"total={o['total']:4}  online={o['online']:4}  "
                f"unknown={o['no_uptime']}{warn}"
            )
