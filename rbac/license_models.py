from django.db import models
from django.utils import timezone
from rbac.models import Company, Package

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
