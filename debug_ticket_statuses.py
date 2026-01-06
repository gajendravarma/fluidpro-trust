#!/usr/bin/env python3

import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/root/customer_portal')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from tickets.services import ManageEngineService

def debug_ticket_statuses():
    print("🔧 Debugging ManageEngine Ticket Statuses...")
    
    try:
        service = ManageEngineService()
        
        # Get raw ticket data to see actual status values
        url = f"{service.base_url}/requests"
        input_data = {
            "list_info": {
                "row_count": 20,  # Get fewer tickets for debugging
                "start_index": 1,
                "fields_required": ["id", "subject", "status", "priority"]
            }
        }
        
        import requests
        import json
        response = requests.get(url, headers=service.headers, params={'input_data': json.dumps(input_data)})
        
        if response.status_code == 200:
            data = response.json()
            tickets = data.get('requests', [])
            
            print(f"📊 Found {len(tickets)} tickets")
            print("\n🎫 Status Analysis:")
            
            status_counts = {}
            
            for i, ticket in enumerate(tickets[:10], 1):
                status = ticket.get('status', {})
                priority = ticket.get('priority', {})
                
                if isinstance(status, dict):
                    status_name = status.get('name', 'Unknown')
                    status_id = status.get('id', 'N/A')
                else:
                    status_name = str(status)
                    status_id = 'N/A'
                
                if isinstance(priority, dict):
                    priority_name = priority.get('name', 'Unknown')
                else:
                    priority_name = str(priority)
                
                print(f"   {i}. ID: {ticket.get('id')} | Status: '{status_name}' (ID: {status_id}) | Priority: '{priority_name}'")
                
                # Count statuses
                status_counts[status_name] = status_counts.get(status_name, 0) + 1
            
            print(f"\n📈 Status Distribution:")
            for status, count in status_counts.items():
                print(f"   '{status}': {count} tickets")
            
            print(f"\n🔍 Categorization Test:")
            pending = resolved = closed = in_progress = other = 0
            
            for ticket in tickets:
                status = ticket.get('status', {})
                if isinstance(status, dict):
                    status_name = status.get('name', '').lower()
                else:
                    status_name = str(status).lower()
                
                if 'open' in status_name or 'pending' in status_name:
                    pending += 1
                elif 'resolved' in status_name:
                    resolved += 1
                elif 'closed' in status_name:
                    closed += 1
                elif 'progress' in status_name:
                    in_progress += 1
                else:
                    other += 1
                    print(f"   Uncategorized status: '{status_name}'")
            
            print(f"\n📊 Current Logic Results:")
            print(f"   Total: {len(tickets)}")
            print(f"   Pending: {pending}")
            print(f"   Resolved: {resolved}")
            print(f"   Closed: {closed}")
            print(f"   In Progress: {in_progress}")
            print(f"   Other/Uncategorized: {other}")
            print(f"   Sum: {pending + resolved + closed + in_progress + other}")
            
        else:
            print(f"❌ API Error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    debug_ticket_statuses()
