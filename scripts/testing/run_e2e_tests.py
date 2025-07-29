#!/usr/bin/env python3
"""
Comprehensive End-to-End Testing Suite for TikTrue Platform
This script runs all automated tests and generates a detailed report.
"""

import requests
import json
import sys
import os
import time
import subprocess
from datetime import datetime

class TikTrueE2ETester:
    def __init__(self):
        self.frontend_url = "https://tiktrue.com"
        self.backend_url = "https://api.tiktrue.com"
        self.test_results = []
        self.auth_token = None
        
    def log_result(self, test_name, passed, message="", details=""):
        """Log test result"""
        result = {
            "test": test_name,
            "passed": passed,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        if message:
            print(f"    {message}")
    
    def test_website_accessibility(self):
        """Test basic website accessibility"""
        print("\n=== Testing Website Accessibility ===")
        
        # Test main page
        try:
            response = requests.get(self.frontend_url, timeout=10)
            self.log_result(
                "Main Page Load",
                response.status_code == 200,
                f"HTTP {response.status_code}",
                f"Response time: {response.elapsed.total_seconds():.2f}s"
            )
        except Exception as e:
            self.log_result("Main Page Load", False, str(e))
        
        # Test key pages
        pages = ["/login", "/register", "/pricing", "/about"]
        for page in pages:
            try:
                response = requests.get(f"{self.frontend_url}{page}", timeout=10)
                self.log_result(
                    f"Page Load: {page}",
                    response.status_code == 200,
                    f"HTTP {response.status_code}"
                )
            except Exception as e:
                self.log_result(f"Page Load: {page}", False, str(e))
    
    def test_api_health(self):
        """Test API health endpoints"""
        print("\n=== Testing API Health ===")
        
        try:
            response = requests.get(f"{self.backend_url}/api/health/", timeout=10)
            self.log_result(
                "API Health Check",
                response.status_code == 200,
                f"HTTP {response.status_code}",
                f"Response time: {response.elapsed.total_seconds():.2f}s"
            )
        except Exception as e:
            self.log_result("API Health Check", False, str(e))
    
    def test_user_registration(self):
        """Test user registration functionality"""
        print("\n=== Testing User Registration ===")
        
        # Generate unique test user
        timestamp = int(time.time())
        test_user = {
            "username": f"testuser{timestamp}",
            "email": f"test{timestamp}@example.com",
            "password": "TestPassword123!",
            "first_name": "Test",
            "last_name": "User"
        }
        
        try:
            response = requests.post(
                f"{self.backend_url}/api/auth/register/",
                json=test_user,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            self.log_result(
                "User Registration",
                response.status_code == 201,
                f"HTTP {response.status_code}",
                f"User: {test_user['username']}"
            )
            
            # Store test user for login test
            self.test_user = test_user
            
        except Exception as e:
            self.log_result("User Registration", False, str(e))
    
    def test_user_login(self):
        """Test user login functionality"""
        print("\n=== Testing User Login ===")
        
        if not hasattr(self, 'test_user'):
            self.log_result("User Login", False, "No test user available")
            return
        
        login_data = {
            "username": self.test_user["username"],
            "password": self.test_user["password"]
        }
        
        try:
            response = requests.post(
                f"{self.backend_url}/api/auth/login/",
                json=login_data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                
            self.log_result(
                "User Login",
                response.status_code == 200 and self.auth_token,
                f"HTTP {response.status_code}",
                f"Token received: {'Yes' if self.auth_token else 'No'}"
            )
            
        except Exception as e:
            self.log_result("User Login", False, str(e))
    
    def test_authenticated_endpoints(self):
        """Test endpoints requiring authentication"""
        print("\n=== Testing Authenticated Endpoints ===")
        
        if not self.auth_token:
            self.log_result("Authenticated Endpoints", False, "No auth token available")
            return
        
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }
        
        # Test user profile endpoint
        try:
            response = requests.get(
                f"{self.backend_url}/api/auth/user/",
                headers=headers,
                timeout=10
            )
            
            self.log_result(
                "User Profile Endpoint",
                response.status_code == 200,
                f"HTTP {response.status_code}"
            )
            
        except Exception as e:
            self.log_result("User Profile Endpoint", False, str(e))
        
        # Test subscription endpoint
        try:
            response = requests.get(
                f"{self.backend_url}/api/subscriptions/current/",
                headers=headers,
                timeout=10
            )
            
            # 200 (has subscription) or 404 (no subscription) are both valid
            self.log_result(
                "Subscription Endpoint",
                response.status_code in [200, 404],
                f"HTTP {response.status_code}"
            )
            
        except Exception as e:
            self.log_result("Subscription Endpoint", False, str(e))
    
    def test_error_handling(self):
        """Test error handling"""
        print("\n=== Testing Error Handling ===")
        
        # Test 404 handling
        try:
            response = requests.get(f"{self.backend_url}/api/nonexistent/", timeout=10)
            self.log_result(
                "404 Error Handling",
                response.status_code == 404,
                f"HTTP {response.status_code}"
            )
        except Exception as e:
            self.log_result("404 Error Handling", False, str(e))
        
        # Test invalid login
        try:
            response = requests.post(
                f"{self.backend_url}/api/auth/login/",
                json={"username": "invalid", "password": "invalid"},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            self.log_result(
                "Invalid Login Handling",
                response.status_code == 401,
                f"HTTP {response.status_code}"
            )
        except Exception as e:
            self.log_result("Invalid Login Handling", False, str(e))
    
    def test_cors_configuration(self):
        """Test CORS configuration"""
        print("\n=== Testing CORS Configuration ===")
        
        try:
            response = requests.options(
                f"{self.backend_url}/api/health/",
                headers={"Origin": self.frontend_url},
                timeout=10
            )
            
            cors_headers = [
                "Access-Control-Allow-Origin",
                "Access-Control-Allow-Methods",
                "Access-Control-Allow-Headers"
            ]
            
            cors_working = all(header in response.headers for header in cors_headers)
            
            self.log_result(
                "CORS Configuration",
                cors_working,
                f"Headers present: {cors_working}",
                f"Response headers: {dict(response.headers)}"
            )
            
        except Exception as e:
            self.log_result("CORS Configuration", False, str(e))
    
    def test_ssl_configuration(self):
        """Test SSL configuration"""
        print("\n=== Testing SSL Configuration ===")
        
        # Test HTTPS redirect
        try:
            response = requests.get(
                "http://tiktrue.com",
                allow_redirects=False,
                timeout=10
            )
            
            https_redirect = response.status_code in [301, 302, 308]
            
            self.log_result(
                "HTTPS Redirect",
                https_redirect,
                f"HTTP {response.status_code}",
                f"Location: {response.headers.get('Location', 'None')}"
            )
            
        except Exception as e:
            self.log_result("HTTPS Redirect", False, str(e))
        
        # Test SSL certificate
        try:
            response = requests.get(self.frontend_url, timeout=10)
            
            self.log_result(
                "SSL Certificate",
                response.url.startswith("https://"),
                f"Final URL: {response.url}"
            )
            
        except Exception as e:
            self.log_result("SSL Certificate", False, str(e))
    
    def generate_report(self):
        """Generate test report"""
        print("\n" + "="*60)
        print("TEST SUMMARY REPORT")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["passed"])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        if failed_tests > 0:
            print("\nFAILED TESTS:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  ✗ {result['test']}: {result['message']}")
        
        # Save detailed report
        report_file = f"e2e_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                "summary": {
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "failed_tests": failed_tests,
                    "success_rate": success_rate,
                    "test_date": datetime.now().isoformat()
                },
                "results": self.test_results
            }, f, indent=2)
        
        print(f"\nDetailed report saved to: {report_file}")
        
        return failed_tests == 0
    
    def run_all_tests(self):
        """Run all tests"""
        print("Starting TikTrue End-to-End Testing Suite")
        print(f"Frontend URL: {self.frontend_url}")
        print(f"Backend URL: {self.backend_url}")
        print(f"Test started at: {datetime.now()}")
        
        # Run all test categories
        self.test_website_accessibility()
        self.test_api_health()
        self.test_user_registration()
        self.test_user_login()
        self.test_authenticated_endpoints()
        self.test_error_handling()
        self.test_cors_configuration()
        self.test_ssl_configuration()
        
        # Generate and return report
        return self.generate_report()

def main():
    """Main function"""
    tester = TikTrueE2ETester()
    
    try:
        success = tester.run_all_tests()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\nTesting interrupted by user")
        return 1
    except Exception as e:
        print(f"\nUnexpected error during testing: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())