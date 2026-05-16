from __future__ import annotations

import json
import sys
from typing import Any


def python_command(payload: Any = "", exit_code: int = 0) -> list[str]:
    rendered = payload if isinstance(payload, str) else json.dumps(payload)
    script = (
        "import sys;"
        f"sys.stdout.write({rendered!r});"
        f"sys.exit({int(exit_code)})"
    )
    return [sys.executable, "-c", script]


def tool_config(
    output: Any = None,
    *,
    exit_code: int = 0,
    stdin_json: bool = False,
) -> dict[str, Any]:
    if output is None:
        output = {"ok": True}
    return {
        "command": python_command(output, exit_code=exit_code),
        "stdin_json": stdin_json,
    }


def suite_config(
    total: int,
    *,
    passed: int | None = None,
    failed: int | None = None,
    skipped: int = 0,
    exit_code: int | None = None,
    error: str = "",
) -> dict[str, Any]:
    if passed is None:
        passed = total if failed in (None, 0) else 0
    if failed is None:
        failed = max(total - passed - skipped, 0)
    if exit_code is None:
        exit_code = 0 if failed == 0 else 1

    payload = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
    }
    if error:
        payload["error"] = error

    return {
        "command": python_command(payload, exit_code=exit_code),
        "result_format": "json",
    }


def device_config(
    *,
    pass_rate: float = 1.0,
    exit_code: int = 0,
    error: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {"pass_rate": pass_rate}
    if error:
        payload["error"] = error
    return {
        "command": python_command(payload, exit_code=exit_code),
        "result_format": "json",
    }
