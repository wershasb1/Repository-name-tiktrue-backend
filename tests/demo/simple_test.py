"""
Simple test script to demonstrate key management functionality
"""

import asyncio
import tempfile
import shutil
from pathlib import Path

from key_manager import KeyManager, KeyStatus


async def main():
    """Demonstrate key management functionality"""
    print("=== Key Management System Demo ===\n")
    
    # Create temporary directory for testing
    test_dir = tempfile.mkdtemp()
    print(f"Using test directory: {test_dir}")
    
    try:
        # Initialize key manager
        key_manager = KeyManager(storage_dir=test_dir)
        print("✓ Key manager initialized")
        
        # Test data
        license_key = "demo_license_key_12345"
        model_id = "demo_model_v1"
        
        # 1. Generate hardware-bound key
        print("\n1. Generating hardware-bound key...")
        managed_key = key_manager.generate_hardware_bound_key(
            license_key=license_key,
            model_id=model_id
        )
        print(f"✓ Generated key: {managed_key.key_id}")
        print(f"  - Algorithm: {managed_key.algorithm}")
        print(f"  - Status: {managed_key.status.value}")
        print(f"  - Generation: {managed_key.rotation_generation}")
        print(f"  - Hardware fingerprint: {managed_key.hardware_fingerprint[:16]}...")
        
        # 2. Validate hardware binding
        print("\n2. Validating hardware binding...")
        is_valid = key_manager.validate_hardware_binding(managed_key.key_id)
        print(f"✓ Hardware binding valid: {is_valid}")
        
        # 3. List active keys
        print("\n3. Listing active keys...")
        active_keys = key_manager.list_active_keys()
        print(f"✓ Found {len(active_keys)} active keys")
        for key in active_keys:
            print(f"  - {key.key_id} (model: {key.metadata.get('model_id', 'unknown')})")
        
        # 4. Rotate key
        print("\n4. Rotating key...")
        new_key = await key_manager.rotate_key(
            old_key_id=managed_key.key_id,
            license_key=license_key,
            notify_clients=["demo_client_1", "demo_client_2"]
        )
        if new_key:
            print(f"✓ Key rotated successfully: {managed_key.key_id} -> {new_key.key_id}")
            print(f"  - New generation: {new_key.rotation_generation}")
            print(f"  - Predecessor: {new_key.predecessor_key_id}")
            
            # Check old key status
            old_key = key_manager.get_key(managed_key.key_id)
            print(f"  - Old key status: {old_key.status.value}")
        else:
            print("✗ Key rotation failed")
        
        # 5. Get rotation history
        print("\n5. Getting rotation history...")
        history = key_manager.get_key_rotation_history(managed_key.key_id)
        print(f"✓ Found {len(history)} rotation events")
        for event in history:
            print(f"  - {event.event_id}: {event.old_key_id} -> {event.new_key_id} ({event.status.value})")
        
        # 6. Test emergency revocation
        print("\n6. Testing emergency key revocation...")
        test_key = key_manager.generate_hardware_bound_key(
            license_key=license_key,
            model_id="revocation_test_model"
        )
        
        revocation_success = await key_manager.revoke_key(
            test_key.key_id,
            reason="demo_revocation"
        )
        print(f"✓ Key revocation successful: {revocation_success}")
        
        # Verify revoked key validation fails
        is_valid_after_revocation = key_manager.validate_hardware_binding(test_key.key_id)
        print(f"✓ Revoked key validation fails: {not is_valid_after_revocation}")
        
        # 7. Test key cleanup
        print("\n7. Testing key cleanup...")
        # Create an expired key for cleanup testing
        expired_key = key_manager.generate_hardware_bound_key(
            license_key=license_key,
            model_id="cleanup_test_model"
        )
        
        # Manually set it as deprecated and expired
        expired_key.status = KeyStatus.DEPRECATED
        from datetime import datetime, timedelta
        expired_key.expires_at = datetime.now() - timedelta(hours=1)
        key_manager._store_key(expired_key)
        key_manager.key_cache[expired_key.key_id] = expired_key
        
        # Run cleanup
        cleaned_count = await key_manager.cleanup_expired_keys()
        print(f"✓ Cleaned up {cleaned_count} expired keys")
        
        # 8. Final status
        print("\n8. Final system status...")
        final_active_keys = key_manager.list_active_keys()
        print(f"✓ Active keys: {len(final_active_keys)}")
        print(f"✓ Revoked keys: {len(key_manager.revoked_keys)}")
        
        print("\n=== Demo completed successfully! ===")
        
    except Exception as e:
        print(f"✗ Demo failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        shutil.rmtree(test_dir, ignore_errors=True)
        print(f"\nCleaned up test directory: {test_dir}")


if __name__ == "__main__":
    asyncio.run(main())