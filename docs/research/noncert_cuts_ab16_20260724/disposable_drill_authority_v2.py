#!/usr/bin/env python3
"""Build one no-overwrite, non-authorizing AB16 disposable-drill authority.

The resulting directory is deliberately outside every formal campaign root.
It binds the complete Gate-A planned source set, the live manager/boot epoch,
the small drill resource contract, and the exact lifecycle entry points.  It
creates no unit and grants no solver, organic-arm, or formal-campaign
authority.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import time
from typing import Any


RESEARCH_DIR = Path(__file__).resolve().parent
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

import ab16_campaign_bootstrap_v2 as bootstrap  # noqa: E402
import organic_resource_lifecycle_v2 as lifecycle  # noqa: E402
import organic_resource_verifier_v2 as verifier  # noqa: E402


AUTHORITY_SCHEMA = "noncert-cuts-ab16-disposable-drill-authority-v2"
ROOT_SCHEMA = "noncert-cuts-ab16-disposable-drill-root-v2"
CONTROL_SCHEMA = "noncert-cuts-ab16-disposable-drill-control-v2"
PACKAGE_SCHEMA = "noncert-cuts-ab16-disposable-drill-package-manifest-v2"
RESULT_SCHEMA = "noncert-cuts-ab16-disposable-drill-authority-result-v2"
PURPOSE = "AB16_GATE_A_DISPOSABLE_DRILL_AUTHORITY"
PACKAGE_PURPOSE = "AB16_GATE_A_DISPOSABLE_DRILL_SOURCE_PACKAGE"
RESULT_PURPOSE = "AB16_GATE_A_DISPOSABLE_DRILL_AUTHORITY_READY"
DRILL_SLOT = "region-capacity-ab-control"
RUN_NONCE_RE = re.compile(r"drill-[A-Za-z0-9][A-Za-z0-9_.-]{4,95}\Z")
HISTORY_FREEZE_SCHEMA = "noncert-cuts-ab16-terminal-reference-history-freeze-v1"
HISTORY_FREEZE_PURPOSE = "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_FREEZE"
HISTORY_FREEZE_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
HISTORY_FREEZE_MANIFEST_SHA256 = (
    "f1a2edd604f06cb958258ea5bfcb3cc8a7ad154cbce184cd73e6a9b15302f619"
)
HISTORY_FREEZE_MANIFEST_SIZE = 15_584
HISTORY_REPLAY_SCHEMA = "noncert-cuts-ab16-terminal-reference-history-replay-v2"
HISTORY_SOURCE_COMMIT = "c0a4aa717ccb3f1dbc7cd26a581934c47b7a14eb"
HISTORY_SOURCE_TREE = "1bae4f350bfdb1d7b51058cad0849c27af71b4c9"
HISTORY_SOURCE_GLOB = "docs/research/noncert_cuts_ab16_20260724/*_v1.py"
HISTORY_ARTIFACT_COUNT = 53
HISTORY_SOURCE_COUNT = 14
HISTORY_REPOSITORY_ROOT = Path(
    "/home/zhuran24/zmd-pj-codex-baselines/noncert-cuts-ab-trust-20260723"
)
HISTORY_FREEZE_MANIFEST_PATH = (
    HISTORY_REPOSITORY_ROOT
    / ".artifacts/noncert_cuts_ab16_20260724/"
    "gate-a-terminal-reference-history-freeze-a001/manifest.json"
)
HISTORY_FREEZE_MANIFEST_MODE = 0o400
HISTORY_FROZEN_ROOTS = (
    ".artifacts/noncert_cuts_ab16_20260724/gate-a-20260724T043946Z-XBW4l8",
    ".artifacts/noncert_cuts_ab16_20260724/gate-a-recovery-20260724T045351Z-mgZ1wQ",
)

TOOL_SOURCE_ROLES = {
    "busctl": "system.busctl",
    "manager_attestor": "script.manager_attestor_v4",
    "manager_epoch_authority": "script.campaign_authority_v4",
    "organic_arm_runner": "script.organic_arm_runner_v1",
    "organic_resource_lifecycle": "script.organic_resource_lifecycle_v2",
    "organic_resource_verifier": "script.organic_resource_verifier_v2",
    "organic_unit_orchestrator": "script.organic_unit_orchestrator_v2",
    "python3_13": "system.python3_13",
    "systemd_unit_reference": "script.systemd_unit_reference_v1",
    "sudo": "system.sudo",
    "systemctl": "system.systemctl",
    "systemd_run": "system.systemd_run",
}


class DrillAuthorityError(RuntimeError):
    """The disposable authority could not be built without ambiguity."""


class _HistoryDescriptor:
    """Own exactly one descriptor until explicit release."""

    def __init__(self, descriptor: int | None = None) -> None:
        self._descriptor = descriptor

    @property
    def descriptor(self) -> int:
        if self._descriptor is None:
            raise RuntimeError("history descriptor ownership is absent")
        return self._descriptor

    def acquire(self, descriptor: int) -> None:
        if self._descriptor is not None:
            raise RuntimeError("history descriptor ownership already exists")
        self._descriptor = descriptor

    def release(self) -> int:
        descriptor = self.descriptor
        self._descriptor = None
        return descriptor

    def close(self) -> BaseException | None:
        descriptor = self._descriptor
        self._descriptor = None
        if descriptor is None:
            return None
        try:
            os.close(descriptor)
        except BaseException as exc:
            return exc
        return None


def _close_history_descriptors(
    owners: Sequence[_HistoryDescriptor],
    *,
    primary: BaseException | None,
) -> None:
    cleanup_error: BaseException | None = None
    for owner in owners:
        error = owner.close()
        if error is None:
            continue
        detail = (
            "history descriptor cleanup failed: "
            f"{type(error).__name__}: {error}"
        )
        if primary is not None:
            primary.add_note(detail)
        elif cleanup_error is None:
            error.add_note(detail)
            cleanup_error = error
        else:
            cleanup_error.add_note(detail)
    if primary is None and cleanup_error is not None:
        raise cleanup_error


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _identity(value: Mapping[str, Any]) -> dict[str, object]:
    return {
        "mode": value["mode"],
        "path": value["path"],
        "sha256": value["sha256"],
        "size_bytes": value["size_bytes"],
    }


def _snapshot_identity(path: Path | str) -> dict[str, object]:
    return dict(lifecycle.snapshot_regular(_absolute(path)).identity)


def _write(path: Path, value: object) -> dict[str, object]:
    return lifecycle.write_json_exclusive(path, value)


def _mkdir(path: Path) -> None:
    try:
        path.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise DrillAuthorityError(f"no-overwrite directory already exists: {path}") from exc


def _capture_live_manager_epoch(
    planned_sources: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    """Observe the current epoch with only identities in the planned set."""

    try:
        captured = bootstrap.authority.capture_manager_epoch_with_transcript(
            attestor_path=planned_sources["script.manager_attestor_v4"]["path"],
            busctl_path=planned_sources["system.busctl"]["path"],
            python_path=planned_sources["system.attestor_python"]["path"],
            sudo_path=planned_sources["system.sudo"]["path"],
        )
        if type(captured) is not dict or set(captured) != {
            "manager_epoch",
            "transcript",
        }:
            raise ValueError("live manager capture returned the wrong schema")
        bootstrap.authority.validate_manager_epoch(captured["manager_epoch"])
        bootstrap.authority.validate_manager_epoch_capture_transcript(
            captured["transcript"],
            expected_epoch=captured["manager_epoch"],
        )
    except Exception as exc:
        raise DrillAuthorityError("live manager/boot capture failed closed") from exc
    return captured


def _capture_reference_capability(
    *,
    busctl_identity: Mapping[str, Any],
    manager_epoch: Mapping[str, Any],
) -> tuple[dict[str, object], dict[str, object]]:
    """Run pinned busctl introspection and derive the exact Ref/Unref surface."""

    expected = _identity(busctl_identity)
    path = Path(str(expected["path"]))
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise DrillAuthorityError("cannot open pinned busctl for capability capture") from exc
    argv = [
        "busctl",
        "--user",
        "introspect",
        "org.freedesktop.systemd1",
        "/org/freedesktop/systemd1",
        "org.freedesktop.systemd1.Manager",
    ]
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise DrillAuthorityError("pinned busctl is not a singly linked regular file")
        os.lseek(descriptor, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        observed = {
            "mode": stat.S_IMODE(before.st_mode),
            "path": str(path),
            "sha256": digest.hexdigest(),
            "size_bytes": size,
        }
        if observed != expected or size != before.st_size:
            raise DrillAuthorityError("pinned busctl identity drifted")
        completed = subprocess.run(
            argv,
            check=False,
            close_fds=True,
            env=dict(os.environ),
            executable=f"/proc/self/fd/{descriptor}",
            pass_fds=(descriptor,),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise DrillAuthorityError("pinned busctl drifted during introspection")
    except subprocess.TimeoutExpired as exc:
        raise DrillAuthorityError("busctl capability introspection timed out") from exc
    finally:
        os.close(descriptor)
    try:
        stdout = completed.stdout.decode("utf-8", "strict")
        stderr = completed.stderr.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise DrillAuthorityError("busctl capability output is not UTF-8") from exc
    if completed.returncode != 0 or stderr:
        raise DrillAuthorityError("busctl capability introspection failed closed")
    methods: dict[str, dict[str, str]] = {}
    for line in stdout.splitlines():
        fields = line.split()
        if fields and fields[0] in {".RefUnit", ".UnrefUnit"}:
            if len(fields) < 5 or fields[1:5] != ["method", "s", "-", "-"]:
                raise DrillAuthorityError("RefUnit/UnrefUnit signature drifted")
            name = fields[0][1:]
            if name in methods:
                raise DrillAuthorityError("duplicate RefUnit/UnrefUnit introspection row")
            methods[name] = {
                "in_signature": fields[2],
                "interface": "org.freedesktop.systemd1.Manager",
                "out_signature": fields[3],
            }
    if set(methods) != {"RefUnit", "UnrefUnit"}:
        raise DrillAuthorityError("RefUnit/UnrefUnit capability is incomplete")
    transcript = {
        "argv": argv,
        "busctl_identity": expected,
        "exit_code": completed.returncode,
        "manager_epoch_digest": lifecycle.epoch_digest(manager_epoch),
        "purpose": "AB16_GATE_A_REFERENCE_CAPABILITY_RAW_TRANSCRIPT",
        "schema_version": "noncert-cuts-ab16-reference-capability-transcript-v1",
        "stderr": stderr,
        "stdout": stdout,
    }
    receipt = {
        "manager_epoch_digest": lifecycle.epoch_digest(manager_epoch),
        "methods": methods,
        "purpose": "AB16_GATE_A_REFERENCE_CAPABILITY_REPLAY",
        "schema_version": "noncert-cuts-ab16-reference-capability-v1",
        "status": "PASS",
        "verdict": "REFUNIT_UNREFUNIT_EXACT_SURFACE_PASS",
    }
    return transcript, receipt


def _observe_repository_head(
    repository_root: Path,
    planned_sources: Mapping[str, Mapping[str, Any]],
) -> str:
    try:
        serialized_git_path = planned_sources["system.git"]["path"]
        if type(serialized_git_path) is not str:
            raise TypeError("planned Git identity path is not a string")
        return bootstrap._observe_repository_head(  # noqa: SLF001
            repository_root,
            Path(serialized_git_path),
            expected_identity=planned_sources["system.git"],
        )
    except Exception as exc:
        raise DrillAuthorityError("repository HEAD replay failed closed") from exc


def _run_history_git(
    *,
    repository_root: Path,
    git_identity: Mapping[str, Any],
    arguments: Sequence[str],
    input_bytes: bytes | None = None,
    output_limit: int = 64 << 20,
) -> bytes:
    """Run one bounded Git query through the exact planned executable bytes."""

    expected = _identity(git_identity)
    git_path = Path(str(expected["path"]))
    if not git_path.is_absolute() or _absolute(git_path) != git_path:
        raise DrillAuthorityError("history replay Git path is not canonical")
    parent_owner = _HistoryDescriptor()
    try:
        parent, parent_descriptor = bootstrap._open_directory_fd(git_path.parent)  # noqa: SLF001
        parent_owner.acquire(parent_descriptor)
    except Exception as exc:
        raise DrillAuthorityError("history replay Git parent path is invalid") from exc
    descriptor_owner = _HistoryDescriptor()
    primary_error: BaseException | None = None
    try:
        descriptor_owner.acquire(
            os.open(
                git_path.name,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=parent_owner.descriptor,
            )
        )
        descriptor = descriptor_owner.descriptor
        observed, before_signature = bootstrap._hash_open_executable(  # noqa: SLF001
            descriptor,
            absolute=parent / git_path.name,
        )
        projected = {
            field: observed[field]
            for field in ("mode", "path", "sha256", "size_bytes")
        }
        if projected != expected:
            raise DrillAuthorityError("history replay Git identity drifted")
        environment = {
            "GIT_CONFIG_COUNT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "HOME": "/nonexistent",
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin",
        }
        completed = subprocess.run(
            [
                "git",
                "--no-replace-objects",
                "-C",
                str(repository_root),
                *arguments,
            ],
            check=False,
            close_fds=True,
            env=environment,
            executable=f"/proc/self/fd/{descriptor}",
            input=input_bytes,
            pass_fds=(descriptor,),
            stdin=None if input_bytes is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        current_path = os.stat(
            git_path.name,
            dir_fd=parent_owner.descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(current_path.st_mode)
            or current_path.st_dev != before_signature[0]
            or current_path.st_ino != before_signature[1]
        ):
            raise DrillAuthorityError("history replay Git path changed during execution")
        after, after_signature = bootstrap._hash_open_executable(  # noqa: SLF001
            descriptor,
            absolute=parent / git_path.name,
        )
        if after_signature != before_signature or after != observed:
            raise DrillAuthorityError("history replay Git bytes changed during execution")
    except DrillAuthorityError as exc:
        primary_error = exc
        raise
    except (OSError, subprocess.TimeoutExpired) as exc:
        error = DrillAuthorityError("history replay Git execution failed closed")
        primary_error = error
        raise error from exc
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        _close_history_descriptors(
            (descriptor_owner, parent_owner),
            primary=primary_error,
        )
    if (
        completed.returncode != 0
        or completed.stderr
        or len(completed.stdout) > output_limit
    ):
        raise DrillAuthorityError(
            "history replay Git query failed closed: "
            f"{tuple(arguments)!r}; exit={completed.returncode}"
        )
    return completed.stdout


def _assert_history_alternates_absent(
    descriptor: int,
) -> None:
    try:
        os.stat(
            "alternates",
            dir_fd=descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return
    except OSError as exc:
        raise DrillAuthorityError("history replay alternate path check failed") from exc
    raise DrillAuthorityError("history replay alternate object store is forbidden")


def _open_history_alternates_guard(
    *,
    repository_root: Path,
    git_identity: Mapping[str, Any],
) -> tuple[int, tuple[int, ...]]:
    raw_common = _run_history_git(
        repository_root=repository_root,
        git_identity=git_identity,
        arguments=("rev-parse", "--git-common-dir"),
        output_limit=1 << 20,
    )
    if not raw_common.endswith(b"\n") or raw_common.count(b"\n") != 1:
        raise DrillAuthorityError("history replay Git common directory is malformed")
    try:
        serialized = raw_common[:-1].decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise DrillAuthorityError("history replay Git common directory is not UTF-8") from exc
    common = Path(serialized)
    if not common.is_absolute():
        common = repository_root / common
    common = _absolute(common)
    common_owner = _HistoryDescriptor()
    try:
        _, common_descriptor = bootstrap._open_directory_fd(common)  # noqa: SLF001
        common_owner.acquire(common_descriptor)
    except Exception as exc:
        raise DrillAuthorityError("history replay Git common directory is invalid") from exc
    objects_owner = _HistoryDescriptor()
    info_owner = _HistoryDescriptor()
    primary_error: BaseException | None = None
    try:
        objects_owner.acquire(
            os.open(
                "objects",
                os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=common_owner.descriptor,
            )
        )
        info_owner.acquire(
            os.open(
                "info",
                os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=objects_owner.descriptor,
            )
        )
        signature = bootstrap._stat_signature(  # noqa: SLF001
            os.fstat(info_owner.descriptor)
        )
        _assert_history_alternates_absent(info_owner.descriptor)
        _close_history_descriptors(
            (objects_owner, common_owner),
            primary=None,
        )
        return info_owner.release(), signature
    except DrillAuthorityError as exc:
        primary_error = exc
        raise
    except OSError as exc:
        error = DrillAuthorityError("history replay object store is invalid")
        primary_error = error
        raise error from exc
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        _close_history_descriptors(
            (info_owner, objects_owner, common_owner),
            primary=primary_error,
        )


def _history_source_records(
    *,
    repository_root: Path,
    git_identity: Mapping[str, Any],
    manifest_head: str,
    current_head: str,
    source_members: Mapping[str, Mapping[str, Any]],
) -> tuple[str, list[dict[str, object]]]:
    alternates_descriptor, alternates_signature = (
        _open_history_alternates_guard(
            repository_root=repository_root,
            git_identity=git_identity,
        )
    )
    alternates_owner = _HistoryDescriptor(alternates_descriptor)
    primary_error: BaseException | None = None
    try:
        result = _history_source_records_guarded(
            repository_root=repository_root,
            git_identity=git_identity,
            manifest_head=manifest_head,
            current_head=current_head,
            source_members=source_members,
        )
        _assert_history_alternates_absent(alternates_owner.descriptor)
        if (
            bootstrap._stat_signature(  # noqa: SLF001
                os.fstat(alternates_owner.descriptor)
            )
            != alternates_signature
        ):
            raise DrillAuthorityError(
                "history replay Git objects/info directory changed"
            )
        return result
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        _close_history_descriptors(
            (alternates_owner,),
            primary=primary_error,
        )


def _history_source_records_guarded(
    *,
    repository_root: Path,
    git_identity: Mapping[str, Any],
    manifest_head: str,
    current_head: str,
    source_members: Mapping[str, Mapping[str, Any]],
) -> tuple[str, list[dict[str, object]]]:
    observed_head = _run_history_git(
        repository_root=repository_root,
        git_identity=git_identity,
        arguments=("rev-parse", "--verify", "HEAD"),
        output_limit=128,
    )
    if observed_head != f"{current_head}\n".encode("ascii"):
        raise DrillAuthorityError("history replay repository HEAD drifted")
    parent = _run_history_git(
        repository_root=repository_root,
        git_identity=git_identity,
        arguments=("rev-list", "--parents", "-n", "1", HISTORY_SOURCE_COMMIT),
        output_limit=128,
    )
    tree = _run_history_git(
        repository_root=repository_root,
        git_identity=git_identity,
        arguments=("rev-parse", "--verify", f"{HISTORY_SOURCE_COMMIT}^{{tree}}"),
        output_limit=128,
    )
    if parent != f"{HISTORY_SOURCE_COMMIT} {manifest_head}\n".encode("ascii"):
        raise DrillAuthorityError("history source commit is not the unique manifest-head child")
    if tree != f"{HISTORY_SOURCE_TREE}\n".encode("ascii"):
        raise DrillAuthorityError("history source commit tree identity drifted")
    _run_history_git(
        repository_root=repository_root,
        git_identity=git_identity,
        arguments=(
            "merge-base",
            "--is-ancestor",
            HISTORY_SOURCE_COMMIT,
            current_head,
        ),
        output_limit=0,
    )
    ordered_paths = sorted(source_members, key=lambda value: value.encode("utf-8"))
    tree_raw = _run_history_git(
        repository_root=repository_root,
        git_identity=git_identity,
        arguments=(
            "ls-tree",
            "-rz",
            "-r",
            "--full-tree",
            HISTORY_SOURCE_COMMIT,
            *ordered_paths,
        ),
    )
    tree_records: dict[str, tuple[str, str]] = {}
    for raw_record in tree_raw.split(b"\0"):
        if not raw_record:
            continue
        try:
            metadata, raw_path = raw_record.split(b"\t", 1)
            mode_raw, object_type, oid_raw = metadata.split(b" ")
            path = raw_path.decode("utf-8", "strict")
            mode = mode_raw.decode("ascii", "strict")
            oid = oid_raw.decode("ascii", "strict")
        except (UnicodeDecodeError, ValueError) as exc:
            raise DrillAuthorityError("history source Git tree record is malformed") from exc
        if (
            path in tree_records
            or path not in source_members
            or object_type != b"blob"
            or mode not in {"100644", "100755"}
            or re.fullmatch(r"[0-9a-f]{40}", oid) is None
        ):
            raise DrillAuthorityError("history source Git tree membership drifted")
        tree_records[path] = (mode, oid)
    if set(tree_records) != set(source_members):
        raise DrillAuthorityError("history source Git tree path set drifted")

    batch_input = b"".join(
        f"{tree_records[path][1]}\n".encode("ascii")
        for path in ordered_paths
    )
    batch = _run_history_git(
        repository_root=repository_root,
        git_identity=git_identity,
        arguments=("cat-file", "--batch"),
        input_bytes=batch_input,
    )
    offset = 0
    records: list[dict[str, object]] = []
    for path in ordered_paths:
        mode, expected_oid = tree_records[path]
        newline = batch.find(b"\n", offset)
        if newline < 0:
            raise DrillAuthorityError("history source Git blob header is truncated")
        header = batch[offset:newline].split(b" ")
        if len(header) != 3 or header[1] != b"blob":
            raise DrillAuthorityError("history source Git blob header drifted")
        try:
            oid = header[0].decode("ascii")
            size = int(header[2])
        except (UnicodeDecodeError, ValueError) as exc:
            raise DrillAuthorityError("history source Git blob header is malformed") from exc
        start = newline + 1
        end = start + size
        if (
            oid != expected_oid
            or end >= len(batch)
            or batch[end : end + 1] != b"\n"
        ):
            raise DrillAuthorityError("history source Git blob framing drifted")
        raw = batch[start:end]
        offset = end + 1
        member = source_members[path]
        expected_mode = 0o755 if mode == "100755" else 0o644
        digest = hashlib.sha256(raw).hexdigest()
        if (
            member["mode"] != expected_mode
            or member["sha256"] != digest
            or member["size_bytes"] != len(raw)
        ):
            raise DrillAuthorityError("history source Git blob identity drifted")
        records.append(
            {
                "git_blob_oid": oid,
                "git_mode": mode,
                "mode": expected_mode,
                "path": path,
                "sha256": digest,
                "size_bytes": len(raw),
            }
        )
    if offset != len(batch):
        raise DrillAuthorityError("history source Git blob batch has trailing bytes")
    final_head = _run_history_git(
        repository_root=repository_root,
        git_identity=git_identity,
        arguments=("rev-parse", "--verify", "HEAD"),
        output_limit=128,
    )
    if final_head != observed_head:
        raise DrillAuthorityError("history replay repository HEAD changed during replay")
    member_digest = hashlib.sha256(
        bootstrap.authority.canonical_json(records)
    ).hexdigest()
    return member_digest, records


def _replay_history_freeze(
    *,
    manifest_path: Path | str,
    repository_root: Path | str,
    current_repository_head: str,
    git_identity: Mapping[str, Any],
) -> dict[str, object]:
    try:
        snapshot = lifecycle.snapshot_regular(_absolute(manifest_path))
    except Exception as exc:
        raise DrillAuthorityError("history-freeze manifest is missing, non-regular, or symlinked") from exc
    try:
        value = bootstrap.authority.strict_loads(
            snapshot.raw,
            "terminal-reference history freeze",
        )
    except Exception as exc:
        raise DrillAuthorityError("history-freeze manifest JSON is invalid") from exc
    if bootstrap.authority.canonical_json(value) != snapshot.raw:
        raise DrillAuthorityError("history-freeze manifest is not canonical campaign-authority JSON")
    if snapshot.identity != {
        "mode": HISTORY_FREEZE_MANIFEST_MODE,
        "path": str(HISTORY_FREEZE_MANIFEST_PATH),
        "sha256": HISTORY_FREEZE_MANIFEST_SHA256,
        "size_bytes": HISTORY_FREEZE_MANIFEST_SIZE,
    }:
        raise DrillAuthorityError("history-freeze manifest byte identity drifted")
    if type(value) is not dict or set(value) != {
        "created_at_utc",
        "file_count",
        "files",
        "frozen_roots",
        "purpose",
        "repository_head",
        "repository_root",
        "schema_version",
        "v1_source_glob",
    }:
        raise DrillAuthorityError("history-freeze manifest schema drifted")
    if (
        value["schema_version"] != HISTORY_FREEZE_SCHEMA
        or value["purpose"] != HISTORY_FREEZE_PURPOSE
        or value["repository_head"] != HISTORY_FREEZE_HEAD
        or value["repository_root"] != str(HISTORY_REPOSITORY_ROOT)
        or type(value["created_at_utc"]) is not str
        or type(value["repository_root"]) is not str
        or type(value["frozen_roots"]) is not list
        or type(value["v1_source_glob"]) is not str
        or value["v1_source_glob"] != HISTORY_SOURCE_GLOB
        or type(value["file_count"]) is not int
        or type(value["files"]) is not list
        or value["file_count"] != len(value["files"])
    ):
        raise DrillAuthorityError("history-freeze manifest scalar semantics drifted")
    try:
        bootstrap._utc(value["created_at_utc"], "history-freeze created_at_utc")  # noqa: SLF001
    except Exception as exc:
        raise DrillAuthorityError("history-freeze manifest timestamp drifted") from exc
    current_root = _absolute(repository_root)
    if current_root != HISTORY_REPOSITORY_ROOT:
        raise DrillAuthorityError("history replay is not running in the registered worktree")
    if (
        type(current_repository_head) is not str
        or re.fullmatch(r"[0-9a-f]{40}", current_repository_head) is None
    ):
        raise DrillAuthorityError("history replay current HEAD is malformed")
    serialized_history_root = value["repository_root"]
    history_root = Path(serialized_history_root)
    if (
        not history_root.is_absolute()
        or _absolute(history_root) != history_root
        or str(history_root) != serialized_history_root
    ):
        raise DrillAuthorityError("history-freeze repository root is not one canonical absolute path")
    try:
        bootstrap.authority._reject_symlink_chain(history_root)  # noqa: SLF001
        metadata = os.lstat(history_root)
    except Exception as exc:
        raise DrillAuthorityError("history-freeze repository root is missing or symlinked") from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise DrillAuthorityError("history-freeze repository root is not a directory")

    frozen_roots: set[str] = set()
    for raw_root in value["frozen_roots"]:
        relative_root = Path(raw_root) if type(raw_root) is str else Path()
        if (
            type(raw_root) is not str
            or not raw_root
            or raw_root in frozen_roots
            or relative_root.is_absolute()
            or relative_root.as_posix() != raw_root
            or any(part in {"", ".", ".."} for part in relative_root.parts)
        ):
            raise DrillAuthorityError("history-freeze frozen root path is invalid")
        frozen_roots.add(raw_root)
    if tuple(value["frozen_roots"]) != HISTORY_FROZEN_ROOTS:
        raise DrillAuthorityError("history-freeze frozen root set drifted")
    source_glob = Path(value["v1_source_glob"])
    if (
        not value["v1_source_glob"]
        or source_glob.is_absolute()
        or source_glob.as_posix() != value["v1_source_glob"]
        or any(part in {"", ".", ".."} for part in source_glob.parts)
    ):
        raise DrillAuthorityError("history-freeze v1 source glob is invalid")

    seen: set[str] = set()
    artifact_members: dict[str, Mapping[str, Any]] = {}
    source_members: dict[str, Mapping[str, Any]] = {}
    for raw in value["files"]:
        if type(raw) is not dict or set(raw) != {
            "mode",
            "path",
            "sha256",
            "size_bytes",
        }:
            raise DrillAuthorityError("history-freeze member schema drifted")
        relative = raw["path"]
        relative_path = Path(relative) if type(relative) is str else Path()
        if (
            type(relative) is not str
            or not relative
            or relative in seen
            or relative_path.is_absolute()
            or relative_path.as_posix() != relative
            or any(part in {"", ".", ".."} for part in relative_path.parts)
            or type(raw["mode"]) is not int
            or raw["mode"] < 0
            or raw["mode"] > 0o7777
            or type(raw["sha256"]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", raw["sha256"]) is None
            or type(raw["size_bytes"]) is not int
            or raw["size_bytes"] < 0
        ):
            raise DrillAuthorityError("history-freeze member path is invalid")
        seen.add(relative)
        under_frozen = any(
            relative == frozen_root or relative.startswith(f"{frozen_root}/")
            for frozen_root in frozen_roots
        )
        matches_source = PurePosixPath(relative).match(HISTORY_SOURCE_GLOB)
        if under_frozen == matches_source:
            raise DrillAuthorityError("history-freeze member class is ambiguous")
        if under_frozen:
            artifact_members[relative] = raw
            member_path = history_root / relative_path
            try:
                observed = lifecycle.snapshot_regular(member_path).identity
            except Exception as exc:
                raise DrillAuthorityError(
                    "history-freeze artifact is missing, non-regular, or symlinked"
                ) from exc
            if observed != {
                "mode": raw["mode"],
                "path": str(member_path),
                "sha256": raw["sha256"],
                "size_bytes": raw["size_bytes"],
            }:
                raise DrillAuthorityError("history-freeze artifact byte identity drifted")
        else:
            source_members[relative] = raw
    if (
        len(seen) != HISTORY_ARTIFACT_COUNT + HISTORY_SOURCE_COUNT
        or len(artifact_members) != HISTORY_ARTIFACT_COUNT
        or len(source_members) != HISTORY_SOURCE_COUNT
    ):
        raise DrillAuthorityError("history-freeze member class counts drifted")
    member_digest, source_records = _history_source_records(
        repository_root=history_root,
        git_identity=git_identity,
        manifest_head=value["repository_head"],
        current_head=current_repository_head,
        source_members=source_members,
    )
    return {
        "artifact_file_count": len(artifact_members),
        "authorizations": {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
        },
        "file_count": len(seen),
        "manifest_identity": snapshot.identity,
        "purpose": "AB16_GATE_A_TERMINAL_REFERENCE_HISTORY_REPLAY",
        "schema_version": HISTORY_REPLAY_SCHEMA,
        "source_file_count": len(source_members),
        "source_materialization": {
            "commit": HISTORY_SOURCE_COMMIT,
            "file_count": len(source_records),
            "manifest_head_parent": value["repository_head"],
            "member_digest": member_digest,
            "tree": HISTORY_SOURCE_TREE,
        },
        "status": "PASS",
        "verdict": "IMMUTABLE_FAILED_GATE_A_HISTORY_REPLAY_PASS",
    }


def _launch_environment() -> dict[str, object]:
    value = {
        "clear_ambient": True,
        "schema_version": lifecycle.LAUNCH_ENVIRONMENT_SCHEMA,
        "variables": {
            "DBUS_SESSION_BUS_ADDRESS": os.environ.get(
                "DBUS_SESSION_BUS_ADDRESS",
                "",
            ),
            "HOME": os.environ.get("HOME", ""),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": os.environ.get("PATH", ""),
            "PYTHONHASHSEED": "0",
            "TZ": "UTC",
            "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", ""),
        },
    }
    try:
        lifecycle.validate_launch_environment(value)
    except Exception as exc:
        raise DrillAuthorityError("fixed drill launch environment is invalid") from exc
    return value


def _package(
    package_dir: Path,
    *,
    planned_sources: Mapping[str, Mapping[str, Any]],
    planned_source_set_digest: str,
) -> dict[str, object]:
    """Seal source identities and the exact libsystemd bytes used at runtime."""

    _mkdir(package_dir)
    payload_dir = package_dir / "payload"
    _mkdir(payload_dir)
    source_identity = _identity(planned_sources["system.libsystemd"])
    source_snapshot = lifecycle.snapshot_regular(source_identity["path"])
    if {field: source_snapshot.identity[field] for field in source_identity} != source_identity:
        raise DrillAuthorityError("libsystemd source identity drifted before package copy")
    libsystemd_identity = lifecycle.write_exclusive(
        payload_dir / "libsystemd.so",
        source_snapshot.raw,
    )
    manifest_path = package_dir / "package-manifest.json"
    manifest = {
        "authorizations": {
            "arm_launch_authorized": False,
            "formal_campaign_creation_authorized": False,
            "solver_run_authorized": False,
        },
        "external_source_identities": dict(planned_sources),
        "sealed_payload_identities": {
            "libsystemd": libsystemd_identity,
        },
        "planned_source_set_digest": planned_source_set_digest,
        "purpose": PACKAGE_PURPOSE,
        "schema_version": PACKAGE_SCHEMA,
    }
    manifest_identity = _write(manifest_path, manifest)
    seal_raw = (
        f"{manifest_identity['sha256']}  package-manifest.json\n"
        f"{libsystemd_identity['sha256']}  payload/libsystemd.so\n"
    ).encode("ascii")
    seal_path = package_dir / "SHA256SUMS"
    seal_identity = lifecycle.write_exclusive(seal_path, seal_raw)
    members = {str(item.relative_to(package_dir)) for item in package_dir.rglob("*") if item.is_file()}
    if members != {
        "SHA256SUMS",
        "package-manifest.json",
        "payload/libsystemd.so",
    }:
        raise DrillAuthorityError("disposable package member set drifted")
    return {
        "libsystemd_identity": libsystemd_identity,
        "manifest_identity": manifest_identity,
        "package_id": seal_identity["sha256"],
        "seal_identity": seal_identity,
    }


def _build_drill_source_snapshot(
    authority_dir: Path,
    *,
    planned_sources: Mapping[str, Mapping[str, Any]],
    planned_source_set_digest: str,
    repository_head: str,
    repository_root: Path,
) -> dict[str, object]:
    """Materialize the non-system Gate-A bytes required by pre-run v2.

    The disposable drill never executes from this tree.  It exists solely to
    satisfy the pre-run v2 live/sealed-source discriminator without claiming a
    full repository snapshot or granting formal execution.
    """

    snapshot_dir = authority_dir / "source-snapshot"
    snapshot_root = snapshot_dir / "repository"
    _mkdir(snapshot_dir)
    _mkdir(snapshot_root)
    category_dirs = {
        category: snapshot_root / category
        for category in ("input", "script")
    }
    for path in category_dirs.values():
        _mkdir(path)
    members: list[dict[str, object]] = []
    expected_paths: set[str] = set()
    external_system_identities: dict[str, dict[str, object]] = {}
    for role, planned in sorted(planned_sources.items()):
        category, separator, name = role.partition(".")
        if (
            not separator
            or category not in {"input", "script", "system"}
            or re.fullmatch(r"[A-Za-z0-9_.-]+", name) is None
        ):
            raise DrillAuthorityError("planned source role is unsafe for drill snapshot")
        if category == "system":
            external_system_identities[role] = _identity(planned)
            continue
        source = lifecycle.snapshot_regular(planned["path"])
        if source.identity != _identity(planned):
            raise DrillAuthorityError("planned source drifted during drill snapshot")
        target = category_dirs[category] / name
        materialized = lifecycle.write_exclusive(target, source.raw)
        relative = target.relative_to(snapshot_root).as_posix()
        expected_paths.add(relative)
        members.append(
            {
                "materialized_identity": materialized,
                "path": relative,
                "role": role,
                "source_identity": _identity(planned),
            }
        )
    actual_paths = {
        path.relative_to(snapshot_root).as_posix()
        for path in snapshot_root.rglob("*")
        if path.is_file()
    }
    if actual_paths != expected_paths:
        raise DrillAuthorityError("drill source snapshot member set drifted")
    member_digest = hashlib.sha256(
        bootstrap.authority.canonical_json(members)
    ).hexdigest()
    manifest_identity = _write(
        snapshot_dir / "manifest.json",
        {
            "authorizations": {
                "formal_execution_authorized": False,
                "organic_arm_launch_authorized": False,
                "solver_run_authorized": False,
            },
            "external_system_identities": external_system_identities,
            "import_mode": "not-executed-disposable-source-snapshot",
            "member_count": len(members),
            "member_digest": member_digest,
            "members": members,
            "planned_source_set_digest": planned_source_set_digest,
            "repository_head": repository_head,
            "repository_root": str(repository_root),
            "schema_version": "noncert-cuts-ab16-disposable-source-snapshot-v1",
            "snapshot_root": str(snapshot_root),
        },
    )
    receipt_identity = _write(
        snapshot_dir / "materialization-receipt.json",
        {
            "authorizations": {
                "formal_execution_authorized": False,
                "organic_arm_launch_authorized": False,
                "solver_run_authorized": False,
            },
            "manifest_identity": manifest_identity,
            "member_count": len(members),
            "member_digest": member_digest,
            "planned_source_set_digest": planned_source_set_digest,
            "schema_version": (
                "noncert-cuts-ab16-disposable-source-snapshot-materialization-v1"
            ),
            "snapshot_root": str(snapshot_root),
            "status": "PASS",
        },
    )
    return {
        "manifest_identity": manifest_identity,
        "receipt_identity": receipt_identity,
        "snapshot_root": str(snapshot_root),
    }


def _control_record(
    *,
    kind: str,
    run_nonce: str,
    planned_source_set_digest: str,
    paths: Mapping[str, str],
) -> dict[str, object]:
    return {
        "authorizations": {
            "arm_launch_authorized": False,
            "formal_campaign_creation_authorized": False,
            "solver_run_authorized": False,
        },
        "kind": kind,
        "paths": dict(paths),
        "planned_source_set_digest": planned_source_set_digest,
        "purpose": PURPOSE,
        "run_nonce": run_nonce,
        "schema_version": CONTROL_SCHEMA,
    }


def _reobserve_sources(
    *,
    strict_input_paths: Mapping[str, Path | str],
    system_tool_paths: Mapping[str, Path | str],
    expected: Mapping[str, Mapping[str, Any]],
    expected_digest: str,
) -> None:
    current, _, _, _ = bootstrap._planned_source_identities(  # noqa: SLF001
        strict_input_paths=strict_input_paths,
        system_tool_paths=system_tool_paths,
    )
    if current != expected or bootstrap._source_set_digest(current) != expected_digest:  # noqa: SLF001
        raise DrillAuthorityError("planned source bytes drifted during authority build")


def build_disposable_drill_authority(
    *,
    output_dir: Path | str,
    repository_root: Path | str,
    repository_head: str,
    run_nonce: str,
    expected_planned_source_set_digest: str,
    strict_input_paths: Mapping[str, Path | str],
    system_tool_paths: Mapping[str, Path | str],
) -> dict[str, object]:
    """Publish an inert drill selection without creating a formal campaign."""

    destination = _absolute(output_dir)
    repository = _absolute(repository_root)
    if type(run_nonce) is not str or RUN_NONCE_RE.fullmatch(run_nonce) is None or destination.name != run_nonce:
        raise DrillAuthorityError("drill directory/run nonce binding is invalid")
    if type(repository_head) is not str or re.fullmatch(r"[0-9a-f]{40}", repository_head) is None:
        raise DrillAuthorityError("repository_head is invalid")
    if (
        type(expected_planned_source_set_digest) is not str
        or re.fullmatch(r"[0-9a-f]{64}", expected_planned_source_set_digest) is None
    ):
        raise DrillAuthorityError("planned source-set digest is invalid")
    bootstrap.authority._reject_symlink_chain(destination.parent)  # noqa: SLF001
    if destination.exists() or destination.is_symlink():
        raise DrillAuthorityError("disposable drill authority already exists")

    planned, _, system_paths, _ = bootstrap._planned_source_identities(  # noqa: SLF001
        strict_input_paths=strict_input_paths,
        system_tool_paths=system_tool_paths,
    )
    planned_digest = bootstrap._source_set_digest(planned)  # noqa: SLF001
    if planned_digest != expected_planned_source_set_digest:
        raise DrillAuthorityError("planned source-set digest drifted before drill build")
    observed_head = _observe_repository_head(repository, planned)
    if observed_head != repository_head:
        raise DrillAuthorityError("repository HEAD differs from drill preregistration")
    history_replay = _replay_history_freeze(
        manifest_path=strict_input_paths["history_freeze_manifest"],
        repository_root=repository,
        current_repository_head=repository_head,
        git_identity=planned["system.git"],
    )
    capture = _capture_live_manager_epoch(planned)
    manager_epoch = capture["manager_epoch"]
    transcript = capture["transcript"]
    capability_transcript, capability_receipt = _capture_reference_capability(
        busctl_identity=planned["system.busctl"],
        manager_epoch=manager_epoch,
    )

    _mkdir(destination)
    authority_dir = destination / "authority"
    attempt_dir = destination / "attempt"
    package_dir = authority_dir / "package"
    _mkdir(authority_dir)
    _mkdir(attempt_dir)

    planned_identity = _write(
        authority_dir / "planned-source-identities.json",
        {
            "planned_source_identities": planned,
            "planned_source_set_digest": planned_digest,
            "purpose": PURPOSE,
            "schema_version": AUTHORITY_SCHEMA,
        },
    )
    transcript_identity = _write(
        authority_dir / "manager-transcript-preselection.json",
        transcript,
    )
    transcript_identity = _snapshot_identity(transcript_identity["path"])
    epoch_record = lifecycle.build_epoch_observation(
        phase="preselection",
        slot=DRILL_SLOT,
        observed_epoch=manager_epoch,
        observed_at_monotonic_ns=time.monotonic_ns(),
        capture_transcript_identity=transcript_identity,
    )
    epoch_identity = _write(
        authority_dir / "manager-epoch-preselection.json",
        epoch_record,
    )
    capability_transcript_identity = _write(
        authority_dir / "reference-capability-transcript.json",
        capability_transcript,
    )
    capability_receipt = {
        **capability_receipt,
        "transcript_identity": capability_transcript_identity,
    }
    capability_identity = _write(
        authority_dir / "reference-capability.json",
        capability_receipt,
    )
    history_replay_identity = _write(
        authority_dir / "history-freeze-replay.json",
        history_replay,
    )
    environment_identity = _write(
        authority_dir / "launch-environment.json",
        _launch_environment(),
    )
    environment_identity = _snapshot_identity(environment_identity["path"])
    package_build = _package(
        package_dir,
        planned_sources=planned,
        planned_source_set_digest=planned_digest,
    )
    libsystemd_identity = package_build["libsystemd_identity"]
    package = {
        "manifest_identity": package_build["manifest_identity"],
        "package_id": package_build["package_id"],
        "seal_identity": package_build["seal_identity"],
    }
    source_snapshot = _build_drill_source_snapshot(
        authority_dir,
        planned_sources=planned,
        planned_source_set_digest=planned_digest,
        repository_head=repository_head,
        repository_root=repository,
    )

    common_prestate_path = authority_dir / "common-prestate.json"
    binding_path = authority_dir / "bindings" / f"{DRILL_SLOT}.json"
    _mkdir(binding_path.parent)
    path_map = {
        "attempt_dir": str(attempt_dir),
        "binding_path": str(binding_path),
        "common_prestate_path": str(common_prestate_path),
        "pre_run_authority_path": str(attempt_dir / "pre-run-authority.json"),
        "runner_selection_path": str(attempt_dir / "selection.json"),
    }
    root_identity = _write(
        authority_dir / "drill-root.json",
        {
            **_control_record(
                kind="DISPOSABLE_DRILL_ROOT",
                run_nonce=run_nonce,
                planned_source_set_digest=planned_digest,
                paths=path_map,
            ),
            "manager_epoch": manager_epoch,
            "repository_head": repository_head,
            "repository_root": str(repository),
        },
    )
    continuation_identity = _write(
        authority_dir / "continuation.json",
        _control_record(
            kind="NONAUTHORIZING_DISPOSABLE_CONTINUATION",
            run_nonce=run_nonce,
            planned_source_set_digest=planned_digest,
            paths=path_map,
        ),
    )
    common_prestate_identity = _write(
        common_prestate_path,
        _control_record(
            kind="INERT_COMMON_PRESTATE",
            run_nonce=run_nonce,
            planned_source_set_digest=planned_digest,
            paths=path_map,
        ),
    )
    arm_binding_identity = _write(
        binding_path,
        _control_record(
            kind="INERT_CONTROL_ARM_BINDING",
            run_nonce=run_nonce,
            planned_source_set_digest=planned_digest,
            paths=path_map,
        ),
    )
    baseline_identity = _write(
        authority_dir / "baseline-admission.json",
        _control_record(
            kind="INERT_BASELINE_ADMISSION",
            run_nonce=run_nonce,
            planned_source_set_digest=planned_digest,
            paths=path_map,
        ),
    )
    manifest_identity = _write(
        authority_dir / "drill-manifest.json",
        _control_record(
            kind="DISPOSABLE_DRILL_MANIFEST",
            run_nonce=run_nonce,
            planned_source_set_digest=planned_digest,
            paths=path_map,
        ),
    )
    suite_identity = _write(
        authority_dir / "suite-selection.json",
        _control_record(
            kind="DISPOSABLE_DRILL_SUITE_SELECTION",
            run_nonce=run_nonce,
            planned_source_set_digest=planned_digest,
            paths=path_map,
        ),
    )

    tools = {role: _identity(planned[source_role]) for role, source_role in TOOL_SOURCE_ROLES.items()}
    tools["libsystemd"] = dict(libsystemd_identity)
    strict_inputs = {role: _identity(identity) for role, identity in sorted(planned.items())}
    payload_path = planned["script.disposable_drill_payload_v1"]["path"]
    output_names = {
        "attempt_result": "result.json",
        "cleanup": "cleanup.json",
        "detached_replay": "detached-replay.json",
        "inner": "inner-lifecycle.json",
        "preterminal": "preterminal-resource.json",
        "reference_acquisition": "unit-reference-acquisition.json",
        "reference_release": "unit-reference-release.json",
        "abort_reference_release": "abort-unit-reference-release.json",
        "release": "release-token.json",
        "resource_verification": "resource-verification.json",
        "terminal": "terminal-envelope.json",
    }
    phases = tuple(item for item in lifecycle.PHASES if item != "preselection")
    unit_suffix = hashlib.sha256(f"{run_nonce}:{planned_digest}".encode("utf-8")).hexdigest()[:12]
    unit_name = f"noncert-cuts-ab16-gatea-drill-{unit_suffix}.service"
    authority_chain = {
        "drill_root_identity": root_identity,
        "planned_source_authority_identity": planned_identity,
        "planned_source_set_digest": planned_digest,
    }
    expected_payload_status = {
        "exit_code": 0,
        "expectation": "SUCCESS",
        "signal": 0,
    }
    pre_run = {
        "arm": "control",
        "arm_binding_identity": arm_binding_identity,
        "arm_launch_authorized": False,
        "arm_selection_write_authorized": True,
        "attempt_dir": str(attempt_dir),
        "authority_chain": authority_chain,
        "baseline_admission_identity": baseline_identity,
        "baseline_incumbent_sha256": common_prestate_identity["sha256"],
        "campaign_id": f"disposable-drill-{unit_suffix}",
        "campaign_root_identity": root_identity,
        "common_prestate_identity": common_prestate_identity,
        "configuration": "region-capacity",
        "continuation_identity": continuation_identity,
        "epoch_observation_paths": {phase: str(attempt_dir / f"manager-epoch-{phase}.json") for phase in phases},
        "epoch_transcript_paths": {phase: str(attempt_dir / f"manager-transcript-{phase}.json") for phase in phases},
        "execution_class": "DISPOSABLE_LIVE_DRILL",
        "expected_payload_status": expected_payload_status,
        "launch": {
            "cwd": str(repository),
            "environment_identity": environment_identity,
            "payload_argv": [
                tools["python3_13"]["path"],
                "-I",
                payload_path,
                "--selection",
                str(attempt_dir / "selection.json"),
                "--output",
                str(attempt_dir / "result.json"),
            ],
            "libsystemd_path": tools["libsystemd"]["path"],
            "python3_13_path": tools["python3_13"]["path"],
            "supervisor_argv": [
                tools["python3_13"]["path"],
                "-I",
                tools["organic_resource_lifecycle"]["path"],
                "supervise",
                "--pre-run",
                str(attempt_dir / "pre-run-authority.json"),
                "--selection",
                str(attempt_dir / "selection.json"),
            ],
            "systemctl_path": tools["systemctl"]["path"],
            "systemd_run_path": tools["systemd_run"]["path"],
        },
        "manager_epoch": manager_epoch,
        "order": "ab",
        "output_paths": {role: str(attempt_dir / name) for role, name in output_names.items()},
        "package": package,
        "pre_run_authority_path": str(attempt_dir / "pre-run-authority.json"),
        "prelaunch_allowlist": [
            "pre-run-authority.json",
            "selection.json",
        ],
        "preflight_results": {
            "epoch_identity_pass": True,
            "head_identity_pass": True,
            "package_replay_pass": True,
            "path_preregistration_pass": True,
            "resource_contract_pass": True,
            "reference_contract_pass": True,
            "reference_capability_pass": True,
            "libsystemd_identity_pass": True,
            "history_freeze_replay_pass": True,
            "slot_order_pass": True,
            "strict_inputs_replay_pass": True,
            "tool_identities_replay_pass": True,
        },
        "preselection_epoch_identity": epoch_identity,
        "preselection_transcript_identity": transcript_identity,
        "reference_capability_identity": capability_identity,
        "reference_capability_transcript_identity": capability_transcript_identity,
        "history_freeze_replay_identity": history_replay_identity,
        "live_source_provenance_root": str(repository),
        "prospective_manifest_identity": manifest_identity,
        "purpose": lifecycle.PRE_RUN_PURPOSE,
        "repository_git_tool_identity": _identity(planned["system.git"]),
        "repository_head": repository_head,
        "repository_root": str(repository),
        "resource_contract": lifecycle.DRILL_RESOURCE_CONTRACT,
        "reference_contract": lifecycle.REFERENCE_CONTRACT,
        "run_nonce": run_nonce,
        "runner_selection_path": str(attempt_dir / "selection.json"),
        "schema_version": lifecycle.PRE_RUN_AUTHORITY_SCHEMA,
        "sealed_snapshot_execution_root": source_snapshot["snapshot_root"],
        "seed": 0,
        "snapshot_manifest_identity": source_snapshot["manifest_identity"],
        "snapshot_materialization_receipt_identity": source_snapshot[
            "receipt_identity"
        ],
        "slot": DRILL_SLOT,
        "solver_run_authorized": False,
        "status": "PASS",
        "strict_input_identities": strict_inputs,
        "suite_selection_identity": suite_identity,
        "tool_identities": tools,
        "unit_name": unit_name,
        "verdict": "AB16_ORGANIC_PRE_RUN_AUTHORITY_PASS",
        "workers": 1,
    }
    lifecycle.validate_pre_run_authority(pre_run)
    verifier.validate_pre_run_authority(pre_run)
    pre_run_identity = _write(
        attempt_dir / "pre-run-authority.json",
        pre_run,
    )
    selection = {
        "arm": "control",
        "arm_binding_identity": arm_binding_identity,
        "attempt_dir": str(attempt_dir),
        "authority_chain": authority_chain,
        "authorizations": {
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "organic_arm_launch_authorized": False,
            "production_certified_authorized": False,
            "solver_run_authorized": False,
        },
        "baseline_admission_identity": baseline_identity,
        "baseline_incumbent_sha256": common_prestate_identity["sha256"],
        "campaign_id": pre_run["campaign_id"],
        "common_prestate_identity": common_prestate_identity,
        "configuration": "region-capacity",
        "enabled_families": [],
        "execution_class": "DISPOSABLE_LIVE_DRILL",
        "expected_payload_status": expected_payload_status,
        "fresh_process_required": True,
        "live_source_provenance_root": pre_run["live_source_provenance_root"],
        "manifest_identity": manifest_identity,
        "order": "ab",
        "pre_run_authority_identity": pre_run_identity,
        "purpose": lifecycle.DRILL_SELECTION_PURPOSE,
        "repository_git_tool_identity": pre_run["repository_git_tool_identity"],
        "repository_head": repository_head,
        "repository_root": str(repository),
        "run_nonce": run_nonce,
        "schema_version": lifecycle.DRILL_SELECTION_SCHEMA,
        "sealed_snapshot_execution_root": pre_run[
            "sealed_snapshot_execution_root"
        ],
        "seed": 0,
        "selection_nonce": f"{run_nonce}-selection",
        "slot": DRILL_SLOT,
        "snapshot_manifest_identity": pre_run["snapshot_manifest_identity"],
        "snapshot_materialization_receipt_identity": pre_run[
            "snapshot_materialization_receipt_identity"
        ],
        "unit_name": unit_name,
        "workers": 1,
    }
    lifecycle.validate_runner_selection(
        selection,
        pre_run_authority=pre_run,
        pre_run_authority_identity=pre_run_identity,
    )
    selection_identity = _write(
        attempt_dir / "selection.json",
        selection,
    )
    _reobserve_sources(
        strict_input_paths=strict_input_paths,
        system_tool_paths=system_tool_paths,
        expected=planned,
        expected_digest=planned_digest,
    )
    if set(item.name for item in attempt_dir.iterdir()) != {
        "pre-run-authority.json",
        "selection.json",
    }:
        raise DrillAuthorityError("prelaunch attempt allowlist was not preserved")
    result = {
        "authorizations": {
            "arm_launch_authorized": False,
            "formal_campaign_creation_authorized": False,
            "solver_run_authorized": False,
        },
        "disposable_drill_ready": True,
        "formal_campaign_created": False,
        "planned_source_set_digest": planned_digest,
        "pre_run_authority_identity": pre_run_identity,
        "purpose": RESULT_PURPOSE,
        "run_nonce": run_nonce,
        "schema_version": RESULT_SCHEMA,
        "selection_identity": selection_identity,
        "status": "PASS",
    }
    result_identity = _write(authority_dir / "authority-ready.json", result)
    return {
        "authority_result": result,
        "authority_result_identity": result_identity,
        "formal_campaign_created": False,
        "pre_run_authority_identity": pre_run_identity,
        "selection_identity": selection_identity,
        "status": "PASS",
    }


def _strict_path_map(path: Path, label: str) -> dict[str, Path]:
    snapshot = lifecycle.snapshot_regular(_absolute(path))
    value = lifecycle.strict_loads(snapshot.raw, label)
    if type(value) is not dict or any(type(role) is not str or type(item) is not str for role, item in value.items()):
        raise DrillAuthorityError(f"{label} must map role strings to path strings")
    return {role: Path(item) for role, item in value.items()}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--repository-head", required=True)
    parser.add_argument("--run-nonce", required=True)
    parser.add_argument("--planned-source-set-digest", required=True)
    parser.add_argument("--strict-inputs-json", required=True, type=Path)
    parser.add_argument("--system-tools-json", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        result = build_disposable_drill_authority(
            output_dir=arguments.output_dir,
            repository_root=arguments.repository_root,
            repository_head=arguments.repository_head,
            run_nonce=arguments.run_nonce,
            expected_planned_source_set_digest=arguments.planned_source_set_digest,
            strict_input_paths=_strict_path_map(
                arguments.strict_inputs_json,
                "strict input path map",
            ),
            system_tool_paths=_strict_path_map(
                arguments.system_tools_json,
                "system tool path map",
            ),
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "detail": str(exc),
                    "status": "FAIL_CLOSED",
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
