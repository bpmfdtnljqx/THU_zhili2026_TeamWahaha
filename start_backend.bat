@echo off
REM ============================================
REM  Lyra Backend Launcher
REM  Starts the FastAPI server on port 8000.
REM  Run this from the project root (lyra/).
REM ============================================

cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo Starting Lyra backend on http://127.0.0.1:8000 ...
echo.
echo   Health check: http://127.0.0.1:8000/health
echo   API docs:    http://127.0.0.1:8000/docs
echo   Press Ctrl+C to stop.
echo.

uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
