from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso
from src.search.phase3b_family_bound_formulation_probe import (
    DEFAULT_DIRECT_BOUND_SLICE_PATH,
    DEFAULT_FAMILY_BOUND_SEMANTIC_AUDIT_PATH,
)

ANCHOR_SPECIALIZED_BOUND_INJECTION_SOURCE = (
    "phase3b_anchor_specialized_bound_injection_v1"
)
FORCED_ANCHOR_MODEL_SLICE_SOURCE = "phase3b_forced_anchor_model_slice_diagnostic_v1"
FAMILY_BOUND_SEMANTIC_AUDIT_SOURCE = "phase3b_family_bound_semantic_audit_v1"
FAMILY_BOUND_FORMULATION_PROBE_SOURCE = "phase3b_family_bound_formulation_probe_v1"
POWER_PROTOCOL_INTERACTION_SOURCE = "phase3b_power_protocol_interaction_diagnostic_v1"

DEFAULT_FAMILY_BOUND_FORMULATION_PROBE_PATH = Path(
    ".artifacts/phase3b_family_bound_formulation_probe/family_bound_formulation_probe.json"
)
DEFAULT_POWER_PROTOCOL_INTERACTION_PATH = Path(
    ".artifacts/phase3b_power_protocol_interaction/power_protocol_interaction.json"
)

TARGET_DIRECT_FORMULATION_CLASSIFICATION = (
    "target_direct_terminal_enforced_unknown_all_family_direct_infeasible"
)
TARGET_ONLY_POWER_PROTOCOL_HYPOTHESIS = (
    "target_family_only_direct_bound_injection_candidate"
)


def build_phase3b_anchor_specialized_bound_injection_spec(
    project_root: Path,
    *,
    direct_bound_slice_path: Optional[Path] = None,
    family_bound_semantic_audit_path: Optional[Path] = None,
    family_bound_formulation_probe_path: Optional[Path] = None,
    power_protocol_interaction_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    direct_path = _resolve_path(
        project_root,
        direct_bound_slice_path
        if direct_bound_slice_path is not None
        else DEFAULT_DIRECT_BOUND_SLICE_PATH,
    )
    semantic_path = _resolve_path(
        project_root,
        family_bound_semantic_audit_path
        if family_bound_semantic_audit_path is not None
        else DEFAULT_FAMILY_BOUND_SEMANTIC_AUDIT_PATH,
    )
    formulation_path = _resolve_path(
        project_root,
        family_bound_formulation_probe_path
        if family_bound_formulation_probe_path is not None
        else DEFAULT_FAMILY_BOUND_FORMULATION_PROBE_PATH,
    )
    power_protocol_path = _resolve_path(
        project_root,
        power_protocol_interaction_path
        if power_protocol_interaction_path is not None
        else DEFAULT_POWER_PROTOCOL_INTERACTION_PATH,
    )

    direct_payload, direct_error = _load_json_mapping(direct_path)
    semantic_payload, semantic_error = _load_json_mapping(semantic_path)
    formulation_payload, formulation_error = _load_json_mapping(formulation_path)
    power_protocol_payload, power_protocol_error = _load_json_mapping(power_protocol_path)

    direct = _direct_bound_slice_evidence(direct_payload, direct_error)
    semantic = _semantic_audit_evidence(semantic_payload, semantic_error)
    formulation = _formulation_probe_evidence(formulation_payload, formulation_error)
    power_protocol = _power_protocol_evidence(
        power_protocol_payload,
        power_protocol_error,
    )
    checks = _checks(direct, semantic, formulation, power_protocol)
    gate = _gate(checks)
    injection_spec = _injection_spec(direct, semantic)
    return {
        "metadata": {
            "source": ANCHOR_SPECIALIZED_BOUND_INJECTION_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "guarded_injection_spec_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "direct_bound_slice": _display_path(project_root, direct_path),
            "family_bound_semantic_audit": _display_path(project_root, semantic_path),
            "family_bound_formulation_probe": _display_path(project_root, formulation_path),
            "power_protocol_interaction": _display_path(project_root, power_protocol_path),
        },
        "candidate": {
            "key": direct.get("candidate_key") or semantic.get("candidate_key"),
        },
        "direct_bound_slice": direct,
        "semantic_audit": semantic,
        "formulation_probe": formulation,
        "power_protocol_interaction": power_protocol,
        "injection_spec": injection_spec,
        "gate": gate,
        "checks": checks,
        "recommendation": _recommendation(gate),
    }


def render_phase3b_anchor_specialized_bound_injection_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    gate = _mapping(report.get("gate"))
    spec = _mapping(report.get("injection_spec"))
    target = _mapping(spec.get("target"))
    lines = [
        "# Phase 3B Anchor-Specialized Bound Injection",
        "",
        f"- Candidate: {candidate.get('key')}",
        "- Diagnostic semantics: guarded_injection_spec_not_proof_source",
        f"- Diagnostic spec ready: {gate.get('diagnostic_spec_ready')}",
        f"- Runtime promotion ready: {gate.get('runtime_promotion_ready')}",
        f"- Proof promotion ready: {gate.get('proof_promotion_ready')}",
        f"- Final long-run ready: {gate.get('final_long_run_ready')}",
        f"- Default enabled: {spec.get('default_enabled')}",
        f"- Scope: {spec.get('allowed_scope')}",
        f"- Target anchor: {target.get('anchor_idx')}",
        f"- Target family: {target.get('target_power_family')}",
        f"- U var index: {target.get('u_var_index')}",
        f"- Family count var index: {target.get('family_count_var_index')}",
        f"- Recommendation: {report.get('recommendation')}",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
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


def render_phase3b_anchor_specialized_bound_injection_text(
    report: Mapping[str, Any],
) -> str:
    gate = _mapping(report.get("gate"))
    spec = _mapping(report.get("injection_spec"))
    target = _mapping(spec.get("target"))
    lines = [
        "Phase 3B anchor-specialized bound injection",
        "diagnostic_semantics=guarded_injection_spec_not_proof_source",
        f"diagnostic_spec_ready={gate.get('diagnostic_spec_ready')}",
        f"runtime_promotion_ready={gate.get('runtime_promotion_ready')}",
        f"proof_promotion_ready={gate.get('proof_promotion_ready')}",
        f"final_long_run_ready={gate.get('final_long_run_ready')}",
        f"default_enabled={spec.get('default_enabled')}",
        f"allowed_scope={spec.get('allowed_scope')}",
        f"anchor_idx={target.get('anchor_idx')}",
        f"target_power_family={target.get('target_power_family')}",
        f"u_var_index={target.get('u_var_index')}",
        f"family_count_var_index={target.get('family_count_var_index')}",
        f"recommendation={report.get('recommendation')}",
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check "
                f"id={check.get('check_id')} "
                f"status={check.get('status')} "
                f"detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _direct_bound_slice_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    profile = _mapping(payload.get("profile"))
    matrix = _mapping(payload.get("slice_matrix"))
    entries = [
        entry for entry in list(matrix.get("entries", [])) if isinstance(entry, Mapping)
    ]
    base = _entry_by_variant(entries, "base")
    direct = _entry_by_variant(entries, "target_power_family_bound_direct_after_force")
    removed = _mapping(direct.get("removed_conditioned_power_family_bound_payload"))
    target_family = direct.get("relaxed_power_family") or profile.get("target_power_family")
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FORCED_ANCHOR_MODEL_SLICE_SOURCE,
        "candidate_key": candidate.get("key"),
        "campaign_state_unchanged": bool(payload.get("campaign_state_unchanged", False)),
        "target_power_family": target_family,
        "selected_anchor_indices": [
            int(value)
            for value in list(profile.get("selected_anchor_indices", []))
            if _int_or_none(value) is not None
        ],
        "base_status": base.get("status"),
        "base_branches": base.get("branches"),
        "base_conflicts": base.get("conflicts"),
        "direct_variant_present": bool(direct),
        "direct_status": direct.get("status"),
        "anchor_idx": _int_or_none(direct.get("anchor_idx")),
        "u_var_index": _int_or_none(direct.get("u_var_index")),
        "family_count_var_index": _int_or_none(
            direct.get("relaxed_power_family_count_var_index")
        ),
        "replacement_bound_mode": direct.get("replacement_bound_mode"),
        "replacement_conditioned_power_family_bound": _int_or_none(
            direct.get("replacement_conditioned_power_family_bound")
        ),
        "direct_solution_family_count": _int_or_none(
            direct.get("relaxed_power_family_count_value")
        ),
        "removed_constraint_count": _int_or_none(
            direct.get("relaxed_conditioned_power_family_bound_constraints_removed")
        ),
        "removed_payload_constraint_count": _int_or_none(
            removed.get("removed_constraint_count")
        ),
        "removed_constraint_indices": [
            int(value)
            for value in list(removed.get("removed_constraint_indices", []))
            if _int_or_none(value) is not None
        ],
        "implied_conditioned_upper_bound": _int_or_none(
            removed.get("implied_conditioned_upper_bound")
        ),
        "implied_global_upper_bound": _int_or_none(
            removed.get("implied_global_upper_bound")
        ),
    }


def _semantic_audit_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    family = _mapping(payload.get("family_bound"))
    target = _mapping(payload.get("target_family_slice"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FAMILY_BOUND_SEMANTIC_AUDIT_SOURCE,
        "candidate_key": candidate.get("key") or family.get("candidate_key"),
        "classification": payload.get("classification"),
        "anchor_idx": _int_or_none(family.get("anchor_idx")),
        "target_power_family": family.get("target_power_family")
        or target.get("relaxed_power_family"),
        "derived_conditioned_upper_bound": _int_or_none(
            family.get("derived_conditioned_upper_bound")
        ),
        "global_upper_bound": _int_or_none(family.get("global_upper_bound")),
        "bounds_consistent": bool(family.get("bounds_consistent", False)),
        "all_bounds_consistent": bool(family.get("all_bounds_consistent", False)),
        "target_status": target.get("target_status"),
        "relaxed_family_bound_violation": _int_or_none(
            target.get("relaxed_family_bound_violation")
        ),
        "target_solution_family_count": _int_or_none(
            target.get("relaxed_power_family_count_value")
        ),
    }


def _formulation_probe_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    comparison = _mapping(payload.get("comparison"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FAMILY_BOUND_FORMULATION_PROBE_SOURCE,
        "classification": payload.get("classification"),
        "base_status": comparison.get("base_status"),
        "direct_status": comparison.get("direct_status"),
        "enforced_status": comparison.get("enforced_status"),
        "all_family_status": comparison.get("all_family_status"),
        "all_family_replacement_count": _int_or_none(
            comparison.get("all_family_replacement_count")
        ),
        "direct_bound_value": _int_or_none(comparison.get("direct_bound_value")),
        "direct_count_value": _int_or_none(comparison.get("direct_count_value")),
    }


def _power_protocol_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    analysis = _mapping(payload.get("analysis"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == POWER_PROTOCOL_INTERACTION_SOURCE,
        "primary_hypothesis": analysis.get("primary_hypothesis"),
        "next_actions": [str(item) for item in list(analysis.get("next_actions", []))],
        "recommendation": payload.get("recommendation"),
    }


def _injection_spec(
    direct: Mapping[str, Any],
    semantic: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "name": "target_family_only_anchor_specialized_direct_bound_injection",
        "default_enabled": False,
        "diagnostic_only": True,
        "allowed_scope": "workspace_forced_anchor_clone_after_anchor_is_fixed",
        "forbidden_scopes": [
            "repo_main_campaign",
            "production_168h_long_run",
            "delivery_manifest_proof_source",
            "release_viewer_frontdoor_status",
        ],
        "target": {
            "candidate_key": direct.get("candidate_key") or semantic.get("candidate_key"),
            "anchor_idx": direct.get("anchor_idx") or semantic.get("anchor_idx"),
            "u_var_index": direct.get("u_var_index"),
            "target_power_family": direct.get("target_power_family")
            or semantic.get("target_power_family"),
            "family_count_var_index": direct.get("family_count_var_index"),
            "conditioned_upper_bound": direct.get(
                "replacement_conditioned_power_family_bound"
            )
            or semantic.get("derived_conditioned_upper_bound"),
            "global_upper_bound": direct.get("implied_global_upper_bound")
            or semantic.get("global_upper_bound"),
        },
        "preconditions": [
            "Build the unmodified exact coordinate master model first.",
            "Force the same ghost anchor with u_var == 1 before injecting the direct bound.",
            "Remove exactly the one reified conditioned family-bound row for the target family and forced anchor.",
            "Add the direct row count_var <= conditioned_upper_bound for that target family only.",
            "Do not apply this substitution to all families or to unforced anchors.",
        ],
        "equivalence_argument": (
            "Under the forced-anchor condition u_var == 1, the original row "
            "count_var <= conditioned_upper_bound + global_upper_bound * (1 - u_var) "
            "algebraically reduces to count_var <= conditioned_upper_bound. The "
            "spec is therefore proof-neutral only when every listed precondition "
            "is met; it is still diagnostic-only until a fresh workspace rerun "
            "and acceptance evidence exist."
        ),
        "proof_source_policy": (
            "This spec is not a proof source. Terminal proof remains campaign "
            "state, telemetry, final solution, blueprint, and delivery manifest."
        ),
    }


def _checks(
    direct: Mapping[str, Any],
    semantic: Mapping[str, Any],
    formulation: Mapping[str, Any],
    power_protocol: Mapping[str, Any],
) -> list[Dict[str, str]]:
    direct_bound = _int_or_none(direct.get("replacement_conditioned_power_family_bound"))
    implied_bound = _int_or_none(direct.get("implied_conditioned_upper_bound"))
    semantic_bound = _int_or_none(semantic.get("derived_conditioned_upper_bound"))
    direct_count = _int_or_none(direct.get("direct_solution_family_count"))
    return [
        _check(
            "direct_bound_slice_present",
            "pass" if bool(direct.get("present", False)) else "fail",
            "direct-bound slice loaded"
            if bool(direct.get("present", False))
            else str(direct.get("load_error")),
        ),
        _check(
            "direct_bound_slice_source_supported",
            "pass" if bool(direct.get("source_supported", False)) else "fail",
            f"source_supported={direct.get('source_supported')}",
        ),
        _check(
            "campaign_state_unchanged",
            "pass" if bool(direct.get("campaign_state_unchanged", False)) else "fail",
            f"campaign_state_unchanged={direct.get('campaign_state_unchanged')}",
        ),
        _check(
            "base_zero_branch_unknown_reproduced",
            "pass"
            if direct.get("base_status") == "UNKNOWN"
            and int(direct.get("base_branches") or 0) == 0
            and int(direct.get("base_conflicts") or 0) == 0
            else "fail",
            "base_status="
            f"{direct.get('base_status')} branches={direct.get('base_branches')} "
            f"conflicts={direct.get('base_conflicts')}",
        ),
        _check(
            "target_family_identified",
            "pass" if bool(direct.get("target_power_family")) else "fail",
            f"target_power_family={direct.get('target_power_family')}",
        ),
        _check(
            "forced_anchor_identified",
            "pass" if _int_or_none(direct.get("anchor_idx")) is not None else "fail",
            f"anchor_idx={direct.get('anchor_idx')}",
        ),
        _check(
            "force_var_identified",
            "pass" if _int_or_none(direct.get("u_var_index")) is not None else "fail",
            f"u_var_index={direct.get('u_var_index')}",
        ),
        _check(
            "family_count_var_identified",
            "pass"
            if _int_or_none(direct.get("family_count_var_index")) is not None
            else "fail",
            f"family_count_var_index={direct.get('family_count_var_index')}",
        ),
        _check(
            "direct_variant_terminal",
            "pass" if direct.get("direct_status") in {"OPTIMAL", "FEASIBLE"} else "fail",
            f"direct_status={direct.get('direct_status')}",
        ),
        _check(
            "exactly_one_conditioned_bound_removed",
            "pass"
            if int(direct.get("removed_constraint_count") or 0) == 1
            and int(direct.get("removed_payload_constraint_count") or 0) == 1
            else "fail",
            "removed="
            f"{direct.get('removed_constraint_count')} "
            f"payload_removed={direct.get('removed_payload_constraint_count')}",
        ),
        _check(
            "direct_bound_matches_removed_payload",
            "pass"
            if direct_bound is not None
            and implied_bound is not None
            and int(direct_bound) == int(implied_bound)
            else "fail",
            f"direct_bound={direct_bound} implied_bound={implied_bound}",
        ),
        _check(
            "direct_solution_respects_bound",
            "pass"
            if direct_count is not None
            and direct_bound is not None
            and int(direct_count) <= int(direct_bound)
            else "fail",
            f"direct_count={direct_count} direct_bound={direct_bound}",
        ),
        _check(
            "semantic_audit_present",
            "pass" if bool(semantic.get("present", False)) else "fail",
            "semantic audit loaded"
            if bool(semantic.get("present", False))
            else str(semantic.get("load_error")),
        ),
        _check(
            "semantic_bound_consistent",
            "pass"
            if bool(semantic.get("bounds_consistent", False))
            and bool(semantic.get("all_bounds_consistent", False))
            else "fail",
            "bounds_consistent="
            f"{semantic.get('bounds_consistent')} "
            f"all_bounds_consistent={semantic.get('all_bounds_consistent')}",
        ),
        _check(
            "semantic_same_anchor_and_family",
            "pass"
            if _same_optional_int(direct.get("anchor_idx"), semantic.get("anchor_idx"))
            and str(direct.get("target_power_family")) == str(semantic.get("target_power_family"))
            else "fail",
            "direct_anchor="
            f"{direct.get('anchor_idx')} semantic_anchor={semantic.get('anchor_idx')} "
            f"direct_family={direct.get('target_power_family')} "
            f"semantic_family={semantic.get('target_power_family')}",
        ),
        _check(
            "semantic_bound_matches_direct_bound",
            "pass"
            if direct_bound is not None
            and semantic_bound is not None
            and int(direct_bound) == int(semantic_bound)
            else "fail",
            f"direct_bound={direct_bound} semantic_bound={semantic_bound}",
        ),
        _check(
            "semantic_no_bound_violation",
            "pass"
            if _int_or_none(semantic.get("relaxed_family_bound_violation")) is not None
            and int(semantic.get("relaxed_family_bound_violation")) <= 0
            else "fail",
            f"violation={semantic.get('relaxed_family_bound_violation')}",
        ),
        _check(
            "formulation_probe_present",
            "pass" if bool(formulation.get("present", False)) else "fail",
            "formulation probe loaded"
            if bool(formulation.get("present", False))
            else str(formulation.get("load_error")),
        ),
        _check(
            "target_only_formulation_classified",
            "pass"
            if formulation.get("classification")
            == TARGET_DIRECT_FORMULATION_CLASSIFICATION
            else "fail",
            f"classification={formulation.get('classification')}",
        ),
        _check(
            "all_family_substitution_blocked",
            "pass"
            if formulation.get("all_family_status") == "INFEASIBLE"
            and int(formulation.get("all_family_replacement_count") or 0) > 1
            else "fail",
            "all_family_status="
            f"{formulation.get('all_family_status')} "
            f"replacement_count={formulation.get('all_family_replacement_count')}",
        ),
        _check(
            "power_protocol_target_only_hypothesis",
            "pass"
            if power_protocol.get("primary_hypothesis")
            == TARGET_ONLY_POWER_PROTOCOL_HYPOTHESIS
            else "fail",
            f"primary_hypothesis={power_protocol.get('primary_hypothesis')}",
        ),
        _check(
            "default_disabled",
            "pass",
            "injection spec is default_enabled=false and diagnostic_only=true",
        ),
        _check(
            "runtime_promotion_blocked",
            "pass",
            "runtime/proof/final-long-run promotion remains false",
        ),
    ]


def _gate(checks: list[Dict[str, str]]) -> Dict[str, Any]:
    failed = [
        str(check.get("check_id"))
        for check in checks
        if str(check.get("status")) != "pass"
    ]
    diagnostic_ready = not failed
    return {
        "diagnostic_spec_ready": bool(diagnostic_ready),
        "workspace_diagnostic_rerun_allowed": bool(diagnostic_ready),
        "runtime_promotion_ready": False,
        "proof_promotion_ready": False,
        "final_long_run_ready": False,
        "promotion_blocked_by": [
            "runtime_promotion_requires_fresh_b5a_evidence",
            "proof_promotion_requires_terminal_campaign_evidence",
            "final_long_run_requires_unblocked_preflight",
        ],
        "failed_checks": failed,
    }


def _recommendation(gate: Mapping[str, Any]) -> str:
    if bool(gate.get("diagnostic_spec_ready", False)):
        return (
            "The target-family-only anchor-specialized direct-bound injection spec "
            "is ready for a workspace-only diagnostic rerun. Keep runtime, proof, "
            "release, and final long-run promotion blocked until fresh B5A and "
            "production-acceptance evidence are produced from an accepted path."
        )
    failed = ", ".join(str(item) for item in list(gate.get("failed_checks", [])))
    return (
        "Anchor-specialized injection spec is not ready. Rebuild or repair the "
        f"failed evidence checks before rerunning B5A diagnostics: {failed}"
    )


def _load_json_mapping(path: Path) -> tuple[Optional[Mapping[str, Any]], Optional[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "missing"
    except Exception as exc:
        return None, str(exc)
    if not isinstance(payload, Mapping):
        return None, "json root is not an object"
    return payload, None


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


def _entry_by_variant(entries: list[Mapping[str, Any]], variant: str) -> Mapping[str, Any]:
    for entry in entries:
        if str(entry.get("variant")) == str(variant):
            return entry
    return {}


def _same_optional_int(left: Any, right: Any) -> bool:
    left_int = _int_or_none(left)
    right_int = _int_or_none(right)
    return left_int is not None and right_int is not None and int(left_int) == int(right_int)


def _int_or_none(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    normalized = str(status)
    if normalized not in {"pass", "fail", "skipped"}:
        raise ValueError(f"Unsupported check status: {status!r}")
    return {"check_id": str(check_id), "status": normalized, "detail": str(detail)}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
