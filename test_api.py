#!/usr/bin/env python3
"""
Simple API test script for TikTrue Backend
"""

import requests
import json

# Backend URL
BASE_URL = "https://api.tiktrue.com"

def test_api_endpoints():
    """Test basic API endpoints"""
    
    print("Testing TikTrue Backend API...")
    print(f"Base URL: {BASE_URL}")
    print("-" * 50)
    
    # Test 1: Health check / Root endpoint
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        print(f"✓ Root endpoint: {response.status_code}")
        if response.status_code != 200:
            print(f"  Response: {response.text[:200]}")
    except Exception as e:
        print(f"✗ Root endpoint failed: {e}")
    
    # Test 2: Admin panel
    try:
        response = requests.get(f"{BASE_URL}/admin/", timeout=10)
        print(f"✓ Admin panel: {response.status_code}")
    except Exception as e:
        print(f"✗ Admin panel failed: {e}")
    
    # Test 3: API endpoints
    api_endpoints = [
        ("/api/v1/auth/register/", "POST"),
        ("/api/v1/auth/login/", "POST"),
        ("/api/v1/license/validate/", "GET"), 
        ("/api/v1/models/available/", "GET"),
        ("/health/", "GET")
    ]
    
    for endpoint, method in api_endpoints:
        try:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            else:
                response = requests.post(f"{BASE_URL}{endpoint}", json={}, timeout=10)
            
            print(f"✓ {endpoint} ({method}): {response.status_code}")
            
            # 405 means method not allowed but endpoint exists
            # 400 means bad request but endpoint exists  
            # 401 means unauthorized but endpoint exists
            if response.status_code not in [200, 400, 401, 403, 404, 405]:
                print(f"  Response: {response.text[:200]}")
        except Exception as e:
            print(f"✗ {endpoint} failed: {e}")
    
    print("-" * 50)
    print("API test completed!")

def test_cors():
    """Test CORS configuration"""
    print("\nTesting CORS configuration...")
    print("-" * 50)
    
    # Test CORS headers
    try:
        response = requests.options(f"{BASE_URL}/api/auth/", 
                                  headers={
                                      'Origin': 'https://tiktrue.com',
                                      'Access-Control-Request-Method': 'POST',
                                      'Access-Control-Request-Headers': 'Content-Type'
                                  },
                                  timeout=10)
        
        print(f"✓ CORS preflight: {response.status_code}")
        
        cors_headers = {
            'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
            'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
            'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers'),
            'Access-Control-Allow-Credentials': response.headers.get('Access-Control-Allow-Credentials')
        }
        
        for header, value in cors_headers.items():
            if value:
                print(f"  {header}: {value}")
            else:
                print(f"  {header}: Not set")
                
    except Exception as e:
        print(f"✗ CORS test failed: {e}")

if __name__ == "__main__":
    test_api_endpoints()
    test_cors()