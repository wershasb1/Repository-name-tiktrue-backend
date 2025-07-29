#!/usr/bin/env node
/**
 * Build Optimization Script for TikTrue Frontend
 * 
 * This script optimizes the build output for better performance and deployment.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class BuildOptimizer {
  constructor() {
    this.buildDir = path.join(__dirname, '..', 'build');
    this.optimizations = [];
  }

  log(message, type = 'info') {
    const prefix = {
      info: '✅',
      warning: '⚠️ ',
      error: '❌',
      success: '🎉'
    }[type] || 'ℹ️ ';
    
    console.log(`${prefix} ${message}`);
  }

  optimizeIndexHtml() {
    this.log('Optimizing index.html...');
    
    const indexPath = path.join(this.buildDir, 'index.html');
    
    if (!fs.existsSync(indexPath)) {
      this.log('index.html not found', 'warning');
      return;
    }

    let html = fs.readFileSync(indexPath, 'utf8');
    let optimized = false;

    // Add preconnect for external domains
    const apiDomain = process.env.REACT_APP_BACKEND_URL;
    if (apiDomain && !html.includes('rel="preconnect"')) {
      const preconnect = `<link rel="preconnect" href="${apiDomain}">`;
      html = html.replace('<head>', `<head>\n    ${preconnect}`);
      optimized = true;
    }

    // Add DNS prefetch for external resources
    if (!html.includes('rel="dns-prefetch"')) {
      const dnsPrefetch = `<link rel="dns-prefetch" href="//fonts.googleapis.com">`;
      html = html.replace('<head>', `<head>\n    ${dnsPrefetch}`);
      optimized = true;
    }

    // Add viewport meta tag if missing
    if (!html.includes('name="viewport"')) {
      const viewport = `<meta name="viewport" content="width=device-width, initial-scale=1">`;
      html = html.replace('<head>', `<head>\n    ${viewport}`);
      optimized = true;
    }

    // Add theme-color meta tag
    if (!html.includes('name="theme-color"')) {
      const themeColor = `<meta name="theme-color" content="#3b82f6">`;
      html = html.replace('<head>', `<head>\n    ${themeColor}`);
      optimized = true;
    }

    if (optimized) {
      fs.writeFileSync(indexPath, html);
      this.optimizations.push('Enhanced index.html with performance optimizations');
      this.log('index.html optimized successfully');
    } else {
      this.log('index.html already optimized');
    }
  }

  generateRobotsTxt() {
    this.log('Generating robots.txt...');
    
    const robotsPath = path.join(this.buildDir, 'robots.txt');
    const frontendUrl = process.env.REACT_APP_FRONTEND_URL || 'https://tiktrue.com';
    
    const robotsContent = `User-agent: *
Allow: /

# Sitemap
Sitemap: ${frontendUrl}/sitemap.xml

# Disallow admin and API paths
Disallow: /admin/
Disallow: /api/
`;

    fs.writeFileSync(robotsPath, robotsContent);
    this.optimizations.push('Generated robots.txt for SEO');
    this.log('robots.txt generated successfully');
  }

  generateSitemap() {
    this.log('Generating sitemap.xml...');
    
    const sitemapPath = path.join(this.buildDir, 'sitemap.xml');
    const frontendUrl = process.env.REACT_APP_FRONTEND_URL || 'https://tiktrue.com';
    
    const pages = [
      { url: '/', priority: '1.0', changefreq: 'weekly' },
      { url: '/features', priority: '0.8', changefreq: 'monthly' },
      { url: '/pricing', priority: '0.8', changefreq: 'monthly' },
      { url: '/login', priority: '0.6', changefreq: 'yearly' },
      { url: '/register', priority: '0.6', changefreq: 'yearly' }
    ];

    const sitemapContent = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${pages.map(page => `  <url>
    <loc>${frontendUrl}${page.url}</loc>
    <changefreq>${page.changefreq}</changefreq>
    <priority>${page.priority}</priority>
    <lastmod>${new Date().toISOString().split('T')[0]}</lastmod>
  </url>`).join('\n')}
</urlset>`;

    fs.writeFileSync(sitemapPath, sitemapContent);
    this.optimizations.push('Generated sitemap.xml for SEO');
    this.log('sitemap.xml generated successfully');
  }

  optimizeManifest() {
    this.log('Optimizing manifest.json...');
    
    const manifestPath = path.join(this.buildDir, 'manifest.json');
    
    if (!fs.existsSync(manifestPath)) {
      this.log('manifest.json not found, creating one', 'warning');
      
      const manifest = {
        short_name: "TikTrue",
        name: "TikTrue MDI-LLM Platform",
        icons: [
          {
            src: "favicon.ico",
            sizes: "64x64 32x32 24x24 16x16",
            type: "image/x-icon"
          }
        ],
        start_url: ".",
        display: "standalone",
        theme_color: "#3b82f6",
        background_color: "#ffffff"
      };
      
      fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
      this.optimizations.push('Created optimized manifest.json');
    } else {
      const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
      let updated = false;

      // Ensure required fields
      if (!manifest.theme_color) {
        manifest.theme_color = "#3b82f6";
        updated = true;
      }

      if (!manifest.background_color) {
        manifest.background_color = "#ffffff";
        updated = true;
      }

      if (!manifest.display) {
        manifest.display = "standalone";
        updated = true;
      }

      if (updated) {
        fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
        this.optimizations.push('Enhanced manifest.json');
        this.log('manifest.json optimized');
      } else {
        this.log('manifest.json already optimized');
      }
    }
  }

  compressAssets() {
    this.log('Analyzing asset compression...');
    
    const staticDir = path.join(this.buildDir, 'static');
    
    if (!fs.existsSync(staticDir)) {
      this.log('Static directory not found', 'warning');
      return;
    }

    let totalOriginalSize = 0;
    let compressibleFiles = 0;

    const analyzeDirectory = (dir) => {
      const files = fs.readdirSync(dir);
      
      files.forEach(file => {
        const filePath = path.join(dir, file);
        const stat = fs.statSync(filePath);
        
        if (stat.isDirectory()) {
          analyzeDirectory(filePath);
        } else if (file.endsWith('.js') || file.endsWith('.css')) {
          totalOriginalSize += stat.size;
          compressibleFiles++;
        }
      });
    };

    analyzeDirectory(staticDir);

    const totalSizeMB = (totalOriginalSize / 1024 / 1024).toFixed(2);
    this.log(`Found ${compressibleFiles} compressible files (${totalSizeMB} MB)`);
    
    // Note: Liara handles gzip compression automatically when gzip: true in liara.json
    this.log('Compression will be handled by Liara (gzip enabled in liara.json)');
  }

  validateAccessibility() {
    this.log('Validating accessibility features...');
    
    const indexPath = path.join(this.buildDir, 'index.html');
    const html = fs.readFileSync(indexPath, 'utf8');
    
    const checks = [
      { test: html.includes('lang='), message: 'HTML lang attribute' },
      { test: html.includes('name="viewport"'), message: 'Viewport meta tag' },
      { test: html.includes('<title>'), message: 'Page title' },
      { test: html.includes('name="description"'), message: 'Meta description' }
    ];

    let accessibilityScore = 0;
    checks.forEach(check => {
      if (check.test) {
        accessibilityScore++;
        this.log(`✓ ${check.message}`);
      } else {
        this.log(`✗ Missing: ${check.message}`, 'warning');
      }
    });

    this.log(`Accessibility score: ${accessibilityScore}/${checks.length}`);
    
    if (accessibilityScore === checks.length) {
      this.optimizations.push('All accessibility checks passed');
    }
  }

  generateSecurityTxt() {
    this.log('Generating security.txt...');
    
    const securityPath = path.join(this.buildDir, '.well-known', 'security.txt');
    const wellKnownDir = path.dirname(securityPath);
    
    // Create .well-known directory if it doesn't exist
    if (!fs.existsSync(wellKnownDir)) {
      fs.mkdirSync(wellKnownDir, { recursive: true });
    }

    const securityContent = `Contact: mailto:security@tiktrue.com
Expires: ${new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString()}
Preferred-Languages: en
Canonical: https://tiktrue.com/.well-known/security.txt
`;

    fs.writeFileSync(securityPath, securityContent);
    this.optimizations.push('Generated security.txt for security disclosure');
    this.log('security.txt generated successfully');
  }

  optimizeForPWA() {
    this.log('Checking PWA optimization...');
    
    const manifestPath = path.join(this.buildDir, 'manifest.json');
    const swPath = path.join(this.buildDir, 'service-worker.js');
    
    if (fs.existsSync(manifestPath) && fs.existsSync(swPath)) {
      this.log('PWA files detected');
      this.optimizations.push('PWA files are present');
    } else {
      this.log('PWA files not found (optional)', 'warning');
    }
  }

  generateReport() {
    console.log('\n' + '='.repeat(60));
    console.log('BUILD OPTIMIZATION REPORT');
    console.log('='.repeat(60));

    if (this.optimizations.length > 0) {
      console.log('\n🎉 OPTIMIZATIONS APPLIED:');
      this.optimizations.forEach(optimization => {
        console.log(`  ✅ ${optimization}`);
      });
    } else {
      console.log('\n✅ Build was already optimized');
    }

    console.log('\n📊 BUILD STATISTICS:');
    
    // Calculate build size
    let totalSize = 0;
    const calculateSize = (dir) => {
      if (!fs.existsSync(dir)) return;
      
      const files = fs.readdirSync(dir);
      files.forEach(file => {
        const filePath = path.join(dir, file);
        const stat = fs.statSync(filePath);
        
        if (stat.isDirectory()) {
          calculateSize(filePath);
        } else {
          totalSize += stat.size;
        }
      });
    };

    calculateSize(this.buildDir);
    const totalSizeMB = (totalSize / 1024 / 1024).toFixed(2);
    console.log(`  📦 Total build size: ${totalSizeMB} MB`);

    // Count files
    let fileCount = 0;
    const countFiles = (dir) => {
      if (!fs.existsSync(dir)) return;
      
      const files = fs.readdirSync(dir);
      files.forEach(file => {
        const filePath = path.join(dir, file);
        const stat = fs.statSync(filePath);
        
        if (stat.isDirectory()) {
          countFiles(filePath);
        } else {
          fileCount++;
        }
      });
    };

    countFiles(this.buildDir);
    console.log(`  📄 Total files: ${fileCount}`);

    console.log('\n' + '='.repeat(60));
  }

  async run() {
    console.log('TikTrue Frontend Build Optimization');
    console.log('='.repeat(40));

    if (!fs.existsSync(this.buildDir)) {
      this.log('Build directory not found. Run npm run build first.', 'error');
      process.exit(1);
    }

    // Run all optimizations
    try {
      this.optimizeIndexHtml();
      this.generateRobotsTxt();
      this.generateSitemap();
      this.optimizeManifest();
      this.compressAssets();
      this.validateAccessibility();
      this.generateSecurityTxt();
      this.optimizeForPWA();
    } catch (error) {
      this.log(`Optimization error: ${error.message}`, 'error');
    }

    // Generate final report
    this.generateReport();
    
    this.log('Build optimization completed!', 'success');
  }
}

// Run optimization if called directly
if (require.main === module) {
  const optimizer = new BuildOptimizer();
  optimizer.run().catch(error => {
    console.error('Optimization failed:', error);
    process.exit(1);
  });
}

module.exports = BuildOptimizer;