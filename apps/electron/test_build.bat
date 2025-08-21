@echo off
echo Building Amazon Automaton Electron App...
echo.
cd /d "%~dp0"
npm run build
echo.
echo Build complete! Starting Electron app...
npm start
pause
