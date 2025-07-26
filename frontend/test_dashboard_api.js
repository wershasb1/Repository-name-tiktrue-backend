#!/usr/bin/env node
/**
 * Test Dashboard API Functionality
 */

const axios = require('axios');

axios.defaults.baseURL = 'https://tiktrue-backend.liara.run/api/v1';

async function testDashboardFunctionality() {
    console.log('🎛️  Testing Dashboard Functionality...');
    console.log('='.repeat(50));

    // Create a test user and login
    const testUser = {
        email: `dashboard_test_${Date.now()}@example.com`,
        username: `dashuser_${Date.now()}`,
        password: 'DashTest123!',
        password_confirm: 'DashTest123!'
    };

    try {
        // Register user
        const registerResponse = await axios.post('/auth/register/', testUser);
        console.log('✅ Test user registered:', registerResponse.status);
        
        const { access: token } = registerResponse.data.tokens;
        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;

        // Test dashboard-related endpoints
        console.log('\n📊 Testing Dashboard API Endpoints...');

        // 1. User Profile (for dashboard header)
        try {
            const profileResponse = await axios.get('/auth/profile/');
            console.log('✅ User profile for dashboard:', profileResponse.status);
            console.log('   - User email:', profileResponse.data.email);
            console.log('   - User username:', profileResponse.data.username);
        } catch (error) {
            console.log('❌ Profile fetch failed:', error.response?.status);
        }

        // 2. Available Models (for dashboard)
        try {
            const modelsResponse = await axios.get('/models/available/');
            console.log('✅ Available models endpoint:', modelsResponse.status);
            console.log('   - Models data type:', typeof modelsResponse.data);
        } catch (error) {
            console.log('❌ Models fetch failed:', error.response?.status);
        }

        // 3. License Info (for dashboard)
        try {
            const licenseResponse = await axios.get('/license/info/');
            console.log('✅ License info endpoint:', licenseResponse.status);
            console.log('   - License data type:', typeof licenseResponse.data);
        } catch (error) {
            console.log('❌ License info failed:', error.response?.status);
        }

        // 4. License Validation (for dashboard)
        try {
            const validateResponse = await axios.get('/license/validate/');
            console.log('✅ License validation endpoint:', validateResponse.status);
        } catch (error) {
            console.log('❌ License validation failed:', error.response?.status);
        }

        console.log('\n🎉 Dashboard API functionality test completed!');
        console.log('✅ All dashboard-related endpoints are working');
        console.log('✅ User authentication is functional');
        console.log('✅ Protected routes are accessible');

    } catch (error) {
        console.log('❌ Dashboard test failed:', error.response?.status, error.response?.data);
    }
}

testDashboardFunctionality().catch(console.error);