import requests
import base64
import os
from django.conf import settings
from .token_manager import TokenManager

class Site24x7Platform:
    def __init__(self):
        self.token_manager = TokenManager()
        self.access_token = self.token_manager.get_valid_token()
        self.api_domain = settings.SITE24X7_API_DOMAIN
        self.headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Accept": "application/json; version=2.0"
        }
    
    @staticmethod
    def encode_zaaid(zaaid):
        """Encode ZAAID to base64"""
        return base64.b64encode(str(zaaid).encode()).decode()
    
    @staticmethod
    def decode_zaaid(encoded_zaaid):
        """Decode base64 ZAAID"""
        try:
            return base64.b64decode(encoded_zaaid).decode()
        except:
            return encoded_zaaid
    
    def call_api(self, endpoint, zaaid=None, method="GET", data=None):
        if zaaid:
            separator = "&" if "?" in endpoint else "?"
            url = f"{self.api_domain}{endpoint}{separator}zaaid={zaaid}"
        else:
            url = f"{self.api_domain}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            
            if response.status_code == 401:
                # Token expired, try to refresh
                new_token = self.token_manager.handle_401_error()
                if new_token:
                    self.access_token = new_token
                    self.headers["Authorization"] = f"Zoho-oauthtoken {new_token}"
                    # Retry the request
                    if method == "GET":
                        response = requests.get(url, headers=self.headers)
                    elif method == "POST":
                        response = requests.post(url, headers=self.headers, json=data)
            
            return response.json() if response.content else {}
        except Exception as e:
            return {"error": str(e)}
    
    def get_customers(self):
        """Get MSP customers"""
        return self.call_api("/api/short/msp/customers")
    
    def get_monitors(self, zaaid=None):
        """Get monitors for a customer"""
        return self.call_api("/api/monitors", zaaid=zaaid)
    
    def get_monitor_details(self, monitor_id, zaaid=None):
        """Get detailed monitor information"""
        return self.call_api(f"/api/monitors/{monitor_id}", zaaid=zaaid)
    
    def get_current_status(self, zaaid=None):
        """Get current status of all monitors"""
        return self.call_api("/api/current_status", zaaid=zaaid)
    
    def get_reports(self, monitor_id, period=1, zaaid=None):
        """Get monitor reports"""
        return self.call_api(f"/api/reports/summary/{monitor_id}?period={period}", zaaid=zaaid)
