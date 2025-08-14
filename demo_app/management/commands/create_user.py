from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Create a regular user for production'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='user',
            help='Username for the user'
        )
        parser.add_argument(
            '--email',
            type=str,
            default='user@example.com',
            help='Email for the user'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='UserPass123!',
            help='Password for the user'
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

        # Create user
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created user "{username}" with email "{email}"'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'You can now login at /login/ with username: {username} and password: {password}'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to create user: {str(e)}')
            )

