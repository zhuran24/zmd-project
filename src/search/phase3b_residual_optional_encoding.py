from __future__ import annotations

import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

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
)

RESIDUAL_OPTIONAL_ENCODING_SOURCE = "phase3b_residual_optional_encoding_inventory_v1"

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


def build_phase3b_residual_optional_encoding_inventory(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
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
    ghost_rect = _candidate_ghost_rect(candidate_key, record)
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Residual optional encoding inventory has not run.",
    }
    timing: Dict[str, float] = {}
    model_error: Optional[str] = None
    encoding: Dict[str, Any] = {}
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before residual optional encoding inventory.",
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
    else:
        try:
            overlay_started = time.perf_counter()
            model, base_proto = _build_exact_overlay(
                project_root,
                ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                master_search_profile=master_search_profile,
            )
            timing["overlay_build_seconds"] = float(time.perf_counter() - overlay_started)
            encoding = _encoding_payload(model, base_proto)
            status.update(
                {
                    "completed": True,
                    "evaluated": True,
                    "outcome": "residual_optional_encoding_inventory_built",
                    "recommendation": "Use residual optional encoding scale to decide whether to profile coverage or optional-cardinality constraints next.",
                }
            )
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Residual optional encoding inventory failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    return {
        "metadata": {
            "source": RESIDUAL_OPTIONAL_ENCODING_SOURCE,
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
        "status": status,
        "encoding": encoding,
        "timing": timing,
        "model_error": model_error,
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            status=status,
            model_error=model_error,
        ),
    }


def render_phase3b_residual_optional_encoding_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    encoding = _mapping(report.get("encoding"))
    proto = _mapping(encoding.get("proto"))
    residual = _mapping(encoding.get("residual_optional_slots"))
    power = _mapping(encoding.get("power_coverage"))
    lines = [
        "# Phase 3B Residual Optional Encoding Inventory",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Evaluated: {bool(status.get('evaluated', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Proto variables: {proto.get('variable_count')}",
        f"- Proto constraints: {proto.get('constraint_count')}",
        f"- Residual optional slots: {residual.get('total')}",
        f"- Power coverage: {power}",
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


def render_phase3b_residual_optional_encoding_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    encoding = _mapping(report.get("encoding"))
    proto = _mapping(encoding.get("proto"))
    residual = _mapping(encoding.get("residual_optional_slots"))
    power = _mapping(encoding.get("power_coverage"))
    gvi = _mapping(encoding.get("global_valid_inequalities"))
    lines = [
        "Phase 3B residual optional encoding inventory",
        f"candidate={candidate.get('key')}",
        f"evaluated={bool(status.get('evaluated', False))}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"proto_variables={proto.get('variable_count')}",
        f"proto_constraints={proto.get('constraint_count')}",
        f"constraint_kind_counts={proto.get('constraint_kind_counts')}",
        f"variable_prefix_counts={proto.get('variable_prefix_counts')}",
        f"residual_optional_slots={residual}",
        f"power_coverage={power}",
        f"optional_cardinality_bounds={gvi.get('optional_cardinality_bounds')}",
        f"powered_template_demands={gvi.get('powered_template_demands')}",
        f"power_capacity_summary={gvi.get('power_capacity_summary')}",
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


def _encoding_payload(model: Any, proto: Any) -> Dict[str, Any]:
    build_stats = _mapping(getattr(model, "build_stats", {}))
    delegate = getattr(model, "_coordinate_delegate", None)
    residual_slots = getattr(delegate, "residual_optional_slots", {}) if delegate else {}
    required_slots = getattr(delegate, "required_optional_slots", {}) if delegate else {}
    proto_payload = _proto_payload(proto)
    gvi = _mapping(build_stats.get("global_valid_inequalities"))
    power_families = _mapping(gvi.get("power_capacity_families"))
    return {
        "master_slot_counts": build_stats.get("master_slot_counts", {}),
        "domain_activation": build_stats.get("domain_activation", {}),
        "power_coverage": build_stats.get("power_coverage", {}),
        "residual_optional_slots": {
            "by_template": {
                str(tpl): int(len(slots)) for tpl, slots in sorted(residual_slots.items())
            },
            "total": int(sum(len(slots) for slots in residual_slots.values())),
        },
        "required_optional_slots": {
            "by_template": {
                str(tpl): int(len(slots)) for tpl, slots in sorted(required_slots.items())
            },
            "total": int(sum(len(slots) for slots in required_slots.values())),
        },
        "global_valid_inequalities": {
            "applied": gvi.get("applied", []),
            "optional_cardinality_bounds": gvi.get("optional_cardinality_bounds", {}),
            "powered_template_demands": gvi.get("powered_template_demands", {}),
            "fixed_required_optional_demands": gvi.get(
                "fixed_required_optional_demands",
                {},
            ),
            "lower_bound_optional_powered_demands": gvi.get(
                "lower_bound_optional_powered_demands",
                {},
            ),
            "aggregated_power_capacity_terms": gvi.get(
                "aggregated_power_capacity_terms",
                {},
            ),
            "ghost_aware_via_pole_feasibility": gvi.get(
                "ghost_aware_via_pole_feasibility",
                {},
            ),
            "power_capacity_summary": {
                "applied": bool(power_families.get("applied", False)),
                "family_count": int(power_families.get("family_count", 0)),
                "raw_pole_count": int(power_families.get("raw_pole_count", 0)),
                "shell_pair_count": int(power_families.get("shell_pair_count", 0)),
                "compact_signature_class_count": int(
                    power_families.get("compact_signature_class_count", 0)
                ),
            },
            "power_capacity_families": gvi.get("power_capacity_families", {}),
        },
        "proto": proto_payload,
    }


def _proto_payload(proto: Any) -> Dict[str, Any]:
    variables = list(getattr(proto, "variables", []))
    constraints = list(getattr(proto, "constraints", []))
    return {
        "variable_count": len(variables),
        "constraint_count": len(constraints),
        "constraint_kind_counts": dict(sorted(_constraint_kind_counts(constraints).items())),
        "variable_prefix_counts": dict(sorted(_variable_prefix_counts(variables).items())),
    }


def _constraint_kind_counts(constraints: list[Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for constraint in constraints:
        counts[_constraint_kind(constraint)] += 1
    return counts


def _constraint_kind(constraint: Any) -> str:
    for kind in _CONSTRAINT_KINDS:
        has_method = getattr(constraint, f"has_{kind}", None)
        try:
            if has_method is not None and bool(has_method()):
                return str(kind)
        except Exception:
            continue
    return "unknown"


def _variable_prefix_counts(variables: list[Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for variable in variables:
        name = str(getattr(variable, "name", ""))
        if name.startswith("cover_choice_"):
            counts[name.split("__", 1)[0]] += 1
        elif name.startswith("power_pole_family_count__"):
            counts["power_pole_family_count"] += 1
        elif name.startswith("residual_optional_signature_count__"):
            counts["residual_optional_signature_count"] += 1
        elif name.startswith("required_optional_signature_count__"):
            counts["required_optional_signature_count"] += 1
        elif name.startswith("mandatory_signature_count__"):
            counts["mandatory_signature_count"] += 1
    return counts


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
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
            "residual_optional_encoding_evaluated",
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
