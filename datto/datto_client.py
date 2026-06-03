import requests
from requests.auth import HTTPBasicAuth
from django.conf import settings

class DattoClient:
    def __init__(self):
        self.auth = HTTPBasicAuth(settings.DATTO_PUBLIC_KEY, settings.DATTO_SECRET_KEY)
        self.base_url = settings.DATTO_BASE_URL
    
    def get_devices(self):
        """Get all BCDR devices"""
        url = f"{self.base_url}/bcdr/device"
        resp = requests.get(url, auth=self.auth)
        resp.raise_for_status()
        return resp.json()
    
    def get_agents(self):
        """Get all BCDR agents/clients"""
        url = f"{self.base_url}/bcdr/agent"
        resp = requests.get(url, auth=self.auth)
        resp.raise_for_status()
        return resp.json()
    
    def get_dtc_assets(self):
        """Get all direct-to-cloud assets"""
        url = f"{self.base_url}/dtc/assets"
        resp = requests.get(url, auth=self.auth)
        resp.raise_for_status()
        return resp.json()
    
    def get_dtc_client_assets(self, client_id):
        """Get all direct-to-cloud assets for a client"""
        url = f"{self.base_url}/dtc/{client_id}/assets"
        resp = requests.get(url, auth=self.auth)
        resp.raise_for_status()
        return resp.json()
    
    def get_dtc_asset_details(self, client_id, asset_uuid):
        """Get specific direct-to-cloud asset details"""
        url = f"{self.base_url}/dtc/{client_id}/assets/{asset_uuid}"
        resp = requests.get(url, auth=self.auth)
        resp.raise_for_status()
        return resp.json()
    
    def get_dtc_storage_pool(self):
        """Get storage pool usage"""
        url = f"{self.base_url}/dtc/storage-pool"
        resp = requests.get(url, auth=self.auth)
        resp.raise_for_status()
        return resp.json()
