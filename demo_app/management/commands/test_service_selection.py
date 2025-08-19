from django.core.management.base import BaseCommand
from demo_app.models import Account
from demo_app.chatbot import add_service_to_lines


class Command(BaseCommand):
    help = 'Test the improved service selection behavior that asks for clarification'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-id',
            type=int,
            help='Account ID to test with'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Test Improved Service Selection ==='))
        
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
        
        for line in all_lines:
            self.stdout.write(f'  - {line.line_name} (MSDN: {line.msdn}, Employee: {line.employee_name}, Status: {line.status})')
        
        # Test 1: Try to add service without specifying which service
        self.stdout.write(f'\n--- Test 1: Add service without specifying which service ---')
        result1 = add_service_to_lines(account.id, "")  # Empty service type
        self._display_result("Add service without specification", result1)
        
        # Test 2: Try to add service with invalid service type
        self.stdout.write(f'\n--- Test 2: Add service with invalid service type ---')
        result2 = add_service_to_lines(account.id, "invalid_service")
        self._display_result("Add invalid service", result2)
        
        # Test 3: Try to add service with valid service type
        self.stdout.write(f'\n--- Test 3: Add service with valid service type ---')
        result3 = add_service_to_lines(account.id, "1_day", ["all"])
        self._display_result("Add 1-day pass to all lines", result3)
        
        self.stdout.write(self.style.SUCCESS('\n=== Test Complete ==='))
    
    def _display_result(self, test_name, result):
        """Display the result of a test"""
        self.stdout.write(f'\n{test_name}:')
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS(f'  ✅ Success: {result.get("lines_affected", 0)} lines affected'))
            self.stdout.write(f'  💰 Total cost: ${result.get("total_cost", 0):.2f}')
            for line_result in result.get("results", []):
                self.stdout.write(f'    {line_result}')
        else:
            self.stdout.write(self.style.ERROR(f'  ❌ Failed: {result["error"]}'))
            
            if result.get("needs_clarification"):
                self.stdout.write(f'  🔍 Needs clarification: True')
                
                if result.get("available_services"):
                    self.stdout.write(f'  📋 Available services:')
                    for service in result["available_services"]:
                        self.stdout.write(f'    • {service["name"]} - {service["price"]} ({service["data"]} data, {service["duration"]})')





