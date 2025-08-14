from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.contrib.auth import authenticate


class Command(BaseCommand):
    help = 'Simple authentication test to isolate the issue'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Simple Authentication Test ==='))
        
        # Get all users
        users = User.objects.all()
        if users.count() == 0:
            self.stdout.write(self.style.ERROR('No users found!'))
            return
        
        # Test with first user
        user = users.first()
        self.stdout.write(f'Testing user: {user.username}')
        
        # Test different passwords
        test_passwords = [
            'test123',
            'TestPass123!', 
            'password',
            '123',
            'admin',
            'AdminPass123!'
        ]
        
        working_passwords = []
        
        for password in test_passwords:
            self.stdout.write(f'Testing password: "{password}"')
            auth_result = authenticate(username=user.username, password=password)
            if auth_result:
                self.stdout.write(self.style.SUCCESS(f'  ✓ SUCCESS with password: "{password}"'))
                working_passwords.append(password)
            else:
                self.stdout.write(f'  ✗ FAILED with password: "{password}"')
        
        # Summary
        if working_passwords:
            self.stdout.write(self.style.SUCCESS(f'\nWorking passwords for {user.username}:'))
            for pwd in working_passwords:
                self.stdout.write(f'  - "{pwd}"')
            
            self.stdout.write(self.style.SUCCESS('\nTry logging in with one of these passwords!'))
        else:
            self.stdout.write(self.style.ERROR('\nNo passwords worked! There might be a user account issue.'))
            
            # Check user status
            self.stdout.write(f'\nUser status:')
            self.stdout.write(f'  Active: {user.is_active}')
            self.stdout.write(f'  Staff: {user.is_staff}')
            self.stdout.write(f'  Superuser: {user.is_superuser}')
            self.stdout.write(f'  Password hash: {user.password[:50]}...')

