import uuid

from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_payment_batch_reference'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentReceipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('receipt_number', models.CharField(blank=True, db_index=True, max_length=32, unique=True)),
                ('share_token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('scope', models.CharField(choices=[('single', 'Single Payment'), ('guardian', 'Guardian Bulk Payment'), ('class', 'Class Bulk Payment')], default='single', max_length=20)),
                ('batch_reference', models.CharField(blank=True, db_index=True, default='', max_length=64)),
                ('class_label', models.CharField(blank=True, default='', max_length=120)),
                ('total_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('payment_date', models.DateField(default=django.utils.timezone.now)),
                ('issued_at', models.DateTimeField(auto_now_add=True)),
                ('line_items', models.JSONField(blank=True, default=list)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='issued_payment_receipts', to=settings.AUTH_USER_MODEL)),
                ('guardian', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='payment_receipts', to='core.guardian')),
                ('payments', models.ManyToManyField(blank=True, related_name='receipts', to='core.payment')),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='payment_receipts', to='core.student')),
                ('term', models.ForeignKey(on_delete=models.CASCADE, related_name='payment_receipts', to='core.term')),
            ],
            options={'ordering': ['-payment_date', '-issued_at']},
        ),
    ]