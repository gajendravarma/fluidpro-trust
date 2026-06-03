from django.db.backends.signals import connection_created


def _set_sqlite_wal(sender, connection, **kwargs):
    """
    Enable WAL journal mode and set busy_timeout on every new SQLite connection.

    WAL (Write-Ahead Log) allows concurrent reads while a write is in progress,
    which eliminates most "database is locked" errors caused by the background
    sync threads and chatbot cache refresh running alongside normal requests.
    """
    if connection.vendor == 'sqlite':
        cursor = connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('PRAGMA synchronous=NORMAL;')
        cursor.execute('PRAGMA busy_timeout=30000;')  # 30 s SQLite-level wait


connection_created.connect(_set_sqlite_wal)
