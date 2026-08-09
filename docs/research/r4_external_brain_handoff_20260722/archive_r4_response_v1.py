#!/usr/bin/env python3
"""Archive an R4 response as inert bytes and publish its canonical twin.

The response is never decoded, rendered, interpreted, or used to construct a
path, command, environment variable, or gate.  All control paths are supplied
by the local operator or fixed by this module.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
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
SELECTOR_PATH = RESEARCH_DIR / "select_r4_ready_receipt_v1.py"
DEFAULT_RESPONSE_ROOT = PROJECT_ROOT / ".artifacts/track_b_r4_external_brain_handoff_20260722/responses"
DEFAULT_CLEANROOM_DIR = PROJECT_ROOT / "docs/research/cleanroom_rederivation_20260718"
LOW_WATER_BYTES = 10 * 1024**3
CANONICAL_SUFFIX = "_r4_response_gpt_pro_verbatim.md"
IDENTITY_KEYS = {"relative_path", "size_bytes", "sha256"}
_PREFIX_RE = re.compile(r"^(\d{2,})_")


class ArchiveError(RuntimeError):
    """Fail-closed response archival error."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ArchiveError(f"symlink is not a provenance file: {path}")
    resolved = path.resolve(strict=True)
    mode = resolved.stat().st_mode
    if not stat.S_ISREG(mode):
        raise ArchiveError(f"not a regular provenance file: {resolved}")
    return {
        "path": str(resolved),
        "size_bytes": resolved.stat().st_size,
        "sha256": _sha256(resolved),
    }


def _strict_json(path: Path) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ArchiveError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise ArchiveError(f"non-finite JSON value in {path}: {value}")

    try:
        value = json.loads(
            path.read_bytes().decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArchiveError(f"cannot parse control JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ArchiveError(f"control JSON is not an object: {path}")
    return value


def _identity(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != IDENTITY_KEYS:
        raise ArchiveError(f"{label} is not an exact selected receipt identity")
    relative = value.get("relative_path")
    size = value.get("size_bytes")
    digest = value.get("sha256")
    if type(relative) is not str or not relative:
        raise ArchiveError(f"{label}.relative_path is malformed")
    pure = Path(relative)
    if pure.is_absolute() or "\\" in relative or any(part in {"", ".", ".."} for part in pure.parts):
        raise ArchiveError(f"{label}.relative_path is not normalized")
    if type(size) is not int or size < 0:
        raise ArchiveError(f"{label}.size_bytes is malformed")
    if type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ArchiveError(f"{label}.sha256 is malformed")
    return {"relative_path": relative, "size_bytes": size, "sha256": digest}


def _selector() -> ModuleType:
    if not SELECTOR_PATH.is_file() or SELECTOR_PATH.is_symlink():
        raise ArchiveError(f"local READY selector is unavailable: {SELECTOR_PATH}")
    name = "_r4_ready_selector_for_response_archive"
    spec = importlib.util.spec_from_file_location(name, SELECTOR_PATH)
    if spec is None or spec.loader is None:
        raise ArchiveError("cannot load local READY selector")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_selected_identity(authority_run: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    ready_path = authority_run / "ready/selected-receipt.json"
    ready = _strict_json(ready_path)
    identity = _identity(ready.get("selected_receipt_identity"), "selected_receipt_identity")
    selector = _selector()
    checker = getattr(selector, "check_selected_receipt", None)
    if not callable(checker):
        raise ArchiveError("local READY selector lacks check_selected_receipt")
    try:
        result = checker(authority_run, expected_identity=identity)
    except Exception as exc:
        raise ArchiveError(f"selected receipt failed semantic/byte replay: {exc}") from exc
    if not isinstance(result, Mapping):
        raise ArchiveError("selected receipt checker returned a malformed result")
    return identity, dict(result)


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
    raise ArchiveError(f"pending names exhausted for {path}")


def _publish_bytes(path: Path, raw: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise ArchiveError(f"no-overwrite target exists: {path}")
    pending = _pending_path(path)
    with pending.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.link(pending, path, follow_symlinks=False)
    _fsync_directory(path.parent)
    try:
        pending.unlink()
    except OSError:
        pass
    else:
        _fsync_directory(path.parent)


def _publish_json(path: Path, payload: Mapping[str, Any]) -> None:
    raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    _publish_bytes(path, raw)


def _copy_opaque(source: Path, destination: Path) -> dict[str, Any]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(source, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ArchiveError(f"response source is not regular: {source}")
        if destination.exists() or destination.is_symlink():
            raise ArchiveError(f"no-overwrite target exists: {destination}")
        pending = _pending_path(destination)
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
            raise ArchiveError("response source changed while being archived")
        os.link(pending, destination, follow_symlinks=False)
        _fsync_directory(destination.parent)
        try:
            pending.unlink()
        except OSError:
            pass
        else:
            _fsync_directory(destination.parent)
        record = _record(destination)
        if record["size_bytes"] != size or record["sha256"] != digest.hexdigest():
            raise ArchiveError("published raw response differs from copied bytes")
        return record
    finally:
        os.close(descriptor)


def _copy_published(source: Path, destination: Path) -> dict[str, Any]:
    if destination.exists() or destination.is_symlink():
        raise ArchiveError(f"canonical no-overwrite target exists: {destination}")
    pending = _pending_path(destination)
    with source.open("rb") as input_handle, pending.open("xb") as output_handle:
        shutil.copyfileobj(input_handle, output_handle, length=1024 * 1024)
        output_handle.flush()
        os.fsync(output_handle.fileno())
    os.link(pending, destination, follow_symlinks=False)
    _fsync_directory(destination.parent)
    try:
        pending.unlink()
    except OSError:
        pass
    else:
        _fsync_directory(destination.parent)
    return _record(destination)


def _next_canonical(cleanroom_dir: Path) -> Path:
    by_prefix: dict[int, str] = {}
    for child in cleanroom_dir.iterdir():
        match = _PREFIX_RE.match(child.name)
        if match is None:
            continue
        if child.is_symlink() or not child.is_file():
            raise ArchiveError(f"numbered cleanroom entry is not a regular file: {child}")
        number = int(match.group(1))
        if number in by_prefix:
            raise ArchiveError(f"duplicate cleanroom sequence number {number}: {by_prefix[number]}, {child.name}")
        by_prefix[number] = child.name
    if not by_prefix or sorted(by_prefix) != list(range(max(by_prefix) + 1)):
        raise ArchiveError("cleanroom numbered sequence is empty or non-contiguous")
    number = max(by_prefix) + 1
    return cleanroom_dir / f"{number:02d}{CANONICAL_SUFFIX}"


def _require_space(path: Path) -> None:
    free = shutil.disk_usage(path).free
    if free < LOW_WATER_BYTES:
        raise ArchiveError(f"artifact low-water gate failed: free={free}, required={LOW_WATER_BYTES}")


def archive_response(
    response_path: Path,
    authority_run: Path,
    output_dir: Path,
    *,
    cleanroom_dir: Path = DEFAULT_CLEANROOM_DIR,
) -> dict[str, Any]:
    """Archive one response without interpreting a single response byte."""
    response_path = response_path.absolute()
    authority_run = authority_run.resolve(strict=True)
    cleanroom_dir = cleanroom_dir.resolve(strict=True)
    if not cleanroom_dir.is_dir() or cleanroom_dir.is_symlink():
        raise ArchiveError(f"unsafe cleanroom directory: {cleanroom_dir}")
    output_dir = output_dir.absolute()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if output_dir.parent.is_symlink():
        raise ArchiveError(f"unsafe response-run parent: {output_dir.parent}")
    _require_space(output_dir.parent)
    output_dir.mkdir(mode=0o755, exist_ok=False)
    _fsync_directory(output_dir.parent)

    raw_path = output_dir / "response.verbatim.md"
    raw_record = _copy_opaque(response_path, raw_path)
    try:
        identity, selection = _load_selected_identity(authority_run)
    except Exception as exc:
        _publish_json(
            output_dir / "response-status.json",
            {
                "schema": "r4_response_archive_status_v1",
                "status": "RAW_ARCHIVED_PROVENANCE_BLOCKED",
                "created_at_utc": _utc_now(),
                "raw_response": raw_record,
                "error": f"{type(exc).__name__}: {exc}",
            },
        )
        if isinstance(exc, ArchiveError):
            raise
        raise ArchiveError(f"selected receipt provenance check failed: {exc}") from exc

    directory_fd = os.open(
        cleanroom_dir,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        fcntl.flock(directory_fd, fcntl.LOCK_EX)
        canonical_path: Path | None = None
        intent_path = output_dir / "canonical-intent.json"
        try:
            canonical_path = _next_canonical(cleanroom_dir)
            intent = {
                "schema": "r4_canonical_intent_v1",
                "created_at_utc": _utc_now(),
                "authority_run": str(authority_run),
                "package_id": selection.get("package_id"),
                "selected_receipt_identity": identity,
                "receipt_semantic_replay_pass": True,
                "receipt_detached_byte_match": True,
                "raw_response": raw_record,
                "canonical_target": str(canonical_path),
                "status": "PENDING_CANONICAL_PUBLICATION",
            }
            _publish_json(intent_path, intent)
            canonical_record = _copy_published(raw_path, canonical_path)
            if (raw_record["size_bytes"], raw_record["sha256"]) != (
                canonical_record["size_bytes"],
                canonical_record["sha256"],
            ):
                raise ArchiveError("raw and canonical response bytes differ")
            second_identity, second_selection = _load_selected_identity(authority_run)
            if second_identity != identity:
                raise ArchiveError("selected receipt identity changed during canonical publication")
            if second_selection.get("package_id") != selection.get("package_id"):
                raise ArchiveError("package identity changed during canonical publication")
            ingest = {
                "schema": "r4_response_ingest_v1",
                "created_at_utc": _utc_now(),
                "status": "ARCHIVED_PENDING_RECOMPUTATION",
                "authority_run": str(authority_run),
                "package_id": selection.get("package_id"),
                "selected_receipt_identity": identity,
                "receipt_semantic_replay_pass": True,
                "receipt_detached_byte_match": True,
                "raw_response": raw_record,
                "canonical_document": canonical_record,
                "raw_canonical_byte_equal": True,
                "encoder_return_authorized": False,
            }
            _publish_json(output_dir / "response-ingest.json", ingest)
            return ingest
        except BaseException as exc:
            canonical_published = bool(
                canonical_path is not None and canonical_path.exists() and not canonical_path.is_symlink()
            )
            status_payload: dict[str, Any] = {
                "schema": "r4_response_archive_status_v1",
                "status": "ARCHIVE_INCOMPLETE",
                "created_at_utc": _utc_now(),
                "raw_response": raw_record,
                "canonical_target": None if canonical_path is None else str(canonical_path),
                "canonical_published": canonical_published,
                "selected_receipt_identity": identity,
                "error": f"{type(exc).__name__}: {exc}",
                "encoder_return_authorized": False,
            }
            if canonical_published and canonical_path is not None:
                status_payload["canonical_document"] = _record(canonical_path)
            try:
                _publish_json(output_dir / "response-status.json", status_payload)
            except BaseException as status_exc:
                raise ArchiveError(
                    f"archive incomplete ({exc}); could not publish ARCHIVE_INCOMPLETE status ({status_exc})"
                ) from exc
            raise
    finally:
        fcntl.flock(directory_fd, fcntl.LOCK_UN)
        os.close(directory_fd)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--response", type=Path, required=True, help="operator-supplied response byte file")
    parser.add_argument("--authority-run", type=Path, required=True, help="sealed R4 package authority run")
    parser.add_argument("--output-dir", type=Path, required=True, help="new no-overwrite response run")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = archive_response(args.response, args.authority_run, args.output_dir)
    except (ArchiveError, FileExistsError, OSError) as exc:
        print(f"R4_RESPONSE_ARCHIVE_FAIL: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
