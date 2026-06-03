import requests
import csv
import io
from django.conf import settings
from .customer_config import get_customer_config

# SKUs to exclude — free plans, trial, internal Microsoft services
EXCLUDED_SKUS = {
    # Free / viral / trial plans
    'FLOW_FREE', 'POWERAPPS_VIRAL', 'POWERAPPS_DEV',
    'TEAMS_FREE', 'TEAMS_FREE_SERVICE', 'MICROSOFT_TEAMS_EXPLORATORY', 'TEAMS_EXPLORATORY',
    'INTUNE_FREE', 'MCOFREE', 'RIGHTSMANAGEMENT_ADHOC',
    'CCIBOTS_PRIVPREV_VIRAL', 'Dynamics_365_Hiring_Free',
    # PSTN / telephony add-ons with large seat pools
    'MCOPSTNC', 'MCOPSTN_5', 'MCOPSTN2', 'MCOCAP', 'MCOEV_VIRTUALUSER',
    'PHONESYSTEM_VIRTUALUSER', 'PHONESYSTEM_VIRTUALUSER_GOV', 'MCOMEETADV',
    # Security / compliance trial plans
    'WIN_DEF_ATP', 'ATP_ENTERPRISE_FACULTY',
    # CRM / Power Platform free
    'CRMPLAN2', 'DYN365_ENTERPRISE_PLAN1',
    'POWER_BI_STANDARD', 'POWER_BI_BASIC',
    # Education / faculty / student plans
    'OFFICESUBSCRIPTION_FACULTY', 'STANDARDPACK_FACULTY', 'STANDARDWOFFPACK_FACULTY',
    'DEVELOPERPACK', 'DEVELOPERPACK_E3', 'STANDARDPACK_STUDENT',
    'ENTERPRISEWITHSCAL_FACULTY', 'ENTERPRISEWITHSCAL_STUDENT',
    'DESKLESSPACK', 'DESKLESSSUITE',
    # Internal Microsoft service plans
    'MICROSOFT_BUSINESS_CENTER', 'SPZA_IW', 'WINDOWS_STORE',
    'WORKPLACE_ANALYTICS', 'PROJECTWORKMANAGEMENT',
}

# Human-readable SKU name mapping — covers both legacy and modern SKU part numbers
SKU_DISPLAY_NAMES = {
    # Business plans
    'O365_BUSINESS_PREMIUM': 'Microsoft 365 Business Premium',
    'SPB': 'Microsoft 365 Business Premium',
    'O365_BUSINESS_ESSENTIALS': 'Microsoft 365 Business Basic',
    'O365_BUSINESS_BASIC': 'Microsoft 365 Business Basic',
    'SMB_BUSINESS_ESSENTIALS': 'Microsoft 365 Business Basic',
    'O365_BUSINESS': 'Microsoft 365 Apps for Business',
    'SMB_BUSINESS': 'Microsoft 365 Apps for Business',
    'O365_BUSINESS_PREMIUM_EEA': 'Microsoft 365 Business Premium',
    'Microsoft_365_Business_Standard': 'Microsoft 365 Business Standard',
    'Microsoft_365_Business_Basic': 'Microsoft 365 Business Basic',
    # Enterprise plans
    'OFFICE_365_E1': 'Office 365 E1',
    'STANDARDPACK': 'Office 365 E1',
    'OFFICE_365_E3': 'Office 365 E3',
    'ENTERPRISEPACK': 'Office 365 E3',
    'OFFICE_365_E5': 'Office 365 E5',
    'ENTERPRISEPREMIUM': 'Office 365 E5',
    'MICROSOFT_365_E3': 'Microsoft 365 E3',
    'SPE_E3': 'Microsoft 365 E3',
    'MICROSOFT_365_E5': 'Microsoft 365 E5',
    'SPE_E5': 'Microsoft 365 E5',
    # Teams
    'TEAMS_ESSENTIALS_AAD': 'Microsoft Teams Essentials',
    'TEAMS_PREMIUM': 'Microsoft Teams Premium',
    # Exchange / archiving
    'EXCHANGEARCHIVE_ADDON': 'Exchange Online Archiving',
    'EXCHANGE_S_DESKLESS': 'Exchange Online Kiosk',
    # EMS / Intune
    'EMS': 'Enterprise Mobility + Security E3',
    'EMSPREMIUM': 'Enterprise Mobility + Security E5',
    'INTUNE_A': 'Microsoft Intune',
    # Azure AD
    'AAD_PREMIUM': 'Azure AD Premium P1',
    'AAD_PREMIUM_P2': 'Azure AD Premium P2',
    # Power Platform
    'POWER_BI_PRO': 'Power BI Pro',
    'POWER_BI_PREMIUM_PER_USER': 'Power BI Premium Per User',
    # Project / Visio
    'PROJECTPROFESSIONAL': 'Project Plan 3',
    'PROJECTPREMIUM': 'Project Plan 5',
    'VISIOCLIENT': 'Visio Plan 2',
    'VISIOONLINE_PLAN1': 'Visio Plan 1',
    # Phone / voice
    'MCOEV': 'Microsoft Teams Phone',
    'MCOPSTN1': 'Microsoft 365 Domestic Calling Plan',
    'MCOPSTN2': 'Microsoft 365 International Calling Plan',
    # Teams Premium variants
    'TEAMS_PREMIUM': 'Microsoft Teams Premium',
    'Teams_Premium_(for_Departments)': 'Microsoft Teams Premium (Departments)',
    # Dynamics / Forms
    'DYN365_BUSINESS_MARKETING': 'Dynamics 365 Marketing',
    'FORMS_PRO': 'Dynamics 365 Customer Voice',
}

# Tier classification — list all known SKU codes per tier
SKU_TIERS = {
    'basic': [
        'O365_BUSINESS_ESSENTIALS', 'O365_BUSINESS_BASIC', 'SMB_BUSINESS_ESSENTIALS',
        'Microsoft_365_Business_Basic', 'OFFICE_365_E1', 'STANDARDPACK',
        'TEAMS_ESSENTIALS_AAD', 'EXCHANGEARCHIVE_ADDON', 'EXCHANGE_S_DESKLESS',
    ],
    'standard': [
        'Microsoft_365_Business_Standard', 'SMB_BUSINESS',
        'O365_BUSINESS', 'OFFICE_365_E3', 'ENTERPRISEPACK',
        'MICROSOFT_365_E3', 'SPE_E3', 'EMS', 'INTUNE_A',
    ],
    'premium': [
        # Microsoft 365 Business Premium (formerly O365 Business Premium)
        'O365_BUSINESS_PREMIUM', 'SPB', 'O365_BUSINESS_PREMIUM_EEA',
        # Enterprise E5 / M365 E5
        'OFFICE_365_E5', 'ENTERPRISEPREMIUM', 'MICROSOFT_365_E5', 'SPE_E5',
        'EMSPREMIUM', 'AAD_PREMIUM_P2', 'POWER_BI_PREMIUM_PER_USER',
        'TEAMS_PREMIUM', 'Teams_Premium_(for_Departments)',
    ],
}


class Office365API:
    def __init__(self, customer_key=None):
        if customer_key:
            config = get_customer_config(customer_key)
            if config:
                self.tenant_id = config['tenant_id']
                self.client_id = config['client_id']
                self.client_secret = config['client_secret']
            else:
                raise Exception(f"Customer configuration not found: {customer_key}")
        else:
            # Fallback to settings for backward compatibility
            self.tenant_id = getattr(settings, 'OFFICE365_TENANT_ID', '')
            self.client_id = getattr(settings, 'OFFICE365_CLIENT_ID', '')
            self.client_secret = getattr(settings, 'OFFICE365_CLIENT_SECRET', '')
        self.access_token = None

    def _is_demo_mode(self):
        """True when real credentials are not configured."""
        return (
            self.tenant_id in ('demo-tenant-id', '', None) or
            self.client_id in ('demo-client-id', '', None) or
            self.client_secret in ('demo-secret', '', None)
        )

    def get_access_token(self):
        """Get access token for Microsoft Graph API"""
        if self._is_demo_mode():
            self.access_token = None  # never use demo-token against real API
            return None

        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }
        response = requests.post(token_url, data=token_data)
        response.raise_for_status()
        self.access_token = response.json()["access_token"]
        return self.access_token

    def _get_headers(self):
        """Return auth headers, obtaining a token first if needed."""
        if not self.access_token:
            self.get_access_token()
        if not self.access_token:
            raise Exception("Office 365 credentials not configured for this company.")
        return {"Authorization": f"Bearer {self.access_token}"}

    def get_license_summary(self):
        """Get Office 365 license summary with display names and tier info."""
        if self._is_demo_mode():
            return []

        headers = self._get_headers()
        response = requests.get("https://graph.microsoft.com/v1.0/subscribedSkus", headers=headers)
        response.raise_for_status()

        license_summary = []
        for sku in response.json().get("value", []):
            sku_name = sku.get("skuPartNumber", "")

            # Skip known free/trial/internal plans
            if sku_name in EXCLUDED_SKUS:
                continue

            prepaid = sku.get("prepaidUnits", {})
            enabled = prepaid.get("enabled", 0)
            warning = prepaid.get("warning", 0)
            suspended = prepaid.get("suspended", 0)
            consumed = sku.get("consumedUnits", 0)
            capability_status = sku.get("capabilityStatus", "")

            # Active seats = enabled only.
            # "warning" seats are licenses in a renewal/grace period — still assigned
            # to users but the subscription renewal is pending. We show them separately
            # so the count matches what the Office 365 admin portal shows (active only).
            total = enabled

            # Skip SKUs with no seats at all
            if total == 0 and consumed == 0:
                continue

            # Skip massive free/viral pools (>10,000 seats)
            if total > 10000:
                continue

            # Skip if ratio of total:consumed is absurdly high — free plan symptom
            # (e.g. 20,000 total but only 5 consumed = 4,000:1 ratio → free plan)
            if consumed > 0 and total > 0 and (total / consumed) > 200:
                continue

            # Skip completely unassigned SKUs with very large seat counts
            if consumed == 0 and total > 500:
                continue

            # Last-resort guard: if total is still 0 but seats are consumed
            # (fully expired subscription), treat total = consumed so we
            # at least show 100% usage rather than negative available.
            if total == 0 and consumed > 0:
                total = consumed

            available = max(0, total - consumed)

            # Determine tier
            tier = 'other'
            for t, skus in SKU_TIERS.items():
                if sku_name in skus:
                    tier = t
                    break

            usage_percent = round((consumed / total * 100), 1) if total > 0 else 0

            # Flag subscriptions in warning/renewal state
            in_warning = warning > 0

            license_summary.append({
                'sku_id': sku.get("skuId", ""),
                'sku_name': sku_name,
                'display_name': SKU_DISPLAY_NAMES.get(sku_name, sku_name.replace('_', ' ').title()),
                'tier': tier,
                'total': total,
                'consumed': consumed,
                'available': available,
                'suspended': suspended,
                'warning': warning,          # seats in renewal/grace state
                'usage_percent': usage_percent,
                'in_warning': in_warning,
                'capability_status': capability_status,
                'overallocated': consumed > total,
            })

        return sorted(license_summary, key=lambda x: x['consumed'], reverse=True)

    def get_license_breakdown(self):
        """Return license counts grouped by tier: basic/standard/premium/other."""
        skus = self.get_license_summary()
        breakdown = {'basic': 0, 'standard': 0, 'premium': 0, 'other': 0,
                     'basic_consumed': 0, 'standard_consumed': 0,
                     'premium_consumed': 0, 'other_consumed': 0}
        for s in skus:
            t = s['tier']
            breakdown[t] = breakdown.get(t, 0) + s['total']
            breakdown[f"{t}_consumed"] = breakdown.get(f"{t}_consumed", 0) + s['consumed']
        return breakdown

    def get_all_users_with_licenses(self):
        """Get all users with their assigned license details."""
        if self._is_demo_mode():
            return []

        headers = self._get_headers()
        users = []
        url = ("https://graph.microsoft.com/v1.0/users"
               "?$select=id,displayName,userPrincipalName,accountEnabled,"
               "assignedLicenses,jobTitle,department,usageLocation"
               "&$top=999")

        while url:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            users.extend(data.get('value', []))
            url = data.get('@odata.nextLink')

        # Build SKU id → display name map
        sku_map = {s['sku_id']: s['display_name'] for s in self.get_license_summary()}

        result = []
        for u in users:
            assigned = u.get('assignedLicenses', [])
            license_names = [sku_map.get(lic.get('skuId', ''), lic.get('skuId', 'Unknown'))
                             for lic in assigned]
            result.append({
                'display_name': u.get('displayName', ''),
                'upn': u.get('userPrincipalName', ''),
                'account_enabled': u.get('accountEnabled', True),
                'job_title': u.get('jobTitle', ''),
                'department': u.get('department', ''),
                'usage_location': u.get('usageLocation', ''),
                'license_count': len(assigned),
                'licenses': ', '.join(license_names) if license_names else 'No License',
            })

        return sorted(result, key=lambda x: x['display_name'].lower())

    def get_mailbox_usage(self, period='D30'):
        """Get mailbox usage report."""
        if self._is_demo_mode():
            return {'all_mailboxes': [], 'high_usage': [], 'total_mailboxes': 0}

        headers = self._get_headers()
        report_url = (f"https://graph.microsoft.com/v1.0/reports/"
                      f"getMailboxUsageDetail(period='{period}')?$format=text/csv")
        response = requests.get(report_url, headers=headers)
        response.raise_for_status()

        reader = csv.DictReader(io.StringIO(response.text))
        mailbox_data = []
        high_usage = []
        threshold = 85.0

        for row in reader:
            upn = row.get("User Principal Name") or ""
            display_name = row.get("Display Name") or ""
            storage_used_str = row.get("Storage Used (Byte)", "").strip()
            quota_str = row.get("Prohibit Send/Receive Quota (Byte)", "").strip()

            if not storage_used_str or not quota_str:
                continue

            storage_used = int(storage_used_str.replace(",", ""))
            quota_bytes = int(quota_str.replace(",", ""))
            if quota_bytes <= 0:
                continue

            used_percent = (storage_used * 100.0) / quota_bytes
            used_gb = storage_used / (1024 ** 3)
            quota_gb = quota_bytes / (1024 ** 3)

            info = {'upn': upn, 'display_name': display_name,
                    'used_percent': used_percent, 'used_gb': used_gb, 'quota_gb': quota_gb}
            mailbox_data.append(info)
            if used_percent >= threshold:
                high_usage.append(info)

        return {'all_mailboxes': mailbox_data, 'high_usage': high_usage,
                'total_mailboxes': len(mailbox_data)}

    def get_user_activity(self, period='D30'):
        """Get user activity report."""
        if self._is_demo_mode():
            return []

        try:
            headers = self._get_headers()
            report_url = (f"https://graph.microsoft.com/v1.0/reports/"
                          f"getOffice365ActiveUserDetail(period='{period}')?$format=text/csv")
            response = requests.get(report_url, headers=headers)
            response.raise_for_status()

            reader = csv.DictReader(io.StringIO(response.text))
            active_users = []
            for row in reader:
                dates = [row.get(k, "").strip() for k in [
                    "Exchange Last Activity Date", "Teams Last Activity Date",
                    "SharePoint Last Activity Date", "OneDrive Last Activity Date"
                ] if row.get(k, "").strip()]
                active_users.append({
                    'upn': row.get("User Principal Name", ""),
                    'display_name': row.get("Display Name", ""),
                    'last_activity': max(dates) if dates else "",
                    'exchange_active': row.get("Has Exchange License", "") == "True",
                    'teams_active': row.get("Has Teams License", "") == "True",
                    'sharepoint_active': row.get("Has SharePoint License", "") == "True",
                })
            return active_users
        except Exception:
            return []

    def get_teams_usage(self, period='D30'):
        """Get Teams usage statistics."""
        if self._is_demo_mode():
            return []

        try:
            headers = self._get_headers()
            report_url = (f"https://graph.microsoft.com/v1.0/reports/"
                          f"getTeamsUserActivityUserDetail(period='{period}')?$format=text/csv")
            response = requests.get(report_url, headers=headers)
            response.raise_for_status()

            reader = csv.DictReader(io.StringIO(response.text))
            return [{
                'upn': row.get("User Principal Name", ""),
                'display_name': row.get("Display Name", ""),
                'team_chat_messages': int(row.get("Team Chat Message Count", 0) or 0),
                'private_chat_messages': int(row.get("Private Chat Message Count", 0) or 0),
                'calls': int(row.get("Call Count", 0) or 0),
                'meetings': int(row.get("Meeting Count", 0) or 0),
                'last_activity': row.get("Last Activity Date", ""),
            } for row in reader]
        except Exception:
            return []

    def get_email_activity(self, period='D30'):
        """Get email activity statistics."""
        if self._is_demo_mode():
            return []

        try:
            headers = self._get_headers()
            report_url = (f"https://graph.microsoft.com/v1.0/reports/"
                          f"getEmailActivityUserDetail(period='{period}')?$format=text/csv")
            response = requests.get(report_url, headers=headers)
            response.raise_for_status()

            reader = csv.DictReader(io.StringIO(response.text))
            return [{
                'upn': row.get("User Principal Name", ""),
                'display_name': row.get("Display Name", ""),
                'send_count': int(row.get("Send Count", 0) or 0),
                'receive_count': int(row.get("Receive Count", 0) or 0),
                'read_count': int(row.get("Read Count", 0) or 0),
                'last_activity': row.get("Last Activity Date", ""),
            } for row in reader]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # User Management
    # ------------------------------------------------------------------

    def _fetch_users_with_signin(self):
        """Fetch all users, with signInActivity if permitted.
        Returns (users_list, has_signin_data: bool)."""
        headers = self._get_headers()

        select_with = (
            "id,displayName,userPrincipalName,accountEnabled,"
            "assignedLicenses,jobTitle,department,usageLocation,"
            "userType,createdDateTime,signInActivity"
        )
        select_without = (
            "id,displayName,userPrincipalName,accountEnabled,"
            "assignedLicenses,jobTitle,department,usageLocation,"
            "userType,createdDateTime"
        )

        # Try with signInActivity — if 403, fall back without it
        # 403 with Authentication_RequestFromNonPremiumTenantOrB2CTenant = AAD Premium required
        url = f"https://graph.microsoft.com/v1.0/users?$select={select_with}&$top=999"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 403:
            has_signin_data = False
            url = f"https://graph.microsoft.com/v1.0/users?$select={select_without}&$top=999"
            resp = requests.get(url, headers=headers)
        else:
            has_signin_data = True

        resp.raise_for_status()
        users = []
        data = resp.json()
        users.extend(data.get('value', []))
        url = data.get('@odata.nextLink')

        while url:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            users.extend(data.get('value', []))
            url = data.get('@odata.nextLink')

        return users, has_signin_data

    def get_all_users_detailed(self):
        """Get all users with sign-in activity, MFA hints, and account status.
        signInActivity requires AuditLog.Read.All — falls back gracefully if missing."""
        if self._is_demo_mode():
            return []

        sku_map = {s['sku_id']: s['display_name'] for s in self.get_license_summary()}
        users, has_signin_data = self._fetch_users_with_signin()

        result = []
        for u in users:
            sign_in = u.get('signInActivity') or {}
            last_sign_in = sign_in.get('lastSignInDateTime', '') if has_signin_data else ''
            assigned = u.get('assignedLicenses', [])
            license_names = [sku_map.get(lic.get('skuId', ''), 'Unknown') for lic in assigned]
            result.append({
                'id': u.get('id', ''),
                'display_name': u.get('displayName', ''),
                'upn': u.get('userPrincipalName', ''),
                'account_enabled': u.get('accountEnabled', True),
                'user_type': u.get('userType', 'Member'),
                'job_title': u.get('jobTitle', ''),
                'department': u.get('department', ''),
                'usage_location': u.get('usageLocation', ''),
                'license_count': len(assigned),
                'licenses': ', '.join(license_names) if license_names else 'No License',
                'last_sign_in': last_sign_in,
                'created': u.get('createdDateTime', ''),
                'has_signin_data': has_signin_data,
            })

        return sorted(result, key=lambda x: x['display_name'].lower())

    def enable_user(self, user_id):
        """Enable a user account."""
        if self._is_demo_mode():
            raise Exception("Office 365 credentials not configured.")
        headers = self._get_headers()
        headers['Content-Type'] = 'application/json'
        resp = requests.patch(
            f"https://graph.microsoft.com/v1.0/users/{user_id}",
            headers=headers,
            json={'accountEnabled': True},
        )
        resp.raise_for_status()

    def disable_user(self, user_id):
        """Disable a user account."""
        if self._is_demo_mode():
            raise Exception("Office 365 credentials not configured.")
        headers = self._get_headers()
        headers['Content-Type'] = 'application/json'
        resp = requests.patch(
            f"https://graph.microsoft.com/v1.0/users/{user_id}",
            headers=headers,
            json={'accountEnabled': False},
        )
        resp.raise_for_status()

    def reset_password(self, user_id, new_password, force_change=True):
        """Reset a user's password."""
        if self._is_demo_mode():
            raise Exception("Office 365 credentials not configured.")
        headers = self._get_headers()
        headers['Content-Type'] = 'application/json'
        resp = requests.patch(
            f"https://graph.microsoft.com/v1.0/users/{user_id}",
            headers=headers,
            json={
                'passwordProfile': {
                    'password': new_password,
                    'forceChangePasswordNextSignIn': force_change,
                }
            },
        )
        resp.raise_for_status()

    # ------------------------------------------------------------------
    # Inactive Users Report
    # ------------------------------------------------------------------

    def get_inactive_users(self, days=30):
        """Return users who have not signed in within the last `days` days.
        Returns dict: {'users': [...], 'has_signin_data': bool}"""
        if self._is_demo_mode():
            return {'users': [], 'has_signin_data': False}

        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Fetch directly so we get has_signin_data reliably
        raw_users, has_signin_data = self._fetch_users_with_signin()

        if not has_signin_data:
            # Distinguish premium-required from plain permission missing
            premium_required = False
            try:
                test = requests.get(
                    f"https://graph.microsoft.com/v1.0/users?$select=id,signInActivity&$top=1",
                    headers=self._get_headers()
                )
                if test.status_code == 403:
                    err = test.json().get('error', {}).get('code', '')
                    premium_required = 'NonPremium' in err or 'B2C' in err
            except Exception:
                pass
            return {'users': [], 'has_signin_data': False, 'premium_required': premium_required}

        sku_map = {s['sku_id']: s['display_name'] for s in self.get_license_summary()}

        inactive = []
        for u in raw_users:
            if u.get('userType') != 'Member':
                continue
            if not u.get('accountEnabled', True):
                continue  # already disabled

            sign_in = u.get('signInActivity') or {}
            last = sign_in.get('lastSignInDateTime', '')

            if last:
                try:
                    last_dt = datetime.fromisoformat(last.replace('Z', '+00:00'))
                    if last_dt >= cutoff:
                        continue  # signed in recently
                except Exception:
                    pass

            assigned = u.get('assignedLicenses', [])
            license_names = [sku_map.get(lic.get('skuId', ''), 'Unknown') for lic in assigned]

            days_inactive = days
            if last:
                try:
                    days_inactive = (
                        datetime.now(timezone.utc) -
                        datetime.fromisoformat(last.replace('Z', '+00:00'))
                    ).days
                except Exception:
                    pass

            inactive.append({
                'id': u.get('id', ''),
                'display_name': u.get('displayName', ''),
                'upn': u.get('userPrincipalName', ''),
                'account_enabled': u.get('accountEnabled', True),
                'user_type': u.get('userType', 'Member'),
                'job_title': u.get('jobTitle', ''),
                'department': u.get('department', ''),
                'license_count': len(assigned),
                'licenses': ', '.join(license_names) if license_names else 'No License',
                'last_sign_in': last,
                'days_inactive': days_inactive,
            })

        return {
            'users': sorted(inactive, key=lambda x: x['days_inactive'], reverse=True),
            'has_signin_data': True,
        }

    # ------------------------------------------------------------------
    # MFA / Security Status
    # ------------------------------------------------------------------

    def get_mfa_status(self):
        """Get per-user MFA registration status via credentialUserRegistrationDetails.
        Requires Reports.Read.All. Returns {'data': [...], 'permission_error': bool}."""
        if self._is_demo_mode():
            return {'data': [], 'permission_error': False}

        headers = self._get_headers()

        # Try v1.0 replacement endpoint first (requires UserAuthenticationMethod.Read.All)
        # Fall back to beta if 400/404, which covers tenants on older API surface
        endpoints = [
            ("https://graph.microsoft.com/v1.0/reports/authenticationMethods/userRegistrationDetails", 'v1'),
            ("https://graph.microsoft.com/beta/reports/authenticationMethods/userRegistrationDetails", 'beta'),
        ]

        results = []
        api_version = None
        for url, ver in endpoints:
            resp = requests.get(url, headers=headers)
            if resp.status_code == 403:
                err_code = ''
                try:
                    err_code = resp.json().get('error', {}).get('code', '')
                except Exception:
                    pass
                premium_required = 'NonPremium' in err_code or 'B2C' in err_code
                return {'data': [], 'permission_error': True, 'premium_required': premium_required}
            if resp.status_code in (400, 404):
                continue  # try next endpoint
            resp.raise_for_status()
            api_version = ver
            data = resp.json()
            results = data.get('value', [])
            # paginate if needed
            next_url = data.get('@odata.nextLink')
            while next_url:
                r2 = requests.get(next_url, headers=headers)
                r2.raise_for_status()
                d2 = r2.json()
                results.extend(d2.get('value', []))
                next_url = d2.get('@odata.nextLink')
            break

        if api_version is None:
            return {'data': [], 'permission_error': True, 'premium_required': False}

        # v1 and beta use slightly different field names
        def parse(r):
            # v1: isMfaRegistered / methodsRegistered
            # beta: isMfaRegistered / authMethods
            methods = r.get('methodsRegistered') or r.get('authMethods') or []
            return {
                'upn': r.get('userPrincipalName', ''),
                'display_name': r.get('userDisplayName', '') or r.get('displayName', ''),
                'is_registered': r.get('isMfaRegistered', False),
                'is_enabled': r.get('isMfaEnabled', False) or r.get('isMfaRegistered', False),
                'is_capable': r.get('isMfaCapable', False) or r.get('isMfaRegistered', False),
                'methods': methods,
            }

        return {
            'data': [parse(r) for r in results],
            'permission_error': False,
        }

    # ------------------------------------------------------------------
    # Guest Users
    # ------------------------------------------------------------------

    def get_guest_users(self):
        """Return all external / guest accounts in the tenant."""
        if self._is_demo_mode():
            return []

        headers = self._get_headers()
        url = (
            "https://graph.microsoft.com/v1.0/users"
            "?$filter=userType eq 'Guest'"
            "&$select=id,displayName,userPrincipalName,accountEnabled,"
            "createdDateTime,signInActivity,mail,externalUserState"
            "&$top=999"
        )
        guests = []
        while url:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            guests.extend(data.get('value', []))
            url = data.get('@odata.nextLink')

        return [{
            'id': g.get('id', ''),
            'display_name': g.get('displayName', ''),
            'upn': g.get('userPrincipalName', ''),
            'mail': g.get('mail', ''),
            'account_enabled': g.get('accountEnabled', True),
            'external_state': g.get('externalUserState', ''),
            'created': g.get('createdDateTime', ''),
            'last_sign_in': (g.get('signInActivity') or {}).get('lastSignInDateTime', ''),
        } for g in sorted(guests, key=lambda x: x.get('displayName', '').lower())]

    # ------------------------------------------------------------------
    # OneDrive Storage
    # ------------------------------------------------------------------

    def get_onedrive_usage(self, period='D30'):
        """Get per-user OneDrive storage usage."""
        if self._is_demo_mode():
            return {'users': [], 'total_used_gb': 0, 'high_usage': []}

        headers = self._get_headers()
        report_url = (
            f"https://graph.microsoft.com/v1.0/reports/"
            f"getOneDriveUsageAccountDetail(period='{period}')?$format=text/csv"
        )
        resp = requests.get(report_url, headers=headers)
        resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        users = []
        for row in reader:
            used_str = row.get("Storage Used (Byte)", "").strip()
            quota_str = row.get("Storage Allocated (Byte)", "").strip()
            if not used_str:
                continue
            used = int(used_str.replace(",", ""))
            quota = int(quota_str.replace(",", "")) if quota_str else 0
            used_gb = used / (1024 ** 3)
            quota_gb = quota / (1024 ** 3) if quota else 0
            pct = round((used / quota * 100), 1) if quota > 0 else 0
            users.append({
                'upn': row.get("Owner Principal Name", ""),
                'display_name': row.get("Owner Display Name", ""),
                'used_gb': round(used_gb, 2),
                'quota_gb': round(quota_gb, 2),
                'used_percent': pct,
                'file_count': int(row.get("File Count", 0) or 0),
                'last_activity': row.get("Last Activity Date", ""),
            })

        users.sort(key=lambda x: x['used_gb'], reverse=True)
        total_used = round(sum(u['used_gb'] for u in users), 2)
        high_usage = [u for u in users if u['used_percent'] >= 80]
        return {'users': users, 'total_used_gb': total_used, 'high_usage': high_usage}

    def get_dashboard_summary(self):
        """Get comprehensive dashboard summary"""
        try:
            # Get all data
            licenses = self.get_license_summary()
            mailboxes = self.get_mailbox_usage()
            users = self.get_user_activity()
            teams = self.get_teams_usage()
            email = self.get_email_activity()
            
            # Calculate summary statistics
            total_licenses = sum(lic['total'] for lic in licenses)
            consumed_licenses = sum(lic['consumed'] for lic in licenses)
            
            # Active users in last 30 days
            active_users = len([u for u in users if u['last_activity']])
            
            # Teams usage summary
            teams_active = len([t for t in teams if t['team_chat_messages'] > 0 or t['meetings'] > 0])
            
            # Email activity summary  
            email_active = len([e for e in email if e['send_count'] > 0])
            
            return {
                'licenses': {
                    'total': total_licenses,
                    'consumed': consumed_licenses,
                    'available': total_licenses - consumed_licenses,
                    'usage_percent': (consumed_licenses / total_licenses * 100) if total_licenses > 0 else 0
                },
                'mailboxes': {
                    'total': mailboxes.get('total_mailboxes', 0),
                    'high_usage': len(mailboxes.get('high_usage', [])),
                    'normal_usage': mailboxes.get('total_mailboxes', 0) - len(mailboxes.get('high_usage', []))
                },
                'users': {
                    'total': len(users),
                    'active': active_users,
                    'inactive': len(users) - active_users
                },
                'teams': {
                    'total_users': len(teams),
                    'active_users': teams_active,
                    'total_messages': sum(t['team_chat_messages'] + t['private_chat_messages'] for t in teams),
                    'total_meetings': sum(t['meetings'] for t in teams)
                },
                'email': {
                    'active_users': email_active,
                    'total_sent': sum(e['send_count'] for e in email),
                    'total_received': sum(e['receive_count'] for e in email)
                }
            }
        except Exception as e:
            return {
                'error': str(e),
                'licenses': {'total': 0, 'consumed': 0, 'available': 0, 'usage_percent': 0},
                'mailboxes': {'total': 0, 'high_usage': 0, 'normal_usage': 0},
                'users': {'total': 0, 'active': 0, 'inactive': 0},
                'teams': {'total_users': 0, 'active_users': 0, 'total_messages': 0, 'total_meetings': 0},
                'email': {'active_users': 0, 'total_sent': 0, 'total_received': 0}
            }
