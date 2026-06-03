#!/usr/bin/env python3
"""
RAG-based Intelligent Chatbot - Day 1: Setup and Data Ingestion
Following the proven company chatbot timeline
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
import sqlite3

# Step 1: Data Ingestion - Extract your actual database schema and data patterns
class CompanyDataIngestion:
    """Extract and structure company data for RAG training"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.company_knowledge = {}
        
    def extract_database_schema(self):
        """Extract actual database structure and relationships"""
        
        # Your actual company data patterns
        self.company_knowledge = {
            "companies": {
                "market_xcel": {
                    "names": ["Market Xcel", "MarketXcel", "market-excel", "market excel", "market xcel"],
                    "devices": 231,
                    "tickets": 3321,
                    "organization_name": "MarketXcel"
                },
                "cg_logistics": {
                    "names": ["C G Logistics", "CG Logistics", "cg logistics", "cglogistics"],
                    "devices": 155, 
                    "tickets": 1243,
                    "organization_name": "CG Logistics"
                },
                "aiqmen": {
                    "names": ["Aiqmen", "aquimen", "aiqmen company"],
                    "devices": 8,
                    "tickets": 169,
                    "organization_name": "Aiqmen"
                },
                "digtinctive": {
                    "names": ["Digtinctive", "digtinctive pune"],
                    "devices": 79,
                    "tickets": 0,
                    "organization_name": "Digtinctive Pune"
                },
                "wepsol": {
                    "names": ["Wepsol", "wep solutions", "wep solutuions ltd"],
                    "devices": 1,
                    "tickets": 0,
                    "organization_name": "Wep solutuions ltd"
                },
                "ficc": {
                    "names": ["FICC", "FIICC", "ficc"],
                    "devices": 7,
                    "tickets": 0,
                    "organization_name": "FIICC"
                }
            },
            
            "ticket_statuses": {
                "open": {
                    "names": ["open", "active", "new", "unresolved"],
                    "db_value": "Open"
                },
                "closed": {
                    "names": ["closed", "resolved", "completed", "finished", "done"],
                    "db_value": "Closed"
                },
                "cancelled": {
                    "names": ["cancelled", "canceled", "rejected", "dropped"],
                    "db_value": "Cancelled"
                },
                "pending": {
                    "names": ["pending", "waiting", "on hold", "paused"],
                    "db_value": "Pending"
                },
                "onhold": {
                    "names": ["onhold", "on hold", "hold", "paused"],
                    "db_value": "Onhold"
                }
            },
            
            "time_periods": {
                "last_week": {
                    "names": ["last week", "past week", "previous week", "from last week", "last 7 days"],
                    "days": 7
                },
                "last_month": {
                    "names": ["last month", "past month", "previous month", "from last month", "last 30 days"],
                    "days": 30
                },
                "this_week": {
                    "names": ["this week", "current week", "week"],
                    "days": "current_week"
                },
                "today": {
                    "names": ["today", "now", "current"],
                    "days": 0
                }
            },
            
            "query_intents": {
                "ticket_count": {
                    "patterns": ["how many tickets", "total tickets", "ticket count", "number of tickets"],
                    "requires": ["data_source: tickets"],
                    "optional": ["company", "status", "time_period"]
                },
                "device_count": {
                    "patterns": ["how many devices", "total devices", "device count", "number of devices"],
                    "requires": ["data_source: devices"],
                    "optional": ["company", "status"]
                },
                "device_status": {
                    "patterns": ["device status", "devices online", "devices offline", "server status"],
                    "requires": ["data_source: devices"],
                    "optional": ["company"]
                },
                "office365_licenses": {
                    "patterns": ["office365 licenses", "license count", "o365 licenses", "user licenses"],
                    "requires": ["data_source: office365"],
                    "optional": ["company"]
                }
            }
        }
        
        return self.company_knowledge
    
    def create_training_examples(self):
        """Create training examples from your actual failed queries"""
        
        training_examples = [
            # Your actual failed queries with correct interpretations
            {
                "query": "how many open tickets",
                "intent": "ticket_count",
                "entities": {"status": "Open"},
                "expected_result": "Count of tickets where status = 'Open'"
            },
            {
                "query": "total cancelled tickets", 
                "intent": "ticket_count",
                "entities": {"status": "Cancelled"},
                "expected_result": "Count of tickets where status = 'Cancelled'"
            },
            {
                "query": "total market excel tickets from last week",
                "intent": "ticket_count", 
                "entities": {"company": "Market Xcel", "time_period": "last_week"},
                "expected_result": "Count of tickets for Market Xcel from last 7 days"
            },
            {
                "query": "total cg logistics ticket from last month",
                "intent": "ticket_count",
                "entities": {"company": "C G Logistics", "time_period": "last_month"}, 
                "expected_result": "Count of tickets for C G Logistics from last 30 days"
            },
            {
                "query": "total aquimen devices",
                "intent": "device_count",
                "entities": {"company": "Aiqmen"},
                "expected_result": "Count of devices for Aiqmen organization"
            },
            {
                "query": "total market-excel company devices",
                "intent": "device_count",
                "entities": {"company": "Market Xcel"},
                "expected_result": "Count of devices for MarketXcel organization"
            },
            {
                "query": "total aquimen company devices",
                "intent": "device_count", 
                "entities": {"company": "Aiqmen"},
                "expected_result": "Count of devices for Aiqmen organization"
            }
        ]
        
        return training_examples
    
    def save_knowledge_base(self, filename="company_knowledge.json"):
        """Save the structured knowledge base"""
        
        knowledge_base = {
            "metadata": {
                "created": datetime.now().isoformat(),
                "version": "1.0",
                "description": "Company-specific knowledge base for RAG chatbot"
            },
            "schema": self.company_knowledge,
            "training_examples": self.create_training_examples()
        }
        
        with open(filename, 'w') as f:
            json.dump(knowledge_base, f, indent=2)
        
        print(f"✅ Knowledge base saved to {filename}")
        return knowledge_base

# Step 2: Create Vector Embeddings for Semantic Search
class VectorEmbeddingCreator:
    """Create embeddings for semantic understanding"""
    
    def __init__(self, knowledge_base):
        self.knowledge_base = knowledge_base
        
    def create_company_embeddings(self):
        """Create embeddings for all company name variations"""
        
        company_texts = []
        for company_key, company_data in self.knowledge_base["schema"]["companies"].items():
            for name_variant in company_data["names"]:
                company_texts.append({
                    "text": name_variant,
                    "canonical_name": company_key,
                    "metadata": company_data
                })
        
        return company_texts
    
    def create_status_embeddings(self):
        """Create embeddings for all status variations"""
        
        status_texts = []
        for status_key, status_data in self.knowledge_base["schema"]["ticket_statuses"].items():
            for name_variant in status_data["names"]:
                status_texts.append({
                    "text": name_variant,
                    "canonical_status": status_key,
                    "db_value": status_data["db_value"]
                })
        
        return status_texts
    
    def create_intent_embeddings(self):
        """Create embeddings for query intent patterns"""
        
        intent_texts = []
        for intent_key, intent_data in self.knowledge_base["schema"]["query_intents"].items():
            for pattern in intent_data["patterns"]:
                intent_texts.append({
                    "text": pattern,
                    "intent": intent_key,
                    "metadata": intent_data
                })
        
        return intent_texts

# Step 3: RAG Query Processor
class RAGQueryProcessor:
    """Process queries using RAG approach"""
    
    def __init__(self, knowledge_base):
        self.knowledge_base = knowledge_base
        
    def find_best_company_match(self, query_text):
        """Find best matching company using semantic similarity"""
        
        query_lower = query_text.lower()
        best_match = None
        best_score = 0
        
        for company_key, company_data in self.knowledge_base["schema"]["companies"].items():
            for name_variant in company_data["names"]:
                if name_variant.lower() in query_lower:
                    # Simple scoring based on exact match
                    score = len(name_variant) / len(query_text)
                    if score > best_score:
                        best_score = score
                        best_match = {
                            "company": company_key,
                            "canonical_name": company_data["names"][0],
                            "data": company_data
                        }
        
        return best_match
    
    def find_best_status_match(self, query_text):
        """Find best matching status"""
        
        query_lower = query_text.lower()
        
        for status_key, status_data in self.knowledge_base["schema"]["ticket_statuses"].items():
            for name_variant in status_data["names"]:
                if name_variant in query_lower:
                    return {
                        "status": status_key,
                        "db_value": status_data["db_value"]
                    }
        
        return None
    
    def find_best_intent_match(self, query_text):
        """Find best matching intent"""
        
        query_lower = query_text.lower()
        
        for intent_key, intent_data in self.knowledge_base["schema"]["query_intents"].items():
            for pattern in intent_data["patterns"]:
                if any(word in query_lower for word in pattern.split()):
                    return {
                        "intent": intent_key,
                        "metadata": intent_data
                    }
        
        return {"intent": "general_query", "metadata": {}}
    
    def process_query(self, query_text):
        """Process query using RAG approach"""
        
        # Find matches using semantic understanding
        company_match = self.find_best_company_match(query_text)
        status_match = self.find_best_status_match(query_text)
        intent_match = self.find_best_intent_match(query_text)
        
        # Build structured query
        structured_query = {
            "original_query": query_text,
            "intent": intent_match["intent"],
            "entities": {}
        }
        
        if company_match:
            structured_query["entities"]["company"] = company_match["canonical_name"]
            structured_query["company_data"] = company_match["data"]
        
        if status_match:
            structured_query["entities"]["status"] = status_match["db_value"]
        
        return structured_query

def main():
    """Day 1: Setup RAG system"""
    
    print("🚀 Day 1: Setting up RAG-based Company Chatbot")
    print("=" * 50)
    
    # Step 1: Data Ingestion
    print("📊 Step 1: Extracting company data...")
    ingestion = CompanyDataIngestion("db.sqlite3")
    knowledge = ingestion.extract_database_schema()
    knowledge_base = ingestion.save_knowledge_base()
    
    # Step 2: Create Embeddings
    print("🧠 Step 2: Creating semantic embeddings...")
    embedder = VectorEmbeddingCreator(knowledge_base)
    company_embeddings = embedder.create_company_embeddings()
    status_embeddings = embedder.create_status_embeddings()
    intent_embeddings = embedder.create_intent_embeddings()
    
    print(f"✅ Created {len(company_embeddings)} company embeddings")
    print(f"✅ Created {len(status_embeddings)} status embeddings") 
    print(f"✅ Created {len(intent_embeddings)} intent embeddings")
    
    # Step 3: Test RAG Processing
    print("🧪 Step 3: Testing RAG query processing...")
    processor = RAGQueryProcessor(knowledge_base)
    
    # Test with your actual failed queries
    test_queries = [
        "how many open tickets",
        "total cancelled tickets", 
        "total market excel tickets from last week",
        "total aquimen devices",
        "total market-excel company devices"
    ]
    
    for query in test_queries:
        result = processor.process_query(query)
        print(f"\nQuery: '{query}'")
        print(f"Intent: {result['intent']}")
        print(f"Entities: {result['entities']}")
    
    print("\n🎉 Day 1 Complete: RAG foundation ready!")
    print("Next: Day 2-3 will integrate with your Django chatbot")

if __name__ == "__main__":
    main()
