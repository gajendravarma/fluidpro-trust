from django import template
from rbac.utils import has_package_access

register = template.Library()

@register.filter
def has_package_access(user, package_name):
    """Template filter to check if user has access to a package"""
    from rbac.utils import has_package_access as check_access
    return check_access(user, package_name)
