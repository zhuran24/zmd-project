from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

GROUP_PACKING_PROOF_PROMOTION_SOURCE = (
    "phase3b_group_packing_proof_promotion_blockers_v1"
)
DEFAULT_PROMOTION_SPEC_PATH = Path(
    ".artifacts/phase3b_group_packing_precheck_promotion_spec/promotion_spec.json"
)
DEFAULT_PRE_MASTER_PROFILE_PATH = Path(
    ".artifacts/phase3b_pre_master_precheck_profiler/pre_master_profile_69x19_boundary128_rect64_cap32.json"
)
DEFAULT_RUNTIME_DIAGNOSTIC_PATH = Path(
    ".artifacts/phase3b_runtime_group_packing/runtime_group_packing_69x19.json"
)
DEFAULT_SOUNDNESS_GATE_PATH = Path(
    ".artifacts/phase3b_group_packing_soundness/soundness_gate.json"
)
DEFAULT_GHOST_ONLY_VERIFIER_PATH = Path(
    ".artifacts/phase3b_group_packing_ghost_only/ghost_only_group_packing_69x19_samples51.json"
)
DEFAULT_B5A_SUMMARY_PATH = Path(".artifacts/phase3b_b5_anchor_sprint/operator_summary.json")


def build_phase3b_group_packing_proof_promotion_blockers(
    project_root: Path,
    *,
    promotion_spec_path: Optional[Path] = None,
    runtime_diagnostic_path: Optional[Path] = None,
    soundness_gate_path: Optional[Path] = None,
    ghost_only_verifier_path: Optional[Path] = None,
    pre_master_profile_path: Optional[Path] = None,
    b5a_summary_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    promotion_path = _resolve_path(
        project_root,
        promotion_spec_path if promotion_spec_path is not None else DEFAULT_PROMOTION_SPEC_PATH,
    )
    runtime_path = _resolve_path(
        project_root,
        runtime_diagnostic_path
        if runtime_diagnostic_path is not None
        else DEFAULT_RUNTIME_DIAGNOSTIC_PATH,
    )
    profile_path = _resolve_path(
        project_root,
        pre_master_profile_path
        if pre_master_profile_path is not None
        else DEFAULT_PRE_MASTER_PROFILE_PATH,
    )
    soundness_path = _resolve_path(
        project_root,
        soundness_gate_path
        if soundness_gate_path is not None
        else DEFAULT_SOUNDNESS_GATE_PATH,
    )
    ghost_only_path = _resolve_path(
        project_root,
        ghost_only_verifier_path
        if ghost_only_verifier_path is not None
        else DEFAULT_GHOST_ONLY_VERIFIER_PATH,
    )
    b5a_path = _resolve_path(
        project_root,
        b5a_summary_path if b5a_summary_path is not None else DEFAULT_B5A_SUMMARY_PATH,
    )

    promotion_spec, promotion_error = _load_json_mapping(promotion_path)
    runtime_diagnostic, runtime_error = _load_json_mapping(runtime_path)
    soundness_gate, soundness_error = _load_json_mapping(soundness_path)
    ghost_only_verifier, ghost_only_error = _load_json_mapping(ghost_only_path)
    pre_master_profile, profile_error = _load_json_mapping(profile_path)
    b5a_summary, b5a_error = _load_json_mapping(b5a_path)

    candidate = _candidate_summary(
        promotion_spec,
        runtime_diagnostic,
        pre_master_profile,
        b5a_summary,
    )
    evidence = {
        "promotion_spec": _promotion_spec_evidence(promotion_spec, promotion_error),
        "runtime_group_packing": _runtime_group_packing_evidence(
            runtime_diagnostic,
            runtime_error,
        ),
        "soundness_gate": _soundness_gate_evidence(soundness_gate, soundness_error),
        "ghost_only_verifier": _ghost_only_verifier_evidence(
            ghost_only_verifier,
            ghost_only_error,
        ),
        "pre_master_profile": _pre_master_profile_evidence(
            pre_master_profile,
            profile_error,
        ),
        "b5a": _b5a_evidence(b5a_summary, b5a_error),
    }
    blockers = _promotion_blockers(evidence)
    checks = _checks(evidence, blockers)
    diagnostic_evidence_ready = _diagnostic_evidence_ready(evidence)
    proof_promotion_ready = bool(not blockers)
    return {
        "metadata": {
            "source": GROUP_PACKING_PROOF_PROMOTION_SOURCE,
            "generated_at": now_iso(),
        },
        "paths": {
            "project_root": str(project_root),
            "promotion_spec": _display_path(project_root, promotion_path),
            "runtime_group_packing": _display_path(project_root, runtime_path),
            "soundness_gate": _display_path(project_root, soundness_path),
            "ghost_only_verifier": _display_path(project_root, ghost_only_path),
            "pre_master_profile": _display_path(project_root, profile_path),
            "b5a_operator_summary": _display_path(project_root, b5a_path),
        },
        "candidate": candidate,
        "promotion_readiness": {
            "diagnostic_evidence_ready": bool(diagnostic_evidence_ready),
            "proof_promotion_ready": bool(proof_promotion_ready),
            "blocked_by": blockers,
            "recommendation": _recommendation(
                diagnostic_evidence_ready=diagnostic_evidence_ready,
                blockers=blockers,
            ),
        },
        "evidence": evidence,
        "checks": checks,
    }


def render_phase3b_group_packing_proof_promotion_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    readiness = _mapping(report.get("promotion_readiness"))
    evidence = _mapping(report.get("evidence"))
    lines = [
        "# Phase 3B Group-Packing Proof Promotion Blockers",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Diagnostic evidence ready: {bool(readiness.get('diagnostic_evidence_ready', False))}",
        f"- Proof promotion ready: {bool(readiness.get('proof_promotion_ready', False))}",
        f"- Recommendation: {readiness.get('recommendation')}",
        "",
        "## Blockers",
        "",
    ]
    blockers = [str(item) for item in list(readiness.get("blocked_by", []))]
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Evidence",
            "",
            "| Source | Present | Key status | Samples | Blockers |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for source_id in [
        "promotion_spec",
        "runtime_group_packing",
        "soundness_gate",
        "ghost_only_verifier",
        "pre_master_profile",
        "b5a",
    ]:
        entry = _mapping(evidence.get(source_id))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(source_id),
                    _markdown_cell(entry.get("present")),
                    _markdown_cell(_evidence_status_text(source_id, entry)),
                    _markdown_cell(_evidence_sample_text(source_id, entry)),
                    _markdown_cell(entry.get("blocker_count", "")),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in list(report.get("checks", [])):
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


def render_phase3b_group_packing_proof_promotion_text(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    readiness = _mapping(report.get("promotion_readiness"))
    evidence = _mapping(report.get("evidence"))
    lines = [
        "Phase 3B group-packing proof promotion blockers",
        f"candidate={candidate.get('key')}",
        f"diagnostic_evidence_ready={bool(readiness.get('diagnostic_evidence_ready', False))}",
        f"proof_promotion_ready={bool(readiness.get('proof_promotion_ready', False))}",
        f"blocked_by={','.join(str(item) for item in list(readiness.get('blocked_by', [])))}",
        f"recommendation={readiness.get('recommendation')}",
    ]
    for source_id in [
        "promotion_spec",
        "runtime_group_packing",
        "soundness_gate",
        "ghost_only_verifier",
        "pre_master_profile",
        "b5a",
    ]:
        entry = _mapping(evidence.get(source_id))
        lines.append(
            "evidence "
            f"source={source_id} "
            f"present={bool(entry.get('present', False))} "
            f"status={_evidence_status_text(source_id, entry)} "
            f"samples={_evidence_sample_text(source_id, entry)} "
            f"blockers={entry.get('blocker_count', '')}"
        )
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check "
                f"id={check.get('check_id')} "
                f"status={check.get('status')} "
                f"detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _promotion_spec_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    status = _mapping(payload.get("promotion_status"))
    evidence = _mapping(payload.get("evidence_summary"))
    candidate = _mapping(payload.get("candidate"))
    return {
        "present": True,
        "load_error": load_error,
        "candidate_key": candidate.get("key"),
        "design_gate_passed": bool(status.get("design_gate_passed", False)),
        "spec_ready_for_runtime_slice": bool(
            status.get("spec_ready_for_runtime_slice", False)
        ),
        "runtime_promotion_ready": bool(status.get("runtime_promotion_ready", False)),
        "runtime_promotion_guarded": bool(
            status.get("runtime_promotion_guarded", False)
        ),
        "sample_count": int(evidence.get("sample_count", 0)),
        "infeasible_count": int(evidence.get("infeasible_count", 0)),
        "feasible_count": int(evidence.get("feasible_count", 0)),
        "unknown_count": int(evidence.get("unknown_count", 0)),
        "skipped_count": int(evidence.get("skipped_count", 0)),
        "blocker_count": int(evidence.get("blocker_count", 0)),
    }


def _runtime_group_packing_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    status = _mapping(payload.get("status"))
    diagnostics = _mapping(payload.get("diagnostics"))
    probe = _mapping(diagnostics.get("group_packing_probe"))
    blockers = _mapping(diagnostics.get("group_packing_blockers"))
    input_evidence = _mapping(payload.get("input_evidence"))
    return {
        "present": True,
        "load_error": load_error,
        "evaluated": bool(status.get("evaluated", False)),
        "outcome": status.get("outcome"),
        "campaign_state_unchanged": bool(
            payload.get("campaign_state_unchanged", False)
        ),
        "failed_anchor_count": int(input_evidence.get("failed_anchor_count", 0)),
        "failed_anchor_sample_count": int(
            input_evidence.get("failed_anchor_sample_count", 0)
        ),
        "sample_count": int(probe.get("sample_count", 0)),
        "infeasible_count": int(probe.get("infeasible_count", 0)),
        "feasible_count": int(probe.get("feasible_count", 0)),
        "unknown_count": int(probe.get("unknown_count", 0)),
        "skipped_count": int(probe.get("skipped_count", 0)),
        "blocker_count": int(blockers.get("blocker_count", 0)),
        "precheck_design_candidate": bool(
            blockers.get("precheck_design_candidate", False)
        ),
    }


def _pre_master_profile_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    status = _mapping(payload.get("status"))
    stages = _mapping(payload.get("stages"))
    boundary = _mapping(stages.get("boundary_port_precheck"))
    mandatory = _mapping(stages.get("mandatory_rectangle_precheck"))
    boundary_summary = _mapping(boundary.get("summary"))
    return {
        "present": True,
        "load_error": load_error,
        "completed": bool(status.get("completed", False)),
        "outcome": status.get("outcome"),
        "boundary_supported": bool(boundary_summary.get("supported", False)),
        "boundary_considered_anchor_count": int(
            boundary_summary.get("considered_anchor_count", 0)
        ),
        "boundary_screen_pass_anchor_count": int(
            boundary_summary.get("screen_pass_anchor_count", 0)
        ),
        "mandatory_status": mandatory.get("status"),
        "mandatory_skip_reason": mandatory.get("skip_reason"),
        "mandatory_anchor_count": int(mandatory.get("anchor_count", 0)),
        "pre_master_anchor_cap": int(mandatory.get("pre_master_anchor_cap", 0)),
    }


def _soundness_gate_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    soundness = _mapping(payload.get("soundness"))
    return {
        "present": True,
        "load_error": load_error,
        "all_samples_infeasible": bool(
            soundness.get("all_samples_infeasible", False)
        ),
        "terminal_elimination_sound": bool(
            soundness.get("terminal_elimination_sound", False)
        ),
        "sample_count": int(soundness.get("sample_count", 0)),
        "terminal_safe_sample_count": int(
            soundness.get("terminal_safe_sample_count", 0)
        ),
        "prefix_conditioned_sample_count": int(
            soundness.get("prefix_conditioned_sample_count", 0)
        ),
        "blocked_by": [
            str(item) for item in list(soundness.get("blocked_by", []))
        ],
        "blocker_count": len(list(soundness.get("blocked_by", []))),
    }


def _ghost_only_verifier_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    status = _mapping(payload.get("status"))
    verifier = _mapping(payload.get("ghost_only_verifier"))
    return {
        "present": True,
        "load_error": load_error,
        "evaluated": bool(status.get("evaluated", False)),
        "outcome": status.get("outcome"),
        "campaign_state_unchanged": bool(
            payload.get("campaign_state_unchanged", False)
        ),
        "sample_count": int(verifier.get("sample_count", 0)),
        "feasible_count": int(verifier.get("feasible_count", 0)),
        "infeasible_count": int(verifier.get("infeasible_count", 0)),
        "unknown_count": int(verifier.get("unknown_count", 0)),
        "skipped_count": int(verifier.get("skipped_count", 0)),
        "blocker_count": int(verifier.get("feasible_count", 0)),
    }


def _b5a_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    status = _mapping(payload.get("status"))
    campaign = _mapping(payload.get("campaign"))
    runtime_group_packing = _mapping(payload.get("runtime_group_packing"))
    current_candidate_keys = [
        str(key)
        for key in list(runtime_group_packing.get("current_candidate_keys", []))
    ]
    relevant_count_raw = runtime_group_packing.get("relevant_diagnostic_count")
    relevant_count = (
        int(relevant_count_raw)
        if relevant_count_raw is not None
        else int(runtime_group_packing.get("diagnostic_count", 0))
    )
    pose_order_validation = _mapping(payload.get("pose_order_validation"))
    return {
        "present": True,
        "load_error": load_error,
        "anchor_found": bool(status.get("anchor_found", False)),
        "outcome": status.get("outcome"),
        "campaign_final_status": campaign.get("final_status"),
        "last_stop_reason": _mapping(campaign.get("last_stop_reason")).get("reason"),
        "runtime_group_packing_diagnostic_count": int(
            runtime_group_packing.get("diagnostic_count", 0)
        ),
        "runtime_group_packing_relevant_diagnostic_count": int(relevant_count),
        "current_candidate_keys": current_candidate_keys,
        "pose_order_validation_rejected_count": int(
            pose_order_validation.get("rejected_count", 0)
        ),
        "pose_order_validation_reason_counts": {
            str(key): int(value)
            for key, value in dict(
                _mapping(pose_order_validation.get("reason_counts"))
            ).items()
        },
        "pose_order_validation_status_counts": {
            str(key): int(value)
            for key, value in dict(
                _mapping(pose_order_validation.get("status_counts"))
            ).items()
        },
    }


def _promotion_blockers(evidence: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    promotion = _mapping(evidence.get("promotion_spec"))
    runtime = _mapping(evidence.get("runtime_group_packing"))
    soundness = _mapping(evidence.get("soundness_gate"))
    ghost_only = _mapping(evidence.get("ghost_only_verifier"))
    profile = _mapping(evidence.get("pre_master_profile"))
    b5a = _mapping(evidence.get("b5a"))
    if not bool(promotion.get("present", False)):
        blockers.append("promotion_spec_missing")
    elif not bool(promotion.get("spec_ready_for_runtime_slice", False)):
        blockers.append("promotion_spec_not_ready")
    if not bool(runtime.get("present", False)):
        blockers.append("runtime_group_packing_missing")
    elif not bool(runtime.get("evaluated", False)):
        blockers.append("runtime_group_packing_not_evaluated")
    elif runtime.get("outcome") != "diagnostic_group_packing_infeasible":
        blockers.append("runtime_group_packing_not_uniformly_infeasible")
    if bool(runtime.get("present", False)) and not bool(
        runtime.get("campaign_state_unchanged", False)
    ):
        blockers.append("runtime_diagnostic_mutated_campaign_state")
    if not bool(soundness.get("present", False)):
        blockers.append("soundness_gate_missing")
    elif not bool(soundness.get("terminal_elimination_sound", False)):
        blockers.extend(list(soundness.get("blocked_by", [])))
    if not bool(ghost_only.get("present", False)):
        blockers.append("ghost_only_verifier_missing")
    elif not bool(ghost_only.get("evaluated", False)):
        blockers.append("ghost_only_verifier_not_evaluated")
    elif not bool(ghost_only.get("campaign_state_unchanged", False)):
        blockers.append("ghost_only_verifier_mutated_campaign_state")
    elif int(ghost_only.get("feasible_count", 0)) > 0:
        blockers.append("ghost_only_feasible_counterexample_found")
    runtime_samples = int(runtime.get("sample_count", 0))
    full_samples = int(promotion.get("sample_count", 0))
    if runtime_samples <= 0 or (full_samples > 0 and runtime_samples < full_samples):
        blockers.append("runtime_sample_coverage_below_full_diagnostic")
    if not bool(profile.get("present", False)):
        blockers.append("pre_master_profile_missing")
    elif not bool(profile.get("completed", False)):
        blockers.append("pre_master_profile_incomplete")
    if not bool(b5a.get("present", False)):
        blockers.append("b5a_summary_missing")
    elif not bool(b5a.get("runtime_group_packing_relevant_diagnostic_count", 0)):
        blockers.append("b5a_summary_missing_runtime_group_packing")
    promotion_candidate_key = str(promotion.get("candidate_key", ""))
    b5a_candidate_keys = {
        str(key) for key in list(b5a.get("current_candidate_keys", [])) if str(key)
    }
    if (
        promotion_candidate_key
        and b5a_candidate_keys
        and promotion_candidate_key not in b5a_candidate_keys
    ):
        blockers.append("b5a_current_candidate_mismatch_for_promotion")
    if int(b5a.get("pose_order_validation_rejected_count", 0)) > 0:
        blockers.append("coordinate_pose_order_validation_infeasible")
    if bool(b5a.get("anchor_found", False)):
        blockers.append("unexpected_anchor_found_for_promotion_report")
    if bool(soundness.get("terminal_elimination_sound", False)):
        blockers.append("proof_semantics_not_implemented")
    blockers.append("terminal_proof_integration_missing")
    blockers.append("post_promotion_b5a_rerun_missing")
    return _dedupe(blockers)


def _checks(evidence: Mapping[str, Any], blockers: list[str]) -> list[Dict[str, str]]:
    promotion = _mapping(evidence.get("promotion_spec"))
    runtime = _mapping(evidence.get("runtime_group_packing"))
    soundness = _mapping(evidence.get("soundness_gate"))
    ghost_only = _mapping(evidence.get("ghost_only_verifier"))
    profile = _mapping(evidence.get("pre_master_profile"))
    b5a = _mapping(evidence.get("b5a"))
    runtime_samples = int(runtime.get("sample_count", 0))
    full_samples = int(promotion.get("sample_count", 0))
    return [
        _check(
            "promotion_spec_ready",
            "pass"
            if bool(promotion.get("present", False))
            and bool(promotion.get("spec_ready_for_runtime_slice", False))
            else "fail",
            f"spec_ready={bool(promotion.get('spec_ready_for_runtime_slice', False))}",
        ),
        _check(
            "runtime_group_packing_infeasible",
            "pass"
            if bool(runtime.get("present", False))
            and runtime.get("outcome") == "diagnostic_group_packing_infeasible"
            else "fail",
            f"outcome={runtime.get('outcome')}",
        ),
        _check(
            "runtime_campaign_state_unchanged",
            "pass" if bool(runtime.get("campaign_state_unchanged", False)) else "fail",
            f"campaign_state_unchanged={bool(runtime.get('campaign_state_unchanged', False))}",
        ),
        _check(
            "runtime_sample_coverage_matches_full_diagnostic",
            "pass" if full_samples > 0 and runtime_samples >= full_samples else "fail",
            f"runtime_samples={runtime_samples}; full_diagnostic_samples={full_samples}",
        ),
        _check(
            "soundness_gate_terminal_safe",
            "pass"
            if bool(soundness.get("present", False))
            and bool(soundness.get("terminal_elimination_sound", False))
            else "fail",
            f"terminal_elimination_sound={bool(soundness.get('terminal_elimination_sound', False))}; blocked_by={list(soundness.get('blocked_by', []))}",
        ),
        _check(
            "ghost_only_verifier_no_counterexample",
            "pass"
            if bool(ghost_only.get("present", False))
            and bool(ghost_only.get("evaluated", False))
            and int(ghost_only.get("feasible_count", 0)) == 0
            and bool(ghost_only.get("campaign_state_unchanged", False))
            else "fail",
            f"outcome={ghost_only.get('outcome')}; feasible_count={int(ghost_only.get('feasible_count', 0))}",
        ),
        _check(
            "pre_master_profile_completed",
            "pass"
            if bool(profile.get("present", False)) and bool(profile.get("completed", False))
            else "fail",
            f"outcome={profile.get('outcome')}",
        ),
        _check(
            "b5a_summary_links_runtime_group_packing",
            "pass"
            if bool(b5a.get("present", False))
            and int(b5a.get("runtime_group_packing_relevant_diagnostic_count", 0)) > 0
            else "fail",
            "diagnostic_count="
            f"{int(b5a.get('runtime_group_packing_diagnostic_count', 0))}; "
            "relevant_diagnostic_count="
            f"{int(b5a.get('runtime_group_packing_relevant_diagnostic_count', 0))}",
        ),
        _check(
            "b5a_current_candidate_matches_promotion_candidate",
            "pass"
            if not str(promotion.get("candidate_key", ""))
            or not list(b5a.get("current_candidate_keys", []))
            or str(promotion.get("candidate_key", ""))
            in {str(key) for key in list(b5a.get("current_candidate_keys", []))}
            else "fail",
            f"promotion_candidate={promotion.get('candidate_key')}; "
            f"b5a_current_candidates={list(b5a.get('current_candidate_keys', []))}",
        ),
        _check(
            "coordinate_pose_order_validation_clear",
            "pass"
            if int(b5a.get("pose_order_validation_rejected_count", 0)) == 0
            else "fail",
            "rejected_count="
            f"{int(b5a.get('pose_order_validation_rejected_count', 0))}; "
            f"reasons={dict(b5a.get('pose_order_validation_reason_counts', {}))}",
        ),
        _check(
            "terminal_proof_integration",
            "fail" if "terminal_proof_integration_missing" in blockers else "pass",
            "group-packing proof is not integrated into terminal campaign semantics",
        ),
        _check(
            "proof_semantics_implemented",
            _proof_semantics_check_status(soundness, blockers),
            _proof_semantics_check_detail(soundness, blockers),
        ),
    ]


def _proof_semantics_check_status(
    soundness: Mapping[str, Any],
    blockers: list[str],
) -> str:
    if not bool(soundness.get("present", False)) or not bool(
        soundness.get("terminal_elimination_sound", False)
    ):
        return "skipped"
    if "proof_semantics_not_implemented" in blockers:
        return "fail"
    return "pass"


def _proof_semantics_check_detail(
    soundness: Mapping[str, Any],
    blockers: list[str],
) -> str:
    if not bool(soundness.get("present", False)):
        return "soundness gate missing; proof semantics not evaluated"
    if not bool(soundness.get("terminal_elimination_sound", False)):
        return "blocked before proof semantics by soundness gate"
    if "proof_semantics_not_implemented" in blockers:
        return "terminal-safe evidence exists, but terminal proof semantics are not implemented"
    return "terminal proof semantics implemented"


def _diagnostic_evidence_ready(evidence: Mapping[str, Any]) -> bool:
    promotion = _mapping(evidence.get("promotion_spec"))
    runtime = _mapping(evidence.get("runtime_group_packing"))
    soundness = _mapping(evidence.get("soundness_gate"))
    ghost_only = _mapping(evidence.get("ghost_only_verifier"))
    profile = _mapping(evidence.get("pre_master_profile"))
    b5a = _mapping(evidence.get("b5a"))
    return bool(
        promotion.get("spec_ready_for_runtime_slice", False)
        and runtime.get("outcome") == "diagnostic_group_packing_infeasible"
        and bool(runtime.get("campaign_state_unchanged", False))
        and bool(soundness.get("present", False))
        and bool(ghost_only.get("present", False))
        and bool(ghost_only.get("evaluated", False))
        and bool(profile.get("completed", False))
        and int(b5a.get("runtime_group_packing_diagnostic_count", 0)) > 0
    )


def _recommendation(
    *,
    diagnostic_evidence_ready: bool,
    blockers: list[str],
) -> str:
    if not diagnostic_evidence_ready:
        return "Do not promote: diagnostic evidence is incomplete; repair missing inputs first."
    return (
        "Diagnostic evidence is strong, but proof promotion remains blocked by "
        + ", ".join(blockers)
        + "."
    )


def _candidate_summary(*payloads: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    for payload in payloads:
        if not isinstance(payload, Mapping):
            continue
        candidate = payload.get("candidate")
        if isinstance(candidate, Mapping) and candidate.get("key"):
            return dict(candidate)
    return {}


def _evidence_status_text(source_id: str, entry: Mapping[str, Any]) -> str:
    if source_id == "promotion_spec":
        return f"spec_ready={bool(entry.get('spec_ready_for_runtime_slice', False))}"
    if source_id == "runtime_group_packing":
        return str(entry.get("outcome"))
    if source_id == "soundness_gate":
        return f"terminal_sound={bool(entry.get('terminal_elimination_sound', False))}"
    if source_id == "ghost_only_verifier":
        return str(entry.get("outcome"))
    if source_id == "pre_master_profile":
        return str(entry.get("outcome"))
    if source_id == "b5a":
        return f"anchor_found={bool(entry.get('anchor_found', False))}; final={entry.get('campaign_final_status')}"
    return ""


def _evidence_sample_text(source_id: str, entry: Mapping[str, Any]) -> str:
    if source_id == "runtime_group_packing":
        return (
            f"{entry.get('sample_count', 0)}/"
            f"{entry.get('failed_anchor_count', 0)} runtime"
        )
    if source_id == "soundness_gate":
        return (
            f"safe={entry.get('terminal_safe_sample_count', 0)}/"
            f"{entry.get('sample_count', 0)}; "
            f"prefix={entry.get('prefix_conditioned_sample_count', 0)}"
        )
    if source_id == "ghost_only_verifier":
        return (
            f"feasible={entry.get('feasible_count', 0)}/"
            f"{entry.get('sample_count', 0)}; "
            f"infeasible={entry.get('infeasible_count', 0)}"
        )
    if source_id == "promotion_spec":
        return f"{entry.get('sample_count', 0)} full"
    if source_id == "pre_master_profile":
        return (
            f"boundary_pass={entry.get('boundary_screen_pass_anchor_count', 0)}; "
            f"cap={entry.get('pre_master_anchor_cap', 0)}"
        )
    return ""


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


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
