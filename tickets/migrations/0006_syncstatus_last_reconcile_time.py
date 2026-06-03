from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0005_me_user_cache'),
    ]

    operations = [
        migrations.AddField(
            model_name='syncstatus',
            name='last_reconcile_time',
            field=models.DateTimeField(blank=True, null=True,
                                       help_text='Last time the daily reconcile (ghost-ticket purge) ran'),
        ),
    ]
