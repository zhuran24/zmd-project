#!/usr/bin/env python3
"""Publish and replay the AB16 child of one existing Gate-1-v4 campaign.

This tool never creates a campaign root, authority package, Gate-1 selection,
unit, arm, or solver process.  It consumes the single campaign root produced
by ``campaign_authority_v4.py`` and permits the following no-overwrite sequence:

1. a fresh, same-campaign Gate-1 continuation and the package-pinned baseline
   admission authorize publication of the runner-exact organic manifest;
2. a non-launching suite selection freezes that manifest and launch order;
3. each arm independently passes a current epoch/package/HEAD/input/resource
   preflight before the authority creates its attempt directory, copies the
   non-authorizing pre-run bytes, and publishes the runner-exact selection;
4. each selected arm must be consumed as a credible terminal before the next
   slot, while any credibility failure writes an immutable immediate stop.

The selected campaign package must already contain every AB16 tool/input byte,
the distinct Gate-A/Gate-B records, strict inputs, legacy provenance, and the
manager/boot epoch authority.  A historical Gate-1 package with
``PACKAGE_SEAL_DRIFT`` cannot pass this consumer.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any, Mapping, Sequence


SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
HEAD_RE = re.compile(r"[0-9a-f]{40}\Z")

MANIFEST_SCHEMA = "noncert-cuts-ab16-organic-manifest-v2"
SUITE_SELECTION_SCHEMA = "noncert-cuts-ab16-suite-selection-v2"
ARM_SELECTION_SCHEMA = "noncert-cuts-ab16-organic-arm-selection-v1"
PRE_RUN_AUTHORITY_SCHEMA = "noncert-cuts-ab16-organic-pre-run-authority-v2"
ARM_CONSUMPTION_SCHEMA = "noncert-cuts-ab16-organic-arm-consumption-v2"
CAMPAIGN_STOP_SCHEMA = "noncert-cuts-ab16-immediate-stop-v1"
PATH_PREREGISTRATION_SCHEMA = "noncert-cuts-ab16-path-preregistration-v4"
GATE_A_SCHEMA = "noncert-cuts-ab16-bootstrap-gate-a-receipt-v2"
GATE_B_SCHEMA = "noncert-cuts-ab16-bootstrap-gate-b-approval-v4"
GATE_B_EPOCH_SCHEMA = "noncert-cuts-ab16-gate-b-epoch-observation-v3"
FINAL_FULL_PREFLIGHT_SCHEMA = "noncert-cuts-ab16-gate-a-full-preflight-receipt-v5"
FINAL_FULL_PREFLIGHT_SCRATCH_BASENAME = "pytest-scratch"
FINAL_FULL_PREFLIGHT_BASETEMP_BASENAME = "basetemp"
FINAL_FULL_PREFLIGHT_SCRATCH_POLICY = "fresh-no-overwrite-repo-local-retained-closed-tree-v1"
FINAL_FULL_PREFLIGHT_PUBLICATION_COMMIT_SCHEMA = (
    "noncert-cuts-ab16-gate-a-preflight-publication-commit-v1"
)
REPOSITORY_SNAPSHOT_SCHEMA = "noncert-cuts-ab16-repository-snapshot-v1"
SNAPSHOT_MATERIALIZATION_SCHEMA = "noncert-cuts-ab16-repository-snapshot-materialization-v1"
EXTERNAL_PLATFORM_SCHEMA = "noncert-cuts-ab16-external-platform-assumptions-v2"
CONTINUATION_SCHEMA = "noncert-cuts-gate1-v4-continuation-authorization-v1"
BASELINE_ADMISSION_SCHEMA = "noncert-cuts-ab16-baseline-admission-v1"
COMMON_PRESTATE_SCHEMA = "noncert-cuts-ab16-common-prestate-v1"
COMMON_PRESTATE_PURPOSE = "prospective_noncert_cuts_ab16_common_prestate"
ARM_BINDING_SCHEMA = "noncert-cuts-ab16-arm-binding-v2"
ARM_BINDING_PURPOSE = "prospective_noncert_cuts_ab16_arm_binding"

CONFIGURATIONS = (
    "region-capacity",
    "shape-packing-hall",
    "power-hitting-set",
    "bundle",
)
ORDERS = ("ab", "ba")
ARMS = ("control", "treatment")
GATE1_SLOTS = (
    "q-success",
    "q-postseal-fail",
    "forced-control",
    "forced-treatment",
)

REQUIRED_PACKAGE_ROLES = frozenset(
    {
        "campaign_authority_v4.py",
        "input.ab16_gate_a_receipt.json",
        "input.ab16_gate_b_approval.json",
        "input.ab16_gate_b_epoch_observation.json",
        "input.ab16_gate_b_final_full_preflight.json",
        "input.ab16_external_platform_assumptions.json",
        "input.ab16_offline_candidate.json",
        "input.ab16_path_preregistration.json",
        "input.ab16_repository_snapshot.json",
        "input.ab16_repository_snapshot.zip",
        "input.ab16_bootstrap_manager_epoch_capture.json",
        "input.candidate_placements.json",
        "input.canonical_rules.json",
        "input.cuts_mandatory_schedule.txt",
        "input.history_freeze_manifest.json",
        "input.legacy_control_a002.json",
        "input.mandatory_instances.json",
        "input.preflight_gate.txt",
        "input.project_lock.txt",
        "system.attestor_python.bin",
        "system.busctl.bin",
        "system.git.bin",
        "system.libsystemd.bin",
        "system.python3_13.bin",
        "system.sudo.bin",
        "system.systemctl.bin",
        "system.systemd_run.bin",
        "tool.ab16_authority_v1.py",
        "tool.ab16_authority_v2.py",
        "tool.ab16_campaign_bootstrap_v1.py",
        "tool.ab16_campaign_bootstrap_v2.py",
        "tool.ab16_contract_v1.py",
        "tool.ab16_formal_campaign_v1.py",
        "tool.ab16_formal_controller_v1.py",
        "tool.ab16_formal_launch_authority_v1.py",
        "tool.ab16_formal_launch_validator_v1.py",
        "tool.ab16_formal_loader_v1.py",
        "tool.ab16_formal_orchestrator_v1.py",
        "tool.ab16_formal_success_verifier_v1.py",
        "tool.ab16_gate_b_qualification_v1.py",
        "tool.ab16_outer_closeout_state_v1.py",
        "tool.ab16_outer_guardian_v1.py",
        "tool.ab16_outer_refunit_closeout_v1.py",
        "tool.ab16_preflight_qualification_v1.py",
        "tool.ab16_pytest_collection_plugin_v1.py",
        "tool.ab16_pytest_collection_protocol_v1.py",
        "tool.ab16_terminal_gate_v1.py",
        "tool.ab16_terminal_gate_v2.py",
        "tool.baseline_admission_v1.py",
        "tool.baseline_rebuild_v1.py",
        "tool.cut_free_incumbent_replay_v1.py",
        "tool.disposable_drill_authority_v1.py",
        "tool.disposable_drill_authority_v2.py",
        "tool.disposable_drill_payload_v1.py",
        "tool.gate_a_validation_v2.py",
        "tool.gate_a_pinned_entrypoint_v2.py",
        "tool.gate_a_recovery_inputs_v1.py",
        "tool.organic_arm_runner_v1.py",
        "tool.organic_arm_replay_v1.py",
        "tool.organic_resource_lifecycle_v1.py",
        "tool.organic_resource_lifecycle_v2.py",
        "tool.organic_resource_verifier_v1.py",
        "tool.organic_resource_verifier_v2.py",
        "tool.organic_unit_orchestrator_v1.py",
        "tool.organic_unit_orchestrator_v2.py",
        "tool.systemd_unit_reference_v1.py",
        "tool.gate1_campaign_bootstrap_v4.py",
        "tool.gate1_campaign_driver_v4.py",
        "tool.gate1_campaign_execution_v4.py",
        "tool.gate1_payload_v4.py",
        "tool.gate1_unit_orchestrator_v4.py",
        "tool.independent_arithmetic_v4.py",
        "tool.manager_attestor_v4.py",
        "tool.positive_control_formal_v4.py",
        "tool.positive_control_gate_v4.py",
        "tool.positive_control_v4.py",
        "tool.resource_lifecycle_v4.py",
        "tool.resource_verifier_v4.py",
    }
)

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
        "bundle": {
            "control_enabled_families": [],
            "treatment_enabled_families": [
                "region_capacity",
                "shape_packing_hall",
                "power_hitting_set",
            ],
        },
        "power-hitting-set": {
            "control_enabled_families": [],
            "treatment_enabled_families": ["power_hitting_set"],
        },
        "region-capacity": {
            "control_enabled_families": [],
            "treatment_enabled_families": ["region_capacity"],
        },
        "shape-packing-hall": {
            "control_enabled_families": [],
            "treatment_enabled_families": ["shape_packing_hall"],
        },
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
    "order": [
        f"{configuration}-{order}-{arm}"
        for configuration in CONFIGURATIONS
        for order, arms in (
            ("ab", ("control", "treatment")),
            ("ba", ("treatment", "control")),
        )
        for arm in arms
    ],
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

IMMEDIATE_STOP_POLICY: dict[str, object] = {
    "classification": "CREDIBILITY_INCOMPLETE",
    "no_cross_epoch_or_run_splicing": True,
    "preserve_consumed_arm": True,
    "selection_after_launch_failure": "ARM_CONSUMED",
    "selection_before_launch_failure": "DO_NOT_LAUNCH",
    "stop_before_next_arm_on": [
        "AUTHORITY_OR_TOOL_DRIFT",
        "MANAGER_OR_BOOT_EPOCH_DRIFT",
        "RESOURCE_OR_LIMIT_DRIFT",
        "LEDGER_OR_REPLAY_INCOMPLETE",
        "OUTER_TIMEOUT_OOM_KILL_OR_CRASH",
        "PAIR_COMPARABILITY_FAILURE",
    ],
}


class AuthorityError(RuntimeError):
    """Fail-closed authority error with a stable code."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class FormalRuntimeBoundary:
    """Public package-replayed view consumed by the existing closeout owner."""

    campaign: Path
    context: Mapping[str, Any]
    formal_dir: Path
    preregistration: Mapping[str, Any]
    root: Mapping[str, Any]


@dataclass(frozen=True)
class Snapshot:
    path: Path
    data: bytes
    device: int
    inode: int
    mode: int
    size_bytes: int
    sha256: str


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _assert_no_symlink_chain(path: Path | str, *, include_leaf: bool = True) -> None:
    absolute = _absolute(path)
    parts = absolute.parts
    cursor = Path(parts[0])
    limit = len(parts) if include_leaf else len(parts) - 1
    for part in parts[1:limit]:
        cursor /= part
        try:
            mode = os.lstat(cursor).st_mode
        except FileNotFoundError as exc:
            raise AuthorityError("PATH_MISSING", str(cursor)) from exc
        if stat.S_ISLNK(mode):
            raise AuthorityError("SYMLINK_REJECTED", str(cursor))


def snapshot_regular(path: Path | str) -> Snapshot:
    absolute = _absolute(path)
    _assert_no_symlink_chain(absolute, include_leaf=False)
    if not hasattr(os, "O_NOFOLLOW"):
        raise AuthorityError("NOFOLLOW_UNAVAILABLE", "O_NOFOLLOW is required")
    try:
        descriptor = os.open(
            absolute,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
    except OSError as exc:
        raise AuthorityError("INPUT_OPEN_FAILED", f"{absolute}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise AuthorityError("INPUT_NOT_REGULAR", str(absolute))
        chunks: list[bytes] = []
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    stable = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
    data = b"".join(chunks)
    if any(getattr(before, field) != getattr(after, field) for field in stable) or len(data) != before.st_size:
        raise AuthorityError("SAME_FD_INPUT_DRIFT", str(absolute))
    return Snapshot(
        path=absolute,
        data=data,
        device=int(before.st_dev),
        inode=int(before.st_ino),
        mode=stat.S_IMODE(before.st_mode),
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def detached_identity(snapshot: Snapshot) -> dict[str, object]:
    return {
        "path": str(snapshot.path),
        "sha256": snapshot.sha256,
        "size_bytes": snapshot.size_bytes,
    }


def full_identity(snapshot: Snapshot) -> dict[str, object]:
    return {
        "device": snapshot.device,
        "inode": snapshot.inode,
        "mode": snapshot.mode,
        **detached_identity(snapshot),
    }


def _pairs_without_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuthorityError("JSON_DUPLICATE_KEY", key)
        result[key] = value
    return result


def strict_loads(data: bytes, label: str, *, canonical: bool = True) -> Any:
    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_pairs_without_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(AuthorityError("JSON_CONSTANT_INVALID", token)),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthorityError("JSON_INVALID", label) from exc
    if canonical and canonical_json(value) != data:
        raise AuthorityError("JSON_NOT_CANONICAL", label)
    return value


def _record(snapshot: Snapshot, label: str, *, canonical: bool = True) -> Mapping[str, Any]:
    value = strict_loads(snapshot.data, label, canonical=canonical)
    if type(value) is not dict:
        raise AuthorityError("JSON_RECORD_INVALID", label)
    return value


def _unterminated_record(snapshot: Snapshot, label: str) -> Mapping[str, Any]:
    value = _record(snapshot, label, canonical=False)
    if canonical_json(value)[:-1] != snapshot.data:
        raise AuthorityError("JSON_NOT_CANONICAL", label)
    return value


def _exact_keys(value: object, keys: set[str], label: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise AuthorityError("SCHEMA_KEYS_INVALID", label)
    return value


def _write_exclusive(path: Path | str, data: bytes, *, mode: int = 0o600) -> dict[str, object]:
    absolute = _absolute(path)
    if type(mode) is not int or mode not in {0o444, 0o600}:
        raise AuthorityError("OUTPUT_MODE_INVALID", str(absolute))
    parent = absolute.parent
    _assert_no_symlink_chain(parent)
    if not parent.is_dir():
        raise AuthorityError("OUTPUT_PARENT_INVALID", str(parent))
    parent_fd = os.open(parent, os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            # A requested 0444 mode is the cross-actor completion signal.  The
            # final name remains non-ready while its bytes are still mutable.
            descriptor = os.open(
                absolute.name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent_fd,
            )
        except FileExistsError as exc:
            raise AuthorityError("NO_OVERWRITE_COLLISION", str(absolute)) from exc
        try:
            view = memoryview(data)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise AuthorityError("OUTPUT_WRITE_FAILED", str(absolute))
                view = view[written:]
            os.fsync(descriptor)
            os.fchmod(descriptor, mode)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        os.close(parent_fd)
    return detached_identity(snapshot_regular(absolute))


def _mkdir_exclusive(path: Path | str) -> Path:
    absolute = _absolute(path)
    parent = absolute.parent
    _assert_no_symlink_chain(parent)
    if not parent.is_dir():
        raise AuthorityError("OUTPUT_PARENT_INVALID", str(parent))
    if absolute.exists() or absolute.is_symlink():
        raise AuthorityError("NO_OVERWRITE_COLLISION", str(absolute))
    try:
        os.mkdir(absolute, 0o700)
    except FileExistsError as exc:
        raise AuthorityError("NO_OVERWRITE_COLLISION", str(absolute)) from exc
    return absolute


def _safe_rel(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or "\\" in value or any(part in {"", ".", ".."} for part in path.parts):
        raise AuthorityError("PACKAGE_PATH_INVALID", value)
    return path.as_posix()


def _scan_package(package_dir: Path | str) -> dict[str, Snapshot]:
    root = _absolute(package_dir)
    _assert_no_symlink_chain(root)
    if not root.is_dir():
        raise AuthorityError("PACKAGE_INVALID", str(root))
    result: dict[str, Snapshot] = {}
    for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for dirname in dirnames:
            child = current_path / dirname
            rel = child.relative_to(root).as_posix()
            mode = os.lstat(child).st_mode
            if stat.S_ISLNK(mode):
                raise AuthorityError("PACKAGE_SYMLINK_REJECTED", rel)
            if dirname == "__pycache__":
                raise AuthorityError("PACKAGE_PYCACHE_REJECTED", rel)
        for filename in filenames:
            child = current_path / filename
            rel = child.relative_to(root).as_posix()
            mode = os.lstat(child).st_mode
            if stat.S_ISLNK(mode):
                raise AuthorityError("PACKAGE_SYMLINK_REJECTED", rel)
            if filename.endswith(".pyc"):
                raise AuthorityError("PACKAGE_PYCACHE_REJECTED", rel)
            result[rel] = snapshot_regular(child)
    return result


def _parse_seal(data: bytes) -> dict[str, str]:
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise AuthorityError("PACKAGE_SEAL_INVALID", "non-ASCII") from exc
    if not text or not text.endswith("\n"):
        raise AuthorityError("PACKAGE_SEAL_INVALID", "framing")
    result: dict[str, str] = {}
    for line in text.splitlines():
        if len(line) < 67 or line[64:66] != "  ":
            raise AuthorityError("PACKAGE_SEAL_INVALID", line)
        digest = line[:64]
        rel = _safe_rel(line[66:])
        if SHA256_RE.fullmatch(digest) is None or rel == "SHA256SUMS" or rel in result:
            raise AuthorityError("PACKAGE_SEAL_INVALID", line)
        result[rel] = digest
    if text != "".join(f"{result[rel]}  {rel}\n" for rel in sorted(result)):
        raise AuthorityError("PACKAGE_SEAL_INVALID", "noncanonical ordering")
    return result


def _validate_source_identity(value: object, label: str) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise AuthorityError("SOURCE_IDENTITY_INVALID", label)
    required = {"path", "sha256", "size_bytes"}
    if not required <= set(value):
        raise AuthorityError("SOURCE_IDENTITY_INVALID", label)
    if (
        type(value["path"]) is not str
        or not Path(value["path"]).is_absolute()
        or type(value["sha256"]) is not str
        or SHA256_RE.fullmatch(value["sha256"]) is None
        or type(value["size_bytes"]) is not int
        or value["size_bytes"] < 0
    ):
        raise AuthorityError("SOURCE_IDENTITY_INVALID", label)
    return value


def _package_sources(
    package_dir: Path | str,
) -> tuple[dict[str, Snapshot], Mapping[str, Any], dict[str, Mapping[str, Any]]]:
    files = _scan_package(package_dir)
    if {"SHA256SUMS", "package-manifest.json"} - set(files):
        raise AuthorityError("PACKAGE_SEAL_DRIFT", "manifest or seal missing")
    seal = _parse_seal(files["SHA256SUMS"].data)
    actual = set(files) - {"SHA256SUMS"}
    if set(seal) != actual or any(files[path].sha256 != digest for path, digest in seal.items()):
        raise AuthorityError("PACKAGE_SEAL_DRIFT", "member set or digest")
    manifest = _record(files["package-manifest.json"], "campaign package manifest")
    sources = manifest.get("external_sources")
    if type(sources) is not list:
        raise AuthorityError("PACKAGE_MANIFEST_INVALID", "external_sources")
    by_role: dict[str, Mapping[str, Any]] = {}
    for item in sources:
        record = _exact_keys(
            item,
            {"package_path", "parse_json", "role", "source_identity"},
            "package source",
        )
        role = record["role"]
        package_path = record["package_path"]
        if (
            type(role) is not str
            or not role
            or role in by_role
            or type(package_path) is not str
            or package_path not in files
            or type(record["parse_json"]) is not bool
        ):
            raise AuthorityError("PACKAGE_MANIFEST_INVALID", "source role/path")
        source = _validate_source_identity(record["source_identity"], f"package source {role}")
        current = snapshot_regular(source["path"])
        if (
            current.sha256 != source["sha256"]
            or current.size_bytes != source["size_bytes"]
            or files[package_path].data != current.data
        ):
            raise AuthorityError("PACKAGE_SOURCE_DRIFT", role)
        by_role[role] = record
    if set(by_role) != REQUIRED_PACKAGE_ROLES:
        missing = sorted(REQUIRED_PACKAGE_ROLES - set(by_role))
        extra = sorted(set(by_role) - REQUIRED_PACKAGE_ROLES)
        raise AuthorityError(
            "AB16_PACKAGE_ROLE_SET_DRIFT",
            f"missing={missing}; extra={extra}",
        )
    return files, manifest, by_role


def _load_module(snapshot: Snapshot, name: str) -> ModuleType:
    namespace = ModuleType(name)
    namespace.__file__ = str(snapshot.path)
    namespace.__package__ = None
    sys.modules[name] = namespace
    try:
        code = compile(snapshot.data, str(snapshot.path), "exec", dont_inherit=True)
        exec(code, namespace.__dict__, namespace.__dict__)
    except Exception as exc:
        sys.modules.pop(name, None)
        raise AuthorityError("PINNED_TOOL_LOAD_FAILED", name) from exc
    return namespace


def _source_snapshot(
    files: Mapping[str, Snapshot],
    sources: Mapping[str, Mapping[str, Any]],
    role: str,
) -> Snapshot:
    record = sources[role]
    packaged = files[record["package_path"]]
    source = _validate_source_identity(record["source_identity"], f"package source {role}")
    current = snapshot_regular(source["path"])
    if (
        current.sha256 != source["sha256"]
        or current.size_bytes != source["size_bytes"]
        or current.data != packaged.data
    ):
        raise AuthorityError("PACKAGE_SOURCE_DRIFT", role)
    return current


def _detached_from_source(value: Mapping[str, Any]) -> dict[str, object]:
    return {
        "path": value["path"],
        "sha256": value["sha256"],
        "size_bytes": value["size_bytes"],
    }


def _mode_identity(snapshot: Snapshot) -> dict[str, object]:
    return {"mode": snapshot.mode, **detached_identity(snapshot)}


def validate_repository_snapshot_manifest(value: object) -> Mapping[str, Any]:
    """Validate the finite fixed-HEAD source set without trusting its builder."""

    record = _exact_keys(
        value,
        set(
            "archive_descriptor authority_scope import_mode member_count members ordered_member_digest repository_head "
            "repository_tree schema_version total_bytes".split()
        ),
        "AB16 repository snapshot manifest",
    )
    members = record["members"]
    if type(members) is not list or not members:
        raise AuthorityError("REPOSITORY_SNAPSHOT_INVALID", "empty or malformed member list")
    paths: set[str] = set()
    collision_keys: set[str] = set()
    git_paths: list[str] = []
    overlay_count = 0
    total_bytes = 0
    for ordinal, item in enumerate(members):
        if type(item) is not dict:
            raise AuthorityError("REPOSITORY_SNAPSHOT_INVALID", f"member {ordinal}")
        kind = item.get("source_kind")
        keys = (
            {"git_blob_oid", "git_mode", "materialized_mode", "path", "raw_sha256", "size_bytes", "source_kind"}
            if kind == "git_blob"
            else set("materialized_mode package_role path raw_sha256 size_bytes source_kind".split())
        )
        member = _exact_keys(item, keys, f"AB16 repository snapshot member {ordinal}")
        path = member["path"]
        if type(path) is not str:
            raise AuthorityError("REPOSITORY_SNAPSHOT_INVALID", f"member path {ordinal}")
        try:
            path = _safe_rel(path)
        except AuthorityError as exc:
            raise AuthorityError("REPOSITORY_SNAPSHOT_INVALID", f"member path {ordinal}") from exc
        collision = unicodedata.normalize("NFC", path).casefold()
        if (
            path != member["path"]
            or path in paths
            or collision in collision_keys
            or unicodedata.normalize("NFC", path) != path
            or type(member["raw_sha256"]) is not str
            or SHA256_RE.fullmatch(member["raw_sha256"]) is None
            or type(member["size_bytes"]) is not int
            or member["size_bytes"] < 0
        ):
            raise AuthorityError("REPOSITORY_SNAPSHOT_INVALID", f"member identity {path}")
        paths.add(path)
        collision_keys.add(collision)
        total_bytes += member["size_bytes"]
        if kind == "git_blob":
            if (
                type(member["git_blob_oid"]) is not str
                or HEAD_RE.fullmatch(member["git_blob_oid"]) is None
                or member["git_mode"] not in {"100644", "100755"}
                or member["materialized_mode"] != (0o555 if member["git_mode"] == "100755" else 0o444)
            ):
                raise AuthorityError("REPOSITORY_SNAPSHOT_INVALID", f"tracked member {path}")
            git_paths.append(path)
        elif kind == "package_overlay":
            overlay_count += 1
            if (
                path != "data/preprocessed/candidate_placements.json"
                or ordinal != len(members) - 1
                or member["package_role"] != "input.candidate_placements.json"
                or member["materialized_mode"] != 0o444
            ):
                raise AuthorityError("REPOSITORY_SNAPSHOT_INVALID", "candidate overlay")
        else:
            raise AuthorityError("REPOSITORY_SNAPSHOT_INVALID", f"source kind {kind!r}")
    archive = _exact_keys(
        record["archive_descriptor"],
        {"package_role", "sha256", "size_bytes"},
        "AB16 repository snapshot archive",
    )
    if (
        overlay_count != 1
        or git_paths != sorted(git_paths, key=lambda path: path.encode("utf-8"))
        or record["schema_version"] != REPOSITORY_SNAPSHOT_SCHEMA
        or record["authority_scope"] != "AB16_RESEARCH_ONLY"
        or record["import_mode"] != "ordinary_pathfinder"
        or type(record["repository_head"]) is not str
        or HEAD_RE.fullmatch(record["repository_head"]) is None
        or type(record["repository_tree"]) is not str
        or HEAD_RE.fullmatch(record["repository_tree"]) is None
        or type(record["member_count"]) is not int
        or record["member_count"] != len(members)
        or type(record["total_bytes"]) is not int
        or record["total_bytes"] != total_bytes
        or type(record["ordered_member_digest"]) is not str
        or record["ordered_member_digest"] != hashlib.sha256(canonical_json(members)).hexdigest()
        or archive["package_role"] != "input.ab16_repository_snapshot.zip"
        or type(archive["sha256"]) is not str
        or SHA256_RE.fullmatch(archive["sha256"]) is None
        or type(archive["size_bytes"]) is not int
        or archive["size_bytes"] <= 0
    ):
        raise AuthorityError("REPOSITORY_SNAPSHOT_INVALID", "manifest aggregate")
    return record


def _bootstrap_literal_values(
    files: Mapping[str, Snapshot],
    sources: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    """Read the selected literal bytes from the sealed bootstrap source without executing it."""

    snapshot = _source_snapshot(files, sources, "tool.ab16_campaign_bootstrap_v2.py")
    try:
        tree = ast.parse(snapshot.data, filename=str(snapshot.path), mode="exec")
    except (SyntaxError, ValueError) as exc:
        raise AuthorityError("REPOSITORY_SNAPSHOT_BINDING_DRIFT", "bootstrap source parse") from exc
    names = {
        "FORMAL_LAUNCH_OWNER_DRIVER_V1",
        "GATE_B_OWNER_DRIVER_V1",
        "OWNER_OEXCL_PUBLISH_V1",
        "SELECTED_BYTE_LAUNCH_V1",
    }

    def static_string(node: ast.AST) -> str:
        if isinstance(node, ast.Constant) and type(node.value) is str:
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return static_string(node.left) + static_string(node.right)
        if (
            isinstance(node, ast.Call)
            and not node.args
            and not node.keywords
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "strip"
        ):
            return static_string(node.func.value).strip()
        raise ValueError("not one supported static string expression")

    values: dict[str, str] = {}
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        selected = [target.id for target in targets if isinstance(target, ast.Name) and target.id in names]
        if not selected:
            continue
        try:
            value = static_string(statement.value)
        except ValueError as exc:
            raise AuthorityError(
                "REPOSITORY_SNAPSHOT_BINDING_DRIFT",
                f"bootstrap literal {selected[0]} is not static",
            ) from exc
        if type(value) is not str:
            raise AuthorityError(
                "REPOSITORY_SNAPSHOT_BINDING_DRIFT",
                f"bootstrap literal {selected[0]} type",
            )
        for name in selected:
            if name in values:
                raise AuthorityError(
                    "REPOSITORY_SNAPSHOT_BINDING_DRIFT",
                    f"bootstrap literal {name} duplicated",
                )
            values[name] = value
    if set(values) != names:
        raise AuthorityError("REPOSITORY_SNAPSHOT_BINDING_DRIFT", "bootstrap literal set")
    return values


def _bootstrap_literal_identities(
    files: Mapping[str, Snapshot],
    sources: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, object]]:
    values = _bootstrap_literal_values(files, sources)
    return {
        name: {
            "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
            "size_bytes": len(value.encode("utf-8")),
        }
        for name, value in values.items()
    }


def _replay_repository_snapshot(
    *,
    directory: Path,
    root: Mapping[str, Any],
    files: Mapping[str, Snapshot],
    sources: Mapping[str, Mapping[str, Any]],
) -> dict[str, object]:
    manifest_snapshot = files[sources["input.ab16_repository_snapshot.json"]["package_path"]]
    archive_snapshot = files[sources["input.ab16_repository_snapshot.zip"]["package_path"]]
    platform_snapshot = files[sources["input.ab16_external_platform_assumptions.json"]["package_path"]]
    manifest = validate_repository_snapshot_manifest(
        _record(manifest_snapshot, "AB16 repository snapshot manifest")
    )
    expected_authority = directory / "campaign-authority" / "source-snapshot-a001"
    snapshot_root = expected_authority / "repository"
    receipt_snapshot = _replay_detached(
        root["strict_inputs"].get("ab16_repository_snapshot_materialization"),
        "AB16 repository snapshot materialization",
    )
    receipt = _exact_keys(
        _record(receipt_snapshot, "AB16 repository snapshot materialization"),
        set(
            "authority_scope candidate_identity created_at_utc import_mode member_count ordered_member_digest "
            "package_id repository_head repository_tree schema_version snapshot_archive_identity "
            "snapshot_manifest_identity snapshot_root status total_bytes".split()
        ),
        "AB16 repository snapshot materialization",
    )
    manifest_identity = detached_identity(manifest_snapshot)
    archive_identity = detached_identity(archive_snapshot)
    candidate_snapshot = files[sources["input.candidate_placements.json"]["package_path"]]
    overlay = manifest["members"][-1]
    if (
        receipt_snapshot.path != expected_authority / "materialization-receipt.json"
        or manifest["archive_descriptor"]
        != {
            "package_role": "input.ab16_repository_snapshot.zip",
            "sha256": archive_identity["sha256"],
            "size_bytes": archive_identity["size_bytes"],
        }
        or root["strict_inputs"].get("ab16_repository_snapshot") != manifest_identity
        or root["strict_inputs"].get("ab16_repository_snapshot_archive") != archive_identity
        or root["strict_inputs"].get("ab16_external_platform_assumptions") != detached_identity(platform_snapshot)
        or receipt["schema_version"] != SNAPSHOT_MATERIALIZATION_SCHEMA
        or receipt["status"] != "PASS"
        or receipt["authority_scope"] != "AB16_RESEARCH_ONLY"
        or receipt["import_mode"] != "ordinary_pathfinder"
        or receipt["package_id"] != root["package"]["package_id"]
        or receipt["repository_head"] != root["repository_head"]
        or receipt["repository_head"] != manifest["repository_head"]
        or receipt["repository_tree"] != manifest["repository_tree"]
        or receipt["snapshot_archive_identity"] != archive_identity
        or receipt["snapshot_manifest_identity"] != manifest_identity
        or receipt["snapshot_root"] != str(snapshot_root)
        or receipt["member_count"] != manifest["member_count"]
        or receipt["total_bytes"] != manifest["total_bytes"]
        or receipt["ordered_member_digest"] != manifest["ordered_member_digest"]
        or receipt["candidate_identity"] != detached_identity(candidate_snapshot)
        or overlay["raw_sha256"] != candidate_snapshot.sha256
        or overlay["size_bytes"] != candidate_snapshot.size_bytes
        or type(receipt["created_at_utc"]) is not str
    ):
        raise AuthorityError("REPOSITORY_SNAPSHOT_BINDING_DRIFT", "package/root/materialization join")
    platform = _exact_keys(
        _record(platform_snapshot, "AB16 external platform assumptions"),
        set(
            "authority_scope cpython_version dual_holder_survival external_platform_trust "
            "formal_launch_owner_driver gate_b_owner_driver mechanical_oexcl_publisher "
            "ortools_version protobuf_version python_identity repository_head schema_version "
            "selected_byte_launch".split()
        ),
        "AB16 external platform assumptions",
    )
    literal_identities = _bootstrap_literal_identities(files, sources)
    dual_holder = _exact_keys(
        platform["dual_holder_survival"],
        {
            "assumption_id",
            "reboot_or_power_loss_during_heavy_runtime_excluded",
            "simultaneous_guardian_supervisor_death_excluded",
            "single_holder_death_must_be_contained",
        },
        "AB16 dual-holder platform assumption",
    )
    selected_launch = _exact_keys(
        platform["selected_byte_launch"],
        {
            "direct_fd_map",
            "execution_strategy",
            "literal_identity",
            "systemd_fd_map",
            "systemd_fd_names",
        },
        "AB16 selected-byte launch",
    )
    python_snapshot = _replay_detached(root["authority_tools"].get("python3_13"), "AB16 CPython")
    if (
        platform["schema_version"] != EXTERNAL_PLATFORM_SCHEMA
        or platform["authority_scope"] != "AB16_RESEARCH_ONLY"
        or platform["cpython_version"] != "3.13.13"
        or platform["repository_head"] != root["repository_head"]
        or platform["python_identity"] != _mode_identity(python_snapshot)
        or platform["formal_launch_owner_driver"]
        != literal_identities["FORMAL_LAUNCH_OWNER_DRIVER_V1"]
        or platform["gate_b_owner_driver"] != literal_identities["GATE_B_OWNER_DRIVER_V1"]
        or platform["mechanical_oexcl_publisher"] != literal_identities["OWNER_OEXCL_PUBLISH_V1"]
        or selected_launch["literal_identity"] != literal_identities["SELECTED_BYTE_LAUNCH_V1"]
        or selected_launch["execution_strategy"] != "selected-byte-python-loader-fd-v1"
        or selected_launch["direct_fd_map"] != {"authority": 5, "loader": 4, "python": 3}
        or selected_launch["systemd_fd_map"] != {"authority": 5, "loader": 4, "python": 3}
        or selected_launch["systemd_fd_names"]
        != ["ab16-python", "ab16-loader", "ab16-authority"]
        or dual_holder
        != {
            "assumption_id": "AB16_DUAL_HOLDER_SURVIVAL_V1",
            "reboot_or_power_loss_during_heavy_runtime_excluded": True,
            "simultaneous_guardian_supervisor_death_excluded": True,
            "single_holder_death_must_be_contained": True,
        }
        or platform["external_platform_trust"]
        != [
            "CPython runtime and standard library semantics",
            "OR-Tools/protobuf installation and native dependencies",
            "kernel, systemd, D-Bus, cgroup-v2 and filesystem durability",
            "non-hostile operating-system account",
        ]
        or type(platform["ortools_version"]) is not str
        or not platform["ortools_version"]
        or type(platform["protobuf_version"]) is not str
        or not platform["protobuf_version"]
    ):
        raise AuthorityError("REPOSITORY_SNAPSHOT_BINDING_DRIFT", "external platform assumptions")
    members = {member["path"]: member for member in manifest["members"]}
    expected_dirs = {
        parent.as_posix()
        for path in members
        for parent in PurePosixPath(path).parents
        if parent.as_posix() != "."
    }
    _assert_no_symlink_chain(snapshot_root)
    try:
        root_mode = os.lstat(snapshot_root).st_mode
    except OSError as exc:
        raise AuthorityError("REPOSITORY_SNAPSHOT_REPLAY_FAILED", str(snapshot_root)) from exc
    if not stat.S_ISDIR(root_mode) or stat.S_IMODE(root_mode) != 0o555:
        raise AuthorityError("REPOSITORY_SNAPSHOT_REPLAY_FAILED", "snapshot root mode")
    actual_dirs: set[str] = set()
    actual_files: dict[str, Snapshot] = {}
    for current, dirnames, filenames in os.walk(snapshot_root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in dirnames:
            child = current_path / name
            relative = child.relative_to(snapshot_root).as_posix()
            mode = os.lstat(child).st_mode
            if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode) or stat.S_IMODE(mode) != 0o555:
                raise AuthorityError("REPOSITORY_SNAPSHOT_REPLAY_FAILED", f"directory {relative}")
            actual_dirs.add(relative)
        for name in filenames:
            child = current_path / name
            relative = child.relative_to(snapshot_root).as_posix()
            mode = os.lstat(child).st_mode
            if not stat.S_ISREG(mode) or stat.S_ISLNK(mode) or os.lstat(child).st_nlink != 1:
                raise AuthorityError("REPOSITORY_SNAPSHOT_REPLAY_FAILED", f"member {relative}")
            actual_files[relative] = snapshot_regular(child)
    if set(actual_files) != set(members) or actual_dirs != expected_dirs:
        raise AuthorityError("REPOSITORY_SNAPSHOT_REPLAY_FAILED", "missing or extra path")
    identities: dict[str, dict[str, object]] = {}
    for path, member in members.items():
        snapshot = actual_files[path]
        if (
            snapshot.mode != member["materialized_mode"]
            or snapshot.sha256 != member["raw_sha256"]
            or snapshot.size_bytes != member["size_bytes"]
        ):
            raise AuthorityError("REPOSITORY_SNAPSHOT_REPLAY_FAILED", f"identity {path}")
        identities[path] = detached_identity(snapshot)
    return {
        "archive_identity": archive_identity,
        "external_platform": platform,
        "external_platform_identity": detached_identity(platform_snapshot),
        "manifest_identity": manifest_identity,
        "materialization_identity": detached_identity(receipt_snapshot),
        "member_identities": identities,
        "repository_root": str(snapshot_root),
        "repository_tree": manifest["repository_tree"],
    }


def _candidate_planned_source_roles() -> set[str]:
    roles = {
        "script.campaign_authority_v4",
        *(
            f"script.{role.removeprefix('tool.').removesuffix('.py')}"
            for role in REQUIRED_PACKAGE_ROLES
            if role.startswith("tool.") and role.endswith(".py")
        ),
        *(
            f"system.{role.removeprefix('system.').removesuffix('.bin')}"
            for role in REQUIRED_PACKAGE_ROLES
            if role.startswith("system.") and role.endswith(".bin")
        ),
        *(
            f"input.{role}"
            for role in (
                "candidate_placements",
                "canonical_rules",
                "cuts_mandatory_schedule",
                "history_freeze_manifest",
                "legacy_control_a002",
                "mandatory_instances",
                "preflight_gate",
                "project_lock",
            )
        ),
    }
    return roles


def _validate_candidate_planned_identity(
    value: object,
    *,
    role: str,
) -> Mapping[str, Any]:
    expected_keys = {
        "device",
        "inode",
        "mode",
        "mode_octal",
        "path",
        "sha256",
        "size_bytes",
    }
    if role.startswith("system."):
        expected_keys.add("requested_path")
    identity = _exact_keys(value, expected_keys, f"candidate planned source {role}")
    if (
        type(identity["device"]) is not int
        or identity["device"] < 0
        or type(identity["inode"]) is not int
        or identity["inode"] < 0
        or type(identity["mode"]) is not int
        or not 0 <= identity["mode"] <= 0o7777
        or type(identity["mode_octal"]) is not str
        or identity["mode_octal"] != f"{identity['mode']:04o}"
        or type(identity["path"]) is not str
        or not Path(identity["path"]).is_absolute()
        or _absolute(identity["path"]) != Path(identity["path"])
        or type(identity["sha256"]) is not str
        or SHA256_RE.fullmatch(identity["sha256"]) is None
        or type(identity["size_bytes"]) is not int
        or identity["size_bytes"] < 0
        or (
            role.startswith("system.")
            and (
                type(identity["requested_path"]) is not str
                or not Path(identity["requested_path"]).is_absolute()
                or _absolute(identity["requested_path"]) != Path(identity["requested_path"])
            )
        )
    ):
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", f"candidate planned source {role}")
    return identity


def _candidate_planned_source_identities(
    candidate: object,
    *,
    directory: Path,
    root: Mapping[str, Any],
) -> Mapping[str, Mapping[str, Any]]:
    expected_keys = set(
        "arm_launch_authorized candidate_id candidate_only created_at_utc formal_campaign_creation_authorized "
        "gate_a_receipt_identity path_preregistration_identity planned_source_identities "
        "planned_source_set_digest purpose repository_head repository_root run_nonce schema_version "
        "target_campaign_dir".split()
    )
    record = _exact_keys(candidate, expected_keys, "AB16 offline candidate")
    planned = _exact_keys(
        record["planned_source_identities"],
        _candidate_planned_source_roles(),
        "candidate planned source identities",
    )
    for role, identity in planned.items():
        _validate_candidate_planned_identity(identity, role=role)
    candidate_without_id = dict(record)
    candidate_without_id.pop("candidate_id")
    repository_root = record["repository_root"]
    target_campaign_dir = record["target_campaign_dir"]
    if (
        record["schema_version"] != "noncert-cuts-ab16-bootstrap-offline-candidate-v2"
        or record["purpose"] != "AB16_OFFLINE_NONAUTHORIZING_CANDIDATE"
        or record["candidate_only"] is not True
        or record["formal_campaign_creation_authorized"] is not False
        or record["arm_launch_authorized"] is not False
        or type(record["candidate_id"]) is not str
        or record["candidate_id"] != hashlib.sha256(canonical_json(candidate_without_id)).hexdigest()
        or record["planned_source_set_digest"] != hashlib.sha256(canonical_json(planned)).hexdigest()
        or type(repository_root) is not str
        or not Path(repository_root).is_absolute()
        or _absolute(repository_root) != Path(repository_root)
        or type(target_campaign_dir) is not str
        or not Path(target_campaign_dir).is_absolute()
        or _absolute(target_campaign_dir) != Path(target_campaign_dir)
        or _absolute(target_campaign_dir) != directory
        or record["repository_head"] != root.get("repository_head")
        or record["run_nonce"] != root.get("run_nonce")
        or Path(target_campaign_dir).name != root.get("run_nonce")
    ):
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", "candidate planned source binding")
    expected_live_bindings = {
        "script.manager_attestor_v4": (
            Path(repository_root)
            / "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724/manager_attestor_v4.py",
            0o644,
        ),
        "input.history_freeze_manifest": (
            Path(repository_root)
            / ".artifacts/noncert_cuts_ab16_20260724/"
            "gate-a-terminal-reference-history-freeze-a001/manifest.json",
            0o400,
        ),
    }
    for role, (expected_path, expected_mode) in expected_live_bindings.items():
        if (
            planned[role]["path"] != str(expected_path)
            or planned[role]["mode"] != expected_mode
        ):
            raise AuthorityError("CAMPAIGN_ROOT_INVALID", f"candidate planned source binding {role}")
    return planned


def _validate_live_planned_source_join(
    *,
    root_role: str,
    selected: object,
    source_identity: Mapping[str, Any],
    packaged_identity: Mapping[str, Any],
    planned_identity: Mapping[str, Any],
) -> None:
    try:
        selected_identity = _exact_keys(
            selected,
            {"path", "sha256", "size_bytes"},
            f"root {root_role}",
        )
        current = snapshot_regular(planned_identity["path"])
    except (KeyError, TypeError, AuthorityError) as exc:
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", f"source join {root_role}") from exc
    detached_planned = {
        field: planned_identity[field]
        for field in ("path", "sha256", "size_bytes")
    }
    current_full = full_identity(current)
    planned_full = {
        field: planned_identity[field]
        for field in ("device", "inode", "mode", "path", "sha256", "size_bytes")
    }
    if (
        selected_identity != detached_planned
        or current_full != planned_full
        or planned_identity["mode_octal"] != f"{current.mode:04o}"
        or source_identity["sha256"] != selected_identity["sha256"]
        or source_identity["size_bytes"] != selected_identity["size_bytes"]
        or packaged_identity["sha256"] != selected_identity["sha256"]
        or packaged_identity["size_bytes"] != selected_identity["size_bytes"]
    ):
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", f"source join {root_role}")


def _validate_manager_attestor_source_join(
    *,
    root: Mapping[str, Any],
    selected: object,
    source_identity: Mapping[str, Any],
    packaged_identity: Mapping[str, Any],
    planned_identity: Mapping[str, Any],
) -> None:
    _validate_live_planned_source_join(
        root_role="manager_attestor_v4",
        selected=selected,
        source_identity=source_identity,
        packaged_identity=packaged_identity,
        planned_identity=planned_identity,
    )
    try:
        epoch_attestor = _exact_keys(
            root["manager_epoch"]["attestation_toolchain"]["attestor"],
            {
                "device",
                "inode",
                "mode",
                "mode_octal",
                "path",
                "requested_path",
                "sha256",
                "size_bytes",
            },
            "manager epoch attestor",
        )
    except (KeyError, TypeError, AuthorityError) as exc:
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", "source join manager_attestor_v4") from exc
    planned_full = {
        field: planned_identity[field]
        for field in ("device", "inode", "mode", "path", "sha256", "size_bytes")
    }
    epoch_full = {
        field: epoch_attestor[field]
        for field in ("device", "inode", "mode", "path", "sha256", "size_bytes")
    }
    if (
        epoch_full != planned_full
        or epoch_attestor["mode_octal"] != planned_identity["mode_octal"]
        or epoch_attestor["requested_path"] != planned_identity["path"]
    ):
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", "source join manager_attestor_v4")


def _validate_root_source_joins(
    directory: Path,
    root: Mapping[str, Any],
    files: Mapping[str, Snapshot],
    sources: Mapping[str, Mapping[str, Any]],
    repository_snapshot: Mapping[str, Any],
) -> None:
    tools = root.get("authority_tools")
    inputs = root.get("strict_inputs")
    if type(tools) is not dict or type(inputs) is not dict:
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", "tool/input identity maps")
    script_roles = {
        "campaign_authority_v4": "campaign_authority_v4.py",
        "ab16_authority_v1": "tool.ab16_authority_v1.py",
        "ab16_authority_v2": "tool.ab16_authority_v2.py",
        "ab16_campaign_bootstrap_v1": "tool.ab16_campaign_bootstrap_v1.py",
        "ab16_campaign_bootstrap_v2": "tool.ab16_campaign_bootstrap_v2.py",
        "ab16_contract_v1": "tool.ab16_contract_v1.py",
        "ab16_formal_campaign_v1": "tool.ab16_formal_campaign_v1.py",
        "ab16_formal_controller_v1": "tool.ab16_formal_controller_v1.py",
        "ab16_formal_launch_authority_v1": "tool.ab16_formal_launch_authority_v1.py",
        "ab16_formal_launch_validator_v1": "tool.ab16_formal_launch_validator_v1.py",
        "ab16_formal_loader_v1": "tool.ab16_formal_loader_v1.py",
        "ab16_formal_orchestrator_v1": "tool.ab16_formal_orchestrator_v1.py",
        "ab16_formal_success_verifier_v1": "tool.ab16_formal_success_verifier_v1.py",
        "ab16_outer_closeout_state_v1": "tool.ab16_outer_closeout_state_v1.py",
        "ab16_outer_guardian_v1": "tool.ab16_outer_guardian_v1.py",
        "ab16_outer_refunit_closeout_v1": "tool.ab16_outer_refunit_closeout_v1.py",
        "ab16_preflight_qualification_v1": "tool.ab16_preflight_qualification_v1.py",
        "ab16_pytest_collection_plugin_v1": "tool.ab16_pytest_collection_plugin_v1.py",
        "ab16_pytest_collection_protocol_v1": "tool.ab16_pytest_collection_protocol_v1.py",
        "ab16_terminal_gate_v1": "tool.ab16_terminal_gate_v1.py",
        "ab16_terminal_gate_v2": "tool.ab16_terminal_gate_v2.py",
        "baseline_admission_v1": "tool.baseline_admission_v1.py",
        "baseline_rebuild_v1": "tool.baseline_rebuild_v1.py",
        "cut_free_incumbent_replay_v1": "tool.cut_free_incumbent_replay_v1.py",
        "disposable_drill_authority_v1": "tool.disposable_drill_authority_v1.py",
        "disposable_drill_authority_v2": "tool.disposable_drill_authority_v2.py",
        "disposable_drill_payload_v1": "tool.disposable_drill_payload_v1.py",
        "gate_a_validation_v2": "tool.gate_a_validation_v2.py",
        "gate_a_pinned_entrypoint_v2": "tool.gate_a_pinned_entrypoint_v2.py",
        "gate_a_recovery_inputs_v1": "tool.gate_a_recovery_inputs_v1.py",
        "organic_arm_runner_v1": "tool.organic_arm_runner_v1.py",
        "organic_arm_replay_v1": "tool.organic_arm_replay_v1.py",
        "organic_resource_lifecycle_v1": "tool.organic_resource_lifecycle_v1.py",
        "organic_resource_lifecycle_v2": "tool.organic_resource_lifecycle_v2.py",
        "organic_resource_verifier_v1": "tool.organic_resource_verifier_v1.py",
        "organic_resource_verifier_v2": "tool.organic_resource_verifier_v2.py",
        "organic_unit_orchestrator_v1": "tool.organic_unit_orchestrator_v1.py",
        "organic_unit_orchestrator_v2": "tool.organic_unit_orchestrator_v2.py",
        "systemd_unit_reference_v1": "tool.systemd_unit_reference_v1.py",
        "gate1_campaign_bootstrap_v4": "tool.gate1_campaign_bootstrap_v4.py",
        "gate1_campaign_driver_v4": "tool.gate1_campaign_driver_v4.py",
        "gate1_campaign_execution_v4": "tool.gate1_campaign_execution_v4.py",
        "gate1_payload_v4": "tool.gate1_payload_v4.py",
        "gate1_unit_orchestrator_v4": "tool.gate1_unit_orchestrator_v4.py",
        "independent_arithmetic_v4": "tool.independent_arithmetic_v4.py",
        "manager_attestor_v4": "tool.manager_attestor_v4.py",
        "positive_control_formal_v4": "tool.positive_control_formal_v4.py",
        "positive_control_gate_v4": "tool.positive_control_gate_v4.py",
        "positive_control_v4": "tool.positive_control_v4.py",
        "resource_lifecycle_v4": "tool.resource_lifecycle_v4.py",
        "resource_verifier_v4": "tool.resource_verifier_v4.py",
        "attestor_python": "system.attestor_python.bin",
        "busctl": "system.busctl.bin",
        "git": "system.git.bin",
        "libsystemd": "system.libsystemd.bin",
        "python3_13": "system.python3_13.bin",
        "sudo": "system.sudo.bin",
        "systemctl": "system.systemctl.bin",
        "systemd_run": "system.systemd_run.bin",
    }
    input_roles = {
        "ab16_bootstrap_manager_epoch_capture": "input.ab16_bootstrap_manager_epoch_capture.json",
        "ab16_external_platform_assumptions": "input.ab16_external_platform_assumptions.json",
        "ab16_gate_a_receipt": "input.ab16_gate_a_receipt.json",
        "ab16_gate_b_approval": "input.ab16_gate_b_approval.json",
        "ab16_gate_b_epoch_observation": "input.ab16_gate_b_epoch_observation.json",
        "ab16_gate_b_final_full_preflight": "input.ab16_gate_b_final_full_preflight.json",
        "ab16_offline_candidate": "input.ab16_offline_candidate.json",
        "ab16_path_preregistration": "input.ab16_path_preregistration.json",
        "ab16_repository_snapshot": "input.ab16_repository_snapshot.json",
        "ab16_repository_snapshot_archive": "input.ab16_repository_snapshot.zip",
        "candidate_placements": "input.candidate_placements.json",
        "canonical_rules": "input.canonical_rules.json",
        "cuts_mandatory_schedule": "input.cuts_mandatory_schedule.txt",
        "history_freeze_manifest": "input.history_freeze_manifest.json",
        "legacy_control_a002": "input.legacy_control_a002.json",
        "mandatory_instances": "input.mandatory_instances.json",
        "preflight_gate": "input.preflight_gate.txt",
        "project_lock": "input.project_lock.txt",
    }
    if (
        not set(script_roles) <= set(tools)
        or not set(input_roles) <= set(inputs)
        or "ab16_repository_snapshot_materialization" not in inputs
    ):
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", "required AB16 root roles absent")
    snapshot_paths = {
        "candidate_placements": "data/preprocessed/candidate_placements.json",
        "canonical_rules": "rules/canonical_rules.json",
        "cuts_mandatory_schedule": (
            "docs/research/b1_sidewise_marked_membrane_authority_recovery_20260724/"
            "04_cuts_mandatory_schedule.md"
        ),
        "mandatory_instances": "data/preprocessed/mandatory_exact_instances.json",
        "preflight_gate": "scripts/preflight_gate.py",
        "project_lock": "PROJECT_LOCK.md",
    }
    materialized = repository_snapshot["member_identities"]
    try:
        candidate = _record(
            _source_snapshot(files, sources, "input.ab16_offline_candidate.json"),
            "AB16 offline candidate",
        )
        planned_sources = _candidate_planned_source_identities(
            candidate,
            directory=directory,
            root=root,
        )
    except (KeyError, TypeError, AuthorityError) as exc:
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", "candidate planned source joins") from exc
    for root_role, package_role in {**script_roles, **input_roles}.items():
        group = tools if root_role in script_roles else inputs
        selected = group[root_role]
        source_identity = _detached_from_source(sources[package_role]["source_identity"])
        packaged_identity = detached_identity(files[sources[package_role]["package_path"]])
        if root_role == "manager_attestor_v4":
            _validate_manager_attestor_source_join(
                root=root,
                selected=selected,
                source_identity=source_identity,
                packaged_identity=packaged_identity,
                planned_identity=planned_sources["script.manager_attestor_v4"],
            )
            continue
        if root_role == "history_freeze_manifest":
            _validate_live_planned_source_join(
                root_role=root_role,
                selected=selected,
                source_identity=source_identity,
                packaged_identity=packaged_identity,
                planned_identity=planned_sources["input.history_freeze_manifest"],
            )
            continue
        allowed = [source_identity, packaged_identity]
        if root_role in snapshot_paths:
            expected_snapshot = materialized.get(snapshot_paths[root_role])
            if expected_snapshot is None:
                raise AuthorityError("CAMPAIGN_ROOT_INVALID", f"snapshot role {root_role}")
            allowed.append(expected_snapshot)
        if (
            selected not in allowed
            or selected["sha256"] != source_identity["sha256"]
            or selected["size_bytes"] != source_identity["size_bytes"]
        ):
            raise AuthorityError("CAMPAIGN_ROOT_INVALID", f"source join {root_role}")
    if (
        inputs["ab16_repository_snapshot_materialization"]
        != repository_snapshot["materialization_identity"]
    ):
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", "source join repository snapshot materialization")


def _campaign_context(campaign_dir: Path | str) -> dict[str, object]:
    directory = _absolute(campaign_dir)
    root_snapshot = snapshot_regular(directory / "campaign-root.json")
    root = _record(root_snapshot, "campaign root")
    if root.get("repository_head") is None or HEAD_RE.fullmatch(str(root["repository_head"])) is None:
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", "repository HEAD")
    package = root.get("package")
    if type(package) is not dict or type(package.get("package_dir")) is not str:
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", "package binding")
    files, package_manifest, sources = _package_sources(package["package_dir"])
    campaign_tool = _load_module(
        _source_snapshot(files, sources, "campaign_authority_v4.py"),
        f"_ab16_campaign_authority_{root_snapshot.sha256[:16]}",
    )
    try:
        campaign_tool.validate_campaign_root(root, campaign_dir=directory)
        replay = campaign_tool.verify_package(
            package["package_dir"],
            expected_manager_epoch=root["manager_epoch"],
            replay_external=True,
        )
    except Exception as exc:
        raise AuthorityError("CAMPAIGN_AUTHORITY_REPLAY_FAILED", str(exc)) from exc
    if (
        replay.get("package_id") != package.get("package_id")
        or replay.get("manifest_identity") != package.get("manifest_identity")
        or replay.get("seal_identity") != package.get("seal_identity")
    ):
        raise AuthorityError("CAMPAIGN_PACKAGE_BINDING_DRIFT", "root/package replay")
    if (
        package_manifest.get("manager_epoch") != root.get("manager_epoch")
        or package_manifest.get("repository_head") != root.get("repository_head")
        or package_manifest.get("run_nonce") != root.get("run_nonce")
    ):
        raise AuthorityError("CAMPAIGN_PACKAGE_BINDING_DRIFT", "manifest/root")
    repository_snapshot = _replay_repository_snapshot(
        directory=directory,
        root=root,
        files=files,
        sources=sources,
    )
    context: dict[str, object] = {
        "campaign_module": campaign_tool,
        "directory": directory,
        "files": files,
        "package_manifest": package_manifest,
        "root": root,
        "root_identity": detached_identity(root_snapshot),
        "repository_snapshot": repository_snapshot,
        "sources": sources,
    }
    _validate_gate_approvals(context)
    _validate_root_source_joins(
        directory,
        root,
        files,
        sources,
        repository_snapshot,
    )
    gate = root["stage_topology"]["gate1_v4"]
    positive = gate["positive_control"]
    required_positive = {
        "binding_paths",
        "binding_seal_path",
        "common_artifact_paths",
        "common_manifest_path",
    }
    if not required_positive <= set(positive):
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", "common-prestate/bindings not preregistered")
    return context


def _repository_snapshot_barrier(context: Mapping[str, Any]) -> None:
    refreshed = _campaign_context(context["directory"])
    if refreshed["root_identity"] != context["root_identity"] or (
        refreshed["repository_snapshot"] != context["repository_snapshot"]
    ):
        raise AuthorityError("REPOSITORY_SNAPSHOT_BINDING_DRIFT", "barrier replay")


def replay_repository_snapshot(campaign_dir: Path | str) -> Mapping[str, Any]:
    """Replay the sealed repository source tree and return its exact identities."""

    return _campaign_context(campaign_dir)["repository_snapshot"]


def _validate_gate_b_publisher_record(
    value: object,
    *,
    driver_identity: Mapping[str, Any],
    mechanical_publisher_identity: Mapping[str, Any],
    owner_source_identity: Mapping[str, Any],
    output_identity: Mapping[str, Any],
    python_identity: Mapping[str, Any],
    renderer_identity: Mapping[str, Any],
) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "actor",
            "driver_program",
            "execution_strategy",
            "mechanical_publisher",
            "owner_source",
            "output_mode",
            "output_path",
            "python",
            "qualification_session",
            "renderer_source",
        },
        "AB16 Gate-B publisher",
    )
    actor = _exact_keys(
        record["actor"],
        {"pid", "pid_starttime", "role"},
        "AB16 Gate-B publisher actor",
    )
    projected_output = {
        field: output_identity[field] for field in ("mode", "path", "sha256", "size_bytes")
    }
    qualification = _exact_keys(
        record["qualification_session"],
        {
            "lock_identities",
            "retained_fd_roles",
            "sequence",
            "session_id",
            "state",
        },
        "AB16 Gate-B qualification session",
    )
    lock_identities = qualification["lock_identities"]
    if type(lock_identities) is not list or len(lock_identities) != 3:
        raise AuthorityError("GATE_APPROVALS_INVALID", "Gate-B qualification lock set")
    lock_paths: list[str] = []
    for value in lock_identities:
        lock = _exact_keys(
            value,
            {"device", "inode", "mode", "nlink", "path", "uid"},
            "AB16 Gate-B qualification lock",
        )
        if (
            type(lock["device"]) is not int
            or lock["device"] < 0
            or type(lock["inode"]) is not int
            or lock["inode"] < 0
            or type(lock["mode"]) is not int
            or lock["mode"] != 0o600
            or lock["nlink"] != 1
            or type(lock["path"]) is not str
            or type(lock["uid"]) is not int
            or lock["uid"] < 0
        ):
            raise AuthorityError(
                "GATE_APPROVALS_INVALID",
                "Gate-B qualification lock identity",
            )
        lock_paths.append(lock["path"])
    if (
        actor["role"] != "AB16_GATE_B_OWNER"
        or type(actor["pid"]) is not int
        or actor["pid"] <= 1
        or type(actor["pid_starttime"]) is not str
        or not actor["pid_starttime"].isdigit()
        or record["driver_program"] != driver_identity
        or record["mechanical_publisher"] != mechanical_publisher_identity
        or record["execution_strategy"]
        != "persistent-owner-sealed-fd-oexcl-bootstrap-handoff-v1"
        or record["owner_source"] != owner_source_identity
        or record["output_mode"] != 0o444
        or record["output_path"] != projected_output["path"]
        or projected_output["mode"] != 0o444
        or record["python"] != python_identity
        or record["renderer_source"] != renderer_identity
        or lock_paths
        != [
            "/tmp/zmd-pj-codex-heavy-validation.lock",
            "/run/user/1000/zmd_pj_prod_scale_solver.lock",
            "/run/user/1000/zmd-pj-prod-scale-solve.lock",
        ]
        or qualification["retained_fd_roles"]
        != [
            "lock",
            "mechanical_publisher",
            "output_directory",
            "rendered_record",
            "renderer_source",
            "request",
        ]
        or qualification["sequence"] not in (1, 2)
        or type(qualification["session_id"]) is not str
        or SHA256_RE.fullmatch(qualification["session_id"]) is None
        or qualification["state"]
        != "PUBLISHED_FDS_RETAINED_PENDING_BOOTSTRAP_HANDOFF"
    ):
        raise AuthorityError("GATE_APPROVALS_INVALID", "Gate-B publisher identity drifted")
    return record


def _join_gate_b_renderer_identity(
    planned_identity: Mapping[str, Any],
    staged_source_identity: Mapping[str, Any],
) -> dict[str, object]:
    """Bind the live Gate-B renderer to the byte-identical staged package source."""

    planned = _exact_keys(
        planned_identity,
        {"mode", "path", "sha256", "size_bytes"},
        "AB16 planned Gate-B renderer",
    )
    staged = _validate_source_identity(
        staged_source_identity,
        "AB16 staged Gate-B renderer",
    )
    if (
        type(planned["mode"]) is not int
        or type(planned["path"]) is not str
        or not Path(planned["path"]).is_absolute()
        or type(planned["sha256"]) is not str
        or SHA256_RE.fullmatch(planned["sha256"]) is None
        or type(planned["size_bytes"]) is not int
        or planned["size_bytes"] < 0
        or staged["sha256"] != planned["sha256"]
        or staged["size_bytes"] != planned["size_bytes"]
    ):
        raise AuthorityError(
            "GATE_APPROVALS_INVALID",
            "Gate-B live/staged renderer identity drifted",
        )
    return dict(planned)


def _open_validation_directory_no_symlinks(path: Path) -> int:
    absolute = _absolute(path)
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(absolute.anchor, flags)
        for component in absolute.parts[1:]:
            following = os.open(component, flags, dir_fd=descriptor)
            try:
                os.close(descriptor)
            except BaseException as exc:
                try:
                    os.close(following)
                except OSError as close_error:
                    exc.add_note(
                        "validation directory-chain cleanup failed: "
                        f"{type(close_error).__name__}: {close_error}"
                    )
                raise
            descriptor = following
        return descriptor
    except BaseException as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as close_error:
                exc.add_note(
                    "validation directory-chain cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        if isinstance(exc, OSError):
            raise AuthorityError(
                "GATE_APPROVALS_INVALID",
                "preflight scratch directory path is invalid or symlinked",
            ) from exc
        raise


def _validate_closed_preflight_scratch(
    value: object,
    *,
    receipt_directory: Path,
    label: str,
) -> None:
    record = _exact_keys(
        value,
        {
            "basetemp_identity",
            "basetemp_path",
            "initial_identity",
            "path",
            "policy",
            "retention_policy",
            "status",
        },
        f"{label} pytest scratch",
    )
    identity = _exact_keys(
        record["initial_identity"],
        {"device", "inode", "mode", "uid"},
        f"{label} pytest scratch initial identity",
    )
    basetemp_identity = _exact_keys(
        record["basetemp_identity"],
        {"device", "inode", "mode", "uid"},
        f"{label} pytest basetemp identity",
    )
    if (
        any(type(identity[field]) is not int for field in identity)
        or any(type(basetemp_identity[field]) is not int for field in basetemp_identity)
        or identity["device"] < 0
        or identity["inode"] <= 0
        or identity["mode"] != 0o700
        or identity["uid"] != os.geteuid()
        or basetemp_identity["device"] < 0
        or basetemp_identity["inode"] <= 0
        or basetemp_identity["mode"] != 0o700
        or basetemp_identity["uid"] != os.geteuid()
        or record["path"] != str(receipt_directory / FINAL_FULL_PREFLIGHT_SCRATCH_BASENAME)
        or record["basetemp_path"]
        != str(
            receipt_directory
            / FINAL_FULL_PREFLIGHT_SCRATCH_BASENAME
            / FINAL_FULL_PREFLIGHT_BASETEMP_BASENAME
        )
        or record["policy"] != FINAL_FULL_PREFLIGHT_SCRATCH_POLICY
        or record["retention_policy"] != "failed"
        or record["status"] != "CLOSED_EMPTY_BASETEMP_RETAINED_AFTER_PASS"
    ):
        raise AuthorityError(
            "GATE_APPROVALS_INVALID",
            f"{label} pytest scratch is not an exact closed PASS",
        )
    descriptor: int | None = None
    basetemp_descriptor: int | None = None
    try:
        descriptor = _open_validation_directory_no_symlinks(Path(record["path"]))
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(observed.st_mode)
            or observed.st_dev != identity["device"]
            or observed.st_ino != identity["inode"]
            or stat.S_IMODE(observed.st_mode) != identity["mode"]
            or observed.st_uid != identity["uid"]
        ):
            raise AuthorityError(
                "GATE_APPROVALS_INVALID",
                f"{label} pytest scratch identity drifted",
            )
        with os.scandir(descriptor) as iterator:
            entries = list(iterator)
        if len(entries) != 1 or entries[0].name != FINAL_FULL_PREFLIGHT_BASETEMP_BASENAME:
            raise AuthorityError(
                "GATE_APPROVALS_INVALID",
                f"{label} pytest scratch tree drifted",
            )
        named = entries[0].stat(follow_symlinks=False)
        if not stat.S_ISDIR(named.st_mode):
            raise AuthorityError(
                "GATE_APPROVALS_INVALID",
                f"{label} pytest basetemp type drifted",
            )
        basetemp_descriptor = os.open(
            FINAL_FULL_PREFLIGHT_BASETEMP_BASENAME,
            os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=descriptor,
        )
        opened = os.fstat(basetemp_descriptor)
        if (
            (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
            or opened.st_dev != basetemp_identity["device"]
            or opened.st_ino != basetemp_identity["inode"]
            or stat.S_IMODE(opened.st_mode) != basetemp_identity["mode"]
            or opened.st_uid != basetemp_identity["uid"]
        ):
            raise AuthorityError(
                "GATE_APPROVALS_INVALID",
                f"{label} pytest basetemp identity drifted",
            )
        with os.scandir(basetemp_descriptor) as iterator:
            if next(iterator, None) is not None:
                raise AuthorityError(
                    "GATE_APPROVALS_INVALID",
                    f"{label} pytest basetemp is not empty",
                )
    except BaseException as exc:
        for opened_descriptor in (basetemp_descriptor, descriptor):
            if opened_descriptor is None:
                continue
            try:
                os.close(opened_descriptor)
            except OSError as close_error:
                exc.add_note(
                    f"{label} pytest scratch cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        if isinstance(exc, OSError):
            raise AuthorityError(
                "GATE_APPROVALS_INVALID",
                f"{label} pytest scratch closure check failed",
            ) from exc
        raise
    close_error: OSError | None = None
    for opened_descriptor in (basetemp_descriptor, descriptor):
        try:
            os.close(opened_descriptor)
        except OSError as exc:
            if close_error is None:
                close_error = exc
    if close_error is not None:
        raise AuthorityError(
            "GATE_APPROVALS_INVALID",
            f"{label} pytest scratch descriptor close failed",
        ) from close_error


def _validate_preflight_output_root(
    value: object,
    *,
    receipt_directory: Path,
    label: str,
) -> None:
    identity = _exact_keys(
        value,
        {"device", "inode", "mode", "uid"},
        f"{label} output-root identity",
    )
    if (
        any(type(identity[field]) is not int for field in identity)
        or identity["device"] < 0
        or identity["inode"] <= 0
        or identity["mode"] != 0o700
        or identity["uid"] != os.geteuid()
    ):
        raise AuthorityError(
            "GATE_APPROVALS_INVALID",
            f"{label} output-root identity is malformed",
        )
    descriptor: int | None = None
    try:
        descriptor = _open_validation_directory_no_symlinks(receipt_directory)
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(observed.st_mode)
            or observed.st_dev != identity["device"]
            or observed.st_ino != identity["inode"]
            or stat.S_IMODE(observed.st_mode) != identity["mode"]
            or observed.st_uid != identity["uid"]
        ):
            raise AuthorityError(
                "GATE_APPROVALS_INVALID",
                f"{label} output-root identity drifted",
            )
        with os.scandir(descriptor) as iterator:
            entries = {entry.name for entry in iterator}
        if entries != {
            FINAL_FULL_PREFLIGHT_SCRATCH_BASENAME,
            "receipt.commit.json",
            "receipt.json",
            "stderr.log",
            "stdout.log",
        }:
            raise AuthorityError(
                "GATE_APPROVALS_INVALID",
                f"{label} output-root member set drifted",
            )
    except BaseException as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError as close_error:
                exc.add_note(
                    f"{label} output-root cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        if isinstance(exc, OSError):
            raise AuthorityError(
                "GATE_APPROVALS_INVALID",
                f"{label} output-root validation failed",
            ) from exc
        raise
    try:
        os.close(descriptor)
    except OSError as exc:
        raise AuthorityError(
            "GATE_APPROVALS_INVALID",
            f"{label} output-root descriptor close failed",
        ) from exc


def _validate_preflight_publication_commit(
    *,
    receipt_identity: Mapping[str, object],
    output_root_identity: object,
    label: str,
) -> None:
    receipt_path = Path(str(receipt_identity["path"]))
    snapshot = snapshot_regular(receipt_path.parent / "receipt.commit.json")
    record = _exact_keys(
        _unterminated_record(snapshot, f"{label} publication commit"),
        {
            "output_root_identity",
            "receipt_identity",
            "schema_version",
            "status",
        },
        f"{label} publication commit",
    )
    if (
        snapshot.mode != 0o444
        or record["schema_version"] != FINAL_FULL_PREFLIGHT_PUBLICATION_COMMIT_SCHEMA
        or record["status"] != "COMMITTED"
        or record["receipt_identity"] != receipt_identity
        or record["output_root_identity"] != output_root_identity
    ):
        raise AuthorityError(
            "GATE_APPROVALS_INVALID",
            f"{label} publication commit is invalid",
        )


def _validate_preflight_collection_projection(
    value: object,
    *,
    label: str,
) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "collection_count",
            "collection_sha256",
            "manifest_sha256",
            "markexpr",
            "schema_version",
            "stage_module_origin_count",
            "stage_sha256",
            "terminal_module_origin_count",
            "terminal_sha256",
            "workflow",
        },
        f"{label} pytest collection projection",
    )
    if (
        type(record["collection_count"]) is not int
        or record["collection_count"] <= 0
        or type(record["stage_module_origin_count"]) is not int
        or record["stage_module_origin_count"] < 0
        or type(record["terminal_module_origin_count"]) is not int
        or record["terminal_module_origin_count"] < 0
        or any(
            type(record[field]) is not str
            or SHA256_RE.fullmatch(record[field]) is None
            for field in (
                "collection_sha256",
                "manifest_sha256",
                "stage_sha256",
                "terminal_sha256",
            )
        )
        or record["markexpr"] != "not slow"
        or record["schema_version"]
        != "noncert-cuts-ab16-pytest-collection-binding-v1"
        or record["workflow"] != "full"
    ):
        raise AuthorityError(
            "GATE_APPROVALS_INVALID",
            f"{label} pytest collection projection is malformed",
        )
    return record


def _expected_preflight_qualification_argv(
    record: Mapping[str, Any],
    *,
    python: Mapping[str, object],
    qualification: Mapping[str, object],
    preflight: Mapping[str, object],
    protocol: Mapping[str, object],
    plugin: Mapping[str, object],
    label: str,
) -> list[object]:
    collection = _validate_preflight_collection_projection(
        record["pytest_collection"],
        label=label,
    )
    repository = Path(record["repository_root"])
    scratch = _exact_keys(
        record["pytest_scratch"],
        {
            "basetemp_identity",
            "basetemp_path",
            "initial_identity",
            "path",
            "policy",
            "retention_policy",
            "status",
        },
        f"{label} pytest scratch",
    )
    basetemp = Path(scratch["basetemp_path"])
    try:
        basetemp_relative = basetemp.relative_to(repository)
    except ValueError as exc:
        raise AuthorityError(
            "GATE_APPROVALS_INVALID",
            f"{label} basetemp is outside its repository",
        ) from exc
    return [
        python["path"],
        "-I",
        "-B",
        qualification["path"],
        "--repository-root",
        str(repository),
        "--basetemp",
        str(basetemp),
        "--basetemp-relative",
        basetemp_relative.as_posix(),
        "--expected-count",
        str(collection["collection_count"]),
        "--expected-sha256",
        collection["collection_sha256"],
        "--preflight-source",
        preflight["path"],
        "--collection-protocol-source",
        protocol["path"],
        "--collection-plugin-source",
        plugin["path"],
        "--full",
    ]


def _validate_gate_approvals(context: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    files = context["files"]
    sources = context["sources"]
    gate_a_snapshot = _source_snapshot(files, sources, "input.ab16_gate_a_receipt.json")
    gate_b_snapshot = _source_snapshot(files, sources, "input.ab16_gate_b_approval.json")
    candidate_snapshot = _source_snapshot(files, sources, "input.ab16_offline_candidate.json")
    final_snapshot = _source_snapshot(files, sources, "input.ab16_gate_b_final_full_preflight.json")
    epoch_snapshot = _source_snapshot(files, sources, "input.ab16_gate_b_epoch_observation.json")
    gate_a = _record(gate_a_snapshot, "AB16 Gate-A")
    candidate = _exact_keys(
        _record(candidate_snapshot, "AB16 offline candidate"),
        set(
            "arm_launch_authorized candidate_id candidate_only created_at_utc formal_campaign_creation_authorized "
            "gate_a_receipt_identity path_preregistration_identity planned_source_identities "
            "planned_source_set_digest purpose repository_head repository_root run_nonce schema_version "
            "target_campaign_dir".split()
        ),
        "AB16 offline candidate",
    )
    gate_b = _exact_keys(
        _record(gate_b_snapshot, "AB16 Gate-B"),
        set(
            "approval_id arm_launch_authorized candidate_identity created_at_utc decision "
            "final_full_preflight_receipt_identity formal_campaign_creation_authorized gate "
            "gate_a_receipt_identity gate_b_epoch_observation_identity planned_source_set_digest purpose "
            "publisher repository_head repository_root run_nonce schema_version target_campaign_dir".split()
        ),
        "AB16 Gate-B",
    )
    gate_a_identity = _detached_from_source(sources["input.ab16_gate_a_receipt.json"]["source_identity"])
    candidate_identity = _detached_from_source(sources["input.ab16_offline_candidate.json"]["source_identity"])
    final_source = sources["input.ab16_gate_b_final_full_preflight.json"]["source_identity"]
    epoch_source = sources["input.ab16_gate_b_epoch_observation.json"]["source_identity"]
    final_identity = {field: final_source[field] for field in ("mode", "path", "sha256", "size_bytes")}
    epoch_identity = {field: epoch_source[field] for field in ("mode", "path", "sha256", "size_bytes")}
    gate_a_expected_keys = set(
        "approval_id arm_launch_authorized created_at_utc decision disposable_authority_ready_identity "
        "disposable_detached_replay_identity formal_campaign_creation_authorized full_preflight_receipt_identity "
        "gate history_freeze_replay_identity manager_epoch offline_candidate_only planned_source_set_digest "
        "purpose reference_capability_identity reference_capability_transcript_identity repository_head "
        "repository_root run_nonce schema_version target_campaign_dir".split()
    )
    if set(gate_a) != gate_a_expected_keys:
        raise AuthorityError(
            "GATE_APPROVALS_INVALID",
            "Gate-A exact evidence schema drifted",
        )
    planned = candidate["planned_source_identities"]
    if type(planned) is not dict:
        raise AuthorityError("GATE_APPROVALS_INVALID", "candidate planned source identities")
    planned_projections: dict[str, dict[str, object]] = {}
    for role in (
        "input.preflight_gate",
        "script.ab16_campaign_bootstrap_v2",
        "script.ab16_gate_b_qualification_v1",
        "script.ab16_preflight_qualification_v1",
        "script.ab16_pytest_collection_plugin_v1",
        "script.ab16_pytest_collection_protocol_v1",
        "script.gate_a_validation_v2",
        "system.python3_13",
    ):
        identity = planned.get(role)
        if type(identity) is not dict:
            raise AuthorityError("GATE_APPROVALS_INVALID", f"candidate planned source {role}")
        try:
            projection = {field: identity[field] for field in ("mode", "path", "sha256", "size_bytes")}
        except KeyError as exc:
            raise AuthorityError("GATE_APPROVALS_INVALID", f"candidate planned source {role}") from exc
        if (
            type(projection["mode"]) is not int
            or type(projection["path"]) is not str
            or not Path(projection["path"]).is_absolute()
            or type(projection["sha256"]) is not str
            or SHA256_RE.fullmatch(projection["sha256"]) is None
            or type(projection["size_bytes"]) is not int
            or projection["size_bytes"] < 0
        ):
            raise AuthorityError("GATE_APPROVALS_INVALID", f"candidate planned source {role}")
        planned_projections[role] = projection
    for field in (
        "disposable_authority_ready_identity",
        "disposable_detached_replay_identity",
        "full_preflight_receipt_identity",
        "history_freeze_replay_identity",
        "reference_capability_identity",
        "reference_capability_transcript_identity",
    ):
        _replay_identity_with_optional_mode(
            gate_a[field],
            f"AB16 Gate-A {field}",
        )
    try:
        context["campaign_module"].validate_manager_epoch(gate_a["manager_epoch"])
    except Exception as exc:
        raise AuthorityError(
            "GATE_APPROVALS_INVALID",
            f"Gate-A manager epoch is invalid: {exc}",
        ) from exc
    final = _exact_keys(
        _unterminated_record(final_snapshot, "AB16 Gate-B final full preflight"),
        set(
            "authorizations authority_ready_identity command detached_replay_identity duration_monotonic_ns "
            "exit_code finished_at_utc planned_source_set_digest pre_run_authority_identity "
            "output_root_identity qualification_runner_identity preflight_script_identity "
            "preflight_timeout_scale purpose pytest_collection pytest_collection_plugin_identity "
            "pytest_collection_protocol_identity pytest_scratch "
            "python_identity repository_head "
            "repository_root runner_tool_identity schema_version started_at_utc status stderr_identity "
            "stdout_identity timed_out".split()
        ),
        "AB16 Gate-B final full preflight",
    )
    for field in (
        "authority_ready_identity",
        "detached_replay_identity",
        "pre_run_authority_identity",
        "qualification_runner_identity",
        "preflight_script_identity",
        "pytest_collection_plugin_identity",
        "pytest_collection_protocol_identity",
        "python_identity",
        "stderr_identity",
        "stdout_identity",
    ):
        _replay_identity_with_optional_mode(final[field], f"AB16 Gate-B final full preflight {field}")
    command = _exact_keys(
        final["command"],
        {"argv", "execution_strategy", "loader_identity"},
        "AB16 Gate-B final full preflight command",
    )
    loader = _exact_keys(
        command["loader_identity"],
        {"sha256", "size_bytes"},
        "AB16 Gate-B final full preflight loader",
    )
    gate_a_full_snapshot = _replay_identity_with_optional_mode(
        gate_a["full_preflight_receipt_identity"],
        "AB16 Gate-A full preflight",
    )
    gate_a_full = _exact_keys(
        _unterminated_record(gate_a_full_snapshot, "AB16 Gate-A full preflight"),
        set(final),
        "AB16 Gate-A full preflight",
    )
    final_receipt_directory = final_snapshot.path.parent
    _validate_preflight_publication_commit(
        receipt_identity=final_identity,
        output_root_identity=final["output_root_identity"],
        label="AB16 Gate-B final full preflight",
    )
    _validate_preflight_output_root(
        final["output_root_identity"],
        receipt_directory=final_receipt_directory,
        label="AB16 Gate-B final full preflight",
    )
    _validate_closed_preflight_scratch(
        final["pytest_scratch"],
        receipt_directory=final_receipt_directory,
        label="AB16 Gate-B final full preflight",
    )
    gate_a_receipt_directory = gate_a_full_snapshot.path.parent
    _validate_preflight_publication_commit(
        receipt_identity=gate_a["full_preflight_receipt_identity"],
        output_root_identity=gate_a_full["output_root_identity"],
        label="AB16 Gate-A full preflight",
    )
    _validate_preflight_output_root(
        gate_a_full["output_root_identity"],
        receipt_directory=gate_a_receipt_directory,
        label="AB16 Gate-A full preflight",
    )
    _validate_closed_preflight_scratch(
        gate_a_full["pytest_scratch"],
        receipt_directory=gate_a_receipt_directory,
        label="AB16 Gate-A full preflight",
    )
    gate_a_command = _exact_keys(
        gate_a_full["command"],
        {"argv", "execution_strategy", "loader_identity"},
        "AB16 Gate-A full preflight command",
    )
    gate_a_loader = _exact_keys(
        gate_a_command["loader_identity"],
        {"sha256", "size_bytes"},
        "AB16 Gate-A full preflight loader",
    )
    snapshot_members = context["repository_snapshot"]["member_identities"]
    preflight_member = _replay_detached(
        snapshot_members["scripts/preflight_gate.py"],
        "AB16 snapshot preflight script",
    )
    preflight = planned_projections["input.preflight_gate"]
    python = planned_projections["system.python3_13"]
    qualification = planned_projections["script.ab16_preflight_qualification_v1"]
    protocol = planned_projections["script.ab16_pytest_collection_protocol_v1"]
    plugin = planned_projections["script.ab16_pytest_collection_plugin_v1"]
    runner_relative = "docs/research/noncert_cuts_ab16_20260724/gate_a_validation_v2.py"
    runner_member = _replay_detached(snapshot_members[runner_relative], "AB16 snapshot preflight runner")
    runner = planned_projections["script.gate_a_validation_v2"]
    python_snapshot = _replay_detached(
        context["root"]["authority_tools"].get("python3_13"),
        "AB16 preflight Python",
    )
    epoch = _exact_keys(
        _record(epoch_snapshot, "AB16 Gate-B epoch observation"),
        set(
            "authorizations candidate_identity capture_transcript created_at_utc "
            "final_full_preflight_receipt_identity gate_a_receipt_identity manager_epoch "
            "planned_source_set_digest publisher purpose repository_head repository_root run_nonce schema_version status "
            "target_campaign_dir".split()
        ),
        "AB16 Gate-B epoch observation",
    )
    external_platform = context["repository_snapshot"]["external_platform"]
    renderer_source = sources["tool.ab16_campaign_bootstrap_v2.py"]["source_identity"]
    renderer_identity = _join_gate_b_renderer_identity(
        planned_projections["script.ab16_campaign_bootstrap_v2"],
        renderer_source,
    )
    owner_source = sources["tool.ab16_gate_b_qualification_v1.py"]["source_identity"]
    owner_source_identity = _join_gate_b_renderer_identity(
        planned_projections["script.ab16_gate_b_qualification_v1"],
        owner_source,
    )
    gate_b_publisher = _validate_gate_b_publisher_record(
        gate_b["publisher"],
        driver_identity=external_platform["gate_b_owner_driver"],
        mechanical_publisher_identity=external_platform["mechanical_oexcl_publisher"],
        owner_source_identity=owner_source_identity,
        output_identity=sources["input.ab16_gate_b_approval.json"]["source_identity"],
        python_identity=planned_projections["system.python3_13"],
        renderer_identity=renderer_identity,
    )
    epoch_publisher = _validate_gate_b_publisher_record(
        epoch["publisher"],
        driver_identity=external_platform["gate_b_owner_driver"],
        mechanical_publisher_identity=external_platform["mechanical_oexcl_publisher"],
        owner_source_identity=owner_source_identity,
        output_identity=sources["input.ab16_gate_b_epoch_observation.json"]["source_identity"],
        python_identity=planned_projections["system.python3_13"],
        renderer_identity=renderer_identity,
    )
    try:
        context["campaign_module"].validate_manager_epoch(epoch["manager_epoch"])
        context["campaign_module"].validate_manager_epoch_capture_transcript(
            epoch["capture_transcript"],
            expected_epoch=epoch["manager_epoch"],
        )
    except Exception as exc:
        raise AuthorityError("GATE_APPROVALS_INVALID", f"Gate-B epoch is invalid: {exc}") from exc
    if (
        candidate["schema_version"] != "noncert-cuts-ab16-bootstrap-offline-candidate-v2"
        or candidate["purpose"] != "AB16_OFFLINE_NONAUTHORIZING_CANDIDATE"
        or candidate["candidate_only"] is not True
        or candidate["formal_campaign_creation_authorized"] is not False
        or candidate["arm_launch_authorized"] is not False
        or candidate["gate_a_receipt_identity"] != gate_a_identity
        or candidate["path_preregistration_identity"]
        != _detached_from_source(sources["input.ab16_path_preregistration.json"]["source_identity"])
        or candidate["planned_source_set_digest"] != hashlib.sha256(canonical_json(planned)).hexdigest()
        or candidate["candidate_id"]
        != hashlib.sha256(canonical_json({key: value for key, value in candidate.items() if key != "candidate_id"})).hexdigest()
        or any(candidate.get(field) != gate_a.get(field) for field in (
            "planned_source_set_digest",
            "repository_head",
            "repository_root",
            "run_nonce",
            "target_campaign_dir",
        ))
        or preflight_member.sha256 != preflight["sha256"]
        or preflight_member.size_bytes != preflight["size_bytes"]
        or runner_member.sha256 != runner["sha256"]
        or runner_member.size_bytes != runner["size_bytes"]
        or python_snapshot.sha256 != python["sha256"]
        or python_snapshot.size_bytes != python["size_bytes"]
        or gate_a.get("schema_version") != GATE_A_SCHEMA
        or gate_a.get("gate") != "A"
        or gate_a.get("decision") != "PASS"
        or gate_a.get("purpose") != "AB16_OFFLINE_SOURCE_SET_PREFLIGHT"
        or gate_a.get("offline_candidate_only") is not True
        or gate_a.get("formal_campaign_creation_authorized") is not False
        or gate_a.get("arm_launch_authorized") is not False
        or gate_b.get("schema_version") != GATE_B_SCHEMA
        or gate_b.get("gate") != "B"
        or gate_b.get("decision") != "APPROVED"
        or gate_b.get("purpose") != "AB16_FORMAL_CAMPAIGN_IDENTITY_CREATION"
        or gate_b.get("formal_campaign_creation_authorized") is not True
        or gate_b.get("arm_launch_authorized") is not False
        or gate_b.get("gate_a_receipt_identity") != gate_a_identity
        or gate_b.get("candidate_identity") != candidate_identity
        or gate_b.get("final_full_preflight_receipt_identity") != final_identity
        or gate_b.get("gate_b_epoch_observation_identity") != epoch_identity
        or final_snapshot.sha256 != final_identity["sha256"]
        or final_snapshot.size_bytes != final_identity["size_bytes"]
        or epoch_snapshot.sha256 != epoch_identity["sha256"]
        or epoch_snapshot.size_bytes != epoch_identity["size_bytes"]
        or gate_a.get("repository_root") != gate_b.get("repository_root")
        or any(gate_b.get(field) != gate_a.get(field) for field in (
            "planned_source_set_digest",
            "repository_head",
            "repository_root",
            "run_nonce",
            "target_campaign_dir",
        ))
        or gate_a.get("manager_epoch") != context["root"].get("manager_epoch")
        or gate_a.get("repository_head") != context["root"].get("repository_head")
        or gate_a.get("run_nonce") != context["root"].get("run_nonce")
        or gate_a.get("target_campaign_dir") != str(context["directory"])
        or type(gate_a.get("repository_root")) is not str
        or not Path(gate_a["repository_root"]).is_absolute()
        or gate_a.get("approval_id") == gate_b.get("approval_id")
        or gate_a_snapshot.sha256 == gate_b_snapshot.sha256
        or final_identity["mode"] != 0o444
        or epoch_identity["mode"] != 0o444
        or final["schema_version"] != FINAL_FULL_PREFLIGHT_SCHEMA
        or final["purpose"] != "AB16_GATE_A_FULL_PREFLIGHT"
        or final["status"] != "PASS"
        or final["exit_code"] != 0
        or final["timed_out"] is not False
        or final["preflight_timeout_scale"] != "12"
        or final["authorizations"]
        != {
            "formal_campaign_creation_authorized": False,
            "organic_arm_launch_authorized": False,
            "solver_run_authorized": False,
        }
        or type(final["duration_monotonic_ns"]) is not int
        or final["duration_monotonic_ns"] <= 0
        or final["authority_ready_identity"] != gate_a["disposable_authority_ready_identity"]
        or final["detached_replay_identity"] != gate_a["disposable_detached_replay_identity"]
        or final["pre_run_authority_identity"] != gate_a_full["pre_run_authority_identity"]
        or final["planned_source_set_digest"] != gate_a["planned_source_set_digest"]
        or final["repository_head"] != context["root"]["repository_head"]
        or final["repository_root"] != gate_a["repository_root"]
        or final["preflight_script_identity"] != preflight
        or final["qualification_runner_identity"] != qualification
        or final["pytest_collection_protocol_identity"] != protocol
        or final["pytest_collection_plugin_identity"] != plugin
        or final["python_identity"] != python
        or final["runner_tool_identity"] != runner
        or command["execution_strategy"] != "same-fd-subreaper-ab16-qualification-runner-v4"
        or command["argv"]
        != _expected_preflight_qualification_argv(
            final,
            python=python,
            qualification=qualification,
            preflight=preflight,
            protocol=protocol,
            plugin=plugin,
            label="AB16 Gate-B final full preflight",
        )
        or loader != gate_a_loader
        or gate_a_full["schema_version"] != FINAL_FULL_PREFLIGHT_SCHEMA
        or gate_a_full["purpose"] != "AB16_GATE_A_FULL_PREFLIGHT"
        or gate_a_full["status"] != "PASS"
        or gate_a_full["exit_code"] != 0
        or gate_a_full["timed_out"] is not False
        or gate_a_full["authorizations"] != final["authorizations"]
        or gate_a_full["authority_ready_identity"] != gate_a["disposable_authority_ready_identity"]
        or gate_a_full["detached_replay_identity"] != gate_a["disposable_detached_replay_identity"]
        or gate_a_full["repository_head"] != gate_a["repository_head"]
        or gate_a_full["repository_root"] != gate_a["repository_root"]
        or gate_a_full["planned_source_set_digest"] != gate_a["planned_source_set_digest"]
        or gate_a_full["preflight_script_identity"] != preflight
        or gate_a_full["qualification_runner_identity"] != qualification
        or gate_a_full["pytest_collection_protocol_identity"] != protocol
        or gate_a_full["pytest_collection_plugin_identity"] != plugin
        or gate_a_full["python_identity"] != python
        or gate_a_full["runner_tool_identity"] != runner
        or gate_a_command["execution_strategy"]
        != "same-fd-subreaper-ab16-qualification-runner-v4"
        or gate_a_command["argv"]
        != _expected_preflight_qualification_argv(
            gate_a_full,
            python=python,
            qualification=qualification,
            preflight=preflight,
            protocol=protocol,
            plugin=plugin,
            label="AB16 Gate-A full preflight",
        )
        or final_identity["path"] == gate_a["full_preflight_receipt_identity"]["path"]
        or final_identity["sha256"] == gate_a["full_preflight_receipt_identity"]["sha256"]
        or type(loader["sha256"]) is not str
        or SHA256_RE.fullmatch(loader["sha256"]) is None
        or type(loader["size_bytes"]) is not int
        or loader["size_bytes"] <= 0
        or epoch["schema_version"] != GATE_B_EPOCH_SCHEMA
        or epoch["purpose"] != "AB16_GATE_B_MANAGER_EPOCH_OBSERVATION"
        or epoch["status"] != "PASS"
        or epoch["authorizations"] != final["authorizations"]
        or epoch["candidate_identity"] != candidate_identity
        or epoch["gate_a_receipt_identity"] != gate_a_identity
        or epoch["final_full_preflight_receipt_identity"] != final_identity
        or epoch["manager_epoch"] != context["root"]["manager_epoch"]
        or epoch_publisher["actor"] != gate_b_publisher["actor"]
        or epoch_publisher["qualification_session"]["session_id"]
        != gate_b_publisher["qualification_session"]["session_id"]
        or epoch_publisher["qualification_session"]["sequence"] != 1
        or gate_b_publisher["qualification_session"]["sequence"] != 2
        or epoch_publisher["qualification_session"]["lock_identities"]
        != gate_b_publisher["qualification_session"]["lock_identities"]
        or any(epoch[field] != gate_a[field] for field in (
            "planned_source_set_digest",
            "repository_head",
            "repository_root",
            "run_nonce",
            "target_campaign_dir",
        ))
    ):
        raise AuthorityError("GATE_APPROVALS_INVALID", "Gate-A/Gate-B are not distinct and bound")
    return {
        "gate_a_identity": gate_a_identity,
        "gate_b_identity": _detached_from_source(sources["input.ab16_gate_b_approval.json"]["source_identity"]),
        "gate_b_epoch_identity": epoch_identity,
        "gate_b_final_full_preflight_identity": final_identity,
        "history_freeze_replay_identity": dict(gate_a["history_freeze_replay_identity"]),
        "reference_capability_identity": dict(gate_a["reference_capability_identity"]),
        "reference_capability_transcript_identity": dict(gate_a["reference_capability_transcript_identity"]),
        "repository_root": gate_a["repository_root"],
    }


def replay_gate_approvals(campaign_dir: Path | str) -> dict[str, Mapping[str, Any]]:
    """Replay the independently published Gate-A/Gate-B chain for launch validators."""

    return _validate_gate_approvals(_campaign_context(campaign_dir))


def replay_formal_runtime_boundary(campaign_dir: Path | str) -> FormalRuntimeBoundary:
    """Return the sole replayed boundary for supervisor/guardian closeout."""

    context = _campaign_context(campaign_dir)
    _validate_gate_approvals(context)
    preregistration, _identity = _path_preregistration(context)
    campaign = Path(context["directory"])
    return FormalRuntimeBoundary(
        campaign=campaign,
        context=context,
        formal_dir=Path(preregistration["formal_attempt_dir"]),
        preregistration=preregistration,
        root=context["root"],
    )


FORMAL_ROLE_SOURCES = {
    "baseline-admission": (
        "docs.research.noncert_cuts_ab16_20260724.baseline_admission_v1",
        "docs/research/noncert_cuts_ab16_20260724/baseline_admission_v1.py",
    ),
    "baseline-rebuild": (
        "docs.research.noncert_cuts_ab16_20260724.baseline_rebuild_v1",
        "docs/research/noncert_cuts_ab16_20260724/baseline_rebuild_v1.py",
    ),
    "cut-free-incumbent-replay": (
        "docs.research.noncert_cuts_ab16_20260724.cut_free_incumbent_replay_v1",
        "docs/research/noncert_cuts_ab16_20260724/cut_free_incumbent_replay_v1.py",
    ),
    "formal-controller": (
        "docs.research.noncert_cuts_ab16_20260724.ab16_formal_controller_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_controller_v1.py",
    ),
    "formal-launch-authority": (
        "docs.research.noncert_cuts_ab16_20260724.ab16_formal_launch_authority_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_launch_authority_v1.py",
    ),
    "formal-launch-validator": (
        "docs.research.noncert_cuts_ab16_20260724.ab16_formal_launch_validator_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_launch_validator_v1.py",
    ),
    "formal-orchestrator": (
        "docs.research.noncert_cuts_ab16_20260724.ab16_formal_orchestrator_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_orchestrator_v1.py",
    ),
    "formal-success-verifier": (
        "docs.research.noncert_cuts_ab16_20260724.ab16_formal_success_verifier_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_success_verifier_v1.py",
    ),
    "formal-supervisor": (
        "docs.research.noncert_cuts_ab16_20260724.ab16_formal_campaign_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_campaign_v1.py",
    ),
    "organic-arm": (
        "docs.research.noncert_cuts_ab16_20260724.organic_arm_runner_v1",
        "docs/research/noncert_cuts_ab16_20260724/organic_arm_runner_v1.py",
    ),
    "organic-supervisor": (
        "docs.research.noncert_cuts_ab16_20260724.organic_resource_lifecycle_v2",
        "docs/research/noncert_cuts_ab16_20260724/organic_resource_lifecycle_v2.py",
    ),
    "outer-guardian": (
        "docs.research.noncert_cuts_ab16_20260724.ab16_outer_guardian_v1",
        "docs/research/noncert_cuts_ab16_20260724/ab16_outer_guardian_v1.py",
    ),
}


def replay_loader_context(
    *,
    campaign_dir: Path | str,
    role: str,
    role_module: str,
    role_path: str,
) -> dict[str, object]:
    """Bind one isolated-loader role to the sealed source snapshot."""

    context = _campaign_context(campaign_dir)
    expected = FORMAL_ROLE_SOURCES.get(role)
    if expected != (role_module, role_path):
        raise AuthorityError("FORMAL_LOADER_ROLE_INVALID", role)
    snapshot = context["repository_snapshot"]
    identity = snapshot["member_identities"].get(role_path)
    if identity is None:
        raise AuthorityError("FORMAL_LOADER_ROLE_INVALID", f"{role} is absent from the sealed snapshot")
    root = context["root"]
    return {
        "authority_scope": "AB16_RESEARCH_ONLY",
        "campaign_dir": str(context["directory"]),
        "campaign_root_identity": context["root_identity"],
        "package_id": root["package"]["package_id"],
        "package_manifest_identity": root["package"]["manifest_identity"],
        "package_seal_identity": root["package"]["seal_identity"],
        "repository_head": root["repository_head"],
        "repository_tree": snapshot["repository_tree"],
        "role": role,
        "role_module": role_module,
        "role_source_identity": identity,
        "schema_version": "noncert-cuts-ab16-formal-loader-context-v1",
        "snapshot_materialization_identity": snapshot["materialization_identity"],
        "snapshot_root": snapshot["repository_root"],
        "status": "PASS",
    }


def replay_formal_launch_context(*, campaign_dir: Path | str) -> dict[str, object]:
    """Replay every upstream identity needed by the independent formal launch owner."""

    context = _campaign_context(campaign_dir)
    root = context["root"]
    approvals = _validate_gate_approvals(context)
    paths, _ = _path_preregistration(context)
    snapshot = context["repository_snapshot"]
    gate1_path = Path(root["stage_topology"]["gate1_v4"]["selection_path"])
    gate1_snapshot = snapshot_regular(gate1_path)
    gate1_identity = detached_identity(gate1_snapshot)
    try:
        context["campaign_module"].replay_gate1_selection(
            context["directory"] / "campaign-root.json",
            context["root_identity"],
            gate1_identity,
            current_manager_epoch=root["manager_epoch"],
        )
    except Exception as exc:
        raise AuthorityError("FORMAL_LAUNCH_CONTEXT_INVALID", f"Gate-1 selection: {exc}") from exc
    tools = {
        "baseline_identity": ("baseline_rebuild_v1", "tool.baseline_rebuild_v1.py"),
        "controller_identity": ("ab16_formal_controller_v1", "tool.ab16_formal_controller_v1.py"),
        "formal_loader_identity": ("ab16_formal_loader_v1", "tool.ab16_formal_loader_v1.py"),
        "formal_orchestrator_identity": (
            "ab16_formal_orchestrator_v1",
            "tool.ab16_formal_orchestrator_v1.py",
        ),
        "guardian_runtime_identity": ("ab16_outer_guardian_v1", "tool.ab16_outer_guardian_v1.py"),
        "launch_renderer_identity": (
            "ab16_formal_launch_authority_v1",
            "tool.ab16_formal_launch_authority_v1.py",
        ),
        "launch_validator_identity": (
            "ab16_formal_launch_validator_v1",
            "tool.ab16_formal_launch_validator_v1.py",
        ),
        "success_verifier_identity": (
            "ab16_formal_success_verifier_v1",
            "tool.ab16_formal_success_verifier_v1.py",
        ),
    }
    tool_identities = {
        name: _root_tool_identity(context, role, package_role)
        for name, (role, package_role) in tools.items()
    }
    python_with_mode = _root_tool_identity_with_mode(
        context,
        "python3_13",
        "system.python3_13.bin",
    )
    loader_with_mode = _root_tool_identity_with_mode(
        context,
        "ab16_formal_loader_v1",
        "tool.ab16_formal_loader_v1.py",
    )
    authority_with_mode = _root_tool_identity_with_mode(
        context,
        "ab16_authority_v2",
        "tool.ab16_authority_v2.py",
    )
    literal = _bootstrap_literal_values(context["files"], context["sources"])[
        "SELECTED_BYTE_LAUNCH_V1"
    ]
    literal_identity = {
        "sha256": hashlib.sha256(literal.encode("utf-8")).hexdigest(),
        "size_bytes": len(literal.encode("utf-8")),
    }
    selected_identities = {
        "authority": authority_with_mode,
        "loader": loader_with_mode,
        "python": python_with_mode,
    }
    selected_identity_argument = json.dumps(
        selected_identities,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    outer_spec = {
        "arm_prelaunch_paths": paths["arm_prelaunch_paths"],
        "barrier_path": paths["outer_barrier_path"],
        "child_audit_path": paths["child_audit_path"],
        "controller_identity": tool_identities["controller_identity"],
        "gate1_prelaunch_ownership_path": paths["gate1_prelaunch_ownership_path"],
        "loader_identity": tool_identities["formal_loader_identity"],
        "python_identity": {
            field: python_with_mode[field] for field in ("path", "sha256", "size_bytes")
        },
        "receipt_paths": paths["outer_receipt_paths"],
        "resource_contract": {
            "collect_mode": "inactive-or-failed",
            "kill_mode": "control-group",
            "memory_high_bytes": 35 * 1024**3,
            "memory_max_bytes": 39 * 1024**3,
            "memory_swap_max_bytes": 16 * 1024**3,
            "oom_policy": "continue",
            "runtime_max_sec": 57_600,
            "send_sigkill": True,
        },
        "selected_byte_argv": [
            "/proc/self/fd/3",
            "-I",
            "-B",
            "-c",
            literal,
            "systemd-openfile",
            selected_identity_argument,
            "--campaign-dir",
            str(context["directory"]),
            "--role",
            "formal-controller",
            "--",
            "--campaign-dir",
            str(context["directory"]),
            "--formal-selection",
            paths["formal_selection_path"],
        ],
        "unit_name": f"{root['unit_namespace']}-ab16-outer.service",
        "working_directory": snapshot["repository_root"],
    }
    guardian_spec = {
        "resource_contract": dict(outer_spec["resource_contract"]),
        "selected_byte_argv": [
            "/proc/self/fd/3",
            "-I",
            "-B",
            "-c",
            literal,
            "systemd-openfile",
            selected_identity_argument,
            "--campaign-dir",
            str(context["directory"]),
            "--role",
            "outer-guardian",
            "--",
            "--campaign-dir",
            str(context["directory"]),
            "--formal-admission",
            paths["formal_admission_path"],
            "--control-socket",
            paths["guardian_control_socket_path"],
            "--ready-output",
            paths["guardian_ready_path"],
        ],
        "unit_name": f"{root['unit_namespace']}-ab16-guardian.service",
        "working_directory": snapshot["repository_root"],
    }
    external_platform = snapshot["external_platform"]
    return {
        "authority_scope": "AB16_RESEARCH_ONLY",
        **tool_identities,
        "campaign_dir": str(context["directory"]),
        "campaign_root_identity": context["root_identity"],
        "dual_holder_platform_assumption": (
            "kernel/systemd/filesystem semantics and a non-hostile OS account preserve "
            "at least one of the separately-cgrouped supervisor or guardian lock "
            "holders until the finite residual-runtime ledger is absent; simultaneous "
            "loss of both holders or reboot is an external platform failure and can "
            "never produce a successful closeout"
        ),
        "formal_admission_path": paths["formal_admission_path"],
        "formal_attempt_dir": paths["formal_attempt_dir"],
        "formal_selection_path": paths["formal_selection_path"],
        "gate1_selection_identity": gate1_identity,
        "gate_b_approval_identity": approvals["gate_b_identity"],
        "gate_b_epoch_observation_identity": _detached_from_source(
            approvals["gate_b_epoch_identity"]
        ),
        "guardian_ready_path": paths["guardian_ready_path"],
        "guardian_control_socket_path": paths["guardian_control_socket_path"],
        "guardian_control_retired_socket_path": paths[
            "guardian_control_retired_socket_path"
        ],
        "guardian_spec": guardian_spec,
        "manager_epoch": root["manager_epoch"],
        "manager_epoch_observation_identity": _root_input_identity(
            context,
            "ab16_bootstrap_manager_epoch_capture",
            "input.ab16_bootstrap_manager_epoch_capture.json",
        ),
        "package_id": root["package"]["package_id"],
        "package_manifest_identity": root["package"]["manifest_identity"],
        "package_seal_identity": root["package"]["seal_identity"],
        "outer_spec": outer_spec,
        "formal_launch_owner_driver_identity": external_platform[
            "formal_launch_owner_driver"
        ],
        "mechanical_oexcl_publisher_identity": external_platform[
            "mechanical_oexcl_publisher"
        ],
        "python_identity": {
            field: python_with_mode[field] for field in ("path", "sha256", "size_bytes")
        },
        "repository_head": root["repository_head"],
        "schema_version": "noncert-cuts-ab16-formal-launch-context-v3",
        "snapshot_materialization_identity": snapshot["materialization_identity"],
        "snapshot_root": snapshot["repository_root"],
        "selected_byte_launch_identity": literal_identity,
        "status": "PASS",
    }


def _replay_detached(value: object, label: str) -> Snapshot:
    record = _exact_keys(value, {"path", "sha256", "size_bytes"}, label)
    if (
        type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
    ):
        raise AuthorityError("DETACHED_IDENTITY_INVALID", label)
    snapshot = snapshot_regular(record["path"])
    if detached_identity(snapshot) != record:
        raise AuthorityError("DETACHED_IDENTITY_DRIFT", label)
    return snapshot


def _replay_identity_with_optional_mode(
    value: object,
    label: str,
) -> Snapshot:
    if type(value) is not dict or not {"path", "sha256", "size_bytes"} <= set(value):
        raise AuthorityError("DETACHED_IDENTITY_INVALID", label)
    if set(value) - {"mode", "path", "sha256", "size_bytes"}:
        raise AuthorityError("DETACHED_IDENTITY_INVALID", label)
    detached = {key: value[key] for key in ("path", "sha256", "size_bytes")}
    snapshot = _replay_detached(detached, label)
    if "mode" in value and value["mode"] != snapshot.mode:
        raise AuthorityError("DETACHED_IDENTITY_DRIFT", f"{label} mode")
    return snapshot


def _normalized_identity(value: object, label: str) -> dict[str, object]:
    snapshot = _replay_identity_with_optional_mode(value, label)
    return detached_identity(snapshot)


def _observe_repository_head(context: Mapping[str, Any]) -> str:
    gate_a = _record(
        _source_snapshot(
            context["files"],
            context["sources"],
            "input.ab16_gate_a_receipt.json",
        ),
        "AB16 Gate-A",
    )
    repository_root = gate_a.get("repository_root")
    if type(repository_root) is not str or not Path(repository_root).is_absolute():
        raise AuthorityError("HEAD_REPLAY_FAILED", "Gate-A repository root")
    git_identity = context["root"]["authority_tools"].get("git")
    git_snapshot = _replay_detached(git_identity, "campaign git tool")
    try:
        completed = subprocess.run(
            [
                str(git_snapshot.path),
                "-C",
                repository_root,
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
        raise AuthorityError("HEAD_REPLAY_FAILED", str(exc)) from exc
    try:
        head = completed.stdout.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise AuthorityError("HEAD_REPLAY_FAILED", "non-ASCII output") from exc
    if completed.returncode != 0 or completed.stderr or HEAD_RE.fullmatch(head) is None:
        raise AuthorityError(
            "HEAD_REPLAY_FAILED",
            f"exit={completed.returncode}; stderr={completed.stderr!r}",
        )
    return head


def _continuation(context: Mapping[str, Any]) -> tuple[Mapping[str, Any], dict[str, object]]:
    root = context["root"]
    continuation_path = root["stage_topology"]["gate1_v4"]["continuation_path"]
    snapshot = snapshot_regular(continuation_path)
    continuation = _record(snapshot, "Gate-1 continuation")
    try:
        context["campaign_module"].validate_continuation_authorization(
            continuation,
            root=root,
        )
    except Exception as exc:
        raise AuthorityError("GATE1_CONTINUATION_INVALID", str(exc)) from exc
    replay_ids = continuation.get("detached_replay_identities")
    if type(replay_ids) is not dict or set(replay_ids) != set(GATE1_SLOTS):
        raise AuthorityError("GATE1_CONTINUATION_INVALID", "detached replay set")
    for slot in GATE1_SLOTS:
        _replay_detached(replay_ids[slot], f"Gate-1 continuation {slot}")
    if (
        continuation.get("schema_version") != CONTINUATION_SCHEMA
        or continuation.get("continuation_authorized") is not True
        or continuation.get("continuation_eligible") is not True
        or continuation.get("organic_arm_launch_authorized") is not False
        or continuation.get("campaign_closed") is not False
        or continuation.get("campaign_id") != root["campaign_id"]
        or continuation.get("run_nonce") != root["run_nonce"]
        or continuation.get("manager_epoch") != root["manager_epoch"]
        or continuation.get("campaign_root_identity") != context["root_identity"]
    ):
        raise AuthorityError("GATE1_CONTINUATION_INVALID", "fresh campaign/epoch binding")
    future = continuation.get("future_child")
    prospective = root["stage_topology"]["prospective_ab16"]
    if (
        type(future) is not dict
        or future.get("suite") != "prospective-ab16"
        or future.get("manifest_path") != prospective["manifest_path"]
        or future.get("arm_selection_path") != prospective["arm_selection_path"]
        or future.get("slots_absent") is not True
    ):
        raise AuthorityError("GATE1_CONTINUATION_INVALID", "future child binding")
    return continuation, detached_identity(snapshot)


def _launch_plan(root: Mapping[str, Any]) -> list[dict[str, object]]:
    arms = root["stage_topology"]["prospective_ab16"]["arms"]
    if type(arms) is not list or len(arms) != 16:
        raise AuthorityError("AB16_LAUNCH_PLAN_INVALID", "arm count")
    by_triplet: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for item in arms:
        record = _exact_keys(
            item,
            {"arm", "attempt_dir", "configuration", "order", "slot", "unit_name"},
            "campaign AB16 arm",
        )
        triplet = (record["configuration"], record["order"], record["arm"])
        if (
            triplet in by_triplet
            or triplet[0] not in CONFIGURATIONS
            or triplet[1] not in ORDERS
            or triplet[2] not in ARMS
            or record["slot"] != "-".join(triplet)
            or type(record["attempt_dir"]) is not str
            or not Path(record["attempt_dir"]).is_absolute()
            or type(record["unit_name"]) is not str
            or not record["unit_name"]
        ):
            raise AuthorityError("AB16_LAUNCH_PLAN_INVALID", "campaign arm")
        by_triplet[triplet] = record
    result: list[dict[str, object]] = []
    ordinal = 0
    for configuration in CONFIGURATIONS:
        for order in ORDERS:
            roles = ARMS if order == "ab" else tuple(reversed(ARMS))
            for arm in roles:
                ordinal += 1
                source = by_triplet[(configuration, order, arm)]
                attempt = Path(source["attempt_dir"])
                result.append(
                    {
                        **dict(source),
                        "arithmetic_replay_path": str(attempt / "replays/independent-arithmetic.json"),
                        "arm_gate_path": str(attempt / "replays/arm-credibility.json"),
                        "arm_selection_path": str(attempt / "selection.json"),
                        "cut_free_replay_path": str(attempt / "replays/cut-free-incumbent.json"),
                        "epoch_checkpoint_paths": {
                            phase: str(attempt / f"manager-epoch-{phase}.json")
                            for phase in (
                                "cleanup",
                                "detached-replay",
                                "launch",
                                "preterminal",
                                "reference-acquire",
                                "reference-release",
                                "release",
                                "terminal-first",
                                "terminal-stable",
                            )
                        },
                        "launch_ordinal": ordinal,
                        "raw_dir": str(attempt / "raw"),
                        "resource_replay_path": str(attempt / "replays/independent-resource-terminal.json"),
                        "result_path": str(attempt / "result.json"),
                        "terminal_dir": str(attempt / "terminal"),
                    }
                )
    if [item["slot"] for item in result] != EXPERIMENT_CONTRACT["order"]:
        raise AuthorityError("AB16_LAUNCH_PLAN_INVALID", "AB/BA order")
    return result


def _digest_without(record: Mapping[str, object], field: str) -> str:
    copied = dict(record)
    copied[field] = ""
    return hashlib.sha256(canonical_json(copied)).hexdigest()


def _source_identities(context: Mapping[str, Any]) -> dict[str, object]:
    return {role: dict(context["sources"][role]["source_identity"]) for role in sorted(REQUIRED_PACKAGE_ROLES)}


def _package_role_identity(
    context: Mapping[str, Any],
    role: str,
) -> dict[str, object]:
    """Return the detached identity of one package-pinned live source."""

    _source_snapshot(context["files"], context["sources"], role)
    return _detached_from_source(context["sources"][role]["source_identity"])


def _root_tool_identity(
    context: Mapping[str, Any],
    root_role: str,
    package_role: str,
) -> dict[str, object]:
    _source_snapshot(context["files"], context["sources"], package_role)
    identity = context["root"]["authority_tools"].get(root_role)
    _replay_detached(identity, f"campaign root tool {root_role}")
    return dict(identity)


def _root_tool_identity_with_mode(
    context: Mapping[str, Any],
    root_role: str,
    package_role: str,
) -> dict[str, object]:
    identity = _root_tool_identity(context, root_role, package_role)
    snapshot = _replay_detached(identity, f"campaign root tool {root_role}")
    return {
        "mode": snapshot.mode,
        **identity,
    }


def _root_input_identity(
    context: Mapping[str, Any],
    root_role: str,
    package_role: str,
) -> dict[str, object]:
    _source_snapshot(context["files"], context["sources"], package_role)
    identity = context["root"]["strict_inputs"].get(root_role)
    _replay_detached(identity, f"campaign root input {root_role}")
    return dict(identity)


def _runner_module(context: Mapping[str, Any]) -> ModuleType:
    snapshot = _source_snapshot(
        context["files"],
        context["sources"],
        "tool.organic_arm_runner_v1.py",
    )
    runner = _load_module(
        snapshot,
        f"_ab16_organic_runner_{snapshot.sha256[:16]}",
    )
    if (
        getattr(runner, "FORMAL_MANIFEST_SCHEMA", None) != MANIFEST_SCHEMA
        or getattr(runner, "SELECTION_SCHEMA", None) != ARM_SELECTION_SCHEMA
        or type(getattr(runner, "FORMAL_ARITHMETIC_PURPOSE", None)) is not str
    ):
        raise AuthorityError(
            "RUNNER_CONTRACT_DRIFT",
            "organic runner schema/purpose differs from the authority consumer",
        )
    return runner


def _path_preregistration(
    context: Mapping[str, Any],
) -> tuple[Mapping[str, Any], dict[str, object]]:
    """Replay the package/root-bound prospective AB16 path authority."""

    snapshot = _source_snapshot(
        context["files"],
        context["sources"],
        "input.ab16_path_preregistration.json",
    )
    record = _exact_keys(
        _record(snapshot, "AB16 path preregistration"),
        {
            "arithmetic_replay_paths",
            "arm_gate_paths",
            "arm_prelaunch_paths",
            "arm_selection_paths",
            "attempt_dirs",
            "baseline_admission_path",
            "baseline_fixed_replay_path",
            "baseline_incumbent_path",
            "baseline_campaign_provenance_path",
            "baseline_rebuilt_metadata_path",
            "baseline_rebuilt_model_path",
            "binding_paths",
            "campaign_dir",
            "classification_contract_path",
            "child_audit_path",
            "common_prestate_path",
            "cut_free_replay_paths",
            "formal_admission_path",
            "formal_attempt_dir",
            "formal_selection_path",
            "gate1_prelaunch_ownership_path",
            "guardian_control_socket_path",
            "guardian_control_retired_socket_path",
            "guardian_ready_path",
            "immediate_stop_path",
            "launch_environment_paths",
            "manifest_path",
            "outer_barrier_path",
            "outer_receipt_paths",
            "preselection_epoch_paths",
            "preselection_transcript_paths",
            "pre_run_candidate_paths",
            "pre_run_authority_paths",
            "repository_snapshot_archive_path",
            "repository_snapshot_manifest_path",
            "repository_snapshot_materialization_receipt_path",
            "repository_snapshot_root",
            "resource_replay_paths",
            "purpose",
            "run_nonce",
            "schema",
            "suite_selection_path",
            "terminal_classification_path",
        },
        "AB16 path preregistration",
    )
    root = context["root"]
    prospective = root["stage_topology"]["prospective_ab16"]
    slots = [item["slot"] for item in _launch_plan(root)]
    if (
        record["schema"] != PATH_PREREGISTRATION_SCHEMA
        or record["purpose"] != "prospective_noncert_cuts_ab16_path_authority"
        or record["campaign_dir"] != str(context["directory"])
        or record["run_nonce"] != root["run_nonce"]
        or record["manifest_path"] != prospective["manifest_path"]
        or record["suite_selection_path"] != prospective["arm_selection_path"]
        or record["terminal_classification_path"] != prospective["terminal_classification_path"]
    ):
        raise AuthorityError(
            "PATH_PREREGISTRATION_INVALID",
            "campaign/root scalar binding",
        )
    path_fields = (
        "baseline_admission_path",
        "baseline_fixed_replay_path",
        "baseline_incumbent_path",
        "baseline_campaign_provenance_path",
        "baseline_rebuilt_metadata_path",
        "baseline_rebuilt_model_path",
        "classification_contract_path",
        "child_audit_path",
        "common_prestate_path",
        "formal_admission_path",
        "formal_attempt_dir",
        "formal_selection_path",
        "gate1_prelaunch_ownership_path",
        "guardian_control_socket_path",
        "guardian_control_retired_socket_path",
        "guardian_ready_path",
        "immediate_stop_path",
        "manifest_path",
        "outer_barrier_path",
        "repository_snapshot_archive_path",
        "repository_snapshot_manifest_path",
        "repository_snapshot_materialization_receipt_path",
        "repository_snapshot_root",
        "suite_selection_path",
        "terminal_classification_path",
    )
    prospective_dir = Path(prospective["manifest_path"]).parent
    authority_path_fields = {
        "classification_contract_path",
        "repository_snapshot_archive_path",
        "repository_snapshot_manifest_path",
        "repository_snapshot_materialization_receipt_path",
        "repository_snapshot_root",
    }
    formal_path_fields = {
        "child_audit_path",
        "formal_admission_path",
        "formal_attempt_dir",
        "formal_selection_path",
        "gate1_prelaunch_ownership_path",
        "guardian_control_socket_path",
        "guardian_control_retired_socket_path",
        "guardian_ready_path",
        "outer_barrier_path",
    }
    formal_dir = context["directory"] / "formal-ab16"
    for field in path_fields:
        value = record[field]
        if (
            type(value) is not str
            or not Path(value).is_absolute()
            or Path(value) == context["directory"]
            or (
                field not in authority_path_fields | formal_path_fields
                and prospective_dir not in (Path(value), *Path(value).parents)
            )
            or (
                field in formal_path_fields
                and formal_dir not in (Path(value), *Path(value).parents)
            )
        ):
            raise AuthorityError(
                "PATH_PREREGISTRATION_INVALID",
                f"{field} is not an absolute prospective child path",
            )
    formal_attempt = formal_dir / "formal-attempt-a001"
    if (
        Path(record["formal_admission_path"]) != formal_dir / "formal-launch-admission-a001.json"
        or Path(record["formal_attempt_dir"]) != formal_attempt
        or Path(record["formal_selection_path"]) != formal_attempt / "selection.json"
        or Path(record["gate1_prelaunch_ownership_path"])
        != formal_attempt / "gate1-prelaunch-ownership.json"
        or Path(record["child_audit_path"]) != formal_attempt / "child-audit.json"
        or Path(record["guardian_control_socket_path"]) != formal_dir / "guardian-control.sock"
        or Path(record["guardian_control_retired_socket_path"])
        != formal_dir / "guardian-control.sock.retired"
        or Path(record["guardian_ready_path"]) != formal_dir / "outer-guardian-ready-a001.json"
        or Path(record["outer_barrier_path"]) != formal_attempt / "outer-barrier-release.json"
    ):
        raise AuthorityError(
            "PATH_PREREGISTRATION_INVALID",
            "formal launch paths differ from the one-shot topology",
        )
    maps: dict[str, Mapping[str, Any]] = {}
    for field in (
        "arithmetic_replay_paths",
        "arm_gate_paths",
        "arm_selection_paths",
        "attempt_dirs",
        "binding_paths",
        "cut_free_replay_paths",
        "launch_environment_paths",
        "preselection_epoch_paths",
        "preselection_transcript_paths",
        "pre_run_candidate_paths",
        "pre_run_authority_paths",
        "resource_replay_paths",
    ):
        value = _exact_keys(record[field], set(slots), f"path preregistration {field}")
        if len(set(value.values())) != len(slots):
            raise AuthorityError(
                "PATH_PREREGISTRATION_INVALID",
                f"{field} paths are not unique",
            )
        maps[field] = value
    arm_prelaunch = _exact_keys(
        record["arm_prelaunch_paths"],
        set(slots),
        "path preregistration arm_prelaunch_paths",
    )
    for slot, item in arm_prelaunch.items():
        pair = _exact_keys(
            item,
            {"receipt", "request"},
            f"path preregistration arm_prelaunch_paths.{slot}",
        )
        expected_parent = formal_attempt / "arm-prelaunch"
        if (
            Path(pair["receipt"]) != expected_parent / f"{slot}-receipt.json"
            or Path(pair["request"]) != expected_parent / f"{slot}-request.json"
        ):
            raise AuthorityError(
                "PATH_PREREGISTRATION_INVALID",
                f"arm_prelaunch_paths.{slot} drifted",
            )
    outer_receipts = _exact_keys(
        record["outer_receipt_paths"],
        {
            "detached_closeout",
            "detached_incomplete_closeout",
            "dual_lock_release",
            "guardian_absence",
            "guardian_lock_close",
            "observer",
            "outer_prelaunch",
            "outer_resource",
            "outer_start",
            "outer_terminal",
            "post_unref_absence",
            "pre_unref_cleanup",
            "reference_acquisition",
            "reference_release",
        },
        "path preregistration outer_receipt_paths",
    )
    for name, raw in outer_receipts.items():
        expected_names = {
            "detached_closeout": "detached-closeout.json",
            "detached_incomplete_closeout": "detached-incomplete-closeout.json",
            "dual_lock_release": "dual-lock-release.json",
            "guardian_absence": "guardian-absence.json",
            "guardian_lock_close": "guardian-lock-close.json",
            "observer": "observer.json",
            "outer_prelaunch": "outer-prelaunch.json",
            "outer_resource": "resource-live.json",
            "outer_start": "outer-start.json",
            "outer_terminal": "outer-terminal.json",
            "post_unref_absence": "post-unref-absence.json",
            "pre_unref_cleanup": "pre-unref-cleanup.json",
            "reference_acquisition": "reference-acquisition.json",
            "reference_release": "reference-release.json",
        }
        if Path(raw) != formal_attempt / expected_names[name]:
            raise AuthorityError(
                "PATH_PREREGISTRATION_INVALID",
                f"outer_receipt_paths.{name} drifted",
            )
    root_attempts = {item["slot"]: item["attempt_dir"] for item in prospective["arms"]}
    if dict(maps["attempt_dirs"]) != root_attempts:
        raise AuthorityError(
            "PATH_PREREGISTRATION_INVALID",
            "attempt dirs differ from campaign root",
        )
    for slot in slots:
        attempt = Path(str(maps["attempt_dirs"][slot]))
        expected = {
            "arithmetic_replay_paths": (attempt / "replays/independent-arithmetic.json"),
            "arm_gate_paths": attempt / "replays/arm-credibility.json",
            "arm_selection_paths": attempt / "selection.json",
            "cut_free_replay_paths": (attempt / "replays/cut-free-incumbent.json"),
            "pre_run_authority_paths": attempt / "pre-run-authority.json",
            "resource_replay_paths": (attempt / "replays/independent-resource-terminal.json"),
        }
        for field, path in expected.items():
            if Path(str(maps[field][slot])) != path:
                raise AuthorityError(
                    "PATH_PREREGISTRATION_INVALID",
                    f"{field}.{slot} is not derived from attempt_dir",
                )
        binding = Path(str(maps["binding_paths"][slot]))
        if (
            not binding.is_absolute()
            or binding.parent != prospective_dir / "bindings"
            or binding.name != f"{slot}.json"
        ):
            raise AuthorityError(
                "PATH_PREREGISTRATION_INVALID",
                f"binding path drift for {slot}",
            )
        candidate = Path(str(maps["pre_run_candidate_paths"][slot]))
        if (
            not candidate.is_absolute()
            or candidate.parent != prospective_dir / "pre-run-candidates"
            or candidate.name != f"{slot}.json"
        ):
            raise AuthorityError(
                "PATH_PREREGISTRATION_INVALID",
                f"pre-run candidate path drift for {slot}",
            )
        candidate_parent = prospective_dir / "pre-run-candidates"
        expected_candidate_artifacts = {
            "launch_environment_paths": (candidate_parent / f"{slot}-launch-environment.json"),
            "preselection_epoch_paths": (candidate_parent / f"{slot}-preselection-epoch.json"),
            "preselection_transcript_paths": (candidate_parent / f"{slot}-preselection-transcript.json"),
        }
        for field, expected_path in expected_candidate_artifacts.items():
            if Path(str(maps[field][slot])) != expected_path:
                raise AuthorityError(
                    "PATH_PREREGISTRATION_INVALID",
                    f"{field}.{slot} is not the canonical candidate child",
                )
    expected_fixed_paths = {
        "baseline_admission_path": prospective_dir / "baseline-admission-a001.json",
        "baseline_fixed_replay_path": prospective_dir / "baseline/fixed-replay-a001.json",
        "baseline_incumbent_path": prospective_dir / "baseline/incumbent.json",
        "baseline_campaign_provenance_path": prospective_dir / "baseline/campaign-provenance.json",
        "baseline_rebuilt_metadata_path": (prospective_dir / "baseline/rebuilt-model-metadata.json"),
        "baseline_rebuilt_model_path": (prospective_dir / "baseline/cut-free-model.bin"),
        "classification_contract_path": (
            context["directory"] / "campaign-authority/package/payload/tool.ab16_contract_v1.py"
        ),
        "common_prestate_path": prospective_dir / "common-prestate-a001.json",
        "immediate_stop_path": prospective_dir / "immediate-stop-a001.json",
        "repository_snapshot_archive_path": (
            context["directory"]
            / "campaign-authority/package/payload/input.ab16_repository_snapshot.zip"
        ),
        "repository_snapshot_manifest_path": (
            context["directory"]
            / "campaign-authority/package/payload/input.ab16_repository_snapshot.json"
        ),
        "repository_snapshot_materialization_receipt_path": (
            context["directory"]
            / "campaign-authority/source-snapshot-a001/materialization-receipt.json"
        ),
        "repository_snapshot_root": (
            context["directory"] / "campaign-authority/source-snapshot-a001/repository"
        ),
    }
    for field, expected in expected_fixed_paths.items():
        if Path(str(record[field])) != expected:
            raise AuthorityError(
                "PATH_PREREGISTRATION_INVALID",
                f"{field} differs from the canonical campaign child path",
            )
    return record, _root_input_identity(
        context,
        "ab16_path_preregistration",
        "input.ab16_path_preregistration.json",
    )


def _expected_runtime_parameters(runner: ModuleType) -> dict[str, object]:
    contract = runner.EXPERIMENT_CONTRACT
    budget = contract["budget"]
    solver = contract["solver_parameters"]
    return {
        "attach_iteration": 1,
        "attach_trigger": "after_byte_locked_cut_free_baseline_before_attach",
        "binding_alt_cap": solver["binding_alt_cap"],
        "binding_seconds": budget["binding_seconds"],
        "ghost_rect": list(solver["ghost_rectangle"]),
        "master_seconds": budget["master_seconds"],
        "max_iterations": budget["max_iterations"],
        "post_attach_seconds": budget["post_attach_seconds"],
        "routing_seconds": budget["routing_seconds"],
    }


def _baseline_manifest_inputs(
    context: Mapping[str, Any],
) -> dict[str, object]:
    preregistration, preregistration_identity = _path_preregistration(context)
    paths = {
        name: snapshot_regular(preregistration[name])
        for name in (
            "baseline_admission_path",
            "baseline_incumbent_path",
            "classification_contract_path",
        )
    }
    baseline = _replay_baseline_admission(
        context,
        paths["baseline_admission_path"],
    )
    incumbent_identity = detached_identity(paths["baseline_incumbent_path"])
    fixed_replay = baseline.get("fixed_assignment_replay")
    expected_baseline = baseline.get("expected_baseline")
    if (
        type(fixed_replay) is not dict
        or fixed_replay.get("incumbent_identity") != incumbent_identity
        or type(expected_baseline) is not dict
        or expected_baseline.get("incumbent_sha256") != incumbent_identity["sha256"]
    ):
        raise AuthorityError(
            "BASELINE_ADMISSION_INVALID",
            "incumbent identity/digest does not join the preregistered bytes",
        )
    return {
        "baseline": baseline,
        "baseline_admission_identity": detached_identity(paths["baseline_admission_path"]),
        "baseline_incumbent_identity": incumbent_identity,
        "classification_contract_identity": detached_identity(paths["classification_contract_path"]),
        "path_preregistration": preregistration,
        "path_preregistration_identity": preregistration_identity,
    }


def _common_prestate_expected(
    context: Mapping[str, Any],
    *,
    inputs: Mapping[str, Any],
    runner: ModuleType,
) -> dict[str, object]:
    baseline = inputs["baseline"]
    approvals = _validate_gate_approvals(context)
    return {
        "authorizations": {
            "arm_launch_authorized": False,
            "global_claim_authorized": False,
            "manifest_published": False,
            "mathematical_claim_authorized": False,
            "production_certified_authorized": False,
            "solver_run_authorized": False,
        },
        "baseline_admission_identity": inputs["baseline_admission_identity"],
        "baseline_incumbent_identity": baseline["fixed_assignment_replay"]["incumbent_identity"],
        "builder_identity": _root_tool_identity(
            context,
            "ab16_authority_v2",
            "tool.ab16_authority_v2.py",
        ),
        "campaign_id": context["root"]["campaign_id"],
        "classification_contract_identity": inputs["classification_contract_identity"],
        "experiment_contract": runner.EXPERIMENT_CONTRACT,
        "fixed_assignment_replay_identity": baseline["fixed_assignment_replay"]["receipt_identity"],
        "purpose": COMMON_PRESTATE_PURPOSE,
        "rebuilt_metadata_identity": baseline["rebuilt_model"]["metadata"]["metadata_identity"],
        "rebuilt_model_identity": baseline["rebuilt_model"]["identity"],
        "repository_head": context["root"]["repository_head"],
        "repository_root": approvals["repository_root"],
        "run_nonce": context["root"]["run_nonce"],
        "runtime_parameters": _expected_runtime_parameters(runner),
        "schema_version": COMMON_PRESTATE_SCHEMA,
        "seed": runner.EXPERIMENT_CONTRACT["solver_parameters"]["random_seed"],
        "status": "PASS",
        "verdict": "AB16_COMMON_PRESTATE_FROZEN",
        "workers": 1,
    }


def _binding_expected(
    context: Mapping[str, Any],
    *,
    common_prestate_identity: Mapping[str, Any],
    plan: Mapping[str, Any],
    runner: ModuleType,
) -> dict[str, object]:
    enabled = [] if plan["arm"] == "control" else list(runner.CONFIGURATION_FAMILIES[plan["configuration"]])
    return {
        "arm": plan["arm"],
        "attempt_dir": plan["attempt_dir"],
        "authorizations": {
            "arm_launch_authorized": False,
            "manifest_published": False,
            "solver_run_authorized": False,
        },
        "builder_identity": _root_tool_identity(
            context,
            "ab16_authority_v2",
            "tool.ab16_authority_v2.py",
        ),
        "campaign_id": context["root"]["campaign_id"],
        "common_prestate_identity": dict(common_prestate_identity),
        "configuration": plan["configuration"],
        "enabled_families": enabled,
        "order": plan["order"],
        "purpose": ARM_BINDING_PURPOSE,
        "repository_head": context["root"]["repository_head"],
        "run_nonce": context["root"]["run_nonce"],
        "schema_version": ARM_BINDING_SCHEMA,
        "slot": plan["slot"],
        "status": "PASS",
        "unit_name": plan["unit_name"],
        "verdict": "AB16_ARM_BINDING_FROZEN",
    }


def _empty_child_directory(path: Path, label: str) -> None:
    if path.exists() or path.is_symlink():
        _assert_no_symlink_chain(path)
        if not path.is_dir() or any(path.iterdir()):
            raise AuthorityError("PRE_MANIFEST_CHILD_INVALID", label)
        return
    _mkdir_exclusive(path)


def _build_pre_manifest_inputs(
    context: Mapping[str, Any],
    *,
    inputs: Mapping[str, Any],
    runner: ModuleType,
) -> None:
    preregistration = inputs["path_preregistration"]
    common_path = _absolute(preregistration["common_prestate_path"])
    binding_paths = {slot: _absolute(path) for slot, path in preregistration["binding_paths"].items()}
    if (
        common_path.exists()
        or common_path.is_symlink()
        or any(path.exists() or path.is_symlink() for path in binding_paths.values())
    ):
        raise AuthorityError(
            "PRE_MANIFEST_INPUT_ALREADY_CONSUMED",
            "common prestate or arm binding already exists",
        )
    prospective = common_path.parent
    _assert_no_symlink_chain(prospective)
    if not prospective.is_dir():
        raise AuthorityError(
            "PRE_MANIFEST_PARENT_INVALID",
            "prospective child parent does not exist",
        )
    binding_parent = next(iter(binding_paths.values())).parent
    _empty_child_directory(binding_parent, "binding directory")
    _empty_child_directory(prospective / "arms", "attempt directory parent")
    _empty_child_directory(
        prospective / "pre-run-candidates",
        "pre-run candidate directory",
    )
    common = _common_prestate_expected(
        context,
        inputs=inputs,
        runner=runner,
    )
    common_identity = _write_exclusive(common_path, runner.canonical_json(common))
    plans = {item["slot"]: item for item in _launch_plan(context["root"])}
    for slot in runner.ARM_SEQUENCE:
        binding = _binding_expected(
            context,
            common_prestate_identity=common_identity,
            plan=plans[slot],
            runner=runner,
        )
        _write_exclusive(
            binding_paths[slot],
            runner.canonical_json(binding),
        )


def _manifest_inputs(
    context: Mapping[str, Any],
) -> dict[str, object]:
    result = _baseline_manifest_inputs(context)
    preregistration = result["path_preregistration"]
    runner = _runner_module(context)
    common_snapshot = snapshot_regular(preregistration["common_prestate_path"])
    common = _record(common_snapshot, "AB16 common prestate")
    expected_common = _common_prestate_expected(
        context,
        inputs=result,
        runner=runner,
    )
    if common != expected_common:
        raise AuthorityError(
            "COMMON_PRESTATE_INVALID",
            "common prestate semantics differ from replayed baseline/contract",
        )
    common_identity = detached_identity(common_snapshot)
    plans = {item["slot"]: item for item in _launch_plan(context["root"])}
    binding_identities: dict[str, dict[str, object]] = {}
    for slot in runner.ARM_SEQUENCE:
        snapshot = snapshot_regular(preregistration["binding_paths"][slot])
        binding = _record(snapshot, f"AB16 arm binding {slot}")
        expected_binding = _binding_expected(
            context,
            common_prestate_identity=common_identity,
            plan=plans[slot],
            runner=runner,
        )
        if binding != expected_binding:
            raise AuthorityError(
                "ARM_BINDING_INVALID",
                f"{slot} semantics differ from the preregistered arm",
            )
        binding_identities[slot] = detached_identity(snapshot)
    result.update(
        {
            "binding_identities": binding_identities,
            "common_prestate_identity": common_identity,
        }
    )
    return result


def _organic_authority_chain(
    context: Mapping[str, Any],
    continuation_identity: Mapping[str, Any],
) -> dict[str, object]:
    root = context["root"]
    return {
        "campaign_root_identity": context["root_identity"],
        "continuation_identity": dict(continuation_identity),
        "manager_epoch_authority_identity": _root_input_identity(
            context,
            "ab16_bootstrap_manager_epoch_capture",
            "input.ab16_bootstrap_manager_epoch_capture.json",
        ),
        "package": {
            "manifest_identity": root["package"]["manifest_identity"],
            "package_id": root["package"]["package_id"],
            "seal_identity": root["package"]["seal_identity"],
        },
    }


def _per_arm_tool_identities(
    context: Mapping[str, Any],
) -> dict[str, dict[str, object]]:
    return {
        "cut_free_replay": _root_tool_identity(
            context,
            "cut_free_incumbent_replay_v1",
            "tool.cut_free_incumbent_replay_v1.py",
        ),
        "resource_lifecycle": _root_tool_identity(
            context,
            "organic_resource_lifecycle_v2",
            "tool.organic_resource_lifecycle_v2.py",
        ),
        "resource_verifier": _root_tool_identity(
            context,
            "organic_resource_verifier_v2",
            "tool.organic_resource_verifier_v2.py",
        ),
        "terminal_gate": _root_tool_identity(
            context,
            "ab16_terminal_gate_v2",
            "tool.ab16_terminal_gate_v2.py",
        ),
        "terminal_replay": _root_tool_identity(
            context,
            "organic_arm_replay_v1",
            "tool.organic_arm_replay_v1.py",
        ),
        "unit_orchestrator": _root_tool_identity(
            context,
            "organic_unit_orchestrator_v2",
            "tool.organic_unit_orchestrator_v2.py",
        ),
    }


def build_manifest(campaign_dir: Path | str) -> dict[str, object]:
    """Publish the runner-exact manifest only after continuation and baseline PASS."""

    context = _campaign_context(campaign_dir)
    approvals = _validate_gate_approvals(context)
    continuation, continuation_identity = _continuation(context)
    runner = _runner_module(context)
    baseline_inputs = _baseline_manifest_inputs(context)
    root = context["root"]
    preregistration = baseline_inputs["path_preregistration"]
    output = _absolute(preregistration["manifest_path"])
    suite_selection = _absolute(preregistration["suite_selection_path"])
    terminal = _absolute(preregistration["terminal_classification_path"])
    immediate_stop = _absolute(preregistration["immediate_stop_path"])
    if any(path.exists() or path.is_symlink() for path in (output, suite_selection, terminal, immediate_stop)):
        raise AuthorityError(
            "PROSPECTIVE_CHILD_ALREADY_CONSUMED",
            "manifest, suite selection, terminal, or immediate-stop already exists",
        )
    for path in preregistration["attempt_dirs"].values():
        absolute = _absolute(path)
        if absolute.exists() or absolute.is_symlink():
            raise AuthorityError("PROSPECTIVE_CHILD_ALREADY_CONSUMED", str(absolute))
    _build_pre_manifest_inputs(
        context,
        inputs=baseline_inputs,
        runner=runner,
    )
    inputs = _manifest_inputs(context)
    launch_plan = _launch_plan(root)
    attempts = {item["slot"]: item["attempt_dir"] for item in launch_plan}
    unit_names = {item["slot"]: item["unit_name"] for item in launch_plan}
    record: dict[str, object] = {
        "arithmetic_verifier": {
            "purpose": runner.FORMAL_ARITHMETIC_PURPOSE,
            "tool_identity": _root_tool_identity(
                context,
                "organic_arm_replay_v1",
                "tool.organic_arm_replay_v1.py",
            ),
        },
        "arm_binding_identities": inputs["binding_identities"],
        "arm_sequence": list(runner.ARM_SEQUENCE),
        "attempt_dirs": attempts,
        "authority_chain": _organic_authority_chain(
            context,
            continuation_identity,
        ),
        "authorizations": {
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "organic_arm_launch_authorized": True,
            "production_certified_authorized": False,
        },
        "baseline_admission_identity": inputs["baseline_admission_identity"],
        "baseline_incumbent_identity": inputs["baseline_incumbent_identity"],
        "campaign_id": root["campaign_id"],
        "classification_contract_identity": inputs["classification_contract_identity"],
        "common_prestate_identity": inputs["common_prestate_identity"],
        "configuration_families": {
            configuration: list(families) for configuration, families in runner.CONFIGURATION_FAMILIES.items()
        },
        "experiment_contract": runner.EXPERIMENT_CONTRACT,
        "forbidden_families": list(runner.FORBIDDEN_FAMILIES),
        "live_source_provenance_root": approvals["repository_root"],
        "per_arm_tool_identities": _per_arm_tool_identities(context),
        "purpose": runner.MANIFEST_PURPOSE,
        "repository_git_tool_identity": _root_tool_identity_with_mode(
            context,
            "git",
            "system.git.bin",
        ),
        "repository_head": root["repository_head"],
        "repository_root": approvals["repository_root"],
        "run_nonce": root["run_nonce"],
        "runner_tool_identity": _root_tool_identity(
            context,
            "organic_arm_runner_v1",
            "tool.organic_arm_runner_v1.py",
        ),
        "runtime_parameters": _expected_runtime_parameters(runner),
        "schema_version": runner.FORMAL_MANIFEST_SCHEMA,
        "sealed_snapshot_execution_root": context["repository_snapshot"]["repository_root"],
        "seed": runner.EXPERIMENT_CONTRACT["solver_parameters"]["random_seed"],
        "snapshot_manifest_identity": context["repository_snapshot"]["manifest_identity"],
        "snapshot_materialization_receipt_identity": context["repository_snapshot"][
            "materialization_identity"
        ],
        "unit_names": unit_names,
        "workers": 1,
    }
    validate_manifest(record, context=context, continuation=continuation)
    _assert_no_symlink_chain(output.parent)
    if not output.parent.is_dir():
        raise AuthorityError(
            "MANIFEST_PARENT_INVALID",
            "baseline/common/binding parent must already exist",
        )
    identity = _write_exclusive(output, runner.canonical_json(record))
    return {"manifest": record, "manifest_identity": identity, "status": "PASS"}


def validate_manifest(
    value: object,
    *,
    context: Mapping[str, Any],
    continuation: Mapping[str, Any],
) -> Mapping[str, Any]:
    _repository_snapshot_barrier(context)
    runner = _runner_module(context)
    try:
        record = runner.validate_manifest(value)
    except Exception as exc:
        raise AuthorityError("MANIFEST_INVALID", str(exc)) from exc
    root = context["root"]
    inputs = _manifest_inputs(context)
    preregistration = inputs["path_preregistration"]
    continuation_snapshot = _replay_detached(
        record["authority_chain"]["continuation_identity"],
        "manifest continuation",
    )
    if _record(continuation_snapshot, "manifest continuation") != continuation:
        raise AuthorityError("MANIFEST_INVALID", "continuation bytes")
    expected_launch = _launch_plan(root)
    if (
        record["campaign_id"] != root["campaign_id"]
        or record["repository_head"] != root["repository_head"]
        or record["run_nonce"] != root["run_nonce"]
        or record["arm_sequence"] != [item["slot"] for item in expected_launch]
        or record["attempt_dirs"] != preregistration["attempt_dirs"]
        or record["unit_names"] != {item["slot"]: item["unit_name"] for item in expected_launch}
        or record["authority_chain"]
        != _organic_authority_chain(
            context,
            record["authority_chain"]["continuation_identity"],
        )
        or record["baseline_admission_identity"] != inputs["baseline_admission_identity"]
        or record["baseline_incumbent_identity"] != inputs["baseline_incumbent_identity"]
        or record["classification_contract_identity"] != inputs["classification_contract_identity"]
        or record["common_prestate_identity"] != inputs["common_prestate_identity"]
        or record["arm_binding_identities"] != inputs["binding_identities"]
        or record["per_arm_tool_identities"] != _per_arm_tool_identities(context)
        or record["runner_tool_identity"]
        != _root_tool_identity(
            context,
            "organic_arm_runner_v1",
            "tool.organic_arm_runner_v1.py",
        )
        or record["repository_git_tool_identity"]
        != _root_tool_identity_with_mode(
            context,
            "git",
            "system.git.bin",
        )
        or record["repository_root"] != _validate_gate_approvals(context)["repository_root"]
        or record["live_source_provenance_root"]
        != _validate_gate_approvals(context)["repository_root"]
        or record["sealed_snapshot_execution_root"]
        != context["repository_snapshot"]["repository_root"]
        or record["snapshot_manifest_identity"]
        != context["repository_snapshot"]["manifest_identity"]
        or record["snapshot_materialization_receipt_identity"]
        != context["repository_snapshot"]["materialization_identity"]
        or record["arithmetic_verifier"]
        != {
            "purpose": runner.FORMAL_ARITHMETIC_PURPOSE,
            "tool_identity": _root_tool_identity(
                context,
                "organic_arm_replay_v1",
                "tool.organic_arm_replay_v1.py",
            ),
        }
        or record["runtime_parameters"] != _expected_runtime_parameters(runner)
    ):
        raise AuthorityError("MANIFEST_INVALID", "authority/path/input binding")
    return record


def _campaign_provenance_expected(context: Mapping[str, Any]) -> dict[str, object]:
    snapshot = context["repository_snapshot"]
    return {
        "import_mode": "ordinary_pathfinder",
        "materialization_receipt_identity": snapshot["materialization_identity"],
        "package_id": context["root"]["package"]["package_id"],
        "repository_head": context["root"]["repository_head"],
        "schema_version": "noncert-cuts-ab16-campaign-snapshot-provenance-v1",
        "snapshot_manifest_identity": snapshot["manifest_identity"],
        "snapshot_root": snapshot["repository_root"],
    }


def prepare_baseline_output(campaign_dir: Path | str) -> dict[str, object]:
    """Create the sole ABSENT -> PROVENANCE_ONLY baseline prestate."""

    context = _campaign_context(campaign_dir)
    _validate_gate_approvals(context)
    _continuation(context)
    _repository_snapshot_barrier(context)
    preregistration, _ = _path_preregistration(context)
    provenance_path = Path(preregistration["baseline_campaign_provenance_path"])
    baseline_dir = provenance_path.parent
    prospective_dir = baseline_dir.parent
    expected_dirs = (
        prospective_dir,
        baseline_dir,
        prospective_dir / "arms",
        prospective_dir / "bindings",
        prospective_dir / "pre-run-candidates",
    )
    if any(path.exists() or path.is_symlink() for path in expected_dirs):
        raise AuthorityError(
            "BASELINE_PRESTATE_ALREADY_CONSUMED",
            "prospective AB16 layout already exists",
        )
    _mkdir_exclusive(prospective_dir)
    _mkdir_exclusive(baseline_dir)
    _mkdir_exclusive(prospective_dir / "arms")
    _mkdir_exclusive(prospective_dir / "bindings")
    _mkdir_exclusive(prospective_dir / "pre-run-candidates")
    provenance = _campaign_provenance_expected(context)
    identity = _write_exclusive(
        provenance_path,
        canonical_json(provenance),
        mode=0o444,
    )
    if (
        set(os.listdir(baseline_dir)) != {"campaign-provenance.json"}
        or _record(snapshot_regular(provenance_path), "AB16 campaign provenance") != provenance
    ):
        raise AuthorityError("BASELINE_PRESTATE_INVALID", "PROVENANCE_ONLY readback")
    return {
        "baseline_dir": str(baseline_dir),
        "campaign_provenance": provenance,
        "campaign_provenance_identity": identity,
        "status": "PROVENANCE_ONLY",
    }


def _replay_baseline_admission(
    context: Mapping[str, Any],
    receipt_snapshot: Snapshot,
) -> Mapping[str, Any]:
    receipt = _record(receipt_snapshot, "baseline admission")
    if (
        receipt.get("schema_version") != BASELINE_ADMISSION_SCHEMA
        or receipt.get("status") != "PASS"
        or receipt.get("verdict") != "AB16_BASELINE_INPUTS_ADMITTED"
    ):
        raise AuthorityError("BASELINE_ADMISSION_INVALID", "status/schema")
    authorizations = receipt.get("authorizations")
    if authorizations != {
        "baseline_inputs_admitted": True,
        "global_claim_authorized": False,
        "mathematical_claim_authorized": False,
        "organic_arm_launch_authorized": False,
        "solver_run_authorized": False,
    }:
        raise AuthorityError("BASELINE_ADMISSION_INVALID", "claim boundary")
    admission_tool = _load_module(
        _source_snapshot(
            context["files"],
            context["sources"],
            "tool.baseline_admission_v1.py",
        ),
        f"_ab16_baseline_admission_{receipt_snapshot.sha256[:16]}",
    )
    preregistration, _ = _path_preregistration(context)
    provenance_snapshot = snapshot_regular(preregistration["baseline_campaign_provenance_path"])
    if _record(provenance_snapshot, "AB16 campaign provenance") != _campaign_provenance_expected(context):
        raise AuthorityError("BASELINE_ADMISSION_ROOT_JOIN_FAILED", "campaign provenance")
    legacy_identity = context["root"]["strict_inputs"]["legacy_control_a002"]
    try:
        replayed = admission_tool.admit_paths(
            campaign_provenance_path=provenance_snapshot.path,
            legacy_control=legacy_identity["path"],
            rebuilt_model=receipt["rebuilt_model"]["identity"]["path"],
            rebuilt_metadata=receipt["rebuilt_model"]["metadata"]["metadata_identity"]["path"],
            fixed_assignment_replay=receipt["fixed_assignment_replay"]["receipt_identity"]["path"],
            created_at_utc=receipt["created_at_utc"],
        )
    except Exception as exc:
        raise AuthorityError("BASELINE_ADMISSION_REPLAY_FAILED", str(exc)) from exc
    if replayed != receipt:
        raise AuthorityError("BASELINE_ADMISSION_REPLAY_FAILED", "semantic replay differs")
    expected_tools = {
        "admission": _root_tool_identity(
            context,
            "baseline_admission_v1",
            "tool.baseline_admission_v1.py",
        ),
        "builder": _root_tool_identity(
            context,
            "baseline_rebuild_v1",
            "tool.baseline_rebuild_v1.py",
        ),
        "fixed_replay": _root_tool_identity(
            context,
            "cut_free_incumbent_replay_v1",
            "tool.cut_free_incumbent_replay_v1.py",
        ),
    }
    metadata = receipt["rebuilt_model"]["metadata"]
    expected_inputs = {
        role: context["root"]["strict_inputs"][role]
        for role in (
            "candidate_placements",
            "canonical_rules",
            "mandatory_instances",
        )
    }
    expected_paths = {
        "fixed_replay": preregistration["baseline_fixed_replay_path"],
        "incumbent": preregistration["baseline_incumbent_path"],
        "metadata": preregistration["baseline_rebuilt_metadata_path"],
        "model": preregistration["baseline_rebuilt_model_path"],
    }
    if (
        receipt["admission_tool_identity"] != expected_tools["admission"]
        or receipt["campaign_provenance"] != _campaign_provenance_expected(context)
        or metadata["builder_identity"] != expected_tools["builder"]
        or metadata["input_identities"] != expected_inputs
        or receipt["fixed_assignment_replay"]["replay_tool_identity"] != expected_tools["fixed_replay"]
        or receipt["legacy_control"]["identity"] != context["root"]["strict_inputs"]["legacy_control_a002"]
        or receipt["rebuilt_model"]["identity"]["path"] != expected_paths["model"]
        or metadata["metadata_identity"]["path"] != expected_paths["metadata"]
        or receipt["fixed_assignment_replay"]["incumbent_identity"]["path"] != expected_paths["incumbent"]
        or receipt["fixed_assignment_replay"]["receipt_identity"]["path"] != expected_paths["fixed_replay"]
    ):
        raise AuthorityError(
            "BASELINE_ADMISSION_ROOT_JOIN_FAILED",
            "package tools/inputs or preregistered baseline paths differ",
        )
    return receipt


def _read_organic_manifest(
    context: Mapping[str, Any],
    *,
    continuation: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Snapshot]:
    preregistration, _ = _path_preregistration(context)
    snapshot = snapshot_regular(preregistration["manifest_path"])
    runner = _runner_module(context)
    try:
        value = runner._strict_loads(  # noqa: SLF001 - sealed tool API replay
            snapshot.data,
            "organic manifest",
        )
    except Exception as exc:
        raise AuthorityError("MANIFEST_INVALID", str(exc)) from exc
    return (
        validate_manifest(
            value,
            context=context,
            continuation=continuation,
        ),
        snapshot,
    )


def create_suite_selection(
    campaign_dir: Path | str,
) -> dict[str, object]:
    """Publish the non-launching suite selection after the exact manifest."""

    context = _campaign_context(campaign_dir)
    continuation, continuation_identity = _continuation(context)
    manifest, manifest_snapshot = _read_organic_manifest(
        context,
        continuation=continuation,
    )
    inputs = _manifest_inputs(context)
    preregistration = inputs["path_preregistration"]
    output = _absolute(preregistration["suite_selection_path"])
    terminal = _absolute(preregistration["terminal_classification_path"])
    immediate_stop = _absolute(preregistration["immediate_stop_path"])
    if terminal.exists() or terminal.is_symlink() or immediate_stop.exists() or immediate_stop.is_symlink():
        raise AuthorityError(
            "PROSPECTIVE_CHILD_ALREADY_CONSUMED",
            "terminal or immediate-stop exists",
        )
    for path_value in preregistration["attempt_dirs"].values():
        path = _absolute(path_value)
        if path.exists() or path.is_symlink():
            raise AuthorityError("PROSPECTIVE_CHILD_ALREADY_CONSUMED", str(path))
    record: dict[str, object] = {
        "arm_launch_authorized": False,
        "baseline_admission_identity": inputs["baseline_admission_identity"],
        "baseline_admission_pass": True,
        "campaign_root_identity": context["root_identity"],
        "continuation_identity": continuation_identity,
        "experiment_contract": manifest["experiment_contract"],
        "immediate_stop_policy": IMMEDIATE_STOP_POLICY,
        "launch_plan": _launch_plan(context["root"]),
        "live_source_provenance_root": manifest["live_source_provenance_root"],
        "manifest_identity": detached_identity(manifest_snapshot),
        "next_required_gate": "PER_ARM_MANAGER_EPOCH_RESOURCE_AND_TERMINAL_PREFLIGHT",
        "organic_manifest_validated": True,
        "package_id": context["root"]["package"]["package_id"],
        "path_preregistration_identity": inputs["path_preregistration_identity"],
        "purpose": "AB16_SUITE_SELECTION_NO_ARM_LAUNCH",
        "run_nonce": context["root"]["run_nonce"],
        "schema_version": SUITE_SELECTION_SCHEMA,
        "sealed_snapshot_execution_root": manifest["sealed_snapshot_execution_root"],
        "selection_id": "",
        "snapshot_manifest_identity": manifest["snapshot_manifest_identity"],
        "snapshot_materialization_receipt_identity": manifest[
            "snapshot_materialization_receipt_identity"
        ],
        "solver_run_authorized": False,
    }
    record["selection_id"] = _digest_without(record, "selection_id")
    validate_suite_selection(
        record,
        context=context,
        continuation_identity=continuation_identity,
        manifest_identity=detached_identity(manifest_snapshot),
        baseline_identity=inputs["baseline_admission_identity"],
    )
    identity = _write_exclusive(output, canonical_json(record))
    return {"selection": record, "selection_identity": identity, "status": "PASS"}


def validate_suite_selection(
    value: object,
    *,
    context: Mapping[str, Any],
    continuation_identity: Mapping[str, Any],
    manifest_identity: Mapping[str, Any],
    baseline_identity: Mapping[str, Any],
) -> Mapping[str, Any]:
    _repository_snapshot_barrier(context)
    record = _exact_keys(
        value,
        {
            "arm_launch_authorized",
            "baseline_admission_identity",
            "baseline_admission_pass",
            "campaign_root_identity",
            "continuation_identity",
            "experiment_contract",
            "immediate_stop_policy",
            "launch_plan",
            "live_source_provenance_root",
            "manifest_identity",
            "next_required_gate",
            "organic_manifest_validated",
            "package_id",
            "path_preregistration_identity",
            "purpose",
            "run_nonce",
            "schema_version",
            "sealed_snapshot_execution_root",
            "selection_id",
            "snapshot_manifest_identity",
            "snapshot_materialization_receipt_identity",
            "solver_run_authorized",
        },
        "AB16 suite selection",
    )
    root = context["root"]
    inputs = _manifest_inputs(context)
    manifest, _ = _read_organic_manifest(
        context,
        continuation=_record(
            _replay_detached(continuation_identity, "suite continuation"),
            "suite continuation",
        ),
    )
    if (
        record["schema_version"] != SUITE_SELECTION_SCHEMA
        or record["purpose"] != "AB16_SUITE_SELECTION_NO_ARM_LAUNCH"
        or record["arm_launch_authorized"] is not False
        or record["solver_run_authorized"] is not False
        or record["baseline_admission_pass"] is not True
        or record["organic_manifest_validated"] is not True
        or record["campaign_root_identity"] != context["root_identity"]
        or record["continuation_identity"] != continuation_identity
        or record["manifest_identity"] != manifest_identity
        or record["baseline_admission_identity"] != baseline_identity
        or record["path_preregistration_identity"] != inputs["path_preregistration_identity"]
        or record["experiment_contract"] != manifest["experiment_contract"]
        or record["immediate_stop_policy"] != IMMEDIATE_STOP_POLICY
        or record["launch_plan"] != _launch_plan(root)
        or record["live_source_provenance_root"] != manifest["live_source_provenance_root"]
        or record["sealed_snapshot_execution_root"] != manifest["sealed_snapshot_execution_root"]
        or record["snapshot_manifest_identity"] != manifest["snapshot_manifest_identity"]
        or record["snapshot_materialization_receipt_identity"]
        != manifest["snapshot_materialization_receipt_identity"]
        or record["next_required_gate"] != "PER_ARM_MANAGER_EPOCH_RESOURCE_AND_TERMINAL_PREFLIGHT"
        or record["package_id"] != root["package"]["package_id"]
        or record["run_nonce"] != root["run_nonce"]
        or record["selection_id"] != _digest_without(record, "selection_id")
    ):
        raise AuthorityError("SELECTION_INVALID", "binding or claim boundary")
    return record


def create_selection(
    campaign_dir: Path | str,
    *,
    baseline_admission: Path | str | None = None,
) -> dict[str, object]:
    """Compatibility wrapper; baseline path is fixed by preregistration."""

    if baseline_admission is not None:
        context = _campaign_context(campaign_dir)
        preregistration, _ = _path_preregistration(context)
        if _absolute(baseline_admission) != _absolute(preregistration["baseline_admission_path"]):
            raise AuthorityError(
                "BASELINE_ADMISSION_INVALID",
                "caller path differs from package-pinned preregistration",
            )
    return create_suite_selection(campaign_dir)


def _read_suite_selection(
    context: Mapping[str, Any],
    *,
    continuation_identity: Mapping[str, Any],
    manifest_identity: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Snapshot]:
    inputs = _manifest_inputs(context)
    path = inputs["path_preregistration"]["suite_selection_path"]
    snapshot = snapshot_regular(path)
    value = _record(snapshot, "AB16 suite selection")
    return (
        validate_suite_selection(
            value,
            context=context,
            continuation_identity=continuation_identity,
            manifest_identity=manifest_identity,
            baseline_identity=inputs["baseline_admission_identity"],
        ),
        snapshot,
    )


def _resource_modules(
    context: Mapping[str, Any],
) -> tuple[ModuleType, ModuleType]:
    lifecycle_snapshot = _source_snapshot(
        context["files"],
        context["sources"],
        "tool.organic_resource_lifecycle_v2.py",
    )
    verifier_snapshot = _source_snapshot(
        context["files"],
        context["sources"],
        "tool.organic_resource_verifier_v2.py",
    )
    lifecycle = _load_module(
        lifecycle_snapshot,
        f"_ab16_resource_lifecycle_{lifecycle_snapshot.sha256[:16]}",
    )
    verifier = _load_module(
        verifier_snapshot,
        f"_ab16_resource_verifier_{verifier_snapshot.sha256[:16]}",
    )
    if (
        getattr(lifecycle, "PRE_RUN_AUTHORITY_SCHEMA", None) != getattr(verifier, "PRE_RUN_SCHEMA", None)
        or getattr(lifecycle, "RUNNER_SELECTION_SCHEMA", None) != ARM_SELECTION_SCHEMA
    ):
        raise AuthorityError(
            "RESOURCE_CONTRACT_DRIFT",
            "lifecycle/verifier/runner schemas differ",
        )
    return lifecycle, verifier


def _arm_evidence_modules(
    context: Mapping[str, Any],
) -> tuple[ModuleType, ModuleType, ModuleType]:
    replay_snapshot = _source_snapshot(
        context["files"],
        context["sources"],
        "tool.organic_arm_replay_v1.py",
    )
    gate_snapshot = _source_snapshot(
        context["files"],
        context["sources"],
        "tool.ab16_terminal_gate_v2.py",
    )
    contract_snapshot = _source_snapshot(
        context["files"],
        context["sources"],
        "tool.ab16_contract_v1.py",
    )
    replay_tool = _load_module(
        replay_snapshot,
        f"_ab16_arm_replay_{replay_snapshot.sha256[:16]}",
    )
    gate_tool = _load_module(
        gate_snapshot,
        f"_ab16_terminal_gate_{gate_snapshot.sha256[:16]}",
    )
    contract_tool = _load_module(
        contract_snapshot,
        f"_ab16_contract_{contract_snapshot.sha256[:16]}",
    )
    if (
        getattr(replay_tool, "RECEIPT_SCHEMA", None) != getattr(gate_tool, "ARITHMETIC_SCHEMA", None)
        or getattr(replay_tool, "RECEIPT_PURPOSE", None) != getattr(gate_tool, "ARITHMETIC_PURPOSE", None)
        or tuple(getattr(gate_tool, "ARM_SEQUENCE", ())) != tuple(getattr(contract_tool, "ARM_SEQUENCE", ()))
    ):
        raise AuthorityError(
            "ARM_EVIDENCE_CONTRACT_DRIFT",
            "arithmetic/gate/contract schemas or order differ",
        )
    return replay_tool, gate_tool, contract_tool


def _resource_campaign_root_view(
    context: Mapping[str, Any],
) -> dict[str, object]:
    """Project independently replayed campaign authority for the resource gate."""

    root = context["root"]
    strict_inputs: dict[str, dict[str, object]] = {}
    for role, identity in root["strict_inputs"].items():
        snapshot = _replay_detached(identity, f"resource root strict input {role}")
        strict_inputs[role] = {
            "mode": snapshot.mode,
            **detached_identity(snapshot),
        }
    return {
        **root,
        "package": {
            "manifest_identity": root["package"]["manifest_identity"],
            "package_id": root["package"]["package_id"],
            "seal_identity": root["package"]["seal_identity"],
        },
        "repository_git_tool_identity": _root_tool_identity_with_mode(
            context,
            "git",
            "system.git.bin",
        ),
        "repository_root": _validate_gate_approvals(context)["repository_root"],
        "strict_input_identities": strict_inputs,
    }


def _expected_pre_run_tools(
    context: Mapping[str, Any],
) -> dict[str, dict[str, object]]:
    tool_roles = {
        "ab16_authority": "ab16_authority_v2",
        "ab16_formal_loader": "ab16_formal_loader_v1",
        "attestor_python": "attestor_python",
        "busctl": "busctl",
        "manager_attestor": "manager_attestor_v4",
        "organic_arm_runner": "organic_arm_runner_v1",
        "organic_resource_lifecycle": "organic_resource_lifecycle_v2",
        "organic_resource_verifier": "organic_resource_verifier_v2",
        "organic_unit_orchestrator": "organic_unit_orchestrator_v2",
        "python3_13": "python3_13",
        "systemd_unit_reference": "systemd_unit_reference_v1",
        "libsystemd": "libsystemd",
        "sudo": "sudo",
        "systemctl": "systemctl",
        "systemd_run": "systemd_run",
    }
    result: dict[str, dict[str, object]] = {}
    for output_role, root_role in tool_roles.items():
        identity = context["root"]["authority_tools"][root_role]
        snapshot = _replay_detached(identity, f"pre-run tool {root_role}")
        result[output_role] = {
            "mode": snapshot.mode,
            **detached_identity(snapshot),
        }
    epoch_identity = context["root"]["authority_tools"]["campaign_authority_v4"]
    epoch_snapshot = _replay_detached(
        epoch_identity,
        "pre-run manager epoch authority",
    )
    result["manager_epoch_authority"] = {
        "mode": epoch_snapshot.mode,
        **detached_identity(epoch_snapshot),
    }
    return result


def _validate_preselection_epoch(
    lifecycle: ModuleType,
    pre_run: Mapping[str, Any],
    *,
    root_epoch: Mapping[str, Any],
) -> None:
    transcript_snapshot = _replay_identity_with_optional_mode(
        pre_run["preselection_transcript_identity"],
        "preselection manager epoch capture transcript",
    )
    transcript_identity = {
        "mode": transcript_snapshot.mode,
        **detached_identity(transcript_snapshot),
    }
    snapshot = _replay_identity_with_optional_mode(
        pre_run["preselection_epoch_identity"],
        "preselection manager epoch observation",
    )
    try:
        observation = lifecycle.strict_loads(
            snapshot.data,
            "preselection manager epoch observation",
        )
        rebuilt = lifecycle.build_epoch_observation(
            phase="preselection",
            slot=pre_run["slot"],
            observed_epoch=observation["observed_epoch"],
            observed_at_monotonic_ns=observation["observed_at_monotonic_ns"],
            capture_transcript_identity=observation["capture_transcript_identity"],
        )
    except Exception as exc:
        raise AuthorityError("PRE_RUN_EPOCH_INVALID", str(exc)) from exc
    if (
        observation != rebuilt
        or observation["observed_epoch"] != root_epoch
        or observation["capture_transcript_identity"] != transcript_identity
    ):
        raise AuthorityError(
            "PRE_RUN_EPOCH_INVALID",
            "preselection observation/transcript differs from the campaign manager/boot epoch",
        )


def _capture_current_manager_epoch(
    context: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Capture the live manager epoch with only package-pinned tools."""

    tools = context["root"]["authority_tools"]
    authority = context["campaign_module"]
    try:
        captured = authority.capture_manager_epoch_with_transcript(
            attestor_path=tools["manager_attestor_v4"]["path"],
            busctl_path=tools["busctl"]["path"],
            python_path=tools["attestor_python"]["path"],
            sudo_path=tools["sudo"]["path"],
        )
        if type(captured) is not dict or set(captured) != {
            "manager_epoch",
            "transcript",
        }:
            raise ValueError("live capture returned the wrong exact schema")
        authority.validate_manager_epoch(captured["manager_epoch"])
        authority.validate_manager_epoch_capture_transcript(
            captured["transcript"],
            expected_epoch=captured["manager_epoch"],
        )
    except Exception as exc:
        raise AuthorityError("PRE_RUN_EPOCH_CAPTURE_FAILED", str(exc)) from exc
    return captured


def _launch_environment_record(lifecycle: ModuleType) -> dict[str, object]:
    """Freeze the exact ambient-free environment for one future child."""

    variables = {
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
    }
    record: dict[str, object] = {
        "clear_ambient": True,
        "schema_version": lifecycle.LAUNCH_ENVIRONMENT_SCHEMA,
        "variables": variables,
    }
    try:
        lifecycle.validate_launch_environment(record)
    except Exception as exc:
        raise AuthorityError(
            "LAUNCH_ENVIRONMENT_INVALID",
            str(exc),
        ) from exc
    return record


def _build_pre_run_candidate_unprotected(
    campaign_dir: Path | str,
    *,
    slot: str,
) -> dict[str, object]:
    """Publish one non-launching, package-pinned pre-run authority candidate."""

    context = _campaign_context(campaign_dir)
    continuation, continuation_identity = _continuation(context)
    manifest, manifest_snapshot = _read_organic_manifest(
        context,
        continuation=continuation,
    )
    suite, suite_snapshot = _read_suite_selection(
        context,
        continuation_identity=continuation_identity,
        manifest_identity=detached_identity(manifest_snapshot),
    )
    _assert_arm_selection_order(context, slot=slot)
    inputs = _manifest_inputs(context)
    gate_approvals = _validate_gate_approvals(context)
    preregistration = inputs["path_preregistration"]
    candidate_paths = {
        "candidate": Path(preregistration["pre_run_candidate_paths"][slot]),
        "environment": Path(preregistration["launch_environment_paths"][slot]),
        "epoch": Path(preregistration["preselection_epoch_paths"][slot]),
        "transcript": Path(preregistration["preselection_transcript_paths"][slot]),
    }
    if any(path.exists() or path.is_symlink() for path in candidate_paths.values()):
        raise AuthorityError(
            "PRE_RUN_CANDIDATE_ALREADY_EXISTS",
            slot,
        )
    captured = _capture_current_manager_epoch(context)
    if captured["manager_epoch"] != context["root"]["manager_epoch"]:
        raise AuthorityError(
            "PRE_RUN_EPOCH_DRIFT",
            "live manager/boot epoch differs before candidate publication",
        )
    if _observe_repository_head(context) != context["root"]["repository_head"]:
        raise AuthorityError("HEAD_REPLAY_FAILED", "repository HEAD drifted")

    lifecycle, verifier = _resource_modules(context)
    environment_record = _launch_environment_record(lifecycle)
    transcript_identity = _write_exclusive(
        candidate_paths["transcript"],
        lifecycle.canonical_json_bytes(captured["transcript"]),
    )
    transcript_snapshot = snapshot_regular(candidate_paths["transcript"])
    transcript_identity_with_mode = {
        "mode": transcript_snapshot.mode,
        **transcript_identity,
    }
    epoch_record = lifecycle.build_epoch_observation(
        phase="preselection",
        slot=slot,
        observed_epoch=captured["manager_epoch"],
        observed_at_monotonic_ns=time.monotonic_ns(),
        capture_transcript_identity=transcript_identity_with_mode,
    )
    epoch_identity = _write_exclusive(
        candidate_paths["epoch"],
        lifecycle.canonical_json_bytes(epoch_record),
    )
    environment_identity = _write_exclusive(
        candidate_paths["environment"],
        lifecycle.canonical_json_bytes(environment_record),
    )
    environment_snapshot = snapshot_regular(candidate_paths["environment"])
    environment_identity_with_mode = {
        "mode": environment_snapshot.mode,
        **environment_identity,
    }

    plan = next(item for item in _launch_plan(context["root"]) if item["slot"] == slot)
    configuration = plan["configuration"]
    arm = plan["arm"]
    tools = _expected_pre_run_tools(context)
    strict_inputs = {
        role: {
            "mode": snapshot.mode,
            **detached_identity(snapshot),
        }
        for role, identity in context["root"]["strict_inputs"].items()
        for snapshot in [
            _replay_detached(
                identity,
                f"pre-run strict input {role}",
            )
        ]
    }
    attempt = Path(plan["attempt_dir"])
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
    phases = (
        "launch",
        "preterminal",
        "reference-acquire",
        "release",
        "terminal-first",
        "terminal-stable",
        "reference-release",
        "cleanup",
        "detached-replay",
    )
    expected_package = {
        "manifest_identity": context["root"]["package"]["manifest_identity"],
        "package_id": context["root"]["package"]["package_id"],
        "seal_identity": context["root"]["package"]["seal_identity"],
    }
    expected_payload_status = {
        "exit_code": 0,
        "expectation": "SUCCESS",
        "signal": 0,
    }
    repository_snapshot = context["repository_snapshot"]
    runner_relative = "docs/research/noncert_cuts_ab16_20260724/organic_arm_runner_v1.py"
    runner_member = repository_snapshot["member_identities"].get(runner_relative)
    if runner_member is None:
        raise AuthorityError(
            "PRE_RUN_AUTHORITY_INVALID",
            "organic runner is absent from the sealed source snapshot",
        )
    runner_member_snapshot = snapshot_regular(runner_member["path"])
    runner_member_with_mode = {
        "mode": runner_member_snapshot.mode,
        **dict(runner_member),
    }
    selected_literal_identity = repository_snapshot["external_platform"][
        "selected_byte_launch"
    ]["literal_identity"]
    module_origin_path = attempt / "module-origin-receipt.json"
    supervisor_origin_path = attempt / "supervisor-module-origin-receipt.json"
    execution_source = lifecycle.build_sealed_execution_source(
        live_source_provenance_root=manifest["live_source_provenance_root"],
        sealed_snapshot_execution_root=manifest["sealed_snapshot_execution_root"],
        snapshot_manifest_identity=manifest["snapshot_manifest_identity"],
        snapshot_materialization_receipt_identity=manifest[
            "snapshot_materialization_receipt_identity"
        ],
        package_id=context["root"]["package"]["package_id"],
        literal_identity=selected_literal_identity,
        python_identity=tools["python3_13"],
        loader_identity=tools["ab16_formal_loader"],
        authority_identity=tools["ab16_authority"],
        runner_snapshot_relative_path=runner_relative,
        runner_snapshot_member_identity=runner_member_with_mode,
        runner_package_tool_identity=tools["organic_arm_runner"],
        initial_working_directory=str(context["directory"]),
        pre_run_authority_path=preregistration["pre_run_authority_paths"][slot],
        runner_selection_path=preregistration["arm_selection_paths"][slot],
        module_origin_receipt_path=str(module_origin_path),
        tmpdir=str(attempt / "tmp"),
    )
    payload_argv = lifecycle.build_formal_direct_argv(
        execution_source,
        literal=_bootstrap_literal_values(context["files"], context["sources"])[
            "SELECTED_BYTE_LAUNCH_V1"
        ],
        role="organic-arm",
        campaign_dir=str(context["directory"]),
        pre_run_path=preregistration["pre_run_authority_paths"][slot],
        selection_path=preregistration["arm_selection_paths"][slot],
        module_origin_receipt_path=str(module_origin_path),
    )
    supervisor_argv = lifecycle.build_formal_direct_argv(
        execution_source,
        literal=_bootstrap_literal_values(context["files"], context["sources"])[
            "SELECTED_BYTE_LAUNCH_V1"
        ],
        role="organic-supervisor",
        campaign_dir=str(context["directory"]),
        pre_run_path=preregistration["pre_run_authority_paths"][slot],
        selection_path=preregistration["arm_selection_paths"][slot],
        module_origin_receipt_path=str(supervisor_origin_path),
    )
    record: dict[str, object] = {
        "arm": arm,
        "arm_binding_identity": manifest["arm_binding_identities"][slot],
        "arm_launch_authorized": False,
        "arm_selection_write_authorized": True,
        "attempt_dir": str(attempt),
        "authority_chain": manifest["authority_chain"],
        "baseline_admission_identity": manifest["baseline_admission_identity"],
        "baseline_incumbent_sha256": manifest["baseline_incumbent_identity"]["sha256"],
        "campaign_id": context["root"]["campaign_id"],
        "campaign_root_identity": context["root_identity"],
        "common_prestate_identity": manifest["common_prestate_identity"],
        "configuration": configuration,
        "continuation_identity": continuation_identity,
        "epoch_observation_paths": {phase: str(attempt / f"manager-epoch-{phase}.json") for phase in phases},
        "epoch_transcript_paths": {phase: str(attempt / f"manager-transcript-{phase}.json") for phase in phases},
        "execution_class": "FORMAL_AB16",
        "expected_payload_status": expected_payload_status,
        "launch": {
            "cwd": str(context["directory"]),
            "environment_identity": environment_identity_with_mode,
            "execution_source": execution_source,
            "payload_argv": payload_argv,
            "libsystemd_path": tools["libsystemd"]["path"],
            "python3_13_path": tools["python3_13"]["path"],
            "supervisor_argv": supervisor_argv,
            "systemctl_path": tools["systemctl"]["path"],
            "systemd_run_path": tools["systemd_run"]["path"],
        },
        "live_source_provenance_root": manifest["live_source_provenance_root"],
        "manager_epoch": context["root"]["manager_epoch"],
        "order": plan["order"],
        "output_paths": {role: str(attempt / name) for role, name in output_names.items()},
        "package": expected_package,
        "pre_run_authority_path": preregistration["pre_run_authority_paths"][slot],
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
        "preselection_transcript_identity": (transcript_identity_with_mode),
        "reference_capability_identity": gate_approvals["reference_capability_identity"],
        "reference_capability_transcript_identity": gate_approvals["reference_capability_transcript_identity"],
        "history_freeze_replay_identity": gate_approvals["history_freeze_replay_identity"],
        "prospective_manifest_identity": detached_identity(manifest_snapshot),
        "purpose": lifecycle.PRE_RUN_PURPOSE,
        "repository_git_tool_identity": manifest["repository_git_tool_identity"],
        "repository_head": manifest["repository_head"],
        "repository_root": manifest["repository_root"],
        "resource_contract": lifecycle.RESOURCE_CONTRACTS["FORMAL_AB16"],
        "reference_contract": lifecycle.REFERENCE_CONTRACT,
        "run_nonce": manifest["run_nonce"],
        "runner_selection_path": preregistration["arm_selection_paths"][slot],
        "schema_version": lifecycle.PRE_RUN_AUTHORITY_SCHEMA,
        "sealed_snapshot_execution_root": manifest["sealed_snapshot_execution_root"],
        "seed": manifest["seed"],
        "snapshot_manifest_identity": manifest["snapshot_manifest_identity"],
        "snapshot_materialization_receipt_identity": manifest[
            "snapshot_materialization_receipt_identity"
        ],
        "slot": slot,
        "solver_run_authorized": False,
        "status": "PASS",
        "strict_input_identities": strict_inputs,
        "suite_selection_identity": detached_identity(suite_snapshot),
        "tool_identities": tools,
        "unit_name": plan["unit_name"],
        "verdict": "AB16_ORGANIC_PRE_RUN_AUTHORITY_PASS",
        "workers": 1,
    }
    try:
        verifier.validate_pre_run_authority(
            record,
            campaign_root=_resource_campaign_root_view(context),
            manifest=manifest,
            suite_selection=suite,
            expected_slot=slot,
        )
    except Exception as exc:
        raise AuthorityError(
            "PRE_RUN_AUTHORITY_INVALID",
            str(exc),
        ) from exc
    candidate_identity = _write_exclusive(
        candidate_paths["candidate"],
        lifecycle.canonical_json_bytes(record),
    )
    return {
        "candidate": record,
        "candidate_identity": candidate_identity,
        "environment_identity": environment_identity_with_mode,
        "preselection_epoch_identity": epoch_identity,
        "preselection_transcript_identity": (transcript_identity_with_mode),
        "status": "PASS",
    }


def _optional_existing_identity(path: Path) -> dict[str, object] | None:
    """Return one same-FD identity without following a hostile leaf."""

    try:
        return detached_identity(snapshot_regular(path))
    except AuthorityError:
        return None


def _publish_preselection_stop(
    campaign_dir: Path | str,
    *,
    slot: str,
    failure: BaseException,
) -> dict[str, object] | None:
    """Permanently stop a campaign after a non-launching preselection failure."""

    context = _campaign_context(campaign_dir)
    preregistration, _ = _path_preregistration(context)
    stop_path = Path(preregistration["immediate_stop_path"])
    if stop_path.exists() or stop_path.is_symlink():
        return None
    partial_paths = {
        "candidate": Path(preregistration["pre_run_candidate_paths"][slot]),
        "environment": Path(preregistration["launch_environment_paths"][slot]),
        "epoch": Path(preregistration["preselection_epoch_paths"][slot]),
        "transcript": Path(preregistration["preselection_transcript_paths"][slot]),
    }
    failure_code = failure.code if isinstance(failure, AuthorityError) else "PRESELECTION_UNEXPECTED_FAILURE"
    stop = {
        "arm_slot_consumed": False,
        "campaign_id": context["root"]["campaign_id"],
        "code": "AB16_PRESELECTION_FAIL_CLOSED",
        "failed_slot": slot,
        "failure_code": failure_code,
        "partial_output_identities": {role: _optional_existing_identity(path) for role, path in partial_paths.items()},
        "phase": "PRESELECTION",
        "purpose": "AB16_IMMEDIATE_STOP",
        "run_nonce": context["root"]["run_nonce"],
        "schema_version": CAMPAIGN_STOP_SCHEMA,
        "selection_created": False,
    }
    return _write_exclusive(stop_path, canonical_json(stop))


def build_pre_run_candidate(
    campaign_dir: Path | str,
    *,
    slot: str,
) -> dict[str, object]:
    """Publish one candidate or immutably stop before any arm selection."""

    try:
        return _build_pre_run_candidate_unprotected(
            campaign_dir,
            slot=slot,
        )
    except BaseException as exc:
        try:
            _publish_preselection_stop(
                campaign_dir,
                slot=slot,
                failure=exc,
            )
        except BaseException as stop_exc:
            raise AuthorityError(
                "PRESELECTION_STOP_PUBLICATION_FAILED",
                f"{type(exc).__name__}: {exc}; stop: {type(stop_exc).__name__}: {stop_exc}",
            ) from stop_exc
        raise


def _validate_pre_run_candidate(
    context: Mapping[str, Any],
    *,
    slot: str,
    manifest: Mapping[str, Any],
    manifest_identity: Mapping[str, Any],
    suite_selection: Mapping[str, Any],
    suite_selection_identity: Mapping[str, Any],
    continuation_identity: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Snapshot]:
    inputs = _manifest_inputs(context)
    preregistration = inputs["path_preregistration"]
    candidate_snapshot = snapshot_regular(preregistration["pre_run_candidate_paths"][slot])
    lifecycle, verifier = _resource_modules(context)
    try:
        candidate = verifier.strict_loads(
            candidate_snapshot.data,
            "AB16 pre-run authority candidate",
        )
        candidate = verifier.validate_pre_run_authority(
            candidate,
            campaign_root=_resource_campaign_root_view(context),
            manifest=manifest,
            suite_selection=suite_selection,
            expected_slot=slot,
        )
    except Exception as exc:
        raise AuthorityError("PRE_RUN_AUTHORITY_INVALID", str(exc)) from exc
    plan = next(item for item in _launch_plan(context["root"]) if item["slot"] == slot)
    expected_package = {
        "manifest_identity": context["root"]["package"]["manifest_identity"],
        "package_id": context["root"]["package"]["package_id"],
        "seal_identity": context["root"]["package"]["seal_identity"],
    }
    if (
        candidate["campaign_root_identity"] != context["root_identity"]
        or candidate["continuation_identity"] != continuation_identity
        or candidate["prospective_manifest_identity"] != manifest_identity
        or candidate["suite_selection_identity"] != suite_selection_identity
        or candidate["authority_chain"] != manifest["authority_chain"]
        or candidate["package"] != expected_package
        or candidate["manager_epoch"] != context["root"]["manager_epoch"]
        or candidate["repository_head"] != context["root"]["repository_head"]
        or candidate["baseline_admission_identity"] != manifest["baseline_admission_identity"]
        or candidate["baseline_incumbent_sha256"] != manifest["baseline_incumbent_identity"]["sha256"]
        or candidate["common_prestate_identity"] != manifest["common_prestate_identity"]
        or candidate["arm_binding_identity"] != manifest["arm_binding_identities"][slot]
        or candidate["seed"] != manifest["seed"]
        or candidate["workers"] != manifest["workers"]
        or candidate["attempt_dir"] != plan["attempt_dir"]
        or candidate["unit_name"] != plan["unit_name"]
        or candidate["pre_run_authority_path"] != preregistration["pre_run_authority_paths"][slot]
        or candidate["runner_selection_path"] != preregistration["arm_selection_paths"][slot]
        or candidate["prelaunch_allowlist"] != ["pre-run-authority.json", "selection.json"]
    ):
        raise AuthorityError(
            "PRE_RUN_AUTHORITY_INVALID",
            "campaign/manifest/path binding",
        )
    strict = {
        role: _normalized_identity(identity, f"pre-run strict input {role}")
        for role, identity in candidate["strict_input_identities"].items()
    }
    if strict != context["root"]["strict_inputs"]:
        raise AuthorityError(
            "PRE_RUN_AUTHORITY_INVALID",
            "strict input identity map differs from campaign root",
        )
    tools = {
        role: _normalized_identity(identity, f"pre-run tool {role}")
        for role, identity in candidate["tool_identities"].items()
    }
    expected_tools = {
        role: {key: value for key, value in identity.items() if key in {"path", "sha256", "size_bytes"}}
        for role, identity in _expected_pre_run_tools(context).items()
    }
    if tools != expected_tools:
        raise AuthorityError(
            "PRE_RUN_AUTHORITY_INVALID",
            "tool identities differ from campaign package/root",
        )
    runner_resource = dict(manifest["experiment_contract"]["resource_contract"])
    runner_resource["runtime_max_seconds"] = runner_resource.pop("runtime_max_sec")
    if (
        candidate["resource_contract"] != lifecycle.RESOURCE_CONTRACTS["FORMAL_AB16"]
        or candidate["resource_contract"] != runner_resource
    ):
        raise AuthorityError(
            "PRE_RUN_AUTHORITY_INVALID",
            "35/39/16 GiB or 3600-second resource contract drift",
        )
    _validate_preselection_epoch(
        lifecycle,
        candidate,
        root_epoch=context["root"]["manager_epoch"],
    )
    if _observe_repository_head(context) != context["root"]["repository_head"]:
        raise AuthorityError("HEAD_REPLAY_FAILED", "repository HEAD drifted")
    return candidate, candidate_snapshot


def _load_consumption(
    context: Mapping[str, Any],
    *,
    slot: str,
    required_credible: bool,
) -> Mapping[str, Any]:
    preregistration, _ = _path_preregistration(context)
    path = Path(preregistration["attempt_dirs"][slot]) / "consumption.json"
    snapshot = snapshot_regular(path)
    record = _exact_keys(
        _record(snapshot, f"arm consumption {slot}"),
        {
            "arm_gate_identity",
            "arm_result_identity",
            "arithmetic_receipt_identity",
            "campaign_id",
            "consumption_id",
            "failure_code",
            "immediate_stop_required",
            "next_arm_authorized",
            "outcome",
            "purpose",
            "resource_preterminal_identity",
            "resource_replay_identity",
            "resource_terminal_identity",
            "run_nonce",
            "schema_version",
            "selection_identity",
            "slot",
            "suite_terminal_identity",
        },
        f"arm consumption {slot}",
    )
    if record["selection_identity"] is not None:
        _replay_detached(record["selection_identity"], f"arm selection {slot}")
    evidence_fields = (
        "arm_gate_identity",
        "arm_result_identity",
        "arithmetic_receipt_identity",
        "resource_preterminal_identity",
        "resource_replay_identity",
        "resource_terminal_identity",
        "suite_terminal_identity",
    )
    for field in evidence_fields:
        identity = record[field]
        if identity is not None:
            _replay_detached(identity, f"arm consumption {field} {slot}")
    if (
        record["schema_version"] != ARM_CONSUMPTION_SCHEMA
        or record["purpose"] != "AB16_ARM_CONSUMPTION"
        or record["campaign_id"] != context["root"]["campaign_id"]
        or record["run_nonce"] != context["root"]["run_nonce"]
        or record["slot"] != slot
        or record["outcome"] not in {"CREDIBLE_TERMINAL", "CREDIBILITY_INCOMPLETE"}
        or type(record["failure_code"]) is not str
        or record["consumption_id"] != _digest_without(record, "consumption_id")
    ):
        raise AuthorityError("ARM_CONSUMPTION_INVALID", slot)
    credible = record["outcome"] == "CREDIBLE_TERMINAL"
    final_slot = slot == _launch_plan(context["root"])[-1]["slot"]
    required_evidence_present = all(
        record[field] is not None for field in evidence_fields if field != "suite_terminal_identity"
    )
    if (
        record["next_arm_authorized"] is not (credible and not final_slot)
        or record["immediate_stop_required"] is credible
        or (credible and record["failure_code"] != "")
        or (not credible and not record["failure_code"])
        or (credible and record["selection_identity"] is None)
        or (credible and not required_evidence_present)
        or (credible and (record["suite_terminal_identity"] is not None) is not final_slot)
        or (required_credible and not credible)
    ):
        raise AuthorityError("ARM_CONSUMPTION_INVALID", f"{slot} outcome")
    if credible:
        replayed_gate, replayed_suite = _replay_consumed_arm(
            context,
            slot=slot,
        )
        if record["arm_gate_identity"] != replayed_gate or record["suite_terminal_identity"] != replayed_suite:
            raise AuthorityError(
                "ARM_CONSUMPTION_INVALID",
                f"{slot} gate replay identity",
            )
    return record


def _assert_arm_selection_order(
    context: Mapping[str, Any],
    *,
    slot: str,
) -> int:
    preregistration, _ = _path_preregistration(context)
    plan = _launch_plan(context["root"])
    slots = [item["slot"] for item in plan]
    if slot not in slots:
        raise AuthorityError("ARM_SLOT_INVALID", slot)
    stop = Path(preregistration["immediate_stop_path"])
    if stop.exists() or stop.is_symlink():
        raise AuthorityError("CAMPAIGN_IMMEDIATE_STOPPED", str(stop))
    index = slots.index(slot)
    for prior in slots[:index]:
        _load_consumption(context, slot=prior, required_credible=True)
    for pending in slots[index:]:
        attempt = Path(preregistration["attempt_dirs"][pending])
        if attempt.exists() or attempt.is_symlink():
            raise AuthorityError(
                "ARM_ORDER_OR_NO_OVERWRITE_VIOLATION",
                f"{pending} attempt already exists",
            )
    return index + 1


def create_arm_selection(
    campaign_dir: Path | str,
    *,
    slot: str,
    selection_nonce: str,
) -> dict[str, object]:
    """Copy a validated pre-run receipt and publish one exact runner selection."""

    context = _campaign_context(campaign_dir)
    continuation, continuation_identity = _continuation(context)
    manifest, manifest_snapshot = _read_organic_manifest(
        context,
        continuation=continuation,
    )
    suite, suite_snapshot = _read_suite_selection(
        context,
        continuation_identity=continuation_identity,
        manifest_identity=detached_identity(manifest_snapshot),
    )
    ordinal = _assert_arm_selection_order(context, slot=slot)
    pre_run, candidate_snapshot = _validate_pre_run_candidate(
        context,
        slot=slot,
        manifest=manifest,
        manifest_identity=detached_identity(manifest_snapshot),
        suite_selection=suite,
        suite_selection_identity=detached_identity(suite_snapshot),
        continuation_identity=continuation_identity,
    )
    _repository_snapshot_barrier(context)
    preregistration, _ = _path_preregistration(context)
    attempt = _absolute(preregistration["attempt_dirs"][slot])
    _mkdir_exclusive(attempt)
    pre_run_identity: dict[str, object] | None = None
    try:
        pre_run_identity = _write_exclusive(
            preregistration["pre_run_authority_paths"][slot],
            candidate_snapshot.data,
        )
        runner = _runner_module(context)
        configuration = pre_run["configuration"]
        arm = pre_run["arm"]
        enabled = [] if arm == "control" else list(runner.CONFIGURATION_FAMILIES[configuration])
        record = {
            "arm": arm,
            "arm_binding_identity": manifest["arm_binding_identities"][slot],
            "attempt_dir": str(attempt),
            "authority_chain": manifest["authority_chain"],
            "authorizations": {
                "global_claim_authorized": False,
                "mathematical_claim_authorized": False,
                "organic_arm_launch_authorized": True,
                "production_certified_authorized": False,
                "solver_run_authorized": True,
            },
            "baseline_admission_identity": manifest["baseline_admission_identity"],
            "baseline_incumbent_sha256": manifest["baseline_incumbent_identity"]["sha256"],
            "campaign_id": manifest["campaign_id"],
            "common_prestate_identity": manifest["common_prestate_identity"],
            "configuration": configuration,
            "enabled_families": enabled,
            "execution_class": pre_run["execution_class"],
            "expected_payload_status": pre_run["expected_payload_status"],
            "fresh_process_required": True,
            "live_source_provenance_root": manifest["live_source_provenance_root"],
            "manifest_identity": detached_identity(manifest_snapshot),
            "order": pre_run["order"],
            "pre_run_authority_identity": pre_run_identity,
            "purpose": runner.SELECTION_PURPOSE,
            "repository_git_tool_identity": manifest["repository_git_tool_identity"],
            "repository_head": manifest["repository_head"],
            "repository_root": manifest["repository_root"],
            "run_nonce": manifest["run_nonce"],
            "schema_version": runner.SELECTION_SCHEMA,
            "sealed_snapshot_execution_root": manifest["sealed_snapshot_execution_root"],
            "seed": manifest["seed"],
            "selection_nonce": selection_nonce,
            "snapshot_manifest_identity": manifest["snapshot_manifest_identity"],
            "snapshot_materialization_receipt_identity": manifest[
                "snapshot_materialization_receipt_identity"
            ],
            "slot": slot,
            "unit_name": manifest["unit_names"][slot],
            "workers": manifest["workers"],
        }
        try:
            runner.validate_selection(record, manifest=manifest)
            lifecycle, _ = _resource_modules(context)
            lifecycle.validate_runner_selection(
                record,
                pre_run_authority=pre_run,
                pre_run_authority_identity=pre_run_identity,
            )
        except Exception as exc:
            raise AuthorityError("ARM_SELECTION_INVALID", str(exc)) from exc
        selection_identity = _write_exclusive(
            preregistration["arm_selection_paths"][slot],
            runner.canonical_json(record),
        )
    except Exception as exc:
        stop_record = {
            "campaign_id": context["root"]["campaign_id"],
            "code": "ARM_SELECTION_PUBLICATION_FAILED",
            "detail": str(exc),
            "failed_slot": slot,
            "package_id": context["root"]["package"]["package_id"],
            "purpose": "AB16_IMMEDIATE_STOP",
            "run_nonce": context["root"]["run_nonce"],
            "schema_version": CAMPAIGN_STOP_SCHEMA,
        }
        stop_path = Path(preregistration["immediate_stop_path"])
        if not stop_path.exists() and not stop_path.is_symlink():
            _write_exclusive(stop_path, canonical_json(stop_record))
        raise
    return {
        "arm_selection": record,
        "arm_selection_identity": selection_identity,
        "launch_ordinal": ordinal,
        "pre_run_authority_identity": pre_run_identity,
        "status": "PASS",
    }


def _optional_identity_at(path: Path | str) -> dict[str, object] | None:
    try:
        return detached_identity(snapshot_regular(path))
    except AuthorityError:
        return None


def _consumption_evidence_identities(
    preregistration: Mapping[str, Any],
    *,
    slot: str,
    pre_run: Mapping[str, Any] | None,
) -> dict[str, dict[str, object] | None]:
    attempt = Path(preregistration["attempt_dirs"][slot])
    output_paths = pre_run.get("output_paths", {}) if pre_run is not None else {}
    paths = {
        "arm_gate_identity": Path(preregistration["arm_gate_paths"][slot]),
        "arm_result_identity": Path(output_paths.get("attempt_result", attempt / "result.json")),
        "arithmetic_receipt_identity": Path(preregistration["arithmetic_replay_paths"][slot]),
        "resource_preterminal_identity": Path(
            output_paths.get(
                "resource_verification",
                attempt / "resource-verification.json",
            )
        ),
        "resource_replay_identity": Path(preregistration["resource_replay_paths"][slot]),
        "resource_terminal_identity": Path(
            output_paths.get(
                "detached_replay",
                attempt / "detached-replay.json",
            )
        ),
    }
    return {field: _optional_identity_at(path) for field, path in paths.items()}


def _write_arm_consumption(
    context: Mapping[str, Any],
    *,
    preregistration: Mapping[str, Any],
    slot: str,
    outcome: str,
    selection_identity: Mapping[str, Any] | None,
    evidence: Mapping[str, Mapping[str, Any] | None],
    failure_code: str,
    suite_terminal_identity: Mapping[str, Any] | None,
) -> dict[str, object]:
    credible = outcome == "CREDIBLE_TERMINAL"
    slots = [item["slot"] for item in _launch_plan(context["root"])]
    final_slot = slot == slots[-1]
    record: dict[str, object] = {
        "arm_gate_identity": (None if evidence["arm_gate_identity"] is None else dict(evidence["arm_gate_identity"])),
        "arm_result_identity": (
            None if evidence["arm_result_identity"] is None else dict(evidence["arm_result_identity"])
        ),
        "arithmetic_receipt_identity": (
            None if evidence["arithmetic_receipt_identity"] is None else dict(evidence["arithmetic_receipt_identity"])
        ),
        "campaign_id": context["root"]["campaign_id"],
        "consumption_id": "",
        "failure_code": failure_code,
        "immediate_stop_required": not credible,
        "next_arm_authorized": credible and not final_slot,
        "outcome": outcome,
        "purpose": "AB16_ARM_CONSUMPTION",
        "resource_preterminal_identity": (
            None
            if evidence["resource_preterminal_identity"] is None
            else dict(evidence["resource_preterminal_identity"])
        ),
        "resource_replay_identity": (
            None if evidence["resource_replay_identity"] is None else dict(evidence["resource_replay_identity"])
        ),
        "resource_terminal_identity": (
            None if evidence["resource_terminal_identity"] is None else dict(evidence["resource_terminal_identity"])
        ),
        "run_nonce": context["root"]["run_nonce"],
        "schema_version": ARM_CONSUMPTION_SCHEMA,
        "selection_identity": (None if selection_identity is None else dict(selection_identity)),
        "slot": slot,
        "suite_terminal_identity": (None if suite_terminal_identity is None else dict(suite_terminal_identity)),
    }
    record["consumption_id"] = _digest_without(record, "consumption_id")
    path = Path(preregistration["attempt_dirs"][slot]) / "consumption.json"
    identity = _write_exclusive(path, canonical_json(record))
    stop_identity: dict[str, object] | None = None
    if not credible:
        stop = {
            "campaign_id": context["root"]["campaign_id"],
            "code": failure_code,
            "consumption_identity": identity,
            "failed_slot": slot,
            "package_id": context["root"]["package"]["package_id"],
            "phase": "POST_SELECTION",
            "purpose": "AB16_IMMEDIATE_STOP",
            "run_nonce": context["root"]["run_nonce"],
            "schema_version": CAMPAIGN_STOP_SCHEMA,
            "selection_identity": (None if selection_identity is None else dict(selection_identity)),
        }
        stop_identity = _write_exclusive(
            preregistration["immediate_stop_path"],
            canonical_json(stop),
        )
    return {
        "consumption": record,
        "consumption_identity": identity,
        "immediate_stop_identity": stop_identity,
        "status": "PASS",
    }


def _replay_selected_arm_evidence(
    context: Mapping[str, Any],
    *,
    preregistration: Mapping[str, Any],
    manifest: Mapping[str, Any],
    selection: Mapping[str, Any],
    selection_snapshot: Snapshot,
    pre_run: Mapping[str, Any],
    pre_run_snapshot: Snapshot,
    slot: str,
    publish: bool,
) -> tuple[dict[str, object], dict[str, object] | None]:
    runner = _runner_module(context)
    _lifecycle, verifier = _resource_modules(context)
    replay_tool, gate_tool, contract_tool = _arm_evidence_modules(context)
    attempt = Path(preregistration["attempt_dirs"][slot])
    replays_dir = attempt / "replays"
    if publish:
        _mkdir_exclusive(replays_dir)
    elif not replays_dir.is_dir() or replays_dir.is_symlink():
        raise AuthorityError("ARM_REPLAY_DIRECTORY_INVALID", slot)

    result_snapshot = snapshot_regular(pre_run["output_paths"]["attempt_result"])
    arm_result = runner._strict_loads(  # noqa: SLF001 - package-pinned strict parser
        result_snapshot.data,
        f"arm result {slot}",
    )
    arithmetic_tool_identity = manifest["arithmetic_verifier"]["tool_identity"]
    replayed_arithmetic = replay_tool.replay_arm(
        arm_result=result_snapshot.path,
        cut_free_replay=preregistration["cut_free_replay_paths"][slot],
        replay_tool_identity=arithmetic_tool_identity,
    )
    arithmetic_path = Path(preregistration["arithmetic_replay_paths"][slot])
    if publish:
        arithmetic_identity = _write_exclusive(
            arithmetic_path,
            canonical_json(replayed_arithmetic),
        )
    else:
        arithmetic_identity = detached_identity(snapshot_regular(arithmetic_path))
    arithmetic_snapshot = snapshot_regular(arithmetic_path)
    arithmetic_receipt = _record(
        arithmetic_snapshot,
        f"arithmetic receipt {slot}",
    )
    if arithmetic_receipt != replayed_arithmetic:
        raise AuthorityError("ARITHMETIC_RECEIPT_REPLAY_FAILED", slot)
    second_arithmetic = replay_tool.replay_arm(
        arm_result=result_snapshot.path,
        cut_free_replay=preregistration["cut_free_replay_paths"][slot],
        replay_tool_identity=arithmetic_tool_identity,
    )

    verifier_tool_identity = manifest["per_arm_tool_identities"]["resource_verifier"]
    pre_snapshot = verifier.snapshot_json(pre_run_snapshot.path)
    selected_snapshot = verifier.snapshot_json(selection_snapshot.path)
    inner_snapshot = verifier.snapshot_json(pre_run["output_paths"]["inner"])
    preterminal_snapshot = verifier.snapshot_json(pre_run["output_paths"]["preterminal"])
    payload_snapshot = verifier.snapshot_json(pre_run["output_paths"]["attempt_result"])
    stored_preterminal_snapshot = verifier.snapshot_json(pre_run["output_paths"]["resource_verification"])
    replayed_preterminal = verifier.verify_preterminal(
        pre_run=pre_snapshot,
        selection=selected_snapshot,
        inner=inner_snapshot,
        preterminal=preterminal_snapshot,
        payload_result=payload_snapshot,
        verifier_tool_identity=verifier_tool_identity,
    )
    if stored_preterminal_snapshot.value != replayed_preterminal:
        raise AuthorityError(
            "RESOURCE_PRETERMINAL_REPLAY_FAILED",
            slot,
        )
    release_snapshot = verifier.snapshot_json(pre_run["output_paths"]["release"])
    reference_acquisition_snapshot = verifier.snapshot_json(pre_run["output_paths"]["reference_acquisition"])
    terminal_snapshot = verifier.snapshot_json(pre_run["output_paths"]["terminal"])
    reference_release_snapshot = verifier.snapshot_json(pre_run["output_paths"]["reference_release"])
    cleanup_snapshot = verifier.snapshot_json(pre_run["output_paths"]["cleanup"])
    detached_epoch_snapshot = verifier.snapshot_json(pre_run["epoch_observation_paths"]["detached-replay"])
    stored_detached_snapshot = verifier.snapshot_json(pre_run["output_paths"]["detached_replay"])
    replayed_detached = verifier.verify_detached(
        pre_run=pre_snapshot,
        selection=selected_snapshot,
        inner=inner_snapshot,
        preterminal=preterminal_snapshot,
        payload_result=payload_snapshot,
        resource=stored_preterminal_snapshot,
        reference_acquisition=reference_acquisition_snapshot,
        release=release_snapshot,
        terminal=terminal_snapshot,
        reference_release=reference_release_snapshot,
        cleanup=cleanup_snapshot,
        detached_epoch=detached_epoch_snapshot,
        verifier_tool_identity=verifier_tool_identity,
    )
    if stored_detached_snapshot.value != replayed_detached:
        raise AuthorityError("RESOURCE_TERMINAL_REPLAY_FAILED", slot)
    resource_replay_path = Path(preregistration["resource_replay_paths"][slot])
    if publish:
        _write_exclusive(
            resource_replay_path,
            canonical_json(replayed_detached),
        )
    elif (
        _record(
            snapshot_regular(resource_replay_path),
            f"resource replay receipt {slot}",
        )
        != replayed_detached
    ):
        raise AuthorityError("RESOURCE_REPLAY_RECEIPT_DRIFT", slot)

    gate_tool_identity = manifest["per_arm_tool_identities"]["terminal_gate"]
    arm_gate = gate_tool.build_arm_gate(
        selection=selection,
        selection_identity=detached_identity(selection_snapshot),
        arm_result=arm_result,
        arm_result_identity=detached_identity(result_snapshot),
        arithmetic_receipt=arithmetic_receipt,
        arithmetic_receipt_identity=arithmetic_identity,
        replayed_arithmetic_receipt=second_arithmetic,
        arithmetic_tool_identity=arithmetic_tool_identity,
        resource_receipt=stored_detached_snapshot.value,
        resource_receipt_identity=stored_detached_snapshot.identity,
        replayed_resource_receipt=replayed_detached,
        resource_preterminal_receipt=stored_preterminal_snapshot.value,
        resource_preterminal_identity=stored_preterminal_snapshot.identity,
        replayed_resource_preterminal_receipt=replayed_preterminal,
        resource_verifier_tool_identity=verifier_tool_identity,
        experiment_contract=manifest["experiment_contract"],
        gate_tool_identity=gate_tool_identity,
    )
    arm_gate_path = Path(preregistration["arm_gate_paths"][slot])
    if publish:
        arm_gate_identity = _write_exclusive(
            arm_gate_path,
            canonical_json(arm_gate),
        )
    else:
        arm_gate_snapshot = snapshot_regular(arm_gate_path)
        if _record(arm_gate_snapshot, f"arm gate {slot}") != arm_gate:
            raise AuthorityError("ARM_GATE_REPLAY_FAILED", slot)
        arm_gate_identity = detached_identity(arm_gate_snapshot)

    suite_terminal_identity: dict[str, object] | None = None
    if slot == manifest["arm_sequence"][-1]:
        arm_gates: list[Mapping[str, Any]] = []
        for prior_slot in manifest["arm_sequence"][:-1]:
            prior = _load_consumption(
                context,
                slot=prior_slot,
                required_credible=True,
            )
            gate_identity = prior["arm_gate_identity"]
            if gate_identity is None:
                raise AuthorityError(
                    "SUITE_GATE_INPUT_MISSING",
                    prior_slot,
                )
            arm_gates.append(
                _record(
                    _replay_detached(
                        gate_identity,
                        f"suite arm gate {prior_slot}",
                    ),
                    f"suite arm gate {prior_slot}",
                )
            )
        arm_gates.append(arm_gate)
        terminal_classification = gate_tool.build_suite_gate(
            arm_gates=arm_gates,
            contract=contract_tool,
        )
        if publish:
            suite_terminal_identity = _write_exclusive(
                preregistration["terminal_classification_path"],
                canonical_json(terminal_classification),
            )
        else:
            suite_snapshot = snapshot_regular(preregistration["terminal_classification_path"])
            if (
                _record(
                    suite_snapshot,
                    "AB16 terminal classification",
                )
                != terminal_classification
            ):
                raise AuthorityError("SUITE_GATE_REPLAY_FAILED", slot)
            suite_terminal_identity = detached_identity(suite_snapshot)
    del replays_dir
    return arm_gate_identity, suite_terminal_identity


def _replay_consumed_arm(
    context: Mapping[str, Any],
    *,
    slot: str,
) -> tuple[dict[str, object], dict[str, object] | None]:
    """Rebuild the package-pinned gate behind one credible consumption."""

    continuation, continuation_identity = _continuation(context)
    manifest, manifest_snapshot = _read_organic_manifest(
        context,
        continuation=continuation,
    )
    _read_suite_selection(
        context,
        continuation_identity=continuation_identity,
        manifest_identity=detached_identity(manifest_snapshot),
    )
    preregistration, _ = _path_preregistration(context)
    selection_snapshot = snapshot_regular(preregistration["arm_selection_paths"][slot])
    pre_run_snapshot = snapshot_regular(preregistration["pre_run_authority_paths"][slot])
    runner = _runner_module(context)
    lifecycle, verifier = _resource_modules(context)
    selection = runner._strict_loads(  # noqa: SLF001 - package-pinned parser
        selection_snapshot.data,
        f"consumed arm selection {slot}",
    )
    runner.validate_selection(selection, manifest=manifest)
    pre_run = verifier.strict_loads(
        pre_run_snapshot.data,
        f"consumed pre-run authority {slot}",
    )
    verifier.validate_pre_run_authority(
        pre_run,
        campaign_root=_resource_campaign_root_view(context),
        manifest=manifest,
        expected_slot=slot,
    )
    lifecycle.validate_runner_selection(
        selection,
        pre_run_authority=pre_run,
        pre_run_authority_identity=detached_identity(pre_run_snapshot),
    )
    return _replay_selected_arm_evidence(
        context,
        preregistration=preregistration,
        manifest=manifest,
        selection=selection,
        selection_snapshot=selection_snapshot,
        pre_run=pre_run,
        pre_run_snapshot=pre_run_snapshot,
        slot=slot,
        publish=False,
    )


def consume_arm(
    campaign_dir: Path | str,
    *,
    slot: str,
) -> dict[str, object]:
    """Derive one selected arm's credibility; caller claims are not accepted."""

    context = _campaign_context(campaign_dir)
    continuation, continuation_identity = _continuation(context)
    manifest, manifest_snapshot = _read_organic_manifest(
        context,
        continuation=continuation,
    )
    _read_suite_selection(
        context,
        continuation_identity=continuation_identity,
        manifest_identity=detached_identity(manifest_snapshot),
    )
    preregistration, _ = _path_preregistration(context)
    if slot not in manifest["arm_sequence"]:
        raise AuthorityError("ARM_SLOT_INVALID", slot)
    stop_path = Path(preregistration["immediate_stop_path"])
    if stop_path.exists() or stop_path.is_symlink():
        raise AuthorityError("CAMPAIGN_IMMEDIATE_STOPPED", str(stop_path))
    attempt = Path(preregistration["attempt_dirs"][slot])
    consumption_path = attempt / "consumption.json"
    if consumption_path.exists() or consumption_path.is_symlink():
        raise AuthorityError("ARM_ALREADY_CONSUMED", slot)

    selection_identity: dict[str, object] | None = None
    pre_run: Mapping[str, Any] | None = None
    try:
        selection_snapshot = snapshot_regular(preregistration["arm_selection_paths"][slot])
        selection_identity = detached_identity(selection_snapshot)
        pre_run_snapshot = snapshot_regular(preregistration["pre_run_authority_paths"][slot])
        runner = _runner_module(context)
        lifecycle, verifier = _resource_modules(context)
        selection = runner._strict_loads(  # noqa: SLF001 - sealed tool API replay
            selection_snapshot.data,
            f"arm selection {slot}",
        )
        runner.validate_selection(selection, manifest=manifest)
        pre_run = verifier.strict_loads(
            pre_run_snapshot.data,
            f"pre-run authority {slot}",
        )
        verifier.validate_pre_run_authority(
            pre_run,
            campaign_root=_resource_campaign_root_view(context),
            manifest=manifest,
            expected_slot=slot,
        )
        lifecycle.validate_runner_selection(
            selection,
            pre_run_authority=pre_run,
            pre_run_authority_identity=detached_identity(pre_run_snapshot),
        )
        _replay_selected_arm_evidence(
            context,
            preregistration=preregistration,
            manifest=manifest,
            selection=selection,
            selection_snapshot=selection_snapshot,
            pre_run=pre_run,
            pre_run_snapshot=pre_run_snapshot,
            slot=slot,
            publish=True,
        )
        evidence = _consumption_evidence_identities(
            preregistration,
            slot=slot,
            pre_run=pre_run,
        )
        suite_terminal_identity = (
            _optional_identity_at(preregistration["terminal_classification_path"])
            if slot == manifest["arm_sequence"][-1]
            else None
        )
        return _write_arm_consumption(
            context,
            preregistration=preregistration,
            slot=slot,
            outcome="CREDIBLE_TERMINAL",
            selection_identity=selection_identity,
            evidence=evidence,
            failure_code="",
            suite_terminal_identity=suite_terminal_identity,
        )
    except Exception as exc:
        if not attempt.exists() and not attempt.is_symlink():
            if isinstance(exc, AuthorityError):
                raise
            raise AuthorityError(
                "ARM_CONSUMPTION_INVALID",
                str(exc),
            ) from exc
        evidence = _consumption_evidence_identities(
            preregistration,
            slot=slot,
            pre_run=pre_run,
        )
        result = _write_arm_consumption(
            context,
            preregistration=preregistration,
            slot=slot,
            outcome="CREDIBILITY_INCOMPLETE",
            selection_identity=selection_identity,
            evidence=evidence,
            failure_code="POST_SELECTION_EVIDENCE_REPLAY_FAILED",
            suite_terminal_identity=None,
        )
        result["failure_detail"] = f"{type(exc).__name__}: {exc}"
        return result


def replay(campaign_dir: Path | str, *, selection_required: bool) -> dict[str, object]:
    context = _campaign_context(campaign_dir)
    continuation, continuation_identity = _continuation(context)
    manifest, manifest_snapshot = _read_organic_manifest(
        context,
        continuation=continuation,
    )
    inputs = _manifest_inputs(context)
    preregistration = inputs["path_preregistration"]
    result: dict[str, object] = {
        "campaign_root_identity": context["root_identity"],
        "continuation_identity": continuation_identity,
        "manifest_identity": detached_identity(manifest_snapshot),
        "package_id": context["root"]["package"]["package_id"],
        "selection_present": False,
        "status": "PASS",
    }
    if selection_required:
        baseline_snapshot = snapshot_regular(preregistration["baseline_admission_path"])
        _replay_baseline_admission(context, baseline_snapshot)
        selection_snapshot = snapshot_regular(preregistration["suite_selection_path"])
        validate_suite_selection(
            _record(selection_snapshot, "AB16 selection"),
            context=context,
            continuation_identity=continuation_identity,
            manifest_identity=detached_identity(manifest_snapshot),
            baseline_identity=detached_identity(baseline_snapshot),
        )
        result["baseline_admission_identity"] = detached_identity(baseline_snapshot)
        result["selection_identity"] = detached_identity(selection_snapshot)
        result["selection_present"] = True
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    baseline = sub.add_parser("prepare-baseline-output")
    baseline.add_argument("--campaign-dir", required=True, type=Path)
    manifest = sub.add_parser("publish-manifest")
    manifest.add_argument("--campaign-dir", required=True, type=Path)
    selection = sub.add_parser("create-suite-selection")
    selection.add_argument("--campaign-dir", required=True, type=Path)
    candidate = sub.add_parser("build-pre-run-candidate")
    candidate.add_argument("--campaign-dir", required=True, type=Path)
    candidate.add_argument("--slot", required=True)
    arm = sub.add_parser("create-arm-selection")
    arm.add_argument("--campaign-dir", required=True, type=Path)
    arm.add_argument("--slot", required=True)
    arm.add_argument("--selection-nonce", required=True)
    consume = sub.add_parser("consume-arm")
    consume.add_argument("--campaign-dir", required=True, type=Path)
    consume.add_argument("--slot", required=True)
    replay_parser = sub.add_parser("replay")
    replay_parser.add_argument("--campaign-dir", required=True, type=Path)
    replay_parser.add_argument("--without-selection", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "prepare-baseline-output":
            result = prepare_baseline_output(arguments.campaign_dir)
        elif arguments.command == "publish-manifest":
            result = build_manifest(arguments.campaign_dir)
        elif arguments.command == "create-suite-selection":
            result = create_suite_selection(arguments.campaign_dir)
        elif arguments.command == "build-pre-run-candidate":
            result = build_pre_run_candidate(
                arguments.campaign_dir,
                slot=arguments.slot,
            )
        elif arguments.command == "create-arm-selection":
            result = create_arm_selection(
                arguments.campaign_dir,
                slot=arguments.slot,
                selection_nonce=arguments.selection_nonce,
            )
        elif arguments.command == "consume-arm":
            result = consume_arm(
                arguments.campaign_dir,
                slot=arguments.slot,
            )
        else:
            result = replay(
                arguments.campaign_dir,
                selection_required=not arguments.without_selection,
            )
    except AuthorityError as exc:
        print(
            json.dumps(
                {"code": exc.code, "detail": exc.detail, "status": "FAIL_CLOSED"},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
