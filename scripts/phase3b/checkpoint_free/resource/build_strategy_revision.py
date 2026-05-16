from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[4]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_SCOREBOARD = ARTIFACT_ROOT / "09_checkpoint_free_scoreboard" / "checkpoint_free_eval_scoreboard.json"
DEFAULT_WAVE_DIAGNOSIS = ARTIFACT_ROOT / "11_wave_straggler_diagnosis" / "checkpoint_free_wave_diagnosis.json"
DEFAULT_HOTSPOT_STRATEGY = ARTIFACT_ROOT / "13_resource_hotspot_strategy" / "resource_hotspot_strategy.json"
DEFAULT_NEXT_DECISION = ARTIFACT_ROOT / "09_checkpoint_free_scoreboard" / "checkpoint_free_next_decision.json"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "14_resource_strategy_revision"

EVALUATOR_SCRIPT = "scripts/run_phase3b_checkpoint_free_evaluator.py"
PRIMARY_CONTROL_PROFILE = "B0_prod_4x4"
LOW_MEMORY_PROFILE = "experimental_13900ks_htoff_2x10_global_normal"
COMPARABLE_PROFILE = "experimental_13900ks_htoff_4x5_global_normal"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    revision = build_resource_strategy_revision(
        scoreboard_path=_resolve_path(PROJECT_ROOT, args.scoreboard),
        wave_diagnosis_path=_resolve_path(PROJECT_ROOT, args.wave_diagnosis),
        hotspot_strategy_path=_resolve_path(PROJECT_ROOT, args.hotspot_strategy),
        next_decision_path=_resolve_path(PROJECT_ROOT, args.next_decision),
    )
    print("phase3b checkpoint-free resource strategy revision")
    print(f"action={revision['recommendation']['action']}")
    print(f"primary_probe={revision['recommendation']['primary_probe_id']}")
    print(f"probe_count={len(revision['micro_probe_plan'])}")
    if not args.no_write:
        paths = write_resource_strategy_revision(revision, _resolve_path(PROJECT_ROOT, args.output_dir))
        print(f"revision_json={_display_path(PROJECT_ROOT, paths['json'])}")
        print(f"revision_md={_display_path(PROJECT_ROOT, paths['md'])}")
        print(f"command_matrix={_display_path(PROJECT_ROOT, paths['command_matrix'])}")
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a manifest-only resource strategy revision for checkpoint-free hotspot probes."
    )
    parser.add_argument("--scoreboard", type=Path, default=DEFAULT_SCOREBOARD)
    parser.add_argument("--wave-diagnosis", type=Path, default=DEFAULT_WAVE_DIAGNOSIS)
    parser.add_argument("--hotspot-strategy", type=Path, default=DEFAULT_HOTSPOT_STRATEGY)
    parser.add_argument("--next-decision", type=Path, default=DEFAULT_NEXT_DECISION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_resource_strategy_revision(
    *,
    scoreboard_path: Path,
    wave_diagnosis_path: Path,
    hotspot_strategy_path: Path,
    next_decision_path: Path,
) -> dict[str, Any]:
    scoreboard = _load_json(scoreboard_path)
    wave_diagnosis = _load_json(wave_diagnosis_path)
    hotspot_strategy = _load_json(hotspot_strategy_path)
    next_decision = _load_json(next_decision_path)
    runs = [_mapping(run) for run in list(scoreboard.get("runs", []) or []) if isinstance(run, Mapping)]
    avoid_keys = _avoid_keys(hotspot_strategy, runs)
    completed_no_hotspot = _completed_no_hotspot_runs(runs, avoid_keys)
    hotspot_failures = _hotspot_failure_runs(runs, avoid_keys)
    profile_rows = _profile_rows(runs, completed_no_hotspot, hotspot_failures)
    primary_key = "42x32" if "42x32" in avoid_keys else (avoid_keys[0] if avoid_keys else None)
    secondary_keys = [key for key in avoid_keys if key != primary_key]
    micro_probe_plan = _micro_probe_plan(primary_key, secondary_keys, profile_rows, runs)
    primary_probe = micro_probe_plan[0] if micro_probe_plan else None
    action = _recommendation_action(primary_probe)
    reduced = _mapping(_mapping(next_decision.get("recommendation")).get("reduced_frontier_no_hotspots"))
    return {
        "schema": "phase3b-checkpoint-free-resource-strategy-revision/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "revision_kind": "local_checkpoint_free_resource_strategy_revision",
        "fresh_solver_run_started_by_builder": False,
        "proof_source": False,
        "checkpoint_written": False,
        "scheduler_integration": False,
        "candidate_universe_changed": False,
        "scoreboard_path": str(scoreboard_path),
        "wave_diagnosis_path": str(wave_diagnosis_path),
        "hotspot_strategy_path": str(hotspot_strategy_path),
        "next_decision_path": str(next_decision_path),
        "evidence_summary": {
            "avoid_candidate_keys": avoid_keys,
            "completed_no_hotspot_candidate_ids": [
                str(run.get("candidate_id")) for run in completed_no_hotspot
            ],
            "hotspot_failure_run_ids": [str(run.get("run_id")) for run in hotspot_failures],
            "wave_diagnosis_summary": _mapping(wave_diagnosis.get("summary")),
            "next_decision_action": _mapping(next_decision.get("recommendation")).get("action"),
            "reduced_frontier_action": reduced.get("action"),
            "sensitive_path_mutation_detected": bool(
                _mapping(scoreboard.get("safety")).get("sensitive_path_mutation_detected")
            ),
        },
        "profile_rows": profile_rows,
        "micro_probe_plan": micro_probe_plan,
        "recommendation": {
            "action": action,
            "primary_probe_id": primary_probe.get("probe_id") if primary_probe else None,
            "primary_command": primary_probe.get("execute_command") if primary_probe else [],
            "stop_after_primary_if": [
                "sensitive_path_comparison.changed=true",
                "resource_stop_triggered=true",
                "status not in completed,timeout,stopped_resource_limit",
            ],
            "blocked_actions": [
                "do_not_run_full_wave_matrix",
                "do_not_retry_2x10_hotspot_profile_without_new_cap",
                "do_not_run_secondary_hotspot_probe_after_primary_resource_stop",
                "do_not_promote_local_results_to_proof",
            ],
            "next_step_after_primary_success": (
                "run the secondary hotspot key under the same profile only if primary completes without resource stop"
                if secondary_keys
                else "refresh scoreboards and resource strategy"
            ),
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
            "resource_stop_guard_required": True,
        },
    }


def write_resource_strategy_revision(revision: Mapping[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "resource_strategy_revision.json"
    md_path = output_dir / "resource_strategy_revision.md"
    command_matrix_path = output_dir / "resource_strategy_command_matrix.json"
    json_path.write_text(json.dumps(revision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_resource_strategy_revision_markdown(revision), encoding="utf-8")
    command_matrix_path.write_text(
        json.dumps(_command_matrix(revision), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"json": json_path, "md": md_path, "command_matrix": command_matrix_path}


def render_resource_strategy_revision_markdown(revision: Mapping[str, Any]) -> str:
    recommendation = _mapping(revision.get("recommendation"))
    evidence = _mapping(revision.get("evidence_summary"))
    lines = [
        "# Phase3B Resource Strategy Revision",
        "",
        f"- Generated: `{revision.get('generated_at')}`",
        f"- Action: `{recommendation.get('action')}`",
        "- Fresh solver run started by builder: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "- Scheduler integration: `false`",
        f"- Avoid keys: `{', '.join(evidence.get('avoid_candidate_keys', []))}`",
        f"- Reduced frontier action: `{evidence.get('reduced_frontier_action')}`",
        "",
        "## Micro-Probe Plan",
        "",
        "| Probe | Candidate | Key | Duration | Risk | Status |",
        "|---|---|---:|---:|---|---|",
    ]
    for probe in revision.get("micro_probe_plan", []):
        lines.append(
            "| {probe_id} | {candidate_id} | {candidate_key} | {duration_seconds} | {risk_level} | {status} |".format(
                probe_id=probe.get("probe_id"),
                candidate_id=probe.get("candidate_id"),
                candidate_key=probe.get("candidate_key"),
                duration_seconds=probe.get("duration_seconds"),
                risk_level=probe.get("risk_level"),
                status=probe.get("status"),
            )
        )
    action = str(recommendation.get("action") or "")
    if action == "hold_primary_hotspot_probe_timeout_review":
        guidance = (
            "The primary hotspot probe has already run and timed out without resource stop or sensitive-path mutation. "
            "Do not run secondary hotspot probes until this timeout is reviewed and a narrower follow-up strategy is chosen."
        )
    elif action == "prepare_single_hotspot_micro_probe":
        guidance = (
            "Only the primary probe should be considered next, and only as a bounded checkpoint-free diagnostic with the existing resource-stop guard."
        )
    else:
        guidance = "Hold further hotspot probes until the resource strategy is reviewed."
    lines.extend(
        [
            "",
            f"{guidance} This artifact does not authorize full-wave retry, canonical checkpoints, proof promotion, production default changes, or scheduler integration.",
            "",
        ]
    )
    return "\n".join(lines)


def _command_matrix(revision: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "phase3b-checkpoint-free-resource-strategy-command-matrix/v0",
        "generated_at": revision.get("generated_at"),
        "proof_source": False,
        "checkpoint_written": False,
        "commands": [
            {
                "probe_id": probe.get("probe_id"),
                "status": probe.get("status"),
                "execute_command": probe.get("execute_command"),
                "plan_only_command": probe.get("plan_only_command"),
                "stop_rules": probe.get("stop_rules"),
            }
            for probe in revision.get("micro_probe_plan", [])
        ],
    }


def _micro_probe_plan(
    primary_key: str | None,
    secondary_keys: Sequence[str],
    profile_rows: Sequence[Mapping[str, Any]],
    runs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not primary_key:
        return []
    existing_primary = _existing_explicit_key_run(runs, PRIMARY_CONTROL_PROFILE, primary_key)
    primary_status, primary_executable, primary_risk = _primary_probe_status(existing_primary)
    probes: list[dict[str, Any]] = []
    probes.append(
        _probe(
            probe_id=f"{PRIMARY_CONTROL_PROFILE}_300s_{primary_key}_resource_probe_001",
            candidate_id=PRIMARY_CONTROL_PROFILE,
            candidate_key=primary_key,
            rationale=(
                "Use the production-default profile as the first changed-resource-strategy control for the hotspot key."
            ),
            status=primary_status,
            risk_level=primary_risk,
            executable=primary_executable,
            existing_run_id=existing_primary.get("run_id") if existing_primary else None,
        )
    )
    secondary_status = (
        "ready_after_primary_completed_clean"
        if primary_status == "completed_primary_probe_clean"
        else "blocked_until_primary_probe_clean"
    )
    for key in secondary_keys:
        probes.append(
            _probe(
                probe_id=f"{PRIMARY_CONTROL_PROFILE}_300s_{key}_resource_probe_001",
                candidate_id=PRIMARY_CONTROL_PROFILE,
                candidate_key=key,
                rationale="Only run after the primary hotspot probe completes without resource stop.",
                status=secondary_status,
                risk_level="high_bounded",
                executable=primary_status == "completed_primary_probe_clean",
            )
        )
    if _has_profile(profile_rows, COMPARABLE_PROFILE):
        probes.append(
            _probe(
                probe_id=f"{COMPARABLE_PROFILE}_300s_{primary_key}_resource_probe_001",
                candidate_id=COMPARABLE_PROFILE,
                candidate_key=primary_key,
                rationale="Compare a 4-process/5-worker profile only if the B0 hotspot probe is non-mutating and informative.",
                status=(
                    "blocked_pending_primary_timeout_review"
                    if primary_status == "primary_probe_timeout_no_resource_stop_review_required"
                    else "blocked_until_b0_hotspot_probe_review"
                ),
                risk_level="high_bounded",
                executable=False,
            )
        )
    if _has_profile(profile_rows, LOW_MEMORY_PROFILE):
        probes.append(
            _probe(
                probe_id=f"{LOW_MEMORY_PROFILE}_300s_{primary_key}_resource_probe_retry_blocked",
                candidate_id=LOW_MEMORY_PROFILE,
                candidate_key=primary_key,
                rationale="2x10 already resource-stopped on isolated hotspot keys; retry requires a new cap or evaluator change.",
                status="blocked_prior_resource_stop",
                risk_level="known_resource_stop",
                executable=False,
            )
        )
    return probes


def _probe(
    *,
    probe_id: str,
    candidate_id: str,
    candidate_key: str,
    rationale: str,
    status: str,
    risk_level: str,
    executable: bool = True,
    existing_run_id: str | None = None,
) -> dict[str, Any]:
    run_id = probe_id.replace("_resource_probe_", "_resource_probe_eval_")
    base = [
        "python",
        EVALUATOR_SCRIPT,
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
        "probe_id": probe_id,
        "candidate_id": candidate_id,
        "candidate_key": candidate_key,
        "duration_seconds": 300,
        "max_wave_candidates": 1,
        "risk_level": risk_level,
        "status": status,
        "rationale": rationale,
        "existing_run_id": existing_run_id,
        "plan_only_command": base,
        "execute_command": [base[0], base[1], "--execute", *base[2:]] if executable else [],
        "execution_enabled_by_builder": False,
        "checkpoint_free": True,
        "proof_source": False,
        "checkpoint_written": False,
        "resource_stop_guard_required": True,
        "stop_rules": [
            "run one probe at a time",
            "stop if sensitive_path_comparison.changed=true",
            "stop if resource_stop_triggered=true",
            "do not run followups until scoreboards and strategy are refreshed",
        ],
    }


def _recommendation_action(primary_probe: Mapping[str, Any] | None) -> str:
    if not primary_probe:
        return "hold_no_hotspot_keys_available"
    status = str(primary_probe.get("status") or "")
    if status == "ready_for_single_checkpoint_free_probe":
        return "prepare_single_hotspot_micro_probe"
    if status == "completed_primary_probe_clean":
        return "prepare_secondary_hotspot_micro_probe"
    if status == "primary_probe_timeout_no_resource_stop_review_required":
        return "hold_primary_hotspot_probe_timeout_review"
    if status in {"blocked_primary_resource_stop", "blocked_primary_sensitive_path_changed"}:
        return "hold_primary_hotspot_probe_failed"
    return "hold_resource_strategy_manual_review"


def _existing_explicit_key_run(
    runs: Sequence[Mapping[str, Any]],
    candidate_id: str,
    candidate_key: str,
) -> Mapping[str, Any] | None:
    matches = []
    for run in runs:
        if str(run.get("candidate_id")) != candidate_id:
            continue
        keys = {str(key) for key in list(run.get("wave_candidate_keys", []) or [])}
        requested = {str(key) for key in list(run.get("wave_requested_candidate_keys", []) or [])}
        if candidate_key not in keys and candidate_key not in requested:
            continue
        if int(run.get("wave_max_candidates") or 0) != 1:
            continue
        if "_resource_probe_eval_" not in str(run.get("run_id") or ""):
            continue
        matches.append(run)
    return max(matches, key=lambda run: str(run.get("run_id") or ""), default=None)


def _primary_probe_status(run: Mapping[str, Any] | None) -> tuple[str, bool, str]:
    if not run:
        return ("ready_for_single_checkpoint_free_probe", True, "high_bounded")
    if bool(run.get("sensitive_path_changed")):
        return ("blocked_primary_sensitive_path_changed", False, "disqualified")
    if bool(run.get("resource_stop_triggered")):
        return ("blocked_primary_resource_stop", False, "resource_stop_observed")
    status = str(run.get("status") or "")
    if status == "completed":
        return ("completed_primary_probe_clean", False, "observed_clean")
    if bool(run.get("timed_out")) or status == "timeout":
        return ("primary_probe_timeout_no_resource_stop_review_required", False, "hotspot_timeout")
    return ("primary_probe_finished_unknown_status_review_required", False, "review_required")


def _profile_rows(
    runs: Sequence[Mapping[str, Any]],
    completed_no_hotspot: Sequence[Mapping[str, Any]],
    hotspot_failures: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    candidates = sorted({str(run.get("candidate_id")) for run in runs if run.get("candidate_id")})
    rows = []
    for candidate_id in candidates:
        candidate_runs = [run for run in runs if str(run.get("candidate_id")) == candidate_id]
        no_hotspot_runs = [run for run in completed_no_hotspot if str(run.get("candidate_id")) == candidate_id]
        hotspot_runs = [run for run in hotspot_failures if str(run.get("candidate_id")) == candidate_id]
        best_clean = min(
            no_hotspot_runs,
            key=lambda run: _float(run.get("peak_private_gib")) or 999.0,
            default=None,
        )
        rows.append(
            {
                "candidate_id": candidate_id,
                "run_count": len(candidate_runs),
                "completed_no_hotspot_run_id": best_clean.get("run_id") if best_clean else None,
                "completed_no_hotspot_peak_private_gib": best_clean.get("peak_private_gib") if best_clean else None,
                "hotspot_failure_run_ids": [str(run.get("run_id")) for run in hotspot_runs],
                "any_resource_stop_triggered": any(bool(run.get("resource_stop_triggered")) for run in candidate_runs),
                "any_timeout": any(bool(run.get("timed_out")) for run in candidate_runs),
            }
        )
    return rows


def _completed_no_hotspot_runs(runs: Sequence[Mapping[str, Any]], avoid_keys: Sequence[str]) -> list[Mapping[str, Any]]:
    required = set(avoid_keys)
    rows = []
    for run in runs:
        if str(run.get("status") or "") != "completed":
            continue
        if run.get("resource_stop_triggered") or run.get("sensitive_path_changed"):
            continue
        excluded = {str(key) for key in list(run.get("wave_excluded_candidate_keys", []) or [])}
        if required and not required.issubset(excluded):
            continue
        rows.append(run)
    return rows


def _hotspot_failure_runs(runs: Sequence[Mapping[str, Any]], avoid_keys: Sequence[str]) -> list[Mapping[str, Any]]:
    hotspots = set(avoid_keys)
    rows = []
    for run in runs:
        candidate_keys = {str(key) for key in list(run.get("wave_candidate_keys", []) or [])}
        if not candidate_keys.intersection(hotspots):
            continue
        if bool(run.get("resource_stop_triggered")) or bool(run.get("timed_out")):
            rows.append(run)
    return rows


def _avoid_keys(hotspot_strategy: Mapping[str, Any], runs: Sequence[Mapping[str, Any]]) -> list[str]:
    recommendation = _mapping(hotspot_strategy.get("recommendation"))
    keys = [
        str(key)
        for key in list(recommendation.get("avoid_candidate_keys_for_wave_expansion", []) or [])
        if str(key)
    ]
    if keys:
        return sorted(set(keys))
    inferred = {
        str(key)
        for run in runs
        if bool(run.get("resource_stop_triggered"))
        for key in list(run.get("wave_candidate_keys", []) or [])
        if str(key)
    }
    return sorted(inferred)


def _has_profile(profile_rows: Sequence[Mapping[str, Any]], candidate_id: str) -> bool:
    return any(str(row.get("candidate_id")) == candidate_id for row in profile_rows)


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
