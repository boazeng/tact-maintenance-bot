"""
Application settings.

Secrets and shared config are read from the SHARED env file
(C:\\Users\\User\\Aiprojects\\env\\.env) via the shared_env module, then surfaced
here through pydantic-settings. `extra=ignore` so the many unrelated keys in the
shared env file don't raise validation errors.
"""

import sys
import os

# Make the repo root importable (database / agents / tools / shared_env) regardless
# of where uvicorn is launched from.
_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import shared_env  # noqa: E402  (import side-effect: loads shared env into os.environ)
from shared_env import shared_env_path  # noqa: E402

from pydantic_settings import BaseSettings, SettingsConfigDict  # noqa: E402


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(shared_env_path()),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # AI script generation
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    # Storage backend selector (sqlite | dynamodb)
    storage_backend: str = "sqlite"

    # Server
    api_port: int = 8020
    cors_origins: str = "http://localhost:5210,http://localhost:5173,http://127.0.0.1:5210"

    @property
    def cors_list(self):
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
