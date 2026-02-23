from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='site24x7_dashboard'),
    path('api/data/', views.api_data, name='site24x7_api_data'),
    path('api/customer/<str:customer_id>/monitors/', views.customer_monitors, name='site24x7_customer_monitors'),
    path('api/monitor/<str:monitor_id>/details/', views.monitor_details, name='site24x7_monitor_details'),
]
