#!/usr/bin/env python3
import os
import sys
import django
from datetime import datetime, timedelta
from django.db import connection

# Setup Django
sys.path.append('/home/devops-machine/Fluidtrust-project/customer_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from tickets.models import TicketCache

def check_dashboard_data():
    print("=== DASHBOARD DATA VERIFICATION ===")
    print(f"Checking data for last 30 days from {datetime.now().date()}")
    print("-" * 50)
    
    # Calculate 30 days ago
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    # Query tickets from last 30 days
    tickets_last_30_days = TicketCache.objects.filter(
        created_at__gte=thirty_days_ago
    )
    
    # Get status counts
    status_counts = {}
    for ticket in tickets_last_30_days:
        status = ticket.status.lower()
        # Normalize status names to match ManageEngine format
        if 'open' in status:
            status = 'Open'
        elif 'progress' in status or 'assigned' in status:
            status = 'In Progress'
        elif 'pending' in status or 'wait' in status:
            status = 'Pending'
        elif 'resolved' in status:
            status = 'Resolved'
        elif 'closed' in status or 'complete' in status:
            status = 'Closed'
        elif 'cancel' in status:
            status = 'Cancelled'
        elif 'hold' in status:
            status = 'On Hold'
        else:
            status = 'Other'
            
        status_counts[status] = status_counts.get(status, 0) + 1
    
    total_tickets = sum(status_counts.values())
    
    print("LOCAL DATABASE RESULTS:")
    print(f"Total: {total_tickets}")
    for status, count in sorted(status_counts.items()):
        print(f"{status}: {count}")
    
    print("\n" + "="*50)
    print("EXPECTED MANAGEENGINE DATA:")
    expected_data = {
        'Total': 147,
        'Open': 10,
        'In Progress': 0,
        'Pending': 0,
        'Resolved': 0,
        'Closed': 120,
        'Cancelled': 4,
        'On Hold': 13
    }
    
    for status, count in expected_data.items():
        print(f"{status}: {count}")
    
    print("\n" + "="*50)
    print("COMPARISON:")
    for status, expected_count in expected_data.items():
        if status == 'Total':
            actual_count = total_tickets
        else:
            actual_count = status_counts.get(status, 0)
        
        difference = actual_count - expected_count
        status_symbol = "✓" if difference == 0 else "✗"
        print(f"{status_symbol} {status}: Expected {expected_count}, Got {actual_count} (Diff: {difference:+d})")

def check_pulseway_data():
    print("\n" + "="*50)
    print("CHECKING PULSEWAY DATA CONNECTION")
    print("-" * 50)
    
    # Check if pulseway sync is working
    try:
        with connection.cursor() as cursor:
            # Check for pulseway-related tables or data
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%pulseway%'")
            pulseway_tables = cursor.fetchall()
            
            if pulseway_tables:
                print("Found Pulseway tables:")
                for table in pulseway_tables:
                    print(f"  - {table[0]}")
                    
                    # Get row count for each table
                    cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                    count = cursor.fetchone()[0]
                    print(f"    Records: {count}")
            else:
                print("No dedicated Pulseway tables found.")
                
            # Check if tickets have pulseway-related data
            cursor.execute("""
                SELECT COUNT(*) FROM ticket_cache 
                WHERE description LIKE '%pulseway%' 
                OR subject LIKE '%pulseway%'
                OR technician_name LIKE '%pulseway%'
            """)
            pulseway_tickets = cursor.fetchone()[0]
            print(f"Tickets with Pulseway references: {pulseway_tickets}")
            
    except Exception as e:
        print(f"Error checking Pulseway data: {e}")

def check_recent_sync():
    print("\n" + "="*50)
    print("CHECKING RECENT SYNC STATUS")
    print("-" * 50)
    
    try:
        from tickets.models import SyncStatus
        latest_sync = SyncStatus.objects.order_by('-last_sync_time').first()
        
        if latest_sync:
            print(f"Last sync: {latest_sync.last_sync_time}")
            print(f"Status: {latest_sync.sync_status}")
            print(f"Tickets synced: {latest_sync.total_tickets_synced}")
            if latest_sync.error_message:
                print(f"Error: {latest_sync.error_message}")
        else:
            print("No sync status records found")
            
    except Exception as e:
        print(f"Error checking sync status: {e}")

if __name__ == "__main__":
    check_dashboard_data()
    check_pulseway_data()
    check_recent_sync()
