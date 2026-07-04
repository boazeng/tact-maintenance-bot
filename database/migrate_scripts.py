"""
migrate_scripts — copy bot scripts from a source DynamoDB table into the local
(SQLite) storage backend.

Used to pull the real urbangroup scripts into the standalone app so you start
with actual content (full step flows + saved node positions) instead of just the
demo seed. Run from the repo root with the backend venv:

    backend\\.venv\\Scripts\\python.exe database\\migrate_scripts.py
    # custom source:
    backend\\.venv\\Scripts\\python.exe database\\migrate_scripts.py <table> <region>

Reads secrets/credentials from the shared env (AWS_* via boto3's default chain).
Writes through the SQLite backend regardless of STORAGE_BACKEND.
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import shared_env  # noqa: F401  (loads shared env / AWS creds)

import boto3
from decimal import Decimal

from database.backends.sqlite import scripts as local_scripts

DEFAULT_TABLE = "urbangroup-bot-scripts-prod"
DEFAULT_REGION = "us-east-1"
_JSON_FIELDS = ("steps", "done_actions", "_flow_positions")


def _deserialize(item):
    """DynamoDB item -> plain Python dict (JSON fields parsed, Decimals normalized)."""
    data = {}
    for k, v in item.items():
        if isinstance(v, str) and k in _JSON_FIELDS:
            try:
                data[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                data[k] = v
        elif isinstance(v, Decimal):
            data[k] = int(v) if v == int(v) else float(v)
        else:
            data[k] = v
    return data


def migrate(table_name=DEFAULT_TABLE, region=DEFAULT_REGION):
    table = boto3.resource("dynamodb", region_name=region).Table(table_name)
    items = table.scan().get("Items", [])
    print(f"Source {table_name} ({region}): {len(items)} scripts")

    migrated = 0
    for item in items:
        script = _deserialize(item)
        sid = script.get("script_id")
        if not sid:
            continue
        n_steps = len(script.get("steps", []))
        has_pos = bool(script.get("_flow_positions"))
        local_scripts.save_script(script)
        local_scripts.invalidate_cache(sid)
        print(f"  ✓ {sid} | {script.get('name','')} | steps={n_steps} | positions={'yes' if has_pos else 'no'}")
        migrated += 1

    print(f"Done. Imported {migrated} script(s) into local SQLite.")
    return migrated


if __name__ == "__main__":
    tbl = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TABLE
    rgn = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_REGION
    migrate(tbl, rgn)
