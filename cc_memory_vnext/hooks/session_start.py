#!/usr/bin/env python
"""Thin SessionStart hook wrapper for zmem MVP-0.

Not installed by this task. It prints only L0 context.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ZMEM = ROOT / "zmem.py"


def main() -> int:
    frame = {
        "prompt": "",
        "intents": ["session-start"],
        "keywords": [],
        "paths": [],
        "symbols": [],
        "domains": [],
    }
    cmd = [
        sys.executable,
        str(ZMEM),
        "context",
        "--require-index",
        "--layers",
        "L0",
        "--format",
        "text",
        "--frame-json",
        json.dumps(frame, ensure_ascii=False),
    ]
    result = subprocess.run(cmd, cwd=str(ROOT.parent), text=True, capture_output=True)
    if result.returncode != 0:
        print(f"zmem SessionStart skipped: {result.stderr.strip()}", file=sys.stderr)
        return 0
    print(result.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
