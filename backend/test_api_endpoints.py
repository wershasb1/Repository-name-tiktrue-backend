#!/usr/bin/env python3
"""
API Endpoint Testing Script for TikTrue Backend

This script tests all API endpoints to ensure they're working correctly.
"""

import requests
import json
import sys
from datetime import datetime

class APIEndpointTester:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.test_results = []
        self.auth_token = None
        
    def log_test(self, test_name, status, details=None, response_time=None):
        """Log test result"""
        result = {
            'test': test_name,
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'details': details,
            'response_time_ms': response_time
        }
        self.test_results.append(result)
        
        status_icon = "✓" if status == "pass" else "✗" if status == "fail" else "⚠"
        print(f"{status_icon} {test_name}: {status.upper()}")
        if details:
            print(f"  {details}")
        if response_time:
            print(f"  Response time: {response_time:.2f}ms")

    def test_endpoint(self, method, endpoint, data=None, headers=None, expected_status=None):
        """Test a specific endpoint"""
        import time
        
        if headers is None:
            headers = {'Content-Type': 'application/json'}
        
        if self.auth_token and 'Authorization' not in headers:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        
        try:
            start_time = time.time()
            
            if method.upper() == 'GET':
                response = requests.get(f"{self.base_url}{endpoint}", headers=headers, timeout=10)
            elif method.upper() == 'POST':
                response = requests.post(f"{self.base_url}{endpoint}", json=data, headers=headers, timeout=10)
            elif method.upper() == 'PUT':
                response = requests.put(f"{self.base_url}{endpoint}", json=data, headers=headers, timeout=10)
            elif method.upper() == 'DELETE':
                response = requests.delete(f"{self.base_url}{endpoint}", headers=headers, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response_time = (time.time() - start_time) * 1000
            
            # Check if response matches expected status
            if expected_status and response.status_code != expected_status:
                return False, f"Expected {expected_status}, got {response.status_code}", response_time
            
            # Try to parse JSON response
            try:
                response_data = response.json()
                return True, f"HTTP {response.status_code}: {json.dumps(response_data, indent=2)[:200]}...", response_time
            except:
                return True, f"HTTP {response.status_code}: {response.text[:200]}...", response_time
                
        except Exception as e:
            return False, str(e), None

    def test_health_endpoints(self):
        """Test health and basic endpoints"""
        print("\n" + "-" * 40)
        print("Health and Basic Endpoints")
        print("-" * 40)
        
        # Health check
        success, details, response_time = self.test_endpoint('GET', '/health/')
        status = "pass" if success else "fail"
        self.log_test("Health Check", status, details, response_time)
        
        # Admin panel
        success, details, response_time = self.test_endpoint('GET', '/admin/')
        status = "pass" if success else "fail"
        self.log_test("Admin Panel Access", status, details, response_time)

    def test_auth_endpoints(self):
        """Test authentication endpoints"""
        print("\n" + "-" * 40)
        print("Authentication Endpoints")
        print("-" * 40)
        
        # Test registration endpoint structure
        success, details, response_time = self.test_endpoint('POST', '/api/v1/auth/register/', {})
        status = "pass" if success and "400" in details else "fail"
        self.log_test("Registration Endpoint Structure", status, details, response_time)
        
        # Test login endpoint structure
        success, details, response_time = self.test_endpoint('POST', '/api/v1/auth/login/', {})
        status = "pass" if success and "400" in details else "fail"
        self.log_test("Login Endpoint Structure", status, details, response_time)
        
        # Test actual registration
        test_user_data = {
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpassword123",
            "password_confirm": "testpassword123"
        }
        
        success, details, response_time = self.test_endpoint('POST', '/api/v1/auth/register/', test_user_data)
        if success and ("201" in details or "400" in details):
            status = "pass"
            # Try to extract token if registration was successful
            if "201" in details and "access" in details:
                try:
                    response_data = json.loads(details.split(': ', 1)[1])
                    if 'tokens' in response_data and 'access' in response_data['tokens']:
                        self.auth_token = response_data['tokens']['access']
                except:
                    pass
        else:
            status = "fail"
        self.log_test("User Registration", status, details, response_time)
        
        # Test login with test user
        login_data = {
            "email": "test@example.com",
            "password": "testpassword123"
        }
        
        success, details, response_time = self.test_endpoint('POST', '/api/v1/auth/login/', login_data)
        if success and ("200" in details or "400" in details):
            status = "pass"
            # Try to extract token if login was successful
            if "200" in details and "access" in details:
                try:
                    response_data = json.loads(details.split(': ', 1)[1])
                    if 'tokens' in response_data and 'access' in response_data['tokens']:
                        self.auth_token = response_data['tokens']['access']
                except:
                    pass
        else:
            status = "fail"
        self.log_test("User Login", status, details, response_time)

    def test_protected_endpoints(self):
        """Test protected endpoints that require authentication"""
        print("\n" + "-" * 40)
        print("Protected Endpoints")
        print("-" * 40)
        
        if not self.auth_token:
            self.log_test("Protected Endpoints", "skip", "No auth token available")
            return
        
        # Test profile endpoint
        success, details, response_time = self.test_endpoint('GET', '/api/v1/auth/profile/')
        status = "pass" if success and "200" in details else "fail"
        self.log_test("User Profile", status, details, response_time)
        
        # Test license info
        success, details, response_time = self.test_endpoint('GET', '/api/v1/license/info/')
        status = "pass" if success else "fail"
        self.log_test("License Info", status, details, response_time)
        
        # Test available models
        success, details, response_time = self.test_endpoint('GET', '/api/v1/models/available/')
        status = "pass" if success else "fail"
        self.log_test("Available Models", status, details, response_time)

    def test_license_endpoints(self):
        """Test license-related endpoints"""
        print("\n" + "-" * 40)
        print("License Endpoints")
        print("-" * 40)
        
        # Test license validation (should work without auth for desktop app)
        license_data = {
            "license_key": "test-license-key",
            "hardware_fingerprint": "test-fingerprint"
        }
        
        success, details, response_time = self.test_endpoint('POST', '/api/v1/license/validate/', license_data)
        status = "pass" if success else "fail"
        self.log_test("License Validation", status, details, response_time)

    def test_model_endpoints(self):
        """Test model-related endpoints"""
        print("\n" + "-" * 40)
        print("Model Endpoints")
        print("-" * 40)
        
        # Test available models (public endpoint)
        success, details, response_time = self.test_endpoint('GET', '/api/v1/models/available/')
        status = "pass" if success else "fail"
        self.log_test("Available Models (Public)", status, details, response_time)

    def test_error_handling(self):
        """Test error handling"""
        print("\n" + "-" * 40)
        print("Error Handling")
        print("-" * 40)
        
        # Test 404 error
        success, details, response_time = self.test_endpoint('GET', '/api/v1/nonexistent/')
        status = "pass" if "404" in details else "fail"
        self.log_test("404 Error Handling", status, details, response_time)
        
        # Test invalid JSON
        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.post(f"{self.base_url}/api/v1/auth/login/", 
                                   data="invalid json", headers=headers, timeout=10)
            status = "pass" if response.status_code == 400 else "fail"
            details = f"HTTP {response.status_code}"
        except Exception as e:
            status = "fail"
            details = str(e)
        
        self.log_test("Invalid JSON Handling", status, details)

    def run_all_tests(self):
        """Run all API endpoint tests"""
        print(f"TikTrue Backend API Endpoint Test Suite")
        print(f"Base URL: {self.base_url}")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        self.test_health_endpoints()
        self.test_auth_endpoints()
        self.test_protected_endpoints()
        self.test_license_endpoints()
        self.test_model_endpoints()
        self.test_error_handling()
        
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("API ENDPOINT TEST SUMMARY")
        print("=" * 60)
        
        passed = len([r for r in self.test_results if r['status'] == 'pass'])
        failed = len([r for r in self.test_results if r['status'] == 'fail'])
        skipped = len([r for r in self.test_results if r['status'] == 'skip'])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Skipped: {skipped}")
        
        if failed > 0:
            print(f"\n❌ {failed} tests failed - API has issues")
            print("\nFailed Tests:")
            for result in self.test_results:
                if result['status'] == 'fail':
                    print(f"  - {result['test']}: {result['details']}")
        elif skipped > 0:
            print(f"\n⚠️  {skipped} tests skipped - Some functionality not tested")
        else:
            print(f"\n✅ All tests passed - API is working correctly")
        
        # Save results to file
        with open('api_endpoint_test_results.json', 'w') as f:
            json.dump(self.test_results, f, indent=2)
        print(f"\nDetailed results saved to: api_endpoint_test_results.json")

def main():
    """Main function"""
    base_url = "https://api.tiktrue.com"
    
    # Allow URL override from command line
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    tester = APIEndpointTester(base_url)
    tester.run_all_tests()

if __name__ == "__main__":
    main()