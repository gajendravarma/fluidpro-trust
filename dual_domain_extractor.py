#!/usr/bin/env python3
"""
12-Month Email Extractor for Team Aviation and Flycraft domains
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import csv
import sys

load_dotenv()

class DualDomainExtractor:
    def __init__(self):
        self.tenant_id = os.getenv('CGL_TENANT_ID')
        self.client_id = os.getenv('CGL_CLIENT_ID')
        self.client_secret = os.getenv('CGL_CLIENT_SECRET')
        self.access_token = None
        
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        sys.stdout.flush()
    
    def get_access_token(self):
        self.log("🔐 Getting access token...")
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': 'https://graph.microsoft.com/.default',
            'grant_type': 'client_credentials'
        }
        
        try:
            response = requests.post(url, data=data, timeout=30)
            if response.status_code == 200:
                self.access_token = response.json()['access_token']
                self.log("✅ Access token obtained")
                return True
            else:
                self.log(f"❌ Token failed: {response.status_code}")
                return False
        except Exception as e:
            self.log(f"❌ Token error: {str(e)}")
            return False
    
    def get_domain_users(self, domain_keyword):
        self.log(f"📋 Fetching all users and filtering for {domain_keyword}...")
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = "https://graph.microsoft.com/v1.0/users"
        
        domain_users = []
        page = 1
        
        while url:
            try:
                self.log(f"   📄 Fetching page {page}...")
                response = requests.get(url, headers=headers, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    users = data.get('value', [])
                    
                    for user in users:
                        email = user.get('mail') or user.get('userPrincipalName', '')
                        if domain_keyword.lower() in email.lower():
                            domain_users.append(user)
                    
                    url = data.get('@odata.nextLink')
                    page += 1
                else:
                    self.log(f"❌ Failed to fetch users: {response.status_code}")
                    break
            except Exception as e:
                self.log(f"❌ Error: {str(e)}")
                break
        
        self.log(f"✅ Found {len(domain_users)} {domain_keyword} users")
        return domain_users
    
    def get_user_contacts(self, user_id):
        headers = {'Authorization': f'Bearer {self.access_token}'}
        start_date = (datetime.now() - timedelta(days=365)).isoformat() + 'Z'  # 12 months
        
        # Get sent emails
        sent_url = f"https://graph.microsoft.com/v1.0/users/{user_id}/mailFolders/SentItems/messages"
        sent_params = {
            '$filter': f"sentDateTime ge {start_date}",
            '$select': 'sender,toRecipients,ccRecipients',
            '$top': 999
        }
        
        # Get received emails
        inbox_url = f"https://graph.microsoft.com/v1.0/users/{user_id}/mailFolders/Inbox/messages"
        inbox_params = {
            '$filter': f"receivedDateTime ge {start_date}",
            '$select': 'sender,toRecipients,ccRecipients',
            '$top': 999
        }
        
        contacts = set()
        
        # Process sent emails (get recipients)
        try:
            response = requests.get(sent_url, headers=headers, params=sent_params, timeout=30)
            if response.status_code == 200:
                emails = response.json().get('value', [])
                for email in emails:
                    for recipient_type in ['toRecipients', 'ccRecipients']:
                        recipients = email.get(recipient_type, [])
                        for recipient in recipients:
                            if recipient.get('emailAddress'):
                                contacts.add(recipient['emailAddress']['address'])
        except Exception as e:
            self.log(f"     ❌ Sent emails error: {str(e)}")
        
        # Process received emails (get senders)
        try:
            response = requests.get(inbox_url, headers=headers, params=inbox_params, timeout=30)
            if response.status_code == 200:
                emails = response.json().get('value', [])
                for email in emails:
                    if email.get('sender') and email['sender'].get('emailAddress'):
                        contacts.add(email['sender']['emailAddress']['address'])
        except Exception as e:
            self.log(f"     ❌ Received emails error: {str(e)}")
        
        return contacts
    
    def save_contacts(self, contacts, filename):
        self.log(f"💾 Saving {len(contacts)} sender+receiver contacts to {filename}...")
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Email Address', 'Domain', 'Contact Type'])
            
            for email in sorted(contacts):
                domain = email.split('@')[1] if '@' in email else ''
                writer.writerow([email, domain, 'Sender/Receiver'])
        
        self.log(f"✅ Saved {filename}")
    
    def extract_domain_data(self, domain, filename):
        self.log(f"\n🚀 Starting {domain} extraction (12 months)...")
        
        users = self.get_domain_users(domain)
        if not users:
            self.log(f"❌ No {domain} users found")
            return 0
        
        all_contacts = set()
        
        for i, user in enumerate(users, 1):
            user_email = user.get('mail', '')
            self.log(f"📧 [{i}/{len(users)}] Processing: {user_email}")
            
            contacts = self.get_user_contacts(user['id'])
            all_contacts.update(contacts)
            
            self.log(f"   ✅ Found {len(contacts)} contacts | Total: {len(all_contacts)}")
            progress = (i / len(users)) * 100
            self.log(f"   📊 Progress: {progress:.1f}%")
        
        self.save_contacts(all_contacts, filename)
        return len(all_contacts)
    
    def generate_reports(self):
        self.log("🚀 Starting Dual Domain Email Extraction (12 months)...")
        
        if not self.get_access_token():
            return
        
        # Extract Team Aviation data
        teamaviation_count = self.extract_domain_data('teamaviation', 'teamaviation12monthdata.csv')
        
        # Extract Flycraft data
        flycraft_count = self.extract_domain_data('flycraft', 'flycraft12monthdata.csv')
        
        self.log(f"\n🎉 ALL EXTRACTIONS COMPLETE!")
        self.log(f"📊 Team Aviation: {teamaviation_count} contacts")
        self.log(f"📊 Flycraft: {flycraft_count} contacts")
        self.log(f"📁 Files: teamaviation12monthdata.csv, flycraft12monthdata.csv")

if __name__ == "__main__":
    extractor = DualDomainExtractor()
    extractor.generate_reports()
