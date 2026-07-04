"""
WhatsApp Bot tool — Meta WhatsApp Cloud API wrapper.

Copied from the urbangroup 5000-whatsapp agent and made standalone:
env (WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_ACCESS_TOKEN / WHATSAPP_VERIFY_TOKEN)
is read from the SHARED env file via shared_env, not a project-local .env.

Public API: send_message, send_template, send_buttons, verify_webhook,
            handle_incoming, mark_as_read.
"""

import sys
import os
import io
import json

# Fix Windows console encoding for Hebrew
if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests

# Load secrets from the shared env file (idempotent).
try:
    import shared_env  # noqa: F401  (import side-effect loads env)
except ImportError:
    # When imported outside the repo root, add it to sys.path and retry.
    _repo_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    import shared_env  # noqa: F401


def _phone_number_id():
    return os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")


def _access_token():
    return os.getenv("WHATSAPP_ACCESS_TOKEN", "")


def _verify_token():
    return os.getenv("WHATSAPP_VERIFY_TOKEN", "")


def _api_url():
    return f"https://graph.facebook.com/v21.0/{_phone_number_id()}/messages"


def _headers():
    return {
        "Authorization": f"Bearer {_access_token()}",
        "Content-Type": "application/json",
    }


def validate_config():
    missing = []
    if not _phone_number_id():
        missing.append("WHATSAPP_PHONE_NUMBER_ID")
    if not _access_token():
        missing.append("WHATSAPP_ACCESS_TOKEN")
    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        from shared_env import shared_env_path
        print(f"Please fill in the shared .env at: {shared_env_path()}")
        return False
    return True


def send_message(phone, text):
    """Send a text message to a WhatsApp number."""
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "text",
        "text": {"body": text},
    }
    print(f"Sending message to {phone}: {text[:50]}...")
    resp = requests.post(_api_url(), json=payload, headers=_headers())
    resp.raise_for_status()
    result = resp.json()
    msg_id = result.get("messages", [{}])[0].get("id", "N/A")
    print(f"Message sent → ID: {msg_id}")
    return result


def send_template(phone, template_name, language="he", parameters=None):
    """Send a template message (required for first contact with a user)."""
    template = {"name": template_name, "language": {"code": language}}
    if parameters:
        template["components"] = [{
            "type": "body",
            "parameters": [{"type": "text", "text": str(p)} for p in parameters],
        }]
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": template,
    }
    print(f"Sending template '{template_name}' to {phone}...")
    resp = requests.post(_api_url(), json=payload, headers=_headers())
    resp.raise_for_status()
    result = resp.json()
    msg_id = result.get("messages", [{}])[0].get("id", "N/A")
    print(f"Template sent → ID: {msg_id}")
    return result


def send_buttons(phone, body_text, buttons, header=None, footer=None):
    """Send an interactive button message (max 3 buttons, 20 chars per title)."""
    interactive = {
        "type": "button",
        "body": {"text": body_text},
        "action": {
            "buttons": [
                {
                    "type": "reply",
                    "reply": {"id": btn["id"], "title": btn["title"][:20]},
                }
                for btn in buttons[:3]
            ]
        },
    }
    if header:
        interactive["header"] = {"type": "text", "text": header[:60]}
    if footer:
        interactive["footer"] = {"text": footer[:60]}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "interactive",
        "interactive": interactive,
    }
    print(f"Sending buttons to {phone}: {body_text[:50]}...")
    resp = requests.post(_api_url(), json=payload, headers=_headers())
    resp.raise_for_status()
    result = resp.json()
    msg_id = result.get("messages", [{}])[0].get("id", "N/A")
    print(f"Buttons sent → ID: {msg_id}")
    return result


def verify_webhook(mode, token, challenge):
    """Verify webhook subscription from Meta. Returns challenge if valid, else None."""
    if mode == "subscribe" and token == _verify_token():
        print("Webhook verified successfully")
        return challenge
    print(f"Webhook verification failed: mode={mode}, token mismatch")
    return None


def handle_incoming(payload):
    """Process an incoming webhook payload from Meta.

    Returns:
        list of dicts [{phone, name, text, type, timestamp, message_id, media_id, caption}]
    """
    messages = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts = {
                c["wa_id"]: c.get("profile", {}).get("name", "")
                for c in value.get("contacts", [])
            }
            for msg in value.get("messages", []):
                phone = msg.get("from", "")
                name = contacts.get(phone, "")
                timestamp = msg.get("timestamp", "")
                msg_type = msg.get("type", "")
                text = ""
                media_id = ""
                caption = ""
                if msg_type == "text":
                    text = msg.get("text", {}).get("body", "")
                elif msg_type == "image":
                    text = "[תמונה]"
                    media_id = msg.get("image", {}).get("id", "")
                    caption = msg.get("image", {}).get("caption", "")
                elif msg_type == "document":
                    text = "[מסמך]"
                    media_id = msg.get("document", {}).get("id", "")
                elif msg_type == "audio":
                    text = "[הודעה קולית]"
                    media_id = msg.get("audio", {}).get("id", "")
                elif msg_type == "interactive":
                    interactive = msg.get("interactive", {})
                    int_type = interactive.get("type", "")
                    if int_type == "button_reply":
                        btn = interactive.get("button_reply", {})
                        text = btn.get("id", "")
                        caption = btn.get("title", "")
                    elif int_type == "list_reply":
                        reply = interactive.get("list_reply", {})
                        text = reply.get("id", "")
                        caption = reply.get("title", "")
                    else:
                        text = f"[interactive:{int_type}]"
                elif msg_type == "location":
                    text = "[מיקום]"
                else:
                    text = f"[{msg_type}]"

                print(f"Incoming from {phone} ({name}): {text[:80]}")
                messages.append({
                    "phone": phone, "name": name, "text": text,
                    "type": msg_type, "timestamp": timestamp,
                    "message_id": msg.get("id", ""),
                    "media_id": media_id, "caption": caption,
                })
    return messages


def mark_as_read(message_id):
    """Mark a message as read (blue checkmarks)."""
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    requests.post(_api_url(), json=payload, headers=_headers())


def main():
    print("=" * 60)
    print("  takt-bots WhatsApp tool - Meta Cloud API")
    print("=" * 60)
    if not validate_config():
        sys.exit(1)
    print(f"Phone Number ID: {_phone_number_id()}")
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python whatsapp_bot.py send <phone> <message>")
        print("  python whatsapp_bot.py template <phone> <template_name>")
        sys.exit(1)
    command, phone = sys.argv[1], sys.argv[2]
    if command == "send":
        text = sys.argv[3] if len(sys.argv) > 3 else "שלום מ-takt-bots!"
        try:
            result = send_message(phone, text)
            print(f"OK: {json.dumps(result, indent=2)}")
        except requests.exceptions.HTTPError as e:
            print(f"Error: HTTP {e.response.status_code}\nResponse: {e.response.text}")
    elif command == "template":
        template_name = sys.argv[3] if len(sys.argv) > 3 else "hello_world"
        try:
            result = send_template(phone, template_name, language="en_US")
            print(f"OK: {json.dumps(result, indent=2)}")
        except requests.exceptions.HTTPError as e:
            print(f"Error: HTTP {e.response.status_code}\nResponse: {e.response.text}")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
