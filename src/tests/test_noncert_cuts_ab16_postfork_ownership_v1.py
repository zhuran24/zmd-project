from __future__ import annotations

from collections.abc import Callable, Mapping
import hashlib
import os
from pathlib import Path
import signal
import socket
import stat
from typing import Any

import pytest

from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_budget_broker_v1 as broker,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_closure_actor_v1 as closure,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_final_release_actor_v1 as final_release,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_recovery_closeout_v1 as recovery,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_resource_calibration_workloads_v1 as calibration_workloads,
)


ROOT_LIMITS = {
    "closeout": 512 * 1024,
    "metadata": 1024 * 1024,
    "model": 128 * 1024,
    "normal": 128 * 1024,
}
FINAL_RELEASE_MAXIMUM_BYTES = 256 * 1024


def _fd_count() -> int:
    return len(os.listdir("/proc/self/fd"))


def _tracked_fork(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[int, int]]:
    real_fork = os.fork
    children: list[tuple[int, int]] = []

    def fork() -> int:
        pid = real_fork()
        if pid > 0:
            children.append((pid, broker.process_starttime(pid)))
        return pid

    monkeypatch.setattr(os, "fork", fork)
    return children


def _assert_exact_child_reaped(child: tuple[int, int]) -> None:
    pid, starttime = child
    with pytest.raises(ChildProcessError):
        os.waitpid(pid, os.WNOHANG)
    try:
        current_starttime = broker.process_starttime(pid)
    except broker.BrokerProtocolError:
        return
    assert current_starttime != starttime


def _raise_open_pidfd(fault: BaseException) -> Callable[[int], tuple[int, str]]:
    def fail(_pid: int) -> tuple[int, str]:
        raise fault

    return fail


def _tracked_parent_closes(
    monkeypatch: pytest.MonkeyPatch,
    descriptors: tuple[int, ...],
) -> dict[int, int]:
    parent_pid = os.getpid()
    targets = set(descriptors)
    counts = {descriptor: 0 for descriptor in descriptors}
    real_close = os.close

    def close(descriptor: int) -> None:
        if os.getpid() == parent_pid and descriptor in targets:
            counts[descriptor] += 1
        real_close(descriptor)

    monkeypatch.setattr(os, "close", close)
    return counts


def _spawn_test_broker(tmp_path: Path) -> broker.BrokerProcess:
    return broker.spawn_broker_for_test(
        tmp_path / "formal",
        category_limits=ROOT_LIMITS,
    )


def _close_test_broker(process: broker.BrokerProcess) -> None:
    try:
        process.connection.close()
        if not process._waited:  # noqa: SLF001
            assert process.wait() in {0, 2}
    finally:
        process.close()


def _prepare_recovery(
    process: broker.BrokerProcess,
) -> tuple[dict[str, object], tuple[int, ...]]:
    frame = process.request(
        "PREPARE_RECOVERY",
        {"closeout_maximum_bytes": 16 * 1024},
        expected_fd_counts=frozenset({3}),
    )
    return dict(frame.record["result"]), frame.descriptors


def _prepare_closure(
    process: broker.BrokerProcess,
) -> tuple[dict[str, object], tuple[int, ...]]:
    frame = process.request(
        "PREPARE_CLOSURE",
        {
            "budget_terminal_maximum_bytes": 32 * 1024,
            "formal_manifest_maximum_bytes": 128 * 1024,
            "recovery_terminal_maximum_bytes": 16 * 1024,
        },
        expected_fd_counts=frozenset({5}),
    )
    return dict(frame.record["result"]), frame.descriptors


def test_test_broker_open_pidfd_failure_reaps_child_without_fd_growth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    fault = RuntimeError("deterministic test-broker pidfd fault")
    with monkeypatch.context() as patch:
        children = _tracked_fork(patch)
        sockets = _tracked_socketpair(patch)
        patch.setattr(broker, "open_pidfd", _raise_open_pidfd(fault))
        with pytest.raises(RuntimeError) as captured:
            broker.spawn_broker_for_test(
                tmp_path / "broker-open-pidfd-fault",
                category_limits=ROOT_LIMITS,
            )
    assert captured.value is fault
    assert len(children) == 1
    _assert_exact_child_reaped(children[0])
    assert [item.close_count for item in sockets] == [1, 1]
    assert _fd_count() == before


def test_recovery_open_pidfd_failure_reaps_child_and_consumes_fds_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _spawn_test_broker(tmp_path)
    try:
        before = _fd_count()
        prepared, descriptors = _prepare_recovery(process)
        fault = RuntimeError("deterministic recovery pidfd fault")
        with monkeypatch.context() as patch:
            children = _tracked_fork(patch)
            sockets = _tracked_socketpair(patch)
            close_counts = _tracked_parent_closes(patch, descriptors)
            patch.setattr(
                broker,
                "open_pidfd",
                _raise_open_pidfd(fault),
            )
            with pytest.raises(RuntimeError) as captured:
                recovery.spawn_recovery_for_test(
                    broker_process=process,
                    prepared_result=prepared,
                    descriptors=descriptors,
                )
        assert captured.value is fault
        assert len(children) == 1
        _assert_exact_child_reaped(children[0])
        assert [item.close_count for item in sockets] == [1, 1]
        assert set(close_counts.values()) == {1}
        assert _fd_count() == before
        assert not (
            tmp_path
            / "formal/closeout/formal-consumed-incomplete.json"
        ).exists()
    finally:
        _close_test_broker(process)


def test_closure_open_pidfd_failure_reaps_child_and_consumes_fds_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _spawn_test_broker(tmp_path)
    try:
        recovery_result, recovery_descriptors = _prepare_recovery(process)
        for descriptor in recovery_descriptors:
            os.close(descriptor)
        before = _fd_count()
        prepared, descriptors = _prepare_closure(process)
        fault = RuntimeError("deterministic closure pidfd fault")
        with monkeypatch.context() as patch:
            children = _tracked_fork(patch)
            sockets = _tracked_socketpair(patch)
            close_counts = _tracked_parent_closes(patch, descriptors)
            patch.setattr(
                broker,
                "open_pidfd",
                _raise_open_pidfd(fault),
            )
            with pytest.raises(RuntimeError) as captured:
                closure.spawn_closure_for_test(
                    root=tmp_path / "formal",
                    broker_actor=process.actor,
                    broker_pidfd=process.pidfd,
                    recovery_actor=process.actor,
                    recovery_pidfd=process.pidfd,
                    recovery_lock_extent=recovery_result["lock_extent"],
                    prepared_result=prepared,
                    descriptors=descriptors,
                )
        assert captured.value is fault
        assert len(children) == 1
        _assert_exact_child_reaped(children[0])
        assert [item.close_count for item in sockets] == [1, 1]
        assert set(close_counts.values()) == {1}
        assert _fd_count() == before
        assert not (
            tmp_path / "formal/formal-closure/formal-manifest.json"
        ).exists()
    finally:
        _close_test_broker(process)


def _content_identity(tag: str) -> dict[str, object]:
    raw = tag.encode("utf-8")
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _final_extent(
    parent_fd: int,
    *,
    staging_name: str,
    target_name: str,
) -> tuple[dict[str, object], int]:
    descriptor = os.open(
        staging_name,
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | os.O_CLOEXEC
        | os.O_NOFOLLOW,
        0o600,
        dir_fd=parent_fd,
    )
    os.posix_fallocate(descriptor, 0, FINAL_RELEASE_MAXIMUM_BYTES)
    os.fsync(descriptor)
    return (
        {
            "schema_version": broker.PREPARED_EXTENT_SCHEMA,
            "artifact_class": "closeout",
            "maximum_bytes": FINAL_RELEASE_MAXIMUM_BYTES,
            "parent_identity": broker._parent_identity(parent_fd),  # noqa: SLF001
            "parent_path": ".",
            "staging_identity": broker._identity(descriptor),  # noqa: SLF001
            "staging_name": staging_name,
            "target_name": target_name,
        },
        descriptor,
    )


def test_final_release_open_pidfd_failure_reaps_child_and_consumes_fds_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    formal_root = tmp_path / "formal-root"
    release_root = tmp_path / "outside-final-release"
    formal_root.mkdir()
    release_root.mkdir()
    parent_fd = os.open(
        release_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    extents = {
        purpose: _final_extent(
            parent_fd,
            staging_name=f".{purpose}.stage",
            target_name=target,
        )
        for purpose, target in {
            "success": final_release.SUCCESS_TARGET,
            "failure": final_release.FAILURE_TARGET,
            "primary": final_release.PRIMARY_REPLAY_TARGET,
            "alternate": final_release.ALTERNATE_REPLAY_TARGET,
        }.items()
    }
    transferred_descriptors = (
        parent_fd,
        *(descriptor for _extent, descriptor in extents.values()),
    )
    fault = RuntimeError("deterministic final-release pidfd fault")
    with monkeypatch.context() as patch:
        children = _tracked_fork(patch)
        sockets = _tracked_socketpair(patch)
        close_counts = _tracked_parent_closes(
            patch,
            transferred_descriptors,
        )
        patch.setattr(
            broker,
            "open_pidfd",
            _raise_open_pidfd(fault),
        )
        with pytest.raises(RuntimeError) as captured:
            final_release.spawn_final_release_for_test(
                formal_root=formal_root,
                release_root=release_root,
                parent_fd=parent_fd,
                success_fd=extents["success"][1],
                failure_fd=extents["failure"][1],
                primary_replay_fd=extents["primary"][1],
                alternate_replay_fd=extents["alternate"][1],
                success_extent=extents["success"][0],
                failure_extent=extents["failure"][0],
                primary_replay_extent=extents["primary"][0],
                alternate_replay_extent=extents["alternate"][0],
                primary_replay_source_identity=_content_identity("primary"),
                alternate_replay_source_identity=_content_identity(
                    "alternate"
                ),
                source_identity=_content_identity("final-release"),
            )
    assert captured.value is fault
    assert len(children) == 1
    _assert_exact_child_reaped(children[0])
    assert [item.close_count for item in sockets] == [1, 1]
    assert set(close_counts.values()) == {1}
    assert _fd_count() == before
    assert not (release_root / final_release.SUCCESS_TARGET).exists()
    assert not (release_root / final_release.FAILURE_TARGET).exists()
    assert not (release_root / final_release.PRIMARY_REPLAY_TARGET).exists()
    assert not (
        release_root / final_release.ALTERNATE_REPLAY_TARGET
    ).exists()
    assert {
        path.name for path in release_root.iterdir()
    } == {
        ".alternate.stage",
        ".failure.stage",
        ".primary.stage",
        ".success.stage",
    }


class _CountingCapability:
    def __init__(
        self,
        *,
        path: Path | None = None,
        close_error: BaseException | None = None,
    ) -> None:
        self.path = path
        self.close_count = 0
        self._close_error = close_error

    def close(self) -> None:
        self.close_count += 1
        if self._close_error is not None:
            raise self._close_error

    def release_parent_copy(self) -> None:
        self.close()

    def require_verified_role(self, _role: str) -> None:
        return


class _CountingAccount(_CountingCapability):
    def __init__(self, root: Path) -> None:
        super().__init__()
        self.root = root


class _CountingNativeAuthorization(_CountingCapability):
    @property
    def helper(self) -> object:
        return object()


class _CountingSocket:
    def __init__(self, wrapped: socket.socket) -> None:
        self._wrapped = wrapped
        self.close_count = 0

    def close(self) -> None:
        self.close_count += 1
        self._wrapped.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)


def _tracked_socketpair(
    monkeypatch: pytest.MonkeyPatch,
) -> list[_CountingSocket]:
    real_socketpair = socket.socketpair
    sockets: list[_CountingSocket] = []

    def socketpair(*args: object, **kwargs: object) -> tuple[Any, Any]:
        first, second = real_socketpair(*args, **kwargs)
        wrapped = (_CountingSocket(first), _CountingSocket(second))
        sockets.extend(wrapped)
        return wrapped

    monkeypatch.setattr(socket, "socketpair", socketpair)
    return sockets


def test_production_broker_open_pidfd_failure_reaps_and_releases_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    account = _CountingAccount(tmp_path / "formal-root")
    account.root.mkdir()
    close_fault = RuntimeError("deterministic capability close fault")
    reservations = {
        purpose: _CountingCapability(
            close_error=(
                close_fault
                if purpose == sorted(broker.FIXED_PURPOSE_SPECS)[0]
                else None
            )
        )
        for purpose in broker.FIXED_PURPOSE_SPECS
    }
    control = _CountingCapability(path=tmp_path / "control")
    final_parent = _CountingCapability(path=tmp_path / "release")
    package = _CountingCapability()
    native_authorization = _CountingNativeAuthorization()
    identity = {
        "path": str(tmp_path / "identity.json"),
        "sha256": "0" * 64,
        "size_bytes": 1,
    }
    calibration_bundles = {
        stage: {"identity": dict(identity), "record": {}}
        for stage in (
            "FULL_PREFLIGHT",
            "GATE_B_QUALIFICATION",
            "FORMAL_ORGANIC_ARM",
        )
    }
    fault = RuntimeError("deterministic production-broker pidfd fault")

    def pause_owner(**_kwargs: object) -> int:
        while True:
            signal.pause()

    with monkeypatch.context() as patch:
        children = _tracked_fork(patch)
        sockets = _tracked_socketpair(patch)
        patch.setattr(
            broker,
            "open_pidfd",
            _raise_open_pidfd(fault),
        )
        patch.setattr(
            broker,
            "_require_detached_bytes",
            lambda *_args, **_kwargs: dict(identity),
        )
        patch.setattr(
            broker,
            "_detached_identity",
            lambda value, **_kwargs: dict(value),
        )
        patch.setattr(
            broker,
            "_resource_calibration_authorization_bundles",
            lambda _value: calibration_bundles,
        )
        patch.setattr(
            broker,
            "_calibration_tool_content_identities",
            lambda _value: {},
        )
        patch.setattr(
            broker,
            "_bootstrap_handoff_spec",
            lambda value: dict(value),
        )
        patch.setattr(
            broker,
            "_campaign_run_nonce",
            lambda value: str(value),
        )
        patch.setattr(
            broker,
            "_PublicationPolicyState",
            lambda **_kwargs: object(),
        )
        patch.setattr(
            broker,
            "validate_transferred_account",
            lambda *_args, **_kwargs: None,
        )
        patch.setattr(
            broker,
            "validate_transferred_reservations",
            lambda *_args, **_kwargs: None,
        )
        patch.setattr(
            broker,
            "validate_transferred_control_parent",
            lambda *_args, **_kwargs: None,
        )
        patch.setattr(
            broker,
            "validate_transferred_final_release_parent",
            lambda *_args, **_kwargs: None,
        )
        patch.setattr(broker, "_run_persistent_owner", pause_owner)
        with pytest.raises(RuntimeError) as captured:
            broker.spawn_persistent_broker_from_transfer(
                account=account,  # type: ignore[arg-type]
                ownership_handoff={},
                fixed_purpose_reservations=reservations,  # type: ignore[arg-type]
                fixed_purpose_handoffs={
                    purpose: {}
                    for purpose in broker.FIXED_PURPOSE_SPECS
                },
                control_parent_capability=control,  # type: ignore[arg-type]
                control_parent_handoff={},
                final_release_parent_capability=final_parent,  # type: ignore[arg-type]
                final_release_parent_handoff={},
                endpoint_path=tmp_path / "control/broker.sock",
                owner_nonce="1" * 64,
                package_authorization=package,  # type: ignore[arg-type]
                native_helper_authorization=native_authorization,  # type: ignore[arg-type]
                bootstrap_handoff_spec={},
                formal_root_budget_contract_identity=identity,
                formal_resource_calibration_bundle_identity=identity,
                resource_budget_profile_identity={
                    "mode": 0o444,
                    **identity,
                },
                resource_calibration_authorization_bundles=(
                    calibration_bundles
                ),
                calibration_tool_content_identities={},
                package_id="2" * 64,
                campaign_run_nonce="zero-authority-test",
                bootstrap_failure_closeout_path=(
                    tmp_path / "failure-closeout.json"
                ),
            )
    assert captured.value is fault
    assert len(children) == 1
    _assert_exact_child_reaped(children[0])
    assert _fd_count() == before
    assert [item.close_count for item in sockets] == [1, 1]
    assert account.close_count == 1
    assert {item.close_count for item in reservations.values()} == {1}
    assert control.close_count == 1
    assert final_parent.close_count == 1
    assert package.close_count == 1
    assert native_authorization.close_count == 1
    assert any(
        "parent capabilities cleanup also failed" in note
        and "capability close fault" in note
        for note in getattr(fault, "__notes__", ())
    )
    assert list(account.root.iterdir()) == []
    assert not (tmp_path / "failure-closeout.json").exists()


def test_persistent_broker_handle_identity_failure_closes_internal_fd_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retired_parent = tmp_path / "retired-parent"
    retired_parent.mkdir()
    before = _fd_count()
    fault = RuntimeError("deterministic retired-parent identity fault")
    opened: list[int] = []
    close_counts: dict[int, int] = {}
    real_open = broker._open_absolute_directory_no_symlinks  # noqa: SLF001
    real_close = os.close

    def open_parent(path: Path) -> int:
        descriptor = real_open(path)
        opened.append(descriptor)
        close_counts[descriptor] = 0
        return descriptor

    def close(descriptor: int) -> None:
        real_close(descriptor)
        if descriptor in close_counts:
            close_counts[descriptor] += 1
            raise OSError("deterministic close-after-release fault")

    with monkeypatch.context() as patch:
        patch.setattr(
            broker,
            "_open_absolute_directory_no_symlinks",
            open_parent,
        )
        patch.setattr(
            broker,
            "_parent_identity",
            lambda _descriptor: (_ for _ in ()).throw(fault),
        )
        patch.setattr(os, "close", close)
        with pytest.raises(RuntimeError) as captured:
            broker.PersistentBrokerProcess(
                pid=os.getpid(),
                pidfd=-1,
                pidfd_method="fault-injection",
                actor={},
                endpoint_identity={},
                retired_endpoint_path=str(
                    retired_parent / "budget-broker.sock.retired"
                ),
                selected_fd_transport={},
                nonce="1" * 64,
                native_helper=None,
            )
    assert captured.value is fault
    assert len(opened) == 1
    assert close_counts == {opened[0]: 1}
    assert _fd_count() == before
    assert any(
        "retired-parent descriptor cleanup also failed" in note
        and "close-after-release fault" in note
        for note in getattr(fault, "__notes__", ())
    )


def test_calibration_broker_constructor_failure_reaps_worker_and_closes_fd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = tmp_path / "package"
    stage_root = tmp_path / "stage"
    package_root.mkdir()
    stage_root.mkdir()
    package_root_fd = os.open(
        package_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    stage_root_fd = os.open(
        stage_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    binary_descriptors: list[int] = []
    binary_close_counts: dict[int, int] = {}
    parent_pid = os.getpid()
    real_close = os.close
    fault = RuntimeError("deterministic calibration broker fault")

    class FakeHelper:
        def __init__(
            self,
            _descriptor: int,
            *,
            expected_identity: Mapping[str, object],
        ) -> None:
            assert expected_identity == {"status": "fake"}

    class FakeWrapper:
        NativeBudgetHelper = FakeHelper

        @staticmethod
        def expected_package_identity() -> dict[str, object]:
            return {"status": "fake"}

    def open_binary(
        _package_root_fd: int,
        _relative: str,
    ) -> int:
        descriptor = os.dup(package_root_fd)
        binary_descriptors.append(descriptor)
        binary_close_counts[descriptor] = 0
        return descriptor

    def close(descriptor: int) -> None:
        if (
            os.getpid() == parent_pid
            and descriptor in binary_close_counts
        ):
            binary_close_counts[descriptor] += 1
        real_close(descriptor)

    fixture = {
        "aggregate_budget_bytes": 8 * 1024 * 1024,
        "ledger_segment_maximum_bytes": 4096,
        "model_maximum_bytes": 4096,
        "native_helper_binary_member": "native-helper.so",
        "native_helper_wrapper_member": "native-helper.py",
        "schema_version": calibration_workloads.FORMAL_FIXTURE_SCHEMA,
        "stage": "FORMAL_ORGANIC_ARM",
        "variable_count": 1,
    }
    before = _fd_count()
    try:
        with monkeypatch.context() as patch:
            children = _tracked_fork(patch)
            sockets = _tracked_socketpair(patch)
            patch.setattr(
                calibration_workloads,
                "_load_member_module",
                lambda *_args, **_kwargs: FakeWrapper,
            )
            patch.setattr(
                calibration_workloads,
                "_open_member",
                open_binary,
            )
            patch.setattr(
                calibration_workloads,
                "_CalibrationBroker",
                lambda **_kwargs: (_ for _ in ()).throw(fault),
            )
            patch.setattr(os, "close", close)
            with pytest.raises(RuntimeError) as captured:
                calibration_workloads._formal_workload(  # noqa: SLF001
                    fixture,
                    package_root_fd=package_root_fd,
                    package_receipt={},
                    stage_root_fd=stage_root_fd,
                )
        assert captured.value is fault
        assert len(children) == 1
        _assert_exact_child_reaped(children[0])
        assert [item.close_count for item in sockets] == [1, 1]
        assert len(binary_descriptors) == 1
        assert binary_close_counts == {binary_descriptors[0]: 1}
        assert _fd_count() == before
        assert list(stage_root.iterdir()) == []
    finally:
        os.close(stage_root_fd)
        os.close(package_root_fd)
