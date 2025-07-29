"""
Django management command for production setup
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
from django.contrib.auth import get_user_model
import os

class Command(BaseCommand):
    help = 'Setup production environment with database migrations and initial data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-superuser',
            action='store_true',
            help='Skip superuser creation',
        )
        parser.add_argument(
            '--skip-static',
            action='store_true',
            help='Skip static files collection',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting production setup...')
        )

        # 1. Run migrations
        self.stdout.write('Running database migrations...')
        try:
            call_command('migrate', verbosity=1)
            self.stdout.write(
                self.style.SUCCESS('✅ Migrations completed successfully')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Migration failed: {e}')
            )
            return

        # 2. Collect static files
        if not options['skip_static']:
            self.stdout.write('Collecting static files...')
            try:
                call_command('collectstatic', '--noinput', verbosity=1)
                self.stdout.write(
                    self.style.SUCCESS('✅ Static files collected')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Static files collection failed: {e}')
                )

        # 3. Create superuser if needed
        if not options['skip_superuser']:
            self.create_superuser_if_needed()

        # 4. Validate setup
        self.validate_setup()

        self.stdout.write(
            self.style.SUCCESS('\n✅ Production setup completed!')
        )

    def create_superuser_if_needed(self):
        """Create superuser if none exists"""
        User = get_user_model()
        
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write('✅ Superuser already exists')
            return

        self.stdout.write('Creating superuser...')
        
        # Get credentials from environment or prompt
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if username and email and password:
            try:
                User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password
                )
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Superuser "{username}" created')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Superuser creation failed: {e}')
                )
        else:
            self.stdout.write(
                self.style.WARNING(
                    '⚠️  Superuser environment variables not set. '
                    'Set DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, '
                    'and DJANGO_SUPERUSER_PASSWORD to create automatically.'
                )
            )

    def validate_setup(self):
        """Validate the setup"""
        self.stdout.write('Validating setup...')
        
        # Check database connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            self.stdout.write('✅ Database connection working')
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Database connection failed: {e}')
            )
            return

        # Check if key tables exist
        expected_tables = ['accounts_user', 'licenses_license']
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = ANY(%s)
            """, [expected_tables])
            existing_tables = [row[0] for row in cursor.fetchall()]

        missing_tables = set(expected_tables) - set(existing_tables)
        if missing_tables:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Missing tables: {missing_tables}')
            )
        else:
            self.stdout.write('✅ All expected tables exist')

        self.stdout.write('✅ Setup validation completed')