from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_NARROW_REVIEW = (
    ARTIFACT_ROOT / "16_hotspot_narrow_strategy" / "hotspot_narrow_result_review.json"
)
DEFAULT_AUGMENTED_READINESS = (
    ARTIFACT_ROOT / "16_hotspot_narrow_strategy" / "hotspot_augmented_readiness_packet.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "17_hotspot_algorithmic_strategy"

EVALUATOR_SCRIPT = "scripts/run_phase3b_checkpoint_free_evaluator.py"
HOTSPOT_CANDIDATE_ID = "local_hotspot_b0_1x1_global_normal"
HOTSPOT_CANDIDATE_KEY = "42x32"
STAGE_HEARTBEAT_RUN_ID = (
    "local_hotspot_b0_1x1_global_normal_300s_42x32_stage_heartbeat_eval_001"
)

SOURCE_MARKERS = {
    "src/search/benders_loop.py": ["heartbeat_callback", "_emit_campaign_heartbeat"],
    "src/search/exact_parallel_scheduler.py": ["heartbeat_events", "message_type\": \"HEARTBEAT"],
    "src/runtime/checkpoint_free_evaluator.py": ["stage_heartbeats_jsonl", "stage_heartbeat_count"],
}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_hotspot_algorithmic_strategy(
        project_root=PROJECT_ROOT,
        narrow_review_path=_resolve_path(PROJECT_ROOT, args.narrow_review),
        augmented_readiness_path=_resolve_path(PROJECT_ROOT, args.augmented_readiness),
    )
    print("phase3b checkpoint-free hotspot algorithmic strategy")
    print(f"classification={strategy['evidence']['classification']}")
    print(f"action={strategy['recommendation']['action']}")
    if not args.no_write:
        paths = write_hotspot_algorithmic_strategy(
            strategy,
            _resolve_path(PROJECT_ROOT, args.output_dir),
        )
        print(f"strategy_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"strategy_md={_display_path(PROJECT_ROOT, paths['md'])}")
        print(f"command_matrix={_display_path(PROJECT_ROOT, paths['command_matrix'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a manifest-only algorithmic strategy after the 42x32 hotspot remains a "
            "memory-controlled compute straggler."
        )
    )
    parser.add_argument("--narrow-review", type=Path, default=DEFAULT_NARROW_REVIEW)
    parser.add_argument("--augmented-readiness", type=Path, default=DEFAULT_AUGMENTED_READINESS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_hotspot_algorithmic_strategy(
    *,
    project_root: Path,
    narrow_review_path: Path,
    augmented_readiness_path: Path,
    source_markers: Mapping[str, Sequence[str]] = SOURCE_MARKERS,
) -> dict[str, Any]:
    project_root = Path(project_root)
    narrow_review = _load_json(narrow_review_path)
    interpretation = _mapping(narrow_review.get("interpretation"))
    recommendation = _mapping(narrow_review.get("recommendation"))
    source_audit = _source_audit(project_root=project_root, source_markers=source_markers)
    instrumentation_ready = bool(source_audit["all_markers_present"])
    evidence_action = str(recommendation.get("action") or "")
    classification = str(interpretation.get("classification") or "")
    expected_hold_state = (
        evidence_action == "hold_hotspot_algorithmic_strategy_review"
        and classification == "memory_controlled_compute_straggler_at_600s"
    )
    probe_command = _stage_heartbeat_probe_command(augmented_readiness_path)
    action = (
        "ready_for_single_stage_heartbeat_probe"
        if expected_hold_state and instrumentation_ready
        else "hold_until_stage_heartbeat_instrumentation_verified"
        if expected_hold_state
        else "hold_manual_review"
    )
    return {
        "schema": "phase3b-checkpoint-free-hotspot-algorithmic-strategy/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "strategy_kind": "local_checkpoint_free_hotspot_algorithmic_strategy_manifest_only",
        "fresh_solver_run_started_by_builder": False,
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "narrow_review_path": str(narrow_review_path),
        "augmented_readiness_path": str(augmented_readiness_path),
        "evidence": {
            "classification": classification,
            "narrow_review_action": evidence_action,
            "runs_reviewed": len(list(narrow_review.get("runs", []) or []))
            + len(list(narrow_review.get("confirmation_runs", []) or [])),
            "confirmation_600s_present": interpretation.get("confirmation_600s_present"),
            "confirmation_600s_timeout_no_result": interpretation.get(
                "confirmation_600s_timeout_no_result"
            ),
        },
        "instrumentation": source_audit,
        "recommendation": {
            "action": action,
            "next_engineering_step": (
                "run exactly one 300s 1x1 checkpoint-free stage-heartbeat probe for 42x32"
                if action == "ready_for_single_stage_heartbeat_probe"
                else "finish and verify stage-heartbeat instrumentation before any new hotspot run"
                if expected_hold_state
                else "review hotspot evidence before selecting another run"
            ),
            "first_probe_candidate_id": HOTSPOT_CANDIDATE_ID
            if action == "ready_for_single_stage_heartbeat_probe"
            else None,
            "first_probe_candidate_key": HOTSPOT_CANDIDATE_KEY
            if action == "ready_for_single_stage_heartbeat_probe"
            else None,
            "first_probe_duration_seconds": 300
            if action == "ready_for_single_stage_heartbeat_probe"
            else None,
            "first_probe_run_id": STAGE_HEARTBEAT_RUN_ID
            if action == "ready_for_single_stage_heartbeat_probe"
            else None,
            "execute_command_after_review": probe_command
            if action == "ready_for_single_stage_heartbeat_probe"
            else [],
            "required_new_output": [
                "stage_heartbeats.jsonl",
                "run_summary.json execution.stage_heartbeat_count",
            ],
            "blocked_actions": [
                "do_not_run_67x20_hotspot_followup_yet",
                "do_not_run_4x5_hotspot_followup_yet",
                "do_not_retry_2x10_hotspot_profile",
                "do_not_extend_42x32_duration_without_stage_evidence",
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


def write_hotspot_algorithmic_strategy(
    strategy: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "hotspot_algorithmic_strategy.json"
    md_path = output_dir / "hotspot_algorithmic_strategy.md"
    command_matrix_path = output_dir / "hotspot_stage_heartbeat_command_matrix.json"
    json_path.write_text(json.dumps(strategy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_hotspot_algorithmic_strategy_markdown(strategy), encoding="utf-8")
    command_matrix_path.write_text(
        json.dumps(_command_matrix(strategy), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"json": json_path, "md": md_path, "command_matrix": command_matrix_path}


def render_hotspot_algorithmic_strategy_markdown(strategy: Mapping[str, Any]) -> str:
    evidence = _mapping(strategy.get("evidence"))
    instrumentation = _mapping(strategy.get("instrumentation"))
    recommendation = _mapping(strategy.get("recommendation"))
    lines = [
        "# Phase3B Hotspot Algorithmic Strategy",
        "",
        f"- Generated: `{strategy.get('generated_at')}`",
        f"- Classification: `{evidence.get('classification')}`",
        f"- Narrow review action: `{evidence.get('narrow_review_action')}`",
        f"- Stage-heartbeat instrumentation ready: `{instrumentation.get('all_markers_present')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- Fresh solver run started by builder: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "- Scheduler integration: `false`",
        "",
        "## Next Probe",
        "",
        f"- Candidate id: `{recommendation.get('first_probe_candidate_id')}`",
        f"- Candidate key: `{recommendation.get('first_probe_candidate_key')}`",
        f"- Duration seconds: `{recommendation.get('first_probe_duration_seconds')}`",
        f"- Run id: `{recommendation.get('first_probe_run_id')}`",
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
            "This is a manifest-only strategy. The next run, when performed, is one bounded checkpoint-free diagnostic to collect stage heartbeats for the 42x32 straggler.",
            "",
        ]
    )
    return "\n".join(lines)


def _command_matrix(strategy: Mapping[str, Any]) -> dict[str, Any]:
    recommendation = _mapping(strategy.get("recommendation"))
    return {
        "schema": "phase3b-checkpoint-free-hotspot-stage-heartbeat-command-matrix/v0",
        "generated_at": strategy.get("generated_at"),
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "commands": [
            {
                "candidate_id": recommendation.get("first_probe_candidate_id"),
                "candidate_key": recommendation.get("first_probe_candidate_key"),
                "duration_seconds": recommendation.get("first_probe_duration_seconds"),
                "run_id": recommendation.get("first_probe_run_id"),
                "status": recommendation.get("action"),
                "execute_command_after_review": recommendation.get("execute_command_after_review", []),
            }
        ],
    }


def _stage_heartbeat_probe_command(augmented_readiness_path: Path) -> list[str]:
    return [
        "python",
        EVALUATOR_SCRIPT,
        "--execute",
        "--readiness-packet",
        str(augmented_readiness_path),
        "--candidate-id",
        HOTSPOT_CANDIDATE_ID,
        "--duration-seconds",
        "300",
        "--max-wave-candidates",
        "1",
        "--wave-candidate-key",
        HOTSPOT_CANDIDATE_KEY,
        "--run-id",
        STAGE_HEARTBEAT_RUN_ID,
    ]


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
