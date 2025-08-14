from django.core.management.base import BaseCommand
from demo_app.models import Account, Line
from demo_app.chatbot import reactivate_cancelled_lines


class Command(BaseCommand):
    help = 'Test reactivate cancelled lines functionality for chatbot'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-id',
            type=int,
            help='Account ID to test with'
        )
        parser.add_argument(
            '--line-identifier',
            type=str,
            help='Line identifier to reactivate'
        )
        parser.add_argument(
            '--create-test-data',
            action='store_true',
            help='Create test cancelled lines if none exist'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Reactivate Cancelled Lines Test ==='))
        
        # Get account
        if options['account_id']:
            try:
                account = Account.objects.get(id=options['account_id'])
            except Account.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Account {options["account_id"]} not found'))
                return
        else:
            # Use first account
            account = Account.objects.first()
            if not account:
                self.stdout.write(self.style.ERROR('No accounts found'))
                return
        
        self.stdout.write(f'Testing with account: {account.account_number} (ID: {account.id})')
        
        # Show all lines in account with their statuses
        all_lines = account.lines.all()
        self.stdout.write(f'\nAll lines in account ({all_lines.count()}):')
        
        status_counts = {}
        for line in all_lines:
            status = line.status
            if status not in status_counts:
                status_counts[status] = []
            status_counts[status].append(line)
            
            self.stdout.write(f'  - {line.line_name} (MSDN: {line.msdn}, Employee: {line.employee_name}, Status: {line.status})')
        
        # Show status breakdown
        self.stdout.write(f'\nStatus breakdown:')
        for status, lines in status_counts.items():
            self.stdout.write(f'  {status}: {len(lines)} lines')
        
        # Check if we have cancelled lines
        cancelled_lines = account.lines.filter(status='CANCELLED')
        if not cancelled_lines.exists():
            if options['create_test_data']:
                self.stdout.write(self.style.WARNING('\nNo cancelled lines found. Creating test cancelled lines...'))
                self._create_test_cancelled_lines(account)
                cancelled_lines = account.lines.filter(status='CANCELLED')
            else:
                self.stdout.write(self.style.WARNING('\nNo cancelled lines found. Use --create-test-data to create test lines.'))
                return
        
        self.stdout.write(f'\nFound {cancelled_lines.count()} cancelled lines:')
        for line in cancelled_lines:
            self.stdout.write(f'  - {line.line_name} (MSDN: {line.msdn}, Employee: {line.employee_name})')
        
        # Test reactivation
        if options['line_identifier']:
            identifier = options['line_identifier']
            self.stdout.write(f'\n--- Testing reactivation for: "{identifier}" ---')
            
            # Test the reactivate_cancelled_lines function
            result = reactivate_cancelled_lines(account.id, [identifier])
            
            if result['success']:
                self.stdout.write(self.style.SUCCESS(f'✅ Reactivation successful!'))
                self.stdout.write(f'Lines reactivated: {result["lines_reactivated"]}')
                for line_result in result['results']:
                    self.stdout.write(f'  {line_result}')
            else:
                self.stdout.write(self.style.ERROR(f'❌ Reactivation failed: {result["error"]}'))
                if 'available_identifiers' in result:
                    self.stdout.write(f'Available identifiers: {result["available_identifiers"][:10]}...')
        else:
            # Test reactivating all cancelled lines
            self.stdout.write(f'\n--- Testing reactivation of all cancelled lines ---')
            
            result = reactivate_cancelled_lines(account.id)
            
            if result['success']:
                self.stdout.write(self.style.SUCCESS(f'✅ Reactivation successful!'))
                self.stdout.write(f'Lines reactivated: {result["lines_reactivated"]}')
                for line_result in result['results']:
                    self.stdout.write(f'  {line_result}')
            else:
                self.stdout.write(self.style.ERROR(f'❌ Reactivation failed: {result["error"]}'))
        
        # Show final status
        self.stdout.write(f'\n--- Final Status ---')
        final_lines = account.lines.all()
        final_status_counts = {}
        for line in final_lines:
            status = line.status
            if status not in final_status_counts:
                final_status_counts[status] = []
            final_status_counts[status].append(line)
        
        for status, lines in final_status_counts.items():
            self.stdout.write(f'  {status}: {len(lines)} lines')
        
        self.stdout.write(self.style.SUCCESS('\n=== Reactivate Cancelled Lines Test Complete ==='))
    
    def _create_test_cancelled_lines(self, account):
        """Create test cancelled lines for testing purposes"""
        try:
            # Create a test cancelled line
            test_line = Line.objects.create(
                account=account,
                line_name='Test Cancelled Line',
                msdn='+1-555-9999',
                employee_name='Test Employee',
                employee_number='TEST001',
                status='CANCELLED',
                plan_name='Basic Plan',
                device_model='iPhone 15',
                device_color='Black',
                device_storage='128GB'
            )
            
            self.stdout.write(self.style.SUCCESS(f'Created test cancelled line: {test_line.line_name}'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to create test line: {str(e)}'))



