# Generated migration for Document model enhancement

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chamas', '0001_initial'),  # Replace with your latest migration
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='file_type',
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AddField(
            model_name='document',
            name='file_size',
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]