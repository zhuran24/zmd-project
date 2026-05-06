from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.search.exact_campaign import now_iso
from src.search.phase3b_forced_anchor_master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
    _candidate_ghost_rect,
    _check,
    _display_path,
    _file_hash,
    _load_json_mapping,
    _mapping,
    _resolve_path,
    _selected_anchor_indices,
)
from src.search.phase3b_forced_anchor_model_slice import (
    _build_exact_overlay,
    _constraint_var_indices,
    _literal_var_index,
)
from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE


ANCHOR_DIFFERENTIAL_AUDIT_SOURCE = "phase3b_anchor_differential_audit_v1"


def build_phase3b_anchor_differential_audit(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = "67x13",
    anchor_indices: Optional[Sequence[int]] = None,
    sample_limit: int = 2,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path if campaign_state_path is not None else DEFAULT_CAMPAIGN_STATE_PATH,
    )
    before_hash = _file_hash(campaign_path)
    state, state_error = _load_json_mapping(campaign_path)
    candidates = _mapping(state.get("candidates")) if state else {}
    record = _mapping(candidates.get(str(candidate)))
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
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Anchor differential audit has not run.",
    }
    model_error: Optional[str] = None
    anchor_profiles: list[Dict[str, Any]] = []
    comparison: Dict[str, Any] = {}
    proto_profile: Dict[str, Any] = {}
    capacity_profile: Dict[str, Any] = {}
    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before anchor differential audit.",
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
                "recommendation": "No anchor indices were selected; pass --anchor-indices explicitly.",
            }
        )
    else:
        try:
            ghost_rect = _candidate_ghost_rect(str(candidate), record)
            model, base_proto = _build_exact_overlay(
                project_root,
                ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                master_search_profile=master_search_profile,
            )
            proto_profile = _proto_profile(base_proto)
            capacity_profile = _capacity_profile_from_model(model)
            for anchor_idx in selected_anchor_indices:
                u_var = model.u_vars.get(int(anchor_idx))
                if u_var is None:
                    anchor_profiles.append(
                        {
                            "anchor_idx": int(anchor_idx),
                            "present": False,
                            "skip_reason": "anchor_not_in_model_u_vars",
                        }
                    )
                    continue
                anchor_profile = _anchor_profile(
                    base_proto,
                    anchor_idx=int(anchor_idx),
                    u_var_index=int(u_var.Index()),
                )
                anchor_profile["capacity_certificate"] = _anchor_capacity_certificate(
                    anchor_profile,
                    capacity_profile,
                )
                anchor_profiles.append(anchor_profile)
            comparison = _compare_anchor_profiles(anchor_profiles)
            status.update(
                {
                    "completed": True,
                    "evaluated": True,
                    "outcome": "anchor_differential_audit_completed",
                    "recommendation": "Use this no-solve anchor-local profile to decide whether a guarded precheck has an exact necessary-condition target.",
                }
            )
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Anchor differential audit failed; inspect model_error before using this evidence.",
                }
            )
    after_hash = _file_hash(campaign_path)
    campaign_state_unchanged = before_hash == after_hash
    return {
        "metadata": {
            "source": ANCHOR_DIFFERENTIAL_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_anchor_differential_audit_not_proof_source",
            "solver_invoked": False,
        },
        "paths": {
            "project_root": str(project_root),
            "campaign_state": _display_path(project_root, campaign_path),
        },
        "candidate": {
            "key": str(candidate),
            "campaign_status": record.get("status") if record else None,
            "ghost_rect": _candidate_ghost_rect(str(candidate), record) if record else {},
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "sample_limit": int(sample_limit),
            "selected_anchor_indices": [int(idx) for idx in selected_anchor_indices],
        },
        "proto_profile": proto_profile,
        "capacity_profile": capacity_profile,
        "anchors": anchor_profiles,
        "comparison": comparison,
        "status": status,
        "model_error": model_error,
        "campaign_state_unchanged": bool(campaign_state_unchanged),
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            status=status,
            campaign_state_unchanged=campaign_state_unchanged,
            model_error=model_error,
        ),
    }


def render_phase3b_anchor_differential_audit_markdown(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    candidate = _mapping(report.get("candidate"))
    lines = [
        "# Phase 3B Anchor Differential Audit",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Evaluated: {bool(status.get('evaluated', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Solver invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
        f"- Campaign state unchanged: {bool(report.get('campaign_state_unchanged', False))}",
        "",
        "## Anchors",
        "",
        "| Anchor | Present | u_var | constraint refs | enforcement refs | var refs | family-count refs | top neighbor prefixes |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for anchor in list(report.get("anchors", [])):
        if not isinstance(anchor, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(anchor.get("anchor_idx")),
                    _cell(anchor.get("present")),
                    _cell(anchor.get("u_var_index")),
                    _cell(anchor.get("constraint_reference_count")),
                    _cell(anchor.get("enforcement_reference_count")),
                    _cell(anchor.get("var_reference_count")),
                    _cell(anchor.get("family_count_linear_reference_count")),
                    _cell(_top_counts(_mapping(anchor.get("neighbor_prefix_counts")))),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Family Count Linear Refs", ""])
    lines.append("| Anchor | Constraint | Family terms | Active bounds | Domain |")
    lines.append("| --- | ---: | --- | --- | --- |")
    for anchor in list(report.get("anchors", [])):
        if not isinstance(anchor, Mapping):
            continue
        for ref in list(anchor.get("family_count_linear_refs", []))[:80]:
            if not isinstance(ref, Mapping):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(anchor.get("anchor_idx")),
                        _cell(ref.get("constraint_idx")),
                        _cell(_format_family_terms(list(ref.get("family_count_terms", [])))),
                        _cell(_format_active_bounds(list(ref.get("active_family_count_bounds", [])))),
                        _cell(ref.get("linear_domain")),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Comparison", "", "```json"])
    lines.append(json.dumps(report.get("comparison", {}), indent=2, ensure_ascii=False))
    lines.extend(["```", "", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(check.get("check_id")),
                        _cell(check.get("status")),
                        _cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_anchor_differential_audit_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    candidate = _mapping(report.get("candidate"))
    lines = [
        "Phase 3B anchor differential audit",
        f"candidate={candidate.get('key')}",
        f"evaluated={bool(status.get('evaluated', False))}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"solver_invoked={bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
        f"campaign_state_unchanged={bool(report.get('campaign_state_unchanged', False))}",
        "",
        "anchors:",
    ]
    for anchor in list(report.get("anchors", [])):
        if isinstance(anchor, Mapping):
            lines.append(
                "  "
                f"anchor={anchor.get('anchor_idx')} "
                f"present={anchor.get('present')} "
                f"u_var={anchor.get('u_var_index')} "
                f"constraints={anchor.get('constraint_reference_count')} "
                f"enforcements={anchor.get('enforcement_reference_count')} "
                f"var_refs={anchor.get('var_reference_count')} "
                f"family_count_refs={anchor.get('family_count_linear_reference_count')} "
                f"top_prefixes={_top_counts(_mapping(anchor.get('neighbor_prefix_counts')))}"
            )
            cert = _mapping(anchor.get("capacity_certificate"))
            lines.append(
                "    "
                f"capacity_deficit={cert.get('has_deficit')} "
                f"templates={_capacity_summary(cert)}"
            )
            for ref in list(anchor.get("family_count_linear_refs", []))[:10]:
                if isinstance(ref, Mapping):
                    lines.append(
                        "    "
                        f"constraint={ref.get('constraint_idx')} "
                        f"families={_format_family_terms(list(ref.get('family_count_terms', [])))} "
                        f"active_bounds={_format_active_bounds(list(ref.get('active_family_count_bounds', [])))} "
                        f"domain={ref.get('linear_domain')}"
                    )
    lines.append("")
    lines.append("comparison:")
    lines.append(json.dumps(report.get("comparison", {}), indent=2, ensure_ascii=False))
    return "\n".join(lines) + "\n"


def _proto_profile(model_proto: Any) -> Dict[str, Any]:
    kind_counts: Dict[str, int] = {}
    for constraint in model_proto.constraints:
        kind = _constraint_kind(constraint)
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    return {
        "variable_count": int(len(model_proto.variables)),
        "constraint_count": int(len(model_proto.constraints)),
        "constraint_kind_counts": dict(sorted(kind_counts.items())),
    }


def _capacity_profile_from_model(model: Any) -> Dict[str, Any]:
    gvi = _mapping(getattr(model, "build_stats", {}).get("global_valid_inequalities"))
    family_payload = _mapping(gvi.get("power_capacity_families"))
    families = [
        dict(family)
        for family in list(family_payload.get("families", []))
        if isinstance(family, Mapping)
    ]
    return {
        "powered_template_demands": {
            str(tpl): int(demand)
            for tpl, demand in sorted(_mapping(gvi.get("powered_template_demands")).items())
        },
        "families": families,
        "family_count": int(family_payload.get("family_count", len(families)) or 0),
        "coefficient_source": family_payload.get("coefficient_source"),
    }


def _anchor_capacity_certificate(
    anchor_profile: Mapping[str, Any],
    capacity_profile: Mapping[str, Any],
) -> Dict[str, Any]:
    demands = {
        str(tpl): int(demand)
        for tpl, demand in sorted(_mapping(capacity_profile.get("powered_template_demands")).items())
    }
    families = [
        dict(family)
        for family in list(capacity_profile.get("families", []))
        if isinstance(family, Mapping)
    ]
    active_upper_by_family = _active_upper_by_family(anchor_profile)
    family_bounds: Dict[str, Dict[str, Any]] = {}
    for family in families:
        family_name = str(family.get("family_id", ""))
        if not family_name:
            continue
        default_upper = int(family.get("count_var_upper_bound", family.get("size", 0)) or 0)
        active_upper = active_upper_by_family.get(family_name)
        if active_upper is None:
            effective_upper = int(default_upper)
            source = "global_upper_bound"
        else:
            effective_upper = int(min(default_upper, math.floor(float(active_upper))))
            source = "anchor_active_bound"
        family_bounds[family_name] = {
            "family_name": family_name,
            "default_upper": int(default_upper),
            "effective_upper": int(max(0, effective_upper)),
            "source": source,
            "coefficients": {
                str(tpl): int(coeff)
                for tpl, coeff in sorted(_mapping(family.get("coefficients")).items())
            },
        }
    template_certificates: list[Dict[str, Any]] = []
    for tpl, demand in demands.items():
        contributions: list[Dict[str, Any]] = []
        max_capacity = 0
        for family_name, bound in sorted(family_bounds.items()):
            coeff = int(_mapping(bound.get("coefficients")).get(str(tpl), 0) or 0)
            if coeff <= 0:
                continue
            contribution = coeff * int(bound["effective_upper"])
            max_capacity += int(contribution)
            contributions.append(
                {
                    "family_name": family_name,
                    "coeff": int(coeff),
                    "effective_upper": int(bound["effective_upper"]),
                    "source": str(bound["source"]),
                    "max_contribution": int(contribution),
                }
            )
        template_certificates.append(
            {
                "template": str(tpl),
                "demand": int(demand),
                "max_capacity": int(max_capacity),
                "slack": int(max_capacity) - int(demand),
                "deficit": int(max_capacity) < int(demand),
                "top_contributions": sorted(
                    contributions,
                    key=lambda item: (-int(item["max_contribution"]), str(item["family_name"])),
                )[:12],
            }
        )
    return {
        "evaluated": bool(demands and families),
        "has_deficit": any(bool(item["deficit"]) for item in template_certificates),
        "template_certificates": template_certificates,
        "anchor_active_bound_family_count": int(len(active_upper_by_family)),
    }


def _active_upper_by_family(anchor_profile: Mapping[str, Any]) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for ref in list(anchor_profile.get("family_count_linear_refs", [])):
        if not isinstance(ref, Mapping):
            continue
        for bound in list(ref.get("active_family_count_bounds", [])):
            if not isinstance(bound, Mapping):
                continue
            family_name = str(bound.get("family_name", ""))
            if not family_name:
                continue
            active_upper = float(bound.get("implied_upper_when_anchor_active", 0))
            if family_name in result:
                result[family_name] = min(result[family_name], active_upper)
            else:
                result[family_name] = active_upper
    return result


def _anchor_profile(model_proto: Any, *, anchor_idx: int, u_var_index: int) -> Dict[str, Any]:
    references: list[Dict[str, Any]] = []
    family_count_linear_refs: list[Dict[str, Any]] = []
    neighbor_indices: set[int] = set()
    kind_counts: Dict[str, int] = {}
    enforcement_count = 0
    var_ref_count = 0
    for constraint_idx, constraint in enumerate(model_proto.constraints):
        vars_in_constraint = set(_constraint_var_indices(constraint))
        vars_in_constraint.update(_constraint_literal_var_indices(constraint))
        enforcement_vars = {
            _literal_var_index(int(lit)) for lit in getattr(constraint, "enforcement_literal", [])
        }
        roles: list[str] = []
        if int(u_var_index) in vars_in_constraint:
            roles.append("var")
            var_ref_count += 1
        if int(u_var_index) in enforcement_vars:
            roles.append("enforcement")
            enforcement_count += 1
        if not roles:
            continue
        kind = _constraint_kind(constraint)
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        neighbor_indices.update(vars_in_constraint)
        neighbor_indices.update(enforcement_vars)
        references.append(
            {
                "constraint_idx": int(constraint_idx),
                "kind": kind,
                "roles": roles,
                "var_count": int(len(vars_in_constraint)),
                "enforcement_count": int(len(enforcement_vars)),
            }
        )
        if kind == "linear":
            family_ref = _family_count_linear_ref(
                model_proto,
                constraint,
                constraint_idx=int(constraint_idx),
                u_var_index=int(u_var_index),
            )
            if family_ref:
                family_count_linear_refs.append(family_ref)
    neighbor_indices.discard(int(u_var_index))
    neighbor_prefix_counts = _variable_prefix_counts(model_proto, sorted(neighbor_indices))
    family_count_name_counts: Dict[str, int] = {}
    for ref in family_count_linear_refs:
        for term in list(ref.get("family_count_terms", [])):
            family_name = str(term.get("family_name", ""))
            if family_name:
                family_count_name_counts[family_name] = family_count_name_counts.get(family_name, 0) + 1
    return {
        "anchor_idx": int(anchor_idx),
        "present": True,
        "u_var_index": int(u_var_index),
        "u_var_name": str(model_proto.variables[int(u_var_index)].name),
        "constraint_reference_count": int(len(references)),
        "enforcement_reference_count": int(enforcement_count),
        "var_reference_count": int(var_ref_count),
        "constraint_kind_counts": dict(sorted(kind_counts.items())),
        "neighbor_variable_count": int(len(neighbor_indices)),
        "neighbor_prefix_counts": neighbor_prefix_counts,
        "family_count_linear_reference_count": int(len(family_count_linear_refs)),
        "family_count_name_counts": dict(sorted(family_count_name_counts.items())),
        "family_count_linear_refs": family_count_linear_refs,
        "reference_samples": references[:40],
    }


def _compare_anchor_profiles(anchors: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    present = [anchor for anchor in anchors if bool(anchor.get("present"))]
    if len(present) < 2:
        return {
            "comparable": False,
            "reason": "fewer_than_two_present_anchors",
        }
    base = present[0]
    comparisons = []
    for other in present[1:]:
        comparisons.append(
            {
                "left_anchor": int(base.get("anchor_idx", -1)),
                "right_anchor": int(other.get("anchor_idx", -1)),
                "constraint_reference_delta": int(other.get("constraint_reference_count", 0))
                - int(base.get("constraint_reference_count", 0)),
                "enforcement_reference_delta": int(other.get("enforcement_reference_count", 0))
                - int(base.get("enforcement_reference_count", 0)),
                "var_reference_delta": int(other.get("var_reference_count", 0))
                - int(base.get("var_reference_count", 0)),
                "constraint_kind_count_delta": _count_delta(
                    _mapping(base.get("constraint_kind_counts")),
                    _mapping(other.get("constraint_kind_counts")),
                ),
                "neighbor_prefix_count_delta": _count_delta(
                    _mapping(base.get("neighbor_prefix_counts")),
                    _mapping(other.get("neighbor_prefix_counts")),
                ),
                "family_count_linear_reference_delta": int(
                    other.get("family_count_linear_reference_count", 0)
                )
                - int(base.get("family_count_linear_reference_count", 0)),
                "family_count_name_count_delta": _count_delta(
                    _mapping(base.get("family_count_name_counts")),
                    _mapping(other.get("family_count_name_counts")),
                ),
            }
        )
    return {
        "comparable": True,
        "baseline_anchor": int(base.get("anchor_idx", -1)),
        "comparisons": comparisons,
    }


def _variable_prefix_counts(model_proto: Any, indices: Sequence[int]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for index in indices:
        if index < 0 or index >= len(model_proto.variables):
            continue
        name = str(model_proto.variables[int(index)].name)
        prefix = _variable_prefix(name)
        counts[prefix] = counts.get(prefix, 0) + 1
    return dict(sorted(counts.items()))


def _constraint_kind(constraint: Any) -> str:
    for field in (
        "bool_or",
        "bool_and",
        "bool_xor",
        "at_most_one",
        "exactly_one",
        "linear",
        "element",
        "interval",
        "no_overlap",
        "no_overlap_2d",
        "cumulative",
        "lin_max",
        "table",
        "automaton",
        "inverse",
        "reservoir",
        "circuit",
        "routes",
        "all_diff",
        "int_div",
        "int_mod",
        "int_prod",
        "dummy_constraint",
    ):
        checker = getattr(constraint, f"has_{field}", None)
        if callable(checker):
            if checker():
                return field
            continue
        has_field = getattr(constraint, "HasField", None)
        if callable(has_field):
            try:
                if has_field(field):
                    return field
            except ValueError:
                continue
    return "empty"


def _constraint_literal_var_indices(constraint: Any) -> list[int]:
    indices: set[int] = set()
    for field in ("bool_or", "bool_and", "bool_xor", "at_most_one", "exactly_one"):
        checker = getattr(constraint, f"has_{field}", None)
        if callable(checker) and not checker():
            continue
        payload = getattr(constraint, field, None)
        if payload is None:
            continue
        for literal in list(getattr(payload, "literals", [])):
            indices.add(_literal_var_index(int(literal)))
    return sorted(indices)


def _family_count_linear_ref(
    model_proto: Any,
    constraint: Any,
    *,
    constraint_idx: int,
    u_var_index: int,
) -> Dict[str, Any]:
    linear = getattr(constraint, "linear", None)
    if linear is None:
        return {}
    terms = _linear_terms(model_proto, linear)
    family_terms = [
        term
        for term in terms
        if str(term.get("name", "")).startswith("power_pole_family_count__")
    ]
    if not family_terms:
        return {}
    u_terms = [term for term in terms if int(term.get("var_index", -1)) == int(u_var_index)]
    active_bounds = _active_family_count_bounds(
        family_terms=family_terms,
        u_terms=u_terms,
        linear_domain=[int(value) for value in list(getattr(linear, "domain", []))],
    )
    return {
        "constraint_idx": int(constraint_idx),
        "linear_domain": [int(value) for value in list(getattr(linear, "domain", []))],
        "u_terms": u_terms,
        "family_count_terms": family_terms,
        "active_family_count_bounds": active_bounds,
        "all_terms": terms,
    }


def _active_family_count_bounds(
    *,
    family_terms: Sequence[Mapping[str, Any]],
    u_terms: Sequence[Mapping[str, Any]],
    linear_domain: Sequence[int],
) -> list[Dict[str, Any]]:
    if len(family_terms) != 1 or len(u_terms) != 1:
        return []
    family_term = dict(family_terms[0])
    u_term = dict(u_terms[0])
    family_coeff = int(family_term.get("coeff", 0) or 0)
    if family_coeff == 0:
        return []
    domain = [int(value) for value in list(linear_domain)]
    if len(domain) < 2:
        return []
    upper = int(domain[-1])
    lower = int(domain[0])
    u_coeff = int(u_term.get("coeff", 0) or 0)
    family_domain = [int(value) for value in list(family_term.get("domain", []))]
    family_domain_upper = int(family_domain[-1]) if family_domain else None
    active_upper = (upper - u_coeff) / family_coeff
    payload: Dict[str, Any] = {
        "family_name": str(family_term.get("family_name", "")),
        "family_var_index": int(family_term.get("var_index", -1)),
        "family_coeff": int(family_coeff),
        "u_coeff": int(u_coeff),
        "linear_upper": int(upper),
        "implied_upper_when_anchor_active": active_upper,
        "family_domain_upper": family_domain_upper,
    }
    if family_domain_upper is not None:
        payload["upper_reduction_when_anchor_active"] = float(
            family_domain_upper - active_upper
        )
    if len(domain) >= 2 and lower > -9223372036854770000:
        active_lower = (lower - u_coeff) / family_coeff
        payload["linear_lower"] = int(lower)
        payload["implied_lower_when_anchor_active"] = active_lower
    return [payload]


def _linear_terms(model_proto: Any, linear: Any) -> list[Dict[str, Any]]:
    vars_ = [int(var_idx) for var_idx in list(getattr(linear, "vars", []))]
    coeffs = [int(coeff) for coeff in list(getattr(linear, "coeffs", []))]
    terms: list[Dict[str, Any]] = []
    for var_idx, coeff in zip(vars_, coeffs):
        name = _var_name(model_proto, int(var_idx))
        term: Dict[str, Any] = {
            "var_index": int(var_idx),
            "name": name,
            "prefix": _variable_prefix(name),
            "coeff": int(coeff),
            "domain": _var_domain(model_proto, int(var_idx)),
        }
        family_name = _family_count_name(name)
        if family_name:
            term["family_name"] = family_name
        terms.append(term)
    return terms


def _var_name(model_proto: Any, var_idx: int) -> str:
    if var_idx < 0 or var_idx >= len(model_proto.variables):
        return ""
    return str(model_proto.variables[int(var_idx)].name)


def _var_domain(model_proto: Any, var_idx: int) -> list[int]:
    if var_idx < 0 or var_idx >= len(model_proto.variables):
        return []
    return [int(value) for value in list(model_proto.variables[int(var_idx)].domain)]


def _family_count_name(var_name: str) -> str:
    prefix = "power_pole_family_count__"
    if not str(var_name).startswith(prefix):
        return ""
    return str(var_name)[len(prefix):]


def _variable_prefix(name: str) -> str:
    if name.startswith("cover_choice_"):
        return "cover_choice_"
    if "__" in name:
        return name.split("__", 1)[0] + "__"
    if "_" in name:
        return name.split("_", 1)[0] + "_"
    return name or "<unnamed>"


def _count_delta(left: Mapping[str, Any], right: Mapping[str, Any]) -> Dict[str, int]:
    keys = sorted(set(left) | set(right))
    return {
        key: int(right.get(key, 0) or 0) - int(left.get(key, 0) or 0)
        for key in keys
        if int(right.get(key, 0) or 0) - int(left.get(key, 0) or 0) != 0
    }


def _top_counts(counts: Mapping[str, Any], *, limit: int = 5) -> str:
    items = sorted(
        ((str(key), int(value)) for key, value in counts.items()),
        key=lambda item: (-item[1], item[0]),
    )
    return ", ".join(f"{key}:{value}" for key, value in items[:limit])


def _format_family_terms(terms: Sequence[Any]) -> str:
    rendered: list[str] = []
    for term in terms:
        if not isinstance(term, Mapping):
            continue
        rendered.append(
            f"{term.get('family_name')}@{term.get('var_index')} coeff={term.get('coeff')} domain={term.get('domain')}"
        )
    return "; ".join(rendered)


def _format_active_bounds(bounds: Sequence[Any]) -> str:
    rendered: list[str] = []
    for item in bounds:
        if not isinstance(item, Mapping):
            continue
        rendered.append(
            f"{item.get('family_name')} <= {item.get('implied_upper_when_anchor_active')} "
            f"(reduction={item.get('upper_reduction_when_anchor_active')})"
        )
    return "; ".join(rendered)


def _capacity_summary(certificate: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for item in list(certificate.get("template_certificates", [])):
        if not isinstance(item, Mapping):
            continue
        parts.append(
            f"{item.get('template')}:max={item.get('max_capacity')} demand={item.get('demand')} slack={item.get('slack')}"
        )
    return "; ".join(parts)


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
    selected_anchor_count: int,
    status: Mapping[str, Any],
    campaign_state_unchanged: bool,
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    return [
        _check(
            "campaign_state_present",
            "pass" if state_present else "fail",
            "campaign state loaded" if state_present else "campaign state missing or invalid",
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
            "no_solver_invoked",
            "pass",
            "audit builds and inspects proto only; CpSolver.Solve is not called",
        ),
        _check(
            "anchor_differential_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "fail",
            str(status.get("outcome")),
        ),
        _check(
            "campaign_state_unchanged",
            "pass" if campaign_state_unchanged else "fail",
            "campaign state hash unchanged"
            if campaign_state_unchanged
            else "campaign state hash changed",
        ),
        _check(
            "model_error_absent",
            "pass" if not model_error else "fail",
            "no model error" if not model_error else str(model_error),
        ),
    ]


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
