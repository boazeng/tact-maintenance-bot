"""SQLite backend for LLM system prompts (mirrors bot_prompts_db API)."""

import time
import logging
from datetime import datetime

from . import _base

logger = logging.getLogger("taktbots.prompts")

_cache = {}
CACHE_TTL_SECONDS = 300


def get_active_prompt(use_cache=True):
    """Get the currently active LLM prompt, or None."""
    if use_cache:
        cached = _cache.get("active")
        if cached and (time.time() - cached["fetched_at"]) < CACHE_TTL_SECONDS:
            return cached["data"]
    for item in _base.list_all("bot_prompts"):
        if item.get("active"):
            _cache["active"] = {"data": item, "fetched_at": time.time()}
            return item
    return None


def get_prompt(prompt_id, use_cache=True):
    """Get a prompt by ID, or None."""
    if use_cache:
        cached = _cache.get(prompt_id)
        if cached and (time.time() - cached["fetched_at"]) < CACHE_TTL_SECONDS:
            return cached["data"]
    data = _base.get("bot_prompts", prompt_id)
    if data is not None:
        _cache[prompt_id] = {"data": data, "fetched_at": time.time()}
    return data


def save_prompt(prompt_data):
    """Save or update a prompt. Returns {'prompt_id': ...}."""
    now = datetime.utcnow().isoformat() + "Z"
    prompt_data["updated_at"] = now
    if not prompt_data.get("created_at"):
        prompt_data["created_at"] = now
    pid = prompt_data["prompt_id"]
    _base.put("bot_prompts", pid, prompt_data)
    _cache.pop(pid, None)
    _cache.pop("active", None)
    logger.info(f"Prompt saved: {pid}")
    return {"prompt_id": pid}


def list_prompts():
    """List all prompts."""
    return _base.list_all("bot_prompts")


def invalidate_cache(prompt_id=None):
    """Clear cached prompt(s)."""
    if prompt_id:
        _cache.pop(prompt_id, None)
        _cache.pop("active", None)
    else:
        _cache.clear()
