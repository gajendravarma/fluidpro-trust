#!/usr/bin/env python3

import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/root/customer_portal')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from datto.datto_client import DattoClient

def test_datto_integration():
    print("🔧 Testing Datto API Integration...")
    
    try:
        client = DattoClient()
        print("✅ Datto client initialized successfully")
        
        # Test API endpoints
        print("\n📡 Testing API endpoints:")
        
        try:
            devices = client.get_devices()
            print(f"✅ BCDR Devices: Found {len(devices.get('items', devices))} devices")
        except Exception as e:
            print(f"⚠️  BCDR Devices: {str(e)}")
        
        try:
            agents = client.get_agents()
            print(f"✅ BCDR Agents: Found {len(agents.get('clients', agents))} agents")
        except Exception as e:
            print(f"⚠️  BCDR Agents: {str(e)}")
        
        try:
            assets = client.get_dtc_assets()
            print(f"✅ DTC Assets: Found {len(assets.get('items', assets))} assets")
        except Exception as e:
            print(f"⚠️  DTC Assets: {str(e)}")
        
        try:
            storage = client.get_dtc_storage_pool()
            print(f"✅ Storage Pool: Retrieved storage information")
        except Exception as e:
            print(f"⚠️  Storage Pool: {str(e)}")
        
        print("\n🎉 Datto integration test completed!")
        print("🌐 Access the Datto dashboard at: http://localhost:8000/datto/")
        
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")

if __name__ == "__main__":
    test_datto_integration()
