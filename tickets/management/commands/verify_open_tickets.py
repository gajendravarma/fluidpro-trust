"""
Management command: verify_open_tickets

Re-fetches every ticket in local DB that has status 'Open' (or any non-terminal
status) directly from ManageEngine and updates its status if it has changed.

Run this to fix stale data immediately:
    python manage.py verify_open_tickets

Add to cron alongside sync_incremental to keep data accurate.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
import requests
import json
import time


OPEN_STATUSES = {'open', 'in progress', 'assigned', 'under observation'}


class Command(BaseCommand):
    help = 'Re-verify Open tickets against ManageEngine API and update stale statuses'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=0,
            help='Only check Open tickets not updated in this many days (0 = all Open tickets)'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print what would change without writing to DB'
        )

    def handle(self, *args, **options):
        from tickets.models import TicketCache
        from tickets.services import ManageEngineService
        from datetime import timedelta

        dry_run = options['dry_run']
        days = options['days']

        svc = ManageEngineService()

        qs = TicketCache.objects.filter(status__iexact='open')
        if days:
            cutoff = timezone.now() - timedelta(days=days)
            qs = qs.filter(updated_at__lt=cutoff)

        total = qs.count()
        self.stdout.write(f'Verifying {total} Open tickets against ManageEngine API...')
        if dry_run:
            self.stdout.write('  (DRY RUN — no changes will be written)')

        changed = 0
        errors = 0
        checked = 0

        for ticket in qs.iterator():
            checked += 1
            try:
                resp = requests.get(
                    f'{svc.base_url}/requests/{ticket.ticket_id}',
                    headers=svc.headers,
                    timeout=10
                )
                if resp.status_code != 200:
                    errors += 1
                    continue

                data = resp.json().get('request', {})
                api_status_raw = data.get('status', {})
                api_status = (
                    api_status_raw.get('name', '')
                    if isinstance(api_status_raw, dict)
                    else str(api_status_raw)
                )

                if not api_status:
                    errors += 1
                    continue

                if api_status.lower() != ticket.status.lower():
                    self.stdout.write(
                        f'  #{ticket.ticket_id}: "{ticket.status}" -> "{api_status}" '
                        f'(last_updated: {str(ticket.updated_at)[:19]})'
                    )
                    if not dry_run:
                        # Also grab updated_at from API
                        updated_raw = data.get('last_updated_time', {})
                        resolved_raw = data.get('resolved_time', {})

                        updated_at = self._parse_ts(updated_raw) or ticket.updated_at
                        resolved_at = self._parse_ts(resolved_raw)

                        ticket.status = api_status
                        ticket.updated_at = updated_at
                        if resolved_at:
                            ticket.resolved_at = resolved_at
                        ticket.save(update_fields=['status', 'updated_at', 'resolved_at'])
                    changed += 1

                # Throttle: 10 requests/sec to avoid hitting ME API rate limits
                if checked % 10 == 0:
                    time.sleep(1)

            except Exception as e:
                errors += 1
                if checked <= 5:  # Only print first few errors to avoid noise
                    self.stdout.write(f'  Error checking #{ticket.ticket_id}: {e}')

        action = 'Would update' if dry_run else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Checked: {checked} | {action}: {changed} | Errors: {errors}'
        ))

    def _parse_ts(self, time_data):
        if not time_data or not isinstance(time_data, dict):
            return None
        try:
            val = time_data.get('value')
            if val:
                from datetime import datetime
                return datetime.fromtimestamp(int(val) / 1000)
        except Exception:
            pass
        return None
