#!/usr/bin/env python3
"""
AI Chatbot Core - Minimal Implementation
Demonstrates how the chatbot would work with your data sources
"""

import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

class IntentClassifier:
    """Simple rule-based intent classifier"""
    
    INTENT_PATTERNS = {
        'ticket_count': [
            r'how many.*tickets',
            r'ticket count',
            r'number of tickets',
            r'total tickets'
        ],
        'ticket_status': [
            r'(open|closed|pending|cancelled).*tickets',
            r'tickets.*status',
            r'show.*tickets'
        ],
        'device_status': [
            r'device.*status',
            r'how many.*devices',
            r'offline.*devices',
            r'online.*devices'
        ],
        'company_tickets': [
            r'tickets.*for.*(company|client)',
            r'(market xcel|fluid|digtinctive).*tickets'
        ],
        'technician_tickets': [
            r'tickets.*assigned.*to',
            r'(azim|avdesh|yogesh).*tickets'
        ],
        'office365_query': [
            r'office365|o365|microsoft',
            r'email.*users',
            r'onedrive.*usage'
        ],
        'backup_status': [
            r'backup.*status',
            r'datto.*backup',
            r'failed.*backups'
        ]
    }
    
    def classify(self, query: str) -> str:
        query_lower = query.lower()
        
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return intent
        
        return 'general_query'

class EntityExtractor:
    """Extract entities from user queries"""
    
    COMPANY_PATTERNS = [
        r'market xcel',
        r'c g logistics', 
        r'digtinctive',
        r'fluidtrust',
        r'soc',
        r'aiqmen',
        r'wepsol'
    ]
    
    STATUS_PATTERNS = [
        r'open',
        r'closed', 
        r'pending',
        r'cancelled',
        r'onhold',
        r'resolved'
    ]
    
    TECHNICIAN_PATTERNS = [
        r'azim',
        r'avdesh',
        r'yogesh',
        r'tamil',
        r'khaja'
    ]
    
    def extract(self, query: str) -> Dict[str, Any]:
        query_lower = query.lower()
        entities = {}
        
        # Extract company
        for company in self.COMPANY_PATTERNS:
            if company in query_lower:
                entities['company'] = company.title()
                break
        
        # Extract status
        for status in self.STATUS_PATTERNS:
            if status in query_lower:
                entities['status'] = status.title()
                break
        
        # Extract technician
        for tech in self.TECHNICIAN_PATTERNS:
            if tech in query_lower:
                entities['technician'] = tech.title()
                break
        
        # Extract time periods
        if 'today' in query_lower:
            entities['date_range'] = 'today'
        elif 'yesterday' in query_lower:
            entities['date_range'] = 'yesterday'
        elif 'this week' in query_lower or 'last week' in query_lower:
            entities['date_range'] = 'week'
        elif 'this month' in query_lower or 'last month' in query_lower:
            entities['date_range'] = 'month'
        
        return entities

class DatabaseConnector:
    """Simulates database queries - would connect to actual Django models"""
    
    def __init__(self):
        # In real implementation, this would use Django ORM
        self.sample_data = {
            'tickets': [
                {'id': 1, 'status': 'Open', 'company': 'Market Xcel', 'technician': 'Azim A'},
                {'id': 2, 'status': 'Closed', 'company': 'C G Logistics', 'technician': 'Avdesh Kumar'},
                {'id': 3, 'status': 'Open', 'company': 'Digtinctive', 'technician': 'Yogesh M'},
            ],
            'devices': [
                {'name': 'Server-01', 'status': 'online', 'company': 'FluidTrust'},
                {'name': 'PC-Marketing', 'status': 'offline', 'company': 'Market Xcel'},
            ]
        }
    
    def get_ticket_count(self, filters: Dict = None) -> int:
        """Get ticket count with optional filters"""
        tickets = self.sample_data['tickets']
        
        if filters:
            if 'status' in filters:
                tickets = [t for t in tickets if t['status'].lower() == filters['status'].lower()]
            if 'company' in filters:
                tickets = [t for t in tickets if filters['company'].lower() in t['company'].lower()]
            if 'technician' in filters:
                tickets = [t for t in tickets if filters['technician'].lower() in t['technician'].lower()]
        
        return len(tickets)
    
    def get_device_status(self, status: str = None) -> List[Dict]:
        """Get device status information"""
        devices = self.sample_data['devices']
        
        if status:
            devices = [d for d in devices if d['status'].lower() == status.lower()]
        
        return devices

class APIConnector:
    """Simulates API calls to external services"""
    
    def get_office365_users(self) -> Dict:
        """Simulate Office365 API call"""
        return {
            'total_users': 145,
            'active_users': 142,
            'admin_users': 5
        }
    
    def get_backup_status(self) -> Dict:
        """Simulate Datto backup API call"""
        return {
            'total_jobs': 25,
            'successful': 23,
            'failed': 2,
            'last_backup': '2026-03-07 02:00:00'
        }

class ResponseGenerator:
    """Generate natural language responses"""
    
    def __init__(self):
        self.db = DatabaseConnector()
        self.api = APIConnector()
    
    def generate_response(self, intent: str, entities: Dict, query: str) -> str:
        """Generate response based on intent and entities"""
        
        if intent == 'ticket_count':
            count = self.db.get_ticket_count(entities)
            if entities:
                filters = ', '.join([f"{k}: {v}" for k, v in entities.items()])
                return f"Found {count} tickets matching your criteria ({filters})."
            return f"Total tickets in the system: {count}"
        
        elif intent == 'ticket_status':
            status = entities.get('status', 'Open')
            count = self.db.get_ticket_count({'status': status})
            return f"There are {count} {status.lower()} tickets currently."
        
        elif intent == 'company_tickets':
            company = entities.get('company')
            if company:
                count = self.db.get_ticket_count({'company': company})
                return f"{company} has {count} tickets in the system."
            return "Please specify which company you'd like to check."
        
        elif intent == 'device_status':
            if 'offline' in query.lower():
                devices = self.db.get_device_status('offline')
                count = len(devices)
                return f"There are {count} offline devices. Would you like to see the details?"
            elif 'online' in query.lower():
                devices = self.db.get_device_status('online')
                count = len(devices)
                return f"There are {count} online devices currently."
            else:
                online = len(self.db.get_device_status('online'))
                offline = len(self.db.get_device_status('offline'))
                return f"Device status: {online} online, {offline} offline"
        
        elif intent == 'office365_query':
            data = self.api.get_office365_users()
            return f"Office365 Status: {data['total_users']} total users, {data['active_users']} active, {data['admin_users']} admins."
        
        elif intent == 'backup_status':
            data = self.api.get_backup_status()
            return f"Backup Status: {data['successful']}/{data['total_jobs']} successful, {data['failed']} failed. Last backup: {data['last_backup']}"
        
        else:
            return "I understand you're asking about the system, but I need more specific information. Try asking about tickets, devices, or Office365 status."

class ChatBot:
    """Main chatbot class"""
    
    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.entity_extractor = EntityExtractor()
        self.response_generator = ResponseGenerator()
        self.conversation_history = []
    
    def process_query(self, query: str) -> str:
        """Process user query and return response"""
        
        # Store query in conversation history
        self.conversation_history.append({
            'timestamp': datetime.now(),
            'query': query,
            'type': 'user'
        })
        
        # Classify intent
        intent = self.intent_classifier.classify(query)
        
        # Extract entities
        entities = self.entity_extractor.extract(query)
        
        # Generate response
        response = self.response_generator.generate_response(intent, entities, query)
        
        # Store response in conversation history
        self.conversation_history.append({
            'timestamp': datetime.now(),
            'response': response,
            'type': 'bot',
            'intent': intent,
            'entities': entities
        })
        
        return response
    
    def get_conversation_history(self) -> List[Dict]:
        """Get conversation history"""
        return self.conversation_history

# Demo function
def demo_chatbot():
    """Demonstrate chatbot functionality"""
    
    bot = ChatBot()
    
    test_queries = [
        "How many tickets do we have?",
        "Show me open tickets for Market Xcel",
        "How many devices are offline?",
        "What's our Office365 user count?",
        "What's the backup status?",
        "Show me tickets assigned to Azim",
        "How many closed tickets this week?"
    ]
    
    print("=== AI CHATBOT DEMO ===")
    print("Demonstrating natural language queries to your data sources\n")
    
    for query in test_queries:
        print(f"User: {query}")
        response = bot.process_query(query)
        print(f"Bot: {response}\n")
    
    print("=== CONVERSATION HISTORY ===")
    for entry in bot.get_conversation_history():
        if entry['type'] == 'user':
            print(f"[{entry['timestamp'].strftime('%H:%M:%S')}] User: {entry['query']}")
        else:
            print(f"[{entry['timestamp'].strftime('%H:%M:%S')}] Bot: {entry['response']}")
            print(f"    Intent: {entry['intent']}, Entities: {entry['entities']}")

if __name__ == "__main__":
    demo_chatbot()
