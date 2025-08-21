@echo off
echo Debugging Amazon Automaton Electron App...
echo.
echo Current directory:
cd /d "%~dp0"
pwd
echo.
echo Checking if Vite server is running on port 5173...
curl -s http://localhost:5173 > nul
if %errorlevel% == 0 (
    echo Vite server is running!
) else (
    echo Vite server is NOT running on port 5173
)
echo.
echo Checking if files exist:
if exist "src\index.html" (
    echo src\index.html exists
) else (
    echo src\index.html MISSING
)
if exist "src\App.jsx" (
    echo src\App.jsx exists
) else (
    echo src\App.jsx MISSING
)
if exist "renderer\index.html" (
    echo renderer\index.html exists (built)
) else (
    echo renderer\index.html MISSING (not built yet)
)
echo.
echo Press any key to continue...
pause
