#!/usr/bin/env python3
"""
CORS Configuration Testing Script for TikTrue Backend

This script tests CORS configuration to ensure proper frontend-backend connectivity.
"""

import requests
import json
import sys
from datetime import datetime

class CORSTester:
    def __init__(self, backend_url, frontend_origins=None):
        self.backend_url = backend_url.rstrip('/')
        self.frontend_origins = frontend_origins or [
            'https://tiktrue.com',
            'https://www.tiktrue.com',
            'https://tiktrue-frontend.liara.run',
            'http://localhost:3000',
            'http://127.0.0.1:3000'
        ]
        self.test_results = []
        
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

    def test_preflight_request(self, origin, endpoint='/api/v1/auth/login/'):
        """Test CORS preflight request for a specific origin"""
        import time
        
        try:
            start_time = time.time()
            response = requests.options(
                f"{self.backend_url}{endpoint}",
                headers={
                    'Origin': origin,
                    'Access-Control-Request-Method': 'POST',
                    'Access-Control-Request-Headers': 'Content-Type,Authorization'
                },
                timeout=10
            )
            response_time = (time.time() - start_time) * 1000
            
            # Check response status
            if response.status_code != 200:
                self.log_test(f"Preflight {origin}", "fail", 
                            f"HTTP {response.status_code}", response_time)
                return False
            
            # Check CORS headers
            cors_headers = {
                'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
                'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
                'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers'),
                'Access-Control-Allow-Credentials': response.headers.get('Access-Control-Allow-Credentials'),
                'Access-Control-Max-Age': response.headers.get('Access-Control-Max-Age')
            }
            
            # Validate required headers
            issues = []
            
            if not cors_headers['Access-Control-Allow-Origin']:
                issues.append("Missing Access-Control-Allow-Origin")
            elif cors_headers['Access-Control-Allow-Origin'] not in [origin, '*']:
                issues.append(f"Origin mismatch: got {cors_headers['Access-Control-Allow-Origin']}, expected {origin}")
            
            if not cors_headers['Access-Control-Allow-Methods']:
                issues.append("Missing Access-Control-Allow-Methods")
            elif 'POST' not in cors_headers['Access-Control-Allow-Methods']:
                issues.append("POST method not allowed")
            
            if not cors_headers['Access-Control-Allow-Headers']:
                issues.append("Missing Access-Control-Allow-Headers")
            else:
                required_headers = ['content-type', 'authorization']
                allowed_headers = cors_headers['Access-Control-Allow-Headers'].lower()
                for header in required_headers:
                    if header not in allowed_headers:
                        issues.append(f"Missing required header: {header}")
            
            if cors_headers['Access-Control-Allow-Credentials'] != 'true':
                issues.append("Credentials not allowed")
            
            if issues:
                self.log_test(f"Preflight {origin}", "fail", 
                            f"Issues: {', '.join(issues)}", response_time)
                return False
            else:
                self.log_test(f"Preflight {origin}", "pass", 
                            f"All CORS headers correct", response_time)
                return True
                
        except Exception as e:
            self.log_test(f"Preflight {origin}", "fail", str(e))
            return False

    def test_actual_request(self, origin, endpoint='/api/v1/auth/login/'):
        """Test actual CORS request (not preflight)"""
        import time
        
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.backend_url}{endpoint}",
                headers={
                    'Origin': origin,
                    'Content-Type': 'application/json'
                },
                json={},  # Empty data to trigger validation error
                timeout=10
            )
            response_time = (time.time() - start_time) * 1000
            
            # Check CORS headers in actual response
            cors_origin = response.headers.get('Access-Control-Allow-Origin')
            cors_credentials = response.headers.get('Access-Control-Allow-Credentials')
            
            issues = []
            
            if not cors_origin:
                issues.append("Missing Access-Control-Allow-Origin in response")
            elif cors_origin not in [origin, '*']:
                issues.append(f"Origin mismatch in response: got {cors_origin}, expected {origin}")
            
            if cors_credentials != 'true':
                issues.append("Credentials not allowed in response")
            
            # We expect 400 for empty data, which means the endpoint is working
            if response.status_code == 400:
                if issues:
                    self.log_test(f"Actual Request {origin}", "warning", 
                                f"Endpoint works but CORS issues: {', '.join(issues)}", response_time)
                else:
                    self.log_test(f"Actual Request {origin}", "pass", 
                                f"Endpoint works with proper CORS", response_time)
                return len(issues) == 0
            else:
                self.log_test(f"Actual Request {origin}", "fail", 
                            f"Unexpected status: {response.status_code}", response_time)
                return False
                
        except Exception as e:
            self.log_test(f"Actual Request {origin}", "fail", str(e))
            return False

    def test_forbidden_origin(self):
        """Test that forbidden origins are properly rejected"""
        forbidden_origins = [
            'https://malicious-site.com',
            'http://localhost:8080',
            'https://example.com'
        ]
        
        for origin in forbidden_origins:
            try:
                response = requests.options(
                    f"{self.backend_url}/api/v1/auth/login/",
                    headers={
                        'Origin': origin,
                        'Access-Control-Request-Method': 'POST',
                        'Access-Control-Request-Headers': 'Content-Type'
                    },
                    timeout=10
                )
                
                cors_origin = response.headers.get('Access-Control-Allow-Origin')
                
                if cors_origin == origin:
                    self.log_test(f"Forbidden Origin {origin}", "fail", 
                                "Origin incorrectly allowed")
                    return False
                else:
                    self.log_test(f"Forbidden Origin {origin}", "pass", 
                                "Origin correctly rejected")
                    
            except Exception as e:
                self.log_test(f"Forbidden Origin {origin}", "warning", 
                            f"Request failed: {str(e)}")
        
        return True

    def test_cors_methods(self, origin='https://tiktrue.com'):
        """Test different HTTP methods with CORS"""
        methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
        
        for method in methods:
            try:
                response = requests.options(
                    f"{self.backend_url}/api/v1/auth/login/",
                    headers={
                        'Origin': origin,
                        'Access-Control-Request-Method': method,
                        'Access-Control-Request-Headers': 'Content-Type'
                    },
                    timeout=10
                )
                
                allowed_methods = response.headers.get('Access-Control-Allow-Methods', '')
                
                if method in allowed_methods:
                    self.log_test(f"Method {method}", "pass", 
                                f"Method allowed")
                else:
                    self.log_test(f"Method {method}", "fail", 
                                f"Method not in allowed methods: {allowed_methods}")
                    
            except Exception as e:
                self.log_test(f"Method {method}", "fail", str(e))

    def test_cors_headers(self, origin='https://tiktrue.com'):
        """Test different headers with CORS"""
        headers_to_test = [
            'Content-Type',
            'Authorization',
            'X-Requested-With',
            'Accept',
            'Origin'
        ]
        
        for header in headers_to_test:
            try:
                response = requests.options(
                    f"{self.backend_url}/api/v1/auth/login/",
                    headers={
                        'Origin': origin,
                        'Access-Control-Request-Method': 'POST',
                        'Access-Control-Request-Headers': header
                    },
                    timeout=10
                )
                
                allowed_headers = response.headers.get('Access-Control-Allow-Headers', '').lower()
                
                if header.lower() in allowed_headers:
                    self.log_test(f"Header {header}", "pass", 
                                f"Header allowed")
                else:
                    self.log_test(f"Header {header}", "fail", 
                                f"Header not in allowed headers: {allowed_headers}")
                    
            except Exception as e:
                self.log_test(f"Header {header}", "fail", str(e))

    def run_all_tests(self):
        """Run all CORS tests"""
        print(f"TikTrue Backend CORS Test Suite")
        print(f"Backend URL: {self.backend_url}")
        print(f"Testing {len(self.frontend_origins)} origins")
        print("=" * 60)
        
        # Test preflight requests for all origins
        print("\n" + "-" * 40)
        print("Preflight Request Tests")
        print("-" * 40)
        
        for origin in self.frontend_origins:
            self.test_preflight_request(origin)
        
        # Test actual requests for all origins
        print("\n" + "-" * 40)
        print("Actual Request Tests")
        print("-" * 40)
        
        for origin in self.frontend_origins:
            self.test_actual_request(origin)
        
        # Test forbidden origins
        print("\n" + "-" * 40)
        print("Forbidden Origin Tests")
        print("-" * 40)
        
        self.test_forbidden_origin()
        
        # Test methods and headers
        print("\n" + "-" * 40)
        print("Methods and Headers Tests")
        print("-" * 40)
        
        self.test_cors_methods()
        self.test_cors_headers()
        
        # Generate summary
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("CORS TEST SUMMARY")
        print("=" * 60)
        
        passed = len([r for r in self.test_results if r['status'] == 'pass'])
        failed = len([r for r in self.test_results if r['status'] == 'fail'])
        warnings = len([r for r in self.test_results if r['status'] == 'warning'])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Warnings: {warnings}")
        
        if failed > 0:
            print(f"\n❌ {failed} tests failed - CORS configuration has issues")
            print("\nFailed Tests:")
            for result in self.test_results:
                if result['status'] == 'fail':
                    print(f"  - {result['test']}: {result['details']}")
        elif warnings > 0:
            print(f"\n⚠️  {warnings} tests have warnings - CORS mostly working")
        else:
            print(f"\n✅ All tests passed - CORS is properly configured")
        
        # Save results to file
        with open('cors_test_results.json', 'w') as f:
            json.dump(self.test_results, f, indent=2)
        print(f"\nDetailed results saved to: cors_test_results.json")

def main():
    """Main function"""
    backend_url = "https://api.tiktrue.com"
    
    # Allow URL override from command line
    if len(sys.argv) > 1:
        backend_url = sys.argv[1]
    
    # Allow custom origins from command line
    frontend_origins = None
    if len(sys.argv) > 2:
        frontend_origins = sys.argv[2].split(',')
    
    tester = CORSTester(backend_url, frontend_origins)
    tester.run_all_tests()

if __name__ == "__main__":
    main()