from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import atomic_write_json, compute_exact_artifact_hashes, now_iso
from src.search.phase3b.coordinate_validation.direct_equality_core import (
    DEFAULT_DIRECT_EQUALITY_CORE_GROUP_ID,
)
from src.search.phase3b.coordinate_validation.x_domain_order_audit import (
    _load_t24_core_labels,
)
from src.search.phase3b.forced_anchor.master import _check, _mapping
from src.search.phase3b.mandatory_core.mandatory_core_matrix import _build_mandatory_core_overlay
from src.search.phase3b.signature_region.equivalence_audit import DEFAULT_CANDIDATE

SIGNATURE_MONOTONIC_FORCED_LABEL_AUDIT_SOURCE = (
    "phase3b_signature_monotonic_forced_label_audit_v1"
)
DEFAULT_GROUP_ID = DEFAULT_DIRECT_EQUALITY_CORE_GROUP_ID


def build_phase3b_signature_monotonic_forced_label_audit(
    project_root: Path,
    *,
    candidate: str = DEFAULT_CANDIDATE,
    group_id: str = DEFAULT_GROUP_ID,
    core_json: Optional[Path] = None,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    enable_symmetry_breaking: bool = True,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    candidate_key = str(candidate)
    started = time.perf_counter()
    core_payload = _load_t24_core_labels(core_json, group_id=str(group_id))
    labels = [
        dict(label)
        for label in list(core_payload.get("labels", []))
        if isinstance(label, Mapping)
    ]
    report: Dict[str, Any] = {
        "metadata": {
            "source": SIGNATURE_MONOTONIC_FORCED_LABEL_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_signature_monotonic_forced_label_audit_not_proof_source",
            "solver_invoked": False,
            "proof_source": False,
        },
        "paths": {
            "project_root": str(project_root),
            "core_json": str(Path(core_json).resolve()) if core_json is not None else None,
        },
        "candidate": {"key": candidate_key, "ghost_rect": _parse_candidate(candidate_key)},
        "profile": {
            "group_id": str(group_id),
            "master_search_profile": str(master_search_profile),
            "enable_symmetry_breaking": bool(enable_symmetry_breaking),
        },
        "artifact_hashes": {},
        "artifact_hash_error": None,
        "core_input": {
            key: value
            for key, value in dict(core_payload).items()
            if key != "labels"
        }
        | {"label_count": int(len(labels))},
        "target_group": {},
        "monotonicity": {},
        "status": {
            "completed": False,
            "outcome": "running",
            "recommendation": "Signature monotonic forced-label audit is running.",
        },
        "timing": {},
        "model_error": None,
        "checks": [],
    }
    try:
        try:
            report["artifact_hashes"] = compute_exact_artifact_hashes(project_root)
        except Exception as exc:
            report["artifact_hash_error"] = f"{type(exc).__name__}: {exc}"
        ghost = _mapping(report["candidate"].get("ghost_rect"))
        model, _base_proto = _build_mandatory_core_overlay(
            project_root,
            ghost_rect=(int(ghost.get("w", 0)), int(ghost.get("h", 0))),
            master_search_profile=str(master_search_profile),
            enable_symmetry_breaking=bool(enable_symmetry_breaking),
        )
        delegate = getattr(model, "_coordinate_delegate", None)
        audit = audit_signature_monotonic_forced_labels(
            model,
            delegate,
            group_id=str(group_id),
            labels=labels,
        )
        report["target_group"] = dict(audit.get("target_group", {}))
        report["monotonicity"] = dict(audit.get("monotonicity", {}))
        report["status"] = _status_from_monotonicity(report["monotonicity"])
    except Exception as exc:
        report["model_error"] = f"{type(exc).__name__}: {exc}"
        report["status"] = {
            "completed": True,
            "outcome": "diagnostic_error",
            "recommendation": "Signature monotonic forced-label audit failed; inspect model_error before using this evidence.",
        }
    report["timing"]["total_seconds"] = float(time.perf_counter() - started)
    report["checks"] = _checks(report)
    return report


def audit_signature_monotonic_forced_labels(
    model: Any,
    delegate: Any,
    *,
    group_id: str,
    labels: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    if delegate is None:
        return _not_evaluated(group_id, "coordinate_delegate_missing")
    group = _find_group(model, group_id)
    if group is None:
        return _not_evaluated(group_id, "target_group_missing")
    group_map = _mapping(group)
    slot_specs = list(getattr(delegate, "mandatory_slots", {}).get(str(group_id), []))
    if not slot_specs:
        return _not_evaluated(group_id, "target_slots_missing")
    signature_ids = _signature_ids_for_slot(slot_specs[0])
    if not signature_ids:
        return _not_evaluated(group_id, "signature_ids_missing")
    rows_by_bucket = _bucket_rows(delegate, str(group_id), str(group_map.get("facility_type", "")))
    all_signatures = set(int(sig) for sig in signature_ids)
    slot_allowed: list[set[int]] = [set(all_signatures) for _ in slot_specs]
    slot_forced_values: list[dict[str, int]] = [dict() for _ in slot_specs]
    label_entries: list[Dict[str, Any]] = []
    for label in labels:
        label_map = _mapping(label)
        slot_index = _int_or_none(label_map.get("slot_index"))
        field = str(label_map.get("field", ""))
        forced_value = _int_or_none(label_map.get("forced_value"))
        if slot_index is None or not (0 <= int(slot_index) < len(slot_allowed)):
            label_entries.append({**dict(label_map), "applied": False, "reason": "slot_index_out_of_range"})
            continue
        if field not in {"x", "y", "mode"} or forced_value is None:
            label_entries.append({**dict(label_map), "applied": False, "reason": "unsupported_field"})
            continue
        slot_forced_values[int(slot_index)][str(field)] = int(forced_value)
        allowed_by_label = {
            int(signature_id)
            for signature_id, rows in rows_by_bucket.items()
            if any(_row_matches(row, field, int(forced_value)) for row in rows)
        }
        label_entries.append(
            {
                **dict(label_map),
                "applied": True,
                "allowed_signature_ids": sorted(int(value) for value in allowed_by_label),
                "slot_conjunctive_forced_fields": None,
                "slot_conjunctive_allowed_signature_ids": None,
            }
        )
    slot_constraint_entries: list[Dict[str, Any]] = []
    for slot_index, constraints in enumerate(slot_forced_values):
        if not constraints:
            continue
        allowed_by_slot = {
            int(signature_id)
            for signature_id, rows in rows_by_bucket.items()
            if any(
                all(
                    _row_matches(row, str(field), int(value))
                    for field, value in constraints.items()
                )
                for row in rows
            )
        }
        slot_allowed[int(slot_index)] = allowed_by_slot
        slot_constraint_entries.append(
            {
                "slot_index": int(slot_index),
                "forced_fields": {
                    str(field): int(value)
                    for field, value in sorted(constraints.items())
                },
                "allowed_signature_ids": sorted(int(value) for value in allowed_by_slot),
            }
        )
    slot_allowed_by_index = {
        int(entry["slot_index"]): list(entry["allowed_signature_ids"])
        for entry in slot_constraint_entries
    }
    slot_fields_by_index = {
        int(entry["slot_index"]): dict(entry["forced_fields"])
        for entry in slot_constraint_entries
    }
    for entry in label_entries:
        if not bool(entry.get("applied")):
            continue
        slot_index = int(entry.get("slot_index", -1))
        entry["slot_conjunctive_forced_fields"] = slot_fields_by_index.get(slot_index, {})
        entry["slot_conjunctive_allowed_signature_ids"] = slot_allowed_by_index.get(
            slot_index,
            sorted(int(value) for value in all_signatures),
        )
    dp_entries, feasible, failure = _monotonic_dp(slot_allowed)
    constrained_slots = [
        {
            "slot_index": int(index),
            "allowed_signature_ids": sorted(int(value) for value in values),
        }
        for index, values in enumerate(slot_allowed)
        if set(values) != all_signatures
    ]
    return {
        "target_group": {
            "group_id": str(group_id),
            "present": True,
            "facility_type": group_map.get("facility_type"),
            "operation_type": group_map.get("operation_type"),
            "required_count": int(group_map.get("count", len(slot_specs))),
            "slot_count": int(len(slot_specs)),
            "signature_ids": sorted(int(value) for value in all_signatures),
        },
        "monotonicity": {
            "evaluated": True,
            "outcome": "monotonic_feasible" if feasible else "monotonic_infeasible",
            "label_count": int(len(labels)),
            "applied_label_count": int(sum(1 for entry in label_entries if bool(entry.get("applied")))),
            "constrained_slot_count": int(len(constrained_slots)),
            "constrained_slots": constrained_slots,
            "slot_constraint_implications": slot_constraint_entries,
            "label_implications": label_entries,
            "dp": dp_entries,
            "failure": failure,
        },
    }


def render_phase3b_signature_monotonic_forced_label_audit_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    target = _mapping(report.get("target_group"))
    mono = _mapping(report.get("monotonicity"))
    lines = [
        "# Phase 3B Signature Monotonic Forced-Label Audit",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Group: {target.get('group_id')}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "- Diagnostic semantics: no_solve_signature_monotonic_forced_label_audit_not_proof_source",
        "- Solver invoked: false",
        "",
        "| Slot | Allowed Signature IDs |",
        "| ---: | --- |",
    ]
    for slot in list(mono.get("constrained_slots", [])):
        if isinstance(slot, Mapping):
            lines.append(
                f"| {slot.get('slot_index')} | {', '.join(str(v) for v in list(slot.get('allowed_signature_ids', [])))} |"
            )
    failure = _mapping(mono.get("failure"))
    if failure:
        lines.extend(
            [
                "",
                f"- Failure slot: {failure.get('slot_index')}",
                f"- Previous feasible signatures: {failure.get('previous_possible_signature_ids')}",
                f"- Current allowed signatures: {failure.get('current_allowed_signature_ids')}",
            ]
        )
    return "\n".join(lines) + "\n"


def render_phase3b_signature_monotonic_forced_label_audit_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    target = _mapping(report.get("target_group"))
    mono = _mapping(report.get("monotonicity"))
    return "\n".join(
        [
            "Phase 3B signature monotonic forced-label audit",
            f"group_id={target.get('group_id')}",
            f"outcome={status.get('outcome')}",
            f"recommendation={status.get('recommendation')}",
            "solver_invoked=false",
            "diagnostic_semantics=no_solve_signature_monotonic_forced_label_audit_not_proof_source",
            f"label_count={mono.get('label_count')}",
            f"constrained_slot_count={mono.get('constrained_slot_count')}",
        ]
    ) + "\n"


def write_phase3b_signature_monotonic_forced_label_audit(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str,
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    _atomic_write_text(md_path, render_phase3b_signature_monotonic_forced_label_audit_markdown(report))
    _atomic_write_text(txt_path, render_phase3b_signature_monotonic_forced_label_audit_text(report))
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _not_evaluated(group_id: str, outcome: str) -> Dict[str, Any]:
    return {
        "target_group": {"group_id": str(group_id), "present": False},
        "monotonicity": {"evaluated": False, "outcome": str(outcome)},
    }


def _status_from_monotonicity(monotonicity: Mapping[str, Any]) -> Dict[str, Any]:
    outcome = str(monotonicity.get("outcome", "not_evaluated"))
    if outcome == "monotonic_infeasible":
        return {
            "completed": True,
            "outcome": outcome,
            "recommendation": "Forced labels imply no nondecreasing signature assignment; promote only through a guarded exact-safe precheck spec.",
        }
    if outcome == "monotonic_feasible":
        return {
            "completed": True,
            "outcome": outcome,
            "recommendation": "Signature monotonicity does not explain this subset; inspect signature counts or other families.",
        }
    return {
        "completed": True,
        "outcome": outcome,
        "recommendation": "Audit did not evaluate; inspect target group and core labels.",
    }


def _checks(report: Mapping[str, Any]) -> list[Dict[str, Any]]:
    status = _mapping(report.get("status"))
    mono = _mapping(report.get("monotonicity"))
    return [
        _check("solver_not_invoked", "pass", "audit uses tuple implication and dynamic programming only"),
        _check("audit_completed", "pass" if bool(status.get("completed")) else "fail", str(status.get("outcome"))),
        _check(
            "monotonicity_evaluated",
            "pass" if bool(mono.get("evaluated", False)) else "fail",
            str(mono.get("outcome")),
        ),
    ]


def _parse_candidate(candidate: str) -> Dict[str, int]:
    left, right = str(candidate).lower().split("x", 1)
    w = int(left)
    h = int(right)
    return {"w": w, "h": h, "area": int(w * h)}


def _find_group(model: Any, group_id: str) -> Optional[Mapping[str, Any]]:
    for group in list(getattr(model, "_mandatory_groups", [])):
        if str(_mapping(group).get("group_id")) == str(group_id):
            return _mapping(group)
    return None


def _signature_ids_for_slot(slot: Any) -> set[int]:
    return {int(value) for value in dict(getattr(slot, "signature_id_to_bucket_id", {})).keys()}


def _bucket_rows(delegate: Any, group_id: str, template: str) -> Dict[int, list[tuple[int, int, int]]]:
    slots = list(getattr(delegate, "mandatory_slots", {}).get(str(group_id), []))
    if not slots:
        return {}
    bucket_to_int = {
        str(bucket_id): int(bucket_int)
        for bucket_int, bucket_id in dict(getattr(slots[0], "signature_id_to_bucket_id", {})).items()
    }
    pose_tuple_by_idx = dict(getattr(delegate, "_template_pose_tuple_by_idx", {}).get(str(template), {}))
    bucket_pose_indices = dict(
        getattr(delegate, "_mandatory_group_bucket_pose_indices", {}).get(str(group_id), {})
    )
    rows: Dict[int, list[tuple[int, int, int]]] = {}
    for bucket_id, pose_indices in bucket_pose_indices.items():
        if str(bucket_id) not in bucket_to_int:
            continue
        signature_id = int(bucket_to_int[str(bucket_id)])
        rows[signature_id] = []
        for pose_idx in list(pose_indices):
            pose_tuple = pose_tuple_by_idx.get(int(pose_idx))
            if pose_tuple is None:
                continue
            x_val, y_val, mode_id = pose_tuple
            rows[signature_id].append((int(x_val), int(y_val), int(mode_id)))
    return rows


def _row_matches(row: tuple[int, int, int], field: str, value: int) -> bool:
    index = {"x": 0, "y": 1, "mode": 2}[str(field)]
    return int(row[index]) == int(value)


def _monotonic_dp(slot_allowed: Sequence[set[int]]) -> tuple[list[Dict[str, Any]], bool, Optional[Dict[str, Any]]]:
    possible: Optional[set[int]] = None
    entries: list[Dict[str, Any]] = []
    for slot_index, allowed in enumerate(slot_allowed):
        current_allowed = set(int(value) for value in allowed)
        if possible is None:
            current_possible = set(current_allowed)
        else:
            current_possible = {
                current
                for current in current_allowed
                if any(previous <= current for previous in possible)
            }
        entry = {
            "slot_index": int(slot_index),
            "allowed_signature_ids": sorted(current_allowed),
            "possible_signature_ids": sorted(current_possible),
        }
        entries.append(entry)
        if not current_possible:
            failure = {
                "slot_index": int(slot_index),
                "previous_possible_signature_ids": sorted(possible or []),
                "current_allowed_signature_ids": sorted(current_allowed),
            }
            return entries, False, failure
        possible = current_possible
    return entries, True, None


def _int_or_none(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)
