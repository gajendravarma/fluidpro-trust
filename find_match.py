#!/usr/bin/env python3
import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
sys.path.append('/home/devops-machine/Fluidtrust-project/customer_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from tickets.models import TicketCache
from django.db.models import Count, Q

def find_147_match():
    print("=== FINDING EXACT MATCH FOR 147 TICKETS ===")
    
    thirty_days_ago = datetime.now() - timedelta(days=30)
    all_tickets = TicketCache.objects.filter(created_at__gte=thirty_days_ago)
    
    print(f"Total tickets in last 30 days: {all_tickets.count()}")
    
    # The closest match we found was "All except Market Xcel and C G Logistics: 140"
    # Let's explore this further
    
    excluded_companies = ['Market Xcel', 'C G Logistics']
    filtered_tickets = all_tickets.exclude(company_name__in=excluded_companies)
    
    print(f"\nTickets excluding Market Xcel and C G Logistics: {filtered_tickets.count()}")
    
    # Let's see what companies are in this subset
    print("\nCompanies in the 140-ticket subset:")
    companies = filtered_tickets.values('company_name').annotate(count=Count('id')).order_by('-count')
    for company in companies:
        name = company['company_name'] or 'Unknown'
        print(f"  {name}: {company['count']}")
    
    # Let's try adding back some tickets to get to 147
    print(f"\nNeed {147 - filtered_tickets.count()} more tickets to reach 147")
    
    # Check if adding specific status types gets us closer
    print("\nStatus distribution in the 140-ticket subset:")
    statuses = filtered_tickets.values('status').annotate(count=Count('id')).order_by('-count')
    for status in statuses:
        print(f"  '{status['status']}': {status['count']}")
    
    # Try different combinations to get exactly 147
    print("\n" + "="*50)
    print("TRYING TO GET EXACTLY 147 TICKETS")
    print("="*50)
    
    # Maybe it's a specific company combination
    test_combinations = [
        # Try including some Market Xcel tickets
        (['Market Xcel'], 'first 7 Market Xcel tickets', 7),
        (['C G Logistics'], 'first 7 C G Logistics tickets', 7),
        # Try specific status from excluded companies
        (['Market Xcel'], 'Market Xcel Open tickets only', None),
        (['C G Logistics'], 'C G Logistics Open tickets only', None),
    ]
    
    base_count = filtered_tickets.count()  # 140
    
    for companies, description, limit in test_combinations:
        if limit:
            additional = all_tickets.filter(company_name__in=companies)[:limit].count()
            total = base_count + additional
            print(f"Base 140 + {description}: {total}")
        else:
            additional = all_tickets.filter(company_name__in=companies, status='Open').count()
            total = base_count + additional
            print(f"Base 140 + {description}: {total}")
        
        if total == 147:
            print(f"  *** EXACT MATCH FOUND! ***")

def check_manageengine_source():
    print("\n" + "="*60)
    print("CHECKING POSSIBLE MANAGEENGINE DATA SOURCE")
    print("="*60)
    
    # Check if there are any tickets with ManageEngine-specific fields
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    # Look for patterns that might indicate ManageEngine source
    me_patterns = [
        'servicedesk',
        'manage',
        'engine',
        'sdp',
        'helpdesk'
    ]
    
    for pattern in me_patterns:
        count = TicketCache.objects.filter(
            created_at__gte=thirty_days_ago
        ).filter(
            Q(subject__icontains=pattern) |
            Q(description__icontains=pattern) |
            Q(technician_name__icontains=pattern) |
            Q(company_name__icontains=pattern)
        ).count()
        
        print(f"Tickets containing '{pattern}': {count}")
    
    # Check for specific technician patterns
    print("\nTechnician analysis:")
    technicians = TicketCache.objects.filter(
        created_at__gte=thirty_days_ago
    ).values('technician_name').annotate(count=Count('id')).order_by('-count')[:10]
    
    for tech in technicians:
        name = tech['technician_name'] or 'Unknown'
        print(f"  {name}: {tech['count']}")

def final_recommendation():
    print("\n" + "="*60)
    print("FINAL ANALYSIS & RECOMMENDATIONS")
    print("="*60)
    
    print("FINDINGS:")
    print("1. Local database has 586 tickets in last 30 days")
    print("2. ManageEngine dashboard shows 147 tickets")
    print("3. Closest match: 140 tickets (excluding Market Xcel & C G Logistics)")
    print("4. Pulseway integration is active but has some sync errors")
    
    print("\nPOSSIBLE EXPLANATIONS:")
    print("1. ManageEngine dashboard may have different date range")
    print("2. ManageEngine may filter by specific companies/technicians")
    print("3. ManageEngine may exclude certain ticket types")
    print("4. Data sync timing differences")
    
    print("\nRECOMMENDATIONS:")
    print("1. Check ManageEngine dashboard filters and date range")
    print("2. Verify which companies/technicians are included in ME dashboard")
    print("3. Check if ME dashboard excludes certain statuses")
    print("4. Sync timing - ensure both systems use same time zone")
    print("5. Consider creating a filtered view that matches ME criteria")

if __name__ == "__main__":
    find_147_match()
    check_manageengine_source()
    final_recommendation()
