#!/usr/bin/env python
"""Thin UserPromptSubmit hook wrapper for zmem MVP-0.

Not installed by this task. It reads hook JSON from stdin and prints L0+L1.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ZMEM = ROOT / "zmem.py"


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def prompt_from_payload(payload: dict[str, Any]) -> str:
    for key in ("prompt", "user_prompt", "text"):
        if payload.get(key):
            return str(payload[key])
    message = payload.get("message")
    if isinstance(message, dict) and message.get("content"):
        return str(message["content"])
    return ""


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {"prompt": raw}
    frame = {
        "prompt": prompt_from_payload(payload),
        "intents": _list(payload.get("intents")),
        "keywords": _list(payload.get("keywords")),
        "paths": _list(payload.get("paths")),
        "symbols": _list(payload.get("symbols")),
        "domains": _list(payload.get("domains")),
        "claims": _list(payload.get("claims")),
        "phase": str(payload.get("phase", "")),
    }
    cmd = [
        sys.executable,
        str(ZMEM),
        "context",
        "--require-index",
        "--enrich-frame",
        "--layers",
        "L0,L1",
        "--format",
        "text",
        "--log",
        str(ROOT / "logs" / "activation_decisions.jsonl"),
        "--frame-json",
        json.dumps(frame, ensure_ascii=False),
    ]
    result = subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)
    if result.returncode != 0:
        print(f"zmem UserPromptSubmit skipped: {result.stderr.strip()}", file=sys.stderr)
        return 0
    print(result.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
