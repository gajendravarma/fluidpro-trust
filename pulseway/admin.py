from django.contrib import admin
from .models import PulsewayDevice, PulsewayPatchReport, PulsewayAction

@admin.register(PulsewayDevice)
class PulsewayDeviceAdmin(admin.ModelAdmin):
    list_display = ['device_name', 'company', 'status', 'last_seen']
    list_filter = ['status', 'company']
    search_fields = ['device_name', 'device_id', 'company__name']

@admin.register(PulsewayPatchReport)
class PulsewayPatchReportAdmin(admin.ModelAdmin):
    list_display = ['patch_name', 'device', 'company', 'status', 'created_at']
    list_filter = ['status', 'company']
    search_fields = ['patch_name', 'device__device_name']

@admin.register(PulsewayAction)
class PulsewayActionAdmin(admin.ModelAdmin):
    list_display = ['action_type', 'target_name', 'user', 'status', 'created_at']
    list_filter = ['action_type', 'status']
    search_fields = ['target_name', 'user__username']
