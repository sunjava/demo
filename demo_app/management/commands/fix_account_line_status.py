from django.core.management.base import BaseCommand
from demo_app.models import Account, Line


class Command(BaseCommand):
    help = 'Fix account and line status inconsistencies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('Checking for account-line status inconsistencies...'))
        
        # Find inactive accounts with active lines
        inactive_accounts = Account.objects.filter(status='INACTIVE')
        inconsistencies = []
        
        for account in inactive_accounts:
            active_lines = account.lines.filter(status='ACTIVE')
            suspended_lines = account.lines.filter(status='SUSPENDED')
            
            if active_lines.exists() or suspended_lines.exists():
                inconsistencies.append({
                    'account': account,
                    'active_lines': list(active_lines),
                    'suspended_lines': list(suspended_lines)
                })
        
        if not inconsistencies:
            self.stdout.write(self.style.SUCCESS('No inconsistencies found! All inactive accounts have inactive lines.'))
            return
        
        self.stdout.write(f'Found {len(inconsistencies)} inactive accounts with active/suspended lines:')
        
        total_lines_to_fix = 0
        for item in inconsistencies:
            account = item['account']
            active_lines = item['active_lines']
            suspended_lines = item['suspended_lines']
            
            self.stdout.write(f'\nAccount #{account.account_number} (ID: {account.id}):')
            self.stdout.write(f'  Status: {account.status}')
            self.stdout.write(f'  Active lines: {len(active_lines)}')
            self.stdout.write(f'  Suspended lines: {len(suspended_lines)}')
            
            for line in active_lines:
                self.stdout.write(f'    - {line.line_name} ({line.msdn}) - Status: {line.status}')
            
            for line in suspended_lines:
                self.stdout.write(f'    - {line.line_name} ({line.msdn}) - Status: {line.status}')
            
            total_lines_to_fix += len(active_lines) + len(suspended_lines)
        
        if dry_run:
            self.stdout.write(f'\n{self.style.WARNING("DRY RUN")}: Would fix {total_lines_to_fix} lines')
            self.stdout.write('Run without --dry-run to apply changes')
        else:
            # Apply fixes
            self.stdout.write(f'\nFixing {total_lines_to_fix} lines...')
            
            for item in inconsistencies:
                account = item['account']
                active_lines = item['active_lines']
                suspended_lines = item['suspended_lines']
                
                # Update all active and suspended lines to inactive
                lines_to_update = account.lines.filter(status__in=['ACTIVE', 'SUSPENDED'])
                updated_count = lines_to_update.update(status='INACTIVE')
                
                self.stdout.write(f'  Account #{account.account_number}: Updated {updated_count} lines to INACTIVE')
            
            self.stdout.write(self.style.SUCCESS(f'\nSuccessfully fixed {total_lines_to_fix} lines!'))
            
            # Verify the fix
            self.stdout.write('\nVerifying fix...')
            remaining_inconsistencies = []
            
            for account in Account.objects.filter(status='INACTIVE'):
                non_inactive_lines = account.lines.exclude(status='INACTIVE')
                if non_inactive_lines.exists():
                    remaining_inconsistencies.append(account)
            
            if not remaining_inconsistencies:
                self.stdout.write(self.style.SUCCESS('✓ All inconsistencies have been resolved!'))
            else:
                self.stdout.write(self.style.ERROR(f'✗ {len(remaining_inconsistencies)} accounts still have inconsistencies')) 