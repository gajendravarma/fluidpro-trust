import requests
import sqlite3
from difflib import SequenceMatcher
from django.conf import settings

def similarity(a, b):
    """Calculate similarity between two strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def get_mdm_data_for_company(company_name):
    """Get real MDM data for a specific company"""
    
    # Connect to original MDM database
    mdm_db_path = '/root/mdm_portal_project/db.sqlite3'
    
    try:
        conn = sqlite3.connect(mdm_db_path)
        cursor = conn.cursor()
        
        # Get all customers from MDM database
        cursor.execute("SELECT * FROM dashboard_customer")
        customers = cursor.fetchall()
        
        # Get column names
        cursor.execute("PRAGMA table_info(dashboard_customer)")
        customer_columns = [col[1] for col in cursor.fetchall()]
        
        # Find matching customer by company name similarity
        best_match = None
        best_similarity = 0.0
        
        for customer_row in customers:
            customer_dict = dict(zip(customer_columns, customer_row))
            customer_name = customer_dict.get('name', '')
            
            # Calculate similarity
            sim = similarity(company_name, customer_name)
            if sim > best_similarity and sim > 0.6:  # 60% similarity threshold
                best_similarity = sim
                best_match = customer_dict
        
        if not best_match:
            return None
        
        # Get devices for this customer
        cursor.execute("SELECT * FROM dashboard_device WHERE customer_id = ?", (best_match['id'],))
        devices = cursor.fetchall()
        
        cursor.execute("PRAGMA table_info(dashboard_device)")
        device_columns = [col[1] for col in cursor.fetchall()]
        
        device_list = []
        for device_row in devices:
            device_dict = dict(zip(device_columns, device_row))
            device_list.append(device_dict)
        
        # Get security events
        cursor.execute("""
            SELECT se.* FROM dashboard_securityevent se 
            JOIN dashboard_device d ON se.device_id = d.id 
            WHERE d.customer_id = ?
        """, (best_match['id'],))
        
        security_events = cursor.fetchall()
        
        conn.close()
        
        return {
            'customer': best_match,
            'devices': device_list,
            'total_devices': len(device_list),
            'active_devices': len([d for d in device_list if d.get('status') == 'active']),
            'security_events': len(security_events),
            'similarity_score': best_similarity
        }
        
    except Exception as e:
        print(f"Error fetching MDM data: {e}")
        return None

def sync_mdm_customer_data(company_name):
    """Sync MDM data for a specific company"""
    
    mdm_data = get_mdm_data_for_company(company_name)
    if not mdm_data:
        return False
    
    from .models import MdmCustomer, Device
    from rbac.models import Company
    
    try:
        # Get or create company
        company = Company.objects.get(name=company_name)
        
        # Create or update MDM customer
        customer_data = mdm_data['customer']
        mdm_customer, created = MdmCustomer.objects.get_or_create(
            customer_id=customer_data.get('customer_id', f"MDM_{customer_data['id']}"),
            defaults={
                'company': company,
                'device_count': mdm_data['total_devices'],
                'status': customer_data.get('status', 'active')
            }
        )
        
        # Sync devices
        for device_data in mdm_data['devices']:
            Device.objects.update_or_create(
                device_id=device_data.get('device_id', f"DEV_{device_data['id']}"),
                defaults={
                    'mdm_customer': mdm_customer,
                    'device_name': device_data.get('device_name', 'Unknown Device'),
                    'device_type': device_data.get('device_type', 'android'),
                    'platform': device_data.get('platform', ''),
                    'model': device_data.get('model', ''),
                    'manufacturer': device_data.get('manufacturer', ''),
                    'os_version': device_data.get('os_version', ''),
                    'status': device_data.get('status', 'managed'),
                    'username': device_data.get('username', ''),
                    'user_email': device_data.get('user_email', ''),
                    'battery_level': device_data.get('battery_level'),
                    'is_encrypted': bool(device_data.get('is_encrypted', False)),
                }
            )
        
        return True
        
    except Exception as e:
        print(f"Error syncing MDM data: {e}")
        return False
