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
]
