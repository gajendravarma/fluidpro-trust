# Office 365 Multi-Customer Support

## Overview
The Office 365 dashboard now supports multiple customers with separate tenant configurations. Users can switch between Wepsol and CGL customers using a dropdown selector.

## Features
- **Customer Selection**: Dropdown in the dashboard header to switch between customers
- **Session Persistence**: Selected customer is remembered during the session
- **Separate Configurations**: Each customer has its own tenant ID, client ID, and client secret
- **Consistent UI**: Customer selector appears on all Office 365 pages (dashboard, teams analytics, email analytics)

## Customer Configurations

### Wepsol (Default)
- **Environment Variables**: `WEPSOL_TENANT_ID`, `WEPSOL_CLIENT_ID`, `WEPSOL_CLIENT_SECRET`

### CGL
- **Environment Variables**: `CGL_TENANT_ID`, `CGL_CLIENT_ID`, `CGL_CLIENT_SECRET`

## How It Works

### 1. Customer Configuration (`office365/customer_config.py`)
- Centralized configuration for all customers
- Easy to add new customers by updating the `CUSTOMER_CONFIGS` dictionary

### 2. API Service Updates (`office365/services.py`)
- `Office365API` class now accepts a `customer_key` parameter
- Automatically loads the correct configuration based on the selected customer

### 3. View Updates (`office365/views.py`)
- All views now support customer selection
- Customer selection is stored in the user's session
- Default customer is 'wepsol' if none selected

### 4. Template Updates
- Customer dropdown added to all Office 365 templates
- Dropdown automatically submits when changed
- Current selection is highlighted

## Usage

1. **Navigate to Office 365 Dashboard**: Go to `/office365/dashboard/`
2. **Select Customer**: Use the dropdown in the top-right corner to select between Wepsol and CGL
3. **View Data**: All data (licenses, mailboxes, teams, email) will be loaded for the selected customer
4. **Switch Customers**: Change the dropdown selection to switch between customers instantly

## Adding New Customers

To add a new customer:

1. **Update Configuration**: Add new customer to `CUSTOMER_CONFIGS` in `office365/customer_config.py`:
   ```python
   'new_customer': {
       'name': 'New Customer Name',
       'tenant_id': 'your-tenant-id',
       'client_id': 'your-client-id',
       'client_secret': 'your-client-secret'
   }
   ```

2. **No Code Changes Required**: The system will automatically detect and include the new customer in the dropdown.

## Technical Details

- **Session Storage**: Customer selection is stored in `request.session['office365_customer']`
- **Default Fallback**: If no customer is selected, defaults to 'wepsol'
- **Error Handling**: Graceful error handling if customer configuration is not found
- **Backward Compatibility**: Still supports the old environment variable method as fallback

## Files Modified

1. `office365/customer_config.py` - New customer configuration file
2. `office365/services.py` - Updated to support customer-specific configurations
3. `office365/views.py` - Updated all views to handle customer selection
4. `templates/office365/dashboard.html` - Added customer dropdown
5. `templates/office365/teams_analytics.html` - Added customer dropdown
6. `templates/office365/email_analytics.html` - Added customer dropdown
