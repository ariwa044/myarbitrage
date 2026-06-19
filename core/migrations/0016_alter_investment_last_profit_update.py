# Generated migration to fix last_profit_update field

from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_alter_cryptocurrency_symbol'),
    ]

    operations = [
        migrations.AlterField(
            model_name='investment',
            name='last_profit_update',
            field=models.DateTimeField(default=timezone.now),
        ),
    ]
