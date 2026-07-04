"""SQLite backend for conversation sessions (mirrors troubleshoot_sessions_db API)."""

import time
import logging
from datetime import datetime

from . import _base

logger = logging.getLogger("taktbots.sessions")


def save_session(session_data):
    """Save a new session. Overwrites any existing session for this phone."""
    _base.put("sessions", session_data["phone"], session_data)
    logger.info(f"Session saved for {session_data['phone']}, step={session_data.get('step')}")


def get_session(phone):
    """Get the session for a phone number. Returns dict or None."""
    return _base.get("sessions", phone)


def update_session(phone, session_data):
    """Update full session data."""
    _base.put("sessions", phone, session_data)
    logger.info(f"Session updated for {phone}, step={session_data.get('step')}")


def update_session_step(phone, new_step):
    """Quick update of just the step field."""
    session = _base.get("sessions", phone)
    if session is None:
        return
    session["step"] = new_step
    session["updated_at"] = datetime.utcnow().isoformat() + "Z"
    _base.put("sessions", phone, session)


def delete_session(phone):
    """Delete a session."""
    _base.delete("sessions", phone)
    logger.info(f"Session deleted for {phone}")


def list_sessions(limit=50):
    """List recent sessions, sorted by created_at descending."""
    sessions = _base.list_all("sessions")
    sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return sessions[:limit]


def extend_session_ttl(phone, days=7):
    """Extend the session TTL."""
    session = _base.get("sessions", phone)
    if session is None:
        return
    session["expires_at"] = int(time.time()) + days * 86400
    _base.put("sessions", phone, session)
