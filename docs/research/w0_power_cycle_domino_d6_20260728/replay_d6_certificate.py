#!/usr/bin/env python3
"""Independent, solver-free replay for one W0 D6 local completion result.

This program deliberately uses only the Python standard library.  It does not
import the producer, the gate, the shared research helpers, ``src``, or
OR-Tools.  A replay first checks the complete byte-identity graph.  It then
independently rebuilds the D6 antecedent from the copied strict instance,
framework, and seed.  Only a FEASIBLE producer result triggers semantic
certificate checking.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
from itertools import combinations
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, cast


MAX_ARTIFACT_BYTES = 128 * 1024 * 1024
SHA256_RE = re.compile(r"[0-9a-f]{64}")
CONFIG_SCHEMA = "research_run_config_v1"
RECEIPT_SCHEMA = "research_run_receipt_v1"
ARTIFACT_ROOT_MANIFEST_SCHEMA = "research_artifact_root_manifest_v1"
ISOLATED_PYTHON_PROCESS_SCHEMA = "isolated_python_process_contract_v1"
TERMINAL_RECEIPT_PATH = "receipt.json"
ANTECEDENT_SCHEMA = "w0_d6_antecedent_v1"
V3_ANTECEDENT_SCHEMA = "w0_d6_antecedent_v2"
GATE_RESULT_SCHEMA = "w0_d6_gate_result_v1"
RESULT_SCHEMA = "w0_d6_result_v1"
CONFIGURATION_SCHEMA = "w0_d6_configuration_v1"
CERTIFICATE_SCHEMA = "w0_d6_local_certificate_v1"
CLOSED_V2_CONFIG_PAYLOAD_SCHEMA = "w0_d6_run_config_v2"
CLOSED_V2_RECEIPT_PAYLOAD_SCHEMA = "w0_d6_receipt_payload_v2"
CLOSED_V2_REPLAY_RECEIPT_SCHEMA = "w0_d6_replay_receipt_v2"
PROTOCOL_COHORT = "w0_d6_swap_v3"
CLASS_ALLOCATION_PROFILE = "d6_6b_d9_6g_swap_v1"
V3_CONFIG_PAYLOAD_SCHEMA = "w0_d6_run_config_v3"
V3_RECEIPT_PAYLOAD_SCHEMA = "w0_d6_receipt_payload_v3"
V3_REPLAY_RECEIPT_SCHEMA = "w0_d6_replay_receipt_v3"
EXPECTED_PROJECT_LOCK_SHA256 = (
    "aeadef3aded03099d18580a05454c90af11a4dd6859d7798516ced73d2df2b42"
)
CLOSED_V2_PROFILE = "closed_v2"
SWAP_V3_PROFILE = "swap_v3"
CLASS_ORDER = ("3I2", "3L", "3O2", "3O3", "5L", "5O2", "6B", "6F", "6G")
D6_BEFORE_CLASS_COUNTS = {
    "3I2": 0,
    "3L": 7,
    "3O2": 0,
    "3O3": 3,
    "5L": 2,
    "5O2": 2,
    "6B": 1,
    "6F": 0,
    "6G": 2,
}
D6_AFTER_CLASS_COUNTS = {
    "3I2": 0,
    "3L": 7,
    "3O2": 0,
    "3O3": 3,
    "5L": 2,
    "5O2": 2,
    "6B": 0,
    "6F": 0,
    "6G": 3,
}
D9_BEFORE_CLASS_COUNTS = {
    "3I2": 0,
    "3L": 18,
    "3O2": 0,
    "3O3": 0,
    "5L": 3,
    "5O2": 0,
    "6B": 0,
    "6F": 0,
    "6G": 3,
}
D9_AFTER_CLASS_COUNTS = {
    "3I2": 0,
    "3L": 18,
    "3O2": 0,
    "3O3": 0,
    "5L": 3,
    "5O2": 0,
    "6B": 1,
    "6F": 0,
    "6G": 2,
}
GLOBAL_CLASS_COUNTS = {
    "3I2": 6,
    "3L": 109,
    "3O2": 6,
    "3O3": 11,
    "5L": 32,
    "5O2": 17,
    "6B": 3,
    "6F": 3,
    "6G": 32,
}
D6_BEFORE_TOTALS = {"bodies": 17, "active_inputs": 25, "active_outputs": 25}
D6_AFTER_TOTALS = {"bodies": 17, "active_inputs": 23, "active_outputs": 25}
D9_BEFORE_TOTALS = {"bodies": 24, "active_inputs": 30, "active_outputs": 24}
D9_AFTER_TOTALS = {"bodies": 24, "active_inputs": 32, "active_outputs": 24}
OPEN_SUPPORTS_DIR_FD = os.open in os.supports_dir_fd
SCANDIR_SUPPORTS_FD = os.scandir in os.supports_fd

BASE_ARTIFACT_RELATIVE_PATHS = {
    "config": "config.json",
    "antecedent": "antecedent.json",
    "result": "result.json",
    "inputs.strict_instance": "inputs/strict_instance.json",
    "inputs.framework": "inputs/framework.json",
    "inputs.seed": "inputs/seed.json",
    "sources.runner": "sources/run_d6_research.py",
    "sources.gate": "sources/d6_joint_completion_gate.py",
    "sources.replayer": "sources/replay_d6_certificate.py",
    "sources.common_contract": "sources/research_run_contract.py",
}
FEASIBLE_ARTIFACT_RELATIVE_PATHS = {
    "configuration": "configuration.json",
    "certificate": "certificate.json",
}

DIRECTIONS = ("N", "E", "S", "W")
DELTA = {"E": (1, 0), "N": (0, 1), "S": (0, -1), "W": (-1, 0)}
OPPOSITE = {"E": "W", "N": "S", "S": "N", "W": "E"}


class ReplayError(RuntimeError):
    """Fail-closed independent replay error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


class _OwnedDescriptor:
    """Track one descriptor until ownership is explicitly released or closed."""

    __slots__ = ("_descriptor",)

    def __init__(self, descriptor: int | None = None) -> None:
        self._descriptor = descriptor

    @property
    def owned(self) -> bool:
        return self._descriptor is not None

    def acquire(self, descriptor: int) -> int:
        if self._descriptor is not None:
            raise RuntimeError("descriptor ownership is already held")
        self._descriptor = descriptor
        return descriptor

    @property
    def descriptor(self) -> int:
        descriptor = self._descriptor
        if descriptor is None:
            raise RuntimeError("descriptor ownership has already been released")
        return descriptor

    def release(self) -> int:
        descriptor = self.descriptor
        self._descriptor = None
        return descriptor

    def close(self) -> BaseException | None:
        descriptor = self.release()
        try:
            os.close(descriptor)
        except BaseException as exc:
            return exc
        return None

    def close_preserving(self, error: BaseException) -> None:
        close_error = self.close()
        if close_error is not None:
            error.add_note(
                f"descriptor close failed: {type(close_error).__name__}: {close_error}"
            )


def _fail(code: str, detail: str) -> None:
    raise ReplayError(code, detail)


def _validate_json_value(value: object, label: str = "$") -> object:
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is list:
        return [_validate_json_value(item, f"{label}[{index}]") for index, item in enumerate(value)]
    if type(value) is dict:
        result: dict[str, object] = {}
        for key, item in value.items():
            if type(key) is not str:
                _fail("NON_JSON_VALUE", f"{label}: non-string object key")
            result[key] = _validate_json_value(item, f"{label}.{key}")
        return result
    _fail("NON_JSON_VALUE", f"{label}: unsupported {type(value).__name__}")


def canonical_json_bytes(value: object) -> bytes:
    """Match the G3 compact/sorted UTF-8 JSON encoding with one final LF."""

    normalized = _validate_json_value(value)
    try:
        rendered = json.dumps(
            normalized,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return (rendered + "\n").encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        _fail("NON_JSON_VALUE", str(exc))


def _duplicate_guard(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail("JSON_DUPLICATE_KEY", key)
        result[key] = value
    return result


def _reject_number(token: str) -> object:
    _fail("JSON_NUMBER_REJECTED", token)


def strict_json_loads(raw: bytes, label: str, *, require_canonical: bool = False) -> object:
    """Decode strict integer JSON, rejecting duplicate keys and non-finite values."""

    if type(raw) is not bytes or not raw:
        _fail("JSON_EMPTY", label)
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_duplicate_guard,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail("JSON_INVALID", f"{label}: {exc}")
    _validate_json_value(value)
    if require_canonical and canonical_json_bytes(value) != raw:
        _fail("JSON_NOT_CANONICAL", label)
    return value


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _reject_symlink_chain(path: Path, *, leaf_may_be_missing: bool = False) -> None:
    current = Path(path.anchor)
    for index, part in enumerate(path.parts[1:]):
        current /= part
        is_leaf = index == len(path.parts[1:]) - 1
        try:
            item = os.lstat(current)
        except FileNotFoundError:
            if is_leaf and leaf_may_be_missing:
                return
            _fail("PATH_COMPONENT_MISSING", str(current))
        if stat.S_ISLNK(item.st_mode):
            _fail("SYMLINK_REJECTED", str(current))
        if not is_leaf and not stat.S_ISDIR(item.st_mode):
            _fail("PATH_COMPONENT_NOT_DIRECTORY", str(current))


def _directory_open_flags() -> int:
    if (
        not hasattr(os, "O_DIRECTORY")
        or not hasattr(os, "O_NOFOLLOW")
        or not OPEN_SUPPORTS_DIR_FD
        or not SCANDIR_SUPPORTS_FD
    ):
        _fail(
            "PLATFORM_CAPABILITY_UNAVAILABLE",
            "descriptor-relative O_DIRECTORY|O_NOFOLLOW directory opens are required",
        )
    return (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
    )


def _open_absolute_directory_no_symlinks(
    path: Path | str,
    *,
    error_code: str,
) -> int:
    absolute = _absolute(path)
    parts = absolute.parts
    if not absolute.is_absolute() or not parts or not absolute.anchor:
        _fail(error_code, f"absolute directory path required: {absolute}")
    flags = _directory_open_flags()
    opened: list[_OwnedDescriptor] = []
    try:
        root_owner = _OwnedDescriptor()
        opened.append(root_owner)
        root_owner.acquire(os.open(absolute.anchor, flags))
        for part in parts[1:]:
            owner = _OwnedDescriptor()
            opened.append(owner)
            owner.acquire(os.open(part, flags, dir_fd=opened[-2].descriptor))
    except BaseException as exc:
        if isinstance(exc, OSError):
            primary: BaseException = ReplayError(error_code, f"{absolute}: {exc}")
        else:
            primary = exc
        for owner in reversed(opened):
            if owner.owned:
                owner.close_preserving(primary)
        if primary is exc:
            raise
        raise primary from exc
    if not opened:
        _fail(error_code, f"{absolute}: directory open produced no descriptor")
    leaf_owner = opened.pop()
    primary_close_error: BaseException | None = None
    for owner in reversed(opened):
        close_error = owner.close()
        if close_error is None:
            continue
        if primary_close_error is None:
            if isinstance(close_error, OSError):
                primary_close_error = ReplayError(
                    error_code,
                    (
                        f"{absolute}: ancestor descriptor close failed: "
                        f"{close_error}"
                    ),
                )
            else:
                primary_close_error = close_error
        else:
            primary_close_error.add_note(
                "additional ancestor descriptor close failure: "
                f"{type(close_error).__name__}: {close_error}"
            )
    if primary_close_error is not None:
        leaf_owner.close_preserving(primary_close_error)
        raise primary_close_error
    return leaf_owner.release()


def _open_absolute_regular_no_symlinks(
    path: Path | str,
    *,
    error_code: str,
) -> int:
    absolute = _absolute(path)
    parts = absolute.parts
    if (
        not absolute.is_absolute()
        or len(parts) < 2
        or not absolute.anchor
    ):
        _fail(error_code, f"absolute regular-file path required: {absolute}")
    directory_flags = _directory_open_flags()
    file_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | os.O_NOFOLLOW
        | getattr(os, "O_NONBLOCK", 0)
    )
    opened_directories: list[_OwnedDescriptor] = []
    file_owner = _OwnedDescriptor()
    try:
        root_owner = _OwnedDescriptor()
        opened_directories.append(root_owner)
        root_owner.acquire(os.open(absolute.anchor, directory_flags))
        for part in parts[1:-1]:
            owner = _OwnedDescriptor()
            opened_directories.append(owner)
            owner.acquire(
                os.open(
                    part,
                    directory_flags,
                    dir_fd=opened_directories[-2].descriptor,
                )
            )
        file_owner.acquire(
            os.open(
                parts[-1],
                file_flags,
                dir_fd=opened_directories[-1].descriptor,
            )
        )
    except BaseException as exc:
        if isinstance(exc, OSError):
            primary: BaseException = ReplayError(error_code, f"{absolute}: {exc}")
        else:
            primary = exc
        if file_owner.owned:
            file_owner.close_preserving(primary)
        for owner in reversed(opened_directories):
            if owner.owned:
                owner.close_preserving(primary)
        if primary is exc:
            raise
        raise primary from exc
    if not file_owner.owned:
        _fail(error_code, f"{absolute}: regular-file open produced no descriptor")
    primary_close_error: BaseException | None = None
    for owner in reversed(opened_directories):
        close_error = owner.close()
        if close_error is None:
            continue
        if primary_close_error is None:
            if isinstance(close_error, OSError):
                primary_close_error = ReplayError(
                    error_code,
                    (
                        f"{absolute}: ancestor descriptor close failed: "
                        f"{close_error}"
                    ),
                )
            else:
                primary_close_error = close_error
        else:
            primary_close_error.add_note(
                "additional ancestor descriptor close failure: "
                f"{type(close_error).__name__}: {close_error}"
            )
    if primary_close_error is not None:
        file_owner.close_preserving(primary_close_error)
        raise primary_close_error
    return file_owner.release()


def _stat_signature(item: os.stat_result) -> tuple[int, ...]:
    return (
        item.st_dev,
        item.st_ino,
        item.st_mode,
        item.st_nlink,
        item.st_size,
        item.st_mtime_ns,
        item.st_ctime_ns,
    )


def _require_isolated_python_process() -> dict[str, object]:
    observed = {
        "isolated": sys.flags.isolated,
        "ignore_environment": sys.flags.ignore_environment,
        "no_user_site": sys.flags.no_user_site,
        "safe_path": bool(getattr(sys.flags, "safe_path", False)),
        "dont_write_bytecode_flag": sys.flags.dont_write_bytecode,
        "dont_write_bytecode_runtime": sys.dont_write_bytecode,
    }
    expected = {
        "isolated": 1,
        "ignore_environment": 1,
        "no_user_site": 1,
        "safe_path": True,
        "dont_write_bytecode_flag": 1,
        "dont_write_bytecode_runtime": True,
    }
    if observed != expected:
        _fail(
            "PYTHON_PROCESS_CONTRACT_INVALID",
            f"expected={expected!r}; observed={observed!r}",
        )
    return {
        "schema": ISOLATED_PYTHON_PROCESS_SCHEMA,
        "required_argv_flags": ["-I", "-B"],
        "observed": observed,
    }


def _manifest_relative_path(
    value: object,
    label: str,
    *,
    allow_terminal_receipt: bool = False,
) -> str:
    if type(value) is not str or not value:
        _fail("ARTIFACT_ROOT_MANIFEST_INVALID", f"{label}: path must be non-empty text")
    path = cast(str, value)
    try:
        path.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        _fail("ARTIFACT_ROOT_MANIFEST_INVALID", f"{label}: path is not UTF-8 encodable")
    parts = path.split("/")
    if (
        path.startswith("/")
        or path.endswith("/")
        or "\\" in path
        or "\x00" in path
        or any(part in {"", ".", ".."} for part in parts)
    ):
        _fail("ARTIFACT_ROOT_PATH_ESCAPE", f"{label}: {path!r}")
    if parts[0] == TERMINAL_RECEIPT_PATH and (
        not allow_terminal_receipt or path != TERMINAL_RECEIPT_PATH
    ):
        _fail(
            "ARTIFACT_ROOT_RECEIPT_RESERVED",
            f"{label}: {TERMINAL_RECEIPT_PATH} is not a manifest member",
        )
    return path


def _validate_artifact_root_manifest(value: object) -> dict[str, object]:
    manifest = _exact_keys(value, {"schema", "entries"}, "artifact_root_manifest")
    if manifest["schema"] != ARTIFACT_ROOT_MANIFEST_SCHEMA:
        _fail("ARTIFACT_ROOT_MANIFEST_INVALID", "schema differs")
    raw_entries = _array(manifest["entries"], "artifact_root_manifest.entries")
    entries: list[dict[str, str]] = []
    entry_types: dict[str, str] = {}
    for index, raw_entry in enumerate(raw_entries):
        entry = _exact_keys(
            raw_entry,
            {"path", "type"},
            f"artifact_root_manifest.entries[{index}]",
        )
        path = _manifest_relative_path(
            entry["path"],
            f"artifact_root_manifest.entries[{index}].path",
        )
        node_type = entry["type"]
        if node_type not in {"directory", "regular_file"}:
            _fail(
                "ARTIFACT_ROOT_MANIFEST_INVALID",
                f"artifact_root_manifest.entries[{index}].type",
            )
        if path in entry_types:
            _fail("ARTIFACT_ROOT_MANIFEST_INVALID", f"duplicate path: {path}")
        entry_types[path] = node_type
        entries.append({"path": path, "type": node_type})
    if entries != sorted(entries, key=lambda item: item["path"]):
        _fail("ARTIFACT_ROOT_MANIFEST_INVALID", "entries are not path-sorted")
    for path in entry_types:
        parts = path.split("/")
        for depth in range(1, len(parts)):
            parent = "/".join(parts[:depth])
            if entry_types.get(parent) != "directory":
                _fail(
                    "ARTIFACT_ROOT_MANIFEST_INVALID",
                    f"{path}: parent {parent!r} is absent or not a directory",
                )
    return {
        "schema": ARTIFACT_ROOT_MANIFEST_SCHEMA,
        "entries": entries,
    }


def _validate_d6_manifest_layout(manifest: dict[str, object]) -> set[str]:
    regular_paths: set[str] = set()
    directory_paths: set[str] = set()
    for index, raw_entry in enumerate(
        _array(manifest["entries"], "artifact_root_manifest.entries")
    ):
        entry = _object(raw_entry, f"artifact_root_manifest.entries[{index}]")
        path = _text(
            entry["path"],
            f"artifact_root_manifest.entries[{index}].path",
        )
        node_type = _text(
            entry["type"],
            f"artifact_root_manifest.entries[{index}].type",
        )
        if node_type == "regular_file":
            regular_paths.add(path)
        else:
            directory_paths.add(path)
    required_directories = {
        "/".join(path.split("/")[:depth])
        for path in regular_paths
        for depth in range(1, len(path.split("/")))
    }
    if directory_paths != required_directories:
        _fail(
            "ARTIFACT_ROOT_DIRECTORY_SET_MISMATCH",
            (
                f"manifest_only={sorted(directory_paths - required_directories)!r}; "
                f"required_only={sorted(required_directories - directory_paths)!r}"
            ),
        )
    return regular_paths


def _artifact_root_entries(
    run_root: Path,
    *,
    expected_root_signature: tuple[int, ...] | None = None,
) -> dict[str, str]:
    flags = _directory_open_flags()
    root_owner = _OwnedDescriptor(
        _open_absolute_directory_no_symlinks(
            run_root,
            error_code="ARTIFACT_ROOT_OPEN_FAILED",
        )
    )
    try:
        root_before = os.fstat(root_owner.descriptor)
        if not stat.S_ISDIR(root_before.st_mode):
            _fail("RUN_ROOT_INVALID", str(run_root))
        root_signature = _stat_signature(root_before)
        if (
            expected_root_signature is not None
            and root_signature != expected_root_signature
        ):
            _fail("ARTIFACT_ROOT_CHANGED", str(run_root))
        observed: dict[str, str] = {}
        opened_directories: list[
            tuple[_OwnedDescriptor, tuple[str, ...], tuple[int, ...]]
        ] = [(root_owner, (), root_signature)]
    except OSError as exc:
        error = ReplayError("ARTIFACT_ROOT_OPEN_FAILED", f"{run_root}: {exc}")
        root_owner.close_preserving(error)
        raise error from exc
    except BaseException as exc:
        root_owner.close_preserving(exc)
        raise

    def walk(descriptor: int, prefix: tuple[str, ...]) -> None:
        try:
            with os.scandir(descriptor) as iterator:
                names = sorted(entry.name for entry in iterator)
        except OSError as exc:
            _fail(
                "ARTIFACT_ROOT_ENUMERATION_FAILED",
                f"{run_root.joinpath(*prefix)}: {exc}",
            )
        for name in names:
            relative = "/".join((*prefix, name))
            _manifest_relative_path(
                relative,
                "observed path",
                allow_terminal_receipt=True,
            )
            try:
                item = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            except OSError as exc:
                _fail(
                    "ARTIFACT_ROOT_ENUMERATION_FAILED",
                    f"{run_root.joinpath(*prefix, name)}: {exc}",
                )
            if stat.S_ISLNK(item.st_mode):
                _fail(
                    "ARTIFACT_ROOT_SYMLINK_REJECTED",
                    str(run_root.joinpath(*prefix, name)),
                )
            if stat.S_ISREG(item.st_mode):
                observed[relative] = "regular_file"
                continue
            if not stat.S_ISDIR(item.st_mode):
                _fail(
                    "ARTIFACT_ROOT_SPECIAL_NODE_REJECTED",
                    str(run_root.joinpath(*prefix, name)),
                )
            observed[relative] = "directory"
            child_prefix = (*prefix, name)
            child_owner = _OwnedDescriptor()
            try:
                child_owner.acquire(os.open(name, flags, dir_fd=descriptor))
            except OSError as exc:
                _fail(
                    "ARTIFACT_ROOT_ENUMERATION_FAILED",
                    f"{run_root.joinpath(*prefix, name)}: {exc}",
                )
            try:
                opened = os.fstat(child_owner.descriptor)
                child_signature = _stat_signature(opened)
                if opened.st_dev != item.st_dev or opened.st_ino != item.st_ino:
                    _fail(
                        "ARTIFACT_ROOT_CHANGED",
                        str(run_root.joinpath(*prefix, name)),
                    )
                opened_directories.append(
                    (child_owner, child_prefix, child_signature)
                )
            except OSError as exc:
                error = ReplayError(
                    "ARTIFACT_ROOT_CHANGED",
                    f"{run_root.joinpath(*prefix, name)}: {exc}",
                )
                child_owner.close_preserving(error)
                raise error from exc
            except BaseException as exc:
                child_owner.close_preserving(exc)
                raise
            walk(child_owner.descriptor, child_prefix)

    primary_error: BaseException | None = None
    try:
        walk(root_owner.descriptor, ())
    except BaseException as exc:
        primary_error = exc

    finalize_error: BaseException | None = None

    def record_finalize_error(error: BaseException, detail: str) -> None:
        nonlocal finalize_error
        if primary_error is not None:
            primary_error.add_note(detail)
        elif finalize_error is None:
            error.add_note(detail)
            finalize_error = error
        else:
            finalize_error.add_note(detail)

    for owner, prefix, initial_signature in reversed(opened_directories):
        display_path = str(run_root.joinpath(*prefix))
        try:
            final_signature = _stat_signature(os.fstat(owner.descriptor))
        except OSError as exc:
            error = ReplayError(
                "ARTIFACT_ROOT_CHANGED",
                f"{display_path}: final fstat failed: {exc}",
            )
            record_finalize_error(error, str(error))
        except BaseException as exc:
            record_finalize_error(
                exc,
                (
                    f"artifact-root finalization validation failed for "
                    f"{display_path}: {type(exc).__name__}: {exc}"
                ),
            )
        else:
            if final_signature != initial_signature:
                error = ReplayError(
                    "ARTIFACT_ROOT_CHANGED",
                    f"{display_path}: final signature changed",
                )
                record_finalize_error(error, str(error))
        close_error = owner.close()
        if isinstance(close_error, OSError):
            error = ReplayError(
                "ARTIFACT_ROOT_CHANGED",
                f"{display_path}: descriptor close failed: {close_error}",
            )
            record_finalize_error(error, str(error))
        elif close_error is not None:
            record_finalize_error(
                close_error,
                (
                    f"artifact-root descriptor close failed for "
                    f"{display_path}: {type(close_error).__name__}: {close_error}"
                ),
            )

    if primary_error is not None:
        raise primary_error
    if finalize_error is not None:
        raise finalize_error
    return observed


def _verify_artifact_root_closure(
    run_root: Path,
    manifest: dict[str, object],
    *,
    expected_root_signature: tuple[int, ...] | None = None,
) -> None:
    expected: dict[str, str] = {}
    for index, raw_entry in enumerate(
        _array(manifest["entries"], "artifact_root_manifest.entries")
    ):
        entry = _object(raw_entry, f"artifact_root_manifest.entries[{index}]")
        path = _text(
            entry["path"],
            f"artifact_root_manifest.entries[{index}].path",
        )
        expected[path] = _text(
            entry["type"],
            f"artifact_root_manifest.entries[{index}].type",
        )
    expected[TERMINAL_RECEIPT_PATH] = "regular_file"
    observed = _artifact_root_entries(
        run_root,
        expected_root_signature=expected_root_signature,
    )
    if observed != expected:
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        type_mismatch = sorted(
            path
            for path in set(expected) & set(observed)
            if expected[path] != observed[path]
        )
        _fail(
            "ARTIFACT_ROOT_CLOSURE_MISMATCH",
            f"missing={missing!r}; extra={extra!r}; type_mismatch={type_mismatch!r}",
        )


def stable_read(path: Path | str, label: str) -> tuple[bytes, dict[str, object]]:
    """Read and hash one regular file through one unchanged descriptor."""

    absolute = _absolute(path)
    descriptor = _open_absolute_regular_no_symlinks(
        absolute,
        error_code="ARTIFACT_OPEN_FAILED",
    )
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            _fail("ARTIFACT_NOT_REGULAR", label)
        if before.st_size < 0 or before.st_size > MAX_ARTIFACT_BYTES:
            _fail("ARTIFACT_SIZE_REJECTED", label)
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(1 << 20, remaining))
            if not chunk:
                _fail("ARTIFACT_CHANGED", f"{label}: truncated during read")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            _fail("ARTIFACT_CHANGED", f"{label}: grew during read")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if _stat_signature(before) != _stat_signature(after):
        _fail("ARTIFACT_CHANGED", f"{label}: descriptor identity drift")
    raw = b"".join(chunks)
    return raw, {
        "path": str(absolute),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _write_exclusive(path: Path | str, raw: bytes) -> None:
    absolute = _absolute(path)
    _reject_symlink_chain(absolute.parent)
    _reject_symlink_chain(absolute, leaf_may_be_missing=True)
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(absolute, flags, 0o600)
    except FileExistsError:
        _fail("NO_OVERWRITE_COLLISION", str(absolute))
    except OSError as exc:
        _fail("OUTPUT_OPEN_FAILED", str(exc))
    created = os.fstat(descriptor)
    completed = False
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                _fail("OUTPUT_WRITE_FAILED", str(absolute))
            view = view[written:]
        os.fsync(descriptor)
        completed = True
    finally:
        os.close(descriptor)
        if not completed:
            try:
                observed = os.lstat(absolute)
                if (
                    stat.S_ISREG(observed.st_mode)
                    and observed.st_dev == created.st_dev
                    and observed.st_ino == created.st_ino
                ):
                    os.unlink(absolute)
            except FileNotFoundError:
                pass


def _object(value: object, label: str) -> dict[str, Any]:
    if type(value) is not dict:
        _fail("TYPE_OBJECT_REQUIRED", label)
    return value


def _array(value: object, label: str) -> list[Any]:
    if type(value) is not list:
        _fail("TYPE_ARRAY_REQUIRED", label)
    return value


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value:
        _fail("TYPE_TEXT_REQUIRED", label)
    return value


def _integer(value: object, label: str, *, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        suffix = "" if minimum is None else f" >= {minimum}"
        _fail("TYPE_INTEGER_REQUIRED", f"{label}{suffix}")
    return value


def _exact_keys(value: object, expected: set[str], label: str) -> dict[str, Any]:
    record = _object(value, label)
    if set(record) != expected:
        _fail(
            "KEY_SET_MISMATCH",
            f"{label}: expected {sorted(expected)!r}, got {sorted(record)!r}",
        )
    return record


def _protocol_identity() -> dict[str, str]:
    return {
        "cohort": PROTOCOL_COHORT,
        "class_allocation_profile": CLASS_ALLOCATION_PROFILE,
        "antecedent_schema": V3_ANTECEDENT_SCHEMA,
        "config_payload_schema": V3_CONFIG_PAYLOAD_SCHEMA,
        "receipt_payload_schema": V3_RECEIPT_PAYLOAD_SCHEMA,
        "replay_receipt_schema": V3_REPLAY_RECEIPT_SCHEMA,
        "project_lock_sha256": EXPECTED_PROJECT_LOCK_SHA256,
    }


def _authority_boundary() -> dict[str, object]:
    return {
        "artifact_status": "research_only_local_d6",
        "proves_whole_witness": False,
        "changes_lower_bound": False,
        "changes_upper_bound": False,
        "may_emit_cut_or_rejection": False,
        "production_authority": False,
        "certified_exact_source_authority": False,
        "frozen_or_sealed_input_mutation": False,
    }


def _verify_authority_boundary(value: object, label: str) -> dict[str, Any]:
    expected = _authority_boundary()
    boundary = _exact_keys(value, set(expected), label)
    if boundary != expected or any(
        boundary[field] is not False
        for field in set(expected) - {"artifact_status"}
    ):
        _fail("AUTHORITY_BOUNDARY_INVALID", label)
    return boundary


def _verify_v3_protocol(value: object, label: str) -> dict[str, Any]:
    expected = _protocol_identity()
    if type(value) is not dict or set(value) != set(expected) or value != expected:
        _fail(
            "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
            f"{label}: expected the complete {PROTOCOL_COHORT} identity",
        )
    return value


def _ordered_class_counts(values: dict[str, int]) -> dict[str, int]:
    if set(values) != set(CLASS_ORDER):
        _fail("REPLAYER_INTERNAL_ERROR", "class ledger key set")
    return {class_name: values[class_name] for class_name in CLASS_ORDER}


def _class_transfer() -> dict[str, object]:
    return {
        "profile": CLASS_ALLOCATION_PROFILE,
        "moves": [
            {"from": "D6", "to": "D9", "class": "6B", "count": 1},
            {"from": "D9", "to": "D6", "class": "6G", "count": 1},
        ],
    }


def _class_ledger_profile_identity() -> dict[str, object]:
    global_counts = _ordered_class_counts(GLOBAL_CLASS_COUNTS)
    return {
        "class_order": list(CLASS_ORDER),
        "d6": {
            "before": {
                "class_counts": _ordered_class_counts(D6_BEFORE_CLASS_COUNTS),
                "totals": dict(D6_BEFORE_TOTALS),
            },
            "after": {
                "class_counts": _ordered_class_counts(D6_AFTER_CLASS_COUNTS),
                "totals": dict(D6_AFTER_TOTALS),
            },
            "modeled_state": "after",
        },
        "d9": {
            "before": {
                "class_counts": _ordered_class_counts(D9_BEFORE_CLASS_COUNTS),
                "totals": dict(D9_BEFORE_TOTALS),
            },
            "after": {
                "class_counts": _ordered_class_counts(D9_AFTER_CLASS_COUNTS),
                "totals": dict(D9_AFTER_TOTALS),
            },
            "role": "arithmetic_compensation_only_not_geometrically_modeled",
        },
        "global": {
            "before": global_counts,
            "after": dict(global_counts),
            "conserved": True,
        },
    }


def _allocation_totals(
    class_counts: dict[str, int],
    class_catalog: dict[str, dict[str, object]],
    *,
    label: str,
) -> dict[str, int]:
    totals = {"bodies": 0, "active_inputs": 0, "active_outputs": 0}
    for class_name, count in class_counts.items():
        if type(count) is not int or count < 0:
            _fail("REPLAYER_INTERNAL_ERROR", f"{label}.{class_name}")
        totals["bodies"] += count
        if count == 0:
            continue
        record = class_catalog.get(class_name)
        if record is None:
            _fail("ANTECEDENT_INPUT_INVALID", f"{label}.{class_name}")
        totals["active_inputs"] += count * _integer(
            record["input_count"],
            f"{label}.{class_name}.input_count",
            minimum=0,
        )
        totals["active_outputs"] += count * _integer(
            record["output_count"],
            f"{label}.{class_name}.output_count",
            minimum=0,
        )
    return totals


def _class_ledger(
    class_catalog: dict[str, dict[str, object]],
) -> dict[str, object]:
    state_specs = (
        ("d6.before", D6_BEFORE_CLASS_COUNTS, D6_BEFORE_TOTALS),
        ("d6.after", D6_AFTER_CLASS_COUNTS, D6_AFTER_TOTALS),
        ("d9.before", D9_BEFORE_CLASS_COUNTS, D9_BEFORE_TOTALS),
        ("d9.after", D9_AFTER_CLASS_COUNTS, D9_AFTER_TOTALS),
    )
    observed_totals: dict[str, dict[str, int]] = {}
    for label, counts, expected in state_specs:
        observed = _allocation_totals(counts, class_catalog, label=label)
        if observed != expected:
            _fail("ANTECEDENT_INPUT_INVALID", f"{label} totals drifted")
        observed_totals[label] = observed
    for class_name in CLASS_ORDER:
        before = (
            D6_BEFORE_CLASS_COUNTS[class_name]
            + D9_BEFORE_CLASS_COUNTS[class_name]
        )
        after = (
            D6_AFTER_CLASS_COUNTS[class_name]
            + D9_AFTER_CLASS_COUNTS[class_name]
        )
        if before != after:
            _fail("REPLAYER_INTERNAL_ERROR", f"class transfer {class_name}")
    return _class_ledger_profile_identity()


def _antecedent_cohort_keys(protocol_profile: str) -> set[str]:
    keys = {
        "schema",
        "claim_boundary",
        "benchmark_id",
        "attachment_scope",
        "local_bounds",
        "tiles",
        "poles",
        "protected_body_only_rect",
        "cycle",
        "class_counts",
        "class_catalog",
        "mode_catalog",
        "power_rule",
        "routing_patterns",
        "seed_hints",
        "seed_hint_policy",
        "expected_totals",
    }
    if protocol_profile == SWAP_V3_PROFILE:
        keys.update({"protocol", "class_transfer", "class_ledger"})
    elif protocol_profile != CLOSED_V2_PROFILE:
        _fail("ARTIFACT_PROTOCOL_COHORT_MISMATCH", protocol_profile)
    return keys


def _verify_antecedent_cohort_shape(
    value: object,
    *,
    protocol_profile: str,
    expected_protocol: object | None = None,
) -> dict[str, Any]:
    antecedent = _object(value, "antecedent")
    expected_keys = _antecedent_cohort_keys(protocol_profile)
    if set(antecedent) != expected_keys:
        _fail(
            "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
            (
                "antecedent key set does not match the selected cohort: "
                f"missing={sorted(expected_keys - set(antecedent))!r}; "
                f"extra={sorted(set(antecedent) - expected_keys)!r}"
            ),
        )
    expected_schema = (
        ANTECEDENT_SCHEMA
        if protocol_profile == CLOSED_V2_PROFILE
        else V3_ANTECEDENT_SCHEMA
    )
    if antecedent.get("schema") != expected_schema:
        _fail(
            "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
            "antecedent schema does not match receipt/config cohort",
        )
    if protocol_profile == SWAP_V3_PROFILE:
        protocol = _verify_v3_protocol(
            antecedent.get("protocol"),
            "antecedent.protocol",
        )
        if expected_protocol is not None and protocol != expected_protocol:
            _fail(
                "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
                "antecedent/config/receipt protocol identities differ",
            )
        if antecedent.get("class_transfer") != _class_transfer():
            _fail(
                "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
                "antecedent class-transfer profile identity differs",
            )
        if antecedent.get("class_ledger") != _class_ledger_profile_identity():
            _fail(
                "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
                "antecedent class-ledger profile identity differs",
            )
    return antecedent


def _profile_from_receipt_payload(payload: dict[str, Any]) -> str:
    schema = payload.get("schema")
    if schema == "w0_d6_receipt_payload_v1":
        _fail(
            "ROOT_CLOSURE_CONTRACT_MISSING",
            "historical v1 receipt has no exact artifact-root manifest",
        )
    if schema == CLOSED_V2_RECEIPT_PAYLOAD_SCHEMA:
        if "protocol" in payload:
            _fail(
                "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
                "closed-root v2 receipt must not carry a v3 protocol identity",
            )
        return CLOSED_V2_PROFILE
    if schema == V3_RECEIPT_PAYLOAD_SCHEMA:
        _verify_v3_protocol(payload.get("protocol"), "receipt.payload.protocol")
        return SWAP_V3_PROFILE
    _fail(
        "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
        f"unsupported receipt payload schema: {schema!r}",
    )


def _receipt_payload_cohort_keys(protocol_profile: str) -> set[str]:
    keys = {
        "schema",
        "status",
        "attachment_scope",
        "antecedent_sha256",
        "result_sha256",
        "configuration_sha256",
        "certificate_sha256",
        "identity_graph_sha256",
        "artifact_root_manifest",
        "claim_boundary",
        "replay",
    }
    if protocol_profile == SWAP_V3_PROFILE:
        keys.update({"protocol", "authority_boundary"})
    elif protocol_profile != CLOSED_V2_PROFILE:
        _fail("ARTIFACT_PROTOCOL_COHORT_MISMATCH", protocol_profile)
    return keys


def _verify_receipt_payload_cohort_shape(
    value: object,
    *,
    protocol_profile: str,
) -> dict[str, Any]:
    payload = _object(value, "receipt.payload")
    expected_keys = _receipt_payload_cohort_keys(protocol_profile)
    if set(payload) != expected_keys:
        _fail(
            "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
            (
                f"{protocol_profile} receipt payload does not select one complete cohort: "
                f"missing={sorted(expected_keys - set(payload))!r}; "
                f"extra={sorted(set(payload) - expected_keys)!r}"
            ),
        )
    expected_schema = (
        CLOSED_V2_RECEIPT_PAYLOAD_SCHEMA
        if protocol_profile == CLOSED_V2_PROFILE
        else V3_RECEIPT_PAYLOAD_SCHEMA
    )
    if payload.get("schema") != expected_schema:
        _fail(
            "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
            f"receipt payload schema {payload.get('schema')!r} does not match {protocol_profile}",
        )
    if protocol_profile == SWAP_V3_PROFILE:
        _verify_v3_protocol(payload.get("protocol"), "receipt.payload.protocol")
    return payload


def _sha256(value: object, label: str) -> str:
    if type(value) is not str or SHA256_RE.fullmatch(value) is None:
        _fail("SHA256_INVALID", label)
    return value


def _xy(value: object, label: str) -> tuple[int, int]:
    if type(value) is list and len(value) == 2:
        return _integer(value[0], f"{label}[0]"), _integer(value[1], f"{label}[1]")
    if type(value) is dict and set(value) == {"x", "y"}:
        return _integer(value["x"], f"{label}.x"), _integer(value["y"], f"{label}.y")
    _fail("COORDINATE_INVALID", label)


def _body_size(value: object, label: str) -> tuple[int, int]:
    if type(value) is list and len(value) == 2:
        return (
            _integer(value[0], f"{label}[0]", minimum=1),
            _integer(value[1], f"{label}[1]", minimum=1),
        )
    if type(value) is dict and set(value) == {"width", "height"}:
        return (
            _integer(value["width"], f"{label}.width", minimum=1),
            _integer(value["height"], f"{label}.height", minimum=1),
        )
    _fail("BODY_SIZE_INVALID", label)


def _bounds(value: object, label: str) -> tuple[int, int, int, int]:
    if type(value) is list and len(value) == 4:
        x_min, y_min, x_max, y_max = (
            _integer(value[0], f"{label}[0]"),
            _integer(value[1], f"{label}[1]"),
            _integer(value[2], f"{label}[2]"),
            _integer(value[3], f"{label}[3]"),
        )
    elif type(value) is dict and set(value) == {"x_min", "y_min", "x_max", "y_max"}:
        x_min = _integer(value["x_min"], f"{label}.x_min")
        y_min = _integer(value["y_min"], f"{label}.y_min")
        x_max = _integer(value["x_max"], f"{label}.x_max")
        y_max = _integer(value["y_max"], f"{label}.y_max")
    else:
        _fail("BOUNDS_INVALID", label)
    if x_min > x_max or y_min > y_max:
        _fail("BOUNDS_INVALID", f"{label}: reversed")
    return x_min, y_min, x_max, y_max


def _direction(value: object, label: str) -> str:
    if value not in DIRECTIONS:
        _fail("DIRECTION_INVALID", label)
    return value


def _identity(value: object, label: str) -> dict[str, object]:
    record = _exact_keys(value, {"path", "sha256", "size_bytes"}, label)
    path = _text(record["path"], f"{label}.path")
    if not Path(path).is_absolute():
        _fail("IDENTITY_PATH_INVALID", label)
    return {
        "path": path,
        "sha256": _sha256(record["sha256"], f"{label}.sha256"),
        "size_bytes": _integer(record["size_bytes"], f"{label}.size_bytes", minimum=0),
    }


def _identity_matches(observed: dict[str, object], expected: object, label: str) -> None:
    if observed != _identity(expected, label):
        _fail("IDENTITY_MISMATCH", label)


def _load_json_identity(
    identity: object,
    label: str,
    *,
    require_canonical: bool,
) -> tuple[bytes, object, dict[str, object]]:
    expected = _identity(identity, label)
    raw, observed = stable_read(expected["path"], label)
    if observed != expected:
        _fail("IDENTITY_MISMATCH", label)
    return raw, strict_json_loads(raw, label, require_canonical=require_canonical), observed


def _is_below(root: Path, path: str) -> bool:
    try:
        return os.path.commonpath((str(root), str(_absolute(path)))) == str(root)
    except ValueError:
        return False


def _graph_sha256(artifacts: dict[str, object]) -> str:
    graph = {"schema": "artifact_identity_graph_v1", "artifacts": artifacts}
    return hashlib.sha256(canonical_json_bytes(graph)).hexdigest()


def _contains_scalar(value: object, target: object) -> bool:
    if value == target:
        return True
    if type(value) is list:
        return any(_contains_scalar(item, target) for item in value)
    if type(value) is dict:
        return any(_contains_scalar(item, target) for item in value.values())
    return False


def _verify_process_contract(value: object, label: str) -> dict[str, object]:
    contract = _exact_keys(
        value,
        {"schema", "required_argv_flags", "observed"},
        label,
    )
    if contract["schema"] != ISOLATED_PYTHON_PROCESS_SCHEMA:
        _fail("PYTHON_PROCESS_CONTRACT_INVALID", f"{label}.schema")
    required_flags = _array(
        contract["required_argv_flags"],
        f"{label}.required_argv_flags",
    )
    if required_flags != ["-I", "-B"]:
        _fail("PYTHON_PROCESS_CONTRACT_INVALID", f"{label}.required_argv_flags")
    observed = _exact_keys(
        contract["observed"],
        {
            "isolated",
            "ignore_environment",
            "no_user_site",
            "safe_path",
            "dont_write_bytecode_flag",
            "dont_write_bytecode_runtime",
        },
        f"{label}.observed",
    )
    expected = {
        "isolated": 1,
        "ignore_environment": 1,
        "no_user_site": 1,
        "safe_path": True,
        "dont_write_bytecode_flag": 1,
        "dont_write_bytecode_runtime": True,
    }
    if observed != expected:
        _fail("PYTHON_PROCESS_CONTRACT_INVALID", f"{label}.observed")
    return {
        "schema": ISOLATED_PYTHON_PROCESS_SCHEMA,
        "required_argv_flags": ["-I", "-B"],
        "observed": observed,
    }


def _verify_config(
    config: object,
    *,
    protocol_profile: str,
    run_root: Path,
    config_identity: dict[str, object],
    artifacts: dict[str, dict[str, object]],
    self_identity: dict[str, object],
) -> dict[str, Any]:
    envelope = _exact_keys(config, {"schema", "experiment_id", "payload"}, "config")
    if envelope["schema"] != CONFIG_SCHEMA or envelope["experiment_id"] != "w0_power_cycle_domino_d6":
        _fail("CONFIG_ENVELOPE_INVALID", "schema or experiment_id")
    expected_payload_keys = {
        "schema",
        "attachment_scope",
        "solver",
        "runtime",
        "process_contract",
        "git",
        "inputs",
        "sources",
        "antecedent",
        "rejected_producer_claims",
        "authority_boundary",
        "replay",
    }
    if protocol_profile == SWAP_V3_PROFILE:
        expected_payload_keys.add("protocol")
    elif protocol_profile != CLOSED_V2_PROFILE:
        _fail("ARTIFACT_PROTOCOL_COHORT_MISMATCH", protocol_profile)
    raw_payload = _object(envelope["payload"], "config.payload")
    expected_schema = (
        CLOSED_V2_CONFIG_PAYLOAD_SCHEMA
        if protocol_profile == CLOSED_V2_PROFILE
        else V3_CONFIG_PAYLOAD_SCHEMA
    )
    if raw_payload.get("schema") != expected_schema:
        _fail(
            "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
            f"config payload schema {raw_payload.get('schema')!r} does not match {protocol_profile}",
        )
    if set(raw_payload) != expected_payload_keys:
        _fail(
            "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
            (
                f"{protocol_profile} config payload does not select one complete cohort: "
                f"missing={sorted(expected_payload_keys - set(raw_payload))!r}; "
                f"extra={sorted(set(raw_payload) - expected_payload_keys)!r}"
            ),
        )
    payload = _exact_keys(raw_payload, expected_payload_keys, "config.payload")
    if protocol_profile == SWAP_V3_PROFILE:
        _verify_v3_protocol(payload["protocol"], "config.payload.protocol")
    attachment_scope = _text(
        payload["attachment_scope"],
        "config.payload.attachment_scope",
    )
    if (
        protocol_profile == SWAP_V3_PROFILE
        and attachment_scope != "all_legal_d6_slots"
    ):
        _fail(
            "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
            "v3 requires attachment_scope=all_legal_d6_slots",
        )
    solver = _exact_keys(
        payload["solver"],
        {"workers", "random_seed", "max_time_seconds"},
        "config.payload.solver",
    )
    _integer(solver["workers"], "solver.workers", minimum=1)
    _integer(solver["random_seed"], "solver.random_seed", minimum=0)
    _integer(solver["max_time_seconds"], "solver.max_time_seconds", minimum=1)
    runtime = _exact_keys(
        payload["runtime"],
        {
            "python_version",
            "python_implementation",
            "python_executable",
            "ortools_distribution_version",
        },
        "config.payload.runtime",
    )
    for key, value in runtime.items():
        _text(value, f"config.payload.runtime.{key}")
    if not Path(str(runtime["python_executable"])).is_absolute():
        _fail("CONFIG_RUNTIME_INVALID", "python_executable must be absolute")
    _verify_process_contract(
        payload["process_contract"],
        "config.payload.process_contract",
    )
    git = _exact_keys(
        payload["git"],
        {"project_root", "head", "status_porcelain_v1", "clean"},
        "config.payload.git",
    )
    if (
        not Path(_text(git["project_root"], "git.project_root")).is_absolute()
        or type(git["head"]) is not str
        or re.fullmatch(r"[0-9a-f]{40}", git["head"]) is None
        or git["status_porcelain_v1"] != ""
        or git["clean"] is not True
    ):
        _fail("CONFIG_GIT_IDENTITY_INVALID", "clean HEAD is not pinned")

    expected_input_sha = {
        "strict_instance": "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
        "framework": "db6046cf598f9b5738b7f8950c91ea31834e8214e7e07995175b71eb04bdbb89",
        "seed": "18c72669105f486bf54a2665bd74d1ff952ce2eeb39b28a7b30d5ce8d5d2f5f1",
    }
    inputs = _exact_keys(payload["inputs"], set(expected_input_sha), "config.payload.inputs")
    for name, expected_sha in expected_input_sha.items():
        pair = _exact_keys(inputs[name], {"external", "run_copy"}, f"inputs.{name}")
        external = _identity(pair["external"], f"inputs.{name}.external")
        run_copy = _identity(pair["run_copy"], f"inputs.{name}.run_copy")
        receipt_identity = artifacts[f"inputs.{name}"]
        if run_copy != receipt_identity:
            _fail("CONFIG_ARTIFACT_BINDING_MISMATCH", f"inputs.{name}")
        if (
            external["sha256"] != expected_sha
            or run_copy["sha256"] != expected_sha
            or external["size_bytes"] != run_copy["size_bytes"]
        ):
            _fail("INPUT_AUTHORITY_HASH_MISMATCH", name)

    source_names = {"runner", "gate", "replayer", "common_contract"}
    sources = _exact_keys(payload["sources"], source_names, "config.payload.sources")
    for name in sorted(source_names):
        pair = _exact_keys(sources[name], {"working_tree", "run_copy"}, f"sources.{name}")
        working_tree = _identity(pair["working_tree"], f"sources.{name}.working_tree")
        run_copy = _identity(pair["run_copy"], f"sources.{name}.run_copy")
        if run_copy != artifacts[f"sources.{name}"]:
            _fail("CONFIG_ARTIFACT_BINDING_MISMATCH", f"sources.{name}")
        if (
            working_tree["sha256"] != run_copy["sha256"]
            or working_tree["size_bytes"] != run_copy["size_bytes"]
        ):
            _fail("SOURCE_COPY_MISMATCH", name)
    pinned_replayer = _identity(
        _object(sources["replayer"], "sources.replayer")["run_copy"],
        "sources.replayer.run_copy",
    )
    if (
        _absolute(Path(__file__)) != _absolute(str(pinned_replayer["path"]))
        or self_identity["sha256"] != pinned_replayer["sha256"]
        or self_identity["size_bytes"] != pinned_replayer["size_bytes"]
    ):
        _fail("REPLAYER_SOURCE_MISMATCH", "executing source differs from pinned run copy")

    antecedent_identity = _identity(payload["antecedent"], "config.payload.antecedent")
    if antecedent_identity != artifacts["antecedent"]:
        _fail("CONFIG_ARTIFACT_BINDING_MISMATCH", "antecedent")
    legacy_digest = "295bfef9b2681193e3a9cc085c479a960f87de0131abfbdfacb676479bdb2aa5"
    rejected = _array(payload["rejected_producer_claims"], "rejected_producer_claims")
    if len(rejected) != 1:
        _fail("LEGACY_PRODUCER_CLAIM_NOT_REJECTED", "expected exactly one rejection record")
    rejection = _exact_keys(
        rejected[0],
        {
            "claim_path",
            "accepted_as_binding",
            "actual_seed_sha256",
            "reason",
            "claimed_sha256",
            "matches_known_unbound_claim",
        },
        "rejected_producer_claims[0]",
    )
    expected_rejection = {
        "claim_path": "seed.validation_summary.source_sha256",
        "accepted_as_binding": False,
        "actual_seed_sha256": expected_input_sha["seed"],
        "reason": (
            "producer-reported source identity is not an independent binding "
            "to the snapshotted seed bytes"
        ),
        "claimed_sha256": legacy_digest,
        "matches_known_unbound_claim": True,
    }
    if (
        rejection != expected_rejection
        or rejection["accepted_as_binding"] is not False
        or rejection["matches_known_unbound_claim"] is not True
    ):
        _fail("LEGACY_PRODUCER_CLAIM_NOT_REJECTED", legacy_digest)
    _verify_authority_boundary(
        payload["authority_boundary"],
        "config.payload.authority_boundary",
    )
    replay = _exact_keys(payload["replay"], {"argv_template"}, "config.payload.replay")
    argv_template = _array(replay["argv_template"], "config.payload.replay.argv_template")
    expected_argv = [
        "<python3>",
        "-I",
        "-B",
        str(pinned_replayer["path"]),
        "--run-root",
        str(run_root),
    ]
    if argv_template != expected_argv:
        _fail("REPLAY_TEMPLATE_INVALID", "config")
    if config_identity != artifacts["config"]:
        _fail("CONFIG_ARTIFACT_BINDING_MISMATCH", "config identity")
    return payload


def _verify_receipt_payload(
    payload_value: object,
    *,
    protocol_profile: str,
    graph_sha256: str,
    artifacts: dict[str, dict[str, object]],
    feasible_artifact_topology: bool,
) -> dict[str, Any]:
    payload = _verify_receipt_payload_cohort_shape(
        payload_value,
        protocol_profile=protocol_profile,
    )
    if protocol_profile == SWAP_V3_PROFILE:
        _verify_authority_boundary(
            payload["authority_boundary"],
            "receipt.payload.authority_boundary",
        )
    status_value = payload["status"]
    if status_value not in {"FEASIBLE", "INFEASIBLE", "UNKNOWN"}:
        _fail("STATUS_INVALID", "receipt.payload.status")
    feasible = status_value == "FEASIBLE"
    if feasible != feasible_artifact_topology:
        _fail(
            "ARTIFACT_STATUS_TOPOLOGY_MISMATCH",
            (
                f"status={status_value!r}; "
                f"feasible_artifact_topology={feasible_artifact_topology!r}"
            ),
        )
    if payload["identity_graph_sha256"] != graph_sha256:
        _fail("IDENTITY_GRAPH_HASH_MISMATCH", "receipt payload")
    if payload["antecedent_sha256"] != artifacts["antecedent"]["sha256"]:
        _fail("CROSS_HASH_MISMATCH", "antecedent")
    if payload["result_sha256"] != artifacts["result"]["sha256"]:
        _fail("CROSS_HASH_MISMATCH", "result")
    for label, field in (
        ("configuration", "configuration_sha256"),
        ("certificate", "certificate_sha256"),
    ):
        expected = artifacts[label]["sha256"] if feasible else None
        if payload[field] != expected:
            _fail("CROSS_HASH_MISMATCH", label)
    _text(payload["attachment_scope"], "receipt.payload.attachment_scope")
    _text(payload["claim_boundary"], "receipt.payload.claim_boundary")
    replay = _exact_keys(payload["replay"], {"argv_template"}, "receipt.payload.replay")
    argv_template = _array(replay["argv_template"], "receipt.payload.replay.argv_template")
    if not argv_template or any(type(item) is not str for item in argv_template):
        _fail("REPLAY_TEMPLATE_INVALID", "receipt")
    return payload


def verify_byte_graph(run_root_value: Path | str) -> dict[str, Any]:
    """Verify every producer byte before interpreting a D6 verdict."""

    replayer_process_contract = _require_isolated_python_process()
    run_root = _absolute(run_root_value)
    root_owner = _OwnedDescriptor(
        _open_absolute_directory_no_symlinks(
            run_root,
            error_code="ARTIFACT_ROOT_OPEN_FAILED",
        )
    )
    try:
        root_item = os.fstat(root_owner.descriptor)
        if not stat.S_ISDIR(root_item.st_mode):
            _fail("RUN_ROOT_INVALID", str(run_root))
        root_signature = _stat_signature(root_item)
    except OSError as exc:
        error = ReplayError("ARTIFACT_ROOT_OPEN_FAILED", f"{run_root}: {exc}")
        root_owner.close_preserving(error)
        raise error from exc
    except BaseException as exc:
        root_owner.close_preserving(exc)
        raise
    close_error = root_owner.close()
    if isinstance(close_error, OSError):
        _fail(
            "ARTIFACT_ROOT_OPEN_FAILED",
            f"{run_root}: descriptor close failed: {close_error}",
        )
    if close_error is not None:
        raise close_error
    receipt_raw, receipt_identity = stable_read(
        run_root / TERMINAL_RECEIPT_PATH,
        "receipt",
    )
    receipt = _exact_keys(
        strict_json_loads(receipt_raw, "receipt", require_canonical=True),
        {"schema", "experiment_id", "config_identity", "artifacts", "payload"},
        "receipt",
    )
    if receipt["schema"] != RECEIPT_SCHEMA or receipt["experiment_id"] != "w0_power_cycle_domino_d6":
        _fail("RECEIPT_ENVELOPE_INVALID", "schema or experiment_id")
    config_identity = _identity(receipt["config_identity"], "receipt.config_identity")
    if config_identity["path"] != str(run_root / "config.json"):
        _fail("ARTIFACT_PATH_INVALID", "config_identity")

    payload_preview = _object(receipt["payload"], "receipt.payload")
    protocol_profile = _profile_from_receipt_payload(payload_preview)
    payload_preview = _verify_receipt_payload_cohort_shape(
        payload_preview,
        protocol_profile=protocol_profile,
    )
    artifact_root_manifest = _validate_artifact_root_manifest(
        payload_preview["artifact_root_manifest"]
    )
    manifest_regular_paths = _validate_d6_manifest_layout(
        artifact_root_manifest
    )
    _verify_artifact_root_closure(
        run_root,
        artifact_root_manifest,
        expected_root_signature=root_signature,
    )

    raw_artifacts = _object(receipt["artifacts"], "receipt.artifacts")
    observed_labels = set(raw_artifacts)
    base_labels = set(BASE_ARTIFACT_RELATIVE_PATHS)
    feasible_labels = base_labels | set(FEASIBLE_ARTIFACT_RELATIVE_PATHS)
    if observed_labels == base_labels:
        feasible_artifact_topology = False
        expected_relative_paths = dict(BASE_ARTIFACT_RELATIVE_PATHS)
    elif observed_labels == feasible_labels:
        feasible_artifact_topology = True
        expected_relative_paths = {
            **BASE_ARTIFACT_RELATIVE_PATHS,
            **FEASIBLE_ARTIFACT_RELATIVE_PATHS,
        }
    else:
        _fail(
            "ARTIFACT_LABEL_SET_INVALID",
            (
                "receipt artifacts must select one status-free topology: "
                f"observed={sorted(observed_labels)!r}"
            ),
        )
    artifacts = {
        label: _identity(raw_artifacts[label], f"receipt.artifacts.{label}")
        for label in sorted(raw_artifacts)
    }
    if artifacts["config"] != config_identity:
        _fail("CONFIG_ARTIFACT_BINDING_MISMATCH", "receipt")
    paths = [item["path"] for item in artifacts.values()]
    if len(paths) != len(set(paths)):
        _fail("ARTIFACT_PATH_ALIAS", "duplicate receipt artifact path")
    artifact_relative_paths: set[str] = set()
    for label, identity in artifacts.items():
        identity_path = str(identity["path"])
        absolute_path = _absolute(identity_path)
        if identity_path != str(absolute_path) or not _is_below(
            run_root,
            identity_path,
        ):
            _fail("ARTIFACT_PATH_INVALID", f"{label}: outside run root")
        try:
            relative_path = absolute_path.relative_to(run_root).as_posix()
        except ValueError:
            _fail("ARTIFACT_PATH_INVALID", f"{label}: outside run root")
        expected_relative_path = expected_relative_paths[label]
        if relative_path != expected_relative_path:
            _fail(
                "ARTIFACT_FIXED_PATH_MISMATCH",
                (
                    f"{label}: expected {expected_relative_path!r}; "
                    f"observed {relative_path!r}"
                ),
            )
        artifact_relative_paths.add(relative_path)
    if artifact_relative_paths != manifest_regular_paths:
        _fail(
            "ARTIFACT_ROOT_ARTIFACT_SET_MISMATCH",
            (
                f"manifest_only={sorted(manifest_regular_paths - artifact_relative_paths)!r}; "
                f"artifacts_only={sorted(artifact_relative_paths - manifest_regular_paths)!r}"
            ),
        )

    snapshots: dict[str, dict[str, Any]] = {}
    for label, identity in artifacts.items():
        raw, observed = stable_read(str(identity["path"]), label)
        if observed != identity:
            _fail("IDENTITY_MISMATCH", label)
        snapshots[label] = {"raw": raw, "identity": observed}
    graph_sha = _graph_sha256({label: artifacts[label] for label in sorted(artifacts)})
    self_raw, self_identity = stable_read(Path(__file__), "executing replayer")
    del self_raw
    config = strict_json_loads(snapshots["config"]["raw"], "config", require_canonical=True)
    config_payload = _verify_config(
        config,
        protocol_profile=protocol_profile,
        run_root=run_root,
        config_identity=config_identity,
        artifacts=artifacts,
        self_identity=self_identity,
    )
    if protocol_profile == SWAP_V3_PROFILE:
        if config_payload["protocol"] != payload_preview.get("protocol"):
            _fail(
                "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
                "config and receipt protocol identities differ",
            )
    for label in ("antecedent", "result", "configuration", "certificate"):
        if label in snapshots:
            snapshots[label]["value"] = strict_json_loads(
                snapshots[label]["raw"],
                label,
                require_canonical=True,
            )
    for label in ("inputs.strict_instance", "inputs.framework", "inputs.seed"):
        snapshots[label]["value"] = strict_json_loads(
            snapshots[label]["raw"],
            label,
            require_canonical=False,
        )
    _verify_antecedent_cohort_shape(
        snapshots["antecedent"]["value"],
        protocol_profile=protocol_profile,
        expected_protocol=config_payload.get("protocol"),
    )
    receipt_payload = _verify_receipt_payload(
        receipt["payload"],
        protocol_profile=protocol_profile,
        graph_sha256=graph_sha,
        artifacts=artifacts,
        feasible_artifact_topology=feasible_artifact_topology,
    )
    if config_payload["attachment_scope"] != receipt_payload["attachment_scope"]:
        _fail("CROSS_FIELD_MISMATCH", "attachment_scope")
    if config_payload["replay"] != receipt_payload["replay"]:
        _fail("CROSS_FIELD_MISMATCH", "replay argv template")
    if protocol_profile == SWAP_V3_PROFILE:
        if (
            config_payload["authority_boundary"]
            != receipt_payload["authority_boundary"]
        ):
            _fail(
                "AUTHORITY_BOUNDARY_INVALID",
                "config and receipt authority boundaries differ",
            )
    _verify_artifact_root_closure(
        run_root,
        artifact_root_manifest,
        expected_root_signature=root_signature,
    )
    return {
        "run_root": run_root,
        "receipt_identity": receipt_identity,
        "receipt": receipt,
        "receipt_payload": receipt_payload,
        "protocol_profile": protocol_profile,
        "config": config,
        "config_payload": config_payload,
        "artifacts": artifacts,
        "snapshots": snapshots,
        "identity_graph_sha256": graph_sha,
        "self_identity": self_identity,
        "artifact_root_manifest": artifact_root_manifest,
        "artifact_root_signature": root_signature,
        "replayer_process_contract": replayer_process_contract,
    }


def _revalidate_verified_byte_graph(context: dict[str, Any]) -> None:
    receipt_raw, receipt_identity = stable_read(
        context["run_root"] / TERMINAL_RECEIPT_PATH,
        "receipt final revalidation",
    )
    del receipt_raw
    if receipt_identity != context["receipt_identity"]:
        _fail("ARTIFACT_CHANGED", "receipt changed during replay")
    for label, expected in context["artifacts"].items():
        raw, observed = stable_read(
            _text(expected["path"], f"artifacts.{label}.path"),
            f"{label} final revalidation",
        )
        del raw
        if observed != expected:
            _fail("ARTIFACT_CHANGED", f"{label} changed during replay")


def verify_result_bindings(context: dict[str, Any]) -> str:
    """Cross-check the receipt, result wrapper, and optional certificate files."""

    payload = context["receipt_payload"]
    artifacts = context["artifacts"]
    snapshots = context["snapshots"]
    result = _exact_keys(
        snapshots["result"]["value"],
        {
            "schema",
            "status",
            "antecedent_sha256",
            "configuration_sha256",
            "certificate_sha256",
            "claim_boundary",
            "gate_observation",
        },
        "result",
    )
    if result["schema"] != RESULT_SCHEMA:
        _fail("RESULT_INVALID", "schema")
    status_value = result["status"]
    if status_value not in {"FEASIBLE", "INFEASIBLE", "UNKNOWN"}:
        _fail("STATUS_INVALID", "result.status")
    status = str(status_value)
    if status != payload["status"]:
        _fail("CROSS_FIELD_MISMATCH", "result/receipt status")
    if result["antecedent_sha256"] != artifacts["antecedent"]["sha256"]:
        _fail("CROSS_HASH_MISMATCH", "result antecedent")
    feasible = status == "FEASIBLE"
    expected_configuration = artifacts["configuration"]["sha256"] if feasible else None
    expected_certificate = artifacts["certificate"]["sha256"] if feasible else None
    if result["configuration_sha256"] != expected_configuration:
        _fail("CROSS_HASH_MISMATCH", "result configuration")
    if result["certificate_sha256"] != expected_certificate:
        _fail("CROSS_HASH_MISMATCH", "result certificate")
    claim_boundary = _text(result["claim_boundary"], "result.claim_boundary")
    if claim_boundary != payload["claim_boundary"]:
        _fail("CROSS_FIELD_MISMATCH", "claim_boundary")
    expected_claim = {
        "FEASIBLE": "feasible_only_for_the_exact_local_d6_antecedent",
        "INFEASIBLE": "infeasible_only_for_the_exact_local_d6_antecedent",
        "UNKNOWN": "unknown_no_rejection_cut_or_global_conclusion",
    }[status]
    if claim_boundary != expected_claim:
        _fail("CLAIM_BOUNDARY_INVALID", status)

    observation = _object(result["gate_observation"], "result.gate_observation")
    observation_schema = observation.get("schema")
    if observation_schema == GATE_RESULT_SCHEMA:
        observation = _exact_keys(
            observation,
            {
                "schema",
                "status",
                "status_detail",
                "claim_boundary",
                "antecedent_sha256",
                "solver_statistics",
            },
            "result.gate_observation",
        )
        statistics = _exact_keys(
            observation["solver_statistics"],
            {
                "wall_time_ms",
                "num_conflicts",
                "num_branches",
                "response_stats",
                "workers",
                "random_seed",
                "max_time_ms",
            },
            "gate_observation.solver_statistics",
        )
        for name in ("wall_time_ms", "num_conflicts", "num_branches"):
            _integer(statistics[name], f"solver_statistics.{name}", minimum=0)
        _integer(statistics["workers"], "solver_statistics.workers", minimum=1)
        _integer(statistics["random_seed"], "solver_statistics.random_seed", minimum=0)
        _integer(statistics["max_time_ms"], "solver_statistics.max_time_ms", minimum=1)
        if type(statistics["response_stats"]) is not str:
            _fail("GATE_OBSERVATION_INVALID", "response_stats")
        solver_config = context["config_payload"]["solver"]
        if (
            statistics["workers"] != solver_config["workers"]
            or statistics["random_seed"] != solver_config["random_seed"]
            or statistics["max_time_ms"] != solver_config["max_time_seconds"] * 1000
        ):
            _fail("GATE_OBSERVATION_INVALID", "solver config binding")
    elif observation_schema == "w0_d6_gate_execution_observation_v1":
        observation = _exact_keys(
            observation,
            {
                "schema",
                "status",
                "status_detail",
                "claim_boundary",
                "solver_statistics",
            },
            "result.gate_observation",
        )
        if status != "UNKNOWN":
            _fail("GATE_OBSERVATION_INVALID", "execution failure cannot produce a verdict")
        if observation["solver_statistics"] != {}:
            _fail("GATE_OBSERVATION_INVALID", "execution failure statistics")
    else:
        _fail("GATE_OBSERVATION_INVALID", "schema")
    if observation["status"] != status:
        _fail("GATE_OBSERVATION_INVALID", "status")
    if observation_schema == GATE_RESULT_SCHEMA and observation["antecedent_sha256"] != artifacts["antecedent"]["sha256"]:
        _fail("CROSS_HASH_MISMATCH", "gate observation antecedent")
    _text(observation["status_detail"], "gate_observation.status_detail")
    if observation["claim_boundary"] != expected_claim:
        _fail("CLAIM_BOUNDARY_INVALID", "gate observation")

    if feasible:
        configuration = _object(snapshots["configuration"]["value"], "configuration")
        certificate = _exact_keys(
            snapshots["certificate"]["value"],
            {
                "schema",
                "antecedent_sha256",
                "configuration_sha256",
                "status",
                "claim_boundary",
            },
            "certificate",
        )
        if (
            certificate["schema"] != CERTIFICATE_SCHEMA
            or certificate["status"] != "FEASIBLE"
            or certificate["antecedent_sha256"] != artifacts["antecedent"]["sha256"]
            or certificate["configuration_sha256"] != artifacts["configuration"]["sha256"]
            or certificate["claim_boundary"] != expected_claim
        ):
            _fail("CERTIFICATE_BINDING_MISMATCH", "minimal local certificate")
        if configuration.get("antecedent_sha256") != artifacts["antecedent"]["sha256"]:
            _fail("CONFIGURATION_BINDING_MISMATCH", "antecedent")
    return status


def _rect_cells(anchor: tuple[int, int], width: int, height: int) -> set[tuple[int, int]]:
    return {
        (anchor[0] + dx, anchor[1] + dy)
        for dx in range(width)
        for dy in range(height)
    }


def _inside(cell: tuple[int, int], bounds: tuple[int, int, int, int]) -> bool:
    return bounds[0] <= cell[0] <= bounds[2] and bounds[1] <= cell[1] <= bounds[3]


def _positive_sum(value: object, label: str) -> int:
    record = _object(value, label)
    return sum(
        _integer(item, f"{label}.{key}", minimum=1)
        for key, item in record.items()
    )


def _rebuild_class_catalog(
    strict_instance: dict[str, Any],
    *,
    protocol_profile: str,
) -> dict[str, dict[str, object]]:
    selectors = {
        "3L": ("manufacturing_3x3", 1, 1),
        "3O3": ("manufacturing_3x3", 1, 3),
        "5L": ("manufacturing_5x5", 1, 1),
        "5O2": ("manufacturing_5x5", 1, 2),
        "6G": ("manufacturing_6x4", 3, 1),
        "6B": ("manufacturing_6x4", 5, 1),
    }
    required_counts = {
        "3L": 7,
        "3O3": 3,
        "5L": 2,
        "5O2": 2,
        "6G": 3 if protocol_profile == SWAP_V3_PROFILE else 2,
        "6B": 1,
    }
    if protocol_profile not in {CLOSED_V2_PROFILE, SWAP_V3_PROFILE}:
        _fail("ARTIFACT_PROTOCOL_COHORT_MISMATCH", protocol_profile)
    groups: list[dict[str, object]] = []
    for index, raw_group in enumerate(_array(strict_instance.get("operation_groups"), "strict.operation_groups")):
        group = _object(raw_group, f"strict.operation_groups[{index}]")
        group_id = _text(group.get("id"), f"strict.operation_groups[{index}].id")
        needs = _object(group.get("port_needs"), f"{group_id}.port_needs")
        groups.append(
            {
                "id": group_id,
                "template": _text(group.get("template"), f"{group_id}.template"),
                "count": _integer(group.get("count"), f"{group_id}.count", minimum=1),
                "input_count": _positive_sum(needs.get("inputs"), f"{group_id}.inputs"),
                "output_count": _positive_sum(needs.get("outputs"), f"{group_id}.outputs"),
            }
        )
    result: dict[str, dict[str, object]] = {}
    for name, (template, input_count, output_count) in selectors.items():
        matching = sorted(
            (
                group
                for group in groups
                if (
                    group["template"],
                    group["input_count"],
                    group["output_count"],
                )
                == (template, input_count, output_count)
            ),
            key=lambda group: str(group["id"]),
        )
        if sum(int(group["count"]) for group in matching) < required_counts[name]:
            _fail("ANTECEDENT_INPUT_INVALID", f"strict cannot supply class {name}")
        result[name] = {
            "template": template,
            "input_count": input_count,
            "output_count": output_count,
            "operation_group_ids": [str(group["id"]) for group in matching],
        }
    return result


def _rebuild_mode_catalog(strict_instance: dict[str, Any]) -> dict[str, list[dict[str, object]]]:
    templates = _object(strict_instance.get("facility_templates"), "strict.facility_templates")
    result: dict[str, list[dict[str, object]]] = {}
    for template_name in sorted(("manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4")):
        template = _object(templates.get(template_name), f"strict.facility_templates.{template_name}")
        if template.get("placement_rule") != "any_body_in_grid" or template.get("requires_power") is not True:
            _fail("ANTECEDENT_INPUT_INVALID", f"{template_name} placement/power")
        modes: list[dict[str, object]] = []
        seen_modes: set[str] = set()
        for mode_index, raw_mode in enumerate(_array(template.get("modes"), f"{template_name}.modes")):
            mode = _object(raw_mode, f"{template_name}.modes[{mode_index}]")
            mode_id = _text(mode.get("id"), f"{template_name}.modes[{mode_index}].id")
            if mode_id in seen_modes:
                _fail("ANTECEDENT_INPUT_INVALID", f"duplicate mode {template_name}.{mode_id}")
            seen_modes.add(mode_id)
            width, height = _body_size(mode.get("body"), f"{template_name}.{mode_id}.body")
            ports: list[dict[str, object]] = []
            seen_ports: set[str] = set()
            for port_index, raw_port in enumerate(
                _array(mode.get("ports"), f"{template_name}.{mode_id}.ports")
            ):
                port = _object(raw_port, f"{template_name}.{mode_id}.ports[{port_index}]")
                port_id = _text(port.get("id"), f"{template_name}.{mode_id}.ports[{port_index}].id")
                if port_id in seen_ports or port.get("kind") not in {"input", "output"}:
                    _fail("ANTECEDENT_INPUT_INVALID", f"{template_name}.{mode_id}.{port_id}")
                seen_ports.add(port_id)
                body_cell = _xy(port.get("body_cell"), f"{template_name}.{mode_id}.{port_id}.body_cell")
                if not (0 <= body_cell[0] < width and 0 <= body_cell[1] < height):
                    _fail("ANTECEDENT_INPUT_INVALID", f"{template_name}.{mode_id}.{port_id} body cell")
                direction = _direction(
                    port.get("direction"),
                    f"{template_name}.{mode_id}.{port_id}.direction",
                )
                ports.append(
                    {
                        "id": port_id,
                        "kind": str(port["kind"]),
                        "body_cell": [body_cell[0], body_cell[1]],
                        "direction": direction,
                    }
                )
            modes.append(
                {
                    "id": mode_id,
                    "body": {"width": width, "height": height},
                    "ports": sorted(ports, key=lambda port: str(port["id"])),
                }
            )
        result[template_name] = sorted(modes, key=lambda mode: str(mode["id"]))
    return result


def _rebuild_routing_patterns() -> dict[str, object]:
    ground: list[dict[str, object]] = []
    for d_in in DIRECTIONS:
        for d_out in DIRECTIONS:
            if d_out != d_in:
                ground.append(
                    {
                        "name": f"belt:{d_in}>{d_out}",
                        "component": "belt",
                        "in_dirs": [d_in],
                        "out_dirs": [d_out],
                    }
                )
    for d_in in DIRECTIONS:
        remaining = [direction for direction in DIRECTIONS if direction != d_in]
        for degree in (2, 3):
            for outputs in combinations(remaining, degree):
                ordered = [direction for direction in DIRECTIONS if direction in outputs]
                ground.append(
                    {
                        "name": f"splitter:{d_in}>{'+'.join(ordered)}",
                        "component": "splitter",
                        "in_dirs": [d_in],
                        "out_dirs": ordered,
                    }
                )
    for d_out in DIRECTIONS:
        remaining = [direction for direction in DIRECTIONS if direction != d_out]
        for degree in (2, 3):
            for inputs in combinations(remaining, degree):
                ordered = [direction for direction in DIRECTIONS if direction in inputs]
                ground.append(
                    {
                        "name": f"merger:{'+'.join(ordered)}>{d_out}",
                        "component": "merger",
                        "in_dirs": ordered,
                        "out_dirs": [d_out],
                    }
                )
    elevated = [
        {
            "name": f"elevated:{d_in}>{OPPOSITE[d_in]}",
            "component": "elevated_straight",
            "in_dirs": [d_in],
            "out_dirs": [OPPOSITE[d_in]],
        }
        for d_in in DIRECTIONS
    ]
    if len(ground) != 44 or len(elevated) != 4:
        _fail("REPLAYER_INTERNAL_ERROR", "routing enumeration")
    return {
        "ground": ground,
        "elevated": elevated,
        "crossing": "perpendicular_ground_and_elevated_straights_without_transfer",
    }


def _validate_rebuild_authorities(
    strict_instance: dict[str, Any],
    framework: dict[str, Any],
    class_catalog: dict[str, dict[str, object]],
    *,
    protocol_profile: str,
) -> None:
    grid = _object(strict_instance.get("grid"), "strict.grid")
    if (grid.get("width"), grid.get("height")) != (70, 70):
        _fail("ANTECEDENT_INPUT_INVALID", "strict grid")
    coordinate = _object(strict_instance.get("coordinate_system"), "strict.coordinate_system")
    if coordinate != {
        "origin": "southwest",
        "indexing": "zero_based",
        "x_positive": "east",
        "y_positive": "north",
        "directions": list(DIRECTIONS),
    }:
        _fail("ANTECEDENT_INPUT_INVALID", "strict coordinate system")
    routing = _object(strict_instance.get("routing"), "strict.routing")
    expected_routing = {
        "component_cells_must_avoid_bodies": True,
        "crossing": "two_perpendicular_straight_channels_without_transfer",
        "throughput_in_scope": False,
        "terminal_input_requires_component_output": "opposite_terminal_direction",
        "terminal_output_requires_component_input": "opposite_terminal_direction",
    }
    if any(routing.get(key) != value for key, value in expected_routing.items()):
        _fail("ANTECEDENT_INPUT_INVALID", "strict routing")
    if framework.get("grid") != [70, 70]:
        _fail("ANTECEDENT_INPUT_INVALID", "framework grid")
    if _object(framework.get("routing_macrocells"), "framework.routing_macrocells").get("D6") != [
        [1, 2],
        [2, 2],
    ]:
        _fail("ANTECEDENT_INPUT_INVALID", "framework D6")
    tile_seed = _object(framework.get("tile_type_count_seed"), "framework.tile_type_count_seed")
    if tile_seed.get("1,2") != [5, 3, 1] or tile_seed.get("2,2") != [5, 1, 2]:
        _fail("ANTECEDENT_INPUT_INVALID", "framework D6 type counts")
    required_counts = {"3L": 7, "3O3": 3, "5L": 2, "5O2": 2, "6G": 2, "6B": 1}
    allocations = _object(
        framework.get("macrocell_class_allocation_seed"),
        "framework.macrocell_class_allocation_seed",
    )
    if allocations.get("D6") != required_counts:
        _fail("ANTECEDENT_INPUT_INVALID", "framework class allocation")
    classes = _object(framework.get("operation_classes"), "framework.operation_classes")
    if protocol_profile == SWAP_V3_PROFILE:
        if allocations.get("D9") != {
            "3L": 18,
            "5L": 3,
            "6G": 3,
        }:
            _fail("ANTECEDENT_INPUT_INVALID", "framework D9 class allocation")
        expected_macrocell_names = {f"D{index}" for index in range(1, 13)}
        if set(allocations) != expected_macrocell_names:
            _fail(
                "ANTECEDENT_INPUT_INVALID",
                "framework macrocell allocation row set",
            )
        allocation_sum = {class_name: 0 for class_name in CLASS_ORDER}
        for macrocell_name in sorted(allocations):
            row = _object(
                allocations[macrocell_name],
                f"framework.macrocell_class_allocation_seed.{macrocell_name}",
            )
            if not row:
                _fail(
                    "ANTECEDENT_INPUT_INVALID",
                    f"empty framework allocation row {macrocell_name}",
                )
            for class_name, raw_count in row.items():
                if class_name not in allocation_sum:
                    _fail(
                        "ANTECEDENT_INPUT_INVALID",
                        f"unknown framework class {class_name}",
                    )
                allocation_sum[class_name] += _integer(
                    raw_count,
                    f"framework.macrocell_class_allocation_seed.{macrocell_name}.{class_name}",
                    minimum=1,
                )
        if allocation_sum != GLOBAL_CLASS_COUNTS:
            _fail(
                "ANTECEDENT_INPUT_INVALID",
                "framework macrocell allocation global sum",
            )
        observed_global_counts = {
            class_name: _integer(
                _object(
                    classes.get(class_name),
                    f"framework.operation_classes.{class_name}",
                ).get("count"),
                f"framework.operation_classes.{class_name}.count",
                minimum=0,
            )
            for class_name in CLASS_ORDER
        }
        if observed_global_counts != GLOBAL_CLASS_COUNTS:
            _fail("ANTECEDENT_INPUT_INVALID", "framework global class ledger")
    elif protocol_profile != CLOSED_V2_PROFILE:
        _fail("ARTIFACT_PROTOCOL_COHORT_MISMATCH", protocol_profile)
    size_by_template = {
        "manufacturing_3x3": "3x3",
        "manufacturing_5x5": "5x5",
        "manufacturing_6x4": "6x4 or 4x6",
    }
    for name, derived in class_catalog.items():
        item = _object(classes.get(name), f"framework.operation_classes.{name}")
        if (
            item.get("size") != size_by_template[str(derived["template"])]
            or item.get("need") != [derived["input_count"], derived["output_count"]]
        ):
            _fail("ANTECEDENT_INPUT_INVALID", f"framework class {name}")
    protected = _object(framework.get("protected_rectangle"), "framework.protected_rectangle")
    if (
        protected.get("anchor") != [29, 28]
        or protected.get("size") != [6, 7]
        or protected.get("body_only") is not True
    ):
        _fail("ANTECEDENT_INPUT_INVALID", "protected rectangle")
    cycle = _object(framework.get("directed_cycle"), "framework.directed_cycle")
    if {"from": [2, 29], "to": [68, 29], "direction": "E"} not in _array(
        cycle.get("segments"),
        "framework.directed_cycle.segments",
    ):
        _fail("ANTECEDENT_INPUT_INVALID", "eastbound cycle segment")
    expected_rule = (
        "output branches enter distinct noncorner cells by a legal merger; input branches leave distinct "
        "noncorner cells by a legal splitter; no cell serves both roles"
    )
    if cycle.get("attachment_rule") != expected_rule:
        _fail("ANTECEDENT_INPUT_INVALID", "cycle attachment rule")


def _rebuild_fixed(
    strict_instance: dict[str, Any],
    framework: dict[str, Any],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    templates = _object(strict_instance.get("facility_templates"), "strict.facility_templates")
    pole = _object(templates.get("power_pole"), "strict.facility_templates.power_pole")
    modes = _array(pole.get("modes"), "power_pole.modes")
    if len(modes) != 1:
        _fail("ANTECEDENT_INPUT_INVALID", "power pole modes")
    mode = _object(modes[0], "power_pole.modes[0]")
    if mode.get("id") != "fixed" or _body_size(mode.get("body"), "power pole body") != (2, 2):
        _fail("ANTECEDENT_INPUT_INVALID", "power pole body")
    if mode.get("ports") != []:
        _fail("ANTECEDENT_INPUT_INVALID", "power pole ports")
    power_cells = _object(framework.get("power_cells"), "framework.power_cells")
    if (
        power_cells.get("ordinary_pole_local_anchor") != [6, 6]
        or power_cells.get("protected_cell") != [2, 2]
        or power_cells.get("protected_pole_local_anchor") != [7, 7]
    ):
        _fail("ANTECEDENT_INPUT_INVALID", "framework pole geometry")
    poles: list[dict[str, object]] = [
        {"tile": [1, 2], "anchor": [20, 34], "size": [2, 2]},
        {"tile": [2, 2], "anchor": [35, 35], "size": [2, 2]},
    ]
    strict_power = _object(strict_instance.get("power"), "strict.power")
    offsets = _exact_keys(
        strict_power.get("coverage_from_pole_anchor"),
        {"x_min_offset", "x_max_offset", "y_min_offset", "y_max_offset"},
        "strict.power.coverage_from_pole_anchor",
    )
    power_rule: dict[str, object] = {
        "required_rule": _text(strict_power.get("required_rule"), "strict.power.required_rule"),
        "pole_template": _text(strict_power.get("pole_template"), "strict.power.pole_template"),
        "coverage_offsets": {
            key: _integer(offsets[key], f"strict.power.coverage_offsets.{key}")
            for key in ("x_min_offset", "x_max_offset", "y_min_offset", "y_max_offset")
        },
    }
    if (
        power_rule["required_rule"] != "at_least_one_body_cell_covered"
        or power_rule["pole_template"] != "power_pole"
    ):
        _fail("ANTECEDENT_INPUT_INVALID", "strict power rule")
    return poles, power_rule


def _rebuild_seed(
    seed: dict[str, Any],
    power_rule: dict[str, object],
    attachment_scope: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    tile_bounds = {(1, 2): (14, 28, 27, 41), (2, 2): (28, 28, 41, 41)}
    pole_by_tile = {(1, 2): (20, 34), (2, 2): (35, 35)}
    protected = _rect_cells((29, 28), 6, 7)
    cycle = {(x, 29) for x in range(14, 42)}
    poles = _rect_cells((20, 34), 2, 2) | _rect_cells((35, 35), 2, 2)
    offsets = _object(power_rule["coverage_offsets"], "power_rule.coverage_offsets")
    occupied: set[tuple[int, int]] = set()
    selected: list[dict[str, object]] = []
    for index, raw in enumerate(_array(seed.get("manufacturing_placements"), "seed.manufacturing_placements")):
        placement = _object(raw, f"seed.manufacturing_placements[{index}]")
        tile = _xy(placement.get("tile"), f"seed.manufacturing_placements[{index}].tile")
        if tile not in tile_bounds:
            continue
        type_code = _integer(placement.get("type"), f"seed.manufacturing_placements[{index}].type")
        anchor = _xy(placement.get("anchor"), f"seed.manufacturing_placements[{index}].anchor")
        size = _body_size(placement.get("size"), f"seed.manufacturing_placements[{index}].size")
        if size not in {3: {(3, 3)}, 5: {(5, 5)}, 6: {(6, 4), (4, 6)}}.get(type_code, set()):
            _fail("ANTECEDENT_INPUT_INVALID", f"seed placement {index} type/size")
        cells = _rect_cells(anchor, *size)
        if (
            any(not _inside(cell, tile_bounds[tile]) for cell in cells)
            or cells & (protected | cycle | poles | occupied)
        ):
            _fail("ANTECEDENT_INPUT_INVALID", f"seed placement {index} geometry")
        pole_x, pole_y = pole_by_tile[tile]
        coverage = {
            (x, y)
            for x in range(
                pole_x + _integer(offsets["x_min_offset"], "x_min_offset"),
                pole_x + _integer(offsets["x_max_offset"], "x_max_offset") + 1,
            )
            for y in range(
                pole_y + _integer(offsets["y_min_offset"], "y_min_offset"),
                pole_y + _integer(offsets["y_max_offset"], "y_max_offset") + 1,
            )
        }
        if not cells & coverage:
            _fail("ANTECEDENT_INPUT_INVALID", f"seed placement {index} power")
        occupied.update(cells)
        selected.append(
            {
                "tile": [tile[0], tile[1]],
                "type": type_code,
                "anchor": [anchor[0], anchor[1]],
                "size": [size[0], size[1]],
            }
        )
    selected.sort(
        key=lambda item: (
            item["tile"],
            item["type"],
            item["anchor"],
            item["size"],
        )
    )
    expected_counts = {
        (1, 2): {3: 5, 5: 3, 6: 1},
        (2, 2): {3: 5, 5: 1, 6: 2},
    }
    if len(selected) != 17:
        _fail("ANTECEDENT_INPUT_INVALID", "seed D6 body count")
    for tile, counts in expected_counts.items():
        for type_code, expected in counts.items():
            actual = sum(
                item["tile"] == [tile[0], tile[1]] and item["type"] == type_code
                for item in selected
            )
            if actual != expected:
                _fail("ANTECEDENT_INPUT_INVALID", f"seed type count {tile}:{type_code}")

    if attachment_scope == "seed_narrow":
        slots_by_tile = _object(
            seed.get("eligible_attachment_slots_by_tile"),
            "seed.eligible_attachment_slots_by_tile",
        )
        observed: list[dict[str, object]] = []
        for tile in ((1, 2), (2, 2)):
            key = f"{tile[0]},{tile[1]}"
            for index, raw_slot in enumerate(_array(slots_by_tile.get(key), f"seed slots {key}")):
                slot = _exact_keys(raw_slot, {"cycle", "branch"}, f"seed slots {key}[{index}]")
                cycle_cell = _xy(slot["cycle"], f"seed slots {key}[{index}].cycle")
                branch = _xy(slot["branch"], f"seed slots {key}[{index}].branch")
                observed.append(
                    {
                        "cycle": [cycle_cell[0], cycle_cell[1]],
                        "branch": [branch[0], branch[1]],
                    }
                )
        observed.sort(key=lambda item: (item["cycle"], item["branch"]))
        expected_slots = [
            {"cycle": [x, 29], "branch": [x, 30]}
            for x in (23, 24, 25, 30, 31, 32, 33, 34, 35, 36, 37)
        ]
        if observed != expected_slots:
            _fail("ANTECEDENT_INPUT_INVALID", "seed-narrow slots")
        slots = expected_slots
    elif attachment_scope == "all_legal_d6_slots":
        slots = [
            {"cycle": [x, 29], "branch": [x, 30]}
            for x in range(14, 42)
        ]
    else:
        _fail("ANTECEDENT_INPUT_INVALID", f"attachment_scope={attachment_scope!r}")
    return selected, slots


def rebuild_d6_antecedent(
    strict_instance: dict[str, Any],
    framework: dict[str, Any],
    seed: dict[str, Any],
    *,
    protocol_profile: str,
    attachment_scope: str,
) -> dict[str, object]:
    """Independently derive the complete canonical D6 antecedent."""

    if protocol_profile == CLOSED_V2_PROFILE:
        antecedent_schema = ANTECEDENT_SCHEMA
        class_counts = {
            "3L": 7,
            "3O3": 3,
            "5L": 2,
            "5O2": 2,
            "6G": 2,
            "6B": 1,
        }
        expected_totals = D6_BEFORE_TOTALS
    elif protocol_profile == SWAP_V3_PROFILE:
        if attachment_scope != "all_legal_d6_slots":
            _fail(
                "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
                "v3 antecedent rebuild requires all_legal_d6_slots",
            )
        antecedent_schema = V3_ANTECEDENT_SCHEMA
        class_counts = {
            class_name: D6_AFTER_CLASS_COUNTS[class_name]
            for class_name in ("3L", "3O3", "5L", "5O2", "6B", "6G")
        }
        expected_totals = D6_AFTER_TOTALS
    else:
        _fail("ARTIFACT_PROTOCOL_COHORT_MISMATCH", protocol_profile)
    class_catalog = _rebuild_class_catalog(
        strict_instance,
        protocol_profile=protocol_profile,
    )
    mode_catalog = _rebuild_mode_catalog(strict_instance)
    _validate_rebuild_authorities(
        strict_instance,
        framework,
        class_catalog,
        protocol_profile=protocol_profile,
    )
    poles, power_rule = _rebuild_fixed(strict_instance, framework)
    seed_hints, slots = _rebuild_seed(seed, power_rule, attachment_scope)
    for class_name, item in class_catalog.items():
        for mode in mode_catalog[str(item["template"])]:
            ports = _array(mode["ports"], f"rebuilt mode {class_name}")
            if (
                sum(port["kind"] == "input" for port in ports) < item["input_count"]
                or sum(port["kind"] == "output" for port in ports) < item["output_count"]
            ):
                _fail("ANTECEDENT_INPUT_INVALID", f"mode capacity for {class_name}")
    antecedent: dict[str, object] = {
        "schema": antecedent_schema,
        "claim_boundary": "exact_local_d6_antecedent_only",
        "benchmark_id": _text(strict_instance.get("benchmark_id"), "strict.benchmark_id"),
        "attachment_scope": attachment_scope,
        "local_bounds": {"x_min": 14, "x_max": 41, "y_min": 28, "y_max": 41},
        "tiles": [
            {
                "tile": [1, 2],
                "bounds": {"x_min": 14, "x_max": 27, "y_min": 28, "y_max": 41},
                "type_counts": {"3": 5, "5": 3, "6": 1},
            },
            {
                "tile": [2, 2],
                "bounds": {"x_min": 28, "x_max": 41, "y_min": 28, "y_max": 41},
                "type_counts": {"3": 5, "5": 1, "6": 2},
            },
        ],
        "poles": poles,
        "protected_body_only_rect": {"anchor": [29, 28], "size": [6, 7]},
        "cycle": {
            "y": 29,
            "x_min": 14,
            "x_max": 41,
            "direction": "E",
            "attachment_slots": slots,
            "roles": {
                "none": {"in_dirs": ["W"], "out_dirs": ["E"]},
                "output_injection": {"in_dirs": ["W", "N"], "out_dirs": ["E"]},
                "input_tap": {"in_dirs": ["W"], "out_dirs": ["E", "N"]},
            },
        },
        "class_counts": {name: class_counts[name] for name in sorted(class_counts)},
        "class_catalog": {name: class_catalog[name] for name in sorted(class_catalog)},
        "mode_catalog": mode_catalog,
        "power_rule": power_rule,
        "routing_patterns": _rebuild_routing_patterns(),
        "seed_hints": seed_hints,
        "seed_hint_policy": "add_hint_only_never_constraint",
        "expected_totals": dict(expected_totals),
    }
    if protocol_profile == SWAP_V3_PROFILE:
        antecedent.update(
            {
                "protocol": _protocol_identity(),
                "class_transfer": _class_transfer(),
                "class_ledger": _class_ledger(class_catalog),
            }
        )
    canonical_json_bytes(antecedent)
    return antecedent


def _slot_cycle(value: object, label: str) -> tuple[int, int]:
    if type(value) is dict:
        record = _exact_keys(value, {"cycle", "branch"}, label)
        cycle = _xy(record["cycle"], f"{label}.cycle")
        branch = _xy(record["branch"], f"{label}.branch")
        if branch != (cycle[0], cycle[1] + 1):
            _fail("ATTACHMENT_SLOT_INVALID", label)
        return cycle
    return _xy(value, label)


def _parse_antecedent(
    antecedent_value: object,
    *,
    protocol_profile: str,
) -> dict[str, Any]:
    antecedent = _verify_antecedent_cohort_shape(
        antecedent_value,
        protocol_profile=protocol_profile,
    )
    if (
        antecedent["claim_boundary"] != "exact_local_d6_antecedent_only"
        or antecedent["benchmark_id"] != "factory_layout_optimality_benchmark_v1"
        or antecedent["seed_hint_policy"] != "add_hint_only_never_constraint"
    ):
        _fail("ANTECEDENT_D6_DRIFT", "identity or claim boundary")
    if antecedent["attachment_scope"] not in {"seed_narrow", "all_legal_d6_slots"}:
        _fail("ANTECEDENT_INVALID", "attachment_scope")
    if (
        protocol_profile == SWAP_V3_PROFILE
        and antecedent["attachment_scope"] != "all_legal_d6_slots"
    ):
        _fail(
            "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
            "v3 antecedent requires all_legal_d6_slots",
        )
    local_bounds = _bounds(antecedent["local_bounds"], "antecedent.local_bounds")
    if local_bounds != (14, 28, 41, 41):
        _fail("ANTECEDENT_D6_DRIFT", "local bounds")

    expected_tiles = {
        (1, 2): ((14, 28, 27, 41), {"3": 5, "5": 3, "6": 1}),
        (2, 2): ((28, 28, 41, 41), {"3": 5, "5": 1, "6": 2}),
    }
    tiles: dict[tuple[int, int], dict[str, Any]] = {}
    for index, value in enumerate(_array(antecedent["tiles"], "antecedent.tiles")):
        tile = _exact_keys(
            value,
            {"tile", "bounds", "type_counts"},
            f"antecedent.tiles[{index}]",
        )
        tile_id = _xy(tile["tile"], f"tiles[{index}].tile")
        if tile_id in tiles or tile_id not in expected_tiles:
            _fail("ANTECEDENT_D6_DRIFT", f"tile {tile_id}")
        bounds = _bounds(tile["bounds"], f"tiles[{index}].bounds")
        type_counts_raw = _exact_keys(
            tile["type_counts"],
            {"3", "5", "6"},
            f"tiles[{index}].type_counts",
        )
        type_counts = {
            name: _integer(count, f"tiles[{index}].type_counts.{name}", minimum=0)
            for name, count in type_counts_raw.items()
        }
        if (bounds, type_counts) != expected_tiles[tile_id]:
            _fail("ANTECEDENT_D6_DRIFT", f"tile facts {tile_id}")
        tiles[tile_id] = {
            "bounds": bounds,
            "type_counts": type_counts,
        }
    if set(tiles) != set(expected_tiles):
        _fail("ANTECEDENT_D6_DRIFT", "tile set")

    protected = _exact_keys(
        antecedent["protected_body_only_rect"],
        {"anchor", "size"},
        "antecedent.protected_body_only_rect",
    )
    protected_anchor = _xy(protected["anchor"], "protected.anchor")
    protected_size = _body_size(protected["size"], "protected.size")
    if protected_anchor != (29, 28) or protected_size != (6, 7):
        _fail("ANTECEDENT_D6_DRIFT", "protected rectangle")
    protected_cells = _rect_cells(protected_anchor, *protected_size)

    cycle = _exact_keys(
        antecedent["cycle"],
        {"y", "x_min", "x_max", "direction", "attachment_slots", "roles"},
        "antecedent.cycle",
    )
    cycle_y = _integer(cycle["y"], "cycle.y")
    cycle_x_min = _integer(cycle["x_min"], "cycle.x_min")
    cycle_x_max = _integer(cycle["x_max"], "cycle.x_max")
    if (cycle_y, cycle_x_min, cycle_x_max, cycle["direction"]) != (29, 14, 41, "E"):
        _fail("ANTECEDENT_D6_DRIFT", "cycle")
    attachment_slots = {
        _slot_cycle(value, f"cycle.attachment_slots[{index}]")
        for index, value in enumerate(_array(cycle["attachment_slots"], "cycle.attachment_slots"))
    }
    if len(attachment_slots) != len(_array(cycle["attachment_slots"], "cycle.attachment_slots")):
        _fail("ATTACHMENT_SLOT_INVALID", "duplicate cycle cell")
    if antecedent["attachment_scope"] == "seed_narrow":
        expected_slots = {(x, 29) for x in (*range(23, 26), *range(30, 38))}
        if attachment_slots != expected_slots:
            _fail("ANTECEDENT_D6_DRIFT", "seed-narrow attachment slots")
    if any(y != 29 or not 14 <= x <= 41 for x, y in attachment_slots):
        _fail("ATTACHMENT_SLOT_INVALID", "cycle slot leaves D6")
    expected_roles = {
        "none": {"in_dirs": ["W"], "out_dirs": ["E"]},
        "output_injection": {"in_dirs": ["W", "N"], "out_dirs": ["E"]},
        "input_tap": {"in_dirs": ["W"], "out_dirs": ["E", "N"]},
    }
    if cycle["roles"] != expected_roles:
        _fail("ANTECEDENT_D6_DRIFT", "cycle roles")
    cycle_cells = {(x, cycle_y) for x in range(cycle_x_min, cycle_x_max + 1)}

    expected_class_counts = (
        {"3L": 7, "3O3": 3, "5L": 2, "5O2": 2, "6G": 2, "6B": 1}
        if protocol_profile == CLOSED_V2_PROFILE
        else {
            class_name: D6_AFTER_CLASS_COUNTS[class_name]
            for class_name in ("3L", "3O3", "5L", "5O2", "6B", "6G")
        }
    )
    class_counts_raw = _exact_keys(
        antecedent["class_counts"],
        set(expected_class_counts),
        "antecedent.class_counts",
    )
    class_counts = {
        name: _integer(value, f"class_counts.{name}", minimum=0)
        for name, value in class_counts_raw.items()
    }
    if class_counts != expected_class_counts:
        _fail("ANTECEDENT_D6_DRIFT", "class counts")

    class_catalog_raw = _exact_keys(
        antecedent["class_catalog"],
        set(class_counts),
        "antecedent.class_catalog",
    )
    class_catalog: dict[str, dict[str, Any]] = {}
    expected_class_shape = {
        "3L": ("manufacturing_3x3", 1, 1),
        "3O3": ("manufacturing_3x3", 1, 3),
        "5L": ("manufacturing_5x5", 1, 1),
        "5O2": ("manufacturing_5x5", 1, 2),
        "6G": ("manufacturing_6x4", 3, 1),
        "6B": ("manufacturing_6x4", 5, 1),
    }
    for class_name, value in class_catalog_raw.items():
        record = _exact_keys(
            value,
            {"template", "input_count", "output_count", "operation_group_ids"},
            f"class_catalog.{class_name}",
        )
        template = _text(record["template"], f"class_catalog.{class_name}.template")
        input_count = _integer(record["input_count"], f"{class_name}.input_count", minimum=0)
        output_count = _integer(record["output_count"], f"{class_name}.output_count", minimum=0)
        group_ids = _array(record["operation_group_ids"], f"{class_name}.operation_group_ids")
        if any(type(item) is not str or not item for item in group_ids) or len(group_ids) != len(set(group_ids)):
            _fail("CLASS_CATALOG_INVALID", class_name)
        if (template, input_count, output_count) != expected_class_shape[class_name]:
            _fail("ANTECEDENT_D6_DRIFT", f"class {class_name}")
        class_catalog[class_name] = {
            "template": template,
            "input_count": input_count,
            "output_count": output_count,
            "operation_group_ids": list(group_ids),
        }

    mode_catalog_raw = _object(antecedent["mode_catalog"], "antecedent.mode_catalog")
    if set(mode_catalog_raw) != {item["template"] for item in class_catalog.values()}:
        _fail("MODE_CATALOG_INVALID", "template set")
    mode_catalog: dict[str, dict[str, dict[str, Any]]] = {}
    for template, raw_modes in mode_catalog_raw.items():
        by_id: dict[str, dict[str, Any]] = {}
        for index, raw_mode in enumerate(_array(raw_modes, f"mode_catalog.{template}")):
            mode = _exact_keys(
                raw_mode,
                {"id", "body", "ports"},
                f"mode_catalog.{template}[{index}]",
            )
            mode_id = _text(mode["id"], f"mode_catalog.{template}[{index}].id")
            if mode_id in by_id:
                _fail("MODE_CATALOG_INVALID", f"duplicate {template}.{mode_id}")
            width, height = _body_size(mode["body"], f"{template}.{mode_id}.body")
            ports: dict[str, dict[str, Any]] = {}
            for port_index, raw_port in enumerate(_array(mode["ports"], f"{template}.{mode_id}.ports")):
                port = _exact_keys(
                    raw_port,
                    {"id", "kind", "body_cell", "direction"},
                    f"{template}.{mode_id}.ports[{port_index}]",
                )
                port_id = _text(port["id"], "mode port id")
                if port_id in ports or port["kind"] not in {"input", "output"}:
                    _fail("MODE_CATALOG_INVALID", f"{template}.{mode_id}.{port_id}")
                body_cell = _xy(port["body_cell"], f"{template}.{mode_id}.{port_id}.body_cell")
                direction = _direction(port["direction"], f"{template}.{mode_id}.{port_id}.direction")
                x, y = body_cell
                outward = (
                    (direction == "N" and y == height - 1 and 0 <= x < width)
                    or (direction == "S" and y == 0 and 0 <= x < width)
                    or (direction == "E" and x == width - 1 and 0 <= y < height)
                    or (direction == "W" and x == 0 and 0 <= y < height)
                )
                if not outward:
                    _fail("MODE_CATALOG_INVALID", f"non-outward {template}.{mode_id}.{port_id}")
                ports[port_id] = {
                    "id": port_id,
                    "kind": port["kind"],
                    "body_cell": body_cell,
                    "direction": direction,
                }
            by_id[mode_id] = {
                "id": mode_id,
                "body": (width, height),
                "ports": ports,
            }
        if not by_id:
            _fail("MODE_CATALOG_INVALID", f"empty {template}")
        mode_catalog[template] = by_id

    power_rule = _exact_keys(
        antecedent["power_rule"],
        {"required_rule", "pole_template", "coverage_offsets"},
        "antecedent.power_rule",
    )
    if (
        power_rule["required_rule"] != "at_least_one_body_cell_covered"
        or power_rule["pole_template"] != "power_pole"
    ):
        _fail("POWER_RULE_INVALID", "strict power rule identity")
    coverage_offsets = _exact_keys(
        power_rule["coverage_offsets"],
        {"x_min_offset", "x_max_offset", "y_min_offset", "y_max_offset"},
        "antecedent.power_rule.coverage_offsets",
    )
    power_offsets = tuple(
        _integer(coverage_offsets[name], f"power_rule.coverage_offsets.{name}")
        for name in ("x_min_offset", "x_max_offset", "y_min_offset", "y_max_offset")
    )
    if power_offsets[0] > power_offsets[1] or power_offsets[2] > power_offsets[3]:
        _fail("POWER_RULE_INVALID", "reversed offsets")

    poles: dict[tuple[int, int], tuple[int, int]] = {}
    for index, raw_pole in enumerate(_array(antecedent["poles"], "antecedent.poles")):
        pole = _exact_keys(raw_pole, {"tile", "anchor", "size"}, f"poles[{index}]")
        tile_id = _xy(pole["tile"], f"poles[{index}].tile")
        anchor = _xy(pole["anchor"], f"poles[{index}].anchor")
        if tile_id in poles or _body_size(pole["size"], f"poles[{index}].size") != (2, 2):
            _fail("ANTECEDENT_D6_DRIFT", "poles")
        poles[tile_id] = anchor
    if poles != {(1, 2): (20, 34), (2, 2): (35, 35)}:
        _fail("ANTECEDENT_D6_DRIFT", "pole anchors")
    for tile_id in tiles:
        tiles[tile_id]["pole_anchor"] = poles[tile_id]

    totals = _exact_keys(
        antecedent["expected_totals"],
        {"bodies", "active_inputs", "active_outputs"},
        "antecedent.expected_totals",
    )
    expected_totals = (
        D6_BEFORE_TOTALS
        if protocol_profile == CLOSED_V2_PROFILE
        else D6_AFTER_TOTALS
    )
    if totals != expected_totals:
        _fail("ANTECEDENT_D6_DRIFT", "expected totals")
    seed_hints = _array(antecedent["seed_hints"], "antecedent.seed_hints")
    if len(seed_hints) != 17:
        _fail("ANTECEDENT_D6_DRIFT", "seed hint count")
    if (
        protocol_profile == SWAP_V3_PROFILE
        and antecedent["class_ledger"] != _class_ledger(class_catalog)
    ):
        _fail("ANTECEDENT_D6_DRIFT", "class ledger")

    return {
        "value": antecedent,
        "claim_boundary": antecedent["claim_boundary"],
        "attachment_scope": antecedent["attachment_scope"],
        "local_bounds": local_bounds,
        "tiles": tiles,
        "protected_cells": protected_cells,
        "cycle_cells": cycle_cells,
        "cycle_x_min": cycle_x_min,
        "cycle_x_max": cycle_x_max,
        "attachment_slots": attachment_slots,
        "class_counts": class_counts,
        "class_catalog": class_catalog,
        "expected_totals": dict(expected_totals),
        "protocol_profile": protocol_profile,
        "mode_catalog": mode_catalog,
        "power_offsets": power_offsets,
        "routing_patterns_raw": antecedent["routing_patterns"],
    }


def _direction_set(value: object, label: str) -> frozenset[str]:
    items = _array(value, label)
    directions = [_direction(item, f"{label}[{index}]") for index, item in enumerate(items)]
    if len(directions) != len(set(directions)):
        _fail("DIRECTION_SET_INVALID", f"{label}: duplicate")
    return frozenset(directions)


def _routing_catalog(value: object) -> dict[str, dict[str, dict[str, Any]]]:
    catalog = _exact_keys(value, {"ground", "elevated", "crossing"}, "routing_patterns")
    result: dict[str, dict[str, dict[str, Any]]] = {}
    observed_ground: set[tuple[str, frozenset[str], frozenset[str]]] = set()
    observed_elevated: set[tuple[frozenset[str], frozenset[str]]] = set()
    for level in ("ground", "elevated"):
        by_name: dict[str, dict[str, Any]] = {}
        for index, raw_pattern in enumerate(_array(catalog[level], f"routing_patterns.{level}")):
            pattern = _exact_keys(
                raw_pattern,
                {"name", "component", "in_dirs", "out_dirs"},
                f"routing_patterns.{level}[{index}]",
            )
            name = _text(pattern["name"], f"routing_patterns.{level}[{index}].name")
            component = _text(pattern["component"], f"routing_patterns.{level}[{index}].component")
            in_dirs = _direction_set(pattern["in_dirs"], f"{level}.{name}.in_dirs")
            out_dirs = _direction_set(pattern["out_dirs"], f"{level}.{name}.out_dirs")
            if name in by_name or not in_dirs or not out_dirs or in_dirs & out_dirs:
                _fail("ROUTING_PATTERN_INVALID", f"{level}.{name}")
            by_name[name] = {
                "component": component,
                "in_dirs": in_dirs,
                "out_dirs": out_dirs,
            }
            if level == "ground":
                observed_ground.add((component, in_dirs, out_dirs))
            else:
                observed_elevated.add((in_dirs, out_dirs))
                if len(in_dirs) != 1 or len(out_dirs) != 1:
                    _fail("ROUTING_PATTERN_INVALID", f"elevated degree {name}")
        result[level] = by_name

    expected_ground: set[tuple[str, frozenset[str], frozenset[str]]] = set()
    for d_in in DIRECTIONS:
        for d_out in DIRECTIONS:
            if d_out != d_in:
                expected_ground.add(("belt", frozenset({d_in}), frozenset({d_out})))
        remaining = [direction for direction in DIRECTIONS if direction != d_in]
        for first in range(len(remaining)):
            for second in range(first + 1, len(remaining)):
                expected_ground.add(
                    (
                        "splitter",
                        frozenset({d_in}),
                        frozenset({remaining[first], remaining[second]}),
                    )
                )
        expected_ground.add(("splitter", frozenset({d_in}), frozenset(remaining)))
    for d_out in DIRECTIONS:
        remaining = [direction for direction in DIRECTIONS if direction != d_out]
        for first in range(len(remaining)):
            for second in range(first + 1, len(remaining)):
                expected_ground.add(
                    (
                        "merger",
                        frozenset({remaining[first], remaining[second]}),
                        frozenset({d_out}),
                    )
                )
        expected_ground.add(("merger", frozenset(remaining), frozenset({d_out})))
    expected_elevated = {
        (frozenset({direction}), frozenset({OPPOSITE[direction]}))
        for direction in DIRECTIONS
    }
    if observed_ground != expected_ground or len(result["ground"]) != 44:
        _fail("ROUTING_CATALOG_DRIFT", "ground patterns are not the exact 44-state catalog")
    if observed_elevated != expected_elevated or len(result["elevated"]) != 4:
        _fail("ROUTING_CATALOG_DRIFT", "elevated patterns are not four directed straights")
    if catalog["crossing"] != "perpendicular_ground_and_elevated_straights_without_transfer":
        _fail("ROUTING_CATALOG_DRIFT", "crossing rule absent")
    return result


def _body_type(width: int, height: int) -> str:
    if (width, height) == (3, 3):
        return "3"
    if (width, height) == (5, 5):
        return "5"
    if {width, height} == {4, 6}:
        return "6"
    _fail("BODY_TYPE_INVALID", f"{width}x{height}")


def _parse_bodies(
    configuration: dict[str, Any],
    antecedent: dict[str, Any],
) -> dict[str, Any]:
    bodies_raw = _array(configuration["bodies"], "configuration.bodies")
    body_ids: set[str] = set()
    class_counter: Counter[str] = Counter()
    tile_type_counter: dict[tuple[int, int], Counter[str]] = defaultdict(Counter)
    occupied: set[tuple[int, int]] = set()
    pole_cells = set().union(
        *(
            _rect_cells(tile["pole_anchor"], 2, 2)
            for tile in antecedent["tiles"].values()
        )
    )
    forbidden_body = pole_cells | antecedent["protected_cells"] | antecedent["cycle_cells"]
    terminals: dict[tuple[str, str], dict[str, Any]] = {}
    deferred_fronts: list[tuple[tuple[str, str], tuple[int, int], str, str]] = []

    for index, raw_body in enumerate(bodies_raw):
        body = _exact_keys(
            raw_body,
            {
                "id",
                "class",
                "tile",
                "anchor",
                "template",
                "mode",
                "active_inputs",
                "active_outputs",
                "ports",
            },
            f"configuration.bodies[{index}]",
        )
        body_id = _text(body["id"], f"bodies[{index}].id")
        if body_id in body_ids:
            _fail("BODY_DUPLICATE", body_id)
        body_ids.add(body_id)
        class_name = _text(body["class"], f"bodies[{index}].class")
        if class_name not in antecedent["class_catalog"]:
            _fail("BODY_CLASS_INVALID", class_name)
        class_counter[class_name] += 1
        class_record = antecedent["class_catalog"][class_name]
        template = _text(body["template"], f"bodies[{index}].template")
        if template != class_record["template"]:
            _fail("BODY_TEMPLATE_MISMATCH", body_id)
        mode_id = _text(body["mode"], f"bodies[{index}].mode")
        mode = antecedent["mode_catalog"].get(template, {}).get(mode_id)
        if mode is None:
            _fail("BODY_MODE_INVALID", f"{body_id}:{template}:{mode_id}")
        tile_id = _xy(body["tile"], f"bodies[{index}].tile")
        if tile_id not in antecedent["tiles"]:
            _fail("BODY_TILE_INVALID", body_id)
        tile = antecedent["tiles"][tile_id]
        anchor = _xy(body["anchor"], f"bodies[{index}].anchor")
        width, height = mode["body"]
        body_cells = _rect_cells(anchor, width, height)
        if any(not _inside(cell, tile["bounds"]) for cell in body_cells):
            _fail("BODY_TILE_CONTAINMENT_FAILED", body_id)
        collision = body_cells & (occupied | forbidden_body)
        if collision:
            _fail("BODY_COLLISION", f"{body_id}: {min(collision)}")
        occupied.update(body_cells)
        tile_type_counter[tile_id][_body_type(width, height)] += 1

        x_min, x_max, y_min, y_max = antecedent["power_offsets"]
        pole_x, pole_y = tile["pole_anchor"]
        powered = any(
            pole_x + x_min <= x <= pole_x + x_max
            and pole_y + y_min <= y <= pole_y + y_max
            for x, y in body_cells
        )
        if not powered:
            _fail("BODY_POWER_COVERAGE_FAILED", body_id)

        active_inputs = _array(body["active_inputs"], f"bodies[{index}].active_inputs")
        active_outputs = _array(body["active_outputs"], f"bodies[{index}].active_outputs")
        if (
            any(type(item) is not str for item in active_inputs + active_outputs)
            or len(active_inputs) != len(set(active_inputs))
            or len(active_outputs) != len(set(active_outputs))
            or set(active_inputs) & set(active_outputs)
            or len(active_inputs) != class_record["input_count"]
            or len(active_outputs) != class_record["output_count"]
        ):
            _fail("ACTIVE_PORT_SELECTION_INVALID", body_id)
        selected = {
            **{port_id: "input" for port_id in active_inputs},
            **{port_id: "output" for port_id in active_outputs},
        }
        raw_ports = _array(body["ports"], f"bodies[{index}].ports")
        if len(raw_ports) != len(selected):
            _fail("ACTIVE_PORT_RECORD_MISMATCH", body_id)
        observed_ids: set[str] = set()
        for port_index, raw_port in enumerate(raw_ports):
            port = _exact_keys(
                raw_port,
                {"id", "kind", "body_cell", "direction", "front"},
                f"bodies[{index}].ports[{port_index}]",
            )
            port_id = _text(port["id"], f"bodies[{index}].ports[{port_index}].id")
            if port_id in observed_ids or port_id not in selected:
                _fail("ACTIVE_PORT_RECORD_MISMATCH", f"{body_id}:{port_id}")
            observed_ids.add(port_id)
            catalog_port = mode["ports"].get(port_id)
            if catalog_port is None or selected[port_id] != catalog_port["kind"]:
                _fail("ACTIVE_PORT_RECORD_MISMATCH", f"{body_id}:{port_id}")
            body_cell = _xy(port["body_cell"], f"{body_id}.{port_id}.body_cell")
            direction = _direction(port["direction"], f"{body_id}.{port_id}.direction")
            if (
                port["kind"] != catalog_port["kind"]
                or body_cell != catalog_port["body_cell"]
                or direction != catalog_port["direction"]
            ):
                _fail("ACTIVE_PORT_RECORD_MISMATCH", f"{body_id}:{port_id}")
            dx, dy = DELTA[direction]
            expected_front = (anchor[0] + body_cell[0] + dx, anchor[1] + body_cell[1] + dy)
            front = _xy(port["front"], f"{body_id}.{port_id}.front")
            if front != expected_front or not _inside(front, antecedent["local_bounds"]):
                _fail("FRONT_RECOMPUTATION_FAILED", f"{body_id}:{port_id}")
            terminal_key = (body_id, port_id)
            terminals[terminal_key] = {
                "kind": catalog_port["kind"],
                "front": front,
                "direction": direction,
            }
            deferred_fronts.append((terminal_key, front, catalog_port["kind"], direction))
        if observed_ids != set(selected):
            _fail("ACTIVE_PORT_RECORD_MISMATCH", body_id)

    observed_class_counts = {
        class_name: class_counter.get(class_name, 0)
        for class_name in antecedent["class_counts"]
    }
    if observed_class_counts != antecedent["class_counts"]:
        _fail("BODY_CLASS_COUNT_MISMATCH", repr(dict(class_counter)))
    for tile_id, tile in antecedent["tiles"].items():
        if dict(tile_type_counter[tile_id]) != tile["type_counts"]:
            _fail("BODY_TILE_TYPE_COUNT_MISMATCH", repr(tile_id))
    front_incidence_counter = Counter(
        (front, OPPOSITE[direction], kind)
        for _key, front, kind, direction in deferred_fronts
    )
    for terminal_key, front, kind, direction in deferred_fronts:
        if front in occupied or front in pole_cells:
            _fail("FRONT_NOT_FREE", f"{terminal_key}: {front}")
        if front_incidence_counter[(front, OPPOSITE[direction], kind)] != 1:
            _fail("FRONT_INCIDENCE_DUPLICATE", f"{terminal_key}: {front}")
    expected_inputs = sum(
        antecedent["class_counts"][name] * record["input_count"]
        for name, record in antecedent["class_catalog"].items()
    )
    expected_outputs = sum(
        antecedent["class_counts"][name] * record["output_count"]
        for name, record in antecedent["class_catalog"].items()
    )
    if (
        sum(item["kind"] == "input" for item in terminals.values()) != expected_inputs
        or sum(item["kind"] == "output" for item in terminals.values()) != expected_outputs
        or (
            expected_inputs,
            expected_outputs,
        )
        != (
            antecedent["expected_totals"]["active_inputs"],
            antecedent["expected_totals"]["active_outputs"],
        )
    ):
        _fail(
            "ACTIVE_PORT_TOTAL_MISMATCH",
            (
                "D6 active port totals differ from the exact protocol profile: "
                f"inputs={expected_inputs}, outputs={expected_outputs}"
            ),
        )
    return {
        "occupied": occupied,
        "pole_cells": pole_cells,
        "terminals": terminals,
    }


def _parse_channel(
    value: object,
    *,
    level: str,
    catalog: dict[str, dict[str, dict[str, Any]]],
    label: str,
) -> dict[str, Any] | None:
    if value is None:
        return None
    channel = _exact_keys(value, {"pattern", "in_dirs", "out_dirs"}, label)
    pattern_name = _text(channel["pattern"], f"{label}.pattern")
    pattern = catalog[level].get(pattern_name)
    if pattern is None:
        _fail("TRANSPORT_PATTERN_UNKNOWN", f"{level}:{pattern_name}")
    in_dirs = _direction_set(channel["in_dirs"], f"{label}.in_dirs")
    out_dirs = _direction_set(channel["out_dirs"], f"{label}.out_dirs")
    if in_dirs != pattern["in_dirs"] or out_dirs != pattern["out_dirs"]:
        _fail("TRANSPORT_PATTERN_MISMATCH", f"{level}:{pattern_name}")
    return {
        "pattern": pattern_name,
        "component": pattern["component"],
        "in_dirs": in_dirs,
        "out_dirs": out_dirs,
    }


def _straight_axis(channel: dict[str, Any]) -> str | None:
    if len(channel["in_dirs"]) != 1 or len(channel["out_dirs"]) != 1:
        return None
    d_in = next(iter(channel["in_dirs"]))
    d_out = next(iter(channel["out_dirs"]))
    if d_out != OPPOSITE[d_in]:
        return None
    return "horizontal" if d_in in {"E", "W"} else "vertical"


def _parse_transport(
    configuration: dict[str, Any],
    antecedent: dict[str, Any],
    body_state: dict[str, Any],
    catalog: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    channels: dict[tuple[tuple[int, int], str], dict[str, Any]] = {}
    cell_levels: dict[tuple[int, int], set[str]] = defaultdict(set)
    seen_cells: set[tuple[int, int]] = set()
    for index, raw_transport in enumerate(_array(configuration["transport"], "configuration.transport")):
        record = _exact_keys(
            raw_transport,
            {"cell", "ground", "elevated"},
            f"configuration.transport[{index}]",
        )
        cell = _xy(record["cell"], f"transport[{index}].cell")
        if cell in seen_cells:
            _fail("TRANSPORT_DUPLICATE_CELL", repr(cell))
        seen_cells.add(cell)
        if not _inside(cell, antecedent["local_bounds"]):
            _fail("TRANSPORT_OUTSIDE_LOCAL_BOUNDS", repr(cell))
        if cell in body_state["occupied"] or cell in body_state["pole_cells"]:
            _fail("TRANSPORT_BODY_COLLISION", repr(cell))
        for level in ("ground", "elevated"):
            channel = _parse_channel(
                record[level],
                level=level,
                catalog=catalog,
                label=f"transport[{index}].{level}",
            )
            if channel is not None:
                state = (cell, level)
                if state in channels:
                    _fail("TRANSPORT_DUPLICATE", f"{cell}:{level}")
                channels[state] = channel
                cell_levels[cell].add(level)
        if not cell_levels[cell]:
            _fail("TRANSPORT_EMPTY_CELL", repr(cell))
        if len(cell_levels[cell]) == 2:
            ground = channels[(cell, "ground")]
            elevated = channels[(cell, "elevated")]
            ground_axis = _straight_axis(ground)
            elevated_axis = _straight_axis(elevated)
            if ground_axis is None or elevated_axis is None or ground_axis == elevated_axis:
                _fail("CROSSING_INVALID", repr(cell))

    roles: dict[tuple[int, int], str] = {}
    for index, raw_role in enumerate(_array(configuration["cycle_roles"], "configuration.cycle_roles")):
        role = _exact_keys(raw_role, {"cell", "role"}, f"configuration.cycle_roles[{index}]")
        cell = _xy(role["cell"], f"cycle_roles[{index}].cell")
        role_name = role["role"]
        if (
            cell in roles
            or cell not in antecedent["attachment_slots"]
            or role_name not in {"output_injection", "input_tap"}
        ):
            _fail("CYCLE_ROLE_INVALID", f"{cell}:{role_name!r}")
        roles[cell] = str(role_name)
    if not roles:
        _fail("CYCLE_ROLE_INVALID", "no active D6 attachment role")

    for cell in antecedent["cycle_cells"]:
        ground = channels.get((cell, "ground"))
        if ground is None:
            _fail("CYCLE_CHANNEL_MISSING", repr(cell))
        role = roles.get(cell)
        expected = {
            None: (frozenset({"W"}), frozenset({"E"})),
            "output_injection": (frozenset({"W", "N"}), frozenset({"E"})),
            "input_tap": (frozenset({"W"}), frozenset({"E", "N"})),
        }[role]
        if (ground["in_dirs"], ground["out_dirs"]) != expected:
            _fail("CYCLE_ROLE_INCIDENCE_MISMATCH", f"{cell}:{role}")

    terminal_stub: dict[
        tuple[tuple[int, int], str, str, str],
        tuple[str, str],
    ] = {}
    for terminal_key, terminal in body_state["terminals"].items():
        sense = "in" if terminal["kind"] == "output" else "out"
        side = OPPOSITE[terminal["direction"]]
        ground_channel = channels.get((terminal["front"], "ground"))
        if ground_channel is None or side not in ground_channel[f"{sense}_dirs"]:
            _fail("TERMINAL_INCIDENCE_INVALID", f"{terminal_key}: exact ground stub absent")
        level = "ground"
        terminal["layer"] = level
        key = (terminal["front"], level, sense, side)
        if key in terminal_stub:
            _fail("TERMINAL_INCIDENCE_ALIAS", repr(key))
        terminal_stub[key] = terminal_key

    edges: set[
        tuple[str, tuple[int, int], str, tuple[int, int]]
    ] = set()
    used_terminal_stubs: set[tuple[tuple[int, int], str, str, str]] = set()
    for (cell, level), channel in channels.items():
        for sense in ("in", "out"):
            for direction in channel[f"{sense}_dirs"]:
                dx, dy = DELTA[direction]
                neighbour = (cell[0] + dx, cell[1] + dy)
                reciprocal = "out_dirs" if sense == "in" else "in_dirs"
                neighbour_levels = [
                    neighbour_level
                    for neighbour_level in ("ground", "elevated")
                    if (
                        (neighbour_channel := channels.get((neighbour, neighbour_level)))
                        is not None
                        and OPPOSITE[direction] in neighbour_channel[reciprocal]
                    )
                ]
                external_cycle = (
                    level == "ground"
                    and cell == (antecedent["cycle_x_min"], 29)
                    and sense == "in"
                    and direction == "W"
                ) or (
                    level == "ground"
                    and cell == (antecedent["cycle_x_max"], 29)
                    and sense == "out"
                    and direction == "E"
                )
                stub_key = (cell, level, sense, direction)
                if stub_key in terminal_stub:
                    if external_cycle or neighbour_levels:
                        _fail("TERMINAL_INCIDENCE_COLLISION", repr(stub_key))
                    used_terminal_stubs.add(stub_key)
                    continue
                if external_cycle:
                    if neighbour_levels:
                        _fail(
                            "TRANSPORT_INCIDENCE_COLLISION",
                            f"{cell}:{level}:{sense}:{direction}",
                        )
                    continue
                if len(neighbour_levels) != 1:
                    _fail("TRANSPORT_DANGLING_INCIDENCE", f"{cell}:{level}:{sense}:{direction}")
                neighbour_level = neighbour_levels[0]
                counterpart_sense = "out" if sense == "in" else "in"
                counterpart_stub = (
                    neighbour,
                    neighbour_level,
                    counterpart_sense,
                    OPPOSITE[direction],
                )
                if counterpart_stub in terminal_stub:
                    _fail("TERMINAL_INCIDENCE_COLLISION", repr(counterpart_stub))
                if sense == "out":
                    edges.add((level, cell, neighbour_level, neighbour))
    if used_terminal_stubs != set(terminal_stub):
        _fail("TERMINAL_INCIDENCE_INVALID", "not every active terminal is consumed")
    return {
        "channels": channels,
        "edges": edges,
        "roles": roles,
        "terminals": body_state["terminals"],
    }


def _layer(value: object, label: str) -> str:
    if value not in {"ground", "elevated"}:
        _fail("LAYER_INVALID", label)
    return str(value)


def _flow_arcs(
    value: object,
    *,
    polarity: str,
    physical_edges: set[
        tuple[str, tuple[int, int], str, tuple[int, int]]
    ],
) -> dict[tuple[str, tuple[int, int], str, tuple[int, int]], int]:
    arcs: dict[
        tuple[str, tuple[int, int], str, tuple[int, int]],
        int,
    ] = {}
    for index, raw_arc in enumerate(_array(value, f"flows.{polarity}.arcs")):
        arc = _exact_keys(
            raw_arc,
            {"from_layer", "to_layer", "from", "to", "amount"},
            f"flows.{polarity}.arcs[{index}]",
        )
        key = (
            _layer(
                arc["from_layer"],
                f"flows.{polarity}.arcs[{index}].from_layer",
            ),
            _xy(arc["from"], f"flows.{polarity}.arcs[{index}].from"),
            _layer(
                arc["to_layer"],
                f"flows.{polarity}.arcs[{index}].to_layer",
            ),
            _xy(arc["to"], f"flows.{polarity}.arcs[{index}].to"),
        )
        amount = _integer(arc["amount"], f"flows.{polarity}.arcs[{index}].amount", minimum=1)
        if key in arcs or key not in physical_edges:
            _fail("FLOW_ARC_INVALID", f"{polarity}:{key}")
        arcs[key] = amount
    return arcs


def _terminal_amounts(
    value: object,
    *,
    polarity: str,
    field: str,
    kind: str,
    terminals: dict[tuple[str, str], dict[str, Any]],
) -> dict[tuple[str, str], int]:
    amounts: dict[tuple[str, str], int] = {}
    for index, raw_entry in enumerate(_array(value, f"flows.{polarity}.{field}")):
        entry = _exact_keys(
            raw_entry,
            {"body_id", "port_id", "cell", "amount"},
            f"flows.{polarity}.{field}[{index}]",
        )
        key = (
            _text(entry["body_id"], f"{field}[{index}].body_id"),
            _text(entry["port_id"], f"{field}[{index}].port_id"),
        )
        terminal = terminals.get(key)
        if (
            key in amounts
            or terminal is None
            or terminal["kind"] != kind
            or _xy(entry["cell"], f"{field}[{index}].cell") != terminal["front"]
        ):
            _fail("FLOW_TERMINAL_INVALID", f"{polarity}:{key}")
        amounts[key] = _integer(entry["amount"], f"{field}[{index}].amount", minimum=1)
    expected = {key for key, terminal in terminals.items() if terminal["kind"] == kind}
    if set(amounts) != expected or any(amount != 1 for amount in amounts.values()):
        _fail("FLOW_TERMINAL_INVALID", f"{polarity}: exact unit terminal set")
    return amounts


def _cycle_amounts(
    value: object,
    *,
    polarity: str,
    field: str,
    role: str,
    roles: dict[tuple[int, int], str],
) -> dict[tuple[int, int], int]:
    amounts: dict[tuple[int, int], int] = {}
    for index, raw_entry in enumerate(_array(value, f"flows.{polarity}.{field}")):
        entry = _exact_keys(
            raw_entry,
            {"cell", "amount"},
            f"flows.{polarity}.{field}[{index}]",
        )
        cell = _xy(entry["cell"], f"{field}[{index}].cell")
        if cell in amounts or roles.get(cell) != role:
            _fail("FLOW_CYCLE_ENDPOINT_INVALID", f"{polarity}:{cell}")
        amounts[cell] = _integer(entry["amount"], f"{field}[{index}].amount", minimum=1)
    expected = {cell for cell, observed_role in roles.items() if observed_role == role}
    if set(amounts) != expected:
        _fail("FLOW_CYCLE_ENDPOINT_INVALID", f"{polarity}: active role set")
    return amounts


def _path_states(value: object, label: str) -> list[tuple[tuple[int, int], str]]:
    states: list[tuple[tuple[int, int], str]] = []
    for index, raw_state in enumerate(_array(value, label)):
        state = _exact_keys(raw_state, {"cell", "layer"}, f"{label}[{index}]")
        states.append(
            (
                _xy(state["cell"], f"{label}[{index}].cell"),
                _layer(state["layer"], f"{label}[{index}].layer"),
            )
        )
    if not states:
        _fail("REACHABILITY_PATH_INVALID", f"{label}: empty")
    return states


def _reachable_states(
    starts: set[tuple[tuple[int, int], str]],
    edges: set[
        tuple[str, tuple[int, int], str, tuple[int, int]]
    ],
) -> set[tuple[tuple[int, int], str]]:
    graph: dict[tuple[tuple[int, int], str], set[tuple[tuple[int, int], str]]] = defaultdict(set)
    for from_level, source, to_level, target in edges:
        graph[(source, from_level)].add((target, to_level))
    seen = set(starts)
    queue = deque(starts)
    while queue:
        state = queue.popleft()
        for target in graph.get(state, set()):
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return seen


def _verify_reachability_records(
    value: object,
    *,
    polarity: str,
    terminals: dict[tuple[str, str], dict[str, Any]],
    kind: str,
    role_cells: set[tuple[int, int]],
    flow_arcs: dict[
        tuple[str, tuple[int, int], str, tuple[int, int]],
        int,
    ],
) -> None:
    observed: set[tuple[str, str]] = set()
    endpoint_name = "sink" if polarity == "OUT" else "source"
    for index, raw_entry in enumerate(_array(value, f"flows.{polarity}.reachability")):
        entry = _exact_keys(
            raw_entry,
            {"body_id", "port_id", "path", endpoint_name},
            f"flows.{polarity}.reachability[{index}]",
        )
        key = (
            _text(entry["body_id"], f"reachability[{index}].body_id"),
            _text(entry["port_id"], f"reachability[{index}].port_id"),
        )
        terminal = terminals.get(key)
        endpoint = _xy(entry[endpoint_name], f"reachability[{index}].{endpoint_name}")
        states = _path_states(entry["path"], f"flows.{polarity}.reachability[{index}].path")
        terminal_state = (terminal["front"], terminal["layer"]) if terminal is not None else None
        if key in observed or terminal is None or terminal["kind"] != kind or endpoint not in role_cells:
            _fail("REACHABILITY_RECORD_INVALID", f"{polarity}:{key}")
        observed.add(key)
        if polarity == "OUT":
            if states[0] != terminal_state or states[-1] != (endpoint, "ground"):
                _fail("REACHABILITY_PATH_INVALID", f"{polarity}:{key}: endpoints")
        elif states[0] != (endpoint, "ground") or states[-1] != terminal_state:
            _fail("REACHABILITY_PATH_INVALID", f"{polarity}:{key}: endpoints")
        for left, right in zip(states, states[1:]):
            if (left[1], left[0], right[1], right[0]) not in flow_arcs:
                _fail("REACHABILITY_PATH_INVALID", f"{polarity}:{key}: non-flow arc")
    expected = {key for key, terminal in terminals.items() if terminal["kind"] == kind}
    if observed != expected:
        _fail("REACHABILITY_RECORD_INVALID", f"{polarity}: terminal set")


def _verify_one_flow(
    raw_flow: object,
    *,
    polarity: str,
    transport: dict[str, Any],
) -> None:
    if polarity == "OUT":
        flow = _exact_keys(
            raw_flow,
            {"arcs", "terminal_emissions", "cycle_absorptions", "reachability"},
            "flows.OUT",
        )
        terminal_field = "terminal_emissions"
        cycle_field = "cycle_absorptions"
        terminal_kind = "output"
        role = "output_injection"
    else:
        flow = _exact_keys(
            raw_flow,
            {"arcs", "cycle_emissions", "terminal_absorptions", "reachability"},
            "flows.IN",
        )
        terminal_field = "terminal_absorptions"
        cycle_field = "cycle_emissions"
        terminal_kind = "input"
        role = "input_tap"

    arcs = _flow_arcs(
        flow["arcs"],
        polarity=polarity,
        physical_edges=transport["edges"],
    )
    terminal_amounts = _terminal_amounts(
        flow[terminal_field],
        polarity=polarity,
        field=terminal_field,
        kind=terminal_kind,
        terminals=transport["terminals"],
    )
    cycle_amounts = _cycle_amounts(
        flow[cycle_field],
        polarity=polarity,
        field=cycle_field,
        role=role,
        roles=transport["roles"],
    )
    expected_total = sum(
        terminal["kind"] == terminal_kind
        for terminal in transport["terminals"].values()
    )
    if (
        sum(terminal_amounts.values()) != expected_total
        or sum(cycle_amounts.values()) != expected_total
    ):
        _fail("FLOW_TOTAL_MISMATCH", polarity)

    balance: defaultdict[tuple[tuple[int, int], str], int] = defaultdict(int)
    for (from_level, source, to_level, target), amount in arcs.items():
        balance[(source, from_level)] -= amount
        balance[(target, to_level)] += amount
    if polarity == "OUT":
        for key, amount in terminal_amounts.items():
            terminal = transport["terminals"][key]
            balance[(terminal["front"], terminal["layer"])] += amount
        for cell, amount in cycle_amounts.items():
            balance[(cell, "ground")] -= amount
    else:
        for cell, amount in cycle_amounts.items():
            balance[(cell, "ground")] += amount
        for key, amount in terminal_amounts.items():
            terminal = transport["terminals"][key]
            balance[(terminal["front"], terminal["layer"])] -= amount
    nonzero = {state: amount for state, amount in balance.items() if amount}
    if nonzero:
        _fail("FLOW_CONSERVATION_FAILED", f"{polarity}: {next(iter(nonzero.items()))}")

    role_cells = set(cycle_amounts)
    _verify_reachability_records(
        flow["reachability"],
        polarity=polarity,
        terminals=transport["terminals"],
        kind=terminal_kind,
        role_cells=role_cells,
        flow_arcs=arcs,
    )
    if polarity == "OUT":
        for key, terminal in transport["terminals"].items():
            if terminal["kind"] != "output":
                continue
            reachable = _reachable_states({(terminal["front"], terminal["layer"])}, transport["edges"])
            if not any((cell, "ground") in reachable for cell in role_cells):
                _fail("GRAPH_REACHABILITY_FAILED", f"OUT:{key}")
    else:
        reachable = _reachable_states({(cell, "ground") for cell in role_cells}, transport["edges"])
        for key, terminal in transport["terminals"].items():
            if terminal["kind"] == "input" and (terminal["front"], terminal["layer"]) not in reachable:
                _fail("GRAPH_REACHABILITY_FAILED", f"IN:{key}")


def verify_feasible_configuration(
    configuration_value: object,
    antecedent: dict[str, Any],
) -> dict[str, object]:
    configuration = _exact_keys(
        configuration_value,
        {
            "schema",
            "antecedent_sha256",
            "claim_boundary",
            "bodies",
            "transport",
            "cycle_roles",
            "flows",
        },
        "configuration",
    )
    if configuration["schema"] != CONFIGURATION_SCHEMA:
        _fail("CONFIGURATION_INVALID", "schema")
    if configuration["claim_boundary"] != "feasible_only_for_the_exact_local_d6_antecedent":
        _fail("CLAIM_BOUNDARY_INVALID", "configuration")
    body_state = _parse_bodies(configuration, antecedent)
    catalog = _routing_catalog(antecedent["routing_patterns_raw"])
    transport = _parse_transport(configuration, antecedent, body_state, catalog)
    flows = _exact_keys(configuration["flows"], {"OUT", "IN"}, "configuration.flows")
    _verify_one_flow(flows["OUT"], polarity="OUT", transport=transport)
    _verify_one_flow(flows["IN"], polarity="IN", transport=transport)
    return {
        "body_count": len(_array(configuration["bodies"], "configuration.bodies")),
        "active_input_count": antecedent["expected_totals"]["active_inputs"],
        "active_output_count": antecedent["expected_totals"]["active_outputs"],
        "transport_cell_count": len(
            _array(configuration["transport"], "configuration.transport")
        ),
        "cycle_role_count": len(
            _array(configuration["cycle_roles"], "configuration.cycle_roles")
        ),
    }


def replay_run(run_root: Path | str) -> dict[str, object]:
    """Replay a producer run without mutating it."""

    context = verify_byte_graph(run_root)
    status = verify_result_bindings(context)
    snapshots = context["snapshots"]
    actual_antecedent = snapshots["antecedent"]["value"]
    rebuilt_antecedent = rebuild_d6_antecedent(
        _object(snapshots["inputs.strict_instance"]["value"], "strict instance"),
        _object(snapshots["inputs.framework"]["value"], "framework"),
        _object(snapshots["inputs.seed"]["value"], "seed"),
        protocol_profile=context["protocol_profile"],
        attachment_scope=context["config_payload"]["attachment_scope"],
    )
    rebuilt_bytes = canonical_json_bytes(rebuilt_antecedent)
    if actual_antecedent != rebuilt_antecedent or snapshots["antecedent"]["raw"] != rebuilt_bytes:
        _fail("ANTECEDENT_RECOMPUTATION_MISMATCH", "copied strict/framework/seed derivation")
    antecedent = _parse_antecedent(
        actual_antecedent,
        protocol_profile=context["protocol_profile"],
    )
    if antecedent["attachment_scope"] != context["config_payload"]["attachment_scope"]:
        _fail("CROSS_FIELD_MISMATCH", "antecedent attachment_scope")
    if context["protocol_profile"] == SWAP_V3_PROFILE:
        if (
            actual_antecedent["protocol"] != context["config_payload"]["protocol"]
            or actual_antecedent["protocol"] != context["receipt_payload"]["protocol"]
        ):
            _fail(
                "ARTIFACT_PROTOCOL_COHORT_MISMATCH",
                "antecedent/config/receipt protocol identities differ",
            )

    semantic_summary: dict[str, object] | None = None
    if status == "FEASIBLE":
        semantic_summary = verify_feasible_configuration(
            snapshots["configuration"]["value"],
            antecedent,
        )

    if status == "FEASIBLE":
        conclusion = {
            "kind": "local_d6_feasible_only",
            "antecedent_sha256": context["artifacts"]["antecedent"]["sha256"],
        }
    elif status == "INFEASIBLE":
        conclusion = {
            "kind": "exact_d6_antecedent_infeasible_only",
            "antecedent_sha256": context["artifacts"]["antecedent"]["sha256"],
        }
    else:
        conclusion = None
    source_identities = {
        "executing_replayer": context["self_identity"],
        "pinned_run_copies": {
            name.removeprefix("sources."): context["artifacts"][name]
            for name in sorted(context["artifacts"])
            if name.startswith("sources.")
        },
    }
    if context["protocol_profile"] == CLOSED_V2_PROFILE:
        replay_schema = CLOSED_V2_REPLAY_RECEIPT_SCHEMA
        replay_authority_boundary = {
            "research_only": True,
            "local_d6_only": True,
            "whole_witness": False,
            "lower_bound_change": False,
            "upper_bound_change": False,
            "cut_or_rejection": False,
            "production_authority": False,
            "certified_exact_source_authority": False,
        }
    else:
        replay_schema = V3_REPLAY_RECEIPT_SCHEMA
        replay_authority_boundary = _authority_boundary()
    replay = {
        "schema": replay_schema,
        "status": "PASS",
        "producer_status": status,
        "claim_boundary": context["receipt_payload"]["claim_boundary"],
        "artifact_root": {
            "verified": True,
            "manifest": context["artifact_root_manifest"],
            "terminal_receipt_path": TERMINAL_RECEIPT_PATH,
            "producer_receipt_observed_identity": context["receipt_identity"],
        },
        "byte_graph": {
            "verified": True,
            "identity_graph_sha256": context["identity_graph_sha256"],
            "receipt": context["receipt_identity"],
            "artifacts": {
                label: context["artifacts"][label]
                for label in sorted(context["artifacts"])
            },
        },
        "antecedent_recomputation": {
            "verified": True,
            "sha256": context["artifacts"]["antecedent"]["sha256"],
            "attachment_scope": antecedent["attachment_scope"],
        },
        "semantic_verification": {
            "performed": status == "FEASIBLE",
            "summary": semantic_summary,
        },
        "conclusion": conclusion,
        "source_identities": source_identities,
        "replayer_process_contract": context["replayer_process_contract"],
        "authority_boundary": replay_authority_boundary,
    }
    if context["protocol_profile"] == SWAP_V3_PROFILE:
        replay["protocol"] = _protocol_identity()
    _revalidate_verified_byte_graph(context)
    _verify_artifact_root_closure(
        context["run_root"],
        context["artifact_root_manifest"],
        expected_root_signature=context["artifact_root_signature"],
    )
    return replay


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Independently replay one W0 D6 research run"
    )
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.output is not None and _is_below(
            _absolute(args.run_root),
            str(_absolute(args.output)),
        ):
            _fail(
                "OUTPUT_INSIDE_ARTIFACT_ROOT",
                "replay output must not mutate the producer artifact root",
            )
        replay = replay_run(args.run_root)
        raw = canonical_json_bytes(replay)
        if args.output is None:
            sys.stdout.buffer.write(raw)
        else:
            _write_exclusive(args.output, raw)
    except KeyboardInterrupt:
        error = {
            "schema": "w0_d6_replay_error_v1",
            "status": "ERROR",
            "error_code": "INTERRUPTED",
            "detail": "independent replay interrupted",
            "conclusion": None,
        }
        sys.stderr.buffer.write(canonical_json_bytes(error))
        return 130
    except ReplayError as exc:
        error = {
            "schema": "w0_d6_replay_error_v1",
            "status": "ERROR",
            "error_code": exc.code,
            "detail": str(exc),
            "conclusion": None,
        }
        sys.stderr.buffer.write(canonical_json_bytes(error))
        return 2
    except Exception as exc:
        error = {
            "schema": "w0_d6_replay_error_v1",
            "status": "ERROR",
            "error_code": "INTERNAL_REPLAY_ERROR",
            "detail": f"{type(exc).__name__}: {exc}",
            "conclusion": None,
        }
        sys.stderr.buffer.write(canonical_json_bytes(error))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
