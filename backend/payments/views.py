from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Sum, Count, Q, Avg
from django.http import HttpResponse
from datetime import datetime, timedelta
import json
import logging

from .models import (
    PaymentMethod, PricingPlan, Payment, PaymentCallback,
    PaymentRefund, PaymentAnalytics, PaymentStatus, PaymentProvider
)
from .serializers import (
    PaymentMethodSerializer, PricingPlanSerializer, PaymentCreateSerializer,
    PaymentSerializer, PaymentListSerializer, PaymentCallbackSerializer,
    PaymentRefundSerializer, PaymentAnalyticsSerializer,
    UserSubscriptionSerializer, PaymentStatsSerializer
)
from .payment_processors import PaymentProcessorFactory
from .utils import get_client_ip, get_user_agent

logger = logging.getLogger(__name__)

class PaymentMethodListView(generics.ListAPIView):
    """List available payment methods"""
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return PaymentMethod.objects.filter(is_active=True)

class PricingPlanListView(generics.ListAPIView):
    """List available pricing plans"""
    serializer_class = PricingPlanSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return PricingPlan.objects.filter(is_active=True)

class CreatePaymentView(generics.CreateAPIView):
    """Create a new payment"""
    serializer_class = PaymentCreateSerializer
    permission_classes = [IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create payment
        payment = serializer.save()
        
        try:
            # Initialize payment with provider
            processor = PaymentProcessorFactory.get_processor(
                payment.payment_method.provider
            )
            
            # Initialize payment with provider
            payment_url, transaction_id = processor.initialize_payment(
                payment=payment,
                return_url=request.build_absolute_uri('/api/v1/payments/callback/'),
                cancel_url=request.build_absolute_uri('/api/v1/payments/cancel/')
            )
            
            # Update payment with provider details
            payment.provider_payment_url = payment_url
            payment.provider_transaction_id = transaction_id
            payment.status = PaymentStatus.PROCESSING
            payment.save()
            
            # Return payment details with redirect URL
            response_serializer = PaymentSerializer(payment)
            return Response({
                'payment': response_serializer.data,
                'redirect_url': payment_url,
                'message': 'Payment initialized successfully'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Payment initialization failed: {e}")
            payment.status = PaymentStatus.FAILED
            payment.save()
            
            return Response({
                'error': 'Payment initialization failed',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

class PaymentDetailView(generics.RetrieveAPIView):
    """Get payment details"""
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)

class PaymentListView(generics.ListAPIView):
    """List user's payments"""
    serializer_class = PaymentListSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_payment(request, payment_id):
    """Verify payment status with provider"""
    try:
        payment = get_object_or_404(Payment, id=payment_id, user=request.user)
        
        if payment.status == PaymentStatus.COMPLETED:
            return Response({
                'verified': True,
                'status': payment.status,
                'message': 'Payment already completed'
            })
            
        # Verify with payment provider
        processor = PaymentProcessorFactory.get_processor(
            payment.payment_method.provider
        )
        
        is_verified, provider_response = processor.verify_payment(payment)
        
        if is_verified:
            payment.mark_as_paid()
            payment.provider_response = provider_response
            payment.save()
            
            return Response({
                'verified': True,
                'status': payment.status,
                'message': 'Payment verified successfully'
            })
        else:
            payment.status = PaymentStatus.FAILED
            payment.provider_response = provider_response
            payment.save()
            
            return Response({
                'verified': False,
                'status': payment.status,
                'message': 'Payment verification failed'
            })
            
    except Exception as e:
        logger.error(f"Payment verification failed: {e}")
        return Response({
            'error': 'Payment verification failed',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST', 'GET'])
def payment_callback(request):
    """Handle payment provider callbacks/webhooks"""
    try:
        # Determine provider from request
        provider = request.GET.get('provider') or request.POST.get('provider')
        
        if not provider:
            # Try to determine from callback data
            callback_data = request.POST.dict() if request.method == 'POST' else request.GET.dict()
            provider = determine_provider_from_callback(callback_data)
            
        if not provider:
            logger.error("Could not determine payment provider from callback")
            return HttpResponse("Invalid callback", status=400)
            
        # Get payment from callback data
        processor = PaymentProcessorFactory.get_processor(provider)
        payment = processor.get_payment_from_callback(request)
        
        if not payment:
            logger.error("Could not find payment from callback data")
            return HttpResponse("Payment not found", status=404)
            
        # Create callback record
        callback = PaymentCallback.objects.create(
            payment=payment,
            provider=provider,
            callback_data=request.POST.dict() if request.method == 'POST' else request.GET.dict(),
            headers=dict(request.headers),
            ip_address=get_client_ip(request)
        )
        
        # Process callback
        try:
            is_success, result_message = processor.process_callback(request, payment)
            
            if is_success:
                payment.mark_as_paid()
                callback.mark_as_processed("Payment completed successfully")
                logger.info(f"Payment {payment.id} completed via callback")
            else:
                payment.status = PaymentStatus.FAILED
                payment.save()
                callback.mark_as_processed(f"Payment failed: {result_message}")
                logger.warning(f"Payment {payment.id} failed via callback: {result_message}")
                
        except Exception as e:
            callback.mark_as_processed(f"Callback processing error: {str(e)}")
            logger.error(f"Callback processing error: {e}")
            
        return HttpResponse("OK", status=200)
        
    except Exception as e:
        logger.error(f"Payment callback error: {e}")
        return HttpResponse("Error", status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_cancel(request):
    """Handle payment cancellation"""
    payment_id = request.GET.get('payment_id')
    
    if payment_id:
        try:
            payment = Payment.objects.get(id=payment_id, user=request.user)
            if payment.status == PaymentStatus.PROCESSING:
                payment.status = PaymentStatus.CANCELLED
                payment.save()
                
            return Response({
                'message': 'Payment cancelled',
                'payment_id': payment_id
            })
        except Payment.DoesNotExist:
            pass
            
    return Response({
        'message': 'Payment cancellation processed'
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_subscription(request):
    """Get user's current subscription information"""
    serializer = UserSubscriptionSerializer(request.user)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_refund(request, payment_id):
    """Request a refund for a payment"""
    try:
        payment = get_object_or_404(Payment, id=payment_id, user=request.user)
        
        if payment.status != PaymentStatus.COMPLETED:
            return Response({
                'error': 'Only completed payments can be refunded'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Check if refund already exists
        if payment.refunds.exists():
            return Response({
                'error': 'Refund already requested for this payment'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        reason = request.data.get('reason', '')
        if not reason:
            return Response({
                'error': 'Refund reason is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Create refund request
        refund = PaymentRefund.objects.create(
            payment=payment,
            amount=payment.amount,
            reason=reason,
            requested_by=request.user
        )
        
        serializer = PaymentRefundSerializer(refund)
        return Response({
            'refund': serializer.data,
            'message': 'Refund request submitted successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Refund request failed: {e}")
        return Response({
            'error': 'Refund request failed',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

# Admin Views

class AdminPaymentListView(generics.ListAPIView):
    """Admin view for all payments"""
    serializer_class = PaymentSerializer
    permission_classes = [IsAdminUser]
    queryset = Payment.objects.all()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        # Filter by provider
        provider_filter = self.request.query_params.get('provider')
        if provider_filter:
            queryset = queryset.filter(payment_method__provider=provider_filter)
            
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
            
        return queryset.order_by('-created_at')

class AdminRefundListView(generics.ListAPIView):
    """Admin view for refund requests"""
    serializer_class = PaymentRefundSerializer
    permission_classes = [IsAdminUser]
    queryset = PaymentRefund.objects.all()

@api_view(['POST'])
@permission_classes([IsAdminUser])
def approve_refund(request, refund_id):
    """Approve a refund request"""
    try:
        refund = get_object_or_404(PaymentRefund, id=refund_id)
        
        if refund.status != PaymentStatus.PENDING:
            return Response({
                'error': 'Only pending refunds can be approved'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Process refund with payment provider
        processor = PaymentProcessorFactory.get_processor(
            refund.payment.payment_method.provider
        )
        
        is_success, provider_response = processor.process_refund(refund)
        
        if is_success:
            refund.status = PaymentStatus.COMPLETED
            refund.approved_by = request.user
            refund.processed_at = timezone.now()
            refund.provider_response = provider_response
            refund.save()
            
            return Response({
                'message': 'Refund approved and processed successfully'
            })
        else:
            refund.status = PaymentStatus.FAILED
            refund.provider_response = provider_response
            refund.save()
            
            return Response({
                'error': 'Refund processing failed',
                'message': provider_response.get('message', 'Unknown error')
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Refund approval failed: {e}")
        return Response({
            'error': 'Refund approval failed',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def payment_analytics(request):
    """Get payment analytics and statistics"""
    try:
        # Date range
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if not date_from:
            date_from = (timezone.now() - timedelta(days=30)).date()
        else:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            
        if not date_to:
            date_to = timezone.now().date()
        else:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            
        # Get analytics data
        analytics = PaymentAnalytics.objects.filter(
            date__range=[date_from, date_to]
        ).order_by('-date')
        
        # Calculate summary statistics
        payments = Payment.objects.filter(
            created_at__date__range=[date_from, date_to]
        )
        
        total_payments = payments.count()
        successful_payments = payments.filter(status=PaymentStatus.COMPLETED).count()
        failed_payments = payments.filter(status=PaymentStatus.FAILED).count()
        pending_payments = payments.filter(status=PaymentStatus.PENDING).count()
        
        total_revenue = payments.filter(status=PaymentStatus.COMPLETED).aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        success_rate = (successful_payments / total_payments * 100) if total_payments > 0 else 0
        
        average_payment = payments.filter(status=PaymentStatus.COMPLETED).aggregate(
            avg=Avg('amount')
        )['avg'] or 0
        
        # Time-based stats
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        today_payments = payments.filter(created_at__date=today).count()
        this_week_payments = payments.filter(created_at__date__gte=week_ago).count()
        this_month_payments = payments.filter(created_at__date__gte=month_ago).count()
        
        # Provider breakdown
        provider_breakdown = {}
        for provider in PaymentProvider.choices:
            provider_code = provider[0]
            provider_payments = payments.filter(payment_method__provider=provider_code)
            provider_breakdown[provider_code] = {
                'total': provider_payments.count(),
                'successful': provider_payments.filter(status=PaymentStatus.COMPLETED).count(),
                'revenue': float(provider_payments.filter(status=PaymentStatus.COMPLETED).aggregate(
                    total=Sum('amount')
                )['total'] or 0)
            }
            
        # Plan breakdown
        plan_breakdown = {}
        for plan in ['free', 'pro', 'enterprise']:
            plan_payments = payments.filter(pricing_plan__plan=plan)
            plan_breakdown[plan] = {
                'total': plan_payments.count(),
                'successful': plan_payments.filter(status=PaymentStatus.COMPLETED).count(),
                'revenue': float(plan_payments.filter(status=PaymentStatus.COMPLETED).aggregate(
                    total=Sum('amount')
                )['total'] or 0)
            }
            
        # Currency breakdown
        currency_breakdown = {}
        for currency in ['USD', 'EUR', 'IRR', 'TOMAN']:
            currency_payments = payments.filter(currency=currency)
            currency_breakdown[currency] = {
                'total': currency_payments.count(),
                'successful': currency_payments.filter(status=PaymentStatus.COMPLETED).count(),
                'revenue': float(currency_payments.filter(status=PaymentStatus.COMPLETED).aggregate(
                    total=Sum('amount')
                )['total'] or 0)
            }
            
        stats_data = {
            'total_payments': total_payments,
            'successful_payments': successful_payments,
            'failed_payments': failed_payments,
            'pending_payments': pending_payments,
            'total_revenue': total_revenue,
            'success_rate': round(success_rate, 2),
            'average_payment_amount': round(average_payment, 2),
            'today_payments': today_payments,
            'this_week_payments': this_week_payments,
            'this_month_payments': this_month_payments,
            'provider_breakdown': provider_breakdown,
            'plan_breakdown': plan_breakdown,
            'currency_breakdown': currency_breakdown
        }
        
        stats_serializer = PaymentStatsSerializer(stats_data)
        analytics_serializer = PaymentAnalyticsSerializer(analytics, many=True)
        
        return Response({
            'summary': stats_serializer.data,
            'daily_analytics': analytics_serializer.data,
            'date_range': {
                'from': date_from,
                'to': date_to
            }
        })
        
    except Exception as e:
        logger.error(f"Payment analytics failed: {e}")
        return Response({
            'error': 'Failed to get payment analytics',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

# Utility functions

def determine_provider_from_callback(callback_data):
    """Determine payment provider from callback data"""
    # ZarinPal
    if 'Authority' in callback_data or 'Status' in callback_data:
        return PaymentProvider.ZARINPAL
        
    # IDPay
    if 'id' in callback_data and 'order_id' in callback_data:
        return PaymentProvider.IDPAY
        
    # NextPay
    if 'trans_id' in callback_data and 'order_id' in callback_data:
        return PaymentProvider.NEXTPAY
        
    # Stripe
    if 'payment_intent' in callback_data or 'session_id' in callback_data:
        return PaymentProvider.STRIPE
        
    # PayPal
    if 'paymentId' in callback_data or 'PayerID' in callback_data:
        return PaymentProvider.PAYPAL
        
    return None