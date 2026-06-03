#!/usr/bin/env python3
"""
Simple runner script for email data extraction
"""

import subprocess
import sys
import os

def install_requirements():
    """Install required packages"""
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'requests', 'python-dotenv'])
        print("Dependencies installed successfully")
    except subprocess.CalledProcessError:
        print("Failed to install dependencies")
        return False
    return True

def run_extractor():
    """Run the email data extractor"""
    if install_requirements():
        try:
            from email_data_extractor import EmailDataExtractor
            extractor = EmailDataExtractor()
            extractor.generate_report()
        except Exception as e:
            print(f"Error running extractor: {e}")

if __name__ == "__main__":
    run_extractor()
