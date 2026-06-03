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
from django.db.models import Count

def analyze_data():
    print("=== COMPREHENSIVE TICKET ANALYSIS ===")
    
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    # Get all tickets from last 30 days
    tickets = TicketCache.objects.filter(created_at__gte=thirty_days_ago)
    
    print(f"Total tickets in last 30 days: {tickets.count()}")
    
    # Analyze by company
    print("\nTop companies by ticket count:")
    companies = tickets.values('company_name').annotate(count=Count('id')).order_by('-count')[:10]
    for company in companies:
        name = company['company_name'] or 'Unknown'
        print(f"  {name}: {company['count']}")
    
    # Analyze exact status values
    print("\nExact status distribution:")
    statuses = tickets.values('status').annotate(count=Count('id')).order_by('-count')
    for status in statuses:
        print(f"  '{status['status']}': {status['count']}")
    
    # Try to find a subset that matches 147 tickets
    print("\n" + "="*50)
    print("LOOKING FOR SUBSET MATCHING 147 TICKETS")
    print("="*50)
    
    # Try Market Xcel only (largest company)
    market_xcel = tickets.filter(company_name='Market Xcel').count()
    print(f"Market Xcel only: {market_xcel}")
    
    # Try C G Logistics only
    cg_logistics = tickets.filter(company_name='C G Logistics').count()
    print(f"C G Logistics only: {cg_logistics}")
    
    # Try combining smaller companies
    small_companies = tickets.exclude(company_name__in=['Market Xcel', 'C G Logistics']).count()
    print(f"All except Market Xcel and C G Logistics: {small_companies}")
    
    # Try specific status combinations
    closed_cancelled = tickets.filter(status__in=['Closed', 'Cancelled']).count()
    print(f"Closed + Cancelled only: {closed_cancelled}")
    
    # Try recent tickets (last 15 days)
    fifteen_days_ago = datetime.now() - timedelta(days=15)
    recent_tickets = tickets.filter(created_at__gte=fifteen_days_ago).count()
    print(f"Last 15 days only: {recent_tickets}")
    
    # Try specific date range that might match ManageEngine
    print("\nTrying different date ranges:")
    for days in [7, 14, 21, 28]:
        date_cutoff = datetime.now() - timedelta(days=days)
        count = tickets.filter(created_at__gte=date_cutoff).count()
        print(f"Last {days} days: {count}")
        if abs(count - 147) < 20:
            print(f"  *** CLOSE MATCH! Difference: {count - 147}")

def check_pulseway_integration():
    print("\n" + "="*50)
    print("PULSEWAY INTEGRATION STATUS")
    print("="*50)
    
    # Check pulseway sync log
    try:
        with open('/home/devops-machine/Fluidtrust-project/customer_portal/pulseway_sync.log', 'r') as f:
            lines = f.readlines()
            print(f"Pulseway sync log has {len(lines)} lines")
            print("Last 5 log entries:")
            for line in lines[-5:]:
                print(f"  {line.strip()}")
    except FileNotFoundError:
        print("Pulseway sync log not found")
    
    # Check for pulseway-related tickets
    thirty_days_ago = datetime.now() - timedelta(days=30)
    pulseway_tickets = TicketCache.objects.filter(
        created_at__gte=thirty_days_ago
    ).filter(
        models.Q(subject__icontains='pulseway') |
        models.Q(description__icontains='pulseway') |
        models.Q(technician_name__icontains='pulseway')
    ).count()
    
    print(f"Tickets mentioning Pulseway: {pulseway_tickets}")

def create_summary_report():
    print("\n" + "="*60)
    print("SUMMARY REPORT")
    print("="*60)
    
    thirty_days_ago = datetime.now() - timedelta(days=30)
    tickets = TicketCache.objects.filter(created_at__gte=thirty_days_ago)
    
    # Create status mapping similar to ManageEngine
    status_mapping = {
        'Open': ['Open'],
        'In Progress': ['In Progress', 'Assigned'],
        'Pending': ['Pending'],
        'Resolved': ['Resolved'],
        'Closed': ['Closed'],
        'Cancelled': ['Cancelled'],
        'On Hold': ['Onhold', 'On Hold', 'Under Observation', 'On Hold – User Dependency', 'On Hold - For Spare']
    }
    
    print("LOCAL DATABASE (mapped to ManageEngine categories):")
    total = 0
    for me_status, local_statuses in status_mapping.items():
        count = tickets.filter(status__in=local_statuses).count()
        total += count
        print(f"{me_status}: {count}")
    
    print(f"Total: {total}")
    
    print("\nMANAGEENGINE EXPECTED:")
    expected = {
        'Total': 147,
        'Open': 10,
        'In Progress': 0,
        'Pending': 0,
        'Resolved': 0,
        'Closed': 120,
        'Cancelled': 4,
        'On Hold': 13
    }
    
    for status, count in expected.items():
        print(f"{status}: {count}")
    
    print(f"\nDISCREPANCY ANALYSIS:")
    print(f"Our total ({total}) vs Expected (147) = {total - 147} difference")
    print(f"This suggests we may be pulling from a different data source")
    print(f"or time range than ManageEngine dashboard.")

if __name__ == "__main__":
    from django.db import models
    analyze_data()
    check_pulseway_integration()
    create_summary_report()
