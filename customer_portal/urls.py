from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from rbac.views import user_dashboard
from rbac.registration_views import register_view
from rbac.password_reset_views import forgot_password, reset_password

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', user_dashboard, name='home'),
    path('rbac/', include('rbac.urls')),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', register_view, name='register'),
    path('forgot-password/', forgot_password, name='forgot_password'),
    path('reset-password/<uidb64>/<token>/', reset_password, name='reset_password'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('tickets/', include('tickets.urls')),
    path('chatbot/', include('chatbot.urls')),
    path('pulseway/', include('pulseway.urls')),
    path('office365/', include('office365.urls')),
    path('datto/', include('datto.urls')),
    path('site24x7/', include('site24x7.urls')),
    path('mdm/', include('mdm.urls')),
]
