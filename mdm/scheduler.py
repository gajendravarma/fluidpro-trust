"""
Background sync scheduler for MDM (ManageEngine MDM).
Runs sync every SYNC_INTERVAL_MINUTES using a daemon thread.
"""
import threading
import time
import logging

logger = logging.getLogger(__name__)

SYNC_INTERVAL_MINUTES = 5
_scheduler_started = False
_lock = threading.Lock()


def _sync_loop():
    time.sleep(45)  # slightly offset from Pulseway to avoid simultaneous API bursts
    consecutive_failures = 0
    while True:
        try:
            from mdm.manageengine_mdm_service import ManageEngineMDMService
            from mdm.models import MdmCustomer
            from django.db import connection
            # Ensure WAL mode is active on this thread's connection
            with connection.cursor() as cur:
                cur.execute('PRAGMA journal_mode=WAL;')
                cur.execute('PRAGMA synchronous=NORMAL;')
                cur.execute('PRAGMA busy_timeout=30000;')
            svc = ManageEngineMDMService()
            customers = list(MdmCustomer.objects.all())  # fetch list before write tx
            logger.info(f"[MDM Scheduler] Syncing {len(customers)} customers...")
            total_created = total_updated = 0
            for customer in customers:
                try:
                    created, updated, _ = svc.sync_devices_for_customer(customer)
                    total_created += created
                    total_updated += updated
                except Exception as ce:
                    logger.error(f"[MDM Scheduler] Customer {customer}: {ce}")
            logger.info(f"[MDM Scheduler] Done — {total_created} created, {total_updated} updated.")
            consecutive_failures = 0
        except Exception as e:
            consecutive_failures += 1
            backoff = min(2 ** (consecutive_failures - 1), 8)
            logger.error(
                f"[MDM Scheduler] Sync error (failure #{consecutive_failures}, "
                f"next retry in {SYNC_INTERVAL_MINUTES * backoff} min): {e}"
            )
            time.sleep(SYNC_INTERVAL_MINUTES * backoff * 60)
            continue
        time.sleep(SYNC_INTERVAL_MINUTES * 60)


def start():
    global _scheduler_started
    with _lock:
        if _scheduler_started:
            return
        t = threading.Thread(target=_sync_loop, daemon=True, name="mdm-sync")
        t.start()
        _scheduler_started = True
        logger.info(f"[MDM Scheduler] Started — syncing every {SYNC_INTERVAL_MINUTES} min.")
