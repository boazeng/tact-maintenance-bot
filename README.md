# TACT Bots — WhatsApp Bot Platform

A standalone platform for building, editing and running WhatsApp bot scripts.
Copied and decoupled from the urbangroup maintenance system; built in the TACT
design format. Each bot is independent — build a different bot whenever you like.

## What's inside
- **עורך זרימה ויזואלי** — drag-and-drop flow editor (React Flow) — the main way to build/edit bots.
- **מנוע הרצה** — M1000 router + M10010 data-driven script engine + Meta webhook.
- **כלי וואטסאפ** — Meta WhatsApp Cloud API send/receive.

## Architecture (layered)
```
frontend (React + Vite + React Flow, TACT design)
        │  /api  (Vite proxy → 8020)
backend  (FastAPI)  backend/app/api/*
        │
bot engine          agents/bot_engine/{M1000,M10010,integrations}
        │
storage (pluggable) database/maintenance/* → backends/{sqlite,dynamodb}
        │
tools               tools/whatsapp/whatsapp_bot.py
```
Secrets load from the SHARED env file `C:\Users\User\Aiprojects\env\.env`.

## Dev setup (PowerShell)

Backend (FastAPI on :8020) — run from the repo root:
```powershell
cd C:\Users\User\Aiprojects\takt-bots
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8020 --reload
# or: backend\run.ps1
```

Frontend (Vite on :5210):
```powershell
cd C:\Users\User\Aiprojects\takt-bots\frontend
npm install
npm run dev
```
Open http://localhost:5210

## Storage
Default is local **SQLite** at `data/takt-bots.db` (auto-created). To move to AWS
later, set `STORAGE_BACKEND=dynamodb` (and the table-name env vars) — the engine
and API are unchanged; only the backend implementation swaps.

See [CLAUDE.md](CLAUDE.md) for conventions and the full layout.
