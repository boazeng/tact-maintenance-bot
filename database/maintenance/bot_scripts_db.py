"""
bot_scripts_db — storage dispatcher for bot conversation scripts.

Selects the backend via STORAGE_BACKEND env var (sqlite | dynamodb, default sqlite).
Public API: get_script, save_script, list_scripts, delete_script, invalidate_cache.
"""

import os

_BACKEND = os.environ.get("STORAGE_BACKEND", "sqlite").lower()

if _BACKEND == "dynamodb":
    from database.backends.dynamodb import scripts as _impl
else:
    from database.backends.sqlite import scripts as _impl

get_script = _impl.get_script
save_script = _impl.save_script
list_scripts = _impl.list_scripts
delete_script = _impl.delete_script
invalidate_cache = _impl.invalidate_cache
