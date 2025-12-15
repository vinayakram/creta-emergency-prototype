@echo off
setlocal
cd /d "%~dp0frontend"
echo Starting website...
echo Leave this window open.
npm run dev
