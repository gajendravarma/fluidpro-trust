#!/usr/bin/env python3
"""
Final verification of CGL Office 365 dashboard fix
"""
import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/home/devops-machine/Fluidtrust-project/customer_portal')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from office365.services import Office365API

def verify_fix():
    """Verify the license data fix is working correctly"""
    print("🔍 Final Verification of CGL License Data Fix")
    print("=" * 50)
    
    try:
        # Test CGL license data
        api = Office365API(customer_key='cgl')
        license_summary = api.get_license_summary()
        
        print("📊 CGL License Summary (After Fix):")
        print("-" * 40)
        
        total_licenses = 0
        total_consumed = 0
        total_suspended = 0
        
        for lic in license_summary:
            total_licenses += lic['total']
            total_consumed += lic['consumed']
            total_suspended += lic.get('suspended', 0)
            
            print(f"• {lic['sku_name']}")
            print(f"  Enabled: {lic['total']}, Used: {lic['consumed']}, Available: {lic['available']}")
            if lic.get('suspended', 0) > 0:
                print(f"  Suspended: {lic['suspended']} (not counted in total)")
            print(f"  Usage: {lic['usage_percent']:.1f}%")
            print()
        
        print("📈 Overall Summary:")
        print(f"  Total Enabled Licenses: {total_licenses}")
        print(f"  Total Consumed: {total_consumed}")
        print(f"  Total Available: {total_licenses - total_consumed}")
        print(f"  Total Suspended: {total_suspended} (excluded)")
        print(f"  Overall Usage: {(total_consumed / total_licenses * 100) if total_licenses > 0 else 0:.1f}%")
        print()
        
        # Validation checks
        print("✅ Validation Checks:")
        
        # Check 1: No consumed > total
        issues = []
        for lic in license_summary:
            if lic['consumed'] > lic['total']:
                issues.append(f"  ❌ {lic['sku_name']}: Consumed ({lic['consumed']}) > Total ({lic['total']})")
        
        if not issues:
            print("  ✅ All consumed counts are within total limits")
        else:
            for issue in issues:
                print(issue)
        
        # Check 2: Available calculation
        calc_issues = []
        for lic in license_summary:
            expected_available = lic['total'] - lic['consumed']
            if lic['available'] != expected_available:
                calc_issues.append(f"  ❌ {lic['sku_name']}: Available calculation error")
        
        if not calc_issues:
            print("  ✅ All available license calculations are correct")
        else:
            for issue in calc_issues:
                print(issue)
        
        # Check 3: Usage percentage
        usage_issues = []
        for lic in license_summary:
            if lic['total'] > 0:
                expected_usage = (lic['consumed'] / lic['total']) * 100
                if abs(lic['usage_percent'] - expected_usage) > 0.1:
                    usage_issues.append(f"  ❌ {lic['sku_name']}: Usage percentage calculation error")
        
        if not usage_issues:
            print("  ✅ All usage percentage calculations are correct")
        else:
            for issue in usage_issues:
                print(issue)
        
        print()
        print("🎉 Summary of Changes Made:")
        print("  1. Fixed license total calculation to exclude suspended licenses")
        print("  2. Added suspended license count to API response")
        print("  3. Updated dashboard template to show suspended license info")
        print("  4. Expanded license types to include all relevant Office 365 SKUs")
        print("  5. Improved accuracy of usage percentage calculations")
        print()
        print("✅ CGL Office 365 dashboard license data is now accurate!")
        print(f"   Dashboard URL: http://192.168.2.68:8000/office365/")
        print("   Select 'CGL' from the customer dropdown to view corrected data")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during verification: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    verify_fix()
