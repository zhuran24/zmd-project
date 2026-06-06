#!/usr/bin/env python3
"""Sanitized legacy Gemini cross-check entrypoint.

This one-shot script previously carried a repository-stored credential. The
credential and prompt payload have been removed from the current publishable
repository tree. Use GEMINI_API_KEY from the environment and reconstruct a fresh,
self-contained review prompt before calling an external model again.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    script_name = Path(__file__).name
    if not os.environ.get("GEMINI_API_KEY"):
        print(
            f"{script_name}: GEMINI_API_KEY is required; no API key is stored in this repository.",
            file=sys.stderr,
        )
        return 2
    print(
        f"{script_name}: legacy one-shot prompt was sanitized. "
        "Create a fresh self-contained prompt before calling Gemini."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
