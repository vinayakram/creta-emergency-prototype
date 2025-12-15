@echo off
setlocal
cd /d "%~dp0frontend"

echo Installing frontend dependencies (npm)...
npm install

if not exist ".env" (
  copy .env.example .env >nul
)

echo.
echo DONE: Frontend is set up.
echo Next: run 05_START_WEBSITE.bat
pause
