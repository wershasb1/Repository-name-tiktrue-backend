#!/usr/bin/env python3
"""
SSL and HTTPS Configuration Testing Script for TikTrue Platform

This script tests SSL certificates, HTTPS redirects, security headers,
and mixed content issues for both frontend and backend.
"""

import requests
import json
import ssl
import socket
import sys
from datetime import datetime
from urllib.parse import urlparse

class SSLHTTPSTester:
    def __init__(self, frontend_url, backend_url):
        self.frontend_url = frontend_url.rstrip('/')
        self.backend_url = backend_url.rstrip('/')
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

    def test_ssl_certificate(self, url):
        """Test SSL certificate validity"""
        import time
        
        try:
            parsed_url = urlparse(url)
            hostname = parsed_url.hostname
            port = parsed_url.port or 443
            
            start_time = time.time()
            
            # Create SSL context
            context = ssl.create_default_context()
            
            # Connect and get certificate
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    
            response_time = (time.time() - start_time) * 1000
            
            # Check certificate details
            subject = dict(x[0] for x in cert['subject'])
            issuer = dict(x[0] for x in cert['issuer'])
            
            # Check expiration
            not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
            days_until_expiry = (not_after - datetime.now()).days
            
            if days_until_expiry > 30:
                status = "pass"
                details = f"Valid until {not_after.strftime('%Y-%m-%d')} ({days_until_expiry} days)"
            elif days_until_expiry > 0:
                status = "warning"
                details = f"Expires soon: {not_after.strftime('%Y-%m-%d')} ({days_until_expiry} days)"
            else:
                status = "fail"
                details = f"Certificate expired on {not_after.strftime('%Y-%m-%d')}"
            
            self.log_test(f"SSL Certificate {hostname}", status, details, response_time)
            
            # Additional certificate info
            self.log_test(f"SSL Issuer {hostname}", "pass", 
                         f"Issued by: {issuer.get('organizationName', 'Unknown')}")
            
            return True
            
        except Exception as e:
            self.log_test(f"SSL Certificate {hostname}", "fail", str(e))
            return False

    def test_https_redirect(self, url):
        """Test HTTP to HTTPS redirect"""
        import time
        
        try:
            # Convert HTTPS URL to HTTP
            http_url = url.replace('https://', 'http://')
            
            start_time = time.time()
            response = requests.get(http_url, allow_redirects=False, timeout=10)
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code in [301, 302, 307, 308]:
                location = response.headers.get('Location', '')
                if location.startswith('https://'):
                    self.log_test(f"HTTPS Redirect {urlparse(url).hostname}", "pass", 
                                f"HTTP {response.status_code} → {location}", response_time)
                    return True
                else:
                    self.log_test(f"HTTPS Redirect {urlparse(url).hostname}", "fail", 
                                f"Redirects to non-HTTPS: {location}", response_time)
                    return False
            else:
                self.log_test(f"HTTPS Redirect {urlparse(url).hostname}", "fail", 
                            f"No redirect, HTTP {response.status_code}", response_time)
                return False
                
        except Exception as e:
            self.log_test(f"HTTPS Redirect {urlparse(url).hostname}", "fail", str(e))
            return False

    def test_security_headers(self, url):
        """Test security headers"""
        import time
        
        try:
            start_time = time.time()
            response = requests.get(url, timeout=10)
            response_time = (time.time() - start_time) * 1000
            
            hostname = urlparse(url).hostname
            
            # Required security headers
            security_headers = {
                'Strict-Transport-Security': 'HSTS header',
                'X-Content-Type-Options': 'Content type options',
                'X-Frame-Options': 'Frame options',
                'Referrer-Policy': 'Referrer policy',
                'Cross-Origin-Opener-Policy': 'Cross-origin opener policy'
            }
            
            missing_headers = []
            present_headers = []
            
            for header, description in security_headers.items():
                if header in response.headers:
                    present_headers.append(f"{header}: {response.headers[header]}")
                else:
                    missing_headers.append(header)
            
            if not missing_headers:
                self.log_test(f"Security Headers {hostname}", "pass", 
                            f"All headers present", response_time)
            elif len(missing_headers) <= 2:
                self.log_test(f"Security Headers {hostname}", "warning", 
                            f"Missing: {', '.join(missing_headers)}", response_time)
            else:
                self.log_test(f"Security Headers {hostname}", "fail", 
                            f"Missing: {', '.join(missing_headers)}", response_time)
            
            # Log present headers
            for header_info in present_headers:
                self.log_test(f"Header {hostname}", "pass", header_info)
            
            return len(missing_headers) == 0
            
        except Exception as e:
            self.log_test(f"Security Headers {hostname}", "fail", str(e))
            return False

    def test_mixed_content(self, url):
        """Test for mixed content issues"""
        import time
        
        try:
            start_time = time.time()
            response = requests.get(url, timeout=10)
            response_time = (time.time() - start_time) * 1000
            
            hostname = urlparse(url).hostname
            content = response.text
            
            # Look for HTTP resources in HTTPS page
            mixed_content_patterns = [
                'src="http://',
                'href="http://',
                'action="http://',
                'url(http://',
                "'http://",
                '"http://'
            ]
            
            mixed_content_found = []
            for pattern in mixed_content_patterns:
                if pattern in content:
                    # Find the specific URLs
                    import re
                    matches = re.findall(f'{pattern}[^"\'\\s>]+', content)
                    mixed_content_found.extend(matches)
            
            if not mixed_content_found:
                self.log_test(f"Mixed Content {hostname}", "pass", 
                            "No mixed content detected", response_time)
                return True
            else:
                self.log_test(f"Mixed Content {hostname}", "fail", 
                            f"Found {len(mixed_content_found)} mixed content issues", response_time)
                # Log first few examples
                for i, content_url in enumerate(mixed_content_found[:3]):
                    self.log_test(f"Mixed Content Example {i+1}", "fail", content_url)
                return False
                
        except Exception as e:
            self.log_test(f"Mixed Content {hostname}", "fail", str(e))
            return False

    def test_hsts_preload(self, url):
        """Test HSTS preload configuration"""
        import time
        
        try:
            start_time = time.time()
            response = requests.get(url, timeout=10)
            response_time = (time.time() - start_time) * 1000
            
            hostname = urlparse(url).hostname
            hsts_header = response.headers.get('Strict-Transport-Security', '')
            
            if not hsts_header:
                self.log_test(f"HSTS {hostname}", "fail", "HSTS header not present", response_time)
                return False
            
            # Check HSTS configuration
            hsts_checks = {
                'max-age': False,
                'includeSubDomains': False,
                'preload': False
            }
            
            if 'max-age=' in hsts_header:
                hsts_checks['max-age'] = True
                # Extract max-age value
                import re
                max_age_match = re.search(r'max-age=(\d+)', hsts_header)
                if max_age_match:
                    max_age = int(max_age_match.group(1))
                    if max_age >= 31536000:  # 1 year
                        hsts_checks['max-age'] = True
            
            if 'includeSubDomains' in hsts_header:
                hsts_checks['includeSubDomains'] = True
            
            if 'preload' in hsts_header:
                hsts_checks['preload'] = True
            
            passed_checks = sum(hsts_checks.values())
            
            if passed_checks == 3:
                self.log_test(f"HSTS Configuration {hostname}", "pass", 
                            f"Full HSTS: {hsts_header}", response_time)
                return True
            elif passed_checks >= 2:
                missing = [k for k, v in hsts_checks.items() if not v]
                self.log_test(f"HSTS Configuration {hostname}", "warning", 
                            f"Missing: {', '.join(missing)}", response_time)
                return True
            else:
                self.log_test(f"HSTS Configuration {hostname}", "fail", 
                            f"Insufficient HSTS: {hsts_header}", response_time)
                return False
                
        except Exception as e:
            self.log_test(f"HSTS Configuration {hostname}", "fail", str(e))
            return False

    def test_tls_version(self, url):
        """Test TLS version support"""
        import time
        
        try:
            parsed_url = urlparse(url)
            hostname = parsed_url.hostname
            port = parsed_url.port or 443
            
            start_time = time.time()
            
            # Test TLS 1.2 and 1.3 support
            tls_versions = {
                'TLS 1.2': ssl.PROTOCOL_TLSv1_2,
                'TLS 1.3': getattr(ssl, 'PROTOCOL_TLS', ssl.PROTOCOL_TLSv1_2)
            }
            
            supported_versions = []
            
            for version_name, protocol in tls_versions.items():
                try:
                    context = ssl.SSLContext(protocol)
                    with socket.create_connection((hostname, port), timeout=5) as sock:
                        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                            supported_versions.append(version_name)
                except:
                    pass
            
            response_time = (time.time() - start_time) * 1000
            
            if 'TLS 1.3' in supported_versions:
                self.log_test(f"TLS Version {hostname}", "pass", 
                            f"Supports: {', '.join(supported_versions)}", response_time)
                return True
            elif 'TLS 1.2' in supported_versions:
                self.log_test(f"TLS Version {hostname}", "warning", 
                            f"Supports: {', '.join(supported_versions)} (consider TLS 1.3)", response_time)
                return True
            else:
                self.log_test(f"TLS Version {hostname}", "fail", 
                            "No modern TLS support detected", response_time)
                return False
                
        except Exception as e:
            self.log_test(f"TLS Version {hostname}", "fail", str(e))
            return False

    def test_frontend_ssl(self):
        """Test frontend SSL configuration"""
        print("\n" + "-" * 40)
        print("Frontend SSL/HTTPS Tests")
        print("-" * 40)
        
        self.test_ssl_certificate(self.frontend_url)
        self.test_https_redirect(self.frontend_url)
        self.test_security_headers(self.frontend_url)
        self.test_mixed_content(self.frontend_url)
        self.test_hsts_preload(self.frontend_url)
        self.test_tls_version(self.frontend_url)

    def test_backend_ssl(self):
        """Test backend SSL configuration"""
        print("\n" + "-" * 40)
        print("Backend SSL/HTTPS Tests")
        print("-" * 40)
        
        health_url = f"{self.backend_url}/health/"
        
        self.test_ssl_certificate(self.backend_url)
        self.test_https_redirect(self.backend_url)
        self.test_security_headers(health_url)
        self.test_hsts_preload(health_url)
        self.test_tls_version(self.backend_url)

    def test_cross_origin_security(self):
        """Test cross-origin security between frontend and backend"""
        print("\n" + "-" * 40)
        print("Cross-Origin Security Tests")
        print("-" * 40)
        
        try:
            # Test CORS preflight with HTTPS origins
            response = requests.options(
                f"{self.backend_url}/api/v1/auth/login/",
                headers={
                    'Origin': self.frontend_url,
                    'Access-Control-Request-Method': 'POST',
                    'Access-Control-Request-Headers': 'Content-Type,Authorization'
                },
                timeout=10
            )
            
            if response.status_code == 200:
                cors_origin = response.headers.get('Access-Control-Allow-Origin')
                if cors_origin == self.frontend_url:
                    self.log_test("CORS HTTPS Origin", "pass", 
                                f"Frontend origin allowed: {cors_origin}")
                else:
                    self.log_test("CORS HTTPS Origin", "fail", 
                                f"Origin mismatch: got {cors_origin}, expected {self.frontend_url}")
            else:
                self.log_test("CORS HTTPS Origin", "fail", 
                            f"CORS preflight failed: HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("CORS HTTPS Origin", "fail", str(e))

    def run_all_tests(self):
        """Run all SSL/HTTPS tests"""
        print(f"TikTrue Platform SSL/HTTPS Test Suite")
        print(f"Frontend URL: {self.frontend_url}")
        print(f"Backend URL: {self.backend_url}")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        self.test_frontend_ssl()
        self.test_backend_ssl()
        self.test_cross_origin_security()
        
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("SSL/HTTPS TEST SUMMARY")
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
            print(f"\n❌ {failed} tests failed - SSL/HTTPS configuration has issues")
            print("\nFailed Tests:")
            for result in self.test_results:
                if result['status'] == 'fail':
                    print(f"  - {result['test']}: {result['details']}")
        elif warnings > 0:
            print(f"\n⚠️  {warnings} tests have warnings - SSL/HTTPS mostly configured")
        else:
            print(f"\n✅ All tests passed - SSL/HTTPS is properly configured")
        
        # Save results to file
        with open('ssl_https_test_results.json', 'w') as f:
            json.dump(self.test_results, f, indent=2)
        print(f"\nDetailed results saved to: ssl_https_test_results.json")

def main():
    """Main function"""
    frontend_url = "https://tiktrue.com"
    backend_url = "https://api.tiktrue.com"
    
    # Allow URL override from command line
    if len(sys.argv) > 1:
        frontend_url = sys.argv[1]
    if len(sys.argv) > 2:
        backend_url = sys.argv[2]
    
    tester = SSLHTTPSTester(frontend_url, backend_url)
    tester.run_all_tests()

if __name__ == "__main__":
    main()