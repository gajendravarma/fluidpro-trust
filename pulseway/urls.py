from django.urls import path
from . import views

app_name = 'pulseway'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('devices/', views.devices, name='devices'),
    path('sites/', views.sites, name='sites'),
    path('groups/', views.groups, name='groups'),
    path('groups/<str:group_id>/devices/', views.group_devices, name='group_devices'),
    path('organizations/', views.organizations, name='organizations'),
    path('company-dashboard/', views.company_dashboard, name='company_dashboard'),
    path('api/company-data/', views.get_company_data, name='get_company_data'),
    path('api/by-status/', views.devices_by_status_api, name='devices_by_status_api'),
    path('api/devices/', views.pulseway_devices_api, name='pulseway_devices_api'),
    path('create-site/', views.create_site, name='create_site'),
    path('create-group/', views.create_group, name='create_group'),
    path('run-script/', views.run_script, name='run_script'),
    path('install-patches/', views.install_patches, name='install_patches'),
    path('reboot-device/<str:device_id>/', views.reboot_device, name='reboot_device'),
    path('remote-desktop/<str:device_id>/', views.remote_desktop, name='remote_desktop'),
    path('automation/', views.automation_tasks, name='automation_tasks'),
    path('automation/create/', views.create_automation_task, name='create_automation_task'),
    path('automation/run/<str:task_id>/', views.run_automation_task, name='run_automation_task'),
    path('automation/edit/<str:task_id>/', views.edit_automation_task, name='edit_automation_task'),
    path('automation/delete/<str:task_id>/', views.delete_automation_task, name='delete_automation_task'),
    path('sites/edit/<str:site_id>/', views.edit_site, name='edit_site'),
    path('sites/delete/<str:site_id>/', views.delete_site, name='delete_site'),
    path('groups/edit/<str:group_id>/', views.edit_group, name='edit_group'),
    path('groups/delete/<str:group_id>/', views.delete_group, name='delete_group'),
    path('actions/', views.actions_history, name='actions_history'),
    path('devices/<str:device_id>/', views.device_detail, name='device_detail'),
    path('devices/<str:device_id>/install-patches/', views.device_install_patches, name='device_install_patches'),
    path('devices/<str:device_id>/reboot/', views.device_reboot, name='device_reboot'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<str:notification_id>/acknowledge/', views.acknowledge_notification, name='acknowledge_notification'),
    path('debug/device/<str:device_id>/fields/', views.debug_device_fields, name='debug_device_fields'),
    path('api/sync-devices/', views.trigger_device_sync, name='trigger_device_sync'),
    path('admin/sync/', views.sync_control, name='sync_control'),
    path('admin/api-vs-db/', views.api_vs_db_compare, name='api_vs_db_compare'),
    # Reports (admin/technician only)
    path('reports/device-inventory/', views.report_device_inventory, name='report_device_inventory'),
    path('reports/alert-log/', views.report_alert_log, name='report_alert_log'),
    path('reports/patch-alerts/', views.report_patch_alerts, name='report_patch_alerts'),
    path('reports/software/', views.software_report, name='software_report'),
    # Device edit (admin/technician only)
    path('devices/<str:device_id>/edit/', views.edit_device, name='edit_device'),
    # Policies (admin/technician only)
    path('policies/', views.policies, name='policies'),
    path('policies/create/', views.create_policy, name='create_policy'),
    path('policies/<str:policy_id>/edit/', views.edit_policy, name='edit_policy'),
    path('policies/<str:policy_id>/delete/', views.delete_policy, name='delete_policy'),
]
