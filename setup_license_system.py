#!/usr/bin/env python3
"""
Setup script for license management system
"""
import os
import sys
import django
from datetime import date, timedelta

# Setup Django
sys.path.append('/home/devops-machine/Fluidtrust-project/customer_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from django.contrib.auth.models import User
from rbac.models import Company, Package, UserPackageAccess, CompanyLicense, UserProfile

def setup_license_system():
    """Setup sample license data"""
    print("🔧 Setting up License Management System...")
    
    # Ensure packages exist
    packages_data = [
        ('pulseway', 'Pulseway RMM'),
        ('mdm', 'Mobile Device Management'),
        ('tickets', 'Ticket Management'),
    ]
    
    for name, display_name in packages_data:
        package, created = Package.objects.get_or_create(
            name=name,
            defaults={'display_name': display_name, 'is_active': True}
        )
        if created:
            print(f"✅ Created package: {display_name}")
    
    # Get companies with MDM customers
    companies = Company.objects.filter(mdm_customer__isnull=False)
    packages = Package.objects.all()
    
    # Create sample licenses for each company
    for company in companies:
        print(f"\n🏢 Setting up licenses for {company.name}:")
        
        for package in packages:
            license_data = {
                'pulseway': {'total': 50, 'used': 25, 'type': 'Premium'},
                'mdm': {'total': 100, 'used': 45, 'type': 'Enterprise'},
                'tickets': {'total': 25, 'used': 12, 'type': 'Standard'},
            }
            
            data = license_data.get(package.name, {'total': 10, 'used': 5, 'type': 'Standard'})
            
            license, created = CompanyLicense.objects.get_or_create(
                company=company,
                package=package,
                defaults={
                    'total_licenses': data['total'],
                    'used_licenses': data['used'],
                    'license_type': data['type'],
                    'expiry_date': date.today() + timedelta(days=365),
                    'is_active': True
                }
            )
            
            if created:
                print(f"   ✅ {package.display_name}: {data['total']} licenses ({data['used']} used)")
    
    # Assign package access to existing users
    print(f"\n👥 Assigning package access to users:")
    
    for profile in UserProfile.objects.filter(company__isnull=False):
        user = profile.user
        company = profile.company
        
        # Give access to packages that have licenses for their company
        company_packages = CompanyLicense.objects.filter(
            company=company, is_active=True
        ).values_list('package', flat=True)
        
        for package_id in company_packages:
            package = Package.objects.get(id=package_id)
            access, created = UserPackageAccess.objects.get_or_create(
                user=user,
                package=package,
                defaults={'is_enabled': True, 'can_read': True}
            )
            
            if created:
                print(f"   ✅ {user.username} -> {package.display_name}")
    
    print(f"\n🎉 License Management System setup complete!")
    print(f"📊 Access URLs:")
    print(f"   User License Dashboard: http://192.168.2.68:8000/rbac/licenses/")
    print(f"   Admin License Management: http://192.168.2.68:8000/rbac/licenses/company/12/")

if __name__ == '__main__':
    setup_license_system()
