from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_LOG_REVIEW = ARTIFACT_ROOT / "20_master_solve_log_review" / "master_solve_log_review.json"
DEFAULT_MASTER_READINESS = (
    ARTIFACT_ROOT / "19_master_solve_micro_diagnostics" / "master_solve_micro_augmented_readiness_packet.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "21_master_presolve_parameter_micro_matrix"

EVALUATOR_SCRIPT = "scripts/run_phase3b_checkpoint_free_evaluator.py"
SOURCE_CANDIDATE_ID = "local_hotspot_b0_1x1_master_log_global_normal"
HOTSPOT_CANDIDATE_KEY = "42x32"
SOURCE_MARKERS = {
    "src/models/master_model.py": [
        "EXACT_MASTER_SYMMETRY_LEVEL_ENV",
        "EXACT_MASTER_CP_MODEL_PROBING_LEVEL_ENV",
        "EXACT_MASTER_CP_MODEL_PRESOLVE_ENV",
    ],
}
PARAMETER_VARIANTS = [
    {
        "variant_id": "sym0",
        "candidate_id": "local_hotspot_b0_1x1_master_log_sym0_global_normal",
        "run_id": "local_hotspot_b0_1x1_master_log_sym0_300s_42x32_eval_001",
        "env": {"EXACT_MASTER_SYMMETRY_LEVEL": "0"},
        "purpose": "test whether disabling CP-SAT symmetry reduces presolve overhead",
        "risk_level": "medium",
        "eligibility": "first_candidate_after_matrix_review",
    },
    {
        "variant_id": "probe0",
        "candidate_id": "local_hotspot_b0_1x1_master_log_probe0_global_normal",
        "run_id": "local_hotspot_b0_1x1_master_log_probe0_300s_42x32_eval_001",
        "env": {"EXACT_MASTER_CP_MODEL_PROBING_LEVEL": "0"},
        "purpose": "test whether disabling CP-SAT probing reduces presolve overhead",
        "risk_level": "medium",
        "eligibility": "second_candidate_if_sym0_is_safe_or_needs_comparison",
    },
    {
        "variant_id": "sym0_probe0",
        "candidate_id": "local_hotspot_b0_1x1_master_log_sym0_probe0_global_normal",
        "run_id": "local_hotspot_b0_1x1_master_log_sym0_probe0_300s_42x32_eval_001",
        "env": {
            "EXACT_MASTER_SYMMETRY_LEVEL": "0",
            "EXACT_MASTER_CP_MODEL_PROBING_LEVEL": "0",
        },
        "purpose": "test the combined low-presolve-overhead configuration after individual variants",
        "risk_level": "medium_high",
        "eligibility": "third_candidate_after_individual_variants",
    },
]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    matrix = build_master_presolve_parameter_micro_matrix(
        project_root=PROJECT_ROOT,
        log_review_path=_resolve_path(PROJECT_ROOT, args.log_review),
        master_readiness_path=_resolve_path(PROJECT_ROOT, args.master_readiness),
    )
    print("phase3b checkpoint-free master presolve parameter micro matrix")
    print(f"action={matrix['recommendation']['action']}")
    print(f"variant_count={len(matrix['variants'])}")
    if not args.no_write:
        paths = write_master_presolve_parameter_micro_matrix(
            matrix,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"matrix_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"matrix_md={_display_path(PROJECT_ROOT, paths['md'])}")
        print(f"augmented_readiness={_display_path(PROJECT_ROOT, paths['augmented_readiness'])}")
        print(f"command_matrix={_display_path(PROJECT_ROOT, paths['command_matrix'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build local-only 42x32 master presolve parameter micro variants."
    )
    parser.add_argument("--log-review", type=Path, default=DEFAULT_LOG_REVIEW)
    parser.add_argument("--master-readiness", type=Path, default=DEFAULT_MASTER_READINESS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_master_presolve_parameter_micro_matrix(
    *,
    project_root: Path,
    log_review_path: Path,
    master_readiness_path: Path,
    source_markers: Mapping[str, Sequence[str]] = SOURCE_MARKERS,
) -> dict[str, Any]:
    project_root = Path(project_root)
    log_review = _load_json(log_review_path)
    readiness = _load_json(master_readiness_path)
    source_profile = _find_candidate(readiness, SOURCE_CANDIDATE_ID)
    source_audit = _source_audit(project_root=project_root, source_markers=source_markers)
    review_recommendation = _mapping(log_review.get("recommendation"))
    review_interpretation = _mapping(log_review.get("interpretation"))
    ready = (
        review_recommendation.get("action") == "prepare_master_presolve_parameter_micro_matrix"
        and review_interpretation.get("classification")
        == "presolve_symmetry_scale_bottleneck_before_search"
        and bool(source_audit["all_markers_present"])
    )
    variants = [_build_variant(source_profile, raw) for raw in PARAMETER_VARIANTS]
    augmented_readiness = _augmented_readiness(readiness, variants)
    return {
        "schema": "phase3b-checkpoint-free-master-presolve-parameter-micro-matrix/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "matrix_kind": "local_checkpoint_free_master_presolve_parameter_micro_matrix_manifest_only",
        "fresh_solver_run_started_by_builder": False,
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "log_review_path": str(log_review_path),
        "source_readiness_path": str(master_readiness_path),
        "evidence": {
            "classification": review_interpretation.get("classification"),
            "review_action": review_recommendation.get("action"),
            "max_symmetry_nodes": _mapping(log_review.get("extracted_metrics")).get("max_symmetry_nodes"),
            "max_symmetry_arcs": _mapping(log_review.get("extracted_metrics")).get("max_symmetry_arcs"),
            "max_sat_presolve_vars": _mapping(log_review.get("extracted_metrics")).get("max_sat_presolve_vars"),
            "source_run_id": _mapping(log_review.get("run")).get("run_id"),
        },
        "source_audit": source_audit,
        "variants": variants,
        "augmented_readiness_packet": augmented_readiness,
        "command_matrix": _command_matrix(variants, ready=ready),
        "recommendation": {
            "action": "ready_for_single_sym0_micro_probe" if ready else "hold_manual_review",
            "next_engineering_step": (
                "run at most one 300s checkpoint-free 42x32 parameter variant, starting with sym0"
                if ready
                else "repair or review the S20 evidence and master parameter env support before executing"
            ),
            "first_candidate_id": PARAMETER_VARIANTS[0]["candidate_id"] if ready else None,
            "first_run_id": PARAMETER_VARIANTS[0]["run_id"] if ready else None,
            "blocked_actions": [
                "do_not_run_67x20_hotspot_followup_yet",
                "do_not_run_4x5_hotspot_followup_yet",
                "do_not_retry_2x10_hotspot_profile",
                "do_not_run_more_than_one_parameter_variant_per_decision",
                "do_not_extend_42x32_duration_until_one_300s_variant_is_reviewed",
                "do_not_run_full_wave_matrix",
                "do_not_promote_local_results_to_proof",
            ],
        },
        "safety": {
            "main_py_executed": False,
            "exact_campaign_used": False,
            "proof_source": False,
            "checkpoint_written": False,
            "candidate_universe_changed": False,
            "production_profile_changed": False,
            "scheduler_integration": False,
            "builder_executes_solver": False,
            "execution_enabled": False,
            "canonical_checkpoint_write_allowed": False,
        },
    }


def write_master_presolve_parameter_micro_matrix(
    matrix: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "master_presolve_parameter_micro_matrix.json"
    md_path = output_dir / "master_presolve_parameter_micro_matrix.md"
    readiness_path = output_dir / "master_presolve_parameter_augmented_readiness_packet.json"
    command_matrix_path = output_dir / "master_presolve_parameter_command_matrix.json"
    json_path.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_master_presolve_parameter_micro_matrix_markdown(matrix), encoding="utf-8")
    readiness_path.write_text(
        json.dumps(matrix.get("augmented_readiness_packet", {}), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    command_matrix_path.write_text(
        json.dumps(matrix.get("command_matrix", {}), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "json": json_path,
        "md": md_path,
        "augmented_readiness": readiness_path,
        "command_matrix": command_matrix_path,
    }


def render_master_presolve_parameter_micro_matrix_markdown(matrix: Mapping[str, Any]) -> str:
    evidence = _mapping(matrix.get("evidence"))
    recommendation = _mapping(matrix.get("recommendation"))
    lines = [
        "# Phase3B Master Presolve Parameter Micro Matrix",
        "",
        f"- Generated: `{matrix.get('generated_at')}`",
        f"- Classification: `{evidence.get('classification')}`",
        f"- Action: `{recommendation.get('action')}`",
        f"- First candidate: `{recommendation.get('first_candidate_id')}`",
        "- Fresh solver run started by builder: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "## Variants",
        "",
        "| Candidate | Env override | Risk | Eligibility |",
        "|---|---|---|---|",
    ]
    for variant in list(matrix.get("variants", []) or []):
        env = ", ".join(f"{key}={value}" for key, value in sorted(_mapping(variant.get("env")).items()))
        lines.append(
            f"| {variant.get('candidate_id')} | {env} | {variant.get('risk_level')} | {variant.get('eligibility')} |"
        )
    lines.extend(
        [
            "",
            "These variants are local, checkpoint-free, one-at-a-time diagnostics for the 42x32 master-solve presolve bottleneck. They do not change production defaults, scheduler order, proof semantics, or checkpoint behavior.",
            "",
        ]
    )
    return "\n".join(lines)


def _build_variant(source_profile: Mapping[str, Any], raw: Mapping[str, Any]) -> dict[str, Any]:
    env = {str(key): str(value) for key, value in _mapping(source_profile.get("env")).items()}
    env.update({str(key): str(value) for key, value in _mapping(raw.get("env")).items()})
    profile = {
        key: value
        for key, value in dict(source_profile).items()
        if key not in {"candidate_id", "source_kind", "source_profile_id", "planned_future_commands"}
    }
    return {
        **profile,
        "candidate_id": str(raw["candidate_id"]),
        "source_kind": "local_master_presolve_parameter_micro_matrix",
        "source_profile_id": str(raw["candidate_id"]),
        "variant_id": str(raw["variant_id"]),
        "candidate_key": HOTSPOT_CANDIDATE_KEY,
        "duration_seconds": 300,
        "process_count": 1,
        "env": env,
        "status": "not_executed_manifest_only",
        "execution_enabled": False,
        "proof_source": False,
        "checkpoint_written": False,
        "risk_level": str(raw["risk_level"]),
        "eligibility": str(raw["eligibility"]),
        "purpose": str(raw["purpose"]),
        "run_id": str(raw["run_id"]),
        "diagnostic_flags": {
            "master_cp_sat_parameter_variant": True,
            "master_cp_sat_log_heartbeat_enabled": True,
            "candidate_universe_changed": False,
            "scheduler_integration": False,
        },
    }


def _augmented_readiness(readiness: Mapping[str, Any], variants: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    variant_ids = {str(variant.get("candidate_id")) for variant in variants}
    candidates = [
        dict(candidate)
        for candidate in list(readiness.get("candidates", []) or [])
        if isinstance(candidate, Mapping) and str(candidate.get("candidate_id")) not in variant_ids
    ]
    candidates.extend(dict(variant) for variant in variants)
    existing_ids = [str(candidate_id) for candidate_id in list(readiness.get("augmented_candidate_ids", []) or [])]
    return {
        **dict(readiness),
        "packet_kind": "checkpoint_free_master_presolve_parameter_micro_matrix_readiness_local_only",
        "local_readiness_candidate_list_extended": True,
        "master_presolve_parameter_variant_candidate_ids": sorted(variant_ids),
        "augmented_candidate_ids": [*existing_ids, *sorted(variant_ids)],
        "candidates": candidates,
        "proof_source": False,
        "checkpoint_written": False,
        "production_profile_changed": False,
    }


def _command_matrix(variants: Sequence[Mapping[str, Any]], *, ready: bool) -> dict[str, Any]:
    commands: list[dict[str, Any]] = []
    for variant in variants:
        run_id = str(variant.get("run_id"))
        command = [
            "python",
            EVALUATOR_SCRIPT,
            "--execute",
            "--readiness-packet",
            str(DEFAULT_OUTPUT_DIR / "master_presolve_parameter_augmented_readiness_packet.json"),
            "--candidate-id",
            str(variant.get("candidate_id")),
            "--duration-seconds",
            "300",
            "--max-wave-candidates",
            "1",
            "--wave-candidate-key",
            HOTSPOT_CANDIDATE_KEY,
            "--run-id",
            run_id,
        ]
        commands.append(
            {
                "candidate_id": variant.get("candidate_id"),
                "candidate_key": HOTSPOT_CANDIDATE_KEY,
                "duration_seconds": 300,
                "run_id": run_id,
                "env": dict(_mapping(variant.get("env"))),
                "risk_level": variant.get("risk_level"),
                "eligibility": variant.get("eligibility"),
                "execution_enabled": False,
                "execute_command_after_review": command if ready else [],
            }
        )
    return {
        "schema": "phase3b-checkpoint-free-master-presolve-parameter-command-matrix/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "one_candidate_per_decision": True,
        "commands": commands,
    }


def _find_candidate(readiness: Mapping[str, Any], candidate_id: str) -> Mapping[str, Any]:
    for candidate in list(readiness.get("candidates", []) or []):
        if isinstance(candidate, Mapping) and str(candidate.get("candidate_id")) == str(candidate_id):
            return candidate
    raise ValueError(f"Candidate not found in readiness packet: {candidate_id}")


def _source_audit(
    *,
    project_root: Path,
    source_markers: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    for relative_path, markers in sorted(source_markers.items()):
        path = project_root / relative_path
        exists = path.exists()
        text = path.read_text(encoding="utf-8") if exists else ""
        marker_status = {marker: marker in text for marker in markers}
        sources.append(
            {
                "relative_path": relative_path,
                "exists": exists,
                "size_bytes": path.stat().st_size if exists else None,
                "sha256": _sha256(path) if exists else None,
                "marker_status": marker_status,
                "markers_present": exists and all(marker_status.values()),
            }
        )
    return {
        "source_count": len(sources),
        "all_markers_present": all(bool(item["markers_present"]) for item in sources),
        "sources": sources,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
