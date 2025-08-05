from django.core.management.base import BaseCommand
from django.core.management import call_command
from demo_app.models import Account, Line, Service, LineService
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Clear existing data and populate with fresh sample data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-users',
            action='store_true',
            help='Keep existing users when clearing data'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Clearing existing data...'))
        
        # Clear existing data
        LineService.objects.all().delete()
        self.stdout.write('Cleared line services')
        
        Line.objects.all().delete()
        self.stdout.write('Cleared lines')
        
        Account.objects.all().delete()
        self.stdout.write('Cleared accounts')
        
        Service.objects.all().delete()
        self.stdout.write('Cleared services')
        
        if not options['keep_users']:
            User.objects.all().delete()
            self.stdout.write('Cleared users')
        
        self.stdout.write(self.style.SUCCESS('Data cleared successfully!'))
        
        # Now populate with fresh data
        self.stdout.write(self.style.SUCCESS('Populating with fresh sample data...'))
        call_command('populate_extended_data', '--accounts', '20', '--lines-per-account', '6')
        
        self.stdout.write(self.style.SUCCESS('Fresh sample data created successfully!')) 