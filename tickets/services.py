import requests
import json
from django.conf import settings

class ManageEngineService:
    def __init__(self):
        self.base_url = settings.MANAGE_ENGINE_BASE_URL
        self.auth_token = settings.MANAGE_ENGINE_AUTH_TOKEN
        self.headers = {
            'Accept': 'application/json',
            'authtoken': self.auth_token
        }
    
    def get_valid_requester_email(self, user_email):
        """Get a valid requester email that exists in ManageEngine"""
        # First try to find the user in ManageEngine
        if user_email and user_email.strip():
            users = self.get_all_users()
            if users and 'users' in users:
                for user in users['users']:
                    user_email_from_api = user.get('email_id', '')
                    if user_email_from_api and user_email_from_api.lower() == user_email.lower():
                        return user_email
        
        # Fallback to a known working email
        return "jayakumarm@wepsol.com"
    
    def get_all_users(self, page=1, per_page=20, search=None):
        """Get all users from ManageEngine with pagination and search"""
        url = f"{self.base_url}/users"
        
        start_index = (page - 1) * per_page + 1
        
        input_data = {
            "list_info": {
                "row_count": per_page,
                "start_index": start_index,
                "fields_required": ["id", "name", "email_id", "phone", "created_time", "status", "department", "type", "is_technician"]
            }
        }
        
        # Add search filter if provided
        if search and search.strip():
            input_data["list_info"]["search_fields"] = {
                "name": search,
                "email_id": search
            }
        
        try:
            response = requests.get(url, headers=self.headers, params={'input_data': json.dumps(input_data)})
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error fetching users: {e}")
            return None

    def get_users_last_activity(self, user_emails):
        """Get last activity for multiple users from recent requests"""
        url = f"{self.base_url}/requests"
        
        input_data = {
            "list_info": {
                "row_count": 100,  # Get more requests to find user activity
                "start_index": 1,
                "fields_required": ["requester", "last_updated_time"],
                "sort_field": "last_updated_time",
                "sort_order": "desc"
            }
        }
        
        try:
            response = requests.get(url, headers=self.headers, params={'input_data': json.dumps(input_data)})
            data = response.json() if response.status_code == 200 else None
            
            user_activity = {}
            if data and 'requests' in data:
                # Convert user emails to lowercase for comparison
                target_emails = [email.lower() for email in user_emails if email]
                
                for request in data['requests']:
                    requester = request.get('requester', {})
                    if isinstance(requester, dict):
                        requester_email = requester.get('email_id', '')
                        if requester_email and requester_email.lower() in target_emails:
                            # Only store if we haven't seen this user yet (first = most recent)
                            if requester_email.lower() not in user_activity:
                                last_updated = request.get('last_updated_time', {})
                                if isinstance(last_updated, dict) and 'value' in last_updated:
                                    user_activity[requester_email.lower()] = int(last_updated['value']) / 1000
            
            return user_activity
        except Exception as e:
            print(f"Error fetching users activity: {e}")
            return {}

    def get_total_users_count(self):
        """Get total count of all users"""
        url = f"{self.base_url}/users"
        
        input_data = {
            "list_info": {
                "row_count": 1,
                "start_index": 1,
                "get_total_count": True,
                "fields_required": ["id"]
            }
        }
        
        try:
            response = requests.get(url, headers=self.headers, params={'input_data': json.dumps(input_data)})
            data = response.json() if response.status_code == 200 else None
            return data.get('list_info', {}).get('total_count', 0) if data else 0
        except Exception as e:
            print(f"Error fetching total count: {e}")
            return 0
    
    def create_ticket(self, title, description, priority='Normal', requester_email=None, attachment_file=None):
        """Create a ticket in ManageEngine with optional attachment"""
        url = f"{self.base_url}/requests"
        
        # Get valid requester email
        valid_email = self.get_valid_requester_email(requester_email)
        
        input_data = {
            "request": {
                "subject": title,
                "description": description,
                "requester": {"email_id": valid_email},
                "priority": {"name": priority},
                "request_type": {"name": "Incident"},
                "status": {"name": "Open"}
            }
        }
        
        try:
            # Prepare the request
            files = {}
            data = {'input_data': json.dumps(input_data)}
            
            # Add attachment if provided
            if attachment_file:
                files['attachment'] = (
                    attachment_file.name,
                    attachment_file.read(),
                    attachment_file.content_type
                )
                # Reset file pointer for potential reuse
                attachment_file.seek(0)
            
            # Make request with or without files
            if files:
                # Remove Content-Type header when sending files (requests will set it)
                headers = {'authtoken': self.auth_token}
                response = requests.post(url, headers=headers, data=data, files=files)
            else:
                response = requests.post(url, headers=self.headers, data=data)
            
            if response.status_code == 201:
                result = response.json()
                # Add info about email used
                if valid_email != requester_email:
                    print(f"Note: Used fallback email {valid_email} instead of {requester_email}")
                return result
            else:
                print(f"Create ticket error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Error creating ticket: {e}")
            return None
    
    def get_ticket(self, ticket_id):
        """Get ticket details from ManageEngine"""
        url = f"{self.base_url}/requests/{ticket_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error fetching ticket: {e}")
            return None
    
    def get_user_tickets(self, user_email=None):
        """Get tickets for a specific user"""
        url = f"{self.base_url}/requests"
        
        input_data = {
            "list_info": {
                "row_count": 100,
                "start_index": 1,
                "fields_required": ["id", "subject", "status", "priority", "created_time", "description"]
            }
        }
        
        try:
            response = requests.get(url, headers=self.headers, params={'input_data': json.dumps(input_data)})
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error fetching tickets: {e}")
            return None
    
    def update_ticket(self, ticket_id, updates):
        """Update ticket in ManageEngine"""
        url = f"{self.base_url}/requests/{ticket_id}"
        
        input_data = {"request": updates}
        
        try:
            response = requests.put(url, headers=self.headers, data={'input_data': json.dumps(input_data)})
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error updating ticket: {e}")
            return None
    
    def get_technicians(self):
        """Get list of technicians"""
        url = f"{self.base_url}/users"
        
        input_data = {
            "list_info": {
                "row_count": 100,
                "start_index": 1,
                "fields_required": ["id", "name", "email_id", "phone", "is_technician", "type"]
            }
        }
        
        try:
            response = requests.get(url, headers=self.headers, params={'input_data': json.dumps(input_data)})
            if response.status_code == 200:
                data = response.json()
                # Filter only technicians
                if 'users' in data:
                    technicians = [user for user in data['users'] if user.get('is_technician', False)]
                    return {'users': technicians}
            return None
        except Exception as e:
            print(f"Error fetching technicians: {e}")
            return None
    def create_user(self, user_data):
        """Create a new user in ManageEngine"""
        url = f"{self.base_url}/users"
        headers = {
            'authtoken': self.auth_token,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        # Use the default department that exists in the system
        user_payload = {
            'name': user_data.get('name'),
            'email_id': user_data.get('email_id'),
            'is_technician': True,
            'department': {'id': '6'}  # Use existing department ID
        }
        
        # Add optional fields only if provided
        if user_data.get('phone'):
            user_payload['phone'] = user_data.get('phone')
            
        # Add company/account if provided
        if user_data.get('company'):
            user_payload['account'] = {'name': user_data.get('company')}
            
        data = {
            'input_data': json.dumps({
                'user': user_payload
            })
        }
        
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 201:
            return response.json()
        else:
            raise Exception(f"Failed to create user: {response.text}")

    def update_user(self, user_id, user_data):
        """Update a user in ManageEngine"""
        url = f"{self.base_url}/users/{user_id}"
        headers = {
            'authtoken': self.auth_token,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        # Only update basic fields that are supported
        user_payload = {
            'name': user_data.get('name'),
            'email_id': user_data.get('email_id')
        }
        
        # Add optional fields only if provided
        if user_data.get('phone'):
            user_payload['phone'] = user_data.get('phone')
            
        # Add company/account if provided
        if user_data.get('company'):
            user_payload['account'] = {'name': user_data.get('company')}
        
        data = {
            'input_data': json.dumps({
                'user': user_payload
            })
        }
        
        response = requests.put(url, headers=headers, data=data)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to update user: {response.text}")

    def delete_user(self, user_id):
        """Delete a user from ManageEngine"""
        url = f"{self.base_url}/users/{user_id}"
        headers = {
            'authtoken': self.auth_token
        }
        
        response = requests.delete(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to delete user: {response.text}")

    def get_user_details(self, user_id):
        """Get detailed information for a specific user"""
        url = f"{self.base_url}/users/{user_id}"
        
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching user details: {e}")
            return None

    def get_companies(self):
        """Get list of all companies from ManageEngine"""
        # Predefined companies that should always be available
        predefined_companies = [
            {'name': 'Wepsol'},
            {'name': 'MarketExcel'},
            {'name': 'C G Logistics'},
        ]
        
        url = f"{self.base_url}/accounts"
        
        input_data = {
            "list_info": {
                "row_count": 100,
                "start_index": 1,
                "fields_required": ["id", "name"]
            }
        }
        
        try:
            response = requests.get(url, headers=self.headers, params={'input_data': json.dumps(input_data)})
            if response.status_code == 200:
                data = response.json()
                api_companies = data.get('accounts', [])
            else:
                # Fallback: get companies from tickets if accounts API doesn't work
                api_companies = self._get_companies_from_tickets()
        except Exception as e:
            print(f"Error fetching companies: {e}")
            api_companies = self._get_companies_from_tickets()
        
        # Combine predefined and API companies, avoiding duplicates
        all_companies = predefined_companies.copy()
        existing_names = {company['name'].lower() for company in predefined_companies}
        
        for company in api_companies:
            company_name = company.get('name', '')
            if company_name and company_name.lower() not in existing_names:
                all_companies.append({'name': company_name})
                existing_names.add(company_name.lower())
        
        # Sort by name for better UX
        return sorted(all_companies, key=lambda x: x['name'])
    
    def _get_companies_from_tickets(self):
        """Fallback method to get companies from tickets"""
        try:
            url = f"{self.base_url}/requests"
            input_data = {
                "list_info": {
                    "row_count": 500,
                    "start_index": 1,
                    "fields_required": ["account"]
                }
            }
            
            response = requests.get(url, headers=self.headers, params={'input_data': json.dumps(input_data)})
            if response.status_code == 200:
                data = response.json()
                tickets = data.get('requests', [])
                companies = set()
                
                for ticket in tickets:
                    account = ticket.get('account', {})
                    if isinstance(account, dict):
                        account_name = account.get('name', '')
                        if account_name:
                            companies.add(account_name)
                
                # Convert to list of dicts for consistency
                return [{'name': company} for company in sorted(companies)]
            return []
        except Exception as e:
            print(f"Error fetching companies from tickets: {e}")
            return []
        """Delete a ticket from ManageEngine - first move to trash, then delete"""
        # First, move ticket to trash
        trash_url = f"{self.base_url}/requests/{ticket_id}/move_to_trash"
        headers = {
            'authtoken': self.auth_token,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        try:
            # Move to trash first
            trash_response = requests.put(trash_url, headers=headers)
            if trash_response.status_code != 200:
                # If already in trash or other issue, try direct delete
                pass
            
            # Now delete from trash
            delete_url = f"{self.base_url}/requests/{ticket_id}"
            response = requests.delete(delete_url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Failed to delete ticket: {response.text}")
        except Exception as e:
            # If delete fails, at least it's in trash
            return {"status": "moved_to_trash", "message": str(e)}
