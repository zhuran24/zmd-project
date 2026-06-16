from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso
from src.search.phase3b.power_protocol.interaction import (
    DEFAULT_POWER_COVERAGE_ANCHOR_DELTA_PATH,
    DEFAULT_RESIDUAL_OPTIONAL_ENCODING_PATH,
)

POWER_COVERAGE_CORE_BLOCKER_SOURCE = "phase3b_power_coverage_core_blocker_v1"
FORCED_ANCHOR_MODEL_SLICE_SOURCE = "phase3b_forced_anchor_model_slice_diagnostic_v1"
POWER_COVERAGE_ANCHOR_DELTA_SOURCE = "phase3b_power_coverage_anchor_delta_v1"
RESIDUAL_OPTIONAL_ENCODING_SOURCE = "phase3b_residual_optional_encoding_inventory_v1"

DEFAULT_CORE_SLICE_PATH = Path(
    ".artifacts/phase3b_forced_anchor_model_slice_67x13_cap112_v3/"
    "forced_anchor_model_slice_67x13_anchor119_core5.json"
)
DEFAULT_CUSTOM_CORE_SLICE_PATH = Path(
    ".artifacts/phase3b_forced_anchor_model_slice_67x13_cap112_v3/"
    "forced_anchor_model_slice_67x13_anchor119_custom_core.json"
)


def build_phase3b_power_coverage_core_blocker_report(
    project_root: Path,
    *,
    core_slice_path: Optional[Path] = None,
    custom_core_slice_path: Optional[Path] = None,
    residual_optional_encoding_path: Optional[Path] = None,
    power_coverage_anchor_delta_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    core_path = _resolve_path(
        project_root,
        core_slice_path if core_slice_path is not None else DEFAULT_CORE_SLICE_PATH,
    )
    custom_path = _resolve_path(
        project_root,
        custom_core_slice_path
        if custom_core_slice_path is not None
        else DEFAULT_CUSTOM_CORE_SLICE_PATH,
    )
    residual_path = _resolve_path(
        project_root,
        residual_optional_encoding_path
        if residual_optional_encoding_path is not None
        else DEFAULT_RESIDUAL_OPTIONAL_ENCODING_PATH,
    )
    power_delta_path = _resolve_path(
        project_root,
        power_coverage_anchor_delta_path
        if power_coverage_anchor_delta_path is not None
        else DEFAULT_POWER_COVERAGE_ANCHOR_DELTA_PATH,
    )
    core_payload, core_error = _load_json_mapping(core_path)
    custom_payload, custom_error = _load_json_mapping(custom_path)
    residual_payload, residual_error = _load_json_mapping(residual_path)
    power_delta_payload, power_delta_error = _load_json_mapping(power_delta_path)

    core = _slice_evidence(core_payload, core_error)
    custom = _slice_evidence(custom_payload, custom_error)
    residual = _residual_evidence(residual_payload, residual_error)
    power_delta = _power_delta_evidence(power_delta_payload, power_delta_error)
    matrix = _combined_matrix(core, custom)
    classification = _classification(matrix, residual, power_delta)
    checks = _checks(core, custom, residual, power_delta, matrix, classification)
    return {
        "metadata": {
            "source": POWER_COVERAGE_CORE_BLOCKER_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "artifact_join_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "core_slice": _display_path(project_root, core_path),
            "custom_core_slice": _display_path(project_root, custom_path),
            "residual_optional_encoding": _display_path(project_root, residual_path),
            "power_coverage_anchor_delta": _display_path(project_root, power_delta_path),
        },
        "candidate": {
            "key": core.get("candidate_key")
            or custom.get("candidate_key")
            or residual.get("candidate_key")
            or power_delta.get("candidate_key")
        },
        "core_slice": core,
        "custom_core_slice": custom,
        "residual_optional_encoding": residual,
        "power_coverage_anchor_delta": power_delta,
        "combined_matrix": matrix,
        "classification": classification,
        "recommendation": _recommendation(classification),
        "checks": checks,
    }


def render_phase3b_power_coverage_core_blocker_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    matrix = _mapping(report.get("combined_matrix"))
    residual = _mapping(report.get("residual_optional_encoding"))
    power = _mapping(residual.get("power_coverage"))
    lines = [
        "# Phase 3B Power Coverage Core Blocker",
        "",
        f"- Candidate: {candidate.get('key')}",
        "- Diagnostic semantics: artifact_join_not_proof_source",
        f"- Classification: {report.get('classification')}",
        f"- Anchor: {matrix.get('anchor_idx')}",
        f"- Base status: {matrix.get('base_status')}",
        f"- Skip power coverage status: {matrix.get('skip_power_coverage_core_status')}",
        f"- No protocol lower-bound status: {matrix.get('no_protocol_lower_bound_core_status')}",
        f"- Powered slots: {power.get('powered_slots')}",
        f"- Pole slots: {power.get('pole_slots')}",
        f"- Witness indices: {power.get('witness_indices')}",
        f"- Element constraints: {power.get('element_constraints')}",
        f"- Recommendation: {report.get('recommendation')}",
        "",
        "## Variant Statuses",
        "",
        "| Variant | Status |",
        "| --- | --- |",
    ]
    for variant, status in sorted(_mapping(matrix.get("variant_statuses")).items()):
        lines.append(f"| {_markdown_cell(variant)} | {_markdown_cell(status)} |")
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


def render_phase3b_power_coverage_core_blocker_text(
    report: Mapping[str, Any],
) -> str:
    matrix = _mapping(report.get("combined_matrix"))
    residual = _mapping(report.get("residual_optional_encoding"))
    power = _mapping(residual.get("power_coverage"))
    lines = [
        "Phase 3B power coverage core blocker",
        "diagnostic_semantics=artifact_join_not_proof_source",
        f"classification={report.get('classification')}",
        f"anchor_idx={matrix.get('anchor_idx')}",
        f"base_status={matrix.get('base_status')}",
        f"skip_power_coverage_core_status={matrix.get('skip_power_coverage_core_status')}",
        f"no_protocol_lower_bound_core_status={matrix.get('no_protocol_lower_bound_core_status')}",
        f"powered_slots={power.get('powered_slots')}",
        f"pole_slots={power.get('pole_slots')}",
        f"witness_indices={power.get('witness_indices')}",
        f"element_constraints={power.get('element_constraints')}",
        f"recommendation={report.get('recommendation')}",
    ]
    for variant, status in sorted(_mapping(matrix.get("variant_statuses")).items()):
        lines.append(f"variant_status {variant}={status}")
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check "
                f"id={check.get('check_id')} "
                f"status={check.get('status')} "
                f"detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _slice_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    matrix = _mapping(payload.get("slice_matrix"))
    entries = [entry for entry in list(matrix.get("entries", [])) if isinstance(entry, Mapping)]
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FORCED_ANCHOR_MODEL_SLICE_SOURCE,
        "candidate_key": candidate.get("key"),
        "diagnostic_findings": [
            str(item) for item in list(matrix.get("diagnostic_findings", []))
        ],
        "variant_statuses": _variant_statuses(entries),
        "anchor_indices": sorted(
            {
                int(entry.get("anchor_idx"))
                for entry in entries
                if _int_or_none(entry.get("anchor_idx")) is not None
            }
        ),
        "status_counts_by_variant": dict(
            _mapping(matrix.get("status_counts_by_variant"))
        ),
    }


def _residual_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    encoding = _mapping(payload.get("encoding"))
    residual = _mapping(encoding.get("residual_optional_slots"))
    power = _mapping(encoding.get("power_coverage"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == RESIDUAL_OPTIONAL_ENCODING_SOURCE,
        "candidate_key": candidate.get("key"),
        "residual_slots_by_template": dict(_mapping(residual.get("by_template"))),
        "residual_slot_total": int(residual.get("total", 0)),
        "power_coverage": {
            "representation": power.get("representation"),
            "encoding": power.get("encoding"),
            "powered_slots": int(power.get("powered_slots", 0)),
            "pole_slots": int(power.get("pole_slots", 0)),
            "witness_indices": int(power.get("witness_indices", 0)),
            "element_constraints": int(power.get("element_constraints", 0)),
            "radius": power.get("radius"),
        },
    }


def _power_delta_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    delta = _mapping(payload.get("delta"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == POWER_COVERAGE_ANCHOR_DELTA_SOURCE,
        "candidate_key": candidate.get("key"),
        "power_family_changed_count": int(delta.get("power_family_changed_count", 0)),
        "top_power_family_deltas": [
            dict(entry)
            for entry in list(delta.get("top_power_family_deltas", []))
            if isinstance(entry, Mapping)
        ],
        "optional_template_deltas": [
            dict(entry)
            for entry in list(delta.get("optional_template_deltas", []))
            if isinstance(entry, Mapping)
        ],
    }


def _combined_matrix(
    core: Mapping[str, Any],
    custom: Mapping[str, Any],
) -> Dict[str, Any]:
    variant_statuses: Dict[str, str] = {}
    variant_statuses.update(
        {str(k): str(v) for k, v in _mapping(core.get("variant_statuses")).items()}
    )
    variant_statuses.update(
        {str(k): str(v) for k, v in _mapping(custom.get("variant_statuses")).items()}
    )
    anchor_indices = [
        int(value)
        for value in [
            *list(core.get("anchor_indices", [])),
            *list(custom.get("anchor_indices", [])),
        ]
        if _int_or_none(value) is not None
    ]
    anchor_idx = sorted(set(anchor_indices))[0] if anchor_indices else None
    return {
        "anchor_idx": anchor_idx,
        "variant_statuses": variant_statuses,
        "base_status": variant_statuses.get("base"),
        "residual_all_inactive_status": variant_statuses.get("residual_all_inactive"),
        "protocol_boxes_inactive_status": variant_statuses.get("protocol_boxes_inactive"),
        "power_poles_inactive_status": variant_statuses.get("power_poles_inactive"),
        "skip_power_coverage_core_status": variant_statuses.get(
            "skip_power_coverage_core"
        ),
        "no_protocol_lower_bound_core_status": variant_statuses.get(
            "no_protocol_lower_bound_core"
        ),
        "skip_power_coverage_no_protocol_lower_bound_core_status": variant_statuses.get(
            "skip_power_coverage_no_protocol_lower_bound_core"
        ),
        "skip_power_coverage_no_protocol_lower_bound_core_residual_all_inactive_status": (
            variant_statuses.get(
                "skip_power_coverage_no_protocol_lower_bound_core_residual_all_inactive"
            )
        ),
        "diagnostic_findings": _dedupe(
            [
                *[str(item) for item in list(core.get("diagnostic_findings", []))],
                *[str(item) for item in list(custom.get("diagnostic_findings", []))],
            ]
        ),
    }


def _classification(
    matrix: Mapping[str, Any],
    residual: Mapping[str, Any],
    power_delta: Mapping[str, Any],
) -> str:
    if (
        matrix.get("base_status") == "UNKNOWN"
        and matrix.get("skip_power_coverage_core_status") in {"OPTIMAL", "FEASIBLE"}
        and int(_mapping(residual.get("power_coverage")).get("element_constraints", 0)) > 0
    ):
        if matrix.get("no_protocol_lower_bound_core_status") == "UNKNOWN":
            return "power_coverage_core_primary_protocol_lower_bound_not_primary"
        return "power_coverage_core_primary_blocker"
    if int(power_delta.get("power_family_changed_count", 0)) > 0:
        return "power_coverage_family_delta_present_without_terminal_core_slice"
    return "power_coverage_core_blocker_inconclusive"


def _recommendation(classification: str) -> str:
    if classification == "power_coverage_core_primary_protocol_lower_bound_not_primary":
        return (
            "The current forced-anchor slice becomes terminal only when power "
            "coverage is removed, while removing the protocol-storage lower bound "
            "alone remains UNKNOWN. Focus the next diagnostic on geometric power "
            "coverage witness/domain encoding, not family-bound injection."
        )
    if classification == "power_coverage_core_primary_blocker":
        return (
            "The current forced-anchor slice becomes terminal when power coverage "
            "is removed. Build a smaller power-coverage witness/domain audit before "
            "rerunning B5A."
        )
    if classification == "power_coverage_family_delta_present_without_terminal_core_slice":
        return (
            "Power-family deltas are present, but the refreshed core slice does not "
            "yet show a terminal power-coverage relaxation. Rebuild the core slice "
            "before changing runtime behavior."
        )
    return "Power-coverage blocker report is inconclusive; rebuild the slice artifacts."


def _checks(
    core: Mapping[str, Any],
    custom: Mapping[str, Any],
    residual: Mapping[str, Any],
    power_delta: Mapping[str, Any],
    matrix: Mapping[str, Any],
    classification: str,
) -> list[Dict[str, str]]:
    return [
        _check(
            "core_slice_present",
            "pass" if bool(core.get("present", False)) else "fail",
            "core slice loaded" if bool(core.get("present", False)) else str(core.get("load_error")),
        ),
        _check(
            "custom_core_slice_present",
            "pass" if bool(custom.get("present", False)) else "fail",
            "custom core slice loaded"
            if bool(custom.get("present", False))
            else str(custom.get("load_error")),
        ),
        _check(
            "residual_encoding_present",
            "pass" if bool(residual.get("present", False)) else "fail",
            "residual encoding loaded"
            if bool(residual.get("present", False))
            else str(residual.get("load_error")),
        ),
        _check(
            "power_delta_present",
            "pass" if bool(power_delta.get("present", False)) else "fail",
            "power delta loaded"
            if bool(power_delta.get("present", False))
            else str(power_delta.get("load_error")),
        ),
        _check(
            "base_reproduces_zero_branch_unknown",
            "pass" if matrix.get("base_status") == "UNKNOWN" else "fail",
            f"base_status={matrix.get('base_status')}",
        ),
        _check(
            "skip_power_coverage_terminal",
            "pass"
            if matrix.get("skip_power_coverage_core_status") in {"OPTIMAL", "FEASIBLE"}
            else "fail",
            f"skip_power_coverage_core_status={matrix.get('skip_power_coverage_core_status')}",
        ),
        _check(
            "protocol_lower_bound_not_primary",
            "pass"
            if matrix.get("no_protocol_lower_bound_core_status") == "UNKNOWN"
            else "skipped",
            f"no_protocol_lower_bound_core_status={matrix.get('no_protocol_lower_bound_core_status')}",
        ),
        _check(
            "classification_terminal",
            "pass"
            if str(classification).startswith("power_coverage_core_primary")
            else "fail",
            f"classification={classification}",
        ),
    ]


def _variant_statuses(entries: list[Mapping[str, Any]]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for entry in entries:
        variant = entry.get("variant")
        if variant is None:
            continue
        result[str(variant)] = str(entry.get("status"))
    return result


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


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
