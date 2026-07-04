"""
Telegram Bot tool — Telegram Bot API wrapper.

Mirrors the shape of tools/whatsapp/whatsapp_bot.py so the engine can drive
either channel. The bot token (TELEGRAM_BOT_TOKEN) is read from the SHARED env
file via shared_env.

For local testing we use long polling (get_updates) — no public webhook URL is
required. Buttons are rendered as an inline keyboard whose callback_data carries
the engine's button id, so the M10010 engine matches them exactly like WhatsApp
reply buttons.

Public API: validate_config, send_message, send_buttons, get_updates,
            answer_callback, normalize_update, get_me.
"""

import sys
import os
import io

# Fix Windows console encoding for Hebrew
if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests

# Load secrets from the shared env file (idempotent).
try:
    import shared_env  # noqa: F401  (import side-effect loads env)
except ImportError:
    _repo_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    import shared_env  # noqa: F401


def _token():
    return os.getenv("TELEGRAM_BOT_TOKEN", "")


def _api_url(method):
    return f"https://api.telegram.org/bot{_token()}/{method}"


def validate_config():
    if not _token():
        print("Error: Missing environment variable: TELEGRAM_BOT_TOKEN")
        from shared_env import shared_env_path
        print(f"Create a bot with @BotFather and paste the token into: {shared_env_path()}")
        return False
    return True


def get_me():
    """Return the bot's own profile (used to confirm the token works)."""
    resp = requests.get(_api_url("getMe"), timeout=10)
    resp.raise_for_status()
    return resp.json().get("result", {})


def send_message(chat_id, text):
    """Send a plain text message to a Telegram chat."""
    payload = {"chat_id": chat_id, "text": text}
    print(f"Sending message to {chat_id}: {text[:50]}...")
    resp = requests.post(_api_url("sendMessage"), json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def send_buttons(chat_id, body_text, buttons, header=None, footer=None):
    """Send a message with an inline keyboard.

    Each engine button {id, title} becomes an inline button whose callback_data
    is the button id — so a tap delivers the id back to the engine, exactly like
    a WhatsApp reply button.
    """
    text = body_text
    if header:
        text = f"{header}\n\n{text}"
    if footer:
        text = f"{text}\n\n{footer}"
    # One button per row keeps long Hebrew titles readable on mobile.
    keyboard = [[{"text": btn["title"], "callback_data": btn["id"]}] for btn in buttons]
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {"inline_keyboard": keyboard},
    }
    print(f"Sending buttons to {chat_id}: {body_text[:50]}...")
    resp = requests.post(_api_url("sendMessage"), json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def answer_callback(callback_query_id):
    """Acknowledge a button tap so Telegram stops the loading spinner."""
    try:
        requests.post(
            _api_url("answerCallbackQuery"),
            json={"callback_query_id": callback_query_id},
            timeout=10,
        )
    except Exception as e:
        print(f"answer_callback failed: {e}")


def get_updates(offset=None, timeout=30):
    """Long-poll for new updates. Returns a list of raw update dicts."""
    params = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    # HTTP timeout must exceed the long-poll timeout.
    resp = requests.get(_api_url("getUpdates"), params=params, timeout=timeout + 15)
    resp.raise_for_status()
    return resp.json().get("result", [])


def normalize_update(update):
    """Normalize a raw Telegram update into the engine's message shape.

    Returns a dict
        {update_id, phone, name, text, type, message_id, caption, callback_query_id}
    where `phone` is the chat id (the engine's session key), or None for updates
    we don't handle.
    """
    update_id = update.get("update_id")

    # Button tap
    if "callback_query" in update:
        cq = update["callback_query"]
        msg = cq.get("message", {})
        chat_id = msg.get("chat", {}).get("id", "")
        return {
            "update_id": update_id,
            "phone": str(chat_id),
            "name": cq.get("from", {}).get("first_name", ""),
            "text": cq.get("data", ""),     # = the engine button id
            "type": "interactive",
            "message_id": str(msg.get("message_id", "")),
            "caption": "",
            "callback_query_id": cq.get("id", ""),
        }

    # Regular message
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return None
    chat_id = msg.get("chat", {}).get("id", "")
    text = msg.get("text", "")
    if not text:
        # Non-text content (photo, voice, etc.) — surface a placeholder for now.
        if "photo" in msg:
            text = "[תמונה]"
        elif "voice" in msg or "audio" in msg:
            text = "[הודעה קולית]"
        elif "document" in msg:
            text = "[מסמך]"
        else:
            text = "[הודעה]"
    return {
        "update_id": update_id,
        "phone": str(chat_id),
        "name": msg.get("from", {}).get("first_name", ""),
        "text": text,
        "type": "text",
        "message_id": str(msg.get("message_id", "")),
        "caption": msg.get("caption", ""),
        "callback_query_id": "",
    }
