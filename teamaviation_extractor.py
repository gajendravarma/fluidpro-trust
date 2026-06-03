#!/usr/bin/env python3
"""
Team Aviation Email Extractor - Simplified version for @teamaviation.in domain only
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import csv
import sys

load_dotenv()

class TeamAviationExtractor:
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
    
    def get_teamaviation_users(self):
        self.log("📋 Fetching all users and filtering for @teamaviation.in...")
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = "https://graph.microsoft.com/v1.0/users"
        
        all_users = []
        teamaviation_users = []
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                all_users = response.json().get('value', [])
                self.log(f"📄 Got {len(all_users)} total users")
                
                # Filter for teamaviation domain
                for user in all_users:
                    email = user.get('mail') or user.get('userPrincipalName', '')
                    if '@teamaviation.in' in email.lower():
                        teamaviation_users.append(user)
                
                self.log(f"✅ Found {len(teamaviation_users)} @teamaviation.in users")
            else:
                self.log(f"❌ Failed to fetch users: {response.status_code}")
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
        
        return teamaviation_users
    
    def get_user_contacts(self, user_id):
        headers = {'Authorization': f'Bearer {self.access_token}'}
        start_date = (datetime.now() - timedelta(days=180)).isoformat() + 'Z'  # 6 months
        
        # Get sent emails only (faster)
        url = f"https://graph.microsoft.com/v1.0/users/{user_id}/mailFolders/SentItems/messages"
        params = {
            '$filter': f"sentDateTime ge {start_date}",
            '$select': 'toRecipients,ccRecipients',
            '$top': 999
        }
        
        contacts = set()
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            if response.status_code == 200:
                emails = response.json().get('value', [])
                for email in emails:
                    for recipient_type in ['toRecipients', 'ccRecipients']:
                        recipients = email.get(recipient_type, [])
                        for recipient in recipients:
                            if recipient.get('emailAddress'):
                                contacts.add(recipient['emailAddress']['address'])
        except Exception as e:
            self.log(f"     ❌ Error: {str(e)}")
        
        return contacts
    
    def generate_report(self):
        self.log("🚀 Starting Team Aviation Email Extraction (6 months)...")
        
        if not self.get_access_token():
            return
        
        users = self.get_teamaviation_users()
        if not users:
            self.log("❌ No @teamaviation.in users found")
            return
        
        all_contacts = set()
        
        for i, user in enumerate(users, 1):
            user_email = user.get('mail', '')
            self.log(f"📧 [{i}/{len(users)}] Processing: {user_email}")
            
            contacts = self.get_user_contacts(user['id'])
            all_contacts.update(contacts)
            
            self.log(f"   ✅ Found {len(contacts)} contacts | Total: {len(all_contacts)}")
            progress = (i / len(users)) * 100
            self.log(f"   📊 Progress: {progress:.1f}%")
        
        # Save report
        self.log("💾 Saving report...")
        with open('teamaviation_contacts_6months.csv', 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Email Address', 'Domain'])
            
            for email in sorted(all_contacts):
                domain = email.split('@')[1] if '@' in email else ''
                writer.writerow([email, domain])
        
        self.log(f"🎉 COMPLETE! {len(all_contacts)} contacts saved to teamaviation_contacts_6months.csv")

if __name__ == "__main__":
    extractor = TeamAviationExtractor()
    extractor.generate_report()
