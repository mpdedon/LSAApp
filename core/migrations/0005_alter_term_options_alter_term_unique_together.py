# Generated by Django 5.0.1 on 2025-04-17 11:48

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_alter_schoolday_options_alter_schoolday_date_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='term',
            options={'ordering': ['session__start_date', 'start_date']},
        ),
        migrations.AlterUniqueTogether(
            name='term',
            unique_together={('session', 'name')},
        ),
    ]
