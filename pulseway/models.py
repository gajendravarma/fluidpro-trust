from django.db import models
from django.contrib.auth.models import User
from rbac.models import Company


class PulsewayDevice(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='pulseway_devices')
    device_id = models.CharField(max_length=100, unique=True)
    device_name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=[('online', 'Online'), ('offline', 'Offline')], default='offline')
    last_seen = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.device_name} ({self.company.name})"


class PulsewayPatchReport(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='pulseway_patches')
    device = models.ForeignKey(PulsewayDevice, on_delete=models.CASCADE)
    patch_name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=[('installed', 'Installed'), ('pending', 'Pending'), ('failed', 'Failed')])
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.patch_name} - {self.status}"


class PulsewayAction(models.Model):
    ACTION_TYPES = [
        ('script', 'Script Execution'),
        ('patch', 'Patch Installation'),
        ('reboot', 'Device Reboot'),
        ('site_create', 'Site Creation'),
        ('site_update', 'Site Update'),
        ('site_delete', 'Site Deletion'),
        ('group_create', 'Group Creation'),
        ('group_update', 'Group Update'),
        ('group_delete', 'Group Deletion'),
        ('automation_create', 'Automation Task Creation'),
        ('automation_run', 'Automation Task Execution'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    target_id = models.CharField(max_length=100)  # Device ID, Site ID, etc.
    target_name = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    result = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action_type} on {self.target_name} by {self.user.username}"
