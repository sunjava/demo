from django.core.management.base import BaseCommand
from demo_app.models import Account, Line
from demo_app.chatbot import _find_lines


class Command(BaseCommand):
    help = 'Test line searching functionality for chatbot'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-id',
            type=int,
            help='Account ID to test with'
        )
        parser.add_argument(
            '--line-identifier',
            type=str,
            help='Line identifier to search for'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Line Search Test ==='))
        
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
        
        # Show all lines in account
        all_lines = account.lines.all()
        self.stdout.write(f'\nAll lines in account ({all_lines.count()}):')
        for line in all_lines:
            self.stdout.write(f'  - {line.line_name} (MSDN: {line.msdn}, Employee: {line.employee_name}, Status: {line.status})')
        
        # Test line search
        if options['line_identifier']:
            identifier = options['line_identifier']
            self.stdout.write(f'\n--- Testing search for: "{identifier}" ---')
            
            # Test the _find_lines function
            found_lines = _find_lines(account, [identifier])
            
            if found_lines:
                self.stdout.write(self.style.SUCCESS(f'Found {len(found_lines)} lines:'))
                for line in found_lines:
                    self.stdout.write(f'  ✅ {line.line_name} (MSDN: {line.msdn}, Employee: {line.employee_name})')
            else:
                self.stdout.write(self.style.WARNING('No lines found'))
                
                # Show what we're searching for
                self.stdout.write(f'\nSearching in these fields:')
                self.stdout.write(f'  - line_name (contains "{identifier}")')
                self.stdout.write(f'  - msdn (contains "{identifier}")')
                self.stdout.write(f'  - employee_name (contains "{identifier}")')
                self.stdout.write(f'  - employee_number (contains "{identifier}")')
                
                # Show potential matches
                self.stdout.write(f'\nPotential matches (case-insensitive):')
                for line in all_lines:
                    if (identifier.lower() in line.line_name.lower() or
                        identifier.lower() in line.msdn.lower() or
                        identifier.lower() in line.employee_name.lower() or
                        identifier.lower() in line.employee_number.lower()):
                        self.stdout.write(f'  🔍 {line.line_name} (MSDN: {line.msdn}, Employee: {line.employee_name})')
        else:
            # Test with common identifiers
            self.stdout.write(f'\n--- Testing common search patterns ---')
            
            test_identifiers = [
                'Line 1',
                'Line 2', 
                'John',
                'Sarah',
                'EMP001',
                '+1-555'
            ]
            
            for identifier in test_identifiers:
                self.stdout.write(f'\nSearching for: "{identifier}"')
                found_lines = _find_lines(account, [identifier])
                
                if found_lines:
                    self.stdout.write(self.style.SUCCESS(f'  Found {len(found_lines)} lines'))
                    for line in found_lines:
                        self.stdout.write(f'    ✅ {line.line_name} ({line.msdn})')
                else:
                    self.stdout.write(f'  No lines found')
        
        self.stdout.write(self.style.SUCCESS('\n=== Line Search Test Complete ==='))
