"""
state — shared engine state and helpers.

Holds the lazy-loaded DB modules (selected by STORAGE_BACKEND through the
database.maintenance dispatchers), the pluggable integration getters, engine
constants, and small session helpers used across the other submodules.
"""

import os
import logging
from datetime import datetime

from agents.bot_engine import integrations

logger = logging.getLogger("taktbots.M10010")

# Lazy-load DB modules
_session_db = None
_maint_db = None
_scripts_db = None

SESSION_TTL_SECONDS = 30 * 60  # 30 minutes
DEFAULT_SCRIPT_ID = "maintenance-troubleshoot"


def _get_session_db():
    global _session_db
    if _session_db is None:
        from database.maintenance import troubleshoot_sessions_db
        _session_db = troubleshoot_sessions_db
    return _session_db


def _get_maint_db():
    global _maint_db
    if _maint_db is None:
        from database.maintenance import maintenance_db
        _maint_db = maintenance_db
    return _maint_db


def _get_scripts_db():
    global _scripts_db
    if _scripts_db is None:
        from database.maintenance import bot_scripts_db
        _scripts_db = bot_scripts_db
    return _scripts_db


def _get_equipment_reader():
    """Pluggable equipment reader — None unless EQUIPMENT_READER_ENABLED is set."""
    return integrations.get_equipment_reader()


def _get_service_call_writer():
    """Pluggable service-call writer — None unless SERVICE_CALL_WRITER_ENABLED is set."""
    return integrations.get_service_call_writer()


def _append_log(session, event, **kwargs):
    """Append a diagnostic event to the session log."""
    if "session_log" not in session:
        session["session_log"] = []
    entry = {"ts": datetime.utcnow().isoformat() + "Z", "event": event}
    entry.update(kwargs)
    session["session_log"].append(entry)


def _is_demo_env():
    """Check if running against a demo external environment."""
    return "demo" in os.environ.get("PRIORITY_URL", "").lower()


def _get_technician():
    """Return default technician login."""
    return "יוסי"


def _lookup_customer(phone):
    """Look up customer by phone number in the service-calls history.

    Returns name and customer_number only — device_number is intentionally
    excluded because the customer may be calling about a different device.

    Returns:
        dict: {"name": "...", "customer_number": "..."} or empty dict
    """
    try:
        db = _get_maint_db()
        calls = db.get_service_calls(phone=phone, limit=5)
        if calls:
            latest = calls[0]
            return {
                "name": latest.get("cdes") or latest.get("name", ""),
                "customer_number": latest.get("custname", ""),
            }
    except Exception as e:
        logger.error(f"[M10010] Customer lookup failed for {phone}: {e}")
    return {}


def _enrich_from_device(session):
    """When device_number is set but customer info is missing, look it up via the equipment reader."""
    sernum = session.get("device_number", "")
    if not sernum or session.get("customer_number"):
        return
    try:
        eq = _get_equipment_reader()
        if eq is None:
            return
        device = eq.fetch_equipment_by_sernum(sernum)
        if device:
            session["customer_number"] = device["custname"]
            session["customer_name"] = device["cdes"]
            logger.info(f"[M10010] Enriched from device {sernum}: "
                        f"customer={device['custname']} ({device['cdes']})")
    except Exception as e:
        logger.error(f"[M10010] Device enrichment failed for {sernum}: {e}")
