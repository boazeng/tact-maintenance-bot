"""
engine — public entry points for the bot script engine.

  reset_session(phone)
  get_active_session(phone)
  start_session(phone, name, ...)
  process_message(phone, text, msg_type, caption)
"""

import uuid
import json
import time
from datetime import datetime

from .state import (
    logger, SESSION_TTL_SECONDS, DEFAULT_SCRIPT_ID,
    _get_session_db, _append_log, _enrich_from_device,
)
from .scripts import _load_script, _is_done_step
from .steps import _process_step_input, _resolve_skip_chain, _build_step_message
from .done_actions import _handle_done, _switch_to_script


def reset_session(phone):
    """Delete the active session for a phone number (force restart)."""
    db = _get_session_db()
    db.delete_session(phone)
    logger.info(f"[M10010] Session reset for {phone}")


def get_active_session(phone):
    """Check if phone has an active (non-expired) troubleshooting session.

    Returns:
        dict session data, or None.
    """
    db = _get_session_db()
    session = db.get_session(phone)
    if not session:
        return None

    # Session marked as done or cancelled — not active
    if session.get("status") in ("done", "cancelled"):
        return None

    step = session.get("step")
    # Check if step is a done step
    script = _load_script(session.get("script_id"))
    if script and _is_done_step(step, script):
        return None
    if step is None:
        return None

    if session.get("expires_at", 0) > time.time():
        return session
    return None


def start_session(phone, name, parsed_data=None, message_id="", media_id="",
                  original_text="", llm_result=None, script_id=None,
                  device_number="", customer_number="", customer_name=""):
    """Start a new troubleshooting session.

    Args:
        device_number: Device serial number from an external lookup (via M1000)
        customer_number: Customer code
        customer_name: Customer name

    Returns:
        dict: {"text": "...", "buttons": [...]} for the greeting question.
    """
    sid = script_id or DEFAULT_SCRIPT_ID
    script = _load_script(sid)
    if not script:
        logger.error(f"[M10010] Script {sid} not found")
        return {"text": "שגיאה: תסריט לא נמצא", "buttons": None}

    db = _get_session_db()
    now = datetime.utcnow().isoformat() + "Z"

    # Fallback chain: external lookup → parsed_data["שם הלקוח"] → WhatsApp profile name
    if not customer_name and parsed_data:
        raw_pd = parsed_data if isinstance(parsed_data, dict) else {}
        if isinstance(parsed_data, str):
            try:
                raw_pd = json.loads(parsed_data)
            except Exception:
                raw_pd = {}
        customer_name = raw_pd.get("שם הלקוח", "")
    customer_name = customer_name or name

    first_step = script.get("first_step", "GREETING")

    bot_instructions = script.get("bot_instructions", "")
    if bot_instructions:
        logger.info(f"[M10010] Bot instructions loaded for script '{sid}': {bot_instructions[:100]}...")

    session_data = {
        "phone": phone,
        "session_id": str(uuid.uuid4()),
        "script_id": sid,
        "name": name,
        "step": first_step,
        "created_at": now,
        "updated_at": now,
        "expires_at": int(time.time()) + SESSION_TTL_SECONDS,
        "customer_name": customer_name,
        "customer_number": customer_number,
        # Use device number from QR/parsed message, but not from phone lookup
        "device_number": (parsed_data or {}).get("מספר מכשיר", "").strip(),
        "original_text": original_text,
        "original_message_id": message_id,
        "original_media_id": media_id,
        "parsed_data": parsed_data or {},
        "llm_result": llm_result or {},
        "bot_instructions": bot_instructions,
    }

    # Pre-initialize all save_to fields defined in the script (text steps and buttons)
    for step in script.get("steps", []):
        if step.get("save_to") and step["save_to"] not in session_data:
            session_data[step["save_to"]] = ""
        for btn in step.get("buttons", []):
            if btn.get("save_to") and btn["save_to"] not in session_data:
                session_data[btn["save_to"]] = ""

    # Log session start
    _append_log(session_data, "session_start",
                script_id=sid, first_step=first_step,
                customer_name=customer_name, device_number=device_number)

    # Resolve step-level skip_if on first step
    first_step = _resolve_skip_chain(first_step, script, session_data)
    session_data["step"] = first_step

    db.save_session(session_data)
    logger.info(f"[M10010] Session started for {phone}, script={sid}, "
                f"customer={customer_name}, device={device_number}")

    # Check if skip chain landed on a done step
    if _is_done_step(first_step, script):
        return _handle_done(first_step, script, session_data)

    return _build_step_message(first_step, script, session_data)


def process_message(phone, text, msg_type="text", caption=""):
    """Process an incoming message for an active troubleshooting session.

    Returns:
        dict: {"text": "...", "buttons": [...]} or {"text": "..."} or None
    """
    db = _get_session_db()
    session = db.get_session(phone)

    if not session:
        return None

    script = _load_script(session.get("script_id"))
    if not script:
        return {"text": "שגיאה: תסריט לא נמצא", "buttons": None}

    current_step = session.get("step", "")
    logger.info(f"[M10010] Processing {phone} step={current_step} input={text[:50]}")

    # User pressed -1 → end conversation immediately
    if text.strip() == "-1":
        logger.info(f"[M10010] User {phone} pressed -1 → ending session")
        session["status"] = "cancelled"
        _append_log(session, "session_cancelled", step=current_step)
        db.update_session_step(phone, "CANCELLED")
        session["expires_at"] = int(time.time()) + 7 * 86400
        db.save_session(session)
        return {"text": "השיחה הסתיימה. תודה!"}

    next_step = _process_step_input(current_step, script, session, text, msg_type)

    # If device_number was just entered, enrich customer info
    if session.get("device_number") and not session.get("customer_number"):
        _enrich_from_device(session)

    if next_step is None:
        # Invalid input - re-send current step prompt with a nudge
        msg = _build_step_message(current_step, script, session)
        if msg.get("buttons"):
            msg["text"] = "אנא בחר אחת מהאפשרויות:\n\n" + msg["text"]
        return msg

    if _is_done_step(next_step, script):
        done_cfg = script.get("done_actions", {}).get(next_step, {})
        if done_cfg.get("action") == "switch_script":
            logger.info(f"[M10010] switch_script: {phone} → {done_cfg.get('target_script_id')}")
            return _switch_to_script(phone, done_cfg.get("target_script_id", ""), session, db)
        result = _handle_done(next_step, script, session)
        db.update_session_step(phone, next_step)
        logger.info(f"[M10010] Done: {phone} → {next_step}")
        return result

    # Resolve step-level skip_if chain
    next_step = _resolve_skip_chain(next_step, script, session)

    # Check if skip chain landed on a done step
    if _is_done_step(next_step, script):
        done_cfg = script.get("done_actions", {}).get(next_step, {})
        if done_cfg.get("action") == "switch_script":
            logger.info(f"[M10010] switch_script (after skip): {phone} → {done_cfg.get('target_script_id')}")
            return _switch_to_script(phone, done_cfg.get("target_script_id", ""), session, db)
        result = _handle_done(next_step, script, session)
        db.update_session_step(phone, next_step)
        logger.info(f"[M10010] Done (after skip): {phone} → {next_step}")
        return result

    # Advance to next step
    session["step"] = next_step
    session["updated_at"] = datetime.utcnow().isoformat() + "Z"
    session["expires_at"] = int(time.time()) + SESSION_TTL_SECONDS
    db.update_session(phone, session)

    return _build_step_message(next_step, script, session)
