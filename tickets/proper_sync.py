
from tickets.services import ManageEngineService
from tickets.models import TicketCache, SyncStatus
from django.utils import timezone
from datetime import datetime
import json
import requests
import logging

logger = logging.getLogger(__name__)

class ProperSyncService:
    """Efficient ticket synchronization service"""
    
    def __init__(self):
        self.service = ManageEngineService()
        self.batch_size = 100
    
    def sync_all_tickets(self):
        """Sync all tickets efficiently with proper error handling"""
        try:
            # Mark sync as running
            sync_status = SyncStatus.objects.create(
                last_sync_time=timezone.now(),
                sync_status='running',
                total_tickets_synced=0
            )
            
            # Get total count
            total_count = self._get_total_count()
            logger.info(f"Starting sync of {total_count} tickets")
            
            # Clear old data
            TicketCache.objects.all().delete()
            
            synced_count = 0
            batch_num = 0
            
            while synced_count < total_count:
                start_index = (batch_num * self.batch_size) + 1
                
                tickets = self._fetch_batch(start_index, self.batch_size)
                if not tickets:
                    break
                
                # Process batch
                for ticket in tickets:
                    if self._process_ticket(ticket):
                        synced_count += 1
                
                batch_num += 1
                logger.info(f"Synced batch {batch_num}: {len(tickets)} tickets")
                
                # Update progress
                sync_status.total_tickets_synced = synced_count
                sync_status.save()
            
            # Mark as completed
            sync_status.sync_status = 'completed'
            sync_status.last_sync_time = timezone.now()
            sync_status.save()
            
            logger.info(f"Sync completed: {synced_count} tickets")
            return synced_count
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            if 'sync_status' in locals():
                sync_status.sync_status = 'error'
                sync_status.error_message = str(e)
                sync_status.save()
            return 0
    
    def _get_total_count(self):
        """Get total ticket count"""
        url = f"{self.service.base_url}/requests"
        input_data = {
            'list_info': {
                'row_count': 1,
                'start_index': 1,
                'get_total_count': True,
                'fields_required': ['id']
            }
        }
        
        response = requests.get(url, headers=self.service.headers, 
                              params={'input_data': json.dumps(input_data)})
        
        if response.status_code == 200:
            data = response.json()
            return data.get('list_info', {}).get('total_count', 0)
        return 0
    
    def _fetch_batch(self, start_index, batch_size):
        """Fetch a batch of tickets"""
        url = f"{self.service.base_url}/requests"
        input_data = {
            'list_info': {
                'row_count': batch_size,
                'start_index': start_index,
                'fields_required': [
                    'id', 'subject', 'description', 'status', 'priority',
                    'category', 'requester', 'technician', 'created_time',
                    'last_updated_time', 'resolved_time', 'account'
                ],
                'sort_field': 'created_time',
                'sort_order': 'desc'
            }
        }
        
        try:
            response = requests.get(url, headers=self.service.headers,
                                  params={'input_data': json.dumps(input_data)})
            
            if response.status_code == 200:
                data = response.json()
                return data.get('requests', [])
        except Exception as e:
            logger.error(f"Error fetching batch {start_index}: {e}")
        
        return []
    
    def _process_ticket(self, ticket):
        """Process individual ticket with proper error handling"""
        try:
            # Safe field extraction
            ticket_id = str(ticket.get('id', ''))
            if not ticket_id:
                return False
            
            # Parse timestamps safely
            created_at = self._parse_timestamp(ticket.get('created_time'))
            updated_at = self._parse_timestamp(ticket.get('last_updated_time')) or created_at
            resolved_at = self._parse_timestamp(ticket.get('resolved_time'))
            
            # Safe field extraction with defaults
            status_obj = ticket.get('status') or {}
            priority_obj = ticket.get('priority') or {}
            category_obj = ticket.get('category') or {}
            requester_obj = ticket.get('requester') or {}
            technician_obj = ticket.get('technician') or {}
            account_obj = ticket.get('account') or {}
            
            # Create/update ticket
            TicketCache.objects.update_or_create(
                ticket_id=ticket_id,
                defaults={
                    'subject': ticket.get('subject', '')[:500],  # Limit length
                    'description': ticket.get('description', '')[:1000],
                    'status': status_obj.get('name', 'Unknown'),
                    'priority': priority_obj.get('name', 'Normal'),
                    'category': category_obj.get('name', ''),
                    'requester_name': requester_obj.get('name', ''),
                    'requester_email': requester_obj.get('email_id', ''),
                    'technician_name': technician_obj.get('name', ''),
                    'company_name': account_obj.get('name', ''),
                    'created_at': created_at,
                    'updated_at': updated_at,
                    'resolved_at': resolved_at,
                    'last_synced': timezone.now()
                }
            )
            return True
            
        except Exception as e:
            logger.error(f"Error processing ticket {ticket.get('id')}: {e}")
            return False
    
    def _parse_timestamp(self, timestamp_obj):
        """Safely parse timestamp"""
        if not timestamp_obj:
            return None
            
        try:
            if isinstance(timestamp_obj, dict) and 'value' in timestamp_obj:
                timestamp_value = timestamp_obj['value']
                if isinstance(timestamp_value, str):
                    timestamp_value = int(timestamp_value)
                return datetime.fromtimestamp(timestamp_value / 1000)
        except:
            pass
        
        return None
    
    def incremental_sync(self):
        """Sync only recent changes for performance"""
        try:
            # Get last sync time
            last_sync = SyncStatus.objects.filter(sync_status='completed').last()
            if not last_sync:
                return self.sync_all_tickets()
            
            # Sync tickets updated since last sync
            # Implementation for incremental sync
            pass
            
        except Exception as e:
            logger.error(f"Incremental sync failed: {e}")
            return 0
