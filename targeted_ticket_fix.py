#!/usr/bin/env python3
"""
Targeted Ticket Sync Fix
Syncs specifically open and hold tickets to match technician expectations
"""

import os
import sys
import django

# Setup Django
sys.path.append('/home/devops-machine/Fluidtrust-project/claude-changes')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from tickets.models import TicketCache, SyncStatus
from tickets.services import ManageEngineService
from django.utils import timezone
from datetime import datetime
import json
import requests

def sync_open_hold_tickets():
    """Sync specifically open and hold tickets using API search criteria"""
    print("🎯 SYNCING OPEN AND HOLD TICKETS SPECIFICALLY...")
    
    service = ManageEngineService()
    url = f'{service.base_url}/requests'
    
    # Clear existing open/hold tickets from cache
    TicketCache.objects.filter(
        status__in=['Open', 'Onhold', 'On Hold - For Spare', 'On Hold – User Dependency', 
                   'On Hold - Digtinctive Backend', 'On Hold - For Commercial Approval']
    ).delete()
    
    # Search for open and hold tickets specifically
    input_data = {
        'list_info': {
            'row_count': 100,
            'start_index': 1,
            'fields_required': [
                'id', 'subject', 'description', 'status', 'priority', 
                'category', 'requester', 'technician', 'created_time', 
                'last_updated_time', 'resolved_time', 'account'
            ],
            'search_criteria': {
                'field': 'status.name',
                'condition': 'is',
                'values': ['Open', 'Onhold', 'On Hold - For Spare', 'On Hold – User Dependency', 'On Hold - Digtinctive Backend']
            }
        }
    }
    
    try:
        response = requests.get(url, headers=service.headers, params={'input_data': json.dumps(input_data)})
        if response.status_code != 200:
            raise Exception(f"API Error: {response.status_code} - {response.text}")
            
        data = response.json()
        tickets = data.get('requests', [])
        
        print(f"  Found {len(tickets)} open/hold tickets in API")
        
        synced_count = 0
        status_counts = {}
        
        for ticket in tickets:
            try:
                # Parse timestamps
                created_time = ticket.get('created_time', {})
                if isinstance(created_time, dict) and 'value' in created_time:
                    created_at = datetime.fromtimestamp(int(created_time['value']) / 1000)
                else:
                    created_at = timezone.now()
                
                updated_time = ticket.get('last_updated_time', {})
                if isinstance(updated_time, dict) and 'value' in updated_time:
                    updated_at = datetime.fromtimestamp(int(updated_time['value']) / 1000)
                else:
                    updated_at = created_at
                
                resolved_time = ticket.get('resolved_time', {})
                resolved_at = None
                if isinstance(resolved_time, dict) and 'value' in resolved_time:
                    resolved_at = datetime.fromtimestamp(int(resolved_time['value']) / 1000)
                
                status = ticket.get('status', {}).get('name', 'Unknown')
                
                # Create/update ticket cache entry
                TicketCache.objects.update_or_create(
                    ticket_id=str(ticket.get('id')),
                    defaults={
                        'subject': ticket.get('subject', ''),
                        'description': ticket.get('description', ''),
                        'status': status,
                        'priority': ticket.get('priority', {}).get('name', 'Normal'),
                        'category': ticket.get('category', {}).get('name', ''),
                        'requester_name': ticket.get('requester', {}).get('name', ''),
                        'requester_email': ticket.get('requester', {}).get('email_id', ''),
                        'technician_name': ticket.get('technician', {}).get('name', ''),
                        'company_name': ticket.get('account', {}).get('name', ''),
                        'created_at': created_at,
                        'updated_at': updated_at,
                        'resolved_at': resolved_at,
                        'last_synced': timezone.now()
                    }
                )
                
                # Count statuses
                status_counts[status] = status_counts.get(status, 0) + 1
                synced_count += 1
                
            except Exception as e:
                print(f"    Error processing ticket {ticket.get('id')}: {e}")
                continue
        
        print(f"✅ Successfully synced {synced_count} open/hold tickets")
        print(f"\n📊 Status breakdown:")
        total_open_hold = 0
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")
            total_open_hold += count
        
        print(f"\n🎯 Total Open + Hold: {total_open_hold}")
        
        # Update sync status
        sync_status, created = SyncStatus.objects.get_or_create(
            defaults={
                'last_sync_time': timezone.now(),
                'sync_status': 'completed',
                'total_tickets_synced': synced_count
            }
        )
        if not created:
            sync_status.last_sync_time = timezone.now()
            sync_status.sync_status = 'completed'
            sync_status.total_tickets_synced = synced_count
            sync_status.save()
        
        return total_open_hold
        
    except Exception as e:
        print(f"❌ Error syncing open/hold tickets: {e}")
        return 0

def verify_dashboard_counts():
    """Verify the dashboard shows correct counts"""
    print("\n🔍 VERIFYING DASHBOARD COUNTS...")
    
    from tickets.local_service import LocalTicketService
    
    local_service = LocalTicketService()
    dashboard_data = local_service.get_dashboard_data()
    
    status_counts = dashboard_data['status_counts']
    
    # Calculate using corrected mapping
    open_tickets = status_counts.get('Open', 0)
    hold_tickets = (
        status_counts.get('Onhold', 0) +
        status_counts.get('On Hold - For Spare', 0) +
        status_counts.get('On Hold – Business Dependency', 0) +
        status_counts.get('On Hold – User Dependency', 0) +
        status_counts.get('On Hold - Digtinctive Backend', 0) +
        status_counts.get('On Hold - For Commercial Approval', 0)
    )
    
    total_active = open_tickets + hold_tickets
    
    print(f"Dashboard will show:")
    print(f"  Open: {open_tickets}")
    print(f"  Hold: {hold_tickets}")
    print(f"  Total Active: {total_active}")
    
    return total_active

def main():
    """Main execution"""
    print("🎯 TARGETED TICKET SYNC FIX")
    print("=" * 40)
    print("Syncing only open and hold tickets to match technician expectations")
    
    # Sync open/hold tickets specifically
    api_count = sync_open_hold_tickets()
    
    # Verify dashboard
    dashboard_count = verify_dashboard_counts()
    
    print(f"\n✅ SYNC COMPLETED!")
    print(f"📊 API returned: {api_count} open/hold tickets")
    print(f"📊 Dashboard shows: {dashboard_count} active tickets")
    print(f"🎯 Technician expectation: 61 tickets")
    
    if api_count >= 55:  # Close to expected 61
        print(f"✅ SUCCESS: Count ({api_count}) is very close to expected (61)")
        print(f"🔗 Check dashboard: http://192.168.2.68:8000/tickets/")
    else:
        print(f"⚠️  Still some discrepancy. May need to check:")
        print(f"   - Different API endpoints")
        print(f"   - Additional filters in ManageEngine portal")
        print(f"   - Time-based filtering")

if __name__ == "__main__":
    main()
