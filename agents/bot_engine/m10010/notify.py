"""
notify — build the staff notification payload for a completed done action.

A done action may alert staff on WhatsApp either as free text (`notify_text`)
or, so it still arrives outside WhatsApp's 24-hour service window, as an
approved Meta template (`notify_template` + `notify_params`).

WhatsApp rejects template parameters that contain newlines/tabs, runs of 4+
spaces, or that are empty — every value goes through `tpl_param` first.
"""

import collections
import json
import re
from datetime import datetime, timedelta, timezone

DEFAULT_NOTIFY_TEXT = "נפתחה קריאת שירות חדשה 📞\nמספר קריאה: {call_id}\nטלפון: {phone}"

# Israel local time for the human-facing "opened at" stamp (Lambda runs on UTC).
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Asia/Jerusalem")
except Exception:                       # pragma: no cover — missing tzdata
    _TZ = timezone(timedelta(hours=3))


def notify_phones(done_config):
    """Numbers to alert. `notify_phone` may hold several, comma/space separated."""
    raw = done_config.get("notify_phone", "") or done_config.get("notify_phones", "")
    parts = raw if isinstance(raw, (list, tuple)) else re.split(r"[,;\s]+", str(raw))
    return [str(p).strip() for p in parts if p and str(p).strip()]


def tpl_param(value, limit=300):
    """Make one value safe to use as a WhatsApp template parameter."""
    s = str(value if value is not None else "").strip()
    s = re.sub(r"[\r\n\t]+", " · ", s)      # newlines are rejected outright
    s = re.sub(r" {4,}", "   ", s)          # so are runs of 4+ spaces
    if len(s) > limit:
        s = s[:limit - 1] + "…"
    return s or "-"                          # and so are empty parameters


def build_context(session, call_id):
    """Placeholders available to notify_text / notify_params."""
    ctx = {}
    raw_pd = session.get("parsed_data", {})
    if isinstance(raw_pd, str):
        try:
            raw_pd = json.loads(raw_pd)
        except (ValueError, TypeError):
            raw_pd = {}
    if isinstance(raw_pd, dict):
        ctx.update(raw_pd)
    ctx.update(session)

    down = str(session.get("is_system_down", "")).strip().lower()
    ctx["is_system_down_he"] = "כן" if down in ("yes", "true", "1", "כן") else "לא"
    ctx["opened_at"] = datetime.now(_TZ).strftime("%d/%m/%Y %H:%M")
    ctx["call_id"] = call_id
    # Address: the step-captured location, else the site of the matched device.
    ctx["address"] = session.get("location") or session.get("site", "")
    return collections.defaultdict(str, ctx)


def build_notification(done_config, session, call_id):
    """Return the notify_whatsapp payload, or None when nothing is configured."""
    phones = notify_phones(done_config)
    if not phones or not call_id:
        return None

    ctx = build_context(session, call_id)
    payload = {"phones": phones}
    template = done_config.get("notify_template", "")
    if template:
        payload["template"] = template
        payload["language"] = done_config.get("notify_language", "he")
        payload["params"] = [tpl_param(str(p).format_map(ctx))
                             for p in done_config.get("notify_params", [])]
    else:
        tmpl = str(done_config.get("notify_text") or DEFAULT_NOTIFY_TEXT)
        payload["text"] = tmpl.format_map(ctx)
    return payload
