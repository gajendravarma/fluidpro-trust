#!/usr/bin/env python3
"""
Ticket Status Synchronization Fix
Corrects the status mapping and ensures accurate ticket counts
"""

import os
import sys
import django

# Setup Django
sys.path.append('/home/devops-machine/Fluidtrust-project/claude-changes')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from tickets.models import TicketCache
from tickets.services import ManageEngineService
from django.db.models import Count
import json
import requests
from collections import Counter

def analyze_status_mapping():
    """Analyze current status mapping issues"""
    print("=== TICKET STATUS ANALYSIS ===")
    
    # Get local database status counts
    local_status_counts = TicketCache.objects.values('status').annotate(count=Count('id')).order_by('status')
    print("\n📊 LOCAL DATABASE STATUS COUNTS:")
    local_total = 0
    local_statuses = {}
    for item in local_status_counts:
        status = item['status']
        count = item['count']
        local_statuses[status] = count
        local_total += count
        print(f"  {status}: {count}")
    print(f"  TOTAL LOCAL: {local_total}")
    
    # Get API status counts
    service = ManageEngineService()
    url = f'{service.base_url}/requests'
    
    print("\n🌐 FETCHING API STATUS COUNTS...")
    api_statuses = Counter()
    api_total = 0
    
    try:
        # Get total count first
        input_data = {
            'list_info': {
                'row_count': 1,
                'start_index': 1,
                'get_total_count': True,
                'fields_required': ['id']
            }
        }
        
        response = requests.get(url, headers=service.headers, params={'input_data': json.dumps(input_data)})
        if response.status_code == 200:
            data = response.json()
            api_total = data.get('list_info', {}).get('total_count', 0)
            print(f"  Total tickets in API: {api_total}")
        
        # Sample recent tickets for status analysis
        input_data = {
            'list_info': {
                'row_count': 500,
                'start_index': 1,
                'fields_required': ['id', 'status'],
                'sort_field': 'created_time',
                'sort_order': 'desc'
            }
        }
        
        response = requests.get(url, headers=service.headers, params={'input_data': json.dumps(input_data)})
        if response.status_code == 200:
            data = response.json()
            tickets = data.get('requests', [])
            
            for ticket in tickets:
                status = ticket.get('status', {}).get('name', 'Unknown')
                api_statuses[status] += 1
            
            print(f"\n📊 API STATUS COUNTS (from {len(tickets)} recent tickets):")
            for status, count in sorted(api_statuses.items()):
                print(f"  {status}: {count}")
    
    except Exception as e:
        print(f"❌ Error fetching API data: {e}")
        return False
    
    # Analyze the mapping issues
    print("\n🔍 STATUS MAPPING ANALYSIS:")
    
    # Current dashboard logic (incorrect)
    current_open = local_statuses.get('Open', 0)
    current_pending = local_statuses.get('Pending', 0)
    current_hold = (local_statuses.get('Hold', 0) + 
                   local_statuses.get('On Hold', 0) + 
                   local_statuses.get('Onhold', 0) +
                   local_statuses.get('On Hold - For Spare', 0) +
                   local_statuses.get('On Hold – Business Dependency', 0) +
                   local_statuses.get('On Hold – User Dependency', 0) +
                   local_statuses.get('On Hold - Digtinctive Backend', 0) +
                   local_statuses.get('On Hold - For Commercial Approval', 0))
    
    print(f"  Current Dashboard Logic:")
    print(f"    Open: {current_open}")
    print(f"    Pending: {current_pending}")
    print(f"    Hold: {current_hold}")
    
    # Correct mapping based on actual statuses
    correct_open = local_statuses.get('Open', 0)
    correct_pending = local_statuses.get('Pending', 0)  # This status doesn't exist in our data
    correct_hold = (local_statuses.get('Onhold', 0) +
                   local_statuses.get('On Hold - For Spare', 0) +
                   local_statuses.get('On Hold – Business Dependency', 0) +
                   local_statuses.get('On Hold – User Dependency', 0) +
                   local_statuses.get('On Hold - Digtinctive Backend', 0) +
                   local_statuses.get('On Hold - For Commercial Approval', 0))
    
    print(f"\n  Correct Mapping Should Be:")
    print(f"    Open: {correct_open}")
    print(f"    Pending: {correct_pending}")
    print(f"    Hold: {correct_hold}")
    print(f"    Open + Hold Total: {correct_open + correct_hold}")
    
    # Check what technicians expect (61 total open+hold)
    expected_total = 61
    actual_total = correct_open + correct_hold
    
    print(f"\n🎯 TECHNICIAN EXPECTATION vs REALITY:")
    print(f"  Expected Open+Hold: {expected_total}")
    print(f"  Actual Open+Hold: {actual_total}")
    print(f"  Difference: {actual_total - expected_total}")
    
    if actual_total != expected_total:
        print(f"\n⚠️  DATA MISMATCH DETECTED!")
        print(f"  The local database has {actual_total} open+hold tickets")
        print(f"  But technicians report {expected_total} total")
        print(f"  This suggests sync issues or different filtering")
    
    return True

def fix_status_mapping():
    """Create the corrected status mapping logic"""
    print("\n🔧 CREATING STATUS MAPPING FIX...")
    
    fix_code = '''
def get_corrected_status_counts(status_counts):
    """
    Correct status mapping based on actual ManageEngine statuses
    """
    # Map all "On Hold" variations to hold_tickets
    hold_statuses = [
        'Onhold',
        'On Hold - For Spare', 
        'On Hold – Business Dependency',
        'On Hold – User Dependency',
        'On Hold - Digtinctive Backend',
        'On Hold - For Commercial Approval'
    ]
    
    open_tickets = status_counts.get('Open', 0)
    pending_tickets = status_counts.get('Pending', 0)  # Usually 0 in ManageEngine
    in_progress_tickets = status_counts.get('In Progress', 0)
    resolved_tickets = status_counts.get('Resolved', 0)
    closed_tickets = status_counts.get('Closed', 0)
    cancelled_tickets = status_counts.get('Cancelled', 0)
    under_observation = status_counts.get('Under Observation', 0)
    
    # Sum all hold variations
    hold_tickets = sum(status_counts.get(status, 0) for status in hold_statuses)
    
    return {
        'open': open_tickets,
        'pending': pending_tickets,
        'in_progress': in_progress_tickets,
        'hold': hold_tickets,
        'resolved': resolved_tickets,
        'closed': closed_tickets,
        'cancelled': cancelled_tickets,
        'under_observation': under_observation,
        'total_active': open_tickets + pending_tickets + in_progress_tickets + hold_tickets + under_observation
    }
'''
    
    # Write the fix to a file
    with open('/home/devops-machine/Fluidtrust-project/claude-changes/tickets/status_fix.py', 'w') as f:
        f.write(fix_code)
    
    print("✅ Status mapping fix created in tickets/status_fix.py")
    return True

def main():
    """Main function to analyze and fix status mapping"""
    print("🚀 TICKET STATUS SYNCHRONIZATION FIX")
    print("=" * 50)
    
    if analyze_status_mapping():
        fix_status_mapping()
        
        print("\n📋 RECOMMENDED ACTIONS:")
        print("1. Update dashboard view to use corrected status mapping")
        print("2. Verify sync process is capturing all ticket updates")
        print("3. Check if filtering is applied that technicians don't see")
        print("4. Consider real-time sync for critical status changes")
        
        print("\n✨ Next steps:")
        print("- Apply the status mapping fix to views.py")
        print("- Test the corrected counts")
        print("- Verify with technicians")

if __name__ == "__main__":
    main()
