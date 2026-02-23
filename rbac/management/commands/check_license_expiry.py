from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime, timedelta
from rbac.models import LicenseConfig


class Command(BaseCommand):
    help = 'Check license expiry and send alerts'

    def handle(self, *args, **kwargs):
        today = datetime.now().date()
        one_month_later = today + timedelta(days=30)
        one_week_later = today + timedelta(days=7)
        
        licenses = LicenseConfig.objects.all()
        
        for license in licenses:
            # Check for 1 month alert
            if license.expiry_date <= one_month_later and not license.alert_sent_one_month:
                days_left = (license.expiry_date - today).days
                self.send_alert_email(license, days_left, 'one_month')
                license.alert_sent_one_month = True
                license.save()
                self.stdout.write(self.style.SUCCESS(
                    f'Sent 1-month alert for {license.service_name}'
                ))
            
            # Check for 1 week alert
            if license.expiry_date <= one_week_later and not license.alert_sent_one_week:
                days_left = (license.expiry_date - today).days
                self.send_alert_email(license, days_left, 'one_week')
                license.alert_sent_one_week = True
                license.save()
                self.stdout.write(self.style.SUCCESS(
                    f'Sent 1-week alert for {license.service_name}'
                ))

    def send_alert_email(self, license, days_left, alert_type):
        """Send email alert for license expiry"""
        subject = f'License Expiry Alert: {license.service_name}'
        
        if days_left <= 0:
            message = f'''
License Expired!

Service: {license.service_name}
License Type: {license.license_type}
Total Licenses: {license.total_licenses}
Expiry Date: {license.expiry_date}

The license has already expired. Please renew immediately.
'''
        else:
            message = f'''
License Expiry Warning

Service: {license.service_name}
License Type: {license.license_type}
Total Licenses: {license.total_licenses}
Expiry Date: {license.expiry_date}
Days Remaining: {days_left}

Please renew the license before it expires.
'''
        
        # Get admin emails
        admin_emails = getattr(settings, 'LICENSE_ALERT_EMAILS', ['admin@example.com'])
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                admin_emails,
                fail_silently=False,
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to send email: {str(e)}'))
