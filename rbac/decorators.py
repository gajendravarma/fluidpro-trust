from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from .utils import has_package_permission, has_package_access

def require_package_access(package_name):
    """Decorator to check if user has access to package"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not has_package_access(request.user, package_name):
                messages.error(request, f'You do not have access to {package_name}')
                return redirect('/')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def require_package_permission(package_name, permission_name):
    """Decorator to check package permission"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not has_package_permission(request.user, package_name, permission_name):
                messages.error(request, f'You do not have {permission_name} permission for {package_name}')
                return redirect('/')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
