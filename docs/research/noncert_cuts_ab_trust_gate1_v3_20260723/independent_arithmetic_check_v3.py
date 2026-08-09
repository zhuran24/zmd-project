#!/usr/bin/env python3
"""Binary-authority replay for one concrete Gate-1 APPLIED inequality.

This checker deliberately starts below every JSON rendering used by the
positive-control runner.  It reads an official binary ``CpModelProto`` and
``CpSolverResponse`` from one stable file descriptor each, rejects protobuf
encodings that are not deterministic canonical encodings, derives the complete
ghost-selector set and its unique active member, and only then joins the
incumbent, cut sample, APPLIED ledger receipt, and captured assignment.

The result is narrow: it validates one applied inequality and its selector
join.  It is not a proof sidecar and does not establish family-global cut
soundness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from google.protobuf.message import DecodeError, Message
from ortools.sat import cp_model_pb2


EXPECTED_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
_GHOST_DIGEST_PREFIX = b"zmd.ghost-rect.v1:"
_SUPPORTED_BACKEND = "coordinate_exact_v1"
_GHOST_NAME_PREFIX = "ghost__"
_ALLOWED_OPERATIONS = {
    "region_capacity_le",
    "shape_packing_hall_le",
    "power_pose_exclusion",
}
_LEDGER_SCHEMA = "cut-ledger-v1"
_LEDGER_EVENTS = frozenset(
    {
        "GENESIS",
        "GENERATED",
        "REJECTED",
        "VALIDATED",
        "SHADOW",
        "PREPARED",
        "APPLIED",
        "HELD",
        "QUARANTINED",
        "SUPERSEDED",
        "POISONED",
        "EPOCH_CLOSED",
        "SEGMENT_SEAL",
    }
)
_LEDGER_GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class Snapshot:
    path: str
    size: int
    sha256: str
    device: int
    inode: int
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True)
class GhostTruth:
    backend: str
    grid_width: int
    grid_height: int
    ghost_width: int
    ghost_height: int
    selector_count: int
    model_variable_count: int
    model_constraint_count: int
    active_rect_idx: int
    active_variable_index: int
    active_variable_name: str
    anchor_x: int
    anchor_y: int
    rectangle_digest: str


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _json_digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _strict_json(raw: bytes, *, label: str) -> object:
    def reject_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise ValueError(f"{label}: non-finite JSON constant {value}")

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{label}: invalid strict JSON: {exc}") from exc


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _reject_symlink_components(path: Path) -> None:
    absolute = _absolute(path)
    current = Path(absolute.anchor)
    for part in absolute.parts[1:-1]:
        current /= part
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError as exc:
            raise ValueError(f"missing path component: {current}") from exc
        if stat.S_ISLNK(mode):
            raise ValueError(f"symlink path component rejected: {current}")
        if not stat.S_ISDIR(mode):
            raise ValueError(f"non-directory path component rejected: {current}")


def read_snapshot(path: Path) -> tuple[bytes, Snapshot]:
    """Read a regular file once through one O_NOFOLLOW descriptor.

    The before/after ``fstat`` tuple makes concurrent replacement or mutation a
    hard failure.  No pathname read or second open is used for the payload.
    """

    absolute = _absolute(path)
    _reject_symlink_components(absolute)
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("O_NOFOLLOW is required for authority snapshots")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        fd = os.open(absolute, flags)
    except OSError as exc:
        raise ValueError(f"cannot open non-symlink authority file {absolute}: {exc}") from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"authority input is not a regular file: {absolute}")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError(f"authority input truncated during snapshot: {absolute}")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1):
            raise ValueError(f"authority input grew during snapshot: {absolute}")
        after = os.fstat(fd)
        try:
            named_after = os.lstat(absolute)
        except FileNotFoundError as exc:
            raise ValueError(f"authority pathname disappeared during snapshot: {absolute}") from exc
    finally:
        os.close(fd)
    stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, key) != getattr(after, key) for key in stable_fields):
        raise ValueError(f"authority input changed during snapshot: {absolute}")
    if (
        stat.S_ISLNK(named_after.st_mode)
        or not stat.S_ISREG(named_after.st_mode)
        or named_after.st_dev != after.st_dev
        or named_after.st_ino != after.st_ino
    ):
        raise ValueError(f"authority pathname was replaced during snapshot: {absolute}")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise ValueError(f"authority input size drift during snapshot: {absolute}")
    return raw, Snapshot(
        path=str(absolute),
        size=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        device=before.st_dev,
        inode=before.st_ino,
        mtime_ns=before.st_mtime_ns,
        ctime_ns=before.st_ctime_ns,
    )


def _parse_canonical_proto(raw: bytes, message: Message, *, label: str) -> Message:
    if not raw:
        raise ValueError(f"{label}: empty protobuf rejected")
    try:
        consumed = message.ParseFromString(raw)
    except DecodeError as exc:
        raise ValueError(f"{label}: truncated or malformed protobuf") from exc
    if consumed != len(raw):
        raise ValueError(f"{label}: protobuf parser did not consume every byte")
    without_unknown = type(message)()
    without_unknown.CopyFrom(message)
    without_unknown.DiscardUnknownFields()
    canonical = without_unknown.SerializeToString(deterministic=True)
    if canonical != raw:
        raise ValueError(f"{label}: unknown, duplicate, or noncanonical protobuf encoding rejected")
    return without_unknown


def parse_model(raw: bytes) -> cp_model_pb2.CpModelProto:
    return _parse_canonical_proto(
        raw,
        cp_model_pb2.CpModelProto(),
        label="CpModelProto",
    )


def parse_response(raw: bytes) -> cp_model_pb2.CpSolverResponse:
    return _parse_canonical_proto(
        raw,
        cp_model_pb2.CpSolverResponse(),
        label="CpSolverResponse",
    )


def _exact_int(value: object, *, field: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{field} must be an exact integer >= {minimum}")
    return value


def _selector_contract(
    contract: object,
) -> tuple[int, int, int, int, list[tuple[int, int, str]]]:
    if type(contract) is not dict:
        raise ValueError("selector contract must be an object")
    if set(contract) != {"schema_version", "backend", "grid", "ghost", "anchor_filter"}:
        raise ValueError("selector contract has missing or unexpected fields")
    if contract["schema_version"] != 1:
        raise ValueError("selector contract schema_version must be exact 1")
    if contract["backend"] != _SUPPORTED_BACKEND:
        raise ValueError("unsupported or drifted selector backend")
    if contract["anchor_filter"] is not None:
        raise ValueError("Gate-1 v3 requires the unfiltered full anchor domain")
    grid = contract["grid"]
    ghost = contract["ghost"]
    if type(grid) is not dict or set(grid) != {"width", "height"}:
        raise ValueError("grid contract must contain width and height only")
    if type(ghost) is not dict or set(ghost) != {"width", "height"}:
        raise ValueError("ghost contract must contain width and height only")
    grid_w = _exact_int(grid["width"], field="grid.width", minimum=1)
    grid_h = _exact_int(grid["height"], field="grid.height", minimum=1)
    ghost_w = _exact_int(ghost["width"], field="ghost.width", minimum=1)
    ghost_h = _exact_int(ghost["height"], field="ghost.height", minimum=1)
    if ghost_w > grid_w or ghost_h > grid_h:
        raise ValueError("ghost dimensions exceed the fixed grid")
    anchors = [
        (x, y, f"{_GHOST_NAME_PREFIX}{x}_{y}_{ghost_w}_{ghost_h}")
        for x in range(grid_w - ghost_w + 1)
        for y in range(grid_h - ghost_h + 1)
    ]
    return grid_w, grid_h, ghost_w, ghost_h, anchors


def _rectangle_digest(x: int, y: int, width: int, height: int) -> str:
    return hashlib.sha256(_GHOST_DIGEST_PREFIX + _canonical_json([x, y, width, height])).hexdigest()


def derive_ghost_truth(
    model: cp_model_pb2.CpModelProto,
    response: cp_model_pb2.CpSolverResponse,
    contract: object,
) -> GhostTruth:
    """Derive the unique active ghost solely from binary solver authority."""

    grid_w, grid_h, ghost_w, ghost_h, anchors = _selector_contract(contract)
    expected_names = [name for _x, _y, name in anchors]
    expected_set = set(expected_names)
    by_name: dict[str, list[int]] = defaultdict(list)
    for index, variable in enumerate(model.variables):
        by_name[str(variable.name)].append(index)
    unexpected = sorted(name for name in by_name if name.startswith(_GHOST_NAME_PREFIX) and name not in expected_set)
    if unexpected:
        raise ValueError(f"model contains unexpected ghost selector name: {unexpected[0]}")
    selector_indices: list[int] = []
    for name in expected_names:
        indices = by_name.get(name, [])
        if len(indices) != 1:
            raise ValueError(f"ghost selector must occur exactly once: {name}")
        index = indices[0]
        if list(model.variables[index].domain) != [0, 1]:
            raise ValueError(f"ghost selector has non-Boolean domain: {name}")
        selector_indices.append(index)
    selector_set = set(selector_indices)

    matching = 0
    for constraint in model.constraints:
        if constraint.WhichOneof("constraint") != "exactly_one":
            continue
        literals = [int(value) for value in constraint.exactly_one.literals]
        touched = selector_set.intersection(literals)
        if not touched:
            continue
        if (
            len(literals) != len(selector_indices)
            or len(set(literals)) != len(literals)
            or set(literals) != selector_set
        ):
            raise ValueError("ghost selector participates in a drifted exactly-one set")
        matching += 1
    if matching != 1:
        raise ValueError("model must contain exactly one complete ghost exactly-one constraint")

    if response.status not in {cp_model_pb2.FEASIBLE, cp_model_pb2.OPTIMAL}:
        raise ValueError("solver response status is not FEASIBLE or OPTIMAL")
    if len(response.solution) != len(model.variables):
        raise ValueError("solver response does not contain the full model solution vector")
    active_ordinals: list[int] = []
    for ordinal, variable_index in enumerate(selector_indices):
        value = int(response.solution[variable_index])
        if value not in {0, 1}:
            raise ValueError("solver response assigns a non-Boolean ghost value")
        if value == 1:
            active_ordinals.append(ordinal)
    if len(active_ordinals) != 1:
        raise ValueError("solver response must activate exactly one ghost selector")
    ordinal = active_ordinals[0]
    x, y, name = anchors[ordinal]
    variable_index = selector_indices[ordinal]
    return GhostTruth(
        backend=_SUPPORTED_BACKEND,
        grid_width=grid_w,
        grid_height=grid_h,
        ghost_width=ghost_w,
        ghost_height=ghost_h,
        selector_count=len(selector_indices),
        model_variable_count=len(model.variables),
        model_constraint_count=len(model.constraints),
        active_rect_idx=ordinal,
        active_variable_index=variable_index,
        active_variable_name=name,
        anchor_x=x,
        anchor_y=y,
        rectangle_digest=_rectangle_digest(x, y, ghost_w, ghost_h),
    )


def _mandatory_groups(
    payload: object,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    if type(payload) is not list or not payload:
        raise ValueError("mandatory instances must be a non-empty array")
    instances: dict[str, dict[str, Any]] = {}
    buckets: dict[tuple[str, str], list[str]] = defaultdict(list)
    for offset, item in enumerate(payload):
        if type(item) is not dict:
            raise ValueError(f"mandatory instance {offset} is not an object")
        instance_id = item.get("instance_id")
        facility = item.get("facility_type")
        operation = item.get("operation_type")
        if not all(type(value) is str and value for value in (instance_id, facility, operation)):
            raise ValueError("mandatory identity fields must be non-empty strings")
        if instance_id in instances:
            raise ValueError(f"duplicate mandatory instance {instance_id}")
        if item.get("is_mandatory") is not True or item.get("bound_type") != "exact":
            raise ValueError(f"{instance_id} is not mandatory exact")
        instances[instance_id] = item
        buckets[(facility, operation)].append(instance_id)
    groups: dict[str, list[str]] = {}
    for group_index, ((_facility, _operation), members) in enumerate(sorted(buckets.items())):
        facility, operation = sorted(buckets)[group_index]
        groups[f"group::{facility}::{operation}::{group_index}"] = sorted(members)
    return instances, groups


def _selected_groups(
    *,
    mandatory: object,
    candidates: object,
    incumbent: object,
) -> dict[str, list[dict[str, Any]]]:
    instances, groups = _mandatory_groups(mandatory)
    if type(candidates) is not dict or type(candidates.get("facility_pools")) is not dict:
        raise ValueError("candidate placements lack facility_pools")
    if type(incumbent) is not dict:
        raise ValueError("incumbent must be an object")
    pools: dict[str, tuple[list[dict[str, Any]], dict[str, int]]] = {}
    for item in instances.values():
        facility = str(item["facility_type"])
        if facility in pools:
            continue
        pool = candidates["facility_pools"].get(facility)
        if type(pool) is not list or not pool:
            raise ValueError(f"candidate pool missing for {facility}")
        pose_indices: dict[str, int] = {}
        for index, pose in enumerate(pool):
            if type(pose) is not dict or type(pose.get("pose_id")) is not str:
                raise ValueError("candidate pose identity is malformed")
            if pose["pose_id"] in pose_indices:
                raise ValueError(f"duplicate candidate pose {pose['pose_id']}")
            pose_indices[pose["pose_id"]] = index
        pools[facility] = (pool, pose_indices)
    selected: dict[str, dict[str, Any]] = {}
    for instance_id, strict in instances.items():
        entry = incumbent.get(instance_id)
        if type(entry) is not dict:
            raise ValueError(f"incumbent omits {instance_id}")
        if any(entry.get(field) != strict[field] for field in ("instance_id", "facility_type", "operation_type")):
            raise ValueError(f"incumbent identity drift for {instance_id}")
        pool, pool_indices = pools[str(strict["facility_type"])]
        pose_id = entry.get("pose_id")
        pose_idx = entry.get("pose_idx")
        if type(pose_id) is not str or type(pose_idx) is not int:
            raise ValueError(f"incumbent pose identity malformed for {instance_id}")
        if pose_idx < 0 or pose_idx >= len(pool) or pool_indices.get(pose_id) != pose_idx:
            raise ValueError(f"incumbent pose index drift for {instance_id}")
        if entry.get("anchor") != pool[pose_idx].get("anchor"):
            raise ValueError(f"incumbent anchor drift for {instance_id}")
        selected[instance_id] = {**entry, "_pose": pool[pose_idx]}
    result: dict[str, list[dict[str, Any]]] = {}
    for group_id, member_ids in groups.items():
        entries = [selected[instance_id] for instance_id in member_ids]
        if len({str(entry["pose_id"]) for entry in entries}) != len(entries):
            raise ValueError(f"group {group_id} selects a duplicate pose")
        result[group_id] = entries
    return result


def _recompute_arithmetic(
    operation: object,
    parameters: object,
    groups: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, object]], int, int]:
    if operation not in _ALLOWED_OPERATIONS or type(parameters) is not dict:
        raise ValueError("unsupported or malformed inequality plan")
    contributions: list[dict[str, object]] = []
    if operation == "region_capacity_le":
        weights = parameters.get("group_cell_weights")
        capacity = parameters.get("capacity")
        if type(weights) is not dict or type(capacity) is not int:
            raise ValueError("region-capacity parameters are malformed")
        for group_id in sorted(weights):
            weight = weights[group_id]
            if group_id not in groups or type(weight) is not int or weight < 0:
                raise ValueError("region-capacity group/weight is malformed")
            count = len({str(entry["pose_id"]) for entry in groups[group_id]})
            contributions.append(
                {
                    "label": group_id,
                    "selected_count": count,
                    "weight": weight,
                    "value": count * weight,
                }
            )
        rhs = capacity
    elif operation == "shape_packing_hall_le":
        group_id = parameters.get("group_id")
        region_kind = parameters.get("region_kind")
        capacity = parameters.get("capacity")
        if (
            type(group_id) is not str
            or group_id not in groups
            or region_kind not in {"left_baseline", "top_baseline"}
            or type(capacity) is not int
        ):
            raise ValueError("shape-packing parameters are malformed")
        count = 0
        for entry in groups[group_id]:
            cells = entry["_pose"].get("occupied_cells")
            if (
                type(cells) is not list
                or not cells
                or any(
                    type(cell) is not list or len(cell) != 2 or type(cell[0]) is not int or type(cell[1]) is not int
                    for cell in cells
                )
            ):
                raise ValueError("candidate occupied_cells are malformed")
            if region_kind == "left_baseline":
                count += int(all(cell[1] == 0 for cell in cells))
            else:
                count += int(all(cell[0] == 0 for cell in cells))
        contributions.append(
            {
                "label": group_id,
                "selected_count": count,
                "weight": 1,
                "value": count,
            }
        )
        rhs = capacity
    else:
        group_id = parameters.get("group_id")
        pose_id = parameters.get("pose_id")
        if type(group_id) is not str or group_id not in groups or type(pose_id) is not str:
            raise ValueError("power-pose parameters are malformed")
        count = sum(str(entry["pose_id"]) == pose_id for entry in groups[group_id])
        contributions.append(
            {
                "label": f"{group_id}:{pose_id}",
                "selected_count": count,
                "weight": 1,
                "value": count,
            }
        )
        rhs = 0
    lhs = sum(int(row["value"]) for row in contributions)
    return contributions, lhs, rhs


def _literal_map(payload: object, *, prestate_sha256: str) -> dict[int, dict[str, Any]]:
    if type(payload) is not dict or payload.get("schema_version") != 1:
        raise ValueError("assignment schema_version must be exact 1")
    if payload.get("prestate_sha256") != prestate_sha256:
        raise ValueError("assignment prestate identity drift")
    literals = payload.get("literals")
    if type(literals) is not list:
        raise ValueError("assignment literals must be an array")
    result: dict[int, dict[str, Any]] = {}
    names: set[str] = set()
    for row in literals:
        if type(row) is not dict or set(row) != {"index", "name", "value"}:
            raise ValueError("assignment literal has invalid fields")
        index, name, value = row["index"], row["name"], row["value"]
        if (
            type(index) is not int
            or type(name) is not str
            or not name
            or type(value) is not int
            or value not in {0, 1}
            or index in result
            or name in names
        ):
            raise ValueError("assignment literal identity/value is invalid")
        result[index] = row
        names.add(name)
    return result


def replay_ledger(raw: bytes) -> dict[str, object]:
    """Replay one canonical, sealed cut-ledger segment from its raw bytes."""

    if not raw or not raw.endswith(b"\n"):
        raise ValueError("ledger segment lacks its final newline")
    lines = raw.splitlines()
    events: list[dict[str, Any]] = []
    previous = _LEDGER_GENESIS_HASH
    writer_id: str | None = None
    scope_id: str | None = None
    for seq, line in enumerate(lines):
        event = _strict_json(line, label=f"ledger line {seq}")
        if type(event) is not dict or _canonical_json(event) != line:
            raise ValueError(f"ledger line {seq} is not canonical JSON")
        if (
            event.get("schema_version") != _LEDGER_SCHEMA
            or event.get("seq") != seq
            or event.get("event") not in _LEDGER_EVENTS
            or event.get("prev_event_hash") != previous
        ):
            raise ValueError(f"ledger line {seq} schema, sequence, event, or chain drifted")
        if seq == 0 and event["event"] != "GENESIS":
            raise ValueError("ledger does not start with GENESIS")
        if events and events[-1]["event"] == "SEGMENT_SEAL":
            raise ValueError("ledger has bytes after SEGMENT_SEAL")
        current_writer = event.get("writer_id")
        current_scope = event.get("scope_id")
        if type(current_writer) is not str or not current_writer or type(current_scope) is not str or not current_scope:
            raise ValueError("ledger writer/scope identity is invalid")
        writer_id = writer_id or current_writer
        scope_id = scope_id or current_scope
        if current_writer != writer_id or current_scope != scope_id:
            raise ValueError("ledger writer/scope identity drifted")
        events.append(event)
        previous = hashlib.sha256(line).hexdigest()
    if not events or events[-1]["event"] != "SEGMENT_SEAL":
        raise ValueError("ledger segment is not sealed")
    counts = Counter(str(event["event"]) for event in events)
    return {
        "events": events,
        "event_count": len(events),
        "event_counts": dict(sorted(counts.items())),
        "tail_hash": previous,
        "writer_id": writer_id,
        "scope_id": scope_id,
    }


def verify_arm_cut_counts(
    *,
    arm_result: object,
    ledger_raw: bytes,
    expected_head: str = EXPECTED_HEAD,
) -> dict[str, object]:
    """Rebuild GENERATED/COMPILED/APPLIED counts from one sealed arm ledger."""

    if type(arm_result) is not dict:
        raise ValueError("arm result must be an object")
    authority = arm_result.get("authority")
    if type(authority) is not dict or authority.get("repository_head") != expected_head:
        raise ValueError("arm result repository HEAD drift")
    arm = arm_result.get("arm")
    if arm not in {"control", "treatment"}:
        raise ValueError("arm result label is invalid")
    ledger = arm_result.get("ledger")
    injection = arm_result.get("injection")
    if type(ledger) is not dict or type(injection) is not dict:
        raise ValueError("arm result lacks ledger or injection evidence")
    replay = replay_ledger(ledger_raw)
    counts = replay["event_counts"]
    generated = counts.get("GENERATED", 0)
    applied = counts.get("APPLIED", 0)
    compiled_records = injection.get("compiled_records")
    compiled = injection.get("compiled_observed")
    exact_ints = (
        ledger.get("event_count"),
        ledger.get("generated"),
        ledger.get("applied"),
        compiled,
        injection.get("arithmetic_sample_count"),
    )
    if any(type(value) is not int or value < 0 for value in exact_ints):
        raise ValueError("arm cut counters must be exact nonnegative integers")
    if (
        ledger.get("status") != "complete"
        or ledger.get("event_count") != replay["event_count"]
        or ledger.get("event_counts") != counts
        or ledger.get("tail_hash") != replay["tail_hash"]
        or ledger.get("generated") != generated
        or ledger.get("applied") != applied
        or type(compiled_records) is not list
        or compiled != len(compiled_records)
    ):
        raise ValueError("arm result cut counters differ from the sealed ledger/compiled records")
    return {
        "arm": arm,
        "generated": generated,
        "compiled": compiled,
        "applied": applied,
        "ledger": replay,
    }


def verify_binary_prestate(
    *,
    model_raw: bytes,
    response_raw: bytes,
    selector_contract: object,
    arm_result: object,
    expected_head: str = EXPECTED_HEAD,
) -> GhostTruth:
    """Derive selector truth from official binaries, then check reported prestate."""

    if type(arm_result) is not dict:
        raise ValueError("arm result must be an object")
    authority = arm_result.get("authority")
    if type(authority) is not dict or authority.get("repository_head") != expected_head:
        raise ValueError("arm result repository HEAD drift")
    model = parse_model(model_raw)
    response = parse_response(response_raw)
    truth = derive_ghost_truth(model, response, selector_contract)
    prestate = arm_result.get("prestate")
    if type(prestate) is not dict or type(prestate.get("incumbent")) is not dict:
        raise ValueError("arm result lacks frozen incumbent")
    incumbent = prestate["incumbent"]
    prestate_sha = _json_digest(incumbent)
    if prestate.get("incumbent_sha256") != prestate_sha:
        raise ValueError("incumbent digest drift")
    if prestate.get("model_binary_sha256") != hashlib.sha256(model_raw).hexdigest():
        raise ValueError("binary model identity drift")
    if prestate.get("response_binary_sha256") != hashlib.sha256(response_raw).hexdigest():
        raise ValueError("binary response identity drift")
    if prestate.get("model_variable_count") != truth.model_variable_count:
        raise ValueError("model variable count drift")
    if prestate.get("model_constraint_count") != truth.model_constraint_count:
        raise ValueError("model constraint count drift")
    expected_ghost = {
        "pose_id": f"ghost_anchor::{truth.anchor_x},{truth.anchor_y}",
        "pose_idx": truth.active_rect_idx,
        "anchor": {"x": truth.anchor_x, "y": truth.anchor_y},
    }
    if incumbent.get("ghost_pick") != expected_ghost or prestate.get("ghost_pick") != expected_ghost:
        raise ValueError("incumbent/prestate ghost differs from binary truth")
    return truth


def verify_applied_inequality(
    *,
    model_raw: bytes,
    response_raw: bytes,
    selector_contract: object,
    arm_result: object,
    compiled_record: object,
    sample: object,
    ledger_raw: bytes,
    frozen_assignment: object,
    mandatory_instances: object,
    candidate_placements: object,
    expected_head: str = EXPECTED_HEAD,
) -> dict[str, object]:
    """Verify one applied inequality after deriving binary selector truth."""

    if any(type(value) is not dict for value in (arm_result, compiled_record, sample)):
        raise ValueError("join inputs must be objects")
    truth = verify_binary_prestate(
        model_raw=model_raw,
        response_raw=response_raw,
        selector_contract=selector_contract,
        arm_result=arm_result,
        expected_head=expected_head,
    )
    counts = verify_arm_cut_counts(
        arm_result=arm_result,
        ledger_raw=ledger_raw,
        expected_head=expected_head,
    )
    if counts["arm"] != "treatment":
        raise ValueError("concrete APPLIED replay must use the treatment arm")
    prestate = arm_result["prestate"]
    incumbent = prestate["incumbent"]
    prestate_sha = _json_digest(incumbent)

    operation = compiled_record.get("operation")
    parameters = compiled_record.get("parameters")
    model_scope = compiled_record.get("model_scope")
    if type(model_scope) is not dict:
        plan = compiled_record.get("plan")
        model_scope = plan.get("model_scope") if type(plan) is dict else None
        if type(plan) is dict:
            operation = plan.get("operation")
            parameters = plan.get("parameters")
    if (
        type(model_scope) is not dict
        or model_scope.get("ghost_policy") != "bound"
        or model_scope.get("ghost_rect_digest") != truth.rectangle_digest
    ):
        raise ValueError("compiled plan is not bound to the binary-active rectangle")
    cut_id = compiled_record.get("cut_id")
    family = compiled_record.get("family")
    injection = arm_result["injection"]
    matching_compiled = [
        record for record in injection["compiled_records"] if type(record) is dict and record.get("cut_id") == cut_id
    ]
    if matching_compiled != [compiled_record]:
        raise ValueError("compiled cut is not the unique arm-result compiled record")
    if sample.get("cut_id") != cut_id or sample.get("family") != family:
        raise ValueError("sample/compiled cut identity drift")
    if sample.get("operation") != operation or sample.get("parameters") != parameters:
        raise ValueError("sample/compiled inequality plan drift")
    applied_events = [
        event
        for event in counts["ledger"]["events"]
        if event.get("event") == "APPLIED" and event.get("cut_id") == cut_id and event.get("family") == family
    ]
    if len(applied_events) != 1:
        raise ValueError("compiled cut does not have one unique APPLIED ledger event")
    applied_event = applied_events[0]
    if applied_event.get("cut_id") != cut_id or applied_event.get("family") != family:
        raise ValueError("APPLIED/compiled cut identity drift")
    receipt = applied_event.get("receipt")
    if (
        type(receipt) is not dict
        or receipt.get("apply_completed") is not True
        or type(receipt.get("count_delta")) is not int
        or receipt["count_delta"] <= 0
        or receipt.get("rect_idx") != truth.active_rect_idx
        or receipt.get("ghost_rect_digest") != truth.rectangle_digest
    ):
        raise ValueError("APPLIED receipt is not bound to the binary-active rectangle")

    expected_literal = {
        "index": truth.active_variable_index,
        "name": truth.active_variable_name,
    }
    condition_lits = receipt.get("condition_lits")
    if condition_lits != [expected_literal]:
        raise ValueError("APPLIED condition literal differs from binary truth")
    assignment = _literal_map(frozen_assignment, prestate_sha256=prestate_sha)
    assigned = assignment.get(truth.active_variable_index)
    if assigned != {**expected_literal, "value": 1}:
        raise ValueError("captured assignment differs from binary solution truth")
    enforcement = sample.get("enforcement_literals")
    if enforcement != [{**expected_literal, "value": 1}]:
        raise ValueError("sample enforcement literal differs from binary truth")
    if sample.get("enforcement_values") != [1]:
        raise ValueError("sample enforcement values differ from binary truth")

    groups = _selected_groups(
        mandatory=mandatory_instances,
        candidates=candidate_placements,
        incumbent=incumbent,
    )
    contributions, lhs, rhs = _recompute_arithmetic(operation, parameters, groups)
    if sample.get("contributions") != contributions:
        raise ValueError("sample contributions differ from independent geometry replay")
    if sample.get("lhs") != lhs or sample.get("rhs") != rhs:
        raise ValueError("sample inequality differs from independent geometry replay")
    if sample.get("active") is not True or sample.get("violated") is not (lhs > rhs):
        raise ValueError("sample active/violated flags differ from binary replay")
    if lhs <= rhs:
        raise ValueError("APPLIED inequality does not exclude the frozen incumbent")
    return {
        "schema_version": 3,
        "checker": "independent_arithmetic_check_v3",
        "status": "PASS_APPLIED_VIOLATION",
        "head": expected_head,
        "model_sha256": hashlib.sha256(model_raw).hexdigest(),
        "response_sha256": hashlib.sha256(response_raw).hexdigest(),
        "binary_truth": asdict(truth),
        "selected": {
            "cut_id": cut_id,
            "family": family,
            "operation": operation,
            "lhs": lhs,
            "rhs": rhs,
            "active": True,
            "violated": True,
        },
        "checks": [
            "canonical_binary_model_and_response",
            "complete_selector_domain_and_exactly_one",
            "full_feasible_solution_and_unique_active_selector",
            "incumbent_prestate_sample_applied_assignment_join",
            "independent_geometry_arithmetic_violation",
        ],
        "claim_boundary": {
            "established": ["one concrete APPLIED inequality is active and violated at the frozen binary assignment"],
            "not_established": [
                "cut-family global soundness",
                "runtime usefulness",
                "witness feasibility",
                "formal infeasibility",
            ],
        },
    }


def _write_exclusive(path: Path, value: object) -> None:
    absolute = _absolute(path)
    _reject_symlink_components(absolute)
    if absolute.exists() or absolute.is_symlink():
        raise FileExistsError(f"refusing to overwrite output: {absolute}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    fd = os.open(absolute, flags, 0o600)
    try:
        raw = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
        os.write(fd, raw + b"\n")
        os.fsync(fd)
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        model_raw, model_identity = read_snapshot(args.model)
        response_raw, response_identity = read_snapshot(args.response)
        contract_raw, contract_identity = read_snapshot(args.contract)
        contract = _strict_json(contract_raw, label="selector contract")
        truth = derive_ghost_truth(
            parse_model(model_raw),
            parse_response(response_raw),
            contract,
        )
        result: dict[str, object] = {
            "schema_version": 3,
            "checker": "independent_arithmetic_check_v3",
            "status": "PASS_BINARY_SELECTOR_TRUTH",
            "inputs": {
                "model": asdict(model_identity),
                "response": asdict(response_identity),
                "contract": asdict(contract_identity),
            },
            "binary_truth": asdict(truth),
        }
    except (OSError, ValueError, RuntimeError) as exc:
        result = {
            "schema_version": 3,
            "checker": "independent_arithmetic_check_v3",
            "status": "FAIL",
            "error": f"{type(exc).__name__}: {exc}",
        }
    _write_exclusive(args.output, result)
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
