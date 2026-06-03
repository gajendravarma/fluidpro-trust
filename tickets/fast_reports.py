from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from .models import TicketCache
from rbac.models import Company
from django.contrib.auth.models import User
import json
import logging

logger = logging.getLogger(__name__)


class FastReportService:
    """Fast report service using TicketCache (synced every 5 minutes)"""
    
    def get_available_companies(self):
        """Get list of companies from TicketCache"""
        return list(TicketCache.objects.values_list('company_name', flat=True).distinct().exclude(company_name='').order_by('company_name'))
    
    def get_available_technicians(self):
        """Get list of technicians from TicketCache"""
        return list(TicketCache.objects.values_list('technician_name', flat=True).distinct().exclude(technician_name='').order_by('technician_name'))
    
    @transaction.atomic
    def get_daily_report(self, date=None):
        # Get tickets for the specific date from TicketCache (synced every 5 minutes)
        from .models import TicketCache
        tickets = TicketCache.objects.filter(created_at__date=date)
        
        # Calculate statistics
        total_tickets = tickets.count()
        open_tickets = tickets.filter(status__iexact='Open').count()
        closed_tickets = tickets.filter(status__iexact='Closed').count()
        resolved_tickets = tickets.filter(status__iexact='Resolved').count()
        
        # Priority distribution
        high_priority = tickets.filter(Q(priority__iexact='High') | Q(priority__iexact='Urgent')).count()
        medium_priority = tickets.filter(Q(priority__iexact='Medium') | Q(priority__iexact='Normal')).count()
        low_priority = tickets.filter(Q(priority__iexact='Low')).count()
        none_priority = tickets.filter(Q(priority__iexact='None') | Q(priority__isnull=True) | Q(priority='')).count()
        
        # Company distribution
        company_stats = tickets.values('company_name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Status distribution
        status_breakdown = {}
        for status in ['Open', 'Closed', 'Resolved', 'Pending', 'Cancelled', 'Onhold']:
            count = tickets.filter(status__iexact=status).count()
            if count > 0:
                status_breakdown[status] = count
        
        # Priority breakdown
        priority_breakdown = {
            'High': high_priority,
            'Medium': medium_priority, 
            'Low': low_priority,
            'None': none_priority
        }
        
        return {
            'report_type': 'daily',
            'date': date,
            'generated_at': datetime.now(),
            'total_tickets': total_tickets,
            'open_tickets': open_tickets,
            'closed_tickets': closed_tickets,
            'resolved_tickets': resolved_tickets,
            'high_priority': high_priority,
            'medium_priority': medium_priority,
            'low_priority': low_priority,
            'none_priority': none_priority,
            'status_breakdown': status_breakdown,
            'priority_breakdown': priority_breakdown,
            'daily_breakdown': {str(date): total_tickets},
            'company_stats': list(company_stats),
            'tickets': list(tickets.values(
                'ticket_id', 'subject', 'status', 'priority', 
                'company_name', 'requester_name', 'technician_name', 'created_at'
            )[:100])
        }
    
    @transaction.atomic
    def get_weekly_report(self, date=None):
        """Get weekly report data"""
        if date is None:
            date = datetime.now().date()
        
        # Get start of week (Monday)
        start_date = date - timedelta(days=date.weekday())
        end_date = start_date + timedelta(days=6)
        
        tickets = TicketCache.objects.filter(created_at__date__range=[start_date, end_date])
        
        # Status distribution
        status_breakdown = {}
        for status in ['Open', 'Closed', 'Resolved', 'Pending', 'Onhold', 'Cancelled']:
            count = tickets.filter(status__iexact=status).count()
            if count > 0:
                status_breakdown[status] = count
        
        return {
            'report_type': 'weekly',
            'start_date': start_date,
            'end_date': end_date,
            'generated_at': datetime.now(),
            'total_tickets': tickets.count(),
            'status_breakdown': status_breakdown,
            'priority_breakdown': {},
            'daily_breakdown': {},
            'tickets': list(tickets.values(
                'ticket_id', 'subject', 'status', 'priority', 
                'company_name', 'technician_name', 'requester_name', 'created_at'
            )[:100])
        }
    
    @transaction.atomic
    def get_monthly_report(self, year=None, month=None):
        """Get monthly report data"""
        if year is None or month is None:
            now = datetime.now()
            year = now.year
            month = now.month
        
        tickets = TicketCache.objects.filter(created_at__year=year, created_at__month=month)
        
        # Status distribution
        status_breakdown = {}
        for status in ['Open', 'Closed', 'Resolved', 'Pending', 'Onhold', 'Cancelled']:
            count = tickets.filter(status__iexact=status).count()
            if count > 0:
                status_breakdown[status] = count
        
        return {
            'report_type': 'monthly',
            'year': year,
            'month': month,
            'generated_at': datetime.now(),
            'total_tickets': tickets.count(),
            'status_breakdown': status_breakdown,
            'priority_breakdown': {},
            'daily_breakdown': {},
            'tickets': list(tickets.values(
                'ticket_id', 'subject', 'status', 'priority', 
                'company_name', 'technician_name', 'requester_name', 'created_at'
            )[:100])
        }
    
    @transaction.atomic
    def get_company_report(self, company=None, start_date=None, end_date=None):
        """Get company-specific report"""
        tickets = TicketCache.objects.all()
        
        if company:
            tickets = tickets.filter(company_name__icontains=company)
        if start_date:
            tickets = tickets.filter(created_at__date__gte=start_date)
        if end_date:
            tickets = tickets.filter(created_at__date__lte=end_date)
        
        # Status distribution
        status_breakdown = {}
        for status in ['Open', 'Closed', 'Resolved', 'Pending', 'Onhold', 'Cancelled']:
            count = tickets.filter(status__iexact=status).count()
            if count > 0:
                status_breakdown[status] = count
        
        return {
            'report_type': 'company',
            'company': company,
            'generated_at': datetime.now(),
            'total_tickets': tickets.count(),
            'status_breakdown': status_breakdown,
            'priority_breakdown': {},
            'daily_breakdown': {},
            'tickets': list(tickets.values(
                'ticket_id', 'subject', 'status', 'priority', 
                'company_name', 'technician_name', 'requester_name', 'created_at'
            )[:100])
        }
    
    @transaction.atomic
    def get_technician_report(self, technician=None, start_date=None, end_date=None):
        """Get technician-specific report"""
        tickets = TicketCache.objects.all()
        
        if technician:
            tickets = tickets.filter(technician_name__iexact=technician)
        if start_date:
            tickets = tickets.filter(created_at__date__gte=start_date)
        if end_date:
            tickets = tickets.filter(created_at__date__lte=end_date)
        
        # Status distribution
        status_breakdown = {}
        for status in ['Open', 'Closed', 'Resolved', 'Pending', 'Onhold', 'Cancelled']:
            count = tickets.filter(status__iexact=status).count()
            if count > 0:
                status_breakdown[status] = count
        
        return {
            'report_type': 'technician',
            'technician': technician,
            'generated_at': datetime.now(),
            'total_tickets': tickets.count(),
            'status_breakdown': status_breakdown,
            'priority_breakdown': {},
            'daily_breakdown': {},
            'tickets': list(tickets.values(
                'ticket_id', 'subject', 'status', 'priority', 
                'company_name', 'technician_name', 'requester_name', 'created_at'
            )[:100])
        }


@login_required
def fast_reports_dashboard(request):
    """Super fast reports using local database"""
    local_service = LocalTicketService()
    
    # Get filter parameters
    company = request.GET.get('company', '')
    technician = request.GET.get('technician', '')
    status = request.GET.get('status', '')
    priority = request.GET.get('priority', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Build filters
    filters = {}
    if company:
        filters['company'] = company
    if technician:
        filters['technician'] = technician
    if status:
        filters['status'] = status
    if priority:
        filters['priority'] = priority
    if date_from:
        try:
            filters['date_from'] = datetime.strptime(date_from, '%Y-%m-%d').date()
        except:
            pass
    if date_to:
        try:
            filters['date_to'] = datetime.strptime(date_to, '%Y-%m-%d').date()
        except:
            pass
    
    # Get filtered tickets from local database
    tickets = local_service.get_tickets_for_reports(filters)
    
    # Get statistics
    company_stats = local_service.get_company_stats()
    technician_stats = local_service.get_technician_stats()
    priority_stats = local_service.get_priority_distribution()
    status_stats = local_service.get_status_distribution()
    
    # Get unique values for dropdowns
    companies = TicketCache.objects.values_list('company_name', flat=True).distinct().exclude(company_name='')
    technicians = TicketCache.objects.values_list('technician_name', flat=True).distinct().exclude(technician_name='')
    statuses = TicketCache.objects.values_list('status', flat=True).distinct()
    priorities = TicketCache.objects.values_list('priority', flat=True).distinct()
    
    context = {
        'tickets': tickets[:100],  # Limit display to 100 for performance
        'total_tickets': tickets.count(),
        'company_stats': company_stats,
        'technician_stats': technician_stats,
        'priority_stats': priority_stats,
        'status_stats': status_stats,
        'companies': sorted(companies),
        'technicians': sorted(technicians),
        'statuses': sorted(statuses),
        'priorities': sorted(priorities),
        'filters': {
            'company': company,
            'technician': technician,
            'status': status,
            'priority': priority,
            'date_from': date_from,
            'date_to': date_to,
        },
        'sync_info': local_service.get_last_sync_info(),
    }
    
    return render(request, 'tickets/fast_reports.html', context)

@login_required
def export_tickets_csv(request):
    """Export filtered tickets to CSV"""
    import csv
    from django.http import HttpResponse
    
    local_service = LocalTicketService()
    
    # Get same filters as reports
    filters = {}
    company = request.GET.get('company', '')
    technician = request.GET.get('technician', '')
    status = request.GET.get('status', '')
    priority = request.GET.get('priority', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if company:
        filters['company'] = company
    if technician:
        filters['technician'] = technician
    if status:
        filters['status'] = status
    if priority:
        filters['priority'] = priority
    if date_from:
        try:
            filters['date_from'] = datetime.strptime(date_from, '%Y-%m-%d').date()
        except:
            pass
    if date_to:
        try:
            filters['date_to'] = datetime.strptime(date_to, '%Y-%m-%d').date()
        except:
            pass
    
    # Get tickets from local database
    tickets = local_service.get_tickets_for_reports(filters)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="tickets_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Ticket ID', 'Subject', 'Status', 'Priority', 'Category',
        'Requester Name', 'Requester Email', 'Technician', 'Company',
        'Created Date', 'Updated Date', 'Resolved Date'
    ])
    
    for ticket in tickets:
        writer.writerow([
            ticket.ticket_id,
            ticket.subject,
            ticket.status,
            ticket.priority,
            ticket.category,
            ticket.requester_name,
            ticket.requester_email,
            ticket.technician_name,
            ticket.company_name,
            ticket.created_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.created_at else '',
            ticket.updated_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.updated_at else '',
            ticket.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.resolved_at else '',
        ])
    
    return response

@login_required
def search_tickets_api(request):
    """API endpoint for searching tickets"""
    search_term = request.GET.get('q', '')
    
    if not search_term:
        return JsonResponse({'tickets': []})
    
    local_service = LocalTicketService()
    tickets = local_service.search_tickets(search_term)[:20]  # Limit to 20 results
    
    tickets_data = []
    for ticket in tickets:
        tickets_data.append({
            'id': ticket.ticket_id,
            'subject': ticket.subject,
            'status': ticket.status,
            'priority': ticket.priority,
            'company': ticket.company_name,
            'technician': ticket.technician_name,
            'created_at': ticket.created_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.created_at else '',
        })
    
    return JsonResponse({'tickets': tickets_data})

@login_required
def ticket_stats_api(request):
    """API endpoint for getting ticket statistics"""
    local_service = LocalTicketService()
    
    stats = {
        'total_tickets': TicketCache.objects.count(),
        'company_stats': list(local_service.get_company_stats()[:10]),
        'technician_stats': list(local_service.get_technician_stats()[:10]),
        'priority_distribution': list(local_service.get_priority_distribution()),
        'status_distribution': list(local_service.get_status_distribution()),
        'sync_info': local_service.get_last_sync_info(),
    }
    
    return JsonResponse(stats)
