from django.db import migrations


def activate_all_accounts(apps, schema_editor):
    Account = apps.get_model('demo_app', 'Account')
    Account.objects.exclude(status='ACTIVE').update(status='ACTIVE')


class Migration(migrations.Migration):

    dependencies = [
        ('demo_app', '0010_line_status_ordered_label'),
    ]

    operations = [
        migrations.RunPython(activate_all_accounts, migrations.RunPython.noop),
    ]
