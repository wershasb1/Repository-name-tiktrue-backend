from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'payments'
    verbose_name = 'Payment Management'
    
    def ready(self):
        """Initialize payment system when app is ready"""
        import payments.signals  # Import signals to register them
