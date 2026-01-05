# Generated manually to remove grace_period and end_date fields from Contribution model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chamas', '0055_remove_contributionrecord_cluster'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='contribution',
            name='grace_period',
        ),
        migrations.RemoveField(
            model_name='contribution',
            name='end_date',
        ),
    ]