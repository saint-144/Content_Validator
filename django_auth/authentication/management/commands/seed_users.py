import os
from django.core.management.base import BaseCommand
from authentication.models import User

class Command(BaseCommand):
    help = 'Seed default admin and app-level admin users'

    def handle(self, *args, **kwargs):
        # Superadmin
        admin_username = os.environ.get('ADMIN_USERNAME', 'ADMIN')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'ADMIN')
        
        if not User.objects.filter(username=admin_username).exists():
            User.objects.create_superuser(
                username=admin_username,
                password=admin_password,
                email='admin@example.com',
                role='admin',
                name='Super Admin'
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully created superuser: {admin_username}'))
        else:
            self.stdout.write(self.style.WARNING(f'Superuser {admin_username} already exists'))

        # App Admin
        app_admin_username = os.environ.get('APP_ADMIN_USERNAME', 'admin')
        app_admin_password = os.environ.get('APP_ADMIN_PASSWORD', 'admin')
        
        if not User.objects.filter(username=app_admin_username).exists():
            User.objects.create_user(
                username=app_admin_username,
                password=app_admin_password,
                role='admin',
                name='App Admin'
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully created app admin: {app_admin_username}'))
        else:
            self.stdout.write(self.style.WARNING(f'App admin {app_admin_username} already exists'))
