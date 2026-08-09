#!/usr/bin/env python3
"""Independent Gate-1 replay for one concrete typed APPLIED inequality.

This stdlib-only checker does not import the cut encoder, typed compiler,
ledger reader, or the positive-control runner.  It reconstructs mandatory
groups and selected poses from byte-identified strict inputs, rebuilds typed
plan/compiled digests, replays the canonical JSONL ledger chain, joins each
captured sample to its compiled cut and durable APPLIED event, and evaluates
the inequality from the frozen incumbent and literal assignment.

The result is deliberately narrow.  It checks a concrete application and
exclusion; it is not a family-global soundness verifier or proof sidecar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


EXPECTED_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
LEDGER_SCHEMA_VERSION = "cut-ledger-v1"
LEDGER_EVENT_TYPES = frozenset(
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
ALLOWED_OPERATIONS = {
    "region_capacity_le": "region_capacity",
    "shape_packing_hall_le": "shape_packing_hall",
    "power_pose_exclusion": "power_hitting_set",
}
_GENESIS_ANCHOR = "0" * 64
_PLAN_DIGEST_PREFIX = b"zmd.constraint-plan.v1:"
_MODEL_SCOPE_DIGEST_PREFIX = b"zmd.model-scope.v1:"
_COMPILED_CUT_DIGEST_PREFIX = b"zmd.compiled-cut.v1:"
_GHOST_RECT_DIGEST_PREFIX = b"zmd.ghost-rect.v1:"


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON constant: {value}")


def _strict_loads(raw: bytes, *, label: str) -> object:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} is not UTF-8") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_constant,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not strict JSON: {exc}") from exc


def _absolute(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def _reject_symlink_chain(path: Path) -> None:
    absolute = _absolute(path)
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"symlink path component rejected: {current}")


def _read_regular(path: Path) -> bytes:
    absolute = _absolute(path)
    _reject_symlink_chain(absolute)
    if not absolute.is_file() or absolute.is_symlink():
        raise ValueError(f"input must be a regular non-symlink file: {path}")
    return absolute.read_bytes()


def _identity(path: Path, raw: bytes | None = None) -> dict[str, object]:
    data = _read_regular(path) if raw is None else raw
    return {
        "path": str(_absolute(path)),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _read_json(path: Path) -> tuple[object, bytes, dict[str, object]]:
    raw = _read_regular(path)
    return _strict_loads(raw, label=str(path)), raw, _identity(path, raw)


def _write_exclusive(path: Path, payload: object) -> None:
    absolute = _absolute(path)
    if absolute.exists() or absolute.is_symlink():
        raise FileExistsError(f"refusing to overwrite output: {absolute}")
    parent = absolute.parent
    _reject_symlink_chain(parent)
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError("output parent must be an existing non-symlink directory")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(absolute, flags, 0o600)
    try:
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ).encode("utf-8")
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(raw)
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _plain_digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _is_sha256(value: object) -> bool:
    if type(value) is not str or len(value) != 64 or value != value.lower():
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _nonempty_str(value: object, *, field: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{field} must be a non-empty exact string")
    return value


def _sha256(value: object, *, field: str) -> str:
    if not _is_sha256(value):
        raise ValueError(f"{field} must be a lowercase SHA-256")
    return str(value)


def _exact_int(value: object, *, field: str, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        suffix = f" >= {minimum}" if minimum is not None else ""
        raise ValueError(f"{field} must be an exact integer{suffix}")
    return value


def _canonical_node(value: object) -> object:
    if value is None:
        return ["null"]
    if type(value) is bool:
        return ["bool", value]
    if type(value) is int:
        return ["int", value]
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("digest projection contains non-finite float")
        return ["float", value]
    if type(value) is str:
        return ["str", value]
    if type(value) is dict:
        return [
            "mapping",
            [[key, _canonical_node(value[key])] for key in sorted(value)],
        ]
    if type(value) is list:
        return ["sequence", [_canonical_node(item) for item in value]]
    raise ValueError(f"digest projection has unsupported {type(value).__name__}")


def _domain_digest(prefix: bytes, projection: object) -> str:
    return hashlib.sha256(prefix + _canonical_bytes(projection)).hexdigest()


def _rebuild_plan(compiled: dict[str, Any]) -> dict[str, Any]:
    plan = compiled.get("plan")
    if type(plan) is not dict:
        raise ValueError("compiled record plan must be an object")
    family = _nonempty_str(plan.get("family"), field="plan.family")
    schema_version = _exact_int(
        plan.get("schema_version"),
        field="plan.schema_version",
        minimum=1,
    )
    semantic_fingerprint = _sha256(
        plan.get("semantic_fingerprint"),
        field="plan.semantic_fingerprint",
    )
    operation = _nonempty_str(plan.get("operation"), field="plan.operation")
    if ALLOWED_OPERATIONS.get(operation) != family:
        raise ValueError("plan family/operation pair is outside the Gate-1 set")
    parameters = plan.get("parameters")
    if type(parameters) is not dict:
        raise ValueError("plan.parameters must be an object")
    _validate_parameters(operation, parameters)
    scope = plan.get("model_scope")
    if type(scope) is not dict:
        raise ValueError("plan.model_scope must be an object")
    if set(scope) != {"domain_fingerprint", "ghost_policy", "ghost_rect_digest"}:
        raise ValueError("plan.model_scope has an unexpected field set")
    domain_fingerprint = _nonempty_str(
        scope.get("domain_fingerprint"),
        field="model_scope.domain_fingerprint",
    )
    ghost_policy = scope.get("ghost_policy")
    if ghost_policy not in {"agnostic", "bound"}:
        raise ValueError("model_scope.ghost_policy must be agnostic or bound")
    ghost_rect_digest = scope.get("ghost_rect_digest")
    if ghost_policy == "agnostic":
        if ghost_rect_digest is not None:
            raise ValueError("agnostic model scope cannot carry ghost digest")
    else:
        _sha256(ghost_rect_digest, field="model_scope.ghost_rect_digest")
    scope_projection = {
        "domain_fingerprint": domain_fingerprint,
        "ghost_policy": ghost_policy,
        "ghost_rect_digest": ghost_rect_digest,
        "schema_version": 1,
    }
    rebuilt_scope_digest = _domain_digest(
        _MODEL_SCOPE_DIGEST_PREFIX,
        scope_projection,
    )
    rebuilt_plan_digest = _domain_digest(
        _PLAN_DIGEST_PREFIX,
        {
            "family": family,
            "model_scope": _canonical_node(scope_projection),
            "operation": operation,
            "parameters": _canonical_node(parameters),
            "schema_version": schema_version,
            "semantic_fingerprint": semantic_fingerprint,
        },
    )
    cut_id = _nonempty_str(compiled.get("cut_id"), field="compiled.cut_id")
    proof_digest = _sha256(
        compiled.get("proof_digest"),
        field="compiled.proof_digest",
    )
    snapshot_digest = _sha256(
        compiled.get("snapshot_digest"),
        field="compiled.snapshot_digest",
    )
    if compiled.get("family") != family:
        raise ValueError("compiled record family differs from plan family")
    if compiled.get("scope_digest") != rebuilt_scope_digest:
        raise ValueError("compiled scope digest does not rebuild")
    if plan.get("digest") != rebuilt_plan_digest:
        raise ValueError("typed plan digest does not rebuild")
    rebuilt_compiled_digest = _domain_digest(
        _COMPILED_CUT_DIGEST_PREFIX,
        {
            "cut_id": cut_id,
            "plan_digest": rebuilt_plan_digest,
            "proof_digest": proof_digest,
            "scope_digest": rebuilt_scope_digest,
            "snapshot_digest": snapshot_digest,
        },
    )
    if compiled.get("compiled_digest") != rebuilt_compiled_digest:
        raise ValueError("compiled cut digest does not rebuild")
    return {
        "cut_id": cut_id,
        "family": family,
        "operation": operation,
        "parameters": parameters,
        "semantic_fingerprint": semantic_fingerprint,
        "plan_digest": rebuilt_plan_digest,
        "compiled_digest": rebuilt_compiled_digest,
        "snapshot_digest": snapshot_digest,
        "model_scope": scope,
    }


def _validate_parameters(operation: str, parameters: dict[str, Any]) -> None:
    expected = {
        "region_capacity_le": {"capacity", "group_cell_weights"},
        "shape_packing_hall_le": {"capacity", "group_id", "region_kind"},
        "power_pose_exclusion": {
            "blocked_cells_digest",
            "group_id",
            "pose_id",
        },
    }[operation]
    if set(parameters) != expected:
        raise ValueError(f"{operation} parameters have unexpected fields")
    if operation == "region_capacity_le":
        _exact_int(parameters["capacity"], field="capacity", minimum=0)
        weights = parameters["group_cell_weights"]
        if type(weights) is not dict or not weights:
            raise ValueError("group_cell_weights must be a non-empty object")
        for group_id, weight in weights.items():
            _nonempty_str(group_id, field="group_cell_weights key")
            _exact_int(weight, field=f"weight[{group_id}]", minimum=1)
    elif operation == "shape_packing_hall_le":
        _exact_int(parameters["capacity"], field="capacity", minimum=0)
        _nonempty_str(parameters["group_id"], field="group_id")
        if parameters["region_kind"] not in {
            "left_baseline",
            "bottom_baseline",
        }:
            raise ValueError("region_kind is outside the closed set")
    else:
        _nonempty_str(parameters["group_id"], field="group_id")
        _nonempty_str(parameters["pose_id"], field="pose_id")
        _sha256(parameters["blocked_cells_digest"], field="blocked_cells_digest")


def _replay_ledger(raw: bytes) -> dict[str, object]:
    if not raw.endswith(b"\n"):
        raise ValueError("ledger segment lacks its final newline")
    lines = raw.split(b"\n")[:-1]
    if not lines:
        raise ValueError("ledger segment is empty")
    events: list[dict[str, Any]] = []
    previous = _GENESIS_ANCHOR
    writer_id: str | None = None
    scope_id: str | None = None
    for index, line in enumerate(lines):
        parsed = _strict_loads(line, label=f"ledger line {index}")
        if type(parsed) is not dict:
            raise ValueError(f"ledger line {index} is not an object")
        if _canonical_bytes(parsed) != line:
            raise ValueError(f"ledger line {index} is not canonical JSON")
        if parsed.get("schema_version") != LEDGER_SCHEMA_VERSION:
            raise ValueError(f"ledger line {index} schema mismatch")
        if parsed.get("event") not in LEDGER_EVENT_TYPES:
            raise ValueError(f"ledger line {index} has unknown event")
        if parsed.get("seq") != index:
            raise ValueError(f"ledger line {index} sequence mismatch")
        if parsed.get("prev_event_hash") != previous:
            raise ValueError(f"ledger line {index} hash-chain mismatch")
        if index == 0 and parsed.get("event") != "GENESIS":
            raise ValueError("ledger does not start with GENESIS")
        if index and events[-1]["event"] == "SEGMENT_SEAL":
            raise ValueError("ledger contains data after SEGMENT_SEAL")
        current_writer = _nonempty_str(
            parsed.get("writer_id"),
            field=f"ledger[{index}].writer_id",
        )
        current_scope = _nonempty_str(
            parsed.get("scope_id"),
            field=f"ledger[{index}].scope_id",
        )
        writer_id = writer_id or current_writer
        scope_id = scope_id or current_scope
        if current_writer != writer_id or current_scope != scope_id:
            raise ValueError("ledger writer/scope identity drift")
        events.append(parsed)
        previous = hashlib.sha256(line).hexdigest()
    if events[-1]["event"] != "SEGMENT_SEAL":
        raise ValueError("ledger segment is not sealed")
    counts = Counter(str(event["event"]) for event in events)
    return {
        "status": "complete",
        "events": events,
        "event_count": len(events),
        "event_counts": dict(sorted(counts.items())),
        "tail_hash": previous,
        "writer_id": writer_id,
        "scope_id": scope_id,
    }


def _mandatory_groups(
    payload: object,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if type(payload) is not list or not payload:
        raise ValueError("mandatory instances must be a non-empty array")
    instances: dict[str, dict[str, Any]] = {}
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for index, item in enumerate(payload):
        if type(item) is not dict:
            raise ValueError(f"mandatory instance {index} is not an object")
        instance_id = _nonempty_str(
            item.get("instance_id"),
            field=f"mandatory[{index}].instance_id",
        )
        if instance_id in instances:
            raise ValueError(f"duplicate mandatory instance {instance_id}")
        facility = _nonempty_str(
            item.get("facility_type"),
            field=f"mandatory[{index}].facility_type",
        )
        operation = _nonempty_str(
            item.get("operation_type"),
            field=f"mandatory[{index}].operation_type",
        )
        if item.get("is_mandatory") is not True or item.get("bound_type") != "exact":
            raise ValueError(f"{instance_id} is not a mandatory exact instance")
        instances[instance_id] = item
        buckets[(facility, operation)].append(item)
    groups: dict[str, dict[str, Any]] = {}
    for group_index, ((facility, operation), members) in enumerate(sorted(buckets.items())):
        ordered = sorted((_nonempty_str(item["instance_id"], field="instance_id") for item in members))
        group_id = f"group::{facility}::{operation}::{group_index}"
        groups[group_id] = {
            "facility_type": facility,
            "operation_type": operation,
            "instance_ids": ordered,
        }
    return instances, groups


def _candidate_indices(
    payload: object,
    facilities: set[str],
) -> dict[str, tuple[list[dict[str, Any]], dict[str, int]]]:
    if type(payload) is not dict or type(payload.get("facility_pools")) is not dict:
        raise ValueError("candidate placements lack facility_pools object")
    raw_pools = payload["facility_pools"]
    indices: dict[str, tuple[list[dict[str, Any]], dict[str, int]]] = {}
    for facility in sorted(facilities):
        pool = raw_pools.get(facility)
        if type(pool) is not list or not pool:
            raise ValueError(f"candidate pool missing for {facility}")
        by_id: dict[str, int] = {}
        checked: list[dict[str, Any]] = []
        for index, pose in enumerate(pool):
            if type(pose) is not dict:
                raise ValueError(f"{facility} pose {index} is not an object")
            pose_id = _nonempty_str(
                pose.get("pose_id"),
                field=f"{facility}[{index}].pose_id",
            )
            if pose_id in by_id:
                raise ValueError(f"duplicate pose ID {facility}:{pose_id}")
            by_id[pose_id] = index
            checked.append(pose)
        indices[facility] = (checked, by_id)
    return indices


def _validate_incumbent(
    arm_result: dict[str, Any],
    mandatory: dict[str, dict[str, Any]],
    groups: dict[str, dict[str, Any]],
    candidates: dict[str, tuple[list[dict[str, Any]], dict[str, int]]],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    prestate = arm_result.get("prestate")
    if type(prestate) is not dict or type(prestate.get("incumbent")) is not dict:
        raise ValueError("arm result lacks frozen incumbent")
    incumbent = prestate["incumbent"]
    digest = _plain_digest(incumbent)
    if prestate.get("incumbent_sha256") != digest:
        raise ValueError("frozen incumbent digest mismatch")
    selected: dict[str, dict[str, Any]] = {}
    for instance_id, strict in mandatory.items():
        entry = incumbent.get(instance_id)
        if type(entry) is not dict:
            raise ValueError(f"frozen incumbent omits {instance_id}")
        if (
            entry.get("instance_id") != instance_id
            or entry.get("facility_type") != strict["facility_type"]
            or entry.get("operation_type") != strict["operation_type"]
        ):
            raise ValueError(f"frozen incumbent identity drift for {instance_id}")
        facility = str(strict["facility_type"])
        pool, by_id = candidates[facility]
        pose_id = _nonempty_str(
            entry.get("pose_id"),
            field=f"incumbent[{instance_id}].pose_id",
        )
        pose_idx = _exact_int(
            entry.get("pose_idx"),
            field=f"incumbent[{instance_id}].pose_idx",
            minimum=0,
        )
        if pose_idx >= len(pool) or by_id.get(pose_id) != pose_idx:
            raise ValueError(f"pose identity/index mismatch for {instance_id}")
        if entry.get("anchor") != pool[pose_idx].get("anchor"):
            raise ValueError(f"pose anchor mismatch for {instance_id}")
        selected[instance_id] = {
            **entry,
            "_pose": pool[pose_idx],
        }
    by_group: dict[str, list[dict[str, Any]]] = {}
    for group_id, group in groups.items():
        entries = [selected[instance_id] for instance_id in group["instance_ids"]]
        pose_ids = [str(entry["pose_id"]) for entry in entries]
        if len(pose_ids) != len(set(pose_ids)):
            raise ValueError(f"group {group_id} selects a pose more than once")
        by_group[group_id] = entries
    ghost = incumbent.get("ghost_pick")
    if type(ghost) is not dict or type(ghost.get("anchor")) is not dict:
        raise ValueError("frozen incumbent lacks ghost_pick")
    return prestate, by_group, ghost


def _literal_assignment(
    payload: object | None,
    *,
    prestate_sha256: str,
    required: bool,
) -> dict[int, dict[str, Any]]:
    if payload is None:
        if required:
            raise ValueError("APPLIED samples require a frozen literal assignment")
        return {}
    if type(payload) is not dict or payload.get("schema_version") != 1:
        raise ValueError("frozen assignment schema_version must be exact 1")
    if payload.get("prestate_sha256") != prestate_sha256:
        raise ValueError("frozen assignment prestate digest mismatch")
    literals = payload.get("literals")
    if type(literals) is not list:
        raise ValueError("frozen assignment literals must be an array")
    by_index: dict[int, dict[str, Any]] = {}
    names: set[str] = set()
    for offset, literal in enumerate(literals):
        if type(literal) is not dict or set(literal) != {"index", "name", "value"}:
            raise ValueError(f"assignment literal {offset} has invalid fields")
        index = _exact_int(literal["index"], field="literal.index")
        name = _nonempty_str(literal["name"], field="literal.name")
        value = literal["value"]
        if type(value) is not int or value not in {0, 1}:
            raise ValueError("literal.value must be exact 0 or 1")
        if index in by_index or name in names:
            raise ValueError("frozen assignment has duplicate index/name")
        by_index[index] = literal
        names.add(name)
    return by_index


def _ghost_digest(
    arm_result: dict[str, Any],
    ghost: dict[str, Any],
) -> tuple[int, str]:
    config = arm_result.get("config")
    if type(config) is not dict or type(config.get("ghost_rect")) is not list:
        raise ValueError("arm result lacks ghost_rect config")
    dims = config["ghost_rect"]
    if len(dims) != 2 or any(type(value) is not int or value <= 0 for value in dims):
        raise ValueError("ghost_rect config must contain two positive exact ints")
    anchor = ghost["anchor"]
    x = _exact_int(anchor.get("x"), field="ghost anchor x", minimum=0)
    y = _exact_int(anchor.get("y"), field="ghost anchor y", minimum=0)
    rect_idx = _exact_int(ghost.get("pose_idx"), field="ghost pose_idx", minimum=0)
    if ghost.get("pose_id") != f"ghost_anchor::{x},{y}":
        raise ValueError("ghost pose identity does not match its anchor")
    digest = hashlib.sha256(_GHOST_RECT_DIGEST_PREFIX + _canonical_bytes([x, y, dims[0], dims[1]])).hexdigest()
    return rect_idx, digest


def _independent_arithmetic(
    record: dict[str, Any],
    by_group: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, object]], int, int]:
    operation = str(record["operation"])
    parameters = record["parameters"]
    contributions: list[dict[str, object]] = []
    if operation == "region_capacity_le":
        for group_id in sorted(parameters["group_cell_weights"]):
            if group_id not in by_group:
                raise ValueError(f"region cut references unknown group {group_id}")
            weight = int(parameters["group_cell_weights"][group_id])
            count = len({str(entry["pose_id"]) for entry in by_group[group_id]})
            contributions.append(
                {
                    "label": group_id,
                    "selected_count": count,
                    "weight": weight,
                    "value": count * weight,
                }
            )
        rhs = int(parameters["capacity"])
    elif operation == "shape_packing_hall_le":
        group_id = str(parameters["group_id"])
        entries = by_group.get(group_id)
        if entries is None:
            raise ValueError(f"shape cut references unknown group {group_id}")
        region_kind = str(parameters["region_kind"])
        count = 0
        for entry in entries:
            cells = entry["_pose"].get("occupied_cells")
            if type(cells) is not list or not cells:
                raise ValueError("selected candidate pose lacks occupied_cells")
            checked_cells: list[tuple[int, int]] = []
            for cell in cells:
                if type(cell) is not list or len(cell) != 2 or type(cell[0]) is not int or type(cell[1]) is not int:
                    raise ValueError("candidate occupied_cells entry is malformed")
                checked_cells.append((cell[0], cell[1]))
            on_baseline = (
                all(y == 0 for _x, y in checked_cells)
                if region_kind == "left_baseline"
                else all(x == 0 for x, _y in checked_cells)
            )
            count += int(on_baseline)
        contributions.append(
            {
                "label": group_id,
                "selected_count": count,
                "weight": 1,
                "value": count,
            }
        )
        rhs = int(parameters["capacity"])
    else:
        group_id = str(parameters["group_id"])
        entries = by_group.get(group_id)
        if entries is None:
            raise ValueError(f"power cut references unknown group {group_id}")
        pose_id = str(parameters["pose_id"])
        count = sum(str(entry["pose_id"]) == pose_id for entry in entries)
        contributions.append(
            {
                "label": f"{group_id}:{pose_id}",
                "selected_count": count,
                "weight": 1,
                "value": count,
            }
        )
        rhs = 0
    lhs = sum(int(item["value"]) for item in contributions)
    return contributions, lhs, rhs


def _validate_result_envelope(
    arm_result: dict[str, Any],
    sample_corpus: dict[str, Any],
    ledger_replay: dict[str, Any],
    *,
    expected_head: str,
) -> tuple[str, str]:
    if arm_result.get("schema_version") != 1:
        raise ValueError("arm result schema_version must be exact 1")
    if arm_result.get("terminal_status") != "ARM_COMPLETE":
        raise ValueError("arm result is not ARM_COMPLETE")
    arm = arm_result.get("arm")
    if arm not in {"control", "treatment"}:
        raise ValueError("arm must be control or treatment")
    authority = arm_result.get("authority")
    if type(authority) is not dict or authority.get("repository_head") != expected_head:
        raise ValueError("arm authority HEAD mismatch")
    if sample_corpus.get("schema_version") != 1:
        raise ValueError("sample corpus schema_version must be exact 1")
    if sample_corpus.get("arm") != arm:
        raise ValueError("sample corpus arm mismatch")
    sample_authority = sample_corpus.get("authority")
    if type(sample_authority) is not dict or sample_authority.get("head") != expected_head:
        raise ValueError("sample corpus authority HEAD mismatch")
    prestate = arm_result.get("prestate")
    if type(prestate) is not dict:
        raise ValueError("arm result lacks prestate")
    prestate_sha256 = _sha256(
        prestate.get("incumbent_sha256"),
        field="prestate.incumbent_sha256",
    )
    if sample_corpus.get("prestate_sha256") != prestate_sha256:
        raise ValueError("sample corpus prestate mismatch")
    result_ledger = arm_result.get("ledger")
    if type(result_ledger) is not dict:
        raise ValueError("arm result lacks ledger summary")
    for key in ("status", "event_count", "event_counts", "tail_hash"):
        if result_ledger.get(key) != ledger_replay.get(key):
            raise ValueError(f"arm result ledger summary drift: {key}")
    expected_applied = ledger_replay["event_counts"].get("APPLIED", 0)
    if result_ledger.get("applied") != expected_applied:
        raise ValueError("arm result APPLIED count differs from ledger")
    return str(arm), prestate_sha256


def verify(
    *,
    arm_result: dict[str, Any],
    sample_corpus: dict[str, Any],
    ledger_replay: dict[str, Any],
    mandatory_instances: object,
    candidate_placements: dict[str, Any],
    frozen_assignment: dict[str, Any] | None,
    expected_head: str = EXPECTED_HEAD,
) -> dict[str, object]:
    """Verify semantic inputs already decoded from strict JSON."""

    if type(arm_result) is not dict or type(sample_corpus) is not dict:
        raise ValueError("arm result and sample corpus must be objects")
    if type(ledger_replay) is not dict or ledger_replay.get("status") != "complete":
        raise ValueError("ledger replay must be complete")
    arm, prestate_sha256 = _validate_result_envelope(
        arm_result,
        sample_corpus,
        ledger_replay,
        expected_head=expected_head,
    )
    mandatory, groups = _mandatory_groups(mandatory_instances)
    facilities = {str(item["facility_type"]) for item in mandatory.values()}
    candidates = _candidate_indices(candidate_placements, facilities)
    prestate, by_group, ghost = _validate_incumbent(
        arm_result,
        mandatory,
        groups,
        candidates,
    )
    if prestate["incumbent_sha256"] != prestate_sha256:
        raise ValueError("prestate identity drift after incumbent replay")

    samples = sample_corpus.get("samples")
    if type(samples) is not list:
        raise ValueError("sample corpus samples must be an array")
    injection = arm_result.get("injection")
    if type(injection) is not dict:
        raise ValueError("arm result lacks injection record")
    compiled_raw = injection.get("compiled_records")
    if type(compiled_raw) is not list:
        raise ValueError("compiled_records must be an array")
    if injection.get("compiled_observed") != len(compiled_raw):
        raise ValueError("compiled_observed count drift")
    if injection.get("arithmetic_sample_count") != len(samples):
        raise ValueError("arithmetic_sample_count drift")

    compiled: dict[tuple[str, str], dict[str, Any]] = {}
    for raw_record in compiled_raw:
        if type(raw_record) is not dict:
            raise ValueError("compiled record is not an object")
        rebuilt = _rebuild_plan(raw_record)
        key = (str(rebuilt["cut_id"]), str(rebuilt["family"]))
        if key in compiled:
            raise ValueError(f"duplicate compiled cut identity {key}")
        compiled[key] = rebuilt

    applied_events = [event for event in ledger_replay["events"] if event.get("event") == "APPLIED"]
    assignment = _literal_assignment(
        frozen_assignment,
        prestate_sha256=prestate_sha256,
        required=bool(samples or applied_events),
    )
    if not samples and not applied_events:
        return {
            "schema_version": 2,
            "checker": "independent_arithmetic_check_v2",
            "status": "NO_APPLIED_CUT",
            "arm": arm,
            "head": expected_head,
            "prestate_sha256": prestate_sha256,
            "mandatory_instance_count": len(mandatory),
            "mandatory_group_count": len(groups),
            "checked_sample_count": 0,
            "applied_join_count": 0,
            "ledger": {key: ledger_replay[key] for key in ("status", "event_count", "event_counts", "tail_hash")},
            "checks": [
                "strict_geometry_rebuilt",
                "ledger_chain_and_seal_replayed",
                "zero_applied_join_confirmed",
            ],
        }
    if len(samples) != len(applied_events):
        raise ValueError("captured sample count differs from ledger APPLIED count")

    applied_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for event in applied_events:
        key = (
            _nonempty_str(event.get("cut_id"), field="APPLIED.cut_id"),
            _nonempty_str(event.get("family"), field="APPLIED.family"),
        )
        if key in applied_by_key:
            raise ValueError(f"duplicate APPLIED cut identity {key}")
        applied_by_key[key] = event

    rect_idx, incumbent_ghost_digest = _ghost_digest(arm_result, ghost)
    checked: list[dict[str, Any]] = []
    seen_samples: set[tuple[str, str]] = set()
    for offset, sample in enumerate(samples):
        if type(sample) is not dict:
            raise ValueError(f"sample {offset} is not an object")
        key = (
            _nonempty_str(sample.get("cut_id"), field="sample.cut_id"),
            _nonempty_str(sample.get("family"), field="sample.family"),
        )
        if key in seen_samples:
            raise ValueError(f"duplicate sample identity {key}")
        seen_samples.add(key)
        record = compiled.get(key)
        event = applied_by_key.get(key)
        if record is None or event is None:
            raise ValueError(f"sample lacks compiled/APPLIED join: {key}")
        for field in ("operation", "parameters", "plan_digest", "compiled_digest"):
            if sample.get(field) != record[field]:
                raise ValueError(f"sample/compiled mismatch for {key}: {field}")
        if event.get("semantic_fingerprint") != record["semantic_fingerprint"]:
            raise ValueError("APPLIED semantic fingerprint mismatch")
        if event.get("plan_digest") != record["plan_digest"]:
            raise ValueError("APPLIED plan digest mismatch")
        receipt = event.get("receipt")
        if type(receipt) is not dict:
            raise ValueError("APPLIED event lacks receipt object")
        if (
            receipt.get("apply_completed") is not True
            or type(receipt.get("count_delta")) is not int
            or receipt["count_delta"] <= 0
        ):
            raise ValueError("APPLIED receipt lacks a positive completed apply")
        if receipt.get("snapshot_digest") != record["snapshot_digest"]:
            raise ValueError("APPLIED snapshot digest mismatch")
        if receipt.get("master_domain_family") != record["family"]:
            raise ValueError("APPLIED master-domain family mismatch")

        scope = record["model_scope"]
        recorded_lits = receipt.get("condition_lits")
        sample_lits = sample.get("enforcement_literals")
        if type(recorded_lits) is not list or type(sample_lits) is not list:
            raise ValueError("condition/enforcement literals must be arrays")
        if scope["ghost_policy"] == "agnostic":
            if (
                scope["ghost_rect_digest"] is not None
                or receipt.get("rect_idx") is not None
                or receipt.get("ghost_rect_digest") is not None
                or recorded_lits
                or sample_lits
            ):
                raise ValueError("agnostic scope carries enforcement material")
        else:
            if (
                scope["ghost_rect_digest"] != incumbent_ghost_digest
                or receipt.get("ghost_rect_digest") != incumbent_ghost_digest
                or receipt.get("rect_idx") != rect_idx
                or len(recorded_lits) != 1
                or len(sample_lits) != 1
            ):
                raise ValueError("bound scope does not bind the frozen ghost")

        independently_replayed_lits: list[dict[str, object]] = []
        values: list[int] = []
        for lit_offset, ledger_lit in enumerate(recorded_lits):
            if type(ledger_lit) is not dict or set(ledger_lit) != {"index", "name"}:
                raise ValueError("APPLIED condition literal has invalid fields")
            index = _exact_int(ledger_lit["index"], field="condition_lit.index")
            name = _nonempty_str(ledger_lit["name"], field="condition_lit.name")
            assigned = assignment.get(index)
            if assigned is None or assigned["name"] != name:
                raise ValueError("condition literal lacks stable assignment join")
            expected_sample_lit = sample_lits[lit_offset]
            if (
                type(expected_sample_lit) is not dict
                or expected_sample_lit.get("index") != index
                or expected_sample_lit.get("name") != name
            ):
                raise ValueError("sample enforcement literal identity mismatch")
            value = int(assigned["value"])
            independently_replayed_lits.append({"index": index, "name": name, "value": value})
            values.append(value)
        contributions, lhs, rhs = _independent_arithmetic(record, by_group)
        active = all(value == 1 for value in values)
        violated = bool(active and lhs > rhs)
        if sample.get("contributions") != contributions:
            raise ValueError("captured contributions differ from independent replay")
        if sample.get("lhs") != lhs or sample.get("rhs") != rhs:
            raise ValueError("captured inequality differs from independent replay")
        if sample.get("enforcement_literals") != independently_replayed_lits:
            raise ValueError("captured enforcement values differ from assignment")
        if sample.get("enforcement_values") != values:
            raise ValueError("captured enforcement_values differ from assignment")
        if sample.get("active") is not active or sample.get("violated") is not violated:
            raise ValueError("captured active/violated flags differ from replay")
        checked.append(
            {
                "cut_id": key[0],
                "family": key[1],
                "operation": record["operation"],
                "lhs": lhs,
                "rhs": rhs,
                "active": active,
                "violated": violated,
                "plan_digest": record["plan_digest"],
                "compiled_digest": record["compiled_digest"],
                "semantic_fingerprint": record["semantic_fingerprint"],
                "ledger_seq": event["seq"],
            }
        )
    if set(applied_by_key) != seen_samples:
        raise ValueError("not every APPLIED event has a captured sample")
    violated_rows = sorted(
        (row for row in checked if row["violated"]),
        key=lambda row: (row["family"], row["cut_id"]),
    )
    if not violated_rows:
        raise ValueError("no active violated APPLIED inequality was reproduced")
    return {
        "schema_version": 2,
        "checker": "independent_arithmetic_check_v2",
        "status": "PASS_APPLIED_VIOLATION",
        "arm": arm,
        "head": expected_head,
        "prestate_sha256": prestate_sha256,
        "mandatory_instance_count": len(mandatory),
        "mandatory_group_count": len(groups),
        "checked_sample_count": len(checked),
        "applied_join_count": len(applied_events),
        "violated_sample_count": len(violated_rows),
        "selected": violated_rows[0],
        "ledger": {key: ledger_replay[key] for key in ("status", "event_count", "event_counts", "tail_hash")},
        "checks": [
            "strict_geometry_rebuilt",
            "typed_plan_and_compiled_digests_rebuilt",
            "ledger_chain_and_seal_replayed",
            "compiled_applied_assignment_join_replayed",
            "active_violated_inequality_reproduced",
        ],
    }


def build_receipt(
    *,
    arm_result_path: Path,
    sample_corpus_path: Path,
    ledger_segment_path: Path,
    mandatory_instances_path: Path,
    candidate_placements_path: Path,
    frozen_assignment_path: Path | None = None,
    history_manifest_path: Path | None = None,
    expected_head: str = EXPECTED_HEAD,
) -> dict[str, object]:
    """Read byte identities, replay inputs, and return one success receipt."""

    inputs: dict[str, dict[str, object]] = {}
    arm_any, _arm_raw, inputs["arm_result"] = _read_json(arm_result_path)
    sample_any, _sample_raw, inputs["sample_corpus"] = _read_json(sample_corpus_path)
    mandatory_any, _mandatory_raw, inputs["mandatory_instances"] = _read_json(mandatory_instances_path)
    candidates_any, _candidates_raw, inputs["candidate_placements"] = _read_json(candidate_placements_path)
    ledger_raw = _read_regular(ledger_segment_path)
    inputs["ledger_segment"] = _identity(ledger_segment_path, ledger_raw)
    frozen_any: dict[str, Any] | None = None
    if frozen_assignment_path is not None:
        frozen_payload, _frozen_raw, inputs["frozen_assignment"] = _read_json(frozen_assignment_path)
        if type(frozen_payload) is not dict:
            raise ValueError("frozen assignment root must be an object")
        frozen_any = frozen_payload
    if history_manifest_path is not None:
        manifest, _manifest_raw, inputs["history_manifest"] = _read_json(history_manifest_path)
        if type(manifest) is not dict:
            raise ValueError("history manifest root must be an object")
        if manifest.get("repository_head") != expected_head:
            raise ValueError("history manifest repository HEAD mismatch")
    if type(arm_any) is not dict or type(sample_any) is not dict or type(candidates_any) is not dict:
        raise ValueError("arm, sample, and candidates roots must be objects")
    ledger_replay = _replay_ledger(ledger_raw)
    recorded_sample = arm_any.get("arithmetic_sample_corpus")
    if type(recorded_sample) is not dict:
        raise ValueError("arm result lacks arithmetic sample identity")
    if (
        recorded_sample.get("size") != inputs["sample_corpus"]["size"]
        or recorded_sample.get("sha256") != inputs["sample_corpus"]["sha256"]
    ):
        raise ValueError("arm result sample-corpus byte identity mismatch")
    recorded_ledger = arm_any.get("ledger")
    if type(recorded_ledger) is not dict:
        raise ValueError("arm result lacks ledger identity")
    if Path(str(recorded_ledger.get("path"))).absolute() != _absolute(ledger_segment_path):
        raise ValueError("arm result ledger path differs from supplied segment")
    authority = arm_any.get("authority")
    authority_ids = authority.get("identities") if type(authority) is dict else None
    candidate_id = authority_ids.get("candidate_placements") if type(authority_ids) is dict else None
    if type(candidate_id) is not dict or (
        candidate_id.get("size") != inputs["candidate_placements"]["size"]
        or candidate_id.get("sha256") != inputs["candidate_placements"]["sha256"]
    ):
        raise ValueError("candidate placements differ from arm authority")
    semantic = verify(
        arm_result=arm_any,
        sample_corpus=sample_any,
        ledger_replay=ledger_replay,
        mandatory_instances=mandatory_any,
        candidate_placements=candidates_any,
        frozen_assignment=frozen_any,
        expected_head=expected_head,
    )
    semantic["input_identities"] = inputs
    semantic["checker_identity"] = _identity(Path(__file__))
    return semantic


def _best_effort_identity(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    try:
        return _identity(path)
    except Exception as exc:  # noqa: BLE001 - diagnostic only
        return {
            "path": str(_absolute(path)),
            "identity_error": f"{type(exc).__name__}: {exc}",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm-result", type=Path, required=True)
    parser.add_argument("--sample-corpus", type=Path, required=True)
    parser.add_argument("--ledger-segment", type=Path, required=True)
    parser.add_argument("--mandatory-instances", type=Path, required=True)
    parser.add_argument("--candidate-placements", type=Path, required=True)
    parser.add_argument("--frozen-assignment", type=Path)
    parser.add_argument("--history-manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-head", default=EXPECTED_HEAD)
    args = parser.parse_args()
    try:
        receipt = build_receipt(
            arm_result_path=args.arm_result,
            sample_corpus_path=args.sample_corpus,
            ledger_segment_path=args.ledger_segment,
            mandatory_instances_path=args.mandatory_instances,
            candidate_placements_path=args.candidate_placements,
            frozen_assignment_path=args.frozen_assignment,
            history_manifest_path=args.history_manifest,
            expected_head=args.expected_head,
        )
        exit_code = 0
    except Exception as exc:  # noqa: BLE001 - fail-closed receipt
        paths = {
            "arm_result": args.arm_result,
            "sample_corpus": args.sample_corpus,
            "ledger_segment": args.ledger_segment,
            "mandatory_instances": args.mandatory_instances,
            "candidate_placements": args.candidate_placements,
            "frozen_assignment": args.frozen_assignment,
            "history_manifest": args.history_manifest,
        }
        receipt = {
            "schema_version": 2,
            "checker": "independent_arithmetic_check_v2",
            "status": "FAIL",
            "error": f"{type(exc).__name__}: {exc}",
            "checker_identity": _best_effort_identity(Path(__file__)),
            "input_identities": {
                name: identity for name, path in paths.items() if (identity := _best_effort_identity(path)) is not None
            },
        }
        exit_code = 2
    _write_exclusive(args.output, receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
