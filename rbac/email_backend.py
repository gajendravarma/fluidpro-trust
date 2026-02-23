import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings
import logging

logger = logging.getLogger('rbac.registration')

class AutoForwardEmailBackend(BaseEmailBackend):
    """
    Custom email backend that saves emails to files and attempts to forward them
    """
    
    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        
        sent_count = 0
        
        for message in email_messages:
            try:
                # Save to file first (backup)
                self._save_to_file(message)
                
                # Try to forward via Gmail SMTP (if available)
                if self._try_gmail_forward(message):
                    logger.info(f"Email forwarded successfully to {message.to}")
                    sent_count += 1
                else:
                    logger.info(f"Email saved to file for {message.to}")
                    sent_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to process email: {str(e)}")
        
        return sent_count
    
    def _save_to_file(self, message):
        """Save email to file as backup"""
        import time
        import threading
        
        file_path = os.path.join(settings.EMAIL_FILE_PATH, 
                                f"{int(time.time())}-{threading.get_ident()}.log")
        
        with open(file_path, 'w') as f:
            f.write(f"From: {message.from_email}\n")
            f.write(f"To: {', '.join(message.to)}\n")
            f.write(f"Subject: {message.subject}\n")
            f.write(f"Body:\n{message.body}\n")
            f.write("-" * 50 + "\n")
    
    def _try_gmail_forward(self, message):
        """Try to forward email via Gmail SMTP"""
        try:
            # Gmail SMTP settings (you can add your Gmail credentials here)
            gmail_user = os.environ.get('GMAIL_FORWARD_USER', '')
            gmail_password = os.environ.get('GMAIL_FORWARD_PASSWORD', '')
            
            if not gmail_user or not gmail_password:
                return False
            
            # Create MIME message
            msg = MIMEMultipart()
            msg['From'] = gmail_user
            msg['To'] = ', '.join(message.to)
            msg['Subject'] = message.subject
            
            # Add body
            msg.attach(MIMEText(message.body, 'plain'))
            
            # Send via Gmail
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(gmail_user, gmail_password)
            
            text = msg.as_string()
            server.sendmail(gmail_user, message.to, text)
            server.quit()
            
            return True
            
        except Exception as e:
            logger.error(f"Gmail forwarding failed: {str(e)}")
            return False
