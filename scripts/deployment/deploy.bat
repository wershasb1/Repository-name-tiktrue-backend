@echo off
REM TikTrue Platform Deployment Script for Windows
REM This script provides an easy interface to the Python deployment orchestrator

setlocal enabledelayedexpansion

echo ========================================
echo TikTrue Platform Deployment Tool
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11+ and try again
    pause
    exit /b 1
)

REM Get script directory
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..\..\

REM Change to project root
cd /d "%PROJECT_ROOT%"

REM Check if deployment script exists
if not exist "%SCRIPT_DIR%deploy.py" (
    echo ERROR: deploy.py not found in %SCRIPT_DIR%
    pause
    exit /b 1
)

REM Parse command line arguments
set DRY_RUN=
set CONFIG_FILE=
set ROLLBACK=
set BACKUP_ID=

:parse_args
if "%1"=="" goto end_parse
if "%1"=="--dry-run" set DRY_RUN=--dry-run
if "%1"=="--config" (
    shift
    set CONFIG_FILE=--config "%1"
)
if "%1"=="--rollback" set ROLLBACK=--rollback
if "%1"=="--backup-id" (
    shift
    set BACKUP_ID=--backup-id "%1"
)
shift
goto parse_args
:end_parse

REM Show menu if no arguments provided
if "%DRY_RUN%%CONFIG_FILE%%ROLLBACK%"=="" (
    echo Select deployment option:
    echo.
    echo 1. Full deployment
    echo 2. Dry run (test without executing)
    echo 3. Rollback to previous deployment
    echo 4. Exit
    echo.
    set /p choice="Enter your choice (1-4): "
    
    if "!choice!"=="1" goto full_deploy
    if "!choice!"=="2" goto dry_run
    if "!choice!"=="3" goto rollback
    if "!choice!"=="4" goto exit
    
    echo Invalid choice. Please try again.
    pause
    goto parse_args
)

:full_deploy
echo.
echo Starting full deployment...
echo.
python "%SCRIPT_DIR%deploy.py" %CONFIG_FILE%
goto end

:dry_run
echo.
echo Starting dry run deployment...
echo.
python "%SCRIPT_DIR%deploy.py" --dry-run %CONFIG_FILE%
goto end

:rollback
echo.
echo Available backups:
if exist "%PROJECT_ROOT%temp\deployment_backups" (
    dir /b "%PROJECT_ROOT%temp\deployment_backups"
) else (
    echo No backups found.
    pause
    goto exit
)
echo.
set /p backup_id="Enter backup ID to rollback to (or press Enter to cancel): "
if "!backup_id!"=="" goto exit

echo.
echo Starting rollback to backup: !backup_id!
echo.
python "%SCRIPT_DIR%deploy.py" --rollback --backup-id "!backup_id!"
goto end

:end
echo.
echo Deployment process completed.
echo Check the logs in temp\logs\ for detailed information.
echo.
pause

:exit
exit /b 0