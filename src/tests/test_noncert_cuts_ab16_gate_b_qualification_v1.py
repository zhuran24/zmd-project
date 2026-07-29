from __future__ import annotations

import ctypes
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import stat
import sys
from types import ModuleType
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BOOTSTRAP = _load(
    "noncert_cuts_ab16_gate_b_qualification_bootstrap_tested",
    RESEARCH / "ab16_campaign_bootstrap_v2.py",
)
QUALIFICATION = _load(
    "noncert_cuts_ab16_gate_b_qualification_v1_tested",
    RESEARCH / "ab16_gate_b_qualification_v1.py",
)


def _renderer(path: Path) -> Path:
    path.write_text(
        """
import json

def _render(request):
    record = dict(request["record"])
    record["publisher"] = dict(globals()["__ab16_gate_b_owner_context__"])
    return (
        json.dumps(
            record,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\\n"
    ).encode("utf-8")

def render_gate_b_epoch_observation(request):
    return _render(request)

def render_gate_b_approval(request):
    return _render(request)
""".lstrip(),
        encoding="utf-8",
    )
    return path


def _identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    metadata = path.stat()
    return {
        "mode": stat.S_IMODE(metadata.st_mode),
        "path": str(path.resolve()),
        "sha256": __import__("hashlib").sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _open_competing_locks(paths: tuple[Path, ...]) -> list[int]:
    descriptors: list[int] = []
    try:
        for path in paths:
            descriptor = os.open(path, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
            descriptors.append(descriptor)
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise
    return descriptors


def _handoff_request(
    owner: object,
    *,
    epoch_identity: dict[str, object],
    approval_identity: dict[str, object],
) -> dict[str, object]:
    return {
        "action": "BOOTSTRAP_HANDOFF",
        "actor": owner.actor,
        "campaign_root_identity": {
            "path": "/fixture/campaign-root.json",
            "sha256": "c" * 64,
            "size_bytes": 1,
        },
        "gate1_selection_identity": {
            "path": "/fixture/gate1-selection.json",
            "sha256": "d" * 64,
            "size_bytes": 1,
        },
        "gate_b_approval_identity": approval_identity,
        "gate_b_epoch_identity": epoch_identity,
        "lock_identities": owner.lock_identities,
        "publisher_sequences": [1, 2],
        "schema": QUALIFICATION.HANDOFF_REQUEST_SCHEMA,
        "session_id": owner.session_id,
    }


def _fd_count() -> int:
    return len(os.listdir("/proc/self/fd"))


def _install_fake_session_bus(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[socket.socket, dict[str, str]]:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    runtime.chmod(0o700)
    bus = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        runtime_descriptor = os.open(runtime, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            bus.bind(f"/proc/self/fd/{runtime_descriptor}/bus")
        finally:
            os.close(runtime_descriptor)
    except BaseException:
        bus.close()
        raise
    uid = os.getuid()
    expected_runtime = f"/run/user/{uid}"
    expected = {
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={expected_runtime}/bus",
        "XDG_RUNTIME_DIR": expected_runtime,
    }
    real_open_directory = QUALIFICATION._open_directory  # noqa: SLF001

    def open_fake_runtime(path: Path | str) -> int:
        assert Path(os.path.abspath(os.fspath(path))) == Path(expected_runtime)
        return real_open_directory(runtime)

    monkeypatch.setattr(QUALIFICATION, "_open_directory", open_fake_runtime)
    for key, value in expected.items():
        monkeypatch.setenv(key, value)
    return bus, expected


def _unstarted_owner(tmp_path: Path) -> object:
    return QUALIFICATION.PersistentGateBOwner(
        python_path=Path(os.path.realpath(sys.executable)),
        owner_source_path=RESEARCH / "ab16_gate_b_qualification_v1.py",
        renderer_source_path=tmp_path / "renderer.py",
        renderer_identity={},
        mechanical_publisher="fixture",
        owner_driver="fixture",
        lock_paths=tuple(tmp_path / f"qualification-{index}.lock" for index in range(3)),
    )


def test_preflight_environment_adds_only_verified_fixed_session_bus(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus, expected = _install_fake_session_bus(tmp_path, monkeypatch)
    try:
        before = _fd_count()
        environment = QUALIFICATION._preflight_environment()  # noqa: SLF001
        assert _fd_count() == before
    finally:
        bus.close()

    assert {key: environment[key] for key in expected} == expected
    assert set(environment) == {
        "DBUS_SESSION_BUS_ADDRESS",
        "LANG",
        "LC_ALL",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONHASHSEED",
        "PYTHONNOUSERSITE",
        "TZ",
        "XDG_RUNTIME_DIR",
    }
    clean = QUALIFICATION._clean_environment()  # noqa: SLF001
    assert "DBUS_SESSION_BUS_ADDRESS" not in clean
    assert "XDG_RUNTIME_DIR" not in clean


def test_preflight_environment_ignores_inherited_session_bus_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus, expected = _install_fake_session_bus(tmp_path, monkeypatch)
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/tmp/untrusted-runtime")
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/tmp/untrusted-bus")
    try:
        environment = QUALIFICATION._preflight_environment()  # noqa: SLF001
    finally:
        bus.close()
    assert {key: environment[key] for key in expected} == expected


def test_fake_session_bus_fixture_accepts_long_pytest_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_root = tmp_path / ("long-" + ("x" * 100))
    long_root.mkdir()
    assert len(os.fsencode(long_root / "runtime" / "bus")) > 107
    bus, expected = _install_fake_session_bus(long_root, monkeypatch)
    try:
        environment = QUALIFICATION._preflight_environment()  # noqa: SLF001
    finally:
        bus.close()
    assert {key: environment[key] for key in expected} == expected


def test_gate_b_final_preflight_receipt_uses_unterminated_canonical_contract(
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "receipt.json"
    value = {"schema_version": "fixture-v1", "status": "PASS"}
    raw = QUALIFICATION._canonical_json(value)[:-1]  # noqa: SLF001
    receipt.write_bytes(raw)
    receipt.chmod(0o444)
    before = _fd_count()
    observed, identity = QUALIFICATION._unterminated_mode_record(  # noqa: SLF001
        receipt,
        "Gate-B final full-preflight receipt",
    )
    assert _fd_count() == before
    assert observed == value
    assert identity == {
        "mode": 0o444,
        "path": str(receipt),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }

    terminated = tmp_path / "terminated.json"
    terminated.write_bytes(QUALIFICATION._canonical_json(value))  # noqa: SLF001
    with pytest.raises(
        QUALIFICATION.QualificationError,
        match="canonical JSON",
    ):
        QUALIFICATION._unterminated_mode_record(  # noqa: SLF001
            terminated,
            "Gate-B final full-preflight receipt",
        )
    assert _fd_count() == before


def test_preflight_environment_rejects_non_socket_bus_without_fd_leak(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    runtime.chmod(0o700)
    (runtime / "bus").write_bytes(b"not-a-socket")
    uid = os.getuid()
    expected_runtime = f"/run/user/{uid}"
    monkeypatch.setenv("XDG_RUNTIME_DIR", expected_runtime)
    monkeypatch.setenv(
        "DBUS_SESSION_BUS_ADDRESS",
        f"unix:path={expected_runtime}/bus",
    )
    real_open_directory = QUALIFICATION._open_directory  # noqa: SLF001
    monkeypatch.setattr(
        QUALIFICATION,
        "_open_directory",
        lambda _path: real_open_directory(runtime),
    )
    before = _fd_count()
    with pytest.raises(
        QUALIFICATION.QualificationError,
        match="session bus node failed validation",
    ):
        QUALIFICATION._preflight_environment()  # noqa: SLF001
    assert _fd_count() == before


def test_pinned_gate_a_preflight_uses_verified_session_bus_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entrypoint = tmp_path / "entrypoint.py"
    entrypoint.write_bytes(b"raise AssertionError('not executed')\n")
    expected_environment = {
        **QUALIFICATION._clean_environment(),  # noqa: SLF001
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1234/bus",
        "XDG_RUNTIME_DIR": "/run/user/1234",
    }
    captured: dict[str, object] = {}

    def run(_argv: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(
            returncode=0,
            stderr=b"",
            stdout=b'{"status":"PASS"}\n',
        )

    monkeypatch.setattr(
        QUALIFICATION,
        "_preflight_environment",
        lambda: dict(expected_environment),
    )
    monkeypatch.setattr(QUALIFICATION.subprocess, "run", run)
    before = _fd_count()
    QUALIFICATION._run_pinned_gate_a_preflight(  # noqa: SLF001
        {
            "observation_identity": {
                "path": str(tmp_path / "observation.json"),
                "sha256": "a" * 64,
                "size_bytes": 1,
            },
            "planned_digest": "b" * 64,
            "repository": tmp_path,
            "scripts": {"gate_a_pinned_entrypoint_v2": entrypoint},
            "system_paths": {"python3_13": Path(os.path.realpath(sys.executable))},
        },
        SimpleNamespace(gate_a_authority_root=tmp_path / "authority"),
        tmp_path / "preflight",
    )
    assert captured["env"] == expected_environment
    assert _fd_count() == before


def test_pinned_gate_a_preflight_environment_failure_closes_source_fds_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entrypoint = tmp_path / "entrypoint.py"
    entrypoint.write_bytes(b"raise AssertionError('not executed')\n")
    real_open_regular = QUALIFICATION._open_regular  # noqa: SLF001
    real_close = os.close
    opened: list[int] = []
    close_count: dict[int, int] = {}
    primary = RuntimeError("session-env-fault")

    def open_regular(path: Path | str) -> int:
        descriptor = real_open_regular(path)
        opened.append(descriptor)
        return descriptor

    def counted_close(descriptor: int) -> None:
        if descriptor in opened:
            close_count[descriptor] = close_count.get(descriptor, 0) + 1
        real_close(descriptor)

    monkeypatch.setattr(QUALIFICATION, "_open_regular", open_regular)
    monkeypatch.setattr(QUALIFICATION.os, "close", counted_close)
    monkeypatch.setattr(
        QUALIFICATION,
        "_preflight_environment",
        lambda: (_ for _ in ()).throw(primary),
    )
    monkeypatch.setattr(
        QUALIFICATION.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("subprocess must not start"),
    )
    before = _fd_count()
    with pytest.raises(RuntimeError, match="session-env-fault") as observed:
        QUALIFICATION._run_pinned_gate_a_preflight(  # noqa: SLF001
            {
                "observation_identity": {
                    "path": str(tmp_path / "observation.json"),
                    "sha256": "a" * 64,
                    "size_bytes": 1,
                },
                "planned_digest": "b" * 64,
                "repository": tmp_path,
                "scripts": {"gate_a_pinned_entrypoint_v2": entrypoint},
                "system_paths": {"python3_13": Path(os.path.realpath(sys.executable))},
            },
            SimpleNamespace(gate_a_authority_root=tmp_path / "authority"),
            tmp_path / "preflight",
        )
    assert observed.value is primary
    assert len(opened) == 2
    assert close_count == {descriptor: 1 for descriptor in opened}
    assert _fd_count() == before


def test_open_regular_runtime_failure_closes_once_without_masking_close_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target.py"
    target.write_bytes(b"fixture\n")
    before = _fd_count()
    real_open = os.open
    real_close = os.close
    real_fstat = os.fstat
    opened: list[int] = []
    close_count: dict[int, int] = {}
    primary = RuntimeError("fstat-fault")

    def injected_open(path: object, *args: object, **kwargs: object) -> int:
        descriptor = real_open(path, *args, **kwargs)
        if os.fspath(path) == target.name and kwargs.get("dir_fd") is not None:
            opened.append(descriptor)
        return descriptor

    def injected_fstat(descriptor: int) -> os.stat_result:
        if opened and descriptor == opened[0]:
            raise primary
        return real_fstat(descriptor)

    def injected_close(descriptor: int) -> None:
        if opened and descriptor == opened[0]:
            close_count[descriptor] = close_count.get(descriptor, 0) + 1
            real_close(descriptor)
            raise OSError("close-fault")
        real_close(descriptor)

    monkeypatch.setattr(QUALIFICATION.os, "open", injected_open)
    monkeypatch.setattr(QUALIFICATION.os, "fstat", injected_fstat)
    monkeypatch.setattr(QUALIFICATION.os, "close", injected_close)
    with pytest.raises(RuntimeError, match="fstat-fault") as observed:
        QUALIFICATION._open_regular(target)  # noqa: SLF001
    assert observed.value is primary
    assert opened and close_count == {opened[0]: 1}
    assert any("close-fault" in note for note in getattr(primary, "__notes__", ()))
    assert _fd_count() == before


def test_component_directory_close_fault_closes_following_descriptor_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    real_open = os.open
    real_close = os.close
    opened: list[int] = []
    close_count: dict[int, int] = {}

    def counted_open(path: object, *args: object, **kwargs: object) -> int:
        descriptor = real_open(path, *args, **kwargs)
        opened.append(descriptor)
        return descriptor

    def injected_close(descriptor: int) -> None:
        close_count[descriptor] = close_count.get(descriptor, 0) + 1
        real_close(descriptor)
        if descriptor == opened[0]:
            raise RuntimeError("ancestor-close-fault")

    monkeypatch.setattr(QUALIFICATION.os, "open", counted_open)
    monkeypatch.setattr(QUALIFICATION.os, "close", injected_close)
    with pytest.raises(RuntimeError, match="ancestor-close-fault") as observed:
        QUALIFICATION._open_directory(tmp_path)  # noqa: SLF001
    assert len(opened) == 2
    assert close_count == {descriptor: 1 for descriptor in opened}
    assert not getattr(observed.value, "__notes__", ())
    assert _fd_count() == before


def test_lock_and_memfd_validation_faults_close_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    real_open = os.open
    real_close = os.close
    libc = ctypes.CDLL(None, use_errno=True)
    real_memfd_create = libc.memfd_create
    real_memfd_create.argtypes = [ctypes.c_char_p, ctypes.c_uint]
    real_memfd_create.restype = ctypes.c_int
    lock_fd: list[int] = []
    memfd: list[int] = []
    close_count: dict[int, int] = {}

    def injected_open(path: object, *args: object, **kwargs: object) -> int:
        descriptor = real_open(path, *args, **kwargs)
        if os.fspath(path) == "qualification.lock" and kwargs.get("dir_fd") is not None:
            lock_fd.append(descriptor)
        return descriptor

    def injected_memfd_create(name: str, flags: int) -> int:
        descriptor = int(real_memfd_create(name.encode("ascii"), flags))
        assert descriptor >= 0
        memfd.append(descriptor)
        return descriptor

    def counted_close(descriptor: int) -> None:
        if descriptor in (*lock_fd, *memfd):
            close_count[descriptor] = close_count.get(descriptor, 0) + 1
        real_close(descriptor)

    monkeypatch.setattr(QUALIFICATION.os, "open", injected_open)
    monkeypatch.setattr(
        QUALIFICATION.os,
        "memfd_create",
        injected_memfd_create,
        raising=False,
    )
    monkeypatch.setattr(QUALIFICATION.os, "close", counted_close)
    monkeypatch.setattr(
        QUALIFICATION,
        "_lock_identity",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("lock-fault")),
    )
    with pytest.raises(RuntimeError, match="lock-fault"):
        QUALIFICATION._acquire_lock(tmp_path / "qualification.lock")  # noqa: SLF001
    assert len(lock_fd) == 1
    assert close_count == {lock_fd[0]: 1}
    close_count.clear()

    monkeypatch.setattr(
        QUALIFICATION.fcntl,
        "fcntl",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("seal-fault")),
    )
    with pytest.raises(RuntimeError, match="seal-fault"):
        QUALIFICATION._sealed_memfd("fixture", b"fixture")  # noqa: SLF001
    assert len(memfd) == 1
    assert close_count == {memfd[0]: 1}
    assert _fd_count() == before


def test_partial_lock_duplication_closes_once_and_preserves_primary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    real_open = os.open
    real_dup = os.dup
    real_close = os.close
    originals = [real_open("/dev/null", os.O_RDONLY | os.O_CLOEXEC) for _ in range(3)]
    duplicated: list[int] = []
    close_count: dict[int, int] = {}
    primary = RuntimeError("dup-fault")
    calls = 0
    owner = _unstarted_owner(tmp_path)
    owner._lock_fds = originals  # noqa: SLF001

    def injected_dup(descriptor: int) -> int:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise primary
        result = real_dup(descriptor)
        duplicated.append(result)
        return result

    def injected_close(descriptor: int) -> None:
        if descriptor in duplicated:
            close_count[descriptor] = close_count.get(descriptor, 0) + 1
            real_close(descriptor)
            raise OSError("dup-close-fault")
        real_close(descriptor)

    monkeypatch.setattr(QUALIFICATION.os, "dup", injected_dup)
    monkeypatch.setattr(QUALIFICATION.os, "close", injected_close)
    with pytest.raises(RuntimeError, match="dup-fault") as observed:
        owner.duplicate_lock_fds()
    assert observed.value is primary
    assert duplicated and close_count == {duplicated[0]: 1}
    assert any("dup-close-fault" in note for note in getattr(primary, "__notes__", ()))
    for descriptor in originals:
        real_close(descriptor)
    assert _fd_count() == before


def test_start_failure_closes_each_acquired_lock_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    real_open = os.open
    real_close = os.close
    acquired: list[int] = []
    close_count: dict[int, int] = {}

    def acquire(_path: object) -> int:
        descriptor = real_open("/dev/null", os.O_RDWR | os.O_CLOEXEC)
        acquired.append(descriptor)
        return descriptor

    def counted_close(descriptor: int) -> None:
        if descriptor in acquired:
            close_count[descriptor] = close_count.get(descriptor, 0) + 1
        real_close(descriptor)

    monkeypatch.setattr(QUALIFICATION, "_acquire_lock", acquire)
    monkeypatch.setattr(
        QUALIFICATION,
        "_open_regular",
        lambda _path: (_ for _ in ()).throw(RuntimeError("source-open-fault")),
    )
    monkeypatch.setattr(QUALIFICATION.os, "close", counted_close)
    owner = _unstarted_owner(tmp_path)
    with pytest.raises(RuntimeError, match="source-open-fault"):
        owner.start()
    assert len(acquired) == 3
    assert close_count == {descriptor: 1 for descriptor in acquired}
    assert owner._descriptors == []  # noqa: SLF001
    assert owner._lock_fds == []  # noqa: SLF001
    assert _fd_count() == before


def test_retain_registration_failure_closes_unregistered_descriptor_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    real_open = os.open
    real_close = os.close
    descriptor = real_open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
    close_count = 0

    class RejectingList(list[int]):
        def append(self, _value: int) -> None:
            raise RuntimeError("registration-fault")

    def counted_close(observed: int) -> None:
        nonlocal close_count
        if observed == descriptor:
            close_count += 1
        real_close(observed)

    owner = _unstarted_owner(tmp_path)
    owner._descriptors = RejectingList()  # noqa: SLF001
    monkeypatch.setattr(QUALIFICATION.os, "close", counted_close)
    with pytest.raises(RuntimeError, match="registration-fault"):
        owner._retain_descriptor(descriptor)  # noqa: SLF001
    assert close_count == 1
    assert _fd_count() == before


def test_owner_cleanup_retries_interrupted_wait_and_preserves_primary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    real_open = os.open
    real_close = os.close
    retained = real_open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
    stderr = open("/dev/null", "rb")  # noqa: SIM115
    control, peer = socket.socketpair()
    close_count = 0
    primary = RuntimeError("active-fault")

    class FakeProcess:
        def __init__(self) -> None:
            self.stderr = stderr
            self.wait_calls = 0
            self.kill_calls = 0

        def poll(self) -> None:
            return None

        def wait(self, *, timeout: float | None = None) -> int:
            del timeout
            self.wait_calls += 1
            if self.wait_calls == 1:
                raise InterruptedError
            return 2

        def kill(self) -> None:
            self.kill_calls += 1

    process = FakeProcess()
    owner = _unstarted_owner(tmp_path)
    owner._process = process  # type: ignore[assignment]  # noqa: SLF001
    owner._control = control  # noqa: SLF001
    owner._descriptors = [retained]  # noqa: SLF001
    owner._lock_fds = [retained]  # noqa: SLF001

    def injected_close(descriptor: int) -> None:
        nonlocal close_count
        if descriptor == retained:
            close_count += 1
            real_close(descriptor)
            raise OSError("retained-close-fault")
        real_close(descriptor)

    monkeypatch.setattr(QUALIFICATION, "_send_frame", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(QUALIFICATION.os, "close", injected_close)
    owner.__exit__(RuntimeError, primary, None)
    peer.close()
    assert process.wait_calls == 2
    assert process.kill_calls == 0
    assert close_count == 1
    assert any("retained-close-fault" in note for note in getattr(primary, "__notes__", ()))
    assert _fd_count() == before


def test_release_retries_interrupted_wait(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    control, peer = socket.socketpair()

    class FakeProcess:
        stderr = None

        def __init__(self) -> None:
            self.exited = False
            self.wait_timeouts: list[float | None] = []

        def poll(self) -> int | None:
            return 0 if self.exited else None

        def wait(self, *, timeout: float | None = None) -> int:
            self.wait_timeouts.append(timeout)
            if len(self.wait_timeouts) == 1:
                raise InterruptedError
            self.exited = True
            return 0

        def kill(self) -> None:
            self.exited = True

    process = FakeProcess()
    owner = _unstarted_owner(tmp_path)
    owner._process = process  # type: ignore[assignment]  # noqa: SLF001
    owner._control = control  # noqa: SLF001
    monkeypatch.setattr(QUALIFICATION, "_send_frame", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        QUALIFICATION,
        "_recv_frame",
        lambda *_args, **_kwargs: {
            "state": "RELEASE_ACCEPTED",
            "status": "PASS",
        },
    )
    owner.release(bootstrap_result=b"{}\n")
    owner.__exit__(None, None, None)
    peer.close()
    assert process.wait_timeouts[:2] == [5, 5]
    assert _fd_count() == before


def test_bootstrap_attach_send_fault_closes_new_socketpair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _fd_count()
    control, peer = socket.socketpair()
    owner = _unstarted_owner(tmp_path)
    owner._control = control  # noqa: SLF001
    before_attach = _fd_count()
    monkeypatch.setattr(
        QUALIFICATION,
        "_send_frame",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("send-fault")),
    )
    with pytest.raises(RuntimeError, match="send-fault"):
        owner.attach_bootstrap_channel()
    assert _fd_count() == before_attach
    owner.__exit__(None, None, None)
    peer.close()
    assert _fd_count() == baseline


def test_bootstrap_second_source_open_fault_closes_first_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    real_open = os.open
    real_close = os.close
    first = real_open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
    close_count = 0
    calls = 0

    def injected_open(_path: object) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            return first
        raise RuntimeError("bootstrap-open-fault")

    def counted_close(descriptor: int) -> None:
        nonlocal close_count
        if descriptor == first:
            close_count += 1
        real_close(descriptor)

    monkeypatch.setattr(QUALIFICATION, "_open_regular", injected_open)
    monkeypatch.setattr(QUALIFICATION.os, "close", counted_close)
    with pytest.raises(RuntimeError, match="bootstrap-open-fault"):
        QUALIFICATION._run_bootstrap_child(  # noqa: SLF001
            {
                "scripts": {"ab16_campaign_bootstrap_v2": tmp_path / "bootstrap.py"},
                "system_paths": {"python3_13": Path(sys.executable)},
            },
            SimpleNamespace(),
            gate_b_approval=tmp_path / "approval.json",
            qualification_fd=-1,
            qualification_lock_fds={},
        )
    assert close_count == 1
    assert _fd_count() == before


def test_duplicated_descriptor_cleanup_attempts_all_once_and_preserves_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    real_open = os.open
    real_close = os.close
    descriptors = tuple(
        real_open("/dev/null", os.O_RDONLY | os.O_CLOEXEC) for _ in range(3)
    )
    close_count: dict[int, int] = {}
    primary = RuntimeError("bootstrap-fault")

    def injected_close(descriptor: int) -> None:
        close_count[descriptor] = close_count.get(descriptor, 0) + 1
        real_close(descriptor)
        if descriptor == descriptors[-1]:
            raise OSError("duplicate-close-fault")

    monkeypatch.setattr(QUALIFICATION.os, "close", injected_close)
    QUALIFICATION._close_descriptors(descriptors, primary=primary)  # noqa: SLF001
    assert close_count == {descriptor: 1 for descriptor in descriptors}
    assert any("duplicate-close-fault" in note for note in getattr(primary, "__notes__", ()))
    assert _fd_count() == before


def test_persistent_owner_holds_actor_locks_and_fds_until_bootstrap_handoff(
    tmp_path: Path,
) -> None:
    renderer = _renderer(tmp_path / "renderer.py")
    lock_paths = tuple(tmp_path / f"qualification-{index}.lock" for index in range(3))
    epoch_path = tmp_path / "published/gate-b-epoch.json"
    approval_path = tmp_path / "published/gate-b-approval.json"
    epoch_path.parent.mkdir()

    with QUALIFICATION.PersistentGateBOwner(
        python_path=Path(os.path.realpath(sys.executable)),
        owner_source_path=RESEARCH / "ab16_gate_b_qualification_v1.py",
        renderer_source_path=renderer,
        renderer_identity=_identity(renderer),
        mechanical_publisher=BOOTSTRAP.OWNER_OEXCL_PUBLISH_V1,
        owner_driver=BOOTSTRAP.GATE_B_OWNER_DRIVER_V1,
        lock_paths=lock_paths,
    ) as owner:
        epoch = owner.publish(
            kind="epoch",
            output_path=epoch_path,
            record={"kind": "epoch"},
        )
        approval = owner.publish(
            kind="approval",
            output_path=approval_path,
            record={"kind": "approval"},
        )
        assert owner.is_alive()
        assert epoch["publisher"]["actor"] == approval["publisher"]["actor"] == owner.actor
        assert epoch["publisher"]["qualification_session"]["sequence"] == 1
        assert approval["publisher"]["qualification_session"]["sequence"] == 2
        assert (
            epoch["publisher"]["qualification_session"]["session_id"]
            == approval["publisher"]["qualification_session"]["session_id"]
            == owner.session_id
        )

        with pytest.raises(BlockingIOError):
            _open_competing_locks(lock_paths)

        fd_links = {
            path.name: os.readlink(path)
            for path in Path(f"/proc/{owner.actor['pid']}/fd").iterdir()
        }
        assert any("ab16-gate-b-request-1" in target for target in fd_links.values())
        assert any("ab16-gate-b-request-2" in target for target in fd_links.values())
        assert any("ab16-gate-b-rendered-1" in target for target in fd_links.values())
        assert any("ab16-gate-b-rendered-2" in target for target in fd_links.values())
        assert any("ab16-gate-b-renderer" in target for target in fd_links.values())
        assert any("ab16-gate-b-publisher" in target for target in fd_links.values())

        channel = owner.attach_bootstrap_channel()
        QUALIFICATION._send_frame(  # noqa: SLF001
            channel,
            _handoff_request(
                owner,
                epoch_identity=_identity(epoch_path),
                approval_identity=_identity(approval_path),
            ),
        )
        handoff = QUALIFICATION._recv_frame(channel)  # noqa: SLF001
        assert handoff["status"] == "PASS"
        assert handoff["actor"] == owner.actor
        assert handoff["session_id"] == owner.session_id
        assert handoff["publisher_sequences"] == [1, 2]
        assert handoff["lock_identities"] == owner.lock_identities
        assert set(handoff["retained_fd_roles"]) == {
            "lock",
            "mechanical_publisher",
            "output_directory",
            "rendered_record",
            "renderer_source",
            "request",
        }
        assert owner.is_alive()

        owner.release(bootstrap_result=b'{"status":"PASS"}\n')
        assert not owner.is_alive()

    competing = _open_competing_locks(lock_paths)
    for descriptor in reversed(competing):
        os.close(descriptor)


def test_persistent_owner_rejects_out_of_order_publication(
    tmp_path: Path,
) -> None:
    renderer = _renderer(tmp_path / "renderer.py")
    lock_paths = tuple(tmp_path / f"qualification-{index}.lock" for index in range(3))
    output = tmp_path / "published/gate-b-approval.json"
    output.parent.mkdir()
    with QUALIFICATION.PersistentGateBOwner(
        python_path=Path(os.path.realpath(sys.executable)),
        owner_source_path=RESEARCH / "ab16_gate_b_qualification_v1.py",
        renderer_source_path=renderer,
        renderer_identity=_identity(renderer),
        mechanical_publisher=BOOTSTRAP.OWNER_OEXCL_PUBLISH_V1,
        owner_driver=BOOTSTRAP.GATE_B_OWNER_DRIVER_V1,
        lock_paths=lock_paths,
    ) as owner:
        with pytest.raises(
            QUALIFICATION.QualificationError,
            match="OWNER_REJECTED:PUBLISH_SEQUENCE",
        ):
            owner.publish(kind="approval", output_path=output, record={"kind": "approval"})
        assert not output.exists()


def test_bootstrap_handoff_rejects_session_or_lock_drift_before_return(
    tmp_path: Path,
) -> None:
    renderer = _renderer(tmp_path / "renderer.py")
    lock_paths = tuple(tmp_path / f"qualification-{index}.lock" for index in range(3))
    epoch_path = tmp_path / "published/gate-b-epoch.json"
    approval_path = tmp_path / "published/gate-b-approval.json"
    epoch_path.parent.mkdir()
    with QUALIFICATION.PersistentGateBOwner(
        python_path=Path(os.path.realpath(sys.executable)),
        owner_source_path=RESEARCH / "ab16_gate_b_qualification_v1.py",
        renderer_source_path=renderer,
        renderer_identity=_identity(renderer),
        mechanical_publisher=BOOTSTRAP.OWNER_OEXCL_PUBLISH_V1,
        owner_driver=BOOTSTRAP.GATE_B_OWNER_DRIVER_V1,
        lock_paths=lock_paths,
    ) as owner:
        epoch = owner.publish(kind="epoch", output_path=epoch_path, record={"kind": "epoch"})
        approval = owner.publish(
            kind="approval",
            output_path=approval_path,
            record={"kind": "approval"},
        )
        channel = owner.attach_bootstrap_channel()
        lock_fds = {
            str(path): descriptor
            for path, descriptor in zip(lock_paths, owner.duplicate_lock_fds(), strict=True)
        }
        try:
            with pytest.raises(
                BOOTSTRAP.BootstrapError,
                match="qualification session",
            ):
                BOOTSTRAP._complete_gate_b_qualification_handoff(  # noqa: SLF001
                    qualification_fd=channel.fileno(),
                    qualification_lock_fds=lock_fds,
                    epoch_publisher=epoch["publisher"],
                    approval_publisher={
                        **approval["publisher"],
                        "qualification_session": {
                            **approval["publisher"]["qualification_session"],
                            "session_id": "f" * 64,
                        },
                    },
                    gate_b_epoch_identity=_identity(epoch_path),
                    gate_b_approval_identity=_identity(approval_path),
                    campaign_root_identity={
                        "path": "/fixture/campaign-root.json",
                        "sha256": "c" * 64,
                        "size_bytes": 1,
                    },
                    gate1_selection_identity={
                        "path": "/fixture/gate1-selection.json",
                        "sha256": "d" * 64,
                        "size_bytes": 1,
                    },
                    expected_lock_paths=tuple(str(path) for path in lock_paths),
                )
        finally:
            for descriptor in lock_fds.values():
                os.close(descriptor)


def test_qualify_orders_locks_preflight_epoch_second_gate_bootstrap_and_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    manager_epoch = {
        "boot_id": "b" * 36,
        "manager_pid": 1,
        "manager_starttime": "1",
    }
    campaign = tmp_path / "run-ab16-fixture"
    output = tmp_path / "qualification"
    renderer = _renderer(tmp_path / "bootstrap.py")
    owner_source = RESEARCH / "ab16_gate_b_qualification_v1.py"
    final_receipt = {"status": "PASS"}

    class FakeBootstrap:
        OWNER_OEXCL_PUBLISH_V1 = "publisher"
        GATE_B_OWNER_DRIVER_V1 = "driver"
        GATE_B_EPOCH_PURPOSE = "epoch"
        GATE_B_EPOCH_SCHEMA = "epoch-v3"
        GATE_B_PURPOSE = "approval"
        GATE_B_SCHEMA = "approval-v4"
        RESULT_SCHEMA = "bootstrap-v3"

        @staticmethod
        def _validate_final_full_preflight(
            value: object,
            *,
            gate_a: object,
            planned: object,
        ) -> object:
            del gate_a, planned
            assert value == final_receipt
            return value

        @staticmethod
        def _capture_epoch(*, scripts: object, system_paths: object) -> dict[str, object]:
            del scripts, system_paths
            events.append("capture-epoch")
            return {"manager_epoch": manager_epoch, "transcript": {"fixture": True}}

        @staticmethod
        def _validate_gate_b_epoch_observation(value: object, **_kwargs: object) -> object:
            return value

        @staticmethod
        def _validate_gate_b(value: object) -> object:
            return value

    bootstrap = FakeBootstrap()
    prepared = {
        "bootstrap": bootstrap,
        "campaign": campaign,
        "candidate_identity": {"path": "/candidate", "sha256": "c" * 64, "size_bytes": 1},
        "gate_a": {
            "approval_id": "gate-a-fixture",
            "full_preflight_receipt_identity": {
                "mode": 0o444,
                "path": "/old/receipt.json",
                "sha256": "0" * 64,
                "size_bytes": 1,
            },
            "manager_epoch": manager_epoch,
            "planned_source_set_digest": "d" * 64,
            "repository_head": "e" * 40,
            "repository_root": str(ROOT),
            "run_nonce": campaign.name,
            "target_campaign_dir": str(campaign),
        },
        "gate_a_identity": {"path": "/gate-a.json", "sha256": "a" * 64, "size_bytes": 1},
        "output": output,
        "planned": {
            "script.ab16_campaign_bootstrap_v2": _identity(renderer),
        },
        "planned_digest": "d" * 64,
        "repository": ROOT,
        "scripts": {
            "ab16_campaign_bootstrap_v2": renderer,
            "ab16_gate_b_qualification_v1": owner_source,
        },
        "system_paths": {"python3_13": Path(os.path.realpath(sys.executable))},
    }
    prepare_count = 0

    def prepare(_args: object, observed_bootstrap: object) -> dict[str, object]:
        nonlocal prepare_count
        assert observed_bootstrap is bootstrap
        prepare_count += 1
        events.append("prepare-before-locks" if prepare_count == 1 else "prepare-under-locks")
        return dict(prepared)

    class FakeOwner:
        def __init__(self, **_kwargs: object) -> None:
            self.actor = {"pid": os.getpid(), "pid_starttime": "1", "role": "AB16_GATE_B_OWNER"}
            self.session_id = "f" * 64
            self.lock_identities = [
                {"path": path, "inode": index}
                for index, path in enumerate(QUALIFICATION.LOCK_PATHS)
            ]
            self._channels: tuple[socket.socket, socket.socket] | None = None

        def __enter__(self) -> FakeOwner:
            events.append("locks-acquired")
            return self

        def __exit__(self, *_args: object) -> None:
            if self._channels is not None:
                for channel in self._channels:
                    channel.close()

        def publish(
            self,
            *,
            kind: str,
            output_path: Path,
            record: dict[str, object],
        ) -> dict[str, object]:
            events.append(f"publish-{kind}")
            sequence = 1 if kind == "epoch" else 2
            rendered = {
                **record,
                "publisher": {
                    "actor": self.actor,
                    "qualification_session": {
                        "lock_identities": self.lock_identities,
                        "sequence": sequence,
                        "session_id": self.session_id,
                    },
                },
            }
            QUALIFICATION._write_exclusive(  # noqa: SLF001
                output_path,
                QUALIFICATION._canonical_json(rendered),  # noqa: SLF001
            )
            return rendered

        def attach_bootstrap_channel(self) -> socket.socket:
            events.append("attach-bootstrap")
            self._channels = socket.socketpair()
            return self._channels[0]

        def duplicate_lock_fds(self) -> tuple[int, ...]:
            return tuple(os.open("/dev/null", os.O_RDONLY) for _ in range(3))

        def release(self, *, bootstrap_result: bytes) -> None:
            assert json.loads(bootstrap_result)["status"] == (
                "FORMAL_CAMPAIGN_AUTHORITY_READY_NO_UNIT_LAUNCHED"
            )
            events.append("release-after-readback")

    def resource_gate(
        _path: Path,
        *,
        stage: str,
        **_kwargs: object,
    ) -> dict[str, object]:
        events.append(f"resource:{stage}")
        return {"stage": stage, "status": "PASS"}

    def preflight(_context: object, _args: object, destination: Path) -> None:
        events.append("pinned-record-preflight")
        destination.mkdir()
        (destination / "receipt.json").write_bytes(
            QUALIFICATION._canonical_json(final_receipt)[:-1]  # noqa: SLF001
        )
        (destination / "receipt.json").chmod(0o444)

    def bootstrap_child(
        context: dict[str, object],
        _args: object,
        **_kwargs: object,
    ) -> tuple[bytes, dict[str, object]]:
        events.append("bootstrap-handoff-readback")
        value = {
            "campaign_dir": str(context["campaign"]),
            "gate_b_qualification_handoff": {"status": "PASS"},
            "schema": bootstrap.RESULT_SCHEMA,
            "status": "FORMAL_CAMPAIGN_AUTHORITY_READY_NO_UNIT_LAUNCHED",
        }
        return QUALIFICATION._canonical_json(value), value  # noqa: SLF001

    monkeypatch.setattr(QUALIFICATION, "_load_bootstrap", lambda _repository: bootstrap)
    monkeypatch.setattr(QUALIFICATION, "_prepare_qualification", prepare)
    monkeypatch.setattr(QUALIFICATION, "PersistentGateBOwner", FakeOwner)
    monkeypatch.setattr(QUALIFICATION, "_resource_gate", resource_gate)
    monkeypatch.setattr(QUALIFICATION, "_run_pinned_gate_a_preflight", preflight)
    monkeypatch.setattr(QUALIFICATION, "_run_bootstrap_child", bootstrap_child)

    result = QUALIFICATION.qualify(
        SimpleNamespace(
            approval_id="gate-b-fixture",
            gate_a_receipt=tmp_path / "gate-a.json",
            offline_candidate=tmp_path / "candidate.json",
            repository_root=ROOT,
        )
    )
    assert result["status"] == "FORMAL_CAMPAIGN_AUTHORITY_READY_NO_UNIT_LAUNCHED"
    assert events == [
        "prepare-before-locks",
        "locks-acquired",
        "prepare-under-locks",
        "resource:BEFORE_FINAL_FULL_PREFLIGHT",
        "pinned-record-preflight",
        "capture-epoch",
        "publish-epoch",
        "resource:AFTER_FINAL_FULL_PREFLIGHT_BEFORE_GATE_B_APPROVAL",
        "publish-approval",
        "attach-bootstrap",
        "bootstrap-handoff-readback",
        "release-after-readback",
    ]
