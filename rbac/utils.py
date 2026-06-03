import re
from difflib import SequenceMatcher
from .models import UserPackageAccess

def has_package_access(user, package_name):
    """Check if user has access to a package. Admins always have full access."""
    if user.is_superuser:
        return True
    try:
        if user.userprofile.get_role() == 'admin':
            return True
    except Exception:
        pass
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
    """Check if user has specific permission for a package. Admins always have full access."""
    if user.is_superuser:
        return True
    try:
        if user.userprofile.get_role() == 'admin':
            return True
    except Exception:
        pass
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


# ---------------------------------------------------------------------------
# Company name matching helpers
# ---------------------------------------------------------------------------

_COMPANY_SUFFIXES = re.compile(
    r'\b(pvt\.?\s*ltd\.?|private\s+limited|ltd\.?|llp|inc\.?|corp\.?|co\.?|group)\b',
    re.IGNORECASE,
)


def normalize_company_name(name):
    """Strip common legal suffixes and extra whitespace for fuzzy comparison."""
    if not name:
        return ''
    name = _COMPANY_SUFFIXES.sub('', name).lower()
    return re.sub(r'\s+', ' ', name).strip()


def company_name_match(name_a, name_b, threshold=0.6):
    """Return True if two company name strings are similar enough."""
    a = normalize_company_name(name_a)
    b = normalize_company_name(name_b)
    if not a or not b:
        return False
    # Substring match is fast and catches "CG Logistics" vs "CG Logistics Pvt Ltd"
    if a in b or b in a:
        return True
    return SequenceMatcher(None, a, b).ratio() >= threshold


def get_technician_companies(user):
    """
    Return the set of company names a technician is allowed to see, or None.

    None  → unrestricted (admin, superuser, or technician with no restrictions set)
    set() → restricted to exactly these company names (inhouse / limited-access tech)

    Usage in views:
        allowed = get_technician_companies(request.user)
        if allowed is not None:
            qs = qs.filter(company_name__in=allowed)
    """
    if not user.is_authenticated:
        return set()
    if user.is_superuser:
        return None   # always unrestricted

    try:
        role = user.userprofile.get_role()
    except Exception:
        return None

    if role == 'admin':
        return None   # unrestricted

    if role != 'technician':
        # customers handled separately by their UserProfile.company
        return None

    from .models import TechnicianCompanyAccess
    accesses = TechnicianCompanyAccess.objects.filter(user=user).select_related('company')
    if not accesses.exists():
        return None   # no restrictions configured → unrestricted technician

    return {a.company.name for a in accesses}


def find_company_for_name(name, threshold=0.6):
    """Return the Company whose name best matches *name*, or None.
    Uses normalized fuzzy matching to handle slight variations across packages.
    """
    from .models import Company
    norm = normalize_company_name(name)
    best, best_ratio = None, 0.0
    for company in Company.objects.all():
        ratio = SequenceMatcher(None, norm, normalize_company_name(company.name)).ratio()
        if (norm in normalize_company_name(company.name) or
                normalize_company_name(company.name) in norm):
            return company  # exact substring — return immediately
        if ratio > best_ratio and ratio >= threshold:
            best_ratio = ratio
            best = company
    return best
