"""
AI Engine for Production Chatbot
Integrates with Django models and external APIs
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from tickets.models import TicketCache
from pulseway.models import PulsewayDevice, PulsewayOrganization
from office365.models import Office365User
from rbac.models import Company
from django.db.models import Count, Q


class ProductionChatBot:
    """Production chatbot with real Django integration"""
    
    def __init__(self):
        self.intent_patterns = {
            'ticket_count': [
                r'how many.*tickets',
                r'ticket count',
                r'number of tickets',
                r'total tickets',
                r'tickets.*count',
                r'count.*tickets'
            ],
            'ticket_status': [
                r'(open|closed|pending|cancelled|onhold).*tickets',
                r'tickets.*status',
                r'show.*tickets.*status'
            ],
            'company_tickets': [
                r'tickets.*for.*(market.?xcel|c.?g.?logistics|digtinctive|soc|aiqmen|wepsol|ficc)',
                r'(market.?xcel|c.?g.?logistics|digtinctive|soc|aiqmen|wepsol|ficc).*tickets',
                r'tickets.*(market.?xcel|c.?g.?logistics|digtinctive|soc|aiqmen|wepsol|ficc)',
                r'ticket.*count.*for.*(market.?xcel|c.?g.?logistics|digtinctive|soc|aiqmen|wepsol|ficc)'
            ],
            'technician_tickets': [
                r'tickets.*assigned.*to',
                r'(azim|avdesh|yogesh|tamil|khaja\s*babu?|khaja).*tickets',
                r'technician.*(azim|avdesh|yogesh|tamil|khaja\s*babu?|khaja)',
                r'(azim|avdesh|yogesh|tamil|khaja\s*babu?|khaja).*open.*tickets',
                r'(azim|avdesh|yogesh|tamil|khaja\s*babu?|khaja).*closed.*tickets'
            ],
            'device_count': [
                r'how many.*devices',
                r'total.*devices',
                r'device.*count',
                r'devices.*in.*pulseway',
                r'pulseway.*devices',
                r'devices.*for.*(market.?xcel|c.?g.?logistics|digtinctive|soc|aiqmen|wepsol|ficc)',
                r'(market.?xcel|c.?g.?logistics|digtinctive|soc|aiqmen|wepsol|ficc).*devices'
            ],
            'device_status': [
                r'device.*status',
                r'(offline|online).*devices',
                r'devices.*(offline|online)',
                r'devices.*status.*for.*(market.?xcel|c.?g.?logistics|digtinctive|soc|aiqmen|wepsol|ficc)'
            ],
            'office365_licenses': [
                r'licen[sc]es?.*office.*365',
                r'office.*365.*licen[sc]es?',
                r'o365.*licen[sc]es?',
                r'licen[sc]es?.*o365',
                r'total.*licen[sc]es?.*365',
                r'licen[sc]es?.*for.*(wepsol|market.?xcel|c.?g.?logistics|digtinctive|soc|aiqmen|ficc)',
                r'365.*licen[sc]es?.*for',
                r'licen[sc]es?.*cg.*logistic',
                r'total.*licen[sc]es?.*cg'
            ],
            'top_companies': [
                r'top.*companies',
                r'which company.*most tickets',
                r'company.*ranking'
            ],
            'recent_tickets': [
                r'recent.*tickets',
                r'latest.*tickets',
                r'tickets.*(today|yesterday|this week|last week|last month)',
                r'(last week|last month).*tickets',
                r'tickets.*from.*(last week|last month|this week)'
            ]
        }
    
    def classify_intent(self, query: str) -> str:
        """Classify user intent"""
        query_lower = query.lower()
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return intent
        
        return 'general_query'
    
    def extract_entities(self, query: str) -> Dict[str, Any]:
        """Extract entities from query"""
        query_lower = query.lower()
        entities = {}
        
        # Company extraction - more flexible patterns
        company_patterns = {
            'Market Xcel': [r'market.?xcel', r'market-xcel', r'marketxcel', r'market\s+excel'],
            'C G Logistics': [r'c.?g.?logistics', r'cg.?logistics', r'c-g-logistics', r'cg\s+logistic'],
            'Digtinctive': [r'digtinctive'],
            'SOC': [r'\bsoc\b'],
            'Aiqmen': [r'aiqmen'],
            'Wepsol': [r'wepsol'],
            'FICC': [r'ficc']
        }
        
        for company, patterns in company_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    entities['company'] = company
                    break
            if 'company' in entities:
                break
        
        # Status extraction
        statuses = ['open', 'closed', 'pending', 'cancelled', 'onhold', 'resolved']
        for status in statuses:
            if status in query_lower:
                entities['status'] = status.title()
                break
        
        # Technician extraction
        technicians = ['khaja babu', 'azim', 'avdesh', 'yogesh', 'tamil', 'khaja']
        for tech in technicians:
            if tech in query_lower:
                entities['technician'] = tech
                break
        
        # Time period extraction - improved
        if 'today' in query_lower:
            entities['date_filter'] = datetime.now().date()
        elif 'yesterday' in query_lower:
            entities['date_filter'] = datetime.now().date() - timedelta(days=1)
        elif 'last week' in query_lower or 'from last one week' in query_lower:
            entities['date_range'] = 'last_week'
        elif 'this week' in query_lower:
            entities['date_range'] = 'this_week'
        elif 'last month' in query_lower:
            entities['date_range'] = 'last_month'
        elif 'this month' in query_lower:
            entities['date_range'] = 'this_month'
        
        # Specific month extraction
        months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        for month_name, month_num in months.items():
            if month_name in query_lower:
                # Extract year if mentioned, default to current year
                year = datetime.now().year
                if '2026' in query_lower:
                    year = 2026
                elif '2025' in query_lower:
                    year = 2025
                entities['specific_month'] = {'month': month_num, 'year': year}
                break
        
        return entities
    
    def query_tickets(self, filters: Dict = None) -> Dict[str, Any]:
        """Query tickets from database"""
        queryset = TicketCache.objects.all()
        
        if filters:
            if 'status' in filters:
                queryset = queryset.filter(status__iexact=filters['status'])
            
            if 'company' in filters:
                queryset = queryset.filter(company_name__icontains=filters['company'])
            
            if 'technician' in filters:
                queryset = queryset.filter(technician_name__icontains=filters['technician'])
            
            if 'date_filter' in filters:
                queryset = queryset.filter(created_at__date=filters['date_filter'])
            
            if 'date_range' in filters:
                if filters['date_range'] == 'last_week':
                    week_ago = datetime.now() - timedelta(days=7)
                    queryset = queryset.filter(created_at__gte=week_ago)
                elif filters['date_range'] == 'this_week':
                    # Start of current week (Monday)
                    today = datetime.now()
                    start_week = today - timedelta(days=today.weekday())
                    queryset = queryset.filter(created_at__gte=start_week)
                elif filters['date_range'] == 'last_month':
                    month_ago = datetime.now() - timedelta(days=30)
                    queryset = queryset.filter(created_at__gte=month_ago)
                elif filters['date_range'] == 'this_month':
                    # Start of current month
                    today = datetime.now()
                    start_month = today.replace(day=1)
                    queryset = queryset.filter(created_at__gte=start_month)
            
            if 'specific_month' in filters:
                month_data = filters['specific_month']
                from calendar import monthrange
                import datetime as dt
                
                # Get start and end of the specific month
                year = month_data['year']
                month = month_data['month']
                start_date = dt.datetime(year, month, 1)
                
                # Get last day of the month
                last_day = monthrange(year, month)[1]
                end_date = dt.datetime(year, month, last_day, 23, 59, 59)
                
                queryset = queryset.filter(created_at__gte=start_date, created_at__lte=end_date)
        
        return {
            'count': queryset.count(),
            'tickets': list(queryset.values('ticket_id', 'subject', 'status', 'company_name', 'technician_name', 'created_at')[:10])
        }
    
    def query_devices(self, filters: Dict = None) -> Dict[str, Any]:
        """Query devices from database with company filtering"""
        queryset = PulsewayDevice.objects.all()
        
        if filters:
            if 'company' in filters:
                # Map company names to actual organization names in Pulseway database
                company_name = filters['company'].lower()
                if 'market xcel' in company_name or 'marketxcel' in company_name:
                    queryset = queryset.filter(organization_name__icontains='MarketXcel')
                elif 'c g logistics' in company_name or 'cg logistics' in company_name:
                    queryset = queryset.filter(organization_name__icontains='CG Logistics')
                elif 'wepsol' in company_name or 'wep' in company_name:
                    queryset = queryset.filter(organization_name__icontains='Wep solutuions')
                elif 'digtinctive' in company_name:
                    queryset = queryset.filter(organization_name__icontains='Digtinctive')
                elif 'aiqmen' in company_name:
                    queryset = queryset.filter(organization_name__icontains='Aiqmen')
                elif 'ficc' in company_name or 'fiicc' in company_name:
                    queryset = queryset.filter(organization_name__icontains='FIICC')
            
            if 'status' in filters:
                if filters['status'].lower() == 'offline':
                    queryset = queryset.filter(status__iexact='offline')
                elif filters['status'].lower() == 'online':
                    queryset = queryset.filter(status__iexact='online')
        
        return {
            'count': queryset.count(),
            'devices': list(queryset.values('device_name', 'status', 'organization_name', 'last_seen')[:10])
        }
    
    def query_office365_licenses(self, company: str = None) -> Dict[str, Any]:
        """Query Office365 licenses from real database"""
        try:
            if company:
                # Map company names and get real data
                company_name = company.lower()
                company_filters = []
                
                if 'market xcel' in company_name:
                    company_filters = ['Market Xcel', 'MarketXcel']
                elif 'c g logistics' in company_name or 'cg logistics' in company_name:
                    company_filters = ['C G Logistics', 'CG Logistics']
                elif 'wepsol' in company_name:
                    company_filters = ['Wepsol']
                elif 'digtinctive' in company_name:
                    company_filters = ['Digtinctive']
                elif 'soc' in company_name:
                    company_filters = ['SOC']
                elif 'aiqmen' in company_name:
                    company_filters = ['Aiqmen']
                elif 'ficc' in company_name:
                    company_filters = ['FICC']
                
                if company_filters:
                    # Try to get from Company model first
                    companies = Company.objects.filter(name__in=company_filters)
                    if companies.exists():
                        total_users = Office365User.objects.filter(company__in=companies).count()
                        licensed_users = Office365User.objects.filter(company__in=companies, license_assigned=True).count()
                        return {
                            'total': total_users,
                            'used': licensed_users,
                            'available': total_users - licensed_users
                        }
                
                # If no Office365 data found, return zero
                return {'total': 0, 'used': 0, 'available': 0}
            else:
                # Return total across all companies
                total_users = Office365User.objects.count()
                licensed_users = Office365User.objects.filter(license_assigned=True).count()
                return {
                    'total': total_users,
                    'used': licensed_users,
                    'available': total_users - licensed_users
                }
        except Exception as e:
            # If Office365 models don't have data, return informative message
            return {'total': 0, 'used': 0, 'available': 0, 'error': 'No Office365 data available in database'}
    
    def get_top_companies(self) -> List[Dict]:
        """Get companies with most tickets"""
        return list(
            TicketCache.objects.values('company_name')
            .annotate(ticket_count=Count('id'))
            .order_by('-ticket_count')[:5]
        )
        """Generate natural language response"""
        
    def generate_response(self, intent: str, entities: Dict, query: str) -> str:
        """Generate natural language response"""
        
        try:
            if intent == 'ticket_count':
                result = self.query_tickets(entities)
                count = result['count']
                
                if entities:
                    filter_desc = []
                    if 'status' in entities:
                        filter_desc.append(f"status: {entities['status']}")
                    if 'company' in entities:
                        filter_desc.append(f"company: {entities['company']}")
                    if 'technician' in entities:
                        filter_desc.append(f"technician: {entities['technician']}")
                    if 'date_range' in entities:
                        filter_desc.append(f"period: {entities['date_range'].replace('_', ' ')}")
                    
                    filters = ", ".join(filter_desc)
                    return f"Found {count} tickets matching your criteria ({filters})."
                else:
                    return f"Total tickets in the system: {count}"
            
            elif intent == 'company_tickets':
                company = entities.get('company')
                if company:
                    result = self.query_tickets(entities)
                    count = result['count']
                    
                    if 'date_range' in entities:
                        period = entities['date_range'].replace('_', ' ')
                        return f"{company} has {count} tickets from {period}."
                    else:
                        return f"{company} has {count} tickets in the system."
                else:
                    return "Please specify which company you'd like to check."
            
            elif intent == 'ticket_status':
                result = self.query_tickets(entities)
                count = result['count']
                status = entities.get('status', 'all')
                
                if 'company' in entities:
                    return f"Found {count} {status.lower()} tickets for {entities['company']}."
                else:
                    return f"There are {count} {status.lower()} tickets currently."
            
            elif intent == 'technician_tickets':
                technician = entities.get('technician')
                if technician:
                    result = self.query_tickets({'technician': technician})
                    count = result['count']
                    return f"Found {count} tickets assigned to {technician.title()}."
                else:
                    return "Please specify which technician you'd like to check."
            
            elif intent == 'device_count':
                company = entities.get('company')
                if company:
                    result = self.query_devices({'company': company})
                    count = result['count']
                    return f"Total devices for {company}: {count}"
                else:
                    total_result = self.query_devices()
                    count = total_result['count']
                    return f"Total devices in Pulseway: {count}"
            
            elif intent == 'device_status':
                company = entities.get('company')
                filters = {}
                if company:
                    filters['company'] = company
                
                if 'offline' in query.lower():
                    filters['status'] = 'offline'
                    result = self.query_devices(filters)
                    count = result['count']
                    if company:
                        return f"There are {count} offline devices for {company}."
                    else:
                        return f"There are {count} offline devices currently."
                elif 'online' in query.lower():
                    filters['status'] = 'online'
                    result = self.query_devices(filters)
                    count = result['count']
                    if company:
                        return f"There are {count} online devices for {company}."
                    else:
                        return f"There are {count} online devices currently."
                else:
                    online_filters = filters.copy()
                    offline_filters = filters.copy()
                    online_filters['status'] = 'online'
                    offline_filters['status'] = 'offline'
                    
                    online_result = self.query_devices(online_filters)
                    offline_result = self.query_devices(offline_filters)
                    
                    if company:
                        return f"Device status for {company}: {online_result['count']} online, {offline_result['count']} offline"
                    else:
                        return f"Device status: {online_result['count']} online, {offline_result['count']} offline"
            
            elif intent == 'office365_licenses':
                company = entities.get('company')
                license_data = self.query_office365_licenses(company)
                
                if 'error' in license_data:
                    if company:
                        return f"No Office365 license data found for {company.title()} in the database. Please check if Office365 integration is set up."
                    else:
                        return "No Office365 license data found in the database. Please check if Office365 integration is set up."
                
                if company:
                    if license_data['total'] == 0:
                        return f"No Office365 licenses found for {company.title()} in the database."
                    return f"Office365 licenses for {company.title()}: {license_data['total']} total, {license_data['used']} used, {license_data['available']} available."
                else:
                    if license_data['total'] == 0:
                        return "No Office365 license data found in the database."
                    return f"Total Office365 licenses: {license_data['total']} total, {license_data['used']} used, {license_data['available']} available."
            
            elif intent == 'top_companies':
                companies = self.get_top_companies()
                response = "Top companies by ticket count:\n"
                for i, company in enumerate(companies, 1):
                    name = company['company_name'] or 'Unknown'
                    count = company['ticket_count']
                    response += f"{i}. {name}: {count} tickets\n"
                return response
            
            elif intent == 'recent_tickets':
                result = self.query_tickets(entities)
                count = result['count']
                tickets = result['tickets']
                
                period = entities.get('date_range', 'recent').replace('_', ' ')
                response = f"Found {count} tickets from {period}:\n"
                
                for ticket in tickets[:5]:
                    response += f"• {ticket['ticket_id']}: {ticket['subject'][:50]}... ({ticket['status']})\n"
                
                if count > 5:
                    response += f"... and {count - 5} more tickets."
                
                return response
            
            else:
                return "I can help you with:\n• Ticket counts and status\n• Device monitoring\n• Company statistics\n• Office365 licenses\n• Technician workloads\n\nTry asking: 'How many tickets for Market Xcel?' or 'Office365 licenses for Wepsol'"
        
        except Exception as e:
            return f"Sorry, I encountered an error: {str(e)}"
    
    def chat(self, query: str) -> Dict[str, Any]:
        """Main chat interface"""
        intent = self.classify_intent(query)
        entities = self.extract_entities(query)
        response = self.generate_response(intent, entities, query)
        
        return {
            'query': query,
            'intent': intent,
            'entities': entities,
            'response': response,
            'timestamp': datetime.now().isoformat()
        }
