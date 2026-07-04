"""seed — write the default demo script to storage on first run."""

from .state import logger, DEFAULT_SCRIPT_ID, _get_scripts_db


def seed_default_script():
    """Write the default maintenance-troubleshoot script to storage if it doesn't exist."""
    db = _get_scripts_db()
    existing = db.get_script(DEFAULT_SCRIPT_ID, use_cache=False)
    if existing:
        logger.info(f"[M10010] Default script already exists, skipping seed")
        return existing

    script = {
        "script_id": DEFAULT_SCRIPT_ID,
        "name": "תסריט אבחון תקלות",
        "active": True,
        "greeting_known": "שלום {customer_name}! כאן הבוט החכם של חברת האחזקה.",
        "greeting_unknown": "שלום! כאן הבוט החכם של חברת האחזקה.",
        "first_step": "GREETING",
        "steps": [
            {
                "id": "GREETING",
                "type": "buttons",
                "text": "מה תרצה לעשות?",
                "buttons": [
                    {
                        "id": "intent_fault",
                        "title": "לדווח על תקלה",
                        "next_step": "ASK_DEVICE",
                        "skip_if": {
                            "field": "device_number",
                            "not_empty": True,
                            "goto": "ASK_SYSTEM_DOWN",
                        },
                    },
                    {
                        "id": "intent_message",
                        "title": "להשאיר הודעה",
                        "next_step": "GET_MESSAGE",
                    },
                ],
            },
            {
                "id": "GET_MESSAGE",
                "type": "text_input",
                "text": "שלח את ההודעה שלך:",
                "save_to": "customer_message",
                "next_step": "DONE_MESSAGE",
            },
            {
                "id": "ASK_DEVICE",
                "type": "buttons",
                "text": "האם יש לך את מספר המכשיר/המתקן?",
                "buttons": [
                    {"id": "device_yes", "title": "כן, יש לי", "next_step": "DEVICE_INPUT"},
                    {"id": "device_no", "title": "לא", "next_step": "ASK_ADDRESS"},
                ],
            },
            {
                "id": "DEVICE_INPUT",
                "type": "text_input",
                "text": "שלח את מספר המכשיר/המתקן:",
                "save_to": "device_number",
                "next_step": "ASK_SYSTEM_DOWN",
            },
            {
                "id": "ASK_ADDRESS",
                "type": "text_input",
                "text": "באיזה כתובת נמצא המתקן?\n(נשתמש בכתובת כדי לאתר את המכשיר)",
                "save_to": "location",
                "next_step": "ASK_SYSTEM_DOWN",
            },
            {
                "id": "ASK_SYSTEM_DOWN",
                "type": "buttons",
                "text": "האם המערכת מושבתת?",
                "buttons": [
                    {
                        "id": "system_down_yes",
                        "title": "כן, מושבתת",
                        "next_step": "DESCRIBE_FAULT",
                        "save_to": "is_system_down",
                        "save_value": "yes",
                    },
                    {
                        "id": "system_down_no",
                        "title": "לא, פעילה",
                        "next_step": "DESCRIBE_FAULT",
                        "save_to": "is_system_down",
                        "save_value": "no",
                    },
                ],
            },
            {
                "id": "DESCRIBE_FAULT",
                "type": "text_input",
                "text": "תאר בקצרה את התקלה:",
                "save_to": "description",
                "next_step": "DONE_FAULT",
            },
        ],
        "done_actions": {
            "DONE_MESSAGE": {
                "text": "ההודעה התקבלה, תודה! נחזור אליך בהקדם.",
                "action": "save_message",
            },
            "DONE_FAULT": {
                "text": "נפתחה קריאת שירות! ניצור איתך קשר בהקדם. תודה!",
                "action": "save_service_call",
            },
        },
    }

    db.save_script(script)
    logger.info(f"[M10010] Default script seeded: {DEFAULT_SCRIPT_ID}")
    return script
