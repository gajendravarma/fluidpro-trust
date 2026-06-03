#!/usr/bin/env python3
"""
Complete Ticket Synchronization Fix
Forces fresh sync and fixes status mapping
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

def force_fresh_sync():
    """Force a complete fresh sync from ManageEngine API"""
    print("🔄 FORCING FRESH TICKET SYNC...")
    
    # Clear old sync status
    SyncStatus.objects.all().delete()
    
    # Clear old ticket cache
    print("  Clearing old ticket cache...")
    TicketCache.objects.all().delete()
    
    service = ManageEngineService()
    url = f'{service.base_url}/requests'
    
    try:
        # Create new sync status
        sync_status = SyncStatus.objects.create(
            last_sync_time=timezone.now(),
            sync_status='running',
            total_tickets_synced=0
        )
        
        # Get total count
        input_data = {
            'list_info': {
                'row_count': 1,
                'start_index': 1,
                'get_total_count': True,
                'fields_required': ['id']
            }
        }
        
        response = requests.get(url, headers=service.headers, params={'input_data': json.dumps(input_data)})
        if response.status_code != 200:
            raise Exception(f"API Error: {response.status_code}")
            
        data = response.json()
        total_tickets = data.get('list_info', {}).get('total_count', 0)
        print(f"  Total tickets to sync: {total_tickets}")
        
        # Sync in batches
        batch_size = 100
        total_synced = 0
        
        for batch_num in range(0, min(total_tickets, 1000), batch_size):  # Limit to 1000 for now
            start_index = batch_num + 1
            
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
            
            response = requests.get(url, headers=service.headers, params={'input_data': json.dumps(input_data)})
            if response.status_code != 200:
                print(f"  ❌ Error in batch {batch_num//batch_size + 1}: {response.status_code}")
                continue
                
            batch_data = response.json()
            tickets = batch_data.get('requests', [])
            
            # Process tickets
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
                    
                    # Create ticket cache entry
                    TicketCache.objects.update_or_create(
                        ticket_id=str(ticket.get('id')),
                        defaults={
                            'subject': ticket.get('subject', ''),
                            'description': ticket.get('description', ''),
                            'status': ticket.get('status', {}).get('name', 'Unknown'),
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
                    total_synced += 1
                    
                except Exception as e:
                    print(f"    Error processing ticket {ticket.get('id')}: {e}")
                    continue
            
            print(f"  ✅ Synced batch {batch_num//batch_size + 1}: {len(tickets)} tickets")
            
            # Update sync status
            sync_status.total_tickets_synced = total_synced
            sync_status.save()
        
        # Mark sync as completed
        sync_status.sync_status = 'completed'
        sync_status.last_sync_time = timezone.now()
        sync_status.save()
        
        print(f"✅ Sync completed! Total tickets synced: {total_synced}")
        return True
        
    except Exception as e:
        print(f"❌ Sync failed: {e}")
        if 'sync_status' in locals():
            sync_status.sync_status = 'error'
            sync_status.error_message = str(e)
            sync_status.save()
        return False

def update_dashboard_view():
    """Update the dashboard view with correct status mapping"""
    print("\n🔧 UPDATING DASHBOARD VIEW...")
    
    dashboard_fix = '''
    # Get statistics from local database
    status_counts = dashboard_data['status_counts']
    total_tickets = dashboard_data['total_tickets']
    
    # CORRECTED STATUS MAPPING - matches actual ManageEngine statuses
    open_tickets = status_counts.get('Open', 0)
    pending_tickets = status_counts.get('Pending', 0)  # Usually 0 in ManageEngine
    in_progress_tickets = status_counts.get('In Progress', 0)
    
    # Sum all "On Hold" variations correctly
    hold_tickets = (
        status_counts.get('Onhold', 0) +
        status_counts.get('On Hold - For Spare', 0) +
        status_counts.get('On Hold – Business Dependency', 0) +
        status_counts.get('On Hold – User Dependency', 0) +
        status_counts.get('On Hold - Digtinctive Backend', 0) +
        status_counts.get('On Hold - For Commercial Approval', 0)
    )
    
    resolved_tickets = status_counts.get('Resolved', 0)
    closed_tickets = status_counts.get('Closed', 0)
    cancelled_tickets = status_counts.get('Cancelled', 0)
    under_observation = status_counts.get('Under Observation', 0)
    
    # Total active tickets (what technicians care about)
    active_tickets = open_tickets + pending_tickets + in_progress_tickets + hold_tickets + under_observation
    '''
    
    # Read current dashboard view
    dashboard_path = '/home/devops-machine/Fluidtrust-project/claude-changes/tickets/views.py'
    with open(dashboard_path, 'r') as f:
        content = f.read()
    
    # Find the section to replace
    start_marker = "# Calculate ticket counts by status"
    end_marker = "# Calculate percentages"
    
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)
    
    if start_idx != -1 and end_idx != -1:
        # Replace the section
        new_content = (
            content[:start_idx] + 
            "# Calculate ticket counts by status - CORRECTED MAPPING\n" +
            dashboard_fix + "\n    " +
            content[end_idx:]
        )
        
        # Write back
        with open(dashboard_path, 'w') as f:
            f.write(new_content)
        
        print("✅ Dashboard view updated with correct status mapping")
        return True
    else:
        print("❌ Could not find section to update in dashboard view")
        return False

def main():
    """Main execution function"""
    print("🚀 COMPLETE TICKET SYNCHRONIZATION FIX")
    print("=" * 50)
    
    # Step 1: Force fresh sync
    if force_fresh_sync():
        print("\n📊 CHECKING NEW DATA...")
        
        # Check new counts
        from django.db.models import Count
        status_counts = TicketCache.objects.values('status').annotate(count=Count('id')).order_by('status')
        
        open_count = 0
        hold_count = 0
        total_count = 0
        
        print("\nNew status counts:")
        for item in status_counts:
            status = item['status']
            count = item['count']
            total_count += count
            
            if status == 'Open':
                open_count = count
            elif 'Hold' in status or status == 'Onhold':
                hold_count += count
                
            print(f"  {status}: {count}")
        
        print(f"\nSummary:")
        print(f"  Open: {open_count}")
        print(f"  Hold (all variations): {hold_count}")
        print(f"  Open + Hold: {open_count + hold_count}")
        print(f"  Total: {total_count}")
        
        # Step 2: Update dashboard view
        update_dashboard_view()
        
        print(f"\n✅ FIX COMPLETED!")
        print(f"🔗 Check the updated dashboard at: http://192.168.2.68:8000/tickets/")
        print(f"📊 New Open + Hold count: {open_count + hold_count}")
        
    else:
        print("❌ Sync failed. Please check the error messages above.")

if __name__ == "__main__":
    main()
