"""
Sync ALL real data from original MDM portal - accurate numbers
"""

import os
import sys
import django
import sqlite3

# Setup Django environment
sys.path.append('/home/devops-machine/Fluidtrust-project/customer_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from mdm.models import MdmCustomer, Device
from rbac.models import Company

def sync_all_real_data():
    """Sync ALL real data from original MDM portal"""
    
    mdm_db_path = '/root/mdm_portal_project/db.sqlite3'
    conn = sqlite3.connect(mdm_db_path)
    cursor = conn.cursor()
    
    try:
        # Clear existing data first
        print("Clearing existing MDM data...")
        Device.objects.all().delete()
        MdmCustomer.objects.all().delete()
        
        # Get real customers with devices
        cursor.execute("""
            SELECT c.*, COUNT(d.id) as actual_device_count 
            FROM dashboard_customer c 
            LEFT JOIN dashboard_device d ON c.id = d.customer_id 
            WHERE c.name != 'DEFAULT_CUSTOMER' 
            GROUP BY c.id 
            HAVING actual_device_count > 0
        """)
        
        customers = cursor.fetchall()
        cursor.execute("PRAGMA table_info(dashboard_customer)")
        customer_columns = [col[1] for col in cursor.fetchall()]
        customer_columns.append('actual_device_count')  # Add the count column
        
        for customer_row in customers:
            customer_dict = dict(zip(customer_columns, customer_row))
            
            print(f"\\nSyncing: {customer_dict['name']}")
            print(f"  Actual devices in MDM: {customer_dict['actual_device_count']}")
            
            # Create or get company
            company, created = Company.objects.get_or_create(
                name=customer_dict['name'],
                defaults={'code': customer_dict['customer_id']}
            )
            
            # Create MDM customer with REAL device count
            mdm_customer, created = MdmCustomer.objects.update_or_create(
                customer_id=customer_dict['customer_id'],
                defaults={
                    'company': company,
                    'device_count': customer_dict['actual_device_count'],  # Use REAL count
                    'no_of_devices': str(customer_dict['actual_device_count']),
                    'status': customer_dict.get('status', 'active'),
                }
            )
            
            # Get ALL devices for this customer
            cursor.execute("SELECT * FROM dashboard_device WHERE customer_id = ?", (customer_dict['id'],))
            devices = cursor.fetchall()
            
            cursor.execute("PRAGMA table_info(dashboard_device)")
            device_columns = [col[1] for col in cursor.fetchall()]
            
            synced_count = 0
            for device_row in devices:
                device_dict = dict(zip(device_columns, device_row))
                
                # Determine device type from name
                device_type = 'android'  # default
                device_name = device_dict.get('device_name', '').lower()
                if 'iphone' in device_name:
                    device_type = 'ios'
                elif 'laptop' in device_name or 'dell' in device_name or 'hp' in device_name:
                    device_type = 'laptop'
                elif 'windows' in device_name:
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
                synced_count += 1
            
            print(f"  Synced: {synced_count} devices")
            
            # Update with actual synced count
            mdm_customer.device_count = synced_count
            mdm_customer.save()
        
        conn.close()
        
        # Print final summary
        print(f"\\n✅ REAL DATA SYNC COMPLETED!")
        print(f"\\n📊 ACCURATE SUMMARY:")
        
        for customer in MdmCustomer.objects.all():
            actual_devices = Device.objects.filter(mdm_customer=customer).count()
            active_devices = Device.objects.filter(mdm_customer=customer, status='active').count()
            managed_devices = Device.objects.filter(mdm_customer=customer, status='managed').count()
            
            print(f"\\n🏢 {customer.company.name}:")
            print(f"   Customer ID: {customer.customer_id}")
            print(f"   Total Devices: {actual_devices}")
            print(f"   Active Devices: {active_devices}")
            print(f"   Managed Devices: {managed_devices}")
            
            # Show sample devices
            sample_devices = Device.objects.filter(mdm_customer=customer)[:3]
            for device in sample_devices:
                print(f"   • {device.device_name} ({device.username}) - {device.status}")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.close()

if __name__ == '__main__':
    sync_all_real_data()
