from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from models_api.models import ModelFile

User = get_user_model()

class Command(BaseCommand):
    help = 'Setup initial data for TikTrue backend'

    def handle(self, *args, **options):
        """Setup initial data"""
        
        self.stdout.write("🚀 Setting up initial data...")
        
        # 1. Create models
        self.setup_models()
        
        # 2. Create admin user if not exists
        self.setup_admin_user()
        
        self.stdout.write(
            self.style.SUCCESS('✅ Initial data setup completed!')
        )
    
    def setup_models(self):
        """Create model records"""
        models_data = [
            {
                'name': 'llama3_1_8b_fp16',
                'display_name': 'Llama 3.1 8B FP16',
                'description': 'Meta Llama 3.1 8B model in FP16 precision',
                'version': '1.0.0',
                'file_size': 16000000000,  # ~16GB
                'block_count': 33,
            },
            {
                'name': 'mistral_7b_int4',
                'display_name': 'Mistral 7B INT4',
                'description': 'Mistral 7B model quantized to INT4',
                'version': '1.0.0',
                'file_size': 4000000000,  # ~4GB
                'block_count': 32,
            }
        ]
        
        for model_data in models_data:
            model, created = ModelFile.objects.get_or_create(
                name=model_data['name'],
                defaults=model_data
            )
            
            if created:
                self.stdout.write(f'✅ Created model: {model.display_name}')
            else:
                self.stdout.write(f'⚠️  Model exists: {model.display_name}')
    
    def setup_admin_user(self):
        """Create admin user if not exists"""
        if not User.objects.filter(is_superuser=True).exists():
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@tiktrue.com',
                password='admin123'  # Change this!
            )
            self.stdout.write(f'✅ Created admin user: {admin_user.email}')
            self.stdout.write('⚠️  Default password: admin123 (Please change!)')
        else:
            self.stdout.write('⚠️  Admin user already exists')