"""
DynamoDB backend for conversation sessions (mirrors troubleshoot_sessions_db API).

Table: TROUBLESHOOT_SESSIONS_TABLE env var (default "takt-bots-sessions").
  PK: phone (String) ; TTL: expires_at (Number, epoch seconds)

Not active by default — selected only when STORAGE_BACKEND=dynamodb.
"""

import os
import json
import time
import logging
from datetime import datetime
from decimal import Decimal

import boto3

logger = logging.getLogger("taktbots.dynamodb.sessions")

_dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
TABLE_NAME = os.environ.get("TROUBLESHOOT_SESSIONS_TABLE", "takt-bots-sessions")
_table = _dynamodb.Table(TABLE_NAME)

_JSON_FIELDS = ("llm_result", "parsed_data", "skipped_steps", "session_log")


def save_session(session_data):
    _table.put_item(Item=_prepare_item(session_data))
    logger.info(f"Session saved for {session_data['phone']}, step={session_data.get('step')}")


def get_session(phone):
    resp = _table.get_item(Key={"phone": phone})
    item = resp.get("Item")
    return _deserialize_item(item) if item else None


def update_session(phone, session_data):
    _table.put_item(Item=_prepare_item(session_data))
    logger.info(f"Session updated for {phone}, step={session_data.get('step')}")


def update_session_step(phone, new_step):
    _table.update_item(
        Key={"phone": phone},
        UpdateExpression="SET step = :s, updated_at = :now",
        ExpressionAttributeValues={
            ":s": new_step,
            ":now": datetime.utcnow().isoformat() + "Z",
        },
    )


def delete_session(phone):
    _table.delete_item(Key={"phone": phone})
    logger.info(f"Session deleted for {phone}")


def list_sessions(limit=50):
    resp = _table.scan()
    sessions = [_deserialize_item(i) for i in resp.get("Items", [])]
    sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return sessions[:limit]


def extend_session_ttl(phone, days=7):
    new_ttl = int(time.time()) + days * 86400
    _table.update_item(
        Key={"phone": phone},
        UpdateExpression="SET expires_at = :ttl",
        ExpressionAttributeValues={":ttl": new_ttl},
    )


def _prepare_item(data):
    item = {}
    for k, v in data.items():
        if isinstance(v, (dict, list)):
            item[k] = json.dumps(v, ensure_ascii=False)
        elif isinstance(v, bool):
            item[k] = v
        elif isinstance(v, float):
            item[k] = Decimal(str(v))
        elif isinstance(v, int):
            item[k] = v
        else:
            item[k] = v
    return item


def _deserialize_item(item):
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
