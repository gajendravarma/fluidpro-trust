from django.core.management.base import BaseCommand
from pulseway.local_service import PulsewayLocalService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync Pulseway data to local database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sync-type',
            type=str,
            choices=['all', 'organizations', 'devices', 'patches', 'reports'],
            default='all',
            help='Type of data to sync'
        )

    def handle(self, *args, **options):
        sync_type = options['sync_type']
        service = PulsewayLocalService()
        
        self.stdout.write(f'Starting Pulseway {sync_type} sync...')
        
        try:
            if sync_type == 'all':
                success = service.sync_all_data()
            elif sync_type == 'organizations':
                service.sync_organizations()
                success = True
            elif sync_type == 'devices':
                service.sync_devices()
                success = True
            elif sync_type == 'patches':
                service.sync_patches()
                success = True
            elif sync_type == 'reports':
                service.sync_reports()
                success = True
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully synced {sync_type} data')
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'Failed to sync {sync_type} data')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error syncing {sync_type} data: {str(e)}')
            )
