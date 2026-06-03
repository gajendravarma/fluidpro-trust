"""
Data migration script to copy MDM data from original project
and link it with existing companies in customer portal
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

from mdm.models import MdmCustomer, Device, SecurityEvent, InstalledApp, AppPolicy, Profile
from rbac.models import Company

def migrate_mdm_data():
    """Migrate data from original MDM project"""
    
    # Connect to original MDM database
    mdm_db_path = '/root/mdm_portal_project/db.sqlite3'
    
    if not os.path.exists(mdm_db_path):
        print(f"MDM database not found at {mdm_db_path}")
        return
    
    conn = sqlite3.connect(mdm_db_path)
    cursor = conn.cursor()
    
    try:
        # Create sample companies if they don't exist
        companies_data = [
            {'name': 'Dignitive Technologies', 'code': 'DIGN'},
            {'name': 'TechCorp Solutions', 'code': 'TECH'},
            {'name': 'InnovateLab', 'code': 'INNO'},
        ]
        
        for comp_data in companies_data:
            company, created = Company.objects.get_or_create(
                code=comp_data['code'],
                defaults={'name': comp_data['name']}
            )
            if created:
                print(f"Created company: {company.name}")
        
        # Migrate customers
        cursor.execute("SELECT * FROM dashboard_customer")
        customers = cursor.fetchall()
        
        # Get column names
        cursor.execute("PRAGMA table_info(dashboard_customer)")
        customer_columns = [col[1] for col in cursor.fetchall()]
        
        for customer_row in customers:
            customer_dict = dict(zip(customer_columns, customer_row))
            
            # Map to existing company (for demo, we'll use the first company)
            company = Company.objects.first()
            
            mdm_customer, created = MdmCustomer.objects.get_or_create(
                customer_id=customer_dict.get('customer_id', f"CUST_{customer_dict['id']}"),
                defaults={
                    'company': company,
                    'device_count': customer_dict.get('device_count', 0),
                    'no_of_devices': customer_dict.get('no_of_devices', ''),
                    'status': customer_dict.get('status', 'active'),
                }
            )
            
            if created:
                print(f"Created MDM customer: {mdm_customer}")
        
        # Migrate devices
        cursor.execute("SELECT * FROM dashboard_device LIMIT 10")  # Limit for demo
        devices = cursor.fetchall()
        
        cursor.execute("PRAGMA table_info(dashboard_device)")
        device_columns = [col[1] for col in cursor.fetchall()]
        
        for device_row in devices:
            device_dict = dict(zip(device_columns, device_row))
            
            # Get MDM customer (use first one for demo)
            mdm_customer = MdmCustomer.objects.first()
            
            if mdm_customer:
                device, created = Device.objects.get_or_create(
                    device_id=device_dict.get('device_id', f"DEV_{device_dict['id']}"),
                    defaults={
                        'mdm_customer': mdm_customer,
                        'device_name': device_dict.get('device_name', 'Unknown Device'),
                        'device_type': device_dict.get('device_type', 'android'),
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
                        'is_supervised': bool(device_dict.get('is_supervised', False)),
                        'is_encrypted': bool(device_dict.get('is_encrypted', False)),
                    }
                )
                
                if created:
                    print(f"Created device: {device.device_name}")
        
        print("MDM data migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()

def create_sample_data():
    """Create sample MDM data for testing"""
    
    # Get or create companies
    company1, _ = Company.objects.get_or_create(
        code='DIGN',
        defaults={'name': 'Dignitive Technologies'}
    )
    
    company2, _ = Company.objects.get_or_create(
        code='TECH',
        defaults={'name': 'TechCorp Solutions'}
    )
    
    # Create MDM customers
    mdm_customer1, _ = MdmCustomer.objects.get_or_create(
        customer_id='DIGN001',
        defaults={
            'company': company1,
            'device_count': 5,
            'status': 'active'
        }
    )
    
    mdm_customer2, _ = MdmCustomer.objects.get_or_create(
        customer_id='TECH001',
        defaults={
            'company': company2,
            'device_count': 3,
            'status': 'active'
        }
    )
    
    # Create sample devices
    devices_data = [
        {
            'device_id': 'DIGN_IPHONE_001',
            'mdm_customer': mdm_customer1,
            'device_name': 'John\'s iPhone',
            'device_type': 'ios',
            'manufacturer': 'Apple',
            'model': 'iPhone 14 Pro',
            'os_version': '17.2',
            'username': 'john.doe',
            'user_email': 'john.doe@dignitive.com',
            'status': 'active',
            'battery_level': 85,
            'is_encrypted': True,
        },
        {
            'device_id': 'DIGN_ANDROID_001',
            'mdm_customer': mdm_customer1,
            'device_name': 'Sarah\'s Galaxy',
            'device_type': 'android',
            'manufacturer': 'Samsung',
            'model': 'Galaxy S23',
            'os_version': '14.0',
            'username': 'sarah.smith',
            'user_email': 'sarah.smith@dignitive.com',
            'status': 'managed',
            'battery_level': 92,
            'is_encrypted': True,
        },
        {
            'device_id': 'TECH_LAPTOP_001',
            'mdm_customer': mdm_customer2,
            'device_name': 'Mike\'s Laptop',
            'device_type': 'laptop',
            'manufacturer': 'Dell',
            'model': 'Latitude 7420',
            'os_version': 'Windows 11',
            'username': 'mike.johnson',
            'user_email': 'mike.johnson@techcorp.com',
            'status': 'active',
            'is_encrypted': True,
        }
    ]
    
    for device_data in devices_data:
        device, created = Device.objects.get_or_create(
            device_id=device_data['device_id'],
            defaults=device_data
        )
        if created:
            print(f"Created sample device: {device.device_name}")
    
    # Create sample security events
    devices = Device.objects.all()
    for device in devices[:2]:  # Create events for first 2 devices
        SecurityEvent.objects.get_or_create(
            device=device,
            event_type='policy_violation',
            defaults={
                'severity': 'medium',
                'description': f'Unauthorized app installation detected on {device.device_name}',
                'resolved': False,
            }
        )
    
    print("Sample MDM data created successfully!")

if __name__ == '__main__':
    print("Starting MDM data migration...")
    
    # Try to migrate from original MDM project first
    migrate_mdm_data()
    
    # Create sample data for testing
    create_sample_data()
    
    print("MDM integration completed!")
