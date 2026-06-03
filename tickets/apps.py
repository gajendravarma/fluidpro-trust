from django.apps import AppConfig

class TicketsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tickets'
    
    def ready(self):
        # Start auto-sync when Django starts
        try:
            from .auto_sync import auto_sync
            auto_sync.start()
        except Exception as e:
            print(f"Failed to start auto-sync: {e}")
