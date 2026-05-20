from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[4]
WORKSPACE_ROOT = PROJECT_ROOT.parent
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"

DEFAULT_STRATEGY = ARTIFACT_ROOT / "36_signature_bucket_tightening_strategy" / "signature_bucket_tightening_strategy.json"
DEFAULT_ORIGINAL_SPEC = (
    ARTIFACT_ROOT
    / "37_signature_bucket_tightening_instrumentation_patch_spec"
    / "signature_bucket_tightening_instrumentation_patch_spec.json"
)
DEFAULT_REVIEW_REPLY = (
    WORKSPACE_ROOT
    / ".codex_test_logs"
    / "chatgpt_project_uploader"
    / "review_reply_extract_s38_signature_bucket_review_reply_001.md"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "39_signature_bucket_patch_spec_revision"

TARGET_METHOD = "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening"
COMPANION_FINALIZATION_METHOD = "CoordinateExactMasterDelegate._add_global_valid_inequalities"
ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION"
COLLECTION_STATS_PATH = (
    "_ghost_anchor_signature_bucket_tightening_stats.signature_tightening_instrumentation"
)
FINAL_BUILD_STATS_PATH = (
    "build_stats.global_valid_inequalities.signature_bucket_capacity_bounds."
    "signature_tightening_instrumentation"
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    revision = build_signature_bucket_patch_spec_revision(
        strategy_path=_resolve_path(PROJECT_ROOT, args.strategy),
        original_spec_path=_resolve_path(PROJECT_ROOT, args.original_spec),
        review_reply_path=_resolve_path(PROJECT_ROOT, args.review_reply),
    )
    print("phase3b checkpoint-free signature bucket patch spec revision")
    print(f"classification={revision['interpretation']['classification']}")
    print(f"action={revision['recommendation']['action']}")
    if not args.no_write:
        paths = write_signature_bucket_patch_spec_revision(
            revision,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"revision_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"revision_md={_display_path(PROJECT_ROOT, paths['md'])}")
    return 0 if revision["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the S39 revised spec after S38 external review found the "
            "signature-bucket instrumentation output-path blocker."
        )
    )
    parser.add_argument("--strategy", type=Path, default=DEFAULT_STRATEGY)
    parser.add_argument("--original-spec", type=Path, default=DEFAULT_ORIGINAL_SPEC)
    parser.add_argument("--review-reply", type=Path, default=DEFAULT_REVIEW_REPLY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_patch_spec_revision(
    *,
    strategy_path: Path,
    original_spec_path: Path,
    review_reply_path: Path,
) -> dict[str, Any]:
    strategy_path = Path(strategy_path)
    original_spec_path = Path(original_spec_path)
    review_reply_path = Path(review_reply_path)
    strategy = _load_json(strategy_path)
    original_spec = _load_json(original_spec_path)
    review_reply = review_reply_path.read_text(encoding="utf-8")
    blocker = _classify_s38_blocker(review_reply)
    strategy_ready = (
        strategy.get("status") == "completed"
        and _mapping(strategy.get("interpretation")).get("classification")
        == "signature_bucket_internal_loop_strategy_required"
    )
    original_spec_ready = (
        original_spec.get("source_mutation_performed") is False
        and _mapping(original_spec.get("interpretation")).get("implementation_allowed_now")
        is False
    )
    completed = (
        blocker["classification"] == "output_path_finalization_revision_required"
        and strategy_ready
        and original_spec_ready
    )
    return {
        "schema": "phase3b-signature-bucket-patch-spec-revision/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "completed" if completed else "manual_review_required",
        "revision_kind": "external_review_blocker_revision_spec_no_mutation",
        "strategy_path": str(strategy_path),
        "original_spec_path": str(original_spec_path),
        "review_reply_path": str(review_reply_path),
        "fresh_solver_run_started_by_builder": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "no_solve": True,
        "proof_source": False,
        "checkpoint_written": False,
        "source_model_mutation": False,
        "source_mutation_performed": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "review_required_before_authorization": True,
        "external_review_is_authorization": False,
        "s38_review": {
            "verdict": "does_not_pass",
            "blocker": blocker,
            "reply_chars": len(review_reply),
            "reply_lines": len(review_reply.splitlines()),
            "untrusted_external_content": True,
        },
        "interpretation": {
            "classification": blocker["classification"] if completed else "manual_review_required",
            "source_mutation_authorized_by_this_artifact": False,
            "implementation_allowed_now": False,
            "reason": (
                "S38 identified that method-local writes to the final build_stats path can be "
                "overwritten by the later global-valid-inequalities rebuild. The revised spec "
                "keeps measurement in the target method and adds only a narrow finalization "
                "copy point where signature_bucket_capacity_bounds is constructed."
                if completed
                else "Required S36/S37/S38 inputs are not in the expected review-blocker state."
            ),
        },
        "revised_patch_spec": _revised_patch_spec() if completed else {},
        "validation_plan": _validation_plan() if completed else [],
        "recommendation": {
            "action": (
                "prepare_signature_bucket_re_review_package"
                if completed
                else "hold_for_manual_review"
            ),
            "next_engineering_step": (
                "build S40 external re-review package before requesting authorization or mutating source"
                if completed
                else "inspect S38 reply and S37 spec manually before proceeding"
            ),
            "blocked_actions": [
                "do_not_request_user_authorization_before_re_review_passes",
                "do_not_mutate_src_models_before_explicit_authorization",
                "do_not_run_more_42x32_runtime",
                "do_not_run_67x20",
                "do_not_run_full_wave_matrix",
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


def write_signature_bucket_patch_spec_revision(
    revision: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    _assert_revision_namespace(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "signature_bucket_patch_spec_revision.json"
    md_path = output_dir / "signature_bucket_patch_spec_revision.md"
    json_path.write_text(json.dumps(revision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_signature_bucket_patch_spec_revision_markdown(revision), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def render_signature_bucket_patch_spec_revision_markdown(revision: Mapping[str, Any]) -> str:
    interpretation = _mapping(revision.get("interpretation"))
    recommendation = _mapping(revision.get("recommendation"))
    spec = _mapping(revision.get("revised_patch_spec"))
    lines = [
        "# Phase3B Signature Bucket Patch Spec Revision",
        "",
        f"- Status: `{revision.get('status')}`",
        f"- Classification: `{interpretation.get('classification')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- Source mutation performed: `false`",
        "- Implementation allowed now: `false`",
        "- Review required before authorization: `true`",
        "",
        "## Revised Scope",
        "",
        f"- Collection method: `{spec.get('collection_method')}`",
        f"- Companion finalization method: `{spec.get('companion_finalization_method')}`",
        f"- Collection stats path: `{spec.get('collection_stats_path')}`",
        f"- Final build_stats path: `{spec.get('final_build_stats_output_path')}`",
        "",
        "## Default-Off Contract",
        "",
    ]
    for item in list(spec.get("default_off_contract", []) or []):
        lines.append(f"- {item}")
    lines.extend(["", "## Required Top Entry Fields", ""])
    for item in list(spec.get("required_top_entry_fields", []) or []):
        lines.append(f"- `{item}`")
    lines.extend(["", "## Validation Plan", ""])
    for item in list(revision.get("validation_plan", []) or []):
        lines.append(f"- `{item.get('id')}`: {item.get('check')}")
    lines.extend(
        [
            "",
            "This artifact revises the spec only. It is not authorization, not a source patch, and not proof evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def _classify_s38_blocker(review_reply: str) -> dict[str, Any]:
    text = review_reply.lower()
    markers = {
        "review_does_not_pass": "review does not pass" in text,
        "scope_output_path_mismatch": "scope/output-path mismatch" in text,
        "target_method_before_finalization": "_apply_ghost_anchor_signature_bucket_tightening" in text
        and "_add_global_valid_inequalities" in text,
        "final_path_overwrite_risk": "overwritten" in text
        or "reconstructs and assigns" in text,
    }
    classification = (
        "output_path_finalization_revision_required"
        if all(markers.values())
        else "manual_review_required"
    )
    return {
        "classification": classification,
        "markers": markers,
        "summary": (
            "S37 method-local final build_stats output path can be overwritten by the later "
            "_add_global_valid_inequalities reconstruction."
            if classification == "output_path_finalization_revision_required"
            else "S38 blocker markers were incomplete."
        ),
    }


def _revised_patch_spec() -> dict[str, Any]:
    return {
        "target_file": "src/models/exact_coordinate_master.py",
        "env_var": ENV_VAR,
        "collection_method": TARGET_METHOD,
        "companion_finalization_method": COMPANION_FINALIZATION_METHOD,
        "collection_stats_path": COLLECTION_STATS_PATH,
        "final_build_stats_output_path": FINAL_BUILD_STATS_PATH,
        "implementation_outline": [
            "Resolve the env var default-off using the same true/false/invalid pattern as existing via-pole instrumentation.",
            "When enabled, collect timing/counter diagnostics inside _apply_ghost_anchor_signature_bucket_tightening only.",
            "Store diagnostics under _ghost_anchor_signature_bucket_tightening_stats['signature_tightening_instrumentation'].",
            "In _add_global_valid_inequalities, after signature_bucket_capacity_bounds is constructed, copy that nested diagnostics object to the final build_stats output path if present.",
            "When disabled, do not create signature_tightening_instrumentation in temporary stats or final build_stats.",
        ],
        "default_off_contract": [
            f"`{ENV_VAR}` unset or `0` leaves no `signature_tightening_instrumentation` key.",
            "Default-off ModelProto text, variable count, constraint count, and constraint type distribution remain unchanged.",
            "Default-off final serialized build_stats remain unchanged except for unrelated timestamp-free ordering already present in the code.",
            "Invalid env values raise ValueError mentioning the env var name.",
        ],
        "instrumentation_groups": [
            "mandatory_payload_build",
            "required_optional_payload_build",
            "per_anchor_mandatory_scan",
            "per_anchor_required_optional_scan",
            "constraint_add",
            "stats_finalize",
        ],
        "required_top_entry_fields": [
            "rect_idx",
            "anchor",
            "group_id_or_template",
            "bucket_id",
            "scan_count",
            "reduction_count",
            "elapsed_seconds",
        ],
        "mandatory_required_optional_separation": True,
        "non_goals": [
            "do not disable, relax, or rewrite any signature bucket constraint",
            "do not change production defaults",
            "do not connect instrumentation output to proof semantics",
            "do not write canonical checkpoints",
            "do not alter scheduler order or candidate universe",
        ],
    }


def _validation_plan() -> list[dict[str, str]]:
    return [
        {
            "id": "re_review_before_authorization",
            "check": "submit S40 package for external review and do not request user authorization unless review passes",
        },
        {
            "id": "default_off_regression",
            "check": "after later authorization and implementation, env unset and env=0 keep ModelProto and final build_stats unchanged",
        },
        {
            "id": "enabled_stats_copy",
            "check": "with env enabled in a small fixture, diagnostics appear in final build_stats via _add_global_valid_inequalities copy/finalization",
        },
        {
            "id": "invalid_env_guard",
            "check": "invalid env value raises ValueError mentioning EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION",
        },
        {
            "id": "sensitive_path_guard",
            "check": "confirm checkpoints, final solution, blueprint, certified manifest, preflight, viewer, release, and frontdoor fingerprints are unchanged",
        },
    ]


def _assert_revision_namespace(path: Path) -> None:
    normalized = str(path).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "39_signature_bucket_patch_spec_revision" not in normalized
    ):
        raise ValueError(f"Refusing to write outside signature bucket patch spec revision namespace: {path}")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _resolve_path(root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else root / path


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
