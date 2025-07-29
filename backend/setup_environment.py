#!/usr/bin/env python3
"""
Environment Variables Setup Script for TikTrue Backend

This script helps generate and validate environment variables for production deployment.
"""

import os
import secrets
import string
from django.core.management.utils import get_random_secret_key

def generate_secret_key():
    """Generate a secure Django secret key"""
    return get_random_secret_key()

def generate_secure_password(length=32):
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def validate_environment_variables():
    """Validate that all required environment variables are set"""
    required_vars = {
        'SECRET_KEY': 'Django secret key for cryptographic signing',
        'DEBUG': 'Debug mode (should be False in production)',
        'ALLOWED_HOSTS': 'Comma-separated list of allowed hosts',
        'CORS_ALLOWED_ORIGINS': 'Comma-separated list of allowed CORS origins'
    }
    
    missing_vars = []
    warnings = []
    
    for var, description in required_vars.items():
        value = os.environ.get(var)
        if not value:
            missing_vars.append(f"{var}: {description}")
        elif var == 'SECRET_KEY' and 'django-insecure' in value:
            warnings.append(f"{var}: Using insecure default key")
        elif var == 'DEBUG' and value.lower() == 'true':
            warnings.append(f"{var}: Debug mode is enabled (should be False in production)")
    
    return missing_vars, warnings

def create_env_file():
    """Create .env file with secure defaults"""
    from pathlib import Path
    
    env_file = Path('.env')
    env_example = Path('.env.example')
    
    if env_file.exists():
        print("✅ .env file already exists")
        return True
    
    secret_key = generate_secret_key()
    db_password = generate_secure_password(16)
    
    env_content = f"""# TikTrue Backend Environment Configuration
# Generated automatically by setup_environment.py

# Django Settings
SECRET_KEY={secret_key}
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,tiktrue.com,www.tiktrue.com,api.tiktrue.com

# Database Configuration (Development - SQLite)
# For production, use DATABASE_URL instead
# DATABASE_URL=postgresql://user:password@localhost:5432/tiktrue_db

# Database Configuration (Production - PostgreSQL)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=tiktrue_db
DB_USER=tiktrue_user
DB_PASSWORD={db_password}
DB_ADMIN_USER=postgres
DB_ADMIN_PASSWORD=

# CORS Settings
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://tiktrue.com,https://www.tiktrue.com

# Payment Gateway Settings

# Stripe (International)
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRO_PRICE_ID=price_...
STRIPE_ENTERPRISE_PRICE_ID=price_...

# PayPal (International)
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_SANDBOX=True

# Iranian Payment Gateways
ZARINPAL_MERCHANT_ID=
ZARINPAL_SANDBOX=True

IDPAY_API_KEY=
IDPAY_SANDBOX=True

NEXTPAY_API_KEY=
NEXTPAY_SANDBOX=True

# Email Settings (Optional)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=

# Logging Level
DJANGO_LOG_LEVEL=INFO

# Security Settings (Production)
# Uncomment these for production deployment
# SECURE_SSL_REDIRECT=True
# SECURE_HSTS_SECONDS=31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS=True
# SECURE_HSTS_PRELOAD=True
# SESSION_COOKIE_SECURE=True
# CSRF_COOKIE_SECURE=True
"""
    
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        print("✅ .env file created with secure defaults")
        print(f"   Database password: {db_password}")
        print("⚠️  Please edit .env file with your actual configuration")
        return True
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False

def print_environment_template():
    """Print a template for environment variables"""
    secret_key = generate_secret_key()
    
    template = f"""
# TikTrue Backend Environment Variables
# Set these in Liara dashboard for production deployment

# REQUIRED: Django Secret Key
SECRET_KEY={secret_key}

# Debug mode (False for production)
DEBUG=False

# Allowed hosts (include your domains)
ALLOWED_HOSTS=tiktrue-backend.liara.run,api.tiktrue.com,tiktrue.com

# CORS allowed origins (include frontend domains)
CORS_ALLOWED_ORIGINS=https://tiktrue.com,https://www.tiktrue.com,https://tiktrue-frontend.liara.run

# Database URL (automatically provided by Liara)
# DATABASE_URL=postgres://user:password@host:port/database

# Payment Gateway Settings (Production)
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRO_PRICE_ID=price_...
STRIPE_ENTERPRISE_PRICE_ID=price_...

# Iranian Payment Gateways
ZARINPAL_MERCHANT_ID=your_merchant_id
ZARINPAL_SANDBOX=False
IDPAY_API_KEY=your_api_key
IDPAY_SANDBOX=False
NEXTPAY_API_KEY=your_api_key
NEXTPAY_SANDBOX=False

# Optional: Django logging level
DJANGO_LOG_LEVEL=INFO

# Optional: Email configuration for password reset
# EMAIL_HOST=smtp.gmail.com
# EMAIL_PORT=587
# EMAIL_USE_TLS=True
# EMAIL_HOST_USER=your-email@gmail.com
# EMAIL_HOST_PASSWORD=your-app-password
"""
    
    print("Environment Variables Template:")
    print("=" * 50)
    print(template)
    print("=" * 50)
    print("\nInstructions:")
    print("1. Copy the variables above")
    print("2. Go to Liara dashboard → Your App → Settings → Environment Variables")
    print("3. Add each variable with its value")
    print("4. Restart your application after setting variables")

def main():
    """Main function"""
    print("TikTrue Backend Environment Setup")
    print("=" * 40)
    
    # Create .env file if it doesn't exist
    create_env_file()
    
    # Check if we're in a Django environment
    try:
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tiktrue_backend.settings')
        django.setup()
        
        # Validate current environment
        missing, warnings = validate_environment_variables()
        
        if missing:
            print("\n❌ Missing required environment variables:")
            for var in missing:
                print(f"  - {var}")
        
        if warnings:
            print("\n⚠️  Environment variable warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        
        if not missing and not warnings:
            print("\n✅ All environment variables are properly configured!")
        
    except ImportError:
        print("Django not available. Generating template only.")
    
    # Always print the template for production deployment
    print_environment_template()
    
    print("\n🎉 Environment setup completed!")
    print("\nNext steps:")
    print("1. Edit .env file with your actual configuration")
    print("2. For production: Set up PostgreSQL with setup_postgresql.py")
    print("3. Run database setup: python setup_database.py")
    print("4. Start development server: python manage.py runserver")

if __name__ == "__main__":
    main()