#!/usr/bin/env python3
"""P1 #24 cache trio throughput compare.

读 baseline + cache-trio campaign telemetry, 算 throughput (candidates/sec,
cuts/sec, wave/sec), 打表对比 + 算 delta%.

用法:
    python scripts/p1_24_throughput_compare.py \
        --baseline .artifacts/p1_24_validation/baseline_run \
        --cache-trio .artifacts/p1_24_validation/cache_trio_run
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_telemetry(run_dir: Path) -> dict:
    tel = run_dir / "exact_campaign_telemetry.json"
    if not tel.exists():
        return {"waves": [], "_missing": str(tel)}
    return json.loads(tel.read_text())


def _summarize(payload: dict) -> dict:
    waves = payload.get("waves") or []
    total_elapsed = 0.0
    candidates_resolved = 0
    cuts_generated = 0
    cuts_loaded = 0
    worker_crashes = 0
    peak_rss = 0
    outcome_totals: dict[str, int] = {}
    for w in waves:
        if not isinstance(w, dict):
            continue
        total_elapsed += float(w.get("elapsed_seconds") or 0.0)
        cr = w.get("candidate_results") or []
        candidates_resolved += len(cr) if isinstance(cr, list) else 0
        cuts_generated += int(w.get("generated_exact_safe_cut_count_sum") or 0)
        cuts_loaded += int(w.get("loaded_exact_safe_cut_count_sum") or 0)
        if "worker_crash" in str(w.get("failure_reason") or ""):
            worker_crashes += 1
        peak_rss = max(peak_rss, int(w.get("peak_rss_bytes_external_total") or 0))
        oc = w.get("outcome_counts") or {}
        if isinstance(oc, dict):
            for k, v in oc.items():
                outcome_totals[str(k)] = outcome_totals.get(str(k), 0) + int(v)
    cands_per_sec = candidates_resolved / total_elapsed if total_elapsed > 0 else 0.0
    cuts_per_sec = cuts_generated / total_elapsed if total_elapsed > 0 else 0.0
    return {
        "waves": len(waves),
        "elapsed_seconds": total_elapsed,
        "candidates_resolved": candidates_resolved,
        "cuts_generated": cuts_generated,
        "cuts_loaded": cuts_loaded,
        "worker_crashes": worker_crashes,
        "peak_rss_gib": peak_rss / (1024**3),
        "cands_per_sec": cands_per_sec,
        "cuts_per_sec": cuts_per_sec,
        "outcome_totals": outcome_totals,
    }


def _pct(a: float, b: float) -> str:
    if b == 0:
        return "n/a"
    return f"{(a - b) / b * 100:+.1f}%"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", required=True, type=Path)
    ap.add_argument("--cache-trio", required=True, type=Path)
    args = ap.parse_args()
    base_payload = _load_telemetry(args.baseline)
    trio_payload = _load_telemetry(args.cache_trio)
    base = _summarize(base_payload)
    trio = _summarize(trio_payload)
    fields = [
        ("waves", "{:d}"),
        ("elapsed_seconds", "{:.1f}"),
        ("candidates_resolved", "{:d}"),
        ("cuts_generated", "{:d}"),
        ("cuts_loaded", "{:d}"),
        ("worker_crashes", "{:d}"),
        ("peak_rss_gib", "{:.2f}"),
        ("cands_per_sec", "{:.4f}"),
        ("cuts_per_sec", "{:.4f}"),
    ]
    print(f"{'metric':<28}{'baseline':>14}{'cache-trio':>14}{'delta':>10}")
    print("-" * 66)
    for name, fmt in fields:
        b = base[name]
        t = trio[name]
        bs = fmt.format(b)
        ts = fmt.format(t)
        # delta% only for numerics where bigger=better (throughput) or smaller=better (rss/crashes)
        if name in ("cands_per_sec", "cuts_per_sec", "candidates_resolved", "cuts_generated"):
            delta = _pct(t, b)
        elif name in ("peak_rss_gib", "worker_crashes"):
            delta = _pct(t, b)
        else:
            delta = ""
        print(f"{name:<28}{bs:>14}{ts:>14}{delta:>10}")
    print()
    print("outcome_totals:")
    print(f"  baseline:   {base['outcome_totals']}")
    print(f"  cache-trio: {trio['outcome_totals']}")
    print()
    if base_payload.get("_missing"):
        print(f"WARN: baseline telemetry missing: {base_payload['_missing']}")
    if trio_payload.get("_missing"):
        print(f"WARN: cache-trio telemetry missing: {trio_payload['_missing']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
