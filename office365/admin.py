from django.contrib import admin
from .models import Office365User

@admin.register(Office365User)
class Office365UserAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'email', 'company', 'license_assigned', 'last_login']
    list_filter = ['license_assigned', 'company']
    search_fields = ['display_name', 'email', 'company__name']
