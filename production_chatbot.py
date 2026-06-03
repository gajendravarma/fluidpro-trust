#!/usr/bin/env python3
"""
Production AI Chatbot Implementation for Django
Integrates with your existing data sources
"""

import os
import sys
import django
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json
import re

# Setup Django
sys.path.append('/home/devops-machine/Fluidtrust-project/customer_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from tickets.models import TicketCache
from pulseway.models import PulsewayDevice
from django.db.models import Count, Q
from django.contrib.auth.models import User

class ProductionChatBot:
    """Production chatbot with real Django integration"""
    
    def __init__(self):
        self.intent_patterns = {
            'ticket_count': [
                r'how many.*tickets',
                r'ticket count',
                r'number of tickets',
                r'total tickets'
            ],
            'ticket_status': [
                r'(open|closed|pending|cancelled|onhold).*tickets',
                r'tickets.*status',
                r'show.*tickets.*status'
            ],
            'company_tickets': [
                r'tickets.*for.*(market xcel|c g logistics|digtinctive|soc|aiqmen|wepsol)',
                r'(market xcel|c g logistics|digtinctive|soc|aiqmen|wepsol).*tickets'
            ],
            'technician_tickets': [
                r'tickets.*assigned.*to',
                r'(azim|avdesh|yogesh|tamil|khaja).*tickets'
            ],
            'device_status': [
                r'device.*status',
                r'how many.*devices',
                r'(offline|online).*devices',
                r'devices.*(offline|online)'
            ],
            'top_companies': [
                r'top.*companies',
                r'which company.*most tickets',
                r'company.*ranking'
            ],
            'recent_tickets': [
                r'recent.*tickets',
                r'latest.*tickets',
                r'tickets.*(today|yesterday|this week)'
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
        
        # Company extraction
        companies = ['market xcel', 'c g logistics', 'digtinctive', 'soc', 'aiqmen', 'wepsol']
        for company in companies:
            if company in query_lower:
                entities['company'] = company.title()
                break
        
        # Status extraction
        statuses = ['open', 'closed', 'pending', 'cancelled', 'onhold', 'resolved']
        for status in statuses:
            if status in query_lower:
                entities['status'] = status.title()
                break
        
        # Technician extraction
        technicians = ['azim', 'avdesh', 'yogesh', 'tamil', 'khaja']
        for tech in technicians:
            if tech in query_lower:
                entities['technician'] = tech
                break
        
        # Time period extraction
        if 'today' in query_lower:
            entities['date_filter'] = datetime.now().date()
        elif 'yesterday' in query_lower:
            entities['date_filter'] = datetime.now().date() - timedelta(days=1)
        elif 'this week' in query_lower:
            entities['date_range'] = 'week'
        elif 'this month' in query_lower:
            entities['date_range'] = 'month'
        
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
                if filters['date_range'] == 'week':
                    week_ago = datetime.now() - timedelta(days=7)
                    queryset = queryset.filter(created_at__gte=week_ago)
                elif filters['date_range'] == 'month':
                    month_ago = datetime.now() - timedelta(days=30)
                    queryset = queryset.filter(created_at__gte=month_ago)
        
        return {
            'count': queryset.count(),
            'tickets': list(queryset.values('ticket_id', 'subject', 'status', 'company_name', 'technician_name', 'created_at')[:10])
        }
    
    def query_devices(self, filters: Dict = None) -> Dict[str, Any]:
        """Query devices from database"""
        queryset = PulsewayDevice.objects.all()
        
        if filters:
            if 'status' in filters:
                if filters['status'].lower() == 'offline':
                    queryset = queryset.filter(status__iexact='offline')
                elif filters['status'].lower() == 'online':
                    queryset = queryset.filter(status__iexact='online')
        
        return {
            'count': queryset.count(),
            'devices': list(queryset.values('device_name', 'status', 'organization_name', 'last_seen')[:10])
        }
    
    def get_top_companies(self) -> List[Dict]:
        """Get companies with most tickets"""
        return list(
            TicketCache.objects.values('company_name')
            .annotate(ticket_count=Count('id'))
            .order_by('-ticket_count')[:5]
        )
    
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
                    
                    filters = ", ".join(filter_desc)
                    return f"Found {count} tickets matching your criteria ({filters})."
                else:
                    return f"Total tickets in the system: {count}"
            
            elif intent == 'ticket_status':
                result = self.query_tickets(entities)
                count = result['count']
                status = entities.get('status', 'all')
                
                if 'company' in entities:
                    return f"Found {count} {status.lower()} tickets for {entities['company']}."
                else:
                    return f"There are {count} {status.lower()} tickets currently."
            
            elif intent == 'company_tickets':
                company = entities.get('company')
                if company:
                    result = self.query_tickets({'company': company})
                    count = result['count']
                    return f"{company} has {count} tickets in the system."
                else:
                    return "Please specify which company you'd like to check."
            
            elif intent == 'technician_tickets':
                technician = entities.get('technician')
                if technician:
                    result = self.query_tickets({'technician': technician})
                    count = result['count']
                    return f"Found {count} tickets assigned to {technician.title()}."
                else:
                    return "Please specify which technician you'd like to check."
            
            elif intent == 'device_status':
                if 'offline' in query.lower():
                    result = self.query_devices({'status': 'offline'})
                    count = result['count']
                    return f"There are {count} offline devices currently. Would you like to see the details?"
                elif 'online' in query.lower():
                    result = self.query_devices({'status': 'online'})
                    count = result['count']
                    return f"There are {count} online devices currently."
                else:
                    online_result = self.query_devices({'status': 'online'})
                    offline_result = self.query_devices({'status': 'offline'})
                    return f"Device status: {online_result['count']} online, {offline_result['count']} offline"
            
            elif intent == 'top_companies':
                companies = self.get_top_companies()
                response = "Top companies by ticket count:\\n"
                for i, company in enumerate(companies, 1):
                    name = company['company_name'] or 'Unknown'
                    count = company['ticket_count']
                    response += f"{i}. {name}: {count} tickets\\n"
                return response
            
            elif intent == 'recent_tickets':
                result = self.query_tickets(entities)
                count = result['count']
                tickets = result['tickets']
                
                response = f"Found {count} recent tickets:\\n"
                for ticket in tickets[:5]:
                    response += f"• {ticket['ticket_id']}: {ticket['subject'][:50]}... ({ticket['status']})\\n"
                
                if count > 5:
                    response += f"... and {count - 5} more tickets."
                
                return response
            
            else:
                return "I can help you with tickets, devices, companies, and technicians. Try asking 'How many open tickets?' or 'Which devices are offline?'"
        
        except Exception as e:
            return f"Sorry, I encountered an error while processing your request: {str(e)}"
    
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

def test_production_chatbot():
    """Test the production chatbot with real data"""
    
    bot = ProductionChatBot()
    
    test_queries = [
        "How many tickets do we have?",
        "Show me open tickets",
        "How many tickets for Market Xcel?",
        "Show me tickets assigned to Azim",
        "How many devices are offline?",
        "Which companies have the most tickets?",
        "Show me recent tickets from this week",
        "How many closed tickets?",
        "What's the device status?"
    ]
    
    print("=== PRODUCTION AI CHATBOT TEST ===")
    print("Testing with real database data\\n")
    
    for query in test_queries:
        print(f"User: {query}")
        result = bot.chat(query)
        print(f"Bot: {result['response']}")
        print(f"Intent: {result['intent']}, Entities: {result['entities']}\\n")

if __name__ == "__main__":
    test_production_chatbot()
