import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'your-secret-key-here'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'tickets',
    'pulseway',
    'office365',
    'datto',
    'site24x7',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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
    }
}

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ManageEngine API Configuration
MANAGE_ENGINE_BASE_URL = 'https://fluidpro.wepsol.com:8080/api/v3'
MANAGE_ENGINE_AUTH_TOKEN = 'B6E3626D-BC0A-461C-B78C-ECDC79021ED0'

# Pulseway API Configuration
PULSEWAY_ENDPOINT = 'https://fluidpulse.pulseway.com/api/v3'
PULSEWAY_TOKEN_ID = '8137df64d8d949f693364bd46522883f'
PULSEWAY_TOKEN_SECRET = 'f42f47339208469da07bc3c62998e879ac53acd7dd6f4928837bb2392ca2b9f9'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'

# Office 365 API Configuration
OFFICE365_TENANT_ID = os.environ.get('OFFICE365_TENANT_ID', '')
OFFICE365_CLIENT_ID = os.environ.get('OFFICE365_CLIENT_ID', '')
OFFICE365_CLIENT_SECRET = os.environ.get('OFFICE365_CLIENT_SECRET', '')

# Azure API Configuration
AZURE_CLIENT_ID = os.environ.get('AZURE_CLIENT_ID', '')
AZURE_CLIENT_SECRET = os.environ.get('AZURE_CLIENT_SECRET', '')
AZURE_TENANT_ID = os.environ.get('AZURE_TENANT_ID', '')

# Datto API Configuration
DATTO_PUBLIC_KEY = os.environ.get('DATTO_PUBLIC_KEY', 'e16f42')
DATTO_SECRET_KEY = os.environ.get('DATTO_SECRET_KEY', '05817e9d31fd009260931e46f90d6205')
DATTO_BASE_URL = os.environ.get('DATTO_BASE_URL', 'https://api.datto.com/v1')

# Site24x7 API Configuration
SITE24X7_ACCESS_TOKEN = os.environ.get('SITE24X7_ACCESS_TOKEN', '1000.ca3eaf90f2903e166e022c577a619bd9.f98078be33d0e48b87804b0f094fbcc7')
SITE24X7_REFRESH_TOKEN = os.environ.get('SITE24X7_REFRESH_TOKEN', '1000.5664d5446a88dc8dda978e65d6be3929.5cea347c31be5379d8946aad7366b66c')
SITE24X7_API_DOMAIN = os.environ.get('SITE24X7_API_DOMAIN', 'https://www.site24x7.in')
ZOHO_CLIENT_ID = os.environ.get('ZOHO_CLIENT_ID', '')
ZOHO_CLIENT_SECRET = os.environ.get('ZOHO_CLIENT_SECRET', '')
