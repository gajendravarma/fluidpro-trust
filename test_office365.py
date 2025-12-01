#!/usr/bin/env python3
import os
import sys
import django

# Setup Django
sys.path.append('/root/customer_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from office365.services import Office365API

def test_office365_api():
    """Test Office 365 API integration"""
    try:
        api = Office365API()
        
        print("Testing Office 365 API Connection...")
        print("=" * 50)
        
        # Test license summary
        print("\n1. Testing License Summary:")
        licenses = api.get_license_summary()
        for license in licenses:
            print(f"   {license['sku_name']}: {license['consumed']}/{license['total']} ({license['usage_percent']:.1f}%)")
        
        # Test mailbox usage
        print("\n2. Testing Mailbox Usage:")
        mailbox_data = api.get_mailbox_usage()
        print(f"   Total Mailboxes: {mailbox_data['total_mailboxes']}")
        print(f"   High Usage Mailboxes: {len(mailbox_data['high_usage'])}")
        
        # Show first 3 mailboxes
        for i, mailbox in enumerate(mailbox_data['all_mailboxes'][:3]):
            print(f"   {i+1}. {mailbox['upn']}: {mailbox['used_percent']:.1f}% ({mailbox['used_gb']:.2f}GB/{mailbox['quota_gb']:.2f}GB)")
        
        print("\n✅ Office 365 API integration successful!")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    test_office365_api()
