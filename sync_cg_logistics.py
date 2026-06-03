"""
Script to sync real CG Logistics data and fix company name matching
"""

import os
import sys
import django
import sqlite3
from difflib import SequenceMatcher

# Setup Django environment
sys.path.append('/home/devops-machine/Fluidtrust-project/customer_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from mdm.models import MdmCustomer, Device, SecurityEvent
from rbac.models import Company

def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def sync_cg_logistics_data():
    """Sync real CG Logistics data from MDM database"""
    
    mdm_db_path = '/root/mdm_portal_project/db.sqlite3'
    
    if not os.path.exists(mdm_db_path):
        print(f"MDM database not found at {mdm_db_path}")
        return
    
    conn = sqlite3.connect(mdm_db_path)
    cursor = conn.cursor()
    
    try:
        # Get CG Logistics customer (ID: 1, Customer ID: 301)
        cursor.execute("SELECT * FROM dashboard_customer WHERE id = 1")
        cg_customer = cursor.fetchone()
        
        if not cg_customer:
            print("CG Logistics customer (ID: 301) not found in MDM database")
            return
        
        cursor.execute("PRAGMA table_info(dashboard_customer)")
        customer_columns = [col[1] for col in cursor.fetchall()]
        cg_customer_dict = dict(zip(customer_columns, cg_customer))
        
        print(f"Found CG Logistics: {cg_customer_dict}")
        
        # Find or create matching company in customer portal
        # Try exact match first
        try:
            company = Company.objects.get(name__iexact="C G Logistics")
        except Company.DoesNotExist:
            try:
                company = Company.objects.get(name__icontains="CG")
            except Company.DoesNotExist:
                try:
                    company = Company.objects.get(name__icontains="Logistics")
                except Company.DoesNotExist:
                    # Create new company
                    company = Company.objects.create(
                        name="C G Logistics",
                        code="CGL"
                    )
                    print(f"Created new company: {company.name}")
        
        # Create or update MDM customer
        mdm_customer, created = MdmCustomer.objects.update_or_create(
            customer_id="301",
            defaults={
                'company': company,
                'device_count': cg_customer_dict.get('device_count', 11),
                'no_of_devices': cg_customer_dict.get('no_of_devices', '11'),
                'status': cg_customer_dict.get('status', 'active'),
            }
        )
        
        print(f"{'Created' if created else 'Updated'} MDM customer: {mdm_customer}")
        
        # Get devices for CG Logistics
        cursor.execute("SELECT * FROM dashboard_device WHERE customer_id = 1")
        devices = cursor.fetchall()
        
        cursor.execute("PRAGMA table_info(dashboard_device)")
        device_columns = [col[1] for col in cursor.fetchall()]
        
        device_count = 0
        for device_row in devices:
            device_dict = dict(zip(device_columns, device_row))
            
            device, created = Device.objects.update_or_create(
                device_id=device_dict.get('device_id', f"CGL_DEV_{device_dict['id']}"),
                defaults={
                    'mdm_customer': mdm_customer,
                    'device_name': device_dict.get('device_name', 'CGL Device'),
                    'device_type': device_dict.get('device_type', 'android'),
                    'platform': device_dict.get('platform', ''),
                    'model': device_dict.get('model', ''),
                    'manufacturer': device_dict.get('manufacturer', ''),
                    'os_version': device_dict.get('os_version', ''),
                    'serial_number': device_dict.get('serial_number', ''),
                    'imei': device_dict.get('imei', ''),
                    'phone_number': device_dict.get('phone_number', ''),
                    'status': 'active' if device_dict.get('status') == 'managed' else device_dict.get('status', 'active'),
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
            device_count += 1
            if created:
                print(f"Created device: {device.device_name}")
        
        # Update device count
        mdm_customer.device_count = device_count
        mdm_customer.save()
        
        print(f"Synced {device_count} devices for CG Logistics")
        
        # Get security events
        cursor.execute("""
            SELECT se.* FROM dashboard_securityevent se 
            JOIN dashboard_device d ON se.device_id = d.id 
            WHERE d.customer_id = 1
        """)
        
        security_events = cursor.fetchall()
        print(f"Found {len(security_events)} security events for CG Logistics")
        
        conn.close()
        
        print("CG Logistics data sync completed successfully!")
        
    except Exception as e:
        print(f"Error syncing CG Logistics data: {e}")
        conn.close()

if __name__ == '__main__':
    sync_cg_logistics_data()
