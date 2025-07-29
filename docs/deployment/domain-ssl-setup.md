# Domain Configuration and SSL Setup for TikTrue Platform

This guide covers comprehensive domain configuration and SSL certificate setup for both frontend and backend deployments on Liara.

## Overview

The TikTrue platform uses the following domain structure:
- **Frontend**: `tiktrue.com` (main website)
- **Backend API**: `api.tiktrue.com` (API endpoints)
- **WWW Redirect**: `www.tiktrue.com` → `tiktrue.com`

## Prerequisites

### Required Access
- Domain registrar account (Namecheap, GoDaddy, etc.)
- Liara console access for both apps
- DNS management permissions

### Required Information
- Domain name: `tiktrue.com`
- Liara app names:
  - Frontend: `tiktrue-frontend`
  - Backend: `tiktrue-backend`

## Domain Configuration Process

### Step 1: Add Domains to Liara Apps

#### Frontend Domain Setup

```bash
# Add main domain
liara domain add tiktrue.com --app tiktrue-frontend

# Add www subdomain
liara domain add www.tiktrue.com --app tiktrue-frontend

# Verify domains added
liara domain list --app tiktrue-frontend
```

#### Backend Domain Setup

```bash
# Add API subdomain
liara domain add api.tiktrue.com --app tiktrue-backend

# Verify domain added
liara domain list --app tiktrue-backend
```

### Step 2: DNS Configuration

#### Option A: Using A Records (Recommended)

**For Frontend (tiktrue.com)**:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | @ | 185.231.115.209 | 300 |
| CNAME | www | tiktrue-frontend.liara.run | 300 |

**For Backend (api.tiktrue.com)**:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| CNAME | api | tiktrue-backend.liara.run | 300 |

#### Option B: Using CNAME Records

**For Frontend (if registrar supports CNAME for root)**:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| CNAME | @ | tiktrue-frontend.liara.run | 300 |
| CNAME | www | tiktrue-frontend.liara.run | 300 |

**For Backend**:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| CNAME | api | tiktrue-backend.liara.run | 300 |

### Step 3: DNS Configuration Examples

#### Namecheap Configuration

1. Login to Namecheap account
2. Go to Domain List → Manage
3. Navigate to Advanced DNS tab
4. Add the following records:

```
Type: A Record
Host: @
Value: 185.231.115.209
TTL: 5 min

Type: CNAME Record
Host: www
Value: tiktrue-frontend.liara.run
TTL: 5 min

Type: CNAME Record
Host: api
Value: tiktrue-backend.liara.run
TTL: 5 min
```

#### GoDaddy Configuration

1. Login to GoDaddy account
2. Go to My Products → DNS
3. Add the following records:

```
Type: A
Name: @
Value: 185.231.115.209
TTL: 600

Type: CNAME
Name: www
Value: tiktrue-frontend.liara.run
TTL: 600

Type: CNAME
Name: api
Value: tiktrue-backend.liara.run
TTL: 600
```

#### Cloudflare Configuration

1. Login to Cloudflare dashboard
2. Select your domain
3. Go to DNS → Records
4. Add the following records:

```
Type: A
Name: @
IPv4 address: 185.231.115.209
Proxy status: DNS only (gray cloud)
TTL: Auto

Type: CNAME
Name: www
Target: tiktrue-frontend.liara.run
Proxy status: DNS only (gray cloud)
TTL: Auto

Type: CNAME
Name: api
Target: tiktrue-backend.liara.run
Proxy status: DNS only (gray cloud)
TTL: Auto
```

**Important**: When using Cloudflare, ensure proxy is disabled (gray cloud) for Liara domains.

### Step 4: Verify DNS Propagation

```bash
# Check DNS propagation
nslookup tiktrue.com
nslookup www.tiktrue.com
nslookup api.tiktrue.com

# Check from multiple locations
dig tiktrue.com @8.8.8.8
dig api.tiktrue.com @1.1.1.1

# Use online tools
# https://dnschecker.org/
# https://whatsmydns.net/
```

### Step 5: Test Domain Resolution

```bash
# Test HTTP access (should work before SSL)
curl -I http://tiktrue.com
curl -I http://api.tiktrue.com

# Check if domains resolve to Liara
curl -I http://tiktrue.com | grep -i server
curl -I http://api.tiktrue.com | grep -i server
```

## SSL Certificate Setup

### Automatic SSL Certificate Issuance

Liara automatically issues SSL certificates for verified domains:

1. **Domain Verification**: Liara verifies domain ownership via DNS
2. **Certificate Issuance**: Let's Encrypt certificate is automatically issued
3. **Auto-Renewal**: Certificates are automatically renewed before expiration
4. **HTTPS Redirect**: HTTP traffic is automatically redirected to HTTPS

### SSL Certificate Verification

#### Check Certificate Status

```bash
# Check certificate details
openssl s_client -connect tiktrue.com:443 -servername tiktrue.com

# Check certificate expiration
echo | openssl s_client -connect tiktrue.com:443 -servername tiktrue.com 2>/dev/null | openssl x509 -noout -dates

# Check API certificate
echo | openssl s_client -connect api.tiktrue.com:443 -servername api.tiktrue.com 2>/dev/null | openssl x509 -noout -dates
```

#### Test HTTPS Access

```bash
# Test frontend HTTPS
curl -I https://tiktrue.com

# Test backend HTTPS
curl -I https://api.tiktrue.com

# Test HTTPS redirect
curl -I http://tiktrue.com
# Should return 301/302 redirect to HTTPS
```

### SSL Configuration in Liara

#### Frontend SSL Configuration

Update `frontend/liara.json`:

```json
{
  "platform": "react",
  "app": "tiktrue-frontend",
  "static": {
    "headers": {
      "/*": {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin"
      }
    },
    "redirects": [
      {
        "source": "http://tiktrue.com/*",
        "destination": "https://tiktrue.com/:splat",
        "permanent": true
      },
      {
        "source": "https://www.tiktrue.com/*",
        "destination": "https://tiktrue.com/:splat",
        "permanent": true
      }
    ]
  }
}
```

#### Backend SSL Configuration

Update Django `settings.py`:

```python
# SSL/HTTPS Configuration
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS Configuration
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Additional Security Headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
```

## Advanced SSL Configuration

### Custom Security Headers

#### Frontend Security Headers

```json
{
  "static": {
    "headers": {
      "/*": {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://api.tiktrue.com"
      }
    }
  }
}
```

#### Backend Security Headers

```python
# In settings.py
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Custom middleware for additional headers
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # ... other middleware
]

# Custom security headers
def custom_headers_middleware(get_response):
    def middleware(request):
        response = get_response(request)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        return response
    return middleware
```

### SSL Certificate Monitoring

#### Certificate Expiration Monitoring

```bash
#!/bin/bash
# ssl-monitor.sh - Monitor SSL certificate expiration

check_ssl_expiry() {
    domain=$1
    expiry_date=$(echo | openssl s_client -connect $domain:443 -servername $domain 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)
    expiry_epoch=$(date -d "$expiry_date" +%s)
    current_epoch=$(date +%s)
    days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))
    
    echo "SSL certificate for $domain expires in $days_until_expiry days"
    
    if [ $days_until_expiry -lt 30 ]; then
        echo "WARNING: Certificate expires soon!"
    fi
}

# Check all domains
check_ssl_expiry "tiktrue.com"
check_ssl_expiry "api.tiktrue.com"
```

#### Automated SSL Health Check

```bash
#!/bin/bash
# ssl-health-check.sh - Automated SSL health check

domains=("tiktrue.com" "api.tiktrue.com")

for domain in "${domains[@]}"; do
    echo "Checking SSL for $domain..."
    
    # Check if HTTPS is accessible
    if curl -s -I https://$domain > /dev/null; then
        echo "✓ HTTPS accessible for $domain"
    else
        echo "✗ HTTPS not accessible for $domain"
    fi
    
    # Check certificate validity
    if echo | openssl s_client -connect $domain:443 -servername $domain 2>/dev/null | openssl x509 -noout -checkend 2592000; then
        echo "✓ Certificate valid for $domain"
    else
        echo "✗ Certificate expires within 30 days for $domain"
    fi
    
    echo "---"
done
```

## Troubleshooting

### Common DNS Issues

#### 1. DNS Not Propagating

**Symptoms**: Domain doesn't resolve to Liara servers

**Solutions**:
```bash
# Check DNS propagation status
dig tiktrue.com
nslookup tiktrue.com 8.8.8.8

# Clear local DNS cache
# Windows:
ipconfig /flushdns

# macOS:
sudo dscacheutil -flushcache

# Linux:
sudo systemctl restart systemd-resolved
```

#### 2. Wrong DNS Configuration

**Symptoms**: Domain resolves to wrong IP or server

**Solutions**:
```bash
# Verify DNS records
dig tiktrue.com A
dig api.tiktrue.com CNAME

# Check for conflicting records
dig tiktrue.com ANY

# Verify TTL settings (should be low during setup)
dig tiktrue.com | grep -i ttl
```

#### 3. Subdomain Not Working

**Symptoms**: Main domain works but subdomains don't

**Solutions**:
```bash
# Check subdomain DNS
dig api.tiktrue.com
dig www.tiktrue.com

# Verify CNAME records point to correct Liara app
# api.tiktrue.com should point to tiktrue-backend.liara.run
# www.tiktrue.com should point to tiktrue-frontend.liara.run
```

### Common SSL Issues

#### 1. SSL Certificate Not Issued

**Symptoms**: HTTPS not working, certificate errors

**Solutions**:
```bash
# Check domain verification status in Liara dashboard
liara domain list --app tiktrue-frontend
liara domain list --app tiktrue-backend

# Verify DNS is correctly configured
nslookup tiktrue.com
nslookup api.tiktrue.com

# Wait for certificate issuance (can take up to 24 hours)
# Check Liara logs for certificate issuance messages
liara logs --app tiktrue-frontend | grep -i ssl
```

#### 2. Mixed Content Errors

**Symptoms**: HTTPS page loading HTTP resources

**Solutions**:
```bash
# Check for HTTP resources in HTTPS pages
curl -s https://tiktrue.com | grep -i "http://"

# Update all resource URLs to HTTPS or relative URLs
# In React components, use relative URLs:
// Instead of: http://api.tiktrue.com/api/v1/
// Use: https://api.tiktrue.com/api/v1/
// Or: /api/v1/ (if same domain)
```

#### 3. HSTS Issues

**Symptoms**: Browser security warnings, HSTS errors

**Solutions**:
```bash
# Check HSTS header
curl -I https://tiktrue.com | grep -i strict-transport

# Clear HSTS cache in browser
# Chrome: chrome://net-internals/#hsts
# Firefox: Clear browsing data including security settings

# Verify HSTS configuration in liara.json or Django settings
```

#### 4. Certificate Chain Issues

**Symptoms**: Certificate warnings in some browsers

**Solutions**:
```bash
# Check certificate chain
openssl s_client -connect tiktrue.com:443 -servername tiktrue.com -showcerts

# Verify intermediate certificates are included
# Liara automatically handles certificate chains

# Test with SSL Labs
# https://www.ssllabs.com/ssltest/analyze.html?d=tiktrue.com
```

### Performance Optimization

#### 1. DNS Performance

```bash
# Use faster DNS servers
# Add to /etc/resolv.conf (Linux) or network settings:
nameserver 1.1.1.1
nameserver 8.8.8.8

# Optimize TTL values
# During setup: TTL = 300 (5 minutes)
# After stable: TTL = 3600 (1 hour) or higher
```

#### 2. SSL Performance

```bash
# Enable HTTP/2 (automatically enabled by Liara)
curl -I https://tiktrue.com --http2

# Enable OCSP stapling (handled by Liara)
# Verify with SSL Labs test

# Optimize cipher suites (handled by Liara)
# Modern browsers get optimal cipher suites automatically
```

## Security Best Practices

### 1. Domain Security

- Use strong passwords for domain registrar account
- Enable two-factor authentication on domain registrar
- Lock domain transfers when not needed
- Monitor domain expiration dates
- Use domain privacy protection

### 2. DNS Security

- Use reputable DNS providers
- Enable DNSSEC if supported
- Monitor DNS changes
- Use DNS monitoring services
- Implement DNS CAA records

### 3. SSL Security

- Monitor certificate expiration
- Use strong cipher suites (handled by Liara)
- Implement HSTS with preload
- Use Certificate Transparency monitoring
- Regular security audits

### 4. CAA Records

Add Certificate Authority Authorization records:

```
Type: CAA
Name: @
Value: 0 issue "letsencrypt.org"

Type: CAA
Name: @
Value: 0 issuewild "letsencrypt.org"

Type: CAA
Name: @
Value: 0 iodef "mailto:admin@tiktrue.com"
```

## Monitoring and Maintenance

### 1. Domain Monitoring

```bash
# Monitor domain expiration
whois tiktrue.com | grep -i expir

# Monitor DNS changes
dig tiktrue.com | tee dns-check-$(date +%Y%m%d).log

# Set up automated monitoring
# Use services like UptimeRobot, Pingdom, or custom scripts
```

### 2. SSL Monitoring

```bash
# Daily SSL check script
#!/bin/bash
domains=("tiktrue.com" "api.tiktrue.com")

for domain in "${domains[@]}"; do
    expiry=$(echo | openssl s_client -connect $domain:443 -servername $domain 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)
    days_left=$(( ($(date -d "$expiry" +%s) - $(date +%s)) / 86400 ))
    
    if [ $days_left -lt 30 ]; then
        echo "WARNING: SSL certificate for $domain expires in $days_left days"
        # Send alert email or notification
    fi
done
```

### 3. Performance Monitoring

```bash
# Monitor DNS resolution time
dig tiktrue.com | grep "Query time"

# Monitor SSL handshake time
curl -w "@curl-format.txt" -o /dev/null -s https://tiktrue.com

# Monitor overall page load time
curl -w "Total time: %{time_total}s\n" -o /dev/null -s https://tiktrue.com
```

## Emergency Procedures

### 1. Domain Issues

```bash
# If domain is not resolving:
1. Check DNS configuration at registrar
2. Verify Liara domain settings
3. Check for DNS propagation delays
4. Contact domain registrar support if needed

# If domain is hijacked:
1. Immediately contact domain registrar
2. Change registrar account passwords
3. Enable domain lock
4. Document all changes for investigation
```

### 2. SSL Issues

```bash
# If SSL certificate expires:
1. Check Liara dashboard for certificate status
2. Verify domain ownership
3. Contact Liara support if auto-renewal failed
4. Temporarily use HTTP if critical (not recommended)

# If SSL is compromised:
1. Revoke current certificate
2. Generate new certificate
3. Update all references
4. Monitor for unauthorized usage
```

### 3. DNS Poisoning

```bash
# If DNS is compromised:
1. Change DNS provider passwords
2. Review all DNS records
3. Remove unauthorized records
4. Enable DNSSEC if available
5. Monitor DNS queries for anomalies
```

## Support and Resources

### Liara Resources
- [Domain Configuration](https://docs.liara.ir/domains/)
- [SSL Certificates](https://docs.liara.ir/domains/ssl/)
- [DNS Management](https://docs.liara.ir/domains/dns/)

### External Tools
- [SSL Labs Test](https://www.ssllabs.com/ssltest/)
- [DNS Checker](https://dnschecker.org/)
- [What's My DNS](https://whatsmydns.net/)
- [Certificate Transparency Monitor](https://crt.sh/)

### Emergency Contacts
- Liara Support: https://liara.ir/support
- Domain Registrar Support: [Registrar Contact]
- DNS Provider Support: [DNS Provider Contact]
- Development Team: [Team Contact Information]

---

**Last Updated**: [Current Date]
**Version**: 1.0
**Maintainer**: TikTrue Development Team