"""Phase 3C P1 #12 — subproblem invocation repeat-rate spike instrument.

Goal: 24h campaign run with `EXACT_SUBPROBLEM_REPEAT_PROBE=1` to measure
how often the same binding/routing input recurs. If repeat rate < 15%,
the cache-trio idea (P1 #12) gets killed per audit `a36d33351616095f1`.

Design (kept intentionally minimal):
- env-gated: nothing happens unless `EXACT_SUBPROBLEM_REPEAT_PROBE=1`
- per-process Counter (workers each get their own; aggregation is
  offline via scripts/analyze_subproblem_repeat_rate.py)
- periodic JSONL append to data/telemetry/subproblem_repeat_<pid>.jsonl
- thread-safe (CP-SAT internals are single-threaded per LBBDController
  but parallel_processes uses subprocesses so contention is per-pid)
- key = blake2b-16 over canonical JSON of the input mapping
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


def _is_enabled() -> bool:
    return os.environ.get(
        "EXACT_SUBPROBLEM_REPEAT_PROBE", ""
    ).strip().lower() in {"1", "true", "yes", "on"}


class SubproblemInvocationCounter:
    """Per-process counter; offline-aggregated."""

    def __init__(
        self,
        *,
        log_path: Optional[Path] = None,
        dump_interval_seconds: float = 300.0,
    ) -> None:
        self._lock = threading.Lock()
        self._counts: Dict[str, "Counter[str]"] = {}
        self._log_path = log_path
        self._dump_interval = float(dump_interval_seconds)
        self._last_dump = time.monotonic()

    def record(self, kind: str, key: Mapping[str, Any]) -> None:
        if not _is_enabled():
            return
        key_hash = self._hash_key(key)
        with self._lock:
            counter = self._counts.setdefault(kind, Counter())
            counter[key_hash] += 1
            if (
                self._log_path is not None
                and time.monotonic() - self._last_dump >= self._dump_interval
            ):
                self._dump_locked()
                self._last_dump = time.monotonic()

    @staticmethod
    def _hash_key(key: Mapping[str, Any]) -> str:
        canonical = json.dumps(key, sort_keys=True, default=str)
        return hashlib.blake2b(canonical.encode("utf-8"), digest_size=16).hexdigest()

    @staticmethod
    def _summary_for_counter(counter: "Counter[str]") -> Dict[str, Any]:
        total = sum(counter.values())
        unique = len(counter)
        return {
            "total": total,
            "unique": unique,
            "repeat_rate": (1.0 - unique / total) if total > 0 else 0.0,
            "max_repeats": max(counter.values()) if counter else 0,
        }

    def summary(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {
                kind: self._summary_for_counter(counter)
                for kind, counter in self._counts.items()
            }

    def _dump_locked(self) -> None:
        assert self._log_path is not None
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "timestamp": time.time(),
                "pid": os.getpid(),
                "summary": {
                    kind: self._summary_for_counter(counter)
                    for kind, counter in self._counts.items()
                },
            }
            with self._log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except OSError:
            # Telemetry failures must never break the campaign.
            pass

    def dump_now(self) -> None:
        if self._log_path is None:
            return
        with self._lock:
            self._dump_locked()


_GLOBAL_COUNTER: Optional[SubproblemInvocationCounter] = None
_GLOBAL_LOCK = threading.Lock()


def get_global_counter() -> SubproblemInvocationCounter:
    """Lazy-init a process-local counter writing to data/telemetry."""
    global _GLOBAL_COUNTER
    with _GLOBAL_LOCK:
        if _GLOBAL_COUNTER is None:
            log_dir = Path(
                os.environ.get(
                    "EXACT_SUBPROBLEM_REPEAT_LOG_DIR",
                    "data/telemetry",
                )
            )
            log_path = log_dir / f"subproblem_repeat_{os.getpid()}.jsonl"
            _GLOBAL_COUNTER = SubproblemInvocationCounter(log_path=log_path)
        return _GLOBAL_COUNTER


def record(kind: str, key: Mapping[str, Any]) -> None:
    """Module-level convenience: record an invocation if the probe is enabled.

    No-op when env unset (zero overhead path checks env every call —
    cheap enough for solver loop, but callers can pre-check is_enabled()
    if they want to short-circuit key construction).
    """
    if not _is_enabled():
        return
    get_global_counter().record(kind, key)


def is_enabled() -> bool:
    return _is_enabled()
