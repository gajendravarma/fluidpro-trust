#!/usr/bin/env python3
"""
Email Data Extractor for Centralized Mailing System
Extracts sender and receiver email data from last 3 months using CGL app registration
"""

import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import csv
import sys
import time

load_dotenv()

class EmailDataExtractor:
    def __init__(self):
        self.tenant_id = os.getenv('CGL_TENANT_ID')
        self.client_id = os.getenv('CGL_CLIENT_ID')
        self.client_secret = os.getenv('CGL_CLIENT_SECRET')
        self.access_token = None
        
    def log(self, message):
        """Print with timestamp and flush immediately"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        sys.stdout.flush()
    
    def get_access_token(self):
        """Get access token for Microsoft Graph API"""
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
                self.log(f"❌ Token request failed: {response.status_code}")
                return False
        except Exception as e:
            self.log(f"❌ Token request error: {str(e)}")
            return False
    
    def get_users(self):
        """Get all users from the organization"""
        self.log("📋 Fetching organization users...")
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = "https://graph.microsoft.com/v1.0/users"
        
        users = []
        page = 1
        while url:
            try:
                self.log(f"   📄 Fetching users page {page}...")
                response = requests.get(url, headers=headers, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    new_users = data.get('value', [])
                    users.extend(new_users)
                    self.log(f"   ✅ Got {len(new_users)} users (total: {len(users)})")
                    url = data.get('@odata.nextLink')
                    page += 1
                else:
                    self.log(f"   ❌ Failed to fetch users: {response.status_code}")
                    break
            except Exception as e:
                self.log(f"   ❌ Error fetching users: {str(e)}")
                break
        
        self.log(f"✅ Total users found: {len(users)}")
        return users
    
    def get_user_emails(self, user_id, days_back=90):
        """Get emails for a specific user from last 3 months"""
        headers = {'Authorization': f'Bearer {self.access_token}'}
        
        # Calculate date filter for last 3 months
        start_date = (datetime.now() - timedelta(days=days_back)).isoformat() + 'Z'
        
        # Get sent emails
        sent_url = f"https://graph.microsoft.com/v1.0/users/{user_id}/mailFolders/SentItems/messages"
        sent_params = {
            '$filter': f"sentDateTime ge {start_date}",
            '$select': 'sender,toRecipients,ccRecipients,bccRecipients,sentDateTime,subject',
            '$top': 999
        }
        
        # Get received emails  
        inbox_url = f"https://graph.microsoft.com/v1.0/users/{user_id}/mailFolders/Inbox/messages"
        inbox_params = {
            '$filter': f"receivedDateTime ge {start_date}",
            '$select': 'sender,toRecipients,ccRecipients,receivedDateTime,subject',
            '$top': 999
        }
        
        emails = []
        
        # Fetch sent emails
        try:
            self.log("     📤 Fetching sent emails...")
            response = requests.get(sent_url, headers=headers, params=sent_params, timeout=30)
            if response.status_code == 200:
                sent_emails = response.json().get('value', [])
                emails.extend(sent_emails)
                self.log(f"     ✅ Got {len(sent_emails)} sent emails")
            else:
                self.log(f"     ⚠️  Sent emails failed: {response.status_code}")
        except Exception as e:
            self.log(f"     ❌ Sent emails error: {str(e)}")
            
        # Fetch received emails
        try:
            self.log("     📥 Fetching received emails...")
            response = requests.get(inbox_url, headers=headers, params=inbox_params, timeout=30)
            if response.status_code == 200:
                received_emails = response.json().get('value', [])
                emails.extend(received_emails)
                self.log(f"     ✅ Got {len(received_emails)} received emails")
            else:
                self.log(f"     ⚠️  Received emails failed: {response.status_code}")
        except Exception as e:
            self.log(f"     ❌ Received emails error: {str(e)}")
            
        return emails
    
    def extract_email_addresses(self, emails):
        """Extract unique email addresses from email data"""
        email_contacts = set()
        
        for email in emails:
            # Extract sender
            if email.get('sender') and email['sender'].get('emailAddress'):
                email_contacts.add(email['sender']['emailAddress']['address'])
            
            # Extract recipients
            for recipient_type in ['toRecipients', 'ccRecipients', 'bccRecipients']:
                recipients = email.get(recipient_type, [])
                for recipient in recipients:
                    if recipient.get('emailAddress'):
                        email_contacts.add(recipient['emailAddress']['address'])
        
        return email_contacts
    
    def filter_team_aviation_senders(self, emails):
        """Filter emails where sender is from teamaviation domain"""
        filtered_emails = []
        for email in emails:
            if email.get('sender') and email['sender'].get('emailAddress'):
                sender_email = email['sender']['emailAddress']['address']
                if 'teamaviation' in sender_email.lower():
                    filtered_emails.append(email)
        return filtered_emails
    
    def generate_report(self):
        """Generate comprehensive email communication report"""
        self.log("🚀 Starting Email Data Extraction...")
        
        if not self.get_access_token():
            self.log("❌ Failed to get access token - stopping")
            return
        
        users = self.get_users()
        if not users:
            self.log("❌ No users found - stopping")
            return
        
        all_contacts = set()
        team_aviation_contacts = set()
        communication_data = []
        
        self.log(f"\n📧 Processing {len(users)} users for email data...")
        
        for i, user in enumerate(users, 1):
            user_email = user.get('mail') or user.get('userPrincipalName', '')
            self.log(f"\n👤 [{i}/{len(users)}] Processing: {user_email}")
            
            emails = self.get_user_emails(user['id'])
            self.log(f"   📊 Total emails found: {len(emails)}")
            
            # All email contacts
            contacts = self.extract_email_addresses(emails)
            all_contacts.update(contacts)
            self.log(f"   👥 Unique contacts extracted: {len(contacts)}")
            
            # Team Aviation specific
            team_aviation_emails = self.filter_team_aviation_senders(emails)
            aviation_contacts = self.extract_email_addresses(team_aviation_emails)
            team_aviation_contacts.update(aviation_contacts)
            self.log(f"   ✈️  Team Aviation emails: {len(team_aviation_emails)}")
            
            # Communication summary
            communication_data.append({
                'user': user_email,
                'total_emails': len(emails),
                'team_aviation_emails': len(team_aviation_emails),
                'unique_contacts': len(contacts)
            })
            
            progress = (i / len(users)) * 100
            self.log(f"   📈 Overall Progress: {progress:.1f}% ({i}/{len(users)} users)")
            self.log(f"   📊 Running totals - All contacts: {len(all_contacts)}, Aviation: {len(team_aviation_contacts)}")
        
        # Generate reports
        self.log(f"\n💾 Generating CSV reports...")
        self.save_contact_list(all_contacts, 'all_customer_contacts.csv')
        self.save_contact_list(team_aviation_contacts, 'team_aviation_contacts.csv')
        self.save_communication_summary(communication_data, 'communication_summary.csv')
        
        self.log(f"\n🎉 EXTRACTION COMPLETE!")
        self.log(f"📊 Final Results:")
        self.log(f"   • Total unique contacts: {len(all_contacts)}")
        self.log(f"   • Team Aviation contacts: {len(team_aviation_contacts)}")
        self.log(f"   • Users processed: {len(users)}")
        self.log(f"   • Files created: all_customer_contacts.csv, team_aviation_contacts.csv, communication_summary.csv")
    
    def save_contact_list(self, contacts, filename):
        """Save contact list to CSV"""
        self.log(f"💾 Saving {len(contacts)} contacts to {filename}...")
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Email Address', 'Domain'])
            
            for email in sorted(contacts):
                domain = email.split('@')[1] if '@' in email else ''
                writer.writerow([email, domain])
        
        self.log(f"✅ Saved {filename}")
    
    def save_communication_summary(self, data, filename):
        """Save communication summary to CSV"""
        self.log(f"💾 Saving communication summary to {filename}...")
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['user', 'total_emails', 'team_aviation_emails', 'unique_contacts']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for row in data:
                writer.writerow(row)
        
        self.log(f"✅ Saved {filename}")

if __name__ == "__main__":
    extractor = EmailDataExtractor()
    extractor.generate_report()
