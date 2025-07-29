# Frontend Deployment Checklist

## Pre-Deployment Checklist

### Environment Variables
- [ ] `REACT_APP_API_BASE_URL` - Backend API URL
- [ ] `REACT_APP_FRONTEND_URL` - Frontend URL
- [ ] `REACT_APP_BACKEND_URL` - Backend base URL
- [ ] `GENERATE_SOURCEMAP` - Set to false for production

### Configuration Files
- [ ] `liara.json` - Verify static platform configuration
- [ ] `package.json` - All dependencies included and up to date
- [ ] `.env.production` - Production environment variables set
- [ ] `tailwind.config.js` - CSS framework configured
- [ ] `postcss.config.js` - PostCSS processing configured

### Code Quality
- [ ] Build process works locally (`npm run build`)
- [ ] No ESLint errors or warnings
- [ ] All components render without errors
- [ ] Responsive design tested on multiple screen sizes
- [ ] Cross-browser compatibility verified

## Deployment Process

### 1. Deploy to Liara
```bash
# Install Liara CLI if not already installed
npm install -g @liara/cli

# Login to Liara
liara login

# Deploy the application
liara deploy --app your-frontend-app --platform static
```

### 2. Verify Build Configuration
In Liara dashboard:
1. Go to your static app
2. Check build logs for any errors
3. Verify build output directory is correct
4. Ensure SPA routing is enabled

### 3. Domain Configuration
```bash
# Add custom domain (if needed)
liara domain add yourdomain.com --app your-frontend-app

# Verify SSL certificate
curl -I https://yourdomain.com
```

## Post-Deployment Verification

### Basic Functionality
- [ ] Website loads at custom domain
- [ ] Homepage renders correctly
- [ ] Navigation works properly
- [ ] All pages accessible via direct URLs
- [ ] No console errors in browser

### SPA Routing
- [ ] Direct URL access works (e.g., /dashboard)
- [ ] Browser back/forward buttons work
- [ ] Page refresh doesn't return 404
- [ ] All routes render correct components

### API Connectivity
- [ ] API calls reach backend successfully
- [ ] CORS headers present in responses
- [ ] Authentication flow works
- [ ] Error handling displays properly

### Performance
- [ ] Page load time under 3 seconds
- [ ] Images load properly
- [ ] CSS and JS files cached correctly
- [ ] No unnecessary network requests

### Security
- [ ] HTTPS redirect works
- [ ] Security headers present
- [ ] No sensitive data in client-side code
- [ ] Content Security Policy working

## Troubleshooting

### Common Issues

**Build fails on Liara:**
- Check for ESLint warnings (use `CI=false` in build command)
- Verify all dependencies are in `dependencies`, not `devDependencies`
- Check for memory issues during build

**SPA routing not working:**
- Verify `spa: true` in liara.json
- Check that React Router is using BrowserRouter
- Ensure all routes have proper error boundaries

**API calls failing:**
- Check CORS configuration on backend
- Verify API URLs in environment variables
- Test API endpoints directly with curl

**Static files not loading:**
- Check build output directory in liara.json
- Verify static file paths in code
- Check browser network tab for 404 errors

### Useful Commands
```bash
# Check deployment logs
liara logs --app your-frontend-app --tail

# Test build locally
npm run build
npx serve -s build -l 3000

# Analyze bundle size
npm run build:analyze

# Check for security vulnerabilities
npm audit

# Update dependencies
npm update
```

## Performance Optimization

### Bundle Size Optimization
- [ ] Implement code splitting for large components
- [ ] Use lazy loading for non-critical routes
- [ ] Optimize images (WebP format, proper sizing)
- [ ] Remove unused dependencies

### Caching Strategy
- [ ] Static assets cached for 1 year
- [ ] HTML files not cached
- [ ] API responses cached appropriately
- [ ] Service worker implemented (if needed)

### Loading Performance
- [ ] Critical CSS inlined
- [ ] Non-critical resources lazy loaded
- [ ] Preload important resources
- [ ] Minimize render-blocking resources

## Security Checklist

### Content Security Policy
- [ ] CSP headers configured
- [ ] Script sources whitelisted
- [ ] Image sources controlled
- [ ] No inline scripts or styles

### Data Protection
- [ ] No sensitive data in environment variables
- [ ] API keys handled on backend only
- [ ] User input properly sanitized
- [ ] XSS protection implemented

### HTTPS Configuration
- [ ] SSL certificate valid
- [ ] HTTPS redirect working
- [ ] Mixed content issues resolved
- [ ] Secure cookies used

## Monitoring and Maintenance

### Health Monitoring
- [ ] Uptime monitoring configured
- [ ] Error tracking implemented
- [ ] Performance monitoring active
- [ ] User analytics configured

### Regular Maintenance
- [ ] Dependencies updated monthly
- [ ] Security patches applied
- [ ] Performance metrics reviewed
- [ ] User feedback incorporated

### Backup and Recovery
- [ ] Source code in version control
- [ ] Build artifacts backed up
- [ ] Deployment process documented
- [ ] Rollback procedure tested

## Rollback Procedure

If deployment fails:
1. Check deployment logs: `liara logs --app your-frontend-app`
2. Identify the issue (build failure, configuration error, etc.)
3. Fix the issue in code
4. Redeploy: `liara deploy --app your-frontend-app`
5. If critical, rollback to previous version (if available)

## Success Criteria

### Functionality
- ✅ All pages load without errors
- ✅ Navigation works correctly
- ✅ API integration functional
- ✅ Authentication flow complete
- ✅ Responsive design working

### Performance
- ✅ Page load time < 3 seconds
- ✅ Bundle size optimized
- ✅ Images optimized
- ✅ Caching configured properly

### Security
- ✅ HTTPS enforced
- ✅ Security headers present
- ✅ No sensitive data exposed
- ✅ CSP configured

### SEO and Accessibility
- ✅ Meta tags configured
- ✅ Semantic HTML used
- ✅ Alt text for images
- ✅ Keyboard navigation working