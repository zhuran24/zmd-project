#!/usr/bin/env python3
"""Independent verifier for one AB16 organic arm lifecycle.

The verifier intentionally does not import the lifecycle recorder, the unit
orchestrator, or the arm runner.  It reads each authority/evidence file once
through an ``O_NOFOLLOW`` descriptor, validates the immutable joins, and
derives resource and terminal facts from raw systemd/cgroup fields.

Importing this module never starts a subprocess, unit, or solver.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
from types import ModuleType
from typing import Any


PRE_RUN_SCHEMA = "noncert-cuts-ab16-organic-pre-run-authority-v2"
RUNNER_SELECTION_SCHEMA = "noncert-cuts-ab16-organic-arm-selection-v1"
DRILL_SELECTION_SCHEMA = "noncert-cuts-ab16-organic-drill-selection-v1"
SEALED_EXECUTION_SOURCE_SCHEMA = "noncert-cuts-ab16-sealed-execution-source-v1"
SELECTED_BYTE_LAUNCH_SCHEMA = "noncert-cuts-ab16-selected-byte-launch-v1"
SNAPSHOT_MANIFEST_SCHEMA = "noncert-cuts-ab16-repository-snapshot-v1"
SNAPSHOT_MATERIALIZATION_SCHEMA = "noncert-cuts-ab16-repository-snapshot-materialization-v1"
EPOCH_SCHEMA = "noncert-cuts-ab16-manager-epoch-observation-v2"
INNER_SCHEMA = "noncert-cuts-ab16-inner-lifecycle-v2"
PRETERMINAL_SCHEMA = "noncert-cuts-ab16-preterminal-resource-v2"
RESOURCE_SCHEMA = "noncert-cuts-ab16-resource-verification-v2"
RELEASE_SCHEMA = "noncert-cuts-ab16-release-token-v2"
TERMINAL_SCHEMA = "noncert-cuts-ab16-terminal-envelope-v2"
CLEANUP_SCHEMA = "noncert-cuts-ab16-cleanup-v2"
DETACHED_SCHEMA = "noncert-cuts-ab16-detached-resource-terminal-v2"
REFERENCE_ACQUISITION_SCHEMA = "noncert-cuts-ab16-unit-reference-acquisition-v1"
REFERENCE_RELEASE_SCHEMA = "noncert-cuts-ab16-unit-reference-release-v1"

PURPOSE = "PROSPECTIVE_AB16_ORGANIC_ARM_RESOURCE_AUTHORITY"
PRE_RUN_PURPOSE = "PROSPECTIVE_AB16_ORGANIC_ARM_PRE_RUN_AUTHORITY"
RUNNER_PURPOSE = "prospective_noncert_cuts_ab16_formal_arm"
DRILL_PURPOSE = "noncert_cuts_ab16_disposable_live_drill"
LAUNCH_ENVIRONMENT_SCHEMA = "noncert-cuts-ab16-launch-environment-v2"
LAUNCH_ENVIRONMENT_KEYS = frozenset(
    {
        "DBUS_SESSION_BUS_ADDRESS",
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "PYTHONHASHSEED",
        "TZ",
        "XDG_RUNTIME_DIR",
    }
)
RESOURCE_SUCCESS_VERDICT = "RESOURCE_PRETERMINAL_PASS"
RESOURCE_EXPECTED_FAILURE_VERDICT = "RESOURCE_PRETERMINAL_PASS_EXPECTED_PAYLOAD_FAILURE"
FORMAL_LOADER_ROLE = "ab16_formal_loader_v1"
FORMAL_RUNNER_MODULE = "docs.research.noncert_cuts_ab16_20260724.organic_arm_runner_v1"
SELECTED_BYTE_EXECUTION_STRATEGY = "selected-byte-python-loader-fd-v1"
SELECTED_BYTE_TRANSPORT = "systemd-openfile-v1"
SELECTED_BYTE_OPEN_FILE_NAMES = ["ab16-python", "ab16-loader", "ab16-authority"]
SELECTED_BYTE_FD_MAP = {"authority": 5, "loader": 4, "python": 3}
FORMAL_IMPORT_MODE = "ordinary_pathfinder"
FORMAL_MODULE_ORIGIN_POLICY = "sealed-snapshot-only-v1"

GIB = 1024**3
FORMAL_RESOURCE_CONTRACT: dict[str, object] = {
    "collect_mode": "inactive-or-failed",
    "kill_mode": "control-group",
    "memory_high_bytes": 35 * GIB,
    "memory_max_bytes": 39 * GIB,
    "memory_swap_max_bytes": 16 * GIB,
    "oom_policy": "continue",
    "runtime_max_seconds": 60 * 60,
    "send_sigkill": True,
    "single_worker": True,
}
DRILL_RESOURCE_CONTRACT: dict[str, object] = {
    "collect_mode": "inactive-or-failed",
    "kill_mode": "control-group",
    "memory_high_bytes": 2 * GIB,
    "memory_max_bytes": 4 * GIB,
    "memory_swap_max_bytes": 1 * GIB,
    "oom_policy": "continue",
    "runtime_max_seconds": 15 * 60,
    "send_sigkill": True,
    "single_worker": True,
}
RESOURCE_CONTRACTS = {
    "DISPOSABLE_LIVE_DRILL": DRILL_RESOURCE_CONTRACT,
    "FORMAL_AB16": FORMAL_RESOURCE_CONTRACT,
}
REFERENCE_CONTRACT = {
    "post_unref_cleanup_deadline_seconds": 10,
    "stability_hold_ns": 1_000_000_000,
    "terminal_transition_deadline_seconds": 10,
}
SYSTEMD_PRETERMINAL_FIELDS = frozenset(
    {
        "ActiveState",
        "CollectMode",
        "SubState",
        "MainPID",
        "ControlGroup",
        "InvocationID",
        "MemoryHigh",
        "MemoryMax",
        "MemorySwapMax",
        "OOMPolicy",
        "KillMode",
        "SendSIGKILL",
        "RuntimeMaxUSec",
    }
)
SYSTEMD_TERMINAL_FIELDS = frozenset(
    {
        "LoadState",
        "ActiveState",
        "SubState",
        "CollectMode",
        "ControlGroup",
        "InvocationID",
        "Result",
        "ExecMainCode",
        "ExecMainStatus",
    }
)
SYSTEMD_REFERENCE_FIELDS = frozenset(
    {
        "LoadState",
        "ActiveState",
        "SubState",
        "CollectMode",
        "ControlGroup",
        "InvocationID",
    }
)
CGROUP_FIELDS = frozenset(
    {
        "memory.high",
        "memory.max",
        "memory.swap.max",
        "memory.current",
        "memory.peak",
        "memory.swap.current",
        "memory.events",
        "cgroup.procs",
        "cgroup.events",
    }
)
MEMORY_EVENT_KEYS = frozenset({"low", "high", "max", "oom", "oom_kill", "oom_group_kill"})
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
GIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")


class VerificationError(RuntimeError):
    """Immutable evidence does not establish the lifecycle claim."""


MAX_TOOL_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class Snapshot:
    """Bytes, strict-JSON value, and detached identity from one descriptor."""

    raw: bytes
    value: Mapping[str, Any]
    identity: dict[str, object]


def _reject_constant(token: str) -> object:
    raise VerificationError(f"invalid JSON constant: {token}")


def _reject_float(token: str) -> object:
    raise VerificationError(f"floating-point JSON value is forbidden: {token}")


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json(value: object, label: str = "value") -> None:
    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise VerificationError(f"{label} contains non-finite float")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _strict_json(item, f"{label}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise VerificationError(f"{label} contains a non-string key")
            _strict_json(item, f"{label}.{key}")
        return
    raise VerificationError(f"{label} is not strict JSON")


def canonical_json_bytes(value: object) -> bytes:
    _strict_json(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def strict_loads(raw: bytes, label: str) -> Mapping[str, Any]:
    if type(raw) is not bytes or not raw:
        raise VerificationError(f"{label} must be non-empty bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"{label} is malformed JSON") from exc
    if type(value) is not dict or canonical_json_bytes(value) != raw:
        raise VerificationError(f"{label} is not a canonical JSON object")
    return value


def _strict_campaign_json(raw: bytes, label: str) -> Mapping[str, Any]:
    """Parse the campaign-authority JSON dialect, whose canonical form has LF."""

    if type(raw) is not bytes or not raw:
        raise VerificationError(f"{label} must be non-empty bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
            parse_float=_reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"{label} is malformed JSON") from exc
    if type(value) is not dict:
        raise VerificationError(f"{label} must be an exact object")
    canonical = (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    if canonical != raw:
        raise VerificationError(f"{label} is not canonical campaign-authority JSON")
    return value


def _load_pinned_module(
    identity: Mapping[str, Any],
    *,
    module_name: str,
) -> ModuleType:
    """Compile exactly one same-FD verified local authority module."""

    expected = _identity(identity, module_name, mode_required=True)
    raw, observed = snapshot_bytes(expected["path"])
    if any(observed.get(field) != expected[field] for field in expected):
        raise VerificationError(f"{module_name} byte identity drifted")
    if len(raw) > MAX_TOOL_BYTES:
        raise VerificationError(f"{module_name} exceeds tool byte cap")
    module = ModuleType(module_name)
    module.__file__ = str(expected["path"])
    sys.modules[module_name] = module
    try:
        code = compile(raw, str(expected["path"]), "exec", dont_inherit=True)
        exec(code, module.__dict__)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def _open_parent_dirfd(path: Path) -> tuple[Path, int, str]:
    absolute = Path(os.path.abspath(path))
    if absolute == Path(absolute.anchor):
        raise VerificationError("file path may not be the filesystem root")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute.anchor, flags)
    except OSError as exc:
        raise VerificationError("symlink or invalid path root") from exc
    try:
        for component in absolute.parts[1:-1]:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return absolute, descriptor, absolute.name
    except OSError as exc:
        os.close(descriptor)
        raise VerificationError("symlink or invalid path component") from exc


def _open_regular(path: Path | str) -> tuple[Path, int]:
    absolute, parent_descriptor, leaf = _open_parent_dirfd(Path(path))
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(leaf, flags, dir_fd=parent_descriptor)
    except OSError as exc:
        os.close(parent_descriptor)
        raise VerificationError("symlink or invalid file path") from exc
    os.close(parent_descriptor)
    return absolute, descriptor


def snapshot_json(path: Path | str) -> Snapshot:
    """Read/hash/parse a regular file through one stable descriptor."""

    absolute, descriptor = _open_regular(path)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise VerificationError(f"authority must be singly linked regular file: {absolute}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)

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
            raise VerificationError(f"authority changed during same-FD read: {absolute}")
        raw = b"".join(chunks)
        if len(raw) != after.st_size:
            raise VerificationError(f"short same-FD read: {absolute}")
        return Snapshot(
            raw=raw,
            value=strict_loads(raw, str(absolute)),
            identity={
                "mode": stat.S_IMODE(after.st_mode),
                "path": str(absolute),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            },
        )
    finally:
        os.close(descriptor)


def snapshot_bytes(path: Path | str) -> tuple[bytes, dict[str, object]]:
    """Read/hash non-JSON tool bytes through one stable descriptor."""

    absolute, descriptor = _open_regular(path)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise VerificationError(f"tool must be singly linked regular file: {absolute}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise VerificationError(f"tool changed during same-FD read: {absolute}")
        raw = b"".join(chunks)
        return raw, {
            "mode": stat.S_IMODE(after.st_mode),
            "path": str(absolute),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
    finally:
        os.close(descriptor)


def write_exclusive(path: Path | str, value: object) -> dict[str, object]:
    """Publish canonical JSON with O_EXCL and no symlink traversal."""

    absolute, parent_descriptor, leaf = _open_parent_dirfd(Path(path))
    raw = canonical_json_bytes(value)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(
            leaf,
            flags,
            0o444,
            dir_fd=parent_descriptor,
        )
    except Exception:
        os.close(parent_descriptor)
        raise
    os.close(parent_descriptor)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise VerificationError(f"short write: {absolute}")
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o444)
    finally:
        os.close(descriptor)
    return {
        "mode": 0o444,
        "path": str(absolute),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise VerificationError(f"{label} must be an exact object")
    return value


def _keys(value: object, expected: set[str] | frozenset[str], label: str) -> Mapping[str, Any]:
    record = _mapping(value, label)
    if set(record) != set(expected):
        raise VerificationError(f"{label} has the wrong key set")
    return record


def _integer(value: object, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise VerificationError(f"{label} must be integer >= {minimum}")
    return value


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise VerificationError(f"{label} must be non-empty string")
    return value


def _identity(
    value: object,
    label: str,
    *,
    mode_required: bool = False,
) -> Mapping[str, Any]:
    record = _mapping(value, label)
    required = {"path", "sha256", "size_bytes"}
    if (
        not required.issubset(record)
        or not set(record).issubset(required | {"mode"})
        or (mode_required and "mode" not in record)
    ):
        raise VerificationError(f"{label} has an invalid identity key set")
    if (
        not Path(_text(record["path"], f"{label}.path")).is_absolute()
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
        or ("mode" in record and type(record["mode"]) is not int)
    ):
        raise VerificationError(f"{label} identity is invalid")
    return record


def _validate_resource_contract(
    value: object,
    *,
    execution_class: object,
) -> Mapping[str, Any]:
    if type(execution_class) is not str or execution_class not in RESOURCE_CONTRACTS:
        raise VerificationError("resource contract execution class is invalid")
    expected = RESOURCE_CONTRACTS[execution_class]
    record = _keys(value, set(expected), "resource contract")
    for name in (
        "memory_high_bytes",
        "memory_max_bytes",
        "memory_swap_max_bytes",
        "runtime_max_seconds",
    ):
        _integer(record[name], f"resource contract {name}", 1)
    for name in ("send_sigkill", "single_worker"):
        if type(record[name]) is not bool:
            raise VerificationError(f"resource contract {name} must be exact boolean")
    for name in ("collect_mode", "kill_mode", "oom_policy"):
        _text(record[name], f"resource contract {name}")
    if dict(record) != expected:
        raise VerificationError("resource contract differs from preregistration")
    return record


def _validate_reference_contract(value: object) -> Mapping[str, Any]:
    record = _keys(value, set(REFERENCE_CONTRACT), "reference contract")
    for name in REFERENCE_CONTRACT:
        _integer(record[name], f"reference contract {name}", 1)
    if dict(record) != REFERENCE_CONTRACT:
        raise VerificationError("reference contract differs from preregistration")
    return record


def _replay_identity(
    value: object,
    label: str,
    *,
    mode_required: bool = False,
) -> dict[str, object]:
    identity = _identity(value, label, mode_required=mode_required)
    _raw, observed = snapshot_bytes(identity["path"])
    projected = {field: observed[field] for field in identity}
    if projected != identity:
        raise VerificationError(f"{label} byte identity drifted")
    return projected


def _replay_history_freeze(
    *,
    pre_run: Mapping[str, Any],
    strict_inputs: Mapping[str, Any],
) -> None:
    """Independently replay the failed-run history manifest and its receipt."""

    receipt_identity = _identity(
        pre_run["history_freeze_replay_identity"],
        "history freeze replay identity",
        mode_required=True,
    )
    receipt = snapshot_json(receipt_identity["path"])
    if receipt.identity != receipt_identity:
        raise VerificationError("history freeze replay identity drifted")
    receipt_record = _keys(
        receipt.value,
        {
            "authorizations",
            "file_count",
            "manifest_identity",
            "purpose",
            "schema_version",
            "status",
            "verdict",
        },
        "history freeze replay receipt",
    )
    authorizations = _keys(
        receipt_record["authorizations"],
        {
            "formal_campaign_creation_authorized",
            "organic_arm_launch_authorized",
        },
        "history freeze replay authorizations",
    )
    manifest_identity = _identity(
        receipt_record["manifest_identity"],
        "history freeze manifest identity",
        mode_required=True,
    )
    expected_manifest_role = (
        "input.history_freeze_manifest"
        if pre_run["execution_class"] == "DISPOSABLE_LIVE_DRILL"
        else "history_freeze_manifest"
    )
    expected_manifest = strict_inputs.get(expected_manifest_role)
    if (
        receipt_record["schema_version"] != "noncert-cuts-ab16-terminal-reference-history-replay-v1"
        or receipt_record["purpose"] != "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_REPLAY"
        or receipt_record["status"] != "PASS"
        or receipt_record["verdict"] != "IMMUTABLE_FAILED_GATE_A_HISTORY_REPLAY_PASS"
        or authorizations
        != {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
        }
        or manifest_identity != expected_manifest
    ):
        raise VerificationError("history freeze replay receipt semantics drifted")
    manifest_raw, observed_manifest = snapshot_bytes(manifest_identity["path"])
    if observed_manifest != manifest_identity:
        raise VerificationError("history freeze manifest identity drifted")
    manifest = _strict_campaign_json(
        manifest_raw,
        "history freeze manifest",
    )
    manifest_record = _keys(
        manifest,
        {
            "created_at_utc",
            "file_count",
            "files",
            "frozen_roots",
            "purpose",
            "repository_head",
            "repository_root",
            "live_source_provenance_root",
            "sealed_snapshot_execution_root",
            "snapshot_manifest_identity",
            "snapshot_materialization_receipt_identity",
            "schema_version",
            "v1_source_glob",
        },
        "history freeze manifest",
    )
    files = manifest_record["files"]
    file_count = receipt_record["file_count"]
    if (
        manifest_record["schema_version"] != "noncert-cuts-ab16-terminal-reference-history-freeze-v1"
        or manifest_record["purpose"] != "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_FREEZE"
        or manifest_record["repository_head"] != pre_run["repository_head"]
        or manifest_record["repository_root"] != pre_run["repository_root"]
        or type(files) is not list
        or type(file_count) is not int
        or file_count <= 0
        or manifest_record["file_count"] != file_count
        or len(files) != file_count
    ):
        raise VerificationError("history freeze manifest semantics drifted")
    repository_root = Path(pre_run["repository_root"])
    seen: set[str] = set()
    for raw_member in files:
        member = _keys(
            raw_member,
            {"mode", "path", "sha256", "size_bytes"},
            "history freeze member",
        )
        relative = member["path"]
        if (
            type(relative) is not str
            or not relative
            or relative in seen
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            raise VerificationError("history freeze member path is invalid")
        seen.add(relative)
        expected_member = {
            "mode": member["mode"],
            "path": str(repository_root / relative),
            "sha256": member["sha256"],
            "size_bytes": member["size_bytes"],
        }
        _identity(
            expected_member,
            f"history freeze member {relative}",
            mode_required=True,
        )
        _raw, observed = snapshot_bytes(expected_member["path"])
        if observed != expected_member:
            raise VerificationError("history freeze member identity drifted")


def _replay_drill_package(
    *,
    package: Mapping[str, Any],
    strict_inputs: Mapping[str, Any],
    tools: Mapping[str, Any],
) -> None:
    """Independently replay the three-member disposable authority package."""

    manifest_identity = _identity(
        package["manifest_identity"],
        "pre-run package manifest",
        mode_required=True,
    )
    seal_identity = _identity(
        package["seal_identity"],
        "pre-run package seal",
        mode_required=True,
    )
    manifest = snapshot_json(manifest_identity["path"])
    if manifest.identity != manifest_identity:
        raise VerificationError("pre-run package manifest identity drifted")
    record = _keys(
        manifest.value,
        {
            "authorizations",
            "external_source_identities",
            "sealed_payload_identities",
            "planned_source_set_digest",
            "purpose",
            "schema_version",
        },
        "disposable package manifest",
    )
    authorizations = _keys(
        record["authorizations"],
        {
            "arm_launch_authorized",
            "formal_campaign_creation_authorized",
            "solver_run_authorized",
        },
        "disposable package authorizations",
    )
    sealed = _keys(
        record["sealed_payload_identities"],
        {"libsystemd"},
        "disposable sealed payload identities",
    )
    external = _mapping(
        record["external_source_identities"],
        "disposable external source identities",
    )
    if (
        record["schema_version"] != "noncert-cuts-ab16-disposable-drill-package-manifest-v2"
        or record["purpose"] != "AB16_GATE_A_DISPOSABLE_DRILL_SOURCE_PACKAGE"
        or authorizations
        != {
            "arm_launch_authorized": False,
            "formal_campaign_creation_authorized": False,
            "solver_run_authorized": False,
        }
        or set(external) != set(strict_inputs)
        or sealed["libsystemd"] != tools["libsystemd"]
    ):
        raise VerificationError("disposable package semantics drifted")
    projected_external: dict[str, dict[str, object]] = {}
    for role, raw_identity in external.items():
        identity = _mapping(
            raw_identity,
            f"disposable external source {role}",
        )
        projection = {field: identity.get(field) for field in ("mode", "path", "sha256", "size_bytes")}
        if projection != strict_inputs[role]:
            raise VerificationError("disposable external source/strict-input join failed")
        projected_external[role] = dict(identity)
    planned_digest = hashlib.sha256(
        (
            json.dumps(
                projected_external,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    ).hexdigest()
    if type(record["planned_source_set_digest"]) is not str or record["planned_source_set_digest"] != planned_digest:
        raise VerificationError("disposable package source-set digest drifted")
    seal_raw, observed_seal = snapshot_bytes(seal_identity["path"])
    if observed_seal != seal_identity or package["package_id"] != seal_identity["sha256"]:
        raise VerificationError("disposable package seal identity drifted")
    libsystemd = _identity(
        tools["libsystemd"],
        "sealed libsystemd",
        mode_required=True,
    )
    expected_seal = (
        f"{manifest_identity['sha256']}  package-manifest.json\n{libsystemd['sha256']}  payload/libsystemd.so\n"
    ).encode("ascii")
    if seal_raw != expected_seal:
        raise VerificationError("disposable package seal contents drifted")
    package_dir = Path(manifest_identity["path"]).parent
    members = {str(item.relative_to(package_dir)) for item in package_dir.rglob("*") if item.is_file()}
    if members != {
        "SHA256SUMS",
        "package-manifest.json",
        "payload/libsystemd.so",
    }:
        raise VerificationError("disposable package member set drifted")


def _load_launch_environment(identity: object) -> dict[str, str]:
    expected = _identity(
        identity,
        "launch environment identity",
        mode_required=True,
    )
    snapshot = snapshot_json(expected["path"])
    if {field: snapshot.identity[field] for field in expected} != expected:
        raise VerificationError("launch environment byte identity drifted")
    record = _keys(
        snapshot.value,
        {"clear_ambient", "schema_version", "variables"},
        "launch environment",
    )
    if record["schema_version"] != LAUNCH_ENVIRONMENT_SCHEMA or record["clear_ambient"] is not True:
        raise VerificationError("launch environment framing drifted")
    variables = _keys(
        record["variables"],
        LAUNCH_ENVIRONMENT_KEYS,
        "launch environment variables",
    )
    for name, item in variables.items():
        text = _text(item, f"launch environment {name}")
        if "\x00" in text or "\n" in text or "\r" in text:
            raise VerificationError(f"launch environment {name} contains control bytes")
    for name in ("HOME", "XDG_RUNTIME_DIR"):
        if not Path(variables[name]).is_absolute():
            raise VerificationError(f"launch environment {name} must be absolute")
    path_items = variables["PATH"].split(":")
    if not path_items or any(not Path(item).is_absolute() for item in path_items):
        raise VerificationError("launch environment PATH must contain absolute entries")
    if (
        variables["LANG"] != "C.UTF-8"
        or variables["LC_ALL"] != "C.UTF-8"
        or variables["PYTHONHASHSEED"] != "0"
        or variables["TZ"] != "UTC"
        or not variables["DBUS_SESSION_BUS_ADDRESS"].startswith("unix:path=/")
    ):
        raise VerificationError("launch environment fixed values drifted")
    return dict(variables)  # type: ignore[arg-type]


def _epoch(value: object, label: str) -> Mapping[str, Any]:
    record = _mapping(value, label)
    required = {
        "boot_id",
        "dbus_unique_owner",
        "manager_pid",
        "manager_pid_starttime",
        "manager_executable",
        "manager_version",
        "manager_features",
    }
    if not required.issubset(record):
        raise VerificationError(f"{label} lacks manager/boot fields")
    _text(record["boot_id"], f"{label}.boot_id")
    _text(record["dbus_unique_owner"], f"{label}.dbus_unique_owner")
    _integer(record["manager_pid"], f"{label}.manager_pid", 1)
    _integer(record["manager_pid_starttime"], f"{label}.manager_pid_starttime", 1)
    executable = _mapping(record["manager_executable"], f"{label}.manager_executable")
    executable_required = {
        "path",
        "sha256",
        "size_bytes",
        "mode",
        "device",
        "inode",
    }
    if not executable_required.issubset(executable):
        raise VerificationError(f"{label}.manager_executable has wrong keys")
    _text(executable["path"], f"{label}.manager_executable.path")
    if type(executable["sha256"]) is not str or SHA256_RE.fullmatch(executable["sha256"]) is None:
        raise VerificationError(f"{label}.manager_executable.sha256 invalid")
    for field in ("size_bytes", "mode", "device", "inode"):
        _integer(executable[field], f"{label}.manager_executable.{field}")
    _text(record["manager_version"], f"{label}.manager_version")
    _text(record["manager_features"], f"{label}.manager_features")
    return record


def _epoch_digest(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(_epoch(value, "manager epoch"))).hexdigest()


def _literal_identity(value: str) -> dict[str, object]:
    raw = value.encode("utf-8")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}


def _selected_identity_argument(selected: Mapping[str, Any]) -> str:
    return canonical_json_bytes(
        {
            "authority": selected["authority_identity"],
            "loader": selected["loader_identity"],
            "python": selected["python_identity"],
        }
    ).decode("utf-8")


def _validate_formal_direct_argv(
    value: object,
    *,
    selected: Mapping[str, Any],
    loader_argv: list[str],
    label: str,
) -> None:
    if type(value) is not list or any(type(item) is not str or not item for item in value):
        raise VerificationError(f"{label} must be an exact non-empty string list")
    if (
        len(value) != 7 + len(loader_argv)
        or value[:4] != [selected["python_identity"]["path"], "-I", "-B", "-c"]
        or value[5] != "direct"
        or value[6] != _selected_identity_argument(selected)
        or value[7:] != loader_argv
        or _literal_identity(value[4]) != selected["literal_identity"]
    ):
        raise VerificationError(f"{label} selected-byte command drifted")


def validate_formal_execution_source(
    value: object,
    *,
    pre_run: Mapping[str, Any],
    launch: Mapping[str, Any],
    tools: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Independently replay the sealed execution-source closure."""

    record = _keys(
        value,
        {
            "environment",
            "execution_working_directory",
            "import_mode",
            "initial_working_directory",
            "live_source_provenance_root",
            "loader_argv",
            "loader_role",
            "module_origin_policy",
            "module_origin_receipt_path",
            "package_id",
            "runner_module",
            "runner_package_tool_identity",
            "runner_snapshot_member_identity",
            "runner_snapshot_relative_path",
            "schema_version",
            "sealed_snapshot_execution_root",
            "selected_byte_launch",
            "snapshot_manifest_identity",
            "snapshot_materialization_receipt_identity",
        },
        "formal execution source",
    )
    if (
        record["schema_version"] != SEALED_EXECUTION_SOURCE_SCHEMA
        or record["loader_role"] != FORMAL_LOADER_ROLE
        or record["runner_module"] != FORMAL_RUNNER_MODULE
        or record["import_mode"] != FORMAL_IMPORT_MODE
        or record["module_origin_policy"] != FORMAL_MODULE_ORIGIN_POLICY
        or record["package_id"] != pre_run["package"]["package_id"]
    ):
        raise VerificationError("formal execution source semantics drifted")
    live_root = Path(_text(record["live_source_provenance_root"], "formal live root"))
    snapshot_root = Path(_text(record["sealed_snapshot_execution_root"], "formal snapshot root"))
    initial_cwd = Path(_text(record["initial_working_directory"], "formal initial cwd"))
    execution_cwd = Path(_text(record["execution_working_directory"], "formal execution cwd"))
    if (
        not all(path.is_absolute() for path in (live_root, snapshot_root, initial_cwd, execution_cwd))
        or live_root != Path(pre_run["repository_root"])
        or record["live_source_provenance_root"] != pre_run["live_source_provenance_root"]
        or record["sealed_snapshot_execution_root"] != pre_run["sealed_snapshot_execution_root"]
        or live_root == snapshot_root
        or execution_cwd != snapshot_root
        or initial_cwd != Path(launch["cwd"])
    ):
        raise VerificationError("formal execution source root/cwd join failed")

    manifest_identity = _keys(
        record["snapshot_manifest_identity"],
        {"path", "sha256", "size_bytes"},
        "formal snapshot manifest identity",
    )
    receipt_identity = _keys(
        record["snapshot_materialization_receipt_identity"],
        {"path", "sha256", "size_bytes"},
        "formal snapshot receipt identity",
    )
    if (
        dict(manifest_identity) != pre_run["snapshot_manifest_identity"]
        or dict(receipt_identity) != pre_run["snapshot_materialization_receipt_identity"]
    ):
        raise VerificationError("formal snapshot top-level identity join failed")
    manifest_raw, manifest_observed = snapshot_bytes(manifest_identity["path"])
    receipt_raw, receipt_observed = snapshot_bytes(receipt_identity["path"])
    if (
        {field: manifest_observed[field] for field in manifest_identity} != manifest_identity
        or {field: receipt_observed[field] for field in receipt_identity} != receipt_identity
    ):
        raise VerificationError("formal snapshot manifest/receipt identity drifted")
    manifest = _keys(
        _strict_campaign_json(manifest_raw, "formal snapshot manifest"),
        {
            "archive_descriptor",
            "authority_scope",
            "import_mode",
            "member_count",
            "members",
            "ordered_member_digest",
            "repository_head",
            "repository_tree",
            "schema_version",
            "total_bytes",
        },
        "formal snapshot manifest",
    )
    receipt = _keys(
        _strict_campaign_json(receipt_raw, "formal snapshot materialization receipt"),
        {
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
        },
        "formal snapshot materialization receipt",
    )
    members = manifest["members"]
    if type(members) is not list or any(type(item) is not dict for item in members):
        raise VerificationError("formal snapshot member list is malformed")
    member_paths = [item.get("path") for item in members]
    if (
        manifest["schema_version"] != SNAPSHOT_MANIFEST_SCHEMA
        or manifest["authority_scope"] != "AB16_RESEARCH_ONLY"
        or manifest["import_mode"] != FORMAL_IMPORT_MODE
        or manifest["repository_head"] != pre_run["repository_head"]
        or manifest["member_count"] != len(members)
        or manifest["total_bytes"]
        != sum(_integer(item.get("size_bytes"), "formal snapshot member size") for item in members)
        or manifest["ordered_member_digest"]
        != hashlib.sha256(canonical_json_bytes(members) + b"\n").hexdigest()
        or any(type(path) is not str or not path for path in member_paths)
        or len(set(member_paths)) != len(member_paths)
    ):
        raise VerificationError("formal snapshot manifest semantic replay failed")
    if (
        receipt["schema_version"] != SNAPSHOT_MATERIALIZATION_SCHEMA
        or receipt["authority_scope"] != "AB16_RESEARCH_ONLY"
        or receipt["status"] != "PASS"
        or receipt["import_mode"] != FORMAL_IMPORT_MODE
        or receipt["package_id"] != record["package_id"]
        or receipt["repository_head"] != manifest["repository_head"]
        or receipt["repository_tree"] != manifest["repository_tree"]
        or receipt["member_count"] != manifest["member_count"]
        or receipt["ordered_member_digest"] != manifest["ordered_member_digest"]
        or receipt["total_bytes"] != manifest["total_bytes"]
        or receipt["snapshot_manifest_identity"] != dict(manifest_identity)
        or Path(receipt["snapshot_root"]) != snapshot_root
    ):
        raise VerificationError("formal snapshot materialization join failed")

    relative_text = _text(record["runner_snapshot_relative_path"], "formal runner relative path")
    relative = Path(relative_text)
    if relative.is_absolute() or relative_text != relative.as_posix() or ".." in relative.parts:
        raise VerificationError("formal runner relative path escaped")
    matching = [member for member in members if member.get("path") == relative_text]
    if len(matching) != 1:
        raise VerificationError("formal runner is not one snapshot member")
    member = matching[0]
    runner_identity = _identity(
        record["runner_snapshot_member_identity"],
        "formal runner snapshot member",
        mode_required=True,
    )
    observed_runner = _replay_identity(
        runner_identity,
        "formal runner snapshot member",
        mode_required=True,
    )
    if (
        Path(runner_identity["path"]) != snapshot_root / relative
        or runner_identity["sha256"] != member.get("raw_sha256")
        or runner_identity["size_bytes"] != member.get("size_bytes")
        or runner_identity["mode"] != member.get("materialized_mode")
        or observed_runner != dict(runner_identity)
    ):
        raise VerificationError("formal runner snapshot member join failed")
    package_runner = _identity(
        record["runner_package_tool_identity"],
        "formal package runner tool",
        mode_required=True,
    )
    if (
        dict(package_runner) != dict(tools["organic_arm_runner"])
        or package_runner["sha256"] != runner_identity["sha256"]
        or package_runner["size_bytes"] != runner_identity["size_bytes"]
    ):
        raise VerificationError("formal snapshot/package runner join failed")

    selected = _keys(
        record["selected_byte_launch"],
        {
            "execution_strategy",
            "fd_map",
            "authority_identity",
            "literal_identity",
            "loader_identity",
            "open_file_names",
            "python_identity",
            "schema_version",
            "transport",
        },
        "formal selected-byte launch",
    )
    literal_identity = _keys(
        selected["literal_identity"],
        {"sha256", "size_bytes"},
        "formal selected-byte literal",
    )
    if (
        selected["schema_version"] != SELECTED_BYTE_LAUNCH_SCHEMA
        or selected["execution_strategy"] != SELECTED_BYTE_EXECUTION_STRATEGY
        or selected["transport"] != SELECTED_BYTE_TRANSPORT
        or selected["open_file_names"] != SELECTED_BYTE_OPEN_FILE_NAMES
        or selected["fd_map"] != SELECTED_BYTE_FD_MAP
        or type(literal_identity["sha256"]) is not str
        or SHA256_RE.fullmatch(literal_identity["sha256"]) is None
        or type(literal_identity["size_bytes"]) is not int
        or literal_identity["size_bytes"] <= 0
    ):
        raise VerificationError("formal selected-byte launch semantics drifted")
    python_identity = _identity(selected["python_identity"], "formal selected Python", mode_required=True)
    loader_identity = _identity(selected["loader_identity"], "formal selected loader", mode_required=True)
    authority_identity = _identity(
        selected["authority_identity"],
        "formal selected authority",
        mode_required=True,
    )
    if dict(python_identity) != dict(tools["python3_13"]):
        raise VerificationError("formal selected Python differs from package tool")
    _replay_identity(python_identity, "formal selected Python", mode_required=True)
    _replay_identity(loader_identity, "formal selected loader", mode_required=True)
    _replay_identity(authority_identity, "formal selected authority", mode_required=True)
    package_manifest_identity = _identity(
        pre_run["package"]["manifest_identity"],
        "formal package manifest",
    )
    package_manifest_raw, observed_package_manifest = snapshot_bytes(
        package_manifest_identity["path"]
    )
    if {
        field: observed_package_manifest[field] for field in package_manifest_identity
    } != package_manifest_identity:
        raise VerificationError("formal package manifest identity drifted")
    package_manifest = _strict_campaign_json(
        package_manifest_raw,
        "formal package manifest",
    )
    sources = package_manifest.get("external_sources")
    if type(sources) is not list:
        raise VerificationError("formal package manifest lacks external sources")
    authority_roles = [
        source
        for source in sources
        if type(source) is dict and source.get("role") == "tool.ab16_authority_v2.py"
    ]
    if len(authority_roles) != 1:
        raise VerificationError("formal package authority role is absent or duplicated")
    authority_role = _keys(
        authority_roles[0],
        {"package_path", "parse_json", "role", "source_identity"},
        "formal package authority role",
    )
    source_identity = _identity(
        authority_role["source_identity"],
        "formal package authority source",
    )
    package_path = _text(authority_role["package_path"], "formal package authority path")
    if (
        package_path.startswith("/")
        or ".." in Path(package_path).parts
        or Path(authority_identity["path"]) != Path(package_manifest_identity["path"]).parent / package_path
        or authority_identity["sha256"] != source_identity["sha256"]
        or authority_identity["size_bytes"] != source_identity["size_bytes"]
    ):
        raise VerificationError("formal selected authority differs from sealed package role")

    environment = _keys(
        record["environment"],
        {
            "LANG",
            "LC_ALL",
            "PYTHONDONTWRITEBYTECODE",
            "PYTHONHASHSEED",
            "PYTHONNOUSERSITE",
            "TMPDIR",
            "TZ",
        },
        "formal execution environment",
    )
    if {
        key: environment[key]
        for key in ("LANG", "LC_ALL", "PYTHONDONTWRITEBYTECODE", "PYTHONHASHSEED", "PYTHONNOUSERSITE", "TZ")
    } != {
        "LANG": "C",
        "LC_ALL": "C",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "TZ": "UTC",
    }:
        raise VerificationError("formal execution environment drifted")
    attempt_dir = Path(pre_run["attempt_dir"])
    tmpdir = Path(_text(environment["TMPDIR"], "formal execution TMPDIR"))
    origin_receipt = Path(_text(record["module_origin_receipt_path"], "formal module-origin receipt"))
    if (
        not tmpdir.is_absolute()
        or tmpdir.parent != attempt_dir
        or origin_receipt != attempt_dir / "module-origin-receipt.json"
    ):
        raise VerificationError("formal execution temp/origin path drifted")
    expected_loader_argv = [
        "--role",
        "organic-arm",
        "--campaign-dir",
        str(initial_cwd),
        "--pre-run",
        str(pre_run["pre_run_authority_path"]),
        "--selection",
        str(pre_run["runner_selection_path"]),
        "--module-origin-receipt",
        str(origin_receipt),
    ]
    if record["loader_argv"] != expected_loader_argv:
        raise VerificationError("formal organic-arm loader argv drifted")
    _validate_formal_direct_argv(
        launch["payload_argv"],
        selected=selected,
        loader_argv=expected_loader_argv,
        label="formal payload argv",
    )
    supervisor = launch["supervisor_argv"]
    if type(supervisor) is not list or len(supervisor) != 17:
        raise VerificationError("formal supervisor argv is malformed")
    supervisor_loader_argv = supervisor[7:]
    if (
        supervisor_loader_argv[:8]
        != [
            "--role",
            "organic-supervisor",
            "--campaign-dir",
            str(initial_cwd),
            "--pre-run",
            str(pre_run["pre_run_authority_path"]),
            "--selection",
            str(pre_run["runner_selection_path"]),
        ]
        or supervisor_loader_argv[8] != "--module-origin-receipt"
    ):
        raise VerificationError("formal supervisor loader argv drifted")
    supervisor_origin = Path(supervisor_loader_argv[9])
    if (
        not supervisor_origin.is_absolute()
        or supervisor_origin.parent != attempt_dir
        or supervisor_origin == origin_receipt
    ):
        raise VerificationError("formal supervisor module-origin receipt path drifted")
    _validate_formal_direct_argv(
        supervisor,
        selected=selected,
        loader_argv=supervisor_loader_argv,
        label="formal supervisor argv",
    )
    return record


def validate_pre_run_authority(
    value: object,
    *,
    campaign_root: Mapping[str, Any] | None = None,
    manifest: Mapping[str, Any] | None = None,
    suite_selection: Mapping[str, Any] | None = None,
    expected_slot: str | None = None,
) -> Mapping[str, Any]:
    """Validate one non-authorizing receipt and optional authority context."""

    expected_keys = {
        "arm",
        "arm_binding_identity",
        "arm_launch_authorized",
        "arm_selection_write_authorized",
        "attempt_dir",
        "authority_chain",
        "baseline_admission_identity",
        "baseline_incumbent_sha256",
        "campaign_id",
        "campaign_root_identity",
        "common_prestate_identity",
        "configuration",
        "continuation_identity",
        "epoch_observation_paths",
        "epoch_transcript_paths",
        "execution_class",
        "expected_payload_status",
        "launch",
        "manager_epoch",
        "order",
        "output_paths",
        "package",
        "pre_run_authority_path",
        "prelaunch_allowlist",
        "preflight_results",
        "preselection_epoch_identity",
        "preselection_transcript_identity",
        "reference_capability_identity",
        "reference_capability_transcript_identity",
        "history_freeze_replay_identity",
        "prospective_manifest_identity",
        "purpose",
        "repository_head",
        "repository_root",
        "live_source_provenance_root",
        "sealed_snapshot_execution_root",
        "snapshot_manifest_identity",
        "snapshot_materialization_receipt_identity",
        "repository_git_tool_identity",
        "resource_contract",
        "reference_contract",
        "run_nonce",
        "runner_selection_path",
        "schema_version",
        "seed",
        "slot",
        "solver_run_authorized",
        "status",
        "strict_input_identities",
        "suite_selection_identity",
        "tool_identities",
        "unit_name",
        "verdict",
        "workers",
    }
    record = _keys(value, expected_keys, "pre-run authority")
    if (
        record.get("schema_version") != PRE_RUN_SCHEMA
        or record.get("purpose") != PRE_RUN_PURPOSE
        or record.get("status") != "PASS"
        or record.get("verdict") != "AB16_ORGANIC_PRE_RUN_AUTHORITY_PASS"
        or record.get("arm_launch_authorized") is not False
        or record.get("solver_run_authorized") is not False
        or record.get("arm_selection_write_authorized") is not True
        or record.get("workers") != 1
        or type(record.get("repository_head")) is not str
        or GIT_SHA_RE.fullmatch(record["repository_head"]) is None
        or record.get("execution_class") not in {"DISPOSABLE_LIVE_DRILL", "FORMAL_AB16"}
    ):
        raise VerificationError("pre-run authority semantics drifted")
    _validate_resource_contract(
        record["resource_contract"],
        execution_class=record["execution_class"],
    )
    _validate_reference_contract(record["reference_contract"])
    repository_root = Path(_text(record["repository_root"], "repository root"))
    live_root = Path(
        _text(record["live_source_provenance_root"], "live source provenance root")
    )
    snapshot_root = Path(
        _text(record["sealed_snapshot_execution_root"], "sealed snapshot execution root")
    )
    if (
        not repository_root.is_absolute()
        or live_root != repository_root
        or not snapshot_root.is_absolute()
        or snapshot_root == live_root
    ):
        raise VerificationError("pre-run live/sealed repository roots are invalid")
    _replay_identity(
        record["snapshot_manifest_identity"],
        "pre-run snapshot manifest identity",
    )
    _replay_identity(
        record["snapshot_materialization_receipt_identity"],
        "pre-run snapshot materialization identity",
    )
    _replay_identity(
        record["repository_git_tool_identity"],
        "pre-run repository git tool",
        mode_required=True,
    )
    _epoch(record.get("manager_epoch"), "pre-run manager epoch")
    expected_payload = _keys(
        record["expected_payload_status"],
        {"exit_code", "expectation", "signal"},
        "pre-run expected payload status",
    )
    exit_code = _integer(expected_payload["exit_code"], "expected payload exit")
    signal_number = _integer(expected_payload["signal"], "expected payload signal")
    if expected_payload["expectation"] == "SUCCESS":
        if exit_code != 0 or signal_number != 0:
            raise VerificationError("successful payload status drifted")
    elif expected_payload["expectation"] == "POST_SEAL_FAILURE":
        if (exit_code == 0) == (signal_number == 0):
            raise VerificationError("post-SEAL payload failure mode is ambiguous")
    else:
        raise VerificationError("expected payload status is invalid")
    attempt_dir = Path(_text(record["attempt_dir"], "pre-run attempt_dir"))
    pre_run_path = Path(_text(record["pre_run_authority_path"], "pre-run authority path"))
    selection_path = Path(_text(record["runner_selection_path"], "pre-run selection path"))
    if (
        not attempt_dir.is_absolute()
        or pre_run_path != attempt_dir / "pre-run-authority.json"
        or selection_path != attempt_dir / "selection.json"
    ):
        raise VerificationError("pre-run attempt/preregistered paths drifted")
    for field in (
        "campaign_root_identity",
        "continuation_identity",
        "prospective_manifest_identity",
        "suite_selection_identity",
        "baseline_admission_identity",
        "common_prestate_identity",
        "arm_binding_identity",
        "reference_capability_identity",
        "reference_capability_transcript_identity",
        "history_freeze_replay_identity",
    ):
        _replay_identity(record.get(field), f"pre-run {field}")
    capability_identity = _identity(
        record["reference_capability_identity"],
        "reference capability identity",
    )
    capability = snapshot_json(capability_identity["path"])
    if {field: capability.identity[field] for field in capability_identity} != capability_identity:
        raise VerificationError("reference capability identity drifted")
    transcript_identity = _identity(
        record["reference_capability_transcript_identity"],
        "reference capability transcript identity",
    )
    transcript = snapshot_json(transcript_identity["path"])
    if {field: transcript.identity[field] for field in transcript_identity} != transcript_identity:
        raise VerificationError("reference capability transcript identity drifted")
    capability_record = _keys(
        capability.value,
        {
            "manager_epoch_digest",
            "methods",
            "purpose",
            "schema_version",
            "status",
            "transcript_identity",
            "verdict",
        },
        "reference capability receipt",
    )
    transcript_record = _keys(
        transcript.value,
        {
            "argv",
            "busctl_identity",
            "exit_code",
            "manager_epoch_digest",
            "purpose",
            "schema_version",
            "stderr",
            "stdout",
        },
        "reference capability transcript",
    )
    expected_methods = {
        "RefUnit": {
            "in_signature": "s",
            "interface": "org.freedesktop.systemd1.Manager",
            "out_signature": "-",
        },
        "UnrefUnit": {
            "in_signature": "s",
            "interface": "org.freedesktop.systemd1.Manager",
            "out_signature": "-",
        },
    }
    digest = _epoch_digest(record["manager_epoch"])
    if (
        capability_record["schema_version"] != "noncert-cuts-ab16-reference-capability-v1"
        or capability_record["purpose"] != "AB16_GATE_A_REFERENCE_CAPABILITY_REPLAY"
        or capability_record["status"] != "PASS"
        or capability_record["verdict"] != "REFUNIT_UNREFUNIT_EXACT_SURFACE_PASS"
        or capability_record["manager_epoch_digest"] != digest
        or capability_record["methods"] != expected_methods
        or capability_record["transcript_identity"] != transcript_identity
        or transcript_record["schema_version"] != "noncert-cuts-ab16-reference-capability-transcript-v1"
        or transcript_record["purpose"] != "AB16_GATE_A_REFERENCE_CAPABILITY_RAW_TRANSCRIPT"
        or transcript_record["manager_epoch_digest"] != digest
        or transcript_record["busctl_identity"] != record["tool_identities"]["busctl"]
        or transcript_record["exit_code"] != 0
        or transcript_record["stderr"] != ""
        or type(transcript_record["stdout"]) is not str
    ):
        raise VerificationError("reference capability semantic replay failed")
    observed_methods: dict[str, tuple[str, str, str, str]] = {}
    for line in transcript_record["stdout"].splitlines():
        fields = line.split()
        if fields and fields[0] in {".RefUnit", ".UnrefUnit"}:
            name = fields[0][1:]
            if len(fields) < 5 or name in observed_methods:
                raise VerificationError("reference capability row is truncated or duplicated")
            observed_methods[name] = tuple(fields[1:5])  # type: ignore[assignment]
    if observed_methods != {
        "RefUnit": ("method", "s", "-", "-"),
        "UnrefUnit": ("method", "s", "-", "-"),
    }:
        raise VerificationError("reference capability raw transcript differs")
    package = _mapping(record.get("package"), "pre-run package")
    if set(package) != {"manifest_identity", "package_id", "seal_identity"}:
        raise VerificationError("pre-run package key set drifted")
    _replay_identity(package["manifest_identity"], "pre-run package manifest")
    seal = _replay_identity(package["seal_identity"], "pre-run package seal")
    if (
        type(package["package_id"]) is not str
        or SHA256_RE.fullmatch(package["package_id"]) is None
        or package["package_id"] != seal["sha256"]
    ):
        raise VerificationError("pre-run package identity is invalid")
    tools = _mapping(record.get("tool_identities"), "pre-run tool identities")
    if set(tools) != {
        "busctl",
        "manager_attestor",
        "manager_epoch_authority",
        "organic_arm_runner",
        "organic_resource_lifecycle",
        "organic_resource_verifier",
        "organic_unit_orchestrator",
        "python3_13",
        "systemd_unit_reference",
        "libsystemd",
        "sudo",
        "systemctl",
        "systemd_run",
    }:
        raise VerificationError("pre-run tool role set drifted")
    for role, identity in tools.items():
        _replay_identity(identity, f"pre-run tool {role}", mode_required=True)
    outputs = _mapping(record.get("output_paths"), "pre-run output paths")
    required_outputs = {
        "attempt_result",
        "cleanup",
        "detached_replay",
        "inner",
        "preterminal",
        "reference_acquisition",
        "reference_release",
        "abort_reference_release",
        "release",
        "resource_verification",
        "terminal",
    }
    if set(outputs) != required_outputs:
        raise VerificationError("pre-run output role set drifted")
    seen = {pre_run_path, selection_path}
    for role, raw_path in outputs.items():
        output = Path(_text(raw_path, f"pre-run output {role}"))
        if output.parent != attempt_dir or output in seen:
            raise VerificationError("pre-run output path escaped or collided")
        seen.add(output)
    epoch_paths = _mapping(
        record.get("epoch_observation_paths"),
        "pre-run epoch observation paths",
    )
    if set(epoch_paths) != {
        "launch",
        "preterminal",
        "reference-acquire",
        "release",
        "terminal-first",
        "terminal-stable",
        "reference-release",
        "cleanup",
        "detached-replay",
    }:
        raise VerificationError("pre-run epoch phase path set drifted")
    for phase, raw_path in epoch_paths.items():
        output = Path(_text(raw_path, f"pre-run epoch path {phase}"))
        if output.parent != attempt_dir or output in seen:
            raise VerificationError("pre-run epoch path escaped or collided")
        seen.add(output)
    transcript_paths = _mapping(
        record.get("epoch_transcript_paths"),
        "pre-run epoch transcript paths",
    )
    if set(transcript_paths) != set(epoch_paths):
        raise VerificationError("pre-run epoch transcript phase set drifted")
    for phase, raw_path in transcript_paths.items():
        output = Path(_text(raw_path, f"pre-run epoch transcript path {phase}"))
        if output.parent != attempt_dir or output in seen:
            raise VerificationError("pre-run epoch transcript path escaped or collided")
        seen.add(output)
    preselection_snapshot = snapshot_json(
        _identity(
            record.get("preselection_epoch_identity"),
            "preselection epoch identity",
        )["path"]
    )
    expected_preselection = _identity(
        record["preselection_epoch_identity"],
        "preselection epoch identity",
    )
    if {field: preselection_snapshot.identity[field] for field in expected_preselection} != expected_preselection:
        raise VerificationError("preselection epoch byte identity drifted")
    preselection_transcript = _identity(
        record["preselection_transcript_identity"],
        "preselection manager transcript",
        mode_required=True,
    )
    if preselection_snapshot.value.get("capture_transcript_identity") != preselection_transcript:
        raise VerificationError("preselection transcript identity join failed")
    _epoch_observation(
        preselection_snapshot.value,
        pre_run=record,
        phase="preselection",
    )
    strict_inputs = _mapping(
        record.get("strict_input_identities"),
        "pre-run strict inputs",
    )
    if not strict_inputs:
        raise VerificationError("pre-run strict input map is empty")
    for role, identity in strict_inputs.items():
        _text(role, "pre-run strict input role")
        _replay_identity(
            identity,
            f"pre-run strict input {role}",
            mode_required=True,
        )
    _replay_history_freeze(
        pre_run=record,
        strict_inputs=strict_inputs,
    )
    if record["execution_class"] == "DISPOSABLE_LIVE_DRILL":
        _replay_drill_package(
            package=package,
            strict_inputs=strict_inputs,
            tools=tools,
        )
    if record.get("prelaunch_allowlist") != [
        "pre-run-authority.json",
        "selection.json",
    ]:
        raise VerificationError("pre-run allowlist drifted")
    launch = _mapping(record.get("launch"), "pre-run launch")
    launch_keys = {
        "cwd",
        "environment_identity",
        "payload_argv",
        "python3_13_path",
        "libsystemd_path",
        "supervisor_argv",
        "systemctl_path",
        "systemd_run_path",
    }
    if record["execution_class"] == "FORMAL_AB16":
        launch_keys.add("execution_source")
    if set(launch) != launch_keys:
        raise VerificationError("pre-run launch key set drifted")
    if (
        not Path(_text(launch["cwd"], "pre-run launch cwd")).is_absolute()
        or not Path(_text(launch["systemd_run_path"], "pre-run systemd-run path")).is_absolute()
    ):
        raise VerificationError("pre-run launch paths must be absolute")
    _load_launch_environment(launch["environment_identity"])
    for launch_field, tool_role in (
        ("python3_13_path", "python3_13"),
        ("libsystemd_path", "libsystemd"),
        ("systemctl_path", "systemctl"),
        ("systemd_run_path", "systemd_run"),
    ):
        if launch[launch_field] != tools[tool_role]["path"]:
            raise VerificationError(f"pre-run launch {launch_field} differs from pinned tool")
    if record["execution_class"] == "FORMAL_AB16":
        validate_formal_execution_source(
            launch["execution_source"],
            pre_run=record,
            launch=launch,
            tools=tools,
        )
    else:
        for field in ("payload_argv", "supervisor_argv"):
            argv = launch[field]
            if type(argv) is not list or len(argv) < 3 or any(type(item) is not str or not item for item in argv):
                raise VerificationError(f"pre-run launch {field} is invalid")
            if argv[0] != tools["python3_13"]["path"]:
                raise VerificationError(f"pre-run launch {field}[0] Python drifted")
            if argv[1] != "-I":
                raise VerificationError(f"pre-run launch {field} Python isolation drifted")
        if launch["supervisor_argv"][2] != tools["organic_resource_lifecycle"]["path"]:
            raise VerificationError("pre-run supervisor tool path drifted")
        if launch["payload_argv"][2] not in {identity["path"] for identity in strict_inputs.values()}:
            raise VerificationError("pre-run drill payload is not a strict input")
    preflight = _mapping(record.get("preflight_results"), "pre-run preflight")
    required_preflight = {
        "epoch_identity_pass",
        "head_identity_pass",
        "package_replay_pass",
        "path_preregistration_pass",
        "resource_contract_pass",
        "reference_contract_pass",
        "reference_capability_pass",
        "libsystemd_identity_pass",
        "history_freeze_replay_pass",
        "slot_order_pass",
        "strict_inputs_replay_pass",
        "tool_identities_replay_pass",
    }
    if set(preflight) != required_preflight or any(
        type(item) is not bool or item is not True for item in preflight.values()
    ):
        raise VerificationError("pre-run mandatory preflight is not all PASS")
    if expected_slot is not None and record.get("slot") != expected_slot:
        raise VerificationError("pre-run expected slot differs")
    if campaign_root is not None:
        joins = {
            "campaign_id": "campaign_id",
            "run_nonce": "run_nonce",
            "repository_head": "repository_head",
            "repository_root": "repository_root",
            "repository_git_tool_identity": "repository_git_tool_identity",
            "manager_epoch": "manager_epoch",
            "package": "package",
        }
        for receipt_field, root_field in joins.items():
            if record.get(receipt_field) != campaign_root.get(root_field):
                raise VerificationError(f"pre-run campaign root {receipt_field} join failed")
        root_strict = campaign_root.get("strict_input_identities")
        if root_strict is not None and record["strict_input_identities"] != root_strict:
            raise VerificationError("pre-run root strict input map join failed")
    if manifest is not None:
        arm_sequence = manifest.get("arm_sequence")
        attempt_dirs = manifest.get("attempt_dirs")
        unit_names = manifest.get("unit_names")
        slot = record.get("slot")
        if (
            type(arm_sequence) is not list
            or type(attempt_dirs) is not dict
            or type(unit_names) is not dict
            or slot not in arm_sequence
            or set(arm_sequence) != set(attempt_dirs)
            or set(arm_sequence) != set(unit_names)
            or attempt_dirs.get(slot) != record.get("attempt_dir")
            or unit_names.get(slot) != record.get("unit_name")
        ):
            raise VerificationError("pre-run manifest slot/path/name join failed")
        if slot != (f"{record.get('configuration')}-{record.get('order')}-{record.get('arm')}"):
            raise VerificationError("pre-run slot decomposition failed")
        for field in (
            "campaign_id",
            "run_nonce",
            "repository_head",
            "repository_root",
            "live_source_provenance_root",
            "sealed_snapshot_execution_root",
            "snapshot_manifest_identity",
            "snapshot_materialization_receipt_identity",
            "repository_git_tool_identity",
            "authority_chain",
        ):
            if manifest.get(field) != record.get(field):
                raise VerificationError(f"pre-run manifest {field} join failed")
        for identity_field in (
            "baseline_admission_identity",
            "common_prestate_identity",
        ):
            if manifest.get(identity_field) != record.get(identity_field):
                raise VerificationError(f"pre-run manifest {identity_field} join failed")
        binding_map = manifest.get("arm_binding_identities")
        if type(binding_map) is not dict or binding_map.get(slot) != record.get("arm_binding_identity"):
            raise VerificationError("pre-run manifest arm binding join failed")
    if suite_selection is not None:
        if (
            suite_selection.get("arm_launch_authorized") is not False
            or suite_selection.get("run_nonce") != record.get("run_nonce")
            or suite_selection.get("package_id") != record["package"]["package_id"]
            or suite_selection.get("live_source_provenance_root")
            != record["live_source_provenance_root"]
            or suite_selection.get("sealed_snapshot_execution_root")
            != record["sealed_snapshot_execution_root"]
            or suite_selection.get("snapshot_manifest_identity")
            != record["snapshot_manifest_identity"]
            or suite_selection.get("snapshot_materialization_receipt_identity")
            != record["snapshot_materialization_receipt_identity"]
        ):
            raise VerificationError("pre-run suite selection join failed")
    return record


def _validate_selection(
    value: object,
    *,
    pre_run: Mapping[str, Any],
    pre_run_identity: Mapping[str, Any],
) -> Mapping[str, Any]:
    record = _keys(
        value,
        {
            "arm",
            "arm_binding_identity",
            "attempt_dir",
            "authority_chain",
            "authorizations",
            "baseline_admission_identity",
            "baseline_incumbent_sha256",
            "campaign_id",
            "common_prestate_identity",
            "configuration",
            "enabled_families",
            "execution_class",
            "expected_payload_status",
            "fresh_process_required",
            "live_source_provenance_root",
            "manifest_identity",
            "order",
            "pre_run_authority_identity",
            "purpose",
            "repository_head",
            "repository_root",
            "repository_git_tool_identity",
            "run_nonce",
            "schema_version",
            "sealed_snapshot_execution_root",
            "seed",
            "selection_nonce",
            "snapshot_manifest_identity",
            "snapshot_materialization_receipt_identity",
            "slot",
            "unit_name",
            "workers",
        },
        "runner selection",
    )
    formal = (
        record.get("schema_version") == RUNNER_SELECTION_SCHEMA
        and record.get("purpose") == RUNNER_PURPOSE
        and record.get("execution_class") == "FORMAL_AB16"
    )
    drill = (
        record.get("schema_version") == DRILL_SELECTION_SCHEMA
        and record.get("purpose") == DRILL_PURPOSE
        and record.get("execution_class") == "DISPOSABLE_LIVE_DRILL"
    )
    if (not formal and not drill) or record.get("fresh_process_required") is not True:
        raise VerificationError("runner selection semantics drifted")
    selected_pre_run_identity = _identity(
        record.get("pre_run_authority_identity"),
        "runner selection pre-run identity",
    )
    if {field: pre_run_identity[field] for field in selected_pre_run_identity} != selected_pre_run_identity:
        raise VerificationError("runner selection pre-run identity drifted")
    joins = {
        "arm": "arm",
        "arm_binding_identity": "arm_binding_identity",
        "attempt_dir": "attempt_dir",
        "authority_chain": "authority_chain",
        "baseline_admission_identity": "baseline_admission_identity",
        "baseline_incumbent_sha256": "baseline_incumbent_sha256",
        "campaign_id": "campaign_id",
        "common_prestate_identity": "common_prestate_identity",
        "configuration": "configuration",
        "execution_class": "execution_class",
        "expected_payload_status": "expected_payload_status",
        "order": "order",
        "repository_head": "repository_head",
        "repository_root": "repository_root",
        "live_source_provenance_root": "live_source_provenance_root",
        "sealed_snapshot_execution_root": "sealed_snapshot_execution_root",
        "snapshot_manifest_identity": "snapshot_manifest_identity",
        "snapshot_materialization_receipt_identity": "snapshot_materialization_receipt_identity",
        "repository_git_tool_identity": "repository_git_tool_identity",
        "run_nonce": "run_nonce",
        "seed": "seed",
        "slot": "slot",
        "unit_name": "unit_name",
        "workers": "workers",
        "manifest_identity": "prospective_manifest_identity",
    }
    for selected_field, pre_run_field in joins.items():
        if record.get(selected_field) != pre_run.get(pre_run_field):
            raise VerificationError(f"runner selection {selected_field} join failed")
    expected_families = (
        []
        if record["arm"] == "control" or drill
        else {
            "region-capacity": ["region_capacity"],
            "shape-packing-hall": ["shape_packing_hall"],
            "power-hitting-set": ["power_hitting_set"],
            "bundle": [
                "region_capacity",
                "shape_packing_hall",
                "power_hitting_set",
            ],
        }.get(record["configuration"])
    )
    if expected_families is None or record.get("enabled_families") != expected_families:
        raise VerificationError("runner selection enabled families drifted")
    if (
        type(record.get("selection_nonce")) is not str
        or re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}",
            record["selection_nonce"],
        )
        is None
    ):
        raise VerificationError("runner selection nonce is invalid")
    if record.get("authorizations") != {
        "global_claim_authorized": False,
        "mathematical_claim_authorized": False,
        "organic_arm_launch_authorized": formal,
        "production_certified_authorized": False,
        "solver_run_authorized": formal,
    }:
        raise VerificationError("runner selection authorization drifted")
    return record


def _epoch_observation(
    value: object,
    *,
    pre_run: Mapping[str, Any],
    phase: str,
) -> Mapping[str, Any]:
    record = _keys(
        value,
        {
            "capture_transcript_identity",
            "observed_at_monotonic_ns",
            "observed_epoch",
            "observed_epoch_digest",
            "phase",
            "schema_version",
            "slot",
        },
        f"{phase} epoch observation",
    )
    if (
        record["schema_version"] != EPOCH_SCHEMA
        or record["phase"] != phase
        or record["slot"] != pre_run["slot"]
        or record["observed_epoch"] != pre_run["manager_epoch"]
        or record["observed_epoch_digest"] != _epoch_digest(record["observed_epoch"])
    ):
        raise VerificationError(f"{phase} manager/boot epoch drifted")
    _integer(record["observed_at_monotonic_ns"], f"{phase} observed time", 1)
    transcript_identity = _identity(
        record["capture_transcript_identity"],
        f"{phase} manager transcript",
        mode_required=True,
    )
    expected_transcript_path = (
        pre_run["preselection_transcript_identity"]["path"]
        if phase == "preselection"
        else pre_run["epoch_transcript_paths"].get(phase)
    )
    if transcript_identity["path"] != expected_transcript_path:
        raise VerificationError(f"{phase} manager transcript path drifted")
    transcript = snapshot_json(transcript_identity["path"])
    if {field: transcript.identity[field] for field in transcript_identity} != transcript_identity:
        raise VerificationError(f"{phase} manager transcript identity drifted")
    authority_identity = pre_run["tool_identities"]["manager_epoch_authority"]
    authority = _load_pinned_module(
        authority_identity,
        module_name=(f"_ab16_verifier_epoch_authority_{authority_identity['sha256'][:12]}_{phase.replace('-', '_')}"),
    )
    try:
        authority.validate_manager_epoch(pre_run["manager_epoch"])
        authority.validate_manager_epoch_capture_transcript(
            transcript.value,
            expected_epoch=record["observed_epoch"],
        )
    except Exception as exc:
        raise VerificationError(f"{phase} manager transcript semantic replay failed") from exc
    return record


def _replay_epoch_observation_file(
    *,
    pre_run: Mapping[str, Any],
    phase: str,
    embedded_observation: object,
    supplied_snapshot: Snapshot | None = None,
) -> Mapping[str, Any]:
    expected_path = pre_run["epoch_observation_paths"].get(phase)
    if type(expected_path) is not str:
        raise VerificationError(f"{phase} epoch observation path is absent")
    snapshot = supplied_snapshot or snapshot_json(expected_path)
    if snapshot.identity["path"] != expected_path:
        raise VerificationError(f"{phase} epoch observation path drifted")
    if snapshot.value != embedded_observation:
        raise VerificationError(f"{phase} standalone/embedded epoch observation differs")
    return _epoch_observation(
        snapshot.value,
        pre_run=pre_run,
        phase=phase,
    )


def _raw_mapping(
    value: object,
    expected: frozenset[str],
    label: str,
) -> Mapping[str, str]:
    record = _keys(value, expected, label)
    if any(type(item) is not str for item in record.values()):
        raise VerificationError(f"{label} values must be exact strings")
    return record  # type: ignore[return-value]


def _uint_text(value: str, label: str) -> int:
    if re.fullmatch(r"0|[1-9][0-9]*", value) is None:
        raise VerificationError(f"{label} is not canonical unsigned integer")
    return int(value)


def _key_value_lines(
    value: str,
    *,
    required: frozenset[str],
    label: str,
) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in value.splitlines():
        parts = line.split()
        if len(parts) != 2 or parts[0] in result:
            raise VerificationError(f"{label} has malformed/duplicate lines")
        result[parts[0]] = _uint_text(parts[1], f"{label}.{parts[0]}")
    if not required.issubset(result):
        raise VerificationError(f"{label} lacks required keys")
    return result


def _duration_usec(value: str) -> int:
    if re.fullmatch(r"0|[1-9][0-9]*", value):
        return int(value)
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(us|ms|s|min|h)", value)
    if match is None:
        raise VerificationError("RuntimeMaxUSec has unsupported syntax")
    factors = {
        "us": Decimal(1),
        "ms": Decimal(1000),
        "s": Decimal(1_000_000),
        "min": Decimal(60_000_000),
        "h": Decimal(3_600_000_000),
    }
    try:
        result = Decimal(match.group(1)) * factors[match.group(2)]
    except InvalidOperation as exc:
        raise VerificationError("RuntimeMaxUSec is invalid") from exc
    if result != result.to_integral_value():
        raise VerificationError("RuntimeMaxUSec is not integral microseconds")
    return int(result)


def _expected_resource_verdict(pre_run: Mapping[str, Any]) -> str:
    expectation = pre_run["expected_payload_status"]["expectation"]
    if expectation == "SUCCESS":
        return RESOURCE_SUCCESS_VERDICT
    if expectation == "POST_SEAL_FAILURE":
        return RESOURCE_EXPECTED_FAILURE_VERDICT
    raise VerificationError("unsupported payload expectation")


def _common_join(
    record: Mapping[str, Any],
    *,
    pre_run: Mapping[str, Any],
    pre_run_identity: Mapping[str, Any],
    selection_identity: Mapping[str, Any],
    invocation_id: str,
    phase: str,
) -> None:
    if (
        record.get("campaign_id") != pre_run["campaign_id"]
        or record.get("run_nonce") != pre_run["run_nonce"]
        or record.get("slot") != pre_run["slot"]
        or record.get("unit_name") != pre_run["unit_name"]
        or record.get("invocation_id") != invocation_id
        or record.get("pre_run_authority_identity") != pre_run_identity
        or record.get("runner_selection_identity") != selection_identity
    ):
        raise VerificationError(f"{phase} authority join failed")
    _epoch_observation(
        record.get("manager_epoch_observation"),
        pre_run=pre_run,
        phase=phase,
    )


def _verify_preterminal_values(
    *,
    pre_run: Mapping[str, Any],
    inner: Mapping[str, Any],
    preterminal: Mapping[str, Any],
) -> dict[str, object]:
    systemd = _raw_mapping(
        preterminal.get("systemd_raw"),
        SYSTEMD_PRETERMINAL_FIELDS,
        "preterminal systemd",
    )
    cgroup = _raw_mapping(
        preterminal.get("cgroup_raw"),
        CGROUP_FIELDS,
        "preterminal cgroup",
    )
    invocation_id = _text(inner.get("invocation_id"), "inner invocation_id")
    keeper_pid = _integer(inner.get("keeper_pid"), "inner keeper_pid", 1)
    keeper_starttime = _integer(
        inner.get("keeper_starttime"),
        "inner keeper_starttime",
        1,
    )
    payload_pid = _integer(inner.get("payload_pid"), "inner payload_pid", 1)
    expected = pre_run["resource_contract"]
    if (
        inner.get("payload_reaped") is not True
        or preterminal.get("payload_current_starttime") is not None
        or preterminal.get("keeper_current_starttime") != keeper_starttime
        or systemd["ActiveState"] != "active"
        or systemd["SubState"] != "running"
        or _uint_text(systemd["MainPID"], "systemd MainPID") != keeper_pid
        or not systemd["ControlGroup"].startswith("/")
        or systemd["InvocationID"] != invocation_id
        or systemd["OOMPolicy"] != "continue"
        or systemd["CollectMode"] != expected["collect_mode"]
        or systemd["KillMode"] != "control-group"
        or systemd["SendSIGKILL"] != "yes"
    ):
        raise VerificationError("preterminal supervisor/payload/systemd state failed")
    if (
        _uint_text(systemd["MemoryHigh"], "systemd MemoryHigh") != expected["memory_high_bytes"]
        or _uint_text(systemd["MemoryMax"], "systemd MemoryMax") != expected["memory_max_bytes"]
        or _uint_text(systemd["MemorySwapMax"], "systemd MemorySwapMax") != expected["memory_swap_max_bytes"]
        or _duration_usec(systemd["RuntimeMaxUSec"]) != expected["runtime_max_seconds"] * 1_000_000
        or _uint_text(cgroup["memory.high"], "cgroup memory.high") != expected["memory_high_bytes"]
        or _uint_text(cgroup["memory.max"], "cgroup memory.max") != expected["memory_max_bytes"]
        or _uint_text(cgroup["memory.swap.max"], "cgroup memory.swap.max") != expected["memory_swap_max_bytes"]
    ):
        raise VerificationError("resource contract drifted")
    memory_current = _uint_text(cgroup["memory.current"], "memory.current")
    memory_peak = _uint_text(cgroup["memory.peak"], "memory.peak")
    swap_current = _uint_text(cgroup["memory.swap.current"], "memory.swap.current")
    if memory_peak < memory_current:
        raise VerificationError("memory.peak is below memory.current")
    events = _key_value_lines(
        cgroup["memory.events"],
        required=MEMORY_EVENT_KEYS,
        label="memory.events",
    )
    if any(events[name] != 0 for name in ("max", "oom", "oom_kill", "oom_group_kill")):
        raise VerificationError("memory limit/OOM event observed")
    procs = [_uint_text(line, "cgroup.procs") for line in cgroup["cgroup.procs"].splitlines() if line]
    if procs != [keeper_pid] or payload_pid in procs:
        raise VerificationError("keeper is not the sole preterminal cgroup member")
    cgroup_events = _key_value_lines(
        cgroup["cgroup.events"],
        required=frozenset({"populated", "frozen"}),
        label="cgroup.events",
    )
    if cgroup_events["populated"] != 1 or cgroup_events["frozen"] != 0:
        raise VerificationError("preterminal cgroup existence/state failed")
    return {
        "control_group": systemd["ControlGroup"],
        "invocation_id": invocation_id,
        "keeper_pid": keeper_pid,
        "memory_current_bytes": memory_current,
        "memory_events": events,
        "memory_peak_bytes": memory_peak,
        "payload_pid": payload_pid,
        "swap_current_bytes": swap_current,
    }


def verify_preterminal(
    *,
    pre_run: Snapshot,
    selection: Snapshot,
    inner: Snapshot,
    preterminal: Snapshot,
    payload_result: Snapshot,
    verifier_tool_identity: Mapping[str, Any],
) -> dict[str, object]:
    """Derive the release prerequisite from raw preterminal evidence."""

    pre = validate_pre_run_authority(pre_run.value)
    _validate_selection(
        selection.value,
        pre_run=pre,
        pre_run_identity=pre_run.identity,
    )
    if verifier_tool_identity != pre["tool_identities"]["organic_resource_verifier"]:
        raise VerificationError("resource verifier tool identity drifted")
    inner_record = inner.value
    preterminal_record = preterminal.value
    if inner_record.get("schema_version") != INNER_SCHEMA:
        raise VerificationError("inner lifecycle schema drifted")
    if preterminal_record.get("schema_version") != PRETERMINAL_SCHEMA:
        raise VerificationError("preterminal schema drifted")
    invocation_id = _text(inner_record.get("invocation_id"), "inner invocation_id")
    _common_join(
        inner_record,
        pre_run=pre,
        pre_run_identity=pre_run.identity,
        selection_identity=selection.identity,
        invocation_id=invocation_id,
        phase="launch",
    )
    _common_join(
        preterminal_record,
        pre_run=pre,
        pre_run_identity=pre_run.identity,
        selection_identity=selection.identity,
        invocation_id=invocation_id,
        phase="preterminal",
    )
    launch_epoch = _replay_epoch_observation_file(
        pre_run=pre,
        phase="launch",
        embedded_observation=inner_record.get("manager_epoch_observation"),
    )
    preterminal_epoch = _replay_epoch_observation_file(
        pre_run=pre,
        phase="preterminal",
        embedded_observation=preterminal_record.get("manager_epoch_observation"),
    )
    if preterminal_record.get("inner_identity") != inner.identity:
        raise VerificationError("preterminal inner identity join failed")
    if (
        inner_record.get("payload_result_identity") != payload_result.identity
        or payload_result.identity["path"] != pre["output_paths"]["attempt_result"]
        or payload_result.value.get("schema_version") != "noncert-cuts-ab16-organic-arm-result-v1"
        or payload_result.value.get("slot") != pre["slot"]
    ):
        raise VerificationError("payload result identity/schema join failed")
    derived = _verify_preterminal_values(
        pre_run=pre,
        inner=inner_record,
        preterminal=preterminal_record,
    )
    expected_payload = pre["expected_payload_status"]
    if (
        inner_record.get("payload_exit_code") != expected_payload["exit_code"]
        or inner_record.get("payload_signal") != expected_payload["signal"]
    ):
        raise VerificationError("payload terminal status differs from preregistration")
    if not (
        _integer(
            launch_epoch.get("observed_at_monotonic_ns"),
            "launch epoch observation",
            1,
        )
        <= _integer(inner_record.get("payload_seal_monotonic_ns"), "payload seal", 1)
        <= _integer(inner_record.get("payload_exit_monotonic_ns"), "payload exit", 1)
        <= _integer(inner_record.get("keeper_ready_monotonic_ns"), "keeper ready", 1)
        and _integer(
            preterminal_epoch.get("observed_at_monotonic_ns"),
            "preterminal epoch observation",
            1,
        )
        <= _integer(preterminal_record.get("captured_at_monotonic_ns"), "preterminal capture", 1)
        and _integer(
            launch_epoch.get("observed_at_monotonic_ns"),
            "launch epoch observation",
            1,
        )
        < _integer(
            preterminal_epoch.get("observed_at_monotonic_ns"),
            "preterminal epoch observation",
            1,
        )
    ):
        raise VerificationError("preterminal time order failed")
    return {
        "authorizations": {
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "production_certified_authorized": False,
            "release_keeper_authorized": True,
        },
        "derived": derived,
        "inner_identity": inner.identity,
        "pre_run_authority_identity": pre_run.identity,
        "preterminal_identity": preterminal.identity,
        "payload_result_identity": payload_result.identity,
        "purpose": PURPOSE,
        "runner_selection_identity": selection.identity,
        "schema_version": RESOURCE_SCHEMA,
        "slot": pre["slot"],
        "status": "PASS",
        "verdict": _expected_resource_verdict(pre),
        "verifier_tool_identity": dict(verifier_tool_identity),
    }


def verify_detached(
    *,
    pre_run: Snapshot,
    selection: Snapshot,
    inner: Snapshot,
    preterminal: Snapshot,
    payload_result: Snapshot,
    resource: Snapshot,
    reference_acquisition: Snapshot,
    release: Snapshot,
    terminal: Snapshot,
    reference_release: Snapshot,
    cleanup: Snapshot,
    detached_epoch: Snapshot,
    verifier_tool_identity: Mapping[str, Any],
) -> dict[str, object]:
    """Replay the full two-stage lifecycle after unit cleanup."""

    pre = validate_pre_run_authority(pre_run.value)
    _validate_selection(
        selection.value,
        pre_run=pre,
        pre_run_identity=pre_run.identity,
    )
    expected_resource = verify_preterminal(
        pre_run=pre_run,
        selection=selection,
        inner=inner,
        preterminal=preterminal,
        payload_result=payload_result,
        verifier_tool_identity=verifier_tool_identity,
    )
    if resource.value != expected_resource:
        raise VerificationError("resource receipt semantic replay differs")
    acquisition_record = reference_acquisition.value
    release_record = release.value
    terminal_record = terminal.value
    reference_release_record = reference_release.value
    cleanup_record = cleanup.value
    detached_epoch_record = detached_epoch.value
    if acquisition_record.get("schema_version") != REFERENCE_ACQUISITION_SCHEMA:
        raise VerificationError("reference acquisition schema drifted")
    if release_record.get("schema_version") != RELEASE_SCHEMA:
        raise VerificationError("release schema drifted")
    if terminal_record.get("schema_version") != TERMINAL_SCHEMA:
        raise VerificationError("terminal schema drifted")
    if reference_release_record.get("schema_version") != REFERENCE_RELEASE_SCHEMA:
        raise VerificationError("reference release schema drifted")
    if cleanup_record.get("schema_version") != CLEANUP_SCHEMA:
        raise VerificationError("cleanup schema drifted")
    invocation_id = _text(inner.value.get("invocation_id"), "inner invocation_id")
    for phase, record in (
        ("reference-acquire", acquisition_record),
        ("release", release_record),
        ("terminal-first", terminal_record),
        ("reference-release", reference_release_record),
        ("cleanup", cleanup_record),
    ):
        _common_join(
            record,
            pre_run=pre,
            pre_run_identity=pre_run.identity,
            selection_identity=selection.identity,
            invocation_id=invocation_id,
            phase=phase,
        )
    if (
        release_record.get("preterminal_identity") != preterminal.identity
        or release_record.get("resource_verification_identity") != resource.identity
        or release_record.get("reference_acquisition_identity") != reference_acquisition.identity
        or release_record.get("verdict") != _expected_resource_verdict(pre)
        or terminal_record.get("release_identity") != release.identity
        or terminal_record.get("reference_acquisition_identity") != reference_acquisition.identity
        or reference_release_record.get("reference_acquisition_identity") != reference_acquisition.identity
        or reference_release_record.get("terminal_identity") != terminal.identity
        or cleanup_record.get("terminal_identity") != terminal.identity
        or cleanup_record.get("reference_release_identity") != reference_release.identity
    ):
        raise VerificationError("release/terminal/cleanup identity chain failed")
    acquisition_systemd = _raw_mapping(
        acquisition_record.get("systemd_raw"),
        SYSTEMD_REFERENCE_FIELDS,
        "reference acquisition systemd",
    )
    first_systemd = _raw_mapping(
        terminal_record.get("first_systemd_raw"),
        SYSTEMD_TERMINAL_FIELDS,
        "first terminal systemd",
    )
    stable_systemd = _raw_mapping(
        terminal_record.get("stable_systemd_raw"),
        SYSTEMD_TERMINAL_FIELDS,
        "stable terminal systemd",
    )
    if type(invocation_id) is not str or re.fullmatch(r"[0-9a-f]{32}", invocation_id) is None:
        raise VerificationError("launch InvocationID is absent or malformed")
    manager_owner = _text(pre["manager_epoch"].get("dbus_unique_owner"), "manager DBus owner")

    def reference_call(
        value: object,
        *,
        label: str,
    ) -> Mapping[str, str]:
        record = _keys(
            value,
            {
                "client_unique_name",
                "manager_owner_after",
                "manager_owner_before",
                "unit_name",
            },
            label,
        )
        if any(type(item) is not str or not item for item in record.values()):
            raise VerificationError(f"{label} contains an invalid string")
        if (
            record["unit_name"] != pre["unit_name"]
            or record["manager_owner_before"] != manager_owner
            or record["manager_owner_after"] != manager_owner
            or re.fullmatch(r":[0-9]+\.[0-9]+", record["client_unique_name"]) is None
        ):
            raise VerificationError(f"{label} authority join failed")
        return record  # type: ignore[return-value]

    acquired_call = reference_call(
        acquisition_record.get("call_evidence"),
        label="RefUnit call evidence",
    )
    released_call = reference_call(
        reference_release_record.get("call_evidence"),
        label="UnrefUnit call evidence",
    )
    if acquired_call["client_unique_name"] != released_call["client_unique_name"]:
        raise VerificationError("RefUnit/UnrefUnit did not use the same DBus client")
    if (
        acquisition_systemd["LoadState"] != "loaded"
        or acquisition_systemd["CollectMode"] != "inactive-or-failed"
        or acquisition_systemd["InvocationID"] != invocation_id
    ):
        raise VerificationError("reference acquisition did not bind the live unit")
    stable_epoch = terminal_record.get("stable_manager_epoch_observation")
    _epoch_observation(
        stable_epoch,
        pre_run=pre,
        phase="terminal-stable",
    )
    if (
        first_systemd != stable_systemd
        or first_systemd["LoadState"] != "loaded"
        or first_systemd["CollectMode"] != "inactive-or-failed"
        or first_systemd["InvocationID"] != invocation_id
    ):
        raise VerificationError("terminal snapshots did not retain the exact unit identity")
    expected_payload = pre["expected_payload_status"]
    if expected_payload["expectation"] == "SUCCESS":
        terminal_ok = (
            first_systemd["Result"] == "success"
            and first_systemd["ExecMainCode"] in {"exited", "1"}
            and first_systemd["ExecMainStatus"] == "0"
            and first_systemd["ActiveState"] == "inactive"
            and first_systemd["SubState"] in {"dead", "exited"}
        )
        detached_verdict = "RESOURCE_TERMINAL_CLEANUP_REPLAY_PASS"
    else:
        expected_supervisor_status = (
            expected_payload["exit_code"] if expected_payload["exit_code"] != 0 else 128 + expected_payload["signal"]
        )
        terminal_ok = (
            first_systemd["Result"] == "exit-code"
            and first_systemd["ExecMainCode"] in {"exited", "1"}
            and first_systemd["ExecMainStatus"] == str(expected_supervisor_status)
            and first_systemd["ActiveState"] == "failed"
            and first_systemd["SubState"] == "failed"
        )
        detached_verdict = "EXPECTED_POST_SEAL_FAILURE_REPLAY_PASS"
    if not terminal_ok:
        raise VerificationError("systemd terminal status differs from preregistration")
    if (
        cleanup_record.get("payload_current_starttime") is not None
        or cleanup_record.get("keeper_current_starttime") is not None
        or cleanup_record.get("cgroup_path_exists") is not False
        or cleanup_record.get("matching_unit_names") != []
        or cleanup_record.get("unit_load_state") != "not-found"
    ):
        raise VerificationError("cleanup did not prove absence of residual state")
    times = [
        _integer(inner.value.get("payload_seal_monotonic_ns"), "payload seal", 1),
        _integer(inner.value.get("payload_exit_monotonic_ns"), "payload exit", 1),
        _integer(inner.value.get("keeper_ready_monotonic_ns"), "keeper ready", 1),
        _integer(preterminal.value.get("captured_at_monotonic_ns"), "preterminal", 1),
        _integer(
            acquisition_record.get("acquired_at_monotonic_ns"),
            "reference acquisition",
            1,
        ),
        _integer(release_record.get("release_monotonic_ns"), "release", 1),
        _integer(
            terminal_record.get("first_captured_at_monotonic_ns"),
            "first terminal",
            1,
        ),
        _integer(
            terminal_record.get("stable_captured_at_monotonic_ns"),
            "stable terminal",
            1,
        ),
        _integer(
            reference_release_record.get("released_at_monotonic_ns"),
            "reference release",
            1,
        ),
        _integer(cleanup_record.get("captured_at_monotonic_ns"), "cleanup", 1),
    ]
    if times != sorted(times) or len(set(times)) != len(times):
        raise VerificationError("two-stage lifecycle time chain failed")
    phase_observations = {
        "launch": inner.value.get("manager_epoch_observation"),
        "preterminal": preterminal.value.get("manager_epoch_observation"),
        "reference-acquire": acquisition_record.get("manager_epoch_observation"),
        "release": release_record.get("manager_epoch_observation"),
        "terminal-first": terminal_record.get("manager_epoch_observation"),
        "terminal-stable": stable_epoch,
        "reference-release": reference_release_record.get("manager_epoch_observation"),
        "cleanup": cleanup_record.get("manager_epoch_observation"),
        "detached-replay": detached_epoch_record,
    }
    epoch_times: dict[str, int] = {}
    for phase, embedded in phase_observations.items():
        replayed_epoch = _replay_epoch_observation_file(
            pre_run=pre,
            phase=phase,
            embedded_observation=embedded,
            supplied_snapshot=(detached_epoch if phase == "detached-replay" else None),
        )
        epoch_times[phase] = _integer(
            replayed_epoch.get("observed_at_monotonic_ns"),
            f"{phase} epoch observation",
            1,
        )
    ordered_epoch_times = [
        epoch_times[phase]
        for phase in (
            "launch",
            "preterminal",
            "reference-acquire",
            "release",
            "terminal-first",
            "terminal-stable",
            "reference-release",
            "cleanup",
            "detached-replay",
        )
    ]
    if (
        ordered_epoch_times != sorted(ordered_epoch_times)
        or len(set(ordered_epoch_times)) != len(ordered_epoch_times)
        or epoch_times["launch"] > times[0]
        or epoch_times["preterminal"] > times[3]
        or epoch_times["reference-acquire"] > times[4]
        or epoch_times["release"] > times[5]
        or epoch_times["terminal-first"] > times[6]
        or epoch_times["terminal-stable"] > times[7]
        or epoch_times["reference-release"] > times[8]
        or epoch_times["cleanup"] > times[9]
        or epoch_times["detached-replay"] <= times[9]
    ):
        raise VerificationError("manager epoch observation time chain failed")
    if times[6] - times[5] > pre["reference_contract"]["terminal_transition_deadline_seconds"] * 1_000_000_000:
        raise VerificationError("terminal transition exceeded its fixed deadline")
    if times[7] - times[6] < pre["reference_contract"]["stability_hold_ns"]:
        raise VerificationError("terminal reference stability interval is too short")
    if times[9] - times[8] > pre["reference_contract"]["post_unref_cleanup_deadline_seconds"] * 1_000_000_000:
        raise VerificationError("post-Unref cleanup exceeded its fixed deadline")
    return {
        "authorizations": {
            "family_global_soundness_authorized": False,
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "production_certified_authorized": False,
            "stage_b_promotion_authorized": False,
        },
        "cleanup_identity": cleanup.identity,
        "derived": expected_resource["derived"],
        "detached_epoch_observation_identity": detached_epoch.identity,
        "inner_identity": inner.identity,
        "pre_run_authority_identity": pre_run.identity,
        "preterminal_identity": preterminal.identity,
        "purpose": PURPOSE,
        "reference_acquisition_identity": reference_acquisition.identity,
        "reference_release_identity": reference_release.identity,
        "release_identity": release.identity,
        "resource_verification_identity": resource.identity,
        "runner_selection_identity": selection.identity,
        "schema_version": DETACHED_SCHEMA,
        "slot": pre["slot"],
        "status": "PASS",
        "terminal_identity": terminal.identity,
        "verdict": detached_verdict,
        "verifier_tool_identity": dict(verifier_tool_identity),
    }


def current_tool_identity() -> dict[str, object]:
    """Return this verifier's same-FD detached byte identity."""

    _raw, identity = snapshot_bytes(Path(__file__))
    return identity


def verify_preterminal_paths(
    *,
    pre_run_path: Path | str,
    selection_path: Path | str,
    inner_path: Path | str,
    preterminal_path: Path | str,
    payload_result_path: Path | str,
    output_path: Path | str,
) -> dict[str, object]:
    receipt = verify_preterminal(
        pre_run=snapshot_json(pre_run_path),
        selection=snapshot_json(selection_path),
        inner=snapshot_json(inner_path),
        preterminal=snapshot_json(preterminal_path),
        payload_result=snapshot_json(payload_result_path),
        verifier_tool_identity=current_tool_identity(),
    )
    write_exclusive(output_path, receipt)
    return receipt


def verify_detached_paths(
    *,
    pre_run_path: Path | str,
    selection_path: Path | str,
    inner_path: Path | str,
    preterminal_path: Path | str,
    payload_result_path: Path | str,
    resource_path: Path | str,
    reference_acquisition_path: Path | str,
    release_path: Path | str,
    terminal_path: Path | str,
    reference_release_path: Path | str,
    cleanup_path: Path | str,
    detached_epoch_path: Path | str,
    output_path: Path | str,
) -> dict[str, object]:
    receipt = verify_detached(
        pre_run=snapshot_json(pre_run_path),
        selection=snapshot_json(selection_path),
        inner=snapshot_json(inner_path),
        preterminal=snapshot_json(preterminal_path),
        payload_result=snapshot_json(payload_result_path),
        resource=snapshot_json(resource_path),
        reference_acquisition=snapshot_json(reference_acquisition_path),
        release=snapshot_json(release_path),
        terminal=snapshot_json(terminal_path),
        reference_release=snapshot_json(reference_release_path),
        cleanup=snapshot_json(cleanup_path),
        detached_epoch=snapshot_json(detached_epoch_path),
        verifier_tool_identity=current_tool_identity(),
    )
    write_exclusive(output_path, receipt)
    return receipt
