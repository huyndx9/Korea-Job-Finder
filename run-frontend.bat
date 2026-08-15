@echo off
title Korea Job Finder - FRONTEND
cd /d "%~dp0frontend"

if not exist "node_modules" (
  echo [X] Chua cai dependencies. Chay trong thu muc frontend:
  echo       npm install
  echo.
  pause
  exit /b 1
)

echo Frontend dang chay tai http://localhost:5173
echo (Dong cua so nay de tat frontend)
echo.

npm run dev

echo.
echo Frontend da dung.
pause
