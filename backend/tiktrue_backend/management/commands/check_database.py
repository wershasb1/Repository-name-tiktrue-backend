"""
Django management command for database health checks
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.contrib.auth import get_user_model
from django.conf import settings
import time

class Command(BaseCommand):
    help = 'Check database health and configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed database information',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Database Health Check')
        )
        self.stdout.write('=' * 30)

        # Basic connection test
        self.check_connection()
        
        # Database info
        if options['detailed']:
            self.show_database_info()
        
        # Table checks
        self.check_tables()
        
        # User checks
        self.check_users()
        
        # Performance test
        self.performance_test()

    def check_connection(self):
        """Test basic database connection"""
        try:
            start_time = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            connection_time = (time.time() - start_time) * 1000
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Database connection: OK ({connection_time:.2f}ms)'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Database connection failed: {e}')
            )

    def show_database_info(self):
        """Show detailed database information"""
        try:
            with connection.cursor() as cursor:
                # Database version
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
                self.stdout.write(f'Database: {version.split()[0]} {version.split()[1]}')
                
                # Database name
                cursor.execute("SELECT current_database()")
                db_name = cursor.fetchone()[0]
                self.stdout.write(f'Database name: {db_name}')
                
                # Connection info
                db_settings = settings.DATABASES['default']
                self.stdout.write(f'Host: {db_settings.get("HOST", "localhost")}')
                self.stdout.write(f'Port: {db_settings.get("PORT", "5432")}')
                
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Could not get database info: {e}')
            )

    def check_tables(self):
        """Check if all expected tables exist"""
        expected_tables = [
            'django_migrations',
            'auth_user',
            'accounts_user',
            'licenses_license',
            'models_api_model'
        ]
        
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
                existing_tables = [row[0] for row in cursor.fetchall()]
            
            self.stdout.write(f'\nTables found: {len(existing_tables)}')
            
            missing_tables = []
            for table in expected_tables:
                if table in existing_tables:
                    self.stdout.write(f'✅ {table}')
                else:
                    self.stdout.write(f'❌ {table} (missing)')
                    missing_tables.append(table)
            
            if missing_tables:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n⚠️  Missing tables: {missing_tables}'
                    )
                )
                self.stdout.write('Run: python manage.py migrate')
            else:
                self.stdout.write(
                    self.style.SUCCESS('\n✅ All expected tables exist')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Table check failed: {e}')
            )

    def check_users(self):
        """Check user accounts"""
        try:
            User = get_user_model()
            
            total_users = User.objects.count()
            superusers = User.objects.filter(is_superuser=True).count()
            active_users = User.objects.filter(is_active=True).count()
            
            self.stdout.write(f'\nUser Statistics:')
            self.stdout.write(f'Total users: {total_users}')
            self.stdout.write(f'Superusers: {superusers}')
            self.stdout.write(f'Active users: {active_users}')
            
            if superusers == 0:
                self.stdout.write(
                    self.style.WARNING('⚠️  No superuser found')
                )
                self.stdout.write('Run: python manage.py createsuperuser')
            else:
                self.stdout.write('✅ Superuser exists')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ User check failed: {e}')
            )

    def performance_test(self):
        """Basic performance test"""
        try:
            self.stdout.write('\nPerformance Test:')
            
            # Simple query performance
            start_time = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM django_migrations")
                count = cursor.fetchone()[0]
            query_time = (time.time() - start_time) * 1000
            
            self.stdout.write(f'Simple query: {query_time:.2f}ms')
            self.stdout.write(f'Migrations count: {count}')
            
            # Connection pool info
            if hasattr(connection, 'queries'):
                self.stdout.write(f'Queries executed: {len(connection.queries)}')
            
            if query_time < 100:
                self.stdout.write('✅ Database performance: Good')
            elif query_time < 500:
                self.stdout.write('⚠️  Database performance: Acceptable')
            else:
                self.stdout.write('❌ Database performance: Slow')
                
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Performance test failed: {e}')
            )