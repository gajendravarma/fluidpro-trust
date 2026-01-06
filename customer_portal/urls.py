from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('tickets.urls')),
    path('pulseway/', include('pulseway.urls')),
    path('office365/', include('office365.urls')),
    path('datto/', include('datto.urls')),
    path('site24x7/', include('site24x7.urls')),
]
