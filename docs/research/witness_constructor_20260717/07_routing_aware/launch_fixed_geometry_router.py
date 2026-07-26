"""Outer supervisor for one production-size fixed-geometry routing attempt.

The launcher snapshots one explicit geometry file, holds the repository-wide
prod-scale mutex from busy checks through terminal classification, starts one
transient user service with the exact memory contract, and refuses to treat a
malformed or drifting result as usable routing evidence.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import importlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import signal
import stat
import subprocess
import sys
from typing import Any


_BOOTSTRAP_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_BOOTSTRAP_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_PROJECT_ROOT))

_MODULE_PREFIX = "docs.research.witness_constructor_20260717.07_routing_aware"
cgroup_telemetry = importlib.import_module(f"{_MODULE_PREFIX}.cgroup_telemetry")
fixed_geometry_router = importlib.import_module(f"{_MODULE_PREFIX}.fixed_geometry_router")
run_supervisor = importlib.import_module(f"{_MODULE_PREFIX}.run_supervisor")

PROJECT_ROOT = _BOOTSTRAP_PROJECT_ROOT
RESEARCH_ROOT = Path(__file__).resolve().parent
DEFAULT_RUN_ROOT = RESEARCH_ROOT / "fixed_router_runs"
EXPECTED_BASELINE_HEAD = "ea407fafaff56333bcf18066cecf890f0ef0c6da"
WORKER_MODULE = f"{_MODULE_PREFIX}.solve_fixed_geometry_router"
WORKER_RELATIVE_PATH = Path(
    "docs/research/witness_constructor_20260717/07_routing_aware/solve_fixed_geometry_router.py"
)
LAUNCH_SCHEMA_VERSION = "fixed_geometry_router_launch.v1"
CLASSIFICATION_SCHEMA_VERSION = "fixed_geometry_router_classification.v1"
UNIT_PREFIX = "zmd-witness-fixed-router-"
EXPECTED_REQUIRED_PLACEMENTS = 266
EXPECTED_PORT_SPECS = 628

CLEAN_REJECTED_RESULT = "CLEAN_REJECTED_RESULT"
LAUNCH_TIMEOUT = "LAUNCH_TIMEOUT"

_FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_SAFE_UNIT_RE = re.compile(r"zmd-witness-fixed-router-[0-9]{8}T[0-9]{6}Z\.service")
_EVENT_KEY_RE = re.compile(r"[a-z][a-z0-9_]*")

_SOURCE_RELATIVE_PATHS = {
    "cgroup_telemetry": Path(
        "docs/research/witness_constructor_20260717/07_routing_aware/cgroup_telemetry.py"
    ),
    "fixed_geometry_router": Path(
        "docs/research/witness_constructor_20260717/07_routing_aware/fixed_geometry_router.py"
    ),
    "launcher": Path(
        "docs/research/witness_constructor_20260717/07_routing_aware/launch_fixed_geometry_router.py"
    ),
    "run_supervisor": Path(
        "docs/research/witness_constructor_20260717/07_routing_aware/run_supervisor.py"
    ),
    "worker": WORKER_RELATIVE_PATH,
}

_FEASIBLE_KEYS = {
    "schema_version",
    "status",
    "classification",
    "claim_boundary",
    "required_placements",
    "optional_placements",
    "port_specs",
    "route_components",
    "route_components_digest",
    "telemetry",
}
_REJECTED_REQUIRED_KEYS = {
    "schema_version",
    "status",
    "classification",
    "phase",
    "message",
    "route_components",
    "telemetry",
}
_CGROUP_KEYS = {
    "schema_version",
    "expected_unit_name",
    "cgroup_path",
    "contract_start",
    "contract_end",
    "counters_start",
    "counters_end",
    "memory.events.delta",
    "oom_attribution",
}
_CONTRACT_KEYS = {"leaf", "ancestors", "effective"}
_LIMIT_KEYS = {"path", "memory.high", "memory.max", "memory.swap.max"}
_EFFECTIVE_KEYS = {"memory.high", "memory.max", "memory.swap.max"}
_COUNTER_KEYS = {
    "memory.current",
    "memory.peak",
    "memory.swap.current",
    "memory.swap.peak",
    "pids.current",
    "memory.events",
}


class FixedRouterLaunchError(run_supervisor.SupervisorError):
    """One launch, snapshot, or classification invariant failed closed."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class GeometrySnapshot:
    source_path: str
    snapshot_path: Path
    sha256: str
    size_bytes: int
    required_placement_count: int
    pole_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "snapshot_path": str(self.snapshot_path),
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "required_placement_count": self.required_placement_count,
            "pole_count": self.pole_count,
        }


@dataclass(frozen=True)
class _GeometrySource:
    source_path: str
    payload: bytes
    sha256: str
    size_bytes: int
    required_placement_count: int
    pole_count: int


@dataclass(frozen=True)
class ResultInspection:
    present: bool
    parse_valid: bool
    schema_valid: bool
    integrity_valid: bool
    worker_status: str | None
    worker_classification: str | None
    oom_attribution: str | None
    sha256: str | None
    size_bytes: int | None
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AttemptClassification:
    code: str
    successful: bool
    detail: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LaunchOutcome:
    run_dir: Path
    attempt_dir: Path
    unit_name: str
    geometry_path: Path
    result_path: Path
    classification_path: Path
    classification_code: str
    successful: bool
    route_ready: bool
    dry_run: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_dir": str(self.run_dir),
            "attempt_dir": str(self.attempt_dir),
            "unit_name": self.unit_name,
            "geometry_path": str(self.geometry_path),
            "result_path": str(self.result_path),
            "classification_path": str(self.classification_path),
            "classification_code": self.classification_code,
            "successful": self.successful,
            "route_ready": self.route_ready,
            "dry_run": self.dry_run,
        }


def _normalize_now(now: datetime | None) -> datetime:
    value = datetime.now(timezone.utc) if now is None else now
    if value.tzinfo is None or value.utcoffset() is None:
        raise FixedRouterLaunchError("TIME_INVALID", "launch timestamp must be timezone-aware")
    return value.astimezone(timezone.utc)


def _utc_stamp(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%SZ")


def _repository_head(project_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise FixedRouterLaunchError("GIT_HEAD_UNAVAILABLE", str(exc)) from exc
    head = completed.stdout.strip()
    if _FULL_SHA_RE.fullmatch(head) is None:
        raise FixedRouterLaunchError("GIT_HEAD_INVALID", repr(head))
    return head


def _resolve_project_root(project_root: Path) -> Path:
    try:
        root = Path(project_root).resolve(strict=True)
    except OSError as exc:
        raise FixedRouterLaunchError("PROJECT_ROOT_INVALID", str(exc)) from exc
    marker = root / ".git"
    if (
        not root.is_dir()
        or marker.is_symlink()
        or not (marker.is_dir() or marker.is_file())
    ):
        raise FixedRouterLaunchError("PROJECT_ROOT_INVALID", f"not a Git working tree: {root}")

    git_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("GIT_")
    }
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "rev-parse",
                "--is-inside-work-tree",
                "--show-toplevel",
                "--absolute-git-dir",
            ],
            check=True,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=5.0,
            env=git_env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise FixedRouterLaunchError("PROJECT_ROOT_INVALID", f"Git probe failed for {root}: {exc}") from exc

    fields = completed.stdout.splitlines()
    if len(fields) != 3 or fields[0] != "true":
        raise FixedRouterLaunchError("PROJECT_ROOT_INVALID", f"invalid Git probe for {root}")
    try:
        reported_root = Path(fields[1]).resolve(strict=True)
        reported_git_dir = Path(fields[2]).resolve(strict=True)
    except OSError as exc:
        raise FixedRouterLaunchError("PROJECT_ROOT_INVALID", f"invalid Git paths for {root}: {exc}") from exc
    if reported_root != root or not reported_git_dir.is_dir():
        raise FixedRouterLaunchError("PROJECT_ROOT_INVALID", f"Git top-level mismatch for {root}")

    try:
        if marker.is_dir():
            marker_git_dir = marker.resolve(strict=True)
        else:
            raw_marker = marker.read_bytes()
            if not raw_marker.endswith(b"\n") or raw_marker.count(b"\n") != 1 or len(raw_marker) > 4096:
                raise ValueError("malformed linked-worktree marker")
            marker_line = raw_marker[:-1].decode("utf-8", errors="strict")
            if not marker_line.startswith("gitdir: ") or not marker_line[8:]:
                raise ValueError("malformed linked-worktree marker")
            marker_target = Path(marker_line[8:])
            if not marker_target.is_absolute():
                marker_target = marker.parent / marker_target
            marker_git_dir = marker_target.resolve(strict=True)

            backlink = marker_git_dir / "gitdir"
            if backlink.is_symlink() or not backlink.is_file():
                raise ValueError("linked-worktree backlink is missing")
            raw_backlink = backlink.read_bytes()
            if not raw_backlink.endswith(b"\n") or raw_backlink.count(b"\n") != 1 or len(raw_backlink) > 4096:
                raise ValueError("malformed linked-worktree backlink")
            backlink_target = Path(raw_backlink[:-1].decode("utf-8", errors="strict"))
            if not backlink_target.is_absolute():
                backlink_target = backlink.parent / backlink_target
            if backlink_target.resolve(strict=True) != marker.resolve(strict=True):
                raise ValueError("linked-worktree backlink mismatch")

            commondir = marker_git_dir / "commondir"
            if commondir.is_symlink() or not commondir.is_file():
                raise ValueError("linked-worktree commondir is missing")
            raw_commondir = commondir.read_bytes()
            if not raw_commondir.endswith(b"\n") or raw_commondir.count(b"\n") != 1 or len(raw_commondir) > 4096:
                raise ValueError("malformed linked-worktree commondir")
            common_target = Path(raw_commondir[:-1].decode("utf-8", errors="strict"))
            if not common_target.is_absolute():
                common_target = commondir.parent / common_target
            common_git_dir = common_target.resolve(strict=True)
            if (
                not common_git_dir.is_dir()
                or marker_git_dir.parent.resolve(strict=True)
                != (common_git_dir / "worktrees").resolve(strict=True)
            ):
                raise ValueError("linked-worktree admin directory mismatch")
    except (OSError, UnicodeError, ValueError) as exc:
        raise FixedRouterLaunchError("PROJECT_ROOT_INVALID", f"invalid .git marker for {root}: {exc}") from exc
    if marker_git_dir != reported_git_dir:
        raise FixedRouterLaunchError("PROJECT_ROOT_INVALID", f"Git directory mismatch for {root}")
    return root


def _require_output_scope(path: Path) -> Path:
    root = RESEARCH_ROOT.resolve(strict=True)
    candidate = Path(path).resolve(strict=False)
    if candidate != root and root not in candidate.parents:
        raise FixedRouterLaunchError(
            "OUTPUT_SCOPE_INVALID",
            f"output path must remain below {root}: {candidate}",
        )
    return candidate


def _strict_json_object(payload: bytes, *, label: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise FixedRouterLaunchError("JSON_INVALID", f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise FixedRouterLaunchError("JSON_INVALID", f"{label}: non-finite value {value}")

    try:
        value = json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
        )
    except FixedRouterLaunchError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FixedRouterLaunchError("JSON_INVALID", f"{label}: {exc}") from exc
    if type(value) is not dict:
        raise FixedRouterLaunchError("JSON_INVALID", f"{label}: root must be an object")
    return value


def _read_geometry_source(path: Path) -> _GeometrySource:
    source = Path(path).absolute()
    try:
        metadata = source.lstat()
    except OSError as exc:
        raise FixedRouterLaunchError("GEOMETRY_UNREADABLE", str(exc)) from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise FixedRouterLaunchError(
            "GEOMETRY_FILE_TYPE",
            "geometry source must be a regular non-symlink file",
        )
    snapshot = run_supervisor._read_stable_snapshot(source)
    payload = _strict_json_object(snapshot.payload, label="geometry source")
    try:
        geometry = fixed_geometry_router.parse_geometry_payload(payload, minimum_poles=9)
    except fixed_geometry_router.FixedGeometryRouterError as exc:
        raise FixedRouterLaunchError("GEOMETRY_SCHEMA_INVALID", str(exc)) from exc
    if len(geometry.required_placements) != EXPECTED_REQUIRED_PLACEMENTS:
        raise FixedRouterLaunchError(
            "GEOMETRY_REQUIRED_COUNT",
            f"expected {EXPECTED_REQUIRED_PLACEMENTS}, observed {len(geometry.required_placements)}",
        )
    return _GeometrySource(
        source_path=str(source),
        payload=snapshot.payload,
        sha256=snapshot.sha256,
        size_bytes=snapshot.size_bytes,
        required_placement_count=len(geometry.required_placements),
        pole_count=len(geometry.pole_anchors),
    )


def _materialize_geometry_snapshot(
    source: _GeometrySource,
    *,
    attempt_dir: Path,
) -> GeometrySnapshot:
    target = attempt_dir / f"geometry.{source.sha256}.json"
    run_supervisor.write_bytes_exclusive(target, source.payload)
    observed = run_supervisor._read_stable_snapshot(target)
    if (
        observed.sha256 != source.sha256
        or observed.size_bytes != source.size_bytes
        or observed.payload != source.payload
    ):
        raise FixedRouterLaunchError("GEOMETRY_SNAPSHOT_DRIFT", str(target))
    return GeometrySnapshot(
        source_path=source.source_path,
        snapshot_path=target,
        sha256=source.sha256,
        size_bytes=source.size_bytes,
        required_placement_count=source.required_placement_count,
        pole_count=source.pole_count,
    )


def _source_records(project_root: Path) -> dict[str, run_supervisor.FileRecord]:
    return {
        name: run_supervisor.file_record(project_root / relative, relative_to=project_root)
        for name, relative in sorted(_SOURCE_RELATIVE_PATHS.items())
    }


def _require_mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", f"{label} must be an object")
    return value


def _require_array(value: Any, *, label: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", f"{label} must be an array")
    return value


def _require_string(value: Any, *, label: str) -> str:
    if type(value) is not str or not value:
        raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", f"{label} must be a nonempty string")
    return value


def _require_nonnegative_integer(value: Any, *, label: str) -> int:
    if type(value) is not int or value < 0:
        raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", f"{label} must be a nonnegative integer")
    return value


def _validate_events(value: Any, *, label: str) -> dict[str, int]:
    events = _require_mapping(value, label=label)
    if any(_EVENT_KEY_RE.fullmatch(key) is None for key in events):
        raise FixedRouterLaunchError("CGROUP_TELEMETRY_INVALID", f"{label} has an invalid key")
    missing = set(run_supervisor.REQUIRED_MEMORY_EVENT_KEYS) - set(events)
    if missing:
        raise FixedRouterLaunchError(
            "CGROUP_TELEMETRY_INVALID",
            f"{label} misses {sorted(missing)}",
        )
    return {
        key: _require_nonnegative_integer(item, label=f"{label}.{key}")
        for key, item in sorted(events.items())
    }


def _validate_cgroup_path(value: Any, *, unit_name: str, label: str) -> str:
    path = _require_string(value, label=label)
    if not path.startswith("/") or path.startswith("//"):
        raise FixedRouterLaunchError("CGROUP_TELEMETRY_INVALID", f"{label} is not canonical")
    segments = path.split("/")[1:]
    if not segments or any(segment in {"", ".", ".."} for segment in segments):
        raise FixedRouterLaunchError("CGROUP_TELEMETRY_INVALID", f"{label} is not canonical")
    if segments[-1] != unit_name:
        raise FixedRouterLaunchError("CGROUP_UNIT_MISMATCH", f"{label} does not end in {unit_name!r}")
    return path


def _validate_limit_record(
    value: Any,
    *,
    label: str,
    leaf: bool,
    unit_name: str,
) -> str:
    record = _require_mapping(value, label=label)
    if set(record) != _LIMIT_KEYS:
        raise FixedRouterLaunchError("CGROUP_TELEMETRY_INVALID", f"{label} keys differ")
    path = record["path"]
    if leaf:
        path = _validate_cgroup_path(path, unit_name=unit_name, label=f"{label}.path")
    elif type(path) is not str or not path.startswith("/") or "//" in path:
        raise FixedRouterLaunchError("CGROUP_TELEMETRY_INVALID", f"{label}.path is invalid")
    expected = {
        "memory.high": run_supervisor.MEMORY_HIGH_BYTES,
        "memory.max": run_supervisor.MEMORY_MAX_BYTES,
        "memory.swap.max": run_supervisor.MEMORY_SWAP_MAX_BYTES,
    }
    for key, required in expected.items():
        observed = record[key]
        if leaf:
            if type(observed) is not int or observed != required:
                raise FixedRouterLaunchError(
                    "CGROUP_CONTRACT_INVALID",
                    f"{label}.{key}={observed!r}",
                )
        elif observed != "max" and (type(observed) is not int or observed < required):
            raise FixedRouterLaunchError(
                "CGROUP_CONTRACT_INVALID",
                f"{label}.{key}={observed!r}",
            )
    return str(path)


def _validate_contract(value: Any, *, label: str, unit_name: str, cgroup_path: str) -> None:
    contract = _require_mapping(value, label=label)
    if set(contract) != _CONTRACT_KEYS:
        raise FixedRouterLaunchError("CGROUP_TELEMETRY_INVALID", f"{label} keys differ")
    leaf_path = _validate_limit_record(
        contract["leaf"],
        label=f"{label}.leaf",
        leaf=True,
        unit_name=unit_name,
    )
    if leaf_path != cgroup_path:
        raise FixedRouterLaunchError("CGROUP_CONTRACT_INVALID", f"{label} leaf path differs")
    ancestors = _require_array(contract["ancestors"], label=f"{label}.ancestors")
    if not ancestors:
        raise FixedRouterLaunchError("CGROUP_CONTRACT_INVALID", f"{label} has no ancestors")
    ancestor_paths = [
        _validate_limit_record(
            record,
            label=f"{label}.ancestors[{index}]",
            leaf=False,
            unit_name=unit_name,
        )
        for index, record in enumerate(ancestors)
    ]
    if len(set(ancestor_paths)) != len(ancestor_paths) or ancestor_paths[-1] != "/":
        raise FixedRouterLaunchError("CGROUP_CONTRACT_INVALID", f"{label} ancestor chain is invalid")
    effective = _require_mapping(contract["effective"], label=f"{label}.effective")
    expected = {
        "memory.high": run_supervisor.MEMORY_HIGH_BYTES,
        "memory.max": run_supervisor.MEMORY_MAX_BYTES,
        "memory.swap.max": run_supervisor.MEMORY_SWAP_MAX_BYTES,
    }
    if set(effective) != _EFFECTIVE_KEYS or dict(effective) != expected:
        raise FixedRouterLaunchError("CGROUP_CONTRACT_INVALID", f"{label}.effective differs")


def _validate_counters(value: Any, *, label: str) -> tuple[dict[str, int], dict[str, int]]:
    counters = _require_mapping(value, label=label)
    if set(counters) != _COUNTER_KEYS:
        raise FixedRouterLaunchError("CGROUP_TELEMETRY_INVALID", f"{label} keys differ")
    scalars = {
        key: _require_nonnegative_integer(counters[key], label=f"{label}.{key}")
        for key in sorted(_COUNTER_KEYS - {"memory.events"})
    }
    events = _validate_events(counters["memory.events"], label=f"{label}.memory.events")
    return scalars, events


def _validate_cgroup_telemetry(value: Any, *, unit_name: str) -> str:
    telemetry = _require_mapping(value, label="telemetry.cgroup")
    if set(telemetry) != _CGROUP_KEYS:
        raise FixedRouterLaunchError("CGROUP_TELEMETRY_INVALID", "cgroup keys differ")
    if telemetry["schema_version"] != cgroup_telemetry.TELEMETRY_SCHEMA_VERSION:
        raise FixedRouterLaunchError("CGROUP_TELEMETRY_INVALID", "unexpected cgroup schema")
    if telemetry["expected_unit_name"] != unit_name:
        raise FixedRouterLaunchError("CGROUP_UNIT_MISMATCH", repr(telemetry["expected_unit_name"]))
    cgroup_path = _validate_cgroup_path(
        telemetry["cgroup_path"],
        unit_name=unit_name,
        label="telemetry.cgroup.cgroup_path",
    )
    _validate_contract(
        telemetry["contract_start"],
        label="telemetry.cgroup.contract_start",
        unit_name=unit_name,
        cgroup_path=cgroup_path,
    )
    _validate_contract(
        telemetry["contract_end"],
        label="telemetry.cgroup.contract_end",
        unit_name=unit_name,
        cgroup_path=cgroup_path,
    )
    start_scalars, start_events = _validate_counters(
        telemetry["counters_start"],
        label="telemetry.cgroup.counters_start",
    )
    end_scalars, end_events = _validate_counters(
        telemetry["counters_end"],
        label="telemetry.cgroup.counters_end",
    )
    for peak in ("memory.peak", "memory.swap.peak"):
        if end_scalars[peak] < start_scalars[peak]:
            raise FixedRouterLaunchError("CGROUP_TELEMETRY_INVALID", f"{peak} decreased")
    delta = run_supervisor.memory_events_delta(start_events, end_events)
    observed_delta = _validate_events(
        telemetry["memory.events.delta"],
        label="telemetry.cgroup.memory.events.delta",
    )
    if observed_delta != delta:
        raise FixedRouterLaunchError("CGROUP_TELEMETRY_INVALID", "memory.events.delta differs")
    expected_oom = cgroup_telemetry.NO_CGROUP_OOM
    if delta.get("oom_kill", 0) > 0 or delta.get("oom_group_kill", 0) > 0:
        expected_oom = run_supervisor.CGROUP_OOM_KILL
    elif delta.get("oom", 0) > 0:
        expected_oom = run_supervisor.CGROUP_OOM_EVENT
    if telemetry["oom_attribution"] != expected_oom:
        raise FixedRouterLaunchError(
            "CGROUP_TELEMETRY_INVALID",
            f"oom attribution differs: expected {expected_oom!r}",
        )
    return expected_oom


def _validate_input_snapshot(value: Any, *, geometry_sha256: str) -> None:
    snapshot = _require_mapping(value, label="telemetry.input_snapshot")
    if snapshot.get("geometry_sha256") != geometry_sha256:
        raise FixedRouterLaunchError("RESULT_GEOMETRY_MISMATCH", "geometry digest differs")
    if snapshot.get("post_solve_revalidated") is not True:
        raise FixedRouterLaunchError(
            "RESULT_GEOMETRY_REVALIDATION_MISSING",
            "worker did not report a post-attempt geometry revalidation",
        )
    hashes = _require_mapping(
        snapshot.get("dependency_hashes"),
        label="telemetry.input_snapshot.dependency_hashes",
    )
    if not hashes or any(
        _SHA256_RE.fullmatch(value) is None
        for key, value in hashes.items()
        if type(key) is str and type(value) is str
    ) or any(type(key) is not str or type(value) is not str for key, value in hashes.items()):
        raise FixedRouterLaunchError(
            "RESULT_DEPENDENCY_HASHES_INVALID",
            "dependency hashes are malformed",
        )


def _validate_result_schema(
    record: Mapping[str, Any],
    *,
    geometry: GeometrySnapshot,
    unit_name: str,
) -> str | None:
    if record.get("schema_version") != fixed_geometry_router.OUTPUT_SCHEMA_VERSION:
        raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", "unexpected schema version")
    status = record.get("status")
    if status == "FEASIBLE":
        if set(record) != _FEASIBLE_KEYS:
            raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", "feasible top-level keys differ")
        if record.get("classification") != "STRICT_ROUTES_INDEPENDENTLY_REACHABLE":
            raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", "feasible classification differs")
        if record.get("claim_boundary") != "research_witness_candidate_only":
            raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", "claim boundary differs")
        required = _require_array(record["required_placements"], label="required_placements")
        optional = _require_array(record["optional_placements"], label="optional_placements")
        port_specs = _require_array(record["port_specs"], label="port_specs")
        components = _require_array(record["route_components"], label="route_components")
        if len(required) != geometry.required_placement_count:
            raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", "required placement count differs")
        if len(optional) != geometry.pole_count:
            raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", "pole placement count differs")
        if len(port_specs) != EXPECTED_PORT_SPECS:
            raise FixedRouterLaunchError(
                "RESULT_SCHEMA_INVALID",
                f"expected {EXPECTED_PORT_SPECS} port specs, observed {len(port_specs)}",
            )
        if not components:
            raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", "feasible result has no routes")
        for label, rows in (
            ("required_placements", required),
            ("optional_placements", optional),
            ("port_specs", port_specs),
            ("route_components", components),
        ):
            if any(not isinstance(row, Mapping) for row in rows):
                raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", f"{label} contains a non-object")
        ids = [row.get("instance_id") for row in (*required, *optional)]
        if any(type(instance_id) is not str or not instance_id for instance_id in ids):
            raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", "placement IDs are invalid")
        if len(ids) != len(set(ids)):
            raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", "placement IDs are duplicated")
        route_digest = record.get("route_components_digest")
        if type(route_digest) is not str or _SHA256_RE.fullmatch(route_digest) is None:
            raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", "route digest is malformed")
        if route_digest != fixed_geometry_router.canonical_digest(components):
            raise FixedRouterLaunchError("RESULT_ROUTE_DIGEST_MISMATCH", "route digest differs")
        telemetry = _require_mapping(record["telemetry"], label="telemetry")
        _validate_input_snapshot(telemetry.get("input_snapshot"), geometry_sha256=geometry.sha256)
        oom = _validate_cgroup_telemetry(telemetry.get("cgroup"), unit_name=unit_name)
        if oom != cgroup_telemetry.NO_CGROUP_OOM:
            raise FixedRouterLaunchError("RESULT_CGROUP_OOM", oom)
        return oom

    if status == "REJECTED":
        allowed = _REJECTED_REQUIRED_KEYS | {"error_code"}
        if not _REJECTED_REQUIRED_KEYS <= set(record) or not set(record) <= allowed:
            raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", "rejected top-level keys differ")
        _require_string(record.get("classification"), label="classification")
        _require_string(record.get("phase"), label="phase")
        _require_string(record.get("message"), label="message")
        if "error_code" in record:
            _require_string(record["error_code"], label="error_code")
        components = _require_array(record["route_components"], label="route_components")
        if components:
            raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", "rejected result carries routes")
        telemetry = _require_mapping(record["telemetry"], label="telemetry")
        input_snapshot = telemetry.get("input_snapshot")
        if input_snapshot is not None:
            snapshot = _require_mapping(input_snapshot, label="telemetry.input_snapshot")
            observed = snapshot.get("geometry_sha256")
            if observed is not None and observed != geometry.sha256:
                raise FixedRouterLaunchError("RESULT_GEOMETRY_MISMATCH", "geometry digest differs")
        cgroup = telemetry.get("cgroup")
        return None if cgroup is None else _validate_cgroup_telemetry(cgroup, unit_name=unit_name)

    raise FixedRouterLaunchError("RESULT_SCHEMA_INVALID", f"unexpected status {status!r}")


def _same_file_records(
    left: Mapping[str, run_supervisor.FileRecord],
    right: Mapping[str, run_supervisor.FileRecord],
) -> bool:
    return {
        key: (value.path, value.sha256, value.size_bytes) for key, value in left.items()
    } == {
        key: (value.path, value.sha256, value.size_bytes) for key, value in right.items()
    }


def _inspect_result(
    result_path: Path,
    *,
    project_root: Path,
    geometry: GeometrySnapshot,
    unit_name: str,
    expected_sources: Mapping[str, run_supervisor.FileRecord],
) -> ResultInspection:
    if not result_path.exists():
        return ResultInspection(False, False, False, False, None, None, None, None, None, ("result missing",))
    if result_path.is_symlink() or not result_path.is_file():
        return ResultInspection(
            True,
            False,
            False,
            False,
            None,
            None,
            None,
            None,
            None,
            ("result is not a regular non-symlink file",),
        )
    try:
        result_snapshot = run_supervisor._read_stable_snapshot(result_path)
    except run_supervisor.SupervisorError as exc:
        return ResultInspection(True, False, False, False, None, None, None, None, None, (str(exc),))
    try:
        record = _strict_json_object(result_snapshot.payload, label="worker result")
    except FixedRouterLaunchError as exc:
        return ResultInspection(
            True,
            False,
            False,
            False,
            None,
            None,
            None,
            result_snapshot.sha256,
            result_snapshot.size_bytes,
            (str(exc),),
        )

    status = record.get("status") if type(record.get("status")) is str else None
    worker_classification = (
        record.get("classification") if type(record.get("classification")) is str else None
    )
    errors: list[str] = []
    schema_valid = True
    oom_attribution: str | None = None
    try:
        oom_attribution = _validate_result_schema(record, geometry=geometry, unit_name=unit_name)
    except (FixedRouterLaunchError, run_supervisor.SupervisorError) as exc:
        schema_valid = False
        errors.append(str(exc))

    integrity_valid = schema_valid
    if integrity_valid:
        try:
            geometry_now = run_supervisor._read_stable_snapshot(geometry.snapshot_path)
            if (
                geometry_now.sha256 != geometry.sha256
                or geometry_now.size_bytes != geometry.size_bytes
            ):
                raise FixedRouterLaunchError("GEOMETRY_SNAPSHOT_DRIFT", str(geometry.snapshot_path))
            if not _same_file_records(expected_sources, _source_records(project_root)):
                raise FixedRouterLaunchError("SOURCE_DRIFT", "launcher/worker source bytes changed")
            if _repository_head(project_root) != EXPECTED_BASELINE_HEAD:
                raise FixedRouterLaunchError("GIT_HEAD_DRIFT", "repository HEAD changed")
            result_now = run_supervisor._read_stable_snapshot(result_path)
            if (
                result_now.sha256 != result_snapshot.sha256
                or result_now.size_bytes != result_snapshot.size_bytes
            ):
                raise FixedRouterLaunchError("RESULT_DRIFT", "result changed during inspection")
        except (FixedRouterLaunchError, run_supervisor.SupervisorError) as exc:
            integrity_valid = False
            errors.append(str(exc))

    return ResultInspection(
        True,
        True,
        schema_valid,
        integrity_valid,
        status,
        worker_classification,
        oom_attribution,
        result_snapshot.sha256,
        result_snapshot.size_bytes,
        tuple(errors),
    )


def _classify_attempt(
    *,
    timed_out: bool,
    returncode: int | None,
    inspection: ResultInspection,
) -> AttemptClassification:
    if timed_out:
        return AttemptClassification(LAUNCH_TIMEOUT, False, "systemd-run wait timed out")
    if returncode is None or isinstance(returncode, bool) or not isinstance(returncode, int):
        return AttemptClassification(run_supervisor.PROCESS_NONZERO_EXIT, False, "missing return code")
    if returncode < 0:
        signal_number = -returncode
        if signal_number == signal.SIGSEGV:
            return AttemptClassification(run_supervisor.WORKER_SIGNAL_SIGSEGV, False, "SIGSEGV")
        try:
            name = signal.Signals(signal_number).name
        except ValueError:
            name = f"SIG{signal_number}"
        return AttemptClassification(run_supervisor.WORKER_SIGNAL_OTHER, False, name)
    if returncode != 0:
        return AttemptClassification(
            run_supervisor.PROCESS_NONZERO_EXIT,
            False,
            f"exit {returncode}",
        )
    if not inspection.present or not inspection.parse_valid:
        return AttemptClassification(run_supervisor.RESULT_MISSING_OR_INVALID, False, None)
    if not inspection.schema_valid:
        return AttemptClassification(run_supervisor.RESULT_SCHEMA_INVALID, False, None)
    if not inspection.integrity_valid:
        return AttemptClassification(run_supervisor.RESULT_INTEGRITY_INVALID, False, None)
    if inspection.worker_status == "FEASIBLE":
        return AttemptClassification(run_supervisor.SUCCESS, True, inspection.worker_classification)
    if inspection.worker_status == "REJECTED":
        if inspection.oom_attribution == run_supervisor.CGROUP_OOM_KILL:
            return AttemptClassification(run_supervisor.CGROUP_OOM_KILL, False, inspection.worker_classification)
        if inspection.oom_attribution == run_supervisor.CGROUP_OOM_EVENT:
            return AttemptClassification(run_supervisor.CGROUP_OOM_EVENT, False, inspection.worker_classification)
        return AttemptClassification(CLEAN_REJECTED_RESULT, False, inspection.worker_classification)
    return AttemptClassification(run_supervisor.RESULT_SCHEMA_INVALID, False, "unexpected worker status")


def _worker_command(
    *,
    project_root: Path,
    geometry: GeometrySnapshot,
    result_path: Path,
    unit_name: str,
    time_limit_seconds: float,
    workers: int,
) -> tuple[str, ...]:
    if (
        isinstance(time_limit_seconds, bool)
        or not isinstance(time_limit_seconds, (int, float))
        or not math.isfinite(float(time_limit_seconds))
        or float(time_limit_seconds) <= 0.0
    ):
        raise FixedRouterLaunchError("TIME_LIMIT_INVALID", repr(time_limit_seconds))
    if type(workers) is not int or not 1 <= workers <= 64:
        raise FixedRouterLaunchError("WORKER_COUNT_INVALID", repr(workers))
    interpreter = Path(sys.executable).resolve(strict=True)
    return (
        str(interpreter),
        "-m",
        WORKER_MODULE,
        "--project-root",
        str(project_root),
        "--geometry",
        str(geometry.snapshot_path),
        "--geometry-sha256",
        geometry.sha256,
        "--out",
        str(result_path),
        "--expected-unit",
        unit_name,
        "--time-limit-seconds",
        str(float(time_limit_seconds)),
        "--workers",
        str(workers),
    )


def _launch_command(
    *,
    project_root: Path,
    unit_name: str,
    worker_command: Sequence[str],
) -> tuple[str, ...]:
    command = run_supervisor.build_systemd_run_command(
        unit_name=unit_name,
        working_directory=project_root,
        command=worker_command,
    )
    required_flags = {
        "--user",
        "--wait",
        "--pipe",
        "--collect",
        "--service-type=exec",
        "--expand-environment=no",
        f"--unit={unit_name}",
        f"--working-directory={project_root}",
        *(f"--property={item}" for item in run_supervisor.CGROUP_PROPERTIES),
    }
    if not command or command[0] != "systemd-run":
        raise FixedRouterLaunchError("COMMAND_INVALID", "not a systemd-run command")
    if any(command.count(flag) != 1 for flag in required_flags):
        raise FixedRouterLaunchError("COMMAND_INVALID", "systemd lifecycle contract differs")
    unexpected_properties = [
        item for item in command if item.startswith("--property=") and item not in required_flags
    ]
    if unexpected_properties or tuple(command[-len(worker_command) :]) != tuple(worker_command):
        raise FixedRouterLaunchError("COMMAND_INVALID", "worker suffix or properties differ")
    return command


def _process_markers() -> frozenset[str]:
    return frozenset({*run_supervisor.RELATED_PROCESS_MARKERS, WORKER_RELATIVE_PATH.name})


def _as_bytes(value: object) -> bytes:
    if isinstance(value, bytes):
        return value
    if value is None:
        return b""
    return str(value).encode("utf-8", errors="replace")


def launch_fixed_geometry_router(
    geometry_path: Path,
    *,
    project_root: Path = PROJECT_ROOT,
    run_root: Path = DEFAULT_RUN_ROOT,
    time_limit_seconds: float = 3600.0,
    workers: int = 8,
    dry_run: bool = False,
    now: datetime | None = None,
    lock_path: Path | None = None,
    unit_query: Callable[[], tuple[str, ...]] = run_supervisor.query_active_related_units,
    process_query: Callable[..., tuple[dict[str, Any], ...]] = run_supervisor.detect_active_related_processes,
    systemd_runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> LaunchOutcome:
    """Create, launch, inspect, and classify exactly one immutable attempt."""

    root = _resolve_project_root(project_root)
    output_root = _require_output_scope(run_root)
    timestamp = _normalize_now(now)
    with run_supervisor.acquire_prod_scale_lock(lock_path):
        head = _repository_head(root)
        if head != EXPECTED_BASELINE_HEAD:
            raise FixedRouterLaunchError(
                "BASELINE_HEAD_MISMATCH",
                f"expected {EXPECTED_BASELINE_HEAD}, observed {head}",
            )
        sources = _source_records(root)
        active_units = unit_query()
        active_processes = process_query(markers=_process_markers())
        if active_units or active_processes:
            raise run_supervisor.BusyError(
                f"related prod-scale work is active: units={active_units!r}, processes={active_processes!r}"
            )

        geometry_source = _read_geometry_source(geometry_path)
        run_dir = run_supervisor.create_run_directory(
            output_root,
            EXPECTED_BASELINE_HEAD[:7],
            now=timestamp,
        )
        attempt_dir = run_supervisor.create_attempt_directory(run_dir, 1)
        geometry = _materialize_geometry_snapshot(geometry_source, attempt_dir=attempt_dir)
        unit_name = f"{UNIT_PREFIX}{_utc_stamp(timestamp)}.service"
        if _SAFE_UNIT_RE.fullmatch(unit_name) is None:
            raise FixedRouterLaunchError("UNIT_NAME_INVALID", unit_name)
        result_path = attempt_dir / "fixed_geometry_router_result.json"
        worker_argv = _worker_command(
            project_root=root,
            geometry=geometry,
            result_path=result_path,
            unit_name=unit_name,
            time_limit_seconds=time_limit_seconds,
            workers=workers,
        )
        command = _launch_command(
            project_root=root,
            unit_name=unit_name,
            worker_command=worker_argv,
        )
        header = {
            "schema_version": LAUNCH_SCHEMA_VERSION,
            "created_utc": timestamp.isoformat(),
            "baseline_head": EXPECTED_BASELINE_HEAD,
            "observed_head": head,
            "unit_name": unit_name,
            "dry_run": bool(dry_run),
            "pid": os.getpid(),
            "active_units": list(active_units),
            "active_processes": list(active_processes),
            "sources": {name: record.as_dict() for name, record in sorted(sources.items())},
            "geometry": geometry.as_dict(),
            "result_path": str(result_path),
            "time_limit_seconds": float(time_limit_seconds),
            "workers": workers,
            "wait_contract": "worker_internal_time_limit_then_systemd_wait",
            "lock_path": str(
                run_supervisor.prod_scale_lock_path() if lock_path is None else Path(lock_path)
            ),
        }
        run_supervisor.write_json_exclusive(attempt_dir / "header.json", header)
        run_supervisor.write_json_exclusive(
            attempt_dir / "command.json",
            {"argv": list(command), "shell_display": shlex.join(command)},
        )

        classification_path = attempt_dir / "classification.json"
        if dry_run:
            run_supervisor.write_bytes_exclusive(attempt_dir / "stdout.log", b"")
            run_supervisor.write_bytes_exclusive(attempt_dir / "stderr.log", b"")
            run_supervisor.write_json_exclusive(
                classification_path,
                {
                    "schema_version": CLASSIFICATION_SCHEMA_VERSION,
                    "dry_run": True,
                    "classification": {
                        "code": "DRY_RUN",
                        "successful": True,
                        "detail": "command and immutable geometry snapshot recorded; worker not started",
                    },
                    "route_ready": False,
                    "result_expected_but_not_created": str(result_path),
                },
            )
            return LaunchOutcome(
                run_dir,
                attempt_dir,
                unit_name,
                geometry.snapshot_path,
                result_path,
                classification_path,
                "DRY_RUN",
                True,
                False,
                True,
            )

        timed_out = False
        launch_error: str | None = None
        returncode: int | None = None
        stdout = b""
        stderr = b""
        try:
            completed = systemd_runner(
                command,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=root,
            )
            returncode = completed.returncode
            stdout = _as_bytes(completed.stdout)
            stderr = _as_bytes(completed.stderr)
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            launch_error = str(exc)
            stdout = _as_bytes(exc.stdout)
            stderr = _as_bytes(exc.stderr)
        except OSError as exc:
            launch_error = str(exc)
            stderr = _as_bytes(f"{exc}\n")

        run_supervisor.write_bytes_exclusive(attempt_dir / "stdout.log", stdout)
        run_supervisor.write_bytes_exclusive(attempt_dir / "stderr.log", stderr)
        inspection = _inspect_result(
            result_path,
            project_root=root,
            geometry=geometry,
            unit_name=unit_name,
            expected_sources=sources,
        )
        classification = _classify_attempt(
            timed_out=timed_out,
            returncode=returncode,
            inspection=inspection,
        )
        route_ready = classification.successful and inspection.worker_status == "FEASIBLE"
        run_supervisor.write_json_exclusive(
            classification_path,
            {
                "schema_version": CLASSIFICATION_SCHEMA_VERSION,
                "dry_run": False,
                "classification": classification.as_dict(),
                "route_ready": route_ready,
                "launch_error": launch_error,
                "process": {"timed_out": timed_out, "returncode": returncode},
                "geometry": geometry.as_dict(),
                "result": inspection.as_dict(),
            },
        )
        return LaunchOutcome(
            run_dir,
            attempt_dir,
            unit_name,
            geometry.snapshot_path,
            result_path,
            classification_path,
            classification.code,
            classification.successful,
            route_ready,
            False,
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geometry", type=Path)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--time-limit-seconds", type=float, default=3600.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        outcome = launch_fixed_geometry_router(
            args.geometry,
            project_root=args.project_root,
            run_root=args.run_root,
            time_limit_seconds=args.time_limit_seconds,
            workers=args.workers,
            dry_run=args.dry_run,
        )
    except (FixedRouterLaunchError, run_supervisor.SupervisorError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(outcome.as_dict(), ensure_ascii=True, sort_keys=True))
    return 0 if outcome.dry_run or outcome.route_ready else 1


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
