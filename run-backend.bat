@echo off
title Korea Job Finder - BACKEND
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
  echo [X] Chua co virtualenv. Chay cac lenh sau trong thu muc backend:
  echo       python -m venv .venv
  echo       .venv\Scripts\python.exe -m pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

echo Backend dang chay tai http://127.0.0.1:8000
echo API docs: http://127.0.0.1:8000/docs
echo (Dong cua so nay de tat backend)
echo.

.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo.
echo Backend da dung.
pause
