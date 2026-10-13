from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('demo_app', '0007_accountevent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='line',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING_SHIPMENT', 'Shipment'),
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
