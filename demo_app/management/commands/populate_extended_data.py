from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date, timedelta
import random
from demo_app.models import Account, Line, Service, LineService


class Command(BaseCommand):
    help = 'Populate the database with extensive sample data including multiple accounts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--accounts',
            type=int,
            default=10,
            help='Number of accounts to create (default: 10)'
        )
        parser.add_argument(
            '--lines-per-account',
            type=int,
            default=5,
            help='Number of lines per account (default: 5)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creating extensive sample data...'))
        
        num_accounts = options['accounts']
        lines_per_account = options['lines_per_account']
        
        # Create multiple users
        users_data = [
            {'username': 'admin_user', 'email': 'admin@tmobile.com', 'first_name': 'Admin', 'last_name': 'User'},
            {'username': 'manager1', 'email': 'manager1@tmobile.com', 'first_name': 'Sarah', 'last_name': 'Manager'},
            {'username': 'manager2', 'email': 'manager2@tmobile.com', 'first_name': 'Mike', 'last_name': 'Johnson'},
            {'username': 'agent1', 'email': 'agent1@tmobile.com', 'first_name': 'Lisa', 'last_name': 'Anderson'},
            {'username': 'agent2', 'email': 'agent2@tmobile.com', 'first_name': 'David', 'last_name': 'Wilson'},
        ]
        
        users = []
        for user_data in users_data:
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults=user_data
            )
            if created:
                user.set_password('password123')
                user.save()
                self.stdout.write(f'Created user: {user.username}')
            else:
                self.stdout.write(f'User already exists: {user.username}')
            users.append(user)

        # Create sample services (if they don't exist)
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
                'data_allowance_mb': 5120,
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
                'data_allowance_mb': 15360,
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
            },
            {
                'name': 'Data Add-on 2GB',
                'service_type': 'DATA_ADDON',
                'description': 'Additional 2GB of high-speed data for your current billing cycle.',
                'price': Decimal('10.00'),
                'duration_days': 30,
                'data_allowance_mb': 2048,
                'features': [
                    '2GB additional high-speed data',
                    'Valid for current billing cycle',
                    'No overage charges',
                    'Works on all T-Mobile plans'
                ]
            },
            {
                'name': 'Unlimited Calling Add-on',
                'service_type': 'CALLING_ADDON',
                'description': 'Unlimited calling to any number in the US and Canada.',
                'price': Decimal('15.00'),
                'duration_days': 30,
                'data_allowance_mb': None,
                'features': [
                    'Unlimited calling to US and Canada',
                    'Valid for current billing cycle',
                    'No long distance charges',
                    'Works on all T-Mobile plans'
                ]
            }
        ]

        services = []
        for service_data in services_data:
            service, created = Service.objects.get_or_create(
                name=service_data['name'],
                defaults=service_data
            )
            if created:
                self.stdout.write(f'Created service: {service.name}')
            else:
                self.stdout.write(f'Service already exists: {service.name}')
            services.append(service)

        # Sample employee names for variety
        employee_names = [
            'John Smith', 'Sarah Johnson', 'Michael Brown', 'Emily Davis', 'David Wilson',
            'Lisa Anderson', 'Robert Taylor', 'Jennifer Martinez', 'Christopher Lee', 'Amanda Garcia',
            'James Rodriguez', 'Michelle White', 'Daniel Thompson', 'Jessica Moore', 'Kevin Jackson',
            'Ashley Martin', 'Steven Lee', 'Nicole Garcia', 'Brian Hall', 'Rachel Young',
            'Jason Allen', 'Stephanie King', 'Ryan Wright', 'Lauren Lopez', 'Eric Hill',
            'Amber Scott', 'Timothy Green', 'Megan Baker', 'Jonathan Adams', 'Samantha Nelson'
        ]

        # Create multiple accounts
        accounts_created = 0
        for i in range(num_accounts):
            # Generate account number
            account_number = f"{random.randint(10000000, 99999999)}"
            
            # Random account type and status
            account_type = random.choice(['STANDARD', 'PREMIUM', 'BUSINESS'])
            status = random.choice(['ACTIVE', 'ACTIVE', 'ACTIVE', 'ACTIVE', 'INACTIVE'])  # Mostly active
            
            # Random user assignment
            user = random.choice(users)
            
            # Random dates
            days_ago = random.randint(1, 365)
            created_date = date.today() - timedelta(days=days_ago)
            last_payment = created_date + timedelta(days=random.randint(30, 90))
            payment_due = last_payment + timedelta(days=random.randint(15, 45))
            
            account, created = Account.objects.get_or_create(
                account_number=account_number,
                defaults={
                    'user': user,
                    'status': status,
                    'account_type': account_type,
                    'created_on': created_date,
                    'last_payment_date': last_payment,
                    'payment_due_date': payment_due
                }
            )
            
            if created:
                self.stdout.write(f'Created account: {account.account_number} ({account.account_type})')
                accounts_created += 1
                
                # Create lines for this account
                num_lines = random.randint(1, lines_per_account)
                for j in range(num_lines):
                    # Generate unique MSDN
                    area_code = random.choice(['555', '444', '333', '222'])
                    phone_number = f"{random.randint(1000000, 9999999)}"
                    msdn = f"+1-{area_code}-{phone_number[:3]}-{phone_number[3:]}"
                    
                    # Line status should be consistent with account status
                    if account.status == 'INACTIVE':
                        line_status = 'INACTIVE'  # All lines must be inactive if account is inactive
                    else:  # ACTIVE account
                        line_status = random.choice(['ACTIVE', 'ACTIVE', 'ACTIVE', 'SUSPENDED', 'INACTIVE'])  # Mostly active
                    
                    # Random employee
                    employee_name = random.choice(employee_names)
                    employee_number = f"EMP{random.randint(1000, 9999)}"
                    
                    # Random payment due date
                    line_payment_due = date.today() + timedelta(days=random.randint(1, 30))
                    
                    line, line_created = Line.objects.get_or_create(
                        msdn=msdn,
                        defaults={
                            'account': account,
                            'line_name': f'Line {j + 1}',
                            'employee_name': employee_name,
                            'employee_number': employee_number,
                            'status': line_status,
                            'payment_due_date': line_payment_due
                        }
                    )
                    
                    if line_created:
                        self.stdout.write(f'  Created line: {line.line_name} - {line.msdn} ({line.status})')
                        
                        # Randomly add some services to lines
                        if random.random() < 0.3:  # 30% chance to add a service
                            service = random.choice(services)
                            if service.service_type == 'INTERNATIONAL_PASS':
                                # International passes are usually short-term
                                duration = random.choice([1, 10, 30])
                                service = next(s for s in services if s.duration_days == duration)
                            
                            # Calculate expiration
                            expires_at = date.today() + timedelta(days=service.duration_days)
                            
                            line_service = LineService.objects.create(
                                line=line,
                                service=service,
                                status='ACTIVE',
                                activated_at=date.today(),
                                expires_at=expires_at,
                                amount_paid=service.price,
                                tax_amount=service.price * Decimal('0.08'),
                                total_amount=service.price * Decimal('1.08'),
                                payment_method='Credit Card',
                                transaction_id=f"TXN{random.randint(100000, 999999)}"
                            )
                            self.stdout.write(f'    Added service: {service.name}')

        self.stdout.write(self.style.SUCCESS(f'\nExtended sample data creation completed!'))
        self.stdout.write(self.style.SUCCESS(f'Created {accounts_created} new accounts'))
        self.stdout.write(self.style.SUCCESS(f'Total accounts in database: {Account.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Total lines in database: {Line.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Total services in database: {Service.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Total line services in database: {LineService.objects.count()}'))
        
        # Show some statistics
        active_accounts = Account.objects.filter(status='ACTIVE').count()
        active_lines = Line.objects.filter(status='ACTIVE').count()
        suspended_lines = Line.objects.filter(status='SUSPENDED').count()
        inactive_lines = Line.objects.filter(status='INACTIVE').count()
        
        self.stdout.write(self.style.SUCCESS(f'\nStatistics:'))
        self.stdout.write(self.style.SUCCESS(f'  Active accounts: {active_accounts}'))
        self.stdout.write(self.style.SUCCESS(f'  Active lines: {active_lines}'))
        self.stdout.write(self.style.SUCCESS(f'  Suspended lines: {suspended_lines}'))
        self.stdout.write(self.style.SUCCESS(f'  Inactive lines: {inactive_lines}'))
        
        self.stdout.write(self.style.SUCCESS('\nTo test the application:'))
        self.stdout.write(self.style.SUCCESS('1. Start the server: python manage.py runserver'))
        self.stdout.write(self.style.SUCCESS('2. Visit: http://localhost:8000/'))
        self.stdout.write(self.style.SUCCESS('3. Login with any of the created users (password: password123)')) 