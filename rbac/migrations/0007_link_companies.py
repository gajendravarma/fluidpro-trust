# Link UserProfile to Company objects

from django.db import migrations


def link_profiles_to_companies(apps, schema_editor):
    UserProfile = apps.get_model('rbac', 'UserProfile')
    Company = apps.get_model('rbac', 'Company')
    
    for profile in UserProfile.objects.all():
        if profile.company_old:
            try:
                company = Company.objects.get(name=profile.company_old)
                profile.company = company
                profile.save()
            except Company.DoesNotExist:
                pass


def reverse_link(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('rbac', '0006_company_migration'),
    ]

    operations = [
        migrations.RunPython(link_profiles_to_companies, reverse_link),
        
        # Remove old company field
        migrations.RemoveField(
            model_name='userprofile',
            name='company_old',
        ),
    ]
