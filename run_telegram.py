"""
run_telegram — run the MAIN maintenance bot on Telegram via long polling.

Same engine as WhatsApp (M1000 router + M10010 script engine); no public URL /
webhook needed — ideal for testing from your phone. Reuses the polling loop and
message routing from run_telegram_guy, but pins the channel to the main
maintenance bot and identifies against the live Service-Call app.

Prereqs: TELEGRAM_BOT_TOKEN in the shared env; the main bot script loaded (it is).
Run:   backend/.venv/Scripts/python.exe run_telegram.py     (Ctrl+C to stop)
"""
import os

# Pin Telegram to the main maintenance bot (it switch_scripts into the sub-bot).
os.environ.setdefault("TELEGRAM_SCRIPT_ID", "flow_1772177781916")
# Identify (customer/device/open-call) against the live Service-Call app.
# Writes default to dry-run inside servicecall_provider — no real call is opened.
os.environ.setdefault("EQUIPMENT_READER_ENABLED", "true")
os.environ.setdefault("SERVICE_CALL_WRITER_ENABLED", "true")
os.environ.setdefault("BOT_EQUIPMENT_READER_MODULE", "agents.bot_engine.servicecall_provider")
os.environ.setdefault("BOT_SERVICE_CALL_WRITER_MODULE", "agents.bot_engine.servicecall_provider")

import run_telegram_guy  # reuse the tested polling loop + routing

if __name__ == "__main__":
    run_telegram_guy.main()
