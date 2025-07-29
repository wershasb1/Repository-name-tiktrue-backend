from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    PaymentMethod, PricingPlan, Payment, PaymentCallback,
    PaymentRefund, PaymentAnalytics
)

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider', 'is_active', 'supported_currencies_display', 'created_at']
    list_filter = ['provider', 'is_active', 'created_at']
    search_fields = ['name', 'provider']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'provider', 'description', 'is_active')
        }),
        ('Configuration', {
            'fields': ('supported_currencies', 'configuration'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def supported_currencies_display(self, obj):
        return ', '.join(obj.supported_currencies) if obj.supported_currencies else 'None'
    supported_currencies_display.short_description = 'Supported Currencies'

@admin.register(PricingPlan)
class PricingPlanAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'plan', 'price_display', 'duration_days', 
        'max_clients', 'is_active', 'created_at'
    ]
    list_filter = ['plan', 'currency', 'is_active', 'created_at']
    search_fields = ['name', 'plan']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'plan', 'description', 'is_active')
        }),
        ('Pricing', {
            'fields': ('price', 'currency', 'duration_days')
        }),
        ('Features', {
            'fields': ('max_clients', 'allowed_models', 'features')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def price_display(self, obj):
        return obj.get_price_display()
    price_display.short_description = 'Price'

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user_email', 'pricing_plan_name', 'amount_display',
        'status_colored', 'provider_display', 'created_at'
    ]
    list_filter = [
        'status', 'currency', 'payment_method__provider',
        'created_at', 'paid_at'
    ]
    search_fields = [
        'id', 'user__email', 'user__first_name', 'user__last_name',
        'provider_transaction_id', 'pricing_plan__name'
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'paid_at',
        'is_expired', 'user_link', 'pricing_plan_link'
    ]
    
    fieldsets = (
        ('Payment Information', {
            'fields': (
                'id', 'user_link', 'pricing_plan_link', 'payment_method',
                'amount', 'currency', 'status'
            )
        }),
        ('Provider Details', {
            'fields': (
                'provider_transaction_id', 'provider_payment_url',
                'provider_response'
            ),
            'classes': ('collapse',)
        }),
        ('Tracking', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'paid_at', 'expires_at', 'is_expired'),
            'classes': ('collapse',)
        })
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    
    def pricing_plan_name(self, obj):
        return obj.pricing_plan.name
    pricing_plan_name.short_description = 'Plan'
    
    def amount_display(self, obj):
        return obj.get_amount_display()
    amount_display.short_description = 'Amount'
    
    def status_colored(self, obj):
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray',
            'refunded': 'purple'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_status_display()
        )
    status_colored.short_description = 'Status'
    
    def provider_display(self, obj):
        return obj.payment_method.get_provider_display()
    provider_display.short_description = 'Provider'
    
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:accounts_user_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return '-'
    user_link.short_description = 'User'
    
    def pricing_plan_link(self, obj):
        if obj.pricing_plan:
            url = reverse('admin:payments_pricingplan_change', args=[obj.pricing_plan.pk])
            return format_html('<a href="{}">{}</a>', url, obj.pricing_plan.name)
        return '-'
    pricing_plan_link.short_description = 'Pricing Plan'
    
    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.boolean = True
    is_expired.short_description = 'Expired'

@admin.register(PaymentCallback)
class PaymentCallbackAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'payment_id', 'provider', 'is_processed',
        'received_at', 'processed_at'
    ]
    list_filter = ['provider', 'is_processed', 'received_at']
    search_fields = ['id', 'payment__id', 'payment__user__email']
    readonly_fields = [
        'id', 'payment_link', 'received_at', 'processed_at'
    ]
    
    fieldsets = (
        ('Callback Information', {
            'fields': ('id', 'payment_link', 'provider')
        }),
        ('Data', {
            'fields': ('callback_data', 'headers', 'ip_address')
        }),
        ('Processing', {
            'fields': ('is_processed', 'processing_result', 'received_at', 'processed_at')
        })
    )
    
    def payment_id(self, obj):
        return str(obj.payment.id)[:8] + '...'
    payment_id.short_description = 'Payment ID'
    
    def payment_link(self, obj):
        if obj.payment:
            url = reverse('admin:payments_payment_change', args=[obj.payment.pk])
            return format_html('<a href="{}">{}</a>', url, obj.payment.id)
        return '-'
    payment_link.short_description = 'Payment'

@admin.register(PaymentRefund)
class PaymentRefundAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'payment_id', 'user_email', 'amount_display',
        'status_colored', 'requested_by_email', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'processed_at']
    search_fields = [
        'id', 'payment__id', 'payment__user__email',
        'requested_by__email', 'approved_by__email'
    ]
    readonly_fields = [
        'id', 'payment_link', 'created_at', 'updated_at', 'processed_at'
    ]
    
    fieldsets = (
        ('Refund Information', {
            'fields': ('id', 'payment_link', 'amount', 'reason', 'status')
        }),
        ('Provider Details', {
            'fields': ('provider_refund_id', 'provider_response'),
            'classes': ('collapse',)
        }),
        ('Administration', {
            'fields': ('requested_by', 'approved_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'processed_at'),
            'classes': ('collapse',)
        })
    )
    
    def payment_id(self, obj):
        return str(obj.payment.id)[:8] + '...'
    payment_id.short_description = 'Payment ID'
    
    def user_email(self, obj):
        return obj.payment.user.email
    user_email.short_description = 'User Email'
    
    def amount_display(self, obj):
        return obj.get_amount_display()
    amount_display.short_description = 'Amount'
    
    def status_colored(self, obj):
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_status_display()
        )
    status_colored.short_description = 'Status'
    
    def requested_by_email(self, obj):
        return obj.requested_by.email if obj.requested_by else '-'
    requested_by_email.short_description = 'Requested By'
    
    def payment_link(self, obj):
        if obj.payment:
            url = reverse('admin:payments_payment_change', args=[obj.payment.pk])
            return format_html('<a href="{}">{}</a>', url, obj.payment.id)
        return '-'
    payment_link.short_description = 'Payment'

@admin.register(PaymentAnalytics)
class PaymentAnalyticsAdmin(admin.ModelAdmin):
    list_display = [
        'date', 'total_payments', 'successful_payments',
        'success_rate_display', 'total_amount', 'updated_at'
    ]
    list_filter = ['date', 'created_at']
    search_fields = ['date']
    readonly_fields = [
        'id', 'success_rate_display', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Date', {
            'fields': ('date',)
        }),
        ('Payment Statistics', {
            'fields': (
                'total_payments', 'successful_payments', 'failed_payments',
                'success_rate_display', 'total_amount'
            )
        }),
        ('Detailed Statistics', {
            'fields': ('provider_stats', 'plan_stats', 'currency_stats'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def success_rate_display(self, obj):
        if obj.total_payments > 0:
            rate = (obj.successful_payments / obj.total_payments) * 100
            return f"{rate:.1f}%"
        return "0%"
    success_rate_display.short_description = 'Success Rate'
    
    actions = ['update_analytics']
    
    def update_analytics(self, request, queryset):
        """Update analytics for selected dates"""
        updated_count = 0
        for analytics in queryset:
            analytics.update_daily_stats(analytics.date)
            updated_count += 1
            
        self.message_user(
            request,
            f"Successfully updated analytics for {updated_count} dates."
        )
    update_analytics.short_description = "Update selected analytics"

# Custom admin site configuration
admin.site.site_header = "TikTrue Payment Administration"
admin.site.site_title = "TikTrue Payments"
admin.site.index_title = "Payment Management"