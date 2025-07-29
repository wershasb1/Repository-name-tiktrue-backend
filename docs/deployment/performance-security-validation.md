# Website Performance and Security Validation Guide

## Overview

This document provides comprehensive procedures for validating the performance and security of the TikTrue platform deployed on Liara.

## Table of Contents

1. [Performance Validation](#performance-validation)
2. [Security Validation](#security-validation)
3. [SSL Certificate Validation](#ssl-certificate-validation)
4. [Security Headers Validation](#security-headers-validation)
5. [CORS Configuration Validation](#cors-configuration-validation)
6. [Automated Validation Scripts](#automated-validation-scripts)
7. [Performance Benchmarks](#performance-benchmarks)
8. [Security Compliance Checklist](#security-compliance-checklist)

## Performance Validation

### Website Loading Speed Tests

#### Frontend Performance Metrics
- **Target Response Time**: < 2 seconds for initial page load
- **Target Time to First Byte (TTFB)**: < 500ms
- **Target Largest Contentful Paint (LCP)**: < 2.5 seconds
- **Target First Input Delay (FID)**: < 100ms
- **Target Cumulative Layout Shift (CLS)**: < 0.1

#### Backend API Performance Metrics
- **Target API Response Time**: < 200ms for simple endpoints
- **Target Database Query Time**: < 100ms for standard queries
- **Target Concurrent Users**: Support for 100+ concurrent users
- **Target Uptime**: 99.9% availability

### Performance Testing Commands

#### Basic Response Time Testing
```bash
# Test frontend response time
curl -o /dev/null -s -w "Connect: %{time_connect}s\nTTFB: %{time_starttransfer}s\nTotal: %{time_total}s\n" https://tiktrue.com

# Test backend API response time
curl -o /dev/null -s -w "Connect: %{time_connect}s\nTTFB: %{time_starttransfer}s\nTotal: %{time_total}s\n" https://api.tiktrue.com/api/health/

# Test with multiple requests
for i in {1..10}; do
    curl -o /dev/null -s -w "%{time_total}s\n" https://tiktrue.com
done | awk '{sum+=$1} END {print "Average: " sum/NR "s"}'
```

#### Load Testing with Apache Bench
```bash
# Test concurrent requests to frontend
ab -n 100 -c 10 https://tiktrue.com/

# Test concurrent requests to API
ab -n 100 -c 10 https://api.tiktrue.com/api/health/

# Test with authentication (if needed)
ab -n 50 -c 5 -H "Authorization: Bearer YOUR_TOKEN" https://api.tiktrue.com/api/auth/user/
```

#### Advanced Load Testing with wrk
```bash
# Install wrk (if available)
# Ubuntu: sudo apt-get install wrk
# macOS: brew install wrk

# Test frontend under load
wrk -t12 -c400 -d30s https://tiktrue.com/

# Test API under load
wrk -t12 -c400 -d30s https://api.tiktrue.com/api/health/

# Test with custom script
wrk -t12 -c400 -d30s -s post.lua https://api.tiktrue.com/api/auth/login/
```

### Performance Monitoring Tools

#### Google PageSpeed Insights
```bash
# Use online tool or API
curl "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=https://tiktrue.com&key=YOUR_API_KEY"
```

#### GTmetrix Analysis
- Visit: https://gtmetrix.com/
- Enter URL: https://tiktrue.com
- Analyze performance metrics

#### WebPageTest
- Visit: https://www.webpagetest.org/
- Test URL: https://tiktrue.com
- Review waterfall charts and metrics

## Security Validation

### SSL/TLS Configuration Testing

#### SSL Certificate Validation
```bash
# Check SSL certificate details
echo | openssl s_client -servername tiktrue.com -connect tiktrue.com:443 2>/dev/null | openssl x509 -noout -text

# Check certificate expiration
echo | openssl s_client -servername tiktrue.com -connect tiktrue.com:443 2>/dev/null | openssl x509 -noout -dates

# Check certificate chain
echo | openssl s_client -servername tiktrue.com -connect tiktrue.com:443 -showcerts 2>/dev/null

# Test SSL Labs rating
curl -s "https://api.ssllabs.com/api/v3/analyze?host=tiktrue.com" | jq '.endpoints[0].grade'
```

#### TLS Configuration Testing
```bash
# Test TLS versions
nmap --script ssl-enum-ciphers -p 443 tiktrue.com

# Test for weak ciphers
sslscan tiktrue.com

# Test HSTS implementation
curl -I https://tiktrue.com | grep -i strict-transport-security
```

### Security Headers Validation

#### Required Security Headers Checklist
- [ ] **Strict-Transport-Security (HSTS)**
- [ ] **X-Content-Type-Options**
- [ ] **X-Frame-Options**
- [ ] **X-XSS-Protection**
- [ ] **Content-Security-Policy**
- [ ] **Referrer-Policy**
- [ ] **Permissions-Policy**

#### Security Headers Testing Script
```bash
#!/bin/bash
# test_security_headers.sh

URL="https://tiktrue.com"
echo "Testing security headers for: $URL"

# Get headers
HEADERS=$(curl -I -s "$URL")

# Check each security header
check_header() {
    local header=$1
    local description=$2
    
    if echo "$HEADERS" | grep -qi "$header"; then
        echo "✓ $description: Present"
    else
        echo "✗ $description: Missing"
    fi
}

check_header "strict-transport-security" "HSTS"
check_header "x-content-type-options" "Content Type Options"
check_header "x-frame-options" "Frame Options"
check_header "x-xss-protection" "XSS Protection"
check_header "content-security-policy" "Content Security Policy"
check_header "referrer-policy" "Referrer Policy"
check_header "permissions-policy" "Permissions Policy"
```

### Vulnerability Scanning

#### OWASP ZAP Scanning
```bash
# Install OWASP ZAP
# Download from: https://www.zaproxy.org/download/

# Run baseline scan
zap-baseline.py -t https://tiktrue.com -r zap_report.html

# Run full scan (more comprehensive)
zap-full-scan.py -t https://tiktrue.com -r zap_full_report.html
```

#### Nikto Web Scanner
```bash
# Install Nikto
# Ubuntu: sudo apt-get install nikto
# macOS: brew install nikto

# Scan website
nikto -h https://tiktrue.com -output nikto_report.txt
```

### Authentication Security Testing

#### JWT Token Security
```bash
# Test JWT token structure (decode without verification)
echo "YOUR_JWT_TOKEN" | cut -d. -f2 | base64 -d | jq .

# Test token expiration handling
curl -H "Authorization: Bearer EXPIRED_TOKEN" https://api.tiktrue.com/api/auth/user/

# Test invalid token handling
curl -H "Authorization: Bearer INVALID_TOKEN" https://api.tiktrue.com/api/auth/user/
```

#### Password Security Testing
```bash
# Test password strength requirements
curl -X POST https://api.tiktrue.com/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"weak"}'

# Test account lockout (if implemented)
for i in {1..10}; do
    curl -X POST https://api.tiktrue.com/api/auth/login/ \
      -H "Content-Type: application/json" \
      -d '{"username":"testuser","password":"wrongpassword"}'
done
```

## SSL Certificate Validation

### Certificate Information Extraction
```bash
#!/bin/bash
# ssl_certificate_check.sh

DOMAIN="tiktrue.com"
API_DOMAIN="api.tiktrue.com"

check_ssl_cert() {
    local domain=$1
    echo "Checking SSL certificate for: $domain"
    
    # Get certificate info
    CERT_INFO=$(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | openssl x509 -noout -text)
    
    # Extract key information
    echo "Subject: $(echo "$CERT_INFO" | grep "Subject:" | head -1)"
    echo "Issuer: $(echo "$CERT_INFO" | grep "Issuer:" | head -1)"
    echo "Valid from: $(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | openssl x509 -noout -startdate)"
    echo "Valid until: $(echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | openssl x509 -noout -enddate)"
    
    # Check if certificate is valid
    echo | openssl s_client -servername "$domain" -connect "$domain:443" 2>/dev/null | openssl x509 -noout -checkend 86400
    if [ $? -eq 0 ]; then
        echo "✓ Certificate is valid for at least 24 hours"
    else
        echo "✗ Certificate expires within 24 hours"
    fi
    
    echo "---"
}

check_ssl_cert "$DOMAIN"
check_ssl_cert "$API_DOMAIN"
```

### Certificate Chain Validation
```bash
# Verify certificate chain
openssl s_client -servername tiktrue.com -connect tiktrue.com:443 -verify_return_error

# Check for certificate transparency logs
curl -s "https://crt.sh/?q=tiktrue.com&output=json" | jq '.[0:5]'
```

## Security Headers Validation

### Content Security Policy (CSP) Testing
```bash
# Check CSP header
curl -I https://tiktrue.com | grep -i content-security-policy

# Test CSP violations (manual testing required)
# Open browser developer tools and check for CSP violations
```

### HSTS Implementation Testing
```bash
# Check HSTS header
curl -I https://tiktrue.com | grep -i strict-transport-security

# Test HSTS preload status
curl -s "https://hstspreload.org/api/v2/status?domain=tiktrue.com"
```

## CORS Configuration Validation

### CORS Headers Testing
```bash
#!/bin/bash
# test_cors.sh

API_URL="https://api.tiktrue.com"
FRONTEND_URL="https://tiktrue.com"

echo "Testing CORS configuration..."

# Test preflight request
curl -X OPTIONS "$API_URL/api/health/" \
  -H "Origin: $FRONTEND_URL" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Content-Type" \
  -v

# Test actual request with origin
curl -X GET "$API_URL/api/health/" \
  -H "Origin: $FRONTEND_URL" \
  -v

# Test with invalid origin
curl -X GET "$API_URL/api/health/" \
  -H "Origin: https://malicious-site.com" \
  -v
```

### CORS Policy Validation
```javascript
// Frontend CORS test (run in browser console)
fetch('https://api.tiktrue.com/api/health/', {
    method: 'GET',
    headers: {
        'Content-Type': 'application/json'
    }
})
.then(response => {
    console.log('CORS test successful:', response.status);
})
.catch(error => {
    console.error('CORS test failed:', error);
});
```

## Automated Validation Scripts

### Comprehensive Security and Performance Validator
```python
#!/usr/bin/env python3
# validate_security_performance.py

import requests
import ssl
import socket
import time
import json
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
            'cors': {}
        }
    
    def test_performance(self):
        """Test website performance"""
        print("Testing performance...")
        
        # Test frontend response time
        start_time = time.time()
        try:
            response = requests.get(self.frontend_url, timeout=10)
            response_time = time.time() - start_time
            
            self.results['performance']['frontend'] = {
                'response_time': response_time,
                'status_code': response.status_code,
                'content_length': len(response.content),
                'passed': response_time < 2.0 and response.status_code == 200
            }
        except Exception as e:
            self.results['performance']['frontend'] = {
                'error': str(e),
                'passed': False
            }
        
        # Test backend API response time
        start_time = time.time()
        try:
            response = requests.get(f"{self.backend_url}/api/health/", timeout=10)
            response_time = time.time() - start_time
            
            self.results['performance']['backend'] = {
                'response_time': response_time,
                'status_code': response.status_code,
                'passed': response_time < 0.5 and response.status_code == 200
            }
        except Exception as e:
            self.results['performance']['backend'] = {
                'error': str(e),
                'passed': False
            }
    
    def test_ssl_certificate(self):
        """Test SSL certificate"""
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
                        'passed': days_until_expiry > 30
                    }
        except Exception as e:
            self.results['ssl'] = {
                'error': str(e),
                'passed': False
            }
    
    def test_security_headers(self):
        """Test security headers"""
        print("Testing security headers...")
        
        try:
            response = requests.get(self.frontend_url, timeout=10)
            headers = response.headers
            
            required_headers = {
                'strict-transport-security': 'HSTS',
                'x-content-type-options': 'Content Type Options',
                'x-frame-options': 'Frame Options',
                'x-xss-protection': 'XSS Protection',
                'content-security-policy': 'Content Security Policy'
            }
            
            header_results = {}
            for header, description in required_headers.items():
                present = header in headers or header.title() in headers
                header_results[header] = {
                    'present': present,
                    'value': headers.get(header, headers.get(header.title(), '')),
                    'description': description
                }
            
            self.results['headers'] = {
                'results': header_results,
                'passed': all(result['present'] for result in header_results.values())
            }
            
        except Exception as e:
            self.results['headers'] = {
                'error': str(e),
                'passed': False
            }
    
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
                'access-control-allow-headers': response.headers.get('Access-Control-Allow-Headers')
            }
            
            self.results['cors'] = {
                'preflight_status': response.status_code,
                'headers': cors_headers,
                'passed': response.status_code == 200 and cors_headers['access-control-allow-origin']
            }
            
        except Exception as e:
            self.results['cors'] = {
                'error': str(e),
                'passed': False
            }
    
    def test_https_redirect(self):
        """Test HTTPS redirect"""
        print("Testing HTTPS redirect...")
        
        try:
            http_url = self.frontend_url.replace('https://', 'http://')
            response = requests.get(http_url, allow_redirects=False, timeout=10)
            
            self.results['security']['https_redirect'] = {
                'status_code': response.status_code,
                'location': response.headers.get('Location', ''),
                'passed': response.status_code in [301, 302, 308]
            }
            
        except Exception as e:
            self.results['security']['https_redirect'] = {
                'error': str(e),
                'passed': False
            }
    
    def generate_report(self):
        """Generate validation report"""
        print("\n" + "="*60)
        print("SECURITY AND PERFORMANCE VALIDATION REPORT")
        print("="*60)
        
        # Performance results
        print("\nPERFORMANCE RESULTS:")
        if 'frontend' in self.results['performance']:
            frontend = self.results['performance']['frontend']
            if 'response_time' in frontend:
                status = "✓ PASS" if frontend['passed'] else "✗ FAIL"
                print(f"  Frontend Response Time: {frontend['response_time']:.3f}s {status}")
            else:
                print(f"  Frontend: ✗ FAIL - {frontend.get('error', 'Unknown error')}")
        
        if 'backend' in self.results['performance']:
            backend = self.results['performance']['backend']
            if 'response_time' in backend:
                status = "✓ PASS" if backend['passed'] else "✗ FAIL"
                print(f"  Backend Response Time: {backend['response_time']:.3f}s {status}")
            else:
                print(f"  Backend: ✗ FAIL - {backend.get('error', 'Unknown error')}")
        
        # SSL results
        print("\nSSL CERTIFICATE RESULTS:")
        if 'error' not in self.results['ssl']:
            ssl_info = self.results['ssl']
            status = "✓ PASS" if ssl_info['passed'] else "✗ FAIL"
            print(f"  Certificate Validity: {ssl_info['days_until_expiry']} days remaining {status}")
            print(f"  Issuer: {ssl_info['issuer'].get('organizationName', 'Unknown')}")
        else:
            print(f"  SSL Test: ✗ FAIL - {self.results['ssl']['error']}")
        
        # Security headers results
        print("\nSECURITY HEADERS RESULTS:")
        if 'results' in self.results['headers']:
            for header, info in self.results['headers']['results'].items():
                status = "✓ PASS" if info['present'] else "✗ FAIL"
                print(f"  {info['description']}: {status}")
        else:
            print(f"  Headers Test: ✗ FAIL - {self.results['headers'].get('error', 'Unknown error')}")
        
        # CORS results
        print("\nCORS CONFIGURATION RESULTS:")
        if 'error' not in self.results['cors']:
            status = "✓ PASS" if self.results['cors']['passed'] else "✗ FAIL"
            print(f"  CORS Configuration: {status}")
        else:
            print(f"  CORS Test: ✗ FAIL - {self.results['cors']['error']}")
        
        # HTTPS redirect results
        print("\nHTTPS REDIRECT RESULTS:")
        if 'https_redirect' in self.results['security']:
            redirect = self.results['security']['https_redirect']
            if 'status_code' in redirect:
                status = "✓ PASS" if redirect['passed'] else "✗ FAIL"
                print(f"  HTTPS Redirect: HTTP {redirect['status_code']} {status}")
            else:
                print(f"  HTTPS Redirect: ✗ FAIL - {redirect.get('error', 'Unknown error')}")
        
        # Overall summary
        all_tests = []
        if 'frontend' in self.results['performance']:
            all_tests.append(self.results['performance']['frontend'].get('passed', False))
        if 'backend' in self.results['performance']:
            all_tests.append(self.results['performance']['backend'].get('passed', False))
        all_tests.append(self.results['ssl'].get('passed', False))
        all_tests.append(self.results['headers'].get('passed', False))
        all_tests.append(self.results['cors'].get('passed', False))
        if 'https_redirect' in self.results['security']:
            all_tests.append(self.results['security']['https_redirect'].get('passed', False))
        
        passed_tests = sum(all_tests)
        total_tests = len(all_tests)
        
        print(f"\nOVERALL SUMMARY:")
        print(f"  Tests Passed: {passed_tests}/{total_tests}")
        print(f"  Success Rate: {(passed_tests/total_tests*100):.1f}%")
        
        # Save detailed report
        report_file = f"security_performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\nDetailed report saved to: {report_file}")
        
        return passed_tests == total_tests
    
    def run_all_tests(self):
        """Run all validation tests"""
        print("Starting Security and Performance Validation")
        print(f"Frontend URL: {self.frontend_url}")
        print(f"Backend URL: {self.backend_url}")
        print(f"Test started at: {datetime.now()}")
        
        self.test_performance()
        self.test_ssl_certificate()
        self.test_security_headers()
        self.test_cors_configuration()
        self.test_https_redirect()
        
        return self.generate_report()

def main():
    validator = SecurityPerformanceValidator(
        "https://tiktrue.com",
        "https://api.tiktrue.com"
    )
    
    try:
        success = validator.run_all_tests()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\nValidation interrupted by user")
        return 1
    except Exception as e:
        print(f"\nUnexpected error during validation: {str(e)}")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
```

## Performance Benchmarks

### Expected Performance Targets

#### Frontend Performance
- **Page Load Time**: < 2 seconds
- **Time to First Byte**: < 500ms
- **First Contentful Paint**: < 1.5 seconds
- **Largest Contentful Paint**: < 2.5 seconds
- **Cumulative Layout Shift**: < 0.1

#### Backend Performance
- **API Response Time**: < 200ms for simple endpoints
- **Database Query Time**: < 100ms
- **Authentication Time**: < 300ms
- **File Upload Time**: < 5 seconds for 10MB files

#### Concurrent User Support
- **Target Concurrent Users**: 100+
- **Response Time Under Load**: < 1 second
- **Error Rate Under Load**: < 1%

### Performance Monitoring Commands
```bash
# Continuous monitoring script
#!/bin/bash
while true; do
    echo "$(date): $(curl -o /dev/null -s -w "%{time_total}s" https://tiktrue.com)"
    sleep 60
done > performance_monitor.log
```

## Security Compliance Checklist

### OWASP Top 10 Compliance
- [ ] **A01: Broken Access Control** - Proper authentication and authorization
- [ ] **A02: Cryptographic Failures** - Strong encryption and secure data transmission
- [ ] **A03: Injection** - Input validation and parameterized queries
- [ ] **A04: Insecure Design** - Secure architecture and design patterns
- [ ] **A05: Security Misconfiguration** - Proper security headers and configurations
- [ ] **A06: Vulnerable Components** - Updated dependencies and libraries
- [ ] **A07: Authentication Failures** - Strong authentication mechanisms
- [ ] **A08: Software Integrity Failures** - Code signing and integrity checks
- [ ] **A09: Logging Failures** - Comprehensive logging and monitoring
- [ ] **A10: Server-Side Request Forgery** - Input validation and network controls

### Security Best Practices Checklist
- [ ] HTTPS enforced on all endpoints
- [ ] Strong SSL/TLS configuration
- [ ] Security headers implemented
- [ ] CORS properly configured
- [ ] Input validation on all endpoints
- [ ] SQL injection protection
- [ ] XSS protection implemented
- [ ] CSRF protection enabled
- [ ] Rate limiting implemented
- [ ] Secure session management
- [ ] Regular security updates
- [ ] Vulnerability scanning performed

---

**Note**: This validation guide should be executed regularly as part of the deployment and maintenance process to ensure ongoing security and performance standards.