"""
DynamoDB backend for bot conversation scripts (mirrors bot_scripts_db API).

Table: BOT_SCRIPTS_TABLE env var (default "takt-bots-scripts").
  PK: script_id (String)

Not active by default — selected only when STORAGE_BACKEND=dynamodb. Requires
boto3 and AWS credentials (from the shared env / IAM role).
"""

import os
import json
import time
import logging
from datetime import datetime
from decimal import Decimal

import boto3

logger = logging.getLogger("taktbots.dynamodb.scripts")

_dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
TABLE_NAME = os.environ.get("BOT_SCRIPTS_TABLE", "takt-bots-scripts")
_table = _dynamodb.Table(TABLE_NAME)

_cache = {}
CACHE_TTL_SECONDS = 300
_JSON_FIELDS = ("steps", "done_actions", "_flow_positions")


def get_script(script_id, use_cache=True):
    if use_cache:
        cached = _cache.get(script_id)
        if cached and (time.time() - cached["fetched_at"]) < CACHE_TTL_SECONDS:
            return cached["data"]
    resp = _table.get_item(Key={"script_id": script_id})
    item = resp.get("Item")
    if item:
        data = _deserialize_item(item)
        _cache[script_id] = {"data": data, "fetched_at": time.time()}
        return data
    return None


def save_script(script_data):
    now = datetime.utcnow().isoformat() + "Z"
    script_data["updated_at"] = now
    if not script_data.get("created_at"):
        script_data["created_at"] = now
    _table.put_item(Item=_prepare_item(script_data))
    sid = script_data["script_id"]
    _cache.pop(sid, None)
    logger.info(f"Script saved: {sid}")
    return {"script_id": sid}


def list_scripts():
    resp = _table.scan()
    return [_deserialize_item(i) for i in resp.get("Items", [])]


def delete_script(script_id):
    _table.delete_item(Key={"script_id": script_id})
    _cache.pop(script_id, None)
    logger.info(f"Script deleted: {script_id}")


def invalidate_cache(script_id=None):
    if script_id:
        _cache.pop(script_id, None)
    else:
        _cache.clear()


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
                try:
                    fixed = v.replace("'", '"').replace("True", "true").replace("False", "false").replace("None", "null")
                    data[k] = json.loads(fixed)
                except Exception:
                    data[k] = v
        elif isinstance(v, Decimal):
            data[k] = int(v) if v == int(v) else float(v)
        else:
            data[k] = v
    return data
