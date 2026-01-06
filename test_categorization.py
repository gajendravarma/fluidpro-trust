#!/usr/bin/env python3

import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/root/customer_portal')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from tickets.services import ManageEngineService

def test_new_categorization():
    print("🔧 Testing New Status Categorization Logic...")
    
    # Test the actual method
    service = ManageEngineService()
    data = service.get_historical_tickets(months=2)
    
    if data:
        total = data['total_tickets']
        pending = data['pending_tickets']
        resolved = data['resolved_tickets']
        closed = data['closed_tickets']
        in_progress = data['in_progress_tickets']
        
        calculated_total = pending + resolved + closed + in_progress
        
        print(f"📊 Status Breakdown:")
        print(f"   Total Tickets: {total}")
        print(f"   Pending (Open + Onhold): {pending}")
        print(f"   Resolved: {resolved}")
        print(f"   Closed (Closed + Cancelled): {closed}")
        print(f"   In Progress: {in_progress}")
        print(f"   Calculated Sum: {calculated_total}")
        
        if total == calculated_total:
            print("✅ Numbers match perfectly!")
        else:
            print(f"❌ Mismatch: Total={total}, Sum={calculated_total}")
            
        print(f"\n📝 Explanation:")
        print(f"   - 'Open' and 'Onhold' tickets → Pending")
        print(f"   - 'Closed' and 'Cancelled' tickets → Closed")
        print(f"   - No 'Resolved' status in this ManageEngine instance")
        print(f"   - This is why Resolved = 0 (normal for this setup)")
        
    else:
        print("❌ Failed to get data")

if __name__ == "__main__":
    test_new_categorization()
