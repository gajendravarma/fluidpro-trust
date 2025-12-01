import requests
import csv
import io
from django.conf import settings


class Office365API:
    def __init__(self):
        self.tenant_id = getattr(settings, 'OFFICE365_TENANT_ID', '')
        self.client_id = getattr(settings, 'OFFICE365_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'OFFICE365_CLIENT_SECRET', '')
        self.access_token = None

    def get_access_token(self):
        """Get access token for Microsoft Graph API"""
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

    def get_license_summary(self):
        """Get Office 365 license summary"""
        if not self.access_token:
            self.get_access_token()
            
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.get("https://graph.microsoft.com/v1.0/subscribedSkus", headers=headers)
        response.raise_for_status()
        
        data = response.json()
        license_summary = []
        
        for sku in data.get("value", []):
            sku_name = sku.get("skuPartNumber")
            if sku_name in ["O365_BUSINESS_PREMIUM", "O365_BUSINESS_ESSENTIALS"]:
                total = sku.get("prepaidUnits", {}).get("enabled", 0)
                consumed = sku.get("consumedUnits", 0)
                available = max(total - consumed, 0)
                
                license_summary.append({
                    'sku_name': sku_name,
                    'total': total,
                    'consumed': consumed,
                    'available': available,
                    'usage_percent': (consumed / total * 100) if total > 0 else 0
                })
        
        return license_summary

    def get_mailbox_usage(self, period='D30'):
        """Get mailbox usage report"""
        if not self.access_token:
            self.get_access_token()
            
        headers = {"Authorization": f"Bearer {self.access_token}"}
        report_url = f"https://graph.microsoft.com/v1.0/reports/getMailboxUsageDetail(period='{period}')?$format=text/csv"
        
        response = requests.get(report_url, headers=headers)
        response.raise_for_status()
        
        csv_text = response.text
        reader = csv.DictReader(io.StringIO(csv_text))
        
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
            
            mailbox_info = {
                'upn': upn,
                'display_name': display_name,
                'used_percent': used_percent,
                'used_gb': used_gb,
                'quota_gb': quota_gb
            }
            
            mailbox_data.append(mailbox_info)
            
            if used_percent >= threshold:
                high_usage.append(mailbox_info)
        
        return {
            'all_mailboxes': mailbox_data,
            'high_usage': high_usage,
            'total_mailboxes': len(mailbox_data)
        }

    def get_user_activity(self, period='D30'):
        """Get user activity report"""
        if not self.access_token:
            self.get_access_token()
            
        headers = {"Authorization": f"Bearer {self.access_token}"}
        report_url = f"https://graph.microsoft.com/v1.0/reports/getOffice365ActiveUserDetail(period='{period}')?$format=text/csv"
        
        try:
            response = requests.get(report_url, headers=headers)
            response.raise_for_status()
            
            csv_text = response.text
            reader = csv.DictReader(io.StringIO(csv_text))
            
            active_users = []
            for row in reader:
                active_users.append({
                    'upn': row.get("User Principal Name", ""),
                    'display_name': row.get("Display Name", ""),
                    'last_activity': row.get("Last Activity Date", ""),
                    'exchange_active': row.get("Has Exchange License", "") == "True",
                    'teams_active': row.get("Has Teams License", "") == "True",
                    'sharepoint_active': row.get("Has SharePoint License", "") == "True"
                })
            
            return active_users
        except:
            return []

    def get_teams_usage(self, period='D30'):
        """Get Teams usage statistics"""
        if not self.access_token:
            self.get_access_token()
            
        headers = {"Authorization": f"Bearer {self.access_token}"}
        report_url = f"https://graph.microsoft.com/v1.0/reports/getTeamsUserActivityDetail(period='{period}')?$format=text/csv"
        
        try:
            response = requests.get(report_url, headers=headers)
            response.raise_for_status()
            
            csv_text = response.text
            reader = csv.DictReader(io.StringIO(csv_text))
            
            teams_data = []
            for row in reader:
                teams_data.append({
                    'upn': row.get("User Principal Name", ""),
                    'display_name': row.get("Display Name", ""),
                    'team_chat_messages': int(row.get("Team Chat Message Count", 0) or 0),
                    'private_chat_messages': int(row.get("Private Chat Message Count", 0) or 0),
                    'calls': int(row.get("Call Count", 0) or 0),
                    'meetings': int(row.get("Meeting Count", 0) or 0),
                    'last_activity': row.get("Last Activity Date", "")
                })
            
            return teams_data
        except:
            return []

    def get_email_activity(self, period='D30'):
        """Get email activity statistics"""
        if not self.access_token:
            self.get_access_token()
            
        headers = {"Authorization": f"Bearer {self.access_token}"}
        report_url = f"https://graph.microsoft.com/v1.0/reports/getEmailActivityUserDetail(period='{period}')?$format=text/csv"
        
        try:
            response = requests.get(report_url, headers=headers)
            response.raise_for_status()
            
            csv_text = response.text
            reader = csv.DictReader(io.StringIO(csv_text))
            
            email_data = []
            for row in reader:
                email_data.append({
                    'upn': row.get("User Principal Name", ""),
                    'display_name': row.get("Display Name", ""),
                    'send_count': int(row.get("Send Count", 0) or 0),
                    'receive_count': int(row.get("Receive Count", 0) or 0),
                    'read_count': int(row.get("Read Count", 0) or 0),
                    'last_activity': row.get("Last Activity Date", "")
                })
            
            return email_data
        except:
            return []

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
