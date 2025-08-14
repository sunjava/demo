from django.core.management.base import BaseCommand
from demo_app.models import Account, Line
from demo_app.chatbot import suspend_lines


class Command(BaseCommand):
    help = 'Test the improved suspend behavior that asks for clarification'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-id',
            type=int,
            help='Account ID to test with'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Test Improved Suspend Behavior ==='))
        
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
        
        # Show current line statuses
        all_lines = account.lines.all()
        self.stdout.write(f'\nCurrent lines in account ({all_lines.count()}):')
        
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
        
        # Test 1: Try to suspend without specifying a line
        self.stdout.write(f'\n--- Test 1: Suspend without specifying a line ---')
        result1 = suspend_lines(account.id)
        self._display_result("Suspend without specification", result1)
        
        # Test 2: Try to suspend with ambiguous identifier
        self.stdout.write(f'\n--- Test 2: Suspend with ambiguous identifier ---')
        result2 = suspend_lines(account.id, ["John"])
        self._display_result("Suspend with 'John'", result2)
        
        # Test 3: Try to suspend with specific identifier
        if all_lines.filter(status='ACTIVE').exists():
            active_line = all_lines.filter(status='ACTIVE').first()
            self.stdout.write(f'\n--- Test 3: Suspend with specific identifier ---')
            result3 = suspend_lines(account.id, [active_line.employee_name])
            self._display_result(f"Suspend with '{active_line.employee_name}'", result3)
        
        # Test 4: Try to suspend all lines
        self.stdout.write(f'\n--- Test 4: Suspend all lines ---')
        result4 = suspend_lines(account.id, ["all"])
        self._display_result("Suspend all lines", result4)
        
        self.stdout.write(self.style.SUCCESS('\n=== Test Complete ==='))
    
    def _display_result(self, test_name, result):
        """Display the result of a test"""
        self.stdout.write(f'\n{test_name}:')
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS(f'  ✅ Success: {result.get("lines_suspended", 0)} lines suspended'))
            if result.get("auto_suspended"):
                self.stdout.write(f'  📝 Auto-suspended the only available line')
            for line_result in result.get("results", []):
                self.stdout.write(f'    {line_result}')
        else:
            self.stdout.write(self.style.ERROR(f'  ❌ Failed: {result["error"]}'))
            
            if result.get("needs_clarification"):
                self.stdout.write(f'  🔍 Needs clarification: True')
                
                if result.get("available_lines"):
                    self.stdout.write(f'  📋 Available lines:')
                    for line in result["available_lines"]:
                        self.stdout.write(f'    • {line["employee_name"]} ({line["line_name"]}) - {line["msdn"]}')
                
                if result.get("matching_lines"):
                    self.stdout.write(f'  🔍 Matching lines:')
                    for line in result["matching_lines"]:
                        self.stdout.write(f'    • {line["employee_name"]} ({line["line_name"]}) - {line["msdn"]} - Status: {line["status"]}')
                
                if result.get("available_identifiers"):
                    self.stdout.write(f'  🏷️ Available identifiers: {result["available_identifiers"][:5]}...')



