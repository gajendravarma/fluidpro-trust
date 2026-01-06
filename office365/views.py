from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from .services import Office365API
from django.contrib import messages
import csv


@login_required
def dashboard(request):
    """Office 365 dashboard showing license and usage overview"""
    try:
        api = Office365API()
        
        # Get license summary
        license_summary = api.get_license_summary()
        
        # Get mailbox usage
        mailbox_data = api.get_mailbox_usage()
        
        # Get user activity
        user_activity = api.get_user_activity()
        
        # Calculate totals
        total_licenses = sum(lic['total'] for lic in license_summary)
        consumed_licenses = sum(lic['consumed'] for lic in license_summary)
        available_licenses = total_licenses - consumed_licenses
        
        context = {
            'license_summary': license_summary,
            'mailbox_data': mailbox_data,
            'user_activity': user_activity[:10],  # Show top 10
            'total_licenses': total_licenses,
            'consumed_licenses': consumed_licenses,
            'available_licenses': available_licenses,
            'license_usage_percent': (consumed_licenses / total_licenses * 100) if total_licenses > 0 else 0,
            'high_usage_count': len(mailbox_data.get('high_usage', [])),
            'total_mailboxes': mailbox_data.get('total_mailboxes', 0)
        }
        
        return render(request, 'office365/dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f'Error connecting to Office 365: {str(e)}')
        return render(request, 'office365/dashboard.html', {
            'license_summary': [],
            'mailbox_data': {'all_mailboxes': [], 'high_usage': []},
            'user_activity': [],
            'total_licenses': 0,
            'consumed_licenses': 0,
            'available_licenses': 0,
            'license_usage_percent': 0,
            'high_usage_count': 0,
            'total_mailboxes': 0,
            'error': str(e)
        })


@login_required
def download_high_storage_users(request):
    """Download CSV of users with high mailbox storage usage"""
    try:
        api = Office365API()
        mailbox_data = api.get_mailbox_usage()
        high_usage_users = mailbox_data.get('high_usage', [])
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="high_storage_users.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Email', 'Display Name', 'Used %', 'Used GB', 'Quota GB'])
        
        for user in high_usage_users:
            writer.writerow([
                user['upn'],
                user['display_name'],
                f"{user['used_percent']:.1f}%",
                f"{user['used_gb']:.2f}",
                f"{user['quota_gb']:.2f}"
            ])
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error downloading data: {str(e)}')
        return redirect('office365:dashboard')


@login_required
def license_details(request):
    """Detailed license information"""
    try:
        api = Office365API()
        license_summary = api.get_license_summary()
        
        return JsonResponse({
            'success': True,
            'licenses': license_summary
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def mailbox_details(request):
    """Detailed mailbox usage information"""
    try:
        api = Office365API()
        mailbox_data = api.get_mailbox_usage()
        
        return JsonResponse({
            'success': True,
            'mailboxes': mailbox_data['all_mailboxes'],
            'high_usage': mailbox_data['high_usage']
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def teams_analytics(request):
    """Teams usage analytics"""
    try:
        api = Office365API()
        teams_data = api.get_teams_usage()
        
        # Debug: Check if we have any data
        if not teams_data:
            messages.warning(request, 'No Teams usage data available. This may be due to insufficient permissions or no Teams activity in the selected period.')
        
        # Calculate summary stats
        total_messages = sum(t['team_chat_messages'] + t['private_chat_messages'] for t in teams_data)
        total_meetings = sum(t['meetings'] for t in teams_data)
        active_users = len([t for t in teams_data if t['team_chat_messages'] > 0 or t['meetings'] > 0])
        
        context = {
            'teams_data': teams_data[:20],  # Top 20 users
            'total_messages': total_messages,
            'total_meetings': total_meetings,
            'active_users': active_users,
            'total_users': len(teams_data)
        }
        
        return render(request, 'office365/teams_analytics.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading Teams analytics: {str(e)}')
        return render(request, 'office365/teams_analytics.html', {
            'teams_data': [],
            'total_messages': 0,
            'total_meetings': 0,
            'active_users': 0,
            'total_users': 0,
            'error': str(e)
        })


@login_required
def email_analytics(request):
    """Email activity analytics"""
    try:
        api = Office365API()
        email_data = api.get_email_activity()
        
        # Calculate summary stats
        total_sent = sum(e['send_count'] for e in email_data)
        total_received = sum(e['receive_count'] for e in email_data)
        active_users = len([e for e in email_data if e['send_count'] > 0])
        
        context = {
            'email_data': email_data[:20],  # Top 20 users
            'total_sent': total_sent,
            'total_received': total_received,
            'active_users': active_users,
            'total_users': len(email_data)
        }
        
        return render(request, 'office365/email_analytics.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading email analytics: {str(e)}')
        return render(request, 'office365/email_analytics.html', {
            'email_data': [],
            'error': str(e)
        })


@login_required
def api_summary(request):
    """API endpoint for dashboard summary data"""
    try:
        api = Office365API()
        summary = api.get_dashboard_summary()
        
        return JsonResponse({
            'success': True,
            'data': summary
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
