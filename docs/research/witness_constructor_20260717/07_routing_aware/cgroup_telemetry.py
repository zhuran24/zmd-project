"""Fail-closed cgroup-v2 telemetry for routing-aware witness workers.

The supervisor constructs the ``systemd-run`` command, while this module is
intended to run *inside* the worker.  It checks that the current process is in
the expected service leaf, validates the exact leaf memory contract, walks
every ancestor through the cgroup-v2 root, and captures the counters needed to
attribute OOM failures to one attempt.

All filesystem locations are injectable so the contract can be tested without
mutating the host cgroup hierarchy.  Importing this module has no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import stat
from types import MappingProxyType
from typing import Any, Literal, Mapping

from .run_supervisor import (
    CGROUP_OOM_EVENT,
    CGROUP_OOM_KILL,
    MEMORY_HIGH_BYTES,
    MEMORY_MAX_BYTES,
    MEMORY_SWAP_MAX_BYTES,
    REQUIRED_MEMORY_EVENT_KEYS,
    SupervisorError,
    memory_events_delta,
)


NO_CGROUP_OOM = "NO_CGROUP_OOM"
TELEMETRY_SCHEMA_VERSION = "routing_aware_witness_cgroup_telemetry.v1"

_LIMIT_CONTRACT = (
    ("memory.high", MEMORY_HIGH_BYTES),
    ("memory.max", MEMORY_MAX_BYTES),
    ("memory.swap.max", MEMORY_SWAP_MAX_BYTES),
)
_COUNTER_FILES = (
    "memory.current",
    "memory.peak",
    "memory.swap.current",
    "memory.swap.peak",
    "pids.current",
)
_SAFE_UNIT_RE = re.compile(r"[A-Za-z0-9_.@:-]+\.service")
_NONNEGATIVE_INTEGER_RE = re.compile(r"0|[1-9][0-9]*")
_EVENT_KEY_RE = re.compile(r"[a-z][a-z0-9_]*")

LimitValue = int | Literal["max"]
OomAttribution = Literal["NO_CGROUP_OOM", "CGROUP_OOM_EVENT", "CGROUP_OOM_KILL"]


class CgroupTelemetryError(SupervisorError):
    """A worker-side cgroup contract or telemetry read failed closed."""

    def __init__(self, code: str, message: str, *, path: Path | None = None) -> None:
        self.code = code
        self.path = path
        suffix = f" ({path})" if path is not None else ""
        super().__init__(f"{code}: {message}{suffix}")


@dataclass(frozen=True)
class CgroupLimitRecord:
    """The three memory controls observed at one cgroup node."""

    relative_path: str
    memory_high: LimitValue
    memory_max: LimitValue
    memory_swap_max: LimitValue

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.relative_path,
            "memory.high": self.memory_high,
            "memory.max": self.memory_max,
            "memory.swap.max": self.memory_swap_max,
        }


@dataclass(frozen=True)
class CgroupContractSnapshot:
    """Validated leaf and ancestor limits at one instant."""

    leaf: CgroupLimitRecord
    ancestors: tuple[CgroupLimitRecord, ...]
    effective_memory_high: int
    effective_memory_max: int
    effective_memory_swap_max: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "leaf": self.leaf.as_dict(),
            "ancestors": [record.as_dict() for record in self.ancestors],
            "effective": {
                "memory.high": self.effective_memory_high,
                "memory.max": self.effective_memory_max,
                "memory.swap.max": self.effective_memory_swap_max,
            },
        }


@dataclass(frozen=True)
class CgroupCounterSnapshot:
    """Attempt-scoped scalar counters and ``memory.events``."""

    memory_current: int
    memory_peak: int
    memory_swap_current: int
    memory_swap_peak: int
    pids_current: int
    memory_events: Mapping[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "memory.current": self.memory_current,
            "memory.peak": self.memory_peak,
            "memory.swap.current": self.memory_swap_current,
            "memory.swap.peak": self.memory_swap_peak,
            "pids.current": self.pids_current,
            "memory.events": dict(sorted(self.memory_events.items())),
        }


@dataclass(frozen=True)
class CgroupTelemetryStart:
    """Validated start state retained until the worker finishes."""

    expected_unit_name: str
    proc_self_cgroup: Path
    cgroup_root: Path
    cgroup_path: Path
    relative_path: str
    device: int
    inode: int
    contract: CgroupContractSnapshot
    counters: CgroupCounterSnapshot


@dataclass(frozen=True)
class CgroupTelemetryRecord:
    """Complete start/end worker telemetry ready for strict JSON output."""

    expected_unit_name: str
    relative_path: str
    contract_start: CgroupContractSnapshot
    contract_end: CgroupContractSnapshot
    counters_start: CgroupCounterSnapshot
    counters_end: CgroupCounterSnapshot
    events_delta: Mapping[str, int]
    oom_attribution: OomAttribution

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TELEMETRY_SCHEMA_VERSION,
            "expected_unit_name": self.expected_unit_name,
            "cgroup_path": self.relative_path,
            "contract_start": self.contract_start.as_dict(),
            "contract_end": self.contract_end.as_dict(),
            "counters_start": self.counters_start.as_dict(),
            "counters_end": self.counters_end.as_dict(),
            "memory.events.delta": dict(sorted(self.events_delta.items())),
            "oom_attribution": self.oom_attribution,
        }


def _read_ascii_file(path: Path) -> str:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise CgroupTelemetryError("CGROUP_FILE_MISSING", str(exc), path=path) from exc
    except OSError as exc:
        raise CgroupTelemetryError("CGROUP_FILE_UNREADABLE", str(exc), path=path) from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise CgroupTelemetryError("CGROUP_FILE_SYMLINK", "cgroup control files may not be symlinks", path=path)
    if not stat.S_ISREG(metadata.st_mode):
        raise CgroupTelemetryError("CGROUP_FILE_INVALID", "cgroup control path is not a regular file", path=path)
    try:
        return path.read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        raise CgroupTelemetryError("CGROUP_FILE_UNREADABLE", str(exc), path=path) from exc


def _parse_nonnegative_integer(raw: str, *, path: Path) -> int:
    value = raw.strip()
    if _NONNEGATIVE_INTEGER_RE.fullmatch(value) is None:
        raise CgroupTelemetryError("CGROUP_VALUE_INVALID", f"expected a nonnegative integer, observed {value!r}", path=path)
    return int(value)


def _read_nonnegative_integer(path: Path) -> int:
    return _parse_nonnegative_integer(_read_ascii_file(path), path=path)


def _read_limit(path: Path, *, allow_max: bool) -> LimitValue:
    raw = _read_ascii_file(path).strip()
    if raw == "max":
        if allow_max:
            return "max"
        raise CgroupTelemetryError("LEAF_LIMIT_UNBOUNDED", "the worker leaf must have an exact numeric limit", path=path)
    return _parse_nonnegative_integer(raw, path=path)


def _read_memory_events(path: Path) -> dict[str, int]:
    raw = _read_ascii_file(path)
    events: dict[str, int] = {}
    for line_number, line in enumerate(raw.splitlines(), start=1):
        fields = line.split()
        if len(fields) != 2 or _EVENT_KEY_RE.fullmatch(fields[0]) is None:
            raise CgroupTelemetryError(
                "MEMORY_EVENTS_INVALID",
                f"invalid key/value record on line {line_number}",
                path=path,
            )
        key, value_raw = fields
        if key in events:
            raise CgroupTelemetryError(
                "MEMORY_EVENTS_INVALID",
                f"duplicate event key {key!r}",
                path=path,
            )
        events[key] = _parse_nonnegative_integer(value_raw, path=path)
    missing = set(REQUIRED_MEMORY_EVENT_KEYS) - set(events)
    if missing:
        raise CgroupTelemetryError(
            "MEMORY_EVENTS_KEYS_MISSING",
            f"required keys missing: {sorted(missing)}",
            path=path,
        )
    return dict(sorted(events.items()))


def _validate_relative_cgroup_path(relative: str) -> tuple[str, ...]:
    if relative == "/":
        return ()
    if not relative.startswith("/") or relative.startswith("//") or "\x00" in relative:
        raise CgroupTelemetryError("PROC_CGROUP_PATH_INVALID", f"non-canonical cgroup path {relative!r}")
    segments = tuple(relative.split("/")[1:])
    if not segments or any(segment in {"", ".", ".."} for segment in segments):
        raise CgroupTelemetryError("PROC_CGROUP_PATH_INVALID", f"non-canonical cgroup path {relative!r}")
    return segments


def resolve_current_cgroup(
    *,
    proc_self_cgroup: Path = Path("/proc/self/cgroup"),
    cgroup_root: Path = Path("/sys/fs/cgroup"),
) -> Path:
    """Resolve the process's unique unified-cgroup-v2 leaf below ``cgroup_root``."""

    proc_path = Path(proc_self_cgroup)
    try:
        raw = proc_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CgroupTelemetryError("PROC_CGROUP_UNREADABLE", str(exc), path=proc_path) from exc

    unified_paths: list[str] = []
    for line_number, line in enumerate(raw.splitlines(), start=1):
        if not line:
            continue
        fields = line.split(":", 2)
        if len(fields) != 3:
            raise CgroupTelemetryError(
                "PROC_CGROUP_INVALID",
                f"malformed record on line {line_number}",
                path=proc_path,
            )
        hierarchy, controllers, relative = fields
        if hierarchy == "0" and controllers == "":
            unified_paths.append(relative)
    if not unified_paths:
        raise CgroupTelemetryError("UNIFIED_CGROUP_MISSING", "no cgroup-v2 0:: record", path=proc_path)
    if len(unified_paths) != 1:
        raise CgroupTelemetryError(
            "UNIFIED_CGROUP_AMBIGUOUS",
            f"observed {len(unified_paths)} cgroup-v2 records",
            path=proc_path,
        )

    segments = _validate_relative_cgroup_path(unified_paths[0])
    try:
        root = Path(cgroup_root).resolve(strict=True)
    except OSError as exc:
        raise CgroupTelemetryError("CGROUP_ROOT_INVALID", str(exc), path=Path(cgroup_root)) from exc
    if not root.is_dir():
        raise CgroupTelemetryError("CGROUP_ROOT_INVALID", "cgroup root is not a directory", path=root)
    unresolved = root.joinpath(*segments)
    try:
        resolved = unresolved.resolve(strict=True)
    except OSError as exc:
        raise CgroupTelemetryError("CGROUP_PATH_MISSING", str(exc), path=unresolved) from exc
    if resolved != root and root not in resolved.parents:
        raise CgroupTelemetryError("CGROUP_PATH_ESCAPE", "resolved cgroup path leaves the configured root", path=resolved)
    if not resolved.is_dir():
        raise CgroupTelemetryError("CGROUP_PATH_INVALID", "resolved cgroup path is not a directory", path=resolved)
    return resolved


def _relative_to_root(path: Path, root: Path) -> str:
    if path == root:
        return "/"
    return "/" + path.relative_to(root).as_posix()


def _read_limit_record(path: Path, root: Path, *, allow_max: bool) -> CgroupLimitRecord:
    values: dict[str, LimitValue] = {}
    for filename, _expected in _LIMIT_CONTRACT:
        try:
            values[filename] = _read_limit(path / filename, allow_max=allow_max)
        except CgroupTelemetryError as exc:
            # The cgroup-v2 root has no parent and may legitimately omit
            # hierarchical limit knobs.  Such an omitted root knob is the
            # semantic equivalent of ``max``.  Every non-root omission remains
            # a contract failure because it would hide an effective ancestor.
            if path == root and allow_max and exc.code == "CGROUP_FILE_MISSING":
                values[filename] = "max"
            else:
                raise
    return CgroupLimitRecord(
        relative_path=_relative_to_root(path, root),
        memory_high=values["memory.high"],
        memory_max=values["memory.max"],
        memory_swap_max=values["memory.swap.max"],
    )


def _ancestor_paths(leaf: Path, root: Path) -> tuple[Path, ...]:
    if leaf == root or root not in leaf.parents:
        raise CgroupTelemetryError("CGROUP_PATH_ESCAPE", "worker leaf must be below the cgroup root", path=leaf)
    ancestors: list[Path] = []
    current = leaf.parent
    while True:
        ancestors.append(current)
        if current == root:
            break
        if root not in current.parents:
            raise CgroupTelemetryError("CGROUP_PATH_ESCAPE", "ancestor walk left the cgroup root", path=current)
        current = current.parent
    return tuple(ancestors)


def validate_cgroup_contract(cgroup_path: Path, cgroup_root: Path) -> CgroupContractSnapshot:
    """Validate exact leaf limits and reject every stricter numeric ancestor."""

    try:
        leaf = Path(cgroup_path).resolve(strict=True)
        root = Path(cgroup_root).resolve(strict=True)
    except OSError as exc:
        raise CgroupTelemetryError("CGROUP_PATH_INVALID", str(exc), path=Path(cgroup_path)) from exc
    if leaf == root or root not in leaf.parents:
        raise CgroupTelemetryError("CGROUP_PATH_ESCAPE", "worker leaf must be below the cgroup root", path=leaf)
    leaf_record = _read_limit_record(leaf, root, allow_max=False)
    observed_leaf = {
        "memory.high": leaf_record.memory_high,
        "memory.max": leaf_record.memory_max,
        "memory.swap.max": leaf_record.memory_swap_max,
    }
    for filename, expected in _LIMIT_CONTRACT:
        observed = observed_leaf[filename]
        if observed != expected:
            raise CgroupTelemetryError(
                "LEAF_LIMIT_MISMATCH",
                f"{filename}: expected {expected}, observed {observed}",
                path=leaf / filename,
            )

    ancestor_records = tuple(
        _read_limit_record(path, root, allow_max=True) for path in _ancestor_paths(leaf, root)
    )
    effective: dict[str, int] = {filename: expected for filename, expected in _LIMIT_CONTRACT}
    for record in ancestor_records:
        observed = {
            "memory.high": record.memory_high,
            "memory.max": record.memory_max,
            "memory.swap.max": record.memory_swap_max,
        }
        for filename, expected in _LIMIT_CONTRACT:
            value = observed[filename]
            if isinstance(value, int):
                effective[filename] = min(effective[filename], value)
                if value < expected:
                    raise CgroupTelemetryError(
                        "ANCESTOR_LIMIT_STRICTER",
                        f"{record.relative_path} {filename}={value} is tighter than {expected}",
                        path=root / record.relative_path.lstrip("/") / filename,
                    )
    return CgroupContractSnapshot(
        leaf=leaf_record,
        ancestors=ancestor_records,
        effective_memory_high=effective["memory.high"],
        effective_memory_max=effective["memory.max"],
        effective_memory_swap_max=effective["memory.swap.max"],
    )


def capture_cgroup_counters(cgroup_path: Path) -> CgroupCounterSnapshot:
    """Read one complete leaf counter snapshot or fail without partial data."""

    path = Path(cgroup_path)
    counters = {filename: _read_nonnegative_integer(path / filename) for filename in _COUNTER_FILES}
    return CgroupCounterSnapshot(
        memory_current=counters["memory.current"],
        memory_peak=counters["memory.peak"],
        memory_swap_current=counters["memory.swap.current"],
        memory_swap_peak=counters["memory.swap.peak"],
        pids_current=counters["pids.current"],
        memory_events=MappingProxyType(_read_memory_events(path / "memory.events")),
    )


def begin_worker_cgroup_telemetry(
    *,
    expected_unit_name: str,
    proc_self_cgroup: Path = Path("/proc/self/cgroup"),
    cgroup_root: Path = Path("/sys/fs/cgroup"),
) -> CgroupTelemetryStart:
    """Resolve, validate, and snapshot the worker immediately before solving."""

    if _SAFE_UNIT_RE.fullmatch(expected_unit_name) is None:
        raise CgroupTelemetryError("EXPECTED_UNIT_INVALID", f"unsafe service unit name {expected_unit_name!r}")
    cgroup_path = resolve_current_cgroup(proc_self_cgroup=proc_self_cgroup, cgroup_root=cgroup_root)
    root = Path(cgroup_root).resolve(strict=True)
    if cgroup_path.name != expected_unit_name:
        raise CgroupTelemetryError(
            "UNIT_MISMATCH",
            f"expected leaf {expected_unit_name!r}, observed {cgroup_path.name!r}",
            path=cgroup_path,
        )
    metadata = cgroup_path.stat()
    contract = validate_cgroup_contract(cgroup_path, root)
    counters = capture_cgroup_counters(cgroup_path)
    return CgroupTelemetryStart(
        expected_unit_name=expected_unit_name,
        proc_self_cgroup=Path(proc_self_cgroup),
        cgroup_root=root,
        cgroup_path=cgroup_path,
        relative_path=_relative_to_root(cgroup_path, root),
        device=metadata.st_dev,
        inode=metadata.st_ino,
        contract=contract,
        counters=counters,
    )


def _oom_attribution(delta: Mapping[str, int]) -> OomAttribution:
    if delta.get("oom_kill", 0) > 0 or delta.get("oom_group_kill", 0) > 0:
        return CGROUP_OOM_KILL
    if delta.get("oom", 0) > 0:
        return CGROUP_OOM_EVENT
    return NO_CGROUP_OOM


def finish_worker_cgroup_telemetry(start: CgroupTelemetryStart) -> CgroupTelemetryRecord:
    """Revalidate the same leaf and capture monotone end-of-attempt telemetry."""

    if not isinstance(start, CgroupTelemetryStart):
        raise CgroupTelemetryError("START_RECORD_INVALID", "finish requires a CgroupTelemetryStart")
    current = resolve_current_cgroup(
        proc_self_cgroup=start.proc_self_cgroup,
        cgroup_root=start.cgroup_root,
    )
    if current != start.cgroup_path:
        raise CgroupTelemetryError(
            "CGROUP_MOVED",
            f"worker moved from {start.cgroup_path} to {current}",
            path=current,
        )
    metadata = current.stat()
    if (metadata.st_dev, metadata.st_ino) != (start.device, start.inode):
        raise CgroupTelemetryError("CGROUP_REPLACED", "worker cgroup inode changed during the attempt", path=current)

    contract_end = validate_cgroup_contract(current, start.cgroup_root)
    counters_end = capture_cgroup_counters(current)
    if counters_end.memory_peak < start.counters.memory_peak:
        raise CgroupTelemetryError("PEAK_COUNTER_NONMONOTONE", "memory.peak decreased during the attempt", path=current)
    if counters_end.memory_swap_peak < start.counters.memory_swap_peak:
        raise CgroupTelemetryError("PEAK_COUNTER_NONMONOTONE", "memory.swap.peak decreased during the attempt", path=current)
    try:
        delta = memory_events_delta(start.counters.memory_events, counters_end.memory_events)
    except SupervisorError as exc:
        raise CgroupTelemetryError("MEMORY_EVENTS_DELTA_INVALID", str(exc), path=current / "memory.events") from exc
    return CgroupTelemetryRecord(
        expected_unit_name=start.expected_unit_name,
        relative_path=start.relative_path,
        contract_start=start.contract,
        contract_end=contract_end,
        counters_start=start.counters,
        counters_end=counters_end,
        events_delta=MappingProxyType(delta),
        oom_attribution=_oom_attribution(delta),
    )


__all__ = [
    "CgroupContractSnapshot",
    "CgroupCounterSnapshot",
    "CgroupLimitRecord",
    "CgroupTelemetryError",
    "CgroupTelemetryRecord",
    "CgroupTelemetryStart",
    "NO_CGROUP_OOM",
    "TELEMETRY_SCHEMA_VERSION",
    "begin_worker_cgroup_telemetry",
    "capture_cgroup_counters",
    "finish_worker_cgroup_telemetry",
    "resolve_current_cgroup",
    "validate_cgroup_contract",
]
