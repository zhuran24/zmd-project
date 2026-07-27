#!/usr/bin/env python3
"""Read-only validation for AB16 formal launch admission and selection.

This module owns the two closed formal-launch schemas.  It never publishes an
artifact, starts a unit, acquires a lock, or performs an experiment.  Package,
campaign-root, Gate-B, snapshot, and current-epoch replay remain owned by
``ab16_authority_v2`` through the planned ``replay_formal_launch_context``
interface.

The separation is deliberate:

* Gate B authorizes creation of a campaign root only.
* formal admission authorizes starting the independent lock guardian and
  publishing one formal selection; it does not authorize outer/controller/
  baseline launch;
* formal selection consumes one attempt and authorizes only the selected
  outer/controller/baseline identities;
* neither artifact authorizes a research claim or a production promotion.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from types import ModuleType
from typing import Any

from docs.research.noncert_cuts_ab16_20260724 import ab16_authority_v2 as authority
from docs.research.noncert_cuts_ab16_20260724 import ab16_outer_closeout_state_v1 as closeout_state


FORMAL_CONTEXT_SCHEMA = "noncert-cuts-ab16-formal-launch-context-v1"
FORMAL_ADMISSION_SCHEMA = "noncert-cuts-ab16-formal-launch-admission-v1"
FORMAL_SELECTION_SCHEMA = "noncert-cuts-ab16-formal-launch-selection-v1"
GUARDIAN_READY_SCHEMA = "noncert-cuts-ab16-outer-guardian-ready-v1"
ATTEMPT_CONSUMPTION_SCHEMA = "noncert-cuts-ab16-formal-attempt-consumption-v1"

OWNER_PUBLISHER_ROLE = "AB16_OWNER_FORMAL_LAUNCH_PUBLISHER_V1"
OWNER_EXECUTION_STRATEGY = (
    "selected-byte-render-independent-validate-sealed-memfd-dirfd-oexcl-v1"
)
OWNER_MEMFD_PATH = "/proc/self/fd/6"
AUTHORITY_SCOPE = "AB16_RESEARCH_ONLY"
PACKAGE_PAYLOAD_MODE = 0o600
# Linux fcntl ABI constants.  The coherent CPython 3.13 build used by this
# campaign does not expose them as ``fcntl`` attributes.
LINUX_F_GET_SEALS = 1034
LINUX_F_SEAL_SEAL = 0x0001
LINUX_F_SEAL_SHRINK = 0x0002
LINUX_F_SEAL_GROW = 0x0004
LINUX_F_SEAL_WRITE = 0x0008
DUAL_HOLDER_PLATFORM_ASSUMPTION = (
    "kernel/systemd/filesystem semantics and a non-hostile OS account preserve "
    "at least one of the separately-cgrouped supervisor or guardian lock "
    "holders until the finite residual-runtime ledger is absent; simultaneous "
    "loss of both holders or reboot is an external platform failure and can "
    "never produce a successful closeout"
)

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
HEAD_RE = re.compile(r"[0-9a-f]{40}\Z")
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}\Z")

CLAIM_AUTHORIZATIONS = frozenset(
    {
        "attainability_authorized",
        "b6_promotion_authorized",
        "lower_bound_update_authorized",
        "optimality_authorized",
        "production_certified",
        "stage_b_promotion_authorized",
        "upper_bound_update_authorized",
        "whole_instance_infeasibility_authorized",
    }
)
FALSE_CLAIMS = {name: False for name in sorted(CLAIM_AUTHORIZATIONS)}

FORMAL_CONTEXT_FIELDS = frozenset(
    {
        "authority_scope",
        "baseline_identity",
        "campaign_dir",
        "campaign_root_identity",
        "controller_identity",
        "dual_holder_platform_assumption",
        "formal_admission_path",
        "formal_attempt_dir",
        "formal_loader_identity",
        "formal_launch_owner_driver_identity",
        "formal_selection_path",
        "gate1_selection_identity",
        "gate_b_approval_identity",
        "gate_b_epoch_observation_identity",
        "guardian_control_socket_path",
        "guardian_runtime_identity",
        "guardian_ready_path",
        "guardian_spec",
        "launch_renderer_identity",
        "launch_validator_identity",
        "manager_epoch",
        "manager_epoch_observation_identity",
        "mechanical_oexcl_publisher_identity",
        "outer_spec",
        "package_id",
        "package_manifest_identity",
        "package_seal_identity",
        "python_identity",
        "repository_head",
        "schema_version",
        "selected_byte_launch_identity",
        "snapshot_materialization_identity",
        "snapshot_root",
        "status",
        "success_verifier_identity",
    }
)

PUBLISHER_FIELDS = frozenset(
    {
        "actor",
        "argv",
        "execution_strategy",
        "formal_launch_owner_driver_identity",
        "mechanical_oexcl_publisher_identity",
        "output_mode",
        "output_path",
        "python_identity",
        "renderer_identity",
        "validator_identity",
    }
)

PUBLISHER_ARGV_FIELDS = frozenset(
    {
        "mechanical_publish",
        "render",
        "validate",
    }
)

PUBLISHER_ACTOR_FIELDS = frozenset(
    {
        "pid",
        "role",
        "session_id",
        "starttime",
    }
)

ADMISSION_FIELDS = frozenset(
    {
        "admission_id",
        "authority_scope",
        "authorizations",
        "baseline_launch_authorized",
        "campaign_dir",
        "campaign_root_identity",
        "controller_launch_authorized",
        "created_at_utc",
        "formal_attempt_dir",
        "formal_attempt_selected",
        "formal_selection_path",
        "formal_selection_publication_authorized",
        "gate_b_approval_identity",
        "gate_b_epoch_observation_identity",
        "guardian_control_socket_path",
        "guardian_launch_authorized",
        "guardian_ready_path",
        "guardian_spec",
        "manager_epoch",
        "manager_epoch_observation_identity",
        "outer_launch_authorized",
        "package_id",
        "package_manifest_identity",
        "package_seal_identity",
        "publication_path",
        "publisher",
        "repository_head",
        "schema_version",
        "snapshot_materialization_identity",
        "snapshot_root",
        "status",
    }
)

GUARDIAN_UNIT_FIELDS = frozenset(
    {
        "control_group",
        "invocation_id",
        "processes",
        "unit_name",
    }
)

OUTER_SPEC_FIELDS = frozenset(
    {
        "arm_prelaunch_paths",
        "barrier_path",
        "child_audit_path",
        "controller_identity",
        "gate1_prelaunch_ownership_path",
        "loader_identity",
        "python_identity",
        "receipt_paths",
        "resource_contract",
        "selected_byte_argv",
        "unit_name",
        "working_directory",
    }
)

OUTER_RECEIPT_PATH_FIELDS = frozenset(
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
    }
)

GUARDIAN_SPEC_FIELDS = frozenset(
    {
        "resource_contract",
        "selected_byte_argv",
        "unit_name",
        "working_directory",
    }
)

OUTER_RESOURCE_CONTRACT = {
    "collect_mode": "inactive-or-failed",
    "kill_mode": "control-group",
    "memory_high_bytes": 35 * 1024**3,
    "memory_max_bytes": 39 * 1024**3,
    "memory_swap_max_bytes": 16 * 1024**3,
    "oom_policy": "continue",
    "runtime_max_sec": 57_600,
    "send_sigkill": True,
}

GUARDIAN_READY_FIELDS = frozenset(
    {
        "authority_scope",
        "authorizations",
        "campaign_dir",
        "campaign_root_identity",
        "control_socket_identity",
        "created_at_utc",
        "dual_holder_platform_assumption",
        "formal_admission_identity",
        "formal_launch_authorized",
        "guardian_process_identity",
        "guardian_runtime_identity",
        "guardian_unit_identity",
        "handoff_message_identity",
        "lock_identities",
        "manager_epoch",
        "package_id",
        "schema_version",
        "status",
        "success_eligible",
        "supervisor_death_watch",
        "supervisor_process_identity",
    }
)

SUPERVISOR_DEATH_WATCH_FIELDS = frozenset(
    {
        "method",
        "process_identity",
        "status",
    }
)

SELECTION_FIELDS = frozenset(
    {
        "attempt_consumption_identity",
        "authority_scope",
        "authorizations",
        "baseline_identity",
        "baseline_launch_authorized",
        "campaign_dir",
        "campaign_root_identity",
        "consumed",
        "controller_identity",
        "controller_launch_authorized",
        "created_at_utc",
        "formal_admission_identity",
        "formal_attempt_dir",
        "formal_attempt_selected",
        "arm_prelaunch_paths",
        "child_audit_path",
        "gate1_prelaunch_ownership_path",
        "gate1_selection_identity",
        "gate_b_approval_identity",
        "gate_b_epoch_observation_identity",
        "guardian_ready_identity",
        "guardian_runtime_identity",
        "guardian_spec",
        "guardian_unit_identity",
        "lock_identities",
        "manager_epoch",
        "manager_epoch_observation_identity",
        "outer_launch_authorized",
        "outer_spec",
        "package_id",
        "package_manifest_identity",
        "package_seal_identity",
        "publication_path",
        "publisher",
        "repository_head",
        "retry_eligible",
        "schema_version",
        "selection_id",
        "snapshot_materialization_identity",
        "snapshot_root",
        "status",
    }
)

ATTEMPT_CONSUMPTION_FIELDS = frozenset(
    {
        "authorizations",
        "campaign_root_identity",
        "consumed",
        "created_at_utc",
        "formal_dir",
        "lower_bound",
        "package_id",
        "production_certified",
        "retry_eligible",
        "schema_version",
        "upper_bound",
    }
)


class FormalLaunchValidationError(RuntimeError):
    """A closed formal-launch record or upstream join failed validation."""


def _closed(value: object, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != set(fields):
        raise FormalLaunchValidationError(f"{label} field set drifted")
    return dict(value)


def _reject_none(value: object, label: str) -> None:
    if value is None:
        raise FormalLaunchValidationError(f"{label} contains an unproved null")
    children = value.items() if type(value) is dict else enumerate(value) if type(value) is list else ()
    for key, item in children:
        _reject_none(item, f"{label}.{key}")


def _absolute(value: object, label: str) -> str:
    if type(value) is not str or not value or not Path(value).is_absolute():
        raise FormalLaunchValidationError(f"{label} is not one absolute path")
    return value


def _token(value: object, label: str) -> str:
    if type(value) is not str or TOKEN_RE.fullmatch(value) is None:
        raise FormalLaunchValidationError(f"{label} is malformed")
    return value


def _timestamp(value: object, label: str) -> str:
    if type(value) is not str or not value.endswith("Z"):
        raise FormalLaunchValidationError(f"{label} is not canonical UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise FormalLaunchValidationError(f"{label} is not canonical UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FormalLaunchValidationError(f"{label} has no UTC offset")
    return value


def _identity(value: object, label: str) -> dict[str, object]:
    record = _closed(value, frozenset({"path", "sha256", "size_bytes"}), label)
    if (
        type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
    ):
        raise FormalLaunchValidationError(f"{label} identity is malformed")
    return record


def _message_identity(value: object, label: str) -> dict[str, object]:
    record = _closed(value, frozenset({"sha256", "size_bytes"}), label)
    if (
        type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] <= 0
    ):
        raise FormalLaunchValidationError(f"{label} message identity is malformed")
    return record


def _mode_identity(value: object, label: str) -> dict[str, object]:
    record = _closed(
        value,
        frozenset({"mode", "path", "sha256", "size_bytes"}),
        label,
    )
    projected = _identity(
        {name: record[name] for name in ("path", "sha256", "size_bytes")},
        label,
    )
    if (
        type(record["mode"]) is not int
        or record["mode"] < 0
        or record["mode"] & ~0o7777
    ):
        raise FormalLaunchValidationError(f"{label} mode is malformed")
    return {"mode": record["mode"], **projected}


def _selected_identity_argument(value: str) -> dict[str, dict[str, object]]:
    def pairs_without_duplicates(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, item in pairs:
            if key in result:
                raise FormalLaunchValidationError(
                    "selected-byte identity JSON has a duplicate key"
                )
            result[key] = item
        return result

    try:
        parsed = json.loads(
            value,
            object_pairs_hook=pairs_without_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                FormalLaunchValidationError(
                    f"selected-byte identity JSON contains invalid constant {token}"
                )
            ),
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise FormalLaunchValidationError(
            "selected-byte identity argument is invalid JSON"
        ) from exc
    canonical = json.dumps(
        parsed,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if canonical != value:
        raise FormalLaunchValidationError(
            "selected-byte identity argument is not canonical"
        )
    record = _closed(
        parsed,
        frozenset({"authority", "loader", "python"}),
        "selected-byte identity set",
    )
    return {
        name: _mode_identity(record[name], f"selected-byte {name}")
        for name in ("authority", "loader", "python")
    }


def _process(value: object, label: str) -> dict[str, int]:
    try:
        return closeout_state.validate_process_identity(value, label)
    except closeout_state.CloseoutStateError as exc:
        raise FormalLaunchValidationError(str(exc)) from exc


def _lock_identities(value: object) -> list[dict[str, object]]:
    if type(value) is not list or len(value) != len(closeout_state.LOCK_PATHS):
        raise FormalLaunchValidationError("formal lock identity set is malformed")
    result: list[dict[str, object]] = []
    for expected_path, item in zip(closeout_state.LOCK_PATHS, value, strict=True):
        record = _closed(
            item,
            frozenset({"device", "inode", "path", "uid"}),
            f"formal lock {expected_path}",
        )
        if (
            record["path"] != expected_path
            or type(record["device"]) is not int
            or record["device"] <= 0
            or type(record["inode"]) is not int
            or record["inode"] <= 0
            or type(record["uid"]) is not int
            or record["uid"] < 0
        ):
            raise FormalLaunchValidationError(f"formal lock identity drifted: {expected_path}")
        result.append(record)
    return result


def _manager_epoch(value: object, expected: object) -> dict[str, object]:
    if type(value) is not dict or not value:
        raise FormalLaunchValidationError("manager epoch is not one nonempty object")
    _reject_none(value, "manager epoch")
    if type(expected) is not dict or dict(value) != dict(expected):
        raise FormalLaunchValidationError("manager/boot epoch join drifted")
    return dict(value)


def _claims(value: object) -> dict[str, bool]:
    record = _closed(value, CLAIM_AUTHORIZATIONS, "formal claim authorizations")
    if record != FALSE_CLAIMS:
        raise FormalLaunchValidationError("formal launch artifact attempted to authorize a research claim")
    return {name: False for name in sorted(CLAIM_AUTHORIZATIONS)}


def _publisher(
    value: object,
    *,
    context: Mapping[str, object],
    kind: str,
    output_path: str,
) -> dict[str, object]:
    record = _closed(value, PUBLISHER_FIELDS, "owner-side publisher")
    argv = _closed(record["argv"], PUBLISHER_ARGV_FIELDS, "owner-side publisher argv")
    actor = _closed(record["actor"], PUBLISHER_ACTOR_FIELDS, "owner-side publisher actor")
    if kind not in {"admission", "selection"}:
        raise FormalLaunchValidationError("owner-side publisher kind is malformed")
    common = [
        "--campaign-dir",
        str(context["campaign_dir"]),
    ]
    prerequisites = (
        []
        if kind == "admission"
        else [
            "--admission",
            str(context["formal_admission_path"]),
            "--guardian-ready",
            str(context["guardian_ready_path"]),
            "--attempt-consumption",
            str(Path(str(context["formal_attempt_dir"])) / "attempt-consumption.json"),
        ]
    )
    expected_argv = {
        "mechanical_publish": [
            "OWNER_OEXCL_PUBLISH_V1",
            Path(output_path).name,
        ],
        "render": [
            "formal-launch-authority",
            *common,
            "--draft",
            OWNER_MEMFD_PATH,
            "--kind",
            kind,
            *prerequisites,
        ],
        "validate": [
            "formal-launch-validator",
            *common,
            "--candidate",
            OWNER_MEMFD_PATH,
            "--kind",
            kind,
            *prerequisites,
        ],
    }
    if (
        actor["role"] != OWNER_PUBLISHER_ROLE
        or type(actor["pid"]) is not int
        or actor["pid"] <= 0
        or type(actor["starttime"]) is not int
        or actor["starttime"] <= 0
        or type(actor["session_id"]) is not str
        or TOKEN_RE.fullmatch(actor["session_id"]) is None
        or type(record["execution_strategy"]) is not str
        or record["execution_strategy"] != OWNER_EXECUTION_STRATEGY
        or record["output_mode"] != 0o444
        or record["output_path"] != output_path
        or argv != expected_argv
    ):
        raise FormalLaunchValidationError("owner-side publisher identity is malformed")
    result = dict(record)
    result["actor"] = actor
    result["argv"] = expected_argv
    for field in ("python_identity", "renderer_identity", "validator_identity"):
        result[field] = _identity(record[field], f"owner-side publisher {field}")
    for field in (
        "formal_launch_owner_driver_identity",
        "mechanical_oexcl_publisher_identity",
    ):
        result[field] = _message_identity(
            record[field],
            f"owner-side publisher {field}",
        )
        if result[field] != context[field]:
            raise FormalLaunchValidationError(
                f"owner-side publisher {field} drifted"
            )
    if result["renderer_identity"] == result["validator_identity"]:
        raise FormalLaunchValidationError("renderer and independent validator identities collapsed")
    return result


def _guardian_unit(value: object) -> dict[str, object]:
    record = _closed(value, GUARDIAN_UNIT_FIELDS, "guardian unit identity")
    processes = record["processes"]
    if (
        type(record["unit_name"]) is not str
        or closeout_state.UNIT_RE.fullmatch(record["unit_name"]) is None
        or type(record["invocation_id"]) is not str
        or closeout_state.INVOCATION_RE.fullmatch(record["invocation_id"]) is None
        or type(record["control_group"]) is not str
        or type(processes) is not list
        or not processes
    ):
        raise FormalLaunchValidationError("guardian unit identity is malformed")
    try:
        closeout_state.validate_control_group(record["control_group"])
    except closeout_state.CloseoutStateError as exc:
        raise FormalLaunchValidationError(str(exc)) from exc
    checked_processes = [
        _process(item, f"guardian unit process {index}")
        for index, item in enumerate(processes)
    ]
    if len({item["pid"] for item in checked_processes}) != len(checked_processes):
        raise FormalLaunchValidationError("guardian unit processes are duplicated")
    result = dict(record)
    result["processes"] = checked_processes
    return result


def _control_socket_identity(value: object) -> dict[str, object]:
    record = _closed(
        value,
        frozenset({"device", "inode", "mode", "path", "uid"}),
        "guardian control socket identity",
    )
    if (
        type(record["device"]) is not int
        or record["device"] <= 0
        or type(record["inode"]) is not int
        or record["inode"] <= 0
        or record["mode"] != 0o600
        or type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["uid"]) is not int
        or record["uid"] < 0
    ):
        raise FormalLaunchValidationError("guardian control socket identity is malformed")
    return record


def _supervisor_death_watch(
    value: object,
    *,
    expected_process_identity: Mapping[str, object],
) -> dict[str, object]:
    record = _closed(
        value,
        SUPERVISOR_DEATH_WATCH_FIELDS,
        "guardian supervisor death watch",
    )
    process = _process(
        record["process_identity"],
        "guardian supervisor death watch process",
    )
    expected = _process(
        expected_process_identity,
        "expected guardian supervisor death watch process",
    )
    if (
        record["method"] != "linux-pidfd-open-v1"
        or record["status"] != "ARMED"
        or process != expected
    ):
        raise FormalLaunchValidationError(
            "guardian supervisor death watch identity drifted"
        )
    result = dict(record)
    result["process_identity"] = process
    return result


def _selected_role_argv(
    value: object,
    *,
    campaign_dir: str,
    role: str,
    role_argv: Sequence[str],
    loader_identity: Mapping[str, object],
    python_identity: Mapping[str, object],
    selected_byte_launch_identity: Mapping[str, object],
    label: str,
) -> list[str]:
    """Validate one closed FD3/FD4/FD5 selected-byte loader invocation."""

    argv = validate_argv(value, label)
    expected = [
        "/proc/self/fd/3",
        "-I",
        "-B",
        "-c",
        argv[4] if len(argv) > 4 else "",
        "systemd-openfile",
        argv[6] if len(argv) > 6 else "",
        "--campaign-dir",
        campaign_dir,
        "--role",
        role,
        "--",
        *role_argv,
    ]
    if argv != expected:
        raise FormalLaunchValidationError(
            f"{label} does not match the closed {role} shape"
        )
    literal_raw = argv[4].encode("utf-8")
    if {
        "sha256": hashlib.sha256(literal_raw).hexdigest(),
        "size_bytes": len(literal_raw),
    } != dict(selected_byte_launch_identity):
        raise FormalLaunchValidationError("selected-byte launch literal drifted")
    selected_identities = _selected_identity_argument(argv[6])
    if (
        {
            name: selected_identities["python"][name]
            for name in ("path", "sha256", "size_bytes")
        }
        != dict(python_identity)
        or {
            name: selected_identities["loader"][name]
            for name in ("path", "sha256", "size_bytes")
        }
        != dict(loader_identity)
        or selected_identities["loader"]["mode"] != PACKAGE_PAYLOAD_MODE
        or selected_identities["authority"]["mode"] != PACKAGE_PAYLOAD_MODE
        or selected_identities["authority"]["path"]
        != str(
            Path(campaign_dir)
            / "campaign-authority/package/payload/tool.ab16_authority_v2.py"
        )
        or selected_identities["python"]["mode"] & 0o111 == 0
        or selected_identities["python"]["mode"] & 0o022
    ):
        raise FormalLaunchValidationError(
            "selected-byte open-file identity set drifted"
        )
    return argv


def _outer_spec(
    value: object,
    *,
    campaign_dir: str,
    controller_identity: Mapping[str, object],
    loader_identity: Mapping[str, object],
    python_identity: Mapping[str, object],
    selected_byte_launch_identity: Mapping[str, object],
    formal_selection_path: str,
    snapshot_root: str,
) -> dict[str, object]:
    """Validate the inline selected outer unit; it is not a third artifact."""

    record = _closed(value, OUTER_SPEC_FIELDS, "selected outer spec")
    result = dict(record)
    result["controller_identity"] = _identity(
        record["controller_identity"],
        "selected outer controller",
    )
    result["loader_identity"] = _identity(
        record["loader_identity"],
        "selected outer loader",
    )
    result["python_identity"] = _identity(
        record["python_identity"],
        "selected outer Python",
    )
    argv = _selected_role_argv(
        record["selected_byte_argv"],
        campaign_dir=campaign_dir,
        role="formal-controller",
        role_argv=(
            "--campaign-dir",
            campaign_dir,
            "--formal-selection",
            formal_selection_path,
        ),
        loader_identity=loader_identity,
        python_identity=python_identity,
        selected_byte_launch_identity=selected_byte_launch_identity,
        label="selected outer argv",
    )
    result["selected_byte_argv"] = argv
    if (
        type(record["unit_name"]) is not str
        or closeout_state.UNIT_RE.fullmatch(record["unit_name"]) is None
        or record["working_directory"] != snapshot_root
        or result["controller_identity"] != dict(controller_identity)
        or result["loader_identity"] != dict(loader_identity)
        or result["python_identity"] != dict(python_identity)
        or record["resource_contract"] != OUTER_RESOURCE_CONTRACT
    ):
        raise FormalLaunchValidationError("selected outer byte/resource identity drifted")
    barrier = _absolute(record["barrier_path"], "selected outer barrier")
    gate1_prelaunch = _absolute(
        record["gate1_prelaunch_ownership_path"],
        "selected Gate1 prelaunch ownership",
    )
    child_audit = _absolute(record["child_audit_path"], "selected child audit")
    arm_prelaunch = _closed(
        record["arm_prelaunch_paths"],
        frozenset(closeout_state.ARM_SEQUENCE),
        "selected arm prelaunch paths",
    )
    checked_arm_prelaunch: dict[str, dict[str, str]] = {}
    for slot in closeout_state.ARM_SEQUENCE:
        paths = _closed(
            arm_prelaunch[slot],
            frozenset({"receipt", "request"}),
            f"selected arm prelaunch {slot}",
        )
        checked_arm_prelaunch[slot] = {
            name: _absolute(raw, f"selected arm prelaunch {slot}.{name}")
            for name, raw in paths.items()
        }
    receipts = _closed(
        record["receipt_paths"],
        OUTER_RECEIPT_PATH_FIELDS,
        "selected outer receipt paths",
    )
    campaign = Path(campaign_dir)
    checked_paths: dict[str, str] = {}
    for name, raw in receipts.items():
        path = Path(_absolute(raw, f"selected outer receipt {name}"))
        if not path.is_relative_to(campaign):
            raise FormalLaunchValidationError(f"selected outer receipt escaped campaign: {name}")
        checked_paths[name] = str(path)
    if not Path(barrier).is_relative_to(campaign):
        raise FormalLaunchValidationError("selected outer barrier escaped campaign")
    for label, raw in (
        ("Gate1 prelaunch ownership", gate1_prelaunch),
        ("child audit", child_audit),
    ):
        if not Path(raw).is_relative_to(campaign):
            raise FormalLaunchValidationError(f"selected {label} escaped campaign")
    for slot, paths in checked_arm_prelaunch.items():
        if any(not Path(raw).is_relative_to(campaign) for raw in paths.values()):
            raise FormalLaunchValidationError(f"selected arm prelaunch escaped campaign: {slot}")
    result["arm_prelaunch_paths"] = checked_arm_prelaunch
    result["barrier_path"] = barrier
    result["child_audit_path"] = child_audit
    result["gate1_prelaunch_ownership_path"] = gate1_prelaunch
    result["receipt_paths"] = checked_paths
    result["resource_contract"] = dict(OUTER_RESOURCE_CONTRACT)
    return result


def _guardian_spec(
    value: object,
    *,
    campaign_dir: str,
    formal_admission_path: str,
    guardian_control_socket_path: str,
    guardian_ready_path: str,
    loader_identity: Mapping[str, object],
    python_identity: Mapping[str, object],
    selected_byte_launch_identity: Mapping[str, object],
    snapshot_root: str,
) -> dict[str, object]:
    """Validate the independently selected guardian unit and runtime argv."""

    record = _closed(value, GUARDIAN_SPEC_FIELDS, "selected guardian spec")
    result = dict(record)
    result["selected_byte_argv"] = _selected_role_argv(
        record["selected_byte_argv"],
        campaign_dir=campaign_dir,
        role="outer-guardian",
        role_argv=(
            "--campaign-dir",
            campaign_dir,
            "--formal-admission",
            formal_admission_path,
            "--control-socket",
            guardian_control_socket_path,
            "--ready-output",
            guardian_ready_path,
        ),
        loader_identity=loader_identity,
        python_identity=python_identity,
        selected_byte_launch_identity=selected_byte_launch_identity,
        label="selected guardian argv",
    )
    if (
        type(record["unit_name"]) is not str
        or closeout_state.UNIT_RE.fullmatch(record["unit_name"]) is None
        or record["working_directory"] != snapshot_root
        or record["resource_contract"] != OUTER_RESOURCE_CONTRACT
    ):
        raise FormalLaunchValidationError(
            "selected guardian byte/resource identity drifted"
        )
    result["resource_contract"] = dict(OUTER_RESOURCE_CONTRACT)
    return result


def validate_formal_context(value: object) -> dict[str, object]:
    """Validate the closed output of authority-owned formal replay."""

    record = _closed(value, FORMAL_CONTEXT_FIELDS, "formal launch replay context")
    if (
        record["schema_version"] != FORMAL_CONTEXT_SCHEMA
        or record["status"] != "PASS"
        or record["authority_scope"] != AUTHORITY_SCOPE
        or type(record["package_id"]) is not str
        or SHA256_RE.fullmatch(record["package_id"]) is None
        or type(record["repository_head"]) is not str
        or HEAD_RE.fullmatch(record["repository_head"]) is None
        or record["dual_holder_platform_assumption"] != DUAL_HOLDER_PLATFORM_ASSUMPTION
    ):
        raise FormalLaunchValidationError("formal launch replay context scalar drifted")
    result = dict(record)
    for field in (
        "campaign_dir",
        "formal_admission_path",
        "formal_attempt_dir",
        "formal_selection_path",
        "guardian_control_socket_path",
        "guardian_ready_path",
        "snapshot_root",
    ):
        result[field] = _absolute(record[field], f"formal context {field}")
    if not Path(result["formal_attempt_dir"]).is_relative_to(Path(result["campaign_dir"])):
        raise FormalLaunchValidationError("formal attempt directory escaped the campaign")
    for field in (
        "campaign_root_identity",
        "gate1_selection_identity",
        "gate_b_approval_identity",
        "gate_b_epoch_observation_identity",
        "formal_loader_identity",
        "guardian_runtime_identity",
        "launch_renderer_identity",
        "launch_validator_identity",
        "manager_epoch_observation_identity",
        "package_manifest_identity",
        "package_seal_identity",
        "python_identity",
        "snapshot_materialization_identity",
        "controller_identity",
        "baseline_identity",
        "success_verifier_identity",
    ):
        result[field] = _identity(record[field], f"formal context {field}")
    result["selected_byte_launch_identity"] = _message_identity(
        record["selected_byte_launch_identity"],
        "formal context selected-byte launch literal",
    )
    for field in (
        "formal_launch_owner_driver_identity",
        "mechanical_oexcl_publisher_identity",
    ):
        result[field] = _message_identity(
            record[field],
            f"formal context {field}",
        )
    if type(record["manager_epoch"]) is not dict or not record["manager_epoch"]:
        raise FormalLaunchValidationError("formal context manager epoch is malformed")
    _reject_none(record["manager_epoch"], "formal context manager epoch")
    result["manager_epoch"] = dict(record["manager_epoch"])
    authority_digests = {
        result["launch_renderer_identity"]["sha256"],
        result["launch_validator_identity"]["sha256"],
    }
    runtime_digests = {
        result[field]["sha256"]
        for field in (
            "baseline_identity",
            "controller_identity",
            "formal_loader_identity",
            "guardian_runtime_identity",
            "success_verifier_identity",
        )
    }
    if (
        len(authority_digests) != 2
        or authority_digests & runtime_digests
    ):
        raise FormalLaunchValidationError(
            "formal launch authority and runtime tool identities collapsed"
        )
    result["outer_spec"] = _outer_spec(
        record["outer_spec"],
        campaign_dir=result["campaign_dir"],
        controller_identity=result["controller_identity"],
        loader_identity=result["formal_loader_identity"],
        python_identity=result["python_identity"],
        selected_byte_launch_identity=result["selected_byte_launch_identity"],
        formal_selection_path=result["formal_selection_path"],
        snapshot_root=result["snapshot_root"],
    )
    result["guardian_spec"] = _guardian_spec(
        record["guardian_spec"],
        campaign_dir=result["campaign_dir"],
        formal_admission_path=result["formal_admission_path"],
        guardian_control_socket_path=result["guardian_control_socket_path"],
        guardian_ready_path=result["guardian_ready_path"],
        loader_identity=result["formal_loader_identity"],
        python_identity=result["python_identity"],
        selected_byte_launch_identity=result["selected_byte_launch_identity"],
        snapshot_root=result["snapshot_root"],
    )
    if result["guardian_spec"]["unit_name"] == result["outer_spec"]["unit_name"]:
        raise FormalLaunchValidationError("guardian and outer unit identities collapsed")
    return result


def replay_formal_launch_context(
    authority_module: ModuleType,
    campaign_dir: Path | str,
) -> dict[str, object]:
    """Call the authority owner; never synthesize a package/snapshot fallback."""

    replay = getattr(authority_module, "replay_formal_launch_context", None)
    if not callable(replay):
        raise FormalLaunchValidationError(
            "ab16_authority_v2.replay_formal_launch_context is unavailable; "
            "formal launch remains unauthorized"
        )
    try:
        raw = replay(campaign_dir=Path(campaign_dir).absolute())
    except Exception as exc:
        raise FormalLaunchValidationError(f"formal launch authority replay failed: {exc}") from exc
    return validate_formal_context(raw)


def validate_admission(
    value: object,
    *,
    expected_context: Mapping[str, object],
) -> dict[str, object]:
    """Validate one owner-published admission without granting launch."""

    context = validate_formal_context(expected_context)
    record = _closed(value, ADMISSION_FIELDS, "formal launch admission")
    result = dict(record)
    result["admission_id"] = _token(record["admission_id"], "formal admission ID")
    result["created_at_utc"] = _timestamp(record["created_at_utc"], "formal admission timestamp")
    result["publisher"] = _publisher(
        record["publisher"],
        context=context,
        kind="admission",
        output_path=context["formal_admission_path"],
    )
    result["authorizations"] = _claims(record["authorizations"])
    for field in (
        "campaign_root_identity",
        "gate_b_approval_identity",
        "gate_b_epoch_observation_identity",
        "manager_epoch_observation_identity",
        "package_manifest_identity",
        "package_seal_identity",
        "snapshot_materialization_identity",
    ):
        result[field] = _identity(record[field], f"formal admission {field}")
    scalar_joins = {
        "authority_scope": "authority_scope",
        "campaign_dir": "campaign_dir",
        "campaign_root_identity": "campaign_root_identity",
        "formal_attempt_dir": "formal_attempt_dir",
        "formal_selection_path": "formal_selection_path",
        "gate_b_approval_identity": "gate_b_approval_identity",
        "gate_b_epoch_observation_identity": "gate_b_epoch_observation_identity",
        "guardian_control_socket_path": "guardian_control_socket_path",
        "guardian_ready_path": "guardian_ready_path",
        "manager_epoch_observation_identity": "manager_epoch_observation_identity",
        "package_id": "package_id",
        "package_manifest_identity": "package_manifest_identity",
        "package_seal_identity": "package_seal_identity",
        "repository_head": "repository_head",
        "snapshot_materialization_identity": "snapshot_materialization_identity",
        "snapshot_root": "snapshot_root",
    }
    if any(result[field] != context[context_field] for field, context_field in scalar_joins.items()):
        raise FormalLaunchValidationError("formal admission upstream identity join drifted")
    result["manager_epoch"] = _manager_epoch(record["manager_epoch"], context["manager_epoch"])
    result["guardian_spec"] = _guardian_spec(
        record["guardian_spec"],
        campaign_dir=context["campaign_dir"],
        formal_admission_path=context["formal_admission_path"],
        guardian_control_socket_path=context["guardian_control_socket_path"],
        guardian_ready_path=context["guardian_ready_path"],
        loader_identity=context["formal_loader_identity"],
        python_identity=context["python_identity"],
        selected_byte_launch_identity=context["selected_byte_launch_identity"],
        snapshot_root=context["snapshot_root"],
    )
    if (
        result["publisher"]["python_identity"] != context["python_identity"]
        or result["publisher"]["renderer_identity"] != context["launch_renderer_identity"]
        or result["publisher"]["validator_identity"] != context["launch_validator_identity"]
    ):
        raise FormalLaunchValidationError("formal admission publisher tool identity drifted")
    if (
        record["schema_version"] != FORMAL_ADMISSION_SCHEMA
        or record["status"] != "ADMITTED"
        or record["publication_path"] != context["formal_admission_path"]
        or record["guardian_launch_authorized"] is not True
        or record["formal_selection_publication_authorized"] is not True
        or record["formal_attempt_selected"] is not False
        or record["outer_launch_authorized"] is not False
        or record["controller_launch_authorized"] is not False
        or record["baseline_launch_authorized"] is not False
        or result["guardian_spec"] != context["guardian_spec"]
    ):
        raise FormalLaunchValidationError("formal admission crossed its authority boundary")
    return result


def validate_guardian_ready(
    value: object,
    *,
    admission: Mapping[str, object],
    admission_identity: Mapping[str, object],
    expected_context: Mapping[str, object],
) -> dict[str, object]:
    """Validate guardian readiness; readiness itself never authorizes launch."""

    context = validate_formal_context(expected_context)
    checked_admission = validate_admission(admission, expected_context=context)
    checked_admission_identity = _identity(admission_identity, "formal admission identity")
    if checked_admission_identity["path"] != context["formal_admission_path"]:
        raise FormalLaunchValidationError("formal admission identity path drifted")
    record = _closed(value, GUARDIAN_READY_FIELDS, "outer guardian ready")
    result = dict(record)
    result["created_at_utc"] = _timestamp(record["created_at_utc"], "guardian ready timestamp")
    result["control_socket_identity"] = _control_socket_identity(record["control_socket_identity"])
    result["formal_admission_identity"] = _identity(
        record["formal_admission_identity"],
        "guardian ready formal admission",
    )
    result["guardian_runtime_identity"] = _identity(
        record["guardian_runtime_identity"],
        "guardian runtime",
    )
    result["handoff_message_identity"] = _message_identity(
        record["handoff_message_identity"],
        "guardian handoff",
    )
    result["guardian_process_identity"] = _process(
        record["guardian_process_identity"],
        "guardian process",
    )
    result["supervisor_process_identity"] = _process(
        record["supervisor_process_identity"],
        "supervisor process",
    )
    result["supervisor_death_watch"] = _supervisor_death_watch(
        record["supervisor_death_watch"],
        expected_process_identity=result["supervisor_process_identity"],
    )
    result["guardian_unit_identity"] = _guardian_unit(record["guardian_unit_identity"])
    result["lock_identities"] = _lock_identities(record["lock_identities"])
    result["authorizations"] = _claims(record["authorizations"])
    result["manager_epoch"] = _manager_epoch(record["manager_epoch"], context["manager_epoch"])
    if (
        record["schema_version"] != GUARDIAN_READY_SCHEMA
        or record["status"] != "READY"
        or record["authority_scope"] != AUTHORITY_SCOPE
        or record["campaign_dir"] != context["campaign_dir"]
        or record["campaign_root_identity"] != context["campaign_root_identity"]
        or record["package_id"] != context["package_id"]
        or result["control_socket_identity"]["path"] != context["guardian_control_socket_path"]
        or result["formal_admission_identity"] != checked_admission_identity
        or result["guardian_runtime_identity"] != context["guardian_runtime_identity"]
        or result["guardian_unit_identity"]["unit_name"]
        != context["guardian_spec"]["unit_name"]
        or result["guardian_process_identity"]
        not in result["guardian_unit_identity"]["processes"]
        or record["dual_holder_platform_assumption"] != DUAL_HOLDER_PLATFORM_ASSUMPTION
        or record["formal_launch_authorized"] is not False
        or record["success_eligible"] is not False
        or checked_admission["guardian_launch_authorized"] is not True
    ):
        raise FormalLaunchValidationError("guardian readiness identity/authority drifted")
    return result


def validate_selection(
    value: object,
    *,
    admission: Mapping[str, object],
    admission_identity: Mapping[str, object],
    guardian_ready: Mapping[str, object],
    guardian_ready_identity: Mapping[str, object],
    attempt_consumption: Mapping[str, object],
    attempt_consumption_identity: Mapping[str, object],
    expected_context: Mapping[str, object],
) -> dict[str, object]:
    """Validate one consumed formal selection and all independent joins."""

    context = validate_formal_context(expected_context)
    checked_admission = validate_admission(admission, expected_context=context)
    checked_admission_identity = _identity(admission_identity, "formal admission identity")
    checked_guardian = validate_guardian_ready(
        guardian_ready,
        admission=checked_admission,
        admission_identity=checked_admission_identity,
        expected_context=context,
    )
    checked_guardian_identity = _identity(guardian_ready_identity, "guardian ready identity")
    validate_attempt_consumption(attempt_consumption, expected_context=context)
    checked_consumption = _identity(attempt_consumption_identity, "attempt consumption identity")
    if (
        checked_admission_identity["path"] != context["formal_admission_path"]
        or checked_guardian_identity["path"] != context["guardian_ready_path"]
        or checked_consumption["path"]
        != str(Path(context["formal_attempt_dir"]) / "attempt-consumption.json")
    ):
        raise FormalLaunchValidationError("formal selection prerequisite path drifted")
    record = _closed(value, SELECTION_FIELDS, "formal launch selection")
    result = dict(record)
    result["selection_id"] = _token(record["selection_id"], "formal selection ID")
    result["created_at_utc"] = _timestamp(record["created_at_utc"], "formal selection timestamp")
    result["publisher"] = _publisher(
        record["publisher"],
        context=context,
        kind="selection",
        output_path=context["formal_selection_path"],
    )
    result["authorizations"] = _claims(record["authorizations"])
    for field in (
        "attempt_consumption_identity",
        "baseline_identity",
        "campaign_root_identity",
        "controller_identity",
        "formal_admission_identity",
        "gate1_selection_identity",
        "gate_b_approval_identity",
        "gate_b_epoch_observation_identity",
        "guardian_ready_identity",
        "guardian_runtime_identity",
        "manager_epoch_observation_identity",
        "package_manifest_identity",
        "package_seal_identity",
        "snapshot_materialization_identity",
    ):
        result[field] = _identity(record[field], f"formal selection {field}")
    result["guardian_unit_identity"] = _guardian_unit(record["guardian_unit_identity"])
    result["guardian_spec"] = _guardian_spec(
        record["guardian_spec"],
        campaign_dir=context["campaign_dir"],
        formal_admission_path=context["formal_admission_path"],
        guardian_control_socket_path=context["guardian_control_socket_path"],
        guardian_ready_path=context["guardian_ready_path"],
        loader_identity=context["formal_loader_identity"],
        python_identity=context["python_identity"],
        selected_byte_launch_identity=context["selected_byte_launch_identity"],
        snapshot_root=context["snapshot_root"],
    )
    result["lock_identities"] = _lock_identities(record["lock_identities"])
    result["manager_epoch"] = _manager_epoch(record["manager_epoch"], context["manager_epoch"])
    result["outer_spec"] = _outer_spec(
        record["outer_spec"],
        campaign_dir=context["campaign_dir"],
        controller_identity=context["controller_identity"],
        loader_identity=context["formal_loader_identity"],
        python_identity=context["python_identity"],
        selected_byte_launch_identity=context["selected_byte_launch_identity"],
        formal_selection_path=context["formal_selection_path"],
        snapshot_root=context["snapshot_root"],
    )
    if (
        result["publisher"]["python_identity"] != context["python_identity"]
        or result["publisher"]["renderer_identity"] != context["launch_renderer_identity"]
        or result["publisher"]["validator_identity"] != context["launch_validator_identity"]
    ):
        raise FormalLaunchValidationError("formal selection publisher tool identity drifted")
    if result["publisher"]["actor"] != checked_admission["publisher"]["actor"]:
        raise FormalLaunchValidationError("formal admission/selection owner session drifted")
    publisher_actor = result["publisher"]["actor"]
    runtime_actors = (
        checked_guardian["guardian_process_identity"],
        checked_guardian["supervisor_process_identity"],
    )
    if any(
        publisher_actor["pid"] == runtime["pid"]
        and publisher_actor["starttime"] == runtime["starttime"]
        for runtime in runtime_actors
    ):
        raise FormalLaunchValidationError(
            "formal runtime attempted to authorize its own selection"
        )
    direct_joins = {
        "attempt_consumption_identity": checked_consumption,
        "baseline_identity": context["baseline_identity"],
        "campaign_dir": context["campaign_dir"],
        "campaign_root_identity": context["campaign_root_identity"],
        "controller_identity": context["controller_identity"],
        "formal_admission_identity": checked_admission_identity,
        "formal_attempt_dir": context["formal_attempt_dir"],
        "gate1_selection_identity": context["gate1_selection_identity"],
        "gate_b_approval_identity": context["gate_b_approval_identity"],
        "gate_b_epoch_observation_identity": context["gate_b_epoch_observation_identity"],
        "guardian_ready_identity": checked_guardian_identity,
        "guardian_runtime_identity": checked_guardian["guardian_runtime_identity"],
        "guardian_spec": context["guardian_spec"],
        "guardian_unit_identity": checked_guardian["guardian_unit_identity"],
        "lock_identities": checked_guardian["lock_identities"],
        "manager_epoch_observation_identity": context["manager_epoch_observation_identity"],
        "outer_spec": context["outer_spec"],
        "gate1_prelaunch_ownership_path": context["outer_spec"]["gate1_prelaunch_ownership_path"],
        "arm_prelaunch_paths": context["outer_spec"]["arm_prelaunch_paths"],
        "child_audit_path": context["outer_spec"]["child_audit_path"],
        "package_id": context["package_id"],
        "package_manifest_identity": context["package_manifest_identity"],
        "package_seal_identity": context["package_seal_identity"],
        "repository_head": context["repository_head"],
        "snapshot_materialization_identity": context["snapshot_materialization_identity"],
        "snapshot_root": context["snapshot_root"],
    }
    if any(result[field] != expected for field, expected in direct_joins.items()):
        raise FormalLaunchValidationError("formal selection upstream identity join drifted")
    if (
        record["schema_version"] != FORMAL_SELECTION_SCHEMA
        or record["status"] != "SELECTED"
        or record["authority_scope"] != AUTHORITY_SCOPE
        or record["publication_path"] != context["formal_selection_path"]
        or record["selection_id"] == checked_admission["admission_id"]
        or record["consumed"] is not True
        or record["retry_eligible"] is not False
        or record["formal_attempt_selected"] is not True
        or record["outer_launch_authorized"] is not True
        or record["controller_launch_authorized"] is not True
        or record["baseline_launch_authorized"] is not True
        or checked_admission["formal_selection_publication_authorized"] is not True
    ):
        raise FormalLaunchValidationError("formal selection crossed its authority boundary")
    prohibited_runtime_identities = {
        result["controller_identity"]["sha256"],
        result["guardian_runtime_identity"]["sha256"],
        result["outer_spec"]["controller_identity"]["sha256"],
    }
    publisher = result["publisher"]
    if (
        publisher["renderer_identity"]["sha256"] in prohibited_runtime_identities
        or publisher["validator_identity"]["sha256"] in prohibited_runtime_identities
    ):
        raise FormalLaunchValidationError("formal runtime attempted to authorize itself")
    return result


def validate_attempt_consumption(
    value: object,
    *,
    expected_context: Mapping[str, object],
) -> dict[str, object]:
    """Validate the existing state owner's one-way formal-attempt marker.

    Launch authority does not own or publish this marker.  It replays the
    state owner's closed schema so a detached path/hash cannot stand in for
    the marker's consumption, no-retry, campaign-root, package, and ledger
    boundaries.
    """

    context = validate_formal_context(expected_context)
    record = _closed(
        value,
        ATTEMPT_CONSUMPTION_FIELDS,
        "formal attempt consumption",
    )
    result = dict(record)
    result["created_at_utc"] = _timestamp(
        record["created_at_utc"],
        "formal attempt consumption timestamp",
    )
    result["campaign_root_identity"] = _identity(
        record["campaign_root_identity"],
        "formal attempt consumption campaign root",
    )
    if (
        record["schema_version"] != ATTEMPT_CONSUMPTION_SCHEMA
        or record["consumed"] is not True
        or record["retry_eligible"] is not False
        or record["formal_dir"] != context["formal_attempt_dir"]
        or result["campaign_root_identity"] != context["campaign_root_identity"]
        or record["package_id"] != context["package_id"]
        or record["authorizations"] != closeout_state.FALSE_AUTHORIZATIONS
        or record["lower_bound"] is not None
        or record["upper_bound"] != [1188, 18]
        or record["production_certified"] is not False
    ):
        raise FormalLaunchValidationError(
            "formal attempt consumption crossed its state/claim boundary"
        )
    return result


def read_canonical_record(
    path: Path | str,
    *,
    expected_identity: Mapping[str, object] | None,
    label: str,
    require_published: bool = True,
) -> tuple[dict[str, Any], dict[str, object]]:
    """Read canonical bytes from a published record or selected sealed memfd.

    The embedded ``publisher`` object identifies the selected publication
    protocol; it is not treated as proof that a historical O_EXCL call
    happened.  With ``require_published`` the evidence available to this
    consumer is the real file: a stable same-FD read, an exact 0444/nlink=1
    named-file identity, and canonical bytes joined to the expected detached
    identity.  The sole nonpublished form is a fully sealed
    ``/proc/self/fd/N`` memfd used before owner publication.
    """

    if require_published:
        try:
            snapshot = authority.snapshot_regular(path)
        except authority.AuthorityError as exc:
            raise FormalLaunchValidationError(
                f"{label} publication snapshot failed: {exc}"
            ) from exc
        try:
            named = os.stat(snapshot.path, follow_symlinks=False)
        except OSError as exc:
            raise FormalLaunchValidationError(
                f"{label} publication readback is unavailable"
            ) from exc
        if (
            not stat.S_ISREG(named.st_mode)
            or named.st_nlink != 1
            or stat.S_IMODE(named.st_mode) != 0o444
            or int(named.st_dev) != snapshot.device
            or int(named.st_ino) != snapshot.inode
            or int(named.st_size) != snapshot.size_bytes
            or stat.S_IMODE(named.st_mode) != snapshot.mode
        ):
            raise FormalLaunchValidationError(
                f"{label} publication readback identity/mode drifted"
            )
    else:
        match = re.fullmatch(r"/proc/self/fd/([0-9]+)", os.fspath(path))
        if match is None or int(match.group(1)) < 3:
            raise FormalLaunchValidationError(
                f"{label} nonpublished input is not one selected sealed FD"
            )
        descriptor = os.dup(int(match.group(1)))
        try:
            before = os.fstat(descriptor)
            required_seals = (
                LINUX_F_SEAL_SEAL
                | LINUX_F_SEAL_SHRINK
                | LINUX_F_SEAL_GROW
                | LINUX_F_SEAL_WRITE
            )
            if (
                not stat.S_ISREG(before.st_mode)
                or fcntl.fcntl(descriptor, LINUX_F_GET_SEALS) & required_seals
                != required_seals
            ):
                raise FormalLaunchValidationError(
                    f"{label} selected FD is not one sealed regular memfd"
                )
            os.lseek(descriptor, 0, os.SEEK_SET)
            chunks: list[bytes] = []
            while True:
                block = os.read(descriptor, 1024 * 1024)
                if not block:
                    break
                chunks.append(block)
            after = os.fstat(descriptor)
        except OSError as exc:
            raise FormalLaunchValidationError(
                f"{label} selected FD replay failed"
            ) from exc
        finally:
            os.close(descriptor)
        stable = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_uid",
            "st_gid",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        raw = b"".join(chunks)
        if (
            any(getattr(before, field) != getattr(after, field) for field in stable)
            or len(raw) != before.st_size
        ):
            raise FormalLaunchValidationError(
                f"{label} selected FD changed during same-FD replay"
            )
        snapshot = authority.Snapshot(
            path=Path(os.fspath(path)),
            data=raw,
            device=int(after.st_dev),
            inode=int(after.st_ino),
            mode=stat.S_IMODE(after.st_mode),
            size_bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
        )
    try:
        value = authority.strict_loads(snapshot.data, label)
    except authority.AuthorityError as exc:
        raise FormalLaunchValidationError(
            f"{label} canonical publication parse failed: {exc}"
        ) from exc
    if type(value) is not dict:
        raise FormalLaunchValidationError(f"{label} is not one JSON object")
    if authority.canonical_json(value) != snapshot.data:
        raise FormalLaunchValidationError(f"{label} bytes are not canonical")
    identity = authority.detached_identity(snapshot)
    if expected_identity is not None and identity != _identity(expected_identity, f"{label} expected identity"):
        raise FormalLaunchValidationError(f"{label} identity drifted")
    publication_path = value.get("publication_path")
    publisher = value.get("publisher")
    if require_published and (publication_path is not None or publisher is not None):
        if publication_path != str(snapshot.path):
            raise FormalLaunchValidationError(
                f"{label} publication path does not join actual readback"
            )
        if type(publisher) is not dict or publisher.get("output_path") != str(snapshot.path):
            raise FormalLaunchValidationError(
                f"{label} publisher output path does not join actual readback"
            )
    return dict(value), identity


def validate_argv(value: object, label: str = "argv") -> list[str]:
    """Public helper for closed external command records."""

    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or not value
        or any(type(item) is not str or not item for item in value)
    ):
        raise FormalLaunchValidationError(f"{label} is malformed")
    return list(value)


def validate_detached_identity(value: object, label: str) -> dict[str, object]:
    """Public closed detached-identity validator for sibling formal roles."""

    return _identity(value, label)


def validate_message_identity(value: object, label: str) -> dict[str, object]:
    """Public closed in-protocol message-identity validator."""

    return _message_identity(value, label)


def validate_lock_identities(value: object) -> list[dict[str, object]]:
    """Public exact three-lock identity validator."""

    return _lock_identities(value)


def validate_process_identity(value: object, label: str) -> dict[str, int]:
    """Public exact PID/starttime validator."""

    return _process(value, label)


def validate_guardian_unit_identity(value: object) -> dict[str, object]:
    """Public exact guardian unit/cgroup/process validator."""

    return _guardian_unit(value)


def validate_control_socket_identity(value: object) -> dict[str, object]:
    """Public exact AF_UNIX pathname identity projection validator."""

    return _control_socket_identity(value)


def validate_supervisor_death_watch(
    value: object,
    *,
    expected_process_identity: Mapping[str, object],
) -> dict[str, object]:
    """Public validator for the pidfd watch armed before guardian readiness."""

    return _supervisor_death_watch(
        value,
        expected_process_identity=expected_process_identity,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--emit-context", action="store_true")
    mode.add_argument("--candidate", type=Path)
    parser.add_argument("--kind", choices=("admission", "selection"))
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--guardian-ready", type=Path)
    parser.add_argument("--attempt-consumption", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Independently replay one rendered artifact without publishing it."""

    args = _parser().parse_args(argv)
    try:
        context = replay_formal_launch_context(authority, args.campaign_dir)
        if args.emit_context:
            if any(
                value is not None
                for value in (
                    args.kind,
                    args.admission,
                    args.guardian_ready,
                    args.attempt_consumption,
                )
            ):
                raise FormalLaunchValidationError(
                    "context emission received candidate-validation inputs"
                )
            sys.stdout.buffer.write(authority.canonical_json(context))
            sys.stdout.buffer.flush()
            return 0
        if args.candidate is None or args.kind is None:
            raise FormalLaunchValidationError(
                "candidate validation lacks candidate or kind"
            )
        candidate, candidate_identity = read_canonical_record(
            args.candidate,
            expected_identity=None,
            label="formal launch validation candidate",
            require_published=False,
        )
        if args.kind == "admission":
            if any(
                value is not None
                for value in (
                    args.admission,
                    args.guardian_ready,
                    args.attempt_consumption,
                )
            ):
                raise FormalLaunchValidationError(
                    "admission validation received selection-only inputs"
                )
            validate_admission(candidate, expected_context=context)
        else:
            if (
                args.admission is None
                or args.guardian_ready is None
                or args.attempt_consumption is None
            ):
                raise FormalLaunchValidationError(
                    "selection validation lacks prerequisite paths"
                )
            admission, admission_identity = read_canonical_record(
                args.admission,
                expected_identity=None,
                label="formal launch admission",
            )
            guardian, guardian_identity = read_canonical_record(
                args.guardian_ready,
                expected_identity=None,
                label="outer guardian ready",
            )
            consumption, consumption_identity = read_canonical_record(
                args.attempt_consumption,
                expected_identity=None,
                label="formal attempt consumption",
            )
            validate_selection(
                candidate,
                admission=admission,
                admission_identity=admission_identity,
                guardian_ready=guardian,
                guardian_ready_identity=guardian_identity,
                attempt_consumption=consumption,
                attempt_consumption_identity=consumption_identity,
                expected_context=context,
            )
    except BaseException as exc:
        print(f"FAIL_CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "candidate_identity": candidate_identity,
                "kind": args.kind,
                "status": "PASS",
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
