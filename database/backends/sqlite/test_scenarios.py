"""SQLite backend for bot-test scenarios (mirrors bot_test_scenarios_db API)."""

import uuid
import logging
from datetime import datetime

from . import _base

logger = logging.getLogger("taktbots.test_scenarios")


def get_scenario(scenario_id):
    """Get a saved scenario by ID. Returns dict or None."""
    return _base.get("bot_test_scenarios", scenario_id)


def save_scenario(scenario):
    """Save or update a scenario. Assigns an id if missing. Returns {'scenario_id': ...}."""
    now = datetime.utcnow().isoformat() + "Z"
    sid = scenario.get("scenario_id") or f"scn_{uuid.uuid4().hex[:12]}"
    scenario["scenario_id"] = sid
    scenario["updated_at"] = now
    if not scenario.get("created_at"):
        scenario["created_at"] = now
    _base.put("bot_test_scenarios", sid, scenario)
    logger.info(f"Scenario saved: {sid}")
    return {"scenario_id": sid}


def list_scenarios():
    """List all saved scenarios."""
    return _base.list_all("bot_test_scenarios")


def delete_scenario(scenario_id):
    """Delete a scenario."""
    _base.delete("bot_test_scenarios", scenario_id)
    logger.info(f"Scenario deleted: {scenario_id}")
