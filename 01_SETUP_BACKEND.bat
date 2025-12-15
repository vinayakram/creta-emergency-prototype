@echo off
setlocal
cd /d "%~dp0backend"

REM Create venv if missing
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating Python virtual environment...
  py -3.13 -m venv .venv
)

echo [2/3] Activating venv and installing dependencies...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

if not exist ".env" (
  echo [3/3] Creating .env from template...
  copy .env.example .env >nul
)

echo.
echo DONE: Backend is set up.
echo Next: run 02_INGEST_MANUAL.bat
pause
