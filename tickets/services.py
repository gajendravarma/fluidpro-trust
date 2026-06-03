import requests
import json
from django.conf import settings
from datetime import datetime, timedelta
import time

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
                "row_count": 300,  # Get more requests to find user activity
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
    
    # Default fallback requester — must be a valid ManageEngine user
    FALLBACK_REQUESTER_EMAIL = 'Gajendra.N@wepsol.com'

    def create_ticket(self, title, description, priority='Normal', requester_email=None, attachment_file=None):
        """Create a ticket in ManageEngine.

        Strategy:
        1. Create the ticket WITHOUT the attachment (inline attachment is
           rejected by this ManageEngine instance with a 400 Unknown error).
        2. If an attachment was provided, upload it separately after creation.
        3. If the requester email is not in ManageEngine (400 requester error),
           retry once with FALLBACK_REQUESTER_EMAIL.

        Returns the ticket creation response dict, with an extra key
        'attachment_uploaded' (True/False) when a file was provided.
        """
        import logging
        logger = logging.getLogger(__name__)

        url = f"{self.base_url}/requests"

        def _post_ticket(email):
            """POST to create the ticket (no file)."""
            input_data = {
                "request": {
                    "subject": title,
                    "description": description,
                    "requester": {"email_id": email},
                    "priority": {"name": priority},
                    "request_type": {"name": "Incident"},
                    "status": {"name": "Open"},
                }
            }
            return requests.post(
                url,
                headers=self.headers,
                data={'input_data': json.dumps(input_data)},
                timeout=30,
            )

        def _upload_attachment(ticket_id, file_obj):
            """Try to upload the attachment to an existing ticket.
            ManageEngine v3 doesn't document a public attachment endpoint,
            so we try the most common paths and return True if any succeeds.
            """
            att_headers = {'authtoken': self.auth_token}
            for path in [
                f"{self.base_url}/requests/{ticket_id}/attachments",
                f"{self.base_url}/requests/{ticket_id}/notes",
            ]:
                try:
                    file_obj.seek(0)
                    content_type = getattr(file_obj, 'content_type', None) or 'application/octet-stream'
                    files = {'attachment': (file_obj.name, file_obj.read(), content_type)}
                    r = requests.post(path, headers=att_headers, files=files, timeout=30)
                    if r.status_code in (200, 201):
                        logger.info(f"Attachment uploaded to {path}")
                        return True
                    logger.debug(f"Attachment attempt {path} -> {r.status_code}: {r.text[:200]}")
                except Exception as e:
                    logger.debug(f"Attachment attempt {path} error: {e}")
            return False

        try:
            first_email = (requester_email or '').strip() or self.FALLBACK_REQUESTER_EMAIL
            response = _post_ticket(first_email)
            logger.info(f"ME create_ticket ({first_email}) -> HTTP {response.status_code}")

            # Requester not in ManageEngine — retry with known-good fallback
            if response.status_code == 400 and first_email != self.FALLBACK_REQUESTER_EMAIL:
                body = response.text.lower()
                if 'requester' in body or 'invalid input' in body:
                    logger.warning(
                        f"Requester {first_email!r} not in ManageEngine, "
                        f"retrying with {self.FALLBACK_REQUESTER_EMAIL!r}"
                    )
                    response = _post_ticket(self.FALLBACK_REQUESTER_EMAIL)
                    logger.info(f"ME create_ticket (fallback) -> HTTP {response.status_code}")

            if response.status_code not in (200, 201):
                logger.error(
                    f"ManageEngine ticket creation failed: "
                    f"status={response.status_code} body={response.text[:500]}"
                )
                print(f"ME create_ticket error: {response.status_code} -- {response.text[:500]}")
                return None

            result = response.json()

            # Upload attachment separately if one was provided
            if attachment_file:
                ticket_id = (result.get('request') or {}).get('id')
                if ticket_id:
                    uploaded = _upload_attachment(ticket_id, attachment_file)
                    result['attachment_uploaded'] = uploaded
                    if not uploaded:
                        logger.warning(
                            f"Ticket {ticket_id} created but attachment upload failed. "
                            f"File: {getattr(attachment_file, 'name', 'unknown')}"
                        )
                else:
                    result['attachment_uploaded'] = False

            return result

        except requests.exceptions.ConnectionError as e:
            logger.error(f"ManageEngine unreachable: {e}")
            print(f"ManageEngine connection error: {e}")
            return None
        except requests.exceptions.Timeout:
            logger.error("ManageEngine create_ticket timed out after 30s")
            print("ManageEngine create_ticket timed out")
            return None
        except Exception as e:
            logger.error(f"ManageEngine create_ticket unexpected error: {e}")
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
                "row_count": 300,
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
                "row_count": 300,
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
                "row_count": 300,
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
            raise Exception(f"Failed to delete ticket: {str(e)}")
    
    def get_recent_tickets(self, limit=10):
        """Get recent tickets from ManageEngine"""
        url = f"{self.base_url}/requests"
        
        input_data = {
            "list_info": {
                "row_count": limit,
                "start_index": 1,
                "sort_field": "created_time",
                "sort_order": "desc",
                "fields_required": ["id", "subject", "status", "priority", "created_time", "requester"]
            }
        }
        
        try:
            response = requests.get(url, headers=self.headers, params={'input_data': json.dumps(input_data)})
            
            if response.status_code != 200:
                return []
                
            data = response.json()
            tickets = data.get('requests', []) if data else []
            
            # Format tickets for display
            formatted_tickets = []
            for ticket in tickets:
                created_time = ticket.get('created_time', {})
                if isinstance(created_time, dict) and 'value' in created_time:
                    try:
                        from datetime import datetime
                        timestamp_value = created_time['value']
                        if isinstance(timestamp_value, str):
                            timestamp_value = int(timestamp_value)
                        created_date = datetime.fromtimestamp(timestamp_value / 1000)
                    except:
                        created_date = None
                else:
                    created_date = None
                
                formatted_tickets.append({
                    'id': ticket.get('id'),
                    'title': ticket.get('subject', 'No Subject'),
                    'status': ticket.get('status', {}).get('name', 'Unknown'),
                    'priority': ticket.get('priority', {}).get('name', 'Normal'),
                    'created_at': created_date,
                    'created_by': ticket.get('requester', {}).get('name', 'Unknown'),
                    'manage_engine_id': ticket.get('id')
                })
            
            return formatted_tickets
            
        except Exception as e:
            print(f"Error fetching recent tickets: {e}")
            return []

    def get_historical_tickets(self, months=2):
        """Get tickets from the last specified months - show real data"""
        url = f"{self.base_url}/requests"
        
        try:
            all_tickets = []
            target_count = 300
            batch_size = 100
            
            # Make multiple requests to get 300 tickets
            for batch in range(3):  # 3 batches of 100 = 300
                start_index = (batch * batch_size) + 1
                
                input_data = {
                    "list_info": {
                        "row_count": batch_size,
                        "start_index": start_index,
                        "fields_required": ["id", "subject", "status", "priority", "created_time", "requester"],
                        "sort_field": "created_time",
                        "sort_order": "desc"
                    }
                }
                
                try:
                    response = requests.get(url, headers=self.headers, params={'input_data': json.dumps(input_data)})
                    
                    if response.status_code != 200:
                        print(f"API Error batch {batch+1}: {response.status_code}")
                        break
                        
                    data = response.json()
                    batch_tickets = data.get('requests', []) if data else []
                    
                    print(f"DEBUG: Batch {batch+1} fetched {len(batch_tickets)} tickets")
                    
                    if not batch_tickets:
                        break  # No more tickets available
                        
                    all_tickets.extend(batch_tickets)
                    
                    # Stop if we got less than batch_size (no more tickets)
                    if len(batch_tickets) < batch_size:
                        break
                        
                except Exception as e:
                    print(f"Error fetching batch {batch+1}: {e}")
                    break
            
            print(f"DEBUG: Total fetched {len(all_tickets)} tickets from multiple batches")
            
            if not all_tickets:
                return None
            
            # Filter by date for last N months (client-side)
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=months * 30)
            
            filtered_tickets = []
            for ticket in all_tickets:
                created_time = ticket.get('created_time', {})
                if isinstance(created_time, dict) and 'value' in created_time:
                    try:
                        timestamp_value = created_time['value']
                        if isinstance(timestamp_value, str):
                            timestamp_value = int(timestamp_value)
                        ticket_date = datetime.fromtimestamp(timestamp_value / 1000)
                        if ticket_date >= cutoff_date:
                            filtered_tickets.append(ticket)
                    except:
                        continue
            
            return self._process_ticket_stats(filtered_tickets)
            
        except Exception as e:
            print(f"Error fetching historical tickets: {e}")
            return None
    
    # ------------------------------------------------------------------ #
    #  NOTES                                                             #
    # ------------------------------------------------------------------ #
    def get_ticket_notes(self, ticket_id):
        url = f"{self.base_url}/requests/{ticket_id}/notes"
        try:
            response = requests.get(url, headers=self.headers)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error fetching notes: {e}")
            return None

    def add_ticket_note(self, ticket_id, description, is_public=False):
        url = f"{self.base_url}/requests/{ticket_id}/notes"
        input_data = {"note": {"description": description, "is_public": is_public}}
        try:
            response = requests.post(url, headers=self.headers,
                                     data={'input_data': json.dumps(input_data)})
            return response.json() if response.status_code in [200, 201] else None
        except Exception as e:
            print(f"Error adding note: {e}")
            return None

    def edit_ticket_note(self, ticket_id, note_id, description, is_public=False):
        url = f"{self.base_url}/requests/{ticket_id}/notes/{note_id}"
        input_data = {"note": {"description": description, "is_public": is_public}}
        try:
            response = requests.put(url, headers=self.headers,
                                    data={'input_data': json.dumps(input_data)})
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error editing note: {e}")
            return None

    def delete_ticket_note(self, ticket_id, note_id):
        url = f"{self.base_url}/requests/{ticket_id}/notes/{note_id}"
        try:
            response = requests.delete(url, headers=self.headers)
            return response.status_code == 200
        except Exception as e:
            print(f"Error deleting note: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  WORKLOGS                                                           #
    # ------------------------------------------------------------------ #
    def get_ticket_worklogs(self, ticket_id):
        url = f"{self.base_url}/requests/{ticket_id}/worklogs"
        try:
            response = requests.get(url, headers=self.headers)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error fetching worklogs: {e}")
            return None

    def add_ticket_worklog(self, ticket_id, description, hours, minutes, technician_id=None):
        url = f"{self.base_url}/requests/{ticket_id}/worklogs"
        worklog = {
            "description": description,
            "time_spent": {"hours": int(hours), "minutes": int(minutes)},
        }
        if technician_id:
            worklog["technician"] = {"id": str(technician_id)}
        input_data = {"worklog": worklog}
        try:
            response = requests.post(url, headers=self.headers,
                                     data={'input_data': json.dumps(input_data)})
            return response.json() if response.status_code in [200, 201] else None
        except Exception as e:
            print(f"Error adding worklog: {e}")
            return None

    def delete_ticket_worklog(self, ticket_id, worklog_id):
        url = f"{self.base_url}/requests/{ticket_id}/worklogs/{worklog_id}"
        try:
            response = requests.delete(url, headers=self.headers)
            return response.status_code == 200
        except Exception as e:
            print(f"Error deleting worklog: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  TASKS                                                              #
    # ------------------------------------------------------------------ #
    def get_ticket_tasks(self, ticket_id):
        url = f"{self.base_url}/requests/{ticket_id}/tasks"
        try:
            response = requests.get(url, headers=self.headers)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error fetching tasks: {e}")
            return None

    def add_ticket_task(self, ticket_id, title, description='', assigned_to_id=None):
        url = f"{self.base_url}/requests/{ticket_id}/tasks"
        task = {"title": title, "description": description}
        if assigned_to_id:
            task["owner"] = {"id": str(assigned_to_id)}
        input_data = {"task": task}
        try:
            response = requests.post(url, headers=self.headers,
                                     data={'input_data': json.dumps(input_data)})
            return response.json() if response.status_code in [200, 201] else None
        except Exception as e:
            print(f"Error adding task: {e}")
            return None

    def update_ticket_task(self, ticket_id, task_id, updates):
        url = f"{self.base_url}/requests/{ticket_id}/tasks/{task_id}"
        input_data = {"task": updates}
        try:
            response = requests.put(url, headers=self.headers,
                                    data={'input_data': json.dumps(input_data)})
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error updating task: {e}")
            return None

    def delete_ticket_task(self, ticket_id, task_id):
        url = f"{self.base_url}/requests/{ticket_id}/tasks/{task_id}"
        try:
            response = requests.delete(url, headers=self.headers)
            return response.status_code == 200
        except Exception as e:
            print(f"Error deleting task: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  APPROVALS                                                          #
    # ------------------------------------------------------------------ #
    def get_ticket_approvals(self, ticket_id):
        url = f"{self.base_url}/requests/{ticket_id}/approvals"
        try:
            response = requests.get(url, headers=self.headers)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error fetching approvals: {e}")
            return None

    def send_for_approval(self, ticket_id, approver_id):
        url = f"{self.base_url}/requests/{ticket_id}/approvals"
        input_data = {"approval": {"approver": {"id": str(approver_id)}}}
        try:
            response = requests.post(url, headers=self.headers,
                                     data={'input_data': json.dumps(input_data)})
            return response.json() if response.status_code in [200, 201] else None
        except Exception as e:
            print(f"Error sending for approval: {e}")
            return None

    def approve_reject_ticket(self, ticket_id, approval_id, action, comments=''):
        url = f"{self.base_url}/requests/{ticket_id}/approvals/{approval_id}"
        input_data = {"approval": {"status": {"name": action}, "comments": comments}}
        try:
            response = requests.put(url, headers=self.headers,
                                    data={'input_data': json.dumps(input_data)})
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error approving/rejecting: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  ATTACHMENTS                                                        #
    # ------------------------------------------------------------------ #
    def add_ticket_attachment(self, ticket_id, attachment_file):
        url = f"{self.base_url}/requests/{ticket_id}/attachments"
        headers = {'authtoken': self.auth_token}
        try:
            files = {'attachment': (attachment_file.name, attachment_file.read(),
                                    attachment_file.content_type)}
            response = requests.post(url, headers=headers, files=files)
            return response.json() if response.status_code in [200, 201] else None
        except Exception as e:
            print(f"Error adding attachment: {e}")
            return None

    # ------------------------------------------------------------------ #
    #  ASSIGN / PICKUP / CLOSE                                           #
    # ------------------------------------------------------------------ #
    def assign_technician(self, ticket_id, technician_id):
        return self.update_ticket(ticket_id, {"technician": {"id": str(technician_id)}})

    def pickup_ticket(self, ticket_id, technician_id):
        return self.update_ticket(ticket_id, {"technician": {"id": str(technician_id)}})

    def close_ticket(self, ticket_id, resolution='', closure_code='Resolved'):
        updates = {"status": {"name": "Closed"}}
        if resolution:
            updates["resolution"] = {"content": resolution}
        if closure_code:
            updates["closure_info"] = {"closure_code": {"name": closure_code}}
        return self.update_ticket(ticket_id, updates)

    def _process_ticket_stats(self, filtered_tickets):
        """Process ticket statistics"""
        stats = {
            'total_tickets': len(filtered_tickets),
            'pending_tickets': 0,
            'cancelled_tickets': 0,
            'closed_tickets': 0,
            'in_progress_tickets': 0,
            'tickets_by_month': {},
            'tickets_by_priority': {'Low': 0, 'Medium': 0, 'High': 0, 'Urgent': 0},
            'recent_tickets': filtered_tickets[:10]
        }
        
        for ticket in filtered_tickets:
            status = ticket.get('status', {})
            status_name = status.get('name', '').lower() if isinstance(status, dict) else str(status).lower()
            
            if status_name in ['open', 'pending', 'onhold']:
                stats['pending_tickets'] += 1
            elif status_name in ['cancelled']:
                stats['cancelled_tickets'] += 1
            elif status_name in ['closed']:
                stats['closed_tickets'] += 1
            elif 'progress' in status_name or 'assigned' in status_name:
                stats['in_progress_tickets'] += 1
            else:
                stats['pending_tickets'] += 1
            
            priority = ticket.get('priority', {})
            priority_name = priority.get('name', 'Medium') if isinstance(priority, dict) else str(priority) if priority else 'Medium'
            if priority_name in stats['tickets_by_priority']:
                stats['tickets_by_priority'][priority_name] += 1
            
            created_time = ticket.get('created_time', {})
            if isinstance(created_time, dict) and 'display_value' in created_time:
                try:
                    date_str = created_time['display_value']
                    month_year = date_str.split(',')[0] if ',' in date_str else date_str[:6]
                    stats['tickets_by_month'][month_year] = stats['tickets_by_month'].get(month_year, 0) + 1
                except:
                    pass
        
        return stats
