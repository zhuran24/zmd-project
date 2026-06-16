#!/usr/bin/env python3
"""Install tracked Git hooks for local convenience.

GitHub Actions and `scripts/preflight_gate.py` remain the authoritative gates;
these hooks only make the same checks harder to forget on local commits.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOOKS_SRC = PROJECT_ROOT / ".githooks"
HOOKS_DST = PROJECT_ROOT / ".git" / "hooks"


def main() -> int:
    parser = argparse.ArgumentParser(description="Install tracked local Git hooks.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing hook files.")
    args = parser.parse_args()

    if not (PROJECT_ROOT / ".git").exists():
        print("not a git checkout; .git not found")
        return 1
    if not HOOKS_SRC.is_dir():
        print("tracked hook source missing: .githooks")
        return 1
    HOOKS_DST.mkdir(parents=True, exist_ok=True)

    installed = 0
    skipped = 0
    for source in sorted(HOOKS_SRC.iterdir()):
        if not source.is_file():
            continue
        destination = HOOKS_DST / source.name
        if destination.exists() and not args.force:
            print(f"skip existing hook: {destination.relative_to(PROJECT_ROOT)}")
            skipped += 1
            continue
        shutil.copy2(source, destination)
        mode = destination.stat().st_mode
        destination.chmod(mode | 0o111)
        installed += 1
        print(f"installed hook: {destination.relative_to(PROJECT_ROOT)}")

    print(f"git hook install complete: {installed} installed, {skipped} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
