#!/usr/bin/env python3
"""
Test script for access_control.py module
Tests role-based permissions, license-based feature access, and resource quotas
"""

import sys
from datetime import datetime, timedelta

# Import the access control module
from access_control import (
    AccessControlManager, User, UserRole, Permission, 
    ResourceType, AccessLevel, FeatureFlag
)
from security.license_validator import LicenseInfo, SubscriptionTier, LicenseStatus


def test_access_control():
    """Test access control functionality"""
    print("=== Testing Access Control Module ===\n")
    
    # Create test license (PRO tier)
    license_info = LicenseInfo(
        license_key="TIKT-PRO-12-TEST01",
        plan=SubscriptionTier.PRO,
        duration_months=12,
        unique_id="TEST01",
        expires_at=datetime.now() + timedelta(days=365),
        max_clients=20,
        allowed_models=["llama", "mistral"],
        allowed_features=["multi_network", "api_access", "monitoring"],
        status=LicenseStatus.VALID,
        hardware_signature="test_hw_sig",
        created_at=datetime.now(),
        checksum="test_checksum"
    )
    
    # Create access control manager
    access_manager = AccessControlManager(license_info=license_info)
    
    # Test 1: Create different user roles
    print("1. Testing User Roles and Permissions")
    
    # Admin user
    admin_user = User(
        user_id="admin_001",
        username="admin",
        email="admin@test.com",
        password_hash="hash",
        salt="salt",
        roles={UserRole.ADMIN},
        permissions={Permission.SYSTEM_ADMIN, Permission.NETWORK_CREATE, Permission.USER_MANAGE}
    )
    
    # Developer user
    dev_user = User(
        user_id="dev_001", 
        username="developer",
        email="dev@test.com",
        password_hash="hash",
        salt="salt",
        roles={UserRole.DEVELOPER},
        permissions={Permission.NETWORK_VIEW, Permission.API_INFERENCE, Permission.MODEL_VIEW}
    )
    
    # Client user
    client_user = User(
        user_id="client_001",
        username="client",
        email="client@test.com", 
        password_hash="hash",
        salt="salt",
        roles={UserRole.CLIENT},
        permissions={Permission.API_INFERENCE}
    )
    
    # Test access for different users
    test_cases = [
        (admin_user, ResourceType.NETWORK, AccessLevel.ADMIN, "Admin network admin access"),
        (dev_user, ResourceType.NETWORK, AccessLevel.READ, "Developer network read access"),
        (dev_user, ResourceType.NETWORK, AccessLevel.WRITE, "Developer network write access (should fail)"),
        (client_user, ResourceType.API_ENDPOINT, AccessLevel.EXECUTE, "Client API access"),
        (client_user, ResourceType.SYSTEM_CONFIG, AccessLevel.READ, "Client system config access (should fail)")
    ]
    
    for user, resource_type, access_level, description in test_cases:
        result = access_manager.check_access(user, resource_type, "test_resource", access_level)
        status = "✓ GRANTED" if result.granted else "✗ DENIED"
        print(f"  {status}: {description}")
        if not result.granted:
            print(f"    Reason: {result.reason}")
    
    print()
    
    # Test 2: License-based feature access
    print("2. Testing License-based Feature Access")
    
    features_to_test = [
        (FeatureFlag.BASIC_INFERENCE, "Basic inference (should be available)"),
        (FeatureFlag.MULTI_NETWORK, "Multi-network (PRO feature)"),
        (FeatureFlag.ADVANCED_MONITORING, "Advanced monitoring (ENT feature, should fail)"),
        (FeatureFlag.BACKUP_RESTORE, "Backup restore (ENT feature, should fail)")
    ]
    
    for feature, description in features_to_test:
        available = access_manager.has_feature(feature)
        status = "✓ AVAILABLE" if available else "✗ NOT AVAILABLE"
        print(f"  {status}: {description}")
    
    print()
    
    # Test 3: Resource quotas
    print("3. Testing Resource Quotas")
    
    # Test quota consumption
    quota_tests = [
        (ResourceType.NETWORK, 1, "Network quota consumption"),
        (ResourceType.API_ENDPOINT, 100, "API calls quota consumption"),
        (ResourceType.WORKER, 5, "Worker quota consumption")
    ]
    
    for resource_type, count, description in quota_tests:
        success = access_manager.consume_quota(resource_type, count)
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"  {status}: {description}")
    
    # Show current quota status
    print("\n  Current Quota Status:")
    quotas = access_manager.get_resource_quotas()
    for quota_name, quota_info in quotas.items():
        usage = quota_info['usage_percentage']
        print(f"    {quota_name}: {quota_info['current_count']}/{quota_info['max_count']} ({usage:.1f}%)")
    
    print()
    
    # Test 4: User access summary
    print("4. Testing User Access Summary")
    
    summary = access_manager.get_user_access_summary(dev_user)
    print(f"  User: {summary.get('username', 'N/A')}")
    print(f"  Roles: {summary.get('roles', [])}")
    print(f"  License Tier: {summary.get('license_tier', 'N/A')}")
    print(f"  Available Features: {len(summary.get('available_features', []))}")
    
    # Show resource access matrix
    print("  Resource Access Matrix:")
    resource_access = summary.get('resource_access', {})
    for resource, access_levels in resource_access.items():
        granted_levels = [level for level, granted in access_levels.items() if granted]
        if granted_levels:
            print(f"    {resource}: {', '.join(granted_levels)}")
    
    print()
    
    # Test 5: Access logging
    print("5. Testing Access Logging")
    
    # Generate some access attempts
    access_manager.check_access(admin_user, ResourceType.SYSTEM_CONFIG, "config_1", AccessLevel.ADMIN)
    access_manager.check_access(client_user, ResourceType.NETWORK, "network_1", AccessLevel.WRITE)  # Should fail
    
    # Get access log
    log_entries = access_manager.get_access_log(limit=5)
    print(f"  Recent access attempts: {len(log_entries)}")
    
    for entry in log_entries[-2:]:  # Show last 2 entries
        status = "GRANTED" if entry['granted'] else "DENIED"
        print(f"    {entry['timestamp'][:19]}: {entry['username']} -> {entry['resource_type']} ({status})")
    
    print("\n=== Access Control Tests Completed ===")
    return True


def test_enterprise_features():
    """Test enterprise-level features"""
    print("\n=== Testing Enterprise Features ===\n")
    
    # Create enterprise license
    ent_license = LicenseInfo(
        license_key="TIKT-ENT-24-ENT001",
        plan=SubscriptionTier.ENT,
        duration_months=24,
        unique_id="ENT001",
        expires_at=datetime.now() + timedelta(days=730),
        max_clients=-1,  # Unlimited
        allowed_models=["all_models"],
        allowed_features=["all_features"],
        status=LicenseStatus.VALID,
        hardware_signature="ent_hw_sig",
        created_at=datetime.now(),
        checksum="ent_checksum"
    )
    
    # Create enterprise access manager
    ent_access_manager = AccessControlManager(license_info=ent_license)
    
    # Test enterprise features
    ent_features = [
        FeatureFlag.ADVANCED_MONITORING,
        FeatureFlag.BACKUP_RESTORE,
        FeatureFlag.CUSTOM_ENCRYPTION,
        FeatureFlag.UNLIMITED_WORKERS
    ]
    
    print("Enterprise Features:")
    for feature in ent_features:
        available = ent_access_manager.has_feature(feature)
        status = "✓ AVAILABLE" if available else "✗ NOT AVAILABLE"
        print(f"  {status}: {feature.value}")
    
    # Test unlimited quotas
    print("\nUnlimited Quotas Test:")
    for i in range(100):  # Try to consume way more than normal limits
        success = ent_access_manager.consume_quota(ResourceType.WORKER, 1)
        if not success:
            print(f"  ✗ Quota limit reached at {i} workers")
            break
    else:
        print("  ✓ Successfully consumed 100 worker quotas (unlimited)")
    
    print("\n=== Enterprise Tests Completed ===")


if __name__ == "__main__":
    try:
        # Run basic access control tests
        test_access_control()
        
        # Run enterprise feature tests
        test_enterprise_features()
        
        print("\n🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)