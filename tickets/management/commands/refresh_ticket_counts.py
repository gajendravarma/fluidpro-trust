
from django.core.management.base import BaseCommand
from tickets.realtime_service import RealTimeTicketService

class Command(BaseCommand):
    help = 'Refresh ticket count cache'
    
    def handle(self, *args, **options):
        service = RealTimeTicketService()
        service.clear_cache()
        counts = service.get_dashboard_counts()
        
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Cache refreshed! Active tickets: {counts['total_active']} "
                f"(Open: {counts['open']}, Hold: {counts['hold']})"
            )
        )
