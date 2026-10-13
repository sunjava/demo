from django.core.management.base import BaseCommand

from demo_app.sap import generate_sap_orders


class Command(BaseCommand):
    help = 'Generate mock SAP sales orders and deliveries for existing lines'

    def add_arguments(self, parser):
        parser.add_argument(
            '--recreate',
            action='store_true',
            help='Delete existing mock SAP orders and regenerate',
        )

    def handle(self, *args, **options):
        result = generate_sap_orders(recreate=options.get('recreate', False))
        self.stdout.write(self.style.SUCCESS(
            f"Created {result['created']} SAP order(s) "
            f"({result['skipped']} already existed) "
            f"for {result['lines']} line(s)."
        ))
