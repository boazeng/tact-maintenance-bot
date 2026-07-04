"""
run_telegram_guy — run גיא on Telegram via long polling (local testing).

This is the Telegram counterpart of backend/app/api/whatsapp.py: it pulls
incoming Telegram updates, drives the same M1000 router + M10010 script engine,
and sends replies back through the Telegram tool. No public URL / webhook is
needed — perfect for testing Guy from your phone.

The channel is pinned to Guy's script independently of WhatsApp:
    TELEGRAM_SCRIPT_ID  (default: guy-parking-service)

Prerequisites:
    1. Create a bot with @BotFather in Telegram, copy the token.
    2. Put it in the SHARED env file:  TELEGRAM_BOT_TOKEN=123456:ABC...
    3. Make sure גיא is loaded:  python seed_guy.py

Run (from the takt-bots root):
    backend\\.venv\\Scripts\\python.exe run_telegram_guy.py

Stop with Ctrl+C. In the chat, /start (or "התחל") restarts the conversation.
"""

import sys
import os
import time

import shared_env  # noqa: F401  — loads the shared .env into os.environ

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# Guy's bot token lives under a per-bot key in the shared env (like RAN_BOT_TOKEN).
# Map it onto TELEGRAM_BOT_TOKEN, which the generic telegram tool reads.
# Override the source key name with TELEGRAM_TOKEN_ENV if needed.
_TOKEN_ENV = os.environ.get("TELEGRAM_TOKEN_ENV", "TACT_CHECK_BOT_TOKEN")
if not os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get(_TOKEN_ENV):
    os.environ["TELEGRAM_BOT_TOKEN"] = os.environ[_TOKEN_ENV]

from tools.telegram import telegram_bot
from agents.bot_engine import M1000_bot as m1000_bot
from agents.bot_engine import M10010_bot as m10010_bot

SCRIPT_ID = os.environ.get("TELEGRAM_SCRIPT_ID", "guy-parking-service")
RESET_KEYWORDS = {"/start", "התחל", "התחל מחדש", "חזור", "תפריט", "0", "reset", "restart", "menu"}


def _send_response(chat_id, result):
    """Send an engine result (text and/or buttons) back to Telegram."""
    text = result.get("text", "")
    if text:
        if result.get("buttons"):
            telegram_bot.send_buttons(
                chat_id, text, result["buttons"],
                header=result.get("header"), footer=result.get("footer"),
            )
        else:
            telegram_bot.send_message(chat_id, text)


def _route_message(msg):
    """Drive the bot engine for one incoming Telegram message.

    Mirrors backend/app/api/whatsapp.py:_route_message, but sends via Telegram
    and pins new sessions to Guy's script.
    """
    chat_id = msg["phone"]
    text_stripped = (msg.get("text", "") or "").strip()

    if text_stripped in RESET_KEYWORDS:
        m10010_bot.reset_session(chat_id)
        print(f"Session reset by keyword for {chat_id}")
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

    if isinstance(response, dict) and response.get("handoff") == "M10010":
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
            script_id=SCRIPT_ID,   # pin Telegram to Guy, independent of WhatsApp
        )
        if result:
            _send_response(chat_id, result)
    elif isinstance(response, str) and response:
        telegram_bot.send_message(chat_id, response)


def main():
    print("=" * 60)
    print("  גיא — Telegram (long polling)")
    print("=" * 60)
    if not telegram_bot.validate_config():
        sys.exit(1)

    me = telegram_bot.get_me()
    print(f"Bot: @{me.get('username', '?')} ({me.get('first_name', '')})")
    print(f"Script: {SCRIPT_ID}")
    print("Open Telegram, find the bot, send /start. Ctrl+C to stop.\n")

    offset = None
    while True:
        try:
            updates = telegram_bot.get_updates(offset=offset, timeout=30)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"get_updates error: {e} — retrying in 3s")
            time.sleep(3)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            msg = telegram_bot.normalize_update(update)
            if not msg:
                continue
            if msg.get("callback_query_id"):
                telegram_bot.answer_callback(msg["callback_query_id"])
            try:
                _route_message(msg)
            except Exception as e:
                print(f"Bot error for {msg.get('phone')}: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
