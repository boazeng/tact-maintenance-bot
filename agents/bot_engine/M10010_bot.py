"""
M10010 - Data-Driven Bot Script Engine (facade).

The engine reads conversation scripts from storage and executes them step by
step — no hardcoded flow. The implementation is split by responsibility under
the ``m10010`` package; this module re-exports the public API so existing
imports (``from agents.bot_engine import M10010_bot``) keep working.

Flow:
  Message arrives → M1000 router → hands off to M10010
  M10010 loads script → greets customer → follows step flow → runs done action
"""

from agents.bot_engine.m10010.state import (
    SESSION_TTL_SECONDS, DEFAULT_SCRIPT_ID,
)
from agents.bot_engine.m10010.engine import (
    reset_session, get_active_session, start_session, process_message,
)
from agents.bot_engine.m10010.seed import seed_default_script

__all__ = [
    "SESSION_TTL_SECONDS",
    "DEFAULT_SCRIPT_ID",
    "reset_session",
    "get_active_session",
    "start_session",
    "process_message",
    "seed_default_script",
]
