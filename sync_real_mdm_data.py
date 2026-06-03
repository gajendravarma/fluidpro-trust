"""
Sync ONLY real data from MDM database - no dummy data
"""

import os
import sys
import django
import sqlite3
from datetime import datetime

# Setup Django environment
sys.path.append('/home/devops-machine/Fluidtrust-project/customer_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from mdm.models import MdmCustomer, Device, SecurityEvent
from rbac.models import Company

def sync_real_mdm_data():
    """Sync ONLY real data from MDM database"""
    
    mdm_db_path = '/root/mdm_portal_project/db.sqlite3'
    
    if not os.path.exists(mdm_db_path):
        print(f"MDM database not found at {mdm_db_path}")
        return
    
    conn = sqlite3.connect(mdm_db_path)
    cursor = conn.cursor()
    
    try:
        # Get all real customers (exclude DEFAULT_CUSTOMER)
        cursor.execute("SELECT * FROM dashboard_customer WHERE name != 'DEFAULT_CUSTOMER' AND device_count > 0")
        customers = cursor.fetchall()
        
        cursor.execute("PRAGMA table_info(dashboard_customer)")
        customer_columns = [col[1] for col in cursor.fetchall()]
        
        for customer_row in customers:
            customer_dict = dict(zip(customer_columns, customer_row))
            
            print(f"Processing customer: {customer_dict['name']}")
            
            # Create or get company
            company, created = Company.objects.get_or_create(
                name=customer_dict['name'],
                defaults={'code': customer_dict['customer_id']}
            )
            
            if created:
                print(f"  Created company: {company.name}")
            
            # Create or update MDM customer
            mdm_customer, created = MdmCustomer.objects.update_or_create(
                customer_id=customer_dict['customer_id'],
                defaults={
                    'company': company,
                    'device_count': customer_dict.get('device_count', 0),
                    'no_of_devices': str(customer_dict.get('device_count', 0)),
                    'status': customer_dict.get('status', 'active'),
                }
            )
            
            print(f"  {'Created' if created else 'Updated'} MDM customer: {mdm_customer}")
            
            # Get devices for this customer
            cursor.execute("SELECT * FROM dashboard_device WHERE customer_id = ?", (customer_dict['id'],))
            devices = cursor.fetchall()
            
            cursor.execute("PRAGMA table_info(dashboard_device)")
            device_columns = [col[1] for col in cursor.fetchall()]
            
            device_count = 0
            for device_row in devices:
                device_dict = dict(zip(device_columns, device_row))
                
                # Convert device type based on device name
                device_type = 'android'  # default
                if 'iPhone' in device_dict.get('device_name', ''):
                    device_type = 'ios'
                elif 'laptop' in device_dict.get('device_name', '').lower():
                    device_type = 'laptop'
                elif 'windows' in device_dict.get('device_name', '').lower():
                    device_type = 'windows'
                
                device, created = Device.objects.update_or_create(
                    device_id=device_dict.get('device_id', f"MDM_{device_dict['id']}"),
                    defaults={
                        'mdm_customer': mdm_customer,
                        'device_name': device_dict.get('device_name', 'Unknown Device'),
                        'device_type': device_type,
                        'platform': device_dict.get('platform', ''),
                        'model': device_dict.get('model', ''),
                        'manufacturer': device_dict.get('manufacturer', ''),
                        'os_version': device_dict.get('os_version', ''),
                        'serial_number': device_dict.get('serial_number', ''),
                        'imei': device_dict.get('imei', ''),
                        'phone_number': device_dict.get('phone_number', ''),
                        'status': device_dict.get('status', 'managed'),
                        'username': device_dict.get('username', ''),
                        'user_email': device_dict.get('user_email', ''),
                        'display_name': device_dict.get('display_name', ''),
                        'battery_level': device_dict.get('battery_level'),
                        'storage_total': device_dict.get('storage_total'),
                        'storage_used': device_dict.get('storage_used'),
                        'free_space_gb': device_dict.get('free_space_gb'),
                        'is_supervised': bool(device_dict.get('is_supervised', False)),
                        'is_encrypted': bool(device_dict.get('is_encrypted', False)),
                        'last_contact_time': device_dict.get('last_contact_time'),
                        'last_seen': device_dict.get('last_seen'),
                        'enrollment_time': device_dict.get('enrollment_time'),
                        'apps_count': device_dict.get('apps_count', 0),
                        'associated_groups': device_dict.get('associated_groups', 0),
                        'profile_count': device_dict.get('profile_count', 0),
                    }
                )
                device_count += 1
                
                if created:
                    print(f"    Created device: {device.device_name}")
                else:
                    print(f"    Updated device: {device.device_name}")
            
            # Update device count
            mdm_customer.device_count = device_count
            mdm_customer.save()
            
            print(f"  Total devices synced: {device_count}")
        
        conn.close()
        print("\n✅ Real MDM data sync completed successfully!")
        
        # Print summary
        print("\n📊 Summary:")
        total_customers = MdmCustomer.objects.count()
        total_devices = Device.objects.count()
        print(f"   • {total_customers} real customers")
        print(f"   • {total_devices} real devices")
        
        for customer in MdmCustomer.objects.all():
            device_count = Device.objects.filter(mdm_customer=customer).count()
            print(f"   • {customer.company.name}: {device_count} devices")
        
    except Exception as e:
        print(f"Error syncing real MDM data: {e}")
        conn.close()

if __name__ == '__main__':
    sync_real_mdm_data()
