#!/usr/bin/env python3
"""Check that tracked .artifacts entries are declared historical evidence."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "data" / "artifact_boundaries.json"


def git_ls_files(prefix: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", prefix],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"artifact boundary check failed: {exc}", file=sys.stderr)
        return 2
    if manifest.get("schema_version") != 1:
        print("artifact boundary check failed: schema_version must be 1", file=sys.stderr)
        return 2

    allowed = [str(item["path_prefix"]) for item in manifest.get("tracked_historical_evidence", [])]
    tracked = git_ls_files(".artifacts")
    undeclared = [path for path in tracked if not any(path.startswith(prefix) for prefix in allowed)]
    if undeclared:
        print("artifact boundary check failed: tracked .artifacts path(s) lack historical-evidence declaration")
        for path in undeclared[:50]:
            print(f"  - {path}")
        if len(undeclared) > 50:
            print(f"  ... {len(undeclared) - 50} more")
        return 1

    print(f"artifact boundary check passed: {len(tracked)} tracked .artifacts files declared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
