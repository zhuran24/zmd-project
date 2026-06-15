#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from cc_context.memory_system.cli import main  # noqa: E402  (路径注入后才能 import)

if __name__ == "__main__":
    raise SystemExit(main())
