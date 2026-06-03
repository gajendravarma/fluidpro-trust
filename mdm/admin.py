from django.contrib import admin
from .models import (
    MdmCustomer, MdmUser, Device, InstalledApp, SecurityEvent, 
    DeviceGroup, AppPolicy, Profile, EnrollmentSettings
)

@admin.register(MdmCustomer)
class MdmCustomerAdmin(admin.ModelAdmin):
    list_display = ['company', 'customer_id', 'device_count', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['company__name', 'customer_id']
    readonly_fields = ['created_at']

@admin.register(MdmUser)
class MdmUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'mdm_customer', 'employee_id', 'department', 'role']
    list_filter = ['role', 'department', 'created_at']
    search_fields = ['user__username', 'user__email', 'employee_id']

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['device_name', 'device_type', 'mdm_customer', 'username', 'status', 'enrolled_at']
    list_filter = ['device_type', 'status', 'is_supervised', 'is_encrypted']
    search_fields = ['device_name', 'username', 'user_email', 'serial_number', 'imei']
    readonly_fields = ['enrolled_at']

@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ['device', 'event_type', 'severity', 'resolved', 'created_at']
    list_filter = ['event_type', 'severity', 'resolved', 'created_at']
    search_fields = ['device__device_name', 'description']

@admin.register(AppPolicy)
class AppPolicyAdmin(admin.ModelAdmin):
    list_display = ['app_name', 'mdm_customer', 'policy_type', 'created_at']
    list_filter = ['policy_type', 'created_at']
    search_fields = ['app_name', 'package_name']

admin.site.register(InstalledApp)
admin.site.register(DeviceGroup)
admin.site.register(Profile)
admin.site.register(EnrollmentSettings)
