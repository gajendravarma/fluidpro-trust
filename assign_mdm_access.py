"""
Script to assign MDM package access to users
"""

import os
import sys
import django

# Setup Django environment
sys.path.append('/home/devops-machine/Fluidtrust-project/customer_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from django.contrib.auth.models import User
from rbac.models import Package, UserPackageAccess

def assign_mdm_access():
    """Assign MDM access to admin and technician users"""
    
    try:
        mdm_package = Package.objects.get(name='mdm')
        print(f"Found MDM package: {mdm_package.display_name}")
        
        # Get admin users (superusers)
        admin_users = User.objects.filter(is_superuser=True)
        
        for user in admin_users:
            access, created = UserPackageAccess.objects.get_or_create(
                user=user,
                package=mdm_package,
                defaults={
                    'is_enabled': True,
                    'can_create': True,
                    'can_read': True,
                    'can_update': True,
                    'can_delete': True,
                }
            )
            
            if created:
                print(f"✅ Granted MDM access to admin: {user.username}")
            else:
                print(f"ℹ️  Admin {user.username} already has MDM access")
        
        # Get technician users (users with technician role)
        from rbac.models import UserProfile, Role
        
        try:
            tech_role = Role.objects.get(name='technician')
            tech_users = UserProfile.objects.filter(role=tech_role)
            
            for user_profile in tech_users:
                access, created = UserPackageAccess.objects.get_or_create(
                    user=user_profile.user,
                    package=mdm_package,
                    defaults={
                        'is_enabled': True,
                        'can_create': True,
                        'can_read': True,
                        'can_update': True,
                        'can_delete': False,  # Technicians can't delete
                    }
                )
                
                if created:
                    print(f"✅ Granted MDM access to technician: {user_profile.user.username}")
                else:
                    print(f"ℹ️  Technician {user_profile.user.username} already has MDM access")
        
        except Role.DoesNotExist:
            print("⚠️  Technician role not found")
        
        print("\n🎉 MDM access assignment completed!")
        print("\nℹ️  Note: Customer users need to be assigned MDM access manually through the admin interface.")
        print("   Go to: http://localhost:8000/rbac/manage-users/")
        
    except Package.DoesNotExist:
        print("❌ MDM package not found. Please run: python3 manage.py create_mdm_package")

if __name__ == '__main__':
    assign_mdm_access()
