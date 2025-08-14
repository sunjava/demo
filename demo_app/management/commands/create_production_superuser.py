from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Create a production superuser with predefined credentials'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Username for the superuser'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@tmobile.com',
            help='Email for the superuser'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='TmobileAdmin2024!',
            help='Password for the superuser'
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        # Check if user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User "{username}" already exists. Skipping creation.')
            )
            return

        # Create superuser
        try:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created superuser "{username}" with email "{email}"'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'You can now login at /admin/ with username: {username} and password: {password}'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to create superuser: {str(e)}')
            )

