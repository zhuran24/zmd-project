#!/usr/bin/env python
"""SessionStart hook wrapper for zmem: prints the L0 context packet.

Wired in `.claude/settings.local.json` (see `hooks/WIRING.template.json` for the
tracked copy of that wiring). Like its UserPromptSubmit sibling it is
unconditionally fail-open — any error means "inject nothing and exit 0" — but as
of 2026-08-08 it is no longer *silent* about it. Every failure exit now leaves:

* one `!! MEMORY RECALL OFF: <reason>` line on stdout, so a dead injection
  channel stops being indistinguishable from a session that simply had no L0
  cards to push;
* one `{"event": "recall_failure", ...}` record in the activation log.

Three failure paths reach that announcement, and all three were unguarded
before: the child process failing to launch or hanging (there was no timeout at
all), the child exiting non-zero, and this wrapper itself raising (there was no
top-level net, so `print` blowing up under an ASCII-only locale exited 1 with
nothing said).

Pinned by `tests/test_recall_failure_visibility.py`, which runs this file as a
real subprocess against a stand-in `zmem.py`.
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ZMEM = ROOT / "zmem.py"
ACTIVATION_LOG = ROOT / "logs" / "activation_decisions.jsonl"

HOOK_NAME = "SessionStart"

# Same literal the UserPromptSubmit hook uses; tests and readers key off it.
RECALL_OFF_PREFIX = "!! MEMORY RECALL OFF"

# Wall-clock budget for the zmem child. The settings entry allows 30s, so this
# stays under it: a child killed by the harness tells us nothing, a child killed
# here prints the OFF line. Env override exists purely so the tests can exercise
# the real timeout path in well under a second.
ZMEM_TIMEOUT_SECONDS = 25.0
ZMEM_TIMEOUT_ENV = "ZMEM_SESSION_START_TIMEOUT_SECONDS"


def _timeout_seconds() -> float:
    raw = os.environ.get(ZMEM_TIMEOUT_ENV, "")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return ZMEM_TIMEOUT_SECONDS
    return value if value > 0 else ZMEM_TIMEOUT_SECONDS


def _encodable(stream: Any, text: str) -> str:
    """Fold `text` into whatever `stream` can actually encode.

    Under `LC_ALL=C` / `PYTHONIOENCODING=ascii` every Chinese card title in the
    packet would otherwise raise `UnicodeEncodeError` out of `print`.
    """
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
        return text
    except LookupError:
        return text.encode("ascii", errors="replace").decode("ascii")
    except (UnicodeEncodeError, UnicodeError):
        return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def _write(stream: Any, text: str) -> None:
    if not text:
        return
    try:
        stream.write(_encodable(stream, text) + "\n")
        stream.flush()
    except Exception:
        # Closed/broken stdout is still not a reason to fail a session start.
        return


def _one_line(text: str, limit: int = 240) -> str:
    """Squash anything into one bounded line; the OFF line must stay one line."""
    collapsed = " ".join(str(text).split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3] + "..."


def _append_activation_record(record: dict[str, Any]) -> bool:
    """Append one JSON line to the activation log, swallowing every failure.

    Deliberately a copy of `zmem.append_jsonl`'s contract rather than an import
    of it — see the same note in `user_prompt_submit.py`: a hook whose job is to
    stay audible when zmem is broken must not depend on importing zmem, nor on a
    shared sibling module whose absence would kill both hooks at import time.
    """
    try:
        ACTIVATION_LOG.parent.mkdir(parents=True, exist_ok=True)
        with ACTIVATION_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def recall_off(reason: str) -> None:
    """Announce that this session start got no memory packet, and record why.

    stdout first, log second, on purpose: an unwritable log must not be able to
    take the visible line with it. Pure ASCII so it survives `LC_ALL=C`.
    """
    detail = _one_line(reason) or "unknown failure"
    _write(
        sys.stdout,
        f"{RECALL_OFF_PREFIX}: {detail}; no memory packet was injected at session start "
        "(the !! STALE INDEX check is off too). "
        "Diagnose: python cc_memory_vnext/zmem.py verify",
    )
    _append_activation_record(
        {
            "event": "recall_failure",
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "hook": HOOK_NAME,
            "reason": detail,
        }
    )


def run_zmem(cmd: list[str], timeout: float | None = None) -> subprocess.CompletedProcess[str] | None:
    """Run the zmem child; `None` means "could not be run to completion".

    Same family as the UserPromptSubmit sibling: missing/non-executable
    interpreter and `E2BIG` (`OSError`), a bad argv shape (`ValueError`), and a
    child that hangs past the budget (`subprocess.TimeoutExpired`).
    """
    try:
        return subprocess.run(
            cmd,
            cwd=str(ROOT.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_timeout_seconds() if timeout is None else timeout,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _run() -> int:
    frame = {
        "prompt": "",
        "intents": ["session-start"],
        "keywords": [],
        "paths": [],
        "symbols": [],
        "domains": [],
    }
    cmd = [
        sys.executable,
        str(ZMEM),
        "context",
        "--require-index",
        "--layers",
        "L0",
        "--format",
        "text",
        "--log",
        str(ACTIVATION_LOG),
        "--frame-json",
        json.dumps(frame, ensure_ascii=False),
    ]
    result = run_zmem(cmd)
    if result is None:
        _write(sys.stderr, "zmem SessionStart skipped: zmem child could not be run")
        recall_off("zmem child could not be run (missing interpreter, bad argv, or it hung past the timeout)")
        return 0
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        _write(sys.stderr, f"zmem SessionStart skipped: {stderr}")
        recall_off(f"zmem exited {result.returncode}: {stderr or 'no stderr'}")
        return 0
    _write(sys.stdout, (result.stdout or "").strip())
    return 0


def main() -> int:
    try:
        return _run()
    except BaseException as exc:  # noqa: BLE001 - fail-open is this hook's entire contract
        try:
            recall_off(f"the {HOOK_NAME} hook itself raised {type(exc).__name__}: {exc}")
        except BaseException:
            pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
