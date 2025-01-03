# Generated by Django 5.0.1 on 2024-11-23 01:09

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_student_promotion_history_student_status_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='class',
            name='order',
            field=models.PositiveIntegerField(default=None, unique=True),
        ),
        migrations.AlterField(
            model_name='assignment',
            name='created_at',
            field=models.DateTimeField(default=datetime.datetime(2024, 11, 23, 2, 9, 40, 191301)),
        ),
        migrations.AlterField(
            model_name='assignment',
            name='updated_at',
            field=models.DateTimeField(default=datetime.datetime(2024, 11, 23, 2, 9, 40, 191301)),
        ),
    ]
