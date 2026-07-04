"""
integrations — optional, pluggable external integrations for the bot engine.

The standalone platform runs GENERIC, data-driven scripts out of the box. The
urbangroup-specific integrations (Priority ERP equipment lookup, service-call
writer, and the LLM service-call identifier) are NOT bundled here. They are
exposed through getters that return None unless explicitly enabled AND a real
implementation module is importable.

When a getter returns None the engine degrades gracefully:
  - check_equipment / check_open_service_call action steps take their on_failure exit
  - save_service_call done actions persist to the local DB without an external push

Enable a real integration by setting its feature flag and making its module
importable on sys.path:
  EQUIPMENT_READER_ENABLED=true      provider module exposing
                                     fetch_equipment_by_phone(phone) -> list,
                                     fetch_equipment_by_sernum(sernum) -> dict|None
                                     (module path: BOT_EQUIPMENT_READER_MODULE)
  SERVICE_CALL_WRITER_ENABLED=true   provider module exposing
                                     create_service_call(data) -> {"DOCNO": ...},
                                     find_open_service_calls(device) -> list,
                                     append_note_to_service_call(docno, note) -> None
                                     (module path: BOT_SERVICE_CALL_WRITER_MODULE)
  LLM_IDENTIFIER_ENABLED=true        provider module exposing
                                     process(msg_type, text, media_id, caption) -> dict
                                     (module path: BOT_LLM_IDENTIFIER_MODULE)
"""

import os
import importlib
import logging

logger = logging.getLogger("taktbots.integrations")

_equipment_reader = None
_service_call_writer = None
_llm = None


def _flag(name):
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _try_import(module_path):
    if not module_path:
        return None
    try:
        return importlib.import_module(module_path)
    except Exception as e:
        logger.warning(f"Integration module '{module_path}' could not be imported: {e}")
        return None


def get_equipment_reader():
    """Return the equipment-reader provider module, or None when disabled/unavailable."""
    global _equipment_reader
    if not _flag("EQUIPMENT_READER_ENABLED"):
        return None
    if _equipment_reader is None:
        _equipment_reader = _try_import(os.environ.get("BOT_EQUIPMENT_READER_MODULE", ""))
    return _equipment_reader


def get_service_call_writer():
    """Return the service-call-writer provider module, or None when disabled/unavailable."""
    global _service_call_writer
    if not _flag("SERVICE_CALL_WRITER_ENABLED"):
        return None
    if _service_call_writer is None:
        _service_call_writer = _try_import(os.environ.get("BOT_SERVICE_CALL_WRITER_MODULE", ""))
    return _service_call_writer


def get_llm():
    """Return the LLM service-call-identifier provider module, or None when disabled/unavailable."""
    global _llm
    if not _flag("LLM_IDENTIFIER_ENABLED"):
        return None
    if _llm is None:
        _llm = _try_import(os.environ.get("BOT_LLM_IDENTIFIER_MODULE", ""))
    return _llm
