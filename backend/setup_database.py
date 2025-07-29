#!/usr/bin/env python3
"""
Database Setup Script for TikTrue Backend

This script handles database setup, migrations, and initial data creation.
"""

import os
import sys
import django
from django.core.management import execute_from_command_line, call_command
from django.db import connection
from django.conf import settings

def setup_django():
    """Setup Django environment"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tiktrue_backend.settings')
    django.setup()

def check_database_connection():
    """Check if database connection is working"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def check_database_exists():
    """Check if database tables exist"""
    try:
        with connection.cursor() as cursor:
            # Use database-agnostic approach
            if 'postgresql' in settings.DATABASES['default']['ENGINE']:
                # PostgreSQL
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                table_count = cursor.fetchone()[0]
            else:
                # SQLite
                cursor.execute("""
                    SELECT COUNT(*) FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                table_count = cursor.fetchone()[0]
        print(f"✅ Found {table_count} database tables")
        return table_count > 0
    except Exception as e:
        print(f"⚠️  Could not check database tables: {e}")
        return False

def run_migrations():
    """Run Django migrations"""
    try:
        print("🔄 Running database migrations...")
        
        # First, create migrations for custom apps if they don't exist
        custom_apps = ['accounts', 'licenses', 'models_api']
        for app in custom_apps:
            try:
                call_command('makemigrations', app, verbosity=1)
                print(f"✅ Created migrations for {app}")
            except Exception as e:
                print(f"⚠️  Migrations for {app}: {e}")
        
        # Run all migrations
        call_command('migrate', verbosity=1)
        print("✅ Database migrations completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

def collect_static_files():
    """Collect static files"""
    try:
        print("🔄 Collecting static files...")
        call_command('collectstatic', '--noinput', verbosity=1)
        print("✅ Static files collected successfully")
        return True
    except Exception as e:
        print(f"❌ Static files collection failed: {e}")
        return False

def create_superuser_if_needed():
    """Create superuser if none exists"""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        if not User.objects.filter(is_superuser=True).exists():
            print("🔄 No superuser found. Creating default superuser...")
            
            # Get superuser details from environment or use defaults
            username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
            email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@tiktrue.com')
            password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')
            
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            print(f"✅ Superuser '{username}' created successfully")
            print(f"   Email: {email}")
            print(f"   Password: {password}")
            print("   ⚠️  Please change the password after first login!")
        else:
            print("✅ Superuser already exists")
        
        return True
    except Exception as e:
        print(f"❌ Superuser creation failed: {e}")
        return False

def setup_initial_data():
    """Setup initial data for the application"""
    try:
        print("🔄 Setting up initial data...")
        
        # Import models
        from accounts.models import User
        from licenses.models import License
        from payments.models import PaymentMethod, PricingPlan, PaymentProvider, SubscriptionPlan, Currency
        from models_api.models import ModelFile
        
        # Setup Payment Methods
        setup_payment_methods()
        
        # Setup Pricing Plans
        setup_pricing_plans()
        
        # Setup Model Files
        setup_model_files()
        
        # Create sample data if needed
        if not User.objects.filter(email='demo@tiktrue.com').exists():
            demo_user = User.objects.create_user(
                username='demo',
                email='demo@tiktrue.com',
                password='demo123',
                subscription_plan='enterprise',  # MVP: همه Enterprise
                max_clients=999
            )
            print("✅ Demo user created")
        
        print("✅ Initial data setup completed")
        return True
        
    except Exception as e:
        print(f"⚠️  Initial data setup: {e}")
        return False

def setup_payment_methods():
    """Setup payment methods for different providers"""
    try:
        from payments.models import PaymentMethod, PaymentProvider
        
        payment_methods_data = [
            {
                'provider': PaymentProvider.STRIPE,
                'name': 'Credit Card (International)',
                'description': 'International credit card payments via Stripe',
                'supported_currencies': ['USD', 'EUR'],
                'configuration': {
                    'supports_subscriptions': True,
                    'supports_refunds': True,
                    'processing_fee_percent': 2.9,
                    'processing_fee_fixed': 0.30
                }
            },
            {
                'provider': PaymentProvider.PAYPAL,
                'name': 'PayPal',
                'description': 'PayPal payments for international customers',
                'supported_currencies': ['USD', 'EUR'],
                'configuration': {
                    'supports_subscriptions': True,
                    'supports_refunds': True,
                    'processing_fee_percent': 3.4,
                    'processing_fee_fixed': 0.30
                }
            },
            {
                'provider': PaymentProvider.ZARINPAL,
                'name': 'ZarinPal',
                'description': 'Iranian payment gateway',
                'supported_currencies': ['IRR', 'TOMAN'],
                'configuration': {
                    'supports_subscriptions': False,
                    'supports_refunds': True,
                    'processing_fee_percent': 1.5,
                    'processing_fee_fixed': 0
                }
            },
            {
                'provider': PaymentProvider.IDPAY,
                'name': 'IDPay',
                'description': 'Iranian payment gateway',
                'supported_currencies': ['IRR', 'TOMAN'],
                'configuration': {
                    'supports_subscriptions': False,
                    'supports_refunds': True,
                    'processing_fee_percent': 1.8,
                    'processing_fee_fixed': 0
                }
            },
            {
                'provider': PaymentProvider.NEXTPAY,
                'name': 'NextPay',
                'description': 'Iranian payment gateway',
                'supported_currencies': ['IRR', 'TOMAN'],
                'configuration': {
                    'supports_subscriptions': False,
                    'supports_refunds': True,
                    'processing_fee_percent': 2.0,
                    'processing_fee_fixed': 0
                }
            }
        ]
        
        for method_data in payment_methods_data:
            method, created = PaymentMethod.objects.get_or_create(
                provider=method_data['provider'],
                name=method_data['name'],
                defaults={
                    'description': method_data['description'],
                    'supported_currencies': method_data['supported_currencies'],
                    'configuration': method_data['configuration'],
                    'is_active': True
                }
            )
            if created:
                print(f"✅ Created payment method: {method.name}")
            else:
                print(f"⚪ Payment method exists: {method.name}")
                
    except Exception as e:
        print(f"⚠️  Payment methods setup failed: {e}")

def setup_pricing_plans():
    """Setup pricing plans for different subscription tiers"""
    try:
        from payments.models import PricingPlan, SubscriptionPlan, Currency
        
        # USD Pricing Plans
        usd_plans = [
            {
                'plan': SubscriptionPlan.FREE,
                'name': 'Free Plan',
                'description': 'Basic access with limited features',
                'price': 0,
                'currency': Currency.USD,
                'duration_days': 365,  # Free for 1 year
                'max_clients': 1,
                'allowed_models': ['llama3_1_8b_fp16'],
                'features': [
                    '1 concurrent client',
                    'Basic model access',
                    'Community support'
                ]
            },
            {
                'plan': SubscriptionPlan.PRO,
                'name': 'Pro Plan',
                'description': 'Professional features for small teams',
                'price': 29,
                'currency': Currency.USD,
                'duration_days': 30,
                'max_clients': 20,
                'allowed_models': ['llama3_1_8b_fp16', 'mistral_7b_int4'],
                'features': [
                    'Up to 20 concurrent clients',
                    'All available models',
                    'Priority support',
                    'Advanced analytics'
                ]
            },
            {
                'plan': SubscriptionPlan.ENTERPRISE,
                'name': 'Enterprise Plan',
                'description': 'Full features for large organizations',
                'price': 99,
                'currency': Currency.USD,
                'duration_days': 30,
                'max_clients': 999,
                'allowed_models': ['llama3_1_8b_fp16', 'mistral_7b_int4'],
                'features': [
                    'Unlimited concurrent clients',
                    'All available models',
                    'Premium support',
                    'Custom integrations',
                    'Advanced analytics',
                    'White-label options'
                ]
            }
        ]
        
        # Iranian Toman Pricing Plans
        toman_plans = [
            {
                'plan': SubscriptionPlan.FREE,
                'name': 'پلن رایگان',
                'description': 'دسترسی پایه با امکانات محدود',
                'price': 0,
                'currency': Currency.TOMAN,
                'duration_days': 365,
                'max_clients': 1,
                'allowed_models': ['llama3_1_8b_fp16'],
                'features': [
                    '1 کلاینت همزمان',
                    'دسترسی به مدل پایه',
                    'پشتیبانی انجمن'
                ]
            },
            {
                'plan': SubscriptionPlan.PRO,
                'name': 'پلن حرفه‌ای',
                'description': 'امکانات حرفه‌ای برای تیم‌های کوچک',
                'price': 1200000,  # ~29 USD in Toman
                'currency': Currency.TOMAN,
                'duration_days': 30,
                'max_clients': 20,
                'allowed_models': ['llama3_1_8b_fp16', 'mistral_7b_int4'],
                'features': [
                    'تا 20 کلاینت همزمان',
                    'تمام مدل‌های موجود',
                    'پشتیبانی اولویت‌دار',
                    'آنالیتیک پیشرفته'
                ]
            },
            {
                'plan': SubscriptionPlan.ENTERPRISE,
                'name': 'پلن سازمانی',
                'description': 'تمام امکانات برای سازمان‌های بزرگ',
                'price': 4000000,  # ~99 USD in Toman
                'currency': Currency.TOMAN,
                'duration_days': 30,
                'max_clients': 999,
                'allowed_models': ['llama3_1_8b_fp16', 'mistral_7b_int4'],
                'features': [
                    'کلاینت‌های نامحدود',
                    'تمام مدل‌های موجود',
                    'پشتیبانی ویژه',
                    'یکپارچه‌سازی سفارشی',
                    'آنالیتیک پیشرفته',
                    'گزینه‌های برندسازی'
                ]
            }
        ]
        
        all_plans = usd_plans + toman_plans
        
        for plan_data in all_plans:
            plan, created = PricingPlan.objects.get_or_create(
                plan=plan_data['plan'],
                currency=plan_data['currency'],
                defaults={
                    'name': plan_data['name'],
                    'description': plan_data['description'],
                    'price': plan_data['price'],
                    'duration_days': plan_data['duration_days'],
                    'max_clients': plan_data['max_clients'],
                    'allowed_models': plan_data['allowed_models'],
                    'features': plan_data['features'],
                    'is_active': True
                }
            )
            if created:
                print(f"✅ Created pricing plan: {plan.name}")
            else:
                print(f"⚪ Pricing plan exists: {plan.name}")
                
    except Exception as e:
        print(f"⚠️  Pricing plans setup failed: {e}")

def setup_model_files():
    """Setup model file records"""
    try:
        from models_api.models import ModelFile
        
        models_data = [
            {
                'name': 'llama3_1_8b_fp16',
                'display_name': 'Llama 3.1 8B FP16',
                'description': 'Meta Llama 3.1 8B model with FP16 precision for balanced performance and quality',
                'version': '1.0.0',
                'file_size': 16000000000,  # ~16GB
                'block_count': 33,
            },
            {
                'name': 'mistral_7b_int4',
                'display_name': 'Mistral 7B INT4',
                'description': 'Mistral 7B model with INT4 quantization for efficient inference',
                'version': '1.0.0',
                'file_size': 4000000000,  # ~4GB
                'block_count': 32,
            }
        ]
        
        for model_data in models_data:
            model, created = ModelFile.objects.get_or_create(
                name=model_data['name'],
                defaults={
                    'display_name': model_data['display_name'],
                    'description': model_data['description'],
                    'version': model_data['version'],
                    'file_size': model_data['file_size'],
                    'block_count': model_data['block_count'],
                    'is_active': True
                }
            )
            if created:
                print(f"✅ Created model file: {model.display_name}")
            else:
                print(f"⚪ Model file exists: {model.display_name}")
                
    except Exception as e:
        print(f"⚠️  Model files setup failed: {e}")

def validate_database_setup():
    """Validate that database setup is correct"""
    try:
        print("🔄 Validating database setup...")
        
        # Check if all expected tables exist
        expected_tables = [
            'accounts_user',
            'licenses_license',
            'models_api_modelfile',
            'payments_payment',
            'payments_paymentmethod',
            'payments_pricingplan'
        ]
        
        with connection.cursor() as cursor:
            # Use database-agnostic approach
            if 'postgresql' in settings.DATABASES['default']['ENGINE']:
                # PostgreSQL
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                existing_tables = [row[0] for row in cursor.fetchall()]
            else:
                # SQLite
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                existing_tables = [row[0] for row in cursor.fetchall()]
        
        missing_tables = []
        for table in expected_tables:
            if table not in existing_tables:
                missing_tables.append(table)
        
        if missing_tables:
            print(f"⚠️  Missing tables: {missing_tables}")
            return False
        else:
            print("✅ All expected tables exist")
            return True
            
    except Exception as e:
        print(f"❌ Database validation failed: {e}")
        return False

def main():
    """Main setup function"""
    print("TikTrue Backend Database Setup")
    print("=" * 40)
    
    # Setup Django
    setup_django()
    
    # Check database connection
    if not check_database_connection():
        print("❌ Cannot proceed without database connection")
        sys.exit(1)
    
    # Check if this is first-time setup
    is_first_time = not check_database_exists()
    
    if is_first_time:
        print("🆕 First-time database setup detected")
    else:
        print("🔄 Existing database detected, running updates")
    
    # Run migrations
    if not run_migrations():
        print("❌ Database setup failed at migration step")
        sys.exit(1)
    
    # Collect static files
    if not collect_static_files():
        print("⚠️  Static files collection failed, but continuing...")
    
    # Create superuser if needed
    if is_first_time:
        create_superuser_if_needed()
    
    # Setup initial data
    setup_initial_data()
    
    # Validate setup
    if validate_database_setup():
        print("\n✅ Database setup completed successfully!")
        print("\nNext steps:")
        print("1. Test the health check endpoint: /health/")
        print("2. Access admin panel: /admin/")
        print("3. Test API endpoints")
    else:
        print("\n⚠️  Database setup completed with warnings")
        print("Please check the issues above and resolve them")

if __name__ == "__main__":
    main()