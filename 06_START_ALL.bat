@echo off
setlocal

echo ============================================
echo Creta Emergency Assistant — Start All
echo ============================================

REM ------------------------------------------------
REM Activate backend virtual environment
REM ------------------------------------------------
cd /d "%~dp0backend"
call .venv\Scripts\activate.bat

IF ERRORLEVEL 1 (
    echo ❌ Failed to activate backend venv
    exit /b 1
)

REM ------------------------------------------------
REM 1. Run pytest (NO ingestion, NO backend)
REM ------------------------------------------------
echo.
echo [1/6] Running backend tests...
cd tests
pytest

IF ERRORLEVEL 1 (
    echo ❌ Pytest failed. Aborting startup.
    exit /b 1
)

echo ✅ Pytest passed.

REM ------------------------------------------------
REM 2. Start backend
REM ------------------------------------------------
echo.
echo [2/6] Starting backend API...
cd ..
start "Backend API" cmd /k uvicorn app.main:app --port 8000

REM Give backend time to start
timeout /t 5 >nul


REM ------------------------------------------------
REM 4. Run RAG evaluation
REM ------------------------------------------------
echo.
echo [4/6] Running RAG evaluation...
cd evals
python eval_rag.py

IF ERRORLEVEL 1 (
    echo ❌ RAG evaluation failed. Aborting.
    
)

echo ✅ RAG evaluation passed.

REM ------------------------------------------------
REM 5. Start frontend
REM ------------------------------------------------
echo.
echo [5/6] Starting frontend UI...
cd /d "%~dp0frontend"
start "Frontend UI" cmd /k npm run dev

echo.
echo [6/6] System ready.
echo Backend:  http://localhost:8000/docs
echo Frontend: http://localhost:5173

endlocal
