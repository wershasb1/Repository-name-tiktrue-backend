@echo off
REM TikTrue End-to-End Testing Script for Windows

echo TikTrue Platform - End-to-End Testing Suite
echo ===========================================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is required but not installed
    exit /b 1
)

REM Check if required Python packages are available
python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo Installing required Python packages...
    pip install requests
)

REM Create results directory
set TIMESTAMP=%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set RESULTS_DIR=test_results_%TIMESTAMP%
mkdir "%RESULTS_DIR%"

echo Test results will be saved to: %RESULTS_DIR%
echo.

REM Run the main test suite
echo Running comprehensive end-to-end tests...
python "%~dp0run_e2e_tests.py" > "%RESULTS_DIR%\test_output.log" 2>&1
set TEST_EXIT_CODE=%errorlevel%

REM Move generated report files to results directory
move e2e_test_report_*.json "%RESULTS_DIR%\" >nul 2>&1

REM Additional quick tests
echo.
echo Running additional quick tests...

REM Test website response time (using PowerShell)
echo Testing website response time...
powershell -Command "Measure-Command { Invoke-WebRequest -Uri 'https://tiktrue.com' -UseBasicParsing } | Select-Object -ExpandProperty TotalMilliseconds" > "%RESULTS_DIR%\performance.log"

REM Test API response time
echo Testing API response time...
powershell -Command "Measure-Command { Invoke-WebRequest -Uri 'https://api.tiktrue.com/api/health/' -UseBasicParsing } | Select-Object -ExpandProperty TotalMilliseconds" >> "%RESULTS_DIR%\performance.log"

REM Generate final summary
echo.
echo ==========================================
echo TESTING COMPLETED
echo ==========================================
echo Results directory: %RESULTS_DIR%
echo Main test exit code: %TEST_EXIT_CODE%

if %TEST_EXIT_CODE% equ 0 (
    echo Status: ALL TESTS PASSED ✓
) else (
    echo Status: SOME TESTS FAILED ✗
)

echo.
echo Files generated:
dir "%RESULTS_DIR%"

exit /b %TEST_EXIT_CODE%