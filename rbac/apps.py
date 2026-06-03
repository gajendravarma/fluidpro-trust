from django.apps import AppConfig


class RbacConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rbac'

    def ready(self):
        # Enable SQLite WAL mode for every new connection.
        # WAL allows concurrent reads while a write is in progress, eliminating
        # "database is locked" errors caused by the background sync threads.
        from django.db.backends.signals import connection_created

        def _enable_wal(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                cursor = connection.cursor()
                cursor.execute('PRAGMA journal_mode=WAL;')
                cursor.execute('PRAGMA synchronous=NORMAL;')
                cursor.execute('PRAGMA cache_size=-32000;')    # 32 MB page cache
                cursor.execute('PRAGMA busy_timeout=30000;')   # 30 s SQLite-level retry

        connection_created.connect(_enable_wal)
