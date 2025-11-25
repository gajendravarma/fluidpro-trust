# Pulseway Integration for Customer Portal

This document describes the Pulseway integration added to the Django customer portal.

## Features

### Dashboard
- Overview of devices, sites, and recent actions
- Quick access to all Pulseway management functions
- Real-time status indicators

### Device Management
- View all devices with status, OS, IP address, and last seen information
- Remote device reboot functionality
- Quick access to run scripts and install patches on devices

### Site Management
- List all sites with device counts and details
- Create new sites with name, description, and address
- Edit and delete existing sites

### Group Management
- View all groups organized by sites
- Create new groups and associate them with sites
- Manage group memberships

### Organization Management
- View organization hierarchy
- Monitor organization-level statistics

### Script Execution
- Run PowerShell, Batch, or Bash scripts on remote devices
- Track script execution history
- Support for custom script content

### Patch Management
- Install patches on specific devices
- Support for multiple patch IDs
- Optional reboot after patch installation
- Track patch installation history

### Action History
- Complete audit trail of all Pulseway actions
- Filter by action type, status, and date
- Detailed result information for each action

## API Configuration

The integration uses the following Pulseway API settings in `settings.py`:

```python
PULSEWAY_ENDPOINT = 'https://fluidpulse.pulseway.com/api/v3'
PULSEWAY_TOKEN_ID = 'your-token-id'
PULSEWAY_TOKEN_SECRET = 'your-token-secret'
```

## File Structure

```
pulseway/
├── __init__.py
├── models.py          # PulsewayAction model for tracking operations
├── services.py        # PulsewayAPI service class for API interactions
├── views.py           # Django views for all Pulseway functionality
├── forms.py           # Django forms for user input
├── urls.py            # URL routing for Pulseway app
└── migrations/        # Database migrations

templates/pulseway/
├── dashboard.html     # Main Pulseway dashboard
├── devices.html       # Device listing and management
├── sites.html         # Site listing and management
├── groups.html        # Group listing and management
├── organizations.html # Organization overview
├── create_site.html   # Site creation form
├── create_group.html  # Group creation form
├── run_script.html    # Script execution form
├── install_patches.html # Patch installation form
└── actions_history.html # Action history listing
```

## Usage

### Accessing Pulseway
1. Log into the customer portal
2. Click "Pulseway" in the navigation menu
3. Access the Pulseway dashboard with overview and quick actions

### Creating Sites
1. Navigate to Pulseway → Sites
2. Click "Create Site"
3. Fill in site name, description, and address
4. Submit to create the site

### Running Scripts
1. Navigate to Pulseway → Dashboard
2. Click "Run Script" or go to devices and select a device
3. Enter device ID, select script type, and provide script content
4. Execute the script

### Installing Patches
1. Navigate to Pulseway → Dashboard
2. Click "Install Patches" or select from device actions
3. Enter device ID and patch IDs (one per line)
4. Optionally enable reboot after installation
5. Submit to install patches

### Monitoring Actions
1. Navigate to Pulseway → Dashboard
2. View recent actions in the dashboard
3. Click "View All Actions" for complete history
4. Filter and search through action history

## Security Features

- All actions are logged with user attribution
- CSRF protection on all forms
- Authentication required for all Pulseway functions
- API credentials stored securely in Django settings

## Error Handling

- Comprehensive error handling for API failures
- User-friendly error messages
- Graceful degradation when API is unavailable
- Logging of all API interactions

## Testing

Run the test script to verify API connectivity:

```bash
python3 test_pulseway.py
```

## Dependencies

- Django 4.2.7
- slumber 0.7.1 (for API interactions)
- requests 2.31.0

## API Endpoints Used

- `/devices` - Device management
- `/sites` - Site management  
- `/groups` - Group management
- `/organizations` - Organization data
- `/devices/{id}/scripts` - Script execution
- `/devices/{id}/patches` - Patch installation
- `/devices/{id}/reboot` - Device reboot

## Future Enhancements

- Real-time device status updates
- Scheduled script execution
- Patch approval workflows
- Advanced filtering and search
- Bulk operations on multiple devices
- Integration with ticketing system
- Mobile-responsive design improvements
