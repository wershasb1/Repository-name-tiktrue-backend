from rest_framework import serializers
from .models import (
    PaymentMethod, PricingPlan, Payment, PaymentCallback, 
    PaymentRefund, PaymentAnalytics
)
from django.contrib.auth import get_user_model

User = get_user_model()

class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for payment methods (public view)"""
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    
    class Meta:
        model = PaymentMethod
        fields = [
            'id', 'provider', 'provider_display', 'name', 'description',
            'is_active', 'supported_currencies'
        ]
        read_only_fields = ['id', 'provider_display']

class PricingPlanSerializer(serializers.ModelSerializer):
    """Serializer for pricing plans"""
    plan_display = serializers.CharField(source='get_plan_display', read_only=True)
    currency_display = serializers.CharField(source='get_currency_display', read_only=True)
    price_display = serializers.CharField(source='get_price_display', read_only=True)
    
    class Meta:
        model = PricingPlan
        fields = [
            'id', 'plan', 'plan_display', 'name', 'description',
            'price', 'currency', 'currency_display', 'price_display',
            'duration_days', 'max_clients', 'allowed_models', 'features',
            'is_active'
        ]
        read_only_fields = ['id', 'plan_display', 'currency_display', 'price_display']

class PaymentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payments"""
    
    class Meta:
        model = Payment
        fields = [
            'pricing_plan', 'payment_method'
        ]
        
    def validate(self, data):
        """Validate payment creation data"""
        pricing_plan = data['pricing_plan']
        payment_method = data['payment_method']
        
        # Check if pricing plan is active
        if not pricing_plan.is_active:
            raise serializers.ValidationError("Selected pricing plan is not active")
            
        # Check if payment method is active
        if not payment_method.is_active:
            raise serializers.ValidationError("Selected payment method is not active")
            
        # Check if payment method supports the plan's currency
        if not payment_method.is_currency_supported(pricing_plan.currency):
            raise serializers.ValidationError(
                f"Payment method does not support {pricing_plan.currency} currency"
            )
            
        return data
        
    def create(self, validated_data):
        """Create payment with user context"""
        user = self.context['request'].user
        pricing_plan = validated_data['pricing_plan']
        
        payment = Payment.objects.create(
            user=user,
            pricing_plan=pricing_plan,
            payment_method=validated_data['payment_method'],
            amount=pricing_plan.price,
            currency=pricing_plan.currency,
            ip_address=self.get_client_ip(),
            user_agent=self.get_user_agent()
        )
        
        return payment
        
    def get_client_ip(self):
        """Get client IP address from request"""
        request = self.context.get('request')
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                return x_forwarded_for.split(',')[0]
            return request.META.get('REMOTE_ADDR')
        return None
        
    def get_user_agent(self):
        """Get user agent from request"""
        request = self.context.get('request')
        if request:
            return request.META.get('HTTP_USER_AGENT', '')
        return ''

class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for payment details"""
    user_email = serializers.CharField(source='user.email', read_only=True)
    pricing_plan_name = serializers.CharField(source='pricing_plan.name', read_only=True)
    payment_method_name = serializers.CharField(source='payment_method.name', read_only=True)
    provider_display = serializers.CharField(source='payment_method.get_provider_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    currency_display = serializers.CharField(source='get_currency_display', read_only=True)
    amount_display = serializers.CharField(source='get_amount_display', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'user_email', 'pricing_plan_name', 'payment_method_name',
            'provider_display', 'amount', 'currency', 'currency_display',
            'amount_display', 'status', 'status_display', 'is_expired',
            'provider_transaction_id', 'provider_payment_url',
            'created_at', 'updated_at', 'paid_at', 'expires_at'
        ]
        read_only_fields = [
            'id', 'user_email', 'pricing_plan_name', 'payment_method_name',
            'provider_display', 'status_display', 'currency_display',
            'amount_display', 'is_expired', 'created_at', 'updated_at',
            'paid_at', 'expires_at'
        ]

class PaymentListSerializer(serializers.ModelSerializer):
    """Simplified serializer for payment lists"""
    pricing_plan_name = serializers.CharField(source='pricing_plan.name', read_only=True)
    provider_display = serializers.CharField(source='payment_method.get_provider_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    amount_display = serializers.CharField(source='get_amount_display', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'pricing_plan_name', 'provider_display', 'amount_display',
            'status', 'status_display', 'created_at', 'paid_at'
        ]
        read_only_fields = fields

class PaymentCallbackSerializer(serializers.ModelSerializer):
    """Serializer for payment callbacks"""
    payment_id = serializers.CharField(source='payment.id', read_only=True)
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    
    class Meta:
        model = PaymentCallback
        fields = [
            'id', 'payment_id', 'provider', 'provider_display',
            'callback_data', 'is_processed', 'processing_result',
            'received_at', 'processed_at'
        ]
        read_only_fields = [
            'id', 'payment_id', 'provider_display', 'received_at', 'processed_at'
        ]

class PaymentRefundSerializer(serializers.ModelSerializer):
    """Serializer for payment refunds"""
    payment_id = serializers.CharField(source='payment.id', read_only=True)
    user_email = serializers.CharField(source='payment.user.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    amount_display = serializers.CharField(source='get_amount_display', read_only=True)
    requested_by_email = serializers.CharField(source='requested_by.email', read_only=True)
    approved_by_email = serializers.CharField(source='approved_by.email', read_only=True)
    
    class Meta:
        model = PaymentRefund
        fields = [
            'id', 'payment_id', 'user_email', 'amount', 'amount_display',
            'reason', 'status', 'status_display', 'provider_refund_id',
            'requested_by_email', 'approved_by_email',
            'created_at', 'updated_at', 'processed_at'
        ]
        read_only_fields = [
            'id', 'payment_id', 'user_email', 'amount_display', 'status_display',
            'requested_by_email', 'approved_by_email', 'created_at',
            'updated_at', 'processed_at'
        ]

class PaymentAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for payment analytics"""
    success_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = PaymentAnalytics
        fields = [
            'id', 'date', 'total_payments', 'successful_payments',
            'failed_payments', 'success_rate', 'total_amount',
            'provider_stats', 'plan_stats', 'currency_stats'
        ]
        read_only_fields = fields
        
    def get_success_rate(self, obj):
        """Calculate success rate percentage"""
        if obj.total_payments > 0:
            return round((obj.successful_payments / obj.total_payments) * 100, 2)
        return 0.0

class UserSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for user subscription information"""
    subscription_plan_display = serializers.CharField(source='get_subscription_plan_display', read_only=True)
    allowed_models = serializers.JSONField(read_only=True)
    is_subscription_active = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'subscription_plan', 'subscription_plan_display',
            'subscription_expires', 'max_clients', 'allowed_models',
            'is_subscription_active', 'days_until_expiry'
        ]
        read_only_fields = fields
        
    def get_is_subscription_active(self, obj):
        """Check if subscription is active"""
        if not obj.subscription_expires:
            return obj.subscription_plan != 'free'
        from django.utils import timezone
        return obj.subscription_expires > timezone.now()
        
    def get_days_until_expiry(self, obj):
        """Get days until subscription expires"""
        if not obj.subscription_expires:
            return None
        from django.utils import timezone
        delta = obj.subscription_expires - timezone.now()
        return max(0, delta.days)

class PaymentStatsSerializer(serializers.Serializer):
    """Serializer for payment statistics"""
    total_payments = serializers.IntegerField()
    successful_payments = serializers.IntegerField()
    failed_payments = serializers.IntegerField()
    pending_payments = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    success_rate = serializers.FloatField()
    average_payment_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    # Time-based stats
    today_payments = serializers.IntegerField()
    this_week_payments = serializers.IntegerField()
    this_month_payments = serializers.IntegerField()
    
    # Provider breakdown
    provider_breakdown = serializers.DictField()
    plan_breakdown = serializers.DictField()
    currency_breakdown = serializers.DictField()