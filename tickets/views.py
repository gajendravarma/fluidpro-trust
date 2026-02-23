from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Ticket
from .services import ManageEngineService
from .forms import TicketForm
import json
from datetime import datetime

@login_required
def dashboard(request):
    from .services import ManageEngineService
    
    # Get historical data from ManageEngine (includes recent tickets)
    me_service = ManageEngineService()
    historical_data = me_service.get_historical_tickets(months=2)
    
    # Extract recent tickets from historical data
    recent_tickets = []
    if historical_data and 'recent_tickets' in historical_data:
        raw_tickets = historical_data['recent_tickets'][:10]  # Get first 10
        
        # Format tickets for template display
        for ticket in raw_tickets:
            status = ticket.get('status', {})
            priority = ticket.get('priority', {})
            requester = ticket.get('requester', {})
            created_time = ticket.get('created_time', {})
            
            formatted_ticket = {
                'id': ticket.get('id'),
                'manage_engine_id': ticket.get('id'),
                'title': ticket.get('subject', 'No Subject'),
                'status': status.get('name', 'Unknown') if isinstance(status, dict) else str(status),
                'priority': priority.get('name', 'Medium') if isinstance(priority, dict) else str(priority),
                'created_by': requester.get('name', 'Unknown') if isinstance(requester, dict) else 'Unknown',
                'created_at': created_time.get('display_value', '') if isinstance(created_time, dict) else ''
            }
            recent_tickets.append(formatted_ticket)
    
    # Calculate stats from historical data
    total_tickets = historical_data.get('total_tickets', 0) if historical_data else 0
    open_tickets = historical_data.get('pending_tickets', 0) if historical_data else 0
    in_progress_tickets = historical_data.get('in_progress_tickets', 0) if historical_data else 0
    resolved_tickets = historical_data.get('closed_tickets', 0) if historical_data else 0
    
    # Calculate percentages
    open_percentage = (open_tickets * 100 / total_tickets) if total_tickets > 0 else 0
    progress_percentage = (in_progress_tickets * 100 / total_tickets) if total_tickets > 0 else 0
    resolved_percentage = (resolved_tickets * 100 / total_tickets) if total_tickets > 0 else 0
    
    context = {
        'tickets': recent_tickets,
        'total_tickets': total_tickets,
        'open_tickets': open_tickets,
        'in_progress_tickets': in_progress_tickets,
        'resolved_tickets': resolved_tickets,
        'open_percentage': open_percentage,
        'progress_percentage': progress_percentage,
        'resolved_percentage': resolved_percentage,
    }
    return render(request, 'tickets/dashboard.html', context)

@login_required
def create_ticket(request):
    if request.method == 'POST':
        form = TicketForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.created_by = request.user
            
            # Get attachment file if provided
            attachment_file = form.cleaned_data.get('attachment')
            
            # Validate file size (10MB limit)
            if attachment_file and attachment_file.size > 10 * 1024 * 1024:
                messages.error(request, 'File size must be less than 10MB.')
                return render(request, 'tickets/create_ticket.html', {'form': form})
            
            # Create ticket in ManageEngine
            me_service = ManageEngineService()
            me_response = me_service.create_ticket(
                title=ticket.title,
                description=ticket.description,
                priority=ticket.priority,
                requester_email=request.user.email,
                attachment_file=attachment_file
            )
            
            if me_response and 'request' in me_response:
                ticket.manage_engine_id = me_response['request']['id']
                requester_email = me_response['request']['requester']['email_id']
                
                success_msg = f'Ticket created successfully! ManageEngine ID: {ticket.manage_engine_id}'
                if attachment_file:
                    success_msg += f' (with attachment: {attachment_file.name})'
                
                if requester_email != request.user.email:
                    success_msg += f'. Note: Used {requester_email} as requester since your email is not in ManageEngine.'
                
                messages.success(request, success_msg)
            else:
                messages.error(request, 'Failed to create ticket in ManageEngine. Please contact administrator.')
                return render(request, 'tickets/create_ticket.html', {'form': form})
            
            ticket.save()
            return redirect('dashboard')
    else:
        form = TicketForm()
    
    return render(request, 'tickets/create_ticket.html', {'form': form})

@login_required
def view_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id, created_by=request.user)
    
    # Sync with ManageEngine if we have the ID
    if ticket.manage_engine_id:
        me_service = ManageEngineService()
        me_ticket = me_service.get_ticket(ticket.manage_engine_id)
        if me_ticket and 'request' in me_ticket:
            # Update local ticket with ManageEngine data
            me_data = me_ticket['request']
            if 'status' in me_data and 'name' in me_data['status']:
                ticket.status = me_data['status']['name']
                ticket.save()
    
    return render(request, 'tickets/view_ticket.html', {'ticket': ticket})

@login_required
def technicians(request):
    me_service = ManageEngineService()
    tech_data = me_service.get_technicians()
    companies = me_service.get_companies()
    technicians_list = []
    
    if tech_data and 'users' in tech_data:
        technicians_list = tech_data['users']
        
        # Try to get company info for each user
        for user in technicians_list:
            user_id = user.get('id')
            if user_id:
                try:
                    user_details = me_service.get_user_details(user_id)
                    if user_details and 'user' in user_details:
                        account = user_details['user'].get('account', {})
                        if isinstance(account, dict):
                            user['company'] = account.get('name', '')
                        else:
                            user['company'] = ''
                    else:
                        user['company'] = ''
                except:
                    user['company'] = ''
            else:
                user['company'] = ''
    
    return render(request, 'tickets/technicians.html', {
        'technicians': technicians_list,
        'companies': companies
    })

@login_required
def all_users(request):
    page = int(request.GET.get('page', 1))
    search = request.GET.get('search', '').strip()
    per_page = 20
    
    me_service = ManageEngineService()
    users_data = me_service.get_all_users(page=page, per_page=per_page, search=search)
    companies = me_service.get_companies()
    total_users = me_service.get_total_users_count() if not search else 0
    users_list = []
    
    if users_data and 'users' in users_data:
        users_list = users_data['users']
        
        # Get last activity for all users at once
        user_emails = [user.get('email_id') for user in users_list if user.get('email_id')]
        users_activity = me_service.get_users_last_activity(user_emails)
        
        # Process additional fields for each user
        for user in users_list:
            user_id = user.get('id')
            user_email = user.get('email_id') or ''
            user_email_lower = user_email.lower() if user_email else ''
            
            # Process department information
            department = user.get('department', {})
            if isinstance(department, dict):
                user['department'] = department.get('name', 'N/A')
            else:
                user['department'] = 'N/A'
            
            # Get actual last activity from batch results
            if user_email_lower in users_activity:
                try:
                    import datetime
                    user['last_login'] = datetime.datetime.fromtimestamp(users_activity[user_email_lower])
                except:
                    user['last_login'] = None
            else:
                user['last_login'] = None
            
            # Try to get company info for each user
            if user_id:
                try:
                    user_details = me_service.get_user_details(user_id)
                    if user_details and 'user' in user_details:
                        account = user_details['user'].get('account', {})
                        if isinstance(account, dict):
                            user['company'] = account.get('name', '')
                        else:
                            user['company'] = ''
                    else:
                        user['company'] = ''
                except:
                    user['company'] = ''
            else:
                user['company'] = ''
    
    # Calculate pagination info
    has_next = len(users_list) == per_page
    has_prev = page > 1
    
    context = {
        'technicians': users_list, 
        'show_all_users': True,
        'current_page': page,
        'has_next': has_next,
        'has_prev': has_prev,
        'next_page': page + 1 if has_next else None,
        'prev_page': page - 1 if has_prev else None,
        'total_users': total_users,
        'current_page_count': len(users_list),
        'search_query': search,
        'companies': companies
    }
    
    return render(request, 'tickets/technicians.html', context)

@login_required
def update_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id, created_by=request.user)
    
    if request.method == 'POST':
        form = TicketForm(request.POST, instance=ticket)
        if form.is_valid():
            updated_ticket = form.save()
            
            # Update in ManageEngine
            if ticket.manage_engine_id:
                me_service = ManageEngineService()
                updates = {
                    'subject': updated_ticket.title,
                    'description': updated_ticket.description,
                    'priority': {'name': updated_ticket.priority}
                }
                me_response = me_service.update_ticket(ticket.manage_engine_id, updates)
                if me_response:
                    messages.success(request, 'Ticket updated successfully in both systems!')
                else:
                    messages.warning(request, 'Ticket updated locally but failed to sync with ManageEngine')
            else:
                messages.success(request, 'Ticket updated successfully!')
            
            return redirect('view_ticket', ticket_id=ticket.id)
    else:
        form = TicketForm(instance=ticket)
    
    return render(request, 'tickets/update_ticket.html', {'form': form, 'ticket': ticket})

@login_required
@require_http_methods(["POST"])
def delete_ticket(request, ticket_id):
    """Delete a ticket"""
    try:
        ticket = get_object_or_404(Ticket, id=ticket_id, created_by=request.user)
        ticket_title = ticket.title
        
        # Delete from ManageEngine if it has an external ID
        if ticket.manage_engine_id:
            try:
                service = ManageEngineService()
                service.delete_ticket(ticket.manage_engine_id)
            except Exception as e:
                # Log error but continue with local deletion
                pass
        
        ticket.delete()
        return JsonResponse({'success': True, 'message': f'Ticket "{ticket_title}" deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_http_methods(["POST"])
def add_technician(request):
    """Add a new technician"""
    try:
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        company = request.POST.get('company', '')
        
        if not name or not email:
            return JsonResponse({'success': False, 'message': 'Name and email are required'})
        
        # Add to ManageEngine
        service = ManageEngineService()
        user_data = {
            'name': name,
            'email_id': email,
            'phone': phone,
            'company': company
        }
        
        result = service.create_user(user_data)
        return JsonResponse({'success': True, 'message': f'User "{name}" added successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_http_methods(["POST"])
def edit_technician(request, user_id):
    """Edit a technician"""
    try:
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        company = request.POST.get('company', '')
        
        if not name or not email:
            return JsonResponse({'success': False, 'message': 'Name and email are required'})
        
        # Update in ManageEngine
        service = ManageEngineService()
        user_data = {
            'name': name,
            'email_id': email,
            'phone': phone,
            'company': company
        }
        
        result = service.update_user(user_id, user_data)
        return JsonResponse({'success': True, 'message': f'User "{name}" updated successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
@require_http_methods(["POST"])
def delete_technician(request, user_id):
    """Delete a technician"""
    try:
        # Delete from ManageEngine
        service = ManageEngineService()
        result = service.delete_user(user_id)
        return JsonResponse({'success': True, 'message': 'User deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def historical_tickets_api(request):
    """API endpoint to get historical ticket data for the last 2 months"""
    try:
        months = int(request.GET.get('months', 2))
        service = ManageEngineService()
        data = service.get_historical_tickets(months=months)
        
        if data:
            return JsonResponse({
                'success': True,
                'data': data
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Failed to fetch historical data'
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@login_required
def reports_dashboard(request):
    """Main reports dashboard"""
    from .report_service import ManageEngineReportService
    from datetime import date
    
    report_service = ManageEngineReportService()
    companies = report_service.get_available_companies()
    technicians = report_service.get_available_technicians()
    
    template = 'tickets/reports_dashboard_embed.html' if request.GET.get('embed') else 'tickets/reports_dashboard.html'
    
    return render(request, template, {
        'companies': companies,
        'technicians': technicians,
        'today': date.today().strftime('%Y-%m-%d')
    })

@login_required
def generate_report(request):
    """Generate report based on parameters"""
    from .report_service import ManageEngineReportService
    from django.http import HttpResponse
    
    report_service = ManageEngineReportService()
    report_type = request.GET.get('type', 'daily')
    download = request.GET.get('download', 'false') == 'true'
    
    report_data = None
    
    if report_type == 'daily':
        date_str = request.GET.get('date')
        date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None
        report_data = report_service.get_daily_report(date)
    
    elif report_type == 'weekly':
        date_str = request.GET.get('start_date')
        start_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None
        report_data = report_service.get_weekly_report(start_date)
    
    elif report_type == 'monthly':
        year = int(request.GET.get('year', datetime.now().year))
        month = int(request.GET.get('month', datetime.now().month))
        report_data = report_service.get_monthly_report(year, month)
    
    elif report_type == 'company':
        company_name = request.GET.get('company')
        report_data = report_service.get_company_report(company_name)
    
    elif report_type == 'technician':
        technician_name = request.GET.get('technician')
        report_data = report_service.get_technician_report(technician_name)
    
    # Download as CSV
    if download and report_data:
        csv_data = report_service.export_to_csv(report_data)
        response = HttpResponse(csv_data, content_type='text/csv')
        filename = f"{report_type}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    # Return JSON for AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Convert datetime objects to strings for JSON serialization
        if report_data:
            report_data['generated_at'] = report_data['generated_at'].strftime('%Y-%m-%d %H:%M:%S')
            if report_data.get('start_date'):
                report_data['start_date'] = report_data['start_date'].strftime('%Y-%m-%d')
            if report_data.get('end_date'):
                report_data['end_date'] = report_data['end_date'].strftime('%Y-%m-%d')
            for ticket in report_data.get('tickets', []):
                if ticket.get('created_at'):
                    ticket['created_at'] = ticket['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        
        return JsonResponse(report_data, safe=False)
    
    return render(request, 'tickets/report_view.html', {'report': report_data})
