from django.core.management.base import BaseCommand
from django.conf import settings
from rbac.models import LicenseConfig
from datetime import datetime


class Command(BaseCommand):
    help = 'Initialize license configurations from settings'

    def handle(self, *args, **kwargs):
        services = ['manageengine', 'pulseway', 'datto', 'site24x7']
        
        for service in services:
            config_data = settings.LICENSE_CONFIG.get(service, {})
            
            if config_data:
                license_config, created = LicenseConfig.objects.get_or_create(
                    service_name=service,
                    defaults={
                        'total_licenses': config_data.get('total_licenses', 0),
                        'license_type': config_data.get('license_type', 'Standard'),
                        'expiry_date': datetime.strptime(config_data.get('expiry_date', '2026-12-31'), '%Y-%m-%d').date()
                    }
                )
                
                if created:
                    self.stdout.write(self.style.SUCCESS(
                        f'Created license config for {service}'
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f'License config for {service} already exists'
                    ))
        
        self.stdout.write(self.style.SUCCESS('License initialization complete!'))
