# Device Count Fixes for Sites and Groups Management

## Issue Identified
Sites and groups were showing 0 device counts because the Pulseway API doesn't include device count information in the sites and groups endpoints.

## Root Cause Analysis
1. **Sites API**: Returns basic site info (`Id`, `Name`, `ParentId`, `ParentName`) but no device count
2. **Groups API**: Returns basic group info (`Id`, `Name`, `ParentSiteId`, `ParentSiteName`) but no device count  
3. **Devices API**: Contains `SiteId` and `GroupId` fields that can be used to calculate counts

## Solution Implemented

### 1. Updated Views Logic
Modified `pulseway/views.py` to calculate device counts dynamically:

**Sites View:**
- Fetch all sites and all devices
- For each site, count devices where `device.SiteId == site.Id`
- Add `DeviceCount` field to each site object

**Groups View:**
- Fetch all groups and all devices  
- For each group, count devices where `device.GroupId == group.Id`
- Add `DeviceCount` field to each group object
- Add `SiteName` field using `ParentSiteName`

### 2. Updated Templates
Fixed field references in templates to match actual API data:

**Sites Template:**
- Changed from `site.Description` to `site.ParentName` (organization)
- Changed from `site.CreatedDate` to `site.ParentName` (organization info)
- Updated search to use `organization` instead of `description`

**Groups Template:**
- Changed from `group.Description` to `group.Notes`
- Changed from `group.SiteName` to `group.ParentSiteName`
- Updated search to use `notes` instead of `description`

## Test Results

### Device Distribution:
- **Total Devices**: 491
- **Sites with Devices**: 6 out of 10
- **Groups with Devices**: 6 out of 10

### Sample Counts:
- MarketXcel users: 248 devices
- Delhi site: 160 devices  
- Digtinctive Pune users: 64 devices
- FIICC REMOTE USERS: 9 devices
- Aiqmen Remote Users: 6 devices
- Servers: 4 devices

## Files Modified

### 1. `/pulseway/views.py`
- Updated `sites()` function to calculate device counts
- Updated `groups()` function to calculate device counts
- Added proper error handling

### 2. `/templates/pulseway/sites.html`
- Fixed field references to match API data
- Updated search functionality
- Improved data display

### 3. `/templates/pulseway/groups.html`  
- Fixed field references to match API data
- Updated search functionality
- Improved data display

## Performance Considerations
- Device count calculation happens on each page load
- For large datasets, consider caching or background calculation
- Current implementation handles 491 devices efficiently

## Verification
✅ Device counts now display correctly in both sites and groups management
✅ Search functionality works with correct field names
✅ UI shows accurate device distribution across sites and groups
✅ No more "0 devices" showing incorrectly

The sites and groups management pages now accurately display device counts and provide proper organization information.
