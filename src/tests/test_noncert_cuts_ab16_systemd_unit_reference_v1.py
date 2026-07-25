from __future__ import annotations

from collections import deque
import ctypes
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import sys
from types import ModuleType
from typing import Any, Callable

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "docs/research/noncert_cuts_ab16_20260724" / "systemd_unit_reference_v1.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "noncert_cuts_ab16_systemd_unit_reference_v1_tested",
        MODULE_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = _load()


class _Function:
    def __init__(self, implementation: Callable[..., Any]) -> None:
        self.implementation = implementation
        self.argtypes: object = None
        self.restype: object = None

    def __call__(self, *args: object) -> object:
        return self.implementation(*args)


def _set_void_pointer(pointer: object, value: int) -> None:
    ctypes.cast(pointer, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.c_void_p(value)


def _set_char_pointer(pointer: object, value: bytes) -> None:
    ctypes.cast(pointer, ctypes.POINTER(ctypes.c_char_p))[0] = ctypes.c_char_p(value)


class _FakeSdBus:
    BUS = 0xB055

    def __init__(
        self,
        *,
        owners: tuple[str, ...] = (":1.42",),
        client_names: tuple[str, ...] = (":1.99",),
        fail_members: dict[bytes, int] | None = None,
        null_reply_members: set[bytes] | None = None,
    ) -> None:
        self.owners = deque(value.encode("ascii") for value in owners)
        self.client_names = deque(value.encode("ascii") for value in client_names)
        self.fail_members = dict(fail_members or {})
        self.null_reply_members = set(null_reply_members or set())
        self.calls: list[dict[str, object]] = []
        self.closed_buses: list[int] = []
        self._next_message = 100
        self._messages: dict[int, dict[str, object]] = {}
        self._replies: dict[int, dict[str, object]] = {}

        self.sd_bus_open_user = _Function(self._open_user)
        self.sd_bus_set_allow_interactive_authorization = _Function(self._set_interactive)
        self.sd_bus_get_unique_name = _Function(self._get_unique_name)
        self.sd_bus_message_new_method_call = _Function(self._new_method_call)
        self.sd_bus_message_append_basic = _Function(self._append_basic)
        self.sd_bus_call = _Function(self._call)
        self.sd_bus_message_get_signature = _Function(self._get_signature)
        self.sd_bus_message_read_basic = _Function(self._read_basic)
        self.sd_bus_message_at_end = _Function(lambda _reply, _complete: 1)
        self.sd_bus_message_is_empty = _Function(self._is_empty)
        self.sd_bus_message_unref = _Function(lambda _message: ctypes.c_void_p())
        self.sd_bus_error_free = _Function(lambda _error: None)
        self.sd_bus_flush_close_unref = _Function(self._close)

    @staticmethod
    def _value(pointer: object) -> int:
        assert isinstance(pointer, ctypes.c_void_p)
        assert pointer.value is not None
        return pointer.value

    @staticmethod
    def _next(values: deque[bytes]) -> bytes:
        assert values
        value = values[0]
        if len(values) > 1:
            values.popleft()
        return value

    def _open_user(self, output: object) -> int:
        _set_void_pointer(output, self.BUS)
        return 0

    def _set_interactive(self, bus: object, enabled: object) -> int:
        assert self._value(bus) == self.BUS
        assert isinstance(enabled, ctypes.c_int)
        assert enabled.value == 0
        return 0

    def _get_unique_name(self, bus: object, output: object) -> int:
        assert self._value(bus) == self.BUS
        _set_char_pointer(output, self._next(self.client_names))
        return 0

    def _new_method_call(
        self,
        bus: object,
        output: object,
        destination: object,
        path: object,
        interface: object,
        member: object,
    ) -> int:
        assert self._value(bus) == self.BUS
        assert isinstance(destination, bytes)
        assert isinstance(path, bytes)
        assert isinstance(interface, bytes)
        assert isinstance(member, bytes)
        self._next_message += 1
        self._messages[self._next_message] = {
            "argument": None,
            "bus": self._value(bus),
            "destination": destination,
            "interface": interface,
            "member": member,
            "path": path,
        }
        _set_void_pointer(output, self._next_message)
        return 0

    def _append_basic(self, request: object, kind: object, value: object) -> int:
        assert kind == b"s"
        request_id = self._value(request)
        raw = ctypes.cast(value, ctypes.c_char_p).value
        assert raw is not None
        self._messages[request_id]["argument"] = raw.decode("utf-8", "strict")
        return 0

    def _call(
        self,
        bus: object,
        request: object,
        timeout: object,
        _error: object,
        reply_output: object,
    ) -> int:
        assert self._value(bus) == self.BUS
        assert isinstance(timeout, ctypes.c_ulong)
        assert timeout.value == 5_000_000
        message = dict(self._messages[self._value(request)])
        self.calls.append(message)
        member = message["member"]
        assert isinstance(member, bytes)
        if member in self.fail_members:
            return self.fail_members[member]
        if member in self.null_reply_members:
            return 1
        self._next_message += 1
        if member == b"GetNameOwner":
            self._replies[self._next_message] = {
                "kind": "string",
                "value": self._next(self.owners),
            }
        else:
            self._replies[self._next_message] = {"kind": "empty"}
        _set_void_pointer(reply_output, self._next_message)
        return 1

    def _get_signature(self, reply: object, complete: object) -> bytes:
        assert complete == 1
        record = self._replies[self._value(reply)]
        assert record["kind"] == "string"
        return b"s"

    def _read_basic(self, reply: object, kind: object, output: object) -> int:
        assert kind == b"s"
        record = self._replies[self._value(reply)]
        assert record["kind"] == "string"
        value = record["value"]
        assert isinstance(value, bytes)
        _set_char_pointer(output, value)
        return 1

    def _is_empty(self, reply: object) -> int:
        return int(self._replies[self._value(reply)]["kind"] == "empty")

    def _close(self, bus: object) -> ctypes.c_void_p:
        self.closed_buses.append(self._value(bus))
        return ctypes.c_void_p()


def _identity(path: Path) -> dict[str, object]:
    value = path.stat()
    return {
        "mode": stat.S_IMODE(value.st_mode),
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": value.st_size,
    }


def _reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake: _FakeSdBus,
) -> tuple[object, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    library = tmp_path / "libsystemd-pinned.so"
    library.write_bytes(b"fixture-libsystemd-v1\n")
    expected = _identity(library)

    def load_same_descriptor(path: object, **_kwargs: object) -> _FakeSdBus:
        prefix = "/proc/self/fd/"
        assert isinstance(path, str) and path.startswith(prefix)
        descriptor = int(path.removeprefix(prefix))
        observed = os.fstat(descriptor)
        assert observed.st_ino == library.stat().st_ino
        assert observed.st_size == expected["size_bytes"]
        return fake

    monkeypatch.setattr(MODULE.ctypes, "CDLL", load_same_descriptor)
    reference = MODULE.PersistentUnitReference(
        library_path=library,
        expected_library_identity=expected,
    )
    return reference, library


def _members(fake: _FakeSdBus) -> list[bytes]:
    return [record["member"] for record in fake.calls]  # type: ignore[misc]


def test_one_connection_uses_only_get_owner_ref_and_unref(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeSdBus()
    reference, _library = _reference(tmp_path, monkeypatch, fake)

    acquired = reference.acquire(
        unit_name="ab16-drill.service",
        expected_manager_owner=":1.42",
    )
    verified = reference.verify(expected_manager_owner=":1.42")
    released = reference.release(
        unit_name="ab16-drill.service",
        expected_manager_owner=":1.42",
    )
    reference.close()
    reference.close()

    assert acquired["client_unique_name"] == ":1.99"
    assert verified["client_unique_name"] == ":1.99"
    assert released["client_unique_name"] == ":1.99"
    assert set(_members(fake)) == {b"GetNameOwner", b"RefUnit", b"UnrefUnit"}
    assert _members(fake).count(b"RefUnit") == 1
    assert _members(fake).count(b"UnrefUnit") == 1
    assert {record["bus"] for record in fake.calls} == {_FakeSdBus.BUS}
    for record in fake.calls:
        if record["member"] == b"GetNameOwner":
            assert record["destination"] == MODULE.DBUS_DESTINATION
            assert record["argument"] == MODULE.SYSTEMD_DESTINATION.decode("ascii")
            assert record["interface"] == MODULE.DBUS_INTERFACE
            assert record["path"] == MODULE.DBUS_PATH
        else:
            assert record["destination"] == MODULE.SYSTEMD_DESTINATION
            assert record["argument"] == "ab16-drill.service"
            assert record["interface"] == MODULE.SYSTEMD_INTERFACE
            assert record["path"] == MODULE.SYSTEMD_PATH
    assert fake.closed_buses == [_FakeSdBus.BUS]


def test_state_machine_rejects_invalid_double_and_held_close(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeSdBus()
    reference, _library = _reference(tmp_path, monkeypatch, fake)

    for invalid in ("", "not-a-service", "../escape.service", "bad/service.service"):
        with pytest.raises(MODULE.UnitReferenceError, match="unit name is invalid"):
            reference.acquire(unit_name=invalid, expected_manager_owner=":1.42")
    assert fake.calls == []

    reference.acquire(
        unit_name="ab16-drill.service",
        expected_manager_owner=":1.42",
    )
    with pytest.raises(MODULE.UnitReferenceError, match="already held"):
        reference.acquire(
            unit_name="other.service",
            expected_manager_owner=":1.42",
        )
    with pytest.raises(MODULE.UnitReferenceError, match="normal close"):
        reference.close()
    reference.release(
        unit_name="ab16-drill.service",
        expected_manager_owner=":1.42",
    )
    with pytest.raises(MODULE.UnitReferenceError, match="does not match"):
        reference.release(
            unit_name="ab16-drill.service",
            expected_manager_owner=":1.42",
        )
    reference.close()

    assert _members(fake).count(b"RefUnit") == 1
    assert _members(fake).count(b"UnrefUnit") == 1


def test_owner_drift_after_ref_is_fail_closed_and_connection_close_releases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeSdBus(owners=(":1.42", ":1.43"))
    reference, _library = _reference(tmp_path, monkeypatch, fake)

    with pytest.raises(MODULE.UnitReferenceError, match="drifted after RefUnit"):
        reference.acquire(
            unit_name="ab16-drill.service",
            expected_manager_owner=":1.42",
        )

    assert reference.acquired_unit == "ab16-drill.service"
    assert reference.abort_close() is False
    assert _members(fake).count(b"RefUnit") == 1
    assert _members(fake).count(b"UnrefUnit") == 0
    assert fake.closed_buses == [_FakeSdBus.BUS]


def test_client_unique_name_drift_is_rejected_on_same_live_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeSdBus(client_names=(":1.99", ":1.100"))
    reference, _library = _reference(tmp_path, monkeypatch, fake)

    with pytest.raises(MODULE.UnitReferenceError, match="client unique name drifted"):
        reference.acquire(
            unit_name="ab16-drill.service",
            expected_manager_owner=":1.42",
        )

    assert reference.acquired_unit == "ab16-drill.service"
    assert reference.abort_close() is True
    assert _members(fake).count(b"RefUnit") == 1
    assert _members(fake).count(b"UnrefUnit") == 1


def test_failed_ref_and_null_owner_reply_never_admit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failed = _FakeSdBus(fail_members={b"RefUnit": -110})
    reference, _library = _reference(tmp_path / "failed", monkeypatch, failed)
    with pytest.raises(MODULE.UnitReferenceError, match=r"RefUnit failed with 110"):
        reference.acquire(
            unit_name="ab16-drill.service",
            expected_manager_owner=":1.42",
        )
    assert reference.acquired_unit is None
    # A failed RefUnit call is delivery-ambiguous.  Closing the exact sender is
    # safe, but it must not be reported as an explicit Unref success.
    assert reference.abort_close() is False
    assert _members(failed).count(b"UnrefUnit") == 0

    null_reply = _FakeSdBus(null_reply_members={b"GetNameOwner"})
    reference, _library = _reference(tmp_path / "null", monkeypatch, null_reply)
    with pytest.raises(MODULE.UnitReferenceError, match="null reply"):
        reference.acquire(
            unit_name="ab16-drill.service",
            expected_manager_owner=":1.42",
        )
    assert reference.acquired_unit is None
    assert reference.abort_close() is True


def test_failed_unref_remains_held_until_abort_connection_close(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeSdBus(fail_members={b"UnrefUnit": -5})
    reference, _library = _reference(tmp_path, monkeypatch, fake)
    reference.acquire(
        unit_name="ab16-drill.service",
        expected_manager_owner=":1.42",
    )

    with pytest.raises(MODULE.UnitReferenceError, match=r"UnrefUnit failed with 5"):
        reference.release(
            unit_name="ab16-drill.service",
            expected_manager_owner=":1.42",
        )

    assert reference.acquired_unit == "ab16-drill.service"
    assert reference.abort_close() is False
    # Do not guess after an ambiguous failed Unref by issuing a second call.
    assert _members(fake).count(b"UnrefUnit") == 1
    assert fake.closed_buses == [_FakeSdBus.BUS]


def test_library_identity_symlink_and_same_fd_toctou_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library = tmp_path / "libsystemd.so"
    library.write_bytes(b"fixture-libsystemd-v1\n")
    identity = _identity(library)
    loaded = False

    def forbidden_load(*_args: object, **_kwargs: object) -> object:
        nonlocal loaded
        loaded = True
        raise AssertionError("identity failure must precede CDLL")

    monkeypatch.setattr(MODULE.ctypes, "CDLL", forbidden_load)
    wrong = dict(identity)
    wrong["sha256"] = "0" * 64
    with pytest.raises(MODULE.UnitReferenceError, match="byte identity drifted"):
        MODULE.PersistentUnitReference(
            library_path=library,
            expected_library_identity=wrong,
        )
    assert loaded is False

    link = tmp_path / "libsystemd-link.so"
    link.symlink_to(library)
    link_identity = dict(identity)
    link_identity["path"] = str(link.absolute())
    with pytest.raises(MODULE.UnitReferenceError, match="cannot open pinned"):
        MODULE.PersistentUnitReference(
            library_path=link,
            expected_library_identity=link_identity,
        )
    assert loaded is False

    original_read = os.read
    mutated = False

    def mutate_during_read(descriptor: int, size: int) -> bytes:
        nonlocal mutated
        data = original_read(descriptor, size)
        if data and not mutated:
            mutated = True
            with library.open("r+b", buffering=0) as stream:
                stream.seek(0)
                stream.write(b"X")
                os.fsync(stream.fileno())
        return data

    monkeypatch.setattr(MODULE.os, "read", mutate_during_read)
    with pytest.raises(MODULE.UnitReferenceError, match="changed during same-FD hash"):
        MODULE.PersistentUnitReference(
            library_path=library,
            expected_library_identity=identity,
        )
    assert mutated is True
    assert loaded is False


def test_live_library_drift_closes_abort_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeSdBus()
    reference, library = _reference(tmp_path, monkeypatch, fake)
    original = library.read_bytes()
    library.write_bytes(b"X" + original[1:])

    with pytest.raises(MODULE.UnitReferenceError, match="libsystemd drifted"):
        reference.acquire(
            unit_name="ab16-drill.service",
            expected_manager_owner=":1.42",
        )

    assert reference.acquired_unit == "ab16-drill.service"
    assert reference.abort_close() is True
    assert fake.closed_buses == [_FakeSdBus.BUS]
