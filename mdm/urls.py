from django.urls import path
from . import views

app_name = 'mdm'

urlpatterns = [
    path('', views.mdm_dashboard, name='dashboard'),
    
    # Admin-only routes
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/companies/', views.admin_company_management, name='admin_companies'),
    path('admin/users/', views.admin_user_management, name='admin_users'),
    path('admin/settings/', views.admin_system_settings, name='admin_settings'),
    
    # Device management
    path('devices/', views.device_list, name='device_list'),
    path('devices/<str:device_id>/', views.device_detail, name='device_detail'),
    path('devices/<str:device_id>/action/', views.device_action, name='device_action'),
    path('devices/<str:device_id>/history/', views.device_command_history, name='device_command_history'),
    path('devices/<str:device_id>/sync/', views.device_sync, name='device_sync'),
    
    # Customer management (admin/technician only)
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/<int:customer_id>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:customer_id>/sync/', views.sync_customer_data, name='sync_customer_data'),
    path('customers/add/', views.add_customer, name='add_customer'),
    path('customers/<int:customer_id>/edit/', views.edit_customer, name='edit_customer'),
    path('customers/<int:customer_id>/delete/', views.delete_customer, name='delete_customer'),
    path('customers/<int:customer_id>/add-group/', views.add_device_group, name='add_device_group'),
    path('customers/<int:customer_id>/enrollment/', views.enrollment_settings, name='enrollment_settings'),
    
    # User management (admin/technician only)
    path('users/', views.user_list, name='user_list'),
    path('users/add/', views.add_user, name='add_user'),
    path('users/<int:user_id>/edit/', views.edit_user, name='edit_user'),
    path('users/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    
    # Reports
    path('reports/', views.reports_dashboard, name='reports'),
    path('reports/storage/', views.device_storage_report, name='storage_report'),
    path('reports/security/', views.security_report, name='security_report'),
    path('reports/apps/', views.installed_apps_report, name='apps_report'),
    path('reports/location/', views.location_report, name='location_report'),
    
    # Policies (admin/technician only)
    path('policies/', views.app_policies, name='app_policies'),
    path('policies/add-blacklist/', views.add_to_blacklist, name='add_to_blacklist'),
    path('policies/remove-blacklist/<str:app_id>/', views.remove_from_blacklist, name='remove_from_blacklist'),
    path('policies/blacklist-devices/', views.blacklist_devices, name='blacklist_devices'),
    path('policies/blacklist-groups/', views.blacklist_groups, name='blacklist_groups'),

    # Profiles (admin/technician only)
    path('profiles/', views.profiles_list, name='profiles_list'),
    path('profiles/create/', views.create_profile, name='create_profile'),

    # API endpoints
    path('api/test/', views.api_test, name='api_test'),
    path('api/live-status/', views.live_status, name='live_status'),
    path('api/sync-all/', views.sync_all_data, name='sync_all_data'),
    path('api/blacklist-apps/', views.api_blacklist_apps, name='api_blacklist_apps'),
    path('api/apps/', views.api_app_repository, name='api_app_repository'),
    path('api/profiles/', views.api_profiles_list, name='api_profiles_list'),
    
    # Access control
    path('no-access/', views.no_access, name='no_access'),
]
