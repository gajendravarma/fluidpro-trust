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

def test_historical_data():
    print("🔧 Testing ManageEngine Historical Data API...")
    
    try:
        service = ManageEngineService()
        print("✅ ManageEngine service initialized successfully")
        
        print("\n📊 Fetching last 2 months ticket data...")
        data = service.get_historical_tickets(months=2)
        
        if data:
            print("✅ Historical data retrieved successfully!")
            print(f"\n📈 Statistics Summary:")
            print(f"   Total Tickets: {data['total_tickets']}")
            print(f"   Pending Tickets: {data['pending_tickets']}")
            print(f"   Cancelled Tickets: {data['cancelled_tickets']}")
            print(f"   Closed Tickets: {data['closed_tickets']}")
            print(f"   In Progress Tickets: {data['in_progress_tickets']}")
            
            print(f"\n🎯 Priority Breakdown:")
            for priority, count in data['tickets_by_priority'].items():
                print(f"   {priority}: {count}")
            
            print(f"\n📅 Monthly Breakdown:")
            for month, count in data['tickets_by_month'].items():
                print(f"   {month}: {count}")
            
            print(f"\n🎫 Recent Tickets: {len(data['recent_tickets'])} tickets")
            for i, ticket in enumerate(data['recent_tickets'][:3], 1):
                subject = ticket.get('subject', 'No Subject')[:50]
                status = ticket.get('status', {})
                status_name = status.get('name', 'Unknown') if isinstance(status, dict) else str(status)
                print(f"   {i}. {subject}... (Status: {status_name})")
            
            print("\n🌐 Access the dashboard at: http://localhost:8000/")
            print("📊 Historical data will be displayed in the ManageEngine section")
            
        else:
            print("⚠️  No historical data retrieved - this might be due to:")
            print("   - API authentication issues")
            print("   - No tickets in the last 2 months")
            print("   - ManageEngine API connectivity issues")
        
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        print("\n🔧 Troubleshooting:")
        print("   - Check ManageEngine API credentials in settings")
        print("   - Verify ManageEngine server connectivity")
        print("   - Check if the API endpoint supports date filtering")

if __name__ == "__main__":
    test_historical_data()
