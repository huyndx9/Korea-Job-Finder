@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo    Korea Job Finder
echo ==========================================
echo.
echo Moi server chay trong mot cua so rieng,
echo doc lap voi cua so nay.
echo.

echo [1/2] Mo BACKEND  -^> http://127.0.0.1:8000
start "Korea Job Finder - BACKEND" "%~dp0run-backend.bat"

echo [2/2] Mo FRONTEND -^> http://localhost:5173
start "Korea Job Finder - FRONTEND" "%~dp0run-frontend.bat"

echo.
echo Dang doi server san sang...
timeout /t 10 /nobreak >nul

start "" http://localhost:5173

echo.
echo ------------------------------------------
echo   Giao dien : http://localhost:5173
echo   API docs  : http://127.0.0.1:8000/docs
echo.
echo   DE TAT: dong 2 cua so BACKEND va FRONTEND.
echo ------------------------------------------
echo.
pause
