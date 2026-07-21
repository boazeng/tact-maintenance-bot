"""
steps — step rendering, user-input processing, and automatic flow resolution
(skip_if conditions, action steps, and LLM-routed instruction exits).
"""

from .state import (
    logger, _append_log, _get_session_db,
    _get_equipment_reader, _get_service_call_writer,
)
from .scripts import _find_step, _is_done_step
from .llm_router import resolve_exit


# ── Generic Step Message Builder ──────────────────────────────

def _build_step_message(step_id, script, session_data):
    """Build the message and optional buttons for a step, reading from script config.

    Returns:
        dict: {"text": "...", "buttons": [...] or None}
    """
    step = _find_step(script, step_id)
    if not step:
        return {"text": "שגיאה פנימית", "buttons": None}

    text = step.get("text", "")

    # Interpolate session variables in step text (e.g. {device_number}, {customer_name})
    try:
        import collections as _col
        text = text.format_map(_col.defaultdict(str, session_data))
    except (ValueError, KeyError):
        pass

    # For the first displayed step, prepend greeting
    if not session_data.get("_greeted"):
        customer_name = session_data.get("customer_name", "")
        if customer_name:
            greeting = script.get("greeting_known", "שלום {customer_name}!").format(
                customer_name=customer_name
            )
        else:
            greeting = script.get("greeting_unknown", "שלום!")
        text = f"{greeting}\n{text}"
        session_data["_greeted"] = True
        # Persist the flag immediately — callers save the session *before* building
        # the message, so without this the greeting would repeat on every turn.
        try:
            phone = session_data.get("phone", "")
            if phone:
                _get_session_db().update_session(phone, session_data)
        except Exception as e:
            logger.error(f"[M10010] Failed to persist greeting flag: {e}")

    step_type = step.get("type", "text_input")

    if step_type == "buttons":
        buttons = [
            {"id": btn["id"], "title": btn["title"]}
            for btn in step.get("buttons", [])
        ]
        _append_log(session_data, "step_shown", step=step_id, step_type="buttons", text=text[:120])
        return {"text": text, "buttons": buttons if buttons else None}

    if step_type == "action":
        # Action steps are auto-executed and should not be sent to the user
        logger.warning(f"[M10010] _build_step_message called on action step {step_id} — "
                       "should have been resolved by _resolve_skip_chain")
        return {"text": "מתבצעת בדיקה...", "buttons": None}

    # text_input type
    _append_log(session_data, "step_shown", step=step_id, step_type="text_input", text=text[:120])
    return {"text": text, "buttons": None}


# ── Generic Step Input Processing ─────────────────────────────

def _process_step_input(step_id, script, session_data, text, msg_type):
    """Process user input for a step, reading logic from script config.

    Returns:
        str: next step ID to advance to, or None if input is invalid.
    Updates session_data dict in-place with collected info.
    """
    step = _find_step(script, step_id)
    if not step:
        return None

    step_type = step.get("type", "text_input")

    if step_type == "buttons":
        # Match text against button IDs
        for btn in step.get("buttons", []):
            if text == btn["id"]:
                # Save value if button has save_to/save_value
                if btn.get("save_to"):
                    session_data[btn["save_to"]] = btn.get("save_value", btn["id"])
                next_step = btn.get("next_step", "")
                # Check skip_if condition
                skip_if = btn.get("skip_if")
                if skip_if and _check_skip_condition(skip_if, session_data):
                    target = skip_if.get("goto", next_step)
                    _append_log(session_data, "button_matched",
                                step=step_id, button_id=btn["id"],
                                button_title=btn.get("title", ""), next_step=target)
                    return target
                _append_log(session_data, "button_matched",
                            step=step_id, button_id=btn["id"],
                            button_title=btn.get("title", ""), next_step=next_step)
                return next_step
        return None  # No button matched

    if step_type == "text_input":
        # Accept free-text input
        if msg_type in ("text", "interactive") and text and not text.startswith("["):
            save_to = step.get("save_to")
            if save_to:
                session_data[save_to] = text
            _append_log(session_data, "user_input",
                        step=step_id, input=text[:80], msg_type=msg_type,
                        save_to=save_to or "")
            return step.get("next_step", "")
        return None

    if step_type == "action":
        # Action steps are auto-executed, not driven by user input
        return _execute_action_step(step, session_data)

    return None


def _check_skip_condition(skip_if, session_data):
    """Evaluate a skip_if condition against session data.

    Supports:
        {"field": "device_number", "not_empty": true}
        {"field": "device_number", "empty": true}
        {"field": "is_system_down", "equals": "yes"}
    """
    field = skip_if.get("field", "")
    value = session_data.get(field, "")
    if skip_if.get("not_empty"):
        return bool(value)
    if skip_if.get("empty"):
        return not bool(value)
    if "equals" in skip_if:
        return str(value) == str(skip_if["equals"])
    return False


def _apply_device(session_data, device):
    """Fill customer + site into the session from a matched device."""
    session_data["customer_number"] = device.get("custname", "")
    session_data["customer_name"] = device.get("cdes", "")
    # Kept for staff notifications ("device: 000003 - underground car park").
    session_data["device_description"] = device.get("partdes", "") or device.get("partname", "")
    site = device.get("site_description", "") or device.get("facilitydes", "")
    if site:
        session_data["site"] = site
        if not session_data.get("location"):
            session_data["location"] = site


def _execute_action_step(step, session_data):
    """Execute an action step and return the next step ID based on result.

    Currently supported action_types:
        check_equipment — looks up device by field value via the equipment reader.
            on_success: step to go to if device found (also enriches customer info)
            on_failure: step to go to if device not found or field is empty
        check_open_service_call — checks for an existing open call via the writer.
    """
    action_type = step.get("action_type", "")

    if action_type == "check_equipment":
        field = step.get("field", "device_number")
        value = session_data.get(field, "")
        if not value:
            logger.info(f"[M10010] Action check_equipment: field '{field}' is empty → failure")
            return step.get("on_failure", "")
        try:
            eq = _get_equipment_reader()
            if eq is None:
                logger.info("[M10010] Action check_equipment: equipment reader disabled → failure")
                return step.get("on_failure", "")
            # 1. try the value as a device serial number
            device = eq.fetch_equipment_by_sernum(value)
            if device:
                _apply_device(session_data, device)
                logger.info(f"[M10010] check_equipment: {value} matched a device "
                            f"→ customer={device.get('custname')} ({device.get('cdes')})")
                return step.get("on_success", "")
            # 2. try the value as a CUSTOMER number — single-device rule
            if hasattr(eq, "fetch_equipment_by_customer"):
                devs = eq.fetch_equipment_by_customer(value) or []
                if len(devs) == 1:
                    d = devs[0]
                    session_data["device_number"] = d.get("sernum", "")
                    _apply_device(session_data, d)
                    logger.info(f"[M10010] check_equipment: {value} is a customer with ONE device "
                                f"→ device={d.get('sernum')} ({d.get('cdes')})")
                    return step.get("on_success", "")
                if len(devs) > 1:
                    # Customer known but which device is ambiguous — keep customer, ask for device.
                    session_data["customer_number"] = devs[0].get("custname", "")
                    session_data["customer_name"] = devs[0].get("cdes", "")
                    logger.info(f"[M10010] check_equipment: {value} is a customer with "
                                f"{len(devs)} devices → ambiguous, need device number")
            logger.info(f"[M10010] check_equipment: {value} not found → failure")
            return step.get("on_failure", "")
        except Exception as e:
            logger.error(f"[M10010] Action check_equipment failed for {value}: {e}")
            return step.get("on_failure", "")

    if action_type == "check_open_service_call":
        field = step.get("field", "device_number")
        value = session_data.get(field, "")
        if not value:
            logger.info(f"[M10010] Action check_open_service_call: no device number → no open call")
            return step.get("on_failure", "")
        try:
            writer = _get_service_call_writer()
            if writer is None:
                logger.info("[M10010] Action check_open_service_call: writer disabled → failure")
                return step.get("on_failure", "")
            open_calls = writer.find_open_service_calls(value)
            if open_calls:
                call = open_calls[0]
                session_data["open_call_docno"] = call.get("DOCNO", "")
                session_data["open_call_status"] = call.get("CALLSTATUSCODE", "")
                logger.info(f"[M10010] Action check_open_service_call: {value} has open call "
                            f"DOCNO={call.get('DOCNO')}")
                return step.get("on_success", "")
            else:
                logger.info(f"[M10010] Action check_open_service_call: {value} no open calls")
                return step.get("on_failure", "")
        except Exception as e:
            logger.error(f"[M10010] Action check_open_service_call failed for {value}: {e}")
            return step.get("on_failure", "")

    logger.warning(f"[M10010] Unknown action_type: {action_type}")
    return None


def _llm_route_exits(step, session_data):
    """Choose an exit for an instructions node — delegates to the pluggable router.

    Production runs it in "live" mode (LLM); the bot-test harness can switch it to
    "manual" mode with a forced-exit map. See m10010/llm_router.py.
    """
    return resolve_exit(step, session_data)


def _resolve_skip_chain(step_id, script, session_data, max_depth=10):
    """Resolve automatic steps (skip_if and action) without waiting for user input.

    When the engine reaches a step that has a skip_if condition and the condition is true,
    or a step of type 'action', it executes/jumps automatically.
    This chains until a step that requires user input (text_input or buttons).

    Args:
        step_id: Starting step ID
        script: Full script dict
        session_data: Current session data (fields to check against)
        max_depth: Safety limit to prevent infinite loops

    Returns:
        str: Final step ID after resolving all auto steps
    """
    current = step_id
    for _ in range(max_depth):
        if _is_done_step(current, script):
            break
        step = _find_step(script, current)
        if not step:
            break

        # Auto-execute instructions steps (LLM-route if exits, else simple advance)
        if step.get("type") == "instructions":
            instr_text = step.get("text", "")
            session_data["bot_instructions_step"] = instr_text
            exits = step.get("exits", [])
            if exits:
                # LLM decides which exit to take
                target = _llm_route_exits(step, session_data)
                if target and target != current:
                    # Find chosen exit title for log
                    chosen_title = next(
                        (e.get("title", "") for e in exits if e.get("next_step") == target), ""
                    )
                    _append_log(session_data, "llm_route",
                                step=current, chosen_exit_title=chosen_title, target=target)
                    current = target
                    continue
            else:
                logger.info(f"[M10010] Instructions step {current}: {instr_text[:100]}")
                target = step.get("next_step", "")
                if target and target != current:
                    _append_log(session_data, "instructions_auto", step=current, target=target)
                    current = target
                    continue
            break

        # Auto-execute action steps (no user input needed)
        if step.get("type") == "action":
            action_type = step.get("action_type", "")
            field = step.get("field", "")
            value = session_data.get(field, "")
            target = _execute_action_step(step, session_data)
            if target and target != current:
                result = "success" if target == step.get("on_success") else "failure"
                # Store action result explicitly so subsequent INSTR/LLM steps can read it
                if action_type == "check_equipment":
                    session_data["equipment_check_result"] = "found" if result == "success" else "not_found"
                if action_type == "check_open_service_call":
                    session_data["open_service_call_result"] = "exists" if result == "success" else "none"
                logger.info(f"[M10010] Action step: {current} → {target} "
                            f"(action_type={action_type})")
                _append_log(session_data, "action_executed",
                            step=current, action_type=action_type,
                            field=field, value=str(value)[:40],
                            result=result, target=target)
                current = target
                continue
            break

        # Resolve step-level skip_if conditions
        skip_if = step.get("skip_if")
        if skip_if and _check_skip_condition(skip_if, session_data):
            target = skip_if.get("goto", "")
            if target and target != current:
                logger.info(f"[M10010] Step skip: {current} → {target} "
                            f"(field={skip_if.get('field')} matched)")
                _append_log(session_data, "skip_if_triggered",
                            step=current, field=skip_if.get("field", ""), target=target)
                current = target
                continue
        break
    return current
