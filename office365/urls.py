from django.urls import path
from . import views

app_name = 'office365'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('license-details/', views.license_details, name='license_details'),
    path('mailbox-details/', views.mailbox_details, name='mailbox_details'),
    path('teams-analytics/', views.teams_analytics, name='teams_analytics'),
    path('email-analytics/', views.email_analytics, name='email_analytics'),
    path('api/summary/', views.api_summary, name='api_summary'),
    path('download-high-storage/', views.download_high_storage_users, name='download_high_storage'),
    path('download-all-users/', views.download_all_users, name='download_all_users'),
    path('download-license-report/', views.download_license_report, name='download_license_report'),
    path('api/check-permissions/', views.check_permissions, name='check_permissions'),
    path('api/raw-skus/', views.raw_skus, name='raw_skus'),
    # New admin/technician pages
    path('users/', views.user_management, name='user_management'),
    path('inactive-users/', views.inactive_users, name='inactive_users'),
    path('mfa-status/', views.mfa_status, name='mfa_status'),
    path('guest-users/', views.guest_users, name='guest_users'),
    path('onedrive/', views.onedrive_usage, name='onedrive_usage'),
]
