"""
Management command: reconcile_tickets

Manually trigger the daily reconcile pass.  Normally this runs automatically
inside the auto-sync thread once every 24 hours, but you can also run it
on-demand:

    python manage.py reconcile_tickets

This will:
  1. Iterate over every non-terminal ticket in the local DB
     (status NOT IN Closed / Resolved / Cancelled)
  2. Call GET /api/v3/requests/<id> on the ME API for each one
  3. HTTP 404  → ticket was deleted in ME → delete from local DB
  4. HTTP 200, status changed → update local DB (self-heal drift)
  5. HTTP 200, same status   → no action needed

Use --dry-run to see what would happen without changing anything.
"""

from django.core.management.base import BaseCommand
from tickets.auto_sync import AutoSyncService, TERMINAL_STATUSES
from tickets.models import TicketCache, SyncStatus
from tickets.services import ManageEngineService
import requests
import time
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Reconcile local DB against ME API — purge deleted tickets and self-heal stale statuses'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without writing to the DB',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no DB changes will be made\n'))

        active_tickets = list(
            TicketCache.objects
            .exclude(status__in=TERMINAL_STATUSES)
            .values_list('ticket_id', 'status')
        )
        total = len(active_tickets)
        self.stdout.write(f'Active (non-terminal) tickets to verify: {total}\n')

        me_service = ManageEngineService()
        svc = AutoSyncService()

        deleted_count = 0
        updated_count = 0
        error_count = 0

        for ticket_id, db_status in active_tickets:
            outcome = 'ok'
            try:
                url = f"{me_service.base_url}/requests/{ticket_id}"
                resp = requests.get(url, headers=me_service.headers, timeout=15)

                if resp.status_code == 404:
                    outcome = 'deleted'
                    deleted_count += 1
                    if not dry_run:
                        TicketCache.objects.filter(ticket_id=ticket_id).delete()

                elif resp.status_code == 200:
                    req = resp.json().get('request', {})
                    api_status = (req.get('status') or {}).get('name', '')
                    if api_status and api_status != db_status:
                        outcome = f'heal:{db_status}->{api_status}'
                        updated_count += 1
                        if not dry_run:
                            svc._sync_single_ticket(req)
                else:
                    outcome = f'http_{resp.status_code}'
                    error_count += 1

                time.sleep(0.15)

            except Exception as e:
                outcome = f'error:{e}'
                error_count += 1

            # Print outcome — use only ASCII-safe characters to avoid Windows charmap issues
            if outcome == 'deleted':
                self.stdout.write(self.style.ERROR(
                    f'  PURGE  ticket {ticket_id} (was "{db_status}") -- deleted in ME'
                ))
            elif outcome.startswith('heal:'):
                self.stdout.write(self.style.WARNING(
                    f'  HEAL   ticket {ticket_id}: {outcome[5:]}'
                ))
            elif outcome != 'ok':
                self.stdout.write(self.style.WARNING(
                    f'  WARN   ticket {ticket_id}: {outcome}'
                ))

        # Stamp last_reconcile_time (skip in dry-run)
        if not dry_run:
            from datetime import datetime
            SyncStatus.objects.filter(id=1).update(last_reconcile_time=datetime.now())

        self.stdout.write('\n')
        self.stdout.write(self.style.SUCCESS(
            f'Reconcile complete: '
            f'{deleted_count} purged, '
            f'{updated_count} self-healed, '
            f'{error_count} errors, '
            f'{total - deleted_count - updated_count - error_count} unchanged'
            + (' (DRY RUN — nothing saved)' if dry_run else '')
        ))
