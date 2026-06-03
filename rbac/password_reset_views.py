from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import login
from django.contrib.auth.forms import SetPasswordForm
from django.template.loader import render_to_string
from .models import PasswordResetToken
import logging

logger = logging.getLogger('rbac.registration')

def forgot_password(request):
    """Handle forgot password request"""
    if request.method == 'POST':
        email = request.POST.get('email')
        
        try:
            user = User.objects.get(email=email)
            
            # Generate password reset token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(str(user.pk)))
            
            # Debug logging
            logger.info(f"Debug - User PK: {user.pk}, UID: {uid}, Token: {token}")
            
            # Save token to database for tracking
            PasswordResetToken.objects.create(user=user, token=token)
            
            # Create reset link
            reset_link = f"http://{settings.PUBLIC_IP}/reset-password/{uid}/{token}/"
            print(f"DEBUG: User PK={user.pk}, UID={uid}, Token={token}")
            print(f"DEBUG: Generated reset link: {reset_link}")
            logger.info(f"Debug - Generated reset link: {reset_link}")
            
            # Create HTML email content
            display_name = user.get_full_name() or user.username
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Password Reset — FluidTrust Portal</title>
</head>
<body style="margin:0;padding:0;background:#f4f6fb;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6fb;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#4e73df 0%,#224abe 100%);padding:40px 40px 32px;text-align:center;">
            <div style="width:64px;height:64px;background:rgba(255,255,255,0.18);border:2px solid rgba(255,255,255,0.35);border-radius:50%;display:inline-flex;align-items:center;justify-content:center;margin-bottom:16px;">
              <span style="font-size:28px;">🔐</span>
            </div>
            <h1 style="margin:0 0 6px;color:#ffffff;font-size:24px;font-weight:700;letter-spacing:-0.3px;">Password Reset Request</h1>
            <p style="margin:0;color:rgba(255,255,255,0.85);font-size:14px;">FluidTrust Customer Portal</p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:40px 40px 32px;">
            <p style="margin:0 0 20px;font-size:15px;color:#374151;line-height:1.6;">
              Hello <strong>{display_name}</strong>,
            </p>
            <p style="margin:0 0 20px;font-size:15px;color:#374151;line-height:1.6;">
              We received a request to reset the password for your FluidTrust Customer Portal account.
              Click the button below to choose a new password.
            </p>

            <!-- CTA Button -->
            <table width="100%" cellpadding="0" cellspacing="0" style="margin:32px 0;">
              <tr><td align="center">
                <a href="{reset_link}"
                   style="display:inline-block;background:linear-gradient(135deg,#4e73df,#224abe);color:#ffffff;text-decoration:none;
                          padding:14px 40px;border-radius:8px;font-size:15px;font-weight:600;letter-spacing:0.3px;
                          box-shadow:0 4px 14px rgba(78,115,223,0.4);">
                  Reset My Password →
                </a>
              </td></tr>
            </table>

            <p style="margin:0 0 12px;font-size:13px;color:#6b7280;">
              If the button doesn't work, copy and paste this link into your browser:
            </p>
            <div style="background:#f3f4f6;border:1px solid #e5e7eb;border-radius:8px;padding:12px 16px;
                        font-size:12px;color:#4b5563;word-break:break-all;font-family:monospace;">
              {reset_link}
            </div>

            <!-- Warning box -->
            <div style="background:#fffbeb;border-left:4px solid #f59e0b;border-radius:0 8px 8px 0;padding:14px 16px;margin:28px 0 0;">
              <p style="margin:0;font-size:13px;color:#92400e;line-height:1.5;">
                <strong>⏱ This link expires in 24 hours.</strong><br>
                If you did not request a password reset, you can safely ignore this email —
                your password will remain unchanged.
              </p>
            </div>
          </td>
        </tr>

        <!-- Divider -->
        <tr><td style="padding:0 40px;"><hr style="border:none;border-top:1px solid #e5e7eb;margin:0;"></td></tr>

        <!-- Footer -->
        <tr>
          <td style="padding:24px 40px 32px;text-align:center;">
            <p style="margin:0 0 4px;font-size:12px;color:#9ca3af;">
              This is an automated security email from <strong>FluidTrust Customer Portal</strong>.
            </p>
            <p style="margin:0;font-size:12px;color:#9ca3af;">
              Please do not reply to this message. For support, contact your administrator.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""
            
            # Create plain text version
            plain_text = f"""
Hello {user.first_name or user.username},

You have requested to reset your password for FluidTrust Customer Portal.

Click the link below to reset your password:
{reset_link}

This link will expire in 24 hours for security reasons.

If you did not request this password reset, please ignore this email.

Best regards,
FluidTrust Support Team
            """
            
            # Send email with both HTML and plain text
            subject = "Password Reset - FluidTrust Customer Portal"
            msg = EmailMultiAlternatives(subject, plain_text, settings.DEFAULT_FROM_EMAIL, [email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            messages.success(request, 'Password reset link has been sent to your email address.')
            logger.info(f"Password reset email sent to {email}")
            
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email address.')
            logger.warning(f"Password reset attempted for non-existent email: {email}")
        except Exception as e:
            messages.error(request, 'Failed to send password reset email. Please try again.')
            logger.error(f"Error sending password reset email: {str(e)}")
        
        return redirect('forgot_password')
    
    return render(request, 'registration/forgot_password.html')

def reset_password(request, uidb64, token):
    """Handle password reset with token"""
    print(f"DEBUG: reset_password called with uidb64={uidb64}, token={token}")
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        print(f"DEBUG: Decoded UID={uid}")
        user = User.objects.get(pk=int(uid))
        print(f"DEBUG: Found user={user.username}")
    except (TypeError, ValueError, OverflowError, User.DoesNotExist) as e:
        print(f"DEBUG: Error finding user: {e}")
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        # Check if token exists in database and is not used
        try:
            reset_token = PasswordResetToken.objects.get(user=user, token=token, used=False)
            if reset_token.is_expired():
                messages.error(request, 'The password reset link has expired. Please request a new one.')
                return redirect('forgot_password')
        except PasswordResetToken.DoesNotExist:
            messages.error(request, 'Invalid password reset link.')
            return redirect('forgot_password')
        
        if request.method == 'POST':
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                
                # Mark token as used
                reset_token.used = True
                reset_token.save()
                
                messages.success(request, 'Your password has been reset successfully. You can now login with your new password.')
                logger.info(f"Password reset completed for user: {user.username}")
                return redirect('login')
        else:
            form = SetPasswordForm(user)
        
        return render(request, 'registration/reset_password.html', {'form': form})
    else:
        messages.error(request, 'The password reset link is invalid or has expired.')
        return redirect('forgot_password')
