from django.core.management.base import BaseCommand
from models_api.models import ModelFile

class Command(BaseCommand):
    help = 'Setup initial model records in database'

    def handle(self, *args, **options):
        """Create model records without actual files"""
        
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
                self.stdout.write(
                    self.style.SUCCESS(f'Created model: {model.display_name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Model already exists: {model.display_name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('Model setup completed!')
        )
        
        self.stdout.write(
            self.style.WARNING('Note: Actual model files need to be uploaded separately to cloud storage')
        )