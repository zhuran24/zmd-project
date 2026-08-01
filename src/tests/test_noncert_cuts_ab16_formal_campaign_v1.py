from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
SPEC = importlib.util.spec_from_file_location(
    "_ab16_outer_refunit_closeout_v1_test",
    RESEARCH / "ab16_outer_refunit_closeout_v1.py",
)
assert SPEC is not None and SPEC.loader is not None
HELPER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = HELPER
sys.path.insert(0, str(RESEARCH))
try:
    SPEC.loader.exec_module(HELPER)
    from docs.research.noncert_cuts_ab16_20260724 import (
        ab16_formal_campaign_v1 as FORMAL,
    )
    from docs.research.noncert_cuts_ab16_20260724 import (
        ab16_resource_budget_profile_builder_v1 as PROFILE_BUILDER,
    )
finally:
    sys.path.remove(str(RESEARCH))
STATE = sys.modules["ab16_outer_closeout_state_v1"]


def _identity(tag: str) -> dict[str, object]:
    return {
        "path": f"/evidence/{tag}.json",
        "sha256": hashlib.sha256(tag.encode()).hexdigest(),
        "size_bytes": len(tag),
    }


def _selected_v2_spec(
    tmp_path: Path,
) -> tuple[dict[str, object], list[int], socket.socket, Path]:
    roles = (
        "python",
        "loader",
        "authority",
        "native_helper_wrapper",
        "native_helper",
    )
    modes = {
        "authority": 0o600,
        "loader": 0o600,
        "native_helper": 0o555,
        "native_helper_wrapper": 0o600,
        "python": 0o555,
    }
    retained: list[int] = []
    identities: dict[str, dict[str, object]] = {}
    transport_roles: dict[str, dict[str, object]] = {}
    owner = {
        "pid": os.getpid(),
        "pid_starttime": FORMAL.guardian.read_process_starttime(os.getpid()),
        "uid": os.getuid(),
    }
    for ordinal, role in enumerate(roles):
        path = tmp_path / f"{role}.bin"
        raw = f"{role}-selected-bytes\n".encode()
        path.write_bytes(raw)
        path.chmod(modes[role])
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
        retained.append(descriptor)
        identity = {
            "mode": modes[role],
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
        identities[role] = identity
        transport_roles[role] = {
            "descriptor": descriptor,
            "mode": modes[role],
            "package_path": (
                FORMAL.launch_validator.SELECTED_FD_TRANSPORT_PACKAGE_PATHS[
                    role
                ]
            ),
            "proc_fd_path": f"/proc/{owner['pid']}/fd/{descriptor}",
            "sha256": identity["sha256"],
            "size_bytes": identity["size_bytes"],
        }
    socket_parent = Path(
        tempfile.mkdtemp(prefix="ab16-v2-sock-", dir="/tmp")
    )
    endpoint_path = socket_parent / "budget-broker.sock"
    listener = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
    )
    listener.bind(str(endpoint_path))
    listener.listen(1)
    endpoint_path.chmod(0o600)
    endpoint_stat = os.stat(endpoint_path, follow_symlinks=False)
    transport = {
        "owner": owner,
        "roles": transport_roles,
        "schema_version": (
            FORMAL.launch_validator.SELECTED_FD_TRANSPORT_SCHEMA
        ),
    }
    selected_argument = json.dumps(
        identities,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return (
        {
            "budget_broker_endpoint_identity": {
                "device": endpoint_stat.st_dev,
                "inode": endpoint_stat.st_ino,
                "mode": 0o600,
                "path": str(endpoint_path),
                "uid": os.getuid(),
            },
            "resource_contract": dict(
                FORMAL.launch_validator.OUTER_RESOURCE_CONTRACT
            ),
            "selected_byte_argv": [
                "/proc/self/fd/3",
                "-I",
                "-B",
                "-c",
                "selected-v2-literal",
                "systemd-openfile",
                selected_argument,
            ],
            "selected_fd_transport": transport,
            "unit_name": "ab16-formal-outer-a001.service",
            "working_directory": str(tmp_path),
        },
        retained,
        listener,
        socket_parent,
    )


def _close_selected_v2_spec(
    retained: Sequence[int],
    listener: socket.socket,
    socket_parent: Path,
) -> None:
    listener.close()
    endpoint = socket_parent / "budget-broker.sock"
    if os.path.lexists(endpoint):
        endpoint.unlink()
    socket_parent.rmdir()
    for descriptor in retained:
        os.close(descriptor)


def test_selected_systemd_v2_uses_exact_six_openfile_transport(
    tmp_path: Path,
) -> None:
    spec, retained, listener, socket_parent = _selected_v2_spec(tmp_path)
    try:
        argv = FORMAL.build_selected_systemd_argv(
            systemd_run_path="/usr/bin/systemd-run",
            spec=spec,
        )
        open_files = [
            item
            for item in argv
            if item.startswith("--property=OpenFile=")
        ]
        roles = spec["selected_fd_transport"]["roles"]
        assert argv[argv.index(open_files[0]) - 3 : argv.index(open_files[0])] == [
            "--property=StandardInput=null",
            "--property=StandardOutput=journal",
            "--property=StandardError=journal",
        ]
        assert open_files == [
            (
                "--property=OpenFile="
                f"{roles['python']['proc_fd_path']}:ab16-python:read-only"
            ),
            (
                "--property=OpenFile="
                f"{roles['loader']['proc_fd_path']}:ab16-loader:read-only"
            ),
            (
                "--property=OpenFile="
                f"{roles['authority']['proc_fd_path']}:ab16-authority:read-only"
            ),
            (
                "--property=OpenFile="
                f"{roles['native_helper_wrapper']['proc_fd_path']}:"
                "ab16-native-helper-wrapper:read-only"
            ),
            (
                "--property=OpenFile="
                f"{roles['native_helper']['proc_fd_path']}:"
                "ab16-native-helper:read-only"
            ),
            (
                "--property=OpenFile="
                f"{spec['budget_broker_endpoint_identity']['path']}:"
                "ab16-budget-broker"
            ),
        ]
    finally:
        _close_selected_v2_spec(retained, listener, socket_parent)


@pytest.mark.parametrize("drift", ("fd6-missing", "fd7-drift", "fd8-drift"))
def test_selected_systemd_v2_rejects_missing_or_drifted_transport(
    tmp_path: Path,
    drift: str,
) -> None:
    spec, retained, listener, socket_parent = _selected_v2_spec(tmp_path)
    try:
        if drift == "fd6-missing":
            identities = json.loads(spec["selected_byte_argv"][6])
            identities.pop("native_helper_wrapper")
            spec["selected_byte_argv"][6] = json.dumps(
                identities,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        elif drift == "fd7-drift":
            spec["selected_fd_transport"]["roles"]["native_helper"][
                "proc_fd_path"
            ] = f"/proc/{os.getpid()}/fd/999999"
        else:
            spec["budget_broker_endpoint_identity"]["inode"] += 1
        with pytest.raises(FORMAL.FormalCampaignError):
            FORMAL.build_selected_systemd_argv(
                systemd_run_path="/usr/bin/systemd-run",
                spec=spec,
            )
    finally:
        _close_selected_v2_spec(retained, listener, socket_parent)


def test_direct_nonbudget_broker_connection_mints_no_authority_frame(
    tmp_path: Path,
) -> None:
    spec, retained, listener, socket_parent = _selected_v2_spec(tmp_path)
    accepted: socket.socket | None = None
    connected = -1
    try:
        identities = FORMAL._selected_identities(spec)  # noqa: SLF001
        transport = FORMAL._selected_transport(  # noqa: SLF001
            spec,
            identities,
        )
        assert transport is not None
        connected = FORMAL._connect_selected_broker(transport)  # noqa: SLF001
        accepted, _address = listener.accept()
        accepted.setblocking(False)
        with pytest.raises(BlockingIOError):
            accepted.recv(1)
        assert stat.S_ISSOCK(os.fstat(connected).st_mode)
    finally:
        if connected >= 0:
            os.close(connected)
        if accepted is not None:
            accepted.close()
        _close_selected_v2_spec(retained, listener, socket_parent)


def test_selected_direct_v2_owns_and_closes_fds_three_through_eight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenSelector:
        def register(self, *_args: object) -> None:
            raise RuntimeError("selected-v2-register-fault")

        def close(self) -> None:
            return None

    real_close = os.close
    tracked: set[int] = set()
    close_count: dict[int, int] = {}
    captured_targets: list[int] = []
    peer, child = socket.socketpair(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
    )

    def tracked_close(descriptor: int) -> None:
        if descriptor in tracked:
            close_count[descriptor] = close_count.get(descriptor, 0) + 1
        real_close(descriptor)

    def opened(*_args: object) -> int:
        descriptor = os.open("/dev/null", os.O_RDONLY)
        tracked.add(descriptor)
        return descriptor

    broker_descriptor = child.detach()
    tracked.add(broker_descriptor)
    monkeypatch.setattr(
        FORMAL,
        "_selected_identities",
        lambda _spec: {
            role: {}
            for role in (
                "python",
                "loader",
                "authority",
                "native_helper_wrapper",
                "native_helper",
            )
        },
    )
    monkeypatch.setattr(
        FORMAL,
        "_selected_transport",
        lambda _spec, _identities: {"transport": "v2"},
    )
    monkeypatch.setattr(FORMAL, "_open_selected", opened)
    monkeypatch.setattr(
        FORMAL,
        "_connect_selected_broker",
        lambda _transport: broker_descriptor,
    )
    real_fcntl = FORMAL.fcntl.fcntl

    def duplicate(
        descriptor: int,
        command: int,
        argument: int = 0,
    ) -> int:
        result = real_fcntl(descriptor, command, argument)
        if command == FORMAL.fcntl.F_DUPFD_CLOEXEC:
            tracked.add(result)
        return result

    def spawn(
        _path: str,
        _argv: Sequence[str],
        _env: Mapping[str, str],
        *,
        file_actions: Sequence[tuple[object, ...]],
    ) -> int:
        captured_targets.extend(
            int(action[2])
            for action in file_actions
            if action[0] == os.POSIX_SPAWN_DUP2
            and int(action[2]) in {3, 4, 5, 6, 7, 8}
        )
        return 4242

    monkeypatch.setattr(FORMAL.fcntl, "fcntl", duplicate)
    monkeypatch.setattr(FORMAL.os, "close", tracked_close)
    monkeypatch.setattr(FORMAL.os, "posix_spawn", spawn)
    monkeypatch.setattr(FORMAL.selectors, "DefaultSelector", BrokenSelector)
    monkeypatch.setattr(FORMAL.os, "kill", lambda _pid, _sig: None)
    monkeypatch.setattr(
        FORMAL.os,
        "waitpid",
        lambda pid, _flags: (pid, 0),
    )
    try:
        with pytest.raises(
            RuntimeError,
            match="selected-v2-register-fault",
        ):
            FORMAL.run_selected_direct_result(
                context={
                    "campaign_dir": "/fixture/campaign",
                    "outer_spec": {
                        "selected_byte_argv": [
                            "/proc/self/fd/3",
                            "-I",
                            "-B",
                            "-c",
                            "selected-loader",
                            "direct",
                            "selected-identities",
                        ],
                    },
                },
                role="formal-success-verifier",
                role_argv=("--campaign-dir", "/fixture/campaign"),
                timeout_seconds=1.0,
            )
        assert captured_targets == [3, 4, 5, 6, 7, 8]
        assert close_count == {
            descriptor: 1 for descriptor in tracked
        }
    finally:
        peer.close()


class Campaign:
    starttimes = {41: 9001}

    @staticmethod
    def same_manager_epoch(left: object, right: object) -> bool:
        return left == right

    @classmethod
    def _read_proc_starttime(cls, pid: int) -> int:
        return cls.starttimes.get(pid, 9001)

    @staticmethod
    def validate_manager_epoch_capture_transcript(
        transcript: object,
        *,
        expected_epoch: object,
    ) -> None:
        assert transcript == {"expected_epoch": expected_epoch}


def _boundary(tmp_path: Path) -> Any:
    formal = tmp_path / "formal-campaign-a001"
    formal.mkdir()
    epoch = {"dbus_unique_owner": ":1.42", "boot_id": "b" * 32}
    return SimpleNamespace(
        context={"campaign_module": Campaign, "root_identity": _identity("root")},
        root={"manager_epoch": epoch, "package": {"package_id": "c" * 64}},
        formal_dir=formal,
    )


def test_selected_direct_post_spawn_failure_reaps_once_without_masking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenSelector:
        def register(self, *_args: object) -> None:
            raise RuntimeError("selector-register-fault")

        def close(self) -> None:
            raise RuntimeError("selector-close-fault")

    killed: list[tuple[int, int]] = []
    waited: list[tuple[int, int]] = []
    monkeypatch.setattr(
        FORMAL,
        "_selected_identities",
        lambda _spec: {
            "authority": {},
            "loader": {},
            "python": {},
        },
    )
    monkeypatch.setattr(
        FORMAL,
        "_open_selected",
        lambda *_args: os.open("/dev/null", os.O_RDONLY),
    )
    monkeypatch.setattr(FORMAL.selectors, "DefaultSelector", BrokenSelector)
    monkeypatch.setattr(FORMAL.os, "posix_spawn", lambda *_args, **_kwargs: 4242)
    monkeypatch.setattr(
        FORMAL.os,
        "kill",
        lambda pid, sig: killed.append((pid, sig)),
    )

    def waitpid(pid: int, options: int) -> tuple[int, int]:
        waited.append((pid, options))
        return pid, 0

    monkeypatch.setattr(FORMAL.os, "waitpid", waitpid)
    before = {entry.name for entry in Path("/proc/self/fd").iterdir()}
    with pytest.raises(RuntimeError, match="selector-register-fault"):
        FORMAL.run_selected_direct_result(
            context={
                "campaign_dir": "/fixture/campaign",
                "outer_spec": {
                    "selected_byte_argv": [
                        "/proc/self/fd/3",
                        "-I",
                        "-B",
                        "-c",
                        "selected-loader",
                        "direct",
                        "selected-identities",
                    ],
                },
            },
            role="formal-success-verifier",
            role_argv=("--campaign-dir", "/fixture/campaign"),
            timeout_seconds=1.0,
        )
    after = {entry.name for entry in Path("/proc/self/fd").iterdir()}
    assert killed == [(4242, FORMAL.signal.SIGKILL)]
    assert waited == [(4242, 0)]
    assert after == before


@pytest.mark.parametrize(
    "fault",
    (
        "open-2",
        "open-3",
        "pipe-2",
        "dup-2",
        "dup-3",
        "spawn",
        "high-close",
    ),
)
def test_selected_direct_staged_fd_ownership_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    real_close = os.close
    real_pipe2 = os.pipe2
    real_fcntl = FORMAL.fcntl.fcntl
    tracked: set[int] = set()
    close_count: dict[int, int] = {}
    open_calls = 0
    pipe_calls = 0
    dup_calls = 0
    high_descriptors: list[int] = []
    killed: list[int] = []
    waited: list[int] = []

    def tracked_close(descriptor: int) -> None:
        if descriptor in tracked:
            close_count[descriptor] = close_count.get(descriptor, 0) + 1
        real_close(descriptor)
        if fault == "high-close" and descriptor == high_descriptors[0]:
            raise RuntimeError("fault-high-close")

    def open_selected(*_args: object) -> int:
        nonlocal open_calls
        open_calls += 1
        if fault == f"open-{open_calls}":
            raise RuntimeError(f"fault-{fault}")
        descriptor = os.open("/dev/null", os.O_RDONLY)
        tracked.add(descriptor)
        return descriptor

    def pipe2(flags: int) -> tuple[int, int]:
        nonlocal pipe_calls
        pipe_calls += 1
        if fault == f"pipe-{pipe_calls}":
            raise RuntimeError(f"fault-{fault}")
        descriptors = real_pipe2(flags)
        tracked.update(descriptors)
        return descriptors

    def duplicate(
        descriptor: int,
        command: int,
        argument: int = 0,
    ) -> int:
        nonlocal dup_calls
        if command != FORMAL.fcntl.F_DUPFD_CLOEXEC:
            return real_fcntl(descriptor, command, argument)
        dup_calls += 1
        if fault == f"dup-{dup_calls}":
            raise RuntimeError(f"fault-{fault}")
        duplicate_descriptor = real_fcntl(descriptor, command, argument)
        tracked.add(duplicate_descriptor)
        high_descriptors.append(duplicate_descriptor)
        return duplicate_descriptor

    def spawn(*_args: object, **_kwargs: object) -> int:
        if fault == "spawn":
            raise RuntimeError("fault-spawn")
        return 4242

    monkeypatch.setattr(
        FORMAL,
        "_selected_identities",
        lambda _spec: {"authority": {}, "loader": {}, "python": {}},
    )
    monkeypatch.setattr(FORMAL, "_open_selected", open_selected)
    monkeypatch.setattr(FORMAL.os, "pipe2", pipe2)
    monkeypatch.setattr(FORMAL.fcntl, "fcntl", duplicate)
    monkeypatch.setattr(FORMAL.os, "posix_spawn", spawn)
    monkeypatch.setattr(FORMAL.os, "close", tracked_close)
    monkeypatch.setattr(
        FORMAL.os,
        "kill",
        lambda pid, _signal: killed.append(pid),
    )
    monkeypatch.setattr(
        FORMAL.os,
        "waitpid",
        lambda pid, _flags: waited.append(pid) or (pid, 0),
    )

    before = {entry.name for entry in Path("/proc/self/fd").iterdir()}
    with pytest.raises(RuntimeError, match=f"fault-{fault}"):
        FORMAL.run_selected_direct_result(
            context={
                "campaign_dir": "/fixture/campaign",
                "outer_spec": {
                    "selected_byte_argv": [
                        "/proc/self/fd/3",
                        "-I",
                        "-B",
                        "-c",
                        "selected-loader",
                        "direct",
                        "selected-identities",
                    ],
                },
            },
            role="formal-success-verifier",
            role_argv=("--campaign-dir", "/fixture/campaign"),
            timeout_seconds=1.0,
        )
    after = {entry.name for entry in Path("/proc/self/fd").iterdir()}
    assert after == before
    assert close_count == {descriptor: 1 for descriptor in tracked}
    if fault == "high-close":
        assert killed == [4242]
        assert waited == [4242]
    else:
        assert killed == []
        assert waited == []


def test_selected_direct_cleanup_faults_do_not_mask_original(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenSelector:
        def register(self, *_args: object) -> None:
            raise RuntimeError("original-selector-fault")

        def close(self) -> None:
            raise RuntimeError("cleanup-selector-fault")

    kill_calls: list[int] = []
    wait_calls: list[int] = []
    monkeypatch.setattr(
        FORMAL,
        "_selected_identities",
        lambda _spec: {"authority": {}, "loader": {}, "python": {}},
    )
    monkeypatch.setattr(
        FORMAL,
        "_open_selected",
        lambda *_args: os.open("/dev/null", os.O_RDONLY),
    )
    monkeypatch.setattr(FORMAL.selectors, "DefaultSelector", BrokenSelector)
    monkeypatch.setattr(FORMAL.os, "posix_spawn", lambda *_args, **_kwargs: 4242)

    def fail_kill(pid: int, _signal: int) -> None:
        kill_calls.append(pid)
        raise RuntimeError("cleanup-kill-fault")

    def fail_wait(pid: int, _flags: int) -> tuple[int, int]:
        wait_calls.append(pid)
        if len(wait_calls) == 1:
            raise InterruptedError("cleanup-wait-interrupted")
        return pid, 0

    monkeypatch.setattr(FORMAL.os, "kill", fail_kill)
    monkeypatch.setattr(FORMAL.os, "waitpid", fail_wait)
    before = {entry.name for entry in Path("/proc/self/fd").iterdir()}
    with pytest.raises(RuntimeError, match="original-selector-fault"):
        FORMAL.run_selected_direct_result(
            context={
                "campaign_dir": "/fixture/campaign",
                "outer_spec": {
                    "selected_byte_argv": [
                        "/proc/self/fd/3",
                        "-I",
                        "-B",
                        "-c",
                        "selected-loader",
                        "direct",
                        "selected-identities",
                    ],
                },
            },
            role="formal-success-verifier",
            role_argv=("--campaign-dir", "/fixture/campaign"),
            timeout_seconds=1.0,
        )
    after = {entry.name for entry in Path("/proc/self/fd").iterdir()}
    assert after == before
    assert kill_calls == [4242]
    assert wait_calls == [4242, 4242]


def test_open_selected_close_fault_preserves_validation_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = tmp_path / "selected.py"
    selected.write_text("pass\n", encoding="utf-8")
    real_close = os.close
    monkeypatch.setattr(
        FORMAL.os,
        "fstat",
        lambda _descriptor: (_ for _ in ()).throw(
            RuntimeError("selected-validation-fault")
        ),
    )

    def close_then_fail(descriptor: int) -> None:
        real_close(descriptor)
        raise RuntimeError("selected-close-fault")

    monkeypatch.setattr(FORMAL.os, "close", close_then_fail)
    before = {entry.name for entry in Path("/proc/self/fd").iterdir()}
    with pytest.raises(RuntimeError, match="selected-validation-fault"):
        FORMAL._open_selected(  # noqa: SLF001
            {"path": str(selected)},
            "fixture",
        )
    after = {entry.name for entry in Path("/proc/self/fd").iterdir()}
    assert after == before


class Store:
    def __init__(
        self,
        fail: str = "",
        *,
        return_before_fail: bool = False,
        uncertain_before_fail: bool = False,
    ) -> None:
        self.fail = fail
        self.return_before_fail = return_before_fail
        self.uncertain_before_fail = uncertain_before_fail
        self.records: dict[str, dict[str, Any]] = {}
        self.attempts: dict[str, int] = {}

    @staticmethod
    def _identity(path: Path | str) -> dict[str, object]:
        name = Path(path).name
        return {
            "path": str(path),
            "sha256": hashlib.sha256(name.encode()).hexdigest(),
            "size_bytes": len(name),
        }

    def publish(
        self,
        path: Path | str,
        value: Any,
        _label: str,
        *,
        publication: Any | None = None,
    ) -> dict[str, object]:
        name = Path(path).name
        self.attempts[name] = self.attempts.get(name, 0) + 1
        identity = self._identity(path)
        if name == self.fail:
            if publication is not None and self.uncertain_before_fail:
                publication.note_publication_may_have_happened()
            if publication is not None and self.return_before_fail:
                publication.note_returned(identity)
            raise OSError(f"injected {name} publication failure")
        if name in self.records:
            raise FileExistsError(name)
        if publication is not None:
            publication.note_returned(identity)
        self.records[name] = dict(value)
        if publication is not None:
            publication.note_recorded(identity)
        return identity

    def document(
        self,
        path: Path | str,
        _label: str,
    ) -> tuple[dict[str, Any], dict[str, object]]:
        name = Path(path).name
        return dict(self.records[name]), self._identity(path)


class FakeReference:
    def __init__(self, fault: str = "") -> None:
        self.fault = fault
        self.events: list[str] = []
        self.client = ":1.7"
        self.owner = ":1.42"

    def _event(self, name: str) -> None:
        self.events.append(name)
        if self.fault == name:
            raise RuntimeError(f"uncertain {name}")

    def acquire(self, *, unit_name: str, **_: object) -> dict[str, str]:
        self._event("acquire")
        return {
            "client_unique_name": self.client,
            "manager_owner_after": self.owner,
            "manager_owner_before": self.owner,
            "unit_name": unit_name,
        }

    def verify(self, *, expected_manager_owner: str) -> dict[str, str]:
        self._event("verify")
        return {
            "client_unique_name": self.client,
            "manager_owner": expected_manager_owner,
            "unit_name": "outer.service",
        }

    def release(self, *, unit_name: str, **_: object) -> dict[str, str]:
        self._event("release")
        return {
            "client_unique_name": self.client,
            "manager_owner_after": self.owner,
            "manager_owner_before": self.owner,
            "unit_name": unit_name,
        }

    def verify_released(
        self,
        *,
        expected_manager_owner: str,
    ) -> dict[str, object]:
        self._event("verify_released")
        return {
            "client_unique_name": self.client,
            "library_identity": _identity("libsystemd"),
            "manager_owner": expected_manager_owner,
            "reference_held": False,
        }

    def close(self) -> None:
        self._event("close")

    def abort_close(self) -> bool:
        self._event("abort_close")
        return self.fault != "abort_false"


def _lock_evidence() -> list[dict[str, object]]:
    return [
        {"device": 7, "inode": index + 10, "path": path, "uid": os.getuid()}
        for index, path in enumerate(HELPER.LOCK_PATHS)
    ]


def _formal_resource_fixture(tmp_path: Path) -> dict[str, object]:
    members = {
        PROFILE_BUILDER.BUILDER_SOURCE_RELATIVE_PATH: (
            RESEARCH / "ab16_resource_budget_profile_builder_v1.py"
        ).stat().st_size,
        PROFILE_BUILDER.PROFILE_RELATIVE_PATH: (
            PROFILE_BUILDER.PROFILE_SELF_MAXIMUM_BYTES
        ),
        "PROJECT_LOCK.md": (ROOT / "PROJECT_LOCK.md").stat().st_size,
        "src/example.py": 17,
    }
    profile = PROFILE_BUILDER.build_profile(
        repository_root=ROOT,
        repository_members=members,
        execution_surface_sha256="f" * 64,
        profile_id="ab16-formal-resource-gate-fixture-v1",
        launch_ready=True,
        launch_ready_acknowledgement=(
            PROFILE_BUILDER.LAUNCH_READY_ACKNOWLEDGEMENT
        ),
    )
    raw = PROFILE_BUILDER.canonical_json(profile)
    profile_path = tmp_path / "formal-resource-profile.json"
    if profile_path.exists():
        assert profile_path.read_bytes() == raw
    else:
        profile_path.write_bytes(raw)
        profile_path.chmod(0o444)
    profile_identity = {
        "mode": 0o444,
        "path": str(profile_path.absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }
    bundle_record = {
        "fixture": "independently-validated-calibration-bundle"
    }
    bundle_raw = json.dumps(
        bundle_record,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode() + b"\n"
    bundle_identity = {
        "path": str((tmp_path / "calibration-bundle.json").absolute()),
        "sha256": hashlib.sha256(bundle_raw).hexdigest(),
        "size_bytes": len(bundle_raw),
    }
    tool_identities = {
        role: {
            "sha256": hashlib.sha256(role.encode()).hexdigest(),
            "size_bytes": len(role),
        }
        for role in FORMAL.resource_admission.CALIBRATION_TOOL_ROLES
    }
    authority_context = {
        "resource_budget_profile_identity": profile_identity,
        "resource_calibration_authorization_bundles": {
            FORMAL.resource_admission.FORMAL_ORGANIC_ARM: {
                "identity": bundle_identity,
                "record": bundle_record,
            }
        },
        "calibration_tool_content_identities": tool_identities,
    }
    prospective = FORMAL._prospective_resource_authority(  # noqa: SLF001
        authority_context
    )
    return {
        "authority_context": authority_context,
        "prospective": prospective,
    }


@contextmanager
def _accept_fixture_calibration() -> Iterator[None]:
    resource = FORMAL.resource_admission
    live_baseline = resource._same_uid_process_baseline(  # noqa: SLF001
        (),
        mode=resource.SAME_UID_BASELINE_LIVE_MODE,
    )
    with (
        mock.patch.object(
            resource,
            "validate_calibration_authorization_bundle",
            side_effect=lambda value, **_kwargs: dict(value),
        ),
        mock.patch.object(
            resource,
            "_same_uid_conflicts_with_baseline",
            return_value=([], [], live_baseline),
        ),
    ):
        yield


def _formal_resource_passing_measurements(
    prospective: Mapping[str, object],
) -> dict[str, int]:
    profile = FORMAL.resource_admission._validated_prospective_profile(  # noqa: SLF001
        FORMAL.resource_admission.FORMAL_ORGANIC_ARM,
        enforced_budget_profile=prospective["enforced_budget_profile"],
        enforced_budget_profile_identity=(
            prospective["enforced_budget_profile_identity"]
        ),
    )
    requirements = profile["requirements"]
    assert isinstance(requirements, dict)
    limits = profile["runtime_safety_limits"]
    assert isinstance(limits, dict)
    memory = requirements["memory"]["minimum_available_bytes"]
    usable_memory = (
        memory - requirements["memory"]["host_reserve_bytes"]
    )
    usable_swap = max(0, limits["memory_max_bytes"] - usable_memory)
    swap = (
        requirements["swap"]["host_reserve_bytes"] + usable_swap
        if usable_swap
        else 0
    )
    return {
        "disk": requirements["disk"]["minimum_available_bytes"],
        "memory": memory,
        "swap": swap,
    }


def _formal_resource_receipt(
    tmp_path: Path,
    *,
    disk_delta: int = 0,
    memory_delta: int = 0,
    swap_delta: int = 0,
    conflicts: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    fixture = _formal_resource_fixture(tmp_path)
    prospective = fixture["prospective"]
    assert isinstance(prospective, dict)
    passing = _formal_resource_passing_measurements(prospective)
    observation_context = {
        "authority_id": "a" * 64,
        "disk_path": str(tmp_path.absolute()),
        "kind": "FORMAL_INITIAL_POST_LOCK",
        "ordinal": 0,
        "scope_id": "b" * 64,
        "sequence": 0,
        "slot": "",
        "target": str(tmp_path / "formal-attempt-a001"),
    }
    authority_context = fixture["authority_context"]
    assert isinstance(authority_context, dict)
    with _accept_fixture_calibration():
        return FORMAL.validate_resource_gate(
            tmp_path,
            authority_context=authority_context,
            lock_identities=_lock_evidence(),
            observation_context=observation_context,
            meminfo={
                "MemAvailable": passing["memory"] + memory_delta,
                "SwapFree": passing["swap"] + swap_delta,
            },
            disk_free=passing["disk"] + disk_delta,
            conflicts=conflicts,
            allowed_same_uid_processes=(),
        )


def test_formal_resource_gate_accepts_exact_stage_threshold_and_records_receipt(
    tmp_path: Path,
) -> None:
    receipt = _formal_resource_receipt(tmp_path)
    resource = FORMAL.resource_admission

    assert set(receipt) == {
        "authority_scope",
        "authorizations",
        "calibration_authorization_bundle",
        "calibration_authorization_bundle_identity",
        "created_at_utc",
        "disk_target",
        "hard_cap_feasibility",
        "headroom",
        "lock_check",
        "measurements",
        "observation_context",
        "observation_context_sha256",
        "profile",
        "schema_version",
        "stage",
        "status",
    }
    assert (
        receipt["schema_version"]
        == resource.PROSPECTIVE_RESOURCE_ADMISSION_SCHEMA
    )
    assert receipt["stage"] == resource.FORMAL_ORGANIC_ARM
    assert receipt["status"] == "PASS"
    assert receipt["headroom"] == {
        "disk_bytes_above_minimum": 0,
        "memory_bytes_above_minimum": 0,
        "swap_bytes_above_minimum": 15 * resource.GIB,
        "swap_bytes_usable_for_combined_capacity": 11 * resource.GIB,
    }
    assert receipt["lock_check"] == {
        "checked_after_acquisition": True,
        "identities": _lock_evidence(),
        "identity_format": resource.FORMAL_LOCK_IDENTITY_FORMAT,
        "paths": list(resource.LOCK_PATHS),
    }
    profile = receipt["profile"]
    assert profile["basis"]["classification"] == "CONSERVATIVE_TEMPORARY"
    assert profile["basis"]["stage_peak_receipt_count"] == 0
    assert profile["basis"]["warning"] == (
        "TEMPORARY_PROFILE_NOT_A_STAGE_PEAK_MEASUREMENT"
    )
    assert profile["runtime_safety_limits"] == {
        "applies": True,
        "memory_high_bytes": 35 * resource.GIB,
        "memory_max_bytes": 39 * resource.GIB,
        "memory_swap_max_bytes": 16 * resource.GIB,
        "scope": "ONE_SERIAL_ORGANIC_ARM_CGROUP",
    }
    assert receipt["hard_cap_feasibility"] == {
        "applies": True,
        "memory_after_host_reserve_bytes": 28 * resource.GIB,
        "memory_max_bytes": 39 * resource.GIB,
        "planned_memory_peak_bytes": 28 * resource.GIB,
        "swap_after_host_reserve_capped_bytes": 11 * resource.GIB,
        "total_capacity_for_memory_max_bytes": 39 * resource.GIB,
    }
    fixture = _formal_resource_fixture(tmp_path)
    prospective = fixture["prospective"]
    assert isinstance(prospective, dict)
    with _accept_fixture_calibration():
        assert resource.validate_prospective_resource_admission_receipt(
            receipt,
            expected_stage=resource.FORMAL_ORGANIC_ARM,
            expected_lock_identities=_lock_evidence(),
            expected_lock_identity_format=resource.FORMAL_LOCK_IDENTITY_FORMAT,
            expected_observation_context=receipt["observation_context"],
            **prospective,
        ) == receipt


@pytest.mark.parametrize(
    "dimension,kwargs",
    (
        ("disk", {"disk_delta": -1}),
        ("memory", {"memory_delta": -1}),
    ),
)
def test_formal_resource_gate_rejects_each_threshold_minus_one(
    tmp_path: Path,
    dimension: str,
    kwargs: dict[str, int],
) -> None:
    with pytest.raises(
        FORMAL.FormalCampaignError,
        match=rf"RESOURCE_HEADROOM_INSUFFICIENT: .*{dimension}",
    ):
        _formal_resource_receipt(tmp_path, **kwargs)


def test_formal_resource_gate_rejects_insufficient_combined_capacity(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        FORMAL.FormalCampaignError,
        match="RESOURCE_HARD_CAP_FEASIBILITY_FAILED",
    ):
        _formal_resource_receipt(tmp_path, swap_delta=-1)


def test_formal_resource_gate_accepts_high_ram_without_free_swap(
    tmp_path: Path,
) -> None:
    resource = FORMAL.resource_admission
    fixture = _formal_resource_fixture(tmp_path)
    prospective = fixture["prospective"]
    authority_context = fixture["authority_context"]
    assert isinstance(prospective, dict)
    assert isinstance(authority_context, dict)
    passing = _formal_resource_passing_measurements(prospective)
    profile = prospective["enforced_budget_profile"]
    assert isinstance(profile, dict)
    formal_profile = resource._validated_prospective_profile(  # noqa: SLF001
        resource.FORMAL_ORGANIC_ARM,
        enforced_budget_profile=profile,
        enforced_budget_profile_identity=(
            prospective["enforced_budget_profile_identity"]
        ),
    )
    memory_requirement = formal_profile["requirements"]["memory"]
    memory_available = (
        formal_profile["runtime_safety_limits"]["memory_max_bytes"]
        + memory_requirement["host_reserve_bytes"]
    )
    with _accept_fixture_calibration():
        receipt = FORMAL.validate_resource_gate(
            tmp_path,
            authority_context=authority_context,
            lock_identities=_lock_evidence(),
            observation_context={
                "authority_id": "a" * 64,
                "disk_path": str(tmp_path.absolute()),
                "kind": "FORMAL_INITIAL_POST_LOCK",
                "ordinal": 0,
                "scope_id": "b" * 64,
                "sequence": 0,
                "slot": "",
                "target": str(tmp_path / "formal-attempt-a001"),
            },
            meminfo={
                "MemAvailable": memory_available,
                "SwapFree": 0,
            },
            disk_free=passing["disk"],
            conflicts=[],
            allowed_same_uid_processes=(),
        )
    assert receipt["status"] == "PASS"
    assert receipt["hard_cap_feasibility"][
        "swap_after_host_reserve_capped_bytes"
    ] == 0


def test_formal_resource_gate_rejects_same_uid_conflict(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        FORMAL.FormalCampaignError,
        match="RESOURCE_CONFLICT_DETECTED",
    ):
        _formal_resource_receipt(
            tmp_path,
            conflicts=[
                {
                    "command": "python preflight_gate.py --full",
                    "pid": 4242,
                    "starttime": 31337,
                }
            ],
        )


@pytest.mark.parametrize(
    "failure_code,mem_available,conflicts",
    (
        ("RESOURCE_HEADROOM_INSUFFICIENT", "MINUS_ONE", []),
        (
            "RESOURCE_CONFLICT_DETECTED",
            "EXACT",
            [
                {
                    "command": "python preflight_gate.py --full",
                    "pid": 4242,
                    "starttime": 31337,
                }
            ],
        ),
    ),
)
def test_launch_reevaluation_remeasures_after_receipt_and_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_code: str,
    mem_available: str,
    conflicts: list[dict[str, object]],
) -> None:
    resource = FORMAL.resource_admission
    expected = _formal_resource_receipt(tmp_path)
    fixture = _formal_resource_fixture(tmp_path)
    prospective = fixture["prospective"]
    assert isinstance(prospective, dict)
    passing = _formal_resource_passing_measurements(prospective)
    monkeypatch.setattr(resource, "_open_launch_lock_probes", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(resource, "_revalidate_launch_lock_probes", lambda _opened: None)

    def close_probes(
        _opened: object,
        *,
        primary: BaseException | None,
    ) -> None:
        if primary is not None:
            raise primary

    monkeypatch.setattr(resource, "_close_launch_lock_probes", close_probes)
    with pytest.raises(resource.ResourceAdmissionError, match=failure_code):
        with _accept_fixture_calibration():
            resource.reevaluate_prospective_resource_admission_for_launch(
                expected,
                **prospective,
                meminfo={
                    "MemAvailable": (
                        passing["memory"] - 1
                        if mem_available == "MINUS_ONE"
                        else passing["memory"]
                    ),
                    "SwapFree": passing["swap"],
                },
                disk_free=passing["disk"],
                conflicts=conflicts,
            )


def test_launch_reevaluation_receipt_strictly_replays_prelaunch_contract(
    tmp_path: Path,
) -> None:
    resource = FORMAL.resource_admission
    expected = _formal_resource_receipt(tmp_path)
    fixture = _formal_resource_fixture(tmp_path)
    prospective = fixture["prospective"]
    assert isinstance(prospective, dict)
    passing = _formal_resource_passing_measurements(prospective)
    with _accept_fixture_calibration():
        final = resource.evaluate_prospective_resource_admission(
            tmp_path,
            stage=resource.FORMAL_ORGANIC_ARM,
            lock_identities=_lock_evidence(),
            lock_identity_format=resource.FORMAL_LOCK_IDENTITY_FORMAT,
            observation_context=expected["observation_context"],
            **prospective,
            meminfo={
                "MemAvailable": passing["memory"] + 1,
                "SwapFree": passing["swap"] + 1,
            },
            disk_free=passing["disk"] + 1,
            conflicts=None,
        )
        assert resource.validate_prospective_launch_resource_reevaluation(
            final,
            expected_receipt=expected,
            **prospective,
        ) == final

    tampered = copy.deepcopy(final)
    tampered["measurements"]["mem_available_bytes"] += 1
    with pytest.raises(
        resource.ResourceAdmissionError,
        match="RESOURCE_RECEIPT_INVALID",
    ):
        with _accept_fixture_calibration():
            resource.validate_prospective_launch_resource_reevaluation(
                tampered,
                expected_receipt=expected,
                **prospective,
            )


def test_formal_resource_observation_contexts_are_unique_across_all_launches(
    tmp_path: Path,
) -> None:
    context = {
        "campaign_dir": str(tmp_path),
        "campaign_root_identity": _identity("campaign-root"),
    }
    admission_identity = _identity("admission")
    selection_identity = _identity("selection")
    initial = FORMAL._resource_observation_context(  # noqa: SLF001
        context,
        authority_identity=admission_identity,
        kind="FORMAL_INITIAL_POST_LOCK",
        target=str(tmp_path / "formal-attempt-a001"),
    )
    outer = FORMAL._resource_observation_context(  # noqa: SLF001
        context,
        authority_identity=selection_identity,
        kind="FORMAL_OUTER_PRELAUNCH",
        target="ab16-formal-outer-a001.service",
    )
    arms = [
        FORMAL._resource_observation_context(  # noqa: SLF001
            context,
            authority_identity=selection_identity,
            kind="FORMAL_ORGANIC_ARM_PRELAUNCH",
            target=f"ab16-formal-{slot}.service",
            ordinal=ordinal,
            slot=slot,
        )
        for ordinal, slot in enumerate(FORMAL.ARM_SEQUENCE, start=1)
    ]
    observations = [initial, outer, *arms]

    assert len(observations) == 18
    assert len({tuple(sorted(item.items())) for item in observations}) == 18
    assert [item["sequence"] for item in observations] == list(range(18))
    assert initial["authority_id"] == admission_identity["sha256"]
    assert all(
        item["authority_id"] == selection_identity["sha256"]
        for item in observations[1:]
    )
    assert all(
        item["scope_id"] == context["campaign_root_identity"]["sha256"]
        for item in observations
    )
    assert all(item["disk_path"] == str(tmp_path.absolute()) for item in observations)
    assert [item["slot"] for item in arms] == list(FORMAL.ARM_SEQUENCE)
    assert [item["ordinal"] for item in arms] == list(range(1, 17))


def test_formal_resource_allowlist_is_exactly_supervisor_plus_guardian(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = {"pid": 4242, "starttime": 31337}
    supervisor = {"pid": os.getpid(), "starttime": 31336}
    state = FORMAL.SupervisorState()
    state.guardian = SimpleNamespace(
        ready={"guardian_process_identity": copy.deepcopy(actor)}
    )
    monkeypatch.setattr(
        FORMAL,
        "_process_identity",
        lambda pid: dict(actor if pid == actor["pid"] else supervisor),
    )

    assert FORMAL._formal_resource_allowlist(state) == [  # noqa: SLF001
        supervisor,
        actor,
    ]
    assert state.guardian.ready == {"guardian_process_identity": actor}

    monkeypatch.setattr(
        FORMAL,
        "_process_identity",
        lambda pid: {"pid": pid, "starttime": 31338},
    )
    with pytest.raises(
        FORMAL.FormalCampaignError,
        match="allowlist identity is no longer live",
    ):
        FORMAL._formal_resource_allowlist(state)  # noqa: SLF001

    state.guardian.ready = {
        "guardian_process_identity": {
            **actor,
            "unverified_extra": True,
        }
    }
    with pytest.raises(
        FORMAL.FormalCampaignError,
        match="allowlist identity is malformed",
    ):
        FORMAL._formal_resource_allowlist(state)  # noqa: SLF001


def test_outer_prelaunch_transmits_ready_allowlist_and_rechecks_retained_locks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = {"pid": 4242, "starttime": 31337}
    supervisor = {"pid": os.getpid(), "starttime": 31336}
    locks = _lock_evidence()
    selection_identity = _identity("selection")
    state = FORMAL.SupervisorState()
    state.selection_identity = selection_identity
    state.selection = {
        "lock_identities": copy.deepcopy(locks),
        "outer_spec": {
            "receipt_paths": {
                "outer_prelaunch": str(tmp_path / "outer-prelaunch.json")
            },
            "unit_name": "ab16-formal-outer-a001.service",
        },
    }
    state.guardian = SimpleNamespace(
        ready={"guardian_process_identity": copy.deepcopy(actor)}
    )
    resource_calls: list[dict[str, object]] = []
    publications: list[dict[str, object]] = []

    class Host:
        lock_calls = 0

        @classmethod
        def lock_evidence(cls) -> list[dict[str, object]]:
            cls.lock_calls += 1
            return copy.deepcopy(locks)

        @staticmethod
        def show(_unit_name: str) -> dict[str, str]:
            return dict(FORMAL.closeout_helper.ABSENT)

    def validate_resource(
        path: Path | str,
        *,
        authority_context: Mapping[str, object],
        lock_identities: list[dict[str, object]],
        observation_context: dict[str, object],
        allowed_same_uid_processes: list[dict[str, int]],
    ) -> dict[str, object]:
        assert path == str(tmp_path)
        assert authority_context["campaign_dir"] == str(tmp_path)
        assert lock_identities == locks
        assert allowed_same_uid_processes == [supervisor, actor]
        resource_calls.append(copy.deepcopy(observation_context))
        return {
            "observation_context": copy.deepcopy(observation_context),
            "status": "PASS",
        }

    def publish_phase(
        _attempt: object,
        _store: object,
        **kwargs: object,
    ) -> dict[str, object]:
        publications.append(copy.deepcopy(kwargs))
        return _identity("outer-prelaunch")

    monkeypatch.setattr(
        FORMAL,
        "_process_identity",
        lambda pid: dict(actor if pid == actor["pid"] else supervisor),
    )
    monkeypatch.setattr(FORMAL, "validate_resource_gate", validate_resource)
    monkeypatch.setattr(FORMAL, "_publish_tracked_phase", publish_phase)
    monkeypatch.setattr(FORMAL, "send_ledger_update", lambda *_args, **_kwargs: None)

    identity = FORMAL._publish_outer_prelaunch(  # noqa: SLF001
        context={
            "campaign_dir": str(tmp_path),
            "campaign_root_identity": _identity("root"),
            "manager_epoch": {},
            "package_id": "c" * 64,
        },
        state=state,
        store=SimpleNamespace(),
        host=Host(),  # type: ignore[arg-type]
    )

    expected_context = {
        "authority_id": selection_identity["sha256"],
        "disk_path": str(tmp_path.absolute()),
        "kind": "FORMAL_OUTER_PRELAUNCH",
        "ordinal": 0,
        "scope_id": _identity("root")["sha256"],
        "sequence": 1,
        "slot": "",
        "target": "ab16-formal-outer-a001.service",
    }
    assert identity == _identity("outer-prelaunch")
    assert resource_calls == [expected_context]
    assert Host.lock_calls == 2
    assert len(publications) == 1
    record = publications[0]["record"]
    assert record["resource_admission"]["observation_context"] == expected_context
    validator_kwargs = publications[0]["validator_kwargs"]
    assert validator_kwargs["expected_observation_context"] == expected_context
    assert validator_kwargs["expected_allowed_same_uid_processes"] == [
        supervisor,
        actor,
    ]
    assert state.attempt.outer_prelaunch_identity == identity
    assert state.ledger is not None


@pytest.mark.parametrize("failure_code", (None, "MEMORY", "CONFLICT"))
def test_outer_pinned_host_reevaluates_live_resources_at_subprocess_edge(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_code: str | None,
) -> None:
    executable = tmp_path / "systemd-run"
    executable.write_bytes(b"fixture-systemd-run\n")
    executable.chmod(0o755)
    raw = executable.read_bytes()
    host = HELPER.PinnedHost(
        SimpleNamespace(
            root={
                "authority_tools": {
                    "systemd_run": {
                        "path": str(executable),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "size_bytes": len(raw),
                    }
                }
            }
        ),
        {},
    )
    events: list[str] = []
    receipt = {"schema_version": "fixture-resource-admission"}

    def lock_evidence() -> list[dict[str, object]]:
        events.append("locks")
        return _lock_evidence()

    def owner_check() -> None:
        events.append("guardian")

    final_receipt = {"schema_version": "fixture-final-resource-admission"}

    def reevaluate(observed: object) -> dict[str, object]:
        assert observed is receipt
        events.append("reevaluate")
        if failure_code == "MEMORY":
            raise HELPER.resource_admission.ResourceAdmissionError(
                "RESOURCE_HEADROOM_INSUFFICIENT",
                "memory=min-1",
            )
        if failure_code == "CONFLICT":
            raise HELPER.resource_admission.ResourceAdmissionError(
                "RESOURCE_CONFLICT_DETECTED",
                "same-UID conflict injected",
            )
        return final_receipt

    def run(
        command: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[bytes]:
        events.append("subprocess")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(host, "lock_evidence", lock_evidence)
    monkeypatch.setattr(
        HELPER.resource_admission,
        "reevaluate_resource_admission_for_launch",
        reevaluate,
    )
    monkeypatch.setattr(HELPER.subprocess, "run", run)

    if failure_code is not None:
        with pytest.raises(
            HELPER.resource_admission.ResourceAdmissionError,
            match=(
                "RESOURCE_HEADROOM_INSUFFICIENT"
                if failure_code == "MEMORY"
                else "RESOURCE_CONFLICT_DETECTED"
            ),
        ):
            host.run(
                ["--user", "--unit=outer.service"],
                role="systemd_run",
                launch_resource_admission=receipt,
                launch_owner_check=owner_check,
            )
        assert events == ["locks", "guardian", "reevaluate"]
    else:
        completed = host.run(
            ["--user", "--unit=outer.service"],
            role="systemd_run",
            launch_resource_admission=receipt,
            launch_owner_check=owner_check,
        )
        assert completed.returncode == 0
        assert events == ["locks", "guardian", "reevaluate", "subprocess"]
        assert host.take_final_launch_resource_admission() == final_receipt
        host.run(
            ["--user", "--unit=second.service"],
            role="systemd_run",
            launch_resource_admission=receipt,
            launch_owner_check=owner_check,
        )
        assert events == [
            "locks",
            "guardian",
            "reevaluate",
            "subprocess",
            "locks",
            "guardian",
            "reevaluate",
            "subprocess",
        ]
        assert host.take_final_launch_resource_admission() == final_receipt


@pytest.mark.parametrize(
    "failure_point",
    ("pending", "subprocess", "post_execution_verification"),
)
def test_outer_pinned_host_blocks_unconsumed_launch_before_another_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
) -> None:
    executable = tmp_path / "systemd-run"
    executable.write_bytes(b"fixture-systemd-run\n")
    executable.chmod(0o755)
    raw = executable.read_bytes()
    host = HELPER.PinnedHost(
        SimpleNamespace(
            root={
                "authority_tools": {
                    "systemd_run": {
                        "path": str(executable),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "size_bytes": len(raw),
                    }
                }
            }
        ),
        {},
    )
    receipt = {"schema_version": "fixture-resource-admission"}
    final_receipt = {"schema_version": "fixture-final-resource-admission"}
    events: list[str] = []
    monkeypatch.setattr(
        host,
        "lock_evidence",
        lambda: events.append("locks") or _lock_evidence(),
    )

    def owner_check() -> None:
        events.append("guardian")

    def reevaluate(observed: object) -> dict[str, object]:
        assert observed is receipt
        events.append("reevaluate")
        return final_receipt

    def run(
        command: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[bytes]:
        events.append("subprocess")
        if failure_point == "subprocess":
            raise subprocess.TimeoutExpired(command, 1.0)
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(
        HELPER.resource_admission,
        "reevaluate_resource_admission_for_launch",
        reevaluate,
    )
    monkeypatch.setattr(HELPER.subprocess, "run", run)
    if failure_point == "post_execution_verification":
        real_fstat = HELPER.os.fstat
        fstat_calls = 0

        def fail_second_fstat(descriptor: int) -> os.stat_result:
            nonlocal fstat_calls
            fstat_calls += 1
            if fstat_calls == 2:
                raise RuntimeError("post-execution retained-FD fault")
            return real_fstat(descriptor)

        monkeypatch.setattr(HELPER.os, "fstat", fail_second_fstat)
    expected_match: str | None
    if failure_point == "pending":
        host._final_launch_resource_admission = final_receipt  # noqa: SLF001
        expected_exception: type[BaseException] = HELPER.OuterCloseoutError
        expected_match = "prior launch resource admission remains unconsumed"
    elif failure_point == "subprocess":
        expected_exception = subprocess.TimeoutExpired
        expected_match = None
    else:
        expected_exception = RuntimeError
        expected_match = "post-execution retained-FD fault"

    with pytest.raises(expected_exception, match=expected_match):
        host.run(
            ["--user", "--unit=outer.service"],
            role="systemd_run",
            launch_resource_admission=receipt,
            launch_owner_check=owner_check,
        )
    first_events = list(events)
    with pytest.raises(
        HELPER.OuterCloseoutError,
        match="prior launch resource admission remains unconsumed",
    ):
        host.run(
            ["--user", "--unit=retry.service"],
            role="systemd_run",
            launch_resource_admission=receipt,
            launch_owner_check=owner_check,
        )

    assert events == first_events
    assert host.take_final_launch_resource_admission() == final_receipt
    if failure_point == "pending":
        assert events == []
    else:
        assert events == ["locks", "guardian", "reevaluate", "subprocess"]


def _acquire(
    boundary: Any,
    state: Any,
    store: Store,
    reference: FakeReference,
    *,
    selection_identity: Any | None = None,
    locks: Any | None = None,
) -> dict[str, object]:
    chosen_selection = selection_identity or _identity("selection")
    state.directory_created = True
    state.marker_identity = state.marker_identity or _identity("attempt")
    state.selection_identity = state.selection_identity or chosen_selection
    state.outer_prelaunch_identity = state.outer_prelaunch_identity or _identity("outer-prelaunch")
    state.outer_start_identity = state.outer_start_identity or _identity("outer-start")
    state.resource_identity = state.resource_identity or _identity("resource")
    if not state.outer_launch_attempted:
        STATE.begin_outer_launch(state)
        STATE.record_outer_launch_return(
            state,
            {"runner_returned": True, "unit_name": "outer.service"},
        )
    return STATE.acquire_reference_once(
        boundary,
        state,
        store,
        reference,
        unit_name="outer.service",
        selection_identity=chosen_selection,
        resource_identity=state.resource_identity,
        lock_evidence=locks or _lock_evidence(),
        manager_epoch_capture={
            "manager_epoch": boundary.root["manager_epoch"],
            "transcript": {"expected_epoch": boundary.root["manager_epoch"]},
        },
    )


def _finalize(
    boundary: Any,
    state: Any,
    store: Store,
    *,
    prove_unref: bool,
    reason: str,
    observer_identity: dict[str, object] | None = None,
    pre_unref_cleanup_identity: dict[str, object] | None = None,
) -> dict[str, object]:
    return STATE.finalize_reference_once(
        boundary,
        state,
        store,
        unit_name="outer.service",
        prove_unref=prove_unref,
        reason=reason,
        observer_identity=observer_identity,
        pre_unref_cleanup_identity=pre_unref_cleanup_identity,
    )


@pytest.mark.parametrize(
    ("fault", "failed_receipt", "kind"),
    [
        ("acquire", "", "REF_ACQUIRE_FAILED_OR_UNCERTAIN"),
        ("", "reference-acquisition.json", "REF_ACQUIRE_RETURNED_BUT_UNRECORDED"),
    ],
)
def test_acquire_uncertainty_drops_same_connection_once(
    tmp_path: Path,
    fault: str,
    failed_receipt: str,
    kind: str,
) -> None:
    boundary, state = _boundary(tmp_path), STATE.AttemptState()
    reference, store = FakeReference(fault), Store(failed_receipt)
    assert _acquire(boundary, state, store, reference)["kind"] == kind

    result = _finalize(boundary, state, store, prove_unref=False, reason=kind)
    assert result["kind"] == "UNREF_UNPROVEN_CONNECTION_DROPPED"
    assert reference.events.count("acquire") == 1
    assert reference.events.count("abort_close") == 1
    assert reference.events.count("release") == 0
    assert reference.events.count("close") == 0
    with pytest.raises(STATE.CloseoutStateError):
        _finalize(boundary, state, store, prove_unref=False, reason=kind)


@pytest.mark.parametrize(
    ("fault", "failed_receipt", "expected", "abort_count", "close_count"),
    [
        ("", "", "RECORDED", 0, 1),
        ("release", "", "UNREF_UNPROVEN_CONNECTION_DROPPED", 1, 0),
        ("", "unref-call.json", "UNREF_UNPROVEN_CONNECTION_DROPPED", 1, 0),
        ("close", "", "CONNECTION_CLOSE_FAILED_OR_UNCERTAIN", 0, 1),
        ("", "reference-release.json", "CONNECTION_CLOSED_RELEASE_UNRECORDED", 0, 1),
    ],
)
def test_unref_and_connection_effects_are_never_repeated(
    tmp_path: Path,
    fault: str,
    failed_receipt: str,
    expected: str,
    abort_count: int,
    close_count: int,
) -> None:
    boundary, state = _boundary(tmp_path), STATE.AttemptState()
    reference, store = FakeReference(), Store(failed_receipt)
    assert _acquire(boundary, state, store, reference)["kind"] == "RECORDED"
    reference.fault = fault
    result = _finalize(boundary, state, store, prove_unref=True, reason="normal")
    assert result["kind"] == expected
    assert reference.events.count("release") == 1
    assert reference.events.count("abort_close") == abort_count
    assert reference.events.count("close") == close_count
    if expected == "RECORDED":
        assert store.records["unref-call.json"]["status"] == "UNREF_RETURNED_INCOMPLETE"
    with pytest.raises(STATE.CloseoutStateError):
        _finalize(boundary, state, store, prove_unref=True, reason="repeat")


def test_normal_unref_binds_observer_and_precleanup_before_side_effect(
    tmp_path: Path,
) -> None:
    boundary, state, store = _boundary(tmp_path), STATE.AttemptState(), Store()
    reference = FakeReference()
    assert _acquire(boundary, state, store, reference)["kind"] == "RECORDED"
    observer = _identity("observer")
    cleanup = _identity("pre-unref-cleanup")

    result = _finalize(
        boundary,
        state,
        store,
        prove_unref=True,
        reason="NORMAL_SUCCESS",
        observer_identity=observer,
        pre_unref_cleanup_identity=cleanup,
    )

    assert result["kind"] == "RECORDED"
    call = store.records["unref-call.json"]
    assert call["status"] == "UNREF_RETURNED"
    assert call["observer_identity"] == observer
    assert call["pre_unref_cleanup_identity"] == cleanup
    assert state.observer_identity == observer
    assert state.pre_unref_cleanup_identity == cleanup
    assert reference.events.count("release") == reference.events.count("close") == 1

    partial_root = tmp_path / "partial"
    partial_root.mkdir()
    boundary2, state2, store2 = _boundary(partial_root), STATE.AttemptState(), Store()
    reference2 = FakeReference()
    assert _acquire(boundary2, state2, store2, reference2)["kind"] == "RECORDED"
    with pytest.raises(STATE.CloseoutStateError, match="together"):
        _finalize(
            boundary2,
            state2,
            store2,
            prove_unref=True,
            reason="NORMAL_SUCCESS",
            observer_identity=observer,
        )
    assert reference2.events.count("release") == 0


def test_successor_unref_retains_same_connection_until_terminal_close(
    tmp_path: Path,
) -> None:
    boundary, state, store = _boundary(tmp_path), STATE.AttemptState(), Store()
    reference = FakeReference()
    assert _acquire(boundary, state, store, reference)["kind"] == "RECORDED"
    state.lock_release_attempted = True
    state.lock_release_return = {
        "lock_identities": _lock_evidence(),
        "released": True,
    }
    state.supervisor_raw_lock_release_identity = _identity("raw-lock-release")
    observer = _identity("observer-v2")
    cleanup = _identity("pre-unref-cleanup-v2")

    released = STATE.release_reference_retained_once(
        boundary,
        state,
        store,
        unit_name="outer.service",
        observer_identity=observer,
        pre_unref_cleanup_identity=cleanup,
    )

    assert released["kind"] == "RECORDED_CONNECTION_RETAINED"
    assert reference.events[-1] == "release"
    assert "close" not in reference.events
    release_record = store.records["reference-release.json"]
    assert release_record["schema_version"] == STATE.REFERENCE_RELEASE_SCHEMA_V2
    assert release_record["connection_retained"] is True

    post_unref = _identity("post-unref-absence-v2")
    closed = STATE.close_released_reference_once(
        boundary,
        state,
        store,
        unit_name="outer.service",
        post_unref_absence_identity=post_unref,
    )

    assert closed["kind"] == "RECORDED_CONNECTION_CLOSED"
    assert reference.events[-2:] == ["verify_released", "close"]
    assert (
        store.records["reference-terminal.json"]["schema_version"]
        == STATE.REFERENCE_TERMINAL_SCHEMA
    )
    assert (
        store.records["reference-connection-close.json"]["schema_version"]
        == STATE.REFERENCE_CONNECTION_CLOSE_SCHEMA
    )
    with pytest.raises(STATE.CloseoutStateError, match="exact-once"):
        STATE.close_released_reference_once(
            boundary,
            state,
            store,
            unit_name="outer.service",
            post_unref_absence_identity=post_unref,
        )


@pytest.mark.parametrize(
    ("fault", "expected_kind", "abort_count", "close_count"),
    [
        (
            "verify_released",
            "UNREF_UNPROVEN_CONNECTION_DROPPED",
            1,
            0,
        ),
        (
            "close",
            "CONNECTION_CLOSE_FAILED_OR_UNCERTAIN",
            0,
            1,
        ),
    ],
)
def test_successor_post_unref_uncertainty_never_repeats_terminal_effect(
    tmp_path: Path,
    fault: str,
    expected_kind: str,
    abort_count: int,
    close_count: int,
) -> None:
    boundary, state, store = _boundary(tmp_path), STATE.AttemptState(), Store()
    reference = FakeReference()
    assert _acquire(boundary, state, store, reference)["kind"] == "RECORDED"
    state.lock_release_attempted = True
    state.lock_release_return = {
        "lock_identities": _lock_evidence(),
        "released": True,
    }
    state.supervisor_raw_lock_release_identity = _identity("raw-lock-release")
    assert (
        STATE.release_reference_retained_once(
            boundary,
            state,
            store,
            unit_name="outer.service",
            observer_identity=_identity("observer-v2"),
            pre_unref_cleanup_identity=_identity("cleanup-v2"),
        )["kind"]
        == "RECORDED_CONNECTION_RETAINED"
    )
    reference.fault = fault

    result = STATE.close_released_reference_once(
        boundary,
        state,
        store,
        unit_name="outer.service",
        post_unref_absence_identity=_identity("post-unref-v2"),
    )

    assert result["kind"] == expected_kind
    assert reference.events.count("verify_released") == 1
    assert reference.events.count("abort_close") == abort_count
    assert reference.events.count("close") == close_count
    with pytest.raises(STATE.CloseoutStateError):
        STATE.close_released_reference_once(
            boundary,
            state,
            store,
            unit_name="outer.service",
            post_unref_absence_identity=_identity("post-unref-v2"),
        )


def test_failure_successor_unref_uncertainty_becomes_one_terminal_snapshot(
    tmp_path: Path,
) -> None:
    boundary, attempt, store = _boundary(tmp_path), STATE.AttemptState(), Store()
    reference = FakeReference()
    assert _acquire(boundary, attempt, store, reference)["kind"] == "RECORDED"
    attempt.lock_release_attempted = True
    attempt.lock_release_return = {
        "lock_identities": _lock_evidence(),
        "released": True,
    }
    attempt.supervisor_raw_lock_release_identity = _identity("raw-lock-release")
    reference.fault = "release"

    result = STATE.release_reference_retained_once(
        boundary,
        attempt,
        store,
        unit_name="outer.service",
        observer_identity=_identity("failure-release"),
        pre_unref_cleanup_identity=_identity("failure-release"),
    )

    assert result["kind"] == "UNREF_UNPROVEN_CONNECTION_DROPPED"
    assert reference.events.count("release") == 1
    assert reference.events.count("abort_close") == 1
    supervisor = FORMAL.SupervisorState(attempt=attempt)
    completion = FORMAL._reference_completion_snapshot(supervisor)  # noqa: SLF001
    assert completion["kind"] == "CONNECTION_UNCERTAIN"
    assert completion["uncertainty_terminal"]["kind"] == (
        "UNREF_UNPROVEN_CONNECTION_DROPPED"
    )


@pytest.mark.parametrize(
    ("fault", "expected_terminal_kind"),
    [
        ("verify_released", "UNREF_UNPROVEN_CONNECTION_DROPPED"),
        ("close", "CONNECTION_CLOSE_FAILED_OR_UNCERTAIN"),
    ],
)
def test_failure_post_unref_uncertainty_never_misstates_retained_release_as_closed(
    tmp_path: Path,
    fault: str,
    expected_terminal_kind: str,
) -> None:
    boundary, attempt, store = _boundary(tmp_path), STATE.AttemptState(), Store()
    reference = FakeReference()
    assert _acquire(boundary, attempt, store, reference)["kind"] == "RECORDED"
    attempt.lock_release_attempted = True
    attempt.lock_release_return = {
        "lock_identities": _lock_evidence(),
        "released": True,
    }
    attempt.supervisor_raw_lock_release_identity = _identity("raw-lock-release")
    assert (
        STATE.release_reference_retained_once(
            boundary,
            attempt,
            store,
            unit_name="outer.service",
            observer_identity=_identity("failure-release"),
            pre_unref_cleanup_identity=_identity("failure-release"),
        )["kind"]
        == "RECORDED_CONNECTION_RETAINED"
    )
    reference.fault = fault
    post_unref = _identity("post-unref-v2")
    attempt.post_unref_absence_identity = post_unref
    closed = STATE.close_released_reference_once(
        boundary,
        attempt,
        store,
        unit_name="outer.service",
        post_unref_absence_identity=post_unref,
    )
    assert closed["kind"] != "RECORDED_CONNECTION_CLOSED"

    completion = FORMAL._reference_completion_snapshot(  # noqa: SLF001
        FORMAL.SupervisorState(attempt=attempt)
    )
    assert completion["kind"] == "CONNECTION_UNCERTAIN"
    assert completion["reference_release_identity"] == (
        attempt.reference_release_identity
    )
    assert completion["reference_connection_close_identity"] == "unrecorded"
    assert completion["uncertainty_terminal"]["kind"] == expected_terminal_kind


@pytest.mark.parametrize(
    ("fault", "expected_kind", "abort_count", "close_count"),
    [
        ("release", "UNREF_UNPROVEN_CONNECTION_DROPPED", 1, 0),
        ("verify_released", "UNREF_UNPROVEN_CONNECTION_DROPPED", 1, 0),
        ("close", "CONNECTION_CLOSE_FAILED_OR_UNCERTAIN", 0, 1),
    ],
)
def test_successor_reference_baseexception_is_terminal_and_never_retried(
    tmp_path: Path,
    fault: str,
    expected_kind: str,
    abort_count: int,
    close_count: int,
) -> None:
    class InterruptedReference(FakeReference):
        def _event(self, name: str) -> None:
            self.events.append(name)
            if self.fault == name:
                raise KeyboardInterrupt(f"interrupted {name}")

    boundary, attempt, store = _boundary(tmp_path), STATE.AttemptState(), Store()
    reference = InterruptedReference()
    assert _acquire(boundary, attempt, store, reference)["kind"] == "RECORDED"
    attempt.lock_release_attempted = True
    attempt.lock_release_return = {
        "lock_identities": _lock_evidence(),
        "released": True,
    }
    attempt.supervisor_raw_lock_release_identity = _identity("raw-lock-release")
    if fault == "release":
        reference.fault = fault
        result = STATE.release_reference_retained_once(
            boundary,
            attempt,
            store,
            unit_name="outer.service",
            observer_identity=_identity("failure-release"),
            pre_unref_cleanup_identity=_identity("failure-release"),
        )
    else:
        assert (
            STATE.release_reference_retained_once(
                boundary,
                attempt,
                store,
                unit_name="outer.service",
                observer_identity=_identity("failure-release"),
                pre_unref_cleanup_identity=_identity("failure-release"),
            )["kind"]
            == "RECORDED_CONNECTION_RETAINED"
        )
        reference.fault = fault
        result = STATE.close_released_reference_once(
            boundary,
            attempt,
            store,
            unit_name="outer.service",
            post_unref_absence_identity=_identity("post-unref-v2"),
        )

    assert result["kind"] == expected_kind
    assert reference.events.count(fault) == 1
    assert reference.events.count("abort_close") == abort_count
    assert reference.events.count("close") == close_count
    if fault == "release":
        with pytest.raises(STATE.CloseoutStateError):
            STATE.release_reference_retained_once(
                boundary,
                attempt,
                store,
                unit_name="outer.service",
                observer_identity=_identity("failure-release"),
                pre_unref_cleanup_identity=_identity("failure-release"),
            )
    else:
        with pytest.raises(STATE.CloseoutStateError):
            STATE.close_released_reference_once(
                boundary,
                attempt,
                store,
                unit_name="outer.service",
                post_unref_absence_identity=_identity("post-unref-v2"),
            )


def test_failure_reference_completion_resumes_after_recorded_unref_without_replay(
    tmp_path: Path,
) -> None:
    boundary, store = _boundary(tmp_path), Store()
    state = FORMAL.SupervisorState()
    reference = FakeReference()
    selection_identity = _identity("selection")
    assert (
        _acquire(
            boundary,
            state.attempt,
            store,
            reference,
            selection_identity=selection_identity,
        )["kind"]
        == "RECORDED"
    )
    state.selection_identity = selection_identity
    state.attempt.lock_release_attempted = True
    state.attempt.lock_release_return = {
        "lock_identities": _lock_evidence(),
        "released": True,
    }
    raw_identity = _identity("raw-lock-release")
    state.attempt.supervisor_raw_lock_release_identity = raw_identity
    state.supervisor_raw_lock_release_identity = raw_identity
    failure_identity = _identity("failure-release")
    assert (
        STATE.release_reference_retained_once(
            boundary,
            state.attempt,
            store,
            unit_name="outer.service",
            observer_identity=failure_identity,
            pre_unref_cleanup_identity=failure_identity,
        )["kind"]
        == "RECORDED_CONNECTION_RETAINED"
    )
    attempt = boundary.formal_dir
    receipt_paths = {
        "post_unref_absence": str(attempt / "post-unref-absence.json"),
        "reference_connection_close": str(
            attempt / "reference-connection-close.json"
        ),
        "reference_release": str(attempt / "reference-release.json"),
        "reference_terminal": str(attempt / "reference-terminal.json"),
    }
    state.selection = {"outer_spec": {"receipt_paths": receipt_paths}}
    state.outer_identity = {
        "control_group": "/user.slice/outer.service",
        "invocation_id": "a" * 32,
        "processes": [{"pid": 401, "starttime": 501}],
        "unit_name": "outer.service",
    }
    context = {
        "campaign_root_identity": boundary.context["root_identity"],
        "formal_attempt_dir": str(attempt),
        "manager_epoch": boundary.root["manager_epoch"],
        "outer_spec": {"receipt_paths": receipt_paths},
        "package_id": boundary.root["package"]["package_id"],
    }

    class ResumeHost:
        locks_released = True

        @staticmethod
        def wait_state(
            *_args: object,
            **_kwargs: object,
        ) -> dict[str, object]:
            return {
                "cgroup_absent": True,
                "processes_absent": True,
                "systemctl": dict(HELPER.ABSENT),
            }

    completion = FORMAL._failure_reference_completion(  # noqa: SLF001
        boundary=boundary,
        context=context,
        state=state,
        store=store,  # type: ignore[arg-type]
        host=ResumeHost(),  # type: ignore[arg-type]
        failure_pre_release_identity=failure_identity,
    )

    assert completion["kind"] == "RECORDED_CONNECTION_CLOSED"
    assert reference.events.count("release") == 1
    assert reference.events.count("verify_released") == 1
    assert reference.events.count("close") == 1


@pytest.mark.parametrize(
    "mutation",
    ["acquire_keys", "acquire_owner", "verify_client", "lock_count"],
)
def test_acquisition_schema_and_join_drift_fail_closed(tmp_path: Path, mutation: str) -> None:
    boundary, state, store = _boundary(tmp_path), STATE.AttemptState(), Store()

    class DriftReference(FakeReference):
        def acquire(self, **kwargs: object) -> dict[str, str]:
            result = super().acquire(**kwargs)
            if mutation == "acquire_keys":
                result["extra"] = "forbidden"
            elif mutation == "acquire_owner":
                result["manager_owner_after"] = ":1.404"
            return result

        def verify(self, **kwargs: object) -> dict[str, str]:
            result = super().verify(**kwargs)
            if mutation == "verify_client":
                result["client_unique_name"] = ":1.999"
            return result

    selection: Any = _identity("selection")
    locks: Any = _lock_evidence()
    if mutation == "lock_count":
        locks = locks[:2]
    reference = DriftReference()
    result = _acquire(
        boundary,
        state,
        store,
        reference,
        selection_identity=selection,
        locks=locks,
    )
    assert result["kind"] == "REF_ACQUIRE_RETURNED_BUT_UNRECORDED"
    assert _finalize(
        boundary,
        state,
        store,
        prove_unref=False,
        reason=result["kind"],
    )["kind"] == "UNREF_UNPROVEN_CONNECTION_DROPPED"
    assert reference.events.count("acquire") == 1
    assert reference.events.count("abort_close") == 1
    assert reference.events.count("release") == 0
    assert reference.events.count("close") == 0


def test_acquisition_rejects_missing_or_null_lifecycle_predecessor_before_refunit(
    tmp_path: Path,
) -> None:
    boundary, reference = _boundary(tmp_path), FakeReference()
    with pytest.raises(STATE.CloseoutStateError, match="attempt/barrier boundary"):
        STATE.acquire_reference_once(
            boundary,
            STATE.AttemptState(),
            Store(),
            reference,
            unit_name="outer.service",
            selection_identity=_identity("selection"),
            resource_identity=_identity("resource"),
            lock_evidence=_lock_evidence(),
            manager_epoch_capture={
                "manager_epoch": boundary.root["manager_epoch"],
                "transcript": {"expected_epoch": boundary.root["manager_epoch"]},
            },
        )
    assert reference.events == []

    state = _consumed_state(
        selection_identity={"sha256": None},
        outer_prelaunch_identity=_identity("prelaunch"),
        outer_start_identity=_identity("start"),
        resource_identity=_identity("resource"),
    )
    state.outer_launch_attempted = True
    state.outer_launch_return = {"runner_returned": True}
    with pytest.raises(STATE.CloseoutStateError, match="unproved null join"):
        STATE.acquire_reference_once(
            boundary,
            state,
            Store(),
            reference,
            unit_name="outer.service",
            selection_identity={"sha256": None},
            resource_identity=_identity("resource"),
            lock_evidence=_lock_evidence(),
            manager_epoch_capture={
                "manager_epoch": boundary.root["manager_epoch"],
                "transcript": {"expected_epoch": boundary.root["manager_epoch"]},
            },
        )
    assert reference.events == []


def test_outer_launch_effect_is_monotone_without_start_proof() -> None:
    state = STATE.AttemptState(
        selection_identity=_identity("selection"),
        outer_prelaunch_identity=_identity("outer-prelaunch"),
    )
    STATE.begin_outer_launch(state)
    with pytest.raises(STATE.CloseoutStateError):
        STATE.begin_outer_launch(state)
    assert state.outer_launch_attempted is True and state.outer_launch_return is None
    STATE.record_outer_launch_return(state, {"runner_returned": True, "unit_name": "outer.service"})
    with pytest.raises(STATE.CloseoutStateError):
        STATE.record_outer_launch_return(state, {"runner_returned": True})
    assert state.outer_start_identity is None


def test_definitely_unpublished_marker_is_markerless_without_future_joins(
    tmp_path: Path,
) -> None:
    boundary, state = _boundary(tmp_path), STATE.AttemptState(directory_created=True)
    store = Store("attempt-consumption.json")
    with pytest.raises(STATE.CloseoutStateError, match="markerless"):
        STATE.publish_attempt_consumption(
            boundary,
            state,
            store,
            created_at_utc="2026-07-27T00:00:00Z",
        )
    record = store.records["markerless-incomplete.json"]
    assert record["status"] == STATE.FORMAL_MARKERLESS_INCOMPLETE
    assert record["no_backfill"] is True
    assert record["phase"] == "DIRECTORY_CREATED_MARKER_UNRECORDED"
    assert record["marker_canonical_identity_recorded"] is False
    assert record["attempt_consumption_effect"]["returned"] is False
    assert (
        record["attempt_consumption_effect"]["error"]["code"]
        == "CANONICAL_PUBLICATION_DEFINITELY_NOT_PUBLISHED"
    )
    assert record["failure"]["code"] == "ATTEMPT_MARKER_DEFINITELY_NOT_PUBLISHED"
    assert state.formal_consumption_state == STATE.FORMAL_MARKERLESS_INCOMPLETE
    assert "selection_identity" not in record
    assert "reference_release_identity" not in record
    with pytest.raises(STATE.CloseoutStateError):
        STATE.publish_attempt_consumption(
            boundary,
            state,
            store,
            created_at_utc="2026-07-27T00:00:01Z",
        )
    assert store.attempts["attempt-consumption.json"] == 1
    assert store.attempts["markerless-incomplete.json"] == 1


@pytest.mark.parametrize(
    ("return_before_fail", "uncertain_before_fail"),
    [(False, True), (True, False)],
    ids=("rename-or-fsync-uncertain", "ack-uncertain"),
)
def test_published_or_uncertain_marker_is_formal_consumed_not_markerless(
    tmp_path: Path,
    *,
    return_before_fail: bool,
    uncertain_before_fail: bool,
) -> None:
    boundary, state = _boundary(tmp_path), STATE.AttemptState(directory_created=True)
    store = Store(
        "attempt-consumption.json",
        return_before_fail=return_before_fail,
        uncertain_before_fail=uncertain_before_fail,
    )
    with pytest.raises(STATE.CloseoutStateError, match="formal-consumed-incomplete"):
        STATE.publish_attempt_consumption(
            boundary,
            state,
            store,
            created_at_utc="2026-07-27T00:00:00Z",
        )
    assert state.formal_consumption_state == STATE.FORMAL_CONSUMED_INCOMPLETE
    assert state.irreversible_incomplete is True
    assert state.errors[-1]["code"] == "ATTEMPT_MARKER_PUBLISHED_OR_UNCERTAIN"
    assert "markerless-incomplete.json" not in store.records
    assert store.attempts == {"attempt-consumption.json": 1}
    with pytest.raises(STATE.CloseoutStateError, match="wrong predecessor"):
        STATE.publish_attempt_consumption(
            boundary,
            state,
            store,
            created_at_utc="2026-07-27T00:00:01Z",
        )
    assert store.attempts == {"attempt-consumption.json": 1}


@pytest.mark.parametrize(
    ("cross_boundary", "expected_state"),
    [
        (False, STATE.FORMAL_MARKERLESS_INCOMPLETE),
        (True, STATE.FORMAL_CONSUMED_INCOMPLETE),
    ],
    ids=("pre-send-rejection", "post-send-ack-loss"),
)
def test_receipt_store_preserves_the_broker_publication_boundary(
    tmp_path: Path,
    *,
    cross_boundary: bool,
    expected_state: str,
) -> None:
    boundary, state = _boundary(tmp_path), STATE.AttemptState(directory_created=True)
    attempt_path = boundary.formal_dir / "attempt-consumption.json"
    markerless_path = boundary.formal_dir / "markerless-incomplete.json"

    class Backend:
        @staticmethod
        def maximum_bytes(
            _label: str,
            *,
            artifact_class: str,
        ) -> int:
            assert artifact_class == "closeout"
            return 64 * 1024

        @staticmethod
        def publish_bytes_with_publication_boundary(
            path: Path,
            raw: bytes,
            *,
            maximum_bytes: int,
            artifact_class: str,
            label: str,
            publication_boundary: Callable[[], None],
        ) -> dict[str, object]:
            assert maximum_bytes == 64 * 1024
            assert artifact_class == "closeout"
            if label == "attempt":
                if cross_boundary:
                    publication_boundary()
                    path.write_bytes(raw)
                    path.chmod(0o444)
                raise OSError("injected broker publication failure")
            assert label == "markerless"
            publication_boundary()
            path.write_bytes(raw)
            path.chmod(0o444)
            return {
                "path": str(path.absolute()),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            }

    store = HELPER.ReceiptStore(
        budget_backend=Backend(),
        budget_bindings={
            str(attempt_path.absolute()): {
                "artifact_class": "closeout",
                "label": "attempt",
            },
            str(markerless_path.absolute()): {
                "artifact_class": "closeout",
                "label": "markerless",
            },
        },
    )
    with pytest.raises(
        STATE.CloseoutStateError,
        match=(
            "formal-consumed-incomplete"
            if cross_boundary
            else "markerless"
        ),
    ):
        STATE.publish_attempt_consumption(
            boundary,
            state,
            store,
            created_at_utc="2026-07-27T00:00:00Z",
        )
    assert state.formal_consumption_state == expected_state
    assert attempt_path.exists() is cross_boundary
    assert markerless_path.exists() is (not cross_boundary)


def _consumed_state(**proofs: object) -> Any:
    return STATE.AttemptState(
        directory_created=True,
        marker_identity=_identity("attempt"),
        **proofs,
    )


def test_incomplete_phase_allows_semantic_lower_bound_null_but_rejects_join_drift(
    tmp_path: Path,
) -> None:
    boundary = _boundary(tmp_path)
    valid = _consumed_state(selection_identity=_identity("selection"))
    result = STATE.publish_consumed_incomplete(
        boundary,
        valid,
        Store(),
        phase="SELECTION_RECORDED_OUTER_NOT_LAUNCHED",
        failure_record={"code": "TEST", "detail": "expected"},
    )
    assert result["record"]["lower_bound"] is None

    missing = _consumed_state()
    with pytest.raises(STATE.CloseoutStateError, match="required proof"):
        STATE.publish_consumed_incomplete(
            boundary,
            missing,
            Store(),
            phase="SELECTION_RECORDED_OUTER_NOT_LAUNCHED",
            failure_record={"code": "TEST", "detail": "expected"},
        )
    future = _consumed_state(
        selection_identity=_identity("selection"),
        outer_start_identity=_identity("outer-start"),
    )
    with pytest.raises(STATE.CloseoutStateError, match="future proof"):
        STATE.publish_consumed_incomplete(
            boundary,
            future,
            Store(),
            phase="SELECTION_RECORDED_OUTER_NOT_LAUNCHED",
            failure_record={"code": "TEST", "detail": "expected"},
        )
    extra = _consumed_state(selection_identity=_identity("selection"))
    with pytest.raises(STATE.CloseoutStateError, match="external join"):
        STATE.publish_consumed_incomplete(
            boundary,
            extra,
            Store(),
            phase="SELECTION_RECORDED_OUTER_NOT_LAUNCHED",
            failure_record={"code": "TEST", "detail": "expected"},
            external_joins={"forbidden": _identity("forbidden")},
        )

    impossible = _consumed_state(selection_identity=_identity("selection"))
    impossible.connection_action = "close"
    with pytest.raises(STATE.CloseoutStateError, match="effect ordering"):
        STATE.publish_consumed_incomplete(
            boundary,
            impossible,
            Store(),
            phase="SELECTION_RECORDED_OUTER_NOT_LAUNCHED",
            failure_record={"code": "TEST", "detail": "expected"},
        )


def test_null_frozen_join_is_not_converted_to_semantic_null(tmp_path: Path) -> None:
    boundary = _boundary(tmp_path)
    state = _consumed_state(
        selection_identity=_identity("selection"),
        outer_prelaunch_identity=_identity("prelaunch"),
        outer_start_identity=_identity("start"),
        resource_identity=_identity("resource"),
        acquire_identity=_identity("acquisition"),
    )
    state.release_attempted = True
    frozen = _absent_frozen("outer", "formal", "outer.service")
    frozen["unit_name"] = None
    with pytest.raises(STATE.CloseoutStateError):
        STATE.publish_consumed_incomplete(
            boundary,
            state,
            Store(),
            phase="UNREF_FAILED_OR_UNCERTAIN",
            failure_record={"code": "UNREF", "detail": "expected"},
            external_joins={"frozen_outer_identity": frozen},
        )


def test_uncertain_incomplete_publication_is_never_retried(tmp_path: Path) -> None:
    boundary = _boundary(tmp_path)
    state = _consumed_state(selection_identity=_identity("selection"))
    store = Store(
        "incomplete-selection-recorded-outer-not-launched.json",
        return_before_fail=True,
    )
    arguments = {
        "phase": "SELECTION_RECORDED_OUTER_NOT_LAUNCHED",
        "failure_record": {"code": "TEST", "detail": "expected"},
    }
    with pytest.raises(OSError):
        STATE.publish_consumed_incomplete(boundary, state, store, **arguments)
    with pytest.raises(STATE.CloseoutStateError):
        STATE.publish_consumed_incomplete(boundary, state, store, **arguments)
    assert store.attempts["incomplete-selection-recorded-outer-not-launched.json"] == 1


def _active(invocation: str = "1" * 32) -> dict[str, str]:
    return {
        "LoadState": "loaded",
        "ActiveState": "active",
        "SubState": "running",
        "MainPID": "41",
        "InvocationID": invocation,
        "ControlGroup": "/user.slice/outer",
    }


def _arm_evidence(slot: str, unit_name: str) -> dict[str, object]:
    return {
        "campaign_root_identity": _identity("root"),
        "formal_selection_identity": _identity("formal-selection"),
        "launch_identity": _identity(f"{slot}-launch"),
        "package_id": "c" * 64,
        "pre_run_identity": _identity(f"{slot}-pre"),
        "prelaunch_receipt_identity": _identity(f"{slot}-receipt"),
        "request_identity": _identity(f"{slot}-request"),
        "selection_identity": _identity(f"{slot}-selection"),
        "slot": slot,
        "source": "arm",
        "unit_name": unit_name,
    }


class ChildHost:
    freeze_identity = HELPER.PinnedHost.freeze_identity

    def __init__(
        self,
        shown: dict[str, str],
        *,
        fail_absence: bool = False,
        fail_cgroup: bool = False,
    ) -> None:
        self.shown = shown
        self.fail_absence = fail_absence
        self.fail_cgroup = fail_cgroup
        self.stops = 0
        self.cleaned_units: set[str] = set()

    def show(self, _unit: str) -> dict[str, str]:
        return dict(self.shown)

    def cgroup_processes(self, _group: str) -> list[dict[str, int]]:
        if self.fail_cgroup:
            raise OSError("cgroup read failed")
        return [{"pid": 41, "starttime": 9001}]

    def processes_absent(self, processes: Any) -> bool:
        return not processes or bool(self.cleaned_units)

    def stop_reset_once(self, unit: str) -> list[dict[str, str]]:
        self.stops += 1
        self.cleaned_units.add(unit)
        return []

    def wait_state(self, *_: object, **__: object) -> dict[str, object]:
        if self.fail_absence:
            raise RuntimeError("residual child")
        self.shown = dict(HELPER.ABSENT)
        return {
            "cgroup_absent": True,
            "processes_absent": True,
            "systemctl": dict(HELPER.ABSENT),
        }


def _target(tmp_path: Path, *, evidence: bool) -> Any:
    slot = HELPER.ARM_SEQUENCE[0]
    selection = _identity(f"{slot}-selection")
    pre_run = _identity(f"{slot}-pre")
    return HELPER.ChildTarget(
        source="arm",
        slot=slot,
        unit_name="ab16-child.service",
        inner_path=tmp_path / "inner.json",
        prelaunch_evidence=_arm_evidence(slot, "ab16-child.service") if evidence else None,
        selection_identity=selection,
        pre_run_identity=pre_run,
    )


@pytest.mark.parametrize(
    ("shown", "classification"),
    [
        (_active(), "PRELAUNCH_OWNED_ACTIVE"),
        (dict(HELPER.ABSENT), "PRELAUNCH_OWNED_ABSENT"),
    ],
)
def test_freeze_selected_child_uses_prelaunch_provenance_without_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shown: dict[str, str],
    classification: str,
) -> None:
    target = _target(tmp_path, evidence=True)
    class StableHost(ChildHost):
        cgroup_path = staticmethod(HELPER.PinnedHost.cgroup_path)

    host = StableHost(shown)
    monkeypatch.setattr(
        HELPER,
        "build_child_ledger",
        lambda *_args, **_kwargs: [target],
    )

    result = HELPER.freeze_selected_child_identity(
        _boundary(tmp_path),
        Store(),
        host,
        FakeReference(),
        {},
        source="arm",
        slot=target.slot,
    )

    assert result["classification"] == classification
    assert result["unit_name"] == target.unit_name
    assert result["frozen_identity"]["identity_complete"] is True
    assert host.stops == 0
    if classification.endswith("ABSENT"):
        assert result["frozen_identity"]["invocation_id"] == ""
    else:
        assert result["frozen_identity"]["invocation_id"] == "1" * 32


def test_freeze_selected_child_rejects_same_name_without_prelaunch_ownership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _target(tmp_path, evidence=False)
    host = ChildHost(_active())
    monkeypatch.setattr(
        HELPER,
        "build_child_ledger",
        lambda *_args, **_kwargs: [target],
    )

    with pytest.raises(HELPER.OuterCloseoutError, match="prelaunch ownership"):
        HELPER.freeze_selected_child_identity(
            _boundary(tmp_path),
            Store(),
            host,
            FakeReference(),
            {},
            source="arm",
            slot=target.slot,
        )
    assert host.stops == 0


def test_valid_inner_cannot_upgrade_missing_prelaunch_ownership(tmp_path: Path) -> None:
    class InnerStore(Store):
        def document(self, _path: Path, _label: str) -> tuple[dict[str, object], dict[str, object]]:
            slot = HELPER.ARM_SEQUENCE[0]
            return {
                "slot": slot,
                "unit_name": "ab16-child.service",
                "invocation_id": "1" * 32,
                "runner_selection_identity": _identity(f"{slot}-selection"),
                "pre_run_authority_identity": _identity(f"{slot}-pre"),
            }, _identity("inner")

    target, host = _target(tmp_path, evidence=False), ChildHost(_active())
    target.inner_path.touch()
    result = HELPER._contain(InnerStore(), host, target, abnormal=True)  # noqa: SLF001
    assert result["classification"] == "IDENTITY_GAP"
    assert host.stops == 0


@pytest.mark.parametrize("damage", ["missing", "selection", "unit"])
def test_active_same_name_without_exact_prelaunch_provenance_is_never_stopped(
    tmp_path: Path,
    damage: str,
) -> None:
    target = _target(tmp_path, evidence=damage != "missing")
    if damage != "missing":
        assert target.prelaunch_evidence is not None
        evidence = dict(target.prelaunch_evidence)
        if damage == "selection":
            evidence["selection_identity"] = _identity("other-selection")
        else:
            evidence["unit_name"] = "other-child.service"
        target = HELPER.ChildTarget(
            target.source,
            target.slot,
            target.unit_name,
            target.inner_path,
            evidence,
            target.selection_identity,
            target.pre_run_identity,
            target.selection_token,
        )
    host = ChildHost(_active())

    result = HELPER._contain(Store(), host, target, abnormal=True)  # noqa: SLF001

    assert result["classification"] == "IDENTITY_GAP"
    assert result["prelaunch_owned"] is False
    assert host.stops == 0


@pytest.mark.parametrize(
    ("fail_absence", "classification"),
    [(False, "STARTED_CONTAINED_PASS"), (True, "CONTAINMENT_FAILED")],
)
def test_owned_child_gets_one_bounded_stop_reset_and_exact_absence(
    tmp_path: Path,
    fail_absence: bool,
    classification: str,
) -> None:
    host = ChildHost(_active(), fail_absence=fail_absence)
    result = HELPER._contain(  # noqa: SLF001
        Store(),
        host,
        _target(tmp_path, evidence=True),
        abnormal=True,
    )
    assert result["classification"] == classification
    assert host.stops == 1
    assert result["stop_count"] == result["reset_count"] == 1


def _absent_frozen(source: str, slot: str, unit_name: str = "") -> dict[str, object]:
    return {
        "control_group": "",
        "identity_complete": True,
        "invocation_id": "",
        "ownership_classification": "ABSENT",
        "processes": [],
        "slot": slot,
        "source": source,
        "unit_name": unit_name,
    }


def _frozen_ledger(first: dict[str, object] | None = None) -> dict[str, object]:
    children = [
        _absent_frozen(source, slot)
        for source, slot in HELPER.EXPECTED_CHILD_ORDER
    ]
    if first is not None:
        children[0] = first
    return {
        "child_audit_identity": _identity("child-audit"),
        "children": children,
        "outer": _absent_frozen("outer", "formal", "outer.service"),
    }


def _absence_observation(
    ledger: dict[str, object],
    *,
    absent: bool,
) -> dict[str, object]:
    checked = HELPER.validate_frozen_ledger(ledger)
    records = []
    for item in [*checked["children"], checked["outer"]]:
        runtime_absent = absent or not item["unit_name"]
        identity_complete = item["identity_complete"] is True
        records.append(
            {
                "cgroup_absent": runtime_absent and identity_complete,
                "control_group": item["control_group"],
                "identity_complete": item["identity_complete"],
                "processes": [dict(process) for process in item["processes"]],
                "processes_absent": runtime_absent and identity_complete,
                "slot": item["slot"],
                "source": item["source"],
                "systemctl": dict(HELPER.ABSENT) if runtime_absent else _active(),
                "unit_absent": runtime_absent,
                "unit_name": item["unit_name"],
            }
        )
    return {
        "all_absent": all(
            record["unit_absent"]
            and record["cgroup_absent"]
            and record["processes_absent"]
            for record in records
        ),
        "records": records,
    }


def _pre_unref_failure_state(*, release_returned: bool) -> Any:
    call = {
        "client_unique_name": ":1.7",
        "manager_owner_after": ":1.42",
        "manager_owner_before": ":1.42",
        "unit_name": "outer.service",
    }
    state = _consumed_state(
        selection_identity=_identity("selection"),
        outer_prelaunch_identity=_identity("outer-prelaunch"),
        outer_start_identity=_identity("outer-start"),
        resource_identity=_identity("resource"),
        acquire_identity=_identity("acquisition"),
        barrier_identity=_identity("barrier"),
        observer_identity=_identity("observer"),
        pre_unref_cleanup_identity=_identity("pre-unref-cleanup"),
    )
    state.outer_launch_attempted = True
    state.outer_launch_return = {"runner_returned": True}
    state.acquire_attempted = True
    state.acquire_returned = True
    state.acquire_return = dict(call)
    state.release_attempted = True
    if release_returned:
        state.release_returned = True
        state.release_return = dict(call)
    return state


@pytest.mark.parametrize(
    ("phase", "release_returned"),
    [
        ("UNREF_FAILED_OR_UNCERTAIN", False),
        ("UNREF_RETURNED_BUT_UNRECORDED", True),
    ],
)
def test_unref_failure_phase_uses_only_established_predecessor_proofs(
    tmp_path: Path,
    phase: str,
    release_returned: bool,
) -> None:
    boundary_root = tmp_path / phase.lower()
    boundary_root.mkdir()
    result = STATE.publish_consumed_incomplete(
        _boundary(boundary_root),
        _pre_unref_failure_state(release_returned=release_returned),
        Store(),
        phase=phase,
        failure_record={"code": "UNREF_TEST", "detail": "expected"},
        external_joins={
            "frozen_outer_identity": _absent_frozen(
                "outer",
                "formal",
                "outer.service",
            )
        },
    )

    joins = result["record"]["joins"]
    assert joins["observer_identity"] == _identity("observer")
    assert joins["pre_unref_cleanup_identity"] == _identity("pre-unref-cleanup")
    assert "unref_call_identity" not in joins
    assert "reference_release_identity" not in joins


def test_unref_failure_phase_rejects_missing_or_future_proofs(tmp_path: Path) -> None:
    missing = _pre_unref_failure_state(release_returned=False)
    missing.observer_identity = None
    missing.pre_unref_cleanup_identity = None
    missing_root = tmp_path / "missing"
    missing_root.mkdir()
    with pytest.raises(STATE.CloseoutStateError, match="required proof observer_identity"):
        STATE.publish_consumed_incomplete(
            _boundary(missing_root),
            missing,
            Store(),
            phase="UNREF_FAILED_OR_UNCERTAIN",
            failure_record={"code": "UNREF_TEST", "detail": "expected"},
            external_joins={
                "frozen_outer_identity": _absent_frozen(
                    "outer",
                    "formal",
                    "outer.service",
                )
            },
        )

    future = _pre_unref_failure_state(release_returned=False)
    future.unref_call_identity = _identity("future-unref-call")
    future_root = tmp_path / "future"
    future_root.mkdir()
    with pytest.raises(STATE.CloseoutStateError, match="future proof unref_call_identity"):
        STATE.publish_consumed_incomplete(
            _boundary(future_root),
            future,
            Store(),
            phase="UNREF_FAILED_OR_UNCERTAIN",
            failure_record={"code": "UNREF_TEST", "detail": "expected"},
            external_joins={
                "frozen_outer_identity": _absent_frozen(
                    "outer",
                    "formal",
                    "outer.service",
                )
            },
        )


def test_containment_hold_retains_pre_unref_proofs_but_rejects_future_proof(
    tmp_path: Path,
) -> None:
    state = _pre_unref_failure_state(release_returned=False)
    state.release_attempted = False
    external = {
        "child_audit_identity": _identity("child-audit"),
        "frozen_outer_identity": _absent_frozen(
            "outer",
            "formal",
            "outer.service",
        ),
    }
    result = STATE.publish_consumed_incomplete(
        _boundary(tmp_path),
        state,
        Store(),
        phase="CONTAINMENT_HOLD",
        failure_record={"code": "CONTAINMENT_TEST", "detail": "expected"},
        external_joins=external,
    )
    assert result["record"]["joins"]["observer_identity"] == _identity("observer")
    assert result["record"]["joins"]["pre_unref_cleanup_identity"] == _identity(
        "pre-unref-cleanup"
    )

    future_root = tmp_path / "future"
    future_root.mkdir()
    future = _pre_unref_failure_state(release_returned=False)
    future.release_attempted = False
    future.post_unref_absence_identity = _identity("future-post-unref")
    with pytest.raises(
        STATE.CloseoutStateError,
        match="future proof post_unref_absence_identity",
    ):
        STATE.publish_consumed_incomplete(
            _boundary(future_root),
            future,
            Store(),
            phase="CONTAINMENT_HOLD",
            failure_record={"code": "CONTAINMENT_TEST", "detail": "expected"},
            external_joins=external,
        )


def test_cgroup_read_error_freezes_an_incomplete_identity_and_never_proves_absence() -> None:
    class FrozenHost(ChildHost):
        observe_frozen_absence = HELPER.PinnedHost.observe_frozen_absence
        processes_absent = HELPER.PinnedHost.processes_absent
        cgroup_path = staticmethod(HELPER.PinnedHost.cgroup_path)

        def __init__(self) -> None:
            super().__init__(_active(), fail_cgroup=True)
            self.boundary = SimpleNamespace(context={"campaign_module": Campaign})

        def show(self, _unit: str) -> dict[str, str]:
            return dict(HELPER.ABSENT)

    host = FrozenHost()
    frozen = host.freeze_identity(
        source="gate1",
        slot=HELPER.GATE1_SLOTS[0],
        unit_name="ab16-child.service",
        shown=_active(),
        ownership_classification="IDENTITY_GAP",
    )
    assert frozen["identity_complete"] is False
    assert frozen["processes"] == []
    observation = host.observe_frozen_absence(_frozen_ledger(frozen))
    assert observation["all_absent"] is False
    assert observation["records"][0]["identity_complete"] is False


def test_process_absence_is_bound_to_pid_starttime_not_pid_reuse() -> None:
    host = SimpleNamespace(
        boundary=SimpleNamespace(context={"campaign_module": Campaign})
    )
    Campaign.starttimes = {41: 9002}
    try:
        assert HELPER.PinnedHost.processes_absent(
            host,
            [{"pid": 41, "starttime": 9001}],
        ) is True
        with pytest.raises(STATE.CloseoutStateError):
            HELPER.PinnedHost.processes_absent(
                host,
                [{"pid": 41, "starttime": None}],
            )
    finally:
        Campaign.starttimes = {41: 9001}


@pytest.mark.parametrize("mutation", ["missing", "reordered", "duplicate_slot", "duplicate_unit"])
def test_frozen_ledger_requires_exact_finite_identity_order(mutation: str) -> None:
    ledger = _frozen_ledger()
    if mutation == "missing":
        ledger["children"].pop()
    elif mutation == "reordered":
        ledger["children"][0], ledger["children"][1] = ledger["children"][1], ledger["children"][0]
    elif mutation == "duplicate_slot":
        ledger["children"][1] = dict(ledger["children"][0])
    else:
        ledger["children"][0]["unit_name"] = "duplicate.service"
        ledger["children"][1]["unit_name"] = "duplicate.service"
    with pytest.raises(STATE.CloseoutStateError):
        HELPER.validate_frozen_ledger(ledger)


def test_child_audit_continues_from_early_gap_to_later_owned_active_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    targets = []
    for index, (source, slot) in enumerate(HELPER.EXPECTED_CHILD_ORDER):
        unit = "broken.service" if index == 0 else "owned-later.service" if index == 1 else ""
        selection = _identity(f"{slot}-selection")
        evidence = None
        if index == 1:
            evidence = {
                "campaign_root_identity": _identity("root"),
                "formal_selection_identity": _identity("formal-selection"),
                "gate1_ownership_identity": _identity("gate1-ownership"),
                "package_id": "c" * 64,
                "prelaunch_checkpoint_identity": _identity("gate1-checkpoint"),
                "selection_identity": selection,
                "selection_token": "gate1-token",
                "slot": slot,
                "source": "gate1",
                "unit_name": unit,
            }
        targets.append(
            HELPER.ChildTarget(
                source,
                slot,
                unit,
                tmp_path / f"{slot}.json",
                evidence,
                selection,
                None,
                "gate1-token" if source == "gate1" else "",
            )
        )

    class AuditHost(ChildHost):
        def show(self, unit: str) -> dict[str, str]:
            if unit == "broken.service":
                raise OSError("injected early audit failure")
            if unit == "owned-later.service" and unit not in self.cleaned_units:
                return _active()
            return dict(HELPER.ABSENT)

        def observe_frozen_absence(self, ledger: Any) -> dict[str, object]:
            return _absence_observation(ledger, absent=False)

    host = AuditHost(_active())
    monkeypatch.setattr(HELPER, "build_child_ledger", lambda *_args, **_kwargs: targets)
    boundary = _boundary(tmp_path)
    formal_selection = {"child_audit_path": str(boundary.formal_dir / "child-audit.json")}
    result = HELPER.audit_children(
        boundary,
        Store(),
        host,
        FakeReference(),
        formal_selection,
        abnormal=True,
    )
    assert len(result["record"]["records"]) == 20
    assert result["record"]["records"][0]["classification"] == "AUDIT_FAILED"
    assert result["record"]["records"][0]["stop_count"] == 0
    assert result["record"]["records"][1]["stop_count"] == 1
    assert result["record"]["records"][1]["classification"] == "STARTED_CONTAINED_PASS"
    assert result["record"]["status"] == "CONSUMED_INCOMPLETE"
    assert host.stops == 1


def _owned_audit_targets(
    tmp_path: Path,
    *,
    first_owned: bool,
) -> list[Any]:
    targets: list[Any] = []
    for index, (source, slot) in enumerate(HELPER.EXPECTED_CHILD_ORDER):
        unit_name = f"owned-{index:02d}.service"
        selection = _identity(f"{slot}-selection")
        pre_run = _identity(f"{slot}-pre") if source == "arm" else None
        evidence: dict[str, object] | None = None
        if index == 0 and first_owned:
            evidence = {
                "campaign_root_identity": _identity("root"),
                "formal_selection_identity": _identity("formal-selection"),
                "gate1_ownership_identity": _identity("gate1-ownership"),
                "package_id": "c" * 64,
                "prelaunch_checkpoint_identity": _identity("gate1-checkpoint"),
                "selection_identity": selection,
                "selection_token": "gate1-token",
                "slot": slot,
                "source": source,
                "unit_name": unit_name,
            }
        targets.append(
            HELPER.ChildTarget(
                source,
                slot,
                unit_name,
                tmp_path / f"{slot}.json",
                evidence,
                selection,
                pre_run,
                "gate1-token" if source == "gate1" else "",
            )
        )
    return targets


def _active_frozen(target: Any, invocation: str = "1" * 32) -> dict[str, object]:
    return {
        "control_group": "/user.slice/outer",
        "identity_complete": True,
        "invocation_id": invocation,
        "ownership_classification": "PRELAUNCH_OWNED_ACTIVE",
        "processes": [{"pid": 41, "starttime": 9001}],
        "slot": target.slot,
        "source": target.source,
        "unit_name": target.unit_name,
    }


class PriorLedgerHost(ChildHost):
    cgroup_path = staticmethod(HELPER.PinnedHost.cgroup_path)

    def __init__(self, active_unit: str, invocation: str = "1" * 32) -> None:
        super().__init__(_active(invocation))
        self.active_unit = active_unit

    def show(self, unit: str) -> dict[str, str]:
        if unit == self.active_unit and unit not in self.cleaned_units:
            return dict(self.shown)
        return dict(HELPER.ABSENT)

    def observe_frozen_absence(self, ledger: Any) -> dict[str, object]:
        return _absence_observation(ledger, absent=True)


def test_takeover_freezes_and_contains_child_launched_before_live_ledger_update(
    tmp_path: Path,
) -> None:
    targets = _owned_audit_targets(tmp_path, first_owned=True)
    first = targets[0]
    ledger = {
        "child_audit_identity": {},
        "children": [
            _absent_frozen(source, slot, target.unit_name)
            for target, (source, slot) in zip(
                targets,
                HELPER.EXPECTED_CHILD_ORDER,
                strict=True,
            )
        ],
        "outer": _absent_frozen("outer", "formal", "outer.service"),
    }
    host = PriorLedgerHost(first.unit_name)

    frozen = HELPER.freeze_takeover_child_ledger(host, ledger, targets)

    first_frozen = frozen["ledger"]["children"][0]
    assert first_frozen["unit_name"] == first.unit_name
    assert first_frozen["invocation_id"] == "1" * 32
    assert first_frozen["processes"] == [{"pid": 41, "starttime": 9001}]
    assert frozen["owned_unit_names"] == [first.unit_name]
    contained = HELPER.contain_frozen_ledger_once(
        host,
        frozen["ledger"],
        owned_unit_names=frozen["owned_unit_names"],
    )
    assert contained["all_absent"] is True
    assert contained["records"][0]["classification"] == "STARTED_CONTAINED_PASS"
    assert host.stops == 1


def test_takeover_same_name_without_prelaunch_provenance_is_observe_only(
    tmp_path: Path,
) -> None:
    targets = _owned_audit_targets(tmp_path, first_owned=False)
    first = targets[0]
    ledger = {
        "child_audit_identity": {},
        "children": [
            _absent_frozen(source, slot, target.unit_name)
            for target, (source, slot) in zip(
                targets,
                HELPER.EXPECTED_CHILD_ORDER,
                strict=True,
            )
        ],
        "outer": _absent_frozen("outer", "formal", "outer.service"),
    }

    class IdentityGapHost(PriorLedgerHost):
        def observe_frozen_absence(self, checked: Any) -> dict[str, object]:
            return _absence_observation(checked, absent=False)

    host = IdentityGapHost(first.unit_name)
    frozen = HELPER.freeze_takeover_child_ledger(host, ledger, targets)

    assert frozen["owned_unit_names"] == []
    assert frozen["ledger"]["children"][0]["ownership_classification"] == "IDENTITY_GAP"
    assert any(
        item["code"] == "GUARDIAN_CHILD_OWNERSHIP_IDENTITY_GAP"
        for item in frozen["errors"]
    )
    contained = HELPER.contain_frozen_ledger_once(
        host,
        frozen["ledger"],
        owned_unit_names=[],
    )
    assert contained["all_absent"] is False
    assert contained["records"][0]["classification"] == "IDENTITY_GAP"
    assert host.stops == 0


@pytest.mark.parametrize(
    ("prior_kind", "first_owned", "live_invocation", "classification", "stops"),
    [
        ("ACTIVE", True, "1" * 32, "STARTED_CONTAINED_PASS", 1),
        ("ACTIVE", True, "2" * 32, "IDENTITY_GAP", 0),
        ("ACTIVE", False, "1" * 32, "IDENTITY_GAP", 0),
        ("NOT_STARTED", True, "1" * 32, "STARTED_CONTAINED_PASS", 1),
        ("NOT_STARTED", False, "1" * 32, "IDENTITY_GAP", 0),
    ],
)
def test_abnormal_audit_stops_only_exact_prior_or_prelaunch_owned_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prior_kind: str,
    first_owned: bool,
    live_invocation: str,
    classification: str,
    stops: int,
) -> None:
    targets = _owned_audit_targets(tmp_path, first_owned=first_owned)
    first = targets[0]
    prior_children = [
        _absent_frozen(source, slot, target.unit_name)
        for target, (source, slot) in zip(
            targets,
            HELPER.EXPECTED_CHILD_ORDER,
            strict=True,
        )
    ]
    if prior_kind == "ACTIVE":
        prior_children[0] = _active_frozen(first)
    prior = {
        "child_audit_identity": {},
        "children": prior_children,
        "outer": _absent_frozen("outer", "formal", "outer.service"),
    }
    host = PriorLedgerHost(first.unit_name, live_invocation)
    monkeypatch.setattr(
        HELPER,
        "build_child_ledger",
        lambda *_args, **_kwargs: targets,
    )
    boundary = _boundary(tmp_path)

    result = HELPER.audit_children(
        boundary,
        Store(),
        host,
        FakeReference(),
        {"child_audit_path": str(boundary.formal_dir / "child-audit.json")},
        abnormal=True,
        prior_launch_ledger=prior,
    )

    first_record = result["record"]["records"][0]
    assert first_record["classification"] == classification
    assert first_record.get("stop_count", 0) == stops
    assert host.stops == stops
    if classification == "IDENTITY_GAP":
        assert first_record["prelaunch_owned"] is first_owned
        assert any(
            item["code"] == "PRIOR_FROZEN_IDENTITY_GAP"
            for item in first_record["errors"]
        )


def test_normal_child_cleanup_replays_exact_gate1_and_all_organic_receipts_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    targets = [
        HELPER.ChildTarget(
            source,
            slot,
            f"normal-{index:02d}.service",
            tmp_path / f"{slot}.json",
            None,
            _identity(f"{slot}-selection"),
            _identity(f"{slot}-pre") if source == "arm" else None,
            "gate1-token" if source == "gate1" else "",
        )
        for index, (source, slot) in enumerate(HELPER.EXPECTED_CHILD_ORDER)
    ]
    first = targets[0]
    targets[0] = HELPER.ChildTarget(
        first.source,
        first.slot,
        first.unit_name,
        first.inner_path,
        {
            "campaign_root_identity": _identity("root"),
            "formal_selection_identity": _identity("formal-selection"),
            "gate1_ownership_identity": _identity("gate1-ownership"),
            "package_id": "c" * 64,
            "prelaunch_checkpoint_identity": _identity("gate1-checkpoint"),
            "selection_identity": first.selection_identity,
            "selection_token": first.selection_token,
            "slot": first.slot,
            "source": first.source,
            "unit_name": first.unit_name,
        },
        first.selection_identity,
        first.pre_run_identity,
        first.selection_token,
    )

    class NormalHost(ChildHost):
        def show(self, _unit: str) -> dict[str, str]:
            return dict(HELPER.ABSENT)

        def observe_frozen_absence(self, ledger: Any) -> dict[str, object]:
            return _absence_observation(ledger, absent=True)

    continuation_calls = 0
    organic_calls: list[str] = []
    gate1_detached = [_identity(f"gate1-detached-{index}") for index in range(4)]

    def continuation(_context: Any) -> tuple[dict[str, object], dict[str, object]]:
        nonlocal continuation_calls
        continuation_calls += 1
        return {"detached_replay_identities": gate1_detached}, _identity("gate1-continuation")

    def load_consumption(
        _context: Any,
        *,
        slot: str,
        required_credible: bool,
    ) -> dict[str, object]:
        assert required_credible is True
        organic_calls.append(slot)
        return {
            "consumption_id": f"consumed-{slot}",
            "resource_replay_identity": _identity(f"{slot}-replay"),
            "resource_terminal_identity": _identity(f"{slot}-terminal"),
        }

    monkeypatch.setattr(HELPER, "build_child_ledger", lambda *_args, **_kwargs: targets)
    monkeypatch.setattr(HELPER.authority, "_continuation", continuation)
    monkeypatch.setattr(HELPER.authority, "_load_consumption", load_consumption)
    boundary = _boundary(tmp_path)
    host = NormalHost(dict(HELPER.ABSENT))
    historical_children = [
        _absent_frozen(source, slot, target.unit_name)
        for target, (source, slot) in zip(
            targets,
            HELPER.EXPECTED_CHILD_ORDER,
            strict=True,
        )
    ]
    historical_children[0] = {
        "control_group": "/user.slice/outer",
        "identity_complete": True,
        "invocation_id": "1" * 32,
        "ownership_classification": "PRELAUNCH_OWNED_ACTIVE",
        "processes": [{"pid": 41, "starttime": 9001}],
        "slot": HELPER.EXPECTED_CHILD_ORDER[0][1],
        "source": HELPER.EXPECTED_CHILD_ORDER[0][0],
        "unit_name": targets[0].unit_name,
    }
    prior_ledger = {
        "child_audit_identity": {},
        "children": historical_children,
        "outer": _absent_frozen("outer", "formal", "outer.service"),
    }

    result = HELPER.audit_children(
        boundary,
        Store(),
        host,
        FakeReference(),
        {"child_audit_path": str(boundary.formal_dir / "child-audit.json")},
        abnormal=False,
        prior_launch_ledger=prior_ledger,
    )

    assert result["record"]["status"] == "PASS"
    assert result["record"]["mode"] == "NORMAL_REPLAY"
    assert result["record"]["containment_used"] is False
    assert result["record"]["frozen_children"][0]["invocation_id"] == "1" * 32
    assert result["record"]["records"][0]["systemctl"] == HELPER.ABSENT
    assert result["ledger"]["child_audit_identity"] == result["identity"]
    assert prior_ledger["child_audit_identity"] == {}
    assert continuation_calls == 1
    assert organic_calls == list(HELPER.ARM_SEQUENCE)
    replay = result["record"]["normal_replay"]
    assert replay["gate1_continuation_identity"] == _identity("gate1-continuation")
    assert replay["gate1_detached_identities"] == gate1_detached
    assert replay["arm_cleanup_replay"] == {
        slot: {
            "consumption_id": f"consumed-{slot}",
            "resource_replay_identity": _identity(f"{slot}-replay"),
            "resource_terminal_identity": _identity(f"{slot}-terminal"),
        }
        for slot in HELPER.ARM_SEQUENCE
    }
    assert host.stops == 0


def test_successor_late_proof_order_keeps_ref_before_raw_release_and_final_join() -> None:
    state = STATE.AttemptState(
        acquire_identity=_identity("acquisition"),
        barrier_identity=_identity("barrier"),
    )
    STATE.record_late_proof_once(state, "observer_identity", _identity("observer"))
    STATE.record_late_proof_once(
        state,
        "pre_unref_cleanup_identity",
        _identity("pre-unref-cleanup"),
    )
    with pytest.raises(STATE.CloseoutStateError, match="predecessor"):
        STATE.record_late_proof_once(
            state,
            "guardian_close_identity",
            _identity("guardian-close-too-early"),
        )
    STATE.begin_detached_success_verifier(state)
    STATE.record_detached_success_verifier_return(
        state,
        {"stdout_sha256": "1" * 64},
    )
    STATE.record_late_proof_once(
        state,
        "detached_success_identity",
        _identity("detached-success"),
    )
    STATE.begin_guardian_close(state)
    STATE.record_guardian_close_return(state, {"acknowledged": True})
    STATE.record_late_proof_once(
        state,
        "guardian_close_identity",
        _identity("guardian-close"),
    )
    STATE.record_late_proof_once(
        state,
        "guardian_absence_identity",
        _identity("guardian-absence"),
    )
    STATE.begin_supervisor_lock_release(state)
    STATE.record_supervisor_lock_release_return(
        state,
        {"lock_identities": _lock_evidence(), "released": True},
    )
    raw = _identity("raw-lock-release")
    publication = state.publication("supervisor-raw-lock-release")
    publication.begin()
    publication.note_returned(raw)
    publication.note_recorded(raw)
    STATE.record_late_proof_once(
        state,
        "supervisor_raw_lock_release_identity",
        raw,
    )
    assert state.release_attempted is False
    with pytest.raises(STATE.CloseoutStateError, match="predecessor"):
        STATE.record_late_proof_once(
            state,
            "dual_lock_release_identity",
            _identity("dual-too-early"),
        )


class HoldPort:
    def __init__(self, tmp_path: Path, *, absent: bool) -> None:
        self.absent = absent
        self.guardian_release_count = 0
        self.release_count = 0
        self.descriptors = [
            os.open(tmp_path / f"lock-{index}", os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
            for index in range(3)
        ]

    def lock_evidence(self) -> list[dict[str, object]]:
        return [
            {
                "device": os.fstat(descriptor).st_dev,
                "inode": os.fstat(descriptor).st_ino,
                "path": HELPER.LOCK_PATHS[index],
                "uid": os.getuid(),
            }
            for index, descriptor in enumerate(self.descriptors)
        ]

    def observe_frozen_absence(self, ledger: Any) -> dict[str, object]:
        return _absence_observation(ledger, absent=self.absent)

    def prepare_guardian_release(self, ledger: Any) -> dict[str, object]:
        STATE.validate_frozen_ledger(ledger)
        self.guardian_release_count += 1
        if self.guardian_release_count != 1:
            raise AssertionError("guardian release repeated")
        return _identity("containment-guardian-absence")

    def release_locks_once(self) -> dict[str, object]:
        self.release_count += 1
        if self.release_count != 1:
            raise AssertionError("lock release repeated")
        evidence = self.lock_evidence()
        for descriptor in self.descriptors:
            os.close(descriptor)
        return {"lock_identities": evidence, "released": True}

    def close_for_test(self) -> None:
        for descriptor in self.descriptors:
            try:
                os.close(descriptor)
            except OSError:
                pass


class ScriptedWaiter:
    def __init__(
        self,
        on_wait: Callable[[int], None] | None = None,
        *,
        announce_failures: int = 0,
        wait_failures: int = 0,
    ) -> None:
        self.on_wait = on_wait
        self.announce_failures = announce_failures
        self.wait_failures = wait_failures
        self.announce_attempts = 0
        self.wait_attempts = 0
        self.events: list[dict[str, object]] = []

    def announce(self, event: Any) -> None:
        self.announce_attempts += 1
        if self.announce_attempts <= self.announce_failures:
            raise RuntimeError("injected announce failure")
        self.events.append(dict(event))

    def wait(self, _seconds: float) -> None:
        self.wait_attempts += 1
        if self.wait_attempts <= self.wait_failures:
            raise RuntimeError("injected wait failure")
        if self.on_wait is None:
            raise AssertionError("containment wait was not expected")
        self.on_wait(self.wait_attempts)


def _hold_ledger() -> dict[str, object]:
    return _frozen_ledger()


def _coordinator(
    tmp_path: Path,
    *,
    absent: bool,
    failed_receipt: str = "",
    return_before_fail: bool = False,
) -> tuple[Any, Any, HoldPort, ScriptedWaiter, Store, FakeReference]:
    boundary = _boundary(tmp_path)
    reference = FakeReference()
    store = Store(failed_receipt, return_before_fail=return_before_fail)
    state = STATE.AttemptState(directory_created=True)
    STATE.publish_attempt_consumption(
        boundary,
        state,
        store,
        created_at_utc="2026-07-27T00:00:00Z",
    )
    state.selection_identity = _identity("selection")
    state.outer_prelaunch_identity = _identity("outer-prelaunch")
    state.outer_start_identity = _identity("outer-start")
    state.resource_identity = _identity("resource")
    assert _acquire(
        boundary,
        state,
        store,
        reference,
        selection_identity=state.selection_identity,
    )["kind"] == "RECORDED"
    state.barrier_identity = _identity("barrier")
    port, waiter = HoldPort(tmp_path, absent=absent), ScriptedWaiter()
    coordinator = STATE.ContainmentHoldCoordinator(
        boundary,
        state,
        store,
        port,
        waiter=waiter,
    )
    return coordinator, state, port, waiter, store, reference


@contextmanager
def _coordinator_scope(
    tmp_path: Path,
    *,
    absent: bool,
    failed_receipt: str = "",
    return_before_fail: bool = False,
) -> Iterator[tuple[Any, Any, HoldPort, ScriptedWaiter, Store, FakeReference]]:
    values = _coordinator(
        tmp_path,
        absent=absent,
        failed_receipt=failed_receipt,
        return_before_fail=return_before_fail,
    )
    try:
        yield values
    finally:
        values[2].close_for_test()


def _enter(coordinator: Any) -> dict[str, object]:
    return coordinator.enter(
        unit_name="outer.service",
        failure_record={"code": "CHILD_RESIDUAL", "detail": "test"},
        ledger=_hold_ledger(),
        reference_reason="POST_BARRIER_FAILURE",
    )


def test_containment_hold_keeps_locks_and_side_effects_until_absence(tmp_path: Path) -> None:
    with _coordinator_scope(tmp_path, absent=False) as (
        coordinator,
        _state,
        port,
        _waiter,
        store,
        reference,
    ):
        returned = False
        wait_observations = 0

        def before_absence(_attempt: int) -> None:
            nonlocal wait_observations
            wait_observations += 1
            assert returned is False
            assert port.release_count == 0
            assert all(os.fstat(descriptor) for descriptor in port.descriptors)
            assert reference.events.count("release") == 1
            assert reference.events.count("close") == 1
            assert reference.events.count("abort_close") == 0
            assert "containment-hold.json" in store.records
            if wait_observations == 2:
                port.absent = True

        coordinator.waiter = ScriptedWaiter(before_absence)
        result = _enter(coordinator)
        returned = True

        assert wait_observations == 2
        assert port.release_count == 0
        assert result["status"] == "PRE_RELEASE_CONSUMED_INCOMPLETE"
        assert result["detached_replay_required"] is True
        assert "detached-incomplete.json" not in store.records
        names = list(store.records)
        assert "lock-release.json" not in names
        assert all(os.fstat(descriptor) for descriptor in port.descriptors)

        detached = STATE.verify_detached_incomplete_chain(
            expected_campaign_root_identity=coordinator.boundary.context["root_identity"],
            expected_package_id=coordinator.boundary.root["package"]["package_id"],
            **result["detached_replay_input"],
        )
        assert detached["status"] == "PRE_RELEASE_VERIFIED_INCOMPLETE"
        assert detached["success_eligible"] is False
        assert not any(detached["authorizations"].values())


def test_reference_terminal_exception_enters_hold_before_lock_release(tmp_path: Path) -> None:
    with _coordinator_scope(tmp_path, absent=False) as (
        coordinator,
        state,
        port,
        _waiter,
        _store,
        reference,
    ):
        state.release_attempted = True
        returned = False

        def before_absence(_attempt: int) -> None:
            assert returned is False
            assert port.release_count == 0
            assert all(os.fstat(descriptor) for descriptor in port.descriptors)
            assert reference.events.count("release") == 0
            assert reference.events.count("close") == 0
            assert reference.events.count("abort_close") == 1
            port.absent = True

        coordinator.waiter = ScriptedWaiter(before_absence)
        result = _enter(coordinator)
        returned = True

        assert port.release_count == 0
        assert result["status"] == "PRE_RELEASE_CONSUMED_INCOMPLETE"
        assert any(
            item["code"] == "REFERENCE_TERMINAL_FAILED_OR_UNCERTAIN"
            for item in result["errors"]
        )
        assert reference.events.count("abort_close") == 1


def test_waiter_failures_do_not_unwind_hold_or_repeat_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(STATE, "HOLD_POLL_SECONDS", 0.01)
    with _coordinator_scope(tmp_path, absent=False) as (
        coordinator,
        _state,
        port,
        _waiter,
        _store,
        reference,
    ):
        returned = False

        def before_absence(attempt: int) -> None:
            assert attempt == 2
            assert returned is False
            assert port.release_count == 0
            assert all(os.fstat(descriptor) for descriptor in port.descriptors)
            assert reference.events.count("release") == 1
            assert reference.events.count("close") == 1
            assert reference.events.count("abort_close") == 0
            port.absent = True

        waiter = ScriptedWaiter(
            before_absence,
            announce_failures=1,
            wait_failures=1,
        )
        coordinator.waiter = waiter
        result = _enter(coordinator)
        returned = True

        assert waiter.announce_attempts == 2
        assert waiter.wait_attempts == 2
        assert result["status"] == "PRE_RELEASE_CONSUMED_INCOMPLETE"
        assert port.release_count == 0
        assert reference.events.count("release") == 1
        assert reference.events.count("close") == 1
        error_codes = {item["code"] for item in result["errors"]}
        assert "CONTAINMENT_ANNOUNCEMENT_FAILED" in error_codes
        assert "CONTAINMENT_WAITER_FAILED" in error_codes


def test_clearance_publication_returned_unrecorded_forbids_retry(tmp_path: Path) -> None:
    boundary = _boundary(tmp_path)
    state = STATE.AttemptState()
    store = Store(
        "containment-cleared-after-hold.json",
        return_before_fail=True,
    )
    with pytest.raises(OSError, match="publication failure"):
        STATE._publish_once(  # noqa: SLF001
            state,
            store,
            "containment-clearance",
            boundary.formal_dir / "containment-cleared-after-hold.json",
            {"status": "CONTAINMENT_CLEARED_AFTER_HOLD"},
            "containment clearance",
        )
    effect = state.publication("containment-clearance")
    assert effect.attempted is True
    assert effect.returned_identity is not None
    assert effect.recorded_identity is None
    assert store.attempts["containment-cleared-after-hold.json"] == 1
    with pytest.raises(STATE.CloseoutStateError, match="cannot be attempted twice"):
        STATE._publish_once(  # noqa: SLF001
            state,
            store,
            "containment-clearance",
            boundary.formal_dir / "containment-cleared-after-hold.json",
            {"status": "CONTAINMENT_CLEARED_AFTER_HOLD"},
            "containment clearance",
        )
    assert store.attempts["containment-cleared-after-hold.json"] == 1


def test_containment_pre_release_never_attempts_lock_release(tmp_path: Path) -> None:
    with _coordinator_scope(
        tmp_path,
        absent=True,
        failed_receipt="lock-release.json",
        return_before_fail=True,
    ) as (coordinator, _state, port, _waiter, store, _reference):
        result = _enter(coordinator)
        assert result["status"] == "PRE_RELEASE_CONSUMED_INCOMPLETE"
        assert result["detached_replay_required"] is True
        assert port.release_count == 0
        assert store.attempts.get("lock-release.json", 0) == 0
        replay = result["detached_replay_input"]
        assert replay["guardian_absence_identity"] == _identity(
            "containment-guardian-absence"
        )
        assert replay["hold_identity"] == Store._identity(
            coordinator.boundary.formal_dir / "containment-hold.json"
        )
        assert replay["clearance_identity"] == Store._identity(
            coordinator.boundary.formal_dir
            / "containment-cleared-after-hold.json"
        )
        assert replay["incomplete_identity"] == Store._identity(
            coordinator.boundary.formal_dir
            / "incomplete-containment-hold.json"
        )
        assert replay["lock_identities"] == port.lock_evidence()
        assert all(os.fstat(descriptor) for descriptor in port.descriptors)


def test_no_reference_opened_terminal_is_exact_and_has_no_synthetic_join() -> None:
    assert STATE._validate_reference_terminal(  # noqa: SLF001
        {"kind": "NO_REFERENCE_OPENED"}
    ) == {"kind": "NO_REFERENCE_OPENED"}
    with pytest.raises(STATE.CloseoutStateError, match="field set drifted"):
        STATE._validate_reference_terminal(  # noqa: SLF001
            {
                "identity": _identity("synthetic-reference"),
                "kind": "NO_REFERENCE_OPENED",
            }
        )


@pytest.mark.parametrize(
    "mutation",
    ["hold_schema", "authorization", "absence", "lock_identity"],
)
def test_pure_detached_incomplete_verifier_rejects_mutated_chain(
    tmp_path: Path,
    mutation: str,
) -> None:
    with _coordinator_scope(tmp_path, absent=True) as (
        coordinator,
        _state,
        _port,
        _waiter,
        _store,
        _reference,
    ):
        result = _enter(coordinator)
        replay = copy.deepcopy(result["detached_replay_input"])
    if mutation == "hold_schema":
        replay["hold_record"]["schema_version"] = "wrong"
    elif mutation == "authorization":
        replay["clearance_record"]["authorizations"]["upper_bound_update_authorized"] = True
    elif mutation == "absence":
        replay["clearance_record"]["final_observation"]["records"][0]["unit_absent"] = False
    else:
        replay["lock_identities"][0]["inode"] += 1
    with pytest.raises(STATE.CloseoutStateError):
        STATE.verify_detached_incomplete_chain(
            expected_campaign_root_identity=coordinator.boundary.context["root_identity"],
            expected_package_id=coordinator.boundary.root["package"]["package_id"],
            **replay,
        )


@pytest.mark.parametrize("frozen_index", range(21))
def test_detached_verifier_checks_every_frozen_runtime_identity(
    tmp_path: Path,
    frozen_index: int,
) -> None:
    with _coordinator_scope(tmp_path, absent=True) as (
        coordinator,
        _state,
        _port,
        _waiter,
        _store,
        _reference,
    ):
        result = _enter(coordinator)
        replay = copy.deepcopy(result["detached_replay_input"])
    ledger = replay["hold_record"]["frozen_ledger"]
    frozen = ledger["children"][frozen_index] if frozen_index < 20 else ledger["outer"]
    frozen["control_group"] = "/user.slice/malformed"
    frozen["invocation_id"] = "f" * 32
    frozen["processes"] = [{"pid": 41, "starttime": 0}]

    with pytest.raises(STATE.CloseoutStateError):
        STATE.verify_detached_incomplete_chain(
            expected_campaign_root_identity=coordinator.boundary.context["root_identity"],
            expected_package_id=coordinator.boundary.root["package"]["package_id"],
            **replay,
        )


def test_fixed_arm_order_and_claim_boundary() -> None:
    expected = (
        "region-capacity-ab-control",
        "region-capacity-ab-treatment",
        "region-capacity-ba-treatment",
        "region-capacity-ba-control",
        "shape-packing-hall-ab-control",
        "shape-packing-hall-ab-treatment",
        "shape-packing-hall-ba-treatment",
        "shape-packing-hall-ba-control",
        "power-hitting-set-ab-control",
        "power-hitting-set-ab-treatment",
        "power-hitting-set-ba-treatment",
        "power-hitting-set-ba-control",
        "bundle-ab-control",
        "bundle-ab-treatment",
        "bundle-ba-treatment",
        "bundle-ba-control",
    )
    assert HELPER.ARM_SEQUENCE == expected
    assert len(HELPER.ARM_SEQUENCE) == 16
    assert HELPER.FALSE_AUTHORIZATIONS and not any(HELPER.FALSE_AUTHORIZATIONS.values())


def test_launch_uncertainty_observes_the_exact_unit_until_it_appears() -> None:
    active = {"LoadState": "loaded"}

    class Host:
        def __init__(self) -> None:
            self.observations = [dict(HELPER.ABSENT), active]
            self.names: list[str] = []

        def show(self, unit_name: str) -> dict[str, str]:
            self.names.append(unit_name)
            return self.observations.pop(0)

    ticks = iter((0.0, 0.5, 1.0))
    sleeps: list[float] = []
    host = Host()

    observed = FORMAL._wait_uncertain_unit_resolution(
        host,  # type: ignore[arg-type]
        "outer.service",
        timeout_seconds=2.0,
        monotonic=lambda: next(ticks),
        sleeper=sleeps.append,
    )

    assert observed == active
    assert host.names == ["outer.service", "outer.service"]
    assert sleeps == [FORMAL.POLL_SECONDS]


def test_launch_uncertainty_requires_the_whole_bounded_absence_window() -> None:
    class Host:
        calls = 0

        def show(self, unit_name: str) -> dict[str, str]:
            assert unit_name == "outer.service"
            self.calls += 1
            return dict(HELPER.ABSENT)

    ticks = iter((0.0, 0.5, 1.5))
    host = Host()

    observed = FORMAL._wait_uncertain_unit_resolution(
        host,  # type: ignore[arg-type]
        "outer.service",
        timeout_seconds=1.0,
        monotonic=lambda: next(ticks),
        sleeper=lambda _seconds: None,
    )

    assert observed == HELPER.ABSENT
    assert host.calls == 1


def test_supervisor_checkpoint_blocks_new_effects_after_signal_or_guardian_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = FORMAL.SupervisorState()
    latched = SimpleNamespace(records=[{"signal": 15}])
    with pytest.raises(
        FORMAL.IrreversibleFormalFailure,
        match="termination signal latched",
    ):
        FORMAL._supervisor_checkpoint(
            state,
            SimpleNamespace(),  # type: ignore[arg-type]
            latched,  # type: ignore[arg-type]
        )
    with pytest.raises(
        FORMAL.IrreversibleFormalFailure,
        match="termination signal latched",
    ):
        FORMAL._post_release_signal_checkpoint(
            latched,  # type: ignore[arg-type]
            phase="detached success verifier launch",
        )

    state.guardian = SimpleNamespace()
    clear = SimpleNamespace(records=[])
    monkeypatch.setattr(FORMAL, "guardian_is_alive", lambda _session: False)
    with pytest.raises(
        FORMAL.IrreversibleFormalFailure,
        match="guardian died",
    ):
        FORMAL._supervisor_checkpoint(
            state,
            SimpleNamespace(),  # type: ignore[arg-type]
            clear,  # type: ignore[arg-type]
        )


def test_takeover_audit_exception_keeps_guardian_alive_and_locks_held() -> None:
    guardian_module = FORMAL.guardian
    port = guardian_module.ExistingCloseoutResidualPort.__new__(
        guardian_module.ExistingCloseoutResidualPort
    )
    port.boundary = SimpleNamespace()
    port.selection = {}
    port.store = SimpleNamespace()
    port.host = SimpleNamespace()
    port.containment_attempted = False
    port.takeover_freeze_attempted = False
    port.takeover_ledger = None
    port.takeover_release_eligible = None
    port.takeover_owned_unit_names = []
    port.ownership_errors = []
    port._recorded_reference_verification = lambda _ledger: {}  # type: ignore[method-assign]  # noqa: SLF001

    def fail_build(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("injected takeover build failure")

    port.helper = SimpleNamespace(build_child_ledger=fail_build)
    ledger = _frozen_ledger()

    class StopHold(BaseException):
        pass

    class Lease:
        abort = False
        evidence_calls = 0
        close_calls = 0

        def evidence(self) -> list[dict[str, object]]:
            if self.abort:
                raise StopHold
            self.evidence_calls += 1
            return _lock_evidence()

        def close_local_copies_once(self) -> dict[str, object]:
            self.close_calls += 1
            raise AssertionError("release-ineligible takeover closed lock FDs")

    lease = Lease()
    close_calls: list[str] = []

    class Guardian:
        latest_ledger = ledger
        ledger_update_count = 1
        selection_identity = _identity("selection")
        effects = SimpleNamespace(errors=[])

        @staticmethod
        def hold_until_supervisor_death(**_kwargs: object) -> dict[str, object]:
            return {"status": "SUPERVISOR_EXITED"}

        @staticmethod
        def close_locks_after_absence(**_kwargs: object) -> dict[str, object]:
            close_calls.append("close")
            raise AssertionError("release-ineligible takeover entered lock close")

        @staticmethod
        def _require_lease() -> Lease:
            return lease

    entered_wait = threading.Event()
    unblock = threading.Event()
    returned = threading.Event()

    def blocking_waiter(_seconds: float) -> None:
        entered_wait.set()
        unblock.wait()

    def run_hold() -> None:
        try:
            guardian_module._permanent_peer_loss_hold(  # noqa: SLF001
                Guardian(),
                port=port,
                waiter=blocking_waiter,
                poll_interval_seconds=0.01,
            )
        except StopHold:
            pass
        finally:
            returned.set()

    thread = threading.Thread(target=run_hold, daemon=True)
    thread.start()
    assert entered_wait.wait(timeout=1.0)
    assert thread.is_alive()
    assert returned.is_set() is False
    assert port.takeover_freeze_attempted is True
    assert port.takeover_release_eligible is False
    assert any(
        item["code"] == "GUARDIAN_TAKEOVER_LEDGER_IDENTITY_GAP"
        for item in port.ownership_errors
    )
    assert close_calls == []
    assert lease.close_calls == 0
    assert lease.evidence_calls >= 1
    lease.abort = True
    unblock.set()
    thread.join(timeout=1.0)
    assert thread.is_alive() is False


def test_prelaunch_mirror_precedes_every_child_launch_permission() -> None:
    service_source = inspect.getsource(FORMAL._service_fixed_campaign)
    assert service_source.index("_mirror_gate1_prelaunch(") < service_source.index(
        "_publish_outer_barrier("
    )
    assert "before_receipt_publish=" in service_source

    arm_source = inspect.getsource(HELPER.service_arm_prelaunch)
    assert arm_source.index("admission = before_receipt_publish(slot, checked[\"unit_name\"])") < (
        arm_source.index("record =")
    )
    assert arm_source.index("validate_resource_admission_receipt(") < (
        arm_source.index("store.publish(")
    )
    assert arm_source.index("\"resource_admission\": admission") < (
        arm_source.index("store.publish(")
    )
    validator_source = inspect.getsource(HELPER.validate_arm_prelaunch_receipt)
    assert "validate_resource_admission_receipt(" in validator_source
    assert "expected_stage=resource_admission.FORMAL_ORGANIC_ARM" in validator_source
    assert FORMAL.LEDGER_PHASES == (
        "outer:prelaunch",
        "outer:formal",
        "gate1:prelaunch",
        *(f"gate1:{slot}:live" for slot in HELPER.GATE1_SLOTS),
        *(
            phase
            for slot in HELPER.ARM_SEQUENCE
            for phase in (f"arm:{slot}:prelaunch", f"arm:{slot}:live")
        ),
    )


def test_fixed_campaign_passes_exact_guardian_allowlist_and_unique_arm_contexts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = {"pid": 4242, "starttime": 31337}
    supervisor = {"pid": os.getpid(), "starttime": 31336}
    locks = _lock_evidence()
    selection_identity = _identity("selection")
    state = FORMAL.SupervisorState()
    state.selection_identity = selection_identity
    state.selection = {
        "arm_prelaunch_paths": {
            slot: {"request": str(tmp_path / f"{slot}.request.json")}
            for slot in FORMAL.ARM_SEQUENCE
        },
        "outer_spec": {"resource_contract": {"runtime_max_sec": 60}},
    }
    state.attempt.reference = object()
    state.attempt.acquire_identity = _identity("acquire")
    state.attempt.resource_identity = _identity("outer-resource")
    state.guardian = SimpleNamespace(
        ready={"guardian_process_identity": copy.deepcopy(actor)}
    )
    mirrored: list[tuple[str, str]] = []
    resource_calls: list[dict[str, object]] = []
    service_calls: list[dict[str, object]] = []
    child_count = len(FORMAL.GATE1_SLOTS) + len(FORMAL.ARM_SEQUENCE)
    state.ledger_sequence = len(FORMAL.LEDGER_PHASES) - child_count

    class Host:
        @staticmethod
        def lock_evidence() -> list[dict[str, object]]:
            return copy.deepcopy(locks)

    def validate_resource(
        path: Path | str,
        *,
        authority_context: Mapping[str, object],
        lock_identities: list[dict[str, object]],
        observation_context: dict[str, object],
        allowed_same_uid_processes: list[dict[str, int]],
    ) -> dict[str, object]:
        assert path == str(tmp_path)
        assert authority_context["campaign_dir"] == str(tmp_path)
        assert lock_identities == locks
        assert allowed_same_uid_processes == [supervisor, actor]
        resource_calls.append(copy.deepcopy(observation_context))
        return {
            "observation_context": copy.deepcopy(observation_context),
            "status": "PASS",
        }

    def service_arm(
        *_args: object,
        slot: str,
        ordinal: int,
        expected_allowed_same_uid_processes: list[dict[str, int]],
        expected_resource_observation_context: dict[str, object],
        before_receipt_publish: Callable[[str, str], dict[str, object]],
        **_kwargs: object,
    ) -> None:
        assert expected_allowed_same_uid_processes == [supervisor, actor]
        assert expected_resource_observation_context == {
            "authority_id": selection_identity["sha256"],
            "disk_path": str(tmp_path.absolute()),
            "kind": "FORMAL_ORGANIC_ARM_PRELAUNCH",
            "ordinal": ordinal,
            "scope_id": _identity("root")["sha256"],
            "sequence": ordinal + 1,
            "slot": slot,
            "target": "DERIVE_FROM_VALIDATED_PRE_RUN",
        }
        unit_name = f"ab16-formal-{slot}.service"
        admission = before_receipt_publish(slot, unit_name)
        assert admission["observation_context"]["target"] == unit_name
        service_calls.append(
            {
                "ordinal": ordinal,
                "slot": slot,
                "unit_name": unit_name,
            }
        )

    def mirror_child(**_kwargs: object) -> None:
        state.ledger_sequence += 1

    monkeypatch.setattr(
        FORMAL.closeout_helper,
        "capture_gate1_ownership",
        lambda *_args, **_kwargs: _identity("gate1-ownership"),
    )
    monkeypatch.setattr(
        FORMAL.closeout_helper,
        "service_arm_prelaunch",
        service_arm,
    )
    monkeypatch.setattr(FORMAL, "_mirror_gate1_prelaunch", lambda **_kwargs: None)
    monkeypatch.setattr(FORMAL, "_publish_outer_barrier", lambda **_kwargs: None)
    monkeypatch.setattr(FORMAL, "_wait_arm_request", lambda **_kwargs: None)
    monkeypatch.setattr(
        FORMAL,
        "_mirror_arm_prelaunch",
        lambda **kwargs: mirrored.append((kwargs["slot"], kwargs["unit_name"])),
    )
    monkeypatch.setattr(FORMAL, "_wait_and_mirror_child", mirror_child)
    monkeypatch.setattr(FORMAL, "validate_resource_gate", validate_resource)
    monkeypatch.setattr(
        FORMAL,
        "_process_identity",
        lambda pid: dict(actor if pid == actor["pid"] else supervisor),
    )
    result = ({}, _identity("controller"))
    monkeypatch.setattr(FORMAL, "_read_controller_result", lambda **_kwargs: result)

    observed = FORMAL._service_fixed_campaign(  # noqa: SLF001
        boundary=SimpleNamespace(),
        context={
            "campaign_dir": str(tmp_path),
            "campaign_root_identity": _identity("root"),
        },
        state=state,
        store=SimpleNamespace(),
        host=Host(),  # type: ignore[arg-type]
        latch=SimpleNamespace(),
    )

    assert observed == result
    assert [item["slot"] for item in service_calls] == list(FORMAL.ARM_SEQUENCE)
    assert [item["ordinal"] for item in service_calls] == list(range(1, 17))
    assert mirrored == [
        (slot, f"ab16-formal-{slot}.service")
        for slot in FORMAL.ARM_SEQUENCE
    ]
    assert [item["sequence"] for item in resource_calls] == list(range(2, 18))
    assert len(
        {tuple(sorted(item.items())) for item in resource_calls}
    ) == len(FORMAL.ARM_SEQUENCE)
    assert all(
        item["authority_id"] == selection_identity["sha256"]
        and item["scope_id"] == _identity("root")["sha256"]
        for item in resource_calls
    )


def test_arm_prelaunch_v3_replays_exact_post_lock_resource_admission(
    tmp_path: Path,
) -> None:
    boundary = _boundary(tmp_path)
    slot = HELPER.ARM_SEQUENCE[0]
    boundary.preregistration = {
        "arm_selection_paths": {slot: tmp_path / "selection.json"},
        "pre_run_authority_paths": {slot: tmp_path / "pre-run.json"},
    }

    class Store:
        receipt: dict[str, object]

        @staticmethod
        def identity(path: Path | str) -> dict[str, object]:
            return _identity(Path(path).name)

        def document(
            self,
            _path: Path | str,
            _label: str,
        ) -> tuple[dict[str, object], dict[str, object]]:
            return self.receipt, _identity("arm-prelaunch-receipt")

    store = Store()
    locks = [
        {
            "device": index + 1,
            "inode": index + 101,
            "path": path,
            "uid": os.getuid(),
        }
        for index, path in enumerate(HELPER.LOCK_PATHS)
    ]
    request = HELPER.build_arm_prelaunch_request(
        boundary,
        store,
        store.identity(boundary.formal_dir / "selection.json"),
        slot,
        1,
    )
    admission = HELPER.resource_admission.evaluate_resource_admission(
        boundary.formal_dir,
        stage=HELPER.resource_admission.FORMAL_ORGANIC_ARM,
        lock_identities=locks,
        lock_identity_format=HELPER.resource_admission.FORMAL_LOCK_IDENTITY_FORMAT,
        observation_context={
            "authority_id": "a" * 64,
            "disk_path": str(boundary.formal_dir.absolute()),
            "kind": "FORMAL_ORGANIC_ARM_PRELAUNCH",
            "ordinal": 1,
            "scope_id": "b" * 64,
            "sequence": 2,
            "slot": slot,
            "target": "ab16-arm-a001.service",
        },
        meminfo={
            "MemAvailable": 64 * HELPER.resource_admission.GIB,
            "SwapFree": 64 * HELPER.resource_admission.GIB,
        },
        disk_free=64 * HELPER.resource_admission.GIB,
        conflicts=[],
        observed_at_utc="2026-07-31T00:00:00Z",
    )
    admission["measurements"]["same_uid_allowed_processes"] = [
        {
            "command": "python -c loader --role outer-guardian",
            "pid": 401,
            "starttime": 501,
        }
    ]
    store.receipt = {
        **{key: value for key, value in request.items() if key != "status"},
        "authorizations": dict(HELPER.FALSE_AUTHORIZATIONS),
        "locks": locks,
        "manager_epoch_capture": {
            "manager_epoch": boundary.root["manager_epoch"],
        },
        "outer_reference_verification": {
            "client_unique_name": ":1.99",
            "manager_owner": ":1.42",
            "unit_name": "ab16-formal-outer-a001.service",
        },
        "request_identity": _identity("request"),
        "resource_admission": admission,
        "status": "PASS",
        "systemctl": dict(HELPER.ABSENT),
        "unit_name": "ab16-arm-a001.service",
    }
    checked, _ = HELPER.validate_arm_prelaunch_receipt(
        boundary,
        store,
        request,
        _identity("request"),
        tmp_path / "receipt.json",
        expected_allowed_same_uid_processes=[
            {"pid": 401, "starttime": 501}
        ],
        expected_resource_observation_context=admission["observation_context"],
    )
    assert checked["resource_admission"] == admission

    current_receipt = copy.deepcopy(store.receipt)
    prior_request = copy.deepcopy(request)
    prior_request["schema_version"] = "noncert-cuts-ab16-formal-arm-prelaunch-v2"
    with pytest.raises(HELPER.OuterCloseoutError, match="receipt drifted"):
        HELPER.validate_arm_prelaunch_receipt(
            boundary,
            store,
            prior_request,
            _identity("request"),
            tmp_path / "receipt.json",
            expected_allowed_same_uid_processes=[
                {"pid": 401, "starttime": 501}
            ],
            expected_resource_observation_context=admission["observation_context"],
        )

    store.receipt = copy.deepcopy(current_receipt)
    store.receipt["schema_version"] = (
        "noncert-cuts-ab16-formal-arm-prelaunch-v2"
    )
    with pytest.raises(HELPER.OuterCloseoutError, match="receipt drifted"):
        HELPER.validate_arm_prelaunch_receipt(
            boundary,
            store,
            request,
            _identity("request"),
            tmp_path / "receipt.json",
            expected_allowed_same_uid_processes=[
                {"pid": 401, "starttime": 501}
            ],
            expected_resource_observation_context=admission["observation_context"],
        )

    store.receipt = current_receipt
    store.receipt = copy.deepcopy(store.receipt)
    store.receipt["resource_admission"]["lock_check"]["identities"][0]["inode"] += 1
    with pytest.raises(HELPER.OuterCloseoutError, match="resource admission drifted"):
        HELPER.validate_arm_prelaunch_receipt(
            boundary,
            store,
            request,
            _identity("request"),
            tmp_path / "receipt.json",
            expected_allowed_same_uid_processes=[
                {"pid": 401, "starttime": 501}
            ],
            expected_resource_observation_context=admission["observation_context"],
        )


def test_child_ledger_derives_arm_resource_replay_contract_independently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slot = HELPER.ARM_SEQUENCE[0]
    monkeypatch.setattr(HELPER, "ARM_SEQUENCE", (slot,))
    monkeypatch.setattr(HELPER, "GATE1_SLOTS", ())
    boundary = _boundary(tmp_path)
    boundary.campaign = tmp_path
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    paths = {
        "launch": attempt / "manager-epoch-launch.json",
        "pre_run": tmp_path / "pre-run.json",
        "receipt": tmp_path / "receipt.json",
        "request": tmp_path / "request.json",
        "selection": tmp_path / "selection.json",
    }
    for path in paths.values():
        path.write_bytes(b"{}\n")
    boundary.preregistration = {
        "arm_selection_paths": {slot: str(paths["selection"])},
        "attempt_dirs": {slot: str(attempt)},
        "pre_run_authority_paths": {slot: str(paths["pre_run"])},
    }
    formal_selection = {
        "arm_prelaunch_paths": {
            slot: {
                "receipt": str(paths["receipt"]),
                "request": str(paths["request"]),
            }
        },
        "gate1_prelaunch_ownership_path": str(tmp_path / "gate1-ownership.json"),
        "outer_spec": {"unit_name": "outer.service"},
    }
    unit_name = "ab16-arm-a001.service"
    locks = _lock_evidence()
    reference_verification = {
        "client_unique_name": ":1.7",
        "manager_owner": ":1.42",
        "unit_name": "outer.service",
    }
    documents = {
        paths["launch"]: {"phase": "launch"},
        paths["pre_run"]: {"attempt_dir": str(attempt), "unit_name": unit_name},
        paths["receipt"]: {
            "locks": locks,
            "outer_reference_verification": reference_verification,
            "unit_name": unit_name,
        },
        paths["request"]: {"slot": slot},
        paths["selection"]: {"slot": slot},
    }

    class LedgerStore:
        @staticmethod
        def identity(path: Path | str) -> dict[str, object]:
            return _identity(Path(path).name)

        @staticmethod
        def document(
            path: Path | str,
            _label: str,
        ) -> tuple[dict[str, object], dict[str, object]]:
            resolved = Path(path)
            return copy.deepcopy(documents[resolved]), _identity(resolved.name)

    class Lifecycle:
        @staticmethod
        def validate_pre_run_authority(
            record: Mapping[str, object],
            *,
            expected_slot: str,
        ) -> dict[str, object]:
            assert expected_slot == slot
            return dict(record)

        @staticmethod
        def validate_runner_selection(
            _record: Mapping[str, object],
            **_kwargs: object,
        ) -> None:
            return None

    class Verifier:
        @staticmethod
        def validate_pre_run_authority(
            record: Mapping[str, object],
            *,
            expected_slot: str,
        ) -> dict[str, object]:
            assert expected_slot == slot
            return dict(record)

        @staticmethod
        def _validate_selection(  # noqa: SLF001
            _record: Mapping[str, object],
            **_kwargs: object,
        ) -> None:
            return None

        @staticmethod
        def _replay_epoch_observation_file(  # noqa: SLF001
            **_kwargs: object,
        ) -> None:
            return None

    monkeypatch.setattr(
        HELPER,
        "_gate1",
        lambda _boundary: ({"units": {}}, _identity("gate1")),
    )
    monkeypatch.setattr(
        HELPER.authority,
        "_resource_modules",
        lambda _context: (Lifecycle(), Verifier()),
    )
    expected_allowed = [
        {"pid": 401, "starttime": 501},
        {"pid": 402, "starttime": 502},
    ]
    expected_context = {
        "authority_id": _identity("selection.json")["sha256"],
        "disk_path": str(tmp_path.absolute()),
        "kind": "FORMAL_ORGANIC_ARM_PRELAUNCH",
        "ordinal": 1,
        "scope_id": boundary.context["root_identity"]["sha256"],
        "sequence": 2,
        "slot": slot,
        "target": unit_name,
    }
    captured: dict[str, object] = {}

    def validate_receipt(
        _boundary: object,
        _store: object,
        _request: Mapping[str, object],
        _request_identity: Mapping[str, object],
        receipt_path: Path | str,
        *,
        expected_allowed_same_uid_processes: Sequence[Mapping[str, int]],
        expected_resource_observation_context: Mapping[str, object],
    ) -> tuple[dict[str, object], dict[str, object]]:
        captured["allowed"] = list(expected_allowed_same_uid_processes)
        captured["context"] = dict(expected_resource_observation_context)
        return (
            copy.deepcopy(documents[Path(receipt_path)]),
            _identity("receipt"),
        )

    monkeypatch.setattr(HELPER, "validate_arm_prelaunch_receipt", validate_receipt)
    targets = HELPER.build_child_ledger(
        boundary,
        LedgerStore(),
        SimpleNamespace(lock_evidence=lambda: locks),
        FakeReference(),
        formal_selection,
        expected_allowed_same_uid_processes=expected_allowed,
    )

    assert captured == {
        "allowed": expected_allowed,
        "context": expected_context,
    }
    assert len(targets) == 1
    assert targets[0].prelaunch_evidence is not None
    assert targets[0].unit_name == unit_name


def test_arm_prelaunch_lock_mismatch_fails_before_receipt_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    boundary = _boundary(tmp_path)
    slot = HELPER.ARM_SEQUENCE[0]
    request_path = tmp_path / "request.json"
    receipt_path = tmp_path / "receipt.json"
    pre_run_path = tmp_path / "pre-run.json"
    selection_path = tmp_path / "selection.json"
    attempt_dir = tmp_path / "attempt"
    boundary.preregistration = {
        "arm_selection_paths": {slot: selection_path},
        "attempt_dirs": {slot: str(attempt_dir)},
        "pre_run_authority_paths": {slot: pre_run_path},
    }
    formal_selection = {
        "arm_prelaunch_paths": {
            slot: {"receipt": str(receipt_path), "request": str(request_path)}
        }
    }

    class Store:
        published = False
        documents: dict[str, dict[str, object]] = {}

        @staticmethod
        def identity(path: Path | str) -> dict[str, object]:
            return _identity(Path(path).name)

        def document(
            self,
            path: Path | str,
            _label: str,
        ) -> tuple[dict[str, object], dict[str, object]]:
            return self.documents[str(path)], self.identity(path)

        def publish(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            self.published = True
            return _identity("published")

    store = Store()
    store.documents[str(pre_run_path)] = {"kind": "pre-run"}
    store.documents[str(selection_path)] = {"kind": "selection"}
    store.documents[str(request_path)] = HELPER.build_arm_prelaunch_request(
        boundary,
        store,
        store.identity(boundary.formal_dir / "selection.json"),
        slot,
        1,
    )
    locks = [
        {
            "device": index + 1,
            "inode": index + 101,
            "path": path,
            "uid": os.getuid(),
        }
        for index, path in enumerate(HELPER.LOCK_PATHS)
    ]
    mismatched_locks = copy.deepcopy(locks)
    mismatched_locks[0]["inode"] += 1
    admission = HELPER.resource_admission.evaluate_resource_admission(
        boundary.formal_dir,
        stage=HELPER.resource_admission.FORMAL_ORGANIC_ARM,
        lock_identities=mismatched_locks,
        lock_identity_format=HELPER.resource_admission.FORMAL_LOCK_IDENTITY_FORMAT,
        observation_context={
            "authority_id": "a" * 64,
            "disk_path": str(boundary.formal_dir.absolute()),
            "kind": "FORMAL_ORGANIC_ARM_PRELAUNCH",
            "ordinal": 1,
            "scope_id": "b" * 64,
            "sequence": 2,
            "slot": slot,
            "target": "ab16-formal-arm-a001.service",
        },
        meminfo={
            "MemAvailable": 64 * HELPER.resource_admission.GIB,
            "SwapFree": 64 * HELPER.resource_admission.GIB,
        },
        disk_free=64 * HELPER.resource_admission.GIB,
        conflicts=[],
        observed_at_utc="2026-07-31T00:00:01Z",
    )
    admission["measurements"]["same_uid_allowed_processes"] = [
        {
            "command": "python -c loader --role outer-guardian",
            "pid": 402,
            "starttime": 502,
        }
    ]
    epoch = boundary.root["manager_epoch"]
    checked = {
        "attempt_dir": str(attempt_dir),
        "manager_epoch": epoch,
        "unit_name": "ab16-formal-arm-a001.service",
    }
    lifecycle = SimpleNamespace(
        validate_pre_run_authority=lambda *_args, **_kwargs: checked,
        validate_runner_selection=lambda *_args, **_kwargs: checked,
    )
    monkeypatch.setattr(
        HELPER.authority,
        "_resource_modules",
        lambda _context: (lifecycle, object()),
    )
    monkeypatch.setattr(
        HELPER.authority,
        "_capture_current_manager_epoch",
        lambda _context: {"manager_epoch": epoch},
    )
    host = SimpleNamespace(
        lock_evidence=lambda: copy.deepcopy(locks),
        show=lambda _unit_name: dict(HELPER.ABSENT),
    )
    reference = SimpleNamespace(
        verify=lambda **_kwargs: {
            "client_unique_name": ":1.99",
            "manager_owner": ":1.42",
            "unit_name": "ab16-formal-outer-a001.service",
        }
    )

    with pytest.raises(
        HELPER.OuterCloseoutError,
        match="post-lock resource admission failed closed",
    ):
        HELPER.service_arm_prelaunch(
            boundary,
            store,
            host,
            formal_selection,
            reference,
            slot=slot,
            ordinal=1,
            expected_allowed_same_uid_processes=[
                {"pid": 402, "starttime": 502}
            ],
            expected_resource_observation_context={
                **admission["observation_context"],
                "target": "DERIVE_FROM_VALIDATED_PRE_RUN",
            },
            before_receipt_publish=lambda _slot, _unit: admission,
        )
    assert store.published is False


def test_normal_closeout_has_latch_checks_at_every_late_effect_boundary() -> None:
    normal = inspect.getsource(FORMAL._publish_normal_closeout)
    release = inspect.getsource(FORMAL._release_guardian_and_raw_locks)
    reference = inspect.getsource(FORMAL._complete_reference_and_final_success)
    driver = inspect.getsource(FORMAL.run_formal_campaign)
    for phase in (
        "normal child cleanup replay",
        "outer stable terminal wait",
        "outer terminal receipt publication",
        "outer scoped stop/reset",
        "observer receipt publication",
        "pre-Unref cleanup receipt publication",
    ):
        assert f'phase="{phase}"' in normal
    for phase in (
        "guardian exact-once lock close",
        "guardian lock-close receipt publication",
        "guardian control connection close",
        "guardian terminal absence wait",
        "guardian absence receipt publication",
        "supervisor exact-once raw lock release",
        "supervisor raw lock-release receipt publication",
    ):
        assert f'phase="{phase}"' in release
    for phase in (
        "exact-once RefUnit Unref with connection retained",
        "post-Unref unit cgroup and PID absence wait",
        "post-Unref absence receipt publication",
        "same-connection manager client and library verification",
        "formal-root closure and dual outside replay",
    ):
        assert f'phase="{phase}"' in reference
    assert 'phase="detached substantive success verifier launch"' in driver
    assert (
        driver.index("_run_detached_success(")
        < driver.index("_release_guardian_and_raw_locks(")
        < driver.index("_complete_reference_and_final_success(")
    )
    assert 'phase="VERIFIED supervisor return"' in driver


@pytest.mark.parametrize(
    "boundary_name",
    [
        "after-child-audit",
        "before-guardian-close",
        "before-supervisor-lock-release",
        "before-detached-verifier",
    ],
)
def test_latched_termination_stops_each_late_success_side_effect(
    boundary_name: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    latch = SimpleNamespace(records=[])

    if boundary_name == "after-child-audit":
        state = FORMAL.SupervisorState()
        state.selection_identity = _identity("selection")
        state.selection = {
            "outer_spec": {
                "receipt_paths": {
                    key: str(tmp_path / f"{key}.json")
                    for key in (
                        "observer",
                        "outer_terminal",
                        "post_unref_absence",
                        "pre_unref_cleanup",
                    )
                },
                "unit_name": "outer.service",
            }
        }
        state.outer_identity = {
            "control_group": "/user.slice/outer.service",
            "invocation_id": "a" * 32,
            "processes": [{"pid": 41, "starttime": 9001}],
            "unit_name": "outer.service",
        }
        state.ledger = _frozen_ledger()
        state.guardian = SimpleNamespace(
            ready={
                "guardian_process_identity": {
                    "pid": 4101,
                    "starttime": 5101,
                },
                "supervisor_process_identity": {
                    "pid": 4102,
                    "starttime": 5102,
                },
            }
        )
        state.attempt.reference = object()
        state.attempt.acquire_identity = _identity("acquisition")
        state.attempt.barrier_identity = _identity("barrier")
        original = FORMAL._normal_closeout_checkpoint
        target = "outer stable terminal wait"

        def checkpoint(
            checked_state: Any,
            checked_latch: Any,
            *,
            phase: str,
        ) -> None:
            if phase == target:
                checked_latch.records.append({"signal": 15})
            original(checked_state, checked_latch, phase=phase)

        class Host:
            def stop_reset_once(self, _unit_name: str) -> list[object]:
                events.append("stop-reset")
                return []

            def wait_state(self, *_args: object, **_kwargs: object) -> dict[str, object]:
                events.append("cleanup-wait")
                return {
                    "cgroup_absent": True,
                    "processes_absent": True,
                    "systemctl": {
                        **HELPER.ABSENT,
                        "LoadState": "loaded",
                    },
                    "unit_kept_loaded_by_reference": True,
                }

        monkeypatch.setattr(FORMAL, "_normal_closeout_checkpoint", checkpoint)
        monkeypatch.setattr(FORMAL, "guardian_is_alive", lambda _session: True)
        monkeypatch.setattr(
            FORMAL,
            "_formal_resource_allowlist",
            lambda _state: [
                {"pid": 4101, "starttime": 5101},
                {"pid": 4102, "starttime": 5102},
            ],
        )
        monkeypatch.setattr(
            FORMAL.closeout_helper,
            "audit_children",
            lambda *_args, **_kwargs: events.append("child-audit")
            or {
                "identity": _identity("child-audit"),
                "ledger": state.ledger,
                "record": {"status": "PASS"},
            },
        )
        monkeypatch.setattr(
            FORMAL.closeout_helper,
            "bind_outer_ledger",
            lambda _child, _outer: state.ledger,
        )
        monkeypatch.setattr(
            FORMAL,
            "wait_unit_terminal",
            lambda *_args, **_kwargs: events.append("terminal-wait")
            or ({}, {}, 1),
        )
        monkeypatch.setattr(
            FORMAL,
            "_publish_tracked_phase",
            lambda _attempt, _store, *, key, **_kwargs: events.append(
                f"publish:{key}"
            )
            or _identity(key),
        )

        with pytest.raises(
            FORMAL.IrreversibleFormalFailure,
            match="termination signal latched",
        ):
            FORMAL._publish_normal_closeout(
                boundary=SimpleNamespace(),
                context={
                    "campaign_root_identity": _identity("root"),
                    "manager_epoch": {},
                    "package_id": "c" * 64,
                },
                state=state,
                store=SimpleNamespace(),
                host=Host(),  # type: ignore[arg-type]
                latch=latch,  # type: ignore[arg-type]
                controller_identity=_identity("controller"),
            )
        assert events == ["child-audit"]
        return

    if boundary_name in {
        "before-guardian-close",
        "before-supervisor-lock-release",
    }:
        state = FORMAL.SupervisorState()
        state.selection_identity = _identity("selection")
        state.selection = {
            "outer_spec": {
                "receipt_paths": {
                    "dual_lock_release": str(tmp_path / "dual.json"),
                    "guardian_absence": str(tmp_path / "guardian-absence.json"),
                    "guardian_lock_close": str(tmp_path / "guardian-close.json"),
                    "supervisor_raw_lock_release": str(tmp_path / "raw-lock.json"),
                }
            }
        }
        state.ledger = _frozen_ledger()
        state.pre_unref_identity = _identity("pre-unref")
        state.attempt.pre_unref_cleanup_identity = state.pre_unref_identity
        state.detached_success_identity = _identity("detached-success")
        state.attempt.detached_success_verifier_attempted = True
        state.attempt.detached_success_verifier_return = {
            "stdout_sha256": "1" * 64
        }
        state.attempt.detached_success_identity = state.detached_success_identity
        state.guardian = SimpleNamespace(
            close_received=False,
            connection=object(),
            unit_identity={
                "control_group": "/user.slice/guardian.service",
                "invocation_id": "b" * 32,
                "processes": [{"pid": 42, "starttime": 9002}],
                "unit_name": "guardian.service",
            },
        )
        original_normal = FORMAL._normal_closeout_checkpoint
        original_post = FORMAL._post_release_signal_checkpoint

        def normal_checkpoint(
            checked_state: Any,
            checked_latch: Any,
            *,
            phase: str,
        ) -> None:
            if (
                boundary_name == "before-guardian-close"
                and phase == "guardian exact-once lock close"
            ):
                checked_latch.records.append({"signal": 15})
            original_normal(checked_state, checked_latch, phase=phase)

        def post_checkpoint(checked_latch: Any, *, phase: str) -> None:
            if (
                boundary_name == "before-supervisor-lock-release"
                and phase == "supervisor exact-once raw lock release"
            ):
                checked_latch.records.append({"signal": 15})
            original_post(checked_latch, phase=phase)

        close_record = {key: None for key in FORMAL.guardian.LOCK_CLOSE_FIELDS}
        close_record.update(
            {
                "errors": [],
                "frozen_ledger": state.ledger,
                "outcome": "SUCCESS_CANDIDATE",
                "schema_version": FORMAL.success_verifier.GUARDIAN_LOCK_CLOSE_SCHEMA,
                "status": "GUARDIAN_COPIES_CLOSED",
                "success_eligible": True,
            }
        )

        class Host:
            locks_released = False

            def lock_evidence(self) -> list[dict[str, object]]:
                return _lock_evidence()

            def release_locks_once(self) -> dict[str, object]:
                events.append("supervisor-lock-release")
                self.locks_released = True
                return {"released": True}

        monkeypatch.setattr(FORMAL, "_normal_closeout_checkpoint", normal_checkpoint)
        monkeypatch.setattr(
            FORMAL,
            "_post_release_signal_checkpoint",
            post_checkpoint,
        )
        monkeypatch.setattr(FORMAL, "guardian_is_alive", lambda _session: True)
        monkeypatch.setattr(
            FORMAL,
            "send_guardian_terminal",
            lambda *_args, **_kwargs: events.append("guardian-close"),
        )
        monkeypatch.setattr(
            FORMAL.guardian,
            "receive_frame",
            lambda *_args, **_kwargs: SimpleNamespace(
                identity=_identity("guardian-ack"),
                record=close_record,
            ),
        )
        monkeypatch.setattr(
            FORMAL,
            "_close_guardian_connection",
            lambda _session: events.append("guardian-connection-close"),
        )
        monkeypatch.setattr(
            FORMAL,
            "_wait_guardian_absence",
            lambda *_args, **_kwargs: events.append("guardian-absence-wait")
            or {
                "cgroup_absent": True,
                "pid_absent": True,
                "systemctl": HELPER.ABSENT,
                "unit_absent": True,
            },
        )
        monkeypatch.setattr(
            FORMAL,
            "_publish_tracked_phase",
            lambda _attempt, _store, *, key, **_kwargs: events.append(
                f"publish:{key}"
            )
            or _identity(key),
        )
        with pytest.raises(
            FORMAL.IrreversibleFormalFailure,
            match="termination signal latched",
        ):
            FORMAL._release_guardian_and_raw_locks(
                context={
                    "campaign_root_identity": _identity("root"),
                    "manager_epoch": {},
                    "package_id": "c" * 64,
                },
                state=state,
                store=Store(),
                host=Host(),  # type: ignore[arg-type]
                latch=latch,  # type: ignore[arg-type]
                expected={},
            )
        if boundary_name == "before-guardian-close":
            assert "guardian-close" not in events
        else:
            assert "guardian-absence-wait" in events
            assert "supervisor-lock-release" not in events
        return

    with pytest.raises(
        FORMAL.IrreversibleFormalFailure,
        match="termination signal latched",
    ):
        latch.records.append({"signal": 15})
        FORMAL._post_release_signal_checkpoint(
            latch,  # type: ignore[arg-type]
            phase="detached substantive success verifier launch",
        )
        events.append("detached-success")
    assert events == []


def test_selection_wait_checkpoint_precedes_candidate_consumption(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "selection.json"
    candidate.write_text("{}\n", encoding="utf-8")
    calls: list[str] = []

    def stop() -> None:
        calls.append("checkpoint")
        raise FORMAL.IrreversibleFormalFailure("stop before read")

    with pytest.raises(
        FORMAL.IrreversibleFormalFailure,
        match="stop before read",
    ):
        FORMAL._wait_record(
            candidate,
            expected_identity=None,
            label="selection",
            timeout_seconds=1.0,
            monotonic=lambda: 0.0,
            sleeper=lambda _seconds: None,
            checkpoint=stop,
        )
    assert calls == ["checkpoint"]


def test_selection_wait_uses_one_node_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "selection.json"
    candidate.write_bytes(FORMAL.authority.canonical_json({"status": "SELECTED"}))
    candidate.chmod(0o444)
    real_is_file = Path.is_file
    stale_observations = 0

    def stale_once(path: Path) -> bool:
        nonlocal stale_observations
        if path == candidate and stale_observations == 0:
            stale_observations += 1
            return False
        return real_is_file(path)

    monkeypatch.setattr(Path, "is_file", stale_once)

    record, identity = FORMAL._wait_record(
        candidate,
        expected_identity=None,
        label="selection",
        timeout_seconds=1.0,
        monotonic=lambda: 0.0,
        sleeper=lambda _seconds: None,
    )

    assert record == {"status": "SELECTED"}
    assert identity["path"] == str(candidate)
    assert stale_observations == 0


def test_selection_waits_for_readonly_completion(tmp_path: Path) -> None:
    candidate = tmp_path / "selection.json"
    candidate.write_bytes(FORMAL.authority.canonical_json({"status": "SELECTED"}))
    candidate.chmod(0o600)
    sleeps: list[float] = []

    def complete_publication(seconds: float) -> None:
        sleeps.append(seconds)
        candidate.chmod(0o444)

    record, identity = FORMAL._wait_record(
        candidate,
        expected_identity=None,
        label="selection",
        timeout_seconds=1.0,
        monotonic=lambda: 0.0,
        sleeper=complete_publication,
    )

    assert record == {"status": "SELECTED"}
    assert identity["path"] == str(candidate)
    assert sleeps == [FORMAL.POLL_SECONDS]


def test_arm_request_wait_uses_one_node_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "arm-request.json"
    candidate.write_bytes(b"request")
    candidate.chmod(0o444)
    real_is_file = Path.is_file
    stale_observations = 0

    def stale_once(path: Path) -> bool:
        nonlocal stale_observations
        if path == candidate and stale_observations == 0:
            stale_observations += 1
            return False
        return real_is_file(path)

    monkeypatch.setattr(Path, "is_file", stale_once)
    monkeypatch.setattr(FORMAL, "_guard_running", lambda *_args: None)

    FORMAL._wait_arm_request(
        state=SimpleNamespace(),
        host=SimpleNamespace(),
        latch=SimpleNamespace(),
        path=candidate,
        slot="organic-arm-a001",
        deadline=FORMAL.time.monotonic() + 1.0,
    )

    assert stale_observations == 0


def test_arm_request_waits_for_readonly_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "arm-request.json"
    candidate.write_bytes(b"request")
    candidate.chmod(0o600)
    sleeps: list[float] = []

    def complete_publication(seconds: float) -> None:
        sleeps.append(seconds)
        candidate.chmod(0o444)

    monkeypatch.setattr(FORMAL, "_guard_running", lambda *_args: None)
    monkeypatch.setattr(FORMAL.time, "sleep", complete_publication)

    FORMAL._wait_arm_request(
        state=SimpleNamespace(),
        host=SimpleNamespace(),
        latch=SimpleNamespace(),
        path=candidate,
        slot="organic-arm-a001",
        deadline=FORMAL.time.monotonic() + 1.0,
    )

    assert sleeps == [FORMAL.POLL_SECONDS]


def test_receipt_store_publishes_readonly_validator_surface(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "attempt-consumption.json"
    store = FORMAL.closeout_helper.ReceiptStore()
    record = {"status": "CONSUMED"}

    identity = store.publish(candidate, record, "formal attempt consumption")
    replay, replay_identity = FORMAL.launch_validator.read_canonical_record(
        candidate,
        expected_identity=identity,
        label="formal attempt consumption",
    )

    assert stat.S_IMODE(candidate.stat().st_mode) == 0o444
    assert replay == record
    assert replay_identity == identity


def test_guardian_connection_close_uncertainty_is_never_retried() -> None:
    class Connection:
        calls = 0

        def close(self) -> None:
            self.calls += 1
            raise OSError("uncertain close")

    connection = Connection()
    session = FORMAL.GuardianSession(
        unit_name="guardian.service",
        unit_identity={"processes": [{"pid": 41, "starttime": 9001}]},
        listener=SimpleNamespace(),
        connection=connection,
        ready={},
        ready_identity=_identity("ready"),
        last_message_identity=_identity("message"),
        process_pidfd=None,
    )

    with pytest.raises(OSError, match="uncertain close"):
        FORMAL._close_guardian_connection(session)
    with pytest.raises(
        FORMAL.IrreversibleFormalFailure,
        match="cannot be closed twice",
    ):
        FORMAL._close_guardian_connection(session)

    assert connection.calls == 1
    assert session.connection_close_attempted is True
    assert session.connection_close_returned is False
    assert session.connection_closed is False
    assert session.connection_close_error == {
        "code": "GUARDIAN_CONTROL_CLOSE_FAILED_OR_UNCERTAIN",
        "detail": "OSError: uncertain close",
    }


def test_outer_identity_is_frozen_before_resource_or_receipt_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = FORMAL.SupervisorState()
    selection_identity = _identity("selection")
    prelaunch_identity = _identity("outer-prelaunch")
    state.selection = {
        "outer_spec": {
            "resource_contract": {},
            "unit_name": "outer.service",
        }
    }
    state.selection_identity = selection_identity
    state.attempt.selection_identity = selection_identity
    state.attempt.outer_prelaunch_identity = prelaunch_identity
    state.outer_resource_admission = {"status": "PASS"}
    state.guardian = SimpleNamespace()
    state.ledger = FORMAL.initial_ledger(
        FORMAL._outer_inactive_identity("outer.service")
    )
    state.ledger_sequence = 1
    frozen = {
        "control_group": "/user.slice/outer.service",
        "identity_complete": True,
        "invocation_id": "a" * 32,
        "ownership_classification": "OUTER_LIVE_VERIFIED",
        "processes": [{"pid": 41, "starttime": 9001}],
        "slot": "formal",
        "source": "outer",
        "unit_name": "outer.service",
    }
    monkeypatch.setattr(
        FORMAL,
        "_launch_selected_unit",
        lambda *_args, **_kwargs: {"returncode": 0},
    )

    def fail_after_freeze(
        _host: object,
        *,
        on_frozen: Callable[[Any], None],
        **_kwargs: object,
    ) -> None:
        on_frozen(frozen)
        raise FORMAL.FormalCampaignError("resource drift")

    monkeypatch.setattr(FORMAL, "wait_unit_live", fail_after_freeze)

    class Host:
        def show(self, _unit_name: str) -> dict[str, str]:
            pytest.fail("failure containment re-read the same-name unit")

    host = Host()
    with pytest.raises(FORMAL.FormalCampaignError, match="resource drift"):
        FORMAL._launch_outer(
            boundary=SimpleNamespace(),
            context={},
            state=state,
            store=SimpleNamespace(),
            host=host,  # type: ignore[arg-type]
        )

    assert state.outer_identity == {
        "control_group": frozen["control_group"],
        "invocation_id": frozen["invocation_id"],
        "processes": frozen["processes"],
        "unit_name": frozen["unit_name"],
    }
    assert state.attempt.outer_start_identity is None
    assert FORMAL._freeze_failure_outer(
        state=state,
        host=host,  # type: ignore[arg-type]
    ) == frozen


class _DriverHost:
    def __init__(self, _boundary: object, _locks: object) -> None:
        self.locks_released = False
        self.release_count = 0
        self.lock_identities = _lock_evidence()

    def lock_evidence(self) -> list[dict[str, object]]:
        if self.locks_released:
            raise RuntimeError("locks already released")
        return copy.deepcopy(self.lock_identities)

    def release_locks_once(self) -> dict[str, object]:
        if self.locks_released:
            raise RuntimeError("locks released twice")
        self.locks_released = True
        self.release_count += 1
        return {
            "lock_identities": copy.deepcopy(self.lock_identities),
            "released": True,
        }


def test_failure_terminal_order_is_detached_guardian_raw_unref_then_join(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    state = FORMAL.SupervisorState()
    state.selection_identity = _identity("selection")
    state.attempt.selection_identity = state.selection_identity

    host = _DriverHost(None, None)
    detached_identity = _identity("detached-incomplete")
    failure_identity = _identity("failure-pre-release")
    guardian_absence_identity = _identity("guardian-absence")
    terminal_identity = _identity("failure-terminal-release")

    def detached(**kwargs: object) -> dict[str, object]:
        assert kwargs["host"] is host
        assert host.locks_released is False
        assert kwargs["expected_lock_identities"] == host.lock_identities
        events.append("detached")
        return {
            "detached_incomplete_identity": detached_identity,
            "stderr_sha256": "0" * 64,
            "stdout_sha256": "1" * 64,
        }

    def terminal(**kwargs: object) -> dict[str, object]:
        assert host.locks_released is True
        assert kwargs["detached_substantive_identity"] == detached_identity
        assert kwargs["failure_pre_release_identity"] == failure_identity
        events.append("terminal")
        return terminal_identity

    def raw(**kwargs: object) -> dict[str, object]:
        events.append("raw-release")
        host.locks_released = True
        state.attempt.lock_release_attempted = True
        state.attempt.lock_release_return = {
            "lock_identities": copy.deepcopy(host.lock_identities),
            "released": True,
        }
        identity = _identity("raw-release")
        state.attempt.supervisor_raw_lock_release_identity = identity
        state.supervisor_raw_lock_release_identity = identity
        return {
            "lock_identities": copy.deepcopy(host.lock_identities),
            "lock_release_effect": state.attempt.lock_release_return,
            "supervisor_raw_lock_release_identity": identity,
        }

    def reference(**_kwargs: object) -> dict[str, object]:
        events.append("reference")
        return {
            "kind": "NO_REFERENCE_OPENED",
            "post_unref_absence_identity": "absent",
            "reference_connection_close_identity": "absent",
            "reference_release_identity": "absent",
            "reference_terminal_identity": "absent",
            "uncertainty_terminal": "absent",
        }

    monkeypatch.setattr(FORMAL, "_run_detached_incomplete", detached)
    monkeypatch.setattr(FORMAL, "_publish_failure_raw_lock_release", raw)
    monkeypatch.setattr(FORMAL, "_failure_reference_completion", reference)
    monkeypatch.setattr(FORMAL, "_publish_failure_terminal_release", terminal)
    result = FORMAL._complete_pre_release_failure(  # noqa: SLF001
        boundary=SimpleNamespace(formal_dir=tmp_path),
        context={},
        state=state,
        store=SimpleNamespace(),
        host=host,  # type: ignore[arg-type]
        phase="SELECTION_RECORDED_OUTER_NOT_LAUNCHED",
        lock_identities=host.lock_identities,
        failure_pre_release_identity=failure_identity,
        guardian_absence_callback=lambda: (
            events.append("guardian") or guardian_absence_identity
        ),
    )

    assert events == [
        "detached",
        "guardian",
        "raw-release",
        "reference",
        "terminal",
    ]
    assert state.attempt.lock_release_attempted is True
    assert state.attempt.lock_release_return == result["lock_release"]
    assert (
        result["failure_terminal_release_identity"]
        == terminal_identity
    )


def test_post_raw_failure_uses_existing_detached_and_never_replays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = FORMAL.SupervisorState()
    state.selection_identity = _identity("selection")
    state.selection = {"lock_identities": _lock_evidence()}
    state.detached_success_identity = _identity("detached-success")
    state.guardian_absence_identity = _identity("guardian-absence")
    state.supervisor_raw_lock_release_identity = _identity("raw-release")
    state.child_audit_identity = _identity("child-audit")
    state.outer_terminal_identity = _identity("outer-terminal")
    state.attempt.lock_release_attempted = True
    state.attempt.lock_release_return = {
        "lock_identities": _lock_evidence(),
        "released": True,
    }
    host = _DriverHost(None, None)
    host.locks_released = True
    events: list[str] = []

    monkeypatch.setattr(
        STATE,
        "publish_consumed_incomplete",
        lambda *_args, **_kwargs: pytest.fail(
            "post-release failure fabricated a new incomplete receipt"
        ),
    )

    def terminal(**kwargs: object) -> dict[str, object]:
        events.append("terminal")
        assert kwargs["detached_substantive_identity"] == (
            state.detached_success_identity
        )
        assert kwargs["detached_substantive_kind"] == "success_v3"
        assert kwargs["failure_pre_release_identity"] == "absent"
        assert kwargs["guardian_absence_identity"] == (
            state.guardian_absence_identity
        )
        assert kwargs["supervisor_raw_lock_release_identity"] == (
            state.supervisor_raw_lock_release_identity
        )
        return _identity("failure-terminal")

    monkeypatch.setattr(FORMAL, "_publish_failure_terminal_release", terminal)
    monkeypatch.setattr(
        FORMAL,
        "_reference_completion_snapshot",
        lambda _state: {
            "kind": "CONNECTION_UNCERTAIN",
            "post_unref_absence_identity": "unrecorded",
            "reference_connection_close_identity": "unrecorded",
            "reference_release_identity": "unrecorded",
            "reference_terminal_identity": "unrecorded",
            "uncertainty_terminal": {
                "failure": {"code": "FAULT", "detail": "injected"},
                "kind": "REFERENCE_TERMINAL_FAILED_OR_UNCERTAIN",
            },
        },
    )
    result = FORMAL._close_failed_campaign_v4(  # noqa: SLF001
        boundary=SimpleNamespace(),
        context={},
        admission_identity=_identity("admission"),
        state=state,
        store=SimpleNamespace(),
        host=host,  # type: ignore[arg-type]
        latch=SimpleNamespace(),
        error=RuntimeError("post-release fault"),
    )

    assert events == ["terminal"]
    assert result["failure_terminal_release_identity"] == _identity(
        "failure-terminal"
    )


class _DriverLatch:
    instances: list["_DriverLatch"] = []

    def __init__(self) -> None:
        self.installed = False
        self.records: list[dict[str, int]] = []
        self.restored = False
        self.__class__.instances.append(self)

    def install(self) -> None:
        self.installed = True

    def restore(self) -> None:
        self.restored = True


def _patch_driver_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[list[str], dict[str, object]]:
    events: list[str] = []
    boundary = SimpleNamespace(
        campaign=tmp_path,
        formal_dir=tmp_path / "formal-attempt-a001",
    )
    context = {
        "campaign_dir": str(tmp_path),
        "campaign_root_identity": _identity("root"),
        "formal_attempt_dir": str(boundary.formal_dir),
        "formal_receipt_budget_bindings": {
            str(
                (tmp_path / "fixture-budgeted-receipt.json").absolute()
            ): {
                "artifact_class": "normal",
                "label": "fixture-budgeted-receipt",
            }
        },
        "manager_epoch": {},
        "package_id": "c" * 64,
    }
    admission = {"schema_version": "admission"}
    admission_identity = _identity("admission")
    monkeypatch.setattr(
        FORMAL,
        "load_formal_admission",
        lambda _path: (
            boundary,
            context,
            admission,
            admission_identity,
        ),
    )

    def validate_resource(
        path: Path | str,
        *,
        authority_context: Mapping[str, object],
        lock_identities: list[dict[str, object]],
        observation_context: dict[str, object],
        allowed_same_uid_processes: Sequence[Mapping[str, int]] = (),
    ) -> dict[str, object]:
        events.append("resource")
        assert path == context["campaign_dir"]
        assert authority_context is context
        assert lock_identities == _lock_evidence()
        assert observation_context == {
            "authority_id": admission_identity["sha256"],
            "disk_path": str(tmp_path.absolute()),
            "kind": "FORMAL_INITIAL_POST_LOCK",
            "ordinal": 0,
            "scope_id": context["campaign_root_identity"]["sha256"],
            "sequence": 0,
            "slot": "",
            "target": str(boundary.formal_dir),
        }
        assert allowed_same_uid_processes == [
            FORMAL._process_identity(os.getpid())  # noqa: SLF001
        ]
        return {
            "allowed_same_uid_processes": list(allowed_same_uid_processes),
            "lock_identities": copy.deepcopy(lock_identities),
            "observation_context": copy.deepcopy(observation_context),
            "status": "PASS",
        }

    monkeypatch.setattr(FORMAL, "validate_resource_gate", validate_resource)
    monkeypatch.setattr(
        FORMAL,
        "acquire_formal_locks",
        lambda: events.append("locks") or {"locks": 1},
    )
    monkeypatch.setattr(
        FORMAL.closeout_helper,
        "PinnedHost",
        _DriverHost,
    )
    monkeypatch.setattr(
        FORMAL.closeout_helper,
        "ReceiptStore",
        lambda **_kwargs: SimpleNamespace(),
    )
    _DriverLatch.instances.clear()
    monkeypatch.setattr(
        FORMAL.closeout_helper,
        "TerminationLatch",
        _DriverLatch,
    )
    monkeypatch.setattr(
        FORMAL,
        "_supervisor_checkpoint",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        FORMAL,
        "_normal_closeout_checkpoint",
        lambda *_args, **_kwargs: None,
    )
    return events, {
        "admission": admission,
        "admission_identity": admission_identity,
        "boundary": boundary,
        "context": context,
    }


def _driver_capabilities(
    tmp_path: Path,
    *,
    terminal_tail: object | None = None,
) -> FORMAL.FormalSupervisorCapabilities:
    if terminal_tail is None:
        terminal_tail = SimpleNamespace(
            prepare_closure=lambda **_kwargs: {},
            bind_closure_process_baseline=lambda *_args, **_kwargs: {},
            publish_disarm_intent=lambda **_kwargs: {},
            disarm_recovery_once=lambda **_kwargs: {},
            prove_recovery_absence=lambda **_kwargs: {},
            retire_broker_once=lambda **_kwargs: {},
            close_root_once=lambda **_kwargs: {},
            replay_closed_root=lambda **_kwargs: {},
            publish_final_release=lambda *_args, **_kwargs: {},
            prove_final_release_absence=lambda **_kwargs: {},
        )
    backend = SimpleNamespace(
        bind_formal_selection=lambda identity: {
            "selection_identity": dict(identity),
        },
        maximum_bytes=lambda *_args, **_kwargs: 4096,
        publish_bytes=lambda *_args, **_kwargs: {},
    )
    return FORMAL.FormalSupervisorCapabilities(
        budget_backend=backend,
        receipt_budget_bindings={
            str((tmp_path / "fixture-budgeted-receipt.json").absolute()): {
                "artifact_class": "normal",
                "label": "fixture-budgeted-receipt",
            }
        },
        selection_transition=backend,
        terminal_tail_port=terminal_tail,
    )


def test_formal_campaign_requires_capability_bundle_before_authority_or_locks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        FORMAL,
        "load_formal_admission",
        lambda *_args, **_kwargs: pytest.fail(
            "authority replay ran without a capability bundle"
        ),
    )
    monkeypatch.setattr(
        FORMAL,
        "acquire_formal_locks",
        lambda: pytest.fail("locks acquired without a capability bundle"),
    )
    with pytest.raises(
        FORMAL.FormalCampaignError,
        match="lacks its package-pinned capability bundle",
    ):
        FORMAL.run_formal_campaign(tmp_path)


def test_formal_campaign_rejects_receipt_binding_drift_before_locks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    boundary = SimpleNamespace()
    context = {"formal_receipt_budget_bindings": {}}
    monkeypatch.setattr(
        FORMAL,
        "load_formal_admission",
        lambda *_args, **_kwargs: (
            boundary,
            context,
            {},
            _identity("admission"),
        ),
    )
    monkeypatch.setattr(
        FORMAL.closeout_helper,
        "ReceiptStore",
        lambda **_kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        FORMAL,
        "acquire_formal_locks",
        lambda: pytest.fail("locks acquired after binding drift"),
    )
    with pytest.raises(
        FORMAL.FormalCampaignError,
        match="do not equal the package-bound context",
    ):
        FORMAL.run_formal_campaign(
            tmp_path,
            capabilities=_driver_capabilities(tmp_path),
        )


def test_guardian_launch_rechecks_resources_and_owner_at_selected_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Listener:
        closed = False
        bound = False
        parent_owned = False
        remove_attempted = False

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def close_once(self) -> None:
            self.closed = True

    class Host:
        @staticmethod
        def show(_unit_name: str) -> dict[str, str]:
            return dict(FORMAL.closeout_helper.ABSENT)

    admission = {"publisher": {"actor": {"pid": 4040, "starttime": 5050}}}
    resource_receipt = {"status": "PASS"}
    owner_calls: list[tuple[object, str]] = []
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        FORMAL.guardian,
        "GuardianControlListener",
        Listener,
    )
    monkeypatch.setattr(
        FORMAL,
        "_validate_live_launch_owner",
        lambda artifact, *, label: owner_calls.append((artifact, label))
        or {"pid": 4040, "starttime": 5050},
    )

    def reject_after_edge(
        _host: object,
        **kwargs: object,
    ) -> dict[str, object]:
        captured.update(kwargs)
        owner_check = kwargs["launch_owner_check"]
        assert callable(owner_check)
        owner_check()
        raise RuntimeError("controlled post-edge stop")

    monkeypatch.setattr(FORMAL, "_launch_selected_unit", reject_after_edge)
    monkeypatch.setattr(
        FORMAL,
        "_wait_uncertain_unit_resolution",
        lambda *_args, **_kwargs: dict(FORMAL.closeout_helper.ABSENT),
    )

    with pytest.raises(FORMAL.GuardianLaunchFailure):
        FORMAL.start_guardian(
            boundary=SimpleNamespace(),
            context={
                "guardian_control_retired_socket_path": "/tmp/retired.sock",
                "guardian_control_socket_path": "/tmp/control.sock",
                "guardian_spec": {"unit_name": "ab16-guardian.service"},
            },
            admission=admission,
            admission_identity=_identity("admission"),
            resource_admission_receipt=resource_receipt,
            host=Host(),
            store=SimpleNamespace(),
        )

    assert captured["resource_admission_receipt"] is resource_receipt
    assert owner_calls == [
        (admission, "formal launch admission at guardian launch"),
    ]


def test_top_level_driver_preserves_the_fixed_success_order_and_release(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events, _ = _patch_driver_shell(monkeypatch, tmp_path)
    guardian_session = SimpleNamespace()
    marker, marker_identity = {"consumed": True}, _identity("marker")
    selection_identity = _identity("selection")
    selection = {
        "lock_identities": _lock_evidence(),
        "outer_spec": {"receipt_paths": {}},
    }

    def start_guardian(**kwargs: object) -> object:
        resource_receipt = kwargs["resource_admission_receipt"]
        assert isinstance(resource_receipt, dict)
        assert resource_receipt["status"] == "PASS"
        events.append("guardian")
        return guardian_session

    def create_attempt(**kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        events.append("attempt")
        state = kwargs["state"]
        assert isinstance(state, FORMAL.SupervisorState)
        state.attempt.directory_created = True
        state.attempt.marker_identity = marker_identity
        return marker, marker_identity

    monkeypatch.setattr(FORMAL, "start_guardian", start_guardian)
    monkeypatch.setattr(FORMAL, "_create_consumed_attempt", create_attempt)
    monkeypatch.setattr(
        FORMAL,
        "wait_and_validate_selection",
        lambda **_: events.append("selection")
        or (selection, selection_identity),
    )
    for name, event in (
        ("activate_guardian", "activate"),
        ("_publish_outer_prelaunch", "outer-prelaunch"),
        ("_launch_outer", "outer-launch"),
        ("_acquire_outer_reference", "ref-acquire"),
    ):
        monkeypatch.setattr(
            FORMAL,
            name,
            lambda *args, _event=event, **kwargs: events.append(_event)
            or {"status": "PASS"},
        )
    controller_identity = _identity("controller")
    monkeypatch.setattr(
        FORMAL,
        "_service_fixed_campaign",
        lambda **_: events.append("campaign")
        or ({"status": "PASS"}, controller_identity),
    )

    def normal_closeout(**kwargs: object) -> dict[str, object]:
        events.append("normal-closeout")
        host = kwargs["host"]
        assert isinstance(host, _DriverHost)
        assert host.locks_released is False
        return {"status": "PASS"}

    monkeypatch.setattr(FORMAL, "_publish_normal_closeout", normal_closeout)
    def detached_success(**kwargs: object) -> dict[str, object]:
        events.append("detached-success")
        host = kwargs["host"]
        state = kwargs["state"]
        assert isinstance(host, _DriverHost)
        assert isinstance(state, FORMAL.SupervisorState)
        assert host.locks_released is False
        identity = _identity("detached")
        state.detached_success_identity = identity
        return {"detached_success_identity": identity}

    def release(**kwargs: object) -> dict[str, object]:
        events.append("guardian-raw-lock-release")
        host = kwargs["host"]
        assert isinstance(host, _DriverHost)
        assert host.locks_released is False
        effect = host.release_locks_once()
        return {
            "lock_identities": _lock_evidence(),
            "lock_release_effect": effect,
            "supervisor_raw_lock_release_identity": _identity("raw-release"),
        }

    def complete(**kwargs: object) -> dict[str, object]:
        events.append("reference-close-final-join")
        host = kwargs["host"]
        assert isinstance(host, _DriverHost)
        assert host.locks_released is True
        assert kwargs["lock_identities"] == _lock_evidence()
        return {"dual_lock_release_identity": _identity("dual")}

    monkeypatch.setattr(FORMAL, "_run_detached_success", detached_success)
    monkeypatch.setattr(FORMAL, "_release_guardian_and_raw_locks", release)
    monkeypatch.setattr(
        FORMAL,
        "_complete_reference_and_final_success",
        complete,
    )

    result = FORMAL.run_formal_campaign(
        tmp_path,
        capabilities=_driver_capabilities(tmp_path),
    )

    assert result["outcome"] == "VERIFIED"
    assert events == [
        "locks",
        "resource",
        "guardian",
        "attempt",
        "selection",
        "activate",
        "outer-prelaunch",
        "outer-launch",
        "ref-acquire",
        "campaign",
        "normal-closeout",
        "detached-success",
        "guardian-raw-lock-release",
        "reference-close-final-join",
    ]
    assert len(_DriverLatch.instances) == 1
    assert _DriverLatch.instances[0].installed is True
    assert _DriverLatch.instances[0].restored is True


def test_top_level_selected_path_runs_real_same_connection_refunit_tail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Prove the production driver reaches the real prospective RefUnit tail."""

    events, fixture = _patch_driver_shell(monkeypatch, tmp_path)
    boundary = fixture["boundary"]
    context = fixture["context"]
    assert isinstance(boundary, SimpleNamespace)
    assert isinstance(context, dict)
    boundary.formal_dir.mkdir()
    boundary.root = {
        "manager_epoch": {
            "boot_id": "b" * 32,
            "dbus_unique_owner": ":1.42",
        },
        "package": {"package_id": "c" * 64},
    }
    boundary.context = {
        "campaign_module": Campaign,
        "root_identity": context["campaign_root_identity"],
    }
    context["manager_epoch"] = boundary.root["manager_epoch"]
    context["formal_final_release_paths"] = {
        "incomplete": str(tmp_path / "failure-terminal-release.json"),
        "success": str(tmp_path / "dual-lock-release.json"),
    }
    store = Store()
    reference = FakeReference()
    monkeypatch.setattr(
        FORMAL.closeout_helper,
        "ReceiptStore",
        lambda **_kwargs: store,
    )

    receipt_paths = {
        name: str(boundary.formal_dir / f"{name.replace('_', '-')}.json")
        for name in (
            "dual_lock_release",
            "post_unref_absence",
            "reference_connection_close",
            "reference_release",
            "reference_terminal",
        )
    }
    selection_identity = _identity("selection")
    selection: dict[str, object] = {
        "lock_identities": _lock_evidence(),
        "outer_spec": {
            "receipt_paths": receipt_paths,
            "unit_name": "outer.service",
        },
    }
    context["outer_spec"] = selection["outer_spec"]
    guardian_session = SimpleNamespace()
    marker: dict[str, object] = {"consumed": True}
    marker_identity = _identity("marker")
    captured_state: dict[str, FORMAL.SupervisorState] = {}
    final_records: dict[str, dict[str, object]] = {}

    class TerminalTail:
        def __init__(self) -> None:
            self.terminal_join_sha256: str | None = None

        def bind_closure_process_baseline(
            self,
            resource_admission_receipt: Mapping[str, object],
        ) -> Mapping[str, object]:
            events.append("tail-bind-baseline")
            return dict(resource_admission_receipt)

        def prepare_closure(
            self,
            *,
            branch: str,
            terminal_join_sha256: str,
        ) -> dict[str, object]:
            events.append("tail-prepare")
            self.terminal_join_sha256 = terminal_join_sha256
            return {
                "branch": branch,
                "state": "CLOSURE_AND_FINAL_RELEASE_CONTROL_PREPARED",
                "terminal_join_sha256": terminal_join_sha256,
            }

        def publish_disarm_intent(
            self,
            *,
            terminal_join_sha256: str,
        ) -> dict[str, object]:
            events.append("tail-disarm-intent")
            return {
                "state": "RECOVERY_DISARM_INTENT_PUBLISHED",
                "terminal_join_sha256": terminal_join_sha256,
            }

        def disarm_recovery_once(
            self,
            *,
            disarm_intent: Mapping[str, object],
        ) -> dict[str, object]:
            events.append("tail-disarm")
            return {
                "disarm_intent": dict(disarm_intent),
                "state": "RECOVERY_DISARMED_ACKNOWLEDGED",
            }

        def prove_recovery_absence(
            self,
            *,
            disarm_observation: Mapping[str, object],
        ) -> dict[str, object]:
            events.append("tail-recovery-absence")
            return {
                "disarm_observation": dict(disarm_observation),
                "state": "RECOVERY_ABSENT_TAKEOVER_LOCK_RELEASED",
            }

        def retire_broker_once(
            self,
            *,
            recovery_absence: Mapping[str, object],
        ) -> dict[str, object]:
            events.append("tail-broker-absence")
            return {
                "recovery_absence": dict(recovery_absence),
                "state": "BROKER_ABSENT_NO_ROOT_WRITERS",
            }

        def close_root_once(
            self,
            *,
            broker_absence: Mapping[str, object],
            terminal_join_sha256: str,
        ) -> dict[str, object]:
            events.append("tail-close-root")
            return {
                "broker_absence": dict(broker_absence),
                "formal_manifest_identity": _identity("formal-manifest"),
                "state": "ROOT_CLOSED_NO_WRITERS",
                "terminal_join_sha256": terminal_join_sha256,
            }

        def replay_closed_root(
            self,
            *,
            implementation: str,
        ) -> dict[str, object]:
            events.append(f"tail-replay-{implementation}")
            schema, implementation_name, source_tag = {
                "primary": (
                    FORMAL.PRIMARY_FORMAL_ROOT_REPLAY_SCHEMA,
                    "package-pinned-primary-v1",
                    "primary-replay-source",
                ),
                "alternate": (
                    FORMAL.ALTERNATE_FORMAL_ROOT_REPLAY_SCHEMA,
                    "package-pinned-stdlib-alternate-v1",
                    "alternate-replay-source",
                ),
            }[implementation]
            source_raw = source_tag.encode()
            # The closure join is supplied to prepare_closure first and is
            # retained by this deterministic zero-authority test port.
            assert self.terminal_join_sha256 is not None
            result = {
                "actor_absence": {
                    "broker_absent": True,
                    "closure_actor_absent": True,
                    "recovery_absent": True,
                },
                "authority": {
                    "changes_certified_exact": False,
                    "changes_cut_state": False,
                    "changes_lower_bound": False,
                    "changes_production": False,
                    "changes_upper_bound": False,
                    "research_only": True,
                },
                "authority_scope": FORMAL.AUTHORITY_SCOPE,
                "formal_manifest_identity": _identity("formal-manifest"),
                "formal_root": str(boundary.formal_dir),
                "implementation": implementation_name,
                "manifest_entries_sha256": "e" * 64,
                "schema_version": schema,
                "state": "FORMAL_ROOT_CLOSURE_ACCEPTED",
                "terminal_join_sha256": self.terminal_join_sha256,
            }
            receipt = _identity(f"{implementation}-outside-replay")
            return {
                "receipt_identity": receipt,
                "result": result,
                "source_identity": {
                    "sha256": hashlib.sha256(source_raw).hexdigest(),
                    "size_bytes": len(source_raw),
                },
            }

        def publish_final_release(
            self,
            payload: Mapping[str, object],
        ) -> dict[str, object]:
            events.append("tail-final-release")
            branch = payload["branch"]
            terminal_record = payload["terminal_record"]
            assert isinstance(branch, str)
            assert isinstance(terminal_record, Mapping)
            final_records[branch] = dict(terminal_record)
            release_paths = context["formal_final_release_paths"]
            assert isinstance(release_paths, Mapping)
            path = release_paths[branch]
            assert isinstance(path, str)
            selected = _identity(f"{branch}-final-release")
            selected["path"] = path
            return {
                "branch": branch,
                "evidence": terminal_record["post_root_closure"],
                "schema_version": FORMAL.FINAL_RELEASE_RESULT_SCHEMA,
                "selected_identity": selected,
                "state": "FINAL_RELEASE_PUBLISHED_UNUSED_SEALED",
                "unused_staging_identity": {"mode_octal": "0444"},
            }

        def prove_final_release_absence(
            self,
            *,
            final_release_result: Mapping[str, object],
        ) -> dict[str, object]:
            events.append("tail-final-release-absence")
            return {
                "final_release_result": dict(final_release_result),
                "state": "FINAL_RELEASE_ACTOR_ABSENT",
            }

    terminal_tail = TerminalTail()

    class ReachableHost(_DriverHost):
        def wait_state(
            self,
            *_args: object,
            **_kwargs: object,
        ) -> dict[str, object]:
            assert self.locks_released is True
            assert reference.events[-1] == "release"
            events.append("post-unref-absence")
            return {
                "cgroup_absent": True,
                "processes_absent": True,
                "systemctl": dict(HELPER.ABSENT),
            }

    monkeypatch.setattr(FORMAL.closeout_helper, "PinnedHost", ReachableHost)

    def start_guardian(**_kwargs: object) -> object:
        events.append("guardian")
        return guardian_session

    def create_attempt(
        **kwargs: object,
    ) -> tuple[dict[str, object], dict[str, object]]:
        events.append("attempt")
        state = kwargs["state"]
        assert isinstance(state, FORMAL.SupervisorState)
        captured_state["state"] = state
        state.attempt.directory_created = True
        state.attempt.marker_identity = marker_identity
        return marker, marker_identity

    def acquire_reference(**kwargs: object) -> dict[str, object]:
        events.append("ref-acquire")
        state = kwargs["state"]
        host = kwargs["host"]
        assert isinstance(state, FORMAL.SupervisorState)
        assert isinstance(host, ReachableHost)
        result = _acquire(
            boundary,
            state.attempt,
            store,
            reference,
            selection_identity=state.selection_identity,
            locks=host.lock_evidence(),
        )
        assert result["kind"] == "RECORDED"
        return result

    def normal_closeout(**kwargs: object) -> dict[str, object]:
        events.append("normal-closeout")
        state = kwargs["state"]
        assert isinstance(state, FORMAL.SupervisorState)
        assert reference.events.count("release") == 0
        state.outer_identity = {
            "control_group": "/user.slice/outer.service",
            "invocation_id": "a" * 32,
            "processes": [{"pid": 401, "starttime": 501}],
            "unit_name": "outer.service",
        }
        state.observer_identity = _identity("observer")
        state.pre_unref_identity = _identity("pre-unref-cleanup")
        state.attempt.observer_identity = state.observer_identity
        state.attempt.pre_unref_cleanup_identity = state.pre_unref_identity
        return {"status": "PASS"}

    def detached_success(**kwargs: object) -> dict[str, object]:
        events.append("detached-success")
        state = kwargs["state"]
        assert isinstance(state, FORMAL.SupervisorState)
        assert reference.events.count("release") == 0
        identity = _identity("detached-success")
        state.detached_success_identity = identity
        state.attempt.detached_success_identity = identity
        return {"detached_success_identity": identity}

    def release_guardian_and_locks(**kwargs: object) -> dict[str, object]:
        events.append("guardian-absence")
        state = kwargs["state"]
        host = kwargs["host"]
        assert isinstance(state, FORMAL.SupervisorState)
        assert isinstance(host, ReachableHost)
        assert reference.events.count("release") == 0
        state.guardian_close_identity = _identity("guardian-close")
        state.guardian_absence_identity = _identity("guardian-absence")
        state.attempt.guardian_close_identity = state.guardian_close_identity
        state.attempt.guardian_absence_identity = state.guardian_absence_identity
        lock_effect = host.release_locks_once()
        state.attempt.lock_release_attempted = True
        state.attempt.lock_release_return = lock_effect
        raw_identity = _identity("raw-lock-release")
        state.attempt.supervisor_raw_lock_release_identity = raw_identity
        state.supervisor_raw_lock_release_identity = raw_identity
        events.append("raw-lock-release")
        return {
            "guardian_absence_identity": state.guardian_absence_identity,
            "guardian_lock_close_identity": state.guardian_close_identity,
            "lock_identities": lock_effect["lock_identities"],
            "lock_release_effect": lock_effect,
            "supervisor_raw_lock_release_identity": raw_identity,
        }

    monkeypatch.setattr(FORMAL, "start_guardian", start_guardian)
    monkeypatch.setattr(FORMAL, "_create_consumed_attempt", create_attempt)

    def select(**_kwargs: object) -> tuple[dict[str, object], dict[str, object]]:
        events.append("selection")
        return selection, selection_identity

    monkeypatch.setattr(
        FORMAL,
        "wait_and_validate_selection",
        select,
    )

    def record_stage(
        *_args: object,
        _event: str,
        **_kwargs: object,
    ) -> dict[str, object]:
        events.append(_event)
        return {"status": "PASS"}

    for name, event in (
        ("activate_guardian", "activate"),
        ("_publish_outer_prelaunch", "outer-prelaunch"),
        ("_launch_outer", "outer-launch"),
    ):
        monkeypatch.setattr(
            FORMAL,
            name,
            lambda *args, _event=event, **kwargs: record_stage(
                *args,
                _event=_event,
                **kwargs,
            ),
        )
    monkeypatch.setattr(FORMAL, "_acquire_outer_reference", acquire_reference)
    controller_identity = _identity("controller")

    def service_campaign(
        **_kwargs: object,
    ) -> tuple[dict[str, object], dict[str, object]]:
        events.append("campaign")
        return {"status": "PASS"}, controller_identity

    monkeypatch.setattr(
        FORMAL,
        "_service_fixed_campaign",
        service_campaign,
    )
    monkeypatch.setattr(FORMAL, "_publish_normal_closeout", normal_closeout)
    monkeypatch.setattr(FORMAL, "_run_detached_success", detached_success)
    monkeypatch.setattr(
        FORMAL,
        "_release_guardian_and_raw_locks",
        release_guardian_and_locks,
    )

    result = FORMAL.run_formal_campaign(
        tmp_path,
        capabilities=_driver_capabilities(
            tmp_path,
            terminal_tail=terminal_tail,
        ),
    )

    assert result["outcome"] == "VERIFIED"
    assert reference.events == [
        "acquire",
        "verify",
        "release",
        "verify_released",
        "close",
    ]
    assert events.index("detached-success") < events.index("guardian-absence")
    assert events.index("raw-lock-release") < events.index("post-unref-absence")
    assert store.records["reference-release.json"]["connection_retained"] is True
    assert (
        store.records["reference-terminal.json"]["connection_verification"][
            "client_unique_name"
        ]
        == reference.client
    )
    assert (
        store.records["reference-terminal.json"]["connection_verification"][
            "manager_owner"
        ]
        == reference.owner
    )
    assert (
        store.records["reference-connection-close.json"][
            "connection_close_attempts"
        ]
        == 1
    )
    assert final_records["success"]["terminal_join"] == {
        "broker_absent_before_manifest": True,
        "detached_success_before_guardian_close": True,
        "formal_root_closed_before_outside_replays": True,
        "guardian_absence_before_supervisor_release": True,
        "locks_released_after_substantive_verification": True,
        "outside_replays_before_final_join": True,
        "post_unref_absence_before_reference_terminal": True,
        "raw_lock_release_before_unref": True,
        "recovery_disarmed_before_manifest": True,
        "reference_connection_close_before_final_join": True,
        "reference_terminal_before_connection_close": True,
    }
    assert events.index("post-unref-absence") < events.index("tail-prepare")
    assert events[-10:] == [
        "tail-prepare",
        "tail-disarm-intent",
        "tail-disarm",
        "tail-recovery-absence",
        "tail-broker-absence",
        "tail-close-root",
        "tail-replay-primary",
        "tail-replay-alternate",
        "tail-final-release",
        "tail-final-release-absence",
    ]
    assert captured_state["state"].attempt.release_attempted is True
    assert captured_state["state"].attempt.close_attempted is True
    assert _DriverLatch.instances[0].restored is True


def test_top_level_post_lock_resource_failure_releases_once_before_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events, fixture = _patch_driver_shell(monkeypatch, tmp_path)
    hosts: list[_DriverHost] = []

    def make_host(boundary: object, locks: object) -> _DriverHost:
        host = _DriverHost(boundary, locks)
        hosts.append(host)
        return host

    def fail_resource(
        _path: Path | str,
        *,
        authority_context: Mapping[str, object],
        lock_identities: list[dict[str, object]],
        observation_context: dict[str, object],
        allowed_same_uid_processes: Sequence[Mapping[str, int]] = (),
    ) -> dict[str, object]:
        events.append("resource")
        assert authority_context is fixture["context"]
        assert lock_identities == _lock_evidence()
        assert observation_context["kind"] == "FORMAL_INITIAL_POST_LOCK"
        assert allowed_same_uid_processes == [
            FORMAL._process_identity(os.getpid())  # noqa: SLF001
        ]
        raise FORMAL.FormalCampaignError("fixture post-lock resource failure")

    monkeypatch.setattr(FORMAL.closeout_helper, "PinnedHost", make_host)
    monkeypatch.setattr(FORMAL, "validate_resource_gate", fail_resource)
    for name in (
        "start_guardian",
        "_create_consumed_attempt",
        "wait_and_validate_selection",
    ):
        monkeypatch.setattr(
            FORMAL,
            name,
            lambda *args, _name=name, **kwargs: pytest.fail(
                f"{_name} ran after post-lock resource failure"
            ),
        )

    with pytest.raises(
        FORMAL.FormalCampaignError,
        match="fixture post-lock resource failure",
    ):
        FORMAL.run_formal_campaign(
            tmp_path,
            capabilities=_driver_capabilities(tmp_path),
        )

    assert events == ["locks", "resource"]
    assert len(hosts) == 1
    assert hosts[0].release_count == 1
    assert hosts[0].locks_released is True
    assert _DriverLatch.instances == []
    boundary = fixture["boundary"]
    assert isinstance(boundary, SimpleNamespace)
    assert boundary.formal_dir.exists() is False


def test_top_level_lock_identity_drift_across_resource_check_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events, fixture = _patch_driver_shell(monkeypatch, tmp_path)
    hosts: list[_DriverHost] = []

    class DriftingHost(_DriverHost):
        evidence_calls = 0

        def lock_evidence(self) -> list[dict[str, object]]:
            self.evidence_calls += 1
            evidence = super().lock_evidence()
            if self.evidence_calls >= 2:
                evidence[0]["inode"] = int(evidence[0]["inode"]) + 1
            return evidence

    def make_host(boundary: object, locks: object) -> DriftingHost:
        host = DriftingHost(boundary, locks)
        hosts.append(host)
        return host

    def resource(
        _path: Path | str,
        *,
        authority_context: Mapping[str, object],
        lock_identities: list[dict[str, object]],
        observation_context: dict[str, object],
        allowed_same_uid_processes: Sequence[Mapping[str, int]] = (),
    ) -> dict[str, object]:
        events.append("resource")
        assert authority_context is fixture["context"]
        assert lock_identities == _lock_evidence()
        assert observation_context["kind"] == "FORMAL_INITIAL_POST_LOCK"
        assert allowed_same_uid_processes == [
            FORMAL._process_identity(os.getpid())  # noqa: SLF001
        ]
        return {"status": "PASS"}

    monkeypatch.setattr(FORMAL.closeout_helper, "PinnedHost", make_host)
    monkeypatch.setattr(FORMAL, "validate_resource_gate", resource)
    monkeypatch.setattr(
        FORMAL,
        "start_guardian",
        lambda **_: pytest.fail("guardian ran after retained lock identity drift"),
    )

    with pytest.raises(
        FORMAL.FormalCampaignError,
        match="lock identities drifted across initial resource admission",
    ):
        FORMAL.run_formal_campaign(
            tmp_path,
            capabilities=_driver_capabilities(tmp_path),
        )

    assert events == ["locks", "resource"]
    assert len(hosts) == 1
    assert hosts[0].evidence_calls == 2
    assert hosts[0].release_count == 1
    assert hosts[0].locks_released is True
    assert _DriverLatch.instances == []
    boundary = fixture["boundary"]
    assert isinstance(boundary, SimpleNamespace)
    assert boundary.formal_dir.exists() is False


def test_top_level_driver_routes_marker_boundary_failure_without_later_effects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events, _ = _patch_driver_shell(monkeypatch, tmp_path)
    guardian_session = SimpleNamespace()
    monkeypatch.setattr(
        FORMAL,
        "start_guardian",
        lambda **_: events.append("guardian") or guardian_session,
    )

    def fail_marker(**kwargs: object) -> None:
        events.append("attempt")
        state = kwargs["state"]
        assert isinstance(state, FORMAL.SupervisorState)
        state.attempt.directory_created = True
        raise RuntimeError("marker write uncertain")

    monkeypatch.setattr(FORMAL, "_create_consumed_attempt", fail_marker)

    def close_failed(**kwargs: object) -> dict[str, object]:
        events.append("failure-closeout")
        state = kwargs["state"]
        host = kwargs["host"]
        assert isinstance(state, FORMAL.SupervisorState)
        assert state.attempt.directory_created is True
        assert state.attempt.marker_identity is None
        assert isinstance(host, _DriverHost)
        host.release_locks_once()
        return {
            "outcome": "INCOMPLETE",
            "phase": "DIRECTORY_CREATED_MARKER_UNRECORDED",
        }

    monkeypatch.setattr(FORMAL, "_close_failed_campaign_v4", close_failed)
    for name in (
        "wait_and_validate_selection",
        "activate_guardian",
        "_publish_outer_prelaunch",
        "_launch_outer",
        "_acquire_outer_reference",
        "_service_fixed_campaign",
        "_publish_normal_closeout",
        "_run_detached_success",
    ):
        monkeypatch.setattr(
            FORMAL,
            name,
            lambda *args, _name=name, **kwargs: pytest.fail(
                f"{_name} ran after the marker boundary failed"
            ),
        )

    result = FORMAL.run_formal_campaign(
        tmp_path,
        capabilities=_driver_capabilities(tmp_path),
    )

    assert result["outcome"] == "INCOMPLETE"
    assert result["phase"] == "DIRECTORY_CREATED_MARKER_UNRECORDED"
    assert events == ["locks", "resource", "guardian", "attempt", "failure-closeout"]
    assert _DriverLatch.instances[0].restored is True


def test_live_launch_owner_is_external_and_stable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = {
        "publisher": {
            "actor": {
                "pid": 4242,
                "starttime": 31337,
            },
        },
    }
    monkeypatch.setattr(
        FORMAL,
        "_process_identity",
        lambda pid: {"pid": pid, "starttime": 31337},
    )
    monkeypatch.setattr(FORMAL.os, "getpid", lambda: 9999)
    assert FORMAL._validate_live_launch_owner(  # noqa: SLF001
        artifact,
        label="fixture",
    ) == {"pid": 4242, "starttime": 31337}

    monkeypatch.setattr(
        FORMAL,
        "_process_identity",
        lambda pid: {"pid": pid, "starttime": 31338},
    )
    with pytest.raises(FORMAL.FormalCampaignError, match="no longer live"):
        FORMAL._validate_live_launch_owner(artifact, label="fixture")  # noqa: SLF001

    monkeypatch.setattr(FORMAL.os, "getpid", lambda: 4242)
    with pytest.raises(FORMAL.FormalCampaignError, match="self-authorized"):
        FORMAL._validate_live_launch_owner(artifact, label="fixture")  # noqa: SLF001
