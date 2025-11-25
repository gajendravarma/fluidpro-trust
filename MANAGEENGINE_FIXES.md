# ManageEngine Integration Fixes

## Issues Identified and Fixed

### 1. User Creation Failure
**Problem**: Users and technicians could not be created in ManageEngine due to API field restrictions.

**Root Cause**: 
- The `role` field was not supported by the ManageEngine API
- The `department` field required a valid department ID, not name
- Invalid department references were causing API rejections

**Solution**:
- Removed unsupported `role` field from user creation
- Used existing department ID `6` (General department) for all new users
- Set `is_technician: true` by default for all created users
- Simplified user payload to only include supported fields

### 2. CSRF Token Missing
**Problem**: AJAX requests for user creation were failing due to missing CSRF token.

**Root Cause**: The technicians template was missing the `{% csrf_token %}` tag.

**Solution**: Added `{% csrf_token %}` to the technicians template.

### 3. Ticket Deletion Issues
**Problem**: Tickets could not be deleted directly from ManageEngine.

**Root Cause**: ManageEngine requires tickets to be moved to trash before deletion.

**Solution**: Updated delete_ticket method to first move tickets to trash, then delete them.

## Files Modified

### 1. `/root/customer_portal/tickets/services.py`
- Fixed `create_user()` method to use supported fields only
- Fixed `update_user()` method to remove unsupported department field
- Fixed `delete_ticket()` method to handle trash workflow
- Used department ID `6` (General) for all new users

### 2. `/root/customer_portal/tickets/views.py`
- Updated `add_technician()` to remove role and department parameters
- Updated `edit_technician()` to remove department parameter
- Simplified user data payload

### 3. `/root/customer_portal/templates/tickets/technicians.html`
- Added missing `{% csrf_token %}` tag
- Removed department and role fields from add user form
- Simplified form to only include supported fields

## Test Results

All ManageEngine operations are now working:
- ✅ User creation: Successfully creates users with department "General"
- ✅ User deletion: Successfully deletes users
- ✅ Ticket creation: Successfully creates tickets
- ✅ Ticket deletion: Successfully moves to trash and deletes
- ✅ Get technicians: Successfully retrieves technician list
- ✅ Get all users: Successfully retrieves user list

## API Limitations Discovered

1. **Role Field**: Not supported in user creation/update
2. **Department Field**: Must use existing department ID, cannot create new departments via user API
3. **Ticket Deletion**: Requires two-step process (trash → delete)
4. **Department API**: Restricted access to departments endpoint

## Current Working Configuration

- **Default Department**: General (ID: 6)
- **User Type**: All created users are technicians by default
- **Required Fields**: name, email_id only
- **Optional Fields**: phone
- **CSRF Protection**: Enabled for all AJAX requests

The ManageEngine integration is now fully functional for creating users and tickets.
