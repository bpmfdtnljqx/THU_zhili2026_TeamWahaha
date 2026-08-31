@echo off
setlocal EnableExtensions
title Lyra - AI Music Companion
cd /d "%~dp0"

echo.
echo ========================================
echo         LYRA AI MUSIC COMPANION
echo ========================================
echo.

REM --- If the backend is already running, just open the frontend ---
curl -sf http://127.0.0.1:8000/health >nul 2>&1
if not errorlevel 1 (
    echo [OK] Backend is already running.
    goto open_frontend
)

REM --- 1. Virtual environment ---
set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
if exist "%PYTHON_EXE%" goto venv_ready

echo [1/4] Creating virtual environment .venv ...

set "BASE_PY="
py -3.11 --version >nul 2>&1
if not errorlevel 1 set "BASE_PY=py -3.11"

if defined BASE_PY goto create_venv
python --version >nul 2>&1
if not errorlevel 1 set "BASE_PY=python"

:create_venv
if not defined BASE_PY (
    echo.
    echo [ERROR] Python not found. Please install Python 3.11
    echo          from https://www.python.org/downloads/ and run
    echo          this script again.
    echo.
    pause
    exit /b 1
)

%BASE_PY% -m venv .venv
if errorlevel 1 (
    echo [ERROR] Failed to create the virtual environment.
    pause
    exit /b 1
)

:venv_ready
echo [OK] Virtual environment ready.

REM --- 2. Dependencies (first run only) ---
"%PYTHON_EXE%" -c "import fastapi, uvicorn, chromadb, sentence_transformers" >nul 2>&1
if errorlevel 1 (
    echo [2/4] Installing dependencies - first run only, this may take
    echo       a few minutes ...
    "%PYTHON_EXE%" -m pip install --upgrade pip >nul
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed. Check your network
        echo          connection and run this script again.
        pause
        exit /b 1
    )
)
echo [OK] Python dependencies ready.

if not exist "%CD%\.env" (
    echo [WARN] .env not found - recognition and composition need API
    echo        keys. Copy .env.example to .env and fill it in.
)

REM --- 3. Music knowledge index (first run only) ---
if not exist "%CD%\chroma_db\chroma.sqlite3" (
    echo [3/4] Building the music knowledge index - first run only ...
    "%PYTHON_EXE%" "%CD%\src\build_index.py"
    if errorlevel 1 (
        echo [ERROR] Index build failed.
        pause
        exit /b 1
    )
)
echo [OK] Music knowledge index ready.

REM --- 4. Backend ---
echo [4/4] Starting backend at http://127.0.0.1:8000 ...
start "Lyra Backend" cmd /k ""%PYTHON_EXE%" -m uvicorn backend.app:app --host 127.0.0.1 --port 8000"

echo       Waiting for the backend to become ready ...
set /a TRIES=0
:wait_backend
ping -n 3 127.0.0.1 >nul
curl -sf http://127.0.0.1:8000/health >nul 2>&1
if not errorlevel 1 goto backend_ready
set /a TRIES+=1
if %TRIES% lss 15 goto wait_backend
echo [WARN] Backend not ready after 30s - opening the frontend anyway.

:backend_ready
:open_frontend
REM --- Open the frontend in the default browser ---
set "RAW=%~dp0frontend\index.html"
set "FILE_URL=file:///%RAW:\=/%"
start "" "%FILE_URL%?api=http://127.0.0.1:8000"

echo.
echo ========================================
echo  Backend : http://127.0.0.1:8000
echo  API docs: http://127.0.0.1:8000/docs
echo  Stop    : close the "Lyra Backend" window
echo ========================================
echo.
echo Lyra is ready.
echo.
pause
