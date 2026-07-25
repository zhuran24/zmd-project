"""No-overwrite supervisor for the production-size shelf/power worker.

This launcher is deliberately small and research-scoped.  It performs the
read-only busy checks, holds the repository-wide prod-scale mutex from those
checks through terminal evidence publication, starts exactly one transient
user service, and classifies the attempt from the worker result plus cgroup-v2
telemetry.  It never stops or signals an existing service or process.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence


_BOOTSTRAP_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_BOOTSTRAP_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_PROJECT_ROOT))

_MODULE_PREFIX = "docs.research.witness_constructor_20260717.07_routing_aware"
run_supervisor = importlib.import_module(f"{_MODULE_PREFIX}.run_supervisor")
shelf_constructor = importlib.import_module(f"{_MODULE_PREFIX}.shelf_constructor")
strict_contract = importlib.import_module(f"{_MODULE_PREFIX}.strict_contract")


PROJECT_ROOT = _BOOTSTRAP_PROJECT_ROOT
RESEARCH_ROOT = Path(__file__).resolve().parent
DEFAULT_RUN_ROOT = RESEARCH_ROOT / "solver_runs"
WORKER_PATH = RESEARCH_ROOT / "solve_shelf_power.py"
EXPECTED_BASELINE_HEAD = "ea407fafaff56333bcf18066cecf890f0ef0c6da"
LAUNCH_SCHEMA_VERSION = "routing_aware_shelf_power_launch.v1"
CLASSIFICATION_SCHEMA_VERSION = "routing_aware_shelf_power_classification.v1"
UNIT_PREFIX = "zmd-witness-shelf-power-"

_FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_SAFE_UNIT_RE = re.compile(r"zmd-witness-shelf-power-[0-9]{8}T[0-9]{6}Z\.service")
_EVENT_KEY_RE = re.compile(r"[a-z][a-z0-9_]*")
_RESULT_KEYS = {
    "schema_version",
    "status",
    "input_sha256",
    "manufacturing_slots",
    "pole_anchors",
    "pole_bay_anchors",
    "protected_rect",
    "network_edges",
    "stats",
    "route_validation",
    "cgroup_telemetry",
    "failure",
}
_RESULT_STATUSES = {
    "OPTIMAL",
    "FEASIBLE",
    "INFEASIBLE",
    "UNKNOWN",
    "MODEL_INVALID",
    "WORKER_ERROR",
    "CGROUP_OOM",
}
_TELEMETRY_KEYS = {
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


class ShelfPowerLaunchError(run_supervisor.SupervisorError):
    """One launch or evidence contract failed closed."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class ResultInspection:
    present: bool
    parse_valid: bool
    schema_valid: bool
    integrity_valid: bool
    solver_status: str | None
    memory_events_before: Mapping[str, int] | None
    memory_events_after: Mapping[str, int] | None
    sha256: str | None
    size_bytes: int | None
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "parse_valid": self.parse_valid,
            "schema_valid": self.schema_valid,
            "integrity_valid": self.integrity_valid,
            "solver_status": self.solver_status,
            "memory_events_before": (
                dict(self.memory_events_before)
                if self.memory_events_before is not None
                else None
            ),
            "memory_events_after": (
                dict(self.memory_events_after)
                if self.memory_events_after is not None
                else None
            ),
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class LaunchOutcome:
    run_dir: Path
    attempt_dir: Path
    unit_name: str
    result_path: Path
    classification_path: Path
    classification_code: str
    successful: bool
    geometry_ready: bool
    dry_run: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_dir": str(self.run_dir),
            "attempt_dir": str(self.attempt_dir),
            "unit_name": self.unit_name,
            "result_path": str(self.result_path),
            "classification_path": str(self.classification_path),
            "classification_code": self.classification_code,
            "successful": self.successful,
            "geometry_ready": self.geometry_ready,
            "dry_run": self.dry_run,
        }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_now(now: datetime | None) -> datetime:
    value = _utc_now() if now is None else now
    if value.tzinfo is None or value.utcoffset() is None:
        raise ShelfPowerLaunchError("TIME_INVALID", "launch timestamp must be timezone-aware")
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
        raise ShelfPowerLaunchError("GIT_HEAD_UNAVAILABLE", str(exc)) from exc
    head = completed.stdout.strip()
    if _FULL_SHA_RE.fullmatch(head) is None:
        raise ShelfPowerLaunchError("GIT_HEAD_INVALID", repr(head))
    return head


def _resolve_project_root(project_root: Path) -> Path:
    try:
        root = Path(project_root).resolve(strict=True)
    except OSError as exc:
        raise ShelfPowerLaunchError("PROJECT_ROOT_INVALID", str(exc)) from exc
    if not root.is_dir() or (root / ".git").is_dir() is False:
        raise ShelfPowerLaunchError("PROJECT_ROOT_INVALID", f"not a Git working tree: {root}")
    return root


def _require_output_scope(path: Path) -> Path:
    root = RESEARCH_ROOT.resolve(strict=True)
    candidate = Path(path).resolve(strict=False)
    if candidate != root and root not in candidate.parents:
        raise ShelfPowerLaunchError(
            "OUTPUT_SCOPE_INVALID",
            f"output path must remain below {root}: {candidate}",
        )
    return candidate


def _strict_json_object(payload: bytes, *, label: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ShelfPowerLaunchError("RESULT_JSON_INVALID", f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> Any:
        raise ShelfPowerLaunchError("RESULT_JSON_INVALID", f"{label}: non-finite value {value}")

    try:
        decoded = payload.decode("utf-8", errors="strict")
        value = json.loads(
            decoded,
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
        )
    except ShelfPowerLaunchError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ShelfPowerLaunchError("RESULT_JSON_INVALID", f"{label}: {exc}") from exc
    if type(value) is not dict:
        raise ShelfPowerLaunchError("RESULT_JSON_INVALID", f"{label}: root must be an object")
    return value


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ShelfPowerLaunchError("RESULT_SCHEMA_INVALID", f"{label} must be an object")
    return value


def _require_array(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ShelfPowerLaunchError("RESULT_SCHEMA_INVALID", f"{label} must be an array")
    return value


def _require_nonnegative_integer(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ShelfPowerLaunchError("RESULT_SCHEMA_INVALID", f"{label} must be a nonnegative integer")
    return value


def _require_coordinate(value: Any, label: str) -> tuple[int, int]:
    sequence = _require_array(value, label)
    if len(sequence) != 2:
        raise ShelfPowerLaunchError("RESULT_SCHEMA_INVALID", f"{label} must have length two")
    x = _require_nonnegative_integer(sequence[0], f"{label}[0]")
    y = _require_nonnegative_integer(sequence[1], f"{label}[1]")
    if x >= 70 or y >= 70:
        raise ShelfPowerLaunchError("RESULT_SCHEMA_INVALID", f"{label} is outside the 70x70 grid")
    return (x, y)


def _validate_result_schema(record: Mapping[str, Any]) -> None:
    if set(record) != _RESULT_KEYS:
        raise ShelfPowerLaunchError(
            "RESULT_SCHEMA_INVALID",
            f"top-level keys differ: missing={sorted(_RESULT_KEYS - set(record))}, "
            f"extra={sorted(set(record) - _RESULT_KEYS)}",
        )
    if record["schema_version"] != shelf_constructor.SHELF_RESULT_SCHEMA_VERSION:
        raise ShelfPowerLaunchError(
            "RESULT_SCHEMA_INVALID", f"unexpected schema version {record['schema_version']!r}"
        )
    status = record["status"]
    if type(status) is not str or status not in _RESULT_STATUSES:
        raise ShelfPowerLaunchError("RESULT_SCHEMA_INVALID", f"invalid worker status {status!r}")

    hashes = _require_mapping(record["input_sha256"], "input_sha256")
    if not hashes or any(
        type(key) is not str or type(value) is not str or _SHA256_RE.fullmatch(value) is None
        for key, value in hashes.items()
    ):
        raise ShelfPowerLaunchError("RESULT_SCHEMA_INVALID", "input_sha256 is not a hash map")

    slots = _require_array(record["manufacturing_slots"], "manufacturing_slots")
    for index, raw_slot in enumerate(slots):
        slot = _require_mapping(raw_slot, f"manufacturing_slots[{index}]")
        if set(slot) != {"template", "mode", "anchor", "operation"}:
            raise ShelfPowerLaunchError(
                "RESULT_SCHEMA_INVALID", f"manufacturing_slots[{index}] keys differ"
            )
        if any(type(slot[key]) is not str or not slot[key] for key in ("template", "mode", "operation")):
            raise ShelfPowerLaunchError(
                "RESULT_SCHEMA_INVALID", f"manufacturing_slots[{index}] strings are invalid"
            )
        _require_coordinate(slot["anchor"], f"manufacturing_slots[{index}].anchor")

    for field in ("pole_anchors", "pole_bay_anchors"):
        for index, anchor in enumerate(_require_array(record[field], field)):
            _require_coordinate(anchor, f"{field}[{index}]")

    rect = _require_array(record["protected_rect"], "protected_rect")
    if len(rect) != 4:
        raise ShelfPowerLaunchError("RESULT_SCHEMA_INVALID", "protected_rect must have length four")
    for index, value in enumerate(rect):
        _require_nonnegative_integer(value, f"protected_rect[{index}]")

    for index, edge in enumerate(_require_array(record["network_edges"], "network_edges")):
        pair = _require_array(edge, f"network_edges[{index}]")
        if len(pair) != 2:
            raise ShelfPowerLaunchError(
                "RESULT_SCHEMA_INVALID", f"network_edges[{index}] must have two endpoints"
            )
        _require_coordinate(pair[0], f"network_edges[{index}][0]")
        _require_coordinate(pair[1], f"network_edges[{index}][1]")

    _require_mapping(record["stats"], "stats")
    for field in ("route_validation", "cgroup_telemetry", "failure"):
        if record[field] is not None:
            _require_mapping(record[field], field)
    if status in {"FEASIBLE", "OPTIMAL"}:
        if record["failure"] is not None:
            raise ShelfPowerLaunchError("RESULT_SCHEMA_INVALID", "accepted status has a failure record")
        _require_mapping(record["route_validation"], "route_validation")
        _require_mapping(record["cgroup_telemetry"], "cgroup_telemetry")


def _validate_cgroup_path(value: Any, *, unit_name: str, label: str) -> str:
    if type(value) is not str or not value.startswith("/") or value.startswith("//"):
        raise ShelfPowerLaunchError("TELEMETRY_SCHEMA_INVALID", f"{label} is not canonical")
    segments = value.split("/")[1:]
    if not segments or any(segment in {"", ".", ".."} for segment in segments):
        raise ShelfPowerLaunchError("TELEMETRY_SCHEMA_INVALID", f"{label} is not canonical")
    if segments[-1] != unit_name:
        raise ShelfPowerLaunchError(
            "TELEMETRY_UNIT_MISMATCH", f"{label} does not end in {unit_name!r}"
        )
    return value


def _validate_events(value: Any, label: str) -> dict[str, int]:
    events = _require_mapping(value, label)
    if any(type(key) is not str or _EVENT_KEY_RE.fullmatch(key) is None for key in events):
        raise ShelfPowerLaunchError("TELEMETRY_SCHEMA_INVALID", f"{label} has an invalid key")
    missing = set(run_supervisor.REQUIRED_MEMORY_EVENT_KEYS) - set(events)
    if missing:
        raise ShelfPowerLaunchError(
            "TELEMETRY_SCHEMA_INVALID", f"{label} misses {sorted(missing)}"
        )
    return {
        key: _require_nonnegative_integer(value, f"{label}.{key}")
        for key, value in sorted(events.items())
    }


def _validate_limit_record(
    value: Any,
    *,
    label: str,
    leaf: bool,
    unit_name: str,
) -> str:
    record = _require_mapping(value, label)
    if set(record) != _LIMIT_KEYS:
        raise ShelfPowerLaunchError("TELEMETRY_SCHEMA_INVALID", f"{label} keys differ")
    path = record["path"]
    if leaf:
        path = _validate_cgroup_path(path, unit_name=unit_name, label=f"{label}.path")
    elif type(path) is not str or not path.startswith("/") or "//" in path:
        raise ShelfPowerLaunchError("TELEMETRY_SCHEMA_INVALID", f"{label}.path is invalid")
    expected = {
        "memory.high": run_supervisor.MEMORY_HIGH_BYTES,
        "memory.max": run_supervisor.MEMORY_MAX_BYTES,
        "memory.swap.max": run_supervisor.MEMORY_SWAP_MAX_BYTES,
    }
    for key, required in expected.items():
        observed = record[key]
        if leaf:
            if type(observed) is not int or observed != required:
                raise ShelfPowerLaunchError(
                    "TELEMETRY_CONTRACT_INVALID", f"{label}.{key}={observed!r}"
                )
        elif observed != "max" and (
            type(observed) is not int or observed < required
        ):
            raise ShelfPowerLaunchError(
                "TELEMETRY_CONTRACT_INVALID", f"{label}.{key}={observed!r}"
            )
    return path


def _validate_contract(value: Any, *, label: str, unit_name: str, cgroup_path: str) -> None:
    contract = _require_mapping(value, label)
    if set(contract) != _CONTRACT_KEYS:
        raise ShelfPowerLaunchError("TELEMETRY_SCHEMA_INVALID", f"{label} keys differ")
    leaf_path = _validate_limit_record(
        contract["leaf"], label=f"{label}.leaf", leaf=True, unit_name=unit_name
    )
    if leaf_path != cgroup_path:
        raise ShelfPowerLaunchError("TELEMETRY_CONTRACT_INVALID", f"{label} leaf path differs")
    ancestors = _require_array(contract["ancestors"], f"{label}.ancestors")
    if not ancestors:
        raise ShelfPowerLaunchError("TELEMETRY_CONTRACT_INVALID", f"{label} has no ancestors")
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
        raise ShelfPowerLaunchError("TELEMETRY_CONTRACT_INVALID", f"{label} ancestor chain is invalid")
    effective = _require_mapping(contract["effective"], f"{label}.effective")
    if set(effective) != _EFFECTIVE_KEYS:
        raise ShelfPowerLaunchError("TELEMETRY_SCHEMA_INVALID", f"{label}.effective keys differ")
    expected = {
        "memory.high": run_supervisor.MEMORY_HIGH_BYTES,
        "memory.max": run_supervisor.MEMORY_MAX_BYTES,
        "memory.swap.max": run_supervisor.MEMORY_SWAP_MAX_BYTES,
    }
    if dict(effective) != expected:
        raise ShelfPowerLaunchError(
            "TELEMETRY_CONTRACT_INVALID", f"{label}.effective differs from the launch contract"
        )


def _validate_counters(value: Any, label: str) -> tuple[dict[str, Any], dict[str, int]]:
    counters = _require_mapping(value, label)
    if set(counters) != _COUNTER_KEYS:
        raise ShelfPowerLaunchError("TELEMETRY_SCHEMA_INVALID", f"{label} keys differ")
    normalized: dict[str, Any] = {}
    for key in _COUNTER_KEYS - {"memory.events"}:
        normalized[key] = _require_nonnegative_integer(counters[key], f"{label}.{key}")
    events = _validate_events(counters["memory.events"], f"{label}.memory.events")
    normalized["memory.events"] = events
    return normalized, events


def _validate_telemetry(
    value: Any, *, unit_name: str
) -> tuple[dict[str, int], dict[str, int]]:
    telemetry = _require_mapping(value, "cgroup_telemetry")
    if set(telemetry) != _TELEMETRY_KEYS:
        raise ShelfPowerLaunchError("TELEMETRY_SCHEMA_INVALID", "cgroup_telemetry keys differ")
    if telemetry["schema_version"] != "routing_aware_witness_cgroup_telemetry.v1":
        raise ShelfPowerLaunchError(
            "TELEMETRY_SCHEMA_INVALID", f"unexpected telemetry schema {telemetry['schema_version']!r}"
        )
    if telemetry["expected_unit_name"] != unit_name:
        raise ShelfPowerLaunchError(
            "TELEMETRY_UNIT_MISMATCH", repr(telemetry["expected_unit_name"])
        )
    cgroup_path = _validate_cgroup_path(
        telemetry["cgroup_path"], unit_name=unit_name, label="cgroup_telemetry.cgroup_path"
    )
    _validate_contract(
        telemetry["contract_start"],
        label="cgroup_telemetry.contract_start",
        unit_name=unit_name,
        cgroup_path=cgroup_path,
    )
    _validate_contract(
        telemetry["contract_end"],
        label="cgroup_telemetry.contract_end",
        unit_name=unit_name,
        cgroup_path=cgroup_path,
    )
    counters_start, events_start = _validate_counters(
        telemetry["counters_start"], "cgroup_telemetry.counters_start"
    )
    counters_end, events_end = _validate_counters(
        telemetry["counters_end"], "cgroup_telemetry.counters_end"
    )
    for peak in ("memory.peak", "memory.swap.peak"):
        if counters_end[peak] < counters_start[peak]:
            raise ShelfPowerLaunchError("TELEMETRY_COUNTER_INVALID", f"{peak} decreased")
    delta = run_supervisor.memory_events_delta(events_start, events_end)
    observed_delta = _validate_events(
        telemetry["memory.events.delta"], "cgroup_telemetry.memory.events.delta"
    )
    if observed_delta != delta:
        raise ShelfPowerLaunchError("TELEMETRY_DELTA_INVALID", "memory.events.delta differs")
    expected_oom = "NO_CGROUP_OOM"
    if delta.get("oom_kill", 0) > 0 or delta.get("oom_group_kill", 0) > 0:
        expected_oom = run_supervisor.CGROUP_OOM_KILL
    elif delta.get("oom", 0) > 0:
        expected_oom = run_supervisor.CGROUP_OOM_EVENT
    if telemetry["oom_attribution"] != expected_oom:
        raise ShelfPowerLaunchError(
            "TELEMETRY_OOM_ATTRIBUTION_INVALID",
            f"expected {expected_oom}, observed {telemetry['oom_attribution']!r}",
        )
    return events_start, events_end


def _current_input_hashes(project_root: Path) -> dict[str, str]:
    bundle = strict_contract.load_input_bundle(project_root)
    strict_contract.reconcile_inputs(bundle)
    return dict(bundle.hashes)


def _inspect_result(
    result_path: Path,
    *,
    project_root: Path,
    unit_name: str,
    expected_worker_sha256: str,
) -> ResultInspection:
    if not result_path.exists():
        return ResultInspection(False, False, False, False, None, None, None, None, None, ("result missing",))
    if result_path.is_symlink() or not result_path.is_file():
        return ResultInspection(True, False, False, False, None, None, None, None, None, ("result is not a regular non-symlink file",))
    try:
        snapshot = run_supervisor._read_stable_snapshot(result_path)
    except run_supervisor.SupervisorError as exc:
        return ResultInspection(True, False, False, False, None, None, None, None, None, (str(exc),))
    try:
        record = _strict_json_object(snapshot.payload, label="worker result")
    except ShelfPowerLaunchError as exc:
        return ResultInspection(
            True, False, False, False, None, None, None, snapshot.sha256, snapshot.size_bytes, (str(exc),)
        )

    errors: list[str] = []
    status = record.get("status") if type(record.get("status")) is str else None
    schema_valid = True
    try:
        _validate_result_schema(record)
    except ShelfPowerLaunchError as exc:
        schema_valid = False
        errors.append(str(exc))

    before: Mapping[str, int] | None = None
    after: Mapping[str, int] | None = None
    telemetry_valid = True
    try:
        before, after = _validate_telemetry(record.get("cgroup_telemetry"), unit_name=unit_name)
    except (ShelfPowerLaunchError, run_supervisor.SupervisorError) as exc:
        telemetry_valid = False
        errors.append(str(exc))

    integrity_valid = schema_valid and telemetry_valid
    if integrity_valid:
        try:
            if dict(record["input_sha256"]) != _current_input_hashes(project_root):
                raise ShelfPowerLaunchError(
                    "RESULT_INPUT_DRIFT", "worker hashes differ from current pinned inputs"
                )
            if run_supervisor.sha256_file(WORKER_PATH) != expected_worker_sha256:
                raise ShelfPowerLaunchError("WORKER_DRIFT", "worker changed during the attempt")
            if _repository_head(project_root) != EXPECTED_BASELINE_HEAD:
                raise ShelfPowerLaunchError("GIT_HEAD_DRIFT", "repository HEAD changed during the attempt")
            if status in {"FEASIBLE", "OPTIMAL"}:
                shelf_constructor._load_shelf_result(result_path, project_root=project_root)
                replay_snapshot = run_supervisor._read_stable_snapshot(result_path)
                if (
                    replay_snapshot.sha256 != snapshot.sha256
                    or replay_snapshot.size_bytes != snapshot.size_bytes
                ):
                    raise ShelfPowerLaunchError(
                        "RESULT_DRIFT", "worker result changed during strict replay"
                    )
        except (
            ShelfPowerLaunchError,
            run_supervisor.SupervisorError,
            shelf_constructor.ShelfConstructionError,
            strict_contract.InputContractError,
        ) as exc:
            integrity_valid = False
            errors.append(str(exc))

    return ResultInspection(
        True,
        True,
        schema_valid,
        integrity_valid,
        status,
        before,
        after,
        snapshot.sha256,
        snapshot.size_bytes,
        tuple(errors),
    )


def _ensure_wait_pipe(command: Sequence[str]) -> tuple[str, ...]:
    """Bridge old/new helper revisions without duplicating lifecycle flags."""

    normalized = list(command)
    if not normalized or normalized[0] != "systemd-run":
        raise ShelfPowerLaunchError("COMMAND_INVALID", "not a systemd-run command")
    insertion = normalized.index("--user") + 1 if "--user" in normalized else 1
    for flag in ("--pipe", "--wait"):
        count = normalized.count(flag)
        if count > 1:
            raise ShelfPowerLaunchError("COMMAND_INVALID", f"duplicate {flag}")
        if count == 0:
            normalized.insert(insertion, flag)
            insertion += 1
    return tuple(normalized)


def _validate_launch_command(
    command: Sequence[str],
    *,
    unit_name: str,
    project_root: Path,
    worker_command: Sequence[str],
) -> None:
    required_flags = {
        "--user",
        "--wait",
        "--pipe",
        "--collect",
        "--service-type=exec",
        "--expand-environment=no",
        f"--unit={unit_name}",
        f"--working-directory={project_root}",
        *(f"--property={value}" for value in run_supervisor.CGROUP_PROPERTIES),
    }
    if command[0] != "systemd-run" or any(command.count(flag) != 1 for flag in required_flags):
        raise ShelfPowerLaunchError("COMMAND_INVALID", "systemd-run lifecycle contract differs")
    worker_start = len(command) - len(worker_command)
    if tuple(command[worker_start:]) != tuple(worker_command):
        raise ShelfPowerLaunchError("COMMAND_INVALID", "worker argv is not the command suffix")
    unexpected_properties = [item for item in command if item.startswith("--property=") and item not in required_flags]
    if unexpected_properties:
        raise ShelfPowerLaunchError(
            "COMMAND_INVALID", f"unexpected unit properties: {unexpected_properties}"
        )


def _worker_command(
    *,
    project_root: Path,
    result_path: Path,
    unit_name: str,
    time_limit_seconds: float,
    workers: int,
) -> tuple[str, ...]:
    if type(workers) is not int or workers < 1:
        raise ShelfPowerLaunchError("WORKERS_INVALID", repr(workers))
    if isinstance(time_limit_seconds, bool) or not isinstance(time_limit_seconds, (int, float)) or time_limit_seconds <= 0:
        raise ShelfPowerLaunchError("TIME_LIMIT_INVALID", repr(time_limit_seconds))
    interpreter = Path(sys.executable).resolve(strict=True)
    return (
        str(interpreter),
        "-m",
        f"{_MODULE_PREFIX}.solve_shelf_power",
        "--project-root",
        str(project_root),
        "--time-limit-seconds",
        str(float(time_limit_seconds)),
        "--workers",
        str(workers),
        "--out",
        str(result_path),
        "--expected-unit",
        unit_name,
    )


def _launch_command(
    *, project_root: Path, unit_name: str, worker_command: Sequence[str]
) -> tuple[str, ...]:
    built = run_supervisor.build_systemd_run_command(
        unit_name=unit_name,
        working_directory=project_root,
        command=worker_command,
    )
    command = _ensure_wait_pipe(built)
    _validate_launch_command(
        command,
        unit_name=unit_name,
        project_root=project_root,
        worker_command=worker_command,
    )
    return command


def launch_shelf_power(
    *,
    project_root: Path = PROJECT_ROOT,
    run_root: Path = DEFAULT_RUN_ROOT,
    time_limit_seconds: float = 600.0,
    workers: int = 8,
    dry_run: bool = False,
    now: datetime | None = None,
    lock_path: Path | None = None,
    unit_query: Callable[[], tuple[str, ...]] = run_supervisor.query_active_related_units,
    process_query: Callable[..., tuple[dict[str, Any], ...]] = run_supervisor.detect_active_related_processes,
    systemd_runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> LaunchOutcome:
    """Run or render exactly one shelf/power attempt under the global mutex."""

    root = _resolve_project_root(project_root)
    output_root = _require_output_scope(run_root)
    timestamp = _normalize_now(now)
    with run_supervisor.acquire_prod_scale_lock(lock_path):
        head = _repository_head(root)
        if head != EXPECTED_BASELINE_HEAD:
            raise ShelfPowerLaunchError(
                "BASELINE_HEAD_MISMATCH",
                f"expected {EXPECTED_BASELINE_HEAD}, observed {head}",
            )
        worker_record = run_supervisor.file_record(WORKER_PATH, relative_to=root)
        active_units = unit_query()
        active_processes = process_query()
        if active_units or active_processes:
            raise run_supervisor.BusyError(
                f"related prod-scale work is active: units={active_units!r}, processes={active_processes!r}"
            )

        run_dir = run_supervisor.create_run_directory(
            output_root, EXPECTED_BASELINE_HEAD[:7], now=timestamp
        )
        attempt_dir = run_supervisor.create_attempt_directory(run_dir, 1)
        unit_name = f"{UNIT_PREFIX}{_utc_stamp(timestamp)}.service"
        if _SAFE_UNIT_RE.fullmatch(unit_name) is None:
            raise ShelfPowerLaunchError("UNIT_NAME_INVALID", unit_name)
        result_path = attempt_dir / "shelf_power_result.json"
        worker_argv = _worker_command(
            project_root=root,
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
            "worker": worker_record.as_dict(),
            "result_path": str(result_path),
            "time_limit_seconds": float(time_limit_seconds),
            "external_timeout_seconds": None,
            "wait_contract": "worker_internal_time_limit_then_systemd_wait",
            "workers": workers,
            "lock_path": str(
                run_supervisor.prod_scale_lock_path() if lock_path is None else Path(lock_path)
            ),
        }
        run_supervisor.write_json_exclusive(attempt_dir / "header.json", header)
        run_supervisor.write_json_exclusive(
            attempt_dir / "command.json",
            {
                "argv": list(command),
                "shell_display": shlex.join(command),
            },
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
                        "detail": "command recorded; worker not started",
                        "memory_events_delta": None,
                    },
                    "result_expected_but_not_created": str(result_path),
                },
            )
            return LaunchOutcome(
                run_dir,
                attempt_dir,
                unit_name,
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
            stdout = completed.stdout if isinstance(completed.stdout, bytes) else str(completed.stdout or "").encode()
            stderr = completed.stderr if isinstance(completed.stderr, bytes) else str(completed.stderr or "").encode()
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            launch_error = str(exc)
            stdout = exc.stdout if isinstance(exc.stdout, bytes) else str(exc.stdout or "").encode()
            stderr = exc.stderr if isinstance(exc.stderr, bytes) else str(exc.stderr or "").encode()
        except OSError as exc:
            launch_error = str(exc)
            stderr = (str(exc) + "\n").encode("utf-8", errors="replace")

        run_supervisor.write_bytes_exclusive(attempt_dir / "stdout.log", stdout)
        run_supervisor.write_bytes_exclusive(attempt_dir / "stderr.log", stderr)
        inspection = _inspect_result(
            result_path,
            project_root=root,
            unit_name=unit_name,
            expected_worker_sha256=worker_record.sha256,
        )
        evidence = run_supervisor.AttemptEvidence(
            timed_out=timed_out,
            returncode=returncode,
            solver_status=inspection.solver_status,
            result_present=inspection.present,
            result_parse_valid=inspection.parse_valid,
            schema_valid=inspection.schema_valid,
            integrity_valid=inspection.integrity_valid,
            memory_events_before=inspection.memory_events_before,
            memory_events_after=inspection.memory_events_after,
        )
        classification = run_supervisor.classify_attempt(evidence)
        geometry_ready = (
            classification.successful
            and inspection.solver_status in {"FEASIBLE", "OPTIMAL"}
        )
        run_supervisor.write_json_exclusive(
            classification_path,
            {
                "schema_version": CLASSIFICATION_SCHEMA_VERSION,
                "dry_run": False,
                "classification": classification.as_dict(),
                "geometry_ready": geometry_ready,
                "launch_error": launch_error,
                "evidence": asdict(evidence),
                "result": inspection.as_dict(),
                "post_head": _repository_head(root),
            },
        )
        return LaunchOutcome(
            run_dir,
            attempt_dir,
            unit_name,
            result_path,
            classification_path,
            classification.code,
            classification.successful,
            geometry_ready,
            False,
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--time-limit-seconds", type=float, default=600.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        outcome = launch_shelf_power(
            project_root=args.project_root,
            run_root=args.run_root,
            time_limit_seconds=args.time_limit_seconds,
            workers=args.workers,
            dry_run=args.dry_run,
        )
        print(json.dumps(outcome.as_dict(), ensure_ascii=False, sort_keys=True))
        return 0 if outcome.dry_run or outcome.geometry_ready else 1
    except (ShelfPowerLaunchError, run_supervisor.SupervisorError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
