@echo off
setlocal
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Backend not set up yet.
  echo Run 01_SETUP_BACKEND.bat first.
  pause
  exit /b 1
)

if not exist "data\creta_manual.pdf" (
  echo ERROR: PDF not found at backend\data\creta_manual.pdf
  echo Please download the manual and put it in backend\data\ as creta_manual.pdf
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat

echo Ingesting manual into Qdrant local database...
python -m app.rag.ingest --pdf data\creta_manual.txt

echo.
echo DONE: Manual indexed.
echo Next: run 03_START_BACKEND.bat
pause
