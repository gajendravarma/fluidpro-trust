import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-me')
DEBUG = True
ALLOWED_HOSTS = ['*']

# Security Settings
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'SAMEORIGIN'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
SESSION_COOKIE_SECURE = False  # Set to True when using HTTPS
CSRF_COOKIE_SECURE = False  # Set to True when using HTTPS
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rbac',
    'tickets',
    'pulseway',
    'office365',
    'datto',
    'site24x7',
    'chatbot',
    'mdm',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'rbac.middleware.RBACMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'customer_portal.security_middleware.SecurityHeadersMiddleware',
]

ROOT_URLCONF = 'customer_portal.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            # Wait up to 30 s before raising OperationalError on a locked DB.
            # WAL mode (enabled via connection_created signal in apps.py) gives
            # much better read/write concurrency but this timeout is still needed
            # as a fallback for long-running write transactions.
            'timeout': 30,
        }
    }
}

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'registration.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'rbac.registration': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# ManageEngine ServiceDesk API (tickets)
MANAGE_ENGINE_BASE_URL  = os.environ.get('MANAGE_ENGINE_BASE_URL', 'https://fluidpro.wepsol.com:8080/api/v3')
MANAGE_ENGINE_AUTH_TOKEN = os.environ.get('MANAGE_ENGINE_AUTH_TOKEN', '')

# ManageEngine MDM API (On-Premises)
MDM_API_BASE_URL = os.environ.get('MDM_API_BASE_URL', 'https://mdm.wepsol.com:9041')
MDM_API_KEY      = os.environ.get('MDM_API_KEY', '')

# License Configuration
LICENSE_CONFIG = {
    'manageengine': {
        'total_licenses': 15,
        'license_type': 'Professional',
        'expiry_date': '2026-12-31'
    },
    'pulseway': {
        'total_licenses': 500,
        'license_type': 'Professional',
        'expiry_date': '2026-12-31'
    },
    'datto': {
        'total_licenses': 5,
        'license_type': 'BCDR',
        'expiry_date': '2026-12-31'
    },
    'office365': {
        'expiry_date': '2026-12-31'  # Office365 gets real license data from API
    },
    'site24x7': {
        'total_licenses': 200,
        'license_type': 'Professional',
        'expiry_date': '2026-12-31'
    }
}

# Pulseway API Configuration
PULSEWAY_ENDPOINT     = os.environ.get('PULSEWAY_ENDPOINT', 'https://fluidpulse.pulseway.com/api/v3')
PULSEWAY_TOKEN_ID     = os.environ.get('PULSEWAY_TOKEN_ID', '')
PULSEWAY_TOKEN_SECRET = os.environ.get('PULSEWAY_TOKEN_SECRET', '')

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# Email Configuration for License Alerts
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'your-email@example.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'your-password')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
LICENSE_ALERT_EMAILS = ['admin@example.com']  # Add admin emails here

# Office 365 API Configuration
OFFICE365_TENANT_ID = os.environ.get('OFFICE365_TENANT_ID', '')
OFFICE365_CLIENT_ID = os.environ.get('OFFICE365_CLIENT_ID', '')
OFFICE365_CLIENT_SECRET = os.environ.get('OFFICE365_CLIENT_SECRET', '')

# Azure API Configuration
AZURE_CLIENT_ID = os.environ.get('AZURE_CLIENT_ID', '')
AZURE_CLIENT_SECRET = os.environ.get('AZURE_CLIENT_SECRET', '')
AZURE_TENANT_ID = os.environ.get('AZURE_TENANT_ID', '')

# Datto API Configuration
DATTO_PUBLIC_KEY = os.environ.get('DATTO_PUBLIC_KEY', '')
DATTO_SECRET_KEY = os.environ.get('DATTO_SECRET_KEY', '')
DATTO_BASE_URL = os.environ.get('DATTO_BASE_URL', 'https://api.datto.com/v1')

# Site24x7 API Configuration
SITE24X7_ACCESS_TOKEN = os.environ.get('SITE24X7_ACCESS_TOKEN', '')
SITE24X7_REFRESH_TOKEN = os.environ.get('SITE24X7_REFRESH_TOKEN', '')
SITE24X7_API_DOMAIN = os.environ.get('SITE24X7_API_DOMAIN', 'https://www.site24x7.in')
ZOHO_CLIENT_ID = os.environ.get('ZOHO_CLIENT_ID', '')
ZOHO_CLIENT_SECRET = os.environ.get('ZOHO_CLIENT_SECRET', '')

# Email Configuration - Microsoft Graph API
EMAIL_BACKEND = 'rbac.enhanced_graph_email_backend.GraphEmailBackend'

# Microsoft Graph API Settings (Wepsol Tenant)
GRAPH_TENANT_ID = os.getenv('WEPSOL_TENANT_ID', '')
GRAPH_CLIENT_ID = os.getenv('WEPSOL_CLIENT_ID', '')
GRAPH_CLIENT_SECRET = os.getenv('WEPSOL_CLIENT_SECRET', '')
GRAPH_FROM_EMAIL = 'Gajendra.N@wepsol.com'

DEFAULT_FROM_EMAIL = 'Gajendra.N@wepsol.com'

# Public IP for email links
PUBLIC_IP = '3.109.60.172'

# ── Claude AI (chatbot) ───────────────────────────────────────────────────────
# Set this to enable intelligent Claude-powered chatbot responses.
# Get your key from: https://console.anthropic.com/
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
