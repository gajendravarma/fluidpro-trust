from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from .forms import RegistrationForm
from .models import Company
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
                reset_url = f"http://{settings.PUBLIC_IP}/reset-password/{uid}/{token}/"
                
                subject = 'Welcome to Customer Portal - Set Your Password'
                company_name = form.cleaned_data['company']
                message = (
"<html>"
"<body style='font-family:Arial,sans-serif;line-height:1.6;color:#333;max-width:600px;margin:0 auto;padding:20px;'>"
"<div style='background:linear-gradient(135deg,#4e73df,#224abe);padding:30px;border-radius:10px 10px 0 0;text-align:center;'>"
"<h2 style='color:white;margin:0;font-size:24px;'>Welcome to FluidTrust Portal</h2>"
"</div>"
"<div style='background:#ffffff;padding:30px;border:1px solid #e0e0e0;'>"
f"<p style='font-size:16px;'>Dear <strong>{user.first_name} {user.last_name}</strong>,</p>"
"<p>Your account has been created successfully. Please use the button below to set your password and access the portal.</p>"
"<table style='background:#f8f9fc;border-radius:8px;padding:20px;width:100%;margin:20px 0;border-collapse:collapse;'>"
"<tr><td style='padding:6px 0;color:#666;'>Username</td>"
f"<td style='padding:6px 0;font-weight:bold;'>{user.username}</td></tr>"
"<tr><td style='padding:6px 0;color:#666;'>Email</td>"
f"<td style='padding:6px 0;font-weight:bold;'>{user.email}</td></tr>"
"<tr><td style='padding:6px 0;color:#666;'>Company</td>"
f"<td style='padding:6px 0;font-weight:bold;'>{company_name}</td></tr>"
"</table>"
"<div style='text-align:center;margin:30px 0;'>"
f"<a href='{reset_url}' style='background-color:#4e73df;color:white;padding:14px 36px;text-decoration:none;border-radius:8px;font-size:16px;font-weight:bold;display:inline-block;'>Set My Password</a>"
"</div>"
"<p style='color:#666;font-size:13px;'>Or copy this link into your browser:</p>"
f"<p style='background:#f9f9f9;padding:10px 15px;border-left:4px solid #4e73df;border-radius:4px;font-size:12px;word-break:break-all;color:#333;'>{reset_url}</p>"
"<p style='color:#999;font-size:12px;margin-top:20px;'>This link expires in <strong>24 hours</strong>. If you did not request this, please ignore this email.</p>"
"</div>"
"<div style='background:#f8f9fc;padding:15px;border-radius:0 0 10px 10px;text-align:center;font-size:12px;color:#999;'>"
"FluidTrust Portal &mdash; Customer Portal Team"
"</div>"
"</body></html>"
                )
                
                logger.info(f"Attempting to send email to: {user.email}")
                
                email_sent = False
                try:
                    send_mail(
                        subject,
                        f"Welcome {user.first_name}! Please set your password: {reset_url}",
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                        fail_silently=False,
                        html_message=message,
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
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.replace('_', ' ').title()}: {error}" if field != '__all__' else error)
    else:
        form = RegistrationForm()
        logger.info("GET request - showing registration form")

    return render(request, 'registration/register.html', {
        'form': form,
        'existing_companies': Company.objects.all().order_by('name'),
    })
