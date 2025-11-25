from django.db import models
from django.contrib.auth.models import User

class Ticket(models.Model):
    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Normal', 'Normal'),
        ('High', 'High'),
        ('Urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('Open', 'Open'),
        ('Closed', 'Closed'),
        ('Onhold', 'Onhold'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='Normal')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    manage_engine_id = models.CharField(max_length=50, blank=True, null=True)
    
    def __str__(self):
        return f"{self.title} - {self.status}"
