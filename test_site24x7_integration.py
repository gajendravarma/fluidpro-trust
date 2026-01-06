#!/usr/bin/env python3

import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/root/customer_portal')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from site24x7.site24x7_client import Site24x7Platform

def test_site24x7_integration():
    print("🔧 Testing Site24x7 API Integration...")
    
    try:
        platform = Site24x7Platform()
        print("✅ Site24x7 client initialized successfully")
        
        # Test API endpoints
        print("\n📡 Testing API endpoints:")
        
        try:
            customers = platform.get_customers()
            if 'error' in customers:
                print(f"⚠️  MSP Customers: {customers['error']}")
            else:
                customer_count = len(customers.get('data', customers))
                print(f"✅ MSP Customers: Found {customer_count} customers")
        except Exception as e:
            print(f"⚠️  MSP Customers: {str(e)}")
        
        try:
            monitors = platform.get_monitors()
            if 'error' in monitors:
                print(f"⚠️  Monitors: {monitors['error']}")
            else:
                monitor_count = len(monitors.get('data', monitors))
                print(f"✅ Monitors: Found {monitor_count} monitors")
        except Exception as e:
            print(f"⚠️  Monitors: {str(e)}")
        
        try:
            status = platform.get_current_status()
            if 'error' in status:
                print(f"⚠️  Current Status: {status['error']}")
            else:
                status_count = len(status.get('data', status))
                print(f"✅ Current Status: Retrieved {status_count} status entries")
        except Exception as e:
            print(f"⚠️  Current Status: {str(e)}")
        
        print("\n🎉 Site24x7 integration test completed!")
        print("🌐 Access the Site24x7 dashboard at: http://localhost:8000/site24x7/")
        
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")

if __name__ == "__main__":
    test_site24x7_integration()
