from django.urls import path
from . import views, license_views
from .views_company_dashboard import (
    company_dashboard, 
    company_tickets_by_status, 
    company_tickets_api,
    company_devices_by_status,
    company_devices_api,
    device_details_popup,
    ticket_details_popup,
    company_mdm_devices_api
)
from .password_reset_views import forgot_password, reset_password

app_name = 'rbac'

urlpatterns = [
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('api/dashboard-detail/', views.admin_dashboard_detail_api, name='admin_dashboard_detail_api'),
    path('license-dashboard/', views.license_dashboard, name='license_dashboard'),
    path('edit-license/<str:service_name>/', views.edit_license_config, name='edit_license_config'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path('technician-access/', views.manage_technician_access, name='manage_technician_access'),
    path('technician-access/set/', views.set_technician_company_access, name='set_technician_company_access'),
    path('assign-package-access/', views.assign_package_access, name='assign_package_access'),
    path('remove-package-access/', views.remove_package_access, name='remove_package_access'),
    path('assign-role/', views.assign_role, name='assign_role'),
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('company-dashboard/', company_dashboard, name='company_dashboard'),
    path('company-tickets/', company_tickets_by_status, name='company_tickets_by_status'),
    path('company-devices/', company_devices_by_status, name='company_devices_by_status'),
    path('api/company-tickets/', company_tickets_api, name='company_tickets_api'),
    path('api/company-devices/', company_devices_api, name='company_devices_api'),
    path('api/company-mdm-devices/', company_mdm_devices_api, name='company_mdm_devices_api'),
    path('api/device-details/', device_details_popup, name='device_details_popup'),
    path('api/ticket-details/', ticket_details_popup, name='ticket_details_popup'),
    path('customer-dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('check-permission/', views.check_permission, name='check_permission'),
    
    # License Management
    path('licenses/', license_views.license_dashboard, name='user_license_dashboard'),
    path('licenses/company/<int:company_id>/', license_views.manage_company_licenses, name='manage_company_licenses'),
    path('licenses/<int:license_id>/send-renewal/', license_views.trigger_renewal_email, name='trigger_renewal_email'),
    path('licenses/renewal-log/', license_views.renewal_notification_log, name='renewal_notification_log'),
]
