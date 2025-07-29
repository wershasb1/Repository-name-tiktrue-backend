#!/usr/bin/env python3
"""
Security and Performance Validation Script for TikTrue Platform
This script validates website performance, security headers, SSL configuration, and CORS setup.
"""

import requests
import ssl
import socket
import time
import json
import sys
from urllib.parse import urlparse
from datetime import datetime, timedelta

class SecurityPerformanceValidator:
    def __init__(self, frontend_url, backend_url):
        self.frontend_url = frontend_url
        self.backend_url = backend_url
        self.results = {
            'performance': {},
            'security': {},
            'ssl': {},
            'headers': {},
            'cors': {},
            'timestamp': datetime.now().isoformat()
        }
    
    def test_performance(self):
        """Test website performance metrics"""
        print("Testing performance metrics...")
        
        # Test frontend response time
        start_time = time.time()
        try:
            response = requests.get(self.frontend_url, timeout=10)
            response_time = time.time() - start_time
            
            self.results['performance']['frontend'] = {
                'response_time': round(response_time, 3),
                'status_code': response.status_code,
                'content_length': len(response.content),
                'target_time': 2.0,
                'passed': response_time < 2.0 and response.status_code == 200
            }
            
            print(f"  Frontend response time: {response_time:.3f}s")
            
        except Exception as e:
            self.results['performance']['frontend'] = {
                'error': str(e),
                'passed': False
            }
            print(f"  Frontend test failed: {str(e)}")
        
        # Test backend API response time
        start_time = time.time()
        try:
            response = requests.get(f"{self.backend_url}/api/health/", timeout=10)
            response_time = time.time() - start_time
            
            self.results['performance']['backend'] = {
                'response_time': round(response_time, 3),
                'status_code': response.status_code,
                'target_time': 0.5,
                'passed': response_time < 0.5 and response.status_code == 200
            }
            
            print(f"  Backend API response time: {response_time:.3f}s")
            
        except Exception as e:
            self.results['performance']['backend'] = {
                'error': str(e),
                'passed': False
            }
            print(f"  Backend test failed: {str(e)}")
        
        # Test multiple requests for consistency
        print("  Testing response consistency...")
        try:
            times = []
            for i in range(5):
                start_time = time.time()
                response = requests.get(self.frontend_url, timeout=10)
                times.append(time.time() - start_time)
            
            avg_time = sum(times) / len(times)
            max_time = max(times)
            min_time = min(times)
            
            self.results['performance']['consistency'] = {
                'average_time': round(avg_time, 3),
                'max_time': round(max_time, 3),
                'min_time': round(min_time, 3),
                'variance': round(max_time - min_time, 3),
                'passed': max_time < 3.0  # Allow some variance
            }
            
            print(f"  Average response time (5 requests): {avg_time:.3f}s")
            
        except Exception as e:
            self.results['performance']['consistency'] = {
                'error': str(e),
                'passed': False
            }
    
    def test_ssl_certificate(self):
        """Test SSL certificate configuration and validity"""
        print("Testing SSL certificate...")
        
        try:
            hostname = urlparse(self.frontend_url).hostname
            context = ssl.create_default_context()
            
            with socket.create_connection((hostname, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    
                    # Parse certificate dates
                    not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    not_before = datetime.strptime(cert['notBefore'], '%b %d %H:%M:%S %Y %Z')
                    
                    days_until_expiry = (not_after - datetime.now()).days
                    
                    self.results['ssl'] = {
                        'subject': dict(x[0] for x in cert['subject']),
                        'issuer': dict(x[0] for x in cert['issuer']),
                        'not_before': cert['notBefore'],
                        'not_after': cert['notAfter'],
                        'days_until_expiry': days_until_expiry,
                        'san': cert.get('subjectAltName', []),
                        'passed': days_until_expiry > 30
                    }
                    
                    print(f"  Certificate issuer: {self.results['ssl']['issuer'].get('organizationName', 'Unknown')}")
                    print(f"  Days until expiry: {days_until_expiry}")
                    
        except Exception as e:
            self.results['ssl'] = {
                'error': str(e),
                'passed': False
            }
            print(f"  SSL test failed: {str(e)}")
    
    def test_security_headers(self):
        """Test security headers implementation"""
        print("Testing security headers...")
        
        try:
            response = requests.get(self.frontend_url, timeout=10)
            headers = {k.lower(): v for k, v in response.headers.items()}
            
            required_headers = {
                'strict-transport-security': {
                    'name': 'HSTS',
                    'required': True,
                    'description': 'HTTP Strict Transport Security'
                },
                'x-content-type-options': {
                    'name': 'Content Type Options',
                    'required': True,
                    'description': 'Prevents MIME type sniffing'
                },
                'x-frame-options': {
                    'name': 'Frame Options',
                    'required': True,
                    'description': 'Clickjacking protection'
                },
                'x-xss-protection': {
                    'name': 'XSS Protection',
                    'required': False,
                    'description': 'XSS filtering (deprecated but good to have)'
                },
                'content-security-policy': {
                    'name': 'Content Security Policy',
                    'required': True,
                    'description': 'Controls resource loading'
                },
                'referrer-policy': {
                    'name': 'Referrer Policy',
                    'required': False,
                    'description': 'Controls referrer information'
                }
            }
            
            header_results = {}
            required_passed = 0
            required_total = 0
            
            for header, config in required_headers.items():
                present = header in headers
                value = headers.get(header, '')
                
                header_results[header] = {
                    'present': present,
                    'value': value,
                    'name': config['name'],
                    'required': config['required'],
                    'description': config['description']
                }
                
                if config['required']:
                    required_total += 1
                    if present:
                        required_passed += 1
                
                status = "✓" if present else "✗"
                req_text = " (required)" if config['required'] else " (optional)"
                print(f"  {status} {config['name']}{req_text}")
            
            self.results['headers'] = {
                'results': header_results,
                'required_passed': required_passed,
                'required_total': required_total,
                'passed': required_passed == required_total
            }
            
        except Exception as e:
            self.results['headers'] = {
                'error': str(e),
                'passed': False
            }
            print(f"  Security headers test failed: {str(e)}")
    
    def test_cors_configuration(self):
        """Test CORS configuration"""
        print("Testing CORS configuration...")
        
        try:
            # Test preflight request
            response = requests.options(
                f"{self.backend_url}/api/health/",
                headers={
                    'Origin': self.frontend_url,
                    'Access-Control-Request-Method': 'GET',
                    'Access-Control-Request-Headers': 'Content-Type'
                },
                timeout=10
            )
            
            cors_headers = {
                'access-control-allow-origin': response.headers.get('Access-Control-Allow-Origin'),
                'access-control-allow-methods': response.headers.get('Access-Control-Allow-Methods'),
                'access-control-allow-headers': response.headers.get('Access-Control-Allow-Headers'),
                'access-control-allow-credentials': response.headers.get('Access-Control-Allow-Credentials')
            }
            
            # Test actual request with origin
            actual_response = requests.get(
                f"{self.backend_url}/api/health/",
                headers={'Origin': self.frontend_url},
                timeout=10
            )
            
            actual_cors_origin = actual_response.headers.get('Access-Control-Allow-Origin')
            
            cors_working = (
                response.status_code in [200, 204] and
                cors_headers['access-control-allow-origin'] and
                actual_cors_origin
            )
            
            self.results['cors'] = {
                'preflight_status': response.status_code,
                'actual_request_status': actual_response.status_code,
                'headers': cors_headers,
                'actual_origin_header': actual_cors_origin,
                'passed': cors_working
            }
            
            print(f"  Preflight request: HTTP {response.status_code}")
            print(f"  Allowed origin: {cors_headers['access-control-allow-origin']}")
            
        except Exception as e:
            self.results['cors'] = {
                'error': str(e),
                'passed': False
            }
            print(f"  CORS test failed: {str(e)}")
    
    def test_https_redirect(self):
        """Test HTTPS redirect functionality"""
        print("Testing HTTPS redirect...")
        
        try:
            http_url = self.frontend_url.replace('https://', 'http://')
            response = requests.get(http_url, allow_redirects=False, timeout=10)
            
            redirect_location = response.headers.get('Location', '')
            is_https_redirect = (
                response.status_code in [301, 302, 308] and
                redirect_location.startswith('https://')
            )
            
            self.results['security']['https_redirect'] = {
                'status_code': response.status_code,
                'location': redirect_location,
                'is_https': redirect_location.startswith('https://'),
                'passed': is_https_redirect
            }
            
            print(f"  HTTP redirect: {response.status_code} -> {redirect_location}")
            
        except Exception as e:
            self.results['security']['https_redirect'] = {
                'error': str(e),
                'passed': False
            }
            print(f"  HTTPS redirect test failed: {str(e)}")
    
    def test_api_security(self):
        """Test API security configurations"""
        print("Testing API security...")
        
        try:
            # Test API without authentication
            response = requests.get(f"{self.backend_url}/api/auth/user/", timeout=10)
            
            # Should return 401 Unauthorized
            auth_required = response.status_code == 401
            
            # Test invalid token
            invalid_token_response = requests.get(
                f"{self.backend_url}/api/auth/user/",
                headers={'Authorization': 'Bearer invalid_token'},
                timeout=10
            )
            
            invalid_token_rejected = invalid_token_response.status_code == 401
            
            self.results['security']['api_auth'] = {
                'unauth_status': response.status_code,
                'invalid_token_status': invalid_token_response.status_code,
                'auth_required': auth_required,
                'invalid_token_rejected': invalid_token_rejected,
                'passed': auth_required and invalid_token_rejected
            }
            
            print(f"  Unauthenticated request: HTTP {response.status_code}")
            print(f"  Invalid token request: HTTP {invalid_token_response.status_code}")
            
        except Exception as e:
            self.results['security']['api_auth'] = {
                'error': str(e),
                'passed': False
            }
            print(f"  API security test failed: {str(e)}")
    
    def generate_report(self):
        """Generate comprehensive validation report"""
        print("\n" + "="*70)
        print("SECURITY AND PERFORMANCE VALIDATION REPORT")
        print("="*70)
        print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Frontend URL: {self.frontend_url}")
        print(f"Backend URL: {self.backend_url}")
        
        # Performance results
        print("\n📊 PERFORMANCE RESULTS:")
        print("-" * 30)
        
        if 'frontend' in self.results['performance']:
            frontend = self.results['performance']['frontend']
            if 'response_time' in frontend:
                status = "✅ PASS" if frontend['passed'] else "❌ FAIL"
                target = frontend.get('target_time', 'N/A')
                print(f"  Frontend Response Time: {frontend['response_time']}s (target: <{target}s) {status}")
            else:
                print(f"  Frontend: ❌ FAIL - {frontend.get('error', 'Unknown error')}")
        
        if 'backend' in self.results['performance']:
            backend = self.results['performance']['backend']
            if 'response_time' in backend:
                status = "✅ PASS" if backend['passed'] else "❌ FAIL"
                target = backend.get('target_time', 'N/A')
                print(f"  Backend API Response Time: {backend['response_time']}s (target: <{target}s) {status}")
            else:
                print(f"  Backend: ❌ FAIL - {backend.get('error', 'Unknown error')}")
        
        if 'consistency' in self.results['performance']:
            consistency = self.results['performance']['consistency']
            if 'average_time' in consistency:
                status = "✅ PASS" if consistency['passed'] else "❌ FAIL"
                print(f"  Response Consistency: avg={consistency['average_time']}s, variance={consistency['variance']}s {status}")
        
        # SSL results
        print("\n🔒 SSL CERTIFICATE RESULTS:")
        print("-" * 30)
        
        if 'error' not in self.results['ssl']:
            ssl_info = self.results['ssl']
            status = "✅ PASS" if ssl_info['passed'] else "❌ FAIL"
            print(f"  Certificate Validity: {ssl_info['days_until_expiry']} days remaining {status}")
            print(f"  Issuer: {ssl_info['issuer'].get('organizationName', 'Unknown')}")
            print(f"  Subject: {ssl_info['subject'].get('commonName', 'Unknown')}")
        else:
            print(f"  SSL Test: ❌ FAIL - {self.results['ssl']['error']}")
        
        # Security headers results
        print("\n🛡️ SECURITY HEADERS RESULTS:")
        print("-" * 30)
        
        if 'results' in self.results['headers']:
            header_info = self.results['headers']
            overall_status = "✅ PASS" if header_info['passed'] else "❌ FAIL"
            print(f"  Overall Headers: {header_info['required_passed']}/{header_info['required_total']} required headers {overall_status}")
            
            for header, info in header_info['results'].items():
                status = "✅" if info['present'] else "❌"
                req_text = " (required)" if info['required'] else ""
                print(f"    {status} {info['name']}{req_text}")
        else:
            print(f"  Headers Test: ❌ FAIL - {self.results['headers'].get('error', 'Unknown error')}")
        
        # CORS results
        print("\n🌐 CORS CONFIGURATION RESULTS:")
        print("-" * 30)
        
        if 'error' not in self.results['cors']:
            cors_info = self.results['cors']
            status = "✅ PASS" if cors_info['passed'] else "❌ FAIL"
            print(f"  CORS Configuration: {status}")
            print(f"  Preflight Status: HTTP {cors_info['preflight_status']}")
            print(f"  Allowed Origin: {cors_info['headers']['access-control-allow-origin']}")
        else:
            print(f"  CORS Test: ❌ FAIL - {self.results['cors']['error']}")
        
        # Security results
        print("\n🔐 SECURITY CONFIGURATION RESULTS:")
        print("-" * 30)
        
        if 'https_redirect' in self.results['security']:
            redirect = self.results['security']['https_redirect']
            if 'status_code' in redirect:
                status = "✅ PASS" if redirect['passed'] else "❌ FAIL"
                print(f"  HTTPS Redirect: HTTP {redirect['status_code']} {status}")
            else:
                print(f"  HTTPS Redirect: ❌ FAIL - {redirect.get('error', 'Unknown error')}")
        
        if 'api_auth' in self.results['security']:
            api_auth = self.results['security']['api_auth']
            if 'auth_required' in api_auth:
                status = "✅ PASS" if api_auth['passed'] else "❌ FAIL"
                print(f"  API Authentication: {status}")
            else:
                print(f"  API Authentication: ❌ FAIL - {api_auth.get('error', 'Unknown error')}")
        
        # Overall summary
        all_tests = []
        test_categories = []
        
        # Collect all test results
        if 'frontend' in self.results['performance']:
            all_tests.append(self.results['performance']['frontend'].get('passed', False))
            test_categories.append('Frontend Performance')
        
        if 'backend' in self.results['performance']:
            all_tests.append(self.results['performance']['backend'].get('passed', False))
            test_categories.append('Backend Performance')
        
        if 'consistency' in self.results['performance']:
            all_tests.append(self.results['performance']['consistency'].get('passed', False))
            test_categories.append('Response Consistency')
        
        all_tests.append(self.results['ssl'].get('passed', False))
        test_categories.append('SSL Certificate')
        
        all_tests.append(self.results['headers'].get('passed', False))
        test_categories.append('Security Headers')
        
        all_tests.append(self.results['cors'].get('passed', False))
        test_categories.append('CORS Configuration')
        
        if 'https_redirect' in self.results['security']:
            all_tests.append(self.results['security']['https_redirect'].get('passed', False))
            test_categories.append('HTTPS Redirect')
        
        if 'api_auth' in self.results['security']:
            all_tests.append(self.results['security']['api_auth'].get('passed', False))
            test_categories.append('API Authentication')
        
        passed_tests = sum(all_tests)
        total_tests = len(all_tests)
        
        print(f"\n📋 OVERALL SUMMARY:")
        print("-" * 30)
        print(f"  Tests Passed: {passed_tests}/{total_tests}")
        print(f"  Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        if passed_tests < total_tests:
            print(f"\n❌ FAILED TESTS:")
            for i, (test_passed, category) in enumerate(zip(all_tests, test_categories)):
                if not test_passed:
                    print(f"    • {category}")
        
        # Save detailed report
        report_file = f"security_performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        return passed_tests == total_tests
    
    def run_all_tests(self):
        """Run all validation tests"""
        print("🚀 Starting Security and Performance Validation")
        print(f"Frontend URL: {self.frontend_url}")
        print(f"Backend URL: {self.backend_url}")
        print(f"Test started at: {datetime.now()}")
        print("-" * 50)
        
        self.test_performance()
        self.test_ssl_certificate()
        self.test_security_headers()
        self.test_cors_configuration()
        self.test_https_redirect()
        self.test_api_security()
        
        return self.generate_report()

def main():
    """Main function"""
    # Default URLs - can be overridden via command line arguments
    frontend_url = "https://tiktrue.com"
    backend_url = "https://api.tiktrue.com"
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        frontend_url = sys.argv[1]
    if len(sys.argv) > 2:
        backend_url = sys.argv[2]
    
    validator = SecurityPerformanceValidator(frontend_url, backend_url)
    
    try:
        success = validator.run_all_tests()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\n⚠️ Validation interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n💥 Unexpected error during validation: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())