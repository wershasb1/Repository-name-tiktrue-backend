@echo off
echo Uninstalling TikTrue LLM Service...
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Running as administrator - proceeding with uninstallation...
) else (
    echo ERROR: This script must be run as administrator!
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

REM Stop the service first
echo Stopping service if running...
python windows_service.py stop

REM Uninstall the service
python service_installer.py --uninstall

if %errorLevel% == 0 (
    echo.
    echo Service uninstalled successfully!
) else (
    echo.
    echo Service uninstallation failed!
    echo Check the logs for more details.
)

echo.
pause