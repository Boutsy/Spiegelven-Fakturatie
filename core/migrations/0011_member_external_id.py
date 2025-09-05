# AUTO-REWRITTEN to avoid unique constraint on external_id during add
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0010_remove_member_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='member',
            name='external_id',
            field=models.CharField(max_length=50, null=True, blank=True, db_index=True),
        ),
    ]
