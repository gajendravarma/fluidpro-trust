from django.core.management.base import BaseCommand
from rbac.models import Role

class Command(BaseCommand):
    help = 'Initialize roles in the system'

    def handle(self, *args, **options):
        roles_data = [
            {'name': 'admin', 'description': 'Full system access and user management'},
            {'name': 'technician', 'description': 'Access to assigned packages with specific permissions'},
            {'name': 'customer', 'description': 'View company-specific data and reports'},
        ]
        
        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                name=role_data['name'],
                defaults={'description': role_data['description']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created role: {role.get_name_display()}'))
            else:
                self.stdout.write(self.style.WARNING(f'Role already exists: {role.get_name_display()}'))
        
        self.stdout.write(self.style.SUCCESS('Roles initialization complete!'))
