#!/usr/bin/env python3
"""Independent replay of the Gate-1 v4 forced positive-control pair.

The checker does not import the positive-control runner or its provider.  It
starts from canonical binary ``CpModelProto``/``CpSolverResponse`` bytes and
strict mandatory/candidate data, derives the frozen selector and assignment,
reconstructs the one expected forced region-capacity inequality, and joins it
to the post-model constraint, compiled record, sample and sealed ledger.

Passing establishes only that one non-proof positive-control inequality was
active and violated at the common pre-injection incumbent.  It does not prove
the region-capacity family, runtime usefulness, SAT/UNSAT, or any production
claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from google.protobuf.message import DecodeError, Message
from ortools.sat import cp_model_pb2


SELECTION_SCHEMA = "noncert-cuts-gate1-v4-fixture-selection-v1"
DRILL_PURPOSE = "gate1_v4_e2e_drill"
FORMAL_SELECTION_SCHEMA = "noncert-cuts-gate1-v4-formal-positive-selection-v1"
FORMAL_PURPOSE = "gate1_v4_formal_campaign_positive_control"
PRODUCTION_DRILL_SELECTION_SCHEMA = "noncert-cuts-gate1-v4-production-drill-positive-selection-v1"
PRODUCTION_DRILL_PURPOSE = "gate1_v4_disposable_production_positive_control"
DRILL_RECEIPT_SCHEMA = "noncert-cuts-gate1-v4-independent-arithmetic-receipt-v1"
FORMAL_RECEIPT_SCHEMA = "noncert-cuts-gate1-v4-formal-independent-arithmetic-receipt-v1"
PRODUCTION_DRILL_RECEIPT_SCHEMA = "noncert-cuts-gate1-v4-production-drill-independent-arithmetic-receipt-v1"
FORMAL_ARM_SCHEMA = "noncert-cuts-gate1-v4-formal-positive-control-arm-v1"
FORMAL_COMPILED_SCHEMA = "noncert-cuts-gate1-v4-formal-production-compiled-record-v1"
FORMAL_ATTACH_SCHEMA = "noncert-cuts-gate1-v4-production-typed-attach-trace-v1"
FORMAL_ATTACH_TRIGGER = "binding_infeasible"
FORMAL_ATTACH_ITERATION = 1001
COMMON_SCHEMA = "noncert-cuts-gate1-v4-common-prestate-v1"
BINDING_SCHEMA = "noncert-cuts-gate1-v4-arm-prestate-binding-v1"
BINDING_SET_SCHEMA = "noncert-cuts-gate1-v4-binding-set-v1"
ARM_SCHEMA = "noncert-cuts-gate1-v4-positive-control-arm-v1"
ASSIGNMENT_SCHEMA = "noncert-cuts-gate1-v4-frozen-assignment-v1"
SAMPLE_SCHEMA = "noncert-cuts-gate1-v4-arithmetic-sample-v1"
LEDGER_SCHEMA = "cut-ledger-v1"
EXPECTED_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
_GHOST_PREFIX = "ghost__"
_GHOST_DIGEST_PREFIX = b"zmd.ghost-rect.v1:"
_GENESIS_HASH = "0" * 64
_EPOCH_INSTANCE_RE = re.compile(r"epoch-[1-9][0-9]*-[0-9a-f]{12}-[0-9]{6}\Z")
_LEDGER_EVENTS = frozenset(
    {
        "GENESIS",
        "GENERATED",
        "VALIDATED",
        "PREPARED",
        "APPLIED",
        "SEGMENT_SEAL",
    }
)


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _strict_json(raw: bytes, *, label: str) -> object:
    def no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=no_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"{label}: invalid constant {token}")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}: invalid strict JSON") from exc


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


def read_snapshot(path: Path) -> tuple[bytes, dict[str, object]]:
    """Read one regular input through one stable O_NOFOLLOW descriptor."""

    absolute = _absolute(path)
    _reject_symlink_components(absolute)
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("O_NOFOLLOW is required")
    fd = os.open(absolute, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"input is not a regular file: {absolute}")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(fd, min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError(f"input truncated during snapshot: {absolute}")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(fd, 1):
            raise ValueError(f"input grew during snapshot: {absolute}")
        after = os.fstat(fd)
        named = os.lstat(absolute)
        stable = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, key) != getattr(after, key) for key in stable):
            raise ValueError(f"input changed during snapshot: {absolute}")
        if (
            stat.S_ISLNK(named.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or named.st_dev != after.st_dev
            or named.st_ino != after.st_ino
        ):
            raise ValueError(f"input pathname changed during snapshot: {absolute}")
    finally:
        os.close(fd)
    raw = b"".join(chunks)
    return raw, {
        "path": str(absolute),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _read_canonical_json(path: Path, *, label: str) -> tuple[object, dict[str, object]]:
    raw, identity = read_snapshot(path)
    if not raw.endswith(b"\n"):
        raise ValueError(f"{label}: canonical JSON lacks final newline")
    value = _strict_json(raw[:-1], label=label)
    if raw != canonical_json(value) + b"\n":
        raise ValueError(f"{label}: JSON bytes are not canonical")
    return value, identity


def _parse_canonical_proto(raw: bytes, message: Message, *, label: str) -> Message:
    if not raw:
        raise ValueError(f"{label}: empty protobuf rejected")
    try:
        consumed = message.ParseFromString(raw)
    except DecodeError as exc:
        raise ValueError(f"{label}: malformed protobuf") from exc
    if consumed != len(raw):
        raise ValueError(f"{label}: parser did not consume every byte")
    clean = type(message)()
    clean.CopyFrom(message)
    clean.DiscardUnknownFields()
    if clean.SerializeToString(deterministic=True) != raw:
        raise ValueError(f"{label}: unknown, duplicate, or noncanonical protobuf")
    return clean


def _strict_identity(value: object, *, label: str) -> dict[str, object]:
    if (
        type(value) is not dict
        or set(value) != {"path", "size_bytes", "sha256"}
        or type(value["path"]) is not str
        or not Path(value["path"]).is_absolute()
        or type(value["size_bytes"]) is not int
        or value["size_bytes"] < 0
        or type(value["sha256"]) is not str
        or len(value["sha256"]) != 64
        or value["sha256"] != value["sha256"].lower()
    ):
        raise ValueError(f"{label}: invalid file identity")
    try:
        int(value["sha256"], 16)
    except ValueError as exc:
        raise ValueError(f"{label}: invalid SHA-256") from exc
    return dict(value)


def _require_identity(actual: object, reported: object, *, label: str) -> None:
    if _strict_identity(actual, label=f"{label} actual") != _strict_identity(
        reported,
        label=f"{label} reported",
    ):
        raise ValueError(f"{label}: detached identity drift")


def _rectangle_digest(x: int, y: int, width: int, height: int) -> str:
    return hashlib.sha256(_GHOST_DIGEST_PREFIX + canonical_json([x, y, width, height])).hexdigest()


def derive_ghost_truth(
    model: cp_model_pb2.CpModelProto,
    response: cp_model_pb2.CpSolverResponse,
    contract: object,
) -> dict[str, object]:
    """Derive selector name/index/rectangle from binary authority only."""

    if (
        type(contract) is not dict
        or set(contract) != {"schema_version", "grid", "ghost"}
        or contract["schema_version"] != 1
        or type(contract["grid"]) is not dict
        or set(contract["grid"]) != {"width", "height"}
        or type(contract["ghost"]) is not dict
        or set(contract["ghost"]) != {"width", "height"}
    ):
        raise ValueError("selector contract drifted")
    values = (
        contract["grid"]["width"],
        contract["grid"]["height"],
        contract["ghost"]["width"],
        contract["ghost"]["height"],
    )
    if any(type(value) is not int or value < 1 for value in values):
        raise ValueError("selector dimensions must be exact positive integers")
    grid_w, grid_h, ghost_w, ghost_h = values
    if ghost_w > grid_w or ghost_h > grid_h:
        raise ValueError("ghost dimensions exceed grid")
    anchors = [
        (x, y, f"{_GHOST_PREFIX}{x}_{y}_{ghost_w}_{ghost_h}")
        for x in range(grid_w - ghost_w + 1)
        for y in range(grid_h - ghost_h + 1)
    ]
    expected_names = {name for _x, _y, name in anchors}
    by_name: dict[str, list[int]] = defaultdict(list)
    for index, variable in enumerate(model.variables):
        by_name[str(variable.name)].append(index)
    unexpected = sorted(name for name in by_name if name.startswith(_GHOST_PREFIX) and name not in expected_names)
    if unexpected:
        raise ValueError(f"unexpected ghost selector: {unexpected[0]}")
    indices: list[int] = []
    for _x, _y, name in anchors:
        if len(by_name.get(name, [])) != 1:
            raise ValueError(f"ghost selector must occur exactly once: {name}")
        index = by_name[name][0]
        if list(model.variables[index].domain) != [0, 1]:
            raise ValueError(f"ghost selector has non-Boolean domain: {name}")
        indices.append(index)
    matching = []
    for constraint in model.constraints:
        if constraint.WhichOneof("constraint") != "exactly_one":
            continue
        literals = [int(value) for value in constraint.exactly_one.literals]
        if set(literals).intersection(indices):
            matching.append(literals)
    if (
        len(matching) != 1
        or len(matching[0]) != len(indices)
        or len(set(matching[0])) != len(indices)
        or set(matching[0]) != set(indices)
    ):
        raise ValueError("model lacks one exact complete ghost-selector constraint")
    if response.status not in {cp_model_pb2.FEASIBLE, cp_model_pb2.OPTIMAL}:
        raise ValueError("pre-response is not FEASIBLE or OPTIMAL")
    if len(response.solution) != len(model.variables):
        raise ValueError("pre-response lacks a full solution vector")
    active: list[int] = []
    for ordinal, index in enumerate(indices):
        value = int(response.solution[index])
        if value not in {0, 1}:
            raise ValueError("pre-response assigns a non-Boolean ghost value")
        if value == 1:
            active.append(ordinal)
    if len(active) != 1:
        raise ValueError("pre-response must activate exactly one ghost selector")
    ordinal = active[0]
    x, y, name = anchors[ordinal]
    return {
        "ordinal": ordinal,
        "variable_index": indices[ordinal],
        "variable_name": name,
        "anchor": {"x": x, "y": y},
        "rectangle_digest": _rectangle_digest(x, y, ghost_w, ghost_h),
    }


def _mandatory_groups(
    mandatory: object,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    if type(mandatory) is not list or not mandatory:
        raise ValueError("mandatory instances must be a non-empty list")
    instances: dict[str, dict[str, Any]] = {}
    buckets: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in mandatory:
        if type(row) is not dict:
            raise ValueError("mandatory instance must be an object")
        instance_id = row.get("instance_id")
        facility = row.get("facility_type")
        operation = row.get("operation_type")
        if not all(type(value) is str and value for value in (instance_id, facility, operation)):
            raise ValueError("mandatory identity fields are malformed")
        if instance_id in instances:
            raise ValueError(f"duplicate mandatory instance: {instance_id}")
        if row.get("is_mandatory") is not True or row.get("bound_type") != "exact":
            raise ValueError(f"instance is not mandatory exact: {instance_id}")
        instances[instance_id] = row
        buckets[(facility, operation)].append(instance_id)
    groups: dict[str, list[str]] = {}
    for group_index, ((facility, operation), members) in enumerate(sorted(buckets.items())):
        groups[f"group::{facility}::{operation}::{group_index}"] = sorted(members)
    return instances, groups


def _derive_selected_group(
    mandatory: object,
    candidates: object,
    incumbent: object,
) -> tuple[str, list[str]]:
    instances, groups = _mandatory_groups(mandatory)
    if (
        type(candidates) is not dict
        or type(candidates.get("facility_pools")) is not dict
        or type(incumbent) is not dict
    ):
        raise ValueError("candidate placements or incumbent malformed")
    selected_pose_ids: dict[str, str] = {}
    for instance_id, strict in instances.items():
        entry = incumbent.get(instance_id)
        if type(entry) is not dict:
            raise ValueError(f"incumbent omits {instance_id}")
        if any(entry.get(field) != strict[field] for field in ("instance_id", "facility_type", "operation_type")):
            raise ValueError(f"incumbent identity drift for {instance_id}")
        pool = candidates["facility_pools"].get(strict["facility_type"])
        if type(pool) is not list or not pool:
            raise ValueError(f"candidate pool missing for {strict['facility_type']}")
        pose_idx = entry.get("pose_idx")
        if type(pose_idx) is not int or pose_idx < 0 or pose_idx >= len(pool):
            raise ValueError(f"incumbent pose index malformed for {instance_id}")
        pose = pool[pose_idx]
        if (
            type(pose) is not dict
            or entry.get("pose_id") != pose.get("pose_id")
            or entry.get("anchor") != pose.get("anchor")
        ):
            raise ValueError(f"incumbent pose identity drift for {instance_id}")
        selected_pose_ids[instance_id] = str(entry["pose_id"])
    eligible = [
        (group_id, members)
        for group_id, members in sorted(groups.items())
        if members and len({selected_pose_ids[instance_id] for instance_id in members}) == len(members)
    ]
    if not eligible:
        raise ValueError("no lexicographic mandatory group is eligible")
    return eligible[0]


def _selection_variable_map(model: cp_model_pb2.CpModelProto) -> dict[str, int]:
    result: dict[str, int] = {}
    for index, variable in enumerate(model.variables):
        name = str(variable.name)
        if not name.startswith("select__"):
            continue
        instance_id = name[len("select__") :]
        if not instance_id or instance_id in result or list(variable.domain) != [0, 1]:
            raise ValueError("selection-variable identity/domain drift")
        result[instance_id] = index
    return result


def replay_ledger(raw: bytes) -> dict[str, object]:
    if not raw or not raw.endswith(b"\n"):
        raise ValueError("ledger lacks its final newline")
    previous = _GENESIS_HASH
    events: list[dict[str, Any]] = []
    writer_id: str | None = None
    scope_id: str | None = None
    for sequence, line in enumerate(raw.splitlines()):
        value = _strict_json(line, label=f"ledger line {sequence}")
        if type(value) is not dict or canonical_json(value) != line:
            raise ValueError(f"ledger line {sequence} is not canonical JSON")
        if (
            value.get("schema_version") != LEDGER_SCHEMA
            or value.get("seq") != sequence
            or value.get("event") not in _LEDGER_EVENTS
            or value.get("prev_event_hash") != previous
        ):
            raise ValueError(f"ledger line {sequence} schema/sequence/chain drift")
        if sequence == 0 and value["event"] != "GENESIS":
            raise ValueError("ledger does not begin with GENESIS")
        if events and events[-1]["event"] == "SEGMENT_SEAL":
            raise ValueError("ledger contains bytes after SEGMENT_SEAL")
        current_writer = value.get("writer_id")
        current_scope = value.get("scope_id")
        if type(current_writer) is not str or not current_writer or type(current_scope) is not str or not current_scope:
            raise ValueError("ledger writer/scope identity malformed")
        writer_id = writer_id or current_writer
        scope_id = scope_id or current_scope
        if current_writer != writer_id or current_scope != scope_id:
            raise ValueError("ledger writer/scope identity drift")
        events.append(value)
        previous = hashlib.sha256(line).hexdigest()
    if not events or events[-1]["event"] != "SEGMENT_SEAL":
        raise ValueError("ledger is not sealed")
    return {
        "events": events,
        "event_count": len(events),
        "event_counts": dict(sorted(Counter(event["event"] for event in events).items())),
        "tail_hash": previous,
        "writer_id": writer_id,
        "scope_id": scope_id,
    }


def _event_core(event: Mapping[str, object]) -> dict[str, object]:
    metadata = {
        "schema_version",
        "seq",
        "prev_event_hash",
        "writer_id",
        "scope_id",
        "wallclock_utc",
    }
    return {key: value for key, value in event.items() if key not in metadata}


def load_fixture(root: Path) -> dict[str, object]:
    """Snapshot every fixture member once; return bytes plus detached identities."""

    root = _absolute(root)
    selection, selection_identity = _read_canonical_json(
        root / "selection.json",
        label="selection",
    )
    common, common_identity = _read_canonical_json(
        root / "common-prestate" / "manifest.json",
        label="common manifest",
    )
    common_files = {
        "pre_model": root / "common-prestate" / "pre-injection-model.pb",
        "response": root / "common-prestate" / "pre-injection-response.pb",
        "solution": root / "common-prestate" / "solution.json",
        "incumbent": root / "common-prestate" / "incumbent.json",
        "selector_contract": root / "common-prestate" / "selector-contract.json",
        "mandatory": root / "common-prestate" / "mandatory.json",
        "candidates": root / "common-prestate" / "candidates.json",
    }
    common_artifacts: dict[str, dict[str, object]] = {}
    for role, path in common_files.items():
        raw, identity = read_snapshot(path)
        common_artifacts[role] = {"raw": raw, "identity": identity}
    binding_seal, binding_seal_identity = _read_canonical_json(
        root / "bindings" / "bindings-seal.json",
        label="binding-set seal",
    )
    bindings: dict[str, dict[str, object]] = {}
    arms: dict[str, dict[str, object]] = {}
    for arm in ("control", "treatment"):
        binding, binding_identity = _read_canonical_json(
            root / "bindings" / f"{arm}.json",
            label=f"{arm} binding",
        )
        bindings[arm] = {"value": binding, "identity": binding_identity}
        evidence, evidence_identity = _read_canonical_json(
            root / "arms" / arm / "evidence.json",
            label=f"{arm} evidence",
        )
        arm_members: dict[str, dict[str, object]] = {}
        for role, filename in {
            "post_model": "post-injection-model.pb",
            "assignment": "assignment.json",
            "samples": "arithmetic-samples.json",
            "ledger": "ledger.jsonl",
        }.items():
            raw, identity = read_snapshot(root / "arms" / arm / filename)
            arm_members[role] = {"raw": raw, "identity": identity}
        arms[arm] = {
            "evidence": evidence,
            "evidence_identity": evidence_identity,
            "members": arm_members,
        }
    return {
        "root": str(root),
        "selection": selection,
        "selection_identity": selection_identity,
        "common": common,
        "common_identity": common_identity,
        "common_artifacts": common_artifacts,
        "binding_seal": binding_seal,
        "binding_seal_identity": binding_seal_identity,
        "bindings": bindings,
        "arms": arms,
    }


def _parse_json_member(member: Mapping[str, object], *, label: str) -> object:
    raw = member.get("raw")
    if type(raw) is not bytes or not raw.endswith(b"\n"):
        raise ValueError(f"{label}: canonical JSON member malformed")
    value = _strict_json(raw[:-1], label=label)
    if raw != canonical_json(value) + b"\n":
        raise ValueError(f"{label}: JSON bytes are not canonical")
    return value


def _verify_selection_and_common(
    bundle: Mapping[str, object],
    *,
    selection_schema: str = SELECTION_SCHEMA,
    purpose: str = DRILL_PURPOSE,
    formal_eligible: bool = False,
) -> dict[str, object]:
    selection = bundle.get("selection")
    selection_identity = bundle.get("selection_identity")
    if (
        type(selection) is not dict
        or set(selection)
        != {
            "schema",
            "purpose",
            "campaign_id",
            "run_nonce",
            "manager_epoch_digest",
            "gate1_formal_eligible",
        }
        or selection.get("schema") != selection_schema
        or selection.get("purpose") != purpose
        or selection.get("gate1_formal_eligible") is not formal_eligible
    ):
        profile = "formal campaign" if formal_eligible else "offline fixture"
        raise ValueError(f"{profile} selection drifted")
    selection_identity = _strict_identity(
        selection_identity,
        label="selection identity",
    )
    common = bundle.get("common")
    common_identity = _strict_identity(
        bundle.get("common_identity"),
        label="common manifest identity",
    )
    expected_common_keys = {
        "schema",
        "phase",
        "campaign_id",
        "run_nonce",
        "manager_epoch_digest",
        "repository_head",
        "selection_identity",
        "common_prestate_id",
        "artifacts",
        "model_variable_count",
        "model_constraint_count",
        "response_status",
        "ghost_truth",
        "post_model_paths_absent_at_seal",
        "post_solve_performed",
    }
    if (
        type(common) is not dict
        or set(common) != expected_common_keys
        or common.get("schema") != COMMON_SCHEMA
        or common.get("phase") != "pre_injection"
        or common.get("repository_head") != EXPECTED_HEAD
        or common.get("post_solve_performed") is not False
        or common.get("campaign_id") != selection["campaign_id"]
        or common.get("run_nonce") != selection["run_nonce"]
        or common.get("manager_epoch_digest") != selection["manager_epoch_digest"]
    ):
        raise ValueError("common-prestate manifest drifted")
    _require_identity(selection_identity, common["selection_identity"], label="common selection")
    artifacts = bundle.get("common_artifacts")
    if type(artifacts) is not dict or set(artifacts) != {
        "pre_model",
        "response",
        "solution",
        "incumbent",
        "selector_contract",
        "mandatory",
        "candidates",
    }:
        raise ValueError("common artifact bundle drifted")
    reported_artifacts = common.get("artifacts")
    if type(reported_artifacts) is not dict or set(reported_artifacts) != set(artifacts):
        raise ValueError("common artifact manifest drifted")
    for role, member in artifacts.items():
        if type(member) is not dict:
            raise ValueError(f"common artifact {role} malformed")
        _require_identity(
            member.get("identity"),
            reported_artifacts[role],
            label=f"common artifact {role}",
        )
    expected_common_id = digest_json(
        {
            "campaign_id": common["campaign_id"],
            "run_nonce": common["run_nonce"],
            "manager_epoch_digest": common["manager_epoch_digest"],
            "selection_identity": selection_identity,
            "artifacts": reported_artifacts,
            "phase": "pre_injection",
        }
    )
    if common.get("common_prestate_id") != expected_common_id:
        raise ValueError("common-prestate identity drift")
    return {
        "selection": selection,
        "selection_identity": selection_identity,
        "common": common,
        "common_identity": common_identity,
        "artifacts": artifacts,
    }


def _verify_binary_prestate(state: Mapping[str, object]) -> dict[str, object]:
    common = state["common"]
    artifacts = state["artifacts"]
    model_raw = artifacts["pre_model"]["raw"]
    response_raw = artifacts["response"]["raw"]
    if type(model_raw) is not bytes or type(response_raw) is not bytes:
        raise ValueError("binary common-prestate members malformed")
    model = _parse_canonical_proto(
        model_raw,
        cp_model_pb2.CpModelProto(),
        label="pre-model",
    )
    response = _parse_canonical_proto(
        response_raw,
        cp_model_pb2.CpSolverResponse(),
        label="pre-response",
    )
    solution = _parse_json_member(artifacts["solution"], label="solution")
    incumbent = _parse_json_member(artifacts["incumbent"], label="incumbent")
    contract = _parse_json_member(
        artifacts["selector_contract"],
        label="selector contract",
    )
    mandatory = _parse_json_member(artifacts["mandatory"], label="mandatory")
    candidates = _parse_json_member(artifacts["candidates"], label="candidates")
    if (
        type(solution) is not list
        or any(type(value) is not int for value in solution)
        or solution != list(response.solution)
    ):
        raise ValueError("sealed solution differs from binary response")
    truth = derive_ghost_truth(model, response, contract)
    expected_ghost = {
        "pose_id": f"ghost_anchor::{truth['anchor']['x']},{truth['anchor']['y']}",
        "pose_idx": truth["ordinal"],
        "anchor": truth["anchor"],
    }
    if type(incumbent) is not dict or incumbent.get("ghost_pick") != expected_ghost:
        raise ValueError("incumbent ghost differs from binary response truth")
    if common.get("ghost_truth") != truth:
        raise ValueError("reported ghost truth differs from binary authority")
    if (
        common.get("model_variable_count") != len(model.variables)
        or common.get("model_constraint_count") != len(model.constraints)
        or common.get("response_status") != int(response.status)
    ):
        raise ValueError("reported binary dimensions/status drifted")
    group_id, members = _derive_selected_group(mandatory, candidates, incumbent)
    variable_map = _selection_variable_map(model)
    if any(member not in variable_map for member in members):
        raise ValueError("pre-model omits a selected variable for the forced group")
    selected_indices = [variable_map[member] for member in members]
    if any(int(response.solution[index]) != 1 for index in selected_indices):
        raise ValueError("forced group is not selected in the frozen response")
    return {
        **state,
        "model_raw": model_raw,
        "response_raw": response_raw,
        "model": model,
        "response": response,
        "solution": solution,
        "incumbent": incumbent,
        "contract": contract,
        "mandatory": mandatory,
        "candidates": candidates,
        "truth": truth,
        "group_id": group_id,
        "members": members,
        "selected_indices": selected_indices,
    }


def _verify_bindings(bundle: Mapping[str, object], state: Mapping[str, object]) -> None:
    seal = bundle.get("binding_seal")
    seal_identity = _strict_identity(
        bundle.get("binding_seal_identity"),
        label="binding-set identity",
    )
    common = state["common"]
    expected_seal_keys = {
        "schema",
        "phase",
        "campaign_id",
        "run_nonce",
        "manager_epoch_digest",
        "selection_identity",
        "common_prestate_id",
        "common_manifest_identity",
        "bindings",
        "post_model_paths_absent_at_seal",
    }
    if (
        type(seal) is not dict
        or set(seal) != expected_seal_keys
        or seal.get("schema") != BINDING_SET_SCHEMA
        or seal.get("phase") != "both_arms_bound_before_clone"
        or seal.get("campaign_id") != common["campaign_id"]
        or seal.get("run_nonce") != common["run_nonce"]
        or seal.get("manager_epoch_digest") != common["manager_epoch_digest"]
        or seal.get("common_prestate_id") != common["common_prestate_id"]
    ):
        raise ValueError("binding-set seal drifted")
    _require_identity(
        state["selection_identity"],
        seal["selection_identity"],
        label="binding-set selection",
    )
    _require_identity(
        state["common_identity"],
        seal["common_manifest_identity"],
        label="binding-set common manifest",
    )
    bindings = bundle.get("bindings")
    if (
        type(bindings) is not dict
        or set(bindings) != {"control", "treatment"}
        or type(seal.get("bindings")) is not dict
        or set(seal["bindings"]) != {"control", "treatment"}
    ):
        raise ValueError("binding-set arm map drifted")
    for arm in ("control", "treatment"):
        member = bindings[arm]
        if type(member) is not dict or type(member.get("value")) is not dict:
            raise ValueError(f"{arm} binding malformed")
        binding = member["value"]
        if (
            set(binding)
            != {
                "schema",
                "arm",
                "phase",
                "campaign_id",
                "run_nonce",
                "manager_epoch_digest",
                "selection_identity",
                "common_prestate_id",
                "common_manifest_identity",
                "post_model_path_absent_at_binding",
            }
            or binding.get("schema") != BINDING_SCHEMA
            or binding.get("arm") != arm
            or binding.get("phase") != "pre_injection_binding"
            or binding.get("campaign_id") != common["campaign_id"]
            or binding.get("run_nonce") != common["run_nonce"]
            or binding.get("manager_epoch_digest") != common["manager_epoch_digest"]
            or binding.get("common_prestate_id") != common["common_prestate_id"]
        ):
            raise ValueError(f"{arm} binding drifted")
        _require_identity(
            state["selection_identity"],
            binding["selection_identity"],
            label=f"{arm} binding selection",
        )
        _require_identity(
            state["common_identity"],
            binding["common_manifest_identity"],
            label=f"{arm} binding common manifest",
        )
        _require_identity(
            member.get("identity"),
            seal["bindings"][arm],
            label=f"{arm} binding identity",
        )
    state["binding_set_identity"] = seal_identity


def _expected_assignment(state: Mapping[str, object]) -> dict[str, object]:
    model = state["model"]
    response = state["response"]
    return {
        "schema": ASSIGNMENT_SCHEMA,
        "common_prestate_id": state["common"]["common_prestate_id"],
        "pre_model_sha256": hashlib.sha256(state["model_raw"]).hexdigest(),
        "response_sha256": hashlib.sha256(state["response_raw"]).hexdigest(),
        "variables": [
            {
                "index": index,
                "name": str(model.variables[index].name),
                "value": int(response.solution[index]),
            }
            for index in range(len(model.variables))
        ],
    }


def _expected_treatment(state: Mapping[str, object]) -> dict[str, object]:
    truth = state["truth"]
    capacity = len(state["members"]) - 1
    plan = {
        "schema_version": 1,
        "family": "region_capacity",
        "operation": "region_capacity_le",
        "parameters": {
            "capacity": capacity,
            "group_cell_weights": {state["group_id"]: 1},
        },
        "model_scope": {
            "ghost_policy": "bound",
            "ghost_rect_digest": truth["rectangle_digest"],
        },
        "non_proof_forced_positive_control": True,
    }
    plan_digest = digest_json(plan)
    cut_id = (
        "forced-region-capacity-"
        + digest_json(
            {
                "common_prestate_id": state["common"]["common_prestate_id"],
                "group_id": state["group_id"],
                "plan_digest": plan_digest,
            }
        )[:24]
    )
    compiled_digest = digest_json(
        {
            "cut_id": cut_id,
            "plan_digest": plan_digest,
            "common_prestate_id": state["common"]["common_prestate_id"],
        }
    )
    condition_literals = [
        {
            "index": truth["variable_index"],
            "name": truth["variable_name"],
        }
    ]
    constraint_index = len(state["model"].constraints)
    constraint_name = f"nonproof_forced_region_capacity__{cut_id}"
    compiled = {
        "schema": "noncert-cuts-gate1-v4-compiled-record-v1",
        "cut_id": cut_id,
        "family": "region_capacity",
        "operation": "region_capacity_le",
        "plan": plan,
        "plan_digest": plan_digest,
        "compiled_digest": compiled_digest,
        "condition_literals": condition_literals,
        "post_constraint": {
            "index": constraint_index,
            "name": constraint_name,
            "vars": state["selected_indices"],
            "coeffs": [1] * len(state["selected_indices"]),
            "domain": [0, capacity],
            "enforcement_literals": [truth["variable_index"]],
        },
    }
    sample = {
        "schema": SAMPLE_SCHEMA,
        "cut_id": cut_id,
        "family": "region_capacity",
        "operation": "region_capacity_le",
        "plan_digest": plan_digest,
        "compiled_digest": compiled_digest,
        "parameters": plan["parameters"],
        "enforcement_literals": [
            {
                **condition_literals[0],
                "value": int(state["response"].solution[truth["variable_index"]]),
            }
        ],
        "contributions": [
            {
                "label": state["group_id"],
                "selected_count": len(state["members"]),
                "weight": 1,
                "value": len(state["members"]),
            }
        ],
        "lhs": len(state["members"]),
        "rhs": capacity,
        "active": True,
        "violated": True,
    }
    ledger_core = [
        {
            "event": "GENESIS",
            "arm": "treatment",
            "common_prestate_id": state["common"]["common_prestate_id"],
        },
        {
            "event": "GENERATED",
            "cut_id": cut_id,
            "family": "region_capacity",
            "plan_digest": plan_digest,
        },
        {
            "event": "VALIDATED",
            "cut_id": cut_id,
            "family": "region_capacity",
            "plan_digest": plan_digest,
            "compiled_digest": compiled_digest,
        },
        {
            "event": "PREPARED",
            "cut_id": cut_id,
            "family": "region_capacity",
            "compiled_digest": compiled_digest,
        },
        {
            "event": "APPLIED",
            "cut_id": cut_id,
            "family": "region_capacity",
            "plan_digest": plan_digest,
            "compiled_digest": compiled_digest,
            "receipt": {
                "apply_completed": True,
                "count_delta": 1,
                "constraint_index": constraint_index,
                "condition_lits": condition_literals,
                "common_prestate_id": state["common"]["common_prestate_id"],
            },
        },
        {"event": "SEGMENT_SEAL"},
    ]
    return {
        "capacity": capacity,
        "compiled": compiled,
        "sample": sample,
        "ledger_core": ledger_core,
    }


def _verify_post_model(
    *,
    arm: str,
    raw: object,
    state: Mapping[str, object],
    expected: Mapping[str, object] | None,
) -> None:
    if type(raw) is not bytes:
        raise ValueError(f"{arm} post-model bytes malformed")
    post = _parse_canonical_proto(
        raw,
        cp_model_pb2.CpModelProto(),
        label=f"{arm} post-model",
    )
    if arm == "control":
        if raw != state["model_raw"]:
            raise ValueError("control post-model differs from pre-injection model")
        return
    if len(post.constraints) != len(state["model"].constraints) + 1:
        raise ValueError("treatment post-model must add exactly one constraint")
    stripped = cp_model_pb2.CpModelProto()
    stripped.CopyFrom(post)
    del stripped.constraints[-1]
    if stripped.SerializeToString(deterministic=True) != state["model_raw"]:
        raise ValueError("treatment changed bytes outside its one post constraint")
    reported = expected["compiled"]["post_constraint"]
    constraint = post.constraints[-1]
    actual = {
        "index": len(post.constraints) - 1,
        "name": str(constraint.name),
        "vars": list(constraint.linear.vars),
        "coeffs": list(constraint.linear.coeffs),
        "domain": list(constraint.linear.domain),
        "enforcement_literals": list(constraint.enforcement_literal),
    }
    if constraint.WhichOneof("constraint") != "linear" or actual != reported:
        raise ValueError("treatment post-model inequality differs from independent reconstruction")


def _verify_arm(
    arm: str,
    member: object,
    bundle: Mapping[str, object],
    state: Mapping[str, object],
    expected_treatment: Mapping[str, object],
) -> dict[str, int]:
    if type(member) is not dict or type(member.get("members")) is not dict:
        raise ValueError(f"{arm} arm bundle malformed")
    evidence = member.get("evidence")
    expected_evidence_keys = {
        "schema",
        "arm",
        "phase",
        "campaign_id",
        "run_nonce",
        "manager_epoch_digest",
        "selection_identity",
        "common_prestate_id",
        "common_manifest_identity",
        "binding_identity",
        "binding_set_identity",
        "pre_model_identity",
        "pre_response_identity",
        "post_model_identity",
        "assignment_identity",
        "sample_corpus_identity",
        "ledger_identity",
        "post_solve_performed",
        "post_response_present",
        "injection",
        "ledger",
        "claim_boundary",
    }
    common = state["common"]
    if (
        type(evidence) is not dict
        or set(evidence) != expected_evidence_keys
        or evidence.get("schema") != ARM_SCHEMA
        or evidence.get("arm") != arm
        or evidence.get("phase") != "post_injection_clone"
        or evidence.get("campaign_id") != common["campaign_id"]
        or evidence.get("run_nonce") != common["run_nonce"]
        or evidence.get("manager_epoch_digest") != common["manager_epoch_digest"]
        or evidence.get("common_prestate_id") != common["common_prestate_id"]
        or evidence.get("post_solve_performed") is not False
        or evidence.get("post_response_present") is not False
    ):
        raise ValueError(f"{arm} evidence schema/provenance drifted")
    _require_identity(
        state["selection_identity"],
        evidence["selection_identity"],
        label=f"{arm} selection",
    )
    _require_identity(
        state["common_identity"],
        evidence["common_manifest_identity"],
        label=f"{arm} common manifest",
    )
    binding = bundle["bindings"][arm]
    _require_identity(
        binding["identity"],
        evidence["binding_identity"],
        label=f"{arm} binding",
    )
    _require_identity(
        bundle["binding_seal_identity"],
        evidence["binding_set_identity"],
        label=f"{arm} binding set",
    )
    _require_identity(
        state["artifacts"]["pre_model"]["identity"],
        evidence["pre_model_identity"],
        label=f"{arm} pre-model",
    )
    _require_identity(
        state["artifacts"]["response"]["identity"],
        evidence["pre_response_identity"],
        label=f"{arm} pre-response",
    )
    members = member["members"]
    if set(members) != {"post_model", "assignment", "samples", "ledger"}:
        raise ValueError(f"{arm} member set drifted")
    for role, evidence_key in {
        "post_model": "post_model_identity",
        "assignment": "assignment_identity",
        "samples": "sample_corpus_identity",
        "ledger": "ledger_identity",
    }.items():
        _require_identity(
            members[role]["identity"],
            evidence[evidence_key],
            label=f"{arm} {role}",
        )
    _verify_post_model(
        arm=arm,
        raw=members["post_model"]["raw"],
        state=state,
        expected=expected_treatment if arm == "treatment" else None,
    )
    assignment = _parse_json_member(members["assignment"], label=f"{arm} assignment")
    if assignment != _expected_assignment(state):
        raise ValueError(f"{arm} assignment differs from binary response")
    samples = _parse_json_member(members["samples"], label=f"{arm} samples")
    expected_samples = [expected_treatment["sample"]] if arm == "treatment" else []
    if samples != {
        "schema": "noncert-cuts-gate1-v4-arithmetic-corpus-v1",
        "arm": arm,
        "common_prestate_id": common["common_prestate_id"],
        "samples": expected_samples,
    }:
        raise ValueError(f"{arm} sample corpus differs from independent reconstruction")
    ledger_raw = members["ledger"]["raw"]
    if type(ledger_raw) is not bytes:
        raise ValueError(f"{arm} ledger bytes malformed")
    ledger = replay_ledger(ledger_raw)
    expected_core = (
        expected_treatment["ledger_core"]
        if arm == "treatment"
        else [
            {
                "event": "GENESIS",
                "arm": "control",
                "common_prestate_id": common["common_prestate_id"],
            },
            {"event": "SEGMENT_SEAL"},
        ]
    )
    if [_event_core(event) for event in ledger["events"]] != expected_core:
        raise ValueError(f"{arm} ledger events do not one-to-one join the expected cut")
    if evidence.get("ledger") != {
        "event_count": ledger["event_count"],
        "tail_hash": ledger["tail_hash"],
    }:
        raise ValueError(f"{arm} ledger summary drifted")
    injection = evidence.get("injection")
    expected_injection = (
        {
            "enabled": True,
            "provider": "non_proof_forced_positive_control",
            "generated": 1,
            "compiled": 1,
            "applied": 1,
            "compiled_records": [expected_treatment["compiled"]],
        }
        if arm == "treatment"
        else {
            "enabled": False,
            "provider": "empty_control_provider",
            "generated": 0,
            "compiled": 0,
            "applied": 0,
            "compiled_records": [],
        }
    )
    if injection != expected_injection:
        raise ValueError(f"{arm} injection evidence differs from independent reconstruction")
    return {
        "generated": int(injection["generated"]),
        "compiled": int(injection["compiled"]),
        "applied": int(injection["applied"]),
    }


def _require_exact_int(value: object, *, label: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an exact integer")
    return value


def _production_selection(
    bundle: Mapping[str, object],
    *,
    selection_schema: str,
    purpose: str,
    formal_eligible: bool,
    label: str,
) -> Mapping[str, object]:
    """Bind one production-typed evidence profile before arithmetic replay."""

    selection = bundle.get("selection")
    if (
        type(selection) is not dict
        or set(selection)
        != {
            "schema",
            "purpose",
            "campaign_id",
            "run_nonce",
            "manager_epoch_digest",
            "gate1_formal_eligible",
        }
        or selection.get("schema") != selection_schema
        or selection.get("purpose") != purpose
        or selection.get("gate1_formal_eligible") is not formal_eligible
    ):
        raise ValueError(f"{label} selection drifted")
    arms = bundle.get("arms")
    if type(arms) is not dict or set(arms) != {"control", "treatment"}:
        raise ValueError(f"{label} arm pair drifted")
    for arm in ("control", "treatment"):
        member = arms[arm]
        evidence = member.get("evidence") if type(member) is dict else None
        if (
            type(evidence) is not dict
            or evidence.get("schema") != FORMAL_ARM_SCHEMA
            or evidence.get("phase") != "formal_post_injection_clone"
            or "production_attach" not in evidence
        ):
            raise ValueError(f"{arm} uses the manual fixture schema rather than production-typed evidence")
        injection = evidence.get("injection")
        if type(injection) is not dict:
            raise ValueError(f"{arm} production injection evidence is absent")
        if injection.get("provider") == "non_proof_forced_positive_control":
            raise ValueError("manual non-proof provider is forbidden in production evidence")
        records = injection.get("compiled_records")
        if type(records) is not list:
            raise ValueError(f"{arm} production compiled-record list is absent")
        for record in records:
            if (
                type(record) is not dict
                or record.get("schema") != FORMAL_COMPILED_SCHEMA
                or (type(record.get("plan")) is dict and "non_proof_forced_positive_control" in record["plan"])
            ):
                raise ValueError("manual fixture compiled semantics are forbidden in production evidence")
    return selection


def _formal_selection(bundle: Mapping[str, object]) -> Mapping[str, object]:
    """Reject drill authority before inspecting any claimed arithmetic."""

    return _production_selection(
        bundle,
        selection_schema=FORMAL_SELECTION_SCHEMA,
        purpose=FORMAL_PURPOSE,
        formal_eligible=True,
        label="formal campaign",
    )


def _production_drill_selection(
    bundle: Mapping[str, object],
) -> Mapping[str, object]:
    """Reject formal authority at the disposable-drill verifier boundary."""

    return _production_selection(
        bundle,
        selection_schema=PRODUCTION_DRILL_SELECTION_SCHEMA,
        purpose=PRODUCTION_DRILL_PURPOSE,
        formal_eligible=False,
        label="disposable production drill",
    )


def _formal_constraint(
    raw: object,
    *,
    state: Mapping[str, object],
) -> dict[str, object]:
    if type(raw) is not bytes:
        raise ValueError("formal treatment post-model bytes malformed")
    post = _parse_canonical_proto(
        raw,
        cp_model_pb2.CpModelProto(),
        label="formal treatment post-model",
    )
    model = state["model"]
    if len(post.constraints) != len(model.constraints) + 1:
        raise ValueError("formal treatment must append exactly one constraint")
    stripped = cp_model_pb2.CpModelProto()
    stripped.CopyFrom(post)
    del stripped.constraints[-1]
    if stripped.SerializeToString(deterministic=True) != state["model_raw"]:
        raise ValueError("formal treatment changed bytes outside its one constraint")
    constraint = post.constraints[-1]
    if constraint.WhichOneof("constraint") != "linear":
        raise ValueError("formal treatment appended a non-linear constraint")
    indices = [int(value) for value in constraint.linear.vars]
    coefficients = [int(value) for value in constraint.linear.coeffs]
    domain = [int(value) for value in constraint.linear.domain]
    enforcement = [int(value) for value in constraint.enforcement_literal]
    if (
        not indices
        or len(indices) != len(coefficients)
        or any(index < 0 or index >= len(model.variables) for index in indices)
        or len(domain) != 2
        or domain[0] > domain[1]
        or len(enforcement) != 1
        or enforcement[0] < 0
        or enforcement[0] >= len(model.variables)
    ):
        raise ValueError("formal treatment linear constraint is malformed")
    response = state["response"]
    lhs = sum(
        coefficient * int(response.solution[index]) for index, coefficient in zip(indices, coefficients, strict=True)
    )
    rhs = domain[1]
    literal_index = enforcement[0]
    literal = {
        "index": literal_index,
        "name": str(model.variables[literal_index].name),
    }
    if (
        literal_index != state["truth"]["variable_index"]
        or literal["name"] != state["truth"]["variable_name"]
        or int(response.solution[literal_index]) != 1
    ):
        raise ValueError("formal treatment is not enforced by the active ghost truth")
    if lhs <= rhs:
        raise ValueError("formal treatment inequality does not exclude the frozen incumbent")
    return {
        "index": len(post.constraints) - 1,
        "name": str(constraint.name),
        "vars": indices,
        "coeffs": coefficients,
        "domain": domain,
        "enforcement_literals": enforcement,
        "condition_literals": [literal],
        "lhs": lhs,
        "rhs": rhs,
    }


def _verify_formal_attach(
    value: object,
    *,
    arm: str,
    attached: int,
) -> None:
    expected_keys = {
        "schema",
        "status",
        "arm",
        "attach_entrypoint",
        "adapter_entrypoint",
        "compiler_entrypoint",
        "resolver_entrypoint",
        "apply_entrypoint",
        "attached",
        "post_solve_performed",
    }
    if (
        type(value) is not dict
        or set(value) != expected_keys
        or value.get("schema") != FORMAL_ATTACH_SCHEMA
        or value.get("status") != "PASS_PRODUCTION_TYPED_ATTACH"
        or value.get("arm") != arm
        or value.get("attach_entrypoint") != "LBBDController._maybe_attach_framework_cuts"
        or value.get("adapter_entrypoint") != "cut_to_envelope_v1"
        or value.get("compiler_entrypoint") != "validate_and_compile_cut"
        or value.get("resolver_entrypoint") != "_resolve_model_scope_binding"
        or value.get("apply_entrypoint") != "step_8_apply_to_master"
        or value.get("attached") != attached
        or value.get("post_solve_performed") is not False
    ):
        raise ValueError(f"{arm} production typed-attach trace drifted")


def _formal_compiled_record(
    value: object,
    *,
    state: Mapping[str, object],
    constraint: Mapping[str, object],
) -> Mapping[str, object]:
    expected_keys = {
        "schema",
        "cut_id",
        "family",
        "operation",
        "plan",
        "plan_digest",
        "compiled_digest",
        "semantic_fingerprint",
        "condition_literals",
        "post_constraint",
    }
    if type(value) is not dict or set(value) != expected_keys:
        raise ValueError("formal compiled record field set drifted")
    plan = value.get("plan")
    if (
        value.get("schema") != FORMAL_COMPILED_SCHEMA
        or type(value.get("cut_id")) is not str
        or not value["cut_id"]
        or value.get("family") != "region_capacity"
        or value.get("operation") != "region_capacity_le"
        or type(plan) is not dict
        or set(plan)
        != {
            "schema_version",
            "family",
            "operation",
            "parameters",
            "model_scope",
            "semantic_fingerprint",
            "digest",
        }
        or plan.get("schema_version") != 1
        or plan.get("family") != "region_capacity"
        or plan.get("operation") != "region_capacity_le"
        or value.get("plan_digest") != plan.get("digest")
        or value.get("semantic_fingerprint") != plan.get("semantic_fingerprint")
    ):
        raise ValueError("formal compiled region-capacity identity drifted")
    for label in ("plan_digest", "compiled_digest", "semantic_fingerprint"):
        digest = value.get(label)
        if (
            type(digest) is not str
            or len(digest) != 64
            or digest != digest.lower()
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(f"formal {label} is not SHA-256")
    parameters = plan.get("parameters")
    scope = plan.get("model_scope")
    if (
        type(parameters) is not dict
        or set(parameters) != {"capacity", "group_cell_weights"}
        or _require_exact_int(parameters.get("capacity"), label="formal capacity") != constraint["rhs"]
        or type(parameters.get("group_cell_weights")) is not dict
        or not parameters["group_cell_weights"]
        or any(
            type(group) is not str or not group or type(weight) is not int or weight <= 0
            for group, weight in parameters["group_cell_weights"].items()
        )
        or type(scope) is not dict
        or set(scope)
        != {
            "ghost_policy",
            "ghost_rect_digest",
            "domain_fingerprint",
        }
        or scope.get("ghost_policy") != "bound"
        or scope.get("ghost_rect_digest") != state["truth"]["rectangle_digest"]
        or type(scope.get("domain_fingerprint")) is not str
        or len(scope["domain_fingerprint"]) != 64
    ):
        raise ValueError("formal plan parameters or model scope drifted")
    reported_constraint = value.get("post_constraint")
    if (
        value.get("condition_literals") != constraint["condition_literals"]
        or type(reported_constraint) is not dict
        or reported_constraint
        != {
            key: constraint[key]
            for key in (
                "index",
                "name",
                "vars",
                "coeffs",
                "domain",
                "enforcement_literals",
            )
        }
    ):
        raise ValueError("formal compiled record does not join the post-model")
    return value


def _verify_formal_samples(
    value: object,
    *,
    state: Mapping[str, object],
    compiled: Mapping[str, object],
    constraint: Mapping[str, object],
) -> None:
    expected_keys = {
        "schema",
        "cut_id",
        "family",
        "operation",
        "plan_digest",
        "compiled_digest",
        "parameters",
        "enforcement_literals",
        "contributions",
        "lhs",
        "rhs",
        "active",
        "violated",
    }
    if type(value) is not dict or set(value) != expected_keys:
        raise ValueError("formal arithmetic sample field set drifted")
    literals = [
        {
            **constraint["condition_literals"][0],
            "value": int(state["response"].solution[constraint["condition_literals"][0]["index"]]),
        }
    ]
    contributions = value.get("contributions")
    if (
        value.get("schema") != SAMPLE_SCHEMA
        or value.get("cut_id") != compiled["cut_id"]
        or value.get("family") != "region_capacity"
        or value.get("operation") != "region_capacity_le"
        or value.get("plan_digest") != compiled["plan_digest"]
        or value.get("compiled_digest") != compiled["compiled_digest"]
        or value.get("parameters") != compiled["plan"]["parameters"]
        or value.get("enforcement_literals") != literals
        or type(contributions) is not list
        or not contributions
        or any(
            type(item) is not dict
            or set(item) != {"label", "selected_count", "weight", "value"}
            or type(item["label"]) is not str
            or not item["label"]
            or type(item["selected_count"]) is not int
            or item["selected_count"] < 0
            or type(item["weight"]) is not int
            or item["weight"] <= 0
            or type(item["value"]) is not int
            or item["value"] != item["selected_count"] * item["weight"]
            for item in contributions
        )
        or sum(item["value"] for item in contributions) != constraint["lhs"]
        or value.get("lhs") != constraint["lhs"]
        or value.get("rhs") != constraint["rhs"]
        or value.get("active") is not True
        or value.get("violated") is not True
    ):
        raise ValueError("formal arithmetic sample differs from binary arithmetic")


def _verify_formal_ledger(
    raw: object,
    *,
    arm: str,
    compiled: Mapping[str, object] | None,
    state: Mapping[str, object],
    constraint: Mapping[str, object] | None,
) -> Mapping[str, object]:
    if type(raw) is not bytes:
        raise ValueError(f"{arm} formal ledger bytes malformed")
    ledger = replay_ledger(raw)
    events = ledger["events"]
    names = [event["event"] for event in events]
    expected_names = (
        ["GENESIS", "SEGMENT_SEAL"] if arm == "control" else ["GENESIS", "GENERATED", "APPLIED", "SEGMENT_SEAL"]
    )
    if names != expected_names:
        raise ValueError(f"{arm} formal production ledger sequence drifted")
    expected_scope = f"gate1-v4-{arm}"
    expected_writer = f"{expected_scope}-writer"
    if (
        ledger.get("scope_id") != expected_scope
        or ledger.get("writer_id") != expected_writer
        or any(
            type(event.get("wallclock_utc")) not in (int, float)
            or isinstance(event.get("wallclock_utc"), bool)
            or float(event["wallclock_utc"]) <= 0
            for event in events
        )
    ):
        raise ValueError(f"{arm} formal production ledger envelope drifted")
    common_prestate_id = state["common"]["common_prestate_id"]
    if _event_core(events[0]) != {
        "event": "GENESIS",
        "arm": arm,
        "common_prestate_id": common_prestate_id,
        "predecessor_segment": None,
        "predecessor_tail_hash": None,
        "recovery_reason": "fresh_start",
    } or _event_core(events[-1]) != {"event": "SEGMENT_SEAL"}:
        raise ValueError(f"{arm} formal production ledger boundary drifted")
    if arm == "control":
        return ledger
    assert compiled is not None and constraint is not None
    generated = _event_core(events[1])
    applied = _event_core(events[2])
    expected_generated_keys = {
        "event",
        "cut_id",
        "family",
        "trigger",
        "iteration",
        "epoch_instance_id",
        "epoch_semantic_digest",
    }
    epoch_instance_id = generated.get("epoch_instance_id")
    epoch_semantic_digest = generated.get("epoch_semantic_digest")
    if (
        set(generated) != expected_generated_keys
        or generated.get("event") != "GENERATED"
        or generated.get("cut_id") != compiled["cut_id"]
        or generated.get("family") != "region_capacity"
        or generated.get("trigger") != FORMAL_ATTACH_TRIGGER
        or generated.get("iteration") != FORMAL_ATTACH_ITERATION
        or type(epoch_instance_id) is not str
        or _EPOCH_INSTANCE_RE.fullmatch(epoch_instance_id) is None
        or type(epoch_semantic_digest) is not str
        or len(epoch_semantic_digest) != 64
        or epoch_semantic_digest != epoch_semantic_digest.lower()
        or any(character not in "0123456789abcdef" for character in epoch_semantic_digest)
    ):
        raise ValueError("formal GENERATED event does not join the compiled cut")
    receipt = applied.get("receipt")
    expected_applied_keys = {
        "event",
        "cut_id",
        "family",
        "trigger",
        "iteration",
        "epoch_instance_id",
        "epoch_semantic_digest",
        "semantic_fingerprint",
        "plan_digest",
        "receipt",
    }
    if (
        set(applied) != expected_applied_keys
        or applied.get("event") != "APPLIED"
        or applied.get("cut_id") != compiled["cut_id"]
        or applied.get("family") != "region_capacity"
        or applied.get("trigger") != FORMAL_ATTACH_TRIGGER
        or applied.get("iteration") != FORMAL_ATTACH_ITERATION
        or applied.get("epoch_instance_id") != epoch_instance_id
        or applied.get("epoch_semantic_digest") != epoch_semantic_digest
        or applied.get("semantic_fingerprint") != compiled["semantic_fingerprint"]
        or applied.get("plan_digest") != compiled["plan_digest"]
        or type(receipt) is not dict
        or set(receipt)
        != {
            "rect_idx",
            "ghost_rect_digest",
            "snapshot_digest",
            "master_domain_family",
            "condition_lits",
            "count_delta",
            "apply_completed",
        }
        or type(receipt.get("rect_idx")) is not int
        or receipt["rect_idx"] < 0
        or receipt.get("ghost_rect_digest") != state["truth"]["rectangle_digest"]
        or type(receipt.get("snapshot_digest")) is not str
        or len(receipt["snapshot_digest"]) != 64
        or receipt.get("master_domain_family") != "region_capacity"
        or receipt.get("condition_lits") != constraint["condition_literals"]
        or receipt.get("count_delta") != 1
        or receipt.get("apply_completed") is not True
    ):
        raise ValueError("formal APPLIED event does not join the active inequality")
    return ledger


def _verify_formal_arm(
    arm: str,
    member: object,
    bundle: Mapping[str, object],
    state: Mapping[str, object],
) -> tuple[dict[str, int], dict[str, object] | None]:
    if type(member) is not dict or type(member.get("members")) is not dict:
        raise ValueError(f"{arm} formal arm bundle malformed")
    evidence = member.get("evidence")
    expected_evidence_keys = {
        "schema",
        "arm",
        "phase",
        "campaign_id",
        "run_nonce",
        "manager_epoch_digest",
        "selection_identity",
        "common_prestate_id",
        "common_manifest_identity",
        "binding_identity",
        "binding_set_identity",
        "pre_model_identity",
        "pre_response_identity",
        "post_model_identity",
        "assignment_identity",
        "sample_corpus_identity",
        "ledger_identity",
        "post_solve_performed",
        "post_response_present",
        "injection",
        "production_attach",
        "ledger",
        "claim_boundary",
    }
    common = state["common"]
    if (
        type(evidence) is not dict
        or set(evidence) != expected_evidence_keys
        or evidence.get("schema") != FORMAL_ARM_SCHEMA
        or evidence.get("arm") != arm
        or evidence.get("phase") != "formal_post_injection_clone"
        or evidence.get("campaign_id") != common["campaign_id"]
        or evidence.get("run_nonce") != common["run_nonce"]
        or evidence.get("manager_epoch_digest") != common["manager_epoch_digest"]
        or evidence.get("common_prestate_id") != common["common_prestate_id"]
        or evidence.get("post_solve_performed") is not False
        or evidence.get("post_response_present") is not False
    ):
        raise ValueError(f"{arm} formal evidence schema/provenance drifted")
    for actual, reported, label in (
        (state["selection_identity"], evidence["selection_identity"], "selection"),
        (state["common_identity"], evidence["common_manifest_identity"], "common manifest"),
        (bundle["bindings"][arm]["identity"], evidence["binding_identity"], "binding"),
        (bundle["binding_seal_identity"], evidence["binding_set_identity"], "binding set"),
        (state["artifacts"]["pre_model"]["identity"], evidence["pre_model_identity"], "pre-model"),
        (state["artifacts"]["response"]["identity"], evidence["pre_response_identity"], "pre-response"),
    ):
        _require_identity(actual, reported, label=f"{arm} {label}")
    members = member["members"]
    if set(members) != {"post_model", "assignment", "samples", "ledger"}:
        raise ValueError(f"{arm} formal member set drifted")
    for role, evidence_key in {
        "post_model": "post_model_identity",
        "assignment": "assignment_identity",
        "samples": "sample_corpus_identity",
        "ledger": "ledger_identity",
    }.items():
        _require_identity(
            members[role]["identity"],
            evidence[evidence_key],
            label=f"{arm} formal {role}",
        )
    assignment = _parse_json_member(
        members["assignment"],
        label=f"{arm} formal assignment",
    )
    if assignment != _expected_assignment(state):
        raise ValueError(f"{arm} formal assignment differs from binary response")
    samples = _parse_json_member(members["samples"], label=f"{arm} formal samples")
    if (
        type(samples) is not dict
        or set(samples) != {"schema", "arm", "common_prestate_id", "samples"}
        or samples.get("schema") != "noncert-cuts-gate1-v4-arithmetic-corpus-v1"
        or samples.get("arm") != arm
        or samples.get("common_prestate_id") != common["common_prestate_id"]
        or type(samples.get("samples")) is not list
    ):
        raise ValueError(f"{arm} formal sample corpus drifted")
    injection = evidence.get("injection")
    if type(injection) is not dict or set(injection) != {
        "enabled",
        "provider",
        "generated",
        "compiled",
        "applied",
        "compiled_records",
    }:
        raise ValueError(f"{arm} formal injection schema drifted")
    if arm == "control":
        if (
            members["post_model"]["raw"] != state["model_raw"]
            or samples["samples"] != []
            or injection
            != {
                "enabled": False,
                "provider": "empty_control_provider",
                "generated": 0,
                "compiled": 0,
                "applied": 0,
                "compiled_records": [],
            }
        ):
            raise ValueError("formal control did not remain an exact empty injection")
        _verify_formal_attach(evidence["production_attach"], arm=arm, attached=0)
        ledger = _verify_formal_ledger(
            members["ledger"]["raw"],
            arm=arm,
            compiled=None,
            state=state,
            constraint=None,
        )
        selected = None
    else:
        constraint = _formal_constraint(members["post_model"]["raw"], state=state)
        if (
            injection.get("enabled") is not True
            or injection.get("provider") != "forced_production_region_capacity_provider"
            or injection.get("generated") != 1
            or injection.get("compiled") != 1
            or injection.get("applied") != 1
            or type(injection.get("compiled_records")) is not list
            or len(injection["compiled_records"]) != 1
            or len(samples["samples"]) != 1
        ):
            raise ValueError("formal treatment injection counts/provider drifted")
        compiled = _formal_compiled_record(
            injection["compiled_records"][0],
            state=state,
            constraint=constraint,
        )
        _verify_formal_samples(
            samples["samples"][0],
            state=state,
            compiled=compiled,
            constraint=constraint,
        )
        _verify_formal_attach(evidence["production_attach"], arm=arm, attached=1)
        ledger = _verify_formal_ledger(
            members["ledger"]["raw"],
            arm=arm,
            compiled=compiled,
            state=state,
            constraint=constraint,
        )
        generated_event = _event_core(ledger["events"][1])
        selected = {
            "cut_id": compiled["cut_id"],
            "family": "region_capacity",
            "lhs": constraint["lhs"],
            "rhs": constraint["rhs"],
            "active": True,
            "violated": True,
            "condition_literals": constraint["condition_literals"],
            "trigger": generated_event["trigger"],
            "iteration": generated_event["iteration"],
            "epoch_instance_id": generated_event["epoch_instance_id"],
            "epoch_semantic_digest": generated_event["epoch_semantic_digest"],
        }
    if evidence.get("ledger") != {
        "event_count": ledger["event_count"],
        "tail_hash": ledger["tail_hash"],
    }:
        raise ValueError(f"{arm} formal ledger summary drifted")
    return (
        {
            "generated": int(injection["generated"]),
            "compiled": int(injection["compiled"]),
            "applied": int(injection["applied"]),
        },
        selected,
    )


def verify_formal_bundle(bundle: Mapping[str, object]) -> dict[str, object]:
    """Verify only a campaign-bound production-typed forced-positive pair.

    This API is intentionally disjoint from :func:`verify_bundle`.  In
    particular, the tiny offline fixture, its manual ``n <= n-1`` provider,
    and its receipt schema are never accepted as formal evidence.
    """

    _formal_selection(bundle)
    state = _verify_binary_prestate(
        _verify_selection_and_common(
            bundle,
            selection_schema=FORMAL_SELECTION_SCHEMA,
            purpose=FORMAL_PURPOSE,
            formal_eligible=True,
        )
    )
    _verify_bindings(bundle, state)
    control, control_selected = _verify_formal_arm(
        "control",
        bundle["arms"]["control"],
        bundle,
        state,
    )
    treatment, selected = _verify_formal_arm(
        "treatment",
        bundle["arms"]["treatment"],
        bundle,
        state,
    )
    if control_selected is not None or selected is None:
        raise ValueError("formal pair selected-inequality cardinality drifted")
    return {
        "schema": FORMAL_RECEIPT_SCHEMA,
        "checker": "independent_arithmetic_v4.verify_formal_bundle",
        "status": "PASS_FORMAL_MECHANISM_POSITIVE_CONTROL",
        "repository_head": EXPECTED_HEAD,
        "selection_identity": state["selection_identity"],
        "common_prestate_id": state["common"]["common_prestate_id"],
        "common_prestate": {
            "pre_model_sha256": hashlib.sha256(state["model_raw"]).hexdigest(),
            "response_sha256": hashlib.sha256(state["response_raw"]).hexdigest(),
            "solution_sha256": digest_json(state["solution"]),
            "incumbent_sha256": digest_json(state["incumbent"]),
            "post_solve_performed": False,
        },
        "control": control,
        "treatment": treatment,
        "selected": selected,
        "checks": [
            "formal_campaign_selection_and_eligibility",
            "common_pre_model_response_solution_incumbent_sealed",
            "both_arm_bindings_precede_post_clone_dependency",
            "production_typed_attach_chain",
            "no_post_attach_solve_or_response",
            "control_applied_zero",
            "treatment_generated_compiled_applied_one_to_one",
            "binary_assignment_model_constraint_ledger_join",
        ],
        "claim_boundary": {
            "established": [
                "forced production typed attach reached one APPLIED inequality",
                "that concrete inequality excludes the common frozen incumbent",
            ],
            "not_established": [
                "organic cut activation",
                "cut-family global soundness",
                "runtime usefulness",
                "SAT or UNSAT",
                "witness feasibility",
                "production CERTIFIED",
            ],
        },
    }


def verify_production_drill_bundle(
    bundle: Mapping[str, object],
) -> dict[str, object]:
    """Verify a disposable production-typed pair under non-formal authority.

    The arithmetic, binary-protobuf, attach-chain, assignment and ledger
    checks are identical to the formal verifier.  Only the selection purpose,
    eligibility bit and detached receipt are drill-specific.  Consequently a
    passing receipt is useful for disposable E2E validation but cannot be
    presented to :func:`verify_formal_bundle`.
    """

    _production_drill_selection(bundle)
    state = _verify_binary_prestate(
        _verify_selection_and_common(
            bundle,
            selection_schema=PRODUCTION_DRILL_SELECTION_SCHEMA,
            purpose=PRODUCTION_DRILL_PURPOSE,
            formal_eligible=False,
        )
    )
    _verify_bindings(bundle, state)
    control, control_selected = _verify_formal_arm(
        "control",
        bundle["arms"]["control"],
        bundle,
        state,
    )
    treatment, selected = _verify_formal_arm(
        "treatment",
        bundle["arms"]["treatment"],
        bundle,
        state,
    )
    if control_selected is not None or selected is None:
        raise ValueError("production drill selected-inequality cardinality drifted")
    return {
        "schema": PRODUCTION_DRILL_RECEIPT_SCHEMA,
        "checker": "independent_arithmetic_v4.verify_production_drill_bundle",
        "status": "PASS_DISPOSABLE_PRODUCTION_MECHANISM_POSITIVE_CONTROL",
        "profile": "disposable_drill",
        "formal_eligible": False,
        "repository_head": EXPECTED_HEAD,
        "selection_identity": state["selection_identity"],
        "common_prestate_id": state["common"]["common_prestate_id"],
        "common_prestate": {
            "pre_model_sha256": hashlib.sha256(state["model_raw"]).hexdigest(),
            "response_sha256": hashlib.sha256(state["response_raw"]).hexdigest(),
            "solution_sha256": digest_json(state["solution"]),
            "incumbent_sha256": digest_json(state["incumbent"]),
            "post_solve_performed": False,
        },
        "control": control,
        "treatment": treatment,
        "selected": selected,
        "checks": [
            "disposable_production_drill_selection_and_ineligibility",
            "common_pre_model_response_solution_incumbent_sealed",
            "both_arm_bindings_precede_post_clone_dependency",
            "production_typed_attach_chain",
            "no_post_attach_solve_or_response",
            "control_applied_zero",
            "treatment_generated_compiled_applied_one_to_one",
            "binary_assignment_model_constraint_ledger_join",
        ],
        "claim_boundary": {
            "established": [
                "the disposable drill reached one forced production typed APPLIED inequality",
                "that concrete inequality excludes the drill's common frozen incumbent",
            ],
            "not_established": [
                "formal Gate 1 admission",
                "organic cut activation",
                "cut-family global soundness",
                "runtime usefulness",
                "SAT or UNSAT",
                "witness feasibility",
                "production CERTIFIED",
            ],
        },
    }


def verify_bundle(bundle: Mapping[str, object]) -> dict[str, object]:
    """Verify one already-snapshotted pair without consulting runner code."""

    state = _verify_binary_prestate(_verify_selection_and_common(bundle))
    _verify_bindings(bundle, state)
    arms = bundle.get("arms")
    if type(arms) is not dict or set(arms) != {"control", "treatment"}:
        raise ValueError("arm pair drifted")
    expected = _expected_treatment(state)
    control_counts = _verify_arm("control", arms["control"], bundle, state, expected)
    treatment_counts = _verify_arm(
        "treatment",
        arms["treatment"],
        bundle,
        state,
        expected,
    )
    lhs = int(expected["sample"]["lhs"])
    rhs = int(expected["sample"]["rhs"])
    if lhs <= rhs:
        raise ValueError("forced inequality does not exclude the frozen incumbent")
    return {
        "schema": DRILL_RECEIPT_SCHEMA,
        "checker": "independent_arithmetic_v4",
        "status": "PASS_MECHANISM_POSITIVE_CONTROL",
        "repository_head": EXPECTED_HEAD,
        "selection_identity": state["selection_identity"],
        "common_prestate_id": state["common"]["common_prestate_id"],
        "common_prestate": {
            "pre_model_sha256": hashlib.sha256(state["model_raw"]).hexdigest(),
            "response_sha256": hashlib.sha256(state["response_raw"]).hexdigest(),
            "solution_sha256": digest_json(state["solution"]),
            "incumbent_sha256": digest_json(state["incumbent"]),
            "post_solve_performed": False,
        },
        "control": control_counts,
        "treatment": treatment_counts,
        "selected": {
            "cut_id": expected["compiled"]["cut_id"],
            "family": "region_capacity",
            "group_id": state["group_id"],
            "lhs": lhs,
            "rhs": rhs,
            "active": True,
            "violated": True,
        },
        "checks": [
            "common_pre_model_response_solution_incumbent_sealed",
            "both_arm_bindings_precede_post_clone_dependency",
            "no_post_attach_solve_or_response",
            "control_applied_zero",
            "treatment_generated_compiled_applied_one_to_one",
            "binary_assignment_model_constraint_ledger_join",
        ],
        "claim_boundary": {
            "established": [
                "forced injection mechanism reached one APPLIED inequality",
                "that concrete inequality excludes the common frozen incumbent",
            ],
            "not_established": [
                "organic cut activation",
                "cut-family global soundness",
                "runtime usefulness",
                "SAT or UNSAT",
                "witness feasibility",
                "production CERTIFIED",
            ],
        },
    }


def verify_fixture(root: Path) -> dict[str, object]:
    return verify_bundle(load_fixture(root))


def _write_exclusive(path: Path, value: object) -> None:
    absolute = _absolute(path)
    _reject_symlink_components(absolute)
    if absolute.exists() or absolute.is_symlink():
        raise FileExistsError(f"refusing to overwrite output: {absolute}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("O_NOFOLLOW is required")
    fd = os.open(absolute, flags | os.O_NOFOLLOW, 0o600)
    try:
        raw = canonical_json(value) + b"\n"
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short receipt write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify_fixture(args.fixture_root)
    except (OSError, ValueError, RuntimeError) as exc:
        result = {
            "schema": DRILL_RECEIPT_SCHEMA,
            "checker": "independent_arithmetic_v4",
            "status": "FAIL_CLOSED",
            "error": f"{type(exc).__name__}: {exc}",
        }
    _write_exclusive(args.output, result)
    return 0 if result["status"] == "PASS_MECHANISM_POSITIVE_CONTROL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
