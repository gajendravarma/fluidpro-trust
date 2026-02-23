from django.db import models
from django.contrib.auth.models import User

class Company(models.Model):
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=50, unique=True)
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
