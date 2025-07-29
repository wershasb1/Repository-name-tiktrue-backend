#!/usr/bin/env node
/**
 * Comprehensive Frontend Integration Test Suite
 * 
 * Tests frontend-backend connectivity, API endpoints, and core functionality
 */

const axios = require('axios');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

class FrontendTester {
    constructor() {
        this.backendUrl = process.env.REACT_APP_BACKEND_URL || 'https://api.tiktrue.com';
        this.apiBaseUrl = process.env.REACT_APP_API_BASE_URL || 'https://api.tiktrue.com/api/v1';
        this.frontendUrl = process.env.REACT_APP_FRONTEND_URL || 'https://tiktrue.com';
        
        this.testResults = [];
        this.authToken = null;
        
        // Configure axios
        this.apiClient = axios.create({
            baseURL: this.apiBaseUrl,
            timeout: 10000,
            withCredentials: true
        });
    }

    log(message, type = 'info') {
        const timestamp = new Date().toISOString();
        const prefix = {
            info: '✅',
            warning: '⚠️ ',
            error: '❌',
            success: '🎉'
        }[type] || 'ℹ️ ';
        
        console.log(`${prefix} ${message}`);
    }

    logTest(testName, status, details = null, responseTime = null) {
        const result = {
            test: testName,
            status: status,
            timestamp: new Date().toISOString(),
            details: details,
            responseTime: responseTime
        };
        
        this.testResults.push(result);
        
        const statusIcon = status === 'pass' ? '✅' : status === 'fail' ? '❌' : '⚠️ ';
        console.log(`${statusIcon} ${testName}: ${status.toUpperCase()}`);
        
        if (details) {
            console.log(`  ${details}`);
        }
        if (responseTime) {
            console.log(`  Response time: ${responseTime.toFixed(2)}ms`);
        }
    }

    async testBackendConnectivity() {
        this.log('Testing backend connectivity...');
        
        // Test health endpoint
        try {
            const startTime = Date.now();
            const response = await axios.get(`${this.backendUrl}/health/`);
            const responseTime = Date.now() - startTime;
            
            if (response.status === 200) {
                const data = response.data;
                this.logTest('Backend Health Check', 'pass', 
                    `Status: ${data.status}`, responseTime);
            } else {
                this.logTest('Backend Health Check', 'fail', 
                    `HTTP ${response.status}`, responseTime);
            }
        } catch (error) {
            this.logTest('Backend Health Check', 'fail', error.message);
        }

        // Test admin panel
        try {
            const startTime = Date.now();
            const response = await axios.get(`${this.backendUrl}/admin/`);
            const responseTime = Date.now() - startTime;
            
            if (response.status === 200 || response.status === 302) {
                this.logTest('Admin Panel Access', 'pass', 
                    `HTTP ${response.status}`, responseTime);
            } else {
                this.logTest('Admin Panel Access', 'fail', 
                    `HTTP ${response.status}`, responseTime);
            }
        } catch (error) {
            this.logTest('Admin Panel Access', 'fail', error.message);
        }
    }

    async testCORSConfiguration() {
        this.log('Testing CORS configuration...');
        
        try {
            const startTime = Date.now();
            const response = await axios.options(`${this.apiBaseUrl}/auth/login/`, {
                headers: {
                    'Origin': this.frontendUrl,
                    'Access-Control-Request-Method': 'POST',
                    'Access-Control-Request-Headers': 'Content-Type,Authorization'
                }
            });
            const responseTime = Date.now() - startTime;
            
            const corsHeaders = {
                'Access-Control-Allow-Origin': response.headers['access-control-allow-origin'],
                'Access-Control-Allow-Methods': response.headers['access-control-allow-methods'],
                'Access-Control-Allow-Headers': response.headers['access-control-allow-headers'],
                'Access-Control-Allow-Credentials': response.headers['access-control-allow-credentials']
            };
            
            if (response.status === 200 && corsHeaders['Access-Control-Allow-Origin']) {
                this.logTest('CORS Preflight', 'pass', 
                    `Origin: ${corsHeaders['Access-Control-Allow-Origin']}`, responseTime);
            } else {
                this.logTest('CORS Preflight', 'fail', 
                    `HTTP ${response.status}`, responseTime);
            }
            
        } catch (error) {
            this.logTest('CORS Preflight', 'fail', error.message);
        }
    }

    async testAPIEndpoints() {
        this.log('Testing API endpoints...');
        
        // Test authentication endpoints
        const endpoints = [
            { path: '/auth/register/', method: 'POST', expectedStatus: 400 },
            { path: '/auth/login/', method: 'POST', expectedStatus: 400 },
        ];

        for (const endpoint of endpoints) {
            try {
                const startTime = Date.now();
                const response = await this.apiClient.request({
                    method: endpoint.method,
                    url: endpoint.path,
                    data: {}
                });
                const responseTime = Date.now() - startTime;
                
                this.logTest(`${endpoint.method} ${endpoint.path}`, 'pass', 
                    `HTTP ${response.status}`, responseTime);
                    
            } catch (error) {
                const responseTime = Date.now() - startTime;
                const status = error.response?.status;
                
                if (status === endpoint.expectedStatus) {
                    this.logTest(`${endpoint.method} ${endpoint.path}`, 'pass', 
                        `HTTP ${status} (expected)`, responseTime);
                } else {
                    this.logTest(`${endpoint.method} ${endpoint.path}`, 'fail', 
                        `HTTP ${status || 'No response'}`, responseTime);
                }
            }
        }
    }

    async testUserRegistrationFlow() {
        this.log('Testing user registration flow...');
        
        const testUser = {
            username: `testuser_${Date.now()}`,
            email: `test_${Date.now()}@example.com`,
            password: 'testpassword123',
            password_confirm: 'testpassword123'
        };

        try {
            const startTime = Date.now();
            const response = await this.apiClient.post('/auth/register/', testUser);
            const responseTime = Date.now() - startTime;
            
            if (response.status === 201) {
                const data = response.data;
                if (data.tokens && data.tokens.access) {
                    this.authToken = data.tokens.access;
                    this.logTest('User Registration', 'pass', 
                        'User created with tokens', responseTime);
                } else {
                    this.logTest('User Registration', 'warning', 
                        'User created but no tokens', responseTime);
                }
            } else {
                this.logTest('User Registration', 'fail', 
                    `HTTP ${response.status}`, responseTime);
            }
        } catch (error) {
            const responseTime = Date.now() - startTime;
            this.logTest('User Registration', 'fail', 
                error.response?.data?.message || error.message, responseTime);
        }
    }

    async testAuthenticatedEndpoints() {
        if (!this.authToken) {
            this.logTest('Authenticated Endpoints', 'skip', 'No auth token available');
            return;
        }

        this.log('Testing authenticated endpoints...');
        
        const authenticatedEndpoints = [
            '/auth/profile/',
            '/models/available/',
            '/license/info/'
        ];

        for (const endpoint of authenticatedEndpoints) {
            try {
                const startTime = Date.now();
                const response = await this.apiClient.get(endpoint, {
                    headers: {
                        'Authorization': `Bearer ${this.authToken}`
                    }
                });
                const responseTime = Date.now() - startTime;
                
                if (response.status === 200) {
                    this.logTest(`GET ${endpoint}`, 'pass', 
                        'Data retrieved successfully', responseTime);
                } else {
                    this.logTest(`GET ${endpoint}`, 'fail', 
                        `HTTP ${response.status}`, responseTime);
                }
            } catch (error) {
                const responseTime = Date.now() - startTime;
                const status = error.response?.status;
                
                if (status === 404) {
                    this.logTest(`GET ${endpoint}`, 'warning', 
                        'Endpoint not implemented', responseTime);
                } else {
                    this.logTest(`GET ${endpoint}`, 'fail', 
                        `HTTP ${status || 'No response'}`, responseTime);
                }
            }
        }
    }

    async testFrontendBuild() {
        this.log('Testing frontend build...');
        
        const buildDir = path.join(__dirname, 'build');
        
        // Check if build directory exists
        if (!fs.existsSync(buildDir)) {
            this.logTest('Build Directory', 'fail', 'Build directory not found');
            return;
        }

        // Check for required files
        const requiredFiles = [
            'index.html',
            'static/css',
            'static/js'
        ];

        let allFilesExist = true;
        for (const file of requiredFiles) {
            const filePath = path.join(buildDir, file);
            if (fs.existsSync(filePath)) {
                this.logTest(`Build File: ${file}`, 'pass', 'File exists');
            } else {
                this.logTest(`Build File: ${file}`, 'fail', 'File missing');
                allFilesExist = false;
            }
        }

        if (allFilesExist) {
            this.logTest('Frontend Build', 'pass', 'All required files present');
        }
    }

    async testEnvironmentConfiguration() {
        this.log('Testing environment configuration...');
        
        const requiredEnvVars = [
            'REACT_APP_API_BASE_URL',
            'REACT_APP_BACKEND_URL',
            'REACT_APP_FRONTEND_URL'
        ];

        let allVarsSet = true;
        for (const varName of requiredEnvVars) {
            const value = process.env[varName];
            if (value) {
                this.logTest(`Environment: ${varName}`, 'pass', `Set to: ${value}`);
            } else {
                this.logTest(`Environment: ${varName}`, 'fail', 'Not set');
                allVarsSet = false;
            }
        }

        if (allVarsSet) {
            this.logTest('Environment Configuration', 'pass', 'All required variables set');
        }
    }

    generateReport() {
        console.log('\n' + '='.repeat(60));
        console.log('FRONTEND INTEGRATION TEST REPORT');
        console.log('='.repeat(60));

        const passed = this.testResults.filter(r => r.status === 'pass').length;
        const failed = this.testResults.filter(r => r.status === 'fail').length;
        const warnings = this.testResults.filter(r => r.status === 'warning').length;
        const skipped = this.testResults.filter(r => r.status === 'skip').length;
        const total = this.testResults.length;

        console.log(`\nTest Summary:`);
        console.log(`Total Tests: ${total}`);
        console.log(`Passed: ${passed}`);
        console.log(`Failed: ${failed}`);
        console.log(`Warnings: ${warnings}`);
        console.log(`Skipped: ${skipped}`);

        if (failed > 0) {
            console.log(`\n❌ ${failed} tests failed:`);
            this.testResults
                .filter(r => r.status === 'fail')
                .forEach(result => {
                    console.log(`  - ${result.test}: ${result.details}`);
                });
        }

        if (warnings > 0) {
            console.log(`\n⚠️  ${warnings} warnings:`);
            this.testResults
                .filter(r => r.status === 'warning')
                .forEach(result => {
                    console.log(`  - ${result.test}: ${result.details}`);
                });
        }

        if (failed === 0) {
            if (warnings > 0) {
                console.log(`\n⚠️  Tests completed with warnings - review recommended`);
            } else {
                console.log(`\n✅ All tests passed - frontend is ready!`);
            }
        } else {
            console.log(`\n❌ Tests failed - issues need to be resolved`);
        }

        // Save detailed results
        const reportPath = path.join(__dirname, 'integration-test-results.json');
        fs.writeFileSync(reportPath, JSON.stringify(this.testResults, null, 2));
        console.log(`\nDetailed results saved to: ${reportPath}`);

        console.log('\n' + '='.repeat(60));
        
        return failed === 0;
    }

    async runAllTests() {
        console.log('TikTrue Frontend Integration Test Suite');
        console.log('='.repeat(50));
        console.log(`Backend URL: ${this.backendUrl}`);
        console.log(`API Base URL: ${this.apiBaseUrl}`);
        console.log(`Frontend URL: ${this.frontendUrl}`);
        console.log('='.repeat(50));

        // Run all test categories
        await this.testEnvironmentConfiguration();
        await this.testFrontendBuild();
        await this.testBackendConnectivity();
        await this.testCORSConfiguration();
        await this.testAPIEndpoints();
        await this.testUserRegistrationFlow();
        await this.testAuthenticatedEndpoints();

        // Generate final report
        const success = this.generateReport();
        
        if (!success) {
            process.exit(1);
        }
    }
}

// Allow URL override from command line
const backendUrl = process.argv[2];
const apiBaseUrl = process.argv[3];
const frontendUrl = process.argv[4];

if (backendUrl) process.env.REACT_APP_BACKEND_URL = backendUrl;
if (apiBaseUrl) process.env.REACT_APP_API_BASE_URL = apiBaseUrl;
if (frontendUrl) process.env.REACT_APP_FRONTEND_URL = frontendUrl;

// Run the test suite
const tester = new FrontendTester();
tester.runAllTests().catch(error => {
    console.error('Test suite failed:', error);
    process.exit(1);
});