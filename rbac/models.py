from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class Company(models.Model):
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=50, unique=True)
    contact_email = models.EmailField(
        blank=True,
        help_text='Primary contact email for license renewal notifications. '
                  'If blank, all company users will be notified.'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Companies"

    def __str__(self):
        return self.name

class Role(models.Model):
    ADMIN = 'admin'
    TECHNICIAN = 'technician'
    CUSTOMER = 'customer'
    
    ROLE_CHOICES = [
        (ADMIN, 'Admin'),
        (TECHNICIAN, 'Technician'),
        (CUSTOMER, 'Customer'),
    ]
    
    name = models.CharField(max_length=50, choices=ROLE_CHOICES, unique=True)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.get_name_display()

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    mobile_number = models.CharField(max_length=15, blank=True)
    location = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.company.name if self.company else 'No Company'}"
    
    def get_role(self):
        if self.user.is_superuser:
            return 'admin'
        return self.role.name if self.role else 'technician'

class Package(models.Model):
    """Represents different software packages/tools"""
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.display_name

class UserPackageAccess(models.Model):
    """Direct user access to packages with permissions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    is_enabled = models.BooleanField(default=True)
    can_create = models.BooleanField(default=False)
    can_read = models.BooleanField(default=True)
    can_update = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_accesses')
    
    class Meta:
        unique_together = ['user', 'package']
    
    def __str__(self):
        return f"{self.user.username} - {self.package.name}"

class CompanyLicense(models.Model):
    """Store license details for each company and package"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='licenses')
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    total_licenses = models.IntegerField(default=0)
    used_licenses = models.IntegerField(default=0)
    expiry_date = models.DateField()
    license_type = models.CharField(max_length=100, default='Standard')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['company', 'package']
    
    @property
    def remaining_licenses(self):
        return max(0, self.total_licenses - self.used_licenses)
    
    @property
    def usage_percentage(self):
        if self.total_licenses > 0:
            return round((self.used_licenses / self.total_licenses) * 100, 1)
        return 0
    
    @property
    def is_expired(self):
        return timezone.now().date() > self.expiry_date
    
    def __str__(self):
        return f"{self.company.name} - {self.package.display_name}"

class LicenseConfig(models.Model):
    """Store license configuration for each service"""
    service_name = models.CharField(max_length=50, unique=True)
    total_licenses = models.IntegerField(default=0)
    license_type = models.CharField(max_length=100)
    expiry_date = models.DateField()
    alert_sent_one_month = models.BooleanField(default=False)
    alert_sent_one_week = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.service_name} - {self.total_licenses} licenses"

class TechnicianCompanyAccess(models.Model):
    """
    Controls which companies a portal technician user can see.

    Rules:
    - No rows for a technician  → unrestricted (Level-2 / global techs see everything)
    - One or more rows          → restricted to only the listed companies (inhouse techs)

    Admins and superusers are always unrestricted regardless of this table.
    Customers are always restricted to their own company via UserProfile.company.
    """
    user    = models.ForeignKey(User, on_delete=models.CASCADE,
                                related_name='company_accesses')
    company = models.ForeignKey(Company, on_delete=models.CASCADE,
                                related_name='technician_accesses')
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='granted_company_accesses')
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'company')
        verbose_name        = 'Technician Company Access'
        verbose_name_plural = 'Technician Company Accesses'

    def __str__(self):
        return f"{self.user.username} → {self.company.name}"


class PasswordResetToken(models.Model):
    """Track password reset tokens"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    def is_expired(self):
        """Check if token is expired (24 hours)"""
        return timezone.now() > self.created_at + timedelta(hours=24)

    def __str__(self):
        return f"Reset token for {self.user.username}"


class LicenseRenewalNotification(models.Model):
    """
    Track which renewal reminder emails have been sent.

    Keyed on (license, days_before, license_expiry_date) so that if the
    expiry date is extended (license renewed) the old record does NOT block
    a fresh set of reminders for the new expiry.
    """
    DAYS_CHOICES = [
        (15, '15 days before'),
        (7,  '7 days before'),
        (1,  '1 day before'),
    ]

    license = models.ForeignKey(
        'CompanyLicense', on_delete=models.CASCADE,
        related_name='renewal_notifications'
    )
    days_before = models.IntegerField(choices=DAYS_CHOICES)
    license_expiry_date = models.DateField(
        help_text='Snapshot of expiry_date when the email was sent'
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    recipients = models.TextField(
        blank=True,
        help_text='Comma-separated list of emails this notification was sent to'
    )
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    class Meta:
        unique_together = ['license', 'days_before', 'license_expiry_date']
        ordering = ['-sent_at']

    def __str__(self):
        return (
            f"{self.license} — {self.days_before}d before "
            f"{self.license_expiry_date} (sent {self.sent_at:%Y-%m-%d})"
        )
