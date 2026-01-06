import requests
import os
import json
from datetime import datetime, timedelta
from django.conf import settings

class TokenManager:
    def __init__(self):
        self.env_file = '.env'
        
    def refresh_access_token(self):
        """Refresh access token using refresh token"""
        refresh_token = settings.SITE24X7_REFRESH_TOKEN
        client_id = settings.ZOHO_CLIENT_ID
        client_secret = settings.ZOHO_CLIENT_SECRET
        
        if not refresh_token:
            raise Exception("No refresh token available")
        if not client_id or not client_secret:
            raise Exception("Zoho client credentials not configured")
            
        data = {
            'refresh_token': refresh_token,
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'refresh_token'
        }
        
        response = requests.post('https://accounts.zoho.in/oauth/v2/token', data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            return token_data['access_token']
        else:
            raise Exception(f"Token refresh failed: {response.text}")
    
    def get_valid_token(self):
        """Get access token"""
        return settings.SITE24X7_ACCESS_TOKEN
    
    def handle_401_error(self):
        """Handle 401 error by refreshing token"""
        try:
            return self.refresh_access_token()
        except Exception as e:
            print(f"Token refresh failed: {e}")
            return None
