#!/usr/bin/env python3
"""Record and finalize AB16 Gate A without authorizing Gate B.

The ``record-preflight`` command first replays a completed disposable drill,
then runs the repository's package-pinned full preflight and writes immutable
stdout, stderr, and receipt files.  The ``finalize`` command independently
replays those bytes, the live manager/boot epoch, repository HEAD, planned
sources, and the complete resource/terminal chain before publishing one
non-authorizing Gate-A receipt.

Neither command creates a formal campaign, solver selection, or organic arm.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
import errno
import hashlib
import importlib.machinery
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
from typing import Any


RESEARCH_DIR = Path(__file__).resolve().parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

import ab16_campaign_bootstrap_v2 as bootstrap  # noqa: E402
import ab16_resource_admission_v1 as resource_admission  # noqa: E402
import disposable_drill_authority_v2 as drill_authority  # noqa: E402
import organic_resource_verifier_v2 as verifier  # noqa: E402


PREFLIGHT_SCHEMA = "noncert-cuts-ab16-gate-a-full-preflight-receipt-v7"
GATE_A_SCHEMA = "noncert-cuts-ab16-bootstrap-gate-a-receipt-v3"
PREFLIGHT_PURPOSE = "AB16_GATE_A_FULL_PREFLIGHT"
GATE_A_PURPOSE = "AB16_OFFLINE_SOURCE_SET_PREFLIGHT"
PREFLIGHT_EXECUTION_STRATEGY = "same-fd-subreaper-ab16-qualification-runner-v4"
RUN_NONCE_RE = re.compile(r"run-[A-Za-z0-9][A-Za-z0-9._-]{4,123}\Z")
APPROVAL_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{5,127}\Z")
TIMEOUT_SCALE = "12"
PREFLIGHT_TIMEOUT_SECONDS = 60 * 60
PREFLIGHT_SCRATCH_BASENAME = "pytest-scratch"
PREFLIGHT_BASETEMP_BASENAME = "basetemp"
PREFLIGHT_SCRATCH_POLICY = "fresh-no-overwrite-repo-local-retained-closed-tree-v1"
PREFLIGHT_SCRATCH_CLOSURE_FAILURE_EXIT_CODE = 125
PREFLIGHT_PUBLICATION_COMMIT_SCHEMA = "noncert-cuts-ab16-gate-a-preflight-publication-commit-v2"
PYTEST_COLLECTION_STAGE_SCHEMA = "ab16-pytest-collection-stage-v1"
PYTEST_COLLECTION_TERMINAL_SCHEMA = "ab16-pytest-collection-terminal-v1"
PYTEST_COLLECTION_BINDING_SCHEMA = "noncert-cuts-ab16-pytest-collection-binding-v1"
PYTEST_COLLECTION_STDOUT_PREFIX = b"AB16_PYTEST_COLLECTION_RECORD="
PYTEST_COLLECTION_MANIFEST_DOMAIN = b"ab16-pytest-nodeid-path-manifest-v1\0"
TOOL_SOURCE_ROLE = "script.gate_a_validation_v2"
PREFLIGHT_SOURCE_ROLE = "input.preflight_gate"
QUALIFICATION_SOURCE_ROLE = "script.ab16_preflight_qualification_v1"
COLLECTION_PROTOCOL_SOURCE_ROLE = "script.ab16_pytest_collection_protocol_v1"
COLLECTION_PLUGIN_SOURCE_ROLE = "script.ab16_pytest_collection_plugin_v1"
RESOURCE_ADMISSION_SOURCE_ROLE = "script.ab16_resource_admission_v1"

_SCRIPT_LOADER = r"""
import ctypes
import errno
import hashlib
import os
import signal
import stat
import sys
import time
import traceback
python_fd = int(sys.argv[1])
script_fd = int(sys.argv[2])
python_path = sys.argv[3]
python_mode = int(sys.argv[4])
python_size = int(sys.argv[5])
python_sha256 = sys.argv[6]
source_path = sys.argv[7]
script_mode = int(sys.argv[8])
script_size = int(sys.argv[9])
script_sha256 = sys.argv[10]
forwarded = sys.argv[11:]
PR_SET_CHILD_SUBREAPER = 36
DESCENDANT_CLEANUP_SECONDS = 10.0

def snapshot_fd(fd, expected_mode, expected_size, expected_sha256, label):
    before = os.fstat(fd)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or stat.S_IMODE(before.st_mode) != expected_mode
    ):
        raise RuntimeError(label + " descriptor metadata drifted")
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    chunks = []
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        chunks.append(chunk)
    after = os.fstat(fd)
    before_signature = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_nlink,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_signature = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_nlink,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    raw = b"".join(chunks)
    if (
        before_signature != after_signature
        or len(raw) != expected_size
        or digest.hexdigest() != expected_sha256
    ):
        raise RuntimeError(label + " descriptor identity drifted")
    return raw

def direct_children():
    os.lseek(children_fd, 0, os.SEEK_SET)
    raw_children = os.read(children_fd, 1 << 20)
    if os.read(children_fd, 1):
        raise RuntimeError("selected preflight child set exceeds the fixed limit")
    raw_children = raw_children.strip()
    if not raw_children:
        return []
    return [int(value) for value in raw_children.split()]

def reap_exited_children_until_blocked():
    while True:
        try:
            child, _status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return True
        except OSError as exc:
            if exc.errno == errno.ECHILD:
                return True
            raise
        if child == 0:
            return False

def kill_one_child(child):
    pidfd = None
    uncertain = False
    try:
        pidfd = pidfd_open(child)
    except ProcessLookupError:
        return uncertain
    except OSError:
        uncertain = True
    if pidfd is not None:
        try:
            pidfd_send_signal(pidfd, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            uncertain = True
            try:
                os.kill(child, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError:
                uncertain = True
    else:
        # The PID is still a direct, unreaped child.  It therefore cannot be
        # reused between the children observation and this fallback signal.
        try:
            os.kill(child, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            uncertain = True
    if pidfd is not None:
        try:
            os.close(pidfd)
        except OSError:
            uncertain = True
    return uncertain

def terminate_descendants():
    deadline = time.monotonic() + DESCENDANT_CLEANUP_SECONDS
    observed = set()
    uncertain = False
    while True:
        try:
            # This is the sole descendant-closure proof.  A zero result means
            # at least one child remains alive; procfs is consulted only to
            # discover signal targets and can never authorize this return.
            if reap_exited_children_until_blocked():
                return len(observed), uncertain
        except OSError:
            uncertain = True
            time.sleep(0.01)
            continue
        try:
            children = direct_children()
        except (OSError, RuntimeError, ValueError):
            uncertain = True
            time.sleep(0.01)
            continue
        if children:
            observed.update(children)
            for child in children:
                uncertain = kill_one_child(child) or uncertain
        if time.monotonic() >= deadline:
            uncertain = True
            deadline = time.monotonic() + DESCENDANT_CLEANUP_SECONDS
            print(
                "selected preflight descendants remain live; cleanup continues fail-stop",
                file=sys.stderr,
            )
        time.sleep(0.01)

def selected_main():
    snapshot_fd(
        python_fd,
        python_mode,
        python_size,
        python_sha256,
        "Python",
    )
    raw = snapshot_fd(
        script_fd,
        script_mode,
        script_size,
        script_sha256,
        "script",
    )
    fd_executable = "/proc/{}/fd/{}".format(os.getpid(), python_fd)
    if (
        not os.path.isabs(python_path)
        or not os.path.exists(fd_executable)
        or not os.path.samefile(fd_executable, python_path)
    ):
        raise RuntimeError("Python descriptor/path join drifted")
    sys.executable = fd_executable
    sys._base_executable = fd_executable
    sys.argv = [source_path, *forwarded]
    scope = {
        "__builtins__": __builtins__,
        "__cached__": None,
        "__doc__": None,
        "__file__": source_path,
        "__loader__": None,
        "__name__": "__main__",
        "__package__": None,
        "__spec__": None,
    }
    exec(compile(raw, source_path, "exec", dont_inherit=True), scope, scope)

def worker_exit_code():
    try:
        selected_main()
    except SystemExit as exc:
        if exc.code is None:
            return 0
        if isinstance(exc.code, int):
            return exc.code & 255
        print(exc.code, file=sys.stderr)
        return 1
    except BaseException:
        traceback.print_exc()
        return 1
    return 0

if not sys.platform.startswith("linux"):
    raise RuntimeError("selected preflight subreaper requires Linux")
libc = ctypes.CDLL(None, use_errno=True)
native_pidfd_open = getattr(os, "pidfd_open", None)
native_pidfd_send_signal = getattr(signal, "pidfd_send_signal", None)
libc_pidfd_open = getattr(libc, "pidfd_open", None)
libc_pidfd_send_signal = getattr(libc, "pidfd_send_signal", None)
if callable(native_pidfd_open) != callable(native_pidfd_send_signal):
    raise RuntimeError("selected preflight requires a complete Python pidfd API")
if not callable(native_pidfd_open):
    if libc_pidfd_open is None or libc_pidfd_send_signal is None:
        raise RuntimeError("selected preflight requires public pidfd APIs")
    libc_pidfd_open.argtypes = (ctypes.c_int, ctypes.c_uint)
    libc_pidfd_open.restype = ctypes.c_int
    libc_pidfd_send_signal.argtypes = (
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint,
    )
    libc_pidfd_send_signal.restype = ctypes.c_int

def pidfd_open(pid):
    if callable(native_pidfd_open):
        return native_pidfd_open(pid, 0)
    descriptor = libc_pidfd_open(pid, 0)
    if descriptor >= 0:
        return descriptor
    error_number = ctypes.get_errno()
    if error_number == errno.ESRCH:
        raise ProcessLookupError(error_number, os.strerror(error_number))
    raise OSError(error_number, os.strerror(error_number))

def pidfd_send_signal(descriptor, signum):
    if callable(native_pidfd_send_signal):
        native_pidfd_send_signal(descriptor, signum)
        return
    if libc_pidfd_send_signal(descriptor, signum, None, 0) == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.ESRCH:
        raise ProcessLookupError(error_number, os.strerror(error_number))
    raise OSError(error_number, os.strerror(error_number))

if libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) != 0:
    error_number = ctypes.get_errno()
    raise OSError(error_number, os.strerror(error_number))
children_fd = os.open(
    "/proc/{}/task/{}/children".format(os.getpid(), os.getpid()),
    os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
)

class SupervisorTermination(BaseException):
    def __init__(self, signum):
        self.signum = signum

def terminate_supervisor(signum, _frame):
    raise SupervisorTermination(signum)

def ignore_termination_signals():
    blocked = {signal.SIGTERM, signal.SIGINT}
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, blocked)
    try:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)

signal.signal(signal.SIGTERM, terminate_supervisor)
signal.signal(signal.SIGINT, terminate_supervisor)
worker = None
try:
    worker = os.fork()
    if worker == 0:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        os.close(children_fd)
        exit_code = worker_exit_code()
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        finally:
            os._exit(exit_code)
    _waited, worker_status = os.waitpid(worker, 0)
    ignore_termination_signals()
    observed_descendants, cleanup_uncertain = terminate_descendants()
except SupervisorTermination as exc:
    ignore_termination_signals()
    try:
        _observed_descendants, _cleanup_uncertain = terminate_descendants()
        os.close(children_fd)
    except BaseException:
        traceback.print_exc()
        os._exit(125)
    os._exit(128 + exc.signum)
except BaseException:
    ignore_termination_signals()
    traceback.print_exc()
    try:
        terminate_descendants()
        os.close(children_fd)
    except BaseException:
        traceback.print_exc()
    os._exit(125)

try:
    os.close(children_fd)
except OSError:
    cleanup_uncertain = True
worker_exit = os.waitstatus_to_exitcode(worker_status)
if worker_exit < 0:
    worker_exit = 128 - worker_exit
if observed_descendants or cleanup_uncertain:
    print(
        "selected preflight observed {} descendant(s) or cleanup uncertainty".format(
            observed_descendants
        ),
        file=sys.stderr,
    )
    worker_exit = 125
os._exit(worker_exit)
""".strip()


def _loader_identity() -> dict[str, object]:
    raw = _SCRIPT_LOADER.encode("utf-8")
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


class GateAValidationError(RuntimeError):
    """Gate A evidence is absent, stale, malformed, or non-PASS."""


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _identity(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != {
        "mode",
        "path",
        "sha256",
        "size_bytes",
    }:
        raise GateAValidationError(f"{label} identity key set drifted")
    record = value
    if (
        type(record["mode"]) is not int
        or type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["sha256"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
    ):
        raise GateAValidationError(f"{label} identity is malformed")
    return dict(record)


def _snapshot_identity(path: Path | str) -> dict[str, object]:
    _raw, identity = verifier.snapshot_bytes(_absolute(path))
    return identity


def _same_identity(
    observed: Mapping[str, Any],
    expected: object,
    label: str,
) -> None:
    if dict(observed) != _identity(expected, label):
        raise GateAValidationError(f"{label} byte identity drifted")


def _planned_source_identity(
    sources: Mapping[str, Mapping[str, Any]],
    role: str,
    label: str,
) -> dict[str, object]:
    identity = sources.get(role)
    if type(identity) is not dict:
        raise GateAValidationError(f"{label} is absent from the planned source set")
    try:
        projected = {
            field: identity[field]
            for field in ("mode", "path", "sha256", "size_bytes")
        }
    except KeyError as exc:
        raise GateAValidationError(f"{label} identity is incomplete") from exc
    return _identity(projected, label)


def _validate_authority_ready(
    value: object,
    *,
    planned_source_set_digest: str,
    pre_run_identity: Mapping[str, Any],
    run_nonce: str,
    selection_identity: Mapping[str, Any],
) -> Mapping[str, Any]:
    expected_keys = {
        "authorizations",
        "disposable_drill_ready",
        "formal_campaign_created",
        "planned_source_set_digest",
        "pre_run_authority_identity",
        "purpose",
        "run_nonce",
        "schema_version",
        "selection_identity",
        "status",
    }
    if not isinstance(value, Mapping) or set(value) != expected_keys:
        raise GateAValidationError("authority-ready key set drifted")
    if (
        value["authorizations"]
        != {
            "arm_launch_authorized": False,
            "formal_campaign_creation_authorized": False,
            "solver_run_authorized": False,
        }
        or value["disposable_drill_ready"] is not True
        or value["formal_campaign_created"] is not False
        or value["planned_source_set_digest"] != planned_source_set_digest
        or value["pre_run_authority_identity"] != pre_run_identity
        or value["purpose"] != drill_authority.RESULT_PURPOSE
        or value["run_nonce"] != run_nonce
        or value["schema_version"] != drill_authority.RESULT_SCHEMA
        or value["selection_identity"] != selection_identity
        or value["status"] != "PASS"
    ):
        raise GateAValidationError("authority-ready semantics drifted")
    return value


def _mkdir_exclusive(path: Path) -> None:
    absolute = _absolute(path)
    try:
        absolute.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise GateAValidationError(f"no-overwrite directory already exists: {absolute}") from exc


def _verified_session_bus_environment() -> dict[str, str]:
    uid = os.getuid()
    if os.geteuid() != uid:
        raise GateAValidationError("preflight environment requires matching real/effective uid")
    runtime_path = Path(f"/run/user/{uid}")
    descriptor: int | None = None
    try:
        descriptor = os.open(
            runtime_path,
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise GateAValidationError("fixed session runtime directory open failed") from exc
    try:
        before = os.fstat(descriptor)
        bus = os.stat("bus", dir_fd=descriptor, follow_symlinks=False)
        after = os.fstat(descriptor)
        if (
            (
                before.st_dev,
                before.st_ino,
                before.st_mode,
                before.st_uid,
                before.st_gid,
                before.st_nlink,
            )
            != (
                after.st_dev,
                after.st_ino,
                after.st_mode,
                after.st_uid,
                after.st_gid,
                after.st_nlink,
            )
            or not stat.S_ISDIR(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o700
            or before.st_uid != uid
            or not stat.S_ISSOCK(bus.st_mode)
            or bus.st_uid != uid
            or bus.st_nlink != 1
            or bus.st_dev != before.st_dev
        ):
            raise GateAValidationError("fixed per-user session bus node failed validation")
    except FileNotFoundError:
        try:
            os.close(descriptor)
        except OSError as exc:
            raise GateAValidationError("fixed session runtime directory close failed") from exc
        return {}
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    try:
        os.close(descriptor)
    except OSError as exc:
        raise GateAValidationError("fixed session runtime directory close failed") from exc
    return {
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={runtime_path / 'bus'}",
        "XDG_RUNTIME_DIR": str(runtime_path),
    }


def _preflight_environment() -> dict[str, str]:
    environment = {
        "LANG": "C",
        "LC_ALL": "C",
        "PREFLIGHT_TIMEOUT_SCALE": TIMEOUT_SCALE,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "TZ": "UTC",
    }
    environment.update(_verified_session_bus_environment())
    return environment


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW


def _open_directory_no_symlinks(path: Path) -> int:
    absolute = _absolute(path)
    descriptor: int | None = None
    try:
        descriptor = os.open("/", _directory_flags())
        for component in absolute.parts[1:]:
            following = os.open(
                component,
                _directory_flags(),
                dir_fd=descriptor,
            )
            try:
                os.close(descriptor)
            except BaseException as exc:
                try:
                    os.close(following)
                except OSError as close_error:
                    exc.add_note(
                        "directory-chain cleanup failed: "
                        f"{type(close_error).__name__}: {close_error}"
                    )
                raise
            descriptor = following
        return descriptor
    except BaseException as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as close_error:
                exc.add_note(
                    "directory-chain cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise


def _scratch_directory_identity(descriptor: int) -> dict[str, int]:
    try:
        metadata = os.fstat(descriptor)
    except OSError as exc:
        raise GateAValidationError("preflight scratch identity read failed") from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o700
        or metadata.st_uid != os.geteuid()
    ):
        raise GateAValidationError("preflight scratch directory metadata drifted")
    return {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode": stat.S_IMODE(metadata.st_mode),
        "uid": metadata.st_uid,
    }


def _same_scratch_identity(
    descriptor: int,
    expected: Mapping[str, int],
) -> bool:
    return _scratch_directory_identity(descriptor) == dict(expected)


def _directory_binding_signature(descriptor: int) -> tuple[int, ...]:
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        raise GateAValidationError("retained preflight node is no longer a directory")
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_gid,
    )


def _require_directory_join(
    path: Path,
    *,
    descriptor: int,
    label: str,
) -> None:
    joined = _open_directory_no_symlinks(path)
    try:
        if _directory_binding_signature(joined) != _directory_binding_signature(descriptor):
            raise GateAValidationError(f"{label} absolute topology drifted")
    except BaseException as exc:
        try:
            os.close(joined)
        except OSError as close_error:
            exc.add_note(
                f"{label} join cleanup failed: "
                f"{type(close_error).__name__}: {close_error}"
            )
        raise
    try:
        os.close(joined)
    except OSError as exc:
        raise GateAValidationError(f"{label} join cleanup failed") from exc


def _create_preflight_output_and_scratch(
    *,
    repository: Path,
    output: Path,
) -> tuple[int, int, dict[str, int], dict[str, int]]:
    if output == repository or repository not in output.parents:
        raise GateAValidationError("preflight output must be a repository-local child")
    parent_descriptor: int | None = None
    output_descriptor: int | None = None
    scratch_descriptor: int | None = None
    try:
        parent_descriptor = _open_directory_no_symlinks(output.parent)
        try:
            os.mkdir(output.name, mode=0o700, dir_fd=parent_descriptor)
        except FileExistsError as exc:
            raise GateAValidationError(f"no-overwrite directory already exists: {output}") from exc
        output_descriptor = os.open(
            output.name,
            _directory_flags(),
            dir_fd=parent_descriptor,
        )
        os.fchmod(output_descriptor, 0o700)
        output_named = os.stat(
            output.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        output_open = os.fstat(output_descriptor)
        if (
            not stat.S_ISDIR(output_named.st_mode)
            or (output_named.st_dev, output_named.st_ino)
            != (output_open.st_dev, output_open.st_ino)
        ):
            raise GateAValidationError("preflight output identity drifted during creation")
        output_identity = _scratch_directory_identity(output_descriptor)
        os.mkdir(
            PREFLIGHT_SCRATCH_BASENAME,
            mode=0o700,
            dir_fd=output_descriptor,
        )
        scratch_descriptor = os.open(
            PREFLIGHT_SCRATCH_BASENAME,
            _directory_flags(),
            dir_fd=output_descriptor,
        )
        os.fchmod(scratch_descriptor, 0o700)
        scratch_named = os.stat(
            PREFLIGHT_SCRATCH_BASENAME,
            dir_fd=output_descriptor,
            follow_symlinks=False,
        )
        scratch_open = os.fstat(scratch_descriptor)
        if (
            not stat.S_ISDIR(scratch_named.st_mode)
            or (scratch_named.st_dev, scratch_named.st_ino)
            != (scratch_open.st_dev, scratch_open.st_ino)
        ):
            raise GateAValidationError("preflight scratch identity drifted during creation")
        identity = _scratch_directory_identity(scratch_descriptor)
    except BaseException as exc:
        for descriptor in (scratch_descriptor, output_descriptor, parent_descriptor):
            if descriptor is None:
                continue
            try:
                os.close(descriptor)
            except OSError as close_error:
                exc.add_note(
                    "preflight directory cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise
    try:
        os.close(parent_descriptor)
    except OSError as exc:
        for descriptor in (scratch_descriptor, output_descriptor):
            try:
                os.close(descriptor)
            except OSError as close_error:
                exc.add_note(
                    "preflight directory cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise GateAValidationError("preflight output parent close failed") from exc
    return output_descriptor, scratch_descriptor, output_identity, identity


def _observe_closed_preflight_scratch(
    path: Path,
    *,
    descriptor: int,
    initial_identity: Mapping[str, int],
) -> dict[str, int]:
    if not _same_scratch_identity(descriptor, initial_identity):
        raise GateAValidationError("preflight scratch root identity drifted before closure")
    basetemp_descriptor: int | None = None
    try:
        _require_directory_join(
            path,
            descriptor=descriptor,
            label="preflight scratch",
        )
        with os.scandir(descriptor) as iterator:
            entries = list(iterator)
        if len(entries) != 1 or entries[0].name != PREFLIGHT_BASETEMP_BASENAME:
            raise GateAValidationError("preflight scratch closed tree has unexpected entries")
        named = entries[0].stat(follow_symlinks=False)
        if not stat.S_ISDIR(named.st_mode):
            raise GateAValidationError("preflight basetemp is not a directory")
        basetemp_descriptor = os.open(
            PREFLIGHT_BASETEMP_BASENAME,
            _directory_flags(),
            dir_fd=descriptor,
        )
        opened = os.fstat(basetemp_descriptor)
        if (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino):
            raise GateAValidationError("preflight basetemp identity drifted during closure")
        basetemp_identity = _scratch_directory_identity(basetemp_descriptor)
        with os.scandir(basetemp_descriptor) as iterator:
            if next(iterator, None) is not None:
                raise GateAValidationError("preflight basetemp is not empty after PASS")
        if not _same_scratch_identity(descriptor, initial_identity):
            raise GateAValidationError("preflight scratch root identity drifted during closure")
    except BaseException as exc:
        if basetemp_descriptor is not None:
            try:
                os.close(basetemp_descriptor)
            except OSError as close_error:
                exc.add_note(
                    "preflight basetemp cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise
    try:
        os.close(basetemp_descriptor)
    except OSError as exc:
        raise GateAValidationError("preflight basetemp descriptor close failed") from exc
    return basetemp_identity


def _write_exclusive_at(
    directory_descriptor: int,
    *,
    absolute_path: Path,
    raw: bytes,
    mode: int,
) -> dict[str, object]:
    descriptor: int | None = None
    try:
        descriptor = os.open(
            absolute_path.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            mode,
            dir_fd=directory_descriptor,
        )
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                raise GateAValidationError(f"short write: {absolute_path}")
            offset += written
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
        opened = os.fstat(descriptor)
        named = os.stat(
            absolute_path.name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) != mode
            or opened.st_size != len(raw)
            or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise GateAValidationError(f"output identity drifted during write: {absolute_path}")
    except BaseException as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as close_error:
                exc.add_note(
                    "preflight output cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise
    try:
        os.close(descriptor)
    except OSError as exc:
        raise GateAValidationError(f"output descriptor close failed: {absolute_path}") from exc
    os.fsync(directory_descriptor)
    return {
        "path": str(absolute_path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _recheck_exclusive_at(
    directory_descriptor: int,
    *,
    absolute_path: Path,
    expected: Mapping[str, object],
) -> None:
    descriptor: int | None = None
    try:
        descriptor = os.open(
            absolute_path.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directory_descriptor,
        )
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise GateAValidationError(f"preflight output type drifted: {absolute_path}")
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(descriptor)
        named = os.stat(
            absolute_path.name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        signature_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if (
            any(getattr(before, field) != getattr(after, field) for field in signature_fields)
            or (named.st_dev, named.st_ino) != (after.st_dev, after.st_ino)
            or stat.S_IMODE(after.st_mode) != expected.get("mode")
            or expected.get("path") != str(absolute_path)
            or expected.get("sha256") != digest.hexdigest()
            or expected.get("size_bytes") != size
        ):
            raise GateAValidationError(f"preflight output identity drifted: {absolute_path}")
    except BaseException as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as close_error:
                exc.add_note(
                    "preflight output cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise
    try:
        os.close(descriptor)
    except OSError as exc:
        raise GateAValidationError(f"output descriptor close failed: {absolute_path}") from exc


def _promote_preflight_publication_commit(
    path: Path,
    *,
    directory_descriptor: int,
    expected_directory_identity: Mapping[str, int],
    expected_identity: Mapping[str, object],
) -> None:
    """Consume one retained output-root FD and commit its staged marker.

    The forked child is the sole process allowed to promote the marker.  The
    parent must first close its commit and output-root descriptors; therefore a
    close failure cannot be followed by a successful producer return.
    """

    owned_directory_descriptor: int | None = directory_descriptor
    commit_descriptor: int | None = None
    read_pipe: int | None = None
    write_pipe: int | None = None
    child: int | None = None
    try:
        if not _same_scratch_identity(
            owned_directory_descriptor,
            expected_directory_identity,
        ):
            raise GateAValidationError("preflight publication output-root identity drifted")
        _require_directory_join(
            path.parent,
            descriptor=owned_directory_descriptor,
            label="preflight publication output",
        )
        commit_descriptor = os.open(
            path.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=owned_directory_descriptor,
        )
        before = os.fstat(commit_descriptor)
        named = os.stat(
            path.name,
            dir_fd=owned_directory_descriptor,
            follow_symlinks=False,
        )
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(commit_descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(commit_descriptor)
        signature_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if (
            any(getattr(before, field) != getattr(after, field) for field in signature_fields)
            or not stat.S_ISREG(after.st_mode)
            or after.st_nlink != 1
            or stat.S_IMODE(after.st_mode) != 0o600
            or (named.st_dev, named.st_ino) != (after.st_dev, after.st_ino)
            or expected_identity.get("path") != str(path)
            or expected_identity.get("sha256") != digest.hexdigest()
            or expected_identity.get("size_bytes") != size
        ):
            raise GateAValidationError("preflight publication commit staging identity drifted")
        read_pipe, write_pipe = os.pipe2(os.O_CLOEXEC)
        child = os.fork()
        if child == 0:
            try:
                os.close(write_pipe)
                token = os.read(read_pipe, 1)
                if token != b"G":
                    os._exit(126)
                os.close(read_pipe)
                os.fsync(commit_descriptor)
                os.fsync(owned_directory_descriptor)
                os.close(owned_directory_descriptor)
                # This is the sole publication linearization syscall.  No
                # fallible validation or explicit close follows it; process
                # exit releases the read-only descriptor.
                os.fchmod(commit_descriptor, 0o444)
            except BaseException:
                os._exit(125)
            os._exit(0)
        descriptor_to_close = read_pipe
        read_pipe = None
        os.close(descriptor_to_close)
        descriptor_to_close = commit_descriptor
        commit_descriptor = None
        os.close(descriptor_to_close)
        descriptor_to_close = owned_directory_descriptor
        owned_directory_descriptor = None
        os.close(descriptor_to_close)
        if os.write(write_pipe, b"G") != 1:
            raise GateAValidationError("preflight publication commit promotion signal failed")
        descriptor_to_close = write_pipe
        write_pipe = None
        try:
            os.close(descriptor_to_close)
        except OSError:
            # Linux releases the descriptor even when close reports a
            # post-close error.  The commit signal is already irrevocable, so
            # this transport cleanup cannot retroactively invalidate it.
            pass
        waited: int | None = None
        status: int | None = None
        while True:
            try:
                waited, status = os.waitpid(child, 0)
                break
            except InterruptedError:
                continue
            except ChildProcessError:
                # A successfully promoted marker is reconciled by the caller's
                # complete absolute-path self-replay.  If it is still staged,
                # that replay fails closed.
                break
            except OSError:
                # After G, returning an uncommitted error can contradict an
                # already-linearized 0444 marker.  Retry fail-stop until the
                # exact child can be reaped.
                time.sleep(0.01)
                continue
        child = None
        if waited is not None and (
            waited <= 0
            or status is None
            or os.waitstatus_to_exitcode(status) != 0
        ):
            observed = os.stat(path, follow_symlinks=False)
            if not stat.S_ISREG(observed.st_mode) or stat.S_IMODE(observed.st_mode) != 0o444:
                raise GateAValidationError("preflight publication commit promotion failed")
    except BaseException as exc:
        if child is not None:
            try:
                os.kill(child, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(child, 0)
            except (ChildProcessError, OSError) as wait_error:
                exc.add_note(
                    "preflight commit child cleanup failed: "
                    f"{type(wait_error).__name__}: {wait_error}"
                )
        for descriptor in (
            write_pipe,
            read_pipe,
            commit_descriptor,
            owned_directory_descriptor,
        ):
            if descriptor is None:
                continue
            try:
                os.close(descriptor)
            except OSError as close_error:
                exc.add_note(
                    "preflight commit cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise


def _planned_sources(authority_root: Path) -> tuple[dict[str, Any], str]:
    path = authority_root / "authority/planned-source-identities.json"
    snapshot = verifier.snapshot_json(path)
    value = snapshot.value
    if set(value) != {
        "planned_source_identities",
        "planned_source_set_digest",
        "purpose",
        "schema_version",
    }:
        raise GateAValidationError("planned-source authority key set drifted")
    sources = value["planned_source_identities"]
    digest = value["planned_source_set_digest"]
    if type(sources) is not dict or type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise GateAValidationError("planned-source authority is malformed")
    return dict(sources), digest


_PytestSurface = dict[str, tuple[str, str, str]]
_PYTEST_GOVERNANCE_PATH = "data/repository_governance/code_assets.json"


def _pytest_import_suffixes() -> tuple[str, ...]:
    suffixes = {
        *importlib.machinery.SOURCE_SUFFIXES,
        *importlib.machinery.BYTECODE_SUFFIXES,
        *importlib.machinery.EXTENSION_SUFFIXES,
    }
    if any(
        not suffix.startswith(".")
        or "/" in suffix
        or "\\" in suffix
        or "\0" in suffix
        for suffix in suffixes
    ):
        raise GateAValidationError("Python import suffix set is unsafe")
    return tuple(sorted(suffixes, key=lambda value: (-len(value), value)))


def _pytest_import_file_candidate(
    parts: tuple[str, ...],
    *,
    import_suffixes: Sequence[str],
) -> bool:
    if not parts or any(not component.isidentifier() for component in parts[:-1]):
        return False
    name = parts[-1]
    if name.endswith(".pyc"):
        return len(name) > len(".pyc")
    return any(
        name.endswith(suffix)
        and name[: -len(suffix)].isidentifier()
        for suffix in import_suffixes
    )


def _expected_pytest_surface(tree: bytes) -> _PytestSurface:
    expected: _PytestSurface = {}
    import_suffixes = _pytest_import_suffixes()
    try:
        for raw_entry in tree.split(b"\0"):
            if not raw_entry:
                continue
            metadata, raw_path = raw_entry.split(b"\t", 1)
            mode, kind, oid = metadata.decode("ascii").split(" ", 2)
            relative = raw_path.decode("utf-8")
            path = Path(relative)
            parts = path.parts
            if (
                path.is_absolute()
                or "\\" in relative
                or any(part in {"", ".", ".."} for part in parts)
                or re.fullmatch(r"[0-9a-f]{40}", oid) is None
            ):
                raise GateAValidationError("pytest HEAD surface member is unsafe")
            in_discovery = parts[:2] == ("src", "tests")
            fixed_file = relative in {"pytest.ini", _PYTEST_GOVERNANCE_PATH}
            import_file = _pytest_import_file_candidate(
                parts,
                import_suffixes=import_suffixes,
            )
            package_alias = all(part.isidentifier() for part in parts) and (
                kind != "blob" or mode == "120000"
            )
            if package_alias:
                raise GateAValidationError("pytest HEAD import surface contains an alias")
            if fixed_file or in_discovery or import_file:
                if kind != "blob" or mode not in {"100644", "100755"}:
                    raise GateAValidationError("pytest HEAD surface contains a non-regular member")
                expected[relative] = ("file", mode, oid)
            if in_discovery:
                for index in range(2, len(parts)):
                    expected["/".join(parts[:index])] = ("directory", "", "")
            for index in range(1, len(parts)):
                prefix = parts[:index]
                if not all(part.isidentifier() for part in prefix):
                    break
                expected["/".join(prefix)] = ("directory", "", "")
    except (UnicodeDecodeError, ValueError) as exc:
        raise GateAValidationError("pytest HEAD surface listing is malformed") from exc
    if expected.get("pytest.ini", ("", "", ""))[0] != "file":
        raise GateAValidationError("pytest configuration is absent from HEAD")
    conftests = {
        path
        for path, identity in expected.items()
        if identity[0] == "file"
        and path.startswith("src/tests/")
        and path.endswith("/conftest.py")
    }
    if conftests != {"src/tests/conftest.py"}:
        raise GateAValidationError("pytest conftest authority set drifted")
    if expected.get("src/tests", ("", "", ""))[0] != "directory":
        raise GateAValidationError("pytest discovery root is absent from HEAD")
    return expected


def _git_blob_identity(descriptor: int) -> tuple[str, str]:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise GateAValidationError("pytest surface member is not one regular file")
    digest = hashlib.sha1(usedforsecurity=False)
    digest.update(f"blob {before.st_size}\0".encode("ascii"))
    size = 0
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
    after = os.fstat(descriptor)
    signature = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_nlink,
        before.st_uid,
        before.st_gid,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    if (
        signature
        != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_uid,
            after.st_gid,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        or size != before.st_size
    ):
        raise GateAValidationError("pytest surface member changed during snapshot")
    mode = "100755" if stat.S_IMODE(before.st_mode) & 0o111 else "100644"
    return mode, digest.hexdigest()


def _observe_pytest_surface(repository: Path) -> _PytestSurface:
    observed: _PytestSurface = {}
    import_suffixes = _pytest_import_suffixes()

    def snapshot_file(
        descriptor: int,
        *,
        name: str,
        relative: str,
        metadata: os.stat_result,
    ) -> None:
        if not stat.S_ISREG(metadata.st_mode):
            observed[relative] = ("unsafe", "", "")
            return
        file_descriptor: int | None = None
        try:
            try:
                file_descriptor = os.open(
                    name,
                    os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
                opened = os.fstat(file_descriptor)
                if (
                    opened.st_dev,
                    opened.st_ino,
                    opened.st_mode,
                    opened.st_uid,
                    opened.st_gid,
                ) != (
                    metadata.st_dev,
                    metadata.st_ino,
                    metadata.st_mode,
                    metadata.st_uid,
                    metadata.st_gid,
                ):
                    raise GateAValidationError(
                        f"pytest surface member changed before snapshot: {relative}"
                    )
                mode, oid = _git_blob_identity(file_descriptor)
                observed[relative] = ("file", mode, oid)
            except OSError as exc:
                raise GateAValidationError(
                    f"pytest surface file cannot be opened: {relative}"
                ) from exc
        except BaseException as primary:
            if file_descriptor is not None:
                try:
                    os.close(file_descriptor)
                except OSError as close_error:
                    primary.add_note(
                        "pytest surface file cleanup failed: "
                        f"{type(close_error).__name__}: {close_error}"
                    )
            raise
        try:
            os.close(file_descriptor)
        except OSError as exc:
            raise GateAValidationError(
                f"pytest surface file cannot be closed: {relative}"
            ) from exc

    def walk(
        descriptor: int,
        prefix: tuple[str, ...],
        *,
        in_discovery: bool,
    ) -> None:
        try:
            with os.scandir(descriptor) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name)
        except OSError as exc:
            raise GateAValidationError("pytest surface directory scan failed") from exc
        for entry in entries:
            parts = (*prefix, entry.name)
            relative = "/".join(parts)
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise GateAValidationError(
                    f"pytest surface member cannot be observed: {relative}"
                ) from exc
            if stat.S_ISDIR(metadata.st_mode):
                child_in_discovery = in_discovery or parts[:2] == ("src", "tests")
                identifier_directory = all(part.isidentifier() for part in parts)
                if not child_in_discovery and not identifier_directory:
                    continue
                observed[relative] = ("directory", "", "")
                child: int | None = None
                try:
                    try:
                        child = os.open(
                            entry.name,
                            _directory_flags(),
                            dir_fd=descriptor,
                        )
                        opened = os.fstat(child)
                        if (
                            opened.st_dev,
                            opened.st_ino,
                            opened.st_mode,
                            opened.st_uid,
                            opened.st_gid,
                        ) != (
                            metadata.st_dev,
                            metadata.st_ino,
                            metadata.st_mode,
                            metadata.st_uid,
                            metadata.st_gid,
                        ):
                            raise GateAValidationError(
                                f"pytest surface directory changed before snapshot: {relative}"
                            )
                        walk(
                            child,
                            parts,
                            in_discovery=child_in_discovery,
                        )
                        final = os.fstat(child)
                        if (
                            final.st_dev,
                            final.st_ino,
                            final.st_mode,
                            final.st_uid,
                            final.st_gid,
                            final.st_mtime_ns,
                            final.st_ctime_ns,
                        ) != (
                            opened.st_dev,
                            opened.st_ino,
                            opened.st_mode,
                            opened.st_uid,
                            opened.st_gid,
                            opened.st_mtime_ns,
                            opened.st_ctime_ns,
                        ):
                            raise GateAValidationError(
                                f"pytest surface directory changed during snapshot: {relative}"
                            )
                    except OSError as exc:
                        raise GateAValidationError(
                            f"pytest surface directory cannot be opened: {relative}"
                        ) from exc
                except BaseException as primary:
                    if child is not None:
                        try:
                            os.close(child)
                        except OSError as close_error:
                            primary.add_note(
                                "pytest surface directory cleanup failed: "
                                f"{type(close_error).__name__}: {close_error}"
                            )
                    raise
                try:
                    os.close(child)
                except OSError as exc:
                    raise GateAValidationError(
                        f"pytest surface directory cannot be closed: {relative}"
                    ) from exc
                continue
            fixed_file = relative in {"pytest.ini", _PYTEST_GOVERNANCE_PATH}
            import_file = _pytest_import_file_candidate(
                parts,
                import_suffixes=import_suffixes,
            )
            package_alias = (
                all(part.isidentifier() for part in parts)
                and not stat.S_ISREG(metadata.st_mode)
            )
            if in_discovery or fixed_file or import_file or package_alias:
                snapshot_file(
                    descriptor,
                    name=entry.name,
                    relative=relative,
                    metadata=metadata,
                )

    root_descriptor: int | None = None
    try:
        root_descriptor = _open_directory_no_symlinks(repository)
        initial = os.fstat(root_descriptor)
        walk(root_descriptor, (), in_discovery=False)
        final = os.fstat(root_descriptor)
        if (
            final.st_dev,
            final.st_ino,
            final.st_mode,
            final.st_uid,
            final.st_gid,
            final.st_mtime_ns,
            final.st_ctime_ns,
        ) != (
            initial.st_dev,
            initial.st_ino,
            initial.st_mode,
            initial.st_uid,
            initial.st_gid,
            initial.st_mtime_ns,
            initial.st_ctime_ns,
        ):
            raise GateAValidationError("pytest repository root changed during snapshot")
    except BaseException as primary:
        if root_descriptor is not None:
            try:
                os.close(root_descriptor)
            except OSError as close_error:
                primary.add_note(
                    "pytest surface directory cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise
    try:
        os.close(root_descriptor)
    except OSError as exc:
        raise GateAValidationError("pytest surface directory cannot be closed") from exc
    return observed


def _pytest_git_join(
    *,
    repository: Path,
    git_identity: Mapping[str, Any],
) -> str:
    try:
        status = drill_authority._run_history_git(  # noqa: SLF001
            repository_root=repository,
            git_identity=git_identity,
            arguments=(
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--",
                ".",
                ":(exclude).artifacts/**",
            ),
        )
        head_raw = drill_authority._run_history_git(  # noqa: SLF001
            repository_root=repository,
            git_identity=git_identity,
            arguments=("rev-parse", "--verify", "HEAD^{commit}"),
        )
        head = head_raw.decode("ascii").strip()
    except Exception as exc:
        raise GateAValidationError("pytest repository Git join failed closed") from exc
    if status or re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise GateAValidationError("pytest repository is not one clean committed HEAD")
    return head


class _PytestSurfaceGuard:
    def __init__(
        self,
        *,
        repository: Path,
        git_identity: Mapping[str, Any],
        expected_head: str,
        expected_surface: _PytestSurface,
    ) -> None:
        self._repository = repository
        self._git_identity = dict(git_identity)
        self._expected_head = expected_head
        self._expected_surface = dict(expected_surface)
        self._closed = False

    def verify_and_close(self) -> None:
        if self._closed:
            raise GateAValidationError("pytest surface guard is already closed")
        try:
            if _pytest_git_join(
                repository=self._repository,
                git_identity=self._git_identity,
            ) != self._expected_head:
                raise GateAValidationError("pytest repository HEAD drifted across execution")
            if _observe_pytest_surface(self._repository) != self._expected_surface:
                raise GateAValidationError("pytest discovery surface drifted across execution")
        finally:
            self._closed = True

    def abort(self, _primary: BaseException) -> None:
        self._closed = True


def _verify_pytest_repository_surface(
    *,
    repository: Path,
    sources: Mapping[str, Mapping[str, Any]],
) -> _PytestSurfaceGuard:
    git_identity = sources.get("system.git")
    if type(git_identity) is not dict:
        raise GateAValidationError("planned Git identity is absent from preflight source closure")
    try:
        tree = drill_authority._run_history_git(  # noqa: SLF001
            repository_root=repository,
            git_identity=git_identity,
            arguments=(
                "ls-tree",
                "-rz",
                "--full-tree",
                "HEAD",
            ),
            output_limit=256 << 20,
        )
    except Exception as exc:
        raise GateAValidationError("pytest repository surface observation failed closed") from exc
    expected_head = _pytest_git_join(
        repository=repository,
        git_identity=git_identity,
    )
    expected_surface = _expected_pytest_surface(tree)
    if _observe_pytest_surface(repository) != expected_surface:
        raise GateAValidationError("pytest discovery surface differs from HEAD")
    return _PytestSurfaceGuard(
        repository=repository,
        git_identity=git_identity,
        expected_head=expected_head,
        expected_surface=expected_surface,
    )


def _collection_pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise GateAValidationError(f"pytest collection record duplicates {key!r}")
        result[key] = value
    return result


def _reject_collection_number(token: str) -> object:
    raise GateAValidationError(f"pytest collection record contains forbidden number {token!r}")


def _strict_collection_line(raw: bytes, label: str) -> dict[str, object]:
    if (
        type(raw) is not bytes
        or not raw.endswith(b"\n")
        or b"\n" in raw[:-1]
        or b"\r" in raw
    ):
        raise GateAValidationError(f"{label} is not one canonical line")
    try:
        value = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=_collection_pairs,
            parse_float=_reject_collection_number,
            parse_constant=_reject_collection_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateAValidationError(f"{label} is malformed") from exc
    canonical = (
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")
    if type(value) is not dict or canonical != raw:
        raise GateAValidationError(f"{label} is not canonical")
    return value


def _collection_manifest_sha256(items: object) -> str:
    canonical = json.dumps(
        items,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(PYTEST_COLLECTION_MANIFEST_DOMAIN + canonical).hexdigest()


def _safe_repository_relative(value: str) -> bool:
    path = Path(value)
    return (
        bool(value)
        and not path.is_absolute()
        and "\\" not in value
        and all(ord(character) >= 32 and ord(character) != 127 for character in value)
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _validate_collection_origins(
    value: object,
    *,
    label: str,
) -> list[dict[str, str]]:
    """Validate canonical diagnostic records without granting import authority."""

    if type(value) is not list:
        raise GateAValidationError(f"{label} is not a list")
    records: list[dict[str, str]] = []
    previous: tuple[str, str, str, str] | None = None
    for item in value:
        if type(item) is not dict or set(item) != {
            "kind",
            "module",
            "path",
            "resolved_path",
        }:
            raise GateAValidationError(f"{label} record shape drifted")
        if any(type(item[field]) is not str or not item[field] for field in item):
            raise GateAValidationError(f"{label} record is malformed")
        key = (
            item["module"],
            item["kind"],
            item["path"],
            item["resolved_path"],
        )
        if previous is not None and key <= previous:
            raise GateAValidationError(f"{label} is not strictly sorted and unique")
        previous = key
        if (
            item["kind"] not in {"file", "package_path"}
            or any(
                ord(character) < 32 or ord(character) == 127
                for field in item
                for character in item[field]
            )
        ):
            raise GateAValidationError(f"{label} contains an unsafe scalar")
        records.append(dict(item))
    return records


def _pytest_collection_projection(
    stdout: bytes,
    *,
    expected_count: int | None = None,
    expected_sha256: str | None = None,
    tracked_files: set[str] | None = None,
) -> dict[str, object]:
    records = [
        line.removeprefix(PYTEST_COLLECTION_STDOUT_PREFIX)
        for line in stdout.splitlines(keepends=True)
        if line.startswith(PYTEST_COLLECTION_STDOUT_PREFIX)
    ]
    if len(records) != 2:
        raise GateAValidationError("pytest collection stdout must contain exactly two records")
    stage_raw, terminal_raw = records
    stage = _strict_collection_line(stage_raw, "pytest collection stage")
    terminal = _strict_collection_line(terminal_raw, "pytest collection terminal")
    if set(stage) != {
        "collection_count",
        "collection_sha256",
        "expected_count",
        "expected_sha256",
        "items",
        "manifest_sha256",
        "markexpr",
        "module_origins",
        "nonce",
        "schema_version",
        "workflow",
    } or set(terminal) != {
        "exitstatus",
        "module_origins",
        "nonce",
        "schema_version",
        "stage_sha256",
    }:
        raise GateAValidationError("pytest collection record key set drifted")
    items = stage["items"]
    if type(items) is not list:
        raise GateAValidationError("pytest collection items are malformed")
    normalized: list[tuple[str, str]] = []
    for item in items:
        if type(item) is not dict or set(item) != {"nodeid", "path"}:
            raise GateAValidationError("pytest collection item shape drifted")
        nodeid = item["nodeid"]
        path = item["path"]
        if (
            type(nodeid) is not str
            or type(path) is not str
            or not _safe_repository_relative(path)
            or not path.startswith("src/tests/")
            or any(ord(character) < 32 or ord(character) == 127 for character in nodeid)
            or not (nodeid == path or nodeid.startswith(path + "::"))
        ):
            raise GateAValidationError("pytest collection item is unsafe")
        normalized.append((nodeid, path))
    if normalized != sorted(normalized) or len({item[0] for item in normalized}) != len(normalized):
        raise GateAValidationError("pytest collection items are not strictly sorted and unique")
    nodeids_raw = ("\n".join(item[0] for item in normalized) + "\n").encode()
    observed_sha256 = hashlib.sha256(nodeids_raw).hexdigest()
    stage_origins = _validate_collection_origins(
        stage["module_origins"],
        label="pytest collection-stage module origins",
    )
    terminal_origins = _validate_collection_origins(
        terminal["module_origins"],
        label="pytest terminal module origins",
    )
    if (
        type(stage["collection_count"]) is not int
        or stage["collection_count"] <= 0
        or type(stage["collection_sha256"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", stage["collection_sha256"]) is None
        or type(stage["manifest_sha256"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", stage["manifest_sha256"]) is None
        or type(stage["expected_count"]) is not int
        or stage["expected_count"] <= 0
        or type(stage["expected_sha256"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", stage["expected_sha256"]) is None
        or type(stage["nonce"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", stage["nonce"]) is None
        or type(terminal["nonce"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", terminal["nonce"]) is None
        or type(terminal["exitstatus"]) is not int
        or terminal["exitstatus"] != 0
        or type(terminal["stage_sha256"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", terminal["stage_sha256"]) is None
        or stage["schema_version"] != PYTEST_COLLECTION_STAGE_SCHEMA
        or terminal["schema_version"] != PYTEST_COLLECTION_TERMINAL_SCHEMA
        or stage["nonce"] != terminal["nonce"]
        or stage["workflow"] != "full"
        or stage["markexpr"] != "not slow"
        or stage["collection_count"] != len(normalized)
        or stage["collection_sha256"] != observed_sha256
        or stage["manifest_sha256"] != _collection_manifest_sha256(items)
        or stage["expected_count"] != len(normalized)
        or stage["expected_sha256"] != observed_sha256
        or terminal["stage_sha256"] != hashlib.sha256(stage_raw).hexdigest()
    ):
        raise GateAValidationError("pytest collection records do not close one exact PASS")
    if expected_count is not None or expected_sha256 is not None:
        if (
            type(expected_count) is not int
            or type(expected_sha256) is not str
            or stage["expected_count"] != expected_count
            or stage["expected_sha256"] != expected_sha256
        ):
            raise GateAValidationError("pytest collection differs from committed expectation")
    if tracked_files is not None and any(path not in tracked_files for _nodeid, path in normalized):
        raise GateAValidationError("pytest collection contains a non-HEAD test path")
    return {
        "collection_count": len(normalized),
        "collection_sha256": observed_sha256,
        "manifest_sha256": _collection_manifest_sha256(items),
        "markexpr": "not slow",
        "schema_version": PYTEST_COLLECTION_BINDING_SCHEMA,
        "stage_module_origin_count": len(stage_origins),
        "stage_sha256": hashlib.sha256(stage_raw).hexdigest(),
        "terminal_module_origin_count": len(terminal_origins),
        "terminal_sha256": hashlib.sha256(terminal_raw).hexdigest(),
        "workflow": "full",
    }


def _head_pytest_collection_authority(
    *,
    repository: Path,
    sources: Mapping[str, Mapping[str, Any]],
) -> tuple[int, str, set[str]]:
    git_identity = sources.get("system.git")
    if type(git_identity) is not dict:
        raise GateAValidationError("planned Git identity is absent from collection replay")
    try:
        governance_raw = drill_authority._run_history_git(  # noqa: SLF001
            repository_root=repository,
            git_identity=git_identity,
            arguments=("show", f"HEAD:{_PYTEST_GOVERNANCE_PATH}"),
            output_limit=16 << 20,
        )
        tree = drill_authority._run_history_git(  # noqa: SLF001
            repository_root=repository,
            git_identity=git_identity,
            arguments=("ls-tree", "-rz", "--full-tree", "HEAD"),
            output_limit=256 << 20,
        )
        governance = json.loads(
            governance_raw.decode("utf-8"),
            object_pairs_hook=_collection_pairs,
            parse_float=_reject_collection_number,
            parse_constant=_reject_collection_number,
        )
    except Exception as exc:
        raise GateAValidationError("pytest committed collection authority is unavailable") from exc
    if type(governance) is not dict or type(governance.get("pytest_entrypoints")) is not list:
        raise GateAValidationError("pytest committed collection authority is malformed")
    entries = [
        entry
        for entry in governance["pytest_entrypoints"]
        if type(entry) is dict and entry.get("id") == "preflight_full_non_slow"
    ]
    if len(entries) != 1:
        raise GateAValidationError("pytest committed collection authority is ambiguous")
    expected_count = entries[0].get("expected_count")
    expected_sha256 = entries[0].get("expected_sha256")
    if (
        type(expected_count) is not int
        or expected_count <= 0
        or type(expected_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
    ):
        raise GateAValidationError("pytest committed collection expectation is malformed")
    tracked_files: set[str] = set()
    try:
        for raw_entry in tree.split(b"\0"):
            if not raw_entry:
                continue
            metadata, raw_path = raw_entry.split(b"\t", 1)
            mode, kind, oid = metadata.decode("ascii").split(" ", 2)
            path = raw_path.decode("utf-8")
            if (
                not _safe_repository_relative(path)
                or re.fullmatch(r"[0-9a-f]{40}", oid) is None
            ):
                raise GateAValidationError("pytest HEAD member listing is unsafe")
            if kind == "blob" and mode in {"100644", "100755"}:
                tracked_files.add(path)
    except (UnicodeDecodeError, ValueError) as exc:
        raise GateAValidationError("pytest HEAD member listing is malformed") from exc
    if _PYTEST_GOVERNANCE_PATH not in tracked_files:
        raise GateAValidationError("pytest governance manifest is absent from HEAD")
    return expected_count, expected_sha256, tracked_files


def _verify_pytest_collection_stdout(
    stdout: bytes,
    *,
    repository: Path,
    sources: Mapping[str, Mapping[str, Any]],
) -> dict[str, object]:
    expected_count, expected_sha256, tracked_files = (
        _head_pytest_collection_authority(
            repository=repository,
            sources=sources,
        )
    )
    return _pytest_collection_projection(
        stdout,
        expected_count=expected_count,
        expected_sha256=expected_sha256,
        tracked_files=tracked_files,
    )


def _reobserve_planned_sources(
    *,
    repository_root: Path,
    sources: Mapping[str, Mapping[str, Any]],
    expected_digest: str,
) -> None:
    strict_paths = {
        role.removeprefix("input."): identity["path"] for role, identity in sources.items() if role.startswith("input.")
    }
    system_paths = {
        role.removeprefix("system."): identity["requested_path"]
        for role, identity in sources.items()
        if role.startswith("system.")
    }
    drill_authority._reobserve_sources(  # noqa: SLF001
        strict_input_paths=strict_paths,
        system_tool_paths=system_paths,
        expected=sources,
        expected_digest=expected_digest,
    )
    head = drill_authority._observe_repository_head(  # noqa: SLF001
        repository_root,
        sources,
    )
    if re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise GateAValidationError("repository HEAD replay is malformed")


def _verify_current_tool(
    *,
    sources: Mapping[str, Mapping[str, Any]],
) -> dict[str, object]:
    expected_full = sources.get(TOOL_SOURCE_ROLE)
    if type(expected_full) is not dict:
        raise GateAValidationError("Gate-A validation tool is not planned")
    expected = {field: expected_full[field] for field in ("mode", "path", "sha256", "size_bytes")}
    current = _snapshot_identity(Path(__file__))
    _same_identity(current, expected, "Gate-A validation tool")
    return current


def _verify_drill(
    authority_root: Path,
) -> dict[str, object]:
    """Replay the complete immutable drill without writing a new receipt."""

    pre_run_path = authority_root / "attempt/pre-run-authority.json"
    selection_path = authority_root / "attempt/selection.json"
    pre_run = verifier.snapshot_json(pre_run_path)
    selection = verifier.snapshot_json(selection_path)
    verified_pre_run = verifier.validate_pre_run_authority(pre_run.value)
    if verified_pre_run["execution_class"] != "DISPOSABLE_LIVE_DRILL":
        raise GateAValidationError("Gate-A evidence is not a disposable drill")
    paths = verified_pre_run["output_paths"]
    stored = verifier.snapshot_json(paths["detached_replay"])
    replayed = verifier.verify_detached(
        pre_run=pre_run,
        selection=selection,
        inner=verifier.snapshot_json(paths["inner"]),
        preterminal=verifier.snapshot_json(paths["preterminal"]),
        payload_result=verifier.snapshot_json(paths["attempt_result"]),
        resource=verifier.snapshot_json(paths["resource_verification"]),
        reference_acquisition=verifier.snapshot_json(paths["reference_acquisition"]),
        release=verifier.snapshot_json(paths["release"]),
        terminal=verifier.snapshot_json(paths["terminal"]),
        reference_release=verifier.snapshot_json(paths["reference_release"]),
        cleanup=verifier.snapshot_json(paths["cleanup"]),
        detached_epoch=verifier.snapshot_json(verified_pre_run["epoch_observation_paths"]["detached-replay"]),
        verifier_tool_identity=verified_pre_run["tool_identities"]["organic_resource_verifier"],
    )
    if stored.value != replayed or replayed.get("status") != "PASS":
        raise GateAValidationError("disposable drill detached replay differs")
    ready = verifier.snapshot_json(authority_root / "authority/authority-ready.json")
    sources, digest = _planned_sources(authority_root)
    _validate_authority_ready(
        ready.value,
        planned_source_set_digest=digest,
        pre_run_identity=pre_run.identity,
        run_nonce=verified_pre_run["run_nonce"],
        selection_identity=selection.identity,
    )
    _verify_current_tool(sources=sources)
    return {
        "authority_ready_identity": ready.identity,
        "detached_replay_identity": stored.identity,
        "planned_source_set_digest": digest,
        "pre_run": dict(verified_pre_run),
        "pre_run_identity": pre_run.identity,
        "selection_identity": selection.identity,
        "sources": sources,
    }


def _open_verified(
    identity: object,
    label: str,
) -> tuple[int, tuple[int, ...]]:
    expected = _identity(identity, label)
    path = Path(expected["path"])
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise GateAValidationError(f"cannot open pinned {label}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise GateAValidationError(f"pinned {label} is not a regular file")
        os.lseek(descriptor, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(descriptor)
        signature = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != signature or {
            "mode": stat.S_IMODE(after.st_mode),
            "path": str(path),
            "sha256": digest.hexdigest(),
            "size_bytes": size,
        } != expected:
            raise GateAValidationError(f"pinned {label} identity drifted")
        return descriptor, signature
    except BaseException as exc:
        try:
            os.close(descriptor)
        except OSError as close_error:
            exc.add_note(
                f"pinned {label} descriptor cleanup failed: "
                f"{type(close_error).__name__}: {close_error}"
            )
        raise


def _recheck_open(
    descriptor: int,
    signature: tuple[int, ...],
    expected: object,
    label: str,
) -> None:
    observed = os.fstat(descriptor)
    current = (
        observed.st_dev,
        observed.st_ino,
        observed.st_mode,
        observed.st_nlink,
        observed.st_size,
        observed.st_mtime_ns,
        observed.st_ctime_ns,
    )
    if current != signature:
        raise GateAValidationError(f"pinned {label} metadata drifted")
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
    expected_record = _identity(expected, label)
    if digest.hexdigest() != expected_record["sha256"] or size != expected_record["size_bytes"]:
        raise GateAValidationError(f"pinned {label} bytes drifted")


def _recheck_and_close_sources(
    opened: Sequence[
        tuple[int, tuple[int, ...], Mapping[str, Any], str]
    ],
    *,
    primary: BaseException | None,
) -> None:
    failures: list[tuple[str, BaseException]] = []
    for descriptor, signature, expected, label in opened:
        try:
            _recheck_open(descriptor, signature, expected, label)
        except BaseException as exc:
            failures.append((f"{label} recheck", exc))
    for descriptor, _signature, _expected, label in reversed(tuple(opened)):
        try:
            os.close(descriptor)
        except BaseException as exc:
            failures.append((f"{label} close", exc))
    if primary is not None:
        for label, failure in failures:
            primary.add_note(
                f"{label} failed: {type(failure).__name__}: {failure}"
            )
        return
    if failures:
        label, failure = failures[0]
        if isinstance(failure, GateAValidationError):
            raise failure
        raise GateAValidationError(
            f"preflight retained-source {label} failed"
        ) from failure


def _run_same_fd_python_script(
    *,
    python_identity: Mapping[str, Any],
    script_identity: Mapping[str, Any],
    repository: Path,
    forwarded: Sequence[str],
    environment: Mapping[str, str],
    timeout_seconds: float,
    support_identities: Sequence[tuple[str, Mapping[str, Any]]] = (),
    final_prelaunch_check: Callable[[], None] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run one script while every verified source descriptor remains open."""

    verified_python = _identity(python_identity, "preflight Python")
    verified_script = _identity(script_identity, "preflight script")
    verified_support: list[tuple[str, dict[str, object]]] = []
    seen_roles: set[str] = set()
    for role, identity in support_identities:
        if (
            type(role) is not str
            or re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", role) is None
            or role in seen_roles
        ):
            raise GateAValidationError("preflight support-source role set drifted")
        seen_roles.add(role)
        verified_support.append(
            (role, _identity(identity, f"preflight support source {role}"))
        )
    opened: list[tuple[int, tuple[int, ...], Mapping[str, Any], str]] = []
    try:
        python_fd, python_signature = _open_verified(
            verified_python,
            "preflight Python",
        )
        opened.append(
            (
                python_fd,
                python_signature,
                verified_python,
                "preflight Python",
            )
        )
        script_fd, script_signature = _open_verified(
            verified_script,
            "preflight script",
        )
        opened.append(
            (
                script_fd,
                script_signature,
                verified_script,
                "preflight script",
            )
        )
        support_arguments: list[str] = []
        for role, identity in verified_support:
            descriptor, signature = _open_verified(
                identity,
                f"preflight support source {role}",
            )
            opened.append(
                (
                    descriptor,
                    signature,
                    identity,
                    f"preflight support source {role}",
                )
            )
            support_arguments.extend(
                [
                    "--support-source",
                    role,
                    str(descriptor),
                    str(identity["path"]),
                    str(identity["mode"]),
                    str(identity["size_bytes"]),
                    str(identity["sha256"]),
                ]
            )
    except BaseException as primary:
        _recheck_and_close_sources(opened, primary=primary)
        raise
    actual_argv = [
        str(verified_python["path"]),
        "-I",
        "-B",
        "-c",
        _SCRIPT_LOADER,
        str(python_fd),
        str(script_fd),
        str(verified_python["path"]),
        str(verified_python["mode"]),
        str(verified_python["size_bytes"]),
        str(verified_python["sha256"]),
        str(verified_script["path"]),
        str(verified_script["mode"]),
        str(verified_script["size_bytes"]),
        str(verified_script["sha256"]),
        *support_arguments,
        *forwarded,
    ]
    popen_kwargs: dict[str, Any] = {
        "close_fds": True,
        "cwd": repository,
        "env": dict(environment),
        "executable": f"/proc/self/fd/{python_fd}",
        "pass_fds": tuple(item[0] for item in opened),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "start_new_session": True,
    }
    process: subprocess.Popen[bytes] | None = None
    try:
        if final_prelaunch_check is not None:
            final_prelaunch_check()
        process = subprocess.Popen(actual_argv, **popen_kwargs)
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=15)
            except subprocess.TimeoutExpired as cleanup_timeout:
                for stream in (process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()
                # The subreaper may not be killed while it still owns adopted
                # descendants.  Wait fail-stop for its descendants-only
                # cleanup rather than targeting a potentially reused PGID.
                process.wait()
                raise GateAValidationError(
                    "preflight supervisor required extended descendant cleanup after timeout"
                ) from cleanup_timeout
            raise subprocess.TimeoutExpired(
                actual_argv,
                timeout_seconds,
                output=stdout,
                stderr=stderr,
            )
        completed = subprocess.CompletedProcess(
            actual_argv,
            process.returncode,
            stdout,
            stderr,
        )
    except BaseException as primary:
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            try:
                process.communicate()
            except BaseException as cleanup_error:
                primary.add_note(
                    "preflight process cleanup failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
        _recheck_and_close_sources(opened, primary=primary)
        raise
    _recheck_and_close_sources(opened, primary=None)
    return completed


def _record_full_preflight_with_lease(
    *,
    authority_root: Path | str,
    repository_root: Path | str,
    output_dir: Path | str,
    resource_locks: resource_admission.HeldResourceLocks,
) -> dict[str, object]:
    """Run one package-pinned full preflight after a detached drill PASS."""

    root = _absolute(authority_root)
    repository = _absolute(repository_root)
    evidence = _verify_drill(root)
    pre_run = evidence["pre_run"]
    if pre_run["repository_root"] != str(repository):
        raise GateAValidationError("preflight repository root differs from drill")
    sources = evidence["sources"]
    _reobserve_planned_sources(
        repository_root=repository,
        sources=sources,
        expected_digest=evidence["planned_source_set_digest"],
    )
    expected_head = pre_run["repository_head"]
    observed_head = drill_authority._observe_repository_head(  # noqa: SLF001
        repository,
        sources,
    )
    if observed_head != expected_head:
        raise GateAValidationError("repository HEAD drifted before full preflight")
    python_identity = pre_run["tool_identities"]["python3_13"]
    preflight_identity = _planned_source_identity(
        sources,
        PREFLIGHT_SOURCE_ROLE,
        "preflight script",
    )
    qualification_identity = _planned_source_identity(
        sources,
        QUALIFICATION_SOURCE_ROLE,
        "AB16 preflight qualification runner",
    )
    collection_protocol_identity = _planned_source_identity(
        sources,
        COLLECTION_PROTOCOL_SOURCE_ROLE,
        "AB16 pytest collection protocol",
    )
    collection_plugin_identity = _planned_source_identity(
        sources,
        COLLECTION_PLUGIN_SOURCE_ROLE,
        "AB16 pytest collection plugin",
    )
    resource_admission_identity = _planned_source_identity(
        sources,
        RESOURCE_ADMISSION_SOURCE_ROLE,
        "AB16 resource admission",
    )
    if _snapshot_identity(resource_admission.__file__) != resource_admission_identity:
        raise GateAValidationError("AB16 resource-admission import identity drifted")
    expected_collection_count, expected_collection_sha256, _tracked_files = (
        _head_pytest_collection_authority(
            repository=repository,
            sources=sources,
        )
    )
    output = _absolute(output_dir)
    scratch_root = output / PREFLIGHT_SCRATCH_BASENAME
    basetemp_path = scratch_root / PREFLIGHT_BASETEMP_BASENAME
    try:
        basetemp_relative = basetemp_path.relative_to(repository)
    except ValueError as exc:
        raise GateAValidationError(
            "preflight output is not a repository-local child"
        ) from exc
    qualification_arguments = (
        "--repository-root",
        str(repository),
        "--basetemp",
        str(basetemp_path),
        "--basetemp-relative",
        basetemp_relative.as_posix(),
        "--expected-count",
        str(expected_collection_count),
        "--expected-sha256",
        expected_collection_sha256,
        "--preflight-source",
        str(preflight_identity["path"]),
        "--collection-protocol-source",
        str(collection_protocol_identity["path"]),
        "--collection-plugin-source",
        str(collection_plugin_identity["path"]),
        "--full",
    )
    (
        created_output_descriptor,
        created_scratch_descriptor,
        output_initial_identity,
        scratch_initial_identity,
    ) = _create_preflight_output_and_scratch(
        repository=repository,
        output=output,
    )
    output_descriptor: int | None = created_output_descriptor
    scratch_descriptor: int | None = created_scratch_descriptor
    timed_out = False
    basetemp_identity: dict[str, int] | None = None
    pytest_collection: dict[str, object] | None = None
    surface_guard: _PytestSurfaceGuard | None = None
    try:
        assert output_descriptor is not None
        assert scratch_descriptor is not None
        started_at_utc = _utc_now()
        started_ns = time.monotonic_ns()
        environment = _preflight_environment()
        surface_guard = _verify_pytest_repository_surface(
            repository=repository,
            sources=sources,
        )
        resource_lock_identities = resource_locks.identities()
        resource_observation_context = {
            "authority_id": evidence["pre_run_identity"]["sha256"],
            "disk_path": str(repository),
            "kind": "GATE_A_FULL_PREFLIGHT",
            "ordinal": 0,
            "scope_id": evidence["planned_source_set_digest"],
            "sequence": 1,
            "slot": "",
            "target": str(output),
        }
        resource_receipt: dict[str, object] | None = None

        def final_prelaunch_resource_check() -> None:
            nonlocal resource_receipt
            if resource_locks.identities() != resource_lock_identities:
                raise GateAValidationError(
                    "Gate-A lock identities drifted before final resource admission"
                )
            try:
                checked_receipt = resource_admission.evaluate_resource_admission(
                    repository,
                    stage=resource_admission.FULL_PREFLIGHT,
                    lock_identities=resource_lock_identities,
                    lock_identity_format=resource_admission.GATE_B_LOCK_IDENTITY_FORMAT,
                    observation_context=resource_observation_context,
                )
            except resource_admission.ResourceAdmissionError as exc:
                raise GateAValidationError(
                    f"Gate-A full-preflight resource admission failed: {exc}"
                ) from exc
            if resource_locks.identities() != resource_lock_identities:
                raise GateAValidationError(
                    "Gate-A lock identities drifted across final resource admission"
                )
            resource_receipt = checked_receipt

        try:
            completed = _run_same_fd_python_script(
                python_identity=python_identity,
                script_identity=qualification_identity,
                support_identities=(
                    ("preflight", preflight_identity),
                    ("protocol", collection_protocol_identity),
                    ("plugin", collection_plugin_identity),
                ),
                repository=repository,
                forwarded=qualification_arguments,
                environment=environment,
                timeout_seconds=PREFLIGHT_TIMEOUT_SECONDS,
                final_prelaunch_check=final_prelaunch_resource_check,
            )
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 124
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
        if resource_receipt is None:
            raise GateAValidationError(
                "full-preflight runner skipped final resource admission"
            )
        if surface_guard is not None:
            surface_guard.verify_and_close()
            surface_guard = None
        if exit_code == 0 and not timed_out:
            try:
                pytest_collection = _verify_pytest_collection_stdout(
                    stdout,
                    repository=repository,
                    sources=sources,
                )
            except Exception as exc:  # noqa: BLE001 - collection uncertainty must become receipt-level failure
                exit_code = PREFLIGHT_SCRATCH_CLOSURE_FAILURE_EXIT_CODE
                stderr += (
                    "\nAB16 pytest collection authority failed closed: "
                    f"{type(exc).__name__}\n"
                ).encode("ascii")
        scratch_status = "PRESERVED_AFTER_PREFLIGHT_FAILURE"
        if exit_code == 0 and not timed_out:
            try:
                basetemp_identity = _observe_closed_preflight_scratch(
                    scratch_root,
                    descriptor=scratch_descriptor,
                    initial_identity=scratch_initial_identity,
                )
            except Exception as exc:  # noqa: BLE001 - closure uncertainty must become a receipt-level failure
                exit_code = PREFLIGHT_SCRATCH_CLOSURE_FAILURE_EXIT_CODE
                scratch_status = "CLOSURE_FAILED_FAIL_CLOSED"
                stderr += (
                    f"\nAB16 preflight scratch closure failed closed: {type(exc).__name__}\n"
                ).encode("ascii")
            else:
                scratch_status = "CLOSED_EMPTY_BASETEMP_RETAINED_AFTER_PASS"
        final_resource_lock_identities = resource_locks.identities()
        if final_resource_lock_identities != resource_lock_identities:
            raise GateAValidationError(
                "Gate-A lock identities drifted across full preflight"
            )
        try:
            released_resource_lock_identities = resource_locks.release_once()
        except resource_admission.ResourceAdmissionError as exc:
            raise GateAValidationError(
                f"Gate-A resource-lock release failed: {exc}"
            ) from exc
        if released_resource_lock_identities != resource_lock_identities:
            raise GateAValidationError(
                "Gate-A resource-lock release identity drifted"
            )
        finished_ns = time.monotonic_ns()
        stdout_identity = {
            "mode": 0o444,
            **_write_exclusive_at(
                output_descriptor,
                absolute_path=output / "stdout.log",
                raw=stdout,
                mode=0o444,
            ),
        }
        stderr_identity = {
            "mode": 0o444,
            **_write_exclusive_at(
                output_descriptor,
                absolute_path=output / "stderr.log",
                raw=stderr,
                mode=0o444,
            ),
        }
        receipt = {
            "authorizations": {
                "formal_campaign_creation_authorized": False,
                "organic_arm_launch_authorized": False,
                "solver_run_authorized": False,
            },
            "authority_ready_identity": evidence["authority_ready_identity"],
            "command": {
                "argv": [
                    python_identity["path"],
                    "-I",
                    "-B",
                    qualification_identity["path"],
                    *qualification_arguments,
                ],
                "execution_strategy": PREFLIGHT_EXECUTION_STRATEGY,
                "loader_identity": _loader_identity(),
            },
            "detached_replay_identity": evidence["detached_replay_identity"],
            "duration_monotonic_ns": finished_ns - started_ns,
            "exit_code": exit_code,
            "finished_at_utc": _utc_now(),
            "planned_source_set_digest": evidence["planned_source_set_digest"],
            "pre_run_authority_identity": evidence["pre_run_identity"],
            "qualification_runner_identity": qualification_identity,
            "pytest_collection_plugin_identity": collection_plugin_identity,
            "pytest_collection_protocol_identity": collection_protocol_identity,
            "preflight_script_identity": preflight_identity,
            "preflight_timeout_scale": TIMEOUT_SCALE,
            "purpose": PREFLIGHT_PURPOSE,
            "output_root_identity": output_initial_identity,
            "pytest_collection": pytest_collection,
            "pytest_scratch": {
                "basetemp_identity": basetemp_identity,
                "basetemp_path": str(basetemp_path),
                "initial_identity": scratch_initial_identity,
                "path": str(scratch_root),
                "policy": PREFLIGHT_SCRATCH_POLICY,
                "retention_policy": "failed",
                "status": scratch_status,
            },
            "python_identity": python_identity,
            "resource_admission": resource_receipt,
            "resource_admission_source_identity": resource_admission_identity,
            "resource_lock_release_identities": released_resource_lock_identities,
            "repository_head": expected_head,
            "repository_root": str(repository),
            "runner_tool_identity": _verify_current_tool(sources=sources),
            "schema_version": PREFLIGHT_SCHEMA,
            "started_at_utc": started_at_utc,
            "status": "PASS" if exit_code == 0 and not timed_out else "FAIL_CLOSED",
            "stderr_identity": stderr_identity,
            "stdout_identity": stdout_identity,
            "timed_out": timed_out,
        }
        _require_directory_join(
            output,
            descriptor=output_descriptor,
            label="preflight output",
        )
        _require_directory_join(
            scratch_root,
            descriptor=scratch_descriptor,
            label="preflight scratch",
        )
        with os.scandir(output_descriptor) as iterator:
            output_entries = {entry.name for entry in iterator}
        if output_entries != {
            PREFLIGHT_SCRATCH_BASENAME,
            "stderr.log",
            "stdout.log",
        }:
            raise GateAValidationError("preflight output closed tree has unexpected entries")
        for absolute_path, expected_identity in (
            (output / "stdout.log", stdout_identity),
            (output / "stderr.log", stderr_identity),
        ):
            _recheck_exclusive_at(
                output_descriptor,
                absolute_path=absolute_path,
                expected=expected_identity,
            )
        if receipt["status"] == "PASS":
            final_basetemp_identity = _observe_closed_preflight_scratch(
                scratch_root,
                descriptor=scratch_descriptor,
                initial_identity=scratch_initial_identity,
            )
            if final_basetemp_identity != basetemp_identity:
                raise GateAValidationError("preflight basetemp identity drifted before receipt closeout")
        receipt_identity = {
            "mode": 0o444,
            **_write_exclusive_at(
                output_descriptor,
                absolute_path=output / "receipt.json",
                raw=verifier.canonical_json_bytes(receipt),
                mode=0o444,
            ),
        }
        commit_identity = {
            "mode": 0o600,
            **_write_exclusive_at(
                output_descriptor,
                absolute_path=output / "receipt.commit.json",
                raw=verifier.canonical_json_bytes(
                    {
                        "output_root_identity": output_initial_identity,
                        "receipt_identity": receipt_identity,
                        "schema_version": PREFLIGHT_PUBLICATION_COMMIT_SCHEMA,
                        "status": "COMMITTED",
                    }
                ),
                mode=0o600,
            ),
        }
        with os.scandir(output_descriptor) as iterator:
            published_entries = {entry.name for entry in iterator}
        if published_entries != {
            PREFLIGHT_SCRATCH_BASENAME,
            "receipt.commit.json",
            "receipt.json",
            "stderr.log",
            "stdout.log",
        }:
            raise GateAValidationError("preflight staged publication tree has unexpected entries")
        for absolute_path, expected_identity in (
            (output / "stdout.log", stdout_identity),
            (output / "stderr.log", stderr_identity),
            (output / "receipt.json", receipt_identity),
            (output / "receipt.commit.json", commit_identity),
        ):
            _recheck_exclusive_at(
                output_descriptor,
                absolute_path=absolute_path,
                expected=expected_identity,
            )
        os.fsync(output_descriptor)
        descriptor_to_close = scratch_descriptor
        scratch_descriptor = None
        os.close(descriptor_to_close)
        descriptor_to_promote = output_descriptor
        output_descriptor = None
        _promote_preflight_publication_commit(
            output / "receipt.commit.json",
            directory_descriptor=descriptor_to_promote,
            expected_directory_identity=output_initial_identity,
            expected_identity=commit_identity,
        )
        replayed_identity = _self_replay_preflight_publication(
            output=output,
            receipt=receipt,
            receipt_identity=receipt_identity,
        )
        if replayed_identity != receipt_identity:
            raise GateAValidationError("preflight producer self-replay receipt identity drifted")
        return {
            "receipt": receipt,
            "receipt_identity": replayed_identity,
            "status": receipt["status"],
        }
    except BaseException as exc:
        if surface_guard is not None:
            surface_guard.abort(exc)
        for descriptor in (scratch_descriptor, output_descriptor):
            if descriptor is None:
                continue
            try:
                os.close(descriptor)
            except OSError as close_error:
                exc.add_note(
                    "preflight directory cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise


def record_full_preflight(
    *,
    authority_root: Path | str,
    repository_root: Path | str,
    output_dir: Path | str,
    resource_lock_fds: Mapping[str, int] | None = None,
) -> dict[str, object]:
    """Acquire the three-lock lease, then run one internally gated full lane."""

    try:
        if resource_lock_fds is None:
            resource_locks = resource_admission.HeldResourceLocks.acquire(
                identity_format=resource_admission.GATE_B_LOCK_IDENTITY_FORMAT,
            )
        else:
            resource_locks = resource_admission.HeldResourceLocks.adopt_owned(
                resource_lock_fds,
                identity_format=resource_admission.GATE_B_LOCK_IDENTITY_FORMAT,
            )
    except resource_admission.ResourceAdmissionError as exc:
        raise GateAValidationError(
            f"Gate-A resource-lock acquisition failed: {exc}"
        ) from exc
    try:
        result = _record_full_preflight_with_lease(
            authority_root=authority_root,
            repository_root=repository_root,
            output_dir=output_dir,
            resource_locks=resource_locks,
        )
    except BaseException as exc:
        if not resource_locks.released:
            try:
                resource_locks.release_once()
            except BaseException as cleanup_error:
                exc.add_note(
                    "Gate-A resource-lock failure cleanup failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
        raise
    if not resource_locks.released:
        try:
            resource_locks.release_once()
        except BaseException as cleanup_error:
            raise GateAValidationError(
                "Gate-A full preflight returned with live resource locks and "
                f"cleanup failed: {cleanup_error}"
            ) from cleanup_error
        raise GateAValidationError(
            "Gate-A full preflight returned before its recorded lock release"
        )
    return result


def _owned_resource_lock_fds(values: Sequence[str]) -> dict[str, int] | None:
    if not values:
        return None
    parsed: dict[str, int] = {}
    for value in values:
        path, separator, raw_descriptor = value.rpartition("=")
        if (
            not separator
            or path not in resource_admission.LOCK_PATHS
            or path in parsed
            or not raw_descriptor.isdigit()
            or int(raw_descriptor) < 3
        ):
            raise GateAValidationError(
                "inherited resource-lock descriptors must be the exact three path=fd bindings"
            )
        parsed[path] = int(raw_descriptor)
    if set(parsed) != set(resource_admission.LOCK_PATHS):
        raise GateAValidationError(
            "inherited resource-lock descriptors must cover the exact three lock paths"
        )
    return parsed


def _verify_closed_preflight_scratch(
    value: object,
    *,
    receipt_directory: Path,
) -> None:
    if type(value) is not dict or set(value) != {
        "basetemp_identity",
        "basetemp_path",
        "initial_identity",
        "path",
        "policy",
        "retention_policy",
        "status",
    }:
        raise GateAValidationError("full-preflight pytest scratch record drifted")
    identity = value["initial_identity"]
    basetemp_identity = value["basetemp_identity"]
    if (
        type(identity) is not dict
        or set(identity) != {"device", "inode", "mode", "uid"}
        or type(basetemp_identity) is not dict
        or set(basetemp_identity) != {"device", "inode", "mode", "uid"}
        or any(type(identity[field]) is not int for field in identity)
        or any(type(basetemp_identity[field]) is not int for field in basetemp_identity)
        or identity["device"] < 0
        or identity["inode"] <= 0
        or identity["mode"] != 0o700
        or identity["uid"] != os.geteuid()
        or basetemp_identity["device"] < 0
        or basetemp_identity["inode"] <= 0
        or basetemp_identity["mode"] != 0o700
        or basetemp_identity["uid"] != os.geteuid()
        or value["path"] != str(receipt_directory / PREFLIGHT_SCRATCH_BASENAME)
        or value["basetemp_path"]
        != str(receipt_directory / PREFLIGHT_SCRATCH_BASENAME / PREFLIGHT_BASETEMP_BASENAME)
        or value["policy"] != PREFLIGHT_SCRATCH_POLICY
        or value["retention_policy"] != "failed"
        or value["status"] != "CLOSED_EMPTY_BASETEMP_RETAINED_AFTER_PASS"
    ):
        raise GateAValidationError("full-preflight pytest scratch record is not one exact closed PASS")
    descriptor: int | None = None
    basetemp_descriptor: int | None = None
    try:
        descriptor = _open_directory_no_symlinks(Path(value["path"]))
        if not _same_scratch_identity(descriptor, identity):
            raise GateAValidationError("full-preflight pytest scratch identity drifted")
        with os.scandir(descriptor) as iterator:
            entries = list(iterator)
        if len(entries) != 1 or entries[0].name != PREFLIGHT_BASETEMP_BASENAME:
            raise GateAValidationError("full-preflight pytest scratch tree drifted")
        named = entries[0].stat(follow_symlinks=False)
        if not stat.S_ISDIR(named.st_mode):
            raise GateAValidationError("full-preflight pytest basetemp type drifted")
        basetemp_descriptor = os.open(
            PREFLIGHT_BASETEMP_BASENAME,
            _directory_flags(),
            dir_fd=descriptor,
        )
        opened = os.fstat(basetemp_descriptor)
        if (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino):
            raise GateAValidationError("full-preflight pytest basetemp identity drifted")
        if not _same_scratch_identity(basetemp_descriptor, basetemp_identity):
            raise GateAValidationError("full-preflight pytest basetemp identity drifted")
        with os.scandir(basetemp_descriptor) as iterator:
            if next(iterator, None) is not None:
                raise GateAValidationError("full-preflight pytest basetemp is not empty")
    except BaseException as exc:
        for opened_descriptor in (basetemp_descriptor, descriptor):
            if opened_descriptor is None:
                continue
            try:
                os.close(opened_descriptor)
            except OSError as close_error:
                exc.add_note(
                    "full-preflight pytest scratch cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        if isinstance(exc, OSError):
            raise GateAValidationError("full-preflight pytest scratch closure check failed") from exc
        raise
    close_error: OSError | None = None
    for opened_descriptor in (basetemp_descriptor, descriptor):
        try:
            os.close(opened_descriptor)
        except OSError as exc:
            if close_error is None:
                close_error = exc
    if close_error is not None:
        raise GateAValidationError("full-preflight pytest scratch descriptor close failed") from close_error


def _verify_preflight_output_root(
    *,
    receipt_directory: Path,
    expected_identity: object,
) -> None:
    if (
        type(expected_identity) is not dict
        or set(expected_identity) != {"device", "inode", "mode", "uid"}
        or any(type(expected_identity[field]) is not int for field in expected_identity)
        or expected_identity["device"] < 0
        or expected_identity["inode"] <= 0
        or expected_identity["mode"] != 0o700
        or expected_identity["uid"] != os.geteuid()
    ):
        raise GateAValidationError("full-preflight output-root identity is malformed")
    descriptor: int | None = None
    try:
        descriptor = _open_directory_no_symlinks(receipt_directory)
        if not _same_scratch_identity(descriptor, expected_identity):
            raise GateAValidationError("full-preflight output-root identity drifted")
        with os.scandir(descriptor) as iterator:
            entries = {entry.name for entry in iterator}
        if entries != {
            PREFLIGHT_SCRATCH_BASENAME,
            "receipt.commit.json",
            "receipt.json",
            "stderr.log",
            "stdout.log",
        }:
            raise GateAValidationError("full-preflight output-root member set drifted")
    except BaseException as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as close_error:
                exc.add_note(
                    "full-preflight output-root cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        if isinstance(exc, OSError):
            raise GateAValidationError("full-preflight output-root validation failed") from exc
        raise
    try:
        os.close(descriptor)
    except OSError as exc:
        raise GateAValidationError("full-preflight output-root descriptor close failed") from exc


def _verify_preflight_publication_commit(
    *,
    receipt_identity: Mapping[str, object],
    output_root_identity: object,
) -> None:
    receipt_path = Path(str(receipt_identity["path"]))
    snapshot = verifier.snapshot_json(receipt_path.parent / "receipt.commit.json")
    value = snapshot.value
    if (
        type(value) is not dict
        or set(value) != {
            "output_root_identity",
            "receipt_identity",
            "schema_version",
            "status",
        }
        or value["schema_version"] != PREFLIGHT_PUBLICATION_COMMIT_SCHEMA
        or value["status"] != "COMMITTED"
        or value["receipt_identity"] != dict(receipt_identity)
        or value["output_root_identity"] != output_root_identity
        or snapshot.identity.get("mode") != 0o444
    ):
        raise GateAValidationError("full-preflight publication commit is invalid")


def _self_replay_preflight_publication_once(
    *,
    output: Path,
    receipt: Mapping[str, Any],
    receipt_identity: Mapping[str, object],
) -> dict[str, object]:
    """Replay one just-committed publication through its absolute path."""

    snapshot = verifier.snapshot_json(output / "receipt.json")
    if snapshot.value != receipt or snapshot.identity != dict(receipt_identity):
        raise GateAValidationError("preflight producer self-replay receipt drifted")
    output_root_identity = receipt.get("output_root_identity")
    _verify_preflight_publication_commit(
        receipt_identity=snapshot.identity,
        output_root_identity=output_root_identity,
    )
    _verify_preflight_output_root(
        receipt_directory=output,
        expected_identity=output_root_identity,
    )
    stdout_raw: bytes | None = None
    for field in ("stdout_identity", "stderr_identity"):
        expected = receipt.get(field)
        if type(expected) is not dict:
            raise GateAValidationError(f"preflight producer self-replay {field} is malformed")
        if field == "stdout_identity":
            stdout_raw, observed = verifier.snapshot_bytes(Path(str(expected.get("path"))))
        else:
            observed = _snapshot_identity(Path(str(expected.get("path"))))
        _same_identity(observed, expected, f"preflight producer self-replay {field}")
    if receipt.get("status") == "PASS":
        assert stdout_raw is not None
        if _pytest_collection_projection(stdout_raw) != receipt.get("pytest_collection"):
            raise GateAValidationError("preflight producer self-replay collection binding drifted")
    scratch = receipt.get("pytest_scratch")
    if type(scratch) is not dict:
        raise GateAValidationError("preflight producer self-replay scratch record is malformed")
    _verify_preflight_publication_commit(
        receipt_identity=snapshot.identity,
        output_root_identity=output_root_identity,
    )
    _verify_preflight_output_root(
        receipt_directory=output,
        expected_identity=output_root_identity,
    )
    # Scratch closure is the final temporal observation: no fallible
    # validation follows it.  A mutation after this check is a later external
    # operation and cannot rewrite the already-linearized producer result.
    if receipt.get("status") == "PASS":
        _verify_closed_preflight_scratch(
            scratch,
            receipt_directory=output,
        )
    else:
        scratch_path = output / PREFLIGHT_SCRATCH_BASENAME
        if (
            scratch.get("path") != str(scratch_path)
            or type(scratch.get("initial_identity")) is not dict
        ):
            raise GateAValidationError("preflight producer failure scratch identity is malformed")
        descriptor: int | None = None
        try:
            descriptor = _open_directory_no_symlinks(scratch_path)
            if not _same_scratch_identity(
                descriptor,
                scratch["initial_identity"],
            ):
                raise GateAValidationError("preflight producer failure scratch identity drifted")
        except BaseException as exc:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError as close_error:
                    exc.add_note(
                        "preflight producer failure scratch cleanup failed: "
                        f"{type(close_error).__name__}: {close_error}"
                    )
            raise
        try:
            os.close(descriptor)
        except OSError as exc:
            raise GateAValidationError(
                "preflight producer failure scratch descriptor close failed"
            ) from exc
    return dict(snapshot.identity)


def _post_commit_replay_uncertain(exc: BaseException) -> bool:
    retryable_errnos = {
        errno.EBUSY,
        errno.EINTR,
        errno.EIO,
        errno.EMFILE,
        errno.ENFILE,
        errno.ENOMEM,
        errno.ESTALE,
    }
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, OSError) and current.errno in retryable_errnos:
            return True
        current = current.__cause__ or current.__context__
    return False


def _self_replay_preflight_publication(
    *,
    output: Path,
    receipt: Mapping[str, Any],
    receipt_identity: Mapping[str, object],
) -> dict[str, object]:
    """Complete the post-commit replay without contradicting its marker."""

    while True:
        try:
            return _self_replay_preflight_publication_once(
                output=output,
                receipt=receipt,
                receipt_identity=receipt_identity,
            )
        except Exception as exc:
            if _post_commit_replay_uncertain(exc):
                # The 0444 marker is already the linearization point.  A
                # transient I/O or descriptor-cleanup uncertainty must be
                # reconciled by a new complete replay, never reported as if
                # publication had not committed.  Conclusive topology or byte
                # drift remains a normal fail-closed exception.
                continue
            raise


def _verify_preflight_receipt(
    *,
    receipt_path: Path | str,
    evidence: Mapping[str, Any],
) -> tuple[Mapping[str, Any], dict[str, object]]:
    snapshot = verifier.snapshot_json(receipt_path)
    receipt = snapshot.value
    expected_keys = {
        "authorizations",
        "authority_ready_identity",
        "command",
        "detached_replay_identity",
        "duration_monotonic_ns",
        "exit_code",
        "finished_at_utc",
        "output_root_identity",
        "planned_source_set_digest",
        "pre_run_authority_identity",
        "qualification_runner_identity",
        "preflight_script_identity",
        "preflight_timeout_scale",
        "purpose",
        "pytest_collection",
        "pytest_collection_plugin_identity",
        "pytest_collection_protocol_identity",
        "pytest_scratch",
        "python_identity",
        "resource_admission",
        "resource_admission_source_identity",
        "resource_lock_release_identities",
        "repository_head",
        "repository_root",
        "runner_tool_identity",
        "schema_version",
        "started_at_utc",
        "status",
        "stderr_identity",
        "stdout_identity",
        "timed_out",
    }
    if set(receipt) != expected_keys:
        raise GateAValidationError("full-preflight receipt key set drifted")
    authorizations = receipt["authorizations"]
    if (
        authorizations
        != {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
            "solver_run_authorized": False,
        }
        or receipt["schema_version"] != PREFLIGHT_SCHEMA
        or receipt["purpose"] != PREFLIGHT_PURPOSE
        or receipt["status"] != "PASS"
        or receipt["exit_code"] != 0
        or receipt["timed_out"] is not False
        or receipt["preflight_timeout_scale"] != TIMEOUT_SCALE
        or receipt["authority_ready_identity"] != evidence["authority_ready_identity"]
        or receipt["detached_replay_identity"] != evidence["detached_replay_identity"]
        or receipt["pre_run_authority_identity"] != evidence["pre_run_identity"]
        or receipt["planned_source_set_digest"] != evidence["planned_source_set_digest"]
        or receipt["repository_head"] != evidence["pre_run"]["repository_head"]
        or receipt["repository_root"] != evidence["pre_run"]["repository_root"]
    ):
        raise GateAValidationError("full-preflight receipt is not an exact PASS")
    receipt_directory = Path(snapshot.identity["path"]).parent
    _verify_preflight_publication_commit(
        receipt_identity=snapshot.identity,
        output_root_identity=receipt["output_root_identity"],
    )
    _verify_preflight_output_root(
        receipt_directory=receipt_directory,
        expected_identity=receipt["output_root_identity"],
    )
    _verify_closed_preflight_scratch(
        receipt["pytest_scratch"],
        receipt_directory=receipt_directory,
    )
    sources = evidence["sources"]
    expected_script = _planned_source_identity(
        sources,
        PREFLIGHT_SOURCE_ROLE,
        "preflight script",
    )
    expected_qualification = _planned_source_identity(
        sources,
        QUALIFICATION_SOURCE_ROLE,
        "AB16 preflight qualification runner",
    )
    expected_protocol = _planned_source_identity(
        sources,
        COLLECTION_PROTOCOL_SOURCE_ROLE,
        "AB16 pytest collection protocol",
    )
    expected_plugin = _planned_source_identity(
        sources,
        COLLECTION_PLUGIN_SOURCE_ROLE,
        "AB16 pytest collection plugin",
    )
    expected_resource_admission = _planned_source_identity(
        sources,
        RESOURCE_ADMISSION_SOURCE_ROLE,
        "AB16 resource admission",
    )
    repository = Path(receipt["repository_root"])
    basetemp = Path(receipt["pytest_scratch"]["basetemp_path"])
    try:
        basetemp_relative = basetemp.relative_to(repository)
    except ValueError as exc:
        raise GateAValidationError(
            "full-preflight basetemp is outside its repository"
        ) from exc
    expected_count, expected_sha256, _tracked_files = (
        _head_pytest_collection_authority(
            repository=repository,
            sources=sources,
        )
    )
    expected_arguments = [
        "--repository-root",
        str(repository),
        "--basetemp",
        str(basetemp),
        "--basetemp-relative",
        basetemp_relative.as_posix(),
        "--expected-count",
        str(expected_count),
        "--expected-sha256",
        expected_sha256,
        "--preflight-source",
        str(expected_script["path"]),
        "--collection-protocol-source",
        str(expected_protocol["path"]),
        "--collection-plugin-source",
        str(expected_plugin["path"]),
        "--full",
    ]
    if (
        receipt["preflight_script_identity"] != expected_script
        or receipt["qualification_runner_identity"] != expected_qualification
        or receipt["pytest_collection_protocol_identity"] != expected_protocol
        or receipt["pytest_collection_plugin_identity"] != expected_plugin
        or receipt["resource_admission_source_identity"]
        != expected_resource_admission
        or receipt["python_identity"] != evidence["pre_run"]["tool_identities"]["python3_13"]
        or receipt["runner_tool_identity"] != _verify_current_tool(sources=sources)
        or receipt["command"]
        != {
            "argv": [
                receipt["python_identity"]["path"],
                "-I",
                "-B",
                receipt["qualification_runner_identity"]["path"],
                *expected_arguments,
            ],
            "execution_strategy": PREFLIGHT_EXECUTION_STRATEGY,
            "loader_identity": _loader_identity(),
        }
    ):
        raise GateAValidationError("full-preflight tool/command identity drifted")
    resource_record = receipt["resource_admission"]
    if type(resource_record) is not dict:
        raise GateAValidationError("full-preflight resource admission is malformed")
    lock_check = resource_record.get("lock_check")
    if type(lock_check) is not dict:
        raise GateAValidationError("full-preflight resource lock check is malformed")
    lock_identities = lock_check.get("identities")
    try:
        checked_resource = resource_admission.validate_resource_admission_receipt(
            resource_record,
            expected_stage=resource_admission.FULL_PREFLIGHT,
            expected_lock_identities=lock_identities,
            expected_lock_identity_format=resource_admission.GATE_B_LOCK_IDENTITY_FORMAT,
            expected_observation_context={
                "authority_id": evidence["pre_run_identity"]["sha256"],
                "disk_path": str(repository),
                "kind": "GATE_A_FULL_PREFLIGHT",
                "ordinal": 0,
                "scope_id": evidence["planned_source_set_digest"],
                "sequence": 1,
                "slot": "",
                "target": str(receipt_directory),
            },
        )
    except resource_admission.ResourceAdmissionError as exc:
        raise GateAValidationError(
            f"full-preflight resource admission replay failed: {exc}"
        ) from exc
    if (
        checked_resource != resource_record
        or receipt["resource_lock_release_identities"] != lock_identities
    ):
        raise GateAValidationError(
            "full-preflight resource admission/release join drifted"
        )
    stdout_raw: bytes | None = None
    for field in ("stdout_identity", "stderr_identity"):
        if field == "stdout_identity":
            stdout_raw, observed = verifier.snapshot_bytes(receipt[field]["path"])
        else:
            observed = _snapshot_identity(receipt[field]["path"])
        _same_identity(observed, receipt[field], f"full-preflight {field}")
    assert stdout_raw is not None
    collection = _verify_pytest_collection_stdout(
        stdout_raw,
        repository=Path(receipt["repository_root"]),
        sources=sources,
    )
    if receipt["pytest_collection"] != collection:
        raise GateAValidationError("full-preflight pytest collection binding drifted")
    return receipt, snapshot.identity


def finalize_gate_a(
    *,
    authority_root: Path | str,
    preflight_receipt: Path | str,
    output_path: Path | str,
    approval_id: str,
    target_campaign_dir: Path | str,
    run_nonce: str,
) -> dict[str, object]:
    """Publish one Gate-A PASS that still cannot create a formal campaign."""

    if APPROVAL_ID_RE.fullmatch(approval_id) is None:
        raise GateAValidationError("Gate-A approval_id is invalid")
    if RUN_NONCE_RE.fullmatch(run_nonce) is None:
        raise GateAValidationError("future campaign run nonce is invalid")
    target = _absolute(target_campaign_dir)
    if target.name != run_nonce or target.exists() or target.is_symlink():
        raise GateAValidationError("future campaign target must be absent and match run nonce")
    root = _absolute(authority_root)
    evidence = _verify_drill(root)
    pre_run = evidence["pre_run"]
    sources = evidence["sources"]
    repository = Path(pre_run["repository_root"])
    _reobserve_planned_sources(
        repository_root=repository,
        sources=sources,
        expected_digest=evidence["planned_source_set_digest"],
    )
    observed_head = drill_authority._observe_repository_head(  # noqa: SLF001
        repository,
        sources,
    )
    if observed_head != pre_run["repository_head"]:
        raise GateAValidationError("repository HEAD drifted at Gate-A finalize")
    current_epoch = drill_authority._capture_live_manager_epoch(sources)  # noqa: SLF001
    if current_epoch["manager_epoch"] != pre_run["manager_epoch"]:
        raise GateAValidationError("manager/boot epoch drifted at Gate-A finalize")
    receipt, receipt_identity = _verify_preflight_receipt(
        receipt_path=preflight_receipt,
        evidence=evidence,
    )
    del receipt
    gate_a = {
        "approval_id": approval_id,
        "arm_launch_authorized": False,
        "created_at_utc": _utc_now(),
        "decision": "PASS",
        "disposable_authority_ready_identity": evidence["authority_ready_identity"],
        "disposable_detached_replay_identity": evidence["detached_replay_identity"],
        "formal_campaign_creation_authorized": False,
        "full_preflight_receipt_identity": receipt_identity,
        "gate": "A",
        "history_freeze_replay_identity": pre_run["history_freeze_replay_identity"],
        "manager_epoch": pre_run["manager_epoch"],
        "offline_candidate_only": True,
        "planned_source_set_digest": evidence["planned_source_set_digest"],
        "purpose": GATE_A_PURPOSE,
        "reference_capability_identity": pre_run["reference_capability_identity"],
        "reference_capability_transcript_identity": pre_run["reference_capability_transcript_identity"],
        "repository_head": pre_run["repository_head"],
        "repository_root": pre_run["repository_root"],
        "run_nonce": run_nonce,
        "schema_version": GATE_A_SCHEMA,
        "target_campaign_dir": str(target),
    }
    identity = bootstrap.authority.write_exclusive(
        _absolute(output_path),
        bootstrap.authority.canonical_json(gate_a),
        mode=0o444,
    )
    return {
        "gate_a": gate_a,
        "gate_a_identity": {
            "mode": 0o444,
            **identity,
        },
        "status": "PASS",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preflight = commands.add_parser("record-preflight")
    preflight.add_argument("--authority-root", required=True, type=Path)
    preflight.add_argument("--repository-root", required=True, type=Path)
    preflight.add_argument("--output-dir", required=True, type=Path)
    preflight.add_argument(
        "--resource-lock-fd",
        action="append",
        default=[],
        metavar="ABSOLUTE_PATH=FD",
    )
    finalize = commands.add_parser("finalize")
    finalize.add_argument("--authority-root", required=True, type=Path)
    finalize.add_argument("--preflight-receipt", required=True, type=Path)
    finalize.add_argument("--output", required=True, type=Path)
    finalize.add_argument("--approval-id", required=True)
    finalize.add_argument("--target-campaign-dir", required=True, type=Path)
    finalize.add_argument("--run-nonce", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "record-preflight":
            result = record_full_preflight(
                authority_root=args.authority_root,
                repository_root=args.repository_root,
                output_dir=args.output_dir,
                resource_lock_fds=_owned_resource_lock_fds(args.resource_lock_fd),
            )
        elif args.command == "finalize":
            result = finalize_gate_a(
                authority_root=args.authority_root,
                preflight_receipt=args.preflight_receipt,
                output_path=args.output,
                approval_id=args.approval_id,
                target_campaign_dir=args.target_campaign_dir,
                run_nonce=args.run_nonce,
            )
        else:
            raise GateAValidationError("unknown Gate-A validation command")
    except Exception as exc:
        print(
            json.dumps(
                {
                    "detail": str(exc),
                    "status": "FAIL_CLOSED",
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
