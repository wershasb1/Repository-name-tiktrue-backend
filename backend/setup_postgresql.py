#!/usr/bin/env python3
"""
PostgreSQL Database Setup Script for TikTrue Backend

This script handles PostgreSQL-specific database setup for production environments.
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import subprocess

def get_db_config():
    """Get database configuration from environment variables"""
    return {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'port': os.environ.get('DB_PORT', '5432'),
        'database': os.environ.get('DB_NAME', 'tiktrue_db'),
        'user': os.environ.get('DB_USER', 'tiktrue_user'),
        'password': os.environ.get('DB_PASSWORD', 'tiktrue_password'),
        'admin_user': os.environ.get('DB_ADMIN_USER', 'postgres'),
        'admin_password': os.environ.get('DB_ADMIN_PASSWORD', ''),
    }

def create_database_and_user():
    """Create PostgreSQL database and user if they don't exist"""
    config = get_db_config()
    
    try:
        print("🔄 Connecting to PostgreSQL as admin...")
        
        # Connect as admin user
        admin_conn = psycopg2.connect(
            host=config['host'],
            port=config['port'],
            database='postgres',  # Connect to default database
            user=config['admin_user'],
            password=config['admin_password']
        )
        admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        admin_cursor = admin_conn.cursor()
        
        # Check if user exists
        admin_cursor.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s",
            (config['user'],)
        )
        user_exists = admin_cursor.fetchone()
        
        if not user_exists:
            print(f"🔄 Creating database user: {config['user']}")
            admin_cursor.execute(
                f"CREATE USER {config['user']} WITH PASSWORD %s",
                (config['password'],)
            )
            print(f"✅ Database user created: {config['user']}")
        else:
            print(f"⚪ Database user already exists: {config['user']}")
        
        # Check if database exists
        admin_cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (config['database'],)
        )
        db_exists = admin_cursor.fetchone()
        
        if not db_exists:
            print(f"🔄 Creating database: {config['database']}")
            admin_cursor.execute(f"CREATE DATABASE {config['database']} OWNER {config['user']}")
            print(f"✅ Database created: {config['database']}")
        else:
            print(f"⚪ Database already exists: {config['database']}")
        
        # Grant privileges
        admin_cursor.execute(f"GRANT ALL PRIVILEGES ON DATABASE {config['database']} TO {config['user']}")
        admin_cursor.execute(f"ALTER USER {config['user']} CREATEDB")
        
        admin_cursor.close()
        admin_conn.close()
        
        print("✅ PostgreSQL database and user setup completed")
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL setup failed: {e}")
        return False

def test_database_connection():
    """Test connection to the application database"""
    config = get_db_config()
    
    try:
        print("🔄 Testing database connection...")
        
        conn = psycopg2.connect(
            host=config['host'],
            port=config['port'],
            database=config['database'],
            user=config['user'],
            password=config['password']
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        print(f"✅ Connected to PostgreSQL: {version}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        return False

def setup_database_extensions():
    """Setup required PostgreSQL extensions"""
    config = get_db_config()
    
    try:
        print("🔄 Setting up database extensions...")
        
        conn = psycopg2.connect(
            host=config['host'],
            port=config['port'],
            database=config['database'],
            user=config['user'],
            password=config['password']
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Extensions that might be useful
        extensions = [
            'uuid-ossp',  # For UUID generation
            'pg_trgm',    # For text search
            'btree_gin',  # For JSON indexing
        ]
        
        for extension in extensions:
            try:
                cursor.execute(f"CREATE EXTENSION IF NOT EXISTS \"{extension}\"")
                print(f"✅ Extension enabled: {extension}")
            except Exception as e:
                print(f"⚠️  Extension {extension}: {e}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Extensions setup failed: {e}")
        return False

def optimize_postgresql_settings():
    """Provide PostgreSQL optimization recommendations"""
    print("\n📋 PostgreSQL Optimization Recommendations:")
    print("=" * 50)
    
    recommendations = [
        "# Memory Settings",
        "shared_buffers = 256MB                    # 25% of RAM for small servers",
        "effective_cache_size = 1GB               # 75% of available RAM",
        "work_mem = 4MB                           # Per connection work memory",
        "maintenance_work_mem = 64MB              # For maintenance operations",
        "",
        "# Connection Settings", 
        "max_connections = 100                    # Adjust based on expected load",
        "shared_preload_libraries = 'pg_stat_statements'",
        "",
        "# Logging Settings",
        "log_statement = 'all'                    # Log all statements (development)",
        "log_duration = on                       # Log query duration",
        "log_min_duration_statement = 1000       # Log slow queries (1 second)",
        "",
        "# Performance Settings",
        "random_page_cost = 1.1                  # For SSD storage",
        "effective_io_concurrency = 200          # For SSD storage",
        "checkpoint_completion_target = 0.9      # Spread checkpoints",
        "",
        "# Security Settings",
        "ssl = on                                 # Enable SSL",
        "password_encryption = scram-sha-256     # Strong password encryption",
    ]
    
    for rec in recommendations:
        print(rec)
    
    print("\n⚠️  Add these settings to postgresql.conf and restart PostgreSQL")
    print("⚠️  Adjust values based on your server specifications")

def create_backup_script():
    """Create a database backup script"""
    config = get_db_config()
    
    backup_script = f"""#!/bin/bash
# TikTrue Database Backup Script
# Generated automatically by setup_postgresql.py

# Configuration
DB_HOST="{config['host']}"
DB_PORT="{config['port']}"
DB_NAME="{config['database']}"
DB_USER="{config['user']}"
BACKUP_DIR="/var/backups/tiktrue"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/tiktrue_backup_$DATE.sql"

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Create backup
echo "Creating database backup..."
PGPASSWORD="{config['password']}" pg_dump \\
    -h $DB_HOST \\
    -p $DB_PORT \\
    -U $DB_USER \\
    -d $DB_NAME \\
    --verbose \\
    --clean \\
    --no-owner \\
    --no-privileges \\
    > $BACKUP_FILE

if [ $? -eq 0 ]; then
    echo "✅ Backup created successfully: $BACKUP_FILE"
    
    # Compress backup
    gzip $BACKUP_FILE
    echo "✅ Backup compressed: $BACKUP_FILE.gz"
    
    # Remove backups older than 7 days
    find $BACKUP_DIR -name "tiktrue_backup_*.sql.gz" -mtime +7 -delete
    echo "✅ Old backups cleaned up"
else
    echo "❌ Backup failed"
    exit 1
fi
"""
    
    try:
        with open('backend/backup_database.sh', 'w') as f:
            f.write(backup_script)
        
        # Make script executable
        os.chmod('backend/backup_database.sh', 0o755)
        
        print("✅ Backup script created: backend/backup_database.sh")
        print("   Run with: ./backend/backup_database.sh")
        
        return True
        
    except Exception as e:
        print(f"❌ Backup script creation failed: {e}")
        return False

def create_restore_script():
    """Create a database restore script"""
    config = get_db_config()
    
    restore_script = f"""#!/bin/bash
# TikTrue Database Restore Script
# Generated automatically by setup_postgresql.py

# Configuration
DB_HOST="{config['host']}"
DB_PORT="{config['port']}"
DB_NAME="{config['database']}"
DB_USER="{config['user']}"

# Check if backup file is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo "Example: $0 /var/backups/tiktrue/tiktrue_backup_20240128_120000.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "⚠️  WARNING: This will replace all data in database $DB_NAME"
echo "⚠️  Make sure you have a current backup before proceeding"
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled"
    exit 0
fi

echo "🔄 Restoring database from: $BACKUP_FILE"

# Restore database
if [[ "$BACKUP_FILE" == *.gz ]]; then
    # Compressed backup
    PGPASSWORD="{config['password']}" gunzip -c $BACKUP_FILE | psql \\
        -h $DB_HOST \\
        -p $DB_PORT \\
        -U $DB_USER \\
        -d $DB_NAME \\
        --quiet
else
    # Uncompressed backup
    PGPASSWORD="{config['password']}" psql \\
        -h $DB_HOST \\
        -p $DB_PORT \\
        -U $DB_USER \\
        -d $DB_NAME \\
        --quiet \\
        < $BACKUP_FILE
fi

if [ $? -eq 0 ]; then
    echo "✅ Database restored successfully"
    echo "   Don't forget to run Django migrations if needed"
else
    echo "❌ Database restore failed"
    exit 1
fi
"""
    
    try:
        with open('backend/restore_database.sh', 'w') as f:
            f.write(restore_script)
        
        # Make script executable
        os.chmod('backend/restore_database.sh', 0o755)
        
        print("✅ Restore script created: backend/restore_database.sh")
        print("   Run with: ./backend/restore_database.sh <backup_file>")
        
        return True
        
    except Exception as e:
        print(f"❌ Restore script creation failed: {e}")
        return False

def main():
    """Main PostgreSQL setup function"""
    print("TikTrue PostgreSQL Database Setup")
    print("=" * 40)
    
    # Check if psycopg2 is available
    try:
        import psycopg2
    except ImportError:
        print("❌ psycopg2 not found. Install with: pip install psycopg2-binary")
        sys.exit(1)
    
    # Get configuration
    config = get_db_config()
    print(f"Database Host: {config['host']}:{config['port']}")
    print(f"Database Name: {config['database']}")
    print(f"Database User: {config['user']}")
    print()
    
    # Create database and user
    if not create_database_and_user():
        print("❌ Failed to create database and user")
        sys.exit(1)
    
    # Test connection
    if not test_database_connection():
        print("❌ Failed to connect to database")
        sys.exit(1)
    
    # Setup extensions
    setup_database_extensions()
    
    # Create backup and restore scripts
    create_backup_script()
    create_restore_script()
    
    # Show optimization recommendations
    optimize_postgresql_settings()
    
    print("\n✅ PostgreSQL setup completed successfully!")
    print("\nNext steps:")
    print("1. Run Django migrations: python manage.py migrate")
    print("2. Create superuser: python manage.py createsuperuser")
    print("3. Setup regular backups with: ./backend/backup_database.sh")
    print("4. Consider applying PostgreSQL optimizations shown above")

if __name__ == "__main__":
    main()