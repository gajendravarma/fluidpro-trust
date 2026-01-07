"""
Customer configuration for Office 365 multi-tenant support
"""
import os

CUSTOMER_CONFIGS = {
    'wepsol': {
        'name': 'Wepsol',
        'tenant_id': os.getenv('WEPSOL_TENANT_ID', ''),
        'client_id': os.getenv('WEPSOL_CLIENT_ID', ''),
        'client_secret': os.getenv('WEPSOL_CLIENT_SECRET', '')
    },
    'cgl': {
        'name': 'CGL',
        'tenant_id': os.getenv('CGL_TENANT_ID', ''),
        'client_id': os.getenv('CGL_CLIENT_ID', ''),
        'client_secret': os.getenv('CGL_CLIENT_SECRET', '')
    }
}

def get_customer_config(customer_key):
    """Get configuration for a specific customer"""
    return CUSTOMER_CONFIGS.get(customer_key)

def get_all_customers():
    """Get list of all available customers"""
    return [(key, config['name']) for key, config in CUSTOMER_CONFIGS.items()]
