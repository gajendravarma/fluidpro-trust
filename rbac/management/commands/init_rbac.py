from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rbac.models import Package, UserPackageAccess

class Command(BaseCommand):
    help = 'Initialize RBAC system with default packages and demo users'

    def handle(self, *args, **options):
        self.stdout.write('Initializing RBAC system...')

        # Create packages
        packages_data = [
            ('manageengine', 'ManageEngine', 'IT Service Management and Help Desk'),
            ('pulseway', 'Pulseway', 'Remote Monitoring and Management'),
            ('office365', 'Office 365', 'Microsoft Office 365 Management'),
            ('datto', 'Datto', 'Backup and Disaster Recovery'),
            ('site24x7', 'Site24x7', 'Website and Server Monitoring'),
        ]

        for name, display_name, description in packages_data:
            package, created = Package.objects.get_or_create(
                name=name,
                defaults={
                    'display_name': display_name,
                    'description': description
                }
            )
            if created:
                self.stdout.write(f'Created package: {display_name}')

        # Create demo users with access
        self.create_demo_users()

        self.stdout.write(self.style.SUCCESS('RBAC system initialized successfully!'))

    def create_demo_users(self):
        """Create demo users with different access levels"""
        
        # Admin user (superuser - has access to everything)
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(f'Created admin user: admin')

        # Manager user - access to all packages with full permissions
        manager_user, created = User.objects.get_or_create(
            username='manager',
            defaults={'email': 'manager@example.com'}
        )
        if created:
            manager_user.set_password('manager123')
            manager_user.save()
            self.stdout.write(f'Created user: manager')
            
            # Give manager access to all packages
            for package in Package.objects.all():
                UserPackageAccess.objects.get_or_create(
                    user=manager_user,
                    package=package,
                    defaults={
                        'can_create': True,
                        'can_read': True,
                        'can_update': True,
                        'can_delete': False,  # No delete for manager
                    }
                )

        # Technician user - access to technical packages
        tech_user, created = User.objects.get_or_create(
            username='tech1',
            defaults={'email': 'tech1@example.com'}
        )
        if created:
            tech_user.set_password('tech123')
            tech_user.save()
            self.stdout.write(f'Created user: tech1')
            
            # Give tech access to technical packages
            tech_packages = Package.objects.filter(name__in=['manageengine', 'pulseway', 'datto'])
            for package in tech_packages:
                UserPackageAccess.objects.get_or_create(
                    user=tech_user,
                    package=package,
                    defaults={
                        'can_create': True,
                        'can_read': True,
                        'can_update': True,
                        'can_delete': False,
                    }
                )

        # Viewer user - read-only access to some packages
        viewer_user, created = User.objects.get_or_create(
            username='viewer1',
            defaults={'email': 'viewer1@example.com'}
        )
        if created:
            viewer_user.set_password('viewer123')
            viewer_user.save()
            self.stdout.write(f'Created user: viewer1')
            
            # Give viewer read-only access to office365 and site24x7
            viewer_packages = Package.objects.filter(name__in=['office365', 'site24x7'])
            for package in viewer_packages:
                UserPackageAccess.objects.get_or_create(
                    user=viewer_user,
                    package=package,
                    defaults={
                        'can_create': False,
                        'can_read': True,
                        'can_update': False,
                        'can_delete': False,
                    }
                )
