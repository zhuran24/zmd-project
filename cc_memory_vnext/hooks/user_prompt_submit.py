#!/usr/bin/env python
"""Thin UserPromptSubmit hook wrapper for zmem MVP-0.

Reads hook JSON from stdin and prints the L0+L1 packet. This hook IS wired in
`.claude/settings.local.json` and runs on every real prompt, so every failure
path here stays fail-open: any error means "print nothing", never a blocked
prompt (`zmem context` failing prints a note to stderr and exits 0).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ZMEM = ROOT / "zmem.py"

# Prompts the harness generates for itself — subagent task notifications, slash
# command plumbing, system notices. Nobody reads a memory packet attached to
# those, and the 2026-08-03 usage census measured them as 56% of all UPS
# injections. Skipping them is a pure token/noise cut: recall for real user
# prompts is untouched, and skipping can only ever mean "inject nothing", which
# is the same fail-open direction the rest of this hook already takes.
MACHINE_PROMPT_PREFIXES = (
    "[SYSTEM NOTIFICATION",
    "<task-notification",
    "<local-command",
)


def is_machine_prompt(prompt: str) -> bool:
    """True when the whole prompt is one of the harness's own machine messages.

    Anchored at the start on purpose: a user prompt that merely quotes one of
    these markers further in must still get its packet.
    """
    return prompt.lstrip().startswith(MACHINE_PROMPT_PREFIXES)


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
    prompt = prompt_from_payload(payload)
    if is_machine_prompt(prompt):
        return 0
    frame = {
        "prompt": prompt,
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
