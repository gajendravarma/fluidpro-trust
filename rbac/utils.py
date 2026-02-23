from .models import UserPackageAccess

def has_package_access(user, package_name):
    """Check if user has access to a package"""
    if user.is_superuser:
        return True
    
    try:
        access = UserPackageAccess.objects.get(
            user=user,
            package__name=package_name,
            package__is_active=True,
            is_enabled=True
        )
        return True
    except UserPackageAccess.DoesNotExist:
        return False

def has_package_permission(user, package_name, permission_name):
    """Check if user has specific permission for a package"""
    if user.is_superuser:
        return True
    
    try:
        access = UserPackageAccess.objects.get(
            user=user,
            package__name=package_name,
            package__is_active=True,
            is_enabled=True
        )
        
        permission_field = f"can_{permission_name}"
        return getattr(access, permission_field, False)
    except UserPackageAccess.DoesNotExist:
        return False

def get_user_packages(user):
    """Get all packages accessible to user"""
    if user.is_superuser:
        from .models import Package
        packages = Package.objects.filter(is_active=True)
        return [(pkg, ['create', 'read', 'update', 'delete']) for pkg in packages]
    
    accesses = UserPackageAccess.objects.filter(
        user=user,
        is_enabled=True,
        package__is_active=True
    ).select_related('package')
    
    result = []
    for access in accesses:
        permissions = []
        if access.can_create:
            permissions.append('create')
        if access.can_read:
            permissions.append('read')
        if access.can_update:
            permissions.append('update')
        if access.can_delete:
            permissions.append('delete')
        result.append((access.package, permissions))
    
    return result

def is_admin_user(user):
    """Check if user is admin (superuser)"""
    return user.is_superuser
