#!/usr/bin/env node
/**
 * Simple integration test for frontend-backend connection
 */

const axios = require('axios');

// Configure axios to use the same base URL as frontend
axios.defaults.baseURL = 'https://tiktrue-backend.liara.run/api/v1';

async function testIntegration() {
    console.log('Testing Frontend-Backend Integration...');
    console.log('Backend URL:', axios.defaults.baseURL);
    console.log('-'.repeat(50));

    // Test 1: Health check
    try {
        const response = await axios.get('/../../health/');
        console.log('✓ Health check:', response.status);
    } catch (error) {
        console.log('✗ Health check failed:', error.message);
    }

    // Test 2: Auth endpoints (should return 400 for empty data, which means they work)
    try {
        const response = await axios.post('/auth/register/', {});
        console.log('✓ Register endpoint:', response.status);
    } catch (error) {
        if (error.response && error.response.status === 400) {
            console.log('✓ Register endpoint: 400 (working, needs data)');
        } else {
            console.log('✗ Register endpoint failed:', error.message);
        }
    }

    try {
        const response = await axios.post('/auth/login/', {});
        console.log('✓ Login endpoint:', response.status);
    } catch (error) {
        if (error.response && error.response.status === 400) {
            console.log('✓ Login endpoint: 400 (working, needs data)');
        } else {
            console.log('✗ Login endpoint failed:', error.message);
        }
    }

    // Test 3: CORS check
    try {
        const response = await axios.options('/auth/login/', {
            headers: {
                'Origin': 'https://tiktrue-frontend.liara.run',
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'Content-Type'
            }
        });
        
        console.log('✓ CORS check:', response.status);
        console.log('  Access-Control-Allow-Origin:', response.headers['access-control-allow-origin']);
        console.log('  Access-Control-Allow-Methods:', response.headers['access-control-allow-methods']);
        
    } catch (error) {
        console.log('✗ CORS check failed:', error.message);
    }

    console.log('-'.repeat(50));
    console.log('Integration test completed!');
}

// Run the test
testIntegration().catch(console.error);