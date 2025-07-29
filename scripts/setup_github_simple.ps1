# TikTrue Backend GitHub Setup (Simple Version)
# این اسکریپت فقط git commands را آماده می‌کند

Write-Host "=== TikTrue Backend Git Setup ===" -ForegroundColor Green

# Change to backend directory
Set-Location backend

Write-Host "Git repository is ready!" -ForegroundColor Green
Write-Host ""
Write-Host "Manual steps to create GitHub repository:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Go to https://github.com/new" -ForegroundColor Cyan
Write-Host "2. Repository name: tiktrue-backend" -ForegroundColor Cyan
Write-Host "3. Description: Backend server for TikTrue Distributed LLM Platform" -ForegroundColor Cyan
Write-Host "4. Make it Public" -ForegroundColor Cyan
Write-Host "5. Don't initialize with README (we already have files)" -ForegroundColor Cyan
Write-Host "6. Click 'Create repository'" -ForegroundColor Cyan
Write-Host ""
Write-Host "After creating repository, run these commands:" -ForegroundColor Yellow
Write-Host ""
Write-Host "git branch -M main" -ForegroundColor White
Write-Host "git remote add origin https://github.com/YOUR_USERNAME/tiktrue-backend.git" -ForegroundColor White
Write-Host "git push -u origin main" -ForegroundColor White
Write-Host ""
Write-Host "Replace YOUR_USERNAME with your actual GitHub username" -ForegroundColor Red

# Return to original directory
Set-Location ..

Write-Host ""
Write-Host "=== Ready for GitHub ===" -ForegroundColor Green