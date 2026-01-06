from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

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
]
