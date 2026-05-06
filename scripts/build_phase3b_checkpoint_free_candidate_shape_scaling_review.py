from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.sensitive_path_audit import (  # noqa: E402
    build_sensitive_path_fingerprint,
    compare_sensitive_path_fingerprints,
)
from src.search.exact_campaign import atomic_write_json  # noqa: E402

ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_SHAPE_COMPARISON = (
    ARTIFACT_ROOT
    / "29_candidate_shape_inventory_comparison"
    / "candidate_shape_inventory_comparison_exec_001"
    / "candidate_shape_inventory_comparison.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "30_candidate_shape_scaling_review"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    review = build_candidate_shape_scaling_review(
        comparison_path=_resolve_path(PROJECT_ROOT, args.comparison),
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        no_write=bool(args.no_write),
    )
    print("phase3b checkpoint-free candidate shape scaling review")
    print(f"status={review['status']}")
    print(f"classification={review['interpretation']['classification']}")
    print(f"action={review['recommendation']['action']}")
    if not args.no_write:
        print(f"review_json={_display_path(PROJECT_ROOT, Path(review['review_path']))}")
    return 0 if review["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review no-solve candidate-shape inventory scaling evidence."
    )
    parser.add_argument("--comparison", type=Path, default=DEFAULT_SHAPE_COMPARISON)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_candidate_shape_scaling_review(
    *,
    comparison_path: Path,
    output_dir: Path,
    no_write: bool = False,
) -> dict[str, Any]:
    comparison_path = _resolve_path(PROJECT_ROOT, comparison_path)
    output_dir = _resolve_path(PROJECT_ROOT, output_dir)
    _assert_review_namespace(output_dir)
    comparison = _load_json(comparison_path)
    before = build_sensitive_path_fingerprint(PROJECT_ROOT)
    rows = [_normalize_row(row) for row in list(comparison.get("rows", []) or [])]
    baseline = next((row for row in rows if row.get("candidate_key") == "42x32"), rows[0] if rows else {})
    non_baseline = [row for row in rows if row is not baseline]
    metrics = _shape_metrics(baseline, non_baseline)
    classification = _classify_shape_scaling(
        comparison=comparison,
        baseline=baseline,
        non_baseline=non_baseline,
        metrics=metrics,
    )
    after = build_sensitive_path_fingerprint(PROJECT_ROOT)
    sensitive_comparison = compare_sensitive_path_fingerprints(before, after)
    status = "completed" if not sensitive_comparison.get("changed") else "disqualified_sensitive_path_mutation"
    payload = {
        "schema": "phase3b-checkpoint-free-candidate-shape-scaling-review/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "project_root": str(PROJECT_ROOT),
        "comparison_path": str(comparison_path),
        "output_dir": str(output_dir),
        "review_path": str(output_dir / "candidate_shape_scaling_review.json"),
        "fresh_solver_run_started": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "proof_source": False,
        "checkpoint_written": False,
        "source_mutation_performed": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "rows": rows,
        "metrics": metrics,
        "interpretation": {
            "classification": classification,
            "evidence_kind": "no_solve_shape_inventory_replay",
            "baseline_candidate_key": baseline.get("candidate_key"),
            "comparison_candidate_keys": [row.get("candidate_key") for row in non_baseline],
            "shape_specific_hotspot": classification == "shape_specific_via_pole_anchor_explosion",
            "sensitive_paths_clean": not bool(_mapping(comparison.get("sensitive_path_comparison")).get("changed")),
            "checkpoints_clean": not bool(comparison.get("checkpoint_written")),
        },
        "recommendation": _recommendation(classification),
        "sensitive_path_comparison": sensitive_comparison,
    }
    if not no_write:
        output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(output_dir / "sensitive_path_before.json", before)
        atomic_write_json(output_dir / "sensitive_path_after.json", after)
        atomic_write_json(output_dir / "sensitive_path_comparison.json", sensitive_comparison)
        atomic_write_json(output_dir / "candidate_shape_scaling_review.json", payload)
        (output_dir / "candidate_shape_scaling_review.md").write_text(
            render_candidate_shape_scaling_review_markdown(payload),
            encoding="utf-8",
        )
    return payload


def render_candidate_shape_scaling_review_markdown(payload: Mapping[str, Any]) -> str:
    interpretation = _mapping(payload.get("interpretation"))
    recommendation = _mapping(payload.get("recommendation"))
    metrics = _mapping(payload.get("metrics"))
    lines = [
        "# Phase3B Candidate Shape Scaling Review",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- CpSolver.Solve called: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "- Source mutation performed: `false`",
        "",
        "## Shape Signal",
        "",
        f"- Median non-baseline constraint ratio vs `42x32`: `{_fmt(metrics.get('median_non_baseline_constraint_ratio'))}`",
        f"- Median non-baseline ghost-time ratio vs `42x32`: `{_fmt(metrics.get('median_non_baseline_ghost_seconds_ratio'))}`",
        f"- Median non-baseline family-bound-constraint ratio vs `42x32`: `{_fmt(metrics.get('median_non_baseline_family_bound_constraint_ratio'))}`",
        f"- Median non-baseline anchor-count ratio vs `42x32`: `{_fmt(metrics.get('median_non_baseline_anchor_count_ratio'))}`",
        "",
        "| Candidate | Status | Vars | Constraints | Ghost seconds | Family constraints | Anchors | Surviving placements |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in list(payload.get("rows", []) or []):
        lines.append(
            "| {candidate_key} | {status} | {variables} | {constraints} | {ghost_seconds:.3f} | {family_constraints} | {anchors} | {surviving} |".format(
                candidate_key=row.get("candidate_key"),
                status=row.get("status"),
                variables=row.get("variable_count") or 0,
                constraints=row.get("constraint_count") or 0,
                ghost_seconds=float(row.get("ghost_constraint_seconds") or 0.0),
                family_constraints=row.get("conditioned_family_upper_bound_constraints") or 0,
                anchors=row.get("family_reduction_anchor_count") or 0,
                surviving=row.get("surviving_placements") or 0,
            )
        )
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            str(recommendation.get("next_engineering_step")),
            "",
            "This review is local, no-solve, checkpoint-free evidence only. It does not authorize proof promotion, scheduler changes, or canonical checkpoint writes.",
            "",
        ]
    )
    return "\n".join(lines)


def _shape_metrics(baseline: Mapping[str, Any], non_baseline: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "median_non_baseline_constraint_ratio": _median_ratio(
            non_baseline, "constraint_count", baseline.get("constraint_count")
        ),
        "median_non_baseline_ghost_seconds_ratio": _median_ratio(
            non_baseline, "ghost_constraint_seconds", baseline.get("ghost_constraint_seconds")
        ),
        "median_non_baseline_family_bound_constraint_ratio": _median_ratio(
            non_baseline,
            "conditioned_family_upper_bound_constraints",
            baseline.get("conditioned_family_upper_bound_constraints"),
        ),
        "median_non_baseline_anchor_count_ratio": _median_ratio(
            non_baseline,
            "family_reduction_anchor_count",
            baseline.get("family_reduction_anchor_count"),
        ),
        "max_non_baseline_ghost_seconds_ratio": _max_ratio(
            non_baseline, "ghost_constraint_seconds", baseline.get("ghost_constraint_seconds")
        ),
        "max_non_baseline_anchor_count_ratio": _max_ratio(
            non_baseline,
            "family_reduction_anchor_count",
            baseline.get("family_reduction_anchor_count"),
        ),
        "min_non_baseline_constraint_ratio": _min_ratio(
            non_baseline, "constraint_count", baseline.get("constraint_count")
        ),
    }


def _classify_shape_scaling(
    *,
    comparison: Mapping[str, Any],
    baseline: Mapping[str, Any],
    non_baseline: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
) -> str:
    comparison_ready = (
        comparison.get("status") == "completed"
        and comparison.get("execute_no_solve") is True
        and _mapping(comparison.get("sensitive_path_comparison")).get("changed") is False
        and comparison.get("cp_solver_solve_called") is False
        and comparison.get("checkpoint_written") is False
        and comparison.get("source_mutation_performed") is False
    )
    if not comparison_ready:
        return "shape_scaling_comparison_not_ready"
    if len(non_baseline) < 2:
        return "shape_scaling_insufficient_comparison_shapes"
    if (
        float(baseline.get("ghost_constraint_seconds") or 0.0) >= 30.0
        and int(baseline.get("family_reduction_anchor_count") or 0) >= 500
        and _float(metrics.get("max_non_baseline_ghost_seconds_ratio"), default=1.0) <= 0.10
        and _float(metrics.get("max_non_baseline_anchor_count_ratio"), default=1.0) <= 0.10
        and _float(metrics.get("min_non_baseline_constraint_ratio"), default=0.0) >= 0.75
    ):
        return "shape_specific_via_pole_anchor_explosion"
    return "shape_scaling_inconclusive"


def _recommendation(classification: str) -> dict[str, Any]:
    if classification == "shape_specific_via_pole_anchor_explosion":
        return {
            "action": "prepare_default_off_via_pole_shape_instrumentation_patch_spec",
            "next_engineering_step": (
                "Prepare a spec-only default-off instrumentation patch for via-pole/ghost-aware family-bound "
                "generation. Do not mutate solver source until that source patch is explicitly authorized."
            ),
            "blocked_actions": [
                "do_not_run_more_hotspot_runtime",
                "do_not_write_canonical_checkpoints",
                "do_not_mutate_proof_source",
                "do_not_promote_local_results_to_proof",
                "do_not_change_production_defaults",
            ],
        }
    return {
        "action": "hold_for_manual_shape_scaling_review",
        "next_engineering_step": "Review the no-solve shape evidence before any new runtime or source-edit step.",
        "blocked_actions": [
            "do_not_run_more_hotspot_runtime",
            "do_not_write_canonical_checkpoints",
            "do_not_mutate_proof_source",
        ],
    }


def _normalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = [
        "candidate_key",
        "status",
        "variable_count",
        "constraint_count",
        "ghost_constraint_seconds",
        "conditioned_family_upper_bound_constraints",
        "family_reduction_anchor_count",
        "surviving_placements",
        "constraint_ratio_vs_baseline",
        "ghost_seconds_ratio_vs_baseline",
    ]
    return {key: row.get(key) for key in keys}


def _median_ratio(rows: Sequence[Mapping[str, Any]], key: str, baseline: Any) -> float | None:
    ratios = [_ratio(row.get(key), baseline) for row in rows]
    ratios = [ratio for ratio in ratios if ratio is not None]
    return float(statistics.median(ratios)) if ratios else None


def _max_ratio(rows: Sequence[Mapping[str, Any]], key: str, baseline: Any) -> float | None:
    ratios = [_ratio(row.get(key), baseline) for row in rows]
    ratios = [ratio for ratio in ratios if ratio is not None]
    return max(ratios) if ratios else None


def _min_ratio(rows: Sequence[Mapping[str, Any]], key: str, baseline: Any) -> float | None:
    ratios = [_ratio(row.get(key), baseline) for row in rows]
    ratios = [ratio for ratio in ratios if ratio is not None]
    return min(ratios) if ratios else None


def _ratio(value: Any, baseline: Any) -> float | None:
    denominator = _float(baseline)
    numerator = _float(value)
    if denominator is None or numerator is None or denominator == 0.0:
        return None
    return numerator / denominator


def _float(value: Any, *, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt(value: Any) -> str:
    number = _float(value)
    return "null" if number is None else f"{number:.4f}"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _resolve_path(root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else root / path


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _assert_review_namespace(path: Path) -> None:
    normalized = str(path).replace("/", "\\")
    if "phase3b_local_13900ks_tuning_20260430" not in normalized or "30_candidate_shape_scaling_review" not in normalized:
        raise ValueError(f"refusing to write outside candidate shape scaling review namespace: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
