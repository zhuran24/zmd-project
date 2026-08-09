"""批E/批C shared prod-scale attach host (direct, non-certified-entry).

Extends docs/research/p1_3_m5_convergence_20260708/m5_cell_runner.py (the
sanctioned clean-room-construct → set-env-after → run_with_status() form;
legality notes there apply verbatim) with the 批E RFC-003 surfaces:

- cut ledger wiring (--ledger-root; spec 08 D-5): a CutLedgerWriter scoped by
  --run-tag is threaded into LBBDController; the segment is sealed on exit and
  its tri-state read result is dumped into the output JSON;
- family enablement (--enabled-families; spec 08 D-13) for the prod-scale
  rollback drill (gate 7);
- predecessor lineage flags (--predecessor-segment / --predecessor-tail-hash /
  --recovery-reason) so a manual restart chain writes honest GENESIS lineage;
- solvable-recipe defaults from m5_ab_param_bisect_20260711 (fixed + p3 + s3):
  the M5-era runs never exercised organic attach because the master never
  solved — these defaults are the recipe that reached OPTIMAL@541-649s;
- dedup / epoch telemetry dump (semantic_duplicate bucket, epoch ids).

批C first check (spec 08 §0 卡点①): run with --attach on --ghost-w 6
--ghost-h 6 and confirm coordinate_framework_cut_count > 0 (organic trigger).
Memory discipline: prod-scale masters run ONE at a time (~60G peak).

Usage:
  .venv/bin/python attach_host_runner.py --ghost-w 6 --ghost-h 6 --attach on \
      --master-seconds 900 --out cell.json --run-tag batch_c_probe_1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))


def _exact_env_manifest_digest() -> str:
    pairs = sorted(
        (k, v) for k, v in os.environ.items() if k.startswith("EXACT_")
    )
    return hashlib.sha256(
        json.dumps(pairs, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ghost-w", type=int, required=True)
    parser.add_argument("--ghost-h", type=int, required=True)
    parser.add_argument("--attach", choices=("on", "off"), required=True)
    parser.add_argument("--master-seconds", type=float, default=900.0)
    parser.add_argument("--binding-seconds", type=float, default=600.0)
    parser.add_argument("--routing-seconds", type=float, default=600.0)
    parser.add_argument("--max-iterations", type=int, default=30)
    parser.add_argument("--workers", type=int, default=1)
    # Solvable-recipe defaults (m5_ab_param_bisect_20260711: fixed+p3+s3).
    parser.add_argument(
        "--master-branching",
        choices=("fixed", "automatic", "portfolio"),
        default="fixed",
    )
    parser.add_argument("--probing-level", type=int, default=3)
    parser.add_argument("--symmetry-level", type=int, default=3)
    parser.add_argument("--max-memory-mb", type=int, default=None)
    parser.add_argument("--search-profile", default=None)
    parser.add_argument("--disable-warm-start", action="store_true")
    # 批E surfaces:
    parser.add_argument(
        "--run-tag",
        required=True,
        help="ledger scope id (data/cuts/<run-tag>/ under --ledger-root)",
    )
    parser.add_argument(
        "--ledger-root",
        type=Path,
        default=None,
        help="ledger root dir (default: a fresh scratch dir — NEVER a tracked path)",
    )
    parser.add_argument(
        "--enabled-families",
        default=None,
        help="comma list (default all four); gate-7 rollback drill knob",
    )
    parser.add_argument("--predecessor-segment", default=None)
    parser.add_argument("--predecessor-tail-hash", default=None)
    parser.add_argument("--recovery-reason", default="fresh_start")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    # Clean-room env for construction (session creation fail-closes on the
    # attach env — unsafe map; only exported AFTER construction below).
    os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
    os.environ["EXACT_CP_SAT_WORKERS"] = str(args.workers)
    os.environ["EXACT_MASTER_SEARCH_BRANCHING"] = args.master_branching
    os.environ["EXACT_MASTER_CP_MODEL_PROBING_LEVEL"] = str(args.probing_level)
    os.environ["EXACT_MASTER_SYMMETRY_LEVEL"] = str(args.symmetry_level)
    if args.max_memory_mb is not None:
        os.environ["EXACT_SUBPROBLEM_MAX_MEMORY_MB"] = str(args.max_memory_mb)
    if args.search_profile:
        os.environ["EXACT_COORDINATE_MASTER_SEARCH_PROFILE"] = args.search_profile

    from src.cuts.ledger import CutLedgerWriter, read_segment
    from src.models.cut_manager import CutManager
    from src.models.master_model import MasterPlacementModel
    from src.search.benders_loop import ExactSearchSession, LBBDController

    try:
        from importlib.metadata import version as _pkg_version

        ortools_version = _pkg_version("ortools")
    except Exception:  # noqa: BLE001 — telemetry only
        ortools_version = "unknown"

    result: dict = {
        "ghost_rect": [args.ghost_w, args.ghost_h],
        "attach": args.attach,
        "recipe": {
            "master_branching": args.master_branching,
            "probing_level": args.probing_level,
            "symmetry_level": args.symmetry_level,
            "workers": args.workers,
            "max_iterations": args.max_iterations,
        },
        "run_tag": args.run_tag,
    }

    t0 = time.perf_counter()
    session = ExactSearchSession.create(PROJECT_ROOT, solve_mode="certified_exact")
    result["session_build_seconds"] = round(time.perf_counter() - t0, 3)

    t1 = time.perf_counter()
    master = MasterPlacementModel.from_exact_core(
        session.core, ghost_rect=(args.ghost_w, args.ghost_h)
    )
    result["master_build_seconds"] = round(time.perf_counter() - t1, 3)

    ledger_root = args.ledger_root or Path(tempfile.mkdtemp(prefix="ce_ledger_"))
    ledger = CutLedgerWriter(
        ledger_root,
        scope_id=args.run_tag,
        genesis_context={
            "predecessor_segment": args.predecessor_segment,
            "predecessor_tail_hash": args.predecessor_tail_hash,
            "recovery_reason": args.recovery_reason,
            "ortools_version": ortools_version,
            "workers": args.workers,
            "exact_env_manifest_digest": _exact_env_manifest_digest(),
            "ghost_rect": [args.ghost_w, args.ghost_h],
        },
    )
    result["ledger_segment"] = str(ledger.path)

    enabled = (
        [name.strip() for name in args.enabled_families.split(",") if name.strip()]
        if args.enabled_families
        else None
    )
    scratch = Path(tempfile.mkdtemp(prefix="ce_cell_"))
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
        disable_master_warm_start=bool(args.disable_warm_start),
        session=session,
        enabled_cut_families=enabled,
        cut_ledger=ledger,
    )

    # Only NOW may the attach switch appear (direct invocation; the entrance
    # guards are deliberately not on this path — sanctioned harness form).
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
    finally:
        try:
            ledger.seal()
        except Exception as exc:  # noqa: BLE001
            result["ledger_seal_error"] = f"{type(exc).__name__}: {exc}"
    result["lbbd_wall_seconds"] = round(time.perf_counter() - t2, 3)

    summary = getattr(controller, "last_proof_summary", None) or {}
    result["proof_summary"] = {
        k: v
        for k, v in summary.items()
        if isinstance(v, (str, int, float, bool, type(None)))
    }
    stats = getattr(master, "build_stats", {}) or {}
    result["coordinate_framework_cut_count"] = stats.get(
        "coordinate_framework_cut_count", 0
    )
    result["cut_framework_attach_last"] = stats.get("cut_framework_attach_last")

    seg = read_segment(ledger.path)
    result["ledger_read"] = {
        "status": seg.status,
        "events": len(seg.events),
        "applied": sum(1 for e in seg.events if e["event"] == "APPLIED"),
        "semantic_duplicates": sum(
            1
            for e in seg.events
            if e["event"] == "REJECTED"
            and e.get("reason_code") == "semantic_duplicate"
        ),
        "tail_hash": seg.tail_hash,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result["ledger_read"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
