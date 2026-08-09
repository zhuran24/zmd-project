from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

COORDINATE_GROUP_PRECHECK_CANDIDATE_SOURCE = (
    "phase3b_coordinate_group_precheck_candidate_v1"
)
GROUP_DELTA_SOURCE = "phase3b_coordinate_validation_group_delta_v1"
FIELD_CHANNEL_DELTA_SOURCE = "phase3b_coordinate_validation_field_channel_delta_v1"
DEFAULT_GROUP_DELTA_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_group_delta_anchor159/"
    "coordinate_validation_group_delta_anchor159.json"
)
DEFAULT_FIELD_CHANNEL_DELTA_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_field_channel_delta_anchor159_planter_buckwheat_ghost/"
    "field_channel_delta_anchor159_planter_buckwheat_ghost.json"
)


def build_phase3b_coordinate_group_precheck_candidate(
    project_root: Path,
    *,
    group_delta_path: Optional[Path] = None,
    field_channel_delta_path: Optional[Path] = None,
    target_group_id: str = "group::manufacturing_5x5::planter_buckwheat::9",
    target_field_variant: str = "x_y",
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    group_path = _resolve_path(
        project_root,
        group_delta_path if group_delta_path is not None else DEFAULT_GROUP_DELTA_PATH,
    )
    field_path = _resolve_path(
        project_root,
        field_channel_delta_path
        if field_channel_delta_path is not None
        else DEFAULT_FIELD_CHANNEL_DELTA_PATH,
    )
    group_report, group_error = _load_json_mapping(group_path)
    field_report, field_error = _load_json_mapping(field_path)
    group_meta = _mapping(group_report.get("metadata")) if group_report else {}
    field_meta = _mapping(field_report.get("metadata")) if field_report else {}
    group_candidate = _mapping(group_report.get("candidate")) if group_report else {}
    field_candidate = _mapping(field_report.get("candidate")) if field_report else {}
    candidate_key = str(group_candidate.get("key") or field_candidate.get("key") or "")
    anchor_idx = _first_int(group_candidate.get("anchor_idx"), field_candidate.get("anchor_idx"))

    group_entries = _entries(_mapping(group_report.get("delta")) if group_report else {})
    field_entries = _entries(
        _mapping(field_report.get("field_channel_delta")) if field_report else {}
    )
    target_group_entry = _find_group_entry(
        group_entries,
        group_id=str(target_group_id),
    )
    target_field_entry = _find_field_entry(
        field_entries,
        group_id=str(target_group_id),
        field_variant=str(target_field_variant),
    )
    single_field_entries = [
        entry
        for entry in field_entries
        if str(entry.get("group_id")) == str(target_group_id)
        and str(entry.get("field_variant")) in {"x", "y", "mode"}
    ]
    all_single_fields_nonterminal = all(
        _validation_status(entry) != "INFEASIBLE" for entry in single_field_entries
    )
    target_group_infeasible = _validation_status(target_group_entry) == "INFEASIBLE"
    target_field_infeasible = _validation_status(target_field_entry) == "INFEASIBLE"
    field_entry_uses_ghost = bool(target_field_entry.get("include_ghost", False))
    candidate_keys_match = (
        not group_candidate
        or not field_candidate
        or str(group_candidate.get("key")) == str(field_candidate.get("key"))
    )
    anchor_indices_match = (
        group_candidate.get("anchor_idx") is None
        or field_candidate.get("anchor_idx") is None
        or int(group_candidate.get("anchor_idx")) == int(field_candidate.get("anchor_idx"))
    )
    design_gate_passed = bool(
        group_report is not None
        and group_error is None
        and field_report is not None
        and field_error is None
        and group_meta.get("source") == GROUP_DELTA_SOURCE
        and field_meta.get("source") == FIELD_CHANNEL_DELTA_SOURCE
        and candidate_keys_match
        and anchor_indices_match
        and target_group_infeasible
        and target_field_infeasible
        and field_entry_uses_ghost
        and all_single_fields_nonterminal
    )
    checks = [
        _check(
            "group_delta_present",
            "pass" if group_report is not None and group_error is None else "fail",
            "group delta loaded"
            if group_report is not None and group_error is None
            else group_error or f"missing:{_display_path(project_root, group_path)}",
        ),
        _check(
            "group_delta_schema",
            "pass" if group_meta.get("source") == GROUP_DELTA_SOURCE else "fail",
            "supported group delta schema"
            if group_meta.get("source") == GROUP_DELTA_SOURCE
            else f"unsupported source:{group_meta.get('source')}",
        ),
        _check(
            "field_channel_delta_present",
            "pass" if field_report is not None and field_error is None else "fail",
            "field-channel delta loaded"
            if field_report is not None and field_error is None
            else field_error or f"missing:{_display_path(project_root, field_path)}",
        ),
        _check(
            "field_channel_delta_schema",
            "pass" if field_meta.get("source") == FIELD_CHANNEL_DELTA_SOURCE else "fail",
            "supported field-channel schema"
            if field_meta.get("source") == FIELD_CHANNEL_DELTA_SOURCE
            else f"unsupported source:{field_meta.get('source')}",
        ),
        _check(
            "candidate_keys_match",
            "pass" if candidate_keys_match else "fail",
            f"group={group_candidate.get('key')}; field={field_candidate.get('key')}",
        ),
        _check(
            "anchor_indices_match",
            "pass" if anchor_indices_match else "fail",
            f"group={group_candidate.get('anchor_idx')}; field={field_candidate.get('anchor_idx')}",
        ),
        _check(
            "target_group_infeasible",
            "pass" if target_group_infeasible else "fail",
            _entry_detail(target_group_entry, target_group_id),
        ),
        _check(
            "target_field_infeasible",
            "pass" if target_field_infeasible else "fail",
            _entry_detail(target_field_entry, target_field_variant),
        ),
        _check(
            "target_field_uses_ghost",
            "pass" if field_entry_uses_ghost else "fail",
            f"include_ghost={field_entry_uses_ghost}",
        ),
        _check(
            "single_fields_do_not_individually_explain",
            "pass" if all_single_fields_nonterminal else "fail",
            f"single_field_statuses={_status_by_field(single_field_entries)}",
        ),
        _check(
            "runtime_promotion_guard",
            "fail",
            "candidate is diagnostic-only; exact-safe runtime precheck is not implemented",
        ),
    ]
    return {
        "metadata": {
            "source": COORDINATE_GROUP_PRECHECK_CANDIDATE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "coordinate_group_precheck_candidate_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "group_delta": _display_path(project_root, group_path),
            "field_channel_delta": _display_path(project_root, field_path),
        },
        "candidate": {
            "key": candidate_key,
            "anchor_idx": anchor_idx,
            "ghost_rect": dict(_mapping(group_candidate.get("ghost_rect"))),
        },
        "target": {
            "group_id": str(target_group_id),
            "field_variant": str(target_field_variant),
            "group_entry": _compact_entry(target_group_entry),
            "field_entry": _compact_entry(target_field_entry),
            "single_field_entries": [_compact_entry(entry) for entry in single_field_entries],
        },
        "gate": {
            "design_gate_passed": bool(design_gate_passed),
            "runtime_promotion_ready": False,
            "recommendation": _recommendation(design_gate_passed),
            "promotion_requirements": [
                "Convert the diagnostic into a deterministic exact-safe predicate before runtime use.",
                "Add runtime tests covering non-triggering anchors and non-target groups.",
                "Rerun B5A in a fresh workspace after any runtime precheck change.",
                "Keep proof artifacts and release/frontdoor status unchanged.",
            ],
        },
        "checks": checks,
    }


def render_phase3b_coordinate_group_precheck_candidate_markdown(
    summary: Mapping[str, Any],
) -> str:
    candidate = _mapping(summary.get("candidate"))
    target = _mapping(summary.get("target"))
    gate = _mapping(summary.get("gate"))
    lines = [
        "# Phase 3B Coordinate Group Precheck Candidate",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Anchor: {candidate.get('anchor_idx')}",
        f"- Target group: {target.get('group_id')}",
        f"- Target field variant: {target.get('field_variant')}",
        f"- Design gate passed: {bool(gate.get('design_gate_passed', False))}",
        f"- Runtime promotion ready: {bool(gate.get('runtime_promotion_ready', False))}",
        f"- Recommendation: {gate.get('recommendation')}",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in list(summary.get("checks", [])):
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


def render_phase3b_coordinate_group_precheck_candidate_text(
    summary: Mapping[str, Any],
) -> str:
    candidate = _mapping(summary.get("candidate"))
    target = _mapping(summary.get("target"))
    gate = _mapping(summary.get("gate"))
    lines = [
        "Phase 3B coordinate group precheck candidate",
        f"candidate={candidate.get('key')}",
        f"anchor_idx={candidate.get('anchor_idx')}",
        "diagnostic_semantics=coordinate_group_precheck_candidate_not_proof_source",
        f"target_group={target.get('group_id')}",
        f"target_field_variant={target.get('field_variant')}",
        f"design_gate_passed={bool(gate.get('design_gate_passed', False))}",
        f"runtime_promotion_ready={bool(gate.get('runtime_promotion_ready', False))}",
        f"recommendation={gate.get('recommendation')}",
    ]
    for check in list(summary.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                f"check={check.get('check_id')}:{check.get('status')}:{check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _find_group_entry(entries: list[Mapping[str, Any]], *, group_id: str) -> Dict[str, Any]:
    for entry in entries:
        if (
            str(entry.get("variant")) == "ghost_plus_each_group"
            and str(entry.get("included_group_ids", [""])[0]) == str(group_id)
        ):
            return dict(entry)
    for entry in entries:
        if str(entry.get("included_group_ids", [""])[0]) == str(group_id):
            return dict(entry)
    return {}


def _find_field_entry(
    entries: list[Mapping[str, Any]],
    *,
    group_id: str,
    field_variant: str,
) -> Dict[str, Any]:
    for entry in entries:
        if (
            str(entry.get("group_id")) == str(group_id)
            and str(entry.get("field_variant")) == str(field_variant)
        ):
            return dict(entry)
    return {}


def _compact_entry(entry: Mapping[str, Any]) -> Dict[str, Any]:
    validation = _mapping(entry.get("validation"))
    return {
        "case_id": entry.get("case_id"),
        "variant": entry.get("variant"),
        "group_id": entry.get("group_id")
        or _first_string(entry.get("included_group_ids")),
        "field_variant": entry.get("field_variant"),
        "include_ghost": bool(entry.get("include_ghost", False)),
        "status": validation.get("status"),
        "reason": validation.get("reason"),
        "forced_slot_field_count": int(validation.get("forced_slot_field_count", 0)),
        "wall_time": float(validation.get("wall_time", 0.0)),
        "branches": int(validation.get("branches", 0)),
        "conflicts": int(validation.get("conflicts", 0)),
    }


def _entries(container: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        dict(entry)
        for entry in list(container.get("entries", []))
        if isinstance(entry, Mapping)
    ]


def _validation_status(entry: Mapping[str, Any]) -> str:
    return str(_mapping(entry.get("validation")).get("status") or "")


def _status_by_field(entries: list[Mapping[str, Any]]) -> Dict[str, str]:
    return {
        str(entry.get("field_variant")): _validation_status(entry)
        for entry in entries
    }


def _entry_detail(entry: Mapping[str, Any], fallback: str) -> str:
    if not entry:
        return f"missing:{fallback}"
    compact = _compact_entry(entry)
    return (
        f"status={compact.get('status')}; forced_slots={compact.get('forced_slot_field_count')}; "
        f"wall={compact.get('wall_time')}"
    )


def _recommendation(design_gate_passed: bool) -> str:
    if design_gate_passed:
        return (
            "Design evidence is sufficient for a guarded diagnostic/runtime-slice proposal, "
            "but runtime promotion remains blocked until an exact-safe predicate and tests exist."
        )
    return "Design gate is not satisfied; inspect failed checks before proposing a precheck."


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not path.exists():
        return None, f"missing:{path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(payload, Mapping):
        return None, "json root is not an object"
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


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    normalized = str(status)
    if normalized not in {"pass", "fail", "skipped"}:
        raise ValueError(f"invalid check status: {status}")
    return {
        "check_id": str(check_id),
        "status": normalized,
        "detail": str(detail),
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_int(*values: Any) -> Optional[int]:
    for value in values:
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _first_string(value: Any) -> Optional[str]:
    if isinstance(value, list) and value:
        return str(value[0])
    return None


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
