#!/usr/bin/env python3
"""Persistent, ordinary-user systemd unit references for AB16 evidence.

The object in this module owns one user-bus connection for its entire
lifetime.  It exposes only GetNameOwner, RefUnit, and UnrefUnit.  In
particular, it cannot start, stop, kill, reset, or otherwise manage a unit.

The libsystemd object is opened, hashed, and loaded through the same
``O_NOFOLLOW`` descriptor.  Importing this module performs no I/O and starts
no process or systemd unit.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping


MAX_LIBRARY_BYTES = 16 * 1024 * 1024
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
UNIT_RE = re.compile(r"[A-Za-z0-9_.:@-]+\.service\Z")
UNIQUE_NAME_RE = re.compile(r":[0-9]+\.[0-9]+\Z")

DBUS_DESTINATION = b"org.freedesktop.DBus"
DBUS_PATH = b"/org/freedesktop/DBus"
DBUS_INTERFACE = b"org.freedesktop.DBus"
SYSTEMD_DESTINATION = b"org.freedesktop.systemd1"
SYSTEMD_PATH = b"/org/freedesktop/systemd1"
SYSTEMD_INTERFACE = b"org.freedesktop.systemd1.Manager"


class UnitReferenceError(RuntimeError):
    """The persistent reference could not be established or replayed."""


class _SdBusError(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char_p),
        ("message", ctypes.c_char_p),
        ("need_free", ctypes.c_int),
    ]


def _stat_signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_uid,
        value.st_gid,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _expected_identity(value: object) -> dict[str, object]:
    if type(value) is not dict or set(value) != {
        "mode",
        "path",
        "sha256",
        "size_bytes",
    }:
        raise UnitReferenceError("libsystemd identity key set drifted")
    record = value
    if (
        type(record["mode"]) is not int
        or record["mode"] < 0
        or type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or not 0 < record["size_bytes"] <= MAX_LIBRARY_BYTES
    ):
        raise UnitReferenceError("libsystemd identity is malformed")
    return dict(record)


def _hash_descriptor(
    descriptor: int,
    *,
    absolute: Path,
) -> tuple[dict[str, object], tuple[int, ...]]:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= MAX_LIBRARY_BYTES:
        raise UnitReferenceError(f"invalid pinned libsystemd file: {absolute}")
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
    if _stat_signature(before) != _stat_signature(after) or size != after.st_size:
        raise UnitReferenceError("libsystemd changed during same-FD hash")
    return (
        {
            "mode": stat.S_IMODE(after.st_mode),
            "path": str(absolute),
            "sha256": digest.hexdigest(),
            "size_bytes": size,
        },
        _stat_signature(after),
    )


def _open_pinned_library(
    path: Path | str,
    expected_identity: Mapping[str, Any],
) -> tuple[int, dict[str, object], tuple[int, ...]]:
    expected = _expected_identity(dict(expected_identity))
    absolute = Path(os.path.abspath(os.fspath(path)))
    if str(absolute) != expected["path"]:
        raise UnitReferenceError("libsystemd path differs from pinned identity")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(absolute, flags)
    except OSError as exc:
        raise UnitReferenceError("cannot open pinned libsystemd without following links") from exc
    try:
        observed, signature = _hash_descriptor(descriptor, absolute=absolute)
        if observed != expected:
            raise UnitReferenceError("libsystemd byte identity drifted")
        return descriptor, observed, signature
    except Exception:
        os.close(descriptor)
        raise


class PersistentUnitReference:
    """One exact unit reference held by one persistent sd-bus connection."""

    def __init__(
        self,
        *,
        library_path: Path | str,
        expected_library_identity: Mapping[str, Any],
        method_timeout_usec: int = 5_000_000,
    ) -> None:
        if type(method_timeout_usec) is not int or method_timeout_usec <= 0:
            raise UnitReferenceError("method timeout must be a positive exact integer")
        self._descriptor, self.library_identity, self._signature = _open_pinned_library(
            library_path,
            expected_library_identity,
        )
        try:
            self._library = ctypes.CDLL(
                f"/proc/self/fd/{self._descriptor}",
                mode=os.RTLD_LOCAL | os.RTLD_NOW,
                use_errno=True,
            )
            self._configure()
            bus = ctypes.c_void_p()
            result = self._library.sd_bus_open_user(ctypes.byref(bus))
            self._raise_result(result, "sd_bus_open_user")
            if not bus.value:
                raise UnitReferenceError("sd_bus_open_user returned a null bus")
            self._bus = bus
            self._method_timeout_usec = method_timeout_usec
            self._raise_result(
                self._library.sd_bus_set_allow_interactive_authorization(
                    self._bus,
                    ctypes.c_int(0),
                ),
                "sd_bus_set_allow_interactive_authorization",
            )
            self._unique_name = self._get_unique_name()
            self._acquired_unit: str | None = None
            self._acquired_owner: str | None = None
            self._reference_state_uncertain = False
            self._closed = False
            self._recheck_library()
        except Exception:
            if hasattr(self, "_bus") and self._bus.value:
                self._library.sd_bus_flush_close_unref(self._bus)
            os.close(self._descriptor)
            raise

    def _configure(self) -> None:
        library = self._library
        library.sd_bus_open_user.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        library.sd_bus_open_user.restype = ctypes.c_int
        library.sd_bus_set_allow_interactive_authorization.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        library.sd_bus_set_allow_interactive_authorization.restype = ctypes.c_int
        library.sd_bus_get_unique_name.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_char_p),
        ]
        library.sd_bus_get_unique_name.restype = ctypes.c_int
        library.sd_bus_message_new_method_call.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
        ]
        library.sd_bus_message_new_method_call.restype = ctypes.c_int
        library.sd_bus_message_append_basic.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char,
            ctypes.c_void_p,
        ]
        library.sd_bus_message_append_basic.restype = ctypes.c_int
        library.sd_bus_call.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint64,
            ctypes.POINTER(_SdBusError),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        library.sd_bus_call.restype = ctypes.c_int
        library.sd_bus_message_get_signature.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        library.sd_bus_message_get_signature.restype = ctypes.c_char_p
        library.sd_bus_message_read_basic.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char,
            ctypes.c_void_p,
        ]
        library.sd_bus_message_read_basic.restype = ctypes.c_int
        library.sd_bus_message_at_end.argtypes = [ctypes.c_void_p, ctypes.c_int]
        library.sd_bus_message_at_end.restype = ctypes.c_int
        library.sd_bus_message_is_empty.argtypes = [ctypes.c_void_p]
        library.sd_bus_message_is_empty.restype = ctypes.c_int
        library.sd_bus_message_unref.argtypes = [ctypes.c_void_p]
        library.sd_bus_message_unref.restype = ctypes.c_void_p
        library.sd_bus_error_free.argtypes = [ctypes.POINTER(_SdBusError)]
        library.sd_bus_error_free.restype = None
        library.sd_bus_flush_close_unref.argtypes = [ctypes.c_void_p]
        library.sd_bus_flush_close_unref.restype = ctypes.c_void_p

    @staticmethod
    def _raise_result(result: int, operation: str, error: _SdBusError | None = None) -> None:
        if result >= 0:
            return
        detail = ""
        if error is not None:
            if error.name:
                detail += f" {error.name.decode('utf-8', 'replace')}"
            if error.message:
                detail += f": {error.message.decode('utf-8', 'replace')}"
        raise UnitReferenceError(f"{operation} failed with {-result}{detail}")

    def _get_unique_name(self) -> str:
        raw = ctypes.c_char_p()
        result = self._library.sd_bus_get_unique_name(self._bus, ctypes.byref(raw))
        self._raise_result(result, "sd_bus_get_unique_name")
        if not raw.value:
            raise UnitReferenceError("sd-bus client unique name is absent")
        value = raw.value.decode("ascii", "strict")
        if UNIQUE_NAME_RE.fullmatch(value) is None:
            raise UnitReferenceError("sd-bus client unique name is malformed")
        return value

    def _new_call(
        self,
        *,
        destination: bytes,
        path: bytes,
        interface: bytes,
        member: bytes,
        argument: str,
    ) -> ctypes.c_void_p:
        request = ctypes.c_void_p()
        result = self._library.sd_bus_message_new_method_call(
            self._bus,
            ctypes.byref(request),
            destination,
            path,
            interface,
            member,
        )
        self._raise_result(result, f"{member.decode('ascii')} new message")
        if not request.value:
            raise UnitReferenceError(f"{member.decode('ascii')} returned a null request")
        raw_argument = ctypes.c_char_p(argument.encode("utf-8"))
        try:
            result = self._library.sd_bus_message_append_basic(
                request,
                b"s",
                ctypes.cast(raw_argument, ctypes.c_void_p),
            )
            self._raise_result(result, f"{member.decode('ascii')} append")
            return request
        except Exception:
            self._library.sd_bus_message_unref(request)
            raise

    @staticmethod
    def _error_detail(error: _SdBusError) -> str:
        detail = ""
        if error.name:
            detail += f" {error.name.decode('utf-8', 'replace')}"
        if error.message:
            detail += f": {error.message.decode('utf-8', 'replace')}"
        return detail

    def _call_empty(
        self,
        *,
        destination: bytes,
        path: bytes,
        interface: bytes,
        member: bytes,
        argument: str,
    ) -> None:
        request = ctypes.c_void_p()
        reply = ctypes.c_void_p()
        error = _SdBusError()
        try:
            request = self._new_call(
                destination=destination,
                path=path,
                interface=interface,
                member=member,
                argument=argument,
            )
            result = self._library.sd_bus_call(
                self._bus,
                request,
                ctypes.c_uint64(self._method_timeout_usec),
                ctypes.byref(error),
                ctypes.byref(reply),
            )
            if result < 0:
                detail = self._error_detail(error)
                raise UnitReferenceError(f"{member.decode('ascii')} failed with {-result}{detail}")
            if not reply.value or self._library.sd_bus_message_is_empty(reply) <= 0:
                raise UnitReferenceError(f"{member.decode('ascii')} reply is not empty")
        finally:
            if reply.value:
                self._library.sd_bus_message_unref(reply)
            if request.value:
                self._library.sd_bus_message_unref(request)
            self._library.sd_bus_error_free(ctypes.byref(error))

    def _call_string(
        self,
        *,
        destination: bytes,
        path: bytes,
        interface: bytes,
        member: bytes,
        argument: str,
    ) -> str:
        request = ctypes.c_void_p()
        reply = ctypes.c_void_p()
        error = _SdBusError()
        try:
            request = self._new_call(
                destination=destination,
                path=path,
                interface=interface,
                member=member,
                argument=argument,
            )
            result = self._library.sd_bus_call(
                self._bus,
                request,
                ctypes.c_uint64(self._method_timeout_usec),
                ctypes.byref(error),
                ctypes.byref(reply),
            )
            if result < 0:
                detail = self._error_detail(error)
                raise UnitReferenceError(f"{member.decode('ascii')} failed with {-result}{detail}")
            if not reply.value:
                raise UnitReferenceError(f"{member.decode('ascii')} returned a null reply")
            signature = self._library.sd_bus_message_get_signature(reply, 1)
            if signature != b"s":
                raise UnitReferenceError(f"{member.decode('ascii')} reply signature drifted")
            raw = ctypes.c_char_p()
            result = self._library.sd_bus_message_read_basic(
                reply,
                b"s",
                ctypes.byref(raw),
            )
            if result <= 0:
                raise UnitReferenceError(f"{member.decode('ascii')} reply lacks its exact string")
            if self._library.sd_bus_message_at_end(reply, 1) <= 0:
                raise UnitReferenceError(f"{member.decode('ascii')} reply has trailing fields")
            if not raw.value:
                raise UnitReferenceError(f"{member.decode('ascii')} returned an empty string")
            return raw.value.decode("utf-8", "strict")
        finally:
            if reply.value:
                self._library.sd_bus_message_unref(reply)
            if request.value:
                self._library.sd_bus_message_unref(request)
            self._library.sd_bus_error_free(ctypes.byref(error))

    def manager_owner(self) -> str:
        """Return the manager's unique owner through this exact connection."""

        self._ensure_open()
        value = self._call_string(
            destination=DBUS_DESTINATION,
            path=DBUS_PATH,
            interface=DBUS_INTERFACE,
            member=b"GetNameOwner",
            argument=SYSTEMD_DESTINATION.decode("ascii"),
        )
        if UNIQUE_NAME_RE.fullmatch(value) is None:
            raise UnitReferenceError("manager DBus owner is malformed")
        return value

    @property
    def client_unique_name(self) -> str:
        self._ensure_open()
        current = self._get_unique_name()
        if current != self._unique_name:
            raise UnitReferenceError("sd-bus client unique name drifted")
        return current

    @property
    def acquired_unit(self) -> str | None:
        return self._acquired_unit

    def acquire(self, *, unit_name: str, expected_manager_owner: str) -> dict[str, str]:
        """Acquire exactly one RefUnit reference after owner replay."""

        self._ensure_open()
        self._validate_unit(unit_name)
        self._validate_owner(expected_manager_owner)
        if self._acquired_unit is not None:
            raise UnitReferenceError("a unit reference is already held")
        owner_before = self.manager_owner()
        if owner_before != expected_manager_owner:
            raise UnitReferenceError("manager owner drifted before RefUnit")
        try:
            self._call_empty(
                destination=SYSTEMD_DESTINATION,
                path=SYSTEMD_PATH,
                interface=SYSTEMD_INTERFACE,
                member=b"RefUnit",
                argument=unit_name,
            )
        except Exception:
            # A method timeout can mean that systemd received the call even
            # though the reply was lost.  Closing this exact sender is the
            # only safe cleanup; never claim an explicit Unref in that state.
            self._reference_state_uncertain = True
            raise
        self._acquired_unit = unit_name
        self._acquired_owner = expected_manager_owner
        owner_after = self.manager_owner()
        if owner_after != expected_manager_owner:
            raise UnitReferenceError("manager owner drifted after RefUnit")
        self._recheck_library()
        return {
            "client_unique_name": self.client_unique_name,
            "manager_owner_after": owner_after,
            "manager_owner_before": owner_before,
            "unit_name": unit_name,
        }

    def verify(self, *, expected_manager_owner: str) -> dict[str, str]:
        """Replay the same live connection and manager owner while held."""

        self._ensure_open()
        self._validate_owner(expected_manager_owner)
        if self._acquired_unit is None:
            raise UnitReferenceError("no unit reference is held")
        owner = self.manager_owner()
        if owner != expected_manager_owner:
            raise UnitReferenceError("manager owner drifted while unit reference was held")
        self._recheck_library()
        return {
            "client_unique_name": self.client_unique_name,
            "manager_owner": owner,
            "unit_name": self._acquired_unit,
        }

    def release(self, *, unit_name: str, expected_manager_owner: str) -> dict[str, str]:
        """Release the one held reference and preserve the connection identity."""

        self._ensure_open()
        self._validate_unit(unit_name)
        self._validate_owner(expected_manager_owner)
        if self._acquired_unit != unit_name:
            raise UnitReferenceError("UnrefUnit does not match the held unit")
        owner_before = self.manager_owner()
        if owner_before != expected_manager_owner:
            raise UnitReferenceError("manager owner drifted before UnrefUnit")
        try:
            self._call_empty(
                destination=SYSTEMD_DESTINATION,
                path=SYSTEMD_PATH,
                interface=SYSTEMD_INTERFACE,
                member=b"UnrefUnit",
                argument=unit_name,
            )
        except Exception:
            self._reference_state_uncertain = True
            raise
        self._acquired_unit = None
        self._acquired_owner = None
        self._reference_state_uncertain = False
        owner_after = self.manager_owner()
        if owner_after != expected_manager_owner:
            raise UnitReferenceError("manager owner drifted after UnrefUnit")
        self._recheck_library()
        return {
            "client_unique_name": self.client_unique_name,
            "manager_owner_after": owner_after,
            "manager_owner_before": owner_before,
            "unit_name": unit_name,
        }

    def verify_released(self, *, expected_manager_owner: str) -> dict[str, object]:
        """Replay the same live connection after exact-once ``UnrefUnit``.

        The connection intentionally remains open so the formal supervisor can
        bind post-Unref unit absence, the manager owner, and the original
        client unique name before it closes the final retained reference FD.
        """

        self._ensure_open()
        self._validate_owner(expected_manager_owner)
        if self._acquired_unit is not None or self._reference_state_uncertain:
            raise UnitReferenceError(
                "released connection verification found a held or uncertain reference"
            )
        owner = self.manager_owner()
        if owner != expected_manager_owner:
            raise UnitReferenceError(
                "manager owner drifted after UnrefUnit while the connection was retained"
            )
        self._recheck_library()
        return {
            "client_unique_name": self.client_unique_name,
            "library_identity": dict(self.library_identity),
            "manager_owner": owner,
            "reference_held": False,
        }

    def close(self) -> None:
        """Drop the bus and FD; a held reference is an explicit error."""

        if self._closed:
            return
        if self._acquired_unit is not None:
            raise UnitReferenceError("refusing normal close while a unit reference is held")
        self._library.sd_bus_flush_close_unref(self._bus)
        self._bus = ctypes.c_void_p()
        os.close(self._descriptor)
        self._closed = True

    def abort_close(self) -> bool:
        """Best-effort UnrefUnit, then always close the persistent connection."""

        if self._closed:
            return True
        released = self._acquired_unit is None and self._reference_state_uncertain is False
        if self._acquired_unit is not None:
            unit_name = self._acquired_unit
            try:
                if (
                    self._reference_state_uncertain is False
                    and self._acquired_owner is not None
                    and self.manager_owner() == self._acquired_owner
                ):
                    self._call_empty(
                        destination=SYSTEMD_DESTINATION,
                        path=SYSTEMD_PATH,
                        interface=SYSTEMD_INTERFACE,
                        member=b"UnrefUnit",
                        argument=unit_name,
                    )
                    released = True
            except Exception:
                released = False
            self._acquired_unit = None
            self._acquired_owner = None
        self._reference_state_uncertain = False
        self._library.sd_bus_flush_close_unref(self._bus)
        self._bus = ctypes.c_void_p()
        os.close(self._descriptor)
        self._closed = True
        return released

    def _recheck_library(self) -> None:
        observed, signature = _hash_descriptor(
            self._descriptor,
            absolute=Path(self.library_identity["path"]),
        )
        if observed != self.library_identity or signature != self._signature:
            raise UnitReferenceError("libsystemd drifted while the reference was live")

    def _ensure_open(self) -> None:
        if getattr(self, "_closed", False):
            raise UnitReferenceError("persistent unit reference is closed")

    @staticmethod
    def _validate_unit(unit_name: object) -> None:
        if type(unit_name) is not str or UNIT_RE.fullmatch(unit_name) is None:
            raise UnitReferenceError("unit name is invalid")

    @staticmethod
    def _validate_owner(owner: object) -> None:
        if type(owner) is not str or UNIQUE_NAME_RE.fullmatch(owner) is None:
            raise UnitReferenceError("expected manager owner is invalid")

    def __enter__(self) -> "PersistentUnitReference":
        self._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        del exc_type, traceback
        if exc is None:
            self.close()
        else:
            self.abort_close()
        return False
