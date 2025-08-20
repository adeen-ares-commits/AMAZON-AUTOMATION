@echo off
title Amazon Automation FastAPI Backend
color 0B

echo ========================================
echo Amazon Automation FastAPI Backend
echo ========================================

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org/
    pause
    exit /b 1
)

echo Python found: 
python --version

REM Check if pip is available
pip --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pip is not available
    echo Please ensure pip is installed with Python
    pause
    exit /b 1
)

echo pip found:
pip --version

REM Navigate to backend directory
cd /d "%~dp0"

echo.
echo Installing Python dependencies...
pip install -r requirements.txt

if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Installing Playwright browsers...
playwright install chromium

if errorlevel 1 (
    echo WARNING: Failed to install Playwright browsers
    echo You may need to install them manually: playwright install chromium
)

echo.
echo Starting FastAPI backend server...
echo Backend will be available at: http://localhost:4000
echo API documentation at: http://localhost:4000/docs
echo.
echo Press Ctrl+C to stop the server
echo ========================================

python main.py

pause
