"""
Customer configuration for Office 365 multi-tenant support
"""
import os

# Canonical customer configs — one entry per company, no duplicates
CUSTOMER_CONFIGS = {
    'cgl': {
        'name': 'C G Logistics',
        'tenant_id': os.getenv('CGL_TENANT_ID', ''),
        'client_id': os.getenv('CGL_CLIENT_ID', ''),
        'client_secret': os.getenv('CGL_CLIENT_SECRET', ''),
    },
    'wepsol': {
        'name': 'Wepsol',
        'tenant_id': os.getenv('WEPSOL_TENANT_ID', ''),
        'client_id': os.getenv('WEPSOL_CLIENT_ID', ''),
        'client_secret': os.getenv('WEPSOL_CLIENT_SECRET', ''),
    },
    'market-excel': {
        'name': 'MarketXcel',
        'tenant_id': os.getenv('MARKET_TENANT_ID', 'demo-tenant-id'),
        'client_id': os.getenv('MARKET_CLIENT_ID', 'demo-client-id'),
        'client_secret': os.getenv('MARKET_CLIENT_SECRET', 'demo-secret'),
    },
    'aquimen': {
        'name': 'Aiqmen',
        'tenant_id': os.getenv('AQUIMEN_TENANT_ID', 'demo-tenant-id'),
        'client_id': os.getenv('AQUIMEN_CLIENT_ID', 'demo-client-id'),
        'client_secret': os.getenv('AQUIMEN_CLIENT_SECRET', 'demo-secret'),
    },
    'ficc': {
        'name': 'FIICC',
        'tenant_id': os.getenv('FICC_TENANT_ID', 'demo-tenant-id'),
        'client_id': os.getenv('FICC_CLIENT_ID', 'demo-client-id'),
        'client_secret': os.getenv('FICC_CLIENT_SECRET', 'demo-secret'),
    },
    'digtinctive': {
        'name': 'Digtinctive',
        'tenant_id': os.getenv('DIGTINCTIVE_TENANT_ID', 'demo-tenant-id'),
        'client_id': os.getenv('DIGTINCTIVE_CLIENT_ID', 'demo-client-id'),
        'client_secret': os.getenv('DIGTINCTIVE_CLIENT_SECRET', 'demo-secret'),
    },
}

# Legacy key aliases — old session values still resolve correctly
_KEY_ALIASES = {
    '301': 'cgl',
    '601': 'digtinctive',
    'dingnintive': 'digtinctive',
}


# Customer keys that have real (non-demo) credentials
O365_CUSTOMER_KEYS_WITH_DATA = ['cgl', 'wepsol']


def get_customer_config(customer_key):
    """Get configuration for a specific customer (handles legacy key aliases)."""
    canonical = _KEY_ALIASES.get(customer_key, customer_key)
    return CUSTOMER_CONFIGS.get(canonical)


def get_canonical_key(customer_key):
    """Resolve a key (including legacy aliases) to its canonical form."""
    return _KEY_ALIASES.get(customer_key, customer_key)


def get_all_customers():
    """Return (key, display_name) list — only real companies, no duplicates."""
    return [(key, cfg['name']) for key, cfg in CUSTOMER_CONFIGS.items()]


def resolve_customer_key(company_name):
    """Return the CUSTOMER_CONFIGS key that best matches *company_name*."""
    from rbac.utils import normalize_company_name
    from difflib import SequenceMatcher

    norm_input = normalize_company_name(company_name)
    best_key, best_ratio = None, 0.0

    for key, cfg in CUSTOMER_CONFIGS.items():
        norm_cfg = normalize_company_name(cfg['name'])
        norm_key = normalize_company_name(key)

        for candidate in (norm_cfg, norm_key):
            if not candidate:
                continue
            if norm_input in candidate or candidate in norm_input:
                return key
            ratio = SequenceMatcher(None, norm_input, candidate).ratio()
            if ratio > best_ratio and ratio >= 0.55:
                best_ratio = ratio
                best_key = key
    return best_key
