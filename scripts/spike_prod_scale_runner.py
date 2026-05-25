#!/usr/bin/env python3
"""Prod-scale spike runner — main entry.

Per ``docs/research/prod_scale_spike_design_20260525/MERGER.md`` §5 shrink scope.

Phases:
- A1 (this script): off-limits enforce report
- A2 (this script): failfast probe (G17 ≤ 15s, 50 inst subset toy master)
- A3 (this script): real oracle real emit fixture (≥45 cert, 9 family)
- B  (separate agent): toy translator + scale ramp + feasible smoke + filter +
     telemetry + verdict

Outputs: ``data/cuts/spike/*.jsonl`` (sandboxed).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow running from repo root without install
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.spike_prod_scale_lib import off_limits_check  # noqa: E402


SPIKE_OUTPUT_DIR = REPO_ROOT / "data" / "cuts" / "spike"


def run_a1_off_limits(base_ref: str = "master") -> int:
    print("=" * 70)
    print("A1. off-limits enforce")
    print("=" * 70)
    violations = off_limits_check.check_off_limits(base_ref, "HEAD")
    print(off_limits_check.format_report(violations, base_ref, "HEAD"))
    return 0 if not violations else 1


def run_a2_failfast_probe(timeout_s: float = 15.0, instance_count: int = 50) -> int:
    from scripts.spike_prod_scale_lib import failfast_probe
    print("=" * 70)
    print("A2. failfast probe (G17)")
    print("=" * 70)
    report = failfast_probe.run_probe(
        instance_count=instance_count,
        timeout_s=timeout_s,
    )
    print(report.format_human())
    return 0 if report.passed else 1


def run_a3_oracle_emit_fixture(target_per_family: int = 5) -> int:
    from scripts.spike_prod_scale_lib import oracle_emit_fixture
    print("=" * 70)
    print("A3. real oracle real-emit fixture")
    print("=" * 70)
    SPIKE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SPIKE_OUTPUT_DIR / "oracle_emit_fixture_45cert.jsonl"
    report = oracle_emit_fixture.run_emit(
        target_per_family=target_per_family,
        out_path=out_path,
    )
    print(report.format_human())
    return 0 if report.passed else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Prod-scale spike runner (Phase A only).")
    ap.add_argument("--phase", default="a1,a2,a3",
                    help="Comma-separated subset of {a1,a2,a3}. Default: all of Phase A.")
    ap.add_argument("--base-ref", default="master", help="A1 git base ref.")
    ap.add_argument("--probe-timeout", type=float, default=15.0, help="A2 G17 timeout seconds.")
    ap.add_argument("--probe-instances", type=int, default=50, help="A2 subset inst count.")
    ap.add_argument("--cert-per-family", type=int, default=5, help="A3 per-family cert count.")
    args = ap.parse_args()

    phases = {p.strip().lower() for p in args.phase.split(",") if p.strip()}
    overall_rc = 0
    t0 = time.monotonic()
    for phase in ("a1", "a2", "a3"):
        if phase not in phases:
            continue
        if phase == "a1":
            rc = run_a1_off_limits(args.base_ref)
        elif phase == "a2":
            rc = run_a2_failfast_probe(args.probe_timeout, args.probe_instances)
        elif phase == "a3":
            rc = run_a3_oracle_emit_fixture(args.cert_per_family)
        else:
            rc = 0
        overall_rc = overall_rc or rc
        print()

    print(f"Phase A total wall: {time.monotonic() - t0:.1f}s, rc={overall_rc}")
    return overall_rc


if __name__ == "__main__":
    sys.exit(main())
