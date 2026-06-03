from django.core.management.base import BaseCommand
from pulseway.local_service import PulsewayLocalService
from pulseway.services import PulsewayAPI
from pulseway.models import PulsewayDevice
import json


class Command(BaseCommand):
    help = 'Sync detailed device information from Pulseway API'

    def add_arguments(self, parser):
        parser.add_argument('--device-id', type=str, help='Sync specific device by ID')
        parser.add_argument('--debug', action='store_true', help='Show debug information')

    def handle(self, *args, **options):
        api = PulsewayAPI()
        
        if options['device_id']:
            # Sync specific device
            device_id = options['device_id']
            self.stdout.write(f"Syncing device: {device_id}")
            
            # Get device details
            details = api.get_device_details(device_id)
            if details:
                self.stdout.write("Device details:")
                self.stdout.write(json.dumps(details, indent=2))
            
            # Try to get system info
            try:
                system_info = api.get_device_system_info(device_id)
                if system_info:
                    self.stdout.write("System info:")
                    self.stdout.write(json.dumps(system_info, indent=2))
            except Exception as e:
                self.stdout.write(f"System info error: {e}")
        
        else:
            # Sync all devices
            self.stdout.write("Starting device sync...")
            
            if options['debug']:
                # Get first few devices and show all available fields
                devices = api.get_all_devices()[:3]
                for device in devices:
                    device_id = device.get('Identifier')
                    self.stdout.write(f"\n=== Device: {device.get('Name')} ===")
                    
                    # Show basic device data
                    self.stdout.write("Basic device data:")
                    for key, value in device.items():
                        self.stdout.write(f"  {key}: {value}")
                    
                    # Get detailed data
                    if device_id:
                        details = api.get_device_details(device_id)
                        if details and 'Data' in details:
                            self.stdout.write("\nDetailed device data:")
                            for key, value in details['Data'].items():
                                self.stdout.write(f"  {key}: {value}")
                        
                        # Try different endpoints for system info
                        endpoints = [
                            'systeminfo', 'system', 'info', 'details', 
                            'hardware', 'software', 'network'
                        ]
                        
                        for endpoint in endpoints:
                            try:
                                url = f"devices/{device_id}/{endpoint}"
                                response = getattr(api.api, 'devices')(device_id).get()
                                if response:
                                    self.stdout.write(f"\n{endpoint.upper()} endpoint:")
                                    self.stdout.write(json.dumps(response, indent=2)[:500] + "...")
                            except Exception as e:
                                self.stdout.write(f"{endpoint} endpoint error: {e}")
            
            # Run normal sync
            service = PulsewayLocalService()
            success = service.sync_devices()
            
            if success:
                self.stdout.write(self.style.SUCCESS("Device sync completed successfully"))
                
                # Show sample of synced data
                devices = PulsewayDevice.objects.all()[:5]
                self.stdout.write(f"\nSynced {devices.count()} devices. Sample:")
                for device in devices:
                    self.stdout.write(f"  {device.device_name}: OS={device.operating_system}, IP={device.ip_address}")
            else:
                self.stdout.write(self.style.ERROR("Device sync failed"))
