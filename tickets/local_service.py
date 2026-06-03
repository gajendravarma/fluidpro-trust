from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from .models import TicketCache, SyncStatus

class LocalTicketService:
    """Fast service to fetch ticket data from local database table"""
    
    def get_dashboard_data(self, company_filter=None, technician_filter=None,
                           allowed_companies=None):
        """Get all dashboard data from local database - super fast.

        allowed_companies: set of company names the technician may access.
            None  → no restriction (admin / unrestricted tech)
            set() → restrict to those companies only (inhouse/limited tech)
        """
        queryset = TicketCache.objects.all()

        # Technician company restriction takes priority over a free-text filter
        if allowed_companies is not None:
            queryset = queryset.filter(company_name__in=allowed_companies)
        elif company_filter:
            queryset = queryset.filter(company_name__icontains=company_filter)

        if technician_filter:
            queryset = queryset.filter(technician_name__iexact=technician_filter)
        
        # Get counts by status
        status_counts = queryset.values('status').annotate(count=Count('id'))
        
        # Get counts by priority
        priority_counts = queryset.values('priority').annotate(count=Count('id'))
        
        # Get recent tickets
        recent_tickets = queryset.order_by('-created_at')[:10]
        
        # Get monthly stats
        last_6_months = timezone.now() - timedelta(days=180)
        monthly_tickets = queryset.filter(created_at__gte=last_6_months).extra(
            select={'month': "strftime('%%Y-%%m', created_at)"}
        ).values('month').annotate(count=Count('id')).order_by('month')
        
        return {
            'total_tickets': queryset.count(),
            'status_counts': {item['status']: item['count'] for item in status_counts},
            'priority_counts': {item['priority']: item['count'] for item in priority_counts},
            'recent_tickets': list(recent_tickets.values()),
            'monthly_stats': list(monthly_tickets),
            'last_sync': self.get_last_sync_info()
        }
    
    def get_tickets_for_reports(self, filters=None):
        """Get filtered tickets for reports - from local database"""
        queryset = TicketCache.objects.all()
        
        if filters:
            if filters.get('company'):
                company_name = filters['company']
                # Try exact match first
                exact_match = queryset.filter(company_name__iexact=company_name)
                if exact_match.exists():
                    queryset = exact_match
                else:
                    # Try common company name variations
                    found_match = False
                    
                    # CG Logistics -> C G Logistics
                    if 'CG' in company_name and not found_match:
                        variation = company_name.replace('CG', 'C G')
                        match = queryset.filter(company_name__icontains=variation)
                        if match.exists():
                            queryset = match
                            found_match = True
                    
                    # Market-Excel -> Market Xcel  
                    if 'Market-Excel' in company_name and not found_match:
                        match = queryset.filter(company_name__icontains='Market Xcel')
                        if match.exists():
                            queryset = match
                            found_match = True
                    
                    # Aquimen -> Aiqmen
                    if 'Aquimen' in company_name and not found_match:
                        match = queryset.filter(company_name__icontains='Aiqmen')
                        if match.exists():
                            queryset = match
                            found_match = True
                    
                    # Generic partial match as fallback
                    if not found_match:
                        # Remove special characters and try partial match
                        clean_name = company_name.replace('-', '').replace(' ', '')
                        for ticket_company in queryset.values_list('company_name', flat=True).distinct():
                            clean_ticket = ticket_company.replace('-', '').replace(' ', '')
                            if clean_name.lower() in clean_ticket.lower() or clean_ticket.lower() in clean_name.lower():
                                queryset = queryset.filter(company_name=ticket_company)
                                found_match = True
                                break
                    
                    # If still no match, return empty queryset
                    if not found_match:
                        queryset = queryset.filter(company_name__icontains=company_name)
            
            if filters.get('technician'):
                queryset = queryset.filter(technician_name__iexact=filters['technician'])
            if filters.get('status'):
                queryset = queryset.filter(status__icontains=filters['status'])
            if filters.get('priority'):
                queryset = queryset.filter(priority__icontains=filters['priority'])
            if filters.get('date_from'):
                queryset = queryset.filter(created_at__gte=filters['date_from'])
            if filters.get('date_to'):
                queryset = queryset.filter(created_at__lte=filters['date_to'])
        
        return queryset.order_by('-created_at')
    
    def get_ticket_by_id(self, ticket_id):
        """Get single ticket from local database"""
        try:
            return TicketCache.objects.get(ticket_id=ticket_id)
        except TicketCache.DoesNotExist:
            return None
    
    def get_company_stats(self):
        """Get statistics by company from local database"""
        return TicketCache.objects.values('company_name').annotate(
            total_tickets=Count('id'),
            open_tickets=Count('id', filter=Q(status__in=['Open', 'Pending', 'In Progress'])),
            closed_tickets=Count('id', filter=Q(status__in=['Closed', 'Resolved']))
        ).order_by('-total_tickets')
    
    def get_technician_stats(self):
        """Get statistics by technician from local database"""
        return TicketCache.objects.exclude(technician_name='').values('technician_name').annotate(
            total_tickets=Count('id'),
            open_tickets=Count('id', filter=Q(status__in=['Open', 'Pending', 'In Progress'])),
            closed_tickets=Count('id', filter=Q(status__in=['Closed', 'Resolved']))
        ).order_by('-total_tickets')
    
    def search_tickets(self, search_term):
        """Search tickets in local database"""
        if not search_term:
            return TicketCache.objects.none()
        
        return TicketCache.objects.filter(
            Q(subject__icontains=search_term) |
            Q(description__icontains=search_term) |
            Q(requester_name__icontains=search_term) |
            Q(requester_email__icontains=search_term) |
            Q(ticket_id__icontains=search_term)
        ).order_by('-created_at')
    
    def get_tickets_by_date_range(self, start_date, end_date):
        """Get tickets within date range from local database"""
        return TicketCache.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).order_by('-created_at')
    
    def get_priority_distribution(self):
        """Get ticket distribution by priority"""
        return TicketCache.objects.values('priority').annotate(
            count=Count('id')
        ).order_by('-count')
    
    def get_status_distribution(self):
        """Get ticket distribution by status"""
        return TicketCache.objects.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
    
    def find_company_in_cache(self, company_name):
        """Return the best-matching company_name string found in TicketCache.
        Uses the same normalise/fuzzy logic as rbac.utils so that slight
        spelling differences ('CG Logistics' vs 'C G Logistics') are resolved.
        Returns the matched cache company_name string, or None if no match.
        """
        from rbac.utils import normalize_company_name
        from difflib import SequenceMatcher

        norm_input = normalize_company_name(company_name)
        candidates = (
            TicketCache.objects.values_list('company_name', flat=True)
            .exclude(company_name='')
            .distinct()
        )

        best_name, best_ratio = None, 0.0
        for cand in candidates:
            norm_cand = normalize_company_name(cand)
            if not norm_cand:
                continue
            # Substring match takes priority
            if norm_input in norm_cand or norm_cand in norm_input:
                return cand
            ratio = SequenceMatcher(None, norm_input, norm_cand).ratio()
            if ratio > best_ratio and ratio >= 0.6:
                best_ratio = ratio
                best_name = cand
        return best_name

    def get_last_sync_info(self):
        """Get information about last sync"""
        sync_status = SyncStatus.objects.filter(id=1).first()
        if sync_status:
            return {
                'last_sync_time': sync_status.last_sync_time,
                'total_tickets': sync_status.total_tickets_synced,
                'status': sync_status.sync_status,
                'error_message': sync_status.error_message
            }
        return None
    
    def get_tickets_needing_sync(self):
        """Check if we need to sync (placeholder for future enhancement)"""
        sync_info = self.get_last_sync_info()
        if not sync_info:
            return True
        
        # If last sync was more than 1 hour ago, suggest sync
        if sync_info['last_sync_time']:
            time_diff = timezone.now() - sync_info['last_sync_time']
            return time_diff.total_seconds() > 3600  # 1 hour
        
        return True
