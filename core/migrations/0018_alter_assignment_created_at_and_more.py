# Generated by Django 5.0.1 on 2024-12-24 21:31

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_alter_assignment_created_at_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assignment',
            name='created_at',
            field=models.DateTimeField(default=datetime.datetime(2024, 12, 24, 22, 31, 4, 447620)),
        ),
        migrations.AlterField(
            model_name='assignment',
            name='updated_at',
            field=models.DateTimeField(default=datetime.datetime(2024, 12, 24, 22, 31, 4, 447620)),
        ),
    ]
