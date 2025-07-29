from django.db import models
from django.contrib.auth import get_user_model
import uuid
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone

User = get_user_model()

class PaymentProvider(models.TextChoices):
    """Supported payment providers"""
    STRIPE = 'stripe', 'Stripe'
    PAYPAL = 'paypal', 'PayPal'
    ZARINPAL = 'zarinpal', 'ZarinPal'
    IDPAY = 'idpay', 'IDPay'
    NEXTPAY = 'nextpay', 'NextPay'

class PaymentStatus(models.TextChoices):
    """Payment status choices"""
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'
    REFUNDED = 'refunded', 'Refunded'

class SubscriptionPlan(models.TextChoices):
    """Available subscription plans"""
    FREE = 'free', 'Free'
    PRO = 'pro', 'Pro'
    ENTERPRISE = 'enterprise', 'Enterprise'

class Currency(models.TextChoices):
    """Supported currencies"""
    USD = 'USD', 'US Dollar'
    EUR = 'EUR', 'Euro'
    IRR = 'IRR', 'Iranian Rial'
    TOMAN = 'TOMAN', 'Iranian Toman'

class PaymentMethod(models.Model):
    """Payment method configuration for different providers"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=20, choices=PaymentProvider.choices)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    supported_currencies = models.JSONField(default=list)  # List of supported currency codes
    configuration = models.JSONField(default=dict)  # Provider-specific configuration
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['provider', 'name']
        
    def __str__(self):
        return f"{self.get_provider_display()} - {self.name}"
        
    def is_currency_supported(self, currency_code):
        """Check if currency is supported by this payment method"""
        return currency_code in self.supported_currencies

class PricingPlan(models.Model):
    """Pricing plans for different subscription tiers"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.CharField(max_length=20, choices=SubscriptionPlan.choices)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, choices=Currency.choices, default=Currency.USD)
    duration_days = models.IntegerField(default=30)  # Subscription duration in days
    max_clients = models.IntegerField(default=1)
    allowed_models = models.JSONField(default=list)  # List of allowed model names
    features = models.JSONField(default=list)  # List of features included
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['plan', 'currency']
        
    def __str__(self):
        return f"{self.name} - {self.price} {self.currency}"
        
    def get_price_display(self):
        """Get formatted price display"""
        if self.currency == Currency.IRR:
            return f"{int(self.price):,} ریال"
        elif self.currency == Currency.TOMAN:
            return f"{int(self.price):,} تومان"
        else:
            return f"{self.price} {self.currency}"

class Payment(models.Model):
    """Payment transaction record"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    pricing_plan = models.ForeignKey(PricingPlan, on_delete=models.PROTECT)
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT)
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, choices=Currency.choices)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    
    # Provider-specific fields
    provider_transaction_id = models.CharField(max_length=255, blank=True, null=True)
    provider_payment_url = models.URLField(blank=True, null=True)
    provider_response = models.JSONField(default=dict)  # Store provider response data
    
    # Tracking fields
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['provider_transaction_id']),
            models.Index(fields=['created_at']),
        ]
        
    def __str__(self):
        return f"Payment {self.id} - {self.user.email} - {self.get_status_display()}"
        
    def save(self, *args, **kwargs):
        # Set expires_at if not set
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=1)  # Payment expires in 1 hour
        super().save(*args, **kwargs)
        
    def is_expired(self):
        """Check if payment has expired"""
        return timezone.now() > self.expires_at
        
    def mark_as_paid(self):
        """Mark payment as completed and update user subscription"""
        if self.status != PaymentStatus.COMPLETED:
            self.status = PaymentStatus.COMPLETED
            self.paid_at = timezone.now()
            self.save()
            
            # Update user subscription
            self.update_user_subscription()
            
    def update_user_subscription(self):
        """Update user's subscription based on payment"""
        if self.status == PaymentStatus.COMPLETED:
            user = self.user
            plan = self.pricing_plan
            
            # Update user subscription
            user.subscription_plan = plan.plan
            user.max_clients = plan.max_clients
            user.allowed_models = plan.allowed_models
            
            # Set subscription expiration
            if user.subscription_expires and user.subscription_expires > timezone.now():
                # Extend existing subscription
                user.subscription_expires += timedelta(days=plan.duration_days)
            else:
                # New subscription
                user.subscription_expires = timezone.now() + timedelta(days=plan.duration_days)
                
            user.save()
            
    def get_amount_display(self):
        """Get formatted amount display"""
        if self.currency == Currency.IRR:
            return f"{int(self.amount):,} ریال"
        elif self.currency == Currency.TOMAN:
            return f"{int(self.amount):,} تومان"
        else:
            return f"{self.amount} {self.currency}"

class PaymentCallback(models.Model):
    """Payment callback/webhook record"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='callbacks')
    provider = models.CharField(max_length=20, choices=PaymentProvider.choices)
    
    # Callback data
    callback_data = models.JSONField(default=dict)
    headers = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Processing status
    is_processed = models.BooleanField(default=False)
    processing_result = models.TextField(blank=True)
    
    # Timestamps
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-received_at']
        
    def __str__(self):
        return f"Callback {self.id} - {self.payment.id} - {self.get_provider_display()}"
        
    def mark_as_processed(self, result=""):
        """Mark callback as processed"""
        self.is_processed = True
        self.processed_at = timezone.now()
        self.processing_result = result
        self.save()

class PaymentRefund(models.Model):
    """Payment refund record"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='refunds')
    
    # Refund details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    
    # Provider-specific fields
    provider_refund_id = models.CharField(max_length=255, blank=True, null=True)
    provider_response = models.JSONField(default=dict)
    
    # Admin fields
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='requested_refunds')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_refunds')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Refund {self.id} - {self.payment.id} - {self.get_status_display()}"
        
    def get_amount_display(self):
        """Get formatted amount display"""
        currency = self.payment.currency
        if currency == Currency.IRR:
            return f"{int(self.amount):,} ریال"
        elif currency == Currency.TOMAN:
            return f"{int(self.amount):,} تومان"
        else:
            return f"{self.amount} {currency}"

class PaymentAnalytics(models.Model):
    """Payment analytics and statistics"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField()
    
    # Daily statistics
    total_payments = models.IntegerField(default=0)
    successful_payments = models.IntegerField(default=0)
    failed_payments = models.IntegerField(default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Provider breakdown
    provider_stats = models.JSONField(default=dict)  # Stats per provider
    plan_stats = models.JSONField(default=dict)      # Stats per subscription plan
    currency_stats = models.JSONField(default=dict)  # Stats per currency
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['date']
        ordering = ['-date']
        
    def __str__(self):
        return f"Analytics {self.date} - {self.successful_payments}/{self.total_payments} payments"
        
    @classmethod
    def update_daily_stats(cls, date=None):
        """Update daily statistics for given date"""
        if date is None:
            date = timezone.now().date()
            
        # Get payments for the date
        payments = Payment.objects.filter(created_at__date=date)
        
        # Calculate statistics
        total_payments = payments.count()
        successful_payments = payments.filter(status=PaymentStatus.COMPLETED).count()
        failed_payments = payments.filter(status=PaymentStatus.FAILED).count()
        total_amount = payments.filter(status=PaymentStatus.COMPLETED).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        
        # Provider stats
        provider_stats = {}
        for provider in PaymentProvider.choices:
            provider_code = provider[0]
            provider_payments = payments.filter(payment_method__provider=provider_code)
            provider_stats[provider_code] = {
                'total': provider_payments.count(),
                'successful': provider_payments.filter(status=PaymentStatus.COMPLETED).count(),
                'amount': float(provider_payments.filter(status=PaymentStatus.COMPLETED).aggregate(
                    total=models.Sum('amount')
                )['total'] or Decimal('0'))
            }
            
        # Plan stats
        plan_stats = {}
        for plan in SubscriptionPlan.choices:
            plan_code = plan[0]
            plan_payments = payments.filter(pricing_plan__plan=plan_code)
            plan_stats[plan_code] = {
                'total': plan_payments.count(),
                'successful': plan_payments.filter(status=PaymentStatus.COMPLETED).count(),
                'amount': float(plan_payments.filter(status=PaymentStatus.COMPLETED).aggregate(
                    total=models.Sum('amount')
                )['total'] or Decimal('0'))
            }
            
        # Currency stats
        currency_stats = {}
        for currency in Currency.choices:
            currency_code = currency[0]
            currency_payments = payments.filter(currency=currency_code)
            currency_stats[currency_code] = {
                'total': currency_payments.count(),
                'successful': currency_payments.filter(status=PaymentStatus.COMPLETED).count(),
                'amount': float(currency_payments.filter(status=PaymentStatus.COMPLETED).aggregate(
                    total=models.Sum('amount')
                )['total'] or Decimal('0'))
            }
            
        # Update or create analytics record
        analytics, created = cls.objects.update_or_create(
            date=date,
            defaults={
                'total_payments': total_payments,
                'successful_payments': successful_payments,
                'failed_payments': failed_payments,
                'total_amount': total_amount,
                'provider_stats': provider_stats,
                'plan_stats': plan_stats,
                'currency_stats': currency_stats,
            }
        )
        
        return analytics