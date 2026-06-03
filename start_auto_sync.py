#!/usr/bin/env python3

import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/home/devops-machine/Fluidtrust-project/customer_portal')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from tickets.auto_sync import auto_sync

def start_auto_sync():
    """Start the auto-sync service"""
    print("Starting auto-sync service...")
    auto_sync.start()
    print("Auto-sync service started! Syncing every 5 minutes.")
    print("Press Ctrl+C to stop.")
    
    try:
        import time
        while True:
            time.sleep(60)  # Keep script running
    except KeyboardInterrupt:
        print("\nStopping auto-sync service...")
        auto_sync.stop()
        print("Auto-sync service stopped.")

if __name__ == "__main__":
    start_auto_sync()
