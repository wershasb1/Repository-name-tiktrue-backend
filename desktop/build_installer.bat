@echo off
REM Build script for TikTrue Distributed LLM Platform Installer

echo Building TikTrue LLM Platform Installer...
echo.

REM Check if NSIS is installed
where makensis >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: NSIS (Nullsoft Scriptable Install System) is not installed or not in PATH.
    echo Please download and install NSIS from: https://nsis.sourceforge.io/
    echo.
    pause
    exit /b 1
)

REM Create installer directory if it doesn't exist
if not exist "installer" mkdir installer

REM Copy required files to installer directory
echo Copying application files...
copy "*.py" installer\ >nul 2>nul
copy "*.txt" installer\ >nul 2>nul
copy "*.md" installer\ >nul 2>nul
copy "*.json" installer\ >nul 2>nul

REM Copy data directory
if exist "data" (
    if not exist "installer\data" mkdir installer\data
    copy "data\*" installer\data\ >nul 2>nul
)

REM Create assets directory and copy icon if available
if not exist "installer\assets" mkdir installer\assets
if exist "assets\icon.ico" (
    copy "assets\icon.ico" installer\assets\ >nul 2>nul
) else (
    echo Warning: Icon file not found, using default
)

REM Create LICENSE.txt if it doesn't exist
if not exist "installer\LICENSE.txt" (
    echo Creating default LICENSE.txt...
    echo TikTrue Distributed LLM Platform > installer\LICENSE.txt
    echo Copyright (c) 2024 TikTrue Technologies >> installer\LICENSE.txt
    echo. >> installer\LICENSE.txt
    echo This software is provided "as is" without warranty. >> installer\LICENSE.txt
)

REM Download Python embedded if not present
if not exist "installer\python-3.11.0-embed-amd64.zip" (
    echo Warning: Python embedded package not found.
    echo Please download python-3.11.0-embed-amd64.zip from python.org
    echo and place it in the installer directory.
)

REM Download VC++ Redistributable if not present
if not exist "installer\vc_redist.x64.exe" (
    echo Warning: Visual C++ Redistributable not found.
    echo Please download vc_redist.x64.exe from Microsoft
    echo and place it in the installer directory.
)

REM Build the installer
echo Building installer with NSIS...
cd installer
makensis ..\installer.nsi

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: Installer built successfully!
    echo Output: TikTrueLLM_Setup_1.0.0.exe
    echo.
    
    REM Move installer to root directory
    if exist "TikTrueLLM_Setup_1.0.0.exe" (
        move "TikTrueLLM_Setup_1.0.0.exe" "..\TikTrueLLM_Setup_1.0.0.exe"
        echo Installer moved to root directory.
    )
) else (
    echo.
    echo ERROR: Failed to build installer!
    echo Check the NSIS output above for details.
)

cd ..
echo.
pause