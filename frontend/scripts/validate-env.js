#!/usr/bin/env node
/**
 * Environment Variables Validation Script for TikTrue Frontend
 * 
 * This script validates that all required environment variables are set
 * before building the application.
 */

const requiredVars = [
  'REACT_APP_API_BASE_URL',
  'REACT_APP_BACKEND_URL',
  'REACT_APP_FRONTEND_URL'
];

const optionalVars = [
  'REACT_APP_ENVIRONMENT',
  'REACT_APP_DEBUG',
  'REACT_APP_ENABLE_ANALYTICS',
  'GENERATE_SOURCEMAP'
];

function validateEnvironmentVariables() {
  console.log('🔍 Validating environment variables...');
  console.log('='.repeat(40));

  let hasErrors = false;
  const warnings = [];

  // Check required variables
  console.log('\n📋 Required Variables:');
  requiredVars.forEach(varName => {
    const value = process.env[varName];
    if (!value) {
      console.log(`❌ ${varName}: Missing (REQUIRED)`);
      hasErrors = true;
    } else {
      console.log(`✅ ${varName}: ${value}`);
      
      // Validate URL format for URL variables
      if (varName.includes('URL')) {
        try {
          new URL(value);
        } catch (error) {
          console.log(`❌ ${varName}: Invalid URL format`);
          hasErrors = true;
        }
      }
    }
  });

  // Check optional variables
  console.log('\n📋 Optional Variables:');
  optionalVars.forEach(varName => {
    const value = process.env[varName];
    if (value) {
      console.log(`✅ ${varName}: ${value}`);
    } else {
      console.log(`⚪ ${varName}: Not set (using default)`);
    }
  });

  // Environment-specific validations
  const nodeEnv = process.env.NODE_ENV;
  console.log(`\n🌍 Environment: ${nodeEnv || 'development'}`);

  // Production-specific checks
  if (nodeEnv === 'production') {
    if (process.env.GENERATE_SOURCEMAP !== 'false') {
      warnings.push('GENERATE_SOURCEMAP should be false in production for security');
    }
    
    if (process.env.REACT_APP_DEBUG === 'true') {
      warnings.push('REACT_APP_DEBUG should be false in production');
    }

    const apiUrl = process.env.REACT_APP_API_BASE_URL;
    if (apiUrl && !apiUrl.startsWith('https://')) {
      warnings.push('REACT_APP_API_BASE_URL should use HTTPS in production');
    }
  }

  // Development-specific checks
  if (nodeEnv === 'development') {
    const apiUrl = process.env.REACT_APP_API_BASE_URL;
    if (apiUrl && apiUrl.startsWith('https://') && !apiUrl.includes('localhost')) {
      warnings.push('Consider using local backend URL for development');
    }
  }

  // Display warnings
  if (warnings.length > 0) {
    console.log('\n⚠️  Warnings:');
    warnings.forEach(warning => {
      console.log(`  - ${warning}`);
    });
  }

  // Final result
  console.log('\n' + '='.repeat(40));
  if (hasErrors) {
    console.log('❌ Environment validation failed!');
    console.log('\nTo fix:');
    console.log('1. Copy .env.example to .env.local');
    console.log('2. Set all required environment variables');
    console.log('3. Ensure URLs are valid and use appropriate protocols');
    process.exit(1);
  } else {
    console.log('✅ Environment validation passed!');
    if (warnings.length > 0) {
      console.log(`⚠️  ${warnings.length} warning(s) - review recommended`);
    }
  }
}

// Additional validation functions
function validateApiConnectivity() {
  const apiUrl = process.env.REACT_APP_API_BASE_URL;
  if (!apiUrl) return;

  console.log('\n🌐 API Connectivity Check:');
  console.log(`Target API: ${apiUrl}`);
  
  // Note: We can't actually test connectivity in a build script
  // This would need to be done in a separate test
  console.log('ℹ️  Use "npm run test:api" to test API connectivity');
}

function showEnvironmentSummary() {
  console.log('\n📊 Environment Summary:');
  console.log(`Node Environment: ${process.env.NODE_ENV || 'development'}`);
  console.log(`React App Environment: ${process.env.REACT_APP_ENVIRONMENT || 'not set'}`);
  console.log(`Debug Mode: ${process.env.REACT_APP_DEBUG || 'not set'}`);
  console.log(`Source Maps: ${process.env.GENERATE_SOURCEMAP || 'default'}`);
  console.log(`Analytics: ${process.env.REACT_APP_ENABLE_ANALYTICS || 'not set'}`);
}

// Main execution
if (require.main === module) {
  try {
    validateEnvironmentVariables();
    validateApiConnectivity();
    showEnvironmentSummary();
  } catch (error) {
    console.error('❌ Validation script error:', error.message);
    process.exit(1);
  }
}