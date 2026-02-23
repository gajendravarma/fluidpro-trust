from django.shortcuts import redirect
from django.contrib import messages
from django.urls import resolve
from rbac.utils import has_package_permission, has_package_access

class RBACMiddleware:
    """Middleware to enforce RBAC permissions"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Define package mappings for URL patterns
        self.url_package_mapping = {
            'tickets': 'manageengine',
            'pulseway': 'pulseway',
            'office365': 'office365',
            'datto': 'datto',
            'site24x7': 'site24x7',
        }
        
        # Define permission mappings for HTTP methods
        self.method_permission_mapping = {
            'GET': 'read',
            'POST': 'create',
            'PUT': 'update',
            'PATCH': 'update',
            'DELETE': 'delete',
        }

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Skip permission check for non-authenticated users
        if not request.user.is_authenticated:
            return None
            
        # Skip permission check for superusers
        if request.user.is_superuser:
            return None
            
        # Skip permission check for RBAC, admin, and auth URLs
        resolver_match = resolve(request.path)
        if (resolver_match.app_name in ['rbac', 'admin'] or 
            request.path.startswith('/login/') or 
            request.path.startswith('/logout/') or
            request.path == '/logout/' or
            'logout' in request.path):
            return None
            
        # Get package name from URL
        package_name = None
        for url_prefix, pkg_name in self.url_package_mapping.items():
            if request.path.startswith(f'/{url_prefix}/'):
                package_name = pkg_name
                break
                
        if not package_name:
            return None
            
        # First check if user has access to the package at all
        if not has_package_access(request.user, package_name):
            messages.error(request, f'You do not have access to {package_name}')
            return redirect('/')
            
        # Then check specific permission based on HTTP method
        permission_name = self.method_permission_mapping.get(request.method, 'read')
        
        if not has_package_permission(request.user, package_name, permission_name):
            messages.error(request, f'You do not have {permission_name} permission for {package_name}')
            return redirect('/')
            
        return None
