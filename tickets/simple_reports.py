from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Count, Q
from datetime import datetime, timedelta, date as date_type
from .models import TicketCache

def _customer_company_filter(request):
    """Return a company_name filter kwarg if the logged-in user is a customer, else None."""
    try:
        profile = request.user.userprofile
        if profile.get_role() == 'customer' and profile.company:
            from .local_service import LocalTicketService
            svc = LocalTicketService()
            matched = svc.find_company_in_cache(profile.company.name)
            return matched  # may be None if no match
    except Exception:
        pass
    return None


@login_required
def simple_reports(request):
    """Simple reports directly from database"""

    report_type = request.GET.get('type', 'daily')

    # For customer role: restrict all queries to their company only
    customer_company = _customer_company_filter(request)

    def base_qs():
        qs = TicketCache.objects.all()
        if customer_company:
            qs = qs.filter(company_name__iexact=customer_company)
        return qs

    if report_type == 'daily':
        date = request.GET.get('date', datetime.now().date())
        tickets = base_qs().filter(created_at__date=date)

    elif report_type == 'weekly':
        start_date = request.GET.get('start_date')
        if start_date:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = start + timedelta(days=6)
            tickets = base_qs().filter(created_at__date__range=[start, end])
        else:
            tickets = TicketCache.objects.none()

    elif report_type == 'monthly':
        year = int(request.GET.get('year', datetime.now().year))
        month = int(request.GET.get('month', datetime.now().month))
        tickets = base_qs().filter(created_at__year=year, created_at__month=month)

    elif report_type == 'company':
        company = request.GET.get('company')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        tickets = base_qs()
        if company and not customer_company:
            # Only allow company switching for non-customer roles
            tickets = tickets.filter(company_name__icontains=company)
        if start_date:
            tickets = tickets.filter(created_at__date__gte=start_date)
        if end_date:
            tickets = tickets.filter(created_at__date__lte=end_date)

    elif report_type == 'technician':
        technician = request.GET.get('technician')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        tickets = base_qs()
        if technician:
            tickets = tickets.filter(technician_name__icontains=technician)
        if start_date:
            tickets = tickets.filter(created_at__date__gte=start_date)
        if end_date:
            tickets = tickets.filter(created_at__date__lte=end_date)
    else:
        tickets = TicketCache.objects.none()
    
    # Get status breakdown from actual data — don't hardcode names so every
    # status that exists in the result set is counted and the pie chart total
    # always matches the summary card total.
    status_breakdown = {}
    for row in tickets.values('status').annotate(count=Count('id')).order_by('-count'):
        s = (row['status'] or '').strip()
        if s and row['count'] > 0:
            status_breakdown[s] = status_breakdown.get(s, 0) + row['count']

    # Get priority breakdown the same way
    priority_breakdown = {}
    for row in tickets.values('priority').annotate(count=Count('id')).order_by('-count'):
        p = (row['priority'] or '').strip()
        if p and row['count'] > 0:
            priority_breakdown[p] = priority_breakdown.get(p, 0) + row['count']

    total_tickets = tickets.count()

    # Build daily_breakdown: date string → count, sorted chronologically.
    # For daily reports fill every day in the range so the line chart has no gaps.
    daily_breakdown = {}
    for row in (tickets
                .extra(select={'day': "date(created_at)"})
                .values('day')
                .annotate(count=Count('id'))
                .order_by('day')):
        day_key = str(row['day'])
        if day_key:
            daily_breakdown[day_key] = row['count']

    # For daily report type: ensure the selected date always appears (even if 0)
    if report_type == 'daily':
        raw_date = request.GET.get('date')
        if raw_date and raw_date not in daily_breakdown:
            daily_breakdown[raw_date] = 0

    # For weekly: fill all 7 days so gaps show as 0
    if report_type == 'weekly' and daily_breakdown:
        raw_start = request.GET.get('start_date')
        if raw_start:
            start_d = datetime.strptime(raw_start, '%Y-%m-%d').date()
            for i in range(7):
                k = str(start_d + timedelta(days=i))
                daily_breakdown.setdefault(k, 0)
            daily_breakdown = dict(sorted(daily_breakdown.items()))

    # For monthly: fill every day in the month
    if report_type == 'monthly' and total_tickets > 0:
        import calendar
        yr = int(request.GET.get('year', datetime.now().year))
        mo = int(request.GET.get('month', datetime.now().month))
        days_in_month = calendar.monthrange(yr, mo)[1]
        for d in range(1, days_in_month + 1):
            k = f'{yr}-{mo:02d}-{d:02d}'
            daily_breakdown.setdefault(k, 0)
        daily_breakdown = dict(sorted(daily_breakdown.items()))

    data = {
        'report_type': report_type,
        'total_tickets': total_tickets,
        'status_breakdown': status_breakdown,
        'priority_breakdown': priority_breakdown,
        'daily_breakdown': daily_breakdown,
        'tickets': list(tickets.values(
            'ticket_id', 'subject', 'status', 'priority',
            'company_name', 'technician_name', 'requester_name', 'created_at'
        ))
    }
    
    return JsonResponse(data)
