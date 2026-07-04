"""
seed_dynamodb — push the local (SQLite) bot scripts + prompts into the deployed
DynamoDB tables, so the cloud stack starts with the real content.

Reads from the local SQLite backend and writes through the DynamoDB backend.
AWS creds + region come from the shared env (boto3 default chain).

Run after `sam deploy`, from the repo root with the backend venv:
    backend\.venv\Scripts\python.exe seed_dynamodb.py [stage]     (default stage: prod)
"""
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import shared_env  # noqa: F401  — loads AWS creds + region

STAGE = sys.argv[1] if len(sys.argv) > 1 else "prod"
# The stack lives in us-east-1; force it (the shared env may set another region).
os.environ["AWS_REGION"] = os.environ.get("TAKT_DEPLOY_REGION", "us-east-1")
os.environ["BOT_SCRIPTS_TABLE"] = f"takt-bots-scripts-{STAGE}"
os.environ["BOT_PROMPTS_TABLE"] = f"takt-bots-prompts-{STAGE}"


def main():
    from database.backends.sqlite import scripts as sqlite_scripts
    from database.backends.sqlite import prompts as sqlite_prompts
    from database.backends.dynamodb import scripts as dynamo_scripts
    from database.backends.dynamodb import prompts as dynamo_prompts

    scripts = sqlite_scripts.list_scripts()
    print(f"scripts: {len(scripts)} local -> DynamoDB ({os.environ['BOT_SCRIPTS_TABLE']})")
    for s in scripts:
        dynamo_scripts.save_script(s)
        print(f"  + {s.get('script_id')} ({s.get('name', '')})")

    prompts = sqlite_prompts.list_prompts()
    print(f"prompts: {len(prompts)} local -> DynamoDB ({os.environ['BOT_PROMPTS_TABLE']})")
    for p in prompts:
        dynamo_prompts.save_prompt(p)
        print(f"  + {p.get('prompt_id')}")

    print("done.")


if __name__ == "__main__":
    main()
