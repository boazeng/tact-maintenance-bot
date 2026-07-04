"""
maintenance_db — storage dispatcher for messages + service-call records.

Selects the backend via STORAGE_BACKEND env var (sqlite | dynamodb, default sqlite).
Public API: save_message, get_messages, update_message_status,
            save_service_call, get_service_calls, update_service_call_status,
            get_service_call, mark_service_call_pushed.
"""

import os

_BACKEND = os.environ.get("STORAGE_BACKEND", "sqlite").lower()

if _BACKEND == "dynamodb":
    from database.backends.dynamodb import messages as _impl
else:
    from database.backends.sqlite import messages as _impl

save_message = _impl.save_message
get_messages = _impl.get_messages
update_message_status = _impl.update_message_status
save_service_call = _impl.save_service_call
get_service_calls = _impl.get_service_calls
update_service_call_status = _impl.update_service_call_status
get_service_call = _impl.get_service_call
mark_service_call_pushed = _impl.mark_service_call_pushed
