"""
build_lambda — assemble a clean AWS Lambda deployment package in build/lambda/.

Copies only the runtime code (backend/agents/database/tools + shared_env +
lambda_handler) — never the frontend, .venv, node_modules, local DB or caches —
then installs the Python deps as **Linux** wheels so it runs on Lambda even when
built on Windows (no Docker needed).

Run from the repo root with the backend venv:
    backend\.venv\Scripts\python.exe build_lambda.py
Then:  sam build && sam deploy
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "build", "lambda")

CODE_DIRS = ["backend", "agents", "database", "tools"]
CODE_FILES = ["shared_env.py", "lambda_handler.py"]
IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "*.pyo", ".venv", "venv",
    "node_modules", "*.db", "*.db-journal", "*.ps1", "smoke_test.py",
    "requirements*.txt",
)


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    # 1. copy source (preserving package structure)
    for d in CODE_DIRS:
        shutil.copytree(os.path.join(ROOT, d), os.path.join(OUT, d), ignore=IGNORE)
    for f in CODE_FILES:
        shutil.copy2(os.path.join(ROOT, f), os.path.join(OUT, f))

    # backend/ must be an importable package for `from backend.app.main import app`
    init = os.path.join(OUT, "backend", "__init__.py")
    if not os.path.exists(init):
        open(init, "w").close()

    # 2. install Linux wheels for the runtime deps
    cmd = [
        sys.executable, "-m", "pip", "install",
        "-r", os.path.join(ROOT, "requirements-lambda.txt"),
        "--platform", "manylinux2014_x86_64",
        "--python-version", "3.13",
        "--implementation", "cp",
        "--only-binary=:all:",
        "--target", OUT,
        "--upgrade",
    ]
    print("pip:", " ".join(cmd[-8:]))
    subprocess.check_call(cmd)

    # 3. strip caches pip may have left
    for base, dirs, _ in os.walk(OUT):
        for dd in list(dirs):
            if dd in ("__pycache__",) or dd.endswith((".dist-info", ".egg-info")):
                shutil.rmtree(os.path.join(base, dd), ignore_errors=True)

    size = sum(os.path.getsize(os.path.join(b, f))
               for b, _, fs in os.walk(OUT) for f in fs) / (1024 * 1024)
    print(f"OK — build/lambda assembled ({size:.1f} MB)")


if __name__ == "__main__":
    main()
