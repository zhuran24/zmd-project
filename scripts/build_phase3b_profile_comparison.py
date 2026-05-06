from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json


DEFAULT_CAMPAIGN_STATE = Path(
    r"E:\phase3b_workspaces\endfield_phase3b_b5_anchor_selected_block_pose30_20260422_2235\data\checkpoints\exact_campaign_state.json"
)
DEFAULT_OUTPUT_DIR = Path(
    ".artifacts/phase3b_profile_comparison_67x13_anchors119_123_124_125_20260423"
)
DEFAULT_LOG_DIR = Path(
    ".codex_test_logs/phase3b/profile_comparison_67x13_anchors119_123_124_125_20260423"
)


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = _resolve_path(project_root, args.output_dir)
    log_dir = _resolve_path(project_root, args.log_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    anchors = _parse_csv(args.anchor_indices)
    profiles = _profile_definitions()
    selected_profiles = [
        profile
        for profile in profiles
        if not args.profiles or profile["profile_id"] in set(_parse_csv(args.profiles))
    ]
    if not selected_profiles:
        raise SystemExit("No profiles selected")

    records: list[dict[str, Any]] = []
    for profile in selected_profiles:
        profile_id = str(profile["profile_id"])
        profile_output_dir = output_dir / "raw" / profile_id
        profile_output_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = log_dir / f"{profile_id}.stdout.log"
        stderr_path = log_dir / f"{profile_id}.stderr.log"
        command = [
            sys.executable,
            str(project_root / "scripts" / "build_phase3b_forced_anchor_proto_reduction.py"),
            "--project-root",
            str(project_root),
            "--campaign-state",
            str(args.campaign_state),
            "--candidate",
            str(args.candidate),
            "--anchor-indices",
            ",".join(anchors),
            "--time-limit-seconds",
            str(float(args.time_limit_seconds)),
            "--worker-count",
            str(int(args.worker_count)),
            "--variants",
            "base",
            "--solver-profile-json",
            json.dumps(profile["solver_profile"], separators=(",", ":")),
            "--output-dir",
            str(profile_output_dir),
        ]
        env = os.environ.copy()
        env.update({str(key): str(value) for key, value in profile["env"].items()})
        if args.dry_run:
            records.append(
                {
                    "profile_id": profile_id,
                    "status": "DRY_RUN",
                    "command": command,
                    "env": dict(profile["env"]),
                    "output_dir": _display_path(project_root, profile_output_dir),
                }
            )
            continue
        proc = subprocess.run(
            command,
            cwd=project_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        stdout_path.write_text(proc.stdout, encoding="utf-8")
        stderr_path.write_text(proc.stderr, encoding="utf-8")
        report_path = profile_output_dir / "forced_anchor_proto_reduction.json"
        report = _load_json(report_path)
        records.append(
            _record_from_report(
                profile=profile,
                report=report,
                report_path=report_path,
                command=command,
                exit_code=int(proc.returncode),
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                project_root=project_root,
            )
        )

    summary = _build_summary(
        project_root=project_root,
        campaign_state=Path(args.campaign_state),
        candidate=str(args.candidate),
        anchors=anchors,
        time_limit_seconds=float(args.time_limit_seconds),
        worker_count=int(args.worker_count),
        records=records,
    )
    if not args.no_write:
        atomic_write_json(output_dir / "summary.json", summary)
        _write_text(output_dir / "summary.md", _render_markdown(summary))
        _write_text(output_dir / "compact_table.txt", _render_text(summary))
    print("phase3b profile comparison")
    print(f"- output_dir: {_display_path(project_root, output_dir)}")
    print(f"- profiles: {[record.get('profile_id') for record in records]}")
    print(f"- outcome: {summary['status']['outcome']}")
    print(f"- recommendation: {summary['status']['recommendation']}")
    return 0 if all(int(record.get("exit_code", 0)) == 0 for record in records if record.get("status") != "DRY_RUN") else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare Phase3B forced-anchor profiles across selected anchors."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--campaign-state", type=Path, default=DEFAULT_CAMPAIGN_STATE)
    parser.add_argument("--candidate", default="67x13")
    parser.add_argument("--anchor-indices", default="119,123,124,125")
    parser.add_argument("--time-limit-seconds", type=float, default=60.0)
    parser.add_argument("--worker-count", type=int, default=1)
    parser.add_argument("--profiles", default="")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def _profile_definitions() -> list[dict[str, Any]]:
    default_fixed_probe = {
        "search_branching": "fixed",
        "cp_model_probing_level": 3,
        "symmetry_level": 3,
        "worker_count": 1,
        "hint_conflict_limit": 1000,
        "random_seed": 1,
        "randomize_search": False,
        "log_search_progress": True,
        "log_to_stdout": True,
    }
    low_encoding = {
        "search_branching": "fixed",
        "cp_model_probing_level": 0,
        "symmetry_level": 0,
        "worker_count": 1,
        "hint_conflict_limit": 0,
        "random_seed": 1,
        "randomize_search": False,
        "boolean_encoding_level": 0,
        "max_domain_size_for_linear2_expansion": 0,
        "max_domain_size_when_encoding_eq_neq_constraints": 0,
        "cp_model_presolve": True,
        "cp_model_use_sat_presolve": False,
        "find_clauses_that_are_exactly_one": False,
        "presolve_use_bva": False,
        "linearization_level": 0,
        "log_search_progress": True,
        "log_to_stdout": True,
    }
    return [
        {
            "profile_id": "base_default_fixed_probe3_sym3",
            "label": "base/default formulation with fixed probe3 sym3 solver",
            "diagnostic_semantics": "diagnostic_not_proof_source",
            "env": {"PYTHONPATH": "."},
            "solver_profile": {
                "profile_id": "base_default_fixed_probe3_sym3_1w",
                **default_fixed_probe,
            },
        },
        {
            "profile_id": "base_delta_interval_fixed_probe3_sym3",
            "label": "base/default formulation with selected-cover delta interval",
            "diagnostic_semantics": "diagnostic_not_proof_source",
            "env": {
                "PYTHONPATH": ".",
                "EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING": "delta",
            },
            "solver_profile": {
                "profile_id": "base_delta_interval_fixed_probe3_sym3_1w",
                **default_fixed_probe,
            },
        },
        {
            "profile_id": "selected_block_block64_all_templates",
            "label": "selected-block block64 all-template formulation",
            "diagnostic_semantics": "diagnostic_not_proof_source",
            "env": {
                "PYTHONPATH": ".",
                "EXACT_POWER_FAMILY_LOOKUP_ENCODING": "linear_shell_guards",
                "EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING": "linear_minmax",
                "EXACT_POWER_COVERAGE_WITNESS_ENCODING": "block_element",
                "EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY": "selected_block",
                "EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE": "64",
                "EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES": "",
            },
            "solver_profile": {
                "profile_id": "selected_block_block64_all_templates_fixed_probe3_sym3_1w",
                **default_fixed_probe,
            },
        },
        {
            "profile_id": "block64_all_templates_low_encoding_linearization0",
            "label": "block64 all-template low-encoding linearization0",
            "diagnostic_semantics": "diagnostic_not_proof_source",
            "env": {
                "PYTHONPATH": ".",
                "EXACT_POWER_FAMILY_LOOKUP_ENCODING": "linear_shell_guards",
                "EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING": "linear_minmax",
                "EXACT_POWER_COVERAGE_WITNESS_ENCODING": "block_element",
                "EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY": "final_target",
                "EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE": "64",
                "EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES": "",
            },
            "solver_profile": {
                "profile_id": "block64_all_templates_final_target_low_encoding_linearization0_fixed_1w",
                **low_encoding,
            },
        },
        {
            "profile_id": "block64_all_templates_low_encoding_linearization0_delta_interval",
            "label": "block64 all-template low-encoding linearization0 with selected-cover delta interval",
            "diagnostic_semantics": "diagnostic_not_proof_source",
            "env": {
                "PYTHONPATH": ".",
                "EXACT_POWER_FAMILY_LOOKUP_ENCODING": "linear_shell_guards",
                "EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING": "linear_minmax",
                "EXACT_POWER_COVERAGE_WITNESS_ENCODING": "block_element",
                "EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY": "final_target",
                "EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE": "64",
                "EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES": "",
                "EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING": "delta",
            },
            "solver_profile": {
                "profile_id": "block64_all_templates_final_target_delta_interval_low_encoding_linearization0_fixed_1w",
                **low_encoding,
            },
        },
        {
            "profile_id": "block64_protocol_only_low_encoding_linearization0",
            "label": "block64 protocol-only low-encoding linearization0",
            "diagnostic_semantics": "diagnostic_not_proof_source",
            "env": {
                "PYTHONPATH": ".",
                "EXACT_POWER_FAMILY_LOOKUP_ENCODING": "linear_shell_guards",
                "EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING": "linear_minmax",
                "EXACT_POWER_COVERAGE_WITNESS_ENCODING": "block_element",
                "EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY": "final_target",
                "EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE": "64",
                "EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES": "protocol_storage_box",
            },
            "solver_profile": {
                "profile_id": "block64_protocol_only_final_target_low_encoding_linearization0_fixed_1w",
                **low_encoding,
            },
        },
    ]


def _record_from_report(
    *,
    profile: Mapping[str, Any],
    report: Mapping[str, Any],
    report_path: Path,
    command: list[str],
    exit_code: int,
    stdout_path: Path,
    stderr_path: Path,
    project_root: Path,
) -> dict[str, Any]:
    entries = list(_mapping(report.get("reduction")).get("entries", []))
    compact_entries = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        compact_entries.append(
            {
                "anchor_idx": entry.get("anchor_idx"),
                "variant": entry.get("variant"),
                "status": entry.get("status"),
                "wall_time": entry.get("wall_time"),
                "deterministic_time": entry.get("deterministic_time"),
                "branches": entry.get("branches"),
                "conflicts": entry.get("conflicts"),
                "booleans": _mapping(entry.get("response_stats_parsed")).get("booleans"),
                "propagations": _mapping(entry.get("response_stats_parsed")).get("propagations"),
                "integer_propagations": _mapping(entry.get("response_stats_parsed")).get("integer_propagations"),
                "response_summary": entry.get("response_summary"),
            }
        )
    status_counts = _mapping(_mapping(report.get("reduction")).get("status_counts"))
    progress_entries = [
        entry
        for entry in compact_entries
        if str(entry.get("status")) == "UNKNOWN"
        and (int(entry.get("branches") or 0) > 0 or int(entry.get("conflicts") or 0) > 0)
    ]
    zero_branch_unknown_entries = [
        entry
        for entry in compact_entries
        if str(entry.get("status")) == "UNKNOWN"
        and int(entry.get("branches") or 0) == 0
        and int(entry.get("conflicts") or 0) == 0
    ]
    terminal_entries = [
        entry
        for entry in compact_entries
        if str(entry.get("status")) in {"OPTIMAL", "FEASIBLE", "INFEASIBLE"}
    ]
    return {
        "profile_id": profile.get("profile_id"),
        "label": profile.get("label"),
        "diagnostic_semantics": profile.get("diagnostic_semantics"),
        "env": dict(_mapping(profile.get("env"))),
        "solver_profile": dict(_mapping(profile.get("solver_profile"))),
        "exit_code": int(exit_code),
        "report_path": _display_path(project_root, report_path),
        "stdout_path": _display_path(project_root, stdout_path),
        "stderr_path": _display_path(project_root, stderr_path),
        "command": command,
        "status": _mapping(report.get("status")),
        "status_counts": dict(status_counts),
        "terminal_count": len(terminal_entries),
        "search_progress_unknown_count": len(progress_entries),
        "zero_branch_unknown_count": len(zero_branch_unknown_entries),
        "entries": compact_entries,
    }


def _build_summary(
    *,
    project_root: Path,
    campaign_state: Path,
    candidate: str,
    anchors: list[str],
    time_limit_seconds: float,
    worker_count: int,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    terminal_profiles = [
        str(record.get("profile_id"))
        for record in records
        if int(record.get("terminal_count", 0)) > 0
    ]
    progress_profiles = [
        str(record.get("profile_id"))
        for record in records
        if int(record.get("search_progress_unknown_count", 0)) > 0
    ]
    failed_profiles = [
        str(record.get("profile_id"))
        for record in records
        if int(record.get("exit_code", 0)) != 0
    ]
    if failed_profiles:
        outcome = "profile_comparison_failed"
        recommendation = "Inspect failed profile logs before using this matrix."
    elif terminal_profiles:
        outcome = "terminal_profile_observed"
        recommendation = "At least one diagnostic profile reached terminal status; inspect per-anchor entries before interpreting."
    elif progress_profiles:
        outcome = "search_progress_without_terminal"
        recommendation = "At least one diagnostic profile broke zero-branch UNKNOWN without terminal proof; compare per-anchor patterns and avoid treating progress as proof."
    else:
        outcome = "all_profiles_zero_branch_or_nonprogress"
        recommendation = "No profile produced terminal or search progress; pivot to medium repro or deeper formulation audit."
    return {
        "metadata": {
            "source": "phase3b_profile_comparison_v1",
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "diagnostic_semantics": "profile_comparison_not_proof_source",
            "solver_invoked": True,
        },
        "paths": {
            "project_root": str(project_root),
            "campaign_state": str(campaign_state),
        },
        "profile": {
            "candidate": candidate,
            "anchor_indices": anchors,
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
        },
        "status": {
            "completed": not failed_profiles,
            "outcome": outcome,
            "recommendation": recommendation,
            "failed_profiles": failed_profiles,
            "terminal_profiles": terminal_profiles,
            "search_progress_profiles": progress_profiles,
            "proof_source": False,
            "runtime_promotion_ready": False,
        },
        "records": records,
    }


def _render_markdown(summary: Mapping[str, Any]) -> str:
    status = _mapping(summary.get("status"))
    lines = [
        "# Phase3B Profile Comparison",
        "",
        f"- Outcome: `{status.get('outcome')}`",
        f"- Recommendation: {status.get('recommendation')}",
        "- Proof source: `false`",
        "- Runtime promotion ready: `false`",
        "",
        "| Profile | Status Counts | Terminal | Search-Progress UNKNOWN | Zero-Branch UNKNOWN |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for record in list(summary.get("records", [])):
        if not isinstance(record, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    str(record.get("profile_id")),
                    "`" + json.dumps(record.get("status_counts", {}), sort_keys=True) + "`",
                    str(record.get("terminal_count", 0)),
                    str(record.get("search_progress_unknown_count", 0)),
                    str(record.get("zero_branch_unknown_count", 0)),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Per-Anchor Entries", ""])
    lines.append("| Profile | Anchor | Status | Branches | Conflicts | Det Time | Wall |")
    lines.append("| --- | ---: | --- | ---: | ---: | ---: | ---: |")
    for record in list(summary.get("records", [])):
        if not isinstance(record, Mapping):
            continue
        for entry in list(record.get("entries", [])):
            if not isinstance(entry, Mapping):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(record.get("profile_id")),
                        str(entry.get("anchor_idx")),
                        str(entry.get("status")),
                        str(entry.get("branches")),
                        str(entry.get("conflicts")),
                        str(entry.get("deterministic_time")),
                        str(entry.get("wall_time")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def _render_text(summary: Mapping[str, Any]) -> str:
    lines = [
        "phase3b profile comparison",
        f"outcome={_mapping(summary.get('status')).get('outcome')}",
        f"recommendation={_mapping(summary.get('status')).get('recommendation')}",
    ]
    for record in list(summary.get("records", [])):
        if not isinstance(record, Mapping):
            continue
        lines.append(
            "profile "
            f"id={record.get('profile_id')} "
            f"status_counts={record.get('status_counts')} "
            f"terminal={record.get('terminal_count')} "
            f"progress_unknown={record.get('search_progress_unknown_count')} "
            f"zero_branch_unknown={record.get('zero_branch_unknown_count')}"
        )
        for entry in list(record.get("entries", [])):
            if not isinstance(entry, Mapping):
                continue
            lines.append(
                "entry "
                f"profile={record.get('profile_id')} "
                f"anchor={entry.get('anchor_idx')} "
                f"status={entry.get('status')} "
                f"branches={entry.get('branches')} "
                f"conflicts={entry.get('conflicts')} "
                f"deterministic_time={entry.get('deterministic_time')} "
                f"wall={entry.get('wall_time')}"
            )
    return "\n".join(lines) + "\n"


def _load_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    return value if isinstance(value, Mapping) else {}


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else project_root / path


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(Path(path).resolve())


def _parse_csv(raw_value: str) -> list[str]:
    return [token.strip() for token in str(raw_value).split(",") if token.strip()]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())
