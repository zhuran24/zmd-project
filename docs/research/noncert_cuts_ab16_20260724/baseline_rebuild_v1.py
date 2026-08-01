#!/usr/bin/env python3
"""Rebuild the historical AB16 baseline from package-pinned strict inputs.

This is a formal-stage payload.  Importing it is side-effect free; the CLI is
only run after the separately authorized Gate B selection.  Its output is
evidence for the independent baseline admission tool, never an admission by
itself.  Repository code is imported with ordinary Python semantics only from
the package-bound, no-overwrite campaign snapshot named by the canonical
campaign-provenance record.  Every data input is an exact member of that same
snapshot; the live checkout is not an execution source.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
from typing import Any, Protocol

import baseline_admission_v1 as baseline_contract
from ortools.sat import cp_model_pb2


EXPECTED_MODEL_PROTO_SHA256 = "3a9be08dcca722fc4bf7dfc9bcf7be4a1213af14ded9ec7b769909a029904d32"
EXPECTED_INCUMBENT_SHA256 = "13f88404d7f5e4fde86929f82997a2b9850fa1cc4791d710c0363ed3e072f223"
EXPECTED_VARIABLE_COUNT = 37_760
EXPECTED_CONSTRAINT_COUNT = 95_136
SCHEMA = "noncert-cuts-ab16-baseline-rebuild-v1"
METADATA_SCHEMA = baseline_contract.METADATA_SCHEMA
MODEL_BACKEND = "ortools.sat.cp_model_pb2.CpModelProto"
MODEL_BINARY_FORMAT = "deterministic-protobuf-v1"
REBUILD_PURPOSE = "strict_ab16_baseline_model_rebuild"
CAMPAIGN_PROVENANCE_NAME = "campaign-provenance.json"
MAX_PROVENANCE_BYTES = 64 * 1024 * 1024
STRICT_INPUT_ROLES = (
    "candidate_placements",
    "canonical_rules",
    "mandatory_instances",
)
PROSPECTIVE_BASELINE_SUFFIX = (
    "formal-ab16",
    "artifacts",
    "prospective",
    "baseline",
)
BASELINE_BUDGET_LABELS = {
    "AB16 baseline rebuilt model": "model",
    "AB16 baseline incumbent": "normal",
    "AB16 baseline rebuilt metadata": "metadata",
    "AB16 baseline rebuild result": "publication",
    "AB16 baseline cut segment": "ledger",
}
BASELINE_TMP_DIRECTORY_LABEL = "AB16 baseline tmp directory"
BASELINE_CHECKPOINT_DIRECTORY_LABEL = "AB16 baseline checkpoint directory"
BASELINE_CUT_DIRECTORY_LABEL = "AB16 baseline cut channel directory"
BASELINE_CUT_CHANNEL = "ab16-baseline-rebuild-cuts"
BASELINE_CUT_DIRECTORY_NAME = "benders-cuts"
BASELINE_WORKER_CONFINEMENT = "landlock-read-only-worker-v1"


class BaselineRebuildError(RuntimeError):
    """The deterministic baseline could not be rebuilt exactly."""


class BaselineBudgetBackend(Protocol):
    """Formal-root broker view supplied only by the package-pinned launcher."""

    @property
    def authority_binding(self) -> Mapping[str, object]: ...

    def maximum_bytes(self, label: str, *, artifact_class: str) -> int: ...

    def register_directory(
        self,
        path: Path,
        *,
        label: str,
        mode_octal: str,
    ) -> Mapping[str, object]: ...

    def install_worker_confinement(
        self,
        retained_read_only_fds: Sequence[int],
    ) -> Mapping[str, object]: ...

    def publish_bytes(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
    ) -> Mapping[str, object]: ...

    def append_segment(
        self,
        channel: str,
        sequence: int,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        arm_slot: str | None = None,
    ) -> Mapping[str, object]: ...

    def export_model_to_sealed_memfd(
        self,
        model: object,
        path: Path,
        *,
        maximum_bytes: int,
        label: str,
    ) -> Mapping[str, object]: ...


@dataclass
class ProvenanceOnlyOutput:
    """One retained-FD view of the formal baseline output prestate."""

    root: Path
    directory_fd: int
    provenance_fd: int
    directory_object: tuple[int, int]
    provenance_signature: tuple[int, ...]
    provenance_raw: bytes
    provenance_identity: dict[str, object]
    provenance: dict[str, object]
    initial_members: frozenset[str]

    def close(self) -> None:
        os.close(self.provenance_fd)
        os.close(self.directory_fd)


@dataclass
class BaselineBudgetWorkspace:
    """Retained identities for the broker-created, read-only workspace."""

    tmp_path: Path
    tmp_fd: int
    tmp_identity: tuple[int, int]
    checkpoint_path: Path
    checkpoint_fd: int
    checkpoint_identity: tuple[int, int]

    def verify(self, *, mode_octal: str = "0500") -> None:
        _verify_budget_fixed_directory(
            self.tmp_path,
            self.tmp_fd,
            self.tmp_identity,
            label=BASELINE_TMP_DIRECTORY_LABEL,
            mode_octal=mode_octal,
        )
        _verify_budget_fixed_directory(
            self.checkpoint_path,
            self.checkpoint_fd,
            self.checkpoint_identity,
            label=BASELINE_CHECKPOINT_DIRECTORY_LABEL,
            mode_octal=mode_octal,
        )

    def close(self) -> None:
        os.close(self.checkpoint_fd)
        os.close(self.tmp_fd)

    def retained_read_only_fds(self) -> tuple[int, int]:
        return (self.tmp_fd, self.checkpoint_fd)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _authority_json(value: object) -> bytes:
    return _canonical(value) + b"\n"


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _jsonable(value: object) -> object:
    if value is None or type(value) in (bool, int, float, str):
        return value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return str(value)


def _reject_symlink_chain(
    path: Path,
    *,
    leaf_may_not_exist: bool,
) -> Path:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for index, part in enumerate(absolute.parts[1:]):
        current /= part
        is_leaf = index == len(absolute.parts[1:]) - 1
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            if leaf_may_not_exist and is_leaf:
                return absolute
            raise BaselineRebuildError(f"path component is missing: {current}") from None
        if stat.S_ISLNK(metadata.st_mode):
            raise BaselineRebuildError(f"symlink path component is forbidden: {current}")
    return absolute


def _snapshot_signature(item: os.stat_result) -> tuple[int, ...]:
    return (
        item.st_dev,
        item.st_ino,
        item.st_mode,
        item.st_nlink,
        item.st_uid,
        item.st_gid,
        item.st_size,
        item.st_mtime_ns,
        item.st_ctime_ns,
    )


def _object_identity(item: os.stat_result) -> tuple[int, int]:
    return item.st_dev, item.st_ino


def _open_directory(path: Path, *, label: str) -> tuple[Path, int, os.stat_result]:
    absolute = _reject_symlink_chain(path, leaf_may_not_exist=False)
    if not hasattr(os, "O_NOFOLLOW"):
        raise BaselineRebuildError("O_NOFOLLOW is required")
    try:
        descriptor = os.open(
            absolute,
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
        )
    except OSError as exc:
        raise BaselineRebuildError(f"{label} is not an openable real directory") from exc
    try:
        opened = os.fstat(descriptor)
        named = os.stat(absolute, follow_symlinks=False)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or not stat.S_ISDIR(named.st_mode)
            or _object_identity(opened) != _object_identity(named)
        ):
            raise BaselineRebuildError(f"{label} directory identity is invalid")
    except BaseException:
        os.close(descriptor)
        raise
    return absolute, descriptor, opened


def _verify_directory_binding(path: Path, descriptor: int, expected: tuple[int, int], *, label: str) -> None:
    opened = os.fstat(descriptor)
    try:
        named = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise BaselineRebuildError(f"{label} path binding disappeared") from exc
    if (
        not stat.S_ISDIR(opened.st_mode)
        or not stat.S_ISDIR(named.st_mode)
        or _object_identity(opened) != expected
        or _object_identity(named) != expected
    ):
        raise BaselineRebuildError(f"{label} path binding drifted")


def _read_stable_fd(
    descriptor: int,
    *,
    label: str,
    limit: int,
) -> tuple[bytes, os.stat_result]:
    before = os.fstat(descriptor)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size < 0
        or before.st_size > limit
    ):
        raise BaselineRebuildError(f"{label} is not an admissible regular file")
    chunks: list[bytes] = []
    offset = 0
    while offset < before.st_size:
        chunk = os.pread(descriptor, min(1 << 20, before.st_size - offset), offset)
        if not chunk:
            raise BaselineRebuildError(f"{label} was truncated during same-FD read")
        chunks.append(chunk)
        offset += len(chunk)
    if os.pread(descriptor, 1, before.st_size):
        raise BaselineRebuildError(f"{label} grew during same-FD read")
    after = os.fstat(descriptor)
    if _snapshot_signature(before) != _snapshot_signature(after):
        raise BaselineRebuildError(f"{label} changed during same-FD read")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise BaselineRebuildError(f"{label} size replay failed")
    return raw, before


def _snapshot_regular(path: Path, *, limit: int) -> tuple[bytes, dict[str, object]]:
    absolute = _reject_symlink_chain(
        path,
        leaf_may_not_exist=False,
    )
    descriptor = os.open(
        absolute,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        raw, _ = _read_stable_fd(descriptor, label=f"strict input {absolute}", limit=limit)
    finally:
        os.close(descriptor)
    return raw, {
        "path": str(absolute),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _campaign_provenance(path: Path) -> dict[str, object]:
    try:
        return baseline_contract.campaign_provenance(path)
    except baseline_contract.AdmissionError as exc:
        raise BaselineRebuildError(f"campaign provenance failed closed: {exc}") from exc


def _require_snapshot_imports(snapshot_root: Path) -> None:
    for name, module in tuple(sys.modules.items()):
        if name != "src" and not name.startswith("src."):
            continue
        source = getattr(module, "__file__", None)
        if type(source) is str:
            if not Path(os.path.abspath(source)).is_relative_to(snapshot_root):
                raise BaselineRebuildError(f"repository module imported outside snapshot: {name}")
            continue
        search_path = getattr(module, "__path__", None)
        if search_path is None or any(
            not Path(os.path.abspath(item)).is_relative_to(snapshot_root)
            for item in search_path
        ):
            raise BaselineRebuildError(f"repository package imported outside snapshot: {name}")


def _budget_maximum(
    backend: BaselineBudgetBackend,
    label: str,
    *,
    artifact_class: str,
) -> int:
    if BASELINE_BUDGET_LABELS.get(label) != artifact_class:
        raise BaselineRebuildError(f"{label}: baseline budget label/class is not fixed")
    try:
        maximum = backend.maximum_bytes(label, artifact_class=artifact_class)
    except Exception as exc:
        raise BaselineRebuildError(f"{label}: budget maximum lookup failed closed") from exc
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        raise BaselineRebuildError(f"{label}: budget maximum is not a positive exact integer")
    return maximum


def _write_exclusive(
    path: Path,
    raw: bytes,
    *,
    mode: int = 0o600,
    budget_backend: BaselineBudgetBackend | None = None,
    budget_label: str | None = None,
    artifact_class: str | None = None,
) -> dict[str, object]:
    absolute = Path(os.path.abspath(path))
    path_is_prospective = _is_prospective_baseline_output(absolute.parent)
    if path_is_prospective and budget_backend is None:
        raise BaselineRebuildError("prospective baseline artifact lacks its formal-root budget broker")
    if budget_backend is not None and not path_is_prospective:
        raise BaselineRebuildError("budgeted baseline artifact path differs from the fixed layout")
    if budget_backend is not None:
        if mode != 0o600 or type(budget_label) is not str or type(artifact_class) is not str:
            raise BaselineRebuildError("budgeted baseline publication lacks its fixed label/class")
        maximum = _budget_maximum(
            budget_backend,
            budget_label,
            artifact_class=artifact_class,
        )
        if len(raw) <= 0 or len(raw) > maximum:
            raise BaselineRebuildError(f"{budget_label}: payload differs from its fixed allocation")
        try:
            observed = dict(
                budget_backend.publish_bytes(
                    absolute,
                    raw,
                    maximum_bytes=maximum,
                    artifact_class=artifact_class,
                    label=budget_label,
                )
            )
        except BaselineRebuildError:
            raise
        except Exception as exc:
            raise BaselineRebuildError(
                f"{budget_label}: broker publication failed or acknowledgement is uncertain"
            ) from exc
        expected = {
            "path": str(absolute),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
        if any(observed.get(key) != value for key, value in expected.items()):
            raise BaselineRebuildError(f"{budget_label}: broker publication identity differs")
        return expected
    if budget_label is not None or artifact_class is not None:
        raise BaselineRebuildError("baseline budget metadata was supplied without its broker")
    parent, parent_fd, parent_before = _open_directory(absolute.parent, label="output parent")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
        try:
            descriptor = os.open(absolute.name, flags, mode, dir_fd=parent_fd)
        except OSError as exc:
            raise BaselineRebuildError(f"exclusive output creation failed: {absolute}") from exc
        try:
            view = memoryview(raw)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise BaselineRebuildError(f"short write: {absolute}")
                view = view[written:]
            os.fsync(descriptor)
            metadata = os.fstat(descriptor)
            named = os.stat(absolute.name, dir_fd=parent_fd, follow_symlinks=False)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
                or _snapshot_signature(metadata) != _snapshot_signature(named)
                or stat.S_IMODE(metadata.st_mode) != mode
                or metadata.st_size != len(raw)
            ):
                raise BaselineRebuildError(f"exclusive output identity failed: {absolute}")
        finally:
            os.close(descriptor)
        os.fsync(parent_fd)
        _verify_directory_binding(
            parent,
            parent_fd,
            _object_identity(parent_before),
            label="output parent",
        )
    finally:
        os.close(parent_fd)
    return {
        "path": str(absolute),
        "size_bytes": metadata.st_size,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _is_prospective_baseline_output(path: Path) -> bool:
    absolute = Path(os.path.abspath(path))
    return tuple(absolute.parts[-len(PROSPECTIVE_BASELINE_SUFFIX) :]) == PROSPECTIVE_BASELINE_SUFFIX


def _open_budget_fixed_directory(
    backend: BaselineBudgetBackend,
    path: Path,
    *,
    label: str,
) -> tuple[int, tuple[int, int]]:
    absolute = Path(os.path.abspath(path))
    try:
        observed = dict(
            backend.register_directory(
                absolute,
                label=label,
                mode_octal="0700",
            )
        )
    except BaselineRebuildError:
        raise
    except Exception as exc:
        raise BaselineRebuildError(f"{label}: broker directory registration failed closed") from exc
    absolute, descriptor, opened = _open_directory(absolute, label=label)
    try:
        if stat.S_IMODE(opened.st_mode) != 0o700:
            raise BaselineRebuildError(f"{label}: fixed directory is not mode 0700")
        expected = {
            "device": opened.st_dev,
            "inode": opened.st_ino,
            "mode_octal": "0700",
            "path": str(absolute),
        }
        if observed != expected:
            raise BaselineRebuildError(f"{label}: broker directory identity differs")
        if os.listdir(descriptor):
            raise BaselineRebuildError(f"{label}: fixed directory is not initially empty")
        return descriptor, _object_identity(opened)
    except BaseException:
        os.close(descriptor)
        raise


def _verify_budget_fixed_directory(
    path: Path,
    descriptor: int,
    identity: tuple[int, int],
    *,
    label: str,
    mode_octal: str,
) -> None:
    _verify_directory_binding(path, descriptor, identity, label=label)
    if mode_octal not in {"0500", "0700"}:
        raise BaselineRebuildError(f"{label}: expected directory mode is invalid")
    if stat.S_IMODE(os.fstat(descriptor).st_mode) != int(mode_octal, 8):
        raise BaselineRebuildError(f"{label}: fixed directory mode drifted")


def _validate_budget_authority_binding(backend: BaselineBudgetBackend) -> None:
    try:
        binding = dict(backend.authority_binding)
    except Exception as exc:
        raise BaselineRebuildError("baseline budget authority binding is unavailable") from exc
    if binding.get("filesystem_write_confinement") != BASELINE_WORKER_CONFINEMENT:
        raise BaselineRebuildError("baseline worker lacks the fixed read-only Landlock confinement")
    forbidden = {
        key
        for key in binding
        if key.endswith(("_root_fd", "_staging_fd", "_directory_fd"))
        or key in {"root_fd", "staging_fd", "directory_fd"}
    }
    if forbidden:
        raise BaselineRebuildError("baseline worker received a writable root or staging descriptor")


def _promote_budget_directory_read_only(
    backend: BaselineBudgetBackend,
    path: Path,
    descriptor: int,
    identity: tuple[int, int],
    *,
    label: str,
) -> None:
    try:
        observed = dict(
            backend.register_directory(
                path,
                label=label,
                mode_octal="0500",
            )
        )
    except Exception as exc:
        raise BaselineRebuildError(f"{label}: broker directory seal failed closed") from exc
    expected = {
        "device": identity[0],
        "inode": identity[1],
        "mode_octal": "0500",
        "path": str(path),
    }
    if observed != expected:
        raise BaselineRebuildError(f"{label}: broker directory seal identity differs")
    _verify_budget_fixed_directory(
        path,
        descriptor,
        identity,
        label=label,
        mode_octal="0500",
    )


def _prepare_budget_workspace(
    output: Path,
    backend: BaselineBudgetBackend,
) -> BaselineBudgetWorkspace:
    if not _is_prospective_baseline_output(output):
        raise BaselineRebuildError("budget workspace path differs from the fixed layout")
    _validate_budget_authority_binding(backend)
    tmp_path = output / "tmp"
    checkpoint_path = output / "checkpoint"
    tmp_fd = -1
    checkpoint_fd = -1
    try:
        tmp_fd, tmp_identity = _open_budget_fixed_directory(
            backend,
            tmp_path,
            label=BASELINE_TMP_DIRECTORY_LABEL,
        )
        checkpoint_fd, checkpoint_identity = _open_budget_fixed_directory(
            backend,
            checkpoint_path,
            label=BASELINE_CHECKPOINT_DIRECTORY_LABEL,
        )
        cut_directory = checkpoint_path / BASELINE_CUT_DIRECTORY_NAME
        try:
            cut_record = dict(
                backend.register_directory(
                    cut_directory,
                    label=BASELINE_CUT_DIRECTORY_LABEL,
                    mode_octal="0700",
                )
            )
        except Exception as exc:
            raise BaselineRebuildError(
                "baseline immutable cut channel registration failed closed"
            ) from exc
        cut_fd = os.open(
            BASELINE_CUT_DIRECTORY_NAME,
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=checkpoint_fd,
        )
        try:
            cut_metadata = os.fstat(cut_fd)
            expected_cut_record = {
                "device": cut_metadata.st_dev,
                "inode": cut_metadata.st_ino,
                "mode_octal": "0700",
                "path": str(cut_directory),
            }
            if (
                cut_record != expected_cut_record
                or not stat.S_ISDIR(cut_metadata.st_mode)
                or os.listdir(cut_fd)
            ):
                raise BaselineRebuildError("baseline immutable cut channel identity differs")
        finally:
            os.close(cut_fd)
        _promote_budget_directory_read_only(
            backend,
            tmp_path,
            tmp_fd,
            tmp_identity,
            label=BASELINE_TMP_DIRECTORY_LABEL,
        )
        _promote_budget_directory_read_only(
            backend,
            checkpoint_path,
            checkpoint_fd,
            checkpoint_identity,
            label=BASELINE_CHECKPOINT_DIRECTORY_LABEL,
        )
        workspace = BaselineBudgetWorkspace(
            tmp_path=tmp_path,
            tmp_fd=tmp_fd,
            tmp_identity=tmp_identity,
            checkpoint_path=checkpoint_path,
            checkpoint_fd=checkpoint_fd,
            checkpoint_identity=checkpoint_identity,
        )
        workspace.verify()
        return workspace
    except BaseException:
        if checkpoint_fd >= 0:
            os.close(checkpoint_fd)
        if tmp_fd >= 0:
            os.close(tmp_fd)
        raise


def _publish_budgeted_model(
    backend: BaselineBudgetBackend,
    model: object,
    path: Path,
    expected_raw: bytes,
) -> dict[str, object]:
    if not _is_prospective_baseline_output(Path(os.path.abspath(path)).parent):
        raise BaselineRebuildError("budgeted baseline model path differs from the fixed layout")
    maximum = _budget_maximum(
        backend,
        "AB16 baseline rebuilt model",
        artifact_class="model",
    )
    if len(expected_raw) <= 0 or len(expected_raw) > maximum:
        raise BaselineRebuildError("rebuilt model differs from its fixed allocation")
    try:
        identity = dict(
            backend.export_model_to_sealed_memfd(
                model,
                path,
                maximum_bytes=maximum,
                label="AB16 baseline rebuilt model",
            )
        )
    except Exception as exc:
        raise BaselineRebuildError(
            "native-helper sealed baseline model export failed or acknowledgement is uncertain"
        ) from exc
    expected = {
        "path": str(Path(os.path.abspath(path))),
        "sha256": hashlib.sha256(expected_raw).hexdigest(),
        "size_bytes": len(expected_raw),
    }
    if any(identity.get(key) != value for key, value in expected.items()):
        raise BaselineRebuildError("sealed baseline model publication identity differs")
    return expected


def _install_budget_worker_confinement(
    backend: BaselineBudgetBackend,
    descriptors: Sequence[int],
) -> dict[str, object]:
    retained = tuple(sorted(descriptors))
    if (
        not retained
        or len(set(retained)) != len(retained)
        or any(type(descriptor) is not int or descriptor < 3 for descriptor in retained)
    ):
        raise BaselineRebuildError("baseline retained read-only FD allowlist is invalid")
    for descriptor in retained:
        try:
            flags = fcntl.fcntl(descriptor, fcntl.F_GETFL)
        except OSError as exc:
            raise BaselineRebuildError("baseline retained read-only FD is unavailable") from exc
        if flags & os.O_ACCMODE != os.O_RDONLY:
            raise BaselineRebuildError("baseline retained FD is writable")
    try:
        observed = dict(backend.install_worker_confinement(retained))
    except Exception as exc:
        raise BaselineRebuildError(
            "native-helper close-range/Landlock installation failed closed"
        ) from exc
    expected = {
        "filesystem_write_confinement": BASELINE_WORKER_CONFINEMENT,
        "retained_read_only_fds": list(retained),
        "root_or_staging_writable_fd_count": 0,
    }
    if observed != expected:
        raise BaselineRebuildError("baseline worker confinement receipt differs")
    return expected


def _mkdir_exclusive(path: Path, *, mode: int = 0o700) -> Path:
    absolute = Path(os.path.abspath(path))
    parent, parent_fd, parent_before = _open_directory(absolute.parent, label="directory parent")
    try:
        try:
            os.mkdir(absolute.name, mode, dir_fd=parent_fd)
        except OSError as exc:
            raise BaselineRebuildError(f"exclusive directory creation failed: {absolute}") from exc
        child_fd = -1
        try:
            child_fd = os.open(
                absolute.name,
                os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
            opened = os.fstat(child_fd)
            named = os.stat(absolute.name, dir_fd=parent_fd, follow_symlinks=False)
            if (
                not stat.S_ISDIR(opened.st_mode)
                or _snapshot_signature(opened) != _snapshot_signature(named)
                or stat.S_IMODE(opened.st_mode) != mode
            ):
                raise BaselineRebuildError(f"exclusive directory identity failed: {absolute}")
        finally:
            if child_fd >= 0:
                os.close(child_fd)
        os.fsync(parent_fd)
        _verify_directory_binding(
            parent,
            parent_fd,
            _object_identity(parent_before),
            label="directory parent",
        )
    finally:
        os.close(parent_fd)
    return absolute


def _verify_provenance_member(state: ProvenanceOnlyOutput) -> None:
    _verify_directory_binding(
        state.root,
        state.directory_fd,
        state.directory_object,
        label="baseline output",
    )
    named = os.stat(
        CAMPAIGN_PROVENANCE_NAME,
        dir_fd=state.directory_fd,
        follow_symlinks=False,
    )
    opened = os.fstat(state.provenance_fd)
    if (
        _snapshot_signature(named) != state.provenance_signature
        or _snapshot_signature(opened) != state.provenance_signature
    ):
        raise BaselineRebuildError("campaign provenance member identity drifted")
    raw, _ = _read_stable_fd(
        state.provenance_fd,
        label="campaign provenance",
        limit=MAX_PROVENANCE_BYTES,
    )
    if raw != state.provenance_raw:
        raise BaselineRebuildError("campaign provenance bytes drifted")


def _open_provenance_only_output(
    output_dir: Path,
    campaign_provenance: Path,
    *,
    prospective: bool = False,
) -> ProvenanceOnlyOutput:
    output = Path(os.path.abspath(output_dir))
    provenance_path = Path(os.path.abspath(campaign_provenance))
    if not output_dir.is_absolute() or output_dir != output:
        raise BaselineRebuildError("output directory must be an absolute normalized path")
    if provenance_path != output / CAMPAIGN_PROVENANCE_NAME:
        raise BaselineRebuildError("campaign provenance is not the canonical baseline child")
    output, directory_fd, directory_before = _open_directory(output, label="baseline output")
    provenance_fd = -1
    try:
        names_before = os.listdir(directory_fd)
        expected_members = {CAMPAIGN_PROVENANCE_NAME}
        if set(names_before) != expected_members or len(names_before) != len(expected_members):
            raise BaselineRebuildError("baseline output is not in PROVENANCE_ONLY state")
        member_before = os.stat(
            CAMPAIGN_PROVENANCE_NAME,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISREG(member_before.st_mode)
            or member_before.st_nlink != 1
            or stat.S_IMODE(member_before.st_mode) != 0o444
        ):
            raise BaselineRebuildError("campaign provenance member is not regular nlink1 mode0444")
        provenance_fd = os.open(
            CAMPAIGN_PROVENANCE_NAME,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directory_fd,
        )
        opened = os.fstat(provenance_fd)
        if _snapshot_signature(opened) != _snapshot_signature(member_before):
            raise BaselineRebuildError("campaign provenance lstat/fstat identity mismatch")
        raw, stable_member = _read_stable_fd(
            provenance_fd,
            label="campaign provenance",
            limit=MAX_PROVENANCE_BYTES,
        )
        member_after = os.stat(
            CAMPAIGN_PROVENANCE_NAME,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        directory_after = os.fstat(directory_fd)
        if (
            _snapshot_signature(stable_member) != _snapshot_signature(member_after)
            or _snapshot_signature(directory_before) != _snapshot_signature(directory_after)
            or os.listdir(directory_fd) != names_before
        ):
            raise BaselineRebuildError("PROVENANCE_ONLY member set changed during validation")
        provenance = _campaign_provenance(provenance_path)
        if baseline_contract.canonical_json(provenance) != raw:
            raise BaselineRebuildError("campaign provenance bytes are not canonical and identity-bound")
        state = ProvenanceOnlyOutput(
            root=output,
            directory_fd=directory_fd,
            provenance_fd=provenance_fd,
            directory_object=_object_identity(directory_before),
            provenance_signature=_snapshot_signature(stable_member),
            provenance_raw=raw,
            provenance_identity={
                "path": str(provenance_path),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            },
            provenance=provenance,
            initial_members=frozenset(expected_members),
        )
        _verify_provenance_member(state)
        return state
    except BaseException:
        if provenance_fd >= 0:
            os.close(provenance_fd)
        os.close(directory_fd)
        raise


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-nonce", required=True)
    parser.add_argument("--campaign-provenance", required=True, type=Path)
    parser.add_argument("--master-seconds", type=float, default=900.0)
    parser.add_argument("--binding-seconds", type=float, default=600.0)
    parser.add_argument("--routing-seconds", type=float, default=600.0)
    parser.add_argument("--max-iterations", type=int, default=30)
    parser.add_argument("--binding-alt-cap", type=int, default=200)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed", type=int, default=2026072301)
    parser.add_argument("--ghost-w", type=int, default=6)
    parser.add_argument("--ghost-h", type=int, default=6)
    parser.add_argument(
        "--candidate-placements",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--canonical-rules",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--mandatory-instances",
        type=Path,
        required=True,
    )
    return parser


def _validate_fixed_parameters(args: argparse.Namespace) -> None:
    expected = {
        "master_seconds": 900.0,
        "binding_seconds": 600.0,
        "routing_seconds": 600.0,
        "max_iterations": 30,
        "binding_alt_cap": 200,
        "workers": 1,
        "seed": 2026072301,
        "ghost_w": 6,
        "ghost_h": 6,
    }
    actual = {key: getattr(args, key) for key in expected}
    if actual != expected:
        raise BaselineRebuildError(f"baseline parameters drifted: expected {expected!r}, got {actual!r}")
    if not args.run_nonce or len(args.run_nonce) > 128:
        raise BaselineRebuildError("run nonce is invalid")
    if not Path(args.campaign_provenance).is_absolute():
        raise BaselineRebuildError("campaign provenance path is not absolute")
    for role in STRICT_INPUT_ROLES:
        path = Path(getattr(args, role))
        if not path.is_absolute():
            raise BaselineRebuildError(f"strict input path is not absolute for {role}")


def _run_rebuild(
    args: argparse.Namespace,
    output_state: ProvenanceOnlyOutput,
    *,
    budget_backend: BaselineBudgetBackend | None = None,
    budget_workspace: BaselineBudgetWorkspace | None = None,
) -> int:
    provenance_before = output_state.provenance
    repository_root = Path(str(provenance_before["snapshot_root"]))
    if Path.cwd() != repository_root:
        raise BaselineRebuildError("working directory is not the campaign snapshot root")
    if any(name == "src" or name.startswith("src.") for name in sys.modules):
        raise BaselineRebuildError("repository modules were imported before snapshot activation")
    for entry in sys.path:
        candidate = Path(os.path.abspath(entry or Path.cwd()))
        if (
            candidate != repository_root
            and (candidate / "PROJECT_LOCK.md").is_file()
            and (candidate / "src").is_dir()
        ):
            raise BaselineRebuildError("ambient repository import path is forbidden")
    output = output_state.root
    if budget_backend is None:
        if budget_workspace is not None:
            raise BaselineRebuildError("legacy rebuild received a prospective budget workspace")
        tmp_dir = _mkdir_exclusive(output / "tmp")
        checkpoint_dir = _mkdir_exclusive(output / "checkpoint")
        _write_exclusive(checkpoint_dir / "benders_cuts.jsonl", b"")
    else:
        if budget_workspace is None:
            raise BaselineRebuildError("prospective rebuild lacks its broker-created workspace")
        budget_workspace.verify()
        tmp_dir = budget_workspace.tmp_path
        checkpoint_dir = budget_workspace.checkpoint_path

    os.environ["TMPDIR"] = str(tmp_dir)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
    os.environ["EXACT_CP_SAT_WORKERS"] = "1"
    os.environ["EXACT_MASTER_CP_SAT_WORKERS"] = "1"
    os.environ["EXACT_MASTER_RANDOM_SEED"] = str(args.seed)
    os.environ["EXACT_MASTER_SEARCH_BRANCHING"] = "fixed"
    os.environ["EXACT_MASTER_CP_MODEL_PROBING_LEVEL"] = "3"
    os.environ["EXACT_MASTER_SYMMETRY_LEVEL"] = "3"
    os.environ["EXACT_B1_BINDING_ALT_CAP"] = str(args.binding_alt_cap)

    strict_inputs = {role: Path(os.path.abspath(getattr(args, role))) for role in STRICT_INPUT_ROLES}
    expected_inputs = {
        "candidate_placements": repository_root / "data" / "preprocessed" / "candidate_placements.json",
        "canonical_rules": repository_root / "rules" / "canonical_rules.json",
        "mandatory_instances": repository_root / "data" / "preprocessed" / "mandatory_exact_instances.json",
    }
    if strict_inputs != expected_inputs:
        raise BaselineRebuildError("strict input paths are not the campaign snapshot members")
    input_identities: dict[str, dict[str, object]] = {}
    for role, path in strict_inputs.items():
        _, identity = _snapshot_regular(path, limit=1 << 30)
        input_identities[role] = identity

    sys.path.insert(0, str(repository_root))
    from src.models.cut_manager import CutManager
    from src.models.master_model import MasterPlacementModel
    from src.search.benders_loop import ExactSearchSession, LBBDController

    _require_snapshot_imports(repository_root)
    started = time.perf_counter()
    session = ExactSearchSession.create(
        repository_root,
        solve_mode="certified_exact",
    )
    master = MasterPlacementModel.from_exact_core(
        session.core,
        ghost_rect=(args.ghost_w, args.ghost_h),
    )
    if budget_backend is None:
        cut_manager = CutManager(
            checkpoint_dir=checkpoint_dir,
            solve_mode="certified_exact",
        )
    else:
        from docs.research.noncert_cuts_ab16_20260724.ab16_budgeted_writers_v1 import (
            AB16BudgetedCutManager,
        )

        cut_manager = AB16BudgetedCutManager(
            checkpoint_dir=checkpoint_dir,
            solve_mode="certified_exact",
            immutable_budget=budget_backend,
            budget_channel=BASELINE_CUT_CHANNEL,
            budget_segment_max_bytes=_budget_maximum(
                budget_backend,
                "AB16 baseline cut segment",
                artifact_class="ledger",
            ),
            budget_arm_slot=None,
        )
    controller = LBBDController(
        master=master,
        cut_manager=cut_manager,
        project_root=repository_root,
        solve_mode="certified_exact",
        master_seconds=args.master_seconds,
        binding_seconds=args.binding_seconds,
        routing_seconds=args.routing_seconds,
        max_iterations=args.max_iterations,
        artifact_hashes=session.artifact_hashes,
        session=session,
        enabled_cut_families=(),
    )
    if os.environ.get("EXACT_CUT_FRAMEWORK_ATTACH") is not None:
        raise BaselineRebuildError("attach environment leaked into baseline build")

    status, returned_solution = controller.run_with_status()
    incumbent: Mapping[str, Any]
    if returned_solution:
        incumbent = returned_solution
    else:
        incumbent = master.extract_solution()
    if not incumbent or "ghost_pick" not in incumbent or master._solver is None:
        raise BaselineRebuildError("baseline run did not retain a complete incumbent")

    solution_values = [int(value) for value in master._solver.ResponseProto().solution]
    if len(solution_values) != len(master.model.Proto().variables):
        raise BaselineRebuildError("solver response length does not match model variables")

    incumbent_json = _jsonable(incumbent)
    model_text = str(master.model.Proto()).encode("utf-8")
    observed = {
        "model_proto_sha256": hashlib.sha256(model_text).hexdigest(),
        "model_variable_count": len(master.model.Proto().variables),
        "model_constraint_count": len(master.model.Proto().constraints),
        "incumbent_sha256": _digest(incumbent_json),
    }
    expected = {
        "model_proto_sha256": EXPECTED_MODEL_PROTO_SHA256,
        "model_variable_count": EXPECTED_VARIABLE_COUNT,
        "model_constraint_count": EXPECTED_CONSTRAINT_COUNT,
        "incumbent_sha256": EXPECTED_INCUMBENT_SHA256,
    }
    if observed != expected:
        raise BaselineRebuildError(f"historical baseline did not reproduce: {observed!r}")
    _verify_provenance_member(output_state)
    if _campaign_provenance(args.campaign_provenance) != provenance_before:
        raise BaselineRebuildError("campaign provenance drifted during baseline rebuild")
    _verify_provenance_member(output_state)

    model_path = output / "cut-free-model.bin"
    model_raw = master.model.Proto().SerializeToString(deterministic=True)
    parsed = cp_model_pb2.CpModelProto()
    consumed = parsed.ParseFromString(model_raw)
    if consumed != len(model_raw) or parsed.SerializeToString(deterministic=True) != model_raw:
        raise BaselineRebuildError("binary model export is not canonical")
    if budget_backend is None:
        model_identity = _write_exclusive(model_path, model_raw)
    else:
        model_identity = _publish_budgeted_model(
            budget_backend,
            master.model,
            model_path,
            model_raw,
        )
    incumbent_identity = _write_exclusive(
        output / "incumbent.json",
        _authority_json(incumbent_json),
        budget_backend=budget_backend,
        budget_label=(
            "AB16 baseline incumbent"
            if budget_backend is not None
            else None
        ),
        artifact_class="normal" if budget_backend is not None else None,
    )
    _, builder_identity = _snapshot_regular(Path(__file__), limit=64 << 20)
    metadata = {
        "schema_version": METADATA_SCHEMA,
        "status": "PASS",
        "purpose": REBUILD_PURPOSE,
        "created_at_utc": _utc_now(),
        "campaign_provenance": provenance_before,
        "model_backend": MODEL_BACKEND,
        "model_binary_format": MODEL_BINARY_FORMAT,
        "canonical_binary": True,
        "model_identity": model_identity,
        "historical_model_text_sha256": observed["model_proto_sha256"],
        "model_variable_count": observed["model_variable_count"],
        "model_constraint_count": observed["model_constraint_count"],
        "builder_identity": builder_identity,
        "input_identities": input_identities,
        "legacy_control_used_as_build_input": False,
        "global_claim_authorized": False,
        "errors": [],
    }
    metadata_identity = _write_exclusive(
        output / "rebuilt-model-metadata.json",
        _authority_json(metadata),
        budget_backend=budget_backend,
        budget_label=(
            "AB16 baseline rebuilt metadata"
            if budget_backend is not None
            else None
        ),
        artifact_class="metadata" if budget_backend is not None else None,
    )
    record = {
        "schema_version": SCHEMA,
        "created_at_utc": _utc_now(),
        "campaign_provenance": provenance_before,
        "run_nonce": args.run_nonce,
        "parameters": {
            "ghost_rect": [args.ghost_w, args.ghost_h],
            "master_seconds": args.master_seconds,
            "binding_seconds": args.binding_seconds,
            "routing_seconds": args.routing_seconds,
            "max_iterations": args.max_iterations,
            "binding_alt_cap": args.binding_alt_cap,
            "workers": args.workers,
            "seed": args.seed,
            "enabled_cut_families": [],
            "framework_attach_enabled": False,
        },
        "runner_status": str(status),
        "proof_summary": _jsonable(controller.last_proof_summary or {}),
        "wall_seconds": round(time.perf_counter() - started, 6),
        "observed": observed,
        "cut_free_model_identity": model_identity,
        "incumbent_identity": incumbent_identity,
        "rebuilt_metadata_identity": metadata_identity,
        "claim_boundary": {
            "authorizing": False,
            "establishes": ["deterministic baseline bytes reproduced"],
            "does_not_establish": [
                "baseline admission",
                "organic cut credibility",
                "SAT or UNSAT",
                "witness or bound",
            ],
        },
    }
    _write_exclusive(
        output / "rebuild-result.json",
        _authority_json(record),
        budget_backend=budget_backend,
        budget_label=(
            "AB16 baseline rebuild result"
            if budget_backend is not None
            else None
        ),
        artifact_class="publication" if budget_backend is not None else None,
    )
    _verify_provenance_member(output_state)
    if budget_workspace is not None:
        budget_workspace.verify()
    expected_top_level = {
        CAMPAIGN_PROVENANCE_NAME,
        "checkpoint",
        "cut-free-model.bin",
        "incumbent.json",
        "rebuilt-model-metadata.json",
        "rebuild-result.json",
        "tmp",
    }
    if set(os.listdir(output_state.directory_fd)) != expected_top_level:
        raise BaselineRebuildError("baseline output member set drifted after rebuild")
    print(json.dumps({"status": "REBUILT_PENDING_INDEPENDENT_REPLAY"}))
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    budget_backend: BaselineBudgetBackend | None = None,
    prospective: bool = False,
) -> int:
    args = _parser().parse_args(argv)
    _validate_fixed_parameters(args)
    output_is_prospective = _is_prospective_baseline_output(args.output_dir)
    prospective = prospective or output_is_prospective
    if prospective and not output_is_prospective:
        raise BaselineRebuildError("prospective baseline output path differs from the fixed layout")
    if prospective and budget_backend is None:
        raise BaselineRebuildError("prospective baseline rebuild lacks its formal-root budget broker")
    if not prospective and budget_backend is not None:
        raise BaselineRebuildError("legacy baseline rebuild cannot consume prospective budget authority")
    output_state = _open_provenance_only_output(
        args.output_dir,
        args.campaign_provenance,
        prospective=prospective,
    )
    budget_workspace: BaselineBudgetWorkspace | None = None
    try:
        if budget_backend is not None:
            budget_workspace = _prepare_budget_workspace(
                output_state.root,
                budget_backend,
            )
            _install_budget_worker_confinement(
                budget_backend,
                (
                    output_state.directory_fd,
                    output_state.provenance_fd,
                    *budget_workspace.retained_read_only_fds(),
                ),
            )
        return _run_rebuild(
            args,
            output_state,
            budget_backend=budget_backend,
            budget_workspace=budget_workspace,
        )
    finally:
        if budget_workspace is not None:
            budget_workspace.close()
        output_state.close()


if __name__ == "__main__":
    raise SystemExit(main())
