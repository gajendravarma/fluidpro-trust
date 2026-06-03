from django.shortcuts import redirect
from django.http import JsonResponse
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
            
        # Skip permission check for superusers and admin-role users
        if request.user.is_superuser:
            return None
        try:
            if request.user.userprofile.get_role() == 'admin':
                return None
        except Exception:
            pass
            
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
            
        is_ajax = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
            request.headers.get('Accept', '').startswith('application/json')
        )

        # First check if user has access to the package at all
        if not has_package_access(request.user, package_name):
            if is_ajax:
                return JsonResponse({'success': False, 'message': f'You do not have access to {package_name}'}, status=403)
            messages.error(request, f'You do not have access to {package_name}')
            return redirect('/')

        # Then check specific permission based on HTTP method
        # POST sub-actions (assign, pickup, close, notes, worklogs) are update-level, not create
        method = request.method
        if method == 'POST' and any(x in request.path for x in ['/assign/', '/pickup/', '/close/', '/notes/', '/worklogs/', '/tasks/', '/attachments/', '/approvals/']):
            permission_name = 'update'
        else:
            permission_name = self.method_permission_mapping.get(method, 'read')

        if not has_package_permission(request.user, package_name, permission_name):
            if is_ajax:
                return JsonResponse({'success': False, 'message': f'You do not have {permission_name} permission for {package_name}'}, status=403)
            messages.error(request, f'You do not have {permission_name} permission for {package_name}')
            return redirect('/')

        return None
