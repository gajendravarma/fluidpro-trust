from django.conf import settings
from tickets.services import ManageEngineService
from pulseway.services import PulsewayAPI
from datto.datto_client import DattoClient
from office365.services import Office365API
from site24x7.site24x7_client import Site24x7Platform
from .models import LicenseConfig


class LicenseDashboardService:
    """Service to fetch license data for all integrated services"""
    
    def _get_license_config(self, service_name):
        """Get license config from DB or fallback to settings"""
        try:
            config = LicenseConfig.objects.get(service_name=service_name)
            return {
                'total_licenses': config.total_licenses,
                'license_type': config.license_type,
                'expiry_date': config.expiry_date.strftime('%Y-%m-%d')
            }
        except LicenseConfig.DoesNotExist:
            return settings.LICENSE_CONFIG.get(service_name, {})
    
    def get_manageengine_license(self):
        """Get ManageEngine license usage"""
        try:
            config = self._get_license_config('manageengine')
            me_service = ManageEngineService()
            techs = me_service.get_technicians()
            used = len(techs.get('users', [])) if techs else 0
            total = config['total_licenses']
            
            return {
                'service': 'ManageEngine',
                'total': total,
                'used': used,
                'available': total - used,
                'percentage': round((used / total * 100), 1) if total > 0 else 0,
                'license_type': config['license_type'],
                'expiry_date': config['expiry_date']
            }
        except Exception as e:
            return {'service': 'ManageEngine', 'error': str(e)}
    
    def get_pulseway_license(self):
        """Get Pulseway license usage"""
        try:
            config = self._get_license_config('pulseway')
            pw_service = PulsewayAPI()
            devices = pw_service.get_all_devices()
            used = sum(1 for d in devices if d.get('IsAgentInstalled', False))
            total = config['total_licenses']
            
            return {
                'service': 'Pulseway',
                'total': total,
                'used': used,
                'available': total - used,
                'percentage': round((used / total * 100), 1) if total > 0 else 0,
                'license_type': config['license_type'],
                'expiry_date': config['expiry_date']
            }
        except Exception as e:
            return {'service': 'Pulseway', 'error': str(e)}
    
    def get_datto_license(self):
        """Get Datto license usage"""
        try:
            config = self._get_license_config('datto')
            datto_client = DattoClient()
            devices = datto_client.get_devices()
            agents = datto_client.get_agents()
            used = len(devices.get('items', [])) + len(agents.get('clients', []))
            total = config['total_licenses']
            
            return {
                'service': 'Datto',
                'total': total,
                'used': used,
                'available': total - used,
                'percentage': round((used / total * 100), 1) if total > 0 else 0,
                'license_type': config['license_type'],
                'expiry_date': config['expiry_date']
            }
        except Exception as e:
            return {'service': 'Datto', 'error': str(e)}
    
    def get_office365_license(self):
        """Get Office 365 license usage - REAL API DATA"""
        try:
            o365_api = Office365API()
            license_summary = o365_api.get_license_summary()
            
            # Aggregate all SKUs
            total = sum(sku['total'] for sku in license_summary)
            used = sum(sku['consumed'] for sku in license_summary)
            available = sum(sku['available'] for sku in license_summary)
            
            return {
                'service': 'Office 365',
                'total': total,
                'used': used,
                'available': available,
                'percentage': round((used / total * 100), 1) if total > 0 else 0,
                'license_type': 'Microsoft 365',
                'expiry_date': settings.LICENSE_CONFIG.get('office365', {}).get('expiry_date', 'N/A'),
                'skus': license_summary  # Detailed SKU breakdown
            }
        except Exception as e:
            return {'service': 'Office 365', 'error': str(e)}
    
    def get_site24x7_license(self):
        """Get Site24x7 license usage"""
        try:
            config = self._get_license_config('site24x7')
            site24x7 = Site24x7Platform()
            monitors = site24x7.get_monitors()
            used = len(monitors.get('data', [])) if monitors else 0
            total = config['total_licenses']
            
            return {
                'service': 'Site24x7',
                'total': total,
                'used': used,
                'available': total - used,
                'percentage': round((used / total * 100), 1) if total > 0 else 0,
                'license_type': config['license_type'],
                'expiry_date': config['expiry_date']
            }
        except Exception as e:
            return {'service': 'Site24x7', 'error': str(e)}
    
    def get_all_licenses(self):
        """Get license data for all services"""
        return {
            'manageengine': self.get_manageengine_license(),
            'pulseway': self.get_pulseway_license(),
            'datto': self.get_datto_license(),
            'office365': self.get_office365_license(),
            'site24x7': self.get_site24x7_license()
        }
