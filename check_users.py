#!/usr/bin/env python3
"""
Check all users in the organization to see actual user counts
"""

import os
import requests
from dotenv import load_dotenv
import sys

load_dotenv()

def log(message):
    print(f"{message}")
    sys.stdout.flush()

def get_access_token():
    tenant_id = os.getenv('CGL_TENANT_ID')
    client_id = os.getenv('CGL_CLIENT_ID')
    client_secret = os.getenv('CGL_CLIENT_SECRET')
    
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    
    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'https://graph.microsoft.com/.default',
        'grant_type': 'client_credentials'
    }
    
    response = requests.post(url, data=data, timeout=30)
    if response.status_code == 200:
        return response.json()['access_token']
    return None

def get_all_users():
    token = get_access_token()
    if not token:
        return []
    
    headers = {'Authorization': f'Bearer {token}'}
    url = "https://graph.microsoft.com/v1.0/users"
    
    all_users = []
    page = 1
    
    while url:
        log(f"Fetching page {page}...")
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            users = data.get('value', [])
            all_users.extend(users)
            url = data.get('@odata.nextLink')
            page += 1
        else:
            break
    
    return all_users

if __name__ == "__main__":
    log("🔍 Checking all users in organization...")
    users = get_all_users()
    
    teamaviation_count = 0
    flycraft_count = 0
    other_count = 0
    
    log(f"\n📊 Analyzing {len(users)} total users:")
    
    for user in users:
        email = user.get('mail') or user.get('userPrincipalName', '')
        if 'teamaviation' in email.lower():
            teamaviation_count += 1
            log(f"✈️  Team Aviation: {email}")
        elif 'flycraft' in email.lower():
            flycraft_count += 1
            log(f"🛩️  Flycraft: {email}")
        else:
            other_count += 1
    
    log(f"\n📈 Summary:")
    log(f"Team Aviation users: {teamaviation_count}")
    log(f"Flycraft users: {flycraft_count}")
    log(f"Other users: {other_count}")
    log(f"Total users: {len(users)}")
