import requests
import logging
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings

logger = logging.getLogger('rbac.registration')

class GraphEmailBackend(BaseEmailBackend):
    """
    Email backend using Microsoft Graph API with enhanced HTML email support
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.access_token = None
    
    def _get_access_token(self):
        """Get OAuth2 access token from Microsoft"""
        token_url = f"https://login.microsoftonline.com/{settings.GRAPH_TENANT_ID}/oauth2/v2.0/token"
        
        token_data = {
            "grant_type": "client_credentials",
            "client_id": settings.GRAPH_CLIENT_ID,
            "client_secret": settings.GRAPH_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default"
        }
        
        try:
            response = requests.post(token_url, data=token_data)
            response.raise_for_status()
            return response.json()["access_token"]
        except Exception as e:
            logger.error(f"Failed to get access token: {str(e)}")
            return None
    
    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        
        # Get access token
        self.access_token = self._get_access_token()
        if not self.access_token:
            logger.error("No access token available")
            return 0
        
        sent_count = 0
        for message in email_messages:
            if self._send_message(message):
                sent_count += 1
        
        return sent_count
    
    def _send_message(self, message):
        """Send a single email via Graph API"""
        send_mail_url = f"https://graph.microsoft.com/v1.0/users/{settings.GRAPH_FROM_EMAIL}/sendMail"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # Check if message has HTML content
        if hasattr(message, 'alternatives') and message.alternatives:
            # Use HTML content if available
            html_content = message.alternatives[0][0]
            content_type = "HTML"
            content = html_content
        else:
            # Convert plain text to HTML
            content = message.body.replace('\n', '<br>')
            content_type = "HTML"
        
        email_body = {
            "message": {
                "subject": message.subject,
                "body": {
                    "contentType": content_type,
                    "content": content
                },
                "toRecipients": [
                    {"emailAddress": {"address": recipient}}
                    for recipient in message.to
                ]
            },
            "saveToSentItems": True
        }
        
        try:
            response = requests.post(send_mail_url, headers=headers, json=email_body)
            response.raise_for_status()
            logger.info(f"Email sent successfully to {message.to}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            if hasattr(response, 'text'):
                logger.error(f"Response: {response.text}")
            return False
