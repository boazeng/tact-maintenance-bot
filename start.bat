@echo off
rem ── takt-bots — start backend (8020) + frontend (5210) in their own windows ──
rem Run this once; the two windows stay open independently. Close them to stop.
cd /d "%~dp0"

start "takt-bots backend  (8020)" cmd /k "backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8020"
start "takt-bots frontend (5210)" cmd /k "cd frontend && npm run dev"

echo.
echo   Backend :  http://localhost:8020
echo   Frontend:  http://localhost:5210   (open this)
echo.
echo   Two windows opened. Keep them running. Close them to stop the app.
timeout /t 6 >nul
