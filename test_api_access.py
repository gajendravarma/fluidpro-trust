#!/usr/bin/env python3

import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/root/customer_portal')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

def test_api_access():
    print("🔧 Testing API Access and Authentication...")
    
    try:
        # Create a test client
        client = Client()
        
        # Test without authentication
        print("\n1. Testing without authentication:")
        response = client.get('/api/historical-tickets/')
        print(f"   Status: {response.status_code}")
        if response.status_code == 302:
            print("   ✅ Correctly redirects to login (authentication required)")
        
        # Create or get a test user
        print("\n2. Testing with authentication:")
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={'email': 'test@example.com'}
        )
        if created:
            user.set_password('testpass')
            user.save()
            print("   Created test user")
        
        # Login and test
        login_success = client.login(username='testuser', password='testpass')
        if login_success:
            print("   ✅ Login successful")
            
            # Test API with authentication
            response = client.get('/api/historical-tickets/')
            print(f"   API Status: {response.status_code}")
            
            if response.status_code == 200:
                print("   ✅ API accessible with authentication")
                try:
                    data = response.json()
                    if data.get('success'):
                        print(f"   ✅ Data retrieved: {data['data']['total_tickets']} tickets")
                    else:
                        print(f"   ⚠️  API returned error: {data.get('message')}")
                except:
                    print("   ⚠️  Response is not JSON")
            else:
                print(f"   ❌ API error: {response.status_code}")
        else:
            print("   ❌ Login failed")
        
        print("\n3. Testing dashboard access:")
        response = client.get('/')
        print(f"   Dashboard Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Dashboard accessible")
        
        print("\n🎯 Recommendations:")
        print("   1. Make sure you're logged in when accessing the dashboard")
        print("   2. Use HTTP (not HTTPS) for development server")
        print("   3. Access via: http://localhost:8000/ (not https://)")
        
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")

if __name__ == "__main__":
    test_api_access()
