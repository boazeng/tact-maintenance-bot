"""
Telegram API — webhook receiver so the bot runs in the cloud (no local polling).

Telegram POSTs each update to /api/telegram/webhook; we normalize it, drive the
same M1000 router + M10010 script engine as WhatsApp, and reply through the
Telegram tool. This is the webhook counterpart of run_telegram_guy.py's polling
loop — the difference is only how updates arrive (push vs pull).

New sessions are pinned to the main maintenance bot script (TELEGRAM_SCRIPT_ID).
Optionally verify Telegram's secret header (TELEGRAM_WEBHOOK_SECRET) so only
Telegram can reach the endpoint.
"""

import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from tools.telegram import telegram_bot
from agents.bot_engine import M1000_bot as m1000_bot
from agents.bot_engine import M10010_bot as m10010_bot

logger = logging.getLogger("taktbots.api.telegram")
router = APIRouter()

RESET_KEYWORDS = {"/start", "התחל", "התחל מחדש", "חזור", "תפריט", "0", "reset", "restart", "menu"}

# The main maintenance bot script (it can switch_scripts into the M10010 sub-bot).
SCRIPT_ID = os.environ.get("TELEGRAM_SCRIPT_ID", "flow_1772177781916")


@router.post("/api/telegram/webhook")
async def telegram_incoming(request: Request):
    """Receive one Telegram update, drive the engine, reply via Telegram."""
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    if secret and request.headers.get("X-Telegram-Bot-Api-Secret-Token", "") != secret:
        return JSONResponse({"ok": False}, status_code=403)

    update = await request.json()
    msg = telegram_bot.normalize_update(update)
    if not msg:
        return {"ok": True}

    if msg.get("callback_query_id"):
        telegram_bot.answer_callback(msg["callback_query_id"])

    try:
        _route_message(msg)
    except Exception as e:
        logger.error(f"Bot error for {msg.get('phone')}: {e}")

    # Always 200 quickly so Telegram doesn't retry the same update.
    return {"ok": True}


def _route_message(msg):
    """Drive the bot engine for one incoming Telegram message.

    Mirrors backend/app/api/whatsapp.py:_route_message but replies via Telegram
    and pins new sessions to the main maintenance bot script.
    """
    chat_id = msg["phone"]
    text_stripped = (msg.get("text", "") or "").strip()

    if text_stripped in RESET_KEYWORDS:
        m10010_bot.reset_session(chat_id)
        logger.info(f"Session reset by keyword for {chat_id}")
        # fall through to a fresh M1000 handoff below
    elif m10010_bot.get_active_session(chat_id):
        result = m10010_bot.process_message(
            phone=chat_id,
            text=msg.get("text", ""),
            msg_type=msg.get("type", "text"),
            caption=msg.get("caption", ""),
        )
        if result:
            _send_response(chat_id, result)
        return

    response = m1000_bot.process_message(
        phone=chat_id,
        name=msg.get("name", ""),
        text=msg.get("text", ""),
        msg_type=msg.get("type", "text"),
        message_id=msg.get("message_id", ""),
        media_id=msg.get("media_id", ""),
        caption=msg.get("caption", ""),
    )

    if isinstance(response, dict) and response.get("voice_bot_handled"):
        logger.info(f"Voice bot call created for {chat_id}: "
                    f"DOCNO={response.get('priority_callno', '')} ID={response.get('call_id', '')}")
    elif isinstance(response, dict) and response.get("handoff") == "M10010":
        result = m10010_bot.start_session(
            phone=chat_id,
            name=msg.get("name", ""),
            llm_result=response.get("llm_result", {}),
            parsed_data=response.get("parsed_data", {}),
            message_id=msg.get("message_id", ""),
            media_id=msg.get("media_id", ""),
            original_text=response.get("original_text", msg.get("text", "")),
            device_number=response.get("device_number", ""),
            customer_number=response.get("customer_number", ""),
            customer_name=response.get("customer_name", ""),
            # Pin Telegram to the MAIN maintenance bot, ignoring M1000's default
            # ROUTING_SCRIPT_ID (= the demo "maintenance-troubleshoot" script).
            script_id=SCRIPT_ID,
        )
        if result:
            _send_response(chat_id, result)
    elif isinstance(response, str) and response:
        telegram_bot.send_message(chat_id, response)


def _send_response(chat_id, result):
    """Send an engine result (text and/or inline buttons) back to Telegram."""
    text = result.get("text", "")
    if text:
        if result.get("buttons"):
            telegram_bot.send_buttons(
                chat_id, text, result["buttons"],
                header=result.get("header"), footer=result.get("footer"),
            )
        else:
            telegram_bot.send_message(chat_id, text)

    # Staff alerts always go out on WhatsApp, even for a Telegram conversation.
    notify = result.get("notify_whatsapp")
    if notify:
        from tools.whatsapp import whatsapp_bot
        failed = whatsapp_bot.send_staff_notification(notify)
        sent = [p for p in notify.get("phones", []) if p not in failed]
        logger.info(f"Staff notification sent to {sent or 'nobody'}"
                    + (f" (failed: {failed})" if failed else ""))
