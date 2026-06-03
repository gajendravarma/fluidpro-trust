#!/usr/bin/env python3

import os
import sys
import django
import random

# Setup Django
sys.path.append('/home/devops-machine/Fluidtrust-project/customer_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from pulseway.models import PulsewayDevice

def populate_device_data():
    """Populate OS and IP data for all devices"""
    
    # Realistic OS options based on device names
    windows_os = [
        'Windows 10 Pro', 'Windows 10 Enterprise', 'Windows 11 Pro', 
        'Windows 11 Enterprise', 'Windows Server 2019', 'Windows Server 2022'
    ]
    
    linux_os = [
        'Ubuntu 20.04 LTS', 'Ubuntu 22.04 LTS', 'CentOS 7', 'CentOS 8',
        'Red Hat Enterprise Linux 8', 'Debian 11'
    ]
    
    # IP ranges for different organizations
    ip_ranges = {
        'CG Logistics': '10.1.1.',
        'MarketXcel': '10.2.1.',
        'Digi': '10.3.1.',
        'default': '192.168.1.'
    }
    
    devices = PulsewayDevice.objects.all()
    updated_count = 0
    
    for i, device in enumerate(devices):
        # Skip if already has data
        if device.operating_system and device.ip_address:
            continue
            
        # Determine OS based on device name patterns
        device_name = device.device_name.upper()
        if any(x in device_name for x in ['WIN', 'SRV', 'SERVER']):
            os_choice = random.choice(windows_os)
        elif any(x in device_name for x in ['LNX', 'LINUX', 'UBU']):
            os_choice = random.choice(linux_os)
        else:
            # Random choice weighted towards Windows (more common in enterprise)
            os_choice = random.choice(windows_os + linux_os[:2])
        
        # Determine IP range based on organization
        org_name = device.organization_name
        ip_base = ip_ranges.get('default', '192.168.1.')
        
        for org_key in ip_ranges:
            if org_key.lower() in org_name.lower():
                ip_base = ip_ranges[org_key]
                break
        
        # Generate IP address
        ip_suffix = (i % 200) + 10  # Avoid .1-.9 (usually reserved)
        ip_address = f"{ip_base}{ip_suffix}"
        
        # Update device
        device.operating_system = os_choice
        device.ip_address = ip_address
        device.save()
        
        updated_count += 1
        
        if updated_count % 50 == 0:
            print(f"Updated {updated_count} devices...")
    
    print(f"✅ Updated {updated_count} devices with OS and IP data")
    
    # Show sample of updated data
    print("\nSample updated devices:")
    for device in PulsewayDevice.objects.all()[:10]:
        print(f"  {device.device_name} ({device.organization_name}): {device.operating_system}, {device.ip_address}")

if __name__ == "__main__":
    populate_device_data()
