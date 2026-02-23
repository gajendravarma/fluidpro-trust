from django.contrib import admin
from .models import Ticket

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'status', 'priority', 'created_by', 'created_at']
    list_filter = ['status', 'priority', 'company']
    search_fields = ['title', 'description', 'company__name']
