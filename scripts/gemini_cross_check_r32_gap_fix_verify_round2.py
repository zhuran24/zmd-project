#!/usr/bin/env python3
"""Sanitized legacy Gemini cross-check entrypoint."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    script_name = Path(__file__).name
    if not os.environ.get("GEMINI_API_KEY"):
        print(f"{script_name}: set GEMINI_API_KEY before running this legacy helper.", file=sys.stderr)
        return 2
    print(f"{script_name}: legacy inline prompt was removed; create a fresh self-contained prompt first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
