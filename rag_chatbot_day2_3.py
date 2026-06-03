#!/usr/bin/env python3
"""
RAG-based Intelligent Chatbot - Day 2-3: Django Integration
Integrating RAG system with your existing Django chatbot
"""

import json
import os
import sys
import django
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Setup Django
sys.path.append('/home/devops-machine/Fluidtrust-project/customer_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from tickets.models import TicketCache
from pulseway.models import PulsewayDevice
from office365.models import Office365User
from rbac.models import Company
from django.db.models import Count, Q

class RAGEnhancedChatBot:
    """RAG-enhanced chatbot that solves your misunderstanding issues"""
    
    def __init__(self):
        # Load the knowledge base created in Day 1
        with open('company_knowledge.json', 'r') as f:
            self.knowledge_base = json.load(f)
        
        print("✅ RAG Knowledge Base loaded")
    
    def semantic_entity_extraction(self, query_text):
        """Extract entities using RAG semantic understanding"""
        
        query_lower = query_text.lower()
        entities = {}
        
        # Company extraction using RAG knowledge
        best_company_match = None
        best_company_score = 0
        
        for company_key, company_data in self.knowledge_base["schema"]["companies"].items():
            for name_variant in company_data["names"]:
                if name_variant.lower() in query_lower:
                    # Score based on exact match length and position
                    score = len(name_variant) / len(query_text)
                    if name_variant.lower() == query_lower.strip():
                        score += 0.5  # Bonus for exact match
                    
                    if score > best_company_score:
                        best_company_score = score
                        best_company_match = {
                            "name": company_data["names"][0],  # Canonical name
                            "key": company_key,
                            "org_name": company_data["organization_name"]
                        }
        
        if best_company_match:
            entities["company"] = best_company_match["name"]
            entities["company_key"] = best_company_match["key"]
            entities["org_name"] = best_company_match["org_name"]
        
        # Status extraction using RAG knowledge
        for status_key, status_data in self.knowledge_base["schema"]["ticket_statuses"].items():
            for name_variant in status_data["names"]:
                if name_variant in query_lower:
                    entities["status"] = status_data["db_value"]
                    entities["status_key"] = status_key
                    break
            if "status" in entities:
                break
        
        # Time period extraction
        for time_key, time_data in self.knowledge_base["schema"]["time_periods"].items():
            for name_variant in time_data["names"]:
                if name_variant in query_lower:
                    entities["time_period"] = time_key
                    entities["time_days"] = time_data["days"]
                    break
            if "time_period" in entities:
                break
        
        return entities
    
    def semantic_intent_classification(self, query_text):
        """Classify intent using RAG knowledge"""
        
        query_lower = query_text.lower()
        
        # Intent scoring based on patterns
        intent_scores = {}
        
        for intent_key, intent_data in self.knowledge_base["schema"]["query_intents"].items():
            score = 0
            for pattern in intent_data["patterns"]:
                pattern_words = pattern.split()
                matches = sum(1 for word in pattern_words if word in query_lower)
                score += matches / len(pattern_words)
            
            intent_scores[intent_key] = score
        
        # Get best intent
        best_intent = max(intent_scores, key=intent_scores.get)
        
        # Additional logic for device vs ticket disambiguation
        if "device" in query_lower or "computer" in query_lower or "server" in query_lower:
            if "status" in query_lower or "online" in query_lower or "offline" in query_lower:
                return "device_status"
            else:
                return "device_count"
        
        return best_intent if intent_scores[best_intent] > 0 else "general_query"
    
    def build_database_query(self, intent, entities):
        """Build database query based on RAG understanding"""
        
        if intent in ["ticket_count", "company_tickets"]:
            return self.build_ticket_query(entities)
        elif intent in ["device_count", "device_status"]:
            return self.build_device_query(entities, intent)
        elif intent == "office365_licenses":
            return self.build_office365_query(entities)
        else:
            return {"error": "Unknown intent"}
    
    def build_ticket_query(self, entities):
        """Build ticket query with proper filters"""
        
        queryset = TicketCache.objects.all()
        filters_applied = []
        
        # Company filter
        if "company" in entities:
            company_name = entities["company"]
            if "market xcel" in company_name.lower():
                queryset = queryset.filter(company_name__icontains="Market Xcel")
            elif "c g logistics" in company_name.lower():
                queryset = queryset.filter(company_name__icontains="C G Logistics")
            else:
                queryset = queryset.filter(company_name__icontains=company_name)
            filters_applied.append(f"company: {company_name}")
        
        # Status filter
        if "status" in entities:
            status = entities["status"]
            queryset = queryset.filter(status__iexact=status)
            filters_applied.append(f"status: {status}")
        
        # Time filter
        if "time_period" in entities:
            time_period = entities["time_period"]
            if time_period == "last_week":
                week_ago = datetime.now() - timedelta(days=7)
                queryset = queryset.filter(created_at__gte=week_ago)
                filters_applied.append("time: last week")
            elif time_period == "last_month":
                month_ago = datetime.now() - timedelta(days=30)
                queryset = queryset.filter(created_at__gte=month_ago)
                filters_applied.append("time: last month")
        
        return {
            "count": queryset.count(),
            "data_type": "tickets",
            "filters": filters_applied,
            "queryset": queryset
        }
    
    def build_device_query(self, entities, intent):
        """Build device query with proper filters"""
        
        queryset = PulsewayDevice.objects.all()
        filters_applied = []
        
        # Company filter using organization name mapping
        if "org_name" in entities:
            org_name = entities["org_name"]
            queryset = queryset.filter(organization_name__icontains=org_name)
            filters_applied.append(f"organization: {org_name}")
        
        if intent == "device_status":
            online_count = queryset.filter(status='online').count()
            offline_count = queryset.filter(status='offline').count()
            return {
                "online": online_count,
                "offline": offline_count,
                "total": queryset.count(),
                "data_type": "device_status",
                "filters": filters_applied
            }
        else:
            return {
                "count": queryset.count(),
                "data_type": "devices", 
                "filters": filters_applied
            }
    
    def build_office365_query(self, entities):
        """Build Office365 query"""
        
        if "company" in entities:
            company_name = entities["company"]
            try:
                companies = Company.objects.filter(name__icontains=company_name)
                if companies.exists():
                    total = Office365User.objects.filter(company__in=companies).count()
                    used = Office365User.objects.filter(company__in=companies, license_assigned=True).count()
                    return {
                        "total": total,
                        "used": used,
                        "available": total - used,
                        "data_type": "office365",
                        "company": company_name
                    }
            except:
                pass
        
        # Total licenses
        total = Office365User.objects.count()
        used = Office365User.objects.filter(license_assigned=True).count()
        return {
            "total": total,
            "used": used,
            "available": total - used,
            "data_type": "office365"
        }
    
    def generate_smart_response(self, query, intent, entities, data):
        """Generate contextually aware response"""
        
        if "error" in data:
            return f"Sorry, I couldn't process that query: {data['error']}"
        
        # Ticket responses
        if data.get("data_type") == "tickets":
            count = data.get("count", 0)
            filters = data.get("filters", [])
            
            if filters:
                filter_text = " with " + ", ".join(filters)
                return f"Found {count} tickets{filter_text}."
            else:
                return f"Found {count} tickets total."
        
        # Device responses
        elif data.get("data_type") == "devices":
            count = data.get("count", 0)
            filters = data.get("filters", [])
            
            if filters:
                filter_text = " for " + ", ".join(filters)
                return f"Found {count} devices{filter_text}."
            else:
                return f"Total devices: {count}"
        
        elif data.get("data_type") == "device_status":
            online = data.get("online", 0)
            offline = data.get("offline", 0)
            filters = data.get("filters", [])
            
            if filters:
                filter_text = " for " + ", ".join(filters)
                return f"Device status{filter_text}: {online} online, {offline} offline"
            else:
                return f"Device status: {online} online, {offline} offline"
        
        # Office365 responses
        elif data.get("data_type") == "office365":
            total = data.get("total", 0)
            used = data.get("used", 0)
            available = data.get("available", 0)
            company = data.get("company")
            
            if company:
                return f"Office365 licenses for {company}: {total} total, {used} used, {available} available"
            else:
                return f"Office365 licenses: {total} total, {used} used, {available} available"
        
        return "I found some data but couldn't format it properly."
    
    def chat(self, query):
        """Main RAG-enhanced chat interface"""
        
        # Step 1: Semantic entity extraction
        entities = self.semantic_entity_extraction(query)
        
        # Step 2: Intent classification
        intent = self.semantic_intent_classification(query)
        
        # Step 3: Build database query
        data = self.build_database_query(intent, entities)
        
        # Step 4: Generate smart response
        response = self.generate_smart_response(query, intent, entities, data)
        
        return {
            "query": query,
            "intent": intent,
            "entities": entities,
            "response": response,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }

def test_rag_chatbot():
    """Test RAG chatbot with your actual failed queries"""
    
    print("🧪 Testing RAG-Enhanced Chatbot")
    print("=" * 50)
    
    bot = RAGEnhancedChatBot()
    
    # Your actual failed queries
    test_queries = [
        "how many open tickets",
        "total cancelled tickets",
        "total market excel tickets from last week", 
        "total cg logistics ticket from last month",
        "total devices",
        "total aquimen devices",
        "total market-excel company devices",
        "total aquimen company devices"
    ]
    
    for query in test_queries:
        print(f"\n🔍 Query: '{query}'")
        result = bot.chat(query)
        print(f"🤖 Response: {result['response']}")
        print(f"📊 Intent: {result['intent']}")
        print(f"🏷️  Entities: {result['entities']}")
        print(f"📈 Data: {result['data'].get('count', result['data'])}")

if __name__ == "__main__":
    test_rag_chatbot()
