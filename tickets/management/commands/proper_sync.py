
from django.core.management.base import BaseCommand
from tickets.proper_sync import ProperSyncService
from django.db.models import Count
from tickets.models import TicketCache

class Command(BaseCommand):
    help = 'Properly sync all tickets from ManageEngine API'
    
    def add_arguments(self, parser):
        parser.add_argument('--incremental', action='store_true', help='Incremental sync only')
    
    def handle(self, *args, **options):
        service = ProperSyncService()
        
        if options['incremental']:
            count = service.incremental_sync()
            self.stdout.write(f"Incremental sync: {count} tickets")
        else:
            count = service.sync_all_tickets()
            self.stdout.write(f"Full sync: {count} tickets")
        
        # Show status counts
        status_counts = TicketCache.objects.values('status').annotate(count=Count('id'))
        
        open_count = 0
        hold_count = 0
        
        self.stdout.write("\nStatus counts:")
        for item in status_counts:
            status = item['status']
            count = item['count']
            
            if status == 'Open':
                open_count = count
            elif 'Hold' in status or status == 'Onhold':
                hold_count += count
                
            self.stdout.write(f"  {status}: {count}")
        
        total_active = open_count + hold_count
        self.stdout.write(
            self.style.SUCCESS(f"\n✅ Active tickets: {total_active} (Open: {open_count}, Hold: {hold_count})")
        )
