from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.conf import settings
from django.db import connection


class Command(BaseCommand):
    help = 'Debug authentication issues in production'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Authentication Debug Report ==='))
        
        # Check database connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                self.stdout.write(self.style.SUCCESS('✓ Database connection: OK'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Database connection: FAILED - {e}'))
            return
        
        # Check Django settings
        self.stdout.write(f'DEBUG: {settings.DEBUG}')
        self.stdout.write(f'DATABASES: {list(settings.DATABASES.keys())}')
        self.stdout.write(f'LOGIN_URL: {getattr(settings, "LOGIN_URL", "Not set")}')
        
        # Check users
        try:
            user_count = User.objects.count()
            self.stdout.write(f'Total users in database: {user_count}')
            
            if user_count > 0:
                self.stdout.write('\nUser details:')
                for user in User.objects.all():
                    self.stdout.write(
                        f'  - {user.username}: Active={user.is_active}, '
                        f'Staff={user.is_staff}, Superuser={user.is_superuser}'
                    )
            else:
                self.stdout.write(self.style.WARNING('No users found in database!'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error checking users: {e}'))
        
        # Check authentication backend
        self.stdout.write(f'\nAuthentication backends: {settings.AUTHENTICATION_BACKENDS}')
        
        # Check middleware
        self.stdout.write(f'Middleware: {settings.MIDDLEWARE}')
        
        # Check if admin site is accessible
        try:
            from django.contrib.admin.sites import site
            admin_urls = len(site.get_urls())
            self.stdout.write(f'Admin URLs registered: {admin_urls}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Admin site error: {e}'))
        
        self.stdout.write(self.style.SUCCESS('\n=== End Debug Report ==='))

