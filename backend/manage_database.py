#!/usr/bin/env python3
"""
Comprehensive Database Management Script for TikTrue Backend

This script provides a unified interface for all database operations.
"""

import os
import sys
import argparse
from pathlib import Path

def setup_django():
    """Setup Django environment"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tiktrue_backend.settings')
    import django
    django.setup()

def run_environment_setup():
    """Run environment setup"""
    print("🔄 Running environment setup...")
    from setup_environment import main as env_main
    env_main()

def run_postgresql_setup():
    """Run PostgreSQL setup"""
    print("🔄 Running PostgreSQL setup...")
    from setup_postgresql import main as pg_main
    pg_main()

def run_database_setup():
    """Run database setup and migrations"""
    print("🔄 Running database setup...")
    from setup_database import main as db_main
    db_main()

def create_fresh_database():
    """Create a fresh database (WARNING: Destroys existing data)"""
    print("⚠️  WARNING: This will destroy all existing data!")
    confirm = input("Are you sure you want to continue? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("Operation cancelled")
        return
    
    setup_django()
    from django.core.management import call_command
    from django.db import connection
    
    try:
        # Drop all tables
        print("🔄 Dropping all tables...")
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
        
        print("✅ All tables dropped")
        
        # Run migrations
        print("🔄 Running fresh migrations...")
        call_command('migrate', verbosity=1)
        
        # Setup initial data
        from setup_database import setup_initial_data, create_superuser_if_needed
        create_superuser_if_needed()
        setup_initial_data()
        
        print("✅ Fresh database created successfully!")
        
    except Exception as e:
        print(f"❌ Fresh database creation failed: {e}")

def backup_database():
    """Create a database backup"""
    setup_django()
    from django.core.management import call_command
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_{timestamp}.json"
    
    try:
        print(f"🔄 Creating database backup: {backup_file}")
        call_command('dumpdata', '--natural-foreign', '--natural-primary', 
                    '--exclude=contenttypes', '--exclude=auth.permission',
                    '--output', backup_file)
        print(f"✅ Database backup created: {backup_file}")
        
    except Exception as e:
        print(f"❌ Database backup failed: {e}")

def restore_database(backup_file):
    """Restore database from backup"""
    if not Path(backup_file).exists():
        print(f"❌ Backup file not found: {backup_file}")
        return
    
    print("⚠️  WARNING: This will replace all existing data!")
    confirm = input("Are you sure you want to continue? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("Operation cancelled")
        return
    
    setup_django()
    from django.core.management import call_command
    
    try:
        print(f"🔄 Restoring database from: {backup_file}")
        call_command('loaddata', backup_file)
        print("✅ Database restored successfully!")
        
    except Exception as e:
        print(f"❌ Database restore failed: {e}")

def show_database_info():
    """Show database information"""
    setup_django()
    from django.db import connection
    from django.conf import settings
    
    print("Database Information:")
    print("=" * 40)
    
    # Database engine
    engine = settings.DATABASES['default']['ENGINE']
    print(f"Engine: {engine}")
    
    if 'sqlite' in engine:
        db_path = settings.DATABASES['default']['NAME']
        print(f"Database file: {db_path}")
        
        # Check file size
        if Path(db_path).exists():
            size = Path(db_path).stat().st_size
            print(f"File size: {size:,} bytes ({size/1024/1024:.2f} MB)")
    
    # Table count
    with connection.cursor() as cursor:
        if 'postgresql' in engine:
            cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
        else:
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        
        table_count = cursor.fetchone()[0]
        print(f"Tables: {table_count}")
    
    # User count
    try:
        from accounts.models import User
        user_count = User.objects.count()
        print(f"Users: {user_count}")
        
        from licenses.models import License
        license_count = License.objects.count()
        print(f"Licenses: {license_count}")
        
        from payments.models import Payment
        payment_count = Payment.objects.count()
        print(f"Payments: {payment_count}")
        
    except Exception as e:
        print(f"⚠️  Could not get model counts: {e}")

def main():
    """Main function with command line interface"""
    parser = argparse.ArgumentParser(description='TikTrue Database Management')
    parser.add_argument('command', choices=[
        'setup-env', 'setup-postgresql', 'setup-database', 
        'fresh-db', 'backup', 'restore', 'info', 'full-setup'
    ], help='Command to execute')
    parser.add_argument('--backup-file', help='Backup file for restore command')
    
    args = parser.parse_args()
    
    print("TikTrue Database Management")
    print("=" * 40)
    
    if args.command == 'setup-env':
        run_environment_setup()
        
    elif args.command == 'setup-postgresql':
        run_postgresql_setup()
        
    elif args.command == 'setup-database':
        run_database_setup()
        
    elif args.command == 'fresh-db':
        create_fresh_database()
        
    elif args.command == 'backup':
        backup_database()
        
    elif args.command == 'restore':
        if not args.backup_file:
            print("❌ --backup-file is required for restore command")
            sys.exit(1)
        restore_database(args.backup_file)
        
    elif args.command == 'info':
        show_database_info()
        
    elif args.command == 'full-setup':
        print("🚀 Running full database setup...")
        run_environment_setup()
        print("\n" + "="*40 + "\n")
        run_database_setup()
        print("\n✅ Full setup completed!")
        print("\nNext steps:")
        print("1. Start development server: python manage.py runserver")
        print("2. Access admin panel: http://localhost:8000/admin/")
        print("3. Test API endpoints")

if __name__ == "__main__":
    main()