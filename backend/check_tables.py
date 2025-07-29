#!/usr/bin/env python3
"""
Check database tables script
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tiktrue_backend.settings')
django.setup()

from django.db import connection

def check_tables():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
    
    print("Existing database tables:")
    for table in tables:
        print(f"  - {table}")
    
    return tables

if __name__ == "__main__":
    check_tables()