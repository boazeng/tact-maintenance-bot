"""
SQLite backend for messages + service-call records (mirrors maintenance_db API).

The original urbangroup module carried Priority-ERP-specific columns; here they
are kept as plain optional fields on the record dict so generic flows that set
them still round-trip, while standalone bots that ignore them are unaffected.
"""

import uuid
import logging
from datetime import datetime

from . import _base

logger = logging.getLogger("taktbots.messages")


# ── Messages ──────────────────────────────────────────────────

def save_message(phone, name, text, msg_type="text", message_id="", parsed_data=None):
    """Save an incoming message. Returns {'id': ...}."""
    item_id = str(uuid.uuid4())
    item = {
        "id": item_id,
        "phone": phone,
        "name": name,
        "text": text,
        "msg_type": msg_type,
        "message_id": message_id,
        "status": "new",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    if parsed_data:
        item["parsed_data"] = parsed_data
    _base.put("messages", item_id, item)
    logger.info(f"Saved message {item_id} from {phone}")
    return {"id": item_id}


def get_messages(status=None, limit=50):
    """Retrieve messages, optionally filtered by status, newest first."""
    items = _base.list_all("messages")
    if status:
        items = [m for m in items if m.get("status") == status]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items[:limit]


def update_message_status(item_id, new_status):
    """Update the status of a message. Returns updated item."""
    item = _base.get("messages", item_id)
    if item is None:
        return {}
    item["status"] = new_status
    item["updated_at"] = datetime.utcnow().isoformat() + "Z"
    _base.put("messages", item_id, item)
    logger.info(f"Updated message {item_id} status to {new_status}")
    return item


# ── Service Calls ─────────────────────────────────────────────

def save_service_call(phone, name, issue_type, description, urgency,
                      location="", summary="", message_id="", media_id="",
                      source_type="whatsapp",
                      custname="", cdes="", sernum="", branchname="",
                      callstatuscode="", technicianlogin="",
                      contact_name="", fault_text="", internal_notes="",
                      breakstart="", partname="",
                      is_system_down=False):
    """Save a service-call / fault record. Returns {'id': ...}."""
    item_id = str(uuid.uuid4())
    item = {
        "id": item_id,
        "phone": phone,
        "name": name,
        "issue_type": issue_type,
        "description": description,
        "urgency": urgency,
        "location": location or "",
        "summary": summary or "",
        "message_id": message_id,
        "media_id": media_id,
        "source_type": source_type,
        "status": "new",
        "created_at": datetime.utcnow().isoformat() + "Z",
        # Optional Priority-ERP passthrough fields
        "custname": custname or "99999",
        "cdes": cdes or name or "",
        "sernum": sernum or "",
        "branchname": branchname or "001",
        "callstatuscode": callstatuscode or "ממתין לאישור",
        "technicianlogin": technicianlogin or "",
        "contact_name": contact_name or "",
        "fault_text": fault_text or "",
        "internal_notes": internal_notes or "",
        "breakstart": breakstart or "",
        "partname": partname or "",
        "is_system_down": bool(is_system_down),
        "priority_pushed": False,
    }
    _base.put("service_calls", item_id, item)
    logger.info(f"Saved service call {item_id}: {issue_type} ({urgency}) from {phone}")
    return {"id": item_id}


def get_service_calls(status=None, phone=None, limit=50):
    """Retrieve service calls, optionally filtered, newest first."""
    items = _base.list_all("service_calls")
    if status:
        items = [c for c in items if c.get("status") == status]
    elif phone:
        items = [c for c in items if c.get("phone") == phone]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items[:limit]


def update_service_call_status(item_id, new_status):
    """Update the status of a service call. Returns updated item."""
    item = _base.get("service_calls", item_id)
    if item is None:
        return {}
    item["status"] = new_status
    item["updated_at"] = datetime.utcnow().isoformat() + "Z"
    _base.put("service_calls", item_id, item)
    logger.info(f"Updated service call {item_id} status to {new_status}")
    return item


def get_service_call(item_id):
    """Get a single service call by ID, or None."""
    return _base.get("service_calls", item_id)


def mark_service_call_pushed(item_id, callno=""):
    """Mark a service call as pushed to an external system. Returns updated item."""
    item = _base.get("service_calls", item_id)
    if item is None:
        return {}
    item["priority_pushed"] = True
    item["updated_at"] = datetime.utcnow().isoformat() + "Z"
    if callno:
        item["priority_callno"] = callno
    _base.put("service_calls", item_id, item)
    logger.info(f"Marked service call {item_id} as pushed (CALLNO={callno})")
    return item
