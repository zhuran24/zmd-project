from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

from src.search.exact_campaign import now_iso

OPERATING_PROFILE_SCHEMA_SOURCE = "phase3b_operating_profile_v1"
DEFAULT_PRODUCTION_PROFILE_ID = "prod_4x4_normal"
DEFAULT_DIAGNOSTIC_PROFILE_ID = "diagnostic_1x1_normal"
ALL_TEMPLATE_BLOCK64_FORMULATION_PROFILE_ID = (
    "diagnostic_block64_all_templates_low_encoding_linearization0_1w"
)
SELECTED_BLOCK_FORMULATION_PROFILE_ID = (
    "diagnostic_block64_all_templates_selected_block_low_encoding_linearization0_1w"
)
ACTIVE_GUARD_FORMULATION_PROFILE_ID = (
    "diagnostic_block64_all_templates_selected_block_active_guard_low_encoding_linearization0_1w"
)
JOINED_XY_FORMULATION_PROFILE_ID = (
    "diagnostic_block64_all_templates_selected_block_active_guard_joined_xy_low_encoding_linearization0_1w"
)
DELTA_INTERVAL_FORMULATION_PROFILE_ID = (
    "diagnostic_block64_all_templates_delta_interval_low_encoding_linearization0_1w"
)


def build_phase3b_operating_profile_summary(project_root: Path) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    profiles = _profile_definitions()
    profile_by_id = {str(profile["profile_id"]): dict(profile) for profile in profiles}
    return {
        "metadata": {
            "source": OPERATING_PROFILE_SCHEMA_SOURCE,
            "generated_at": now_iso(),
            "project_root": str(project_root),
        },
        "defaults": {
            "production_profile_id": DEFAULT_PRODUCTION_PROFILE_ID,
            "diagnostic_profile_id": DEFAULT_DIAGNOSTIC_PROFILE_ID,
        },
        "profiles": profiles,
        "profile_by_id": profile_by_id,
        "policy": {
            "high_priority_default": False,
            "default_production_runner": "scripts/run_prod_4x4_normal.ps1",
            "default_diagnostic_runner": "scripts/run_prod_1x1_normal.ps1",
            "workspace_policy": (
                "Run tuning, diagnostic campaigns, and long campaigns in workspace "
                "copies. Repo main proof paths only receive final frozen evidence."
            ),
            "profile_change_gate": (
                "Any production profile change must be justified by a fresh "
                "production-acceptance benchmark on the same artifact set."
            ),
            "formulation_profile_gate": (
                "Formulation diagnostic profiles are default-off and are not "
                "production profiles until a certified anchor and production "
                "acceptance both pass."
            ),
            "production_acceptance_command": (
                "python temp_scripts/benchmark_parallelism.py --suite-kind "
                "production-acceptance --suite-output "
                ".codex_test_logs/phase3b/production_acceptance_after_change.json"
            ),
            "long_run_command": _command(
                parallel_processes=4,
                process_priority="normal",
                include_resume=True,
            ),
        },
    }


def render_phase3b_operating_profile_markdown(summary: Mapping[str, Any]) -> str:
    defaults = _mapping(summary.get("defaults"))
    policy = _mapping(summary.get("policy"))
    profiles = [
        profile
        for profile in list(summary.get("profiles", []))
        if isinstance(profile, Mapping)
    ]
    lines = [
        "# Phase 3B Operating Profile",
        "",
        f"- Default production profile: {defaults.get('production_profile_id')}",
        f"- Default diagnostic profile: {defaults.get('diagnostic_profile_id')}",
        f"- High priority default: {bool(policy.get('high_priority_default', False))}",
        f"- Production acceptance: {policy.get('production_acceptance_command')}",
        "",
        "| Profile | Role | Default | Parallel | CP-SAT workers | Priority | Probe | Runner |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for profile in profiles:
        env = _mapping(profile.get("env"))
        default_text = []
        if bool(profile.get("is_default_production", False)):
            default_text.append("production")
        if bool(profile.get("is_default_diagnostic", False)):
            default_text.append("diagnostic")
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(profile.get("profile_id")),
                    _markdown_cell(profile.get("role")),
                    _markdown_cell(", ".join(default_text) if default_text else "no"),
                    _markdown_cell(profile.get("parallel_processes")),
                    _markdown_cell(env.get("EXACT_CP_SAT_WORKERS")),
                    _markdown_cell(profile.get("process_priority")),
                    _markdown_cell(profile.get("frontier_probe_mode")),
                    _markdown_cell(profile.get("runner_script")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Policy",
            "",
            f"- {policy.get('profile_change_gate')}",
            f"- {policy.get('formulation_profile_gate')}",
            f"- {policy.get('workspace_policy')}",
            "- `process-priority high` is an explicit experiment profile, not the default production profile.",
        ]
    )
    return "\n".join(lines) + "\n"


def _profile_definitions() -> list[Dict[str, Any]]:
    return [
        _profile(
            profile_id=DEFAULT_DIAGNOSTIC_PROFILE_ID,
            label="1x1 normal diagnostic",
            role="diagnostic",
            parallel_processes=1,
            cp_sat_workers=1,
            process_priority="normal",
            frontier_probe_mode="auto",
            runner_script="scripts/run_prod_1x1_normal.ps1",
            is_default_diagnostic=True,
            is_default_production=False,
        ),
        _profile(
            profile_id=DEFAULT_PRODUCTION_PROFILE_ID,
            label="prod 4x4 normal",
            role="production",
            parallel_processes=4,
            cp_sat_workers=4,
            process_priority="normal",
            frontier_probe_mode="auto",
            runner_script="scripts/run_prod_4x4_normal.ps1",
            is_default_diagnostic=False,
            is_default_production=True,
        ),
        _profile(
            profile_id="prod_4x4_high",
            label="prod 4x4 high priority experiment",
            role="experimental",
            parallel_processes=4,
            cp_sat_workers=4,
            process_priority="high",
            frontier_probe_mode="auto",
            runner_script="scripts/run_prod_4x4_high.ps1",
            is_default_diagnostic=False,
            is_default_production=False,
        ),
        _formulation_probe_profile(),
        _delta_interval_formulation_probe_profile(),
        _selected_block_formulation_probe_profile(),
        _active_guard_formulation_probe_profile(),
        _joined_xy_formulation_probe_profile(),
    ]


def _profile(
    *,
    profile_id: str,
    label: str,
    role: str,
    parallel_processes: int,
    cp_sat_workers: int,
    process_priority: str,
    frontier_probe_mode: str,
    runner_script: str,
    is_default_diagnostic: bool,
    is_default_production: bool,
) -> Dict[str, Any]:
    return {
        "profile_id": str(profile_id),
        "label": str(label),
        "role": str(role),
        "parallel_processes": int(parallel_processes),
        "env": {"EXACT_CP_SAT_WORKERS": str(int(cp_sat_workers))},
        "process_priority": str(process_priority),
        "frontier_probe_mode": str(frontier_probe_mode),
        "runner_script": str(runner_script),
        "is_default_diagnostic": bool(is_default_diagnostic),
        "is_default_production": bool(is_default_production),
        "command": _command(
            parallel_processes=int(parallel_processes),
            process_priority=str(process_priority),
            include_resume=True,
        ),
        "dry_run_command": (
            f"powershell -ExecutionPolicy Bypass -File {runner_script} -DryRun"
        ),
    }


def _formulation_probe_profile() -> Dict[str, Any]:
    runner_script = "scripts/run_phase3b_block64_low_encoding_anchor_probe.ps1"
    command = (
        "powershell -ExecutionPolicy Bypass -File "
        f"{runner_script} -AllBlockTemplates -BlockSize 64 "
        "-AnchorIndices 124 -TimeLimitSeconds 300"
    )
    return {
        "profile_id": ALL_TEMPLATE_BLOCK64_FORMULATION_PROFILE_ID,
        "label": "block64 all-template low-encoding formulation diagnostic",
        "role": "formulation_diagnostic",
        "parallel_processes": 1,
        "env": {
            "EXACT_CP_SAT_WORKERS": "1",
            "EXACT_POWER_COVERAGE_WITNESS_ENCODING": "block_element",
            "EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE": "64",
            "EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES": "",
            "EXACT_POWER_FAMILY_LOOKUP_ENCODING": "linear_shell_guards",
            "EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING": "linear_minmax",
        },
        "process_priority": "normal",
        "frontier_probe_mode": "diagnostic_forced_anchor_probe",
        "runner_script": runner_script,
        "is_default_diagnostic": False,
        "is_default_production": False,
        "is_formulation_diagnostic": True,
        "proof_semantics": "proof_preserving_encoding_comparison_not_proof_source",
        "command": command,
        "dry_run_command": f"{command} -DryRun",
    }


def _delta_interval_formulation_probe_profile() -> Dict[str, Any]:
    runner_script = "scripts/run_phase3b_block64_low_encoding_anchor_probe.ps1"
    command = (
        "powershell -ExecutionPolicy Bypass -File "
        f"{runner_script} -AllBlockTemplates -BlockSize 64 "
        "-SelectedIntervalEncoding delta "
        "-AnchorIndices 118,125 -TimeLimitSeconds 300"
    )
    return {
        "profile_id": DELTA_INTERVAL_FORMULATION_PROFILE_ID,
        "label": "block64 all-template delta-interval low-encoding formulation diagnostic",
        "role": "formulation_diagnostic",
        "parallel_processes": 1,
        "env": {
            "EXACT_CP_SAT_WORKERS": "1",
            "EXACT_POWER_COVERAGE_WITNESS_ENCODING": "block_element",
            "EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE": "64",
            "EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES": "",
            "EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING": "delta",
            "EXACT_POWER_FAMILY_LOOKUP_ENCODING": "linear_shell_guards",
            "EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING": "linear_minmax",
        },
        "process_priority": "normal",
        "frontier_probe_mode": "diagnostic_forced_anchor_probe",
        "runner_script": runner_script,
        "is_default_diagnostic": False,
        "is_default_production": False,
        "is_formulation_diagnostic": True,
        "proof_semantics": "proof_preserving_encoding_comparison_not_proof_source",
        "command": command,
        "dry_run_command": f"{command} -DryRun",
    }


def _selected_block_formulation_probe_profile() -> Dict[str, Any]:
    runner_script = "scripts/run_phase3b_block64_low_encoding_anchor_probe.ps1"
    command = (
        "powershell -ExecutionPolicy Bypass -File "
        f"{runner_script} -AllBlockTemplates -BlockSize 64 "
        "-BlockGeometry selected_block "
        "-AnchorIndices 124 -TimeLimitSeconds 300"
    )
    return {
        "profile_id": SELECTED_BLOCK_FORMULATION_PROFILE_ID,
        "label": "block64 all-template selected-block low-encoding formulation diagnostic",
        "role": "formulation_diagnostic",
        "parallel_processes": 1,
        "env": {
            "EXACT_CP_SAT_WORKERS": "1",
            "EXACT_POWER_COVERAGE_WITNESS_ENCODING": "block_element",
            "EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY": "selected_block",
            "EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE": "64",
            "EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES": "",
            "EXACT_POWER_FAMILY_LOOKUP_ENCODING": "linear_shell_guards",
            "EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING": "linear_minmax",
        },
        "process_priority": "normal",
        "frontier_probe_mode": "diagnostic_forced_anchor_probe",
        "runner_script": runner_script,
        "is_default_diagnostic": False,
        "is_default_production": False,
        "is_formulation_diagnostic": True,
        "proof_semantics": "proof_preserving_encoding_comparison_not_proof_source",
        "command": command,
        "dry_run_command": f"{command} -DryRun",
    }


def _active_guard_formulation_probe_profile() -> Dict[str, Any]:
    runner_script = "scripts/run_phase3b_block64_low_encoding_anchor_probe.ps1"
    command = (
        "powershell -ExecutionPolicy Bypass -File "
        f"{runner_script} -AllBlockTemplates -BlockSize 64 "
        "-BlockGeometry selected_block_active_guard "
        "-AnchorIndices 118,125 -TimeLimitSeconds 45"
    )
    return {
        "profile_id": ACTIVE_GUARD_FORMULATION_PROFILE_ID,
        "label": "block64 all-template selected-block active-guard low-encoding formulation diagnostic",
        "role": "formulation_diagnostic",
        "parallel_processes": 1,
        "env": {
            "EXACT_CP_SAT_WORKERS": "1",
            "EXACT_POWER_COVERAGE_WITNESS_ENCODING": "block_element",
            "EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY": "selected_block_active_guard",
            "EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE": "64",
            "EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES": "",
            "EXACT_POWER_FAMILY_LOOKUP_ENCODING": "linear_shell_guards",
            "EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING": "linear_minmax",
        },
        "process_priority": "normal",
        "frontier_probe_mode": "diagnostic_forced_anchor_probe",
        "runner_script": runner_script,
        "is_default_diagnostic": False,
        "is_default_production": False,
        "is_formulation_diagnostic": True,
        "proof_semantics": "diagnostic_formulation_only_equivalence_unproven_not_proof_source",
        "candidate_elimination_claim": False,
        "warning": (
            "selected_block_active_guard is default-off diagnostic/formulation-only; "
            "forced-anchor results are not campaign proof, not production readiness, "
            "and not candidate elimination."
        ),
        "risk_note": (
            "Default-off diagnostic only; removes active block Element channels but "
            "adds a large Boolean guard layer, so it needs no-solve and bounded "
            "probe gates before any production consideration."
        ),
        "command": command,
        "dry_run_command": f"{command} -DryRun",
    }


def _joined_xy_formulation_probe_profile() -> Dict[str, Any]:
    runner_script = "scripts/run_phase3b_block64_low_encoding_anchor_probe.ps1"
    command = (
        "powershell -ExecutionPolicy Bypass -File "
        f"{runner_script} -AllBlockTemplates -BlockSize 64 "
        "-BlockGeometry selected_block_active_guard_joined_xy "
        "-AnchorIndices 118,119,125 -TimeLimitSeconds 120"
    )
    return {
        "profile_id": JOINED_XY_FORMULATION_PROFILE_ID,
        "label": "block64 all-template selected-block active-guard joined-XY low-encoding formulation diagnostic",
        "role": "formulation_diagnostic",
        "parallel_processes": 1,
        "env": {
            "EXACT_CP_SAT_WORKERS": "1",
            "EXACT_POWER_COVERAGE_WITNESS_ENCODING": "block_element",
            "EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY": "selected_block_active_guard_joined_xy",
            "EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE": "64",
            "EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES": "",
            "EXACT_POWER_FAMILY_LOOKUP_ENCODING": "linear_shell_guards",
            "EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING": "linear_minmax",
        },
        "process_priority": "normal",
        "frontier_probe_mode": "diagnostic_forced_anchor_probe",
        "runner_script": runner_script,
        "is_default_diagnostic": False,
        "is_default_production": False,
        "is_formulation_diagnostic": True,
        "proof_semantics": "diagnostic_formulation_only_not_proof_source",
        "candidate_elimination_claim": False,
        "warning": (
            "selected_block_active_guard_joined_xy is default-off diagnostic/formulation-only; "
            "forced-anchor results are not campaign proof, not production readiness, "
            "and not candidate elimination."
        ),
        "risk_note": (
            "Current evidence shows SAT expansion recovery versus grouped-XY and "
            "anchor118 terminal reproduction plus search-progress UNKNOWN across "
            "anchors 119-125; the full 300s focus set remains conflictful UNKNOWN, "
            "so the path still requires workspace validation and "
            "production acceptance before any production consideration."
        ),
        "evidence_artifacts": [
            ".artifacts/phase3b_joined_xy_profile_audit_20260423/joined_xy_profile_audit.json",
            ".artifacts/phase3b_joined_xy_sat_expansion_audit_20260423/joined_xy_sat_expansion_audit.json",
            ".artifacts/phase3b_joined_xy_probe_synthesis_20260423_r5/joined_xy_probe_synthesis.json",
        ],
        "command": command,
        "dry_run_command": f"{command} -DryRun",
    }


def _command(
    *,
    parallel_processes: int,
    process_priority: str,
    include_resume: bool,
) -> str:
    parts = [
        "python",
        "main.py",
        "--mode",
        "certified_exact",
        "--campaign-hours",
        "168",
        "--parallel-processes",
        str(int(parallel_processes)),
        "--process-priority",
        str(process_priority),
        "--frontier-probe-mode",
        "auto",
    ]
    if include_resume:
        parts.append("--resume-campaign")
    return " ".join(parts)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
