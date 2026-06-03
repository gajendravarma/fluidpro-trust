from django.apps import AppConfig


class MdmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mdm'

    def ready(self):
        # MDM data is fetched live from the API on each request — no background
        # sync needed, so the scheduler is intentionally disabled.
        pass
