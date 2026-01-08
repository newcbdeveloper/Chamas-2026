"""Add reference_id UUID field to PendingTransfer

Generated manually to add a UUID for existing rows safely.
"""
from __future__ import annotations

import uuid
from django.db import migrations, models


def generate_reference_ids(apps, schema_editor):
  PendingTransfer = apps.get_model('wallet', 'PendingTransfer')
  for pt in PendingTransfer.objects.filter(reference_id__isnull=True):
    pt.reference_id = uuid.uuid4()
    pt.save(update_fields=['reference_id'])


class Migration(migrations.Migration):

  dependencies = [
    ('wallet', '0002_pendingtransfer_auto_approved_and_more'),
  ]

  operations = [
    migrations.AddField(
      model_name='pendingtransfer',
      name='reference_id',
      field=models.UUIDField(null=True, editable=False),
    ),
    migrations.RunPython(generate_reference_ids, reverse_code=migrations.RunPython.noop),
    migrations.AlterField(
      model_name='pendingtransfer',
      name='reference_id',
      field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
    ),
  ]
