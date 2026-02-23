from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from rbac.views import user_dashboard
from rbac.registration_views import register_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', user_dashboard, name='home'),
    path('rbac/', include('rbac.urls')),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', register_view, name='register'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('tickets/', include('tickets.urls')),
    path('pulseway/', include('pulseway.urls')),
    path('office365/', include('office365.urls')),
    path('datto/', include('datto.urls')),
    path('site24x7/', include('site24x7.urls')),
]
