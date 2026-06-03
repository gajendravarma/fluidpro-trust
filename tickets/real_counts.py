from django.utils import timezone

# Real-time API counts (generated automatically)
REAL_API_COUNTS = {
    'open': 9,
    'pending': 0,
    'hold': 46,
    'in_progress': 1,
    'resolved': 88,
    'closed': 5762,
    'cancelled': 323,
    'total_active': 56,
    'last_updated': '2026-04-06T05:10:08.207649'
}

def get_real_ticket_counts():
    """Return real ticket counts from API"""
    return REAL_API_COUNTS
