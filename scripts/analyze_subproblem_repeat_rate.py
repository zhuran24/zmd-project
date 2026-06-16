#!/usr/bin/env python
"""Phase 3C P1 #12 — aggregate subproblem repeat-rate spike data.

Usage (after a 24h campaign run with EXACT_SUBPROBLEM_REPEAT_PROBE=1):

    python scripts/analyze_subproblem_repeat_rate.py

Reads `data/telemetry/subproblem_repeat_<pid>.jsonl` files (one per
worker process), takes the LAST summary line per pid (latest snapshot),
aggregates across pids, and prints global repeat rate per kind.

Decision rule per audit a36d33351616095f1: if cross-pid aggregate
repeat_rate < 15%, KILL the cache-trio idea (P1 #12 main body).
Otherwise GO with caveats.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TELEMETRY_DIR = PROJECT_ROOT / "data" / "telemetry"
DECISION_THRESHOLD = 0.15


def load_latest_summaries(telemetry_dir: Path) -> List[Dict[str, Any]]:
    """For each pid file, return the last (most recent) JSONL record."""
    pattern = "subproblem_repeat_*.jsonl"
    summaries: List[Dict[str, Any]] = []
    for path in sorted(telemetry_dir.glob(pattern)):
        try:
            lines = [
                line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
            ]
        except OSError as exc:
            print(f"WARN: cannot read {path}: {exc}", file=sys.stderr)
            continue
        if not lines:
            continue
        try:
            summaries.append(json.loads(lines[-1]))
        except json.JSONDecodeError as exc:
            print(f"WARN: malformed last line in {path}: {exc}", file=sys.stderr)
    return summaries


def aggregate(summaries: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """Aggregate across pids: sum totals; unique requires set-merge but we
    can only see hashes' totals per pid, so unique here is conservatively
    the sum-of-uniques (an upper bound). Real cross-pid dedup needs the
    raw hash list per record, which we don't keep — so document the
    upper-bound interpretation."""
    by_kind: Dict[str, Dict[str, float]] = {}
    for rec in summaries:
        for kind, info in rec.get("summary", {}).items():
            slot = by_kind.setdefault(
                kind, {"total": 0, "unique_upper": 0, "max_repeats": 0}
            )
            slot["total"] += int(info.get("total", 0))
            slot["unique_upper"] += int(info.get("unique", 0))
            slot["max_repeats"] = max(
                slot["max_repeats"], int(info.get("max_repeats", 0))
            )
    for kind, slot in by_kind.items():
        total = slot["total"]
        slot["repeat_rate_lower_bound"] = (
            (1.0 - slot["unique_upper"] / total) if total > 0 else 0.0
        )
    return by_kind


def render(aggregate_data: Dict[str, Dict[str, float]], num_pids: int) -> str:
    lines = [
        "=" * 60,
        f"P1 #12 cache-trio spike — repeat rate aggregation ({num_pids} pid(s))",
        "=" * 60,
        "",
    ]
    if not aggregate_data:
        lines.append("No data — was EXACT_SUBPROBLEM_REPEAT_PROBE=1 set during the run?")
        return "\n".join(lines)
    for kind, slot in aggregate_data.items():
        rate = slot["repeat_rate_lower_bound"]
        lines.append(f"  [{kind}]")
        lines.append(f"    total invocations          : {slot['total']}")
        lines.append(f"    unique hashes (upper bound): {slot['unique_upper']}")
        lines.append(f"    max repeats (single key)    : {slot['max_repeats']}")
        lines.append(f"    repeat_rate (LOWER bound)   : {rate:.4f} ({rate*100:.2f}%)")
        decision = (
            "GO (cache trio worth investigating)"
            if rate >= DECISION_THRESHOLD
            else "KILL (cache trio not worth — gated threshold 15%)"
        )
        lines.append(f"    decision                    : {decision}")
        lines.append("")
    lines.append("=" * 60)
    lines.append(
        "Note: repeat_rate is a LOWER bound — cross-pid hash dedup not done"
    )
    lines.append("      (would only INCREASE the rate). If lower bound already")
    lines.append("      passes 15%, decision is robust.")
    lines.append("=" * 60)
    return "\n".join(lines)


def main() -> int:
    telemetry_dir = DEFAULT_TELEMETRY_DIR
    if len(sys.argv) > 1:
        telemetry_dir = Path(sys.argv[1])
    if not telemetry_dir.exists():
        print(f"telemetry dir does not exist: {telemetry_dir}", file=sys.stderr)
        return 2
    summaries = load_latest_summaries(telemetry_dir)
    aggregate_data = aggregate(summaries)
    print(render(aggregate_data, len(summaries)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
