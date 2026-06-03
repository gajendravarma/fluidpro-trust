from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rbac', '0010_companylicense'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='contact_email',
            field=models.EmailField(
                blank=True,
                help_text=(
                    'Primary contact email for license renewal notifications. '
                    'If blank, all company users will be notified.'
                ),
            ),
        ),
        migrations.CreateModel(
            name='LicenseRenewalNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('days_before', models.IntegerField(choices=[(15, '15 days before'), (7, '7 days before'), (1, '1 day before')])),
                ('license_expiry_date', models.DateField(help_text='Snapshot of expiry_date when the email was sent')),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('recipients', models.TextField(blank=True, help_text='Comma-separated list of emails this notification was sent to')),
                ('success', models.BooleanField(default=True)),
                ('error_message', models.TextField(blank=True)),
                ('license', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='renewal_notifications',
                    to='rbac.companylicense',
                )),
            ],
            options={
                'ordering': ['-sent_at'],
                'unique_together': {('license', 'days_before', 'license_expiry_date')},
            },
        ),
    ]
