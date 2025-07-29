# SSL/HTTPS Configuration Guide for TikTrue Platform

## Overview

This guide documents the SSL/HTTPS configuration for the TikTrue platform, ensuring secure communication between users and both the frontend and backend applications deployed on Liara.

## Current SSL/HTTPS Status

### ✅ Working Correctly

**Backend (api.tiktrue.com):**
- ✅ Valid SSL certificate (Let's Encrypt, expires 2025-10-24)
- ✅ HTTPS redirect (HTTP 301 → HTTPS)
- ✅ All security headers properly configured
- ✅ HSTS with preload enabled
- ✅ TLS 1.2 and 1.3 support
- ✅ CORS working with HTTPS origins

**Frontend (tiktrue.com):**
- ✅ Valid SSL certificate (Let's Encrypt, expires 2025-10-23)
- ✅ HTTPS redirect (HTTP 301 → HTTPS)
- ✅ No mixed content issues
- ✅ TLS 1.2 and 1.3 support
- ✅ Liara configuration has security headers defined

### ❌ Issues to Address

**Frontend Security Headers:**
- ❌ Security headers not being applied by Liara
- ❌ HSTS header missing from responses
- ❌ X-Content-Type-Options header missing
- ❌ X-Frame-Options header missing
- ❌ Referrer-Policy header missing
- ❌ Cross-Origin-Opener-Policy header missing

## SSL Certificate Information

### Frontend Certificate (tiktrue.com)
```
Issuer: Let's Encrypt
Valid Until: 2025-10-23 (88 days remaining)
Subject: CN=tiktrue.com
SAN: tiktrue.com, www.tiktrue.com
```

### Backend Certificate (api.tiktrue.com)
```
Issuer: Let's Encrypt
Valid Until: 2025-10-24 (89 days remaining)
Subject: CN=api.tiktrue.com
SAN: api.tiktrue.com
```

## Backend SSL/HTTPS Configuration

### Django Settings (WORKING ✅)

The Django backend is properly configured with comprehensive security settings:

```python
# Security settings for production
if not DEBUG:
    # SSL/HTTPS Configuration
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # HSTS Configuration
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Cookie security
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'
    
    # Content security headers
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'
    
    # Additional security headers
    SECURE_REFERRER_POLICY = 'same-origin'
    SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
```

### Backend Security Headers (WORKING ✅)

The backend correctly returns these security headers:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: same-origin
Cross-Origin-Opener-Policy: same-origin
```

## Frontend SSL/HTTPS Configuration

### Liara Configuration (CONFIGURED ✅)

The frontend Liara configuration includes comprehensive security headers:

```json
{
  "platform": "static",
  "app": "tiktrue-frontend",
  "static": {
    "spa": true,
    "gzip": true,
    "headers": {
      "/*": {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-XSS-Protection": "1; mode=block",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://fonts.googleapis.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://api.tiktrue.com; frame-ancestors 'none';"
      }
    },
    "redirects": [
      {
        "source": "http://tiktrue.com/*",
        "destination": "https://tiktrue.com/:splat",
        "permanent": true
      },
      {
        "source": "http://www.tiktrue.com/*",
        "destination": "https://tiktrue.com/:splat",
        "permanent": true
      }
    ]
  }
}
```

### Issue: Headers Not Applied (NEEDS DEPLOYMENT ⚠️)

The security headers are configured in `liara.json` but not being applied to the live site. This indicates:

1. **Configuration needs redeployment**: The updated `liara.json` needs to be deployed to Liara
2. **Cache invalidation**: CDN/browser caches may need to be cleared
3. **Configuration format**: May need adjustment for Liara's static platform

## HTTPS Redirects

### Frontend Redirects (WORKING ✅)

HTTP to HTTPS redirects are working correctly:

```
http://tiktrue.com/* → https://tiktrue.com/* (301 Permanent)
http://www.tiktrue.com/* → https://tiktrue.com/* (301 Permanent)
```

### Backend Redirects (WORKING ✅)

Django automatically redirects HTTP to HTTPS:

```
http://api.tiktrue.com/* → https://api.tiktrue.com/* (301 Permanent)
```

## Security Headers Analysis

### Required Security Headers

| Header | Purpose | Backend Status | Frontend Status |
|--------|---------|----------------|-----------------|
| Strict-Transport-Security | HSTS protection | ✅ Working | ❌ Missing |
| X-Content-Type-Options | MIME type sniffing protection | ✅ Working | ❌ Missing |
| X-Frame-Options | Clickjacking protection | ✅ Working | ❌ Missing |
| Referrer-Policy | Referrer information control | ✅ Working | ❌ Missing |
| Cross-Origin-Opener-Policy | Cross-origin isolation | ✅ Working | ❌ Missing |
| Content-Security-Policy | XSS protection | ❌ Not configured | ❌ Missing |

### Security Header Details

**Strict-Transport-Security (HSTS):**
```
max-age=31536000; includeSubDomains; preload
```
- Forces HTTPS for 1 year
- Applies to all subdomains
- Eligible for browser preload list

**X-Content-Type-Options:**
```
nosniff
```
- Prevents MIME type sniffing attacks

**X-Frame-Options:**
```
DENY
```
- Prevents clickjacking by denying iframe embedding

**Referrer-Policy:**
```
strict-origin-when-cross-origin
```
- Controls referrer information sent with requests

**Content-Security-Policy:**
```
default-src 'self'; 
script-src 'self' 'unsafe-inline' 'unsafe-eval' https://fonts.googleapis.com; 
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; 
font-src 'self' https://fonts.gstatic.com; 
img-src 'self' data: https:; 
connect-src 'self' https://api.tiktrue.com; 
frame-ancestors 'none';
```
- Comprehensive XSS protection policy

## Mixed Content Analysis

### Current Status (WORKING ✅)

No mixed content issues detected:
- ✅ All resources loaded over HTTPS
- ✅ No HTTP resources in HTTPS pages
- ✅ External resources (fonts, etc.) use HTTPS

### External Resources

All external resources properly use HTTPS:
```html
<!-- Google Fonts -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
```

## TLS Configuration

### TLS Version Support (WORKING ✅)

Both frontend and backend support modern TLS versions:
- ✅ TLS 1.2 supported
- ✅ TLS 1.3 supported
- ❌ TLS 1.0/1.1 disabled (secure)

### Cipher Suites

Modern, secure cipher suites are used by Let's Encrypt certificates.

## CORS with HTTPS

### Current Status (WORKING ✅)

CORS is properly configured to work with HTTPS:
- ✅ Frontend origin (https://tiktrue.com) allowed
- ✅ Preflight requests work correctly
- ✅ Credentials properly handled
- ✅ All CORS headers present

## Deployment Instructions

### Frontend Deployment (TO FIX HEADERS)

To apply the security headers configuration:

1. **Deploy Updated Configuration:**
   ```bash
   cd frontend
   liara deploy
   ```

2. **Verify Deployment:**
   ```bash
   curl -I https://tiktrue.com
   ```

3. **Clear CDN Cache (if needed):**
   ```bash
   liara app:cache:clear --app tiktrue-frontend
   ```

### Backend Deployment (ALREADY WORKING)

The backend is already properly configured and deployed.

## Testing and Validation

### Automated Testing

Use the provided test scripts to validate SSL/HTTPS configuration:

```bash
# Test backend SSL/HTTPS
cd backend
python test_ssl_https.py

# Test frontend SSL configuration
cd frontend
node test_ssl_configuration.js
```

### Manual Testing

Test SSL/HTTPS manually:

```bash
# Test SSL certificate
openssl s_client -connect tiktrue.com:443 -servername tiktrue.com

# Test security headers
curl -I https://tiktrue.com
curl -I https://api.tiktrue.com

# Test HTTPS redirect
curl -I http://tiktrue.com
curl -I http://api.tiktrue.com
```

### Browser Testing

1. Open https://tiktrue.com in browser
2. Check Developer Tools → Security tab
3. Verify certificate is valid
4. Check Network tab for security headers
5. Ensure no mixed content warnings

## Security Recommendations

### Immediate Actions Required

1. **Deploy Frontend Configuration:**
   - Redeploy frontend to apply security headers
   - Verify headers are being returned

2. **Monitor Certificate Expiration:**
   - Backend cert expires: 2025-10-24 (89 days)
   - Frontend cert expires: 2025-10-23 (88 days)

### Future Enhancements

1. **Content Security Policy:**
   - Implement stricter CSP rules
   - Remove 'unsafe-inline' and 'unsafe-eval' where possible

2. **Certificate Pinning:**
   - Consider implementing HPKP for additional security

3. **Security Monitoring:**
   - Set up automated SSL certificate monitoring
   - Monitor security header compliance

## Troubleshooting

### Common Issues

1. **Headers Not Applied:**
   - Redeploy Liara configuration
   - Clear CDN/browser cache
   - Check Liara logs for errors

2. **Mixed Content Errors:**
   - Ensure all resources use HTTPS
   - Update hardcoded HTTP URLs

3. **Certificate Issues:**
   - Let's Encrypt auto-renewal should handle this
   - Contact Liara support if issues persist

4. **CORS Errors with HTTPS:**
   - Verify CORS_ALLOWED_ORIGINS includes HTTPS URLs
   - Check preflight request handling

### Debug Commands

```bash
# Check SSL certificate details
openssl s_client -connect tiktrue.com:443 -servername tiktrue.com | openssl x509 -noout -dates

# Test specific security headers
curl -H "Origin: https://tiktrue.com" -I https://api.tiktrue.com/api/v1/auth/login/

# Check TLS version support
nmap --script ssl-enum-ciphers -p 443 tiktrue.com
```

## Monitoring and Maintenance

### SSL Certificate Monitoring

Set up monitoring for:
- Certificate expiration dates
- Certificate chain validity
- TLS configuration changes

### Security Header Monitoring

Regular checks for:
- HSTS header presence and configuration
- CSP policy effectiveness
- Security header compliance

### Performance Impact

Security headers have minimal performance impact:
- Headers add ~1KB to response size
- HSTS reduces future connection overhead
- CSP may block malicious resources

## Conclusion

### Current Status Summary

**Backend SSL/HTTPS: ✅ FULLY CONFIGURED**
- All security measures properly implemented
- Comprehensive security headers
- Valid SSL certificates
- HTTPS redirects working

**Frontend SSL/HTTPS: ⚠️ PARTIALLY CONFIGURED**
- SSL certificates valid and working
- HTTPS redirects working
- Security headers configured but not applied
- Needs redeployment to activate headers

### Next Steps

1. **Deploy frontend configuration** to apply security headers
2. **Verify headers are working** with test scripts
3. **Monitor certificate expiration** dates
4. **Regular security audits** using provided test tools

The SSL/HTTPS configuration is comprehensive and follows security best practices. Once the frontend headers are deployed, the platform will have enterprise-grade SSL/HTTPS security.

---

*Last Updated: July 27, 2025*
*Status: Backend Complete ✅ | Frontend Needs Deployment ⚠️*