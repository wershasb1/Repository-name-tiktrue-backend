#!/usr/bin/env node
/**
 * Build Validation Script for TikTrue Frontend
 * 
 * This script validates the build process and ensures all requirements are met
 * for successful deployment on Liara platform.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class BuildValidator {
  constructor() {
    this.errors = [];
    this.warnings = [];
    this.buildDir = path.join(__dirname, '..', 'build');
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

  validateEnvironmentVariables() {
    this.log('Validating environment variables...');
    
    const requiredVars = [
      'REACT_APP_API_BASE_URL',
      'REACT_APP_BACKEND_URL',
      'REACT_APP_FRONTEND_URL'
    ];

    const missing = requiredVars.filter(varName => !process.env[varName]);

    if (missing.length > 0) {
      this.errors.push(`Missing required environment variables: ${missing.join(', ')}`);
      return false;
    }

    // Validate URL formats
    try {
      new URL(process.env.REACT_APP_API_BASE_URL);
      new URL(process.env.REACT_APP_BACKEND_URL);
      new URL(process.env.REACT_APP_FRONTEND_URL);
    } catch (error) {
      this.errors.push('Invalid URL format in environment variables');
      return false;
    }

    this.log('Environment variables validated successfully');
    return true;
  }

  validatePackageJson() {
    this.log('Validating package.json...');
    
    const packageJsonPath = path.join(__dirname, '..', 'package.json');
    
    if (!fs.existsSync(packageJsonPath)) {
      this.errors.push('package.json not found');
      return false;
    }

    const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));

    // Check required scripts
    const requiredScripts = ['start', 'build', 'test'];
    const missingScripts = requiredScripts.filter(script => !packageJson.scripts[script]);
    
    if (missingScripts.length > 0) {
      this.errors.push(`Missing required scripts: ${missingScripts.join(', ')}`);
      return false;
    }

    // Check required dependencies
    const requiredDeps = ['react', 'react-dom', 'react-scripts'];
    const missingDeps = requiredDeps.filter(dep => !packageJson.dependencies[dep]);
    
    if (missingDeps.length > 0) {
      this.errors.push(`Missing required dependencies: ${missingDeps.join(', ')}`);
      return false;
    }

    this.log('package.json validated successfully');
    return true;
  }

  validateLiaraConfig() {
    this.log('Validating liara.json...');
    
    const liaraConfigPath = path.join(__dirname, '..', 'liara.json');
    
    if (!fs.existsSync(liaraConfigPath)) {
      this.errors.push('liara.json not found');
      return false;
    }

    const liaraConfig = JSON.parse(fs.readFileSync(liaraConfigPath, 'utf8'));

    // Check required configuration
    if (liaraConfig.platform !== 'static') {
      this.errors.push('liara.json platform must be "static"');
      return false;
    }

    if (!liaraConfig.build || !liaraConfig.build.command) {
      this.errors.push('liara.json must have build.command');
      return false;
    }

    if (!liaraConfig.build.output) {
      this.errors.push('liara.json must have build.output');
      return false;
    }

    if (!liaraConfig.static || !liaraConfig.static.spa) {
      this.warnings.push('SPA routing not enabled in liara.json');
    }

    this.log('liara.json validated successfully');
    return true;
  }

  runBuild() {
    this.log('Running build process...');
    
    try {
      // Clean previous build
      if (fs.existsSync(this.buildDir)) {
        fs.rmSync(this.buildDir, { recursive: true, force: true });
        this.log('Cleaned previous build directory');
      }

      // Run build
      const buildCommand = 'npm run build';
      this.log(`Executing: ${buildCommand}`);
      
      const output = execSync(buildCommand, { 
        cwd: path.join(__dirname, '..'),
        encoding: 'utf8',
        stdio: 'pipe'
      });

      this.log('Build completed successfully');
      return true;
    } catch (error) {
      this.errors.push(`Build failed: ${error.message}`);
      return false;
    }
  }

  validateBuildOutput() {
    this.log('Validating build output...');
    
    if (!fs.existsSync(this.buildDir)) {
      this.errors.push('Build directory not found');
      return false;
    }

    // Check for required files
    const requiredFiles = [
      'index.html',
      'static/css',
      'static/js'
    ];

    const missingFiles = requiredFiles.filter(file => 
      !fs.existsSync(path.join(this.buildDir, file))
    );

    if (missingFiles.length > 0) {
      this.errors.push(`Missing build files: ${missingFiles.join(', ')}`);
      return false;
    }

    // Check index.html content
    const indexHtml = fs.readFileSync(path.join(this.buildDir, 'index.html'), 'utf8');
    
    if (!indexHtml.includes('<div id="root">')) {
      this.errors.push('index.html missing root div');
      return false;
    }

    // Check for CSS and JS files
    const staticDir = path.join(this.buildDir, 'static');
    const cssFiles = fs.readdirSync(path.join(staticDir, 'css')).filter(f => f.endsWith('.css'));
    const jsFiles = fs.readdirSync(path.join(staticDir, 'js')).filter(f => f.endsWith('.js'));

    if (cssFiles.length === 0) {
      this.warnings.push('No CSS files found in build output');
    }

    if (jsFiles.length === 0) {
      this.errors.push('No JavaScript files found in build output');
      return false;
    }

    this.log(`Build output validated: ${cssFiles.length} CSS files, ${jsFiles.length} JS files`);
    return true;
  }

  analyzeBundleSize() {
    this.log('Analyzing bundle size...');
    
    const staticDir = path.join(this.buildDir, 'static');
    
    if (!fs.existsSync(staticDir)) {
      this.warnings.push('Static directory not found for bundle analysis');
      return;
    }

    let totalSize = 0;
    const fileSizes = {};

    const analyzeDirectory = (dir, prefix = '') => {
      const files = fs.readdirSync(dir);
      
      files.forEach(file => {
        const filePath = path.join(dir, file);
        const stat = fs.statSync(filePath);
        
        if (stat.isDirectory()) {
          analyzeDirectory(filePath, `${prefix}${file}/`);
        } else {
          const size = stat.size;
          totalSize += size;
          fileSizes[`${prefix}${file}`] = size;
        }
      });
    };

    analyzeDirectory(staticDir);

    // Convert to MB
    const totalSizeMB = (totalSize / 1024 / 1024).toFixed(2);
    
    this.log(`Total bundle size: ${totalSizeMB} MB`);

    // Warn if bundle is too large
    if (totalSize > 5 * 1024 * 1024) { // 5MB
      this.warnings.push(`Bundle size is large (${totalSizeMB} MB). Consider code splitting.`);
    }

    // Show largest files
    const sortedFiles = Object.entries(fileSizes)
      .sort(([,a], [,b]) => b - a)
      .slice(0, 5);

    this.log('Largest files:');
    sortedFiles.forEach(([file, size]) => {
      const sizeMB = (size / 1024 / 1024).toFixed(2);
      console.log(`  ${file}: ${sizeMB} MB`);
    });
  }

  testSPARouting() {
    this.log('Testing SPA routing configuration...');
    
    const indexHtml = path.join(this.buildDir, 'index.html');
    
    if (!fs.existsSync(indexHtml)) {
      this.errors.push('index.html not found for SPA routing test');
      return false;
    }

    // In a real SPA setup, all routes should serve index.html
    // This is handled by the server configuration, not the build
    this.log('SPA routing will be handled by Liara static hosting');
    return true;
  }

  validateSecurityHeaders() {
    this.log('Validating security configuration...');
    
    const liaraConfigPath = path.join(__dirname, '..', 'liara.json');
    const liaraConfig = JSON.parse(fs.readFileSync(liaraConfigPath, 'utf8'));

    if (!liaraConfig.static || !liaraConfig.static.headers) {
      this.warnings.push('No security headers configured in liara.json');
      return false;
    }

    const headers = liaraConfig.static.headers;
    const recommendedHeaders = [
      'X-Frame-Options',
      'X-Content-Type-Options',
      'Referrer-Policy'
    ];

    const missingHeaders = recommendedHeaders.filter(header => !headers[header]);
    
    if (missingHeaders.length > 0) {
      this.warnings.push(`Missing recommended security headers: ${missingHeaders.join(', ')}`);
    } else {
      this.log('Security headers configured properly');
    }

    return true;
  }

  generateReport() {
    console.log('\n' + '='.repeat(60));
    console.log('BUILD VALIDATION REPORT');
    console.log('='.repeat(60));

    if (this.errors.length === 0 && this.warnings.length === 0) {
      this.log('All validations passed! Build is ready for deployment.', 'success');
    } else {
      if (this.errors.length > 0) {
        console.log('\n❌ ERRORS:');
        this.errors.forEach(error => console.log(`  - ${error}`));
      }

      if (this.warnings.length > 0) {
        console.log('\n⚠️  WARNINGS:');
        this.warnings.forEach(warning => console.log(`  - ${warning}`));
      }
    }

    console.log('\n' + '='.repeat(60));
    
    return this.errors.length === 0;
  }

  async run() {
    console.log('TikTrue Frontend Build Validation');
    console.log('='.repeat(40));

    // Run all validations
    const validations = [
      () => this.validateEnvironmentVariables(),
      () => this.validatePackageJson(),
      () => this.validateLiaraConfig(),
      () => this.runBuild(),
      () => this.validateBuildOutput(),
      () => this.analyzeBundleSize(),
      () => this.testSPARouting(),
      () => this.validateSecurityHeaders()
    ];

    for (const validation of validations) {
      try {
        validation();
      } catch (error) {
        this.errors.push(`Validation error: ${error.message}`);
      }
    }

    // Generate final report
    const success = this.generateReport();
    
    if (!success) {
      process.exit(1);
    }
  }
}

// Run validation if called directly
if (require.main === module) {
  const validator = new BuildValidator();
  validator.run().catch(error => {
    console.error('Validation failed:', error);
    process.exit(1);
  });
}

module.exports = BuildValidator;