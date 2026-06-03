from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from .services import Office365API
from .customer_config import get_all_customers, get_canonical_key
from django.contrib import messages
import csv


@login_required
def dashboard(request):
    """Office 365 dashboard showing license and usage overview"""
    from .customer_config import resolve_customer_key

    try:
        profile = request.user.userprofile
        user_role = profile.get_role()
        user_company = profile.company
    except Exception:
        user_role = 'admin'
        user_company = None

    if user_role == 'customer' and user_company:
        # Customer: always show their own company, no switching allowed
        resolved = resolve_customer_key(user_company.name)
        selected_customer = resolved or 'cgl'
    else:
        # Admin/technician: manual selection, default to CGL (first real tenant)
        raw = request.session.get('office365_customer', 'cgl')
        selected_customer = get_canonical_key(raw)  # resolve legacy aliases like '301'

    # Handle customer selection (admin/technician only)
    if request.method == 'POST' and 'customer' in request.POST:
        if user_role != 'customer':
            selected_customer = get_canonical_key(request.POST['customer'])
            request.session['office365_customer'] = selected_customer
        return redirect('office365:dashboard')
    
    api = Office365API(customer_key=selected_customer)
    is_demo = api._is_demo_mode()

    try:
        license_summary = api.get_license_summary()
        license_breakdown = api.get_license_breakdown()
        mailbox_data = api.get_mailbox_usage()
        user_activity = api.get_user_activity()

        total_licenses = sum(lic['total'] for lic in license_summary)
        consumed_licenses = sum(lic['consumed'] for lic in license_summary)
        available_licenses = max(0, total_licenses - consumed_licenses)
        overallocated_skus = [lic for lic in license_summary if lic.get('overallocated')]
        warning_skus = [lic for lic in license_summary if lic.get('in_warning')]

        context = {
            'license_summary': license_summary,
            'license_breakdown': license_breakdown,
            'mailbox_data': mailbox_data,
            'user_activity': user_activity[:10],
            'total_licenses': total_licenses,
            'consumed_licenses': consumed_licenses,
            'available_licenses': available_licenses,
            'license_usage_percent': round((consumed_licenses / total_licenses * 100), 1) if total_licenses > 0 else 0,
            'high_usage_count': len(mailbox_data.get('high_usage', [])),
            'total_mailboxes': mailbox_data.get('total_mailboxes', 0),
            'overallocated_skus': overallocated_skus,
            'warning_skus': warning_skus,
            'customers': get_all_customers(),
            'selected_customer': selected_customer,
            'user_role': user_role,
            'is_demo': is_demo,
        }

        return render(request, 'office365/dashboard.html', context)

    except Exception as e:
        messages.error(request, f'Error connecting to Office 365: {str(e)}')
        return render(request, 'office365/dashboard.html', {
            'license_summary': [], 'license_breakdown': {},
            'mailbox_data': {'all_mailboxes': [], 'high_usage': []},
            'user_activity': [], 'total_licenses': 0,
            'consumed_licenses': 0, 'available_licenses': 0,
            'license_usage_percent': 0, 'high_usage_count': 0,
            'total_mailboxes': 0, 'customers': get_all_customers(),
            'selected_customer': selected_customer, 'user_role': user_role,
            'is_demo': is_demo, 'error': str(e),
        })


@login_required
def download_high_storage_users(request):
    """Download CSV of users with high mailbox storage usage"""
    selected_customer = get_canonical_key(request.session.get('office365_customer', 'cgl'))
    
    try:
        api = Office365API(customer_key=selected_customer)
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
    selected_customer = get_canonical_key(request.session.get('office365_customer', 'cgl'))
    
    try:
        api = Office365API(customer_key=selected_customer)
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
    selected_customer = get_canonical_key(request.session.get('office365_customer', 'cgl'))
    
    try:
        api = Office365API(customer_key=selected_customer)
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
    selected_customer = get_canonical_key(request.session.get('office365_customer', 'cgl'))
    
    try:
        api = Office365API(customer_key=selected_customer)
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
            'total_users': len(teams_data),
            'customers': get_all_customers(),
            'selected_customer': selected_customer
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
            'customers': get_all_customers(),
            'selected_customer': selected_customer,
            'error': str(e)
        })


@login_required
def email_analytics(request):
    """Email activity analytics"""
    selected_customer = get_canonical_key(request.session.get('office365_customer', 'cgl'))
    
    try:
        api = Office365API(customer_key=selected_customer)
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
            'total_users': len(email_data),
            'customers': get_all_customers(),
            'selected_customer': selected_customer
        }
        
        return render(request, 'office365/email_analytics.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading email analytics: {str(e)}')
        return render(request, 'office365/email_analytics.html', {
            'email_data': [],
            'customers': get_all_customers(),
            'selected_customer': selected_customer,
            'error': str(e)
        })


@login_required
def check_permissions(request):
    """Diagnostic: test which Graph API permissions are working."""
    try:
        role = request.user.userprofile.get_role()
    except Exception:
        role = 'admin'
    if role == 'customer':
        return JsonResponse({'error': 'Access denied'}, status=403)

    # Allow ?customer= override so any tenant can be tested directly
    customer_param = request.GET.get('customer', '').strip()
    if customer_param:
        selected_customer = get_canonical_key(customer_param)
    else:
        selected_customer = get_canonical_key(request.session.get('office365_customer', 'cgl'))
    api = Office365API(customer_key=selected_customer)

    import requests as req
    results = {}

    try:
        headers = api._get_headers()

        # Test 1: basic users list (User.Read.All)
        try:
            r = req.get(
                "https://graph.microsoft.com/v1.0/users?$select=id,displayName&$top=1",
                headers=headers, timeout=10
            )
            results['User.Read.All'] = {'status': r.status_code, 'ok': r.status_code == 200}
        except Exception as e:
            results['User.Read.All'] = {'status': 'error', 'ok': False, 'error': str(e)}

        # Test 2: signInActivity (AuditLog.Read.All)
        try:
            r = req.get(
                "https://graph.microsoft.com/v1.0/users?$select=id,signInActivity&$top=1",
                headers=headers, timeout=10
            )
            try:
                err_body = r.json() if r.status_code != 200 else {}
            except Exception:
                err_body = {}
            results['AuditLog.Read.All (signInActivity)'] = {
                'status': r.status_code,
                'ok': r.status_code == 200,
                'error_code': err_body.get('error', {}).get('code', ''),
                'error_message': err_body.get('error', {}).get('message', ''),
            }
        except Exception as e:
            results['AuditLog.Read.All (signInActivity)'] = {'status': 'error', 'ok': False, 'error': str(e)}

        # Test 3: MFA v1.0
        try:
            r = req.get(
                "https://graph.microsoft.com/v1.0/reports/authenticationMethods/userRegistrationDetails",
                headers=headers, timeout=10
            )
            try:
                err_body = r.json() if r.status_code != 200 else {}
            except Exception:
                err_body = {}
            results['UserAuthenticationMethod.Read.All (MFA v1)'] = {
                'status': r.status_code,
                'ok': r.status_code == 200,
                'error_code': err_body.get('error', {}).get('code', ''),
                'error_message': err_body.get('error', {}).get('message', ''),
            }
        except Exception as e:
            results['UserAuthenticationMethod.Read.All (MFA v1)'] = {'status': 'error', 'ok': False, 'error': str(e)}

        # Test 3b: MFA beta endpoint
        try:
            r = req.get(
                "https://graph.microsoft.com/beta/reports/authenticationMethods/userRegistrationDetails",
                headers=headers, timeout=10
            )
            try:
                err_body = r.json() if r.status_code != 200 else {}
            except Exception:
                err_body = {}
            results['UserAuthenticationMethod.Read.All (MFA beta)'] = {
                'status': r.status_code,
                'ok': r.status_code == 200,
                'error_code': err_body.get('error', {}).get('code', ''),
                'error_message': err_body.get('error', {}).get('message', ''),
            }
        except Exception as e:
            results['UserAuthenticationMethod.Read.All (MFA beta)'] = {'status': 'error', 'ok': False, 'error': str(e)}

        # Test 4: licenses (Organization.Read.All)
        try:
            r = req.get(
                "https://graph.microsoft.com/v1.0/subscribedSkus",
                headers=headers, timeout=10
            )
            results['Organization.Read.All (licenses)'] = {'status': r.status_code, 'ok': r.status_code == 200}
        except Exception as e:
            results['Organization.Read.All (licenses)'] = {'status': 'error', 'ok': False, 'error': str(e)}

    except Exception as e:
        return JsonResponse({'error': f'Token error: {str(e)}'}, status=500)

    return JsonResponse({'permissions': results, 'customer': selected_customer})


@login_required
def raw_skus(request):
    """Diagnostic: show ALL raw SKU data from Microsoft API — admin/technician only."""
    try:
        role = request.user.userprofile.get_role()
    except Exception:
        role = 'admin'
    if role == 'customer':
        return JsonResponse({'error': 'Access denied'}, status=403)

    selected_customer = get_canonical_key(request.session.get('office365_customer', 'cgl'))
    api = Office365API(customer_key=selected_customer)
    try:
        import requests as req
        headers = api._get_headers()
        resp = req.get("https://graph.microsoft.com/v1.0/subscribedSkus", headers=headers)
        resp.raise_for_status()
        raw = resp.json().get('value', [])
        result = []
        for sku in raw:
            prepaid = sku.get('prepaidUnits', {})
            result.append({
                'skuPartNumber': sku.get('skuPartNumber'),
                'skuId': sku.get('skuId'),
                'capabilityStatus': sku.get('capabilityStatus'),
                'consumedUnits': sku.get('consumedUnits'),
                'prepaidEnabled': prepaid.get('enabled'),
                'prepaidSuspended': prepaid.get('suspended'),
                'prepaidWarning': prepaid.get('warning'),
            })
        result.sort(key=lambda x: x['consumedUnits'] or 0, reverse=True)
        return JsonResponse({'skus': result, 'count': len(result)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_summary(request):
    """API endpoint for dashboard summary data"""
    selected_customer = get_canonical_key(request.session.get('office365_customer', 'cgl'))

    try:
        api = Office365API(customer_key=selected_customer)
        summary = api.get_dashboard_summary()
        return JsonResponse({'success': True, 'data': summary})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def download_all_users(request):
    """Download CSV of all users with their license assignments — admin/technician only."""
    try:
        role = request.user.userprofile.get_role()
    except Exception:
        role = 'admin'

    if role == 'customer':
        messages.error(request, 'Access denied.')
        return redirect('office365:dashboard')

    selected_customer = get_canonical_key(request.session.get('office365_customer', 'cgl'))

    try:
        api = Office365API(customer_key=selected_customer)

        if api._is_demo_mode():
            messages.warning(request, 'Office 365 credentials not configured for this company.')
            return redirect('office365:dashboard')

        users = api.get_all_users_with_licenses()

        response = HttpResponse(content_type='text/csv')
        from .customer_config import get_customer_config
        company = (get_customer_config(selected_customer) or {}).get('name', selected_customer)
        response['Content-Disposition'] = f'attachment; filename="o365_users_{company}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Display Name', 'Email / UPN', 'Account Status',
            'Job Title', 'Department', 'Usage Location',
            'License Count', 'Licenses Assigned'
        ])
        for u in users:
            writer.writerow([
                u['display_name'], u['upn'],
                'Active' if u['account_enabled'] else 'Disabled',
                u['job_title'], u['department'], u['usage_location'],
                u['license_count'], u['licenses'],
            ])
        return response

    except Exception as e:
        messages.error(request, f'Error downloading users: {str(e)}')
        return redirect('office365:dashboard')


@login_required
def download_license_report(request):
    """Download CSV of license SKU summary — admin/technician only."""
    try:
        role = request.user.userprofile.get_role()
    except Exception:
        role = 'admin'

    if role == 'customer':
        messages.error(request, 'Access denied.')
        return redirect('office365:dashboard')

    selected_customer = get_canonical_key(request.session.get('office365_customer', 'cgl'))

    try:
        api = Office365API(customer_key=selected_customer)

        if api._is_demo_mode():
            messages.warning(request, 'Office 365 credentials not configured for this company.')
            return redirect('office365:dashboard')

        skus = api.get_license_summary()

        response = HttpResponse(content_type='text/csv')
        from .customer_config import get_customer_config
        company = (get_customer_config(selected_customer) or {}).get('name', selected_customer)
        response['Content-Disposition'] = f'attachment; filename="o365_licenses_{company}.csv"'

        writer = csv.writer(response)
        writer.writerow(['License Name', 'SKU Code', 'Tier', 'Total', 'Consumed', 'Available', 'Usage %'])
        for s in skus:
            writer.writerow([
                s['display_name'], s['sku_name'], s['tier'].title(),
                s['total'], s['consumed'], s['available'],
                f"{s['usage_percent']}%",
            ])
        return response

    except Exception as e:
        messages.error(request, f'Error downloading license report: {str(e)}')
        return redirect('office365:dashboard')


# ---------------------------------------------------------------------------
# Helper: resolve role + customer for admin/tech views
# ---------------------------------------------------------------------------

def _resolve_tech_context(request):
    """Return (role, selected_customer) — raises PermissionError for customers."""
    try:
        role = request.user.userprofile.get_role()
    except Exception:
        role = 'admin'
    if role == 'customer':
        raise PermissionError("Access denied.")
    selected_customer = get_canonical_key(request.session.get('office365_customer', 'cgl'))
    return role, selected_customer


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------

@login_required
def user_management(request):
    """List all users; admin/technician can enable/disable accounts or reset passwords."""
    try:
        role, selected_customer = _resolve_tech_context(request)
    except PermissionError:
        messages.error(request, 'Access denied.')
        return redirect('office365:dashboard')

    api = Office365API(customer_key=selected_customer)

    # POST: toggle account or reset password
    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        user_name = request.POST.get('user_name', user_id)
        try:
            if action == 'enable':
                api.enable_user(user_id)
                messages.success(request, f'Account enabled: {user_name}')
            elif action == 'disable':
                api.disable_user(user_id)
                messages.success(request, f'Account disabled: {user_name}')
            elif action == 'reset_password':
                new_pw = request.POST.get('new_password', '')
                if len(new_pw) < 8:
                    messages.error(request, 'Password must be at least 8 characters.')
                else:
                    api.reset_password(user_id, new_pw)
                    messages.success(request, f'Password reset for: {user_name}')
            else:
                messages.error(request, 'Unknown action.')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
        return redirect('office365:user_management')

    # GET: list users
    search = request.GET.get('search', '').strip().lower()
    status_filter = request.GET.get('status', 'all')
    license_filter = request.GET.get('licensed', 'all')

    try:
        users = api.get_all_users_detailed()
    except Exception as e:
        messages.error(request, f'Error loading users: {str(e)}')
        users = []

    # Filter
    if search:
        users = [u for u in users if search in u['display_name'].lower() or search in u['upn'].lower()
                 or search in (u['department'] or '').lower()]
    if status_filter == 'enabled':
        users = [u for u in users if u['account_enabled']]
    elif status_filter == 'disabled':
        users = [u for u in users if not u['account_enabled']]
    if license_filter == 'licensed':
        users = [u for u in users if u['license_count'] > 0]
    elif license_filter == 'unlicensed':
        users = [u for u in users if u['license_count'] == 0]

    from django.core.paginator import Paginator
    paginator = Paginator(users, 25)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'office365/user_management.html', {
        'users': page,
        'total_users': len(users),
        'search': search,
        'status_filter': status_filter,
        'license_filter': license_filter,
        'customers': get_all_customers(),
        'selected_customer': selected_customer,
        'user_role': role,
        'is_demo': api._is_demo_mode(),
    })


# ---------------------------------------------------------------------------
# Inactive Users Report
# ---------------------------------------------------------------------------

@login_required
def inactive_users(request):
    """Show users who have not signed in within a configurable number of days."""
    try:
        role, selected_customer = _resolve_tech_context(request)
    except PermissionError:
        messages.error(request, 'Access denied.')
        return redirect('office365:dashboard')

    days = int(request.GET.get('days', 30))
    if days not in (30, 60, 90):
        days = 30

    api = Office365API(customer_key=selected_customer)
    has_signin_data = True
    premium_required = False
    try:
        result = api.get_inactive_users(days=days)
        users = result['users']
        has_signin_data = result['has_signin_data']
        premium_required = result.get('premium_required', False)
    except Exception as e:
        messages.error(request, f'Error loading inactive users: {str(e)}')
        users = []

    licensed_inactive = [u for u in users if u['license_count'] > 0]

    return render(request, 'office365/inactive_users.html', {
        'users': users,
        'licensed_inactive': licensed_inactive,
        'days': days,
        'total_inactive': len(users),
        'licensed_waste': len(licensed_inactive),
        'has_signin_data': has_signin_data,
        'premium_required': premium_required,
        'customers': get_all_customers(),
        'selected_customer': selected_customer,
        'user_role': role,
        'is_demo': api._is_demo_mode(),
    })


# ---------------------------------------------------------------------------
# MFA Status Report
# ---------------------------------------------------------------------------

@login_required
def mfa_status(request):
    """Show MFA registration and enablement status per user."""
    try:
        role, selected_customer = _resolve_tech_context(request)
    except PermissionError:
        messages.error(request, 'Access denied.')
        return redirect('office365:dashboard')

    filter_type = request.GET.get('filter', 'all')  # all / no_mfa / mfa_enabled

    api = Office365API(customer_key=selected_customer)
    mfa_permission_error = False
    mfa_premium_required = False
    try:
        result = api.get_mfa_status()
        mfa_data = result['data']
        mfa_permission_error = result['permission_error']
        mfa_premium_required = result.get('premium_required', False)
    except Exception as e:
        messages.error(request, f'Error loading MFA status: {str(e)}')
        mfa_data = []

    total = len(mfa_data)
    mfa_registered = sum(1 for u in mfa_data if u['is_registered'])
    mfa_not_registered = total - mfa_registered

    if filter_type == 'no_mfa':
        mfa_data = [u for u in mfa_data if not u['is_registered']]
    elif filter_type == 'mfa_enabled':
        mfa_data = [u for u in mfa_data if u['is_registered']]

    from django.core.paginator import Paginator
    paginator = Paginator(mfa_data, 25)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'office365/mfa_status.html', {
        'users': page,
        'total': total,
        'mfa_registered': mfa_registered,
        'mfa_not_registered': mfa_not_registered,
        'mfa_percent': round(mfa_registered / total * 100, 1) if total else 0,
        'filter_type': filter_type,
        'mfa_permission_error': mfa_permission_error,
        'mfa_premium_required': mfa_premium_required,
        'customers': get_all_customers(),
        'selected_customer': selected_customer,
        'user_role': role,
        'is_demo': api._is_demo_mode(),
    })


# ---------------------------------------------------------------------------
# Guest Users
# ---------------------------------------------------------------------------

@login_required
def guest_users(request):
    """List all external/guest accounts in the tenant."""
    try:
        role, selected_customer = _resolve_tech_context(request)
    except PermissionError:
        messages.error(request, 'Access denied.')
        return redirect('office365:dashboard')

    # POST: disable guest
    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        user_name = request.POST.get('user_name', user_id)
        api = Office365API(customer_key=selected_customer)
        try:
            if action == 'disable':
                api.disable_user(user_id)
                messages.success(request, f'Guest account disabled: {user_name}')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
        return redirect('office365:guest_users')

    api = Office365API(customer_key=selected_customer)
    try:
        guests = api.get_guest_users()
    except Exception as e:
        messages.error(request, f'Error loading guests: {str(e)}')
        guests = []

    pending = [g for g in guests if g['external_state'] == 'PendingAcceptance']
    active = [g for g in guests if g['account_enabled'] and g['external_state'] != 'PendingAcceptance']

    return render(request, 'office365/guest_users.html', {
        'guests': guests,
        'active_guests': len(active),
        'pending_guests': len(pending),
        'total_guests': len(guests),
        'customers': get_all_customers(),
        'selected_customer': selected_customer,
        'user_role': role,
        'is_demo': api._is_demo_mode(),
    })


# ---------------------------------------------------------------------------
# OneDrive Storage
# ---------------------------------------------------------------------------

@login_required
def onedrive_usage(request):
    """Per-user OneDrive storage usage report."""
    try:
        role, selected_customer = _resolve_tech_context(request)
    except PermissionError:
        messages.error(request, 'Access denied.')
        return redirect('office365:dashboard')

    period = request.GET.get('period', 'D30')
    if period not in ('D7', 'D30', 'D90', 'D180'):
        period = 'D30'

    api = Office365API(customer_key=selected_customer)
    try:
        data = api.get_onedrive_usage(period=period)
    except Exception as e:
        messages.error(request, f'Error loading OneDrive data: {str(e)}')
        data = {'users': [], 'total_used_gb': 0, 'high_usage': []}

    users = data['users']
    from django.core.paginator import Paginator
    paginator = Paginator(users, 25)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'office365/onedrive_usage.html', {
        'users': page,
        'total_users': len(users),
        'total_used_gb': data['total_used_gb'],
        'high_usage_count': len(data['high_usage']),
        'period': period,
        'customers': get_all_customers(),
        'selected_customer': selected_customer,
        'user_role': role,
        'is_demo': api._is_demo_mode(),
    })
