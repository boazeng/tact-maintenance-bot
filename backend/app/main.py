"""
takt-bots backend — FastAPI application entry point.

Layering: api (this package) -> bot engine (agents/bot_engine) -> storage
(database/maintenance) -> tools (tools/whatsapp). Secrets load from the shared
env file via backend.app.config (imported first for its sys.path + env side-effects).
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings  # noqa: F401  (sets sys.path + loads shared env)
from backend.app.api import scripts, sessions, whatsapp, bot_test

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("taktbots")

app = FastAPI(title="takt-bots", description="WhatsApp bot platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scripts.router)
app.include_router(sessions.router)
app.include_router(whatsapp.router)
app.include_router(bot_test.router)


@app.get("/api/health")
def health():
    return {"ok": True, "service": "takt-bots", "storage": settings.storage_backend}


@app.on_event("startup")
def _seed():
    """Seed a demo script on first run so the editor has something to open."""
    try:
        from agents.bot_engine import M10010_bot
        M10010_bot.seed_default_script()
    except Exception as e:
        logger.warning(f"Demo script seed skipped: {e}")
