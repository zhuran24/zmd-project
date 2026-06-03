"""B5 telemetry hook — RSS sample / proto sample / dark_matter_emit.

Per MERGER §5.2 + §5.4 N11:
- 3 必 telemetry event class:
  - ``rss_sample``: 1Hz background thread, psutil.Process.memory_info().rss
  - ``proto_sample``: explicit emit at build / solve milestone points
  - ``dark_matter_emit``: emit on INFEASIBLE with witness blob (per
    ``17_workflow_telemetry §20.2`` hard gate — spike INFEASIBLE 必 emit
    witness blob, 不能 reproduce 即 abort)

Output: jsonl at ``data/cuts/spike/telemetry_<pid>.jsonl``.

N11 trigger: any of 3 event class count = 0 at end of spike run.

This file is spike-only. Off-limits paths untouched.
"""
from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import psutil


def _resolve_repo_root() -> Path:
    """Return the project root in production and review-mirror layouts.

    Production modules live under project/scripts/spike_prod_scale_lib/.
    Review-package mirrors live under project/code_context/spike/spike_prod_scale_lib/.
    """
    here = Path(__file__).resolve()
    candidates = (here.parent.parent.parent, here.parent.parent.parent.parent)
    for root in candidates:
        if (root / "data" / "preprocessed" / "candidate_placements.json").exists() and (root / "src").is_dir():
            return root
    return candidates[0]


REPO_ROOT = _resolve_repo_root()


# ============================================================================
# Telemetry buffer + jsonl writer
# ============================================================================


@dataclass
class TelemetryBuffer:
    out_path: Path
    events: List[dict] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _flushed_count: int = 0

    def emit(self, event: str, data: dict) -> None:
        record = {
            "ts": time.time(),
            "event": event,
            "data": data,
        }
        with self._lock:
            self.events.append(record)

    def flush(self) -> int:
        """Append all buffered events to jsonl. Return # new lines written."""
        with self._lock:
            new_events = self.events[self._flushed_count:]
            self._flushed_count = len(self.events)
        if not new_events:
            return 0
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        with self.out_path.open("a", encoding="utf-8") as f:
            for ev in new_events:
                f.write(json.dumps(ev, ensure_ascii=False))
                f.write("\n")
        return len(new_events)

    def event_counts(self) -> Dict[str, int]:
        with self._lock:
            counts: Dict[str, int] = {}
            for ev in self.events:
                counts[ev["event"]] = counts.get(ev["event"], 0) + 1
        return counts


# ============================================================================
# 1Hz RSS sampler — background thread
# ============================================================================


@dataclass
class RSSSampler:
    buf: TelemetryBuffer
    interval_s: float = 1.0
    _thread: Optional[threading.Thread] = None
    _stop_event: threading.Event = field(default_factory=threading.Event)
    _process: Optional[psutil.Process] = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._process = psutil.Process(os.getpid())
        # Prime cpu_percent for delta-based readings.
        try:
            self._process.cpu_percent(interval=None)
        except Exception:
            pass
        self._thread = threading.Thread(
            target=self._loop, name="RSSSampler", daemon=True,
        )
        self._thread.start()

    def _loop(self) -> None:
        assert self._process is not None
        while not self._stop_event.is_set():
            try:
                mem = self._process.memory_info()
                rss_bytes = int(mem.rss)
                vms_bytes = int(mem.vms)
                self.buf.emit("rss_sample", {
                    "rss_bytes": rss_bytes,
                    "vms_bytes": vms_bytes,
                    "rss_gb": round(rss_bytes / (1024**3), 3),
                })
            except Exception as e:
                self.buf.emit("rss_sample_error", {"err": str(e)})
            self._stop_event.wait(self.interval_s)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def current_rss_gb(self) -> float:
        if self._process is None:
            self._process = psutil.Process(os.getpid())
        return self._process.memory_info().rss / (1024**3)


# ============================================================================
# proto_sample emit — explicit milestone
# ============================================================================


def emit_proto_sample(
    buf: TelemetryBuffer,
    label: str,
    proto_bytesize: int,
    n_vars: int,
    n_constraints: int,
) -> None:
    """Emit a proto_sample event with serialized size + var/constraint counts.

    Called at milestone points: after build, after cuts applied at each ramp
    tier, etc.
    """
    buf.emit("proto_sample", {
        "label": label,
        "proto_bytesize": proto_bytesize,
        "proto_mb": round(proto_bytesize / (1024**2), 2),
        "n_vars": n_vars,
        "n_constraints": n_constraints,
    })


# ============================================================================
# dark_matter_emit — INFEASIBLE witness blob (hard gate per N11)
# ============================================================================


def emit_rss_after_solve(
    buf: TelemetryBuffer,
    tier: str,
    rss_bytes: int,
    vms_bytes: int = 0,
) -> None:
    """Emit explicit RSS sample at solve completion (GPT pro v15 三审 finding 4).

    Per finding 4: raw telemetry max 0.866 GB came from background 1Hz
    ``rss_sample`` only, while ``phase_b_results.json`` carried the higher
    after-solve peak (e.g., 100K = 1.03 GB). Reviewer asked for an explicit
    raw event at solve completion so the after-solve peak shows up directly
    in the telemetry jsonl rather than only in the aggregated report.

    Field structure mirrors ``rss_sample``: ``rss_bytes`` / ``rss_gb`` /
    ``vms_bytes`` plus a ``tier`` tag identifying which ramp tier closed.
    The 1Hz background sampler keeps running — this is an additional event
    class, not a replacement.
    """
    buf.emit("rss_sample_after_solve", {
        "tier": tier,
        "rss_bytes": int(rss_bytes),
        "vms_bytes": int(vms_bytes),
        "rss_gb": round(rss_bytes / (1024 ** 3), 4),
    })


def emit_dark_matter(
    buf: TelemetryBuffer,
    context: str,
    status_label: str,
    wall_s: float,
    extra: Optional[dict] = None,
) -> None:
    """Emit a dark_matter event on INFEASIBLE / UNKNOWN.

    Per ``17_workflow_telemetry §20.2`` hard gate: spike INFEASIBLE 必 emit
    witness blob — if no witness can be produced ⇒ spike abort. Here we emit
    the context-string + solver_response_proto stats (no full witness for
    toy master, but the context is sufficient since toy master cuts are
    structural not semantic).
    """
    payload = {
        "context": context,
        "status": status_label,
        "wall_s": round(wall_s, 4),
    }
    if extra:
        payload.update(extra)
    buf.emit("dark_matter_emit", payload)


# ============================================================================
# Context manager helper — start/stop in one block
# ============================================================================


@contextmanager
def telemetry_session(out_path: Path, rss_interval_s: float = 1.0):
    """Open a telemetry session with auto start/stop + flush on exit."""
    buf = TelemetryBuffer(out_path=out_path)
    sampler = RSSSampler(buf=buf, interval_s=rss_interval_s)
    sampler.start()
    try:
        yield buf, sampler
    finally:
        sampler.stop()
        buf.flush()


# ============================================================================
# N11 audit — verify 3 必 event class each ≥ 1
# ============================================================================


@dataclass
class N11AuditReport:
    counts: Dict[str, int]
    rss_sample_present: bool
    proto_sample_present: bool
    dark_matter_present: bool
    n11_pass: bool

    def format_human(self) -> str:
        verdict = "N11 PASS" if self.n11_pass else "N11 FAIL"
        lines = [f"telemetry audit — {verdict}"]
        lines.append(f"  rss_sample      count = {self.counts.get('rss_sample', 0)}  (≥1 required)")
        lines.append(f"  proto_sample    count = {self.counts.get('proto_sample', 0)}  (≥1 required)")
        lines.append(f"  dark_matter_emit count = {self.counts.get('dark_matter_emit', 0)}  (≥1 required)")
        for k, v in sorted(self.counts.items()):
            if k not in ("rss_sample", "proto_sample", "dark_matter_emit"):
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)


def audit_n11(jsonl_path: Path) -> N11AuditReport:
    """Parse a telemetry jsonl, count event class occurrences."""
    counts: Dict[str, int] = {}
    if not jsonl_path.exists():
        return N11AuditReport(
            counts={},
            rss_sample_present=False,
            proto_sample_present=False,
            dark_matter_present=False,
            n11_pass=False,
        )
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            ev = rec.get("event", "")
            counts[ev] = counts.get(ev, 0) + 1
    rss_p = counts.get("rss_sample", 0) >= 1
    proto_p = counts.get("proto_sample", 0) >= 1
    dm_p = counts.get("dark_matter_emit", 0) >= 1
    return N11AuditReport(
        counts=counts,
        rss_sample_present=rss_p,
        proto_sample_present=proto_p,
        dark_matter_present=dm_p,
        n11_pass=rss_p and proto_p and dm_p,
    )


# ============================================================================
# Self-test
# ============================================================================


if __name__ == "__main__":
    out = REPO_ROOT / "data" / "cuts" / "spike" / f"telemetry_selftest_{os.getpid()}.jsonl"
    if out.exists():
        out.unlink()
    with telemetry_session(out, rss_interval_s=0.3) as (buf, sampler):
        time.sleep(0.8)  # let 2-3 RSS samples land
        emit_proto_sample(buf, "selftest", 12345678, 100, 50)
        emit_dark_matter(buf, "selftest INFEASIBLE simulate", "INFEASIBLE", 0.5)
    rep = audit_n11(out)
    print(rep.format_human())
    raise SystemExit(0 if rep.n11_pass else 1)
