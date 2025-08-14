from django.core.management.base import BaseCommand
from demo_app.models import Account
from demo_app.chatbot import upgrade_line


class Command(BaseCommand):
    help = 'Test the upgrade functionality that triggers the upgrade modal'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-id',
            type=int,
            help='Account ID to test with'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Test Upgrade Functionality ==='))
        
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
        
        # Test 1: Try to upgrade without specifying which line (should trigger modal)
        self.stdout.write(f'\n--- Test 1: Upgrade without line specification (should trigger modal) ---')
        result1 = upgrade_line(account.id)  # No line identifier
        self._display_result("Upgrade without line specification", result1)
        
        # Test 2: Try to upgrade with a specific line identifier
        self.stdout.write(f'\n--- Test 2: Upgrade with specific line identifier ---')
        if account.lines.exists():
            line = account.lines.first()
            result2 = upgrade_line(account.id, line.employee_name)
            self._display_result(f"Upgrade line {line.employee_name}", result2)
        else:
            self.stdout.write(self.style.WARNING('  ⚠️  No lines found in account to test with'))
        
        self.stdout.write(self.style.SUCCESS('\n=== Test Complete ==='))
    
    def _display_result(self, test_name, result):
        """Display the result of a test"""
        self.stdout.write(f'\n{test_name}:')
        
        if result['success']:
            if result.get("trigger_modal"):
                self.stdout.write(self.style.SUCCESS(f'  ✅ Success: Modal trigger detected'))
                self.stdout.write(f'  🎯 Modal type: {result["trigger_modal"]}')
                self.stdout.write(f'  📱 Account: #{result["account_number"]}')
                for line_result in result.get("results", []):
                    self.stdout.write(f'    {line_result}')
                
                if result.get("line_to_upgrade"):
                    self.stdout.write(f'  📞 Line to upgrade: {result["line_to_upgrade"]}')
                    if result.get("line_to_upgrade_data"):
                        line_data = result["line_to_upgrade_data"]
                        self.stdout.write(f'    Employee: {line_data["employee_name"]}')
                        self.stdout.write(f'    Phone: {line_data["msdn"]}')
                        self.stdout.write(f'    Device: {line_data["device_model"]}')
            else:
                self.stdout.write(self.style.SUCCESS(f'  ✅ Success: {result.get("message", "Action completed")}'))
        else:
            self.stdout.write(self.style.ERROR(f'  ❌ Failed: {result["error"]}'))



