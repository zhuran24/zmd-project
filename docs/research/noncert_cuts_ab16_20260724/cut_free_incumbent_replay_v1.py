#!/usr/bin/env python3
"""Independently replay one fixed assignment on a cut-free binary model.

The checker reads the model, metadata and incumbent on stable O_NOFOLLOW
descriptors, parses the official binary protobuf, independently maps every
incumbent record to the production coordinate/C1/ghost variable face, and
solves a fresh model with those placements fixed.  It does not import the
baseline builder or an organic arm runner.  It reuses only the package-pinned admission module's
tracked-clean-checkout provenance validator.

The model metadata and this receipt share one exact package-bound repository
checkout provenance record.  Its campaign root, package, Git tool, pinned HEAD
and three baseline inputs are replayed before and after the solve.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

import baseline_admission_v1 as baseline_contract
from google.protobuf import text_format
from ortools.sat import cp_model_pb2
from ortools.sat.python import cp_model


SCHEMA = baseline_contract.REPLAY_SCHEMA
METADATA_SCHEMA = baseline_contract.METADATA_SCHEMA
PURPOSE = "strict_ab16_incumbent_fixed_assignment_replay"
VERDICT = "INCUMBENT_FIXED_ASSIGNMENT_REPLAY_PASS"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
METADATA_KEYS = {
    "builder_identity",
    "campaign_provenance",
    "canonical_binary",
    "created_at_utc",
    "errors",
    "global_claim_authorized",
    "historical_model_text_sha256",
    "input_identities",
    "legacy_control_used_as_build_input",
    "model_backend",
    "model_binary_format",
    "model_constraint_count",
    "model_identity",
    "model_variable_count",
    "purpose",
    "schema_version",
    "status",
}


class ReplayError(RuntimeError):
    """The cut-free fixed-assignment replay failed closed."""


def _pairs(items: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ReplayError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _authority_json(value: object) -> bytes:
    return _canonical(value) + b"\n"


def _snapshot(path: Path, *, limit: int) -> tuple[bytes, dict[str, object]]:
    absolute = path.absolute()
    current = Path("/")
    for part in absolute.parts[1:]:
        current /= part
        metadata = os.lstat(current)
        if stat.S_ISLNK(metadata.st_mode):
            raise ReplayError(f"symlink component rejected: {current}")
    flags = os.O_RDONLY | os.O_CLOEXEC
    if not hasattr(os, "O_NOFOLLOW"):
        raise ReplayError("O_NOFOLLOW is unavailable")
    descriptor = os.open(absolute, flags | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
            raise ReplayError(f"invalid input file: {absolute}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    def signature(item: os.stat_result) -> tuple[int, ...]:
        return (
            item.st_dev,
            item.st_ino,
            item.st_mode,
            item.st_nlink,
            item.st_size,
            item.st_mtime_ns,
            item.st_ctime_ns,
        )

    if signature(before) != signature(after):
        raise ReplayError(f"input changed during same-fd read: {absolute}")
    raw = b"".join(chunks)
    return raw, {
        "path": str(absolute),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _strict_json(raw: bytes, label: str, *, canonical: bool = True) -> object:
    if canonical and not raw.endswith(b"\n"):
        raise ReplayError(f"{label} lacks its canonical final newline")
    payload = raw[:-1] if canonical else raw
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(ReplayError(f"non-finite JSON token: {token}")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplayError(f"{label} JSON is invalid: {exc}") from exc
    if canonical and _authority_json(value) != raw:
        raise ReplayError(f"{label} JSON is not canonical")
    return value


def _identity(value: object, label: str) -> dict[str, object]:
    if (
        type(value) is not dict
        or set(value) != {"path", "size_bytes", "sha256"}
        or type(value["path"]) is not str
        or not Path(value["path"]).is_absolute()
        or type(value["size_bytes"]) is not int
        or value["size_bytes"] < 0
        or type(value["sha256"]) is not str
        or SHA256_RE.fullmatch(value["sha256"]) is None
    ):
        raise ReplayError(f"{label} identity is invalid")
    return dict(value)


def _exact_mapping(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise ReplayError(f"{label} exact key set drifted")
    return value


def _campaign_provenance(path: Path) -> dict[str, object]:
    try:
        return baseline_contract.campaign_provenance(path)
    except baseline_contract.AdmissionError as exc:
        raise ReplayError(f"campaign provenance failed closed: {exc}") from exc


def _semantic_digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class _PoseRecord:
    pose_idx: int
    pose_id: str
    x: int
    y: int
    mode: int

    @property
    def coordinate(self) -> tuple[int, int, int]:
        return self.x, self.y, self.mode


@dataclass
class _FixPlan:
    values: dict[int, int]
    assignment_variables: dict[str, tuple[int, ...]]
    active_slots: dict[str, bool]
    regions_by_slot: dict[str, tuple[int, ...]]


def _strict_integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise ReplayError(f"{label} is not an exact integer")
    return value


def _domain_contains(variable: cp_model_pb2.IntegerVariableProto, value: int) -> bool:
    domain = list(variable.domain)
    if not domain or len(domain) % 2 != 0:
        raise ReplayError(f"model variable has an invalid domain: {variable.name}")
    return any(lower <= value <= upper for lower, upper in zip(domain[::2], domain[1::2]))


def _require_exact_boolean(variable: cp_model_pb2.IntegerVariableProto, label: str) -> None:
    if list(variable.domain) != [0, 1]:
        raise ReplayError(f"{label} is not an exact boolean")


def _model_name_index(model: cp_model_pb2.CpModelProto) -> dict[str, int]:
    by_name: dict[str, int] = {}
    for index, variable in enumerate(model.variables):
        if not variable.name:
            continue
        if variable.name in by_name:
            raise ReplayError("model variable names are duplicated")
        by_name[variable.name] = index
    if any(name.startswith(("z__", "opt__")) for name in by_name):
        raise ReplayError("retired pose-selector variable surface is not accepted")
    return by_name


def _cell_xy(cell: object, label: str) -> tuple[int, int]:
    if type(cell) is dict:
        if not {"x", "y"} <= set(cell):
            raise ReplayError(f"{label} lacks x/y")
        return (
            _strict_integer(cell["x"], f"{label} x"),
            _strict_integer(cell["y"], f"{label} y"),
        )
    if type(cell) is list and len(cell) == 2:
        return (
            _strict_integer(cell[0], f"{label} x"),
            _strict_integer(cell[1], f"{label} y"),
        )
    raise ReplayError(f"{label} is not a coordinate pair")


def _pose_mode_token(pose: Mapping[str, Any], *, label: str) -> tuple[str, str, str]:
    anchor = pose.get("anchor")
    if type(anchor) is not dict:
        raise ReplayError(f"{label} anchor is invalid")
    anchor_x = _strict_integer(anchor.get("x"), f"{label} anchor x")
    anchor_y = _strict_integer(anchor.get("y"), f"{label} anchor y")
    occupied = pose.get("occupied_cells", []) or []
    if type(occupied) is not list:
        raise ReplayError(f"{label} occupied cells are invalid")
    relative = sorted(
        {
            (cell_x - anchor_x, cell_y - anchor_y)
            for cell_x, cell_y in (
                _cell_xy(cell, f"{label} occupied cell") for cell in occupied
            )
        }
    )
    if relative:
        xs = [cell[0] for cell in relative]
        ys = [cell[1] for cell in relative]
        bounds_token = ":".join(str(value) for value in (min(xs), max(xs), min(ys), max(ys)))
        cell_token = ";".join(f"{x_val}:{y_val}" for x_val, y_val in relative)
        footprint = f"footprint::{bounds_token}::{cell_token}"
    else:
        footprint = "footprint::missing"
    params = pose.get("pose_params", {}) or {}
    if type(params) is not dict:
        raise ReplayError(f"{label} pose parameters are invalid")
    return str(params.get("orientation", "")), str(params.get("port_mode", "")), footprint


def _pose_records(
    pools: Mapping[str, Any],
    template: str,
    cache: dict[str, tuple[_PoseRecord, ...]],
) -> tuple[_PoseRecord, ...]:
    if template in cache:
        return cache[template]
    pool = pools.get(template)
    if type(pool) is not list:
        raise ReplayError(f"candidate pool is absent for template: {template}")
    tokens: list[tuple[str, str, str]] = []
    raw_rows: list[tuple[str, int, int, tuple[str, str, str]]] = []
    pose_ids: set[str] = set()
    for pose_idx, raw_pose in enumerate(pool):
        if type(raw_pose) is not dict:
            raise ReplayError(f"candidate pose is invalid: {template}[{pose_idx}]")
        label = f"candidate pose {template}[{pose_idx}]"
        pose_id = raw_pose.get("pose_id")
        anchor = raw_pose.get("anchor")
        if type(pose_id) is not str or not pose_id or type(anchor) is not dict:
            raise ReplayError(f"{label} identity is invalid")
        if pose_id in pose_ids:
            raise ReplayError(f"candidate pose ids are duplicated for template: {template}")
        pose_ids.add(pose_id)
        x_val = _strict_integer(anchor.get("x"), f"{label} anchor x")
        y_val = _strict_integer(anchor.get("y"), f"{label} anchor y")
        token = _pose_mode_token(raw_pose, label=label)
        tokens.append(token)
        raw_rows.append((pose_id, x_val, y_val, token))
    mode_by_token = {token: mode for mode, token in enumerate(sorted(set(tokens)))}
    records = tuple(
        _PoseRecord(
            pose_idx=pose_idx,
            pose_id=pose_id,
            x=x_val,
            y=y_val,
            mode=mode_by_token[token],
        )
        for pose_idx, (pose_id, x_val, y_val, token) in enumerate(raw_rows)
    )
    coordinates = [record.coordinate for record in records]
    if len(coordinates) != len(set(coordinates)):
        raise ReplayError(f"candidate coordinate pose keys are duplicated for template: {template}")
    cache[template] = records
    return records


def _mandatory_groups(
    mandatory_instances: object,
) -> tuple[dict[str, tuple[str, str, tuple[str, ...]]], dict[str, tuple[str, str, str]]]:
    if type(mandatory_instances) is not list:
        raise ReplayError("mandatory instances must be an exact array")
    grouped: dict[tuple[str, str], list[str]] = {}
    registry: dict[str, tuple[str, str, str]] = {}
    for entry in mandatory_instances:
        if type(entry) is not dict:
            raise ReplayError("mandatory instance entry is invalid")
        instance_id = entry.get("instance_id")
        facility_type = entry.get("facility_type")
        operation_type = entry.get("operation_type", "")
        if type(instance_id) is not str:
            raise ReplayError("mandatory instance identity is invalid")
        if type(facility_type) is not str:
            raise ReplayError("mandatory instance identity is invalid")
        if type(operation_type) is not str:
            raise ReplayError("mandatory instance identity is invalid")
        if entry.get("is_mandatory") is not True or entry.get("bound_type") != "exact":
            raise ReplayError("mandatory instance authority semantics are invalid")
        if instance_id in registry:
            raise ReplayError("mandatory instance ids are duplicated")
        grouped.setdefault((facility_type, operation_type), []).append(instance_id)
        registry[instance_id] = (facility_type, operation_type, "")
    groups: dict[str, tuple[str, str, tuple[str, ...]]] = {}
    for group_index, ((facility_type, operation_type), members) in enumerate(sorted(grouped.items())):
        group_id = f"group::{facility_type}::{operation_type}::{group_index}"
        ordered_members = tuple(sorted(members))
        groups[group_id] = (facility_type, operation_type, ordered_members)
        for instance_id in ordered_members:
            registry[instance_id] = (facility_type, operation_type, group_id)
    return groups, registry


def _coordinate_slots(
    model: cp_model_pb2.CpModelProto,
    by_name: Mapping[str, int],
    groups: Mapping[str, tuple[str, str, tuple[str, ...]]],
) -> tuple[
    dict[str, tuple[str, ...]],
    dict[str, tuple[str, ...]],
    dict[str, tuple[str, ...]],
    dict[str, tuple[int, ...]],
]:
    keys_by_prefix = {
        prefix: {name[len(prefix) :] for name in by_name if name.startswith(prefix)}
        for prefix in ("x__", "y__", "mode__", "order_key__")
    }
    coordinate_keys = keys_by_prefix["x__"]
    if any(keys != coordinate_keys for keys in keys_by_prefix.values()):
        raise ReplayError("coordinate slot x/y/mode/order_key variable faces disagree")

    mandatory: dict[str, list[tuple[int, str]]] = {group_id: [] for group_id in groups}
    required: dict[str, list[tuple[int, str]]] = {}
    residual: dict[str, list[tuple[int, str]]] = {}
    for key in coordinate_keys:
        matched_group = None
        slot_index = None
        for group_id in groups:
            prefix = f"{group_id}::slot::"
            suffix = key.removeprefix(prefix)
            if suffix != key and suffix.isdigit() and str(int(suffix)) == suffix:
                matched_group = group_id
                slot_index = int(suffix)
                break
        if matched_group is not None and slot_index is not None:
            mandatory[matched_group].append((slot_index, key))
            continue
        match = re.fullmatch(r"required_optional::(.+)::slot::(0|[1-9][0-9]*)", key)
        if match is not None:
            required.setdefault(match.group(1), []).append((int(match.group(2)), key))
            continue
        match = re.fullmatch(r"residual_optional::(.+)::slot::(0|[1-9][0-9]*)", key)
        if match is not None:
            residual.setdefault(match.group(1), []).append((int(match.group(2)), key))
            continue
        raise ReplayError(f"coordinate slot name is outside the production grammar: {key}")

    def ordered_slots(rows: list[tuple[int, str]], label: str) -> tuple[str, ...]:
        ordered = sorted(rows)
        if [index for index, _ in ordered] != list(range(len(ordered))):
            raise ReplayError(f"{label} slot indices are not contiguous")
        return tuple(key for _, key in ordered)

    mandatory_result: dict[str, tuple[str, ...]] = {}
    for group_id, (_, _, members) in groups.items():
        slots = ordered_slots(mandatory[group_id], f"mandatory group {group_id}")
        if len(slots) != len(members):
            raise ReplayError(f"mandatory group slot count differs from its instance count: {group_id}")
        mandatory_result[group_id] = slots
    required_result = {
        template: ordered_slots(rows, f"required optional {template}")
        for template, rows in required.items()
    }
    residual_result = {
        template: ordered_slots(rows, f"residual optional {template}")
        for template, rows in residual.items()
    }

    active_keys = {name.removeprefix("active__") for name in by_name if name.startswith("active__")}
    residual_keys = {key for slots in residual_result.values() for key in slots}
    if active_keys != residual_keys:
        raise ReplayError("residual optional active-variable face disagrees with coordinate slots")
    for key in residual_keys:
        _require_exact_boolean(model.variables[by_name[f"active__{key}"]], f"active slot {key}")

    regions_by_slot: dict[str, list[int]] = {key: [] for key in coordinate_keys}
    for name, index in by_name.items():
        if not name.startswith("region__"):
            continue
        suffix = name.removeprefix("region__")
        matches = [key for key in coordinate_keys if suffix.startswith(f"{key}__")]
        if len(matches) != 1:
            raise ReplayError(f"region variable does not identify exactly one coordinate slot: {name}")
        _require_exact_boolean(model.variables[index], f"region variable {name}")
        regions_by_slot[matches[0]].append(index)
    for key, indices in regions_by_slot.items():
        if indices and f"signature__{key}" not in by_name:
            raise ReplayError(f"region-bearing coordinate slot lacks a signature variable: {key}")
    return (
        mandatory_result,
        required_result,
        residual_result,
        {key: tuple(indices) for key, indices in regions_by_slot.items() if indices},
    )


def _candidate_assignment(
    raw_assignment: Mapping[str, Any],
    *,
    instance_id: str,
    pools: Mapping[str, Any],
    cache: dict[str, tuple[_PoseRecord, ...]],
) -> tuple[str, _PoseRecord]:
    facility_type = raw_assignment.get("facility_type")
    pose_idx = raw_assignment.get("pose_idx")
    if type(facility_type) is not str:
        raise ReplayError("incumbent facility type is invalid")
    pose_idx = _strict_integer(pose_idx, "incumbent pose index")
    records = _pose_records(pools, facility_type, cache)
    if pose_idx < 0 or pose_idx >= len(records):
        raise ReplayError("incumbent pose does not exist in candidate data")
    record = records[pose_idx]
    anchor = raw_assignment.get("anchor")
    if (
        raw_assignment.get("pose_id") != record.pose_id
        or type(anchor) is not dict
        or anchor.get("x") != record.x
        or anchor.get("y") != record.y
        or any(type(anchor.get(axis)) is not int for axis in ("x", "y"))
    ):
        raise ReplayError("incumbent pose identity differs from candidate data")
    if raw_assignment.get("bound_type") == "exact_pose_optional":
        expected_id = f"pose_optional::{facility_type}::{record.pose_id}"
        if instance_id != expected_id:
            raise ReplayError("optional incumbent synthetic identity is invalid")
    return facility_type, record


def _add_fix(
    plan: _FixPlan,
    model: cp_model_pb2.CpModelProto,
    index: int,
    value: int,
) -> None:
    variable = model.variables[index]
    if not _domain_contains(variable, value):
        raise ReplayError(f"fixed value is outside the model variable domain: {variable.name}")
    previous = plan.values.get(index)
    if previous is not None and previous != value:
        raise ReplayError(f"fixed values conflict for model variable: {variable.name}")
    plan.values[index] = value


def _fix_coordinate_slot(
    plan: _FixPlan,
    model: cp_model_pb2.CpModelProto,
    by_name: Mapping[str, int],
    *,
    assignment_id: str,
    slot: str,
    pose: _PoseRecord,
    active: bool | None,
) -> None:
    indices = tuple(by_name[f"{prefix}__{slot}"] for prefix in ("x", "y", "mode"))
    for index, value in zip(indices, pose.coordinate):
        _add_fix(plan, model, index, value)
    assignment_indices = list(indices)
    if active is not None:
        active_index = by_name[f"active__{slot}"]
        _add_fix(plan, model, active_index, int(active))
        assignment_indices.append(active_index)
    if assignment_id in plan.assignment_variables:
        raise ReplayError("incumbent assignment was mapped more than once")
    plan.assignment_variables[assignment_id] = tuple(assignment_indices)
    plan.active_slots[slot] = active is not False


def _placement_fix_plan(
    model: cp_model_pb2.CpModelProto,
    *,
    incumbent: Mapping[str, Any],
    mandatory_instances: object,
    candidate_placements: object,
) -> _FixPlan:
    if type(incumbent) is not dict:
        raise ReplayError("incumbent must be an exact object")
    if type(candidate_placements) is not dict:
        raise ReplayError("candidate placements must be an exact object")
    pools = candidate_placements.get("facility_pools")
    if type(pools) is not dict:
        raise ReplayError("candidate facility pools are absent")
    groups, mandatory_registry = _mandatory_groups(mandatory_instances)
    by_name = _model_name_index(model)
    mandatory_slots, required_slots, residual_slots, regions_by_slot = _coordinate_slots(
        model,
        by_name,
        groups,
    )
    plan = _FixPlan(values={}, assignment_variables={}, active_slots={}, regions_by_slot=regions_by_slot)
    pose_cache: dict[str, tuple[_PoseRecord, ...]] = {}
    mandatory_assignments: dict[str, list[tuple[str, _PoseRecord]]] = {
        group_id: [] for group_id in groups
    }
    optional_assignments: dict[str, list[tuple[str, _PoseRecord]]] = {}
    ghost_assignments: list[tuple[str, Mapping[str, Any]]] = []
    for instance_id, raw_assignment in incumbent.items():
        if type(instance_id) is not str or type(raw_assignment) is not dict:
            raise ReplayError("incumbent entry is invalid")
        if raw_assignment.get("instance_id") != instance_id:
            raise ReplayError("incumbent instance join failed")
        bound_type = raw_assignment.get("bound_type")
        if instance_id == "ghost_pick":
            if (
                raw_assignment.get("facility_type") != "ghost_rect"
                or raw_assignment.get("is_mandatory") is not False
                or bound_type != "ghost_rect"
                or raw_assignment.get("solve_mode") != "certified_exact"
            ):
                raise ReplayError("ghost incumbent semantics are invalid")
            ghost_assignments.append((instance_id, raw_assignment))
        elif bound_type == "exact":
            registry = mandatory_registry.get(instance_id)
            if registry is None:
                raise ReplayError("mandatory incumbent lacks a group")
            facility_type, operation_type, group_id = registry
            if (
                raw_assignment.get("facility_type") != facility_type
                or raw_assignment.get("operation_type", "") != operation_type
                or raw_assignment.get("is_mandatory") is not True
                or raw_assignment.get("solve_mode") != "certified_exact"
            ):
                raise ReplayError("mandatory incumbent identity differs from mandatory authority")
            candidate_template, pose = _candidate_assignment(
                raw_assignment,
                instance_id=instance_id,
                pools=pools,
                cache=pose_cache,
            )
            if candidate_template != facility_type:
                raise ReplayError("mandatory incumbent candidate template drifted")
            mandatory_assignments[group_id].append((instance_id, pose))
        elif bound_type == "exact_pose_optional":
            facility_type, pose = _candidate_assignment(
                raw_assignment,
                instance_id=instance_id,
                pools=pools,
                cache=pose_cache,
            )
            expected_operation = {
                "power_pole": "power_supply",
                "protocol_storage_box": "box_sink",
            }.get(facility_type)
            if (
                expected_operation is None
                or raw_assignment.get("operation_type") != expected_operation
                or raw_assignment.get("is_mandatory") is not False
                or raw_assignment.get("solve_mode") != "certified_exact"
            ):
                raise ReplayError("optional incumbent semantics are invalid")
            optional_assignments.setdefault(facility_type, []).append((instance_id, pose))
        else:
            raise ReplayError("incumbent bound type is unsupported")

    used_resources: set[str] = set()
    for group_id, (facility_type, _operation_type, members) in groups.items():
        assignments = mandatory_assignments[group_id]
        if {instance_id for instance_id, _ in assignments} != set(members):
            raise ReplayError(f"mandatory incumbent coverage differs from model group: {group_id}")
        by_instance = sorted(assignments)
        instance_pose_indices = [pose.pose_idx for _, pose in by_instance]
        if instance_pose_indices != sorted(instance_pose_indices) or len(set(instance_pose_indices)) != len(members):
            raise ReplayError(f"mandatory instance-to-pose ordering is not one-to-one: {group_id}")
        slots = mandatory_slots[group_id]
        by_coordinate = sorted(assignments, key=lambda item: item[1].coordinate)
        if len(by_coordinate) != len(slots):
            raise ReplayError(f"mandatory incumbent count differs from coordinate slots: {group_id}")
        _pose_records(pools, facility_type, pose_cache)
        for (assignment_id, pose), slot in zip(by_coordinate, slots):
            if slot in used_resources:
                raise ReplayError("coordinate slot was mapped more than once")
            used_resources.add(slot)
            _fix_coordinate_slot(
                plan,
                model,
                by_name,
                assignment_id=assignment_id,
                slot=slot,
                pose=pose,
                active=None,
            )

    c1_rows: list[tuple[int, int]] = []
    for name, index in by_name.items():
        if not name.startswith("c1pole__"):
            continue
        match = re.fullmatch(r"c1pole__(0|[1-9][0-9]*)", name)
        if match is None:
            raise ReplayError(f"C1 power-pole variable name is invalid: {name}")
        _require_exact_boolean(model.variables[index], f"C1 power-pole variable {name}")
        c1_rows.append((int(match.group(1)), index))
    c1_rows.sort()
    if [pose_idx for pose_idx, _ in c1_rows] != list(range(len(c1_rows))):
        raise ReplayError("C1 power-pole variable indices are not contiguous")
    coordinate_optional_templates = set(required_slots) | set(residual_slots)
    if c1_rows and "power_pole" in coordinate_optional_templates:
        raise ReplayError("power_pole appears on both C1 and coordinate variable surfaces")

    optional_templates = set(optional_assignments) | coordinate_optional_templates
    if c1_rows:
        optional_templates.discard("power_pole")
        pole_records = _pose_records(pools, "power_pole", pose_cache)
        if len(pole_records) != len(c1_rows):
            raise ReplayError("C1 power-pole variable face differs from the candidate pool")
        chosen_poles = optional_assignments.get("power_pole", [])
        if len({pose.pose_idx for _, pose in chosen_poles}) != len(chosen_poles):
            raise ReplayError("C1 power-pole incumbent assignments are duplicated")
        chosen_by_index = {pose.pose_idx: assignment_id for assignment_id, pose in chosen_poles}
        for pose_idx, index in c1_rows:
            selected = pose_idx in chosen_by_index
            _add_fix(plan, model, index, int(selected))
            if selected:
                assignment_id = chosen_by_index[pose_idx]
                resource = f"c1pole::{pose_idx}"
                if resource in used_resources or assignment_id in plan.assignment_variables:
                    raise ReplayError("C1 power-pole assignment was mapped more than once")
                used_resources.add(resource)
                plan.assignment_variables[assignment_id] = (index,)
        optional_assignments.pop("power_pole", None)
    elif optional_assignments.get("power_pole") and "power_pole" not in coordinate_optional_templates:
        raise ReplayError("power-pole incumbent lacks a production placement variable surface")

    for template in sorted(optional_templates):
        assignments = optional_assignments.get(template, [])
        if len({pose.pose_idx for _, pose in assignments}) != len(assignments):
            raise ReplayError(f"optional incumbent assignments are duplicated: {template}")
        required = required_slots.get(template, ())
        residual = residual_slots.get(template, ())
        assignment_count = len(assignments)
        if assignment_count < len(required) or assignment_count > len(required) + len(residual):
            raise ReplayError(f"optional incumbent count differs from coordinate slots: {template}")
        if required and assignment_count > len(required):
            raise ReplayError(f"optional incumbent origin is ambiguous between required and residual slots: {template}")
        selected_residual_count = assignment_count - len(required)
        selected_slots = tuple(required) + tuple(residual[:selected_residual_count])
        by_coordinate = sorted(assignments, key=lambda item: item[1].coordinate)
        if len(by_coordinate) != len(selected_slots):
            raise ReplayError(f"optional incumbent did not map one-to-one to selected slots: {template}")
        _pose_records(pools, template, pose_cache)
        for (assignment_id, pose), slot in zip(by_coordinate, selected_slots):
            if slot in used_resources:
                raise ReplayError("coordinate slot was mapped more than once")
            used_resources.add(slot)
            _fix_coordinate_slot(
                plan,
                model,
                by_name,
                assignment_id=assignment_id,
                slot=slot,
                pose=pose,
                active=True if slot in residual else None,
            )
        for slot in residual[selected_residual_count:]:
            active_index = by_name[f"active__{slot}"]
            _add_fix(plan, model, active_index, 0)
            plan.active_slots[slot] = False
        optional_assignments.pop(template, None)
    if optional_assignments:
        raise ReplayError("optional incumbent template lacks a coordinate mapping")

    ghost_rows: list[tuple[int, int, int, int, int]] = []
    for name, index in by_name.items():
        if not name.startswith("ghost__"):
            continue
        match = re.fullmatch(r"ghost__([0-9]+)_([0-9]+)_([1-9][0-9]*)_([1-9][0-9]*)", name)
        if match is None:
            raise ReplayError(f"ghost selector variable name is invalid: {name}")
        _require_exact_boolean(model.variables[index], f"ghost selector {name}")
        ghost_rows.append(
            (
                index,
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
                int(match.group(4)),
            )
        )
    ghost_rows.sort()
    if len(ghost_assignments) != (1 if ghost_rows else 0):
        raise ReplayError("ghost incumbent coverage differs from the ghost variable face")
    if ghost_rows:
        sizes = {(width, height) for _, _, _, width, height in ghost_rows}
        anchors = [(x_val, y_val) for _, x_val, y_val, _, _ in ghost_rows]
        if len(sizes) != 1 or len(anchors) != len(set(anchors)):
            raise ReplayError("ghost variable face has ambiguous dimensions or anchors")
        assignment_id, ghost_assignment = ghost_assignments[0]
        pose_idx = _strict_integer(ghost_assignment.get("pose_idx"), "ghost pose index")
        anchor = ghost_assignment.get("anchor")
        if type(anchor) is not dict:
            raise ReplayError("ghost anchor is invalid")
        anchor_xy = (
            _strict_integer(anchor.get("x"), "ghost anchor x"),
            _strict_integer(anchor.get("y"), "ghost anchor y"),
        )
        if pose_idx < 0 or pose_idx >= len(ghost_rows) or anchors[pose_idx] != anchor_xy:
            raise ReplayError("ghost pose index and model-variable anchor do not join")
        expected_pose_id = f"ghost_anchor::{anchor_xy[0]},{anchor_xy[1]}"
        if ghost_assignment.get("pose_id") != expected_pose_id:
            raise ReplayError("ghost pose identity differs from its model-variable anchor")
        selected_index = ghost_rows[pose_idx][0]
        for index, *_ in ghost_rows:
            _add_fix(plan, model, index, int(index == selected_index))
        plan.assignment_variables[assignment_id] = (selected_index,)

    if set(plan.assignment_variables) != set(incumbent):
        raise ReplayError("incumbent did not map one-to-one to production placement variables")
    variable_resources = list(plan.assignment_variables.values())
    if len(variable_resources) != len({variables for variables in variable_resources}):
        raise ReplayError("production placement resources are not one-to-one with incumbent assignments")
    return plan


def replay_fixed_assignment(
    model_raw: bytes,
    *,
    incumbent: Mapping[str, Any],
    mandatory_instances: object,
    candidate_placements: object,
    max_time_seconds: float,
) -> dict[str, object]:
    if max_time_seconds <= 0:
        raise ReplayError("replay time budget must be positive")
    parsed = cp_model_pb2.CpModelProto()
    try:
        parsed.ParseFromString(model_raw)
    except Exception as exc:  # pragma: no cover - protobuf implementation detail
        raise ReplayError(f"binary model parse failed: {exc}") from exc
    if parsed.SerializeToString(deterministic=True) != model_raw:
        raise ReplayError("binary model is not the canonical deterministic protobuf")
    without_unknown = cp_model_pb2.CpModelProto()
    without_unknown.CopyFrom(parsed)
    without_unknown.DiscardUnknownFields()
    if without_unknown.SerializeToString(deterministic=True) != model_raw:
        raise ReplayError("binary model contains unknown protobuf fields")
    plan = _placement_fix_plan(
        parsed,
        incumbent=incumbent,
        mandatory_instances=mandatory_instances,
        candidate_placements=candidate_placements,
    )

    model = cp_model.CpModel()
    model.proto.parse_text_format(text_format.MessageToString(parsed))
    for index, value in sorted(plan.values.items()):
        model.add(model.get_int_var_from_proto_index(index) == value)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = float(max_time_seconds)
    solver.parameters.random_seed = 2026072301
    status = solver.solve(model)
    status_name = solver.status_name(status)
    if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        raise ReplayError(f"fixed assignment was not feasible: {status_name}")
    for index, expected in plan.values.items():
        variable = model.get_int_var_from_proto_index(index)
        if solver.value(variable) != expected:
            raise ReplayError(f"solver result differs from a fixed model variable: {parsed.variables[index].name}")
    for slot, region_indices in plan.regions_by_slot.items():
        selected_region_count = sum(
            solver.value(model.get_int_var_from_proto_index(index)) for index in region_indices
        )
        expected_count = 1 if plan.active_slots.get(slot, True) else 0
        if selected_region_count != expected_count:
            raise ReplayError(f"coordinate signature/region channel did not select exactly one region: {slot}")
    return {
        "status": "PASS",
        "solver_status": status_name,
        "variable_count": len(parsed.variables),
        "constraint_count_before_fixing": len(parsed.constraints),
        "fixed_assignment_count": len(plan.assignment_variables),
        "workers": 1,
        "max_time_seconds": float(max_time_seconds),
    }


def _write_exclusive(path: Path, raw: bytes) -> dict[str, object]:
    if path.is_symlink() or not path.parent.is_dir() or path.parent.is_symlink():
        raise ReplayError("output path is not a stable non-symlink location")
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
        0o600,
    )
    try:
        view = memoryview(raw)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise ReplayError("short output write")
            view = view[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-provenance", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--incumbent", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-time-seconds", type=float, default=600.0)
    return parser


def _replay_paths(
    *,
    campaign_provenance_path: Path | str,
    model_path: Path | str,
    metadata_path: Path | str,
    incumbent_path: Path | str,
    output_path: Path | str,
    expectation: baseline_contract.BaselineExpectation,
    created_at_utc: str,
    max_time_seconds: float,
) -> tuple[dict[str, object], dict[str, object]]:
    """Replay and publish one receipt; tests may supply a small expectation."""

    campaign_provenance_path = Path(campaign_provenance_path)
    model_path = Path(model_path)
    metadata_path = Path(metadata_path)
    incumbent_path = Path(incumbent_path)
    output_path = Path(output_path)
    if not campaign_provenance_path.is_absolute():
        raise ReplayError("campaign provenance path is not absolute")
    provenance_before = _campaign_provenance(campaign_provenance_path)
    repository_root = Path(str(provenance_before["repository_root"]))
    if Path.cwd() != repository_root:
        raise ReplayError("working directory is not the campaign repository root")
    model_raw, model_identity = _snapshot(model_path, limit=1 << 30)
    metadata_raw, metadata_identity = _snapshot(metadata_path, limit=64 << 20)
    incumbent_raw, incumbent_identity = _snapshot(incumbent_path, limit=64 << 20)
    metadata = _exact_mapping(
        _strict_json(metadata_raw, "metadata"),
        METADATA_KEYS,
        "metadata",
    )
    incumbent = _strict_json(incumbent_raw, "incumbent")
    if (
        metadata["schema_version"] != METADATA_SCHEMA
        or metadata["status"] != "PASS"
        or metadata["campaign_provenance"] != provenance_before
        or metadata["global_claim_authorized"] is not False
        or metadata["legacy_control_used_as_build_input"] is not False
        or metadata["errors"] != []
        or metadata["historical_model_text_sha256"] != expectation.historical_model_text_sha256
        or metadata["model_variable_count"] != expectation.model_variable_count
        or type(metadata["model_variable_count"]) is not int
        or metadata["model_constraint_count"] != expectation.model_constraint_count
        or type(metadata["model_constraint_count"]) is not int
    ):
        raise ReplayError("metadata semantics drifted")
    if _identity(metadata.get("model_identity"), "metadata model") != model_identity:
        raise ReplayError("metadata does not bind the supplied model")
    if type(incumbent) is not dict:
        raise ReplayError("incumbent must be an exact object")
    if (
        len(incumbent) != expectation.incumbent_assignment_count
        or _semantic_digest(incumbent) != expectation.incumbent_sha256
    ):
        raise ReplayError("incumbent digest or assignment count drifted")
    input_identities = metadata.get("input_identities")
    if type(input_identities) is not dict or set(input_identities) != {
        "candidate_placements",
        "canonical_rules",
        "mandatory_instances",
    }:
        raise ReplayError("metadata strict input identities drifted")
    candidate_identity = _identity(input_identities["candidate_placements"], "candidate")
    canonical_rules_identity = _identity(input_identities["canonical_rules"], "canonical rules")
    mandatory_identity = _identity(input_identities["mandatory_instances"], "mandatory")
    expected_paths = {
        "candidate": repository_root / "data" / "preprocessed" / "candidate_placements.json",
        "canonical_rules": repository_root / "rules" / "canonical_rules.json",
        "mandatory": repository_root / "data" / "preprocessed" / "mandatory_exact_instances.json",
    }
    if (
        Path(str(candidate_identity["path"])) != expected_paths["candidate"]
        or Path(str(canonical_rules_identity["path"])) != expected_paths["canonical_rules"]
        or Path(str(mandatory_identity["path"])) != expected_paths["mandatory"]
    ):
        raise ReplayError("metadata strict inputs are not campaign checkout members")
    candidate_raw, candidate_actual = _snapshot(
        Path(str(candidate_identity["path"])),
        limit=1 << 30,
    )
    mandatory_raw, mandatory_actual = _snapshot(
        Path(str(mandatory_identity["path"])),
        limit=64 << 20,
    )
    _, canonical_rules_actual = _snapshot(
        Path(str(canonical_rules_identity["path"])),
        limit=64 << 20,
    )
    if (
        candidate_actual != candidate_identity
        or canonical_rules_actual != canonical_rules_identity
        or mandatory_actual != mandatory_identity
    ):
        raise ReplayError("strict input detached identity drifted")
    candidate = _strict_json(candidate_raw, "candidate placements", canonical=False)
    mandatory = _strict_json(mandatory_raw, "mandatory instances", canonical=False)
    result = replay_fixed_assignment(
        model_raw,
        incumbent=incumbent,
        mandatory_instances=mandatory,
        candidate_placements=candidate,
        max_time_seconds=max_time_seconds,
    )
    if (
        result["variable_count"] != expectation.model_variable_count
        or result["constraint_count_before_fixing"] != expectation.model_constraint_count
    ):
        raise ReplayError("model variable or constraint count drifted")
    if _campaign_provenance(campaign_provenance_path) != provenance_before:
        raise ReplayError("campaign provenance drifted during fixed-assignment replay")
    _, tool_identity = _snapshot(Path(__file__), limit=64 << 20)
    receipt = {
        "schema_version": SCHEMA,
        "status": "PASS",
        "verdict": VERDICT,
        "purpose": PURPOSE,
        "created_at_utc": created_at_utc,
        "campaign_provenance": provenance_before,
        "model_identity": model_identity,
        "metadata_identity": metadata_identity,
        "incumbent_identity": incumbent_identity,
        "incumbent_sha256": expectation.incumbent_sha256,
        "replay_tool_identity": tool_identity,
        "solver_status": result["solver_status"],
        "model_variable_count": result["variable_count"],
        "model_constraint_count": result["constraint_count_before_fixing"],
        "assignment_count": len(incumbent),
        "fixed_assignment_count": result["fixed_assignment_count"],
        "unresolved_assignment_count": 0,
        "conflicting_assignment_count": 0,
        "solution_matches_fixed_assignments": True,
        "all_fixed_equalities_added": True,
        "legacy_control_used_as_truth_root": False,
        "model_validation_errors": [],
        "replay_errors": [],
        "global_claim_authorized": False,
    }
    identity = _write_exclusive(output_path, _authority_json(receipt))
    return receipt, identity


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _, identity = _replay_paths(
        campaign_provenance_path=args.campaign_provenance,
        model_path=args.model,
        metadata_path=args.metadata,
        incumbent_path=args.incumbent,
        output_path=args.output,
        expectation=baseline_contract.PRODUCTION_EXPECTATION,
        created_at_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        max_time_seconds=args.max_time_seconds,
    )
    print(json.dumps({"status": "PASS", "receipt": identity}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
