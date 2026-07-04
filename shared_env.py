"""
shared_env — single source of truth for locating and loading environment variables.

All takt-bots projects read secrets (WhatsApp tokens, Anthropic/OpenAI keys, AWS
credentials) from the SHARED env file at C:\\Users\\User\\Aiprojects\\env\\.env so
nothing is duplicated per project. Override the location with TAKT_SHARED_ENV.

Importing this module (or calling load_shared_env()) is idempotent.
"""

import os
from pathlib import Path

DEFAULT_SHARED_ENV = Path(r"C:\Users\User\Aiprojects\env\.env")

_loaded = False


def shared_env_path():
    """Return the resolved path to the shared .env file."""
    override = os.environ.get("TAKT_SHARED_ENV")
    return Path(override) if override else DEFAULT_SHARED_ENV


def load_shared_env(override=False):
    """Load the shared .env into os.environ. Safe to call multiple times.

    Args:
        override: when True, values in the file overwrite existing env vars.
    """
    global _loaded
    if _loaded and not override:
        return
    path = shared_env_path()
    if path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(path, override=override)
        except ImportError:
            _load_manual(path, override)
    _loaded = True


def _load_manual(path, override):
    """Minimal .env parser fallback when python-dotenv is unavailable."""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and (override or key not in os.environ):
            os.environ[key] = value


# Load eagerly on import so any module importing this gets a populated environment.
load_shared_env()
