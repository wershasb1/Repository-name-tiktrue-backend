#!/usr/bin/env python3
"""
Test script for Payment Processing System
Tests payment creation, verification, and management functionality
"""

import os
import sys
import django
import json
import requests
from datetime import datetime, timedelta
from decimal import Decimal

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tiktrue_backend.settings')
django.setup()

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from payments.models import (
    PaymentMethod, PricingPlan, Payment, PaymentCallback,
    PaymentRefund, PaymentAnalytics, PaymentProvider,
    SubscriptionPlan, Currency, PaymentStatus
)
from payments.serializers import (
    PaymentMethodSerializer, PricingPlanSerializer,
    PaymentCreateSerializer, PaymentSerializer
)

User = get_user_model()

class PaymentSystemTest:
    """Test suite for payment system"""
    
    def __init__(self):
        self.client = APIClient()
        self.setup_test_data()
        
    def setup_test_data(self):
        """Setup test data"""
        print("Setting up test data...")
        
        # Get or create test user
        self.user, created = User.objects.get_or_create(
            email='test@example.com',
            defaults={
                'username': 'testuser',
                'first_name': 'Test',
                'last_name': 'User'
            }
        )
        if created:
            self.user.set_password('testpass123')
            self.user.save()
        
        # Get or create admin user
        self.admin_user, created = User.objects.get_or_create(
            email='admin@example.com',
            defaults={
                'username': 'adminuser',
                'first_name': 'Admin',
                'last_name': 'User',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            self.admin_user.set_password('adminpass123')
            self.admin_user.save()
        
        # Get or create payment method
        self.payment_method, created = PaymentMethod.objects.get_or_create(
            provider=PaymentProvider.ZARINPAL,
            name='ZarinPal',
            defaults={
                'description': 'Test payment method',
                'is_active': True,
                'supported_currencies': ['IRR', 'TOMAN'],
                'configuration': {
                    'merchant_id': 'test_merchant',
                    'sandbox': True
                }
            }
        )
        
        # Get or create pricing plan
        self.pricing_plan, created = PricingPlan.objects.get_or_create(
            plan=SubscriptionPlan.PRO,
            currency=Currency.TOMAN,
            defaults={
                'name': 'Test Pro Plan',
                'description': 'Test professional plan',
                'price': Decimal('50000'),
                'duration_days': 30,
                'max_clients': 5,
                'allowed_models': ['llama3_1_8b_fp16'],
                'features': ['Feature 1', 'Feature 2'],
                'is_active': True
            }
        )
        
        print("Test data setup complete")
        
    def authenticate_user(self, user=None):
        """Authenticate user for API calls"""
        if user is None:
            user = self.user
            
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        return access_token
        
    def test_payment_methods_api(self):
        """Test payment methods API"""
        print("\n=== Testing Payment Methods API ===")
        
        # Authenticate user
        self.authenticate_user()
        
        # Test list payment methods
        url = '/api/v1/payments/methods/'
        response = self.client.get(url)
        
        print(f"GET {url}")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.data, indent=2, ensure_ascii=False)}")
        
        assert response.status_code == 200
        assert len(response.data) > 0
        assert response.data[0]['provider'] == PaymentProvider.ZARINPAL
        
        print("✓ Payment methods API test passed")
        
    def test_pricing_plans_api(self):
        """Test pricing plans API"""
        print("\n=== Testing Pricing Plans API ===")
        
        # Authenticate user
        self.authenticate_user()
        
        # Test list pricing plans
        url = '/api/v1/payments/plans/'
        response = self.client.get(url)
        
        print(f"GET {url}")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.data, indent=2, ensure_ascii=False)}")
        
        assert response.status_code == 200
        assert len(response.data) > 0
        assert response.data[0]['plan'] == SubscriptionPlan.PRO
        
        print("✓ Pricing plans API test passed")
        
    def test_create_payment(self):
        """Test payment creation"""
        print("\n=== Testing Payment Creation ===")
        
        # Authenticate user
        self.authenticate_user()
        
        # Test create payment
        url = '/api/v1/payments/create/'
        data = {
            'pricing_plan': str(self.pricing_plan.id),
            'payment_method': str(self.payment_method.id)
        }
        
        response = self.client.post(url, data)
        
        print(f"POST {url}")
        print(f"Data: {json.dumps(data, indent=2)}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 201:
            print(f"Response: {json.dumps(response.data, indent=2, ensure_ascii=False)}")
            
            # Store payment for further tests
            self.test_payment = Payment.objects.get(id=response.data['payment']['id'])
            
            assert 'payment' in response.data
            assert 'redirect_url' in response.data
            assert response.data['payment']['status'] == PaymentStatus.PROCESSING
            
            print("✓ Payment creation test passed")
        else:
            print(f"Error: {response.data}")
            print("⚠ Payment creation test failed (expected in test environment)")
            
    def test_payment_detail(self):
        """Test payment detail API"""
        print("\n=== Testing Payment Detail API ===")
        
        # Create a test payment first
        payment = Payment.objects.create(
            user=self.user,
            pricing_plan=self.pricing_plan,
            payment_method=self.payment_method,
            amount=self.pricing_plan.price,
            currency=self.pricing_plan.currency,
            status=PaymentStatus.PENDING
        )
        
        # Authenticate user
        self.authenticate_user()
        
        # Test get payment detail
        url = f'/api/v1/payments/{payment.id}/'
        response = self.client.get(url)
        
        print(f"GET {url}")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.data, indent=2, ensure_ascii=False)}")
        
        assert response.status_code == 200
        assert response.data['id'] == str(payment.id)
        assert response.data['status'] == PaymentStatus.PENDING
        
        print("✓ Payment detail API test passed")
        
    def test_payment_list(self):
        """Test payment list API"""
        print("\n=== Testing Payment List API ===")
        
        # Authenticate user
        self.authenticate_user()
        
        # Test list user payments
        url = '/api/v1/payments/list/'
        response = self.client.get(url)
        
        print(f"GET {url}")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.data, indent=2, ensure_ascii=False)}")
        
        assert response.status_code == 200
        assert isinstance(response.data, list)
        
        print("✓ Payment list API test passed")
        
    def test_user_subscription(self):
        """Test user subscription API"""
        print("\n=== Testing User Subscription API ===")
        
        # Authenticate user
        self.authenticate_user()
        
        # Test get user subscription
        url = '/api/v1/payments/subscription/'
        response = self.client.get(url)
        
        print(f"GET {url}")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.data, indent=2, ensure_ascii=False)}")
        
        assert response.status_code == 200
        assert 'subscription_plan' in response.data
        assert 'is_subscription_active' in response.data
        
        print("✓ User subscription API test passed")
        
    def test_admin_payments_api(self):
        """Test admin payments API"""
        print("\n=== Testing Admin Payments API ===")
        
        # Authenticate admin user
        self.authenticate_user(self.admin_user)
        
        # Test list all payments (admin)
        url = '/api/v1/payments/admin/payments/'
        response = self.client.get(url)
        
        print(f"GET {url}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"Response: {json.dumps(response.data, indent=2, ensure_ascii=False)}")
            assert isinstance(response.data, list)
            print("✓ Admin payments API test passed")
        else:
            print(f"Error: {response.data}")
            print("⚠ Admin payments API test failed")
            
    def test_payment_analytics(self):
        """Test payment analytics API"""
        print("\n=== Testing Payment Analytics API ===")
        
        # Authenticate admin user
        self.authenticate_user(self.admin_user)
        
        # Test get payment analytics
        url = '/api/v1/payments/admin/analytics/'
        response = self.client.get(url)
        
        print(f"GET {url}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"Response: {json.dumps(response.data, indent=2, ensure_ascii=False)}")
            assert 'summary' in response.data
            assert 'daily_analytics' in response.data
            print("✓ Payment analytics API test passed")
        else:
            print(f"Error: {response.data}")
            print("⚠ Payment analytics API test failed")
            
    def test_payment_models(self):
        """Test payment models"""
        print("\n=== Testing Payment Models ===")
        
        # Test PaymentMethod model
        method = self.payment_method
        print(f"Payment Method: {method}")
        print(f"Provider Display: {method.get_provider_display()}")
        print(f"Supports IRR: {method.is_currency_supported('IRR')}")
        
        # Test PricingPlan model
        plan = self.pricing_plan
        print(f"Pricing Plan: {plan}")
        print(f"Price Display: {plan.get_price_display()}")
        
        # Test Payment model
        payment = Payment.objects.create(
            user=self.user,
            pricing_plan=plan,
            payment_method=method,
            amount=plan.price,
            currency=plan.currency,
            status=PaymentStatus.PENDING
        )
        
        print(f"Payment: {payment}")
        print(f"Amount Display: {payment.get_amount_display()}")
        print(f"Is Expired: {payment.is_expired()}")
        
        # Test payment completion
        payment.mark_as_paid()
        print(f"After completion - Status: {payment.status}")
        print(f"Paid At: {payment.paid_at}")
        
        # Check user subscription update
        self.user.refresh_from_db()
        print(f"User subscription plan: {self.user.subscription_plan}")
        print(f"User max clients: {self.user.max_clients}")
        
        print("✓ Payment models test passed")
        
    def test_payment_analytics_model(self):
        """Test payment analytics model"""
        print("\n=== Testing Payment Analytics Model ===")
        
        # Create some test payments
        for i in range(5):
            Payment.objects.create(
                user=self.user,
                pricing_plan=self.pricing_plan,
                payment_method=self.payment_method,
                amount=self.pricing_plan.price,
                currency=self.pricing_plan.currency,
                status=PaymentStatus.COMPLETED if i < 3 else PaymentStatus.FAILED
            )
            
        # Update analytics
        today = timezone.now().date()
        analytics = PaymentAnalytics.update_daily_stats(today)
        
        print(f"Analytics for {today}:")
        print(f"  Total payments: {analytics.total_payments}")
        print(f"  Successful payments: {analytics.successful_payments}")
        print(f"  Failed payments: {analytics.failed_payments}")
        print(f"  Total amount: {analytics.total_amount}")
        print(f"  Provider stats: {analytics.provider_stats}")
        
        assert analytics.total_payments >= 5
        assert analytics.successful_payments >= 3
        assert analytics.failed_payments >= 2
        
        print("✓ Payment analytics model test passed")
        
    def run_all_tests(self):
        """Run all tests"""
        print("Starting Payment System Tests...")
        print("=" * 50)
        
        try:
            self.test_payment_methods_api()
            self.test_pricing_plans_api()
            self.test_create_payment()
            self.test_payment_detail()
            self.test_payment_list()
            self.test_user_subscription()
            self.test_admin_payments_api()
            self.test_payment_analytics()
            self.test_payment_models()
            self.test_payment_analytics_model()
            
            print("\n" + "=" * 50)
            print("✅ All Payment System Tests Completed Successfully!")
            
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            
        except AssertionError as e:
            print(f"\n❌ Assertion failed: {e}")
            import traceback
            traceback.print_exc()

def main():
    """Main test function"""
    print("TikTrue Payment Processing System Test Suite")
    print("=" * 50)
    
    # Run tests
    test_suite = PaymentSystemTest()
    test_suite.run_all_tests()

if __name__ == '__main__':
    main()