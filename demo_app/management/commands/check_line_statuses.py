from django.core.management.base import BaseCommand
from demo_app.models import Account, Line


class Command(BaseCommand):
    help = 'Check current line statuses in all accounts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-id',
            type=int,
            help='Check specific account ID only'
        )

    def handle(self, *args, **options):
        account_id = options.get('account_id')
        
        if account_id:
            # Check specific account
            try:
                account = Account.objects.get(id=account_id)
                self._check_account_status(account)
            except Account.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Account with ID {account_id} not found')
                )
        else:
            # Check all accounts
            accounts = Account.objects.all()
            if not accounts.exists():
                self.stdout.write(self.style.WARNING('No accounts found in database'))
                return
            
            for account in accounts:
                self._check_account_status(account)
                self.stdout.write('-' * 50)

    def _check_account_status(self, account):
        self.stdout.write(f'\nAccount #{account.id}: {account.account_number}')
        self.stdout.write(f'Status: {account.get_status_display()}')
        self.stdout.write(f'Type: {account.get_account_type_display()}')
        
        lines = account.lines.all()
        if not lines.exists():
            self.stdout.write('  No lines found')
            return
        
        # Count by status
        status_counts = {}
        for line in lines:
            status = line.status
            if status not in status_counts:
                status_counts[status] = []
            status_counts[status].append(line)
        
        self.stdout.write(f'  Total lines: {lines.count()}')
        for status, line_list in status_counts.items():
            self.stdout.write(f'  {status}: {len(line_list)}')
            
            # Show details for each status
            for line in line_list:
                self.stdout.write(f'    • {line.line_name} ({line.msdn}) - {line.employee_name}')
        
        # Show specific status breakdowns
        if 'SUSPENDED' in status_counts:
            self.stdout.write(f'\n  Suspended lines ({len(status_counts["SUSPENDED"])}):')
            for line in status_counts['SUSPENDED']:
                self.stdout.write(f'    • {line.line_name} ({line.msdn}) - {line.employee_name}')
        
        if 'CANCELLED' in status_counts:
            self.stdout.write(f'\n  Cancelled lines ({len(status_counts["CANCELLED"])}):')
            for line in status_counts['CANCELLED']:
                self.stdout.write(f'    • {line.line_name} ({line.msdn}) - {line.employee_name}')
