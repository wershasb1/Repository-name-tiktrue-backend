from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Payment, PaymentStatus, PaymentAnalytics
from .utils import log_payment_event
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Payment)
def payment_status_changed(sender, instance, created, **kwargs):
    """Handle payment status changes"""
    if created:
        log_payment_event('created', instance)
        logger.info(f"New payment created: {instance.id}")
    else:
        # Check if status changed
        if hasattr(instance, '_original_status'):
            if instance._original_status != instance.status:
                log_payment_event('status_changed', instance, {
                    'old_status': instance._original_status,
                    'new_status': instance.status
                })
                
                # Handle specific status changes
                if instance.status == PaymentStatus.COMPLETED:
                    handle_payment_completed(instance)
                elif instance.status == PaymentStatus.FAILED:
                    handle_payment_failed(instance)

@receiver(pre_save, sender=Payment)
def store_original_status(sender, instance, **kwargs):
    """Store original status before save"""
    if instance.pk:
        try:
            original = Payment.objects.get(pk=instance.pk)
            instance._original_status = original.status
        except Payment.DoesNotExist:
            instance._original_status = None
    else:
        instance._original_status = None

def handle_payment_completed(payment):
    """Handle completed payment"""
    try:
        # Update user subscription
        payment.update_user_subscription()
        
        # Update daily analytics
        today = timezone.now().date()
        PaymentAnalytics.update_daily_stats(today)
        
        logger.info(f"Payment completed successfully: {payment.id}")
        
    except Exception as e:
        logger.error(f"Error handling completed payment {payment.id}: {e}")

def handle_payment_failed(payment):
    """Handle failed payment"""
    try:
        # Log failure reason
        log_payment_event('failed', payment, {
            'provider_response': payment.provider_response
        }, level='warning')
        
        # Update daily analytics
        today = timezone.now().date()
        PaymentAnalytics.update_daily_stats(today)
        
        logger.warning(f"Payment failed: {payment.id}")
        
    except Exception as e:
        logger.error(f"Error handling failed payment {payment.id}: {e}")

@receiver(post_save, sender=Payment)
def update_payment_analytics(sender, instance, created, **kwargs):
    """Update payment analytics when payment is saved"""
    if created or (hasattr(instance, '_original_status') and 
                   instance._original_status != instance.status):
        try:
            # Update analytics for payment date
            payment_date = instance.created_at.date()
            PaymentAnalytics.update_daily_stats(payment_date)
            
            # Also update today's analytics if different
            today = timezone.now().date()
            if payment_date != today:
                PaymentAnalytics.update_daily_stats(today)
                
        except Exception as e:
            logger.error(f"Error updating payment analytics: {e}")