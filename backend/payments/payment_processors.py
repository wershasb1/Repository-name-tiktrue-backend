from abc import ABC, abstractmethod
import requests
import json
import hashlib
import hmac
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from .models import PaymentStatus, PaymentProvider
import logging

logger = logging.getLogger(__name__)

class BasePaymentProcessor(ABC):
    """Base class for payment processors"""
    
    def __init__(self, config):
        self.config = config
        
    @abstractmethod
    def initialize_payment(self, payment, return_url, cancel_url):
        """Initialize payment with provider"""
        pass
        
    @abstractmethod
    def verify_payment(self, payment):
        """Verify payment with provider"""
        pass
        
    @abstractmethod
    def process_callback(self, request, payment):
        """Process payment callback"""
        pass
        
    @abstractmethod
    def get_payment_from_callback(self, request):
        """Get payment object from callback data"""
        pass
        
    @abstractmethod
    def process_refund(self, refund):
        """Process refund with provider"""
        pass

class ZarinPalProcessor(BasePaymentProcessor):
    """ZarinPal payment processor for Iranian market"""
    
    def __init__(self, config):
        super().__init__(config)
        self.merchant_id = config.get('merchant_id')
        self.sandbox = config.get('sandbox', False)
        
        if self.sandbox:
            self.base_url = 'https://sandbox.zarinpal.com/pg/rest/WebGate/'
            self.payment_url = 'https://sandbox.zarinpal.com/pg/StartPay/'
        else:
            self.base_url = 'https://api.zarinpal.com/pg/rest/WebGate/'
            self.payment_url = 'https://www.zarinpal.com/pg/StartPay/'
            
    def initialize_payment(self, payment, return_url, cancel_url):
        """Initialize payment with ZarinPal"""
        try:
            # Convert amount to Rials if needed
            amount = int(payment.amount)
            if payment.currency == 'TOMAN':
                amount *= 10  # Convert Toman to Rial
                
            data = {
                'MerchantID': self.merchant_id,
                'Amount': amount,
                'Description': f'TikTrue {payment.pricing_plan.name} Subscription',
                'CallbackURL': return_url,
                'Email': payment.user.email,
                'Mobile': getattr(payment.user, 'phone', '')
            }
            
            response = requests.post(
                f'{self.base_url}PaymentRequest.json',
                json=data,
                timeout=30
            )
            
            result = response.json()
            
            if result['Status'] == 100:
                authority = result['Authority']
                payment_url = f'{self.payment_url}{authority}'
                return payment_url, authority
            else:
                raise Exception(f"ZarinPal error: {result.get('Status')} - {result.get('errors', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"ZarinPal initialization failed: {e}")
            raise
            
    def verify_payment(self, payment):
        """Verify payment with ZarinPal"""
        try:
            amount = int(payment.amount)
            if payment.currency == 'TOMAN':
                amount *= 10
                
            data = {
                'MerchantID': self.merchant_id,
                'Amount': amount,
                'Authority': payment.provider_transaction_id
            }
            
            response = requests.post(
                f'{self.base_url}PaymentVerification.json',
                json=data,
                timeout=30
            )
            
            result = response.json()
            
            if result['Status'] == 100 or result['Status'] == 101:
                return True, result
            else:
                return False, result
                
        except Exception as e:
            logger.error(f"ZarinPal verification failed: {e}")
            return False, {'error': str(e)}
            
    def process_callback(self, request, payment):
        """Process ZarinPal callback"""
        try:
            authority = request.GET.get('Authority') or request.POST.get('Authority')
            status = request.GET.get('Status') or request.POST.get('Status')
            
            if status == 'OK' and authority:
                is_verified, response = self.verify_payment(payment)
                return is_verified, response.get('message', 'Payment verified')
            else:
                return False, 'Payment cancelled or failed'
                
        except Exception as e:
            logger.error(f"ZarinPal callback processing failed: {e}")
            return False, str(e)
            
    def get_payment_from_callback(self, request):
        """Get payment from ZarinPal callback"""
        from .models import Payment
        
        authority = request.GET.get('Authority') or request.POST.get('Authority')
        if authority:
            try:
                return Payment.objects.get(provider_transaction_id=authority)
            except Payment.DoesNotExist:
                pass
        return None
        
    def process_refund(self, refund):
        """Process refund with ZarinPal"""
        # ZarinPal doesn't support automatic refunds via API
        # This would need to be handled manually
        return False, {'message': 'Manual refund required for ZarinPal'}

class IDPayProcessor(BasePaymentProcessor):
    """IDPay payment processor for Iranian market"""
    
    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.sandbox = config.get('sandbox', False)
        
        if self.sandbox:
            self.base_url = 'https://api.idpay.ir/v1.1/'
        else:
            self.base_url = 'https://api.idpay.ir/v1.1/'
            
    def initialize_payment(self, payment, return_url, cancel_url):
        """Initialize payment with IDPay"""
        try:
            # Convert amount to Rials if needed
            amount = int(payment.amount)
            if payment.currency == 'TOMAN':
                amount *= 10
                
            headers = {
                'X-API-KEY': self.api_key,
                'Content-Type': 'application/json'
            }
            
            data = {
                'order_id': str(payment.id),
                'amount': amount,
                'name': payment.user.get_full_name() or payment.user.email,
                'phone': getattr(payment.user, 'phone', ''),
                'mail': payment.user.email,
                'desc': f'TikTrue {payment.pricing_plan.name} Subscription',
                'callback': return_url
            }
            
            response = requests.post(
                f'{self.base_url}payment',
                json=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 201:
                result = response.json()
                payment_url = result['link']
                transaction_id = result['id']
                return payment_url, transaction_id
            else:
                error_data = response.json()
                raise Exception(f"IDPay error: {error_data.get('error_message', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"IDPay initialization failed: {e}")
            raise
            
    def verify_payment(self, payment):
        """Verify payment with IDPay"""
        try:
            headers = {
                'X-API-KEY': self.api_key,
                'Content-Type': 'application/json'
            }
            
            data = {
                'id': payment.provider_transaction_id,
                'order_id': str(payment.id)
            }
            
            response = requests.post(
                f'{self.base_url}payment/verify',
                json=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return True, result
            else:
                error_data = response.json()
                return False, error_data
                
        except Exception as e:
            logger.error(f"IDPay verification failed: {e}")
            return False, {'error': str(e)}
            
    def process_callback(self, request, payment):
        """Process IDPay callback"""
        try:
            status = request.POST.get('status')
            track_id = request.POST.get('track_id')
            
            if status == '200' and track_id:
                is_verified, response = self.verify_payment(payment)
                return is_verified, response.get('message', 'Payment verified')
            else:
                return False, 'Payment failed or cancelled'
                
        except Exception as e:
            logger.error(f"IDPay callback processing failed: {e}")
            return False, str(e)
            
    def get_payment_from_callback(self, request):
        """Get payment from IDPay callback"""
        from .models import Payment
        
        order_id = request.POST.get('order_id')
        if order_id:
            try:
                return Payment.objects.get(id=order_id)
            except Payment.DoesNotExist:
                pass
        return None
        
    def process_refund(self, refund):
        """Process refund with IDPay"""
        # IDPay supports refunds via API
        try:
            headers = {
                'X-API-KEY': self.api_key,
                'Content-Type': 'application/json'
            }
            
            data = {
                'id': refund.payment.provider_transaction_id,
                'amount': int(refund.amount)
            }
            
            response = requests.post(
                f'{self.base_url}payment/refund',
                json=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return True, result
            else:
                error_data = response.json()
                return False, error_data
                
        except Exception as e:
            logger.error(f"IDPay refund failed: {e}")
            return False, {'error': str(e)}

class PaymentProcessorFactory:
    """Factory class for payment processors"""
    
    _processors = {
        PaymentProvider.ZARINPAL: ZarinPalProcessor,
        PaymentProvider.IDPAY: IDPayProcessor,
    }
    
    @classmethod
    def get_processor(cls, provider):
        """Get payment processor instance"""
        if provider not in cls._processors:
            raise ValueError(f"Unsupported payment provider: {provider}")
            
        processor_class = cls._processors[provider]
        
        # Get configuration from settings
        config = getattr(settings, 'PAYMENT_PROCESSORS', {}).get(provider, {})
        
        return processor_class(config)
        
    @classmethod
    def register_processor(cls, provider, processor_class):
        """Register a new payment processor"""
        cls._processors[provider] = processor_class
        
    @classmethod
    def get_available_providers(cls):
        """Get list of available payment providers"""
        return list(cls._processors.keys())