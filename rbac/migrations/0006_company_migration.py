# Generated migration to handle company field change

from django.db import migrations, models
import django.db.models.deletion


def migrate_company_data(apps, schema_editor):
    UserProfile = apps.get_model('rbac', 'UserProfile')
    Company = apps.get_model('rbac', 'Company')
    
    # Get all unique company names from existing profiles
    company_names = UserProfile.objects.values_list('company', flat=True).distinct()
    
    # Create Company objects for each unique company name
    for company_name in company_names:
        if company_name:
            Company.objects.get_or_create(
                name=company_name,
                defaults={'code': company_name.lower().replace(' ', '_')}
            )


def reverse_migrate(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('rbac', '0005_licenseconfig'),
    ]

    operations = [
        # Step 1: Create Company model
        migrations.CreateModel(
            name='Company',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True)),
                ('code', models.CharField(max_length=50, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name_plural': 'Companies',
            },
        ),
        
        # Step 2: Rename old company field
        migrations.RenameField(
            model_name='userprofile',
            old_name='company',
            new_name='company_old',
        ),
        
        # Step 3: Add new company ForeignKey field (nullable)
        migrations.AddField(
            model_name='userprofile',
            name='company',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='users', to='rbac.company'),
        ),
        
        # Step 4: Migrate data
        migrations.RunPython(migrate_company_data, reverse_migrate),
    ]
