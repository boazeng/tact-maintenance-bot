"""scripts — load bot scripts and locate steps within them."""

from .state import logger, DEFAULT_SCRIPT_ID, _get_scripts_db


def _load_script(script_id=None):
    """Load a bot script from storage (cached).

    Tries to find the script by ID first. If not found, falls back to
    scanning all scripts for a matching name (case-insensitive).

    Returns:
        dict: script data, or None if not found
    """
    sid = script_id or DEFAULT_SCRIPT_ID
    try:
        db = _get_scripts_db()
        script = db.get_script(sid)
        if script:
            return script
        # Fallback: search by name (useful when ROUTING_SCRIPT_ID is set to a display name)
        logger.info(f"[M10010] Script '{sid}' not found by ID, searching by name...")
        all_scripts = db.list_scripts()
        sid_lower = sid.strip().lower()
        for s in all_scripts:
            if (s.get("name") or "").strip().lower() == sid_lower:
                logger.info(f"[M10010] Found script by name '{sid}' → id={s['script_id']}")
                return s
    except Exception as e:
        logger.error(f"[M10010] Failed to load script {sid}: {e}")
    return None


def _find_step(script, step_id):
    """Find a step definition in the script by ID.

    Returns:
        dict: step config, or None
    """
    for step in script.get("steps", []):
        if step.get("id") == step_id:
            return step
    return None


def _is_done_step(step_id, script):
    """Check if a step ID is a terminal (done) step."""
    done_actions = script.get("done_actions", {})
    return step_id in done_actions
