import threading
import time
import requests
import json
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import OperationalError, transaction
from tickets.models import TicketCache, SyncStatus
from tickets.services import ManageEngineService

logger = logging.getLogger(__name__)

_sync_lock = threading.Lock()  # Prevents concurrent sync runs

# ManageEngine API caps page size at 100 regardless of what you request
ME_PAGE_SIZE = 100

# Statuses that are permanently terminal — no need to reconcile these
TERMINAL_STATUSES = {'Closed', 'Resolved', 'Cancelled'}

# How long between full reconcile runs (seconds).  Default: 24 hours.
RECONCILE_INTERVAL_SECONDS = 24 * 3600


class AutoSyncService:
    def __init__(self, sync_interval_minutes=5):
        self.sync_interval = sync_interval_minutes * 60  # Convert to seconds
        self.running = False
        self.thread = None

    def start(self):
        """Start auto-sync in background thread"""
        if not self.running:
            # Fix stuck 'running' status from a previous crashed sync
            try:
                sync_status = SyncStatus.objects.filter(id=1).first()
                if sync_status and sync_status.sync_status == 'running':
                    if sync_status.last_sync_time and (
                        timezone.now() - sync_status.last_sync_time > timedelta(minutes=30)
                    ):
                        sync_status.sync_status = 'error'
                        sync_status.error_message = 'Reset: was stuck in running state on startup'
                        sync_status.save()
                        logger.warning("Cleared stuck 'running' sync status on startup")
            except Exception as e:
                logger.warning(f"Could not check/fix sync status on startup: {e}")

            self.running = True
            self.thread = threading.Thread(target=self._sync_loop, daemon=True)
            self.thread.start()
            logger.info(f"Auto-sync started with {self.sync_interval / 60:.0f} minute interval")

    def stop(self):
        """Stop auto-sync"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Auto-sync stopped")

    # ──────────────────────────────────────────────
    # Main loop
    # ──────────────────────────────────────────────

    def _sync_loop(self):
        """
        Main loop:
          - Runs an incremental sync immediately on startup, then every 5 minutes.
          - Once per 24 hours (after a regular sync completes) runs the full
            reconcile pass that catches deleted/ghost tickets.
        """
        # Run immediately on startup to catch up any missed period
        try:
            if _sync_lock.acquire(blocking=False):
                try:
                    self._perform_smart_sync()
                    self._maybe_reconcile()
                finally:
                    _sync_lock.release()
            else:
                logger.warning("Sync already running at startup, skipping initial run")
        except Exception as e:
            logger.error(f"Auto-sync startup run error: {e}")

        while self.running:
            try:
                time.sleep(self.sync_interval)
                if not self.running:
                    break
                if _sync_lock.acquire(blocking=False):
                    try:
                        self._perform_smart_sync()
                        self._maybe_reconcile()
                    finally:
                        _sync_lock.release()
                else:
                    logger.warning("Sync already running, skipping this cycle")
            except Exception as e:
                logger.error(f"Auto-sync error: {e}")
                time.sleep(60)

    def _maybe_reconcile(self):
        """Run the daily reconcile only when 24 h have elapsed since the last run."""
        try:
            sync_status = SyncStatus.objects.filter(id=1).first()
            last_reconcile = sync_status.last_reconcile_time if sync_status else None
            if last_reconcile:
                elapsed = (datetime.now() - last_reconcile).total_seconds()
                if elapsed < RECONCILE_INTERVAL_SECONDS:
                    logger.debug(
                        f"Reconcile not due yet ({elapsed / 3600:.1f}h elapsed, "
                        f"next in {(RECONCILE_INTERVAL_SECONDS - elapsed) / 3600:.1f}h)"
                    )
                    return
            self._reconcile_deleted_tickets()
        except Exception as e:
            logger.error(f"Error in _maybe_reconcile: {e}")

    # ──────────────────────────────────────────────
    # Tier 1 — incremental sync (every 5 min)
    # ──────────────────────────────────────────────

    def _perform_smart_sync(self):
        """Incremental sync — fetch all tickets changed/created since last sync."""
        logger.info("Starting smart sync...")

        try:
            sync_status = SyncStatus.objects.filter(id=1).first()
            if sync_status and sync_status.sync_status == 'completed' and sync_status.last_sync_time:
                last_sync_time = sync_status.last_sync_time
            else:
                last_sync_time = timezone.now() - timedelta(days=7)
        except Exception:
            last_sync_time = timezone.now() - timedelta(days=7)

        gap_hours = (timezone.now() - last_sync_time).total_seconds() / 3600
        logger.info(f"Last successful sync was {gap_hours:.1f}h ago — catching up from that point")

        sync_status, _ = SyncStatus.objects.get_or_create(
            id=1, defaults={'last_sync_time': timezone.now(), 'sync_status': 'running'}
        )
        sync_status.sync_status = 'running'
        sync_status.save()

        try:
            me_service = ManageEngineService()

            self._sync_updated_since(me_service, last_sync_time)

            api_total = self._get_api_total_count(me_service)
            local_total = TicketCache.objects.count()
            logger.info(f"API total: {api_total}, Local total: {local_total}")
            if api_total > local_total:
                self._sync_missing_tickets(me_service)

            sync_status.last_sync_time = timezone.now()
            sync_status.total_tickets_synced = TicketCache.objects.count()
            sync_status.sync_status = 'completed'
            sync_status.error_message = ''
            sync_status.save()

            logger.info("Smart sync completed successfully")

        except Exception as e:
            sync_status.sync_status = 'error'
            sync_status.error_message = str(e)
            sync_status.save()
            logger.error(f"Smart sync failed: {e}")

    # ──────────────────────────────────────────────
    # Tier 2 — daily reconcile (ghost-ticket purge)
    # ──────────────────────────────────────────────

    def _reconcile_deleted_tickets(self, force=False):
        """
        Permanent fix for deleted/ghost tickets.

        For every ticket in the local DB whose status is NOT in TERMINAL_STATUSES
        (i.e. Open, In Progress, On Hold, Pending …), we call ME API individually:

          • HTTP 404  → ticket was deleted in ME → delete from DB
          • HTTP 200, status changed → update DB with latest ME data (self-healing)
          • HTTP 200, same status → no change needed

        Runs automatically once per 24 hours via _maybe_reconcile().
        Can also be triggered manually via the `reconcile_tickets` management command.
        """
        active_tickets = list(
            TicketCache.objects
            .exclude(status__in=TERMINAL_STATUSES)
            .values_list('ticket_id', 'status')
        )
        total = len(active_tickets)
        deleted_count = 0
        updated_count = 0
        error_count = 0

        logger.info(f"[Reconcile] Starting — {total} active (non-terminal) tickets to verify")

        me_service = ManageEngineService()

        for ticket_id, db_status in active_tickets:
            try:
                url = f"{me_service.base_url}/requests/{ticket_id}"
                resp = requests.get(url, headers=me_service.headers, timeout=15)

                if resp.status_code == 404:
                    # Ticket was deleted in ManageEngine
                    TicketCache.objects.filter(ticket_id=ticket_id).delete()
                    deleted_count += 1
                    logger.info(
                        f"[Reconcile] Purged ghost ticket {ticket_id} "
                        f"(was '{db_status}' in DB, 404 in ME)"
                    )

                elif resp.status_code == 200:
                    req = resp.json().get('request', {})
                    api_status = (req.get('status') or {}).get('name', '')
                    if api_status and api_status != db_status:
                        self._sync_single_ticket(req)
                        updated_count += 1
                        logger.info(
                            f"[Reconcile] Self-healed ticket {ticket_id}: "
                            f"'{db_status}' -> '{api_status}'"
                        )
                else:
                    logger.warning(
                        f"[Reconcile] Unexpected HTTP {resp.status_code} for ticket {ticket_id}"
                    )
                    error_count += 1

                # Gentle pacing — avoid flooding the ME API
                time.sleep(0.15)

            except Exception as e:
                logger.warning(f"[Reconcile] Error checking ticket {ticket_id}: {e}")
                error_count += 1

        logger.info(
            f"[Reconcile] Done — {deleted_count} purged, {updated_count} self-healed, "
            f"{error_count} errors, {total - deleted_count - updated_count - error_count} unchanged"
        )

        # Stamp the reconcile time so _maybe_reconcile knows when we last ran
        try:
            SyncStatus.objects.filter(id=1).update(last_reconcile_time=datetime.now())
        except Exception as e:
            logger.warning(f"[Reconcile] Could not update last_reconcile_time: {e}")

        return {'total': total, 'deleted': deleted_count, 'updated': updated_count, 'errors': error_count}

    # ──────────────────────────────────────────────
    # Helpers shared by both tiers
    # ──────────────────────────────────────────────

    def _get_api_total_count(self, me_service):
        url = f"{me_service.base_url}/requests"
        input_data = {
            "list_info": {
                "row_count": 1,
                "start_index": 1,
                "get_total_count": True,
                "fields_required": ["id"]
            }
        }
        try:
            response = requests.get(
                url, headers=me_service.headers,
                params={'input_data': json.dumps(input_data)},
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get('list_info', {}).get('total_count', 0)
        except Exception as e:
            logger.warning(f"Could not get API total count: {e}")
        return 0

    def _sync_updated_since(self, me_service, since_time):
        """
        Fetch all tickets whose last_updated_time or created_time >= since_time
        and upsert them.  Paginates fully (100 rows per page — ME API hard cap).
        """
        since_ms = int(since_time.timestamp() * 1000)
        total_synced = 0

        for sort_field in ('last_updated_time', 'created_time'):
            start_index = 1
            while True:
                input_data = {
                    "list_info": {
                        "row_count": ME_PAGE_SIZE,
                        "start_index": start_index,
                        "sort_field": sort_field,
                        "sort_order": "desc",
                        "search_criteria": [
                            {
                                "field": sort_field,
                                "condition": "greater than",
                                "value": str(since_ms),
                                "logical_operator": "AND"
                            }
                        ],
                        "fields_required": [
                            "id", "subject", "description", "status", "priority",
                            "category", "requester", "technician", "account",
                            "created_time", "last_updated_time", "resolved_time"
                        ]
                    }
                }

                try:
                    response = requests.get(
                        f"{me_service.base_url}/requests",
                        headers=me_service.headers,
                        params={'input_data': json.dumps(input_data)},
                        timeout=30
                    )
                except Exception as e:
                    logger.error(f"Network error fetching {sort_field} page {start_index}: {e}")
                    break

                if response.status_code != 200:
                    logger.error(f"ME API returned {response.status_code} for {sort_field} page {start_index}")
                    break

                data = response.json()
                tickets = data.get('requests', [])
                if not tickets:
                    break

                # Batch-prepare all defaults first (no DB I/O), then write
                # the whole page in one atomic transaction.  This cuts lock
                # acquisitions from N-per-page down to 1-per-page.
                batch = [self._prepare_ticket_defaults(t) for t in tickets]
                self._batch_upsert(batch)
                total_synced += len(batch)

                if len(tickets) < ME_PAGE_SIZE:
                    break

                start_index += ME_PAGE_SIZE

        logger.info(f"_sync_updated_since: {total_synced} ticket upserts (since {since_time})")

    def _sync_missing_tickets(self, me_service):
        """
        Walk through all API tickets newest-first and insert any that are
        missing from the local DB.  Stops early once a full page of already-known
        tickets is hit.
        """
        logger.info("Checking for tickets missing from local DB...")
        inserted = 0
        start_index = 1

        while True:
            input_data = {
                "list_info": {
                    "row_count": ME_PAGE_SIZE,
                    "start_index": start_index,
                    "sort_field": "created_time",
                    "sort_order": "desc",
                    "fields_required": [
                        "id", "subject", "description", "status", "priority",
                        "category", "requester", "technician", "account",
                        "created_time", "last_updated_time", "resolved_time"
                    ]
                }
            }

            try:
                response = requests.get(
                    f"{me_service.base_url}/requests",
                    headers=me_service.headers,
                    params={'input_data': json.dumps(input_data)},
                    timeout=30
                )
            except Exception as e:
                logger.error(f"Network error in _sync_missing_tickets page {start_index}: {e}")
                break

            if response.status_code != 200:
                break

            tickets = response.json().get('requests', [])
            if not tickets:
                break

            # One query to find which IDs already exist in this page
            page_ids = [str(t.get('id', '')) for t in tickets if t.get('id')]
            existing_ids = set(
                TicketCache.objects.filter(ticket_id__in=page_ids)
                    .values_list('ticket_id', flat=True)
            )
            missing = [t for t in tickets if str(t.get('id', '')) not in existing_ids]
            if not missing:
                break  # full page already known — stop scanning

            batch = [self._prepare_ticket_defaults(t) for t in missing]
            self._batch_upsert(batch)
            inserted += len(batch)

            if len(tickets) < ME_PAGE_SIZE:
                break

            start_index += ME_PAGE_SIZE

        if inserted:
            logger.info(f"_sync_missing_tickets: inserted {inserted} previously missing tickets")

    def _prepare_ticket_defaults(self, ticket_data) -> tuple[str, dict] | None:
        """Parse one ticket API dict into (ticket_id, defaults). Returns None if no id."""
        ticket_id = str(ticket_data.get('id', ''))
        if not ticket_id:
            return None

        status_data = ticket_data.get('status', {})
        status = status_data.get('name', 'Unknown') if isinstance(status_data, dict) else str(status_data)

        priority_data = ticket_data.get('priority', {})
        priority = priority_data.get('name', 'Medium') if isinstance(priority_data, dict) else str(priority_data)

        category_data = ticket_data.get('category', {})
        category = category_data.get('name', '') if isinstance(category_data, dict) else str(category_data)

        requester_data = ticket_data.get('requester', {})
        requester_name = requester_data.get('name', '') if isinstance(requester_data, dict) else ''
        requester_email = requester_data.get('email_id', '') if isinstance(requester_data, dict) else ''

        technician_data = ticket_data.get('technician', {})
        technician_name = technician_data.get('name', '') if isinstance(technician_data, dict) else ''

        account_data = ticket_data.get('account', {})
        company_name = account_data.get('name', '') if isinstance(account_data, dict) else ''

        return ticket_id, {
            'subject': ticket_data.get('subject') or '',
            'description': ticket_data.get('description') or '',
            'status': status,
            'priority': priority,
            'category': category,
            'requester_name': requester_name,
            'requester_email': requester_email,
            'technician_name': technician_name,
            'company_name': company_name,
            'created_at': self._parse_timestamp(ticket_data.get('created_time', {})) or datetime.now(),
            'updated_at': self._parse_timestamp(ticket_data.get('last_updated_time', {})) or datetime.now(),
            'resolved_at': self._parse_timestamp(ticket_data.get('resolved_time', {})),
        }

    def _batch_upsert(self, batch: list):
        """Write a list of (ticket_id, defaults) tuples in a single transaction."""
        if not batch:
            return
        records = [r for r in batch if r]  # drop any None entries
        if not records:
            return
        with transaction.atomic():
            for ticket_id, defaults in records:
                TicketCache.objects.update_or_create(ticket_id=ticket_id, defaults=defaults)

    def _sync_single_ticket(self, ticket_data):
        """Upsert one ticket (used by reconcile). Delegates to _batch_upsert."""
        prepared = self._prepare_ticket_defaults(ticket_data)
        if prepared:
            self._batch_upsert([prepared])

        return False

    def _parse_timestamp(self, time_data):
        """Parse ManageEngine timestamp (milliseconds since epoch) as naive local datetime.
        USE_TZ=False in this project — SQLite requires naive datetimes."""
        if not time_data or not isinstance(time_data, dict):
            return None
        try:
            ts = time_data.get('value')
            if ts:
                if isinstance(ts, str):
                    ts = int(ts)
                return datetime.fromtimestamp(ts / 1000)
        except Exception:
            pass
        return None


# Global auto-sync instance
auto_sync = AutoSyncService(sync_interval_minutes=5)
