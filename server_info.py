#!/usr/bin/env python3
"""
Django Server Information Script
Shows server status and available endpoints
"""

import subprocess
import sys
import os

def check_server_status():
    """Check if Django server is running"""
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if 'runserver' in result.stdout:
            print("✅ Django server is running")
            return True
        else:
            print("❌ Django server is not running")
            return False
    except Exception as e:
        print(f"Error checking server status: {e}")
        return False

def show_project_info():
    """Display project information"""
    print("\n" + "="*60)
    print("🚀 FLUIDTRUST DJANGO PROJECT")
    print("="*60)
    
    print("\n📁 Project Structure:")
    print("├── customer_portal/     # Main Django project")
    print("├── rbac/               # Role-based access control")
    print("├── tickets/            # Ticket management")
    print("├── pulseway/           # Pulseway integration")
    print("├── office365/          # Office 365 integration")
    print("├── mdm/                # Mobile device management")
    print("├── chatbot/            # AI chatbot")
    print("├── datto/              # Datto integration")
    print("├── site24x7/           # Site24x7 monitoring")
    print("└── templates/          # HTML templates")
    
    print("\n🌐 Available Endpoints:")
    print("├── http://localhost:8000/           # Home dashboard")
    print("├── http://localhost:8000/admin/     # Django admin")
    print("├── http://localhost:8000/login/     # User login")
    print("├── http://localhost:8000/register/  # User registration")
    print("├── http://localhost:8000/tickets/   # Ticket management")
    print("├── http://localhost:8000/pulseway/  # Pulseway dashboard")
    print("├── http://localhost:8000/office365/ # Office 365 analytics")
    print("├── http://localhost:8000/mdm/       # MDM dashboard")
    print("├── http://localhost:8000/chatbot/   # AI chatbot")
    print("├── http://localhost:8000/datto/     # Datto backup")
    print("└── http://localhost:8000/site24x7/  # Site24x7 monitoring")
    
    print("\n🔧 Server Information:")
    print(f"├── Host: 0.0.0.0:8000")
    print(f"├── Environment: Development")
    print(f"├── Database: SQLite (db.sqlite3)")
    print(f"├── Debug Mode: Enabled")
    print(f"└── Static Files: /static/")

def main():
    print("Checking Django server status...")
    
    if check_server_status():
        show_project_info()
        print("\n✨ Server is ready! You can access the application at:")
        print("   🔗 http://localhost:8000")
        print("\n💡 Tips:")
        print("   • Use Ctrl+C to stop the server")
        print("   • Check server.log for detailed logs")
        print("   • Admin interface available at /admin/")
    else:
        print("\n❌ Server is not running. To start it:")
        print("   cd /home/devops-machine/Fluidtrust-project/claude-changes")
        print("   source venv/bin/activate")
        print("   python manage.py runserver 0.0.0.0:8000")

if __name__ == "__main__":
    main()
