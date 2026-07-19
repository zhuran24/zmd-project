#!/usr/bin/env python3
"""Supervise the Round-4/5 compact coordinate-master revalidation campaign.

This module deliberately keeps OR-Tools and the compact-model implementation
out of the long-lived supervisor.  Only the ``worker`` subcommand imports the
model/oracle modules.  Every solver arm therefore runs in a fresh Python child,
inside a transient systemd user service created by ``launch-next``.

The campaign is research-only.  It reads and hashes the live project inputs but
never writes production, frozen, or sealed surfaces.  All mutable output lives
below the caller-selected campaign directory.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import inspect
import json
import os
import platform
import re
import resource
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "round45_bespoke_coordinate_campaign.v1"
WORKER_SCHEMA_VERSION = "round45_bespoke_coordinate_worker.v1"
TERMINAL_SCHEMA_VERSION = "round45_bespoke_coordinate_terminal.v1"
SUMMARY_SCHEMA_VERSION = "round45_bespoke_coordinate_summary.v1"
SEMANTIC_LABEL = "identity_front_newpool_f05b1291_physical_protocol_ports"
PROFILE_NAME = "strict_lean"

SCRIPT_PATH = Path(__file__).resolve()
RESEARCH_DIR = SCRIPT_PATH.parent
DEFAULT_PROJECT_ROOT = SCRIPT_PATH.parents[4]

MEMORY_HIGH = "34G"
MEMORY_MAX = "38G"
MEMORY_SWAP_MAX = "16G"
MEMORY_HIGH_BYTES = 34 * 1024**3
MEMORY_MAX_BYTES = 38 * 1024**3
MEMORY_SWAP_MAX_BYTES = 16 * 1024**3

SOLVE_GATE_MAX_VARIABLES = 500_000
SOLVE_GATE_MAX_BUILD_RSS_KIB = 8 * 1024 * 1024
HARD_TOMBSTONE_MAX_VARIABLES = 1_000_000
HARD_TOMBSTONE_MAX_CONSTRAINTS = 2_000_000
HARD_TOMBSTONE_MAX_BUILD_RSS_KIB = 10 * 1024 * 1024

EXIT_OK = 0
EXIT_CLI = 2
EXIT_ACTIVE = 11
EXIT_BUSY = 75
EXIT_CONFIG = 78
EXIT_WORKER = 70

ARM_MATRIX: tuple[dict[str, Any], ...] = (
    {"ordinal": 1, "run_key": "g7x7-t600-s71", "ghost_w": 7, "ghost_h": 7, "time_limit_seconds": 600.0, "seed": 71},
    {"ordinal": 2, "run_key": "g6x8-t600-s72", "ghost_w": 6, "ghost_h": 8, "time_limit_seconds": 600.0, "seed": 72},
    {"ordinal": 3, "run_key": "g8x6-t600-s73", "ghost_w": 8, "ghost_h": 6, "time_limit_seconds": 600.0, "seed": 73},
    {"ordinal": 4, "run_key": "g7x7-t1200-s71", "ghost_w": 7, "ghost_h": 7, "time_limit_seconds": 1200.0, "seed": 71},
    {"ordinal": 5, "run_key": "g6x8-t1200-s72", "ghost_w": 6, "ghost_h": 8, "time_limit_seconds": 1200.0, "seed": 72},
    {"ordinal": 6, "run_key": "g8x6-t1200-s73", "ghost_w": 8, "ghost_h": 6, "time_limit_seconds": 1200.0, "seed": 73},
)

PREPARE_ANCHORS: tuple[dict[str, int | str], ...] = (
    {"anchor_key": "g7x7-s71", "ghost_w": 7, "ghost_h": 7, "seed": 71},
    {"anchor_key": "g6x8-s72", "ghost_w": 6, "ghost_h": 8, "seed": 72},
    {"anchor_key": "g8x6-s73", "ghost_w": 8, "ghost_h": 6, "seed": 73},
)

INPUT_CLOSURE_PATHS: tuple[str, ...] = (
    "data/preprocessed/candidate_placements.json",
    "data/preprocessed/mandatory_exact_instances.json",
    "data/preprocessed/generic_io_requirements.json",
    "rules/canonical_rules.json",
    "rules/preprocess_plan.json",
)

SOURCE_CLOSURE_PATHS: tuple[str, ...] = (
    "src/preprocess/operation_profiles.py",
    "src/models/exact_coordinate_master.py",
    "src/models/binding_subproblem.py",
    "src/models/master_model.py",
    "src/models/port_binding.py",
    "src/models/routing_binding_context.py",
    "docs/research/front_offset_incident_20260718/round45_bespoke_coordinate_master/compact_model.py",
    "docs/research/front_offset_incident_20260718/round45_bespoke_coordinate_master/independent_oracle.py",
    "docs/research/front_offset_incident_20260718/round45_bespoke_coordinate_master/run_campaign.py",
)

_SAFE_UNIT_RE = re.compile(
    r"^zmd-r45-[0-9a-f]{8}-g(?:7x7|6x8|8x6)-t(?:600|1200)-s(?:71|72|73)-a[0-9]{2}\.service$"
)
_CLEAN_TERMINALS = frozenset(
    {"CLEAN_FEASIBLE", "CLEAN_INFEASIBLE", "CLEAN_UNKNOWN"}
)
_KNOWN_SOLVER_SCRIPTS = frozenset(
    {
        "main.py",
        "run_reconstructed_prod_ab.py",
        "run_reconstructed_witness.py",
        "witness_cpsat_v1.py",
    }
)


class CampaignError(RuntimeError):
    """Raised when a campaign invariant is not satisfied."""


def _utc_now() -> str:
    import datetime as _datetime

    return _datetime.datetime.now(_datetime.timezone.utc).isoformat()


def _canonical_bytes(payload: Any) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _duplicate_rejecting_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CampaignError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_duplicate_rejecting_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CampaignError(f"non-finite JSON constant: {value}")
            ),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CampaignError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CampaignError(f"JSON root must be an object: {path}")
    return payload


def _write_complete_temp(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temp = tempfile.mkstemp(
        prefix=f".{path.name}.tmp.", dir=str(path.parent)
    )
    temp_path = Path(raw_temp)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_canonical_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path


def _write_json_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    temp_path = _write_complete_temp(path, payload)
    try:
        os.link(temp_path, path)
    except FileExistsError as exc:
        raise CampaignError(f"refusing to overwrite existing artifact: {path}") from exc
    finally:
        temp_path.unlink(missing_ok=True)


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    temp_path = _write_complete_temp(path, payload)
    try:
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _write_text_exclusive(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temp = tempfile.mkstemp(
        prefix=f".{path.name}.tmp.", dir=str(path.parent)
    )
    temp_path = Path(raw_temp)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(text.encode(encoding))
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_path, path)
        except FileExistsError as exc:
            raise CampaignError(f"refusing to overwrite existing artifact: {path}") from exc
    finally:
        temp_path.unlink(missing_ok=True)


def _jsonable(value: Any, *, depth: int = 0) -> Any:
    if depth > 8:
        return repr(value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text in {"model", "cp_model", "solver"}:
                continue
            out[key_text] = _jsonable(item, depth=depth + 1)
        return out
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item, depth=depth + 1) for item in value]
    if hasattr(value, "__dict__"):
        return _jsonable(vars(value), depth=depth + 1)
    return repr(value)


def _file_record(path: Path, project_root: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    try:
        display = resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        display = str(resolved)
    stat = resolved.stat()
    return {
        "path": display,
        "sha256": _sha256_file(resolved),
        "size_bytes": int(stat.st_size),
    }


def _closure_records(project_root: Path) -> dict[str, Any]:
    project_root = project_root.resolve(strict=True)
    inputs = {
        relative: _file_record(project_root / relative, project_root)
        for relative in INPUT_CLOSURE_PATHS
    }
    sources = {
        relative: _file_record(project_root / relative, project_root)
        for relative in SOURCE_CLOSURE_PATHS
    }
    payload = {"inputs": inputs, "sources": sources}
    payload["closure_sha256"] = _sha256_bytes(_canonical_bytes(payload))
    return payload


def _git_snapshot(project_root: Path) -> dict[str, Any]:
    def run(*args: str, binary: bool = False) -> str | bytes:
        completed = subprocess.run(
            ["git", *args],
            cwd=project_root,
            env={**os.environ, "LC_ALL": "C"},
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return completed.stdout if binary else completed.stdout.decode("utf-8").rstrip("\n")

    status = str(run("status", "--porcelain=v1", "--untracked-files=normal"))
    tracked_diff = run("diff", "--binary", "--no-ext-diff", "HEAD", "--", binary=True)
    assert isinstance(tracked_diff, bytes)
    return {
        "head": str(run("rev-parse", "HEAD")),
        "branch": str(run("branch", "--show-current")),
        "dirty": bool(status),
        "status_porcelain_v1": status.splitlines(),
        "tracked_diff_sha256": _sha256_bytes(tracked_diff),
    }


def _spec_base(spec: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(spec)
    result.pop("campaign_id", None)
    result.pop("campaign_spec_sha256", None)
    result.pop("created_at_utc", None)
    return result


def _seal_spec(base: Mapping[str, Any]) -> dict[str, Any]:
    digest = _sha256_bytes(_canonical_bytes(_spec_base(base)))
    return {
        **dict(base),
        "campaign_id": f"r45-{digest[:16]}",
        "campaign_spec_sha256": digest,
    }


def _expected_solver_parameters(*, seed: int, time_limit_seconds: float) -> dict[str, Any]:
    return {
        "cp_model_probing_level": 0,
        "linearization_level": 0,
        "log_search_progress": True,
        "log_to_stdout": False,
        "max_memory_in_mb": 10_000,
        "max_presolve_iterations": 1,
        "max_time_in_seconds": float(time_limit_seconds),
        "merge_no_overlap_work_limit": 0.0,
        "num_search_workers": 1,
        "probing_deterministic_time_limit": 0.05,
        "random_seed": int(seed),
    }


def _expected_solver_contract() -> dict[str, Any]:
    return {
        "profile": PROFILE_NAME,
        "workers": 1,
        "pythonhashseed": "0",
        "parameters_by_run_key": {
            str(arm["run_key"]): _expected_solver_parameters(
                seed=int(arm["seed"]),
                time_limit_seconds=float(arm["time_limit_seconds"]),
            )
            for arm in ARM_MATRIX
        },
    }


def _expected_cgroup_contract() -> dict[str, Any]:
    return {
        "memory_high": MEMORY_HIGH,
        "memory_high_bytes": MEMORY_HIGH_BYTES,
        "memory_max": MEMORY_MAX,
        "memory_max_bytes": MEMORY_MAX_BYTES,
        "memory_swap_max": MEMORY_SWAP_MAX,
        "memory_swap_max_bytes": MEMORY_SWAP_MAX_BYTES,
        "oom_policy": "continue",
        "mode": "unified_cgroup_v2",
    }


def _validate_closure_record(closure: Any) -> None:
    if not isinstance(closure, Mapping):
        raise CampaignError("campaign closure must be an object")
    inputs = closure.get("inputs")
    sources = closure.get("sources")
    if not isinstance(inputs, Mapping) or set(inputs) != set(INPUT_CLOSURE_PATHS):
        raise CampaignError("campaign input closure path set is invalid")
    if not isinstance(sources, Mapping) or set(sources) != set(SOURCE_CLOSURE_PATHS):
        raise CampaignError("campaign source closure path set is invalid")
    for expected_paths, records, label in (
        (INPUT_CLOSURE_PATHS, inputs, "input"),
        (SOURCE_CLOSURE_PATHS, sources, "source"),
    ):
        for relative in expected_paths:
            raw = records.get(relative)
            if not isinstance(raw, Mapping):
                raise CampaignError(f"campaign {label} closure record is invalid: {relative}")
            if raw.get("path") != relative:
                raise CampaignError(f"campaign {label} closure path disagrees: {relative}")
            digest = raw.get("sha256")
            size = raw.get("size_bytes")
            if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                raise CampaignError(f"campaign {label} closure SHA is invalid: {relative}")
            if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                raise CampaignError(f"campaign {label} closure size is invalid: {relative}")
    expected_digest = closure.get("closure_sha256")
    closure_base = {"inputs": dict(inputs), "sources": dict(sources)}
    observed_digest = _sha256_bytes(_canonical_bytes(closure_base))
    if expected_digest != observed_digest:
        raise CampaignError("campaign closure digest is invalid")


def _validate_spec_contract(spec: Mapping[str, Any]) -> None:
    expected_digest = str(spec.get("campaign_spec_sha256", ""))
    if spec.get("campaign_id") != f"r45-{expected_digest[:16]}":
        raise CampaignError("campaign id is not derived from the sealed spec digest")
    if spec.get("semantic_label") != SEMANTIC_LABEL:
        raise CampaignError("campaign semantic label mismatch")
    if spec.get("profile") != PROFILE_NAME or spec.get("workers") != 1:
        raise CampaignError("campaign solver profile/worker contract mismatch")
    if spec.get("pythonhashseed") != 0:
        raise CampaignError("campaign PYTHONHASHSEED contract mismatch")
    if spec.get("arms") != [dict(item) for item in ARM_MATRIX]:
        raise CampaignError("campaign arm matrix mismatch")
    if spec.get("solver_contract") != _expected_solver_contract():
        raise CampaignError("campaign solver parameter contract mismatch")
    if spec.get("cgroup_contract") != _expected_cgroup_contract():
        raise CampaignError("campaign cgroup contract mismatch")
    _validate_closure_record(spec.get("closure"))
    launcher_environment = spec.get("launcher_environment")
    expected_launcher_environment = {
        "python_executable": _python_executable(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }
    if launcher_environment != expected_launcher_environment:
        raise CampaignError("campaign launcher runtime environment mismatch")

    prepare_builds = spec.get("prepare_builds")
    expected_prepare_keys = {
        str(anchor["anchor_key"])
        for anchor in PREPARE_ANCHORS
    }
    if not isinstance(prepare_builds, Mapping) or set(prepare_builds) != expected_prepare_keys:
        raise CampaignError("campaign prepare-build anchor set mismatch")
    for anchor in PREPARE_ANCHORS:
        key = str(anchor["anchor_key"])
        build = prepare_builds.get(key)
        if not isinstance(build, Mapping):
            raise CampaignError(f"campaign prepare build is invalid: {key}")
        if (
            build.get("ghost_w") != int(anchor["ghost_w"])
            or build.get("ghost_h") != int(anchor["ghost_h"])
            or build.get("seed") != int(anchor["seed"])
        ):
            raise CampaignError(f"campaign prepare build identity mismatch: {key}")
        proto_sha = build.get("proto_sha256")
        if not isinstance(proto_sha, str) or re.fullmatch(r"[0-9a-f]{64}", proto_sha) is None:
            raise CampaignError(f"campaign prepare Proto SHA is invalid: {key}")
        for field in ("proto_size_bytes", "variable_count", "constraint_count"):
            value = build.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise CampaignError(f"campaign prepare {field} is invalid: {key}")
        if not isinstance(build.get("proto_serialization_path"), str):
            raise CampaignError(f"campaign prepare Proto serialization path is invalid: {key}")
        if not _verdict_passed(build.get("oracle")):
            raise CampaignError(f"campaign prepare oracle did not pass: {key}")
        for gate in ("hard_tombstone", "solve_gate"):
            raw_gate = build.get(gate)
            if not isinstance(raw_gate, Mapping) or raw_gate.get("passed") is not True:
                raise CampaignError(f"campaign prepare {gate} did not pass: {key}")
        environment = build.get("worker_environment")
        expected_environment_fields = {
            "python_executable": expected_launcher_environment["python_executable"],
            "python_version": expected_launcher_environment["python_version"],
            "pythonhashseed": "0",
            "profile": PROFILE_NAME,
            "workers": 1,
            "seed": int(anchor["seed"]),
        }
        if not isinstance(environment, Mapping) or any(
            environment.get(field) != value
            for field, value in expected_environment_fields.items()
        ):
            raise CampaignError(f"campaign prepare runtime environment mismatch: {key}")
        if not isinstance(environment.get("ortools_version"), str) or not environment.get("ortools_version"):
            raise CampaignError(f"campaign prepare OR-Tools version is invalid: {key}")


def _load_spec(campaign_root: Path, *, verify_context: bool = True) -> dict[str, Any]:
    spec_path = campaign_root / "campaign_spec.json"
    spec = _read_json(spec_path)
    if spec.get("schema_version") != SCHEMA_VERSION:
        raise CampaignError("campaign schema mismatch")
    expected = str(spec.get("campaign_spec_sha256", ""))
    observed = _sha256_bytes(_canonical_bytes(_spec_base(spec)))
    if expected != observed:
        raise CampaignError(
            f"campaign spec digest mismatch: expected {expected}, observed {observed}"
        )
    _validate_spec_contract(spec)
    digest_path = campaign_root / "campaign_spec.sha256"
    if digest_path.read_text(encoding="ascii").strip() != expected:
        raise CampaignError("campaign_spec.sha256 disagrees with campaign_spec.json")
    if verify_context:
        project_root = Path(str(spec["project_root"])).resolve(strict=True)
        current = _closure_records(project_root)
        if current != spec.get("closure"):
            raise CampaignError("campaign context drift: current input/source closure differs")
    return spec


def _arm_map(spec: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    arms = spec.get("arms")
    if not isinstance(arms, list):
        raise CampaignError("campaign arms must be a list")
    result: dict[str, dict[str, Any]] = {}
    for raw in arms:
        if not isinstance(raw, dict) or not isinstance(raw.get("run_key"), str):
            raise CampaignError("malformed campaign arm")
        run_key = str(raw["run_key"])
        if run_key in result:
            raise CampaignError(f"duplicate campaign run_key: {run_key}")
        result[run_key] = dict(raw)
    return result


def _prepare_key(ghost_w: int, ghost_h: int, seed: int) -> str:
    return f"g{ghost_w}x{ghost_h}-s{seed}"


def _safe_child_env(*, seed: int) -> dict[str, str]:
    inherited_names = {
        "LANG",
        "LANGUAGE",
        "LC_ALL",
        "PATH",
        "TMPDIR",
        "TZ",
        "XDG_RUNTIME_DIR",
    }
    env = {
        key: value
        for key, value in os.environ.items()
        if key in inherited_names or key.startswith("LC_")
    }
    env.setdefault("PATH", os.defpath)
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "R45_RANDOM_SEED": str(seed),
            "R45_WORKERS": "1",
            "R45_PROFILE": PROFILE_NAME,
        }
    )
    return dict(sorted(env.items()))


def _python_executable() -> str:
    return str(Path(sys.executable).absolute())


def _worker_argv(
    *,
    project_root: Path,
    output: Path,
    operation: str,
    ghost_w: int,
    ghost_h: int,
    seed: int,
    time_limit_seconds: float = 0.0,
    expected_proto_sha256: str | None = None,
    expected_variable_count: int | None = None,
    expected_constraint_count: int | None = None,
    expected_campaign_id: str | None = None,
    expected_campaign_spec_sha256: str | None = None,
    expected_closure_sha256: str | None = None,
    expected_run_key: str | None = None,
    expected_run_spec_sha256: str | None = None,
) -> list[str]:
    argv = [
        _python_executable(),
        str(SCRIPT_PATH),
        "worker",
        operation,
        "--project-root",
        str(project_root.resolve()),
        "--output",
        str(output.resolve()),
        "--ghost-w",
        str(ghost_w),
        "--ghost-h",
        str(ghost_h),
        "--seed",
        str(seed),
        "--time-limit-seconds",
        str(float(time_limit_seconds)),
    ]
    if expected_proto_sha256 is not None:
        argv.extend(["--expected-proto-sha256", expected_proto_sha256])
    if expected_variable_count is not None:
        argv.extend(["--expected-variable-count", str(expected_variable_count)])
    if expected_constraint_count is not None:
        argv.extend(["--expected-constraint-count", str(expected_constraint_count)])
    for option, value in (
        ("--expected-campaign-id", expected_campaign_id),
        ("--expected-campaign-spec-sha256", expected_campaign_spec_sha256),
        ("--expected-closure-sha256", expected_closure_sha256),
        ("--expected-run-key", expected_run_key),
        ("--expected-run-spec-sha256", expected_run_spec_sha256),
    ):
        if value is not None:
            argv.extend([option, value])
    return argv


def _validate_prepare_payload(
    payload: Mapping[str, Any], *, anchor: Mapping[str, Any]
) -> None:
    anchor_key = str(anchor["anchor_key"])
    expected_ghost = {"w": int(anchor["ghost_w"]), "h": int(anchor["ghost_h"])}
    if payload.get("schema_version") != WORKER_SCHEMA_VERSION:
        raise CampaignError(f"prepare worker {anchor_key} schema mismatch")
    if payload.get("operation") != "prepare-anchor" or payload.get("worker_status") != "BUILD_READY":
        raise CampaignError(f"prepare worker {anchor_key} did not return BUILD_READY")
    if payload.get("ghost") != expected_ghost:
        raise CampaignError(f"prepare worker {anchor_key} ghost identity mismatch")
    if (
        payload.get("seed") != int(anchor["seed"])
        or payload.get("workers") != 1
        or payload.get("profile") != PROFILE_NAME
    ):
        raise CampaignError(f"prepare worker {anchor_key} execution identity mismatch")

    environment = payload.get("environment")
    if not isinstance(environment, Mapping):
        raise CampaignError(f"prepare worker {anchor_key} environment is missing")
    required_environment = {
        "python_executable": _python_executable(),
        "python_version": platform.python_version(),
        "pythonhashseed": "0",
        "profile": PROFILE_NAME,
        "workers": 1,
        "seed": int(anchor["seed"]),
    }
    if any(environment.get(key) != value for key, value in required_environment.items()):
        raise CampaignError(f"prepare worker {anchor_key} environment mismatch")
    ortools_version = environment.get("ortools_version")
    if not isinstance(ortools_version, str) or not ortools_version:
        raise CampaignError(f"prepare worker {anchor_key} OR-Tools version is missing")

    model = payload.get("model")
    if not isinstance(model, Mapping):
        raise CampaignError(f"prepare worker {anchor_key} model record is missing")
    proto_sha = model.get("proto_sha256")
    if not isinstance(proto_sha, str) or re.fullmatch(r"[0-9a-f]{64}", proto_sha) is None:
        raise CampaignError(f"prepare worker {anchor_key} Proto SHA is invalid")
    for field in ("proto_size_bytes", "variable_count", "constraint_count"):
        value = model.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise CampaignError(f"prepare worker {anchor_key} {field} is invalid")
    if model.get("validate_error") != "":
        raise CampaignError(f"prepare worker {anchor_key} model validation failed")
    if not _verdict_passed(payload.get("oracle")):
        raise CampaignError(f"prepare worker {anchor_key} oracle did not pass")
    for gate in ("hard_tombstone", "solve_gate"):
        raw_gate = payload.get(gate)
        if not isinstance(raw_gate, Mapping) or raw_gate.get("passed") is not True:
            raise CampaignError(f"prepare worker {anchor_key} failed {gate}")


def _run_prepare_worker(
    *, project_root: Path, prepare_dir: Path, anchor: Mapping[str, Any]
) -> dict[str, Any]:
    anchor_key = str(anchor["anchor_key"])
    anchor_dir = prepare_dir / anchor_key
    anchor_dir.mkdir(parents=False, exist_ok=False)
    output = anchor_dir / "build.json"
    stdout_path = anchor_dir / "stdout.txt"
    stderr_path = anchor_dir / "stderr.txt"
    argv = _worker_argv(
        project_root=project_root,
        output=output,
        operation="prepare-anchor",
        ghost_w=int(anchor["ghost_w"]),
        ghost_h=int(anchor["ghost_h"]),
        seed=int(anchor["seed"]),
    )
    with stdout_path.open("xb") as stdout_handle, stderr_path.open("xb") as stderr_handle:
        completed = subprocess.run(
            argv,
            cwd=project_root,
            env=_safe_child_env(seed=int(anchor["seed"])),
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            check=False,
        )
    if completed.returncode != 0:
        raise CampaignError(
            f"prepare worker {anchor_key} exited {completed.returncode}; see {stderr_path}"
        )
    payload = _read_json(output)
    _validate_prepare_payload(payload, anchor=anchor)
    return payload


def command_prepare(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve(strict=True)
    campaign_root = Path(args.campaign_root).resolve()
    spec_path = campaign_root / "campaign_spec.json"
    if campaign_root.exists():
        if spec_path.is_file():
            spec = _load_spec(campaign_root)
            print(json.dumps({"status": "ALREADY_PREPARED", "campaign_id": spec["campaign_id"]}, sort_keys=True))
            return EXIT_OK
        raise CampaignError(f"refusing incomplete/existing campaign directory: {campaign_root}")
    campaign_root.mkdir(parents=True, exist_ok=False)
    prepare_dir = campaign_root / "prepare"
    prepare_dir.mkdir(parents=False, exist_ok=False)

    closure_before = _closure_records(project_root)
    builds: dict[str, Any] = {}
    for anchor in PREPARE_ANCHORS:
        payload = _run_prepare_worker(
            project_root=project_root,
            prepare_dir=prepare_dir,
            anchor=anchor,
        )
        builds[str(anchor["anchor_key"])] = {
            "ghost_w": int(anchor["ghost_w"]),
            "ghost_h": int(anchor["ghost_h"]),
            "seed": int(anchor["seed"]),
            "proto_sha256": payload["model"]["proto_sha256"],
            "proto_size_bytes": payload["model"]["proto_size_bytes"],
            "proto_serialization_path": payload["model"]["proto_serialization_path"],
            "variable_count": payload["model"]["variable_count"],
            "constraint_count": payload["model"]["constraint_count"],
            "constraint_histogram": payload["model"].get("constraint_histogram", {}),
            "hard_tombstone": payload["hard_tombstone"],
            "solve_gate": payload["solve_gate"],
            "oracle": payload["oracle"],
            "worker_environment": payload["environment"],
            "artifact": _file_record(
                prepare_dir / str(anchor["anchor_key"]) / "build.json",
                project_root,
            ),
        }
    normalized_environments = {
        _sha256_bytes(
            _canonical_bytes(
                {
                    key: value
                    for key, value in build["worker_environment"].items()
                    if key != "seed"
                }
            )
        )
        for build in builds.values()
    }
    if len(normalized_environments) != 1:
        raise CampaignError("prepare workers did not use one common runtime environment")
    closure_after = _closure_records(project_root)
    if closure_before != closure_after:
        raise CampaignError("input/source closure changed while prepare workers ran")

    base = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": _utc_now(),
        "project_root": str(project_root),
        "semantic_label": SEMANTIC_LABEL,
        "profile": PROFILE_NAME,
        "workers": 1,
        "pythonhashseed": 0,
        "solver_contract": _expected_solver_contract(),
        "arms": [dict(item) for item in ARM_MATRIX],
        "prepare_builds": builds,
        "build_limits": {
            "solve_gate": {
                "max_variables": SOLVE_GATE_MAX_VARIABLES,
                "max_build_rss_kib": SOLVE_GATE_MAX_BUILD_RSS_KIB,
            },
            "hard_tombstone": {
                "max_variables": HARD_TOMBSTONE_MAX_VARIABLES,
                "max_constraints": HARD_TOMBSTONE_MAX_CONSTRAINTS,
                "max_build_rss_kib": HARD_TOMBSTONE_MAX_BUILD_RSS_KIB,
            },
        },
        "closure": closure_after,
        "git": _git_snapshot(project_root),
        "launcher_environment": {
            "python_executable": _python_executable(),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "cgroup_contract": _expected_cgroup_contract(),
        "certificate_boundary": (
            "research-only; clean INFEASIBLE is merely an upper-bound candidate "
            "until independent projection/soundness checks pass"
        ),
    }
    spec = _seal_spec(base)
    _write_json_exclusive(spec_path, spec)
    digest_path = campaign_root / "campaign_spec.sha256"
    _write_text_exclusive(
        digest_path,
        str(spec["campaign_spec_sha256"]) + "\n",
        encoding="ascii",
    )
    print(json.dumps({"status": "PREPARED", "campaign_id": spec["campaign_id"]}, sort_keys=True))
    return EXIT_OK


def _load_worker_apis() -> tuple[Callable[..., Any], ...]:
    # Lazy by design: supervisors can run help/status/launch without importing
    # OR-Tools or any compact-model module.
    if str(RESEARCH_DIR) not in sys.path:
        sys.path.insert(0, str(RESEARCH_DIR))
    from compact_model import (  # type: ignore[import-not-found]
        build_compact_model,
        configure_strict_lean,
        extract_solution,
        validate_solution,
    )
    from independent_oracle import (  # type: ignore[import-not-found]
        compare_oracle_to_build,
        run_independent_oracle,
    )

    return (
        build_compact_model,
        configure_strict_lean,
        extract_solution,
        validate_solution,
        run_independent_oracle,
        compare_oracle_to_build,
    )


def _invoke(fn: Callable[..., Any], available: Mapping[str, Any]) -> Any:
    signature = inspect.signature(fn)
    positional: list[Any] = []
    keyword: dict[str, Any] = {}
    accepts_var_keyword = any(
        item.kind == inspect.Parameter.VAR_KEYWORD
        for item in signature.parameters.values()
    )
    for parameter in signature.parameters.values():
        if parameter.kind in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }:
            continue
        if parameter.name not in available:
            if parameter.default is inspect.Parameter.empty:
                raise CampaignError(
                    f"unsupported required parameter {parameter.name!r} for {fn.__name__}"
                )
            continue
        if parameter.kind == inspect.Parameter.POSITIONAL_ONLY:
            positional.append(available[parameter.name])
        else:
            keyword[parameter.name] = available[parameter.name]
    if accepts_var_keyword:
        for key in (
            "project_root",
            "ghost_w",
            "ghost_h",
            "seed",
            "workers",
            "profile",
            "time_limit_seconds",
        ):
            if key in available and key not in keyword:
                keyword[key] = available[key]
    return fn(*positional, **keyword)


def _extract_model(build: Any) -> Any:
    if hasattr(build, "Proto"):
        return build
    if isinstance(build, Mapping):
        for key in ("model", "cp_model"):
            model = build.get(key)
            if hasattr(model, "Proto"):
                return model
    for name in ("model", "cp_model"):
        model = getattr(build, name, None)
        if hasattr(model, "Proto"):
            return model
    if isinstance(build, tuple):
        for item in build:
            if hasattr(item, "Proto"):
                return item
    raise CampaignError("build_compact_model did not expose a CpModel-like object")


def _proto_record(model: Any) -> dict[str, Any]:
    proto = model.Proto()
    histogram_proto = proto
    serializer = getattr(proto, "SerializeToString", None)
    serialization_path = "native_protobuf"
    if callable(serializer):
        try:
            encoded = serializer(deterministic=True)
        except TypeError:
            encoded = serializer()
    else:
        # OR-Tools 9.14+ may expose a pybind CpModelProto view rather than a
        # google.protobuf message.  Its text form is canonical protobuf text;
        # parse that into the generated message before deterministic encoding.
        from google.protobuf import text_format
        from ortools.sat import cp_model_pb2

        portable_proto = cp_model_pb2.CpModelProto()
        text_format.Parse(str(proto), portable_proto)
        encoded = portable_proto.SerializeToString(deterministic=True)
        histogram_proto = portable_proto
        serialization_path = "pybind_text_to_deterministic_protobuf"
    histogram: Counter[str] = Counter()
    for constraint in histogram_proto.constraints:
        try:
            kind = str(constraint.WhichOneof("constraint") or "unknown")
        except (AttributeError, ValueError):
            kind = "unknown"
        histogram[kind] += 1
    validate = ""
    validate_fn = getattr(model, "Validate", None) or getattr(model, "validate", None)
    if callable(validate_fn):
        validate = str(validate_fn() or "")
    return {
        "proto_sha256": _sha256_bytes(encoded),
        "proto_size_bytes": len(encoded),
        "proto_serialization_path": serialization_path,
        "variable_count": len(proto.variables),
        "constraint_count": len(proto.constraints),
        "constraint_histogram": dict(sorted(histogram.items())),
        "validate_error": validate,
    }


def _verdict_passed(value: Any) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    if isinstance(value, Mapping):
        for key in ("passed", "ok", "match", "equivalent", "sound"):
            if key in value:
                return value[key] is True
        status = str(value.get("status", value.get("verdict", ""))).upper()
        return status in {"PASS", "PASSED", "OK", "MATCH", "EQUIVALENT", "SOUND"}
    return False


def _build_and_audit(
    *, project_root: Path, ghost_w: int, ghost_h: int, seed: int
) -> tuple[Any, Any, dict[str, Any]]:
    (
        build_compact_model,
        _configure_strict_lean,
        _extract_solution,
        _validate_solution,
        run_independent_oracle,
        compare_oracle_to_build,
    ) = _load_worker_apis()
    available = {
        "project_root": project_root,
        "root": project_root,
        "ghost_w": ghost_w,
        "ghost_h": ghost_h,
        "ghost": (ghost_w, ghost_h),
        "ghost_shape": (ghost_w, ghost_h),
        "seed": seed,
        "random_seed": seed,
        "workers": 1,
        "worker_count": 1,
        "profile": PROFILE_NAME,
        "config": {
            "project_root": project_root,
            "ghost_w": ghost_w,
            "ghost_h": ghost_h,
            "seed": seed,
            "workers": 1,
            "profile": PROFILE_NAME,
        },
    }
    started = time.perf_counter()
    build = _invoke(build_compact_model, available)
    build_seconds = time.perf_counter() - started
    model = _extract_model(build)
    build_audit = getattr(build, "audit", None)
    if not isinstance(build_audit, Mapping):
        raise CampaignError("build_compact_model result did not expose mapping-valued audit")
    model_record = _proto_record(model)
    if model_record["validate_error"]:
        raise CampaignError(f"CpModel.Validate failed: {model_record['validate_error']}")
    build_usage = resource.getrusage(resource.RUSAGE_SELF)

    oracle_available = {
        **available,
        "build": build,
        "build_result": build,
        "build_audit": build_audit,
        "model": model,
        "model_record": model_record,
    }
    oracle_result = _invoke(run_independent_oracle, oracle_available)
    comparison = _invoke(
        compare_oracle_to_build,
        {
            **oracle_available,
            "oracle": oracle_result,
            "oracle_result": oracle_result,
        },
    )
    if not _verdict_passed(comparison):
        raise CampaignError("independent oracle/build comparison did not pass")
    hard_tombstone_reasons: list[str] = []
    if int(model_record["variable_count"]) > HARD_TOMBSTONE_MAX_VARIABLES:
        hard_tombstone_reasons.append("variable_count_exceeded")
    if int(model_record["constraint_count"]) > HARD_TOMBSTONE_MAX_CONSTRAINTS:
        hard_tombstone_reasons.append("constraint_count_exceeded")
    if int(build_usage.ru_maxrss) > HARD_TOMBSTONE_MAX_BUILD_RSS_KIB:
        hard_tombstone_reasons.append("build_rss_exceeded")
    solve_gate_reasons: list[str] = []
    if int(model_record["variable_count"]) > SOLVE_GATE_MAX_VARIABLES:
        solve_gate_reasons.append("variable_count_exceeded")
    if int(build_usage.ru_maxrss) > SOLVE_GATE_MAX_BUILD_RSS_KIB:
        solve_gate_reasons.append("build_rss_exceeded")
    hard_tombstone = {
        "passed": not hard_tombstone_reasons,
        "reasons": hard_tombstone_reasons,
        "max_variables": HARD_TOMBSTONE_MAX_VARIABLES,
        "max_constraints": HARD_TOMBSTONE_MAX_CONSTRAINTS,
        "max_build_rss_kib": HARD_TOMBSTONE_MAX_BUILD_RSS_KIB,
        "observed_variables": int(model_record["variable_count"]),
        "observed_constraints": int(model_record["constraint_count"]),
        "observed_build_rss_kib": int(build_usage.ru_maxrss),
    }
    solve_gate = {
        "passed": not solve_gate_reasons,
        "reasons": solve_gate_reasons,
        "max_variables": SOLVE_GATE_MAX_VARIABLES,
        "max_build_rss_kib": SOLVE_GATE_MAX_BUILD_RSS_KIB,
        "observed_variables": int(model_record["variable_count"]),
        "observed_build_rss_kib": int(build_usage.ru_maxrss),
    }
    audit = {
        "model": model_record,
        "build_seconds": round(build_seconds, 6),
        "build_metadata": _jsonable(build_audit),
        "oracle": {
            "result": _jsonable(oracle_result),
            "comparison": _jsonable(comparison),
            "passed": True,
        },
        "hard_tombstone": hard_tombstone,
        "solve_gate": solve_gate,
    }
    if hard_tombstone_reasons:
        raise CampaignError(
            "hard build tombstone rejected model: " + ",".join(hard_tombstone_reasons)
        )
    return build, model, audit


def _configure_solver(
    *, solver: Any, seed: int, time_limit_seconds: float
) -> tuple[Any, dict[str, Any]]:
    (_, configure_strict_lean, _, _, _, _) = _load_worker_apis()
    available = {
        "solver": solver,
        "seed": seed,
        "random_seed": seed,
        "workers": 1,
        "worker_count": 1,
        "profile": PROFILE_NAME,
        "time_limit": time_limit_seconds,
        "time_limit_seconds": time_limit_seconds,
        "max_time_in_seconds": time_limit_seconds,
        "config": {
            "seed": seed,
            "workers": 1,
            "profile": PROFILE_NAME,
            "time_limit_seconds": time_limit_seconds,
        },
    }
    configured = _invoke(configure_strict_lean, available)
    if not isinstance(configured, Mapping):
        raise CampaignError("configure_strict_lean did not return its parameter mapping")
    requested_parameters = _jsonable(dict(configured))
    expected_parameters = _expected_solver_parameters(
        seed=seed,
        time_limit_seconds=time_limit_seconds,
    )
    if requested_parameters != expected_parameters:
        raise CampaignError(
            "configure_strict_lean returned parameters outside the sealed strict_lean contract"
        )
    parameters = solver.parameters
    parameters.random_seed = int(seed)
    parameters.num_search_workers = 1
    parameters.max_time_in_seconds = float(time_limit_seconds)
    parameters.linearization_level = 0
    actual_parameters: dict[str, Any] = {}
    unsupported_parameters: list[str] = []
    for name in sorted(requested_parameters):
        if not hasattr(parameters, name):
            unsupported_parameters.append(name)
            actual_parameters[name] = None
            continue
        actual_parameters[name] = _jsonable(getattr(parameters, name))
    if unsupported_parameters:
        raise CampaignError(
            "runtime OR-Tools does not support sealed solver parameters: "
            + ",".join(unsupported_parameters)
        )
    if actual_parameters != expected_parameters:
        raise CampaignError("actual solver parameters differ from the sealed strict_lean contract")
    return solver, {
        "profile": PROFILE_NAME,
        "expected_parameters": expected_parameters,
        "requested_parameters": requested_parameters,
        "actual_parameters": actual_parameters,
        "unsupported_parameters": unsupported_parameters,
    }


def _solver_numeric(response: Any, name: str, default: int | float = 0) -> int | float:
    value = getattr(response, name, default)
    try:
        return value() if callable(value) else value
    except Exception:
        return default


def _worker_payload(args: argparse.Namespace) -> dict[str, Any]:
    from ortools.sat.python import cp_model  # lazy: worker-only

    project_root = Path(args.project_root).resolve(strict=True)
    expected_runtime_env = {
        "PYTHONHASHSEED": "0",
        "R45_PROFILE": PROFILE_NAME,
        "R45_RANDOM_SEED": str(int(args.seed)),
        "R45_WORKERS": "1",
    }
    runtime_env = {
        key: os.environ.get(key)
        for key in expected_runtime_env
    }
    if runtime_env != expected_runtime_env:
        raise CampaignError(
            f"worker runtime environment mismatch: expected {expected_runtime_env}, observed {runtime_env}"
        )

    campaign_context: dict[str, Any] | None = None
    if args.operation == "solve-arm":
        context_values = {
            "campaign_id": args.expected_campaign_id,
            "campaign_spec_sha256": args.expected_campaign_spec_sha256,
            "closure_sha256": args.expected_closure_sha256,
            "run_key": args.expected_run_key,
            "run_spec_sha256": args.expected_run_spec_sha256,
        }
        missing = sorted(key for key, value in context_values.items() if not value)
        if missing:
            raise CampaignError(
                "solve worker is missing sealed campaign context: " + ",".join(missing)
            )
        observed_closure = _closure_records(project_root)
        if observed_closure.get("closure_sha256") != args.expected_closure_sha256:
            raise CampaignError("solve worker observed input/source closure drift")
        campaign_context = {
            **context_values,
            "closure": observed_closure,
        }

    started = time.perf_counter()
    build, model, audit = _build_and_audit(
        project_root=project_root,
        ghost_w=int(args.ghost_w),
        ghost_h=int(args.ghost_h),
        seed=int(args.seed),
    )
    model_record = dict(audit["model"])
    if args.expected_proto_sha256 is not None and model_record["proto_sha256"] != args.expected_proto_sha256:
        raise CampaignError("rebuilt Proto SHA differs from prepared anchor")
    if args.expected_variable_count is not None and model_record["variable_count"] != args.expected_variable_count:
        raise CampaignError("rebuilt variable count differs from prepared anchor")
    if args.expected_constraint_count is not None and model_record["constraint_count"] != args.expected_constraint_count:
        raise CampaignError("rebuilt constraint count differs from prepared anchor")

    environment = {
        "python_executable": _python_executable(),
        "python_version": platform.python_version(),
        "ortools_version": __import__("ortools").__version__,
        "pythonhashseed": runtime_env["PYTHONHASHSEED"],
        "profile": runtime_env["R45_PROFILE"],
        "workers": int(str(runtime_env["R45_WORKERS"])),
        "seed": int(str(runtime_env["R45_RANDOM_SEED"])),
    }
    base: dict[str, Any] = {
        "schema_version": WORKER_SCHEMA_VERSION,
        "operation": args.operation,
        "ghost": {"w": int(args.ghost_w), "h": int(args.ghost_h)},
        "seed": int(args.seed),
        "workers": 1,
        "profile": PROFILE_NAME,
        "environment": environment,
        "model": model_record,
        "build_seconds": audit["build_seconds"],
        "build_metadata": audit["build_metadata"],
        "hard_tombstone": audit["hard_tombstone"],
        "solve_gate": audit["solve_gate"],
        "oracle": audit["oracle"],
    }
    if campaign_context is not None:
        base["campaign_context"] = campaign_context
    if args.operation == "prepare-anchor":
        base.update(
            {
                "worker_status": "BUILD_READY",
                "total_wall_seconds": round(time.perf_counter() - started, 6),
            }
        )
        return base

    if audit["solve_gate"]["passed"] is not True:
        reasons = ",".join(str(item) for item in audit["solve_gate"]["reasons"])
        raise CampaignError(f"solve gate rejected model: {reasons}")

    solver, strict_lean_configuration = _configure_solver(
        solver=cp_model.CpSolver(),
        seed=int(args.seed),
        time_limit_seconds=float(args.time_limit_seconds),
    )
    solve_started = time.perf_counter()
    raw_status = solver.Solve(model)
    process_wall = time.perf_counter() - solve_started
    status_name = str(solver.StatusName(raw_status)).upper()
    response_stats = str(solver.ResponseStats())
    solver_record: dict[str, Any] = {
        "status": status_name,
        "raw_status": int(raw_status),
        "process_wall_seconds": round(process_wall, 6),
        "wall_time": float(solver.WallTime()),
        "user_time": float(_solver_numeric(solver, "UserTime", 0.0)),
        "deterministic_time": float(
            _solver_numeric(getattr(solver, "ResponseProto")(), "deterministic_time", 0.0)
        ),
        "branches": int(solver.NumBranches()),
        "conflicts": int(solver.NumConflicts()),
        "binary_propagations": int(
            _solver_numeric(getattr(solver, "ResponseProto")(), "num_binary_propagations", 0)
        ),
        "integer_propagations": int(
            _solver_numeric(getattr(solver, "ResponseProto")(), "num_integer_propagations", 0)
        ),
        "best_bound": float(solver.BestObjectiveBound()),
        "response_stats": response_stats,
        "response_stats_sha256": _sha256_bytes(response_stats.encode("utf-8")),
        "parameters": strict_lean_configuration["actual_parameters"],
        "strict_lean_configuration": strict_lean_configuration,
    }
    solution_payload: Any = None
    solution_validation: Any = None
    if raw_status in {cp_model.FEASIBLE, cp_model.OPTIMAL}:
        (_, _, extract_solution, validate_solution, _, _) = _load_worker_apis()
        available = {
            "project_root": project_root,
            "build": build,
            "build_result": build,
            "model": model,
            "solver": solver,
            "status": raw_status,
            "ghost_w": int(args.ghost_w),
            "ghost_h": int(args.ghost_h),
            "seed": int(args.seed),
        }
        solution_payload = _invoke(extract_solution, available)
        solution_validation = _invoke(
            validate_solution,
            {**available, "payload": solution_payload},
        )
        if not _verdict_passed(solution_validation):
            raise CampaignError("extracted solution failed compact-model validation")
    if status_name not in {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"}:
        raise CampaignError(f"unexpected CP-SAT status: {status_name}")
    base.update(
        {
            "worker_status": "SOLVER_RESULT",
            "time_limit_seconds": float(args.time_limit_seconds),
            "solver": solver_record,
            "solution": _jsonable(solution_payload),
            "solution_validation": _jsonable(solution_validation),
            "total_wall_seconds": round(time.perf_counter() - started, 6),
        }
    )
    return base


def command_worker(args: argparse.Namespace) -> int:
    output = Path(args.output).resolve()
    try:
        payload = _worker_payload(args)
        _write_json_exclusive(output, payload)
        return EXIT_OK
    except Exception as exc:
        failure = {
            "schema_version": WORKER_SCHEMA_VERSION,
            "operation": args.operation,
            "worker_status": "WORKER_ERROR",
            "exception_type": type(exc).__name__,
            "exception": str(exc),
            "traceback": traceback.format_exc(),
            "finished_at_utc": _utc_now(),
        }
        if not output.exists():
            try:
                _write_json_exclusive(output, failure)
            except Exception:
                pass
        print(f"worker failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_WORKER


def _read_cgroup_path() -> Path:
    raw = Path("/proc/self/cgroup").read_text(encoding="utf-8")
    for line in raw.splitlines():
        hierarchy, controllers, relative = line.split(":", 2)
        if hierarchy == "0" and controllers == "":
            return Path("/sys/fs/cgroup") / relative.lstrip("/")
    raise CampaignError("unified cgroup v2 path not found")


def _read_int_or_max(path: Path) -> int | str:
    raw = path.read_text(encoding="ascii").strip()
    return "max" if raw == "max" else int(raw)


def _read_kv_ints(path: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        key, value = line.split(None, 1)
        result[key] = int(value)
    return result


def _cgroup_snapshot(cgroup_dir: Path) -> dict[str, Any]:
    scalar_files = (
        "memory.current",
        "memory.peak",
        "memory.swap.current",
        "memory.swap.peak",
        "pids.current",
        "pids.peak",
    )
    values = {
        name: _read_int_or_max(cgroup_dir / name)
        for name in scalar_files
    }
    values.update(
        {
            "memory.events": _read_kv_ints(cgroup_dir / "memory.events"),
            "memory.events.local": _read_kv_ints(cgroup_dir / "memory.events.local"),
            "cpu.stat": _read_kv_ints(cgroup_dir / "cpu.stat"),
        }
    )
    return values


def _events_delta(before: Mapping[str, int], after: Mapping[str, int]) -> dict[str, int]:
    return {
        key: int(after.get(key, 0)) - int(before.get(key, 0))
        for key in sorted(set(before) | set(after))
    }


def _effective_ancestor_limit(cgroup_dir: Path, filename: str) -> int | str:
    numeric: list[int] = []
    current = cgroup_dir
    root = Path("/sys/fs/cgroup")
    while current == root or root in current.parents:
        path = current / filename
        if path.is_file():
            value = _read_int_or_max(path)
            if isinstance(value, int):
                numeric.append(value)
        if current == root:
            break
        current = current.parent
    return min(numeric) if numeric else "max"


def _verify_cgroup(unit_name: str) -> tuple[Path, dict[str, Any]]:
    cgroup_dir = _read_cgroup_path().resolve(strict=True)
    if cgroup_dir.name != unit_name:
        raise CampaignError(
            f"execute-arm must run inside {unit_name}, observed {cgroup_dir.name}"
        )
    observed = {
        "path": str(cgroup_dir),
        "memory.high": _read_int_or_max(cgroup_dir / "memory.high"),
        "memory.max": _read_int_or_max(cgroup_dir / "memory.max"),
        "memory.swap.max": _read_int_or_max(cgroup_dir / "memory.swap.max"),
        "effective.memory.high": _effective_ancestor_limit(cgroup_dir, "memory.high"),
        "effective.memory.max": _effective_ancestor_limit(cgroup_dir, "memory.max"),
        "effective.memory.swap.max": _effective_ancestor_limit(cgroup_dir, "memory.swap.max"),
    }
    required = {
        "memory.high": MEMORY_HIGH_BYTES,
        "memory.max": MEMORY_MAX_BYTES,
        "memory.swap.max": MEMORY_SWAP_MAX_BYTES,
    }
    for key, expected in required.items():
        if observed[key] != expected:
            raise CampaignError(
                f"cgroup {key} mismatch: expected {expected}, observed {observed[key]}"
            )
        effective = observed[f"effective.{key}"]
        if isinstance(effective, int) and effective < expected:
            raise CampaignError(
                f"effective cgroup {key} is tighter than requested: {effective} < {expected}"
            )
    return cgroup_dir, observed


def _mutex_path() -> Path:
    return Path("/run/user") / str(os.getuid()) / "zmd-pj-prod-scale-solve.lock"


def _acquire_mutex() -> Any:
    path = _mutex_path()
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    handle = os.fdopen(descriptor, "a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise CampaignError(f"prod-scale solve mutex is busy: {path}") from exc
    return handle


def _active_units() -> list[str]:
    completed = subprocess.run(
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
        raise CampaignError(f"cannot query user units: {completed.stderr.strip()}")
    units: list[str] = []
    for line in completed.stdout.splitlines():
        unit = line.split(None, 1)[0] if line.split() else ""
        if unit.startswith(("zmd-r45-", "zmd-b4-")):
            units.append(unit)
    return sorted(units)


def _active_solver_processes(*, exclude_pids: set[int] | None = None) -> list[dict[str, Any]]:
    excluded = {os.getpid()} | (exclude_pids or set())
    found: list[dict[str, Any]] = []
    for proc_dir in Path("/proc").iterdir():
        if not proc_dir.name.isdigit():
            continue
        pid = int(proc_dir.name)
        if pid in excluded:
            continue
        try:
            exe_name = (proc_dir / "exe").resolve(strict=True).name.lower()
            if "python" not in exe_name:
                continue
            argv = [
                item.decode("utf-8", errors="replace")
                for item in (proc_dir / "cmdline").read_bytes().split(b"\0")
                if item
            ]
        except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
            continue
        basenames = {Path(item).name for item in argv}
        known = sorted(basenames & _KNOWN_SOLVER_SCRIPTS)
        is_round45_worker = (
            "run_campaign.py" in basenames
            and any(item in {"worker", "execute-arm"} for item in argv)
        )
        if known or is_round45_worker:
            found.append({"pid": pid, "argv": argv, "matched": known or ["round45"]})
    return sorted(found, key=lambda item: int(item["pid"]))


def _unit_name(spec: Mapping[str, Any], arm: Mapping[str, Any], attempt: int) -> str:
    if not 1 <= attempt <= 99:
        raise CampaignError("attempt must be in 1..99")
    digest = str(spec["campaign_spec_sha256"])[:8]
    name = (
        f"zmd-r45-{digest}-g{int(arm['ghost_w'])}x{int(arm['ghost_h'])}"
        f"-t{int(float(arm['time_limit_seconds']))}-s{int(arm['seed'])}-a{attempt:02d}.service"
    )
    if not _SAFE_UNIT_RE.fullmatch(name):
        raise CampaignError(f"unsafe systemd unit name: {name}")
    completed = subprocess.run(
        ["systemd-escape", "--mangle", name],
        check=True,
        capture_output=True,
        text=True,
    )
    if completed.stdout.strip() != name:
        raise CampaignError(f"systemd would mangle unit name: {name}")
    return name


def _attempt_dir(campaign_root: Path, arm: Mapping[str, Any], attempt: int) -> Path:
    ordinal = int(arm["ordinal"])
    run_key = str(arm["run_key"])
    return campaign_root / "arms" / f"{ordinal:02d}_{run_key}" / "attempts" / f"a{attempt:02d}"


def _output_hashes(attempt_dir: Path) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for name in ("result.json", "stdout.txt", "stderr.txt", "run_record.json"):
        path = attempt_dir / name
        records[name] = (
            {"sha256": _sha256_file(path), "size_bytes": path.stat().st_size}
            if path.is_file()
            else {"sha256": None, "size_bytes": None}
        )
    return records


def _model_identity(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    try:
        proto_sha256 = value["proto_sha256"]
        variable_count = value["variable_count"]
        constraint_count = value["constraint_count"]
        proto_size_bytes = value["proto_size_bytes"]
    except KeyError:
        return None
    if not isinstance(proto_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", proto_sha256) is None:
        return None
    numeric = (proto_size_bytes, variable_count, constraint_count)
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in numeric):
        return None
    return {
        "proto_sha256": proto_sha256,
        "proto_size_bytes": int(proto_size_bytes),
        "variable_count": int(variable_count),
        "constraint_count": int(constraint_count),
    }


def _result_integrity_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    *,
    expected: Any = None,
    observed: Any = None,
) -> None:
    record: dict[str, Any] = {"check": name, "passed": bool(passed)}
    if not passed:
        record["expected"] = _jsonable(expected)
        record["observed"] = _jsonable(observed)
    checks.append(record)


def _validate_solve_result(
    *,
    result: Mapping[str, Any] | None,
    spec: Mapping[str, Any],
    arm: Mapping[str, Any],
    prepared: Mapping[str, Any],
    run_spec_sha256: str,
    observed_closure: Mapping[str, Any],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    if not isinstance(result, Mapping):
        _result_integrity_check(checks, "result.object", False, expected="object", observed=type(result).__name__)
        return {"passed": False, "errors": ["result.object"], "checks": checks}

    _result_integrity_check(
        checks,
        "result.schema_version",
        result.get("schema_version") == WORKER_SCHEMA_VERSION,
        expected=WORKER_SCHEMA_VERSION,
        observed=result.get("schema_version"),
    )
    _result_integrity_check(
        checks,
        "result.worker_status",
        result.get("worker_status") == "SOLVER_RESULT",
        expected="SOLVER_RESULT",
        observed=result.get("worker_status"),
    )
    _result_integrity_check(
        checks,
        "result.operation",
        result.get("operation") == "solve-arm",
        expected="solve-arm",
        observed=result.get("operation"),
    )
    expected_ghost = {"w": int(arm["ghost_w"]), "h": int(arm["ghost_h"])}
    _result_integrity_check(
        checks,
        "arm.ghost",
        result.get("ghost") == expected_ghost,
        expected=expected_ghost,
        observed=result.get("ghost"),
    )
    for field, expected in (
        ("seed", int(arm["seed"])),
        ("workers", int(spec["workers"])),
        ("profile", str(spec["profile"])),
        ("time_limit_seconds", float(arm["time_limit_seconds"])),
    ):
        _result_integrity_check(
            checks,
            f"arm.{field}",
            result.get(field) == expected,
            expected=expected,
            observed=result.get(field),
        )

    expected_context = {
        "campaign_id": spec["campaign_id"],
        "campaign_spec_sha256": spec["campaign_spec_sha256"],
        "closure_sha256": spec["closure"]["closure_sha256"],
        "run_key": arm["run_key"],
        "run_spec_sha256": run_spec_sha256,
        "closure": spec["closure"],
    }
    context = result.get("campaign_context")
    _result_integrity_check(
        checks,
        "campaign.context",
        context == expected_context,
        expected=expected_context,
        observed=context,
    )
    closure_valid = True
    if isinstance(context, Mapping):
        try:
            _validate_closure_record(context.get("closure"))
        except CampaignError:
            closure_valid = False
    else:
        closure_valid = False
    _result_integrity_check(
        checks,
        "campaign.result_closure_valid",
        closure_valid,
        expected=True,
        observed=closure_valid,
    )
    _result_integrity_check(
        checks,
        "campaign.post_run_closure",
        observed_closure == spec.get("closure"),
        expected=spec.get("closure"),
        observed=observed_closure,
    )

    expected_model = _model_identity(prepared)
    observed_model = _model_identity(result.get("model"))
    _result_integrity_check(
        checks,
        "model.prepared_identity",
        expected_model is not None and observed_model == expected_model,
        expected=expected_model,
        observed=observed_model,
    )
    model = result.get("model")
    _result_integrity_check(
        checks,
        "model.validate",
        isinstance(model, Mapping) and model.get("validate_error") == "",
        expected="",
        observed=model.get("validate_error") if isinstance(model, Mapping) else None,
    )
    for gate_name in ("hard_tombstone", "solve_gate"):
        gate = result.get(gate_name)
        _result_integrity_check(
            checks,
            f"model.{gate_name}",
            isinstance(gate, Mapping) and gate.get("passed") is True,
            expected=True,
            observed=gate.get("passed") if isinstance(gate, Mapping) else None,
        )

    oracle = result.get("oracle")
    _result_integrity_check(
        checks,
        "oracle.passed",
        isinstance(oracle, Mapping) and _verdict_passed(oracle),
        expected=True,
        observed=oracle.get("passed") if isinstance(oracle, Mapping) else None,
    )
    _result_integrity_check(
        checks,
        "oracle.prepared_identity",
        oracle == prepared.get("oracle"),
        expected=prepared.get("oracle"),
        observed=oracle,
    )

    expected_environment = prepared.get("worker_environment")
    environment = result.get("environment")
    _result_integrity_check(
        checks,
        "runtime.prepared_environment",
        isinstance(expected_environment, Mapping) and environment == expected_environment,
        expected=expected_environment,
        observed=environment,
    )
    launcher_environment = spec.get("launcher_environment")
    launcher_matches = (
        isinstance(environment, Mapping)
        and isinstance(launcher_environment, Mapping)
        and environment.get("python_executable") == launcher_environment.get("python_executable")
        and environment.get("python_version") == launcher_environment.get("python_version")
    )
    _result_integrity_check(
        checks,
        "runtime.launcher_python",
        launcher_matches,
        expected=launcher_environment,
        observed=environment,
    )
    expected_runtime_fields = {
        "pythonhashseed": str(spec["pythonhashseed"]),
        "profile": spec["profile"],
        "seed": int(arm["seed"]),
        "workers": int(spec["workers"]),
    }
    observed_runtime_fields = (
        {key: environment.get(key) for key in expected_runtime_fields}
        if isinstance(environment, Mapping)
        else None
    )
    _result_integrity_check(
        checks,
        "runtime.fixed_fields",
        observed_runtime_fields == expected_runtime_fields,
        expected=expected_runtime_fields,
        observed=observed_runtime_fields,
    )

    solver = result.get("solver")
    solver_status = str(solver.get("status", "")).upper() if isinstance(solver, Mapping) else ""
    _result_integrity_check(
        checks,
        "solver.status",
        solver_status in {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"},
        expected=["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"],
        observed=solver_status,
    )
    duration_fields = ("build_seconds", "total_wall_seconds")
    duration_values = {name: result.get(name) for name in duration_fields}
    durations_valid = all(
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and float(value) >= 0.0
        for value in duration_values.values()
    )
    _result_integrity_check(
        checks,
        "result.durations",
        durations_valid,
        expected="non-negative numeric build_seconds and total_wall_seconds",
        observed=duration_values,
    )
    solver_numeric_fields = (
        "process_wall_seconds",
        "wall_time",
        "user_time",
        "deterministic_time",
        "branches",
        "conflicts",
        "binary_propagations",
        "integer_propagations",
        "best_bound",
    )
    solver_numeric_values = (
        {name: solver.get(name) for name in solver_numeric_fields}
        if isinstance(solver, Mapping)
        else {}
    )
    numeric_metrics_valid = len(solver_numeric_values) == len(solver_numeric_fields) and all(
        not isinstance(value, bool) and isinstance(value, (int, float))
        for value in solver_numeric_values.values()
    )
    raw_status = solver.get("raw_status") if isinstance(solver, Mapping) else None
    _result_integrity_check(
        checks,
        "solver.metrics",
        numeric_metrics_valid and type(raw_status) is int,
        expected="complete numeric solver metrics and integer raw_status",
        observed={**solver_numeric_values, "raw_status": raw_status},
    )
    response_stats = solver.get("response_stats") if isinstance(solver, Mapping) else None
    response_digest = solver.get("response_stats_sha256") if isinstance(solver, Mapping) else None
    response_stats_valid = (
        isinstance(response_stats, str)
        and bool(response_stats)
        and response_digest == _sha256_bytes(response_stats.encode("utf-8"))
    )
    _result_integrity_check(
        checks,
        "solver.response_stats",
        response_stats_valid,
        expected="non-empty response_stats with matching SHA-256",
        observed=response_digest,
    )
    solver_contract = spec.get("solver_contract")
    expected_parameters = (
        solver_contract.get("parameters_by_run_key", {}).get(str(arm["run_key"]))
        if isinstance(solver_contract, Mapping)
        else None
    )
    configuration = solver.get("strict_lean_configuration") if isinstance(solver, Mapping) else None
    expected_configuration = {
        "profile": PROFILE_NAME,
        "expected_parameters": expected_parameters,
        "requested_parameters": expected_parameters,
        "actual_parameters": expected_parameters,
        "unsupported_parameters": [],
    }
    _result_integrity_check(
        checks,
        "solver.strict_configuration",
        configuration == expected_configuration,
        expected=expected_configuration,
        observed=configuration,
    )
    _result_integrity_check(
        checks,
        "solver.actual_parameters",
        isinstance(solver, Mapping) and solver.get("parameters") == expected_parameters,
        expected=expected_parameters,
        observed=solver.get("parameters") if isinstance(solver, Mapping) else None,
    )
    unsupported = configuration.get("unsupported_parameters") if isinstance(configuration, Mapping) else None
    _result_integrity_check(
        checks,
        "solver.unsupported_parameters_empty",
        unsupported == [],
        expected=[],
        observed=unsupported,
    )

    if solver_status in {"FEASIBLE", "OPTIMAL"}:
        solution_ok = result.get("solution") is not None and _verdict_passed(
            result.get("solution_validation")
        )
    else:
        solution_ok = (
            solver_status in {"INFEASIBLE", "UNKNOWN"}
            and result.get("solution") is None
            and result.get("solution_validation") is None
        )
    _result_integrity_check(
        checks,
        "solver.solution_contract",
        solution_ok,
        expected=("validated solution" if solver_status in {"FEASIBLE", "OPTIMAL"} else None),
        observed={
            "solution_present": result.get("solution") is not None,
            "validation": result.get("solution_validation"),
        },
    )
    errors = [str(check["check"]) for check in checks if check["passed"] is not True]
    return {"passed": not errors, "errors": errors, "checks": checks}


def _oom_observed(events: Any) -> bool:
    if not isinstance(events, Mapping):
        return True
    try:
        return any(
            str(key).startswith("oom") and int(value) > 0
            for key, value in events.items()
        )
    except (TypeError, ValueError):
        return True


def _classify_attempt(
    *,
    returncode: int,
    result: Mapping[str, Any] | None,
    events_delta: Mapping[str, int],
    result_integrity: Mapping[str, Any] | None = None,
) -> tuple[str, str | None]:
    try:
        oom_kill_count = int(events_delta.get("oom_kill", 0))
    except (TypeError, ValueError):
        oom_kill_count = 1
    if oom_kill_count > 0:
        return "CGROUP_OOM_KILL", None
    if _oom_observed(events_delta):
        return "CGROUP_OOM_EVENT", None
    if returncode < 0:
        signal_number = -returncode
        if signal_number == signal.SIGSEGV:
            return "WORKER_SIGNAL_SIGSEGV", "SIGSEGV"
        try:
            signal_name = signal.Signals(signal_number).name
        except ValueError:
            signal_name = f"SIG{signal_number}"
        return f"WORKER_SIGNAL_{signal_name}", signal_name
    if returncode != 0:
        return "PROCESS_NONZERO_EXIT", None
    if result is None:
        return "RESULT_MISSING_OR_INVALID", None
    if (
        result.get("schema_version") != WORKER_SCHEMA_VERSION
        or result.get("operation") != "solve-arm"
        or result.get("worker_status") != "SOLVER_RESULT"
    ):
        return "RESULT_SCHEMA_INVALID", None
    if not isinstance(result_integrity, Mapping) or result_integrity.get("passed") is not True:
        return "RESULT_INTEGRITY_INVALID", None
    solver = result.get("solver")
    if not isinstance(solver, Mapping):
        return "RESULT_SCHEMA_INVALID", None
    status = str(solver.get("status", "")).upper()
    if status in {"FEASIBLE", "OPTIMAL"}:
        return "CLEAN_FEASIBLE", None
    if status == "INFEASIBLE":
        return "CLEAN_INFEASIBLE", None
    if status == "UNKNOWN":
        return "CLEAN_UNKNOWN", None
    return "RESULT_SCHEMA_INVALID", None


def command_execute_arm(args: argparse.Namespace) -> int:
    campaign_root = Path(args.campaign_root).resolve(strict=True)
    spec = _load_spec(campaign_root)
    arm = _arm_map(spec).get(args.run_key)
    if arm is None:
        raise CampaignError(f"unknown run_key: {args.run_key}")
    expected_unit = _unit_name(spec, arm, int(args.attempt))
    if args.unit_name != expected_unit:
        raise CampaignError(
            f"unit identity mismatch: expected {expected_unit}, received {args.unit_name}"
        )

    mutex_handle = _acquire_mutex()
    try:
        other_processes = _active_solver_processes()
        if other_processes:
            raise CampaignError(f"another prod-scale solver is active: {other_processes}")
        attempt_dir = _attempt_dir(campaign_root, arm, int(args.attempt))
        attempt_dir.parent.mkdir(parents=True, exist_ok=True)
        attempt_dir.mkdir(parents=False, exist_ok=False)
        prepare_key = _prepare_key(
            int(arm["ghost_w"]), int(arm["ghost_h"]), int(arm["seed"])
        )
        prepared = spec["prepare_builds"][prepare_key]
        run_spec = {
            "schema_version": "round45_bespoke_coordinate_run_spec.v1",
            "campaign_id": spec["campaign_id"],
            "campaign_spec_sha256": spec["campaign_spec_sha256"],
            "closure_sha256": spec["closure"]["closure_sha256"],
            "run_key": args.run_key,
            "attempt": int(args.attempt),
            "unit_name": expected_unit,
            "arm": arm,
            "prepare_key": prepare_key,
            "prepared_model": _model_identity(prepared),
            "solver_parameters": spec["solver_contract"]["parameters_by_run_key"][args.run_key],
        }
        run_spec_sha256 = _sha256_bytes(_canonical_bytes(run_spec))
        run_spec["run_spec_sha256"] = run_spec_sha256
        _write_json_exclusive(attempt_dir / "run_spec.json", run_spec)

        cgroup_dir, cgroup_contract = _verify_cgroup(expected_unit)
        cgroup_start = _cgroup_snapshot(cgroup_dir)
        result_path = attempt_dir / "result.json"
        worker_argv = _worker_argv(
            project_root=Path(str(spec["project_root"])),
            output=result_path,
            operation="solve-arm",
            ghost_w=int(arm["ghost_w"]),
            ghost_h=int(arm["ghost_h"]),
            seed=int(arm["seed"]),
            time_limit_seconds=float(arm["time_limit_seconds"]),
            expected_proto_sha256=str(prepared["proto_sha256"]),
            expected_variable_count=int(prepared["variable_count"]),
            expected_constraint_count=int(prepared["constraint_count"]),
            expected_campaign_id=str(spec["campaign_id"]),
            expected_campaign_spec_sha256=str(spec["campaign_spec_sha256"]),
            expected_closure_sha256=str(spec["closure"]["closure_sha256"]),
            expected_run_key=str(args.run_key),
            expected_run_spec_sha256=run_spec_sha256,
        )
        run_record_path = attempt_dir / "run_record.json"
        run_record: dict[str, Any] = {
            "schema_version": "round45_bespoke_coordinate_run_record.v1",
            "status": "RUNNING",
            "started_at_utc": _utc_now(),
            "pid": os.getpid(),
            "invocation_id": os.environ.get("INVOCATION_ID"),
            "run_spec_sha256": run_spec_sha256,
            "worker_argv": worker_argv,
            "worker_environment": _safe_child_env(seed=int(arm["seed"])),
            "cgroup_contract": cgroup_contract,
            "cgroup_start": cgroup_start,
        }
        _write_json_exclusive(run_record_path, run_record)

        started = time.perf_counter()
        stdout_path = attempt_dir / "stdout.txt"
        stderr_path = attempt_dir / "stderr.txt"
        with stdout_path.open("xb") as stdout_handle, stderr_path.open("xb") as stderr_handle:
            completed = subprocess.run(
                worker_argv,
                cwd=Path(str(spec["project_root"])),
                env=_safe_child_env(seed=int(arm["seed"])),
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                check=False,
            )
        elapsed = time.perf_counter() - started
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        cgroup_end = _cgroup_snapshot(cgroup_dir)
        event_delta = _events_delta(
            cgroup_start["memory.events"], cgroup_end["memory.events"]
        )
        result: dict[str, Any] | None = None
        if result_path.is_file():
            try:
                result = _read_json(result_path)
            except CampaignError:
                result = None
        try:
            observed_closure: Mapping[str, Any] = _closure_records(
                Path(str(spec["project_root"]))
            )
        except (OSError, CampaignError) as exc:
            observed_closure = {
                "error": f"{type(exc).__name__}: {exc}",
            }
        result_integrity = _validate_solve_result(
            result=result,
            spec=spec,
            arm=arm,
            prepared=prepared,
            run_spec_sha256=run_spec_sha256,
            observed_closure=observed_closure,
        )
        terminal_class, signal_name = _classify_attempt(
            returncode=int(completed.returncode),
            result=result,
            events_delta=event_delta,
            result_integrity=result_integrity,
        )
        clean = terminal_class in _CLEAN_TERMINALS
        certificate_eligibility = {
            "status": (
                "RESEARCH_UPPER_BOUND_CANDIDATE"
                if terminal_class == "CLEAN_INFEASIBLE"
                else "NOT_APPLICABLE"
            ),
            "boundary": (
                "never a production-certified result; requires independent soundness "
                "and projection review before any upper-bound claim"
            ),
        }
        run_record.update(
            {
                "status": "COMPLETED" if clean else "WORKER_FAILED",
                "finished_at_utc": _utc_now(),
                "worker_exit_code": int(completed.returncode),
                "wall_seconds": round(elapsed, 6),
                "terminal_class": terminal_class,
                "signal": signal_name,
                "child_resource_usage": {
                    "max_rss_kib": int(usage.ru_maxrss),
                    "major_page_faults": int(usage.ru_majflt),
                    "minor_page_faults": int(usage.ru_minflt),
                    "user_seconds": round(float(usage.ru_utime), 6),
                    "system_seconds": round(float(usage.ru_stime), 6),
                },
                "cgroup_end": cgroup_end,
                "memory_events_delta": event_delta,
                "result_integrity": result_integrity,
                "post_run_closure": observed_closure,
            }
        )
        _write_json_atomic(run_record_path, run_record)
        terminal = {
            "schema_version": TERMINAL_SCHEMA_VERSION,
            "campaign_id": spec["campaign_id"],
            "run_key": args.run_key,
            "attempt": int(args.attempt),
            "unit_name": expected_unit,
            "run_spec_sha256": run_spec_sha256,
            "clean": clean,
            "terminal_class": terminal_class,
            "worker_exit_code": int(completed.returncode),
            "signal": signal_name,
            "result_complete_and_validated": result_integrity.get("passed") is True,
            "result_integrity": result_integrity,
            "solver_status": (
                result.get("solver", {}).get("status")
                if isinstance(result, Mapping) and isinstance(result.get("solver"), Mapping)
                else None
            ),
            "resources": {
                "ru_maxrss_kib": int(usage.ru_maxrss),
                "cgroup_memory_peak_bytes": cgroup_end["memory.peak"],
                "cgroup_swap_peak_bytes": cgroup_end["memory.swap.peak"],
                "memory_events_delta": event_delta,
                "pids_peak": cgroup_end["pids.peak"],
            },
            "certificate_eligibility": certificate_eligibility,
            "output_hashes": _output_hashes(attempt_dir),
            "finished_at_utc": _utc_now(),
        }
        _write_json_exclusive(attempt_dir / "terminal.json", terminal)
        print(json.dumps(terminal, ensure_ascii=False, sort_keys=True))
        return EXIT_OK if clean else EXIT_WORKER
    finally:
        mutex_handle.close()


def _expected_run_spec(
    *, spec: Mapping[str, Any], arm: Mapping[str, Any], attempt: int, unit_name: str
) -> dict[str, Any]:
    prepare_key = _prepare_key(
        int(arm["ghost_w"]), int(arm["ghost_h"]), int(arm["seed"])
    )
    prepared = spec["prepare_builds"][prepare_key]
    base = {
        "schema_version": "round45_bespoke_coordinate_run_spec.v1",
        "campaign_id": spec["campaign_id"],
        "campaign_spec_sha256": spec["campaign_spec_sha256"],
        "closure_sha256": spec["closure"]["closure_sha256"],
        "run_key": arm["run_key"],
        "attempt": int(attempt),
        "unit_name": unit_name,
        "arm": dict(arm),
        "prepare_key": prepare_key,
        "prepared_model": _model_identity(prepared),
        "solver_parameters": spec["solver_contract"]["parameters_by_run_key"][str(arm["run_key"])],
    }
    digest = _sha256_bytes(_canonical_bytes(base))
    return {**base, "run_spec_sha256": digest}


def _attempt_integrity_check(
    checks: list[dict[str, Any]], name: str, passed: bool
) -> None:
    checks.append({"check": name, "passed": bool(passed)})


def _read_attempt_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, "missing"
    try:
        return _read_json(path), None
    except CampaignError as exc:
        return None, str(exc)


def _validate_completed_attempt(
    *,
    attempt_dir: Path,
    spec: Mapping[str, Any],
    arm: Mapping[str, Any],
    attempt: int,
    expected_unit: str,
    run_spec: Mapping[str, Any] | None,
    run_record: Mapping[str, Any] | None,
    terminal: Mapping[str, Any] | None,
    result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    expected_run_spec = _expected_run_spec(
        spec=spec,
        arm=arm,
        attempt=attempt,
        unit_name=expected_unit,
    )
    expected_run_spec_sha256 = str(expected_run_spec["run_spec_sha256"])
    _attempt_integrity_check(checks, "run_spec.exact", run_spec == expected_run_spec)

    prepare_key = str(expected_run_spec["prepare_key"])
    prepared = spec["prepare_builds"][prepare_key]
    result_integrity = _validate_solve_result(
        result=result,
        spec=spec,
        arm=arm,
        prepared=prepared,
        run_spec_sha256=expected_run_spec_sha256,
        observed_closure=spec["closure"],
    )
    _attempt_integrity_check(
        checks,
        "result.complete_and_validated",
        result_integrity.get("passed") is True,
    )

    run_record_events = (
        run_record.get("memory_events_delta")
        if isinstance(run_record, Mapping)
        else None
    )
    run_record_ok = (
        isinstance(run_record, Mapping)
        and run_record.get("schema_version") == "round45_bespoke_coordinate_run_record.v1"
        and run_record.get("status") == "COMPLETED"
        and run_record.get("run_spec_sha256") == expected_run_spec_sha256
        and run_record.get("worker_exit_code") == 0
        and run_record.get("terminal_class") in _CLEAN_TERMINALS
        and run_record.get("signal") is None
        and run_record.get("result_integrity") == result_integrity
        and run_record.get("post_run_closure") == spec.get("closure")
        and not _oom_observed(run_record_events)
    )
    _attempt_integrity_check(checks, "run_record.complete", run_record_ok)
    observed_cgroup = run_record.get("cgroup_contract") if isinstance(run_record, Mapping) else None
    cgroup_ok = (
        isinstance(observed_cgroup, Mapping)
        and observed_cgroup.get("memory.high") == MEMORY_HIGH_BYTES
        and observed_cgroup.get("memory.max") == MEMORY_MAX_BYTES
        and observed_cgroup.get("memory.swap.max") == MEMORY_SWAP_MAX_BYTES
        and str(observed_cgroup.get("path", "")).endswith("/" + expected_unit)
    )
    _attempt_integrity_check(checks, "run_record.cgroup", cgroup_ok)

    terminal_resources = terminal.get("resources") if isinstance(terminal, Mapping) else None
    terminal_events = (
        terminal_resources.get("memory_events_delta")
        if isinstance(terminal_resources, Mapping)
        else None
    )
    terminal_ok = (
        isinstance(terminal, Mapping)
        and terminal.get("schema_version") == TERMINAL_SCHEMA_VERSION
        and terminal.get("campaign_id") == spec.get("campaign_id")
        and terminal.get("run_key") == arm.get("run_key")
        and terminal.get("attempt") == int(attempt)
        and terminal.get("unit_name") == expected_unit
        and terminal.get("run_spec_sha256") == expected_run_spec_sha256
        and terminal.get("clean") is True
        and terminal.get("terminal_class") in _CLEAN_TERMINALS
        and terminal.get("worker_exit_code") == 0
        and terminal.get("signal") is None
        and terminal.get("result_complete_and_validated") is True
        and terminal.get("result_integrity") == result_integrity
        and not _oom_observed(terminal_events)
    )
    _attempt_integrity_check(checks, "terminal.clean", terminal_ok)

    solver = result.get("solver") if isinstance(result, Mapping) else None
    solver_status = solver.get("status") if isinstance(solver, Mapping) else None
    _attempt_integrity_check(
        checks,
        "terminal.solver_status",
        isinstance(terminal, Mapping) and terminal.get("solver_status") == solver_status,
    )
    expected_output_hashes = _output_hashes(attempt_dir)
    _attempt_integrity_check(
        checks,
        "terminal.output_hashes",
        isinstance(terminal, Mapping)
        and terminal.get("output_hashes") == expected_output_hashes,
    )

    errors = [str(check["check"]) for check in checks if check["passed"] is not True]
    return {
        "passed": not errors,
        "errors": errors,
        "checks": checks,
        "result_integrity": result_integrity,
        "run_spec_sha256": expected_run_spec_sha256,
    }


def _attempts_for_arm(
    campaign_root: Path,
    arm: Mapping[str, Any],
    spec: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    attempts_root = _attempt_dir(campaign_root, arm, 1).parent
    if not attempts_root.is_dir():
        return []
    result: list[dict[str, Any]] = []
    active = set(_active_units())
    for path in sorted(attempts_root.iterdir()):
        if not path.is_dir() or not re.fullmatch(r"a[0-9]{2}", path.name):
            continue
        attempt_number = int(path.name[1:])
        terminal_path = path / "terminal.json"
        run_spec_path = path / "run_spec.json"
        run_record_path = path / "run_record.json"
        result_path = path / "result.json"
        run_spec, run_spec_error = _read_attempt_json(run_spec_path)
        run_record, run_record_error = _read_attempt_json(run_record_path)
        terminal, terminal_error = _read_attempt_json(terminal_path)
        worker_result, result_error = _read_attempt_json(result_path)
        entry: dict[str, Any] = {
            "attempt_id": path.name,
            "path": str(path),
            "terminal": None,
            "unit_name": None,
            "result_model": None,
            "artifact_errors": {
                name: error
                for name, error in (
                    ("run_spec", run_spec_error),
                    ("run_record", run_record_error),
                    ("terminal", terminal_error),
                    ("result", result_error),
                )
                if error not in {None, "missing"}
            },
        }
        if run_spec is not None:
            entry["unit_name"] = run_spec.get("unit_name")
            entry["run_spec_sha256"] = run_spec.get("run_spec_sha256")
        expected_unit = (
            _unit_name(spec, arm, attempt_number)
            if spec is not None
            else entry["unit_name"]
        )
        if entry["unit_name"] is None:
            entry["unit_name"] = expected_unit
        if terminal_path.exists():
            entry["terminal"] = terminal
            if spec is None:
                entry["state"] = (
                    "COMPLETE"
                    if terminal is not None and terminal.get("clean") is True
                    else "FAILED"
                )
            else:
                integrity = _validate_completed_attempt(
                    attempt_dir=path,
                    spec=spec,
                    arm=arm,
                    attempt=attempt_number,
                    expected_unit=str(expected_unit),
                    run_spec=run_spec,
                    run_record=run_record,
                    terminal=terminal,
                    result=worker_result,
                )
                entry["integrity"] = integrity
                entry["state"] = "COMPLETE" if integrity["passed"] is True else "FAILED"
        elif entry["unit_name"] in active:
            entry["state"] = "ACTIVE"
        elif run_record_path.is_file():
            entry["state"] = "ORPHANED"
            entry["run_record"] = run_record
        else:
            entry["state"] = "OUTPUT_CONFLICT"
        if worker_result is not None:
            entry["result_model"] = _model_identity(worker_result.get("model"))
            context = worker_result.get("campaign_context")
            if isinstance(context, Mapping):
                entry["result_closure_sha256"] = context.get("closure_sha256")
        result.append(entry)
    return result


def _model_anchor_cross_check(
    spec: Mapping[str, Any], arms_summary: Sequence[Mapping[str, Any]]
) -> tuple[bool | None, list[dict[str, Any]]]:
    prepare_builds = spec.get("prepare_builds")
    if not isinstance(prepare_builds, Mapping):
        return False, [{"match": False, "reason": "prepare_builds_missing"}]
    checks: list[dict[str, Any]] = []
    for arm in arms_summary:
        prepare_key = _prepare_key(
            int(arm["ghost_w"]), int(arm["ghost_h"]), int(arm["seed"])
        )
        prepared_raw = prepare_builds.get(prepare_key)
        prepared = _model_identity(prepared_raw)
        attempts = arm.get("attempts")
        if not isinstance(attempts, Sequence):
            continue
        for attempt in attempts:
            if not isinstance(attempt, Mapping):
                continue
            terminal = attempt.get("terminal")
            if not isinstance(terminal, Mapping):
                continue
            integrity = attempt.get("integrity")
            if (
                attempt.get("state") != "COMPLETE"
                or not isinstance(integrity, Mapping)
                or integrity.get("passed") is not True
            ):
                continue
            observed = attempt.get("result_model")
            observed_model = dict(observed) if isinstance(observed, Mapping) else None
            checks.append(
                {
                    "run_key": str(arm["run_key"]),
                    "attempt_id": str(attempt["attempt_id"]),
                    "prepare_key": prepare_key,
                    "prepared": prepared,
                    "result": observed_model,
                    "match": (
                        prepared == observed_model
                        if prepared is not None and observed_model is not None
                        else None
                    ),
                }
            )
    if not checks:
        return None, checks
    if len(checks) != len(arms_summary):
        return None, checks
    matches = [item["match"] for item in checks]
    if any(match is False for match in matches):
        return False, checks
    if any(match is None for match in matches):
        return None, checks
    return True, checks


def _campaign_summary(campaign_root: Path, spec: Mapping[str, Any]) -> dict[str, Any]:
    arms_summary: list[dict[str, Any]] = []
    overall_status = "READY"
    next_run_key: str | None = None
    completed_count = 0
    for arm in sorted(_arm_map(spec).values(), key=lambda item: int(item["ordinal"])):
        attempts = _attempts_for_arm(campaign_root, arm, spec)
        clean_attempts = [
            entry
            for entry in attempts
            if entry.get("state") == "COMPLETE"
            and isinstance(entry.get("integrity"), Mapping)
            and entry["integrity"].get("passed") is True
        ]
        if clean_attempts:
            logical_status = "COMPLETE"
            completed_count += 1
            selected_attempt = clean_attempts[0]["attempt_id"]
        elif any(entry.get("state") == "ACTIVE" for entry in attempts):
            logical_status = "ACTIVE"
            selected_attempt = None
            if overall_status == "READY":
                overall_status = "ACTIVE"
        elif attempts:
            logical_status = str(attempts[-1].get("state", "FAILED"))
            selected_attempt = None
            if overall_status in {"READY", "ACTIVE"}:
                overall_status = "BLOCKED_RETRYABLE"
        else:
            logical_status = "NOT_STARTED"
            selected_attempt = None
        if next_run_key is None and logical_status != "COMPLETE":
            next_run_key = str(arm["run_key"])
        arms_summary.append(
            {
                **dict(arm),
                "logical_status": logical_status,
                "selected_attempt": selected_attempt,
                "attempts": attempts,
            }
        )
    model_same_by_anchor, model_anchor_checks = _model_anchor_cross_check(
        spec, arms_summary
    )
    expected_closure_sha256 = spec["closure"]["closure_sha256"]
    closure_checks: list[dict[str, Any]] = []
    for arm_summary in arms_summary:
        selected_attempt_id = arm_summary.get("selected_attempt")
        selected = next(
            (
                attempt
                for attempt in arm_summary["attempts"]
                if attempt.get("attempt_id") == selected_attempt_id
            ),
            None,
        )
        observed = (
            selected.get("result_closure_sha256")
            if isinstance(selected, Mapping)
            else None
        )
        closure_checks.append(
            {
                "run_key": arm_summary["run_key"],
                "attempt_id": selected_attempt_id,
                "expected_closure_sha256": expected_closure_sha256,
                "observed_closure_sha256": observed,
                "match": observed == expected_closure_sha256,
            }
        )
    closure_same_all_arms = (
        len(closure_checks) == len(ARM_MATRIX)
        and all(item["match"] is True for item in closure_checks)
        and len(
            {
                str(item["observed_closure_sha256"])
                for item in closure_checks
            }
        )
        == 1
    )
    all_attempts_integrity_valid = (
        completed_count == len(ARM_MATRIX)
        and all(
            arm_summary.get("logical_status") == "COMPLETE"
            for arm_summary in arms_summary
        )
    )
    campaign_integrity_valid = (
        len(arms_summary) == len(ARM_MATRIX)
        and all_attempts_integrity_valid
        and closure_same_all_arms
        and model_same_by_anchor is True
    )
    if completed_count == len(arms_summary):
        if campaign_integrity_valid:
            overall_status = "COMPLETE"
            next_run_key = None
        else:
            overall_status = "BLOCKED_RETRYABLE"
    cross_checks: dict[str, Any] = {
        "six_arms_present": len(arms_summary) == len(ARM_MATRIX),
        "all_selected_attempts_integrity_valid": all_attempts_integrity_valid,
        "campaign_integrity_valid": campaign_integrity_valid,
        "closure_same_all_arms": closure_same_all_arms,
        "closure_checks": closure_checks,
        "model_same_by_anchor": model_same_by_anchor,
        "model_anchor_checks": model_anchor_checks,
        "no_overlap_observed": not any(
            arm["logical_status"] == "ACTIVE" for arm in arms_summary
        ) or sum(arm["logical_status"] == "ACTIVE" for arm in arms_summary) <= 1,
    }
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "campaign": {
            "id": spec["campaign_id"],
            "spec_sha256": spec["campaign_spec_sha256"],
            "semantic_label": spec["semantic_label"],
            "git": spec["git"],
            "closure": spec["closure"],
        },
        "contract": {
            "arm_order": [arm["run_key"] for arm in sorted(spec["arms"], key=lambda item: item["ordinal"])],
            "workers": 1,
            "profile": PROFILE_NAME,
            "cgroup": spec["cgroup_contract"],
        },
        "overall": {
            "status": overall_status,
            "next_run_key": next_run_key,
            "completed_count": completed_count,
            "total_count": len(arms_summary),
        },
        "arms": arms_summary,
        "cross_checks": cross_checks,
    }


def command_status(args: argparse.Namespace) -> int:
    campaign_root = Path(args.campaign_root).resolve(strict=True)
    spec = _load_spec(campaign_root)
    summary = _campaign_summary(campaign_root, spec)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    status = summary["overall"]["status"]
    if status == "ACTIVE":
        return EXIT_ACTIVE
    if status == "BLOCKED_RETRYABLE":
        return EXIT_WORKER
    return EXIT_OK


def command_summarize(args: argparse.Namespace) -> int:
    campaign_root = Path(args.campaign_root).resolve(strict=True)
    spec = _load_spec(campaign_root)
    summary = _campaign_summary(campaign_root, spec)
    _write_json_atomic(campaign_root / "summary.json", summary)
    print(campaign_root / "summary.json")
    return EXIT_OK if summary["overall"]["status"] == "COMPLETE" else EXIT_ACTIVE


def _next_attempt_number(attempts: Sequence[Mapping[str, Any]]) -> int:
    if not attempts:
        return 1
    numbers = [int(str(item["attempt_id"])[1:]) for item in attempts]
    return max(numbers) + 1


def command_launch_next(args: argparse.Namespace) -> int:
    campaign_root = Path(args.campaign_root).resolve(strict=True)
    spec = _load_spec(campaign_root)
    active_units = _active_units()
    if active_units:
        print(json.dumps({"status": "ACTIVE_UNIT", "units": active_units}, sort_keys=True))
        return EXIT_ACTIVE
    active_processes = _active_solver_processes()
    if active_processes:
        print(json.dumps({"status": "ACTIVE_PROCESS", "processes": active_processes}, sort_keys=True))
        return EXIT_BUSY

    summary = _campaign_summary(campaign_root, spec)
    if summary["overall"]["status"] == "COMPLETE":
        print(json.dumps({"status": "CAMPAIGN_COMPLETE"}, sort_keys=True))
        return EXIT_OK
    next_key = summary["overall"]["next_run_key"]
    if not isinstance(next_key, str):
        raise CampaignError("summary did not identify a next arm")
    arm_summary = next(item for item in summary["arms"] if item["run_key"] == next_key)
    attempts = list(arm_summary["attempts"])
    if attempts and not args.retry_failed:
        raise CampaignError(
            f"{next_key} has a failed/orphaned attempt; use --retry-failed explicitly"
        )
    attempt = _next_attempt_number(attempts)
    arm = _arm_map(spec)[next_key]
    unit_name = _unit_name(spec, arm, attempt)
    argv = [
        "systemd-run",
        "--user",
        f"--unit={unit_name}",
        "--service-type=exec",
        "--collect",
        "--expand-environment=no",
        f"--working-directory={spec['project_root']}",
        f"--property=MemoryHigh={MEMORY_HIGH}",
        f"--property=MemoryMax={MEMORY_MAX}",
        f"--property=MemorySwapMax={MEMORY_SWAP_MAX}",
        "--property=OOMPolicy=continue",
        _python_executable(),
        str(SCRIPT_PATH),
        "execute-arm",
        "--campaign-root",
        str(campaign_root),
        "--run-key",
        next_key,
        "--attempt",
        str(attempt),
        "--unit-name",
        unit_name,
    ]
    launch = {
        "status": "DRY_RUN" if args.dry_run else "LAUNCHING",
        "run_key": next_key,
        "attempt": attempt,
        "unit_name": unit_name,
        "argv": argv,
    }
    if args.dry_run:
        print(json.dumps(launch, ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_OK
    completed = subprocess.run(
        argv,
        cwd=Path(str(spec["project_root"])),
        check=False,
        capture_output=True,
        text=True,
    )
    launch["systemd_run_exit_code"] = int(completed.returncode)
    launch["stdout"] = completed.stdout.strip()
    launch["stderr"] = completed.stderr.strip()
    print(json.dumps(launch, ensure_ascii=False, sort_keys=True))
    if completed.returncode != 0:
        return EXIT_CONFIG
    return EXIT_ACTIVE


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="build/audit three anchors and seal a campaign spec")
    prepare.add_argument("--campaign-root", type=Path, required=True)
    prepare.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    prepare.set_defaults(func=command_prepare)

    worker = subparsers.add_parser("worker", help="fresh-process model build or solve worker")
    worker.add_argument("operation", choices=("prepare-anchor", "solve-arm"))
    worker.add_argument("--project-root", type=Path, required=True)
    worker.add_argument("--output", type=Path, required=True)
    worker.add_argument("--ghost-w", type=int, required=True)
    worker.add_argument("--ghost-h", type=int, required=True)
    worker.add_argument("--seed", type=int, required=True)
    worker.add_argument("--time-limit-seconds", type=float, default=0.0)
    worker.add_argument("--expected-proto-sha256")
    worker.add_argument("--expected-variable-count", type=int)
    worker.add_argument("--expected-constraint-count", type=int)
    worker.add_argument("--expected-campaign-id")
    worker.add_argument("--expected-campaign-spec-sha256")
    worker.add_argument("--expected-closure-sha256")
    worker.add_argument("--expected-run-key")
    worker.add_argument("--expected-run-spec-sha256")
    worker.set_defaults(func=command_worker)

    execute = subparsers.add_parser("execute-arm", help="cgroup-bound launcher for one logical arm")
    execute.add_argument("--campaign-root", type=Path, required=True)
    execute.add_argument("--run-key", required=True)
    execute.add_argument("--attempt", type=int, required=True)
    execute.add_argument("--unit-name", required=True)
    execute.set_defaults(func=command_execute_arm)

    launch = subparsers.add_parser("launch-next", help="launch at most one next arm via systemd-run")
    launch.add_argument("--campaign-root", type=Path, required=True)
    launch.add_argument("--retry-failed", action="store_true")
    launch.add_argument("--dry-run", action="store_true")
    launch.set_defaults(func=command_launch_next)

    status = subparsers.add_parser("status", help="render current campaign state without writing")
    status.add_argument("--campaign-root", type=Path, required=True)
    status.set_defaults(func=command_status)

    summarize = subparsers.add_parser("summarize", help="atomically regenerate summary.json")
    summarize.add_argument("--campaign-root", type=Path, required=True)
    summarize.set_defaults(func=command_summarize)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except CampaignError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_CONFIG


if __name__ == "__main__":
    raise SystemExit(main())
