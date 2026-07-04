"""
DynamoDB backend for LLM system prompts (mirrors bot_prompts_db API).

Table: BOT_PROMPTS_TABLE env var (default "takt-bots-prompts"). PK: prompt_id.
Not active by default — selected only when STORAGE_BACKEND=dynamodb.
"""

import os
import json
import time
import logging
from datetime import datetime
from decimal import Decimal

import boto3

logger = logging.getLogger("taktbots.dynamodb.prompts")

_dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
TABLE_NAME = os.environ.get("BOT_PROMPTS_TABLE", "takt-bots-prompts")
_table = _dynamodb.Table(TABLE_NAME)

_cache = {}
CACHE_TTL_SECONDS = 300


def get_active_prompt(use_cache=True):
    if use_cache:
        cached = _cache.get("active")
        if cached and (time.time() - cached["fetched_at"]) < CACHE_TTL_SECONDS:
            return cached["data"]
    resp = _table.scan(
        FilterExpression="active = :val",
        ExpressionAttributeValues={":val": True},
    )
    items = resp.get("Items", [])
    if items:
        data = _deserialize_item(items[0])
        _cache["active"] = {"data": data, "fetched_at": time.time()}
        return data
    return None


def get_prompt(prompt_id, use_cache=True):
    if use_cache:
        cached = _cache.get(prompt_id)
        if cached and (time.time() - cached["fetched_at"]) < CACHE_TTL_SECONDS:
            return cached["data"]
    resp = _table.get_item(Key={"prompt_id": prompt_id})
    item = resp.get("Item")
    if item:
        data = _deserialize_item(item)
        _cache[prompt_id] = {"data": data, "fetched_at": time.time()}
        return data
    return None


def save_prompt(prompt_data):
    now = datetime.utcnow().isoformat() + "Z"
    prompt_data["updated_at"] = now
    if not prompt_data.get("created_at"):
        prompt_data["created_at"] = now
    _table.put_item(Item=_prepare_item(prompt_data))
    pid = prompt_data["prompt_id"]
    _cache.pop(pid, None)
    _cache.pop("active", None)
    logger.info(f"Prompt saved: {pid}")
    return {"prompt_id": pid}


def list_prompts():
    resp = _table.scan()
    return [_deserialize_item(i) for i in resp.get("Items", [])]


def invalidate_cache(prompt_id=None):
    if prompt_id:
        _cache.pop(prompt_id, None)
        _cache.pop("active", None)
    else:
        _cache.clear()


def _prepare_item(data):
    item = {}
    for k, v in data.items():
        if isinstance(v, bool):
            item[k] = v
        elif isinstance(v, (dict, list)):
            item[k] = json.dumps(v, ensure_ascii=False)
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
        if isinstance(v, Decimal):
            data[k] = int(v) if v == int(v) else float(v)
        else:
            data[k] = v
    return data
