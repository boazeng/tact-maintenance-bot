"""
troubleshoot_sessions_db — storage dispatcher for conversation sessions.

Selects the backend via STORAGE_BACKEND env var (sqlite | dynamodb, default sqlite).
Public API: save_session, get_session, update_session, update_session_step,
            delete_session, list_sessions, extend_session_ttl.
"""

import os

_BACKEND = os.environ.get("STORAGE_BACKEND", "sqlite").lower()

if _BACKEND == "dynamodb":
    from database.backends.dynamodb import sessions as _impl
else:
    from database.backends.sqlite import sessions as _impl

save_session = _impl.save_session
get_session = _impl.get_session
update_session = _impl.update_session
update_session_step = _impl.update_session_step
delete_session = _impl.delete_session
list_sessions = _impl.list_sessions
extend_session_ttl = _impl.extend_session_ttl
