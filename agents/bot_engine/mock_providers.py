"""
mock_providers — an in-memory fake of the external "Priority" integrations,
used by the bot-test harness so every scenario branch can be exercised without
a real ERP.

It exposes exactly the interface the engine's integration getters expect
(see integrations.py), so the real engine code runs unchanged. A test session
loads a scenario into the module-level store via ``load_scenario`` and the
engine then reads equipment / open-calls from it.

Enable it in dev by pointing the integration env vars here::

    EQUIPMENT_READER_ENABLED=true
    SERVICE_CALL_WRITER_ENABLED=true
    BOT_EQUIPMENT_READER_MODULE=agents.bot_engine.mock_providers
    BOT_SERVICE_CALL_WRITER_MODULE=agents.bot_engine.mock_providers

NOTE: the store is process-global — one active tester at a time (fine locally).
"""

import logging

logger = logging.getLogger("taktbots.mock_providers")

# ── In-memory store (populated per scenario by the test API) ──────────
_STORE = {
    "equipment": {},    # {sernum: {"custname","cdes","location", ...}}
    "open_calls": {},   # {sernum: [{"DOCNO","CALLSTATUSCODE"}, ...]}
    "by_phone": {},     # {phone: [equipment dict, ...]}
}
_created = []           # service calls created this run
_notes = []             # notes appended to existing calls
_docno_seq = 0


def load_scenario(equipment=None, open_calls=None, by_phone=None):
    """Reset the store and load a scenario's mock data.

    Args:
        equipment:  {sernum: {custname, cdes, location, ...}}
        open_calls: {sernum: [ {DOCNO, CALLSTATUSCODE}, ... ]}
        by_phone:   {phone: [equipment dict, ...]}  (optional phone lookup)
    """
    global _created, _notes, _docno_seq
    _STORE["equipment"] = dict(equipment or {})
    _STORE["open_calls"] = dict(open_calls or {})
    _STORE["by_phone"] = dict(by_phone or {})
    _created = []
    _notes = []
    _docno_seq = 0
    logger.info(
        "[mock] scenario loaded: %d device(s), %d with open call(s)",
        len(_STORE["equipment"]),
        sum(1 for v in _STORE["open_calls"].values() if v),
    )


def clear():
    """Empty the store (no devices, no open calls)."""
    load_scenario()


def get_activity():
    """Return what the mock recorded this run (for the session inspector)."""
    return {"created_calls": list(_created), "notes": list(_notes)}


# ── Equipment reader interface ───────────────────────────────────────

def fetch_equipment_by_sernum(sernum):
    """Return the device dict for a serial number, or None if unknown."""
    device = _STORE["equipment"].get(str(sernum).strip())
    logger.info("[mock] fetch_equipment_by_sernum(%s) -> %s",
                sernum, "found" if device else "None")
    return dict(device) if device else None


def fetch_equipment_by_phone(phone):
    """Return the list of devices tied to a phone number (may be empty)."""
    return list(_STORE["by_phone"].get(str(phone).strip(), []))


def fetch_equipment_by_customer(customer_number):
    """Return the devices whose custname matches the customer number."""
    cust = str(customer_number).strip()
    out = []
    for sernum, dev in _STORE["equipment"].items():
        if str(dev.get("custname", "")) == cust:
            out.append({**dev, "sernum": sernum})
    return out


# ── Service-call writer interface ────────────────────────────────────

def find_open_service_calls(device):
    """Return open service calls for a device serial number (may be empty)."""
    calls = _STORE["open_calls"].get(str(device).strip(), [])
    logger.info("[mock] find_open_service_calls(%s) -> %d", device, len(calls))
    return [dict(c) for c in calls]


def create_service_call(data):
    """Pretend to open a service call in the ERP; return a fake DOCNO."""
    global _docno_seq
    _docno_seq += 1
    docno = f"TEST-{_docno_seq:04d}"
    _created.append({"DOCNO": docno, "data": dict(data)})
    logger.info("[mock] create_service_call -> DOCNO=%s", docno)
    return {"DOCNO": docno}


def append_note_to_service_call(docno, note):
    """Pretend to append a note to an existing service call."""
    _notes.append({"DOCNO": docno, "note": note})
    logger.info("[mock] append_note_to_service_call(%s) (+%d chars)", docno, len(note or ""))
