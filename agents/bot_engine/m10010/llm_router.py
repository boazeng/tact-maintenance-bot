"""
llm_router — pluggable resolver for instructions-node exits.

An "instructions" step with an ``exits`` list is a branch the engine must pick
automatically. In production this is decided by an LLM (OpenAI). The bot-test
harness needs two extra behaviours, so the decision is funnelled through
``resolve_exit`` here:

  - mode "live"   : ask the LLM (production default — unchanged behaviour).
  - mode "manual" : take the exit named in ``forced_exits[step_id]``; if none is
                    configured, fall back to exit 0. Every decision is recorded
                    on the session (``_llm_routes``) so the tester can see which
                    branch was taken and override it deterministically.

Configure per request from the test API; production never calls ``configure``
so it stays in "live" mode.
"""

import os
import json
import logging

import requests as _requests

logger = logging.getLogger("taktbots.llm_router")

# Per-process routing context. Production leaves this at the default.
#   on_missing: what manual mode does when a step has no forced exit —
#     "default" → take exit 0 (headless replay), "raise" → pause for a choice.
_ctx = {"mode": "live", "forced": {}, "on_missing": "default"}


class RouteChoiceNeeded(Exception):
    """Raised in manual mode when an instructions step needs the tester to pick
    an exit (no forced choice configured). Carries the step id and its exits."""
    def __init__(self, step_id, exits):
        self.step_id = step_id
        self.exits = [{"index": i, "title": e.get("title", f"יציאה {i}")}
                      for i, e in enumerate(exits)]
        super().__init__(f"route choice needed for {step_id}")


def configure(mode="live", forced=None, on_missing="default"):
    """Set the routing mode ('live' | 'manual'), forced-exit map, and the
    manual missing-choice behaviour ('default' | 'raise')."""
    _ctx["mode"] = mode if mode in ("live", "manual") else "live"
    _ctx["forced"] = dict(forced or {})
    _ctx["on_missing"] = on_missing if on_missing in ("default", "raise") else "default"


def reset():
    """Restore production defaults (live LLM, no forced exits)."""
    _ctx["mode"] = "live"
    _ctx["forced"] = {}
    _ctx["on_missing"] = "default"


def _record(session_data, step_id, index, exit_cfg, source):
    """Log the chosen exit on the session so the inspector can show it."""
    routes = session_data.setdefault("_llm_routes", [])
    routes.append({
        "step": step_id,
        "index": index,
        "title": exit_cfg.get("title", ""),
        "next_step": exit_cfg.get("next_step", ""),
        "source": source,  # "forced" | "default" | "llm"
    })


def _haystack(session_data):
    """The text a deterministic rule searches: the raw message + parsed fields."""
    parts = [str(session_data.get("original_text", ""))]
    pd = session_data.get("parsed_data", {})
    if isinstance(pd, dict):
        parts += [f"{k}:{v}" for k, v in pd.items()]
    return "\n".join(parts)


def _rule_ok(m, hay):
    contains = m.get("contains", [])
    not_contains = m.get("not_contains", [])
    if not contains and not not_contains:
        return False
    if contains and not any(c in hay for c in contains):
        return False
    if not_contains and any(c in hay for c in not_contains):
        return False
    return True


def _match_exit(exits, session_data):
    """Deterministic routing: pick the first exit whose `match` rule fits the
    message. Returns (index, exit) or None (no rules / nothing matched → let LLM decide).

    An exit's `match` is {contains:[...], not_contains:[...]} or {default:true}
    (used only when no positive rule matched)."""
    if not any(isinstance(e.get("match"), dict) for e in exits):
        return None  # node has no rules → LLM / manual decides
    hay = _haystack(session_data)
    for i, e in enumerate(exits):
        m = e.get("match")
        if isinstance(m, dict) and not m.get("default") and _rule_ok(m, hay):
            return i, e
    for i, e in enumerate(exits):        # nothing matched → the default exit
        m = e.get("match")
        if isinstance(m, dict) and m.get("default"):
            return i, e
    return None


def resolve_exit(step, session_data):
    """Decide which exit to take from an instructions node. Returns next_step."""
    exits = step.get("exits", [])
    if not exits:
        return ""
    step_id = step.get("id", "")

    # 1. An explicit manual choice wins — lets the tester force any branch.
    if _ctx["mode"] == "manual" and step_id in _ctx["forced"]:
        idx = _clamp(int(_ctx["forced"][step_id]), len(exits))
        chosen = exits[idx]
        _record(session_data, step_id, idx, chosen, "forced")
        logger.info("[llm_router] manual forced exit %d for %s", idx, step_id)
        return chosen.get("next_step", "")

    # 2. Deterministic rules — certain, instant, no LLM and no manual pause.
    ruled = _match_exit(exits, session_data)
    if ruled is not None:
        idx, chosen = ruled
        _record(session_data, step_id, idx, chosen, "rule")
        logger.info("[llm_router] RULE matched exit %d ('%s') for %s",
                    idx, chosen.get("title"), step_id)
        return chosen.get("next_step", "")

    if _ctx["mode"] == "manual":
        # No forced choice and no rule: pause for the tester, or (headless) default.
        if _ctx["on_missing"] == "raise":
            raise RouteChoiceNeeded(step_id, exits)
        chosen = exits[0]
        _record(session_data, step_id, 0, chosen, "default")
        logger.info("[llm_router] manual default exit 0 for %s -> %s",
                    step_id, chosen.get("next_step"))
        return chosen.get("next_step", "")

    # ── live mode: ask the LLM ──
    return _llm_choose(step, session_data, exits, step_id)


def _clamp(idx, n):
    return max(0, min(idx, n - 1))


def _llm_choose(step, session_data, exits, step_id):
    """Ask OpenAI to choose an exit (1-based to match how scripts are written)."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    exit_lines = "\n".join([
        f"- יציאה {i + 1}: \"{e.get('title', f'יציאה {i + 1}')}\""
        for i, e in enumerate(exits)
    ])

    skip_keys = {"expires_at", "session_id", "created_at", "updated_at",
                 "parsed_data", "llm_result", "original_message_id",
                 "original_media_id", "bot_instructions", "bot_instructions_step",
                 "_llm_routes", "session_log"}
    session_info = {k: v for k, v in session_data.items()
                    if k not in skip_keys and isinstance(v, (str, int, float, bool)) and v}
    original_text = session_data.get("original_text", "")

    prompt = (
        f"אתה מנתח נתוני שיחה ובוחר יציאה לפי הוראות. "
        f"החזר אך ורק מספר היציאה ללא שום טקסט נוסף.\n\n"
        f"הוראות:\n{step.get('text', '')}\n\n"
        f"ההודעה המקורית שהתקבלה:\n{original_text}\n\n"
        f"נתוני הסשן הנוכחי:\n{json.dumps(session_info, ensure_ascii=False)}\n\n"
        f"אפשרויות יציאה:\n{exit_lines}\n\n"
        f"בחר מספר יציאה (החזר רק את המספר, 1 עד {len(exits)}):"
    )

    try:
        response = _requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 5,
                "temperature": 0,
            },
            timeout=10,
        )
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"].strip()
        idx = _clamp(int(answer) - 1, len(exits))
        chosen = exits[idx]
        _record(session_data, step_id, idx, chosen, "llm")
        logger.info("[llm_router] LLM chose exit %d ('%s') -> %s",
                    idx, chosen.get("title"), chosen.get("next_step"))
        return chosen.get("next_step", "")
    except Exception as e:
        logger.error("[llm_router] LLM route failed: %s", e)

    # Fallback: first exit
    chosen = exits[0]
    _record(session_data, step_id, 0, chosen, "llm_fallback")
    logger.warning("[llm_router] fallback -> first exit: %s", chosen.get("next_step"))
    return chosen.get("next_step", "")
