from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_TIMEOUT_REVIEW = ARTIFACT_ROOT / "15_hotspot_timeout_review" / "hotspot_timeout_review.json"
DEFAULT_RESOURCE_REVISION = (
    ARTIFACT_ROOT / "14_resource_strategy_revision" / "resource_strategy_revision.json"
)
DEFAULT_SCOREBOARD = ARTIFACT_ROOT / "09_checkpoint_free_scoreboard" / "checkpoint_free_eval_scoreboard.json"
DEFAULT_READINESS = ARTIFACT_ROOT / "07_short_run_readiness" / "short_run_readiness_packet.json"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "16_hotspot_narrow_strategy"
DEFAULT_AUGMENTED_READINESS = DEFAULT_OUTPUT_DIR / "hotspot_augmented_readiness_packet.json"

EVALUATOR_SCRIPT = "scripts/run_phase3b_checkpoint_free_evaluator.py"
BASELINE_PROFILE = "B0_prod_4x4"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_hotspot_narrow_strategy(
        timeout_review_path=_resolve_path(PROJECT_ROOT, args.timeout_review),
        resource_revision_path=_resolve_path(PROJECT_ROOT, args.resource_revision),
        scoreboard_path=_resolve_path(PROJECT_ROOT, args.scoreboard),
        readiness_path=_resolve_path(PROJECT_ROOT, args.readiness),
    )
    print("phase3b checkpoint-free hotspot narrow strategy")
    print(f"hotspot_key={strategy['hotspot']['candidate_key']}")
    print(f"action={strategy['recommendation']['action']}")
    print(f"proposed_profiles={len(strategy['proposed_local_profiles'])}")
    if not args.no_write:
        paths = write_hotspot_narrow_strategy(strategy, _resolve_path(PROJECT_ROOT, args.output_dir))
        print(f"strategy_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"strategy_md={_display_path(PROJECT_ROOT, paths['md'])}")
        print(f"command_matrix={_display_path(PROJECT_ROOT, paths['command_matrix'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a manifest-only narrow local profile strategy for a checkpoint-free hotspot."
    )
    parser.add_argument("--timeout-review", type=Path, default=DEFAULT_TIMEOUT_REVIEW)
    parser.add_argument("--resource-revision", type=Path, default=DEFAULT_RESOURCE_REVISION)
    parser.add_argument("--scoreboard", type=Path, default=DEFAULT_SCOREBOARD)
    parser.add_argument("--readiness", type=Path, default=DEFAULT_READINESS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_hotspot_narrow_strategy(
    *,
    timeout_review_path: Path,
    resource_revision_path: Path,
    scoreboard_path: Path,
    readiness_path: Path,
) -> dict[str, Any]:
    timeout_review = _load_json(timeout_review_path)
    resource_revision = _load_json(resource_revision_path)
    scoreboard = _load_json(scoreboard_path)
    readiness = _load_json(readiness_path)

    hotspot = _hotspot_summary(timeout_review)
    readiness_summary = _readiness_summary(readiness)
    proposed_profiles = _proposed_local_profiles(hotspot, timeout_review)
    augmented_readiness = _augmented_readiness_packet(readiness, proposed_profiles)
    current_candidates = set(readiness_summary["candidate_ids"])
    any_proposed_currently_runnable = any(
        str(profile["candidate_id"]) in current_candidates for profile in proposed_profiles
    )
    return {
        "schema": "phase3b-checkpoint-free-hotspot-narrow-strategy/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "strategy_kind": "local_checkpoint_free_hotspot_narrow_strategy_manifest_only",
        "fresh_solver_run_started_by_builder": False,
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "timeout_review_path": str(timeout_review_path),
        "resource_revision_path": str(resource_revision_path),
        "scoreboard_path": str(scoreboard_path),
        "readiness_path": str(readiness_path),
        "hotspot": hotspot,
        "current_readiness": readiness_summary,
        "evidence_summary": {
            "timeout_review_action": _mapping(timeout_review.get("recommendation")).get("action"),
            "resource_revision_action": _mapping(resource_revision.get("recommendation")).get("action"),
            "scoreboard_run_count": len(list(scoreboard.get("runs", []) or [])),
            "sensitive_path_mutation_detected": bool(
                _mapping(scoreboard.get("safety")).get("sensitive_path_mutation_detected")
            ),
        },
        "proposed_local_profiles": proposed_profiles,
        "augmented_readiness_packet": augmented_readiness,
        "augmented_readiness_requirements": _augmented_readiness_requirements(proposed_profiles),
        "recommendation": {
            "action": (
                "ready_to_plan_existing_narrow_profile_probe"
                if any_proposed_currently_runnable
                else "prepare_narrow_local_profile_readiness_extension"
            ),
            "first_candidate_profile": proposed_profiles[0]["candidate_id"] if proposed_profiles else None,
            "first_probe_duration_seconds": 300,
            "first_probe_candidate_key": hotspot["candidate_key"],
            "why_not_run_now": (
                "current_readiness_packet_has_no_single_process_hotspot_profile"
                if not readiness_summary["single_process_profile_present"]
                else "narrow_profile_still_requires_explicit_checkpoint_free_guard_review"
            ),
            "next_engineering_step": (
                "add local-only augmented readiness/evaluator support, then run exactly one 300s "
                "checkpoint-free hotspot probe if tests and guards pass"
            ),
            "blocked_actions": [
                "do_not_run_67x20_hotspot_followup_yet",
                "do_not_run_4x5_hotspot_followup_yet",
                "do_not_retry_2x10_hotspot_profile",
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
            "resource_stop_guard_required": True,
        },
    }


def write_hotspot_narrow_strategy(strategy: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "hotspot_narrow_strategy.json"
    md_path = output_dir / "hotspot_narrow_strategy.md"
    command_matrix_path = output_dir / "hotspot_narrow_command_matrix.json"
    augmented_readiness_path = output_dir / "hotspot_augmented_readiness_packet.json"
    json_path.write_text(json.dumps(strategy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_hotspot_narrow_strategy_markdown(strategy), encoding="utf-8")
    command_matrix_path.write_text(
        json.dumps(_command_matrix(strategy), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    augmented_readiness_path.write_text(
        json.dumps(strategy.get("augmented_readiness_packet", {}), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "json": json_path,
        "md": md_path,
        "command_matrix": command_matrix_path,
        "augmented_readiness": augmented_readiness_path,
    }


def render_hotspot_narrow_strategy_markdown(strategy: Mapping[str, Any]) -> str:
    hotspot = _mapping(strategy.get("hotspot"))
    readiness = _mapping(strategy.get("current_readiness"))
    recommendation = _mapping(strategy.get("recommendation"))
    lines = [
        "# Phase3B Hotspot Narrow Strategy",
        "",
        f"- Generated: `{strategy.get('generated_at')}`",
        f"- Hotspot key: `{hotspot.get('candidate_key')}`",
        f"- Prior run: `{hotspot.get('prior_run_id')}`",
        f"- Prior classification: `{hotspot.get('classification')}`",
        f"- Observed peak private GiB: `{hotspot.get('observed_peak_private_gib')}`",
        f"- Current readiness has single-process profile: `{str(readiness.get('single_process_profile_present')).lower()}`",
        f"- Action: `{recommendation.get('action')}`",
        "- Augmented readiness packet: `hotspot_augmented_readiness_packet.json`",
        "- Fresh solver run started by builder: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "- Scheduler integration: `false`",
        "",
        "## Proposed Local Profiles",
        "",
        "| Profile | Processes | Workers | Slots | Duration | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for profile in list(strategy.get("proposed_local_profiles", []) or []):
        lines.append(
            "| {candidate_id} | {process_count} | {workers} | {total_worker_slots} | {duration_seconds} | {status} |".format(
                candidate_id=profile.get("candidate_id"),
                process_count=profile.get("process_count"),
                workers=profile.get("env", {}).get("EXACT_CP_SAT_WORKERS"),
                total_worker_slots=profile.get("total_worker_slots"),
                duration_seconds=profile.get("duration_seconds"),
                status=profile.get("status"),
            )
        )
    lines.extend(
        [
            "",
            "These profiles are manifest-only until a local-only augmented readiness packet or evaluator support exists. "
            "The first future execution should be one 300s checkpoint-free `42x32` probe, not a matrix.",
            "",
        ]
    )
    return "\n".join(lines)


def _command_matrix(strategy: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "phase3b-checkpoint-free-hotspot-narrow-command-matrix/v0",
        "generated_at": strategy.get("generated_at"),
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "commands": [
            {
                "candidate_id": profile.get("candidate_id"),
                "status": profile.get("status"),
                "duration_seconds": profile.get("duration_seconds"),
                "candidate_key": profile.get("candidate_key"),
                "execute_command": profile.get("execute_command"),
                "future_execute_command_after_support": profile.get(
                    "future_execute_command_after_support"
                ),
                "stop_rules": profile.get("stop_rules"),
            }
            for profile in list(strategy.get("proposed_local_profiles", []) or [])
        ],
    }


def _hotspot_summary(timeout_review: Mapping[str, Any]) -> dict[str, Any]:
    run = _mapping(timeout_review.get("run"))
    telemetry = _mapping(timeout_review.get("telemetry_review"))
    interpretation = _mapping(timeout_review.get("interpretation"))
    recommendation = _mapping(timeout_review.get("recommendation"))
    return {
        "candidate_key": str(run.get("candidate_key") or "42x32"),
        "prior_run_id": run.get("run_id"),
        "prior_candidate_id": run.get("candidate_id"),
        "prior_status": run.get("status"),
        "prior_duration_seconds": run.get("requested_duration_seconds"),
        "classification": interpretation.get("classification"),
        "timeout_review_action": recommendation.get("action"),
        "observed_peak_private_gib": recommendation.get(
            "observed_peak_private_gib", telemetry.get("peak_total_private_gib")
        ),
        "dominant_process_peak_private_gib": telemetry.get("dominant_process_peak_private_gib"),
        "resource_stop_triggered": bool(run.get("resource_stop_triggered")),
        "sensitive_path_changed": bool(run.get("sensitive_path_changed")),
    }


def _readiness_summary(readiness: Mapping[str, Any]) -> dict[str, Any]:
    candidates = [
        _mapping(candidate)
        for candidate in list(readiness.get("candidates", []) or [])
        if isinstance(candidate, Mapping)
    ]
    slot_counts = [_total_slots(candidate) for candidate in candidates]
    return {
        "candidate_count": len(candidates),
        "candidate_ids": [str(candidate.get("candidate_id")) for candidate in candidates],
        "single_process_profile_present": any(
            int(candidate.get("process_count") or 0) == 1 for candidate in candidates
        ),
        "smallest_process_count": min(
            (int(candidate.get("process_count") or 999) for candidate in candidates),
            default=None,
        ),
        "smallest_total_worker_slots": min(slot_counts, default=None),
        "allowed_durations_seconds": list(readiness.get("allowed_durations_seconds", []) or []),
    }


def _proposed_local_profiles(
    hotspot: Mapping[str, Any],
    timeout_review: Mapping[str, Any],
) -> list[dict[str, Any]]:
    candidate_key = str(hotspot.get("candidate_key") or "42x32")
    dominant_peak = _float(hotspot.get("dominant_process_peak_private_gib")) or 0.0
    observed_peak = _float(hotspot.get("observed_peak_private_gib")) or 0.0
    specs = [
        ("local_hotspot_b0_1x4_global_normal", 4, "preserve B0 per-process CP-SAT worker count while removing cross-process fanout"),
        ("local_hotspot_b0_1x2_global_normal", 2, "halve per-process worker pressure if 1x4 still trends too high"),
        ("local_hotspot_b0_1x1_global_normal", 1, "minimum diagnostic profile for separating model size from parallelism pressure"),
    ]
    profiles = []
    for index, (candidate_id, workers, purpose) in enumerate(specs, start=1):
        risk = "high_bounded" if workers == 4 else "medium_bounded"
        profiles.append(
            _profile(
                candidate_id=candidate_id,
                candidate_key=candidate_key,
                workers=workers,
                order=index,
                risk_level=risk,
                purpose=purpose,
                observed_peak_private_gib=observed_peak,
                dominant_peak_private_gib=dominant_peak,
                timeout_review_action=_mapping(timeout_review.get("recommendation")).get("action"),
            )
        )
    return profiles


def _profile(
    *,
    candidate_id: str,
    candidate_key: str,
    workers: int,
    order: int,
    risk_level: str,
    purpose: str,
    observed_peak_private_gib: float,
    dominant_peak_private_gib: float,
    timeout_review_action: Any,
) -> dict[str, Any]:
    run_id = f"{candidate_id}_300s_{candidate_key}_narrow_eval_001"
    future = [
        "python",
        EVALUATOR_SCRIPT,
        "--execute",
        "--readiness-packet",
        str(DEFAULT_AUGMENTED_READINESS),
        "--candidate-id",
        candidate_id,
        "--duration-seconds",
        "300",
        "--max-wave-candidates",
        "1",
        "--wave-candidate-key",
        candidate_key,
        "--run-id",
        run_id,
    ]
    return {
        "candidate_id": candidate_id,
        "candidate_key": candidate_key,
        "strategy_order": order,
        "source_kind": "proposed_local_augmented_readiness_only",
        "process_count": 1,
        "env": {"EXACT_CP_SAT_WORKERS": str(workers)},
        "total_worker_slots": workers,
        "duration_seconds": 300,
        "max_wave_candidates": 1,
        "process_priority": "normal",
        "frontier_probe_mode": "explicit_candidate_key",
        "risk_level": risk_level,
        "purpose": purpose,
        "status": "blocked_until_local_augmented_readiness_support",
        "execution_enabled": False,
        "execute_command": [],
        "future_execute_command_after_support": future,
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "estimated_memory_note": {
            "prior_total_peak_private_gib": observed_peak_private_gib,
            "prior_dominant_process_peak_private_gib": dominant_peak_private_gib,
            "estimate_kind": "qualitative_from_prior_process_tree_telemetry",
            "expected_direction": "lower_total_private_memory_than_4_process_B0_probe",
        },
        "blocked_until": [
            "augmented_readiness_packet_or_evaluator_local_profile_support_exists",
            "focused_tests_pass",
            "sensitive_path_guard_confirmed",
            "timeout_review_action_remains_hold_hotspot_followups_pending_narrower_timeout_strategy",
        ],
        "stop_rules": [
            "run one narrow profile at a time",
            "duration_seconds must equal 300 for first probe",
            "stop if sensitive_path_comparison.changed=true",
            "stop if resource_stop_triggered=true",
            "stop if peak_private_memory approaches configured guard",
            "refresh scoreboard and strategy before any followup",
        ],
        "source_timeout_review_action": timeout_review_action,
    }


def _augmented_readiness_packet(
    readiness: Mapping[str, Any],
    profiles: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    packet = json.loads(json.dumps(dict(readiness), sort_keys=True))
    source_candidates = [
        candidate
        for candidate in list(packet.get("candidates", []) or [])
        if isinstance(candidate, Mapping)
    ]
    existing_ids = {str(candidate.get("candidate_id")) for candidate in source_candidates}
    added = [
        _readiness_candidate_from_profile(profile)
        for profile in profiles
        if str(profile.get("candidate_id")) not in existing_ids
    ]
    packet["schema"] = "phase3b-short-run-augmented-readiness-packet/v0"
    packet["packet_kind"] = "checkpoint_free_hotspot_augmented_readiness_local_only"
    packet["generated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    packet["source_packet_kind"] = readiness.get("packet_kind")
    packet["local_augmented_profile_source"] = "16_hotspot_narrow_strategy"
    packet["execution_enabled"] = False
    packet["proof_source"] = False
    packet["checkpoint_written"] = False
    packet["production_profile_changed"] = False
    packet["candidate_universe_changed"] = False
    packet["local_readiness_candidate_list_extended"] = bool(added)
    packet["augmented_candidate_ids"] = [str(candidate.get("candidate_id")) for candidate in added]
    packet["candidates"] = [*source_candidates, *added]
    packet["selected_candidate_ids"] = [
        *[str(value) for value in list(packet.get("selected_candidate_ids", []) or [])],
        *[str(candidate.get("candidate_id")) for candidate in added],
    ]
    return packet


def _readiness_candidate_from_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    workers = int(_mapping(profile.get("env")).get("EXACT_CP_SAT_WORKERS") or 1)
    return {
        "candidate_id": str(profile.get("candidate_id")),
        "source_kind": "s16_hotspot_narrow_strategy",
        "source_profile_id": str(profile.get("candidate_id")),
        "process_count": int(profile.get("process_count") or 1),
        "env": {"EXACT_CP_SAT_WORKERS": str(workers)},
        "risk": {
            "level": str(profile.get("risk_level") or "high_bounded"),
            "reasons": ["local_hotspot_narrow_probe", "manifest_only_until_explicit_execute"],
        },
        "process_priority": str(profile.get("process_priority") or "normal"),
        "frontier_probe_mode": "auto",
        "execution_enabled": False,
        "proof_source": False,
        "checkpoint_written": False,
        "worker_profile_kind": "global",
        "global_workers": workers,
        "total_worker_slots": int(profile.get("total_worker_slots") or workers),
        "planned_future_commands": [
            {
                "candidate_id": str(profile.get("candidate_id")),
                "duration_seconds": int(profile.get("duration_seconds") or 300),
                "command_kind": "checkpoint_free_local_hotspot_template",
                "command": list(profile.get("future_execute_command_after_support") or []),
                "env": {"EXACT_CP_SAT_WORKERS": str(workers)},
                "is_executable_now": False,
                "execution_enabled": False,
                "proof_source": False,
                "checkpoint_written": False,
                "contains_resume_campaign": False,
                "contains_checkpoint_flag": False,
                "contains_final_168h": False,
            }
        ],
    }


def _augmented_readiness_requirements(profiles: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "required_before_execution": True,
        "preferred_shape": "artifact_scoped_augmented_readiness_packet",
        "allowed_namespace": "phase3b_local_13900ks_tuning_20260430/16_hotspot_narrow_strategy",
        "must_not_change": [
            "prod_4x4_normal production default",
            "canonical checkpoint paths",
            "proof/preflight/release/viewer/frontdoor outputs",
            "production scheduler ordering",
        ],
        "candidate_ids_to_add_locally": [str(profile.get("candidate_id")) for profile in profiles],
    }


def _total_slots(candidate: Mapping[str, Any]) -> int:
    if candidate.get("total_worker_slots") is not None:
        return int(candidate.get("total_worker_slots") or 0)
    env = _mapping(candidate.get("env"))
    workers = int(env.get("EXACT_CP_SAT_WORKERS") or 1)
    return int(candidate.get("process_count") or 1) * workers


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_json(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _resolve_path(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
