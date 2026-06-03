from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .fast_reports import fast_reports_dashboard, export_tickets_csv, search_tickets_api, ticket_stats_api
from .simple_reports import simple_reports

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('create/', views.create_ticket, name='create_ticket'),
    path('ticket/<int:ticket_id>/', views.view_ticket, name='view_ticket'),
    path('ticket/<int:ticket_id>/update/', views.update_ticket, name='update_ticket'),
    path('technicians/', views.technicians, name='technicians'),
    path('users/', views.all_users, name='all_users'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('tickets/delete/<int:ticket_id>/', views.delete_ticket, name='delete_ticket'),
    path('technicians/add/', views.add_technician, name='add_technician'),
    path('technicians/edit/<int:user_id>/', views.edit_technician, name='edit_technician'),
    path('technicians/delete/<int:user_id>/', views.delete_technician, name='delete_technician'),
    path('api/historical-tickets/', views.historical_tickets_api, name='historical_tickets_api'),
    path('reports/', views.reports_dashboard, name='reports_dashboard'),
    path('reports/generate/', views.generate_report, name='generate_report'),
    path('reports/simple/', simple_reports, name='simple_reports'),
    path('reports/export/', views.export_report_csv, name='export_report_csv'),
    path('reports/companies/', views.get_companies_api, name='get_companies_api'),
    path('reports/technicians/', views.get_technicians_api, name='get_technicians_api'),
    path('api/by-status/', views.tickets_by_status_api, name='tickets_by_status_api'),
    path('reports/export/pulseway/', views.export_pulseway_csv, name='export_pulseway_csv'),
    path('reports/export/mdm/', views.export_mdm_csv, name='export_mdm_csv'),
    path('reports/export/manageengine/', views.export_manageengine_csv, name='export_manageengine_csv'),
    path('reports/export/o365-users/', views.export_o365_users_csv, name='export_o365_users_csv'),
    path('api/o365-users/', views.o365_users_api, name='o365_users_api'),
    path('api/list/', views.dashboard_tickets_api, name='dashboard_tickets_api'),
    
    # Fast reports using local database
    path('fast-reports/', fast_reports_dashboard, name='fast_reports'),
    path('export-csv/', export_tickets_csv, name='export_csv'),
    path('api/search/', search_tickets_api, name='search_api'),
    path('api/stats/', ticket_stats_api, name='stats_api'),

    # ── ManageEngine ticket detail (technician / admin) ──────────────── #
    path('me/<str:me_ticket_id>/', views.me_ticket_detail, name='me_ticket_detail'),

    # Notes
    path('me/<str:me_ticket_id>/notes/add/', views.me_ticket_add_note, name='me_ticket_add_note'),
    path('me/<str:me_ticket_id>/notes/<str:note_id>/edit/', views.me_ticket_edit_note, name='me_ticket_edit_note'),
    path('me/<str:me_ticket_id>/notes/<str:note_id>/delete/', views.me_ticket_delete_note, name='me_ticket_delete_note'),

    # Worklogs
    path('me/<str:me_ticket_id>/worklogs/add/', views.me_ticket_add_worklog, name='me_ticket_add_worklog'),
    path('me/<str:me_ticket_id>/worklogs/<str:worklog_id>/delete/', views.me_ticket_delete_worklog, name='me_ticket_delete_worklog'),

    # Tasks
    path('me/<str:me_ticket_id>/tasks/add/', views.me_ticket_add_task, name='me_ticket_add_task'),
    path('me/<str:me_ticket_id>/tasks/<str:task_id>/update/', views.me_ticket_update_task, name='me_ticket_update_task'),
    path('me/<str:me_ticket_id>/tasks/<str:task_id>/delete/', views.me_ticket_delete_task, name='me_ticket_delete_task'),

    # Assign / Pickup / Close
    path('me/<str:me_ticket_id>/assign/', views.me_ticket_assign, name='me_ticket_assign'),
    path('me/<str:me_ticket_id>/pickup/', views.me_ticket_pickup, name='me_ticket_pickup'),
    path('me/<str:me_ticket_id>/close/', views.me_ticket_close, name='me_ticket_close'),

    # Attachment
    path('me/<str:me_ticket_id>/attachments/add/', views.me_ticket_add_attachment, name='me_ticket_add_attachment'),

    # Approvals
    path('me/<str:me_ticket_id>/approvals/send/', views.me_ticket_send_approval, name='me_ticket_send_approval'),
    path('me/<str:me_ticket_id>/approvals/<str:approval_id>/action/', views.me_ticket_approve_reject, name='me_ticket_approve_reject'),
]
