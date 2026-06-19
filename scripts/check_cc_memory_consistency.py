#!/usr/bin/env python3
"""CI / pre-commit hard-gate check for cc_memory consistency (no GPU needed).

Layer (3) of the cc_memory hook backstop (meeting 2026-06-19, entry
`cc-memory-hook-4-a-i-gpu-posttooluse-async`): the Claude PostToolUse hook keeps the
live store finalized, but `--no-verify` and non-CC writers can bypass it, so the real
hard gate lives in CI / pre-commit. This script verifies the *committed* collaboration
memory is internally consistent and that its generated view is not stale:

  1. `mem.py check` passes — schema marker, edge integrity, no unreviewed high-score
     relation suggestions, no hard-dependency cycle, export size within budget.
  2. exports/MEMORY.md content-matches a fresh export of memory.db (the view is in sync
     with the source of truth).

Exit 0 = consistent; exit 1 = block. The first stdout line is a one-line summary so
preflight_gate.py can surface it. Pure SQLite — never loads the GPU embedding layer, so
it runs identically on a GPU-less CI runner.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEM = ROOT / "cc_memory" / "mem.py"
DB = ROOT / "cc_memory" / "memory.db"
EXPORT = ROOT / "cc_memory" / "exports" / "MEMORY.md"


def _norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def main() -> int:
    if not MEM.exists() or not DB.exists():
        print("cc_memory consistency: SKIP (mem.py or memory.db absent)")
        return 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "MEMORY.md"
        try:
            proc = subprocess.run(
                [sys.executable, str(MEM), "--db", str(DB), "--export", str(tmp), "check"],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            print("cc_memory consistency: mem.py check timed out (>120s)")
            return 1
        except OSError as exc:
            print(f"cc_memory consistency: could not run mem.py check: {exc}")
            return 1

        out_lines = (proc.stdout or "").strip().splitlines()
        err_lines = (proc.stderr or "").strip().splitlines()
        if proc.returncode != 0:
            errs = [ln for ln in out_lines if ln.startswith("ERROR")]
            head = errs[0] if errs else (out_lines[0] if out_lines else "non-zero exit")
            print(f"cc_memory consistency: mem.py check FAILED — {head}")
            for ln in (out_lines + err_lines)[-12:]:
                print(f"  {ln}")
            return 1

        if not EXPORT.exists():
            print("cc_memory consistency: exports/MEMORY.md missing — run `python cc_memory/mem.py export`")
            return 1
        if _norm(tmp.read_bytes()) != _norm(EXPORT.read_bytes()):
            print(
                "cc_memory consistency: exports/MEMORY.md is STALE vs memory.db — "
                "run `python cc_memory/mem.py export` and stage exports/MEMORY.md with memory.db"
            )
            return 1

    print("cc_memory consistency: OK (check passed, MEMORY.md in sync with memory.db)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
