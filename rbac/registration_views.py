from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from .forms import RegistrationForm
import logging
from datetime import datetime

logger = logging.getLogger('rbac.registration')

def register_view(request):
    logger.info(f"Registration attempt started at {datetime.now()}")
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        logger.info(f"POST request received with data: {request.POST.dict()}")
        
        if form.is_valid():
            logger.info("Form validation successful")
            try:
                user = form.save()
                logger.info(f"User created successfully: {user.username}, Email: {user.email}")
                
                # Log user profile creation
                try:
                    profile = user.userprofile
                    logger.info(f"User profile created: Company: {profile.company}")
                except Exception as profile_error:
                    logger.error(f"User profile creation failed: {str(profile_error)}")
                
                # Send registration success email with password reset link
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                reset_url = f"http://{settings.PUBLIC_IP}:8000/password-reset/{uid}/{token}/"
                
                subject = 'Welcome to Customer Portal - Set Your Password'
                message = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2 style="color: #0066cc;">Welcome to Customer Portal!</h2>
    
    <p>Dear {user.first_name} {user.last_name},</p>
    
    <p>Your account has been created successfully.</p>
    
    <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <strong>Account Details:</strong><br>
        Username: <strong>{user.username}</strong><br>
        Email: <strong>{user.email}</strong><br>
        Company: <strong>{form.cleaned_data['company']}</strong>
    </div>
    
    <p>To set up your password and access the portal, please click the button below:</p>
    
    <div style="margin: 30px 0;">
        <a href="{reset_url}" style="background-color: #0066cc; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Set My Password</a>
    </div>
    
    <p>Or copy and paste this link into your browser:</p>
    <p style="background-color: #f9f9f9; padding: 10px; border-left: 3px solid #0066cc; word-break: break-all;">
        {reset_url}
    </p>
    
    <p style="color: #666; font-size: 12px; margin-top: 30px;">
        <strong>Note:</strong> This link will expire in 24 hours for security reasons.
    </p>
    
    <p>Best regards,<br>
    <strong>Customer Portal Team</strong></p>
</body>
</html>
                """
                
                logger.info(f"Attempting to send email to: {user.email}")
                
                email_sent = False
                try:
                    send_mail(
                        subject,
                        message,
                        'Gajendra.N@wepsol.com',
                        [user.email],
                        fail_silently=False,
                    )
                    logger.info(f"Email sent successfully to {user.email}")
                    email_sent = True
                    
                except Exception as email_error:
                    logger.error(f"Email sending failed: {str(email_error)}")
                
                # Show success message
                if email_sent:
                    messages.success(request, f'Registration successful! An email has been sent to {user.email} with instructions to set your password.')
                else:
                    messages.success(request, f'Registration successful! Please use this link to set your password: {reset_url}')
                    messages.warning(request, 'Email could not be sent. Please save the password reset link above.')
                
                logger.info("Registration process completed successfully")
                return redirect('login')
                
            except Exception as user_error:
                logger.error(f"User creation failed: {str(user_error)}")
                messages.error(request, f'Registration failed: {str(user_error)}')
        else:
            logger.error(f"Form validation failed: {form.errors}")
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RegistrationForm()
        logger.info("GET request - showing registration form")
    
    return render(request, 'registration/register.html', {'form': form})
