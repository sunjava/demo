from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Check middleware configuration for potential authentication issues'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Middleware Configuration Check ==='))
        
        middleware = getattr(settings, 'MIDDLEWARE', [])
        
        self.stdout.write(f'Total middleware: {len(middleware)}')
        
        for i, m in enumerate(middleware):
            self.stdout.write(f'{i+1}. {m}')
        
        # Check for problematic middleware
        self.stdout.write('\n--- Potential Issues ---')
        
        # Check for security middleware that might interfere
        security_middleware = [
            'django.middleware.security.SecurityMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.middleware.clickjacking.XFrameOptionsMiddleware',
        ]
        
        for m in security_middleware:
            if m in middleware:
                self.stdout.write(f'✓ {m} - Present')
            else:
                self.stdout.write(f'✗ {m} - Missing')
        
        # Check for authentication middleware
        auth_middleware = [
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.contrib.sessions.middleware.SessionMiddleware',
        ]
        
        for m in auth_middleware:
            if m in middleware:
                self.stdout.write(f'✓ {m} - Present')
            else:
                self.stdout.write(f'✗ {m} - Missing')
        
        # Check Django settings
        self.stdout.write('\n--- Django Settings ---')
        self.stdout.write(f'DEBUG: {settings.DEBUG}')
        self.stdout.write(f'CSRF_COOKIE_SECURE: {getattr(settings, "CSRF_COOKIE_SECURE", "Not set")}')
        self.stdout.write(f'SESSION_COOKIE_SECURE: {getattr(settings, "SESSION_COOKIE_SECURE", "Not set")}')
        self.stdout.write(f'CSRF_TRUSTED_ORIGINS: {getattr(settings, "CSRF_TRUSTED_ORIGINS", "Not set")}')
        
        self.stdout.write(self.style.SUCCESS('\n=== Middleware Check Complete ==='))





