from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_SHAPE_REVIEW = ARTIFACT_ROOT / "30_candidate_shape_scaling_review" / "candidate_shape_scaling_review.json"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "31_via_pole_shape_instrumentation_patch_spec"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    spec = build_via_pole_shape_instrumentation_patch_spec(
        shape_review_path=_resolve_path(PROJECT_ROOT, args.shape_review),
    )
    print("phase3b checkpoint-free via-pole shape instrumentation patch spec")
    print(f"classification={spec['interpretation']['classification']}")
    print(f"action={spec['recommendation']['action']}")
    if not args.no_write:
        paths = write_via_pole_shape_instrumentation_patch_spec(
            spec,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"spec_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"spec_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Draft a no-source-mutation spec for default-off via-pole shape instrumentation."
    )
    parser.add_argument("--shape-review", type=Path, default=DEFAULT_SHAPE_REVIEW)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_via_pole_shape_instrumentation_patch_spec(*, shape_review_path: Path) -> dict[str, Any]:
    shape_review_path = Path(shape_review_path)
    review = _load_json(shape_review_path)
    interpretation = _mapping(review.get("interpretation"))
    recommendation = _mapping(review.get("recommendation"))
    ready = (
        review.get("status") == "completed"
        and interpretation.get("classification") == "shape_specific_via_pole_anchor_explosion"
        and recommendation.get("action")
        == "prepare_default_off_via_pole_shape_instrumentation_patch_spec"
        and review.get("source_mutation_performed") is False
    )
    return {
        "schema": "phase3b-checkpoint-free-via-pole-shape-instrumentation-patch-spec/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "spec_kind": "default_off_source_patch_spec_no_mutation",
        "shape_review_path": str(shape_review_path),
        "fresh_solver_run_started_by_builder": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "proof_source": False,
        "checkpoint_written": False,
        "source_mutation_performed": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "evidence": {
            "shape_review_classification": interpretation.get("classification"),
            "shape_review_action": recommendation.get("action"),
            "metrics": review.get("metrics"),
        },
        "interpretation": {
            "classification": (
                "patch_spec_ready_source_mutation_still_blocked"
                if ready
                else "manual_review_required"
            ),
            "source_mutation_authorized_by_this_artifact": False,
            "implementation_allowed_now": False,
            "reason": (
                "no-solve shape evidence points to a 42x32 via-pole anchor explosion; instrumentation would touch proof-adjacent model construction and needs explicit authorization"
                if ready
                else "shape-scaling review is not ready for an instrumentation patch spec"
            ),
        },
        "patch_spec": _patch_spec() if ready else {},
        "validation_plan": _validation_plan() if ready else [],
        "recommendation": {
            "action": (
                "hold_for_default_off_via_pole_shape_instrumentation_source_authorization"
                if ready
                else "hold_for_manual_review"
            ),
            "next_engineering_step": (
                "request or wait for explicit authorization before mutating proof-adjacent source; after authorization, implement only default-off instrumentation and validate with no-solve inventory"
                if ready
                else "review shape-scaling evidence before proceeding"
            ),
            "blocked_actions": [
                "do_not_mutate_src_models_without_explicit_authorization",
                "do_not_run_more_hotspot_runtime",
                "do_not_write_canonical_checkpoints",
                "do_not_promote_local_results_to_proof",
                "do_not_change_production_defaults",
            ],
        },
        "safety": {
            "spec_only": True,
            "builder_executes_solver": False,
            "builder_constructs_model": False,
            "proof_source": False,
            "checkpoint_written": False,
            "canonical_checkpoint_write_allowed": False,
        },
    }


def write_via_pole_shape_instrumentation_patch_spec(spec: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    _assert_spec_namespace(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "via_pole_shape_instrumentation_patch_spec.json"
    md_path = output_dir / "via_pole_shape_instrumentation_patch_spec.md"
    json_path.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_via_pole_shape_instrumentation_patch_spec_markdown(spec), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_via_pole_shape_instrumentation_patch_spec_markdown(spec: Mapping[str, Any]) -> str:
    interpretation = _mapping(spec.get("interpretation"))
    recommendation = _mapping(spec.get("recommendation"))
    patch = _mapping(spec.get("patch_spec"))
    lines = [
        "# Phase3B Via-Pole Shape Instrumentation Patch Spec",
        "",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- Source mutation performed: `false`",
        "- Implementation allowed now: `false`",
        "- Fresh solver run started by builder: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "## Proposed Patch",
        "",
        f"- Target file: `{patch.get('target_file')}`",
        f"- Target method: `{patch.get('target_method')}`",
        f"- New env var: `{patch.get('env_var')}`",
        f"- Default behavior: `{patch.get('default_behavior')}`",
        f"- Diagnostic behavior: `{patch.get('diagnostic_behavior')}`",
        "",
        "## Instrumentation Fields",
        "",
    ]
    for item in list(patch.get("instrumentation_fields", []) or []):
        lines.append(f"- `{item}`")
    lines.extend(["", "## Validation Plan", ""])
    for item in list(spec.get("validation_plan", []) or []):
        lines.append(f"- `{item.get('id')}`: {item.get('check')}")
    lines.extend(
        [
            "",
            "This is a patch specification only. It does not authorize source mutation, proof promotion, canonical checkpoints, or production-default changes.",
            "",
        ]
    )
    return "\n".join(lines)


def _patch_spec() -> dict[str, Any]:
    return {
        "target_file": "src/models/exact_coordinate_master.py",
        "target_method": "CoordinateExactMasterDelegate._apply_ghost_anchor_power_capacity_screen",
        "env_var": "EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION",
        "default_behavior": "disabled; current model construction and build_stats remain unchanged when the env var is unset",
        "diagnostic_behavior": (
            "when explicitly set to 1/true/on for local no-solve experiments, record extra via-pole shape counters and phase timings under build_stats without changing constraints"
        ),
        "instrumentation_fields": [
            "shape_instrumentation.enabled",
            "shape_instrumentation.phase_seconds.pole_cell_index",
            "shape_instrumentation.phase_seconds.per_anchor_blocked_counts",
            "shape_instrumentation.phase_seconds.per_anchor_family_reductions",
            "shape_instrumentation.blocked_pose_indices_histogram",
            "shape_instrumentation.blocked_family_count_histogram",
            "shape_instrumentation.family_reduction_count_histogram",
            "shape_instrumentation.top_family_reduction_anchors",
        ],
        "non_goals": [
            "do not disable, relax, or rewrite any constraint in this patch",
            "do not change production defaults",
            "do not connect instrumentation output to proof semantics",
            "do not write canonical checkpoints",
            "do not alter scheduler order or candidate universe",
        ],
    }


def _validation_plan() -> list[dict[str, str]]:
    return [
        {
            "id": "default_off_regression",
            "check": "with env unset, existing exact-coordinate and ghost-conditioned family-bound tests continue to pass and emitted build_stats remain byte-compatible where asserted",
        },
        {
            "id": "instrumentation_unit_test",
            "check": "with env enabled in a small fixture, shape_instrumentation fields are present and constraints/variables match the default-off model",
        },
        {
            "id": "no_solve_42x32_instrumented_inventory",
            "check": "run exactly one 42x32 no-solve inventory with the env enabled to identify the dominant per-anchor loop or histogram bucket",
        },
        {
            "id": "sensitive_path_guard",
            "check": "confirm data/checkpoints, final solution, blueprint, certified manifest, preflight, viewer, release, and frontdoor fingerprints are unchanged",
        },
    ]


def _assert_spec_namespace(path: Path) -> None:
    normalized = str(Path(path)).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "31_via_pole_shape_instrumentation_patch_spec" not in normalized
    ):
        raise ValueError(f"Refusing to write outside via-pole shape instrumentation patch spec namespace: {path}")


def _load_json(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _resolve_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
