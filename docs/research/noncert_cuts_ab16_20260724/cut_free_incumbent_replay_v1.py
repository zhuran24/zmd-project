#!/usr/bin/env python3
"""Independently replay one fixed assignment on a cut-free binary model.

The checker reads the model, metadata and incumbent on stable O_NOFOLLOW
descriptors, parses the official binary protobuf, independently maps every
incumbent record to a real placement selector, and solves a fresh model with
those placements fixed.  It does not import the baseline builder or an
organic arm runner.  It reuses only the package-pinned admission module's
tracked-clean-checkout provenance validator.

The model metadata and this receipt share one exact package-bound repository
checkout provenance record.  Its campaign root, package, Git tool, pinned HEAD
and three baseline inputs are replayed before and after the solve.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
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
EXPECTED_INCUMBENT_SHA256 = "13f88404d7f5e4fde86929f82997a2b9850fa1cc4791d710c0363ed3e072f223"
EXPECTED_ASSIGNMENT_COUNT = 293
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


def _placement_indices(
    model: cp_model_pb2.CpModelProto,
    *,
    incumbent: Mapping[str, Any],
    mandatory_instances: object,
    candidate_placements: object,
) -> set[int]:
    if type(mandatory_instances) is not list:
        raise ReplayError("mandatory instances must be an exact array")
    if type(candidate_placements) is not dict:
        raise ReplayError("candidate placements must be an exact object")
    pools = candidate_placements.get("facility_pools")
    if type(pools) is not dict:
        raise ReplayError("candidate facility pools are absent")

    grouped: dict[tuple[str, str], list[str]] = {}
    for entry in mandatory_instances:
        if type(entry) is not dict:
            raise ReplayError("mandatory instance entry is invalid")
        instance_id = entry.get("instance_id")
        facility_type = entry.get("facility_type")
        operation_type = entry.get("operation_type", "")
        if any(type(value) is not str for value in (instance_id, facility_type, operation_type)):
            raise ReplayError("mandatory instance identity is invalid")
        grouped.setdefault((facility_type, operation_type), []).append(instance_id)
    group_by_instance: dict[str, str] = {}
    for group_index, ((facility_type, operation_type), members) in enumerate(sorted(grouped.items())):
        group_id = f"group::{facility_type}::{operation_type}::{group_index}"
        for instance_id in sorted(members):
            group_by_instance[instance_id] = group_id

    by_name: dict[str, int] = {}
    for index, variable in enumerate(model.variables):
        if not variable.name:
            continue
        if variable.name in by_name:
            raise ReplayError("model variable names are duplicated")
        by_name[variable.name] = index

    selected: set[int] = set()
    for instance_id, raw_assignment in incumbent.items():
        if type(instance_id) is not str or type(raw_assignment) is not dict:
            raise ReplayError("incumbent entry is invalid")
        if raw_assignment.get("instance_id") != instance_id:
            raise ReplayError("incumbent instance join failed")
        pose_idx = raw_assignment.get("pose_idx")
        if type(pose_idx) is not int or pose_idx < 0:
            raise ReplayError("incumbent pose index is invalid")
        bound_type = raw_assignment.get("bound_type")
        if instance_id == "ghost_pick":
            anchor = raw_assignment.get("anchor")
            if type(anchor) is not dict or type(anchor.get("x")) is not int or type(anchor.get("y")) is not int:
                raise ReplayError("ghost anchor is invalid")
            index = by_name.get(
                f"ghost__{anchor['x']}_{anchor['y']}_6_6",
                -1,
            )
        elif bound_type == "exact":
            group_id = group_by_instance.get(instance_id)
            if group_id is None:
                raise ReplayError("mandatory incumbent lacks a group")
            index = by_name.get(f"z__{group_id}__{pose_idx}", -1)
        elif bound_type == "exact_pose_optional":
            facility_type = raw_assignment.get("facility_type")
            if type(facility_type) is not str:
                raise ReplayError("optional incumbent facility type is invalid")
            index = by_name.get(f"opt__{facility_type}__{pose_idx}", -1)
        else:
            raise ReplayError("incumbent bound type is unsupported")
        if index < 0 or index in selected:
            raise ReplayError("incumbent selector is absent or duplicated")
        if list(model.variables[index].domain) != [0, 1]:
            raise ReplayError("incumbent selector is not an exact boolean")

        if instance_id != "ghost_pick":
            facility_type = raw_assignment.get("facility_type")
            pool = pools.get(facility_type) if type(facility_type) is str else None
            if type(pool) is not list or pose_idx >= len(pool) or type(pool[pose_idx]) is not dict:
                raise ReplayError("incumbent pose does not exist in candidate data")
            candidate = pool[pose_idx]
            if candidate.get("pose_id") != raw_assignment.get("pose_id") or candidate.get(
                "anchor"
            ) != raw_assignment.get("anchor"):
                raise ReplayError("incumbent pose identity differs from candidate data")
        selected.add(index)
    return selected


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
    selected = _placement_indices(
        parsed,
        incumbent=incumbent,
        mandatory_instances=mandatory_instances,
        candidate_placements=candidate_placements,
    )
    if len(selected) != len(incumbent):
        raise ReplayError("incumbent did not map one-to-one to placement selectors")

    model = cp_model.CpModel()
    model.proto.parse_text_format(text_format.MessageToString(parsed))
    placement_prefixes = ("z__", "opt__", "ghost__")
    for index, variable_proto in enumerate(parsed.variables):
        if variable_proto.name.startswith(placement_prefixes):
            variable = model.get_int_var_from_proto_index(index)
            model.add(variable == (1 if index in selected else 0))
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = float(max_time_seconds)
    solver.parameters.random_seed = 2026072301
    status = solver.solve(model)
    status_name = solver.status_name(status)
    if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        raise ReplayError(f"fixed assignment was not feasible: {status_name}")
    return {
        "status": "PASS",
        "solver_status": status_name,
        "variable_count": len(parsed.variables),
        "constraint_count_before_fixing": len(parsed.constraints),
        "fixed_assignment_count": len(selected),
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


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.campaign_provenance.is_absolute():
        raise ReplayError("campaign provenance path is not absolute")
    provenance_before = _campaign_provenance(args.campaign_provenance)
    repository_root = Path(str(provenance_before["repository_root"]))
    if Path.cwd() != repository_root:
        raise ReplayError("working directory is not the campaign repository root")
    model_raw, model_identity = _snapshot(args.model, limit=1 << 30)
    metadata_raw, metadata_identity = _snapshot(args.metadata, limit=64 << 20)
    incumbent_raw, incumbent_identity = _snapshot(args.incumbent, limit=64 << 20)
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
    ):
        raise ReplayError("metadata semantics drifted")
    if _identity(metadata.get("model_identity"), "metadata model") != model_identity:
        raise ReplayError("metadata does not bind the supplied model")
    if type(incumbent) is not dict:
        raise ReplayError("incumbent must be an exact object")
    if len(incumbent) != EXPECTED_ASSIGNMENT_COUNT or _semantic_digest(incumbent) != EXPECTED_INCUMBENT_SHA256:
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
        max_time_seconds=args.max_time_seconds,
    )
    if _campaign_provenance(args.campaign_provenance) != provenance_before:
        raise ReplayError("campaign provenance drifted during fixed-assignment replay")
    _, tool_identity = _snapshot(Path(__file__), limit=64 << 20)
    receipt = {
        "schema_version": SCHEMA,
        "status": "PASS",
        "verdict": VERDICT,
        "purpose": PURPOSE,
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "campaign_provenance": provenance_before,
        "model_identity": model_identity,
        "metadata_identity": metadata_identity,
        "incumbent_identity": incumbent_identity,
        "incumbent_sha256": EXPECTED_INCUMBENT_SHA256,
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
    identity = _write_exclusive(args.output, _authority_json(receipt))
    print(json.dumps({"status": "PASS", "receipt": identity}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
