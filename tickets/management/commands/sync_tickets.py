from django.core.management.base import BaseCommand
from django.db import OperationalError
from django.utils import timezone
from tickets.models import TicketCache, SyncStatus
from tickets.services import ManageEngineService
from datetime import datetime
import json
import time

class Command(BaseCommand):
    help = 'Sync tickets from ManageEngine to local database table'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=1000, help='Limit number of tickets to sync')

    def handle(self, *args, **options):
        self.stdout.write('Starting ticket sync to local database...')
        
        sync_status, created = SyncStatus.objects.get_or_create(
            id=1,
            defaults={'last_sync_time': timezone.now(), 'sync_status': 'running'}
        )
        sync_status.sync_status = 'running'
        sync_status.save()

        try:
            me_service = ManageEngineService()
            synced_count = 0
            batch_size = 100
            total_limit = options['limit']
            
            for batch_start in range(0, total_limit, batch_size):
                current_batch_size = min(batch_size, total_limit - batch_start)
                page = (batch_start // batch_size) + 1
                
                self.stdout.write(f'Fetching batch {page}...')
                
                tickets_data = self._fetch_tickets_batch(me_service, page, current_batch_size)
                
                if not tickets_data or 'requests' not in tickets_data:
                    break
                
                tickets = tickets_data['requests']
                if not tickets:
                    break
                
                for ticket_data in tickets:
                    if self._sync_ticket(ticket_data):
                        synced_count += 1
                
                if len(tickets) < current_batch_size:
                    break

            sync_status.last_sync_time = timezone.now()
            sync_status.total_tickets_synced = synced_count
            sync_status.sync_status = 'completed'
            sync_status.save()

            self.stdout.write(self.style.SUCCESS(f'Successfully synced {synced_count} tickets to local database'))

        except Exception as e:
            sync_status.sync_status = 'error'
            sync_status.error_message = str(e)
            sync_status.save()
            self.stdout.write(self.style.ERROR(f'Sync failed: {str(e)}'))

    def _fetch_tickets_batch(self, me_service, page, batch_size):
        url = f"{me_service.base_url}/requests"
        start_index = ((page - 1) * batch_size) + 1
        
        input_data = {
            "list_info": {
                "row_count": batch_size,
                "start_index": start_index,
                "sort_field": "created_time",
                "sort_order": "desc",
                "fields_required": [
                    "id", "subject", "description", "status", "priority", 
                    "category", "requester", "technician", "account",
                    "created_time", "last_updated_time", "resolved_time"
                ]
            }
        }
        
        try:
            import requests
            response = requests.get(url, headers=me_service.headers, params={'input_data': json.dumps(input_data)})
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            self.stdout.write(f'Error fetching batch: {e}')
            return None

    def _sync_ticket(self, ticket_data):
        ticket_id = str(ticket_data.get('id', ''))
        if not ticket_id:
            return False

        # Extract all ticket data
        subject = ticket_data.get('subject', '')
        description = ticket_data.get('description', '')

        status_data = ticket_data.get('status', {})
        status = status_data.get('name', 'Unknown') if isinstance(status_data, dict) else str(status_data)

        priority_data = ticket_data.get('priority', {})
        priority = priority_data.get('name', 'Medium') if isinstance(priority_data, dict) else str(priority_data)

        category_data = ticket_data.get('category', {})
        category = category_data.get('name', '') if isinstance(category_data, dict) else str(category_data)

        requester_data = ticket_data.get('requester', {})
        requester_name = requester_data.get('name', '') if isinstance(requester_data, dict) else ''
        requester_email = requester_data.get('email_id', '') if isinstance(requester_data, dict) else ''

        technician_data = ticket_data.get('technician', {})
        technician_name = technician_data.get('name', '') if isinstance(technician_data, dict) else ''

        account_data = ticket_data.get('account', {})
        company_name = account_data.get('name', '') if isinstance(account_data, dict) else ''

        created_at = self._parse_timestamp(ticket_data.get('created_time', {}))
        updated_at = self._parse_timestamp(ticket_data.get('last_updated_time', {}))
        resolved_at = self._parse_timestamp(ticket_data.get('resolved_time', {}))

        defaults = {
            'subject': subject,
            'description': description,
            'status': status,
            'priority': priority,
            'category': category,
            'requester_name': requester_name,
            'requester_email': requester_email,
            'technician_name': technician_name,
            'company_name': company_name,
            'created_at': created_at or timezone.now(),
            'updated_at': updated_at or timezone.now(),
            'resolved_at': resolved_at,
        }

        # Retry up to 3 times on database lock
        for attempt in range(3):
            try:
                TicketCache.objects.update_or_create(ticket_id=ticket_id, defaults=defaults)
                return True
            except OperationalError as e:
                if 'database is locked' in str(e) and attempt < 2:
                    wait = (attempt + 1) * 2  # 2s, 4s
                    self.stdout.write(f'DB locked on ticket {ticket_id}, retrying in {wait}s...')
                    time.sleep(wait)
                else:
                    self.stdout.write(f'Error syncing ticket {ticket_id}: {e}')
                    return False
            except Exception as e:
                self.stdout.write(f'Error syncing ticket {ticket_id}: {e}')
                return False

        return False

    def _parse_timestamp(self, time_data):
        if not time_data or not isinstance(time_data, dict):
            return None
        
        try:
            timestamp_value = time_data.get('value')
            if timestamp_value:
                if isinstance(timestamp_value, str):
                    timestamp_value = int(timestamp_value)
                return datetime.fromtimestamp(timestamp_value / 1000)
        except:
            pass
        
        return None
