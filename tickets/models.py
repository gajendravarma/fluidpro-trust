from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

# Original Ticket model (simplified)
class Ticket(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('pending', 'Pending'),
        ('closed', 'Closed'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    company = models.CharField(max_length=200, blank=True, null=True, default='')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title

# New cache models for fast reports
class TicketCache(models.Model):
    # Basic ticket info
    ticket_id = models.CharField(max_length=50, unique=True, db_index=True)
    subject = models.TextField()
    description = models.TextField(blank=True)
    
    # Status and Priority
    status = models.CharField(max_length=100, db_index=True)
    priority = models.CharField(max_length=50, db_index=True)
    category = models.CharField(max_length=100, blank=True)
    
    # People
    requester_name = models.CharField(max_length=200, blank=True)
    requester_email = models.EmailField(blank=True, null=True)
    technician_name = models.CharField(max_length=200, blank=True, db_index=True)
    company_name = models.CharField(max_length=200, blank=True, db_index=True)
    
    # Dates
    created_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Sync tracking
    last_synced = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ticket_cache'
        indexes = [
            models.Index(fields=['created_at', 'status']),
            models.Index(fields=['company_name', 'created_at']),
            models.Index(fields=['technician_name', 'created_at']),
        ]
    
    def __str__(self):
        return f"Ticket {self.ticket_id}: {self.subject[:50]}"

class ManageEngineUser(models.Model):
    """Local cache of ManageEngine users/requesters — synced periodically from the API."""
    me_id = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True, db_index=True)
    phone = models.CharField(max_length=50, blank=True)
    department = models.CharField(max_length=200, blank=True)
    company_name = models.CharField(max_length=200, blank=True, db_index=True)
    is_technician = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    last_synced = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'me_user_cache'
        indexes = [
            models.Index(fields=['is_technician']),
            models.Index(fields=['company_name']),
        ]

    def __str__(self):
        return f"{self.name} ({self.email})"


class SyncStatus(models.Model):
    last_sync_time = models.DateTimeField()
    total_tickets_synced = models.IntegerField(default=0)
    sync_status = models.CharField(max_length=20, default='pending')  # pending, running, completed, error
    error_message = models.TextField(blank=True)
    last_reconcile_time = models.DateTimeField(
        null=True, blank=True,
        help_text='Last time the daily reconcile (ghost-ticket purge) ran'
    )

    class Meta:
        db_table = 'sync_status'
