#!/usr/bin/env python3
"""
Script to check ManageEngine dashboard data for duplicate tickets
and analyze the 300 tickets being fetched via multiple API calls.
"""

import os
import sys
import django
from collections import Counter, defaultdict
from datetime import datetime

# Setup Django environment
sys.path.append('/home/devops-machine/Fluidtrust-project/customer_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from tickets.services import ManageEngineService
from pulseway.manageengine_service import ManageEngineAPI

def check_ticket_duplicates():
    """Check for duplicate tickets in the fetched data"""
    print("=== ManageEngine Ticket Duplicate Analysis ===\n")
    
    # Initialize services
    me_service = ManageEngineService()
    me_api = ManageEngineAPI()
    
    print("1. Fetching tickets via ManageEngineService (300 tickets)...")
    historical_data = me_service.get_historical_tickets(months=2)
    
    print("2. Fetching tickets via ManageEngineAPI (300 tickets)...")
    api_tickets = me_api.get_tickets(row_count=300)
    
    # Analyze ManageEngineService data
    service_tickets = []
    if historical_data and 'recent_tickets' in historical_data:
        service_tickets = historical_data['recent_tickets']
    
    print(f"\n=== RESULTS ===")
    print(f"ManageEngineService fetched: {len(service_tickets)} tickets")
    print(f"ManageEngineAPI fetched: {len(api_tickets)} tickets")
    
    # Check for duplicates within each dataset
    print(f"\n=== DUPLICATE ANALYSIS ===")
    
    # Check service tickets for duplicates
    service_ids = [ticket.get('id') for ticket in service_tickets if ticket.get('id')]
    service_duplicates = [id for id, count in Counter(service_ids).items() if count > 1]
    
    # Check API tickets for duplicates  
    api_ids = [ticket.get('id') for ticket in api_tickets if ticket.get('id')]
    api_duplicates = [id for id, count in Counter(api_ids).items() if count > 1]
    
    print(f"Service tickets - Unique IDs: {len(set(service_ids))}, Total: {len(service_ids)}")
    print(f"Service duplicates found: {len(service_duplicates)}")
    if service_duplicates:
        print(f"Duplicate IDs: {service_duplicates}")
    
    print(f"\nAPI tickets - Unique IDs: {len(set(api_ids))}, Total: {len(api_ids)}")
    print(f"API duplicates found: {len(api_duplicates)}")
    if api_duplicates:
        print(f"Duplicate IDs: {api_duplicates}")
    
    # Check overlap between the two datasets
    service_id_set = set(service_ids)
    api_id_set = set(api_ids)
    overlap = service_id_set.intersection(api_id_set)
    
    print(f"\n=== OVERLAP ANALYSIS ===")
    print(f"Common tickets between both datasets: {len(overlap)}")
    print(f"Service-only tickets: {len(service_id_set - api_id_set)}")
    print(f"API-only tickets: {len(api_id_set - service_id_set)}")
    
    # Detailed analysis of fetching methods
    print(f"\n=== FETCHING METHOD ANALYSIS ===")
    
    # Check how ManageEngineService fetches data
    print("ManageEngineService method:")
    print("- Uses get_historical_tickets() with 3 batches of 100 tickets each")
    print("- Fetches tickets in descending order by created_time")
    print("- Filters by date (last 2 months)")
    
    print("\nManageEngineAPI method:")
    print("- Uses get_tickets() with pagination")
    print("- Fetches in batches of 100 until reaching row_count limit")
    print("- Uses caching with 5-minute timeout")
    
    # Check if there are any issues with the current implementation
    print(f"\n=== POTENTIAL ISSUES ===")
    
    issues_found = False
    
    if service_duplicates:
        print("❌ ISSUE: Duplicate tickets found in ManageEngineService data")
        issues_found = True
    
    if api_duplicates:
        print("❌ ISSUE: Duplicate tickets found in ManageEngineAPI data")
        issues_found = True
    
    # Check if both services are fetching the same data
    if len(overlap) == len(service_id_set) == len(api_id_set):
        print("✅ GOOD: Both services are fetching identical ticket sets")
    elif len(overlap) > 0:
        print("⚠️  WARNING: Partial overlap - services fetching different ticket sets")
        issues_found = True
    else:
        print("❌ ISSUE: No overlap - services fetching completely different data")
        issues_found = True
    
    # Check for potential caching issues
    print(f"\n=== CACHING ANALYSIS ===")
    print("ManageEngineAPI uses caching with 5-minute timeout")
    print("ManageEngineService does not use caching")
    print("This could lead to inconsistent data if called at different times")
    
    if not issues_found:
        print(f"\n✅ SUMMARY: No duplicate issues found. All {len(set(service_ids + api_ids))} tickets are unique.")
    else:
        print(f"\n❌ SUMMARY: Issues detected. Please review the implementation.")
    
    return {
        'service_tickets': len(service_tickets),
        'api_tickets': len(api_tickets),
        'service_duplicates': len(service_duplicates),
        'api_duplicates': len(api_duplicates),
        'overlap': len(overlap),
        'issues_found': issues_found
    }

def analyze_dashboard_calls():
    """Analyze how dashboard data is being called"""
    print(f"\n=== DASHBOARD CALL ANALYSIS ===")
    
    # Check the dashboard view implementation
    print("Dashboard view calls:")
    print("1. me_service.get_historical_tickets(months=2)")
    print("   - This makes 3 API calls (batches of 100 each)")
    print("   - Total: 300 tickets maximum")
    print("   - No caching implemented")
    
    print("\nPotential issues:")
    print("- Multiple API calls without deduplication")
    print("- No caching in ManageEngineService")
    print("- Different services might fetch different data")
    print("- Dashboard refresh could show inconsistent data")

if __name__ == "__main__":
    try:
        results = check_ticket_duplicates()
        analyze_dashboard_calls()
        
        print(f"\n=== RECOMMENDATIONS ===")
        print("1. Implement deduplication logic in get_historical_tickets()")
        print("2. Add caching to ManageEngineService similar to ManageEngineAPI")
        print("3. Use a single service for all ticket fetching")
        print("4. Add unique constraint checks before processing tickets")
        print("5. Consider using ticket IDs as primary keys for deduplication")
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()
