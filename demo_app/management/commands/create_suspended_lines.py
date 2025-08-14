from django.core.management.base import BaseCommand
from demo_app.models import Account, Line


class Command(BaseCommand):
    help = 'Create suspended lines for testing chatbot restore functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-id',
            type=int,
            default=1,
            help='Account ID to create suspended lines in (default: 1)'
        )
        parser.add_argument(
            '--count',
            type=int,
            default=3,
            help='Number of lines to suspend (default: 3)'
        )

    def handle(self, *args, **options):
        account_id = options['account_id']
        count = options['count']
        
        try:
            account = Account.objects.get(id=account_id)
            self.stdout.write(f'Found account: {account.account_number}')
            
            # Get active lines to suspend
            active_lines = account.lines.filter(status='ACTIVE')[:count]
            
            if not active_lines.exists():
                self.stdout.write(self.style.ERROR('No active lines found to suspend'))
                return
            
            suspended_count = 0
            for line in active_lines:
                line.status = 'SUSPENDED'
                line.save()
                suspended_count += 1
                self.stdout.write(f'Suspended line: {line.line_name} ({line.msdn}) - {line.employee_name}')
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully suspended {suspended_count} lines in account {account.account_number}'
                )
            )
            
            # Show current line status breakdown
            total_lines = account.lines.count()
            active_lines = account.lines.filter(status='ACTIVE').count()
            suspended_lines = account.lines.filter(status='SUSPENDED').count()
            cancelled_lines = account.lines.filter(status='CANCELLED').count()
            
            self.stdout.write('\nCurrent line status breakdown:')
            self.stdout.write(f'  Total lines: {total_lines}')
            self.stdout.write(f'  Active lines: {active_lines}')
            self.stdout.write(f'  Suspended lines: {suspended_lines}')
            self.stdout.write(f'  Cancelled lines: {cancelled_lines}')
            
            # Show suspended line details
            if suspended_lines > 0:
                self.stdout.write('\nSuspended lines:')
                for line in account.lines.filter(status='SUSPENDED'):
                    self.stdout.write(f'  • {line.line_name} ({line.msdn}) - {line.employee_name}')
            
        except Account.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Account with ID {account_id} not found')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {str(e)}')
            )
