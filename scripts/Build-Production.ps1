# TikTrue Platform - Production Build Script (PowerShell)
# This script automates the production build process on Windows
# Requirements: 4.1 - Production build system setup

param(
    [string]$Version = "1.0.0",
    [switch]$NoObfuscation,
    [switch]$DryRun,
    [switch]$SkipTests,
    [switch]$CreateInstaller,
    [string]$OutputDir = ""
)

# Script configuration
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Colors for output
$Colors = @{
    Success = "Green"
    Warning = "Yellow" 
    Error = "Red"
    Info = "Cyan"
    Header = "Magenta"
}

function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White",
        [string]$Prefix = ""
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $fullMessage = "[$timestamp] $Prefix$Message"
    Write-Host $fullMessage -ForegroundColor $Color
}

function Write-Success { param([string]$Message) Write-ColorOutput $Message $Colors.Success "✅ " }
function Write-Warning { param([string]$Message) Write-ColorOutput $Message $Colors.Warning "⚠️ " }
function Write-Error { param([string]$Message) Write-ColorOutput $Message $Colors.Error "❌ " }
function Write-Info { param([string]$Message) Write-ColorOutput $Message $Colors.Info "ℹ️ " }
function Write-Header { param([string]$Message) Write-ColorOutput $Message $Colors.Header "🚀 " }

function Test-Command {
    param([string]$Command)
    
    try {
        $null = Get-Command $Command -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

function Test-PythonPackage {
    param([string]$Package)
    
    try {
        $result = python -c "import $Package; print('OK')" 2>$null
        return $result -eq "OK"
    }
    catch {
        return $false
    }
}

function Initialize-BuildEnvironment {
    Write-Header "Initializing build environment..."
    
    # Check Python
    if (-not (Test-Command "python")) {
        Write-Error "Python is not installed or not in PATH"
        return $false
    }
    
    $pythonVersion = python --version 2>&1
    Write-Info "Python version: $pythonVersion"
    
    # Check required packages
    $requiredPackages = @("pyinstaller")
    if (-not $NoObfuscation) {
        $requiredPackages += "pyarmor"
    }
    
    $missingPackages = @()
    foreach ($package in $requiredPackages) {
        if (-not (Test-PythonPackage $package)) {
            $missingPackages += $package
        } else {
            Write-Success "$package is installed"
        }
    }
    
    if ($missingPackages.Count -gt 0) {
        Write-Error "Missing Python packages: $($missingPackages -join ', ')"
        Write-Info "Install missing packages with: pip install $($missingPackages -join ' ')"
        return $false
    }
    
    # Check project structure
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $desktopDir = Join-Path $projectRoot "desktop"
    $mainScript = Join-Path $desktopDir "main_app.py"
    
    if (-not (Test-Path $mainScript)) {
        Write-Error "Main application script not found: $mainScript"
        return $false
    }
    
    Write-Success "Build environment initialized"
    return $true
}

function Invoke-PythonBuild {
    Write-Header "Starting Python build process..."
    
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $buildScript = Join-Path $PSScriptRoot "build_production.py"
    
    if (-not (Test-Path $buildScript)) {
        Write-Error "Build script not found: $buildScript"
        return $false
    }
    
    # Prepare build arguments
    $buildArgs = @("--version", $Version)
    
    if ($NoObfuscation) {
        $buildArgs += "--no-obfuscation"
    }
    
    if ($DryRun) {
        $buildArgs += "--dry-run"
    }
    
    # Execute build
    try {
        Write-Info "Executing: python `"$buildScript`" $($buildArgs -join ' ')"
        
        if ($DryRun) {
            Write-Info "DRY RUN: Would execute Python build script"
            return $true
        }
        
        $process = Start-Process -FilePath "python" -ArgumentList @($buildScript) + $buildArgs -Wait -PassThru -NoNewWindow
        
        if ($process.ExitCode -eq 0) {
            Write-Success "Python build completed successfully"
            return $true
        } else {
            Write-Error "Python build failed with exit code: $($process.ExitCode)"
            return $false
        }
    }
    catch {
        Write-Error "Failed to execute Python build: $($_.Exception.Message)"
        return $false
    }
}

function Test-BuildOutput {
    Write-Header "Testing build output..."
    
    if ($DryRun) {
        Write-Info "DRY RUN: Would test build output"
        return $true
    }
    
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $distDir = Join-Path $projectRoot "dist"
    $mainExe = Join-Path $distDir "TikTrue.exe"
    
    if (-not (Test-Path $mainExe)) {
        Write-Error "Main executable not found: $mainExe"
        return $false
    }
    
    # Check file size
    $fileSize = (Get-Item $mainExe).Length
    $sizeMB = [math]::Round($fileSize / 1MB, 2)
    
    Write-Info "Executable size: $sizeMB MB"
    
    if ($sizeMB -lt 10) {
        Write-Warning "Executable seems too small: $sizeMB MB"
    } elseif ($sizeMB -gt 500) {
        Write-Warning "Executable seems too large: $sizeMB MB"
    } else {
        Write-Success "Executable size looks good: $sizeMB MB"
    }
    
    # Test execution (basic check)
    if (-not $SkipTests) {
        try {
            Write-Info "Testing executable execution..."
            $testProcess = Start-Process -FilePath $mainExe -ArgumentList "--help" -Wait -PassThru -WindowStyle Hidden -ErrorAction SilentlyContinue
            
            if ($testProcess.ExitCode -eq 0) {
                Write-Success "Executable runs successfully"
            } else {
                Write-Warning "Executable test returned non-zero exit code: $($testProcess.ExitCode)"
            }
        }
        catch {
            Write-Warning "Could not test executable execution: $($_.Exception.Message)"
        }
    }
    
    Write-Success "Build output validation completed"
    return $true
}

function New-Installer {
    if (-not $CreateInstaller) {
        Write-Info "Installer creation skipped (use -CreateInstaller to enable)"
        return $true
    }
    
    Write-Header "Creating installer..."
    
    if ($DryRun) {
        Write-Info "DRY RUN: Would create installer"
        return $true
    }
    
    # Check for NSIS
    if (-not (Test-Command "makensis")) {
        Write-Warning "NSIS not found, skipping installer creation"
        Write-Info "Download NSIS from: https://nsis.sourceforge.io/"
        return $true
    }
    
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $installerScript = Join-Path $projectRoot "installer.nsi"
    
    if (-not (Test-Path $installerScript)) {
        Write-Warning "Installer script not found: $installerScript"
        return $true
    }
    
    try {
        Write-Info "Building installer with NSIS..."
        $process = Start-Process -FilePath "makensis" -ArgumentList $installerScript -Wait -PassThru -NoNewWindow
        
        if ($process.ExitCode -eq 0) {
            Write-Success "Installer created successfully"
            return $true
        } else {
            Write-Error "Installer creation failed with exit code: $($process.ExitCode)"
            return $false
        }
    }
    catch {
        Write-Error "Failed to create installer: $($_.Exception.Message)"
        return $false
    }
}

function Copy-BuildOutput {
    if ([string]::IsNullOrEmpty($OutputDir)) {
        Write-Info "No output directory specified, skipping copy"
        return $true
    }
    
    Write-Header "Copying build output..."
    
    if ($DryRun) {
        Write-Info "DRY RUN: Would copy build output to $OutputDir"
        return $true
    }
    
    try {
        $projectRoot = Split-Path -Parent $PSScriptRoot
        $distDir = Join-Path $projectRoot "dist"
        
        if (-not (Test-Path $distDir)) {
            Write-Error "Distribution directory not found: $distDir"
            return $false
        }
        
        # Create output directory
        if (-not (Test-Path $OutputDir)) {
            New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
            Write-Info "Created output directory: $OutputDir"
        }
        
        # Copy files
        $files = Get-ChildItem -Path $distDir -File
        foreach ($file in $files) {
            $destination = Join-Path $OutputDir $file.Name
            Copy-Item -Path $file.FullName -Destination $destination -Force
            Write-Info "Copied: $($file.Name)"
        }
        
        Write-Success "Build output copied to: $OutputDir"
        return $true
    }
    catch {
        Write-Error "Failed to copy build output: $($_.Exception.Message)"
        return $false
    }
}

function Show-BuildSummary {
    Write-Header "Build Summary"
    
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $distDir = Join-Path $projectRoot "dist"
    
    Write-Info "Version: $Version"
    Write-Info "Obfuscation: $(if ($NoObfuscation) { 'Disabled' } else { 'Enabled' })"
    Write-Info "Dry Run: $(if ($DryRun) { 'Yes' } else { 'No' })"
    
    if (-not $DryRun -and (Test-Path $distDir)) {
        Write-Info "Output Directory: $distDir"
        
        $files = Get-ChildItem -Path $distDir -File
        if ($files.Count -gt 0) {
            Write-Info "Generated Files:"
            foreach ($file in $files) {
                $sizeMB = [math]::Round($file.Length / 1MB, 2)
                Write-Info "  📄 $($file.Name) ($sizeMB MB)"
            }
        }
    }
    
    if ($OutputDir -and -not $DryRun) {
        Write-Info "Files copied to: $OutputDir"
    }
}

# Main execution
try {
    Write-Header "TikTrue Production Build Script"
    Write-Info "Version: $Version"
    Write-Info "Started at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    
    # Step 1: Initialize environment
    if (-not (Initialize-BuildEnvironment)) {
        exit 1
    }
    
    # Step 2: Run Python build
    if (-not (Invoke-PythonBuild)) {
        exit 1
    }
    
    # Step 3: Test build output
    if (-not (Test-BuildOutput)) {
        exit 1
    }
    
    # Step 4: Create installer (optional)
    if (-not (New-Installer)) {
        exit 1
    }
    
    # Step 5: Copy output (optional)
    if (-not (Copy-BuildOutput)) {
        exit 1
    }
    
    # Step 6: Show summary
    Show-BuildSummary
    
    Write-Success "Production build completed successfully!"
    Write-Info "Finished at: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    
    exit 0
}
catch {
    Write-Error "Build script failed: $($_.Exception.Message)"
    Write-Error "Stack trace: $($_.ScriptStackTrace)"
    exit 1
}