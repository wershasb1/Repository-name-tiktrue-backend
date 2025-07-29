@echo off
REM Security and Performance Validation Script for Windows

echo TikTrue Platform - Security and Performance Validation
echo =====================================================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is required but not installed
    exit /b 1
)

REM Check if required Python packages are available
python -c "import requests, ssl, socket" >nul 2>&1
if errorlevel 1 (
    echo Installing required Python packages...
    pip install requests
)

REM Create results directory
set TIMESTAMP=%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set RESULTS_DIR=validation_results_%TIMESTAMP%
mkdir "%RESULTS_DIR%"

echo Results will be saved to: %RESULTS_DIR%
echo.

REM Run the validation script
echo Running security and performance validation...
python "%~dp0validate_security_performance.py" %1 %2 > "%RESULTS_DIR%\validation_output.log" 2>&1
set VALIDATION_EXIT_CODE=%errorlevel%

REM Move generated report files to results directory
move security_performance_report_*.json "%RESULTS_DIR%\" >nul 2>&1

REM Generate final summary
echo.
echo =====================================================
echo VALIDATION COMPLETED
echo =====================================================
echo Results directory: %RESULTS_DIR%
echo Validation exit code: %VALIDATION_EXIT_CODE%

if %VALIDATION_EXIT_CODE% equ 0 (
    echo Status: ALL VALIDATIONS PASSED ✓
) else (
    echo Status: SOME VALIDATIONS FAILED ✗
)

echo.
echo Files generated:
dir "%RESULTS_DIR%"

echo.
echo To view detailed results:
echo   type "%RESULTS_DIR%\validation_output.log"

exit /b %VALIDATION_EXIT_CODE%