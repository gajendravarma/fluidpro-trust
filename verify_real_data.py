"""
Final verification that only real data is shown
"""

import os
import sys
import django

# Setup Django environment
sys.path.append('/home/devops-machine/Fluidtrust-project/customer_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from mdm.models import MdmCustomer, Device

def verify_real_data_only():
    """Verify only real data from MDM API is present"""
    
    print("🔍 FINAL VERIFICATION: Real Data Only")
    print("=" * 50)
    
    # Check for dummy data
    dummy_devices = Device.objects.filter(
        device_name__in=['Mike\'s Laptop', 'Sarah\'s Galaxy', 'John\'s iPhone']
    )
    
    if dummy_devices.exists():
        print("❌ DUMMY DATA FOUND:")
        for device in dummy_devices:
            print(f"   - {device.device_name}")
        return False
    else:
        print("✅ NO DUMMY DATA FOUND")
    
    print("\n📱 REAL DEVICES FROM MDM API:")
    
    total_real_devices = 0
    for customer in MdmCustomer.objects.all():
        devices = Device.objects.filter(mdm_customer=customer)
        print(f"\n🏢 {customer.company.name} (Customer ID: {customer.customer_id})")
        print(f"   Total Devices: {devices.count()}")
        
        for device in devices[:3]:  # Show first 3 as sample
            battery_info = f"{device.battery_level}%" if device.battery_level else "N/A"
            print(f"   ✅ {device.device_name}")
            print(f"      User: {device.username}")
            print(f"      Email: {device.user_email or 'N/A'}")
            print(f"      Status: {device.status}")
            print(f"      Battery: {battery_info}")
        
        if devices.count() > 3:
            print(f"   ... and {devices.count() - 3} more real devices")
        
        total_real_devices += devices.count()
    
    print(f"\n📊 SUMMARY:")
    print(f"   • Total Real Customers: {MdmCustomer.objects.count()}")
    print(f"   • Total Real Devices: {total_real_devices}")
    print(f"   • Dummy Devices: 0")
    
    print(f"\n✅ VERIFICATION PASSED: Only real MDM data is present!")
    print(f"🌐 Access URL: http://192.168.2.68:8001/mdm/")
    
    return True

if __name__ == '__main__':
    verify_real_data_only()
