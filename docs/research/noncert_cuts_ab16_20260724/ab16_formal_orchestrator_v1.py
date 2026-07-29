#!/usr/bin/env python3
"""Research-only owner/supervisor coordinator for one formal AB16 attempt.

The coordinator owns no launch decision.  It keeps one externally identified
formal-launch owner alive across admission and selection, starts the
package-selected supervisor only after admission, and does not request
selection until the supervisor-published guardian-ready and attempt-consumption
records have been independently replayed.  The selected supervisor remains the
sole owner of the three formal locks and every unit lifecycle.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import sys
import threading
import time
from types import ModuleType
from typing import Any, cast

from docs.research.noncert_cuts_ab16_20260724 import ab16_authority_v2 as authority
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_campaign_bootstrap_v2 as bootstrap,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_formal_launch_validator_v1 as launch_validator,
)


AUTHORITY_SCOPE = "AB16_RESEARCH_ONLY"
REQUEST_SCHEMA = "noncert-cuts-ab16-formal-launch-owner-request-v1"
RESPONSE_SCHEMA = "noncert-cuts-ab16-formal-launch-owner-response-v1"
SESSION_ID = "formal-owner-session-a001"
PREREQUISITE_WAIT_SECONDS = 600.0
SUPERVISOR_WAIT_SECONDS = 64_800.0
POLL_SECONDS = 0.10
MAX_FRAME = 16 * 1024 * 1024
F_ADD_SEALS = 1033
F_GET_SEALS = 1034
REQUIRED_SEALS = 0x0001 | 0x0002 | 0x0004 | 0x0008
MFD_CLOEXEC = 0x0001
MFD_ALLOW_SEALING = 0x0002
CLEAN_ENV = {
    "LANG": "C",
    "LC_ALL": "C",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONNOUSERSITE": "1",
    "TZ": "UTC",
}


class FormalOrchestrationError(RuntimeError):
    """The external owner/supervisor join failed closed."""


_FORMAL_CAMPAIGN_MODULE: ModuleType | None = None


def _formal_campaign_module() -> ModuleType:
    """Import the package-pinned supervisor with its legacy local imports."""

    global _FORMAL_CAMPAIGN_MODULE
    if _FORMAL_CAMPAIGN_MODULE is not None:
        return _FORMAL_CAMPAIGN_MODULE
    research = str(Path(__file__).resolve().parent)
    sys.path.insert(0, research)
    try:
        from docs.research.noncert_cuts_ab16_20260724 import (
            ab16_formal_campaign_v1,
        )
    finally:
        sys.path.remove(research)
    _FORMAL_CAMPAIGN_MODULE = ab16_formal_campaign_v1
    return ab16_formal_campaign_v1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _message_identity(raw: bytes) -> dict[str, object]:
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _canonical_argument(value: Mapping[str, object]) -> str:
    return json.dumps(
        dict(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _process_starttime(pid: int) -> int:
    raw = Path(f"/proc/{pid}/stat").read_bytes()
    marker = raw.rfind(b") ")
    fields = raw[marker + 2 :].split() if marker >= 0 else []
    if len(fields) <= 19:
        raise FormalOrchestrationError("formal owner process identity is unreadable")
    return int(fields[19])


def _sealed_memfd(name: str, raw: bytes) -> int:
    libc = ctypes.CDLL(None, use_errno=True)
    create = libc.memfd_create
    create.argtypes = (ctypes.c_char_p, ctypes.c_uint)
    create.restype = ctypes.c_int
    descriptor = int(
        create(
            os.fsencode(name),
            MFD_CLOEXEC | MFD_ALLOW_SEALING,
        )
    )
    if descriptor < 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short memfd write")
            view = view[written:]
        os.lseek(descriptor, 0, os.SEEK_SET)
        fcntl.fcntl(descriptor, F_ADD_SEALS, REQUIRED_SEALS)
        if fcntl.fcntl(descriptor, F_GET_SEALS) & REQUIRED_SEALS != REQUIRED_SEALS:
            raise OSError("memfd seal set drifted")
        return descriptor
    except BaseException as exc:
        try:
            os.close(descriptor)
        except BaseException as cleanup_exc:
            exc.add_note(
                "sealed memfd cleanup close failed: "
                f"{type(cleanup_exc).__name__}: {cleanup_exc}"
            )
        raise


def _read_frame(control: socket.socket, label: str) -> dict[str, Any]:
    raw = control.recv(MAX_FRAME + 1)
    if not raw or len(raw) > MAX_FRAME:
        raise FormalOrchestrationError(f"{label} frame is absent or oversized")
    try:
        value = authority.strict_loads(raw, label)
    except Exception as exc:
        raise FormalOrchestrationError(f"{label} frame is invalid: {exc}") from exc
    if type(value) is not dict or authority.canonical_json(value) != raw:
        raise FormalOrchestrationError(f"{label} frame is not one canonical object")
    return value


def _send_frame(control: socket.socket, value: Mapping[str, object]) -> None:
    raw = authority.canonical_json(dict(value))
    if control.send(raw) != len(raw):
        raise FormalOrchestrationError("formal owner request send was short")


@dataclass
class OwnerSession:
    """One persistent formal-launch owner process and its control channel."""

    pid: int
    control: socket.socket
    stderr_descriptor: int
    actor: dict[str, object]
    reaped: bool = False
    control_owned: bool = True

    def _close_control_once(self) -> BaseException | None:
        if not self.control_owned:
            return None
        self.control_owned = False
        try:
            self.control.close()
        except BaseException as exc:
            return exc
        return None

    def _close_stderr_once(self) -> BaseException | None:
        if self.stderr_descriptor < 0:
            return None
        descriptor = self.stderr_descriptor
        self.stderr_descriptor = -1
        try:
            os.close(descriptor)
        except BaseException as exc:
            return exc
        return None

    def _cleanup_reap(self) -> list[BaseException]:
        errors: list[BaseException] = []
        if self.reaped:
            return errors
        try:
            os.kill(self.pid, 9)
        except ProcessLookupError:
            pass
        except BaseException as exc:
            errors.append(exc)
        while not self.reaped:
            try:
                observed, _status = os.waitpid(self.pid, 0)
                if observed == self.pid:
                    self.reaped = True
                else:
                    errors.append(
                        FormalOrchestrationError(
                            "formal owner cleanup wait returned pid "
                            f"{observed}, expected {self.pid}"
                        )
                    )
                    break
            except InterruptedError:
                continue
            except ChildProcessError:
                self.reaped = True
            except BaseException as exc:
                errors.append(exc)
                break
        return errors

    def request(
        self,
        *,
        sequence: int,
        kind: str,
        draft: Mapping[str, object],
    ) -> dict[str, Any]:
        if self.reaped or _process_starttime(self.pid) != self.actor["starttime"]:
            raise FormalOrchestrationError("formal owner actor is no longer live")
        _send_frame(
            self.control,
            {
                "draft": dict(draft),
                "kind": kind,
                "schema_version": REQUEST_SCHEMA,
                "sequence": sequence,
            },
        )
        response = _read_frame(self.control, f"formal owner {kind}")
        if (
            set(response)
            != {
                "actor",
                "artifact_identity",
                "kind",
                "schema_version",
                "sequence",
                "status",
            }
            or response["schema_version"] != RESPONSE_SCHEMA
            or response["status"] != "PUBLISHED"
            or response["sequence"] != sequence
            or response["kind"] != kind
            or response["actor"] != self.actor
        ):
            raise FormalOrchestrationError(
                f"formal owner {kind} response drifted"
            )
        return response

    def complete_handoff(self) -> None:
        waited = -1
        status = -1
        stderr = b""
        failure: BaseException | None = None
        try:
            if (
                self.reaped
                or not self.control_owned
                or _process_starttime(self.pid) != self.actor["starttime"]
            ):
                raise FormalOrchestrationError(
                    "formal owner died before selection handoff"
                )
            _send_frame(
                self.control,
                {
                    "kind": "handoff-complete",
                    "schema_version": REQUEST_SCHEMA,
                    "sequence": 3,
                },
            )
            response = _read_frame(self.control, "formal owner handoff")
            if response != {
                "actor": self.actor,
                "schema_version": RESPONSE_SCHEMA,
                "sequence": 3,
                "status": "HANDOFF_COMPLETE",
            }:
                raise FormalOrchestrationError(
                    "formal owner handoff response drifted"
                )
            control_error = self._close_control_once()
            if control_error is not None:
                raise control_error
            while True:
                try:
                    waited, status = os.waitpid(self.pid, 0)
                    self.reaped = waited == self.pid
                    break
                except InterruptedError:
                    continue
            if not self.reaped:
                raise FormalOrchestrationError(
                    "formal owner handoff wait returned a different child"
                )
            stderr = os.read(self.stderr_descriptor, MAX_FRAME + 1)
            if os.waitstatus_to_exitcode(status) != 0 or stderr:
                raise FormalOrchestrationError(
                    "formal owner handoff exit drifted: "
                    f"status={status}, stderr={stderr!r}"
                )
        except BaseException as exc:
            failure = exc
            raise
        finally:
            cleanup_errors: list[BaseException] = []
            control_error = self._close_control_once()
            if control_error is not None:
                cleanup_errors.append(control_error)
            cleanup_errors.extend(self._cleanup_reap())
            stderr_error = self._close_stderr_once()
            if stderr_error is not None:
                cleanup_errors.append(stderr_error)
            if failure is not None:
                for cleanup_error in cleanup_errors:
                    failure.add_note(
                        "formal owner handoff cleanup failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
            elif cleanup_errors:
                raise FormalOrchestrationError(
                    "formal owner handoff cleanup failed: "
                    f"{type(cleanup_errors[0]).__name__}: "
                    f"{cleanup_errors[0]}"
                ) from cleanup_errors[0]

    def close(self) -> None:
        errors: list[BaseException] = []
        control_error = self._close_control_once()
        if control_error is not None:
            errors.append(control_error)
        errors.extend(self._cleanup_reap())
        stderr_error = self._close_stderr_once()
        if stderr_error is not None:
            errors.append(stderr_error)
        if errors:
            raise FormalOrchestrationError(
                f"formal owner cleanup failed: {type(errors[0]).__name__}: "
                f"{errors[0]}"
            ) from errors[0]


def _spawn_owner(context: Mapping[str, object]) -> OwnerSession:
    driver_raw = bootstrap.FORMAL_LAUNCH_OWNER_DRIVER_V1.encode("utf-8")
    publisher_raw = bootstrap.OWNER_OEXCL_PUBLISH_V1.encode("utf-8")
    driver_identity = _message_identity(driver_raw)
    publisher_identity = _message_identity(publisher_raw)
    if (
        context["formal_launch_owner_driver_identity"] != driver_identity
        or context["mechanical_oexcl_publisher_identity"] != publisher_identity
    ):
        raise FormalOrchestrationError(
            "formal owner literal identities differ from campaign context"
        )
    context_raw = authority.canonical_json(dict(context))
    context_identity = _message_identity(context_raw)
    campaign_module = _formal_campaign_module()
    selected = campaign_module._selected_identities(  # type: ignore[attr-defined]  # noqa: SLF001
        context["outer_spec"]
    )
    owned_descriptors: set[int] = set()
    owned_sockets: set[socket.socket] = set()
    parent: socket.socket | None = None
    child: socket.socket | None = None
    stderr_read = -1
    stderr_write = -1
    pid: int | None = None

    def own_descriptor(descriptor: int) -> int:
        owned_descriptors.add(descriptor)
        return descriptor

    def close_descriptor(descriptor: int) -> BaseException | None:
        if descriptor in owned_descriptors:
            # Remove before close: after an exceptional close the numeric FD
            # may already be reusable, so a retry could close an unrelated FD.
            owned_descriptors.remove(descriptor)
            try:
                os.close(descriptor)
            except BaseException as exc:
                return exc
        return None

    def close_socket(value: socket.socket) -> BaseException | None:
        if value in owned_sockets:
            owned_sockets.remove(value)
            try:
                value.close()
            except BaseException as exc:
                return exc
        return None

    def close_descriptors(values: Sequence[int]) -> BaseException | None:
        first_error: BaseException | None = None
        for descriptor in values:
            error = close_descriptor(descriptor)
            if first_error is None and error is not None:
                first_error = error
        return first_error

    def close_sockets(values: Sequence[socket.socket]) -> BaseException | None:
        first_error: BaseException | None = None
        for value in values:
            error = close_socket(value)
            if first_error is None and error is not None:
                first_error = error
        return first_error

    failure: BaseException | None = None
    try:
        descriptors = {
            3: own_descriptor(
                campaign_module._open_selected(  # type: ignore[attr-defined]  # noqa: SLF001
                    selected["python"],
                    "formal owner Python",
                )
            ),
            4: own_descriptor(
                _sealed_memfd("ab16-formal-owner-publisher", publisher_raw)
            ),
            5: own_descriptor(
                _sealed_memfd("ab16-formal-owner-context", context_raw)
            ),
        }
        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        owned_sockets.update((parent, child))
        parent.settimeout(PREREQUISITE_WAIT_SECONDS)
        stderr_read, stderr_write = os.pipe2(os.O_CLOEXEC)
        own_descriptor(stderr_read)
        own_descriptor(stderr_write)
        high = {
            target: own_descriptor(
                fcntl.fcntl(source, fcntl.F_DUPFD_CLOEXEC, 32)
            )
            for target, source in {
                **descriptors,
                6: child.fileno(),
            }.items()
        }
        actions: list[tuple[Any, ...]] = [
            *(
                (os.POSIX_SPAWN_DUP2, high[target], target)
                for target in (3, 4, 5, 6)
            ),
            (os.POSIX_SPAWN_DUP2, stderr_write, 2),
            (os.POSIX_SPAWN_CLOSE, stderr_read),
        ]
        pid = os.posix_spawn(
            "/proc/self/fd/3",
            [
                str(selected["python"]["path"]),
                "-I",
                "-B",
                "-c",
                bootstrap.FORMAL_LAUNCH_OWNER_DRIVER_V1,
                SESSION_ID,
                _canonical_argument(context_identity),
                _canonical_argument(driver_identity),
            ],
            CLEAN_ENV,
            file_actions=actions,
        )
        cleanup_error = close_descriptors(tuple(high.values()))
        socket_error = close_socket(child)
        stderr_error = close_descriptor(stderr_write)
        selected_error = close_descriptors(tuple(descriptors.values()))
        for error in (
            cleanup_error,
            socket_error,
            stderr_error,
            selected_error,
        ):
            if error is not None:
                raise error
        ready = _read_frame(parent, "formal owner ready")
        actor = ready.get("actor")
        if (
            set(ready) != {"actor", "schema_version", "status"}
            or ready["schema_version"] != RESPONSE_SCHEMA
            or ready["status"] != "READY"
            or type(actor) is not dict
            or actor
            != {
                "pid": pid,
                "role": launch_validator.OWNER_PUBLISHER_ROLE,
                "session_id": SESSION_ID,
                "starttime": _process_starttime(pid),
            }
        ):
            raise FormalOrchestrationError(
                "formal owner ready identity drifted"
            )
        owned_sockets.remove(parent)
        owned_descriptors.remove(stderr_read)
        return OwnerSession(
            pid=pid,
            control=parent,
            stderr_descriptor=stderr_read,
            actor=dict(actor),
        )
    except BaseException as exc:
        failure = exc
        if pid is not None:
            try:
                os.kill(pid, 15)
            except ProcessLookupError:
                pass
            except BaseException:
                pass
            while True:
                try:
                    observed, _status = os.waitpid(pid, 0)
                    if observed != pid:
                        exc.add_note(
                            "formal owner cleanup wait returned pid "
                            f"{observed}, expected {pid}"
                        )
                    break
                except InterruptedError:
                    continue
                except ChildProcessError:
                    break
                except BaseException as cleanup_exc:
                    exc.add_note(
                        "formal owner cleanup wait failed: "
                        f"{type(cleanup_exc).__name__}: {cleanup_exc}"
                    )
                    break
        raise
    finally:
        socket_cleanup_error = close_sockets(tuple(owned_sockets))
        descriptor_cleanup_error = close_descriptors(
            tuple(owned_descriptors)
        )
        cleanup_error = socket_cleanup_error or descriptor_cleanup_error
        if failure is None and cleanup_error is not None:
            raise cleanup_error


def _publisher(
    context: Mapping[str, object],
    actor: Mapping[str, object],
    *,
    kind: str,
) -> dict[str, object]:
    output = str(
        context[
            "formal_admission_path"
            if kind == "admission"
            else "formal_selection_path"
        ]
    )
    prerequisites = (
        []
        if kind == "admission"
        else [
            "--admission",
            str(context["formal_admission_path"]),
            "--guardian-ready",
            str(context["guardian_ready_path"]),
            "--attempt-consumption",
            str(Path(str(context["formal_attempt_dir"])) / "attempt-consumption.json"),
        ]
    )
    return {
        "actor": dict(actor),
        "argv": {
            "mechanical_publish": [
                "OWNER_OEXCL_PUBLISH_V1",
                Path(output).name,
            ],
            "render": [
                "formal-launch-authority",
                "--campaign-dir",
                str(context["campaign_dir"]),
                "--draft",
                launch_validator.OWNER_MEMFD_PATH,
                "--kind",
                kind,
                *prerequisites,
            ],
            "validate": [
                "formal-launch-validator",
                "--campaign-dir",
                str(context["campaign_dir"]),
                "--candidate",
                launch_validator.OWNER_MEMFD_PATH,
                "--kind",
                kind,
                *prerequisites,
            ],
        },
        "execution_strategy": launch_validator.OWNER_EXECUTION_STRATEGY,
        "formal_launch_owner_driver_identity": context[
            "formal_launch_owner_driver_identity"
        ],
        "mechanical_oexcl_publisher_identity": context[
            "mechanical_oexcl_publisher_identity"
        ],
        "output_mode": 0o444,
        "output_path": output,
        "python_identity": context["python_identity"],
        "renderer_identity": context["launch_renderer_identity"],
        "validator_identity": context["launch_validator_identity"],
    }


def build_admission_draft(
    context: Mapping[str, object],
    actor: Mapping[str, object],
) -> dict[str, object]:
    draft = {
        "admission_id": "formal-admission-a001",
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(launch_validator.FALSE_CLAIMS),
        "baseline_launch_authorized": False,
        "campaign_dir": context["campaign_dir"],
        "campaign_root_identity": context["campaign_root_identity"],
        "controller_launch_authorized": False,
        "created_at_utc": _utc_now(),
        "formal_attempt_dir": context["formal_attempt_dir"],
        "formal_attempt_selected": False,
        "formal_selection_path": context["formal_selection_path"],
        "formal_selection_publication_authorized": True,
        "gate_b_approval_identity": context["gate_b_approval_identity"],
        "gate_b_epoch_observation_identity": context[
            "gate_b_epoch_observation_identity"
        ],
        "guardian_control_socket_path": context["guardian_control_socket_path"],
        "guardian_launch_authorized": True,
        "guardian_ready_path": context["guardian_ready_path"],
        "guardian_spec": context["guardian_spec"],
        "manager_epoch": context["manager_epoch"],
        "manager_epoch_observation_identity": context[
            "manager_epoch_observation_identity"
        ],
        "outer_launch_authorized": False,
        "package_id": context["package_id"],
        "package_manifest_identity": context["package_manifest_identity"],
        "package_seal_identity": context["package_seal_identity"],
        "publication_path": context["formal_admission_path"],
        "publisher": _publisher(context, actor, kind="admission"),
        "repository_head": context["repository_head"],
        "schema_version": launch_validator.FORMAL_ADMISSION_SCHEMA,
        "snapshot_materialization_identity": context[
            "snapshot_materialization_identity"
        ],
        "snapshot_root": context["snapshot_root"],
        "status": "ADMITTED",
    }
    return launch_validator.validate_admission(
        draft,
        expected_context=context,
    )


def build_selection_draft(
    context: Mapping[str, object],
    actor: Mapping[str, object],
    *,
    admission: Mapping[str, object],
    admission_identity: Mapping[str, object],
    guardian_ready: Mapping[str, object],
    guardian_ready_identity: Mapping[str, object],
    attempt_consumption: Mapping[str, object],
    attempt_consumption_identity: Mapping[str, object],
) -> dict[str, object]:
    outer_spec = cast(Mapping[str, object], context["outer_spec"])
    draft = {
        "arm_prelaunch_paths": outer_spec["arm_prelaunch_paths"],
        "attempt_consumption_identity": dict(attempt_consumption_identity),
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(launch_validator.FALSE_CLAIMS),
        "baseline_identity": context["baseline_identity"],
        "baseline_launch_authorized": True,
        "campaign_dir": context["campaign_dir"],
        "campaign_root_identity": context["campaign_root_identity"],
        "child_audit_path": outer_spec["child_audit_path"],
        "consumed": True,
        "controller_identity": context["controller_identity"],
        "controller_launch_authorized": True,
        "created_at_utc": _utc_now(),
        "formal_admission_identity": dict(admission_identity),
        "formal_attempt_dir": context["formal_attempt_dir"],
        "formal_attempt_selected": True,
        "gate1_prelaunch_ownership_path": outer_spec[
            "gate1_prelaunch_ownership_path"
        ],
        "gate1_selection_identity": context["gate1_selection_identity"],
        "gate_b_approval_identity": context["gate_b_approval_identity"],
        "gate_b_epoch_observation_identity": context[
            "gate_b_epoch_observation_identity"
        ],
        "guardian_ready_identity": dict(guardian_ready_identity),
        "guardian_runtime_identity": guardian_ready["guardian_runtime_identity"],
        "guardian_spec": context["guardian_spec"],
        "guardian_unit_identity": guardian_ready["guardian_unit_identity"],
        "lock_identities": guardian_ready["lock_identities"],
        "manager_epoch": context["manager_epoch"],
        "manager_epoch_observation_identity": context[
            "manager_epoch_observation_identity"
        ],
        "outer_launch_authorized": True,
        "outer_spec": context["outer_spec"],
        "package_id": context["package_id"],
        "package_manifest_identity": context["package_manifest_identity"],
        "package_seal_identity": context["package_seal_identity"],
        "publication_path": context["formal_selection_path"],
        "publisher": _publisher(context, actor, kind="selection"),
        "repository_head": context["repository_head"],
        "retry_eligible": False,
        "schema_version": launch_validator.FORMAL_SELECTION_SCHEMA,
        "selection_id": "formal-selection-a001",
        "snapshot_materialization_identity": context[
            "snapshot_materialization_identity"
        ],
        "snapshot_root": context["snapshot_root"],
        "status": "SELECTED",
    }
    return launch_validator.validate_selection(
        draft,
        admission=admission,
        admission_identity=admission_identity,
        guardian_ready=guardian_ready,
        guardian_ready_identity=guardian_ready_identity,
        attempt_consumption=attempt_consumption,
        attempt_consumption_identity=attempt_consumption_identity,
        expected_context=context,
    )


def _wait_record(
    path: Path,
    label: str,
    *,
    owner: OwnerSession,
    supervisor_alive: Callable[[], bool],
) -> tuple[dict[str, Any], dict[str, object]]:
    deadline = time.monotonic() + PREREQUISITE_WAIT_SECONDS
    while time.monotonic() <= deadline:
        if _process_starttime(owner.pid) != owner.actor["starttime"]:
            raise FormalOrchestrationError(
                f"formal owner died while waiting for {label}"
            )
        if not supervisor_alive():
            raise FormalOrchestrationError(
                f"formal supervisor exited before {label}"
            )
        try:
            observed = os.lstat(path)
        except FileNotFoundError:
            time.sleep(POLL_SECONDS)
            continue
        except OSError as exc:
            raise FormalOrchestrationError(
                f"{label} surface could not be inspected"
            ) from exc
        observed_mode = stat.S_IMODE(observed.st_mode)
        if stat.S_ISREG(observed.st_mode) and observed_mode == 0o444:
            return launch_validator.read_canonical_record(
                path,
                expected_identity=None,
                label=label,
            )
        if stat.S_ISREG(observed.st_mode) and observed_mode == 0o600:
            time.sleep(POLL_SECONDS)
            continue
        raise FormalOrchestrationError(
            f"{label} is not one completed readonly regular file"
        )
    raise FormalOrchestrationError(f"{label} did not appear before deadline")


def _verify_selected_self(context: Mapping[str, object]) -> None:
    """Require this executing module to be the loader-selected snapshot byte."""

    snapshot = authority.snapshot_regular(Path(__file__).resolve())
    actual = authority.detached_identity(snapshot)
    expected = launch_validator.validate_detached_identity(
        context["formal_orchestrator_identity"],
        "formal orchestrator selected identity",
    )
    actual_path = Path(str(actual["path"]))
    snapshot_root = Path(str(context["snapshot_root"]))
    if (
        actual["sha256"] != expected["sha256"]
        or actual["size_bytes"] != expected["size_bytes"]
        or not actual_path.is_relative_to(snapshot_root)
    ):
        raise FormalOrchestrationError(
            "formal orchestrator is not the package-selected snapshot byte"
        )


def orchestrate(campaign_dir: Path | str) -> dict[str, object]:
    """Run one fixed admission-to-selection-to-supervisor lifecycle."""

    campaign = Path(campaign_dir).absolute()
    context = launch_validator.replay_formal_launch_context(authority, campaign)
    _verify_selected_self(context)
    owner = _spawn_owner(context)
    supervisor_result: dict[str, object] = {}
    supervisor_error: list[BaseException] = []
    supervisor_returncode: list[int] = []
    supervisor_done = threading.Event()
    supervisor_cancel = threading.Event()

    def run_supervisor() -> None:
        try:
            campaign_module = _formal_campaign_module()
            selected_result = campaign_module.run_selected_direct_result(  # type: ignore[attr-defined]
                context=context,
                role="formal-supervisor",
                role_argv=("--campaign-dir", str(campaign)),
                timeout_seconds=SUPERVISOR_WAIT_SECONDS,
                cancel_requested=supervisor_cancel.is_set,
            )
            if (
                selected_result.returncode not in {0, 2}
                or selected_result.stderr
            ):
                raise FormalOrchestrationError(
                    "formal supervisor exit contract drifted: "
                    f"exit={selected_result.returncode}, "
                    f"stderr={selected_result.stderr!r}"
                )
            value = authority.strict_loads(
                selected_result.stdout,
                "formal supervisor output",
            )
            canonical = authority.canonical_json(value)
            if type(value) is not dict or selected_result.stdout not in {
                canonical,
                canonical + b"\n",
            }:
                raise FormalOrchestrationError(
                    "formal supervisor output is not canonical"
                )
            supervisor_result.update(value)
            supervisor_returncode.append(selected_result.returncode)
        except BaseException as exc:
            supervisor_error.append(exc)
        finally:
            supervisor_done.set()

    supervisor_thread: threading.Thread | None = None
    failure: BaseException | None = None
    try:
        admission_draft = build_admission_draft(context, owner.actor)
        admission_response = owner.request(
            sequence=1,
            kind="admission",
            draft=admission_draft,
        )
        admission, admission_identity = launch_validator.read_canonical_record(
            str(context["formal_admission_path"]),
            expected_identity=admission_response["artifact_identity"],
            label="formal launch admission",
        )
        launch_validator.validate_admission(
            admission,
            expected_context=context,
        )

        supervisor_thread = threading.Thread(
            target=run_supervisor,
            name="ab16-formal-supervisor",
            daemon=False,
        )
        supervisor_thread.start()

        def supervisor_alive() -> bool:
            return not supervisor_done.is_set()

        guardian, guardian_identity = _wait_record(
            Path(str(context["guardian_ready_path"])),
            "outer guardian ready",
            owner=owner,
            supervisor_alive=supervisor_alive,
        )
        attempt, attempt_identity = _wait_record(
            Path(str(context["formal_attempt_dir"])) / "attempt-consumption.json",
            "formal attempt consumption",
            owner=owner,
            supervisor_alive=supervisor_alive,
        )
        selection_draft = build_selection_draft(
            context,
            owner.actor,
            admission=admission,
            admission_identity=admission_identity,
            guardian_ready=guardian,
            guardian_ready_identity=guardian_identity,
            attempt_consumption=attempt,
            attempt_consumption_identity=attempt_identity,
        )
        selection_response = owner.request(
            sequence=2,
            kind="selection",
            draft=selection_draft,
        )
        selection, selection_identity = launch_validator.read_canonical_record(
            str(context["formal_selection_path"]),
            expected_identity=selection_response["artifact_identity"],
            label="formal launch selection",
        )
        launch_validator.validate_selection(
            selection,
            admission=admission,
            admission_identity=admission_identity,
            guardian_ready=guardian,
            guardian_ready_identity=guardian_identity,
            attempt_consumption=attempt,
            attempt_consumption_identity=attempt_identity,
            expected_context=context,
        )
        supervisor_thread.join(SUPERVISOR_WAIT_SECONDS)
        if supervisor_thread.is_alive():
            raise FormalOrchestrationError(
                "formal supervisor outlived its fixed orchestration deadline"
            )
        if supervisor_error:
            raise FormalOrchestrationError(
                f"formal supervisor failed: {supervisor_error[0]}"
            ) from supervisor_error[0]
        outcome = supervisor_result.get("outcome")
        expected_returncode = 0 if outcome == "VERIFIED" else 2
        if (
            outcome not in {"VERIFIED", "INCOMPLETE"}
            or supervisor_returncode != [expected_returncode]
            or supervisor_result.get("formal_selection_identity")
            != selection_identity
        ):
            raise FormalOrchestrationError(
                "formal supervisor result did not join the selected campaign"
            )
        # The supervisor independently replays the selection publisher's
        # PID/starttime before activating the guardian and formal units.  Keep
        # the same owner actor live until that complete supervisor lifecycle
        # has returned; local selection replay is not a consumption ack.
        owner.complete_handoff()
        return {
            "admission_identity": admission_identity,
            "authority_scope": AUTHORITY_SCOPE,
            "formal_selection_identity": selection_identity,
            "owner_actor": owner.actor,
            "owner_handoff_complete": True,
            "status": outcome,
            "supervisor_result": supervisor_result,
        }
    except BaseException as exc:
        failure = exc
        raise
    finally:
        cleanup_error: BaseException | None = None
        if supervisor_thread is not None and supervisor_thread.is_alive():
            supervisor_cancel.set()
            supervisor_thread.join(PREREQUISITE_WAIT_SECONDS)
            if supervisor_thread.is_alive():
                cleanup_error = FormalOrchestrationError(
                    "formal supervisor did not stop after coordinator cancellation"
                )
        if not owner.reaped:
            try:
                owner.close()
            except BaseException as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        if failure is None and cleanup_error is not None:
            raise cleanup_error


def launch_selected(campaign_dir: Path | str) -> dict[str, object]:
    """Enter the orchestrator only through the existing selected-byte loader."""

    campaign = Path(campaign_dir).absolute()
    context = launch_validator.replay_formal_launch_context(authority, campaign)
    campaign_module = _formal_campaign_module()
    selected_result = campaign_module.run_selected_direct_result(  # type: ignore[attr-defined]
        context=context,
        role="formal-orchestrator",
        role_argv=("--selected", "--campaign-dir", str(campaign)),
        timeout_seconds=SUPERVISOR_WAIT_SECONDS + PREREQUISITE_WAIT_SECONDS,
    )
    if (
        selected_result.returncode not in {0, 2}
        or selected_result.stderr
    ):
        raise FormalOrchestrationError(
            "selected formal orchestrator exit contract drifted: "
            f"exit={selected_result.returncode}, "
            f"stderr={selected_result.stderr!r}"
        )
    value = authority.strict_loads(
        selected_result.stdout,
        "selected formal orchestrator output",
    )
    canonical = authority.canonical_json(value)
    expected_status = "VERIFIED" if selected_result.returncode == 0 else "INCOMPLETE"
    if (
        type(value) is not dict
        or selected_result.stdout != canonical
        or value.get("status") != expected_status
        or value.get("authority_scope") != AUTHORITY_SCOPE
    ):
        raise FormalOrchestrationError(
            "selected formal orchestrator result contract drifted"
        )
    return dict(value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", required=True, type=Path)
    parser.add_argument("--selected", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        result = (
            orchestrate(arguments.campaign_dir)
            if arguments.selected
            else launch_selected(arguments.campaign_dir)
        )
    except BaseException as exc:
        print(
            f"FAIL_CLOSED: {type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )
        return 125
    sys.stdout.buffer.write(authority.canonical_json(result))
    sys.stdout.buffer.flush()
    return 0 if result["status"] == "VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
