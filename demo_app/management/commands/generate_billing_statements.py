from django.core.management.base import BaseCommand

from demo_app.billing import generate_billing_statements
from demo_app.models import Account


class Command(BaseCommand):
    help = 'Generate monthly billing statements and amount due for accounts'

    def add_arguments(self, parser):
        parser.add_argument('--account-id', type=int, help='Limit generation to a single account ID')
        parser.add_argument(
            '--recreate',
            action='store_true',
            help='Delete and regenerate statements for the selected periods',
        )

    def handle(self, *args, **options):
        accounts = Account.objects.all()
        if options.get('account_id'):
            accounts = accounts.filter(id=options['account_id'])
            if not accounts.exists():
                self.stderr.write(self.style.ERROR(f"No account found with id={options['account_id']}"))
                return

        result = generate_billing_statements(accounts, recreate=options.get('recreate', False))
        self.stdout.write(self.style.SUCCESS(
            f"Generated {result['created']} statement(s) "
            f"({result['skipped']} already existed) "
            f"across {result['accounts']} account(s)."
        ))
