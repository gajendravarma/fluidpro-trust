from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='datto_dashboard'),
    path('api/data/', views.api_data, name='datto_api_data'),
    path('api/dtc/<str:client_id>/assets/', views.dtc_client_assets, name='datto_dtc_client_assets'),
]
