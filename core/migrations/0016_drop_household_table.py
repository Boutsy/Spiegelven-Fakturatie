from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0015_delete_household'),
    ]
    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS core_household",
            reverse_sql="/* noop */",
        ),
    ]
