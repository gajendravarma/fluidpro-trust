
def get_corrected_status_counts(status_counts):
    """
    Correct status mapping based on actual ManageEngine statuses
    """
    # Map all "On Hold" variations to hold_tickets
    hold_statuses = [
        'Onhold',
        'On Hold - For Spare', 
        'On Hold – Business Dependency',
        'On Hold – User Dependency',
        'On Hold - Digtinctive Backend',
        'On Hold - For Commercial Approval'
    ]
    
    open_tickets = status_counts.get('Open', 0)
    pending_tickets = status_counts.get('Pending', 0)  # Usually 0 in ManageEngine
    in_progress_tickets = status_counts.get('In Progress', 0)
    resolved_tickets = status_counts.get('Resolved', 0)
    closed_tickets = status_counts.get('Closed', 0)
    cancelled_tickets = status_counts.get('Cancelled', 0)
    under_observation = status_counts.get('Under Observation', 0)
    
    # Sum all hold variations
    hold_tickets = sum(status_counts.get(status, 0) for status in hold_statuses)
    
    return {
        'open': open_tickets,
        'pending': pending_tickets,
        'in_progress': in_progress_tickets,
        'hold': hold_tickets,
        'resolved': resolved_tickets,
        'closed': closed_tickets,
        'cancelled': cancelled_tickets,
        'under_observation': under_observation,
        'total_active': open_tickets + pending_tickets + in_progress_tickets + hold_tickets + under_observation
    }
