from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.campaign_triage import build_phase3b_unknown_triage_inventory
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso
from src.search.exact_campaign_inspector import build_exact_campaign_inspection
from src.search.phase3b_b5a_gate_integration_marker import (
    B5A_GATE_INTEGRATION_MARKER_SOURCE,
    validate_phase3b_b5a_gate_integration_marker_for_preflight,
)
from src.search.phase3b_b5a_certification_contracts import (
    AUTHORIZATION_SAFETY_FALSE_FIELDS,
    PREFLIGHT_MUTATION_FALSE_FIELDS,
    chain_fingerprint,
    required_false,
    sha256_file,
)
from src.search.phase3b_operating_profile import build_phase3b_operating_profile_summary

LONG_RUN_PREFLIGHT_SCHEMA_SOURCE = "phase3b_long_run_preflight_v1"
DEFAULT_B5A_SUMMARY_PATH = Path(".artifacts/phase3b_b5_anchor_sprint/operator_summary.json")
DEFAULT_PRODUCTION_ACCEPTANCE_PATH = Path(
    ".codex_test_logs/phase3b/production_acceptance_before_final_long_run.json"
)
DEFAULT_STARTLINE_MANIFEST_PATH = Path(".artifacts/phase3b_startline/startline_manifest.json")
DEFAULT_GROUP_PACKING_PROMOTION_SPEC_PATH = Path(
    ".artifacts/phase3b_group_packing_precheck_promotion_spec/promotion_spec.json"
)
DEFAULT_GROUP_PACKING_PROOF_PROMOTION_PATH = Path(
    ".artifacts/phase3b_group_packing_proof_promotion/proof_promotion_blockers.json"
)
DEFAULT_COORDINATE_VALIDATION_PRECHECK_CANDIDATE_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_precheck_candidate/precheck_candidate.json"
)
DEFAULT_COORDINATE_VALIDATION_PROMOTION_SPEC_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_precheck_promotion_spec/promotion_spec.json"
)
DEFAULT_ZERO_BRANCH_UNKNOWN_TRIAGE_PATH = Path(
    ".artifacts/phase3b_zero_branch_unknown_triage/zero_branch_unknown_triage.json"
)
DEFAULT_POWER_PROTOCOL_INTERACTION_PATH = Path(
    ".artifacts/phase3b_power_protocol_interaction/power_protocol_interaction.json"
)
DEFAULT_JOINED_XY_PROBE_SYNTHESIS_PATH = Path(
    ".artifacts/phase3b_joined_xy_probe_synthesis_20260423_r5/"
    "joined_xy_probe_synthesis.json"
)
DEFAULT_WORKSPACE_ROOT = Path("D:/phase3b_workspaces/endfield_phase3b_b5_anchor_20260417")
DEFAULT_MIN_FREE_GB = 100.0
EXPECTED_PRODUCTION_ACCEPTANCE_LABELS = {
    "prod_1x1": (1, 1),
    "prod_2x4": (2, 4),
    "prod_4x4": (4, 4),
    "prod_2x8": (2, 8),
}
EXPECTED_PRODUCTION_MASTER_SEARCH_PROFILE = "exact_coordinate_guided_branching_v4"
EXPECTED_PRODUCTION_SAFE_AREA_UPPER_BOUND = 1347
EXPECTED_PRODUCTION_SELECTED_CANDIDATE = [1330, 70, 19]
EXPECTED_PRODUCTION_FRONTIER_CANDIDATES = [
    [1344, 42, 32],
    [1344, 48, 28],
    [1344, 56, 24],
    [1344, 64, 21],
    [1342, 61, 22],
    [1340, 67, 20],
    [1334, 46, 29],
    [1334, 58, 23],
]
EXPECTED_ACCEPTANCE_VALIDATOR_CHAIN_INPUT_IDS = [
    "acceptance_execution_staging",
    "pre_run_acceptance_validation",
    "provided_acceptance_result",
]
ACCEPTANCE_VALIDATOR_STABLE_METADATA_FIELDS = [
    "source",
    "diagnostic_semantics",
    "spec_only",
    "default_off",
    "runtime_precheck_enabled",
    "runtime_semantics_changed",
    "proof_source",
    "candidate_elimination_claim",
    "solver_invoked",
    "acceptance_executed",
]


def build_phase3b_long_run_preflight_summary(
    project_root: Path,
    *,
    b5a_summary_path: Optional[Path] = None,
    production_acceptance_path: Optional[Path] = None,
    production_acceptance_result_validator_path: Optional[Path] = None,
    startline_manifest_path: Optional[Path] = None,
    group_packing_promotion_spec_path: Optional[Path] = None,
    group_packing_proof_promotion_path: Optional[Path] = None,
    coordinate_validation_precheck_candidate_path: Optional[Path] = None,
    coordinate_validation_promotion_spec_path: Optional[Path] = None,
    zero_branch_unknown_triage_path: Optional[Path] = None,
    power_protocol_interaction_path: Optional[Path] = None,
    joined_xy_probe_synthesis_path: Optional[Path] = None,
    b5a_gate_integration_marker_path: Optional[Path] = None,
    workspace_root: Optional[Path] = None,
    min_free_gb: float = DEFAULT_MIN_FREE_GB,
    disk_free_gb_override: Optional[float] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    b5a_path = _resolve_path(
        project_root,
        b5a_summary_path if b5a_summary_path is not None else DEFAULT_B5A_SUMMARY_PATH,
    )
    acceptance_path = _resolve_path(
        project_root,
        production_acceptance_path
        if production_acceptance_path is not None
        else DEFAULT_PRODUCTION_ACCEPTANCE_PATH,
    )
    startline_path = _resolve_path(
        project_root,
        startline_manifest_path
        if startline_manifest_path is not None
        else DEFAULT_STARTLINE_MANIFEST_PATH,
    )
    promotion_spec_path = _resolve_path(
        project_root,
        group_packing_promotion_spec_path
        if group_packing_promotion_spec_path is not None
        else DEFAULT_GROUP_PACKING_PROMOTION_SPEC_PATH,
    )
    proof_promotion_path = _resolve_path(
        project_root,
        group_packing_proof_promotion_path
        if group_packing_proof_promotion_path is not None
        else DEFAULT_GROUP_PACKING_PROOF_PROMOTION_PATH,
    )
    coordinate_precheck_path = _resolve_path(
        project_root,
        coordinate_validation_precheck_candidate_path
        if coordinate_validation_precheck_candidate_path is not None
        else DEFAULT_COORDINATE_VALIDATION_PRECHECK_CANDIDATE_PATH,
    )
    coordinate_spec_path = _resolve_path(
        project_root,
        coordinate_validation_promotion_spec_path
        if coordinate_validation_promotion_spec_path is not None
        else DEFAULT_COORDINATE_VALIDATION_PROMOTION_SPEC_PATH,
    )
    zero_branch_path = _resolve_path(
        project_root,
        zero_branch_unknown_triage_path
        if zero_branch_unknown_triage_path is not None
        else DEFAULT_ZERO_BRANCH_UNKNOWN_TRIAGE_PATH,
    )
    power_protocol_path = _resolve_path(
        project_root,
        power_protocol_interaction_path
        if power_protocol_interaction_path is not None
        else DEFAULT_POWER_PROTOCOL_INTERACTION_PATH,
    )
    joined_xy_path = _resolve_path(
        project_root,
        joined_xy_probe_synthesis_path
        if joined_xy_probe_synthesis_path is not None
        else DEFAULT_JOINED_XY_PROBE_SYNTHESIS_PATH,
    )
    b5a_gate_marker_path = (
        _resolve_path(project_root, b5a_gate_integration_marker_path)
        if b5a_gate_integration_marker_path is not None
        else None
    )
    acceptance_result_validator_path = (
        _resolve_path(project_root, production_acceptance_result_validator_path)
        if production_acceptance_result_validator_path is not None
        else None
    )
    workspace_path = Path(workspace_root or DEFAULT_WORKSPACE_ROOT)
    if not workspace_path.is_absolute():
        workspace_path = (project_root / workspace_path).resolve()
    else:
        workspace_path = workspace_path.resolve()

    campaign_state_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    inspection = build_exact_campaign_inspection(project_root)
    triage = build_phase3b_unknown_triage_inventory(project_root)
    operating_profile = build_phase3b_operating_profile_summary(project_root)
    startline_manifest, startline_error = _load_json_mapping(startline_path)
    promotion_spec, promotion_spec_error = _load_json_mapping(promotion_spec_path)
    proof_promotion, proof_promotion_error = _load_json_mapping(proof_promotion_path)
    coordinate_precheck, coordinate_precheck_error = _load_json_mapping(
        coordinate_precheck_path
    )
    coordinate_spec, coordinate_spec_error = _load_json_mapping(coordinate_spec_path)
    zero_branch_triage, zero_branch_error = _load_json_mapping(zero_branch_path)
    power_protocol, power_protocol_error = _load_json_mapping(power_protocol_path)
    joined_xy_synthesis, joined_xy_error = _load_json_mapping(joined_xy_path)
    b5a_gate_marker, b5a_gate_marker_error = (
        _load_json_mapping(b5a_gate_marker_path)
        if b5a_gate_marker_path is not None
        else (None, None)
    )
    b5a_summary, b5a_error = _load_json_mapping(b5a_path)
    production_acceptance, production_error = _load_json_mapping(acceptance_path)
    acceptance_result_validator, acceptance_result_validator_error = (
        _load_json_mapping(acceptance_result_validator_path)
        if acceptance_result_validator_path is not None
        else (None, None)
    )
    current_hashes, hash_error = _current_hashes(project_root)
    hash_expected = (
        dict(startline_manifest.get("exact_source_of_truth_hashes", {}))
        if isinstance(startline_manifest, Mapping)
        and isinstance(startline_manifest.get("exact_source_of_truth_hashes"), Mapping)
        else {}
    )
    hash_matches = bool(
        hash_expected and hash_error is None and dict(hash_expected) == dict(current_hashes)
    )

    disk_free_gb = (
        float(disk_free_gb_override)
        if disk_free_gb_override is not None
        else _free_gb_for_path(workspace_path)
    )
    b5a_marker_explicit = b5a_gate_marker_path is not None
    production_acceptance_explicit = production_acceptance_path is not None
    production_acceptance_validator_explicit = (
        production_acceptance_result_validator_path is not None
    )
    prod_4x4_record = _prod_4x4_record(production_acceptance)
    b5a_gate_marker_validation = (
        validate_phase3b_b5a_gate_integration_marker_for_preflight(
            project_root,
            b5a_gate_marker,
            marker_path=b5a_gate_marker_path,
        )
        if b5a_marker_explicit
        else {
            "accepted": False,
            "summary": "final production preflight requires --b5a-gate-integration-marker",
            "failed_rule_ids": ["explicit_b5a_gate_integration_marker_present"],
            "rule_results": [],
        }
    )
    acceptance_validator_check = _acceptance_result_validator_for_preflight(
        project_root=project_root,
        validator=acceptance_result_validator,
        validator_error=acceptance_result_validator_error,
        validator_path=acceptance_result_validator_path,
        acceptance_summary_path=acceptance_path,
        acceptance_summary=production_acceptance,
    )
    b5a_anchor_found = bool(
        b5a_marker_explicit and b5a_gate_marker_validation.get("accepted") is True
    )
    checks = [
        _check(
            "startline_manifest_present",
            "pass" if startline_manifest is not None and startline_error is None else "fail",
            "startline manifest loaded"
            if startline_manifest is not None and startline_error is None
            else startline_error or f"missing:{_display_path(project_root, startline_path)}",
        ),
        _check(
            "exact_hashes_match_startline",
            "pass" if hash_matches else "fail",
            "current exact source-of-truth hashes match B0 startline"
            if hash_matches
            else hash_error or "current exact hashes do not match B0 startline",
        ),
        _check(
            "repo_main_campaign_state_absent",
            "pass" if not campaign_state_path.exists() else "fail",
            "repo main has no intermediate exact campaign state"
            if not campaign_state_path.exists()
            else _display_path(project_root, campaign_state_path),
        ),
        _check(
            "operating_profile_locked",
            "pass" if _operating_profile_locked(operating_profile) else "fail",
            "B4 default production profile is prod_4x4_normal"
            if _operating_profile_locked(operating_profile)
            else "B4 default production profile does not match prod_4x4_normal",
        ),
        _check(
            "b5a_summary_present",
            "pass" if b5a_summary is not None and b5a_error is None else "fail",
            "B5A operator summary loaded"
            if b5a_summary is not None and b5a_error is None
                else b5a_error or f"missing:{_display_path(project_root, b5a_path)}",
        ),
        _check(
            "explicit_b5a_gate_integration_marker_present",
            "pass" if b5a_marker_explicit else "fail",
            "explicit B5A gate integration marker supplied"
            if b5a_marker_explicit
            else "final production preflight requires --b5a-gate-integration-marker",
        ),
        _check(
            "b5a_anchor_found",
            "pass" if b5a_anchor_found else "fail",
            _b5a_anchor_detail(
                b5a_summary,
                b5a_error,
                b5a_gate_marker,
                b5a_gate_marker_error,
                b5a_gate_marker_path,
                project_root,
                b5a_gate_marker_validation,
            ),
        ),
        _check(
            "explicit_production_acceptance_summary_present",
            "pass" if production_acceptance_explicit else "fail",
            "explicit production acceptance summary supplied"
            if production_acceptance_explicit
            else "final production preflight requires --production-acceptance-summary",
        ),
        _check(
            "production_acceptance_present",
            "pass"
            if production_acceptance is not None and production_error is None
            else "fail",
            "production-acceptance summary loaded"
            if production_acceptance is not None and production_error is None
            else production_error or f"missing:{_display_path(project_root, acceptance_path)}",
        ),
        _check(
            "production_acceptance_prod_4x4_valid",
            "pass"
            if _prod_4x4_record_valid(
                prod_4x4_record,
                summary=production_acceptance,
            )
            else "fail",
            "prod_4x4 completed with valid campaign and no duplicated work"
            if _prod_4x4_record_valid(
                prod_4x4_record,
                summary=production_acceptance,
            )
            else _prod_4x4_failure_detail(
                prod_4x4_record,
                summary=production_acceptance,
            ),
        ),
        _check(
            "explicit_production_acceptance_result_validator_present",
            "pass" if production_acceptance_validator_explicit else "fail",
            "explicit production acceptance result validator supplied"
            if production_acceptance_validator_explicit
            else (
                "final production preflight requires "
                "--production-acceptance-result-validator"
            ),
        ),
        _check(
            "production_acceptance_result_validator_passed",
            "pass" if acceptance_validator_check.get("accepted") is True else "fail",
            str(acceptance_validator_check.get("summary")),
        ),
        _check(
            "workspace_disk_free",
            "pass" if disk_free_gb >= float(min_free_gb) else "fail",
            f"{_drive_label(workspace_path)} free {disk_free_gb:.2f}GB >= {float(min_free_gb):.2f}GB"
            if disk_free_gb >= float(min_free_gb)
            else f"{_drive_label(workspace_path)} free {disk_free_gb:.2f}GB < {float(min_free_gb):.2f}GB",
        ),
    ]
    ready = all(str(check["status"]) == "pass" for check in checks)
    return {
        "metadata": {
            "source": LONG_RUN_PREFLIGHT_SCHEMA_SOURCE,
            "generated_at": now_iso(),
            "project_root": str(project_root),
        },
        "paths": {
            "startline_manifest": _display_path(project_root, startline_path),
            "group_packing_promotion_spec": _display_path(
                project_root,
                promotion_spec_path,
            ),
            "group_packing_proof_promotion": _display_path(
                project_root,
                proof_promotion_path,
            ),
            "coordinate_validation_precheck_candidate": _display_path(
                project_root,
                coordinate_precheck_path,
            ),
            "coordinate_validation_promotion_spec": _display_path(
                project_root,
                coordinate_spec_path,
            ),
            "zero_branch_unknown_triage": _display_path(project_root, zero_branch_path),
            "power_protocol_interaction": _display_path(
                project_root,
                power_protocol_path,
            ),
            "joined_xy_probe_synthesis": _display_path(project_root, joined_xy_path),
            "b5a_operator_summary": _display_path(project_root, b5a_path),
            "b5a_gate_integration_marker": _display_path(
                project_root, b5a_gate_marker_path
            ),
            "production_acceptance_summary": _display_path(project_root, acceptance_path),
            "production_acceptance_result_validator": _display_path(
                project_root, acceptance_result_validator_path
            ),
            "workspace_root": str(workspace_path),
            "repo_main_campaign_state": _display_path(project_root, campaign_state_path),
        },
        "ready_for_final_long_run": bool(ready),
        "preflight_gate_ready": bool(ready),
        "ready_to_request_human_launch_authorization": bool(ready),
        "human_launch_authorization_required": True,
        "final_168h_authorized": False,
        "execution_allowed": False,
        "recommendation": _recommendation(
            ready=ready,
            checks=checks,
            b5a_summary=b5a_summary,
            group_packing_promotion_spec=promotion_spec,
            group_packing_promotion_spec_error=promotion_spec_error,
            group_packing_proof_promotion=proof_promotion,
            group_packing_proof_promotion_error=proof_promotion_error,
            coordinate_validation_precheck=coordinate_precheck,
            coordinate_validation_precheck_error=coordinate_precheck_error,
            coordinate_validation_promotion_spec=coordinate_spec,
            coordinate_validation_promotion_spec_error=coordinate_spec_error,
            zero_branch_unknown_triage=zero_branch_triage,
            zero_branch_unknown_triage_error=zero_branch_error,
            power_protocol_interaction=power_protocol,
            power_protocol_interaction_error=power_protocol_error,
            joined_xy_probe_synthesis=joined_xy_synthesis,
            joined_xy_probe_synthesis_error=joined_xy_error,
        ),
        "final_long_run": {
            "allowed": False,
            "execution_allowed": False,
            "final_168h_authorized": False,
            "human_launch_authorization_required": True,
            "preflight_gate_ready": bool(ready),
            "ready_to_request_human_launch_authorization": bool(ready),
            "dry_run_command": (
                "powershell -ExecutionPolicy Bypass -File "
                "scripts/run_prod_4x4_normal.ps1 -ResumeCampaign -DryRun"
            ),
            "command": None,
            "non_dry_run_command": None,
            "must_not_start_in_this_step": True,
        },
        "disk": {
            "workspace_drive": _drive_label(workspace_path),
            "workspace_free_gb": float(disk_free_gb),
            "min_free_gb": float(min_free_gb),
        },
        "startline": {
            "present": startline_manifest is not None and startline_error is None,
            "load_error": startline_error,
            "expected_exact_hashes": hash_expected,
            "current_exact_hashes": current_hashes,
            "hashes_match": bool(hash_matches),
        },
        "inspection": {
            "campaign": inspection.get("campaign", {}),
            "telemetry": inspection.get("telemetry", {}),
            "delivery_manifest": inspection.get("delivery_manifest", {}),
        },
        "triage": {
            "summary": triage.get("summary", {}),
        },
        "b2_targeted_shrink": _b2_targeted_shrink_advisory(
            promotion_spec,
            promotion_spec_error,
            proof_promotion,
            proof_promotion_error,
        ),
        "coordinate_validation_precheck": _coordinate_validation_precheck_advisory(
            coordinate_precheck,
            coordinate_precheck_error,
        ),
        "coordinate_validation_promotion_spec": _coordinate_validation_promotion_advisory(
            coordinate_spec,
            coordinate_spec_error,
        ),
        "zero_branch_unknown_triage": _zero_branch_unknown_advisory(
            zero_branch_triage,
            zero_branch_error,
        ),
        "power_protocol_interaction": _power_protocol_interaction_advisory(
            power_protocol,
            power_protocol_error,
        ),
        "joined_xy_probe_synthesis": _joined_xy_probe_synthesis_advisory(
            joined_xy_synthesis,
            joined_xy_error,
        ),
        "operating_profile": {
            "defaults": operating_profile.get("defaults", {}),
            "profile": _prod_profile(operating_profile),
            "policy": operating_profile.get("policy", {}),
        },
        "b5a": {
            "present": b5a_summary is not None and b5a_error is None,
            "load_error": b5a_error,
            "status": _mapping(b5a_summary.get("status")) if b5a_summary else {},
            "anchor": b5a_summary.get("anchor") if b5a_summary else None,
        },
        "b5a_gate_integration_marker": {
            "provided": b5a_gate_marker_path is not None,
            "present": b5a_gate_marker is not None and b5a_gate_marker_error is None,
            "load_error": b5a_gate_marker_error,
            "status": _mapping(b5a_gate_marker.get("status"))
            if b5a_gate_marker
            else {},
            "marker": _mapping(b5a_gate_marker.get("gate_integration_marker"))
            if b5a_gate_marker
            else {},
            "preflight_validation": b5a_gate_marker_validation,
        },
        "production_acceptance": {
            "present": production_acceptance is not None and production_error is None,
            "load_error": production_error,
            "prod_4x4_record": prod_4x4_record,
            "result_validator": acceptance_validator_check,
        },
        "checks": checks,
    }


def render_phase3b_long_run_preflight_markdown(summary: Mapping[str, Any]) -> str:
    b2_advisory = _mapping(summary.get("b2_targeted_shrink"))
    coordinate_advisory = _mapping(summary.get("coordinate_validation_precheck"))
    coordinate_spec_advisory = _mapping(
        summary.get("coordinate_validation_promotion_spec")
    )
    zero_branch_advisory = _mapping(summary.get("zero_branch_unknown_triage"))
    power_protocol_advisory = _mapping(summary.get("power_protocol_interaction"))
    joined_xy_advisory = _mapping(summary.get("joined_xy_probe_synthesis"))
    lines = [
        "# Phase 3B Final Long-Run Preflight",
        "",
        "- Preflight gate ready: "
        f"{bool(summary.get('preflight_gate_ready', summary.get('ready_for_final_long_run', False)))}",
        "- Ready to request human launch authorization: "
        f"{bool(summary.get('ready_to_request_human_launch_authorization', False))}",
        f"- Final 168h authorized: {bool(summary.get('final_168h_authorized', False))}",
        f"- Execution allowed: {bool(summary.get('execution_allowed', False))}",
        f"- Recommendation: {summary.get('recommendation')}",
        f"- Dry-run command: `{_mapping(summary.get('final_long_run')).get('dry_run_command')}`",
        f"- B2 targeted shrink advisory: {b2_advisory.get('recommendation')}",
        f"- Coordinate-validation precheck advisory: {coordinate_advisory.get('recommendation')}",
        f"- Coordinate-validation promotion spec: {coordinate_spec_advisory.get('recommendation')}",
        f"- Zero-branch UNKNOWN triage: {zero_branch_advisory.get('recommendation')}",
        f"- Power/protocol interaction: {power_protocol_advisory.get('recommendation')}",
        f"- Joined-XY probe synthesis: {joined_xy_advisory.get('recommendation')}",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in list(summary.get("checks", [])):
        if not isinstance(check, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(check.get("check_id")),
                    _markdown_cell(check.get("status")),
                    _markdown_cell(check.get("detail")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def render_phase3b_long_run_preflight_text(summary: Mapping[str, Any]) -> str:
    b2_advisory = _mapping(summary.get("b2_targeted_shrink"))
    coordinate_advisory = _mapping(summary.get("coordinate_validation_precheck"))
    coordinate_spec_advisory = _mapping(
        summary.get("coordinate_validation_promotion_spec")
    )
    zero_branch_advisory = _mapping(summary.get("zero_branch_unknown_triage"))
    power_protocol_advisory = _mapping(summary.get("power_protocol_interaction"))
    joined_xy_advisory = _mapping(summary.get("joined_xy_probe_synthesis"))
    lines = [
        "Phase 3B final long-run preflight",
        "preflight_gate_ready="
        + str(bool(summary.get("preflight_gate_ready", summary.get("ready_for_final_long_run", False)))),
        "ready_to_request_human_launch_authorization="
        + str(bool(summary.get("ready_to_request_human_launch_authorization", False))),
        "final_168h_authorized="
        + str(bool(summary.get("final_168h_authorized", False))),
        "execution_allowed=" + str(bool(summary.get("execution_allowed", False))),
        f"ready_for_final_long_run={bool(summary.get('ready_for_final_long_run', False))}",
        f"recommendation={summary.get('recommendation')}",
        f"dry_run_command={_mapping(summary.get('final_long_run')).get('dry_run_command')}",
        f"b2_targeted_shrink={b2_advisory.get('recommendation')}",
        f"coordinate_validation_precheck={coordinate_advisory.get('recommendation')}",
        f"coordinate_validation_promotion_spec={coordinate_spec_advisory.get('recommendation')}",
        f"zero_branch_unknown_triage={zero_branch_advisory.get('recommendation')}",
        f"power_protocol_interaction={power_protocol_advisory.get('recommendation')}",
        f"joined_xy_probe_synthesis={joined_xy_advisory.get('recommendation')}",
    ]
    for check in list(summary.get("checks", [])):
        if not isinstance(check, Mapping):
            continue
        lines.append(
            f"check {check.get('check_id')} status={check.get('status')} detail={check.get('detail')}"
        )
    return "\n".join(lines) + "\n"


def _current_hashes(project_root: Path) -> tuple[Dict[str, str], Optional[str]]:
    try:
        return compute_exact_artifact_hashes(project_root), None
    except Exception as exc:
        return {}, f"exact_artifact_hash_error:{type(exc).__name__}:{exc}"


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"json_load_error:{type(exc).__name__}:{exc}"
    if not isinstance(payload, Mapping):
        return None, "json_payload_not_object"
    return dict(payload), None


def _operating_profile_locked(summary: Mapping[str, Any]) -> bool:
    defaults = _mapping(summary.get("defaults"))
    profile = _prod_profile(summary)
    env = _mapping(profile.get("env"))
    return (
        defaults.get("production_profile_id") == "prod_4x4_normal"
        and int(profile.get("parallel_processes", 0)) == 4
        and env.get("EXACT_CP_SAT_WORKERS") == "4"
        and profile.get("process_priority") == "normal"
        and profile.get("frontier_probe_mode") == "auto"
    )


def _prod_profile(summary: Mapping[str, Any]) -> Dict[str, Any]:
    profile_by_id = _mapping(summary.get("profile_by_id"))
    profile = profile_by_id.get("prod_4x4_normal")
    return dict(profile) if isinstance(profile, Mapping) else {}


def _b5a_anchor_found(summary: Optional[Mapping[str, Any]]) -> bool:
    if not isinstance(summary, Mapping):
        return False
    status = _mapping(summary.get("status"))
    return bool(status.get("anchor_found", False))


def _b5a_gate_marker_ready(marker: Optional[Mapping[str, Any]]) -> bool:
    if not isinstance(marker, Mapping):
        return False
    meta = _mapping(marker.get("metadata"))
    status = _mapping(marker.get("status"))
    payload = _mapping(marker.get("gate_integration_marker"))
    status_false_fields = (
        AUTHORIZATION_SAFETY_FALSE_FIELDS
        + PREFLIGHT_MUTATION_FALSE_FIELDS
        + [
            "proof_source",
            "runtime_semantics_changed",
            "checkpoint_written",
        ]
    )
    payload_false_fields = [
        "proof_source",
        "runtime_semantics_changed",
        "checkpoint_written",
    ] + AUTHORIZATION_SAFETY_FALSE_FIELDS + PREFLIGHT_MUTATION_FALSE_FIELDS
    return (
        meta.get("source") == B5A_GATE_INTEGRATION_MARKER_SOURCE
        and status.get("gate_integration_marker_ready") is True
        and status.get("repo_side_b5a_gate_state_updated") is True
        and status.get("b5a_anchor_found") is True
        and status.get("certified_anchor_found") is True
        and required_false(status, status_false_fields)
        and payload.get("gate_integration_marker_ready") is True
        and payload.get("b5a_anchor_found") is True
        and payload.get("certified_anchor_found") is True
        and required_false(payload, payload_false_fields)
    )


def _b5a_anchor_detail(
    summary: Optional[Mapping[str, Any]],
    load_error: Optional[str],
    marker: Optional[Mapping[str, Any]],
    marker_error: Optional[str],
    marker_path: Optional[Path],
    project_root: Path,
    marker_validation: Optional[Mapping[str, Any]] = None,
) -> str:
    if isinstance(marker_validation, Mapping) and marker_validation.get("accepted") is True:
        return (
            "B5A gate integration marker accepted certified-anchor promotion for "
            "candidate 67x13 anchors 118-125"
        )
    if _b5a_anchor_found(summary):
        return (
            "legacy B5A summary claims anchor_found=true, but final production "
            "preflight now requires an explicit accepted B5A gate integration marker"
        )
    detail = _b5a_block_reason(summary, load_error)
    if marker_path is not None:
        if not isinstance(marker, Mapping):
            marker_detail = marker_error or f"missing:{_display_path(project_root, marker_path)}"
        else:
            marker_status = _mapping(marker.get("status"))
            marker_detail = (
                "gate_integration_marker_ready="
                + str(marker_status.get("gate_integration_marker_ready"))
                + " b5a_anchor_found="
                + str(marker_status.get("b5a_anchor_found"))
                + " certified_anchor_found="
                + str(marker_status.get("certified_anchor_found"))
            )
            if isinstance(marker_validation, Mapping):
                marker_detail += (
                    " validation="
                    + str(marker_validation.get("summary"))
                )
        detail = detail + "; B5A gate integration marker not accepted: " + marker_detail
    return detail


def _b5a_block_reason(
    summary: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> str:
    if not isinstance(summary, Mapping):
        return load_error or "B5A operator summary missing"
    status = _mapping(summary.get("status"))
    return str(
        status.get("recommendation")
        or status.get("outcome")
        or "B5A did not find a certified anchor; return to B3/B2"
    )


def _acceptance_result_validator_for_preflight(
    *,
    project_root: Path,
    validator: Optional[Mapping[str, Any]],
    validator_error: Optional[str],
    validator_path: Optional[Path],
    acceptance_summary_path: Path,
    acceptance_summary: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    if validator_path is None:
        return {
            "accepted": False,
            "failed_rule_ids": ["explicit_production_acceptance_result_validator_present"],
            "rule_results": [],
            "summary": (
                "final production preflight requires "
                "--production-acceptance-result-validator"
            ),
        }
    if not isinstance(validator, Mapping):
        return {
            "accepted": False,
            "failed_rule_ids": ["production_acceptance_result_validator_loadable"],
            "rule_results": [
                _validation_rule(
                    "production_acceptance_result_validator_loadable",
                    False,
                    validator_error
                    or f"missing:{_display_path(project_root, validator_path)}",
                )
            ],
            "summary": validator_error
            or f"missing:{_display_path(project_root, validator_path)}",
        }
    meta = _mapping(validator.get("metadata"))
    paths = _mapping(validator.get("paths"))
    status = _mapping(validator.get("status"))
    contract = _mapping(validator.get("acceptance_result_validator"))
    result_validation = _mapping(validator.get("result_validation"))
    chain_input_hashes = list(validator.get("chain_input_hashes", []))
    expected_summary_path = _display_path(project_root, acceptance_summary_path)
    actual_summary_hash = sha256_file(acceptance_summary_path)
    recorded_summary_hash = result_validation.get("provided_acceptance_result_sha256")
    selected_record = _prod_4x4_record(acceptance_summary)
    chain_input_ids_exact, chain_input_ids_detail = _exact_chain_input_ids(
        chain_input_hashes,
        EXPECTED_ACCEPTANCE_VALIDATOR_CHAIN_INPUT_IDS,
    )
    chain_hash_check = _acceptance_validator_chain_hash_check(
        project_root=project_root,
        validator_paths=paths,
        acceptance_summary_path=acceptance_summary_path,
        records=chain_input_hashes,
        recorded_fingerprint=validator.get("chain_fingerprint"),
    )
    canonical_validator, canonical_error = (
        _rebuild_acceptance_result_validator_for_preflight(
            project_root=project_root,
            validator_paths=paths,
            acceptance_summary_path=acceptance_summary_path,
        )
    )
    canonical_signature = (
        _acceptance_validator_preflight_signature(canonical_validator)
        if canonical_validator is not None
        else None
    )
    provided_signature = _acceptance_validator_preflight_signature(validator)
    canonical_match = bool(
        canonical_validator is not None
        and canonical_error is None
        and canonical_signature == provided_signature
    )
    rules = [
        _validation_rule(
            "production_acceptance_result_validator_source_supported",
            meta.get("source")
            == "phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_v1",
            str(meta.get("source") or "missing"),
        ),
        _validation_rule(
            "production_acceptance_result_validator_ready",
            status.get("acceptance_result_validator_ready") is True,
            str(status.get("acceptance_result_validator_ready")),
        ),
        _validation_rule(
            "production_acceptance_result_validation_performed",
            status.get("acceptance_result_validation_performed") is True
            and result_validation.get("validation_performed") is True,
            "status="
            + str(status.get("acceptance_result_validation_performed"))
            + " result="
            + str(result_validation.get("validation_performed")),
        ),
        _validation_rule(
            "production_acceptance_result_validation_passed",
            status.get("acceptance_result_validation_passed") is True
            and result_validation.get("validation_passed") is True,
            "status="
            + str(status.get("acceptance_result_validation_passed"))
            + " result="
            + str(result_validation.get("validation_passed")),
        ),
        _validation_rule(
            "production_acceptance_result_validator_does_not_enable_runtime",
            status.get("runtime_enablement_allowed") is False
            and contract.get("does_not_imply_enablement") is True,
            "runtime_enablement_allowed="
            + str(status.get("runtime_enablement_allowed"))
            + " does_not_imply_enablement="
            + str(contract.get("does_not_imply_enablement")),
        ),
        _validation_rule(
            "production_acceptance_result_validator_matches_summary_path",
            result_validation.get("result_path_matches_expected") is True
            and _normalize_path_text(str(result_validation.get("provided_acceptance_result_path") or ""))
            == _normalize_path_text(expected_summary_path),
            "validator_path="
            + str(result_validation.get("provided_acceptance_result_path"))
            + " preflight_path="
            + expected_summary_path,
        ),
        _validation_rule(
            "production_acceptance_result_validator_matches_summary_hash",
            bool(
                actual_summary_hash
                and recorded_summary_hash
                and actual_summary_hash == recorded_summary_hash
            ),
            "validator_sha256="
            + str(recorded_summary_hash)
            + " current_sha256="
            + str(actual_summary_hash),
        ),
        _validation_rule(
            "production_acceptance_result_validator_chain_inputs_exact",
            chain_input_ids_exact,
            chain_input_ids_detail,
        ),
        _validation_rule(
            "production_acceptance_result_validator_chain_hashes_match",
            bool(chain_hash_check["hashes_match"]),
            str(chain_hash_check["hash_detail"]),
        ),
        _validation_rule(
            "production_acceptance_result_validator_chain_fingerprint_match",
            bool(chain_hash_check["fingerprint_match"]),
            str(chain_hash_check["fingerprint_detail"]),
        ),
        _validation_rule(
            "production_acceptance_result_validator_canonical_rebuild",
            canonical_validator is not None and canonical_error is None,
            canonical_error or "canonical acceptance result validator rebuilt",
        ),
        _validation_rule(
            "production_acceptance_result_validator_canonical_match",
            canonical_match,
            "provided_signature="
            + str(provided_signature)
            + " canonical_signature="
            + str(canonical_signature),
        ),
        _validation_rule(
            "production_acceptance_result_suite_contract_passed",
            result_validation.get("production_acceptance_suite_contract_passed") is True,
            str(result_validation.get("production_acceptance_suite_contract_detail")),
        ),
        _validation_rule(
            "production_acceptance_result_supporting_artifacts_passed",
            result_validation.get("supporting_artifacts_passed") is True,
            str(
                [
                    item.get("artifact_id")
                    for item in list(result_validation.get("supporting_artifact_results", []))
                    if isinstance(item, Mapping) and item.get("passed") is not True
                ]
            ),
        ),
        _validation_rule(
            "production_acceptance_result_prod_4x4_still_valid",
            _prod_4x4_record_valid(selected_record, summary=acceptance_summary),
            _prod_4x4_failure_detail(selected_record, summary=acceptance_summary)
            if not _prod_4x4_record_valid(selected_record, summary=acceptance_summary)
            else "prod_4x4 selected by preflight remains valid",
        ),
    ]
    accepted = all(rule["passed"] is True for rule in rules)
    return {
        "accepted": bool(accepted),
        "validator_path": _display_path(project_root, validator_path),
        "acceptance_summary_path": expected_summary_path,
        "acceptance_summary_sha256": actual_summary_hash,
        "canonical_validator_error": canonical_error,
        "provided_validator_signature": provided_signature,
        "canonical_validator_signature": canonical_signature,
        "recomputed_chain_input_hashes": chain_hash_check["recomputed_records"],
        "recomputed_chain_fingerprint": chain_hash_check["recomputed_fingerprint"],
        "failed_rule_ids": [
            str(rule["rule_id"]) for rule in rules if rule["passed"] is not True
        ],
        "rule_results": rules,
        "summary": (
            "production acceptance result validator passed and matches summary"
            if accepted
            else "production acceptance result validator rejected: "
            + ",".join(str(rule["rule_id"]) for rule in rules if rule["passed"] is not True)
        ),
    }


def _rebuild_acceptance_result_validator_for_preflight(
    *,
    project_root: Path,
    validator_paths: Mapping[str, Any],
    acceptance_summary_path: Path,
) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    missing = [
        field
        for field in [
            "acceptance_execution_staging",
            "pre_run_acceptance_validation",
            "provided_acceptance_result",
        ]
        if not str(validator_paths.get(field) or "").strip()
    ]
    if missing:
        return None, "missing_validator_paths:" + ",".join(missing)
    if _normalize_path_text(str(validator_paths.get("provided_acceptance_result"))) != _normalize_path_text(
        _display_path(project_root, acceptance_summary_path)
    ):
        return (
            None,
            "provided_acceptance_result_path_does_not_match_preflight_summary",
        )
    try:
        from src.search.phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator import (
            build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator,
        )

        return (
            build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator(
                project_root,
                acceptance_execution_staging_path=Path(
                    str(validator_paths["acceptance_execution_staging"])
                ),
                pre_run_acceptance_validation_path=Path(
                    str(validator_paths["pre_run_acceptance_validation"])
                ),
                acceptance_result_path=acceptance_summary_path,
            ),
            None,
        )
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _acceptance_validator_preflight_signature(
    validator: Mapping[str, Any],
) -> str:
    payload = _acceptance_validator_preflight_payload(validator)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _acceptance_validator_preflight_payload(
    validator: Mapping[str, Any],
) -> Dict[str, Any]:
    metadata = _mapping(validator.get("metadata"))
    paths = _mapping(validator.get("paths"))
    payload = {
        "metadata": {
            key: metadata.get(key)
            for key in ACCEPTANCE_VALIDATOR_STABLE_METADATA_FIELDS
        },
        "paths": {
            "acceptance_execution_staging": _normalize_path_text(
                str(paths.get("acceptance_execution_staging") or "")
            ),
            "pre_run_acceptance_validation": _normalize_path_text(
                str(paths.get("pre_run_acceptance_validation") or "")
            ),
            "expected_result_path": _normalize_path_text(
                str(paths.get("expected_result_path") or "")
            ),
            "provided_acceptance_result": _normalize_path_text(
                str(paths.get("provided_acceptance_result") or "")
            ),
        },
        "chain_input_hashes": [
            _normalize_acceptance_validator_value(record)
            for record in list(validator.get("chain_input_hashes", []))
        ],
        "chain_fingerprint": validator.get("chain_fingerprint"),
        "candidate": _normalize_acceptance_validator_value(validator.get("candidate")),
        "status": _normalize_acceptance_validator_value(validator.get("status")),
        "acceptance_result_validator": _normalize_acceptance_validator_value(
            validator.get("acceptance_result_validator")
        ),
        "result_validation": _normalize_acceptance_validator_value(
            validator.get("result_validation")
        ),
        "gates": _normalize_acceptance_validator_value(validator.get("gates")),
        "checks": _normalize_acceptance_validator_value(validator.get("checks")),
    }
    return payload


def _normalize_acceptance_validator_value(value: Any, key: str = "") -> Any:
    if isinstance(value, Mapping):
        return {
            str(child_key): _normalize_acceptance_validator_value(
                child_value,
                str(child_key),
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [
            _normalize_acceptance_validator_value(item, key)
            for item in value
        ]
    if isinstance(value, str) and (
        key == "path"
        or key.endswith("_path")
        or key in {
            "expected_result_path",
            "provided_acceptance_result",
            "acceptance_execution_staging",
            "pre_run_acceptance_validation",
        }
    ):
        return _normalize_path_text(value)
    return value


def _exact_chain_input_ids(
    records: list[Any],
    expected: list[str],
) -> tuple[bool, str]:
    actual: list[str] = []
    malformed = 0
    for record in records:
        if not isinstance(record, Mapping):
            malformed += 1
            continue
        actual.append(str(record.get("input_id") or ""))
    duplicates = sorted({item for item in actual if actual.count(item) > 1})
    ok = bool(malformed == 0 and actual == expected and not duplicates)
    return (
        ok,
        "actual="
        + str(actual)
        + " expected="
        + str(expected)
        + " malformed="
        + str(malformed)
        + " duplicates="
        + str(duplicates),
    )


def _acceptance_validator_chain_hash_check(
    *,
    project_root: Path,
    validator_paths: Mapping[str, Any],
    acceptance_summary_path: Path,
    records: list[Any],
    recorded_fingerprint: Any,
) -> Dict[str, Any]:
    expected_paths = {
        "acceptance_execution_staging": _resolve_path(
            project_root,
            Path(str(validator_paths.get("acceptance_execution_staging") or "")),
        ),
        "pre_run_acceptance_validation": _resolve_path(
            project_root,
            Path(str(validator_paths.get("pre_run_acceptance_validation") or "")),
        ),
        "provided_acceptance_result": acceptance_summary_path,
    }
    records_by_id: dict[str, list[Mapping[str, Any]]] = {}
    malformed = 0
    for record in records:
        if not isinstance(record, Mapping):
            malformed += 1
            continue
        input_id = str(record.get("input_id") or "")
        records_by_id.setdefault(input_id, []).append(record)

    problems: list[str] = []
    recomputed_records: list[Dict[str, str]] = []
    if malformed:
        problems.append(f"malformed_records={malformed}")
    for input_id in EXPECTED_ACCEPTANCE_VALIDATOR_CHAIN_INPUT_IDS:
        matches = records_by_id.get(input_id, [])
        if len(matches) != 1:
            problems.append(f"{input_id}.record_count={len(matches)}")
            continue
        record = matches[0]
        expected_path = expected_paths[input_id]
        expected_display = _display_path(project_root, expected_path)
        recorded_path = str(record.get("path") or "")
        if _normalize_path_text(recorded_path) != _normalize_path_text(expected_display):
            problems.append(
                f"{input_id}.path={recorded_path!r} expected={expected_display!r}"
            )
        if record.get("exists") is not True:
            problems.append(f"{input_id}.exists={record.get('exists')!r}")
        recorded_sha = str(record.get("sha256") or "")
        actual_sha = sha256_file(expected_path)
        if not _is_sha256_hex(recorded_sha):
            problems.append(f"{input_id}.sha256=invalid_or_missing")
        if actual_sha is None:
            problems.append(f"{input_id}.actual_sha256=missing")
            continue
        if recorded_sha != actual_sha:
            problems.append(
                f"{input_id}.sha256_mismatch recorded={recorded_sha} actual={actual_sha}"
            )
        recomputed_records.append(
            {
                "input_id": input_id,
                "path": expected_display,
                "sha256": actual_sha,
            }
        )

    extra_ids = sorted(
        input_id
        for input_id in records_by_id
        if input_id not in EXPECTED_ACCEPTANCE_VALIDATOR_CHAIN_INPUT_IDS
    )
    if extra_ids:
        problems.append("extra_input_ids=" + ",".join(extra_ids))

    recomputed_fingerprint = chain_fingerprint(recomputed_records)
    recorded_fingerprint_text = str(recorded_fingerprint or "")
    fingerprint_match = bool(
        _is_sha256_hex(recorded_fingerprint_text)
        and recomputed_fingerprint
        and recorded_fingerprint_text == recomputed_fingerprint
    )
    if not fingerprint_match:
        problems.append(
            "fingerprint_mismatch recorded="
            + recorded_fingerprint_text
            + " recomputed="
            + str(recomputed_fingerprint)
        )
    return {
        "hashes_match": not problems,
        "fingerprint_match": fingerprint_match,
        "hash_detail": "all_chain_input_hashes_match"
        if not problems
        else "; ".join(problems),
        "fingerprint_detail": "chain_fingerprint_matches_recomputed_inputs"
        if fingerprint_match
        else "recorded="
        + recorded_fingerprint_text
        + " recomputed="
        + str(recomputed_fingerprint),
        "recomputed_records": recomputed_records,
        "recomputed_fingerprint": recomputed_fingerprint,
    }


def _is_sha256_hex(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _prod_4x4_record(summary: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(summary, Mapping):
        return None
    if summary.get("suite_kind") != "production-acceptance":
        return None
    records: list[Dict[str, Any]] = []
    for record in list(summary.get("run_records", [])):
        if not isinstance(record, Mapping):
            continue
        if (
            str(record.get("label", "")) == "prod_4x4"
            and _int_field(record, "process_count") == 4
            and _int_field(record, "worker_count_per_process") == 4
        ):
            records.append(dict(record))
    return records[0] if len(records) == 1 else None


def _prod_4x4_record_valid(
    record: Optional[Mapping[str, Any]],
    *,
    summary: Optional[Mapping[str, Any]] = None,
) -> bool:
    if not isinstance(record, Mapping):
        return False
    if summary is not None and (
        not isinstance(summary, Mapping)
        or summary.get("suite_kind") != "production-acceptance"
        or not _production_acceptance_summary_contract_valid(summary)
    ):
        return False
    return (
        record.get("label") == "prod_4x4"
        and _int_field(record, "process_count") == 4
        and _int_field(record, "worker_count_per_process") == 4
        and record.get("completed") is True
        and _int_field(record, "return_code") == 0
        and record.get("campaign_valid_after_run") is True
        and record.get("duplicated_work") is False
    )


def _prod_4x4_failure_detail(
    record: Optional[Mapping[str, Any]],
    *,
    summary: Optional[Mapping[str, Any]] = None,
) -> str:
    if summary is not None and not _production_acceptance_summary_contract_valid(summary):
        return (
            "production acceptance summary does not satisfy the locked suite "
            "contract: "
            + _production_acceptance_summary_contract_detail(summary)
        )
    if not isinstance(record, Mapping):
        return (
            "exactly one prod_4x4 production-acceptance record with label, "
            "process_count=4 and worker_count_per_process=4 is required"
        )
    return (
        "prod_4x4 invalid: "
        f"label={record.get('label')} "
        f"process_count={record.get('process_count')} "
        f"worker_count_per_process={record.get('worker_count_per_process')} "
        f"completed={record.get('completed')} "
        f"return_code={record.get('return_code')} "
        f"campaign_valid_after_run={record.get('campaign_valid_after_run')} "
        f"duplicated_work={record.get('duplicated_work')}"
    )


def _production_acceptance_summary_contract_valid(
    summary: Optional[Mapping[str, Any]],
) -> bool:
    return not _production_acceptance_summary_contract_violations(summary)


def _production_acceptance_summary_contract_detail(
    summary: Optional[Mapping[str, Any]],
) -> str:
    violations = _production_acceptance_summary_contract_violations(summary)
    return "ok" if not violations else ",".join(violations)


def _production_acceptance_summary_contract_violations(
    summary: Optional[Mapping[str, Any]],
) -> list[str]:
    if not isinstance(summary, Mapping):
        return ["summary_not_object"]
    violations: list[str] = []
    if summary.get("suite_kind") != "production-acceptance":
        violations.append("suite_kind")
    benchmark_inputs = _mapping(summary.get("benchmark_inputs"))
    if benchmark_inputs.get("grid_w") != 70:
        violations.append("benchmark_inputs.grid_w")
    if benchmark_inputs.get("grid_h") != 70:
        violations.append("benchmark_inputs.grid_h")
    if benchmark_inputs.get("safe_area_upper_bound") != EXPECTED_PRODUCTION_SAFE_AREA_UPPER_BOUND:
        violations.append("benchmark_inputs.safe_area_upper_bound")
    if benchmark_inputs.get("selected_candidate") != EXPECTED_PRODUCTION_SELECTED_CANDIDATE:
        violations.append("benchmark_inputs.selected_candidate")
    if benchmark_inputs.get("frontier_candidates") != EXPECTED_PRODUCTION_FRONTIER_CANDIDATES:
        violations.append("benchmark_inputs.frontier_candidates")
    if not isinstance(summary.get("generated_at_epoch"), (int, float)):
        violations.append("generated_at_epoch")
    if _int_field(summary, "logical_cpu_count") is None or _int_field(
        summary, "logical_cpu_count"
    ) <= 0:
        violations.append("logical_cpu_count")
    if _int_field(summary, "physical_cpu_count") is None or _int_field(
        summary, "physical_cpu_count"
    ) <= 0:
        violations.append("physical_cpu_count")
    if summary.get("requested_master_search_profile") != EXPECTED_PRODUCTION_MASTER_SEARCH_PROFILE:
        violations.append("requested_master_search_profile")
    if not str(summary.get("process_priority_mode") or "").strip():
        violations.append("process_priority_mode")

    raw_records = summary.get("run_records", [])
    records = list(raw_records) if isinstance(raw_records, list) else []
    if not isinstance(raw_records, list):
        violations.append("run_records")
    labels = [
        str(record.get("label") or "")
        for record in records
        if isinstance(record, Mapping)
    ]
    if sorted(labels) != sorted(EXPECTED_PRODUCTION_ACCEPTANCE_LABELS):
        violations.append("run_record_labels")
    if len(labels) != len(set(labels)):
        violations.append("duplicate_run_record_labels")
    for record in records:
        if not isinstance(record, Mapping):
            violations.append("run_record_not_object")
            continue
        label = str(record.get("label") or "")
        expected_parallelism = EXPECTED_PRODUCTION_ACCEPTANCE_LABELS.get(label)
        if expected_parallelism is None:
            continue
        expected_process_count, expected_worker_count = expected_parallelism
        if _int_field(record, "process_count") != expected_process_count:
            violations.append(f"{label}.process_count")
        if _int_field(record, "worker_count_per_process") != expected_worker_count:
            violations.append(f"{label}.worker_count_per_process")
        if _int_field(record, "parallel_processes") != expected_process_count:
            violations.append(f"{label}.parallel_processes")
        if record.get("target") != "production-campaign-run":
            violations.append(f"{label}.target")
        if record.get("requested_master_search_profile") != EXPECTED_PRODUCTION_MASTER_SEARCH_PROFILE:
            violations.append(f"{label}.requested_master_search_profile")
        for field in ["command", "project_root", "output_json", "log_path"]:
            if not str(record.get(field) or "").strip():
                violations.append(f"{label}.{field}")
        if not isinstance(record.get("wall_seconds"), (int, float)):
            violations.append(f"{label}.wall_seconds")
    return violations


def _int_field(record: Mapping[str, Any], key: str) -> Optional[int]:
    value = record.get(key)
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _b2_targeted_shrink_advisory(
    promotion_spec: Optional[Mapping[str, Any]],
    load_error: Optional[str],
    proof_promotion: Optional[Mapping[str, Any]],
    proof_load_error: Optional[str],
) -> Dict[str, Any]:
    proof_readiness = _mapping(proof_promotion.get("promotion_readiness")) if proof_promotion else {}
    proof_blockers = [
        str(item) for item in list(proof_readiness.get("blocked_by", []))
    ]
    if not isinstance(promotion_spec, Mapping):
        return {
            "present": False,
            "load_error": load_error,
            "proof_promotion_present": proof_promotion is not None and proof_load_error is None,
            "proof_promotion_load_error": proof_load_error,
            "proof_promotion_ready": bool(proof_readiness.get("proof_promotion_ready", False)),
            "proof_promotion_blocked_by": proof_blockers,
            "spec_ready_for_runtime_slice": False,
            "runtime_promotion_ready": False,
            "runtime_promotion_guarded": False,
            "candidate": {},
            "promotion_blocked_by": ["promotion_spec_missing"],
            "recommendation": (
                "No B2 group-packing promotion spec is available; use B3 triage "
                "or rebuild the precheck promotion spec before runtime shrink work."
            ),
        }
    status = _mapping(promotion_spec.get("promotion_status"))
    candidate = _mapping(promotion_spec.get("candidate"))
    return {
        "present": True,
        "load_error": load_error,
        "proof_promotion_present": proof_promotion is not None and proof_load_error is None,
        "proof_promotion_load_error": proof_load_error,
        "proof_promotion_ready": bool(
            proof_readiness.get("proof_promotion_ready", False)
        ),
        "proof_promotion_blocked_by": proof_blockers,
        "soundness_gate_terminal_safe": _check_passed(
            proof_promotion,
            "soundness_gate_terminal_safe",
        ),
        "spec_ready_for_runtime_slice": bool(
            status.get("spec_ready_for_runtime_slice", False)
        ),
        "runtime_promotion_ready": bool(status.get("runtime_promotion_ready", False)),
        "runtime_promotion_guarded": bool(
            status.get("runtime_promotion_guarded", False)
        ),
        "candidate": dict(candidate),
        "promotion_blocked_by": [
            str(item) for item in list(status.get("promotion_blocked_by", []))
        ],
        "recommendation": _b2_advisory_recommendation(
            status,
            candidate,
            proof_promotion=proof_promotion,
            proof_load_error=proof_load_error,
            proof_blockers=proof_blockers,
            proof_ready=bool(proof_readiness.get("proof_promotion_ready", False)),
        ),
    }


def _coordinate_validation_precheck_advisory(
    report: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(report, Mapping):
        return {
            "present": False,
            "load_error": load_error,
            "design_gate_passed": False,
            "runtime_promotion_ready": False,
            "candidate": {},
            "coordinate_rejected_count": 0,
            "matrix_all_infeasible": False,
            "row_domain_runtime_patch_ready": False,
            "row_domain_review_state_ready": False,
            "reviewed_runtime_patch_exists": False,
            "runtime_enablement_allowed": False,
            "recommendation": (
                "No coordinate-validation precheck candidate report is available."
            ),
        }
    gate = _mapping(report.get("gate"))
    validation = _mapping(report.get("coordinate_validation"))
    matrix = _mapping(report.get("forced_anchor_solver_matrix"))
    joined_xy_current_blocker = _mapping(report.get("joined_xy_current_blocker"))
    joined_xy_proof_candidate = _mapping(
        report.get("joined_xy_proof_preserving_candidate")
    )
    candidate = _mapping(report.get("candidate"))
    row_domain_runtime_patch_ready = bool(
        joined_xy_proof_candidate.get("row_domain_runtime_patch_ready", False)
    )
    row_domain_review_state_ready = bool(
        joined_xy_proof_candidate.get("row_domain_review_state_ready", False)
    )
    reviewed_runtime_patch_exists = bool(
        joined_xy_proof_candidate.get("reviewed_runtime_patch_exists", False)
    )
    runtime_enablement_allowed = bool(
        joined_xy_proof_candidate.get("runtime_enablement_allowed", False)
    )
    design_gate_passed = bool(gate.get("design_gate_passed", False))
    runtime_ready = bool(gate.get("runtime_promotion_ready", False))
    if (
        row_domain_review_state_ready
        and reviewed_runtime_patch_exists
        and not runtime_enablement_allowed
    ):
        recommendation = joined_xy_proof_candidate.get(
            "recommendation",
            gate.get(
                "recommendation",
                "Reviewed runtime patch state is marked; refresh production acceptance next.",
            ),
        )
    elif bool(joined_xy_current_blocker.get("active", False)):
        if bool(joined_xy_proof_candidate.get("proof_preserving_precheck_ready", False)):
            recommendation = joined_xy_proof_candidate.get(
                "recommendation",
                "Joined-XY proof-preserving extraction is ready for review gating.",
            )
        else:
            recommendation = joined_xy_current_blocker.get(
                "recommendation",
                "Joined-XY points at the current coordinate-validation blocker.",
            )
    elif design_gate_passed and not runtime_ready:
        recommendation = (
            "Coordinate-validation evidence is ready as a B2 design candidate, "
            "but runtime promotion remains guarded."
        )
    elif runtime_ready:
        recommendation = (
            "Coordinate-validation runtime promotion is marked ready; implement guarded "
            "pre-master tests and rerun B5A."
        )
    else:
        recommendation = gate.get(
            "recommendation",
            "Coordinate-validation evidence is incomplete.",
        )
    return {
        "present": True,
        "load_error": load_error,
        "design_gate_passed": design_gate_passed,
        "runtime_promotion_ready": runtime_ready,
        "candidate": dict(candidate),
        "coordinate_rejected_count": int(validation.get("rejected_count", 0)),
        "matrix_all_infeasible": bool(matrix.get("matrix_all_infeasible", False)),
        "joined_xy_current_blocker_active": bool(
            joined_xy_current_blocker.get("active", False)
        ),
        "joined_xy_proof_candidate_ready": bool(
            joined_xy_proof_candidate.get("proof_preserving_precheck_ready", False)
        ),
        "row_domain_runtime_patch_ready": row_domain_runtime_patch_ready,
        "row_domain_review_state_ready": row_domain_review_state_ready,
        "reviewed_runtime_patch_exists": reviewed_runtime_patch_exists,
        "runtime_enablement_allowed": runtime_enablement_allowed,
        "recommendation": str(recommendation),
    }


def _coordinate_validation_promotion_advisory(
    report: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(report, Mapping):
        return {
            "present": False,
            "load_error": load_error,
            "spec_ready_for_runtime_slice": False,
            "runtime_slice_implemented": False,
            "runtime_promotion_ready": False,
            "runtime_promotion_guarded": False,
            "candidate": {},
            "promotion_blocked_by": ["promotion_spec_missing"],
            "recommendation": (
                "No coordinate-validation promotion spec is available."
            ),
        }
    status = _mapping(report.get("promotion_status"))
    evidence = _mapping(report.get("evidence_summary"))
    candidate = _mapping(report.get("candidate"))
    blocked_by = [str(item) for item in list(status.get("promotion_blocked_by", []))]
    spec_ready = bool(status.get("spec_ready_for_runtime_slice", False))
    runtime_slice_implemented = bool(status.get("runtime_slice_implemented", False))
    runtime_ready = bool(status.get("runtime_promotion_ready", False))
    guarded = bool(status.get("runtime_promotion_guarded", False))
    explicit_recommendation = status.get("recommendation")
    if spec_ready and guarded and runtime_slice_implemented and not runtime_ready:
        if explicit_recommendation:
            recommendation = str(explicit_recommendation)
        elif bool(evidence.get("joined_xy_proof_candidate_design_ready", False)) and not bool(
            evidence.get("joined_xy_proof_candidate_ready", False)
        ):
            recommendation = (
                "Guarded coordinate-validation runtime precheck exists, but the preferred "
                "next move is to finish the joined-XY proof-preserving extraction around "
                "protocol_planter_buckwheat_3_x_labels before any B5A workspace rerun."
            )
        else:
            recommendation = (
                "Coordinate-validation runtime precheck is available only as a guarded "
                "B5A workspace rerun; production promotion remains blocked until fresh "
                "B5A evidence."
            )
    elif spec_ready and guarded and not runtime_ready:
        recommendation = (
            "Coordinate-validation promotion spec is ready for a guarded runtime slice; "
            "runtime promotion remains blocked until implementation tests and B5A rerun."
        )
    else:
        recommendation = status.get(
            "recommendation",
            "Coordinate-validation promotion spec is not ready.",
        )
    return {
        "present": True,
        "load_error": load_error,
        "spec_ready_for_runtime_slice": spec_ready,
        "runtime_slice_implemented": runtime_slice_implemented,
        "runtime_promotion_ready": runtime_ready,
        "runtime_promotion_guarded": guarded,
        "candidate": dict(candidate),
        "promotion_blocked_by": blocked_by,
        "recommendation": str(recommendation),
    }


def _zero_branch_unknown_advisory(
    report: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(report, Mapping):
        return {
            "present": False,
            "load_error": load_error,
            "zero_branch_unknown_count": 0,
            "candidate": {},
            "findings": [],
            "recommendation": "No zero-branch UNKNOWN triage report is available.",
        }
    matrix = _mapping(report.get("matrix"))
    candidate = _mapping(report.get("candidate"))
    findings = [str(item) for item in list(report.get("findings", []))]
    return {
        "present": True,
        "load_error": load_error,
        "zero_branch_unknown_count": int(matrix.get("zero_branch_unknown_count", 0)),
        "candidate": dict(candidate),
        "findings": findings,
        "recommendation": str(
            report.get(
                "recommendation",
                "Zero-branch UNKNOWN triage report is present.",
            )
        ),
    }


def _power_protocol_interaction_advisory(
    report: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(report, Mapping):
        return {
            "present": False,
            "load_error": load_error,
            "candidate": {},
            "primary_hypothesis": None,
            "next_probe_family": None,
            "next_probe_template": None,
            "findings": [],
            "recommendation": "No power/protocol interaction diagnostic is available.",
        }
    candidate = _mapping(report.get("candidate"))
    analysis = _mapping(report.get("analysis"))
    return {
        "present": True,
        "load_error": load_error,
        "candidate": dict(candidate),
        "primary_hypothesis": analysis.get("primary_hypothesis"),
        "next_probe_family": analysis.get("next_probe_family"),
        "next_probe_template": analysis.get("next_probe_template"),
        "findings": [str(item) for item in list(report.get("findings", []))],
        "recommendation": str(
            report.get(
                "recommendation",
                "Power/protocol interaction diagnostic is present.",
            )
        ),
    }


def _joined_xy_probe_synthesis_advisory(
    report: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(report, Mapping):
        return {
            "present": False,
            "load_error": load_error,
            "completed": False,
            "terminal_anchor_indices": [],
            "search_progress_unknown_anchor_indices": [],
            "zero_branch_unknown_count": 0,
            "recommendation": "No joined-XY probe synthesis report is available.",
        }
    status = _mapping(report.get("status"))
    aggregate = _mapping(report.get("aggregate"))
    return {
        "present": True,
        "load_error": load_error,
        "completed": bool(status.get("completed", False)),
        "outcome": status.get("outcome"),
        "terminal_anchor_indices": list(aggregate.get("terminal_anchor_indices", [])),
        "search_progress_unknown_anchor_indices": list(
            aggregate.get("search_progress_unknown_anchor_indices", [])
        ),
        "zero_branch_unknown_count": int(aggregate.get("zero_branch_unknown_count", 0)),
        "recommendation": str(
            status.get(
                "recommendation",
                "Joined-XY probe synthesis report is present.",
            )
        ),
    }


def _b2_advisory_recommendation(
    status: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    proof_promotion: Optional[Mapping[str, Any]],
    proof_load_error: Optional[str],
    proof_blockers: list[str],
    proof_ready: bool,
) -> str:
    if isinstance(proof_promotion, Mapping):
        if proof_ready:
            return (
                "B2 group-packing proof-promotion report is ready for "
                f"{candidate.get('key')}; implement the terminal proof integration "
                "and rerun B5A."
            )
        return (
            "B2 group-packing remains diagnostic-only for "
            f"{candidate.get('key')}; resolve proof-promotion blockers before "
            "any guarded shrink: "
            + ", ".join(proof_blockers)
        )
    if proof_load_error:
        return (
            "B2 group-packing proof-promotion report failed to load; repair "
            f"{proof_load_error} before shrink work."
        )
    if bool(status.get("spec_ready_for_runtime_slice", False)):
        return (
            "B2 group-packing promotion spec is diagnostically ready for "
            f"{candidate.get('key')}, but proof-promotion/soundness evidence is "
            "missing; rebuild that report before guarded shrink work."
        )
    return (
        "B2 group-packing promotion spec is not ready; repair the diagnostic "
        "promotion blockers before runtime shrink work."
    )


def _recommendation(
    *,
    ready: bool,
    checks: list[Mapping[str, Any]],
    b5a_summary: Optional[Mapping[str, Any]],
    group_packing_promotion_spec: Optional[Mapping[str, Any]],
    group_packing_promotion_spec_error: Optional[str],
    group_packing_proof_promotion: Optional[Mapping[str, Any]],
    group_packing_proof_promotion_error: Optional[str],
    coordinate_validation_precheck: Optional[Mapping[str, Any]],
    coordinate_validation_precheck_error: Optional[str],
    coordinate_validation_promotion_spec: Optional[Mapping[str, Any]],
    coordinate_validation_promotion_spec_error: Optional[str],
    zero_branch_unknown_triage: Optional[Mapping[str, Any]],
    zero_branch_unknown_triage_error: Optional[str],
    power_protocol_interaction: Optional[Mapping[str, Any]],
    power_protocol_interaction_error: Optional[str],
    joined_xy_probe_synthesis: Optional[Mapping[str, Any]],
    joined_xy_probe_synthesis_error: Optional[str],
) -> str:
    if ready:
        return (
            "Preflight gate is ready to request human final-launch authorization; "
            "this is not launch authorization and the final 168h run must not start in this step."
        )
    failed = [
        str(check.get("check_id"))
        for check in checks
        if str(check.get("status")) == "fail"
    ]
    production_acceptance_ready = (
        "explicit_production_acceptance_summary_present" not in failed
        and "explicit_production_acceptance_result_validator_present" not in failed
        and
        "production_acceptance_present" not in failed
        and "production_acceptance_prod_4x4_valid" not in failed
        and "production_acceptance_result_validator_passed" not in failed
    )
    if "b5a_anchor_found" in failed:
        b5a_stop_reason = _b5a_last_stop_reason(b5a_summary)
        if b5a_stop_reason == "b5a_wall_timeout":
            return (
                "Blocked before final long run: latest B5A ended with b5a_wall_timeout; "
                "inspect the timeout workspace and keep production acceptance/final long run blocked."
            )
        advisory = _b2_targeted_shrink_advisory(
            group_packing_promotion_spec,
            group_packing_promotion_spec_error,
            group_packing_proof_promotion,
            group_packing_proof_promotion_error,
        )
        coordinate_advisory = _coordinate_validation_precheck_advisory(
            coordinate_validation_precheck,
            coordinate_validation_precheck_error,
        )
        coordinate_spec_advisory = _coordinate_validation_promotion_advisory(
            coordinate_validation_promotion_spec,
            coordinate_validation_promotion_spec_error,
        )
        zero_branch_advisory = _zero_branch_unknown_advisory(
            zero_branch_unknown_triage,
            zero_branch_unknown_triage_error,
        )
        power_protocol_advisory = _power_protocol_interaction_advisory(
            power_protocol_interaction,
            power_protocol_interaction_error,
        )
        joined_xy_advisory = _joined_xy_probe_synthesis_advisory(
            joined_xy_probe_synthesis,
            joined_xy_probe_synthesis_error,
        )
        coordinate_review_state_ready = bool(
            coordinate_advisory.get("row_domain_review_state_ready", False)
        ) and bool(
            coordinate_advisory.get("reviewed_runtime_patch_exists", False)
        ) and not bool(
            coordinate_advisory.get("runtime_enablement_allowed", False)
        )
        b5a_master_unknown = _b5a_master_unknown_diagnostic(b5a_summary)
        if bool(joined_xy_advisory.get("completed", False)):
            if bool(b5a_master_unknown.get("conflictful_unknown", False)):
                failure_counts = _mapping(b5a_master_unknown.get("failure_reason_counts"))
                coordinate_infeasible = int(
                    failure_counts.get("coordinate_validation_infeasible", 0)
                )
                if coordinate_review_state_ready:
                    if production_acceptance_ready:
                        coordinate_next_step = (
                            "Reviewed runtime patch state and prod_4x4_normal production "
                            "acceptance are both validated. The remaining gate is B5A "
                            "certified-anchor evidence; continue B5A/B2 targeted shrink or "
                            "anchor-proof work without enabling runtime elimination."
                        )
                    else:
                        coordinate_next_step = str(
                            coordinate_advisory.get("recommendation")
                            or "Reviewed runtime patch state is marked; refresh prod_4x4_normal production acceptance next."
                        )
                else:
                    coordinate_next_step = str(
                        coordinate_spec_advisory.get("recommendation")
                        or coordinate_advisory.get("recommendation")
                        or "Inspect the coordinate-validation / ghost-aware start gate under joined-XY."
                    )
                return (
                    "Blocked before final long run: B5A did not find a certified anchor; "
                    "joined-XY workspace validation already reached conflictful master "
                    f"UNKNOWN for {b5a_master_unknown.get('candidate_key')} "
                    f"(branches={b5a_master_unknown.get('branches')}, "
                    f"conflicts={b5a_master_unknown.get('conflicts')}, "
                    f"deterministic_time={b5a_master_unknown.get('deterministic_time')}). "
                    f"coordinate_validation_infeasible currently rejects {coordinate_infeasible} "
                    "sampled anchors. Joined-XY 300s focus now covers anchors 119-125 "
                    "and all remain conflictful UNKNOWN, while anchor118 stays terminal "
                    "and the targeted set has no zero-branch UNKNOWN. Next step: "
                    f"{coordinate_next_step} Do not rerun bounded workspace validation "
                    "until that gate changes, and do not launch final 168h."
                )
            return (
                "Blocked before final long run: B5A did not find a certified anchor; "
                "joined-XY is now the active bounded diagnostic route, with terminal "
                f"anchors {joined_xy_advisory.get('terminal_anchor_indices')} and "
                "search-progress UNKNOWN for "
                f"{joined_xy_advisory.get('search_progress_unknown_anchor_indices')}. "
                f"{joined_xy_advisory.get('recommendation')}"
            )
        if bool(b5a_master_unknown.get("conflictful_unknown", False)):
            failure_counts = _mapping(b5a_master_unknown.get("failure_reason_counts"))
            coordinate_infeasible = int(
                failure_counts.get("coordinate_validation_infeasible", 0)
            )
            return (
                "Blocked before final long run: B5A did not find a certified anchor; "
                "latest B5A reached conflictful master UNKNOWN for "
                f"{b5a_master_unknown.get('candidate_key')} "
                f"(branches={b5a_master_unknown.get('branches')}, "
                f"conflicts={b5a_master_unknown.get('conflicts')}, "
                f"deterministic_time={b5a_master_unknown.get('deterministic_time')}). "
                f"Ghost-aware coordinate validation now rejects {coordinate_infeasible} sampled anchors; "
                "continue with B2/B3 targeted shrink of the master search surface, not final long run."
            )
        if bool(zero_branch_advisory.get("present", False)) and int(
            zero_branch_advisory.get("zero_branch_unknown_count", 0)
        ) > 0:
            zero_candidate = _mapping(zero_branch_advisory.get("candidate"))
            power_protocol_detail = ""
            if bool(power_protocol_advisory.get("present", False)):
                power_protocol_detail = (
                    " Power/protocol interaction diagnostic narrows the next probe to "
                    f"{power_protocol_advisory.get('primary_hypothesis')}"
                    f" (family={power_protocol_advisory.get('next_probe_family')}, "
                    f"template={power_protocol_advisory.get('next_probe_template')})."
                )
            return (
                "Blocked before final long run: B5A did not find a certified anchor; "
                "zero-branch UNKNOWN triage for "
                f"{zero_candidate.get('key')} points to presolve/model-building work: "
                f"{zero_branch_advisory.get('recommendation')}"
                f"{power_protocol_detail}"
            )
        if (
            bool(coordinate_advisory.get("design_gate_passed", False))
            and bool(coordinate_spec_advisory.get("spec_ready_for_runtime_slice", False))
            and bool(coordinate_spec_advisory.get("runtime_slice_implemented", False))
            and not bool(coordinate_spec_advisory.get("runtime_promotion_ready", False))
        ):
            coordinate_candidate = _mapping(coordinate_spec_advisory.get("candidate"))
            group_blockers = []
            if bool(advisory.get("proof_promotion_present", False)) and not bool(
                advisory.get("proof_promotion_ready", False)
            ):
                group_blockers = [
                    str(item)
                    for item in list(advisory.get("proof_promotion_blocked_by", []))
                ]
            group_detail = (
                "; group-packing remains diagnostic-only"
                + (": " + ", ".join(group_blockers) if group_blockers else "")
            )
            return (
                "Blocked before final long run: B5A did not find a certified anchor; "
                "coordinate-validation is the active B2 follow-up for "
                f"{coordinate_candidate.get('key')}, but promotion remains guarded "
                "until fresh B5A evidence confirms the runtime slice"
                f"{group_detail}."
            )
        if bool(advisory.get("proof_promotion_present", False)) and not bool(
            advisory.get("proof_promotion_ready", False)
        ):
            blockers = ", ".join(
                str(item) for item in list(advisory.get("proof_promotion_blocked_by", []))
            )
            return (
                "Blocked before final long run: B5A did not find a certified anchor; "
                "group-packing remains diagnostic-only, so resolve proof-promotion "
                f"blockers before B2 shrink/B5A rerun: {blockers}."
            )
        if bool(advisory.get("proof_promotion_ready", False)):
            candidate = _mapping(advisory.get("candidate"))
            return (
                "Blocked before final long run: B5A did not find a certified anchor; "
                f"B2 group-packing proof promotion is ready for {candidate.get('key')}, "
                "so implement terminal proof integration and rerun B5A before production acceptance."
            )
        if bool(advisory.get("spec_ready_for_runtime_slice", False)):
            candidate = _mapping(advisory.get("candidate"))
            return (
                "Blocked before final long run: B5A did not find a certified anchor; "
                f"group-packing diagnostics point at {candidate.get('key')}, but "
                "proof-promotion/soundness evidence is missing, so rebuild that report "
                "before B2 shrink/B5A rerun."
            )
        return "Blocked before final long run: B5A did not find a certified anchor; return to B3 triage or B2 targeted shrink."
    if "production_acceptance_prod_4x4_valid" in failed or "production_acceptance_present" in failed:
        return "Blocked before final long run: run or repair production-acceptance for prod_4x4."
    return "Blocked before final long run: repair failed preflight checks before any 168h run."


def _b5a_last_stop_reason(summary: Optional[Mapping[str, Any]]) -> str:
    if not isinstance(summary, Mapping):
        return ""
    campaign = _mapping(summary.get("campaign"))
    last_stop_reason = _mapping(campaign.get("last_stop_reason"))
    return str(last_stop_reason.get("reason", ""))


def _b5a_master_unknown_diagnostic(
    summary: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    if not isinstance(summary, Mapping):
        return {}
    triage = _mapping(summary.get("triage"))
    top_blockers = [
        entry
        for entry in list(triage.get("top_blockers", []))
        if isinstance(entry, Mapping)
    ]
    if not top_blockers:
        return {}
    blocker = top_blockers[0]
    proof_summary = _mapping(blocker.get("proof_summary"))
    if not proof_summary:
        evidence_refs = _mapping(blocker.get("evidence_refs"))
        proof_fields = _mapping(evidence_refs.get("proof_fields"))
        proof_summary = proof_fields
    master_last_solve = _mapping(proof_summary.get("master_last_solve"))
    if str(proof_summary.get("master_status")) != "UNKNOWN":
        return {}
    branches = _int_or_zero(master_last_solve.get("branches"))
    conflicts = _int_or_zero(master_last_solve.get("conflicts"))
    start_failure = _mapping(proof_summary.get("master_start_failure_attribution"))
    start_failure_summary = _mapping(blocker.get("start_failure_summary"))
    failure_counts = _mapping(
        start_failure.get("failure_reason_counts")
        or start_failure_summary.get("failure_reason_counts")
    )
    return {
        "candidate_key": str(blocker.get("candidate_key", "")),
        "subtype": str(blocker.get("blocker_subtype", "")),
        "branches": int(branches),
        "conflicts": int(conflicts),
        "deterministic_time": float(master_last_solve.get("deterministic_time", 0.0) or 0.0),
        "conflictful_unknown": bool(branches > 0 or conflicts > 0),
        "failure_reason_counts": dict(failure_counts),
    }


def _int_or_zero(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _check_passed(summary: Optional[Mapping[str, Any]], check_id: str) -> bool:
    if not isinstance(summary, Mapping):
        return False
    for check in list(summary.get("checks", [])):
        if not isinstance(check, Mapping):
            continue
        if check.get("check_id") == check_id:
            return str(check.get("status")) == "pass"
    return False


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {
        "check_id": str(check_id),
        "status": str(status),
        "detail": str(detail),
    }


def _validation_rule(rule_id: str, passed: bool, detail: str) -> Dict[str, Any]:
    return {
        "rule_id": str(rule_id),
        "passed": bool(passed),
        "detail": str(detail),
    }


def _normalize_path_text(value: str) -> str:
    return str(value).replace("\\", "/").strip().lower()


def _free_gb_for_path(path: Path) -> float:
    anchor = Path(path)
    while not anchor.exists() and anchor.parent != anchor:
        anchor = anchor.parent
    usage = shutil.disk_usage(str(anchor))
    return float(usage.free / (1024**3))


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _drive_label(path: Path) -> str:
    return Path(path).drive or "unknown"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
