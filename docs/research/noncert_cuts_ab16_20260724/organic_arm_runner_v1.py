#!/usr/bin/env python3
"""Selection-driven runner for one prospective non-certified AB16 arm.

This runner is deliberately narrower than an experiment gate.  It executes
one fresh-process, single-worker arm selected by immutable authority bytes and
publishes raw observations.  It never classifies a pair, upgrades a cut claim,
establishes family-global soundness, or authorizes production use.

The attach environment is absent while the model/controller is constructed.
After a byte-locked baseline incumbent has been reproduced, both control and
treatment set ``EXACT_CUT_FRAMEWORK_ATTACH=1``.  Control constructs the real
attach chain with no enabled families; treatment uses exactly the family set
selected by the manifest.  ``pattern_nogood`` is forbidden in every arm.

Two independent append-only surfaces are retained:

* :class:`src.cuts.ledger.CutLedgerWriter` records every GENERATED/APPLIED
  lifecycle event emitted by the production attach chain; and
* a separate hash-chained journal records every observed ``CompiledCut`` and
  every attach-hook entry/exit, instead of relying on
  ``cut_framework_attach_last``.

All authority inputs are read once through ``O_NOFOLLOW`` descriptors with
before/after ``fstat``.  Every owned output path is created with
``O_EXCL``/exclusive ``mkdir`` below the selection's preregistered attempt
directory.  A failed arm remains a consumed, immutable attempt.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from types import ModuleType
from typing import Any, Protocol


MANIFEST_SCHEMA = "noncert-cuts-ab16-organic-manifest-v2"
SELECTION_SCHEMA = "noncert-cuts-ab16-organic-arm-selection-v2"
PRE_RUN_SCHEMA = "noncert-cuts-ab16-organic-pre-run-authority-v2"
ATTEMPT_EXECUTION_SCHEMA = "noncert-cuts-ab16-attempt-execution-v1"
INPUT_SET_SCHEMA = "noncert-cuts-ab16-attempt-input-set-v2"
SUITE_SELECTION_SCHEMA = "noncert-cuts-ab16-suite-selection-v1"
RESULT_SCHEMA = "noncert-cuts-ab16-organic-arm-result-v1"
JOURNAL_SCHEMA = "noncert-cuts-ab16-compile-attach-journal-v1"
CONTROLLER_TERMINAL_SCHEMA = "noncert-cuts-ab16-controller-terminal-v1"
MANIFEST_PURPOSE = "prospective_noncert_cuts_ab16"
SELECTION_PURPOSE = "prospective_noncert_cuts_ab16_formal_arm"
FORMAL_ARITHMETIC_PURPOSE = "prospective_noncert_cuts_ab16_formal_applied_inequality_replay_v1"
ATTACH_ENV = "EXACT_CUT_FRAMEWORK_ATTACH"
BASELINE_ADMISSION_SCHEMA = "noncert-cuts-ab16-baseline-admission-v2"
BASELINE_ADMISSION_VERDICT = "AB16_BASELINE_INPUTS_ADMITTED"

CONFIGURATION_FAMILIES = {
    "region-capacity": ("region_capacity",),
    "shape-packing-hall": ("shape_packing_hall",),
    "power-hitting-set": ("power_hitting_set",),
    "bundle": (
        "region_capacity",
        "shape_packing_hall",
        "power_hitting_set",
    ),
}
ORDERS = ("ab", "ba")
ARMS = ("control", "treatment")
ARM_SEQUENCE = tuple(
    f"{configuration}-{order}-{arm}"
    for configuration in CONFIGURATION_FAMILIES
    for order, ordered_arms in (
        ("ab", ("control", "treatment")),
        ("ba", ("treatment", "control")),
    )
    for arm in ordered_arms
)
ALLOWED_FAMILIES = frozenset(
    {
        "region_capacity",
        "shape_packing_hall",
        "power_hitting_set",
    }
)
FORBIDDEN_FAMILIES = ("pattern_nogood",)
CONTROLLER_STATUSES = frozenset({"CERTIFIED", "INFEASIBLE", "UNKNOWN", "UNPROVEN"})
EXECUTION_TOOL_ROLES = frozenset(
    {
        "ab16_contract",
        "ab16_terminal_gate",
        "busctl",
        "manager_attestor",
        "manager_epoch_authority",
        "organic_arm_replay",
        "organic_arm_runner",
        "organic_resource_lifecycle",
        "organic_resource_verifier",
        "organic_unit_orchestrator",
        "python3_13",
        "sudo",
        "systemctl",
        "systemd_run",
    }
)
# Historical public name retained for test/import compatibility.  Tool
# authority now lives in each attempt-execution record, never in the shared
# scientific manifest.
PER_ARM_TOOL_ROLES = EXECUTION_TOOL_ROLES
EXPERIMENT_CONTRACT: dict[str, object] = {
    "aggregation": {
        "claim_gate": "conservative_worst_pair_delta",
        "descriptive_summary": "arithmetic_mean_of_ab_and_ba",
        "inconsistent_repeats": "FIXED_RUN_OBSERVATIONS_ONLY",
        "runtime_effect_requires": [
            "both_order_balanced_pairs_credible",
            "both_pair_deltas_cross_same_preregistered_threshold",
            "no_primary_metric_regression",
            "organic_applied_required_for_positive_runtime_effect",
        ],
    },
    "arm_semantics": {
        configuration: {
            "control_enabled_families": [],
            "treatment_enabled_families": list(families),
        }
        for configuration, families in CONFIGURATION_FAMILIES.items()
    },
    "budget": {
        "arm_hard_guard_seconds": 3600,
        "binding_seconds": 600,
        "ledger_cap_bytes": 1_000_000_000,
        "master_seconds": 900,
        "max_iterations": 30,
        "post_attach_seconds": 120,
        "routing_seconds": 600,
        "runtime_max_seconds": 3600,
    },
    "censoring": {
        "internal_budget_unknown": "VALID_RIGHT_CENSORED_TERMINAL",
        "nonactivation": "VALID_FIXED_CONFIGURATION_RESULT",
        "outer_timeout_oom_kill_or_limit_drift": "CREDIBILITY_INCOMPLETE",
        "unknown_without_internal_budget_reached": "CREDIBILITY_INCOMPLETE",
    },
    "classification": {
        "compiled_or_applied_zero_after_generation": "NO_ORGANIC_APPLIED_CUT",
        "generated_zero": "ORGANIC_NONACTIVATION",
        "single_pair_maximum_claim": "SINGLE_PAIR_OBSERVED_DELTA",
        "two_credible_consistent_beneficial_pairs": "RUNTIME_EFFECT_CANDIDATE",
        "two_credible_consistent_no_effect_pairs": "FIXED_CONFIGURATION_NO_EFFECT",
        "two_credible_consistent_regression_pairs": "FIXED_CONFIGURATION_REGRESSION",
        "inconsistent_pairs": "INCONSISTENT_FIXED_RUN_OBSERVATIONS",
    },
    "metrics": {
        "primary": {
            "direction": "false_to_true_is_better",
            "metric": "arm_incumbent_present_after_cut_free_replay",
            "threshold": "boolean_state_change",
        },
        "secondary": [
            {
                "direction": "lower_is_better",
                "metric": "cumulative_deterministic_time_at_normal_controller_terminal",
                "milestone": "normal controller return under the preregistered internal budget",
                "threshold_absolute": 0.000001,
                "threshold_effective_rule": "max(1e-6,abs(control)*0.01)",
                "threshold_relative_control": 0.01,
            },
            {
                "claim_weight": "DESCRIPTIVE_ONLY",
                "metrics": [
                    "branches",
                    "conflicts",
                    "binary_propagations",
                    "integer_propagations",
                    "generated",
                    "compiled",
                    "applied",
                    "first_cut_deterministic_time",
                ],
            },
        ],
        "wall_time": "RESOURCE_DIAGNOSTIC_ONLY",
    },
    "bundle_interaction_diagnostic": {
        "basis": "same cumulative_deterministic_time_at_normal_controller_terminal definition",
        "formula_by_order": "D_bundle - (D_region + D_shape + D_power)",
        "orders": ["ab", "ba"],
        "threshold_effective_rule": "max(1e-6,abs(control)*0.01)",
    },
    "order": list(ARM_SEQUENCE),
    "resource_contract": {
        "collect_mode": "inactive-or-failed",
        "kill_mode": "control-group",
        "memory_high_bytes": 35 * 1024**3,
        "memory_max_bytes": 39 * 1024**3,
        "memory_swap_max_bytes": 16 * 1024**3,
        "oom_policy": "continue",
        "runtime_max_sec": 3600,
        "send_sigkill": True,
        "single_worker": True,
    },
    "schema_version": "noncert-cuts-ab16-experiment-contract-v1",
    "solver_parameters": {
        "binding_alt_cap": 200,
        "fixed_search_branching": True,
        "ghost_rectangle": [6, 6],
        "num_search_workers": 1,
        "probing_level": 3,
        "random_seed": 2026072301,
        "symmetry_level": 3,
    },
}
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
GIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
SAFE_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
MAX_AUTHORITY_BYTES = 64 * 1024 * 1024
PROD_SCALE_LOCK_PATHS = (
    Path("/tmp/zmd-pj-codex-heavy-validation.lock"),
    Path("/run/user/1000/zmd_pj_prod_scale_solver.lock"),
    Path("/run/user/1000/zmd-pj-prod-scale-solve.lock"),
)
_PROD_SCALE_LOCK_DESCRIPTORS: tuple[int, ...] | None = None


class RunnerError(RuntimeError):
    """An authority, lifecycle, evidence, or no-overwrite gate failed."""


def _acquire_prod_scale_locks(
    lock_paths: Sequence[Path] = PROD_SCALE_LOCK_PATHS,
) -> tuple[int, ...]:
    """Acquire every compatibility lock, closing any partial acquisition."""

    if tuple(lock_paths) == () or len(set(lock_paths)) != len(lock_paths):
        raise RunnerError("prod-scale lock path set is empty or duplicated")
    descriptors: list[int] = []
    try:
        for lock_path in lock_paths:
            absolute = Path(os.path.abspath(lock_path))
            if not absolute.parent.is_dir():
                raise RunnerError(f"prod-scale lock parent is unavailable: {absolute.parent}")
            try:
                descriptor = os.open(
                    absolute,
                    os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
                    0o600,
                )
            except OSError as exc:
                raise RunnerError(f"prod-scale lock is unavailable: {absolute}") from exc
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                os.close(descriptor)
                reason = "already held" if isinstance(exc, BlockingIOError) else "unavailable"
                raise RunnerError(f"prod-scale lock is {reason}: {absolute}") from exc
            descriptors.append(descriptor)
        return tuple(descriptors)
    except BaseException:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise


def _retain_process_lifetime_prod_scale_locks(
    lock_paths: Sequence[Path] = PROD_SCALE_LOCK_PATHS,
) -> None:
    """Retain the formal lease until interpreter/process teardown closes its FDs."""

    global _PROD_SCALE_LOCK_DESCRIPTORS
    if _PROD_SCALE_LOCK_DESCRIPTORS is not None:
        raise RunnerError("prod-scale process-lifetime locks are already initialized")
    _PROD_SCALE_LOCK_DESCRIPTORS = _acquire_prod_scale_locks(lock_paths)


@dataclass(frozen=True)
class Snapshot:
    """Bytes and detached identity from one stable open descriptor."""

    data: bytes
    identity: dict[str, object]


@dataclass(frozen=True)
class ArmContext:
    """Strict inputs passed to an arm implementation."""

    attempt_dir: Path
    enabled_families: tuple[str, ...]
    ledger: Any
    manifest: Mapping[str, Any]
    repository_root: Path
    selection: Mapping[str, Any]
    workers: int


@dataclass(frozen=True)
class ArmOutcome:
    """Raw outcome returned by a real or fixture hook implementation."""

    raw_incumbent: Mapping[str, object] | None
    raw_controller_terminal: Mapping[str, object]
    raw_metrics: Mapping[str, object]
    raw_proof_summary: Mapping[str, object]
    raw_solution_vector: Sequence[int] | None
    raw_solver_status: str


class ArmHooks(Protocol):
    """Implementation seam used by production and small offline fixtures."""

    def construct(self, context: ArmContext) -> object:
        """Build the arm while the attach environment is absent."""

    def run_attach_phase(
        self,
        runtime: object,
        context: ArmContext,
        recorder: "CompileAttachRecorder",
    ) -> ArmOutcome:
        """Run attach/post-attach work while the attach environment is on."""


def _canonical_compact(value: object) -> bytes:
    _validate_json(value)
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_json(value: object) -> bytes:
    """Canonical authority bytes, with exactly one trailing newline."""

    return _canonical_compact(value) + b"\n"


def semantic_digest(value: object) -> str:
    """Digest JSON semantics using the baseline-admission convention."""

    return hashlib.sha256(_canonical_compact(value)).hexdigest()


def _validate_json(value: object, label: str = "JSON value") -> None:
    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise RunnerError(f"{label} contains a non-finite number")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _validate_json(item, f"{label}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise RunnerError(f"{label} contains a non-string key")
            _validate_json(item, f"{label}.{key}")
        return
    raise RunnerError(f"{label} is outside the strict JSON domain")


def _json_projection(value: object, label: str = "observed value") -> object:
    """Copy immutable production projections into the strict JSON domain."""

    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise RunnerError(f"{label} contains a non-finite float")
        return value
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, member in value.items():
            if type(key) is not str or key in result:
                raise RunnerError(f"{label} has an invalid mapping key")
            result[key] = _json_projection(member, f"{label}.{key}")
        return result
    if type(value) in {list, tuple}:
        return [_json_projection(member, f"{label}[{index}]") for index, member in enumerate(value)]
    raise RunnerError(f"{label} cannot be projected to strict JSON")


def _strict_loads(raw: bytes, label: str) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise RunnerError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda token: (_ for _ in ()).throw(
                RunnerError(f"{label}: invalid JSON constant {token!r}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunnerError(f"{label}: malformed UTF-8 JSON") from exc
    if canonical_json(value) != raw:
        raise RunnerError(f"{label}: bytes are not canonical JSON")
    return value


def _strict_loads_authority_compact(raw: bytes, label: str) -> object:
    """Parse a compact, no-trailing-newline R1 authority record."""

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise RunnerError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=lambda token: (_ for _ in ()).throw(
                RunnerError(f"{label}: invalid JSON constant {token!r}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunnerError(f"{label}: malformed UTF-8 JSON") from exc
    if _canonical_compact(value) != raw:
        raise RunnerError(f"{label}: bytes are not canonical compact JSON")
    return value


def _exact_keys(
    value: object,
    expected: set[str],
    label: str,
) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise RunnerError(f"{label}: exact key set drifted")
    return value


def _exact_identity(value: object, label: str) -> Mapping[str, Any]:
    record = _exact_keys(value, {"path", "sha256", "size_bytes"}, label)
    if (
        type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
    ):
        raise RunnerError(f"{label}: detached identity is malformed")
    return record


def _exact_identity_with_mode(
    value: object,
    label: str,
) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {"mode", "path", "sha256", "size_bytes"},
        label,
    )
    if type(record["mode"]) is not int or record["mode"] < 0:
        raise RunnerError(f"{label}: mode is malformed")
    _exact_identity(
        {key: record[key] for key in ("path", "sha256", "size_bytes")},
        label,
    )
    return record


def _open_directory_chain(path: Path) -> int:
    """Open an absolute directory without following any path component."""

    absolute = Path(os.path.abspath(path))
    if not absolute.is_absolute():
        raise RunnerError("internal directory path is not absolute")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY
    if not hasattr(os, "O_NOFOLLOW"):
        raise RunnerError("O_NOFOLLOW is unavailable")
    flags |= os.O_NOFOLLOW
    descriptor = os.open("/", flags)
    try:
        for component in absolute.parts[1:]:
            next_descriptor = os.open(
                component,
                flags,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def snapshot_regular(
    path: Path | str,
    *,
    label: str,
    limit: int = MAX_AUTHORITY_BYTES,
) -> Snapshot:
    """Read/hash a regular file once through a no-symlink descriptor."""

    absolute = Path(os.path.abspath(Path(path)))
    parent_fd = _open_directory_chain(absolute.parent)
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(absolute.name, flags, dir_fd=parent_fd)
    except OSError as exc:
        os.close(parent_fd)
        raise RunnerError(f"{label}: cannot open no-symlink input") from exc
    os.close(parent_fd)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size < 0 or before.st_size > limit:
            raise RunnerError(f"{label}: inadmissible regular file")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(1 << 20, remaining))
            if not chunk:
                raise RunnerError(f"{label}: file truncated during same-fd read")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise RunnerError(f"{label}: file grew during same-fd read")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    def signature(item: os.stat_result) -> tuple[int, ...]:
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

    if signature(before) != signature(after):
        raise RunnerError(f"{label}: file changed during same-fd read")
    raw = b"".join(chunks)
    return Snapshot(
        data=raw,
        identity={
            "path": str(absolute),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        },
    )


def replay_identity(value: object, label: str) -> Snapshot:
    """Replay one detached identity and return its exact bytes."""

    identity = _exact_identity(value, label)
    snapshot = snapshot_regular(identity["path"], label=label)
    if snapshot.identity != dict(identity):
        raise RunnerError(f"{label}: detached identity replay failed")
    return snapshot


def replay_identity_with_mode(value: object, label: str) -> Snapshot:
    """Replay one mode-bearing detached identity."""

    identity = _exact_identity_with_mode(value, label)
    detached = {key: identity[key] for key in ("path", "sha256", "size_bytes")}
    snapshot = snapshot_regular(detached["path"], label=label)
    if snapshot.identity != detached:
        raise RunnerError(f"{label}: detached identity replay failed")
    observed_mode = stat.S_IMODE(os.stat(snapshot.identity["path"]).st_mode)
    if observed_mode != identity["mode"]:
        raise RunnerError(f"{label}: mode drifted")
    return snapshot


def _replay_repository_head(execution: Mapping[str, Any]) -> Path:
    """Recheck the per-attempt repository and package-pinned git tool."""

    raw_root = execution["repository_root"]
    if type(raw_root) is not str or not Path(raw_root).is_absolute():
        raise RunnerError("attempt execution repository root is invalid")
    repository_root = Path(raw_root)
    descriptor = _open_directory_chain(repository_root)
    os.close(descriptor)
    git_snapshot = replay_identity_with_mode(
        execution["repository_git_tool_identity"],
        "attempt execution repository git tool",
    )
    try:
        completed = subprocess.run(
            [
                str(git_snapshot.identity["path"]),
                "-C",
                str(repository_root),
                "rev-parse",
                "--verify",
                "HEAD^{commit}",
            ],
            check=False,
            capture_output=True,
            env={"LC_ALL": "C", "PATH": "/usr/bin:/bin"},
            text=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RunnerError("repository HEAD replay failed") from exc
    try:
        observed = completed.stdout.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise RunnerError("repository HEAD replay returned non-ASCII output") from exc
    if (
        completed.returncode != 0
        or completed.stderr
        or GIT_SHA_RE.fullmatch(observed) is None
        or observed != execution["repository_head"]
    ):
        raise RunnerError("repository HEAD differs from the attempt execution")
    return repository_root


def _load_pinned_module(snapshot: Snapshot, role: str) -> ModuleType:
    """Execute one already verified tool from the exact bytes just read."""

    module_name = f"_ab16_{role}_{snapshot.identity['sha256'][:16]}"
    module = ModuleType(module_name)
    module.__file__ = str(snapshot.identity["path"])
    sys.modules[module_name] = module
    try:
        code = compile(
            snapshot.data,
            str(snapshot.identity["path"]),
            "exec",
            dont_inherit=True,
        )
        exec(code, module.__dict__)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def _mkdir_exclusive(path: Path, *, label: str) -> Path:
    absolute = Path(os.path.abspath(path))
    parent_fd = _open_directory_chain(absolute.parent)
    try:
        os.mkdir(absolute.name, 0o700, dir_fd=parent_fd)
        os.fsync(parent_fd)
    except FileExistsError as exc:
        raise RunnerError(f"{label}: no-overwrite collision") from exc
    except OSError as exc:
        raise RunnerError(f"{label}: exclusive directory creation failed") from exc
    finally:
        os.close(parent_fd)
    return absolute


def _prepare_selected_attempt(path: Path, pre_run: Mapping[str, Any]) -> Path:
    """Open the authority-created attempt and exclusively add runner dirs."""

    absolute = Path(os.path.abspath(path))
    descriptor = _open_directory_chain(absolute)
    launch_receipts = {
        Path(pre_run["epoch_observation_paths"]["launch"]),
        Path(pre_run["epoch_transcript_paths"]["launch"]),
    }
    if any(receipt.parent != absolute for receipt in launch_receipts):
        os.close(descriptor)
        raise RunnerError("organic arm launch receipts escaped the attempt directory")
    required = {
        "pre-run-authority.json",
        "selection.json",
        *(receipt.name for receipt in launch_receipts),
    }
    owned = {"checkpoint", "ledger", "runtime", "tmp"}
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISDIR(before.st_mode):
            raise RunnerError("organic arm attempt is not a directory")
        if set(os.listdir(descriptor)) != required:
            raise RunnerError("organic arm attempt prelaunch contents drifted")
        for name in sorted(owned):
            try:
                os.mkdir(name, 0o700, dir_fd=descriptor)
            except FileExistsError as exc:
                raise RunnerError(f"organic arm {name}: no-overwrite collision") from exc
            except OSError as exc:
                raise RunnerError(f"organic arm {name}: exclusive directory creation failed") from exc
        os.fsync(descriptor)
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_uid,
            before.st_gid,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_uid,
            after.st_gid,
        ):
            raise RunnerError("organic arm attempt directory identity drifted")
        if set(os.listdir(descriptor)) != required | owned:
            raise RunnerError("organic arm attempt changed during runner preparation")
    finally:
        os.close(descriptor)
    return absolute


def _write_exclusive(path: Path, raw: bytes, *, label: str) -> dict[str, object]:
    absolute = Path(os.path.abspath(path))
    parent_fd = _open_directory_chain(absolute.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(absolute.name, flags, 0o600, dir_fd=parent_fd)
    except FileExistsError as exc:
        os.close(parent_fd)
        raise RunnerError(f"{label}: no-overwrite collision") from exc
    except OSError as exc:
        os.close(parent_fd)
        raise RunnerError(f"{label}: exclusive output creation failed") from exc
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise RunnerError(f"{label}: output write made no progress")
            view = view[written:]
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
    finally:
        os.close(descriptor)
        os.fsync(parent_fd)
        os.close(parent_fd)
    return {
        "path": str(absolute),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": metadata.st_size,
    }


def _identity_map(value: object, expected_keys: set[str], label: str) -> dict[str, Mapping[str, Any]]:
    record = _exact_keys(value, expected_keys, label)
    return {key: _exact_identity(record[key], f"{label}.{key}") for key in sorted(record)}


def _runtime_parameters(value: object) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "attach_iteration",
            "attach_trigger",
            "binding_alt_cap",
            "binding_seconds",
            "ghost_rect",
            "master_seconds",
            "max_iterations",
            "post_attach_seconds",
            "routing_seconds",
        },
        "manifest runtime parameters",
    )
    ghost = record["ghost_rect"]
    if type(ghost) is not list or len(ghost) != 2 or any(type(item) is not int or item <= 0 for item in ghost):
        raise RunnerError("manifest ghost_rect is invalid")
    for field in (
        "master_seconds",
        "binding_seconds",
        "routing_seconds",
        "post_attach_seconds",
    ):
        if type(record[field]) not in {int, float} or record[field] <= 0:
            raise RunnerError(f"manifest {field} must be a positive exact number")
    for field in ("max_iterations", "binding_alt_cap", "attach_iteration"):
        if type(record[field]) is not int or record[field] <= 0:
            raise RunnerError(f"manifest {field} must be a positive exact integer")
    if type(record["attach_trigger"]) is not str or not record["attach_trigger"]:
        raise RunnerError("manifest attach_trigger is invalid")
    return record


def _detached_identity(value: Mapping[str, Any]) -> dict[str, object]:
    return {field: value[field] for field in ("path", "sha256", "size_bytes")}


def _authority_chain(value: object, *, label: str = "attempt execution authority chain") -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "campaign_root_identity",
            "continuation_identity",
            "manager_epoch_authority_identity",
            "package",
        },
        label,
    )
    for field in (
        "campaign_root_identity",
        "continuation_identity",
        "manager_epoch_authority_identity",
    ):
        _exact_identity(record[field], f"{label} {field}")
    package = _exact_keys(
        record["package"],
        {"manifest_identity", "package_id", "seal_identity"},
        f"{label} package",
    )
    _exact_identity(package["manifest_identity"], "package manifest identity")
    seal = _exact_identity(package["seal_identity"], "package seal identity")
    if (
        type(package["package_id"]) is not str
        or SHA256_RE.fullmatch(package["package_id"]) is None
        or package["package_id"] != seal["sha256"]
    ):
        raise RunnerError(f"{label} package identity is invalid")
    return record


def _research_only_authorizations(value: object, label: str) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "cut_authorized",
            "family_global_soundness_authorized",
            "global_claim_authorized",
            "lower_bound_authorized",
            "mathematical_claim_authorized",
            "optimality_authorized",
            "production_certified_authorized",
            "stage_b_promotion_authorized",
            "upper_bound_authorized",
            "witness_authorized",
        },
        label,
    )
    if any(type(item) is not bool or item is not False for item in record.values()):
        raise RunnerError(f"{label} must remain research-only")
    return record


def _identity_content_projection(value: Mapping[str, Any]) -> dict[str, object]:
    return {
        "mode": value["mode"],
        "sha256": value["sha256"],
        "size_bytes": value["size_bytes"],
    }


def _identity_projection_digest(schema: str, identities: Mapping[str, Mapping[str, Any]]) -> str:
    return hashlib.sha256(
        _canonical_compact(
            {
                "members": {
                    role: _identity_content_projection(identities[role])
                    for role in sorted(identities)
                },
                "schema": schema,
            }
        )
    ).hexdigest()


def _attempt_input_set_digest(
    *,
    preregistration_sha256: str,
    repository_head: str,
    strict_inputs: Mapping[str, Mapping[str, Any]],
    tools: Mapping[str, Mapping[str, Any]],
) -> str:
    return hashlib.sha256(
        _canonical_compact(
            {
                "preregistration_sha256": preregistration_sha256,
                "repository_head": repository_head,
                "schema": "noncert-cuts-ab16-attempt-input-set-v1",
                "strict_input_identities": {
                    role: _identity_content_projection(strict_inputs[role])
                    for role in sorted(strict_inputs)
                },
                "tool_identities": {
                    role: _identity_content_projection(tools[role])
                    for role in sorted(tools)
                },
            }
        )
    ).hexdigest()


def validate_manifest(value: object) -> Mapping[str, Any]:
    """Validate the campaign-wide scientific manifest, with no run topology."""

    record = _exact_keys(
        value,
        {
            "arm_sequence",
            "configuration_families",
            "experiment_contract",
            "forbidden_families",
            "preregistration_sha256",
            "purpose",
            "runtime_parameters",
            "schema_version",
            "scientific_input_set_sha256",
            "scientific_materialization_sha256",
            "seed",
            "workers",
        },
        "organic manifest",
    )
    if (
        record["schema_version"] != MANIFEST_SCHEMA
        or record["purpose"] != MANIFEST_PURPOSE
        or type(record["preregistration_sha256"]) is not str
        or SHA256_RE.fullmatch(record["preregistration_sha256"]) is None
        or type(record["scientific_input_set_sha256"]) is not str
        or SHA256_RE.fullmatch(record["scientific_input_set_sha256"]) is None
        or type(record["scientific_materialization_sha256"]) is not str
        or SHA256_RE.fullmatch(record["scientific_materialization_sha256"]) is None
        or record["workers"] != 1
        or type(record["workers"]) is not int
        or type(record["seed"]) is not int
        or record["arm_sequence"] != list(ARM_SEQUENCE)
        or record["forbidden_families"] != list(FORBIDDEN_FAMILIES)
    ):
        raise RunnerError("organic manifest scalar semantics drifted")
    families = _exact_keys(
        record["configuration_families"],
        set(CONFIGURATION_FAMILIES),
        "manifest configuration families",
    )
    for configuration, expected in CONFIGURATION_FAMILIES.items():
        if families[configuration] != list(expected):
            raise RunnerError(f"manifest family set drifted for {configuration}")
    if record["experiment_contract"] != EXPERIMENT_CONTRACT:
        raise RunnerError("manifest experiment contract drifted")
    _runtime_parameters(record["runtime_parameters"])
    return record


def validate_attempt_execution(value: object) -> Mapping[str, Any]:
    """Validate per-attempt paths, repository state, and tool authority."""

    record = _exact_keys(
        value,
        {
            "attempt_ordinal",
            "authorizations",
            "authority_attempt_dir",
            "authority_chain",
            "campaign_id",
            "campaign_root_identity",
            "continuation_identity",
            "input_set_identity",
            "input_set_sha256",
            "manager_epoch",
            "manifest_identity",
            "package",
            "pre_run_authority_path",
            "preregistration_sha256",
            "repository_git_tool_identity",
            "repository_head",
            "repository_root",
            "run_dir",
            "run_nonce",
            "schema_version",
            "scientific_input_set_sha256",
            "scientific_materialization_sha256",
            "selection_path",
            "slot",
            "status",
            "suite_selection_identity",
            "support_dir",
            "tool_identities",
            "unit_name",
        },
        "attempt execution",
    )
    if (
        record["schema_version"] != ATTEMPT_EXECUTION_SCHEMA
        or record["status"] != "READY"
        or record["slot"] not in ARM_SEQUENCE
        or type(record["attempt_ordinal"]) is not int
        or record["attempt_ordinal"] < 1
        or type(record["preregistration_sha256"]) is not str
        or SHA256_RE.fullmatch(record["preregistration_sha256"]) is None
        or type(record["campaign_id"]) is not str
        or SHA256_RE.fullmatch(record["campaign_id"]) is None
        or type(record["run_nonce"]) is not str
        or SAFE_TOKEN_RE.fullmatch(record["run_nonce"]) is None
        or type(record["repository_head"]) is not str
        or GIT_SHA_RE.fullmatch(record["repository_head"]) is None
        or type(record["repository_root"]) is not str
        or not Path(record["repository_root"]).is_absolute()
        or type(record["input_set_sha256"]) is not str
        or SHA256_RE.fullmatch(record["input_set_sha256"]) is None
        or type(record["scientific_input_set_sha256"]) is not str
        or SHA256_RE.fullmatch(record["scientific_input_set_sha256"]) is None
        or type(record["scientific_materialization_sha256"]) is not str
        or SHA256_RE.fullmatch(record["scientific_materialization_sha256"]) is None
    ):
        raise RunnerError("attempt execution scalar semantics drifted")
    _research_only_authorizations(record["authorizations"], "attempt execution authorizations")
    for field in ("input_set_identity", "repository_git_tool_identity"):
        _exact_identity_with_mode(record[field], f"attempt execution {field}")
    for field in ("manifest_identity", "suite_selection_identity"):
        _exact_identity(record[field], f"attempt execution {field}")
    authority_attempt = Path(record["authority_attempt_dir"])
    run_dir = Path(record["run_dir"])
    support_dir = Path(record["support_dir"])
    pre_run_path = Path(record["pre_run_authority_path"])
    selection_path = Path(record["selection_path"])
    if (
        any(not path.is_absolute() for path in (authority_attempt, run_dir, support_dir, pre_run_path, selection_path))
        or run_dir == authority_attempt
        or support_dir == authority_attempt
        or run_dir.parent != authority_attempt
        or support_dir.parent != authority_attempt
        or run_dir == support_dir
        or pre_run_path != run_dir / "pre-run-authority.json"
        or selection_path != run_dir / "selection.json"
        or Path(record["input_set_identity"]["path"]) != authority_attempt / "attempt-input-set.json"
    ):
        raise RunnerError("attempt execution topology is invalid")
    if type(record["unit_name"]) is not str or not record["unit_name"].endswith(".service") or "/" in record["unit_name"]:
        raise RunnerError("attempt execution unit name is invalid")
    if type(record["manager_epoch"]) is not dict or not record["manager_epoch"]:
        raise RunnerError("attempt execution manager epoch is invalid")
    _validate_json(record["manager_epoch"], "attempt execution manager epoch")
    package = _exact_keys(
        record["package"],
        {"manifest_identity", "package_id", "seal_identity"},
        "attempt execution package",
    )
    _exact_identity(package["manifest_identity"], "attempt execution package manifest")
    seal = _exact_identity(package["seal_identity"], "attempt execution package seal")
    if (
        type(package["package_id"]) is not str
        or SHA256_RE.fullmatch(package["package_id"]) is None
        or package["package_id"] != seal["sha256"]
    ):
        raise RunnerError("attempt execution package identity is invalid")
    chain = _authority_chain(record["authority_chain"])
    for field in ("campaign_root_identity", "continuation_identity"):
        _exact_identity(record[field], f"attempt execution {field}")
    if (
        chain["package"] != package
        or chain["campaign_root_identity"] != record["campaign_root_identity"]
        or chain["continuation_identity"] != record["continuation_identity"]
    ):
        raise RunnerError("attempt execution authority-chain projection drifted")
    tools = _exact_keys(record["tool_identities"], set(EXECUTION_TOOL_ROLES), "attempt execution tools")
    for role in EXECUTION_TOOL_ROLES:
        _exact_identity_with_mode(tools[role], f"attempt execution tool {role}")
    return record


def validate_attempt_input_set(
    value: object,
    *,
    execution: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Validate and rederive the current attempt input-set content hash."""

    record = _exact_keys(
        value,
        {
            "authorizations",
            "input_set_sha256",
            "preregistration_identity",
            "preregistration_sha256",
            "repository_head",
            "schema_version",
            "scientific_input_set_sha256",
            "scientific_materialization_sha256",
            "source_strict_input_identities",
            "source_tool_identities",
            "strict_input_identities",
            "tool_identities",
        },
        "attempt input set",
    )
    _research_only_authorizations(record["authorizations"], "attempt input-set authorizations")
    _exact_identity_with_mode(record["preregistration_identity"], "attempt input-set preregistration")
    strict_inputs_raw = record["strict_input_identities"]
    tools_raw = record["tool_identities"]
    source_inputs_raw = record["source_strict_input_identities"]
    source_tools_raw = record["source_tool_identities"]
    if any(type(item) is not dict or not item for item in (strict_inputs_raw, tools_raw, source_inputs_raw, source_tools_raw)):
        raise RunnerError("attempt input-set identity maps must be non-empty objects")
    strict_inputs: dict[str, Mapping[str, Any]] = {}
    tools: dict[str, Mapping[str, Any]] = {}
    source_inputs: dict[str, Mapping[str, Any]] = {}
    source_tools: dict[str, Mapping[str, Any]] = {}
    for target, raw, label in (
        (strict_inputs, strict_inputs_raw, "strict input"),
        (tools, tools_raw, "tool"),
        (source_inputs, source_inputs_raw, "source strict input"),
        (source_tools, source_tools_raw, "source tool"),
    ):
        for role, identity in raw.items():
            if type(role) is not str or not role:
                raise RunnerError(f"attempt input-set {label} role is invalid")
            target[role] = _exact_identity_with_mode(identity, f"attempt input-set {label} {role}")
    if set(strict_inputs) != set(source_inputs) or set(tools) != set(source_tools):
        raise RunnerError("attempt input-set source and snapshot role sets differ")
    for snapshots, sources in ((strict_inputs, source_inputs), (tools, source_tools)):
        for role in snapshots:
            if any(snapshots[role][field] != sources[role][field] for field in ("sha256", "size_bytes")):
                raise RunnerError(f"attempt input-set source bytes differ for {role}")
    for role, identity in (*strict_inputs.items(), *tools.items()):
        replay_identity_with_mode(identity, f"attempt input-set snapshot {role}")
    expected_digest = _attempt_input_set_digest(
        preregistration_sha256=str(record["preregistration_sha256"]),
        repository_head=str(record["repository_head"]),
        strict_inputs=strict_inputs,
        tools=tools,
    )
    if (
        record["schema_version"] != INPUT_SET_SCHEMA
        or record["input_set_sha256"] != expected_digest
        or record["input_set_sha256"] != execution["input_set_sha256"]
        or record["preregistration_sha256"] != execution["preregistration_sha256"]
        or record["preregistration_identity"]["sha256"] != record["preregistration_sha256"]
        or record["repository_head"] != execution["repository_head"]
        or record["scientific_input_set_sha256"] != execution["scientific_input_set_sha256"]
        or record["scientific_materialization_sha256"] != execution["scientific_materialization_sha256"]
    ):
        raise RunnerError("attempt input-set joins drifted")
    for role in (
        "ab16_contract",
        "ab16_terminal_gate",
        "organic_arm_replay",
        "organic_arm_runner",
        "organic_resource_lifecycle",
        "organic_resource_verifier",
        "organic_unit_orchestrator",
    ):
        if tools.get(role) != execution["tool_identities"][role]:
            raise RunnerError(f"attempt execution code tool {role} differs from input-set snapshot")
    return record


def validate_suite_selection(
    value: object,
    *,
    manifest: Mapping[str, Any],
    manifest_identity: Mapping[str, Any],
) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "arm_sequence",
            "authorizations",
            "manifest_identity",
            "preregistration_sha256",
            "purpose",
            "schema_version",
            "scientific_input_set_sha256",
            "scientific_materialization_sha256",
            "selection_id",
            "status",
        },
        "suite selection",
    )
    _research_only_authorizations(record["authorizations"], "suite selection authorizations")
    without_id = dict(record)
    without_id["selection_id"] = ""
    if (
        record["schema_version"] != SUITE_SELECTION_SCHEMA
        or record["purpose"] != "AB16_SUITE_SELECTION_NO_ARM_LAUNCH"
        or record["status"] != "PASS"
        or record["arm_sequence"] != list(ARM_SEQUENCE)
        or record["manifest_identity"] != manifest_identity
        or record["preregistration_sha256"] != manifest["preregistration_sha256"]
        or record["scientific_input_set_sha256"] != manifest["scientific_input_set_sha256"]
        or record["scientific_materialization_sha256"] != manifest["scientific_materialization_sha256"]
        or record["selection_id"] != hashlib.sha256(_canonical_compact(without_id)).hexdigest()
    ):
        raise RunnerError("suite selection joins drifted")
    return record


def validate_selection(
    value: object,
    *,
    manifest: Mapping[str, Any],
    execution: Mapping[str, Any],
    input_set: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Validate one formal selection against science and its attempt record."""

    record = _exact_keys(
        value,
        {
            "arm",
            "arm_binding_identity",
            "attempt_execution_identity",
            "attempt_dir",
            "attempt_ordinal",
            "authority_chain",
            "authorizations",
            "baseline_admission_identity",
            "baseline_incumbent_sha256",
            "campaign_id",
            "common_prestate_identity",
            "configuration",
            "enabled_families",
            "execution_class",
            "expected_payload_status",
            "fresh_process_required",
            "manifest_identity",
            "order",
            "pre_run_authority_identity",
            "preregistration_sha256",
            "purpose",
            "repository_git_tool_identity",
            "repository_head",
            "repository_root",
            "run_nonce",
            "schema_version",
            "seed",
            "selection_nonce",
            "slot",
            "unit_name",
            "workers",
        },
        "organic arm selection",
    )
    configuration = record["configuration"]
    order = record["order"]
    arm = record["arm"]
    if (
        record["schema_version"] != SELECTION_SCHEMA
        or record["purpose"] != SELECTION_PURPOSE
        or configuration not in CONFIGURATION_FAMILIES
        or order not in ORDERS
        or arm not in ARMS
        or record["slot"] != f"{configuration}-{order}-{arm}"
        or record["execution_class"] != "FORMAL_AB16"
        or record["expected_payload_status"] != {"exit_code": 0, "expectation": "SUCCESS", "signal": 0}
        or record["fresh_process_required"] is not True
        or type(record["fresh_process_required"]) is not bool
        or type(record["selection_nonce"]) is not str
        or SAFE_TOKEN_RE.fullmatch(record["selection_nonce"]) is None
    ):
        raise RunnerError("organic arm selection scalar semantics drifted")
    for field in (
        "campaign_id",
        "repository_git_tool_identity",
        "repository_head",
        "repository_root",
        "run_nonce",
    ):
        if record[field] != execution[field]:
            raise RunnerError(f"selection {field} differs from attempt execution")
    for field in ("workers", "seed"):
        if record[field] != manifest[field]:
            raise RunnerError(f"selection {field} differs from scientific manifest")
    if record["authority_chain"] != execution["authority_chain"]:
        raise RunnerError("selection authority chain differs from attempt execution")
    _authority_chain(record["authority_chain"])
    slot = record["slot"]
    if (
        slot != execution["slot"]
        or record["attempt_ordinal"] != execution["attempt_ordinal"]
        or record["preregistration_sha256"] != execution["preregistration_sha256"]
        or record["attempt_dir"] != execution["run_dir"]
        or record["unit_name"] != execution["unit_name"]
    ):
        raise RunnerError("selection topology differs from attempt execution")
    if not Path(record["attempt_dir"]).is_absolute():
        raise RunnerError("selection attempt directory is not absolute")
    _exact_identity(record["attempt_execution_identity"], "selection attempt execution identity")
    pre_run_identity = _exact_identity(
        record["pre_run_authority_identity"],
        "selection pre-run authority identity",
    )
    if Path(pre_run_identity["path"]) != Path(record["attempt_dir"]) / "pre-run-authority.json":
        raise RunnerError("selection pre-run authority path escaped the preregistered attempt")
    expected_families = () if arm == "control" else CONFIGURATION_FAMILIES[str(configuration)]
    if (
        type(record["enabled_families"]) is not list
        or record["enabled_families"] != list(expected_families)
        or any(family not in ALLOWED_FAMILIES for family in record["enabled_families"])
        or "pattern_nogood" in record["enabled_families"]
    ):
        raise RunnerError("selection enabled family set drifted")
    for field in ("arm_binding_identity", "common_prestate_identity", "baseline_admission_identity"):
        _exact_identity(record[field], f"selection {field}")
    if input_set is not None:
        strict_inputs = input_set["strict_input_identities"]
        for field, role in (
            ("arm_binding_identity", f"arm_binding.{slot}"),
            ("common_prestate_identity", "common_prestate"),
            ("baseline_admission_identity", "baseline_admission"),
        ):
            if record[field] != _detached_identity(strict_inputs[role]):
                raise RunnerError(f"selection {field} differs from current attempt input set")
    if (
        type(record["baseline_incumbent_sha256"]) is not str
        or SHA256_RE.fullmatch(record["baseline_incumbent_sha256"]) is None
    ):
        raise RunnerError("selection baseline incumbent digest is invalid")
    authorizations = _exact_keys(
        record["authorizations"],
        {
            "global_claim_authorized",
            "mathematical_claim_authorized",
            "organic_arm_launch_authorized",
            "production_certified_authorized",
            "solver_run_authorized",
        },
        "selection authorizations",
    )
    if authorizations != {
        "global_claim_authorized": False,
        "mathematical_claim_authorized": False,
        "organic_arm_launch_authorized": True,
        "production_certified_authorized": False,
        "solver_run_authorized": True,
    }:
        raise RunnerError("selection authorization boundary drifted")
    return record


def _validate_baseline_admission(
    value: object,
    *,
    baseline_incumbent_identity: Mapping[str, Any],
    baseline_incumbent_source_identity: Mapping[str, Any],
    selection: Mapping[str, Any],
) -> str:
    record = _exact_keys(
        value,
        {
            "admission_tool_identity",
            "authorizations",
            "campaign_provenance",
            "created_at_utc",
            "expectation_profile",
            "expected_baseline",
            "fixed_assignment_replay",
            "legacy_control",
            "rebuilt_model",
            "schema_version",
            "status",
            "verdict",
        },
        "baseline admission",
    )
    if (
        record["schema_version"] != BASELINE_ADMISSION_SCHEMA
        or record["status"] != "PASS"
        or record["verdict"] != BASELINE_ADMISSION_VERDICT
    ):
        raise RunnerError("baseline admission status/schema drifted")
    authorizations = _exact_keys(
        record["authorizations"],
        {
            "baseline_inputs_admitted",
            "global_claim_authorized",
            "mathematical_claim_authorized",
            "organic_arm_launch_authorized",
            "solver_run_authorized",
        },
        "baseline admission authorizations",
    )
    if authorizations != {
        "baseline_inputs_admitted": True,
        "global_claim_authorized": False,
        "mathematical_claim_authorized": False,
        "organic_arm_launch_authorized": False,
        "solver_run_authorized": False,
    }:
        raise RunnerError("baseline admission authorization boundary drifted")
    expected = record["expected_baseline"]
    if not isinstance(expected, Mapping):
        raise RunnerError("baseline admission expected_baseline is not an object")
    digest = expected.get("incumbent_sha256")
    if (
        type(digest) is not str
        or SHA256_RE.fullmatch(digest) is None
        or digest != selection["baseline_incumbent_sha256"]
    ):
        raise RunnerError("baseline incumbent digest differs from selection")
    replay = record["fixed_assignment_replay"]
    if not isinstance(replay, Mapping):
        raise RunnerError("baseline fixed-assignment replay is not an object")
    provenance = record["campaign_provenance"]
    rebuilt = record["rebuilt_model"]
    if type(provenance) is not dict or not provenance:
        raise RunnerError("baseline admission campaign provenance is not an object")
    if not isinstance(rebuilt, Mapping) or not isinstance(rebuilt.get("metadata"), Mapping):
        raise RunnerError("baseline admission rebuilt metadata is absent")
    if replay.get("campaign_provenance") != provenance or rebuilt["metadata"].get("campaign_provenance") != provenance:
        raise RunnerError("baseline admission campaign provenance join drifted")
    incumbent_identity = _exact_identity(
        replay.get("incumbent_identity"),
        "baseline replay incumbent identity",
    )
    source_identity = _exact_identity_with_mode(
        baseline_incumbent_source_identity,
        "baseline incumbent source identity",
    )
    snapshot_identity = _exact_identity(
        baseline_incumbent_identity,
        "baseline incumbent attempt snapshot identity",
    )
    if dict(incumbent_identity) != _detached_identity(source_identity):
        raise RunnerError("baseline replay incumbent identity differs from attempt source input")
    if any(
        incumbent_identity[field] != snapshot_identity[field]
        for field in ("sha256", "size_bytes")
    ):
        raise RunnerError("baseline incumbent source bytes differ from current attempt snapshot")
    if replay.get("status") != "PASS" or replay.get("solver_status") != "OPTIMAL":
        raise RunnerError("baseline fixed-assignment replay status drifted")
    return digest


class HashChainJournal:
    """Single-FD, append-only, O_EXCL compile/attach journal."""

    def __init__(
        self,
        path: Path,
        *,
        genesis: Mapping[str, object],
    ) -> None:
        self.path = Path(os.path.abspath(path))
        parent_fd = _open_directory_chain(self.path.parent)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND | os.O_CLOEXEC | os.O_NOFOLLOW
        try:
            self._fd = os.open(self.path.name, flags, 0o600, dir_fd=parent_fd)
        except FileExistsError as exc:
            os.close(parent_fd)
            raise RunnerError("compile/attach journal already exists") from exc
        except OSError as exc:
            os.close(parent_fd)
            raise RunnerError("compile/attach journal creation failed") from exc
        else:
            os.fsync(parent_fd)
            os.close(parent_fd)
        self._seq = 0
        self._tail = "0" * 64
        self._sealed = False
        self._counts: dict[str, int] = {}
        self.append("GENESIS", dict(genesis))

    @property
    def counts(self) -> dict[str, int]:
        return dict(sorted(self._counts.items()))

    def append(self, event: str, payload: Mapping[str, object]) -> None:
        if self._sealed:
            raise RunnerError("compile/attach journal is already sealed")
        if type(event) is not str or not event:
            raise RunnerError("journal event name is invalid")
        projected = _json_projection(payload, f"journal {event} payload")
        record = {
            "event": event,
            "payload": projected,
            "prev_event_sha256": self._tail,
            "schema_version": JOURNAL_SCHEMA,
            "seq": self._seq,
        }
        raw = _canonical_compact(record)
        view = memoryview(raw + b"\n")
        while view:
            written = os.write(self._fd, view)
            if written <= 0:
                raise RunnerError("compile/attach journal write made no progress")
            view = view[written:]
        os.fsync(self._fd)
        self._tail = hashlib.sha256(raw).hexdigest()
        self._seq += 1
        self._counts[event] = self._counts.get(event, 0) + 1

    def seal(self) -> None:
        if self._sealed:
            return
        self.append(
            "JOURNAL_SEAL",
            {
                "event_counts_before_seal": self.counts,
                "tail_before_seal": self._tail,
            },
        )
        os.fsync(self._fd)
        os.close(self._fd)
        self._fd = -1
        self._sealed = True

    def abort(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1
        self._sealed = True


class CompileAttachRecorder:
    """Ordered observer for first-solution, attach-hook, and compiled-cut facts."""

    def __init__(
        self,
        journal: HashChainJournal,
        *,
        expected_solution_digest: str,
        require_model_evidence: bool,
    ) -> None:
        self._journal = journal
        self._expected_solution_digest = expected_solution_digest
        self._solution_authorized = False
        self._open_hook: int | None = None
        self._hook_count = 0
        self._compiled_count = 0
        self._require_model_evidence = require_model_evidence
        self._model_evidence_hooks: set[int] = set()

    @property
    def hook_count(self) -> int:
        return self._hook_count

    @property
    def compiled_count(self) -> int:
        return self._compiled_count

    def authorize_first_attach_solution(
        self,
        solution: Mapping[str, object],
    ) -> str:
        if self._solution_authorized:
            raise RunnerError("first attach solution was authorized twice")
        projected = _json_projection(solution, "first attach solution")
        digest = semantic_digest(projected)
        if digest != self._expected_solution_digest:
            raise RunnerError("first attach solution differs from baseline-admission incumbent")
        self._journal.append(
            "FIRST_ATTACH_SOLUTION_VERIFIED",
            {
                "incumbent_sha256": digest,
                "solution_entry_count": len(solution),
            },
        )
        self._solution_authorized = True
        return digest

    def begin_attach_hook(
        self,
        *,
        trigger: str,
        iteration: int,
        solution: Mapping[str, object],
    ) -> int:
        if self._open_hook is not None:
            raise RunnerError("attach hooks may not overlap")
        if type(trigger) is not str or not trigger:
            raise RunnerError("attach trigger is invalid")
        if type(iteration) is not int or iteration <= 0:
            raise RunnerError("attach iteration is invalid")
        projected = _json_projection(solution, "attach solution")
        solution_digest = semantic_digest(projected)
        if not self._solution_authorized:
            self.authorize_first_attach_solution(solution)
        if self._hook_count == 0 and solution_digest != self._expected_solution_digest:
            raise RunnerError("first real attach hook did not consume the frozen incumbent")
        hook_id = self._hook_count
        self._open_hook = hook_id
        self._hook_count += 1
        self._journal.append(
            "ATTACH_HOOK_BEGIN",
            {
                "attach_env": os.environ.get(ATTACH_ENV),
                "hook_id": hook_id,
                "iteration": iteration,
                "solution_sha256": solution_digest,
                "trigger": trigger,
            },
        )
        return hook_id

    def record_compiled_cut(self, compiled: object) -> None:
        if self._open_hook is None:
            raise RunnerError("CompiledCut observation occurred outside an attach hook")
        from src.cuts.typed_platform import CompiledCut

        if type(compiled) is not CompiledCut:
            raise RunnerError("compiled observer accepted an object that is not CompiledCut")
        plan = compiled.plan
        scope = plan.model_scope
        self._journal.append(
            "COMPILED_CUT",
            {
                "compiled_digest": compiled.digest,
                "cut_id": compiled.cut_id,
                "hook_id": self._open_hook,
                "plan": {
                    "digest": plan.digest,
                    "family": plan.family,
                    "model_scope": {
                        "domain_fingerprint": scope.domain_fingerprint,
                        "ghost_policy": scope.ghost_policy,
                        "ghost_rect_digest": scope.ghost_rect_digest,
                    },
                    "operation": plan.operation,
                    "parameters": _json_projection(
                        plan.parameters,
                        "CompiledCut plan parameters",
                    ),
                    "schema_version": plan.schema_version,
                    "semantic_fingerprint": plan.semantic_fingerprint,
                },
                "proof_digest": compiled.proof_digest,
                "scope_digest": compiled.scope_digest,
                "snapshot_digest": compiled.snapshot_digest,
            },
        )
        self._compiled_count += 1

    def record_attach_model_evidence(
        self,
        hook_id: int,
        *,
        pre_model_identity: Mapping[str, object],
        post_model_identity: Mapping[str, object],
        solution_vector_identity: Mapping[str, object],
    ) -> None:
        """Bind raw pre/post model bytes and the incumbent solver vector."""

        if self._open_hook != hook_id or hook_id in self._model_evidence_hooks:
            raise RunnerError("attach model evidence does not match one open hook")
        for label, identity in (
            ("pre model", pre_model_identity),
            ("post model", post_model_identity),
            ("solution vector", solution_vector_identity),
        ):
            _exact_identity(identity, f"attach {label} identity")
        self._journal.append(
            "ATTACH_MODEL_EVIDENCE",
            {
                "hook_id": hook_id,
                "post_model_identity": dict(post_model_identity),
                "pre_model_identity": dict(pre_model_identity),
                "solution_vector_identity": dict(solution_vector_identity),
            },
        )
        self._model_evidence_hooks.add(hook_id)

    def end_attach_hook(
        self,
        hook_id: int,
        *,
        status: str,
        attached_count: int | None,
        error: str | None = None,
    ) -> None:
        if self._open_hook != hook_id:
            raise RunnerError("attach hook exit does not match its entry")
        if status not in {"RETURNED", "RAISED"}:
            raise RunnerError("attach hook terminal status is invalid")
        if status == "RETURNED":
            if type(attached_count) is not int or attached_count < 0 or error is not None:
                raise RunnerError("returned attach hook has invalid terminal fields")
            if self._require_model_evidence and hook_id not in self._model_evidence_hooks:
                raise RunnerError("returned production hook lacks raw model evidence")
        elif attached_count is not None or type(error) is not str or not error:
            raise RunnerError("raised attach hook has invalid terminal fields")
        self._journal.append(
            "ATTACH_HOOK_END",
            {
                "attached_count": attached_count,
                "error": error,
                "hook_id": hook_id,
                "status": status,
            },
        )
        self._open_hook = None

    @contextmanager
    def attach_hook(
        self,
        *,
        trigger: str,
        iteration: int,
        solution: Mapping[str, object],
    ) -> Any:
        """Context helper that records one complete attach invocation."""

        hook_id = self.begin_attach_hook(
            trigger=trigger,
            iteration=iteration,
            solution=solution,
        )

        class Completion:
            def __init__(self, selected_hook_id: int) -> None:
                self.attached_count: int | None = None
                self.hook_id = selected_hook_id

            def returned(self, count: int) -> None:
                if type(count) is not int or count < 0:
                    raise RunnerError("attach return count is invalid")
                self.attached_count = count

        completion = Completion(hook_id)
        try:
            yield completion
        except BaseException as exc:
            self.end_attach_hook(
                hook_id,
                status="RAISED",
                attached_count=None,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        else:
            if completion.attached_count is None:
                raise RunnerError("attach hook exited without recording its return count")
            self.end_attach_hook(
                hook_id,
                status="RETURNED",
                attached_count=completion.attached_count,
            )

    def finalize(self) -> None:
        if not self._solution_authorized:
            raise RunnerError("first attach solution was never authorized")
        if self._open_hook is not None:
            raise RunnerError("attach hook remained open at finalization")
        if self._hook_count <= 0:
            raise RunnerError("arm completed without traversing an attach hook")


def _validate_outcome(value: object) -> ArmOutcome:
    if type(value) is not ArmOutcome:
        raise RunnerError("arm hook returned an invalid outcome type")
    if type(value.raw_solver_status) is not str or not value.raw_solver_status:
        raise RunnerError("raw solver status is invalid")
    metrics = _json_projection(value.raw_metrics, "raw solver metrics")
    proof = _json_projection(value.raw_proof_summary, "raw proof summary")
    controller = _json_projection(
        value.raw_controller_terminal,
        "raw controller terminal",
    )
    if type(metrics) is not dict or type(proof) is not dict or type(controller) is not dict:
        raise RunnerError("raw metrics/proof summary must be JSON objects")
    _validate_controller_terminal(controller)
    if value.raw_solver_status != controller["controller_status"]:
        raise RunnerError("raw solver status differs from controller terminal status")
    incumbent = None if value.raw_incumbent is None else _json_projection(value.raw_incumbent, "raw incumbent")
    vector = (
        None
        if value.raw_solution_vector is None
        else _json_projection(
            list(value.raw_solution_vector),
            "raw solution vector",
        )
    )
    if incumbent is not None and type(incumbent) is not dict:
        raise RunnerError("raw incumbent must be a JSON object or null")
    if vector is not None and (type(vector) is not list or any(type(item) is not int for item in vector)):
        raise RunnerError("raw solution vector must be exact integers or null")
    if (incumbent is None) != (vector is None):
        raise RunnerError("raw incumbent and solution vector presence differ")
    return ArmOutcome(
        raw_controller_terminal=controller,
        raw_incumbent=incumbent,
        raw_metrics=metrics,
        raw_proof_summary=proof,
        raw_solution_vector=vector,
        raw_solver_status=value.raw_solver_status,
    )


def _validate_controller_terminal(value: object) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "budget_censor_evidence",
            "controller_completed",
            "controller_status",
            "cumulative_deterministic_time",
            "master_last_solve",
            "master_solve_history",
            "schema_version",
        },
        "controller terminal",
    )
    if (
        record["schema_version"] != CONTROLLER_TERMINAL_SCHEMA
        or record["controller_completed"] is not True
        or record["controller_status"] not in CONTROLLER_STATUSES
        or type(record["cumulative_deterministic_time"]) not in {int, float}
        or record["cumulative_deterministic_time"] < 0
        or type(record["master_last_solve"]) is not dict
        or type(record["master_solve_history"]) is not list
    ):
        raise RunnerError("controller terminal scalar semantics drifted")
    cumulative = 0.0
    for ordinal, raw in enumerate(record["master_solve_history"], start=1):
        item = _exact_keys(
            raw,
            {
                "binary_propagations",
                "branches",
                "conflicts",
                "deterministic_time",
                "integer_propagations",
                "ordinal",
                "requested_time_limit_seconds",
                "status",
                "user_time",
                "wall_time",
            },
            f"controller master solve {ordinal}",
        )
        if (
            item["ordinal"] != ordinal
            or type(item["status"]) is not str
            or not item["status"]
            or type(item["requested_time_limit_seconds"]) not in {int, float}
            or item["requested_time_limit_seconds"] <= 0
        ):
            raise RunnerError("controller master solve identity/status drifted")
        for field in (
            "binary_propagations",
            "branches",
            "conflicts",
            "integer_propagations",
        ):
            if type(item[field]) is not int or item[field] < 0:
                raise RunnerError("controller master solve counter is invalid")
        for field in ("deterministic_time", "user_time", "wall_time"):
            if type(item[field]) not in {int, float} or item[field] < 0:
                raise RunnerError("controller master solve time is invalid")
        cumulative += float(item["deterministic_time"])
    if abs(cumulative - float(record["cumulative_deterministic_time"])) > 1e-9:
        raise RunnerError("controller cumulative deterministic time drifted")
    budget = _exact_keys(
        record["budget_censor_evidence"],
        {"internal_budget_reached", "kind", "limit", "observed"},
        "controller budget censor evidence",
    )
    if type(budget["internal_budget_reached"]) is not bool:
        raise RunnerError("controller budget censor flag is invalid")
    if budget["internal_budget_reached"]:
        if (
            budget["kind"]
            not in {
                "binding_seconds",
                "master_seconds",
                "max_iterations",
                "routing_seconds",
            }
            or type(budget["limit"]) not in {int, float}
            or budget["limit"] <= 0
            or type(budget["observed"]) is not dict
            or not budget["observed"]
        ):
            raise RunnerError("controller budget censor evidence is invalid")
    elif budget != {
        "internal_budget_reached": False,
        "kind": "none",
        "limit": None,
        "observed": {},
    }:
        raise RunnerError("controller non-censor evidence is not canonical")
    return record


def _read_journal(path: Path) -> tuple[list[Mapping[str, Any]], dict[str, object]]:
    snapshot = snapshot_regular(path, label="compile/attach journal")
    events: list[Mapping[str, Any]] = []
    previous = "0" * 64

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise RunnerError(f"compile/attach journal has duplicate key {key!r}")
            result[key] = value
        return result

    for expected_seq, line in enumerate(snapshot.data.splitlines()):
        try:
            value = json.loads(
                line,
                object_pairs_hook=unique,
                parse_constant=lambda token: (_ for _ in ()).throw(RunnerError(f"journal invalid constant {token}")),
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RunnerError("compile/attach journal is malformed") from exc
        record = _exact_keys(
            value,
            {"event", "payload", "prev_event_sha256", "schema_version", "seq"},
            "compile/attach journal event",
        )
        if (
            record["schema_version"] != JOURNAL_SCHEMA
            or record["seq"] != expected_seq
            or record["prev_event_sha256"] != previous
            or _canonical_compact(record) != line
        ):
            raise RunnerError("compile/attach journal replay failed")
        previous = hashlib.sha256(line).hexdigest()
        events.append(record)
    if not events or events[-1]["event"] != "JOURNAL_SEAL":
        raise RunnerError("compile/attach journal lacks a terminal seal")
    return events, snapshot.identity


def _load_authority(
    selection_path: Path,
) -> tuple[
    Mapping[str, Any],
    Mapping[str, Any],
    dict[str, dict[str, object]],
    Mapping[str, Any],
]:
    selection_snapshot = snapshot_regular(
        selection_path,
        label="organic arm selection",
    )
    selection_raw = _strict_loads_authority_compact(selection_snapshot.data, "organic arm selection")
    if not isinstance(selection_raw, Mapping):
        raise RunnerError("organic arm selection is not an object")
    execution_identity = _exact_identity(
        selection_raw.get("attempt_execution_identity"),
        "selection attempt execution identity",
    )
    execution_snapshot = replay_identity(execution_identity, "attempt execution")
    execution_raw = _strict_loads_authority_compact(execution_snapshot.data, "attempt execution")
    execution = validate_attempt_execution(execution_raw)
    if Path(execution_snapshot.identity["path"]) != Path(execution["authority_attempt_dir"]) / "attempt-execution.json":
        raise RunnerError("attempt execution record escaped its authority attempt")
    if selection_snapshot.identity["path"] != execution["selection_path"]:
        raise RunnerError("organic arm selection path differs from attempt execution")

    input_snapshot = replay_identity_with_mode(execution["input_set_identity"], "attempt input set")
    input_raw = _strict_loads_authority_compact(input_snapshot.data, "attempt input set")
    input_set = validate_attempt_input_set(input_raw, execution=execution)

    manifest_identity = _exact_identity(selection_raw.get("manifest_identity"), "selection manifest identity")
    manifest_snapshot = replay_identity(manifest_identity, "organic manifest")
    manifest_raw = _strict_loads_authority_compact(manifest_snapshot.data, "organic manifest")
    manifest = validate_manifest(manifest_raw)
    manifest_input_identity = input_set["strict_input_identities"]["scientific_manifest"]
    if (
        manifest_snapshot.identity != execution["manifest_identity"]
        or any(
            manifest_snapshot.identity[field] != manifest_input_identity[field]
            for field in ("sha256", "size_bytes")
        )
        or manifest["preregistration_sha256"] != execution["preregistration_sha256"]
        or manifest["scientific_input_set_sha256"] != execution["scientific_input_set_sha256"]
        or manifest["scientific_materialization_sha256"] != execution["scientific_materialization_sha256"]
    ):
        raise RunnerError("scientific manifest differs from the attempt execution/input set")

    suite_snapshot = replay_identity(execution["suite_selection_identity"], "suite selection")
    suite_raw = _strict_loads_authority_compact(suite_snapshot.data, "suite selection")
    suite_selection = validate_suite_selection(
        suite_raw,
        manifest=manifest,
        manifest_identity=manifest_snapshot.identity,
    )
    suite_input_identity = input_set["strict_input_identities"]["suite_selection"]
    if any(suite_snapshot.identity[field] != suite_input_identity[field] for field in ("sha256", "size_bytes")):
        raise RunnerError("suite selection differs from the current attempt input set")

    selection = validate_selection(
        selection_raw,
        manifest=manifest,
        execution=execution,
        input_set=input_set,
    )
    if selection["attempt_execution_identity"] != execution_snapshot.identity:
        raise RunnerError("selection attempt execution identity differs from read bytes")
    _replay_repository_head(execution)

    replayed: dict[str, dict[str, object]] = {
        "attempt_execution": execution_snapshot.identity,
        "attempt_input_set": input_snapshot.identity,
        "selection": selection_snapshot.identity,
        "manifest": manifest_snapshot.identity,
        "suite_selection": suite_snapshot.identity,
    }
    authority_snapshots: dict[str, Snapshot] = {}
    strict_inputs = input_set["strict_input_identities"]
    for required_role in (
        "baseline_admission",
        "baseline_incumbent",
        "common_prestate",
        f"arm_binding.{selection['slot']}",
    ):
        if required_role not in strict_inputs:
            raise RunnerError(f"attempt input set lacks required scientific role {required_role}")
    detached_scientific = {
        "baseline_admission": _detached_identity(strict_inputs["baseline_admission"]),
        "baseline_incumbent": _detached_identity(strict_inputs["baseline_incumbent"]),
        "common_prestate": _detached_identity(strict_inputs["common_prestate"]),
        "arm_binding": _detached_identity(strict_inputs[f"arm_binding.{selection['slot']}"]),
    }
    if "classification_contract" in strict_inputs:
        detached_scientific["classification_contract_tool"] = _detached_identity(
            strict_inputs["classification_contract"]
        )
    for role, identity in detached_scientific.items():
        snapshot = replay_identity(identity, role.replace("_", " "))
        authority_snapshots[role] = snapshot
        replayed[role] = snapshot.identity

    pre_run_snapshot = replay_identity(selection["pre_run_authority_identity"], "organic arm pre-run authority")
    if pre_run_snapshot.identity["path"] != execution["pre_run_authority_path"]:
        raise RunnerError("pre-run authority path differs from attempt execution")
    authority_snapshots["pre_run_authority"] = pre_run_snapshot
    replayed["pre_run_authority"] = pre_run_snapshot.identity

    tool_snapshots: dict[str, Snapshot] = {}
    for role, identity in sorted(execution["tool_identities"].items()):
        snapshot = replay_identity_with_mode(identity, f"attempt execution tool {role}")
        tool_snapshots[role] = snapshot
        replayed[f"execution_tool_{role}"] = snapshot.identity
    runner_snapshot = tool_snapshots["organic_arm_runner"]
    if Path(runner_snapshot.identity["path"]) != Path(__file__).resolve():
        raise RunnerError("attempt execution runner tool does not select this runner")
    authority_snapshots["runner_tool"] = runner_snapshot
    authority_snapshots["per_arm_tool_resource_lifecycle"] = tool_snapshots["organic_resource_lifecycle"]
    replayed["runner_tool"] = runner_snapshot.identity
    replayed["per_arm_tool_resource_lifecycle"] = tool_snapshots["organic_resource_lifecycle"].identity

    for role, identity in (
        ("campaign_root", execution["campaign_root_identity"]),
        ("continuation", execution["continuation_identity"]),
        ("manager_epoch_authority", execution["authority_chain"]["manager_epoch_authority_identity"]),
        ("package_manifest", execution["package"]["manifest_identity"]),
        ("package_seal", execution["package"]["seal_identity"]),
    ):
        snapshot = replay_identity(identity, role.replace("_", " "))
        authority_snapshots[role] = snapshot
        replayed[role] = snapshot.identity

    pre_run_value = _strict_loads_authority_compact(pre_run_snapshot.data, "organic arm pre-run authority")
    if not isinstance(pre_run_value, Mapping):
        raise RunnerError("organic arm pre-run authority is not an object")
    try:
        lifecycle_tool = _load_pinned_module(
            authority_snapshots["per_arm_tool_resource_lifecycle"],
            "organic_resource_lifecycle",
        )
        checked_pre_run = lifecycle_tool.validate_pre_run_authority(
            pre_run_value,
            manifest=manifest,
            suite_selection=suite_selection,
            attempt_execution=execution,
            attempt_execution_identity=execution_snapshot.identity,
        )
        checked_selection = lifecycle_tool.validate_runner_selection(
            selection,
            pre_run_authority=checked_pre_run,
            pre_run_authority_identity=pre_run_snapshot.identity,
            attempt_execution=execution,
            attempt_execution_identity=execution_snapshot.identity,
        )
    except Exception as exc:
        raise RunnerError("package-pinned pre-run authority or selection replay failed") from exc
    if dict(checked_pre_run) != dict(pre_run_value) or dict(checked_selection) != dict(selection):
        raise RunnerError("package-pinned pre-run semantic replay changed its inputs")

    admission_value = _strict_loads(
        authority_snapshots["baseline_admission"].data,
        "baseline admission",
    )
    expected_digest = _validate_baseline_admission(
        admission_value,
        baseline_incumbent_identity=authority_snapshots["baseline_incumbent"].identity,
        baseline_incumbent_source_identity=input_set["source_strict_input_identities"]["baseline_incumbent"],
        selection=selection,
    )
    incumbent = _strict_loads(
        authority_snapshots["baseline_incumbent"].data,
        "baseline incumbent",
    )
    if type(incumbent) is not dict or semantic_digest(incumbent) != expected_digest:
        raise RunnerError("baseline incumbent bytes do not match admitted digest")
    return manifest, selection, replayed, pre_run_value


def _event_counts(events: Sequence[Mapping[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        name = event.get("event")
        if type(name) is not str:
            raise RunnerError("evidence event lacks a string event name")
        counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def _join_ledger_and_journal(
    ledger_events: Sequence[Mapping[str, object]],
    journal_events: Sequence[Mapping[str, object]],
    *,
    enabled_families: Sequence[str],
) -> dict[str, object]:
    generated = [event for event in ledger_events if event.get("event") == "GENERATED"]
    applied = [event for event in ledger_events if event.get("event") == "APPLIED"]
    compiled = [event["payload"] for event in journal_events if event.get("event") == "COMPILED_CUT"]
    if (
        type(enabled_families) is not list
        or any(type(family) is not str for family in enabled_families)
        or len(set(enabled_families)) != len(enabled_families)
    ):
        raise RunnerError("enabled family authority is malformed")
    enabled = set(enabled_families)
    generated_by_cut: dict[str, Mapping[str, object]] = {}
    for event in generated:
        cut_id = event.get("cut_id")
        family = event.get("family")
        if (
            type(cut_id) is not str
            or not cut_id
            or cut_id in generated_by_cut
            or type(family) is not str
            or family not in enabled
        ):
            raise RunnerError("GENERATED event is duplicate, malformed, or outside enabled families")
        generated_by_cut[cut_id] = event
    if not enabled and generated_by_cut:
        raise RunnerError("control arm generated a cut")

    compiled_by_join: dict[
        tuple[str, str, str],
        Mapping[str, object],
    ] = {}
    compiled_cut_ids: set[str] = set()
    for projection in compiled:
        if not isinstance(projection, Mapping):
            raise RunnerError("compiled journal projection is malformed")
        cut_id = projection.get("cut_id")
        plan = projection.get("plan")
        if (
            type(cut_id) is not str
            or not cut_id
            or cut_id in compiled_cut_ids
            or not isinstance(plan, Mapping)
            or type(plan.get("family")) is not str
            or plan.get("family") not in enabled
            or generated_by_cut.get(cut_id, {}).get("family") != plan.get("family")
            or type(plan.get("digest")) is not str
            or type(plan.get("semantic_fingerprint")) is not str
        ):
            raise RunnerError("COMPILED cut lacks one unique allowed GENERATED join")
        key = (
            cut_id,
            plan["digest"],
            plan["semantic_fingerprint"],
        )
        if key in compiled_by_join:
            raise RunnerError("COMPILED cut identity is duplicated")
        compiled_cut_ids.add(cut_id)
        compiled_by_join[key] = projection

    consumed_compiled: set[tuple[str, str, str]] = set()
    for event in applied:
        cut_id = event.get("cut_id")
        plan_digest = event.get("plan_digest")
        semantic_fingerprint = event.get("semantic_fingerprint")
        if type(cut_id) is not str or type(plan_digest) is not str or type(semantic_fingerprint) is not str:
            raise RunnerError("APPLIED event identity is malformed")
        key = (
            cut_id,
            plan_digest,
            semantic_fingerprint,
        )
        projection = compiled_by_join.get(key)
        plan = projection.get("plan") if projection is not None else None
        if (
            projection is None
            or not isinstance(plan, Mapping)
            or event.get("family") != plan.get("family")
            or event.get("family") not in enabled
            or key in consumed_compiled
        ):
            raise RunnerError("APPLIED event lacks one unique allowed COMPILED join")
        consumed_compiled.add(key)
    if not 0 <= len(applied) <= len(compiled) <= len(generated):
        raise RunnerError("cut counts do not satisfy 0 <= APPLIED <= COMPILED <= GENERATED")
    return {
        "applied": len(applied),
        "compiled": len(compiled),
        "generated": len(generated),
    }


@contextmanager
def _arm_environment(attempt_dir: Path, *, seed: int) -> Any:
    keys = {
        ATTACH_ENV,
        "EXACT_CP_SAT_WORKERS",
        "EXACT_MASTER_CP_SAT_WORKERS",
        "EXACT_MASTER_RANDOM_SEED",
        "EXACT_MASTER_SEARCH_BRANCHING",
        "EXACT_MASTER_CP_MODEL_PROBING_LEVEL",
        "EXACT_MASTER_SYMMETRY_LEVEL",
        "PYTHONDONTWRITEBYTECODE",
        "TMPDIR",
    }
    previous = {key: os.environ.get(key) for key in keys}
    if previous[ATTACH_ENV] is not None:
        raise RunnerError("attach environment must be absent before construction")
    try:
        os.environ["EXACT_CP_SAT_WORKERS"] = "1"
        os.environ["EXACT_MASTER_CP_SAT_WORKERS"] = "1"
        os.environ["EXACT_MASTER_RANDOM_SEED"] = str(seed)
        os.environ["EXACT_MASTER_SEARCH_BRANCHING"] = "fixed"
        os.environ["EXACT_MASTER_CP_MODEL_PROBING_LEVEL"] = "3"
        os.environ["EXACT_MASTER_SYMMETRY_LEVEL"] = "3"
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
        os.environ["TMPDIR"] = str(attempt_dir / "tmp")
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _install_repository_import_root(repository_root: object) -> Path:
    """Expose the already replayed repository to isolated-Python imports."""

    if type(repository_root) is not str or not Path(repository_root).is_absolute():
        raise RunnerError("replayed repository import root is invalid")
    root = Path(repository_root)
    descriptor = _open_directory_chain(root)
    os.close(descriptor)
    text = str(root)
    if text not in sys.path:
        sys.path.insert(0, text)
    return root


def _read_small_ascii(path: Path, label: str) -> str:
    """Read one procfs/cgroupfs control through a no-symlink descriptor."""

    absolute = Path(os.path.abspath(path))
    try:
        parent_fd = _open_directory_chain(absolute.parent)
    except OSError as exc:
        raise RunnerError(f"{label} parent path is unavailable") from exc
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(absolute.name, flags, dir_fd=parent_fd)
    except OSError as exc:
        os.close(parent_fd)
        raise RunnerError(f"{label} is unavailable") from exc
    os.close(parent_fd)
    try:
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise RunnerError(f"{label} is not a singly linked regular control")
            chunks: list[bytes] = []
            size = 0
            while True:
                chunk = os.read(descriptor, 4096)
                if not chunk:
                    break
                size += len(chunk)
                if size > 64 * 1024:
                    raise RunnerError(f"{label} exceeds the bounded control size")
                chunks.append(chunk)
            after = os.fstat(descriptor)
        except OSError as exc:
            raise RunnerError(f"{label} same-FD read failed") from exc
    finally:
        os.close(descriptor)
    if (before.st_dev, before.st_ino, before.st_mode, before.st_nlink) != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_nlink,
    ):
        raise RunnerError(f"{label} changed during same-FD read")
    try:
        text = b"".join(chunks).decode("ascii")
    except UnicodeDecodeError as exc:
        raise RunnerError(f"{label} is not ASCII") from exc
    if "\x00" in text or "\r" in text:
        raise RunnerError(f"{label} contains invalid control bytes")
    return text


def _current_unified_cgroup_path() -> Path:
    records: list[str] = []
    membership_path = Path("/proc") / str(os.getpid()) / "cgroup"
    for line in _read_small_ascii(membership_path, "runner cgroup membership").splitlines():
        hierarchy, separator, remainder = line.partition(":")
        controllers, second_separator, path = remainder.partition(":")
        if not separator or not second_separator:
            raise RunnerError("runner cgroup membership is malformed")
        if hierarchy == "0" and controllers == "":
            records.append(path)
    if len(records) != 1:
        raise RunnerError("runner lacks one unified cgroup membership")
    raw_path = records[0]
    if not raw_path.startswith("/") or any(component in {"", ".", ".."} for component in raw_path.split("/")[1:]):
        raise RunnerError("runner unified cgroup path is unsafe")
    return Path(raw_path)


def _require_prod_scale_unit_context(
    unit_name: str,
    resource_contract: Mapping[str, Any],
) -> None:
    """Reject a public run outside its selected, resource-capped unit."""

    if os.geteuid() != os.getuid() or os.geteuid() == 0:
        raise RunnerError("prod-scale runner must be the ordinary selected user")
    control_group = _current_unified_cgroup_path()
    if control_group.name != unit_name:
        raise RunnerError(f"selected prod-scale resource unit context is absent: {unit_name}")
    expected = {
        "memory.high": str(resource_contract["memory_high_bytes"]),
        "memory.max": str(resource_contract["memory_max_bytes"]),
        "memory.swap.max": str(resource_contract["memory_swap_max_bytes"]),
    }
    cgroup_root = Path("/sys/fs/cgroup").joinpath(*control_group.parts[1:])
    for control_name, expected_value in expected.items():
        observed = _read_small_ascii(cgroup_root / control_name, f"runner cgroup {control_name}")
        if observed.endswith("\n"):
            observed = observed[:-1]
        if "\n" in observed or observed != expected_value:
            raise RunnerError(f"runner cgroup {control_name} differs from the prod-scale contract")


def _run_with_hooks(
    selection_path: Path,
    hooks: ArmHooks,
    *,
    enforce_single_process_use: bool,
    require_prod_scale_unit_context: bool = False,
    retain_prod_scale_locks: bool = False,
) -> dict[str, object]:
    """Execute one selected arm; tests inject small hooks through this seam."""

    global _PUBLIC_RUN_STARTED
    if enforce_single_process_use:
        if _PUBLIC_RUN_STARTED:
            raise RunnerError("fresh process contract forbids a second arm")
        _PUBLIC_RUN_STARTED = True

    manifest, selection, authority_identities, pre_run = _load_authority(selection_path)
    if require_prod_scale_unit_context:
        _require_prod_scale_unit_context(
            str(selection["unit_name"]),
            pre_run["resource_contract"],
        )
    if retain_prod_scale_locks:
        _retain_process_lifetime_prod_scale_locks()
    attempt_dir = _prepare_selected_attempt(Path(selection["attempt_dir"]), pre_run)
    _install_repository_import_root(selection["repository_root"])

    from src.cuts.ledger import CutLedgerWriter, read_segment

    ledger = CutLedgerWriter(
        attempt_dir / "ledger",
        scope_id=str(selection["slot"]),
        writer_id="organic-arm-v1",
        genesis_context={
            "arm": selection["arm"],
            "campaign_id": selection["campaign_id"],
            "enabled_families": list(selection["enabled_families"]),
            "manifest_sha256": authority_identities["manifest"]["sha256"],
            "selection_sha256": authority_identities["selection"]["sha256"],
            "selection_nonce": selection["selection_nonce"],
        },
    )
    journal = HashChainJournal(
        attempt_dir / "compile-attach-journal.jsonl",
        genesis={
            "arm": selection["arm"],
            "campaign_id": selection["campaign_id"],
            "enabled_families": list(selection["enabled_families"]),
            "selection_identity": authority_identities["selection"],
            "slot": selection["slot"],
        },
    )
    recorder = CompileAttachRecorder(
        journal,
        expected_solution_digest=str(selection["baseline_incumbent_sha256"]),
        require_model_evidence=bool(getattr(hooks, "requires_model_evidence", False)),
    )
    outcome: ArmOutcome | None = None
    failure: BaseException | None = None
    started_ns = time.monotonic_ns()
    try:
        with _arm_environment(attempt_dir, seed=int(selection["seed"])):
            context = ArmContext(
                attempt_dir=attempt_dir,
                enabled_families=tuple(selection["enabled_families"]),
                ledger=ledger,
                manifest=manifest,
                repository_root=Path(selection["repository_root"]),
                selection=selection,
                workers=1,
            )
            if os.environ.get(ATTACH_ENV) is not None:
                raise RunnerError("attach environment leaked into construction")
            runtime = hooks.construct(context)
            if os.environ.get(ATTACH_ENV) is not None:
                raise RunnerError("arm construction mutated the attach environment")
            os.environ[ATTACH_ENV] = "1"
            outcome = _validate_outcome(hooks.run_attach_phase(runtime, context, recorder))
            if os.environ.get(ATTACH_ENV) != "1":
                raise RunnerError("arm hook changed the enabled attach environment")
            recorder.finalize()
    except BaseException as exc:
        failure = exc
    finally:
        try:
            ledger.seal(
                {
                    "runner_completed": failure is None,
                    "slot": selection["slot"],
                }
            )
        except BaseException as exc:
            failure = failure or exc
        if failure is None:
            try:
                journal.seal()
            except BaseException as exc:
                failure = exc
        else:
            journal.abort()

    if failure is not None:
        failure_record = {
            "authorizations": {
                "global_claim_authorized": False,
                "mathematical_claim_authorized": False,
                "organic_runtime_effect_authorized": False,
                "production_certified_authorized": False,
            },
            "error": f"{type(failure).__name__}: {failure}",
            "schema_version": RESULT_SCHEMA,
            "selection_identity": authority_identities["selection"],
            "status": "CREDIBILITY_INCOMPLETE",
        }
        _write_exclusive(
            attempt_dir / "failure.json",
            canonical_json(failure_record),
            label="organic arm failure record",
        )
        if isinstance(failure, RunnerError):
            raise failure
        raise RunnerError("organic arm hook failed closed") from failure

    if outcome is None:  # pragma: no cover - guarded by failure/outcome flow
        raise RunnerError("organic arm outcome is absent")
    ledger_result = read_segment(ledger.path)
    if ledger_result.status != "complete":
        raise RunnerError("cut ledger is not a complete sealed segment")
    journal_events, journal_identity = _read_journal(journal.path)
    cut_activity = _join_ledger_and_journal(
        ledger_result.events,
        journal_events,
        enabled_families=list(selection["enabled_families"]),
    )
    if recorder.compiled_count != cut_activity["compiled"]:
        raise RunnerError("in-memory and replayed CompiledCut counts differ")
    journal_counts = _event_counts(journal_events)
    if recorder.hook_count != journal_counts.get("ATTACH_HOOK_BEGIN", 0) or recorder.hook_count != journal_counts.get(
        "ATTACH_HOOK_END", 0
    ):
        raise RunnerError("attach-hook journal entry/exit counts differ")
    ledger_snapshot = snapshot_regular(ledger.path, label="cut ledger segment")
    if outcome.raw_incumbent is None:
        incumbent_export: dict[str, object] = {
            "incumbent_identity": None,
            "present": False,
            "solution_vector_identity": None,
        }
    else:
        incumbent_export = {
            "incumbent_identity": _write_exclusive(
                attempt_dir / "raw-incumbent.json",
                canonical_json(dict(outcome.raw_incumbent)),
                label="raw incumbent export",
            ),
            "present": True,
            "solution_vector_identity": _write_exclusive(
                attempt_dir / "raw-solution-vector.json",
                canonical_json(list(outcome.raw_solution_vector or ())),
                label="raw solution-vector export",
            ),
        }
    result = {
        "arm": selection["arm"],
        "authority_identities": authority_identities,
        "authorizations": {
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "organic_runtime_effect_authorized": False,
            "production_certified_authorized": False,
        },
        "campaign_id": selection["campaign_id"],
        "controller_terminal": dict(outcome.raw_controller_terminal),
        "cut_activity": cut_activity,
        "enabled_families": list(selection["enabled_families"]),
        "evidence": {
            "compile_attach_journal_identity": journal_identity,
            "cut_ledger_identity": ledger_snapshot.identity,
            "cut_ledger_status": ledger_result.status,
            "journal_event_counts": journal_counts,
            "ledger_event_counts": _event_counts(ledger_result.events),
        },
        "fresh_process_required": True,
        "incumbent_export": incumbent_export,
        "raw_metrics": dict(outcome.raw_metrics),
        "raw_proof_summary": dict(outcome.raw_proof_summary),
        "raw_solver_status": outcome.raw_solver_status,
        "runtime_wall_monotonic_ns": time.monotonic_ns() - started_ns,
        "schema_version": RESULT_SCHEMA,
        "selection_nonce": selection["selection_nonce"],
        "slot": selection["slot"],
        "status": "RAW_ARM_OBSERVATION_COMPLETE",
        "workers": 1,
    }
    result_identity = _write_exclusive(
        attempt_dir / "result.json",
        canonical_json(result),
        label="organic arm result",
    )
    return {
        **result,
        "result_identity": result_identity,
    }


_PUBLIC_RUN_STARTED = False


@dataclass
class _ProductionRuntime:
    controller: Any
    master: Any


def _master_solve_history_item(
    *,
    ordinal: int,
    requested_time_limit_seconds: object,
    last_solve: Mapping[str, Any],
) -> dict[str, object]:
    if type(requested_time_limit_seconds) not in {int, float} or requested_time_limit_seconds <= 0:
        raise RunnerError("master solve lacked a positive requested time limit")
    return {
        "binary_propagations": int(last_solve.get("binary_propagations", 0)),
        "branches": int(last_solve.get("branches", 0)),
        "conflicts": int(last_solve.get("conflicts", 0)),
        "deterministic_time": float(last_solve.get("deterministic_time", 0.0)),
        "integer_propagations": int(last_solve.get("integer_propagations", 0)),
        "ordinal": ordinal,
        "requested_time_limit_seconds": float(requested_time_limit_seconds),
        "status": str(last_solve.get("status", "")),
        "user_time": float(last_solve.get("user_time", 0.0)),
        "wall_time": float(last_solve.get("wall_time", 0.0)),
    }


def _controller_terminal_record(
    *,
    controller_status: str,
    proof_summary: Mapping[str, Any],
    master_last_solve: Mapping[str, Any],
    master_solve_history: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    if controller_status not in CONTROLLER_STATUSES:
        raise RunnerError("controller returned an unsupported terminal status")
    budget = EXPERIMENT_CONTRACT["budget"]
    evidence: dict[str, object] = {
        "internal_budget_reached": False,
        "kind": "none",
        "limit": None,
        "observed": {},
    }
    if controller_status in {"UNKNOWN", "UNPROVEN"}:
        if (
            proof_summary.get("master_status") == "MAX_ITERATIONS"
            and proof_summary.get("benders_iterations") == budget["max_iterations"]
        ):
            evidence = {
                "internal_budget_reached": True,
                "kind": "max_iterations",
                "limit": budget["max_iterations"],
                "observed": {
                    "benders_iterations": proof_summary["benders_iterations"],
                    "master_status": "MAX_ITERATIONS",
                },
            }
        elif proof_summary.get("binding_status") == "TIMEOUT":
            evidence = {
                "internal_budget_reached": True,
                "kind": "binding_seconds",
                "limit": budget["binding_seconds"],
                "observed": {"binding_status": "TIMEOUT"},
            }
        elif proof_summary.get("routing_status") == "TIMEOUT":
            evidence = {
                "internal_budget_reached": True,
                "kind": "routing_seconds",
                "limit": budget["routing_seconds"],
                "observed": {"routing_status": "TIMEOUT"},
            }
        elif master_solve_history:
            last = master_solve_history[-1]
            master_limit = float(budget["master_seconds"])
            if (
                proof_summary.get("master_status") == "UNKNOWN"
                and last.get("status") == "UNKNOWN"
                and float(last.get("requested_time_limit_seconds", -1)) == master_limit
                and float(last.get("wall_time", -1)) >= master_limit * 0.99
            ):
                evidence = {
                    "internal_budget_reached": True,
                    "kind": "master_seconds",
                    "limit": budget["master_seconds"],
                    "observed": {
                        "master_status": "UNKNOWN",
                        "solver_status": "UNKNOWN",
                        "wall_time": last["wall_time"],
                    },
                }
    record = {
        "budget_censor_evidence": evidence,
        "controller_completed": True,
        "controller_status": controller_status,
        "cumulative_deterministic_time": sum(float(item["deterministic_time"]) for item in master_solve_history),
        "master_last_solve": _json_projection(
            master_last_solve,
            "controller master last solve",
        ),
        "master_solve_history": [
            _json_projection(item, "controller master solve history") for item in master_solve_history
        ],
        "schema_version": CONTROLLER_TERMINAL_SCHEMA,
    }
    _validate_controller_terminal(record)
    return record


class ProductionArmHooks:
    """Lazy production adapter; importing this class does not run a solver."""

    requires_model_evidence = True

    @staticmethod
    def _export_model(model: Any, path: Path) -> dict[str, object]:
        if os.path.lexists(path):
            raise RunnerError("attach model evidence path already exists")
        exported = model.export_to_file(str(path))
        if exported is not True:
            raise RunnerError("official binary attach-model export failed")
        return snapshot_regular(
            path,
            label="attach model evidence",
            limit=2 * 1024**3,
        ).identity

    def construct(self, context: ArmContext) -> object:
        if os.environ.get(ATTACH_ENV) is not None:
            raise RunnerError("production construction observed attach env")
        parameters = _runtime_parameters(context.manifest["runtime_parameters"])
        os.environ["EXACT_B1_BINDING_ALT_CAP"] = str(parameters["binding_alt_cap"])
        if str(context.repository_root) not in sys.path:
            sys.path.insert(0, str(context.repository_root))
        from src.models.cut_manager import CutManager
        from src.models.master_model import MasterPlacementModel
        from src.search.benders_loop import ExactSearchSession, LBBDController

        session = ExactSearchSession.create(
            context.repository_root,
            solve_mode="certified_exact",
        )
        master = MasterPlacementModel.from_exact_core(
            session.core,
            ghost_rect=tuple(parameters["ghost_rect"]),
        )
        controller = LBBDController(
            master=master,
            cut_manager=CutManager(
                checkpoint_dir=context.attempt_dir / "checkpoint",
                solve_mode="certified_exact",
            ),
            project_root=context.repository_root,
            solve_mode="certified_exact",
            master_seconds=float(parameters["master_seconds"]),
            binding_seconds=float(parameters["binding_seconds"]),
            routing_seconds=float(parameters["routing_seconds"]),
            max_iterations=int(parameters["max_iterations"]),
            artifact_hashes=session.artifact_hashes,
            session=session,
            enabled_cut_families=context.enabled_families,
            cut_ledger=context.ledger,
        )
        if os.environ.get(ATTACH_ENV) is not None:
            raise RunnerError("production controller construction leaked attach env")
        return _ProductionRuntime(
            controller=controller,
            master=master,
        )

    def run_attach_phase(
        self,
        runtime: object,
        context: ArmContext,
        recorder: CompileAttachRecorder,
    ) -> ArmOutcome:
        if type(runtime) is not _ProductionRuntime:
            raise RunnerError("production runtime type drifted")
        if os.environ.get(ATTACH_ENV) != "1":
            raise RunnerError("production attach phase lacks attach env")
        import src.cuts.typed_platform as typed_platform

        real_validate = typed_platform.validate_and_compile_cut
        production_attach_entry = getattr(
            runtime.controller,
            "_maybe_attach_framework_cuts",
        )
        real_master_solve = runtime.master.solve
        master_solve_history: list[dict[str, object]] = []

        def observed_master_solve(*args: Any, **kwargs: Any) -> Any:
            requested = kwargs.get("time_limit_seconds")
            if requested is None and args:
                requested = args[0]
            returned = real_master_solve(*args, **kwargs)
            last_solve = dict((runtime.master.build_stats or {}).get("last_solve", {}))
            master_solve_history.append(
                _master_solve_history_item(
                    ordinal=len(master_solve_history) + 1,
                    requested_time_limit_seconds=requested,
                    last_solve=last_solve,
                )
            )
            return returned

        def observed_validate(envelope: Any, snapshot: Any, registry: Any) -> Any:
            result = real_validate(envelope, snapshot, registry)
            if type(result) is typed_platform.CompiledCut:
                recorder.record_compiled_cut(result)
            return result

        def observed_attach(
            *,
            trigger: str,
            iteration: int,
            solution: Mapping[str, object] | None = None,
        ) -> int:
            if solution is None:
                raise RunnerError("production attach hook lacked the incumbent needed for replay")
            with recorder.attach_hook(
                trigger=trigger,
                iteration=iteration,
                solution=solution,
            ) as completion:
                solver = getattr(runtime.master, "_solver", None)
                if solver is None:
                    raise RunnerError("production attach hook lacks its pre-injection solver response")
                solution_vector = [int(value) for value in solver.ResponseProto().solution]
                if len(solution_vector) != len(runtime.master.model.Proto().variables):
                    raise RunnerError("pre-injection response length differs from the live model")
                evidence_prefix = context.attempt_dir / "runtime" / f"hook-{completion.hook_id:04d}"
                solution_identity = _write_exclusive(
                    evidence_prefix.with_name(evidence_prefix.name + "-solution-vector.json"),
                    canonical_json(solution_vector),
                    label="attach solution-vector evidence",
                )
                pre_model_identity = self._export_model(
                    runtime.master.model,
                    evidence_prefix.with_name(evidence_prefix.name + "-pre-model.pb"),
                )
                attached = production_attach_entry(
                    trigger=trigger,
                    iteration=iteration,
                    solution=solution,
                )
                post_model_identity = self._export_model(
                    runtime.master.model,
                    evidence_prefix.with_name(evidence_prefix.name + "-post-model.pb"),
                )
                recorder.record_attach_model_evidence(
                    completion.hook_id,
                    pre_model_identity=pre_model_identity,
                    post_model_identity=post_model_identity,
                    solution_vector_identity=solution_identity,
                )
                completion.returned(attached)
                return attached

        typed_platform.validate_and_compile_cut = observed_validate
        runtime.controller._maybe_attach_framework_cuts = observed_attach
        runtime.master.solve = observed_master_solve
        try:
            status, returned_solution = runtime.controller.run_with_status()
        finally:
            typed_platform.validate_and_compile_cut = real_validate
            del runtime.controller._maybe_attach_framework_cuts
            runtime.master.solve = real_master_solve

        solver = getattr(runtime.master, "_solver", None)
        response: dict[str, object] = {}
        solution_vector: list[int] | None = None
        incumbent: Mapping[str, object] | None = None
        if solver is not None:
            proto = solver.ResponseProto()
            for field in (
                "best_objective_bound",
                "deterministic_time",
                "num_binary_propagations",
                "num_booleans",
                "num_branches",
                "num_conflicts",
                "num_integer_propagations",
                "objective_value",
                "user_time",
                "wall_time",
            ):
                response[field] = _json_projection(
                    getattr(proto, field),
                    f"solver response {field}",
                )
            if proto.solution:
                solution_vector = [int(value) for value in proto.solution]
                incumbent = returned_solution or runtime.master.extract_solution()
                if not incumbent:
                    raise RunnerError("solver response has a solution vector but no incumbent")
        last_solve = dict((runtime.master.build_stats or {}).get("last_solve", {}))
        proof_summary = _json_projection(
            runtime.controller.last_proof_summary or {},
            "controller proof summary",
        )
        if type(proof_summary) is not dict:
            raise RunnerError("controller proof summary is not a JSON object")
        controller_terminal = _controller_terminal_record(
            controller_status=str(status),
            proof_summary=proof_summary,
            master_last_solve=last_solve,
            master_solve_history=master_solve_history,
        )
        return ArmOutcome(
            raw_controller_terminal=controller_terminal,
            raw_incumbent=incumbent,
            raw_metrics={
                "attach_last": _json_projection(
                    (runtime.master.build_stats or {}).get("cut_framework_attach_last"),
                    "attach_last",
                ),
                "has_returned_solution": returned_solution is not None,
                "solver_response": response,
            },
            raw_proof_summary={
                "controller_last_proof_summary": proof_summary,
                "master_last_solve": _json_projection(
                    last_solve,
                    "master last solve",
                ),
            },
            raw_solution_vector=solution_vector,
            raw_solver_status=str(status),
        )


def run_selected_arm(selection_path: Path | str) -> dict[str, object]:
    """Public one-shot entry owned by the selected prod-scale unit payload."""

    return _run_with_hooks(
        Path(selection_path),
        ProductionArmHooks(),
        enforce_single_process_use=True,
        require_prod_scale_unit_context=True,
        retain_prod_scale_locks=True,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_selected_arm(args.selection)
    except RunnerError as exc:
        print(f"FAIL_CLOSED: {exc}", file=sys.stderr)
        return 2
    summary = {
        "cut_activity": result["cut_activity"],
        "result_identity": result["result_identity"],
        "slot": result["slot"],
        "status": result["status"],
    }
    print(canonical_json(summary).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
