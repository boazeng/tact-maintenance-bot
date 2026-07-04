"""Bot-scripts API — CRUD over the storage layer (used by the visual flow editor)."""

from fastapi import APIRouter

from database.maintenance import bot_scripts_db

router = APIRouter()


@router.get("/api/bot-scripts")
def list_bot_scripts():
    """List all bot conversation scripts."""
    try:
        scripts = bot_scripts_db.list_scripts()
        return {"ok": True, "scripts": scripts, "count": len(scripts)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/bot-scripts/{script_id}")
def get_bot_script(script_id: str):
    """Get a single bot script by ID (uncached, for the editor)."""
    try:
        script = bot_scripts_db.get_script(script_id, use_cache=False)
        if not script:
            return {"ok": False, "error": "תסריט לא נמצא"}
        return {"ok": True, "script": script}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/bot-scripts")
def create_bot_script(data: dict):
    """Create a new bot script."""
    if not data.get("script_id") or not data.get("name"):
        return {"ok": False, "error": "script_id and name are required"}
    try:
        result = bot_scripts_db.save_script(data)
        return {"ok": True, **result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.put("/api/bot-scripts/{script_id}")
def update_bot_script(script_id: str, data: dict):
    """Update an existing bot script and invalidate the engine cache."""
    data["script_id"] = script_id
    try:
        result = bot_scripts_db.save_script(data)
        bot_scripts_db.invalidate_cache(script_id)
        return {"ok": True, **result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/api/bot-scripts/{script_id}")
def delete_bot_script(script_id: str):
    """Delete a bot script."""
    try:
        bot_scripts_db.delete_script(script_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
