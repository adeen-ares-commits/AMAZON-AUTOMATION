@echo off
echo ========================================
echo Amazon Automaton - Build & Run Script
echo ========================================
echo.

echo Step 1: Installing dependencies...
npm install
if %errorlevel% neq 0 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Step 2: Building the application...
npm run build
if %errorlevel% neq 0 (
    echo Error: Failed to build the application
    pause
    exit /b 1
)

echo.
echo Step 3: Starting the application...
echo Make sure your backend server is running on localhost:4000
echo.
npm start

pause
