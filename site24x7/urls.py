from django.urls import path
from . import views
from . import views_extra as ve

app_name = 'site24x7'

urlpatterns = [
    # ── Dashboard ──────────────────────────────────────────────────────────────
    path('', views.dashboard, name='site24x7_dashboard'),

    # ── Customer report (availability summary) ────────────────────────────────
    path('customer/<str:zaaid>/report/', views.customer_report, name='customer_report'),

    # ── Monitor management ────────────────────────────────────────────────────
    path('customer/<str:zaaid>/monitors/', ve.monitor_list, name='monitor_list'),
    path('customer/<str:zaaid>/monitors/create/', ve.monitor_create, name='monitor_create'),
    path('customer/<str:zaaid>/monitors/<str:monitor_id>/', ve.monitor_detail, name='monitor_detail'),
    path('customer/<str:zaaid>/monitors/<str:monitor_id>/edit/', ve.monitor_edit, name='monitor_edit'),
    path('customer/<str:zaaid>/monitors/<str:monitor_id>/delete/', ve.monitor_delete, name='monitor_delete'),

    # ── Maintenance windows ────────────────────────────────────────────────────
    path('customer/<str:zaaid>/maintenance/', ve.maintenance_view, name='maintenance'),

    # ── Profiles & configuration viewer ───────────────────────────────────────
    path('customer/<str:zaaid>/profiles/', ve.profiles_view, name='profiles'),

    # ── JSON API (for JS interactions) ────────────────────────────────────────
    path('api/data/', views.api_data, name='site24x7_api_data'),
    path('api/customer/<str:customer_id>/monitors/', views.customer_monitors, name='site24x7_customer_monitors'),
    path('api/monitor/<str:monitor_id>/details/', views.monitor_details, name='site24x7_monitor_details'),

    # ── Token management ──────────────────────────────────────────────────────
    path('token/update/', views.update_token, name='update_token'),
    path('api/token-status/', views.token_status, name='token_status'),
]
