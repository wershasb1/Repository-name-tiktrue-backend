#!/usr/bin/env python3
"""
Test setup endpoint
"""

import requests

def test_setup():
    url = "https://tiktrue.com/setup/database/"
    
    print("🔧 Testing database setup...")
    
    try:
        response = requests.post(url)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Setup successful!")
            print("Results:")
            for key, value in result.get('results', {}).items():
                print(f"  {key}: {value}")
        else:
            print(f"❌ Setup failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_setup()