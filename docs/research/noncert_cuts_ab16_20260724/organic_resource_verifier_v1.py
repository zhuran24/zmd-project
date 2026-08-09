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
RUNNER_SELECTION_SCHEMA = "noncert-cuts-ab16-organic-arm-selection-v2"
ATTEMPT_EXECUTION_SCHEMA = "noncert-cuts-ab16-attempt-execution-v1"
EPOCH_SCHEMA = "noncert-cuts-ab16-manager-epoch-observation-v1"
INNER_SCHEMA = "noncert-cuts-ab16-inner-lifecycle-v1"
PRETERMINAL_SCHEMA = "noncert-cuts-ab16-preterminal-resource-v1"
RESOURCE_SCHEMA = "noncert-cuts-ab16-resource-verification-v1"
RELEASE_SCHEMA = "noncert-cuts-ab16-release-token-v1"
TERMINAL_SCHEMA = "noncert-cuts-ab16-terminal-envelope-v1"
CLEANUP_SCHEMA = "noncert-cuts-ab16-cleanup-v1"
DETACHED_SCHEMA = "noncert-cuts-ab16-detached-resource-terminal-v1"

PURPOSE = "PROSPECTIVE_AB16_ORGANIC_ARM_RESOURCE_AUTHORITY"
PRE_RUN_PURPOSE = "PROSPECTIVE_AB16_ORGANIC_ARM_PRE_RUN_AUTHORITY"
RUNNER_PURPOSE = "prospective_noncert_cuts_ab16_formal_arm"
EXECUTION_CLASS = "FORMAL_AB16"
LAUNCH_ENVIRONMENT_SCHEMA = "noncert-cuts-ab16-launch-environment-v1"
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
ATTEMPT_EXECUTION_TOOL_ROLES = frozenset(
    {
        "ab16_contract",
        "ab16_terminal_gate",
        "attestor_python",
        "busctl",
        "manager_attestor",
        "manager_epoch_authority",
        "organic_arm_replay",
        "organic_arm_runner",
        "organic_resource_lifecycle",
        "organic_resource_verifier",
        "organic_unit_orchestrator",
        "python3_13",
        "sudo",
        "systemctl",
        "systemd_run",
    }
)

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
        "ActiveState",
        "SubState",
        "ControlGroup",
        "InvocationID",
        "Result",
        "ExecMainCode",
        "ExecMainStatus",
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


def _strict_loads_runner_json(raw: bytes, label: str) -> Mapping[str, Any]:
    """Parse the runner's canonical object framing with one trailing newline."""

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
    if type(value) is not dict or canonical_json_bytes(value) + b"\n" != raw:
        raise VerificationError(f"{label} is not a canonical runner JSON object")
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


def snapshot_runner_json(path: Path | str) -> Snapshot:
    """Read one runner result using its typed trailing-newline framing."""

    raw, identity = snapshot_bytes(path)
    return Snapshot(
        raw=raw,
        value=_strict_loads_runner_json(raw, str(Path(path))),
        identity=identity,
    )


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
    if execution_class != EXECUTION_CLASS:
        raise VerificationError("resource contract execution class is invalid")
    expected = FORMAL_RESOURCE_CONTRACT
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


def _epoch_attestor_python(value: object, label: str) -> Mapping[str, Any]:
    epoch = _epoch(value, label)
    toolchain = _mapping(epoch.get("attestation_toolchain"), f"{label}.attestation_toolchain")
    python = _mapping(toolchain.get("python"), f"{label}.attestation_toolchain.python")
    if (
        not Path(_text(python.get("path"), f"{label}.attestation_toolchain.python.path")).is_absolute()
        or type(python.get("sha256")) is not str
        or SHA256_RE.fullmatch(python["sha256"]) is None
        or type(python.get("size_bytes")) is not int
        or python["size_bytes"] < 0
        or type(python.get("mode")) is not int
        or python["mode"] < 0
    ):
        raise VerificationError(f"{label}.attestation_toolchain.python identity is invalid")
    return python


def _epoch_digest(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(_epoch(value, "manager epoch"))).hexdigest()


def _detached_identity(value: Mapping[str, Any]) -> dict[str, object]:
    return {field: value[field] for field in ("path", "sha256", "size_bytes")}


def _research_only_authorizations(value: object, label: str) -> Mapping[str, Any]:
    record = _keys(
        value,
        {
            "cut_authorized",
            "family_global_soundness_authorized",
            "global_claim_authorized",
            "lower_bound_authorized",
            "mathematical_claim_authorized",
            "optimality_authorized",
            "production_certified_authorized",
            "stage_b_promotion_authorized",
            "upper_bound_authorized",
            "witness_authorized",
        },
        label,
    )
    if any(type(item) is not bool or item is not False for item in record.values()):
        raise VerificationError(f"{label} must remain research-only")
    return record


def _validate_attempt_execution(value: object) -> Mapping[str, Any]:
    record = _keys(
        value,
        {
            "attempt_ordinal",
            "authorizations",
            "authority_attempt_dir",
            "authority_chain",
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
            "unit_name",
        },
        "attempt execution",
    )
    if (
        record["schema_version"] != ATTEMPT_EXECUTION_SCHEMA
        or record["status"] != "READY"
        or _integer(record["attempt_ordinal"], "attempt ordinal", 1) < 1
        or type(record["slot"]) is not str
        or type(record["campaign_id"]) is not str
        or SHA256_RE.fullmatch(record["campaign_id"]) is None
        or type(record["repository_head"]) is not str
        or GIT_SHA_RE.fullmatch(record["repository_head"]) is None
    ):
        raise VerificationError("attempt execution scalar semantics drifted")
    for field in ("preregistration_sha256", "input_set_sha256", "scientific_input_set_sha256", "scientific_materialization_sha256"):
        if type(record[field]) is not str or SHA256_RE.fullmatch(record[field]) is None:
            raise VerificationError(f"attempt execution {field} is invalid")
    _research_only_authorizations(record["authorizations"], "attempt execution authorizations")
    for field in ("input_set_identity", "repository_git_tool_identity"):
        _identity(record[field], f"attempt execution {field}", mode_required=True)
    for field in ("campaign_root_identity", "continuation_identity", "manifest_identity", "suite_selection_identity"):
        _identity(record[field], f"attempt execution {field}")
    authority_attempt = Path(_text(record["authority_attempt_dir"], "authority attempt dir"))
    run_dir = Path(_text(record["run_dir"], "attempt run dir"))
    support_dir = Path(_text(record["support_dir"], "attempt support dir"))
    pre_run_path = Path(_text(record["pre_run_authority_path"], "attempt pre-run path"))
    selection_path = Path(_text(record["selection_path"], "attempt selection path"))
    repository_root = Path(_text(record["repository_root"], "attempt repository root"))
    if (
        any(not path.is_absolute() for path in (authority_attempt, run_dir, support_dir, repository_root))
        or run_dir.parent != authority_attempt
        or support_dir.parent != authority_attempt
        or run_dir == support_dir
        or pre_run_path != run_dir / "pre-run-authority.json"
        or selection_path != run_dir / "selection.json"
        or Path(record["input_set_identity"]["path"]) != authority_attempt / "attempt-input-set.json"
    ):
        raise VerificationError("attempt execution topology drifted")
    unit_name = _text(record["unit_name"], "attempt unit name")
    if not unit_name.endswith(".service") or "/" in unit_name:
        raise VerificationError("attempt unit name is invalid")
    _epoch(record["manager_epoch"], "attempt execution manager epoch")
    package = _keys(
        record["package"],
        {"manifest_identity", "package_id", "seal_identity"},
        "attempt execution package",
    )
    _identity(package["manifest_identity"], "attempt package manifest")
    seal = _identity(package["seal_identity"], "attempt package seal")
    if (
        type(package["package_id"]) is not str
        or SHA256_RE.fullmatch(package["package_id"]) is None
        or package["package_id"] != seal["sha256"]
    ):
        raise VerificationError("attempt execution package drifted")
    chain = _keys(
        record["authority_chain"],
        {"campaign_root_identity", "continuation_identity", "manager_epoch_authority_identity", "package"},
        "attempt execution authority chain",
    )
    for field in ("campaign_root_identity", "continuation_identity", "manager_epoch_authority_identity"):
        _identity(chain[field], f"attempt authority chain {field}")
    if (
        chain["campaign_root_identity"] != record["campaign_root_identity"]
        or chain["continuation_identity"] != record["continuation_identity"]
        or chain["package"] != package
    ):
        raise VerificationError("attempt execution authority-chain projection drifted")
    tools = _keys(record["tool_identities"], ATTEMPT_EXECUTION_TOOL_ROLES, "attempt execution tools")
    for role, identity in tools.items():
        _identity(identity, f"attempt execution tool {role}", mode_required=True)
    manager_python = _epoch_attestor_python(record["manager_epoch"], "attempt execution manager epoch")
    if any(
        manager_python[field] != tools["attestor_python"][field]
        for field in tools["attestor_python"]
    ):
        raise VerificationError("attempt execution attestor Python differs from manager epoch")
    return record


def _load_attempt_execution(identity: object) -> tuple[Mapping[str, Any], dict[str, object]]:
    expected = _identity(identity, "attempt execution identity")
    snapshot = snapshot_json(expected["path"])
    observed = _detached_identity(snapshot.identity)
    if observed != dict(expected):
        raise VerificationError("attempt execution identity replay failed")
    checked = _validate_attempt_execution(snapshot.value)
    if Path(snapshot.identity["path"]) != Path(checked["authority_attempt_dir"]) / "attempt-execution.json":
        raise VerificationError("attempt execution record escaped its authority attempt")
    return checked, observed


def validate_pre_run_authority(
    value: object,
    *,
    campaign_root: Mapping[str, Any] | None = None,
    manifest: Mapping[str, Any] | None = None,
    suite_selection: Mapping[str, Any] | None = None,
    expected_slot: str | None = None,
    attempt_execution: Mapping[str, Any] | None = None,
    attempt_execution_identity: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Validate one non-authorizing receipt and optional authority context."""

    expected_keys = {
        "arm",
        "arm_binding_identity",
        "arm_launch_authorized",
        "arm_selection_write_authorized",
        "attempt_execution_identity",
        "attempt_dir",
        "attempt_ordinal",
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
        "prospective_manifest_identity",
        "preregistration_sha256",
        "purpose",
        "repository_head",
        "repository_root",
        "repository_git_tool_identity",
        "resource_contract",
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
    execution, execution_identity = _load_attempt_execution(record.get("attempt_execution_identity"))
    if attempt_execution is not None and _validate_attempt_execution(attempt_execution) != execution:
        raise VerificationError("supplied attempt execution differs from replayed bytes")
    if attempt_execution_identity is not None and dict(
        _identity(attempt_execution_identity, "supplied attempt execution identity")
    ) != execution_identity:
        raise VerificationError("supplied attempt execution identity differs from replayed bytes")
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
        or record.get("execution_class") != EXECUTION_CLASS
        or record.get("attempt_ordinal") != execution["attempt_ordinal"]
        or record.get("preregistration_sha256") != execution["preregistration_sha256"]
    ):
        raise VerificationError("pre-run authority semantics drifted")
    _validate_resource_contract(
        record["resource_contract"],
        execution_class=record["execution_class"],
    )
    repository_root = Path(_text(record["repository_root"], "repository root"))
    if not repository_root.is_absolute():
        raise VerificationError("pre-run repository root must be absolute")
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
    ):
        _replay_identity(record.get(field), f"pre-run {field}")
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
        "attestor_python",
        "busctl",
        "manager_attestor",
        "manager_epoch_authority",
        "organic_arm_runner",
        "organic_resource_lifecycle",
        "organic_resource_verifier",
        "organic_unit_orchestrator",
        "python3_13",
        "sudo",
        "systemctl",
        "systemd_run",
    }:
        raise VerificationError("pre-run tool role set drifted")
    for role, identity in tools.items():
        _replay_identity(identity, f"pre-run tool {role}", mode_required=True)
    manager_python = _epoch_attestor_python(record.get("manager_epoch"), "pre-run manager epoch")
    if any(
        manager_python[field] != tools["attestor_python"][field]
        for field in tools["attestor_python"]
    ):
        raise VerificationError("pre-run attestor Python differs from manager epoch")
    outputs = _mapping(record.get("output_paths"), "pre-run output paths")
    required_outputs = {
        "attempt_result",
        "cleanup",
        "detached_replay",
        "inner",
        "preterminal",
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
        "release",
        "terminal",
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
    if record.get("prelaunch_allowlist") != [
        "pre-run-authority.json",
        "selection.json",
    ]:
        raise VerificationError("pre-run allowlist drifted")
    launch = _mapping(record.get("launch"), "pre-run launch")
    if set(launch) != {
        "cwd",
        "environment_identity",
        "payload_argv",
        "python3_13_path",
        "supervisor_argv",
        "systemctl_path",
        "systemd_run_path",
    }:
        raise VerificationError("pre-run launch key set drifted")
    if (
        not Path(_text(launch["cwd"], "pre-run launch cwd")).is_absolute()
        or not Path(_text(launch["systemd_run_path"], "pre-run systemd-run path")).is_absolute()
    ):
        raise VerificationError("pre-run launch paths must be absolute")
    _load_launch_environment(launch["environment_identity"])
    for launch_field, tool_role in (
        ("python3_13_path", "python3_13"),
        ("systemctl_path", "systemctl"),
        ("systemd_run_path", "systemd_run"),
    ):
        if launch[launch_field] != tools[tool_role]["path"]:
            raise VerificationError(f"pre-run launch {launch_field} differs from pinned tool")
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
    if launch["payload_argv"][2] != tools["organic_arm_runner"]["path"]:
        raise VerificationError("pre-run formal payload tool path drifted")
    preflight = _mapping(record.get("preflight_results"), "pre-run preflight")
    required_preflight = {
        "epoch_identity_pass",
        "head_identity_pass",
        "package_replay_pass",
        "path_preregistration_pass",
        "resource_contract_pass",
        "slot_order_pass",
        "strict_inputs_replay_pass",
        "tool_identities_replay_pass",
    }
    if set(preflight) != required_preflight or any(
        type(item) is not bool or item is not True for item in preflight.values()
    ):
        raise VerificationError("pre-run mandatory preflight is not all PASS")
    execution_joins = {
        "attempt_dir": "run_dir",
        "authority_chain": "authority_chain",
        "campaign_id": "campaign_id",
        "campaign_root_identity": "campaign_root_identity",
        "continuation_identity": "continuation_identity",
        "manager_epoch": "manager_epoch",
        "package": "package",
        "pre_run_authority_path": "pre_run_authority_path",
        "prospective_manifest_identity": "manifest_identity",
        "repository_git_tool_identity": "repository_git_tool_identity",
        "repository_head": "repository_head",
        "repository_root": "repository_root",
        "run_nonce": "run_nonce",
        "runner_selection_path": "selection_path",
        "slot": "slot",
        "suite_selection_identity": "suite_selection_identity",
        "unit_name": "unit_name",
    }
    for pre_run_field, execution_field in execution_joins.items():
        if record.get(pre_run_field) != execution[execution_field]:
            raise VerificationError(f"pre-run {pre_run_field} differs from attempt execution")
    for role in (
        "attestor_python",
        "busctl",
        "manager_attestor",
        "manager_epoch_authority",
        "organic_arm_runner",
        "organic_resource_lifecycle",
        "organic_resource_verifier",
        "organic_unit_orchestrator",
        "python3_13",
        "sudo",
        "systemctl",
        "systemd_run",
    ):
        if tools[role] != execution["tool_identities"][role]:
            raise VerificationError(f"pre-run tool {role} differs from attempt execution")
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
        slot = record.get("slot")
        if (
            type(arm_sequence) is not list
            or slot not in arm_sequence
            or manifest.get("preregistration_sha256") != record.get("preregistration_sha256")
            or manifest.get("seed") != record.get("seed")
            or manifest.get("workers") != record.get("workers")
            or manifest.get("scientific_input_set_sha256") != execution["scientific_input_set_sha256"]
            or manifest.get("scientific_materialization_sha256")
            != execution["scientific_materialization_sha256"]
        ):
            raise VerificationError("pre-run scientific manifest join failed")
        if slot != (f"{record.get('configuration')}-{record.get('order')}-{record.get('arm')}"):
            raise VerificationError("pre-run slot decomposition failed")
    if suite_selection is not None:
        suite_authorizations = suite_selection.get("authorizations")
        if (
            suite_selection.get("schema_version") != "noncert-cuts-ab16-suite-selection-v1"
            or suite_selection.get("purpose") != "AB16_SUITE_SELECTION_NO_ARM_LAUNCH"
            or suite_selection.get("status") != "PASS"
            or type(suite_authorizations) is not dict
            or not suite_authorizations
            or any(value is not False for value in suite_authorizations.values())
            or suite_selection.get("manifest_identity") != record["prospective_manifest_identity"]
            or suite_selection.get("preregistration_sha256") != record["preregistration_sha256"]
            or suite_selection.get("scientific_input_set_sha256") != execution["scientific_input_set_sha256"]
            or suite_selection.get("scientific_materialization_sha256")
            != execution["scientific_materialization_sha256"]
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
            "attempt_execution_identity",
            "attempt_dir",
            "attempt_ordinal",
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
            "manifest_identity",
            "order",
            "pre_run_authority_identity",
            "preregistration_sha256",
            "purpose",
            "repository_head",
            "repository_root",
            "repository_git_tool_identity",
            "run_nonce",
            "schema_version",
            "seed",
            "selection_nonce",
            "slot",
            "unit_name",
            "workers",
        },
        "runner selection",
    )
    formal = (
        record.get("schema_version") == RUNNER_SELECTION_SCHEMA
        and record.get("purpose") == RUNNER_PURPOSE
        and record.get("execution_class") == EXECUTION_CLASS
    )
    if not formal or record.get("fresh_process_required") is not True:
        raise VerificationError("runner selection semantics drifted")
    execution, execution_identity = _load_attempt_execution(pre_run.get("attempt_execution_identity"))
    selected_pre_run_identity = _identity(
        record.get("pre_run_authority_identity"),
        "runner selection pre-run identity",
    )
    if {field: pre_run_identity[field] for field in selected_pre_run_identity} != selected_pre_run_identity:
        raise VerificationError("runner selection pre-run identity drifted")
    joins = {
        "arm": "arm",
        "arm_binding_identity": "arm_binding_identity",
        "attempt_execution_identity": "attempt_execution_identity",
        "attempt_dir": "attempt_dir",
        "attempt_ordinal": "attempt_ordinal",
        "authority_chain": "authority_chain",
        "baseline_admission_identity": "baseline_admission_identity",
        "baseline_incumbent_sha256": "baseline_incumbent_sha256",
        "campaign_id": "campaign_id",
        "common_prestate_identity": "common_prestate_identity",
        "configuration": "configuration",
        "execution_class": "execution_class",
        "expected_payload_status": "expected_payload_status",
        "order": "order",
        "preregistration_sha256": "preregistration_sha256",
        "repository_head": "repository_head",
        "repository_root": "repository_root",
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
    if (
        record.get("attempt_execution_identity") != execution_identity
        or record.get("attempt_dir") != execution["run_dir"]
        or record.get("attempt_ordinal") != execution["attempt_ordinal"]
        or record.get("preregistration_sha256") != execution["preregistration_sha256"]
        or record.get("slot") != execution["slot"]
        or record.get("unit_name") != execution["unit_name"]
        or record.get("repository_head") != execution["repository_head"]
        or record.get("repository_root") != execution["repository_root"]
        or record.get("repository_git_tool_identity") != execution["repository_git_tool_identity"]
        or record.get("authority_chain") != execution["authority_chain"]
    ):
        raise VerificationError("runner selection differs from attempt execution")
    expected_families = (
        []
        if record["arm"] == "control"
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
        _integer(inner_record.get("payload_seal_monotonic_ns"), "payload seal", 1)
        <= _integer(inner_record.get("payload_exit_monotonic_ns"), "payload exit", 1)
        <= _integer(inner_record.get("keeper_ready_monotonic_ns"), "keeper ready", 1)
        <= _integer(preterminal_record.get("captured_at_monotonic_ns"), "preterminal capture", 1)
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
        "inner_identity": _detached_identity(inner.identity),
        "pre_run_authority_identity": _detached_identity(pre_run.identity),
        "preterminal_identity": _detached_identity(preterminal.identity),
        "payload_result_identity": _detached_identity(payload_result.identity),
        "purpose": PURPOSE,
        "runner_selection_identity": _detached_identity(selection.identity),
        "schema_version": RESOURCE_SCHEMA,
        "slot": pre["slot"],
        "status": "PASS",
        "verdict": _expected_resource_verdict(pre),
        "verifier_tool_identity": _detached_identity(verifier_tool_identity),
    }


def verify_detached(
    *,
    pre_run: Snapshot,
    selection: Snapshot,
    inner: Snapshot,
    preterminal: Snapshot,
    payload_result: Snapshot,
    resource: Snapshot,
    release: Snapshot,
    terminal: Snapshot,
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
    release_record = release.value
    terminal_record = terminal.value
    cleanup_record = cleanup.value
    detached_epoch_record = detached_epoch.value
    if release_record.get("schema_version") != RELEASE_SCHEMA:
        raise VerificationError("release schema drifted")
    if terminal_record.get("schema_version") != TERMINAL_SCHEMA:
        raise VerificationError("terminal schema drifted")
    if cleanup_record.get("schema_version") != CLEANUP_SCHEMA:
        raise VerificationError("cleanup schema drifted")
    _epoch_observation(
        detached_epoch_record,
        pre_run=pre,
        phase="detached-replay",
    )
    invocation_id = _text(inner.value.get("invocation_id"), "inner invocation_id")
    for phase, record in (
        ("release", release_record),
        ("terminal", terminal_record),
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
        or release_record.get("verdict") != _expected_resource_verdict(pre)
        or terminal_record.get("release_identity") != release.identity
        or cleanup_record.get("terminal_identity") != terminal.identity
    ):
        raise VerificationError("release/terminal/cleanup identity chain failed")
    systemd = _raw_mapping(
        terminal_record.get("systemd_raw"),
        SYSTEMD_TERMINAL_FIELDS,
        "terminal systemd",
    )
    expected_payload = pre["expected_payload_status"]
    if expected_payload["expectation"] == "SUCCESS":
        terminal_ok = (
            systemd["Result"] == "success"
            and systemd["ExecMainCode"] in {"exited", "1"}
            and systemd["ExecMainStatus"] == "0"
            and systemd["ActiveState"] == "inactive"
            and systemd["SubState"] in {"dead", "exited"}
        )
        detached_verdict = "RESOURCE_TERMINAL_CLEANUP_REPLAY_PASS"
    else:
        expected_supervisor_status = (
            expected_payload["exit_code"] if expected_payload["exit_code"] != 0 else 128 + expected_payload["signal"]
        )
        terminal_ok = (
            systemd["Result"] == "exit-code"
            and systemd["ExecMainCode"] in {"exited", "1"}
            and systemd["ExecMainStatus"] == str(expected_supervisor_status)
            and systemd["ActiveState"] == "failed"
            and systemd["SubState"] == "failed"
        )
        detached_verdict = "EXPECTED_POST_SEAL_FAILURE_REPLAY_PASS"
    if systemd["InvocationID"] != invocation_id or not terminal_ok:
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
        _integer(release_record.get("release_monotonic_ns"), "release", 1),
        _integer(terminal_record.get("captured_at_monotonic_ns"), "terminal", 1),
        _integer(cleanup_record.get("captured_at_monotonic_ns"), "cleanup", 1),
    ]
    if times != sorted(times) or len(set(times)) != len(times):
        raise VerificationError("two-stage lifecycle time chain failed")
    return {
        "authorizations": {
            "family_global_soundness_authorized": False,
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "production_certified_authorized": False,
            "stage_b_promotion_authorized": False,
        },
        "cleanup_identity": _detached_identity(cleanup.identity),
        "derived": expected_resource["derived"],
        "detached_epoch_observation_identity": _detached_identity(detached_epoch.identity),
        "inner_identity": _detached_identity(inner.identity),
        "pre_run_authority_identity": _detached_identity(pre_run.identity),
        "preterminal_identity": _detached_identity(preterminal.identity),
        "purpose": PURPOSE,
        "release_identity": _detached_identity(release.identity),
        "resource_verification_identity": _detached_identity(resource.identity),
        "runner_selection_identity": _detached_identity(selection.identity),
        "schema_version": DETACHED_SCHEMA,
        "slot": pre["slot"],
        "status": "PASS",
        "terminal_identity": _detached_identity(terminal.identity),
        "verdict": detached_verdict,
        "verifier_tool_identity": _detached_identity(verifier_tool_identity),
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
        payload_result=snapshot_runner_json(payload_result_path),
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
    release_path: Path | str,
    terminal_path: Path | str,
    cleanup_path: Path | str,
    detached_epoch_path: Path | str,
    output_path: Path | str,
) -> dict[str, object]:
    receipt = verify_detached(
        pre_run=snapshot_json(pre_run_path),
        selection=snapshot_json(selection_path),
        inner=snapshot_json(inner_path),
        preterminal=snapshot_json(preterminal_path),
        payload_result=snapshot_runner_json(payload_result_path),
        resource=snapshot_json(resource_path),
        release=snapshot_json(release_path),
        terminal=snapshot_json(terminal_path),
        cleanup=snapshot_json(cleanup_path),
        detached_epoch=snapshot_json(detached_epoch_path),
        verifier_tool_identity=current_tool_identity(),
    )
    write_exclusive(output_path, receipt)
    return receipt
