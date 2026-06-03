from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from tickets.models import TicketCache, SyncStatus
from tickets.services import ManageEngineService
from datetime import datetime, timedelta
import json

class Command(BaseCommand):
    help = 'Incremental sync - only sync new/updated tickets'

    def handle(self, *args, **options):
        self.stdout.write('Starting incremental ticket sync...')
        
        try:
            # Get last sync time
            sync_status = SyncStatus.objects.filter(id=1).first()
            last_sync = sync_status.last_sync_time if sync_status else timezone.now() - timedelta(days=7)
            
            me_service = ManageEngineService()
            
            # Get tickets updated since last sync
            updated_tickets = self._get_updated_tickets(me_service, last_sync)
            
            synced_count = 0
            with transaction.atomic():
                for ticket_data in updated_tickets:
                    ticket_id = str(ticket_data.get('id', ''))
                    
                    # Check if ticket exists and needs update
                    existing_ticket = TicketCache.objects.filter(ticket_id=ticket_id).first()
                    
                    # Parse updated time from API
                    api_updated_time = self._parse_timestamp(ticket_data.get('last_updated_time', {}))
                    
                    # Only update if ticket is new or has been modified
                    if not existing_ticket or (api_updated_time and api_updated_time > existing_ticket.updated_at):
                        if self._sync_ticket(ticket_data):
                            synced_count += 1
                            self.stdout.write(f'Updated ticket {ticket_id}')
            
            # Update sync status
            sync_status, created = SyncStatus.objects.get_or_create(id=1)
            sync_status.last_sync_time = timezone.now()
            sync_status.total_tickets_synced = TicketCache.objects.count()
            sync_status.sync_status = 'completed'
            sync_status.save()
            
            self.stdout.write(self.style.SUCCESS(f'Incremental sync completed: {synced_count} tickets updated'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Incremental sync failed: {str(e)}'))

    def _get_updated_tickets(self, me_service, since_date):
        """Get ALL tickets updated since given date — paginated, no cap.
        ManageEngine API hard-caps at 100 rows per page regardless of row_count."""
        import requests as req_lib

        url = f"{me_service.base_url}/requests"
        batch_size = 100  # ME API hard cap
        start = 1
        all_tickets = []

        while True:
            input_data = {
                "list_info": {
                    "row_count": batch_size,
                    "start_index": start,
                    "sort_field": "last_updated_time",
                    "sort_order": "desc",
                    "fields_required": [
                        "id", "subject", "description", "status", "priority",
                        "category", "requester", "technician", "account",
                        "created_time", "last_updated_time", "resolved_time"
                    ]
                }
            }

            try:
                response = req_lib.get(
                    url, headers=me_service.headers,
                    params={'input_data': json.dumps(input_data)},
                    timeout=30
                )
                if response.status_code != 200:
                    break
                data = response.json()
                tickets = data.get('requests', [])
                if not tickets:
                    break

                reached_old = False
                for ticket in tickets:
                    updated_time = self._parse_timestamp(ticket.get('last_updated_time', {}))
                    if updated_time and updated_time >= since_date:
                        all_tickets.append(ticket)
                    else:
                        # Results are sorted desc — once we see one older than since_date,
                        # all remaining pages will also be older
                        reached_old = True
                        break

                if reached_old or len(tickets) < batch_size:
                    break

                start += batch_size

            except Exception as e:
                self.stdout.write(f'Error fetching updated tickets: {e}')
                break

        return all_tickets

    def _sync_ticket(self, ticket_data):
        """Same sync logic as full sync"""
        try:
            ticket_id = str(ticket_data.get('id', ''))
            if not ticket_id:
                return False

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
            
            from django.utils import timezone
            ticket_cache, created = TicketCache.objects.update_or_create(
                ticket_id=ticket_id,
                defaults={
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
            )
            
            return True
            
        except Exception as e:
            return False

    def _parse_timestamp(self, time_data):
        """USE_TZ=False — return naive local datetime, SQLite doesn't support aware datetimes."""
        if not time_data or not isinstance(time_data, dict):
            return None
        try:
            timestamp_value = time_data.get('value')
            if timestamp_value:
                if isinstance(timestamp_value, str):
                    timestamp_value = int(timestamp_value)
                return datetime.fromtimestamp(timestamp_value / 1000)
        except Exception:
            pass
        return None
