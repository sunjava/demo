from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date, timedelta
from demo_app.models import Account, Line, Service, LineService


class Command(BaseCommand):
    help = 'Populate the database with sample data for testing'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creating sample data...'))
        
        # Create a test user
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={
                'email': 'test@example.com',
                'first_name': 'Test',
                'last_name': 'User'
            }
        )
        if created:
            user.set_password('testpass123')
            user.save()
            self.stdout.write(f'Created user: {user.username}')
        else:
            self.stdout.write(f'User already exists: {user.username}')

        # Create a sample account
        account, created = Account.objects.get_or_create(
            account_number='12345678',
            defaults={
                'user': user,
                'status': 'ACTIVE',
                'account_type': 'STANDARD',
                'last_payment_date': date.today() - timedelta(days=30),
                'payment_due_date': date.today() + timedelta(days=20)
            }
        )
        if created:
            self.stdout.write(f'Created account: {account.account_number}')
        else:
            self.stdout.write(f'Account already exists: {account.account_number}')

        # Create sample services
        services_data = [
            {
                'name': '1 Day International Pass',
                'service_type': 'INTERNATIONAL_PASS',
                'description': 'Perfect for short trips. 24-hour high-speed data with unlimited calling and texting.',
                'price': Decimal('1.00'),
                'duration_days': 1,
                'data_allowance_mb': 512,
                'features': [
                    'Valid for 24 hours from activation',
                    '512MB high-speed data allowance',
                    'Unlimited texting to 210+ countries',
                    'Unlimited calling to 210+ countries',
                    'Works in 210+ countries and destinations',
                    'No overage charges - data stops when limit reached'
                ]
            },
            {
                'name': '10 Day International Pass',
                'service_type': 'INTERNATIONAL_PASS',
                'description': 'Great for business trips and week-long vacations. 10 days of high-speed data with unlimited calling and texting.',
                'price': Decimal('35.00'),
                'duration_days': 10,
                'data_allowance_mb': 5120,  # 5GB
                'features': [
                    'Valid for 10 consecutive days from activation',
                    '5GB high-speed data allowance',
                    'Unlimited texting to 210+ countries',
                    'Unlimited calling to 210+ countries',
                    'Works in 210+ countries and destinations',
                    'No overage charges - data stops when limit reached',
                    'Ideal for week-long business trips or vacations'
                ]
            },
            {
                'name': '30 Day International Pass',
                'service_type': 'INTERNATIONAL_PASS',
                'description': 'Best value for extended travel. 30 days of high-speed data with unlimited calling and texting.',
                'price': Decimal('50.00'),
                'duration_days': 30,
                'data_allowance_mb': 15360,  # 15GB
                'features': [
                    'Valid for 30 consecutive days from activation',
                    '15GB high-speed data allowance',
                    'Unlimited texting to 210+ countries',
                    'Unlimited calling to 210+ countries',
                    'Works in 210+ countries and destinations',
                    'No overage charges - data stops when limit reached',
                    'Perfect for extended international travel',
                    'Best value for frequent international travelers'
                ]
            }
        ]

        for service_data in services_data:
            service, created = Service.objects.get_or_create(
                name=service_data['name'],
                defaults=service_data
            )
            if created:
                self.stdout.write(f'Created service: {service.name}')
            else:
                self.stdout.write(f'Service already exists: {service.name}')

        # Create sample lines
        lines_data = [
            {'line_name': 'Line 1', 'msdn': '+1-555-0123', 'employee_name': 'John Smith', 'employee_number': 'EMP001'},
            {'line_name': 'Line 2', 'msdn': '+1-555-0124', 'employee_name': 'Sarah Johnson', 'employee_number': 'EMP002'},
            {'line_name': 'Line 3', 'msdn': '+1-555-0125', 'employee_name': 'Michael Brown', 'employee_number': 'EMP003'},
            {'line_name': 'Line 4', 'msdn': '+1-555-0126', 'employee_name': 'Emily Davis', 'employee_number': 'EMP004'},
            {'line_name': 'Line 5', 'msdn': '+1-555-0127', 'employee_name': 'David Wilson', 'employee_number': 'EMP005'},
            {'line_name': 'Line 6', 'msdn': '+1-555-0128', 'employee_name': 'Lisa Anderson', 'employee_number': 'EMP006'},
            {'line_name': 'Line 7', 'msdn': '+1-555-0129', 'employee_name': 'Robert Taylor', 'employee_number': 'EMP007'},
            {'line_name': 'Line 8', 'msdn': '+1-555-0130', 'employee_name': 'Jennifer Martinez', 'employee_number': 'EMP008'},
            {'line_name': 'Line 9', 'msdn': '+1-555-0131', 'employee_name': 'Christopher Lee', 'employee_number': 'EMP009'},
            {'line_name': 'Line 10', 'msdn': '+1-555-0132', 'employee_name': 'Amanda Garcia', 'employee_number': 'EMP010'},
        ]

        for i, line_data in enumerate(lines_data):
            line_data['account'] = account
            line_data['status'] = 'ACTIVE'
            line_data['payment_due_date'] = date.today() + timedelta(days=15 + i)
            
            line, created = Line.objects.get_or_create(
                msdn=line_data['msdn'],
                defaults=line_data
            )
            if created:
                self.stdout.write(f'Created line: {line.line_name} - {line.msdn}')
            else:
                self.stdout.write(f'Line already exists: {line.line_name} - {line.msdn}')

        self.stdout.write(self.style.SUCCESS('\nSample data creation completed!'))
        self.stdout.write(self.style.SUCCESS('\nTo test the application:'))
        self.stdout.write(self.style.SUCCESS('1. Run migrations: python manage.py migrate'))
        self.stdout.write(self.style.SUCCESS('2. Start the server: python manage.py runserver'))
        self.stdout.write(self.style.SUCCESS('3. Visit: http://localhost:8000/accounts/1/'))
        self.stdout.write(self.style.SUCCESS(f'4. Login with username: {user.username}, password: testpass123'))