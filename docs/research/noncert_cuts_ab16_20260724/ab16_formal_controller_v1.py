#!/usr/bin/env python3
"""Package-pinned outer payload for one formal AB16 campaign.

The controller is deliberately not a launch authority.  It consumes the
independently published formal selection, waits for the supervisor's
canonical barrier, and only then runs the already-owned campaign stages:

1. Gate1-v4 formal preparation, four fixed child units, and formal gate;
2. a fresh selected-byte baseline rebuild, fixed-assignment replay, and
   independent baseline admission;
3. the immutable organic manifest and non-launching suite selection;
4. the fixed sixteen-arm sequence, one fresh selected unit at a time.

System effects stay behind existing owners.  Gate1-v4 is called through its
unchanged execution owner, each baseline role is a fresh selected-byte child,
and organic units are launched only by ``organic_unit_orchestrator_v2``.
Per-arm prelaunch ownership is a canonical request/receipt exchange with the
outer supervisor.  This module never publishes Gate B, formal admission,
formal selection, outer lifecycle evidence, or a final successful closeout.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import sys
import time
from types import ModuleType, SimpleNamespace
from typing import Any, Protocol

from docs.research.noncert_cuts_ab16_20260724 import ab16_authority_v2 as authority
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_formal_launch_validator_v1 as launch_validator,
)


CONTROLLER_RESULT_SCHEMA = "noncert-cuts-ab16-formal-controller-result-v1"
OUTER_BARRIER_SCHEMA = "noncert-cuts-ab16-outer-barrier-release-v1"
AUTHORITY_SCOPE = "AB16_RESEARCH_ONLY"
CONTROLLER_RESULT_NAME = "controller-result.json"
_AUTHORITY_ARM_SEQUENCE = authority.EXPERIMENT_CONTRACT.get("order")
if (
    type(_AUTHORITY_ARM_SEQUENCE) is not list
    or len(_AUTHORITY_ARM_SEQUENCE) != 16
    or any(type(slot) is not str or not slot for slot in _AUTHORITY_ARM_SEQUENCE)
):
    raise RuntimeError("AB16 authority-owned arm sequence is malformed")
ARM_SEQUENCE: tuple[str, ...] = tuple(_AUTHORITY_ARM_SEQUENCE)
GATE1_SLOTS = (
    "q-success",
    "q-postseal-fail",
    "forced-control",
    "forced-treatment",
)
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
FALSE_AUTHORIZATIONS = dict(launch_validator.FALSE_CLAIMS)
MAX_ROLE_OUTPUT_BYTES = 8 * 1024 * 1024

BARRIER_FIELDS = frozenset(
    {
        "authority_scope",
        "authorizations",
        "campaign_root_identity",
        "formal_selection_identity",
        "gate1_prelaunch_ownership_identity",
        "lock_identities",
        "manager_epoch",
        "outer_resource_identity",
        "outer_start_identity",
        "reference_acquisition_identity",
        "released",
        "schema_version",
        "status",
    }
)


class FormalControllerError(RuntimeError):
    """The selected controller sequence failed closed."""


@dataclass(frozen=True)
class FormalInputs:
    """Read-only validated authority needed before the barrier."""

    context: dict[str, object]
    selection: dict[str, object]
    selection_identity: dict[str, object]


@dataclass(frozen=True)
class SelectedRoleResult:
    """One fresh selected-byte child result."""

    role: str
    returncode: int
    stdout: bytes
    stderr: bytes


class ControllerPorts(Protocol):
    """Narrow seams around effects already owned elsewhere."""

    def wait_for_barrier(self, inputs: FormalInputs) -> tuple[dict[str, object], dict[str, object]]:
        """Wait for and validate the single supervisor release barrier."""

    def run_gate1(self, inputs: FormalInputs) -> Mapping[str, object]:
        """Run the unchanged Gate1-v4 formal owner in its fixed order."""

    def run_selected_role(
        self,
        inputs: FormalInputs,
        *,
        role: str,
        argv: Sequence[str],
        timeout_seconds: float,
    ) -> SelectedRoleResult:
        """Run one package-selected role in a fresh process."""

    def run_baseline_chain(self, inputs: FormalInputs) -> Mapping[str, object]:
        """Run the fixed three-role baseline chain."""

    def publish_arm_prelaunch_request(
        self,
        inputs: FormalInputs,
        *,
        slot: str,
        ordinal: int,
    ) -> dict[str, object]:
        """Publish the existing helper-owned prelaunch request."""

    def wait_for_arm_prelaunch_receipt(
        self,
        inputs: FormalInputs,
        *,
        slot: str,
        ordinal: int,
        request_identity: Mapping[str, object],
    ) -> dict[str, object]:
        """Wait for the supervisor's same-request absence receipt."""

    def run_organic_arm(
        self,
        inputs: FormalInputs,
        *,
        pre_run_path: Path,
        selection_path: Path,
    ) -> Mapping[str, object]:
        """Delegate one selected arm to the existing organic orchestrator."""


def _closed(value: object, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != set(fields):
        raise FormalControllerError(f"{label} field set drifted")
    return dict(value)


def _identity(value: object, label: str) -> dict[str, object]:
    try:
        return launch_validator.validate_detached_identity(value, label)
    except Exception as exc:
        raise FormalControllerError(f"{label} is invalid: {exc}") from exc


def _snapshot_identity(path: Path | str) -> dict[str, object]:
    return authority.detached_identity(authority.snapshot_regular(path))


def _read_record(
    path: Path | str,
    *,
    expected_identity: Mapping[str, object] | None,
    label: str,
) -> tuple[dict[str, Any], dict[str, object]]:
    try:
        return launch_validator.read_canonical_record(
            path,
            expected_identity=expected_identity,
            label=label,
        )
    except Exception as exc:
        raise FormalControllerError(f"{label} replay failed: {exc}") from exc


def load_formal_inputs(
    *,
    campaign_dir: Path | str,
    formal_selection: Path | str,
) -> FormalInputs:
    """Replay the complete formal selection without authoring any authority."""

    campaign = Path(campaign_dir).absolute()
    selection_path = Path(formal_selection).absolute()
    try:
        context = launch_validator.replay_formal_launch_context(authority, campaign)
    except Exception as exc:
        raise FormalControllerError(f"formal launch context replay failed: {exc}") from exc
    if selection_path != Path(str(context["formal_selection_path"])):
        raise FormalControllerError("caller formal selection path differs from authority context")
    selection, selection_identity = _read_record(
        selection_path,
        expected_identity=None,
        label="formal selection",
    )
    prerequisite_fields = {
        "formal_admission_identity": "formal admission",
        "guardian_ready_identity": "guardian ready",
        "attempt_consumption_identity": "attempt consumption",
    }
    records: dict[str, dict[str, Any]] = {}
    identities: dict[str, dict[str, object]] = {}
    for field, label in prerequisite_fields.items():
        expected = _identity(selection.get(field), f"selection {field}")
        record, observed = _read_record(
            expected["path"],
            expected_identity=expected,
            label=label,
        )
        records[field] = record
        identities[field] = observed
    try:
        checked = launch_validator.validate_selection(
            selection,
            admission=records["formal_admission_identity"],
            admission_identity=identities["formal_admission_identity"],
            guardian_ready=records["guardian_ready_identity"],
            guardian_ready_identity=identities["guardian_ready_identity"],
            attempt_consumption=records["attempt_consumption_identity"],
            attempt_consumption_identity=identities["attempt_consumption_identity"],
            expected_context=context,
        )
    except Exception as exc:
        raise FormalControllerError(f"formal selection validation failed: {exc}") from exc
    if checked["outer_spec"]["barrier_path"] != context["outer_spec"]["barrier_path"]:
        raise FormalControllerError("formal selection barrier join drifted")
    return FormalInputs(
        context=dict(context),
        selection=dict(checked),
        selection_identity=selection_identity,
    )


def validate_outer_barrier(
    value: object,
    *,
    inputs: FormalInputs,
) -> dict[str, object]:
    """Validate the supervisor release without granting any new authority."""

    record = _closed(value, BARRIER_FIELDS, "outer barrier")
    for field in (
        "campaign_root_identity",
        "formal_selection_identity",
        "gate1_prelaunch_ownership_identity",
        "outer_resource_identity",
        "outer_start_identity",
        "reference_acquisition_identity",
    ):
        record[field] = _identity(record[field], f"outer barrier {field}")
    try:
        record["lock_identities"] = launch_validator.validate_lock_identities(record["lock_identities"])
    except Exception as exc:
        raise FormalControllerError(f"outer barrier lock identities failed: {exc}") from exc
    outer_paths = inputs.selection["outer_spec"]["receipt_paths"]
    expected_paths = {
        "outer_start_identity": outer_paths["outer_start"],
        "outer_resource_identity": outer_paths["outer_resource"],
        "reference_acquisition_identity": outer_paths["reference_acquisition"],
        "gate1_prelaunch_ownership_identity": inputs.selection["gate1_prelaunch_ownership_path"],
    }
    if any(record[field]["path"] != expected for field, expected in expected_paths.items()):
        raise FormalControllerError("outer barrier prerequisite path drifted")
    if (
        record["schema_version"] != OUTER_BARRIER_SCHEMA
        or record["status"] != "RELEASED"
        or record["authority_scope"] != AUTHORITY_SCOPE
        or record["released"] is not True
        or record["authorizations"] != FALSE_AUTHORIZATIONS
        or record["campaign_root_identity"] != inputs.context["campaign_root_identity"]
        or record["formal_selection_identity"] != inputs.selection_identity
        or record["manager_epoch"] != inputs.context["manager_epoch"]
        or record["lock_identities"] != inputs.selection["lock_identities"]
    ):
        raise FormalControllerError("outer barrier authority/identity join drifted")
    for field in expected_paths:
        _read_record(
            record[field]["path"],
            expected_identity=record[field],
            label=f"outer barrier prerequisite {field}",
        )
    return record


def _wait_for_record(
    path: Path,
    *,
    timeout_seconds: float,
    label: str,
) -> tuple[dict[str, Any], dict[str, object]]:
    if timeout_seconds <= 0:
        raise FormalControllerError(f"{label} timeout is not positive")
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            observed = os.lstat(path)
        except FileNotFoundError:
            observed = None
        except OSError as exc:
            raise FormalControllerError(
                f"{label} surface could not be inspected"
            ) from exc
        if (
            observed is not None
            and stat.S_ISREG(observed.st_mode)
            and stat.S_IMODE(observed.st_mode) == 0o444
        ):
            return _read_record(path, expected_identity=None, label=label)
        if observed is not None and (
            not stat.S_ISREG(observed.st_mode)
            or stat.S_IMODE(observed.st_mode) != 0o600
        ):
            raise FormalControllerError(
                f"{label} surface is not one readonly regular file"
            )
        if time.monotonic() >= deadline:
            raise FormalControllerError(f"{label} did not appear before its fixed deadline")
        time.sleep(0.05)


def _module_origin(module: ModuleType, *, snapshot_root: Path, relative: str, label: str) -> None:
    raw = getattr(module, "__file__", None)
    expected = snapshot_root / relative
    if type(raw) is not str or Path(raw).resolve(strict=False) != expected.resolve(strict=False):
        raise FormalControllerError(f"{label} did not originate in the sealed snapshot")


def _import_snapshot_owner(
    inputs: FormalInputs,
    *,
    module_name: str,
    relative: str,
    aliases: Sequence[tuple[str, str, str]] = (),
) -> ModuleType:
    """Import one existing owner through the loader-established PathFinder."""

    snapshot_root = Path(str(inputs.context["snapshot_root"]))
    for alias, alias_module, alias_relative in aliases:
        loaded = importlib.import_module(alias_module)
        _module_origin(
            loaded,
            snapshot_root=snapshot_root,
            relative=alias_relative,
            label=f"snapshot alias {alias}",
        )
        present = sys.modules.get(alias)
        if present is not None and present is not loaded:
            raise FormalControllerError(f"snapshot alias collision: {alias}")
        sys.modules[alias] = loaded
    module = importlib.import_module(module_name)
    _module_origin(
        module,
        snapshot_root=snapshot_root,
        relative=relative,
        label=module_name,
    )
    return module


def _selected_role_template(inputs: FormalInputs) -> tuple[str, str, dict[str, Any]]:
    argv = inputs.selection["outer_spec"]["selected_byte_argv"]
    if (
        type(argv) is not list
        or len(argv) < 7
        or argv[1:4] != ["-I", "-B", "-c"]
        or argv[5] != "systemd-openfile"
    ):
        raise FormalControllerError("selected-byte outer argv is not the fixed three-FD form")
    try:
        identities = json.loads(argv[6])
    except (TypeError, json.JSONDecodeError) as exc:
        raise FormalControllerError("selected-byte identity JSON is invalid") from exc
    if type(identities) is not dict or set(identities) != {"authority", "loader", "python"}:
        raise FormalControllerError("selected-byte identity field set drifted")
    for role, identity in identities.items():
        if (
            type(identity) is not dict
            or set(identity) != {"mode", "path", "sha256", "size_bytes"}
            or type(identity["mode"]) is not int
            or type(identity["path"]) is not str
            or not Path(identity["path"]).is_absolute()
            or type(identity["sha256"]) is not str
            or SHA256_RE.fullmatch(identity["sha256"]) is None
            or type(identity["size_bytes"]) is not int
            or identity["size_bytes"] <= 0
        ):
            raise FormalControllerError(f"selected-byte {role} identity is malformed")
    if argv[0] != "/proc/self/fd/3":
        raise FormalControllerError("selected-byte Python executable is not fixed FD3")
    return argv[4], argv[6], identities


def _open_selected(identity: Mapping[str, Any], label: str) -> int:
    descriptor = os.open(
        identity["path"],
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != identity["mode"]
            or metadata.st_size != identity["size_bytes"]
        ):
            raise FormalControllerError(f"selected-byte {label} metadata drifted")
        current = os.stat(identity["path"], follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise FormalControllerError(f"selected-byte {label} path/FD drifted")
        digest = hashlib.sha256()
        offset = 0
        while offset < metadata.st_size:
            block = os.pread(descriptor, min(1 << 20, metadata.st_size - offset), offset)
            if not block:
                raise FormalControllerError(f"selected-byte {label} was truncated")
            digest.update(block)
            offset += len(block)
        if os.pread(descriptor, 1, metadata.st_size):
            raise FormalControllerError(f"selected-byte {label} grew during replay")
        replayed = os.fstat(descriptor)
        if (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            metadata.st_nlink,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        ) != (
            replayed.st_dev,
            replayed.st_ino,
            replayed.st_mode,
            replayed.st_nlink,
            replayed.st_size,
            replayed.st_mtime_ns,
            replayed.st_ctime_ns,
        ):
            raise FormalControllerError(f"selected-byte {label} changed during replay")
        if digest.hexdigest() != identity["sha256"]:
            raise FormalControllerError(f"selected-byte {label} SHA-256 drifted")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _drain_spawn(
    *,
    executable_fds: Mapping[int, int],
    argv: Sequence[str],
    timeout_seconds: float,
) -> tuple[int, bytes, bytes]:
    """posix_spawn with exact FD3/4/5 and bounded captured output."""

    if timeout_seconds <= 0:
        raise FormalControllerError("selected role timeout is not positive")
    stdout_read, stdout_write = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
    stderr_read, stderr_write = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
    high_fds: dict[int, int] = {}
    try:
        for target, source in executable_fds.items():
            high_fds[target] = fcntl.fcntl(source, fcntl.F_DUPFD_CLOEXEC, 20)
        actions: list[tuple[Any, ...]] = [
            (os.POSIX_SPAWN_DUP2, high_fds[3], 3),
            (os.POSIX_SPAWN_DUP2, high_fds[4], 4),
            (os.POSIX_SPAWN_DUP2, high_fds[5], 5),
            (os.POSIX_SPAWN_DUP2, stdout_write, 1),
            (os.POSIX_SPAWN_DUP2, stderr_write, 2),
            (os.POSIX_SPAWN_CLOSE, stdout_read),
            (os.POSIX_SPAWN_CLOSE, stderr_read),
        ]
        pid = os.posix_spawn(
            "/proc/self/fd/3",
            list(argv),
            {},
            file_actions=actions,
        )
    finally:
        for descriptor in high_fds.values():
            os.close(descriptor)
        os.close(stdout_write)
        os.close(stderr_write)
    selector = selectors.DefaultSelector()
    selector.register(stdout_read, selectors.EVENT_READ, "stdout")
    selector.register(stderr_read, selectors.EVENT_READ, "stderr")
    output = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + timeout_seconds
    status: int | None = None
    try:
        while selector.get_map() or status is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
                raise FormalControllerError("selected role exceeded its fixed deadline")
            for key, _event in selector.select(min(0.25, remaining)):
                block = os.read(key.fd, 64 * 1024)
                if block:
                    target = output[str(key.data)]
                    target.extend(block)
                    if len(target) > MAX_ROLE_OUTPUT_BYTES:
                        os.kill(pid, signal.SIGKILL)
                        os.waitpid(pid, 0)
                        raise FormalControllerError("selected role output exceeded its fixed limit")
                else:
                    selector.unregister(key.fd)
                    os.close(key.fd)
            if status is None:
                observed_pid, observed_status = os.waitpid(pid, os.WNOHANG)
                if observed_pid == pid:
                    status = observed_status
        if status is None:
            raise FormalControllerError("selected role terminal status is absent")
        return os.waitstatus_to_exitcode(status), bytes(output["stdout"]), bytes(output["stderr"])
    finally:
        for key in list(selector.get_map().values()):
            selector.unregister(key.fd)
            os.close(key.fd)
        selector.close()


class DefaultControllerPorts:
    """Live adapters composed only from package-pinned existing owners."""

    def __init__(self, inputs: FormalInputs) -> None:
        self.inputs = inputs
        if Path.cwd().resolve(strict=False) != Path(str(inputs.context["snapshot_root"])).resolve(strict=False):
            raise FormalControllerError("controller cwd is not the sealed snapshot root")
        try:
            campaign_context = authority._campaign_context(inputs.context["campaign_dir"])  # noqa: SLF001
            preregistration, _identity_value = authority._path_preregistration(  # noqa: SLF001
                campaign_context
            )
        except Exception as exc:
            raise FormalControllerError(f"campaign boundary replay failed: {exc}") from exc
        self.campaign_context = campaign_context
        self.preregistration = preregistration
        self._helper: ModuleType | None = None
        self._store: Any = None

    def wait_for_barrier(self, inputs: FormalInputs) -> tuple[dict[str, object], dict[str, object]]:
        path = Path(str(inputs.selection["outer_spec"]["barrier_path"]))
        record, identity = _wait_for_record(
            path,
            timeout_seconds=600.0,
            label="outer barrier",
        )
        return validate_outer_barrier(record, inputs=inputs), identity

    def run_gate1(self, inputs: FormalInputs) -> Mapping[str, object]:
        module = _import_snapshot_owner(
            inputs,
            module_name=(
                "docs.research.noncert_cuts_ab_trust_gate1_v4_20260724."
                "gate1_campaign_execution_v4"
            ),
            relative=(
                "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724/"
                "gate1_campaign_execution_v4.py"
            ),
            aliases=(
                (
                    "campaign_authority_v4",
                    (
                        "docs.research.noncert_cuts_ab_trust_gate1_v4_20260724."
                        "campaign_authority_v4"
                    ),
                    (
                        "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724/"
                        "campaign_authority_v4.py"
                    ),
                ),
            ),
        )
        root_identity = inputs.context["campaign_root_identity"]
        gate1_identity = inputs.context["gate1_selection_identity"]
        prepared = module.prepare_formal_positive_pair(
            campaign_root_identity=root_identity,
            selection_identity=gate1_identity,
            formal_authorized=True,
        )
        if prepared.get("mode") != module.FORMAL or prepared.get("formal_publication_authorized") is not True:
            raise FormalControllerError("Gate1 formal preparation did not authorize its fixed publication")
        units = module.orchestrate_gate1_units(
            campaign_root_identity=root_identity,
            selection_identity=gate1_identity,
            mode=module.FORMAL,
            formal_authorized=True,
        )
        if type(units) is not dict or list(units) != list(GATE1_SLOTS):
            raise FormalControllerError("Gate1 unit result order drifted")
        assembled = module.assemble_and_publish_formal_gate(
            campaign_root_identity=root_identity,
            selection_identity=gate1_identity,
            formal_authorized=True,
        )
        if (
            assembled.get("mode") != module.FORMAL
            or assembled.get("gate_written") is not True
            or assembled.get("continuation_written") is not True
            or assembled.get("organic_arm_launch_authorized") is not False
        ):
            raise FormalControllerError("Gate1 formal result crossed its authority boundary")
        return {
            "gate_identity": _identity(assembled.get("gate_identity"), "Gate1 gate"),
            "continuation_identity": _identity(
                assembled.get("continuation_identity"),
                "Gate1 continuation",
            ),
            "unit_order": list(units),
        }

    def run_selected_role(
        self,
        inputs: FormalInputs,
        *,
        role: str,
        argv: Sequence[str],
        timeout_seconds: float,
    ) -> SelectedRoleResult:
        literal, identity_json, identities = _selected_role_template(inputs)
        opened: dict[int, int] = {}
        try:
            opened[3] = _open_selected(identities["python"], "python")
            opened[4] = _open_selected(identities["loader"], "loader")
            opened[5] = _open_selected(identities["authority"], "authority")
            command = [
                identities["python"]["path"],
                "-I",
                "-B",
                "-c",
                literal,
                "direct",
                identity_json,
                "--campaign-dir",
                str(inputs.context["campaign_dir"]),
                "--role",
                role,
                "--",
                *argv,
            ]
            returncode, stdout, stderr = _drain_spawn(
                executable_fds=opened,
                argv=command,
                timeout_seconds=timeout_seconds,
            )
        finally:
            for descriptor in opened.values():
                os.close(descriptor)
        result = SelectedRoleResult(
            role=role,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )
        if returncode != 0 or stderr:
            raise FormalControllerError(
                f"selected role {role} failed: exit={returncode}, stderr={stderr!r}"
            )
        return result

    def run_baseline_chain(self, inputs: FormalInputs) -> Mapping[str, object]:
        return _run_baseline_chain(inputs, ports=self)

    def _outer_helper(self) -> tuple[ModuleType, Any, Any]:
        if self._helper is None:
            self._helper = _import_snapshot_owner(
                self.inputs,
                module_name=(
                    "docs.research.noncert_cuts_ab16_20260724."
                    "ab16_outer_refunit_closeout_v1"
                ),
                relative=(
                    "docs/research/noncert_cuts_ab16_20260724/"
                    "ab16_outer_refunit_closeout_v1.py"
                ),
            )
            self._store = self._helper.ReceiptStore()
        boundary = SimpleNamespace(
            campaign=Path(str(self.inputs.context["campaign_dir"])),
            context=self.campaign_context,
            formal_dir=Path(str(self.inputs.context["formal_attempt_dir"])),
            preregistration=self.preregistration,
            root=self.campaign_context["root"],
        )
        return self._helper, self._store, boundary

    def publish_arm_prelaunch_request(
        self,
        inputs: FormalInputs,
        *,
        slot: str,
        ordinal: int,
    ) -> dict[str, object]:
        helper, store, boundary = self._outer_helper()
        record = helper.build_arm_prelaunch_request(
            boundary,
            store,
            inputs.selection_identity,
            slot,
            ordinal,
        )
        path = inputs.selection["arm_prelaunch_paths"][slot]["request"]
        return store.publish(path, record, f"{slot} prelaunch request")

    def wait_for_arm_prelaunch_receipt(
        self,
        inputs: FormalInputs,
        *,
        slot: str,
        ordinal: int,
        request_identity: Mapping[str, object],
    ) -> dict[str, object]:
        helper, store, boundary = self._outer_helper()
        request_path = inputs.selection["arm_prelaunch_paths"][slot]["request"]
        request, observed_request_identity = store.document(
            request_path,
            f"{slot} prelaunch request",
        )
        if observed_request_identity != dict(request_identity):
            raise FormalControllerError(f"{slot} prelaunch request identity drifted")
        receipt_path = Path(inputs.selection["arm_prelaunch_paths"][slot]["receipt"])
        _wait_for_record(
            receipt_path,
            timeout_seconds=300.0,
            label=f"{slot} prelaunch receipt",
        )
        try:
            _receipt, receipt_identity = helper.validate_arm_prelaunch_receipt(
                boundary,
                store,
                request,
                observed_request_identity,
                receipt_path,
            )
        except Exception as exc:
            raise FormalControllerError(f"{slot} prelaunch receipt failed: {exc}") from exc
        if slot != ARM_SEQUENCE[ordinal - 1]:
            raise FormalControllerError("prelaunch receipt order drifted")
        return receipt_identity

    def run_organic_arm(
        self,
        inputs: FormalInputs,
        *,
        pre_run_path: Path,
        selection_path: Path,
    ) -> Mapping[str, object]:
        module = _import_snapshot_owner(
            inputs,
            module_name=(
                "docs.research.noncert_cuts_ab16_20260724."
                "organic_unit_orchestrator_v2"
            ),
            relative=(
                "docs/research/noncert_cuts_ab16_20260724/"
                "organic_unit_orchestrator_v2.py"
            ),
        )
        return module.run_pinned_entry(
            execution_class="FORMAL_AB16",
            pre_run_path=pre_run_path,
            selection_path=selection_path,
        )


def _baseline_paths(ports: DefaultControllerPorts, prepared: Mapping[str, object]) -> dict[str, Path]:
    baseline_dir = Path(str(prepared["baseline_dir"]))
    prospective = baseline_dir.parent
    expected = {
        "admission": Path(ports.preregistration["baseline_admission_path"]),
        "fixed_replay": Path(ports.preregistration["baseline_fixed_replay_path"]),
        "incumbent": Path(ports.preregistration["baseline_incumbent_path"]),
        "metadata": Path(ports.preregistration["baseline_rebuilt_metadata_path"]),
        "model": Path(ports.preregistration["baseline_rebuilt_model_path"]),
        "provenance": Path(ports.preregistration["baseline_campaign_provenance_path"]),
    }
    if (
        baseline_dir != prospective / "baseline"
        or expected["provenance"].parent != baseline_dir
        or any(
            not path.is_relative_to(prospective)
            for path in expected.values()
        )
    ):
        raise FormalControllerError("baseline path preregistration drifted")
    return expected


def _run_baseline_chain(
    inputs: FormalInputs,
    *,
    ports: DefaultControllerPorts,
) -> dict[str, object]:
    prepared = authority.prepare_baseline_output(inputs.context["campaign_dir"])
    if prepared.get("status") != "PROVENANCE_ONLY":
        raise FormalControllerError("baseline prestate is not PROVENANCE_ONLY")
    paths = _baseline_paths(ports, prepared)
    snapshot_root = Path(str(inputs.context["snapshot_root"]))
    ports.run_selected_role(
        inputs,
        role="baseline-rebuild",
        argv=(
            "--output-dir",
            str(paths["model"].parent),
            "--run-nonce",
            Path(str(inputs.context["campaign_dir"])).name,
            "--campaign-provenance",
            str(paths["provenance"]),
            "--candidate-placements",
            str(snapshot_root / "data/preprocessed/candidate_placements.json"),
            "--canonical-rules",
            str(snapshot_root / "rules/canonical_rules.json"),
            "--mandatory-instances",
            str(snapshot_root / "data/preprocessed/mandatory_exact_instances.json"),
        ),
        timeout_seconds=55_000.0,
    )
    ports.run_selected_role(
        inputs,
        role="cut-free-incumbent-replay",
        argv=(
            "--campaign-provenance",
            str(paths["provenance"]),
            "--model",
            str(paths["model"]),
            "--metadata",
            str(paths["metadata"]),
            "--incumbent",
            str(paths["incumbent"]),
            "--output",
            str(paths["fixed_replay"]),
            "--max-time-seconds",
            "600",
        ),
        timeout_seconds=1_200.0,
    )
    legacy = ports.campaign_context["root"]["strict_inputs"]["legacy_control_a002"]
    if _snapshot_identity(legacy["path"]) != legacy:
        raise FormalControllerError("legacy control identity drifted before baseline admission")
    ports.run_selected_role(
        inputs,
        role="baseline-admission",
        argv=(
            "--campaign-provenance",
            str(paths["provenance"]),
            "--legacy-control",
            str(legacy["path"]),
            "--rebuilt-model",
            str(paths["model"]),
            "--rebuilt-metadata",
            str(paths["metadata"]),
            "--fixed-assignment-replay",
            str(paths["fixed_replay"]),
            "--created-at-utc",
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "--output",
            str(paths["admission"]),
        ),
        timeout_seconds=600.0,
    )
    return {
        f"{name}_identity": _snapshot_identity(path)
        for name, path in paths.items()
    }


def _consume_selected_arm(
    inputs: FormalInputs,
    *,
    ports: ControllerPorts,
    slot: str,
    ordinal: int,
) -> dict[str, object]:
    candidate = authority.build_pre_run_candidate(
        inputs.context["campaign_dir"],
        slot=slot,
    )
    if candidate.get("status") != "PASS":
        raise FormalControllerError(f"{slot} pre-run candidate did not PASS")
    selected = authority.create_arm_selection(
        inputs.context["campaign_dir"],
        slot=slot,
        selection_nonce=f"formal-{ordinal:02d}-{slot}",
    )
    selection_identity = _identity(
        selected.get("arm_selection_identity"),
        f"{slot} arm selection",
    )
    pre_run_identity = _identity(
        selected.get("pre_run_authority_identity"),
        f"{slot} pre-run authority",
    )
    request_identity: dict[str, object] | None = None
    receipt_identity: dict[str, object] | None = None
    orchestration_error: BaseException | None = None
    try:
        request_identity = ports.publish_arm_prelaunch_request(
            inputs,
            slot=slot,
            ordinal=ordinal,
        )
        receipt_identity = ports.wait_for_arm_prelaunch_receipt(
            inputs,
            slot=slot,
            ordinal=ordinal,
            request_identity=request_identity,
        )
        ports.run_organic_arm(
            inputs,
            pre_run_path=Path(str(pre_run_identity["path"])),
            selection_path=Path(str(selection_identity["path"])),
        )
    except BaseException as exc:
        orchestration_error = exc
    try:
        consumed = authority.consume_arm(
            inputs.context["campaign_dir"],
            slot=slot,
        )
    except BaseException as consumption_error:
        if orchestration_error is not None:
            raise FormalControllerError(
                f"{slot} orchestration and immutable consumption both failed"
            ) from ExceptionGroup(
                f"{slot} post-selection failures",
                [orchestration_error, consumption_error],
            )
        raise FormalControllerError(f"{slot} immutable consumption failed") from consumption_error
    if orchestration_error is not None:
        raise FormalControllerError(f"{slot} selected arm failed after selection") from orchestration_error
    record = consumed.get("consumption")
    if (
        type(record) is not dict
        or record.get("outcome") != "CREDIBLE_TERMINAL"
        or consumed.get("immediate_stop_identity") is not None
    ):
        raise FormalControllerError(f"{slot} did not reach one credible terminal")
    if request_identity is None or receipt_identity is None:
        raise FormalControllerError(f"{slot} prelaunch evidence was not recorded")
    return {
        "arm_gate_identity": _identity(record["arm_gate_identity"], f"{slot} arm gate"),
        "consumption_identity": _identity(
            consumed["consumption_identity"],
            f"{slot} consumption",
        ),
        "ordinal": ordinal,
        "pre_run_authority_identity": pre_run_identity,
        "prelaunch_receipt_identity": receipt_identity,
        "prelaunch_request_identity": request_identity,
        "resource_terminal_identity": _identity(
            record["resource_terminal_identity"],
            f"{slot} resource terminal",
        ),
        "selection_identity": selection_identity,
        "slot": slot,
        "suite_terminal_identity": (
            None
            if record["suite_terminal_identity"] is None
            else _identity(record["suite_terminal_identity"], "AB16 suite terminal")
        ),
    }


def _publish_controller_result(
    inputs: FormalInputs,
    *,
    barrier_identity: Mapping[str, object],
    gate1: Mapping[str, object],
    baseline: Mapping[str, object],
    manifest_identity: Mapping[str, object],
    suite_selection_identity: Mapping[str, object],
    arms: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    if len(arms) != len(ARM_SEQUENCE):
        raise FormalControllerError("controller result lacks all sixteen arms")
    terminal_identity = arms[-1]["suite_terminal_identity"]
    if terminal_identity is None:
        raise FormalControllerError("final arm did not publish the suite terminal classification")
    result = {
        "arm_results": [dict(item) for item in arms],
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "barrier_identity": dict(barrier_identity),
        "baseline": dict(baseline),
        "campaign_root_identity": inputs.context["campaign_root_identity"],
        "formal_selection_identity": inputs.selection_identity,
        "gate1": dict(gate1),
        "manifest_identity": dict(manifest_identity),
        "package_id": inputs.context["package_id"],
        "schema_version": CONTROLLER_RESULT_SCHEMA,
        "status": "PASS",
        "suite_selection_identity": dict(suite_selection_identity),
        "terminal_classification_identity": dict(terminal_identity),
    }
    output = Path(str(inputs.context["formal_attempt_dir"])) / CONTROLLER_RESULT_NAME
    identity = authority._write_exclusive(  # noqa: SLF001 - package authority owns canonical O_EXCL
        output,
        authority.canonical_json(result),
        mode=0o444,
    )
    replay, replay_identity = _read_record(
        output,
        expected_identity=identity,
        label="formal controller result",
    )
    if replay != result or replay_identity != identity:
        raise FormalControllerError("formal controller result same-byte readback drifted")
    return result, identity


def run_controller(
    *,
    campaign_dir: Path | str,
    formal_selection: Path | str,
    ports: ControllerPorts | None = None,
) -> dict[str, object]:
    """Execute the fixed campaign sequence after the canonical barrier."""

    inputs = load_formal_inputs(
        campaign_dir=campaign_dir,
        formal_selection=formal_selection,
    )
    selected_ports = DefaultControllerPorts(inputs) if ports is None else ports
    barrier, barrier_identity = selected_ports.wait_for_barrier(inputs)
    if barrier["released"] is not True:
        raise FormalControllerError("outer barrier was not released")
    gate1 = selected_ports.run_gate1(inputs)
    baseline = selected_ports.run_baseline_chain(inputs)
    manifest = authority.build_manifest(inputs.context["campaign_dir"])
    if manifest.get("status") != "PASS":
        raise FormalControllerError("immutable organic manifest did not PASS")
    suite = authority.create_suite_selection(inputs.context["campaign_dir"])
    if suite.get("status") != "PASS":
        raise FormalControllerError("non-launching suite selection did not PASS")
    arm_results = [
        _consume_selected_arm(
            inputs,
            ports=selected_ports,
            slot=slot,
            ordinal=ordinal,
        )
        for ordinal, slot in enumerate(ARM_SEQUENCE, start=1)
    ]
    result, identity = _publish_controller_result(
        inputs,
        barrier_identity=barrier_identity,
        gate1=gate1,
        baseline=baseline,
        manifest_identity=_identity(manifest["manifest_identity"], "organic manifest"),
        suite_selection_identity=_identity(
            suite["selection_identity"],
            "organic suite selection",
        ),
        arms=arm_results,
    )
    return {
        "controller_result": result,
        "controller_result_identity": identity,
        "status": "PASS",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--formal-selection", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        result = run_controller(
            campaign_dir=arguments.campaign_dir,
            formal_selection=arguments.formal_selection,
        )
    except BaseException as exc:
        print(f"FAIL_CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(authority.canonical_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
