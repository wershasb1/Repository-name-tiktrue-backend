from django.core.management.base import BaseCommand
from django.db import transaction
from payments.models import PaymentMethod, PricingPlan, PaymentProvider, SubscriptionPlan, Currency

class Command(BaseCommand):
    help = 'Setup initial payment methods and pricing plans'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset existing data before creating new data',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Resetting existing payment data...')
            PaymentMethod.objects.all().delete()
            PricingPlan.objects.all().delete()

        with transaction.atomic():
            self.create_payment_methods()
            self.create_pricing_plans()

        self.stdout.write(
            self.style.SUCCESS('Successfully setup payment data')
        )

    def create_payment_methods(self):
        """Create default payment methods"""
        self.stdout.write('Creating payment methods...')

        # ZarinPal for Iranian market
        zarinpal, created = PaymentMethod.objects.get_or_create(
            provider=PaymentProvider.ZARINPAL,
            name='ZarinPal',
            defaults={
                'description': 'درگاه پرداخت زرین‌پال برای کاربران ایرانی',
                'is_active': True,
                'supported_currencies': ['IRR', 'TOMAN'],
                'configuration': {
                    'merchant_id': 'YOUR_ZARINPAL_MERCHANT_ID',
                    'sandbox': True  # Set to False in production
                }
            }
        )
        if created:
            self.stdout.write(f'  Created: {zarinpal.name}')

        # IDPay for Iranian market
        idpay, created = PaymentMethod.objects.get_or_create(
            provider=PaymentProvider.IDPAY,
            name='IDPay',
            defaults={
                'description': 'درگاه پرداخت آیدی‌پی برای کاربران ایرانی',
                'is_active': True,
                'supported_currencies': ['IRR', 'TOMAN'],
                'configuration': {
                    'api_key': 'YOUR_IDPAY_API_KEY',
                    'sandbox': True  # Set to False in production
                }
            }
        )
        if created:
            self.stdout.write(f'  Created: {idpay.name}')

        # NextPay for Iranian market
        nextpay, created = PaymentMethod.objects.get_or_create(
            provider=PaymentProvider.NEXTPAY,
            name='NextPay',
            defaults={
                'description': 'درگاه پرداخت نکست‌پی برای کاربران ایرانی',
                'is_active': False,  # Disabled by default
                'supported_currencies': ['IRR', 'TOMAN'],
                'configuration': {
                    'api_key': 'YOUR_NEXTPAY_API_KEY',
                    'sandbox': True
                }
            }
        )
        if created:
            self.stdout.write(f'  Created: {nextpay.name}')

        # Stripe for international market
        stripe, created = PaymentMethod.objects.get_or_create(
            provider=PaymentProvider.STRIPE,
            name='Stripe',
            defaults={
                'description': 'International payment processing via Stripe',
                'is_active': True,
                'supported_currencies': ['USD', 'EUR'],
                'configuration': {
                    'publishable_key': 'YOUR_STRIPE_PUBLISHABLE_KEY',
                    'secret_key': 'YOUR_STRIPE_SECRET_KEY',
                    'webhook_secret': 'YOUR_STRIPE_WEBHOOK_SECRET'
                }
            }
        )
        if created:
            self.stdout.write(f'  Created: {stripe.name}')

        # PayPal for international market
        paypal, created = PaymentMethod.objects.get_or_create(
            provider=PaymentProvider.PAYPAL,
            name='PayPal',
            defaults={
                'description': 'International payment processing via PayPal',
                'is_active': True,
                'supported_currencies': ['USD', 'EUR'],
                'configuration': {
                    'client_id': 'YOUR_PAYPAL_CLIENT_ID',
                    'client_secret': 'YOUR_PAYPAL_CLIENT_SECRET',
                    'sandbox': True  # Set to False in production
                }
            }
        )
        if created:
            self.stdout.write(f'  Created: {paypal.name}')

    def create_pricing_plans(self):
        """Create default pricing plans"""
        self.stdout.write('Creating pricing plans...')

        # Free plan (Iranian market)
        free_irr, created = PricingPlan.objects.get_or_create(
            plan=SubscriptionPlan.FREE,
            currency=Currency.IRR,
            defaults={
                'name': 'رایگان',
                'description': 'پلن رایگان با امکانات محدود',
                'price': 0,
                'duration_days': 30,
                'max_clients': 1,
                'allowed_models': ['llama3_1_8b_fp16'],
                'features': [
                    'دسترسی به مدل‌های پایه',
                    'حداکثر 1 کلاینت',
                    'پشتیبانی محدود'
                ],
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'  Created: {free_irr.name}')

        # Pro plan (Iranian market)
        pro_irr, created = PricingPlan.objects.get_or_create(
            plan=SubscriptionPlan.PRO,
            currency=Currency.IRR,
            defaults={
                'name': 'حرفه‌ای',
                'description': 'پلن حرفه‌ای برای کاربران جدی',
                'price': 500000,  # 500,000 Rials
                'duration_days': 30,
                'max_clients': 5,
                'allowed_models': [
                    'llama3_1_8b_fp16',
                    'mistral_7b_int4'
                ],
                'features': [
                    'دسترسی به تمام مدل‌ها',
                    'حداکثر 5 کلاینت',
                    'پشتیبانی اولویت‌دار',
                    'آپدیت‌های منظم'
                ],
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'  Created: {pro_irr.name}')

        # Enterprise plan (Iranian market)
        enterprise_irr, created = PricingPlan.objects.get_or_create(
            plan=SubscriptionPlan.ENTERPRISE,
            currency=Currency.IRR,
            defaults={
                'name': 'سازمانی',
                'description': 'پلن سازمانی برای شرکت‌ها',
                'price': 2000000,  # 2,000,000 Rials
                'duration_days': 30,
                'max_clients': 50,
                'allowed_models': [
                    'llama3_1_8b_fp16',
                    'mistral_7b_int4',
                    'custom_models'
                ],
                'features': [
                    'دسترسی به تمام مدل‌ها',
                    'حداکثر 50 کلاینت',
                    'پشتیبانی 24/7',
                    'مدل‌های سفارشی',
                    'گزارش‌گیری پیشرفته'
                ],
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'  Created: {enterprise_irr.name}')

        # Pro plan (Toman)
        pro_toman, created = PricingPlan.objects.get_or_create(
            plan=SubscriptionPlan.PRO,
            currency=Currency.TOMAN,
            defaults={
                'name': 'حرفه‌ای',
                'description': 'پلن حرفه‌ای برای کاربران جدی',
                'price': 50000,  # 50,000 Toman
                'duration_days': 30,
                'max_clients': 5,
                'allowed_models': [
                    'llama3_1_8b_fp16',
                    'mistral_7b_int4'
                ],
                'features': [
                    'دسترسی به تمام مدل‌ها',
                    'حداکثر 5 کلاینت',
                    'پشتیبانی اولویت‌دار',
                    'آپدیت‌های منظم'
                ],
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'  Created: {pro_toman.name}')

        # International plans (USD)
        pro_usd, created = PricingPlan.objects.get_or_create(
            plan=SubscriptionPlan.PRO,
            currency=Currency.USD,
            defaults={
                'name': 'Pro',
                'description': 'Professional plan for serious users',
                'price': 19.99,
                'duration_days': 30,
                'max_clients': 5,
                'allowed_models': [
                    'llama3_1_8b_fp16',
                    'mistral_7b_int4'
                ],
                'features': [
                    'Access to all models',
                    'Up to 5 clients',
                    'Priority support',
                    'Regular updates'
                ],
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'  Created: {pro_usd.name}')

        enterprise_usd, created = PricingPlan.objects.get_or_create(
            plan=SubscriptionPlan.ENTERPRISE,
            currency=Currency.USD,
            defaults={
                'name': 'Enterprise',
                'description': 'Enterprise plan for organizations',
                'price': 99.99,
                'duration_days': 30,
                'max_clients': 50,
                'allowed_models': [
                    'llama3_1_8b_fp16',
                    'mistral_7b_int4',
                    'custom_models'
                ],
                'features': [
                    'Access to all models',
                    'Up to 50 clients',
                    '24/7 support',
                    'Custom models',
                    'Advanced analytics'
                ],
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'  Created: {enterprise_usd.name}')

        # International plans (EUR)
        pro_eur, created = PricingPlan.objects.get_or_create(
            plan=SubscriptionPlan.PRO,
            currency=Currency.EUR,
            defaults={
                'name': 'Pro',
                'description': 'Professional plan for serious users',
                'price': 17.99,
                'duration_days': 30,
                'max_clients': 5,
                'allowed_models': [
                    'llama3_1_8b_fp16',
                    'mistral_7b_int4'
                ],
                'features': [
                    'Access to all models',
                    'Up to 5 clients',
                    'Priority support',
                    'Regular updates'
                ],
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'  Created: {pro_eur.name}')

        enterprise_eur, created = PricingPlan.objects.get_or_create(
            plan=SubscriptionPlan.ENTERPRISE,
            currency=Currency.EUR,
            defaults={
                'name': 'Enterprise',
                'description': 'Enterprise plan for organizations',
                'price': 89.99,
                'duration_days': 30,
                'max_clients': 50,
                'allowed_models': [
                    'llama3_1_8b_fp16',
                    'mistral_7b_int4',
                    'custom_models'
                ],
                'features': [
                    'Access to all models',
                    'Up to 50 clients',
                    '24/7 support',
                    'Custom models',
                    'Advanced analytics'
                ],
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'  Created: {enterprise_eur.name}')