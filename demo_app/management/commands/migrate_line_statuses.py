from django.core.management.base import BaseCommand
from demo_app.models import Line


class Command(BaseCommand):
    help = 'Migrate line statuses from INACTIVE to CANCELLED'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting line status migration...'))
        
        # Count lines with INACTIVE status
        inactive_lines = Line.objects.filter(status='INACTIVE')
        inactive_count = inactive_lines.count()
        
        if inactive_count > 0:
            self.stdout.write(f'Found {inactive_count} lines with INACTIVE status')
            
            # Update all lines with INACTIVE status to CANCELLED
            updated_count = inactive_lines.update(status='CANCELLED')
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully migrated {updated_count} lines from INACTIVE to CANCELLED')
            )
        else:
            self.stdout.write('No lines with INACTIVE status found')
        
        # Show current status counts
        active_count = Line.objects.filter(status='ACTIVE').count()
        suspended_count = Line.objects.filter(status='SUSPENDED').count()
        cancelled_count = Line.objects.filter(status='CANCELLED').count()
        total_count = Line.objects.count()
        
        self.stdout.write('\nCurrent line status counts:')
        self.stdout.write(f'  Active: {active_count}')
        self.stdout.write(f'  Suspended: {suspended_count}')
        self.stdout.write(f'  Cancelled: {cancelled_count}')
        self.stdout.write(f'  Total: {total_count}')
        
        self.stdout.write(self.style.SUCCESS('\nMigration completed!')) 