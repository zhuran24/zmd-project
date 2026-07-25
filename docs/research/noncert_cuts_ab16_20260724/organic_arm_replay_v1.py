#!/usr/bin/env python3
"""Independent replay of one prospective non-certified-cuts organic arm.

This verifier intentionally does not import the arm runner, experiment
contract, cut ledger implementation, or cut framework.  It replays their
published byte formats independently:

* a complete ledger and compile/attach journal establish event presence or
  absence;
* every branch requires a separate cut-free fixed-incumbent replay PASS; and
* every APPLIED event must join one compiled journal record and one concrete
  binary ``CpModelProto`` constraint evaluated on the bound solution vector.

The result is research telemetry only.  It cannot prove family-global
soundness, a mathematical bound, a witness, runtime effect, or production
certification.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any

from google.protobuf.message import DecodeError
from google.protobuf import text_format
from ortools.sat import cp_model_pb2
from ortools.sat.python import cp_model


RESULT_SCHEMA = "noncert-cuts-ab16-organic-arm-result-v1"
JOURNAL_SCHEMA = "noncert-cuts-ab16-compile-attach-journal-v1"
LEDGER_SCHEMA = "cut-ledger-v1"
CUT_FREE_SCHEMA = "noncert-cuts-ab16-fixed-assignment-replay-v1"
CORPUS_SCHEMA = "noncert-cuts-ab16-concrete-inequality-corpus-v1"
ASSIGNMENT_SCHEMA = "noncert-cuts-ab16-applied-assignment-v1"
RECEIPT_SCHEMA = "noncert-cuts-ab16-independent-organic-arm-replay-v1"
CORPUS_PURPOSE = "independent_concrete_applied_inequality_join"
ASSIGNMENT_PURPOSE = "organic_cut_attach_assignment"
RECEIPT_PURPOSE = "independent_organic_arm_event_and_arithmetic_replay"

ORGANIC_NONACTIVATION = "ORGANIC_NONACTIVATION"
NO_ORGANIC_APPLIED_CUT = "NO_ORGANIC_APPLIED_CUT"
ORGANIC_APPLIED = "ORGANIC_APPLIED"

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
LEDGER_EVENTS = frozenset(
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
CUT_LEDGER_EVENTS = LEDGER_EVENTS - {
    "GENESIS",
    "EPOCH_CLOSED",
    "SEGMENT_SEAL",
}
ALLOWED_OPERATIONS = frozenset(
    {
        "power_pose_exclusion",
        "region_capacity_le",
        "shape_packing_hall_le",
    }
)
INT64_MIN = -(2**63)
PLAN_DIGEST_PREFIX = b"zmd.constraint-plan.v1:"
MODEL_SCOPE_DIGEST_PREFIX = b"zmd.model-scope.v1:"
COMPILED_CUT_DIGEST_PREFIX = b"zmd.compiled-cut.v1:"
MAX_JSON_BYTES = 128 * 1024 * 1024
MAX_MODEL_BYTES = 2 * 1024 * 1024 * 1024


class ReplayError(RuntimeError):
    """The supplied arm evidence failed closed."""


@dataclass(frozen=True)
class Snapshot:
    data: bytes
    identity: dict[str, object]


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _compact_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _stat_signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_uid,
        value.st_gid,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _reject_symlink_chain(path: Path, *, missing_leaf: bool = False) -> None:
    absolute = _absolute(path)
    current = Path(absolute.anchor)
    for index, part in enumerate(absolute.parts[1:]):
        current /= part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            if missing_leaf and index == len(absolute.parts[1:]) - 1:
                return
            raise ReplayError(f"path component is missing: {current}") from None
        if stat.S_ISLNK(metadata.st_mode):
            raise ReplayError(f"symlink path component rejected: {current}")


def snapshot_regular(
    path: Path | str,
    *,
    max_bytes: int = MAX_JSON_BYTES,
) -> Snapshot:
    absolute = _absolute(path)
    _reject_symlink_chain(absolute.parent)
    parent_fd = os.open(
        absolute.parent,
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        descriptor = os.open(
            absolute.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
    except OSError as exc:
        os.close(parent_fd)
        raise ReplayError(f"input open failed: {absolute}") from exc
    try:
        before_fd = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before_fd.st_mode)
            or before_fd.st_nlink != 1
            or before_fd.st_size < 0
            or before_fd.st_size > max_bytes
        ):
            raise ReplayError(f"input is not one bounded regular file: {absolute}")
        chunks: list[bytes] = []
        remaining = before_fd.st_size
        while remaining:
            block = os.read(descriptor, min(1 << 20, remaining))
            if not block:
                raise ReplayError(f"input truncated during read: {absolute}")
            chunks.append(block)
            remaining -= len(block)
        if os.read(descriptor, 1):
            raise ReplayError(f"input grew during read: {absolute}")
        after_fd = os.fstat(descriptor)
        if _stat_signature(before_fd) != _stat_signature(after_fd):
            raise ReplayError(f"input changed during read: {absolute}")
    finally:
        os.close(descriptor)
        os.close(parent_fd)
    raw = b"".join(chunks)
    return Snapshot(
        data=raw,
        identity={
            "path": str(absolute),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        },
    )


def _pairs_unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ReplayError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _strict_json(
    raw: bytes,
    label: str,
    *,
    canonical: bool,
    allow_float: bool = False,
) -> object:
    def reject_float(value: str) -> object:
        if allow_float:
            parsed = float(value)
            if parsed != parsed or parsed in {float("inf"), float("-inf")}:
                raise ReplayError(f"{label}: non-finite float")
            return parsed
        raise ReplayError(f"{label}: float is forbidden")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs_unique,
            parse_constant=lambda token: (_ for _ in ()).throw(ReplayError(f"{label}: invalid constant {token}")),
            parse_float=reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReplayError(f"{label}: invalid JSON") from exc
    if canonical and canonical_json(value) != raw:
        raise ReplayError(f"{label}: noncanonical JSON bytes")
    return value


def _exact_keys(
    value: object,
    expected: set[str],
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ReplayError(f"{label}: key set drifted")
    return value


def _identity(value: object, label: str) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {"path", "sha256", "size_bytes"},
        label,
    )
    if (
        type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
    ):
        raise ReplayError(f"{label}: malformed identity")
    return record


def _replay_identity(
    value: object,
    label: str,
    *,
    max_bytes: int = MAX_JSON_BYTES,
) -> Snapshot:
    expected = _identity(value, label)
    current = snapshot_regular(expected["path"], max_bytes=max_bytes)
    if current.identity != expected:
        raise ReplayError(f"{label}: detached identity drifted")
    return current


def _utc(value: object, label: str) -> None:
    if type(value) is not str:
        raise ReplayError(f"{label}: timestamp is not a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReplayError(f"{label}: invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise ReplayError(f"{label}: timestamp lacks timezone")


def _parse_ledger(snapshot: Snapshot) -> list[Mapping[str, Any]]:
    raw = snapshot.data
    if not raw or not raw.endswith(b"\n"):
        raise ReplayError("ledger is not newline-terminated")
    lines = raw[:-1].split(b"\n")
    previous = "0" * 64
    events: list[Mapping[str, Any]] = []
    writer: object = None
    scope: object = None
    for sequence, line in enumerate(lines):
        value = _strict_json(
            line,
            f"ledger line {sequence}",
            canonical=False,
            allow_float=True,
        )
        if not isinstance(value, Mapping) or _compact_json(value) != line:
            raise ReplayError(f"ledger line {sequence}: noncanonical event")
        if (
            value.get("schema_version") != LEDGER_SCHEMA
            or value.get("seq") != sequence
            or value.get("prev_event_hash") != previous
            or value.get("event") not in LEDGER_EVENTS
        ):
            raise ReplayError(f"ledger line {sequence}: chain/schema drift")
        if sequence == 0 and value["event"] != "GENESIS":
            raise ReplayError("ledger does not begin with GENESIS")
        if events and events[-1]["event"] == "SEGMENT_SEAL":
            raise ReplayError("ledger contains data after SEGMENT_SEAL")
        if sequence == 0:
            writer = value.get("writer_id")
            scope = value.get("scope_id")
            if type(writer) is not str or not writer or type(scope) is not str or not scope:
                raise ReplayError("ledger writer/scope identity is malformed")
        elif value.get("writer_id") != writer or value.get("scope_id") != scope:
            raise ReplayError("ledger writer/scope identity drifted")
        previous = hashlib.sha256(line).hexdigest()
        events.append(value)
    if not events or events[-1]["event"] != "SEGMENT_SEAL":
        raise ReplayError("ledger is not a complete sealed segment")
    return events


def _parse_journal(snapshot: Snapshot) -> list[Mapping[str, Any]]:
    raw = snapshot.data
    if not raw or not raw.endswith(b"\n"):
        raise ReplayError("compile/attach journal is not newline-terminated")
    previous = "0" * 64
    events: list[Mapping[str, Any]] = []
    for sequence, line in enumerate(raw[:-1].split(b"\n")):
        value = _strict_json(
            line,
            f"journal line {sequence}",
            canonical=False,
        )
        record = _exact_keys(
            value,
            {
                "event",
                "payload",
                "prev_event_sha256",
                "schema_version",
                "seq",
            },
            f"journal line {sequence}",
        )
        if (
            record["schema_version"] != JOURNAL_SCHEMA
            or record["seq"] != sequence
            or record["prev_event_sha256"] != previous
            or type(record["event"]) is not str
            or type(record["payload"]) is not dict
            or _compact_json(record) != line
        ):
            raise ReplayError(f"journal line {sequence}: chain/schema drift")
        if events and events[-1]["event"] == "JOURNAL_SEAL":
            raise ReplayError("compile/attach journal contains data after its seal")
        previous = hashlib.sha256(line).hexdigest()
        events.append(record)
    if not events or events[-1]["event"] != "JOURNAL_SEAL":
        raise ReplayError("compile/attach journal lacks its terminal seal")
    return events


def _event_counts(
    events: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        name = event["event"]
        assert isinstance(name, str)
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def _validate_result(
    value: object,
    *,
    result_identity: Mapping[str, object],
) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "arm",
            "authority_identities",
            "authorizations",
            "campaign_id",
            "cut_activity",
            "enabled_families",
            "evidence",
            "fresh_process_required",
            "incumbent_export",
            "raw_metrics",
            "raw_proof_summary",
            "raw_solver_status",
            "runtime_wall_monotonic_ns",
            "schema_version",
            "selection_nonce",
            "slot",
            "status",
            "workers",
        },
        "organic arm result",
    )
    if (
        record["schema_version"] != RESULT_SCHEMA
        or record["status"] != "RAW_ARM_OBSERVATION_COMPLETE"
        or record["arm"] not in {"control", "treatment"}
        or record["fresh_process_required"] is not True
        or record["workers"] != 1
        or type(record["workers"]) is not int
        or type(record["runtime_wall_monotonic_ns"]) is not int
        or record["runtime_wall_monotonic_ns"] < 0
        or type(record["raw_solver_status"]) is not str
        or not record["raw_solver_status"]
        or type(record["slot"]) is not str
        or type(record["selection_nonce"]) is not str
        or type(record["enabled_families"]) is not list
        or type(record["raw_metrics"]) is not dict
        or type(record["raw_proof_summary"]) is not dict
    ):
        raise ReplayError("organic arm result scalar semantics drifted")
    authorizations = _exact_keys(
        record["authorizations"],
        {
            "global_claim_authorized",
            "mathematical_claim_authorized",
            "organic_runtime_effect_authorized",
            "production_certified_authorized",
        },
        "result authorizations",
    )
    if any(value is not False for value in authorizations.values()):
        raise ReplayError("organic arm result upgrades an authorization")
    activity = _exact_keys(
        record["cut_activity"],
        {"applied", "compiled", "generated"},
        "result cut activity",
    )
    if (
        any(type(activity[field]) is not int for field in activity)
        or not 0 <= activity["applied"] <= activity["compiled"] <= activity["generated"]
    ):
        raise ReplayError("result cut activity is invalid")
    evidence = _exact_keys(
        record["evidence"],
        {
            "compile_attach_journal_identity",
            "cut_ledger_identity",
            "cut_ledger_status",
            "journal_event_counts",
            "ledger_event_counts",
        },
        "result evidence",
    )
    _identity(
        evidence["compile_attach_journal_identity"],
        "result journal identity",
    )
    _identity(evidence["cut_ledger_identity"], "result ledger identity")
    if (
        evidence["cut_ledger_status"] != "complete"
        or type(evidence["journal_event_counts"]) is not dict
        or type(evidence["ledger_event_counts"]) is not dict
    ):
        raise ReplayError("result evidence summary is incomplete")
    authorities = record["authority_identities"]
    if not isinstance(authorities, Mapping) or "baseline_incumbent" not in authorities:
        raise ReplayError("result lacks baseline incumbent authority")
    _identity(
        authorities["baseline_incumbent"],
        "result baseline incumbent identity",
    )
    incumbent = _exact_keys(
        record["incumbent_export"],
        {
            "incumbent_identity",
            "present",
            "solution_vector_identity",
        },
        "result incumbent export",
    )
    if incumbent["present"] is True:
        _identity(incumbent["incumbent_identity"], "result incumbent export")
        _identity(
            incumbent["solution_vector_identity"],
            "result solution vector",
        )
    elif (
        incumbent["present"] is not False
        or incumbent["incumbent_identity"] is not None
        or incumbent["solution_vector_identity"] is not None
    ):
        raise ReplayError("result incumbent absence branch is malformed")
    del result_identity
    return record


def _validate_cut_free(
    value: object,
    *,
    arm_incumbent_identity: Mapping[str, object],
) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "all_fixed_equalities_added",
            "assignment_count",
            "conflicting_assignment_count",
            "created_at_utc",
            "fixed_assignment_count",
            "global_claim_authorized",
            "incumbent_identity",
            "incumbent_sha256",
            "legacy_control_used_as_truth_root",
            "metadata_identity",
            "model_constraint_count",
            "model_identity",
            "model_validation_errors",
            "model_variable_count",
            "purpose",
            "replay_errors",
            "replay_tool_identity",
            "schema_version",
            "solution_matches_fixed_assignments",
            "solver_status",
            "status",
            "unresolved_assignment_count",
            "verdict",
        },
        "cut-free replay receipt",
    )
    _utc(record["created_at_utc"], "cut-free replay created_at_utc")
    for field in (
        "incumbent_identity",
        "metadata_identity",
        "model_identity",
        "replay_tool_identity",
    ):
        _identity(record[field], f"cut-free {field}")
    if (
        record["schema_version"] != CUT_FREE_SCHEMA
        or record["purpose"] != "strict_ab16_incumbent_fixed_assignment_replay"
        or record["status"] != "PASS"
        or record["verdict"] != "INCUMBENT_FIXED_ASSIGNMENT_REPLAY_PASS"
        or record["solver_status"] != "OPTIMAL"
        or record["incumbent_identity"] != arm_incumbent_identity
        or type(record["incumbent_sha256"]) is not str
        or SHA256_RE.fullmatch(record["incumbent_sha256"]) is None
        or record["all_fixed_equalities_added"] is not True
        or record["solution_matches_fixed_assignments"] is not True
        or record["legacy_control_used_as_truth_root"] is not False
        or record["global_claim_authorized"] is not False
        or record["model_validation_errors"] != []
        or record["replay_errors"] != []
        or any(
            type(record[field]) is not int or record[field] < 0
            for field in (
                "assignment_count",
                "conflicting_assignment_count",
                "fixed_assignment_count",
                "model_constraint_count",
                "model_variable_count",
                "unresolved_assignment_count",
            )
        )
        or record["assignment_count"] != record["fixed_assignment_count"]
        or record["conflicting_assignment_count"] != 0
        or record["unresolved_assignment_count"] != 0
    ):
        raise ReplayError("cut-free fixed-incumbent replay is not a PASS")
    return record


def _parse_model(snapshot: Snapshot, label: str) -> cp_model_pb2.CpModelProto:
    model = cp_model_pb2.CpModelProto()
    try:
        consumed = model.ParseFromString(snapshot.data)
    except DecodeError as exc:
        raise ReplayError(f"{label}: malformed CpModelProto") from exc
    if consumed != len(snapshot.data) or model.SerializeToString(deterministic=True) != snapshot.data:
        raise ReplayError(f"{label}: noncanonical CpModelProto")
    without_unknown = cp_model_pb2.CpModelProto()
    without_unknown.CopyFrom(model)
    without_unknown.DiscardUnknownFields()
    if without_unknown.SerializeToString(deterministic=True) != snapshot.data:
        raise ReplayError(f"{label}: unknown protobuf fields")
    return model


def _canonical_node(value: object) -> object:
    if value is None:
        return ["null"]
    if type(value) is bool:
        return ["bool", value]
    if type(value) is int:
        return ["int", value]
    if type(value) is float:
        return ["float", value]
    if type(value) is str:
        return ["str", value]
    if type(value) is list:
        return ["sequence", [_canonical_node(item) for item in value]]
    if type(value) is dict:
        return [
            "mapping",
            [[key, _canonical_node(value[key])] for key in sorted(value)],
        ]
    raise ReplayError("compiled plan contains a noncanonical parameter type")


def _domain_digest(prefix: bytes, value: object) -> str:
    return hashlib.sha256(prefix + _compact_json(value)).hexdigest()


def _validate_plan_projection(
    plan: Mapping[str, Any],
) -> tuple[str, str]:
    scope = _exact_keys(
        plan["model_scope"],
        {
            "domain_fingerprint",
            "ghost_policy",
            "ghost_rect_digest",
        },
        "compiled model scope",
    )
    if (
        scope["ghost_policy"] not in {"agnostic", "bound"}
        or type(scope["domain_fingerprint"]) is not str
        or not scope["domain_fingerprint"]
        or (scope["ghost_policy"] == "agnostic" and scope["ghost_rect_digest"] is not None)
        or (
            scope["ghost_policy"] == "bound"
            and (type(scope["ghost_rect_digest"]) is not str or SHA256_RE.fullmatch(scope["ghost_rect_digest"]) is None)
        )
    ):
        raise ReplayError("compiled model scope is malformed")
    parameters = plan["parameters"]
    operation = plan["operation"]
    family = plan["family"]
    expected_family = {
        "region_capacity_le": "region_capacity",
        "shape_packing_hall_le": "shape_packing_hall",
        "power_pose_exclusion": "power_hitting_set",
    }[operation]
    if family != expected_family:
        raise ReplayError("compiled plan family/operation pairing drifted")
    if operation == "region_capacity_le":
        params = _exact_keys(
            parameters,
            {"capacity", "group_cell_weights"},
            "region-capacity parameters",
        )
        weights = params["group_cell_weights"]
        if (
            type(params["capacity"]) is not int
            or params["capacity"] < 0
            or type(weights) is not dict
            or not weights
            or any(
                type(group) is not str or not group or type(weight) is not int or weight <= 0
                for group, weight in weights.items()
            )
        ):
            raise ReplayError("region-capacity parameters are malformed")
    elif operation == "shape_packing_hall_le":
        params = _exact_keys(
            parameters,
            {"capacity", "group_id", "region_kind"},
            "shape-packing parameters",
        )
        if (
            type(params["capacity"]) is not int
            or params["capacity"] < 0
            or type(params["group_id"]) is not str
            or not params["group_id"]
            or params["region_kind"] not in {"left_baseline", "bottom_baseline"}
        ):
            raise ReplayError("shape-packing parameters are malformed")
    else:
        params = _exact_keys(
            parameters,
            {"blocked_cells_digest", "group_id", "pose_id"},
            "power-exclusion parameters",
        )
        if (
            type(params["blocked_cells_digest"]) is not str
            or SHA256_RE.fullmatch(params["blocked_cells_digest"]) is None
            or any(type(params[field]) is not str or not params[field] for field in ("group_id", "pose_id"))
        ):
            raise ReplayError("power-exclusion parameters are malformed")
    scope_projection = {
        "domain_fingerprint": scope["domain_fingerprint"],
        "ghost_policy": scope["ghost_policy"],
        "ghost_rect_digest": scope["ghost_rect_digest"],
        "schema_version": 1,
    }
    expected_plan_digest = _domain_digest(
        PLAN_DIGEST_PREFIX,
        {
            "family": family,
            "model_scope": _canonical_node(scope_projection),
            "operation": operation,
            "parameters": _canonical_node(parameters),
            "schema_version": plan["schema_version"],
            "semantic_fingerprint": plan["semantic_fingerprint"],
        },
    )
    expected_scope_digest = _domain_digest(
        MODEL_SCOPE_DIGEST_PREFIX,
        scope_projection,
    )
    return expected_plan_digest, expected_scope_digest


def _compiled_records(
    journal_events: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    result: list[Mapping[str, Any]] = []
    for event in journal_events:
        if event["event"] != "COMPILED_CUT":
            continue
        payload = _exact_keys(
            event["payload"],
            {
                "compiled_digest",
                "cut_id",
                "hook_id",
                "plan",
                "proof_digest",
                "scope_digest",
                "snapshot_digest",
            },
            "compiled journal payload",
        )
        plan = _exact_keys(
            payload["plan"],
            {
                "digest",
                "family",
                "model_scope",
                "operation",
                "parameters",
                "schema_version",
                "semantic_fingerprint",
            },
            "compiled plan",
        )
        if (
            any(
                type(payload[field]) is not str or SHA256_RE.fullmatch(payload[field]) is None
                for field in (
                    "compiled_digest",
                    "proof_digest",
                    "scope_digest",
                    "snapshot_digest",
                )
            )
            or type(payload["cut_id"]) is not str
            or not payload["cut_id"]
            or type(payload["hook_id"]) is not int
            or payload["hook_id"] < 0
            or type(plan["digest"]) is not str
            or SHA256_RE.fullmatch(plan["digest"]) is None
            or type(plan["semantic_fingerprint"]) is not str
            or SHA256_RE.fullmatch(plan["semantic_fingerprint"]) is None
            or plan["operation"] not in ALLOWED_OPERATIONS
            or type(plan["family"]) is not str
            or type(plan["parameters"]) is not dict
            or type(plan["model_scope"]) is not dict
            or type(plan["schema_version"]) is not int
            or plan["schema_version"] != 1
        ):
            raise ReplayError("compiled journal record is malformed")
        expected_plan_digest, expected_scope_digest = _validate_plan_projection(plan)
        expected_compiled_digest = _domain_digest(
            COMPILED_CUT_DIGEST_PREFIX,
            {
                "cut_id": payload["cut_id"],
                "plan_digest": expected_plan_digest,
                "proof_digest": payload["proof_digest"],
                "scope_digest": expected_scope_digest,
                "snapshot_digest": payload["snapshot_digest"],
            },
        )
        if (
            plan["digest"] != expected_plan_digest
            or payload["scope_digest"] != expected_scope_digest
            or payload["compiled_digest"] != expected_compiled_digest
        ):
            raise ReplayError("compiled plan/scope/cut digest differs from independent replay")
        result.append(payload)
    return result


def _applied_events(
    ledger_events: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    result: list[Mapping[str, Any]] = []
    for event in ledger_events:
        if event["event"] != "APPLIED":
            continue
        receipt = _exact_keys(
            event.get("receipt"),
            {
                "apply_completed",
                "condition_lits",
                "count_delta",
                "ghost_rect_digest",
                "master_domain_family",
                "rect_idx",
                "snapshot_digest",
            },
            "APPLIED receipt",
        )
        condition_lits = receipt["condition_lits"]
        if (
            type(event.get("cut_id")) is not str
            or not event["cut_id"]
            or type(event.get("family")) is not str
            or type(event.get("plan_digest")) is not str
            or SHA256_RE.fullmatch(event["plan_digest"]) is None
            or type(event.get("semantic_fingerprint")) is not str
            or SHA256_RE.fullmatch(event["semantic_fingerprint"]) is None
            or receipt["apply_completed"] is not True
            or receipt["count_delta"] != 1
            or type(receipt["count_delta"]) is not int
            or type(condition_lits) is not list
        ):
            raise ReplayError("APPLIED ledger event is malformed")
        seen_indices: set[int] = set()
        for literal in condition_lits:
            item = _exact_keys(
                literal,
                {"index", "name"},
                "APPLIED condition literal",
            )
            if (
                type(item["index"]) is not int
                or item["index"] < 0
                or item["index"] in seen_indices
                or type(item["name"]) is not str
            ):
                raise ReplayError("APPLIED condition literal is malformed")
            seen_indices.add(item["index"])
        result.append(event)
    return result


def _replay_cut_lineage(
    *,
    ledger_events: Sequence[Mapping[str, Any]],
    compiled: Sequence[Mapping[str, Any]],
    applied: Sequence[Mapping[str, Any]],
    enabled_families: Sequence[str],
) -> dict[str, object]:
    """Join every compiled/applied cut to one allowed generated cut."""

    if (
        type(enabled_families) is not list
        or any(type(family) is not str for family in enabled_families)
        or len(set(enabled_families)) != len(enabled_families)
    ):
        raise ReplayError("enabled family authority is malformed")
    enabled = set(enabled_families)
    generated_by_cut: dict[str, Mapping[str, Any]] = {}
    for event in ledger_events:
        if event["event"] != "GENERATED":
            continue
        cut_id = event.get("cut_id")
        family = event.get("family")
        if (
            type(cut_id) is not str
            or not cut_id
            or cut_id in generated_by_cut
            or type(family) is not str
            or family not in enabled
        ):
            raise ReplayError("GENERATED event is duplicate, malformed, or outside enabled families")
        generated_by_cut[cut_id] = event
    if not enabled and generated_by_cut:
        raise ReplayError("control arm generated a cut")

    compiled_by_cut: dict[str, Mapping[str, Any]] = {}
    compiled_by_join: dict[
        tuple[str, str, str],
        Mapping[str, Any],
    ] = {}
    for projection in compiled:
        cut_id = projection["cut_id"]
        plan = projection["plan"]
        family = plan["family"]
        generated = generated_by_cut.get(cut_id)
        key = (
            cut_id,
            plan["digest"],
            plan["semantic_fingerprint"],
        )
        if (
            generated is None
            or generated.get("family") != family
            or family not in enabled
            or cut_id in compiled_by_cut
            or key in compiled_by_join
        ):
            raise ReplayError("COMPILED cut lacks one unique allowed GENERATED join")
        compiled_by_cut[cut_id] = projection
        compiled_by_join[key] = projection

    applied_cut_ids: list[str] = []
    used_compiled: set[str] = set()
    for event in applied:
        key = (
            event["cut_id"],
            event["plan_digest"],
            event["semantic_fingerprint"],
        )
        projection = compiled_by_join.get(key)
        if (
            projection is None
            or projection["plan"]["family"] != event["family"]
            or event["family"] not in enabled
            or projection["compiled_digest"] in used_compiled
        ):
            raise ReplayError("APPLIED event lacks one unique allowed COMPILED join")
        used_compiled.add(projection["compiled_digest"])
        applied_cut_ids.append(event["cut_id"])

    generated_ids = list(generated_by_cut)
    compiled_ids = list(compiled_by_cut)
    applied_set = set(applied_cut_ids)
    return {
        "applied_cut_ids": applied_cut_ids,
        "compiled_cut_ids": compiled_ids,
        "compiled_unapplied_cut_ids": [cut_id for cut_id in compiled_ids if cut_id not in applied_set],
        "generated_cut_ids": generated_ids,
        "generated_uncompiled_cut_ids": [cut_id for cut_id in generated_ids if cut_id not in compiled_by_cut],
    }


def _attach_hooks(
    journal_events: Sequence[Mapping[str, Any]],
) -> tuple[dict[int, Mapping[str, Any]], str | None]:
    begins: dict[int, Mapping[str, Any]] = {}
    ends: dict[int, Mapping[str, Any]] = {}
    first_solution_digest: str | None = None
    first_hook_position: int | None = None
    first_solution_position: int | None = None
    for position, event in enumerate(journal_events):
        if event["event"] == "FIRST_ATTACH_SOLUTION_VERIFIED":
            payload = _exact_keys(
                event["payload"],
                {"incumbent_sha256", "solution_entry_count"},
                "first attach solution",
            )
            if (
                first_solution_digest is not None
                or type(payload["incumbent_sha256"]) is not str
                or SHA256_RE.fullmatch(payload["incumbent_sha256"]) is None
                or type(payload["solution_entry_count"]) is not int
                or payload["solution_entry_count"] < 0
            ):
                raise ReplayError("first attach solution record is malformed")
            first_solution_digest = payload["incumbent_sha256"]
            first_solution_position = position
        if event["event"] == "ATTACH_HOOK_BEGIN":
            payload = _exact_keys(
                event["payload"],
                {
                    "attach_env",
                    "hook_id",
                    "iteration",
                    "solution_sha256",
                    "trigger",
                },
                "attach-hook begin",
            )
            hook_id = payload["hook_id"]
            if (
                type(hook_id) is not int
                or hook_id < 0
                or hook_id in begins
                or type(payload["iteration"]) is not int
                or payload["iteration"] <= 0
                or type(payload["solution_sha256"]) is not str
                or SHA256_RE.fullmatch(payload["solution_sha256"]) is None
                or type(payload["trigger"]) is not str
                or not payload["trigger"]
                or (payload["attach_env"] is not None and type(payload["attach_env"]) is not str)
            ):
                raise ReplayError("attach-hook begin is malformed")
            begins[hook_id] = payload
            if first_hook_position is None:
                first_hook_position = position
        elif event["event"] == "ATTACH_HOOK_END":
            payload = _exact_keys(
                event["payload"],
                {
                    "attached_count",
                    "error",
                    "hook_id",
                    "status",
                },
                "attach-hook end",
            )
            hook_id = payload["hook_id"]
            if (
                type(hook_id) is not int
                or hook_id < 0
                or hook_id in ends
                or payload["status"] != "RETURNED"
                or type(payload["attached_count"]) is not int
                or payload["attached_count"] < 0
                or payload["error"] is not None
            ):
                raise ReplayError("attach-hook end is not one clean return")
            ends[hook_id] = payload
    if set(begins) != set(ends):
        raise ReplayError("attach-hook begin/end coverage drifted")
    if begins and (
        first_solution_digest is None
        or first_solution_position is None
        or first_hook_position is None
        or first_solution_position >= first_hook_position
        or begins[min(begins)]["solution_sha256"] != first_solution_digest
    ):
        raise ReplayError("first attach hook is not bound to the verified baseline solution")
    if not begins and first_solution_digest is not None:
        raise ReplayError("first attach solution exists without an attach hook")
    return begins, first_solution_digest


def _constraint_evaluation(
    constraint: cp_model_pb2.ConstraintProto,
    *,
    model: cp_model_pb2.CpModelProto,
    solution: Sequence[int],
    operation: str,
    applied: Mapping[str, Any],
) -> dict[str, object]:
    if constraint.WhichOneof("constraint") != "linear":
        raise ReplayError("mapped APPLIED constraint is not linear")
    linear = constraint.linear
    variables = list(linear.vars)
    coefficients = list(linear.coeffs)
    domain = list(linear.domain)
    enforcement = list(constraint.enforcement_literal)
    if (
        len(variables) != len(coefficients)
        or not variables
        or any(type(index) is not int or index < 0 or index >= len(solution) for index in variables)
        or any(type(coefficient) is not int for coefficient in coefficients)
        or len(domain) < 2
        or len(domain) % 2
    ):
        raise ReplayError("mapped linear constraint body is malformed")
    receipt_indices = [literal["index"] for literal in applied["receipt"]["condition_lits"]]
    if enforcement != receipt_indices:
        raise ReplayError("constraint enforcement literals differ from APPLIED")
    for literal in applied["receipt"]["condition_lits"]:
        index = literal["index"]
        if index >= len(model.variables) or model.variables[index].name != literal["name"]:
            raise ReplayError("APPLIED condition literal name/index differs from model")
    active = True
    for literal in enforcement:
        if literal >= 0:
            active = active and solution[literal] == 1
        else:
            index = -literal - 1
            if index < 0 or index >= len(solution):
                raise ReplayError("negative enforcement literal is out of range")
            active = active and solution[index] == 0
    lhs = sum(
        coefficient * solution[index]
        for index, coefficient in zip(
            variables,
            coefficients,
            strict=True,
        )
    )
    for index, value in enumerate(solution):
        domain_values = list(model.variables[index].domain)
        if (
            len(domain_values) < 2
            or len(domain_values) % 2
            or not any(
                domain_values[offset] <= value <= domain_values[offset + 1]
                for offset in range(0, len(domain_values), 2)
            )
        ):
            raise ReplayError("attach assignment violates a variable domain")
    in_domain = any(domain[index] <= lhs <= domain[index + 1] for index in range(0, len(domain), 2))
    if operation in {"region_capacity_le", "shape_packing_hall_le"} and (len(domain) != 2 or domain[0] != INT64_MIN):
        raise ReplayError("compiled <= operation did not lower as one upper bound")
    if operation == "power_pose_exclusion" and domain != [0, 0]:
        raise ReplayError("power pose exclusion did not lower as equality zero")
    return {
        "active": active,
        "coefficients": coefficients,
        "domain": domain,
        "enforcement_literals": enforcement,
        "lhs": lhs,
        "variable_indices": variables,
        "violated": active and not in_domain,
    }


def _validate_corpus(
    value: object,
    *,
    corpus_identity: Mapping[str, object],
    result_identity: Mapping[str, object],
    ledger_identity: Mapping[str, object],
    journal_identity: Mapping[str, object],
    cut_free_identity: Mapping[str, object],
    result: Mapping[str, Any],
    applied: Sequence[Mapping[str, Any]],
    compiled: Sequence[Mapping[str, Any]],
    attach_hooks: Mapping[int, Mapping[str, Any]],
) -> list[dict[str, object]]:
    record = _exact_keys(
        value,
        {
            "arm_result_identity",
            "cut_free_replay_identity",
            "expected_evaluations",
            "journal_identity",
            "ledger_identity",
            "mappings",
            "post_model_identity",
            "pre_model_identity",
            "purpose",
            "schema_version",
        },
        "concrete inequality corpus",
    )
    del corpus_identity
    if (
        record["schema_version"] != CORPUS_SCHEMA
        or record["purpose"] != CORPUS_PURPOSE
        or record["arm_result_identity"] != result_identity
        or record["ledger_identity"] != ledger_identity
        or record["journal_identity"] != journal_identity
        or record["cut_free_replay_identity"] != cut_free_identity
        or type(record["mappings"]) is not list
        or type(record["expected_evaluations"]) is not list
    ):
        raise ReplayError("concrete inequality corpus provenance drifted")
    count = len(applied)
    if count == 0:
        if (
            record["mappings"] != []
            or record["expected_evaluations"] != []
            or record["pre_model_identity"] is not None
            or record["post_model_identity"] is not None
        ):
            raise ReplayError("zero-APPLIED corpus must have no arithmetic payload")
        return []

    for field in ("pre_model_identity", "post_model_identity"):
        _identity(record[field], f"corpus {field}")
    pre_snapshot = _replay_identity(
        record["pre_model_identity"],
        "corpus pre-model",
        max_bytes=MAX_MODEL_BYTES,
    )
    post_snapshot = _replay_identity(
        record["post_model_identity"],
        "corpus post-model",
        max_bytes=MAX_MODEL_BYTES,
    )
    pre = _parse_model(pre_snapshot, "pre-model")
    post = _parse_model(post_snapshot, "post-model")
    if len(post.variables) < len(pre.variables) or len(post.constraints) - len(pre.constraints) != count:
        raise ReplayError("post-model/solution/APPLIED cardinality drifted")
    stripped = cp_model_pb2.CpModelProto()
    stripped.CopyFrom(post)
    del stripped.variables[len(pre.variables) :]
    del stripped.constraints[len(pre.constraints) :]
    if stripped.SerializeToString(deterministic=True) != pre.SerializeToString(deterministic=True):
        raise ReplayError("post-model changed bytes outside appended vars/constraints")

    mappings = record["mappings"]
    if len(mappings) != count:
        raise ReplayError("mapping count differs from APPLIED count")
    compiled_by_join: dict[
        tuple[str, str, str],
        list[Mapping[str, Any]],
    ] = {}
    for item in compiled:
        plan = item["plan"]
        key = (
            item["cut_id"],
            plan["digest"],
            plan["semantic_fingerprint"],
        )
        compiled_by_join.setdefault(key, []).append(item)
    evaluations: list[dict[str, object]] = []
    for ordinal, (raw_mapping, applied_event) in enumerate(zip(mappings, applied, strict=True)):
        mapping = _exact_keys(
            raw_mapping,
            {
                "compiled_digest",
                "constraint_index",
                "cut_id",
                "assignment_identity",
                "plan_digest",
                "semantic_fingerprint",
            },
            f"applied mapping {ordinal}",
        )
        expected_constraint_index = len(pre.constraints) + ordinal
        key = (
            applied_event["cut_id"],
            applied_event["plan_digest"],
            applied_event["semantic_fingerprint"],
        )
        matches = compiled_by_join.get(key, [])
        assignment_snapshot = _replay_identity(
            mapping["assignment_identity"],
            f"applied mapping {ordinal} assignment",
        )
        assignment = _exact_keys(
            _strict_json(
                assignment_snapshot.data,
                f"applied mapping {ordinal} assignment",
                canonical=True,
                allow_float=True,
            ),
            {
                "hook_id",
                "purpose",
                "schema_version",
                "solution",
                "solution_vector",
            },
            f"applied mapping {ordinal} assignment",
        )
        if (
            assignment["schema_version"] != ASSIGNMENT_SCHEMA
            or assignment["purpose"] != ASSIGNMENT_PURPOSE
            or type(assignment["hook_id"]) is not int
            or type(assignment["solution"]) is not dict
            or type(assignment["solution_vector"]) is not list
            or any(type(value) is not int for value in assignment["solution_vector"])
            or len(assignment["solution_vector"]) != len(post.variables)
        ):
            raise ReplayError("mapped attach assignment is malformed")
        hook = attach_hooks.get(assignment["hook_id"])
        if (
            mapping["cut_id"] != key[0]
            or mapping["plan_digest"] != key[1]
            or mapping["semantic_fingerprint"] != key[2]
            or mapping["constraint_index"] != expected_constraint_index
            or type(mapping["constraint_index"]) is not int
            or len(matches) != 1
            or mapping["compiled_digest"] != matches[0]["compiled_digest"]
            or matches[0]["hook_id"] != assignment["hook_id"]
            or hook is None
            or hook["solution_sha256"] != hashlib.sha256(_compact_json(assignment["solution"])).hexdigest()
        ):
            raise ReplayError("APPLIED/compiled/assignment/constraint join is not one-to-one")
        evaluation = {
            "assignment_identity": dict(mapping["assignment_identity"]),
            "compiled_digest": mapping["compiled_digest"],
            "constraint_index": expected_constraint_index,
            "cut_id": mapping["cut_id"],
            "operation": matches[0]["plan"]["operation"],
            **_constraint_evaluation(
                post.constraints[expected_constraint_index],
                model=post,
                solution=assignment["solution_vector"],
                operation=matches[0]["plan"]["operation"],
                applied=applied_event,
            ),
        }
        if evaluation["active"] is not True or evaluation["violated"] is not True:
            raise ReplayError("APPLIED inequality was not active and violated at attach")
        evaluations.append(evaluation)
    if record["expected_evaluations"] != evaluations:
        raise ReplayError("reported arithmetic differs from independent evaluation")
    return evaluations


def _fixed_vector_feasible(
    model_proto: cp_model_pb2.CpModelProto,
    solution: Sequence[int],
) -> None:
    """Check one complete vector against the pre-attach model, single-worker."""

    if len(solution) != len(model_proto.variables):
        raise ReplayError("attach vector length differs from pre-model")
    model = cp_model.CpModel()
    model.proto.parse_text_format(text_format.MessageToString(model_proto))
    for index, value in enumerate(solution):
        model.add(model.get_int_var_from_proto_index(index) == value)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 2026072401
    solver.parameters.max_time_in_seconds = 120.0
    status = solver.solve(model)
    if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        raise ReplayError("attach vector is not a feasible complete pre-model assignment")


def _model_evidence_by_hook(
    journal_events: Sequence[Mapping[str, Any]],
) -> dict[int, Mapping[str, Any]]:
    evidence: dict[int, Mapping[str, Any]] = {}
    for event in journal_events:
        if event["event"] != "ATTACH_MODEL_EVIDENCE":
            continue
        payload = _exact_keys(
            event["payload"],
            {
                "hook_id",
                "post_model_identity",
                "pre_model_identity",
                "solution_vector_identity",
            },
            "attach model evidence",
        )
        hook_id = payload["hook_id"]
        if type(hook_id) is not int or hook_id < 0 or hook_id in evidence:
            raise ReplayError("attach model evidence hook identity drifted")
        for field in (
            "post_model_identity",
            "pre_model_identity",
            "solution_vector_identity",
        ):
            _identity(payload[field], f"attach model evidence {field}")
        evidence[hook_id] = payload
    return evidence


def _replay_attached_inequalities(
    *,
    journal_events: Sequence[Mapping[str, Any]],
    attach_hooks: Mapping[int, Mapping[str, Any]],
    applied: Sequence[Mapping[str, Any]],
    compiled: Sequence[Mapping[str, Any]],
) -> list[dict[str, object]]:
    """Rebuild every attached inequality from raw per-hook model evidence."""

    model_evidence = _model_evidence_by_hook(journal_events)
    if set(model_evidence) != set(attach_hooks):
        raise ReplayError("attach model evidence coverage differs from hooks")
    compiled_by_join: dict[
        tuple[str, str, str],
        list[Mapping[str, Any]],
    ] = {}
    for record in compiled:
        plan = record["plan"]
        key = (
            record["cut_id"],
            plan["digest"],
            plan["semantic_fingerprint"],
        )
        compiled_by_join.setdefault(key, []).append(record)
    applied_compiled: dict[int, list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = {}
    used_compiled: set[str] = set()
    for event in applied:
        key = (
            event["cut_id"],
            event["plan_digest"],
            event["semantic_fingerprint"],
        )
        matches = compiled_by_join.get(key, [])
        if len(matches) != 1:
            raise ReplayError("APPLIED event lacks one unique compiled join")
        compiled_record = matches[0]
        digest = compiled_record["compiled_digest"]
        if digest in used_compiled:
            raise ReplayError("one compiled cut joined multiple APPLIED events")
        used_compiled.add(digest)
        applied_compiled.setdefault(
            compiled_record["hook_id"],
            [],
        ).append((event, compiled_record))

    evaluations: list[dict[str, object]] = []
    for hook_id in sorted(attach_hooks):
        raw_evidence = model_evidence[hook_id]
        pre_snapshot = _replay_identity(
            raw_evidence["pre_model_identity"],
            f"hook {hook_id} pre-model",
            max_bytes=MAX_MODEL_BYTES,
        )
        post_snapshot = _replay_identity(
            raw_evidence["post_model_identity"],
            f"hook {hook_id} post-model",
            max_bytes=MAX_MODEL_BYTES,
        )
        vector_snapshot = _replay_identity(
            raw_evidence["solution_vector_identity"],
            f"hook {hook_id} solution vector",
        )
        pre = _parse_model(pre_snapshot, f"hook {hook_id} pre-model")
        post = _parse_model(post_snapshot, f"hook {hook_id} post-model")
        solution = _strict_json(
            vector_snapshot.data,
            f"hook {hook_id} solution vector",
            canonical=True,
        )
        if type(solution) is not list or any(type(value) is not int for value in solution):
            raise ReplayError("attach solution vector is malformed")
        _fixed_vector_feasible(pre, solution)
        if len(post.variables) != len(pre.variables):
            raise ReplayError("attach changed variable cardinality; vector mapping is incomplete")
        stripped = cp_model_pb2.CpModelProto()
        stripped.CopyFrom(post)
        del stripped.constraints[len(pre.constraints) :]
        if stripped.SerializeToString(deterministic=True) != pre.SerializeToString(deterministic=True):
            raise ReplayError("post-model changed bytes outside appended constraints")
        joined = applied_compiled.get(hook_id, [])
        added_count = len(post.constraints) - len(pre.constraints)
        terminal = next(
            event["payload"]
            for event in journal_events
            if event["event"] == "ATTACH_HOOK_END" and event["payload"]["hook_id"] == hook_id
        )
        if added_count != len(joined) or terminal["attached_count"] != len(joined):
            raise ReplayError("post-model delta differs from APPLIED/terminal count")
        for ordinal, (applied_event, compiled_record) in enumerate(joined):
            constraint_index = len(pre.constraints) + ordinal
            evaluation = {
                "compiled_digest": compiled_record["compiled_digest"],
                "constraint_index": constraint_index,
                "cut_id": compiled_record["cut_id"],
                "hook_id": hook_id,
                "operation": compiled_record["plan"]["operation"],
                **_constraint_evaluation(
                    post.constraints[constraint_index],
                    model=post,
                    solution=solution,
                    operation=compiled_record["plan"]["operation"],
                    applied=applied_event,
                ),
            }
            if evaluation["active"] is not True or evaluation["violated"] is not True:
                raise ReplayError("APPLIED inequality was not active and violated at attach")
            evaluations.append(evaluation)
    if len(evaluations) != len(applied):
        raise ReplayError("APPLIED evidence coverage is incomplete")
    return evaluations


def replay_arm(
    *,
    arm_result: Path | str,
    cut_free_replay: Path | str,
    replay_tool_identity: Mapping[str, object],
) -> dict[str, object]:
    """Replay one immutable arm evidence set with fixed-vector feasibility."""

    replay_tool_snapshot = _replay_identity(
        replay_tool_identity,
        "organic arm replay tool",
    )
    result_snapshot = snapshot_regular(arm_result)
    result_value = _strict_json(
        result_snapshot.data,
        "organic arm result",
        canonical=True,
        allow_float=True,
    )
    result = _validate_result(
        result_value,
        result_identity=result_snapshot.identity,
    )
    ledger_snapshot = _replay_identity(
        result["evidence"]["cut_ledger_identity"],
        "organic ledger",
        max_bytes=1_000_000_000,
    )
    journal_snapshot = _replay_identity(
        result["evidence"]["compile_attach_journal_identity"],
        "compile/attach journal",
        max_bytes=1_000_000_000,
    )
    ledger_events = _parse_ledger(ledger_snapshot)
    journal_events = _parse_journal(journal_snapshot)
    ledger_counts = _event_counts(ledger_events)
    journal_counts = _event_counts(journal_events)
    if (
        result["evidence"]["ledger_event_counts"] != ledger_counts
        or result["evidence"]["journal_event_counts"] != journal_counts
    ):
        raise ReplayError("result event-count summaries differ from raw evidence")
    generated = ledger_counts.get("GENERATED", 0)
    compiled_records = _compiled_records(journal_events)
    attach_hooks, first_attach_digest = _attach_hooks(journal_events)
    baseline_snapshot = _replay_identity(
        result["authority_identities"]["baseline_incumbent"],
        "admitted baseline incumbent",
    )
    baseline_value = _strict_json(
        baseline_snapshot.data,
        "admitted baseline incumbent",
        canonical=True,
        allow_float=True,
    )
    if type(baseline_value) is not dict or (
        first_attach_digest is not None
        and hashlib.sha256(_compact_json(baseline_value)).hexdigest() != first_attach_digest
    ):
        raise ReplayError("first attach solution differs from admitted incumbent semantics")
    applied_events = _applied_events(ledger_events)
    for compiled in compiled_records:
        hook_id = compiled["hook_id"]
        if hook_id not in attach_hooks:
            raise ReplayError("compiled cut lacks one complete attach hook")
    activity = {
        "applied": len(applied_events),
        "compiled": len(compiled_records),
        "generated": generated,
    }
    if (
        activity != result["cut_activity"]
        or not 0 <= activity["applied"] <= activity["compiled"] <= activity["generated"]
    ):
        raise ReplayError("raw and reported cut activity differ")
    if generated == 0 and any(event["event"] in CUT_LEDGER_EVENTS for event in ledger_events):
        raise ReplayError("G=0 branch contains a cut lifecycle event")
    lineage_summary = _replay_cut_lineage(
        ledger_events=ledger_events,
        compiled=compiled_records,
        applied=applied_events,
        enabled_families=result["enabled_families"],
    )

    incumbent_export = result["incumbent_export"]
    arm_incumbent_present = incumbent_export["present"] is True
    if arm_incumbent_present:
        replay_subject_snapshot = _replay_identity(
            incumbent_export["incumbent_identity"],
            "arm raw incumbent",
        )
        _replay_identity(
            incumbent_export["solution_vector_identity"],
            "arm raw solution vector",
        )
    else:
        replay_subject_snapshot = baseline_snapshot
    cut_free_snapshot = snapshot_regular(cut_free_replay)
    cut_free_value = _strict_json(
        cut_free_snapshot.data,
        "cut-free replay receipt",
        canonical=True,
    )
    _validate_cut_free(
        cut_free_value,
        arm_incumbent_identity=replay_subject_snapshot.identity,
    )
    evaluations = _replay_attached_inequalities(
        journal_events=journal_events,
        attach_hooks=attach_hooks,
        applied=applied_events,
        compiled=compiled_records,
    )
    if generated == 0:
        classification = ORGANIC_NONACTIVATION
    elif not applied_events:
        classification = NO_ORGANIC_APPLIED_CUT
    else:
        classification = ORGANIC_APPLIED
    authorities = result["authority_identities"]
    selection_identity = dict(
        _identity(
            authorities["selection"],
            "result selection identity",
        )
    )
    manifest_identity = dict(
        _identity(
            authorities["manifest"],
            "result manifest identity",
        )
    )
    return {
        "applied_inequality_evaluations": evaluations,
        "arm_incumbent_present": arm_incumbent_present,
        "arm_result_identity": result_snapshot.identity,
        "authorizations": {
            "family_global_soundness_authorized": False,
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "production_certified_authorized": False,
            "runtime_effect_authorized": False,
        },
        "classification": classification,
        "cut_activity": activity,
        "cut_free_replay_identity": cut_free_snapshot.identity,
        "cut_free_replay_subject_identity": (replay_subject_snapshot.identity),
        "cut_free_replay_status": "PASS",
        "enabled_families": list(result["enabled_families"]),
        "journal_identity": journal_snapshot.identity,
        "ledger_identity": ledger_snapshot.identity,
        "lineage_summary": lineage_summary,
        "manifest_identity": manifest_identity,
        "purpose": RECEIPT_PURPOSE,
        "replay_tool_identity": replay_tool_snapshot.identity,
        "schema_version": RECEIPT_SCHEMA,
        "selection_identity": selection_identity,
        "slot": result["slot"],
        "status": "PASS",
    }


def write_exclusive(
    output: Path | str,
    value: Mapping[str, object],
) -> dict[str, object]:
    absolute = _absolute(output)
    _reject_symlink_chain(absolute.parent)
    if not absolute.parent.is_dir():
        raise ReplayError("output parent is not a directory")
    parent_fd = os.open(
        absolute.parent,
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    raw = canonical_json(value)
    try:
        descriptor = os.open(
            absolute.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        try:
            offset = 0
            while offset < len(raw):
                written = os.write(descriptor, raw[offset:])
                if written <= 0:
                    raise ReplayError("receipt write made no progress")
                offset += written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.fsync(parent_fd)
    except FileExistsError as exc:
        raise ReplayError("refusing to overwrite replay receipt") from exc
    finally:
        os.close(parent_fd)
    return snapshot_regular(absolute).identity


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm-result", type=Path, required=True)
    parser.add_argument("--cut-free-replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay-tool", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse_args(argv)
    try:
        receipt = replay_arm(
            arm_result=arguments.arm_result,
            cut_free_replay=arguments.cut_free_replay,
            replay_tool_identity=snapshot_regular(arguments.replay_tool).identity,
        )
        identity = write_exclusive(arguments.output, receipt)
    except ReplayError as exc:
        sys.stderr.buffer.write(
            canonical_json(
                {
                    "error": str(exc),
                    "schema_version": RECEIPT_SCHEMA,
                    "status": "FAIL_CLOSED",
                }
            )
        )
        return 2
    sys.stdout.buffer.write(
        canonical_json(
            {
                "receipt_identity": identity,
                "status": "PASS",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
