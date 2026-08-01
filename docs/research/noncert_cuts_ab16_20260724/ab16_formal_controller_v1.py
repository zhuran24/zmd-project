#!/usr/bin/env python3
"""Package-pinned outer payload for one formal AB16 campaign.

The controller is deliberately not a launch authority.  It consumes the
independently published formal selection, waits for the supervisor's
canonical barrier, and only then runs the already-owned campaign stages:

1. Gate1-v4 formal preparation, four fixed child units, and formal gate;
2. a fresh selected-byte baseline rebuild, fixed-assignment replay, and
   independent baseline admission;
3. the immutable organic manifest and non-launching suite selection;
4. the fixed sixteen-arm sequence, one fresh selected unit at a time.

System effects stay behind existing owners.  Gate1-v4 is called through its
unchanged execution owner, each baseline role is a fresh selected-byte child,
and organic units are launched only by ``organic_unit_orchestrator_v2``.
Per-arm prelaunch ownership is a canonical request/receipt exchange with the
outer supervisor.  This module never publishes Gate B, formal admission,
formal selection, outer lifecycle evidence, or a final successful closeout.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import selectors
import signal
import socket
import stat
import sys
import time
from types import ModuleType, SimpleNamespace
from typing import Any, cast, Protocol

from docs.research.noncert_cuts_ab16_20260724 import ab16_authority_v2 as authority
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_formal_launch_validator_v1 as launch_validator,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_resource_admission_v1 as resource_admission,
)


CONTROLLER_RESULT_SCHEMA = "noncert-cuts-ab16-formal-controller-result-v3"
OUTER_BARRIER_SCHEMA = "noncert-cuts-ab16-outer-barrier-release-v1"
AUTHORITY_SCOPE = "AB16_RESEARCH_ONLY"
CONTROLLER_RESULT_NAME = "controller-result.json"
_AUTHORITY_ARM_SEQUENCE = authority.EXPERIMENT_CONTRACT.get("order")
if (
    type(_AUTHORITY_ARM_SEQUENCE) is not list
    or len(_AUTHORITY_ARM_SEQUENCE) != 16
    or any(type(slot) is not str or not slot for slot in _AUTHORITY_ARM_SEQUENCE)
):
    raise RuntimeError("AB16 authority-owned arm sequence is malformed")
ARM_SEQUENCE: tuple[str, ...] = tuple(_AUTHORITY_ARM_SEQUENCE)
GATE1_SLOTS = (
    "q-success",
    "q-postseal-fail",
    "forced-control",
    "forced-treatment",
)
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
FALSE_AUTHORIZATIONS = dict(launch_validator.FALSE_CLAIMS)
MAX_ROLE_OUTPUT_BYTES = 8 * 1024 * 1024
RESOURCE_BUDGET_PROFILE_SCHEMA = (
    "noncert-cuts-ab16-resource-budget-profile-v1"
)
FORMAL_APPEND_CHANNEL_FIELDS = frozenset(
    {
        "artifact_class",
        "channel",
        "label",
        "maximum_bytes",
        "maximum_segments",
        "multiplicity_derivation",
        "parent_path",
    }
)
BASELINE_DIRECTORY_LABELS = {
    "prospective/baseline/tmp": (
        "AB16 baseline tmp directory",
        ["0500", "0700"],
    ),
    "prospective/baseline/checkpoint": (
        "AB16 baseline checkpoint directory",
        ["0500", "0700"],
    ),
    "prospective/baseline/checkpoint/benders-cuts": (
        "AB16 baseline cut channel directory",
        ["0700"],
    ),
}
BUDGET_BROKER_MODULE = (
    "docs.research.noncert_cuts_ab16_20260724."
    "ab16_budget_broker_v1"
)
BUDGET_BROKER_RELATIVE = (
    "docs/research/noncert_cuts_ab16_20260724/"
    "ab16_budget_broker_v1.py"
)

BARRIER_FIELDS = frozenset(
    {
        "authority_scope",
        "authorizations",
        "campaign_root_identity",
        "formal_selection_identity",
        "gate1_prelaunch_ownership_identity",
        "lock_identities",
        "manager_epoch",
        "outer_resource_identity",
        "outer_start_identity",
        "reference_acquisition_identity",
        "released",
        "schema_version",
        "status",
    }
)


class FormalControllerError(RuntimeError):
    """The selected controller sequence failed closed."""


@dataclass(frozen=True)
class FormalInputs:
    """Read-only validated authority needed before the barrier."""

    context: dict[str, object]
    guardian_process_identity: dict[str, int]
    supervisor_process_identity: dict[str, int]
    selection: dict[str, object]
    selection_identity: dict[str, object]


@dataclass(frozen=True)
class SelectedRoleResult:
    """One fresh selected-byte child result."""

    role: str
    returncode: int
    stdout: bytes
    stderr: bytes


class ControllerPorts(Protocol):
    """Narrow seams around effects already owned elsewhere."""

    def wait_for_barrier(self, inputs: FormalInputs) -> tuple[dict[str, object], dict[str, object]]:
        """Wait for and validate the single supervisor release barrier."""

    def run_gate1(self, inputs: FormalInputs) -> Mapping[str, object]:
        """Run the unchanged Gate1-v4 formal owner in its fixed order."""

    def run_selected_role(
        self,
        inputs: FormalInputs,
        *,
        role: str,
        argv: Sequence[str],
        timeout_seconds: float,
    ) -> SelectedRoleResult:
        """Run one package-selected role in a fresh process."""

    def run_baseline_chain(self, inputs: FormalInputs) -> Mapping[str, object]:
        """Run the fixed three-role baseline chain."""

    def publish_arm_prelaunch_request(
        self,
        inputs: FormalInputs,
        *,
        slot: str,
        ordinal: int,
    ) -> dict[str, object]:
        """Publish the existing helper-owned prelaunch request."""

    def wait_for_arm_prelaunch_receipt(
        self,
        inputs: FormalInputs,
        *,
        slot: str,
        ordinal: int,
        request_identity: Mapping[str, object],
    ) -> dict[str, object]:
        """Return the independently replayed receipt identity and admission."""

    def prepare_arm_budget(
        self,
        inputs: FormalInputs,
        *,
        slot: str,
    ) -> tuple[Mapping[str, object], BudgetPublicationBackend]:
        """Allocate one slot and return its supervisor publication backend."""

    def run_organic_arm(
        self,
        inputs: FormalInputs,
        *,
        arm_budget_backend: BudgetPublicationBackend,
        pre_run_path: Path,
        resource_admission_receipt: Mapping[str, object],
        selection_path: Path,
    ) -> Mapping[str, object]:
        """Delegate one selected arm to the existing organic orchestrator."""


class BudgetPublicationBackend(Protocol):
    """Authenticated formal-root broker view retained by the controller."""

    @property
    def authority_binding(self) -> Mapping[str, object]: ...

    @property
    def formal_budget_runtime(self) -> Mapping[str, object]: ...

    @property
    def selected_fd_transport(self) -> Mapping[str, object]: ...

    @property
    def native_helper(self) -> object: ...

    @property
    def enforced_budget_profile(self) -> Mapping[str, object]: ...

    @property
    def enforced_budget_profile_identity(
        self,
    ) -> Mapping[str, object]: ...

    @property
    def resource_calibration_authorization_bundle(
        self,
    ) -> Mapping[str, object]: ...

    @property
    def resource_calibration_authorization_bundle_identity(
        self,
    ) -> Mapping[str, object]: ...

    @property
    def expected_calibration_tool_identities(
        self,
    ) -> Mapping[str, Mapping[str, object]]: ...

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

    def expected_root_path_types(self) -> list[dict[str, str]]: ...

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
    ) -> Mapping[str, object]: ...

    def accept_prior_arm_seal_response(
        self,
        *,
        continuation: str,
        successor_arm_slot: str | None,
    ) -> Mapping[str, object]: ...

    def publish_accepted_arm_replay(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        label: str,
    ) -> Mapping[str, object]: ...

    def publish_arm_consumption(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        label: str,
        replay_identity: Mapping[str, object],
    ) -> Mapping[str, object]: ...

    def register_formal_worker_grant(
        self,
        *,
        credential: str,
        expected_peer: Mapping[str, object],
        pidfd: int,
    ) -> Mapping[str, object]: ...

    def bind_formal_selection(
        self,
        selection_identity: Mapping[str, object],
    ) -> Mapping[str, object]: ...

    def allocate_arm(
        self,
        *,
        arm_slot: str,
        category_limits: Mapping[str, object],
    ) -> Mapping[str, object]: ...

    def preregister_manager_openfile_arm_grant(
        self,
        *,
        allocation_identity: Mapping[str, object],
        arm_slot: str,
        attempt_consumption_identity: Mapping[str, object],
        credential: str,
        manager_epoch_identity: Mapping[str, object],
        selection_identity: Mapping[str, object],
        unit_name: str,
    ) -> Mapping[str, object]: ...

    def register_bound_arm_grant(
        self,
        *,
        credential: str,
        expected_peer: Mapping[str, object],
        pidfd: int,
        role: str,
        arm_slot: str,
        selection_identity: Mapping[str, object],
        allocation_identity: Mapping[str, object],
    ) -> Mapping[str, object]: ...

    def connect_registered_arm(
        self,
        *,
        credential: str,
        role: str,
        arm_slot: str,
        selection_identity: Mapping[str, object],
        allocation_identity: Mapping[str, object],
    ) -> object: ...

    def close(self) -> None: ...


def _closed(value: object, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != set(fields):
        raise FormalControllerError(f"{label} field set drifted")
    return dict(value)


def _identity(value: object, label: str) -> dict[str, object]:
    try:
        return launch_validator.validate_detached_identity(value, label)
    except Exception as exc:
        raise FormalControllerError(f"{label} is invalid: {exc}") from exc


def _snapshot_identity(path: Path | str) -> dict[str, object]:
    return authority.detached_identity(authority.snapshot_regular(path))


def _read_record(
    path: Path | str,
    *,
    expected_identity: Mapping[str, object] | None,
    label: str,
) -> tuple[dict[str, Any], dict[str, object]]:
    try:
        return launch_validator.read_canonical_record(
            path,
            expected_identity=expected_identity,
            label=label,
        )
    except Exception as exc:
        raise FormalControllerError(f"{label} replay failed: {exc}") from exc


def load_formal_inputs(
    *,
    campaign_dir: Path | str,
    formal_selection: Path | str,
) -> FormalInputs:
    """Replay the complete formal selection without authoring any authority."""

    campaign = Path(campaign_dir).absolute()
    selection_path = Path(formal_selection).absolute()
    try:
        context = launch_validator.replay_formal_launch_context(authority, campaign)
    except Exception as exc:
        raise FormalControllerError(f"formal launch context replay failed: {exc}") from exc
    if selection_path != Path(str(context["formal_selection_path"])):
        raise FormalControllerError("caller formal selection path differs from authority context")
    selection, selection_identity = _read_record(
        selection_path,
        expected_identity=None,
        label="formal selection",
    )
    prerequisite_fields = {
        "formal_admission_identity": "formal admission",
        "guardian_ready_identity": "guardian ready",
        "attempt_consumption_identity": "attempt consumption",
    }
    records: dict[str, dict[str, Any]] = {}
    identities: dict[str, dict[str, object]] = {}
    for field, label in prerequisite_fields.items():
        expected = _identity(selection.get(field), f"selection {field}")
        record, observed = _read_record(
            expected["path"],
            expected_identity=expected,
            label=label,
        )
        records[field] = record
        identities[field] = observed
    try:
        checked = launch_validator.validate_selection(
            selection,
            admission=records["formal_admission_identity"],
            admission_identity=identities["formal_admission_identity"],
            guardian_ready=records["guardian_ready_identity"],
            guardian_ready_identity=identities["guardian_ready_identity"],
            attempt_consumption=records["attempt_consumption_identity"],
            attempt_consumption_identity=identities["attempt_consumption_identity"],
            expected_context=context,
        )
    except Exception as exc:
        raise FormalControllerError(f"formal selection validation failed: {exc}") from exc
    if checked["outer_spec"]["barrier_path"] != context["outer_spec"]["barrier_path"]:
        raise FormalControllerError("formal selection barrier join drifted")
    try:
        guardian_process_identity = launch_validator.validate_process_identity(
            records["guardian_ready_identity"].get("guardian_process_identity"),
            "formal controller guardian-ready process",
        )
        supervisor_process_identity = launch_validator.validate_process_identity(
            records["guardian_ready_identity"].get("supervisor_process_identity"),
            "formal controller supervisor process",
        )
    except Exception as exc:
        raise FormalControllerError(
            f"guardian-ready process validation failed: {exc}"
        ) from exc
    return FormalInputs(
        context=dict(context),
        guardian_process_identity=guardian_process_identity,
        supervisor_process_identity=supervisor_process_identity,
        selection=dict(checked),
        selection_identity=selection_identity,
    )


def _arm_resource_observation_context(
    inputs: FormalInputs,
    *,
    slot: str,
    ordinal: int,
) -> dict[str, object]:
    if slot != ARM_SEQUENCE[ordinal - 1]:
        raise FormalControllerError("arm resource observation order drifted")
    return {
        "authority_id": inputs.selection_identity["sha256"],
        "disk_path": str(Path(str(inputs.context["campaign_dir"])).absolute()),
        "kind": "FORMAL_ORGANIC_ARM_PRELAUNCH",
        "ordinal": ordinal,
        "scope_id": inputs.context["campaign_root_identity"]["sha256"],
        "sequence": ordinal + 1,
        "slot": slot,
        "target": "DERIVE_FROM_VALIDATED_PRE_RUN",
    }


def validate_outer_barrier(
    value: object,
    *,
    inputs: FormalInputs,
) -> dict[str, object]:
    """Validate the supervisor release without granting any new authority."""

    record = _closed(value, BARRIER_FIELDS, "outer barrier")
    for field in (
        "campaign_root_identity",
        "formal_selection_identity",
        "gate1_prelaunch_ownership_identity",
        "outer_resource_identity",
        "outer_start_identity",
        "reference_acquisition_identity",
    ):
        record[field] = _identity(record[field], f"outer barrier {field}")
    try:
        record["lock_identities"] = launch_validator.validate_lock_identities(record["lock_identities"])
    except Exception as exc:
        raise FormalControllerError(f"outer barrier lock identities failed: {exc}") from exc
    outer_paths = inputs.selection["outer_spec"]["receipt_paths"]
    expected_paths = {
        "outer_start_identity": outer_paths["outer_start"],
        "outer_resource_identity": outer_paths["outer_resource"],
        "reference_acquisition_identity": outer_paths["reference_acquisition"],
        "gate1_prelaunch_ownership_identity": inputs.selection["gate1_prelaunch_ownership_path"],
    }
    if any(record[field]["path"] != expected for field, expected in expected_paths.items()):
        raise FormalControllerError("outer barrier prerequisite path drifted")
    if (
        record["schema_version"] != OUTER_BARRIER_SCHEMA
        or record["status"] != "RELEASED"
        or record["authority_scope"] != AUTHORITY_SCOPE
        or record["released"] is not True
        or record["authorizations"] != FALSE_AUTHORIZATIONS
        or record["campaign_root_identity"] != inputs.context["campaign_root_identity"]
        or record["formal_selection_identity"] != inputs.selection_identity
        or record["manager_epoch"] != inputs.context["manager_epoch"]
        or record["lock_identities"] != inputs.selection["lock_identities"]
    ):
        raise FormalControllerError("outer barrier authority/identity join drifted")
    for field in expected_paths:
        _read_record(
            record[field]["path"],
            expected_identity=record[field],
            label=f"outer barrier prerequisite {field}",
        )
    return record


def _wait_for_record(
    path: Path,
    *,
    timeout_seconds: float,
    label: str,
) -> tuple[dict[str, Any], dict[str, object]]:
    if timeout_seconds <= 0:
        raise FormalControllerError(f"{label} timeout is not positive")
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            observed = os.lstat(path)
        except FileNotFoundError:
            observed = None
        except OSError as exc:
            raise FormalControllerError(
                f"{label} surface could not be inspected"
            ) from exc
        if (
            observed is not None
            and stat.S_ISREG(observed.st_mode)
            and stat.S_IMODE(observed.st_mode) == 0o444
        ):
            return _read_record(path, expected_identity=None, label=label)
        if observed is not None and (
            not stat.S_ISREG(observed.st_mode)
            or stat.S_IMODE(observed.st_mode) != 0o600
        ):
            raise FormalControllerError(
                f"{label} surface is not one readonly regular file"
            )
        if time.monotonic() >= deadline:
            raise FormalControllerError(f"{label} did not appear before its fixed deadline")
        time.sleep(0.05)


def _module_origin(module: ModuleType, *, snapshot_root: Path, relative: str, label: str) -> None:
    raw = getattr(module, "__file__", None)
    expected = snapshot_root / relative
    if type(raw) is not str or Path(raw).resolve(strict=False) != expected.resolve(strict=False):
        raise FormalControllerError(f"{label} did not originate in the sealed snapshot")


def _import_snapshot_owner(
    inputs: FormalInputs,
    *,
    module_name: str,
    relative: str,
    aliases: Sequence[tuple[str, str, str]] = (),
) -> ModuleType:
    """Import one existing owner through the loader-established PathFinder."""

    snapshot_root = Path(str(inputs.context["snapshot_root"]))
    for alias, alias_module, alias_relative in aliases:
        loaded = importlib.import_module(alias_module)
        _module_origin(
            loaded,
            snapshot_root=snapshot_root,
            relative=alias_relative,
            label=f"snapshot alias {alias}",
        )
        present = sys.modules.get(alias)
        if present is not None and present is not loaded:
            raise FormalControllerError(f"snapshot alias collision: {alias}")
        sys.modules[alias] = loaded
    module = importlib.import_module(module_name)
    _module_origin(
        module,
        snapshot_root=snapshot_root,
        relative=relative,
        label=module_name,
    )
    return module


def _formal_budget_tables(
    inputs: FormalInputs,
) -> tuple[
    Path,
    dict[str, object],
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
]:
    grant = inputs.selection.get("manager_openfile_grant")
    if (
        inputs.selection.get("schema_version")
        != launch_validator.FORMAL_SELECTION_SCHEMA_V3
        or type(grant) is not dict
    ):
        raise FormalControllerError(
            "formal budget backend requires exact selection v3"
        )
    profile_identity = grant["budget_profile_identity"]
    profile, observed = _read_record(
        profile_identity["path"],
        expected_identity={
            field: profile_identity[field]
            for field in ("path", "sha256", "size_bytes")
        },
        label="formal budget profile",
    )
    if observed != {
        field: profile_identity[field]
        for field in ("path", "sha256", "size_bytes")
    }:
        raise FormalControllerError(
            "formal budget profile identity drifted"
        )
    if (
        set(profile)
        != {
            "authority",
            "bootstrap",
            "execution_surface_sha256",
            "formal_root",
            "launch_ready",
            "profile_id",
            "profile_sha256",
            "schema_version",
        }
        or profile["schema_version"] != RESOURCE_BUDGET_PROFILE_SCHEMA
        or profile["launch_ready"] is not True
        or type(profile["formal_root"]) is not dict
    ):
        raise FormalControllerError(
            "formal budget profile is not one launch-ready exact cohort"
        )
    formal = profile["formal_root"]
    if set(formal) != {
        "append_channels",
        "arm_allocations",
        "arm_append_channels",
        "arm_artifact_caps",
        "arm_workload_contract",
        "artifact_maxima",
        "category_limits",
        "fixed_directories",
        "fixed_overhead_category_limits",
        "fixed_purpose_reservations",
        "root_relative_path",
    }:
        raise FormalControllerError(
            "formal budget profile lacks the exact append-channel cohort"
        )
    formal_root = Path(str(inputs.context["campaign_dir"])) / (
        "formal-ab16/artifacts"
    )
    if formal["root_relative_path"] != "formal-ab16/artifacts":
        raise FormalControllerError("formal budget root path drifted")

    def relative(value: object, label: str) -> str:
        if type(value) is not str:
            raise FormalControllerError(f"{label} is not text")
        parsed = PurePosixPath(value)
        if (
            parsed.is_absolute()
            or not parsed.parts
            or any(part in {"", ".", ".."} for part in parsed.parts)
        ):
            raise FormalControllerError(f"{label} escaped formal root")
        return parsed.as_posix()

    artifacts_raw = formal["artifact_maxima"]
    if type(artifacts_raw) is not list or not artifacts_raw:
        raise FormalControllerError(
            "formal fixed artifact table is absent"
        )
    fixed_artifacts: dict[str, dict[str, object]] = {}
    for index, item in enumerate(artifacts_raw):
        if (
            type(item) is not dict
            or set(item)
            != {
                "artifact_class",
                "label",
                "maximum_bytes",
                "path",
                "required_on_success",
            }
            or type(item["label"]) is not str
            or not item["label"]
            or type(item["artifact_class"]) is not str
            or isinstance(item["maximum_bytes"], bool)
            or not isinstance(item["maximum_bytes"], int)
            or item["maximum_bytes"] <= 0
            or type(item["required_on_success"]) is not bool
            or item["label"] in fixed_artifacts
        ):
            raise FormalControllerError(
                f"formal fixed artifact[{index}] is invalid"
            )
        fixed_artifacts[item["label"]] = {
            "artifact_class": item["artifact_class"],
            "maximum_bytes": item["maximum_bytes"],
            "relative_path": relative(
                item["path"],
                f"formal fixed artifact[{index}].path",
            ),
        }

    channels_raw = formal["append_channels"]
    if type(channels_raw) is not list or not channels_raw:
        raise FormalControllerError(
            "formal append-channel table is absent"
        )
    fixed_channels: dict[str, dict[str, object]] = {}
    for index, item in enumerate(channels_raw):
        if (
            type(item) is not dict
            or set(item) != set(FORMAL_APPEND_CHANNEL_FIELDS)
            or isinstance(item["maximum_bytes"], bool)
            or not isinstance(item["maximum_bytes"], int)
            or item["maximum_bytes"] <= 0
            or isinstance(item["maximum_segments"], bool)
            or not isinstance(item["maximum_segments"], int)
            or type(item["multiplicity_derivation"]) is not dict
            or item["multiplicity_derivation"].get(
                "result_maximum_segments"
            )
            != item["maximum_segments"]
            or item["channel"] in fixed_channels
        ):
            raise FormalControllerError(
                f"formal append channel[{index}] is invalid"
            )
        derivation = item["multiplicity_derivation"]
        if item["channel"] == "ab16-baseline-rebuild-cuts":
            valid_contract = (
                item["label"] == "AB16 baseline cut segment"
                and item["artifact_class"] == "ledger"
                and item["maximum_segments"] == 128
                and derivation
                == {
                    "basis": (
                        "temporary unmeasured conservative baseline append cap"
                    ),
                    "evidence_status": "unmeasured-temporary",
                    "exhaustion": "formal-consumed-incomplete",
                    "result_maximum_segments": 128,
                }
            )
        elif item["channel"] == "budget-journal":
            valid_contract = (
                item["label"] == "AB16 formal budget journal segment"
                and item["artifact_class"] == "metadata"
                and item["maximum_bytes"] == 4096
                and item["maximum_segments"] == 16_384
                and item["parent_path"] == "channels/budget-journal"
                and derivation
                == {
                    "basis": (
                        "profile-derived data-plane maxima plus explicit "
                        "temporary control-plane allowances"
                    ),
                    "bootstrap_and_formal_control_allowance": 2048,
                    "derived_minimum_actions": 12_320,
                    "evidence_status": "unmeasured-temporary",
                    "exhaustion": (
                        "fail before the next broker-journal append; "
                        "formal-consumed-incomplete"
                    ),
                    "formal_arm_count": 16,
                    "maximum_segment_bytes": 4096,
                    "per_arm_append_maximum": 479,
                    "per_arm_control_allowance": 64,
                    "per_arm_fixed_publication_branch_maximum": 99,
                    "retained_allocation_bytes": 67_108_864,
                    "result_maximum_segments": 16_384,
                    "segment_cap_basis": (
                        "policy-defined canonical action-record cap pending "
                        "comparable calibration"
                    ),
                    "segment_count_rounding": (
                        "next power of two above derived minimum actions"
                    ),
                    "sufficiency_claim": False,
                }
            )
        else:
            valid_contract = False
        if not valid_contract:
            raise FormalControllerError(
                f"formal append channel[{index}] contract drifted"
            )
        fixed_channels[item["channel"]] = {
            "artifact_class": item["artifact_class"],
            "label": item["label"],
            "maximum_bytes": item["maximum_bytes"],
            "maximum_segments": item["maximum_segments"],
            "relative_path": relative(
                item["parent_path"],
                f"formal append channel[{index}].parent_path",
            ),
        }
    if set(fixed_channels) != {
        "ab16-baseline-rebuild-cuts",
        "budget-journal",
    }:
        raise FormalControllerError(
            "formal append-channel set is not exact"
        )
    worker_channels = {
        "ab16-baseline-rebuild-cuts": fixed_channels[
            "ab16-baseline-rebuild-cuts"
        ]
    }

    directories_raw = formal["fixed_directories"]
    if type(directories_raw) is not list:
        raise FormalControllerError(
            "formal fixed directory table is invalid"
        )
    observed_directories: dict[str, str] = {}
    for index, item in enumerate(directories_raw):
        if (
            type(item) is not dict
            or set(item) != {"mode_octal", "path"}
            or item["mode_octal"] not in {"0500", "0700"}
        ):
            raise FormalControllerError(
                f"formal fixed directory[{index}] is invalid"
            )
        path = (
            "."
            if item["path"] == "."
            else relative(
                item["path"],
                f"formal fixed directory[{index}].path",
            )
        )
        if path in observed_directories:
            raise FormalControllerError(
                "formal fixed directory table contains a duplicate"
            )
        observed_directories[path] = item["mode_octal"]
    fixed_directories: dict[str, dict[str, object]] = {}
    for path, (label, allowed_modes) in BASELINE_DIRECTORY_LABELS.items():
        if observed_directories.get(path) not in set(allowed_modes):
            raise FormalControllerError(
                f"formal budget profile lacks {label}"
            )
        fixed_directories[label] = {
            "allowed_modes": list(allowed_modes),
            "relative_path": path,
        }
    return (
        formal_root,
        dict(profile),
        fixed_artifacts,
        worker_channels,
        fixed_directories,
    )


def _formal_resource_calibration_bundle(
    inputs: FormalInputs,
) -> tuple[dict[str, object], dict[str, object]]:
    bundles = inputs.context.get(
        "resource_calibration_authorization_bundles"
    )
    grant = inputs.selection.get("manager_openfile_grant")
    if type(bundles) is not dict or type(grant) is not dict:
        raise FormalControllerError(
            "formal calibration authorization bundle is absent"
        )
    entry = bundles.get("FORMAL_ORGANIC_ARM")
    if (
        type(entry) is not dict
        or set(entry) != {"identity", "record"}
        or type(entry["identity"]) is not dict
        or type(entry["record"]) is not dict
        or grant.get(
            "formal_resource_calibration_bundle_identity"
        )
        != entry["identity"]
    ):
        raise FormalControllerError(
            "formal calibration authorization bundle binding drifted"
        )
    return dict(entry["record"]), dict(entry["identity"])


def _formal_calibration_tool_content_identities(
    inputs: FormalInputs,
) -> dict[str, dict[str, object]]:
    value = inputs.context.get("calibration_tool_content_identities")
    if (
        type(value) is not dict
        or set(value) != resource_admission.CALIBRATION_TOOL_ROLES
    ):
        raise FormalControllerError(
            "formal calibration tool identity cohort is absent or mixed"
        )
    result: dict[str, dict[str, object]] = {}
    for role, identity in sorted(value.items()):
        if (
            type(identity) is not dict
            or set(identity) != {"sha256", "size_bytes"}
            or type(identity["sha256"]) is not str
            or SHA256_RE.fullmatch(identity["sha256"]) is None
            or isinstance(identity["size_bytes"], bool)
            or not isinstance(identity["size_bytes"], int)
            or identity["size_bytes"] <= 0
        ):
            raise FormalControllerError(
                f"formal calibration tool identity is malformed: {role}"
            )
        result[role] = dict(identity)
    return result


def formal_supervisor_budget_material(
    context: Mapping[str, object],
) -> dict[str, object]:
    """Replay the preselection supervisor tables from one validated context.

    This is a read-only projection.  It deliberately supplies no selection
    identity and performs no broker authentication; the selected supervisor
    factory separately consumes its pidfd-bound FD8 grant.
    """

    checked_context = launch_validator.validate_formal_context(context)
    profile_identity = checked_context[
        "resource_budget_profile_identity"
    ]
    bundles = checked_context[
        "resource_calibration_authorization_bundles"
    ]
    formal_bundle = cast(
        Mapping[str, object],
        cast(Mapping[str, object], bundles)["FORMAL_ORGANIC_ARM"],
    )
    synthetic = FormalInputs(
        context=dict(checked_context),
        guardian_process_identity={},
        supervisor_process_identity={},
        selection={
            "manager_openfile_grant": {
                "budget_profile_identity": dict(
                    cast(Mapping[str, object], profile_identity)
                ),
                "formal_resource_calibration_bundle_identity": dict(
                    cast(
                        Mapping[str, object],
                        formal_bundle["identity"],
                    )
                ),
            },
            "schema_version": (
                launch_validator.FORMAL_SELECTION_SCHEMA_V3
            ),
        },
        selection_identity={},
    )
    (
        formal_root,
        profile,
        fixed_artifacts,
        fixed_channels,
        fixed_directories,
    ) = _formal_budget_tables(synthetic)
    calibration_bundle, calibration_identity = (
        _formal_resource_calibration_bundle(synthetic)
    )
    derived_bindings = {
        str(
            (
                formal_root
                / cast(str, specification["relative_path"])
            ).absolute()
        ): {
            "artifact_class": specification["artifact_class"],
            "label": label,
        }
        for label, specification in fixed_artifacts.items()
    }
    expected_bindings = checked_context[
        "formal_receipt_budget_bindings"
    ]
    if derived_bindings != expected_bindings:
        raise FormalControllerError(
            "formal receipt budget bindings differ from the exact profile"
        )
    return {
        "calibration_bundle": calibration_bundle,
        "calibration_bundle_identity": calibration_identity,
        "calibration_tool_content_identities": (
            _formal_calibration_tool_content_identities(synthetic)
        ),
        "fixed_artifacts": fixed_artifacts,
        "fixed_channels": fixed_channels,
        "fixed_directories": fixed_directories,
        "formal_root": str(formal_root),
        "profile": profile,
        "receipt_budget_bindings": dict(
            cast(Mapping[str, object], expected_bindings)
        ),
    }


def _arm_budget_profile_tables(
    inputs: FormalInputs,
    *,
    slot: str,
    allocation: Mapping[str, object],
) -> tuple[
    Path,
    Path,
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
    dict[str, object],
]:
    profile = inputs.context.get("resource_budget_profile")
    if type(profile) is not dict:
        _formal_root, loaded, _artifacts, _channels, _directories = (
            _formal_budget_tables(inputs)
        )
        profile = loaded
    formal = profile.get("formal_root")
    if type(formal) is not dict:
        raise FormalControllerError(
            "arm budget profile lacks its formal-root table"
        )
    allocations = formal.get("arm_allocations")
    artifact_caps = formal.get("arm_artifact_caps")
    arm_channels = formal.get("arm_append_channels")
    if (
        type(allocations) is not dict
        or type(allocations.get(slot)) is not dict
        or type(artifact_caps) is not dict
        or type(artifact_caps.get(slot)) is not dict
        or type(arm_channels) is not dict
        or type(arm_channels.get(slot)) is not list
    ):
        raise FormalControllerError(
            "arm budget profile lacks one exact allocation cohort"
        )
    formal_root = Path(str(inputs.context["campaign_dir"])) / (
        "formal-ab16/artifacts"
    )
    attempt_root = Path(
        str(
            authority._path_preregistration(  # noqa: SLF001
                authority._campaign_context(  # noqa: SLF001
                    inputs.context["campaign_dir"]
                )
            )[0]["attempt_dirs"][slot]
        )
    )
    try:
        attempt_relative = attempt_root.relative_to(
            formal_root
        ).as_posix()
    except ValueError as exc:
        raise FormalControllerError(
            "allocated arm attempt escaped formal root"
        ) from exc
    allocation_limits = cast(dict[str, object], allocations[slot])
    fixed_maxima: dict[str, dict[str, object]] = {}
    for label, item in cast(
        dict[object, object],
        artifact_caps[slot],
    ).items():
        if (
            type(label) is not str
            or not label
            or type(item) is not dict
            or set(item)
            != {
                "artifact_class",
                "branch",
                "maximum_bytes",
                "maximum_publications",
                "multiplicity_source",
                "path_contract",
            }
            or type(item["artifact_class"]) is not str
            or type(item["maximum_bytes"]) is not int
            or item["maximum_bytes"] <= 0
            or type(item["maximum_publications"]) is not int
            or item["maximum_publications"] < 0
            or item["branch"] not in {"common", "failure", "success"}
            or type(item["multiplicity_source"]) is not dict
            or type(item["path_contract"]) is not dict
        ):
            raise FormalControllerError(
                "arm artifact-cap table is malformed"
            )
        artifact_class = cast(str, item["artifact_class"])
        maximum = cast(int, item["maximum_bytes"])
        if (
            type(allocation_limits.get(artifact_class)) is not int
            or maximum > cast(int, allocation_limits[artifact_class])
        ):
            raise FormalControllerError(
                "arm artifact cap exceeds its aggregate category allocation"
            )
        fixed_maxima[label] = dict(item)
    channel_contracts: dict[str, dict[str, object]] = {}
    expected_channel_labels = {
        f"arm-{slot}-compile-journal": "compile attach journal segment",
        f"arm-{slot}-cut-ledger": "cut ledger segment",
        f"arm-{slot}-runtime-cuts": "runtime cut segment",
    }
    expected_channel_segments = {
        f"arm-{slot}-compile-journal": 221,
        f"arm-{slot}-cut-ledger": 258,
        f"arm-{slot}-runtime-cuts": 0,
    }
    for item in cast(list[object], arm_channels[slot]):
        if (
            type(item) is not dict
            or set(item)
            != {
                "artifact_class",
                "channel",
                "label",
                "maximum_bytes",
                "maximum_segments",
                "multiplicity_derivation",
                "parent_path",
            }
            or type(item["channel"]) is not str
            or type(item["parent_path"]) is not str
            or type(item["artifact_class"]) is not str
            or type(item["label"]) is not str
            or type(item["maximum_bytes"]) is not int
            or item["maximum_bytes"] <= 0
            or type(item["maximum_segments"]) is not int
            or item["maximum_segments"] < 0
            or type(item["multiplicity_derivation"]) is not dict
            or item["multiplicity_derivation"].get(
                "result_maximum_segments"
            )
            != item["maximum_segments"]
        ):
            raise FormalControllerError(
                "arm append-channel table is malformed"
            )
        channel = item["channel"]
        if (
            expected_channel_labels.get(channel) != item["label"]
            or expected_channel_segments.get(channel)
            != item["maximum_segments"]
            or item["artifact_class"] != "ledger"
            or type(allocation_limits.get("ledger")) is not int
            or item["maximum_bytes"]
            > cast(int, allocation_limits["ledger"])
            or {
                field: fixed_maxima.get(
                    cast(str, item["label"]),
                    {},
                ).get(field)
                for field in ("artifact_class", "maximum_bytes")
            }
            != {
                "artifact_class": "ledger",
                "maximum_bytes": item["maximum_bytes"],
            }
        ):
            raise FormalControllerError(
                "arm append-channel cap or identity differs"
            )
        parent = PurePosixPath(item["parent_path"])
        expected_parent = {
            f"arm-{slot}-compile-journal": (
                f"{attempt_relative}/ledger/compile-attach-journal"
            ),
            f"arm-{slot}-cut-ledger": (
                f"{attempt_relative}/ledger/cut-ledger"
            ),
            f"arm-{slot}-runtime-cuts": (
                f"{attempt_relative}/checkpoint/runtime-cuts"
            ),
        }[cast(str, channel)]
        if parent.as_posix() != expected_parent:
            raise FormalControllerError(
                "arm append-channel parent differs from fixed layout"
            )
        channel_contracts[cast(str, channel)] = {
            "artifact_class": item["artifact_class"],
            "label": item["label"],
            "maximum_bytes": item["maximum_bytes"],
            "maximum_segments": item["maximum_segments"],
            "relative_path": parent.as_posix(),
        }
    if set(channel_contracts) != set(expected_channel_labels):
        raise FormalControllerError(
            "arm append-channel table is not the exact three-channel cohort"
        )
    registered = allocation.get("registered_directories")
    allocation_identity = allocation.get("allocation_identity")
    if (
        type(registered) is not list
        or type(allocation_identity) is not dict
        or set(allocation_identity) != {"sha256", "size_bytes"}
        or not fixed_maxima
        or not channel_contracts
    ):
        raise FormalControllerError(
            "broker arm allocation lacks its fixed layout or identity"
        )
    directories: list[dict[str, object]] = []
    for item in registered:
        if (
            type(item) is not dict
            or set(item) != {"mode_octal", "path"}
            or item["mode_octal"] not in {"0500", "0700"}
            or type(item["path"]) is not str
        ):
            raise FormalControllerError(
                "broker arm directory receipt is malformed"
            )
        directories.append(
            {
                "mode": int(item["mode_octal"], 8),
                "path": item["path"],
            }
        )
    return (
        formal_root,
        attempt_root,
        fixed_maxima,
        channel_contracts,
        {
            "allocation_identity": dict(allocation_identity),
            "category_limits": dict(allocations[slot]),
            "directories": directories,
        },
    )


def _consume_budget_socket_fd(fd: int, *, label: str) -> int:
    """Consume the caller's FD exactly once and return an owned duplicate."""

    if isinstance(fd, bool) or not isinstance(fd, int) or fd < 0:
        raise FormalControllerError(f"{label} is not one descriptor")
    duplicate = -1
    try:
        duplicate = fcntl.fcntl(fd, fcntl.F_DUPFD_CLOEXEC, 20)
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


def formal_budget_backend_from_fd(
    fd: int,
    *,
    native_budget_helper: object,
    campaign_dir: Path | str,
    formal_selection: Path | str,
) -> BudgetPublicationBackend:
    """Attach FD8 only after replaying selection-v3 and its budget cohort."""

    owned_fd = _consume_budget_socket_fd(
        fd,
        label="formal budget broker FD",
    )
    if fd != 8:
        os.close(owned_fd)
        raise FormalControllerError(
            "formal budget broker must arrive on fixed FD8"
        )
    client: Any | None = None
    try:
        inputs = load_formal_inputs(
            campaign_dir=campaign_dir,
            formal_selection=formal_selection,
        )
        grant = inputs.selection.get("manager_openfile_grant")
        if type(grant) is not dict:
            raise FormalControllerError(
                "formal selection lacks manager OpenFile grant"
            )
        broker_module = _import_snapshot_owner(
            inputs,
            module_name=BUDGET_BROKER_MODULE,
            relative=BUDGET_BROKER_RELATIVE,
            aliases=(
                (
                    "ab16_budget_authority_v1",
                    (
                        "docs.research.noncert_cuts_ab16_20260724."
                        "ab16_budget_authority_v1"
                    ),
                    (
                        "docs/research/noncert_cuts_ab16_20260724/"
                        "ab16_budget_authority_v1.py"
                    ),
                ),
                (
                    "ab16_outer_guardian_v1",
                    (
                        "docs.research.noncert_cuts_ab16_20260724."
                        "ab16_outer_guardian_v1"
                    ),
                    (
                        "docs/research/noncert_cuts_ab16_20260724/"
                        "ab16_outer_guardian_v1.py"
                    ),
                ),
            ),
        )
        runtime = grant["formal_budget_runtime"]
        actor = {
            "schema_version": broker_module.ACTOR_SCHEMA,
            **runtime["broker_actor_identity"],
        }
        transferred_fd = owned_fd
        owned_fd = -1
        client = broker_module.attach_manager_openfile_supervisor(
            transferred_fd,
            broker_actor=actor,
            broker_nonce=runtime["broker_nonce"],
            credential=grant["credential"],
            manager_epoch_identity=grant["manager_epoch_identity"],
            selection_identity=inputs.selection_identity,
            attempt_consumption_identity=grant[
                "attempt_consumption_identity"
            ],
            unit_name=grant["unit_name"],
            native_helper=native_budget_helper,
        )
        (
            formal_root,
            budget_profile,
            fixed_artifacts,
            fixed_channels,
            fixed_directories,
        ) = _formal_budget_tables(inputs)
        calibration_bundle, calibration_bundle_identity = (
            _formal_resource_calibration_bundle(inputs)
        )
        return broker_module.BrokerProcessFormalBudgetBackend(
            broker_client=client,
            native_helper=native_budget_helper,
            formal_root=formal_root,
            enforced_budget_profile=budget_profile,
            resource_calibration_authorization_bundle=(
                calibration_bundle
            ),
            resource_calibration_authorization_bundle_identity=(
                calibration_bundle_identity
            ),
            expected_calibration_tool_identities=(
                _formal_calibration_tool_content_identities(inputs)
            ),
            authority_binding={
                "budget_profile_identity": grant[
                    "budget_profile_identity"
                ],
                "filesystem_write_confinement": (
                    "not-applicable-persistent-supervisor-v1"
                ),
                "formal_budget_runtime": runtime,
                "formal_root_contract_identity": grant[
                    "formal_root_contract_identity"
                ],
                "formal_resource_calibration_bundle_identity": grant[
                    "formal_resource_calibration_bundle_identity"
                ],
                "selected_fd_transport": grant[
                    "selected_fd_transport"
                ],
            },
            fixed_artifacts=fixed_artifacts,
            fixed_channels=fixed_channels,
            fixed_directories=fixed_directories,
            require_worker_confinement=False,
        )
    except BaseException as exc:
        try:
            if client is not None:
                client.close()
            elif owned_fd >= 0:
                os.close(owned_fd)
        except BaseException as cleanup_error:
            exc.add_note(
                "formal broker factory cleanup failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )
        raise


FORMAL_WORKER_SESSION_SCHEMA = (
    "noncert-cuts-ab16-formal-worker-session-v1"
)
FORMAL_WORKER_LABELS = {
    "baseline-rebuild": frozenset(
        {
            "AB16 baseline incumbent",
            "AB16 baseline rebuild result",
            "AB16 baseline rebuilt metadata",
            "AB16 baseline rebuilt model",
        }
    ),
    "baseline-admission": frozenset({"AB16 baseline admission"}),
    "cut-free-incumbent-replay": frozenset(
        {"AB16 baseline fixed replay"}
    ),
}


def formal_worker_budget_backend_from_fd(
    fd: int,
    *,
    native_budget_helper: object,
    campaign_dir: Path | str,
    formal_selection: Path | str,
    worker_role: str,
    worker_session: Mapping[str, object],
) -> BudgetPublicationBackend:
    """Attach a direct, pidfd-preregistered selected child on fixed FD8."""

    owned_fd = _consume_budget_socket_fd(
        fd,
        label="formal worker broker FD",
    )
    if fd != 8 or worker_role not in FORMAL_WORKER_LABELS:
        os.close(owned_fd)
        raise FormalControllerError(
            "formal worker FD or role is outside the fixed child cohort"
        )
    client: Any | None = None
    try:
        if (
            type(worker_session) is not dict
            or set(worker_session)
            != {"broker_grant", "credential", "schema_version"}
            or worker_session["schema_version"]
            != FORMAL_WORKER_SESSION_SCHEMA
            or type(worker_session["credential"]) is not str
            or SHA256_RE.fullmatch(worker_session["credential"]) is None
            or type(worker_session["broker_grant"]) is not dict
        ):
            raise FormalControllerError(
                "formal worker session envelope is malformed"
            )
        inputs = load_formal_inputs(
            campaign_dir=campaign_dir,
            formal_selection=formal_selection,
        )
        manager_grant = inputs.selection.get("manager_openfile_grant")
        if type(manager_grant) is not dict:
            raise FormalControllerError(
                "formal worker selection lacks manager grant"
            )
        broker_module = _import_snapshot_owner(
            inputs,
            module_name=BUDGET_BROKER_MODULE,
            relative=BUDGET_BROKER_RELATIVE,
            aliases=(
                (
                    "ab16_budget_authority_v1",
                    (
                        "docs.research.noncert_cuts_ab16_20260724."
                        "ab16_budget_authority_v1"
                    ),
                    (
                        "docs/research/noncert_cuts_ab16_20260724/"
                        "ab16_budget_authority_v1.py"
                    ),
                ),
                (
                    "ab16_outer_guardian_v1",
                    (
                        "docs.research.noncert_cuts_ab16_20260724."
                        "ab16_outer_guardian_v1"
                    ),
                    (
                        "docs/research/noncert_cuts_ab16_20260724/"
                        "ab16_outer_guardian_v1.py"
                    ),
                ),
            ),
        )
        expected_peer = broker_module.process_identity()
        broker_grant = worker_session["broker_grant"]
        credential = worker_session["credential"]
        if (
            set(broker_grant)
            != {
                "allocation_identity",
                "arm_slot",
                "credential_sha256",
                "expected_peer",
                "role",
                "schema_version",
                "selection_identity",
            }
            or broker_grant["schema_version"]
            != broker_module.SESSION_GRANT_SCHEMA
            or broker_grant["role"] != "formal-worker"
            or broker_grant["expected_peer"] != expected_peer
            or broker_grant["arm_slot"] is not None
            or broker_grant["selection_identity"] is not None
            or broker_grant["allocation_identity"] is not None
            or broker_grant["credential_sha256"]
            != hashlib.sha256(credential.encode("ascii")).hexdigest()
        ):
            raise FormalControllerError(
                "formal worker grant differs from the live selected child"
            )
        runtime = manager_grant["formal_budget_runtime"]
        actor = {
            "schema_version": broker_module.ACTOR_SCHEMA,
            **runtime["broker_actor_identity"],
        }
        transferred_fd = owned_fd
        owned_fd = -1
        client = broker_module.attach_registered_nonarm_session(
            transferred_fd,
            broker_actor=actor,
            broker_nonce=runtime["broker_nonce"],
            credential=credential,
            role="formal-worker",
            native_helper=native_budget_helper,
        )
        (
            formal_root,
            budget_profile,
            all_artifacts,
            all_channels,
            all_directories,
        ) = _formal_budget_tables(inputs)
        calibration_bundle, calibration_bundle_identity = (
            _formal_resource_calibration_bundle(inputs)
        )
        labels = FORMAL_WORKER_LABELS[worker_role]
        fixed_artifacts = {
            label: all_artifacts[label]
            for label in labels
            if label in all_artifacts
        }
        if set(fixed_artifacts) != set(labels):
            raise FormalControllerError(
                f"{worker_role} fixed artifact cohort is incomplete"
            )
        return broker_module.BrokerProcessFormalBudgetBackend(
            broker_client=client,
            native_helper=native_budget_helper,
            formal_root=formal_root,
            enforced_budget_profile=budget_profile,
            resource_calibration_authorization_bundle=(
                calibration_bundle
            ),
            resource_calibration_authorization_bundle_identity=(
                calibration_bundle_identity
            ),
            expected_calibration_tool_identities=(
                _formal_calibration_tool_content_identities(inputs)
            ),
            authority_binding={
                "budget_profile_identity": manager_grant[
                    "budget_profile_identity"
                ],
                "filesystem_write_confinement": (
                    "landlock-read-only-worker-v1"
                ),
                "formal_budget_runtime": runtime,
                "formal_root_contract_identity": manager_grant[
                    "formal_root_contract_identity"
                ],
                "formal_resource_calibration_bundle_identity": manager_grant[
                    "formal_resource_calibration_bundle_identity"
                ],
                "selected_fd_transport": manager_grant[
                    "selected_fd_transport"
                ],
                "worker_role": worker_role,
            },
            fixed_artifacts=fixed_artifacts,
            fixed_channels=(
                all_channels
                if worker_role == "baseline-rebuild"
                else {}
            ),
            fixed_directories=(
                all_directories
                if worker_role == "baseline-rebuild"
                else {}
            ),
            require_worker_confinement=True,
        )
    except BaseException as exc:
        try:
            if client is not None:
                client.close()
            elif owned_fd >= 0:
                os.close(owned_fd)
        except BaseException as cleanup_error:
            exc.add_note(
                "formal worker factory cleanup failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )
        raise


def _selected_role_template(inputs: FormalInputs) -> tuple[str, str, dict[str, Any]]:
    argv = inputs.selection["outer_spec"]["selected_byte_argv"]
    if (
        type(argv) is not list
        or len(argv) < 7
        or argv[1:4] != ["-I", "-B", "-c"]
        or argv[5] != "systemd-openfile"
    ):
        raise FormalControllerError("selected-byte outer argv is not the fixed three-FD form")
    try:
        identities = json.loads(argv[6])
    except (TypeError, json.JSONDecodeError) as exc:
        raise FormalControllerError("selected-byte identity JSON is invalid") from exc
    if type(identities) is not dict or set(identities) != {"authority", "loader", "python"}:
        raise FormalControllerError("selected-byte identity field set drifted")
    for role, identity in identities.items():
        if (
            type(identity) is not dict
            or set(identity) != {"mode", "path", "sha256", "size_bytes"}
            or type(identity["mode"]) is not int
            or type(identity["path"]) is not str
            or not Path(identity["path"]).is_absolute()
            or type(identity["sha256"]) is not str
            or SHA256_RE.fullmatch(identity["sha256"]) is None
            or type(identity["size_bytes"]) is not int
            or identity["size_bytes"] <= 0
        ):
            raise FormalControllerError(f"selected-byte {role} identity is malformed")
    if argv[0] != "/proc/self/fd/3":
        raise FormalControllerError("selected-byte Python executable is not fixed FD3")
    return argv[4], argv[6], identities


def _open_selected(identity: Mapping[str, Any], label: str) -> int:
    descriptor = os.open(
        identity["path"],
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != identity["mode"]
            or metadata.st_size != identity["size_bytes"]
        ):
            raise FormalControllerError(f"selected-byte {label} metadata drifted")
        current = os.stat(identity["path"], follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise FormalControllerError(f"selected-byte {label} path/FD drifted")
        digest = hashlib.sha256()
        offset = 0
        while offset < metadata.st_size:
            block = os.pread(descriptor, min(1 << 20, metadata.st_size - offset), offset)
            if not block:
                raise FormalControllerError(f"selected-byte {label} was truncated")
            digest.update(block)
            offset += len(block)
        if os.pread(descriptor, 1, metadata.st_size):
            raise FormalControllerError(f"selected-byte {label} grew during replay")
        replayed = os.fstat(descriptor)
        if (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            metadata.st_nlink,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        ) != (
            replayed.st_dev,
            replayed.st_ino,
            replayed.st_mode,
            replayed.st_nlink,
            replayed.st_size,
            replayed.st_mtime_ns,
            replayed.st_ctime_ns,
        ):
            raise FormalControllerError(f"selected-byte {label} changed during replay")
        if digest.hexdigest() != identity["sha256"]:
            raise FormalControllerError(f"selected-byte {label} SHA-256 drifted")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_selected_transport_member(
    transport: Mapping[str, object],
    *,
    role: str,
    broker_module: ModuleType,
) -> int:
    owner = transport["owner"]
    roles = transport["roles"]
    if type(owner) is not dict or type(roles) is not dict:
        raise FormalControllerError(
            "selected-FD transport owner/roles are invalid"
        )
    item = roles.get(role)
    if type(item) is not dict:
        raise FormalControllerError(
            f"selected-FD transport lacks role {role}"
        )
    pid = owner["pid"]
    descriptor_number = item["descriptor"]
    expected_path = f"/proc/{pid}/fd/{descriptor_number}"
    if (
        item["proc_fd_path"] != expected_path
        or broker_module.process_starttime(pid)
        != owner["pid_starttime"]
    ):
        raise FormalControllerError(
            f"selected-FD transport {role} owner drifted"
        )
    descriptor = os.open(
        expected_path,
        os.O_RDONLY | os.O_CLOEXEC,
    )
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) != item["mode"]
            or before.st_size != item["size_bytes"]
        ):
            raise FormalControllerError(
                f"selected-FD transport {role} metadata drifted"
            )
        digest = hashlib.sha256()
        offset = 0
        while offset < before.st_size:
            block = os.pread(
                descriptor,
                min(1 << 20, before.st_size - offset),
                offset,
            )
            if not block:
                raise FormalControllerError(
                    f"selected-FD transport {role} ended early"
                )
            digest.update(block)
            offset += len(block)
        after = os.fstat(descriptor)
        stable = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if (
            any(
                getattr(before, field) != getattr(after, field)
                for field in stable
            )
            or digest.hexdigest() != item["sha256"]
            or broker_module.process_starttime(pid)
            != owner["pid_starttime"]
        ):
            raise FormalControllerError(
                f"selected-FD transport {role} bytes drifted"
            )
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _connect_exact_broker_endpoint(
    *,
    broker_module: ModuleType,
    runtime: Mapping[str, object],
) -> socket.socket:
    endpoint = runtime["broker_endpoint_identity"]
    if type(endpoint) is not dict:
        raise FormalControllerError(
            "formal broker endpoint identity is absent"
        )
    path = Path(str(endpoint["path"]))
    parent_fd = broker_module._open_absolute_directory_no_symlinks(  # noqa: SLF001
        path.parent
    )
    connection = socket.socket(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
    )
    try:
        before = os.stat(
            path.name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        expected = (
            endpoint["device"],
            endpoint["inode"],
            endpoint["mode"],
            endpoint["uid"],
        )
        if (
            not stat.S_ISSOCK(before.st_mode)
            or (
                before.st_dev,
                before.st_ino,
                stat.S_IMODE(before.st_mode),
                before.st_uid,
            )
            != expected
        ):
            raise FormalControllerError(
                "formal broker endpoint identity drifted before child connect"
            )
        connection.connect(
            f"/proc/self/fd/{parent_fd}/{path.name}"
        )
        after = os.stat(
            path.name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        if (
            after.st_dev,
            after.st_ino,
            stat.S_IMODE(after.st_mode),
            after.st_uid,
        ) != expected:
            raise FormalControllerError(
                "formal broker endpoint drifted during child connect"
            )
        return connection
    except BaseException:
        connection.close()
        raise
    finally:
        os.close(parent_fd)


def _drain_budgeted_child(
    *,
    broker_module: ModuleType,
    budget_backend: BudgetPublicationBackend,
    executable_fds: Mapping[int, int],
    argv_template: Sequence[str],
    timeout_seconds: float,
) -> tuple[int, bytes, bytes]:
    """Fork, pidfd-bind one grant, then let the child connect and exec."""

    if (
        timeout_seconds <= 0
        or set(executable_fds) != {3, 4, 5, 6, 7}
        or argv_template.count("__AB16_FORMAL_WORKER_SESSION__") != 1
    ):
        raise FormalControllerError(
            "budgeted selected-child launch template is invalid"
        )
    stdout_read, stdout_write = os.pipe2(
        os.O_CLOEXEC | os.O_NONBLOCK
    )
    stderr_read, stderr_write = os.pipe2(
        os.O_CLOEXEC | os.O_NONBLOCK
    )
    parent_control, child_control = socket.socketpair(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
    )
    pid = os.fork()
    if pid == 0:
        parent_control.close()
        try:
            os.close(stdout_read)
            os.close(stderr_read)
            frame = broker_module.receive_frame(child_control)
            session = frame.record
            connection = _connect_exact_broker_endpoint(
                broker_module=broker_module,
                runtime=budget_backend.formal_budget_runtime,
            )
            source_high: dict[int, int] = {}
            try:
                for target, source in executable_fds.items():
                    source_high[target] = fcntl.fcntl(
                        source,
                        fcntl.F_DUPFD_CLOEXEC,
                        20,
                    )
                broker_high = fcntl.fcntl(
                    connection.fileno(),
                    fcntl.F_DUPFD_CLOEXEC,
                    20,
                )
                for target, source in source_high.items():
                    os.dup2(source, target, inheritable=True)
                os.dup2(broker_high, 8, inheritable=True)
                os.dup2(stdout_write, 1, inheritable=True)
                os.dup2(stderr_write, 2, inheritable=True)
            finally:
                connection.close()
            session_json = authority.canonical_json(session).decode(
                "utf-8"
            )
            argv = [
                session_json
                if item == "__AB16_FORMAL_WORKER_SESSION__"
                else item
                for item in argv_template
            ]
            child_control.close()
            broker_module.close_unlisted_descriptors(
                set(range(0, 9))
            )
            os.execve("/proc/self/fd/3", argv, {})
        except BaseException as exc:
            try:
                os.write(
                    2,
                    (
                        "FAIL_CLOSED: selected child setup failed: "
                        f"{type(exc).__name__}: {exc}\n"
                    ).encode("utf-8", "replace"),
                )
            except BaseException:
                pass
        os._exit(125)
    child_control.close()
    os.close(stdout_write)
    os.close(stderr_write)
    pidfd = -1
    status: int | None = None
    try:
        pidfd, _pidfd_method = broker_module.open_pidfd(pid)
        expected_peer = {
            "pid": pid,
            "pid_starttime": broker_module.process_starttime(pid),
            "uid": os.getuid(),
        }
        credential = secrets.token_hex(32)
        broker_grant = dict(
            budget_backend.register_formal_worker_grant(
                credential=credential,
                expected_peer=expected_peer,
                pidfd=pidfd,
            )
        )
        session = {
            "broker_grant": broker_grant,
            "credential": credential,
            "schema_version": FORMAL_WORKER_SESSION_SCHEMA,
        }
        broker_module.send_frame(parent_control, session)
        parent_control.close()

        selector = selectors.DefaultSelector()
        selector.register(stdout_read, selectors.EVENT_READ, "stdout")
        selector.register(stderr_read, selectors.EVENT_READ, "stderr")
        output = {"stdout": bytearray(), "stderr": bytearray()}
        deadline = time.monotonic() + timeout_seconds
        try:
            while selector.get_map() or status is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    os.kill(pid, signal.SIGKILL)
                    os.waitpid(pid, 0)
                    status = 0
                    raise FormalControllerError(
                        "budgeted selected child exceeded its fixed deadline"
                    )
                for key, _event in selector.select(
                    min(0.25, remaining)
                ):
                    block = os.read(key.fd, 64 * 1024)
                    if block:
                        target = output[str(key.data)]
                        target.extend(block)
                        if len(target) > MAX_ROLE_OUTPUT_BYTES:
                            os.kill(pid, signal.SIGKILL)
                            os.waitpid(pid, 0)
                            status = 0
                            raise FormalControllerError(
                                "budgeted selected child output exceeded its fixed limit"
                            )
                    else:
                        selector.unregister(key.fd)
                        os.close(key.fd)
                if status is None:
                    observed_pid, observed_status = os.waitpid(
                        pid,
                        os.WNOHANG,
                    )
                    if observed_pid == pid:
                        status = observed_status
            assert status is not None
            return (
                os.waitstatus_to_exitcode(status),
                bytes(output["stdout"]),
                bytes(output["stderr"]),
            )
        finally:
            for key in list(selector.get_map().values()):
                selector.unregister(key.fd)
                os.close(key.fd)
            selector.close()
    except BaseException:
        try:
            parent_control.close()
        except BaseException:
            pass
        if status is None:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass
        raise
    finally:
        if pidfd >= 0:
            os.close(pidfd)
        for descriptor in (stdout_read, stderr_read):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _drain_spawn(
    *,
    executable_fds: Mapping[int, int],
    argv: Sequence[str],
    timeout_seconds: float,
) -> tuple[int, bytes, bytes]:
    """posix_spawn with exact FD3/4/5 and bounded captured output."""

    if timeout_seconds <= 0:
        raise FormalControllerError("selected role timeout is not positive")
    stdout_read, stdout_write = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
    stderr_read, stderr_write = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
    high_fds: dict[int, int] = {}
    try:
        for target, source in executable_fds.items():
            high_fds[target] = fcntl.fcntl(source, fcntl.F_DUPFD_CLOEXEC, 20)
        actions: list[tuple[Any, ...]] = [
            (os.POSIX_SPAWN_DUP2, high_fds[3], 3),
            (os.POSIX_SPAWN_DUP2, high_fds[4], 4),
            (os.POSIX_SPAWN_DUP2, high_fds[5], 5),
            (os.POSIX_SPAWN_DUP2, stdout_write, 1),
            (os.POSIX_SPAWN_DUP2, stderr_write, 2),
            (os.POSIX_SPAWN_CLOSE, stdout_read),
            (os.POSIX_SPAWN_CLOSE, stderr_read),
        ]
        pid = os.posix_spawn(
            "/proc/self/fd/3",
            list(argv),
            {},
            file_actions=actions,
        )
    finally:
        for descriptor in high_fds.values():
            os.close(descriptor)
        os.close(stdout_write)
        os.close(stderr_write)
    selector = selectors.DefaultSelector()
    selector.register(stdout_read, selectors.EVENT_READ, "stdout")
    selector.register(stderr_read, selectors.EVENT_READ, "stderr")
    output = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + timeout_seconds
    status: int | None = None
    try:
        while selector.get_map() or status is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
                raise FormalControllerError("selected role exceeded its fixed deadline")
            for key, _event in selector.select(min(0.25, remaining)):
                block = os.read(key.fd, 64 * 1024)
                if block:
                    target = output[str(key.data)]
                    target.extend(block)
                    if len(target) > MAX_ROLE_OUTPUT_BYTES:
                        os.kill(pid, signal.SIGKILL)
                        os.waitpid(pid, 0)
                        raise FormalControllerError("selected role output exceeded its fixed limit")
                else:
                    selector.unregister(key.fd)
                    os.close(key.fd)
            if status is None:
                observed_pid, observed_status = os.waitpid(pid, os.WNOHANG)
                if observed_pid == pid:
                    status = observed_status
        if status is None:
            raise FormalControllerError("selected role terminal status is absent")
        return os.waitstatus_to_exitcode(status), bytes(output["stdout"]), bytes(output["stderr"])
    finally:
        for key in list(selector.get_map().values()):
            selector.unregister(key.fd)
            os.close(key.fd)
        selector.close()


def _budgeted_worker_argv(
    inputs: FormalInputs,
    *,
    role: str,
    role_argv: Sequence[str],
) -> list[str]:
    if role not in FORMAL_WORKER_LABELS:
        raise FormalControllerError(
            "selected budget worker role is outside the fixed cohort"
        )
    raw = inputs.selection["outer_spec"]["selected_byte_argv"]
    if (
        type(raw) is not list
        or len(raw) < 12
        or raw[0:6]
        != [
            "/proc/self/fd/3",
            "-I",
            "-B",
            "-c",
            raw[4],
            "systemd-openfile",
        ]
    ):
        raise FormalControllerError(
            "formal controller selected-byte template drifted"
        )
    command = list(raw)
    command[5] = "direct"
    try:
        role_index = command.index("--role")
        delimiter = command.index("--")
    except ValueError as exc:
        raise FormalControllerError(
            "formal controller selected-byte options are incomplete"
        ) from exc
    if (
        role_index + 1 >= delimiter
        or command[role_index + 1] != "formal-controller"
    ):
        raise FormalControllerError(
            "formal controller selected-byte role drifted"
        )
    command[role_index + 1] = role
    selection_path = str(inputs.selection_identity["path"])
    if "--formal-worker-session-json" in command[:delimiter]:
        raise FormalControllerError(
            "selected-byte template already contains a worker session"
        )
    if "--formal-selection-for-budget" in command[:delimiter]:
        selection_index = command.index(
            "--formal-selection-for-budget"
        )
        if (
            selection_index + 1 >= delimiter
            or command[selection_index + 1] != selection_path
        ):
            raise FormalControllerError(
                "selected-byte budget selection path drifted"
            )
        added = [
            "--formal-worker-session-json",
            "__AB16_FORMAL_WORKER_SESSION__",
        ]
    else:
        added = [
            "--formal-selection-for-budget",
            selection_path,
            "--formal-worker-session-json",
            "__AB16_FORMAL_WORKER_SESSION__",
        ]
    command[delimiter:delimiter] = [
        *added,
    ]
    delimiter += len(added)
    command[delimiter + 1 :] = list(role_argv)
    return command


class DefaultControllerPorts:
    """Live adapters composed only from package-pinned existing owners."""

    def __init__(
        self,
        inputs: FormalInputs,
        *,
        budget_backend: BudgetPublicationBackend,
    ) -> None:
        self.inputs = inputs
        self.budget_backend = budget_backend
        if Path.cwd().resolve(strict=False) != Path(str(inputs.context["snapshot_root"])).resolve(strict=False):
            raise FormalControllerError("controller cwd is not the sealed snapshot root")
        try:
            campaign_context = authority._campaign_context(inputs.context["campaign_dir"])  # noqa: SLF001
            preregistration, _identity_value = authority._path_preregistration(  # noqa: SLF001
                campaign_context
            )
        except Exception as exc:
            raise FormalControllerError(f"campaign boundary replay failed: {exc}") from exc
        self.campaign_context = campaign_context
        self.preregistration = preregistration
        self._broker_module = _import_snapshot_owner(
            inputs,
            module_name=BUDGET_BROKER_MODULE,
            relative=BUDGET_BROKER_RELATIVE,
            aliases=(
                (
                    "ab16_budget_authority_v1",
                    (
                        "docs.research.noncert_cuts_ab16_20260724."
                        "ab16_budget_authority_v1"
                    ),
                    (
                        "docs/research/noncert_cuts_ab16_20260724/"
                        "ab16_budget_authority_v1.py"
                    ),
                ),
                (
                    "ab16_outer_guardian_v1",
                    (
                        "docs.research.noncert_cuts_ab16_20260724."
                        "ab16_outer_guardian_v1"
                    ),
                    (
                        "docs/research/noncert_cuts_ab16_20260724/"
                        "ab16_outer_guardian_v1.py"
                    ),
                ),
            ),
        )
        self._helper: ModuleType | None = None
        self._store: Any = None
        (
            receipt_formal_root,
            _receipt_budget_profile,
            receipt_fixed_artifacts,
            _receipt_fixed_channels,
            _receipt_fixed_directories,
        ) = _formal_budget_tables(inputs)
        self._receipt_budget_bindings = {
            str(
                (
                    receipt_formal_root
                    / cast(str, specification["relative_path"])
                ).absolute()
            ): {
                "artifact_class": specification["artifact_class"],
                "label": label,
            }
            for label, specification in receipt_fixed_artifacts.items()
        }
        try:
            bound_selection = self.budget_backend.bind_formal_selection(
                inputs.selection_identity
            )
        except Exception as exc:
            raise FormalControllerError(
                "formal selection could not be bound to the persistent budget broker"
            ) from exc
        if bound_selection != {
            "selection_identity": inputs.selection_identity
        }:
            raise FormalControllerError(
                "persistent budget broker selection receipt drifted"
            )

    def wait_for_barrier(self, inputs: FormalInputs) -> tuple[dict[str, object], dict[str, object]]:
        path = Path(str(inputs.selection["outer_spec"]["barrier_path"]))
        record, identity = _wait_for_record(
            path,
            timeout_seconds=600.0,
            label="outer barrier",
        )
        return validate_outer_barrier(record, inputs=inputs), identity

    def run_gate1(self, inputs: FormalInputs) -> Mapping[str, object]:
        module = _import_snapshot_owner(
            inputs,
            module_name=(
                "docs.research.noncert_cuts_ab_trust_gate1_v4_20260724."
                "gate1_campaign_execution_v4"
            ),
            relative=(
                "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724/"
                "gate1_campaign_execution_v4.py"
            ),
            aliases=(
                (
                    "campaign_authority_v4",
                    (
                        "docs.research.noncert_cuts_ab_trust_gate1_v4_20260724."
                        "campaign_authority_v4"
                    ),
                    (
                        "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724/"
                        "campaign_authority_v4.py"
                    ),
                ),
            ),
        )
        root_identity = inputs.context["campaign_root_identity"]
        gate1_identity = inputs.context["gate1_selection_identity"]
        prepared = module.prepare_formal_positive_pair(
            campaign_root_identity=root_identity,
            selection_identity=gate1_identity,
            formal_authorized=True,
        )
        if prepared.get("mode") != module.FORMAL or prepared.get("formal_publication_authorized") is not True:
            raise FormalControllerError("Gate1 formal preparation did not authorize its fixed publication")
        units = module.orchestrate_gate1_units(
            campaign_root_identity=root_identity,
            selection_identity=gate1_identity,
            mode=module.FORMAL,
            formal_authorized=True,
        )
        if type(units) is not dict or list(units) != list(GATE1_SLOTS):
            raise FormalControllerError("Gate1 unit result order drifted")
        assembled = module.assemble_and_publish_formal_gate(
            campaign_root_identity=root_identity,
            selection_identity=gate1_identity,
            formal_authorized=True,
        )
        if (
            assembled.get("mode") != module.FORMAL
            or assembled.get("gate_written") is not True
            or assembled.get("continuation_written") is not True
            or assembled.get("organic_arm_launch_authorized") is not False
        ):
            raise FormalControllerError("Gate1 formal result crossed its authority boundary")
        return {
            "gate_identity": _identity(assembled.get("gate_identity"), "Gate1 gate"),
            "continuation_identity": _identity(
                assembled.get("continuation_identity"),
                "Gate1 continuation",
            ),
            "unit_order": list(units),
        }

    def run_selected_role(
        self,
        inputs: FormalInputs,
        *,
        role: str,
        argv: Sequence[str],
        timeout_seconds: float,
    ) -> SelectedRoleResult:
        transport = self.budget_backend.selected_fd_transport
        roles = {
            3: "python",
            4: "loader",
            5: "authority",
            6: "native_helper_wrapper",
            7: "native_helper",
        }
        opened: dict[int, int] = {}
        try:
            for target, transport_role in roles.items():
                opened[target] = _open_selected_transport_member(
                    transport,
                    role=transport_role,
                    broker_module=self._broker_module,
                )
            command = _budgeted_worker_argv(
                inputs,
                role=role,
                role_argv=argv,
            )
            returncode, stdout, stderr = _drain_budgeted_child(
                broker_module=self._broker_module,
                budget_backend=self.budget_backend,
                executable_fds=opened,
                argv_template=command,
                timeout_seconds=timeout_seconds,
            )
        finally:
            for descriptor in opened.values():
                os.close(descriptor)
        result = SelectedRoleResult(
            role=role,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )
        if returncode != 0 or stderr:
            raise FormalControllerError(
                f"selected role {role} failed: exit={returncode}, stderr={stderr!r}"
            )
        return result

    def run_baseline_chain(self, inputs: FormalInputs) -> Mapping[str, object]:
        return _run_baseline_chain(inputs, ports=self)

    def _outer_helper(self) -> tuple[ModuleType, Any, Any]:
        if self._helper is None:
            self._helper = _import_snapshot_owner(
                self.inputs,
                module_name=(
                    "docs.research.noncert_cuts_ab16_20260724."
                    "ab16_outer_refunit_closeout_v1"
                ),
                relative=(
                    "docs/research/noncert_cuts_ab16_20260724/"
                    "ab16_outer_refunit_closeout_v1.py"
                ),
            )
            self._store = self._helper.ReceiptStore(
                budget_backend=self.budget_backend,
                budget_bindings=self._receipt_budget_bindings,
            )
        boundary = SimpleNamespace(
            campaign=Path(str(self.inputs.context["campaign_dir"])),
            context=self.campaign_context,
            formal_dir=Path(str(self.inputs.context["formal_attempt_dir"])),
            preregistration=self.preregistration,
            root=self.campaign_context["root"],
        )
        return self._helper, self._store, boundary

    def publish_arm_prelaunch_request(
        self,
        inputs: FormalInputs,
        *,
        slot: str,
        ordinal: int,
    ) -> dict[str, object]:
        helper, store, boundary = self._outer_helper()
        record = helper.build_arm_prelaunch_request(
            boundary,
            store,
            inputs.selection_identity,
            slot,
            ordinal,
        )
        path = inputs.selection["arm_prelaunch_paths"][slot]["request"]
        return store.publish(path, record, f"{slot} prelaunch request")

    def wait_for_arm_prelaunch_receipt(
        self,
        inputs: FormalInputs,
        *,
        slot: str,
        ordinal: int,
        request_identity: Mapping[str, object],
    ) -> dict[str, object]:
        helper, store, boundary = self._outer_helper()
        request_path = inputs.selection["arm_prelaunch_paths"][slot]["request"]
        request, observed_request_identity = store.document(
            request_path,
            f"{slot} prelaunch request",
        )
        if observed_request_identity != dict(request_identity):
            raise FormalControllerError(f"{slot} prelaunch request identity drifted")
        receipt_path = Path(inputs.selection["arm_prelaunch_paths"][slot]["receipt"])
        _wait_for_record(
            receipt_path,
            timeout_seconds=300.0,
            label=f"{slot} prelaunch receipt",
        )
        try:
            receipt, receipt_identity = helper.validate_arm_prelaunch_receipt(
                boundary,
                store,
                request,
                observed_request_identity,
                receipt_path,
                expected_allowed_same_uid_processes=[
                    inputs.supervisor_process_identity,
                    inputs.guardian_process_identity
                ],
                expected_resource_observation_context=(
                    _arm_resource_observation_context(
                        inputs,
                        slot=slot,
                        ordinal=ordinal,
                    )
                ),
            )
        except Exception as exc:
            raise FormalControllerError(f"{slot} prelaunch receipt failed: {exc}") from exc
        if slot != ARM_SEQUENCE[ordinal - 1]:
            raise FormalControllerError("prelaunch receipt order drifted")
        resource_receipt = receipt.get("resource_admission")
        if type(resource_receipt) is not dict:
            raise FormalControllerError(
                f"{slot} prelaunch resource admission is absent"
            )
        return {
            "receipt_identity": receipt_identity,
            "resource_admission": dict(resource_receipt),
        }

    def prepare_arm_budget(
        self,
        inputs: FormalInputs,
        *,
        slot: str,
    ) -> tuple[Mapping[str, object], BudgetPublicationBackend]:
        profile = self.budget_backend.enforced_budget_profile
        formal = profile.get("formal_root")
        allocations = (
            formal.get("arm_allocations")
            if type(formal) is dict
            else None
        )
        if (
            type(allocations) is not dict
            or type(allocations.get(slot)) is not dict
        ):
            raise FormalControllerError(
                f"{slot} lacks its exact profile allocation"
            )
        try:
            allocation = self.budget_backend.allocate_arm(
                arm_slot=slot,
                category_limits=allocations[slot],
            )
            (
                formal_root,
                attempt_root,
                fixed_maxima,
                channel_contracts,
                layout,
            ) = _arm_budget_profile_tables(
                inputs,
                slot=slot,
                allocation=allocation,
            )
        except Exception as exc:
            raise FormalControllerError(
                f"{slot} broker allocation failed closed"
            ) from exc
        allocation_identity = cast(
            Mapping[str, object],
            layout["allocation_identity"],
        )
        formal_grant = inputs.selection.get("manager_openfile_grant")
        if type(formal_grant) is not dict:
            raise FormalControllerError(
                f"{slot} formal selection lacks its manager grant"
            )
        context = authority._campaign_context(  # noqa: SLF001
            inputs.context["campaign_dir"]
        )
        continuation, _continuation_identity = authority._continuation(  # noqa: SLF001
            context
        )
        manifest, _manifest_snapshot = authority._read_organic_manifest(  # noqa: SLF001
            context,
            continuation=continuation,
        )
        unit_names = manifest.get("unit_names")
        if (
            type(unit_names) is not dict
            or type(unit_names.get(slot)) is not str
        ):
            raise FormalControllerError(
                f"{slot} organic unit name is absent"
            )
        arm_manager_credential = secrets.token_hex(32)
        try:
            arm_manager_preregistration = (
                self.budget_backend.preregister_manager_openfile_arm_grant(
                    allocation_identity=allocation_identity,
                    arm_slot=slot,
                    attempt_consumption_identity=formal_grant[
                        "attempt_consumption_identity"
                    ],
                    credential=arm_manager_credential,
                    manager_epoch_identity=formal_grant[
                        "manager_epoch_identity"
                    ],
                    selection_identity=inputs.selection_identity,
                    unit_name=cast(str, unit_names[slot]),
                )
            )
        except Exception as exc:
            raise FormalControllerError(
                f"{slot} manager OpenFile arm grant preregistration failed closed"
            ) from exc
        credential = secrets.token_hex(32)
        pidfd, _pidfd_method = self._broker_module.open_pidfd(
            os.getpid()
        )
        arm_client: Any | None = None
        try:
            expected_peer = self._broker_module.process_identity()
            grant = self.budget_backend.register_bound_arm_grant(
                credential=credential,
                expected_peer=expected_peer,
                pidfd=pidfd,
                role="arm-authority",
                arm_slot=slot,
                selection_identity=inputs.selection_identity,
                allocation_identity=allocation_identity,
            )
            arm_client = self.budget_backend.connect_registered_arm(
                credential=credential,
                role="arm-authority",
                arm_slot=slot,
                selection_identity=inputs.selection_identity,
                allocation_identity=allocation_identity,
            )
        except BaseException:
            if arm_client is not None:
                arm_client.close()
            raise
        finally:
            os.close(pidfd)
        runtime = self.budget_backend.formal_budget_runtime
        contract_identity = runtime["formal_root_contract_identity"]
        contract_mode = stat.S_IMODE(
            os.stat(
                cast(str, contract_identity["path"]),
                follow_symlinks=False,
            ).st_mode
        )
        native_role = self.budget_backend.selected_fd_transport[
            "roles"
        ]["native_helper"]
        handoff = {
            "arm_allocation_id": allocation_identity["sha256"],
            "broker_actor_identity": dict(
                runtime["broker_actor_identity"]
            ),
            "broker_nonce": runtime["broker_nonce"],
            "broker_socket_path": runtime[
                "broker_endpoint_identity"
            ]["path"],
            "calibration_tool_content_identities": {
                role: dict(identity)
                for role, identity in sorted(
                    self.budget_backend.expected_calibration_tool_identities.items()
                )
            },
            "fixed_directory_layout": {
                "attempt_root": str(attempt_root),
                "channel_contracts": channel_contracts,
                "directories": layout["directories"],
                "formal_root": str(formal_root),
            },
            "fixed_maxima": fixed_maxima,
            "formal_budget_authority_identity": {
                "mode": contract_mode,
                **contract_identity,
            },
            "manager_openfile_arm_grant": {
                "credential": arm_manager_credential,
                "preregistration": dict(
                    arm_manager_preregistration
                ),
            },
            "native_helper_package_identity": {
                "mode": native_role["mode"],
                "path": native_role["proc_fd_path"],
                "sha256": native_role["sha256"],
                "size_bytes": native_role["size_bytes"],
            },
        }
        runner_module = _import_snapshot_owner(
            inputs,
            module_name=(
                "docs.research.noncert_cuts_ab16_20260724."
                "organic_arm_runner_v1"
            ),
            relative=(
                "docs/research/noncert_cuts_ab16_20260724/"
                "organic_arm_runner_v1.py"
            ),
        )
        try:
            arm_backend = runner_module.BrokerProcessArmBudgetBackend(
                broker_client=arm_client,
                native_helper=self.budget_backend.native_helper,
                formal_root=formal_root,
                attempt_root=attempt_root,
                formal_budget_runtime=runtime,
                enforced_budget_profile=(
                    self.budget_backend.enforced_budget_profile
                ),
                enforced_budget_profile_identity=(
                    self.budget_backend.enforced_budget_profile_identity
                ),
                resource_calibration_authorization_bundle=(
                    self.budget_backend.resource_calibration_authorization_bundle
                ),
                resource_calibration_authorization_bundle_identity=(
                    self.budget_backend.resource_calibration_authorization_bundle_identity
                ),
                expected_calibration_tool_identities=(
                    self.budget_backend.expected_calibration_tool_identities
                ),
                authority_binding={
                    "arm_allocation_identity": dict(
                        allocation_identity
                    ),
                    "arm_allocation_id": allocation_identity[
                        "sha256"
                    ],
                    "arm_slot": slot,
                    "broker_nonce": runtime["broker_nonce"],
                    "broker_socket_fd": arm_client.connection.fileno(),
                    "filesystem_write_confinement": (
                        "not-applicable-persistent-supervisor-v1"
                    ),
                    "formal_budget_authority_identity": {
                        "mode": contract_mode,
                        **contract_identity,
                    },
                    "next_sequence": arm_client.sequence + 1,
                },
                fixed_maxima=fixed_maxima,
                channel_contracts=channel_contracts,
                manager_openfile_arm_grant=handoff[
                    "manager_openfile_arm_grant"
                ],
                guardian_ready_identity=inputs.selection[
                    "guardian_ready_identity"
                ],
                pidfd_opener=self._broker_module.open_pidfd,
            )
        except BaseException:
            arm_client.close()
            raise
        if grant.get("role") != "arm-authority":
            arm_backend.close()
            raise FormalControllerError(
                f"{slot} arm-authority grant role drifted"
            )
        return handoff, cast(BudgetPublicationBackend, arm_backend)

    def run_organic_arm(
        self,
        inputs: FormalInputs,
        *,
        arm_budget_backend: BudgetPublicationBackend,
        pre_run_path: Path,
        resource_admission_receipt: Mapping[str, object],
        selection_path: Path,
    ) -> Mapping[str, object]:
        module = _import_snapshot_owner(
            inputs,
            module_name=(
                "docs.research.noncert_cuts_ab16_20260724."
                "organic_unit_orchestrator_v2"
            ),
            relative=(
                "docs/research/noncert_cuts_ab16_20260724/"
                "organic_unit_orchestrator_v2.py"
            ),
        )
        return module.run_pinned_entry(
            execution_class="FORMAL_AB16",
            pre_run_path=pre_run_path,
            resource_admission_receipt=resource_admission_receipt,
            selection_path=selection_path,
            budget_backend=arm_budget_backend,
        )


def _baseline_paths(ports: DefaultControllerPorts, prepared: Mapping[str, object]) -> dict[str, Path]:
    baseline_dir = Path(str(prepared["baseline_dir"]))
    prospective = baseline_dir.parent
    expected = {
        "admission": Path(ports.preregistration["baseline_admission_path"]),
        "fixed_replay": Path(ports.preregistration["baseline_fixed_replay_path"]),
        "incumbent": Path(ports.preregistration["baseline_incumbent_path"]),
        "metadata": Path(ports.preregistration["baseline_rebuilt_metadata_path"]),
        "model": Path(ports.preregistration["baseline_rebuilt_model_path"]),
        "provenance": Path(ports.preregistration["baseline_campaign_provenance_path"]),
    }
    if (
        baseline_dir != prospective / "baseline"
        or expected["provenance"].parent != baseline_dir
        or any(
            not path.is_relative_to(prospective)
            for path in expected.values()
        )
    ):
        raise FormalControllerError("baseline path preregistration drifted")
    return expected


def _run_baseline_chain(
    inputs: FormalInputs,
    *,
    ports: DefaultControllerPorts,
) -> dict[str, object]:
    prepared = authority.prepare_baseline_output(inputs.context["campaign_dir"])
    if prepared.get("status") != "PROVENANCE_ONLY":
        raise FormalControllerError("baseline prestate is not PROVENANCE_ONLY")
    paths = _baseline_paths(ports, prepared)
    snapshot_root = Path(str(inputs.context["snapshot_root"]))
    ports.run_selected_role(
        inputs,
        role="baseline-rebuild",
        argv=(
            "--output-dir",
            str(paths["model"].parent),
            "--run-nonce",
            Path(str(inputs.context["campaign_dir"])).name,
            "--campaign-provenance",
            str(paths["provenance"]),
            "--candidate-placements",
            str(snapshot_root / "data/preprocessed/candidate_placements.json"),
            "--canonical-rules",
            str(snapshot_root / "rules/canonical_rules.json"),
            "--mandatory-instances",
            str(snapshot_root / "data/preprocessed/mandatory_exact_instances.json"),
        ),
        timeout_seconds=55_000.0,
    )
    ports.run_selected_role(
        inputs,
        role="cut-free-incumbent-replay",
        argv=(
            "--campaign-provenance",
            str(paths["provenance"]),
            "--model",
            str(paths["model"]),
            "--metadata",
            str(paths["metadata"]),
            "--incumbent",
            str(paths["incumbent"]),
            "--output",
            str(paths["fixed_replay"]),
            "--max-time-seconds",
            "600",
        ),
        timeout_seconds=1_200.0,
    )
    legacy = ports.campaign_context["root"]["strict_inputs"]["legacy_control_a002"]
    if _snapshot_identity(legacy["path"]) != legacy:
        raise FormalControllerError("legacy control identity drifted before baseline admission")
    ports.run_selected_role(
        inputs,
        role="baseline-admission",
        argv=(
            "--campaign-provenance",
            str(paths["provenance"]),
            "--legacy-control",
            str(legacy["path"]),
            "--rebuilt-model",
            str(paths["model"]),
            "--rebuilt-metadata",
            str(paths["metadata"]),
            "--fixed-assignment-replay",
            str(paths["fixed_replay"]),
            "--created-at-utc",
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "--output",
            str(paths["admission"]),
        ),
        timeout_seconds=600.0,
    )
    return {
        f"{name}_identity": _snapshot_identity(path)
        for name, path in paths.items()
    }


def _close_and_consume_prepared_arm(
    inputs: FormalInputs,
    *,
    slot: str,
    ordinal: int,
    prepared: Mapping[str, object],
    arm_budget_backend: BudgetPublicationBackend,
) -> dict[str, object]:
    closure = _import_snapshot_owner(
        inputs,
        module_name=(
            "docs.research.noncert_cuts_ab16_20260724."
            "ab16_arm_attempt_closure_v1"
        ),
        relative=(
            "docs/research/noncert_cuts_ab16_20260724/"
            "ab16_arm_attempt_closure_v1.py"
        ),
    )
    if (
        prepared.get("state") != "PREPARED_NOT_CONSUMED"
        or prepared.get("slot") != slot
        or type(prepared.get("formal_root")) is not str
        or type(prepared.get("arm_attempt_prefix")) is not str
        or type(prepared.get("closure_bindings")) is not dict
    ):
        raise FormalControllerError(
            f"{slot} prepared evidence handoff is invalid"
        )
    formal_root = Path(cast(str, prepared["formal_root"]))
    attempt_prefix = cast(str, prepared["arm_attempt_prefix"])
    expected_path_types = arm_budget_backend.expected_root_path_types()
    try:
        sealed = closure.publish_arm_attempt_manifest(
            formal_root,
            arm_attempt_prefix=attempt_prefix,
            arm_slot=slot,
            bindings=cast(
                Mapping[str, object],
                prepared["closure_bindings"],
            ),
            expected_path_types_before=expected_path_types,
            budget_backend=arm_budget_backend,
        )
    except BaseException as exc:
        raise FormalControllerError(
            f"{slot} arm manifest seal failed or is uncertain"
        ) from exc
    successor = (
        ARM_SEQUENCE[ordinal]
        if ordinal < len(ARM_SEQUENCE)
        else None
    )
    continuation = (
        "next-arm" if successor is not None else "formal-finalize"
    )
    try:
        accepted = arm_budget_backend.accept_prior_arm_seal_response(
            continuation=continuation,
            successor_arm_slot=successor,
        )
    except BaseException as exc:
        raise FormalControllerError(
            f"{slot} arm seal acknowledgement acceptance failed or is uncertain"
        ) from exc
    if (
        type(accepted) is not dict
        or set(accepted) != {"accepted", "journal"}
        or type(accepted["accepted"]) is not dict
        or type(accepted["journal"]) is not dict
        or type(sealed) is not dict
    ):
        raise FormalControllerError(
            f"{slot} arm seal/acceptance evidence shape drifted"
        )
    terminal = sealed.get("arm_budget_terminal")
    terminal_identity = sealed.get("arm_budget_terminal_identity")
    response_authentication = sealed.get(
        "arm_seal_response_authentication"
    )
    manifest_identity = sealed.get("manifest_identity")
    if (
        type(terminal) is not dict
        or type(terminal_identity) is not dict
        or type(response_authentication) is not dict
        or type(manifest_identity) is not dict
        or type(terminal.get("arm_expected_path_types")) is not list
    ):
        raise FormalControllerError(
            f"{slot} arm seal terminal evidence is incomplete"
        )
    replay_path = (
        formal_root / "replays" / "arm-attempt-roots" / f"{slot}.json"
    )
    try:
        replayed = closure.replay_and_publish_arm_attempt_root(
            formal_root,
            arm_attempt_prefix=attempt_prefix,
            arm_slot=slot,
            bindings=cast(
                Mapping[str, object],
                prepared["closure_bindings"],
            ),
            expected_path_types=terminal[
                "arm_expected_path_types"
            ],
            expected_manifest_identity=manifest_identity,
            expected_arm_budget_terminal=terminal,
            expected_arm_budget_terminal_identity=terminal_identity,
            expected_arm_seal_response_authentication=(
                response_authentication
            ),
            prior_response_accepted_result=accepted["accepted"],
            prior_response_accepted_identity=accepted["journal"],
            accepted_continuation=continuation,
            accepted_successor_arm_slot=successor,
            replay_path=replay_path,
            budget_backend=arm_budget_backend,
        )
        closure.verify_published_arm_attempt_replay(
            replay_path,
            expected_replay_identity=replayed["replay_identity"],
            expected_manifest_identity=manifest_identity,
            expected_arm_budget_terminal_identity=terminal_identity,
            expected_arm_seal_response_authentication=(
                response_authentication
            ),
            expected_prior_response_accepted_identity=(
                accepted["journal"]
            ),
            expected_accepted_continuation=continuation,
            expected_accepted_successor_arm_slot=successor,
            arm_attempt_prefix=attempt_prefix,
            arm_slot=slot,
            bindings=cast(
                Mapping[str, object],
                prepared["closure_bindings"],
            ),
        )
    except BaseException as exc:
        raise FormalControllerError(
            f"{slot} sealed arm outside replay failed or is uncertain"
        ) from exc
    arm_closure = {
        "arm_attempt_manifest_identity": dict(manifest_identity),
        "arm_attempt_replay_identity": dict(
            cast(Mapping[str, object], replayed["replay_identity"])
        ),
        "arm_budget_terminal_identity": dict(terminal_identity),
        "prior_response_accepted_identity": dict(
            cast(Mapping[str, object], accepted["journal"])
        ),
        "seal_response_authentication": dict(
            response_authentication
        ),
    }
    try:
        return authority.consume_prepared_arm(
            inputs.context["campaign_dir"],
            slot=slot,
            prepared=prepared,
            arm_closure=arm_closure,
            budget_backend=arm_budget_backend,
        )
    except BaseException as exc:
        raise FormalControllerError(
            f"{slot} post-seal arm consumption failed or is uncertain"
        ) from exc


def _consume_selected_arm_allocated(
    inputs: FormalInputs,
    *,
    ports: ControllerPorts,
    slot: str,
    ordinal: int,
    budget_handoff: Mapping[str, object],
    arm_budget_backend: BudgetPublicationBackend,
) -> dict[str, object]:
    candidate = authority.build_pre_run_candidate(
        inputs.context["campaign_dir"],
        slot=slot,
        budget_handoff=budget_handoff,
        budget_backend=arm_budget_backend,
    )
    if candidate.get("status") != "PASS":
        raise FormalControllerError(f"{slot} pre-run candidate did not PASS")
    selected = authority.create_arm_selection(
        inputs.context["campaign_dir"],
        slot=slot,
        selection_nonce=f"formal-{ordinal:02d}-{slot}",
        budget_backend=arm_budget_backend,
    )
    selection_identity = _identity(
        selected.get("arm_selection_identity"),
        f"{slot} arm selection",
    )
    pre_run_identity = _identity(
        selected.get("pre_run_authority_identity"),
        f"{slot} pre-run authority",
    )
    request_identity: dict[str, object] | None = None
    receipt_identity: dict[str, object] | None = None
    final_resource_admission: dict[str, object] | None = None
    orchestration_error: BaseException | None = None
    try:
        request_identity = ports.publish_arm_prelaunch_request(
            inputs,
            slot=slot,
            ordinal=ordinal,
        )
        prelaunch = ports.wait_for_arm_prelaunch_receipt(
            inputs,
            slot=slot,
            ordinal=ordinal,
            request_identity=request_identity,
        )
        receipt_identity = _identity(
            prelaunch.get("receipt_identity"),
            f"{slot} prelaunch receipt",
        )
        resource_admission_receipt = prelaunch.get("resource_admission")
        if type(resource_admission_receipt) is not dict:
            raise FormalControllerError(
                f"{slot} prelaunch resource admission is absent"
            )
        orchestration_result = ports.run_organic_arm(
            inputs,
            arm_budget_backend=arm_budget_backend,
            pre_run_path=Path(str(pre_run_identity["path"])),
            resource_admission_receipt=resource_admission_receipt,
            selection_path=Path(str(selection_identity["path"])),
        )
        if (
            type(orchestration_result) is not dict
            or set(orchestration_result) != {
                "detached_replay",
                "resource_admission",
            }
        ):
            raise FormalControllerError(
                f"{slot} organic result lacks exact launch resource evidence"
            )
        try:
            final_resource_admission = (
                resource_admission.validate_prospective_launch_resource_reevaluation(
                    orchestration_result["resource_admission"],
                    expected_receipt=resource_admission_receipt,
                    calibration_authorization_bundle=(
                        arm_budget_backend.resource_calibration_authorization_bundle
                    ),
                    calibration_authorization_bundle_identity=(
                        arm_budget_backend.resource_calibration_authorization_bundle_identity
                    ),
                    expected_calibration_tool_identities=(
                        arm_budget_backend.expected_calibration_tool_identities
                    ),
                    enforced_budget_profile=(
                        arm_budget_backend.enforced_budget_profile
                    ),
                    enforced_budget_profile_identity=(
                        arm_budget_backend.enforced_budget_profile_identity
                    ),
                )
            )
        except resource_admission.ResourceAdmissionError as exc:
            raise FormalControllerError(
                f"{slot} launch resource reevaluation failed replay"
            ) from exc
    except BaseException as exc:
        orchestration_error = exc
    try:
        prepared = authority.prepare_arm_consumption_evidence(
            inputs.context["campaign_dir"],
            slot=slot,
            budget_backend=arm_budget_backend,
        )
        consumed = _close_and_consume_prepared_arm(
            inputs,
            slot=slot,
            ordinal=ordinal,
            prepared=prepared,
            arm_budget_backend=arm_budget_backend,
        )
    except BaseException as consumption_error:
        if orchestration_error is not None:
            raise FormalControllerError(
                f"{slot} orchestration and immutable consumption both failed"
            ) from ExceptionGroup(
                f"{slot} post-selection failures",
                [orchestration_error, consumption_error],
            )
        raise FormalControllerError(f"{slot} immutable consumption failed") from consumption_error
    if orchestration_error is not None:
        raise FormalControllerError(f"{slot} selected arm failed after selection") from orchestration_error
    record = consumed.get("consumption")
    if (
        type(record) is not dict
        or record.get("outcome") != "CREDIBLE_TERMINAL"
        or consumed.get("immediate_stop_identity") is not None
    ):
        raise FormalControllerError(f"{slot} did not reach one credible terminal")
    if (
        request_identity is None
        or receipt_identity is None
        or final_resource_admission is None
    ):
        raise FormalControllerError(f"{slot} prelaunch evidence was not recorded")
    return {
        "arm_gate_identity": _identity(record["arm_gate_identity"], f"{slot} arm gate"),
        "consumption_identity": _identity(
            consumed["consumption_identity"],
            f"{slot} consumption",
        ),
        "ordinal": ordinal,
        "pre_run_authority_identity": pre_run_identity,
        "prelaunch_receipt_identity": receipt_identity,
        "prelaunch_request_identity": request_identity,
        "resource_admission": final_resource_admission,
        "resource_terminal_identity": _identity(
            record["resource_terminal_identity"],
            f"{slot} resource terminal",
        ),
        "selection_identity": selection_identity,
        "slot": slot,
        "suite_terminal_identity": (
            None
            if record["suite_terminal_identity"] is None
            else _identity(record["suite_terminal_identity"], "AB16 suite terminal")
        ),
    }


def _consume_selected_arm(
    inputs: FormalInputs,
    *,
    ports: ControllerPorts,
    slot: str,
    ordinal: int,
) -> dict[str, object]:
    try:
        handoff, backend = ports.prepare_arm_budget(
            inputs,
            slot=slot,
        )
    except Exception as exc:
        raise FormalControllerError(
            f"{slot} arm budget allocation failed before selection"
        ) from exc
    primary: BaseException | None = None
    result: dict[str, object] | None = None
    try:
        result = _consume_selected_arm_allocated(
            inputs,
            ports=ports,
            slot=slot,
            ordinal=ordinal,
            budget_handoff=handoff,
            arm_budget_backend=backend,
        )
    except BaseException as exc:
        primary = exc
    try:
        backend.close()
    except BaseException as close_error:
        if primary is None:
            primary = FormalControllerError(
                f"{slot} arm budget session close failed"
            )
            primary.__cause__ = close_error
        else:
            primary.add_note(
                "arm budget session close also failed: "
                f"{type(close_error).__name__}: {close_error}"
            )
    if primary is not None:
        raise primary
    assert result is not None
    return result


def _publish_controller_result(
    inputs: FormalInputs,
    *,
    barrier_identity: Mapping[str, object],
    gate1: Mapping[str, object],
    baseline: Mapping[str, object],
    manifest_identity: Mapping[str, object],
    suite_selection_identity: Mapping[str, object],
    arms: Sequence[Mapping[str, object]],
    budget_backend: BudgetPublicationBackend,
) -> tuple[dict[str, object], dict[str, object]]:
    if len(arms) != len(ARM_SEQUENCE):
        raise FormalControllerError("controller result lacks all sixteen arms")
    terminal_identity = arms[-1]["suite_terminal_identity"]
    if terminal_identity is None:
        raise FormalControllerError("final arm did not publish the suite terminal classification")
    result = {
        "arm_results": [dict(item) for item in arms],
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "barrier_identity": dict(barrier_identity),
        "baseline": dict(baseline),
        "campaign_root_identity": inputs.context["campaign_root_identity"],
        "formal_selection_identity": inputs.selection_identity,
        "gate1": dict(gate1),
        "manifest_identity": dict(manifest_identity),
        "package_id": inputs.context["package_id"],
        "schema_version": CONTROLLER_RESULT_SCHEMA,
        "status": "PASS",
        "suite_selection_identity": dict(suite_selection_identity),
        "terminal_classification_identity": dict(terminal_identity),
    }
    output = Path(str(inputs.context["formal_attempt_dir"])) / CONTROLLER_RESULT_NAME
    raw = authority.canonical_json(result)
    maximum = budget_backend.maximum_bytes(
        "formal controller result",
        artifact_class="publication",
    )
    if type(maximum) is not int or maximum <= 0 or len(raw) > maximum:
        raise FormalControllerError("formal controller result exceeds its fixed budget")
    try:
        identity = dict(
            budget_backend.publish_bytes(
                output,
                raw,
                maximum_bytes=maximum,
                artifact_class="publication",
                label="formal controller result",
            )
        )
    except FormalControllerError:
        raise
    except Exception as exc:
        raise FormalControllerError(
            "formal controller result broker publication failed or acknowledgement is uncertain"
        ) from exc
    expected_identity = {
        "path": str(output.absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }
    if any(identity.get(field) != value for field, value in expected_identity.items()):
        raise FormalControllerError("formal controller result broker identity drifted")
    identity = expected_identity
    replay, replay_identity = _read_record(
        output,
        expected_identity=identity,
        label="formal controller result",
    )
    if replay != result or replay_identity != identity:
        raise FormalControllerError("formal controller result same-byte readback drifted")
    return result, identity


def run_controller(
    *,
    campaign_dir: Path | str,
    formal_selection: Path | str,
    ports: ControllerPorts | None = None,
    budget_backend: BudgetPublicationBackend | None = None,
) -> dict[str, object]:
    """Execute the fixed campaign sequence after the canonical barrier."""

    if budget_backend is None and ports is None:
        raise FormalControllerError(
            "formal controller lacks package-pinned broker-backed budget authority"
        )
    inputs = load_formal_inputs(
        campaign_dir=campaign_dir,
        formal_selection=formal_selection,
    )
    if ports is None:
        assert budget_backend is not None
        selected_ports: ControllerPorts = DefaultControllerPorts(
            inputs,
            budget_backend=budget_backend,
        )
    else:
        selected_ports = ports
    barrier, barrier_identity = selected_ports.wait_for_barrier(inputs)
    if barrier["released"] is not True:
        raise FormalControllerError("outer barrier was not released")
    gate1 = selected_ports.run_gate1(inputs)
    baseline = selected_ports.run_baseline_chain(inputs)
    manifest = authority.build_manifest(inputs.context["campaign_dir"])
    if manifest.get("status") != "PASS":
        raise FormalControllerError("immutable organic manifest did not PASS")
    suite = authority.create_suite_selection(inputs.context["campaign_dir"])
    if suite.get("status") != "PASS":
        raise FormalControllerError("non-launching suite selection did not PASS")
    arm_results = [
        _consume_selected_arm(
            inputs,
            ports=selected_ports,
            slot=slot,
            ordinal=ordinal,
        )
        for ordinal, slot in enumerate(ARM_SEQUENCE, start=1)
    ]
    if budget_backend is None:
        raise FormalControllerError(
            "injected controller ports did not supply a budget publication backend"
        )
    result, identity = _publish_controller_result(
        inputs,
        barrier_identity=barrier_identity,
        gate1=gate1,
        baseline=baseline,
        manifest_identity=_identity(manifest["manifest_identity"], "organic manifest"),
        suite_selection_identity=_identity(
            suite["selection_identity"],
            "organic suite selection",
        ),
        arms=arm_results,
        budget_backend=budget_backend,
    )
    return {
        "controller_result": result,
        "controller_result_identity": identity,
        "status": "PASS",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--formal-selection", type=Path, required=True)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    native_budget_helper: object | None = None,
    formal_budget_backend: BudgetPublicationBackend | None = None,
) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if (
            native_budget_helper is None
            or formal_budget_backend is None
        ):
            raise FormalControllerError(
                "formal controller lacks its selected helper/backend pair"
            )
        result = run_controller(
            campaign_dir=arguments.campaign_dir,
            formal_selection=arguments.formal_selection,
            budget_backend=formal_budget_backend,
        )
    except BaseException as exc:
        print(f"FAIL_CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(authority.canonical_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
