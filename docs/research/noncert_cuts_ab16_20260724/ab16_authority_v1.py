#!/usr/bin/env python3
"""Append-only retry authority for the research-only AB16 campaign.

The scientific preregistration is immutable.  Execution attempts are not:
an incomplete attempt remains as evidence and the same fixed slot may be
retried after a clean committed code repair.  No record produced here grants
cut, witness, bound, production, certified, or Stage-B authority.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from types import ModuleType
from typing import Any


RESEARCH_DIR = Path(__file__).resolve().parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

import ab16_campaign_bootstrap_v1 as bootstrap  # noqa: E402
import ab16_contract_v1 as contract  # noqa: E402
import organic_arm_runner_v1 as runner  # noqa: E402
import organic_resource_lifecycle_v1 as lifecycle  # noqa: E402


INPUT_SET_SCHEMA = "noncert-cuts-ab16-attempt-input-set-v2"
ATTEMPT_OPEN_SCHEMA = "noncert-cuts-ab16-attempt-open-v2"
ATTEMPT_EXECUTION_SCHEMA = "noncert-cuts-ab16-attempt-execution-v1"
ATTEMPT_ABANDONED_SCHEMA = "noncert-cuts-ab16-attempt-abandoned-v1"
SELECTION_BINDING_SCHEMA = "noncert-cuts-ab16-attempt-selection-binding-v2"
RESULT_ENVELOPE_SCHEMA = "noncert-cuts-ab16-attempt-result-envelope-v1"
REPLAY_SCHEMA = "noncert-cuts-ab16-retry-campaign-replay-v1"
SUITE_SELECTION_SCHEMA = "noncert-cuts-ab16-suite-selection-v1"
BASELINE_PROVENANCE_SCHEMA = "noncert-cuts-ab16-tracked-clean-checkout-provenance-v1"
COMMON_PRESTATE_SCHEMA = "noncert-cuts-ab16-common-prestate-v2"
ARM_BINDING_SCHEMA = "noncert-cuts-ab16-arm-binding-v2"
COMMON_PRESTATE_PURPOSE = "prospective_noncert_cuts_ab16_common_prestate"
ARM_BINDING_PURPOSE = "prospective_noncert_cuts_ab16_arm_binding"
BASELINE_IMPORT_MODE = "tracked_clean_pinned_checkout"
GIT_OBSERVATION_TIMEOUT_SECONDS = 10.0

CREDIBLE_TERMINAL = "CREDIBLE_TERMINAL"
CREDIBILITY_INCOMPLETE = "CREDIBILITY_INCOMPLETE"
ATTEMPT_RE = re.compile(r"attempt-([0-9]{4,})\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
GIT_HEAD_RE = re.compile(r"[0-9a-f]{40}\Z")
ROLE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")

BASELINE_CHECKOUT_INPUT_PATHS = {
    "candidate_placements": Path("data/preprocessed/candidate_placements.json"),
    "canonical_rules": Path("rules/canonical_rules.json"),
    "mandatory_instances": Path("data/preprocessed/mandatory_exact_instances.json"),
}

RESEARCH_ONLY_AUTHORIZATIONS = {
    "cut_authorized": False,
    "family_global_soundness_authorized": False,
    "global_claim_authorized": False,
    "lower_bound_authorized": False,
    "mathematical_claim_authorized": False,
    "optimality_authorized": False,
    "production_certified_authorized": False,
    "stage_b_promotion_authorized": False,
    "upper_bound_authorized": False,
    "witness_authorized": False,
}

EXECUTION_TOOL_FILES = {
    "ab16_authority": "ab16_authority_v1.py",
    "ab16_campaign_bootstrap": "ab16_campaign_bootstrap_v1.py",
    "ab16_contract": "ab16_contract_v1.py",
    "ab16_terminal_gate": "ab16_terminal_gate_v1.py",
    "baseline_admission": "baseline_admission_v1.py",
    "baseline_rebuild": "baseline_rebuild_v1.py",
    "cut_free_incumbent_replay": "cut_free_incumbent_replay_v1.py",
    "organic_arm_replay": "organic_arm_replay_v1.py",
    "organic_arm_runner": "organic_arm_runner_v1.py",
    "organic_resource_lifecycle": "organic_resource_lifecycle_v1.py",
    "organic_resource_verifier": "organic_resource_verifier_v1.py",
    "organic_unit_orchestrator": "organic_unit_orchestrator_v1.py",
}


class AuthorityError(RuntimeError):
    """The retry campaign could not be interpreted without ambiguity."""


def canonical_json(value: object) -> bytes:
    return contract.canonical_json_bytes(value)


def _exact_mapping(value: object, keys: set[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise AuthorityError(f"{label} must have the exact key set")
    return value


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _snapshot(path: Path | str) -> tuple[bytes, dict[str, object]]:
    absolute = _absolute(path)
    try:
        descriptor = os.open(absolute, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as exc:
        raise AuthorityError(f"cannot open regular input: {absolute}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise AuthorityError(f"input is not a regular file: {absolute}")
        chunks: list[bytes] = []
        while block := os.read(descriptor, 1024 * 1024):
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
    raw = b"".join(chunks)
    if any(getattr(before, field) != getattr(after, field) for field in fields) or len(raw) != after.st_size:
        raise AuthorityError(f"input changed during read: {absolute}")
    return raw, {
        "mode": stat.S_IMODE(after.st_mode),
        "path": str(absolute),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _load_record(path: Path | str, label: str) -> tuple[Mapping[str, Any], dict[str, object]]:
    raw, identity = _snapshot(path)
    try:
        value = contract.strict_loads(raw)
    except contract.ContractError as exc:
        raise AuthorityError(f"{label} is not canonical strict JSON") from exc
    if type(value) is not dict:
        raise AuthorityError(f"{label} must be a JSON object")
    return value, identity


def _load_line_framed_record(path: Path | str, label: str) -> tuple[Mapping[str, Any], dict[str, object]]:
    """Load the exact single-LF framing published by bootstrap/baseline tools."""

    raw, identity = _snapshot(path)
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise AuthorityError(f"{label} is not canonical single-LF JSON framing")
    try:
        value = contract.strict_loads(raw[:-1])
    except contract.ContractError as exc:
        raise AuthorityError(f"{label} is not canonical single-LF JSON") from exc
    if type(value) is not dict:
        raise AuthorityError(f"{label} must be a JSON object")
    return value, identity


def recover_staging(path: Path | str) -> dict[str, object]:
    """Remove only this final path's interrupted same-directory staging files."""

    absolute = _absolute(path)
    prefix = f".{absolute.name}.pending-"
    try:
        parent_fd = os.open(absolute.parent, os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise AuthorityError(f"output parent is unavailable: {absolute.parent}") from exc
    removed: list[str] = []
    try:
        try:
            final_stat = os.stat(absolute.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            final_stat = None
        if final_stat is not None and not stat.S_ISREG(final_stat.st_mode):
            raise AuthorityError(f"published final is not a regular file: {absolute}")
        for name in sorted(os.listdir(parent_fd)):
            if not name.startswith(prefix):
                continue
            try:
                pending_stat = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(pending_stat.st_mode):
                raise AuthorityError(f"staging recovery found a non-regular entry: {name}")
            os.unlink(name, dir_fd=parent_fd)
            removed.append(name)
        if removed:
            os.fsync(parent_fd)
        if final_stat is not None:
            final_after = os.stat(absolute.name, dir_fd=parent_fd, follow_symlinks=False)
            if not stat.S_ISREG(final_after.st_mode) or final_after.st_nlink != 1:
                raise AuthorityError(f"published final still has staging aliases: {absolute}")
    except OSError as exc:
        raise AuthorityError(f"staging recovery failed: {absolute}") from exc
    finally:
        os.close(parent_fd)
    identity = None if final_stat is None else _snapshot(absolute)[1]
    return {
        "final_identity": identity,
        "path": str(absolute),
        "recovered_pending": removed,
        "status": "STAGING_RECOVERED",
    }


def _write_bytes_exclusive(path: Path, raw: bytes) -> dict[str, object]:
    absolute = _absolute(path)
    recovered = recover_staging(absolute)
    if recovered["final_identity"] is not None:
        raise AuthorityError(f"no-overwrite publication failed: {absolute}")
    try:
        parent_fd = os.open(absolute.parent, os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise AuthorityError(f"output parent is unavailable: {absolute.parent}") from exc
    pending_name = f".{absolute.name}.pending-{os.getpid()}-{time.monotonic_ns()}"
    pending_exists = False
    try:
        descriptor = os.open(
            pending_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        pending_exists = True
        try:
            view = memoryview(raw)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise AuthorityError(f"short write: {absolute}")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.link(
            pending_name,
            absolute.name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
            follow_symlinks=False,
        )
        os.fsync(parent_fd)
        os.unlink(pending_name, dir_fd=parent_fd)
        pending_exists = False
        os.fsync(parent_fd)
    except OSError as exc:
        raise AuthorityError(f"no-overwrite publication failed: {absolute}") from exc
    finally:
        if pending_exists:
            try:
                os.unlink(pending_name, dir_fd=parent_fd)
                os.fsync(parent_fd)
            except OSError:
                pass
        os.close(parent_fd)
    _raw, identity = _snapshot(absolute)
    if _raw != raw:
        raise AuthorityError(f"published bytes changed: {absolute}")
    return identity


def _write_record(path: Path, value: object) -> dict[str, object]:
    return _write_bytes_exclusive(path, canonical_json(value))


def _make_directory(path: Path) -> None:
    absolute = _absolute(path)
    try:
        absolute.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise AuthorityError(f"no-overwrite directory already exists: {absolute}") from exc
    metadata = absolute.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or absolute.is_symlink():
        raise AuthorityError(f"created path is not a real directory: {absolute}")


def _existing_directory(path: Path, label: str) -> Path:
    absolute = _absolute(path)
    try:
        metadata = absolute.lstat()
    except OSError as exc:
        raise AuthorityError(f"{label} is unavailable: {absolute}") from exc
    if absolute.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise AuthorityError(f"{label} is not a real directory: {absolute}")
    return absolute


def _identity(value: object, label: str) -> Mapping[str, Any]:
    record = _exact_mapping(value, {"mode", "path", "sha256", "size_bytes"}, label)
    if (
        type(record["mode"]) is not int
        or not 0 <= record["mode"] <= 0o7777
        or type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
    ):
        raise AuthorityError(f"{label} is malformed")
    return record


def _verify_identity(value: object, label: str) -> Mapping[str, Any]:
    expected = _identity(value, label)
    _raw, actual = _snapshot(expected["path"])
    if actual != expected:
        raise AuthorityError(f"{label} bytes or metadata drifted")
    return expected


def _identity_map(value: object, label: str, *, verify: bool) -> Mapping[str, Mapping[str, Any]]:
    if type(value) is not dict or not value:
        raise AuthorityError(f"{label} must be a non-empty object")
    result: dict[str, Mapping[str, Any]] = {}
    for role, member in value.items():
        if type(role) is not str or ROLE_RE.fullmatch(role) is None:
            raise AuthorityError(f"{label} contains an invalid role")
        result[role] = _verify_identity(member, f"{label}.{role}") if verify else _identity(member, f"{label}.{role}")
    return result


def _detached_identity(value: Mapping[str, Any]) -> dict[str, object]:
    """Project the local mode-bearing identity to the shared detached form."""

    return {field: value[field] for field in ("path", "sha256", "size_bytes")}


def _verify_detached_identity_with_mode(value: object, label: str) -> dict[str, object]:
    expected = _exact_mapping(value, {"path", "sha256", "size_bytes"}, label)
    if (
        type(expected["path"]) is not str
        or not Path(expected["path"]).is_absolute()
        or type(expected["sha256"]) is not str
        or SHA256_RE.fullmatch(expected["sha256"]) is None
        or type(expected["size_bytes"]) is not int
        or expected["size_bytes"] < 0
    ):
        raise AuthorityError(f"{label} is malformed")
    _raw, actual = _snapshot(expected["path"])
    if _detached_identity(actual) != expected:
        raise AuthorityError(f"{label} bytes drifted")
    return actual


def _runtime_parameters() -> dict[str, object]:
    budget = runner.EXPERIMENT_CONTRACT["budget"]
    solver = runner.EXPERIMENT_CONTRACT["solver_parameters"]
    return {
        "attach_iteration": 1001,
        "attach_trigger": "binding_infeasible",
        "binding_alt_cap": solver["binding_alt_cap"],
        "binding_seconds": budget["binding_seconds"],
        "ghost_rect": list(solver["ghost_rectangle"]),
        "master_seconds": budget["master_seconds"],
        "max_iterations": budget["max_iterations"],
        "post_attach_seconds": budget["post_attach_seconds"],
        "routing_seconds": budget["routing_seconds"],
    }


def _baseline_material_paths(preregistration: Mapping[str, Any]) -> dict[str, Path]:
    return {
        "baseline_admission": Path(preregistration["baseline_admission_path"]),
        "baseline_fixed_replay": Path(preregistration["baseline_fixed_replay_path"]),
        "baseline_incumbent": Path(preregistration["baseline_incumbent_path"]),
        "baseline_rebuilt_metadata": Path(preregistration["baseline_rebuilt_metadata_path"]),
        "baseline_rebuilt_model": Path(preregistration["baseline_rebuilt_model_path"]),
        "classification_contract": Path(preregistration["classification_contract_path"]),
    }


def _scientific_material_paths(preregistration: Mapping[str, Any]) -> dict[str, Path]:
    """Return the non-self-referential shared scientific material set."""

    paths = _baseline_material_paths(preregistration)
    paths["common_prestate"] = Path(preregistration["common_prestate_path"])
    paths.update(
        {
            f"arm_binding.{slot}": Path(preregistration["binding_paths"][slot])
            for slot in contract.ARM_SEQUENCE
        }
    )
    return paths


def _materialization_digest(preregistration: Mapping[str, Any]) -> str:
    captured = _capture_sources(_scientific_material_paths(preregistration), "scientific material")
    identities = {role: identity for role, (_raw, identity) in captured.items()}
    return _scientific_materialization_digest(identities)


def _scientific_materialization_digest(identities: Mapping[str, Mapping[str, Any]]) -> str:
    projection = {
        "members": {
            role: {
                "sha256": identities[role]["sha256"],
                "size_bytes": identities[role]["size_bytes"],
            }
            for role in sorted(identities)
        },
        "schema": "noncert-cuts-ab16-scientific-materialization-v1",
    }
    return hashlib.sha256(canonical_json(projection)).hexdigest()


def _validated_campaign_root(
    preregistration: Mapping[str, Any],
) -> tuple[Mapping[str, Any], dict[str, object]]:
    campaign_dir = Path(preregistration["campaign_dir"])
    root, root_identity = _load_line_framed_record(campaign_dir / "campaign-root.json", "campaign root")
    try:
        checked = bootstrap.authority.validate_campaign_root(root, campaign_dir=campaign_dir)
    except Exception as exc:
        raise AuthorityError("campaign root is invalid") from exc
    return checked, root_identity


def _expected_record_identity(path: Path, record: Mapping[str, Any]) -> dict[str, object]:
    raw = canonical_json(record)
    return {
        "path": str(_absolute(path)),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _pre_manifest_expectations(preregistration_path: Path | str) -> dict[str, object]:
    preregistration_path = _absolute(preregistration_path)
    preregistration, preregistration_identity_with_mode = _load_preregistration(preregistration_path)
    root, root_identity_with_mode = _validated_campaign_root(preregistration)
    preregistration_identity = _detached_identity(preregistration_identity_with_mode)
    root_identity = _detached_identity(root_identity_with_mode)
    material_sources = _capture_sources(_baseline_material_paths(preregistration), "baseline material")
    material_identities = {
        role: _detached_identity(identity) for role, (_raw, identity) in material_sources.items()
    }

    experiment_contract_sha256 = hashlib.sha256(runner.canonical_json(runner.EXPERIMENT_CONTRACT)).hexdigest()
    if experiment_contract_sha256 != preregistration["experiment_contract_sha256"]:
        raise AuthorityError("experiment contract differs from the scientific preregistration")
    common_record: dict[str, object] = {
        "authorizations": {
            "arm_launch_authorized": False,
            "global_claim_authorized": False,
            "manifest_published": False,
            "mathematical_claim_authorized": False,
            "production_certified_authorized": False,
            "solver_run_authorized": False,
        },
        "baseline_admission_identity": material_identities["baseline_admission"],
        "baseline_fixed_replay_identity": material_identities["baseline_fixed_replay"],
        "baseline_incumbent_identity": material_identities["baseline_incumbent"],
        "baseline_rebuilt_metadata_identity": material_identities["baseline_rebuilt_metadata"],
        "baseline_rebuilt_model_identity": material_identities["baseline_rebuilt_model"],
        "campaign_root_identity": root_identity,
        "classification_contract_identity": material_identities["classification_contract"],
        "experiment_contract": runner.EXPERIMENT_CONTRACT,
        "preregistration_identity": preregistration_identity,
        "purpose": COMMON_PRESTATE_PURPOSE,
        "schema_version": COMMON_PRESTATE_SCHEMA,
        "scientific_input_set_sha256": preregistration["scientific_input_set_sha256"],
        "status": "PASS",
        "verdict": "AB16_COMMON_PRESTATE_FROZEN",
    }
    common_path = _absolute(preregistration["common_prestate_path"])
    common_identity = _expected_record_identity(common_path, common_record)

    topology = _exact_mapping(
        root["stage_topology"],
        {"gate1_v4", "prospective_ab16"},
        "campaign stage topology",
    )
    prospective = _exact_mapping(
        topology["prospective_ab16"],
        {
            "arm_selection_path",
            "arms",
            "manifest_path",
            "order",
            "requires_continuation_schema",
            "suite",
            "terminal_classification_path",
        },
        "prospective AB16 topology",
    )
    raw_arms = prospective["arms"]
    if type(raw_arms) is not list or len(raw_arms) != len(contract.ARM_SEQUENCE):
        raise AuthorityError("campaign root AB16 arm topology is incomplete")
    arms_by_slot: dict[str, Mapping[str, Any]] = {}
    for raw_arm in raw_arms:
        arm_record = _exact_mapping(
            raw_arm,
            {"arm", "attempt_dir", "configuration", "order", "slot", "unit_name"},
            "campaign root AB16 arm",
        )
        slot = arm_record["slot"]
        if type(slot) is not str or slot in arms_by_slot:
            raise AuthorityError("campaign root AB16 slot coverage drifted")
        arms_by_slot[slot] = arm_record
    if set(arms_by_slot) != set(contract.ARM_SEQUENCE):
        raise AuthorityError("campaign root AB16 slot coverage drifted")

    binding_paths_raw = preregistration["binding_paths"]
    slot_roots_raw = preregistration["slot_roots"]
    if not isinstance(binding_paths_raw, Mapping) or not isinstance(slot_roots_raw, Mapping):
        raise AuthorityError("scientific preregistration binding topology is malformed")
    binding_records: dict[str, dict[str, object]] = {}
    binding_paths: dict[str, Path] = {}
    for slot_index, slot in enumerate(contract.ARM_SEQUENCE):
        configuration, order, arm = _slot_parts(slot)
        plan = arms_by_slot[slot]
        slot_root = _absolute(slot_roots_raw[slot])
        if (
            plan["configuration"] != configuration
            or plan["order"] != order
            or plan["arm"] != arm
            or _absolute(plan["attempt_dir"]) != slot_root
        ):
            raise AuthorityError(f"campaign root and preregistration differ for {slot}")
        binding_records[slot] = {
            "arm": arm,
            "authorizations": {
                "arm_launch_authorized": False,
                "manifest_published": False,
                "solver_run_authorized": False,
            },
            "common_prestate_identity": common_identity,
            "configuration": configuration,
            "enabled_families": (
                [] if arm == "control" else list(runner.CONFIGURATION_FAMILIES[configuration])
            ),
            "order": order,
            "preregistration_identity": preregistration_identity,
            "purpose": ARM_BINDING_PURPOSE,
            "schema_version": ARM_BINDING_SCHEMA,
            "slot": slot,
            "slot_index": slot_index,
            "slot_root": str(slot_root),
            "status": "PASS",
            "unit_name": plan["unit_name"],
            "verdict": "AB16_ARM_BINDING_FROZEN",
        }
        binding_paths[slot] = _absolute(binding_paths_raw[slot])

    return {
        "binding_paths": binding_paths,
        "binding_records": binding_records,
        "common_path": common_path,
        "common_record": common_record,
        "preregistration": preregistration,
    }


def _binding_directory(expectations: Mapping[str, Any], *, create: bool) -> Path:
    binding_paths = expectations["binding_paths"]
    if not isinstance(binding_paths, Mapping) or not binding_paths:
        raise AuthorityError("arm binding path set is empty")
    parents = {_absolute(path).parent for path in binding_paths.values()}
    if len(parents) != 1:
        raise AuthorityError("arm binding paths do not share one directory")
    parent = parents.pop()
    if parent.exists() or parent.is_symlink():
        _existing_directory(parent, "arm binding directory")
    elif create:
        _existing_directory(parent.parent, "prospective AB16 directory")
        _make_directory(parent)
    else:
        raise AuthorityError("arm binding directory is absent")
    expected_names = {Path(path).name for path in binding_paths.values()}
    observed_names = {path.name for path in parent.iterdir()}
    unexpected = observed_names - expected_names
    if unexpected:
        raise AuthorityError(f"arm binding directory contains unexpected members: {sorted(unexpected)!r}")
    return parent


def _validate_existing_pre_manifest_records(
    expectations: Mapping[str, Any],
) -> tuple[dict[str, dict[str, object]], list[tuple[str, Path, Mapping[str, Any]]]]:
    targets: list[tuple[str, Path, Mapping[str, Any]]] = [
        ("common_prestate", expectations["common_path"], expectations["common_record"]),
    ]
    binding_paths = expectations["binding_paths"]
    binding_records = expectations["binding_records"]
    targets.extend(
        (f"arm_binding.{slot}", binding_paths[slot], binding_records[slot])
        for slot in contract.ARM_SEQUENCE
    )
    existing: dict[str, dict[str, object]] = {}
    missing: list[tuple[str, Path, Mapping[str, Any]]] = []
    for role, path, expected in targets:
        if path.exists() or path.is_symlink():
            try:
                metadata = path.lstat()
            except OSError as exc:
                raise AuthorityError(f"existing {role} is unavailable") from exc
            if path.is_symlink() or not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise AuthorityError(f"existing {role} is not one private regular file")
            raw, identity = _snapshot(path)
            if raw != canonical_json(expected):
                raise AuthorityError(f"existing {role} bytes differ from the replayed record")
            existing[role] = identity
        else:
            missing.append((role, path, expected))
    return existing, missing


def _replay_pre_manifest_inputs(preregistration_path: Path | str) -> dict[str, object]:
    expectations = _pre_manifest_expectations(preregistration_path)
    _existing_directory(Path(expectations["common_path"]).parent, "prospective AB16 directory")
    _binding_directory(expectations, create=False)
    identities, missing = _validate_existing_pre_manifest_records(expectations)
    if missing:
        raise AuthorityError(f"pre-manifest inputs are incomplete: {[role for role, _path, _record in missing]!r}")
    return {
        "arm_binding_identities": {
            slot: identities[f"arm_binding.{slot}"] for slot in contract.ARM_SEQUENCE
        },
        "common_prestate_identity": identities["common_prestate"],
    }


def materialize_pre_manifest_inputs(preregistration_path: Path | str) -> dict[str, object]:
    """Derive and publish the common prestate and all 16 attempt-free arm bindings."""

    expectations = _pre_manifest_expectations(preregistration_path)
    _existing_directory(Path(expectations["common_path"]).parent, "prospective AB16 directory")
    _binding_directory(expectations, create=True)
    existing, missing = _validate_existing_pre_manifest_records(expectations)
    published: list[str] = []
    for role, path, record in missing:
        existing[role] = _write_record(path, record)
        published.append(role)
    replayed = _replay_pre_manifest_inputs(preregistration_path)
    return {
        **replayed,
        "published_roles": published,
        "replayed_roles": sorted(set(existing) - set(published)),
        "status": "PRE_MANIFEST_INPUTS_READY",
    }


def build_manifest(preregistration_path: Path | str) -> dict[str, object]:
    """Publish the immutable scientific manifest without execution topology."""

    preregistration_path = _absolute(preregistration_path)
    preregistration, preregistration_identity = _load_preregistration(preregistration_path)
    replayed_before = _replay_pre_manifest_inputs(preregistration_path)
    materialization_sha256 = _materialization_digest(preregistration)
    replayed_after = _replay_pre_manifest_inputs(preregistration_path)
    materialization_after = _materialization_digest(preregistration)
    if replayed_after != replayed_before or materialization_after != materialization_sha256:
        raise AuthorityError("pre-manifest inputs changed during scientific manifest replay")
    scientific_input_sha256 = preregistration["scientific_input_set_sha256"]
    if type(scientific_input_sha256) is not str or SHA256_RE.fullmatch(scientific_input_sha256) is None:
        raise AuthorityError("scientific input-set digest is malformed")
    record = {
        "arm_sequence": list(contract.ARM_SEQUENCE),
        "configuration_families": {
            configuration: list(families) for configuration, families in runner.CONFIGURATION_FAMILIES.items()
        },
        "experiment_contract": runner.EXPERIMENT_CONTRACT,
        "forbidden_families": list(runner.FORBIDDEN_FAMILIES),
        "preregistration_sha256": preregistration_identity["sha256"],
        "purpose": runner.MANIFEST_PURPOSE,
        "runtime_parameters": _runtime_parameters(),
        "schema_version": runner.MANIFEST_SCHEMA,
        "scientific_input_set_sha256": scientific_input_sha256,
        "scientific_materialization_sha256": materialization_sha256,
        "seed": preregistration["seed"],
        "workers": preregistration["workers"],
    }
    try:
        runner.validate_manifest(record)
    except Exception as exc:
        raise AuthorityError("scientific manifest is invalid") from exc
    output = Path(preregistration["manifest_path"])
    identity = _write_record(output, record)
    return {"manifest": record, "manifest_identity": identity, "status": "PASS"}


def _load_manifest(
    preregistration: Mapping[str, Any],
    preregistration_identity: Mapping[str, Any],
) -> tuple[Mapping[str, Any], dict[str, object]]:
    record, identity = _load_record(preregistration["manifest_path"], "scientific manifest")
    try:
        checked = runner.validate_manifest(record)
    except Exception as exc:
        raise AuthorityError("scientific manifest is invalid") from exc
    if (
        checked["preregistration_sha256"] != preregistration_identity["sha256"]
        or checked["scientific_input_set_sha256"] != preregistration["scientific_input_set_sha256"]
    ):
        raise AuthorityError("scientific manifest preregistration join drifted")
    return checked, identity


def create_suite_selection(preregistration_path: Path | str) -> dict[str, object]:
    """Publish the non-launching suite selection after the scientific manifest."""

    preregistration, preregistration_identity = _load_preregistration(preregistration_path)
    manifest, manifest_identity = _load_manifest(preregistration, preregistration_identity)
    record: dict[str, object] = {
        "arm_sequence": list(contract.ARM_SEQUENCE),
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "manifest_identity": _detached_identity(manifest_identity),
        "preregistration_sha256": preregistration_identity["sha256"],
        "purpose": "AB16_SUITE_SELECTION_NO_ARM_LAUNCH",
        "schema_version": SUITE_SELECTION_SCHEMA,
        "scientific_input_set_sha256": preregistration["scientific_input_set_sha256"],
        "scientific_materialization_sha256": manifest["scientific_materialization_sha256"],
        "selection_id": "",
        "status": "PASS",
    }
    record["selection_id"] = hashlib.sha256(canonical_json(record)).hexdigest()
    identity = _write_record(Path(preregistration["suite_selection_path"]), record)
    return {"selection": record, "selection_identity": identity, "status": "PASS"}


def _load_suite_selection(
    preregistration: Mapping[str, Any],
    preregistration_identity: Mapping[str, Any],
    manifest: Mapping[str, Any],
    manifest_identity: Mapping[str, Any],
) -> tuple[Mapping[str, Any], dict[str, object]]:
    record, identity = _load_record(preregistration["suite_selection_path"], "suite selection")
    checked = _exact_mapping(
        record,
        {
            "arm_sequence",
            "authorizations",
            "manifest_identity",
            "preregistration_sha256",
            "purpose",
            "schema_version",
            "scientific_input_set_sha256",
            "scientific_materialization_sha256",
            "selection_id",
            "status",
        },
        "suite selection",
    )
    without_id = dict(checked)
    without_id["selection_id"] = ""
    if (
        checked["schema_version"] != SUITE_SELECTION_SCHEMA
        or checked["purpose"] != "AB16_SUITE_SELECTION_NO_ARM_LAUNCH"
        or checked["status"] != "PASS"
        or checked["authorizations"] != RESEARCH_ONLY_AUTHORIZATIONS
        or checked["arm_sequence"] != list(contract.ARM_SEQUENCE)
        or checked["manifest_identity"] != _detached_identity(manifest_identity)
        or checked["preregistration_sha256"] != preregistration_identity["sha256"]
        or checked["scientific_input_set_sha256"] != manifest["scientific_input_set_sha256"]
        or checked["scientific_materialization_sha256"] != manifest["scientific_materialization_sha256"]
        or checked["selection_id"] != hashlib.sha256(canonical_json(without_id)).hexdigest()
    ):
        raise AuthorityError("suite selection drifted")
    return checked, identity


def _load_preregistration(path: Path | str) -> tuple[Mapping[str, Any], dict[str, object]]:
    record, identity = _load_line_framed_record(path, "scientific preregistration")
    try:
        bootstrap.validate_path_preregistration(record, campaign_dir=record.get("campaign_dir", ""))
    except (bootstrap.BootstrapError, TypeError, ValueError) as exc:
        raise AuthorityError("scientific preregistration drifted") from exc
    if record["arm_sequence"] != list(contract.ARM_SEQUENCE):
        raise AuthorityError("scientific arm order differs from the classifier")
    campaign_dir = Path(record["campaign_dir"])
    root, _root_identity = _load_line_framed_record(campaign_dir / "campaign-root.json", "campaign root")
    try:
        root = bootstrap.authority.validate_campaign_root(root, campaign_dir=campaign_dir)
    except Exception as exc:
        raise AuthorityError("campaign root is invalid") from exc
    pinned_identity = root["strict_inputs"].get(bootstrap.PATH_PREREGISTRATION_INPUT_ROLE)
    if not isinstance(pinned_identity, Mapping) or any(
        pinned_identity.get(field) != identity[field] for field in ("sha256", "size_bytes")
    ):
        raise AuthorityError("scientific preregistration differs from the campaign root")
    return record, identity


def _scientific_source_paths(
    preregistration_path: Path,
    preregistration: Mapping[str, Any],
    slot: str,
) -> dict[str, Path]:
    if slot not in contract.ARM_SEQUENCE:
        raise AuthorityError(f"unknown scientific slot: {slot}")
    paths = _scientific_material_paths(preregistration)
    paths.update(
        {
            "scientific_manifest": Path(preregistration["manifest_path"]),
            "scientific_preregistration": preregistration_path,
            "suite_selection": Path(preregistration["suite_selection_path"]),
        }
    )
    return paths


def _execution_tool_paths(extra: Mapping[str, Path | str] | None) -> dict[str, Path]:
    paths = {role: RESEARCH_DIR / filename for role, filename in EXECUTION_TOOL_FILES.items()}
    for role, path in (extra or {}).items():
        if ROLE_RE.fullmatch(role) is None or role in paths:
            raise AuthorityError(f"invalid or duplicate execution-tool role: {role}")
        paths[role] = _absolute(path)
    return paths


def _campaign_execution_context(
    preregistration: Mapping[str, Any],
    *,
    repository_root: Path,
    slot: str,
    attempt_tool_identities: Mapping[str, Mapping[str, Any]],
) -> dict[str, object]:
    """Join retained Gate-1 ancestry to retry-local execution bytes."""

    campaign_dir = Path(preregistration["campaign_dir"])
    root, root_identity = _load_line_framed_record(campaign_dir / "campaign-root.json", "campaign root")
    try:
        root = bootstrap.authority.validate_campaign_root(root, campaign_dir=campaign_dir)
    except Exception as exc:
        raise AuthorityError("campaign root is invalid") from exc
    continuation_path = Path(root["stage_topology"]["gate1_v4"]["continuation_path"])
    continuation, continuation_identity = _load_line_framed_record(continuation_path, "Gate-1 continuation")
    try:
        bootstrap.authority.validate_continuation_authorization(continuation, root=root)
    except Exception as exc:
        raise AuthorityError("Gate-1 continuation is invalid") from exc

    root_tools = root["authority_tools"]
    system_roles = {
        "attestor_python": "attestor_python",
        "busctl": "busctl",
        "manager_attestor": "manager_attestor_v4",
        "manager_epoch_authority": "campaign_authority_v4",
        "python3_13": "python3_13",
        "sudo": "sudo",
        "systemctl": "systemctl",
        "systemd_run": "systemd_run",
    }
    code_roles = {
        "ab16_contract": "ab16_contract",
        "ab16_terminal_gate": "ab16_terminal_gate",
        "organic_arm_replay": "organic_arm_replay",
        "organic_arm_runner": "organic_arm_runner",
        "organic_resource_lifecycle": "organic_resource_lifecycle",
        "organic_resource_verifier": "organic_resource_verifier",
        "organic_unit_orchestrator": "organic_unit_orchestrator",
    }
    tools: dict[str, dict[str, object]] = {}
    for output_role, root_role in system_roles.items():
        tools[output_role] = _verify_detached_identity_with_mode(
            root_tools[root_role],
            f"campaign tool {root_role}",
        )
    epoch_attestor_python = root["manager_epoch"]["attestation_toolchain"]["python"]
    if any(epoch_attestor_python.get(field) != tools["attestor_python"][field] for field in tools["attestor_python"]):
        raise AuthorityError("campaign manager epoch attestor Python identity drifted")
    for output_role, attempt_role in code_roles.items():
        if attempt_role not in attempt_tool_identities:
            raise AuthorityError(f"attempt tool set lacks {attempt_role}")
        tools[output_role] = dict(_identity(attempt_tool_identities[attempt_role], f"attempt tool {attempt_role}"))
    git_identity = _verify_detached_identity_with_mode(root_tools["git"], "campaign git tool")
    package = {
        "manifest_identity": dict(root["package"]["manifest_identity"]),
        "package_id": root["package"]["package_id"],
        "seal_identity": dict(root["package"]["seal_identity"]),
    }
    unit_by_slot = {
        item["slot"]: item["unit_name"] for item in root["stage_topology"]["prospective_ab16"]["arms"]
    }
    if slot not in unit_by_slot:
        raise AuthorityError("campaign root lacks the selected AB16 slot")
    return {
        "authority_chain": {
            "campaign_root_identity": _detached_identity(root_identity),
            "continuation_identity": _detached_identity(continuation_identity),
            "manager_epoch_authority_identity": _detached_identity(tools["manager_epoch_authority"]),
            "package": package,
        },
        "campaign_id": root["campaign_id"],
        "campaign_root_identity": _detached_identity(root_identity),
        "continuation_identity": _detached_identity(continuation_identity),
        "manager_epoch": root["manager_epoch"],
        "package": package,
        "repository_git_tool_identity": git_identity,
        "repository_root": str(repository_root),
        "run_nonce": root["run_nonce"],
        "tool_identities": tools,
        "unit_name": unit_by_slot[slot],
    }


def _validate_execution_context(
    value: object,
    *,
    slot: str,
    allow_legacy_attestor_omission: bool = False,
) -> Mapping[str, Any]:
    record = _exact_mapping(
        value,
        {
            "authority_chain",
            "campaign_id",
            "campaign_root_identity",
            "continuation_identity",
            "manager_epoch",
            "package",
            "repository_git_tool_identity",
            "repository_root",
            "run_nonce",
            "tool_identities",
            "unit_name",
        },
        "attempt execution context",
    )
    if (
        type(record["campaign_id"]) is not str
        or SHA256_RE.fullmatch(record["campaign_id"]) is None
        or type(record["run_nonce"]) is not str
        or not record["run_nonce"]
        or type(record["repository_root"]) is not str
        or not Path(record["repository_root"]).is_absolute()
        or type(record["unit_name"]) is not str
        or not record["unit_name"].endswith(".service")
        or "/" in record["unit_name"]
    ):
        raise AuthorityError(f"attempt execution context is malformed for {slot}")
    try:
        bootstrap.authority.validate_manager_epoch(record["manager_epoch"])
    except Exception as exc:
        raise AuthorityError("attempt execution manager epoch is invalid") from exc
    _identity(record["repository_git_tool_identity"], "execution git identity")
    tools = _identity_map(record["tool_identities"], "execution tool identities", verify=True)
    expected_tool_roles = set(runner.EXECUTION_TOOL_ROLES)
    legacy_tool_roles = expected_tool_roles - {"attestor_python"}
    legacy_omission = allow_legacy_attestor_omission and set(tools) == legacy_tool_roles
    if set(tools) != expected_tool_roles and not legacy_omission:
        raise AuthorityError("execution tool role set drifted")
    if not legacy_omission:
        manager_python = record["manager_epoch"]["attestation_toolchain"]["python"]
        if any(manager_python.get(field) != tools["attestor_python"][field] for field in tools["attestor_python"]):
            raise AuthorityError("execution attestor Python differs from the manager epoch")
    _exact_mapping(
        record["package"],
        {"manifest_identity", "package_id", "seal_identity"},
        "execution package",
    )
    chain = _exact_mapping(
        record["authority_chain"],
        {"campaign_root_identity", "continuation_identity", "manager_epoch_authority_identity", "package"},
        "execution authority chain",
    )
    for field in ("campaign_root_identity", "continuation_identity", "manager_epoch_authority_identity"):
        _verify_detached_identity_with_mode(chain[field], f"execution authority {field}")
    for field in ("campaign_root_identity", "continuation_identity"):
        _verify_detached_identity_with_mode(record[field], f"execution {field}")
    if (
        chain["package"] != record["package"]
        or record["campaign_root_identity"] != chain["campaign_root_identity"]
        or record["continuation_identity"] != chain["continuation_identity"]
    ):
        raise AuthorityError("execution package differs from authority chain")
    return record


def _capture_sources(paths: Mapping[str, Path], label: str) -> dict[str, tuple[bytes, dict[str, object]]]:
    if not paths:
        raise AuthorityError(f"{label} set is empty")
    result: dict[str, tuple[bytes, dict[str, object]]] = {}
    for role in sorted(paths):
        if ROLE_RE.fullmatch(role) is None:
            raise AuthorityError(f"{label} role is invalid: {role}")
        result[role] = _snapshot(paths[role])
    return result


def _observe_clean_checkout(
    repository_root: Path | str,
    *,
    git_path: Path | str = "git",
) -> tuple[str, str]:
    root = _existing_directory(_absolute(repository_root), "repository root")
    git_environment = {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": os.defpath,
    }
    try:
        top_level = subprocess.run(
            (os.fspath(git_path), "rev-parse", "--show-toplevel"),
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            env=git_environment,
            timeout=GIT_OBSERVATION_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AuthorityError("repository Git top-level observation failed") from exc
    observed_top_level = top_level.stdout.strip()
    if (
        top_level.returncode != 0
        or top_level.stderr
        or not Path(observed_top_level).is_absolute()
        or _absolute(observed_top_level) != root
    ):
        raise AuthorityError("repository root is not the Git top-level")
    commands = (
        (os.fspath(git_path), "diff", "--no-ext-diff", "--quiet", "--"),
        (os.fspath(git_path), "diff", "--cached", "--quiet", "--"),
    )
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                cwd=root,
                check=False,
                capture_output=True,
                env=git_environment,
                timeout=GIT_OBSERVATION_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AuthorityError("repository Git invocation failed") from exc
        if completed.returncode != 0:
            raise AuthorityError("repository tracked tree or index is not clean")
    observed: list[str] = []
    for revision, label in (("HEAD", "HEAD"), ("HEAD^{tree}", "tree")):
        try:
            completed = subprocess.run(
                (os.fspath(git_path), "rev-parse", "--verify", revision),
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                env=git_environment,
                timeout=GIT_OBSERVATION_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AuthorityError(f"repository {label} observation failed") from exc
        value = completed.stdout.strip()
        if completed.returncode != 0 or completed.stderr or GIT_HEAD_RE.fullmatch(value) is None:
            raise AuthorityError(f"repository {label} observation failed")
        observed.append(value)
    return observed[0], observed[1]


def _observe_clean_head(repository_root: Path | str) -> str:
    return _observe_clean_checkout(repository_root)[0]


def prepare_baseline_provenance(
    preregistration_path: Path | str,
    *,
    repository_root: Path | str,
) -> dict[str, object]:
    """Bind baseline inputs to one tracked-clean checkout of the campaign's pinned HEAD."""

    preregistration_path = _absolute(preregistration_path)
    preregistration, _preregistration_identity = _load_preregistration(preregistration_path)
    campaign_dir = Path(preregistration["campaign_dir"])
    root, root_identity = _load_line_framed_record(campaign_dir / "campaign-root.json", "campaign root")
    try:
        root = bootstrap.authority.validate_campaign_root(root, campaign_dir=campaign_dir)
    except Exception as exc:
        raise AuthorityError("campaign root is invalid") from exc

    package = _exact_mapping(
        root["package"],
        {"manifest_identity", "package_dir", "package_id", "seal_identity"},
        "campaign package",
    )
    package_record = {
        "manifest_identity": _detached_identity(
            _verify_detached_identity_with_mode(package["manifest_identity"], "campaign package manifest")
        ),
        "package_id": package["package_id"],
        "seal_identity": _detached_identity(
            _verify_detached_identity_with_mode(package["seal_identity"], "campaign package seal")
        ),
    }
    if package_record["seal_identity"]["sha256"] != package_record["package_id"]:
        raise AuthorityError("campaign package identity drifted")

    root_tools = root["authority_tools"]
    if not isinstance(root_tools, Mapping):
        raise AuthorityError("campaign root tool map is malformed")
    if "git" not in root_tools:
        raise AuthorityError("campaign root lacks its package-pinned Git identity")
    git_identity_with_mode = _verify_detached_identity_with_mode(root_tools["git"], "campaign Git tool")
    git_identity = _detached_identity(git_identity_with_mode)

    repository_root = _existing_directory(_absolute(repository_root), "baseline repository root")
    head_before, tree_before = _observe_clean_checkout(
        repository_root,
        git_path=git_identity["path"],
    )
    if head_before != root["repository_head"]:
        raise AuthorityError("baseline checkout HEAD differs from the campaign root")

    root_inputs = root["strict_inputs"]
    if not isinstance(root_inputs, Mapping):
        raise AuthorityError("campaign root input map is malformed")
    input_identities: dict[str, dict[str, object]] = {}
    for role, relative in BASELINE_CHECKOUT_INPUT_PATHS.items():
        if role not in root_inputs:
            raise AuthorityError(f"campaign root lacks baseline input {role}")
        pinned_with_mode = _verify_detached_identity_with_mode(
            root_inputs[role],
            f"campaign baseline input {role}",
        )
        _raw, checkout_identity_with_mode = _snapshot(repository_root / relative)
        if any(
            checkout_identity_with_mode[field] != pinned_with_mode[field]
            for field in ("sha256", "size_bytes")
        ):
            raise AuthorityError(f"baseline checkout input differs from the campaign root: {role}")
        input_identities[role] = _detached_identity(checkout_identity_with_mode)

    head_after, tree_after = _observe_clean_checkout(
        repository_root,
        git_path=git_identity["path"],
    )
    if (head_after, tree_after) != (head_before, tree_before):
        raise AuthorityError("baseline checkout changed during provenance capture")
    if _snapshot(campaign_dir / "campaign-root.json")[1] != root_identity:
        raise AuthorityError("campaign root changed during provenance capture")

    record = {
        "authority_scope": "AB16_RESEARCH_ONLY",
        "campaign_root_identity": _detached_identity(root_identity),
        "git_identity": git_identity,
        "import_mode": BASELINE_IMPORT_MODE,
        "input_identities": input_identities,
        "package": package_record,
        "repository_head": head_before,
        "repository_root": str(repository_root),
        "repository_tree": tree_before,
        "schema_version": BASELINE_PROVENANCE_SCHEMA,
    }
    baseline_dir = Path(preregistration["baseline_rebuilt_model_path"]).parent
    for directory, label in (
        (baseline_dir.parent, "prospective AB16 directory"),
        (baseline_dir, "baseline directory"),
    ):
        if directory.exists() or directory.is_symlink():
            _existing_directory(directory, label)
        else:
            _make_directory(directory)
    provenance_path = baseline_dir / "campaign-provenance.json"
    provenance_identity = _write_bytes_exclusive(provenance_path, canonical_json(record) + b"\n")
    return {
        "campaign_provenance": record,
        "campaign_provenance_identity": _detached_identity(provenance_identity),
        "status": "BASELINE_CLEAN_CHECKOUT_PROVENANCE_READY",
    }


def _projection_digest(schema: str, identities: Mapping[str, Mapping[str, Any]]) -> str:
    projection = {
        "members": {
            role: {
                "mode": identities[role]["mode"],
                "sha256": identities[role]["sha256"],
                "size_bytes": identities[role]["size_bytes"],
            }
            for role in sorted(identities)
        },
        "schema": schema,
    }
    return hashlib.sha256(canonical_json(projection)).hexdigest()


def _attempt_directories(slot_root: Path) -> list[tuple[int, Path]]:
    if not slot_root.exists() and not slot_root.is_symlink():
        return []
    _existing_directory(slot_root, "slot root")
    members: list[tuple[int, Path]] = []
    for child in slot_root.iterdir():
        match = ATTEMPT_RE.fullmatch(child.name)
        if match is None or child.is_symlink() or not child.is_dir():
            raise AuthorityError(f"unknown or unsafe slot-root child: {child}")
        ordinal = int(match.group(1))
        if ordinal < 1 or child.name != f"attempt-{ordinal:04d}":
            raise AuthorityError(f"noncanonical attempt name: {child}")
        members.append((ordinal, child))
    members.sort()
    if [ordinal for ordinal, _path in members] != list(range(1, len(members) + 1)):
        raise AuthorityError(f"attempt ordinal gap under {slot_root}")
    return members


def _validate_input_set(
    attempt_dir: Path,
    preregistration: Mapping[str, Any],
    preregistration_identity: Mapping[str, Any],
) -> tuple[Mapping[str, Any], dict[str, object]]:
    record, identity = _load_record(attempt_dir / "attempt-input-set.json", "attempt input set")
    checked = _exact_mapping(
        record,
        {
            "authorizations",
            "input_set_sha256",
            "preregistration_identity",
            "preregistration_sha256",
            "repository_head",
            "schema_version",
            "scientific_input_set_sha256",
            "scientific_materialization_sha256",
            "source_strict_input_identities",
            "source_tool_identities",
            "strict_input_identities",
            "tool_identities",
        },
        "attempt input set",
    )
    strict_inputs = _identity_map(checked["strict_input_identities"], "strict input snapshots", verify=True)
    tools = _identity_map(checked["tool_identities"], "tool snapshots", verify=True)
    source_inputs = _identity_map(checked["source_strict_input_identities"], "strict input sources", verify=False)
    source_tools = _identity_map(checked["source_tool_identities"], "tool sources", verify=False)
    if set(strict_inputs) != set(source_inputs) or set(tools) != set(source_tools):
        raise AuthorityError("source and snapshot role sets differ")
    for snapshots, sources in ((strict_inputs, source_inputs), (tools, source_tools)):
        for role in snapshots:
            if any(snapshots[role][field] != sources[role][field] for field in ("sha256", "size_bytes")):
                raise AuthorityError(f"source/snapshot bytes differ for role {role}")
    manifest, _manifest_identity = _load_manifest(preregistration, preregistration_identity)
    material_roles = set(_scientific_material_paths(preregistration))
    if not material_roles.issubset(strict_inputs):
        raise AuthorityError("attempt input set lacks shared scientific material")
    materialization_sha256 = _scientific_materialization_digest(
        {role: strict_inputs[role] for role in material_roles}
    )
    if (
        checked["schema_version"] != INPUT_SET_SCHEMA
        or checked["authorizations"] != RESEARCH_ONLY_AUTHORIZATIONS
        or checked["preregistration_identity"] != preregistration_identity
        or checked["preregistration_sha256"] != preregistration_identity["sha256"]
        or type(checked["repository_head"]) is not str
        or GIT_HEAD_RE.fullmatch(checked["repository_head"]) is None
        or checked["scientific_input_set_sha256"] != preregistration["scientific_input_set_sha256"]
        or checked["scientific_input_set_sha256"] != manifest["scientific_input_set_sha256"]
        or checked["scientific_materialization_sha256"] != materialization_sha256
        or checked["scientific_materialization_sha256"] != manifest["scientific_materialization_sha256"]
        or checked["input_set_sha256"]
        != contract.attempt_input_set_sha256(
            preregistration_sha256=checked["preregistration_sha256"],
            repository_head=checked["repository_head"],
            strict_input_identities=strict_inputs,
            tool_identities=tools,
        )
    ):
        raise AuthorityError("attempt input-set joins drifted")
    return checked, identity


def _validate_attempt_execution(
    attempt_dir: Path,
    *,
    slot: str,
    ordinal: int,
    preregistration: Mapping[str, Any],
    preregistration_identity: Mapping[str, Any],
    input_record: Mapping[str, Any],
    input_identity: Mapping[str, Any],
    allow_legacy_attestor_omission: bool = False,
) -> tuple[Mapping[str, Any], dict[str, object]]:
    record, identity = _load_record(attempt_dir / "attempt-execution.json", "attempt execution")
    checked = _exact_mapping(
        record,
        {
            "authority_attempt_dir",
            "authority_chain",
            "authorizations",
            "campaign_id",
            "campaign_root_identity",
            "continuation_identity",
            "input_set_identity",
            "input_set_sha256",
            "manager_epoch",
            "manifest_identity",
            "package",
            "pre_run_authority_path",
            "preregistration_sha256",
            "repository_git_tool_identity",
            "repository_head",
            "repository_root",
            "run_dir",
            "run_nonce",
            "schema_version",
            "scientific_input_set_sha256",
            "scientific_materialization_sha256",
            "selection_path",
            "slot",
            "status",
            "suite_selection_identity",
            "support_dir",
            "tool_identities",
            "attempt_ordinal",
            "unit_name",
        },
        "attempt execution",
    )
    manifest, manifest_identity = _load_manifest(preregistration, preregistration_identity)
    _suite, suite_identity = _load_suite_selection(
        preregistration,
        preregistration_identity,
        manifest,
        manifest_identity,
    )
    run_dir = attempt_dir / "work"
    support_dir = attempt_dir / "execution-support"
    if (
        checked["schema_version"] != ATTEMPT_EXECUTION_SCHEMA
        or checked["status"] != "READY"
        or checked["authorizations"] != RESEARCH_ONLY_AUTHORIZATIONS
        or checked["slot"] != slot
        or checked["attempt_ordinal"] != ordinal
        or checked["preregistration_sha256"] != preregistration_identity["sha256"]
        or checked["input_set_identity"] != input_identity
        or checked["input_set_sha256"] != input_record["input_set_sha256"]
        or checked["repository_head"] != input_record["repository_head"]
        or checked["authority_attempt_dir"] != str(attempt_dir)
        or checked["run_dir"] != str(run_dir)
        or checked["support_dir"] != str(support_dir)
        or checked["pre_run_authority_path"] != str(run_dir / "pre-run-authority.json")
        or checked["selection_path"] != str(run_dir / "selection.json")
        or checked["manifest_identity"] != _detached_identity(manifest_identity)
        or checked["suite_selection_identity"] != _detached_identity(suite_identity)
        or checked["scientific_input_set_sha256"] != input_record["scientific_input_set_sha256"]
        or checked["scientific_materialization_sha256"] != input_record["scientific_materialization_sha256"]
    ):
        raise AuthorityError("attempt execution joins drifted")
    _existing_directory(run_dir, "attempt run directory")
    _existing_directory(support_dir, "attempt execution-support directory")
    context = {
        field: checked[field]
        for field in (
            "authority_chain",
            "campaign_id",
            "campaign_root_identity",
            "continuation_identity",
            "manager_epoch",
            "package",
            "repository_git_tool_identity",
            "repository_root",
            "run_nonce",
            "tool_identities",
            "unit_name",
        )
    }
    _validate_execution_context(
        context,
        slot=slot,
        allow_legacy_attestor_omission=allow_legacy_attestor_omission,
    )
    if hasattr(runner, "validate_attempt_execution"):
        try:
            runner.validate_attempt_execution(
                checked,
                allow_legacy_attestor_omission=allow_legacy_attestor_omission,
            )
        except Exception as exc:
            raise AuthorityError("runner rejected attempt execution") from exc
    return checked, identity


def _validate_open(
    attempt_dir: Path,
    *,
    slot: str,
    ordinal: int,
    preregistration: Mapping[str, Any],
    preregistration_identity: Mapping[str, Any],
    allow_legacy_attestor_omission: bool = False,
) -> tuple[Mapping[str, Any], Mapping[str, Any], dict[str, object]]:
    inputs, input_identity = _validate_input_set(attempt_dir, preregistration, preregistration_identity)
    execution, execution_identity = _validate_attempt_execution(
        attempt_dir,
        slot=slot,
        ordinal=ordinal,
        preregistration=preregistration,
        preregistration_identity=preregistration_identity,
        input_record=inputs,
        input_identity=input_identity,
        allow_legacy_attestor_omission=allow_legacy_attestor_omission,
    )
    record, identity = _load_record(attempt_dir / "attempt-open.json", "attempt-open receipt")
    checked = _exact_mapping(
        record,
        {
            "attempt_dir",
            "attempt_ordinal",
            "authorizations",
            "attempt_execution_identity",
            "input_set_identity",
            "input_set_sha256",
            "preregistration_sha256",
            "repository_head",
            "schema_version",
            "slot",
            "status",
        },
        "attempt-open receipt",
    )
    if (
        checked["schema_version"] != ATTEMPT_OPEN_SCHEMA
        or checked["status"] != "OPEN"
        or checked["slot"] != slot
        or checked["attempt_ordinal"] != ordinal
        or checked["attempt_dir"] != str(attempt_dir)
        or checked["authorizations"] != RESEARCH_ONLY_AUTHORIZATIONS
        or checked["attempt_execution_identity"] != execution_identity
        or checked["input_set_identity"] != input_identity
        or checked["input_set_sha256"] != inputs["input_set_sha256"]
        or checked["preregistration_sha256"] != preregistration_identity["sha256"]
        or checked["repository_head"] != inputs["repository_head"]
    ):
        raise AuthorityError("attempt-open receipt drifted")
    if execution["repository_head"] != checked["repository_head"]:
        raise AuthorityError("attempt execution/open repository join drifted")
    return checked, inputs, identity


def _validate_formal_selection(
    attempt_dir: Path,
    *,
    slot: str,
    ordinal: int,
    preregistration: Mapping[str, Any],
    preregistration_identity: Mapping[str, Any],
    input_record: Mapping[str, Any],
) -> tuple[Mapping[str, Any], dict[str, object], Mapping[str, Any], dict[str, object]]:
    input_identity = _snapshot(attempt_dir / "attempt-input-set.json")[1]
    execution, execution_identity_with_mode = _validate_attempt_execution(
        attempt_dir,
        slot=slot,
        ordinal=ordinal,
        preregistration=preregistration,
        preregistration_identity=preregistration_identity,
        input_record=input_record,
        input_identity=input_identity,
    )
    execution_identity = _detached_identity(execution_identity_with_mode)
    manifest, manifest_identity_with_mode = _load_manifest(preregistration, preregistration_identity)
    selection, selection_identity = _load_record(execution["selection_path"], "formal arm selection")
    pre_run, pre_run_identity_with_mode = _load_record(
        execution["pre_run_authority_path"],
        "pre-run authority",
    )
    pre_run_identity = _detached_identity(pre_run_identity_with_mode)
    try:
        runner.validate_selection(
            selection,
            manifest=manifest,
            execution=execution,
            input_set=input_record,
        )
        lifecycle.validate_pre_run_authority(
            pre_run,
            manifest=manifest,
            expected_slot=slot,
            attempt_execution=execution,
            attempt_execution_identity=execution_identity,
        )
        lifecycle.validate_runner_selection(
            selection,
            pre_run_authority=pre_run,
            pre_run_authority_identity=pre_run_identity,
        )
    except Exception as exc:
        raise AuthorityError("formal selection chain is invalid") from exc
    if (
        selection["attempt_execution_identity"] != execution_identity
        or selection["manifest_identity"] != _detached_identity(manifest_identity_with_mode)
        or selection["pre_run_authority_identity"] != pre_run_identity
        or selection["slot"] != slot
        or selection["attempt_ordinal"] != ordinal
        or selection["preregistration_sha256"] != preregistration_identity["sha256"]
    ):
        raise AuthorityError("formal selection attempt joins drifted")
    return selection, selection_identity, execution, execution_identity_with_mode


def _optional_selection(
    attempt_dir: Path,
    *,
    slot: str,
    ordinal: int,
    preregistration: Mapping[str, Any],
    preregistration_identity: Mapping[str, Any],
    input_record: Mapping[str, Any],
) -> tuple[Mapping[str, Any] | None, dict[str, object] | None]:
    path = attempt_dir / "selection-binding.json"
    if not path.exists() and not path.is_symlink():
        return None, None
    record, identity = _load_record(path, "selection binding")
    checked = _exact_mapping(
        record,
        {
            "attempt_execution_identity",
            "attempt_ordinal",
            "authorizations",
            "input_set_identity",
            "manifest_identity",
            "preregistration_sha256",
            "schema_version",
            "selection_identity",
            "slot",
            "status",
        },
        "selection binding",
    )
    selection, selection_identity, execution, execution_identity = _validate_formal_selection(
        attempt_dir,
        slot=slot,
        ordinal=ordinal,
        preregistration=preregistration,
        preregistration_identity=preregistration_identity,
        input_record=input_record,
    )
    input_identity = _snapshot(attempt_dir / "attempt-input-set.json")[1]
    if (
        checked["schema_version"] != SELECTION_BINDING_SCHEMA
        or checked["status"] != "BOUND"
        or checked["authorizations"] != RESEARCH_ONLY_AUTHORIZATIONS
        or checked["slot"] != slot
        or checked["attempt_ordinal"] != ordinal
        or checked["preregistration_sha256"] != preregistration_identity["sha256"]
        or checked["selection_identity"] != selection_identity
        or checked["attempt_execution_identity"] != execution_identity
        or checked["input_set_identity"] != input_identity
        or checked["manifest_identity"] != selection["manifest_identity"]
        or checked["selection_identity"]["path"] != execution["selection_path"]
    ):
        raise AuthorityError("selection binding drifted")
    return checked, identity


def _optional_envelope(
    attempt_dir: Path,
    *,
    slot: str,
    ordinal: int,
    preregistration_identity: Mapping[str, Any],
    input_record: Mapping[str, Any],
    input_identity: Mapping[str, Any],
    selection_identity: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any] | None, dict[str, object] | None]:
    path = attempt_dir / "attempt-result.json"
    if not path.exists() and not path.is_symlink():
        return None, None
    record, identity = _load_record(path, "attempt result envelope")
    checked = _exact_mapping(
        record,
        {
            "attempt_ordinal",
            "authorizations",
            "envelope_id",
            "evidence_identities",
            "failure_code",
            "input_set_identity",
            "input_set_sha256",
            "outcome",
            "preregistration_identity",
            "preregistration_sha256",
            "repository_head",
            "retry_disposition",
            "schema_version",
            "selection_binding_identity",
            "slot",
        },
        "attempt result envelope",
    )
    evidence = checked["evidence_identities"]
    if type(evidence) is not dict:
        raise AuthorityError("attempt evidence identities must be an object")
    for role, member in evidence.items():
        if type(role) is not str or ROLE_RE.fullmatch(role) is None:
            raise AuthorityError("attempt evidence role is invalid")
        _verify_identity(member, f"attempt evidence {role}")
    without_id = dict(checked)
    without_id["envelope_id"] = ""
    expected_id = hashlib.sha256(canonical_json(without_id)).hexdigest()
    if (
        checked["schema_version"] != RESULT_ENVELOPE_SCHEMA
        or checked["slot"] != slot
        or checked["attempt_ordinal"] != ordinal
        or checked["authorizations"] != RESEARCH_ONLY_AUTHORIZATIONS
        or checked["envelope_id"] != expected_id
        or checked["preregistration_identity"] != preregistration_identity
        or checked["preregistration_sha256"] != preregistration_identity["sha256"]
        or checked["input_set_identity"] != input_identity
        or checked["input_set_sha256"] != input_record["input_set_sha256"]
        or checked["repository_head"] != input_record["repository_head"]
        or checked["selection_binding_identity"] != selection_identity
    ):
        raise AuthorityError("attempt result envelope joins drifted")
    if checked["outcome"] == CREDIBLE_TERMINAL:
        if checked["failure_code"] is not None or checked["retry_disposition"] != "SLOT_CLOSED":
            raise AuthorityError("credible envelope terminal fields drifted")
        if selection_identity is None or "arm_gate" not in evidence:
            raise AuthorityError("credible envelope lacks selection or arm gate")
    elif checked["outcome"] == CREDIBILITY_INCOMPLETE:
        if (
            type(checked["failure_code"]) is not str
            or not checked["failure_code"]
            or checked["retry_disposition"] != "SAME_SLOT_RETRY_ALLOWED"
        ):
            raise AuthorityError("incomplete envelope terminal fields drifted")
    else:
        raise AuthorityError("attempt outcome is unsupported")
    return checked, identity


def _optional_abandoned(
    attempt_dir: Path,
    *,
    slot: str,
    ordinal: int,
    preregistration_identity: Mapping[str, Any],
) -> tuple[Mapping[str, Any] | None, dict[str, object] | None]:
    path = attempt_dir / "attempt-abandoned.json"
    if not path.exists() and not path.is_symlink():
        return None, None
    record, identity = _load_record(path, "attempt abandonment")
    checked = _exact_mapping(
        record,
        {
            "attempt_dir",
            "attempt_ordinal",
            "authorizations",
            "failure_code",
            "preregistration_identity",
            "preregistration_sha256",
            "retry_disposition",
            "schema_version",
            "slot",
            "status",
        },
        "attempt abandonment",
    )
    if any(
        (attempt_dir / name).exists() or (attempt_dir / name).is_symlink()
        for name in ("attempt-open.json", "selection-binding.json", "attempt-result.json")
    ):
        raise AuthorityError("abandoned attempt contains a committed open, selection, or result")
    if (
        checked["schema_version"] != ATTEMPT_ABANDONED_SCHEMA
        or checked["status"] != "ABANDONED"
        or checked["slot"] != slot
        or checked["attempt_ordinal"] != ordinal
        or checked["attempt_dir"] != str(attempt_dir)
        or checked["authorizations"] != RESEARCH_ONLY_AUTHORIZATIONS
        or type(checked["failure_code"]) is not str
        or not checked["failure_code"]
        or checked["preregistration_identity"] != preregistration_identity
        or checked["preregistration_sha256"] != preregistration_identity["sha256"]
        or checked["retry_disposition"] != "SAME_SLOT_RETRY_ALLOWED"
    ):
        raise AuthorityError("attempt abandonment drifted")
    return checked, identity


def replay_campaign(
    preregistration_path: Path | str,
    *,
    _allow_uncommitted: tuple[str, int] | None = None,
) -> dict[str, object]:
    """Rebuild retry state from immutable attempt receipts on disk."""

    preregistration_path = _absolute(preregistration_path)
    preregistration, preregistration_identity = _load_preregistration(preregistration_path)
    state = contract.new_consumption_state()
    active: dict[str, object] | None = None
    attempts_summary: list[dict[str, object]] = []
    slot_attempt_counts: dict[str, int] = {}
    manifest, _manifest_identity = _load_manifest(preregistration, preregistration_identity)
    if _materialization_digest(preregistration) != manifest["scientific_materialization_sha256"]:
        raise AuthorityError("shared scientific material drifted from the campaign manifest")
    campaign_scientific_digest = preregistration["scientific_input_set_sha256"]

    for slot_index, slot in enumerate(contract.ARM_SEQUENCE):
        slot_root = Path(preregistration["slot_roots"][slot])
        attempts = _attempt_directories(slot_root)
        slot_attempt_counts[slot] = len(attempts)
        if slot_index > state["next_index"] and attempts:
            raise AuthorityError("future slot contains an attempt")
        for attempt_index, (ordinal, attempt_dir) in enumerate(attempts):
            if state["next_index"] >= len(contract.ARM_SEQUENCE) or contract.ARM_SEQUENCE[state["next_index"]] != slot:
                raise AuthorityError("attempt exists after its slot closed or out of order")
            abandoned, abandoned_identity = _optional_abandoned(
                attempt_dir,
                slot=slot,
                ordinal=ordinal,
                preregistration_identity=preregistration_identity,
            )
            if abandoned is not None:
                state = contract.transition_consumption_state(
                    state,
                    {
                        "attempt_ordinal": ordinal,
                        "event": "PRESELECTION_FAILURE",
                        "reason": abandoned["failure_code"],
                        "slot": slot,
                    },
                )
                attempts_summary.append(
                    {
                        "attempt_ordinal": ordinal,
                        "envelope_identity": abandoned_identity,
                        "input_set_sha256": None,
                        "outcome": CREDIBILITY_INCOMPLETE,
                        "repository_head": None,
                        "slot": slot,
                    }
                )
                continue
            if _allow_uncommitted == (slot, ordinal):
                if attempt_index != len(attempts) - 1:
                    raise AuthorityError("uncommitted attempt has a later sibling")
                if any(
                    (attempt_dir / name).exists() or (attempt_dir / name).is_symlink()
                    for name in ("attempt-open.json", "selection-binding.json", "attempt-result.json")
                ):
                    raise AuthorityError("only an unpublished prepare attempt may be abandoned")
                attempts_summary.append(
                    {
                        "attempt_ordinal": ordinal,
                        "envelope_identity": None,
                        "input_set_sha256": None,
                        "outcome": None,
                        "repository_head": None,
                        "slot": slot,
                    }
                )
                active = {
                    "attempt_dir": str(attempt_dir),
                    "attempt_ordinal": ordinal,
                    "slot": slot,
                    "uncommitted": True,
                }
                break
            result_path = attempt_dir / "attempt-result.json"
            # The pre-R16 r6 stop is already closed and lacks only this role.  Active attempts have no result
            # envelope, so they cannot enter the read-only compatibility path or recapture with a fallback.
            _open, inputs, _open_identity = _validate_open(
                attempt_dir,
                slot=slot,
                ordinal=ordinal,
                preregistration=preregistration,
                preregistration_identity=preregistration_identity,
                allow_legacy_attestor_omission=result_path.exists() or result_path.is_symlink(),
            )
            input_identity = _snapshot(attempt_dir / "attempt-input-set.json")[1]
            if inputs["scientific_input_set_sha256"] != campaign_scientific_digest:
                raise AuthorityError("attempt scientific inputs differ from the campaign anchor")
            _selection, selection_binding_identity = _optional_selection(
                attempt_dir,
                slot=slot,
                ordinal=ordinal,
                preregistration=preregistration,
                preregistration_identity=preregistration_identity,
                input_record=inputs,
            )
            envelope, envelope_identity = _optional_envelope(
                attempt_dir,
                slot=slot,
                ordinal=ordinal,
                preregistration_identity=preregistration_identity,
                input_record=inputs,
                input_identity=input_identity,
                selection_identity=selection_binding_identity,
            )
            summary = {
                "attempt_ordinal": ordinal,
                "envelope_identity": envelope_identity,
                "input_set_sha256": inputs["input_set_sha256"],
                "outcome": None if envelope is None else envelope["outcome"],
                "repository_head": inputs["repository_head"],
                "slot": slot,
            }
            attempts_summary.append(summary)
            if envelope is None:
                if attempt_index != len(attempts) - 1:
                    raise AuthorityError("unresolved attempt has a later sibling")
                if selection_binding_identity is not None:
                    state = contract.transition_consumption_state(
                        state,
                        {"attempt_ordinal": ordinal, "event": "SELECTION_CREATED", "reason": None, "slot": slot},
                    )
                active = {"attempt_dir": str(attempt_dir), "attempt_ordinal": ordinal, "slot": slot}
                break
            if selection_binding_identity is None:
                if envelope["outcome"] != CREDIBILITY_INCOMPLETE:
                    raise AuthorityError("credible attempt lacks a selection")
                state = contract.transition_consumption_state(
                    state,
                    {
                        "attempt_ordinal": ordinal,
                        "event": "PRESELECTION_FAILURE",
                        "reason": envelope["failure_code"],
                        "slot": slot,
                    },
                )
            else:
                state = contract.transition_consumption_state(
                    state,
                    {"attempt_ordinal": ordinal, "event": "SELECTION_CREATED", "reason": None, "slot": slot},
                )
                event = "ARM_CREDIBILITY_PASS" if envelope["outcome"] == CREDIBLE_TERMINAL else "ARM_CREDIBILITY_INCOMPLETE"
                state = contract.transition_consumption_state(
                    state,
                    {
                        "attempt_ordinal": ordinal,
                        "event": event,
                        "reason": None if event == "ARM_CREDIBILITY_PASS" else envelope["failure_code"],
                        "slot": slot,
                    },
                )
            if envelope["outcome"] == CREDIBLE_TERMINAL and attempt_index != len(attempts) - 1:
                raise AuthorityError("credible attempt has a later retry")
        if active is not None or state["next_index"] == slot_index:
            for future_slot in contract.ARM_SEQUENCE[slot_index + 1 :]:
                if _attempt_directories(Path(preregistration["slot_roots"][future_slot])):
                    raise AuthorityError("future slot contains an attempt")
            break

    return {
        "active_attempt": active,
        "attempts": attempts_summary,
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "consumption_state": state,
        "preregistration_identity": preregistration_identity,
        "schema_version": REPLAY_SCHEMA,
        "slot_attempt_counts": slot_attempt_counts,
        "status": "PASS",
    }


def abandon_attempt(
    preregistration_path: Path | str,
    *,
    slot: str,
    attempt_ordinal: int,
    failure_code: str,
) -> dict[str, object]:
    """Append an explicit retry marker for a prepare killed before its open receipt."""

    if type(attempt_ordinal) is not int or attempt_ordinal <= 0:
        raise AuthorityError("attempt abandonment requires a positive ordinal")
    if type(failure_code) is not str or not failure_code:
        raise AuthorityError("attempt abandonment requires a failure code")
    preregistration_path = _absolute(preregistration_path)
    _preregistration, preregistration_identity = _load_preregistration(preregistration_path)
    replay = replay_campaign(
        preregistration_path,
        _allow_uncommitted=(slot, attempt_ordinal),
    )
    active = replay["active_attempt"]
    if (
        type(active) is not dict
        or active.get("slot") != slot
        or active.get("attempt_ordinal") != attempt_ordinal
        or active.get("uncommitted") is not True
    ):
        raise AuthorityError("abandonment does not target the sole unpublished attempt")
    attempt_dir = Path(active["attempt_dir"])
    record = {
        "attempt_dir": str(attempt_dir),
        "attempt_ordinal": attempt_ordinal,
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "failure_code": failure_code,
        "preregistration_identity": preregistration_identity,
        "preregistration_sha256": preregistration_identity["sha256"],
        "retry_disposition": "SAME_SLOT_RETRY_ALLOWED",
        "schema_version": ATTEMPT_ABANDONED_SCHEMA,
        "slot": slot,
        "status": "ABANDONED",
    }
    identity = _write_record(attempt_dir / "attempt-abandoned.json", record)
    replayed = replay_campaign(preregistration_path)
    if replayed["active_attempt"] is not None:
        raise AuthorityError("abandoned attempt remained active after replay")
    state = replayed["consumption_state"]
    current = state["slots"][state["next_index"]]
    if current["slot"] != slot or current["state"] != "RETRYABLE" or current["attempt_count"] != attempt_ordinal:
        raise AuthorityError("abandoned attempt did not become retryable")
    return {
        "attempt_abandoned_identity": identity,
        "attempt_ordinal": attempt_ordinal,
        "failure_code": failure_code,
        "retry_disposition": "SAME_SLOT_RETRY_ALLOWED",
        "slot": slot,
        "status": "ATTEMPT_ABANDONED",
    }


def prepare_attempt(
    preregistration_path: Path | str,
    *,
    repository_root: Path | str,
    slot: str | None = None,
    additional_strict_inputs: Mapping[str, Path | str] | None = None,
    additional_execution_tools: Mapping[str, Path | str] | None = None,
    execution_context: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Create the next append-only attempt and bind its actual input bytes."""

    preregistration_path = _absolute(preregistration_path)
    replay = replay_campaign(preregistration_path)
    if replay["active_attempt"] is not None:
        raise AuthorityError("the current attempt must close before retry")
    state = replay["consumption_state"]
    next_index = state["next_index"]
    if next_index == len(contract.ARM_SEQUENCE):
        raise AuthorityError("all preregistered slots are already complete")
    expected_slot = contract.ARM_SEQUENCE[next_index]
    if slot is not None and slot != expected_slot:
        raise AuthorityError(f"next preregistered slot is {expected_slot}")
    slot = expected_slot
    preregistration, preregistration_identity = _load_preregistration(preregistration_path)
    manifest, manifest_identity = _load_manifest(preregistration, preregistration_identity)
    _suite, suite_identity = _load_suite_selection(
        preregistration,
        preregistration_identity,
        manifest,
        manifest_identity,
    )
    ordinal = replay["slot_attempt_counts"].get(slot, 0) + 1

    scientific_paths = _scientific_source_paths(preregistration_path, preregistration, slot)
    for role, path in (additional_strict_inputs or {}).items():
        if ROLE_RE.fullmatch(role) is None or role in scientific_paths:
            raise AuthorityError(f"invalid or duplicate strict-input role: {role}")
        scientific_paths[role] = _absolute(path)
    tool_paths = _execution_tool_paths(additional_execution_tools)

    repository_root = _absolute(repository_root)
    head_before = _observe_clean_head(repository_root)
    scientific_sources = _capture_sources(scientific_paths, "strict input")
    tool_sources = _capture_sources(tool_paths, "execution tool")
    head_after = _observe_clean_head(repository_root)
    if head_before != head_after:
        raise AuthorityError("repository HEAD changed during input capture")
    material_roles = set(_scientific_material_paths(preregistration))
    captured_materialization_sha256 = _scientific_materialization_digest(
        {role: scientific_sources[role][1] for role in material_roles}
    )
    if captured_materialization_sha256 != manifest["scientific_materialization_sha256"]:
        raise AuthorityError("shared scientific material differs from the campaign manifest")

    slot_root = Path(preregistration["slot_roots"][slot])
    if not slot_root.exists() and not slot_root.is_symlink():
        parent = slot_root.parent
        if not parent.exists() and not parent.is_symlink():
            grandparent = _existing_directory(parent.parent, "prospective AB16 directory")
            if grandparent != Path(preregistration["campaign_dir"]) / "prospective-ab16":
                raise AuthorityError("slot-root parent is outside the preregistered topology")
            _make_directory(parent)
        else:
            _existing_directory(parent, "slot-root parent")
        _make_directory(slot_root)
    else:
        _existing_directory(slot_root, "slot root")
    attempt_dir = slot_root / f"attempt-{ordinal:04d}"
    _make_directory(attempt_dir)
    input_snapshot_dir = attempt_dir / "input-snapshots"
    tool_snapshot_dir = attempt_dir / "tool-snapshots"
    work_dir = attempt_dir / "work"
    support_dir = attempt_dir / "execution-support"
    for directory in (input_snapshot_dir, tool_snapshot_dir, work_dir, support_dir):
        _make_directory(directory)

    def publish_snapshots(
        sources: Mapping[str, tuple[bytes, dict[str, object]]],
        directory: Path,
    ) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
        snapshots: dict[str, dict[str, object]] = {}
        source_identities: dict[str, dict[str, object]] = {}
        for index, role in enumerate(sorted(sources)):
            raw, source_identity = sources[role]
            snapshots[role] = _write_bytes_exclusive(directory / f"{index:04d}.bin", raw)
            source_identities[role] = source_identity
        return snapshots, source_identities

    strict_inputs, source_strict_inputs = publish_snapshots(scientific_sources, input_snapshot_dir)
    tools, source_tools = publish_snapshots(tool_sources, tool_snapshot_dir)
    materialization_sha256 = _scientific_materialization_digest(
        {role: strict_inputs[role] for role in material_roles}
    )
    if materialization_sha256 != manifest["scientific_materialization_sha256"]:
        raise AuthorityError("shared scientific material differs from the campaign manifest")
    input_set_sha256 = contract.attempt_input_set_sha256(
        preregistration_sha256=preregistration_identity["sha256"],
        repository_head=head_before,
        strict_input_identities=strict_inputs,
        tool_identities=tools,
    )
    input_record = {
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "input_set_sha256": input_set_sha256,
        "preregistration_identity": preregistration_identity,
        "preregistration_sha256": preregistration_identity["sha256"],
        "repository_head": head_before,
        "schema_version": INPUT_SET_SCHEMA,
        "scientific_input_set_sha256": preregistration["scientific_input_set_sha256"],
        "scientific_materialization_sha256": materialization_sha256,
        "source_strict_input_identities": source_strict_inputs,
        "source_tool_identities": source_tools,
        "strict_input_identities": strict_inputs,
        "tool_identities": tools,
    }
    input_identity = _write_record(attempt_dir / "attempt-input-set.json", input_record)
    context = (
        _campaign_execution_context(
            preregistration,
            repository_root=repository_root,
            slot=slot,
            attempt_tool_identities=tools,
        )
        if execution_context is None
        else dict(_validate_execution_context(execution_context, slot=slot))
    )
    execution_record = {
        "attempt_ordinal": ordinal,
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "authority_attempt_dir": str(attempt_dir),
        "authority_chain": context["authority_chain"],
        "campaign_id": context["campaign_id"],
        "campaign_root_identity": context["campaign_root_identity"],
        "continuation_identity": context["continuation_identity"],
        "input_set_identity": input_identity,
        "input_set_sha256": input_set_sha256,
        "manager_epoch": context["manager_epoch"],
        "manifest_identity": _detached_identity(manifest_identity),
        "package": context["package"],
        "pre_run_authority_path": str(work_dir / "pre-run-authority.json"),
        "preregistration_sha256": preregistration_identity["sha256"],
        "repository_git_tool_identity": context["repository_git_tool_identity"],
        "repository_head": head_before,
        "repository_root": str(repository_root),
        "run_dir": str(work_dir),
        "run_nonce": context["run_nonce"],
        "schema_version": ATTEMPT_EXECUTION_SCHEMA,
        "scientific_input_set_sha256": preregistration["scientific_input_set_sha256"],
        "scientific_materialization_sha256": materialization_sha256,
        "selection_path": str(work_dir / "selection.json"),
        "slot": slot,
        "status": "READY",
        "suite_selection_identity": _detached_identity(suite_identity),
        "support_dir": str(support_dir),
        "tool_identities": context["tool_identities"],
        "unit_name": context["unit_name"],
    }
    execution_identity = _write_record(attempt_dir / "attempt-execution.json", execution_record)
    open_record = {
        "attempt_dir": str(attempt_dir),
        "attempt_ordinal": ordinal,
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "attempt_execution_identity": execution_identity,
        "input_set_identity": input_identity,
        "input_set_sha256": input_set_sha256,
        "preregistration_sha256": preregistration_identity["sha256"],
        "repository_head": head_before,
        "schema_version": ATTEMPT_OPEN_SCHEMA,
        "slot": slot,
        "status": "OPEN",
    }
    open_identity = _write_record(attempt_dir / "attempt-open.json", open_record)
    return {
        "attempt_dir": str(attempt_dir),
        "attempt_open_identity": open_identity,
        "attempt_execution_identity": execution_identity,
        "attempt_ordinal": ordinal,
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "input_set_identity": input_identity,
        "input_set_sha256": input_set_sha256,
        "preregistration_sha256": preregistration_identity["sha256"],
        "repository_head": head_before,
        "slot": slot,
        "status": "ATTEMPT_PREPARED",
        "work_dir": str(work_dir),
    }


def _slot_parts(slot: str) -> tuple[str, str, str]:
    for configuration in runner.CONFIGURATION_FAMILIES:
        for order in runner.ORDERS:
            for arm in runner.ARMS:
                if slot == f"{configuration}-{order}-{arm}":
                    return configuration, order, arm
    raise AuthorityError(f"unknown AB16 slot: {slot}")


def _launch_environment_record(value: Mapping[str, str] | None) -> dict[str, object]:
    variables = (
        {
            "DBUS_SESSION_BUS_ADDRESS": os.environ.get("DBUS_SESSION_BUS_ADDRESS", ""),
            "HOME": os.environ.get("HOME", ""),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": os.environ.get("PATH", ""),
            "PYTHONHASHSEED": "0",
            "TZ": "UTC",
            "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", ""),
        }
        if value is None
        else dict(value)
    )
    record = {
        "clear_ambient": True,
        "schema_version": lifecycle.LAUNCH_ENVIRONMENT_SCHEMA,
        "variables": variables,
    }
    try:
        lifecycle.validate_launch_environment(record)
    except Exception as exc:
        raise AuthorityError("launch environment is invalid") from exc
    return record


def _manager_capture(
    execution: Mapping[str, Any],
    supplied: Mapping[str, object] | None,
) -> Mapping[str, Any]:
    tools = execution["tool_identities"]
    try:
        bootstrap.authority.validate_manager_epoch(execution["manager_epoch"])
        attestor_python = tools["attestor_python"]
        expected_python = execution["manager_epoch"]["attestation_toolchain"]["python"]
        if any(expected_python.get(field) != attestor_python[field] for field in attestor_python):
            raise AuthorityError("attempt attestor Python differs from the manager epoch")
        capture = (
            bootstrap.authority.capture_manager_epoch_with_transcript(
                attestor_path=tools["manager_attestor"]["path"],
                busctl_path=tools["busctl"]["path"],
                python_path=attestor_python["path"],
                sudo_path=tools["sudo"]["path"],
            )
            if supplied is None
            else dict(supplied)
        )
        checked = _exact_mapping(
            capture,
            {"manager_epoch", "transcript"},
            "manager epoch capture",
        )
        bootstrap.authority.validate_manager_epoch(checked["manager_epoch"])
        bootstrap.authority.validate_manager_epoch_capture_transcript(
            checked["transcript"],
            expected_epoch=checked["manager_epoch"],
        )
    except Exception as exc:
        raise AuthorityError("manager epoch capture is invalid") from exc
    if checked["manager_epoch"] != execution["manager_epoch"]:
        raise AuthorityError("manager epoch drifted before selection production")
    return checked


def _admitted_baseline_incumbent_digest(inputs: Mapping[str, Any]) -> str:
    strict_inputs = inputs["strict_input_identities"]
    source_inputs = inputs["source_strict_input_identities"]
    admission_identity = strict_inputs["baseline_admission"]
    admission, observed_identity = _load_line_framed_record(
        admission_identity["path"],
        "baseline admission",
    )
    if observed_identity != admission_identity:
        raise AuthorityError("baseline admission attempt snapshot identity drifted")
    expected = admission.get("expected_baseline")
    digest = expected.get("incumbent_sha256") if isinstance(expected, Mapping) else None
    try:
        admitted_digest = runner._validate_baseline_admission(  # noqa: SLF001 - shared producer/runner join
            admission,
            baseline_incumbent_identity=_detached_identity(strict_inputs["baseline_incumbent"]),
            baseline_incumbent_source_identity=source_inputs["baseline_incumbent"],
            selection={"baseline_incumbent_sha256": digest},
        )
    except Exception as exc:
        raise AuthorityError("baseline admission cannot authorize the selection digest") from exc
    incumbent, incumbent_identity = _load_line_framed_record(
        strict_inputs["baseline_incumbent"]["path"],
        "baseline incumbent",
    )
    if incumbent_identity != strict_inputs["baseline_incumbent"]:
        raise AuthorityError("baseline incumbent attempt snapshot identity drifted")
    if hashlib.sha256(canonical_json(incumbent)).hexdigest() != admitted_digest:
        raise AuthorityError("baseline incumbent semantic digest differs from its admission")
    return admitted_digest


def produce_selection(
    preregistration_path: Path | str,
    *,
    slot: str,
    attempt_ordinal: int,
    selection_nonce: str,
    manager_capture: Mapping[str, object] | None = None,
    launch_environment: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Publish the two runner inputs for the active per-attempt topology."""

    preregistration_path = _absolute(preregistration_path)
    preregistration, preregistration_identity = _load_preregistration(preregistration_path)
    replay = replay_campaign(preregistration_path)
    active = replay["active_attempt"]
    if active is None or active["slot"] != slot or active["attempt_ordinal"] != attempt_ordinal:
        raise AuthorityError("selection production does not target the active attempt")
    attempt_dir = Path(active["attempt_dir"])
    _open, inputs, _open_identity = _validate_open(
        attempt_dir,
        slot=slot,
        ordinal=attempt_ordinal,
        preregistration=preregistration,
        preregistration_identity=preregistration_identity,
    )
    input_identity = _snapshot(attempt_dir / "attempt-input-set.json")[1]
    execution, execution_identity_with_mode = _validate_attempt_execution(
        attempt_dir,
        slot=slot,
        ordinal=attempt_ordinal,
        preregistration=preregistration,
        preregistration_identity=preregistration_identity,
        input_record=inputs,
        input_identity=input_identity,
    )
    execution_identity = _detached_identity(execution_identity_with_mode)
    manifest, manifest_identity_with_mode = _load_manifest(preregistration, preregistration_identity)
    suite, suite_identity_with_mode = _load_suite_selection(
        preregistration,
        preregistration_identity,
        manifest,
        manifest_identity_with_mode,
    )
    if _observe_clean_head(execution["repository_root"]) != execution["repository_head"]:
        raise AuthorityError("repository HEAD drifted before selection production")

    capture = _manager_capture(execution, manager_capture)
    support_dir = Path(execution["support_dir"])
    transcript_identity = _write_record(
        support_dir / "preselection-manager-transcript.json",
        capture["transcript"],
    )
    epoch_record = lifecycle.build_epoch_observation(
        phase="preselection",
        slot=slot,
        observed_epoch=capture["manager_epoch"],
        observed_at_monotonic_ns=time.monotonic_ns(),
        capture_transcript_identity=transcript_identity,
    )
    epoch_identity = _write_record(support_dir / "preselection-manager-epoch.json", epoch_record)
    environment_identity = _write_record(
        support_dir / "launch-environment.json",
        _launch_environment_record(launch_environment),
    )

    configuration, order, arm = _slot_parts(slot)
    run_dir = Path(execution["run_dir"])
    strict_inputs = inputs["strict_input_identities"]
    binding_role = f"arm_binding.{slot}"
    for role in ("baseline_admission", "baseline_incumbent", "common_prestate", binding_role):
        if role not in strict_inputs:
            raise AuthorityError(f"attempt input set lacks {role}")
    baseline_incumbent_sha256 = _admitted_baseline_incumbent_digest(inputs)
    pre_run_tools = {role: execution["tool_identities"][role] for role in lifecycle.TOOL_ROLES}
    output_names = {
        "attempt_result": "result.json",
        "cleanup": "cleanup.json",
        "detached_replay": "detached-replay.json",
        "inner": "inner-lifecycle.json",
        "preterminal": "preterminal-resource.json",
        "release": "release-token.json",
        "resource_verification": "resource-verification.json",
        "terminal": "terminal-envelope.json",
    }
    phases = ("launch", "preterminal", "release", "terminal", "cleanup", "detached-replay")
    expected_payload_status = {"exit_code": 0, "expectation": "SUCCESS", "signal": 0}
    pre_run: dict[str, object] = {
        "arm": arm,
        "arm_binding_identity": _detached_identity(strict_inputs[binding_role]),
        "arm_launch_authorized": False,
        "arm_selection_write_authorized": True,
        "attempt_dir": str(run_dir),
        "attempt_execution_identity": execution_identity,
        "attempt_ordinal": attempt_ordinal,
        "authority_chain": execution["authority_chain"],
        "baseline_admission_identity": _detached_identity(strict_inputs["baseline_admission"]),
        "baseline_incumbent_sha256": baseline_incumbent_sha256,
        "campaign_id": execution["campaign_id"],
        "campaign_root_identity": execution["campaign_root_identity"],
        "common_prestate_identity": _detached_identity(strict_inputs["common_prestate"]),
        "configuration": configuration,
        "continuation_identity": execution["continuation_identity"],
        "epoch_observation_paths": {phase: str(run_dir / f"manager-epoch-{phase}.json") for phase in phases},
        "epoch_transcript_paths": {phase: str(run_dir / f"manager-transcript-{phase}.json") for phase in phases},
        "execution_class": "FORMAL_AB16",
        "expected_payload_status": expected_payload_status,
        "launch": {
            "cwd": execution["repository_root"],
            "environment_identity": environment_identity,
            "payload_argv": [
                pre_run_tools["python3_13"]["path"],
                "-I",
                pre_run_tools["organic_arm_runner"]["path"],
                "--selection",
                execution["selection_path"],
            ],
            "python3_13_path": pre_run_tools["python3_13"]["path"],
            "supervisor_argv": [
                pre_run_tools["python3_13"]["path"],
                "-I",
                pre_run_tools["organic_resource_lifecycle"]["path"],
                "supervise",
                "--pre-run",
                execution["pre_run_authority_path"],
                "--selection",
                execution["selection_path"],
            ],
            "systemctl_path": pre_run_tools["systemctl"]["path"],
            "systemd_run_path": pre_run_tools["systemd_run"]["path"],
        },
        "manager_epoch": execution["manager_epoch"],
        "order": order,
        "output_paths": {role: str(run_dir / name) for role, name in output_names.items()},
        "package": execution["package"],
        "pre_run_authority_path": execution["pre_run_authority_path"],
        "prelaunch_allowlist": ["pre-run-authority.json", "selection.json"],
        "preflight_results": {
            "epoch_identity_pass": True,
            "head_identity_pass": True,
            "package_replay_pass": True,
            "path_preregistration_pass": True,
            "resource_contract_pass": True,
            "slot_order_pass": True,
            "strict_inputs_replay_pass": True,
            "tool_identities_replay_pass": True,
        },
        "preregistration_sha256": preregistration_identity["sha256"],
        "preselection_epoch_identity": epoch_identity,
        "preselection_transcript_identity": transcript_identity,
        "prospective_manifest_identity": _detached_identity(manifest_identity_with_mode),
        "purpose": lifecycle.PRE_RUN_PURPOSE,
        "repository_git_tool_identity": execution["repository_git_tool_identity"],
        "repository_head": execution["repository_head"],
        "repository_root": execution["repository_root"],
        "resource_contract": lifecycle.FORMAL_RESOURCE_CONTRACT,
        "run_nonce": execution["run_nonce"],
        "runner_selection_path": execution["selection_path"],
        "schema_version": lifecycle.PRE_RUN_AUTHORITY_SCHEMA,
        "seed": manifest["seed"],
        "slot": slot,
        "solver_run_authorized": False,
        "status": "PASS",
        "strict_input_identities": strict_inputs,
        "suite_selection_identity": _detached_identity(suite_identity_with_mode),
        "tool_identities": pre_run_tools,
        "unit_name": execution["unit_name"],
        "verdict": "AB16_ORGANIC_PRE_RUN_AUTHORITY_PASS",
        "workers": manifest["workers"],
    }
    try:
        lifecycle.validate_pre_run_authority(
            pre_run,
            manifest=manifest,
            suite_selection=suite,
            expected_slot=slot,
            attempt_execution=execution,
            attempt_execution_identity=execution_identity,
        )
    except Exception as exc:
        raise AuthorityError("pre-run authority is invalid") from exc
    pre_run_identity_with_mode = _write_record(Path(execution["pre_run_authority_path"]), pre_run)
    pre_run_identity = _detached_identity(pre_run_identity_with_mode)
    enabled_families = [] if arm == "control" else list(runner.CONFIGURATION_FAMILIES[configuration])
    selection: dict[str, object] = {
        "arm": arm,
        "arm_binding_identity": pre_run["arm_binding_identity"],
        "attempt_dir": str(run_dir),
        "attempt_execution_identity": execution_identity,
        "attempt_ordinal": attempt_ordinal,
        "authority_chain": execution["authority_chain"],
        "authorizations": {
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "organic_arm_launch_authorized": True,
            "production_certified_authorized": False,
            "solver_run_authorized": True,
        },
        "baseline_admission_identity": pre_run["baseline_admission_identity"],
        "baseline_incumbent_sha256": pre_run["baseline_incumbent_sha256"],
        "campaign_id": execution["campaign_id"],
        "common_prestate_identity": pre_run["common_prestate_identity"],
        "configuration": configuration,
        "enabled_families": enabled_families,
        "execution_class": "FORMAL_AB16",
        "expected_payload_status": expected_payload_status,
        "fresh_process_required": True,
        "manifest_identity": _detached_identity(manifest_identity_with_mode),
        "order": order,
        "pre_run_authority_identity": pre_run_identity,
        "preregistration_sha256": preregistration_identity["sha256"],
        "purpose": runner.SELECTION_PURPOSE,
        "repository_git_tool_identity": execution["repository_git_tool_identity"],
        "repository_head": execution["repository_head"],
        "repository_root": execution["repository_root"],
        "run_nonce": execution["run_nonce"],
        "schema_version": runner.SELECTION_SCHEMA,
        "seed": manifest["seed"],
        "selection_nonce": selection_nonce,
        "slot": slot,
        "unit_name": execution["unit_name"],
        "workers": manifest["workers"],
    }
    try:
        runner.validate_selection(selection, manifest=manifest, execution=execution, input_set=inputs)
        lifecycle.validate_runner_selection(
            selection,
            pre_run_authority=pre_run,
            pre_run_authority_identity=pre_run_identity,
        )
    except Exception as exc:
        raise AuthorityError("formal arm selection is invalid") from exc
    selection_identity = _write_record(Path(execution["selection_path"]), selection)
    return {
        "attempt_execution_identity": execution_identity_with_mode,
        "attempt_ordinal": attempt_ordinal,
        "pre_run_authority_identity": pre_run_identity_with_mode,
        "selection": selection,
        "selection_identity": selection_identity,
        "slot": slot,
        "status": "SELECTION_PRODUCED",
    }


def bind_selection(
    preregistration_path: Path | str,
    *,
    slot: str,
    attempt_ordinal: int,
    selection_path: Path | str,
) -> dict[str, object]:
    preregistration, preregistration_identity = _load_preregistration(preregistration_path)
    replay = replay_campaign(preregistration_path)
    active = replay["active_attempt"]
    if active is None or active["slot"] != slot or active["attempt_ordinal"] != attempt_ordinal:
        raise AuthorityError("selection does not target the active attempt")
    attempt_dir = Path(active["attempt_dir"])
    _open, inputs, _open_identity = _validate_open(
        attempt_dir,
        slot=slot,
        ordinal=attempt_ordinal,
        preregistration=preregistration,
        preregistration_identity=preregistration_identity,
    )
    selection, selection_identity, _execution, execution_identity = _validate_formal_selection(
        attempt_dir,
        slot=slot,
        ordinal=attempt_ordinal,
        preregistration=preregistration,
        preregistration_identity=preregistration_identity,
        input_record=inputs,
    )
    if _absolute(selection_path) != Path(selection_identity["path"]):
        raise AuthorityError("selection path differs from the active attempt execution")
    input_identity = _snapshot(attempt_dir / "attempt-input-set.json")[1]
    record = {
        "attempt_execution_identity": execution_identity,
        "attempt_ordinal": attempt_ordinal,
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "input_set_identity": input_identity,
        "manifest_identity": selection["manifest_identity"],
        "preregistration_sha256": preregistration_identity["sha256"],
        "schema_version": SELECTION_BINDING_SCHEMA,
        "selection_identity": selection_identity,
        "slot": slot,
        "status": "BOUND",
    }
    identity = _write_record(attempt_dir / "selection-binding.json", record)
    return {"selection_binding_identity": identity, "status": "SELECTION_BOUND"}


def _load_line_record(path: Path | str, label: str) -> tuple[Mapping[str, Any], dict[str, object]]:
    raw, identity = _snapshot(path)
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise AuthorityError(f"{label} must use its canonical line framing")
    try:
        value = contract.strict_loads(raw[:-1])
    except contract.ContractError as exc:
        raise AuthorityError(f"{label} is not canonical strict JSON") from exc
    if type(value) is not dict:
        raise AuthorityError(f"{label} must be a JSON object")
    return value, identity


def _load_pinned_source(identity: object, label: str) -> ModuleType:
    checked = _verify_identity(identity, label)
    module_name = f"_ab16_{label.replace(' ', '_')}_{checked['sha256'][:16]}"
    existing = sys.modules.get(module_name)
    if isinstance(existing, ModuleType):
        return existing
    loader = importlib.machinery.SourceFileLoader(module_name, str(checked["path"]))
    specification = importlib.util.spec_from_loader(module_name, loader)
    if specification is None:
        raise AuthorityError(f"cannot load pinned {label}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    try:
        loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise AuthorityError(f"pinned {label} could not be loaded") from exc
    return module


def _build_credible_gate(
    attempt_dir: Path,
    *,
    slot: str,
    ordinal: int,
    preregistration: Mapping[str, Any],
    preregistration_identity: Mapping[str, Any],
    input_record: Mapping[str, Any],
    selection_binding: Mapping[str, Any],
    evidence_paths: Mapping[str, Path | str],
) -> tuple[dict[str, object], dict[str, object], dict[str, dict[str, object]]]:
    required_roles = {"arm_result", "arithmetic_receipt", "resource_preterminal", "resource_receipt"}
    if set(evidence_paths) != required_roles:
        raise AuthorityError("credible closure requires real result, arithmetic, and resource receipts")
    selection, selection_identity_with_mode, execution, _execution_identity = _validate_formal_selection(
        attempt_dir,
        slot=slot,
        ordinal=ordinal,
        preregistration=preregistration,
        preregistration_identity=preregistration_identity,
        input_record=input_record,
    )
    if selection_binding["selection_identity"] != selection_identity_with_mode:
        raise AuthorityError("bound selection changed before credible closure")

    arm_result, arm_result_identity = _load_line_record(evidence_paths["arm_result"], "organic arm result")
    arithmetic_receipt, arithmetic_identity = _load_line_record(
        evidence_paths["arithmetic_receipt"],
        "arithmetic replay receipt",
    )
    resource_preterminal, resource_preterminal_identity = _load_record(
        evidence_paths["resource_preterminal"],
        "preterminal resource receipt",
    )
    resource_receipt, resource_identity = _load_record(
        evidence_paths["resource_receipt"],
        "detached resource receipt",
    )
    if Path(arm_result_identity["path"]) != Path(execution["run_dir"]) / "result.json":
        raise AuthorityError("credible closure did not use the active runner result")

    tools = execution["tool_identities"]
    arithmetic_tool = _load_pinned_source(tools["organic_arm_replay"], "organic arm replay")
    resource_tool = _load_pinned_source(tools["organic_resource_verifier"], "resource verifier")
    gate_tool = _load_pinned_source(tools["ab16_terminal_gate"], "terminal gate")
    try:
        replayed_arithmetic = arithmetic_tool.replay_arm(
            arm_result=arm_result_identity["path"],
            cut_free_replay=arithmetic_receipt["cut_free_replay_identity"]["path"],
            replay_tool_identity=_detached_identity(tools["organic_arm_replay"]),
        )
        pre_run_snapshot = resource_tool.snapshot_json(selection["pre_run_authority_identity"]["path"])
        selection_snapshot = resource_tool.snapshot_json(selection_identity_with_mode["path"])
        inner_snapshot = resource_tool.snapshot_json(resource_preterminal["inner_identity"]["path"])
        preterminal_snapshot = resource_tool.snapshot_json(resource_preterminal["preterminal_identity"]["path"])
        payload_snapshot = resource_tool.snapshot_runner_json(arm_result_identity["path"])
        replayed_preterminal = resource_tool.verify_preterminal(
            pre_run=pre_run_snapshot,
            selection=selection_snapshot,
            inner=inner_snapshot,
            preterminal=preterminal_snapshot,
            payload_result=payload_snapshot,
            verifier_tool_identity=tools["organic_resource_verifier"],
        )
        replayed_resource = resource_tool.verify_detached(
            pre_run=pre_run_snapshot,
            selection=selection_snapshot,
            inner=inner_snapshot,
            preterminal=preterminal_snapshot,
            payload_result=payload_snapshot,
            resource=resource_tool.snapshot_json(resource_preterminal_identity["path"]),
            release=resource_tool.snapshot_json(resource_receipt["release_identity"]["path"]),
            terminal=resource_tool.snapshot_json(resource_receipt["terminal_identity"]["path"]),
            cleanup=resource_tool.snapshot_json(resource_receipt["cleanup_identity"]["path"]),
            detached_epoch=resource_tool.snapshot_json(
                resource_receipt["detached_epoch_observation_identity"]["path"]
            ),
            verifier_tool_identity=tools["organic_resource_verifier"],
        )
        gate = gate_tool.build_arm_gate(
            selection=selection,
            selection_identity=_detached_identity(selection_identity_with_mode),
            arm_result=arm_result,
            arm_result_identity=_detached_identity(arm_result_identity),
            arithmetic_receipt=arithmetic_receipt,
            arithmetic_receipt_identity=_detached_identity(arithmetic_identity),
            replayed_arithmetic_receipt=replayed_arithmetic,
            arithmetic_tool_identity=_detached_identity(tools["organic_arm_replay"]),
            resource_receipt=resource_receipt,
            resource_receipt_identity=_detached_identity(resource_identity),
            replayed_resource_receipt=replayed_resource,
            resource_preterminal_receipt=resource_preterminal,
            resource_preterminal_identity=_detached_identity(resource_preterminal_identity),
            replayed_resource_preterminal_receipt=replayed_preterminal,
            resource_verifier_tool_identity=_detached_identity(tools["organic_resource_verifier"]),
            experiment_contract=runner.EXPERIMENT_CONTRACT,
            gate_tool_identity=_detached_identity(tools["ab16_terminal_gate"]),
        )
    except Exception as exc:
        raise AuthorityError("credible evidence replay or terminal gate failed") from exc
    if gate.get("status") != "PASS" or gate.get("credibility_status") != "PASS" or gate.get("slot") != slot:
        raise AuthorityError("derived arm credibility gate did not pass")
    gate_path = Path(execution["run_dir"]) / "arm-gate.json"
    if gate_path.exists() or gate_path.is_symlink():
        existing, gate_identity = _load_record(gate_path, "derived arm credibility gate")
        if existing != gate:
            raise AuthorityError("existing arm credibility gate differs from replay")
    else:
        gate_identity = _write_record(gate_path, gate)
    identities = {
        "arm_gate": gate_identity,
        "arm_result": arm_result_identity,
        "arithmetic_receipt": arithmetic_identity,
        "resource_preterminal": resource_preterminal_identity,
        "resource_receipt": resource_identity,
    }
    return dict(gate), gate_identity, identities


def close_attempt(
    preregistration_path: Path | str,
    *,
    slot: str,
    attempt_ordinal: int,
    outcome: str,
    failure_code: str | None = None,
    evidence_paths: Mapping[str, Path | str] | None = None,
) -> dict[str, object]:
    """Close the active attempt; incomplete closure leaves its slot retryable."""

    preregistration, preregistration_identity = _load_preregistration(preregistration_path)
    replay = replay_campaign(preregistration_path)
    active = replay["active_attempt"]
    if active is None or active["slot"] != slot or active["attempt_ordinal"] != attempt_ordinal:
        raise AuthorityError("only the active attempt may be closed")
    attempt_dir = Path(active["attempt_dir"])
    _open, inputs, _open_identity = _validate_open(
        attempt_dir,
        slot=slot,
        ordinal=attempt_ordinal,
        preregistration=preregistration,
        preregistration_identity=preregistration_identity,
    )
    input_identity = _snapshot(attempt_dir / "attempt-input-set.json")[1]
    selection, selection_binding_identity = _optional_selection(
        attempt_dir,
        slot=slot,
        ordinal=attempt_ordinal,
        preregistration=preregistration,
        preregistration_identity=preregistration_identity,
        input_record=inputs,
    )
    evidence_identities: dict[str, dict[str, object]] = {}
    if outcome == CREDIBLE_TERMINAL:
        if failure_code is not None or selection is None:
            raise AuthorityError("credible closure requires a bound formal selection with no failure code")
        _gate, _gate_identity, evidence_identities = _build_credible_gate(
            attempt_dir,
            slot=slot,
            ordinal=attempt_ordinal,
            preregistration=preregistration,
            preregistration_identity=preregistration_identity,
            input_record=inputs,
            selection_binding=selection,
            evidence_paths=evidence_paths or {},
        )
        retry_disposition = "SLOT_CLOSED"
    elif outcome == CREDIBILITY_INCOMPLETE:
        if type(failure_code) is not str or not failure_code:
            raise AuthorityError("incomplete closure requires a failure code")
        for role, path in sorted((evidence_paths or {}).items()):
            if ROLE_RE.fullmatch(role) is None:
                raise AuthorityError(f"invalid evidence role: {role}")
            _raw, evidence_identities[role] = _snapshot(path)
        retry_disposition = "SAME_SLOT_RETRY_ALLOWED"
    else:
        raise AuthorityError("attempt outcome is unsupported")
    envelope: dict[str, object] = {
        "attempt_ordinal": attempt_ordinal,
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "envelope_id": "",
        "evidence_identities": evidence_identities,
        "failure_code": failure_code,
        "input_set_identity": input_identity,
        "input_set_sha256": inputs["input_set_sha256"],
        "outcome": outcome,
        "preregistration_identity": preregistration_identity,
        "preregistration_sha256": preregistration_identity["sha256"],
        "repository_head": inputs["repository_head"],
        "retry_disposition": retry_disposition,
        "schema_version": RESULT_ENVELOPE_SCHEMA,
        "selection_binding_identity": selection_binding_identity,
        "slot": slot,
    }
    envelope["envelope_id"] = hashlib.sha256(canonical_json(envelope)).hexdigest()
    envelope_identity = _write_record(attempt_dir / "attempt-result.json", envelope)
    return {
        "attempt_result_identity": envelope_identity,
        "authorizations": dict(RESEARCH_ONLY_AUTHORIZATIONS),
        "outcome": outcome,
        "retry_disposition": retry_disposition,
        "status": "ATTEMPT_CLOSED",
    }


def _role_paths(values: Sequence[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        role, separator, path = value.partition("=")
        if not separator or ROLE_RE.fullmatch(role) is None or role in result or not path:
            raise AuthorityError(f"expected unique ROLE=PATH value, got {value!r}")
        result[role] = _absolute(path)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize_parser = subparsers.add_parser("materialize-pre-manifest")
    materialize_parser.add_argument("--preregistration", type=Path, required=True)
    manifest_parser = subparsers.add_parser("build-manifest")
    manifest_parser.add_argument("--preregistration", type=Path, required=True)
    baseline_parser = subparsers.add_parser("prepare-baseline-provenance")
    baseline_parser.add_argument("--preregistration", type=Path, required=True)
    baseline_parser.add_argument("--repository-root", type=Path, required=True)
    suite_parser = subparsers.add_parser("suite-selection")
    suite_parser.add_argument("--preregistration", type=Path, required=True)
    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("--preregistration", type=Path, required=True)
    recover_parser = subparsers.add_parser("recover-staging")
    recover_parser.add_argument("--path", type=Path, required=True)
    abandon_parser = subparsers.add_parser("abandon-attempt")
    abandon_parser.add_argument("--preregistration", type=Path, required=True)
    abandon_parser.add_argument("--slot", required=True)
    abandon_parser.add_argument("--attempt-ordinal", type=int, required=True)
    abandon_parser.add_argument("--failure-code", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--preregistration", type=Path, required=True)
    prepare_parser.add_argument("--repository-root", type=Path, required=True)
    prepare_parser.add_argument("--slot")
    prepare_parser.add_argument("--strict-input", action="append", default=[])
    prepare_parser.add_argument("--execution-tool", action="append", default=[])
    produce_parser = subparsers.add_parser("produce-selection")
    produce_parser.add_argument("--preregistration", type=Path, required=True)
    produce_parser.add_argument("--slot", required=True)
    produce_parser.add_argument("--attempt-ordinal", type=int, required=True)
    produce_parser.add_argument("--selection-nonce", required=True)
    bind_parser = subparsers.add_parser("bind-selection")
    bind_parser.add_argument("--preregistration", type=Path, required=True)
    bind_parser.add_argument("--slot", required=True)
    bind_parser.add_argument("--attempt-ordinal", type=int, required=True)
    bind_parser.add_argument("--selection", type=Path, required=True)
    close_parser = subparsers.add_parser("close")
    close_parser.add_argument("--preregistration", type=Path, required=True)
    close_parser.add_argument("--slot", required=True)
    close_parser.add_argument("--attempt-ordinal", type=int, required=True)
    close_parser.add_argument("--outcome", choices=(CREDIBLE_TERMINAL, CREDIBILITY_INCOMPLETE), required=True)
    close_parser.add_argument("--failure-code")
    close_parser.add_argument("--evidence", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "materialize-pre-manifest":
        result = materialize_pre_manifest_inputs(args.preregistration)
    elif args.command == "build-manifest":
        result = build_manifest(args.preregistration)
    elif args.command == "prepare-baseline-provenance":
        result = prepare_baseline_provenance(
            args.preregistration,
            repository_root=args.repository_root,
        )
    elif args.command == "suite-selection":
        result = create_suite_selection(args.preregistration)
    elif args.command == "replay":
        result = replay_campaign(args.preregistration)
    elif args.command == "recover-staging":
        result = recover_staging(args.path)
    elif args.command == "abandon-attempt":
        result = abandon_attempt(
            args.preregistration,
            slot=args.slot,
            attempt_ordinal=args.attempt_ordinal,
            failure_code=args.failure_code,
        )
    elif args.command == "prepare":
        result = prepare_attempt(
            args.preregistration,
            repository_root=args.repository_root,
            slot=args.slot,
            additional_strict_inputs=_role_paths(args.strict_input),
            additional_execution_tools=_role_paths(args.execution_tool),
        )
    elif args.command == "produce-selection":
        result = produce_selection(
            args.preregistration,
            slot=args.slot,
            attempt_ordinal=args.attempt_ordinal,
            selection_nonce=args.selection_nonce,
        )
    elif args.command == "bind-selection":
        result = bind_selection(
            args.preregistration,
            slot=args.slot,
            attempt_ordinal=args.attempt_ordinal,
            selection_path=args.selection,
        )
    else:
        result = close_attempt(
            args.preregistration,
            slot=args.slot,
            attempt_ordinal=args.attempt_ordinal,
            outcome=args.outcome,
            failure_code=args.failure_code,
            evidence_paths=_role_paths(args.evidence),
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
