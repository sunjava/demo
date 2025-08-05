from django.core.management.base import BaseCommand
from demo_app.models import Account


class Command(BaseCommand):
    help = 'Migrate accounts with SUSPENDED status to ACTIVE or INACTIVE'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to-active',
            action='store_true',
            help='Convert suspended accounts to ACTIVE instead of INACTIVE'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        to_active = options['to_active']
        
        # Find accounts with SUSPENDED status
        suspended_accounts = Account.objects.filter(status='SUSPENDED')
        
        if not suspended_accounts.exists():
            self.stdout.write(self.style.SUCCESS('No accounts with SUSPENDED status found.'))
            return
        
        new_status = 'ACTIVE' if to_active else 'INACTIVE'
        
        self.stdout.write(f'Found {suspended_accounts.count()} accounts with SUSPENDED status.')
        self.stdout.write(f'Will convert them to {new_status} status.')
        
        if dry_run:
            self.stdout.write('\nAccounts that would be updated:')
            for account in suspended_accounts:
                self.stdout.write(f'  Account #{account.account_number} (ID: {account.id})')
            self.stdout.write(f'\n{self.style.WARNING("DRY RUN")}: Would update {suspended_accounts.count()} accounts to {new_status}')
            self.stdout.write('Run without --dry-run to apply changes')
        else:
            # Update the accounts
            updated_count = suspended_accounts.update(status=new_status)
            self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated_count} accounts to {new_status} status.'))
            
            # Verify the update
            remaining_suspended = Account.objects.filter(status='SUSPENDED').count()
            if remaining_suspended == 0:
                self.stdout.write(self.style.SUCCESS('✓ All SUSPENDED accounts have been migrated!'))
            else:
                self.stdout.write(self.style.ERROR(f'✗ {remaining_suspended} accounts still have SUSPENDED status')) 