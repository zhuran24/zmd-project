#!/usr/bin/env python3
"""Install repository-native Git hooks.

Git does not track `.git/hooks`, so fresh clones need one explicit setup step.
This script points `core.hooksPath` at the tracked `.githooks/` directory. Hooks
are local convenience only; CI and `scripts/preflight_gate.py` remain the source
of truth.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / ".githooks"


def main() -> int:
    if not (REPO_ROOT / ".git").exists():
        print("not a git checkout; no hooks installed")
        return 2
    if not HOOKS_DIR.exists():
        print("tracked hook directory missing: .githooks")
        return 1
    subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=REPO_ROOT, check=True)
    print("git hooks installed: core.hooksPath=.githooks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
