"""
servicecall_provider — talk ONLY to the standalone TACT Service-Call app, never
to Priority directly. It is a full drop-in for BOTH engine integration roles:

  equipment reader : fetch_equipment_by_sernum / fetch_equipment_by_phone
                     → GET {URL}/api/v1/devices        (Priority devices, synced into the app)
  service writer   : find_open_service_calls          → GET {URL}/api/v1/open-calls  (dedup)
                     create_service_call               → POST {URL}/api/v1/service-calls
                     append_note_to_service_call       → (no bot endpoint yet — logged)

All calls use header X-API-Key. The app holds a synced copy of Priority's
SERNUMBERS + open calls, so the bot never needs Priority credentials.

Config (shared env):
    SERVICE_CALL_URL       base URL (e.g. https://service-call.newavera.co.il)
    SERVICE_CALL_API_KEY   a bot API key (format sccall_...)
    SERVICE_CALL_BRANCH    branch to stamp on new calls (default 026 = maintenance)
"""

import os
import logging

import requests

logger = logging.getLogger("taktbots.servicecall")

_created = []       # calls opened this process
_dry_write = True   # default: DON'T actually open a call (safe for testing)
_dry_seq = 0


def set_write_mode(real):
    """real=True → actually POST the call; False → dry-run (don't open anything)."""
    global _dry_write
    _dry_write = not bool(real)


def reset_activity():
    """Clear the created-calls log (called at the start of each test run)."""
    global _dry_seq
    _created.clear()
    _dry_seq = 0


def get_activity():
    return {"created_calls": list(_created), "notes": [],
            "target": "service-call", "url": _base_url(), "dry_write": _dry_write}


def _base_url():
    return os.getenv("SERVICE_CALL_URL", "http://localhost:8021").rstrip("/")


def _api_key():
    return os.getenv("SERVICE_CALL_API_KEY", "")


def _branch():
    return os.getenv("SERVICE_CALL_BRANCH", "026")


def _headers(write=False):
    h = {"X-API-Key": _api_key()}
    if write:
        h["Content-Type"] = "application/json"
    return h


def _get(path, params):
    """GET a bot read endpoint; returns the decoded JSON (a list) or []."""
    if not _api_key():
        logger.error("[servicecall] SERVICE_CALL_API_KEY not set")
        return []
    try:
        resp = requests.get(f"{_base_url()}/api/v1/{path}", params=params,
                            headers=_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # endpoints return a bare array; tolerate {"items": [...]} too
        return data.get("items", []) if isinstance(data, dict) else data
    except requests.exceptions.RequestException as e:
        logger.error(f"[servicecall] GET {path} error: {e}")
        return []


# ── Equipment reader (from the app's synced devices) ─────────────────

def _to_device(rec):
    """Map a Service-Call device row to the shape the engine expects."""
    return {
        "sernum": rec.get("sernum", ""),
        "partname": rec.get("part_name", ""),
        "partdes": rec.get("part_description", ""),
        "custname": rec.get("customer_code", ""),   # → session.customer_number
        "cdes": rec.get("customer_name", ""),        # → session.customer_name
        "phonenum": rec.get("phone", ""),
        "statusname": rec.get("status", ""),
        "familyname": rec.get("family_name", ""),
        "familydes": rec.get("family_description", ""),
        "facilityname": rec.get("facility_name", ""),
        "facilitydes": rec.get("facility_description", ""),
        "site_description": rec.get("site_description", ""),
    }


def fetch_equipment_by_sernum(sernum):
    if not sernum:
        return None
    items = _get("devices", {"sernum": sernum, "limit": 5})
    for rec in items:  # prefer an exact serial match
        if str(rec.get("sernum")) == str(sernum):
            logger.info(f"[servicecall] device {sernum} -> {rec.get('customer_name')}")
            return _to_device(rec)
    return _to_device(items[0]) if items else None


def fetch_equipment_by_phone(phone):
    return [_to_device(r) for r in _get("devices", {"phone": phone, "limit": 20})]


def fetch_equipment_by_customer(customer_number):
    """All devices belonging to a customer code (for the customer-number lookup)."""
    if not customer_number:
        return []
    rows = _get("devices", {"search": customer_number, "limit": 50})
    return [_to_device(r) for r in rows
            if str(r.get("customer_code")) == str(customer_number)]


# ── Service-call writer ──────────────────────────────────────────────

def find_open_service_calls(sernum):
    """Open calls for a device (dedup check) from the app's open-calls endpoint."""
    if not sernum:
        return []
    rows = _get("open-calls", {"device_sernum": sernum, "limit": 5})
    return [{
        "DOCNO": r.get("priority_doc_number") or r.get("call_number", ""),
        "CALLSTATUSCODE": r.get("priority_status") or r.get("status", ""),
        "call_number": r.get("call_number", ""),
    } for r in rows]


def append_note_to_service_call(docno, note_text):
    # The app has no bot-facing "append note" endpoint yet; updates to an
    # existing call go through the app's UI. Best-effort no-op for now.
    logger.info(f"[servicecall] append_note to {docno} skipped (no bot endpoint)")
    return True


def create_service_call(data):
    """Open a NEW service call in the app. Returns {'DOCNO': call_number, ...}."""
    key = _api_key()
    if not key:
        raise RuntimeError("SERVICE_CALL_API_KEY חסר — צור מפתח בוט באפליקציית service-call")

    if _dry_write:
        global _dry_seq
        _dry_seq += 1
        docno = f"SC-DRY-{_dry_seq:04d}"
        _created.append({"DOCNO": docno, "dry": True, "target": "service-call"})
        logger.info(f"[servicecall] DRY-RUN — call NOT sent (would POST): {docno}")
        return {"DOCNO": docno, "dry_run": True}

    fault_text = data.get("fault_text", "") or data.get("description", "")
    title = (data.get("summary") or data.get("description")
             or data.get("issue_type") or "קריאת שירות מהבוט")
    payload = {
        "title": title[:120],
        "description": fault_text or None,
        "customer_name": data.get("cdes") or data.get("name") or None,
        "site": data.get("location") or None,
        # Explicit branch per §4 handoff: 026 = maintenance, 110 = energy.
        "branch": _branch(),
        "device_sernum": data.get("sernum") or None,
        "contact_phone": data.get("phone") or None,
        "urgency": {"high": "high", "medium": "medium", "low": "low",
                    "urgent": "urgent"}.get(str(data.get("urgency", "medium")).lower(), "medium"),
        "external_id": data.get("message_id") or None,
        "extra": {
            "custname": data.get("custname", ""),
            "technicianlogin": data.get("technicianlogin", ""),
            "is_system_down": bool(data.get("is_system_down")),
            "issue_type": data.get("issue_type", ""),
            "origin": "takt-bots",
        },
    }

    resp = requests.post(f"{_base_url()}/api/v1/service-calls", json=payload,
                        headers=_headers(write=True), timeout=20)
    if resp.status_code >= 400:
        logger.error(f"[servicecall] ingest {resp.status_code}: {resp.text[:300]}")
        raise RuntimeError(f"Service-Call API error {resp.status_code}: {resp.text[:200]}")

    result = resp.json()
    call_number = result.get("call_number", "") or str(result.get("id", ""))
    _created.append({"DOCNO": call_number, "id": result.get("id"), "target": "service-call"})
    logger.info(f"[servicecall] opened call {call_number} (id={result.get('id')})")
    return {"DOCNO": call_number, **result}
