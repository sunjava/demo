from django.core.management.base import BaseCommand
from demo_app.models import Line


class Command(BaseCommand):
    help = 'Populate existing lines with default device, plan, and protection information'

    def handle(self, *args, **options):
        lines = Line.objects.all()
        updated_count = 0
        
        for line in lines:
            # Only update lines that don't have device information
            if not line.device_model:
                line.device_model = 'iPhone 15 Pro'
                line.device_color = 'Natural Titanium'
                line.device_storage = '256GB'
                line.device_price = 999.00
                
                line.plan_name = 'T-Mobile Magenta MAX'
                line.plan_price = 85.00
                line.plan_data_limit = 'Unlimited'
                
                line.protection_name = 'Premium Device Protection'
                line.protection_price = 18.00
                
                line.trade_in_value = 0.00
                line.total_monthly_cost = 103.00  # plan + protection
                
                line.save()
                updated_count += 1
                self.stdout.write(f'Updated line {line.line_name} ({line.employee_name})')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {updated_count} lines with device, plan, and protection information')
        ) 