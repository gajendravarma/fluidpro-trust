#!/usr/bin/env python3
"""
Quick fix - just update the JavaScript to call the right endpoints
"""

# Read the template
with open('/home/devops-machine/Fluidtrust-project/customer_portal/templates/rbac/company_dashboard.html', 'r') as f:
    content = f.read()

# Replace the wrong API calls with correct ones
content = content.replace('/rbac/api/company-devices/', '/rbac/api/device-details/')
content = content.replace('/rbac/api/company-tickets/', '/rbac/api/ticket-details/')

# Write back
with open('/home/devops-machine/Fluidtrust-project/customer_portal/templates/rbac/company_dashboard.html', 'w') as f:
    f.write(content)

print("✅ Fixed JavaScript API calls in template")
print("- Changed /rbac/api/company-devices/ → /rbac/api/device-details/")  
print("- Changed /rbac/api/company-tickets/ → /rbac/api/ticket-details/")
