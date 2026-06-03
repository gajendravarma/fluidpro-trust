
from tickets.services import ManageEngineService
import json
import requests
from django.core.cache import cache
from datetime import datetime, timedelta

class RealTimeTicketService:
    """Service to get real-time ticket counts from ManageEngine API"""
    
    def __init__(self):
        self.service = ManageEngineService()
        self.cache_timeout = 300  # 5 minutes cache
    
    def get_status_count(self, status):
        """Get count for a specific status"""
        cache_key = f"ticket_count_{status}"
        count = cache.get(cache_key)
        
        if count is None:
            try:
                url = f"{self.service.base_url}/requests"
                input_data = {
                    'list_info': {
                        'row_count': 1,
                        'start_index': 1,
                        'get_total_count': True,
                        'search_criteria': {
                            'field': 'status.name',
                            'condition': 'is',
                            'value': status
                        }
                    }
                }
                
                response = requests.get(url, headers=self.service.headers, 
                                      params={'input_data': json.dumps(input_data)})
                
                if response.status_code == 200:
                    data = response.json()
                    count = data.get('list_info', {}).get('total_count', 0)
                    cache.set(cache_key, count, self.cache_timeout)
                else:
                    count = 0
                    
            except Exception as e:
                print(f"Error getting count for {status}: {e}")
                count = 0
        
        return count
    
    def get_dashboard_counts(self):
        """Get all dashboard counts with proper status mapping"""
        
        # Get individual status counts
        open_count = self.get_status_count('Open')
        pending_count = self.get_status_count('Pending')
        in_progress_count = self.get_status_count('In Progress')
        
        # Get all hold variations
        hold_statuses = [
            'Onhold',
            'On Hold - For Spare',
            'On Hold – User Dependency', 
            'On Hold - Digtinctive Backend',
            'On Hold - For Commercial Approval'
        ]
        
        hold_count = sum(self.get_status_count(status) for status in hold_statuses)
        
        # Get other statuses
        resolved_count = self.get_status_count('Resolved')
        closed_count = self.get_status_count('Closed')
        cancelled_count = self.get_status_count('Cancelled')
        
        # Calculate totals
        total_active = open_count + pending_count + in_progress_count + hold_count
        total_tickets = (total_active + resolved_count + closed_count + cancelled_count)
        
        return {
            'open': open_count,
            'pending': pending_count,
            'in_progress': in_progress_count,
            'hold': hold_count,
            'resolved': resolved_count,
            'closed': closed_count,
            'cancelled': cancelled_count,
            'total_active': total_active,
            'total_tickets': total_tickets,
            'last_updated': datetime.now().isoformat()
        }
    
    def clear_cache(self):
        """Clear all cached counts to force refresh"""
        statuses = ['Open', 'Pending', 'In Progress', 'Onhold', 
                   'On Hold - For Spare', 'On Hold – User Dependency',
                   'On Hold - Digtinctive Backend', 'On Hold - For Commercial Approval',
                   'Resolved', 'Closed', 'Cancelled']
        
        for status in statuses:
            cache.delete(f"ticket_count_{status}")
