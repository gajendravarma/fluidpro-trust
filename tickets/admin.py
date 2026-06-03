from django.contrib import admin
from .models import Ticket, TicketCache

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'status', 'priority', 'created_by', 'created_at']
    list_filter = ['status', 'priority', 'company']
    search_fields = ['title', 'description', 'company__name']

@admin.register(TicketCache)
class TicketCacheAdmin(admin.ModelAdmin):
    list_display = ['ticket_id', 'subject', 'company_name', 'status', 'priority', 'technician_name', 'created_at']
    list_filter = ['status', 'priority', 'company_name', 'technician_name']
    search_fields = ['ticket_id', 'subject', 'company_name', 'requester_name']
    readonly_fields = ['ticket_id', 'subject', 'description', 'status', 'priority', 'company_name', 'created_at']
