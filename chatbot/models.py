from django.db import models
from django.contrib.auth.models import User


class ChatbotCache(models.Model):
    """
    Snapshot store for live-API data (Office 365, Datto) used by the chatbot.
    Refreshed by the management command: python manage.py refresh_chatbot_cache
    """
    SOURCE_CHOICES = [
        ('office365', 'Office 365'),
        ('datto',     'Datto BCDR'),
    ]
    source      = models.CharField(max_length=30, choices=SOURCE_CHOICES)
    company_key = models.CharField(max_length=50, blank=True)   # e.g. 'cgl', 'wepsol', '' for datto
    data_type   = models.CharField(max_length=50)               # e.g. 'license_summary', 'storage_pool'
    payload     = models.JSONField(default=dict)
    fetched_at  = models.DateTimeField(auto_now=True)
    success     = models.BooleanField(default=True)
    error       = models.TextField(blank=True)

    class Meta:
        unique_together = ('source', 'company_key', 'data_type')

    def __str__(self):
        return f"{self.source}/{self.company_key}/{self.data_type} @ {self.fetched_at:%Y-%m-%d %H:%M}"


class ChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Chat session {self.session_id} - {self.user.username}"


class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    message = models.TextField()
    response = models.TextField()
    intent = models.CharField(max_length=100, blank=True)
    entities = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.session.session_id}: {self.message[:50]}..."
