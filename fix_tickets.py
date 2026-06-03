#!/usr/bin/env python3
"""
Fix ticket pagination by replacing showTickets function
"""

# Read template
with open('/home/devops-machine/Fluidtrust-project/customer_portal/templates/rbac/company_dashboard.html', 'r') as f:
    content = f.read()

# Replace showTickets function calls in HTML
content = content.replace('onclick="showTickets(\'Open\')"', 'onclick="showTicketDetails(\'Open\')"')
content = content.replace('onclick="showTickets(\'Progress\')"', 'onclick="showTicketDetails(\'Progress\')"') 
content = content.replace('onclick="showTickets(\'Pending\')"', 'onclick="showTicketDetails(\'Pending\')"')
content = content.replace('onclick="showTickets(\'Resolved\')"', 'onclick="showTicketDetails(\'Resolved\')"')
content = content.replace('onclick="showTickets(\'Closed\')"', 'onclick="showTicketDetails(\'Closed\')"')
content = content.replace('onclick="showTickets(\'Cancelled\')"', 'onclick="showTicketDetails(\'Cancelled\')"')
content = content.replace('onclick="showTickets(\'Hold\')"', 'onclick="showTicketDetails(\'Hold\')"')
content = content.replace('onclick="showTickets(\'all\')"', 'onclick="showTicketDetails(\'all\')"')

# Write back
with open('/home/devops-machine/Fluidtrust-project/customer_portal/templates/rbac/company_dashboard.html', 'w') as f:
    f.write(content)

print("✅ Fixed all showTickets calls to use showTicketDetails")
