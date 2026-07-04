"""
deploy — build the Lambda package and deploy the takt-bots SAM stack to AWS.

Secrets are read from the SHARED env at deploy time and passed as CloudFormation
parameters (never stored in samconfig / git). Non-secret config uses template
defaults.

Run from the repo root with the backend venv:
    backend\.venv\Scripts\python.exe deploy.py
"""
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import shared_env  # noqa: F401  — loads shared env (secrets + AWS creds)

import build_lambda  # noqa: E402

# SAM parameter -> shared-env variable (only passed when non-empty)
PARAM_MAP = {
    "PriorityUrlDemo": "PRIORITY_URL_DEMO",
    "PriorityUrlReal": "PRIORITY_URL_REAL",
    "PriorityUsername": "PRIORITY_USERNAME",
    "PriorityPassword": "PRIORITY_PASSWORD",
    "ServiceCallUrl": "SERVICE_CALL_URL",
    "ServiceCallApiKey": "SERVICE_CALL_API_KEY",
    "TelegramBotToken": "TELEGRAM_BOT_TOKEN",
    "OpenAiApiKey": "OPENAI_API_KEY",
    "AnthropicApiKey": "ANTHROPIC_API_KEY",
    "WhatsAppPhoneNumberId": "WHATSAPP_PHONE_NUMBER_ID",
    "WhatsAppAccessToken": "WHATSAPP_ACCESS_TOKEN",
    "WhatsAppVerifyToken": "WHATSAPP_VERIFY_TOKEN",
}


def main():
    print(">> 1/2 - assembling Lambda package")
    build_lambda.main()

    overrides = []
    for param, env in PARAM_MAP.items():
        val = os.environ.get(env, "")
        if val:
            overrides.append(f"{param}={val}")

    print(f">> 2/2 - sam deploy ({len(overrides)} secret params)")
    cmd = ["sam", "deploy"]
    if overrides:
        cmd.append("--parameter-overrides")
        cmd.extend(overrides)
    print("running: sam deploy --parameter-overrides <%d params>" % len(overrides))
    # Run without check_call so a failure doesn't dump the secret-bearing cmd.
    rc = subprocess.call(cmd, cwd=ROOT)
    if rc != 0:
        print(f"\nsam deploy failed (exit {rc}). See the SAM output above.")
        sys.exit(rc)


if __name__ == "__main__":
    main()
