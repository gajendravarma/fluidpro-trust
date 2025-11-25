from django.db import models
from django.contrib.auth.models import User


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
