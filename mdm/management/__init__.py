"""
Management command to create MDM package for user access control
"""
from django.core.management.base import BaseCommand
from rbac.models import Package

class Command(BaseCommand):
    help = 'Create MDM package for user access control'

    def handle(self, *args, **options):
        package, created = Package.objects.get_or_create(
            name='mdm',
            defaults={
                'display_name': 'Mobile Device Management',
                'description': 'Access to MDM dashboard, device management, and security monitoring',
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created MDM package: {package.display_name}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'MDM package already exists: {package.display_name}')
            )
