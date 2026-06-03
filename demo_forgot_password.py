#!/usr/bin/env python3

import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/home/devops-machine/Fluidtrust-project/customer_portal')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from rbac.models import PasswordResetToken

def demo_forgot_password():
    """Demonstrate the complete forgot password flow"""
    
    print("🔐 FluidTrust Customer Portal - Forgot Password Demo")
    print("=" * 60)
    
    # Create or get demo user
    demo_email = "demo@fluidtrust.com"
    demo_username = "demouser"
    
    try:
        user = User.objects.get(email=demo_email)
        print(f"✓ Using existing demo user: {user.username} ({user.email})")
    except User.DoesNotExist:
        user = User.objects.create_user(
            username=demo_username,
            email=demo_email,
            password="oldpassword123",
            first_name="Demo",
            last_name="User"
        )
        print(f"✓ Created demo user: {user.username} ({user.email})")
    
    # Generate password reset token
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    
    # Save token to database
    reset_token = PasswordResetToken.objects.create(user=user, token=token)
    
    # Generate reset link
    reset_link = f"http://54.210.61.83/reset-password/{uid}/{token}/"
    
    print(f"\n📧 Password Reset Email Content:")
    print("-" * 40)
    print(f"To: {user.email}")
    print(f"Subject: Password Reset - FluidTrust Customer Portal")
    print(f"\nHello {user.first_name},")
    print(f"\nYou have requested to reset your password for FluidTrust Customer Portal.")
    print(f"\nReset Link: {reset_link}")
    print(f"\nThis link will expire in 24 hours for security reasons.")
    
    print(f"\n🔗 Reset Password URLs:")
    print("-" * 40)
    print(f"Forgot Password Page: http://54.210.61.83/forgot-password/")
    print(f"Reset Password Link: {reset_link}")
    
    print(f"\n📊 Database Records:")
    print("-" * 40)
    print(f"User ID: {user.id}")
    print(f"Username: {user.username}")
    print(f"Email: {user.email}")
    print(f"Reset Token ID: {reset_token.id}")
    print(f"Token Created: {reset_token.created_at}")
    print(f"Token Used: {reset_token.used}")
    print(f"Token Expired: {reset_token.is_expired()}")
    
    print(f"\n🎯 How to Test:")
    print("-" * 40)
    print("1. Open browser and go to: http://54.210.61.83/login/")
    print("2. Click 'Forgot Password?' link")
    print(f"3. Enter email: {demo_email}")
    print("4. Check email for reset link (or use the link above)")
    print("5. Click reset link and set new password")
    print("6. Login with new password")
    
    print(f"\n✅ Forgot Password System Features:")
    print("-" * 40)
    print("• Beautiful, responsive UI matching login page design")
    print("• HTML email with professional styling")
    print("• Secure token-based password reset")
    print("• 24-hour token expiration")
    print("• Token usage tracking to prevent reuse")
    print("• Microsoft Graph API integration for email sending")
    print("• Comprehensive error handling and logging")
    print("• Database cleanup management command")
    
    return reset_link

if __name__ == "__main__":
    reset_link = demo_forgot_password()
    print(f"\n🚀 Demo completed! Test the functionality at: http://54.210.61.83/forgot-password/")
