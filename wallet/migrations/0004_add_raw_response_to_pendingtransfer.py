"""Add raw_response JSON field to PendingTransfer

This field stores the raw JSON payload received from M-Pesa result callbacks.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0003_add_reference_id_to_pendingtransfer'),
    ]

    operations = [
        migrations.AddField(
            model_name='pendingtransfer',
            name='raw_response',
            field=models.JSONField(blank=True, null=True, help_text='Raw JSON response received from the M-Pesa callback'),
        ),
    ]
