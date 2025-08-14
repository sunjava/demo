from django.core.management.base import BaseCommand
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.middleware.csrf import CsrfViewMiddleware
from django.contrib.auth import authenticate
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Test form data handling to identify the authentication issue'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Form Data Test ==='))
        
        # Create a test user if none exists
        if not User.objects.exists():
            user = User.objects.create_user(
                username='testuser',
                password='test123'
            )
            self.stdout.write(f'Created test user: {user.username}')
        else:
            user = User.objects.first()
            self.stdout.write(f'Using existing user: {user.username}')
        
        # Test 1: Simple POST data
        self.stdout.write('\n--- Test 1: Simple POST Data ---')
        factory = RequestFactory()
        request = factory.post('/login/', {
            'username': 'testuser',
            'password': 'test123'
        })
        
        # Check what we get
        self.stdout.write(f'POST data: {request.POST}')
        self.stdout.write(f'Username from POST: "{request.POST.get("username")}"')
        self.stdout.write(f'Password from POST: "{request.POST.get("password")}"')
        
        # Test 2: With CSRF token
        self.stdout.write('\n--- Test 2: With CSRF Token ---')
        request = factory.post('/login/', {
            'username': 'testuser',
            'password': 'test123',
            'csrfmiddlewaretoken': 'test_token'
        })
        
        self.stdout.write(f'POST data with CSRF: {request.POST}')
        self.stdout.write(f'Username from POST: "{request.POST.get("username")}"')
        self.stdout.write(f'Password from POST: "{request.POST.get("password")}"')
        
        # Test 3: Test authentication
        self.stdout.write('\n--- Test 3: Authentication Test ---')
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if username and password:
            auth_result = authenticate(username=username, password=password)
            if auth_result:
                self.stdout.write(self.style.SUCCESS('✓ Authentication successful'))
            else:
                self.stdout.write(self.style.ERROR('✗ Authentication failed'))
        else:
            self.stdout.write(self.style.ERROR('✗ Username or password is empty'))
        
        # Test 4: Check request attributes
        self.stdout.write('\n--- Test 4: Request Attributes ---')
        self.stdout.write(f'Request method: {request.method}')
        self.stdout.write(f'Request content type: {request.content_type}')
        self.stdout.write(f'Request encoding: {request.encoding}')
        self.stdout.write(f'Request body: {request.body}')
        
        # Test 5: Try different field names
        self.stdout.write('\n--- Test 5: Different Field Names ---')
        test_request = factory.post('/login/', {
            'user': 'testuser',
            'pass': 'test123'
        })
        
        self.stdout.write(f'Testing with field names "user" and "pass":')
        self.stdout.write(f'  user: "{test_request.POST.get("user")}"')
        self.stdout.write(f'  pass: "{test_request.POST.get("pass")}"')
        
        self.stdout.write(self.style.SUCCESS('\n=== Form Data Test Complete ==='))
