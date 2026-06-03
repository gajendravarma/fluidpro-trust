from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_interface, name='chat_interface'),
    path('api/chat/', views.chat_api, name='chat_api'),
    path('api/history/', views.chat_history, name='chat_history'),
    path('api/new-session/', views.new_session, name='new_session'),
    path('api/status/', views.engine_status, name='engine_status'),
]
