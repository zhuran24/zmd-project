#!/usr/bin/env python3
"""Ordinary-user Gate 1 v4 unit orchestration.

This module assembles one selected ``systemd-run --user`` command and joins
the existing live manager-epoch checkpoint, keeper lifecycle, independent
resource verification, terminal observation, cleanup, and detached replay
APIs.  Importing this module has no side effects.  A caller must explicitly
provide a runtime adapter; the default adapter is available for a later
disposable or formal run but is never invoked by offline tests.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Protocol

import campaign_authority_v4 as authority
import gate1_campaign_driver_v4 as checkpoint_driver
import resource_lifecycle_v4 as lifecycle
import resource_verifier_v4 as resource_verifier


LAUNCH_SCHEMA = "noncert-cuts-gate1-v4-systemd-launch-evidence-v2"
ENTRYPOINT_SCHEMA = "noncert-cuts-gate1-v4-selected-byte-entrypoint-v1"
DETACHED_REPLAY_FILENAME = "detached-resource-replay.json"
REQUIRED_EXECUTION_TOOL_ROLES = frozenset(
    {
        "campaign_authority_v4",
        "gate1_campaign_driver_v4",
        "gate1_payload_v4",
        "gate1_unit_orchestrator_v4",
        "python3_13",
        "resource_lifecycle_v4",
        "resource_verifier_v4",
        "systemctl",
        "systemd_run",
    }
)
GATE1_SLOTS = authority.GATE1_SLOTS


# This loader is part of the authority-selected orchestrator bytes.  A target
# unit never asks Python to open a selected source path as a script.  Instead,
# this fixed loader snapshots every alias and target on one O_NOFOLLOW fd,
# checks the detached identity against the command's canonical manifest, then
# compiles and executes exactly those bytes.
SELECTED_BYTE_ENTRYPOINT_LOADER = r"""
import base64,hashlib,json,os,stat,sys,types

def _fail(message):
    raise RuntimeError("CUTS_GATE1_V4_SELECTED_LOADER: " + message)

def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            _fail("duplicate JSON key")
        result[key] = value
    return result

def _canonical(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

def _identity(value, label):
    if type(value) is not dict or set(value) != {"path", "sha256", "size_bytes"}:
        _fail(label + " identity fields drifted")
    path = value["path"]
    size = value["size_bytes"]
    digest = value["sha256"]
    if (
        type(path) is not str
        or not os.path.isabs(path)
        or type(size) is not int
        or size < 0
        or type(digest) is not str
        or len(digest) != 64
        or any(char not in "0123456789abcdef" for char in digest)
    ):
        _fail(label + " identity is malformed")
    return value

def _reject_symlink_components(path):
    absolute = os.path.abspath(path)
    current = os.path.sep
    for part in absolute.split(os.path.sep)[1:]:
        current = os.path.join(current, part)
        metadata = os.lstat(current)
        if stat.S_ISLNK(metadata.st_mode):
            _fail("symlink component rejected: " + current)
    return absolute

def _snapshot(value, label):
    identity = _identity(value, label)
    path = _reject_symlink_components(identity["path"])
    flags = os.O_RDONLY | os.O_CLOEXEC
    if not hasattr(os, "O_NOFOLLOW"):
        _fail("O_NOFOLLOW is unavailable")
    descriptor = os.open(path, flags | os.O_NOFOLLOW)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            _fail(label + " is not a regular file")
        chunks = []
        while True:
            chunk = os.read(descriptor, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    signature = lambda item: (
        item.st_dev,
        item.st_ino,
        item.st_mode,
        item.st_size,
        item.st_mtime_ns,
        item.st_ctime_ns,
    )
    if signature(before) != signature(after):
        _fail(label + " changed during same-fd snapshot")
    raw = b"".join(chunks)
    if (
        len(raw) != identity["size_bytes"]
        or hashlib.sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(label + " detached identity drifted")
    return raw

def _module(alias, raw, identity):
    module = types.ModuleType(alias)
    module.__file__ = identity["path"]
    module.__package__ = None
    sys.modules[alias] = module
    code = compile(
        raw,
        "<authority-selected:" + alias + ":" + identity["sha256"] + ">",
        "exec",
        dont_inherit=True,
    )
    exec(code, module.__dict__, module.__dict__)

if len(sys.argv) != 2:
    _fail("loader accepts exactly one canonical manifest")
try:
    encoded = sys.argv[1].encode("ascii")
    raw_manifest = base64.b64decode(encoded, validate=True)
    manifest = json.loads(
        raw_manifest.decode("utf-8"),
        object_pairs_hook=_pairs,
        parse_constant=lambda token: _fail("non-finite JSON token " + token),
    )
except Exception as error:
    _fail("manifest decoding failed: " + str(error))
if _canonical(manifest) != raw_manifest:
    _fail("manifest bytes are not canonical")
if (
    type(manifest) is not dict
    or set(manifest) != {"aliases", "argv", "schema_version", "target"}
    or manifest["schema_version"] != "noncert-cuts-gate1-v4-selected-byte-entrypoint-v1"
    or type(manifest["aliases"]) is not list
    or type(manifest["argv"]) is not list
    or any(type(item) is not str or not item for item in manifest["argv"])
):
    _fail("manifest semantics drifted")
seen = set()
for index, member in enumerate(manifest["aliases"]):
    if (
        type(member) is not dict
        or set(member) != {"alias", "identity", "role"}
        or type(member["alias"]) is not str
        or not member["alias"]
        or type(member["role"]) is not str
        or not member["role"]
        or member["alias"] in seen
    ):
        _fail("alias member is malformed")
    seen.add(member["alias"])
    identity = _identity(member["identity"], "alias " + member["alias"])
    _module(
        member["alias"],
        _snapshot(identity, "alias " + member["alias"]),
        identity,
    )
target = manifest["target"]
if (
    type(target) is not dict
    or set(target) != {"identity", "role"}
    or type(target["role"]) is not str
    or not target["role"]
):
    _fail("target member is malformed")
target_identity = _identity(target["identity"], "target")
target_raw = _snapshot(target_identity, "target")
target_module = types.ModuleType("__main__")
target_module.__file__ = target_identity["path"]
target_module.__package__ = None
sys.modules["__main__"] = target_module
sys.argv = [target_identity["path"], *manifest["argv"]]
target_code = compile(
    target_raw,
    "<authority-selected:target:" + target_identity["sha256"] + ">",
    "exec",
    dont_inherit=True,
)
exec(target_code, target_module.__dict__, target_module.__dict__)
""".strip()


class OrchestrationError(RuntimeError):
    """A selected unit could not be orchestrated without weakening authority."""


@dataclass(frozen=True)
class LaunchObservation:
    argv: tuple[str, ...]
    exit_code: int
    stdout: bytes
    stderr: bytes
    started_monotonic_ns: int
    finished_monotonic_ns: int


class UnitRuntime(Protocol):
    """Injected launcher/waiter plus the existing lifecycle adapter surface."""

    def launch(self, argv: Sequence[str], *, timeout_seconds: int) -> LaunchObservation: ...

    def wait_for_regular(self, path: Path, *, timeout_seconds: int) -> None: ...

    def wait_for_terminal(
        self,
        unit_name: str,
        *,
        timeout_seconds: int,
    ) -> None: ...

    def show(
        self,
        unit_name: str,
        fields: Sequence[str],
    ) -> lifecycle.CommandEvidence: ...

    def read_cgroup(
        self,
        control_group: str,
        fields: Sequence[str],
    ) -> Mapping[str, bytes]: ...

    def pid_starttime(self, pid: int) -> int | None: ...

    def cgroup_exists(self, control_group: str) -> bool: ...

    def cleanup(self, unit_name: str) -> Sequence[lifecycle.CommandEvidence]: ...

    def load_state(self, unit_name: str) -> lifecycle.CommandEvidence: ...


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _exact_mapping(value: object, label: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise OrchestrationError(f"{label} must be an exact mapping")
    return value


def _identity_equal(left: object, right: object) -> bool:
    try:
        return dict(authority.validate_detached_identity(left, "left identity")) == dict(
            authority.validate_detached_identity(right, "right identity")
        )
    except authority.AuthorityError:
        return False


def _selected_attestor_paths(
    manager_epoch: Mapping[str, Any],
) -> dict[str, Path]:
    attestation = _exact_mapping(
        manager_epoch.get("attestation_toolchain"),
        "manager attestation toolchain",
    )
    observation = _exact_mapping(
        manager_epoch.get("observation_toolchain"),
        "manager observation toolchain",
    )
    result: dict[str, Path] = {}
    for role, member in (
        ("attestor", attestation.get("attestor")),
        ("python", attestation.get("python")),
        ("sudo", attestation.get("sudo")),
        ("busctl", observation.get("busctl")),
    ):
        identity = _exact_mapping(member, f"manager tool {role}")
        path = identity.get("requested_path", identity.get("path"))
        if type(path) is not str or not Path(path).is_absolute():
            raise OrchestrationError(f"manager tool {role} path is invalid")
        result[role] = Path(path)
    return result


def _replay_selection_members(selection: Mapping[str, Any]) -> None:
    for group in ("tools", "inputs"):
        members = _exact_mapping(selection.get(group), f"selected {group}")
        for role, identity in members.items():
            if type(role) is not str or not role:
                raise OrchestrationError(f"selected {group} role is invalid")
            authority.replay_detached_identity(
                _exact_mapping(identity, f"selected {group}.{role}"),
                f"selected {group}.{role}",
            )
    tools = _exact_mapping(selection["tools"], "selected tools")
    missing = REQUIRED_EXECUTION_TOOL_ROLES - set(tools)
    if missing:
        raise OrchestrationError(f"selected execution tool roles are absent: {sorted(missing)}")


def _load_execution_authority(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
) -> tuple[
    Mapping[str, Any],
    lifecycle.DetachedDocument,
    authority.Snapshot,
    authority.Snapshot,
]:
    root, selection, root_snapshot, selection_snapshot = checkpoint_driver._load_bound_authorities(  # noqa: SLF001
        campaign_root_identity=campaign_root_identity,
        selection_identity=selection_identity,
    )
    lifecycle_selection = lifecycle.load_gate1_selection_bytes(
        selection_snapshot.data,
        selection_identity,
    )
    if lifecycle_selection.value != selection:
        raise OrchestrationError("campaign and lifecycle selection parsers disagree")
    _replay_selection_members(selection)
    if selection["resource_contract"] != authority.RESOURCE_CONTRACT:
        raise OrchestrationError("selected resource contract drifted")
    return root, lifecycle_selection, root_snapshot, selection_snapshot


def _selected_path(selection: Mapping[str, Any], role: str) -> str:
    identity = _exact_mapping(
        _exact_mapping(selection["tools"], "selected tools").get(role),
        f"selected tool {role}",
    )
    path = identity.get("path")
    if type(path) is not str or not Path(path).is_absolute():
        raise OrchestrationError(f"selected tool {role} path is invalid")
    return path


def _selected_project_root(selection: Mapping[str, Any]) -> Path:
    identity = _exact_mapping(
        _exact_mapping(selection["inputs"], "selected inputs").get("project_lock"),
        "selected project lock",
    )
    path = identity.get("path")
    if type(path) is not str or not Path(path).is_absolute() or Path(path).name != "PROJECT_LOCK.md":
        raise OrchestrationError("selected project lock path is invalid")
    return Path(path).parent


def _detached_projection(identity: object, label: str) -> dict[str, object]:
    checked = authority.validate_detached_identity(identity, label)
    return {
        "path": checked["path"],
        "size_bytes": checked["size_bytes"],
        "sha256": checked["sha256"],
    }


def _selected_entrypoint_command(
    *,
    selection: Mapping[str, Any],
    target_role: str,
    aliases: Sequence[tuple[str, str]],
    argv: Sequence[str],
) -> tuple[str, ...]:
    tools = _exact_mapping(selection["tools"], "selected tools")
    if (
        not isinstance(argv, Sequence)
        or isinstance(argv, (str, bytes))
        or any(type(item) is not str or not item for item in argv)
    ):
        raise OrchestrationError("selected entrypoint argv is invalid")
    alias_members: list[dict[str, object]] = []
    seen_aliases: set[str] = set()
    for alias, role in aliases:
        if type(alias) is not str or not alias or alias in seen_aliases or type(role) is not str or not role:
            raise OrchestrationError("selected entrypoint alias set is invalid")
        seen_aliases.add(alias)
        alias_members.append(
            {
                "alias": alias,
                "role": role,
                "identity": _detached_projection(
                    tools.get(role),
                    f"selected entrypoint alias {role}",
                ),
            }
        )
    manifest = {
        "schema_version": ENTRYPOINT_SCHEMA,
        "aliases": alias_members,
        "target": {
            "role": target_role,
            "identity": _detached_projection(
                tools.get(target_role),
                f"selected entrypoint target {target_role}",
            ),
        },
        "argv": list(argv),
    }
    manifest_raw = json.dumps(
        manifest,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded = base64.b64encode(manifest_raw).decode("ascii")
    return (
        _selected_path(selection, "python3_13"),
        "-I",
        "-c",
        SELECTED_BYTE_ENTRYPOINT_LOADER,
        encoded,
    )


def build_systemd_run_argv(
    *,
    root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    selection: Mapping[str, Any],
    unit_slot: str,
) -> tuple[str, ...]:
    """Build the exact ordinary-user transient-unit launch command."""

    if unit_slot not in GATE1_SLOTS:
        raise OrchestrationError("organic or unknown arm cannot be launched")
    unit = _exact_mapping(selection["units"][unit_slot], f"selected unit {unit_slot}")
    contract = _exact_mapping(selection["resource_contract"], "resource contract")
    profiles = _exact_mapping(contract["profiles"], "resource profiles")
    profile = _exact_mapping(
        profiles[unit["contract_profile"]],
        "selected resource profile",
    )
    expected = authority.RESOURCE_CONTRACT
    if contract != expected:
        raise OrchestrationError("selected resource contract is not the v4 contract")
    systemd_run = _selected_path(selection, "systemd_run")
    project_root = _selected_project_root(selection)
    identity_arguments = (
        "--campaign-root",
        str(root_identity["path"]),
        "--campaign-root-size",
        str(root_identity["size_bytes"]),
        "--campaign-root-sha256",
        str(root_identity["sha256"]),
        "--selection",
        str(selection_identity["path"]),
        "--selection-size",
        str(selection_identity["size_bytes"]),
        "--selection-sha256",
        str(selection_identity["sha256"]),
        "--unit-slot",
        unit_slot,
    )
    payload_command = _selected_entrypoint_command(
        selection=selection,
        target_role="gate1_payload_v4",
        aliases=(
            ("campaign_authority_v4", "campaign_authority_v4"),
            ("resource_lifecycle_v4", "resource_lifecycle_v4"),
        ),
        argv=identity_arguments,
    )
    supervisor_command = _selected_entrypoint_command(
        selection=selection,
        target_role="resource_lifecycle_v4",
        aliases=(),
        argv=(
            "supervisor",
            "--selection",
            str(selection_identity["path"]),
            "--selection-size",
            str(selection_identity["size_bytes"]),
            "--selection-sha256",
            str(selection_identity["sha256"]),
            "--unit-slot",
            unit_slot,
            *payload_command,
        ),
    )
    argv = (
        systemd_run,
        "--user",
        f"--unit={unit['unit_name']}",
        f"--working-directory={project_root}",
        "--property=Type=exec",
        "--property=RemainAfterExit=yes",
        f"--property=MemoryHigh={contract['memory_high_bytes']}",
        f"--property=MemoryMax={contract['memory_max_bytes']}",
        f"--property=MemorySwapMax={contract['memory_swap_max_bytes']}",
        f"--property=OOMPolicy={contract['oom_policy']}",
        f"--property=KillMode={contract['kill_mode']}",
        "--property=SendSIGKILL=yes" if contract["send_sigkill"] else "--property=SendSIGKILL=no",
        f"--property=RuntimeMaxSec={profile['runtime_max_seconds']}",
        "--",
        *supervisor_command,
    )
    if any(Path(item).name == "sudo" for item in argv):
        raise OrchestrationError("sudo is forbidden from the unit launch command")
    return argv


def _write_launch_evidence(
    *,
    path: Path,
    campaign_root_identity: Mapping[str, object],
    selection: Mapping[str, Any],
    selection_identity: Mapping[str, object],
    unit_slot: str,
    observation: LaunchObservation,
    expected_argv: Sequence[str],
    now_utc: Callable[[], str],
) -> dict[str, object]:
    if (
        observation.argv != tuple(expected_argv)
        or observation.exit_code != 0
        or observation.started_monotonic_ns <= 0
        or observation.finished_monotonic_ns < observation.started_monotonic_ns
    ):
        raise OrchestrationError("systemd-run launch evidence failed closed")
    record = {
        "schema_version": LAUNCH_SCHEMA,
        "created_at_utc": now_utc(),
        "campaign_root_identity": dict(campaign_root_identity),
        "selection_identity": dict(selection_identity),
        "campaign_id": selection["campaign_id"],
        "run_nonce": selection["run_nonce"],
        "selection_id": selection["selection_id"],
        "manager_epoch_digest": hashlib.sha256(authority.canonical_json(selection["manager_epoch"])).hexdigest(),
        "unit_slot": unit_slot,
        "unit_name": selection["units"][unit_slot]["unit_name"],
        "argv": list(observation.argv),
        "argv_sha256": hashlib.sha256(authority.canonical_json(list(observation.argv))).hexdigest(),
        "selected_loader_sha256": hashlib.sha256(SELECTED_BYTE_ENTRYPOINT_LOADER.encode("utf-8")).hexdigest(),
        "orchestrator_identity": dict(selection["tools"]["gate1_unit_orchestrator_v4"]),
        "exit_code": observation.exit_code,
        "stdout_b64": base64.b64encode(observation.stdout).decode("ascii"),
        "stderr_b64": base64.b64encode(observation.stderr).decode("ascii"),
        "started_monotonic_ns": observation.started_monotonic_ns,
        "finished_monotonic_ns": observation.finished_monotonic_ns,
        "systemd_run_identity": dict(selection["tools"]["systemd_run"]),
    }
    return authority.write_exclusive(path, authority.canonical_json(record))


def _snapshot(path: Path, label: str) -> tuple[bytes, dict[str, object]]:
    snapshot = authority.snapshot_regular(path)
    return snapshot.data, authority.detached_identity(snapshot)


def _prepare_attempt(selection: Mapping[str, Any], unit_slot: str) -> None:
    unit = _exact_mapping(selection["units"][unit_slot], f"selected unit {unit_slot}")
    attempt = Path(str(unit["attempt_dir"]))
    raw_dir = Path(str(unit["raw_dir"]))
    terminal_dir = Path(str(unit["terminal_dir"]))
    authority_dir = attempt / "authority"
    if any(os.path.lexists(path) for path in (attempt, raw_dir, terminal_dir, authority_dir)):
        raise OrchestrationError("selected unit attempt already exists")
    units_parent = attempt.parent
    selection_parent = Path(str(selection["campaign_root_identity"]["path"])).parent / "gate1-v4"
    if units_parent != selection_parent / "units":
        raise OrchestrationError("selected unit parent topology drifted")
    if not os.path.lexists(units_parent):
        authority.mkdir_exclusive(units_parent)
    else:
        if not units_parent.is_dir() or os.path.islink(units_parent):
            raise OrchestrationError("selected unit parent is not a stable directory")
    authority.mkdir_exclusive(attempt)
    authority.mkdir_exclusive(authority_dir)
    authority.mkdir_exclusive(raw_dir)
    authority.mkdir_exclusive(terminal_dir)


class _LaunchTrackingRuntime:
    """Delegate the runtime surface while recording that launch was invoked."""

    def __init__(self, runtime: UnitRuntime) -> None:
        self._runtime = runtime
        self.launch_attempted = False

    def launch(
        self,
        argv: Sequence[str],
        *,
        timeout_seconds: int,
    ) -> LaunchObservation:
        self.launch_attempted = True
        return self._runtime.launch(argv, timeout_seconds=timeout_seconds)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._runtime, name)


def _validate_emergency_cleanup(
    *,
    runtime: UnitRuntime,
    unit_name: str,
    timeout_seconds: int = 30,
) -> None:
    """Remove one launched unit without publishing lifecycle authority."""

    commands = tuple(runtime.cleanup(unit_name))
    expected = (
        (str(lifecycle.SYSTEMCTL), "--user", "stop", unit_name),
        (str(lifecycle.SYSTEMCTL), "--user", "reset-failed", unit_name),
    )
    if len(commands) != len(expected):
        raise OrchestrationError("emergency cleanup command count drifted")
    for index, (command, expected_argv) in enumerate(zip(commands, expected, strict=True)):
        if tuple(command.argv) != expected_argv:
            raise OrchestrationError("emergency cleanup argv drifted")
        if index == 0:
            if command.exit_code != 0 or command.stdout or command.stderr:
                raise OrchestrationError("emergency cleanup stop failed")
            continue
        expected_not_loaded = (
            f"Failed to reset failed state of unit {unit_name}: Unit {unit_name} not loaded.\n"
        ).encode()
        reset_ok = (command.exit_code == 0 and command.stdout == b"" and command.stderr == b"") or (
            command.exit_code == 1 and command.stdout == b"" and command.stderr == expected_not_loaded
        )
        if not reset_ok:
            raise OrchestrationError("emergency cleanup reset-failed failed")

    deadline = time.monotonic() + timeout_seconds
    expected_load_argv = lifecycle._load_state_argv(unit_name)  # noqa: SLF001
    while time.monotonic() <= deadline:
        load_state = runtime.load_state(unit_name)
        if (
            tuple(load_state.argv) == expected_load_argv
            and load_state.exit_code == 0
            and load_state.stdout == b"not-found\n"
            and load_state.stderr == b""
        ):
            return
        time.sleep(0.05)
    raise OrchestrationError("emergency cleanup did not establish unit absence")


def _orchestrate_selected_unit_without_failure_cleanup(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    unit_slot: str,
    runtime: UnitRuntime,
    checkpoint: Callable[..., Mapping[str, object]] = (checkpoint_driver.capture_lifecycle_epoch_checkpoint),
    capture_preterminal: Callable[..., tuple[dict[str, object], dict[str, object]]] = (lifecycle.capture_preterminal),
    verify_preterminal: Callable[..., dict[str, object]] = (resource_verifier.verify_preterminal_bytes),
    build_release: Callable[..., dict[str, object]] = (resource_verifier.build_release_token),
    capture_terminal: Callable[..., tuple[dict[str, object], dict[str, object]]] = (lifecycle.capture_terminal),
    capture_cleanup: Callable[..., tuple[dict[str, object], dict[str, object]]] = (lifecycle.capture_cleanup),
    verify_detached: Callable[..., dict[str, object]] = (resource_verifier.verify_detached_bytes),
    now_utc: Callable[[], str] = _utc_now,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
) -> dict[str, object]:
    """Fixture-capable implementation behind the sealed production surface."""

    if os.geteuid() != os.getuid() or os.geteuid() == 0:
        raise OrchestrationError("Gate 1 orchestrator must run as the ordinary user")
    if unit_slot not in GATE1_SLOTS:
        raise OrchestrationError("organic or unknown arm cannot be orchestrated")
    root, selection_document, _, _ = _load_execution_authority(
        campaign_root_identity=campaign_root_identity,
        selection_identity=selection_identity,
    )
    selection = selection_document.value
    unit = _exact_mapping(selection["units"][unit_slot], f"selected unit {unit_slot}")
    paths = lifecycle.lifecycle_paths(selection, unit_slot)
    _prepare_attempt(selection, unit_slot)
    manager_tools = _selected_attestor_paths(selection["manager_epoch"])

    def capture_phase(phase: str) -> Mapping[str, object]:
        return checkpoint(
            campaign_root_identity=campaign_root_identity,
            selection_identity=selection_identity,
            unit_slot=unit_slot,
            phase=phase,
            attestor_path=manager_tools["attestor"],
            busctl_path=manager_tools["busctl"],
            python_path=manager_tools["python"],
            sudo_path=manager_tools["sudo"],
        )

    checkpoints: dict[str, Mapping[str, object]] = {}
    checkpoints["prelaunch"] = capture_phase("prelaunch")
    argv = build_systemd_run_argv(
        root_identity=campaign_root_identity,
        selection_identity=selection_identity,
        selection=selection,
        unit_slot=unit_slot,
    )
    profile = selection["resource_contract"]["profiles"][unit["contract_profile"]]
    launch = runtime.launch(
        argv,
        timeout_seconds=min(30, int(profile["runtime_max_seconds"])),
    )
    launch_identity = _write_launch_evidence(
        path=Path(str(unit["raw_dir"])) / "systemd-run-launch.json",
        campaign_root_identity=campaign_root_identity,
        selection=selection,
        selection_identity=selection_identity,
        unit_slot=unit_slot,
        observation=launch,
        expected_argv=argv,
        now_utc=now_utc,
    )
    runtime.wait_for_regular(
        paths["inner"],
        timeout_seconds=int(profile["internal_timeout_seconds"]) + 5,
    )
    checkpoints["preterminal"] = capture_phase("preterminal")
    _, preterminal_identity = capture_preterminal(
        selection=selection_document,
        unit_slot=unit_slot,
        adapter=runtime,
    )
    selection_raw = selection_document.raw
    inner_raw, inner_identity = _snapshot(paths["inner"], "inner lifecycle")
    preterminal_raw, checked_preterminal_identity = _snapshot(
        paths["preterminal"],
        "preterminal",
    )
    if checked_preterminal_identity != preterminal_identity:
        raise OrchestrationError("preterminal identity drifted before verification")
    verifier_identity = selection["tools"]["resource_verifier_v4"]
    resource_receipt = verify_preterminal(
        selection_raw=selection_raw,
        selection_identity=selection_identity,
        unit_slot=unit_slot,
        inner_raw=inner_raw,
        inner_identity=inner_identity,
        preterminal_raw=preterminal_raw,
        preterminal_identity=preterminal_identity,
        verifier_identity=verifier_identity,
        created_at_utc=now_utc(),
    )
    resource_identity = lifecycle.write_exclusive(
        paths["resource_verification"],
        lifecycle.canonical_json_bytes(resource_receipt),
    )
    release = build_release(
        resource_receipt,
        resource_identity,
        released_monotonic_ns=monotonic_ns(),
        created_at_utc=now_utc(),
    )
    release_identity = lifecycle.write_exclusive(
        paths["release"],
        lifecycle.canonical_json_bytes(release),
    )
    runtime.wait_for_terminal(
        str(unit["unit_name"]),
        timeout_seconds=int(profile["runtime_max_seconds"]) + 5,
    )
    checkpoints["terminal"] = capture_phase("terminal")
    _, terminal_identity = capture_terminal(
        selection=selection_document,
        unit_slot=unit_slot,
        adapter=runtime,
        preterminal_identity=preterminal_identity,
        release_identity=release_identity,
    )
    checkpoints["cleanup"] = capture_phase("cleanup")
    _, cleanup_identity = capture_cleanup(
        selection=selection_document,
        unit_slot=unit_slot,
        adapter=runtime,
        terminal_identity=terminal_identity,
    )
    checkpoints["detached-replay"] = capture_phase("detached-replay")

    resource_raw, checked_resource_identity = _snapshot(
        paths["resource_verification"],
        "resource receipt",
    )
    release_raw, checked_release_identity = _snapshot(paths["release"], "release")
    terminal_raw, checked_terminal_identity = _snapshot(paths["terminal"], "terminal")
    cleanup_raw, checked_cleanup_identity = _snapshot(paths["cleanup"], "cleanup")
    if (
        checked_resource_identity != resource_identity
        or checked_release_identity != release_identity
        or checked_terminal_identity != terminal_identity
        or checked_cleanup_identity != cleanup_identity
    ):
        raise OrchestrationError("lifecycle evidence identity drifted before detached replay")
    detached = verify_detached(
        selection_raw=selection_raw,
        selection_identity=selection_identity,
        unit_slot=unit_slot,
        inner_raw=inner_raw,
        inner_identity=inner_identity,
        preterminal_raw=preterminal_raw,
        preterminal_identity=preterminal_identity,
        resource_raw=resource_raw,
        resource_identity=resource_identity,
        release_raw=release_raw,
        release_identity=release_identity,
        terminal_raw=terminal_raw,
        terminal_identity=terminal_identity,
        cleanup_raw=cleanup_raw,
        cleanup_identity=cleanup_identity,
        verifier_identity=verifier_identity,
        created_at_utc=now_utc(),
    )
    detached_path = Path(str(unit["terminal_dir"])) / DETACHED_REPLAY_FILENAME
    detached_identity = lifecycle.write_exclusive(
        detached_path,
        lifecycle.canonical_json_bytes(detached),
    )
    _replay_selection_members(selection)
    authority.replay_detached_identity(
        campaign_root_identity,
        "post-unit campaign root",
    )
    authority.replay_detached_identity(
        selection_identity,
        "post-unit Gate 1 selection",
    )
    return {
        "unit_slot": unit_slot,
        "launch_identity": launch_identity,
        "checkpoint_identities": checkpoints,
        "resource_identity": resource_identity,
        "release_identity": release_identity,
        "terminal_identity": terminal_identity,
        "cleanup_identity": cleanup_identity,
        "detached_identity": detached_identity,
    }


def _orchestrate_selected_unit_with(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    unit_slot: str,
    runtime: UnitRuntime,
    checkpoint: Callable[..., Mapping[str, object]] = (checkpoint_driver.capture_lifecycle_epoch_checkpoint),
    capture_preterminal: Callable[..., tuple[dict[str, object], dict[str, object]]] = (lifecycle.capture_preterminal),
    verify_preterminal: Callable[..., dict[str, object]] = (resource_verifier.verify_preterminal_bytes),
    build_release: Callable[..., dict[str, object]] = (resource_verifier.build_release_token),
    capture_terminal: Callable[..., tuple[dict[str, object], dict[str, object]]] = (lifecycle.capture_terminal),
    capture_cleanup: Callable[..., tuple[dict[str, object], dict[str, object]]] = (lifecycle.capture_cleanup),
    verify_detached: Callable[..., dict[str, object]] = (resource_verifier.verify_detached_bytes),
    now_utc: Callable[[], str] = _utc_now,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
) -> dict[str, object]:
    """Run one unit and remove it if authority collection fails after launch."""

    if unit_slot not in GATE1_SLOTS:
        raise OrchestrationError("organic or unknown arm cannot be orchestrated")
    _, selected_document, _, _ = _load_execution_authority(
        campaign_root_identity=campaign_root_identity,
        selection_identity=selection_identity,
    )
    selected_unit_name = str(
        _exact_mapping(
            selected_document.value["units"][unit_slot],
            f"selected unit {unit_slot}",
        )["unit_name"]
    )
    tracked_runtime = _LaunchTrackingRuntime(runtime)
    normal_cleanup_complete = False

    def tracked_capture_cleanup(
        **kwargs: object,
    ) -> tuple[dict[str, object], dict[str, object]]:
        nonlocal normal_cleanup_complete
        result = capture_cleanup(**kwargs)
        normal_cleanup_complete = True
        return result

    try:
        return _orchestrate_selected_unit_without_failure_cleanup(
            campaign_root_identity=campaign_root_identity,
            selection_identity=selection_identity,
            unit_slot=unit_slot,
            runtime=tracked_runtime,
            checkpoint=checkpoint,
            capture_preterminal=capture_preterminal,
            verify_preterminal=verify_preterminal,
            build_release=build_release,
            capture_terminal=capture_terminal,
            capture_cleanup=tracked_capture_cleanup,
            verify_detached=verify_detached,
            now_utc=now_utc,
            monotonic_ns=monotonic_ns,
        )
    except BaseException as primary_error:
        if tracked_runtime.launch_attempted and not normal_cleanup_complete:
            try:
                _validate_emergency_cleanup(
                    runtime=runtime,
                    unit_name=selected_unit_name,
                )
            except BaseException as cleanup_error:
                raise BaseExceptionGroup(
                    "Gate 1 unit authority collection and emergency cleanup both failed",
                    [primary_error, cleanup_error],
                ) from None
        raise


def orchestrate_selected_unit(
    *,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    unit_slot: str,
) -> dict[str, object]:
    """Run one selected unit with the sole production runtime and lifecycle."""

    return _orchestrate_selected_unit_with(
        campaign_root_identity=campaign_root_identity,
        selection_identity=selection_identity,
        unit_slot=unit_slot,
        runtime=SubprocessUserRuntime(),
    )


class SubprocessUserRuntime(lifecycle.SystemctlUserAdapter):
    """Production ordinary-user adapter, selected but unused by offline tests."""

    def launch(self, argv: Sequence[str], *, timeout_seconds: int) -> LaunchObservation:
        if os.geteuid() != os.getuid() or os.geteuid() == 0:
            raise OrchestrationError("systemd-run launcher must remain unprivileged")
        if not argv or "--user" not in argv or any(Path(item).name == "sudo" for item in argv):
            raise OrchestrationError("launcher command is not ordinary-user systemd-run")
        started = time.monotonic_ns()
        completed = subprocess.run(
            list(argv),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            close_fds=True,
        )
        finished = time.monotonic_ns()
        return LaunchObservation(
            argv=tuple(argv),
            exit_code=int(completed.returncode),
            stdout=bytes(completed.stdout),
            stderr=bytes(completed.stderr),
            started_monotonic_ns=started,
            finished_monotonic_ns=finished,
        )

    def wait_for_regular(self, path: Path, *, timeout_seconds: int) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() <= deadline:
            if os.path.lexists(path):
                authority.snapshot_regular(path)
                return
            time.sleep(0.05)
        raise OrchestrationError(f"selected lifecycle file did not appear: {path}")

    def wait_for_terminal(self, unit_name: str, *, timeout_seconds: int) -> None:
        deadline = time.monotonic() + timeout_seconds
        fields = ("ActiveState", "SubState", "InvocationID")
        while time.monotonic() <= deadline:
            command = self.show(unit_name, fields)
            if command.exit_code == 0 and command.stderr == b"":
                values: dict[str, str] = {}
                for line in command.stdout.decode("utf-8", "strict").splitlines():
                    if "=" not in line:
                        raise OrchestrationError("terminal wait systemctl output is malformed")
                    key, value = line.split("=", 1)
                    if key in values or key not in fields:
                        raise OrchestrationError("terminal wait systemctl fields drifted")
                    values[key] = value
                if set(values) == set(fields) and (
                    values["ActiveState"] == "failed"
                    or (values["ActiveState"] == "active" and values["SubState"] == "exited")
                ):
                    return
            time.sleep(0.05)
        raise OrchestrationError("selected unit did not reach terminal state")
