from django.contrib import admin
from .models import PulsewayDevice, PulsewayOrganization, PulsewayPatch, PulsewayReport, PulsewayAction, PulsewaySync


@admin.register(PulsewayDevice)
class PulsewayDeviceAdmin(admin.ModelAdmin):
    list_display = ['device_name', 'organization_name', 'status', 'pending_patches', 'last_updated']
    list_filter = ['status', 'organization_name', 'last_updated']
    search_fields = ['device_name', 'organization_name', 'ip_address']
    readonly_fields = ['last_updated']


@admin.register(PulsewayOrganization)
class PulsewayOrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'device_count', 'online_devices', 'offline_devices', 'pending_patches']
    readonly_fields = ['last_updated']


@admin.register(PulsewayPatch)
class PulsewayPatchAdmin(admin.ModelAdmin):
    list_display = ['patch_name', 'device', 'status', 'severity', 'last_updated']
    list_filter = ['status', 'severity', 'category']
    search_fields = ['patch_name', 'device__device_name']


@admin.register(PulsewayReport)
class PulsewayReportAdmin(admin.ModelAdmin):
    list_display = ['report_name', 'organization_name', 'report_type', 'generated_date']
    list_filter = ['report_type', 'organization_name']
    search_fields = ['report_name', 'organization_name']


@admin.register(PulsewayAction)
class PulsewayActionAdmin(admin.ModelAdmin):
    list_display = ['action_type', 'target_name', 'user', 'status', 'created_at']
    list_filter = ['action_type', 'status', 'created_at']
    search_fields = ['target_name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PulsewaySync)
class PulsewaySyncAdmin(admin.ModelAdmin):
    list_display = ['sync_type', 'last_sync', 'status', 'records_synced']
    list_filter = ['sync_type', 'status', 'last_sync']
    readonly_fields = ['last_sync']
