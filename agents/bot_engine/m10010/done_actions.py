"""
done_actions — terminal flow actions: save a customer message, open/escalate a
service call, update an existing call, switch to another script, or just notify.
"""

import json
import time
from datetime import datetime

from .state import (
    logger, SESSION_TTL_SECONDS,
    _get_session_db, _get_maint_db, _get_technician, _append_log,
    _get_service_call_writer,
)
from .scripts import _load_script, _is_done_step
from .steps import _resolve_skip_chain, _build_step_message


def _switch_to_script(phone, target_script_id, session, db):
    """Switch the active session to a different script (without losing session data).

    Used by the switch_script done_action to transition from a routing script
    to a fault-reporting script in one seamless session.

    Returns:
        dict: first step message of the new script
    """
    new_script = _load_script(target_script_id)
    if not new_script:
        logger.error(f"[M10010] switch_script: target '{target_script_id}' not found")
        return {"text": f"שגיאה: תסריט {target_script_id} לא נמצא", "buttons": None}

    from_script = session.get("script_id", "")
    first_step = new_script.get("first_step", "")
    _append_log(session, "switch_script", from_script=from_script, to_script=target_script_id)

    first_step = _resolve_skip_chain(first_step, new_script, session)

    session["script_id"] = target_script_id
    session["step"] = first_step
    session["expires_at"] = int(time.time()) + SESSION_TTL_SECONDS
    # Update bot_instructions from the new script
    session["bot_instructions"] = new_script.get("bot_instructions", "")
    db.update_session(phone, session)

    logger.info(f"[M10010] Switched script: {target_script_id}, first_step={first_step}")

    if _is_done_step(first_step, new_script):
        return _handle_done(first_step, new_script, session)

    return _build_step_message(first_step, new_script, session)


def _handle_done(done_id, script, session):
    """Execute the done action and return the completion message.

    Returns:
        dict: {"text": "..."} completion message
    """
    done_actions = script.get("done_actions", {})
    done_config = done_actions.get(done_id, {})

    action = done_config.get("action", "")
    call_id = ""
    if action == "save_message":
        _save_customer_message(session, script)
    elif action == "save_service_call":
        call_id = _save_completed_service_call(session, script) or ""
    elif action == "escalate":
        call_id = _save_completed_service_call(session, script) or ""
        logger.info(f"[M10010] Escalation done: {done_id}")
    elif action == "end_conversation":
        logger.info(f"[M10010] End-conversation done: {done_id}, no record saved")
    elif action == "update_existing_service_call":
        call_id = _update_existing_service_call(session, script) or ""
    elif action == "notify_only":
        logger.info(f"[M10010] Notify-only done: {done_id}, no record saved")
    elif action:
        # Unknown/custom action — log it, save as generic message
        logger.info(f"[M10010] Custom action '{action}' for done={done_id}, saving as message")
        _save_customer_message(session, script)

    # Log done event + extend TTL to 7 days so diagnostics can review completed sessions
    _append_log(session, "session_done", done_id=done_id, action=action)
    session["status"] = "done"
    session["expires_at"] = int(time.time()) + 7 * 86400
    try:
        db = _get_session_db()
        db.update_session(session.get("phone", ""), session)
    except Exception as e:
        logger.error(f"[M10010] Failed to persist done log for {session.get('phone')}: {e}")

    result = {"text": done_config.get("text", "תודה!")}

    # Send admin WhatsApp notification if configured on this done action
    notify_phone = done_config.get("notify_phone", "")
    if notify_phone and call_id:
        import collections as _col
        notify_tmpl = done_config.get("notify_text",
            "נפתחה קריאת שירות חדשה מהבוט הקולי 📞\nמספר קריאה: {call_id}\nטלפון: {phone}")
        try:
            # Flatten parsed_data fields so Hebrew keys from voice-bot are available in template
            flat_ctx = {}
            raw_pd = session.get("parsed_data", {})
            if isinstance(raw_pd, str):
                try:
                    raw_pd = json.loads(raw_pd)
                except Exception:
                    raw_pd = {}
            if isinstance(raw_pd, dict):
                flat_ctx.update(raw_pd)
            flat_ctx.update(session)
            notify_msg = notify_tmpl.format_map(
                _col.defaultdict(str, call_id=call_id, **flat_ctx)
            )
            result["notify_whatsapp"] = {"phone": notify_phone, "text": notify_msg}
            logger.info(f"[M10010] Admin notification queued → {notify_phone}")
        except Exception as e:
            logger.error(f"[M10010] Failed to build admin notification: {e}")

    return result


def _save_customer_message(session, script=None):
    """Save a non-fault customer message as a service-call record."""
    maint_db = _get_maint_db()
    phone = session.get("phone", "")
    name = session.get("customer_name", "") or session.get("name", "")

    # Find message field: prefer "customer_message", fallback to first text save_to in script
    message = session.get("customer_message", "")
    if not message and script:
        for step in script.get("steps", []):
            save_to = step.get("save_to", "")
            if save_to and session.get(save_to):
                message = session[save_to]
                break

    call_data = dict(
        phone=phone,
        name=name,
        issue_type="הודעה",
        description=message,
        urgency="low",
        location="",
        summary=message,
        message_id=session.get("original_message_id", ""),
        custname=session.get("customer_number", "") or "99999",
        cdes=name,
        technicianlogin=_get_technician(),
        callstatuscode="הודעות מלקוח",
    )
    result = maint_db.save_service_call(**call_data)
    call_id = result.get("id", "")

    # Auto-push to an external system (optional, disabled by default)
    writer = _get_service_call_writer()
    if writer is not None:
        try:
            call_data["fault_text"] = f"הודעה מלקוח:\n{message}\nטלפון: {phone}\nשם: {name}"
            priority_result = writer.create_service_call(call_data)
            priority_callno = str(priority_result.get("DOCNO", ""))
            maint_db.mark_service_call_pushed(call_id, callno=priority_callno)
            logger.info(f"[M10010] Message auto-pushed to external: DOCNO={priority_callno}")
        except Exception as e:
            logger.error(f"[M10010] Message auto-push to external failed: {e}")


def _save_completed_service_call(session, script=None):
    """Save completed fault report as a service-call record.

    Dynamically collects all save_to fields from the script steps.
    Known fields (description, location, device_number, is_system_down) are mapped
    to specific service call attributes; all other fields are appended as extra text.

    Returns:
        str: service call ID (external DOCNO when available, else internal id)
    """
    maint_db = _get_maint_db()

    phone = session.get("phone", "")
    name = session.get("customer_name", "") or session.get("name", "")

    # Collect all save_to fields from the script
    SYSTEM_FIELDS = {
        "phone", "session_id", "script_id", "name", "step",
        "created_at", "updated_at", "expires_at",
        "customer_name", "customer_number", "device_number",
        "original_text", "original_message_id", "original_media_id",
        "parsed_data", "llm_result",
    }
    script_fields = []  # ordered list of (field, value) as defined in script steps
    seen = set()
    if script:
        for step in script.get("steps", []):
            save_to = step.get("save_to", "")
            if save_to and save_to not in SYSTEM_FIELDS and save_to not in seen:
                seen.add(save_to)
                if session.get(save_to):
                    script_fields.append((save_to, session[save_to]))
            for btn in step.get("buttons", []):
                bsave = btn.get("save_to", "")
                if bsave and bsave not in SYSTEM_FIELDS and bsave not in seen:
                    seen.add(bsave)
                    if session.get(bsave):
                        script_fields.append((bsave, session[bsave]))

    # Known field aliases that map to specific service call attributes
    description = session.get("description", "")
    # Fallback: use first collected script field as description if none named "description"
    if not description and script_fields:
        description = script_fields[0][1]
    # Final fallback: use original_text (e.g. voice-bot messages that skip straight to DONE)
    if not description:
        description = session.get("original_text", "")
    location = session.get("location", "")
    is_system_down = session.get("is_system_down", "") == "yes"
    # Fallback for voice-bot: check parsed_data["מערכת מושבתת"]
    if not is_system_down:
        raw_pd = session.get("parsed_data", {})
        if isinstance(raw_pd, str):
            try:
                raw_pd = json.loads(raw_pd)
            except Exception:
                raw_pd = {}
        pd_val = str(raw_pd.get("מערכת מושבתת", "")).strip() if isinstance(raw_pd, dict) else ""
        if pd_val and pd_val not in ("לא", "לא פעיל", "לא מושבת", "no", "false"):
            is_system_down = True

    # Build fault text
    fault_lines = []
    if description:
        fault_lines.append(description)
    fault_lines.append(f"טלפון: {phone}")
    if location:
        fault_lines.append(f"מיקום: {location}")
    if session.get("device_number"):
        fault_lines.append(f"מכשיר: {session['device_number']}")
    if is_system_down:
        fault_lines.append("מערכת מושבתת: כן")

    # Append any extra script fields not already included
    KNOWN_MAPPED = {"description", "location", "is_system_down"}
    for field, value in script_fields:
        if field not in KNOWN_MAPPED:
            fault_lines.append(f"{field}: {value}")

    fault_text = "\n".join(fault_lines)

    call_data = dict(
        phone=phone,
        name=name,
        issue_type="תקלה",
        description=description,
        urgency="high" if is_system_down else "medium",
        location=session.get("location", ""),
        summary=description,
        message_id=session.get("original_message_id", ""),
        media_id=session.get("original_media_id", ""),
        custname=session.get("customer_number", "") or "99999",
        cdes=name,
        sernum=session.get("device_number", ""),
        branchname="001",
        technicianlogin=_get_technician(),
        fault_text=fault_text,
        is_system_down=is_system_down,
    )

    result = maint_db.save_service_call(**call_data)
    call_id = result.get("id", "")
    priority_callno = ""

    # Auto-push to an external system (optional, disabled by default)
    writer = _get_service_call_writer()
    if writer is not None:
        try:
            priority_result = writer.create_service_call(call_data)
            priority_callno = str(priority_result.get("DOCNO", ""))
            maint_db.mark_service_call_pushed(call_id, callno=priority_callno)
            logger.info(f"[M10010] Auto-pushed to external: DOCNO={priority_callno}")
        except Exception as e:
            logger.error(f"[M10010] Auto-push to external failed: {e}")

    # Return external DOCNO when available, else internal DB id
    return priority_callno or call_id


def _update_existing_service_call(session, script=None):
    """Append fault description and customer info to an existing open service call.

    Called when check_open_service_call found an existing call (DOCNO stored
    in session['open_call_docno']). Attaches a text note via the writer and
    also saves the update locally.

    Returns:
        str: the existing DOCNO
    """
    docno = session.get("open_call_docno", "")
    if not docno:
        logger.warning("[M10010] update_existing_service_call: no open_call_docno in session")
        return ""

    phone = session.get("phone", "")
    name = session.get("customer_name", "") or session.get("name", "")
    description = session.get("description", "")

    # Build the note text
    lines = []
    if description:
        lines.append(f"תיאור תקלה: {description}")
    lines.append(f"טלפון: {phone}")
    if name:
        lines.append(f"לקוח: {name}")
    if session.get("device_number"):
        lines.append(f"מכשיר: {session['device_number']}")
    if session.get("is_system_down") == "yes":
        lines.append("מערכת מושבתת: כן")
    lines.append(f"תאריך עדכון: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    note_text = "\n".join(lines)

    # Attach note to existing external service call (optional, disabled by default)
    writer = _get_service_call_writer()
    if writer is not None:
        try:
            writer.append_note_to_service_call(docno, note_text)
            logger.info(f"[M10010] Note appended to existing call {docno}")
        except Exception as e:
            logger.error(f"[M10010] Failed to append note to {docno}: {e}")

    # Also save locally as an update record
    try:
        maint_db = _get_maint_db()
        maint_db.save_service_call(
            phone=phone,
            name=name,
            issue_type="עדכון לקריאה קיימת",
            description=f"עדכון לקריאה {docno}: {description}",
            urgency="medium",
            summary=f"עדכון לקריאה {docno}",
            custname=session.get("customer_number", "") or "99999",
            cdes=name,
            sernum=session.get("device_number", ""),
            branchname="001",
            technicianlogin=_get_technician(),
            fault_text=note_text,
        )
    except Exception as e:
        logger.error(f"[M10010] Failed to save update locally: {e}")

    return docno
