from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Package, UserPackageAccess, Company, UserProfile, Role

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'created_at']
    search_fields = ['name', 'code']

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_name_display', 'description']
    search_fields = ['name']

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
    fields = ['company', 'role', 'mobile_number', 'location', 'address']

class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ['username', 'email', 'first_name', 'last_name', 'get_company', 'get_role', 'is_staff']
    
    def get_company(self, obj):
        try:
            return obj.userprofile.company.name if obj.userprofile.company else 'No Company'
        except:
            return 'No Profile'
    get_company.short_description = 'Company'
    
    def get_role(self, obj):
        try:
            return obj.userprofile.role.get_name_display() if obj.userprofile.role else 'No Role'
        except:
            return 'No Profile'
    get_role.short_description = 'Role'

# Unregister the default User admin and register custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'role', 'mobile_number', 'location']
    list_filter = ['company', 'role']
    search_fields = ['user__username', 'company__name']
    raw_id_fields = ['user']

@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'display_name']

@admin.register(UserPackageAccess)
class UserPackageAccessAdmin(admin.ModelAdmin):
    list_display = ['user', 'package', 'is_enabled', 'can_create', 'can_read', 'can_update', 'can_delete', 'assigned_at']
    list_filter = ['package', 'is_enabled', 'can_create', 'can_read', 'can_update', 'can_delete']
    search_fields = ['user__username', 'user__email', 'package__name']
    list_editable = ['is_enabled', 'can_create', 'can_read', 'can_update', 'can_delete']
