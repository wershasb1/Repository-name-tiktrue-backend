"""
Stripe Service Module for TikTrue Payment Integration

This module provides utilities for integrating with Stripe payment processing,
including subscription management, payment processing, and webhook handling.
"""

import stripe
import logging
from django.conf import settings
from django.utils import timezone
from typing import Dict, Any, Optional, Tuple
from .models import SubscriptionPlan, Subscription, Payment, WebhookEvent, Invoice

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)

class StripeService:
    """Service class for Stripe operations"""
    
    @staticmethod
    def create_customer(user) -> Optional[stripe.Customer]:
        """Create a Stripe customer for a user"""
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.get_full_name() or user.username,
                metadata={
                    'user_id': str(user.id),
                    'username': user.username,
                }
            )
            logger.info(f"Created Stripe customer {customer.id} for user {user.email}")
            return customer
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe customer for user {user.email}: {e}")
            return None
    
    @staticmethod
    def create_checkout_session(user, plan: SubscriptionPlan, billing_cycle: str, 
                              success_url: str, cancel_url: str) -> Optional[stripe.checkout.Session]:
        """Create a Stripe checkout session for subscription"""
        try:
            # Get or create Stripe customer
            subscription = getattr(user, 'subscription', None)
            if subscription and subscription.stripe_customer_id:
                customer_id = subscription.stripe_customer_id
            else:
                customer = StripeService.create_customer(user)
                if not customer:
                    return None
                customer_id = customer.id
            
            # Get the appropriate price ID
            if billing_cycle == 'yearly':
                price_id = plan.stripe_price_id_yearly
            else:
                price_id = plan.stripe_price_id_monthly
            
            if not price_id:
                logger.error(f"No Stripe price ID found for plan {plan.name} with billing cycle {billing_cycle}")
                return None
            
            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'user_id': str(user.id),
                    'plan_name': plan.name,
                    'billing_cycle': billing_cycle,
                }
            )
            
            logger.info(f"Created checkout session {session.id} for user {user.email}")
            return session
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create checkout session for user {user.email}: {e}")
            return None
    
    @staticmethod
    def create_billing_portal_session(customer_id: str, return_url: str) -> Optional[stripe.billing_portal.Session]:
        """Create a Stripe billing portal session"""
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
            logger.info(f"Created billing portal session for customer {customer_id}")
            return session
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create billing portal session for customer {customer_id}: {e}")
            return None
    
    @staticmethod
    def get_subscription(subscription_id: str) -> Optional[stripe.Subscription]:
        """Get a Stripe subscription by ID"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve subscription {subscription_id}: {e}")
            return None
    
    @staticmethod
    def cancel_subscription(subscription_id: str) -> Optional[stripe.Subscription]:
        """Cancel a Stripe subscription"""
        try:
            subscription = stripe.Subscription.delete(subscription_id)
            logger.info(f"Canceled subscription {subscription_id}")
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription {subscription_id}: {e}")
            return None
    
    @staticmethod
    def update_subscription(subscription_id: str, new_price_id: str) -> Optional[stripe.Subscription]:
        """Update a Stripe subscription to a new price"""
        try:
            # Get current subscription
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Update subscription
            updated_subscription = stripe.Subscription.modify(
                subscription_id,
                items=[{
                    'id': subscription['items']['data'][0].id,
                    'price': new_price_id,
                }]
            )
            
            logger.info(f"Updated subscription {subscription_id} to price {new_price_id}")
            return updated_subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to update subscription {subscription_id}: {e}")
            return None
    
    @staticmethod
    def construct_webhook_event(payload: bytes, sig_header: str) -> Optional[stripe.Event]:
        """Construct and verify a Stripe webhook event"""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
            return event
        except ValueError as e:
            logger.error(f"Invalid payload in webhook: {e}")
            return None
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid signature in webhook: {e}")
            return None

class SubscriptionManager:
    """Manager class for subscription operations"""
    
    @staticmethod
    def sync_subscription_from_stripe(stripe_subscription: stripe.Subscription) -> Optional[Subscription]:
        """Sync subscription data from Stripe to local database"""
        try:
            # Get user from metadata
            user_id = stripe_subscription.metadata.get('user_id')
            if not user_id:
                logger.error(f"No user_id in subscription metadata: {stripe_subscription.id}")
                return None
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.error(f"User {user_id} not found for subscription {stripe_subscription.id}")
                return None
            
            # Get plan from metadata
            plan_name = stripe_subscription.metadata.get('plan_name')
            if not plan_name:
                logger.error(f"No plan_name in subscription metadata: {stripe_subscription.id}")
                return None
            
            try:
                plan = SubscriptionPlan.objects.get(name=plan_name)
            except SubscriptionPlan.DoesNotExist:
                logger.error(f"Plan {plan_name} not found for subscription {stripe_subscription.id}")
                return None
            
            # Get or create subscription
            subscription, created = Subscription.objects.get_or_create(
                user=user,
                defaults={
                    'plan': plan,
                    'stripe_subscription_id': stripe_subscription.id,
                    'stripe_customer_id': stripe_subscription.customer,
                }
            )
            
            # Update subscription data
            subscription.plan = plan
            subscription.stripe_subscription_id = stripe_subscription.id
            subscription.stripe_customer_id = stripe_subscription.customer
            subscription.status = stripe_subscription.status
            
            # Update period information
            if stripe_subscription.current_period_start:
                subscription.current_period_start = timezone.datetime.fromtimestamp(
                    stripe_subscription.current_period_start, tz=timezone.utc
                )
            
            if stripe_subscription.current_period_end:
                subscription.current_period_end = timezone.datetime.fromtimestamp(
                    stripe_subscription.current_period_end, tz=timezone.utc
                )
            
            # Update trial information
            if stripe_subscription.trial_start:
                subscription.trial_start = timezone.datetime.fromtimestamp(
                    stripe_subscription.trial_start, tz=timezone.utc
                )
            
            if stripe_subscription.trial_end:
                subscription.trial_end = timezone.datetime.fromtimestamp(
                    stripe_subscription.trial_end, tz=timezone.utc
                )
            
            # Update canceled information
            if stripe_subscription.canceled_at:
                subscription.canceled_at = timezone.datetime.fromtimestamp(
                    stripe_subscription.canceled_at, tz=timezone.utc
                )
            
            subscription.save()
            
            # Update user subscription plan
            user.subscription_plan = plan.name
            if subscription.current_period_end:
                user.subscription_expires = subscription.current_period_end
            user.max_clients = plan.max_clients
            user.allowed_models = plan.allowed_models
            user.save()
            
            logger.info(f"Synced subscription {subscription.id} for user {user.email}")
            return subscription
            
        except Exception as e:
            logger.error(f"Failed to sync subscription from Stripe: {e}")
            return None
    
    @staticmethod
    def handle_subscription_created(stripe_subscription: stripe.Subscription) -> bool:
        """Handle subscription.created webhook event"""
        subscription = SubscriptionManager.sync_subscription_from_stripe(stripe_subscription)
        return subscription is not None
    
    @staticmethod
    def handle_subscription_updated(stripe_subscription: stripe.Subscription) -> bool:
        """Handle subscription.updated webhook event"""
        subscription = SubscriptionManager.sync_subscription_from_stripe(stripe_subscription)
        return subscription is not None
    
    @staticmethod
    def handle_subscription_deleted(stripe_subscription: stripe.Subscription) -> bool:
        """Handle subscription.deleted webhook event"""
        try:
            subscription = Subscription.objects.get(
                stripe_subscription_id=stripe_subscription.id
            )
            
            # Update subscription status
            subscription.status = 'canceled'
            subscription.canceled_at = timezone.now()
            subscription.save()
            
            # Update user to free plan
            user = subscription.user
            free_plan = SubscriptionPlan.objects.get(name='free')
            user.subscription_plan = 'free'
            user.subscription_expires = None
            user.max_clients = free_plan.max_clients
            user.allowed_models = free_plan.allowed_models
            user.save()
            
            logger.info(f"Handled subscription deletion for user {user.email}")
            return True
            
        except Subscription.DoesNotExist:
            logger.error(f"Subscription {stripe_subscription.id} not found in database")
            return False
        except Exception as e:
            logger.error(f"Failed to handle subscription deletion: {e}")
            return False

class PaymentManager:
    """Manager class for payment operations"""
    
    @staticmethod
    def handle_payment_succeeded(stripe_payment_intent: stripe.PaymentIntent) -> bool:
        """Handle payment_intent.succeeded webhook event"""
        try:
            # Get user from metadata
            user_id = stripe_payment_intent.metadata.get('user_id')
            if not user_id:
                logger.error(f"No user_id in payment intent metadata: {stripe_payment_intent.id}")
                return False
            
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                logger.error(f"User {user_id} not found for payment intent {stripe_payment_intent.id}")
                return False
            
            # Create or update payment record
            payment, created = Payment.objects.get_or_create(
                stripe_payment_intent_id=stripe_payment_intent.id,
                defaults={
                    'user': user,
                    'amount': stripe_payment_intent.amount / 100,  # Convert from cents
                    'currency': stripe_payment_intent.currency.upper(),
                    'status': 'succeeded',
                    'description': stripe_payment_intent.description or '',
                    'metadata': stripe_payment_intent.metadata or {},
                }
            )
            
            if not created:
                payment.status = 'succeeded'
                payment.save()
            
            logger.info(f"Handled successful payment {payment.id} for user {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle payment success: {e}")
            return False
    
    @staticmethod
    def handle_payment_failed(stripe_payment_intent: stripe.PaymentIntent) -> bool:
        """Handle payment_intent.payment_failed webhook event"""
        try:
            # Update payment record if exists
            try:
                payment = Payment.objects.get(
                    stripe_payment_intent_id=stripe_payment_intent.id
                )
                payment.status = 'failed'
                payment.save()
                
                logger.info(f"Handled failed payment {payment.id}")
                return True
                
            except Payment.DoesNotExist:
                logger.warning(f"Payment record not found for failed payment intent {stripe_payment_intent.id}")
                return True  # Not an error, just no record to update
                
        except Exception as e:
            logger.error(f"Failed to handle payment failure: {e}")
            return False

class WebhookManager:
    """Manager class for webhook operations"""
    
    @staticmethod
    def process_webhook_event(event: stripe.Event) -> bool:
        """Process a Stripe webhook event"""
        try:
            # Check if event was already processed
            webhook_event, created = WebhookEvent.objects.get_or_create(
                stripe_event_id=event.id,
                defaults={
                    'event_type': event.type,
                    'data': event.data,
                }
            )
            
            if not created and webhook_event.processed:
                logger.info(f"Webhook event {event.id} already processed")
                return True
            
            # Process event based on type
            success = False
            
            if event.type == 'customer.subscription.created':
                success = SubscriptionManager.handle_subscription_created(event.data.object)
            elif event.type == 'customer.subscription.updated':
                success = SubscriptionManager.handle_subscription_updated(event.data.object)
            elif event.type == 'customer.subscription.deleted':
                success = SubscriptionManager.handle_subscription_deleted(event.data.object)
            elif event.type == 'payment_intent.succeeded':
                success = PaymentManager.handle_payment_succeeded(event.data.object)
            elif event.type == 'payment_intent.payment_failed':
                success = PaymentManager.handle_payment_failed(event.data.object)
            else:
                logger.info(f"Unhandled webhook event type: {event.type}")
                success = True  # Not an error, just unhandled
            
            # Update webhook event record
            webhook_event.processed = success
            if success:
                webhook_event.processed_at = timezone.now()
            else:
                webhook_event.processing_error = f"Failed to process {event.type} event"
            webhook_event.save()
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to process webhook event {event.id}: {e}")
            return False