#!/usr/bin/env python3
"""Claude Code hook trigger layer for the cc_memory backstop.

The meeting design (2026-06-19, recorded as entry
`cc-memory-hook-4-a-i-gpu-posttooluse-async`) is a 3-layer架构:

  (1) Claude hook = trigger ONLY (this file). It never duplicates maintenance logic.
  (2) `mem.py finalize` = the single收口本体 (lease -> GPU rebuild -> check -> export
      -> record state). All real work lives there.
  (3) git pre-commit + CI = the hard gate.

This script is the layer-(1) trigger. Two modes:

  post-tool  (wire to PostToolUse, async + asyncRewake):
      After a tool that ran a *mutating* `mem.py` command, run `mem.py finalize`
      (GPU rebuild + check + export) in the background. finalize is idempotent and
      lease-guarded, so concurrent triggers collapse to one drain. Exit codes are
      mapped so a STRUCTURAL inconsistency wakes the model (asyncRewake exit 2),
      while a GPU degrade is logged (exit 1) and surfaced at next boot.

  stop  (wire to Stop — Stop CANNOT be async, so this stays light & sync):
      A soft turn-exit reminder. NO GPU, NO red-judging check. Just reads cheap
      counters; if memory was mutated but not finalized, or high-score relation
      suggestions await review, it blocks the stop (exit 2) with a one-line nudge.

Any unexpected failure -> exit 0, so a flaky hook never wedges the session.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEM = HERE.parent / "mem.py"
DB = HERE.parent / "memory.db"

# Subcommands that change the store. Reads (boot/search/read/impact/relations/check/
# export/suggest) and the maintenance commands themselves (finalize/rebuild-embeddings)
# are intentionally excluded so finalize can never re-trigger finalize.
MUTATING = ("add-event", "set-fact", "add-entry", "link", "propose", "review-relation", "init")
# Anchor the subcommand as the first non-global-arg token after `mem.py`, so a read like
# `mem.py read some-link-node` can't false-match the `link` subcommand. The global-arg
# value matcher tolerates QUOTED values containing spaces (e.g. this host's own
# `--db "C:/claude pj/zmd-pj/cc_memory/memory.db"`); a bare `\S+` there would break the
# whole match and silently skip the backstop for any spaced --db/--export path.
# The only global flags that can precede the subcommand are --db/--export/--session, and
# all three REQUIRE a value, so the value is non-optional here. That disambiguates
# `--session add-entry read foo` (value == a subcommand name) — add-entry is consumed as
# the value, leaving the real subcommand `read` to (correctly) not match.
_MUTATION_RE = re.compile(
    r"mem\.py['\"]?\s+(?:--\w[\w-]*[=\s]+(?:\"[^\"]*\"|'[^']*'|[^\s\"']+)\s+)*?("
    + "|".join(MUTATING)
    + r")\b"
)


def _stdin_json() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def _load_mem():
    spec = importlib.util.spec_from_file_location("_ccmem_hook", MEM)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def do_post_tool(data: dict) -> int:
    command = ""
    tool_input = data.get("tool_input")
    if isinstance(tool_input, dict):
        command = str(tool_input.get("command") or "")
    if "mem.py" not in command or not _MUTATION_RE.search(command):
        return 0  # not a memory mutation -> nothing to finalize

    if not MEM.exists():
        return 0
    try:
        proc = subprocess.run(
            [sys.executable, str(MEM), "--db", str(DB), "finalize"],
            capture_output=True,
            text=True,
            timeout=880,  # > finalize's own --gpu-timeout (700), < the settings.json hook timeout (900)
        )
    except subprocess.TimeoutExpired:
        print("cc_memory finalize timed out (GPU rebuild stuck?)", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"cc_memory finalize could not start: {exc}", file=sys.stderr)
        return 0

    if proc.returncode == 2:
        # Structural inconsistency. asyncRewake surfaces stderr to the model.
        tail = (proc.stdout or "").strip().splitlines()[-12:]
        print("cc_memory finalize found an inconsistency that needs fixing:", file=sys.stderr)
        print("\n".join(tail), file=sys.stderr)
        if proc.stderr.strip():
            print(proc.stderr.strip(), file=sys.stderr)
        return 2
    if proc.returncode == 1:
        # GPU degrade — logged only; boot surfaces it, embeddings catch up later.
        print("cc_memory finalize: embeddings degraded (GPU unavailable?) — surfaced at next boot", file=sys.stderr)
        return 1
    return 0


def do_stop(data: dict) -> int:
    if data.get("stop_hook_active"):
        return 0  # already forced a continue ~8x; let the turn end to avoid a loop
    if not DB.exists() or not MEM.exists():
        return 0
    sid = str(data.get("session_id") or "")
    try:
        mem = _load_mem()
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        last_fin = int(mem.get_meta(con, "last_finalized_mutation_id", "0") or 0)
        # Scope "mutated but not finalized" to THIS session — a concurrent session's
        # in-flight writes are finalized by that session's own hooks, so nagging about
        # them here would be cross-talk. pending review / last-finalize-fail stay global.
        # When the session id is unknown (mem.py recorded 'anonymous' / no
        # $CLAUDE_CODE_SESSION_ID), fall back to a GLOBAL unfinalized count so the nag
        # isn't silently disabled.
        if sid:
            my_unfinalized = con.execute(
                "SELECT COUNT(*) AS n FROM mutations WHERE id>? AND session_id=?",
                (last_fin, sid),
            ).fetchone()["n"]
        else:
            my_unfinalized = con.execute(
                "SELECT COUNT(*) AS n FROM mutations WHERE id>?",
                (last_fin,),
            ).fetchone()["n"]
        pending = len(mem.pending_relation_suggestions(con))
        last_status = mem.get_meta(con, "last_finalize_status", "")
    except Exception:
        return 0  # never block a turn on a hook read error

    problems = []
    if my_unfinalized:
        problems.append(f"{my_unfinalized} memory change(s) this session not finalized")
    if pending:
        problems.append(f"{pending} relation suggestion(s) await review")
    if last_status.startswith("check_fail") or last_status.startswith("degraded"):
        problems.append(f"last finalize: {last_status}")
    if not problems:
        return 0

    print(
        "cc_memory backstop — " + "; ".join(problems)
        + ". Run `python cc_memory/mem.py finalize` (and `relations` to review) before ending the turn.",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else ""
    data = _stdin_json()
    if mode == "post-tool":
        return do_post_tool(data)
    if mode == "stop":
        return do_stop(data)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except SystemExit:
        raise
    except Exception:
        # A trigger layer must never crash the session.
        raise SystemExit(0)
