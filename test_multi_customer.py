#!/usr/bin/env python3
"""
Test script for Office 365 multi-customer functionality
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from office365.services import Office365API
from office365.customer_config import get_all_customers, get_customer_config

def test_customer_configurations():
    """Test all customer configurations"""
    print("=== Office 365 Multi-Customer Configuration Test ===\n")
    
    customers = get_all_customers()
    print(f"Found {len(customers)} customers:")
    
    for customer_key, customer_name in customers:
        print(f"\n--- Testing {customer_name} ({customer_key}) ---")
        
        try:
            # Test configuration loading
            config = get_customer_config(customer_key)
            print(f"✓ Configuration loaded")
            print(f"  Tenant ID: {config['tenant_id']}")
            print(f"  Client ID: {config['client_id']}")
            print(f"  Client Secret: {'*' * (len(config['client_secret']) - 4) + config['client_secret'][-4:]}")
            
            # Test API initialization
            api = Office365API(customer_key=customer_key)
            print(f"✓ API initialized successfully")
            
            # Test token acquisition (this will fail without proper permissions, but we can test the request)
            try:
                token = api.get_access_token()
                print(f"✓ Access token acquired successfully")
            except Exception as e:
                print(f"⚠ Token acquisition failed (expected): {str(e)[:100]}...")
                
        except Exception as e:
            print(f"✗ Configuration error: {e}")
    
    print(f"\n=== Test Complete ===")

if __name__ == "__main__":
    test_customer_configurations()
