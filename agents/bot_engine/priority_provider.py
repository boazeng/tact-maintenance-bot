"""
priority_provider — real Priority Cloud (OData) integration for the bot engine.

Exposes exactly the interface the engine's integration getters expect (see
integrations.py), so it can be plugged in place of mock_providers:

  equipment reader : fetch_equipment_by_sernum, fetch_equipment_by_phone
  service writer    : find_open_service_calls, create_service_call,
                      append_note_to_service_call

Credentials come from the shared env (PRIORITY_URL_DEMO / PRIORITY_URL_REAL,
PRIORITY_USERNAME, PRIORITY_PASSWORD). Pick the environment with set_env('demo'|'real').

Adapted from the urbangroup agents 600 (equipment) and 300 (service call), whose
source files carry digit-prefixed names that are not importable as modules.
"""

import os
import re
import base64
import logging
from datetime import datetime, timezone, timedelta

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger("taktbots.priority")

# Israel local time (UTC+2 winter). Priority treats datetimes as local time.
_ISRAEL_TZ = timezone(timedelta(hours=2))

EQUIPMENT_FIELDS = (
    "SERNUM,PARTNAME,PARTDES,CUSTNAME,CDES,PHONENUM,"
    "STATUSNAME,FAMILYNAME,FAMILYDES,FACILITYNAME,FACILITYDES"
)

_env = os.getenv("BOT_PRIORITY_ENV", "real")   # 'demo' | 'real'
_dry_write = True    # default: READS are live, WRITES are simulated (safe for tests)
_created = []        # service calls this process (real or dry)
_dry_seq = 0


def set_env(name):
    """Select the Priority environment: 'demo' or 'real' (ebyael)."""
    global _env
    _env = "demo" if str(name).lower() == "demo" else "real"


def set_write_mode(real):
    """real=True → actually POST service calls; False → dry-run (read live, don't write)."""
    global _dry_write
    _dry_write = not bool(real)


def reset_activity():
    """Clear the created-calls log (called at the start of each test run)."""
    global _dry_seq
    _created.clear()
    _dry_seq = 0


def current_env():
    return _env


def get_activity():
    """Match mock_providers.get_activity() so the inspector can show created calls."""
    return {"created_calls": list(_created), "notes": [],
            "env": _env, "live": True, "dry_write": _dry_write}


def _base_url():
    key = "PRIORITY_URL_DEMO" if _env == "demo" else "PRIORITY_URL_REAL"
    url = os.getenv(key) or os.getenv("PRIORITY_URL", "")
    return url.rstrip("/")


def _auth():
    return HTTPBasicAuth(os.getenv("PRIORITY_USERNAME", ""), os.getenv("PRIORITY_PASSWORD", ""))


_HEADERS = {"Accept": "application/json", "OData-Version": "4.0"}
_WRITE_HEADERS = {**_HEADERS, "Content-Type": "application/json"}


def _israel_now():
    return datetime.now(_ISRAEL_TZ).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Equipment reader ─────────────────────────────────────────────────

def _to_device(rec):
    return {
        "sernum": rec.get("SERNUM", ""),
        "partname": rec.get("PARTNAME", ""),
        "partdes": rec.get("PARTDES", ""),
        "custname": rec.get("CUSTNAME", ""),
        "cdes": rec.get("CDES", ""),
        "phonenum": rec.get("PHONENUM", ""),
        "statusname": rec.get("STATUSNAME", ""),
        "familyname": rec.get("FAMILYNAME", ""),
        "familydes": rec.get("FAMILYDES", ""),
        "facilityname": rec.get("FACILITYNAME", ""),
        "facilitydes": rec.get("FACILITYDES", ""),
    }


def _phone_variants(phone):
    """All formats to try — Priority stores numbers inconsistently."""
    digits = re.sub(r"[^0-9]", "", phone)
    if digits.startswith("972") and len(digits) > 9:
        local9 = digits[3:]
    elif digits.startswith("0") and len(digits) >= 9:
        local9 = digits[1:]
    else:
        local9 = digits
    variants = set()
    if len(local9) == 9:
        variants.add(f"+972{local9}")
        variants.add(f"0{local9}")
        variants.add(f"0{local9[:2]}-{local9[2:]}")
    variants.add(digits)
    return variants


def fetch_equipment_by_customer(customer_number):
    """All active devices for a customer code (for the customer-number lookup)."""
    if not customer_number:
        return []
    try:
        resp = requests.get(
            f"{_base_url()}/SERNUMBERS",
            params={"$filter": f"CUSTNAME eq '{customer_number}'", "$select": EQUIPMENT_FIELDS},
            headers=_HEADERS, auth=_auth(), timeout=15,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"[priority] fetch_equipment_by_customer {customer_number} error: {e}")
        return []
    return [_to_device(r) for r in resp.json().get("value", [])
            if r.get("STATUSNAME", "") != "Reject"]


def fetch_equipment_by_phone(phone):
    """Active devices for a customer phone number (list, possibly empty)."""
    variants = _phone_variants(phone)
    if not variants:
        return []
    or_clauses = " or ".join(f"PHONENUM eq '{v}'" for v in variants)
    try:
        resp = requests.get(
            f"{_base_url()}/SERNUMBERS",
            params={"$filter": f"({or_clauses})", "$select": EQUIPMENT_FIELDS},
            headers=_HEADERS, auth=_auth(), timeout=15,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"[priority] fetch_equipment_by_phone error: {e}")
        return []
    devices = [_to_device(r) for r in resp.json().get("value", [])
               if r.get("STATUSNAME", "") != "Reject"]
    logger.info(f"[priority/{_env}] {len(devices)} active device(s) for phone {phone}")
    return devices


def fetch_equipment_by_sernum(sernum):
    """One device by serial number, or None. Uses $filter (handles leading zeros)."""
    if not sernum:
        return None
    try:
        resp = requests.get(
            f"{_base_url()}/SERNUMBERS",
            params={"$filter": f"SERNUM eq '{sernum}'", "$select": EQUIPMENT_FIELDS},
            headers=_HEADERS, auth=_auth(), timeout=15,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"[priority] fetch_equipment_by_sernum {sernum} error: {e}")
        return None
    records = resp.json().get("value", [])
    if not records:
        logger.info(f"[priority/{_env}] device {sernum} not found")
        return None
    device = _to_device(records[0])
    logger.info(f"[priority/{_env}] device {sernum} -> {device['custname']} ({device['cdes']})")
    return device


# ── Service call writer ──────────────────────────────────────────────

def customer_exists(custname):
    try:
        resp = requests.get(f"{_base_url()}/CUSTOMERS('{custname}')",
                            headers=_HEADERS, auth=_auth(), timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


def sernum_exists(sernum):
    try:
        resp = requests.get(
            f"{_base_url()}/SERNUMBERS",
            params={"$filter": f"SERNUM eq '{sernum}'", "$select": "SERNUM"},
            headers=_HEADERS, auth=_auth(), timeout=10,
        )
        return len(resp.json().get("value", [])) > 0
    except Exception:
        return False


def find_open_service_calls(sernum):
    """Open service calls for a device (list of {DOCNO, CALLSTATUSCODE, STARTDATE, CDES})."""
    try:
        resp = requests.get(
            f"{_base_url()}/DOCUMENTS_Q",
            params={"$filter": f"SERNUM eq '{sernum}' and ACTIVEFLAG eq 'Y'",
                    "$select": "DOCNO,CALLSTATUSCODE,STARTDATE,CDES", "$top": "5"},
            headers=_HEADERS, auth=_auth(), timeout=10,
        )
        if resp.status_code != 200:
            logger.warning(f"[priority] find_open_service_calls HTTP {resp.status_code}")
            return []
        return resp.json().get("value", [])
    except Exception as e:
        logger.warning(f"[priority] find_open_service_calls failed: {e}")
        return []


def create_service_call(data):
    """Create a service call in Priority. Returns the API response (includes DOCNO)."""
    branchname = data.get("branchname", "001")
    custname = data.get("custname", "99999")
    if not custname or custname == "99999" or not customer_exists(custname):
        logger.info(f"[priority] customer '{custname}' not found, using 99999")
        custname = "99999"

    body = {"CUSTNAME": custname, "BRANCHNAME": branchname, "STARTDATE": _israel_now()}
    if data.get("callstatuscode"):
        body["CALLSTATUSCODE"] = data["callstatuscode"]

    for src, dst in (("technicianlogin", "TECHNICIANLOGIN"), ("contact_name", "NAME"),
                     ("phone", "PHONENUM"), ("partname", "PARTNAME")):
        if data.get(src):
            body[dst] = data[src]

    sernum = data.get("sernum", "")
    if sernum and sernum_exists(sernum):
        body["SERNUM"] = sernum

    if data.get("is_system_down"):
        body["BREAKSTART"] = _israel_now()

    fault_desc = data.get("fault_text", "") or data.get("description", "")
    details = []
    if fault_desc:
        details.append(fault_desc[:22])
    if data.get("location"):
        details.append(data["location"])
    if details:
        body["DETAILS"] = " | ".join(details)

    text_parts = [data[k] for k in ("fault_text", "internal_notes") if data.get(k)]
    if not text_parts and data.get("description"):
        text_parts = [data["description"]]
    if text_parts:
        body["DOCTEXT_Q_2_SUBFORM"] = {"TEXT": "\n".join(text_parts)}

    # Dry-run: read live but do NOT create a real service call (test safety).
    if _dry_write:
        global _dry_seq
        _dry_seq += 1
        docno = f"DRY-{_dry_seq:04d}"
        _created.append({"DOCNO": docno, "env": _env, "dry": True})
        logger.info(f"[priority/{_env}] DRY-RUN — service call NOT created (would POST): {docno}")
        return {"DOCNO": docno, "dry_run": True}

    resp = requests.post(f"{_base_url()}/DOCUMENTS_Q", json=body,
                        headers=_WRITE_HEADERS, auth=_auth(), timeout=20)
    if resp.status_code >= 400:
        try:
            err = resp.json().get("FORM", {}).get("InterfaceErrors", {}).get("text", "")
        except Exception:
            err = resp.text[:300]
        logger.error(f"[priority] create_service_call {resp.status_code}: {err}")
        raise RuntimeError(err or f"Priority API error {resp.status_code}")

    result = resp.json()
    docno = result.get("DOCNO", "")
    _created.append({"DOCNO": docno, "env": _env, "dry": False})
    logger.info(f"[priority/{_env}] service call created DOCNO={docno}")
    return result


def append_note_to_service_call(docno, note_text):
    """Append a text note to an existing service call's fault description."""
    if _dry_write:
        logger.info(f"[priority/{_env}] DRY-RUN — note NOT appended to {docno}")
        return True
    base = f"{_base_url()}/DOCUMENTS_Q(DOCNO='{docno}',TYPE='Q')"
    existing = ""
    try:
        r = requests.get(f"{base}/DOCTEXT_Q_2_SUBFORM", headers=_HEADERS, auth=_auth(), timeout=10)
        if r.status_code == 200:
            existing = r.json().get("TEXT", "")
    except Exception as e:
        logger.warning(f"[priority] read text for {docno} failed: {e}")

    note_html = "<br>".join(l for l in note_text.split("\n") if l.strip())
    combined = (existing.rstrip() + "<br><b>---</b><br>" + note_html) if existing else note_html
    try:
        r = requests.post(f"{base}/DOCTEXT_Q_2_SUBFORM", json={"TEXT": combined},
                         headers=_WRITE_HEADERS, auth=_auth(), timeout=15)
        if r.status_code not in (200, 201):
            logger.warning(f"[priority] update text {docno}: {r.status_code}")
            return False
    except Exception as e:
        logger.warning(f"[priority] update text {docno} failed: {e}")
        return False

    try:
        encoded = base64.b64encode(note_text.encode("utf-8")).decode("ascii")
        requests.post(f"{base}/EXTFILES_SUBFORM", json={
            "EXTFILEDES": "עדכון מהבוט",
            "EXTFILENAME": f"data:text/plain;base64,{encoded}",
            "SUFFIX": ".txt",
        }, headers=_WRITE_HEADERS, auth=_auth(), timeout=15)
    except Exception:
        pass
    return True
