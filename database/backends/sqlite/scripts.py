"""SQLite backend for bot conversation scripts (mirrors bot_scripts_db API)."""

import time
import logging
from datetime import datetime

from . import _base

logger = logging.getLogger("taktbots.scripts")

# In-memory cache: {script_id: {"data": {...}, "fetched_at": ts}}
_cache = {}
CACHE_TTL_SECONDS = 300


def get_script(script_id, use_cache=True):
    """Get a bot script by ID. Returns dict or None."""
    if use_cache:
        cached = _cache.get(script_id)
        if cached and (time.time() - cached["fetched_at"]) < CACHE_TTL_SECONDS:
            return cached["data"]
    data = _base.get("bot_scripts", script_id)
    if data is not None:
        _cache[script_id] = {"data": data, "fetched_at": time.time()}
    return data


def save_script(script_data):
    """Save or update a bot script. Returns {'script_id': ...}."""
    now = datetime.utcnow().isoformat() + "Z"
    script_data["updated_at"] = now
    if not script_data.get("created_at"):
        script_data["created_at"] = now
    sid = script_data["script_id"]
    _base.put("bot_scripts", sid, script_data)
    _cache.pop(sid, None)
    logger.info(f"Script saved: {sid}")
    return {"script_id": sid}


def list_scripts():
    """List all bot scripts."""
    return _base.list_all("bot_scripts")


def delete_script(script_id):
    """Delete a bot script."""
    _base.delete("bot_scripts", script_id)
    _cache.pop(script_id, None)
    logger.info(f"Script deleted: {script_id}")


def invalidate_cache(script_id=None):
    """Clear cached script(s)."""
    if script_id:
        _cache.pop(script_id, None)
    else:
        _cache.clear()
