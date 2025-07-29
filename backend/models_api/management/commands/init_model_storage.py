"""
Management command to initialize secure model storage system
"""

import os
import json
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from models_api.storage import secure_storage
from models_api.models import ModelFile


class Command(BaseCommand):
    help = 'Initialize secure model storage system and encrypt existing models'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--model-name',
            type=str,
            help='Specific model to process (default: all models)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-encryption of existing encrypted models'
        )
        parser.add_argument(
            '--verify-only',
            action='store_true',
            help='Only verify existing encrypted models without processing'
        )
    
    def handle(self, *args, **options):
        model_name = options.get('model_name')
        force = options.get('force', False)
        verify_only = options.get('verify_only', False)
        
        if verify_only:
            self.verify_encrypted_models(model_name)
            return
        
        if model_name:
            self.process_single_model(model_name, force)
        else:
            self.process_all_models(force)
    
    def process_all_models(self, force=False):
        """Process all models in the database"""
        self.stdout.write("Initializing secure model storage for all models...")
        
        models = ModelFile.objects.filter(is_active=True)
        
        if not models.exists():
            self.stdout.write(
                self.style.WARNING('No active models found in database')
            )
            return
        
        for model in models:
            self.process_single_model(model.name, force)
    
    def process_single_model(self, model_name, force=False):
        """Process a single model"""
        self.stdout.write(f"Processing model: {model_name}")
        
        try:
            # Get model from database
            model_obj = ModelFile.objects.get(name=model_name, is_active=True)
        except ModelFile.DoesNotExist:
            raise CommandError(f"Model '{model_name}' not found in database")
        
        # Check if already encrypted
        storage_stats = secure_storage.get_storage_stats(model_name)
        if storage_stats.get('exists') and not force:
            self.stdout.write(
                self.style.WARNING(
                    f"Model {model_name} already encrypted. Use --force to re-encrypt"
                )
            )
            return
        
        # Find source model files
        source_path = os.path.join(
            settings.BASE_DIR.parent, 'assets', 'models', model_name
        )
        
        if not os.path.exists(source_path):
            raise CommandError(f"Source model path not found: {source_path}")
        
        # Process model metadata
        metadata_file = os.path.join(source_path, 'metadata.json')
        if os.path.exists(metadata_file):
            self.process_model_metadata(model_name, metadata_file)
        
        # Process model blocks
        blocks_path = os.path.join(source_path, 'blocks')
        if os.path.exists(blocks_path):
            self.process_model_blocks(model_name, blocks_path, model_obj.block_count)
        
        self.stdout.write(
            self.style.SUCCESS(f"Successfully processed model: {model_name}")
        )
    
    def process_model_metadata(self, model_name, metadata_file):
        """Process and encrypt model metadata"""
        self.stdout.write(f"  Processing metadata for {model_name}...")
        
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Store encrypted metadata
            success = secure_storage.store_model_metadata(model_name, metadata)
            
            if success:
                self.stdout.write("    ✓ Metadata encrypted and stored")
            else:
                self.stdout.write(
                    self.style.ERROR("    ✗ Failed to encrypt metadata")
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"    ✗ Error processing metadata: {e}")
            )
    
    def process_model_blocks(self, model_name, blocks_path, expected_blocks):
        """Process and encrypt model blocks"""
        self.stdout.write(f"  Processing {expected_blocks} blocks for {model_name}...")
        
        processed_blocks = 0
        failed_blocks = 0
        
        for block_id in range(1, expected_blocks + 1):
            try:
                # Look for skeleton files (these are the actual model blocks)
                skeleton_file = os.path.join(
                    blocks_path, f'block_{block_id}_skeleton.optimized.onnx'
                )
                
                if not os.path.exists(skeleton_file):
                    # Try alternative naming
                    skeleton_file = os.path.join(
                        blocks_path, f'block_{block_id}_skeleton_with_zeros.onnx'
                    )
                
                if not os.path.exists(skeleton_file):
                    self.stdout.write(
                        self.style.WARNING(f"    ⚠ Block {block_id} skeleton not found")
                    )
                    continue
                
                # Read block data
                with open(skeleton_file, 'rb') as f:
                    block_data = f.read()
                
                # Create block metadata
                block_metadata = {
                    'block_id': block_id,
                    'original_file': os.path.basename(skeleton_file),
                    'file_size': len(block_data),
                    'processed_at': None  # Will be set by storage system
                }
                
                # Store encrypted block
                result = secure_storage.store_model_block(
                    model_name, block_id, block_data, block_metadata
                )
                
                if result.get('success'):
                    processed_blocks += 1
                    if block_id % 5 == 0:  # Progress indicator
                        self.stdout.write(f"    Processed {block_id}/{expected_blocks} blocks")
                else:
                    failed_blocks += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"    ✗ Failed to process block {block_id}: {result.get('error')}"
                        )
                    )
                    
            except Exception as e:
                failed_blocks += 1
                self.stdout.write(
                    self.style.ERROR(f"    ✗ Error processing block {block_id}: {e}")
                )
        
        # Summary
        self.stdout.write(
            f"    ✓ Processed {processed_blocks} blocks successfully"
        )
        if failed_blocks > 0:
            self.stdout.write(
                self.style.WARNING(f"    ⚠ {failed_blocks} blocks failed")
            )
    
    def verify_encrypted_models(self, model_name=None):
        """Verify encrypted models integrity"""
        self.stdout.write("Verifying encrypted models...")
        
        if model_name:
            models = [model_name]
        else:
            # Get all active models
            model_objs = ModelFile.objects.filter(is_active=True)
            models = [model.name for model in model_objs]
        
        for model in models:
            self.verify_single_model(model)
    
    def verify_single_model(self, model_name):
        """Verify a single encrypted model"""
        self.stdout.write(f"Verifying model: {model_name}")
        
        # Check storage stats
        stats = secure_storage.get_storage_stats(model_name)
        
        if not stats.get('exists'):
            self.stdout.write(
                self.style.ERROR(f"  ✗ Model {model_name} not found in storage")
            )
            return
        
        # Verify metadata
        metadata = secure_storage.retrieve_model_metadata(model_name)
        if metadata:
            self.stdout.write("  ✓ Metadata verified")
        else:
            self.stdout.write(
                self.style.ERROR("  ✗ Metadata verification failed")
            )
        
        # Verify blocks
        blocks = secure_storage.list_model_blocks(model_name)
        verified_blocks = 0
        
        for block_info in blocks:
            block_id = block_info.get('block_id')
            block_data = secure_storage.retrieve_model_block(
                model_name, block_id, verify_integrity=True
            )
            
            if block_data:
                verified_blocks += 1
            else:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ Block {block_id} verification failed")
                )
        
        self.stdout.write(
            f"  ✓ Verified {verified_blocks}/{len(blocks)} blocks"
        )
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"Model {model_name}: {stats['total_size']} bytes, "
                f"{stats['block_count']} blocks"
            )
        )