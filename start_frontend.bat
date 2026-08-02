@echo off
REM ============================================
REM  Lyra Frontend Launcher
REM  Opens the demo UI in the default browser.
REM  The backend must already be running.
REM ============================================

cd /d "%~dp0"

REM Detect backend URL — pass as argument or use default
set "API_URL=http://127.0.0.1:8000"
if not "%~1"=="" set "API_URL=%~1"

REM Build a file:// URL so the query parameter (?api=...) is
REM interpreted by the browser, not as part of a filename.
REM %~dp0 is the directory of this script (with trailing backslash).
set "RAW=%~dp0frontend\index.html"
set "FILE_URL=file:///%RAW:\=/%"

start "" "%FILE_URL%?api=%API_URL%"

echo Lyra frontend opened in your browser.
echo Backend URL: %API_URL%
echo.
