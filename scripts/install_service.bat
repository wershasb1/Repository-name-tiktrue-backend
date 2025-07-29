@echo off
echo Installing TikTrue LLM Service...
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% == 0 (
    echo Running as administrator - proceeding with installation...
) else (
    echo ERROR: This script must be run as administrator!
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

REM Install the service
python service_installer.py --install

if %errorLevel% == 0 (
    echo.
    echo Service installed successfully!
    echo You can now start the service using:
    echo   - Services.msc (Windows Services Manager)
    echo   - scripts\start_service.bat
    echo   - python windows_service.py start
) else (
    echo.
    echo Service installation failed!
    echo Check the logs for more details.
)

echo.
pause