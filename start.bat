@echo off
rem ── takt-bots — start everything in its own stable windows ──
rem Run this once (double-click). Each service gets its own window that stays
rem open independently. Close a window to stop that service.
cd /d "%~dp0"

start "takt-bots backend  (8020)" cmd /k "backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8020"
start "takt-bots frontend (5210)" cmd /k "cd frontend && npm run dev"
start "takt-bots Telegram bot"    cmd /k "backend\.venv\Scripts\python.exe run_telegram.py"

echo.
echo   Backend :  http://localhost:8020
echo   Frontend:  http://localhost:5210   (open this)
echo   Telegram:  @Tact_maintenance_bot    (long polling)
echo.
echo   Three windows opened. Keep them running. Close a window to stop that part.
timeout /t 6 >nul
