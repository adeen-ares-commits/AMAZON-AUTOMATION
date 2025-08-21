@echo off
echo Starting Amazon Automaton Electron App...
echo.
echo Make sure the backend server is running on localhost:4000
echo.
echo Starting Vite dev server and Electron...
cd /d "%~dp0"
npm run dev
pause
