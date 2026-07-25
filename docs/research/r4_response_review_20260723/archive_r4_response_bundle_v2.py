#!/usr/bin/env python3
"""Archive the fixed three-file R4 response bundle as inert, exact bytes.

This module never decodes, parses, imports, compiles, executes, or renders an
external input.  Input bytes cannot select a path, command, field name, or
control-flow branch.  The read-only ``check`` command replays the complete
archive and READY binding without writing any file.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
from types import ModuleType
from typing import Any


RESEARCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = RESEARCH_DIR.parents[2]
HANDOFF_DIR = PROJECT_ROOT / "docs/research/r4_external_brain_handoff_20260722"
SELECTOR_PATH = HANDOFF_DIR / "select_r4_ready_receipt_v1.py"
LOW_WATER_BYTES = 10 * 1024**3
CANONICAL_START = 12
IDENTITY_KEYS = {"relative_path", "sha256", "size_bytes"}
SHA_RE = re.compile(r"[0-9a-f]{64}")
PREFIX_RE = re.compile(r"^(\d{2,})_")
SCHEMA_STATUS = "r4_response_bundle_archive_status_v2"
SCHEMA_INTENT = "r4_response_bundle_canonical_intent_v2"
SCHEMA_INGEST = "r4_response_bundle_ingest_v2"

SLOTS: tuple[dict[str, Any], ...] = (
    {
        "slot_id": "response_text",
        "raw_relative_path": "inputs/response_text.verbatim.bin",
        "canonical_number": 12,
        "canonical_name": "12_r4_response_gpt_pro_verbatim.md",
    },
    {
        "slot_id": "certificate_markdown",
        "raw_relative_path": "inputs/certificate_markdown.verbatim.bin",
        "canonical_number": 13,
        "canonical_name": "13_r4_next_certificate_gpt_pro_verbatim.md",
    },
    {
        "slot_id": "certificate_python",
        "raw_relative_path": "inputs/certificate_python.verbatim.bin",
        "canonical_number": 14,
        "canonical_name": "14_r4_next_certificate_python_gpt_pro_verbatim.md",
    },
)


class BundleArchiveError(RuntimeError):
    """Fail-closed three-file archival or replay error."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _regular_record(path: Path) -> dict[str, Any]:
    try:
        mode = path.lstat().st_mode
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise BundleArchiveError(f"cannot resolve provenance file {path}: {exc}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode) or resolved != path.absolute():
        raise BundleArchiveError(f"provenance path is not a canonical regular file: {path}")
    return {
        "path": str(resolved),
        "sha256": _sha256_path(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _strict_json(path: Path) -> dict[str, Any]:
    raw = _regular_bytes(path, "control JSON")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise BundleArchiveError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise BundleArchiveError(f"non-finite JSON value in {path}: {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleArchiveError(f"cannot parse control JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BundleArchiveError(f"control JSON is not an object: {path}")
    return value


def _regular_bytes(path: Path, label: str) -> bytes:
    record = _regular_record(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise BundleArchiveError(f"cannot read {label} {path}: {exc}") from exc
    if len(raw) != record["size_bytes"] or _sha256_bytes(raw) != record["sha256"]:
        raise BundleArchiveError(f"{label} changed while being read: {path}")
    return raw


def _selected_identity(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != IDENTITY_KEYS:
        raise BundleArchiveError(f"{label} is not an exact selected receipt identity")
    relative = value.get("relative_path")
    size = value.get("size_bytes")
    digest = value.get("sha256")
    if type(relative) is not str or not relative:
        raise BundleArchiveError(f"{label}.relative_path is malformed")
    pure = Path(relative)
    if pure.is_absolute() or "\\" in relative or any(part in {"", ".", ".."} for part in pure.parts):
        raise BundleArchiveError(f"{label}.relative_path is not normalized")
    if type(size) is not int or size < 0:
        raise BundleArchiveError(f"{label}.size_bytes is malformed")
    if type(digest) is not str or SHA_RE.fullmatch(digest) is None:
        raise BundleArchiveError(f"{label}.sha256 is malformed")
    return {"relative_path": relative, "sha256": digest, "size_bytes": size}


def _selector() -> ModuleType:
    if SELECTOR_PATH.is_symlink() or not SELECTOR_PATH.is_file():
        raise BundleArchiveError(f"local READY selector is unavailable: {SELECTOR_PATH}")
    name = "_r4_ready_selector_for_bundle_archive_v2"
    spec = importlib.util.spec_from_file_location(name, SELECTOR_PATH)
    if spec is None or spec.loader is None:
        raise BundleArchiveError("cannot load local READY selector")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _authority_binding(
    authority_run: Path,
    *,
    expected_package_id: str,
    expected_manifest_sha256: str,
    expected_receipt_identity: Mapping[str, Any],
) -> dict[str, Any]:
    authority_run = authority_run.resolve(strict=True)
    ready_path = authority_run / "ready/selected-receipt.json"
    ready = _strict_json(ready_path)
    ready_identity = _selected_identity(ready.get("selected_receipt_identity"), "READY selected receipt identity")
    expected = _selected_identity(expected_receipt_identity, "expected selected receipt identity")
    if ready_identity != expected:
        raise BundleArchiveError("READY selected receipt identity differs from the operator-pinned identity")
    selector = _selector()
    checker = getattr(selector, "check_selected_receipt", None)
    if not callable(checker):
        raise BundleArchiveError("local READY selector lacks check_selected_receipt")
    try:
        result = checker(authority_run, expected_identity=expected)
    except Exception as exc:
        raise BundleArchiveError(f"selected receipt failed semantic/byte replay: {exc}") from exc
    if not isinstance(result, Mapping):
        raise BundleArchiveError("selected receipt checker returned a malformed result")
    if (
        result.get("status") != "READY_FOR_MANUAL_EXTERNAL_SUBMISSION"
        or result.get("package_id") != expected_package_id
        or result.get("manifest_sha256") != expected_manifest_sha256
        or result.get("selected_receipt_identity") != expected
    ):
        raise BundleArchiveError("READY replay differs from the operator-pinned authority identity")
    return {
        "run_dir": str(authority_run),
        "manifest_sha256": expected_manifest_sha256,
        "package_id": expected_package_id,
        "ready_selection": _regular_record(ready_path),
        "receipt_detached_byte_match": True,
        "receipt_semantic_replay_pass": True,
        "selected_receipt_identity": expected,
        "selector_tool": _regular_record(SELECTOR_PATH),
    }


def _source_identity(path: Path) -> dict[str, Any]:
    path = path.absolute()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise BundleArchiveError(f"cannot open inert input {path}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise BundleArchiveError(f"inert input is not a regular file: {path}")
        resolved = path.resolve(strict=True)
        if resolved != path:
            raise BundleArchiveError(f"inert input path contains a symlink or alias: {path}")
        digest = hashlib.sha256()
        size = 0
        with os.fdopen(os.dup(descriptor), "rb", closefd=True) as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise BundleArchiveError(f"inert input changed while being hashed: {path}")
        return {"path": str(resolved), "sha256": digest.hexdigest(), "size_bytes": size}
    finally:
        os.close(descriptor)


def _require_expected(record: Mapping[str, Any], expected: Mapping[str, Any], slot_id: str) -> None:
    if record.get("size_bytes") != expected.get("size_bytes") or record.get("sha256") != expected.get("sha256"):
        raise BundleArchiveError(
            f"{slot_id} identity mismatch: "
            f"actual={record.get('size_bytes')}/{record.get('sha256')}, "
            f"expected={expected.get('size_bytes')}/{expected.get('sha256')}"
        )


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _pending_path(path: Path) -> Path:
    for number in range(1, 1_000_000):
        candidate = path.with_name(f".{path.name}.pending-{number:06d}")
        if not candidate.exists() and not candidate.is_symlink():
            return candidate
    raise BundleArchiveError(f"pending names exhausted for {path}")


def _publish_bytes(path: Path, raw: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise BundleArchiveError(f"no-overwrite target exists: {path}")
    pending = _pending_path(path)
    try:
        with pending.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(pending, path, follow_symlinks=False)
        _fsync_directory(path.parent)
    finally:
        pending.unlink(missing_ok=True)
    _fsync_directory(path.parent)


def _publish_json(path: Path, payload: Mapping[str, Any]) -> None:
    raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    _publish_bytes(path, raw)


def _copy_opaque(
    source: Path,
    destination: Path,
    *,
    expected: Mapping[str, Any],
    slot_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = source.absolute()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(source, flags)
    except OSError as exc:
        raise BundleArchiveError(f"cannot open inert input {source}: {exc}") from exc
    pending = _pending_path(destination)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise BundleArchiveError(f"inert input is not a regular file: {source}")
        resolved = source.resolve(strict=True)
        if resolved != source:
            raise BundleArchiveError(f"inert input path contains a symlink or alias: {source}")
        digest = hashlib.sha256()
        size = 0
        with os.fdopen(os.dup(descriptor), "rb", closefd=True) as input_handle, pending.open("xb") as output_handle:
            for chunk in iter(lambda: input_handle.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
                output_handle.write(chunk)
            output_handle.flush()
            os.fsync(output_handle.fileno())
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise BundleArchiveError(f"inert input changed while being copied: {source}")
        source_record = {"path": str(resolved), "sha256": digest.hexdigest(), "size_bytes": size}
        _require_expected(source_record, expected, slot_id)
        if destination.exists() or destination.is_symlink():
            raise BundleArchiveError(f"no-overwrite target exists: {destination}")
        os.link(pending, destination, follow_symlinks=False)
        _fsync_directory(destination.parent)
        raw_record = _regular_record(destination)
        if (raw_record["size_bytes"], raw_record["sha256"]) != (size, digest.hexdigest()):
            raise BundleArchiveError(f"{slot_id} raw artifact differs from copied bytes")
        return source_record, raw_record
    finally:
        os.close(descriptor)
        pending.unlink(missing_ok=True)


def _copy_published(source: Path, destination: Path) -> dict[str, Any]:
    if destination.exists() or destination.is_symlink():
        raise BundleArchiveError(f"canonical no-overwrite target exists: {destination}")
    pending = _pending_path(destination)
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(source, flags)
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise BundleArchiveError(f"raw artifact is not regular: {source}")
            with os.fdopen(os.dup(descriptor), "rb", closefd=True) as input_handle, pending.open("xb") as output_handle:
                shutil.copyfileobj(input_handle, output_handle, length=1024 * 1024)
                output_handle.flush()
                os.fsync(output_handle.fileno())
            after = os.fstat(descriptor)
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
            ):
                raise BundleArchiveError(f"raw artifact changed while publishing canonical bytes: {source}")
        finally:
            os.close(descriptor)
        os.link(pending, destination, follow_symlinks=False)
        _fsync_directory(destination.parent)
        return _regular_record(destination)
    finally:
        pending.unlink(missing_ok=True)


def _numbered_cleanroom(cleanroom_dir: Path) -> dict[int, str]:
    by_number: dict[int, str] = {}
    for child in cleanroom_dir.iterdir():
        match = PREFIX_RE.match(child.name)
        if match is None:
            continue
        if child.is_symlink() or not child.is_file() or child.resolve() != child.absolute():
            raise BundleArchiveError(f"numbered cleanroom entry is not a canonical regular file: {child}")
        number = int(match.group(1))
        if number in by_number:
            raise BundleArchiveError(f"duplicate cleanroom sequence number {number}: {by_number[number]}, {child.name}")
        by_number[number] = child.name
    if not by_number or sorted(by_number) != list(range(max(by_number) + 1)):
        raise BundleArchiveError("cleanroom numbered sequence is empty or non-contiguous")
    return by_number


def _archive_targets(cleanroom_dir: Path) -> dict[str, Path]:
    numbered = _numbered_cleanroom(cleanroom_dir)
    if max(numbered) != CANONICAL_START - 1:
        raise BundleArchiveError(f"cleanroom next number is not {CANONICAL_START}: current maximum is {max(numbered)}")
    return {str(slot["slot_id"]): cleanroom_dir / str(slot["canonical_name"]) for slot in SLOTS}


def _check_targets(cleanroom_dir: Path) -> dict[str, Path]:
    numbered = _numbered_cleanroom(cleanroom_dir)
    targets: dict[str, Path] = {}
    for slot in SLOTS:
        number = int(slot["canonical_number"])
        name = str(slot["canonical_name"])
        if numbered.get(number) != name:
            raise BundleArchiveError(f"cleanroom entry {number} is {numbered.get(number)!r}, expected {name!r}")
        targets[str(slot["slot_id"])] = cleanroom_dir / name
    return targets


def _validate_sha(value: str, label: str) -> str:
    if SHA_RE.fullmatch(value) is None:
        raise BundleArchiveError(f"{label} is not a lowercase SHA-256")
    return value


def _expected_inputs(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for slot in SLOTS:
        slot_id = str(slot["slot_id"])
        size = getattr(args, f"{slot_id}_size")
        digest = getattr(args, f"{slot_id}_sha256")
        if type(size) is not int or size < 0:
            raise BundleArchiveError(f"{slot_id} expected size is invalid")
        result[slot_id] = {"sha256": _validate_sha(digest, f"{slot_id} expected SHA-256"), "size_bytes": size}
    return result


def _input_paths(args: argparse.Namespace) -> dict[str, Path]:
    return {str(slot["slot_id"]): getattr(args, str(slot["slot_id"])).absolute() for slot in SLOTS}


def _expected_receipt(args: argparse.Namespace) -> dict[str, Any]:
    return _selected_identity(
        {
            "relative_path": args.expected_receipt_relative_path,
            "sha256": _validate_sha(args.expected_receipt_sha256, "expected receipt SHA-256"),
            "size_bytes": args.expected_receipt_size,
        },
        "expected selected receipt identity",
    )


def _resolve_directories(
    authority_run: Path,
    output_dir: Path,
    cleanroom_dir: Path,
    *,
    create_response_parent: bool,
) -> tuple[Path, Path, Path]:
    authority = authority_run.resolve(strict=True)
    if not authority.is_dir() or authority.is_symlink():
        raise BundleArchiveError(f"unsafe authority run: {authority_run}")
    cleanroom = cleanroom_dir.resolve(strict=True)
    if (
        not cleanroom.is_dir()
        or cleanroom_dir.absolute() != cleanroom
        or cleanroom_dir.is_symlink()
        or cleanroom != (PROJECT_ROOT / "docs/research/cleanroom_rederivation_20260718").resolve()
    ):
        raise BundleArchiveError(f"unsafe or unexpected cleanroom directory: {cleanroom_dir}")
    output = output_dir.absolute()
    expected_parent = authority.parent / "responses"
    if output.parent != expected_parent:
        raise BundleArchiveError(f"response run must be a direct child of {expected_parent}")
    if create_response_parent:
        expected_parent.mkdir(mode=0o755, exist_ok=True)
    if (
        not expected_parent.is_dir()
        or expected_parent.is_symlink()
        or expected_parent.resolve(strict=True) != expected_parent
    ):
        raise BundleArchiveError(f"unsafe response-run parent: {expected_parent}")
    return authority, output, cleanroom


def _tool_binding() -> dict[str, Any]:
    return _regular_record(Path(__file__).resolve())


def _status_payload(
    *,
    authority_run: Path,
    output_dir: Path,
    error: BaseException,
) -> dict[str, Any]:
    return {
        "archive_complete": False,
        "authority_run": str(authority_run),
        "created_at_utc": _utc_now(),
        "encoder_return_authorized": False,
        "error": f"{type(error).__name__}: {error}",
        "output_dir": str(output_dir),
        "schema": SCHEMA_STATUS,
        "status": "ARCHIVE_INCOMPLETE",
    }


def archive_bundle(args: argparse.Namespace) -> dict[str, Any]:
    """Publish one immutable three-slot bundle without interpreting input bytes."""
    expected_inputs = _expected_inputs(args)
    expected_receipt = _expected_receipt(args)
    package_id = _validate_sha(args.expected_package_id, "expected package ID")
    manifest_sha256 = _validate_sha(args.expected_manifest_sha256, "expected manifest SHA-256")
    authority, output_dir, cleanroom = _resolve_directories(
        args.authority_run,
        args.output_dir,
        args.cleanroom_dir,
        create_response_parent=True,
    )
    free = shutil.disk_usage(authority).free
    if free < LOW_WATER_BYTES:
        raise BundleArchiveError(f"artifact low-water gate failed: free={free}, required={LOW_WATER_BYTES}")
    if output_dir.exists() or output_dir.is_symlink():
        raise BundleArchiveError(f"no-overwrite response run exists: {output_dir}")
    output_dir.mkdir(mode=0o755, exist_ok=False)
    _fsync_directory(output_dir.parent)
    paths = _input_paths(args)
    try:
        authority_binding = _authority_binding(
            authority,
            expected_package_id=package_id,
            expected_manifest_sha256=manifest_sha256,
            expected_receipt_identity=expected_receipt,
        )
        inputs_dir = output_dir / "inputs"
        inputs_dir.mkdir(mode=0o755, exist_ok=False)
        archived: list[dict[str, Any]] = []
        for slot in SLOTS:
            slot_id = str(slot["slot_id"])
            raw_path = output_dir / str(slot["raw_relative_path"])
            source_record, raw_record = _copy_opaque(
                paths[slot_id],
                raw_path,
                expected=expected_inputs[slot_id],
                slot_id=slot_id,
            )
            archived.append(
                {
                    "canonical_target": None,
                    "expected_identity": expected_inputs[slot_id],
                    "input_id": slot_id,
                    "raw_document": raw_record,
                    "source_identity_at_archive": source_record,
                }
            )
        _fsync_directory(inputs_dir)
        directory_fd = os.open(
            cleanroom,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            fcntl.flock(directory_fd, fcntl.LOCK_EX)
            targets = _archive_targets(cleanroom)
            for item in archived:
                item["canonical_target"] = str(targets[str(item["input_id"])])
            intent = {
                "archiver_tool": _tool_binding(),
                "authority": authority_binding,
                "created_at_utc": _utc_now(),
                "encoder_return_authorized": False,
                "inputs": archived,
                "schema": SCHEMA_INTENT,
                "status": "PENDING_CANONICAL_PUBLICATION",
            }
            intent_path = output_dir / "canonical-intent.json"
            _publish_json(intent_path, intent)
            completed: list[dict[str, Any]] = []
            for item in archived:
                slot_id = str(item["input_id"])
                canonical = _copy_published(Path(str(item["raw_document"]["path"])), targets[slot_id])
                if (
                    canonical["size_bytes"],
                    canonical["sha256"],
                ) != (
                    item["raw_document"]["size_bytes"],
                    item["raw_document"]["sha256"],
                ):
                    raise BundleArchiveError(f"{slot_id} raw and canonical bytes differ")
                completed.append(
                    {
                        "canonical_document": canonical,
                        "expected_identity": item["expected_identity"],
                        "input_id": slot_id,
                        "raw_document": item["raw_document"],
                        "raw_canonical_byte_equal": True,
                        "source_identity_at_archive": item["source_identity_at_archive"],
                    }
                )
            second_authority = _authority_binding(
                authority,
                expected_package_id=package_id,
                expected_manifest_sha256=manifest_sha256,
                expected_receipt_identity=expected_receipt,
            )
            if second_authority != authority_binding:
                raise BundleArchiveError("authority binding changed during canonical publication")
            for item in completed:
                slot_id = str(item["input_id"])
                current = _source_identity(paths[slot_id])
                _require_expected(current, expected_inputs[slot_id], slot_id)
                if current != item["source_identity_at_archive"]:
                    raise BundleArchiveError(f"{slot_id} source changed after raw archival")
            ingest = {
                "all_raw_canonical_byte_equal": True,
                "archive_complete": True,
                "archiver_tool": _tool_binding(),
                "authority": authority_binding,
                "canonical_intent": _regular_record(intent_path),
                "created_at_utc": _utc_now(),
                "encoder_return_authorized": False,
                "external_bytes_executed": False,
                "input_count": len(completed),
                "inputs": completed,
                "schema": SCHEMA_INGEST,
                "status": "ARCHIVED_PENDING_RECOMPUTATION",
            }
            _publish_json(output_dir / "response-ingest.json", ingest)
            return ingest
        finally:
            fcntl.flock(directory_fd, fcntl.LOCK_UN)
            os.close(directory_fd)
    except BaseException as exc:
        try:
            _publish_json(
                output_dir / "response-status.json",
                _status_payload(authority_run=authority, output_dir=output_dir, error=exc),
            )
        except BaseException as status_exc:
            raise BundleArchiveError(
                f"archive incomplete ({exc}); could not publish ARCHIVE_INCOMPLETE status ({status_exc})"
            ) from exc
        raise


def _expect_mapping(value: Any, label: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise BundleArchiveError(f"{label} has an unexpected schema")
    return dict(value)


def check_bundle(response_run: Path, authority_run: Path) -> dict[str, Any]:
    """Return normalized bundle provenance after a complete read-only replay."""
    authority = authority_run.resolve(strict=True)
    output_dir = response_run.absolute()
    cleanroom = (PROJECT_ROOT / "docs/research/cleanroom_rederivation_20260718").resolve(strict=True)
    expected_parent = authority.parent / "responses"
    if output_dir.parent != expected_parent:
        raise BundleArchiveError(f"response run must be a direct child of {expected_parent}")
    if output_dir.is_symlink() or output_dir.resolve(strict=True) != output_dir or not output_dir.is_dir():
        raise BundleArchiveError(f"unsafe response run: {output_dir}")
    if (output_dir / "response-status.json").exists() or (output_dir / "response-status.json").is_symlink():
        raise BundleArchiveError("completed archive contains an INCOMPLETE status record")
    intent = _strict_json(output_dir / "canonical-intent.json")
    ingest = _strict_json(output_dir / "response-ingest.json")
    intent_keys = {
        "archiver_tool",
        "authority",
        "created_at_utc",
        "encoder_return_authorized",
        "inputs",
        "schema",
        "status",
    }
    ingest_keys = {
        "all_raw_canonical_byte_equal",
        "archive_complete",
        "archiver_tool",
        "authority",
        "canonical_intent",
        "created_at_utc",
        "encoder_return_authorized",
        "external_bytes_executed",
        "input_count",
        "inputs",
        "schema",
        "status",
    }
    _expect_mapping(intent, "canonical intent", intent_keys)
    _expect_mapping(ingest, "response ingest", ingest_keys)
    if (
        intent.get("schema") != SCHEMA_INTENT
        or intent.get("status") != "PENDING_CANONICAL_PUBLICATION"
        or intent.get("encoder_return_authorized") is not False
        or ingest.get("schema") != SCHEMA_INGEST
        or ingest.get("status") != "ARCHIVED_PENDING_RECOMPUTATION"
        or ingest.get("archive_complete") is not True
        or ingest.get("encoder_return_authorized") is not False
        or ingest.get("external_bytes_executed") is not False
        or ingest.get("input_count") != len(SLOTS)
        or ingest.get("all_raw_canonical_byte_equal") is not True
    ):
        raise BundleArchiveError("archive state fields do not describe one completed inert archive")
    recorded_authority = _expect_mapping(
        ingest.get("authority"),
        "response ingest authority",
        {
            "manifest_sha256",
            "package_id",
            "ready_selection",
            "receipt_detached_byte_match",
            "receipt_semantic_replay_pass",
            "run_dir",
            "selected_receipt_identity",
            "selector_tool",
        },
    )
    package_id = recorded_authority.get("package_id")
    manifest_sha256 = recorded_authority.get("manifest_sha256")
    if type(package_id) is not str or type(manifest_sha256) is not str:
        raise BundleArchiveError("response ingest authority hashes are malformed")
    _validate_sha(package_id, "recorded package ID")
    _validate_sha(manifest_sha256, "recorded manifest SHA-256")
    receipt_identity = _selected_identity(
        recorded_authority.get("selected_receipt_identity"),
        "recorded selected receipt identity",
    )
    authority_binding = _authority_binding(
        authority,
        expected_package_id=package_id,
        expected_manifest_sha256=manifest_sha256,
        expected_receipt_identity=receipt_identity,
    )
    targets = _check_targets(cleanroom)
    tool = _tool_binding()
    if (
        intent.get("archiver_tool") != tool
        or ingest.get("archiver_tool") != tool
        or intent.get("authority") != authority_binding
        or ingest.get("authority") != authority_binding
        or ingest.get("canonical_intent") != _regular_record(output_dir / "canonical-intent.json")
    ):
        raise BundleArchiveError("archive tool, authority, or intent provenance binding differs")
    intent_inputs = intent.get("inputs")
    ingest_inputs = ingest.get("inputs")
    if not isinstance(intent_inputs, list) or not isinstance(ingest_inputs, list):
        raise BundleArchiveError("archive input manifests are not arrays")
    if len(intent_inputs) != len(SLOTS) or len(ingest_inputs) != len(SLOTS):
        raise BundleArchiveError("archive input manifests do not contain exactly three slots")
    checked: list[dict[str, Any]] = []
    for index, slot in enumerate(SLOTS):
        slot_id = str(slot["slot_id"])
        intent_item = _expect_mapping(
            intent_inputs[index],
            f"intent input {slot_id}",
            {
                "canonical_target",
                "expected_identity",
                "input_id",
                "raw_document",
                "source_identity_at_archive",
            },
        )
        ingest_item = _expect_mapping(
            ingest_inputs[index],
            f"ingest input {slot_id}",
            {
                "canonical_document",
                "expected_identity",
                "input_id",
                "raw_document",
                "raw_canonical_byte_equal",
                "source_identity_at_archive",
            },
        )
        expected_identity = _expect_mapping(
            ingest_item.get("expected_identity"),
            f"{slot_id} expected identity",
            {"sha256", "size_bytes"},
        )
        source_at_archive = _expect_mapping(
            ingest_item.get("source_identity_at_archive"),
            f"{slot_id} source identity",
            {"path", "sha256", "size_bytes"},
        )
        source_path = source_at_archive.get("path")
        if type(source_path) is not str or not Path(source_path).is_absolute():
            raise BundleArchiveError(f"{slot_id} source path is malformed")
        _require_expected(source_at_archive, expected_identity, slot_id)
        raw_path = output_dir / str(slot["raw_relative_path"])
        raw_record = _regular_record(raw_path)
        canonical_record = _regular_record(targets[slot_id])
        expected_intent = {
            "canonical_target": str(targets[slot_id]),
            "expected_identity": expected_identity,
            "input_id": slot_id,
            "raw_document": raw_record,
            "source_identity_at_archive": source_at_archive,
        }
        expected_ingest = {
            "canonical_document": canonical_record,
            "expected_identity": expected_identity,
            "input_id": slot_id,
            "raw_document": raw_record,
            "raw_canonical_byte_equal": True,
            "source_identity_at_archive": source_at_archive,
        }
        if intent_item != expected_intent or ingest_item != expected_ingest:
            raise BundleArchiveError(f"{slot_id} provenance fields differ from current exact replay")
        if (
            raw_record["size_bytes"],
            raw_record["sha256"],
        ) != (
            canonical_record["size_bytes"],
            canonical_record["sha256"],
        ):
            raise BundleArchiveError(f"{slot_id} raw and canonical bytes differ")
        checked.append(expected_ingest)
    normalized = dict(ingest)
    normalized["authority"] = authority_binding
    normalized["canonical_intent"] = _regular_record(output_dir / "canonical-intent.json")
    normalized["inputs"] = checked
    normalized["response_ingest"] = _regular_record(output_dir / "response-ingest.json")
    return normalized


def _check_cli_bundle(args: argparse.Namespace) -> dict[str, Any]:
    expected_inputs = _expected_inputs(args)
    expected_receipt = _expected_receipt(args)
    package_id = _validate_sha(args.expected_package_id, "expected package ID")
    manifest_sha256 = _validate_sha(args.expected_manifest_sha256, "expected manifest SHA-256")
    authority, output_dir, _cleanroom = _resolve_directories(
        args.authority_run,
        args.output_dir,
        args.cleanroom_dir,
        create_response_parent=False,
    )
    normalized = check_bundle(output_dir, authority)
    authority_binding = normalized.get("authority")
    if not isinstance(authority_binding, Mapping):
        raise BundleArchiveError("normalized archive authority is malformed")
    if (
        authority_binding.get("package_id") != package_id
        or authority_binding.get("manifest_sha256") != manifest_sha256
        or authority_binding.get("selected_receipt_identity") != expected_receipt
    ):
        raise BundleArchiveError("normalized archive differs from the operator-pinned authority")
    paths = _input_paths(args)
    inputs = normalized.get("inputs")
    if not isinstance(inputs, list) or len(inputs) != len(SLOTS):
        raise BundleArchiveError("normalized archive input set is malformed")
    for index, slot in enumerate(SLOTS):
        slot_id = str(slot["slot_id"])
        item = inputs[index]
        if not isinstance(item, Mapping):
            raise BundleArchiveError(f"normalized {slot_id} input is malformed")
        if (
            item.get("input_id") != slot_id
            or item.get("expected_identity") != expected_inputs[slot_id]
            or item.get("source_identity_at_archive") != _source_identity(paths[slot_id])
        ):
            raise BundleArchiveError(f"normalized {slot_id} input differs from the operator-pinned identity")
    return normalized


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--authority-run", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--cleanroom-dir", required=True, type=Path)
    parser.add_argument("--expected-package-id", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--expected-receipt-relative-path", required=True)
    parser.add_argument("--expected-receipt-size", required=True, type=int)
    parser.add_argument("--expected-receipt-sha256", required=True)
    for slot in SLOTS:
        slot_id = str(slot["slot_id"])
        option = slot_id.replace("_", "-")
        parser.add_argument(f"--{option}", dest=slot_id, required=True, type=Path)
        parser.add_argument(f"--{option}-size", dest=f"{slot_id}_size", required=True, type=int)
        parser.add_argument(f"--{option}-sha256", dest=f"{slot_id}_sha256", required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_common_arguments(subparsers.add_parser("archive", help="publish one new no-overwrite response bundle"))
    _add_common_arguments(subparsers.add_parser("check", help="read-only replay of a completed response bundle"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = archive_bundle(args) if args.command == "archive" else _check_cli_bundle(args)
    except (BundleArchiveError, FileExistsError, OSError) as exc:
        print(
            json.dumps(
                {"error": f"{type(exc).__name__}: {exc}", "schema": "r4_response_bundle_cli_v2", "status": "FAIL"},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
