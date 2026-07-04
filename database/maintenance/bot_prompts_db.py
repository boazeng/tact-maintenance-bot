"""
bot_prompts_db — storage dispatcher for LLM system prompts.

Selects the backend via STORAGE_BACKEND env var (sqlite | dynamodb, default sqlite).
Public API: get_active_prompt, get_prompt, save_prompt, list_prompts, invalidate_cache.
"""

import os

_BACKEND = os.environ.get("STORAGE_BACKEND", "sqlite").lower()

if _BACKEND == "dynamodb":
    from database.backends.dynamodb import prompts as _impl
else:
    from database.backends.sqlite import prompts as _impl

get_active_prompt = _impl.get_active_prompt
get_prompt = _impl.get_prompt
save_prompt = _impl.save_prompt
list_prompts = _impl.list_prompts
invalidate_cache = _impl.invalidate_cache
