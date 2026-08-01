#!/usr/bin/env python3
"""Independent stdlib-only outside replay for a closed AB16 formal root."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any, Final


REPLAY_SCHEMA: Final = (
    "noncert-cuts-ab16-formal-root-outside-replay-alternate-v1"
)
MANIFEST_SCHEMA: Final = "noncert-cuts-ab16-formal-manifest-v2"
BUDGET_TERMINAL_SCHEMA: Final = (
    "noncert-cuts-ab16-formal-root-budget-terminal-v2"
)
MANIFEST_PATH: Final = "formal-closure/formal-manifest.json"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
FALSE_AUTHORITY: Final = {
    "changes_certified_exact": False,
    "changes_cut_state": False,
    "changes_lower_bound": False,
    "changes_production": False,
    "changes_upper_bound": False,
    "research_only": True,
}
DIRECTORY_FLAGS = (
    os.O_RDONLY
    | os.O_DIRECTORY
    | os.O_NOFOLLOW
    | os.O_CLOEXEC
)
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC


class AlternateFormalRootReplayError(RuntimeError):
    """The alternate formal-root replay failed closed."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8") + b"\n"


def _canonical_digest_bytes(value: object) -> bytes:
    return _canonical(value).removesuffix(b"\n")


def _load(raw: bytes, label: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise AlternateFormalRootReplayError(
                    f"{label} contains a duplicate key"
                )
            result[key] = value
        return result

    try:
        value = json.loads(
            raw,
            object_pairs_hook=pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(
                AlternateFormalRootReplayError(
                    f"{label} contains {token}"
                )
            ),
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise AlternateFormalRootReplayError(
            f"{label} is not strict JSON"
        ) from exc
    if type(value) is not dict or _canonical(value) != raw:
        raise AlternateFormalRootReplayError(
            f"{label} is not canonical JSON"
        )
    return value


def _validate_same_uid_baseline(
    value: object,
    expected_sha256: object,
) -> dict[str, object]:
    fields = {
        "mode",
        "observed_uid",
        "policy_id",
        "process_scope_contract",
        "processes",
        "schema_version",
        "threat_boundary",
    }
    if (
        type(value) is not dict
        or set(value) != fields
        or value["schema_version"]
        != "noncert-cuts-ab16-same-uid-process-baseline-v1"
        or value["mode"] != "LIVE_PROCFS_FULL_SCOPE"
        or value["observed_uid"] != os.getuid()
        or value["policy_id"]
        != "exact-resource-gate-pid-starttime-classification-v1"
        or value["process_scope_contract"]
        != "EXACT_PID_STARTTIME_CLASSIFICATION_NO_GLOBAL_FD_SCAN"
        or value["threat_boundary"]
        != "NONADVERSARIAL_SAME_UID_AMBIENT"
        or type(value["processes"]) is not list
    ):
        raise AlternateFormalRootReplayError(
            "same-UID baseline discriminator differs"
        )
    checked: list[dict[str, object]] = []
    identities: set[tuple[int, int]] = set()
    for raw_process in value["processes"]:
        process_fields = {
            "classification",
            "command_sha256",
            "pid",
            "starttime",
        }
        if type(raw_process) is not dict or set(raw_process) != process_fields:
            raise AlternateFormalRootReplayError(
                "same-UID baseline process shape differs"
            )
        identity = (raw_process["pid"], raw_process["starttime"])
        if (
            raw_process["classification"]
            not in {
                "ALLOWED_CAMPAIGN_ACTOR",
                "NONCONFLICTING_AMBIENT",
                "RESOURCE_GATE_ANCESTOR",
            }
            or type(raw_process["command_sha256"]) is not str
            or SHA256_RE.fullmatch(raw_process["command_sha256"])
            is None
            or type(identity[0]) is not int
            or identity[0] <= 0
            or type(identity[1]) is not int
            or identity[1] <= 0
            or identity in identities
        ):
            raise AlternateFormalRootReplayError(
                "same-UID baseline process identity differs"
            )
        identities.add(identity)
        checked.append(dict(raw_process))
    if checked != sorted(
        checked,
        key=lambda item: (item["pid"], item["starttime"]),
    ):
        raise AlternateFormalRootReplayError(
            "same-UID baseline ordering differs"
        )
    if (
        type(expected_sha256) is not str
        or SHA256_RE.fullmatch(expected_sha256) is None
        or hashlib.sha256(_canonical_digest_bytes(value)).hexdigest()
        != expected_sha256
    ):
        raise AlternateFormalRootReplayError(
            "same-UID baseline digest differs"
        )
    return dict(value)


def _signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _sha256_fd(descriptor: int, size_bytes: int) -> str:
    digest = hashlib.sha256()
    offset = 0
    while offset < size_bytes:
        block = os.pread(
            descriptor,
            min(1024 * 1024, size_bytes - offset),
            offset,
        )
        if not block:
            raise AlternateFormalRootReplayError(
                "regular file ended before its stat size"
            )
        digest.update(block)
        offset += len(block)
    if os.pread(descriptor, 1, size_bytes):
        raise AlternateFormalRootReplayError(
            "regular file grew during replay"
        )
    return digest.hexdigest()


def _open_absolute_root(path: Path) -> int:
    if not path.is_absolute():
        raise AlternateFormalRootReplayError(
            "formal root is not absolute"
        )
    descriptor = os.open("/", DIRECTORY_FLAGS)
    try:
        for component in path.parts[1:]:
            successor = os.open(
                component,
                DIRECTORY_FLAGS,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = successor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _walk(root_fd: int) -> list[dict[str, object]]:
    retained: list[
        tuple[str, int, tuple[int, ...], tuple[str, ...]]
    ] = [
        (
            ".",
            os.dup(root_fd),
            _signature(os.fstat(root_fd)),
            tuple(sorted(os.listdir(root_fd))),
        )
    ]
    entries: list[dict[str, object]] = []
    try:
        index = 0
        while index < len(retained):
            relative_parent, parent_fd, _identity, names = retained[index]
            for name in names:
                if (
                    not name
                    or name in {".", ".."}
                    or "/" in name
                ):
                    raise AlternateFormalRootReplayError(
                        "formal root contains a noncanonical member"
                    )
                relative = (
                    name
                    if relative_parent == "."
                    else f"{relative_parent}/{name}"
                )
                before = os.stat(
                    name,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                if stat.S_ISDIR(before.st_mode):
                    child = os.open(
                        name,
                        DIRECTORY_FLAGS,
                        dir_fd=parent_fd,
                    )
                    opened = os.fstat(child)
                    if _signature(opened) != _signature(before):
                        os.close(child)
                        raise AlternateFormalRootReplayError(
                            f"directory changed during replay: {relative}"
                        )
                    retained.append(
                        (
                            relative,
                            child,
                            _signature(opened),
                            tuple(sorted(os.listdir(child))),
                        )
                    )
                    entries.append(
                        {
                            "mode_octal": (
                                f"{stat.S_IMODE(opened.st_mode):04o}"
                            ),
                            "path": relative,
                            "type": "directory",
                        }
                    )
                elif stat.S_ISREG(before.st_mode):
                    if before.st_nlink != 1:
                        raise AlternateFormalRootReplayError(
                            f"regular file link count differs: {relative}"
                        )
                    descriptor = os.open(
                        name,
                        READ_FLAGS,
                        dir_fd=parent_fd,
                    )
                    try:
                        opened = os.fstat(descriptor)
                        if _signature(opened) != _signature(before):
                            raise AlternateFormalRootReplayError(
                                f"regular file changed: {relative}"
                            )
                        digest = _sha256_fd(
                            descriptor,
                            opened.st_size,
                        )
                        if _signature(os.fstat(descriptor)) != _signature(
                            opened
                        ):
                            raise AlternateFormalRootReplayError(
                                f"regular file drifted: {relative}"
                            )
                        entries.append(
                            {
                                "mode_octal": (
                                    f"{stat.S_IMODE(opened.st_mode):04o}"
                                ),
                                "path": relative,
                                "sha256": digest,
                                "size_bytes": opened.st_size,
                                "type": "regular",
                            }
                        )
                    finally:
                        os.close(descriptor)
                else:
                    raise AlternateFormalRootReplayError(
                        f"symlink or special node is forbidden: {relative}"
                    )
            index += 1
        for relative, descriptor, identity, names in retained:
            if (
                _signature(os.fstat(descriptor)) != identity
                or tuple(sorted(os.listdir(descriptor))) != names
            ):
                raise AlternateFormalRootReplayError(
                    f"directory membership drifted: {relative}"
                )
        entries.sort(
            key=lambda item: (
                str(item["path"]),
                str(item["type"]),
            )
        )
        return entries
    finally:
        for _relative, descriptor, _identity, _names in reversed(
            retained
        ):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _read_member(
    root_fd: int,
    relative: str,
    expected: Mapping[str, object],
) -> bytes:
    parts = PurePosixPath(relative).parts
    parent = os.dup(root_fd)
    try:
        for component in parts[:-1]:
            successor = os.open(
                component,
                DIRECTORY_FLAGS,
                dir_fd=parent,
            )
            os.close(parent)
            parent = successor
        descriptor = os.open(
            parts[-1],
            READ_FLAGS,
            dir_fd=parent,
        )
        try:
            metadata = os.fstat(descriptor)
            raw = os.pread(descriptor, metadata.st_size, 0)
            if (
                len(raw) != metadata.st_size
                or hashlib.sha256(raw).hexdigest()
                != expected["sha256"]
                or metadata.st_size != expected["size_bytes"]
            ):
                raise AlternateFormalRootReplayError(
                    f"member identity drifted: {relative}"
                )
            return raw
        finally:
            os.close(descriptor)
    finally:
        os.close(parent)


def _actor_absent(actor: object, label: str) -> dict[str, object]:
    if (
        type(actor) is not dict
        or set(actor) != {"schema_version", "pid", "pid_starttime", "uid"}
        or any(
            type(actor[field]) is not int
            or actor[field] <= 0
            for field in ("pid", "pid_starttime")
        )
        or type(actor["uid"]) is not int
        or actor["uid"] < 0
    ):
        raise AlternateFormalRootReplayError(
            f"{label} actor identity is malformed"
        )
    try:
        fields = Path(f"/proc/{actor['pid']}/stat").read_text(
            encoding="ascii"
        ).split()
        observed: int | None = int(fields[21])
    except FileNotFoundError:
        observed = None
    except (OSError, UnicodeError, ValueError, IndexError) as exc:
        raise AlternateFormalRootReplayError(
            f"{label} actor absence cannot be observed"
        ) from exc
    if observed == actor["pid_starttime"]:
        raise AlternateFormalRootReplayError(
            f"{label} actor remains live"
        )
    return {
        "actor": dict(actor),
        "observed_starttime": observed,
        "state": "EXACT_ACTOR_ABSENT",
    }


def replay_formal_root(root: Path | str) -> dict[str, object]:
    absolute = Path(os.path.abspath(root))
    root_fd = _open_absolute_root(absolute)
    try:
        root_stat = os.fstat(root_fd)
        entries = _walk(root_fd)
        by_path = {
            str(entry["path"]): entry
            for entry in entries
        }
        if len(by_path) != len(entries):
            raise AlternateFormalRootReplayError(
                "formal root contains duplicate paths"
            )
        manifest_entry = by_path.get(MANIFEST_PATH)
        if (
            type(manifest_entry) is not dict
            or manifest_entry.get("type") != "regular"
            or manifest_entry.get("mode_octal") != "0444"
        ):
            raise AlternateFormalRootReplayError(
                "formal manifest path or mode differs"
            )
        manifest = _load(
            _read_member(
                root_fd,
                MANIFEST_PATH,
                manifest_entry,
            ),
            "formal manifest",
        )
        manifest_fields = {
            "authority",
            "budget_terminal_identity",
            "closure_actor",
            "entries",
            "entries_sha256",
            "excluded_terminal_path",
            "lock_consumption_identity",
            "recovery_terminal_identity",
            "same_uid_process_baseline_sha256",
            "schema_version",
            "terminal_join_sha256",
            "writer_capability_closure",
        }
        if (
            set(manifest) != manifest_fields
            or manifest.get("schema_version") != MANIFEST_SCHEMA
            or manifest.get("authority") != FALSE_AUTHORITY
            or manifest.get("excluded_terminal_path") != MANIFEST_PATH
            or type(manifest.get("entries")) is not list
            or not isinstance(
                manifest.get("terminal_join_sha256"),
                str,
            )
            or SHA256_RE.fullmatch(
                manifest["terminal_join_sha256"]
            )
            is None
        ):
            raise AlternateFormalRootReplayError(
                "formal manifest discriminator differs"
            )
        expected_entries = [
            entry
            for entry in entries
            if entry["path"] != MANIFEST_PATH
        ]
        if manifest["entries"] != expected_entries:
            raise AlternateFormalRootReplayError(
                "formal manifest closure equation failed"
            )
        digest = hashlib.sha256(
            _canonical(expected_entries)
        ).hexdigest()
        if manifest.get("entries_sha256") != digest:
            raise AlternateFormalRootReplayError(
                "formal manifest entries digest differs"
            )
        for field, path in (
            (
                "budget_terminal_identity",
                "formal-closure/budget-terminal.json",
            ),
            (
                "recovery_terminal_identity",
                "formal-closure/recovery-disarm-terminal.json",
            ),
            (
                "lock_consumption_identity",
                "locks/formal-closure-consumption.json",
            ),
        ):
            identity = manifest.get(field)
            entry = by_path.get(path)
            if (
                type(identity) is not dict
                or type(entry) is not dict
                or identity.get("path") != path
                or identity.get("sha256") != entry.get("sha256")
                or identity.get("size_bytes")
                != entry.get("size_bytes")
            ):
                raise AlternateFormalRootReplayError(
                    f"{field} fixed-member join failed"
                )
        recovery_entry = by_path[
            "formal-closure/recovery-disarm-terminal.json"
        ]
        recovery = _load(
            _read_member(
                root_fd,
                "formal-closure/recovery-disarm-terminal.json",
                recovery_entry,
            ),
            "recovery terminal",
        )
        if (
            recovery.get("state")
            != "RECOVERY_ABSENT_AND_TAKEOVER_LOCK_RELEASED"
            or recovery.get("terminal_join_sha256")
            != manifest["terminal_join_sha256"]
            or recovery.get("closure_actor")
            != manifest.get("closure_actor")
        ):
            raise AlternateFormalRootReplayError(
                "recovery terminal/manifest join failed"
            )
        budget_entry = by_path[
            "formal-closure/budget-terminal.json"
        ]
        budget_terminal = _load(
            _read_member(
                root_fd,
                "formal-closure/budget-terminal.json",
                budget_entry,
            ),
            "budget terminal",
        )
        budget_fields = {
            "broker_actor",
            "budget_contract",
            "closure_actor",
            "same_uid_process_baseline",
            "same_uid_process_baseline_sha256",
            "schema_version",
            "state",
            "terminal_join_sha256",
            "writer_capability_closure",
        }
        if (
            set(budget_terminal) != budget_fields
            or budget_terminal["schema_version"]
            != BUDGET_TERMINAL_SCHEMA
            or budget_terminal["closure_actor"]
            != manifest["closure_actor"]
            or budget_terminal["state"]
            != "BUDGET_TERMINAL_AFTER_RECOVERY_DISARM"
            or budget_terminal["terminal_join_sha256"]
            != manifest["terminal_join_sha256"]
            or budget_terminal["broker_actor"]
            != recovery.get("broker_actor")
            or budget_terminal["same_uid_process_baseline_sha256"]
            != manifest["same_uid_process_baseline_sha256"]
            or budget_terminal["writer_capability_closure"]
            != manifest["writer_capability_closure"]
        ):
            raise AlternateFormalRootReplayError(
                "budget terminal/manifest join failed"
            )
        _validate_same_uid_baseline(
            budget_terminal["same_uid_process_baseline"],
            budget_terminal["same_uid_process_baseline_sha256"],
        )
        return {
            "actor_absence": {
                "broker": _actor_absent(
                    budget_terminal.get("broker_actor"),
                    "broker",
                ),
                "closure": _actor_absent(
                    manifest.get("closure_actor"),
                    "closure",
                ),
                "recovery": _actor_absent(
                    recovery.get("recovery_actor"),
                    "recovery",
                ),
            },
            "authority": dict(FALSE_AUTHORITY),
            "authority_scope": "AB16_RESEARCH_ONLY",
            "formal_manifest_identity": {
                "path": MANIFEST_PATH,
                "sha256": manifest_entry["sha256"],
                "size_bytes": manifest_entry["size_bytes"],
            },
            "formal_root": {
                "device": root_stat.st_dev,
                "inode": root_stat.st_ino,
                "mode_octal": (
                    f"{stat.S_IMODE(root_stat.st_mode):04o}"
                ),
                "path": str(absolute),
                "uid": root_stat.st_uid,
            },
            "implementation": "package-pinned-stdlib-alternate-v1",
            "manifest_entries_sha256": digest,
            "schema_version": REPLAY_SCHEMA,
            "state": "FORMAL_ROOT_CLOSURE_ACCEPTED",
            "terminal_join_sha256": manifest[
                "terminal_join_sha256"
            ],
        }
    finally:
        os.close(root_fd)


__all__ = [
    "AlternateFormalRootReplayError",
    "FALSE_AUTHORITY",
    "REPLAY_SCHEMA",
    "replay_formal_root",
]
