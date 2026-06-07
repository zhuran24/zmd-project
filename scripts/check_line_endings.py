#!/usr/bin/env python3
"""Check LF line endings for repo-native gates and hash-sensitive contracts."""
from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "data" / "line_ending_policy.json"


def iter_matches(pattern: str) -> list[Path]:
    # pathlib glob does not support every gitignore-style pattern, but the
    # policy uses simple repo-relative globs. We match against tracked-like
    # existing files by walking once for predictable behavior across platforms.
    matches: list[Path] = []
    for path in PROJECT_ROOT.rglob("*"):
        if ".git" in path.parts:
            continue
        if path.is_file():
            rel = path.relative_to(PROJECT_ROOT).as_posix()
            if fnmatch.fnmatch(rel, pattern):
                matches.append(path)
    return sorted(matches)


def main() -> int:
    try:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"line-ending policy check failed: {exc}", file=sys.stderr)
        return 2
    if policy.get("schema_version") != 1:
        print("line-ending policy check failed: schema_version must be 1", file=sys.stderr)
        return 2

    checked = 0
    errors: list[str] = []
    seen: set[Path] = set()
    for pattern in policy.get("required_lf_globs", []):
        matches = iter_matches(str(pattern))
        if not matches:
            errors.append(f"required_lf_glob matched no files: {pattern}")
            continue
        for path in matches:
            if path in seen:
                continue
            seen.add(path)
            data = path.read_bytes()
            checked += 1
            if b"\r\n" in data or b"\r" in data.replace(b"\r\n", b""):
                errors.append(path.relative_to(PROJECT_ROOT).as_posix())

    if errors:
        print("line-ending policy check failed:")
        for rel in errors[:50]:
            print(f"  - {rel}")
        if len(errors) > 50:
            print(f"  ... {len(errors) - 50} more")
        return 1
    print(f"line-ending policy check passed: {checked} files checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
