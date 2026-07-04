"""
bot-test API — an in-site test harness that drives the real bot engine with a
fully controlled "opening condition" (scenario), so every branch can be walked
without a real WhatsApp / Priority.

The interactive endpoints use a deterministic *drive* model: each call re-runs
the scenario from scratch (start_session + the accumulated user inputs) with the
current forced-exit map. That keeps state trivial and lets manual LLM routing
pause for a choice (needs_route) without any mid-flow persistence.

Endpoints:
  POST /api/bot-test/start    begin a scenario -> transcript (or needs_route)
  POST /api/bot-test/message  append a user message and re-drive
  POST /api/bot-test/route    pick an exit for a paused LLM step and re-drive
  POST /api/bot-test/reset    drop a tester session
  POST /api/bot-test/replay   run a whole scenario headless -> transcript + pass/fail
  GET/POST/DELETE /api/bot-test/scenarios[...]   saved-scenario CRUD
  POST /api/bot-test/run-all  run the whole saved suite -> results table

Layering: api -> engine (M10010) + llm_router + mock_providers -> storage.
"""

import os
import uuid
import logging

from fastapi import APIRouter

# Route the engine's pluggable integrations at our in-memory mock (dev default;
# real env overrides in production). Must run before the engine first resolves them.
os.environ.setdefault("EQUIPMENT_READER_ENABLED", "true")
os.environ.setdefault("SERVICE_CALL_WRITER_ENABLED", "true")
os.environ.setdefault("BOT_EQUIPMENT_READER_MODULE", "agents.bot_engine.mock_providers")
os.environ.setdefault("BOT_SERVICE_CALL_WRITER_MODULE", "agents.bot_engine.mock_providers")

from agents.bot_engine import M10010_bot as engine
from agents.bot_engine import mock_providers, priority_provider, servicecall_provider, integrations
from agents.bot_engine.m10010 import llm_router
from database.maintenance import troubleshoot_sessions_db as sessions_db
from database.maintenance import bot_test_scenarios_db as scenarios_db

logger = logging.getLogger("taktbots.api.bot_test")
router = APIRouter()

DEFAULT_TESTER = "test-001"

# Per-tester drive state: {scenario, inputs:[{send,display}], forced_exits:{}}.
_TEST_CFG = {}


# ── Helpers ──────────────────────────────────────────────────────────

def _set_cfg(scenario):
    """Remember a scenario for a tester and clear its input history.

    Assigns a stable per-run external_id so the deterministic drive model (which
    re-runs the whole flow each turn) is idempotent — Service-Call dedups on it,
    so repeated runs never open duplicate calls. Also resets provider activity."""
    tester_id = (scenario.get("caller", {}) or {}).get("phone") or DEFAULT_TESTER
    _TEST_CFG[tester_id] = {
        "scenario": scenario,
        "inputs": [],
        "forced_exits": dict(scenario.get("forced_exits", {}) or {}),
        "ext_id": f"takt-test-{tester_id}-{uuid.uuid4().hex[:8]}",
    }
    servicecall_provider.reset_activity()
    priority_provider.reset_activity()
    return tester_id


def _set_provider(source, write_target="dry", write_real=False):
    """Wire the engine's integrations. `source` picks the READ side (equipment /
    open-call lookups); `write_target` picks where a NEW service call is opened.

      source:       mock | servicecall | priority-demo | priority-real
      write_target: dry (don't open) | priority (real Priority) | servicecall (my app)
      write_real:   only for write_target=servicecall — actually POST (True) or
                    dry-run without opening a call (False, default).
    """
    # Read side (equipment / open-call identification)
    if source == "servicecall":
        reader = servicecall_provider              # read from the Service-Call app's synced data
    elif source in ("priority-demo", "priority-real"):
        priority_provider.set_env("demo" if source == "priority-demo" else "real")
        reader = priority_provider
    else:
        reader = mock_providers
    integrations._equipment_reader = reader

    # Write side (where a NEW service call is opened)
    if write_target == "servicecall":
        servicecall_provider.set_write_mode(write_real)   # gated: dry-run by default
        integrations._service_call_writer = servicecall_provider
    elif write_target == "priority":
        priority_provider.set_env("demo" if source == "priority-demo" else "real")
        priority_provider.set_write_mode(True)
        integrations._service_call_writer = priority_provider
    else:  # dry — read live, but don't actually open a call
        if reader is priority_provider:
            priority_provider.set_write_mode(False)
            integrations._service_call_writer = priority_provider
        else:
            integrations._service_call_writer = mock_providers


def _activity(source, write_target="dry"):
    """Return the active writer's activity (created calls) for the inspector."""
    if write_target == "servicecall":
        return servicecall_provider.get_activity()
    if write_target == "priority" or source in ("priority-demo", "priority-real"):
        return priority_provider.get_activity()
    return mock_providers.get_activity()


def _restore(tester_id, on_missing="default"):
    """Reload the mock store + LLM routing + data source for a tester."""
    cfg = _TEST_CFG.get(tester_id, {})
    scenario = cfg.get("scenario", {})
    mock_providers.load_scenario(
        equipment=scenario.get("equipment", {}) or {},
        open_calls=scenario.get("open_calls", {}) or {},
        by_phone=scenario.get("by_phone", {}) or {},
    )
    _set_provider(scenario.get("data_source", "mock"),
                  write_target=scenario.get("write_target", "dry"),
                  write_real=bool(scenario.get("write_real", False)))
    llm_router.configure(mode=scenario.get("llm_mode", "manual"),
                         forced=cfg.get("forced_exits", {}),
                         on_missing=on_missing)


def _start_args(scenario, tester_id):
    """Translate a scenario's caller + inbound into start_session() kwargs."""
    caller = scenario.get("caller", {}) or {}
    inbound = scenario.get("inbound", {}) or {}

    parsed = dict(inbound.get("parsed_data", {}) or {})
    # A QR / voice-bot message carries the device number under this Hebrew key,
    # which the engine reads into session["device_number"].
    if inbound.get("device_number") and "מספר מכשיר" not in parsed:
        parsed["מספר מכשיר"] = str(inbound["device_number"])

    known = bool(caller.get("known"))
    return dict(
        phone=tester_id,
        name=caller.get("name", ""),
        parsed_data=parsed,
        original_text=inbound.get("text", ""),
        script_id=scenario.get("script_id") or None,
        customer_name=caller.get("customer_name", "") if known else "",
        customer_number=caller.get("customer_number", "") if known else "",
        # Stable id per test run → idempotent writes (Service-Call dedups on it).
        message_id=_TEST_CFG.get(tester_id, {}).get("ext_id", ""),
        # A voice-bot message carries an image; give the session a media id so the
        # engine handles it like a real image message (attached to the service call).
        media_id=(f"test-img-{_TEST_CFG.get(tester_id, {}).get('ext_id', '')}"
                  if inbound.get("has_media") else ""),
    )


LIGHT_SKIP = {"parsed_data", "llm_result", "bot_instructions", "session_log",
              "_llm_routes", "expires_at", "session_id"}


def _light_session(tester_id):
    """Return the useful bits of the session for the inspector."""
    s = sessions_db.get_session(tester_id) or {}
    fields = {k: v for k, v in s.items()
              if k not in LIGHT_SKIP and isinstance(v, (str, int, float, bool))}
    parsed = s.get("parsed_data", {})
    if isinstance(parsed, str):
        parsed = {}
    return {
        "step": s.get("step"),
        "script_id": s.get("script_id"),
        "status": s.get("status", "active"),
        "fields": fields,
        "parsed_data": parsed,
        "log": s.get("session_log", []),
        "llm_routes": s.get("_llm_routes", []),
    }


def _reply(result):
    """Normalise an engine result into {text, buttons, notify}."""
    if not result:
        return {"text": "", "buttons": None}
    return {"text": result.get("text", ""), "buttons": result.get("buttons"),
            "notify": result.get("notify_whatsapp")}


def _drive(tester_id, on_missing):
    """Re-run the scenario from scratch: start + accumulated inputs. Returns a full
    transcript; on a paused LLM step (manual + on_missing='raise') returns needs_route."""
    cfg = _TEST_CFG[tester_id]
    scenario = cfg["scenario"]
    transcript = []
    needs_route = None
    try:
        _restore(tester_id, on_missing)
        engine.reset_session(tester_id)
        result = engine.start_session(**_start_args(scenario, tester_id))
        transcript.append({"from": "bot", **_reply(result)})

        for inp in cfg["inputs"]:
            if engine.get_active_session(tester_id) is None:
                transcript.append({"from": "note", "text": "השיחה הסתיימה — התחל בדיקה חדשה."})
                break
            transcript.append({"from": "user", "text": inp.get("display") or inp["send"]})
            _restore(tester_id, on_missing)
            result = engine.process_message(phone=tester_id, text=inp["send"])
            transcript.append({"from": "bot", **_reply(result or {})})
    except llm_router.RouteChoiceNeeded as rc:
        needs_route = {"step": rc.step_id, "exits": rc.exits}

    source = scenario.get("data_source", "mock")
    return {"transcript": transcript, "needs_route": needs_route,
            "session": _light_session(tester_id),
            "mock": _activity(source, scenario.get("write_target", "dry"))}


# ── Interactive endpoints ────────────────────────────────────────────

@router.post("/api/bot-test/start")
def bot_test_start(scenario: dict):
    """Begin a scenario (resets any prior run for this tester)."""
    try:
        tester_id = _set_cfg(scenario)
        return {"ok": True, "tester_id": tester_id, **_drive(tester_id, "raise")}
    except Exception as e:
        logger.exception("bot_test_start failed")
        return {"ok": False, "error": str(e)}


@router.post("/api/bot-test/message")
def bot_test_message(data: dict):
    """Append a user message (free text or a button id) and re-drive."""
    tester_id = data.get("tester_id") or DEFAULT_TESTER
    cfg = _TEST_CFG.get(tester_id)
    if not cfg:
        return {"ok": False, "error": "no_session"}
    try:
        cfg["inputs"].append({"send": data.get("text", ""),
                              "display": data.get("display") or data.get("text", "")})
        return {"ok": True, "tester_id": tester_id, **_drive(tester_id, "raise")}
    except Exception as e:
        logger.exception("bot_test_message failed")
        return {"ok": False, "error": str(e)}


@router.post("/api/bot-test/route")
def bot_test_route(data: dict):
    """Pick an exit for a paused LLM step, then re-drive."""
    tester_id = data.get("tester_id") or DEFAULT_TESTER
    cfg = _TEST_CFG.get(tester_id)
    if not cfg:
        return {"ok": False, "error": "no_session"}
    step = data.get("step", "")
    try:
        cfg["forced_exits"][step] = int(data.get("exit_index", 0))
        return {"ok": True, "tester_id": tester_id, **_drive(tester_id, "raise")}
    except Exception as e:
        logger.exception("bot_test_route failed")
        return {"ok": False, "error": str(e)}


@router.post("/api/bot-test/reset")
def bot_test_reset(data: dict):
    """Drop a tester session so the next start is clean."""
    tester_id = data.get("tester_id") or DEFAULT_TESTER
    try:
        engine.reset_session(tester_id)
        _TEST_CFG.pop(tester_id, None)
        return {"ok": True, "tester_id": tester_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Headless run (replay + regression) ───────────────────────────────

def _run(scenario):
    """Run a whole scenario headless (default missing LLM routes to exit 0)."""
    tester_id = _set_cfg(scenario)
    _TEST_CFG[tester_id]["inputs"] = [
        {"send": s.get("send", ""), "display": s.get("send", "")}
        for s in scenario.get("steps", [])
    ]
    run = _drive(tester_id, "default")
    run["verdict"] = _evaluate(scenario.get("expect"), run["transcript"], run["session"])
    run["tester_id"] = tester_id
    return run


@router.post("/api/bot-test/replay")
def bot_test_replay(scenario: dict):
    """Run one scenario headless and return the transcript + pass/fail."""
    try:
        return {"ok": True, **_run(scenario)}
    except Exception as e:
        logger.exception("bot_test_replay failed")
        return {"ok": False, "error": str(e)}


# ── Saved scenarios (regression suite) ───────────────────────────────

@router.get("/api/bot-test/scenarios")
def list_scenarios():
    """List all saved test scenarios."""
    try:
        items = scenarios_db.list_scenarios()
        items.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        return {"ok": True, "scenarios": items}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/bot-test/scenarios")
def save_scenario(scenario: dict):
    """Create or update a saved scenario."""
    try:
        return {"ok": True, **scenarios_db.save_scenario(scenario)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/bot-test/scenarios/{scenario_id}")
def get_scenario(scenario_id: str):
    scenario = scenarios_db.get_scenario(scenario_id)
    if not scenario:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "scenario": scenario}


@router.delete("/api/bot-test/scenarios/{scenario_id}")
def delete_scenario(scenario_id: str):
    try:
        scenarios_db.delete_scenario(scenario_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/bot-test/run-all")
def run_all():
    """Run every saved scenario that has steps, and return a results table."""
    try:
        results = []
        for scenario in scenarios_db.list_scenarios():
            # Runnable if it has user steps or an expectation to check (a
            # voice-bot scenario reaches DONE via routing alone, no steps).
            if not scenario.get("steps") and not scenario.get("expect"):
                continue
            try:
                run = _run(scenario)
                verdict = run["verdict"]
                results.append({
                    "scenario_id": scenario.get("scenario_id"),
                    "name": scenario.get("name") or scenario.get("scenario_id"),
                    "passed": (verdict or {}).get("passed") if verdict else None,
                    "checks": (verdict or {}).get("checks", []),
                    "final_step": run["session"].get("step"),
                })
            except Exception as ex:
                results.append({"scenario_id": scenario.get("scenario_id"),
                                "name": scenario.get("name"), "passed": False,
                                "error": str(ex)})
        passed = sum(1 for r in results if r.get("passed") is True)
        return {"ok": True, "total": len(results), "passed": passed,
                "failed": len(results) - passed, "results": results}
    except Exception as e:
        logger.exception("run_all failed")
        return {"ok": False, "error": str(e)}


def _evaluate(expect, transcript, session):
    """Check a scenario's expectations against the run. Returns None if no expect."""
    if not expect:
        return None
    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    if "reach_step" in expect:
        add("reach_step", session.get("step") == expect["reach_step"],
            f"step={session.get('step')}")

    if "final_action" in expect:
        actions = [e.get("action") for e in session.get("log", [])
                   if e.get("event") == "session_done"]
        add("final_action", expect["final_action"] in actions, f"actions={actions}")

    if "contains_text" in expect:
        needle = expect["contains_text"]
        found = any(needle in (m.get("text") or "")
                    for m in transcript if m.get("from") == "bot")
        add("contains_text", found, f"needle={needle!r}")

    return {"passed": all(c["pass"] for c in checks), "checks": checks}
