from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from ortools.sat.python import cp_model

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso
from src.search.phase3b_coordinate_validation_direct_equality_core import (
    DEFAULT_DIRECT_EQUALITY_CORE_GROUP_ID,
)
from src.search.phase3b_coordinate_validation_group_delta import (
    _build_delta_context,
    _candidate_rect,
    _check,
    _compact_greedy,
    _compact_validation,
    _mapping,
    _normalize_solver_profile,
)

COORDINATE_VALIDATION_X_DOMAIN_ORDER_AUDIT_SOURCE = (
    "phase3b_coordinate_validation_x_domain_order_audit_v1"
)

DEFAULT_X_DOMAIN_ORDER_AUDIT_GROUP_ID = DEFAULT_DIRECT_EQUALITY_CORE_GROUP_ID

DEFAULT_T24_X_CORE_LABELS: Tuple[Mapping[str, Any], ...] = tuple(
    {
        "stable_key": (
            "mandatory|group::manufacturing_5x5::planter_sandleaf::10|"
            f"{slot_index}|planter_sandleaf_{slot_index + 1:03d}|{pose_index}|x"
        ),
        "group_id": "group::manufacturing_5x5::planter_sandleaf::10",
        "solution_id": f"planter_sandleaf_{slot_index + 1:03d}",
        "slot_key": str(slot_index),
        "slot_index": int(slot_index),
        "template": "manufacturing_5x5",
        "pose_index": int(pose_index),
        "field": "x",
        "forced_value": 0,
        "selected": True,
    }
    for slot_index, pose_index in zip(range(1, 13), range(11, 122, 10))
)


def build_phase3b_coordinate_validation_x_domain_order_audit(
    project_root: Path,
    *,
    candidate: str = "67x13",
    anchor_idx: int = 119,
    group_id: str = DEFAULT_X_DOMAIN_ORDER_AUDIT_GROUP_ID,
    core_json: Optional[Path] = None,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    time_limit_seconds: float = 2.0,
    worker_count: int = 1,
    solver_parameter_profile: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    normalized_group_id = str(group_id).strip()
    solver_profile = _normalize_solver_profile(
        solver_parameter_profile,
        time_limit_seconds=float(time_limit_seconds),
        worker_count=int(worker_count),
    )
    started = time.perf_counter()

    try:
        artifact_hashes = compute_exact_artifact_hashes(project_root)
        artifact_hash_error = None
    except Exception as exc:
        artifact_hashes = {}
        artifact_hash_error = f"{type(exc).__name__}: {exc}"

    core_payload = _load_t24_core_labels(core_json, group_id=normalized_group_id)
    core_labels = list(core_payload["labels"])
    core_keys = [str(label.get("stable_key")) for label in core_labels]

    context: Dict[str, Any] = {}
    model_error: Optional[str] = None
    greedy: Dict[str, Any] = {}
    subset_validation: Dict[str, Any] = {}
    audit_entries: list[Dict[str, Any]] = []
    group_metadata: Dict[str, Any] = {}
    monotonicity: Dict[str, Any] = {}
    standalone_repro: Dict[str, Any] = {
        "attempted": False,
        "reason": "not_evaluated",
        "variants": [],
    }

    try:
        context = _build_delta_context(
            project_root,
            candidate=str(candidate),
            anchor_idx=int(anchor_idx),
            master_search_profile=str(master_search_profile),
        )
        group_by_id = {
            str(group.get("group_id", "")): group
            for group in list(context["ordered_groups"])
            if isinstance(group, Mapping)
        }
        group = group_by_id.get(normalized_group_id)
        if group is None:
            raise ValueError(f"Unknown x-domain/order audit group id: {normalized_group_id}")

        model = context["model"]
        delegate = getattr(model, "_coordinate_delegate", None)
        if delegate is None:
            raise RuntimeError("Coordinate delegate unavailable")

        greedy = model._run_mandatory_greedy_pass(
            ordered_groups=[group],
            candidates_by_group=context["candidates_by_group"],
            blocked_cells=set(),
            stop_on_first_failure=True,
        )
        if bool(greedy.get("complete", False)) and core_keys:
            subset_validation = _compact_validation(
                model._validate_coordinate_forced_hint(
                    solution_hint=dict(greedy.get("solution_hint", {})),
                    ghost_anchor_hint_idx=None,
                    time_limit_seconds=float(time_limit_seconds),
                    require_complete=False,
                    solver_parameter_profile=solver_profile,
                    force_fields=("x",),
                    force_equality_keys=set(core_keys),
                    collect_force_equality_labels=True,
                )
            )
        else:
            subset_validation = _compact_validation(
                {
                    "attempted": False,
                    "status": "SKIPPED",
                    "accepted": False,
                    "reason": (
                        "missing_core_keys"
                        if not core_keys
                        else "greedy_group_incomplete"
                    ),
                    "missing_hint_count": 0,
                    "missing_pose_tuple_count": 0,
                    "forced_slot_field_count": 0,
                    "forced_ghost_anchor": False,
                    "forced_fields": ["x"],
                    "force_equality_filter_active": bool(core_keys),
                    "force_equality_labels": [],
                    "require_complete": False,
                }
            )

        audit_context = _audit_context_for_group(
            model=model,
            delegate=delegate,
            group=group,
            greedy=greedy,
        )
        group_metadata = dict(audit_context["group_metadata"])
        audit_entries = _audit_core_labels(
            model=model,
            delegate=delegate,
            group=group,
            labels=core_labels,
            selected_validation_labels=list(
                subset_validation.get("force_equality_labels", [])
            ),
            hint_sequence=list(audit_context["hint_sequence"]),
        )
        monotonicity = _summarize_monotonicity(audit_entries)
        standalone_repro = _run_standalone_repros(
            model=model,
            delegate=delegate,
            group=group,
            labels=core_labels,
            time_limit_seconds=float(time_limit_seconds),
            worker_count=int(worker_count),
        )
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"

    status = _status_from_payload(
        subset_validation=subset_validation,
        labels=core_labels,
        audit_entries=audit_entries,
        model_error=model_error,
    )
    return {
        "metadata": {
            "source": COORDINATE_VALIDATION_X_DOMAIN_ORDER_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "coordinate_validation_x_domain_order_audit_not_proof_source"
            ),
        },
        "paths": {
            "project_root": str(project_root),
            "core_json": str(Path(core_json).resolve()) if core_json is not None else None,
        },
        "candidate": {
            "key": str(candidate),
            "ghost_rect": _candidate_rect(str(candidate)),
            "anchor_idx": int(anchor_idx),
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "group_id": normalized_group_id,
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
            "solver_parameter_profile": dict(solver_profile),
        },
        "artifact_hashes": dict(artifact_hashes),
        "artifact_hash_error": artifact_hash_error,
        "context": {
            "ghost_anchor_count": int(context.get("ghost_anchor_count", 0)),
            "blocked_cell_count": int(context.get("blocked_cell_count", 0)),
            "ordered_group_count": int(context.get("ordered_group_count", 0)),
        },
        "status": status,
        "core_input": core_payload,
        "group_metadata": group_metadata,
        "subset_validation": subset_validation,
        "audit": {
            "entries": audit_entries,
            "entry_count": int(len(audit_entries)),
            "monotonicity": monotonicity,
            "all_pose_tuples_allowed": all(
                bool(entry.get("allowed_tuple_present", False))
                for entry in audit_entries
            )
            if audit_entries
            else False,
            "all_forced_values_match_pose_tuple": all(
                bool(entry.get("forced_value_matches_pose_tuple", False))
                for entry in audit_entries
            )
            if audit_entries
            else False,
            "all_tuple_components_within_domains": all(
                bool(entry.get("tuple_components_within_domains", False))
                for entry in audit_entries
            )
            if audit_entries
            else False,
        },
        "standalone_repro": standalone_repro,
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "checks": _checks(status, core_payload, subset_validation, audit_entries, standalone_repro),
    }


def render_phase3b_coordinate_validation_x_domain_order_audit_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    subset = _mapping(report.get("subset_validation"))
    audit = _mapping(report.get("audit"))
    monotonicity = _mapping(audit.get("monotonicity"))
    standalone = _mapping(report.get("standalone_repro"))
    lines = [
        "# Phase 3B Coordinate Validation X-Domain / Order Audit",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Anchor: {candidate.get('anchor_idx')}",
        "- Diagnostic semantics: coordinate_validation_x_domain_order_audit_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- 12-key subset status: {subset.get('status')}",
        f"- Audit entries: {audit.get('entry_count')}",
        f"- All tuples allowed: {audit.get('all_pose_tuples_allowed')}",
        f"- All forced values match pose tuple: {audit.get('all_forced_values_match_pose_tuple')}",
        f"- Core order keys nondecreasing: {monotonicity.get('core_order_keys_nondecreasing')}",
        "",
        "## Core Label Audit",
        "",
        (
            "| Slot | Solution | Pose | Tuple | Field | Value | X Domain | Y Domain | "
            "Mode Domain | Allowed | Order Key | Prev/Next Hint Order |"
        ),
        "| ---: | --- | ---: | --- | --- | ---: | --- | --- | --- | --- | ---: | --- |",
    ]
    for entry in list(audit.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        domains = _mapping(entry.get("variable_domains"))
        neighbors = _mapping(entry.get("neighbor_order"))
        prev_next = (
            f"{neighbors.get('previous_hint_order_key')}/"
            f"{neighbors.get('next_hint_order_key')}"
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("slot_index")),
                    _markdown_cell(entry.get("solution_id")),
                    _markdown_cell(entry.get("pose_index")),
                    _markdown_cell(entry.get("pose_tuple")),
                    _markdown_cell(entry.get("field")),
                    _markdown_cell(entry.get("forced_value")),
                    _markdown_cell(domains.get("x")),
                    _markdown_cell(domains.get("y")),
                    _markdown_cell(domains.get("mode")),
                    _markdown_cell(entry.get("allowed_tuple_present")),
                    _markdown_cell(entry.get("order_key_value")),
                    _markdown_cell(prev_next),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Standalone Repro",
            "",
            f"- Attempted: {standalone.get('attempted')}",
            f"- Reason: {standalone.get('reason')}",
            "",
            "| Variant | Status | Accepted | Forced Equalities | Constraints |",
            "| --- | --- | --- | ---: | ---: |",
        ]
    )
    for variant in list(standalone.get("variants", [])):
        if not isinstance(variant, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(variant.get("variant")),
                    _markdown_cell(variant.get("status")),
                    _markdown_cell(variant.get("accepted")),
                    _markdown_cell(variant.get("forced_equality_count")),
                    _markdown_cell(variant.get("constraint_count")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in list(report.get("checks", [])):
        if not isinstance(check, Mapping):
            continue
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


def render_phase3b_coordinate_validation_x_domain_order_audit_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    candidate = _mapping(report.get("candidate"))
    subset = _mapping(report.get("subset_validation"))
    audit = _mapping(report.get("audit"))
    monotonicity = _mapping(audit.get("monotonicity"))
    lines = [
        "Phase 3B coordinate validation x-domain/order audit",
        f"candidate={candidate.get('key')}",
        f"anchor_idx={candidate.get('anchor_idx')}",
        "diagnostic_semantics=coordinate_validation_x_domain_order_audit_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"subset_status={subset.get('status')}",
        f"entry_count={audit.get('entry_count')}",
        f"all_pose_tuples_allowed={audit.get('all_pose_tuples_allowed')}",
        f"all_forced_values_match_pose_tuple={audit.get('all_forced_values_match_pose_tuple')}",
        f"core_order_keys_nondecreasing={monotonicity.get('core_order_keys_nondecreasing')}",
    ]
    for entry in list(audit.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "entry "
            f"slot={entry.get('slot_index')} "
            f"solution={entry.get('solution_id')} "
            f"pose={entry.get('pose_index')} "
            f"tuple={entry.get('pose_tuple')} "
            f"value={entry.get('forced_value')} "
            f"allowed={entry.get('allowed_tuple_present')} "
            f"order_key={entry.get('order_key_value')}"
        )
    for variant in list(_mapping(report.get("standalone_repro")).get("variants", [])):
        if isinstance(variant, Mapping):
            lines.append(
                "standalone "
                f"variant={variant.get('variant')} "
                f"status={variant.get('status')} "
                f"accepted={variant.get('accepted')}"
            )
    return "\n".join(lines) + "\n"


def _load_t24_core_labels(
    core_json: Optional[Path],
    *,
    group_id: str,
) -> Dict[str, Any]:
    if core_json is None:
        return {
            "source": "built_in_t24_remaining_core",
            "core_json_loaded": False,
            "load_error": None,
            "label_count": len(DEFAULT_T24_X_CORE_LABELS),
            "labels": [dict(label) for label in DEFAULT_T24_X_CORE_LABELS],
        }
    path = Path(core_json)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        core = _mapping(payload.get("direct_equality_core"))
        raw_labels = [
            dict(label)
            for label in list(core.get("remaining_labels", []))
            if isinstance(label, Mapping)
        ]
        labels = [
            dict(label)
            for label in raw_labels
            if str(label.get("group_id")) == str(group_id)
        ]
        return {
            "source": "core_json_remaining_labels",
            "core_json_loaded": True,
            "load_error": None,
            "label_count": len(labels),
            "labels": labels,
            "raw_remaining_label_count": len(raw_labels),
        }
    except Exception as exc:
        return {
            "source": "built_in_t24_remaining_core_after_core_json_error",
            "core_json_loaded": False,
            "load_error": f"{type(exc).__name__}: {exc}",
            "label_count": len(DEFAULT_T24_X_CORE_LABELS),
            "labels": [dict(label) for label in DEFAULT_T24_X_CORE_LABELS],
        }


def _audit_context_for_group(
    *,
    model: Any,
    delegate: Any,
    group: Mapping[str, Any],
    greedy: Mapping[str, Any],
) -> Dict[str, Any]:
    group_id = str(group.get("group_id", ""))
    tpl = str(group.get("facility_type", ""))
    slots = list(delegate.mandatory_slots.get(group_id, []))
    mode_count = int(getattr(delegate, "_template_mode_literals", {}).get(tpl, 1))
    scale_x, scale_y = delegate._slot_order_key_bounds(slots[0]) if slots else (0, 0)
    hint_sequence = _mandatory_slot_hint_sequence(
        model=model,
        delegate=delegate,
        group=group,
        greedy=greedy,
    )
    return {
        "group_metadata": {
            "group_id": group_id,
            "template": tpl,
            "operation_type": group.get("operation_type"),
            "slot_count": len(slots),
            "instance_count": len(list(group.get("instance_ids", []))),
            "grid_width": int(getattr(delegate, "grid_w", 0)),
            "grid_height": int(getattr(delegate, "grid_h", 0)),
            "mode_count": mode_count,
            "order_key_formula": "x * scale_x + y * scale_y + mode",
            "order_key_scale_x": int(scale_x),
            "order_key_scale_y": int(scale_y),
            "mandatory_slot_order_constraint": "slot[i].order_key <= slot[i+1].order_key",
        },
        "hint_sequence": hint_sequence,
    }


def _mandatory_slot_hint_sequence(
    *,
    model: Any,
    delegate: Any,
    group: Mapping[str, Any],
    greedy: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    group_id = str(group.get("group_id", ""))
    tpl = str(group.get("facility_type", ""))
    slots = list(delegate.mandatory_slots.get(group_id, []))
    solution_ids = [str(item) for item in list(group.get("instance_ids", []))]
    solution_hint = dict(greedy.get("solution_hint", {}))
    hinted_pose_indices = [
        int(solution_hint[solution_id])
        for solution_id in solution_ids
        if solution_id in solution_hint
    ]
    hinted_pose_indices = sorted(
        hinted_pose_indices,
        key=lambda pose_idx: model._pose_sort_key(tpl, int(pose_idx)),
    )
    sequence: list[Dict[str, Any]] = []
    for slot_index, pose_idx in enumerate(hinted_pose_indices[: len(slots)]):
        slot = slots[int(slot_index)]
        pose_tuple = delegate._template_pose_tuple_by_idx.get(tpl, {}).get(int(pose_idx))
        order_key = None
        if pose_tuple is not None:
            scale_x, scale_y = delegate._slot_order_key_bounds(slot)
            order_key = _order_key_for_tuple(pose_tuple, scale_x, scale_y)
        sequence.append(
            {
                "slot_index": int(slot_index),
                "solution_id": (
                    solution_ids[int(slot_index)]
                    if int(slot_index) < len(solution_ids)
                    else f"{group_id}::{slot_index}"
                ),
                "pose_index": int(pose_idx),
                "pose_tuple": list(pose_tuple) if pose_tuple is not None else None,
                "order_key_value": order_key,
            }
        )
    return sequence


def _audit_core_labels(
    *,
    model: Any,
    delegate: Any,
    group: Mapping[str, Any],
    labels: Sequence[Mapping[str, Any]],
    selected_validation_labels: Sequence[Mapping[str, Any]],
    hint_sequence: Sequence[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    group_id = str(group.get("group_id", ""))
    slots = list(delegate.mandatory_slots.get(group_id, []))
    proto = model.model.Proto()
    proto_name_to_index = {str(var.name): idx for idx, var in enumerate(proto.variables)}
    selected_by_key = {
        str(label.get("stable_key")): dict(label)
        for label in selected_validation_labels
        if isinstance(label, Mapping)
    }
    hint_by_slot = {
        int(item.get("slot_index")): dict(item)
        for item in hint_sequence
        if isinstance(item, Mapping) and item.get("slot_index") is not None
    }
    allowed_tuple_cache: Dict[str, set[Tuple[int, int, int]]] = {}
    entries: list[Dict[str, Any]] = []
    for label in labels:
        slot_index = int(label.get("slot_index", -1))
        slot = slots[slot_index] if 0 <= slot_index < len(slots) else None
        if slot is None:
            entries.append(
                {
                    "stable_key": str(label.get("stable_key")),
                    "group_id": str(label.get("group_id")),
                    "slot_index": slot_index,
                    "error": "slot_index_out_of_range",
                }
            )
            continue
        tpl = str(label.get("template") or getattr(slot, "template", ""))
        pose_idx = int(label.get("pose_index", -1))
        pose_tuple = delegate._template_pose_tuple_by_idx.get(tpl, {}).get(pose_idx)
        scale_x, scale_y = delegate._slot_order_key_bounds(slot)
        order_key_value = (
            _order_key_for_tuple(pose_tuple, scale_x, scale_y)
            if pose_tuple is not None
            else None
        )
        tuple_key = tuple(int(value) for value in pose_tuple) if pose_tuple is not None else None
        allowed_set = allowed_tuple_cache.setdefault(
            str(slot.key),
            {tuple(int(v) for v in row) for row in tuple(slot.allowed_tuples or ())},
        )
        domains = {
            "x": _var_domain_from_proto(proto, getattr(slot, "x", None)),
            "y": _var_domain_from_proto(proto, getattr(slot, "y", None)),
            "mode": _var_domain_from_proto(proto, getattr(slot, "mode", None)),
        }
        forced_value = int(label.get("forced_value", 0))
        field = str(label.get("field"))
        pose_field_value = _pose_field_value(pose_tuple, field)
        order_domain, order_domain_source = _order_key_domain_from_proto(
            proto=proto,
            proto_name_to_index=proto_name_to_index,
            slot=slot,
        )
        domains["order_key"] = order_domain
        mode_domain = (
            getattr(slot, "mode_rect_domains", {}).get(int(pose_tuple[2]))
            if pose_tuple is not None
            else {}
        )
        entry = {
            "stable_key": str(label.get("stable_key")),
            "group_id": str(label.get("group_id")),
            "solution_id": str(label.get("solution_id")),
            "slot_key": str(label.get("slot_key")),
            "slot_index": slot_index,
            "template": tpl,
            "pose_index": pose_idx,
            "field": field,
            "forced_value": forced_value,
            "pose_tuple": list(pose_tuple) if pose_tuple is not None else None,
            "pose_tuple_source": "delegate._template_pose_tuple_by_idx",
            "pose_field_value": pose_field_value,
            "forced_value_matches_pose_tuple": pose_field_value == forced_value,
            "variable_domains": domains,
            "order_key_domain_source": order_domain_source,
            "tuple_components_within_domains": _tuple_within_domains(pose_tuple, domains),
            "allowed_tuple_count": len(tuple(slot.allowed_tuples or ())),
            "allowed_tuple_present": tuple_key in allowed_set if tuple_key is not None else False,
            "use_domain_table": bool(getattr(slot, "use_domain_table", False)),
            "candidate_pose_count": int(getattr(slot, "candidate_pose_count", 0)),
            "order_key_formula": "x * scale_x + y * scale_y + mode",
            "order_key_scale_x": int(scale_x),
            "order_key_scale_y": int(scale_y),
            "order_key_value": order_key_value,
            "mode_rect_domain": _domain_dataclass_to_dict(mode_domain),
            "neighbor_order": _neighbor_order_payload(
                slot_index=slot_index,
                hint_by_slot=hint_by_slot,
            ),
            "collected_validation_label_present": str(label.get("stable_key")) in selected_by_key,
            "selected_in_subset_validation": bool(
                selected_by_key.get(str(label.get("stable_key")), {}).get("selected", False)
            ),
        }
        entries.append(entry)
    return sorted(entries, key=lambda entry: int(entry.get("slot_index", -1)))


def _run_standalone_repros(
    *,
    model: Any,
    delegate: Any,
    group: Mapping[str, Any],
    labels: Sequence[Mapping[str, Any]],
    time_limit_seconds: float,
    worker_count: int,
) -> Dict[str, Any]:
    variants = []
    for include_no_overlap in (False, True):
        variants.append(
            _run_single_standalone_repro(
                model=model,
                delegate=delegate,
                group=group,
                labels=labels,
                include_no_overlap=include_no_overlap,
                time_limit_seconds=time_limit_seconds,
                worker_count=worker_count,
            )
        )
    return {
        "attempted": True,
        "reason": "group_only_domain_order_no_overlap_repro",
        "scope_note": (
            "Standalone repro includes this group's slot domains, optional allowed tuple "
            "tables when enabled by the slot, slot-order monotonicity, the T24 x "
            "equalities, and optional same-group NoOverlap2D. It does not recreate "
            "global mandatory groups, power coverage, signatures, or other exact "
            "coordinate constraints."
        ),
        "variants": variants,
    }


def _run_single_standalone_repro(
    *,
    model: Any,
    delegate: Any,
    group: Mapping[str, Any],
    labels: Sequence[Mapping[str, Any]],
    include_no_overlap: bool,
    time_limit_seconds: float,
    worker_count: int,
) -> Dict[str, Any]:
    group_id = str(group.get("group_id", ""))
    slots = list(delegate.mandatory_slots.get(group_id, []))
    standalone = cp_model.CpModel()
    source_proto = model.model.Proto()
    xs = []
    ys = []
    modes = []
    x_intervals = []
    y_intervals = []
    allowed_assignment_count = 0
    for slot_index, slot in enumerate(slots):
        x_domain = _var_domain_from_proto(source_proto, getattr(slot, "x", None)) or [0, 0]
        y_domain = _var_domain_from_proto(source_proto, getattr(slot, "y", None)) or [0, 0]
        mode_domain = _var_domain_from_proto(source_proto, getattr(slot, "mode", None)) or [0, 0]
        x_var = _new_int_var_from_flat_domain(standalone, x_domain, f"x_{slot_index}")
        y_var = _new_int_var_from_flat_domain(standalone, y_domain, f"y_{slot_index}")
        mode_var = _new_int_var_from_flat_domain(standalone, mode_domain, f"mode_{slot_index}")
        xs.append(x_var)
        ys.append(y_var)
        modes.append(mode_var)
        if bool(getattr(slot, "use_domain_table", False)) and getattr(slot, "allowed_tuples", None):
            rows = [[int(x), int(y), int(mode)] for x, y, mode in slot.allowed_tuples]
            standalone.AddAllowedAssignments([x_var, y_var, mode_var], rows)
            allowed_assignment_count += len(rows)
        if include_no_overlap:
            width = int(getattr(slot, "dims", (1, 1))[0])
            height = int(getattr(slot, "dims", (1, 1))[1])
            x_end = standalone.NewIntVar(0, int(delegate.grid_w) + width, f"x_end_{slot_index}")
            y_end = standalone.NewIntVar(0, int(delegate.grid_h) + height, f"y_end_{slot_index}")
            standalone.Add(x_end == x_var + width)
            standalone.Add(y_end == y_var + height)
            x_intervals.append(standalone.NewIntervalVar(x_var, width, x_end, f"x_iv_{slot_index}"))
            y_intervals.append(standalone.NewIntervalVar(y_var, height, y_end, f"y_iv_{slot_index}"))
    for left_index, right_index in zip(range(len(slots) - 1), range(1, len(slots))):
        scale_x, scale_y = delegate._slot_order_key_bounds(slots[left_index])
        standalone.Add(
            xs[left_index] * int(scale_x)
            + ys[left_index] * int(scale_y)
            + modes[left_index]
            <= xs[right_index] * int(scale_x)
            + ys[right_index] * int(scale_y)
            + modes[right_index]
        )
    if include_no_overlap and x_intervals and y_intervals:
        standalone.AddNoOverlap2D(x_intervals, y_intervals)
    forced_equality_count = 0
    for label in labels:
        slot_index = int(label.get("slot_index", -1))
        if not (0 <= slot_index < len(slots)):
            continue
        field = str(label.get("field"))
        value = int(label.get("forced_value", 0))
        if field == "x":
            standalone.Add(xs[slot_index] == value)
        elif field == "y":
            standalone.Add(ys[slot_index] == value)
        elif field == "mode":
            standalone.Add(modes[slot_index] == value)
        else:
            continue
        forced_equality_count += 1
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.001, float(time_limit_seconds))
    solver.parameters.num_search_workers = max(1, int(worker_count))
    status = solver.Solve(standalone)
    status_name = solver.StatusName(status)
    return {
        "variant": "group_domain_order_no_overlap" if include_no_overlap else "group_domain_order_only",
        "include_no_overlap": bool(include_no_overlap),
        "status": str(status_name),
        "accepted": status in {cp_model.OPTIMAL, cp_model.FEASIBLE},
        "forced_equality_count": int(forced_equality_count),
        "slot_count": int(len(slots)),
        "allowed_assignment_row_count": int(allowed_assignment_count),
        "constraint_count": int(len(standalone.Proto().constraints)),
        "variable_count": int(len(standalone.Proto().variables)),
        "wall_time": float(solver.WallTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
    }


def _status_from_payload(
    *,
    subset_validation: Mapping[str, Any],
    labels: Sequence[Mapping[str, Any]],
    audit_entries: Sequence[Mapping[str, Any]],
    model_error: Optional[str],
) -> Dict[str, Any]:
    if model_error is not None:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "diagnostic_error",
            "recommendation": "X-domain/order audit failed; inspect model_error.",
        }
    if not labels:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "no_core_labels",
            "recommendation": "No T24 core labels were available for audit.",
        }
    subset_status = str(subset_validation.get("status"))
    if subset_status == "INFEASIBLE":
        if audit_entries:
            return {
                "completed": True,
                "evaluated": True,
                "outcome": "subset_infeasible",
                "recommendation": (
                    "The T24 12-key x core still reproduces INFEASIBLE; use this "
                    "audit to choose the next exact-safe repair or shrink target."
                ),
            }
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "subset_infeasible_without_audit_entries",
            "recommendation": "Subset reproduced INFEASIBLE, but label enrichment was empty.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "subset_not_infeasible",
        "recommendation": (
            "The T24 12-key x core did not reproduce INFEASIBLE in this audit run; "
            "refresh the core before repair work."
        ),
    }


def _summarize_monotonicity(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    ordered = sorted(
        [entry for entry in entries if entry.get("order_key_value") is not None],
        key=lambda entry: int(entry.get("slot_index", -1)),
    )
    values = [int(entry.get("order_key_value", 0)) for entry in ordered]
    nondecreasing = all(left <= right for left, right in zip(values, values[1:]))
    strictly_increasing = all(left < right for left, right in zip(values, values[1:]))
    diffs = [int(right - left) for left, right in zip(values, values[1:])]
    return {
        "core_slot_indices": [int(entry.get("slot_index", -1)) for entry in ordered],
        "core_order_keys": values,
        "core_order_key_deltas": diffs,
        "core_order_keys_nondecreasing": bool(nondecreasing),
        "core_order_keys_strictly_increasing": bool(strictly_increasing),
        "order_key_monotonicity_alone_explains_conflict": False
        if nondecreasing
        else True,
        "reason": (
            "Core order keys are nondecreasing across the 12 labels."
            if nondecreasing
            else "Core order keys violate the slot-order monotonicity constraint."
        ),
    }


def _checks(
    status: Mapping[str, Any],
    core_payload: Mapping[str, Any],
    subset_validation: Mapping[str, Any],
    audit_entries: Sequence[Mapping[str, Any]],
    standalone_repro: Mapping[str, Any],
) -> list[Dict[str, str]]:
    all_allowed = all(
        bool(entry.get("allowed_tuple_present", False)) for entry in audit_entries
    ) if audit_entries else False
    all_match = all(
        bool(entry.get("forced_value_matches_pose_tuple", False)) for entry in audit_entries
    ) if audit_entries else False
    variants = [
        variant
        for variant in list(standalone_repro.get("variants", []))
        if isinstance(variant, Mapping)
    ]
    return [
        _check(
            "t24_core_labels_available",
            "pass" if int(core_payload.get("label_count", 0)) > 0 else "fail",
            f"label_count={core_payload.get('label_count')} source={core_payload.get('source')}",
        ),
        _check(
            "core_json_loaded_or_defaulted",
            "pass" if not core_payload.get("load_error") else "warn",
            str(core_payload.get("load_error") or "no core json load error"),
        ),
        _check(
            "subset_validation_infeasible",
            "pass" if str(subset_validation.get("status")) == "INFEASIBLE" else "fail",
            f"status={subset_validation.get('status')}",
        ),
        _check(
            "all_pose_tuples_allowed",
            "pass" if all_allowed else "fail",
            f"entry_count={len(audit_entries)}",
        ),
        _check(
            "all_forced_values_match_pose_tuple",
            "pass" if all_match else "fail",
            f"entry_count={len(audit_entries)}",
        ),
        _check(
            "standalone_repro_attempted",
            "pass" if bool(standalone_repro.get("attempted", False)) else "warn",
            str(standalone_repro.get("reason")),
        ),
        _check(
            "standalone_variants_feasible",
            "pass"
            if variants and all(bool(variant.get("accepted", False)) for variant in variants)
            else "warn",
            ",".join(str(variant.get("status")) for variant in variants) or "no variants",
        ),
        _check(
            "audit_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "fail",
            str(status.get("outcome")),
        ),
    ]


def _new_int_var_from_flat_domain(
    model: cp_model.CpModel,
    flat_domain: Sequence[int],
    name: str,
) -> cp_model.IntVar:
    domain_values = [int(value) for value in flat_domain]
    if len(domain_values) == 2:
        return model.NewIntVar(domain_values[0], domain_values[1], name)
    return model.NewIntVarFromDomain(
        cp_model.Domain.FromFlatIntervals(domain_values),
        name,
    )


def _var_domain_from_proto(proto: Any, var: Any) -> Optional[list[int]]:
    if var is None:
        return None
    try:
        index = int(var.Index())
    except Exception:
        return None
    if 0 <= index < len(proto.variables):
        return [int(value) for value in proto.variables[index].domain]
    return None


def _order_key_domain_from_proto(
    *,
    proto: Any,
    proto_name_to_index: Mapping[str, int],
    slot: Any,
) -> Tuple[Optional[list[int]], str]:
    slot_order_key = getattr(slot, "order_key", None)
    direct = _var_domain_from_proto(proto, slot_order_key)
    if direct is not None:
        return direct, "slot_spec_var"
    order_name = f"order_key__{slot.key}"
    index = proto_name_to_index.get(order_name)
    if index is None:
        return None, "unavailable"
    return [int(value) for value in proto.variables[int(index)].domain], "proto_name_lookup"


def _pose_field_value(pose_tuple: Optional[Tuple[int, int, int]], field: str) -> Optional[int]:
    if pose_tuple is None:
        return None
    index_by_field = {"x": 0, "y": 1, "mode": 2}
    if field not in index_by_field:
        return None
    return int(pose_tuple[index_by_field[field]])


def _tuple_within_domains(
    pose_tuple: Optional[Tuple[int, int, int]],
    domains: Mapping[str, Any],
) -> bool:
    if pose_tuple is None:
        return False
    return (
        _value_in_flat_domain(int(pose_tuple[0]), domains.get("x"))
        and _value_in_flat_domain(int(pose_tuple[1]), domains.get("y"))
        and _value_in_flat_domain(int(pose_tuple[2]), domains.get("mode"))
    )


def _value_in_flat_domain(value: int, flat_domain: Any) -> bool:
    if not isinstance(flat_domain, Sequence):
        return False
    values = [int(item) for item in flat_domain]
    for lower, upper in zip(values[0::2], values[1::2]):
        if int(lower) <= int(value) <= int(upper):
            return True
    return False


def _order_key_for_tuple(
    pose_tuple: Tuple[int, int, int],
    scale_x: int,
    scale_y: int,
) -> int:
    x_val, y_val, mode_id = pose_tuple
    return int(x_val) * int(scale_x) + int(y_val) * int(scale_y) + int(mode_id)


def _neighbor_order_payload(
    *,
    slot_index: int,
    hint_by_slot: Mapping[int, Mapping[str, Any]],
) -> Dict[str, Any]:
    previous_hint = _mapping(hint_by_slot.get(int(slot_index) - 1))
    current_hint = _mapping(hint_by_slot.get(int(slot_index)))
    next_hint = _mapping(hint_by_slot.get(int(slot_index) + 1))
    return {
        "previous_constraint": (
            f"slot[{slot_index - 1}].order_key <= slot[{slot_index}].order_key"
            if slot_index > 0
            else None
        ),
        "next_constraint": f"slot[{slot_index}].order_key <= slot[{slot_index + 1}].order_key",
        "current_hint_order_key": current_hint.get("order_key_value"),
        "previous_hint_order_key": previous_hint.get("order_key_value"),
        "next_hint_order_key": next_hint.get("order_key_value"),
        "previous_hint_pose_index": previous_hint.get("pose_index"),
        "next_hint_pose_index": next_hint.get("pose_index"),
        "expected_monotonic_position": "nondecreasing_order_key_sequence",
    }


def _domain_dataclass_to_dict(value: Mapping[str, Any]) -> Dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    return {
        key: getattr(value, key)
        for key in ("mode_id", "orientation", "port_mode", "x_min", "x_max", "y_min", "y_max", "pose_count")
        if hasattr(value, key)
    }


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")
