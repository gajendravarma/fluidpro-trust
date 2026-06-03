"""
Management command: sync ManageEngine users to local DB (ManageEngineUser cache).

Fetches all users in batches from the ME API, stores them locally.
On subsequent runs only new/changed records are updated (upsert by me_id).

Usage:
    python manage.py sync_me_users
    python manage.py sync_me_users --force   # re-sync even if recently synced
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
import json, requests


class Command(BaseCommand):
    help = 'Sync ManageEngine users to local database cache'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Force full re-sync')

    def handle(self, *args, **options):
        from tickets.models import ManageEngineUser
        from tickets.services import ManageEngineService

        svc = ManageEngineService()
        batch_size = 100
        start = 1
        total_created = 0

        self.stdout.write('Syncing ManageEngine users...')

        while True:
            input_data = {
                'list_info': {
                    'row_count': batch_size,
                    'start_index': start,
                    'fields_required': [
                        'id', 'name', 'email_id', 'phone',
                        'department', 'is_technician', 'account'
                    ]
                }
            }
            try:
                resp = requests.get(
                    f'{svc.base_url}/users',
                    headers=svc.headers,
                    params={'input_data': json.dumps(input_data)},
                    timeout=30
                )
                data = resp.json() if resp.status_code == 200 else None
            except Exception as e:
                self.stderr.write(f'API error at start={start}: {e}')
                break

            if not data or 'users' not in data or not data['users']:
                break

            users = data['users']

            batch = []
            for u in users:
                me_id = str(u.get('id', ''))
                if not me_id:
                    continue

                dept = u.get('department', {})
                department = dept.get('name', '') if isinstance(dept, dict) else ''

                account = u.get('account', {})
                company_name = account.get('name', '') if isinstance(account, dict) else ''

                email = u.get('email_id') or None

                batch.append(ManageEngineUser(
                    me_id=me_id,
                    name=u.get('name') or '',
                    email=email,
                    phone=u.get('phone') or '',
                    department=department,
                    company_name=company_name,
                    is_technician=bool(u.get('is_technician', False)),
                    is_active=True,
                ))

            created = ManageEngineUser.objects.bulk_create(
                batch,
                update_conflicts=True,
                unique_fields=['me_id'],
                update_fields=['name', 'email', 'phone', 'department', 'company_name', 'is_technician', 'is_active', 'last_synced'],
            )
            total_created += len(created)

            # If fewer rows returned than requested, we've hit the end
            if len(users) < batch_size:
                break
            start += batch_size

        self.stdout.write(self.style.SUCCESS(
            f'Done. Synced: {total_created}, Total in DB: {ManageEngineUser.objects.count()}'
        ))
