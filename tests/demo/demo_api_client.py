"""
Demo API Client with License Integration
Demonstrates the license-aware API client functionality without requiring WebSocket server
"""

import asyncio
import logging
import tempfile
import shutil
from datetime import datetime, timedelta

# Import our modules
from api_client import (
    LicenseAwareAPIClient, APIRequest, APIResponse, ConnectionStatus, 
    LicenseErrorType, create_inference_request
)
from security.license_validator import LicenseInfo, SubscriptionTier, LicenseStatus
from license_storage import LicenseStorage

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("APIClientDemo")


def create_test_license(tier: SubscriptionTier = SubscriptionTier.PRO) -> LicenseInfo:
    """Create a test license for demo purposes"""
    return LicenseInfo(
        license_key=f"TIKT-{tier.value}-1M-DEMO123",
        plan=tier,
        duration_months=1,
        unique_id="DEMO123",
        expires_at=datetime.now() + timedelta(days=30),
        max_clients=20 if tier == SubscriptionTier.PRO else 3,
        allowed_models=["llama-7b", "llama-13b", "mistral-7b"] if tier == SubscriptionTier.PRO else ["llama-7b"],
        allowed_features=["advanced_chat", "session_management", "multi_network"] if tier == SubscriptionTier.PRO else ["basic_chat"],
        status=LicenseStatus.VALID,
        hardware_signature="demo_signature",
        created_at=datetime.now(),
        checksum="demo_checksum"
    )


class MockAPIClientDemo:
    """Demo class that shows API client functionality without WebSocket dependency"""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.license_storage = LicenseStorage(self.temp_dir)
        
        # Create and save test license
        self.test_license = create_test_license(SubscriptionTier.PRO)
        self.license_storage.save_license_locally(self.test_license)
        
        # Create API client
        self.client = LicenseAwareAPIClient(
            server_host="localhost",
            server_port=8702,
            license_storage=self.license_storage,
            auto_reconnect=True,
            max_retries=3
        )
        
        # Set up callbacks
        self.setup_callbacks()
    
    def setup_callbacks(self):
        """Setup client callbacks"""
        def on_license_error(error_type: LicenseErrorType, message: str):
            print(f"🚨 License Error: {error_type.value}")
            print(f"   Message: {message}")
        
        def on_connection_status(status: ConnectionStatus):
            status_icons = {
                ConnectionStatus.DISCONNECTED: "🔴",
                ConnectionStatus.CONNECTING: "🟡",
                ConnectionStatus.CONNECTED: "🟢",
                ConnectionStatus.RECONNECTING: "🟡",
                ConnectionStatus.ERROR: "🔴"
            }
            print(f"{status_icons.get(status, '⚪')} Connection Status: {status.value}")
        
        def on_license_renewal_needed(license_info: LicenseInfo):
            days_remaining = (license_info.expires_at - datetime.now()).days
            print(f"⚠️  License Renewal Needed: {days_remaining} days remaining")
        
        self.client.set_license_error_callback(on_license_error)
        self.client.set_connection_status_callback(on_connection_status)
        self.client.set_license_renewal_callback(on_license_renewal_needed)
    
    def demonstrate_license_functionality(self):
        """Demonstrate license-related functionality"""
        print("=" * 60)
        print("🔐 LICENSE FUNCTIONALITY DEMO")
        print("=" * 60)
        
        # Show license status
        license_status = self.client.get_license_status()
        print(f"📋 License Status:")
        print(f"   Valid: {license_status['valid']}")
        print(f"   Plan: {license_status['plan']}")
        print(f"   Expires: {license_status['expires_at'][:10]}")
        print(f"   Days Remaining: {license_status['days_remaining']}")
        print(f"   Max Clients: {license_status['max_clients']}")
        print(f"   Allowed Models: {len(license_status['allowed_models'])}")
        print(f"   Allowed Features: {len(license_status['allowed_features'])}")
        
        # Show connection stats
        print(f"\n📊 Connection Statistics:")
        stats = self.client.get_connection_stats()
        for key, value in stats.items():
            if value is not None:
                print(f"   {key}: {value}")
    
    def demonstrate_request_validation(self):
        """Demonstrate request validation"""
        print("\n" + "=" * 60)
        print("✅ REQUEST VALIDATION DEMO")
        print("=" * 60)
        
        # Test valid request
        valid_request = APIRequest(
            session_id="demo_session_1",
            step=0,
            input_tensors={"input_ids": [[1, 2, 3, 4, 5]]},
            network_id="demo_network",
            model_id="llama-7b"
        )
        
        error = self.client._validate_request_permissions(valid_request)
        print(f"🟢 Valid Request (llama-7b): {'✅ Allowed' if error is None else '❌ ' + error}")
        
        # Test invalid model request
        invalid_request = APIRequest(
            session_id="demo_session_2",
            step=0,
            input_tensors={"input_ids": [[1, 2, 3, 4, 5]]},
            network_id="demo_network",
            model_id="premium_model_not_in_license"
        )
        
        error = self.client._validate_request_permissions(invalid_request)
        print(f"🔴 Invalid Request (premium model): {'✅ Allowed' if error is None else '❌ ' + error}")
        
        # Show request structure
        print(f"\n📝 Sample Request Structure:")
        request_dict = valid_request.to_dict()
        for key, value in request_dict.items():
            if key == "input_tensors":
                print(f"   {key}: {type(value).__name__} with {len(value)} keys")
            else:
                print(f"   {key}: {value}")
    
    def demonstrate_license_tiers(self):
        """Demonstrate different license tiers"""
        print("\n" + "=" * 60)
        print("🎯 LICENSE TIER COMPARISON")
        print("=" * 60)
        
        tiers = [SubscriptionTier.FREE, SubscriptionTier.PRO, SubscriptionTier.ENT]
        
        for tier in tiers:
            test_license = create_test_license(tier)
            temp_storage = LicenseStorage(tempfile.mkdtemp())
            temp_storage.save_license_locally(test_license)
            
            temp_client = LicenseAwareAPIClient(license_storage=temp_storage)
            status = temp_client.get_license_status()
            
            print(f"\n🏷️  {tier.value} Tier:")
            print(f"   Max Clients: {status['max_clients']}")
            print(f"   Models: {len(status['allowed_models'])}")
            print(f"   Features: {len(status['allowed_features'])}")
            
            # Test model access
            test_models = ["llama-7b", "llama-13b", "mistral-7b"]
            for model in test_models:
                request = APIRequest(
                    session_id="test",
                    step=0,
                    input_tensors={"input_ids": [[1]]},
                    model_id=model
                )
                error = temp_client._validate_request_permissions(request)
                status_icon = "✅" if error is None else "❌"
                print(f"     {model}: {status_icon}")
            
            # Cleanup
            shutil.rmtree(temp_storage.storage_dir, ignore_errors=True)
    
    async def demonstrate_async_functionality(self):
        """Demonstrate async functionality (without actual WebSocket)"""
        print("\n" + "=" * 60)
        print("⚡ ASYNC FUNCTIONALITY DEMO")
        print("=" * 60)
        
        print("🔄 Testing connection attempt (will fail without WebSocket server)...")
        
        # This will fail because no WebSocket server is running, but shows the flow
        try:
            connected = await self.client.connect()
            if connected:
                print("✅ Connected successfully!")
            else:
                print("❌ Connection failed (expected - no WebSocket server running)")
        except Exception as e:
            print(f"❌ Connection error: {e}")
        
        # Demonstrate request creation
        print(f"\n📦 Creating sample requests...")
        
        requests = [
            create_inference_request(
                session_id="demo_session_1",
                input_tensors={"input_ids": [[1, 2, 3, 4, 5]]},
                model_id="llama-7b",
                network_id="demo_network"
            ),
            create_inference_request(
                session_id="demo_session_2",
                input_tensors={"input_ids": [[6, 7, 8, 9, 10]]},
                model_id="llama-13b",
                network_id="demo_network",
                step=1
            )
        ]
        
        for i, request in enumerate(requests, 1):
            print(f"   Request {i}: {request.session_id} -> {request.model_id}")
            
            # Validate permissions
            error = self.client._validate_request_permissions(request)
            if error:
                print(f"     ❌ Permission denied: {error}")
            else:
                print(f"     ✅ Permissions valid")
    
    async def demonstrate_license_management(self):
        """Demonstrate license management features"""
        print("\n" + "=" * 60)
        print("🔧 LICENSE MANAGEMENT DEMO")
        print("=" * 60)
        
        # Test license refresh
        print("🔄 Testing license refresh...")
        refreshed = await self.client.refresh_license()
        print(f"   Result: {'✅ Success' if refreshed else '❌ Failed'}")
        
        # Test license installation (will fail with invalid key)
        print(f"\n🔑 Testing license installation...")
        test_keys = [
            "TIKT-PRO-1M-VALID123",  # This will fail validation
            "INVALID-KEY-FORMAT",    # This will fail format validation
        ]
        
        for key in test_keys:
            print(f"   Testing key: {key[:20]}...")
            try:
                installed = await self.client.install_license(key)
                print(f"     Result: {'✅ Success' if installed else '❌ Failed'}")
            except Exception as e:
                print(f"     Result: ❌ Error - {e}")
        
        # Show license hash generation
        print(f"\n🔐 License Hash Generation:")
        test_keys_for_hash = ["test_key_1", "test_key_2", "test_key_1"]
        for key in test_keys_for_hash:
            hash_value = self.client._generate_license_hash(key)
            print(f"   {key} -> {hash_value}")
    
    def cleanup(self):
        """Cleanup temporary resources"""
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            print(f"\n🧹 Cleaned up temporary directory")
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")


async def main():
    """Main demo function"""
    print("🚀 STARTING API CLIENT DEMO")
    print("This demo shows the license-aware API client functionality")
    print("Note: WebSocket functionality requires 'pip install websockets'\n")
    
    demo = MockAPIClientDemo()
    
    try:
        # Run all demonstrations
        demo.demonstrate_license_functionality()
        demo.demonstrate_request_validation()
        demo.demonstrate_license_tiers()
        await demo.demonstrate_async_functionality()
        await demo.demonstrate_license_management()
        
        print("\n" + "=" * 60)
        print("✨ DEMO COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print("Key Features Demonstrated:")
        print("✅ License validation and status checking")
        print("✅ Request permission validation")
        print("✅ License tier comparison")
        print("✅ Async connection handling")
        print("✅ License management operations")
        print("✅ Error handling and callbacks")
        
        print(f"\n📚 To use with real WebSocket server:")
        print("1. Install websockets: pip install websockets")
        print("2. Start your WebSocket server on localhost:8702")
        print("3. Use the API client in your application")
        
    finally:
        demo.cleanup()


if __name__ == "__main__":
    asyncio.run(main())