"""
Pulseway background sync scheduler — self-terminating singleton.

How it works:
  1. Each start() call mints a new UUID token and writes it to the
     PulsewaySync table (sync_type='_scheduler_token').
  2. Every running thread checks the DB token every 60 seconds during
     its sleep period.
  3. If the DB token no longer matches this thread's token, the thread
     knows a newer scheduler has taken over and exits cleanly.

Result: calling start() multiple times (e.g. Django reloads the module
after a code change, or AppConfig.ready() fires twice) automatically
stops the old thread within 60 seconds — no server restart needed.
"""

import threading
import time
import uuid
import logging

logger = logging.getLogger(__name__)

SYNC_INTERVAL_MINUTES = 30   # full sync including online/offline status
STATUS_SYNC_MINUTES   = SYNC_INTERVAL_MINUTES   # alias for display
LIST_SYNC_MINUTES     = SYNC_INTERVAL_MINUTES   # alias for display

_lock  = threading.Lock()
_token = None   # UUID of the currently registered scheduler


# ── DB token helpers ──────────────────────────────────────────────────────────

def _write_token(token: str):
    """Persist this scheduler's token to the DB, superseding any previous one."""
    try:
        from pulseway.models import PulsewaySync
        PulsewaySync.objects.update_or_create(
            sync_type='_scheduler_token',
            defaults={'status': 'active', 'error_message': token, 'records_synced': 0},
        )
        logger.info(f'[Pulseway Scheduler] Token registered: {token[:8]}...')
    except Exception as e:
        logger.warning(f'[Pulseway Scheduler] Could not write token: {e}')


def _token_is_current(token: str) -> bool:
    """Return True if this thread is still the active scheduler."""
    try:
        from pulseway.models import PulsewaySync
        record = PulsewaySync.objects.filter(sync_type='_scheduler_token').first()
        if record is None:
            return True   # no record yet — assume we are current
        return record.error_message == token
    except Exception:
        return True   # DB unreachable — keep running rather than die silently


def _sleep_interruptible(total_seconds: int, my_token: str) -> bool:
    """
    Sleep in 60-second chunks, checking the token each time.
    Returns True if we should continue, False if we should stop.
    """
    slept = 0
    while slept < total_seconds:
        chunk = min(60, total_seconds - slept)
        time.sleep(chunk)
        slept += chunk
        if not _token_is_current(my_token):
            return False   # stop signal
    return True


# ── WAL pragma ────────────────────────────────────────────────────────────────

def _pragma_wal(connection):
    try:
        with connection.cursor() as cur:
            cur.execute('PRAGMA journal_mode=WAL;')
            cur.execute('PRAGMA synchronous=NORMAL;')
            cur.execute('PRAGMA busy_timeout=30000;')
    except Exception:
        pass


# ── Main sync loop ────────────────────────────────────────────────────────────

def _sync_loop(my_token: str):
    """
    Daemon thread: sync every SYNC_INTERVAL_MINUTES.
    Self-terminates when a newer scheduler token is detected.
    """
    logger.info(f'[Pulseway Scheduler] Thread {my_token[:8]}... starting (30 s warm-up).')

    # Warm-up: give Django ORM time to be ready, but still check token
    if not _sleep_interruptible(30, my_token):
        logger.info(f'[Pulseway Scheduler] Thread {my_token[:8]}... superseded during warm-up. Stopping.')
        return

    consecutive_failures = 0

    while True:
        # ── Token check before each sync ─────────────────────────────────────
        if not _token_is_current(my_token):
            logger.info(
                f'[Pulseway Scheduler] Thread {my_token[:8]}... detected a newer scheduler. '
                f'Self-terminating — no server restart needed.'
            )
            return

        # ── Run sync ─────────────────────────────────────────────────────────
        try:
            from pulseway.local_service import PulsewayLocalService
            from django.db import connection
            _pragma_wal(connection)
            svc = PulsewayLocalService()
            logger.info(f'[Pulseway Sync] Starting full sync (token={my_token[:8]}...).')
            svc.sync_organizations()
            svc.sync_devices()
            logger.info('[Pulseway Sync] Done.')
            consecutive_failures = 0
        except Exception as e:
            consecutive_failures += 1
            backoff = min(2 ** (consecutive_failures - 1), 8)
            wait = SYNC_INTERVAL_MINUTES * backoff * 60
            logger.error(
                f'[Pulseway Sync] Error #{consecutive_failures} — '
                f'retrying in {SYNC_INTERVAL_MINUTES * backoff} min: {e}'
            )
            if not _sleep_interruptible(wait, my_token):
                logger.info(f'[Pulseway Scheduler] Thread {my_token[:8]}... superseded during backoff. Stopping.')
                return
            continue

        # ── Wait for next cycle, checking token every 60 s ───────────────────
        if not _sleep_interruptible(SYNC_INTERVAL_MINUTES * 60, my_token):
            logger.info(f'[Pulseway Scheduler] Thread {my_token[:8]}... superseded during sleep. Stopping.')
            return


# ── Public API ────────────────────────────────────────────────────────────────

def start():
    """
    Start a new scheduler instance.

    Safe to call multiple times — each call mints a new token, causing
    any previous scheduler thread to self-terminate within 60 seconds.
    No server restart required after code changes.
    """
    global _token

    with _lock:
        my_token = str(uuid.uuid4())
        _token   = my_token

    # Write token to DB first so old threads detect the change immediately
    _write_token(my_token)

    t = threading.Thread(
        target=_sync_loop,
        args=(my_token,),
        daemon=True,
        name=f'pulseway-sync-{my_token[:8]}',
    )
    t.start()
    logger.info(
        f'[Pulseway Scheduler] Started (token={my_token[:8]}...) — '
        f'full sync every {SYNC_INTERVAL_MINUTES} min. '
        f'Previous scheduler threads will self-terminate within 60 s.'
    )
