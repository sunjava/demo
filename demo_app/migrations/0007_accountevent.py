from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('demo_app', '0006_line_activation_statuses'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccountEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('occurred_at', models.DateTimeField()),
                ('event_type', models.CharField(choices=[
                    ('LINE_ADDED', 'Line added'),
                    ('DISPATCHED', 'Dispatched'),
                    ('ACTIVATED', 'Activated'),
                    ('SUSPENDED', 'Suspended'),
                    ('RESTORED', 'Restored'),
                    ('REACTIVATED', 'Reactivated'),
                    ('SERVICE_ADDED', 'Service added'),
                    ('PAYMENT', 'Payment'),
                    ('STATEMENT', 'Statement'),
                ], max_length=32)),
                ('summary', models.CharField(max_length=255)),
                ('amount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('reference', models.CharField(blank=True, default='', max_length=255)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='demo_app.account')),
                ('line', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='events', to='demo_app.line')),
            ],
            options={
                'ordering': ['-occurred_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='accountevent',
            index=models.Index(fields=['account', '-occurred_at'], name='demo_app_ac_account_occur_idx'),
        ),
    ]
