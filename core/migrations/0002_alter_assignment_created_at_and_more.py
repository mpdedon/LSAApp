# Generated by Django 5.0.1 on 2024-11-18 23:42

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assignment',
            name='created_at',
            field=models.DateTimeField(default=datetime.datetime(2024, 11, 19, 0, 42, 47, 801312)),
        ),
        migrations.AlterField(
            model_name='assignment',
            name='updated_at',
            field=models.DateTimeField(default=datetime.datetime(2024, 11, 19, 0, 42, 47, 801312)),
        ),
        migrations.AlterField(
            model_name='guardian',
            name='profile_image',
            field=models.ImageField(default='profile_images/default.jpg', upload_to='media/profile_images/'),
        ),
        migrations.AlterField(
            model_name='student',
            name='profile_image',
            field=models.ImageField(default='profile_images/default.jpg', upload_to='media/profile_images/'),
        ),
        migrations.AlterField(
            model_name='teacher',
            name='profile_image',
            field=models.ImageField(default='profile_images/default.jpg', upload_to='media/profile_images/'),
        ),
    ]