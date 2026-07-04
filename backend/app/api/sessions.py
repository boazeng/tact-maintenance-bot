"""Bot-sessions (diagnostics) + bot-prompts API."""

import logging

from fastapi import APIRouter

from database.maintenance import troubleshoot_sessions_db, bot_prompts_db

logger = logging.getLogger("taktbots.api.sessions")
router = APIRouter()


@router.get("/api/bot-sessions")
def api_bot_sessions():
    """List recent bot sessions with their activity logs (for diagnostics)."""
    try:
        sessions = troubleshoot_sessions_db.list_sessions(limit=50)
        sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        light = [
            {
                "phone": s.get("phone"),
                "name": s.get("name"),
                "customer_name": s.get("customer_name"),
                "device_number": s.get("device_number"),
                "script_id": s.get("script_id"),
                "step": s.get("step"),
                "status": s.get("status", "active"),
                "created_at": s.get("created_at"),
                "updated_at": s.get("updated_at"),
                "session_log": s.get("session_log", []),
            }
            for s in sessions
        ]
        return {"ok": True, "sessions": light}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/bot-prompts")
def list_bot_prompts():
    """List all LLM prompts."""
    try:
        prompts = bot_prompts_db.list_prompts()
        return {"ok": True, "prompts": prompts, "count": len(prompts)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/bot-prompts/active")
def get_active_bot_prompt():
    """Get the currently active LLM prompt."""
    try:
        prompt = bot_prompts_db.get_active_prompt(use_cache=False)
        if not prompt:
            return {"ok": False, "error": "No active prompt found"}
        return {"ok": True, "prompt": prompt}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/bot-prompts")
def create_bot_prompt(data: dict):
    """Create a new LLM prompt."""
    if not data.get("prompt_id") or not data.get("content"):
        return {"ok": False, "error": "prompt_id and content are required"}
    try:
        result = bot_prompts_db.save_prompt(data)
        return {"ok": True, **result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.put("/api/bot-prompts/{prompt_id}")
def update_bot_prompt(prompt_id: str, data: dict):
    """Update an existing LLM prompt."""
    data["prompt_id"] = prompt_id
    try:
        result = bot_prompts_db.save_prompt(data)
        bot_prompts_db.invalidate_cache(prompt_id)
        return {"ok": True, **result}
    except Exception as e:
        return {"ok": False, "error": str(e)}
