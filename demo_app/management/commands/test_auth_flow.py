from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.messages.middleware import MessageMiddleware
from django.middleware.common import CommonMiddleware
from django.middleware.csrf import CsrfViewMiddleware
from django.contrib.auth.context_processors import auth
from django.template.context_processors import request
from django.contrib.messages.context_processors import messages
from django.conf import settings


class Command(BaseCommand):
    help = 'Test the complete authentication flow to identify issues'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Testing Authentication Flow ==='))
        
        # Test 1: Check if users exist
        users = User.objects.all()
        self.stdout.write(f'Total users: {users.count()}')
        
        if users.count() == 0:
            self.stdout.write(self.style.ERROR('No users found! Create a user first.'))
            return
        
        # Test 2: Test authentication with first user
        test_user = users.first()
        self.stdout.write(f'Testing with user: {test_user.username}')
        
        # Test 3: Test Django authenticate function
        self.stdout.write('\n--- Testing Django authenticate() ---')
        auth_user = authenticate(username=test_user.username, password='test123')
        if auth_user:
            self.stdout.write(self.style.SUCCESS('✓ Django authenticate() works'))
        else:
            self.stdout.write(self.style.ERROR('✗ Django authenticate() failed'))
            # Try to get the actual password hash
            self.stdout.write(f'User password hash: {test_user.password[:50]}...')
            return
        
        # Test 4: Test login view logic
        self.stdout.write('\n--- Testing Login View Logic ---')
        
        # Create a mock request
        factory = RequestFactory()
        request = factory.post('/login/', {
            'username': test_user.username,
            'password': 'test123'
        })
        
        # Add middleware
        middleware = [
            SessionMiddleware(lambda r: None),
            CommonMiddleware(lambda r: None),
            CsrfViewMiddleware(lambda r: None),
            AuthenticationMiddleware(lambda r: None),
            MessageMiddleware(lambda r: None),
        ]
        
        # Apply middleware
        for m in middleware:
            request = m(request)
        
        # Test the same logic as your login view
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        self.stdout.write(f'Form data - Username: "{username}", Password: "{password}"')
        
        # Test authentication
        user = authenticate(request, username=username, password=password)
        if user is not None:
            self.stdout.write(self.style.SUCCESS('✓ Login view authentication logic works'))
        else:
            self.stdout.write(self.style.ERROR('✗ Login view authentication logic failed'))
        
        # Test 5: Check user status
        self.stdout.write('\n--- User Status Check ---')
        self.stdout.write(f'Username: {test_user.username}')
        self.stdout.write(f'Active: {test_user.is_active}')
        self.stdout.write(f'Staff: {test_user.is_staff}')
        self.stdout.write(f'Superuser: {test_user.is_superuser}')
        
        # Test 6: Check Django settings
        self.stdout.write('\n--- Django Settings Check ---')
        self.stdout.write(f'LOGIN_URL: {getattr(settings, "LOGIN_URL", "Not set")}')
        self.stdout.write(f'DEBUG: {settings.DEBUG}')
        self.stdout.write(f'SESSION_ENGINE: {getattr(settings, "SESSION_ENGINE", "Not set")}')
        
        # Test 7: Test with different password
        self.stdout.write('\n--- Testing Different Passwords ---')
        test_passwords = ['test123', 'TestPass123!', 'password', '123']
        
        for pwd in test_passwords:
            auth_result = authenticate(username=test_user.username, password=pwd)
            if auth_result:
                self.stdout.write(self.style.SUCCESS(f'✓ Password "{pwd}" works'))
            else:
                self.stdout.write(f'✗ Password "{pwd}" failed')
        
        self.stdout.write(self.style.SUCCESS('\n=== Authentication Flow Test Complete ==='))

