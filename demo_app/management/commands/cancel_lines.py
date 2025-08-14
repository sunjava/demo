from django.core.management.base import BaseCommand
from demo_app.models import Account, Line
from django.utils import timezone


class Command(BaseCommand):
    help = 'Cancel lines for testing reactivation functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-id',
            type=int,
            required=True,
            help='Account ID to cancel lines in'
        )
        parser.add_argument(
            '--line-identifier',
            type=str,
            help='Line identifier to cancel (if not provided, cancels all active lines)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force cancellation even if line is not active'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Cancel Lines Test ==='))
        
        account_id = options['account_id']
        
        try:
            account = Account.objects.get(id=account_id)
        except Account.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Account {account_id} not found'))
            return
        
        self.stdout.write(f'Cancelling lines in account: {account.account_number} (ID: {account.id})')
        
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
        
        # Determine which lines to cancel
        if options['line_identifier']:
            # Cancel specific line
            identifier = options['line_identifier']
            self.stdout.write(f'\n--- Cancelling line: "{identifier}" ---')
            
            # Find the line
            lines_to_cancel = []
            for line in all_lines:
                if (identifier.lower() in line.line_name.lower() or
                    identifier.lower() in line.msdn.lower() or
                    identifier.lower() in line.employee_name.lower() or
                    identifier.lower() in line.employee_number.lower()):
                    lines_to_cancel.append(line)
            
            if not lines_to_cancel:
                self.stdout.write(self.style.ERROR(f'No lines found matching "{identifier}"'))
                return
        else:
            # Cancel all active lines
            if options['force']:
                lines_to_cancel = list(all_lines)
                self.stdout.write(f'\n--- Force cancelling all lines ({len(lines_to_cancel)}) ---')
            else:
                lines_to_cancel = list(all_lines.filter(status='ACTIVE'))
                self.stdout.write(f'\n--- Cancelling all active lines ({len(lines_to_cancel)}) ---')
        
        if not lines_to_cancel:
            self.stdout.write(self.style.WARNING('No lines to cancel'))
            return
        
        # Cancel the lines
        cancelled_count = 0
        for line in lines_to_cancel:
            try:
                old_status = line.status
                line.status = 'CANCELLED'
                line.cancelled_on = timezone.now()
                line.save()
                
                self.stdout.write(f'✅ {line.line_name} ({line.msdn}): Cancelled (was {old_status})')
                cancelled_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'❌ {line.line_name} ({line.msdn}): Failed to cancel - {str(e)}'))
        
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
        
        self.stdout.write(self.style.SUCCESS(f'\n=== Successfully cancelled {cancelled_count} lines ==='))



