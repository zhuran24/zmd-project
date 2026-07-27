#!/usr/bin/env python3
"""Fail-closed admission for the prospective non-certified-cuts AB16 baseline.

The historical ``control-a002`` result is accepted only as byte-locked
provenance.  It cannot authorize a baseline, an arm, a solver run, or a
mathematical claim.  Baseline admission instead requires:

* a freshly rebuilt, canonical binary ``CpModelProto``;
* strict rebuild metadata binding the builder and all rebuild inputs; and
* an independently produced fixed-assignment replay receipt binding the same
  model, metadata, incumbent, and replay tool.
* one package-bound repository-snapshot provenance record replayed before and
  after admission, shared exactly by rebuild metadata and replay receipt.

Every file is read once through an ``O_NOFOLLOW`` file descriptor and checked
with before/after ``fstat``.  The only write is an ``O_EXCL`` result after all
checks pass.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, Mapping

from google.protobuf import text_format
from google.protobuf.message import DecodeError
from ortools.sat import cp_model_pb2


ADMISSION_SCHEMA = "noncert-cuts-ab16-baseline-admission-v1"
METADATA_SCHEMA = "noncert-cuts-ab16-rebuilt-model-metadata-v2"
REPLAY_SCHEMA = "noncert-cuts-ab16-fixed-assignment-replay-v2"
CAMPAIGN_PROVENANCE_SCHEMA = "noncert-cuts-ab16-campaign-snapshot-provenance-v1"
MATERIALIZATION_SCHEMA = "noncert-cuts-ab16-repository-snapshot-materialization-v1"
MATERIALIZATION_AUTHORITY_SCOPE = "AB16_RESEARCH_ONLY"
SNAPSHOT_IMPORT_MODE = "ordinary_pathfinder"
MODEL_BACKEND = "ortools.sat.cp_model_pb2.CpModelProto"
MODEL_BINARY_FORMAT = "deterministic-protobuf-v1"
REBUILD_PURPOSE = "strict_ab16_baseline_model_rebuild"
REPLAY_PURPOSE = "strict_ab16_incumbent_fixed_assignment_replay"
REPLAY_VERDICT = "INCUMBENT_FIXED_ASSIGNMENT_REPLAY_PASS"
ADMISSION_VERDICT = "AB16_BASELINE_INPUTS_ADMITTED"
REQUIRED_REBUILD_INPUT_ROLES = frozenset(
    {
        "candidate_placements",
        "canonical_rules",
        "mandatory_instances",
    }
)
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
GIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
ROLE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
MAX_JSON_BYTES = 64 * 1024 * 1024
MAX_MODEL_BYTES = 1024 * 1024 * 1024
CAMPAIGN_PROVENANCE_KEYS = {
    "import_mode",
    "materialization_receipt_identity",
    "package_id",
    "repository_head",
    "schema_version",
    "snapshot_manifest_identity",
    "snapshot_root",
}
MATERIALIZATION_KEYS = {
    "authority_scope",
    "candidate_identity",
    "created_at_utc",
    "import_mode",
    "member_count",
    "ordered_member_digest",
    "package_id",
    "repository_head",
    "repository_tree",
    "schema_version",
    "snapshot_archive_identity",
    "snapshot_manifest_identity",
    "snapshot_root",
    "status",
    "total_bytes",
}


class AdmissionError(RuntimeError):
    """The supplied bytes do not establish the baseline admission contract."""


@dataclass(frozen=True)
class Snapshot:
    """Bytes and detached identity obtained from one stable open descriptor."""

    data: bytes
    identity: dict[str, object]


@dataclass(frozen=True)
class BaselineExpectation:
    """Constants that cannot be overridden by the production CLI."""

    profile: str
    legacy_size_bytes: int
    legacy_sha256: str
    historical_model_text_sha256: str
    model_variable_count: int
    model_constraint_count: int
    incumbent_sha256: str
    incumbent_assignment_count: int


PRODUCTION_EXPECTATION = BaselineExpectation(
    profile="production-control-a002-v1",
    legacy_size_bytes=507_095,
    legacy_sha256="9e747c214c2108b7fc73fede1d31873b24bf765d74857cf4a846cf5178ebcff6",
    historical_model_text_sha256=("3a9be08dcca722fc4bf7dfc9bcf7be4a1213af14ded9ec7b769909a029904d32"),
    model_variable_count=37_760,
    model_constraint_count=95_136,
    incumbent_sha256="13f88404d7f5e4fde86929f82997a2b9850fa1cc4791d710c0363ed3e072f223",
    incumbent_assignment_count=293,
)


def canonical_json(value: object) -> bytes:
    """Return the one accepted representation for new JSON authorities."""

    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def semantic_digest(value: object) -> str:
    """Digest JSON semantics without the authority file's trailing newline."""

    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _snapshot_signature(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def snapshot_regular(
    path: Path | str,
    *,
    max_bytes: int,
    label: str,
) -> Snapshot:
    """Read and hash one regular, non-symlink file through a single descriptor."""

    requested = Path(path)
    absolute = requested if requested.is_absolute() else Path.cwd() / requested
    absolute = Path(os.path.abspath(absolute))
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(absolute, flags)
    except OSError as exc:
        raise AdmissionError(f"{label}: cannot open a non-symlink input") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size < 0 or before.st_size > max_bytes:
            raise AdmissionError(f"{label}: input is not an admissible regular file")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                raise AdmissionError(f"{label}: input ended before its fstat size")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise AdmissionError(f"{label}: input grew while being read")
        after = os.fstat(descriptor)
        if _snapshot_signature(before) != _snapshot_signature(after):
            raise AdmissionError(f"{label}: input changed while its descriptor was open")
        data = b"".join(chunks)
        if len(data) != before.st_size:
            raise AdmissionError(f"{label}: input size replay failed")
    finally:
        os.close(descriptor)
    return Snapshot(
        data=data,
        identity={
            "path": str(absolute),
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
        },
    )


def _strict_loads(
    raw: bytes,
    label: str,
    *,
    canonical: bool,
    allow_historical_floats: bool = False,
) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise AdmissionError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject_float(value: str) -> object:
        raise AdmissionError(f"{label}: non-integer JSON number {value!r}")

    def reject_constant(value: str) -> object:
        raise AdmissionError(f"{label}: non-finite JSON number {value!r}")

    try:
        value = json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=Decimal if allow_historical_floats else reject_float,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdmissionError(f"{label}: malformed strict JSON") from exc
    if canonical and canonical_json(value) != raw:
        raise AdmissionError(f"{label}: JSON bytes are not canonical")
    return value


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AdmissionError(f"{label}: expected object")
    return value


def _exact_keys(
    value: object,
    expected: set[str],
    label: str,
) -> Mapping[str, Any]:
    record = _mapping(value, label)
    if set(record) != expected:
        raise AdmissionError(f"{label}: key set drifted")
    return record


def _identity(value: object, label: str) -> Mapping[str, Any]:
    record = _exact_keys(value, {"path", "sha256", "size_bytes"}, label)
    if (
        type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
    ):
        raise AdmissionError(f"{label}: invalid detached identity")
    return record


def _require_identity(
    actual: Mapping[str, object],
    claimed: object,
    label: str,
) -> None:
    if dict(_identity(claimed, label)) != dict(actual):
        raise AdmissionError(f"{label}: detached identity mismatch")


def _utc(value: object, label: str) -> str:
    if type(value) is not str or not value.endswith("Z"):
        raise AdmissionError(f"{label}: expected an explicit UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise AdmissionError(f"{label}: invalid UTC timestamp") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise AdmissionError(f"{label}: timestamp is not UTC")
    return value


def _integer(value: object, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise AdmissionError(f"{label}: expected integer >= {minimum}")
    return value


def _replay_identity(value: object, label: str, *, max_bytes: int = MAX_JSON_BYTES) -> Snapshot:
    identity = _identity(value, label)
    snapshot = snapshot_regular(identity["path"], max_bytes=max_bytes, label=label)
    _require_identity(snapshot.identity, identity, label)
    return snapshot


def _snapshot_root(value: object) -> Path:
    if type(value) is not str or not Path(value).is_absolute():
        raise AdmissionError("campaign provenance snapshot_root is not absolute")
    root = Path(value)
    if Path(os.path.abspath(root)) != root:
        raise AdmissionError("campaign provenance snapshot_root is not normalized")
    current = Path(root.anchor)
    for component in root.parts[1:]:
        current /= component
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise AdmissionError("campaign provenance snapshot_root is unavailable") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise AdmissionError("campaign provenance snapshot_root contains a symlink")
    if not root.is_dir():
        raise AdmissionError("campaign provenance snapshot_root is not a directory")
    return root


def campaign_provenance(path: Path | str) -> dict[str, object]:
    provenance_snapshot = snapshot_regular(
        path,
        max_bytes=MAX_JSON_BYTES,
        label="campaign provenance",
    )
    record = _exact_keys(
        _strict_loads(
            provenance_snapshot.data,
            "campaign provenance",
            canonical=True,
        ),
        CAMPAIGN_PROVENANCE_KEYS,
        "campaign provenance",
    )
    if (
        record["schema_version"] != CAMPAIGN_PROVENANCE_SCHEMA
        or type(record["repository_head"]) is not str
        or GIT_SHA_RE.fullmatch(record["repository_head"]) is None
        or type(record["package_id"]) is not str
        or SHA256_RE.fullmatch(record["package_id"]) is None
        or record["import_mode"] != SNAPSHOT_IMPORT_MODE
    ):
        raise AdmissionError("campaign provenance semantics drifted")
    root = _snapshot_root(record["snapshot_root"])
    manifest = _replay_identity(
        record["snapshot_manifest_identity"],
        "campaign snapshot manifest",
    )
    _mapping(
        _strict_loads(
            manifest.data,
            "campaign snapshot manifest",
            canonical=True,
        ),
        "campaign snapshot manifest",
    )
    materialization = _replay_identity(
        record["materialization_receipt_identity"],
        "campaign snapshot materialization receipt",
    )
    receipt = _exact_keys(
        _strict_loads(
            materialization.data,
            "campaign snapshot materialization receipt",
            canonical=True,
        ),
        MATERIALIZATION_KEYS,
        "campaign snapshot materialization receipt",
    )
    _utc(receipt["created_at_utc"], "campaign snapshot materialization created_at_utc")
    _integer(receipt["member_count"], "campaign snapshot materialization member_count", 1)
    _integer(receipt["total_bytes"], "campaign snapshot materialization total_bytes", 1)
    _identity(receipt["snapshot_manifest_identity"], "materialization snapshot manifest")
    _identity(receipt["snapshot_archive_identity"], "materialization snapshot archive")
    _identity(receipt["candidate_identity"], "materialization candidate")
    if (
        receipt["schema_version"] != MATERIALIZATION_SCHEMA
        or receipt["status"] != "PASS"
        or receipt["authority_scope"] != MATERIALIZATION_AUTHORITY_SCOPE
        or receipt["repository_head"] != record["repository_head"]
        or type(receipt["repository_tree"]) is not str
        or GIT_SHA_RE.fullmatch(receipt["repository_tree"]) is None
        or receipt["package_id"] != record["package_id"]
        or receipt["snapshot_manifest_identity"] != dict(manifest.identity)
        or receipt["snapshot_manifest_identity"] != record["snapshot_manifest_identity"]
        or receipt["snapshot_root"] != str(root)
        or receipt["import_mode"] != SNAPSHOT_IMPORT_MODE
        or type(receipt["ordered_member_digest"]) is not str
        or SHA256_RE.fullmatch(receipt["ordered_member_digest"]) is None
    ):
        raise AdmissionError("campaign snapshot materialization semantics drifted")
    return dict(record)


def _validate_legacy(
    snapshot: Snapshot,
    expectation: BaselineExpectation,
) -> dict[str, object]:
    if (
        snapshot.identity["sha256"] != expectation.legacy_sha256
        or snapshot.identity["size_bytes"] != expectation.legacy_size_bytes
    ):
        raise AdmissionError("legacy control-a002 bytes do not match pinned provenance")
    value = _mapping(
        _strict_loads(
            snapshot.data,
            "legacy control-a002",
            canonical=False,
            allow_historical_floats=True,
        ),
        "legacy control-a002",
    )
    prestate = _mapping(value.get("prestate"), "legacy prestate")
    injection = _mapping(value.get("injection"), "legacy injection")
    if (
        value.get("schema_version") != 1
        or type(value.get("schema_version")) is not int
        or value.get("run_tag") != "pc-control-a002"
        or value.get("arm") != "control"
        or value.get("terminal_status") != "ARM_COMPLETE"
        or (prestate.get("model_proto_sha256") != expectation.historical_model_text_sha256)
        or prestate.get("model_variable_count") != expectation.model_variable_count
        or type(prestate.get("model_variable_count")) is not int
        or prestate.get("model_constraint_count") != expectation.model_constraint_count
        or type(prestate.get("model_constraint_count")) is not int
        or prestate.get("incumbent_sha256") != expectation.incumbent_sha256
        or type(prestate.get("incumbent")) is not dict
        or len(prestate["incumbent"]) != expectation.incumbent_assignment_count
        or injection.get("compiled_observed") != 0
        or type(injection.get("compiled_observed")) is not int
        or injection.get("arithmetic_sample_count") != 0
        or type(injection.get("arithmetic_sample_count")) is not int
    ):
        raise AdmissionError("legacy control-a002 provenance semantics drifted")
    return {
        "arm": "control",
        "identity": dict(snapshot.identity),
        "reported_incumbent_sha256": prestate["incumbent_sha256"],
        "reported_model_constraint_count": prestate["model_constraint_count"],
        "reported_historical_model_text_sha256": prestate["model_proto_sha256"],
        "reported_model_variable_count": prestate["model_variable_count"],
        "run_tag": "pc-control-a002",
        "terminal_status": "ARM_COMPLETE",
        "authorizing": False,
        "provenance_only": True,
    }


def historical_model_text_bytes(model: cp_model_pb2.CpModelProto) -> bytes:
    """Reproduce the historical runner's protobuf text-rendering bytes."""

    return text_format.MessageToString(model).removesuffix("\n").encode("utf-8")


def historical_model_text_sha256(model: cp_model_pb2.CpModelProto) -> str:
    """Return the detached digest used by the historical control result."""

    return hashlib.sha256(historical_model_text_bytes(model)).hexdigest()


def _parse_model(
    raw: bytes,
    expectation: BaselineExpectation,
) -> cp_model_pb2.CpModelProto:
    model = cp_model_pb2.CpModelProto()
    try:
        consumed = model.ParseFromString(raw)
    except DecodeError as exc:
        raise AdmissionError("rebuilt model: malformed binary CpModelProto") from exc
    if consumed != len(raw):
        raise AdmissionError("rebuilt model: binary parser did not consume all bytes")
    deterministic = model.SerializeToString(deterministic=True)
    if deterministic != raw:
        raise AdmissionError("rebuilt model: binary CpModelProto is not canonical")
    without_unknown = cp_model_pb2.CpModelProto()
    without_unknown.CopyFrom(model)
    without_unknown.DiscardUnknownFields()
    if without_unknown.SerializeToString(deterministic=True) != raw:
        raise AdmissionError("rebuilt model: unknown protobuf fields are forbidden")
    if (
        len(model.variables) != expectation.model_variable_count
        or len(model.constraints) != expectation.model_constraint_count
    ):
        raise AdmissionError("rebuilt model: expected cardinality mismatch")
    if historical_model_text_sha256(model) != expectation.historical_model_text_sha256:
        raise AdmissionError("rebuilt model: historical text digest mismatch")
    return model


def _validate_metadata(
    snapshot: Snapshot,
    *,
    campaign_provenance: Mapping[str, object],
    model_identity: Mapping[str, object],
    expectation: BaselineExpectation,
) -> dict[str, object]:
    record = _exact_keys(
        _strict_loads(snapshot.data, "rebuild metadata", canonical=True),
        {
            "builder_identity",
            "campaign_provenance",
            "canonical_binary",
            "created_at_utc",
            "errors",
            "global_claim_authorized",
            "input_identities",
            "legacy_control_used_as_build_input",
            "model_backend",
            "model_binary_format",
            "model_constraint_count",
            "model_identity",
            "historical_model_text_sha256",
            "model_variable_count",
            "purpose",
            "schema_version",
            "status",
        },
        "rebuild metadata",
    )
    _utc(record["created_at_utc"], "rebuild metadata created_at_utc")
    _integer(record["model_variable_count"], "metadata model_variable_count")
    _integer(record["model_constraint_count"], "metadata model_constraint_count")
    if (
        record["schema_version"] != METADATA_SCHEMA
        or record["status"] != "PASS"
        or record["purpose"] != REBUILD_PURPOSE
        or record["campaign_provenance"] != dict(campaign_provenance)
        or record["model_backend"] != MODEL_BACKEND
        or record["model_binary_format"] != MODEL_BINARY_FORMAT
        or record["canonical_binary"] is not True
        or record["legacy_control_used_as_build_input"] is not False
        or record["global_claim_authorized"] is not False
        or record["errors"] != []
        or (record["historical_model_text_sha256"] != expectation.historical_model_text_sha256)
        or record["model_variable_count"] != expectation.model_variable_count
        or record["model_constraint_count"] != expectation.model_constraint_count
    ):
        raise AdmissionError("rebuild metadata semantics drifted")
    _require_identity(model_identity, record["model_identity"], "metadata model identity")
    builder = _replay_identity(record["builder_identity"], "metadata builder")
    inputs = _mapping(record["input_identities"], "metadata input identities")
    if set(inputs) != REQUIRED_REBUILD_INPUT_ROLES:
        raise AdmissionError("metadata rebuild input role set drifted")
    replayed_inputs: dict[str, dict[str, object]] = {}
    for role in sorted(inputs):
        if ROLE_RE.fullmatch(role) is None:
            raise AdmissionError("metadata rebuild input role is invalid")
        replayed = _replay_identity(inputs[role], f"metadata input {role}")
        replayed_inputs[role] = dict(replayed.identity)
    return {
        "builder_identity": dict(builder.identity),
        "campaign_provenance": dict(campaign_provenance),
        "input_identities": replayed_inputs,
        "metadata_identity": dict(snapshot.identity),
    }


def _validate_incumbent(snapshot: Snapshot, expectation: BaselineExpectation) -> Mapping[str, Any]:
    value = _mapping(
        _strict_loads(snapshot.data, "incumbent", canonical=True),
        "incumbent",
    )
    if semantic_digest(value) != expectation.incumbent_sha256 or len(value) != expectation.incumbent_assignment_count:
        raise AdmissionError("incumbent semantic digest or assignment count drifted")
    for instance_id, assignment in value.items():
        if type(instance_id) is not str or not instance_id:
            raise AdmissionError("incumbent contains an invalid instance id")
        item = _mapping(assignment, f"incumbent assignment {instance_id}")
        if item.get("instance_id") != instance_id:
            raise AdmissionError("incumbent assignment does not join its instance id")
    return value


def _validate_replay(
    snapshot: Snapshot,
    *,
    campaign_provenance: Mapping[str, object],
    model_identity: Mapping[str, object],
    metadata_identity: Mapping[str, object],
    expectation: BaselineExpectation,
) -> dict[str, object]:
    record = _exact_keys(
        _strict_loads(snapshot.data, "fixed-assignment replay", canonical=True),
        {
            "all_fixed_equalities_added",
            "assignment_count",
            "campaign_provenance",
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
        "fixed-assignment replay",
    )
    _utc(record["created_at_utc"], "fixed-assignment replay created_at_utc")
    for field in (
        "assignment_count",
        "conflicting_assignment_count",
        "fixed_assignment_count",
        "model_constraint_count",
        "model_variable_count",
        "unresolved_assignment_count",
    ):
        _integer(record[field], f"fixed-assignment replay {field}")
    if (
        record["schema_version"] != REPLAY_SCHEMA
        or record["status"] != "PASS"
        or record["verdict"] != REPLAY_VERDICT
        or record["purpose"] != REPLAY_PURPOSE
        or record["campaign_provenance"] != dict(campaign_provenance)
        or record["solver_status"] != "OPTIMAL"
        or record["solution_matches_fixed_assignments"] is not True
        or record["all_fixed_equalities_added"] is not True
        or record["legacy_control_used_as_truth_root"] is not False
        or record["global_claim_authorized"] is not False
        or record["model_validation_errors"] != []
        or record["replay_errors"] != []
        or record["incumbent_sha256"] != expectation.incumbent_sha256
        or record["model_variable_count"] != expectation.model_variable_count
        or record["model_constraint_count"] != expectation.model_constraint_count
        or record["assignment_count"] != expectation.incumbent_assignment_count
        or record["fixed_assignment_count"] != expectation.incumbent_assignment_count
        or record["unresolved_assignment_count"] != 0
        or record["conflicting_assignment_count"] != 0
    ):
        raise AdmissionError("fixed-assignment replay semantics drifted")
    _require_identity(model_identity, record["model_identity"], "replay model identity")
    _require_identity(
        metadata_identity,
        record["metadata_identity"],
        "replay metadata identity",
    )
    incumbent_snapshot = _replay_identity(
        record["incumbent_identity"],
        "replay incumbent",
    )
    _validate_incumbent(incumbent_snapshot, expectation)
    replay_tool = _replay_identity(
        record["replay_tool_identity"],
        "fixed-assignment replay tool",
    )
    return {
        "incumbent_identity": dict(incumbent_snapshot.identity),
        "receipt_identity": dict(snapshot.identity),
        "replay_tool_identity": dict(replay_tool.identity),
        "solver_status": "OPTIMAL",
        "status": "PASS",
        "verdict": REPLAY_VERDICT,
    }


def _admit_paths(
    *,
    campaign_provenance_path: Path | str,
    legacy_control: Path | str,
    rebuilt_model: Path | str,
    rebuilt_metadata: Path | str,
    fixed_assignment_replay: Path | str,
    created_at_utc: str,
    expectation: BaselineExpectation,
) -> dict[str, object]:
    """Internal implementation; tests may supply a small fixture expectation."""

    _utc(created_at_utc, "admission created_at_utc")
    provenance_before = campaign_provenance(campaign_provenance_path)
    legacy_snapshot = snapshot_regular(
        legacy_control,
        max_bytes=MAX_JSON_BYTES,
        label="legacy control-a002",
    )
    model_snapshot = snapshot_regular(
        rebuilt_model,
        max_bytes=MAX_MODEL_BYTES,
        label="rebuilt model",
    )
    metadata_snapshot = snapshot_regular(
        rebuilt_metadata,
        max_bytes=MAX_JSON_BYTES,
        label="rebuild metadata",
    )
    replay_snapshot = snapshot_regular(
        fixed_assignment_replay,
        max_bytes=MAX_JSON_BYTES,
        label="fixed-assignment replay",
    )
    tool_snapshot = snapshot_regular(
        Path(__file__),
        max_bytes=MAX_JSON_BYTES,
        label="baseline admission tool",
    )

    legacy = _validate_legacy(legacy_snapshot, expectation)
    _parse_model(model_snapshot.data, expectation)
    metadata = _validate_metadata(
        metadata_snapshot,
        campaign_provenance=provenance_before,
        model_identity=model_snapshot.identity,
        expectation=expectation,
    )
    replay = _validate_replay(
        replay_snapshot,
        campaign_provenance=provenance_before,
        model_identity=model_snapshot.identity,
        metadata_identity=metadata_snapshot.identity,
        expectation=expectation,
    )
    if campaign_provenance(campaign_provenance_path) != provenance_before:
        raise AdmissionError("campaign provenance drifted during baseline admission")
    return {
        "admission_tool_identity": dict(tool_snapshot.identity),
        "authorizations": {
            "baseline_inputs_admitted": True,
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "organic_arm_launch_authorized": False,
            "solver_run_authorized": False,
        },
        "campaign_provenance": provenance_before,
        "created_at_utc": created_at_utc,
        "expected_baseline": {
            "incumbent_assignment_count": expectation.incumbent_assignment_count,
            "incumbent_sha256": expectation.incumbent_sha256,
            "model_constraint_count": expectation.model_constraint_count,
            "historical_model_text_sha256": (expectation.historical_model_text_sha256),
            "model_variable_count": expectation.model_variable_count,
        },
        "expectation_profile": expectation.profile,
        "fixed_assignment_replay": replay,
        "legacy_control": legacy,
        "rebuilt_model": {
            "canonical_binary": True,
            "identity": dict(model_snapshot.identity),
            "metadata": metadata,
            "model_backend": MODEL_BACKEND,
            "model_binary_format": MODEL_BINARY_FORMAT,
        },
        "schema_version": ADMISSION_SCHEMA,
        "status": "PASS",
        "verdict": ADMISSION_VERDICT,
    }


def admit_paths(
    *,
    campaign_provenance_path: Path | str,
    legacy_control: Path | str,
    rebuilt_model: Path | str,
    rebuilt_metadata: Path | str,
    fixed_assignment_replay: Path | str,
    created_at_utc: str,
) -> dict[str, object]:
    """Apply the immutable production expectation."""

    return _admit_paths(
        campaign_provenance_path=campaign_provenance_path,
        legacy_control=legacy_control,
        rebuilt_model=rebuilt_model,
        rebuilt_metadata=rebuilt_metadata,
        fixed_assignment_replay=fixed_assignment_replay,
        created_at_utc=created_at_utc,
        expectation=PRODUCTION_EXPECTATION,
    )


def write_exclusive(path: Path | str, value: object) -> dict[str, object]:
    """Publish canonical result bytes once, without following the parent symlink."""

    output = Path(path)
    absolute = output if output.is_absolute() else Path.cwd() / output
    absolute = Path(os.path.abspath(absolute))
    parent = absolute.parent
    parent_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        parent_flags |= os.O_NOFOLLOW
    try:
        parent_fd = os.open(parent, parent_flags)
    except OSError as exc:
        raise AdmissionError("output parent is not an existing non-symlink directory") from exc
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    raw = canonical_json(value)
    try:
        descriptor = os.open(absolute.name, flags, 0o600, dir_fd=parent_fd)
        try:
            view = memoryview(raw)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise AdmissionError("exclusive output write made no progress")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except FileExistsError as exc:
        raise AdmissionError("output already exists") from exc
    finally:
        os.close(parent_fd)
    return {
        "path": str(absolute),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-provenance", required=True, type=Path)
    parser.add_argument("--legacy-control", required=True, type=Path)
    parser.add_argument("--rebuilt-model", required=True, type=Path)
    parser.add_argument("--rebuilt-metadata", required=True, type=Path)
    parser.add_argument("--fixed-assignment-replay", required=True, type=Path)
    parser.add_argument("--created-at-utc", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        result = admit_paths(
            campaign_provenance_path=arguments.campaign_provenance,
            legacy_control=arguments.legacy_control,
            rebuilt_model=arguments.rebuilt_model,
            rebuilt_metadata=arguments.rebuilt_metadata,
            fixed_assignment_replay=arguments.fixed_assignment_replay,
            created_at_utc=arguments.created_at_utc,
        )
        identity = write_exclusive(arguments.output, result)
    except AdmissionError as exc:
        print(f"FAIL_CLOSED: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "output_identity": identity,
                "status": result["status"],
                "verdict": result["verdict"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
