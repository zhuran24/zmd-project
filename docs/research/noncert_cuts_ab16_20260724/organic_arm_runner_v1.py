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

* the ordinary :class:`src.cuts.ledger.CutLedgerWriter`, or the package-pinned
  AB16 immutable adapter with the same append surface, records every
  GENERATED/APPLIED lifecycle event emitted by the production attach chain;
  and
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
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import resource
import stat
import subprocess
import sys
import time
from types import ModuleType
from typing import Any, Protocol, cast


MANIFEST_SCHEMA = "noncert-cuts-ab16-organic-manifest-v1"
FORMAL_MANIFEST_SCHEMA = "noncert-cuts-ab16-organic-manifest-v2"
PROSPECTIVE_FORMAL_MANIFEST_SCHEMA = "noncert-cuts-ab16-organic-manifest-v3"
SELECTION_SCHEMA = "noncert-cuts-ab16-organic-arm-selection-v1"
FORMAL_SELECTION_SCHEMA = "noncert-cuts-ab16-organic-arm-selection-v2"
RESULT_SCHEMA = "noncert-cuts-ab16-organic-arm-result-v1"
FORMAL_RESULT_SCHEMA = "noncert-cuts-ab16-organic-arm-result-v2"
JOURNAL_SCHEMA = "noncert-cuts-ab16-compile-attach-journal-v1"
CONTROLLER_TERMINAL_SCHEMA = "noncert-cuts-ab16-controller-terminal-v1"
MANIFEST_PURPOSE = "prospective_noncert_cuts_ab16"
SELECTION_PURPOSE = "prospective_noncert_cuts_ab16_formal_arm"
FORMAL_ARITHMETIC_PURPOSE = "prospective_noncert_cuts_ab16_formal_applied_inequality_replay_v1"
ATTACH_ENV = "EXACT_CUT_FRAMEWORK_ATTACH"
BASELINE_ADMISSION_SCHEMA = "noncert-cuts-ab16-baseline-admission-v1"
BASELINE_ADMISSION_VERDICT = "AB16_BASELINE_INPUTS_ADMITTED"
SEALED_EXECUTION_SOURCE_SCHEMA = "noncert-cuts-ab16-sealed-execution-source-v1"
SNAPSHOT_MANIFEST_SCHEMA = "noncert-cuts-ab16-repository-snapshot-v1"
SNAPSHOT_MATERIALIZATION_SCHEMA = "noncert-cuts-ab16-repository-snapshot-materialization-v1"
SELECTED_BYTE_LAUNCH_SCHEMA_V1 = (
    "noncert-cuts-ab16-selected-byte-launch-v1"
)
SELECTED_BYTE_LAUNCH_SCHEMA_V2 = (
    "noncert-cuts-ab16-selected-byte-launch-v2"
)
SELECTED_BYTE_EXECUTION_STRATEGY_V1 = (
    "selected-byte-python-loader-fd-v1"
)
SELECTED_BYTE_EXECUTION_STRATEGY_V2 = (
    "selected-byte-python-loader-budget-fd-v2"
)
SELECTED_BYTE_FD_MAP_V1 = {
    "authority": 5,
    "loader": 4,
    "python": 3,
}
SELECTED_BYTE_FD_MAP_V2 = {
    "authority": 5,
    "budget_broker": 8,
    "loader": 4,
    "native_helper": 7,
    "native_helper_wrapper": 6,
    "python": 3,
}
SELECTED_BYTE_OPEN_FILE_NAMES_V1 = [
    "ab16-python",
    "ab16-loader",
    "ab16-authority",
]
SELECTED_BYTE_OPEN_FILE_NAMES_V2 = [
    "ab16-python",
    "ab16-loader",
    "ab16-authority",
    "ab16-native-helper-wrapper",
    "ab16-native-helper",
    "ab16-budget-broker",
]
FORMAL_LOADER_ROLE = "ab16_formal_loader_v1"
FORMAL_RUNNER_MODULE = "docs.research.noncert_cuts_ab16_20260724.organic_arm_runner_v1"
FORMAL_WORKER_SESSION_SCHEMA = (
    "noncert-cuts-ab16-formal-worker-session-v1"
)
MANAGER_OPENFILE_ARM_GRANT_SCHEMA = (
    "noncert-cuts-ab16-budget-broker-manager-openfile-arm-grant-v1"
)
MODULE_ORIGIN_RECEIPT_SCHEMA = "noncert-cuts-ab16-module-origin-receipt-v1"
FORMAL_MODULE_ORIGIN_RECEIPT_SCHEMA = (
    "noncert-cuts-ab16-organic-arm-module-origin-receipt-v2"
)
BUDGET_SEGMENT_BUNDLE_SCHEMA = "noncert-cuts-ab16-budget-segment-bundle-v1"
BUDGET_WORKER_CONFINEMENT = "landlock-read-only-worker-v1"
CALIBRATION_TOOL_ROLES = frozenset(
    {
        "aggregator",
        "alternate_replayer",
        "fd_loader",
        "observer_harness",
        "package_verifier",
        "primary_replayer",
        "protocol",
        "runner",
        "workload",
    }
)
ARM_ROOT_INVENTORY_SCHEMA = "noncert-cuts-ab16-formal-root-inventory-v1"
ARM_MANIFEST_NAME = "attempt-artifact-manifest.json"
ARM_TERMINAL_DIRECTORY = "budget/arm-terminals"
ARM_REPLAY_DIRECTORY = "replays/arm-attempt-roots"
ARM_MANIFEST_BUDGET_LABEL = "AB16 organic attempt artifact manifest"
ARM_TERMINAL_BUDGET_LABEL = "AB16 arm budget terminal"
ARM_REPLAY_BUDGET_LABEL = "AB16 organic attempt root replay"
BUDGET_ARTIFACT_CLASS_BY_LABEL = {
    "AB16 immediate stop": "closeout",
    "attach model evidence": "model",
    "attach solution-vector evidence": "publication",
    "AB16 arm budget terminal": "closeout",
    "AB16 organic attempt artifact manifest": "publication",
    "AB16 organic attempt root replay": "closeout",
    "arm allocation unselected terminal": "closeout",
    "arm consumed incomplete": "closeout",
    "arm credibility gate": "publication",
    "arm launch environment": "metadata",
    "compile attach journal segment": "ledger",
    "cut ledger segment": "ledger",
    "cut-free incumbent replay receipt": "publication",
    "independent arithmetic replay receipt": "publication",
    "independent resource terminal replay": "publication",
    "module-origin receipt": "metadata",
    "organic arm failure record": "closeout",
    "organic arm consumption": "closeout",
    "organic arm result": "publication",
    "organic arm selection": "metadata",
    "organic pre-run authority": "metadata",
    "organic pre-run candidate": "metadata",
    "preselection manager epoch": "metadata",
    "preselection manager transcript": "metadata",
    "raw incumbent export": "publication",
    "raw solution-vector export": "publication",
    "runtime cut segment": "ledger",
    "terminal classification": "publication",
}
BUDGET_ARM_DIRECTORY_SUFFIX_MODES = (
    ("checkpoint", 0o700),
    ("checkpoint/runtime-cuts", 0o700),
    ("ledger", 0o700),
    ("ledger/compile-attach-journal", 0o700),
    ("ledger/cut-ledger", 0o700),
    ("replays", 0o700),
    ("runtime", 0o700),
    ("tmp", 0o500),
)

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
PER_ARM_TOOL_ROLES = frozenset(
    {
        "cut_free_replay",
        "resource_lifecycle",
        "resource_verifier",
        "terminal_gate",
        "terminal_replay",
        "unit_orchestrator",
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


class RunnerError(RuntimeError):
    """An authority, lifecycle, evidence, or no-overwrite gate failed."""


@dataclass(frozen=True)
class Snapshot:
    """Bytes and detached identity from one stable open descriptor."""

    data: bytes
    identity: dict[str, object]


@dataclass(frozen=True)
class PinnedCutFreeReplayInputs:
    """Package-bound inputs retained for the per-arm cut-free replay."""

    admission: Mapping[str, Any]
    admission_tool: Snapshot
    cut_free_tool: Snapshot


@dataclass(frozen=True)
class ArmContext:
    """Strict inputs passed to an arm implementation."""

    attempt_dir: Path
    budget_backend: "ArmBudgetBackend | None"
    enabled_families: tuple[str, ...]
    ledger: Any
    manifest: Mapping[str, Any]
    repository_root: Path
    execution_source: Mapping[str, Any]
    live_source_provenance_root: Path
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


class ArmBudgetBackend(Protocol):
    """Runner-facing view of one already allocated broker-backed arm budget.

    The formal owner supplies this object only after package verification and
    arm allocation.  It owns the connected broker transport; the worker never
    receives a writable root or staging descriptor.
    """

    @property
    def authority_binding(self) -> Mapping[str, object]: ...

    def maximum_bytes(self, label: str, *, artifact_class: str) -> int: ...

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


def _validate_budget_binding(
    backend: ArmBudgetBackend,
    *,
    expected_arm_slot: str,
) -> dict[str, object]:
    record = _exact_keys(
        backend.authority_binding,
        {
            "arm_allocation_id",
            "arm_allocation_identity",
            "arm_slot",
            "broker_nonce",
            "broker_socket_fd",
            "filesystem_write_confinement",
            "formal_budget_authority_identity",
            "next_sequence",
        },
        "arm budget authority binding",
    )
    _exact_identity(
        record["formal_budget_authority_identity"],
        "formal budget authority identity",
    )
    allocation_identity = record["arm_allocation_identity"]
    if (
        type(allocation_identity) is not dict
        or set(allocation_identity) != {"sha256", "size_bytes"}
        or type(allocation_identity["sha256"]) is not str
        or SHA256_RE.fullmatch(allocation_identity["sha256"]) is None
        or type(allocation_identity["size_bytes"]) is not int
        or allocation_identity["size_bytes"] <= 0
        or type(record["arm_allocation_id"]) is not str
        or SHA256_RE.fullmatch(record["arm_allocation_id"]) is None
        or record["arm_allocation_id"] != allocation_identity["sha256"]
        or record["arm_slot"] != expected_arm_slot
        or type(record["broker_nonce"]) is not str
        or SAFE_TOKEN_RE.fullmatch(record["broker_nonce"]) is None
        or type(record["broker_socket_fd"]) is not int
        or record["broker_socket_fd"] < 0
        or type(record["next_sequence"]) is not int
        or record["next_sequence"] <= 0
        or record["filesystem_write_confinement"] != BUDGET_WORKER_CONFINEMENT
    ):
        raise RunnerError("arm budget authority binding drifted")
    return dict(record)


def _budget_maximum(
    backend: ArmBudgetBackend,
    label: str,
    *,
    artifact_class: str,
) -> int:
    if BUDGET_ARTIFACT_CLASS_BY_LABEL.get(label) != artifact_class:
        raise RunnerError(f"{label}: artifact label/class is not preregistered")
    maximum = backend.maximum_bytes(label, artifact_class=artifact_class)
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        raise RunnerError(f"{label}: budget backend returned an invalid fixed maximum")
    return maximum


class BrokerProcessArmBudgetBackend:
    """Package-side adapter over one already connected persistent broker.

    Construction does not allocate an arm or create directories.  Those
    operations belong to the owner/supervisor authority chain.  This adapter
    accepts only the fixed maxima and channel directories that chain already
    bound, and moves payloads through fully sealed anonymous memfds.
    """

    def __init__(
        self,
        *,
        broker_client: Any,
        native_helper: Any,
        formal_root: Path,
        attempt_root: Path,
        formal_budget_runtime: Mapping[str, object] | None = None,
        enforced_budget_profile: Mapping[str, object] | None = None,
        enforced_budget_profile_identity: Mapping[str, object] | None = None,
        resource_calibration_authorization_bundle: Mapping[
            str, object
        ]
        | None = None,
        resource_calibration_authorization_bundle_identity: Mapping[
            str, object
        ]
        | None = None,
        expected_calibration_tool_identities: Mapping[
            str, Mapping[str, object]
        ]
        | None = None,
        authority_binding: Mapping[str, object],
        fixed_maxima: Mapping[str, Mapping[str, object]],
        channel_contracts: Mapping[str, Mapping[str, object]],
        manager_openfile_arm_grant: Mapping[str, object] | None = None,
        guardian_ready_identity: Mapping[str, object] | None = None,
        pidfd_opener: Callable[[int], tuple[int, str]] | None = None,
    ) -> None:
        self._broker = broker_client
        self._helper = native_helper
        self._formal_root = Path(os.path.abspath(formal_root))
        self._attempt_root = Path(os.path.abspath(attempt_root))
        self._formal_budget_runtime = (
            None
            if formal_budget_runtime is None
            else dict(formal_budget_runtime)
        )
        self._enforced_budget_profile = (
            None
            if enforced_budget_profile is None
            else dict(enforced_budget_profile)
        )
        self._enforced_budget_profile_identity = (
            None
            if enforced_budget_profile_identity is None
            else dict(enforced_budget_profile_identity)
        )
        self._resource_calibration_authorization_bundle = (
            None
            if resource_calibration_authorization_bundle is None
            else dict(resource_calibration_authorization_bundle)
        )
        self._resource_calibration_authorization_bundle_identity = (
            None
            if resource_calibration_authorization_bundle_identity is None
            else dict(
                resource_calibration_authorization_bundle_identity
            )
        )
        if (
            type(expected_calibration_tool_identities) is not dict
            or set(expected_calibration_tool_identities)
            != CALIBRATION_TOOL_ROLES
        ):
            raise RunnerError(
                "arm calibration tool identity cohort is absent or mixed"
            )
        checked_calibration_tools: dict[
            str, dict[str, object]
        ] = {}
        for role, identity in sorted(
            expected_calibration_tool_identities.items()
        ):
            if (
                type(identity) is not dict
                or set(identity) != {"sha256", "size_bytes"}
                or type(identity["sha256"]) is not str
                or SHA256_RE.fullmatch(identity["sha256"]) is None
                or isinstance(identity["size_bytes"], bool)
                or not isinstance(identity["size_bytes"], int)
                or identity["size_bytes"] <= 0
            ):
                raise RunnerError(
                    "arm calibration tool content identity is malformed"
                )
            checked_calibration_tools[role] = dict(identity)
        self._expected_calibration_tool_identities = (
            checked_calibration_tools
        )
        try:
            self._attempt_root.relative_to(self._formal_root)
        except ValueError as exc:
            raise RunnerError("budgeted attempt root escaped formal root") from exc
        self._binding = dict(authority_binding)
        self._manager_openfile_arm_grant = (
            None
            if manager_openfile_arm_grant is None
            else dict(manager_openfile_arm_grant)
        )
        self._guardian_ready_identity = (
            None
            if guardian_ready_identity is None
            else dict(guardian_ready_identity)
        )
        self._pidfd_opener = pidfd_opener
        if (
            self._manager_openfile_arm_grant is None
        ) != (
            self._guardian_ready_identity is None
        ):
            raise RunnerError(
                "manager OpenFile arm binding inputs are incomplete"
            )
        broker_sequence = getattr(broker_client, "sequence", None)
        if (
            getattr(broker_client, "nonce", None) != self._binding.get("broker_nonce")
            or getattr(getattr(broker_client, "connection", None), "fileno", lambda: -1)()
            != self._binding.get("broker_socket_fd")
            or type(broker_sequence) is not int
            or broker_sequence + 1
            != self._binding.get("next_sequence")
            or getattr(broker_client, "native_helper", None) is not native_helper
        ):
            raise RunnerError("connected budget broker identity differs from binding")
        checked_maxima: dict[str, tuple[str, int]] = {}
        checked_fixed_paths: dict[str, str] = {}
        for label, raw in fixed_maxima.items():
            if (
                type(label) is not str
                or not label
                or type(raw) is not dict
                or set(raw)
                != {
                    "artifact_class",
                    "branch",
                    "maximum_bytes",
                    "maximum_publications",
                    "multiplicity_source",
                    "path_contract",
                }
                or type(raw["artifact_class"]) is not str
                or isinstance(raw["maximum_bytes"], bool)
                or not isinstance(raw["maximum_bytes"], int)
                or raw["maximum_bytes"] <= 0
                or isinstance(raw["maximum_publications"], bool)
                or not isinstance(raw["maximum_publications"], int)
                or raw["maximum_publications"] < 0
                or raw["branch"] not in {"common", "failure", "success"}
                or type(raw["multiplicity_source"]) is not dict
                or type(raw["path_contract"]) is not dict
            ):
                raise RunnerError("fixed arm artifact maximum table is invalid")
            checked_maxima[label] = (
                raw["artifact_class"],
                raw["maximum_bytes"],
            )
            path_contract = cast(
                Mapping[str, object],
                raw["path_contract"],
            )
            if path_contract.get("kind") == "fixed":
                if (
                    set(path_contract)
                    != {"kind", "root", "root_relative_path"}
                    or path_contract.get("root") != "formal-root"
                    or type(path_contract.get("root_relative_path"))
                    is not str
                ):
                    raise RunnerError(
                        "fixed arm artifact path contract is invalid"
                    )
                relative = Path(
                    cast(str, path_contract["root_relative_path"])
                )
                if (
                    relative.is_absolute()
                    or not relative.parts
                    or any(
                        part in {"", ".", ".."}
                        for part in relative.parts
                    )
                ):
                    raise RunnerError(
                        "fixed arm artifact path escaped formal root"
                    )
                checked_fixed_paths[label] = relative.as_posix()
        self._fixed_maxima = checked_maxima
        self._fixed_paths = checked_fixed_paths
        if set(checked_maxima) != set(BUDGET_ARTIFACT_CLASS_BY_LABEL):
            raise RunnerError("fixed arm artifact maximum table is incomplete")
        for label, (artifact_class, _maximum) in checked_maxima.items():
            if BUDGET_ARTIFACT_CLASS_BY_LABEL[label] != artifact_class:
                raise RunnerError("fixed arm artifact maximum class differs")
        checked_channels: dict[str, str] = {}
        checked_channel_labels: dict[str, str] = {}
        checked_channel_maximum_segments: dict[str, int] = {}
        for channel, raw in channel_contracts.items():
            if (
                type(channel) is not str
                or SAFE_TOKEN_RE.fullmatch(channel) is None
                or type(raw) is not dict
                or set(raw)
                != {
                    "artifact_class",
                    "label",
                    "maximum_bytes",
                    "maximum_segments",
                    "relative_path",
                }
                or type(raw["label"]) is not str
                or type(raw["artifact_class"]) is not str
                or isinstance(raw["maximum_bytes"], bool)
                or not isinstance(raw["maximum_bytes"], int)
                or raw["maximum_bytes"] <= 0
                or isinstance(raw["maximum_segments"], bool)
                or not isinstance(raw["maximum_segments"], int)
                or raw["maximum_segments"] < 0
                or type(raw["relative_path"]) is not str
            ):
                raise RunnerError("immutable channel directory table is invalid")
            relative = raw["relative_path"]
            relative_path = Path(relative)
            if (
                relative_path.is_absolute()
                or not relative_path.parts
                or any(part in {"", ".", ".."} for part in relative_path.parts)
            ):
                raise RunnerError("immutable channel directory escaped formal root")
            checked_channels[channel] = relative_path.as_posix()
            checked_channel_labels[channel] = raw["label"]
            checked_channel_maximum_segments[channel] = raw[
                "maximum_segments"
            ]
        arm_slot = self._binding.get("arm_slot")
        if type(arm_slot) is not str or SAFE_TOKEN_RE.fullmatch(arm_slot) is None:
            raise RunnerError("budget broker arm slot is invalid")
        allocation_identity = self._binding.get("arm_allocation_identity")
        if (
            type(allocation_identity) is not dict
            or set(allocation_identity) != {"sha256", "size_bytes"}
            or type(allocation_identity["sha256"]) is not str
            or SHA256_RE.fullmatch(allocation_identity["sha256"]) is None
            or type(allocation_identity["size_bytes"]) is not int
            or allocation_identity["size_bytes"] <= 0
            or self._binding.get("arm_allocation_id")
            != allocation_identity["sha256"]
        ):
            raise RunnerError("budget broker arm allocation identity is invalid")
        attempt_relative = self._attempt_root.relative_to(self._formal_root).as_posix()
        expected_channels = {
            f"arm-{arm_slot}-compile-journal": (
                f"{attempt_relative}/ledger/compile-attach-journal"
            ),
            f"arm-{arm_slot}-cut-ledger": f"{attempt_relative}/ledger/cut-ledger",
            f"arm-{arm_slot}-runtime-cuts": (
                f"{attempt_relative}/checkpoint/runtime-cuts"
            ),
        }
        if checked_channels != expected_channels:
            raise RunnerError("immutable channel directory table differs from fixed arm layout")
        expected_channel_labels = {
            f"arm-{arm_slot}-compile-journal": (
                "compile attach journal segment"
            ),
            f"arm-{arm_slot}-cut-ledger": "cut ledger segment",
            f"arm-{arm_slot}-runtime-cuts": "runtime cut segment",
        }
        if (
            checked_channel_labels != expected_channel_labels
            or checked_channel_maximum_segments
            != {
                f"arm-{arm_slot}-compile-journal": 221,
                f"arm-{arm_slot}-cut-ledger": 258,
                f"arm-{arm_slot}-runtime-cuts": 0,
            }
            or any(
                raw["artifact_class"] != "ledger"
                or raw["maximum_bytes"]
                != checked_maxima[checked_channel_labels[channel]][1]
                for channel, raw in channel_contracts.items()
            )
        ):
            raise RunnerError(
                "immutable channel multiplicity contract drifted"
            )
        self._channel_directories = checked_channels
        self._channel_labels = checked_channel_labels
        self._channel_maximum_segments = (
            checked_channel_maximum_segments
        )
        self._channel_next: dict[str, int] = {}
        self._confinement_installed = False
        self._accepted_arm_seal: dict[str, object] | None = None
        self._post_seal_replay_identity: dict[str, object] | None = None
        self._worker_grant_registered = False
        self._manager_openfile_arm_bind_attempted = False

    @property
    def authority_binding(self) -> Mapping[str, object]:
        return dict(self._binding)

    @property
    def formal_budget_runtime(self) -> Mapping[str, object]:
        if self._formal_budget_runtime is None:
            raise RunnerError(
                "arm budget backend lacks its closed formal runtime binding"
            )
        return dict(self._formal_budget_runtime)

    @property
    def enforced_budget_profile(self) -> Mapping[str, object]:
        if self._enforced_budget_profile is None:
            raise RunnerError("arm budget profile is absent")
        return dict(self._enforced_budget_profile)

    @property
    def enforced_budget_profile_identity(
        self,
    ) -> Mapping[str, object]:
        if self._enforced_budget_profile_identity is None:
            raise RunnerError("arm budget profile identity is absent")
        return dict(self._enforced_budget_profile_identity)

    @property
    def resource_calibration_authorization_bundle(
        self,
    ) -> Mapping[str, object]:
        if self._resource_calibration_authorization_bundle is None:
            raise RunnerError("arm resource calibration bundle is absent")
        return dict(self._resource_calibration_authorization_bundle)

    @property
    def resource_calibration_authorization_bundle_identity(
        self,
    ) -> Mapping[str, object]:
        if (
            self._resource_calibration_authorization_bundle_identity
            is None
        ):
            raise RunnerError(
                "arm resource calibration bundle identity is absent"
            )
        return dict(
            self._resource_calibration_authorization_bundle_identity
        )

    @property
    def expected_calibration_tool_identities(
        self,
    ) -> Mapping[str, Mapping[str, object]]:
        return {
            role: dict(identity)
            for role, identity in sorted(
                self._expected_calibration_tool_identities.items()
            )
        }

    def install_worker_confinement(
        self,
        retained_read_only_fds: Sequence[int],
    ) -> Mapping[str, object]:
        if (
            self._binding.get("filesystem_write_confinement")
            != "landlock-read-only-worker-v1"
            or self._confinement_installed
        ):
            raise RunnerError(
                "arm worker confinement is unavailable or already installed"
            )
        from docs.research.noncert_cuts_ab16_20260724 import (
            ab16_budget_broker_v1 as broker_module,
        )

        try:
            stdio_contract = broker_module.validate_worker_stdio_contract()
        except broker_module.BrokerProtocolError as exc:
            raise RunnerError(
                f"arm worker stdio contract failed: {exc.code}"
            ) from exc
        connection_fd = self._broker.connection.fileno()
        keep = {0, 1, 2, connection_fd}
        for descriptor in retained_read_only_fds:
            if (
                isinstance(descriptor, bool)
                or not isinstance(descriptor, int)
                or descriptor < 0
                or fcntl.fcntl(descriptor, fcntl.F_GETFL)
                & os.O_ACCMODE
                != os.O_RDONLY
            ):
                raise RunnerError(
                    "arm retained read-only FD allowlist is invalid"
                )
            keep.add(descriptor)
        if self._helper.landlock_abi() < 1:
            raise RunnerError("arm worker requires a positive Landlock ABI")
        self._helper.close_range_allowlist(sorted(keep))
        self._helper.install_no_filesystem_writes_landlock()
        self._confinement_installed = True
        return {
            "filesystem_write_confinement": (
                "landlock-read-only-worker-v1"
            ),
            "retained_read_only_fds": sorted(
                descriptor
                for descriptor in keep
                if descriptor not in {0, 1, 2, connection_fd}
            ),
            "root_or_staging_writable_fd_count": 0,
            "stdio_contract": stdio_contract,
        }

    def register_arm_worker_grant(
        self,
        *,
        credential: str,
        expected_peer: Mapping[str, object],
        pidfd: int,
    ) -> Mapping[str, object]:
        """Bind the one organic worker to this manager-selected supervisor."""

        selection_identity = self._binding.get("selection_identity")
        allocation_identity = self._binding.get(
            "arm_allocation_identity"
        )
        arm_slot = self._binding.get("arm_slot")
        if (
            self._binding.get("filesystem_write_confinement")
            != "not-applicable-persistent-supervisor-v1"
            or self._worker_grant_registered
            or type(selection_identity) is not dict
            or type(allocation_identity) is not dict
            or type(arm_slot) is not str
        ):
            raise RunnerError(
                "arm supervisor worker-grant authority is absent or consumed"
            )
        try:
            response = self._broker.register_bound_arm_grant(
                {
                    "allocation_identity": dict(allocation_identity),
                    "arm_slot": arm_slot,
                    "credential": credential,
                    "expected_peer": dict(expected_peer),
                    "role": "arm",
                    "selection_identity": dict(selection_identity),
                },
                pidfd=pidfd,
            )
            result = response.record.get("result")
        except Exception as exc:
            raise RunnerError(
                "arm worker grant registration failed or is uncertain"
            ) from exc
        self._worker_grant_registered = True
        if (
            type(result) is not dict
            or result.get("role") != "arm"
            or result.get("arm_slot") != arm_slot
            or result.get("selection_identity")
            != selection_identity
            or result.get("allocation_identity")
            != allocation_identity
        ):
            raise RunnerError("arm worker grant receipt drifted")
        return dict(result)

    def bind_manager_openfile_arm_grant(
        self,
        *,
        application_peer: Mapping[str, object],
        pidfd: int,
        pidfd_method: str,
    ) -> Mapping[str, object]:
        """Bind the selected systemd unit MainPID before FD8 authentication."""

        handoff = self._manager_openfile_arm_grant
        guardian_ready = self._guardian_ready_identity
        if (
            self._binding.get("filesystem_write_confinement")
            != "not-applicable-persistent-supervisor-v1"
            or handoff is None
            or guardian_ready is None
            or self._manager_openfile_arm_bind_attempted
        ):
            raise RunnerError(
                "manager OpenFile arm bind authority is absent or consumed"
            )
        self._manager_openfile_arm_bind_attempted = True
        record = _exact_keys(
            handoff,
            {"credential", "preregistration"},
            "manager OpenFile arm handoff",
        )
        preregistration = _exact_keys(
            record["preregistration"],
            {
                "allocation_identity",
                "arm_slot",
                "attempt_consumption_identity",
                "credential_sha256",
                "manager_epoch_identity",
                "schema_version",
                "selection_identity",
                "state",
                "unit_name",
            },
            "manager OpenFile arm preregistration",
        )
        credential = record["credential"]
        if (
            type(credential) is not str
            or SHA256_RE.fullmatch(credential) is None
            or preregistration["credential_sha256"]
            != hashlib.sha256(credential.encode("ascii")).hexdigest()
            or preregistration["allocation_identity"]
            != self._binding.get("arm_allocation_identity")
            or preregistration["arm_slot"]
            != self._binding.get("arm_slot")
            or type(pidfd_method) is not str
            or not pidfd_method
        ):
            raise RunnerError(
                "manager OpenFile arm handoff identity drifted"
            )
        try:
            response = self._broker.bind_manager_openfile_arm_grant(
                {
                    "allocation_identity": dict(
                        cast(
                            Mapping[str, object],
                            preregistration[
                                "allocation_identity"
                            ],
                        )
                    ),
                    "application_peer": dict(application_peer),
                    "arm_slot": preregistration["arm_slot"],
                    "attempt_consumption_identity": dict(
                        cast(
                            Mapping[str, object],
                            preregistration[
                                "attempt_consumption_identity"
                            ],
                        )
                    ),
                    "credential": credential,
                    "guardian_ready_identity": dict(guardian_ready),
                    "pidfd_method": pidfd_method,
                    "selection_identity": dict(
                        cast(
                            Mapping[str, object],
                            preregistration["selection_identity"],
                        )
                    ),
                },
                pidfd=pidfd,
            )
            result = response.record.get("result")
        except Exception as exc:
            raise RunnerError(
                "manager OpenFile arm bind failed or is uncertain"
            ) from exc
        if (
            type(result) is not dict
            or result.get("schema_version")
            != MANAGER_OPENFILE_ARM_GRANT_SCHEMA
            or result.get("state") != "BOUND"
            or result.get("application_peer")
            != dict(application_peer)
            or result.get("allocation_identity")
            != preregistration["allocation_identity"]
            or result.get("arm_slot") != preregistration["arm_slot"]
            or result.get("selection_identity")
            != preregistration["selection_identity"]
            or result.get("guardian_ready_identity")
            != guardian_ready
        ):
            raise RunnerError(
                "manager OpenFile arm bind receipt drifted"
            )
        return dict(result)

    def open_manager_openfile_pidfd(
        self,
        pid: int,
    ) -> tuple[int, str]:
        """Open the MainPID capability through the package-pinned broker."""

        if (
            self._binding.get("filesystem_write_confinement")
            != "not-applicable-persistent-supervisor-v1"
            or self._pidfd_opener is None
        ):
            raise RunnerError(
                "manager OpenFile pidfd authority is unavailable"
            )
        try:
            descriptor, method = self._pidfd_opener(pid)
        except Exception as exc:
            raise RunnerError(
                "manager OpenFile pidfd open failed"
            ) from exc
        if (
            isinstance(descriptor, bool)
            or not isinstance(descriptor, int)
            or descriptor < 0
            or type(method) is not str
            or not method
        ):
            if type(descriptor) is int and descriptor >= 0:
                os.close(descriptor)
            raise RunnerError(
                "manager OpenFile pidfd opener returned invalid authority"
            )
        return descriptor, method

    def close(self) -> None:
        close_session = getattr(self._broker, "close_session", None)
        if callable(close_session):
            close_session()
            return
        close = getattr(self._broker, "close", None)
        if callable(close):
            close()

    def maximum_bytes(self, label: str, *, artifact_class: str) -> int:
        try:
            expected_class, maximum = self._fixed_maxima[label]
        except KeyError as exc:
            raise RunnerError(f"{label}: no predeclared artifact maximum") from exc
        if artifact_class != expected_class:
            raise RunnerError(f"{label}: artifact class differs from fixed maximum")
        return maximum

    def _relative_output(self, path: Path, *, label: str | None = None) -> str:
        absolute = Path(os.path.abspath(path))
        if label is not None and label in self._fixed_paths:
            expected = self._formal_root / self._fixed_paths[label]
            if absolute != expected:
                raise RunnerError(
                    "arm artifact differs from its fixed target"
                )
            return self._fixed_paths[label]
        try:
            absolute.relative_to(self._attempt_root)
            relative = absolute.relative_to(self._formal_root)
        except ValueError as exc:
            raise RunnerError("budgeted arm output escaped its attempt root") from exc
        return relative.as_posix()

    @staticmethod
    def _sha256_descriptor(descriptor: int, size_bytes: int) -> str:
        digest = hashlib.sha256()
        offset = 0
        while offset < size_bytes:
            block = os.pread(descriptor, min(1024 * 1024, size_bytes - offset), offset)
            if not block:
                raise RunnerError("sealed memfd ended before its stated size")
            digest.update(block)
            offset += len(block)
        if os.pread(descriptor, 1, size_bytes):
            raise RunnerError("sealed memfd exceeds its stated size")
        return digest.hexdigest()

    def _publish_descriptor(
        self,
        descriptor: int,
        *,
        path: Path,
        size_bytes: int,
        digest: str,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
        channel: str | None = None,
        sequence: int | None = None,
        publication_boundary: Callable[[], None] | None = None,
    ) -> dict[str, object]:
        relative = self._relative_output(path, label=label)
        try:
            response = self._broker.publish_descriptor(
                {
                    "arm_slot": self._binding["arm_slot"],
                    "artifact_class": artifact_class,
                    "channel": channel,
                    "expected_sha256": digest,
                    "label": label,
                    "maximum_bytes": maximum_bytes,
                    "relative_path": relative,
                    "sequence": sequence,
                    "size_bytes": size_bytes,
                },
                descriptor=descriptor,
                publication_boundary=publication_boundary,
            )
            result = dict(response.record["result"])
        except Exception as exc:
            raise RunnerError(
                "broker descriptor publication failed or acknowledgement is uncertain"
            ) from exc
        if (
            result.get("path") != relative
            or result.get("sha256") != digest
            or result.get("size_bytes") != size_bytes
            or result.get("maximum_bytes") != maximum_bytes
            or type(result.get("source_seal_mask")) is not int
            or result["source_seal_mask"] != self._helper.final_seal_mask
        ):
            raise RunnerError("broker descriptor publication receipt differs")
        return {
            **result,
            "path": str(Path(os.path.abspath(path))),
        }

    def _sealed_bytes_memfd(self, raw: bytes, *, label: str) -> int:
        descriptor = self._helper.create_memfd(
            f"ab16-{hashlib.sha256(label.encode()).hexdigest()[:16]}"
        )
        try:
            offset = 0
            while offset < len(raw):
                written = os.pwrite(descriptor, raw[offset:], offset)
                if written <= 0:
                    raise RunnerError(f"{label}: memfd write made no progress")
                offset += written
            os.fsync(descriptor)
            if os.fstat(descriptor).st_size != len(raw):
                raise RunnerError(f"{label}: memfd size differs")
            if self._sha256_descriptor(descriptor, len(raw)) != hashlib.sha256(raw).hexdigest():
                raise RunnerError(f"{label}: memfd digest differs")
            if self._helper.has_writable_mapping(descriptor):
                raise RunnerError(f"{label}: memfd has a writable mapping")
            installed = self._helper.install_final_seals(descriptor)
            if (
                installed != self._helper.final_seal_mask
                or self._helper.get_seals(descriptor) != self._helper.final_seal_mask
            ):
                raise RunnerError(f"{label}: final memfd seal mask differs")
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def publish_bytes(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
    ) -> Mapping[str, object]:
        return self._publish_fixed_bytes(
            path,
            raw,
            maximum_bytes=maximum_bytes,
            artifact_class=artifact_class,
            label=label,
            publication_boundary=None,
        )

    def publish_bytes_with_publication_boundary(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
        publication_boundary: Callable[[], None],
    ) -> Mapping[str, object]:
        """Expose the broker client's exact last pre-send boundary."""

        if not callable(publication_boundary):
            raise RunnerError("arm publication boundary is not callable")
        return self._publish_fixed_bytes(
            path,
            raw,
            maximum_bytes=maximum_bytes,
            artifact_class=artifact_class,
            label=label,
            publication_boundary=publication_boundary,
        )

    def _publish_fixed_bytes(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
        publication_boundary: Callable[[], None] | None,
    ) -> Mapping[str, object]:
        if type(raw) is not bytes or len(raw) <= 0 or len(raw) > maximum_bytes:
            raise RunnerError(f"{label}: payload differs from its fixed allocation")
        if maximum_bytes != self.maximum_bytes(label, artifact_class=artifact_class):
            raise RunnerError(f"{label}: allocation maximum drifted")
        descriptor = self._sealed_bytes_memfd(raw, label=label)
        try:
            return self._publish_descriptor(
                descriptor,
                path=path,
                size_bytes=len(raw),
                digest=hashlib.sha256(raw).hexdigest(),
                maximum_bytes=maximum_bytes,
                artifact_class=artifact_class,
                label=label,
                publication_boundary=publication_boundary,
            )
        finally:
            os.close(descriptor)

    def expected_root_path_types(self) -> list[dict[str, str]]:
        """Return the broker's current exact formal-root path/type inventory."""

        try:
            response = self._broker.request("STATUS", {})
            result = response.record.get("result")
        except Exception as exc:
            raise RunnerError(
                "broker root inventory request failed or acknowledgement is uncertain"
            ) from exc
        if (
            type(result) is not dict
            or set(result) != {"contract", "root_closure", "root_inventory"}
            or type(result["root_inventory"]) is not dict
            or set(result["root_inventory"])
            != {"expected_path_types", "schema_version"}
            or result["root_inventory"]["schema_version"]
            != ARM_ROOT_INVENTORY_SCHEMA
            or type(result["root_inventory"]["expected_path_types"]) is not list
        ):
            raise RunnerError("broker root inventory receipt differs")
        rows: list[dict[str, str]] = []
        for item in result["root_inventory"]["expected_path_types"]:
            if (
                type(item) is not dict
                or set(item) != {"path", "type"}
                or type(item["path"]) is not str
                or type(item["type"]) is not str
                or item["type"] not in {"directory", "regular"}
            ):
                raise RunnerError("broker root inventory row differs")
            path = PurePosixPath(item["path"])
            if (
                path.is_absolute()
                or not path.parts
                or any(part in {"", ".", ".."} for part in path.parts)
                or path.as_posix() != item["path"]
            ):
                raise RunnerError("broker root inventory path is invalid")
            rows.append({"path": item["path"], "type": item["type"]})
        if (
            rows != sorted(rows, key=lambda item: (item["path"], item["type"]))
            or len({item["path"] for item in rows}) != len(rows)
        ):
            raise RunnerError("broker root inventory is not canonical")
        return rows

    def publish_arm_manifest_and_seal(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
        arm_slot: str,
        arm_attempt_prefix: str,
        arm_allocation_identity: Mapping[str, object],
        expected_path_types_before: Sequence[Mapping[str, object]],
    ) -> Mapping[str, object]:
        """Atomically publish the arm manifest and pending-ACK terminal."""

        slot = cast(str, self._binding["arm_slot"])
        allocation_identity = cast(
            dict[str, object],
            self._binding["arm_allocation_identity"],
        )
        expected_manifest = self._attempt_root / ARM_MANIFEST_NAME
        expected_prefix = self._attempt_root.relative_to(
            self._formal_root
        ).as_posix()
        if (
            label != ARM_MANIFEST_BUDGET_LABEL
            or artifact_class != "publication"
            or arm_slot != slot
            or arm_attempt_prefix != expected_prefix
            or Path(os.path.abspath(path)) != expected_manifest
            or dict(arm_allocation_identity) != allocation_identity
            or maximum_bytes
            != self.maximum_bytes(
                ARM_MANIFEST_BUDGET_LABEL,
                artifact_class="publication",
            )
            or type(raw) is not bytes
            or not 0 < len(raw) <= maximum_bytes
        ):
            raise RunnerError("arm manifest seal request differs from its fixed authority")
        rows: list[dict[str, str]] = []
        for item in expected_path_types_before:
            if (
                type(item) is not dict
                or set(item) != {"path", "type"}
                or type(item["path"]) is not str
                or type(item["type"]) is not str
                or item["type"] not in {"directory", "regular"}
            ):
                raise RunnerError("arm seal root inventory row differs")
            rows.append(
                {
                    "path": cast(str, item["path"]),
                    "type": cast(str, item["type"]),
                }
            )
        if (
            rows != sorted(rows, key=lambda item: (item["path"], item["type"]))
            or len({item["path"] for item in rows}) != len(rows)
        ):
            raise RunnerError("arm seal root inventory is not canonical")
        terminal_maximum = self.maximum_bytes(
            ARM_TERMINAL_BUDGET_LABEL,
            artifact_class="closeout",
        )
        replay_maximum = self.maximum_bytes(
            ARM_REPLAY_BUDGET_LABEL,
            artifact_class="closeout",
        )
        consumption_maximum = self.maximum_bytes(
            "organic arm consumption",
            artifact_class="closeout",
        )
        descriptor = self._sealed_bytes_memfd(
            raw,
            label=ARM_MANIFEST_BUDGET_LABEL,
        )
        try:
            response = self._broker.publish_arm_manifest_and_seal(
                {
                    "arm_allocation_identity": dict(allocation_identity),
                    "arm_attempt_prefix": expected_prefix,
                    "arm_slot": slot,
                    "expected_path_types_before": rows,
                    "manifest_expected_sha256": hashlib.sha256(raw).hexdigest(),
                    "manifest_maximum_bytes": maximum_bytes,
                    "manifest_size_bytes": len(raw),
                    "replay_maximum_bytes": replay_maximum,
                    "consumption_maximum_bytes": consumption_maximum,
                    "terminal_maximum_bytes": terminal_maximum,
                },
                descriptor=descriptor,
            )
        except Exception as exc:
            raise RunnerError(
                "arm manifest seal failed or acknowledgement is uncertain"
            ) from exc
        finally:
            os.close(descriptor)
        result = response.record.get("result")
        if (
            type(result) is not dict
            or set(result) != {"terminal", "terminal_identity"}
            or type(result["terminal"]) is not dict
            or type(result["terminal_identity"]) is not dict
        ):
            raise RunnerError("arm manifest seal acknowledgement differs")
        terminal = cast(dict[str, object], result["terminal"])
        terminal_identity = cast(
            dict[str, object],
            result["terminal_identity"],
        )
        terminal_size = terminal_identity.get("size_bytes")
        expected_terminal = (
            self._formal_root
            / ARM_TERMINAL_DIRECTORY
            / f"{slot}.json"
        )
        if (
            set(terminal_identity) != {"path", "sha256", "size_bytes"}
            or terminal_identity.get("path") != str(expected_terminal)
            or type(terminal_identity.get("sha256")) is not str
            or SHA256_RE.fullmatch(
                cast(str, terminal_identity["sha256"])
            )
            is None
            or type(terminal_size) is not int
            or terminal_size <= 0
            or terminal.get("status") != "SEAL_DURABLE_PENDING_ACK"
            or terminal.get("allocation_state") != "SEALED_PENDING_ACK"
            or terminal.get("arm_slot") != slot
            or terminal.get("arm_attempt_prefix") != expected_prefix
            or terminal.get("arm_allocation_identity")
            != allocation_identity
        ):
            raise RunnerError("arm manifest seal terminal join differs")
        return {
            "response_authentication": {
                "nonce": self._broker.nonce,
                "response_sequence": self._broker.sequence,
                "response_sha256": response.sha256,
            },
            "terminal": dict(terminal),
            "terminal_identity": dict(terminal_identity),
        }

    def accept_prior_arm_seal_response(
        self,
        *,
        continuation: str,
        successor_arm_slot: str | None,
    ) -> Mapping[str, object]:
        """Durably accept the immediately preceding seal on this connection."""

        try:
            response = self._broker.accept_prior_arm_seal_response(
                continuation=continuation,
                successor_arm_slot=successor_arm_slot,
            )
        except Exception as exc:
            raise RunnerError(
                "prior arm seal acceptance failed or acknowledgement is uncertain"
            ) from exc
        result = response.record.get("result")
        journal = response.record.get("journal")
        if (
            type(result) is not dict
            or result.get("state") != "PRIOR_RESPONSE_ACCEPTED"
            or type(journal) is not dict
            or set(journal) != {"path", "sha256", "size_bytes"}
            or type(journal["path"]) is not str
            or type(journal["sha256"]) is not str
            or SHA256_RE.fullmatch(journal["sha256"]) is None
            or type(journal["size_bytes"]) is not int
            or journal["size_bytes"] <= 0
        ):
            raise RunnerError("prior arm seal acceptance receipt differs")
        accepted = {
            "accepted": dict(result),
            "journal": {
                "path": str(self._formal_root / journal["path"]),
                "sha256": journal["sha256"],
                "size_bytes": journal["size_bytes"],
            },
        }
        self._accepted_arm_seal = accepted
        return accepted

    def _publish_post_seal_bytes(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        label: str,
        kind: str,
        prerequisite_identity: Mapping[str, object] | None,
    ) -> Mapping[str, object]:
        accepted = self._accepted_arm_seal
        if accepted is None:
            raise RunnerError(
                "post-seal publication precedes durable response acceptance"
            )
        expected_label = (
            ARM_REPLAY_BUDGET_LABEL
            if kind == "replay"
            else "organic arm consumption"
        )
        expected_path = (
            self._formal_root
            / ARM_REPLAY_DIRECTORY
            / f"{self._binding['arm_slot']}.json"
            if kind == "replay"
            else self._formal_root
            / "prospective/consumptions"
            / f"{self._binding['arm_slot']}.json"
        )
        if (
            label != expected_label
            or Path(os.path.abspath(path)) != expected_path
            or maximum_bytes
            != self.maximum_bytes(label, artifact_class="closeout")
            or type(raw) is not bytes
            or not 0 < len(raw) <= maximum_bytes
            or (
                kind == "replay"
                and prerequisite_identity is not None
            )
            or (
                kind == "consumption"
                and (
                    prerequisite_identity is None
                    or dict(prerequisite_identity)
                    != self._post_seal_replay_identity
                )
            )
        ):
            raise RunnerError(
                "post-seal publication differs from its fixed arm authority"
            )
        descriptor = self._sealed_bytes_memfd(raw, label=label)
        payload = {
            "allocation_identity": dict(
                cast(
                    dict[str, object],
                    self._binding["arm_allocation_identity"],
                )
            ),
            "arm_slot": self._binding["arm_slot"],
            "expected_sha256": hashlib.sha256(raw).hexdigest(),
            "maximum_bytes": maximum_bytes,
            "prerequisite_identity": (
                None
                if prerequisite_identity is None
                else dict(prerequisite_identity)
            ),
            "prior_response_accepted_identity": dict(
                cast(dict[str, object], accepted["journal"])
            ),
            "relative_path": expected_path.relative_to(
                self._formal_root
            ).as_posix(),
            "size_bytes": len(raw),
        }
        try:
            response = (
                self._broker.publish_accepted_arm_replay(
                    payload,
                    descriptor=descriptor,
                )
                if kind == "replay"
                else self._broker.publish_arm_consumption(
                    payload,
                    descriptor=descriptor,
                )
            )
        except Exception as exc:
            raise RunnerError(
                f"post-seal {kind} publication failed or acknowledgement is uncertain"
            ) from exc
        finally:
            os.close(descriptor)
        result = response.record.get("result")
        if (
            type(result) is not dict
            or set(result) != {"publication_identity", "state"}
            or type(result["publication_identity"]) is not dict
            or result["state"]
            != (
                "REPLAY_PUBLISHED"
                if kind == "replay"
                else "ARM_CLOSED"
            )
            or result["publication_identity"]
            != {
                "path": str(expected_path),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            }
        ):
            raise RunnerError(
                f"post-seal {kind} publication receipt differs"
            )
        identity = dict(
            cast(dict[str, object], result["publication_identity"])
        )
        if kind == "replay":
            self._post_seal_replay_identity = identity
        return identity

    def publish_accepted_arm_replay(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        label: str,
    ) -> Mapping[str, object]:
        return self._publish_post_seal_bytes(
            path,
            raw,
            maximum_bytes=maximum_bytes,
            label=label,
            kind="replay",
            prerequisite_identity=None,
        )

    def publish_arm_consumption(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        label: str,
        replay_identity: Mapping[str, object],
    ) -> Mapping[str, object]:
        return self._publish_post_seal_bytes(
            path,
            raw,
            maximum_bytes=maximum_bytes,
            label=label,
            kind="consumption",
            prerequisite_identity=replay_identity,
        )

    def append_segment(
        self,
        channel: str,
        sequence: int,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        arm_slot: str | None = None,
    ) -> Mapping[str, object]:
        if arm_slot != self._binding.get("arm_slot"):
            raise RunnerError("immutable channel arm allocation identity drifted")
        try:
            directory = self._channel_directories[channel]
        except KeyError as exc:
            raise RunnerError("immutable channel was not preregistered") from exc
        expected = self._channel_next.get(channel, 0)
        if (
            sequence != expected
            or sequence >= self._channel_maximum_segments[channel]
        ):
            raise RunnerError("immutable channel sequence drifted")
        label = self._channel_labels[channel]
        if maximum_bytes != self.maximum_bytes(label, artifact_class=artifact_class):
            raise RunnerError("immutable channel allocation maximum drifted")
        target = self._formal_root / directory / f"segment-{sequence:08d}.bin"
        if type(raw) is not bytes or not 0 < len(raw) <= maximum_bytes:
            raise RunnerError(
                "immutable channel payload differs from its segment cap"
            )
        descriptor = self._sealed_bytes_memfd(
            raw,
            label=f"{label}:{sequence}",
        )
        try:
            receipt = self._publish_descriptor(
                descriptor,
                path=target,
                size_bytes=len(raw),
                digest=hashlib.sha256(raw).hexdigest(),
                maximum_bytes=maximum_bytes,
                artifact_class=artifact_class,
                label=label,
                channel=channel,
                sequence=sequence,
            )
        finally:
            os.close(descriptor)
        self._channel_next[channel] = sequence + 1
        return receipt

    def export_model_to_sealed_memfd(
        self,
        model: object,
        path: Path,
        *,
        maximum_bytes: int,
        label: str,
    ) -> Mapping[str, object]:
        if maximum_bytes != self.maximum_bytes(label, artifact_class="model"):
            raise RunnerError(f"{label}: model allocation maximum drifted")
        descriptor = self._helper.create_memfd(
            f"ab16-model-{hashlib.sha256(str(path).encode()).hexdigest()[:16]}"
        )
        try:
            stale = b"AB16_O_TRUNC_SENTINEL"
            if os.pwrite(descriptor, stale, 0) != len(stale):
                raise RunnerError("model memfd sentinel write failed")
            original_limits = resource.getrlimit(resource.RLIMIT_FSIZE)
            _soft, hard = original_limits
            if hard != resource.RLIM_INFINITY and maximum_bytes > hard:
                raise RunnerError("model maximum exceeds retained RLIMIT_FSIZE hard limit")
            resource.setrlimit(resource.RLIMIT_FSIZE, (maximum_bytes, hard))
            exporter = getattr(model, "export_to_file", None)
            try:
                if (
                    not callable(exporter)
                    or exporter(f"/proc/self/fd/{descriptor}") is not True
                ):
                    raise RunnerError("official O_TRUNC model export failed")
            except BaseException as primary:
                try:
                    resource.setrlimit(
                        resource.RLIMIT_FSIZE,
                        original_limits,
                    )
                except BaseException as restore_error:
                    primary.add_note(
                        "RLIMIT_FSIZE restore also failed: "
                        f"{restore_error!r}"
                    )
                raise
            try:
                resource.setrlimit(
                    resource.RLIMIT_FSIZE,
                    original_limits,
                )
            except BaseException as exc:
                raise RunnerError(
                    "RLIMIT_FSIZE could not be restored before publication"
                ) from exc
            metadata = os.fstat(descriptor)
            if metadata.st_size <= 0 or metadata.st_size > maximum_bytes:
                raise RunnerError("model export exceeds its fixed allocation")
            if os.pread(descriptor, len(stale), 0).startswith(stale):
                raise RunnerError("official model export did not O_TRUNC the memfd")
            digest = self._sha256_descriptor(descriptor, metadata.st_size)
            if self._helper.has_writable_mapping(descriptor):
                raise RunnerError("model memfd has a writable mapping")
            installed = self._helper.install_final_seals(descriptor)
            if (
                installed != self._helper.final_seal_mask
                or self._helper.get_seals(descriptor) != self._helper.final_seal_mask
            ):
                raise RunnerError("model memfd final seal mask differs")
            return self._publish_descriptor(
                descriptor,
                path=path,
                size_bytes=metadata.st_size,
                digest=digest,
                maximum_bytes=maximum_bytes,
                artifact_class="model",
                label=label,
            )
        finally:
            os.close(descriptor)


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


def _replay_repository_head(manifest: Mapping[str, Any]) -> Path:
    """Recheck the manifest-selected repository and package-pinned git tool."""

    raw_root = manifest["repository_root"]
    if type(raw_root) is not str or not Path(raw_root).is_absolute():
        raise RunnerError("manifest repository root is invalid")
    repository_root = Path(raw_root)
    descriptor = _open_directory_chain(repository_root)
    os.close(descriptor)
    git_snapshot = replay_identity_with_mode(
        manifest["repository_git_tool_identity"],
        "manifest repository git tool",
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
        or observed != manifest["repository_head"]
    ):
        raise RunnerError("repository HEAD differs from the manifest")
    return repository_root


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _validate_execution_source(
    value: object,
    *,
    pre_run: Mapping[str, Any],
    manifest: Mapping[str, Any],
    runner_package_snapshot: Snapshot,
) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "environment",
            "execution_working_directory",
            "import_mode",
            "initial_working_directory",
            "live_source_provenance_root",
            "loader_argv",
            "loader_role",
            "module_origin_policy",
            "module_origin_receipt_path",
            "package_id",
            "runner_module",
            "runner_package_tool_identity",
            "runner_snapshot_member_identity",
            "runner_snapshot_relative_path",
            "schema_version",
            "sealed_snapshot_execution_root",
            "selected_byte_launch",
            "snapshot_manifest_identity",
            "snapshot_materialization_receipt_identity",
        },
        "sealed execution source",
    )
    if (
        record["schema_version"] != SEALED_EXECUTION_SOURCE_SCHEMA
        or record["loader_role"] != FORMAL_LOADER_ROLE
        or record["runner_module"] != FORMAL_RUNNER_MODULE
        or record["import_mode"] != "ordinary_pathfinder"
        or record["module_origin_policy"] != "sealed-snapshot-only-v1"
        or record["package_id"] != manifest["authority_chain"]["package"]["package_id"]
    ):
        raise RunnerError("sealed execution source semantics drifted")
    live_root = Path(str(record["live_source_provenance_root"]))
    execution_root = Path(str(record["sealed_snapshot_execution_root"]))
    execution_cwd = Path(str(record["execution_working_directory"]))
    if (
        not live_root.is_absolute()
        or not execution_root.is_absolute()
        or not execution_cwd.is_absolute()
        or live_root != Path(manifest["repository_root"])
        or live_root == execution_root
        or execution_cwd != execution_root
    ):
        raise RunnerError("sealed execution source root join failed")
    directory_fd = _open_directory_chain(execution_root)
    os.close(directory_fd)

    manifest_identity = _exact_identity(
        record["snapshot_manifest_identity"],
        "snapshot manifest identity",
    )
    receipt_identity = _exact_identity(
        record["snapshot_materialization_receipt_identity"],
        "snapshot materialization receipt identity",
    )
    manifest_snapshot = replay_identity(manifest_identity, "snapshot manifest")
    receipt_snapshot = replay_identity(receipt_identity, "snapshot materialization receipt")
    snapshot_manifest = _strict_loads(manifest_snapshot.data, "snapshot manifest")
    snapshot_receipt = _strict_loads(receipt_snapshot.data, "snapshot materialization receipt")
    snapshot_manifest = _exact_keys(
        snapshot_manifest,
        {
            "archive_descriptor",
            "authority_scope",
            "import_mode",
            "member_count",
            "members",
            "ordered_member_digest",
            "repository_head",
            "repository_tree",
            "schema_version",
            "total_bytes",
        },
        "snapshot manifest",
    )
    snapshot_receipt = _exact_keys(
        snapshot_receipt,
        {
            "authority_scope",
            "candidate_identity",
            "created_at_utc",
            "import_mode",
            "member_count",
            "ordered_member_digest",
            "package_id",
            "repository_head",
            "repository_tree",
            "schema_version",
            "snapshot_archive_identity",
            "snapshot_manifest_identity",
            "snapshot_root",
            "status",
            "total_bytes",
        },
        "snapshot materialization receipt",
    )
    members = snapshot_manifest["members"]
    if type(members) is not list or any(type(item) is not dict for item in members):
        raise RunnerError("snapshot member list is malformed")
    if (
        snapshot_manifest["schema_version"] != SNAPSHOT_MANIFEST_SCHEMA
        or snapshot_manifest["authority_scope"] != "AB16_RESEARCH_ONLY"
        or snapshot_manifest["import_mode"] != "ordinary_pathfinder"
        or snapshot_manifest["repository_head"] != manifest["repository_head"]
        or snapshot_manifest["member_count"] != len(members)
        or snapshot_manifest["ordered_member_digest"]
        != hashlib.sha256(canonical_json(members)).hexdigest()
        or snapshot_receipt["schema_version"] != SNAPSHOT_MATERIALIZATION_SCHEMA
        or snapshot_receipt["status"] != "PASS"
        or snapshot_receipt["package_id"] != record["package_id"]
        or snapshot_receipt["snapshot_manifest_identity"] != dict(manifest_identity)
        or Path(snapshot_receipt["snapshot_root"]) != execution_root
        or snapshot_receipt["repository_head"] != snapshot_manifest["repository_head"]
        or snapshot_receipt["repository_tree"] != snapshot_manifest["repository_tree"]
        or snapshot_receipt["member_count"] != snapshot_manifest["member_count"]
        or snapshot_receipt["ordered_member_digest"] != snapshot_manifest["ordered_member_digest"]
        or snapshot_receipt["total_bytes"] != snapshot_manifest["total_bytes"]
    ):
        raise RunnerError("snapshot materialization replay failed")

    relative_text = record["runner_snapshot_relative_path"]
    if type(relative_text) is not str:
        raise RunnerError("runner snapshot relative path is invalid")
    relative = Path(relative_text)
    matching = [member for member in members if member.get("path") == relative_text]
    if relative.is_absolute() or relative.as_posix() != relative_text or ".." in relative.parts or len(matching) != 1:
        raise RunnerError("runner snapshot relative path escaped")
    runner_identity = _exact_identity_with_mode(
        record["runner_snapshot_member_identity"],
        "runner snapshot member identity",
    )
    runner_snapshot = replay_identity_with_mode(
        runner_identity,
        "runner snapshot member",
    )
    member = matching[0]
    if (
        Path(runner_identity["path"]) != execution_root / relative
        or runner_identity["sha256"] != member.get("raw_sha256")
        or runner_identity["size_bytes"] != member.get("size_bytes")
        or runner_identity["mode"] != member.get("materialized_mode")
    ):
        raise RunnerError("runner snapshot member join failed")
    package_identity = _exact_identity_with_mode(
        record["runner_package_tool_identity"],
        "runner package tool identity",
    )
    if (
        {key: package_identity[key] for key in runner_package_snapshot.identity}
        != runner_package_snapshot.identity
        or package_identity["sha256"] != runner_snapshot.identity["sha256"]
        or package_identity["size_bytes"] != runner_snapshot.identity["size_bytes"]
    ):
        raise RunnerError("runner package/snapshot byte join failed")
    prospective = (
        manifest.get("schema_version")
        == PROSPECTIVE_FORMAL_MANIFEST_SCHEMA
    )
    if prospective:
        expected_schema = SELECTED_BYTE_LAUNCH_SCHEMA_V2
        expected_strategy = SELECTED_BYTE_EXECUTION_STRATEGY_V2
        expected_fd_map = SELECTED_BYTE_FD_MAP_V2
        expected_names = SELECTED_BYTE_OPEN_FILE_NAMES_V2
        identity_roles = (
            "authority",
            "loader",
            "native_helper",
            "native_helper_wrapper",
            "python",
        )
    else:
        expected_schema = SELECTED_BYTE_LAUNCH_SCHEMA_V1
        expected_strategy = SELECTED_BYTE_EXECUTION_STRATEGY_V1
        expected_fd_map = SELECTED_BYTE_FD_MAP_V1
        expected_names = SELECTED_BYTE_OPEN_FILE_NAMES_V1
        identity_roles = ("authority", "loader", "python")
    selected = _exact_keys(
        record["selected_byte_launch"],
        {
            "execution_strategy",
            "fd_map",
            "literal_identity",
            "open_file_names",
            "schema_version",
            "transport",
            *(f"{role}_identity" for role in identity_roles),
        },
        "selected-byte launch",
    )
    literal_identity = _exact_keys(
        selected["literal_identity"],
        {"sha256", "size_bytes"},
        "selected-byte literal identity",
    )
    if (
        selected["schema_version"] != expected_schema
        or selected["execution_strategy"] != expected_strategy
        or selected["transport"] != "systemd-openfile-v1"
        or selected["open_file_names"] != expected_names
        or selected["fd_map"] != expected_fd_map
        or type(literal_identity["sha256"]) is not str
        or SHA256_RE.fullmatch(literal_identity["sha256"]) is None
        or type(literal_identity["size_bytes"]) is not int
        or literal_identity["size_bytes"] <= 0
    ):
        raise RunnerError("selected-byte launch semantics drifted")
    for role in identity_roles:
        replay_identity_with_mode(
            _exact_identity_with_mode(
                selected[f"{role}_identity"],
                f"selected-byte {role} identity",
            ),
            f"selected-byte {role}",
        )
    origin_path = Path(str(record["module_origin_receipt_path"]))
    if origin_path != Path(pre_run["attempt_dir"]) / "module-origin-receipt.json":
        raise RunnerError("module-origin receipt path escaped attempt")
    return record


def _assert_initial_import_boundary(execution_source: Mapping[str, Any]) -> None:
    execution_root = Path(str(execution_source["sealed_snapshot_execution_root"])).resolve()
    live_root = Path(str(execution_source["live_source_provenance_root"])).resolve()
    execution_cwd = Path(str(execution_source["execution_working_directory"])).resolve()
    runner_path = Path(str(execution_source["runner_snapshot_member_identity"]["path"])).resolve()
    if Path.cwd().resolve() != execution_cwd:
        raise RunnerError("formal runner cwd is not the sealed execution root")
    if Path(__file__).resolve() != runner_path:
        raise RunnerError("formal runner was not imported from its sealed snapshot member")
    if any(name == "src" or name.startswith("src.") for name in sys.modules):
        raise RunnerError("ambient src module was preloaded before formal construction")
    roots: list[Path] = []
    for raw in sys.path:
        if not raw:
            raise RunnerError("implicit cwd entry is forbidden in isolated sys.path")
        path = Path(raw).resolve()
        roots.append(path)
        if path != execution_root and (path == live_root or _within(path, live_root)):
            raise RunnerError("live checkout path leaked into isolated sys.path")
        if path != execution_root and ((path / ".git").exists() or (path / "PROJECT_LOCK.md").exists()):
            raise RunnerError("checkout-shaped ambient path leaked into isolated sys.path")
    if roots.count(execution_root) != 1:
        raise RunnerError("sealed execution root must be the unique project import root")


def _audit_src_module_origins(execution_source: Mapping[str, Any]) -> list[dict[str, object]]:
    execution_root = Path(str(execution_source["sealed_snapshot_execution_root"])).resolve()
    observations: list[dict[str, object]] = []
    for name, module in sorted(sys.modules.items()):
        if name != "src" and not name.startswith("src."):
            continue
        raw_file = getattr(module, "__file__", None)
        raw_path = getattr(module, "__path__", None)
        if raw_file is not None:
            path = Path(str(raw_file)).resolve()
            if not _within(path, execution_root):
                raise RunnerError(f"module {name} originated outside the sealed snapshot")
            observations.append({"kind": "file", "module": name, "path": str(path)})
        elif raw_path is None:
            raise RunnerError(f"module {name} lacks a sealed file or package path")
        if raw_path is not None:
            paths = [Path(str(item)).resolve() for item in raw_path]
            if not paths or any(not _within(path, execution_root) for path in paths):
                raise RunnerError(f"package {name} path escaped the sealed snapshot")
            observations.append(
                {
                    "kind": "package",
                    "module": name,
                    "paths": [str(path) for path in paths],
                }
            )
    if not observations:
        raise RunnerError("formal construction imported no sealed src modules")
    return observations


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


def _execute_pinned_module_as(snapshot: Snapshot, module_name: str) -> ModuleType:
    """Execute one exact snapshot under a required import name."""

    if module_name in sys.modules:
        raise RunnerError(f"ambient module alias is forbidden: {module_name}")
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


def _publish_cut_free_incumbent_replay(
    *,
    attempt_dir: Path,
    incumbent_identity: Mapping[str, object],
    incumbent_value: Mapping[str, object],
    inputs: PinnedCutFreeReplayInputs,
    budget_backend: ArmBudgetBackend,
) -> dict[str, object]:
    """Run the package-pinned cut-free tool and publish its per-arm receipt."""

    admission = inputs.admission
    rebuilt = admission.get("rebuilt_model")
    if not isinstance(rebuilt, Mapping):
        raise RunnerError("baseline admission lacks rebuilt model authority")
    model_identity = _exact_identity(
        rebuilt.get("identity"),
        "baseline rebuilt model identity",
    )
    metadata = rebuilt.get("metadata")
    if not isinstance(metadata, Mapping):
        raise RunnerError("baseline admission lacks rebuilt metadata authority")
    metadata_identity = _exact_identity(
        metadata.get("metadata_identity"),
        "baseline rebuilt metadata identity",
    )
    model_path = Path(str(model_identity["path"]))
    metadata_path = Path(str(metadata_identity["path"]))
    campaign_provenance_path = model_path.parent / "campaign-provenance.json"
    if metadata_path.parent != model_path.parent:
        raise RunnerError("baseline replay model/metadata directory join failed")
    output = attempt_dir / "replays" / "cut-free-incumbent.json"
    if Path(str(incumbent_identity["path"])) not in {
        attempt_dir / "raw-incumbent.json",
        Path(str(admission["fixed_assignment_replay"]["incumbent_identity"]["path"])),
    }:
        raise RunnerError("cut-free replay incumbent path is not an admitted subject")

    baseline_alias = _execute_pinned_module_as(
        inputs.admission_tool,
        "baseline_admission_v1",
    )
    cut_free_module_name: str | None = None
    try:
        cut_free_module = _load_pinned_module(
            inputs.cut_free_tool,
            "cut_free_incumbent_replay",
        )
        cut_free_module_name = cut_free_module.__name__
        exit_code = cut_free_module.main(
            [
                "--campaign-provenance",
                str(campaign_provenance_path),
                "--model",
                str(model_path),
                "--metadata",
                str(metadata_path),
                "--incumbent",
                str(incumbent_identity["path"]),
                "--output",
                str(output),
            ],
            budget_backend=budget_backend,
            expected_incumbent_sha256=semantic_digest(dict(incumbent_value)),
            emit_summary=False,
        )
    except Exception as exc:
        raise RunnerError("package-pinned per-arm cut-free replay failed closed") from exc
    finally:
        if sys.modules.get("baseline_admission_v1") is baseline_alias:
            sys.modules.pop("baseline_admission_v1", None)
        if cut_free_module_name is not None:
            sys.modules.pop(cut_free_module_name, None)
    if exit_code != 0:
        raise RunnerError("package-pinned per-arm cut-free replay returned nonzero")
    receipt = snapshot_regular(
        output,
        label="per-arm cut-free replay receipt",
    )
    value = _strict_loads(
        receipt.data,
        "per-arm cut-free replay receipt",
    )
    if (
        not isinstance(value, Mapping)
        or value.get("status") != "PASS"
        or value.get("verdict") != "INCUMBENT_FIXED_ASSIGNMENT_REPLAY_PASS"
        or value.get("incumbent_identity") != dict(incumbent_identity)
        or value.get("incumbent_sha256") != semantic_digest(dict(incumbent_value))
        or value.get("replay_tool_identity") != inputs.cut_free_tool.identity
    ):
        raise RunnerError("per-arm cut-free replay receipt self-replay failed")
    return receipt.identity


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


def _prepare_selected_attempt(
    path: Path,
    *,
    budget_backend: ArmBudgetBackend | None = None,
) -> Path:
    """Open the authority-created attempt and exclusively add runner dirs."""

    absolute = Path(os.path.abspath(path))
    descriptor = _open_directory_chain(absolute)
    required = {"pre-run-authority.json", "selection.json"}
    legacy_owned = {"checkpoint", "ledger", "runtime", "tmp"}
    owned = legacy_owned if budget_backend is None else legacy_owned | {"replays"}
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISDIR(before.st_mode):
            raise RunnerError("organic arm attempt is not a directory")
        observed_members = set(os.listdir(descriptor))
        if budget_backend is None:
            if observed_members != required:
                raise RunnerError("organic arm attempt prelaunch contents drifted")
            for name in sorted(owned):
                try:
                    os.mkdir(name, 0o700, dir_fd=descriptor)
                except FileExistsError as exc:
                    raise RunnerError(f"organic arm {name}: no-overwrite collision") from exc
                except OSError as exc:
                    raise RunnerError(f"organic arm {name}: exclusive directory creation failed") from exc
            os.fsync(descriptor)
        else:
            # The broker/package chain must create every directory before
            # dropping the worker into read-only Landlock confinement.
            if observed_members != required | owned:
                raise RunnerError("budgeted organic arm preregistered directories drifted")
            for suffix, expected_mode in BUDGET_ARM_DIRECTORY_SUFFIX_MODES:
                child = _open_directory_chain(absolute / suffix)
                try:
                    metadata = os.fstat(child)
                finally:
                    os.close(child)
                if (
                    not stat.S_ISDIR(metadata.st_mode)
                    or stat.S_IMODE(metadata.st_mode) != expected_mode
                ):
                    raise RunnerError(
                        f"budgeted organic arm {suffix} mode/identity drifted"
                    )
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


def _write_exclusive(
    path: Path,
    raw: bytes,
    *,
    label: str,
    budget_backend: ArmBudgetBackend | None = None,
    artifact_class: str = "normal",
) -> dict[str, object]:
    absolute = Path(os.path.abspath(path))
    if budget_backend is not None:
        maximum = _budget_maximum(
            budget_backend,
            label,
            artifact_class=artifact_class,
        )
        if len(raw) > maximum:
            raise RunnerError(f"{label}: payload exceeds its predeclared budget maximum")
        try:
            record = dict(
                budget_backend.publish_bytes(
                    absolute,
                    raw,
                    maximum_bytes=maximum,
                    artifact_class=artifact_class,
                    label=label,
                )
            )
        except RunnerError:
            raise
        except Exception as exc:
            raise RunnerError(f"{label}: broker publication failed closed") from exc
        if (
            not {"path", "sha256", "size_bytes"} <= set(record)
            or record.get("path") != str(absolute)
            or record.get("sha256") != hashlib.sha256(raw).hexdigest()
            or record.get("size_bytes") != len(raw)
        ):
            raise RunnerError(f"{label}: broker receipt identity differs")
        return record
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


def _authority_chain(value: object) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "campaign_root_identity",
            "continuation_identity",
            "manager_epoch_authority_identity",
            "package",
        },
        "manifest authority chain",
    )
    for field in (
        "campaign_root_identity",
        "continuation_identity",
        "manager_epoch_authority_identity",
    ):
        _exact_identity(record[field], f"manifest authority chain {field}")
    package = _exact_keys(
        record["package"],
        {"manifest_identity", "package_id", "seal_identity"},
        "manifest authority package",
    )
    _exact_identity(package["manifest_identity"], "package manifest identity")
    seal = _exact_identity(package["seal_identity"], "package seal identity")
    if (
        type(package["package_id"]) is not str
        or SHA256_RE.fullmatch(package["package_id"]) is None
        or package["package_id"] != seal["sha256"]
    ):
        raise RunnerError("manifest package identity is invalid")
    return record


def validate_manifest(value: object) -> Mapping[str, Any]:
    """Validate the immutable experiment manifest used by every arm."""

    legacy_fields = {
        "arithmetic_verifier",
        "arm_binding_identities",
        "arm_sequence",
        "attempt_dirs",
        "authority_chain",
        "authorizations",
        "baseline_admission_identity",
        "baseline_incumbent_identity",
        "campaign_id",
        "classification_contract_identity",
        "common_prestate_identity",
        "configuration_families",
        "experiment_contract",
        "forbidden_families",
        "per_arm_tool_identities",
        "purpose",
        "repository_git_tool_identity",
        "repository_head",
        "repository_root",
        "run_nonce",
        "runner_tool_identity",
        "runtime_parameters",
        "schema_version",
        "seed",
        "unit_names",
        "workers",
    }
    if type(value) is not dict:
        raise RunnerError("organic manifest: exact key set drifted")
    schema_version = value.get("schema_version")
    if schema_version == MANIFEST_SCHEMA:
        expected_fields = legacy_fields
        sealed_execution = False
    elif schema_version == FORMAL_MANIFEST_SCHEMA:
        expected_fields = legacy_fields | {
            "live_source_provenance_root",
            "sealed_snapshot_execution_root",
            "snapshot_manifest_identity",
            "snapshot_materialization_receipt_identity",
        }
        sealed_execution = True
    elif schema_version == PROSPECTIVE_FORMAL_MANIFEST_SCHEMA:
        expected_fields = legacy_fields | {
            "formal_budget_runtime",
            "live_source_provenance_root",
            "sealed_snapshot_execution_root",
            "snapshot_manifest_identity",
            "snapshot_materialization_receipt_identity",
        }
        sealed_execution = True
    else:
        raise RunnerError("organic manifest schema drifted")
    record = _exact_keys(
        value,
        expected_fields,
        "organic manifest",
    )
    if (
        record["purpose"] != MANIFEST_PURPOSE
        or type(record["campaign_id"]) is not str
        or SHA256_RE.fullmatch(record["campaign_id"]) is None
        or type(record["repository_head"]) is not str
        or GIT_SHA_RE.fullmatch(record["repository_head"]) is None
        or type(record["repository_root"]) is not str
        or not Path(record["repository_root"]).is_absolute()
        or type(record["run_nonce"]) is not str
        or SAFE_TOKEN_RE.fullmatch(record["run_nonce"]) is None
        or record["workers"] != 1
        or type(record["workers"]) is not int
        or type(record["seed"]) is not int
        or record["arm_sequence"] != list(ARM_SEQUENCE)
        or record["forbidden_families"] != list(FORBIDDEN_FAMILIES)
    ):
        raise RunnerError("organic manifest scalar semantics drifted")
    if sealed_execution and (
        record["live_source_provenance_root"] != record["repository_root"]
        or type(record["sealed_snapshot_execution_root"]) is not str
        or not Path(record["sealed_snapshot_execution_root"]).is_absolute()
        or record["sealed_snapshot_execution_root"]
        == record["live_source_provenance_root"]
    ):
        raise RunnerError("organic manifest sealed-source semantics drifted")
    if (
        schema_version == PROSPECTIVE_FORMAL_MANIFEST_SCHEMA
        and type(record["formal_budget_runtime"]) is not dict
    ):
        raise RunnerError("organic manifest formal budget runtime is not an object")
    families = _exact_keys(
        record["configuration_families"],
        set(CONFIGURATION_FAMILIES),
        "manifest configuration families",
    )
    for configuration, expected in CONFIGURATION_FAMILIES.items():
        if families[configuration] != list(expected):
            raise RunnerError(f"manifest family set drifted for {configuration}")
    _authority_chain(record["authority_chain"])
    if record["experiment_contract"] != EXPERIMENT_CONTRACT:
        raise RunnerError("manifest experiment contract drifted")
    _identity_map(
        record["per_arm_tool_identities"],
        set(PER_ARM_TOOL_ROLES),
        "manifest per-arm tools",
    )
    _identity_map(
        record["arm_binding_identities"],
        set(ARM_SEQUENCE),
        "manifest arm bindings",
    )
    identity_fields = [
        "baseline_admission_identity",
        "baseline_incumbent_identity",
        "classification_contract_identity",
        "common_prestate_identity",
        "runner_tool_identity",
    ]
    if sealed_execution:
        identity_fields.extend(
            (
                "snapshot_manifest_identity",
                "snapshot_materialization_receipt_identity",
            )
        )
    for field in identity_fields:
        _exact_identity(record[field], f"manifest {field}")
    _exact_identity_with_mode(
        record["repository_git_tool_identity"],
        "manifest repository_git_tool_identity",
    )
    attempt_dirs = _exact_keys(
        record["attempt_dirs"],
        set(ARM_SEQUENCE),
        "manifest attempt directories",
    )
    unit_names = _exact_keys(
        record["unit_names"],
        set(ARM_SEQUENCE),
        "manifest unit names",
    )
    if len(set(attempt_dirs.values())) != len(ARM_SEQUENCE):
        raise RunnerError("manifest attempt directories are not unique")
    if len(set(unit_names.values())) != len(ARM_SEQUENCE):
        raise RunnerError("manifest unit names are not unique")
    for slot in ARM_SEQUENCE:
        if (
            type(attempt_dirs[slot]) is not str
            or not Path(attempt_dirs[slot]).is_absolute()
            or type(unit_names[slot]) is not str
            or not unit_names[slot]
        ):
            raise RunnerError("manifest arm path/name preregistration is invalid")
    arithmetic = _exact_keys(
        record["arithmetic_verifier"],
        {"purpose", "tool_identity"},
        "manifest arithmetic verifier",
    )
    if arithmetic["purpose"] != FORMAL_ARITHMETIC_PURPOSE:
        raise RunnerError("formal arithmetic-verifier purpose drifted or reused a drill purpose")
    _exact_identity(arithmetic["tool_identity"], "formal arithmetic-verifier tool")
    authorizations = _exact_keys(
        record["authorizations"],
        {
            "global_claim_authorized",
            "mathematical_claim_authorized",
            "organic_arm_launch_authorized",
            "production_certified_authorized",
        },
        "manifest authorizations",
    )
    if authorizations != {
        "global_claim_authorized": False,
        "mathematical_claim_authorized": False,
        "organic_arm_launch_authorized": True,
        "production_certified_authorized": False,
    }:
        raise RunnerError("manifest authorization boundary drifted")
    _runtime_parameters(record["runtime_parameters"])
    return record


def validate_selection(
    value: object,
    *,
    manifest: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Validate one per-arm formal selection against the manifest."""

    legacy_fields = {
        "arm",
        "arm_binding_identity",
        "attempt_dir",
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
    }
    manifest_schema = manifest.get("schema_version")
    if manifest_schema == MANIFEST_SCHEMA:
        expected_fields = legacy_fields
        sealed_execution = False
    elif manifest_schema == FORMAL_MANIFEST_SCHEMA:
        expected_fields = legacy_fields | {
            "live_source_provenance_root",
            "sealed_snapshot_execution_root",
            "snapshot_manifest_identity",
            "snapshot_materialization_receipt_identity",
        }
        sealed_execution = True
    elif manifest_schema == PROSPECTIVE_FORMAL_MANIFEST_SCHEMA:
        expected_fields = legacy_fields | {
            "budget_handoff",
            "live_source_provenance_root",
            "sealed_snapshot_execution_root",
            "snapshot_manifest_identity",
            "snapshot_materialization_receipt_identity",
        }
        sealed_execution = True
    else:
        raise RunnerError("selection parent manifest schema drifted")
    record = _exact_keys(
        value,
        expected_fields,
        "organic arm selection",
    )
    configuration = record["configuration"]
    order = record["order"]
    arm = record["arm"]
    if (
        record["schema_version"]
        != (
            FORMAL_SELECTION_SCHEMA
            if manifest_schema == PROSPECTIVE_FORMAL_MANIFEST_SCHEMA
            else SELECTION_SCHEMA
        )
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
    joined_fields = [
        "campaign_id",
        "repository_git_tool_identity",
        "repository_head",
        "repository_root",
        "run_nonce",
        "workers",
        "seed",
    ]
    if sealed_execution:
        joined_fields.extend(
            (
                "live_source_provenance_root",
                "sealed_snapshot_execution_root",
                "snapshot_manifest_identity",
                "snapshot_materialization_receipt_identity",
            )
        )
    for field in joined_fields:
        if record[field] != manifest[field]:
            raise RunnerError(f"selection {field} differs from manifest")
    if record["authority_chain"] != manifest["authority_chain"]:
        raise RunnerError("selection authority chain differs from manifest")
    if (
        manifest_schema == PROSPECTIVE_FORMAL_MANIFEST_SCHEMA
        and type(record["budget_handoff"]) is not dict
    ):
        raise RunnerError("selection budget handoff is not an object")
    _authority_chain(record["authority_chain"])
    slot = record["slot"]
    if record["attempt_dir"] != manifest["attempt_dirs"][slot] or record["unit_name"] != manifest["unit_names"][slot]:
        raise RunnerError("selection path/name escaped manifest preregistration")
    if not Path(record["attempt_dir"]).is_absolute():
        raise RunnerError("selection attempt directory is not absolute")
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
    for field, manifest_field in (
        ("arm_binding_identity", "arm_binding_identities"),
        ("common_prestate_identity", "common_prestate_identity"),
        ("baseline_admission_identity", "baseline_admission_identity"),
    ):
        selected_identity = _exact_identity(record[field], f"selection {field}")
        expected_identity = (
            manifest[manifest_field][slot] if manifest_field == "arm_binding_identities" else manifest[manifest_field]
        )
        if dict(selected_identity) != dict(expected_identity):
            raise RunnerError(f"selection {field} differs from manifest")
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
    manifest: Mapping[str, Any],
    selection: Mapping[str, Any],
) -> str:
    record = _exact_keys(
        value,
        {
            "admission_tool_identity",
            "authorizations",
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
    incumbent_identity = _exact_identity(
        replay.get("incumbent_identity"),
        "baseline replay incumbent identity",
    )
    if dict(incumbent_identity) != dict(manifest["baseline_incumbent_identity"]):
        raise RunnerError("baseline incumbent identity differs from manifest")
    if replay.get("status") != "PASS" or replay.get("solver_status") != "OPTIMAL":
        raise RunnerError("baseline fixed-assignment replay status drifted")
    return digest


class HashChainJournal:
    """Local JSONL journal or explicit immutable broker segment sequence."""

    def __init__(
        self,
        path: Path,
        *,
        genesis: Mapping[str, object],
        budget_backend: ArmBudgetBackend | None = None,
        budget_channel: str | None = None,
        budget_segment_max_bytes: int | None = None,
        budget_arm_slot: str | None = None,
    ) -> None:
        self.path = Path(os.path.abspath(path))
        self._budget_backend = budget_backend
        self._budget_channel = budget_channel
        self._budget_segment_max_bytes = budget_segment_max_bytes
        self._budget_arm_slot = budget_arm_slot
        self._segment_records: list[dict[str, object]] = []
        self._events: list[dict[str, object]] = []
        self._raw_segments: list[bytes] = []
        if budget_backend is None:
            if any(
                value is not None
                for value in (
                    budget_channel,
                    budget_segment_max_bytes,
                    budget_arm_slot,
                )
            ):
                raise RunnerError("journal budget options require budget_backend")
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
        else:
            if (
                not isinstance(budget_channel, str)
                or SAFE_TOKEN_RE.fullmatch(budget_channel) is None
                or isinstance(budget_segment_max_bytes, bool)
                or not isinstance(budget_segment_max_bytes, int)
                or budget_segment_max_bytes <= 0
            ):
                raise RunnerError("journal immutable segment allocation is invalid")
            self._fd = -1
        self._seq = 0
        self._tail = "0" * 64
        self._sealed = False
        self._counts: dict[str, int] = {}
        self.append("GENESIS", dict(genesis))

    @property
    def counts(self) -> dict[str, int]:
        return dict(sorted(self._counts.items()))

    @property
    def recorded_events(self) -> tuple[Mapping[str, object], ...]:
        return tuple(dict(event) for event in self._events)

    @property
    def immutable_segment_records(self) -> tuple[Mapping[str, object], ...]:
        return tuple(dict(record) for record in self._segment_records)

    def segment_bundle(self) -> dict[str, object]:
        if self._budget_backend is None:
            raise RunnerError("local journal does not have an immutable segment bundle")
        raw = b"".join(self._raw_segments)
        return {
            "schema_version": BUDGET_SEGMENT_BUNDLE_SCHEMA,
            "channel": self._budget_channel,
            "event_count": len(self._events),
            "segment_identities": [
                dict(record) for record in self._segment_records
            ],
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }

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
        segment = raw + b"\n"
        if self._budget_backend is None:
            view = memoryview(segment)
            while view:
                written = os.write(self._fd, view)
                if written <= 0:
                    raise RunnerError("compile/attach journal write made no progress")
                view = view[written:]
            os.fsync(self._fd)
        else:
            assert self._budget_channel is not None
            assert self._budget_segment_max_bytes is not None
            if len(segment) > self._budget_segment_max_bytes:
                raise RunnerError(
                    "compile/attach journal event exceeds its fixed allocation"
                )
            try:
                receipt = dict(
                    self._budget_backend.append_segment(
                        self._budget_channel,
                        self._seq,
                        segment,
                        maximum_bytes=self._budget_segment_max_bytes,
                        artifact_class="ledger",
                        arm_slot=self._budget_arm_slot,
                    )
                )
            except Exception as exc:
                raise RunnerError(
                    "compile/attach journal broker publication failed closed"
                ) from exc
            if (
                not {"path", "sha256", "size_bytes"} <= set(receipt)
                or receipt.get("sha256") != hashlib.sha256(segment).hexdigest()
                or receipt.get("size_bytes") != len(segment)
            ):
                raise RunnerError("compile/attach journal broker receipt differs")
            self._segment_records.append(receipt)
            self._raw_segments.append(segment)
            self._events.append(dict(record))
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
        if self._budget_backend is None:
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


def _journal_observation(
    journal: HashChainJournal,
) -> tuple[list[Mapping[str, Any]], dict[str, object]]:
    if journal._budget_backend is None:  # noqa: SLF001 - same-module protocol join
        return _read_journal(journal.path)
    events: list[Mapping[str, Any]] = [
        dict(event) for event in journal.recorded_events
    ]
    if not events or events[-1].get("event") != "JOURNAL_SEAL":
        raise RunnerError("immutable compile/attach journal lacks a terminal seal")
    tail = "0" * 64
    for sequence, event in enumerate(events):
        if (
            event.get("schema_version") != JOURNAL_SCHEMA
            or event.get("seq") != sequence
            or event.get("prev_event_sha256") != tail
        ):
            raise RunnerError("immutable compile/attach journal replay failed")
        tail = hashlib.sha256(_canonical_compact(event)).hexdigest()
    return events, journal.segment_bundle()


def _budgeted_ledger_observation(
    ledger: Any,
) -> tuple[list[Mapping[str, Any]], dict[str, object]]:
    events: list[Mapping[str, Any]] = [
        dict(event) for event in ledger.recorded_events
    ]
    records = [dict(record) for record in ledger.immutable_segment_records]
    if (
        not events
        or events[-1].get("event") != "SEGMENT_SEAL"
        or len(events) != len(records)
    ):
        raise RunnerError("immutable cut ledger lacks one complete segment sequence")
    previous = "0" * 64
    raw_segments: list[bytes] = []
    for sequence, (event, record) in enumerate(zip(events, records, strict=True)):
        raw = _canonical_compact(event) + b"\n"
        if (
            event.get("seq") != sequence
            or event.get("prev_event_hash") != previous
            or record.get("sha256") != hashlib.sha256(raw).hexdigest()
            or record.get("size_bytes") != len(raw)
        ):
            raise RunnerError("immutable cut ledger replay failed")
        previous = hashlib.sha256(raw[:-1]).hexdigest()
        raw_segments.append(raw)
    joined = b"".join(raw_segments)
    return events, {
        "schema_version": BUDGET_SEGMENT_BUNDLE_SCHEMA,
        "channel": "cut-ledger",
        "event_count": len(events),
        "segment_identities": records,
        "sha256": hashlib.sha256(joined).hexdigest(),
        "size_bytes": len(joined),
    }


def _load_authority(
    selection_path: Path,
) -> tuple[
    Mapping[str, Any],
    Mapping[str, Any],
    dict[str, dict[str, object]],
    Mapping[str, Any],
    PinnedCutFreeReplayInputs,
]:
    selection_snapshot = snapshot_regular(
        selection_path,
        label="organic arm selection",
    )
    selection_raw = _strict_loads(selection_snapshot.data, "organic arm selection")
    if not isinstance(selection_raw, Mapping):
        raise RunnerError("organic arm selection is not an object")
    manifest_identity = _exact_identity(
        selection_raw.get("manifest_identity"),
        "selection manifest identity",
    )
    manifest_snapshot = replay_identity(manifest_identity, "organic manifest")
    manifest_raw = _strict_loads(manifest_snapshot.data, "organic manifest")
    manifest = validate_manifest(manifest_raw)
    selection = validate_selection(selection_raw, manifest=manifest)
    _replay_repository_head(manifest)
    if dict(selection["manifest_identity"]) != manifest_snapshot.identity:
        raise RunnerError("selection manifest identity differs from read bytes")

    replayed: dict[str, dict[str, object]] = {
        "selection": selection_snapshot.identity,
        "manifest": manifest_snapshot.identity,
    }
    authority_snapshots: dict[str, Snapshot] = {}
    for role, identity in (
        ("baseline_admission", selection["baseline_admission_identity"]),
        ("baseline_incumbent", manifest["baseline_incumbent_identity"]),
        ("common_prestate", selection["common_prestate_identity"]),
        ("arm_binding", selection["arm_binding_identity"]),
        ("pre_run_authority", selection["pre_run_authority_identity"]),
        (
            "arithmetic_verifier_tool",
            manifest["arithmetic_verifier"]["tool_identity"],
        ),
        (
            "classification_contract_tool",
            manifest["classification_contract_identity"],
        ),
        ("runner_tool", manifest["runner_tool_identity"]),
        (
            "campaign_root",
            manifest["authority_chain"]["campaign_root_identity"],
        ),
        (
            "continuation",
            manifest["authority_chain"]["continuation_identity"],
        ),
        (
            "manager_epoch_authority",
            manifest["authority_chain"]["manager_epoch_authority_identity"],
        ),
        (
            "package_manifest",
            manifest["authority_chain"]["package"]["manifest_identity"],
        ),
        (
            "package_seal",
            manifest["authority_chain"]["package"]["seal_identity"],
        ),
        *((f"per_arm_tool_{role}", identity) for role, identity in sorted(manifest["per_arm_tool_identities"].items())),
    ):
        snapshot = replay_identity(identity, role.replace("_", " "))
        authority_snapshots[role] = snapshot
        replayed[role] = snapshot.identity

    if selection_snapshot.identity["path"] != str(Path(selection["attempt_dir"]) / "selection.json"):
        raise RunnerError("organic arm selection path escaped its attempt directory")

    pre_run_value = _strict_loads(
        authority_snapshots["pre_run_authority"].data,
        "organic arm pre-run authority",
    )
    if not isinstance(pre_run_value, Mapping):
        raise RunnerError("organic arm pre-run authority is not an object")
    try:
        lifecycle_tool = _load_pinned_module(
            authority_snapshots["per_arm_tool_resource_lifecycle"],
            "organic_resource_lifecycle",
        )
        checked_pre_run = lifecycle_tool.validate_pre_run_authority(pre_run_value)
        checked_selection = lifecycle_tool.validate_runner_selection(
            selection,
            pre_run_authority=checked_pre_run,
            pre_run_authority_identity=authority_snapshots["pre_run_authority"].identity,
        )
    except Exception as exc:
        raise RunnerError("package-pinned pre-run authority or selection replay failed") from exc
    if dict(checked_pre_run) != dict(pre_run_value) or dict(checked_selection) != dict(selection):
        raise RunnerError("package-pinned pre-run semantic replay changed its inputs")
    launch = pre_run_value.get("launch")
    if not isinstance(launch, Mapping):
        raise RunnerError("formal pre-run launch is absent")
    execution_source = _validate_execution_source(
        launch.get("execution_source"),
        pre_run=pre_run_value,
        manifest=manifest,
        runner_package_snapshot=authority_snapshots["runner_tool"],
    )

    admission_value = _strict_loads(
        authority_snapshots["baseline_admission"].data,
        "baseline admission",
    )
    expected_digest = _validate_baseline_admission(
        admission_value,
        manifest=manifest,
        selection=selection,
    )
    incumbent = _strict_loads(
        authority_snapshots["baseline_incumbent"].data,
        "baseline incumbent",
    )
    if type(incumbent) is not dict or semantic_digest(incumbent) != expected_digest:
        raise RunnerError("baseline incumbent bytes do not match admitted digest")
    if not isinstance(admission_value, Mapping):
        raise RunnerError("baseline admission is not an object")
    admission_tool = replay_identity(
        admission_value.get("admission_tool_identity"),
        "baseline admission tool",
    )
    replayed["baseline_admission_tool"] = admission_tool.identity
    return (
        manifest,
        selection,
        replayed,
        execution_source,
        PinnedCutFreeReplayInputs(
            admission=dict(admission_value),
            admission_tool=admission_tool,
            cut_free_tool=authority_snapshots["per_arm_tool_cut_free_replay"],
        ),
    )


def _consume_budget_socket_fd(fd: int, *, label: str) -> int:
    """Consume one loader-owned broker FD and return one CLOEXEC duplicate."""

    if isinstance(fd, bool) or not isinstance(fd, int) or fd < 0:
        raise RunnerError(f"{label} is not one descriptor")
    duplicate = -1
    try:
        duplicate = fcntl.fcntl(
            fd,
            fcntl.F_DUPFD_CLOEXEC,
            20,
        )
    except BaseException:
        try:
            os.close(fd)
        except BaseException:
            pass
        raise
    try:
        os.close(fd)
    except BaseException:
        try:
            os.close(duplicate)
        except BaseException:
            pass
        raise
    return duplicate


def formal_arm_worker_budget_backend_from_fd(
    fd: int,
    *,
    native_budget_helper: object,
    campaign_dir: Path | str,
    pre_run_path: Path | str,
    selection_path: Path | str,
    worker_session: Mapping[str, object],
) -> ArmBudgetBackend:
    """Attach the exact pidfd-bound organic worker on fixed FD8."""

    owned_fd = _consume_budget_socket_fd(
        fd,
        label="formal arm worker broker FD",
    )
    if fd != 8:
        os.close(owned_fd)
        raise RunnerError(
            "formal arm worker broker must arrive on fixed FD8"
        )
    client: Any | None = None
    try:
        manifest, selection, _replayed, _source, _inputs = (
            _load_authority(Path(selection_path))
        )
        expected_pre_run = _exact_identity(
            selection["pre_run_authority_identity"],
            "formal arm worker pre-run authority",
        )
        if (
            expected_pre_run["path"]
            != str(Path(os.path.abspath(pre_run_path)))
            or selection["execution_class"] != "FORMAL_AB16"
        ):
            raise RunnerError(
                "formal arm worker pre-run/selection join drifted"
            )
        handoff = _exact_keys(
            selection["budget_handoff"],
            {
                "arm_allocation_id",
                "broker_actor_identity",
                "broker_nonce",
                "broker_socket_path",
                "calibration_tool_content_identities",
                "fixed_directory_layout",
                "fixed_maxima",
                "formal_budget_authority_identity",
                "manager_openfile_arm_grant",
                "native_helper_package_identity",
            },
            "formal arm worker budget handoff",
        )
        manager_grant = _exact_keys(
            handoff["manager_openfile_arm_grant"],
            {"credential", "preregistration"},
            "formal arm manager grant",
        )
        preregistration = _exact_keys(
            manager_grant["preregistration"],
            {
                "allocation_identity",
                "arm_slot",
                "attempt_consumption_identity",
                "credential_sha256",
                "manager_epoch_identity",
                "schema_version",
                "selection_identity",
                "state",
                "unit_name",
            },
            "formal arm manager preregistration",
        )
        session = _exact_keys(
            worker_session,
            {"broker_grant", "credential", "schema_version"},
            "formal arm worker session",
        )
        credential = session["credential"]
        broker_grant = _exact_keys(
            session["broker_grant"],
            {
                "allocation_identity",
                "arm_slot",
                "credential_sha256",
                "expected_peer",
                "role",
                "schema_version",
                "selection_identity",
            },
            "formal arm worker broker grant",
        )
        if (
            session["schema_version"] != FORMAL_WORKER_SESSION_SCHEMA
            or type(credential) is not str
            or SHA256_RE.fullmatch(credential) is None
            or broker_grant["role"] != "arm"
            or broker_grant["arm_slot"] != selection["slot"]
            or broker_grant["arm_slot"] != preregistration["arm_slot"]
            or broker_grant["selection_identity"]
            != preregistration["selection_identity"]
            or broker_grant["allocation_identity"]
            != preregistration["allocation_identity"]
            or broker_grant["credential_sha256"]
            != hashlib.sha256(credential.encode("ascii")).hexdigest()
        ):
            raise RunnerError(
                "formal arm worker session authority drifted"
            )

        from docs.research.noncert_cuts_ab16_20260724 import (
            ab16_budget_broker_v1 as broker_module,
        )
        from docs.research.noncert_cuts_ab16_20260724 import (
            ab16_formal_controller_v1 as formal_controller,
        )

        snapshot_root = Path(
            cast(str, manifest["sealed_snapshot_execution_root"])
        )
        expected_origins = {
            broker_module: (
                "docs/research/noncert_cuts_ab16_20260724/"
                "ab16_budget_broker_v1.py"
            ),
            formal_controller: (
                "docs/research/noncert_cuts_ab16_20260724/"
                "ab16_formal_controller_v1.py"
            ),
        }
        for module, relative in expected_origins.items():
            origin = getattr(module, "__file__", None)
            if (
                type(origin) is not str
                or Path(origin).resolve(strict=False)
                != (snapshot_root / relative).resolve(strict=False)
            ):
                raise RunnerError(
                    "formal arm worker dependency escaped the sealed snapshot"
                )
        formal_selection_identity = _exact_identity(
            preregistration["selection_identity"],
            "formal arm worker formal selection",
        )
        formal_inputs = formal_controller.load_formal_inputs(
            campaign_dir=campaign_dir,
            formal_selection=formal_selection_identity["path"],
        )
        if (
            formal_inputs.selection_identity
            != formal_selection_identity
        ):
            raise RunnerError(
                "formal arm worker formal selection replay drifted"
            )
        formal_runtime = formal_inputs.selection[
            "manager_openfile_grant"
        ]["formal_budget_runtime"]
        if (
            formal_runtime["broker_actor_identity"]
            != handoff["broker_actor_identity"]
            or formal_runtime["broker_nonce"]
            != handoff["broker_nonce"]
            or formal_runtime["broker_endpoint_identity"]["path"]
            != handoff["broker_socket_path"]
        ):
            raise RunnerError(
                "formal arm worker broker runtime join drifted"
            )
        expected_peer = broker_module.process_identity()
        if (
            broker_grant["schema_version"]
            != broker_module.SESSION_GRANT_SCHEMA
            or broker_grant["expected_peer"] != expected_peer
        ):
            raise RunnerError(
                "formal arm worker pidfd-bound peer drifted"
            )
        actor = {
            "schema_version": broker_module.ACTOR_SCHEMA,
            **cast(
                Mapping[str, object],
                handoff["broker_actor_identity"],
            ),
        }
        transferred_fd = owned_fd
        owned_fd = -1
        client = broker_module.attach_registered_arm_session(
            transferred_fd,
            broker_actor=actor,
            broker_nonce=cast(str, handoff["broker_nonce"]),
            credential=credential,
            role="arm",
            arm_slot=cast(str, selection["slot"]),
            selection_identity=cast(
                Mapping[str, object],
                preregistration["selection_identity"],
            ),
            allocation_identity=cast(
                Mapping[str, object],
                preregistration["allocation_identity"],
            ),
            native_helper=cast(Any, native_budget_helper),
        )
        formal_root = Path(
            cast(
                str,
                cast(
                    Mapping[str, object],
                    handoff["fixed_directory_layout"],
                )["formal_root"],
            )
        )
        expected_formal_root, profile, _a, _c, _d = (
            formal_controller._formal_budget_tables(  # noqa: SLF001
                formal_inputs
            )
        )
        calibration, calibration_identity = (
            formal_controller._formal_resource_calibration_bundle(  # noqa: SLF001
                formal_inputs
            )
        )
        if formal_root != expected_formal_root:
            raise RunnerError(
                "formal arm worker formal-root profile join drifted"
            )
        binding = {
            "arm_allocation_id": handoff["arm_allocation_id"],
            "arm_allocation_identity": dict(
                cast(
                    Mapping[str, object],
                    preregistration["allocation_identity"],
                )
            ),
            "arm_slot": selection["slot"],
            "broker_nonce": handoff["broker_nonce"],
            "broker_socket_fd": client.connection.fileno(),
            "filesystem_write_confinement": (
                "landlock-read-only-worker-v1"
            ),
            "formal_budget_authority_identity": dict(
                cast(
                    Mapping[str, object],
                    handoff["formal_budget_authority_identity"],
                )
            ),
            "next_sequence": client.sequence + 1,
        }
        layout = cast(
            Mapping[str, object],
            handoff["fixed_directory_layout"],
        )
        backend = BrokerProcessArmBudgetBackend(
            broker_client=client,
            native_helper=native_budget_helper,
            formal_root=formal_root,
            attempt_root=Path(cast(str, layout["attempt_root"])),
            formal_budget_runtime=cast(
                Mapping[str, object],
                formal_runtime,
            ),
            enforced_budget_profile=profile,
            enforced_budget_profile_identity=cast(
                Mapping[str, object],
                formal_inputs.selection["manager_openfile_grant"][
                    "budget_profile_identity"
                ],
            ),
            resource_calibration_authorization_bundle=calibration,
            resource_calibration_authorization_bundle_identity=(
                calibration_identity
            ),
            expected_calibration_tool_identities=cast(
                Mapping[str, Mapping[str, object]],
                handoff["calibration_tool_content_identities"],
            ),
            authority_binding=binding,
            fixed_maxima=cast(
                Mapping[str, Mapping[str, object]],
                handoff["fixed_maxima"],
            ),
            channel_contracts=cast(
                Mapping[str, Mapping[str, object]],
                layout["channel_contracts"],
            ),
        )
        client = None
        return backend
    except BaseException as exc:
        try:
            if client is not None:
                client.close()
            elif owned_fd >= 0:
                os.close(owned_fd)
        except BaseException as cleanup_error:
            exc.add_note(
                "formal arm worker backend cleanup failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )
        raise


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
def _arm_environment(
    attempt_dir: Path,
    *,
    seed: int,
    budgeted: bool = False,
) -> Any:
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
    if budgeted:
        tmp_metadata = os.stat(
            attempt_dir / "tmp",
            follow_symlinks=False,
        )
        if (
            not stat.S_ISDIR(tmp_metadata.st_mode)
            or stat.S_IMODE(tmp_metadata.st_mode) & 0o222
        ):
            raise RunnerError("budgeted TMPDIR is not a retained read-only directory")
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


def _run_with_hooks(
    selection_path: Path,
    hooks: ArmHooks,
    *,
    enforce_single_process_use: bool,
    budget_backend: ArmBudgetBackend | None = None,
) -> dict[str, object]:
    """Execute one selected arm; tests inject small hooks through this seam."""

    global _PUBLIC_RUN_STARTED
    if enforce_single_process_use:
        if _PUBLIC_RUN_STARTED:
            raise RunnerError("fresh process contract forbids a second arm")
        _PUBLIC_RUN_STARTED = True

    (
        manifest,
        selection,
        authority_identities,
        execution_source,
        cut_free_inputs,
    ) = _load_authority(selection_path)
    if (
        bool(getattr(hooks, "requires_budget_authority", False))
        and budget_backend is None
    ):
        raise RunnerError("production organic arm requires broker-backed budget authority")
    budget_binding = (
        _validate_budget_binding(
            budget_backend,
            expected_arm_slot=str(selection["slot"]),
        )
        if budget_backend is not None
        else None
    )
    result_schema = (
        FORMAL_RESULT_SCHEMA if budget_backend is not None else RESULT_SCHEMA
    )
    if bool(getattr(hooks, "requires_sealed_import_boundary", False)):
        _assert_initial_import_boundary(execution_source)
    attempt_dir = _prepare_selected_attempt(
        Path(selection["attempt_dir"]),
        budget_backend=budget_backend,
    )

    from src.cuts.ledger import CutLedgerWriter, read_segment

    ledger_genesis = {
        "arm": selection["arm"],
        "campaign_id": selection["campaign_id"],
        "enabled_families": list(selection["enabled_families"]),
        "manifest_sha256": authority_identities["manifest"]["sha256"],
        "selection_sha256": authority_identities["selection"]["sha256"],
        "selection_nonce": selection["selection_nonce"],
    }
    journal_genesis = {
        "arm": selection["arm"],
        "campaign_id": selection["campaign_id"],
        "enabled_families": list(selection["enabled_families"]),
        "selection_identity": authority_identities["selection"],
        "slot": selection["slot"],
    }
    if budget_backend is None:
        ledger = CutLedgerWriter(
            attempt_dir / "ledger",
            scope_id=str(selection["slot"]),
            writer_id="organic-arm-v1",
            genesis_context=ledger_genesis,
        )
        journal = HashChainJournal(
            attempt_dir / "compile-attach-journal.jsonl",
            genesis=journal_genesis,
        )
    else:
        from docs.research.noncert_cuts_ab16_20260724.ab16_budgeted_writers_v1 import (
            AB16BudgetedCutLedgerWriter,
        )

        ledger = AB16BudgetedCutLedgerWriter(
            attempt_dir / "ledger",
            scope_id=str(selection["slot"]),
            writer_id="organic-arm-v1",
            genesis_context=ledger_genesis,
            immutable_budget=budget_backend,
            budget_channel=f"arm-{selection['slot']}-cut-ledger",
            budget_segment_max_bytes=_budget_maximum(
                budget_backend,
                "cut ledger segment",
                artifact_class="ledger",
            ),
            budget_arm_slot=str(selection["slot"]),
        )
        journal = HashChainJournal(
            attempt_dir / "compile-attach-journal.jsonl",
            genesis=journal_genesis,
            budget_backend=budget_backend,
            budget_channel=f"arm-{selection['slot']}-compile-journal",
            budget_segment_max_bytes=_budget_maximum(
                budget_backend,
                "compile attach journal segment",
                artifact_class="ledger",
            ),
            budget_arm_slot=str(selection["slot"]),
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
        with _arm_environment(
            attempt_dir,
            seed=int(selection["seed"]),
            budgeted=budget_backend is not None,
        ):
            context = ArmContext(
                attempt_dir=attempt_dir,
                budget_backend=budget_backend,
                enabled_families=tuple(selection["enabled_families"]),
                execution_source=execution_source,
                ledger=ledger,
                live_source_provenance_root=Path(selection["repository_root"]),
                manifest=manifest,
                repository_root=Path(execution_source["sealed_snapshot_execution_root"]),
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
            "schema_version": result_schema,
            "selection_identity": authority_identities["selection"],
            "status": "CREDIBILITY_INCOMPLETE",
        }
        _write_exclusive(
            attempt_dir / "failure.json",
            canonical_json(failure_record),
            label="organic arm failure record",
            budget_backend=budget_backend,
            artifact_class="closeout",
        )
        if isinstance(failure, RunnerError):
            raise failure
        raise RunnerError("organic arm hook failed closed") from failure

    if outcome is None:  # pragma: no cover - guarded by failure/outcome flow
        raise RunnerError("organic arm outcome is absent")
    if budget_backend is not None:
        ledger_events, ledger_identity = _budgeted_ledger_observation(ledger)
        ledger_status = "complete"
    else:
        ledger_result = read_segment(ledger.path)
        if ledger_result.status != "complete":
            raise RunnerError("cut ledger is not a complete sealed segment")
        ledger_events = list(ledger_result.events)
        ledger_identity = snapshot_regular(
            ledger.path,
            label="cut ledger segment",
        ).identity
        ledger_status = ledger_result.status
    journal_events, journal_identity = _journal_observation(journal)
    cut_activity = _join_ledger_and_journal(
        ledger_events,
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
                budget_backend=budget_backend,
                artifact_class="publication",
            ),
            "present": True,
            "solution_vector_identity": _write_exclusive(
                attempt_dir / "raw-solution-vector.json",
                canonical_json(list(outcome.raw_solution_vector or ())),
                label="raw solution-vector export",
                budget_backend=budget_backend,
                artifact_class="publication",
            ),
        }
    if (
        budget_backend is not None
        and bool(getattr(hooks, "requires_budget_authority", False))
    ):
        replay_subject = (
            dict(outcome.raw_incumbent)
            if outcome.raw_incumbent is not None
            else _strict_loads(
                replay_identity(
                    manifest["baseline_incumbent_identity"],
                    "baseline incumbent",
                ).data,
                "baseline incumbent",
            )
        )
        if not isinstance(replay_subject, Mapping):
            raise RunnerError("cut-free replay subject is not an incumbent object")
        subject_identity = (
            incumbent_export["incumbent_identity"]
            if incumbent_export["present"] is True
            else manifest["baseline_incumbent_identity"]
        )
        if not isinstance(subject_identity, Mapping):
            raise RunnerError("cut-free replay subject identity is absent")
        _publish_cut_free_incumbent_replay(
            attempt_dir=attempt_dir,
            incumbent_identity=subject_identity,
            incumbent_value=replay_subject,
            inputs=cut_free_inputs,
            budget_backend=budget_backend,
        )
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
            "cut_ledger_identity": ledger_identity,
            "cut_ledger_status": ledger_status,
            "journal_event_counts": journal_counts,
            "ledger_event_counts": _event_counts(ledger_events),
        },
        "fresh_process_required": True,
        "incumbent_export": incumbent_export,
        "raw_metrics": dict(outcome.raw_metrics),
        "raw_proof_summary": dict(outcome.raw_proof_summary),
        "raw_solver_status": outcome.raw_solver_status,
        "runtime_wall_monotonic_ns": time.monotonic_ns() - started_ns,
        "schema_version": result_schema,
        "selection_nonce": selection["selection_nonce"],
        "slot": selection["slot"],
        "status": "RAW_ARM_OBSERVATION_COMPLETE",
        "workers": 1,
    }
    if budget_binding is not None:
        result["budget_authority_binding"] = budget_binding
    result_identity = _write_exclusive(
        attempt_dir / "result.json",
        canonical_json(result),
        label="organic arm result",
        budget_backend=budget_backend,
        artifact_class="publication",
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
    requires_sealed_import_boundary = True
    requires_budget_authority = True

    @staticmethod
    def _export_model(
        model: Any,
        path: Path,
        *,
        budget_backend: ArmBudgetBackend | None = None,
    ) -> dict[str, object]:
        if budget_backend is not None:
            maximum = _budget_maximum(
                budget_backend,
                "attach model evidence",
                artifact_class="model",
            )
            try:
                identity = dict(
                    budget_backend.export_model_to_sealed_memfd(
                        model,
                        Path(os.path.abspath(path)),
                        maximum_bytes=maximum,
                        label="attach model evidence",
                    )
                )
            except Exception as exc:
                raise RunnerError(
                    "sealed memfd model export or broker transfer failed closed"
                ) from exc
            size_bytes = identity.get("size_bytes")
            if (
                not {"path", "sha256", "size_bytes"} <= set(identity)
                or identity.get("path") != str(Path(os.path.abspath(path)))
                or type(identity.get("sha256")) is not str
                or SHA256_RE.fullmatch(str(identity["sha256"])) is None
                or type(size_bytes) is not int
                or size_bytes < 0
                or size_bytes > maximum
            ):
                raise RunnerError("sealed memfd model export receipt differs")
            return identity
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
        from src.models.master_model import MasterPlacementModel
        from src.search.benders_loop import ExactSearchSession, LBBDController

        origins = _audit_src_module_origins(context.execution_source)
        origin_receipt = {
            "authorizations": {
                "global_claim_authorized": False,
                "mathematical_claim_authorized": False,
                "production_certified_authorized": False,
            },
            "import_mode": "ordinary_pathfinder",
            "module_origins": origins,
            "module_origin_policy": "sealed-snapshot-only-v1",
            "runner_module": FORMAL_RUNNER_MODULE,
            "runner_snapshot_member_identity": dict(
                context.execution_source["runner_snapshot_member_identity"]
            ),
            "schema_version": (
                FORMAL_MODULE_ORIGIN_RECEIPT_SCHEMA
                if context.budget_backend is not None
                else MODULE_ORIGIN_RECEIPT_SCHEMA
            ),
            "sealed_snapshot_execution_root": str(context.repository_root),
            "status": "PASS",
        }
        _write_exclusive(
            Path(context.execution_source["module_origin_receipt_path"]),
            canonical_json(origin_receipt),
            label="module-origin receipt",
            budget_backend=context.budget_backend,
            artifact_class="metadata",
        )
        session = ExactSearchSession.create(
            context.repository_root,
            solve_mode="certified_exact",
        )
        master = MasterPlacementModel.from_exact_core(
            session.core,
            ghost_rect=tuple(parameters["ghost_rect"]),
        )
        if context.budget_backend is None:
            from src.models.cut_manager import CutManager

            cut_manager = CutManager(
                checkpoint_dir=context.attempt_dir / "checkpoint",
                solve_mode="certified_exact",
            )
        else:
            from docs.research.noncert_cuts_ab16_20260724.ab16_budgeted_writers_v1 import (
                AB16BudgetedCutManager,
            )

            cut_manager = AB16BudgetedCutManager(
                checkpoint_dir=context.attempt_dir / "checkpoint",
                solve_mode="certified_exact",
                immutable_budget=context.budget_backend,
                budget_channel=f"arm-{context.selection['slot']}-runtime-cuts",
                budget_segment_max_bytes=_budget_maximum(
                    context.budget_backend,
                    "runtime cut segment",
                    artifact_class="ledger",
                ),
                budget_arm_slot=str(context.selection["slot"]),
            )
        controller = LBBDController(
            master=master,
            cut_manager=cut_manager,
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
                    budget_backend=context.budget_backend,
                    artifact_class="publication",
                )
                pre_model_identity = self._export_model(
                    runtime.master.model,
                    evidence_prefix.with_name(evidence_prefix.name + "-pre-model.pb"),
                    budget_backend=context.budget_backend,
                )
                attached = production_attach_entry(
                    trigger=trigger,
                    iteration=iteration,
                    solution=solution,
                )
                post_model_identity = self._export_model(
                    runtime.master.model,
                    evidence_prefix.with_name(evidence_prefix.name + "-post-model.pb"),
                    budget_backend=context.budget_backend,
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


def run_selected_arm(
    selection_path: Path | str,
    *,
    budget_backend: ArmBudgetBackend | None = None,
) -> dict[str, object]:
    """Public one-shot entry: one selected arm per fresh Python process."""

    return _run_with_hooks(
        Path(selection_path),
        ProductionArmHooks(),
        enforce_single_process_use=True,
        budget_backend=budget_backend,
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
