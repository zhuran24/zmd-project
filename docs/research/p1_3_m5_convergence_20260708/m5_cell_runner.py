"""M5 convergence A/B cell runner (P1.3, 2026-07-08).

Runs ONE measurement cell: a direct (non-certified-entry) LBBD invocation on
the real frozen 266-instance session with the cut-framework attach either ON
or OFF, and dumps metrics as JSON.

Legality notes (M5 recon, m4recon/m5_harness.md):
- This is a measurement harness, NOT a certification run. run_with_status()
  has no ability to mint CERTIFIED; we never touch supervisor_seal /
  data/checkpoints / data/solutions. All output goes to the --out path the
  driver points at (scratch/telemetry only).
- ExactSearchSession.create() itself fail-closes if the attach env is set,
  so the env is only exported AFTER session/master/controller construction.
- EXACT_CP_SAT_WORKERS is pinned to 1 for clean wall-clock attribution.

Usage:
  python m5_cell_runner.py --ghost-w 40 --ghost-h 40 --attach on \
      --master-seconds 300 --binding-seconds 300 --routing-seconds 300 \
      --max-iterations 15 --out cell_result.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ghost-w", type=int, required=True)
    parser.add_argument("--ghost-h", type=int, required=True)
    parser.add_argument("--attach", choices=("on", "off"), required=True)
    parser.add_argument("--master-seconds", type=float, default=300.0)
    parser.add_argument("--binding-seconds", type=float, default=300.0)
    parser.add_argument("--routing-seconds", type=float, default=300.0)
    parser.add_argument("--max-iterations", type=int, default=15)
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="EXACT_CP_SAT_WORKERS; 1 = clean attribution, 4 = production axis",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    # Clean-room env for construction: session creation fail-closes on the
    # attach env (unsafe map), so it must be absent now.
    os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
    os.environ["EXACT_CP_SAT_WORKERS"] = str(args.workers)

    from src.models.cut_manager import CutManager
    from src.models.master_model import MasterPlacementModel
    from src.search.benders_loop import ExactSearchSession, LBBDController

    result = {
        "ghost_rect": [args.ghost_w, args.ghost_h],
        "attach": args.attach,
        "master_seconds": args.master_seconds,
        "binding_seconds": args.binding_seconds,
        "routing_seconds": args.routing_seconds,
        "max_iterations": args.max_iterations,
        "workers": args.workers,
    }

    t0 = time.perf_counter()
    session = ExactSearchSession.create(PROJECT_ROOT, solve_mode="certified_exact")
    result["session_build_seconds"] = round(time.perf_counter() - t0, 3)

    t1 = time.perf_counter()
    master = MasterPlacementModel.from_exact_core(
        session.core, ghost_rect=(args.ghost_w, args.ghost_h)
    )
    result["master_build_seconds"] = round(time.perf_counter() - t1, 3)

    scratch = Path(tempfile.mkdtemp(prefix="m5_cell_"))
    controller = LBBDController(
        master=master,
        cut_manager=CutManager(checkpoint_dir=scratch, solve_mode="certified_exact"),
        project_root=PROJECT_ROOT,
        solve_mode="certified_exact",
        master_seconds=args.master_seconds,
        binding_seconds=args.binding_seconds,
        routing_seconds=args.routing_seconds,
        max_iterations=args.max_iterations,
        artifact_hashes=session.artifact_hashes,
    )

    # Only NOW is the attach switch allowed to appear (direct invocation —
    # run_benders_for_ghost_rect's unsafe-map gate is deliberately not on
    # this path; see m5_harness.md Q1).
    if args.attach == "on":
        os.environ["EXACT_CUT_FRAMEWORK_ATTACH"] = "1"

    t2 = time.perf_counter()
    try:
        status, solution = controller.run_with_status()
        result["status"] = str(status)
        result["has_solution"] = solution is not None
    except Exception as exc:  # noqa: BLE001 — record, don't crash the driver
        result["status"] = "HARNESS_EXCEPTION"
        result["exception"] = f"{type(exc).__name__}: {exc}"
    result["lbbd_wall_seconds"] = round(time.perf_counter() - t2, 3)

    summary = getattr(controller, "last_proof_summary", None) or {}
    result["benders_iterations"] = summary.get("benders_iterations")
    result["binding_status"] = summary.get("binding_status")
    result["routing_status"] = summary.get("routing_status")
    result["cut_framework_attached_last_trigger"] = summary.get(
        "cut_framework_attached"
    )
    stats = getattr(master, "build_stats", {}) or {}
    result["coordinate_framework_cut_count"] = stats.get(
        "coordinate_framework_cut_count", 0
    )
    result["cut_framework_attach_last"] = stats.get("cut_framework_attach_last")
    result["coordinate_pattern_nogood_last_cut"] = stats.get(
        "coordinate_pattern_nogood_last_cut"
    )
    result["coordinate_baseline_packing_last_cut"] = stats.get(
        "coordinate_baseline_packing_last_cut"
    )
    result["coordinate_power_pose_exclusion_last_cut"] = stats.get(
        "coordinate_power_pose_exclusion_last_cut"
    )
    result["coordinate_region_capacity_cut_count"] = stats.get(
        "coordinate_region_capacity_cut_count", 0
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
