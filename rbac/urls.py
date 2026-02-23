from django.urls import path
from . import views
from .views_company_dashboard import company_dashboard

app_name = 'rbac'

urlpatterns = [
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('license-dashboard/', views.license_dashboard, name='license_dashboard'),
    path('edit-license/<str:service_name>/', views.edit_license_config, name='edit_license_config'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path('assign-package-access/', views.assign_package_access, name='assign_package_access'),
    path('remove-package-access/', views.remove_package_access, name='remove_package_access'),
    path('assign-role/', views.assign_role, name='assign_role'),
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('company-dashboard/', company_dashboard, name='company_dashboard'),
    path('customer-dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('check-permission/', views.check_permission, name='check_permission'),
]
