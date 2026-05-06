from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

from src.search.exact_campaign import now_iso
from src.search.phase3b_coordinate_validation_group_delta import _mapping

PHASE3B_DIRECT_EQUALITY_CORE_GEOMETRY_SOURCE = (
    "phase3b_direct_equality_core_geometry_v1"
)


def build_phase3b_direct_equality_core_geometry_report(
    project_root: Path,
    *,
    core_paths: Sequence[Path],
    candidate_placements_path: Path | None = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    started = time.perf_counter()
    placements_path = (
        Path(candidate_placements_path)
        if candidate_placements_path is not None
        else project_root / "data" / "preprocessed" / "candidate_placements.json"
    )
    placements_path = _resolve_path(project_root, placements_path)
    pools = _load_facility_pools(placements_path)

    entries = []
    for core_path in core_paths:
        resolved_core_path = _resolve_path(project_root, Path(core_path))
        entries.append(_build_core_entry(project_root, resolved_core_path, pools))

    return {
        "metadata": {
            "source": PHASE3B_DIRECT_EQUALITY_CORE_GEOMETRY_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_geometry_explanation_not_proof_source",
            "solver_invoked": False,
        },
        "paths": {
            "project_root": str(project_root),
            "candidate_placements": str(placements_path),
            "core_paths": [str(_resolve_path(project_root, Path(path))) for path in core_paths],
        },
        "entries": entries,
        "summary": _summary(entries),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "checks": _checks(entries),
    }


def render_phase3b_direct_equality_core_geometry_markdown(report: Mapping[str, Any]) -> str:
    summary = _mapping(report.get("summary"))
    lines = [
        "# Phase 3B Direct-Equality Core Geometry",
        "",
        "- Diagnostic semantics: no_solve_geometry_explanation_not_proof_source",
        "- Solver invoked: false",
        f"- Core count: {summary.get('core_count')}",
        f"- Final key count: {summary.get('final_key_count')}",
        f"- Field counts: `{summary.get('field_counts')}`",
        f"- Complete pose equality keys: {summary.get('complete_pose_equality_key_count')}",
        "",
        "## Core Entries",
        "",
    ]
    for entry in list(report.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        core = _mapping(entry.get("core"))
        lines.extend(
            [
                f"### {_markdown_cell(core.get('name') or core.get('file_name'))}",
                "",
                f"- Path: `{entry.get('path')}`",
                f"- Candidate: `{core.get('candidate_key')}` / anchor `{core.get('anchor_idx')}`",
                f"- Group: `{core.get('group_id')}`",
                f"- Final key count: `{core.get('final_key_count')}`",
                f"- Field counts: `{core.get('field_counts')}`",
                f"- Slot counts: `{core.get('slot_counts')}`",
                "",
                "| Slot | Solution | Field | Forced | Source Pose | Pose Tuple | Pose Overlaps Ghost | Semantics |",
                "| ---: | --- | --- | ---: | --- | --- | --- | --- |",
            ]
        )
        for label in list(entry.get("labels", [])):
            if not isinstance(label, Mapping):
                continue
            pose = _mapping(label.get("source_pose"))
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(label.get("slot_index")),
                        _markdown_cell(label.get("solution_id")),
                        _markdown_cell(label.get("field")),
                        _markdown_cell(label.get("forced_value")),
                        _markdown_cell(pose.get("pose_id")),
                        _markdown_cell(label.get("pose_tuple")),
                        _markdown_cell(label.get("source_pose_overlaps_ghost")),
                        _markdown_cell(label.get("forced_semantics")),
                    ]
                )
                + " |"
            )
        interpretation = list(entry.get("interpretation", []))
        if interpretation:
            lines.extend(["", "Interpretation:"])
            for item in interpretation:
                lines.append(f"- {item}")
        lines.append("")
    lines.extend(["## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
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


def render_phase3b_direct_equality_core_geometry_text(report: Mapping[str, Any]) -> str:
    summary = _mapping(report.get("summary"))
    lines = [
        "Phase 3B direct-equality core geometry",
        "diagnostic_semantics=no_solve_geometry_explanation_not_proof_source",
        "solver_invoked=false",
        f"core_count={summary.get('core_count')}",
        f"final_key_count={summary.get('final_key_count')}",
        f"field_counts={summary.get('field_counts')}",
    ]
    for entry in list(report.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        core = _mapping(entry.get("core"))
        lines.append(
            f"core name={core.get('name') or core.get('file_name')} "
            f"group={core.get('group_id')} final_key_count={core.get('final_key_count')}"
        )
        for label in list(entry.get("labels", [])):
            if isinstance(label, Mapping):
                lines.append(
                    "label "
                    f"slot={label.get('slot_index')} "
                    f"solution={label.get('solution_id')} "
                    f"field={label.get('field')} "
                    f"forced={label.get('forced_value')} "
                    f"pose_tuple={label.get('pose_tuple')} "
                    f"source_pose_overlaps_ghost={label.get('source_pose_overlaps_ghost')} "
                    f"semantics={label.get('forced_semantics')}"
                )
    return "\n".join(lines) + "\n"


def _build_core_entry(
    project_root: Path,
    core_path: Path,
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Dict[str, Any]:
    core_payload = _load_json(core_path)
    core = _core_summary(core_path, core_payload)
    labels = _extract_labels(core_payload)
    ghost = _candidate_ghost(core_payload)
    enriched = [_enrich_label(label, pools, ghost) for label in labels]
    return {
        "path": _display_path(project_root, core_path),
        "core": core,
        "ghost": ghost,
        "labels": enriched,
        "interpretation": _interpret_labels(enriched, ghost),
    }


def _core_summary(core_path: Path, payload: Mapping[str, Any]) -> Dict[str, Any]:
    direct = _mapping(payload.get("direct_equality_core"))
    labels = _extract_labels(payload)
    candidate = payload.get("candidate")
    candidate_key = None
    anchor_idx = None
    if isinstance(candidate, Mapping):
        candidate_key = candidate.get("key")
        anchor_idx = candidate.get("anchor_idx")
    else:
        candidate_key = candidate
        anchor_idx = payload.get("anchor_idx")
    fields = Counter(str(label.get("field")) for label in labels)
    slots = Counter(str(label.get("slot_index")) for label in labels)
    return {
        "file_name": core_path.name,
        "name": payload.get("name"),
        "candidate_key": candidate_key,
        "anchor_idx": anchor_idx,
        "group_id": _first_non_empty([payload.get("group_id"), _mapping(payload.get("profile")).get("group_id"), _first_label_value(labels, "group_id")]),
        "final_key_count": int(len(labels)),
        "field_counts": dict(sorted(fields.items())),
        "slot_counts": dict(sorted(slots.items())),
        "source_final_key_count": direct.get("final_key_count") or len(labels),
    }


def _extract_labels(payload: Mapping[str, Any]) -> list[Dict[str, Any]]:
    direct = _mapping(payload.get("direct_equality_core"))
    labels = direct.get("remaining_labels")
    if isinstance(labels, list):
        return [dict(label) for label in labels if isinstance(label, Mapping)]

    final_keys = payload.get("final_keys")
    if not isinstance(final_keys, list):
        final_keys = direct.get("final_keys")
    return [_label_from_stable_key(str(key)) for key in list(final_keys or [])]


def _label_from_stable_key(stable_key: str) -> Dict[str, Any]:
    parts = str(stable_key).split("|")
    if len(parts) < 6:
        return {"stable_key": stable_key, "parse_error": "unexpected_stable_key_shape"}
    return {
        "stable_key": stable_key,
        "group_id": parts[1],
        "slot_key": parts[2],
        "slot_index": _int_or_none(parts[2]),
        "solution_id": parts[3],
        "pose_index": _int_or_none(parts[4]),
        "field": parts[5],
    }


def _enrich_label(
    label: Mapping[str, Any],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    ghost: Mapping[str, Any],
) -> Dict[str, Any]:
    enriched = dict(label)
    template = str(enriched.get("template") or _template_from_group(enriched.get("group_id")) or "")
    pose_index = _int_or_none(enriched.get("pose_index"))
    pose = None
    if template and pose_index is not None:
        pool = list(pools.get(template, []))
        if 0 <= int(pose_index) < len(pool):
            pose = dict(pool[int(pose_index)])
    pose_tuple = _pose_tuple(template, pose, pools) if pose is not None else None
    field = str(enriched.get("field"))
    forced_value = _int_or_none(enriched.get("forced_value"))
    if forced_value is None and pose_tuple is not None and field in {"x", "y", "mode"}:
        forced_value = int(pose_tuple[{"x": 0, "y": 1, "mode": 2}[field]])
    enriched["template"] = template
    enriched["forced_value"] = forced_value
    enriched["pose_tuple"] = list(pose_tuple) if pose_tuple is not None else None
    enriched["source_pose"] = _compact_pose(pose) if pose is not None else None
    enriched["source_pose_overlaps_ghost"] = _pose_overlaps_ghost(pose, ghost)
    enriched["forced_semantics"] = _forced_semantics(field)
    enriched["stable_key_pose_index_is_provenance_only"] = field != "pose"
    return enriched


def _candidate_ghost(payload: Mapping[str, Any]) -> Dict[str, Any]:
    candidate = payload.get("candidate")
    if isinstance(candidate, Mapping):
        ghost_rect = _mapping(candidate.get("ghost_rect"))
        anchor_idx = _int_or_none(candidate.get("anchor_idx"))
    else:
        ghost_rect = {}
        anchor_idx = _int_or_none(payload.get("anchor_idx"))
    w = _int_or_none(ghost_rect.get("w")) or _ghost_size_from_key(candidate, index=0)
    h = _int_or_none(ghost_rect.get("h")) or _ghost_size_from_key(candidate, index=1)
    anchor = _ghost_anchor_from_idx(anchor_idx, ghost_h=h)
    return {
        "anchor_idx": anchor_idx,
        "w": w,
        "h": h,
        "anchor": anchor,
        "blocked_cell_count": int(w * h) if w is not None and h is not None else None,
    }


def _ghost_anchor_from_idx(anchor_idx: int | None, *, ghost_h: int | None, grid_h: int = 70) -> Dict[str, int] | None:
    if anchor_idx is None or ghost_h is None:
        return None
    stride = int(grid_h) - int(ghost_h) + 1
    if stride <= 0:
        return None
    return {"x": int(anchor_idx) // stride, "y": int(anchor_idx) % stride}


def _pose_overlaps_ghost(pose: Mapping[str, Any] | None, ghost: Mapping[str, Any]) -> bool | None:
    if pose is None:
        return None
    anchor = _mapping(ghost.get("anchor"))
    w = _int_or_none(ghost.get("w"))
    h = _int_or_none(ghost.get("h"))
    if "x" not in anchor or "y" not in anchor or w is None or h is None:
        return None
    blocked = {
        (int(anchor["x"]) + dx, int(anchor["y"]) + dy)
        for dx in range(int(w))
        for dy in range(int(h))
    }
    cells = {(int(x), int(y)) for x, y in list(pose.get("occupied_cells", []) or [])}
    return not cells.isdisjoint(blocked)


def _pose_tuple(
    template: str,
    pose: Mapping[str, Any] | None,
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[int, int, int] | None:
    if pose is None:
        return None
    anchor = _mapping(pose.get("anchor"))
    token = _pose_mode_token(pose)
    mode_tokens = sorted({_pose_mode_token(item) for item in list(pools.get(str(template), []))}) or [("", "")]
    mode_id_by_token = {value: idx for idx, value in enumerate(mode_tokens)}
    return (
        int(anchor.get("x", 0)),
        int(anchor.get("y", 0)),
        int(mode_id_by_token[token]),
    )


def _pose_mode_token(pose: Mapping[str, Any]) -> tuple[str, str]:
    params = _mapping(pose.get("pose_params"))
    return (str(params.get("orientation", "")), str(params.get("port_mode", "")))


def _compact_pose(pose: Mapping[str, Any] | None) -> Dict[str, Any] | None:
    if pose is None:
        return None
    return {
        "pose_id": pose.get("pose_id"),
        "anchor": dict(_mapping(pose.get("anchor"))),
        "pose_params": dict(_mapping(pose.get("pose_params"))),
        "occupied_bounds": _bounds(pose.get("occupied_cells", []) or []),
        "input_port_count": len(list(pose.get("input_port_cells", []) or [])),
        "output_port_count": len(list(pose.get("output_port_cells", []) or [])),
    }


def _interpret_labels(labels: Sequence[Mapping[str, Any]], ghost: Mapping[str, Any]) -> list[str]:
    by_slot: Dict[str, list[str]] = defaultdict(list)
    for label in labels:
        by_slot[str(label.get("slot_index"))].append(str(label.get("field")))
    complete_slots = [
        slot for slot, fields in sorted(by_slot.items()) if {"x", "y", "mode"}.issubset(set(fields))
    ]
    partial_slots = [
        slot for slot, fields in sorted(by_slot.items()) if not {"x", "y", "mode"}.issubset(set(fields))
    ]
    lines = [
        "Stable keys force coordinate fields, not full source poses unless x/y/mode all appear for the same slot.",
    ]
    if partial_slots:
        lines.append(
            "Partial slots remain movable in unforced dimensions; source pose overlap with the ghost is provenance, not proof."
        )
    if complete_slots:
        lines.append(f"Complete pose equality slots: {', '.join(complete_slots)}.")
    if ghost.get("anchor"):
        anchor = _mapping(ghost.get("anchor"))
        lines.append(
            f"Ghost anchor blocks x={anchor.get('x')}..{int(anchor.get('x')) + int(ghost.get('w')) - 1} "
            f"and y={anchor.get('y')}..{int(anchor.get('y')) + int(ghost.get('h')) - 1}."
        )
    return lines


def _summary(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    fields: Counter[str] = Counter()
    final_key_count = 0
    complete_pose_equality_key_count = 0
    for entry in entries:
        labels = [label for label in list(entry.get("labels", [])) if isinstance(label, Mapping)]
        final_key_count += len(labels)
        by_slot: Dict[str, set[str]] = defaultdict(set)
        for label in labels:
            fields[str(label.get("field"))] += 1
            by_slot[str(label.get("slot_index"))].add(str(label.get("field")))
        complete_pose_equality_key_count += sum(
            1 for slot_fields in by_slot.values() if {"x", "y", "mode"}.issubset(slot_fields)
        )
    return {
        "core_count": int(len(entries)),
        "final_key_count": int(final_key_count),
        "field_counts": dict(sorted(fields.items())),
        "complete_pose_equality_key_count": int(complete_pose_equality_key_count),
    }


def _checks(entries: Sequence[Mapping[str, Any]]) -> list[Dict[str, str]]:
    checks: list[Dict[str, str]] = []
    checks.append(
        {
            "check_id": "core_entries_present",
            "status": "pass" if entries else "fail",
            "detail": f"core_entries={len(entries)}",
        }
    )
    missing_pose = sum(
        1
        for entry in entries
        for label in list(entry.get("labels", []))
        if isinstance(label, Mapping) and label.get("source_pose") is None
    )
    checks.append(
        {
            "check_id": "source_pose_resolution",
            "status": "pass" if missing_pose == 0 else "fail",
            "detail": f"missing_source_pose={missing_pose}",
        }
    )
    return checks


def _load_facility_pools(path: Path) -> Mapping[str, Sequence[Mapping[str, Any]]]:
    payload = _load_json(path)
    pools = payload.get("facility_pools", payload)
    if not isinstance(pools, Mapping):
        raise ValueError(f"candidate placements missing facility pools: {path}")
    return {
        str(template): [dict(item) for item in list(pool) if isinstance(item, Mapping)]
        for template, pool in pools.items()
        if isinstance(pool, list)
    }


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _template_from_group(group_id: Any) -> str | None:
    parts = str(group_id or "").split("::")
    if len(parts) >= 3 and parts[0] == "group":
        return parts[1]
    return None


def _ghost_size_from_key(candidate: Any, *, index: int) -> int | None:
    text = str(candidate or "")
    if "x" not in text:
        return None
    parts = text.split("x", 1)
    try:
        return int(parts[index])
    except Exception:
        return None


def _forced_semantics(field: str) -> str:
    if field == "x":
        return "forces x coordinate only"
    if field == "y":
        return "forces y coordinate only"
    if field == "mode":
        return "forces orientation/port-mode id only"
    return f"forces {field}"


def _bounds(cells: Iterable[Any]) -> Dict[str, int] | None:
    parsed = [(int(cell[0]), int(cell[1])) for cell in cells]
    if not parsed:
        return None
    xs = [x for x, _y in parsed]
    ys = [y for _x, y in parsed]
    return {"x_min": min(xs), "x_max": max(xs), "y_min": min(ys), "y_max": max(ys)}


def _first_label_value(labels: Sequence[Mapping[str, Any]], key: str) -> Any:
    for label in labels:
        value = label.get(key)
        if value is not None:
            return value
    return None


def _first_non_empty(values: Sequence[Any]) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)
