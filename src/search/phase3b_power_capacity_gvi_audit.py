from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso
from src.search.phase3b_power_coverage_witness_audit import (
    DEFAULT_POWER_COVERAGE_WITNESS_AUDIT_PATH,
)
from src.search.phase3b_power_protocol_interaction import (
DEFAULT_RESIDUAL_OPTIONAL_ENCODING_PATH,
)

POWER_CAPACITY_GVI_AUDIT_SOURCE = "phase3b_power_capacity_gvi_audit_v1"
RESIDUAL_OPTIONAL_ENCODING_SOURCE = "phase3b_residual_optional_encoding_inventory_v1"
POWER_COVERAGE_WITNESS_AUDIT_SOURCE = "phase3b_power_coverage_witness_audit_v1"
FORCED_ANCHOR_MODEL_SLICE_SOURCE = "phase3b_forced_anchor_model_slice_diagnostic_v1"

DEFAULT_POWER_CAPACITY_GVI_RELAX_SLICE_PATH = Path(
    ".artifacts/phase3b_forced_anchor_model_slice_67x13_power_capacity_gvi_relax/"
    "forced_anchor_model_slice_67x13_anchor119_power_capacity_gvi_relax.json"
)


def build_phase3b_power_capacity_gvi_audit(
    project_root: Path,
    *,
    residual_optional_encoding_path: Optional[Path] = None,
    power_coverage_witness_audit_path: Optional[Path] = None,
    power_capacity_gvi_relax_slice_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    residual_path = _resolve_path(
        project_root,
        residual_optional_encoding_path
        if residual_optional_encoding_path is not None
        else DEFAULT_RESIDUAL_OPTIONAL_ENCODING_PATH,
    )
    witness_path = _resolve_path(
        project_root,
        power_coverage_witness_audit_path
        if power_coverage_witness_audit_path is not None
        else DEFAULT_POWER_COVERAGE_WITNESS_AUDIT_PATH,
    )
    relax_path = _resolve_path(
        project_root,
        power_capacity_gvi_relax_slice_path
        if power_capacity_gvi_relax_slice_path is not None
        else DEFAULT_POWER_CAPACITY_GVI_RELAX_SLICE_PATH,
    )
    residual_payload, residual_error = _load_json_mapping(residual_path)
    witness_payload, witness_error = _load_json_mapping(witness_path)
    relax_payload, relax_error = _load_json_mapping(relax_path)
    residual = _residual_evidence(residual_payload, residual_error)
    witness = _witness_evidence(witness_payload, witness_error)
    relax = _relax_slice_evidence(relax_payload, relax_error)
    capacity = _capacity_gvi_evidence(residual)
    classification = _classification(residual, witness, relax, capacity)
    checks = _checks(residual, witness, relax, capacity, classification)
    return {
        "metadata": {
            "source": POWER_CAPACITY_GVI_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "artifact_join_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "residual_optional_encoding": _display_path(project_root, residual_path),
            "power_coverage_witness_audit": _display_path(project_root, witness_path),
            "power_capacity_gvi_relax_slice": _display_path(project_root, relax_path),
        },
        "candidate": {
            "key": residual.get("candidate_key") or witness.get("candidate_key"),
        },
        "residual_optional_encoding": residual,
        "power_coverage_witness_audit": witness,
        "power_capacity_gvi_relax_slice": relax,
        "power_capacity_gvi": capacity,
        "classification": classification,
        "recommendation": _recommendation(classification),
        "checks": checks,
    }


def render_phase3b_power_capacity_gvi_audit_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    capacity = _mapping(report.get("power_capacity_gvi"))
    witness = _mapping(report.get("power_coverage_witness_audit"))
    relax = _mapping(report.get("power_capacity_gvi_relax_slice"))
    lines = [
        "# Phase 3B Power Capacity GVI Audit",
        "",
        f"- Candidate: {candidate.get('key')}",
        "- Diagnostic semantics: artifact_join_not_proof_source",
        f"- Classification: {report.get('classification')}",
        f"- Witness classification: {witness.get('classification')}",
        f"- Power capacity applied: {capacity.get('power_capacity_applied')}",
        f"- Lower-bound count: {capacity.get('lower_bound_count')}",
        f"- Aggregated nonzero terms: {capacity.get('aggregated_nonzero_terms')}",
        f"- Raw nonzero terms: {capacity.get('raw_nonzero_terms')}",
        f"- Family count: {capacity.get('family_count')}",
        f"- All GVI relaxed status: {relax.get('all_relaxed_status')}",
        f"- Recommendation: {report.get('recommendation')}",
        "",
        "## Lower Bounds",
        "",
        "| Template | Demand | Nonzero Poles |",
        "| --- | --- | --- |",
    ]
    for row in list(capacity.get("lower_bounds", [])):
        if isinstance(row, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(row.get("template")),
                        _markdown_cell(row.get("demand")),
                        _markdown_cell(row.get("nonzero_poles")),
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


def render_phase3b_power_capacity_gvi_audit_text(
    report: Mapping[str, Any],
) -> str:
    capacity = _mapping(report.get("power_capacity_gvi"))
    witness = _mapping(report.get("power_coverage_witness_audit"))
    relax = _mapping(report.get("power_capacity_gvi_relax_slice"))
    lines = [
        "Phase 3B power capacity GVI audit",
        "diagnostic_semantics=artifact_join_not_proof_source",
        f"classification={report.get('classification')}",
        f"witness_classification={witness.get('classification')}",
        f"power_capacity_applied={capacity.get('power_capacity_applied')}",
        f"lower_bound_count={capacity.get('lower_bound_count')}",
        f"aggregated_nonzero_terms={capacity.get('aggregated_nonzero_terms')}",
        f"raw_nonzero_terms={capacity.get('raw_nonzero_terms')}",
        f"family_count={capacity.get('family_count')}",
        f"all_gvi_relaxed_status={relax.get('all_relaxed_status')}",
        f"recommendation={report.get('recommendation')}",
    ]
    for row in list(capacity.get("lower_bounds", [])):
        if isinstance(row, Mapping):
            lines.append(
                "lower_bound "
                f"template={row.get('template')} "
                f"demand={row.get('demand')} "
                f"nonzero_poles={row.get('nonzero_poles')}"
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


def _residual_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    encoding = _mapping(payload.get("encoding"))
    gvi = _mapping(encoding.get("global_valid_inequalities"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == RESIDUAL_OPTIONAL_ENCODING_SOURCE,
        "candidate_key": candidate.get("key"),
        "global_valid_inequalities": dict(gvi),
    }


def _witness_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    pressure = _mapping(payload.get("domain_pressure"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == POWER_COVERAGE_WITNESS_AUDIT_SOURCE,
        "candidate_key": candidate.get("key"),
        "classification": payload.get("classification"),
        "skip_power_coverage_core_status": pressure.get(
            "skip_power_coverage_core_status"
        ),
        "partial_relax_combined_status": pressure.get(
            "power_coverage_active_and_geometry_relaxed_status"
        ),
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

    def _status(variant: str) -> Any:
        return _mapping(by_variant.get(variant)).get("status")

    def _removed_count(variant: str) -> int:
        return _int_or_zero(
            _mapping(by_variant.get(variant)).get(
                "relaxed_power_capacity_gvi_constraint_count"
            )
        )

    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FORCED_ANCHOR_MODEL_SLICE_SOURCE,
        "protocol_relaxed_status": _status(
            "power_capacity_gvi_protocol_storage_box_relaxed"
        ),
        "mandatory_relaxed_status": _status(
            "power_capacity_gvi_mandatory_templates_relaxed"
        ),
        "all_relaxed_status": _status("power_capacity_gvi_all_relaxed"),
        "removed_constraint_counts": {
            "protocol": _removed_count(
                "power_capacity_gvi_protocol_storage_box_relaxed"
            ),
            "mandatory": _removed_count(
                "power_capacity_gvi_mandatory_templates_relaxed"
            ),
            "all": _removed_count("power_capacity_gvi_all_relaxed"),
        },
    }


def _capacity_gvi_evidence(residual: Mapping[str, Any]) -> Dict[str, Any]:
    gvi = _mapping(residual.get("global_valid_inequalities"))
    applied = [entry for entry in list(gvi.get("applied", [])) if isinstance(entry, Mapping)]
    lower_bounds = [
        {
            "template": str(entry.get("template")),
            "demand": _int_or_zero(entry.get("demand")),
            "nonzero_poles": _int_or_zero(entry.get("nonzero_poles")),
        }
        for entry in applied
        if str(entry.get("type")) == "power_capacity_lower_bound"
    ]
    powered_demands = {
        str(tpl): _int_or_zero(demand)
        for tpl, demand in sorted(_mapping(gvi.get("powered_template_demands")).items())
    }
    aggregate = _mapping(gvi.get("aggregated_power_capacity_terms"))
    summary = _mapping(gvi.get("power_capacity_summary"))
    families = _mapping(gvi.get("power_capacity_families"))
    family_rows = [
        dict(row)
        for row in list(families.get("families", []))
        if isinstance(row, Mapping)
    ]
    return {
        "applied_entries_present": bool(applied),
        "power_capacity_applied": bool(summary.get("applied", False))
        or bool(families.get("applied", False)),
        "powered_template_demands": powered_demands,
        "lower_bound_count": int(len(lower_bounds)),
        "lower_bounds": lower_bounds,
        "raw_nonzero_terms": _int_or_zero(aggregate.get("raw_nonzero_terms")),
        "aggregated_nonzero_terms": _int_or_zero(
            aggregate.get("aggregated_nonzero_terms")
        ),
        "family_count": _int_or_zero(
            summary.get("family_count", families.get("family_count"))
        ),
        "raw_pole_count": _int_or_zero(
            summary.get("raw_pole_count", families.get("raw_pole_count"))
        ),
        "shell_pair_count": _int_or_zero(
            summary.get("shell_pair_count", families.get("shell_pair_count"))
        ),
        "compact_signature_class_count": _int_or_zero(
            summary.get(
                "compact_signature_class_count",
                families.get("compact_signature_class_count"),
            )
        ),
        "family_rows_present": bool(family_rows),
        "family_rows_sample": family_rows[:5],
    }


def _classification(
    residual: Mapping[str, Any],
    witness: Mapping[str, Any],
    relax: Mapping[str, Any],
    capacity: Mapping[str, Any],
) -> str:
    if not bool(residual.get("present", False)):
        return "power_capacity_gvi_missing_residual_encoding"
    if not bool(witness.get("present", False)):
        return "power_capacity_gvi_missing_witness_audit"
    if (
        bool(relax.get("present", False))
        and "MODEL_INVALID"
        in {
            str(relax.get("protocol_relaxed_status")),
            str(relax.get("mandatory_relaxed_status")),
            str(relax.get("all_relaxed_status")),
        }
    ):
        return "power_capacity_gvi_relaxation_model_invalid"
    if (
        bool(relax.get("present", False))
        and witness.get("classification") == "power_coverage_full_skip_only_primary_blocker"
        and bool(capacity.get("power_capacity_applied", False))
        and int(capacity.get("lower_bound_count", 0)) > 0
        and relax.get("all_relaxed_status") == "INFEASIBLE"
        and int(_mapping(relax.get("removed_constraint_counts")).get("all", 0))
        >= int(capacity.get("lower_bound_count", 0))
    ):
        return "power_capacity_gvi_lower_bounds_not_sufficient"
    if (
        witness.get("classification") == "power_coverage_full_skip_only_primary_blocker"
        and bool(capacity.get("power_capacity_applied", False))
        and int(capacity.get("lower_bound_count", 0)) > 0
    ):
        return "power_capacity_gvi_full_skip_primary_suspect"
    if (
        witness.get("classification") == "power_coverage_full_skip_only_primary_blocker"
        and bool(capacity.get("power_capacity_applied", False))
    ):
        return "power_capacity_gvi_artifact_needs_refresh"
    return "power_capacity_gvi_inconclusive"


def _recommendation(classification: str) -> str:
    if classification == "power_capacity_gvi_lower_bounds_not_sufficient":
        return (
            "All recorded power-capacity lower-bound rows were relaxed and the "
            "forced-anchor slice remains INFEASIBLE, while full skip_power_coverage "
            "is terminal. The next suspect is the remaining power-family count, "
            "family-membership, or ghost-conditioned upper-bound layer, not the "
            "template lower-bound rows alone."
        )
    if classification == "power_capacity_gvi_relaxation_model_invalid":
        return (
            "The template-specific power-capacity GVI relaxation slices produce "
            "MODEL_INVALID, so they are unusable as feasibility evidence. Keep the "
            "full skip_power_coverage core slice as the reliable blocker signal and "
            "build a safer relaxation method before isolating individual GVI rows."
        )
    if classification == "power_capacity_gvi_full_skip_primary_suspect":
        return (
            "Full skip_power_coverage is terminal while partial witness relaxations "
            "are INFEASIBLE, and residual encoding records power-capacity lower "
            "bounds. Next isolate these GVI lower bounds by template in a forced-anchor "
            "diagnostic slice before any runtime or proof promotion."
        )
    if classification == "power_capacity_gvi_artifact_needs_refresh":
        return (
            "Power-capacity appears active, but the residual encoding artifact lacks "
            "the applied lower-bound rows. Rebuild residual_optional_encoding before "
            "drawing blocker conclusions."
        )
    if classification == "power_capacity_gvi_missing_residual_encoding":
        return "Residual optional encoding artifact is missing; rebuild it before this audit."
    if classification == "power_capacity_gvi_missing_witness_audit":
        return "Power-coverage witness audit is missing; rebuild it before this audit."
    return "Power-capacity GVI audit is inconclusive; rebuild upstream blocker artifacts."


def _checks(
    residual: Mapping[str, Any],
    witness: Mapping[str, Any],
    relax: Mapping[str, Any],
    capacity: Mapping[str, Any],
    classification: str,
) -> list[Dict[str, str]]:
    return [
        _check(
            "residual_encoding_present",
            "pass" if bool(residual.get("present", False)) else "fail",
            "residual encoding loaded"
            if bool(residual.get("present", False))
            else str(residual.get("load_error")),
        ),
        _check(
            "witness_audit_present",
            "pass" if bool(witness.get("present", False)) else "fail",
            "witness audit loaded"
            if bool(witness.get("present", False))
                else str(witness.get("load_error")),
        ),
        _check(
            "power_capacity_gvi_relax_slice_present",
            "pass" if bool(relax.get("present", False)) else "skipped",
            "GVI relax slice loaded"
            if bool(relax.get("present", False))
            else str(relax.get("load_error")),
        ),
        _check(
            "full_skip_only_blocker",
            "pass"
            if witness.get("classification")
            == "power_coverage_full_skip_only_primary_blocker"
            else "fail",
            f"witness_classification={witness.get('classification')}",
        ),
        _check(
            "power_capacity_applied",
            "pass" if bool(capacity.get("power_capacity_applied", False)) else "fail",
            f"power_capacity_applied={capacity.get('power_capacity_applied')}",
        ),
        _check(
            "power_capacity_lower_bounds_present",
            "pass" if int(capacity.get("lower_bound_count", 0)) > 0 else "fail",
            f"lower_bound_count={capacity.get('lower_bound_count')}",
        ),
        _check(
            "aggregated_terms_present",
            "pass"
            if int(capacity.get("aggregated_nonzero_terms", 0)) > 0
            else "fail",
            f"aggregated_nonzero_terms={capacity.get('aggregated_nonzero_terms')}",
        ),
        _check(
            "all_lower_bound_rows_relaxed_but_infeasible",
            "pass"
            if bool(relax.get("present", False))
            and relax.get("all_relaxed_status") == "INFEASIBLE"
            and int(_mapping(relax.get("removed_constraint_counts")).get("all", 0))
            >= int(capacity.get("lower_bound_count", 0))
            else "skipped",
            "all_status="
            f"{relax.get('all_relaxed_status')} removed="
            f"{_mapping(relax.get('removed_constraint_counts')).get('all')} "
            f"lower_bound_count={capacity.get('lower_bound_count')}",
        ),
        _check(
            "gvi_relaxation_model_valid",
            "fail"
            if bool(relax.get("present", False))
            and "MODEL_INVALID"
            in {
                str(relax.get("protocol_relaxed_status")),
                str(relax.get("mandatory_relaxed_status")),
                str(relax.get("all_relaxed_status")),
            }
            else "pass",
            "protocol="
            f"{relax.get('protocol_relaxed_status')} mandatory="
            f"{relax.get('mandatory_relaxed_status')} all={relax.get('all_relaxed_status')}",
        ),
        _check(
            "classification_actionable",
            "pass"
            if classification
            in {
                "power_capacity_gvi_full_skip_primary_suspect",
                "power_capacity_gvi_lower_bounds_not_sufficient",
            }
            else "fail",
            f"classification={classification}",
        ),
    ]


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
