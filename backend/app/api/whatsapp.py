"""
WhatsApp API — Meta webhook (verify + incoming) and manual send.

Incoming messages flow: webhook -> M1000 router -> (active session?) M10010 engine
-> _send_bot_response back through the WhatsApp tool. Mirrors the original
urbangroup server wiring.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from tools.whatsapp import whatsapp_bot
from agents.bot_engine import M1000_bot as m1000_bot
from agents.bot_engine import M10010_bot as m10010_bot

logger = logging.getLogger("taktbots.api.whatsapp")
router = APIRouter()

RESET_KEYWORDS = {"התחל", "התחל מחדש", "חזור", "תפריט", "0", "reset", "restart", "menu"}


@router.get("/api/whatsapp/webhook", response_class=PlainTextResponse)
def whatsapp_verify(request: Request):
    """Meta webhook verification (subscription handshake)."""
    q = request.query_params
    result = whatsapp_bot.verify_webhook(
        q.get("hub.mode", ""), q.get("hub.verify_token", ""), q.get("hub.challenge", "")
    )
    if result:
        return PlainTextResponse(result, status_code=200)
    return PlainTextResponse("Forbidden", status_code=403)


@router.post("/api/whatsapp/webhook")
async def whatsapp_incoming(request: Request):
    """Receive incoming WhatsApp messages from Meta and drive the bot engine."""
    payload = await request.json()
    messages = whatsapp_bot.handle_incoming(payload)
    logger.info(f"Webhook received: {len(messages)} message(s)")

    for msg in messages:
        if msg.get("message_id"):
            try:
                whatsapp_bot.mark_as_read(msg["message_id"])
            except Exception as e:
                logger.error(f"mark_as_read failed: {e}")

    for msg in messages:
        phone = msg.get("phone", "")
        try:
            _route_message(phone, msg)
        except Exception as e:
            logger.error(f"Bot error for {phone}: {e}")

    return {"ok": True}


def _route_message(phone, msg):
    text_stripped = (msg.get("text", "") or "").strip()

    if text_stripped in RESET_KEYWORDS:
        m10010_bot.reset_session(phone)
        logger.info(f"Session reset by keyword for {phone}")
        # fall through to M1000 flow
    elif m10010_bot.get_active_session(phone):
        result = m10010_bot.process_message(
            phone=phone,
            text=msg.get("text", ""),
            msg_type=msg.get("type", "text"),
            caption=msg.get("caption", ""),
        )
        if result:
            _send_bot_response(phone, result)
            logger.info(f"M10010 reply sent to {phone}")
        return

    response = m1000_bot.process_message(
        phone=phone,
        name=msg.get("name", ""),
        text=msg.get("text", ""),
        msg_type=msg.get("type", "text"),
        message_id=msg.get("message_id", ""),
        media_id=msg.get("media_id", ""),
        caption=msg.get("caption", ""),
    )

    if isinstance(response, dict) and response.get("voice_bot_handled"):
        logger.info(f"Voice bot call created for {phone}: "
                    f"DOCNO={response.get('priority_callno', '')} ID={response.get('call_id', '')}")
    elif isinstance(response, dict) and response.get("handoff") == "M10010":
        result = m10010_bot.start_session(
            phone=phone,
            name=msg.get("name", ""),
            llm_result=response.get("llm_result", {}),
            parsed_data=response.get("parsed_data", {}),
            message_id=msg.get("message_id", ""),
            media_id=msg.get("media_id", ""),
            original_text=response.get("original_text", msg.get("text", "")),
            device_number=response.get("device_number", ""),
            customer_number=response.get("customer_number", ""),
            customer_name=response.get("customer_name", ""),
            script_id=response.get("script_id"),
        )
        if result:
            _send_bot_response(phone, result)
            logger.info(f"M10010 session started for {phone}")
    elif response:
        whatsapp_bot.send_message(phone, response)
        logger.info(f"M1000 reply sent to {phone}")


def _send_bot_response(phone, result):
    """Send a bot response — either buttons or plain text — plus optional admin notice."""
    text = result.get("text", "")
    if text:
        if result.get("buttons"):
            whatsapp_bot.send_buttons(
                phone, text, result["buttons"],
                header=result.get("header"), footer=result.get("footer"),
            )
        else:
            whatsapp_bot.send_message(phone, text)

    notify = result.get("notify_whatsapp")
    if notify and notify.get("phone") and notify.get("text"):
        try:
            whatsapp_bot.send_message(notify["phone"], notify["text"])
            logger.info(f"Admin notification sent to {notify['phone']}")
        except Exception as e:
            logger.error(f"Admin notification failed: {e}")


@router.post("/api/whatsapp/send")
def whatsapp_send(data: dict):
    """Send a WhatsApp message or template (manual / from the portal)."""
    phone = data.get("phone", "")
    text = data.get("text", "")
    template_name = data.get("template")
    if not phone:
        return {"ok": False, "error": "Missing phone number"}
    try:
        if template_name:
            result = whatsapp_bot.send_template(
                phone, template_name,
                language=data.get("language", "he"),
                parameters=data.get("parameters"),
            )
        else:
            if not text:
                return {"ok": False, "error": "Missing text"}
            result = whatsapp_bot.send_message(phone, text)
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}
