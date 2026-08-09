#!/usr/bin/env python3
"""Verify one sealed SMM4 authority package through retained file descriptors."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

from identity_contract_v1 import IdentityContractError, validate_full_identity


AUTHORITY_DIRECTORY_NAME = "authority-a001"
AUTHORITY_NAME = "authority.json"
SEAL_NAME = "SHA256SUMS"
MEMBER_NAMES = frozenset({AUTHORITY_NAME, SEAL_NAME})
STAT_FIELDS = (
    "st_dev",
    "st_ino",
    "st_mode",
    "st_nlink",
    "st_uid",
    "st_gid",
    "st_size",
    "st_mtime_ns",
    "st_ctime_ns",
)
LOWER_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class AuthorityPackageError(RuntimeError):
    """Raised when an authority package is malformed, unsealed, or unstable."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AuthorityPackageError(message)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _fingerprint(value: os.stat_result) -> tuple[int, ...]:
    return tuple(int(getattr(value, field)) for field in STAT_FIELDS)


def _require_stable(
    before: os.stat_result,
    after: os.stat_result,
    label: str,
) -> None:
    _require(_fingerprint(before) == _fingerprint(after), f"{label}: stat fields drifted")


def _require_same_object(
    opened: os.stat_result,
    named: os.stat_result,
    label: str,
) -> None:
    _require(
        (opened.st_dev, opened.st_ino) == (named.st_dev, named.st_ino),
        f"{label}: directory entry was renamed, swapped, or replaced",
    )


def _read_all(descriptor: int, expected_size: int, label: str) -> bytes:
    chunks: list[bytes] = []
    while True:
        block = os.read(descriptor, 1 << 20)
        if not block:
            break
        chunks.append(block)
    raw = b"".join(chunks)
    _require(len(raw) == expected_size, f"{label}: short or extended retained-FD read")
    return raw


def _strict_json_object(raw: bytes) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise AuthorityPackageError(f"authority.json: duplicate key {key!r}")
            value[key] = item
        return value

    def reject(number: str) -> Any:
        raise AuthorityPackageError(f"authority.json: non-integer JSON number {number!r}")

    try:
        value = json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthorityPackageError(f"authority.json: malformed JSON: {exc}") from exc
    _require(type(value) is dict, "authority.json: top-level value is not an object")
    return value


def _canonical_authority_directory(path: Path) -> str:
    raw_path = os.fspath(path)
    _require(os.path.isabs(raw_path), "authority directory: path must be absolute")
    normalized = os.path.normpath(raw_path)
    _require(raw_path == normalized, "authority directory: path is not normalized")
    _require(
        os.path.basename(normalized) == AUTHORITY_DIRECTORY_NAME,
        "authority directory: basename is not authority-a001",
    )
    _require(
        os.path.realpath(normalized) == normalized,
        "authority directory: path contains a symlink or alias",
    )
    return normalized


def _file_identity(
    directory: str,
    name: str,
    file_stat: os.stat_result,
    raw: bytes,
    label: str,
) -> dict[str, Any]:
    _require(stat.S_ISREG(file_stat.st_mode), f"{label}: not a regular file")
    _require(stat.S_IMODE(file_stat.st_mode) == 0o644, f"{label}: mode is not 0644")
    _require(file_stat.st_nlink == 1, f"{label}: link_count is not 1")
    identity = {
        "path": os.path.join(directory, name),
        "size_bytes": len(raw),
        "sha256": _sha256(raw),
        "mode_octal": "0644",
        "device": file_stat.st_dev,
        "inode": file_stat.st_ino,
        "link_count": file_stat.st_nlink,
    }
    try:
        return validate_full_identity(identity, label)
    except IdentityContractError as exc:
        raise AuthorityPackageError(f"{label}: invalid full identity: {exc}") from exc


def verify_authority_package(
    authority_directory: Path,
    package_id: str,
) -> dict[str, Any]:
    """Verify and return the exact authority bytes and full package identities.

    The caller supplies ``package_id`` from outside the package. The returned
    object has exactly ``authority_raw``, ``authority``, ``seal``, and
    ``package_id`` keys.
    """

    _require(
        type(package_id) is str and LOWER_SHA256.fullmatch(package_id) is not None,
        "package_id: expected lowercase 64-hex",
    )
    directory = _canonical_authority_directory(authority_directory)
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    file_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    directory_fd = -1
    authority_fd = -1
    seal_fd = -1
    try:
        directory_fd = os.open(directory, directory_flags)
        parent_before = os.fstat(directory_fd)
        named_parent_before = os.stat(directory, follow_symlinks=False)
        _require(stat.S_ISDIR(parent_before.st_mode), "authority directory: not a directory")
        _require(
            stat.S_IMODE(parent_before.st_mode) == 0o755,
            "authority directory: mode is not 0755",
        )
        _require_same_object(parent_before, named_parent_before, "authority directory")
        _require(
            set(os.listdir(directory_fd)) == MEMBER_NAMES,
            "authority directory: member set is not exact",
        )

        authority_fd = os.open(AUTHORITY_NAME, file_flags, dir_fd=directory_fd)
        seal_fd = os.open(SEAL_NAME, file_flags, dir_fd=directory_fd)
        authority_before = os.fstat(authority_fd)
        seal_before = os.fstat(seal_fd)
        named_authority_before = os.stat(AUTHORITY_NAME, dir_fd=directory_fd, follow_symlinks=False)
        named_seal_before = os.stat(SEAL_NAME, dir_fd=directory_fd, follow_symlinks=False)
        _require_same_object(authority_before, named_authority_before, AUTHORITY_NAME)
        _require_same_object(seal_before, named_seal_before, SEAL_NAME)
        _require(
            (authority_before.st_dev, authority_before.st_ino)
            != (seal_before.st_dev, seal_before.st_ino),
            "authority package: authority and seal are the same filesystem object",
        )
        _require(stat.S_ISREG(authority_before.st_mode), "authority.json: not a regular file")
        _require(stat.S_ISREG(seal_before.st_mode), "SHA256SUMS: not a regular file")
        _require(stat.S_IMODE(authority_before.st_mode) == 0o644, "authority.json: mode is not 0644")
        _require(stat.S_IMODE(seal_before.st_mode) == 0o644, "SHA256SUMS: mode is not 0644")
        _require(authority_before.st_nlink == 1, "authority.json: link_count is not 1")
        _require(seal_before.st_nlink == 1, "SHA256SUMS: link_count is not 1")

        authority_raw = _read_all(
            authority_fd,
            authority_before.st_size,
            AUTHORITY_NAME,
        )
        seal_raw = _read_all(seal_fd, seal_before.st_size, SEAL_NAME)

        authority_after = os.fstat(authority_fd)
        seal_after = os.fstat(seal_fd)
        parent_after = os.fstat(directory_fd)
        named_parent_after = os.stat(directory, follow_symlinks=False)
        named_authority_after = os.stat(AUTHORITY_NAME, dir_fd=directory_fd, follow_symlinks=False)
        named_seal_after = os.stat(SEAL_NAME, dir_fd=directory_fd, follow_symlinks=False)
        _require_stable(authority_before, authority_after, AUTHORITY_NAME)
        _require_stable(seal_before, seal_after, SEAL_NAME)
        _require_stable(parent_before, parent_after, "authority directory")
        _require_stable(named_parent_before, named_parent_after, "authority directory path")
        _require_same_object(parent_after, named_parent_after, "authority directory")
        _require_same_object(authority_after, named_authority_after, AUTHORITY_NAME)
        _require_same_object(seal_after, named_seal_after, SEAL_NAME)
        _require(
            set(os.listdir(directory_fd)) == MEMBER_NAMES,
            "authority directory: member set drifted",
        )
    except AuthorityPackageError:
        raise
    except OSError as exc:
        raise AuthorityPackageError(f"authority package filesystem check failed: {exc}") from exc
    finally:
        if seal_fd >= 0:
            os.close(seal_fd)
        if authority_fd >= 0:
            os.close(authority_fd)
        if directory_fd >= 0:
            os.close(directory_fd)

    _strict_json_object(authority_raw)
    expected_seal = f"{_sha256(authority_raw)}  {AUTHORITY_NAME}\n".encode("ascii")
    _require(seal_raw == expected_seal, "SHA256SUMS: seal bytes are not exact")
    _require(_sha256(seal_raw) == package_id, "package_id: external package id mismatch")
    authority_identity = _file_identity(
        directory,
        AUTHORITY_NAME,
        authority_after,
        authority_raw,
        AUTHORITY_NAME,
    )
    seal_identity = _file_identity(
        directory,
        SEAL_NAME,
        seal_after,
        seal_raw,
        SEAL_NAME,
    )
    return {
        "authority_raw": authority_raw,
        "authority": authority_identity,
        "seal": seal_identity,
        "package_id": package_id,
    }


__all__ = [
    "AUTHORITY_DIRECTORY_NAME",
    "AUTHORITY_NAME",
    "AuthorityPackageError",
    "MEMBER_NAMES",
    "SEAL_NAME",
    "STAT_FIELDS",
    "verify_authority_package",
]
