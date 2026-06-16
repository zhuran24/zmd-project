#!/usr/bin/env python3
"""Check LF line endings for repo-native gates and hash-sensitive contracts."""
from __future__ import annotations

import fnmatch
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PROJECT_ROOT / "data" / "line_ending_policy.json"
SKIP_DIR_NAMES = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__"}


def tracked_files_or_walk() -> list[Path]:
    """Return tracked files when git is available, otherwise walk once.

    The first version walked the whole repository once per glob.  That was
    correct but made preflight latency scale as patterns × tree size.  The gate
    is about publishable repo-native files, so `git ls-files --cached --others`
    is the right fast path; the walk fallback keeps source archives without git
    metadata usable.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        result = None
    if result is not None and result.returncode == 0 and result.stdout:
        paths: list[Path] = []
        for raw in result.stdout.split(b"\0"):
            if not raw:
                continue
            rel = raw.decode("utf-8", errors="surrogateescape")
            path = PROJECT_ROOT / rel
            if path.is_file():
                paths.append(path)
        return sorted(paths)

    paths = []
    for path in PROJECT_ROOT.rglob("*"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.is_file():
            paths.append(path)
    return sorted(paths)


def iter_matches(pattern: str, candidates: list[Path]) -> list[Path]:
    matches: list[Path] = []
    for path in candidates:
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if fnmatch.fnmatch(rel, pattern):
            matches.append(path)
    return matches


def main() -> int:
    try:
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"line-ending policy check failed: {exc}", file=sys.stderr)
        return 2
    if policy.get("schema_version") != 1:
        print("line-ending policy check failed: schema_version must be 1", file=sys.stderr)
        return 2

    candidates = tracked_files_or_walk()
    checked = 0
    errors: list[str] = []
    seen: set[Path] = set()
    for pattern in policy.get("required_lf_globs", []):
        matches = iter_matches(str(pattern), candidates)
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
