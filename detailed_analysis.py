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

def detailed_analysis():
    print("=== DETAILED TICKET ANALYSIS ===")
    
    # Calculate different time ranges
    now = datetime.now()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)
    
    print(f"Current time: {now}")
    print(f"30 days ago: {thirty_days_ago}")
    print(f"7 days ago: {seven_days_ago}")
    
    # Check total tickets in database
    total_tickets = TicketCache.objects.count()
    print(f"\nTotal tickets in database: {total_tickets}")
    
    # Check tickets by different time ranges
    tickets_30_days = TicketCache.objects.filter(created_at__gte=thirty_days_ago).count()
    tickets_7_days = TicketCache.objects.filter(created_at__gte=seven_days_ago).count()
    tickets_today = TicketCache.objects.filter(created_at__date=now.date()).count()
    
    print(f"Tickets created in last 30 days: {tickets_30_days}")
    print(f"Tickets created in last 7 days: {tickets_7_days}")
    print(f"Tickets created today: {tickets_today}")
    
    # Check date range of tickets
    with connection.cursor() as cursor:
        cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM ticket_cache")
        min_date, max_date = cursor.fetchone()
        print(f"\nTicket date range: {min_date} to {max_date}")
        
        # Check tickets by company
        cursor.execute("""
            SELECT company_name, COUNT(*) as count 
            FROM ticket_cache 
            WHERE created_at >= %s 
            GROUP BY company_name 
            ORDER BY count DESC 
            LIMIT 10
        """, [thirty_days_ago])
        
        print("\nTop 10 companies by ticket count (last 30 days):")
        for company, count in cursor.fetchall():
            print(f"  {company or 'Unknown'}: {count}")
        
        # Check status distribution with exact values
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM ticket_cache 
            WHERE created_at >= %s 
            GROUP BY status 
            ORDER BY count DESC
        """, [thirty_days_ago])
        
        print("\nExact status values (last 30 days):")
        for status, count in cursor.fetchall():
            print(f"  '{status}': {count}")

def check_manageengine_filter():
    print("\n" + "="*60)
    print("CHECKING FOR MANAGEENGINE-SPECIFIC FILTERS")
    print("="*60)
    
    # The discrepancy suggests we might need to filter by specific criteria
    # Let's check if there's a specific company or source filter needed
    
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    with connection.cursor() as cursor:
        # Check if there are tickets from specific sources
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN company_name LIKE '%manage%' THEN 'ManageEngine Related'
                    WHEN company_name LIKE '%fluid%' THEN 'FluidTrust Related'
                    WHEN company_name = '' OR company_name IS NULL THEN 'No Company'
                    ELSE 'Other Companies'
                END as category,
                COUNT(*) as count
            FROM ticket_cache 
            WHERE created_at >= %s
            GROUP BY category
            ORDER BY count DESC
        """, [thirty_days_ago])
        
        print("Tickets by category (last 30 days):")
        for category, count in cursor.fetchall():
            print(f"  {category}: {count}")
        
        # Check for specific date patterns that might match ManageEngine data
        cursor.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM ticket_cache 
            WHERE created_at >= %s
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            LIMIT 10
        """, [thirty_days_ago])
        
        print("\nDaily ticket creation (last 10 days):")
        for date, count in cursor.fetchall():
            print(f"  {date}: {count}")

def suggest_filter_for_147_tickets():
    print("\n" + "="*60)
    print("FINDING FILTER TO MATCH 147 TICKETS")
    print("="*60)
    
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    # Try different filters to see if we can get close to 147
    filters_to_try = [
        ("Specific company filter", "company_name = 'FluidTrust'"),
        ("Non-empty company", "company_name != '' AND company_name IS NOT NULL"),
        ("Specific technician", "technician_name LIKE '%admin%' OR technician_name LIKE '%support%'"),
        ("High priority only", "priority IN ('High', 'Critical', 'high', 'critical')"),
        ("Recent updates", "updated_at >= ?"),
    ]
    
    with connection.cursor() as cursor:
        for filter_name, filter_condition in filters_to_try:
            if "updated_at" in filter_condition:
                cursor.execute(f"""
                    SELECT COUNT(*) FROM ticket_cache 
                    WHERE created_at >= %s AND {filter_condition}
                """, [thirty_days_ago, thirty_days_ago])
            else:
                cursor.execute(f"""
                    SELECT COUNT(*) FROM ticket_cache 
                    WHERE created_at >= %s AND {filter_condition}
                """, [thirty_days_ago])
            
            count = cursor.fetchone()[0]
            print(f"{filter_name}: {count} tickets")
            
            if abs(count - 147) < 50:  # If close to 147
                print(f"  *** CLOSE MATCH! Difference: {count - 147}")

if __name__ == "__main__":
    detailed_analysis()
    check_manageengine_filter()
    suggest_filter_for_147_tickets()
