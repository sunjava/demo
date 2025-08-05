from django.core.management.base import BaseCommand
from demo_app.models import Line
from datetime import date


class Command(BaseCommand):
    help = 'Update payment due date for a specific line'

    def add_arguments(self, parser):
        parser.add_argument('employee_name', type=str, help='Employee name to search for')
        parser.add_argument('payment_date', type=str, help='Payment due date in YYYY-MM-DD format')

    def handle(self, *args, **options):
        employee_name = options['employee_name']
        payment_date_str = options['payment_date']
        
        try:
            # Parse the date
            payment_date = date.fromisoformat(payment_date_str)
        except ValueError:
            self.stdout.write(
                self.style.ERROR(f'Invalid date format: {payment_date_str}. Use YYYY-MM-DD format.')
            )
            return
        
        # Find lines for the employee
        lines = Line.objects.filter(employee_name__icontains=employee_name)
        
        if not lines.exists():
            self.stdout.write(
                self.style.ERROR(f'No lines found for employee: {employee_name}')
            )
            return
        
        self.stdout.write(f'Found {lines.count()} line(s) for employee: {employee_name}')
        
        for line in lines:
            old_date = line.payment_due_date
            line.payment_due_date = payment_date
            line.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Updated line {line.line_name} (MSDN: {line.msdn}) - '
                    f'Payment due date changed from {old_date} to {payment_date}'
                )
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated payment due date for {lines.count()} line(s)')
        )