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
    path('create-site/', views.create_site, name='create_site'),
    path('create-group/', views.create_group, name='create_group'),
    path('run-script/', views.run_script, name='run_script'),
    path('install-patches/', views.install_patches, name='install_patches'),
    path('reboot-device/<str:device_id>/', views.reboot_device, name='reboot_device'),
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
]
