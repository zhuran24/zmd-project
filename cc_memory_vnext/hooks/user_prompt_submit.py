#!/usr/bin/env python
"""Thin UserPromptSubmit hook wrapper for zmem MVP-0.

Reads hook JSON from stdin and prints the L0+L1 packet. This hook IS wired in
`.claude/settings.local.json` and runs in front of every real prompt, so it is
unconditionally fail-open: **any** error means "inject nothing and exit 0",
never a blocked or delayed prompt. Concretely that means

* `main()` funnels through one `except BaseException -> return 0` net, so even a
  malformed payload shape or an encoding fault cannot turn into exit 1;
* stdin is read with `errors="replace"`, and JSON that parses to something other
  than an object (top-level array/string/number/bool/null) degrades to "the raw
  text is the prompt" instead of blowing up in `payload.get(...)`;
* the zmem child is bounded by a wall-clock timeout and its `OSError` family
  (missing interpreter, `E2BIG`, …) is caught, so a hung or unlaunchable child
  costs one stderr note;
* the child's output is decoded with `errors="replace"`, and everything written
  to stdout/stderr is first folded into whatever encoding the ambient locale
  gives us (an ASCII-only `LC_ALL=C` session gets `?`-substituted text, not a
  `UnicodeEncodeError`).

Those five paths are pinned by `tests/test_user_prompt_submit_machine_skip.py`,
which drives this file as a real CLI subprocess with hostile stdin, a hostile
environment and a hostile stand-in `zmem.py` — not by monkeypatching
`subprocess.run`, which is exactly what let the 2026-08-03 review find every one
of them still live.

Fail-open is kept, but as of 2026-08-08 it is no longer *silent*. Every one of
those exits now leaves two marks (`tests/test_recall_failure_visibility.py`):

* one `!! MEMORY RECALL OFF: <reason>` line on stdout — the packet is gone but
  this line takes its place, so "recall died" stops looking exactly like
  "nothing matched this prompt" (production zero-injection baseline is 32-37%,
  which is where every failure used to hide);
* one `{"event": "recall_failure", ...}` record appended to the activation log,
  so the rate is answerable afterwards instead of only noticeable live.

Neither can change the exit code: the stdout line goes out first, the log write
swallows everything, and both sit inside the same fail-open net.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ZMEM = ROOT / "zmem.py"
ACTIVATION_LOG = ROOT / "logs" / "activation_decisions.jsonl"

HOOK_NAME = "UserPromptSubmit"

# The visible half of the fail-open contract. Grep-stable literal: tests, the
# sibling SessionStart hook and anybody reading a transcript all key off it.
RECALL_OFF_PREFIX = "!! MEMORY RECALL OFF"

# Wall-clock budget for the zmem child. This hook sits directly in front of the
# user's prompt, so a child that hangs must cost a bounded pause and nothing
# else. Overridable via env purely so the fail-open tests can exercise the real
# timeout path in well under a second.
ZMEM_TIMEOUT_SECONDS = 20.0
ZMEM_TIMEOUT_ENV = "ZMEM_UPS_TIMEOUT_SECONDS"

# Prompts the harness generates for itself — subagent task notifications, slash
# command plumbing, system notices. Nobody reads a memory packet attached to
# those, and the 2026-08-03 usage census measured them as 56% of all UPS
# injections. Skipping them is a pure token/noise cut: recall for real user
# prompts is untouched, and skipping can only ever mean "inject nothing", which
# is the same fail-open direction the rest of this hook already takes.
#
# Each entry is (literal marker, regex character class the marker MUST be
# followed by). The terminator is the whole point: bare `startswith` also ate
# `<task-notifications> schema question`, `<local-commandment> wording question`
# and `[SYSTEM NOTIFICATIONAL] wording question` — real prompts a human could
# type, silently dropped with no output at all. The harness's own markers always
# continue with a structural character:
#   `[SYSTEM NOTIFICATION]` / `[SYSTEM NOTIFICATION - foo]` / `[SYSTEM NOTIFICATION foo]`
#   `<task-notification>` / `<task-notification attr=...>`
#   `<local-command-stdout>` / `<local-command-stderr>` / `<local-command-caveat>`
MACHINE_PROMPT_PREFIXES: tuple[tuple[str, str], ...] = (
    ("[SYSTEM NOTIFICATION", r"[ \-\]]"),
    ("<task-notification", r"[>\s]"),
    ("<local-command", r"[->]"),
)

_MACHINE_PROMPT_RE = re.compile(
    "|".join(
        f"(?:{re.escape(marker)}(?={terminator}))"
        for marker, terminator in MACHINE_PROMPT_PREFIXES
    )
)


def is_machine_prompt(prompt: str) -> bool:
    """True when the prompt opens with one of the harness's own machine markers.

    Two deliberate limits, stated plainly because neither is fixable here:

    1. The test is *structural only* — marker at the start, followed by the
       structural character the harness always emits. Nothing else is inspected.
       A prompt whose body merely quotes a marker still gets its packet, because
       the marker is not at the start.
    2. It cannot tell "the harness emitted this" from "the user's whole question
       is about this marker". `<task-notification> what does this tag mean?`
       opens with a genuine marker and is indistinguishable from a real
       notification by prefix alone. That prompt loses its memory packet. We
       accept it and stop here rather than bolting on heuristics (looking for a
       closing tag, sniffing for question words, …): the payoff is one packet on
       a rare prompt, and the cost of a wrong guess is the same silent drop in
       the far more common direction. Structural boundary, no cleverness.
    """
    return bool(_MACHINE_PROMPT_RE.match(prompt.lstrip()))


def _timeout_seconds() -> float:
    raw = os.environ.get(ZMEM_TIMEOUT_ENV, "")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return ZMEM_TIMEOUT_SECONDS
    return value if value > 0 else ZMEM_TIMEOUT_SECONDS


def _encodable(stream: Any, text: str) -> str:
    """Fold `text` into whatever `stream` can actually encode.

    Substituting up front (rather than letting `write` raise) matters: a
    half-written line is worse than a `?`-substituted one, and under
    `LC_ALL=C` / `PYTHONIOENCODING=ascii` every Chinese card title in the packet
    would otherwise raise `UnicodeEncodeError` out of `print`.
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
        # Closed/broken stdout is still not a reason to fail a prompt.
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
    of it: "zmem could not be imported / is broken" is one of the very failures
    this record exists to report, and this hook must stay importable with
    nothing but the standard library. Same reason the OFF-line helpers below are
    duplicated in `session_start.py` instead of shared through a sibling module
    — a shared module that goes missing takes both hooks down at *import* time,
    before any `except` in here can run.
    """
    try:
        ACTIVATION_LOG.parent.mkdir(parents=True, exist_ok=True)
        with ACTIVATION_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def recall_off(reason: str) -> None:
    """Announce that this turn got no memory packet, and record why.

    stdout first, log second, and on purpose: an unwritable log must not be able
    to take the visible line with it. Pure ASCII so it survives `LC_ALL=C`.
    """
    detail = _one_line(reason) or "unknown failure"
    _write(
        sys.stdout,
        f"{RECALL_OFF_PREFIX}: {detail}; no memory packet was injected this turn "
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


def _read_stdin() -> str:
    reconfigure = getattr(sys.stdin, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(errors="replace")
        except Exception:
            pass
    try:
        return sys.stdin.read()
    except Exception:
        buffer = getattr(sys.stdin, "buffer", None)
        if buffer is None:
            return ""
        try:
            return buffer.read().decode("utf-8", errors="replace")
        except Exception:
            return ""


def payload_from_raw(raw: str) -> dict[str, Any]:
    """Always hand back a mapping; never let stdin shape decide the exit code."""
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, RecursionError):
        return {"prompt": raw}
    if isinstance(parsed, dict):
        return parsed
    # Well-formed JSON that is not an object: `[]`, `"human"`, `0`, `false`,
    # `null`. Same treatment as unparseable stdin — the raw text becomes the
    # prompt — because the alternative was an AttributeError out of
    # `payload.get(...)` and a non-zero exit.
    return {"prompt": raw}


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def prompt_from_payload(payload: dict[str, Any]) -> str:
    for key in ("prompt", "user_prompt", "text"):
        if payload.get(key):
            return str(payload[key])
    message = payload.get("message")
    if isinstance(message, dict) and message.get("content"):
        return str(message["content"])
    return ""


def run_zmem(cmd: list[str], timeout: float | None = None) -> subprocess.CompletedProcess[str] | None:
    """Run the zmem child; `None` means "could not be run to completion".

    Covers the whole unlaunchable/unfinishable family in one place: missing or
    non-executable interpreter and `E2BIG` (`OSError`), a bad argv shape
    (`ValueError`), and a child that hangs past the budget
    (`subprocess.TimeoutExpired`, a `SubprocessError`).
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


def _run(payload: dict[str, Any]) -> int:
    prompt = prompt_from_payload(payload)
    if is_machine_prompt(prompt):
        return 0
    frame = {
        "prompt": prompt,
        "intents": _list(payload.get("intents")),
        "keywords": _list(payload.get("keywords")),
        "paths": _list(payload.get("paths")),
        "symbols": _list(payload.get("symbols")),
        "domains": _list(payload.get("domains")),
        "claims": _list(payload.get("claims")),
        "phase": str(payload.get("phase", "")),
    }
    cmd = [
        sys.executable,
        str(ZMEM),
        "context",
        "--require-index",
        "--enrich-frame",
        "--layers",
        "L0,L1",
        "--format",
        "text",
        "--log",
        str(ACTIVATION_LOG),
        "--frame-json",
        json.dumps(frame, ensure_ascii=False),
    ]
    result = run_zmem(cmd)
    if result is None:
        _write(sys.stderr, "zmem UserPromptSubmit skipped: zmem child could not be run")
        recall_off("zmem child could not be run (missing interpreter, bad argv, or it hung past the timeout)")
        return 0
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        _write(sys.stderr, f"zmem UserPromptSubmit skipped: {stderr}")
        recall_off(f"zmem exited {result.returncode}: {stderr or 'no stderr'}")
        return 0
    _write(sys.stdout, (result.stdout or "").strip())
    return 0


def main() -> int:
    try:
        return _run(payload_from_raw(_read_stdin()))
    except BaseException as exc:  # noqa: BLE001 - fail-open is this hook's entire contract
        # Deliberately wider than `Exception`: a hook that fails a prompt is
        # worse than a hook that injects nothing, whatever the cause. The OFF
        # line gets its own net because "the announcement of the failure also
        # failed" must still not cost a non-zero exit.
        try:
            recall_off(f"the {HOOK_NAME} hook itself raised {type(exc).__name__}: {exc}")
        except BaseException:
            pass
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
