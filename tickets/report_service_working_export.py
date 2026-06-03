from datetime import datetime, timedelta
from collections import defaultdict
import csv
from io import StringIO
from pulseway.manageengine_service import ManageEngineAPI


class ManageEngineReportService:
    def __init__(self):
        self.api = ManageEngineAPI()
    
    def _get_all_tickets(self, start_date=None, end_date=None, limit=5000):
        """Fetch all tickets using cached API with optional date filtering"""
        tickets = self.api.get_tickets(row_count=limit)
        
        if start_date or end_date:
            tickets = self._filter_tickets_by_date(tickets, start_date, end_date)
        
        return tickets
    
    def _filter_tickets_by_date(self, tickets, start_date=None, end_date=None):
        """Filter tickets by date range"""
        filtered = []
        for ticket in tickets:
            created_time = ticket.get('created_time', {})
            if isinstance(created_time, dict) and 'value' in created_time:
                try:
                    timestamp = int(created_time['value']) / 1000
                    ticket_date = datetime.fromtimestamp(timestamp).date()
                    
                    if start_date and ticket_date < start_date:
                        continue
                    if end_date and ticket_date > end_date:
                        continue
                    
                    filtered.append(ticket)
                except:
                    continue
        return filtered
    
    def get_daily_report(self, date=None):
        """Get tickets created on a specific day"""
        if not date:
            date = datetime.now().date()
        
        tickets = self._get_all_tickets(start_date=date, end_date=date)
        return self._process_report_data(tickets, 'daily', date)
    
    def get_weekly_report(self, start_date=None):
        """Get tickets for the current/specified week"""
        if not start_date:
            today = datetime.now().date()
            start_date = today - timedelta(days=today.weekday())
        
        end_date = start_date + timedelta(days=6)
        tickets = self._get_all_tickets(start_date=start_date, end_date=end_date)
        return self._process_report_data(tickets, 'weekly', start_date, end_date)
    
    def get_monthly_report(self, year=None, month=None):
        """Get tickets for a specific month"""
        if not year or not month:
            now = datetime.now()
            year = now.year
            month = now.month
        
        print(f"DEBUG: Getting monthly report for {year}-{month}")
        
        start_date = datetime(year, month, 1).date()
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
        
        print(f"DEBUG: Date range {start_date} to {end_date}")
        
        # Get all tickets first
        all_tickets = self.api.get_tickets(row_count=5000)
        print(f"DEBUG: Fetched {len(all_tickets)} total tickets")
        
        # Filter by date manually with debug
        filtered_tickets = []
        for ticket in all_tickets:
            created_time = ticket.get('created_time', {})
            if isinstance(created_time, dict) and 'value' in created_time:
                try:
                    timestamp = int(created_time['value']) / 1000
                    ticket_date = datetime.fromtimestamp(timestamp).date()
                    
                    if start_date <= ticket_date <= end_date:
                        filtered_tickets.append(ticket)
                except Exception as e:
                    print(f"DEBUG: Error parsing date for ticket {ticket.get('id')}: {e}")
                    continue
        
        print(f"DEBUG: Filtered to {len(filtered_tickets)} tickets for {year}-{month}")
        
        return self._process_report_data(filtered_tickets, 'monthly', start_date, end_date)
    
    def get_company_report(self, company_name=None):
        """Get tickets grouped by company"""
        tickets = self._get_all_tickets()
        
        if company_name:
            # Filter for specific company
            filtered = []
            for t in tickets:
                account_obj = t.get('account')
                if account_obj and isinstance(account_obj, dict):
                    if account_obj.get('name', '') == company_name:
                        filtered.append(t)
            return self._process_report_data(filtered, 'company', company_name=company_name)
        else:
            # Group by all companies
            companies = defaultdict(list)
            for ticket in tickets:
                account_obj = ticket.get('account')
                company = account_obj.get('name', 'No Company') if account_obj and isinstance(account_obj, dict) else 'No Company'
                companies[company].append(ticket)
            
            return {
                'report_type': 'company_summary',
                'companies': {
                    name: self._process_report_data(tix, 'company', company_name=name)
                    for name, tix in companies.items()
                }
            }
    
    def get_technician_report(self, technician_name=None):
        """Get tickets by technician"""
        tickets = self._get_all_tickets()
        
        if technician_name:
            filtered = []
            for t in tickets:
                tech_obj = t.get('technician')
                if tech_obj and isinstance(tech_obj, dict):
                    if tech_obj.get('name', '') == technician_name:
                        filtered.append(t)
            return self._process_report_data(filtered, 'technician', technician_name=technician_name)
        else:
            # Group by all technicians
            technicians = defaultdict(list)
            for ticket in tickets:
                tech_obj = ticket.get('technician')
                tech = tech_obj.get('name', 'Unassigned') if tech_obj and isinstance(tech_obj, dict) else 'Unassigned'
                technicians[tech].append(ticket)
            
            return {
                'report_type': 'technician_summary',
                'technicians': {
                    name: self._process_report_data(tix, 'technician', technician_name=name)
                    for name, tix in technicians.items()
                }
            }
    
    def _process_report_data(self, tickets, report_type, start_date=None, end_date=None, 
                            company_name=None, technician_name=None):
        """Process tickets into report format"""
        print(f"DEBUG: Processing {len(tickets)} tickets for report")
        
        report = {
            'report_type': report_type,
            'generated_at': datetime.now(),
            'start_date': start_date,
            'end_date': end_date,
            'company_name': company_name,
            'technician_name': technician_name,
            'total_tickets': len(tickets),
            'status_breakdown': defaultdict(int),
            'priority_breakdown': defaultdict(int),
            'category_breakdown': defaultdict(int),
            'technician_breakdown': defaultdict(int),
            'company_breakdown': defaultdict(int),
            'daily_breakdown': defaultdict(int),
            'tickets': []
        }
        
        for ticket in tickets:
            # Status
            status_obj = ticket.get('status')
            status = status_obj.get('name', 'Unknown') if status_obj and isinstance(status_obj, dict) else 'Unknown'
            report['status_breakdown'][status] += 1
            
            # Priority
            priority_obj = ticket.get('priority')
            priority = priority_obj.get('name', 'Normal') if priority_obj and isinstance(priority_obj, dict) else 'Normal'
            report['priority_breakdown'][priority] += 1
            
            # Category
            category_obj = ticket.get('category')
            category = category_obj.get('name', 'Uncategorized') if category_obj and isinstance(category_obj, dict) else 'Uncategorized'
            report['category_breakdown'][category] += 1
            
            # Technician
            tech_obj = ticket.get('technician')
            tech = tech_obj.get('name', 'Unassigned') if tech_obj and isinstance(tech_obj, dict) else 'Unassigned'
            report['technician_breakdown'][tech] += 1
            
            # Company
            account_obj = ticket.get('account')
            company = account_obj.get('name', 'No Company') if account_obj and isinstance(account_obj, dict) else 'No Company'
            report['company_breakdown'][company] += 1
            
            # Daily breakdown
            created_time = ticket.get('created_time')
            if created_time and isinstance(created_time, dict) and 'value' in created_time:
                try:
                    timestamp = int(created_time['value']) / 1000
                    date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                    report['daily_breakdown'][date_str] += 1
                except:
                    pass
            
            # Add ticket details
            report['tickets'].append(self._format_ticket(ticket))
        
        # Convert defaultdicts to regular dicts
        report['status_breakdown'] = dict(report['status_breakdown'])
        report['priority_breakdown'] = dict(report['priority_breakdown'])
        report['category_breakdown'] = dict(report['category_breakdown'])
        report['technician_breakdown'] = dict(report['technician_breakdown'])
        report['company_breakdown'] = dict(report['company_breakdown'])
        report['daily_breakdown'] = dict(sorted(report['daily_breakdown'].items()))
        
        print(f"DEBUG: Status breakdown: {report['status_breakdown']}")
        print(f"DEBUG: Priority breakdown: {report['priority_breakdown']}")
        print(f"DEBUG: Total processed tickets: {report['total_tickets']}")
        
        return report
    
    def _format_ticket(self, ticket):
        """Format ticket for report"""
        created_time = ticket.get('created_time')
        created_date = None
        if created_time and isinstance(created_time, dict) and 'value' in created_time:
            try:
                timestamp = int(created_time['value']) / 1000
                created_date = datetime.fromtimestamp(timestamp)
            except:
                pass
        
        status_obj = ticket.get('status')
        priority_obj = ticket.get('priority')
        category_obj = ticket.get('category')
        requester_obj = ticket.get('requester')
        technician_obj = ticket.get('technician')
        account_obj = ticket.get('account')
        
        return {
            'id': ticket.get('id'),
            'subject': ticket.get('subject', 'No Subject'),
            'status': status_obj.get('name', 'Unknown') if status_obj and isinstance(status_obj, dict) else 'Unknown',
            'priority': priority_obj.get('name', 'Normal') if priority_obj and isinstance(priority_obj, dict) else 'Normal',
            'category': category_obj.get('name', 'Uncategorized') if category_obj and isinstance(category_obj, dict) else 'Uncategorized',
            'requester': requester_obj.get('name', 'Unknown') if requester_obj and isinstance(requester_obj, dict) else 'Unknown',
            'technician': technician_obj.get('name', 'Unassigned') if technician_obj and isinstance(technician_obj, dict) else 'Unassigned',
            'company': account_obj.get('name', 'No Company') if account_obj and isinstance(account_obj, dict) else 'No Company',
            'created_at': created_date
        }
    
    def export_to_csv(self, report_data):
        """Export report data to CSV format"""
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Ticket ID', 'Subject', 'Status', 'Priority', 'Category', 
                        'Requester', 'Technician', 'Company', 'Created Date'])
        
        # Write ticket data
        for ticket in report_data.get('tickets', []):
            writer.writerow([
                ticket['id'],
                ticket['subject'],
                ticket['status'],
                ticket['priority'],
                ticket['category'],
                ticket['requester'],
                ticket['technician'],
                ticket['company'],
                ticket['created_at'].strftime('%Y-%m-%d %H:%M:%S') if ticket['created_at'] else 'N/A'
            ])
        
        return output.getvalue()
    
    def get_available_companies(self):
        """Get list of companies from tickets"""
        tickets = self._get_all_tickets(limit=500)
        companies = set()
        for ticket in tickets:
            account_obj = ticket.get('account')
            if account_obj and isinstance(account_obj, dict):
                company = account_obj.get('name', '')
                if company:
                    companies.add(company)
        return sorted(list(companies))
    
    def get_available_technicians(self):
        """Get list of technicians from tickets"""
        tickets = self._get_all_tickets(limit=500)
        technicians = set()
        for ticket in tickets:
            tech_obj = ticket.get('technician')
            if tech_obj and isinstance(tech_obj, dict):
                tech = tech_obj.get('name', '')
                if tech:
                    technicians.add(tech)
        return sorted(list(technicians))
