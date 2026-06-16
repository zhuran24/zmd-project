from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_STAGE_REVIEW = ARTIFACT_ROOT / "18_stage_heartbeat_review" / "stage_heartbeat_review.json"
DEFAULT_AUGMENTED_READINESS = (
    ARTIFACT_ROOT / "16_hotspot_narrow_strategy" / "hotspot_augmented_readiness_packet.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "19_master_solve_micro_diagnostics"

EVALUATOR_SCRIPT = "scripts/run_phase3b_checkpoint_free_evaluator.py"
SOURCE_CANDIDATE_ID = "local_hotspot_b0_1x1_global_normal"
MICRO_CANDIDATE_ID = "local_hotspot_b0_1x1_master_log_global_normal"
HOTSPOT_CANDIDATE_KEY = "42x32"
MICRO_RUN_ID = "local_hotspot_b0_1x1_master_log_300s_42x32_eval_001"
LOG_LINE_LIMIT = 80
LOG_MAX_CHARS = 1000

SOURCE_MARKERS = {
    "src/models/master_model.py": [
        "diagnostic_log_callback",
        "log_search_progress",
        "log_callback_enabled",
    ],
    "src/search/benders_loop.py": [
        "EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_LINES",
        "master_solve_log",
    ],
}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_master_solve_micro_diagnostics(
        project_root=PROJECT_ROOT,
        stage_review_path=_resolve_path(PROJECT_ROOT, args.stage_review),
        augmented_readiness_path=_resolve_path(PROJECT_ROOT, args.augmented_readiness),
    )
    print("phase3b checkpoint-free master-solve micro diagnostics")
    print(f"action={strategy['recommendation']['action']}")
    print(f"candidate_id={strategy['diagnostic_profile']['candidate_id']}")
    if not args.no_write:
        paths = write_master_solve_micro_diagnostics(
            strategy,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"strategy_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"strategy_md={_display_path(PROJECT_ROOT, paths['md'])}")
        print(f"augmented_readiness={_display_path(PROJECT_ROOT, paths['augmented_readiness'])}")
        print(f"command_matrix={_display_path(PROJECT_ROOT, paths['command_matrix'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a local-only CP-SAT log heartbeat micro-diagnostic profile."
    )
    parser.add_argument("--stage-review", type=Path, default=DEFAULT_STAGE_REVIEW)
    parser.add_argument("--augmented-readiness", type=Path, default=DEFAULT_AUGMENTED_READINESS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_master_solve_micro_diagnostics(
    *,
    project_root: Path,
    stage_review_path: Path,
    augmented_readiness_path: Path,
    source_markers: Mapping[str, Sequence[str]] = SOURCE_MARKERS,
) -> dict[str, Any]:
    project_root = Path(project_root)
    stage_review = _load_json(stage_review_path)
    readiness = _load_json(augmented_readiness_path)
    source_profile = _find_candidate(readiness, SOURCE_CANDIDATE_ID)
    diagnostic_profile = _diagnostic_profile(source_profile)
    diagnostic_readiness = _diagnostic_readiness(readiness, diagnostic_profile)
    source_audit = _source_audit(project_root=project_root, source_markers=source_markers)
    interpretation = _mapping(stage_review.get("interpretation"))
    recommendation = _mapping(stage_review.get("recommendation"))
    ready = (
        interpretation.get("stalled_stage") == "master_solve"
        and recommendation.get("action") == "prepare_master_solve_micro_diagnostics"
        and bool(source_audit["all_markers_present"])
    )
    command = _execute_command(DEFAULT_OUTPUT_DIR / "master_solve_micro_augmented_readiness_packet.json")
    return {
        "schema": "phase3b-checkpoint-free-master-solve-micro-diagnostics/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "strategy_kind": "local_checkpoint_free_master_solve_micro_diagnostics_manifest_only",
        "fresh_solver_run_started_by_builder": False,
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "stage_review_path": str(stage_review_path),
        "source_readiness_path": str(augmented_readiness_path),
        "evidence": {
            "stalled_stage": interpretation.get("stalled_stage"),
            "stalled_reason": interpretation.get("stalled_reason"),
            "stage_review_action": recommendation.get("action"),
            "prior_run_id": _mapping(stage_review.get("run")).get("run_id"),
        },
        "instrumentation": source_audit,
        "diagnostic_profile": diagnostic_profile,
        "diagnostic_readiness_packet": diagnostic_readiness,
        "recommendation": {
            "action": "ready_for_single_master_solve_log_probe" if ready else "hold_manual_review",
            "next_engineering_step": (
                "run exactly one 300s checkpoint-free 42x32 probe with master CP-SAT log heartbeats"
                if ready
                else "repair or review master-solve diagnostic instrumentation before executing"
            ),
            "execute_command_after_review": command if ready else [],
            "required_new_output": [
                "stage_heartbeats.jsonl entries with payload.stage=master_solve_log",
                "run_summary.json execution.stage_heartbeat_count",
            ],
            "blocked_actions": [
                "do_not_run_67x20_hotspot_followup_yet",
                "do_not_run_4x5_hotspot_followup_yet",
                "do_not_retry_2x10_hotspot_profile",
                "do_not_extend_42x32_duration_without_master_solve_log_review",
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


def write_master_solve_micro_diagnostics(
    strategy: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "master_solve_micro_diagnostics.json"
    md_path = output_dir / "master_solve_micro_diagnostics.md"
    readiness_path = output_dir / "master_solve_micro_augmented_readiness_packet.json"
    command_matrix_path = output_dir / "master_solve_micro_command_matrix.json"
    json_path.write_text(json.dumps(strategy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_master_solve_micro_diagnostics_markdown(strategy), encoding="utf-8")
    readiness_path.write_text(
        json.dumps(strategy.get("diagnostic_readiness_packet", {}), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    command_matrix_path.write_text(
        json.dumps(_command_matrix(strategy), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "json": json_path,
        "md": md_path,
        "augmented_readiness": readiness_path,
        "command_matrix": command_matrix_path,
    }


def render_master_solve_micro_diagnostics_markdown(strategy: Mapping[str, Any]) -> str:
    evidence = _mapping(strategy.get("evidence"))
    profile = _mapping(strategy.get("diagnostic_profile"))
    recommendation = _mapping(strategy.get("recommendation"))
    instrumentation = _mapping(strategy.get("instrumentation"))
    lines = [
        "# Phase3B Master-Solve Micro Diagnostics",
        "",
        f"- Generated: `{strategy.get('generated_at')}`",
        f"- Stalled stage: `{evidence.get('stalled_stage')}`",
        f"- Action: `{recommendation.get('action')}`",
        f"- Candidate id: `{profile.get('candidate_id')}`",
        f"- Candidate key: `{profile.get('candidate_key')}`",
        f"- Duration seconds: `{profile.get('duration_seconds')}`",
        f"- Log heartbeat lines: `{profile.get('env', {}).get('EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_LINES')}`",
        "- Fresh solver run started by builder: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "## Source Instrumentation",
        "",
        "| Source | Exists | Markers present | SHA256 |",
        "|---|---:|---:|---|",
    ]
    for item in list(instrumentation.get("sources", []) or []):
        lines.append(
            f"| {item.get('relative_path')} | {item.get('exists')} | {item.get('markers_present')} | {item.get('sha256')} |"
        )
    lines.extend(
        [
            "",
            "This profile only enables bounded CP-SAT log heartbeat capture for the already-isolated 42x32 master-solve hotspot. It does not change production defaults, proof semantics, candidate ordering, or checkpoint behavior.",
            "",
        ]
    )
    return "\n".join(lines)


def _diagnostic_profile(source_profile: Mapping[str, Any]) -> dict[str, Any]:
    env = {str(key): str(value) for key, value in _mapping(source_profile.get("env")).items()}
    env["EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_LINES"] = str(LOG_LINE_LIMIT)
    env["EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_MAX_CHARS"] = str(LOG_MAX_CHARS)
    profile = {
        key: value
        for key, value in dict(source_profile).items()
        if key not in {"planned_future_commands"}
    }
    return {
        **profile,
        "candidate_id": MICRO_CANDIDATE_ID,
        "source_kind": "local_master_solve_micro_diagnostic",
        "source_profile_id": MICRO_CANDIDATE_ID,
        "process_count": 1,
        "env": env,
        "candidate_key": HOTSPOT_CANDIDATE_KEY,
        "duration_seconds": 300,
        "status": "not_executed_manifest_only",
        "execution_enabled": False,
        "proof_source": False,
        "checkpoint_written": False,
        "diagnostic_flags": {
            "master_cp_sat_log_heartbeat_enabled": True,
            "log_line_limit": LOG_LINE_LIMIT,
            "log_max_chars": LOG_MAX_CHARS,
        },
    }


def _diagnostic_readiness(readiness: Mapping[str, Any], profile: Mapping[str, Any]) -> dict[str, Any]:
    candidates = [
        dict(candidate)
        for candidate in list(readiness.get("candidates", []) or [])
        if isinstance(candidate, Mapping)
        and str(candidate.get("candidate_id")) != str(profile.get("candidate_id"))
    ]
    candidates.append(dict(profile))
    return {
        **dict(readiness),
        "packet_kind": "checkpoint_free_master_solve_micro_diagnostics_readiness_local_only",
        "local_readiness_candidate_list_extended": True,
        "master_solve_micro_diagnostic_candidate_id": MICRO_CANDIDATE_ID,
        "augmented_candidate_ids": [
            *[
                str(candidate_id)
                for candidate_id in list(readiness.get("augmented_candidate_ids", []) or [])
            ],
            MICRO_CANDIDATE_ID,
        ],
        "candidates": candidates,
        "proof_source": False,
        "checkpoint_written": False,
        "production_profile_changed": False,
    }


def _execute_command(readiness_path: Path) -> list[str]:
    return [
        "python",
        EVALUATOR_SCRIPT,
        "--execute",
        "--readiness-packet",
        str(readiness_path),
        "--candidate-id",
        MICRO_CANDIDATE_ID,
        "--duration-seconds",
        "300",
        "--max-wave-candidates",
        "1",
        "--wave-candidate-key",
        HOTSPOT_CANDIDATE_KEY,
        "--run-id",
        MICRO_RUN_ID,
    ]


def _command_matrix(strategy: Mapping[str, Any]) -> dict[str, Any]:
    recommendation = _mapping(strategy.get("recommendation"))
    profile = _mapping(strategy.get("diagnostic_profile"))
    return {
        "schema": "phase3b-checkpoint-free-master-solve-micro-command-matrix/v0",
        "generated_at": strategy.get("generated_at"),
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "commands": [
            {
                "candidate_id": profile.get("candidate_id"),
                "candidate_key": profile.get("candidate_key"),
                "duration_seconds": profile.get("duration_seconds"),
                "run_id": MICRO_RUN_ID,
                "env": dict(_mapping(profile.get("env"))),
                "execute_command_after_review": recommendation.get("execute_command_after_review", []),
            }
        ],
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
