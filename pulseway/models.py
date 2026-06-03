from django.db import models
from django.contrib.auth.models import User
from rbac.models import Company


class PulsewayDevice(models.Model):
    device_id = models.CharField(max_length=100, unique=True)
    device_name = models.CharField(max_length=200)
    organization_name = models.CharField(max_length=200, blank=True)
    site_name = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, default='offline')  # online/offline
    uptime = models.CharField(max_length=100, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    operating_system = models.CharField(max_length=100, blank=True)
    ip_address = models.CharField(max_length=50, blank=True)
    mac_address = models.CharField(max_length=50, blank=True)
    cpu_usage = models.FloatField(null=True, blank=True)
    memory_usage = models.FloatField(null=True, blank=True)
    disk_usage = models.FloatField(null=True, blank=True)
    pending_patches = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.device_name} ({self.organization_name})"

    @property
    def is_online(self):
        return self.status.lower() == 'online'


class PulsewayOrganization(models.Model):
    org_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    device_count = models.IntegerField(default=0)
    online_devices = models.IntegerField(default=0)
    offline_devices = models.IntegerField(default=0)
    pending_patches = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name


class PulsewayPatch(models.Model):
    device = models.ForeignKey(PulsewayDevice, on_delete=models.CASCADE, related_name='patches')
    patch_id = models.CharField(max_length=100)
    patch_name = models.CharField(max_length=200)
    status = models.CharField(max_length=50)  # pending, installed, failed
    severity = models.CharField(max_length=50, blank=True)
    category = models.CharField(max_length=100, blank=True)
    install_date = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['device', 'patch_id']
    
    def __str__(self):
        return f"{self.patch_name} - {self.status}"


class PulsewayReport(models.Model):
    report_id = models.CharField(max_length=100, unique=True)
    report_name = models.CharField(max_length=200)
    organization_name = models.CharField(max_length=200, blank=True)
    report_type = models.CharField(max_length=100)  # device, patch, security, etc.
    report_data = models.JSONField()
    generated_date = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.report_name} ({self.organization_name})"


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
        ('automation_update', 'Automation Task Update'),
        ('automation_delete', 'Automation Task Deletion'),
        ('remote_desktop', 'Remote Desktop Session'),
        ('device_update', 'Device Update'),
        ('policy_create', 'Policy Creation'),
        ('policy_update', 'Policy Update'),
        ('policy_delete', 'Policy Deletion'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    target_id = models.CharField(max_length=100)
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


class PulsewaySync(models.Model):
    sync_type = models.CharField(max_length=50)  # devices, organizations, patches, reports
    last_sync = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, default='success')  # success, failed
    records_synced = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.sync_type} - {self.last_sync}"
