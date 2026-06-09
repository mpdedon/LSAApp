from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_add_nin_education_ndpr_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='batch_reference',
            field=models.CharField(blank=True, db_index=True, default='', max_length=64),
        ),
    ]