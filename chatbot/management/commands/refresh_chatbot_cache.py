"""
Management command: python manage.py refresh_chatbot_cache

Fetches live data from Office 365 (per real tenant) and Datto APIs and stores
snapshots in the ChatbotCache table so the chatbot can query them without
hitting the APIs on every message.

Schedule: every 6 hours via cron / Windows Task Scheduler.
"""
from django.core.management.base import BaseCommand
from chatbot.models import ChatbotCache


# Only tenants with real credentials — demo-mode tenants are skipped automatically
O365_CUSTOMERS = ['cgl', 'wepsol']


class Command(BaseCommand):
    help = 'Refresh chatbot cache: Office 365 and Datto data snapshots'

    def handle(self, *args, **options):
        self._refresh_office365()
        self._refresh_datto()
        self.stdout.write(self.style.SUCCESS('Chatbot cache refresh complete.'))

    # ── Office 365 ────────────────────────────────────────────────────────────

    def _refresh_office365(self):
        from office365.services import Office365API

        for key in O365_CUSTOMERS:
            self.stdout.write(f'  O365 [{key}] ...')
            try:
                api = Office365API(customer_key=key)
                if api._is_demo_mode():
                    self.stdout.write(f'    skipped (demo mode)')
                    continue

                # License summary
                self._save('office365', key, 'license_summary', api.get_license_summary())

                # User list (lightweight: name, upn, license count)
                users = api.get_all_users_with_licenses()
                self._save('office365', key, 'users', [
                    {'display_name': u['display_name'], 'upn': u['upn'],
                     'license_count': u['license_count'], 'licenses': u['licenses'],
                     'account_enabled': u['account_enabled'], 'department': u['department']}
                    for u in users
                ])

                # Mailbox usage
                mb = api.get_mailbox_usage()
                self._save('office365', key, 'mailbox_usage', {
                    'total_mailboxes': mb['total_mailboxes'],
                    'high_usage_count': len(mb['high_usage']),
                    'high_usage_users': mb['high_usage'][:20],   # top 20 for chatbot
                })

                # Teams usage summary
                teams = api.get_teams_usage()
                active = [t for t in teams if t['team_chat_messages'] > 0 or t['meetings'] > 0]
                self._save('office365', key, 'teams_summary', {
                    'total_users': len(teams),
                    'active_users': len(active),
                    'total_messages': sum(t['team_chat_messages'] + t['private_chat_messages'] for t in teams),
                    'total_meetings': sum(t['meetings'] for t in teams),
                    'top_users': sorted(teams, key=lambda x: x['team_chat_messages'], reverse=True)[:10]
                })

                # Email activity summary
                email = api.get_email_activity()
                email_active = [e for e in email if e['send_count'] > 0]
                self._save('office365', key, 'email_summary', {
                    'total_users': len(email),
                    'active_senders': len(email_active),
                    'total_sent': sum(e['send_count'] for e in email),
                    'total_received': sum(e['receive_count'] for e in email),
                })

                self.stdout.write(f'    OK — {len(users)} users, {mb["total_mailboxes"]} mailboxes')

            except Exception as e:
                self._save('office365', key, 'error', {}, success=False, error=str(e))
                self.stdout.write(self.style.WARNING(f'    FAILED: {e}'))

    # ── Datto ─────────────────────────────────────────────────────────────────

    def _refresh_datto(self):
        from datto.datto_client import DattoClient
        self.stdout.write('  Datto ...')
        try:
            client = DattoClient()

            # Storage pool
            raw = client.get_dtc_storage_pool()
            pools = raw if isinstance(raw, list) else [raw]
            enriched_pools = []
            for p in pools:
                total = (p.get('availableStorage', 0) or 0) + (p.get('usedStorage', 0) or 0)
                used = p.get('usedStorage', 0) or 0
                enriched_pools.append({
                    'name': p.get('poolName', 'Default Pool'),
                    'available_gb': round(p.get('availableStorage', 0), 2),
                    'used_gb': round(used, 2),
                    'total_gb': round(total, 2),
                    'usage_pct': round((used / total) * 100, 1) if total else 0,
                })
            self._save('datto', '', 'storage_pool', enriched_pools)

            # BCDR devices
            raw = client.get_devices()
            devices = raw.get('items', raw) if isinstance(raw, dict) else raw
            device_list = []
            for d in (devices or []):
                device_list.append({
                    'name': d.get('name', ''),
                    'serial': d.get('serialNumber', ''),
                    'model': d.get('model', ''),
                    'online': d.get('online', False),
                    'status': 'Online' if d.get('online') else 'Offline',
                    'internal_ip': d.get('internalIpAddress', ''),
                    'last_seen': d.get('lastSeenDate', ''),
                })
            self._save('datto', '', 'bcdr_devices', {
                'total': len(device_list),
                'online': sum(1 for d in device_list if d['online']),
                'offline': sum(1 for d in device_list if not d['online']),
                'devices': device_list,
            })

            # DTC assets
            try:
                raw = client.get_dtc_assets()
                assets = raw.get('items', raw) if isinstance(raw, dict) else raw
                self._save('datto', '', 'dtc_assets', {
                    'total': len(assets or []),
                    'assets': (assets or [])[:50],   # cap at 50 for storage
                })
            except Exception as e:
                self._save('datto', '', 'dtc_assets', {'total': 0, 'assets': []},
                           success=False, error=str(e))

            self.stdout.write(f'    OK — {len(device_list)} BCDR devices, {len(enriched_pools)} pools')

        except Exception as e:
            self._save('datto', '', 'error', {}, success=False, error=str(e))
            self.stdout.write(self.style.WARNING(f'    FAILED: {e}'))

    # ── Helper ────────────────────────────────────────────────────────────────

    def _save(self, source, company_key, data_type, payload, success=True, error=''):
        ChatbotCache.objects.update_or_create(
            source=source, company_key=company_key, data_type=data_type,
            defaults={'payload': payload, 'success': success, 'error': error}
        )
