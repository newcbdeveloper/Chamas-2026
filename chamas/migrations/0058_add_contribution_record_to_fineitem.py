# Generated manually for adding contribution_record field to FineItem

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chamas', '0057_merge_20250729_1409'),
    ]

    operations = [
        migrations.AddField(
            model_name='fineitem',
            name='contribution_record',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='fines', to='chamas.contributionrecord'),
        ),
    ]