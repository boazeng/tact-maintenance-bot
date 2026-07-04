"""
DynamoDB backend for messages + service-call records (mirrors maintenance_db API).

Tables: MESSAGES_TABLE (default "takt-bots-messages"),
        SERVICE_CALLS_TABLE (default "takt-bots-service-calls").
  PK: id (UUID). GSIs expected: status-created_at-index, phone-created_at-index.

Not active by default — selected only when STORAGE_BACKEND=dynamodb.
"""

import os
import uuid
import logging
from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger("taktbots.dynamodb.messages")

_dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))

MESSAGES_TABLE_NAME = os.environ.get("MESSAGES_TABLE", "takt-bots-messages")
_messages_table = _dynamodb.Table(MESSAGES_TABLE_NAME)

SERVICE_CALLS_TABLE_NAME = os.environ.get("SERVICE_CALLS_TABLE", "takt-bots-service-calls")
_service_calls_table = _dynamodb.Table(SERVICE_CALLS_TABLE_NAME)


def save_message(phone, name, text, msg_type="text", message_id="", parsed_data=None):
    now = datetime.utcnow().isoformat() + "Z"
    item_id = str(uuid.uuid4())
    item = {
        "id": item_id, "phone": phone, "name": name, "text": text,
        "msg_type": msg_type, "message_id": message_id, "status": "new",
        "created_at": now,
    }
    if parsed_data:
        item["parsed_data"] = parsed_data
    _messages_table.put_item(Item=item)
    logger.info(f"Saved message {item_id} from {phone}")
    return {"id": item_id}


def get_messages(status=None, limit=50):
    if status:
        resp = _messages_table.query(
            IndexName="status-created_at-index",
            KeyConditionExpression=Key("status").eq(status),
            ScanIndexForward=False, Limit=limit,
        )
    else:
        resp = _messages_table.scan(Limit=limit)
    items = resp.get("Items", [])
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items


def update_message_status(item_id, new_status):
    resp = _messages_table.update_item(
        Key={"id": item_id},
        UpdateExpression="SET #s = :status, updated_at = :now",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":status": new_status, ":now": datetime.utcnow().isoformat() + "Z",
        },
        ReturnValues="ALL_NEW",
    )
    return resp.get("Attributes", {})


def save_service_call(phone, name, issue_type, description, urgency,
                      location="", summary="", message_id="", media_id="",
                      source_type="whatsapp",
                      custname="", cdes="", sernum="", branchname="",
                      callstatuscode="", technicianlogin="",
                      contact_name="", fault_text="", internal_notes="",
                      breakstart="", partname="",
                      is_system_down=False):
    now = datetime.utcnow().isoformat() + "Z"
    item_id = str(uuid.uuid4())
    item = {
        "id": item_id, "phone": phone, "name": name, "issue_type": issue_type,
        "description": description, "urgency": urgency, "location": location or "",
        "summary": summary or "", "message_id": message_id, "media_id": media_id,
        "source_type": source_type, "status": "new", "created_at": now,
        "custname": custname or "99999", "cdes": cdes or name or "",
        "sernum": sernum or "", "branchname": branchname or "001",
        "callstatuscode": callstatuscode or "ממתין לאישור",
        "technicianlogin": technicianlogin or "", "contact_name": contact_name or "",
        "fault_text": fault_text or "", "internal_notes": internal_notes or "",
        "breakstart": breakstart or "", "partname": partname or "",
        "is_system_down": bool(is_system_down), "priority_pushed": False,
    }
    _service_calls_table.put_item(Item=item)
    logger.info(f"Saved service call {item_id}: {issue_type} ({urgency}) from {phone}")
    return {"id": item_id}


def get_service_calls(status=None, phone=None, limit=50):
    if status:
        resp = _service_calls_table.query(
            IndexName="status-created_at-index",
            KeyConditionExpression=Key("status").eq(status),
            ScanIndexForward=False, Limit=limit,
        )
    elif phone:
        resp = _service_calls_table.query(
            IndexName="phone-created_at-index",
            KeyConditionExpression=Key("phone").eq(phone),
            ScanIndexForward=False, Limit=limit,
        )
    else:
        items = []
        scan_kwargs = {}
        while len(items) < limit * 4:
            resp = _service_calls_table.scan(Limit=500, **scan_kwargs)
            items.extend(resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                break
            scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return items[:limit]
    items = resp.get("Items", [])
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items


def update_service_call_status(item_id, new_status):
    resp = _service_calls_table.update_item(
        Key={"id": item_id},
        UpdateExpression="SET #s = :status, updated_at = :now",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":status": new_status, ":now": datetime.utcnow().isoformat() + "Z",
        },
        ReturnValues="ALL_NEW",
    )
    return resp.get("Attributes", {})


def get_service_call(item_id):
    resp = _service_calls_table.get_item(Key={"id": item_id})
    return resp.get("Item")


def mark_service_call_pushed(item_id, callno=""):
    update_expr = "SET priority_pushed = :pushed, updated_at = :now"
    expr_values = {":pushed": True, ":now": datetime.utcnow().isoformat() + "Z"}
    if callno:
        update_expr += ", priority_callno = :callno"
        expr_values[":callno"] = callno
    resp = _service_calls_table.update_item(
        Key={"id": item_id}, UpdateExpression=update_expr,
        ExpressionAttributeValues=expr_values, ReturnValues="ALL_NEW",
    )
    return resp.get("Attributes", {})
