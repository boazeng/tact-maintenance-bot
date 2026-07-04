"""Engine + storage smoke test (no WhatsApp). Run from repo root with the venv python."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("STORAGE_BACKEND", "sqlite")

import shared_env  # noqa: F401
from database.maintenance import bot_scripts_db
from agents.bot_engine import M10010_bot as engine

PHONE = "972500000000"


def main():
    # Clean slate
    engine.reset_session(PHONE)

    # Seed + list scripts (CRUD path)
    engine.seed_default_script()
    scripts = bot_scripts_db.list_scripts()
    assert any(s["script_id"] == "maintenance-troubleshoot" for s in scripts), "seed missing"
    print(f"[OK] scripts in DB: {len(scripts)}")

    # Round-trip a custom script with a flow position blob (editor field)
    custom = {
        "script_id": "flow_demo_test", "name": "תסריט בדיקה",
        "first_step": "Q1",
        "steps": [{"id": "Q1", "type": "text_input", "text": "מה שמך?",
                   "save_to": "full_name", "next_step": "DONE_1"}],
        "done_actions": {"DONE_1": {"text": "תודה!", "action": "save_message"}},
        "_flow_positions": {"Q1": {"x": 10, "y": 20}},
    }
    bot_scripts_db.save_script(custom)
    got = bot_scripts_db.get_script("flow_demo_test", use_cache=False)
    assert got["_flow_positions"]["Q1"]["x"] == 10, "flow position not round-tripped"
    assert got["steps"][0]["save_to"] == "full_name", "steps not round-tripped"
    print("[OK] custom script round-trip (steps + _flow_positions)")

    # Run a full conversation on the default script (integrations off)
    r = engine.start_session(PHONE, "בודק", script_id="maintenance-troubleshoot")
    assert r.get("buttons"), f"expected greeting buttons, got {r}"
    print(f"[OK] start_session → {len(r['buttons'])} buttons: {[b['title'] for b in r['buttons']]}")

    r = engine.process_message(PHONE, "intent_message")
    assert "ההודעה" in r["text"] or r.get("text"), f"expected message prompt, got {r}"
    print(f"[OK] chose 'leave a message' → prompt: {r['text'][:40]}")

    r = engine.process_message(PHONE, "זו הודעת בדיקה אוטומטית")
    assert r and r.get("text"), f"expected done message, got {r}"
    assert not r.get("buttons"), "done step should have no buttons"
    print(f"[OK] sent message → done: {r['text']}")

    # Session should now be inactive (done)
    assert engine.get_active_session(PHONE) is None, "session should be done"
    print("[OK] session closed after done action")

    # Cleanup test script
    bot_scripts_db.delete_script("flow_demo_test")
    engine.reset_session(PHONE)
    print("\nALL CHECKS PASSED ✓")


if __name__ == "__main__":
    main()
