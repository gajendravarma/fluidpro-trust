from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from rbac.models import PasswordResetToken

class Command(BaseCommand):
    help = 'Clean up expired password reset tokens'

    def handle(self, *args, **options):
        # Delete tokens older than 24 hours
        expired_time = timezone.now() - timedelta(hours=24)
        expired_tokens = PasswordResetToken.objects.filter(created_at__lt=expired_time)
        count = expired_tokens.count()
        expired_tokens.delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully cleaned up {count} expired password reset tokens')
        )
