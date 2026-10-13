from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('demo_app', '0009_line_status_awaiting_shipment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='line',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING_SHIPMENT', 'Ordered'),
                    ('SHIPPED', 'Shipped'),
                    ('ACTIVE', 'Active'),
                    ('SUSPENDED', 'Suspended'),
                    ('CANCELLED', 'Cancelled'),
                ],
                default='ACTIVE',
                max_length=20,
            ),
        ),
    ]
