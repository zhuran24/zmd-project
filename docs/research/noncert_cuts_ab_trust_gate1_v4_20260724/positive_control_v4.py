#!/usr/bin/env python3
"""Offline Gate-1 v4 common-prestate and forced-positive-control fixture.

This module exercises the byte and evidence contracts used by the future real
Gate-1 campaign without starting a production solver or a systemd unit.  The
ordering is load-bearing:

1. a pre-injection model, response, full solution and incumbent are sealed;
2. both arm bindings are sealed against those exact bytes;
3. independent post-model clones are created;
4. control performs an empty injection and treatment attaches one explicitly
   non-proof forced ``region_capacity_le`` inequality;
5. neither post-model is solved.

The forced inequality is a mechanism-positive-control fixture.  It is not a
family-global soundness argument, a proof sidecar, or production evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from google.protobuf.message import DecodeError, Message
from ortools.sat import cp_model_pb2


SELECTION_SCHEMA = "noncert-cuts-gate1-v4-fixture-selection-v2"
COMMON_SCHEMA = "noncert-cuts-gate1-v4-common-prestate-v1"
BINDING_SCHEMA = "noncert-cuts-gate1-v4-arm-prestate-binding-v1"
BINDING_SET_SCHEMA = "noncert-cuts-gate1-v4-binding-set-v1"
ARM_SCHEMA = "noncert-cuts-gate1-v4-positive-control-arm-v1"
ASSIGNMENT_SCHEMA = "noncert-cuts-gate1-v4-frozen-assignment-v1"
SAMPLE_SCHEMA = "noncert-cuts-gate1-v4-arithmetic-sample-v1"
TYPED_DRILL_PRESTATE_SCHEMA = "noncert-cuts-gate1-v4-production-typed-drill-prestate-v1"
TYPED_DRILL_BINDING_SCHEMA = "noncert-cuts-gate1-v4-production-typed-drill-binding-v1"
TYPED_DRILL_RESULT_SCHEMA = "noncert-cuts-gate1-v4-production-typed-drill-result-v1"
LEDGER_SCHEMA = "cut-ledger-v1"
EXPECTED_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
_GHOST_PREFIX = "ghost__"
_GHOST_DIGEST_PREFIX = b"zmd.ghost-rect.v1:"
_GENESIS_HASH = "0" * 64
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


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _reject_symlink_components(path: Path, *, include_leaf: bool = False) -> None:
    absolute = _absolute(path)
    stop = None if include_leaf else -1
    current = Path(absolute.anchor)
    for part in absolute.parts[1:stop]:
        current /= part
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError as exc:
            raise ValueError(f"missing path component: {current}") from exc
        if stat.S_ISLNK(mode):
            raise ValueError(f"symlink path component rejected: {current}")
        if not stat.S_ISDIR(mode):
            raise ValueError(f"non-directory path component rejected: {current}")


def _mkdir_exclusive(path: Path) -> Path:
    absolute = _absolute(path)
    _reject_symlink_components(absolute)
    try:
        os.mkdir(absolute, 0o700)
    except FileExistsError as exc:
        raise FileExistsError(f"refusing to reuse output directory: {absolute}") from exc
    return absolute


def _identity(path: Path, raw: bytes) -> dict[str, object]:
    return {
        "path": str(_absolute(path)),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _write_exclusive(path: Path, raw: bytes) -> dict[str, object]:
    absolute = _absolute(path)
    _reject_symlink_components(absolute)
    if absolute.exists() or absolute.is_symlink():
        raise FileExistsError(f"refusing to overwrite output: {absolute}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("O_NOFOLLOW is required")
    flags |= os.O_NOFOLLOW
    fd = os.open(absolute, flags, 0o600)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short exclusive write")
            view = view[written:]
        os.fsync(fd)
        descriptor = os.fstat(fd)
        named = os.lstat(absolute)
        if (
            not stat.S_ISREG(descriptor.st_mode)
            or stat.S_ISLNK(named.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or descriptor.st_dev != named.st_dev
            or descriptor.st_ino != named.st_ino
            or descriptor.st_size != len(raw)
        ):
            raise RuntimeError(f"exclusive output pathname drifted: {absolute}")
    finally:
        os.close(fd)
    return _identity(absolute, raw)


def _write_json_exclusive(path: Path, value: object) -> dict[str, object]:
    return _write_exclusive(path, canonical_json(value) + b"\n")


def _read_regular(path: Path) -> tuple[bytes, dict[str, object]]:
    absolute = _absolute(path)
    _reject_symlink_components(absolute)
    flags = os.O_RDONLY | os.O_CLOEXEC
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("O_NOFOLLOW is required")
    flags |= os.O_NOFOLLOW
    fd = os.open(absolute, flags)
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
        if any(getattr(before, field) != getattr(after, field) for field in stable):
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
    return raw, _identity(absolute, raw)


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


def _read_json(path: Path, *, label: str) -> tuple[object, dict[str, object]]:
    raw, identity = _read_regular(path)
    if not raw.endswith(b"\n"):
        raise ValueError(f"{label}: canonical JSON must end in one newline")
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
    ):
        raise ValueError(f"{label}: invalid detached file identity")
    try:
        int(value["sha256"], 16)
    except ValueError as exc:
        raise ValueError(f"{label}: invalid SHA-256") from exc
    if value["sha256"] != value["sha256"].lower():
        raise ValueError(f"{label}: SHA-256 must be lowercase")
    return dict(value)


def _assert_identity(actual: Mapping[str, object], expected: object, *, label: str) -> None:
    if actual != _strict_identity(expected, label=label):
        raise ValueError(f"{label}: detached byte identity drift")


def _rectangle_digest(x: int, y: int, width: int, height: int) -> str:
    return hashlib.sha256(_GHOST_DIGEST_PREFIX + canonical_json([x, y, width, height])).hexdigest()


def _ghost_truth(
    model: cp_model_pb2.CpModelProto,
    response: cp_model_pb2.CpSolverResponse,
    contract: object,
) -> dict[str, object]:
    if (
        type(contract) is not dict
        or set(contract) != {"schema_version", "grid", "ghost"}
        or contract["schema_version"] != 1
        or type(contract["grid"]) is not dict
        or type(contract["ghost"]) is not dict
        or set(contract["grid"]) != {"width", "height"}
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
    by_name: dict[str, list[int]] = defaultdict(list)
    for index, variable in enumerate(model.variables):
        by_name[str(variable.name)].append(index)
    indices: list[int] = []
    for _x, _y, name in anchors:
        if len(by_name.get(name, [])) != 1:
            raise ValueError(f"ghost selector must occur exactly once: {name}")
        index = by_name[name][0]
        if list(model.variables[index].domain) != [0, 1]:
            raise ValueError(f"ghost selector has non-Boolean domain: {name}")
        indices.append(index)
    matching = [
        constraint
        for constraint in model.constraints
        if constraint.WhichOneof("constraint") == "exactly_one"
        and set(constraint.exactly_one.literals).intersection(indices)
    ]
    if (
        len(matching) != 1
        or len(matching[0].exactly_one.literals) != len(indices)
        or set(matching[0].exactly_one.literals) != set(indices)
    ):
        raise ValueError("model lacks one exact complete ghost-selector constraint")
    if response.status not in {cp_model_pb2.FEASIBLE, cp_model_pb2.OPTIMAL}:
        raise ValueError("response is not FEASIBLE or OPTIMAL")
    if len(response.solution) != len(model.variables):
        raise ValueError("response lacks a full solution vector")
    active = [ordinal for ordinal, index in enumerate(indices) if response.solution[index] == 1]
    if len(active) != 1:
        raise ValueError("response must activate exactly one ghost selector")
    ordinal = active[0]
    x, y, name = anchors[ordinal]
    return {
        "ordinal": ordinal,
        "variable_index": indices[ordinal],
        "variable_name": name,
        "anchor": {"x": x, "y": y},
        "rectangle_digest": _rectangle_digest(x, y, ghost_w, ghost_h),
    }


def _mandatory_groups(mandatory: object) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
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


def _selected_group(
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
    selected: dict[str, str] = {}
    for instance_id, strict in instances.items():
        entry = incumbent.get(instance_id)
        if type(entry) is not dict:
            raise ValueError(f"incumbent omits {instance_id}")
        if any(entry.get(field) != strict[field] for field in ("instance_id", "facility_type", "operation_type")):
            raise ValueError(f"incumbent identity drift for {instance_id}")
        pool = candidates["facility_pools"].get(strict["facility_type"])
        if type(pool) is not list:
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
        selected[instance_id] = str(entry["pose_id"])
    eligible = [
        (group_id, members)
        for group_id, members in sorted(groups.items())
        if members and len({selected[member] for member in members}) == len(members)
    ]
    if not eligible:
        raise ValueError("no lexicographic mandatory group is eligible")
    return eligible[0]


def _selection_variable_map(model: cp_model_pb2.CpModelProto) -> dict[str, int]:
    result: dict[str, int] = {}
    prefix = "select__"
    for index, variable in enumerate(model.variables):
        name = str(variable.name)
        if not name.startswith(prefix):
            continue
        instance_id = name[len(prefix) :]
        if not instance_id or instance_id in result or list(variable.domain) != [0, 1]:
            raise ValueError("selection-variable identity/domain drift")
        result[instance_id] = index
    return result


def _ledger(events: Sequence[Mapping[str, object]], *, scope_id: str) -> tuple[bytes, dict[str, object]]:
    if not events or events[0].get("event") != "GENESIS" or events[-1].get("event") != "SEGMENT_SEAL":
        raise ValueError("ledger events must run from GENESIS through SEGMENT_SEAL")
    previous = _GENESIS_HASH
    lines: list[bytes] = []
    for sequence, fields in enumerate(events):
        event_type = fields.get("event")
        if event_type not in _LEDGER_EVENTS:
            raise ValueError(f"unsupported fixture ledger event: {event_type}")
        event = {
            **fields,
            "schema_version": LEDGER_SCHEMA,
            "seq": sequence,
            "prev_event_hash": previous,
            "writer_id": f"gate1-v4-{scope_id}",
            "scope_id": scope_id,
            "wallclock_utc": sequence,
        }
        line = canonical_json(event)
        lines.append(line)
        previous = hashlib.sha256(line).hexdigest()
    raw = b"\n".join(lines) + b"\n"
    return raw, {
        "event_count": len(lines),
        "tail_hash": previous,
    }


def _verify_common_artifacts(common: Mapping[str, object], common_dir: Path) -> dict[str, bytes]:
    if common.get("schema") != COMMON_SCHEMA:
        raise ValueError("common-prestate schema drift")
    artifacts = common.get("artifacts")
    if type(artifacts) is not dict or set(artifacts) != {
        "pre_model",
        "response",
        "solution",
        "incumbent",
        "selector_contract",
        "mandatory",
        "candidates",
    }:
        raise ValueError("common-prestate artifact map drift")
    names = {
        "pre_model": "pre-injection-model.pb",
        "response": "pre-injection-response.pb",
        "solution": "solution.json",
        "incumbent": "incumbent.json",
        "selector_contract": "selector-contract.json",
        "mandatory": "mandatory.json",
        "candidates": "candidates.json",
    }
    result: dict[str, bytes] = {}
    for role, filename in names.items():
        raw, actual = _read_regular(common_dir / filename)
        _assert_identity(actual, artifacts[role], label=f"common artifacts.{role}")
        result[role] = raw
    return result


def seal_common_prestate(
    root: Path,
    *,
    model_raw: bytes,
    response_raw: bytes,
    incumbent: object,
    selector_contract: object,
    mandatory: object,
    candidates: object,
    selection_identity: Mapping[str, object],
    campaign_id: str,
    run_nonce: str,
    manager_epoch_digest: str,
    repository_head: str,
) -> dict[str, object]:
    """Seal all pre-injection truth before either arm can create a clone."""

    root = _absolute(root)
    common_dir = _mkdir_exclusive(root / "common-prestate")
    if any((root / "arms" / arm / "post-injection-model.pb").exists() for arm in ("control", "treatment")):
        raise ValueError("post-model exists before common prestate seal")
    model = _parse_canonical_proto(model_raw, cp_model_pb2.CpModelProto(), label="pre-model")
    response = _parse_canonical_proto(
        response_raw,
        cp_model_pb2.CpSolverResponse(),
        label="pre-response",
    )
    if response.status not in {cp_model_pb2.FEASIBLE, cp_model_pb2.OPTIMAL}:
        raise ValueError("pre-response is not FEASIBLE or OPTIMAL")
    if len(response.solution) != len(model.variables):
        raise ValueError("pre-response lacks the complete solution")
    ghost = _ghost_truth(model, response, selector_contract)
    if type(incumbent) is not dict:
        raise ValueError("incumbent must be an object")
    expected_ghost = {
        "pose_id": f"ghost_anchor::{ghost['anchor']['x']},{ghost['anchor']['y']}",
        "pose_idx": ghost["ordinal"],
        "anchor": ghost["anchor"],
    }
    if incumbent.get("ghost_pick") != expected_ghost:
        raise ValueError("incumbent ghost differs from pre-response truth")
    _selected_group(mandatory, candidates, incumbent)
    selection = _strict_identity(dict(selection_identity), label="selection_identity")
    for label, value in {
        "campaign_id": campaign_id,
        "run_nonce": run_nonce,
        "manager_epoch_digest": manager_epoch_digest,
    }.items():
        if type(value) is not str or not value:
            raise ValueError(f"{label} must be a non-empty string")
    if (
        type(repository_head) is not str
        or len(repository_head) != 40
        or any(character not in "0123456789abcdef" for character in repository_head)
    ):
        raise ValueError("repository_head must be a lowercase 40-hex Git identity")
    artifact_identities = {
        "pre_model": _write_exclusive(common_dir / "pre-injection-model.pb", model_raw),
        "response": _write_exclusive(common_dir / "pre-injection-response.pb", response_raw),
        "solution": _write_json_exclusive(common_dir / "solution.json", list(response.solution)),
        "incumbent": _write_json_exclusive(common_dir / "incumbent.json", incumbent),
        "selector_contract": _write_json_exclusive(
            common_dir / "selector-contract.json",
            selector_contract,
        ),
        "mandatory": _write_json_exclusive(common_dir / "mandatory.json", mandatory),
        "candidates": _write_json_exclusive(common_dir / "candidates.json", candidates),
    }
    common_id = digest_json(
        {
            "campaign_id": campaign_id,
            "run_nonce": run_nonce,
            "manager_epoch_digest": manager_epoch_digest,
            "selection_identity": selection,
            "artifacts": artifact_identities,
            "phase": "pre_injection",
        }
    )
    manifest = {
        "schema": COMMON_SCHEMA,
        "phase": "pre_injection",
        "campaign_id": campaign_id,
        "run_nonce": run_nonce,
        "manager_epoch_digest": manager_epoch_digest,
        "repository_head": repository_head,
        "selection_identity": selection,
        "common_prestate_id": common_id,
        "artifacts": artifact_identities,
        "model_variable_count": len(model.variables),
        "model_constraint_count": len(model.constraints),
        "response_status": int(response.status),
        "ghost_truth": ghost,
        "post_model_paths_absent_at_seal": [
            str(root / "arms" / "control" / "post-injection-model.pb"),
            str(root / "arms" / "treatment" / "post-injection-model.pb"),
        ],
        "post_solve_performed": False,
    }
    manifest_identity = _write_json_exclusive(common_dir / "manifest.json", manifest)
    return {**manifest, "manifest_identity": manifest_identity}


def create_arm_bindings(root: Path) -> dict[str, object]:
    """Create both common-prestate bindings and seal them before any clone."""

    root = _absolute(root)
    common_value, common_manifest_identity = _read_json(
        root / "common-prestate" / "manifest.json",
        label="common-prestate manifest",
    )
    if type(common_value) is not dict:
        raise ValueError("common-prestate manifest must be an object")
    _verify_common_artifacts(common_value, root / "common-prestate")
    bindings_dir = _mkdir_exclusive(root / "bindings")
    binding_identities: dict[str, dict[str, object]] = {}
    for arm in ("control", "treatment"):
        post_path = root / "arms" / arm / "post-injection-model.pb"
        if post_path.exists() or post_path.is_symlink():
            raise ValueError(f"{arm} post-model exists before binding")
        binding = {
            "schema": BINDING_SCHEMA,
            "arm": arm,
            "phase": "pre_injection_binding",
            "campaign_id": common_value["campaign_id"],
            "run_nonce": common_value["run_nonce"],
            "manager_epoch_digest": common_value["manager_epoch_digest"],
            "selection_identity": common_value["selection_identity"],
            "common_prestate_id": common_value["common_prestate_id"],
            "common_manifest_identity": common_manifest_identity,
            "post_model_path_absent_at_binding": str(post_path),
        }
        binding_identities[arm] = _write_json_exclusive(
            bindings_dir / f"{arm}.json",
            binding,
        )
    seal = {
        "schema": BINDING_SET_SCHEMA,
        "phase": "both_arms_bound_before_clone",
        "campaign_id": common_value["campaign_id"],
        "run_nonce": common_value["run_nonce"],
        "manager_epoch_digest": common_value["manager_epoch_digest"],
        "selection_identity": common_value["selection_identity"],
        "common_prestate_id": common_value["common_prestate_id"],
        "common_manifest_identity": common_manifest_identity,
        "bindings": binding_identities,
        "post_model_paths_absent_at_seal": [
            str(root / "arms" / "control" / "post-injection-model.pb"),
            str(root / "arms" / "treatment" / "post-injection-model.pb"),
        ],
    }
    seal_identity = _write_json_exclusive(bindings_dir / "bindings-seal.json", seal)
    return {**seal, "seal_identity": seal_identity}


def _load_binding_state(root: Path, arm: str) -> tuple[dict[str, object], dict[str, object], dict[str, bytes]]:
    common_value, common_identity = _read_json(
        root / "common-prestate" / "manifest.json",
        label="common-prestate manifest",
    )
    seal_value, seal_identity = _read_json(
        root / "bindings" / "bindings-seal.json",
        label="binding-set seal",
    )
    if type(common_value) is not dict or type(seal_value) is not dict:
        raise ValueError("common manifest or binding seal is not an object")
    if seal_value.get("schema") != BINDING_SET_SCHEMA:
        raise ValueError("binding-set schema drift")
    _assert_identity(common_identity, seal_value.get("common_manifest_identity"), label="binding common manifest")
    if seal_value.get("common_prestate_id") != common_value.get("common_prestate_id"):
        raise ValueError("binding-set common-prestate drift")
    binding_value, binding_identity = _read_json(
        root / "bindings" / f"{arm}.json",
        label=f"{arm} binding",
    )
    if type(binding_value) is not dict or binding_value.get("schema") != BINDING_SCHEMA:
        raise ValueError(f"{arm} binding schema drift")
    _assert_identity(binding_identity, seal_value["bindings"].get(arm), label=f"{arm} binding")
    for other in ("control", "treatment"):
        _raw, actual = _read_regular(root / "bindings" / f"{other}.json")
        _assert_identity(actual, seal_value["bindings"].get(other), label=f"{other} binding")
    artifacts = _verify_common_artifacts(common_value, root / "common-prestate")
    return (
        common_value,
        {
            "binding": binding_value,
            "binding_identity": binding_identity,
            "binding_set_identity": seal_identity,
        },
        artifacts,
    )


def _expected_fixture(
    *,
    model: cp_model_pb2.CpModelProto,
    response: cp_model_pb2.CpSolverResponse,
    common: Mapping[str, object],
    mandatory: object,
    candidates: object,
    incumbent: object,
) -> dict[str, object]:
    group_id, members = _selected_group(mandatory, candidates, incumbent)
    variables = _selection_variable_map(model)
    if any(member not in variables for member in members):
        raise ValueError("pre-model lacks a selected variable for the forced group")
    selected_indices = [variables[member] for member in members]
    if any(int(response.solution[index]) != 1 for index in selected_indices):
        raise ValueError("forced group is not selected in the frozen response")
    ghost = _ghost_truth(model, response, common["ghost_truth_contract"])
    capacity = len(selected_indices) - 1
    plan = {
        "schema_version": 1,
        "family": "region_capacity",
        "operation": "region_capacity_le",
        "parameters": {
            "capacity": capacity,
            "group_cell_weights": {group_id: 1},
        },
        "model_scope": {
            "ghost_policy": "bound",
            "ghost_rect_digest": ghost["rectangle_digest"],
        },
        "non_proof_forced_positive_control": True,
    }
    plan_digest = digest_json(plan)
    cut_id = (
        "forced-region-capacity-"
        + digest_json(
            {
                "common_prestate_id": common["common_prestate_id"],
                "group_id": group_id,
                "plan_digest": plan_digest,
            }
        )[:24]
    )
    compiled = {
        "schema": "noncert-cuts-gate1-v4-compiled-record-v1",
        "cut_id": cut_id,
        "family": "region_capacity",
        "operation": "region_capacity_le",
        "plan": plan,
        "plan_digest": plan_digest,
        "compiled_digest": digest_json(
            {
                "cut_id": cut_id,
                "plan_digest": plan_digest,
                "common_prestate_id": common["common_prestate_id"],
            }
        ),
        "condition_literals": [
            {
                "index": ghost["variable_index"],
                "name": ghost["variable_name"],
            }
        ],
    }
    return {
        "group_id": group_id,
        "members": members,
        "selected_indices": selected_indices,
        "capacity": capacity,
        "ghost": ghost,
        "compiled": compiled,
    }


def materialize_arm(root: Path, arm: str) -> dict[str, object]:
    """Clone the common model and perform one empty/forced post-model attach."""

    if arm not in {"control", "treatment"}:
        raise ValueError("arm must be control or treatment")
    root = _absolute(root)
    common, binding, artifacts = _load_binding_state(root, arm)
    model = _parse_canonical_proto(
        artifacts["pre_model"],
        cp_model_pb2.CpModelProto(),
        label="pre-model",
    )
    response = _parse_canonical_proto(
        artifacts["response"],
        cp_model_pb2.CpSolverResponse(),
        label="pre-response",
    )
    incumbent = _strict_json(artifacts["incumbent"][:-1], label="incumbent")
    mandatory = _strict_json(artifacts["mandatory"][:-1], label="mandatory")
    candidates = _strict_json(artifacts["candidates"][:-1], label="candidates")
    selector_contract = _strict_json(
        artifacts["selector_contract"][:-1],
        label="selector contract",
    )
    common_for_expected = {**common, "ghost_truth_contract": selector_contract}
    expected = _expected_fixture(
        model=model,
        response=response,
        common=common_for_expected,
        mandatory=mandatory,
        candidates=candidates,
        incumbent=incumbent,
    )
    arms_dir = root / "arms"
    if not arms_dir.exists():
        _mkdir_exclusive(arms_dir)
    elif arms_dir.is_symlink() or not arms_dir.is_dir():
        raise ValueError("arms root is not a regular directory")
    arm_dir = _mkdir_exclusive(arms_dir / arm)
    post_model = cp_model_pb2.CpModelProto()
    post_model.CopyFrom(model)
    compiled_records: list[dict[str, object]] = []
    samples: list[dict[str, object]] = []
    if arm == "treatment":
        compiled = expected["compiled"]
        constraint = post_model.constraints.add()
        constraint.name = f"nonproof_forced_region_capacity__{compiled['cut_id']}"
        constraint.enforcement_literal.extend(literal["index"] for literal in compiled["condition_literals"])
        constraint.linear.vars.extend(expected["selected_indices"])
        constraint.linear.coeffs.extend([1] * len(expected["selected_indices"]))
        constraint.linear.domain.extend([0, expected["capacity"]])
        constraint_index = len(post_model.constraints) - 1
        compiled = {
            **compiled,
            "post_constraint": {
                "index": constraint_index,
                "name": constraint.name,
                "vars": list(expected["selected_indices"]),
                "coeffs": [1] * len(expected["selected_indices"]),
                "domain": [0, expected["capacity"]],
                "enforcement_literals": [literal["index"] for literal in compiled["condition_literals"]],
            },
        }
        compiled_records = [compiled]
        samples = [
            {
                "schema": SAMPLE_SCHEMA,
                "cut_id": compiled["cut_id"],
                "family": "region_capacity",
                "operation": "region_capacity_le",
                "plan_digest": compiled["plan_digest"],
                "compiled_digest": compiled["compiled_digest"],
                "parameters": compiled["plan"]["parameters"],
                "enforcement_literals": [
                    {
                        **literal,
                        "value": int(response.solution[literal["index"]]),
                    }
                    for literal in compiled["condition_literals"]
                ],
                "contributions": [
                    {
                        "label": expected["group_id"],
                        "selected_count": len(expected["members"]),
                        "weight": 1,
                        "value": len(expected["members"]),
                    }
                ],
                "lhs": len(expected["members"]),
                "rhs": expected["capacity"],
                "active": True,
                "violated": True,
            }
        ]
        ledger_events: list[dict[str, object]] = [
            {
                "event": "GENESIS",
                "arm": arm,
                "common_prestate_id": common["common_prestate_id"],
            },
            {
                "event": "GENERATED",
                "cut_id": compiled["cut_id"],
                "family": "region_capacity",
                "plan_digest": compiled["plan_digest"],
            },
            {
                "event": "VALIDATED",
                "cut_id": compiled["cut_id"],
                "family": "region_capacity",
                "plan_digest": compiled["plan_digest"],
                "compiled_digest": compiled["compiled_digest"],
            },
            {
                "event": "PREPARED",
                "cut_id": compiled["cut_id"],
                "family": "region_capacity",
                "compiled_digest": compiled["compiled_digest"],
            },
            {
                "event": "APPLIED",
                "cut_id": compiled["cut_id"],
                "family": "region_capacity",
                "plan_digest": compiled["plan_digest"],
                "compiled_digest": compiled["compiled_digest"],
                "receipt": {
                    "apply_completed": True,
                    "count_delta": 1,
                    "constraint_index": constraint_index,
                    "condition_lits": compiled["condition_literals"],
                    "common_prestate_id": common["common_prestate_id"],
                },
            },
            {"event": "SEGMENT_SEAL"},
        ]
    else:
        ledger_events = [
            {
                "event": "GENESIS",
                "arm": arm,
                "common_prestate_id": common["common_prestate_id"],
            },
            {"event": "SEGMENT_SEAL"},
        ]
    post_raw = post_model.SerializeToString(deterministic=True)
    post_identity = _write_exclusive(arm_dir / "post-injection-model.pb", post_raw)
    assignment = {
        "schema": ASSIGNMENT_SCHEMA,
        "common_prestate_id": common["common_prestate_id"],
        "pre_model_sha256": hashlib.sha256(artifacts["pre_model"]).hexdigest(),
        "response_sha256": hashlib.sha256(artifacts["response"]).hexdigest(),
        "variables": [
            {
                "index": index,
                "name": str(model.variables[index].name),
                "value": int(response.solution[index]),
            }
            for index in range(len(model.variables))
        ],
    }
    assignment_identity = _write_json_exclusive(arm_dir / "assignment.json", assignment)
    sample_corpus = {
        "schema": "noncert-cuts-gate1-v4-arithmetic-corpus-v1",
        "arm": arm,
        "common_prestate_id": common["common_prestate_id"],
        "samples": samples,
    }
    samples_identity = _write_json_exclusive(
        arm_dir / "arithmetic-samples.json",
        sample_corpus,
    )
    ledger_raw, ledger_summary = _ledger(
        ledger_events,
        scope_id=f"{common['run_nonce']}-{arm}",
    )
    ledger_identity = _write_exclusive(arm_dir / "ledger.jsonl", ledger_raw)
    evidence = {
        "schema": ARM_SCHEMA,
        "arm": arm,
        "phase": "post_injection_clone",
        "campaign_id": common["campaign_id"],
        "run_nonce": common["run_nonce"],
        "manager_epoch_digest": common["manager_epoch_digest"],
        "selection_identity": common["selection_identity"],
        "common_prestate_id": common["common_prestate_id"],
        "common_manifest_identity": binding["binding"]["common_manifest_identity"],
        "binding_identity": binding["binding_identity"],
        "binding_set_identity": binding["binding_set_identity"],
        "pre_model_identity": common["artifacts"]["pre_model"],
        "pre_response_identity": common["artifacts"]["response"],
        "post_model_identity": post_identity,
        "assignment_identity": assignment_identity,
        "sample_corpus_identity": samples_identity,
        "ledger_identity": ledger_identity,
        "post_solve_performed": False,
        "post_response_present": False,
        "injection": {
            "enabled": arm == "treatment",
            "provider": ("non_proof_forced_positive_control" if arm == "treatment" else "empty_control_provider"),
            "generated": int(arm == "treatment"),
            "compiled": len(compiled_records),
            "applied": int(arm == "treatment"),
            "compiled_records": compiled_records,
        },
        "ledger": ledger_summary,
        "claim_boundary": {
            "established": (
                ["forced fixture attached to an unsolved post-model clone"]
                if arm == "treatment"
                else ["control clone received no injected cut"]
            ),
            "not_established": [
                "post-attach solver result",
                "family-global soundness",
                "runtime usefulness",
                "formal infeasibility",
            ],
        },
    }
    evidence_identity = _write_json_exclusive(arm_dir / "evidence.json", evidence)
    return {**evidence, "evidence_identity": evidence_identity}


def live_master_text_fingerprint(master: object) -> dict[str, object]:
    """Return the drill-only pybind text fingerprint of one unsolved master.

    The formal common-prestate path uses official binary protobuf bytes.  The
    production master currently exposes a pybind proto whose stable in-memory
    read surface is ``str(Proto())``; this fingerprint exists only to ensure
    that control and treatment drill clones start byte-equivalent before the
    real typed attach call.  It is not accepted by the formal arithmetic gate.
    """

    try:
        proto = master.model.Proto()
        variable_count = len(proto.variables)
        constraint_count = len(proto.constraints)
    except (AttributeError, TypeError) as exc:
        raise ValueError("typed drill requires a real CP-SAT master proto") from exc
    raw = str(proto).encode("utf-8")
    if not raw:
        raise ValueError("typed drill master proto text is empty")
    return {
        "surface": "ortools_pybind_proto_text_drill_only_v1",
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "variable_count": variable_count,
        "constraint_count": constraint_count,
    }


def _validate_typed_drill_prestate(
    prestate: object,
    arm_binding: object,
    *,
    arm: str,
    live_fingerprint: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    prestate_keys = {
        "schema",
        "phase",
        "common_prestate_id",
        "pre_model_fingerprint",
        "response_identity",
        "solution_identity",
        "incumbent_identity",
        "post_solve_performed",
        "synthetic_offline_not_solver_verified",
    }
    if (
        type(prestate) is not dict
        or set(prestate) != prestate_keys
        or prestate.get("schema") != TYPED_DRILL_PRESTATE_SCHEMA
        or prestate.get("phase") != "pre_injection"
        or type(prestate.get("common_prestate_id")) is not str
        or not prestate["common_prestate_id"]
        or prestate.get("post_solve_performed") is not False
        or prestate.get("synthetic_offline_not_solver_verified") is not True
        or prestate.get("pre_model_fingerprint") != dict(live_fingerprint)
    ):
        raise ValueError("production typed drill prestate drifted")
    for role in ("response_identity", "solution_identity", "incumbent_identity"):
        _strict_identity(prestate[role], label=f"typed drill {role}")
    binding_keys = {
        "schema",
        "phase",
        "arm",
        "common_prestate_id",
        "pre_model_fingerprint",
    }
    if (
        type(arm_binding) is not dict
        or set(arm_binding) != binding_keys
        or arm_binding.get("schema") != TYPED_DRILL_BINDING_SCHEMA
        or arm_binding.get("phase") != "pre_injection_binding"
        or arm_binding.get("arm") != arm
        or arm_binding.get("common_prestate_id") != prestate["common_prestate_id"]
        or arm_binding.get("pre_model_fingerprint") != dict(live_fingerprint)
    ):
        raise ValueError(f"production typed drill {arm} binding drifted")
    return dict(prestate), dict(arm_binding)


def exercise_production_typed_attach_drill(
    *,
    arm: str,
    controller: object,
    state: object,
    forced_cut: object,
    common_prestate: object,
    arm_binding: object,
) -> dict[str, object]:
    """Exercise the real production typed attach chain without solving.

    ``forced_cut`` must already be a genuine production F1 oracle result for
    ``state``.  The adapter only substitutes the provider output so the
    orchestration path deterministically sees that cut; it does not bypass or
    replace ``cut_to_envelope_v1``, the production registry/compiler,
    step-7, the sole scope resolver, or ``step_8_apply_to_master``.

    This drill is deliberately not the formal forced arithmetic fixture.  A
    production-valid F1 proof cannot encode the deliberately false ``n <=
    n-1`` positive-control inequality, and this no-solver drill has no genuine
    solved incumbent.  Its result therefore establishes only typed mechanism
    reachability and must never authorize Gate 1 by itself.
    """

    if arm not in {"control", "treatment"}:
        raise ValueError("typed drill arm must be control or treatment")
    if os.environ.get("EXACT_CUT_FRAMEWORK_ATTACH") is not None:
        raise ValueError("attach must be absent while the pre-injection state is bound")
    try:
        master = controller.master
        enabled = set(controller._enabled_cut_families)
    except (AttributeError, TypeError) as exc:
        raise ValueError("typed drill requires an LBBD controller") from exc
    if enabled != {"region_capacity"}:
        raise ValueError("typed drill controller must enable only region_capacity")
    if getattr(forced_cut, "family", None) != "region_capacity":
        raise ValueError("typed drill forced provider accepts one production F1 cut")
    before = live_master_text_fingerprint(master)
    checked_prestate, checked_binding = _validate_typed_drill_prestate(
        common_prestate,
        arm_binding,
        arm=arm,
        live_fingerprint=before,
    )

    # Function-local imports keep this research adapter explicit and make its
    # patch surface auditable.  Every wrapped production function still calls
    # the original implementation and records only the returned type/identity.
    from unittest import mock

    from src.cuts import lifecycle, typed_platform
    from src.cuts.oracles import region_capacity_oracle
    from src.cuts.oracles import shape_packing_hall_oracle
    from src.cuts.typed_platform import CompiledCut

    real_validate = typed_platform.validate_and_compile_cut
    real_resolve = lifecycle._resolve_model_scope_binding
    real_step_8 = lifecycle.step_8_apply_to_master
    calls: dict[str, list[dict[str, object]]] = {
        "provider": [],
        "compiler": [],
        "resolver": [],
        "step_8": [],
    }

    def forced_provider(*_args: object, **_kwargs: object) -> list[object]:
        cuts = [] if arm == "control" else [forced_cut]
        calls["provider"].append(
            {
                "returned_count": len(cuts),
                "cut_id": (str(getattr(forced_cut, "cut_id", "")) if cuts else None),
            }
        )
        return cuts

    def capture_validate(*args: object, **kwargs: object) -> object:
        result = real_validate(*args, **kwargs)
        calls["compiler"].append(
            {
                "result_type": type(result).__name__,
                "cut_id": str(getattr(result, "cut_id", "")),
                "family": str(getattr(getattr(result, "plan", None), "family", "")),
                "operation": str(getattr(getattr(result, "plan", None), "operation", "")),
            }
        )
        return result

    def capture_resolve(*args: object, **kwargs: object) -> object:
        binding = real_resolve(*args, **kwargs)
        calls["resolver"].append(
            {
                "binding_type": type(binding).__name__,
                "master_domain_family": str(getattr(binding, "master_domain_family", "")),
                "rect_idx": getattr(binding, "rect_idx", None),
            }
        )
        return binding

    def capture_step_8(*args: object, **kwargs: object) -> object:
        compiled = args[0] if args else None
        if type(compiled) is not CompiledCut:
            raise TypeError("typed drill step-8 wrapper received a non-CompiledCut")
        result = real_step_8(*args, **kwargs)
        calls["step_8"].append(
            {
                "cut_id": str(compiled.cut_id),
                "family": str(compiled.plan.family),
                "operation": str(compiled.plan.operation),
            }
        )
        return result

    with (
        mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}),
        mock.patch.object(
            controller,
            "_build_cut_framework_state",
            return_value=state,
        ),
        mock.patch.object(
            region_capacity_oracle,
            "generate_region_capacity_cuts",
            side_effect=forced_provider,
        ),
        mock.patch.object(
            shape_packing_hall_oracle,
            "compute_sot_region_demand_overrides",
            return_value={},
        ),
        mock.patch.object(
            typed_platform,
            "validate_and_compile_cut",
            side_effect=capture_validate,
        ),
        mock.patch.object(
            lifecycle,
            "_resolve_model_scope_binding",
            side_effect=capture_resolve,
        ),
        mock.patch.object(
            lifecycle,
            "step_8_apply_to_master",
            side_effect=capture_step_8,
        ),
    ):
        attached = controller._maybe_attach_framework_cuts(
            trigger="binding_infeasible",
            iteration=1001,
            solution=None,
        )

    after = live_master_text_fingerprint(master)
    if arm == "control":
        if (
            attached != 0
            or calls["provider"] != [{"returned_count": 0, "cut_id": None}]
            or calls["compiler"]
            or calls["resolver"]
            or calls["step_8"]
            or after != before
        ):
            raise RuntimeError("typed control drill did not remain an exact no-op")
    else:
        if (
            attached != 1
            or len(calls["provider"]) != 1
            or len(calls["compiler"]) != 1
            or calls["compiler"][0]["result_type"] != "CompiledCut"
            or calls["compiler"][0]["family"] != "region_capacity"
            or calls["compiler"][0]["operation"] != "region_capacity_le"
            or len(calls["resolver"]) != 1
            or calls["resolver"][0]["master_domain_family"] != "region_capacity"
            or len(calls["step_8"]) != 1
            or after["constraint_count"] != before["constraint_count"] + 1
        ):
            raise RuntimeError("typed treatment drill did not traverse the full production chain")
    return {
        "schema": TYPED_DRILL_RESULT_SCHEMA,
        "arm": arm,
        "status": "PASS_PRODUCTION_TYPED_ATTACH_DRILL",
        "common_prestate_id": checked_prestate["common_prestate_id"],
        "arm_binding": checked_binding,
        "pre_model_fingerprint": before,
        "post_model_fingerprint": after,
        "post_solve_performed": False,
        "attached": attached,
        "calls": calls,
        "formal_gate_authorized": False,
        "claim_boundary": {
            "established": ["forced provider reached the real production typed attach chain"],
            "not_established": [
                "a genuine solved production frozen incumbent",
                "forced arithmetic-fixture admission through the production registry",
                "family-global soundness beyond the production cut supplied",
                "Gate 1 v4 completion",
            ],
        },
    }


def tiny_inputs() -> dict[str, object]:
    """Return one deterministic tiny common-prestate fixture without solving."""

    model = cp_model_pb2.CpModelProto()
    for name in ("ghost__0_0_2_1", "ghost__1_0_2_1", "select__i1", "select__i2"):
        variable = model.variables.add()
        variable.name = name
        variable.domain.extend([0, 1])
    ghost_exactly_one = model.constraints.add()
    ghost_exactly_one.name = "complete_ghost_selector"
    ghost_exactly_one.exactly_one.literals.extend([0, 1])
    response = cp_model_pb2.CpSolverResponse()
    response.status = cp_model_pb2.FEASIBLE
    response.solution.extend([1, 0, 1, 1])
    mandatory = [
        {
            "instance_id": "i1",
            "facility_type": "machine",
            "operation_type": "op",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "i2",
            "facility_type": "machine",
            "operation_type": "op",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    candidates = {
        "facility_pools": {
            "machine": [
                {
                    "pose_id": "p0",
                    "anchor": {"x": 0, "y": 0},
                    "occupied_cells": [[0, 0]],
                },
                {
                    "pose_id": "p1",
                    "anchor": {"x": 1, "y": 0},
                    "occupied_cells": [[1, 0]],
                },
            ]
        }
    }
    incumbent = {
        "i1": {
            "instance_id": "i1",
            "facility_type": "machine",
            "operation_type": "op",
            "pose_id": "p0",
            "pose_idx": 0,
            "anchor": {"x": 0, "y": 0},
        },
        "i2": {
            "instance_id": "i2",
            "facility_type": "machine",
            "operation_type": "op",
            "pose_id": "p1",
            "pose_idx": 1,
            "anchor": {"x": 1, "y": 0},
        },
        "ghost_pick": {
            "pose_id": "ghost_anchor::0,0",
            "pose_idx": 0,
            "anchor": {"x": 0, "y": 0},
        },
    }
    return {
        "model_raw": model.SerializeToString(deterministic=True),
        "response_raw": response.SerializeToString(deterministic=True),
        "incumbent": incumbent,
        "selector_contract": {
            "schema_version": 1,
            "grid": {"width": 3, "height": 1},
            "ghost": {"width": 2, "height": 1},
        },
        "mandatory": mandatory,
        "candidates": candidates,
    }


def build_tiny_offline_fixture(root: Path) -> dict[str, object]:
    """Build the complete offline fixture in one fresh no-overwrite root."""

    root = _mkdir_exclusive(root)
    selection = {
        "schema": SELECTION_SCHEMA,
        "purpose": "gate1_v4_e2e_drill",
        "campaign_id": "offline-campaign-v4",
        "run_nonce": "offline-run-v4",
        "manager_epoch_digest": "offline-manager-epoch-v4",
        "gate1_formal_eligible": False,
        "repository_head": EXPECTED_HEAD,
    }
    selection_identity = _write_json_exclusive(root / "selection.json", selection)
    values = tiny_inputs()
    common = seal_common_prestate(
        root,
        **values,
        selection_identity=selection_identity,
        campaign_id=selection["campaign_id"],
        run_nonce=selection["run_nonce"],
        manager_epoch_digest=selection["manager_epoch_digest"],
        repository_head=selection["repository_head"],
    )
    bindings = create_arm_bindings(root)
    control = materialize_arm(root, "control")
    treatment = materialize_arm(root, "treatment")
    return {
        "root": str(root),
        "selection_identity": selection_identity,
        "common": common,
        "bindings": bindings,
        "control": control,
        "treatment": treatment,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tiny-offline-fixture", action="store_true")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.tiny_offline_fixture:
        parser.error("only --tiny-offline-fixture is available in this research helper")
    result = build_tiny_offline_fixture(args.output_root)
    print(
        json.dumps(
            {
                "status": "OFFLINE_FIXTURE_COMPLETE",
                "root": result["root"],
                "control": result["control"]["injection"],
                "treatment": result["treatment"]["injection"],
                "solver_started": False,
                "systemd_started": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
