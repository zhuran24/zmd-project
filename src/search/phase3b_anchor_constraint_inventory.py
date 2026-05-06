from __future__ import annotations

import json
import time
from collections import Counter
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

ANCHOR_CONSTRAINT_INVENTORY_SOURCE = "phase3b_anchor_constraint_inventory_v1"

_CONSTRAINT_KINDS = (
    "linear",
    "bool_or",
    "bool_and",
    "bool_xor",
    "at_most_one",
    "exactly_one",
    "interval",
    "no_overlap",
    "no_overlap_2d",
    "all_diff",
    "element",
    "table",
    "lin_max",
    "int_prod",
    "int_div",
    "int_mod",
    "cumulative",
    "reservoir",
)


def build_phase3b_anchor_constraint_inventory(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    sample_limit: int = 3,
    anchor_indices: Optional[Sequence[int]] = None,
    example_limit: int = 5,
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
        "recommendation": "Anchor constraint inventory has not run.",
    }
    timing: Dict[str, float] = {}
    model_error: Optional[str] = None
    anchor_reports: list[Dict[str, Any]] = []
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before anchor constraint inventory.",
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
                "recommendation": "No anchor samples selected; rerun B5A with failed-anchor sampling enabled.",
            }
        )
    else:
        try:
            overlay_started = time.perf_counter()
            model, base_proto = _build_exact_overlay(
                project_root,
                ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                master_search_profile=master_search_profile,
            )
            timing["overlay_build_seconds"] = float(time.perf_counter() - overlay_started)
            proto = base_proto
            for anchor_idx in selected_anchor_indices:
                u_var = model.u_vars.get(int(anchor_idx))
                if u_var is None:
                    anchor_reports.append(
                        {
                            "anchor_idx": int(anchor_idx),
                            "present": False,
                            "skip_reason": "anchor_not_in_model_u_vars",
                        }
                    )
                    continue
                domain = {}
                if int(anchor_idx) < len(getattr(model, "_ghost_domains", [])):
                    domain = dict(model._ghost_domains[int(anchor_idx)])
                anchor_reports.append(
                    _anchor_constraint_report(
                        proto,
                        anchor_idx=int(anchor_idx),
                        u_var_index=int(u_var.Index()),
                        domain=domain,
                        example_limit=int(example_limit),
                    )
                )
            status.update(_status_from_anchor_reports(anchor_reports))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Anchor constraint inventory failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    return {
        "metadata": {
            "source": ANCHOR_CONSTRAINT_INVENTORY_SOURCE,
            "generated_at": now_iso(),
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
            "example_limit": int(example_limit),
        },
        "status": status,
        "anchors": anchor_reports,
        "timing": timing,
        "model_error": model_error,
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            status=status,
            model_error=model_error,
        ),
    }


def render_phase3b_anchor_constraint_inventory_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    lines = [
        "# Phase 3B Anchor Constraint Inventory",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Evaluated: {bool(status.get('evaluated', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Anchors",
        "",
        "| Anchor | U Var | Direct Refs | Ref Counts | Domain |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in list(report.get("anchors", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("anchor_idx")),
                    _markdown_cell(entry.get("u_var_index")),
                    _markdown_cell(entry.get("direct_u_reference_total")),
                    _markdown_cell(entry.get("direct_u_reference_counts")),
                    _markdown_cell(_mapping(entry.get("domain_summary")).get("anchor")),
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


def render_phase3b_anchor_constraint_inventory_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    lines = [
        "Phase 3B anchor constraint inventory",
        f"candidate={candidate.get('key')}",
        f"evaluated={bool(status.get('evaluated', False))}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
    ]
    for entry in list(report.get("anchors", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "anchor "
            f"idx={entry.get('anchor_idx')} "
            f"u_var={entry.get('u_var_index')} "
            f"direct_refs={entry.get('direct_u_reference_total')} "
            f"ref_counts={entry.get('direct_u_reference_counts')} "
            f"role_counts={entry.get('direct_u_reference_role_counts')} "
            f"other_vars={entry.get('direct_u_other_var_name_counts')} "
            f"domain={_mapping(entry.get('domain_summary')).get('anchor')}"
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


def _anchor_constraint_report(
    proto: Any,
    *,
    anchor_idx: int,
    u_var_index: int,
    domain: Mapping[str, Any],
    example_limit: int,
) -> Dict[str, Any]:
    kind_counts: Counter[str] = Counter()
    reference_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    other_var_name_counts: Counter[str] = Counter()
    examples: list[Dict[str, Any]] = []
    variable_names = [
        str(getattr(variable, "name", ""))
        for variable in list(getattr(proto, "variables", []))
    ]
    constraints = list(getattr(proto, "constraints", []))
    for constraint_idx, constraint in enumerate(constraints):
        kind = _constraint_kind(constraint)
        kind_counts[str(kind)] += 1
        roles = _u_reference_roles(constraint, kind=kind, u_var_index=u_var_index)
        if not roles:
            continue
        reference_counts[str(kind)] += 1
        for role in roles:
            role_counts[f"{kind}:{role}"] += 1
        for var_name in _other_reference_variable_names(
            constraint,
            kind=kind,
            u_var_index=u_var_index,
            variable_names=variable_names,
        ):
            other_var_name_counts[str(var_name)] += 1
        if len(examples) < int(example_limit):
            examples.append(
                {
                    "constraint_index": int(constraint_idx),
                    "kind": str(kind),
                    "roles": list(roles),
                    "reference_details": _constraint_reference_details(
                        constraint,
                        kind=kind,
                        u_var_index=u_var_index,
                        variable_names=variable_names,
                    ),
                    "snippet": str(constraint).replace("\n", " ")[:300],
                }
            )
    return {
        "anchor_idx": int(anchor_idx),
        "present": True,
        "u_var_index": int(u_var_index),
        "total_variables": len(list(getattr(proto, "variables", []))),
        "total_constraints": len(constraints),
        "constraint_kind_counts": dict(sorted(kind_counts.items())),
        "direct_u_reference_counts": dict(sorted(reference_counts.items())),
        "direct_u_reference_role_counts": dict(sorted(role_counts.items())),
        "direct_u_reference_total": int(sum(reference_counts.values())),
        "direct_u_other_var_name_counts": dict(sorted(other_var_name_counts.items())),
        "domain_summary": _domain_summary(domain),
        "examples": examples,
    }


def _constraint_kind(constraint: Any) -> str:
    for kind in _CONSTRAINT_KINDS:
        has_method = getattr(constraint, f"has_{kind}", None)
        try:
            if has_method is not None and bool(has_method()):
                return str(kind)
        except Exception:
            continue
    return "unknown"


def _u_reference_roles(
    constraint: Any,
    *,
    kind: str,
    u_var_index: int,
) -> list[str]:
    roles: list[str] = []
    if any(_literal_var_index(lit) == int(u_var_index) for lit in list(constraint.enforcement_literal)):
        roles.append("enforcement")
    if kind == "linear":
        linear = getattr(constraint, "linear")
        if any(int(var_idx) == int(u_var_index) for var_idx in list(linear.vars)):
            roles.append("linear")
    if kind in {"bool_or", "bool_and", "bool_xor", "at_most_one", "exactly_one"}:
        bool_arg = getattr(constraint, kind)
        if any(
            _literal_var_index(lit) == int(u_var_index)
            for lit in list(bool_arg.literals)
        ):
            roles.append("literal")
    return roles


def _other_reference_variable_names(
    constraint: Any,
    *,
    kind: str,
    u_var_index: int,
    variable_names: Sequence[str],
) -> list[str]:
    names: list[str] = []
    if kind != "linear":
        return names
    linear = getattr(constraint, "linear")
    for var_idx in list(linear.vars):
        var_idx = int(var_idx)
        if var_idx == int(u_var_index):
            continue
        names.append(_variable_name(variable_names, var_idx))
    return names


def _constraint_reference_details(
    constraint: Any,
    *,
    kind: str,
    u_var_index: int,
    variable_names: Sequence[str],
) -> Dict[str, Any]:
    if kind == "linear":
        linear = getattr(constraint, "linear")
        return {
            "linear_terms": [
                {
                    "var_index": int(var_idx),
                    "var_name": _variable_name(variable_names, int(var_idx)),
                    "coeff": int(coeff),
                    "is_anchor_u": int(var_idx) == int(u_var_index),
                }
                for var_idx, coeff in zip(list(linear.vars), list(linear.coeffs))
            ],
            "domain": [int(value) for value in list(linear.domain)],
        }
    if kind in {"bool_or", "bool_and", "bool_xor", "at_most_one", "exactly_one"}:
        bool_arg = getattr(constraint, kind)
        return {
            "literals": [
                {
                    "literal": int(lit),
                    "var_index": _literal_var_index(int(lit)),
                    "var_name": _variable_name(variable_names, _literal_var_index(int(lit))),
                    "is_anchor_u": _literal_var_index(int(lit)) == int(u_var_index),
                }
                for lit in list(bool_arg.literals)
            ]
        }
    return {}


def _variable_name(variable_names: Sequence[str], var_idx: int) -> str:
    if 0 <= int(var_idx) < len(variable_names):
        return str(variable_names[int(var_idx)] or f"var_{int(var_idx)}")
    return f"var_{int(var_idx)}"


def _literal_var_index(literal: int) -> int:
    literal = int(literal)
    return literal if literal >= 0 else -literal - 1


def _domain_summary(domain: Mapping[str, Any]) -> Dict[str, Any]:
    cells = list(domain.get("cells", []))
    power_bounds = _mapping(domain.get("conditioned_power_pole_family_upper_bounds"))
    return {
        "anchor": domain.get("anchor"),
        "cell_count": len(cells),
        "screened_by_power_capacity": list(
            domain.get("screened_by_power_capacity", [])
        ),
        "conditioned_power_pole_family_upper_bound_count": len(power_bounds),
        "conditioned_power_pole_family_upper_bounds": dict(power_bounds),
    }


def _status_from_anchor_reports(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not entries:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_anchors_evaluated",
            "recommendation": "No anchors were evaluated.",
        }
    total_direct_refs = sum(int(entry.get("direct_u_reference_total", 0)) for entry in entries)
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "anchor_constraint_inventory_built",
        "direct_u_reference_total": int(total_direct_refs),
        "recommendation": "Use direct u-reference counts and domain summaries to identify forced-anchor constraint families.",
    }


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
    selected_anchor_count: int,
    status: Mapping[str, Any],
    model_error: Optional[str],
) -> list[Dict[str, str]]:
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
            "anchor_constraint_inventory_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "skipped",
            str(status.get("outcome")),
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
