#!/usr/bin/env python3
"""
Simple test for backend API client to debug issues
"""

import asyncio
import sys
from backend_api_client import BackendAPIClient, LoginCredentials

async def test_simple():
    """Simple test to verify basic functionality"""
    print("Testing BackendAPIClient...")
    
    # Test initialization
    client = BackendAPIClient("https://api.test.com")
    print(f"✅ Client initialized: {client.base_url}")
    
    # Test authentication status
    is_auth = client.is_authenticated()
    print(f"✅ Authentication status: {is_auth}")
    
    # Test credentials creation
    creds = LoginCredentials(
        username="test@example.com",
        password="password123",
        hardware_fingerprint="hw_123"
    )
    print(f"✅ Credentials created: {creds.username}")
    
    print("✅ All basic tests passed!")
    return True

if __name__ == "__main__":
    try:
        result = asyncio.run(test_simple())
        print(f"Test result: {result}")
        sys.exit(0)
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)