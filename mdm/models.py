from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from rbac.models import Company

class MdmCustomer(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='mdm_customer')
    customer_id = models.CharField(max_length=10, unique=True)
    device_count = models.IntegerField(default=0)
    no_of_devices = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, default='active')
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.company.name} ({self.customer_id})"

class MdmUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    mdm_customer = models.ForeignKey(MdmCustomer, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=50, blank=True)
    department = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=50, default='user')
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.user.username} - {self.mdm_customer.company.name}"

class Device(models.Model):
    DEVICE_TYPES = [
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('windows', 'Windows'),
        ('laptop', 'Laptop'),
    ]
    
    STATUS_CHOICES = [
        ('managed', 'Managed'),
        ('staged', 'Staged'),
        ('enrollment_pending', 'Enrollment Pending'),
        ('retired', 'Retired'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    
    device_id = models.CharField(max_length=100, unique=True)
    mdm_customer = models.ForeignKey(MdmCustomer, on_delete=models.CASCADE)
    user = models.ForeignKey(MdmUser, on_delete=models.SET_NULL, null=True, blank=True)
    device_name = models.CharField(max_length=200)
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES)
    platform = models.CharField(max_length=50, blank=True)
    model = models.CharField(max_length=100, blank=True)
    manufacturer = models.CharField(max_length=100, blank=True)
    os_version = models.CharField(max_length=50, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    imei = models.CharField(max_length=20, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='managed')
    enrollment_type = models.CharField(max_length=100, blank=True)
    enrollment_time = models.DateTimeField(null=True, blank=True)
    last_contact_time = models.DateTimeField(null=True, blank=True)
    associated_groups = models.IntegerField(default=0)
    profile_count = models.IntegerField(default=0)
    apps_count = models.IntegerField(default=0)
    is_supervised = models.BooleanField(default=False)
    is_encrypted = models.BooleanField(default=False)
    battery_level = models.IntegerField(null=True, blank=True)
    storage_total = models.BigIntegerField(null=True, blank=True)
    storage_used = models.BigIntegerField(null=True, blank=True)
    free_space_gb = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    user_email = models.EmailField(blank=True)
    username = models.CharField(max_length=200, blank=True)
    display_name = models.CharField(max_length=200, blank=True)
    location_lat = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    location_lng = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    location_updated = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    enrolled_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.device_name} - {self.mdm_customer.company.name}"
    
    @property
    def storage_used_percent(self):
        if self.storage_total and self.storage_used:
            return round((self.storage_used / self.storage_total) * 100, 2)
        return 0

class InstalledApp(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    app_name = models.CharField(max_length=200)
    package_name = models.CharField(max_length=200)
    version = models.CharField(max_length=50, blank=True)
    size = models.BigIntegerField(null=True, blank=True)
    is_system_app = models.BooleanField(default=False)
    is_managed = models.BooleanField(default=False)
    install_date = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['device', 'package_name']
    
    def __str__(self):
        return f"{self.app_name} on {self.device.device_name}"

class SecurityEvent(models.Model):
    EVENT_TYPES = [
        ('jailbreak', 'Jailbreak/Root Detected'),
        ('malware', 'Malware Detected'),
        ('policy_violation', 'Policy Violation'),
        ('unauthorized_app', 'Unauthorized App'),
        ('location_violation', 'Location Violation'),
        ('failed_login', 'Failed Login Attempt'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS)
    description = models.TextField()
    details = models.JSONField(default=dict)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.event_type} - {self.device.device_name}"

class DeviceGroup(models.Model):
    name = models.CharField(max_length=200)
    mdm_customer = models.ForeignKey(MdmCustomer, on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    devices = models.ManyToManyField(Device, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.name} - {self.mdm_customer.company.name}"

class AppPolicy(models.Model):
    POLICY_TYPES = [
        ('allow', 'Allow'),
        ('block', 'Block'),
        ('required', 'Required'),
    ]
    
    mdm_customer = models.ForeignKey(MdmCustomer, on_delete=models.CASCADE)
    app_name = models.CharField(max_length=200)
    package_name = models.CharField(max_length=200)
    policy_type = models.CharField(max_length=20, choices=POLICY_TYPES)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ['mdm_customer', 'package_name']
    
    def __str__(self):
        return f"{self.app_name} - {self.policy_type}"

class Profile(models.Model):
    profile_id = models.CharField(max_length=100, unique=True)
    mdm_customer = models.ForeignKey(MdmCustomer, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    profile_type = models.CharField(max_length=50, default='configuration')
    status = models.CharField(max_length=20, default='draft')
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.name} - {self.mdm_customer.company.name}"

class EnrollmentSettings(models.Model):
    mdm_customer = models.OneToOneField(MdmCustomer, on_delete=models.CASCADE)
    allow_personal_apps = models.BooleanField(default=True)
    require_passcode = models.BooleanField(default=True)
    auto_enrollment = models.BooleanField(default=False)
    enrollment_url = models.URLField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Enrollment Settings - {self.mdm_customer.company.name}"
