# CLAUDE.md — takt-bots

Standalone WhatsApp bot platform, copied from urbangroup and rebuilt in TACT format.

## Project rules
- **Max 500–600 lines per source file.** Split by responsibility before hitting the limit.
  The engine lives in the `agents/bot_engine/m10010/` package (state / scripts / steps /
  done_actions / engine / seed), all under the limit; `M10010_bot.py` is a thin facade
  that re-exports the public API.
- **Layering — imports flow downward only:**
  `api → bot engine → storage → tools`. The API never reaches into the storage backend
  directly; it goes through `database/maintenance/*`.
- **No urbangroup coupling.** Priority-ERP / CRM integrations are NOT bundled; they are
  pluggable behind feature flags in `agents/bot_engine/integrations.py` (off by default).

## Layout
```
backend/app/        FastAPI: config.py, main.py, api/{scripts,sessions,whatsapp}.py
agents/bot_engine/  M1000_bot.py (router), M10010_bot.py (engine facade),
                    m10010/ (engine package), integrations.py (pluggable stubs)
tools/whatsapp/     whatsapp_bot.py (Meta Cloud API)
database/
  maintenance/      dispatchers the engine imports (bot_scripts_db, troubleshoot_sessions_db,
                    maintenance_db, bot_prompts_db) — select backend via STORAGE_BACKEND
  backends/sqlite/  local backend (default): scripts, sessions, messages, prompts
  backends/dynamodb/ AWS backend (for production), copied from urbangroup
  schema.sql        reference SQLite schema (tables auto-created at runtime)
frontend/src/       React + Vite (JSX). App.jsx = TACT shell; pages/ = copied editor
  pages/BotFlowEditor/  visual flow editor (React Flow / @xyflow/react) — kept as-is
  styles/           tokens.css + recipes.css + TactLogo.css (TACT design system)
shared_env.py       loads the SHARED env file into os.environ (single source of truth)
data/               takt-bots.db (SQLite, gitignored)
```

## Environment
All secrets come from the SHARED env file `C:\Users\User\Aiprojects\env\.env`
(override with `TAKT_SHARED_ENV`). `shared_env.py` loads it; `backend/app/config.py`
surfaces it via pydantic-settings with `extra="ignore"`. Nothing is duplicated locally.
See `.env.example` for the variable list.

## Storage backend swap (local → AWS)
- Local (default): `STORAGE_BACKEND=sqlite` → `data/takt-bots.db`.
- AWS: `STORAGE_BACKEND=dynamodb` + table-name env vars. Engine/API unchanged.
- Each record is stored as a JSON blob keyed by its PK, mirroring the DynamoDB shape,
  so scripts/sessions round-trip identically across backends.

## Run
- Backend: from repo root, `backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8020`
- Frontend: `cd frontend; npm run dev` (port 5210, proxies `/api` → 8020)

## API surface
- `GET/POST /api/bot-scripts`, `GET/PUT/DELETE /api/bot-scripts/{id}` (used by the visual editor)
- `GET /api/bot-sessions` ; `GET/POST /api/bot-prompts`, `GET /api/bot-prompts/active`, `PUT /api/bot-prompts/{id}`
- `GET/POST /api/whatsapp/webhook` (Meta verify + incoming), `POST /api/whatsapp/send`
- `GET /api/health`

## Out of scope (v1 follow-ups)
- One-time migration of existing urbangroup scripts when moving to DynamoDB.
- Knowledge-base / RAG training page (urbangroup-specific; can be added later).
