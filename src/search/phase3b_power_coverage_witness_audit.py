from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso
from src.search.phase3b_power_coverage_core_blocker import (
    DEFAULT_CORE_SLICE_PATH,
    DEFAULT_CUSTOM_CORE_SLICE_PATH,
    POWER_COVERAGE_CORE_BLOCKER_SOURCE,
)
from src.search.phase3b_power_protocol_interaction import (
    DEFAULT_RESIDUAL_OPTIONAL_ENCODING_PATH,
)

POWER_COVERAGE_WITNESS_AUDIT_SOURCE = "phase3b_power_coverage_witness_audit_v1"
RESIDUAL_OPTIONAL_ENCODING_SOURCE = "phase3b_residual_optional_encoding_inventory_v1"

DEFAULT_POWER_COVERAGE_CORE_BLOCKER_PATH = Path(
    ".artifacts/phase3b_power_coverage_core_blocker/power_coverage_core_blocker.json"
)
DEFAULT_POWER_COVERAGE_WITNESS_AUDIT_PATH = Path(
    ".artifacts/phase3b_power_coverage_witness_audit/power_coverage_witness_audit.json"
)
DEFAULT_POWER_COVERAGE_RELAX_SLICE_PATH = Path(
    ".artifacts/phase3b_forced_anchor_model_slice_67x13_power_coverage_relax/"
    "forced_anchor_model_slice_67x13_anchor119_power_coverage_relax.json"
)


def build_phase3b_power_coverage_witness_audit(
    project_root: Path,
    *,
    residual_optional_encoding_path: Optional[Path] = None,
    power_coverage_core_blocker_path: Optional[Path] = None,
    power_coverage_relax_slice_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    residual_path = _resolve_path(
        project_root,
        residual_optional_encoding_path
        if residual_optional_encoding_path is not None
        else DEFAULT_RESIDUAL_OPTIONAL_ENCODING_PATH,
    )
    core_path = _resolve_path(
        project_root,
        power_coverage_core_blocker_path
        if power_coverage_core_blocker_path is not None
        else DEFAULT_POWER_COVERAGE_CORE_BLOCKER_PATH,
    )
    relax_path = _resolve_path(
        project_root,
        power_coverage_relax_slice_path
        if power_coverage_relax_slice_path is not None
        else DEFAULT_POWER_COVERAGE_RELAX_SLICE_PATH,
    )
    residual_payload, residual_error = _load_json_mapping(residual_path)
    core_payload, core_error = _load_json_mapping(core_path)
    relax_payload, relax_error = _load_json_mapping(relax_path)
    residual = _residual_evidence(residual_payload, residual_error)
    core = _core_blocker_evidence(core_payload, core_error)
    relax = _relax_slice_evidence(relax_payload, relax_error)
    witness = _witness_encoding(residual)
    pressure = _domain_pressure(residual, core, relax)
    checks = _checks(residual, core, relax, witness, pressure)
    classification = _classification(core, relax, checks)
    return {
        "metadata": {
            "source": POWER_COVERAGE_WITNESS_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "artifact_join_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "residual_optional_encoding": _display_path(project_root, residual_path),
            "power_coverage_core_blocker": _display_path(project_root, core_path),
            "power_coverage_relax_slice": _display_path(project_root, relax_path),
            "default_core_slice": _display_path(
                project_root,
                _resolve_path(project_root, DEFAULT_CORE_SLICE_PATH),
            ),
            "default_custom_core_slice": _display_path(
                project_root,
                _resolve_path(project_root, DEFAULT_CUSTOM_CORE_SLICE_PATH),
            ),
        },
        "candidate": {
            "key": residual.get("candidate_key") or core.get("candidate_key"),
        },
        "residual_optional_encoding": residual,
        "power_coverage_core_blocker": core,
        "power_coverage_relax_slice": relax,
        "witness_encoding": witness,
        "domain_pressure": pressure,
        "classification": classification,
        "recommendation": _recommendation(classification),
        "checks": checks,
    }


def render_phase3b_power_coverage_witness_audit_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    witness = _mapping(report.get("witness_encoding"))
    pressure = _mapping(report.get("domain_pressure"))
    lines = [
        "# Phase 3B Power Coverage Witness Audit",
        "",
        f"- Candidate: {candidate.get('key')}",
        "- Diagnostic semantics: artifact_join_not_proof_source",
        f"- Classification: {report.get('classification')}",
        f"- Encoding: {witness.get('encoding')}",
        f"- Powered slots: {witness.get('powered_slots')}",
        f"- Pole slots: {witness.get('pole_slots')}",
        f"- Witness indices: {witness.get('witness_indices')}",
        f"- Element constraints: {witness.get('element_constraints')}",
        f"- Element constraints per powered slot: {witness.get('element_constraints_per_powered_slot')}",
        f"- Cover-choice vars complete: {witness.get('cover_choice_vars_complete')}",
        f"- Core blocker classification: {pressure.get('core_blocker_classification')}",
        f"- Protocol lower-bound status: {pressure.get('no_protocol_lower_bound_core_status')}",
        f"- Linear relax combined status: {pressure.get('power_coverage_active_and_geometry_relaxed_status')}",
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


def render_phase3b_power_coverage_witness_audit_text(
    report: Mapping[str, Any],
) -> str:
    witness = _mapping(report.get("witness_encoding"))
    pressure = _mapping(report.get("domain_pressure"))
    lines = [
        "Phase 3B power coverage witness audit",
        "diagnostic_semantics=artifact_join_not_proof_source",
        f"classification={report.get('classification')}",
        f"encoding={witness.get('encoding')}",
        f"powered_slots={witness.get('powered_slots')}",
        f"pole_slots={witness.get('pole_slots')}",
        f"witness_indices={witness.get('witness_indices')}",
        f"element_constraints={witness.get('element_constraints')}",
        f"element_constraints_per_powered_slot={witness.get('element_constraints_per_powered_slot')}",
        f"cover_choice_vars_complete={witness.get('cover_choice_vars_complete')}",
        f"core_blocker_classification={pressure.get('core_blocker_classification')}",
        f"no_protocol_lower_bound_core_status={pressure.get('no_protocol_lower_bound_core_status')}",
        f"power_coverage_active_and_geometry_relaxed_status={pressure.get('power_coverage_active_and_geometry_relaxed_status')}",
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


def _residual_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    encoding = _mapping(payload.get("encoding"))
    proto = _mapping(encoding.get("proto"))
    gvi = _mapping(encoding.get("global_valid_inequalities"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == RESIDUAL_OPTIONAL_ENCODING_SOURCE,
        "candidate_key": candidate.get("key"),
        "master_slot_counts": dict(_mapping(encoding.get("master_slot_counts"))),
        "residual_optional_slots": dict(_mapping(encoding.get("residual_optional_slots"))),
        "power_coverage": dict(_mapping(encoding.get("power_coverage"))),
        "global_valid_inequalities": dict(gvi),
        "proto": {
            "variable_count": proto.get("variable_count"),
            "constraint_count": proto.get("constraint_count"),
            "constraint_kind_counts": dict(_mapping(proto.get("constraint_kind_counts"))),
            "variable_prefix_counts": dict(_mapping(proto.get("variable_prefix_counts"))),
        },
    }


def _core_blocker_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    matrix = _mapping(payload.get("combined_matrix"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == POWER_COVERAGE_CORE_BLOCKER_SOURCE,
        "candidate_key": candidate.get("key"),
        "classification": payload.get("classification"),
        "anchor_idx": matrix.get("anchor_idx"),
        "base_status": matrix.get("base_status"),
        "skip_power_coverage_core_status": matrix.get("skip_power_coverage_core_status"),
        "no_protocol_lower_bound_core_status": matrix.get(
            "no_protocol_lower_bound_core_status"
        ),
        "variant_statuses": dict(_mapping(matrix.get("variant_statuses"))),
    }


def _relax_slice_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    matrix = _mapping(payload.get("slice_matrix"))
    entries = [entry for entry in list(matrix.get("entries", [])) if isinstance(entry, Mapping)]
    by_variant = {str(entry.get("variant")): entry for entry in entries}
    def _entry_status(variant: str) -> Any:
        return _mapping(by_variant.get(variant)).get("status")

    def _removed_count(variant: str) -> int:
        return _int_or_zero(
            _mapping(by_variant.get(variant)).get(
                "relaxed_power_coverage_linear_constraint_count"
            )
        )

    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == (
            "phase3b_forced_anchor_model_slice_diagnostic_v1"
        ),
        "variant_statuses": {
            str(entry.get("variant")): str(entry.get("status")) for entry in entries
        },
        "removed_linear_constraint_counts": {
            "power_coverage_active_requirement_relaxed": _removed_count(
                "power_coverage_active_requirement_relaxed"
            ),
            "power_coverage_geometry_bounds_relaxed": _removed_count(
                "power_coverage_geometry_bounds_relaxed"
            ),
            "power_coverage_active_and_geometry_relaxed": _removed_count(
                "power_coverage_active_and_geometry_relaxed"
            ),
        },
        "base_status": _entry_status("base"),
        "active_requirement_relaxed_status": _entry_status(
            "power_coverage_active_requirement_relaxed"
        ),
        "geometry_bounds_relaxed_status": _entry_status(
            "power_coverage_geometry_bounds_relaxed"
        ),
        "active_and_geometry_relaxed_status": _entry_status(
            "power_coverage_active_and_geometry_relaxed"
        ),
    }


def _witness_encoding(residual: Mapping[str, Any]) -> Dict[str, Any]:
    power = _mapping(residual.get("power_coverage"))
    proto = _mapping(residual.get("proto"))
    variable_prefix_counts = _mapping(proto.get("variable_prefix_counts"))
    constraint_kind_counts = _mapping(proto.get("constraint_kind_counts"))
    powered_slots = _int_or_zero(power.get("powered_slots"))
    pole_slots = _int_or_zero(power.get("pole_slots"))
    witness_indices = _int_or_zero(power.get("witness_indices"))
    element_constraints = _int_or_zero(power.get("element_constraints"))
    cover_choice_counts = {
        prefix: _int_or_zero(variable_prefix_counts.get(prefix))
        for prefix in (
            "cover_choice_idx",
            "cover_choice_active",
            "cover_choice_x",
            "cover_choice_y",
        )
    }
    proto_element_constraints = _int_or_zero(constraint_kind_counts.get("element"))
    return {
        "representation": power.get("representation"),
        "encoding": power.get("encoding"),
        "powered_slots": powered_slots,
        "pole_slots": pole_slots,
        "cover_literals": _int_or_zero(power.get("cover_literals")),
        "witness_indices": witness_indices,
        "element_constraints": element_constraints,
        "radius": power.get("radius"),
        "witness_indices_per_powered_slot": _ratio(witness_indices, powered_slots),
        "element_constraints_per_powered_slot": _ratio(element_constraints, powered_slots),
        "expected_element_constraints": int(powered_slots * 3),
        "cover_choice_variable_counts": cover_choice_counts,
        "cover_choice_vars_complete": all(
            int(count) == int(powered_slots) for count in cover_choice_counts.values()
        )
        if powered_slots > 0
        else False,
        "proto_element_constraints": proto_element_constraints,
        "non_power_coverage_element_constraints": int(
            max(0, proto_element_constraints - element_constraints)
        ),
    }


def _domain_pressure(
    residual: Mapping[str, Any],
    core: Mapping[str, Any],
    relax: Mapping[str, Any],
) -> Dict[str, Any]:
    residual_slots = _mapping(residual.get("residual_optional_slots"))
    by_template = _mapping(residual_slots.get("by_template"))
    gvi = _mapping(residual.get("global_valid_inequalities"))
    optional_bounds = _mapping(gvi.get("optional_cardinality_bounds"))
    power_capacity = _mapping(gvi.get("power_capacity_summary"))
    return {
        "residual_slots_by_template": dict(by_template),
        "residual_slot_total": _int_or_zero(residual_slots.get("total")),
        "power_pole_residual_slots": _int_or_zero(by_template.get("power_pole")),
        "protocol_storage_box_residual_slots": _int_or_zero(
            by_template.get("protocol_storage_box")
        ),
        "power_pole_optional_bound": dict(_mapping(optional_bounds.get("power_pole"))),
        "protocol_storage_box_optional_bound": dict(
            _mapping(optional_bounds.get("protocol_storage_box"))
        ),
        "power_capacity_summary": dict(power_capacity),
        "core_blocker_classification": core.get("classification"),
        "base_status": core.get("base_status"),
        "skip_power_coverage_core_status": core.get("skip_power_coverage_core_status"),
        "no_protocol_lower_bound_core_status": core.get(
            "no_protocol_lower_bound_core_status"
        ),
        "power_coverage_active_requirement_relaxed_status": relax.get(
            "active_requirement_relaxed_status"
        ),
        "power_coverage_geometry_bounds_relaxed_status": relax.get(
            "geometry_bounds_relaxed_status"
        ),
        "power_coverage_active_and_geometry_relaxed_status": relax.get(
            "active_and_geometry_relaxed_status"
        ),
        "power_coverage_relaxed_linear_constraint_counts": dict(
            _mapping(relax.get("removed_linear_constraint_counts"))
        ),
    }


def _checks(
    residual: Mapping[str, Any],
    core: Mapping[str, Any],
    relax: Mapping[str, Any],
    witness: Mapping[str, Any],
    pressure: Mapping[str, Any],
) -> list[Dict[str, str]]:
    powered_slots = _int_or_zero(witness.get("powered_slots"))
    return [
        _check(
            "residual_encoding_present",
            "pass" if bool(residual.get("present", False)) else "fail",
            "residual encoding loaded"
            if bool(residual.get("present", False))
            else str(residual.get("load_error")),
        ),
        _check(
            "core_blocker_present",
            "pass" if bool(core.get("present", False)) else "fail",
            "power coverage core blocker loaded"
            if bool(core.get("present", False))
                else str(core.get("load_error")),
        ),
        _check(
            "power_coverage_relax_slice_present",
            "pass" if bool(relax.get("present", False)) else "skipped",
            "power-coverage linear relax slice loaded"
            if bool(relax.get("present", False))
            else str(relax.get("load_error")),
        ),
        _check(
            "geometric_witness_encoding_active",
            "pass"
            if witness.get("representation") == "coordinate_geometric"
            and witness.get("encoding") == "geometric_element_witness_v1"
            else "fail",
            f"representation={witness.get('representation')} encoding={witness.get('encoding')}",
        ),
        _check(
            "witness_count_matches_powered_slots",
            "pass"
            if powered_slots > 0
            and _int_or_zero(witness.get("witness_indices")) == powered_slots
            else "fail",
            f"witness_indices={witness.get('witness_indices')} powered_slots={powered_slots}",
        ),
        _check(
            "element_constraint_triplet_per_powered_slot",
            "pass"
            if powered_slots > 0
            and _int_or_zero(witness.get("element_constraints")) == powered_slots * 3
            else "fail",
            "element_constraints="
            f"{witness.get('element_constraints')} expected={powered_slots * 3}",
        ),
        _check(
            "cover_choice_variables_match_powered_slots",
            "pass" if bool(witness.get("cover_choice_vars_complete", False)) else "fail",
            f"cover_choice_counts={witness.get('cover_choice_variable_counts')}",
        ),
        _check(
            "power_pole_slots_match_witness_pole_slots",
            "pass"
            if _int_or_zero(pressure.get("power_pole_residual_slots"))
            == _int_or_zero(witness.get("pole_slots"))
            else "fail",
            "power_pole_residual_slots="
            f"{pressure.get('power_pole_residual_slots')} pole_slots={witness.get('pole_slots')}",
        ),
        _check(
            "geometric_encoding_uses_no_cover_literals",
            "pass" if _int_or_zero(witness.get("cover_literals")) == 0 else "fail",
            f"cover_literals={witness.get('cover_literals')}",
        ),
        _check(
            "core_blocker_terminal_without_power_coverage",
            "pass"
            if pressure.get("skip_power_coverage_core_status") in {"OPTIMAL", "FEASIBLE"}
            else "fail",
            f"skip_power_coverage_core_status={pressure.get('skip_power_coverage_core_status')}",
        ),
        _check(
            "protocol_lower_bound_not_primary",
            "pass"
            if pressure.get("no_protocol_lower_bound_core_status") == "UNKNOWN"
            else "skipped",
            f"no_protocol_lower_bound_core_status={pressure.get('no_protocol_lower_bound_core_status')}",
        ),
        _check(
            "partial_power_coverage_linear_relaxations_infeasible",
            "pass"
            if bool(relax.get("present", False))
            and pressure.get("power_coverage_active_requirement_relaxed_status")
            == "INFEASIBLE"
            and pressure.get("power_coverage_geometry_bounds_relaxed_status")
            == "INFEASIBLE"
            and pressure.get("power_coverage_active_and_geometry_relaxed_status")
            == "INFEASIBLE"
            else "skipped",
            "active="
            f"{pressure.get('power_coverage_active_requirement_relaxed_status')} "
            f"geometry={pressure.get('power_coverage_geometry_bounds_relaxed_status')} "
            f"combined={pressure.get('power_coverage_active_and_geometry_relaxed_status')}",
        ),
    ]


def _classification(
    core: Mapping[str, Any],
    relax: Mapping[str, Any],
    checks: list[Dict[str, str]],
) -> str:
    failed = {
        str(check.get("check_id"))
        for check in checks
        if str(check.get("status")) == "fail"
    }
    invariant_failures = failed.difference(
        {"core_blocker_terminal_without_power_coverage"}
    )
    if invariant_failures:
        return "power_coverage_witness_encoding_invariant_mismatch"
    if (
        bool(relax.get("present", False))
        and "MODEL_INVALID"
        in {
            str(relax.get("active_requirement_relaxed_status")),
            str(relax.get("geometry_bounds_relaxed_status")),
            str(relax.get("active_and_geometry_relaxed_status")),
        }
    ):
        return "power_coverage_partial_relaxation_model_invalid"
    if (
        bool(relax.get("present", False))
        and str(core.get("classification")).startswith("power_coverage_core_primary")
        and relax.get("active_requirement_relaxed_status") == "INFEASIBLE"
        and relax.get("geometry_bounds_relaxed_status") == "INFEASIBLE"
        and relax.get("active_and_geometry_relaxed_status") == "INFEASIBLE"
    ):
        return "power_coverage_full_skip_only_primary_blocker"
    if str(core.get("classification")).startswith("power_coverage_core_primary"):
        return "geometric_power_coverage_witness_primary_blocker"
    return "power_coverage_witness_audit_inconclusive"


def _recommendation(classification: str) -> str:
    if classification == "geometric_power_coverage_witness_primary_blocker":
        return (
            "The geometric witness encoding invariants are internally consistent, "
            "and the current forced-anchor slice becomes terminal only when the "
            "power-coverage core is removed. Next isolate witness-domain feasibility "
            "for anchor119 before any runtime or proof promotion."
        )
    if classification == "power_coverage_full_skip_only_primary_blocker":
        return (
            "The geometric witness encoding invariants are internally consistent, "
            "but relaxing only the witness active/geometry linear constraints stays "
            "INFEASIBLE while full skip_power_coverage is terminal. Next audit the "
            "additional power-capacity/global-valid-inequality layer skipped by "
            "skip_power_coverage before any runtime or proof promotion."
        )
    if classification == "power_coverage_partial_relaxation_model_invalid":
        return (
            "The geometric witness encoding invariants are internally consistent, "
            "but the local partial-relaxation slices produce MODEL_INVALID. Treat "
            "those mutated slices as unusable evidence and rely on the full "
            "skip_power_coverage core slice until a proof-safe relaxation method exists."
        )
    if classification == "power_coverage_witness_encoding_invariant_mismatch":
        return (
            "Power-coverage witness encoding invariants do not match the expected "
            "geometric_element_witness_v1 structure. Rebuild residual encoding and "
            "inspect model construction before running more solver experiments."
        )
    return "Power-coverage witness audit is inconclusive; rebuild core blocker and residual encoding artifacts."


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


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    if int(denominator) == 0:
        return None
    return float(numerator) / float(denominator)


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    normalized = str(status)
    if normalized not in {"pass", "fail", "skipped"}:
        raise ValueError(f"Unsupported check status: {status!r}")
    return {"check_id": str(check_id), "status": normalized, "detail": str(detail)}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
