#!/usr/bin/env node
/**
 * SSL/HTTPS Configuration Test for TikTrue Frontend
 * 
 * This script tests SSL/HTTPS configuration and security headers
 * for the frontend deployment on Liara.
 */

const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

class SSLConfigurationTester {
    constructor() {
        this.testResults = [];
        this.frontendUrl = 'https://tiktrue.com';
        this.backendUrl = 'https://api.tiktrue.com';
    }

    logTest(testName, status, details = null) {
        const result = {
            test: testName,
            status: status,
            timestamp: new Date().toISOString(),
            details: details
        };
        this.testResults.push(result);
        
        const statusIcon = status === "pass" ? "✓" : status === "fail" ? "✗" : "⚠";
        console.log(`${statusIcon} ${testName}: ${status.toUpperCase()}`);
        if (details) {
            console.log(`  ${details}`);
        }
    }

    async makeRequest(url, options = {}) {
        return new Promise((resolve, reject) => {
            const urlObj = new URL(url);
            const isHttps = urlObj.protocol === 'https:';
            const client = isHttps ? https : http;
            
            const requestOptions = {
                hostname: urlObj.hostname,
                port: urlObj.port || (isHttps ? 443 : 80),
                path: urlObj.pathname + urlObj.search,
                method: options.method || 'GET',
                headers: options.headers || {},
                timeout: 10000,
                ...options
            };

            const req = client.request(requestOptions, (res) => {
                let data = '';
                res.on('data', (chunk) => data += chunk);
                res.on('end', () => {
                    resolve({
                        statusCode: res.statusCode,
                        headers: res.headers,
                        data: data
                    });
                });
            });

            req.on('error', reject);
            req.on('timeout', () => reject(new Error('Request timeout')));
            req.end();
        });
    }

    async testLiaraConfiguration() {
        console.log("\n" + "-".repeat(40));
        console.log("Liara Configuration Test");
        console.log("-".repeat(40));

        const liaraPath = path.join(__dirname, 'liara.json');
        
        if (fs.existsSync(liaraPath)) {
            try {
                const content = fs.readFileSync(liaraPath, 'utf8');
                const liaraConfig = JSON.parse(content);
                
                this.logTest("liara.json exists", "pass", "Configuration file found");
                
                // Check security headers configuration
                if (liaraConfig.static && liaraConfig.static.headers) {
                    const headers = liaraConfig.static.headers;
                    
                    // Check if headers are properly structured
                    if (headers['/*']) {
                        this.logTest("Security headers structure", "pass", "Headers configured for all routes");
                        
                        const requiredHeaders = [
                            'Strict-Transport-Security',
                            'X-Content-Type-Options',
                            'X-Frame-Options',
                            'Referrer-Policy',
                            'Cross-Origin-Opener-Policy'
                        ];
                        
                        const configuredHeaders = headers['/*'];
                        const missingHeaders = requiredHeaders.filter(header => !configuredHeaders[header]);
                        
                        if (missingHeaders.length === 0) {
                            this.logTest("Required security headers", "pass", "All required headers configured");
                        } else {
                            this.logTest("Required security headers", "fail", `Missing: ${missingHeaders.join(', ')}`);
                        }
                        
                        // Check HSTS configuration
                        const hsts = configuredHeaders['Strict-Transport-Security'];
                        if (hsts && hsts.includes('max-age=31536000') && hsts.includes('includeSubDomains')) {
                            this.logTest("HSTS configuration", "pass", hsts);
                        } else {
                            this.logTest("HSTS configuration", "fail", `Invalid HSTS: ${hsts}`);
                        }
                        
                        // Check CSP configuration
                        if (configuredHeaders['Content-Security-Policy']) {
                            this.logTest("CSP configuration", "pass", "Content Security Policy configured");
                        } else {
                            this.logTest("CSP configuration", "warning", "Content Security Policy not configured");
                        }
                        
                    } else {
                        this.logTest("Security headers structure", "fail", "Headers not properly structured");
                    }
                } else {
                    this.logTest("Security headers configuration", "fail", "No security headers configured");
                }
                
                // Check HTTPS redirects
                if (liaraConfig.static && liaraConfig.static.redirects) {
                    const redirects = liaraConfig.static.redirects;
                    const httpsRedirects = redirects.filter(r => 
                        r.source.startsWith('http://') && r.destination.startsWith('https://')
                    );
                    
                    if (httpsRedirects.length > 0) {
                        this.logTest("HTTPS redirects", "pass", `${httpsRedirects.length} HTTP→HTTPS redirects configured`);
                    } else {
                        this.logTest("HTTPS redirects", "fail", "No HTTP→HTTPS redirects configured");
                    }
                } else {
                    this.logTest("HTTPS redirects", "fail", "No redirects configured");
                }
                
            } catch (error) {
                this.logTest("liara.json readable", "fail", error.message);
            }
        } else {
            this.logTest("liara.json exists", "fail", "Configuration file not found");
        }
    }

    async testFrontendSSL() {
        console.log("\n" + "-".repeat(40));
        console.log("Frontend SSL/HTTPS Test");
        console.log("-".repeat(40));

        try {
            // Test HTTPS access
            const response = await this.makeRequest(this.frontendUrl);
            
            if (response.statusCode === 200) {
                this.logTest("Frontend HTTPS access", "pass", `HTTP ${response.statusCode}`);
            } else {
                this.logTest("Frontend HTTPS access", "fail", `HTTP ${response.statusCode}`);
            }
            
            // Check security headers
            const requiredHeaders = {
                'strict-transport-security': 'HSTS',
                'x-content-type-options': 'Content Type Options',
                'x-frame-options': 'Frame Options',
                'referrer-policy': 'Referrer Policy',
                'cross-origin-opener-policy': 'Cross-Origin Opener Policy'
            };
            
            for (const [headerName, displayName] of Object.entries(requiredHeaders)) {
                if (response.headers[headerName]) {
                    this.logTest(`${displayName} header`, "pass", response.headers[headerName]);
                } else {
                    this.logTest(`${displayName} header`, "fail", "Header not present");
                }
            }
            
        } catch (error) {
            this.logTest("Frontend HTTPS access", "fail", error.message);
        }
    }

    async testHTTPSRedirect() {
        console.log("\n" + "-".repeat(40));
        console.log("HTTPS Redirect Test");
        console.log("-".repeat(40));

        try {
            // Test HTTP to HTTPS redirect
            const httpUrl = this.frontendUrl.replace('https://', 'http://');
            const response = await this.makeRequest(httpUrl, { 
                method: 'GET',
                followRedirect: false 
            });
            
            if ([301, 302, 307, 308].includes(response.statusCode)) {
                const location = response.headers.location;
                if (location && location.startsWith('https://')) {
                    this.logTest("HTTP→HTTPS redirect", "pass", `${response.statusCode} → ${location}`);
                } else {
                    this.logTest("HTTP→HTTPS redirect", "fail", `Redirects to: ${location}`);
                }
            } else {
                this.logTest("HTTP→HTTPS redirect", "fail", `No redirect, HTTP ${response.statusCode}`);
            }
            
        } catch (error) {
            this.logTest("HTTP→HTTPS redirect", "fail", error.message);
        }
    }

    async testMixedContent() {
        console.log("\n" + "-".repeat(40));
        console.log("Mixed Content Test");
        console.log("-".repeat(40));

        try {
            const response = await this.makeRequest(this.frontendUrl);
            const content = response.data;
            
            // Check for mixed content issues
            const mixedContentPatterns = [
                /src="http:\/\//g,
                /href="http:\/\//g,
                /url\(http:\/\//g,
                /@import.*http:\/\//g
            ];
            
            let mixedContentFound = false;
            const issues = [];
            
            for (const pattern of mixedContentPatterns) {
                const matches = content.match(pattern);
                if (matches) {
                    mixedContentFound = true;
                    issues.push(`${matches.length} ${pattern.source} references`);
                }
            }
            
            if (mixedContentFound) {
                this.logTest("Mixed content check", "fail", `Issues found: ${issues.join(', ')}`);
            } else {
                this.logTest("Mixed content check", "pass", "No mixed content detected");
            }
            
        } catch (error) {
            this.logTest("Mixed content check", "fail", error.message);
        }
    }

    async testBackendSSL() {
        console.log("\n" + "-".repeat(40));
        console.log("Backend SSL/HTTPS Test");
        console.log("-".repeat(40));

        try {
            // Test backend HTTPS access
            const response = await this.makeRequest(`${this.backendUrl}/health/`);
            
            if (response.statusCode === 200) {
                this.logTest("Backend HTTPS access", "pass", `HTTP ${response.statusCode}`);
            } else {
                this.logTest("Backend HTTPS access", "fail", `HTTP ${response.statusCode}`);
            }
            
            // Check backend security headers
            const requiredHeaders = {
                'strict-transport-security': 'HSTS',
                'x-content-type-options': 'Content Type Options',
                'x-frame-options': 'Frame Options',
                'referrer-policy': 'Referrer Policy'
            };
            
            for (const [headerName, displayName] of Object.entries(requiredHeaders)) {
                if (response.headers[headerName]) {
                    this.logTest(`Backend ${displayName}`, "pass", response.headers[headerName]);
                } else {
                    this.logTest(`Backend ${displayName}`, "fail", "Header not present");
                }
            }
            
        } catch (error) {
            this.logTest("Backend HTTPS access", "fail", error.message);
        }
    }

    async testCORSWithHTTPS() {
        console.log("\n" + "-".repeat(40));
        console.log("CORS with HTTPS Test");
        console.log("-".repeat(40));

        try {
            // Test CORS preflight with HTTPS origin
            const response = await this.makeRequest(`${this.backendUrl}/api/v1/auth/login/`, {
                method: 'OPTIONS',
                headers: {
                    'Origin': this.frontendUrl,
                    'Access-Control-Request-Method': 'POST',
                    'Access-Control-Request-Headers': 'Content-Type,Authorization'
                }
            });
            
            if (response.statusCode === 200) {
                const allowOrigin = response.headers['access-control-allow-origin'];
                if (allowOrigin === this.frontendUrl) {
                    this.logTest("CORS HTTPS origin", "pass", `Origin allowed: ${allowOrigin}`);
                } else {
                    this.logTest("CORS HTTPS origin", "fail", `Origin mismatch: ${allowOrigin}`);
                }
            } else {
                this.logTest("CORS HTTPS origin", "fail", `HTTP ${response.statusCode}`);
            }
            
        } catch (error) {
            this.logTest("CORS HTTPS origin", "fail", error.message);
        }
    }

    generateSecurityRecommendations() {
        console.log("\n" + "-".repeat(40));
        console.log("Security Recommendations");
        console.log("-".repeat(40));

        const recommendations = [];
        
        // Check test results for issues
        const failedTests = this.testResults.filter(r => r.status === 'fail');
        const warningTests = this.testResults.filter(r => r.status === 'warning');
        
        if (failedTests.some(t => t.test.includes('HSTS'))) {
            recommendations.push("Configure HSTS header with max-age=31536000; includeSubDomains; preload");
        }
        
        if (failedTests.some(t => t.test.includes('Content Security Policy'))) {
            recommendations.push("Implement Content Security Policy to prevent XSS attacks");
        }
        
        if (failedTests.some(t => t.test.includes('Mixed content'))) {
            recommendations.push("Fix mixed content issues by using HTTPS for all resources");
        }
        
        if (failedTests.some(t => t.test.includes('redirect'))) {
            recommendations.push("Configure HTTP to HTTPS redirects in Liara configuration");
        }
        
        if (recommendations.length > 0) {
            console.log("⚠️  Security Recommendations:");
            recommendations.forEach((rec, index) => {
                console.log(`  ${index + 1}. ${rec}`);
            });
        } else {
            console.log("✅ No security recommendations - configuration looks good!");
        }
    }

    async runAllTests() {
        console.log("TikTrue Frontend SSL/HTTPS Configuration Test Suite");
        console.log("Started at:", new Date().toISOString());
        console.log("=".repeat(60));

        await this.testLiaraConfiguration();
        await this.testFrontendSSL();
        await this.testHTTPSRedirect();
        await this.testMixedContent();
        await this.testBackendSSL();
        await this.testCORSWithHTTPS();
        
        this.generateSecurityRecommendations();
        this.printSummary();
    }

    printSummary() {
        console.log("\n" + "=".repeat(60));
        console.log("SSL/HTTPS CONFIGURATION TEST SUMMARY");
        console.log("=".repeat(60));

        const passed = this.testResults.filter(r => r.status === 'pass').length;
        const failed = this.testResults.filter(r => r.status === 'fail').length;
        const warnings = this.testResults.filter(r => r.status === 'warning').length;
        const total = this.testResults.length;

        console.log(`Total Tests: ${total}`);
        console.log(`Passed: ${passed}`);
        console.log(`Failed: ${failed}`);
        console.log(`Warnings: ${warnings}`);

        if (failed > 0) {
            console.log(`\n❌ ${failed} tests failed - SSL/HTTPS configuration has issues`);
            console.log("\nFailed Tests:");
            for (const result of this.testResults) {
                if (result.status === 'fail') {
                    console.log(`  - ${result.test}: ${result.details || 'No details'}`);
                }
            }
        } else if (warnings > 0) {
            console.log(`\n⚠️  ${warnings} tests have warnings - Configuration mostly secure`);
        } else {
            console.log(`\n✅ All tests passed - SSL/HTTPS configuration is secure`);
        }

        // Save results to file
        fs.writeFileSync('ssl_configuration_test_results.json', JSON.stringify(this.testResults, null, 2));
        console.log(`\nDetailed results saved to: ssl_configuration_test_results.json`);
    }
}

// Run tests
const tester = new SSLConfigurationTester();
tester.runAllTests().catch(console.error);