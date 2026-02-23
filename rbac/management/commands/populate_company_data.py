from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from rbac.models import Company, UserProfile
from tickets.models import Ticket
from pulseway.models import PulsewayDevice, PulsewayPatchReport
from office365.models import Office365User
from datetime import datetime, timedelta
import random


class Command(BaseCommand):
    help = 'Populate sample company dashboard data'

    def handle(self, *args, **options):
        # Get or create companies
        companies = []
        for company_name in ['Wepsol', 'TechCorp', 'DataSystems']:
            company, created = Company.objects.get_or_create(
                name=company_name,
                defaults={'code': company_name.lower()}
            )
            companies.append(company)
            if created:
                self.stdout.write(f'Created company: {company_name}')
        
        # Link existing users to companies
        for profile in UserProfile.objects.filter(company__isnull=True):
            # Assign to first company as default
            if companies:
                profile.company = companies[0]
                profile.save()
                self.stdout.write(f'Linked {profile.user.username} to {companies[0].name}')
        
        # Create sample data for each company
        for company in companies:
            # Create tickets
            users = User.objects.filter(userprofile__company=company)
            if users.exists():
                user = users.first()
                for i in range(10):
                    Ticket.objects.get_or_create(
                        title=f'Ticket {i+1} for {company.name}',
                        company=company,
                        defaults={
                            'description': f'Sample ticket description {i+1}',
                            'status': random.choice(['Open', 'Closed', 'Onhold']),
                            'priority': random.choice(['Low', 'Normal', 'High', 'Urgent']),
                            'created_by': user
                        }
                    )
            
            # Create Pulseway devices
            for i in range(5):
                device, created = PulsewayDevice.objects.get_or_create(
                    device_id=f'{company.code}-device-{i+1}',
                    defaults={
                        'company': company,
                        'device_name': f'{company.name} Server {i+1}',
                        'status': random.choice(['online', 'offline'])
                    }
                )
                
                # Create patch reports for each device
                if created:
                    for j in range(3):
                        PulsewayPatchReport.objects.create(
                            company=company,
                            device=device,
                            patch_name=f'Security Update {j+1}',
                            status=random.choice(['installed', 'pending', 'failed'])
                        )
            
            # Create Office365 users
            for i in range(8):
                Office365User.objects.get_or_create(
                    email=f'user{i+1}@{company.code}.com',
                    defaults={
                        'company': company,
                        'display_name': f'{company.name} User {i+1}',
                        'license_assigned': random.choice([True, False])
                    }
                )
        
        self.stdout.write(self.style.SUCCESS('Successfully populated sample data'))
