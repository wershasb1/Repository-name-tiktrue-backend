@echo off
REM TikTrue Platform - Production Build Batch Script
REM This script provides an easy way to run the production build on Windows
REM Requirements: 4.1 - Production build system setup

setlocal enabledelayedexpansion

echo.
echo ========================================
echo TikTrue Production Build System
echo ========================================
echo.

REM Get script directory
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

REM Default values
set "VERSION=1.0.0"
set "OBFUSCATION=true"
set "DRY_RUN=false"
set "CREATE_INSTALLER=false"
set "SKIP_TESTS=false"

REM Parse command line arguments
:parse_args
if "%~1"=="" goto :args_done
if /i "%~1"=="--version" (
    set "VERSION=%~2"
    shift
    shift
    goto :parse_args
)
if /i "%~1"=="--no-obfuscation" (
    set "OBFUSCATION=false"
    shift
    goto :parse_args
)
if /i "%~1"=="--dry-run" (
    set "DRY_RUN=true"
    shift
    goto :parse_args
)
if /i "%~1"=="--create-installer" (
    set "CREATE_INSTALLER=true"
    shift
    goto :parse_args
)
if /i "%~1"=="--skip-tests" (
    set "SKIP_TESTS=true"
    shift
    goto :parse_args
)
if /i "%~1"=="--help" (
    goto :show_help
)
shift
goto :parse_args

:args_done

echo Build Configuration:
echo   Version: %VERSION%
echo   Obfuscation: %OBFUSCATION%
echo   Dry Run: %DRY_RUN%
echo   Create Installer: %CREATE_INSTALLER%
echo   Skip Tests: %SKIP_TESTS%
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11+ and try again
    goto :error
)

REM Check if PowerShell is available (for advanced features)
powershell -Command "Get-Host" >nul 2>&1
if not errorlevel 1 (
    echo Using PowerShell build script for enhanced features...
    
    REM Build PowerShell command
    set "PS_CMD=powershell -ExecutionPolicy Bypass -File \"%SCRIPT_DIR%Build-Production.ps1\""
    set "PS_CMD=!PS_CMD! -Version \"%VERSION%\""
    
    if "%OBFUSCATION%"=="false" (
        set "PS_CMD=!PS_CMD! -NoObfuscation"
    )
    if "%DRY_RUN%"=="true" (
        set "PS_CMD=!PS_CMD! -DryRun"
    )
    if "%CREATE_INSTALLER%"=="true" (
        set "PS_CMD=!PS_CMD! -CreateInstaller"
    )
    if "%SKIP_TESTS%"=="true" (
        set "PS_CMD=!PS_CMD! -SkipTests"
    )
    
    echo Executing: !PS_CMD!
    !PS_CMD!
    
    if errorlevel 1 (
        echo.
        echo ERROR: PowerShell build failed
        goto :error
    )
) else (
    echo PowerShell not available, using Python build script directly...
    
    REM Build Python command
    set "PY_CMD=python \"%SCRIPT_DIR%build_production.py\""
    set "PY_CMD=!PY_CMD! --version \"%VERSION%\""
    
    if "%OBFUSCATION%"=="false" (
        set "PY_CMD=!PY_CMD! --no-obfuscation"
    )
    if "%DRY_RUN%"=="true" (
        set "PY_CMD=!PY_CMD! --dry-run"
    )
    
    echo Executing: !PY_CMD!
    !PY_CMD!
    
    if errorlevel 1 (
        echo.
        echo ERROR: Python build failed
        goto :error
    )
)

echo.
echo ========================================
echo Build completed successfully!
echo ========================================
echo.

REM Show output location
if exist "%PROJECT_ROOT%\dist" (
    echo Output files:
    dir /b "%PROJECT_ROOT%\dist\*.exe" 2>nul
    echo.
    echo Location: %PROJECT_ROOT%\dist
)

echo Build finished at: %date% %time%
echo.
pause
goto :end

:show_help
echo.
echo TikTrue Production Build System
echo.
echo Usage: %~nx0 [options]
echo.
echo Options:
echo   --version VERSION        Set application version (default: 1.0.0)
echo   --no-obfuscation        Disable PyArmor code obfuscation
echo   --dry-run               Perform dry run without making changes
echo   --create-installer      Create NSIS installer (requires NSIS)
echo   --skip-tests            Skip executable testing
echo   --help                  Show this help message
echo.
echo Examples:
echo   %~nx0 --version 2.0.0
echo   %~nx0 --no-obfuscation --dry-run
echo   %~nx0 --create-installer
echo.
goto :end

:error
echo.
echo ========================================
echo Build failed!
echo ========================================
echo.
echo Please check the error messages above and try again.
echo.
pause
exit /b 1

:end
endlocal