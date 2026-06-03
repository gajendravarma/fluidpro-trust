import requests
import os
import time
import threading
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# Module-level token cache shared across all Site24x7Platform instances.
# Stores the token string + the epoch time when it was fetched.
# Access tokens last 3600 s — we proactively refresh after 3300 s (55 min).
_token_lock   = threading.Lock()
_current_token  = None
_token_fetched_at = 0.0   # epoch seconds
_TOKEN_LIFETIME   = 3300  # refresh proactively 5 min before expiry


def _get_env_path():
    return os.path.join(settings.BASE_DIR, '.env')


def _persist_to_env(key: str, value: str):
    """Overwrite a key=value line in the .env file."""
    env_path = _get_env_path()
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        updated, found = [], False
        for line in lines:
            if line.startswith(f'{key}='):
                updated.append(f'{key}={value}\n')
                found = True
            else:
                updated.append(line)
        if not found:
            updated.append(f'{key}={value}\n')
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(updated)
    except Exception as e:
        logger.warning(f'[Site24x7] Could not persist {key} to .env: {e}')


class TokenManager:

    # ── Public interface ─────────────────────────────────────────────────

    def get_valid_token(self) -> str:
        """
        Return a valid access token, refreshing proactively if it is
        near expiry (within 5 min) or has never been fetched.
        """
        global _current_token, _token_fetched_at

        with _token_lock:
            age = time.time() - _token_fetched_at
            if _current_token is None:
                # First call — use the token from settings/env
                _current_token = settings.SITE24X7_ACCESS_TOKEN
                _token_fetched_at = time.time()
                logger.info('[Site24x7] Loaded access token from settings.')

            if age >= _TOKEN_LIFETIME:
                logger.info(f'[Site24x7] Token age {age:.0f}s >= {_TOKEN_LIFETIME}s — refreshing proactively.')
                refreshed = self._do_refresh()
                if refreshed:
                    _current_token = refreshed
                    _token_fetched_at = time.time()

            return _current_token

    def handle_401_error(self):
        """
        Called by the API client when a 401 is received.
        Forces a token refresh regardless of age, persists the new token,
        and returns it (or None on failure).
        """
        global _current_token, _token_fetched_at
        logger.info('[Site24x7] 401 received — forcing token refresh.')
        refreshed = self._do_refresh()
        if refreshed:
            with _token_lock:
                _current_token = refreshed
                _token_fetched_at = time.time()
            settings.SITE24X7_ACCESS_TOKEN = refreshed
            _persist_to_env('SITE24X7_ACCESS_TOKEN', refreshed)
            logger.info('[Site24x7] Token refreshed and persisted.')
            return refreshed
        logger.error('[Site24x7] Token refresh failed — requests will continue to use the expired token.')
        return None

    # ── Internal ─────────────────────────────────────────────────────────

    def _do_refresh(self) -> str | None:
        """
        Call Zoho's token endpoint with the refresh token.
        Returns the new access token string, or None on any failure.
        """
        refresh_token  = getattr(settings, 'SITE24X7_REFRESH_TOKEN', '')
        client_id      = getattr(settings, 'ZOHO_CLIENT_ID', '')
        client_secret  = getattr(settings, 'ZOHO_CLIENT_SECRET', '')

        if not refresh_token:
            logger.error('[Site24x7] SITE24X7_REFRESH_TOKEN is not set — cannot refresh.')
            return None

        if not client_id or not client_secret:
            logger.error(
                '[Site24x7] ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET are not configured. '
                'Set them in .env to enable automatic token refresh. '
                'Get them from https://api-console.zoho.in'
            )
            return None

        try:
            resp = requests.post(
                'https://accounts.zoho.in/oauth/v2/token',
                data={
                    'refresh_token': refresh_token,
                    'client_id':     client_id,
                    'client_secret': client_secret,
                    'grant_type':    'refresh_token',
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                new_token = data.get('access_token')
                if new_token:
                    # If Zoho also returns a new refresh_token, persist it
                    new_refresh = data.get('refresh_token')
                    if new_refresh and new_refresh != refresh_token:
                        settings.SITE24X7_REFRESH_TOKEN = new_refresh
                        _persist_to_env('SITE24X7_REFRESH_TOKEN', new_refresh)
                        logger.info('[Site24x7] Refresh token also rotated and persisted.')
                    return new_token
                logger.error(f'[Site24x7] Refresh response missing access_token: {data}')
            else:
                logger.error(
                    f'[Site24x7] Token refresh failed — '
                    f'HTTP {resp.status_code}: {resp.text[:200]}'
                )
        except Exception as e:
            logger.error(f'[Site24x7] Token refresh exception: {e}')

        return None

    # ── Legacy compat ─────────────────────────────────────────────────────

    def refresh_access_token(self) -> str:
        """Legacy method — raises on failure (kept for backward compat)."""
        result = self._do_refresh()
        if not result:
            raise Exception(
                'Site24x7 token refresh failed. '
                'Check ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET in .env '
                '(get them from https://api-console.zoho.in).'
            )
        return result

    @staticmethod
    def encode_zaaid(zaaid):
        import base64
        return base64.b64encode(str(zaaid).encode()).decode()

    @staticmethod
    def decode_zaaid(encoded_zaaid):
        import base64
        try:
            return base64.b64decode(encoded_zaaid).decode()
        except Exception:
            return encoded_zaaid
