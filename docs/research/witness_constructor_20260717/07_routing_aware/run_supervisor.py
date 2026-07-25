"""Fail-closed lifecycle helpers for routing-aware witness research runs.

The module exposes filesystem, locking, discovery, command-construction, and
classification primitives.  Importing it has no side effects, and the command
builder never launches a process.  Callers remain responsible for explicitly
executing a returned command after the read-only busy checks pass.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import tempfile
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence, TextIO


MEMORY_HIGH = "34G"
MEMORY_MAX = "38G"
MEMORY_SWAP_MAX = "16G"
OOM_POLICY = "continue"

MEMORY_HIGH_BYTES = 34 * 1024**3
MEMORY_MAX_BYTES = 38 * 1024**3
MEMORY_SWAP_MAX_BYTES = 16 * 1024**3

CGROUP_PROPERTIES = (
    f"MemoryHigh={MEMORY_HIGH}",
    f"MemoryMax={MEMORY_MAX}",
    f"MemorySwapMax={MEMORY_SWAP_MAX}",
    f"OOMPolicy={OOM_POLICY}",
)

CGROUP_SCALAR_FILES = (
    "memory.current",
    "memory.peak",
    "memory.swap.current",
    "memory.swap.peak",
    "pids.current",
    "pids.peak",
)
REQUIRED_MEMORY_EVENT_KEYS = (
    "high",
    "max",
    "oom",
    "oom_kill",
    "oom_group_kill",
)

RELATED_UNIT_PREFIXES = ("zmd-witness-", "zmd-r45-", "zmd-b4-")
RELATED_PROCESS_MARKERS = frozenset(
    {
        "run_supervisor.py",
        "run_campaign.py",
        "run_campaign_linux.sh",
        "run_reconstructed_prod_ab.py",
        "routing_subproblem.py",
        "solve_shelf_power.py",
        "construct_witness.py",
    }
)

SUCCESS = "CLEAN_RESULT"
SOLVER_TIMEOUT = "SOLVER_TIMEOUT"
SOLVER_UNKNOWN = "SOLVER_UNKNOWN"
CGROUP_OOM_KILL = "CGROUP_OOM_KILL"
CGROUP_OOM_EVENT = "CGROUP_OOM_EVENT"
WORKER_SIGNAL_SIGSEGV = "WORKER_SIGNAL_SIGSEGV"
WORKER_SIGNAL_OTHER = "WORKER_SIGNAL_OTHER"
PROCESS_NONZERO_EXIT = "PROCESS_NONZERO_EXIT"
RESULT_MISSING_OR_INVALID = "RESULT_MISSING_OR_INVALID"
RESULT_SCHEMA_INVALID = "RESULT_SCHEMA_INVALID"
RESULT_INTEGRITY_INVALID = "RESULT_INTEGRITY_INVALID"
OOM_TELEMETRY_MISSING = "OOM_TELEMETRY_MISSING"

FAILURE_CLASSES = frozenset(
    {
        SOLVER_TIMEOUT,
        SOLVER_UNKNOWN,
        CGROUP_OOM_KILL,
        CGROUP_OOM_EVENT,
        WORKER_SIGNAL_SIGSEGV,
        WORKER_SIGNAL_OTHER,
        PROCESS_NONZERO_EXIT,
        RESULT_MISSING_OR_INVALID,
        RESULT_SCHEMA_INVALID,
        RESULT_INTEGRITY_INVALID,
        OOM_TELEMETRY_MISSING,
    }
)

_RUN_SHORT_SHA_RE = re.compile(r"[0-9a-f]{7,40}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_SAFE_UNIT_RE = re.compile(r"[A-Za-z0-9_.@:-]+\.service")
_SAFE_LOGICAL_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


class SupervisorError(RuntimeError):
    """A lifecycle contract failed closed."""


class ArtifactExistsError(SupervisorError):
    """An exclusive directory or file already exists."""


class ArtifactIntegrityError(SupervisorError):
    """An existing content-addressed artifact does not match its name/content."""


class BusyError(SupervisorError):
    """Another prod-scale solver owns the global lock."""


@dataclass(frozen=True)
class FileRecord:
    path: str
    sha256: str
    size_bytes: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class PublishRecord:
    path: Path
    sha256: str
    size_bytes: int
    created: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "created": self.created,
        }


@dataclass(frozen=True)
class _FileSnapshot:
    payload: bytes
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class AttemptEvidence:
    timed_out: bool
    returncode: int | None
    solver_status: str | None
    result_present: bool
    result_parse_valid: bool
    schema_valid: bool
    integrity_valid: bool
    memory_events_before: Mapping[str, int] | None
    memory_events_after: Mapping[str, int] | None


@dataclass(frozen=True)
class AttemptClassification:
    code: str
    successful: bool
    detail: str | None
    memory_events_delta: Mapping[str, int] | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "successful": self.successful,
            "detail": self.detail,
            "memory_events_delta": (
                dict(self.memory_events_delta)
                if self.memory_events_delta is not None
                else None
            ),
        }


def prod_scale_lock_path(uid: int | None = None) -> Path:
    """Return the one repository-wide prod-scale solve mutex path."""

    effective_uid = os.getuid() if uid is None else uid
    if isinstance(effective_uid, bool) or not isinstance(effective_uid, int) or effective_uid < 0:
        raise SupervisorError(f"invalid uid: {effective_uid!r}")
    return Path("/run/user") / str(effective_uid) / "zmd-pj-prod-scale-solve.lock"


@contextmanager
def acquire_prod_scale_lock(lock_path: Path | None = None) -> Iterator[TextIO]:
    """Acquire the global non-blocking flock and hold it for the context lifetime."""

    path = prod_scale_lock_path() if lock_path is None else Path(lock_path)
    if not path.parent.is_dir():
        raise SupervisorError(f"lock parent does not exist: {path.parent}")
    try:
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    except OSError as exc:
        raise SupervisorError(f"cannot open prod-scale solve lock {path}: {exc}") from exc
    handle = os.fdopen(descriptor, "a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BusyError(f"prod-scale solve mutex is busy: {path}") from exc
        yield handle
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _normalize_run_timestamp(now: datetime | None) -> str:
    effective = datetime.now(timezone.utc) if now is None else now
    if effective.tzinfo is None or effective.utcoffset() is None:
        raise SupervisorError("run timestamp must be timezone-aware")
    return effective.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def create_run_directory(base_dir: Path, short_sha: str, *, now: datetime | None = None) -> Path:
    """Create one fresh ``run-<UTC>-<sha>`` directory, refusing reuse."""

    if _RUN_SHORT_SHA_RE.fullmatch(short_sha) is None:
        raise SupervisorError(f"invalid lowercase Git SHA: {short_sha!r}")
    root = Path(base_dir)
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / f"run-{_normalize_run_timestamp(now)}-{short_sha}"
    try:
        run_dir.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError as exc:
        raise ArtifactExistsError(f"refusing to reuse run directory: {run_dir}") from exc
    return run_dir


def create_attempt_directory(run_dir: Path, ordinal: int) -> Path:
    """Create one fresh ``aNNN`` attempt directory under an existing run."""

    if isinstance(ordinal, bool) or not isinstance(ordinal, int) or not 1 <= ordinal <= 999:
        raise SupervisorError(f"attempt ordinal must be in 1..999, got {ordinal!r}")
    root = Path(run_dir)
    if not root.is_dir():
        raise SupervisorError(f"run directory does not exist: {root}")
    attempt_dir = root / f"a{ordinal:03d}"
    try:
        attempt_dir.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError as exc:
        raise ArtifactExistsError(f"refusing to reuse attempt directory: {attempt_dir}") from exc
    return attempt_dir


def canonical_json_bytes(payload: Any) -> bytes:
    try:
        rendered = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise SupervisorError(f"payload is not strict JSON: {exc}") from exc
    return (rendered + "\n").encode("utf-8")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_bytes_exclusive(path: Path, payload: bytes) -> None:
    """Durably publish bytes via temp+hardlink, atomically refusing overwrite."""

    if not isinstance(payload, bytes):
        raise SupervisorError("exclusive payload must be bytes")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.tmp.",
        dir=str(target.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise ArtifactExistsError(f"refusing to overwrite artifact: {target}") from exc
        _fsync_directory(target.parent)
    finally:
        temporary.unlink(missing_ok=True)


def write_text_exclusive(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    if not isinstance(text, str):
        raise SupervisorError("exclusive text payload must be str")
    try:
        payload = text.encode(encoding)
    except (LookupError, UnicodeError) as exc:
        raise SupervisorError(f"cannot encode text as {encoding}: {exc}") from exc
    write_bytes_exclusive(path, payload)


def write_json_exclusive(path: Path, payload: Any) -> None:
    write_bytes_exclusive(path, canonical_json_bytes(payload))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise SupervisorError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def _snapshot_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _read_stable_snapshot(path: Path) -> _FileSnapshot:
    """Read bytes and metadata from one file descriptor, rejecting mutation."""

    source = Path(path)
    try:
        descriptor = os.open(source, os.O_RDONLY | os.O_CLOEXEC)
    except OSError as exc:
        raise SupervisorError(f"cannot open snapshot source {source}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise SupervisorError(f"snapshot source is not a regular file: {source}")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise SupervisorError(f"cannot read snapshot source {source}: {exc}") from exc
    finally:
        os.close(descriptor)
    payload = b"".join(chunks)
    if _snapshot_identity(before) != _snapshot_identity(after) or len(payload) != before.st_size:
        raise SupervisorError(f"snapshot source changed while it was read: {source}")
    return _FileSnapshot(
        payload=payload,
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
    )


def file_record(path: Path, *, relative_to: Path | None = None) -> FileRecord:
    source = Path(path).resolve(strict=True)
    if not source.is_file():
        raise SupervisorError(f"manifest source is not a regular file: {source}")
    display = str(source)
    if relative_to is not None:
        try:
            display = source.relative_to(Path(relative_to).resolve(strict=True)).as_posix()
        except ValueError as exc:
            raise SupervisorError(f"manifest source {source} leaves root {relative_to}") from exc
    snapshot = _read_stable_snapshot(source)
    return FileRecord(display, snapshot.sha256, snapshot.size_bytes)


def build_sha256_manifest(
    files: Mapping[str, Path],
    *,
    relative_to: Path | None = None,
) -> dict[str, Any]:
    """Build a deterministic SHA-256/size manifest without writing it."""

    records: dict[str, dict[str, Any]] = {}
    for logical_name in sorted(files):
        if _SAFE_LOGICAL_NAME_RE.fullmatch(logical_name) is None:
            raise SupervisorError(f"unsafe manifest logical name: {logical_name!r}")
        records[logical_name] = file_record(
            Path(files[logical_name]),
            relative_to=relative_to,
        ).as_dict()
    closure_payload = canonical_json_bytes({"files": records})
    return {
        "schema_version": "routing_aware_witness_manifest.v1",
        "files": records,
        "manifest_sha256": hashlib.sha256(closure_payload).hexdigest(),
    }


def _manifest_from_file_records(records: Mapping[str, FileRecord]) -> dict[str, Any]:
    rendered = {logical_name: records[logical_name].as_dict() for logical_name in sorted(records)}
    closure_payload = canonical_json_bytes({"files": rendered})
    return {
        "schema_version": "routing_aware_witness_manifest.v1",
        "files": rendered,
        "manifest_sha256": hashlib.sha256(closure_payload).hexdigest(),
    }


def _verify_content_addressed_publications(
    publications: Mapping[str, PublishRecord],
    *,
    publish_dir: Path,
    relative_to: Path,
) -> dict[str, FileRecord]:
    """Bind live publication bytes and names back to their first publish records."""

    if not publications:
        raise ArtifactIntegrityError("refusing to commit an empty publication manifest")
    try:
        publish_root = Path(publish_dir).resolve(strict=True)
        relative_root = Path(relative_to).resolve(strict=True)
    except OSError as exc:
        raise ArtifactIntegrityError(f"cannot resolve publication root: {exc}") from exc
    if not publish_root.is_dir() or not relative_root.is_dir():
        raise ArtifactIntegrityError("publication and manifest-relative roots must be directories")

    verified: dict[str, FileRecord] = {}
    for logical_name in sorted(publications):
        if _SAFE_LOGICAL_NAME_RE.fullmatch(logical_name) is None:
            raise ArtifactIntegrityError(f"unsafe manifest logical name: {logical_name!r}")
        publication = publications[logical_name]
        if not isinstance(publication, PublishRecord):
            raise ArtifactIntegrityError(f"publication {logical_name!r} lacks its first PublishRecord")
        if _SHA256_RE.fullmatch(publication.sha256) is None:
            raise ArtifactIntegrityError(f"publication {logical_name!r} has an invalid SHA-256")
        if (
            isinstance(publication.size_bytes, bool)
            or not isinstance(publication.size_bytes, int)
            or publication.size_bytes < 0
        ):
            raise ArtifactIntegrityError(f"publication {logical_name!r} has an invalid byte size")

        recorded_path = Path(publication.path)
        try:
            resolved_path = recorded_path.resolve(strict=True)
        except OSError as exc:
            raise ArtifactIntegrityError(
                f"cannot resolve publication {logical_name!r}: {recorded_path}: {exc}"
            ) from exc
        if resolved_path.parent != publish_root:
            raise ArtifactIntegrityError(
                f"publication {logical_name!r} is not a direct child of {publish_root}: {resolved_path}"
            )
        if recorded_path.name.split(".").count(publication.sha256) != 1:
            raise ArtifactIntegrityError(
                f"publication {logical_name!r} filename is not bound to SHA-256 {publication.sha256}"
            )
        try:
            display_path = resolved_path.relative_to(relative_root).as_posix()
        except ValueError as exc:
            raise ArtifactIntegrityError(
                f"publication {logical_name!r} leaves manifest root {relative_root}: {resolved_path}"
            ) from exc

        snapshot = _read_stable_snapshot(resolved_path)
        if (
            snapshot.sha256 != publication.sha256
            or snapshot.size_bytes != publication.size_bytes
        ):
            raise ArtifactIntegrityError(
                f"publication {logical_name!r} drifted from its first PublishRecord: {resolved_path}"
            )
        verified[logical_name] = FileRecord(
            path=display_path,
            sha256=publication.sha256,
            size_bytes=publication.size_bytes,
        )
    return verified


def publish_content_addressed(
    source: Path,
    publish_dir: Path,
    *,
    logical_name: str | None = None,
) -> PublishRecord:
    """Publish ``<stem>.<sha256><suffix>`` without overwriting.

    A pre-existing byte-identical target is accepted as an idempotent reuse.
    A target with the same content-derived name but different bytes fails closed.
    """

    source_path = Path(source).resolve(strict=True)
    if not source_path.is_file():
        raise SupervisorError(f"publish source is not a regular file: {source_path}")
    name = source_path.name if logical_name is None else logical_name
    if _SAFE_LOGICAL_NAME_RE.fullmatch(name) is None or Path(name).name != name:
        raise SupervisorError(f"unsafe publish logical name: {name!r}")
    parsed = Path(name)
    snapshot = _read_stable_snapshot(source_path)
    digest = snapshot.sha256
    target_name = f"{parsed.stem}.{digest}{parsed.suffix}"
    target_dir = Path(publish_dir)
    target = target_dir / target_name
    payload = snapshot.payload
    try:
        write_bytes_exclusive(target, payload)
    except ArtifactExistsError:
        try:
            target_snapshot = _read_stable_snapshot(target)
            identical = target_snapshot.sha256 == digest and target_snapshot.payload == payload
        except OSError as exc:
            raise ArtifactIntegrityError(f"cannot verify existing publication {target}: {exc}") from exc
        if not identical:
            raise ArtifactIntegrityError(
                f"content-addressed target exists with different bytes: {target}"
            )
        return PublishRecord(target, digest, len(payload), created=False)
    return PublishRecord(target, digest, len(payload), created=True)


def publish_manifest_content_addressed(
    files: Mapping[str, Path],
    publish_dir: Path,
    *,
    relative_to: Path | None = None,
) -> tuple[dict[str, Any], PublishRecord]:
    """Build and content-address publish a deterministic manifest."""

    manifest = build_sha256_manifest(files, relative_to=relative_to)
    payload = canonical_json_bytes(manifest)
    digest = hashlib.sha256(payload).hexdigest()
    target = Path(publish_dir) / f"manifest.{digest}.json"
    try:
        write_bytes_exclusive(target, payload)
    except ArtifactExistsError:
        if not target.is_file() or target.read_bytes() != payload:
            raise ArtifactIntegrityError(
                f"content-addressed manifest exists with different bytes: {target}"
            )
        return manifest, PublishRecord(target, digest, len(payload), created=False)
    return manifest, PublishRecord(target, digest, len(payload), created=True)


def publish_verified_manifest_content_addressed(
    publications: Mapping[str, PublishRecord],
    publish_dir: Path,
    *,
    relative_to: Path | None = None,
) -> tuple[dict[str, Any], PublishRecord]:
    """Commit a manifest only after two checks against first-publish identities.

    The first pass binds every live file to its original :class:`PublishRecord`
    and content-addressed filename.  The manifest is then staged under a hidden
    non-commit name, and a second full pass must agree before one atomic hardlink
    exposes ``manifest.<sha256>.json`` as the publication commit marker.
    """

    publish_root = Path(publish_dir)
    manifest_root = publish_root if relative_to is None else Path(relative_to)
    before = _verify_content_addressed_publications(
        publications,
        publish_dir=publish_root,
        relative_to=manifest_root,
    )
    manifest = _manifest_from_file_records(before)
    payload = canonical_json_bytes(manifest)
    digest = hashlib.sha256(payload).hexdigest()
    resolved_publish_root = publish_root.resolve(strict=True)
    target = resolved_publish_root / f"manifest.{digest}.json"

    try:
        descriptor, staging_name = tempfile.mkstemp(
            prefix=f".manifest.{digest}.pending.",
            dir=str(resolved_publish_root),
        )
    except OSError as exc:
        raise SupervisorError(f"cannot stage publication manifest in {resolved_publish_root}: {exc}") from exc
    staging = Path(staging_name)
    try:
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise SupervisorError(f"cannot write staged publication manifest {staging}: {exc}") from exc
        staged_snapshot = _read_stable_snapshot(staging)
        if staged_snapshot.sha256 != digest or staged_snapshot.payload != payload:
            raise ArtifactIntegrityError(f"staged publication manifest drifted: {staging}")

        after = _verify_content_addressed_publications(
            publications,
            publish_dir=resolved_publish_root,
            relative_to=manifest_root,
        )
        if after != before:
            raise ArtifactIntegrityError("publication identities changed across manifest staging")

        try:
            os.link(staging, target)
        except FileExistsError:
            target_snapshot = _read_stable_snapshot(target)
            if target_snapshot.sha256 != digest or target_snapshot.payload != payload:
                raise ArtifactIntegrityError(
                    f"content-addressed manifest exists with different bytes: {target}"
                )
            created = False
        except OSError as exc:
            raise SupervisorError(f"cannot commit publication manifest {target}: {exc}") from exc
        else:
            _fsync_directory(resolved_publish_root)
            created = True
    finally:
        staging.unlink(missing_ok=True)
    return manifest, PublishRecord(target, digest, len(payload), created=created)


def parse_active_related_units(
    stdout: str,
    *,
    prefixes: Sequence[str] = RELATED_UNIT_PREFIXES,
) -> tuple[str, ...]:
    """Parse ``systemctl list-units`` output, retaining only related services."""

    if not isinstance(stdout, str):
        raise SupervisorError("systemctl stdout must be text")
    units: set[str] = set()
    for line in stdout.splitlines():
        fields = line.split()
        if not fields:
            continue
        unit = fields[0]
        if unit.endswith(".service") and unit.startswith(tuple(prefixes)):
            units.add(unit)
    return tuple(sorted(units))


def query_active_related_units(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[str, ...]:
    """Read active user units.  This helper never starts, stops, or kills one."""

    completed = runner(
        [
            "systemctl",
            "--user",
            "list-units",
            "--type=service",
            "--state=running",
            "--no-legend",
            "--no-pager",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SupervisorError(f"cannot query active user units: {completed.stderr.strip()}")
    return parse_active_related_units(completed.stdout)


def detect_active_related_processes(
    *,
    proc_root: Path = Path("/proc"),
    markers: Iterable[str] = RELATED_PROCESS_MARKERS,
    exclude_pids: Iterable[int] = (),
) -> tuple[dict[str, Any], ...]:
    """Read matching process cmdlines under procfs without signalling them."""

    marker_set = frozenset(markers)
    excluded = {os.getpid(), *(int(pid) for pid in exclude_pids)}
    found: list[dict[str, Any]] = []
    try:
        entries = list(Path(proc_root).iterdir())
    except OSError as exc:
        raise SupervisorError(f"cannot enumerate procfs {proc_root}: {exc}") from exc
    for process_dir in entries:
        if not process_dir.name.isdigit():
            continue
        pid = int(process_dir.name)
        if pid in excluded:
            continue
        try:
            argv = tuple(
                item.decode("utf-8", errors="replace")
                for item in (process_dir / "cmdline").read_bytes().split(b"\0")
                if item
            )
        except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
            continue
        basenames = {Path(argument).name for argument in argv}
        matched_set = set(marker_set & basenames)
        # Python's ``-m package.module`` form has no script basename in argv.
        # Match its final module segment back to the same pinned ``*.py``
        # markers so a module-form worker cannot bypass the one-at-a-time gate.
        for index, argument in enumerate(argv[:-1]):
            if argument != "-m":
                continue
            module = argv[index + 1]
            module_marker = module.rsplit(".", 1)[-1] + ".py"
            if module_marker in marker_set:
                matched_set.add(module_marker)
        matched = sorted(matched_set)
        if matched:
            found.append({"pid": pid, "argv": list(argv), "matched": matched})
    return tuple(sorted(found, key=lambda item: int(item["pid"])))


def build_systemd_run_command(
    *,
    unit_name: str,
    working_directory: Path,
    command: Sequence[str],
) -> tuple[str, ...]:
    """Purely construct the exact cgroup-constrained launch command."""

    if _SAFE_UNIT_RE.fullmatch(unit_name) is None:
        raise SupervisorError(f"unsafe systemd unit name: {unit_name!r}")
    workdir = Path(working_directory)
    if not workdir.is_absolute():
        raise SupervisorError("systemd working directory must be absolute")
    if not command or any(not isinstance(item, str) or not item for item in command):
        raise SupervisorError("worker command must be a non-empty sequence of non-empty strings")
    return (
        "systemd-run",
        "--user",
        "--wait",
        "--pipe",
        f"--unit={unit_name}",
        "--service-type=exec",
        "--collect",
        "--expand-environment=no",
        f"--working-directory={workdir}",
        *(f"--property={property_value}" for property_value in CGROUP_PROPERTIES),
        *command,
    )


def validate_cgroup_property_values(
    *,
    memory_high: int,
    memory_max: int,
    memory_swap_max: int,
    oom_policy: str,
) -> None:
    """Validate observed cgroup values against the exact launch contract."""

    observed = (memory_high, memory_max, memory_swap_max, oom_policy)
    expected = (MEMORY_HIGH_BYTES, MEMORY_MAX_BYTES, MEMORY_SWAP_MAX_BYTES, OOM_POLICY)
    if observed != expected:
        raise SupervisorError(f"cgroup property mismatch: expected={expected}, observed={observed}")


def memory_events_delta(
    before: Mapping[str, int] | None,
    after: Mapping[str, int] | None,
) -> dict[str, int]:
    """Validate required OOM telemetry and return monotone event deltas."""

    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        raise SupervisorError("memory.events start/end telemetry is missing")
    missing_before = set(REQUIRED_MEMORY_EVENT_KEYS) - set(before)
    missing_after = set(REQUIRED_MEMORY_EVENT_KEYS) - set(after)
    if missing_before or missing_after:
        raise SupervisorError(
            "memory.events required keys missing: "
            f"before={sorted(missing_before)}, after={sorted(missing_after)}"
        )
    delta: dict[str, int] = {}
    for key in sorted(set(before) | set(after)):
        start = before.get(key)
        end = after.get(key)
        if isinstance(start, bool) or not isinstance(start, int) or start < 0:
            raise SupervisorError(f"memory.events before[{key!r}] is invalid")
        if isinstance(end, bool) or not isinstance(end, int) or end < start:
            raise SupervisorError(f"memory.events after[{key!r}] is invalid or non-monotone")
        delta[key] = end - start
    return delta


def classify_attempt(evidence: AttemptEvidence) -> AttemptClassification:
    """Apply stable, fail-closed attempt classification with OOM precedence."""

    try:
        delta = memory_events_delta(
            evidence.memory_events_before,
            evidence.memory_events_after,
        )
    except SupervisorError as exc:
        return AttemptClassification(OOM_TELEMETRY_MISSING, False, str(exc), None)

    if delta.get("oom_kill", 0) > 0 or delta.get("oom_group_kill", 0) > 0:
        return AttemptClassification(CGROUP_OOM_KILL, False, None, delta)
    if delta.get("oom", 0) > 0:
        return AttemptClassification(CGROUP_OOM_EVENT, False, None, delta)
    if evidence.timed_out:
        return AttemptClassification(SOLVER_TIMEOUT, False, "wall timeout", delta)
    if evidence.returncode is None:
        return AttemptClassification(PROCESS_NONZERO_EXIT, False, "missing return code", delta)
    if isinstance(evidence.returncode, bool) or not isinstance(evidence.returncode, int):
        return AttemptClassification(PROCESS_NONZERO_EXIT, False, "invalid return code", delta)
    if evidence.returncode < 0:
        signal_number = -evidence.returncode
        if signal_number == signal.SIGSEGV:
            return AttemptClassification(WORKER_SIGNAL_SIGSEGV, False, "SIGSEGV", delta)
        try:
            signal_name = signal.Signals(signal_number).name
        except ValueError:
            signal_name = f"SIG{signal_number}"
        return AttemptClassification(WORKER_SIGNAL_OTHER, False, signal_name, delta)
    if evidence.returncode != 0:
        return AttemptClassification(
            PROCESS_NONZERO_EXIT,
            False,
            f"exit {evidence.returncode}",
            delta,
        )
    if not evidence.result_present or not evidence.result_parse_valid:
        return AttemptClassification(RESULT_MISSING_OR_INVALID, False, None, delta)
    if not evidence.schema_valid:
        return AttemptClassification(RESULT_SCHEMA_INVALID, False, None, delta)
    if not evidence.integrity_valid:
        return AttemptClassification(RESULT_INTEGRITY_INVALID, False, None, delta)
    status = evidence.solver_status.upper() if isinstance(evidence.solver_status, str) else ""
    if status in {"TIMEOUT", "TIME_LIMIT", "EXTERNAL_TIMEOUT"}:
        return AttemptClassification(SOLVER_TIMEOUT, False, status, delta)
    if status == "UNKNOWN":
        return AttemptClassification(SOLVER_UNKNOWN, False, status, delta)
    if status not in {"OPTIMAL", "FEASIBLE", "INFEASIBLE"}:
        return AttemptClassification(RESULT_SCHEMA_INVALID, False, f"solver status {status!r}", delta)
    return AttemptClassification(SUCCESS, True, status, delta)
