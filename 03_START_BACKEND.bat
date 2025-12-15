@echo off
setlocal
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Backend not set up yet.
  echo Run 01_SETUP_BACKEND.bat first.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
echo Starting backend API...
echo Leave this window open.
uvicorn app.main:app --reload --port 8000
