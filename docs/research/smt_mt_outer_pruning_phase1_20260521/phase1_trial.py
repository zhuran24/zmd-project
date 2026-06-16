"""Phase 1 trial for SMT-MT outer pruning with REAL B1 LBBD inner solver.

Phase 0 (cheap gate, GO 8/8): Dummy inner mock measured monotone prune ratio
76.7% on 2.35M (w, h, anchor) candidates. Phase 1 wires the engine into
``outer_search.run_outer_search`` behind ``EXACT_SMT_MT_OUTER_PRUNING=1``
and measures real prune ratio with the production B1 pose-bool master +
LBBD inner loop.

This trial selects 5-10 candidates by size (mix of large-area expected
INFEASIBLE + medium-area expected CERTIFIED/UNPROVEN) and runs the real
inner solver. Telemetry is aggregated from
``.artifacts/smt_mt_outer_pruning/phase1_metrics_wave_*.json``.

Usage:
    .venv/bin/python -u docs/research/smt_mt_outer_pruning_phase1_20260521/phase1_trial.py \
        --max-candidates 10 --benders-max-iter 5
    # Dry-run: build engine, verify env wiring, do NOT run any inner.
    .venv/bin/python -u docs/research/smt_mt_outer_pruning_phase1_20260521/phase1_trial.py \
        --dry-run

env required for full run:
    EXACT_SMT_MT_OUTER_PRUNING=1
    EXACT_USE_POSE_BOOL_MASTER=1
    EXACT_OUTER_SKIP_UNKNOWN=1   # let UNKNOWN candidates not stop campaign

GO/NO-GO (Phase 1 thresholds):
    m1_real_prune_ratio >= 0.30
    m2_query_p95_real <= 1000 ms
    m3_total_outer_wall <= 1h
    m4_telemetry_correctness == True
    m5_env_off_regression == True (verified by pytest separately)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _resolve_candidate_pool() -> List[tuple]:
    """Return (area, w, h) triples to run real inner on.

    Mix of large area (>= 1000, expected INFEASIBLE -> trigger SMT-MT prune)
    + medium (400-900, expected UNPROVEN/CERTIFIED) + small (<=300, baseline).
    Curated to cover the m6_prune_by_area_bucket Phase 0 dominance signal.
    """
    return [
        # Large (m6 bucket >=1000): expect INFEASIBLE on tight ghost
        (2500, 50, 50),
        (1600, 40, 40),
        (1200, 30, 40),
        (1000, 25, 40),
        # Medium (500-999): borderline
        (700, 35, 20),
        (500, 25, 20),
        # Small (200-499): typically CERTIFIED or UNPROVEN
        (405, 27, 15),  # blueprint anchor — known interior probe
        (300, 20, 15),
        (240, 16, 15),
        (200, 20, 10),
    ]


def run_trial(
    *,
    max_candidates: int,
    benders_max_iter: int,
    master_seconds: float,
    binding_seconds: float,
    routing_seconds: float,
    flow_seconds: float,
    dry_run: bool,
    output_dir: Path,
) -> Dict[str, Any]:
    """Execute Phase 1 trial: build engine via outer_search hook + run real inner."""
    # Verify env wiring up front
    env_status = {
        "EXACT_SMT_MT_OUTER_PRUNING": os.environ.get("EXACT_SMT_MT_OUTER_PRUNING", ""),
        "EXACT_USE_POSE_BOOL_MASTER": os.environ.get("EXACT_USE_POSE_BOOL_MASTER", ""),
        "EXACT_OUTER_SKIP_UNKNOWN": os.environ.get("EXACT_OUTER_SKIP_UNKNOWN", ""),
    }
    print(f"[trial] env: {env_status}")

    from src.search import smt_mt_outer_pruning as smtmt
    from src.search.outer_search import generate_candidate_sizes

    pool = _resolve_candidate_pool()[:max_candidates]
    print(f"[trial] candidate pool ({len(pool)}):")
    for area, w, h in pool:
        print(f"  area={area:>5} w={w:>2} h={h:>2}")

    if dry_run:
        # Build engine standalone (not via outer_search), verify wiring.
        os.environ["EXACT_SMT_MT_OUTER_PRUNING"] = "1"
        engine = smtmt.maybe_build_engine(generate_candidate_sizes())
        print(f"[dry-run] engine built: {engine is not None}")
        print(f"[dry-run] metrics snapshot keys: {list(engine.metrics_snapshot().keys()) if engine else []}")
        # Simulate a single INFEASIBLE notification
        if engine is not None:
            newly = engine.notify_infeasible(50, 50)
            print(f"[dry-run] notify(50,50) newly pruned: {len(newly)} candidates")
            snapshot = engine.metrics_snapshot()
            print(f"[dry-run] real_prune_ratio: {snapshot['real_prune_ratio']:.4f}")
        # Write summary
        summary = {
            "dry_run": True,
            "env": env_status,
            "candidate_pool_size": len(pool),
            "engine_built": engine is not None,
            "note": "Skipped real inner solve. Use without --dry-run for full trial.",
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "phase1_trial_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n"
        )
        return summary

    # Full run: invoke outer_search with start_area capped to the largest in our pool
    # to keep the candidate set small and bounded.
    if env_status["EXACT_SMT_MT_OUTER_PRUNING"].strip().lower() not in {"1", "true", "yes", "on"}:
        raise RuntimeError(
            "EXACT_SMT_MT_OUTER_PRUNING must be set to 1 for full Phase 1 trial; "
            "use --dry-run to skip the real solve."
        )

    from src.search.outer_search import run_outer_search

    start_area = max(area for area, _w, _h in pool)
    print(f"[trial] start_area cap: {start_area}")
    t0 = time.perf_counter()
    status, result = run_outer_search(
        start_area=start_area,
        max_attempts=len(pool),
        master_seconds=master_seconds,
        binding_seconds=binding_seconds,
        routing_seconds=routing_seconds,
        flow_seconds=flow_seconds,
        benders_max_iter=benders_max_iter,
        campaign_hours=0.5,
        resume_campaign=False,
        parallel_processes=1,
        solve_mode="certified_exact",
    )
    outer_wall = time.perf_counter() - t0
    print(f"[trial] outer_search returned status={status} wall={outer_wall:.1f}s")

    # Aggregate engine telemetry from .artifacts
    telemetry_dir = PROJECT_ROOT / ".artifacts" / "smt_mt_outer_pruning"
    latest_metrics: Optional[Dict[str, Any]] = None
    if telemetry_dir.exists():
        wave_files = sorted(telemetry_dir.glob("phase1_metrics_wave_*.json"))
        if wave_files:
            latest_metrics = json.loads(wave_files[-1].read_text())
            print(f"[trial] aggregated {len(wave_files)} telemetry wave files; latest: {wave_files[-1].name}")

    summary = {
        "dry_run": False,
        "env": env_status,
        "candidate_pool_size": len(pool),
        "outer_status": str(status),
        "outer_wall_seconds": float(outer_wall),
        "smt_mt_latest_metrics": latest_metrics,
        "result_ghost_rect": (result or {}).get("ghost_rect") if isinstance(result, dict) else None,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "phase1_trial_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(f"[trial] wrote {output_dir / 'phase1_trial_summary.json'}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip real inner solve; verify env + engine wiring only.")
    parser.add_argument("--max-candidates", type=int, default=10)
    parser.add_argument("--benders-max-iter", type=int, default=5)
    parser.add_argument("--master-seconds", type=float, default=120.0)
    parser.add_argument("--binding-seconds", type=float, default=60.0)
    parser.add_argument("--routing-seconds", type=float, default=60.0)
    parser.add_argument("--flow-seconds", type=float, default=30.0)
    parser.add_argument("--output-dir", type=Path,
                        default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    summary = run_trial(
        max_candidates=args.max_candidates,
        benders_max_iter=args.benders_max_iter,
        master_seconds=args.master_seconds,
        binding_seconds=args.binding_seconds,
        routing_seconds=args.routing_seconds,
        flow_seconds=args.flow_seconds,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
    )
    return 0 if summary else 1


if __name__ == "__main__":
    raise SystemExit(main())
