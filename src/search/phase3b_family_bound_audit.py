from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import now_iso
from src.search.phase3b_forced_anchor_master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
    _build_exact_overlay,
    _candidate_ghost_rect,
    _check,
    _display_path,
    _load_json_mapping,
    _mapping,
    _resolve_path,
    _selected_anchor_indices,
)

FAMILY_BOUND_AUDIT_SOURCE = "phase3b_family_bound_audit_v1"
DEFAULT_TARGET_POWER_FAMILY = "family_009"


def build_phase3b_family_bound_audit(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    anchor_indices: Optional[Sequence[int]] = None,
    sample_limit: int = 1,
    target_power_family: str = DEFAULT_TARGET_POWER_FAMILY,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    candidate_key = str(candidate)
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path if campaign_state_path is not None else DEFAULT_CAMPAIGN_STATE_PATH,
    )
    state, state_error = _load_json_mapping(campaign_path)
    candidates = _mapping(state.get("candidates")) if state else {}
    record = _mapping(candidates.get(candidate_key))
    proof_summary = _mapping(record.get("proof_summary"))
    failure_attribution = _mapping(proof_summary.get("master_start_failure_attribution"))
    failed_anchor_samples = [
        entry
        for entry in list(failure_attribution.get("failed_anchor_samples", []))
        if isinstance(entry, Mapping)
    ]
    selected_anchor_indices = _selected_anchor_indices(
        failed_anchor_samples,
        sample_limit,
        explicit_anchor_indices=anchor_indices,
    )
    ghost_rect = _candidate_ghost_rect(candidate_key, record)
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Family bound audit has not run.",
    }
    audits: list[Dict[str, Any]] = []
    timing: Dict[str, float] = {}
    model_error: Optional[str] = None
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before family-bound audit.",
            }
        )
    elif not record:
        status.update(
            {
                "completed": True,
                "outcome": "candidate_missing",
                "recommendation": "Candidate is not present in campaign state; choose a recorded blocker candidate.",
            }
        )
    elif not selected_anchor_indices:
        status.update(
            {
                "completed": True,
                "outcome": "anchor_samples_missing",
                "recommendation": "No anchor sample selected for family-bound audit.",
            }
        )
    else:
        try:
            overlay_started = time.perf_counter()
            model, _base_proto = _build_exact_overlay(
                project_root,
                ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                master_search_profile=master_search_profile,
            )
            timing["overlay_build_seconds"] = float(time.perf_counter() - overlay_started)
            audits = [
                _audit_anchor_family(
                    model,
                    anchor_idx=int(anchor_idx),
                    target_power_family=str(target_power_family),
                )
                for anchor_idx in selected_anchor_indices
            ]
            status.update(_status_from_audits(audits))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Family bound audit failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    return {
        "metadata": {
            "source": FAMILY_BOUND_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "derivation_audit_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "campaign_state": _display_path(project_root, campaign_path),
        },
        "candidate": {
            "key": candidate_key,
            "ghost_rect": ghost_rect,
            "campaign_present": state is not None and state_error is None,
            "campaign_load_error": state_error,
            "candidate_present": bool(record),
            "campaign_status": record.get("status") if record else None,
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "sample_limit": int(sample_limit),
            "selected_anchor_indices": [int(idx) for idx in selected_anchor_indices],
            "target_power_family": str(target_power_family),
        },
        "status": status,
        "audits": audits,
        "summary": _summary(audits),
        "timing": timing,
        "model_error": model_error,
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            status=status,
            audits=audits,
            model_error=model_error,
        ),
    }


def render_phase3b_family_bound_audit_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    summary = _mapping(report.get("summary"))
    lines = [
        "# Phase 3B Family Bound Audit",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Evaluated: {bool(status.get('evaluated', False))}",
        f"- Outcome: {status.get('outcome')}",
        "- Diagnostic semantics: derivation_audit_not_proof_source",
        f"- Target family: {_mapping(report.get('profile')).get('target_power_family')}",
        f"- All bounds consistent: {summary.get('all_bounds_consistent')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "| Anchor | Family | Family Size | Blocked | Global UB | Derived UB | Domain UB | Proto UB | Constraint Count |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for audit in list(report.get("audits", [])):
        if not isinstance(audit, Mapping):
            continue
        derivation = _mapping(audit.get("derivation"))
        proto = _mapping(audit.get("proto_constraint"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(audit.get("anchor_idx")),
                    _markdown_cell(audit.get("target_power_family")),
                    _markdown_cell(derivation.get("family_size")),
                    _markdown_cell(derivation.get("blocked_family_pose_count")),
                    _markdown_cell(derivation.get("global_upper_bound")),
                    _markdown_cell(derivation.get("derived_conditioned_upper_bound")),
                    _markdown_cell(derivation.get("domain_conditioned_upper_bound")),
                    _markdown_cell(proto.get("implied_conditioned_upper_bound")),
                    _markdown_cell(proto.get("matching_constraint_count")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
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


def render_phase3b_family_bound_audit_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    summary = _mapping(report.get("summary"))
    lines = [
        "Phase 3B family bound audit",
        f"candidate={candidate.get('key')}",
        f"evaluated={bool(status.get('evaluated', False))}",
        f"outcome={status.get('outcome')}",
        "diagnostic_semantics=derivation_audit_not_proof_source",
        f"target_family={_mapping(report.get('profile')).get('target_power_family')}",
        f"all_bounds_consistent={summary.get('all_bounds_consistent')}",
        f"recommendation={status.get('recommendation')}",
    ]
    for audit in list(report.get("audits", [])):
        if not isinstance(audit, Mapping):
            continue
        derivation = _mapping(audit.get("derivation"))
        proto = _mapping(audit.get("proto_constraint"))
        lines.append(
            "audit "
            f"anchor={audit.get('anchor_idx')} "
            f"family={audit.get('target_power_family')} "
            f"family_size={derivation.get('family_size')} "
            f"blocked={derivation.get('blocked_family_pose_count')} "
            f"global_ub={derivation.get('global_upper_bound')} "
            f"derived_ub={derivation.get('derived_conditioned_upper_bound')} "
            f"domain_ub={derivation.get('domain_conditioned_upper_bound')} "
            f"proto_ub={proto.get('implied_conditioned_upper_bound')} "
            f"consistent={audit.get('bounds_consistent')}"
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


def _audit_anchor_family(
    model: Any,
    *,
    anchor_idx: int,
    target_power_family: str,
) -> Dict[str, Any]:
    target_power_family = str(target_power_family)
    domains = list(getattr(model, "_ghost_domains", []))
    if int(anchor_idx) >= len(domains):
        return {
            "anchor_idx": int(anchor_idx),
            "target_power_family": target_power_family,
            "present": False,
            "skip_reason": "anchor_not_in_model_ghost_domains",
            "bounds_consistent": False,
        }
    domain = dict(domains[int(anchor_idx)])
    blocked_counts = _blocked_family_counts(model, domain)
    family_sizes = _family_sizes(model)
    global_upper_bound = _family_global_upper_bound(model, target_power_family)
    family_size = int(family_sizes.get(target_power_family, 0))
    blocked_count = int(blocked_counts.get(target_power_family, 0))
    available_count = int(family_size - blocked_count)
    derived_bound = int(min(max(0, available_count), global_upper_bound))
    domain_bounds = _mapping(domain.get("conditioned_power_pole_family_upper_bounds"))
    domain_bound = domain_bounds.get(target_power_family)
    domain_bound_int = int(domain_bound) if domain_bound is not None else None
    proto_constraint = _proto_constraint_payload(
        model,
        anchor_idx=int(anchor_idx),
        target_power_family=target_power_family,
        global_upper_bound=int(global_upper_bound),
    )
    proto_bound = proto_constraint.get("implied_conditioned_upper_bound")
    bounds_consistent = (
        domain_bound_int == derived_bound
        and proto_bound == derived_bound
        and int(proto_constraint.get("matching_constraint_count", 0)) == 1
    )
    return {
        "anchor_idx": int(anchor_idx),
        "target_power_family": target_power_family,
        "present": True,
        "anchor": domain.get("anchor"),
        "cell_count": int(len(list(domain.get("cells", [])))),
        "derivation": {
            "family_size": int(family_size),
            "blocked_family_pose_count": int(blocked_count),
            "available_family_pose_count": int(available_count),
            "slot_pool_upper_bound": int(
                len(
                    getattr(getattr(model, "_coordinate_delegate", None), "residual_optional_slots", {}).get(
                        "power_pole",
                        [],
                    )
                )
            ),
            "global_upper_bound": int(global_upper_bound),
            "derived_conditioned_upper_bound": int(derived_bound),
            "domain_conditioned_upper_bound": domain_bound_int,
            "all_domain_conditioned_bounds_count": int(len(domain_bounds)),
        },
        "family": {
            "coefficients": dict(
                _mapping(
                    getattr(
                        getattr(model, "_coordinate_delegate", None),
                        "_power_pole_family_coefficients",
                        {},
                    ).get(target_power_family, {})
                )
            ),
        },
        "proto_constraint": proto_constraint,
        "bounds_consistent": bool(bounds_consistent),
        "finding": (
            "target_family_bound_derivation_consistent"
            if bounds_consistent
            else "target_family_bound_derivation_mismatch"
        ),
    }


def _blocked_family_counts(model: Any, domain: Mapping[str, Any]) -> Dict[str, int]:
    delegate = getattr(model, "_coordinate_delegate", None)
    family_id_by_pose = dict(getattr(delegate, "_power_pole_family_id_by_pose_idx", {}) or {})
    family_name_by_int = dict(getattr(delegate, "_power_pole_family_name_by_int", {}) or {})
    pole_cells_by_pose = {
        int(pose_idx): frozenset((int(cell[0]), int(cell[1])) for cell in cells)
        for pose_idx, cells in _mapping(
            getattr(model, "_pose_cells_by_template_pose", {})
        ).get("power_pole", {}).items()
    }
    blocked_cells = {
        (int(cell[0]), int(cell[1])) for cell in list(domain.get("cells", []))
    }
    counts: Dict[str, int] = defaultdict(int)
    for pose_idx, cells in pole_cells_by_pose.items():
        if blocked_cells.isdisjoint(cells):
            continue
        family_id = family_id_by_pose.get(int(pose_idx))
        if family_id is None:
            continue
        family_name = family_name_by_int.get(int(family_id))
        if family_name is None:
            continue
        counts[str(family_name)] += 1
    return dict(counts)


def _family_sizes(model: Any) -> Dict[str, int]:
    delegate = getattr(model, "_coordinate_delegate", None)
    return {
        str(family): int(count)
        for family, count in dict(
            getattr(delegate, "_power_pole_family_pose_counts", {}) or {}
        ).items()
    }


def _family_global_upper_bound(model: Any, family_name: str) -> int:
    delegate = getattr(model, "_coordinate_delegate", None)
    upper_bound_fn = getattr(delegate, "_power_pole_family_count_upper_bound", None)
    if callable(upper_bound_fn):
        return int(upper_bound_fn(str(family_name)))
    family_size = int(_family_sizes(model).get(str(family_name), 0))
    slot_pool_upper_bound = int(
        len(getattr(delegate, "residual_optional_slots", {}).get("power_pole", []))
    )
    return int(min(family_size, slot_pool_upper_bound))


def _proto_constraint_payload(
    model: Any,
    *,
    anchor_idx: int,
    target_power_family: str,
    global_upper_bound: int,
) -> Dict[str, Any]:
    u_var = getattr(model, "u_vars", {}).get(int(anchor_idx))
    delegate = getattr(model, "_coordinate_delegate", None)
    count_var = dict(getattr(delegate, "power_pole_family_count_vars", {}) or {}).get(
        str(target_power_family)
    )
    if count_var is None:
        count_var = dict(getattr(model, "_power_pole_family_count_vars", {}) or {}).get(
            str(target_power_family)
        )
    if u_var is None or count_var is None:
        return {
            "present": False,
            "matching_constraint_count": 0,
            "reason": "missing_u_or_count_var",
        }
    u_idx = int(u_var.Index())
    count_idx = int(count_var.Index())
    matches: list[Dict[str, Any]] = []
    proto = model.model.Proto()
    variable_names = [str(var.name) for var in list(proto.variables)]
    for constraint_idx, constraint in enumerate(list(proto.constraints)):
        linear = getattr(constraint, "linear", None)
        if linear is None:
            continue
        vars_ = [int(var_idx) for var_idx in list(linear.vars)]
        if sorted(vars_) != sorted([count_idx, u_idx]):
            continue
        coeff_by_var = {
            int(var_idx): int(coeff)
            for var_idx, coeff in zip(list(linear.vars), list(linear.coeffs))
        }
        if coeff_by_var.get(count_idx) != 1:
            continue
        u_coeff = int(coeff_by_var.get(u_idx, 0))
        if u_coeff <= 0:
            continue
        domain = [int(value) for value in list(linear.domain)]
        if len(domain) != 2:
            continue
        implied_bound = int(domain[1] - u_coeff)
        matches.append(
            {
                "constraint_index": int(constraint_idx),
                "u_var_index": int(u_idx),
                "u_var_name": _var_name(variable_names, u_idx),
                "count_var_index": int(count_idx),
                "count_var_name": _var_name(variable_names, count_idx),
                "u_coefficient": int(u_coeff),
                "count_coefficient": int(coeff_by_var.get(count_idx, 0)),
                "domain": domain,
                "implied_global_upper_bound": int(u_coeff),
                "expected_global_upper_bound": int(global_upper_bound),
                "implied_conditioned_upper_bound": int(implied_bound),
            }
        )
    first = matches[0] if matches else {}
    return {
        "present": bool(matches),
        "matching_constraint_count": int(len(matches)),
        "matches": matches[:4],
        "implied_global_upper_bound": first.get("implied_global_upper_bound"),
        "expected_global_upper_bound": int(global_upper_bound),
        "implied_conditioned_upper_bound": first.get(
            "implied_conditioned_upper_bound"
        ),
    }


def _status_from_audits(audits: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not audits:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_family_bound_audits",
            "recommendation": "No family-bound audits were evaluated.",
        }
    if all(bool(audit.get("bounds_consistent", False)) for audit in audits):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "family_bound_derivation_consistent",
            "recommendation": (
                "Target family bound derivation is internally consistent; investigate "
                "whether the bound is proof-safe or too strong for the intended semantics."
            ),
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "family_bound_derivation_mismatch",
        "recommendation": "Family bound derivation mismatch found; inspect domain/proto details before any rerun.",
    }


def _summary(audits: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return {
        "audit_count": int(len(audits)),
        "all_bounds_consistent": bool(
            audits and all(bool(audit.get("bounds_consistent", False)) for audit in audits)
        ),
        "findings": [str(audit.get("finding")) for audit in audits if audit.get("finding")],
    }


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
    selected_anchor_count: int,
    status: Mapping[str, Any],
    audits: Sequence[Mapping[str, Any]],
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    all_consistent = bool(
        audits and all(bool(audit.get("bounds_consistent", False)) for audit in audits)
    )
    return [
        _check(
            "campaign_state_present",
            "pass" if state_present else "fail",
            "campaign state loaded" if state_present else "campaign state missing",
        ),
        _check(
            "candidate_present",
            "pass" if candidate_present else "fail",
            "candidate loaded" if candidate_present else "candidate missing",
        ),
        _check(
            "anchor_samples_present",
            "pass" if selected_anchor_count > 0 else "fail",
            f"selected_anchor_count={int(selected_anchor_count)}",
        ),
        _check(
            "family_bound_audit_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "skipped",
            str(status.get("outcome")),
        ),
        _check(
            "family_bound_derivation_consistent",
            "pass" if all_consistent else "fail",
            "derived/domain/proto bounds agree"
            if all_consistent
            else "derived/domain/proto bounds do not all agree",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _var_name(variable_names: Sequence[str], var_idx: int) -> str:
    if 0 <= int(var_idx) < len(variable_names):
        return str(variable_names[int(var_idx)] or f"var_{int(var_idx)}")
    return f"var_{int(var_idx)}"


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
