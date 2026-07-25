#!/usr/bin/env python3
"""No-overwrite evidence builders for one prospective AB16 organic arm.

This module defines the two-stage supervisor/payload/keeper evidence format
used by the *future* prospective AB16 campaign.  It does not import Gate-1-v4
tools, receipts, selections, or packages, and a valid document from this
module is not an authorization to launch an arm.

The live implementation is deliberately adapter-driven.  The supervisor and
observer remain ordinary-user processes; tests use inert adapters only.  A
future launcher must obtain a separately preregistered arm selection before
calling these builders.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import time
from typing import Any


PRE_RUN_AUTHORITY_SCHEMA = "noncert-cuts-ab16-organic-pre-run-authority-v1"
RUNNER_SELECTION_SCHEMA = "noncert-cuts-ab16-organic-arm-selection-v1"
DRILL_SELECTION_SCHEMA = "noncert-cuts-ab16-organic-drill-selection-v1"
EPOCH_OBSERVATION_SCHEMA = "noncert-cuts-ab16-manager-epoch-observation-v1"
INNER_SCHEMA = "noncert-cuts-ab16-inner-lifecycle-v1"
PRETERMINAL_SCHEMA = "noncert-cuts-ab16-preterminal-resource-v1"
RELEASE_SCHEMA = "noncert-cuts-ab16-release-token-v1"
TERMINAL_SCHEMA = "noncert-cuts-ab16-terminal-envelope-v1"
CLEANUP_SCHEMA = "noncert-cuts-ab16-cleanup-v1"

PURPOSE = "PROSPECTIVE_AB16_ORGANIC_ARM_RESOURCE_AUTHORITY"
PRE_RUN_PURPOSE = "PROSPECTIVE_AB16_ORGANIC_ARM_PRE_RUN_AUTHORITY"
RUNNER_SELECTION_PURPOSE = "prospective_noncert_cuts_ab16_formal_arm"
DRILL_SELECTION_PURPOSE = "noncert_cuts_ab16_disposable_live_drill"
EXECUTION_CLASSES = ("DISPOSABLE_LIVE_DRILL", "FORMAL_AB16")
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

CONFIGURATIONS = (
    "region-capacity",
    "shape-packing-hall",
    "power-hitting-set",
    "bundle",
)
ORDERS = ("ab", "ba")
ARMS = ("control", "treatment")
ARM_SEQUENCE = tuple(
    f"{configuration}-{order}-{arm}"
    for configuration in CONFIGURATIONS
    for order, ordered_arms in (
        ("ab", ("control", "treatment")),
        ("ba", ("treatment", "control")),
    )
    for arm in ordered_arms
)
PHASES = (
    "preselection",
    "launch",
    "preterminal",
    "release",
    "terminal",
    "cleanup",
    "detached-replay",
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

OUTPUT_ROLES = (
    "inner",
    "preterminal",
    "resource_verification",
    "release",
    "terminal",
    "cleanup",
    "detached_replay",
    "attempt_result",
)
TOOL_ROLES = (
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
)

SYSTEMD_PRETERMINAL_FIELDS = (
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
)
SYSTEMD_TERMINAL_FIELDS = (
    "ActiveState",
    "SubState",
    "ControlGroup",
    "InvocationID",
    "Result",
    "ExecMainCode",
    "ExecMainStatus",
)
CGROUP_FIELDS = (
    "memory.high",
    "memory.max",
    "memory.swap.max",
    "memory.current",
    "memory.peak",
    "memory.swap.current",
    "memory.events",
    "cgroup.procs",
    "cgroup.events",
)

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
INVOCATION_ID_RE = re.compile(r"[0-9a-f]{32}\Z")


class LifecycleError(RuntimeError):
    """Lifecycle input is malformed or violates the preregistered contract."""


@dataclass(frozen=True)
class DetachedDocument:
    """Bytes read once with their detached path/size/hash/mode identity."""

    path: Path
    raw: bytes
    identity: dict[str, object]


def _reject_constant(token: str) -> object:
    raise LifecycleError(f"invalid JSON constant: {token}")


def _pairs_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise LifecycleError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _check_json(value: object, label: str = "value") -> None:
    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise LifecycleError(f"{label} contains a non-finite float")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _check_json(item, f"{label}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise LifecycleError(f"{label} contains a non-string key")
            _check_json(item, f"{label}.{key}")
        return
    raise LifecycleError(f"{label} is not strict JSON data")


def canonical_json_bytes(value: object) -> bytes:
    """Encode canonical strict JSON without a trailing newline."""

    _check_json(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def strict_loads(raw: bytes, label: str = "document") -> object:
    """Parse canonical UTF-8 JSON and reject duplicate keys."""

    if type(raw) is not bytes or not raw:
        raise LifecycleError(f"{label} must be non-empty bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"{label} is malformed JSON") from exc
    if canonical_json_bytes(value) != raw:
        raise LifecycleError(f"{label} is not canonical JSON")
    return value


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise LifecycleError(f"{label} must be an exact object")
    return value


def _keys(
    value: object,
    expected: set[str],
    label: str,
) -> Mapping[str, Any]:
    record = _mapping(value, label)
    if set(record) != expected:
        raise LifecycleError(f"{label} must have the exact key set")
    return record


def _string(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise LifecycleError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise LifecycleError(f"{label} must be an integer >= {minimum}")
    return value


def _bool(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise LifecycleError(f"{label} must be an exact boolean")
    return value


def _identity(
    value: object,
    label: str,
    *,
    mode_required: bool = False,
) -> Mapping[str, Any]:
    required = {"path", "sha256", "size_bytes"}
    allowed = required | {"mode"}
    record = _mapping(value, label)
    if not required.issubset(record) or not set(record).issubset(allowed):
        raise LifecycleError(f"{label} has an invalid identity key set")
    if mode_required and "mode" not in record:
        raise LifecycleError(f"{label} must bind mode")
    path = _string(record["path"], f"{label}.path")
    if not Path(path).is_absolute():
        raise LifecycleError(f"{label}.path must be absolute")
    digest = _string(record["sha256"], f"{label}.sha256")
    if SHA256_RE.fullmatch(digest) is None:
        raise LifecycleError(f"{label}.sha256 is invalid")
    _integer(record["size_bytes"], f"{label}.size_bytes")
    if "mode" in record:
        mode = _integer(record["mode"], f"{label}.mode")
        if mode & ~0o7777:
            raise LifecycleError(f"{label}.mode is invalid")
    return record


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
        raise LifecycleError(f"{label} is missing manager/boot identity fields")
    _string(record["boot_id"], f"{label}.boot_id")
    _string(record["dbus_unique_owner"], f"{label}.dbus_unique_owner")
    _integer(record["manager_pid"], f"{label}.manager_pid", minimum=1)
    _integer(
        record["manager_pid_starttime"],
        f"{label}.manager_pid_starttime",
        minimum=1,
    )
    executable = _mapping(
        record["manager_executable"],
        f"{label}.manager_executable",
    )
    for key in ("path", "sha256", "size_bytes", "mode", "device", "inode"):
        if key not in executable:
            raise LifecycleError(f"{label}.manager_executable is missing {key}")
    _string(executable["path"], f"{label}.manager_executable.path")
    if not Path(executable["path"]).is_absolute():
        raise LifecycleError(f"{label}.manager_executable.path must be absolute")
    digest = _string(
        executable["sha256"],
        f"{label}.manager_executable.sha256",
    )
    if SHA256_RE.fullmatch(digest) is None:
        raise LifecycleError(f"{label}.manager_executable.sha256 is invalid")
    for key in ("size_bytes", "mode", "device", "inode"):
        _integer(executable[key], f"{label}.manager_executable.{key}")
    _string(record["manager_version"], f"{label}.manager_version")
    _string(record["manager_features"], f"{label}.manager_features")
    _check_json(record, label)
    return record


def epoch_digest(value: object) -> str:
    """Return the canonical digest of a validated manager/boot epoch."""

    epoch = _epoch(value, "manager epoch")
    return hashlib.sha256(canonical_json_bytes(epoch)).hexdigest()


def _open_parent_dirfd(path: Path) -> tuple[Path, int, str]:
    """Resolve every parent component through O_NOFOLLOW directory FDs."""

    absolute = Path(os.path.abspath(path))
    if absolute == Path(absolute.anchor):
        raise LifecycleError("file path may not be the filesystem root")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute.anchor, flags)
    except OSError as exc:
        raise LifecycleError("symlink or invalid path root") from exc
    try:
        for component in absolute.parts[1:-1]:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return absolute, descriptor, absolute.name
    except OSError as exc:
        os.close(descriptor)
        raise LifecycleError("symlink or invalid path component") from exc


def snapshot_regular(path: Path) -> DetachedDocument:
    """Read/hash one regular file through one O_NOFOLLOW descriptor."""

    absolute, parent_descriptor, leaf = _open_parent_dirfd(path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(leaf, flags, dir_fd=parent_descriptor)
    except OSError as exc:
        os.close(parent_descriptor)
        raise LifecycleError("symlink or invalid file path") from exc
    os.close(parent_descriptor)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise LifecycleError(f"not a regular file: {absolute}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        signature_before = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        signature_after = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if signature_before != signature_after:
            raise LifecycleError(f"file changed during same-FD read: {absolute}")
        raw = b"".join(chunks)
        if len(raw) != after.st_size:
            raise LifecycleError(f"short same-FD read: {absolute}")
        identity = {
            "mode": stat.S_IMODE(after.st_mode),
            "path": str(absolute),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
        return DetachedDocument(absolute, raw, identity)
    finally:
        os.close(descriptor)


def write_exclusive(path: Path, raw: bytes) -> dict[str, object]:
    """Create one immutable regular file with O_EXCL and no symlink traversal."""

    if type(raw) is not bytes:
        raise LifecycleError("exclusive payload must be bytes")
    absolute, parent_descriptor, leaf = _open_parent_dirfd(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(
            leaf,
            flags,
            0o444,
            dir_fd=parent_descriptor,
        )
    except OSError as exc:
        os.close(parent_descriptor)
        raise LifecycleError("symlink or invalid output path") from exc
    os.close(parent_descriptor)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise LifecycleError(f"short write: {absolute}")
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o444)
        metadata = os.fstat(descriptor)
        if metadata.st_size != len(raw):
            raise LifecycleError(f"wrong output size: {absolute}")
    finally:
        os.close(descriptor)
    return {
        "mode": 0o444,
        "path": str(absolute),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def write_json_exclusive(path: Path, value: object) -> dict[str, object]:
    """Write one canonical JSON document without overwriting."""

    return write_exclusive(path, canonical_json_bytes(value))


def _slot_parts(slot: str) -> tuple[str, str, str]:
    if slot not in ARM_SEQUENCE:
        raise LifecycleError("slot is not one of the 16 preregistered arms")
    for configuration in CONFIGURATIONS:
        prefix = f"{configuration}-"
        if slot.startswith(prefix):
            remainder = slot[len(prefix) :]
            order, arm = remainder.split("-", 1)
            return configuration, order, arm
    raise LifecycleError("unreachable arm slot")


def validate_resource_contract(
    value: object,
    *,
    execution_class: str,
) -> Mapping[str, Any]:
    """Validate the class-specific single-worker resource contract."""

    expected = RESOURCE_CONTRACTS.get(execution_class)
    if expected is None:
        raise LifecycleError("resource contract execution class is invalid")
    record = _keys(value, set(expected), "resource contract")
    for name in (
        "memory_high_bytes",
        "memory_max_bytes",
        "memory_swap_max_bytes",
        "runtime_max_seconds",
    ):
        _integer(record[name], f"resource contract {name}", minimum=1)
    for name in ("send_sigkill", "single_worker"):
        _bool(record[name], f"resource contract {name}")
    for name in ("collect_mode", "kill_mode", "oom_policy"):
        _string(record[name], f"resource contract {name}")
    if dict(record) != expected:
        raise LifecycleError("resource contract differs from the preregistration")
    return record


def validate_launch_environment(value: object) -> Mapping[str, str]:
    """Validate the exact ambient-free environment used by live children."""

    record = _keys(
        value,
        {"clear_ambient", "schema_version", "variables"},
        "launch environment",
    )
    if record["schema_version"] != LAUNCH_ENVIRONMENT_SCHEMA or record["clear_ambient"] is not True:
        raise LifecycleError("launch environment framing drifted")
    variables = _keys(
        record["variables"],
        LAUNCH_ENVIRONMENT_KEYS,
        "launch environment variables",
    )
    for name, item in variables.items():
        text = _string(item, f"launch environment {name}")
        if "\x00" in text or "\n" in text or "\r" in text:
            raise LifecycleError(f"launch environment {name} contains control bytes")
    for name in ("HOME", "XDG_RUNTIME_DIR"):
        if not Path(variables[name]).is_absolute():
            raise LifecycleError(f"launch environment {name} must be absolute")
    path_items = variables["PATH"].split(":")
    if not path_items or any(not Path(item).is_absolute() for item in path_items):
        raise LifecycleError("launch environment PATH must contain absolute entries")
    if (
        variables["LANG"] != "C.UTF-8"
        or variables["LC_ALL"] != "C.UTF-8"
        or variables["PYTHONHASHSEED"] != "0"
        or variables["TZ"] != "UTC"
        or not variables["DBUS_SESSION_BUS_ADDRESS"].startswith("unix:path=/")
    ):
        raise LifecycleError("launch environment fixed values drifted")
    return variables  # type: ignore[return-value]


def load_launch_environment(identity: object) -> dict[str, str]:
    """Same-FD replay one canonical pinned environment document."""

    expected = _identity(
        identity,
        "launch.environment_identity",
        mode_required=True,
    )
    snapshot = snapshot_regular(Path(expected["path"]))
    if {field: snapshot.identity[field] for field in expected} != expected:
        raise LifecycleError("launch environment byte identity drifted")
    value = strict_loads(snapshot.raw, "launch environment")
    return dict(validate_launch_environment(value))


def _expected_resource_verdict(pre_run: Mapping[str, Any]) -> str:
    expectation = pre_run["expected_payload_status"]["expectation"]
    if expectation == "SUCCESS":
        return RESOURCE_SUCCESS_VERDICT
    if expectation == "POST_SEAL_FAILURE":
        return RESOURCE_EXPECTED_FAILURE_VERDICT
    raise LifecycleError("unsupported payload expectation")


def validate_pre_run_authority(
    value: object,
    *,
    campaign_root: Mapping[str, Any] | None = None,
    manifest: Mapping[str, Any] | None = None,
    suite_selection: Mapping[str, Any] | None = None,
    expected_slot: str | None = None,
) -> Mapping[str, Any]:
    """Validate the non-authorizing authority frozen before arm selection."""

    expected = {
        "schema_version",
        "purpose",
        "campaign_id",
        "run_nonce",
        "repository_head",
        "repository_root",
        "repository_git_tool_identity",
        "execution_class",
        "expected_payload_status",
        "slot",
        "configuration",
        "order",
        "arm",
        "unit_name",
        "attempt_dir",
        "pre_run_authority_path",
        "runner_selection_path",
        "manager_epoch",
        "resource_contract",
        "package",
        "campaign_root_identity",
        "continuation_identity",
        "prospective_manifest_identity",
        "suite_selection_identity",
        "baseline_admission_identity",
        "common_prestate_identity",
        "arm_binding_identity",
        "baseline_incumbent_sha256",
        "authority_chain",
        "strict_input_identities",
        "seed",
        "workers",
        "preselection_epoch_identity",
        "preselection_transcript_identity",
        "tool_identities",
        "output_paths",
        "epoch_observation_paths",
        "epoch_transcript_paths",
        "launch",
        "prelaunch_allowlist",
        "preflight_results",
        "status",
        "verdict",
        "arm_launch_authorized",
        "solver_run_authorized",
        "arm_selection_write_authorized",
    }
    record = _keys(value, expected, "pre-run authority")
    if (
        record["schema_version"] != PRE_RUN_AUTHORITY_SCHEMA
        or record["purpose"] != PRE_RUN_PURPOSE
        or record["status"] != "PASS"
        or record["verdict"] != "AB16_ORGANIC_PRE_RUN_AUTHORITY_PASS"
    ):
        raise LifecycleError("pre-run authority schema/purpose mismatch")
    if (
        _bool(record["arm_launch_authorized"], "arm_launch_authorized") is not False
        or _bool(record["solver_run_authorized"], "solver_run_authorized") is not False
        or _bool(
            record["arm_selection_write_authorized"],
            "arm_selection_write_authorized",
        )
        is not True
    ):
        raise LifecycleError("pre-run authority may not authorize an arm or solver")
    slot = _string(record["slot"], "slot")
    configuration, order, arm = _slot_parts(slot)
    if record["configuration"] != configuration or record["order"] != order or record["arm"] != arm:
        raise LifecycleError("arm selection slot metadata mismatch")
    _string(record["campaign_id"], "campaign_id")
    _string(record["run_nonce"], "run_nonce")
    repository_head = _string(record["repository_head"], "repository_head")
    if re.fullmatch(r"[0-9a-f]{40}", repository_head) is None:
        raise LifecycleError("repository_head is invalid")
    repository_root = Path(_string(record["repository_root"], "repository_root"))
    if not repository_root.is_absolute():
        raise LifecycleError("repository_root must be absolute")
    _identity(
        record["repository_git_tool_identity"],
        "repository_git_tool_identity",
        mode_required=True,
    )
    if record["execution_class"] not in EXECUTION_CLASSES:
        raise LifecycleError("pre-run execution_class is invalid")
    expected_payload = _keys(
        record["expected_payload_status"],
        {"exit_code", "expectation", "signal"},
        "expected payload status",
    )
    exit_code = _integer(expected_payload["exit_code"], "expected exit_code")
    signal_number = _integer(expected_payload["signal"], "expected signal")
    if expected_payload["expectation"] == "SUCCESS":
        if exit_code != 0 or signal_number != 0:
            raise LifecycleError("successful payload expectation drifted")
    elif expected_payload["expectation"] == "POST_SEAL_FAILURE":
        if (exit_code == 0) == (signal_number == 0):
            raise LifecycleError("post-SEAL failure must fix exactly one failure mode")
    else:
        raise LifecycleError("payload expectation is invalid")
    unit_name = _string(record["unit_name"], "unit_name")
    if not unit_name.endswith(".service") or "/" in unit_name:
        raise LifecycleError("unit_name must be one concrete .service name")
    attempt_dir = Path(_string(record["attempt_dir"], "attempt_dir"))
    selection_path = Path(_string(record["runner_selection_path"], "runner_selection_path"))
    pre_run_path = Path(_string(record["pre_run_authority_path"], "pre_run_authority_path"))
    if not attempt_dir.is_absolute() or not selection_path.is_absolute():
        raise LifecycleError("attempt/selection paths must be absolute")
    if selection_path != attempt_dir / "selection.json":
        raise LifecycleError("runner_selection_path is not preregistered under attempt_dir")
    if pre_run_path != attempt_dir / "pre-run-authority.json":
        raise LifecycleError("pre_run_authority_path is not preregistered under attempt_dir")
    _epoch(record["manager_epoch"], "selection manager_epoch")
    validate_resource_contract(
        record["resource_contract"],
        execution_class=record["execution_class"],
    )
    for key in (
        "campaign_root_identity",
        "continuation_identity",
        "prospective_manifest_identity",
        "suite_selection_identity",
        "baseline_admission_identity",
        "common_prestate_identity",
        "arm_binding_identity",
        "preselection_epoch_identity",
        "preselection_transcript_identity",
    ):
        _identity(record[key], key)
    package = _keys(
        record["package"],
        {"manifest_identity", "package_id", "seal_identity"},
        "package",
    )
    _identity(package["manifest_identity"], "package.manifest_identity")
    seal = _identity(package["seal_identity"], "package.seal_identity")
    if (
        type(package["package_id"]) is not str
        or SHA256_RE.fullmatch(package["package_id"]) is None
        or package["package_id"] != seal["sha256"]
    ):
        raise LifecycleError("package identity is invalid")
    digest = _string(record["baseline_incumbent_sha256"], "baseline_incumbent_sha256")
    if SHA256_RE.fullmatch(digest) is None:
        raise LifecycleError("baseline_incumbent_sha256 is invalid")
    if type(record["authority_chain"]) is not dict:
        raise LifecycleError("authority_chain must be an exact object")
    _check_json(record["authority_chain"], "authority_chain")
    _integer(record["seed"], "seed")
    if _integer(record["workers"], "workers", minimum=1) != 1:
        raise LifecycleError("workers must be exactly one")
    tools = _keys(record["tool_identities"], set(TOOL_ROLES), "tool identities")
    for role in TOOL_ROLES:
        _identity(tools[role], f"tool identity {role}", mode_required=True)
    strict_inputs = _mapping(record["strict_input_identities"], "strict inputs")
    if not strict_inputs:
        raise LifecycleError("strict input identity map must be non-empty")
    for role, identity in strict_inputs.items():
        _string(role, "strict input role")
        _identity(identity, f"strict input {role}", mode_required=True)
    outputs = _keys(record["output_paths"], set(OUTPUT_ROLES), "output paths")
    resolved_outputs: set[Path] = set()
    for role in OUTPUT_ROLES:
        output = Path(_string(outputs[role], f"output path {role}"))
        if not output.is_absolute() or output.parent != attempt_dir:
            raise LifecycleError(f"output path {role} is outside attempt_dir")
        if output in resolved_outputs or output in {selection_path, pre_run_path}:
            raise LifecycleError("selection/output paths must be distinct")
        resolved_outputs.add(output)
    epoch_paths = _keys(
        record["epoch_observation_paths"],
        set(PHASES) - {"preselection"},
        "epoch observation paths",
    )
    for phase, raw_path in epoch_paths.items():
        output = Path(_string(raw_path, f"epoch observation path {phase}"))
        if not output.is_absolute() or output.parent != attempt_dir:
            raise LifecycleError(f"epoch observation path {phase} is outside attempt_dir")
        if output in resolved_outputs or output in {selection_path, pre_run_path}:
            raise LifecycleError("epoch observation/output paths must be distinct")
        resolved_outputs.add(output)
    transcript_paths = _keys(
        record["epoch_transcript_paths"],
        set(PHASES) - {"preselection"},
        "epoch transcript paths",
    )
    for phase, raw_path in transcript_paths.items():
        output = Path(_string(raw_path, f"epoch transcript path {phase}"))
        if not output.is_absolute() or output.parent != attempt_dir:
            raise LifecycleError(f"epoch transcript path {phase} is outside attempt_dir")
        if output in resolved_outputs or output in {selection_path, pre_run_path}:
            raise LifecycleError("epoch transcript/output paths must be distinct")
        resolved_outputs.add(output)
    launch = _keys(
        record["launch"],
        {
            "cwd",
            "environment_identity",
            "payload_argv",
            "supervisor_argv",
            "python3_13_path",
            "systemctl_path",
            "systemd_run_path",
        },
        "launch",
    )
    cwd = Path(_string(launch["cwd"], "launch.cwd"))
    if not cwd.is_absolute():
        raise LifecycleError("launch.cwd must be absolute")
    load_launch_environment(launch["environment_identity"])
    systemd_run_path = Path(_string(launch["systemd_run_path"], "launch.systemd_run_path"))
    if not systemd_run_path.is_absolute():
        raise LifecycleError("launch.systemd_run_path must be absolute")
    if systemd_run_path != Path(tools["systemd_run"]["path"]):
        raise LifecycleError("launch.systemd_run_path differs from pinned tool")
    systemctl_path = Path(_string(launch["systemctl_path"], "launch.systemctl_path"))
    if systemctl_path != Path(tools["systemctl"]["path"]):
        raise LifecycleError("launch.systemctl_path differs from pinned tool")
    python_path = Path(_string(launch["python3_13_path"], "launch.python3_13_path"))
    if python_path != Path(tools["python3_13"]["path"]):
        raise LifecycleError("launch.python3_13_path differs from pinned tool")
    for name in ("payload_argv", "supervisor_argv"):
        argv = launch[name]
        if type(argv) is not list or len(argv) < 3:
            raise LifecycleError(f"launch.{name} must contain executable and script")
        for index, argument in enumerate(argv):
            _string(argument, f"launch.{name}[{index}]")
        if argv[0] != str(python_path):
            raise LifecycleError(f"launch.{name}[0] differs from pinned Python")
        if argv[1] != "-I":
            raise LifecycleError(f"launch.{name} does not isolate Python")
    if (
        len(launch["supervisor_argv"]) < 4
        or launch["supervisor_argv"][2] != tools["organic_resource_lifecycle"]["path"]
    ):
        raise LifecycleError("supervisor argv does not invoke pinned lifecycle tool")
    if record["execution_class"] == "FORMAL_AB16":
        if len(launch["payload_argv"]) < 3 or launch["payload_argv"][2] != tools["organic_arm_runner"]["path"]:
            raise LifecycleError("formal payload argv does not invoke pinned arm runner")
    elif launch["payload_argv"][2] not in {identity["path"] for identity in strict_inputs.values()}:
        raise LifecycleError("drill payload is not a package/test-pinned strict input")
    if record["prelaunch_allowlist"] != [
        "pre-run-authority.json",
        "selection.json",
    ]:
        raise LifecycleError("prelaunch attempt-directory allowlist drifted")
    preflight = _keys(
        record["preflight_results"],
        {
            "epoch_identity_pass",
            "head_identity_pass",
            "package_replay_pass",
            "path_preregistration_pass",
            "resource_contract_pass",
            "slot_order_pass",
            "strict_inputs_replay_pass",
            "tool_identities_replay_pass",
        },
        "preflight results",
    )
    if any(type(item) is not bool or item is not True for item in preflight.values()):
        raise LifecycleError("pre-run preflight did not pass every mandatory gate")
    if expected_slot is not None and record["slot"] != expected_slot:
        raise LifecycleError("pre-run expected slot differs")
    if campaign_root is not None:
        for field in (
            "campaign_id",
            "run_nonce",
            "repository_head",
            "repository_root",
            "repository_git_tool_identity",
            "manager_epoch",
            "package",
        ):
            if record[field] != campaign_root.get(field):
                raise LifecycleError(f"pre-run campaign root {field} join failed")
        root_strict = campaign_root.get("strict_input_identities")
        if root_strict is not None and record["strict_input_identities"] != root_strict:
            raise LifecycleError("pre-run campaign strict input map differs")
    if manifest is not None:
        sequence = manifest.get("arm_sequence")
        attempts = manifest.get("attempt_dirs")
        units = manifest.get("unit_names")
        if (
            type(sequence) is not list
            or type(attempts) is not dict
            or type(units) is not dict
            or record["slot"] not in sequence
            or attempts.get(record["slot"]) != record["attempt_dir"]
            or units.get(record["slot"]) != record["unit_name"]
            or manifest.get("campaign_id") != record["campaign_id"]
            or manifest.get("run_nonce") != record["run_nonce"]
            or manifest.get("repository_head") != record["repository_head"]
            or manifest.get("repository_root") != record["repository_root"]
            or manifest.get("repository_git_tool_identity") != record["repository_git_tool_identity"]
            or manifest.get("authority_chain") != record["authority_chain"]
        ):
            raise LifecycleError("pre-run organic manifest join failed")
        bindings = manifest.get("arm_binding_identities")
        if type(bindings) is not dict or bindings.get(record["slot"]) != record["arm_binding_identity"]:
            raise LifecycleError("pre-run arm-binding manifest join failed")
    if suite_selection is not None and (
        suite_selection.get("arm_launch_authorized") is not False
        or suite_selection.get("run_nonce") != record["run_nonce"]
        or suite_selection.get("package_id") != record["package"]["package_id"]
    ):
        raise LifecycleError("pre-run suite selection join failed")
    return record


def validate_runner_selection(
    value: object,
    *,
    pre_run_authority: Mapping[str, Any],
    pre_run_authority_identity: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Validate the runner's exact selection schema against pre-run bytes."""

    pre_run = validate_pre_run_authority(pre_run_authority)
    expected = {
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
        "fresh_process_required",
        "manifest_identity",
        "order",
        "pre_run_authority_identity",
        "purpose",
        "repository_head",
        "repository_root",
        "repository_git_tool_identity",
        "execution_class",
        "expected_payload_status",
        "run_nonce",
        "schema_version",
        "seed",
        "selection_nonce",
        "slot",
        "unit_name",
        "workers",
    }
    record = _keys(value, expected, "runner selection")
    formal = (
        record["schema_version"] == RUNNER_SELECTION_SCHEMA
        and record["purpose"] == RUNNER_SELECTION_PURPOSE
        and record["execution_class"] == "FORMAL_AB16"
    )
    drill = (
        record["schema_version"] == DRILL_SELECTION_SCHEMA
        and record["purpose"] == DRILL_SELECTION_PURPOSE
        and record["execution_class"] == "DISPOSABLE_LIVE_DRILL"
    )
    if (not formal and not drill) or record["fresh_process_required"] is not True:
        raise LifecycleError("runner selection schema/purpose drifted")
    for field in (
        "arm",
        "arm_binding_identity",
        "attempt_dir",
        "authority_chain",
        "baseline_admission_identity",
        "baseline_incumbent_sha256",
        "campaign_id",
        "common_prestate_identity",
        "configuration",
        "order",
        "repository_head",
        "repository_root",
        "repository_git_tool_identity",
        "execution_class",
        "expected_payload_status",
        "run_nonce",
        "seed",
        "slot",
        "unit_name",
        "workers",
    ):
        pre_field = "prospective_manifest_identity" if field == "manifest_identity" else field
        if record[field] != pre_run[pre_field]:
            raise LifecycleError(f"runner selection {field} differs from pre-run authority")
    if record["manifest_identity"] != pre_run["prospective_manifest_identity"]:
        raise LifecycleError("runner selection manifest identity differs from pre-run")
    selected_pre_run_identity = _identity(
        record["pre_run_authority_identity"],
        "runner selection pre-run authority identity",
    )
    observed_pre_run_identity = _identity(
        pre_run_authority_identity,
        "pre-run authority identity",
    )
    if {field: observed_pre_run_identity[field] for field in selected_pre_run_identity} != selected_pre_run_identity:
        raise LifecycleError("runner selection pre-run authority identity differs")
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
        }[str(record["configuration"])]
    )
    if record["enabled_families"] != expected_families:
        raise LifecycleError("runner selection enabled families drifted")
    if (
        type(record["selection_nonce"]) is not str
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", record["selection_nonce"]) is None
    ):
        raise LifecycleError("runner selection nonce is invalid")
    expected_authorizations = {
        "global_claim_authorized": False,
        "mathematical_claim_authorized": False,
        "organic_arm_launch_authorized": formal,
        "production_certified_authorized": False,
        "solver_run_authorized": formal,
    }
    if record["authorizations"] != expected_authorizations:
        raise LifecycleError("runner selection authorization boundary drifted")
    return record


def build_epoch_observation(
    *,
    phase: str,
    slot: str,
    observed_epoch: Mapping[str, Any],
    observed_at_monotonic_ns: int,
    capture_transcript_identity: Mapping[str, Any],
) -> dict[str, object]:
    """Build one independently observed live manager/boot checkpoint."""

    if phase not in PHASES:
        raise LifecycleError("unsupported lifecycle phase")
    _slot_parts(slot)
    epoch = dict(_epoch(observed_epoch, "observed manager epoch"))
    return {
        "observed_at_monotonic_ns": _integer(
            observed_at_monotonic_ns,
            "observed_at_monotonic_ns",
            minimum=1,
        ),
        "observed_epoch": epoch,
        "observed_epoch_digest": epoch_digest(epoch),
        "capture_transcript_identity": dict(
            _identity(
                capture_transcript_identity,
                "capture_transcript_identity",
                mode_required=True,
            )
        ),
        "phase": phase,
        "schema_version": EPOCH_OBSERVATION_SCHEMA,
        "slot": slot,
    }


def _join(
    pre_run_authority: Mapping[str, Any],
    pre_run_authority_identity: Mapping[str, Any],
    runner_selection: Mapping[str, Any],
    runner_selection_identity: Mapping[str, Any],
    *,
    invocation_id: str,
    observation: Mapping[str, Any],
) -> dict[str, object]:
    pre_run = validate_pre_run_authority(pre_run_authority)
    selected = validate_runner_selection(
        runner_selection,
        pre_run_authority=pre_run,
        pre_run_authority_identity=pre_run_authority_identity,
    )
    pre_run_identity = dict(_identity(pre_run_authority_identity, "pre-run authority identity"))
    selection_identity = dict(_identity(runner_selection_identity, "runner selection identity"))
    observed = _keys(
        observation,
        {
            "capture_transcript_identity",
            "observed_at_monotonic_ns",
            "observed_epoch",
            "observed_epoch_digest",
            "phase",
            "schema_version",
            "slot",
        },
        "epoch observation",
    )
    if (
        observed["schema_version"] != EPOCH_OBSERVATION_SCHEMA
        or observed["slot"] != selected["slot"]
        or observed["observed_epoch_digest"] != epoch_digest(observed["observed_epoch"])
    ):
        raise LifecycleError("epoch observation join mismatch")
    _identity(
        observed["capture_transcript_identity"],
        "epoch capture transcript identity",
        mode_required=True,
    )
    if observed["observed_epoch"] != pre_run["manager_epoch"]:
        raise LifecycleError("live manager/boot epoch drift")
    return {
        "campaign_id": selected["campaign_id"],
        "invocation_id": _string(invocation_id, "invocation_id"),
        "manager_epoch_observation": dict(observed),
        "pre_run_authority_identity": pre_run_identity,
        "run_nonce": selected["run_nonce"],
        "runner_selection_identity": selection_identity,
        "slot": selected["slot"],
        "unit_name": selected["unit_name"],
    }


def build_inner_record(
    pre_run_authority: Mapping[str, Any],
    pre_run_authority_identity: Mapping[str, Any],
    runner_selection: Mapping[str, Any],
    runner_selection_identity: Mapping[str, Any],
    *,
    invocation_id: str,
    launch_observation: Mapping[str, Any],
    supervisor_pid: int,
    supervisor_starttime: int,
    payload_pid: int,
    payload_starttime: int,
    payload_seal_monotonic_ns: int,
    payload_exit_monotonic_ns: int,
    payload_exit_code: int,
    payload_signal: int,
    payload_reaped: bool,
    payload_result_identity: Mapping[str, Any],
    keeper_ready_monotonic_ns: int,
) -> dict[str, object]:
    """Build the inner raw chain after the payload has exited and been reaped."""

    join = _join(
        pre_run_authority,
        pre_run_authority_identity,
        runner_selection,
        runner_selection_identity,
        invocation_id=invocation_id,
        observation=launch_observation,
    )
    if launch_observation["phase"] != "launch":
        raise LifecycleError("inner record requires the launch epoch observation")
    supervisor = _integer(supervisor_pid, "supervisor_pid", minimum=1)
    supervisor_start = _integer(
        supervisor_starttime,
        "supervisor_starttime",
        minimum=1,
    )
    payload = _integer(payload_pid, "payload_pid", minimum=1)
    payload_start = _integer(payload_starttime, "payload_starttime", minimum=1)
    seal = _integer(payload_seal_monotonic_ns, "payload seal", minimum=1)
    exited = _integer(payload_exit_monotonic_ns, "payload exit", minimum=1)
    keeper_ready = _integer(
        keeper_ready_monotonic_ns,
        "keeper ready",
        minimum=1,
    )
    if not seal <= exited <= keeper_ready:
        raise LifecycleError("inner payload/keeper time order is invalid")
    if supervisor == payload and supervisor_start == payload_start:
        raise LifecycleError("payload must be distinct from supervisor/keeper")
    if type(payload_exit_code) is not int or type(payload_signal) is not int:
        raise LifecycleError("payload exit status fields must be exact integers")
    return {
        **join,
        "keeper_pid": supervisor,
        "keeper_ready_monotonic_ns": keeper_ready,
        "keeper_starttime": supervisor_start,
        "payload_exit_code": payload_exit_code,
        "payload_exit_monotonic_ns": exited,
        "payload_pid": payload,
        "payload_reaped": _bool(payload_reaped, "payload_reaped"),
        "payload_result_identity": dict(_identity(payload_result_identity, "payload result identity")),
        "payload_seal_monotonic_ns": seal,
        "payload_signal": payload_signal,
        "payload_starttime": payload_start,
        "purpose": PURPOSE,
        "schema_version": INNER_SCHEMA,
        "supervisor_pid": supervisor,
        "supervisor_starttime": supervisor_start,
    }


def _raw_string_mapping(
    value: object,
    expected: Sequence[str],
    label: str,
) -> dict[str, str]:
    record = _keys(value, set(expected), label)
    result: dict[str, str] = {}
    for key in expected:
        item = record[key]
        if type(item) is not str:
            raise LifecycleError(f"{label}.{key} must be an exact string")
        result[key] = item
    return result


def build_preterminal_record(
    pre_run_authority: Mapping[str, Any],
    pre_run_authority_identity: Mapping[str, Any],
    runner_selection: Mapping[str, Any],
    runner_selection_identity: Mapping[str, Any],
    inner_identity: Mapping[str, Any],
    *,
    invocation_id: str,
    preterminal_observation: Mapping[str, Any],
    observed_at_monotonic_ns: int,
    systemd_raw: Mapping[str, str],
    cgroup_raw: Mapping[str, str],
    payload_current_starttime: int | None,
    keeper_current_starttime: int,
) -> dict[str, object]:
    """Freeze raw systemd/cgroup state while the keeper holds the cgroup."""

    join = _join(
        pre_run_authority,
        pre_run_authority_identity,
        runner_selection,
        runner_selection_identity,
        invocation_id=invocation_id,
        observation=preterminal_observation,
    )
    if preterminal_observation["phase"] != "preterminal":
        raise LifecycleError("preterminal record requires preterminal observation")
    if payload_current_starttime is not None:
        _integer(
            payload_current_starttime,
            "payload_current_starttime",
            minimum=1,
        )
    return {
        **join,
        "captured_at_monotonic_ns": _integer(
            observed_at_monotonic_ns,
            "captured_at_monotonic_ns",
            minimum=1,
        ),
        "cgroup_raw": _raw_string_mapping(
            cgroup_raw,
            CGROUP_FIELDS,
            "cgroup_raw",
        ),
        "inner_identity": dict(_identity(inner_identity, "inner identity")),
        "keeper_current_starttime": _integer(
            keeper_current_starttime,
            "keeper_current_starttime",
            minimum=1,
        ),
        "payload_current_starttime": payload_current_starttime,
        "purpose": PURPOSE,
        "schema_version": PRETERMINAL_SCHEMA,
        "systemd_raw": _raw_string_mapping(
            systemd_raw,
            SYSTEMD_PRETERMINAL_FIELDS,
            "systemd_raw",
        ),
    }


def build_release_record(
    pre_run_authority: Mapping[str, Any],
    pre_run_authority_identity: Mapping[str, Any],
    runner_selection: Mapping[str, Any],
    runner_selection_identity: Mapping[str, Any],
    *,
    invocation_id: str,
    release_observation: Mapping[str, Any],
    preterminal_identity: Mapping[str, Any],
    resource_verification_identity: Mapping[str, Any],
    keeper_pid: int,
    keeper_starttime: int,
    release_monotonic_ns: int,
) -> dict[str, object]:
    """Authorize release only after an independent preterminal PASS receipt."""

    join = _join(
        pre_run_authority,
        pre_run_authority_identity,
        runner_selection,
        runner_selection_identity,
        invocation_id=invocation_id,
        observation=release_observation,
    )
    if release_observation["phase"] != "release":
        raise LifecycleError("release record requires release observation")
    return {
        **join,
        "keeper_pid": _integer(keeper_pid, "keeper_pid", minimum=1),
        "keeper_starttime": _integer(
            keeper_starttime,
            "keeper_starttime",
            minimum=1,
        ),
        "preterminal_identity": dict(_identity(preterminal_identity, "preterminal identity")),
        "purpose": PURPOSE,
        "release_monotonic_ns": _integer(
            release_monotonic_ns,
            "release_monotonic_ns",
            minimum=1,
        ),
        "resource_verification_identity": dict(
            _identity(
                resource_verification_identity,
                "resource verification identity",
            )
        ),
        "schema_version": RELEASE_SCHEMA,
        "verdict": _expected_resource_verdict(validate_pre_run_authority(pre_run_authority)),
    }


def build_terminal_record(
    pre_run_authority: Mapping[str, Any],
    pre_run_authority_identity: Mapping[str, Any],
    runner_selection: Mapping[str, Any],
    runner_selection_identity: Mapping[str, Any],
    release_identity: Mapping[str, Any],
    *,
    invocation_id: str,
    terminal_observation: Mapping[str, Any],
    captured_at_monotonic_ns: int,
    systemd_raw: Mapping[str, str],
) -> dict[str, object]:
    """Freeze the same unit's terminal metadata after keeper release."""

    join = _join(
        pre_run_authority,
        pre_run_authority_identity,
        runner_selection,
        runner_selection_identity,
        invocation_id=invocation_id,
        observation=terminal_observation,
    )
    if terminal_observation["phase"] != "terminal":
        raise LifecycleError("terminal record requires terminal observation")
    return {
        **join,
        "captured_at_monotonic_ns": _integer(
            captured_at_monotonic_ns,
            "captured_at_monotonic_ns",
            minimum=1,
        ),
        "purpose": PURPOSE,
        "release_identity": dict(_identity(release_identity, "release identity")),
        "schema_version": TERMINAL_SCHEMA,
        "systemd_raw": _raw_string_mapping(
            systemd_raw,
            SYSTEMD_TERMINAL_FIELDS,
            "systemd_raw",
        ),
    }


def build_cleanup_record(
    pre_run_authority: Mapping[str, Any],
    pre_run_authority_identity: Mapping[str, Any],
    runner_selection: Mapping[str, Any],
    runner_selection_identity: Mapping[str, Any],
    terminal_identity: Mapping[str, Any],
    *,
    invocation_id: str,
    cleanup_observation: Mapping[str, Any],
    captured_at_monotonic_ns: int,
    payload_pid: int,
    payload_current_starttime: int | None,
    keeper_pid: int,
    keeper_current_starttime: int | None,
    cgroup_path: str,
    cgroup_path_exists: bool,
    unit_load_state: str,
    matching_unit_names: Sequence[str],
) -> dict[str, object]:
    """Freeze independent cleanup evidence; terminal defaults are not proof."""

    join = _join(
        pre_run_authority,
        pre_run_authority_identity,
        runner_selection,
        runner_selection_identity,
        invocation_id=invocation_id,
        observation=cleanup_observation,
    )
    if cleanup_observation["phase"] != "cleanup":
        raise LifecycleError("cleanup record requires cleanup observation")
    for label, value in (
        ("payload_current_starttime", payload_current_starttime),
        ("keeper_current_starttime", keeper_current_starttime),
    ):
        if value is not None:
            _integer(value, label, minimum=1)
    if type(matching_unit_names) not in {list, tuple}:
        raise LifecycleError("matching_unit_names must be a sequence")
    names = [_string(name, "matching unit name") for name in matching_unit_names]
    return {
        **join,
        "captured_at_monotonic_ns": _integer(
            captured_at_monotonic_ns,
            "captured_at_monotonic_ns",
            minimum=1,
        ),
        "cgroup_path": _string(cgroup_path, "cgroup_path"),
        "cgroup_path_exists": _bool(cgroup_path_exists, "cgroup_path_exists"),
        "keeper_current_starttime": keeper_current_starttime,
        "keeper_pid": _integer(keeper_pid, "keeper_pid", minimum=1),
        "matching_unit_names": names,
        "payload_current_starttime": payload_current_starttime,
        "payload_pid": _integer(payload_pid, "payload_pid", minimum=1),
        "purpose": PURPOSE,
        "schema_version": CLEANUP_SCHEMA,
        "terminal_identity": dict(_identity(terminal_identity, "terminal identity")),
        "unit_load_state": _string(unit_load_state, "unit_load_state"),
    }


def build_systemd_run_argv(
    *,
    systemd_run_path: str,
    unit_name: str,
    supervisor_argv: Sequence[str],
    resource_contract: Mapping[str, Any],
    execution_class: str,
) -> list[str]:
    """Build, but never execute, the exact future single-worker unit argv."""

    executable = _string(systemd_run_path, "systemd_run_path")
    if not Path(executable).is_absolute():
        raise LifecycleError("systemd_run_path must be absolute")
    unit = _string(unit_name, "unit_name")
    if not unit.endswith(".service") or "/" in unit:
        raise LifecycleError("unit_name must be one concrete .service name")
    if type(supervisor_argv) not in {list, tuple} or not supervisor_argv:
        raise LifecycleError("supervisor_argv must be non-empty")
    command = [_string(item, "supervisor argv item") for item in supervisor_argv]
    contract = validate_resource_contract(
        resource_contract,
        execution_class=execution_class,
    )
    return [
        executable,
        "--user",
        "--quiet",
        f"--unit={unit.removesuffix('.service')}",
        f"--property=MemoryHigh={contract['memory_high_bytes']}",
        f"--property=MemoryMax={contract['memory_max_bytes']}",
        f"--property=MemorySwapMax={contract['memory_swap_max_bytes']}",
        f"--property=CollectMode={contract['collect_mode']}",
        f"--property=OOMPolicy={contract['oom_policy']}",
        f"--property=KillMode={contract['kill_mode']}",
        "--property=SendSIGKILL=yes",
        f"--property=RuntimeMaxSec={contract['runtime_max_seconds']}",
        "--",
        *command,
    ]


def _proc_starttime(pid: int) -> int | None:
    """Read one exact pid starttime, returning None after process exit."""

    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    except (FileNotFoundError, ProcessLookupError):
        return None
    close = raw.rfind(")")
    if close < 0:
        raise LifecycleError("malformed proc stat comm field")
    fields = raw[close + 2 :].split()
    if len(fields) <= 19:
        raise LifecycleError("truncated proc stat")
    try:
        return int(fields[19])
    except ValueError as exc:
        raise LifecycleError("invalid proc starttime") from exc


def _wait_without_reaping(
    pid: int,
    *,
    timeout_seconds: float,
    monotonic: Callable[[], float],
    sleep: Callable[[float], None],
) -> os.waitid_result | None:
    deadline = monotonic() + timeout_seconds
    options = os.WEXITED | os.WNOWAIT | os.WNOHANG
    while monotonic() <= deadline:
        status = os.waitid(os.P_PID, pid, options)
        if status is not None:
            return status
        sleep(0.05)
    return None


def _terminate_exact_child(process: subprocess.Popen[bytes]) -> None:
    try:
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _returncode_from_waitid(status: os.waitid_result) -> int:
    if status.si_code == os.CLD_EXITED:
        return int(status.si_status)
    if status.si_code in {os.CLD_KILLED, os.CLD_DUMPED}:
        return -int(status.si_status)
    raise LifecycleError(f"unsupported waitid si_code: {status.si_code}")


def _load_json_snapshot(path: Path, label: str) -> tuple[Mapping[str, Any], DetachedDocument]:
    snapshot = snapshot_regular(path)
    value = strict_loads(snapshot.raw, label)
    if type(value) is not dict:
        raise LifecycleError(f"{label} must be an exact object")
    return value, snapshot


def _validate_keeper_release(
    value: object,
    *,
    pre_run: Mapping[str, Any],
    pre_run_identity: Mapping[str, Any],
    selection_identity: Mapping[str, Any],
    inner_identity: Mapping[str, Any],
    invocation_id: str,
    keeper_pid: int,
    keeper_starttime: int,
) -> None:
    record = _mapping(value, "keeper release")
    if (
        record.get("schema_version") != RELEASE_SCHEMA
        or record.get("verdict") != _expected_resource_verdict(pre_run)
        or record.get("campaign_id") != pre_run["campaign_id"]
        or record.get("run_nonce") != pre_run["run_nonce"]
        or record.get("slot") != pre_run["slot"]
        or record.get("unit_name") != pre_run["unit_name"]
        or record.get("invocation_id") != invocation_id
        or record.get("pre_run_authority_identity") != pre_run_identity
        or record.get("runner_selection_identity") != selection_identity
        or record.get("keeper_pid") != keeper_pid
        or record.get("keeper_starttime") != keeper_starttime
    ):
        raise LifecycleError("keeper release token does not join selected unit")
    resource_identity = _identity(
        record.get("resource_verification_identity"),
        "release resource verification",
    )
    resource, resource_snapshot = _load_json_snapshot(
        Path(resource_identity["path"]),
        "resource verification",
    )
    if {field: resource_snapshot.identity[field] for field in resource_identity} != resource_identity:
        raise LifecycleError("release resource-verification identity drifted")
    if (
        resource.get("schema_version") != "noncert-cuts-ab16-resource-verification-v1"
        or resource.get("status") != "PASS"
        or resource.get("verdict") != _expected_resource_verdict(pre_run)
        or resource.get("inner_identity") != inner_identity
    ):
        raise LifecycleError("keeper release lacks independent resource PASS")


def supervise_payload(
    *,
    pre_run_path: Path | str,
    selection_path: Path | str,
    popen: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
    monotonic: Callable[[], float] = time.monotonic,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
    sleep: Callable[[float], None] = time.sleep,
    proc_starttime: Callable[[int], int | None] = _proc_starttime,
    wait_without_reaping: Callable[..., os.waitid_result | None] = (_wait_without_reaping),
) -> int:
    """Run/reap the selected payload, remain keeper, then mirror its status."""

    pre_run, pre_run_snapshot = _load_json_snapshot(
        Path(pre_run_path),
        "pre-run authority",
    )
    selection, selection_snapshot = _load_json_snapshot(
        Path(selection_path),
        "runner selection",
    )
    validate_pre_run_authority(pre_run)
    validate_runner_selection(
        selection,
        pre_run_authority=pre_run,
        pre_run_authority_identity=pre_run_snapshot.identity,
    )
    invocation_id = os.environ.get("INVOCATION_ID", "")
    if INVOCATION_ID_RE.fullmatch(invocation_id) is None:
        raise LifecycleError("supervisor InvocationID is missing or invalid")
    pinned_environment = load_launch_environment(pre_run["launch"]["environment_identity"])
    resource_contract = validate_resource_contract(
        pre_run["resource_contract"],
        execution_class=pre_run["execution_class"],
    )
    if os.geteuid() != os.getuid() or os.geteuid() == 0:
        raise LifecycleError("supervisor must run as the ordinary selected user")
    launch_observation, _launch_snapshot = _load_json_snapshot(
        Path(pre_run["epoch_observation_paths"]["launch"]),
        "launch manager epoch",
    )
    supervisor_pid = os.getpid()
    supervisor_starttime = proc_starttime(supervisor_pid)
    if supervisor_starttime is None:
        raise LifecycleError("cannot establish supervisor starttime")
    started = monotonic()
    process = popen(
        list(pre_run["launch"]["payload_argv"]),
        close_fds=True,
        cwd=pre_run["launch"]["cwd"],
        env=pinned_environment,
        start_new_session=False,
        stdout=None,
        stderr=None,
    )
    payload_starttime = proc_starttime(process.pid)
    if payload_starttime is None:
        _terminate_exact_child(process)
        raise LifecycleError("cannot establish payload starttime")
    status = wait_without_reaping(
        process.pid,
        timeout_seconds=int(resource_contract["runtime_max_seconds"]) - 60,
        monotonic=monotonic,
        sleep=sleep,
    )
    if status is None:
        _terminate_exact_child(process)
        raise LifecycleError("payload exceeded preregistered internal timeout")
    expected_returncode = _returncode_from_waitid(status)
    result_path = Path(pre_run["output_paths"]["attempt_result"])
    payload_result, payload_result_snapshot = _load_json_snapshot(
        result_path,
        "payload result",
    )
    if (
        payload_result.get("schema_version") != "noncert-cuts-ab16-organic-arm-result-v1"
        or payload_result.get("slot") != pre_run["slot"]
    ):
        raise LifecycleError("payload result schema/slot drifted")
    payload_seal_ns = monotonic_ns()
    returncode = int(process.wait())
    payload_exit_ns = monotonic_ns()
    if returncode != expected_returncode or proc_starttime(process.pid) is not None:
        raise LifecycleError("payload waitid/waitpid/reap mismatch")
    payload_signal = -returncode if returncode < 0 else 0
    payload_exit_code = returncode if returncode >= 0 else 0
    inner = build_inner_record(
        pre_run,
        pre_run_snapshot.identity,
        selection,
        selection_snapshot.identity,
        invocation_id=invocation_id,
        launch_observation=launch_observation,
        supervisor_pid=supervisor_pid,
        supervisor_starttime=supervisor_starttime,
        payload_pid=process.pid,
        payload_starttime=payload_starttime,
        payload_seal_monotonic_ns=payload_seal_ns,
        payload_exit_monotonic_ns=payload_exit_ns,
        payload_exit_code=payload_exit_code,
        payload_signal=payload_signal,
        payload_reaped=True,
        payload_result_identity=payload_result_snapshot.identity,
        keeper_ready_monotonic_ns=monotonic_ns(),
    )
    inner_identity = write_json_exclusive(
        Path(pre_run["output_paths"]["inner"]),
        inner,
    )
    release_path = Path(pre_run["output_paths"]["release"])
    release_deadline = started + int(resource_contract["runtime_max_seconds"]) - 10
    while monotonic() <= release_deadline:
        if os.path.lexists(release_path):
            release, _release_snapshot = _load_json_snapshot(
                release_path,
                "keeper release",
            )
            _validate_keeper_release(
                release,
                pre_run=pre_run,
                pre_run_identity=pre_run_snapshot.identity,
                selection_identity=selection_snapshot.identity,
                inner_identity=inner_identity,
                invocation_id=invocation_id,
                keeper_pid=supervisor_pid,
                keeper_starttime=supervisor_starttime,
            )
            return returncode if returncode >= 0 else 128 + payload_signal
        sleep(0.05)
    raise LifecycleError("keeper release token did not arrive before RuntimeMax")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    supervisor = subcommands.add_parser("supervise")
    supervisor.add_argument("--pre-run", required=True, type=Path)
    supervisor.add_argument("--selection", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command != "supervise":
            raise LifecycleError("unsupported lifecycle command")
        return supervise_payload(
            pre_run_path=arguments.pre_run,
            selection_path=arguments.selection,
        )
    except LifecycleError as exc:
        print(f"FAIL_CLOSED: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
