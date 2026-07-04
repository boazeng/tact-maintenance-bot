"""
AWS Lambda entry point — wraps the FastAPI app with Mangum (API Gateway v2 / HTTP API).

The same FastAPI app that runs locally under uvicorn is served here on Lambda.
Storage defaults to DynamoDB and secrets come from the function's environment
(injected by the SAM template), so no shared .env file is needed in the cloud.
"""
import os

os.environ.setdefault("IS_LAMBDA", "true")
os.environ.setdefault("STORAGE_BACKEND", "dynamodb")

from backend.app.main import app  # noqa: E402
from mangum import Mangum  # noqa: E402

# lifespan="off": skip ASGI startup/shutdown (the demo-seed) on every cold start.
_mangum = Mangum(app, lifespan="off")


def handler(event, context):
    """Strip the API Gateway stage prefix (e.g. /prod/api/health -> /api/health)
    so the routes defined as /api/... match. No-op when there is no stage prefix."""
    stage = (event.get("requestContext", {}) or {}).get("stage", "")
    if stage and stage != "$default":
        prefix = f"/{stage}"
        raw = event.get("rawPath", "") or ""
        if raw.startswith(prefix):
            event["rawPath"] = raw[len(prefix):] or "/"
            http = event.get("requestContext", {}).get("http", {})
            if isinstance(http, dict) and (http.get("path", "") or "").startswith(prefix):
                http["path"] = http["path"][len(prefix):] or "/"
    return _mangum(event, context)
