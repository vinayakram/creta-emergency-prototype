@echo off
setlocal
REM Starts backend + frontend in two windows. Assumes setup + ingest are done.
start "Backend API" cmd /k "%~dp003_START_BACKEND.bat"
start "Website" cmd /k "%~dp005_START_WEBSITE.bat"
echo Started two windows: Backend API and Website.
pause
