from django.utils import timezone
from datetime import timedelta
import hashlib
import hmac
import json
import logging

logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

def get_user_agent(request):
    """Get user agent from request"""
    return request.META.get('HTTP_USER_AGENT', '')

def generate_payment_signature(data, secret_key):
    """Generate payment signature for security"""
    message = json.dumps(data, sort_keys=True)
    signature = hmac.new(
        secret_key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature

def verify_payment_signature(data, signature, secret_key):
    """Verify payment signature"""
    expected_signature = generate_payment_signature(data, secret_key)
    return hmac.compare_digest(signature, expected_signature)

def format_currency_amount(amount, currency):
    """Format currency amount for display"""
    if currency == 'IRR':
        return f"{int(amount):,} ریال"
    elif currency == 'TOMAN':
        return f"{int(amount):,} تومان"
    elif currency == 'USD':
        return f"${amount:.2f}"
    elif currency == 'EUR':
        return f"€{amount:.2f}"
    else:
        return f"{amount} {currency}"

def calculate_subscription_expiry(current_expiry, duration_days):
    """Calculate new subscription expiry date"""
    now = timezone.now()
    
    if current_expiry and current_expiry > now:
        # Extend existing subscription
        return current_expiry + timedelta(days=duration_days)
    else:
        # New subscription
        return now + timedelta(days=duration_days)

def is_subscription_active(user):
    """Check if user's subscription is active"""
    if not user.subscription_expires:
        return user.subscription_plan != 'free'
    return user.subscription_expires > timezone.now()

def get_subscription_days_remaining(user):
    """Get days remaining in subscription"""
    if not user.subscription_expires:
        return None
    
    now = timezone.now()
    if user.subscription_expires <= now:
        return 0
        
    delta = user.subscription_expires - now
    return delta.days

def validate_payment_amount(amount, min_amount=1, max_amount=1000000):
    """Validate payment amount"""
    try:
        amount = float(amount)
        if amount < min_amount:
            return False, f"Amount must be at least {min_amount}"
        if amount > max_amount:
            return False, f"Amount cannot exceed {max_amount}"
        return True, None
    except (ValueError, TypeError):
        return False, "Invalid amount format"

def sanitize_callback_data(data):
    """Sanitize callback data for logging"""
    sensitive_fields = [
        'password', 'token', 'secret', 'key', 'auth',
        'card_number', 'cvv', 'pin'
    ]
    
    sanitized = {}
    for key, value in data.items():
        if any(field in key.lower() for field in sensitive_fields):
            sanitized[key] = '***REDACTED***'
        else:
            sanitized[key] = value
            
    return sanitized

def log_payment_event(event_type, payment, data=None, level='info'):
    """Log payment events with structured data"""
    log_data = {
        'event_type': event_type,
        'payment_id': str(payment.id),
        'user_id': str(payment.user.id),
        'user_email': payment.user.email,
        'amount': float(payment.amount),
        'currency': payment.currency,
        'status': payment.status,
        'provider': payment.payment_method.provider,
        'timestamp': timezone.now().isoformat()
    }
    
    if data:
        log_data['data'] = sanitize_callback_data(data)
    
    log_message = f"Payment {event_type}: {payment.id}"
    
    if level == 'error':
        logger.error(log_message, extra=log_data)
    elif level == 'warning':
        logger.warning(log_message, extra=log_data)
    else:
        logger.info(log_message, extra=log_data)

def get_payment_status_display(status):
    """Get human-readable payment status"""
    status_map = {
        'pending': 'در انتظار پرداخت',
        'processing': 'در حال پردازش',
        'completed': 'پرداخت موفق',
        'failed': 'پرداخت ناموفق',
        'cancelled': 'لغو شده',
        'refunded': 'بازگردانده شده'
    }
    return status_map.get(status, status)

def get_provider_display_name(provider):
    """Get human-readable provider name"""
    provider_map = {
        'zarinpal': 'زرین‌پال',
        'idpay': 'آیدی‌پی',
        'nextpay': 'نکست‌پی',
        'stripe': 'Stripe',
        'paypal': 'PayPal'
    }
    return provider_map.get(provider, provider)

def convert_currency_amount(amount, from_currency, to_currency):
    """Convert amount between currencies (simplified)"""
    # This is a simplified conversion - in production you'd use real exchange rates
    conversion_rates = {
        ('TOMAN', 'IRR'): 10,
        ('IRR', 'TOMAN'): 0.1,
        ('USD', 'IRR'): 42000,  # Approximate rate
        ('IRR', 'USD'): 1/42000,
        ('EUR', 'IRR'): 45000,  # Approximate rate
        ('IRR', 'EUR'): 1/45000,
    }
    
    if from_currency == to_currency:
        return amount
        
    rate = conversion_rates.get((from_currency, to_currency))
    if rate:
        return amount * rate
    else:
        # If direct conversion not available, convert through IRR
        if from_currency != 'IRR':
            amount = convert_currency_amount(amount, from_currency, 'IRR')
        if to_currency != 'IRR':
            amount = convert_currency_amount(amount, 'IRR', to_currency)
        return amount

def generate_payment_reference(payment):
    """Generate unique payment reference"""
    import uuid
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    return f"TT-{timestamp}-{unique_id}"

def validate_webhook_signature(payload, signature, secret):
    """Validate webhook signature"""
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)

def parse_callback_amount(amount_str, currency):
    """Parse amount from callback string"""
    try:
        amount = float(amount_str)
        
        # Convert to standard currency if needed
        if currency == 'IRR' and amount < 1000:
            # Probably in Toman, convert to Rial
            amount *= 10
            
        return amount
    except (ValueError, TypeError):
        return None

def get_payment_description(payment):
    """Get payment description for providers"""
    plan_name = payment.pricing_plan.name
    duration = payment.pricing_plan.duration_days
    
    if duration == 30:
        period = "ماهانه"
    elif duration == 365:
        period = "سالانه"
    else:
        period = f"{duration} روزه"
        
    return f"اشتراک {plan_name} TikTrue - {period}"

def calculate_payment_fee(amount, provider, currency='IRR'):
    """Calculate payment processing fee"""
    # Fee structures for different providers (approximate)
    fee_structures = {
        'zarinpal': {
            'IRR': {'rate': 0.015, 'min': 500, 'max': 50000},  # 1.5%
            'TOMAN': {'rate': 0.015, 'min': 50, 'max': 5000}
        },
        'idpay': {
            'IRR': {'rate': 0.02, 'min': 1000, 'max': 100000},  # 2%
            'TOMAN': {'rate': 0.02, 'min': 100, 'max': 10000}
        },
        'stripe': {
            'USD': {'rate': 0.029, 'fixed': 0.30},  # 2.9% + $0.30
            'EUR': {'rate': 0.029, 'fixed': 0.25}   # 2.9% + €0.25
        }
    }
    
    fee_config = fee_structures.get(provider, {}).get(currency)
    if not fee_config:
        return 0
        
    if 'rate' in fee_config:
        fee = amount * fee_config['rate']
        
        if 'min' in fee_config:
            fee = max(fee, fee_config['min'])
        if 'max' in fee_config:
            fee = min(fee, fee_config['max'])
        if 'fixed' in fee_config:
            fee += fee_config['fixed']
            
        return round(fee, 2)
    
    return 0

def get_supported_currencies_for_provider(provider):
    """Get supported currencies for a payment provider"""
    provider_currencies = {
        'zarinpal': ['IRR', 'TOMAN'],
        'idpay': ['IRR', 'TOMAN'],
        'nextpay': ['IRR', 'TOMAN'],
        'stripe': ['USD', 'EUR'],
        'paypal': ['USD', 'EUR']
    }
    
    return provider_currencies.get(provider, [])

def is_test_payment(payment):
    """Check if payment is in test/sandbox mode"""
    provider_config = getattr(payment.payment_method, 'configuration', {})
    return provider_config.get('sandbox', False)

def mask_sensitive_data(data, fields_to_mask=None):
    """Mask sensitive data in payment information"""
    if fields_to_mask is None:
        fields_to_mask = [
            'card_number', 'cvv', 'pin', 'password', 'token',
            'secret', 'key', 'auth', 'signature'
        ]
    
    if isinstance(data, dict):
        masked_data = {}
        for key, value in data.items():
            if any(field in key.lower() for field in fields_to_mask):
                if isinstance(value, str) and len(value) > 4:
                    masked_data[key] = value[:2] + '*' * (len(value) - 4) + value[-2:]
                else:
                    masked_data[key] = '***'
            else:
                masked_data[key] = mask_sensitive_data(value, fields_to_mask)
        return masked_data
    elif isinstance(data, list):
        return [mask_sensitive_data(item, fields_to_mask) for item in data]
    else:
        return data