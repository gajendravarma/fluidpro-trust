from django.db import models
from rbac.models import Company

class Office365User(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='office365_users')
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=200)
    license_assigned = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.display_name} ({self.company.name})"
