from django.urls import path
from . import views

app_name = 'datto'

urlpatterns = [
    path('', views.dashboard, name='datto_dashboard'),
    path('api/data/', views.api_data, name='datto_api_data'),
    path('api/dtc/<str:client_id>/assets/', views.dtc_client_assets, name='datto_dtc_client_assets'),
    path('api/diagnostic/', views.api_diagnostic, name='datto_api_diagnostic'),
    path('reports/storage/', views.download_storage_report, name='download_storage_report'),
    path('reports/devices/', views.download_device_report, name='download_device_report'),
]
