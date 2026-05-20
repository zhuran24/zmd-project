from __future__ import annotations

import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

from ortools.sat.python import cp_model

from src.models._cpsat_compat import cp_model_from_proto
from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    _clone_model_proto,
)
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso
from src.search.phase3b.coordinate_validation.direct_equality_core import (
    DEFAULT_DIRECT_EQUALITY_CORE_GROUP_ID,
)
from src.search.phase3b.coordinate_validation.group_delta import (
    _build_delta_context,
    _candidate_rect,
    _check,
    _mapping,
    _normalize_solver_profile,
)
from src.search.phase3b.coordinate_validation.x_domain_order_audit import (
    _load_t24_core_labels,
)
from src.search.phase3b.forced_anchor.model_slice import (
    _constraint_has_field,
    _constraint_var_indices,
    _delete_constraint_indices,
    _first_line,
    _response_stats_payload,
)

COORDINATE_VALIDATION_GLOBAL_FAMILY_DELTA_SOURCE = (
    "phase3b_coordinate_validation_global_family_delta_v1"
)

DEFAULT_GLOBAL_FAMILY_DELTA_GROUP_ID = DEFAULT_DIRECT_EQUALITY_CORE_GROUP_ID

DEFAULT_GLOBAL_FAMILY_DELTA_VARIANTS = (
    "base_12_key_full_model",
    "remove_slot_order_monotonic",
    "remove_mandatory_signature_count",
    "remove_mandatory_signature_membership_or_bucket",
    "remove_required_optional_signature_count",
    "remove_power_coverage",
    "remove_protocol_storage_interaction",
    "remove_no_overlap_2d",
    "remove_domain_tables_for_target_group",
)


def build_phase3b_coordinate_validation_global_family_delta(
    project_root: Path,
    *,
    candidate: str = "67x13",
    anchor_idx: int = 119,
    group_id: str = DEFAULT_GLOBAL_FAMILY_DELTA_GROUP_ID,
    core_json: Optional[Path] = None,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    time_limit_seconds: float = 2.0,
    worker_count: int = 1,
    variants: Optional[Sequence[str]] = None,
    solver_parameter_profile: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    normalized_group_id = str(group_id).strip()
    normalized_variants = _normalize_variants(variants or DEFAULT_GLOBAL_FAMILY_DELTA_VARIANTS)
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
    core_labels = list(core_payload.get("labels", []))
    context: Dict[str, Any] = {}
    base_payload: Dict[str, Any] = {}
    proto_profile: Dict[str, Any] = {}
    entries: list[Dict[str, Any]] = []
    model_error: Optional[str] = None

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
            raise ValueError(f"Unknown global-family delta group id: {normalized_group_id}")
        model = context["model"]
        delegate = getattr(model, "_coordinate_delegate", None)
        if delegate is None:
            raise RuntimeError("Coordinate delegate unavailable")
        base_payload = _build_12_key_base_proto(
            model=model,
            delegate=delegate,
            group_id=normalized_group_id,
            labels=core_labels,
        )
        base_proto = base_payload["base_proto"]
        proto_profile = _proto_profile(base_proto)
        for variant in normalized_variants:
            entries.append(
                _evaluate_global_family_variant(
                    base_proto=base_proto,
                    variant=str(variant),
                    group_id=normalized_group_id,
                    delegate=delegate,
                    time_limit_seconds=float(time_limit_seconds),
                    worker_count=int(worker_count),
                    solver_profile=solver_profile,
                )
            )
        entries = _annotate_status_changes(entries)
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"

    status = _status_from_entries(entries, model_error=model_error)
    return {
        "metadata": {
            "source": COORDINATE_VALIDATION_GLOBAL_FAMILY_DELTA_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "coordinate_validation_global_family_delta_not_proof_source"
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
            "variants": list(normalized_variants),
            "solver_parameter_profile": dict(solver_profile),
        },
        "artifact_hashes": dict(artifact_hashes),
        "artifact_hash_error": artifact_hash_error,
        "core_input": {
            key: value
            for key, value in dict(core_payload).items()
            if key != "labels"
        }
        | {"label_count": len(core_labels)},
        "context": {
            "ghost_anchor_count": int(context.get("ghost_anchor_count", 0)),
            "blocked_cell_count": int(context.get("blocked_cell_count", 0)),
            "ordered_group_count": int(context.get("ordered_group_count", 0)),
        },
        "base_model": {
            key: value
            for key, value in dict(base_payload).items()
            if key != "base_proto"
        },
        "proto_profile": proto_profile,
        "status": status,
        "delta": {
            "entries": entries,
            "status_counts": _status_counts(entries),
            "evaluated_variants": [
                str(entry.get("variant"))
                for entry in entries
                if bool(entry.get("evaluated", False))
            ],
            "skipped_variants": [
                {
                    "variant": str(entry.get("variant")),
                    "skip_reason": entry.get("skip_reason"),
                }
                for entry in entries
                if not bool(entry.get("evaluated", False))
            ],
            "first_status_change": _first_status_change(entries),
            "first_unlocking_variant": _first_unlocking_variant(entries),
            "implicated_families": _implicated_families(entries),
        },
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "checks": _checks(status=status, entries=entries, model_error=model_error),
    }


def render_phase3b_coordinate_validation_global_family_delta_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    delta = _mapping(report.get("delta"))
    base = _mapping(report.get("base_model"))
    first_change = _mapping(delta.get("first_status_change"))
    lines = [
        "# Phase 3B Coordinate Validation Global Constraint Family Delta",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Anchor: {candidate.get('anchor_idx')}",
        "- Diagnostic semantics: coordinate_validation_global_family_delta_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Forced equality count: {base.get('forced_equality_count')}",
        f"- Base variant status: {status.get('base_status')}",
        f"- First status change: {first_change.get('variant')}",
        f"- Implicated families: {delta.get('implicated_families')}",
        "",
        "## Variant Matrix",
        "",
        "| Variant | Status | Evaluated | Removed | Confidence | Changed | Semantic Weakening |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for entry in list(delta.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        selector = _mapping(entry.get("selector_summary"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("variant")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(entry.get("evaluated")),
                    _markdown_cell(selector.get("removed_constraint_count")),
                    _markdown_cell(selector.get("selector_confidence")),
                    _markdown_cell(entry.get("changes_base_status")),
                    _markdown_cell(entry.get("semantic_weakening")),
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


def render_phase3b_coordinate_validation_global_family_delta_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    delta = _mapping(report.get("delta"))
    lines = [
        "Phase 3B coordinate validation global family delta",
        f"outcome={status.get('outcome')}",
        f"base_status={status.get('base_status')}",
        f"recommendation={status.get('recommendation')}",
        f"implicated_families={delta.get('implicated_families')}",
    ]
    for entry in list(delta.get("entries", [])):
        if isinstance(entry, Mapping):
            selector = _mapping(entry.get("selector_summary"))
            lines.append(
                "entry "
                f"variant={entry.get('variant')} "
                f"status={entry.get('status')} "
                f"evaluated={entry.get('evaluated')} "
                f"removed={selector.get('removed_constraint_count')} "
                f"changed={entry.get('changes_base_status')}"
            )
    return "\n".join(lines) + "\n"


def _build_12_key_base_proto(
    *,
    model: Any,
    delegate: Any,
    group_id: str,
    labels: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    local_model = cp_model_from_proto(_clone_model_proto(model.model.Proto()))
    slot_specs = list(getattr(delegate, "mandatory_slots", {}).get(str(group_id), []))
    forced: list[Dict[str, Any]] = []
    skipped: list[Dict[str, Any]] = []
    for label in labels:
        slot_index = int(label.get("slot_index", -1))
        field = str(label.get("field", ""))
        if not (0 <= slot_index < len(slot_specs)):
            skipped.append({"label": dict(label), "reason": "slot_index_out_of_range"})
            continue
        slot = slot_specs[slot_index]
        var = {"x": getattr(slot, "x", None), "y": getattr(slot, "y", None), "mode": getattr(slot, "mode", None)}.get(field)
        if var is None:
            skipped.append({"label": dict(label), "reason": "field_var_unavailable"})
            continue
        forced_value = int(label.get("forced_value", 0))
        local_model.Add(local_model.GetIntVarFromProtoIndex(int(var.Index())) == forced_value)
        forced.append(
            {
                "stable_key": str(label.get("stable_key")),
                "slot_index": slot_index,
                "field": field,
                "forced_value": forced_value,
                "var_index": int(var.Index()),
            }
        )
    return {
        "base_proto": _clone_model_proto(local_model.Proto()),
        "forced_equality_count": int(len(forced)),
        "forced_equalities": forced,
        "skipped_equality_count": int(len(skipped)),
        "skipped_equalities": skipped,
        "constraint_count_after_forcing": int(len(local_model.Proto().constraints)),
        "variable_count": int(len(local_model.Proto().variables)),
    }


def _evaluate_global_family_variant(
    *,
    base_proto: Any,
    variant: str,
    group_id: str,
    delegate: Any,
    time_limit_seconds: float,
    worker_count: int,
    solver_profile: Mapping[str, Any],
) -> Dict[str, Any]:
    local_proto = _clone_model_proto(base_proto)
    selector = _apply_global_family_variant_selector(
        local_proto,
        variant=str(variant),
        group_id=str(group_id),
    )
    if bool(selector.get("skipped", False)):
        return {
            "variant": str(variant),
            "evaluated": False,
            "status": "SKIPPED",
            "skip_reason": selector.get("skip_reason"),
            "selector_summary": selector,
            "semantic_weakening": bool(selector.get("semantic_weakening", True)),
            "proof_evidence": False,
            "changes_base_status": False,
        }
    local_model = cp_model_from_proto(local_proto)
    if str(variant) == "replace_target_mandatory_region_with_exact_signature_table":
        table_summary = _add_target_mandatory_signature_table_channel(
            local_model,
            delegate=delegate,
            group_id=str(group_id),
        )
        selector["diagnostic_reformulation"] = True
        selector["semantic_weakening"] = not bool(table_summary.get("added", False))
        selector["added_table_constraint_count"] = int(
            table_summary.get("added_table_constraint_count", 0)
        )
        selector["added_table_row_count"] = int(table_summary.get("added_table_row_count", 0))
        selector["table_channel_summary"] = dict(table_summary)
    solver = cp_model.CpSolver()
    applied_profile = _apply_delta_solver_profile(
        solver,
        time_limit_seconds=float(time_limit_seconds),
        worker_count=int(worker_count),
        profile=solver_profile,
    )
    started = time.perf_counter()
    status = solver.Solve(local_model)
    response_stats = solver.ResponseStats()
    return {
        "variant": str(variant),
        "evaluated": True,
        "status": solver.StatusName(status),
        "accepted": status in {cp_model.OPTIMAL, cp_model.FEASIBLE},
        "elapsed_seconds": float(time.perf_counter() - started),
        "wall_time": float(solver.WallTime()),
        "user_time": float(solver.UserTime()),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "deterministic_time": float(
            _response_stats_payload(response_stats).get("deterministic_time", 0.0)
        ),
        "selector_summary": selector,
        "semantic_weakening": bool(selector.get("semantic_weakening", True)),
        "proof_evidence": False,
        "solver_parameter_profile": applied_profile,
        "response_summary": _first_line(response_stats),
        "response_stats_parsed": _response_stats_payload(response_stats),
    }


def _apply_global_family_variant_selector(
    model_proto: Any,
    *,
    variant: str,
    group_id: str,
) -> Dict[str, Any]:
    variant_text = str(variant)
    if variant_text == "base_12_key_full_model":
        return _selector_summary(
            variant=variant_text,
            removed_indices=[],
            confidence="high",
            mode="base_no_removal",
            semantic_weakening=False,
            skipped=False,
            examples=[],
        )
    selectors: Dict[str, tuple[str, str, Callable[[Any, Sequence[str], str], bool]]] = {
        "remove_slot_order_monotonic": (
            "high",
            "linear constraints linking adjacent order_key__ variables",
            lambda c, names, gid: _constraint_kind(c) == "linear"
            and sum(str(name).startswith("order_key__") for name in names) >= 2,
        ),
        "remove_mandatory_signature_count": (
            "high",
            "constraints involving mandatory signature count variables",
            lambda c, names, gid: any(
                str(name).startswith(("group_signature_count__", "sig_count__"))
                for name in names
            ),
        ),
        "remove_mandatory_signature_membership_or_bucket": (
            "medium",
            "mandatory signature, region, and is_sig membership/bucket constraints",
            lambda c, names, gid: any(
                str(name).startswith(("signature__group::", "region__group::", "is_sig__group::"))
                for name in names
            ),
        ),
        "remove_target_mandatory_signature_membership_or_bucket": (
            "medium",
            "target mandatory group signature, region, and is_sig membership/bucket constraints",
            lambda c, names, gid: any(
                _is_target_mandatory_signature_membership_name(name, gid)
                for name in names
            ),
        ),
        "remove_other_mandatory_signature_membership_or_bucket": (
            "medium",
            "non-target mandatory group signature, region, and is_sig membership/bucket constraints",
            lambda c, names, gid: any(
                _is_other_mandatory_signature_membership_name(name, gid)
                for name in names
            ),
        ),
        "remove_target_mandatory_signature_var": (
            "medium",
            "target mandatory group signature__ variable constraints",
            lambda c, names, gid: any(
                str(name).startswith(f"signature__{gid}") for name in names
            ),
        ),
        "remove_target_mandatory_is_sig_bucket": (
            "medium",
            "target mandatory group is_sig__ bucket membership constraints",
            lambda c, names, gid: any(
                str(name).startswith(f"is_sig__{gid}") for name in names
            ),
        ),
        "remove_target_mandatory_region": (
            "medium",
            "target mandatory group region__ bucket geometry constraints",
            lambda c, names, gid: any(
                str(name).startswith(f"region__{gid}") for name in names
            ),
        ),
        "replace_target_mandatory_region_with_exact_signature_table": (
            "medium",
            "target mandatory group region__ constraints replaced with exact [x,y,mode,signature] table channel",
            lambda c, names, gid: any(
                str(name).startswith(f"region__{gid}") for name in names
            ),
        ),
        "remove_required_optional_signature_count": (
            "high",
            "constraints involving required-optional signature count variables",
            lambda c, names, gid: any(
                str(name).startswith(("required_optional_signature_count__", "req_opt_sig_count__"))
                for name in names
            ),
        ),
        "remove_power_coverage": (
            "medium",
            "constraints using cover_choice or cover_lit power coverage variables",
            lambda c, names, gid: any(
                str(name).startswith(("cover_choice_", "cover_lit__", "covers__"))
                for name in names
            ),
        ),
        "remove_protocol_storage_interaction": (
            "low",
            "protocol_storage_box constraints that also touch power/family/coverage variables",
            lambda c, names, gid: any("protocol_storage_box" in str(name) for name in names)
            and any(
                str(name).startswith(
                    (
                        "cover_choice_",
                        "cover_lit__",
                        "family__",
                        "is_family__",
                        "d_lo__",
                        "d_hi__",
                        "active__residual_optional::power_pole",
                        "x__residual_optional::power_pole",
                        "y__residual_optional::power_pole",
                    )
                )
                for name in names
            ),
        ),
        "remove_no_overlap_2d": (
            "high",
            "all no_overlap_2d constraints",
            lambda c, names, gid: _constraint_kind(c) == "no_overlap_2d",
        ),
        "remove_domain_tables_for_target_group": (
            "high",
            "table constraints involving the target mandatory group variables",
            lambda c, names, gid: _constraint_kind(c) == "table"
            and any(str(gid) in str(name) for name in names),
        ),
    }
    if variant_text not in selectors:
        return _selector_summary(
            variant=variant_text,
            removed_indices=[],
            confidence="none",
            mode="unsupported_variant",
            semantic_weakening=True,
            skipped=True,
            skip_reason=f"unsupported variant: {variant_text}",
            examples=[],
        )
    confidence, mode, predicate = selectors[variant_text]
    var_names = _proto_var_names(model_proto)
    remove_indices: list[int] = []
    examples: list[Dict[str, Any]] = []
    for constraint_idx, constraint in enumerate(list(getattr(model_proto, "constraints", []))):
        names = _constraint_names(constraint, var_names)
        if not predicate(constraint, names, str(group_id)):
            continue
        remove_indices.append(int(constraint_idx))
        if len(examples) < 5:
            examples.append(
                {
                    "constraint_idx": int(constraint_idx),
                    "kind": _constraint_kind(constraint),
                    "variable_names": [str(name) for name in names[:10]],
                }
            )
    if remove_indices:
        _delete_constraint_indices(model_proto, remove_indices)
    skipped = bool(variant_text != "base_12_key_full_model" and not remove_indices)
    return _selector_summary(
        variant=variant_text,
        removed_indices=remove_indices,
        confidence=confidence,
        mode=mode,
        semantic_weakening=True,
        skipped=skipped,
        skip_reason="selector_matched_no_constraints" if skipped else None,
        examples=examples,
        kind_counts=_removed_kind_counts_from_examples(examples, len(remove_indices)),
    )


def _is_mandatory_signature_membership_name(name: Any) -> bool:
    text = str(name)
    return text.startswith(("signature__group::", "region__group::", "is_sig__group::"))


def _is_target_mandatory_signature_membership_name(name: Any, group_id: str) -> bool:
    text = str(name)
    return _is_mandatory_signature_membership_name(text) and text.startswith(
        (
            f"signature__{group_id}",
            f"region__{group_id}",
            f"is_sig__{group_id}",
        )
    )


def _is_other_mandatory_signature_membership_name(name: Any, group_id: str) -> bool:
    text = str(name)
    return _is_mandatory_signature_membership_name(text) and not _is_target_mandatory_signature_membership_name(
        text,
        group_id,
    )


def _add_target_mandatory_signature_table_channel(
    local_model: Any,
    *,
    delegate: Any,
    group_id: str,
) -> Dict[str, Any]:
    slot_specs = list(getattr(delegate, "mandatory_slots", {}).get(str(group_id), []))
    if not slot_specs:
        return {
            "added": False,
            "skip_reason": "target_slots_missing",
            "added_table_constraint_count": 0,
            "added_table_row_count": 0,
        }
    table_rows = _target_mandatory_signature_table_rows(delegate, str(group_id))
    if not table_rows:
        return {
            "added": False,
            "skip_reason": "target_signature_table_rows_missing",
            "added_table_constraint_count": 0,
            "added_table_row_count": 0,
        }
    added = 0
    for slot in slot_specs:
        signature = getattr(slot, "signature", None)
        if signature is None:
            return {
                "added": False,
                "skip_reason": "target_slot_signature_var_missing",
                "added_table_constraint_count": int(added),
                "added_table_row_count": int(added * len(table_rows)),
            }
        local_model.AddAllowedAssignments(
            [
                local_model.GetIntVarFromProtoIndex(int(getattr(slot, "x").Index())),
                local_model.GetIntVarFromProtoIndex(int(getattr(slot, "y").Index())),
                local_model.GetIntVarFromProtoIndex(int(getattr(slot, "mode").Index())),
                local_model.GetIntVarFromProtoIndex(int(signature.Index())),
            ],
            table_rows,
        )
        added += 1
    return {
        "added": True,
        "skip_reason": None,
        "slot_count": int(len(slot_specs)),
        "table_row_count_per_slot": int(len(table_rows)),
        "added_table_constraint_count": int(added),
        "added_table_row_count": int(added * len(table_rows)),
    }


def _target_mandatory_signature_table_rows(delegate: Any, group_id: str) -> list[list[int]]:
    slot_specs = list(getattr(delegate, "mandatory_slots", {}).get(str(group_id), []))
    if not slot_specs:
        return []
    template = str(getattr(slot_specs[0], "template", ""))
    pose_tuple_by_idx = dict(getattr(delegate, "_template_pose_tuple_by_idx", {}).get(template, {}))
    int_to_bucket = dict(getattr(slot_specs[0], "signature_id_to_bucket_id", {}))
    bucket_to_int = {str(bucket_id): int(bucket_int) for bucket_int, bucket_id in int_to_bucket.items()}
    bucket_pose_indices = dict(
        getattr(delegate, "_mandatory_group_bucket_pose_indices", {}).get(str(group_id), {})
    )
    rows: set[tuple[int, int, int, int]] = set()
    for bucket_id, pose_indices in bucket_pose_indices.items():
        if str(bucket_id) not in bucket_to_int:
            continue
        bucket_int = int(bucket_to_int[str(bucket_id)])
        for pose_idx in list(pose_indices):
            pose_tuple = pose_tuple_by_idx.get(int(pose_idx))
            if pose_tuple is None:
                continue
            x_val, y_val, mode_id = pose_tuple
            rows.add((int(x_val), int(y_val), int(mode_id), int(bucket_int)))
    return [list(row) for row in sorted(rows)]


def _selector_summary(
    *,
    variant: str,
    removed_indices: Sequence[int],
    confidence: str,
    mode: str,
    semantic_weakening: bool,
    skipped: bool,
    examples: Sequence[Mapping[str, Any]],
    skip_reason: Optional[str] = None,
    kind_counts: Optional[Mapping[str, int]] = None,
) -> Dict[str, Any]:
    return {
        "variant": str(variant),
        "removed_constraint_count": int(len(removed_indices)),
        "removed_constraint_indices_sample": [int(index) for index in list(removed_indices)[:20]],
        "selector_confidence": str(confidence),
        "selector_mode": str(mode),
        "semantic_weakening": bool(semantic_weakening),
        "proof_evidence": False,
        "skipped": bool(skipped),
        "skip_reason": skip_reason,
        "examples": [dict(example) for example in examples],
        "removed_kind_counts": dict(kind_counts or {}),
    }


def _removed_kind_counts_from_examples(
    examples: Sequence[Mapping[str, Any]],
    removed_count: int,
) -> Dict[str, int]:
    if removed_count <= 0:
        return {}
    counts = Counter(str(example.get("kind", "")) for example in examples)
    if len(examples) < removed_count and len(counts) == 1:
        key = next(iter(counts))
        return {str(key): int(removed_count)}
    return {str(key): int(value) for key, value in sorted(counts.items())}


def _apply_delta_solver_profile(
    solver: Any,
    *,
    time_limit_seconds: float,
    worker_count: int,
    profile: Mapping[str, Any],
) -> Dict[str, Any]:
    normalized = dict(profile or {})
    solver.parameters.max_time_in_seconds = max(0.001, float(time_limit_seconds))
    solver.parameters.num_search_workers = max(
        1,
        int(normalized.get("worker_count", worker_count)),
    )
    solver.parameters.search_branching = cp_model.FIXED_SEARCH
    if "random_seed" in normalized:
        solver.parameters.random_seed = int(normalized["random_seed"])
    if "randomize_search" in normalized:
        solver.parameters.randomize_search = bool(normalized["randomize_search"])
    if "cp_model_presolve" in normalized:
        solver.parameters.cp_model_presolve = bool(normalized["cp_model_presolve"])
    return {
        **normalized,
        "time_limit_seconds": float(time_limit_seconds),
        "worker_count": int(solver.parameters.num_search_workers),
        "search_branching": "fixed",
    }


def _status_from_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    model_error: Optional[str],
) -> Dict[str, Any]:
    if model_error is not None:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "diagnostic_error",
            "base_status": None,
            "recommendation": "Global family delta failed; inspect model_error.",
        }
    base = _base_entry(entries)
    base_status = None if base is None else str(base.get("status"))
    first_unlocking = _first_unlocking_variant(entries)
    if base is None or not bool(base.get("evaluated", False)):
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "base_not_evaluated",
            "base_status": base_status,
            "recommendation": "Base 12-key full-model variant did not evaluate.",
        }
    if base_status != "INFEASIBLE":
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "base_not_infeasible",
            "base_status": base_status,
            "recommendation": "Base 12-key full-model status was not INFEASIBLE; refresh T24/T25 core before interpreting variants.",
        }
    if first_unlocking is not None:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "family_delta_unlocking_variant_found",
            "base_status": base_status,
            "recommendation": (
                "At least one semantic-weakening variant changed the 12-key base away "
                "from INFEASIBLE; inspect first_unlocking_variant and selector confidence."
            ),
        }
    if _first_status_change(entries) is not None:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "family_delta_status_changed_nonterminal",
            "base_status": base_status,
            "recommendation": "A variant changed status away from INFEASIBLE but did not prove feasibility within the bounded diagnostic run.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "family_delta_no_status_change",
        "base_status": base_status,
        "recommendation": "Minimum global-family variants did not change the 12-key INFEASIBLE status; refine selectors or shrink further.",
    }


def _checks(
    *,
    status: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    evaluated = [entry for entry in entries if bool(entry.get("evaluated", False))]
    skipped = [entry for entry in entries if not bool(entry.get("evaluated", False))]
    return [
        _check(
            "base_status_infeasible",
            "pass" if status.get("base_status") == "INFEASIBLE" else "fail",
            f"base_status={status.get('base_status')}",
        ),
        _check(
            "variants_evaluated",
            "pass" if len(evaluated) > 0 else "fail",
            f"evaluated={len(evaluated)} skipped={len(skipped)}",
        ),
        _check(
            "semantic_weakening_marked",
            "pass"
            if all(
                (str(entry.get("variant")) == "base_12_key_full_model")
                or bool(entry.get("semantic_weakening", False))
                for entry in entries
            )
            else "fail",
            "all non-base entries mark semantic weakening",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _first_status_change(entries: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    base = _base_entry(entries)
    if base is None:
        return None
    base_status = str(base.get("status"))
    for entry in entries:
        if not bool(entry.get("evaluated", False)):
            continue
        if str(entry.get("variant")) == "base_12_key_full_model":
            continue
        if str(entry.get("status")) != base_status:
            return {
                "variant": str(entry.get("variant")),
                "status": str(entry.get("status")),
                "base_status": base_status,
                "selector_confidence": _mapping(entry.get("selector_summary")).get("selector_confidence"),
            }
    return None


def _annotate_status_changes(
    entries: Sequence[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    base = _base_entry(entries)
    base_status = None if base is None else str(base.get("status"))
    annotated: list[Dict[str, Any]] = []
    for entry in entries:
        payload = dict(entry)
        if not bool(payload.get("evaluated", False)) or base_status is None:
            payload["changes_base_status"] = False
        elif str(payload.get("variant")) == "base_12_key_full_model":
            payload["changes_base_status"] = False
        else:
            payload["changes_base_status"] = str(payload.get("status")) != base_status
        annotated.append(payload)
    return annotated


def _first_unlocking_variant(entries: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    first_change = _first_status_change(entries)
    if first_change is None:
        return None
    if str(first_change.get("status")) not in {"OPTIMAL", "FEASIBLE"}:
        return None
    return dict(first_change)


def _implicated_families(entries: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    base = _base_entry(entries)
    if base is None or str(base.get("status")) != "INFEASIBLE":
        return []
    result: list[Dict[str, Any]] = []
    for entry in entries:
        if not bool(entry.get("evaluated", False)):
            continue
        if str(entry.get("variant")) == "base_12_key_full_model":
            continue
        if str(entry.get("status")) == "INFEASIBLE":
            continue
        selector = _mapping(entry.get("selector_summary"))
        result.append(
            {
                "variant": str(entry.get("variant")),
                "status": str(entry.get("status")),
                "selector_confidence": selector.get("selector_confidence"),
                "removed_constraint_count": selector.get("removed_constraint_count"),
            }
        )
    return result


def _base_entry(entries: Sequence[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    for entry in entries:
        if str(entry.get("variant")) == "base_12_key_full_model":
            return entry
    return None


def _status_counts(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("status", "UNKNOWN"))
        counts[status] = int(counts.get(status, 0)) + 1
    return dict(sorted(counts.items()))


def _proto_profile(model_proto: Any) -> Dict[str, Any]:
    constraints = list(getattr(model_proto, "constraints", []))
    kind_counts = Counter(_constraint_kind(constraint) for constraint in constraints)
    var_names = _proto_var_names(model_proto)
    prefix_counts: Dict[str, int] = {}
    for prefix in (
        "order_key__",
        "group_signature_count__",
        "required_optional_signature_count__",
        "is_sig__",
        "is_req_sig__",
        "signature__",
        "cover_choice_",
        "family__",
    ):
        prefix_counts[prefix] = sum(1 for name in var_names.values() if str(name).startswith(prefix))
    return {
        "variable_count": int(len(getattr(model_proto, "variables", []))),
        "constraint_count": int(len(constraints)),
        "constraint_kind_counts": {str(key): int(value) for key, value in sorted(kind_counts.items())},
        "variable_prefix_counts": dict(sorted(prefix_counts.items())),
    }


def _constraint_kind(constraint: Any) -> str:
    kinds = [
        field_name
        for field_name in (
            "bool_or",
            "bool_and",
            "linear",
            "element",
            "table",
            "interval",
            "no_overlap_2d",
            "lin_max",
        )
        if _constraint_has_field(constraint, field_name)
    ]
    return "+".join(kinds) if kinds else "empty"


def _proto_var_names(model_proto: Any) -> Dict[int, str]:
    return {
        int(index): str(getattr(var, "name", ""))
        for index, var in enumerate(list(getattr(model_proto, "variables", [])))
    }


def _constraint_names(constraint: Any, var_names: Mapping[int, str]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for raw_idx in _constraint_var_indices(constraint):
        idx = abs(int(raw_idx))
        name = str(var_names.get(idx, ""))
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _normalize_variants(variants: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in variants:
        token = str(raw).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        result.append(token)
    return tuple(result or DEFAULT_GLOBAL_FAMILY_DELTA_VARIANTS)


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")
