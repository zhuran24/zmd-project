#!/usr/bin/env python3
"""Single-use formal-root closure actor for the prospective AB16 budget cohort."""

from __future__ import annotations

from collections.abc import Mapping
import fcntl
import hashlib
import os
from pathlib import Path, PurePosixPath
import secrets
import select
import socket
import stat
from typing import Final, cast

if __package__:
    from . import ab16_budget_authority_v1 as budget
    from . import ab16_budget_broker_v1 as broker
    from . import ab16_resource_admission_v1 as resource_admission
else:
    import ab16_budget_authority_v1 as budget
    import ab16_budget_broker_v1 as broker
    import ab16_resource_admission_v1 as resource_admission


PACKAGE_ROLE: Final = "ab16-closure-actor-v1"
REQUEST_SCHEMA: Final = "noncert-cuts-ab16-closure-request-v1"
RESPONSE_SCHEMA: Final = "noncert-cuts-ab16-closure-response-v1"
ACTOR_SCHEMA: Final = "noncert-cuts-ab16-closure-actor-v1"
LOCK_CONSUMPTION_SCHEMA: Final = "noncert-cuts-ab16-closure-lock-consumption-v1"
RECOVERY_TERMINAL_SCHEMA: Final = "noncert-cuts-ab16-recovery-disarm-terminal-v1"
BUDGET_TERMINAL_SCHEMA: Final = "noncert-cuts-ab16-formal-root-budget-terminal-v2"
FORMAL_MANIFEST_SCHEMA: Final = "noncert-cuts-ab16-formal-manifest-v2"
CLOSURE_RESULT_SCHEMA: Final = "noncert-cuts-ab16-closure-result-v2"
READY_SCHEMA: Final = "noncert-cuts-ab16-closure-actor-ready-v1"
OWNER_HANDOFF_SCHEMA: Final = "noncert-cuts-ab16-closure-owner-handoff-v1"
FINAL_RELEASE_ACTOR_SCHEMA: Final = (
    "noncert-cuts-ab16-final-release-actor-v1"
)

_DIRECTORY_FLAGS: Final = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
_READ_FLAGS: Final = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW


class ClosureProtocolError(RuntimeError):
    """A writer-absence, ordering, publication, or closure invariant failed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _exact_keys(value: Mapping[str, object], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        raise ClosureProtocolError("FRAME_SHAPE_MISMATCH", f"{label} keys differ")


def _nonce(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ClosureProtocolError("INVALID_NONCE", "closure nonce is invalid")
    return value


def _content_identity(
    value: object,
    *,
    label: str,
) -> dict[str, object]:
    if (
        type(value) is not dict
        or set(value) != {"sha256", "size_bytes"}
        or type(value["sha256"]) is not str
        or len(cast(str, value["sha256"])) != 64
        or any(
            character not in "0123456789abcdef"
            for character in cast(str, value["sha256"])
        )
        or type(value["size_bytes"]) is not int
        or cast(int, value["size_bytes"]) <= 0
    ):
        raise ClosureProtocolError(
            "FINAL_RELEASE_BINDING_DRIFT",
            f"{label} identity is invalid",
        )
    return dict(cast(Mapping[str, object], value))


def _final_release_actor(
    value: object,
    *,
    pidfd: int,
) -> dict[str, object]:
    if (
        type(value) is not dict
        or set(value)
        != {"schema_version", "pid", "pid_starttime", "uid"}
        or value["schema_version"] != FINAL_RELEASE_ACTOR_SCHEMA
        or type(value["pid"]) is not int
        or type(value["pid_starttime"]) is not int
        or type(value["uid"]) is not int
        or value["uid"] != os.getuid()
        or broker._pidfd_target_pid(pidfd) != value["pid"]  # noqa: SLF001
        or broker.process_starttime(cast(int, value["pid"]))
        != value["pid_starttime"]
        or broker.pidfd_reports_exit(pidfd)
    ):
        raise ClosureProtocolError(
            "FINAL_RELEASE_ACTOR_IDENTITY_DRIFT",
            "final-release actor, pidfd, or liveness identity differs",
        )
    return dict(cast(Mapping[str, object], value))


def _file_sha256(descriptor: int, size_bytes: int) -> str:
    return budget._sha256_descriptor(descriptor, size_bytes=size_bytes)  # noqa: SLF001


def _path_types(entries: list[dict[str, object]]) -> list[dict[str, str]]:
    result = [
        {
            "path": cast(str, entry["path"]),
            "type": cast(str, entry["type"]),
        }
        for entry in entries
    ]
    result.sort(key=lambda item: (item["path"], item["type"]))
    return result


def _validate_root_inventory(value: object) -> dict[str, object]:
    if type(value) is not dict:
        raise ClosureProtocolError(
            "ROOT_INVENTORY_SHAPE_DRIFT",
            "broker root inventory is not one object",
        )
    record = cast(dict[str, object], value)
    _exact_keys(
        record,
        {
            "expected_path_types",
            "schema_version",
            "staging_inventory_sha256",
        },
        label="broker root inventory",
    )
    raw_entries = record["expected_path_types"]
    digest = record["staging_inventory_sha256"]
    if (
        record["schema_version"] != broker.ROOT_INVENTORY_SCHEMA
        or type(raw_entries) is not list
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ClosureProtocolError(
            "ROOT_INVENTORY_SHAPE_DRIFT",
            "broker root inventory discriminator or digest is invalid",
        )
    checked: list[dict[str, str]] = []
    for index, raw in enumerate(raw_entries):
        if type(raw) is not dict:
            raise ClosureProtocolError(
                "ROOT_INVENTORY_SHAPE_DRIFT",
                f"root inventory entry {index} is not one object",
            )
        _exact_keys(
            raw,
            {"path", "type"},
            label=f"root inventory entry {index}",
        )
        path = raw["path"]
        node_type = raw["type"]
        if (
            not isinstance(path, str)
            or not path
            or path.startswith("/")
            or PurePosixPath(path).as_posix() != path
            or any(part in {"", ".", ".."} for part in PurePosixPath(path).parts)
            or node_type not in {"directory", "regular"}
        ):
            raise ClosureProtocolError(
                "ROOT_INVENTORY_SHAPE_DRIFT",
                f"root inventory entry {index} is not canonical",
            )
        checked.append({"path": path, "type": cast(str, node_type)})
    expected = sorted(checked, key=lambda item: (item["path"], item["type"]))
    if checked != expected or len({item["path"] for item in checked}) != len(checked):
        raise ClosureProtocolError(
            "ROOT_INVENTORY_SHAPE_DRIFT",
            "root inventory is unsorted or has duplicate paths",
        )
    return {
        "schema_version": broker.ROOT_INVENTORY_SCHEMA,
        "expected_path_types": checked,
        "staging_inventory_sha256": digest,
    }


def _transition_expected_path(
    entries: list[dict[str, str]],
    *,
    staging_path: str,
    target_path: str,
) -> list[dict[str, str]]:
    replaced = 0
    result: list[dict[str, str]] = []
    for entry in entries:
        if entry["path"] == staging_path:
            if entry["type"] != "regular":
                raise ClosureProtocolError(
                    "ROOT_INVENTORY_TRANSITION_DRIFT",
                    "closure staging expectation is not a regular file",
                )
            result.append({"path": target_path, "type": "regular"})
            replaced += 1
        else:
            result.append(dict(entry))
    result.sort(key=lambda item: (item["path"], item["type"]))
    if (
        replaced != 1
        or len({item["path"] for item in result}) != len(result)
    ):
        raise ClosureProtocolError(
            "ROOT_INVENTORY_TRANSITION_DRIFT",
            "closure publication does not replace one unique staging path",
        )
    return result


def _validate_control_endpoint_paths(value: object) -> tuple[Path, ...]:
    if type(value) is not list or len(value) != 4:
        raise ClosureProtocolError(
            "CONTROL_ENDPOINT_PATH_DRIFT",
            "closure requires exactly four control endpoint paths",
        )
    paths: list[Path] = []
    for raw in value:
        if not isinstance(raw, str):
            raise ClosureProtocolError(
                "CONTROL_ENDPOINT_PATH_DRIFT",
                "control endpoint path is not a string",
            )
        path = Path(raw)
        if not path.is_absolute() or Path(os.path.abspath(path)) != path:
            raise ClosureProtocolError(
                "CONTROL_ENDPOINT_PATH_DRIFT",
                "control endpoint path is not canonical absolute",
            )
        paths.append(path)
    expected_names = (
        "budget-broker.sock",
        "budget-broker.sock.retired",
        "guardian-control.sock",
        "guardian-control.sock.retired",
    )
    if (
        tuple(path.name for path in paths) != expected_names
        or len({path.parent for path in paths}) != 1
    ):
        raise ClosureProtocolError(
            "CONTROL_ENDPOINT_PATH_DRIFT",
            "control endpoint names or parent differ",
        )
    return tuple(paths)


def _snapshot_root_entries_fd(retained_root_fd: int) -> list[dict[str, object]]:
    root_fd = os.dup(retained_root_fd)
    retained: list[tuple[str, int, tuple[int, ...], tuple[str, ...]]] = []
    entries: list[dict[str, object]] = []
    try:
        retained.append(
            (
                ".",
                root_fd,
                budget._signature(os.fstat(root_fd)),  # noqa: SLF001
                tuple(sorted(os.listdir(root_fd))),
            )
        )
        index = 0
        while index < len(retained):
            relative_directory, directory_fd, _identity, names = retained[index]
            for name in names:
                relative = name if relative_directory == "." else f"{relative_directory}/{name}"
                before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if stat.S_ISLNK(before.st_mode):
                    raise ClosureProtocolError("UNSAFE_ROOT_NODE", f"symlink is forbidden: {relative}")
                if stat.S_ISDIR(before.st_mode):
                    child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=directory_fd)
                    opened = os.fstat(child_fd)
                    if budget._signature(opened) != budget._signature(before):  # noqa: SLF001
                        os.close(child_fd)
                        raise ClosureProtocolError("ROOT_IDENTITY_DRIFT", f"directory changed: {relative}")
                    retained.append(
                        (
                            relative,
                            child_fd,
                            budget._signature(opened),  # noqa: SLF001
                            tuple(sorted(os.listdir(child_fd))),
                        )
                    )
                    entries.append(
                        {
                            "mode_octal": f"{stat.S_IMODE(opened.st_mode):04o}",
                            "path": relative,
                            "type": "directory",
                        }
                    )
                elif stat.S_ISREG(before.st_mode):
                    if before.st_nlink != 1:
                        raise ClosureProtocolError(
                            "UNSAFE_ROOT_NODE",
                            f"regular file has external or duplicate hardlinks: {relative}",
                        )
                    descriptor = os.open(name, _READ_FLAGS, dir_fd=directory_fd)
                    try:
                        opened = os.fstat(descriptor)
                        if budget._signature(opened) != budget._signature(before):  # noqa: SLF001
                            raise ClosureProtocolError("ROOT_IDENTITY_DRIFT", f"file changed: {relative}")
                        digest = _file_sha256(descriptor, opened.st_size)
                        after = os.fstat(descriptor)
                        if budget._signature(after) != budget._signature(opened):  # noqa: SLF001
                            raise ClosureProtocolError("ROOT_IDENTITY_DRIFT", f"file drifted: {relative}")
                        entries.append(
                            {
                                "mode_octal": f"{stat.S_IMODE(opened.st_mode):04o}",
                                "path": relative,
                                "sha256": digest,
                                "size_bytes": opened.st_size,
                                "type": "regular",
                            }
                        )
                    finally:
                        os.close(descriptor)
                else:
                    raise ClosureProtocolError("UNSAFE_ROOT_NODE", f"special node is forbidden: {relative}")
            index += 1
        for relative, descriptor, identity, names in retained:
            if budget._signature(os.fstat(descriptor)) != identity:  # noqa: SLF001
                raise ClosureProtocolError("ROOT_IDENTITY_DRIFT", f"directory drifted: {relative}")
            if tuple(sorted(os.listdir(descriptor))) != names:
                raise ClosureProtocolError("ROOT_MEMBER_DRIFT", f"directory members drifted: {relative}")
        entries.sort(key=lambda item: (str(item["path"]), str(item["type"])))
        return entries
    finally:
        for _relative, descriptor, _identity, _names in reversed(retained):
            try:
                os.close(descriptor)
            except OSError:
                pass


def snapshot_root_entries(root: Path | str) -> list[dict[str, object]]:
    """Descriptor-walk one root and reject every symlink or special node."""

    absolute = Path(os.path.abspath(root))
    root_fd = budget._open_absolute_directory_no_symlinks(absolute)  # noqa: SLF001
    try:
        return _snapshot_root_entries_fd(root_fd)
    finally:
        os.close(root_fd)


def writable_root_descriptors(
    root: Path | str,
    *,
    excluded_pids: frozenset[int] = frozenset(),
) -> list[dict[str, object]]:
    """Enumerate same-UID processes retaining writable FDs below the root."""

    absolute = os.path.abspath(root)
    prefix = absolute + os.sep
    result: list[dict[str, object]] = []
    try:
        process_names = os.listdir("/proc")
    except OSError as exc:
        raise ClosureProtocolError("WRITER_SCAN_FAILED", "cannot enumerate /proc") from exc
    for name in process_names:
        if not name.isdecimal():
            continue
        pid = int(name)
        if pid in excluded_pids:
            continue
        try:
            if os.stat(f"/proc/{pid}").st_uid != os.getuid():
                continue
            descriptor_names = os.listdir(f"/proc/{pid}/fd")
        except FileNotFoundError:
            continue
        except PermissionError as exc:
            raise ClosureProtocolError(
                "WRITER_SCAN_FAILED",
                f"cannot inspect same-UID PID {pid}",
            ) from exc
        except OSError as exc:
            raise ClosureProtocolError("WRITER_SCAN_FAILED", f"cannot inspect same-UID PID {pid}") from exc
        for descriptor_name in descriptor_names:
            if not descriptor_name.isdecimal():
                continue
            fd_path = f"/proc/{pid}/fd/{descriptor_name}"
            try:
                target = os.readlink(fd_path)
                flags_line = next(
                    line
                    for line in Path(f"/proc/{pid}/fdinfo/{descriptor_name}")
                    .read_text(encoding="ascii")
                    .splitlines()
                    if line.startswith("flags:")
                )
                flags = int(flags_line.split()[1], 8)
            except (FileNotFoundError, ProcessLookupError):
                continue
            except PermissionError as exc:
                raise ClosureProtocolError(
                    "WRITER_SCAN_FAILED",
                    f"cannot inspect same-UID PID {pid} FD {descriptor_name}",
                ) from exc
            except (OSError, StopIteration, ValueError) as exc:
                raise ClosureProtocolError(
                    "WRITER_SCAN_FAILED",
                    f"cannot inspect same-UID PID {pid} FD {descriptor_name}",
                ) from exc
            if flags & os.O_ACCMODE not in {os.O_WRONLY, os.O_RDWR}:
                continue
            normalized = target.removesuffix(" (deleted)")
            if normalized == absolute or normalized.startswith(prefix):
                result.append(
                    {
                        "descriptor": int(descriptor_name),
                        "flags_octal": f"{flags:o}",
                        "pid": pid,
                        "pid_starttime": broker.process_starttime(pid),
                        "target": target,
                    }
                )
    result.sort(
        key=lambda item: (
            cast(int, item["pid"]),
            cast(int, item["descriptor"]),
        )
    )
    return result


def _prove_self_descriptor_allowlist(
    expected: set[int],
) -> list[int]:
    """Prove the closure actor retains only its package-issued capabilities."""

    try:
        names = os.listdir("/proc/self/fd")
    except OSError as exc:
        raise ClosureProtocolError(
            "FD_ENUMERATION_FAILED",
            "cannot enumerate closure actor descriptors",
        ) from exc
    observed: set[int] = set()
    for name in names:
        if not name.isdecimal():
            continue
        descriptor = int(name)
        try:
            os.fstat(descriptor)
        except OSError:
            continue
        observed.add(descriptor)
    expected_with_stdio = {0, 1, 2, *expected}
    if observed != expected_with_stdio:
        raise ClosureProtocolError(
            "FD_ALLOWLIST_DRIFT",
            "closure actor retained descriptor set differs: "
            f"observed={sorted(observed)}, expected={sorted(expected_with_stdio)}",
        )
    return sorted(observed)


def _prove_takeover_lock_released(root: Path, lock_extent: Mapping[str, object]) -> None:
    extent = broker.validate_prepared_extent(lock_extent)
    path = root / str(extent["parent_path"]) / str(extent["staging_name"])
    try:
        descriptor = os.open(path, _READ_FLAGS)
    except OSError as exc:
        raise ClosureProtocolError("TAKEOVER_LOCK_MISSING", "recovery takeover lock is absent") from exc
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ClosureProtocolError("TAKEOVER_LOCK_HELD", "recovery takeover lock is still held") from exc
        fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


class ClosureServer:
    """Publish the only three post-disarm root members, then prove exact closure."""

    def __init__(
        self,
        connection: socket.socket,
        *,
        root: Path,
        nonce: str,
        expected_peer: Mapping[str, int],
        broker_actor: Mapping[str, object],
        broker_pidfd: int,
        recovery_actor: Mapping[str, object],
        recovery_pidfd: int,
        recovery_lock_extent: object,
        final_release_actor: Mapping[str, object] | None,
        final_release_pidfd: int | None,
        final_release_pidfd_method: str | None,
        final_release_handoff_identity: Mapping[str, object] | None,
        closure_parent_fd: int,
        closure_lock_extent: object,
        closure_lock_fd: int,
        extents: list[object],
        extent_fds: list[int],
        require_control_endpoint_absence: bool,
        control_endpoint_paths: tuple[Path, ...],
    ) -> None:
        if len(extents) != 3 or len(extent_fds) != 3:
            raise ClosureProtocolError("FD_COUNT_MISMATCH", "closure requires exactly three terminal extents")
        self.connection = connection
        self.root = Path(os.path.abspath(root))
        self.root_fd: int | None = budget._open_absolute_directory_no_symlinks(self.root)  # noqa: SLF001
        self.root_identity = budget._path_identity(os.fstat(self.root_fd))  # noqa: SLF001
        self.nonce = _nonce(nonce)
        self.expected_peer = dict(expected_peer)
        self.broker_actor = dict(broker_actor)
        self.broker_pidfd: int | None = broker_pidfd
        self.recovery_actor = dict(recovery_actor)
        self.recovery_pidfd: int | None = recovery_pidfd
        self.recovery_lock_extent = broker.validate_prepared_extent(recovery_lock_extent)
        if (
            final_release_actor is None
            or final_release_pidfd is None
            or final_release_pidfd_method is None
            or final_release_handoff_identity is None
        ):
            if require_control_endpoint_absence or any(
                value is not None
                for value in (
                    final_release_actor,
                    final_release_pidfd,
                    final_release_pidfd_method,
                    final_release_handoff_identity,
                )
            ):
                raise ClosureProtocolError(
                    "FINAL_RELEASE_BINDING_MISSING",
                    "formal closure lacks one complete final-release binding",
                )
            self.final_release_actor: dict[str, object] | None = None
            self.final_release_pidfd: int | None = None
            self.final_release_pidfd_method: str | None = None
            self.final_release_handoff_identity: (
                dict[str, object] | None
            ) = None
        else:
            self.final_release_actor = _final_release_actor(
                final_release_actor,
                pidfd=final_release_pidfd,
            )
            self.final_release_pidfd = final_release_pidfd
            if not final_release_pidfd_method:
                raise ClosureProtocolError(
                    "FINAL_RELEASE_BINDING_DRIFT",
                    "final-release pidfd method is absent",
                )
            self.final_release_pidfd_method = final_release_pidfd_method
            self.final_release_handoff_identity = _content_identity(
                final_release_handoff_identity,
                label="final-release handoff",
            )
        self.closure_parent_fd: int | None = closure_parent_fd
        self.closure_lock_extent = broker.validate_prepared_extent(closure_lock_extent)
        self.closure_lock_fd: int | None = closure_lock_fd
        self.extents = [broker.validate_prepared_extent(value) for value in extents]
        self.extent_fds: list[int | None] = list(extent_fds)
        self.require_control_endpoint_absence = require_control_endpoint_absence
        self.control_endpoint_paths = control_endpoint_paths
        self.actor = {"schema_version": ACTOR_SCHEMA, **broker.process_identity()}
        expected_targets = [
            "recovery-disarm-terminal.json",
            "budget-terminal.json",
            "formal-manifest.json",
        ]
        if [extent["target_name"] for extent in self.extents] != expected_targets:
            raise ClosureProtocolError("EXTENT_ORDER_DRIFT", "closure extent target order drifted")

    def _require_peer(self, observed: Mapping[str, int]) -> None:
        for key in ("pid", "pid_starttime", "uid"):
            if observed[key] != self.expected_peer[key]:
                raise ClosureProtocolError("PEER_IDENTITY_DRIFT", "closure peer identity drifted")

    def _allowed_runtime_actors(self) -> list[dict[str, int]]:
        runtime = [
            {
                "pid": cast(int, self.actor["pid"]),
                "starttime": cast(int, self.actor["pid_starttime"]),
            }
        ]
        if self.final_release_actor is None:
            return runtime
        if self.final_release_pidfd is None:
            raise ClosureProtocolError(
                "FINAL_RELEASE_BINDING_MISSING",
                "final-release pidfd was released before closure completed",
            )
        actor = _final_release_actor(
            self.final_release_actor,
            pidfd=self.final_release_pidfd,
        )
        runtime.append(
            {
                "pid": cast(int, actor["pid"]),
                "starttime": cast(int, actor["pid_starttime"]),
            }
        )
        return runtime

    def _final_release_binding(self, *, phase: str) -> dict[str, object]:
        """Rejoin the retained pidfd to the complete broker-pinned handoff."""

        if self.final_release_actor is None:
            return {
                "phase": phase,
                "state": "NOT_APPLICABLE_ZERO_AUTHORITY_HARNESS",
            }
        if (
            self.final_release_pidfd is None
            or self.final_release_pidfd_method is None
            or self.final_release_handoff_identity is None
        ):
            raise ClosureProtocolError(
                "FINAL_RELEASE_BINDING_MISSING",
                "final-release closure binding was released early",
            )
        actor = _final_release_actor(
            self.final_release_actor,
            pidfd=self.final_release_pidfd,
        )
        return {
            "actor": actor,
            "handoff_identity": dict(
                self.final_release_handoff_identity
            ),
            "phase": phase,
            "pidfd_method": self.final_release_pidfd_method,
            "state": "LIVE_EXACT_FINAL_RELEASE_ACTOR_BOUND",
        }

    def _require_root_join(self) -> None:
        assert self.root_fd is not None
        if budget._path_identity(os.fstat(self.root_fd)) != self.root_identity:  # noqa: SLF001
            raise ClosureProtocolError("ROOT_IDENTITY_DRIFT", "retained root identity drifted")
        joined = budget._open_absolute_directory_no_symlinks(self.root)  # noqa: SLF001
        try:
            if budget._path_identity(os.fstat(joined)) != self.root_identity:  # noqa: SLF001
                raise ClosureProtocolError("ROOT_PATH_DRIFT", "absolute root path identity drifted")
        finally:
            os.close(joined)

    def _publish(self, index: int, record: Mapping[str, object]) -> dict[str, object]:
        assert self.closure_parent_fd is not None
        descriptor = self.extent_fds[index]
        assert descriptor is not None
        identity = broker.publish_preallocated_extent(
            self.extents[index],
            parent_fd=self.closure_parent_fd,
            staging_fd=descriptor,
            raw=broker.canonical_json_bytes(dict(record)),
        )
        self.extent_fds[index] = None
        os.close(descriptor)
        return identity

    def _require_exact_path_types(
        self,
        expected: list[dict[str, str]],
        *,
        phase: str,
    ) -> list[dict[str, object]]:
        assert self.root_fd is not None
        observed = _snapshot_root_entries_fd(self.root_fd)
        if _path_types(observed) != expected:
            raise ClosureProtocolError(
                "ROOT_INVENTORY_MISMATCH",
                f"formal root path/type set differs at {phase}",
            )
        return observed

    def _prove_control_endpoints_absent(self) -> dict[str, object]:
        if len(self.control_endpoint_paths) != 4:
            raise ClosureProtocolError(
                "CONTROL_ENDPOINT_PATH_DRIFT",
                "closure control endpoint path set is absent",
            )
        control = self.control_endpoint_paths[0].parent
        descriptor = budget._open_absolute_directory_no_symlinks(control)  # noqa: SLF001
        try:
            for path in self.control_endpoint_paths:
                try:
                    os.stat(
                        path.name,
                        dir_fd=descriptor,
                        follow_symlinks=False,
                    )
                except FileNotFoundError:
                    continue
                raise ClosureProtocolError(
                    "CONTROL_ENDPOINT_STILL_PRESENT",
                    f"ephemeral control endpoint remains: {path.name}",
                )
            return {
                "control_directory": str(control),
                "paths": [
                    str(path)
                    for path in self.control_endpoint_paths
                ],
                "state": "ALL_FOUR_ENDPOINTS_ABSENT",
            }
        finally:
            os.close(descriptor)

    def _consume_closure_slot(self) -> dict[str, object]:
        assert self.closure_lock_fd is not None
        return broker.consume_once_extent(
            self.closure_lock_extent,
            descriptor=self.closure_lock_fd,
            record={
                "schema_version": LOCK_CONSUMPTION_SCHEMA,
                "actor": dict(self.actor),
                "broker_actor": dict(self.broker_actor),
                "nonce": self.nonce,
                "recovery_actor": dict(self.recovery_actor),
                "state": "CLOSURE_ACTOR_CONSUMED",
            },
        )

    def _release_owned(self) -> None:
        errors: list[BaseException] = []
        for index, descriptor in enumerate(self.extent_fds):
            if descriptor is None:
                continue
            self.extent_fds[index] = None
            try:
                os.close(descriptor)
            except BaseException as exc:
                errors.append(exc)
        for attribute in ("closure_parent_fd", "broker_pidfd", "recovery_pidfd"):
            descriptor = getattr(self, attribute)
            if descriptor is None:
                continue
            setattr(self, attribute, None)
            try:
                os.close(descriptor)
            except BaseException as exc:
                errors.append(exc)
        if self.closure_lock_fd is not None:
            descriptor = self.closure_lock_fd
            self.closure_lock_fd = None
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            except BaseException as exc:
                errors.append(exc)
            try:
                os.close(descriptor)
            except BaseException as exc:
                errors.append(exc)
        if errors:
            primary = ClosureProtocolError(
                "OWNERSHIP_RELEASE_UNCERTAIN",
                "closure FD or once-lock release failed",
            )
            for error in errors:
                primary.add_note(f"{type(error).__name__}: {error}")
            raise primary

    def _release_root_anchor(self) -> None:
        if self.root_fd is None:
            return
        descriptor = self.root_fd
        self.root_fd = None
        os.close(descriptor)

    def _release_final_release_pidfd(self) -> None:
        if self.final_release_pidfd is None:
            return
        descriptor = self.final_release_pidfd
        self.final_release_pidfd = None
        try:
            os.close(descriptor)
        except BaseException as exc:
            raise ClosureProtocolError(
                "OWNERSHIP_RELEASE_UNCERTAIN",
                "final-release pidfd close failed",
            ) from exc

    def _close(self, payload: Mapping[str, object]) -> dict[str, object]:
        _exact_keys(
            payload,
            {
                "budget_contract",
                "disarm_observation",
                "root_inventory",
                "same_uid_process_baseline",
                "same_uid_process_baseline_sha256",
                "terminal_join_sha256",
            },
            label="closure payload",
        )
        if type(payload["budget_contract"]) is not dict or type(payload["disarm_observation"]) is not dict:
            raise ClosureProtocolError("FRAME_SHAPE_MISMATCH", "closure records are invalid")
        terminal_join = payload["terminal_join_sha256"]
        root_inventory = _validate_root_inventory(payload["root_inventory"])
        expected_path_types = cast(
            list[dict[str, str]],
            root_inventory["expected_path_types"],
        )
        if (
            not isinstance(terminal_join, str)
            or len(terminal_join) != 64
            or any(character not in "0123456789abcdef" for character in terminal_join)
        ):
            raise ClosureProtocolError("FRAME_SHAPE_MISMATCH", "terminal join digest is invalid")
        assert self.broker_pidfd is not None and self.recovery_pidfd is not None
        if not broker.pidfd_reports_exit(self.recovery_pidfd):
            raise ClosureProtocolError("RECOVERY_STILL_LIVE", "recovery actor exit is not proved")
        if not broker.pidfd_reports_exit(self.broker_pidfd):
            raise ClosureProtocolError("BROKER_STILL_LIVE", "broker exit is not proved")
        self._require_root_join()
        _prove_takeover_lock_released(
            self.root,
            self.recovery_lock_extent,
        )
        lock_identity = self._consume_closure_slot()
        initial_expected_descriptors = {
            self.connection.fileno(),
            self.root_fd,
            self.broker_pidfd,
            self.recovery_pidfd,
            self.closure_parent_fd,
            self.closure_lock_fd,
            *self.extent_fds,
        }
        if self.final_release_pidfd is not None:
            initial_expected_descriptors.add(
                self.final_release_pidfd
            )
        if None in initial_expected_descriptors:
            raise ClosureProtocolError(
                "FD_ALLOWLIST_DRIFT",
                "closure actor lacks one package-issued descriptor",
            )
        initial_descriptor_allowlist = _prove_self_descriptor_allowlist(
            cast(set[int], initial_expected_descriptors)
        )
        baseline = resource_admission.validate_same_uid_process_baseline(
            payload["same_uid_process_baseline"],
            expected_sha256=payload["same_uid_process_baseline_sha256"],
            require_live=True,
        )
        allowed_runtime_actors = self._allowed_runtime_actors()
        initial_process_scope = (
            resource_admission.observe_same_uid_process_scope(
                baseline,
                expected_sha256=payload[
                    "same_uid_process_baseline_sha256"
                ],
                allowed_runtime_actors=allowed_runtime_actors,
            )
        )
        initial_final_release_binding = self._final_release_binding(
            phase="INITIAL_CLOSURE_SCOPE"
        )
        foreign_writers_before_closure = writable_root_descriptors(
            self.root,
            excluded_pids=frozenset(
                {cast(int, self.actor["pid"])}
            ),
        )
        if foreign_writers_before_closure:
            raise ClosureProtocolError(
                "FOREIGN_ROOT_WRITER_RETAINED",
                "a same-UID process retained a writable formal-root descriptor",
            )
        writer_capability_closure = {
            "broker_exit_proved": True,
            "closure_actor_descriptors": initial_descriptor_allowlist,
            "foreign_writable_root_descriptor_scan": {
                "excluded_actor": dict(self.actor),
                "observed": foreign_writers_before_closure,
                "state": "NO_FOREIGN_WRITABLE_ROOT_DESCRIPTORS",
            },
            "final_release_binding": initial_final_release_binding,
            "recovery_exit_proved": True,
            "same_uid_process_scope": initial_process_scope,
            "state": "PACKAGE_WRITERS_EXITED_CLOSURE_FIXED_FDS_ONLY",
        }
        self._require_exact_path_types(
            expected_path_types,
            phase="broker-exit-linearization",
        )

        disarm_terminal = {
            "schema_version": RECOVERY_TERMINAL_SCHEMA,
            "broker_actor": dict(self.broker_actor),
            "closure_actor": dict(self.actor),
            "recovery_actor": dict(self.recovery_actor),
            "recovery_observation": dict(payload["disarm_observation"]),
            "state": "RECOVERY_ABSENT_AND_TAKEOVER_LOCK_RELEASED",
            "terminal_join_sha256": terminal_join,
        }
        disarm_identity = self._publish(0, disarm_terminal)
        expected_path_types = _transition_expected_path(
            expected_path_types,
            staging_path=(
                f"{self.extents[0]['parent_path']}/"
                f"{self.extents[0]['staging_name']}"
            ),
            target_path=(
                f"{self.extents[0]['parent_path']}/"
                f"{self.extents[0]['target_name']}"
            ),
        )
        budget_terminal = {
            "schema_version": BUDGET_TERMINAL_SCHEMA,
            "broker_actor": dict(self.broker_actor),
            "budget_contract": dict(payload["budget_contract"]),
            "closure_actor": dict(self.actor),
            "same_uid_process_baseline": baseline,
            "same_uid_process_baseline_sha256": payload[
                "same_uid_process_baseline_sha256"
            ],
            "state": "BUDGET_TERMINAL_AFTER_RECOVERY_DISARM",
            "terminal_join_sha256": terminal_join,
            "writer_capability_closure": writer_capability_closure,
        }
        budget_identity = self._publish(1, budget_terminal)
        expected_path_types = _transition_expected_path(
            expected_path_types,
            staging_path=(
                f"{self.extents[1]['parent_path']}/"
                f"{self.extents[1]['staging_name']}"
            ),
            target_path=(
                f"{self.extents[1]['parent_path']}/"
                f"{self.extents[1]['target_name']}"
            ),
        )

        assert self.root_fd is not None
        before_manifest = self._require_exact_path_types(
            expected_path_types,
            phase="before-manifest",
        )
        manifest_stage = (
            f"{self.extents[2]['parent_path']}/{self.extents[2]['staging_name']}"
        )
        manifest_entries = [entry for entry in before_manifest if entry["path"] != manifest_stage]
        if len(manifest_entries) != len(before_manifest) - 1:
            raise ClosureProtocolError("MANIFEST_STAGE_MISSING", "formal manifest staging member is absent")
        entries_sha256 = hashlib.sha256(broker.canonical_json_bytes(manifest_entries)).hexdigest()
        manifest = {
            "schema_version": FORMAL_MANIFEST_SCHEMA,
            "authority": {
                "changes_certified_exact": False,
                "changes_cut_state": False,
                "changes_lower_bound": False,
                "changes_production": False,
                "changes_upper_bound": False,
                "research_only": True,
            },
            "budget_terminal_identity": budget_identity,
            "closure_actor": dict(self.actor),
            "entries": manifest_entries,
            "entries_sha256": entries_sha256,
            "excluded_terminal_path": "formal-closure/formal-manifest.json",
            "lock_consumption_identity": lock_identity,
            "recovery_terminal_identity": disarm_identity,
            "same_uid_process_baseline_sha256": payload[
                "same_uid_process_baseline_sha256"
            ],
            "terminal_join_sha256": terminal_join,
            "writer_capability_closure": writer_capability_closure,
        }
        manifest_identity = self._publish(2, manifest)
        expected_path_types = _transition_expected_path(
            expected_path_types,
            staging_path=manifest_stage,
            target_path="formal-closure/formal-manifest.json",
        )
        self._release_owned()

        self._require_root_join()
        final_entries = self._require_exact_path_types(
            expected_path_types,
            phase="after-manifest",
        )
        final_without_manifest = [
            entry
            for entry in final_entries
            if entry["path"] != "formal-closure/formal-manifest.json"
        ]
        if final_without_manifest != manifest_entries:
            raise ClosureProtocolError("FINAL_ROOT_CLOSURE_DRIFT", "final root differs from its manifest")
        final_expected_descriptors = {
            self.connection.fileno(),
            cast(int, self.root_fd),
        }
        if self.final_release_pidfd is not None:
            final_expected_descriptors.add(
                self.final_release_pidfd
            )
        final_descriptor_allowlist = _prove_self_descriptor_allowlist(
            final_expected_descriptors
        )
        allowed_runtime_actors = self._allowed_runtime_actors()
        final_process_scope = (
            resource_admission.observe_same_uid_process_scope(
                baseline,
                expected_sha256=payload[
                    "same_uid_process_baseline_sha256"
                ],
                allowed_runtime_actors=allowed_runtime_actors,
            )
        )
        final_release_binding = self._final_release_binding(
            phase="FINAL_CLOSURE_SCOPE"
        )
        final_writers = writable_root_descriptors(self.root)
        if final_writers:
            raise ClosureProtocolError(
                "ROOT_WRITER_RETAINED_AFTER_RELEASE",
                "a writable formal-root descriptor remains after closure release",
            )
        final_writer_scan = {
            "excluded_pids": [],
            "observed": final_writers,
            "state": "NO_WRITABLE_ROOT_DESCRIPTORS",
        }
        control_absence = (
            self._prove_control_endpoints_absent()
            if self.require_control_endpoint_absence
            else {
                "state": "NOT_APPLICABLE_ZERO_AUTHORITY_HARNESS",
            }
        )
        self._release_final_release_pidfd()
        self._release_root_anchor()
        return {
            "schema_version": CLOSURE_RESULT_SCHEMA,
            "budget_terminal_identity": budget_identity,
            "formal_manifest_identity": manifest_identity,
            "final_writable_root_descriptor_scan": final_writer_scan,
            "recovery_terminal_identity": disarm_identity,
            "control_endpoint_absence": control_absence,
            "final_closure_actor_descriptors": final_descriptor_allowlist,
            "final_release_binding": final_release_binding,
            "final_same_uid_process_scope": final_process_scope,
            "state": "ROOT_CLOSED_NO_WRITERS",
        }

    def run(self) -> int:
        broker.send_frame(
            self.connection,
            {
                "schema_version": RESPONSE_SCHEMA,
                "action": "READY",
                "actor": dict(self.actor),
                "nonce": self.nonce,
                "result": {"state": "READY"},
                "sequence": 0,
                "status": "PASS",
            },
        )
        try:
            frame = broker.receive_frame(
                self.connection,
                require_message_credentials=True,
            )
            self._require_peer(frame.peer)
            record = frame.record
            _exact_keys(
                record,
                {"action", "nonce", "payload", "schema_version", "sequence"},
                label="closure request",
            )
            if (
                record["schema_version"] != REQUEST_SCHEMA
                or record["action"] != "CLOSE"
                or _nonce(record["nonce"]) != self.nonce
                or record["sequence"] != 1
                or type(record["payload"]) is not dict
            ):
                raise ClosureProtocolError("REQUEST_IDENTITY_DRIFT", "closure request identity drifted")
            result = self._close(dict(record["payload"]))
            broker.send_frame(
                self.connection,
                {
                    "schema_version": RESPONSE_SCHEMA,
                    "action": "CLOSE",
                    "actor": dict(self.actor),
                    "nonce": self.nonce,
                    "result": result,
                    "sequence": 1,
                    "status": "PASS",
                },
            )
            acknowledgement = broker.receive_frame(
                self.connection,
                require_message_credentials=True,
            )
            self._require_peer(acknowledgement.peer)
            expected_acknowledgement = {
                "schema_version": REQUEST_SCHEMA,
                "action": "CLOSE_ACK",
                "nonce": self.nonce,
                "payload": {
                    "result_sha256": hashlib.sha256(
                        broker.canonical_json_bytes(result)
                    ).hexdigest(),
                },
                "sequence": 2,
            }
            if acknowledgement.record != expected_acknowledgement:
                raise ClosureProtocolError(
                    "CLOSE_ACK_IDENTITY_DRIFT",
                    "closure terminal acknowledgement differs",
                )
            return 0
        except BaseException as exc:
            try:
                broker.send_frame(
                    self.connection,
                    {
                        "schema_version": RESPONSE_SCHEMA,
                        "action": "FAIL_CLOSED",
                        "actor": dict(self.actor),
                        "code": getattr(exc, "code", type(exc).__name__),
                        "nonce": self.nonce,
                        "result": {"message": str(exc)},
                        "sequence": 1,
                        "status": "FAIL_CLOSED",
                    },
                )
            except BaseException:
                pass
            return 2
        finally:
            try:
                self._release_owned()
            except BaseException:
                pass
            try:
                self._release_final_release_pidfd()
            except BaseException:
                pass
            try:
                self._release_root_anchor()
            except BaseException:
                pass


class ClosureProcess:
    def __init__(
        self,
        *,
        pid: int,
        pidfd: int,
        pidfd_method: str,
        connection: socket.socket,
        nonce: str,
        actor: Mapping[str, object],
    ) -> None:
        self.pid = pid
        self.pidfd = pidfd
        self.pidfd_method = pidfd_method
        self.connection = connection
        self.nonce = nonce
        self.actor = dict(actor)
        self._waited = False
        self._close_attempted = False

    def close_root(self, payload: Mapping[str, object]) -> dict[str, object]:
        broker.send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "CLOSE",
                "nonce": self.nonce,
                "payload": dict(payload),
                "sequence": 1,
            },
        )
        response = broker.receive_frame(
            self.connection,
            require_message_credentials=True,
        )
        record = response.record
        result_value = record.get("result")
        if type(result_value) is not dict:
            raise ClosureProtocolError("RESPONSE_IDENTITY_DRIFT", "closure result is not one object")
        if record.get("status") != "PASS":
            raise ClosureProtocolError(
                str(record.get("code", "FAIL_CLOSED")),
                str(result_value.get("message", "closure failed")),
            )
        if (
            record.get("schema_version") != RESPONSE_SCHEMA
            or record.get("action") != "CLOSE"
            or record.get("nonce") != self.nonce
            or record.get("sequence") != 1
            or record.get("actor") != self.actor
            or {
                key: response.peer[key]
                for key in ("pid", "pid_starttime", "uid")
            }
            != {
                key: self.actor[key]
                for key in ("pid", "pid_starttime", "uid")
            }
        ):
            raise ClosureProtocolError("RESPONSE_IDENTITY_DRIFT", "closure response identity drifted")
        broker.send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "CLOSE_ACK",
                "nonce": self.nonce,
                "payload": {
                    "result_sha256": hashlib.sha256(
                        broker.canonical_json_bytes(result_value)
                    ).hexdigest(),
                },
                "sequence": 2,
            },
        )
        return dict(result_value)

    def wait(self) -> int:
        if self._waited:
            raise ClosureProtocolError("PROCESS_ALREADY_WAITED", "closure cannot be waited twice")
        _pid, status = os.waitpid(self.pid, 0)
        self._waited = True
        if os.WIFEXITED(status):
            return os.WEXITSTATUS(status)
        return 128 + os.WTERMSIG(status)

    def close(self) -> None:
        if self._close_attempted:
            return
        self._close_attempted = True
        errors: list[BaseException] = []
        try:
            self.connection.close()
        except BaseException as exc:
            errors.append(exc)
        descriptor = self.pidfd
        self.pidfd = -1
        try:
            os.close(descriptor)
        except BaseException as exc:
            errors.append(exc)
        if errors:
            primary = ClosureProtocolError(
                "OWNERSHIP_RELEASE_UNCERTAIN",
                "closure control or pidfd close failed",
            )
            for error in errors:
                primary.add_note(
                    f"{type(error).__name__}: {error}"
                )
            raise primary


class DetachedClosureProcess(ClosureProcess):
    """Supervisor-side handle after the broker transfers sole control."""

    def __init__(
        self,
        *,
        pidfd: int,
        connection: socket.socket,
        nonce: str,
        actor: Mapping[str, object],
        pidfd_method: str,
        source_identity: Mapping[str, object],
    ) -> None:
        actor_pid = actor.get("pid")
        if isinstance(actor_pid, bool) or not isinstance(actor_pid, int):
            raise ClosureProtocolError(
                "ACTOR_IDENTITY_DRIFT",
                "detached closure actor PID is invalid",
            )
        super().__init__(
            pid=actor_pid,
            pidfd=pidfd,
            pidfd_method=pidfd_method,
            connection=connection,
            nonce=nonce,
            actor=actor,
        )
        self.source_identity = dict(source_identity)
        self._exit_proved = False

    def wait(self) -> int:
        raise ClosureProtocolError(
            "DETACHED_PROCESS_NOT_CHILD",
            "detached closure exit must be proved through its pidfd",
        )

    def prove_exit(self, *, timeout_milliseconds: int = 5000) -> None:
        if self._exit_proved:
            raise ClosureProtocolError(
                "PROCESS_ALREADY_WAITED",
                "detached closure exit cannot be proved twice",
            )
        poller = select.poll()
        poller.register(self.pidfd, select.POLLIN | select.POLLHUP)
        if not poller.poll(timeout_milliseconds):
            raise ClosureProtocolError(
                "CLOSURE_EXIT_NOT_PROVED",
                "detached closure pidfd did not report terminal exit",
            )
        self._exit_proved = True


def attach_broker_forked_closure(
    handoff: Mapping[str, object],
    descriptors: tuple[int, ...],
) -> DetachedClosureProcess:
    """Accept the broker's sole closure control/pidfd transfer."""

    expected = {
        "actor",
        "broker_actor",
        "control_descriptor_identity",
        "final_release_actor",
        "final_release_handoff_identity",
        "final_release_pidfd_method",
        "nonce",
        "pidfd_method",
        "prepared_closure_identity",
        "recovery_actor",
        "role",
        "role_source_identity",
        "schema_version",
    }
    if set(handoff) != expected or len(descriptors) != 2:
        for descriptor in descriptors:
            os.close(descriptor)
        raise ClosureProtocolError(
            "BROKER_HANDOFF_SHAPE_DRIFT",
            "broker closure handoff shape or FD count differs",
        )
    control_fd, pidfd = descriptors
    connection: socket.socket | None = None
    try:
        actor = handoff["actor"]
        source_identity = handoff["role_source_identity"]
        prepared_identity = handoff["prepared_closure_identity"]
        control_identity = handoff["control_descriptor_identity"]
        final_actor = handoff["final_release_actor"]
        final_handoff_identity = handoff[
            "final_release_handoff_identity"
        ]
        if (
            handoff["schema_version"] != OWNER_HANDOFF_SCHEMA
            or handoff["role"] != PACKAGE_ROLE
            or type(actor) is not dict
            or set(actor)
            != {"schema_version", "pid", "pid_starttime", "uid"}
            or actor["schema_version"] != ACTOR_SCHEMA
            or actor["uid"] != os.getuid()
            or actor["pid_starttime"]
            != broker.process_starttime(int(actor["pid"]))
            or broker._pidfd_target_pid(pidfd)  # noqa: SLF001
            != actor["pid"]
            or broker.pidfd_reports_exit(pidfd)
            or type(handoff["broker_actor"]) is not dict
            or type(handoff["recovery_actor"]) is not dict
            or type(final_actor) is not dict
            or set(final_actor)
            != {"schema_version", "pid", "pid_starttime", "uid"}
            or final_actor["schema_version"]
            != FINAL_RELEASE_ACTOR_SCHEMA
            or final_actor["uid"] != os.getuid()
            or final_actor["pid_starttime"]
            != broker.process_starttime(
                cast(int, final_actor["pid"])
            )
            or type(handoff["final_release_pidfd_method"]) is not str
            or not handoff["final_release_pidfd_method"]
            or type(source_identity) is not dict
            or set(source_identity) != {"sha256", "size_bytes"}
            or type(prepared_identity) is not dict
            or set(prepared_identity) != {"sha256", "size_bytes"}
            or type(control_identity) is not dict
            or control_identity != broker._identity(control_fd)  # noqa: SLF001
            or _content_identity(
                final_handoff_identity,
                label="final-release handoff",
            )
            != final_handoff_identity
            or not isinstance(handoff["pidfd_method"], str)
        ):
            raise ClosureProtocolError(
                "BROKER_HANDOFF_IDENTITY_DRIFT",
                "broker closure handoff identity differs",
            )
        connection = socket.socket(fileno=control_fd)
        broker._socket_type(connection)  # noqa: SLF001
        return DetachedClosureProcess(
            pidfd=pidfd,
            connection=connection,
            nonce=_nonce(handoff["nonce"]),
            actor=actor,
            pidfd_method=handoff["pidfd_method"],
            source_identity=source_identity,
        )
    except BaseException:
        if connection is None:
            os.close(control_fd)
        else:
            connection.close()
        os.close(pidfd)
        raise


def _spawn_closure(
    *,
    root: Path | str,
    broker_actor: Mapping[str, object],
    broker_pidfd: int,
    recovery_actor: Mapping[str, object],
    recovery_pidfd: int,
    recovery_lock_extent: object,
    final_release_actor: Mapping[str, object] | None,
    final_release_pidfd: int | None,
    final_release_pidfd_method: str | None,
    final_release_handoff_identity: Mapping[str, object] | None,
    prepared_result: Mapping[str, object],
    descriptors: tuple[int, ...],
    require_control_endpoint_absence: bool,
    expected_peer: Mapping[str, int] | None = None,
    nonce: str | None = None,
) -> ClosureProcess:
    """Transfer the last root-writable FDs into one closure process."""

    if len(descriptors) != 5:
        raise ClosureProtocolError("FD_COUNT_MISMATCH", "closure requires parent, lock, and three extent FDs")
    lock_extent = prepared_result.get("lock_extent")
    extent_values = prepared_result.get("extents")
    raw_control_paths = prepared_result.get("control_endpoint_paths")
    if type(lock_extent) is not dict or type(extent_values) is not list:
        raise ClosureProtocolError("FRAME_SHAPE_MISMATCH", "prepared closure result is invalid")
    control_endpoint_paths = (
        _validate_control_endpoint_paths(raw_control_paths)
        if require_control_endpoint_absence
        else ()
    )
    closure_parent_fd, closure_lock_fd, *extent_fds = descriptors
    selected_peer = (
        broker.process_identity()
        if expected_peer is None
        else dict(expected_peer)
    )
    session_nonce = secrets.token_hex(32) if nonce is None else _nonce(nonce)
    parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC)
    parent.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    child.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    broker_pidfd_copy = os.dup(broker_pidfd)
    recovery_pidfd_copy = os.dup(recovery_pidfd)
    final_release_pidfd_copy = (
        None
        if final_release_pidfd is None
        else os.dup(final_release_pidfd)
    )
    pid = os.fork()
    if pid == 0:
        parent.close()
        code = 2
        try:
            server = ClosureServer(
                child,
                root=Path(root),
                nonce=session_nonce,
                expected_peer=selected_peer,
                broker_actor=broker_actor,
                broker_pidfd=broker_pidfd_copy,
                recovery_actor=recovery_actor,
                recovery_pidfd=recovery_pidfd_copy,
                recovery_lock_extent=recovery_lock_extent,
                final_release_actor=final_release_actor,
                final_release_pidfd=final_release_pidfd_copy,
                final_release_pidfd_method=(
                    final_release_pidfd_method
                ),
                final_release_handoff_identity=(
                    final_release_handoff_identity
                ),
                closure_parent_fd=closure_parent_fd,
                closure_lock_extent=lock_extent,
                closure_lock_fd=closure_lock_fd,
                extents=list(extent_values),
                extent_fds=extent_fds,
                require_control_endpoint_absence=(
                    require_control_endpoint_absence
                ),
                control_endpoint_paths=control_endpoint_paths,
            )
            assert server.root_fd is not None
            broker.close_unlisted_descriptors(
                {
                    child.fileno(),
                    broker_pidfd_copy,
                    recovery_pidfd_copy,
                    *(
                        ()
                        if final_release_pidfd_copy is None
                        else (final_release_pidfd_copy,)
                    ),
                    closure_parent_fd,
                    closure_lock_fd,
                    server.root_fd,
                    *extent_fds,
                }
            )
            code = server.run()
        except BaseException:
            code = 2
        finally:
            try:
                child.close()
            except BaseException:
                pass
        os._exit(code)
    child_close_attempted = False
    parent_close_attempted = False
    parent_descriptor_entries = [
        ("closure broker pidfd copy", broker_pidfd_copy),
        ("closure recovery pidfd copy", recovery_pidfd_copy),
        *(
            []
            if final_release_pidfd_copy is None
            else [
                (
                    "closure final-release pidfd copy",
                    final_release_pidfd_copy,
                )
            ]
        ),
        *[
            (f"closure transferred descriptor {index}", descriptor)
            for index, descriptor in enumerate(descriptors)
        ],
    ]
    parent_descriptor_close_attempted = [
        False for _entry in parent_descriptor_entries
    ]

    def close_parent_descriptors() -> None:
        primary: BaseException | None = None
        for index, (label, descriptor) in enumerate(
            parent_descriptor_entries
        ):
            if parent_descriptor_close_attempted[index]:
                continue
            parent_descriptor_close_attempted[index] = True
            try:
                os.close(descriptor)
            except BaseException as exc:
                if primary is None:
                    primary = exc
                else:
                    primary.add_note(
                        f"{label} close also failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
        if primary is not None:
            raise primary

    pidfd = -1
    pidfd_method = ""
    try:
        child_close_attempted = True
        child.close()
        close_parent_descriptors()
        pidfd, pidfd_method = broker.open_pidfd(pid)
        ready = broker.receive_frame(
            parent,
            require_message_credentials=True,
        )
        record = ready.record
        if (
            record.get("schema_version") != RESPONSE_SCHEMA
            or record.get("status") != "PASS"
            or record.get("action") != "READY"
            or record.get("nonce") != session_nonce
            or record.get("sequence") != 0
        ):
            raise ClosureProtocolError("READY_IDENTITY_DRIFT", "closure READY identity drifted")
        actor = record.get("actor")
        if type(actor) is not dict or actor.get("pid") != pid or actor.get("pid_starttime") != broker.process_starttime(pid):
            raise ClosureProtocolError("READY_IDENTITY_DRIFT", "closure actor identity drifted")
        if {
            key: ready.peer[key]
            for key in ("pid", "pid_starttime", "uid")
        } != {
            key: actor[key]
            for key in ("pid", "pid_starttime", "uid")
        }:
            raise ClosureProtocolError("READY_IDENTITY_DRIFT", "closure READY sender identity drifted")
        process = ClosureProcess(
            pid=pid,
            pidfd=pidfd,
            pidfd_method=pidfd_method,
            connection=parent,
            nonce=session_nonce,
            actor=dict(actor),
        )
        pidfd = -1
        return process
    except BaseException as exc:
        if not child_close_attempted:
            child_close_attempted = True
            broker.preserve_spawn_cleanup_failure(
                exc,
                label="closure child socket",
                cleanup=child.close,
            )
        broker.preserve_spawn_cleanup_failure(
            exc,
            label="closure parent capabilities",
            cleanup=close_parent_descriptors,
        )
        if not parent_close_attempted:
            parent_close_attempted = True
            broker.preserve_spawn_cleanup_failure(
                exc,
                label="closure parent control",
                cleanup=parent.close,
            )
        broker.terminate_and_reap_spawned_child(pid, primary=exc)
        if pidfd >= 0:
            owned_pidfd = pidfd
            pidfd = -1
            broker.preserve_spawn_cleanup_failure(
                exc,
                label="closure pidfd",
                cleanup=lambda: os.close(owned_pidfd),
            )
        raise


def spawn_persistent_closure(
    *,
    root: Path | str,
    broker_actor: Mapping[str, object],
    broker_pidfd: int,
    recovery_actor: Mapping[str, object],
    recovery_pidfd: int,
    recovery_lock_extent: object,
    final_release_actor: Mapping[str, object],
    final_release_pidfd: int,
    final_release_pidfd_method: str,
    final_release_handoff_identity: Mapping[str, object],
    prepared_result: Mapping[str, object],
    descriptors: tuple[int, ...],
    expected_peer: Mapping[str, int],
    package_authorization: broker.PackageRoleAuthorizationProtocol,
    native_helper: broker.NativeHelperProtocol,
    nonce: str | None = None,
) -> ClosureProcess:
    """Start the package-pinned, single-use formal closure actor."""

    package_authorization.require_verified_role(PACKAGE_ROLE)
    if native_helper.landlock_abi() < 1:
        raise ClosureProtocolError(
            "NATIVE_HELPER_REQUIRED",
            "formal closure requires the package-pinned native helper",
        )
    return _spawn_closure(
        root=root,
        broker_actor=broker_actor,
        broker_pidfd=broker_pidfd,
        recovery_actor=recovery_actor,
        recovery_pidfd=recovery_pidfd,
        recovery_lock_extent=recovery_lock_extent,
        final_release_actor=final_release_actor,
        final_release_pidfd=final_release_pidfd,
        final_release_pidfd_method=final_release_pidfd_method,
        final_release_handoff_identity=(
            final_release_handoff_identity
        ),
        prepared_result=prepared_result,
        descriptors=descriptors,
        expected_peer=expected_peer,
        nonce=nonce,
        require_control_endpoint_absence=True,
    )


def spawn_closure_for_test(
    *,
    root: Path | str,
    broker_actor: Mapping[str, object],
    broker_pidfd: int,
    recovery_actor: Mapping[str, object],
    recovery_pidfd: int,
    recovery_lock_extent: object,
    prepared_result: Mapping[str, object],
    descriptors: tuple[int, ...],
    final_release_actor: Mapping[str, object] | None = None,
    final_release_pidfd: int | None = None,
    final_release_pidfd_method: str | None = None,
    final_release_handoff_identity: Mapping[str, object] | None = None,
    nonce: str | None = None,
) -> ClosureProcess:
    """Transfer the last root-writable FDs into a zero-authority actor."""

    return _spawn_closure(
        root=root,
        broker_actor=broker_actor,
        broker_pidfd=broker_pidfd,
        recovery_actor=recovery_actor,
        recovery_pidfd=recovery_pidfd,
        recovery_lock_extent=recovery_lock_extent,
        final_release_actor=final_release_actor,
        final_release_pidfd=final_release_pidfd,
        final_release_pidfd_method=final_release_pidfd_method,
        final_release_handoff_identity=(
            final_release_handoff_identity
        ),
        prepared_result=prepared_result,
        descriptors=descriptors,
        nonce=nonce,
        require_control_endpoint_absence=False,
    )


__all__ = [
    "ACTOR_SCHEMA",
    "BUDGET_TERMINAL_SCHEMA",
    "CLOSURE_RESULT_SCHEMA",
    "ClosureProcess",
    "DetachedClosureProcess",
    "ClosureProtocolError",
    "ClosureServer",
    "FORMAL_MANIFEST_SCHEMA",
    "LOCK_CONSUMPTION_SCHEMA",
    "PACKAGE_ROLE",
    "RECOVERY_TERMINAL_SCHEMA",
    "REQUEST_SCHEMA",
    "RESPONSE_SCHEMA",
    "snapshot_root_entries",
    "attach_broker_forked_closure",
    "spawn_closure_for_test",
    "spawn_persistent_closure",
    "writable_root_descriptors",
]
