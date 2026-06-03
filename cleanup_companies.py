#!/usr/bin/env python3
"""
Clean up duplicate/similar company names using fuzzy matching
"""
import os
import sys
import django
from difflib import SequenceMatcher

# Setup Django
sys.path.append('/home/devops-machine/Fluidtrust-project/customer_portal')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customer_portal.settings')
django.setup()

from rbac.models import Company, CompanyLicense
from mdm.models import MdmCustomer

def similarity(a, b):
    """Calculate similarity between two strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def cleanup_duplicate_companies():
    """Find and merge similar company names"""
    print("🔍 CLEANING UP DUPLICATE COMPANIES")
    print("=" * 50)
    
    companies = Company.objects.all()
    duplicates_found = []
    
    # Find similar companies
    for i, company1 in enumerate(companies):
        for company2 in companies[i+1:]:
            sim = similarity(company1.name, company2.name)
            if sim > 0.7:  # 70% similarity threshold
                duplicates_found.append((company1, company2, sim))
    
    print(f"\n📊 Found {len(duplicates_found)} potential duplicates:")
    for comp1, comp2, sim in duplicates_found:
        print(f"   {comp1.name} ↔ {comp2.name} ({sim:.2%} similar)")
    
    # Show companies with and without licenses
    companies_with_licenses = Company.objects.filter(licenses__isnull=False).distinct()
    companies_without_licenses = Company.objects.filter(licenses__isnull=True)
    
    print(f"\n🏢 Companies with licenses ({companies_with_licenses.count()}):")
    for company in companies_with_licenses:
        license_count = company.licenses.count()
        print(f"   ✅ {company.name} ({company.code}) - {license_count} licenses")
    
    print(f"\n🏢 Companies without licenses ({companies_without_licenses.count()}):")
    for company in companies_without_licenses:
        print(f"   ❌ {company.name} ({company.code}) - 0 licenses")
    
    # Recommendation
    print(f"\n💡 RECOMMENDATIONS:")
    print(f"   - Only show companies with licenses in admin panel")
    print(f"   - Consider merging similar companies:")
    for comp1, comp2, sim in duplicates_found:
        if comp1.licenses.exists() and not comp2.licenses.exists():
            print(f"     → Keep '{comp1.name}', remove '{comp2.name}'")
        elif comp2.licenses.exists() and not comp1.licenses.exists():
            print(f"     → Keep '{comp2.name}', remove '{comp1.name}'")
    
    print(f"\n✅ Analysis complete!")

if __name__ == '__main__':
    cleanup_duplicate_companies()
