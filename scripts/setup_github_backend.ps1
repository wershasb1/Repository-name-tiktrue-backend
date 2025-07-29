# TikTrue Backend GitHub Setup Script
# این اسکریپت backend را به GitHub آپلود می‌کند

Write-Host "=== TikTrue Backend GitHub Setup ===" -ForegroundColor Green

# Check if GitHub CLI is installed
if (!(Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "GitHub CLI (gh) is not installed. Please install it first:" -ForegroundColor Red
    Write-Host "https://cli.github.com/" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Alternative: Create repository manually on GitHub and use these commands:" -ForegroundColor Yellow
    Write-Host "cd backend" -ForegroundColor Cyan
    Write-Host "git remote add origin https://github.com/YOUR_USERNAME/tiktrue-backend.git" -ForegroundColor Cyan
    Write-Host "git branch -M main" -ForegroundColor Cyan
    Write-Host "git push -u origin main" -ForegroundColor Cyan
    exit 1
}

# Check if user is logged in to GitHub
$authStatus = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Please login to GitHub first:" -ForegroundColor Red
    Write-Host "gh auth login" -ForegroundColor Cyan
    exit 1
}

# Change to backend directory
Set-Location backend

Write-Host "Creating GitHub repository..." -ForegroundColor Yellow

# Create GitHub repository
$repoResult = gh repo create tiktrue-backend --public --description "Backend server for TikTrue Distributed LLM Platform" --confirm 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ GitHub repository created successfully!" -ForegroundColor Green
    
    # Push code to GitHub
    Write-Host "Pushing code to GitHub..." -ForegroundColor Yellow
    
    git branch -M main
    git remote add origin "https://github.com/$(gh api user --jq .login)/tiktrue-backend.git"
    git push -u origin main
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Code pushed to GitHub successfully!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Repository URL: https://github.com/$(gh api user --jq .login)/tiktrue-backend" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor Yellow
        Write-Host "1. Go to Liara.ir dashboard" -ForegroundColor White
        Write-Host "2. Connect your GitHub account" -ForegroundColor White
        Write-Host "3. Select tiktrue-backend repository" -ForegroundColor White
        Write-Host "4. Deploy your application" -ForegroundColor White
    } else {
        Write-Host "❌ Failed to push code to GitHub" -ForegroundColor Red
    }
} else {
    Write-Host "❌ Failed to create GitHub repository" -ForegroundColor Red
    Write-Host $repoResult -ForegroundColor Red
}

# Return to original directory
Set-Location ..

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green