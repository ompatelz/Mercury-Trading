"""Small, safe operator CLI for local Mercury development."""

from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from typing import Any

from app.core.config import get_settings


def doctor() -> dict[str, Any]:
    settings = get_settings()
    data_root = settings.data_storage_root
    native_available = _native_available()
    return {
        "execution_mode": {"status": "ok", "value": settings.execution_mode},
        "database": {
            "status": "configured",
            "value": _redact_database_url(settings.database_url),
        },
        "queue": {"status": "ok", "detail": "PostgreSQL campaign queue; Redis is not required"},
        "worker": {"status": "ok", "command": "python scripts/run_worker.py"},
        "native_extension": {"status": "ok" if native_available else "unavailable"},
        "data_directory": {
            "status": "ok" if data_root.exists() else "missing",
            "path": str(data_root),
        },
        "model_routing": {"status": "ok", "policy": settings.routing_policy},
    }


def _native_available() -> bool:
    try:
        importlib.import_module("app.backtesting.native._engine")
    except ModuleNotFoundError:
        return False
    return True


def _redact_database_url(value: str) -> str:
    if "@" not in value or "://" not in value:
        return "configured"
    scheme, remainder = value.split("://", 1)
    credentials, host = remainder.rsplit("@", 1)
    username = credentials.split(":", 1)[0]
    return f"{scheme}://{username}:[REDACTED]@{host}"


def main() -> None:
    parser = argparse.ArgumentParser(prog="mercury", description="Mercury developer tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor_parser = subparsers.add_parser("doctor", help="show local configuration readiness")
    doctor_parser.add_argument("--json", action="store_true", help="render JSON")
    demo_parser = subparsers.add_parser("demo", help="show or run the canonical offline mission")
    demo_parser.add_argument(
        "--run", action="store_true", help="run the deterministic mission test"
    )
    args = parser.parse_args()

    if args.command == "doctor":
        report = doctor()
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            for name, result in report.items():
                print(f"{name}: {result['status']}")
        return
    if args.run:
        raise SystemExit(
            subprocess.run(
                [sys.executable, "-m", "pytest", "tests/integration/test_end_to_end_mission.py"],
                check=False,
            ).returncode
        )
    print(
        "Canonical offline mission: python -m pytest tests/integration/test_end_to_end_mission.py"
    )
