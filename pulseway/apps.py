from django.apps import AppConfig


class PulsewayConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pulseway'

    def ready(self):
        # Only start the scheduler in the main process (not in manage.py commands
        # like makemigrations, collectstatic, shell, etc.)
        import sys
        if 'runserver' in sys.argv or 'gunicorn' in sys.modules or 'uvicorn' in sys.modules:
            from pulseway import scheduler
            scheduler.start()
