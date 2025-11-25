import requests
import json
from django.conf import settings
from .company_matcher import CompanyMatcher

class ManageEngineAPI:
    def __init__(self):
        self.base_url = settings.MANAGE_ENGINE_BASE_URL
        self.auth_token = settings.MANAGE_ENGINE_AUTH_TOKEN
        self.headers = {
            'authtoken': self.auth_token
        }
    
    def get_tickets(self, row_count=1000):
        """Get tickets using the working API format"""
        try:
            url = f"{self.base_url}/requests"
            
            input_data = json.dumps({
                "list_info": {
                    "row_count": row_count,
                    "start_index": 1,
                    "sort_order": "desc",
                    "get_total_count": True
                }
            })
            
            params = {'input_data': input_data}
            response = requests.get(url, headers=self.headers, params=params, verify=False, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                tickets = data.get('requests', [])
                list_info = data.get('list_info', {})
                total_count = list_info.get('total_count', len(tickets))
                
                print(f"Retrieved {len(tickets)} tickets out of {total_count} total")
                return tickets
            else:
                print(f"Error getting tickets: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error getting tickets: {str(e)}")
            return []
    
    def get_company_tickets(self, company_name):
        """Get tickets filtered by company name using fuzzy matching"""
        all_tickets = self.get_tickets(row_count=2000)
        
        # Get all unique company names from tickets for matching
        me_companies = set()
        for ticket in all_tickets:
            account = ticket.get('account', {})
            if isinstance(account, dict):
                account_name = account.get('name', '')
                if account_name:
                    me_companies.add(account_name)
        
        # Find best matching ManageEngine company name
        matched_company = CompanyMatcher.match_company(company_name, list(me_companies))
        
        print(f"Matching '{company_name}' -> '{matched_company}'")
        
        company_tickets = []
        
        for ticket in all_tickets:
            # Check account name with fuzzy matching
            account = ticket.get('account', {})
            account_name = account.get('name', '') if isinstance(account, dict) else str(account)
            
            # Check site name
            site = ticket.get('site', {})
            site_name = site.get('name', '') if isinstance(site, dict) else str(site)
            
            # Check subject and description
            subject = ticket.get('subject', '')
            description = ticket.get('description', '')
            
            # Use fuzzy matching for all fields
            if (CompanyMatcher.similarity(company_name, account_name) > 0.6 or
                CompanyMatcher.similarity(company_name, site_name) > 0.6 or
                CompanyMatcher.similarity(matched_company, account_name) > 0.8 or
                company_name.lower() in subject.lower() or
                company_name.lower() in description.lower()):
                company_tickets.append(ticket)
        
        return company_tickets
    
    def get_ticket_stats(self, company_name=None):
        """Get ticket statistics"""
        if company_name:
            tickets = self.get_company_tickets(company_name)
        else:
            tickets = self.get_tickets(row_count=2000)
        
        stats = {
            'total_tickets': len(tickets),
            'open_tickets': 0,
            'closed_tickets': 0,
            'resolved_tickets': 0,
            'pending_tickets': 0,
            'in_progress_tickets': 0
        }
        
        for ticket in tickets:
            status = ticket.get('status', {})
            status_name = status.get('name', '').lower() if isinstance(status, dict) else str(status).lower()
            
            if 'open' in status_name:
                stats['open_tickets'] += 1
            elif 'closed' in status_name:
                stats['closed_tickets'] += 1
            elif 'resolved' in status_name:
                stats['resolved_tickets'] += 1
            elif 'pending' in status_name:
                stats['pending_tickets'] += 1
            elif 'progress' in status_name or 'assigned' in status_name:
                stats['in_progress_tickets'] += 1
        
        return stats
    
    def get_companies(self):
        """Get list of all companies from tickets"""
        tickets = self.get_tickets(row_count=1000)
        companies = set()
        
        for ticket in tickets:
            account = ticket.get('account', {})
            if isinstance(account, dict):
                account_name = account.get('name', '')
                if account_name:
                    companies.add(account_name)
        
        return sorted(list(companies))
