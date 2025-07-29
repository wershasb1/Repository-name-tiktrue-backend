from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'payments'

# API URLs
urlpatterns = [
    # Public endpoints
    path('methods/', views.PaymentMethodListView.as_view(), name='payment-methods'),
    path('plans/', views.PricingPlanListView.as_view(), name='pricing-plans'),
    
    # Payment management
    path('create/', views.CreatePaymentView.as_view(), name='create-payment'),
    path('<uuid:pk>/', views.PaymentDetailView.as_view(), name='payment-detail'),
    path('list/', views.PaymentListView.as_view(), name='payment-list'),
    path('<uuid:payment_id>/verify/', views.verify_payment, name='verify-payment'),
    
    # Payment callbacks
    path('callback/', views.payment_callback, name='payment-callback'),
    path('cancel/', views.payment_cancel, name='payment-cancel'),
    
    # User subscription
    path('subscription/', views.user_subscription, name='user-subscription'),
    
    # Refunds
    path('<uuid:payment_id>/refund/', views.request_refund, name='request-refund'),
    
    # Admin endpoints
    path('admin/payments/', views.AdminPaymentListView.as_view(), name='admin-payments'),
    path('admin/refunds/', views.AdminRefundListView.as_view(), name='admin-refunds'),
    path('admin/refunds/<uuid:refund_id>/approve/', views.approve_refund, name='approve-refund'),
    path('admin/analytics/', views.payment_analytics, name='payment-analytics'),
]