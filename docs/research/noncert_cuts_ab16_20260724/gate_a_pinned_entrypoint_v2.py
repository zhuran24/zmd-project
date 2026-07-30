#!/usr/bin/env python3
"""Pinned, fail-closed entrypoint for AB16 Gate-A operations only.

The file must itself be executed as ``/proc/self/fd/N`` with that descriptor
still open.  A detached size/hash pins the precreated planned-source
observation.  Every local dependency is then opened once without following
symlinks, read and hashed through that same descriptor, checked against its
planned identity, and compiled from the verified bytes.

This entrypoint can build a disposable authority, run its disposable drill, or
record/finalize Gate A.  It deliberately has no formal, solver, campaign, or
organic-arm dispatch.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
from types import ModuleType
from typing import Any


ENTRYPOINT_ROLE = "script.gate_a_pinned_entrypoint_v2"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
PROC_FD_RE = re.compile(r"/proc/self/fd/([1-9][0-9]*)\Z")
MAX_OBSERVATION_BYTES = 4 * 1024 * 1024
MAX_MODULE_BYTES = 8 * 1024 * 1024

MODULE_LOAD_ORDER: tuple[tuple[str, str], ...] = (
    ("campaign_authority_v4", "script.campaign_authority_v4"),
    ("ab16_resource_admission_v1", "script.ab16_resource_admission_v1"),
    ("ab16_campaign_bootstrap_v2", "script.ab16_campaign_bootstrap_v2"),
    ("organic_resource_lifecycle_v2", "script.organic_resource_lifecycle_v2"),
    ("organic_resource_verifier_v2", "script.organic_resource_verifier_v2"),
    ("systemd_unit_reference_v1", "script.systemd_unit_reference_v1"),
    ("disposable_drill_authority_v2", "script.disposable_drill_authority_v2"),
    ("organic_unit_orchestrator_v2", "script.organic_unit_orchestrator_v2"),
    ("gate_a_validation_v2", "script.gate_a_validation_v2"),
)

COMMAND_TARGETS = {
    "build-disposable": ("disposable_drill_authority_v2", None),
    "drill": ("organic_unit_orchestrator_v2", "drill"),
    "finalize": ("gate_a_validation_v2", "finalize"),
    "record-preflight": ("gate_a_validation_v2", "record-preflight"),
}


class PinnedEntrypointError(RuntimeError):
    """The entrypoint or one of its exact source dependencies was not pinned."""


class _LocalModuleBlocker:
    """Reject ordinary-path fallback for any module in the planned script set."""

    def __init__(self, names: set[str]) -> None:
        self._names = names

    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: object = None,
    ) -> None:
        del path, target
        if fullname.split(".", 1)[0] in self._names:
            raise PinnedEntrypointError(f"ordinary import of planned local module is forbidden: {fullname}")
        return None


def _canonical_json_bytes(value: object) -> bytes:
    def check(item: object, label: str) -> None:
        if item is None or type(item) in {bool, int, str}:
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise PinnedEntrypointError(f"{label} contains a non-finite float")
            return
        if type(item) is list:
            for index, child in enumerate(item):
                check(child, f"{label}[{index}]")
            return
        if type(item) is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise PinnedEntrypointError(f"{label} has a non-string key")
                check(child, f"{label}.{key}")
            return
        raise PinnedEntrypointError(f"{label} is not strict JSON")

    check(value, "value")
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _strict_loads(raw: bytes, label: str) -> Mapping[str, Any]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise PinnedEntrypointError(f"{label} has duplicate key {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(
                PinnedEntrypointError(f"{label} has invalid constant {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PinnedEntrypointError(f"{label} is malformed JSON") from exc
    if type(value) is not dict or _canonical_json_bytes(value) != raw:
        raise PinnedEntrypointError(f"{label} is not canonical strict JSON")
    return value


def _stat_signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _open_parent_dirfd(path: Path) -> tuple[Path, int]:
    absolute = Path(os.path.abspath(path))
    if absolute == Path(absolute.anchor):
        raise PinnedEntrypointError("file path may not be the filesystem root")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute.anchor, flags)
    except OSError as exc:
        raise PinnedEntrypointError("invalid or symlinked path root") from exc
    try:
        for component in absolute.parts[1:-1]:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return absolute, descriptor
    except OSError as exc:
        os.close(descriptor)
        raise PinnedEntrypointError("invalid or symlinked path component") from exc


def _read_open_fd(
    descriptor: int,
    *,
    label: str,
    maximum_size: int,
) -> tuple[bytes, os.stat_result]:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size < 0 or before.st_size > maximum_size:
        raise PinnedEntrypointError(f"{label} is not one bounded regular file")
    chunks: list[bytes] = []
    offset = 0
    while offset < before.st_size:
        chunk = os.pread(descriptor, min(1024 * 1024, before.st_size - offset), offset)
        if not chunk:
            raise PinnedEntrypointError(f"{label} was truncated during same-FD read")
        chunks.append(chunk)
        offset += len(chunk)
    if os.pread(descriptor, 1, offset):
        raise PinnedEntrypointError(f"{label} grew during same-FD read")
    after = os.fstat(descriptor)
    if _stat_signature(after) != _stat_signature(before):
        raise PinnedEntrypointError(f"{label} changed during same-FD read")
    return b"".join(chunks), after


def _validate_expected_identity(value: object, label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != {
        "device",
        "inode",
        "mode",
        "mode_octal",
        "path",
        "sha256",
        "size_bytes",
    }:
        raise PinnedEntrypointError(f"{label} planned identity key set drifted")
    if (
        type(value["device"]) is not int
        or type(value["inode"]) is not int
        or type(value["mode"]) is not int
        or value["mode"] < 0
        or value["mode"] > 0o7777
        or type(value["mode_octal"]) is not str
        or value["mode_octal"] != f"{value['mode']:04o}"
        or type(value["path"]) is not str
        or not Path(value["path"]).is_absolute()
        or type(value["sha256"]) is not str
        or SHA256_RE.fullmatch(value["sha256"]) is None
        or type(value["size_bytes"]) is not int
        or value["size_bytes"] < 0
    ):
        raise PinnedEntrypointError(f"{label} planned identity is malformed")
    return value


def _verify_bytes(
    raw: bytes,
    observed: os.stat_result,
    expected: Mapping[str, Any],
    *,
    label: str,
) -> None:
    if (
        observed.st_dev != expected["device"]
        or observed.st_ino != expected["inode"]
        or stat.S_IMODE(observed.st_mode) != expected["mode"]
        or len(raw) != expected["size_bytes"]
        or hashlib.sha256(raw).hexdigest() != expected["sha256"]
    ):
        raise PinnedEntrypointError(f"{label} differs from planned byte identity")


def _verify_current_path(
    *,
    parent_fd: int,
    filename: str,
    observed: os.stat_result,
    label: str,
) -> None:
    try:
        current = os.stat(filename, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        raise PinnedEntrypointError(f"{label} path disappeared during read") from exc
    if _stat_signature(current) != _stat_signature(observed):
        raise PinnedEntrypointError(f"{label} path changed during same-FD read")


def _snapshot_expected_path(
    expected_value: object,
    *,
    label: str,
    maximum_size: int = MAX_MODULE_BYTES,
) -> bytes:
    expected = _validate_expected_identity(expected_value, label)
    absolute, parent_fd = _open_parent_dirfd(Path(expected["path"]))
    descriptor = -1
    try:
        descriptor = os.open(
            absolute.name,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        raw, observed = _read_open_fd(
            descriptor,
            label=label,
            maximum_size=maximum_size,
        )
        _verify_bytes(raw, observed, expected, label=label)
        _verify_current_path(
            parent_fd=parent_fd,
            filename=absolute.name,
            observed=observed,
            label=label,
        )
        return raw
    except OSError as exc:
        raise PinnedEntrypointError(f"{label} cannot be opened without symlinks") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_fd)


def _snapshot_detached_observation(
    path: Path | str,
    *,
    expected_size: int,
    expected_sha256: str,
) -> bytes:
    if (
        type(expected_size) is not int
        or expected_size < 0
        or expected_size > MAX_OBSERVATION_BYTES
        or type(expected_sha256) is not str
        or SHA256_RE.fullmatch(expected_sha256) is None
    ):
        raise PinnedEntrypointError("planned-source observation identity is malformed")
    absolute, parent_fd = _open_parent_dirfd(Path(path))
    descriptor = -1
    try:
        descriptor = os.open(
            absolute.name,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        raw, observed = _read_open_fd(
            descriptor,
            label="planned-source observation",
            maximum_size=MAX_OBSERVATION_BYTES,
        )
        if len(raw) != expected_size or hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise PinnedEntrypointError("planned-source observation detached identity drifted")
        _verify_current_path(
            parent_fd=parent_fd,
            filename=absolute.name,
            observed=observed,
            label="planned-source observation",
        )
        return raw
    except OSError as exc:
        raise PinnedEntrypointError("planned-source observation cannot be opened without symlinks") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_fd)


def _planned_sources(
    raw: bytes,
    *,
    expected_set_digest: str,
) -> Mapping[str, Mapping[str, Any]]:
    if type(expected_set_digest) is not str or SHA256_RE.fullmatch(expected_set_digest) is None:
        raise PinnedEntrypointError("planned source-set digest is malformed")
    record = _strict_loads(raw, "planned-source observation")
    if set(record) != {"planned_source_identities", "planned_source_set_digest"}:
        raise PinnedEntrypointError("planned-source observation key set drifted")
    sources = record["planned_source_identities"]
    if type(sources) is not dict or any(type(role) is not str for role in sources):
        raise PinnedEntrypointError("planned-source identities are malformed")
    # campaign_authority_v4.canonical_json, which defines the bootstrap digest,
    # is LF-terminated.  The surrounding observation is lifecycle JSON and is
    # deliberately not LF-terminated.
    computed = hashlib.sha256(_canonical_json_bytes(sources) + b"\n").hexdigest()
    if record["planned_source_set_digest"] != expected_set_digest or computed != expected_set_digest:
        raise PinnedEntrypointError("planned source-set digest drifted")
    required = {ENTRYPOINT_ROLE, *(role for _, role in MODULE_LOAD_ORDER)}
    if not required <= set(sources):
        raise PinnedEntrypointError("planned-source observation misses a local dependency")
    for role in required:
        _validate_expected_identity(sources[role], role)
    return sources


def _retained_entry_fd(source_name: str) -> int:
    if type(source_name) is not str:
        raise PinnedEntrypointError("entrypoint source name is malformed")
    matched = PROC_FD_RE.fullmatch(source_name)
    if matched is None:
        raise PinnedEntrypointError("ordinary path execution is forbidden; use one retained /proc/self/fd/N")
    descriptor = int(matched.group(1))
    try:
        os.fstat(descriptor)
    except OSError as exc:
        raise PinnedEntrypointError("entrypoint source descriptor is not retained") from exc
    return descriptor


def _snapshot_retained_entry(
    source_name: str,
    expected_value: object,
) -> bytes:
    expected = _validate_expected_identity(expected_value, "pinned entrypoint")
    descriptor = _retained_entry_fd(source_name)
    raw, observed = _read_open_fd(
        descriptor,
        label="pinned entrypoint",
        maximum_size=MAX_MODULE_BYTES,
    )
    _verify_bytes(raw, observed, expected, label="pinned entrypoint")
    absolute, parent_fd = _open_parent_dirfd(Path(expected["path"]))
    try:
        _verify_current_path(
            parent_fd=parent_fd,
            filename=absolute.name,
            observed=observed,
            label="pinned entrypoint",
        )
    finally:
        os.close(parent_fd)
    return raw


def _module_names(sources: Mapping[str, Mapping[str, Any]]) -> set[str]:
    result: set[str] = set()
    for role, identity in sources.items():
        if role.startswith("script."):
            result.add(Path(str(identity["path"])).stem)
    return result


def _preload_modules(
    sources: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, ModuleType], _LocalModuleBlocker, list[str]]:
    snapshots = {
        module_name: (
            role,
            _snapshot_expected_path(sources[role], label=role),
        )
        for module_name, role in MODULE_LOAD_ORDER
    }
    planned_module_names = _module_names(sources)
    collisions = sorted(name for name in planned_module_names if name in sys.modules)
    if collisions:
        raise PinnedEntrypointError(f"planned local module was already imported: {collisions[0]}")
    blocker = _LocalModuleBlocker(planned_module_names)
    original_path = list(sys.path)
    local_directories = {
        str(Path(str(identity["path"])).parent) for role, identity in sources.items() if role.startswith("script.")
    }
    sys.path[:] = [item for item in sys.path if item not in local_directories]
    sys.meta_path.insert(0, blocker)
    loaded: dict[str, ModuleType] = {}
    try:
        for module_name, role in MODULE_LOAD_ORDER:
            raw = snapshots[module_name][1]
            module = ModuleType(module_name)
            module.__file__ = str(sources[role]["path"])
            module.__package__ = ""
            module.__spec__ = None
            sys.modules[module_name] = module
            try:
                code = compile(raw, module.__file__, "exec", dont_inherit=True)
                exec(code, module.__dict__)
            except Exception:
                sys.modules.pop(module_name, None)
                raise
            loaded[module_name] = module
            sys.path[:] = [item for item in sys.path if item not in local_directories]
    except Exception:
        for module_name in reversed(tuple(loaded)):
            sys.modules.pop(module_name, None)
        if blocker in sys.meta_path:
            sys.meta_path.remove(blocker)
        sys.path[:] = original_path
        raise
    return loaded, blocker, original_path


def _dispatch(
    command: str,
    forwarded: Sequence[str],
    modules: Mapping[str, ModuleType],
) -> int:
    target = COMMAND_TARGETS.get(command)
    if target is None:
        raise PinnedEntrypointError("requested dispatch is not a Gate-A operation")
    module_name, subcommand = target
    module = modules[module_name]
    arguments = list(forwarded)
    if subcommand is not None:
        arguments.insert(0, subcommand)
    result = module.main(arguments)
    if type(result) is not int:
        raise PinnedEntrypointError("Gate-A target returned a non-integer status")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--planned-source-observation", required=True, type=Path)
    parser.add_argument("--planned-source-observation-size", required=True, type=int)
    parser.add_argument("--planned-source-observation-sha256", required=True)
    parser.add_argument("--planned-source-set-digest", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in sorted(COMMAND_TARGETS):
        commands.add_parser(command)
    return parser


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    arguments, forwarded = _parser().parse_known_args(argv)
    if forwarded[:1] == ["--"]:
        forwarded = forwarded[1:]
    arguments.forwarded = forwarded
    return arguments


def _run(arguments: argparse.Namespace, *, source_name: str) -> int:
    observation_raw = _snapshot_detached_observation(
        arguments.planned_source_observation,
        expected_size=arguments.planned_source_observation_size,
        expected_sha256=arguments.planned_source_observation_sha256,
    )
    sources = _planned_sources(
        observation_raw,
        expected_set_digest=arguments.planned_source_set_digest,
    )
    _snapshot_retained_entry(source_name, sources[ENTRYPOINT_ROLE])
    loaded, blocker, original_path = _preload_modules(sources)
    try:
        return _dispatch(arguments.command, arguments.forwarded, loaded)
    finally:
        for module_name, _role in reversed(MODULE_LOAD_ORDER):
            sys.modules.pop(module_name, None)
        if blocker in sys.meta_path:
            sys.meta_path.remove(blocker)
        sys.path[:] = original_path


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return _run(_parse_arguments(argv), source_name=__file__)
    except Exception as exc:
        print(
            json.dumps(
                {"detail": str(exc), "status": "FAIL_CLOSED"},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
