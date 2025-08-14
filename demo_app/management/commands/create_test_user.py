from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Create a test user with known credentials for authentication testing'

    def handle(self, *args, **options):
        username = 'testuser'
        password = 'TestPass123!'
        email = 'test@tmobile.com'
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User "{username}" already exists. Updating password...')
            )
            user = User.objects.get(username=username)
            user.set_password(password)
            user.is_active = True
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f'Password updated for existing user "{username}"')
            )
        else:
            # Create new user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            user.is_active = True
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f'Created new test user "{username}"')
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nTest User Credentials:\n'
                f'Username: {username}\n'
                f'Password: {password}\n'
                f'Email: {email}\n\n'
                f'You can now login at /login/ with these credentials.'
            )
        )

