from __future__ import annotations

import ast
from copy import deepcopy
import ctypes
from dataclasses import dataclass
import fcntl
import hashlib
import inspect
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import threading
import time
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from docs.research.noncert_cuts_ab16_20260724 import ab16_authority_v2 as authority
from docs.research.noncert_cuts_ab16_20260724 import ab16_campaign_bootstrap_v2 as bootstrap
from docs.research.noncert_cuts_ab16_20260724 import ab16_formal_controller_v1 as controller
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_formal_orchestrator_v1 as formal_orchestrator,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_formal_launch_authority_v1 as launch_authority,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_formal_launch_validator_v1 as launch_validator,
)
from docs.research.noncert_cuts_ab16_20260724 import ab16_formal_loader_v1 as loader
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_formal_success_verifier_v1 as success_verifier,
)
from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_outer_closeout_state_v1 as closeout_state,
)
from docs.research.noncert_cuts_ab16_20260724 import ab16_outer_guardian_v1 as guardian


def _identity(root: Path, name: str, token: str = "a") -> dict[str, object]:
    return {
        "path": str(root / name),
        "sha256": token * 64,
        "size_bytes": 17,
    }


def _mode_identity(
    identity: dict[str, object],
    *,
    mode: int,
) -> dict[str, object]:
    return {"mode": mode, **identity}


def _publisher(
    *,
    campaign_dir: Path,
    formal_admission_path: Path,
    formal_attempt_dir: Path,
    guardian_ready_path: Path,
    kind: str,
    output_path: Path,
    owner_driver_identity: dict[str, object],
    mechanical_publisher_identity: dict[str, object],
    python_identity: dict[str, object],
    renderer_identity: dict[str, object],
    validator_identity: dict[str, object],
) -> dict[str, object]:
    prerequisites = (
        []
        if kind == "admission"
        else [
            "--admission",
            str(formal_admission_path),
            "--guardian-ready",
            str(guardian_ready_path),
            "--attempt-consumption",
            str(formal_attempt_dir / "attempt-consumption.json"),
        ]
    )
    return {
        "actor": {
            "pid": 901,
            "role": launch_validator.OWNER_PUBLISHER_ROLE,
            "session_id": "formal-owner-session-a001",
            "starttime": 123_456,
        },
        "argv": {
            "mechanical_publish": [
                "OWNER_OEXCL_PUBLISH_V1",
                output_path.name,
            ],
            "render": [
                "formal-launch-authority",
                "--campaign-dir",
                str(campaign_dir),
                "--draft",
                launch_validator.OWNER_MEMFD_PATH,
                "--kind",
                kind,
                *prerequisites,
            ],
            "validate": [
                "formal-launch-validator",
                "--campaign-dir",
                str(campaign_dir),
                "--candidate",
                launch_validator.OWNER_MEMFD_PATH,
                "--kind",
                kind,
                *prerequisites,
            ],
        },
        "execution_strategy": launch_validator.OWNER_EXECUTION_STRATEGY,
        "formal_launch_owner_driver_identity": owner_driver_identity,
        "mechanical_oexcl_publisher_identity": mechanical_publisher_identity,
        "output_mode": 0o444,
        "output_path": str(output_path),
        "python_identity": python_identity,
        "renderer_identity": renderer_identity,
        "validator_identity": validator_identity,
    }


@dataclass(frozen=True)
class FormalFixture:
    context: dict[str, object]
    admission: dict[str, object]
    admission_identity: dict[str, object]
    guardian_ready: dict[str, object]
    guardian_ready_identity: dict[str, object]
    attempt_consumption: dict[str, object]
    attempt_consumption_identity: dict[str, object]
    selection: dict[str, object]
    lock_identities: list[dict[str, object]]


def _formal_fixture(tmp_path: Path) -> FormalFixture:
    campaign = tmp_path / "campaign"
    formal = campaign / "formal-ab16"
    attempt = formal / "formal-attempt-a001"
    snapshot = campaign / "campaign-authority" / "repository-snapshot"
    admission_path = formal / "formal-admission-a001.json"
    selection_path = formal / "formal-selection-a001.json"
    guardian_ready_path = formal / "outer-guardian-ready-a001.json"
    control_socket_path = formal / "outer-guardian-control.sock"

    campaign_root = _identity(campaign, "campaign-root.json", "1")
    gate1_selection = _identity(campaign, "gate1-v4/selection.json", "2")
    gate_b_approval = _identity(campaign, "gate-b-approval.json", "3")
    gate_b_epoch = _identity(campaign, "gate-b-epoch.json", "4")
    manager_epoch_observation = _identity(campaign, "manager-epoch.json", "5")
    package_manifest = _identity(campaign, "campaign-authority/package/manifest.json", "6")
    package_seal = _identity(campaign, "campaign-authority/package/seal.json", "7")
    snapshot_materialization = _identity(
        campaign,
        "campaign-authority/repository-snapshot-materialization.json",
        "8",
    )
    loader_identity = _identity(
        campaign,
        "campaign-authority/package/payload/tool.ab16_formal_loader_v1.py",
        "9",
    )
    authority_identity = _identity(
        campaign,
        "campaign-authority/package/payload/tool.ab16_authority_v2.py",
        "a",
    )
    python_identity = _identity(tmp_path, "platform/python3.13", "b")
    controller_identity = _identity(
        snapshot,
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_controller_v1.py",
        "c",
    )
    baseline_identity = _identity(
        snapshot,
        "docs/research/noncert_cuts_ab16_20260724/baseline_rebuild_v1.py",
        "d",
    )
    formal_orchestrator_identity = _identity(
        snapshot,
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_orchestrator_v1.py",
        "4",
    )
    guardian_runtime_identity = _identity(
        snapshot,
        "docs/research/noncert_cuts_ab16_20260724/ab16_outer_guardian_v1.py",
        "e",
    )
    renderer_identity = _identity(
        snapshot,
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_launch_authority_v1.py",
        "f",
    )
    validator_identity = _identity(
        snapshot,
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_launch_validator_v1.py",
        "0",
    )
    success_verifier_identity = _identity(
        snapshot,
        "docs/research/noncert_cuts_ab16_20260724/ab16_formal_success_verifier_v1.py",
        "1",
    )

    selected_literal = "selected-byte-launch-literal-v1"
    selected_identities = {
        "authority": _mode_identity(
            authority_identity,
            mode=launch_validator.PACKAGE_PAYLOAD_MODE,
        ),
        "loader": _mode_identity(
            loader_identity,
            mode=launch_validator.PACKAGE_PAYLOAD_MODE,
        ),
        "python": _mode_identity(python_identity, mode=0o555),
    }
    selected_identity_argument = json.dumps(
        selected_identities,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    selected_literal_raw = selected_literal.encode("utf-8")
    owner_driver_identity = {
        "sha256": "2" * 64,
        "size_bytes": 31,
    }
    mechanical_publisher_identity = {
        "sha256": "3" * 64,
        "size_bytes": 37,
    }

    receipt_paths = {
        name: str(attempt / f"{name.replace('_', '-')}.json")
        for name in launch_validator.OUTER_RECEIPT_PATH_FIELDS
    }
    arm_prelaunch_paths = {
        slot: {
            "receipt": str(attempt / "arm-prelaunch" / f"{slot}-receipt.json"),
            "request": str(attempt / "arm-prelaunch" / f"{slot}-request.json"),
        }
        for slot in closeout_state.ARM_SEQUENCE
    }
    gate1_prelaunch = str(attempt / "gate1-prelaunch-ownership.json")
    child_audit = str(attempt / "child-audit.json")
    outer_spec = {
        "arm_prelaunch_paths": arm_prelaunch_paths,
        "barrier_path": str(attempt / "outer-barrier-release.json"),
        "child_audit_path": child_audit,
        "controller_identity": controller_identity,
        "gate1_prelaunch_ownership_path": gate1_prelaunch,
        "loader_identity": loader_identity,
        "python_identity": python_identity,
        "receipt_paths": receipt_paths,
        "resource_contract": dict(launch_validator.OUTER_RESOURCE_CONTRACT),
        "selected_byte_argv": [
            "/proc/self/fd/3",
            "-I",
            "-B",
            "-c",
            selected_literal,
            "systemd-openfile",
            selected_identity_argument,
            "--campaign-dir",
            str(campaign),
            "--role",
            "formal-controller",
            "--",
            "--campaign-dir",
            str(campaign),
            "--formal-selection",
            str(selection_path),
        ],
        "unit_name": "ab16-formal-outer-a001.service",
        "working_directory": str(snapshot),
    }
    guardian_spec = {
        "resource_contract": dict(launch_validator.OUTER_RESOURCE_CONTRACT),
        "selected_byte_argv": [
            "/proc/self/fd/3",
            "-I",
            "-B",
            "-c",
            selected_literal,
            "systemd-openfile",
            selected_identity_argument,
            "--campaign-dir",
            str(campaign),
            "--role",
            "outer-guardian",
            "--",
            "--campaign-dir",
            str(campaign),
            "--formal-admission",
            str(admission_path),
            "--control-socket",
            str(control_socket_path),
            "--ready-output",
            str(guardian_ready_path),
        ],
        "unit_name": "ab16-outer-guardian-a001.service",
        "working_directory": str(snapshot),
    }
    manager_epoch = {
        "boot_id": "b" * 32,
        "dbus_unique_owner": ":1.700",
        "manager_invocation_id": "c" * 32,
        "manager_pid": 700,
    }
    context = {
        "authority_scope": launch_validator.AUTHORITY_SCOPE,
        "baseline_identity": baseline_identity,
        "campaign_dir": str(campaign),
        "campaign_root_identity": campaign_root,
        "controller_identity": controller_identity,
        "dual_holder_platform_assumption": launch_validator.DUAL_HOLDER_PLATFORM_ASSUMPTION,
        "formal_admission_path": str(admission_path),
        "formal_attempt_dir": str(attempt),
        "formal_loader_identity": loader_identity,
        "formal_launch_owner_driver_identity": owner_driver_identity,
        "formal_orchestrator_identity": formal_orchestrator_identity,
        "formal_selection_path": str(selection_path),
        "gate1_selection_identity": gate1_selection,
        "gate_b_approval_identity": gate_b_approval,
        "gate_b_epoch_observation_identity": gate_b_epoch,
        "guardian_control_socket_path": str(control_socket_path),
        "guardian_runtime_identity": guardian_runtime_identity,
        "guardian_ready_path": str(guardian_ready_path),
        "guardian_spec": guardian_spec,
        "launch_renderer_identity": renderer_identity,
        "launch_validator_identity": validator_identity,
        "manager_epoch": manager_epoch,
        "manager_epoch_observation_identity": manager_epoch_observation,
        "mechanical_oexcl_publisher_identity": mechanical_publisher_identity,
        "outer_spec": outer_spec,
        "package_id": "d" * 64,
        "package_manifest_identity": package_manifest,
        "package_seal_identity": package_seal,
        "python_identity": python_identity,
        "repository_head": "e" * 40,
        "schema_version": launch_validator.FORMAL_CONTEXT_SCHEMA,
        "selected_byte_launch_identity": {
            "sha256": hashlib.sha256(selected_literal_raw).hexdigest(),
            "size_bytes": len(selected_literal_raw),
        },
        "snapshot_materialization_identity": snapshot_materialization,
        "snapshot_root": str(snapshot),
        "status": "PASS",
        "success_verifier_identity": success_verifier_identity,
    }

    admission_publisher = _publisher(
        campaign_dir=campaign,
        formal_admission_path=admission_path,
        formal_attempt_dir=attempt,
        guardian_ready_path=guardian_ready_path,
        kind="admission",
        output_path=admission_path,
        owner_driver_identity=owner_driver_identity,
        mechanical_publisher_identity=mechanical_publisher_identity,
        python_identity=python_identity,
        renderer_identity=renderer_identity,
        validator_identity=validator_identity,
    )
    admission = {
        "admission_id": "formal-admission-a001",
        "authority_scope": launch_validator.AUTHORITY_SCOPE,
        "authorizations": dict(launch_validator.FALSE_CLAIMS),
        "baseline_launch_authorized": False,
        "campaign_dir": str(campaign),
        "campaign_root_identity": campaign_root,
        "controller_launch_authorized": False,
        "created_at_utc": "2026-07-28T00:00:00Z",
        "formal_attempt_dir": str(attempt),
        "formal_attempt_selected": False,
        "formal_selection_path": str(selection_path),
        "formal_selection_publication_authorized": True,
        "gate_b_approval_identity": gate_b_approval,
        "gate_b_epoch_observation_identity": gate_b_epoch,
        "guardian_control_socket_path": str(control_socket_path),
        "guardian_launch_authorized": True,
        "guardian_ready_path": str(guardian_ready_path),
        "guardian_spec": guardian_spec,
        "manager_epoch": manager_epoch,
        "manager_epoch_observation_identity": manager_epoch_observation,
        "outer_launch_authorized": False,
        "package_id": context["package_id"],
        "package_manifest_identity": package_manifest,
        "package_seal_identity": package_seal,
        "publication_path": str(admission_path),
        "publisher": admission_publisher,
        "repository_head": context["repository_head"],
        "schema_version": launch_validator.FORMAL_ADMISSION_SCHEMA,
        "snapshot_materialization_identity": snapshot_materialization,
        "snapshot_root": str(snapshot),
        "status": "ADMITTED",
    }
    admission_identity = _identity(formal, admission_path.name, "2")

    lock_identities = [
        {
            "device": 100 + index,
            "inode": 200 + index,
            "path": path,
            "uid": os.getuid(),
        }
        for index, path in enumerate(closeout_state.LOCK_PATHS)
    ]
    guardian_process = {"pid": 902, "starttime": 123_457}
    supervisor_process = {"pid": 903, "starttime": 123_458}
    guardian_unit = {
        "control_group": "/user.slice/ab16-outer-guardian-a001.service",
        "invocation_id": "1" * 32,
        "processes": [guardian_process],
        "unit_name": "ab16-outer-guardian-a001.service",
    }
    guardian_ready = {
        "authority_scope": launch_validator.AUTHORITY_SCOPE,
        "authorizations": dict(launch_validator.FALSE_CLAIMS),
        "campaign_dir": str(campaign),
        "campaign_root_identity": campaign_root,
        "control_socket_identity": {
            "device": 301,
            "inode": 401,
            "mode": 0o600,
            "path": str(control_socket_path),
            "uid": os.getuid(),
        },
        "created_at_utc": "2026-07-28T00:01:00Z",
        "dual_holder_platform_assumption": launch_validator.DUAL_HOLDER_PLATFORM_ASSUMPTION,
        "formal_admission_identity": admission_identity,
        "formal_launch_authorized": False,
        "guardian_process_identity": guardian_process,
        "guardian_runtime_identity": guardian_runtime_identity,
        "guardian_unit_identity": guardian_unit,
        "handoff_message_identity": {"sha256": "3" * 64, "size_bytes": 19},
        "lock_identities": lock_identities,
        "manager_epoch": manager_epoch,
        "package_id": context["package_id"],
        "schema_version": launch_validator.GUARDIAN_READY_SCHEMA,
        "status": "READY",
        "success_eligible": False,
        "supervisor_death_watch": {
            "method": "linux-pidfd-open-v1",
            "process_identity": supervisor_process,
            "status": "ARMED",
        },
        "supervisor_process_identity": supervisor_process,
    }
    guardian_ready_identity = _identity(formal, guardian_ready_path.name, "4")

    attempt_consumption = {
        "authorizations": dict(closeout_state.FALSE_AUTHORIZATIONS),
        "campaign_root_identity": campaign_root,
        "consumed": True,
        "created_at_utc": "2026-07-28T00:02:00Z",
        "formal_dir": str(attempt),
        "lower_bound": None,
        "package_id": context["package_id"],
        "production_certified": False,
        "retry_eligible": False,
        "schema_version": launch_validator.ATTEMPT_CONSUMPTION_SCHEMA,
        "upper_bound": [1188, 18],
    }
    attempt_consumption_identity = _identity(
        attempt,
        "attempt-consumption.json",
        "5",
    )

    selection = {
        "arm_prelaunch_paths": arm_prelaunch_paths,
        "attempt_consumption_identity": attempt_consumption_identity,
        "authority_scope": launch_validator.AUTHORITY_SCOPE,
        "authorizations": dict(launch_validator.FALSE_CLAIMS),
        "baseline_identity": baseline_identity,
        "baseline_launch_authorized": True,
        "campaign_dir": str(campaign),
        "campaign_root_identity": campaign_root,
        "child_audit_path": child_audit,
        "consumed": True,
        "controller_identity": controller_identity,
        "controller_launch_authorized": True,
        "created_at_utc": "2026-07-28T00:03:00Z",
        "formal_admission_identity": admission_identity,
        "formal_attempt_dir": str(attempt),
        "formal_attempt_selected": True,
        "gate1_prelaunch_ownership_path": gate1_prelaunch,
        "gate1_selection_identity": gate1_selection,
        "gate_b_approval_identity": gate_b_approval,
        "gate_b_epoch_observation_identity": gate_b_epoch,
        "guardian_ready_identity": guardian_ready_identity,
        "guardian_runtime_identity": guardian_runtime_identity,
        "guardian_spec": guardian_spec,
        "guardian_unit_identity": guardian_unit,
        "lock_identities": lock_identities,
        "manager_epoch": manager_epoch,
        "manager_epoch_observation_identity": manager_epoch_observation,
        "outer_launch_authorized": True,
        "outer_spec": outer_spec,
        "package_id": context["package_id"],
        "package_manifest_identity": package_manifest,
        "package_seal_identity": package_seal,
        "publication_path": str(selection_path),
        "publisher": _publisher(
            campaign_dir=campaign,
            formal_admission_path=admission_path,
            formal_attempt_dir=attempt,
            guardian_ready_path=guardian_ready_path,
            kind="selection",
            output_path=selection_path,
            owner_driver_identity=owner_driver_identity,
            mechanical_publisher_identity=mechanical_publisher_identity,
            python_identity=python_identity,
            renderer_identity=renderer_identity,
            validator_identity=validator_identity,
        ),
        "repository_head": context["repository_head"],
        "retry_eligible": False,
        "schema_version": launch_validator.FORMAL_SELECTION_SCHEMA,
        "selection_id": "formal-selection-a001",
        "snapshot_materialization_identity": snapshot_materialization,
        "snapshot_root": str(snapshot),
        "status": "SELECTED",
    }

    return FormalFixture(
        context=context,
        admission=admission,
        admission_identity=admission_identity,
        guardian_ready=guardian_ready,
        guardian_ready_identity=guardian_ready_identity,
        attempt_consumption=attempt_consumption,
        attempt_consumption_identity=attempt_consumption_identity,
        selection=selection,
        lock_identities=lock_identities,
    )


def _validate_selection(fixture: FormalFixture) -> dict[str, object]:
    return launch_validator.validate_selection(
        fixture.selection,
        admission=fixture.admission,
        admission_identity=fixture.admission_identity,
        guardian_ready=fixture.guardian_ready,
        guardian_ready_identity=fixture.guardian_ready_identity,
        attempt_consumption=fixture.attempt_consumption,
        attempt_consumption_identity=fixture.attempt_consumption_identity,
        expected_context=fixture.context,
    )


def test_formal_context_v2_rejects_legacy_and_mixed_orchestrator_identity(
    tmp_path: Path,
) -> None:
    fixture = _formal_fixture(tmp_path)
    checked = launch_validator.validate_formal_context(fixture.context)
    assert checked["formal_orchestrator_identity"] == (
        fixture.context["formal_orchestrator_identity"]
    )

    legacy = dict(fixture.context)
    legacy.pop("formal_orchestrator_identity")
    legacy["schema_version"] = "noncert-cuts-ab16-formal-launch-context-v1"
    with pytest.raises(
        launch_validator.FormalLaunchValidationError,
        match="field set drifted",
    ):
        launch_validator.validate_formal_context(legacy)

    mixed = dict(fixture.context)
    mixed["schema_version"] = "noncert-cuts-ab16-formal-launch-context-v1"
    with pytest.raises(
        launch_validator.FormalLaunchValidationError,
        match="scalar drifted",
    ):
        launch_validator.validate_formal_context(mixed)


def _call_name(node: ast.Call) -> str:
    cursor = node.func
    parts: list[str] = []
    while isinstance(cursor, ast.Attribute):
        parts.append(cursor.attr)
        cursor = cursor.value
    if isinstance(cursor, ast.Name):
        parts.append(cursor.id)
    return ".".join(reversed(parts))


def test_bootstrap_dag_seals_before_materialization_without_packaging_future_receipt() -> None:
    tree = ast.parse(inspect.getsource(bootstrap.bootstrap_campaign))
    calls = sorted(
        ((node.lineno, _call_name(node)) for node in ast.walk(tree) if isinstance(node, ast.Call)),
        key=lambda item: item[0],
    )
    lines = {name: line for line, name in calls}

    assert (
        lines["_build_repository_snapshot_sources"]
        < lines["authority.build_package"]
        < lines["_materialize_repository_snapshot"]
        < lines["authority.build_campaign_root"]
    )
    package_roles_source = inspect.getsource(bootstrap._package_roles)
    assert "SNAPSHOT_MATERIALIZATION_INPUT_ROLE" not in package_roles_source
    bootstrap_source = inspect.getsource(bootstrap.bootstrap_campaign)
    receipt_assignment = bootstrap_source.index(
        "inputs[SNAPSHOT_MATERIALIZATION_INPUT_ROLE] = dict(materialization_receipt)"
    )
    receipt_validation = bootstrap_source.index(
        "if not isinstance(materialization_receipt, Mapping):"
    )
    assert bootstrap_source.index("_materialize_repository_snapshot(") < receipt_assignment
    assert receipt_validation < receipt_assignment
    assert receipt_assignment < bootstrap_source.index("authority.build_campaign_root(")


def test_launch_renderers_are_pure_canonical_and_publication_is_no_overwrite(
    tmp_path: Path,
) -> None:
    fixture = _formal_fixture(tmp_path)
    checked_admission = launch_validator.validate_admission(
        fixture.admission,
        expected_context=fixture.context,
    )
    admission_raw = launch_authority.render_admission(
        fixture.admission,
        expected_context=fixture.context,
    )
    assert authority.strict_loads(admission_raw, "rendered admission") == checked_admission
    assert not Path(str(fixture.context["formal_admission_path"])).exists()

    checked_selection = _validate_selection(fixture)
    selection_raw = launch_authority.render_selection(
        fixture.selection,
        admission=fixture.admission,
        admission_identity=fixture.admission_identity,
        guardian_ready=fixture.guardian_ready,
        guardian_ready_identity=fixture.guardian_ready_identity,
        attempt_consumption=fixture.attempt_consumption,
        attempt_consumption_identity=fixture.attempt_consumption_identity,
        expected_context=fixture.context,
    )
    assert authority.strict_loads(selection_raw, "rendered selection") == checked_selection
    assert not Path(str(fixture.context["formal_selection_path"])).exists()

    publication = tmp_path / "owner-publication.json"
    authority._write_exclusive(publication, admission_raw, mode=0o444)  # noqa: SLF001
    with pytest.raises(Exception):
        authority._write_exclusive(publication, admission_raw, mode=0o444)  # noqa: SLF001
    assert publication.read_bytes() == admission_raw


def test_readonly_publication_uses_mode_as_completion_signal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publication = tmp_path / "readonly-publication.json"
    raw = authority.canonical_json({"status": "PASS"})
    real_write = authority.os.write
    real_fchmod = authority.os.fchmod
    real_fsync = authority.os.fsync
    events: list[str] = []

    def observe_write(descriptor: int, data: bytes | bytearray | memoryview) -> int:
        events.append(f"write:{stat.S_IMODE(os.fstat(descriptor).st_mode):04o}")
        return real_write(descriptor, data)

    def observe_fsync(descriptor: int) -> None:
        events.append(f"fsync:{stat.S_IMODE(os.fstat(descriptor).st_mode):04o}")
        real_fsync(descriptor)

    def observe_fchmod(descriptor: int, mode: int) -> None:
        events.append(f"fchmod:{mode:04o}")
        real_fchmod(descriptor, mode)

    monkeypatch.setattr(authority.os, "write", observe_write)
    monkeypatch.setattr(authority.os, "fsync", observe_fsync)
    monkeypatch.setattr(authority.os, "fchmod", observe_fchmod)
    identity = authority._write_exclusive(  # noqa: SLF001
        publication,
        raw,
        mode=0o444,
    )

    assert events == [
        "write:0600",
        "fsync:0600",
        "fchmod:0444",
        "fsync:0444",
    ]
    assert stat.S_IMODE(publication.stat().st_mode) == 0o444
    assert publication.read_bytes() == raw
    assert identity == authority.detached_identity(
        authority.snapshot_regular(publication)
    )


def test_formal_controller_waits_for_readonly_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "arm-prelaunch-receipt.json"
    candidate.write_bytes(authority.canonical_json({"status": "PASS"}))
    candidate.chmod(0o600)
    sleeps: list[float] = []

    def complete_publication(seconds: float) -> None:
        sleeps.append(seconds)
        candidate.chmod(0o444)

    monkeypatch.setattr(controller.time, "sleep", complete_publication)
    record, identity = controller._wait_for_record(  # noqa: SLF001
        candidate,
        timeout_seconds=1.0,
        label="arm prelaunch receipt",
    )

    assert record == {"status": "PASS"}
    assert identity["path"] == str(candidate)
    assert sleeps == [0.05]


@pytest.mark.parametrize(
    "mutation",
    ("mode", "hardlink", "noncanonical", "identity", "publisher-path"),
)
def test_formal_published_record_readback_is_actual_stable_canonical_0444(
    tmp_path: Path,
    mutation: str,
) -> None:
    published = tmp_path / "formal-admission-a001.json"
    record = {
        "publication_path": str(published),
        "publisher": {"output_path": str(published)},
        "schema_version": "focused-publication-readback-v1",
    }
    raw = authority.canonical_json(record)
    published.write_bytes(raw)
    published.chmod(0o444)
    expected = authority.detached_identity(authority.snapshot_regular(published))

    if mutation == "mode":
        published.chmod(0o644)
    elif mutation == "hardlink":
        os.link(published, tmp_path / "second-name.json")
    elif mutation == "noncanonical":
        published.chmod(0o644)
        published.write_text(json.dumps(record), encoding="utf-8")
        published.chmod(0o444)
    elif mutation == "identity":
        expected["sha256"] = "f" * 64
    else:
        published.chmod(0o644)
        record["publisher"]["output_path"] = str(tmp_path / "claimed.json")
        published.write_bytes(authority.canonical_json(record))
        published.chmod(0o444)

    with pytest.raises(
        launch_validator.FormalLaunchValidationError,
    ):
        launch_validator.read_canonical_record(
            published,
            expected_identity=expected,
            label="focused published formal record",
        )


def test_formal_published_record_readback_returns_actual_identity(
    tmp_path: Path,
) -> None:
    published = tmp_path / "formal-selection-a001.json"
    record = {
        "publication_path": str(published),
        "publisher": {"output_path": str(published)},
        "schema_version": "focused-publication-readback-v1",
    }
    published.write_bytes(authority.canonical_json(record))
    published.chmod(0o444)
    expected = authority.detached_identity(authority.snapshot_regular(published))

    checked, observed = launch_validator.read_canonical_record(
        published,
        expected_identity=expected,
        label="focused published formal record",
    )

    assert checked == record
    assert observed == expected


def test_formal_render_candidate_requires_sealed_memfd_not_published_mode() -> None:
    raw = authority.canonical_json({"draft": True})
    syscall_number = {"x86_64": 319, "aarch64": 279}.get(os.uname().machine)
    if syscall_number is None:
        pytest.skip("focused memfd syscall number is not registered for this architecture")
    libc = ctypes.CDLL(None, use_errno=True)
    descriptor = int(
        libc.syscall(
            syscall_number,
            b"ab16-formal-render-candidate",
            0x0001 | 0x0002,
        )
    )
    assert descriptor >= 0, os.strerror(ctypes.get_errno())
    try:
        os.write(descriptor, raw)
        path = f"/proc/self/fd/{descriptor}"
        with pytest.raises(
            launch_validator.FormalLaunchValidationError,
            match="sealed regular memfd",
        ):
            launch_validator.read_canonical_record(
                path,
                expected_identity=None,
                label="unsealed formal render candidate",
                require_published=False,
            )
        fcntl.fcntl(
            descriptor,
            1033,
            launch_validator.LINUX_F_SEAL_SEAL
            | launch_validator.LINUX_F_SEAL_SHRINK
            | launch_validator.LINUX_F_SEAL_GROW
            | launch_validator.LINUX_F_SEAL_WRITE,
        )
        checked, identity = launch_validator.read_canonical_record(
            path,
            expected_identity=None,
            label="sealed formal render candidate",
            require_published=False,
        )
    finally:
        os.close(descriptor)

    assert checked == {"draft": True}
    assert identity == {
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


OWNER_REQUEST_SCHEMA = "noncert-cuts-ab16-formal-launch-owner-request-v1"
OWNER_CLEAN_ENV = {
    "LANG": "C",
    "LC_ALL": "C",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONNOUSERSITE": "1",
    "TZ": "UTC",
}


@dataclass
class OwnerDriverProbe:
    process: subprocess.Popen[bytes]
    control: socket.socket
    context: dict[str, object]
    ready: dict[str, object] | None


def _literal_identity(source: str) -> dict[str, object]:
    raw = source.encode("utf-8")
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _selected_file_identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "mode": path.stat().st_mode & 0o7777,
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _focused_sealed_memfd(name: str, raw: bytes, *, seal: bool = True) -> int:
    libc = ctypes.CDLL(None, use_errno=True)
    create = libc.memfd_create
    create.argtypes = (ctypes.c_char_p, ctypes.c_uint)
    create.restype = ctypes.c_int
    descriptor = int(
        create(
            name.encode("ascii"),
            0x0001 | 0x0002,
        )
    )
    assert descriptor >= 0, os.strerror(ctypes.get_errno())
    os.write(descriptor, raw)
    os.lseek(descriptor, 0, os.SEEK_SET)
    if seal:
        fcntl.fcntl(
            descriptor,
            1033,
            launch_validator.LINUX_F_SEAL_SEAL
            | launch_validator.LINUX_F_SEAL_SHRINK
            | launch_validator.LINUX_F_SEAL_GROW
            | launch_validator.LINUX_F_SEAL_WRITE,
        )
    return descriptor


def _process_starttime(pid: int) -> int:
    raw = Path(f"/proc/{pid}/stat").read_bytes()
    marker = raw.rfind(b") ")
    assert marker >= 0
    return int(raw[marker + 2 :].split()[19])


def _owner_response(control: socket.socket) -> dict[str, object] | None:
    raw = control.recv(16 * 1024 * 1024)
    return None if not raw else json.loads(raw)


def _owner_request(
    *,
    actor: dict[str, object],
    sequence: int,
    kind: str,
) -> bytes:
    return authority.canonical_json(
        {
            "draft": {
                "kind": kind,
                "publisher": {"actor": actor},
            },
            "kind": kind,
            "schema_version": OWNER_REQUEST_SCHEMA,
            "sequence": sequence,
        }
    )


def _owner_handoff() -> bytes:
    return authority.canonical_json(
        {
            "kind": "handoff-complete",
            "schema_version": OWNER_REQUEST_SCHEMA,
            "sequence": 3,
        }
    )


def _start_owner_driver(
    tmp_path: Path,
    *,
    publisher_source: str = bootstrap.OWNER_OEXCL_PUBLISH_V1,
    seal_publisher: bool = True,
) -> OwnerDriverProbe:
    campaign = tmp_path / "campaign"
    formal = campaign / "formal-ab16"
    attempt = formal / "formal-attempt-a001"
    formal.mkdir(parents=True)
    attempt.mkdir()
    loader_path = tmp_path / "selected/fake-formal-loader.py"
    authority_path = tmp_path / "selected/fake-authority.py"
    loader_path.parent.mkdir(parents=True)
    loader_path.write_text(
        r"""
import fcntl
import hashlib
import json
import os
import stat
import sys

clean = {
    "LANG": "C",
    "LC_ALL": "C",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONNOUSERSITE": "1",
    "TZ": "UTC",
}
if dict(os.environ) != clean:
    raise SystemExit(121)
argv = sys.argv[1:]
try:
    loader_identity = json.loads(argv[1])
except (IndexError, json.JSONDecodeError):
    raise SystemExit(122)
if (
    argv[:1] != ["--loader-identity"]
    or set(loader_identity) != {"mode", "path", "sha256", "size_bytes"}
    or argv[2:4] != ["--authority-fd", "5"]
    or "--campaign-dir" not in argv
    or "--role" not in argv
    or "--" not in argv
    or not stat.S_ISREG(os.fstat(3).st_mode)
    or not stat.S_ISREG(os.fstat(4).st_mode)
    or not stat.S_ISREG(os.fstat(5).st_mode)
):
    raise SystemExit(122)
role = argv[argv.index("--role") + 1]
role_argv = argv[argv.index("--") + 1:]
kind = role_argv[role_argv.index("--kind") + 1]
input_flag = "--draft" if role == "formal-launch-authority" else "--candidate"
if (
    role not in {"formal-launch-authority", "formal-launch-validator"}
    or role_argv[role_argv.index(input_flag) + 1] != "/proc/self/fd/6"
    or os.fstat(6).st_nlink != 0
    or fcntl.fcntl(6, 1034) & 0x000f != 0x000f
):
    raise SystemExit(123)
os.lseek(6, 0, os.SEEK_SET)
raw = bytearray()
while True:
    chunk = os.read(6, 1024 * 1024)
    if not chunk:
        break
    raw.extend(chunk)
json.loads(raw)
if role == "formal-launch-authority":
    os.write(1, raw)
else:
    result = {
        "candidate_identity": {
            "path": "/proc/self/fd/6",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        },
        "kind": kind,
        "status": "PASS",
    }
    os.write(
        1,
        json.dumps(
            result,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8") + b"\n",
    )
""".strip()
        + "\n",
        encoding="utf-8",
    )
    authority_path.write_text("AUTHORITY = True\n", encoding="utf-8")
    loader_path.chmod(0o444)
    authority_path.chmod(0o444)
    python_path = Path(os.path.realpath(sys.executable))
    selected = {
        "authority": _selected_file_identity(authority_path),
        "loader": _selected_file_identity(loader_path),
        "python": _selected_file_identity(python_path),
    }
    selected_argument = json.dumps(
        selected,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    admission_path = formal / "formal-admission-a001.json"
    selection_path = formal / "formal-selection-a001.json"
    context = {
        "campaign_dir": str(campaign),
        "formal_admission_path": str(admission_path),
        "formal_attempt_dir": str(attempt),
        "formal_launch_owner_driver_identity": _literal_identity(
            bootstrap.FORMAL_LAUNCH_OWNER_DRIVER_V1
        ),
        "formal_selection_path": str(selection_path),
        "guardian_ready_path": str(formal / "outer-guardian-ready-a001.json"),
        "mechanical_oexcl_publisher_identity": _literal_identity(
            publisher_source
        ),
        "outer_spec": {
            "selected_byte_argv": [
                "/proc/self/fd/3",
                "-I",
                "-B",
                "-c",
                bootstrap.SELECTED_BYTE_LAUNCH_V1,
                "systemd-openfile",
                selected_argument,
            ]
        },
        "python_identity": {
            key: selected["python"][key]
            for key in ("path", "sha256", "size_bytes")
        },
        "selected_byte_launch_identity": _literal_identity(
            bootstrap.SELECTED_BYTE_LAUNCH_V1
        ),
    }
    context_raw = authority.canonical_json(context)
    publisher_descriptor = _focused_sealed_memfd(
        "ab16-focused-owner-publisher",
        publisher_source.encode("utf-8"),
        seal=seal_publisher,
    )
    context_descriptor = _focused_sealed_memfd(
        "ab16-focused-owner-context",
        context_raw,
    )
    python_descriptor = os.open(
        python_path,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    parent_control, child_control = socket.socketpair(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET,
    )
    parent_control.settimeout(10)
    wrapper = r"""
import fcntl
import os
import sys

driver, session_id, context_identity, driver_identity, python_path = sys.argv[1:6]
source_descriptors = [int(value) for value in sys.argv[6:10]]
copies = [
    fcntl.fcntl(descriptor, fcntl.F_DUPFD_CLOEXEC, 32)
    for descriptor in source_descriptors
]
for descriptor, target in zip(copies, (3, 4, 5, 6), strict=True):
    os.dup2(descriptor, target, inheritable=True)
clean = {
    "LANG": "C",
    "LC_ALL": "C",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONNOUSERSITE": "1",
    "TZ": "UTC",
}
os.execve(
    "/proc/self/fd/3",
    [
        python_path,
        "-I",
        "-B",
        "-c",
        driver,
        session_id,
        context_identity,
        driver_identity,
    ],
    clean,
)
"""
    context_identity = json.dumps(
        _literal_identity(context_raw.decode("utf-8")),
        separators=(",", ":"),
        sort_keys=True,
    )
    driver_identity = json.dumps(
        _literal_identity(bootstrap.FORMAL_LAUNCH_OWNER_DRIVER_V1),
        separators=(",", ":"),
        sort_keys=True,
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            wrapper,
            bootstrap.FORMAL_LAUNCH_OWNER_DRIVER_V1,
            "formal-owner-session-a001",
            context_identity,
            driver_identity,
            str(python_path),
            str(python_descriptor),
            str(publisher_descriptor),
            str(context_descriptor),
            str(child_control.fileno()),
        ],
        cwd=tmp_path,
        env=OWNER_CLEAN_ENV,
        pass_fds=(
            python_descriptor,
            publisher_descriptor,
            context_descriptor,
            child_control.fileno(),
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    child_control.close()
    os.close(python_descriptor)
    os.close(publisher_descriptor)
    os.close(context_descriptor)
    try:
        ready = _owner_response(parent_control)
    except (TimeoutError, ConnectionError):
        ready = None
    return OwnerDriverProbe(
        process=process,
        control=parent_control,
        context=context,
        ready=ready,
    )


def _finish_owner_probe(probe: OwnerDriverProbe) -> tuple[bytes, bytes]:
    probe.control.close()
    if probe.process.poll() is None:
        probe.process.terminate()
    return probe.process.communicate(timeout=10)


def test_formal_validator_emit_context_is_read_only_and_exclusive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _formal_fixture(tmp_path)
    monkeypatch.setattr(
        launch_validator,
        "replay_formal_launch_context",
        lambda _authority, _campaign_dir: fixture.context,
    )
    assert (
        launch_validator.main(
            [
                "--campaign-dir",
                str(tmp_path),
                "--emit-context",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.encode("utf-8") == authority.canonical_json(
        fixture.context
    )
    assert (
        launch_validator.main(
            [
                "--campaign-dir",
                str(tmp_path),
                "--emit-context",
                "--kind",
                "admission",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "context emission received candidate-validation inputs" in captured.err


def test_formal_owner_driver_uses_one_actor_and_fixed_selected_byte_protocol(
    tmp_path: Path,
) -> None:
    probe = _start_owner_driver(tmp_path)
    try:
        assert probe.ready is not None
        assert probe.ready["status"] == "READY"
        actor = probe.ready["actor"]
        assert actor["pid"] == probe.process.pid
        assert actor["starttime"] == _process_starttime(probe.process.pid)
        probe.control.send(
            _owner_request(actor=actor, sequence=1, kind="admission")
        )
        admission = _owner_response(probe.control)
        assert admission is not None
        assert admission["status"] == "PUBLISHED"
        assert admission["actor"] == actor
        admission_path = Path(str(probe.context["formal_admission_path"]))
        assert admission_path.stat().st_mode & 0o7777 == 0o444
        assert admission_path.stat().st_nlink == 1

        probe.control.send(
            _owner_request(actor=actor, sequence=2, kind="selection")
        )
        selection = _owner_response(probe.control)
        assert selection is not None
        assert selection["status"] == "PUBLISHED"
        assert selection["actor"] == actor
        assert probe.process.poll() is None
        assert _process_starttime(probe.process.pid) == actor["starttime"]
        probe.control.send(_owner_handoff())
        handoff = _owner_response(probe.control)
        assert handoff is not None
        assert handoff["status"] == "HANDOFF_COMPLETE"
        assert handoff["actor"] == actor
        stdout, stderr = probe.process.communicate(timeout=10)
        assert probe.process.returncode == 0, stderr
        assert stdout == b""
        selection_path = Path(str(probe.context["formal_selection_path"]))
        assert selection_path.stat().st_mode & 0o7777 == 0o444
        assert selection_path.stat().st_nlink == 1
    finally:
        if probe.process.poll() is None:
            _finish_owner_probe(probe)
        else:
            probe.control.close()

    source = bootstrap.FORMAL_LAUNCH_OWNER_DRIVER_V1
    assert "python_fd, publisher_fd, context_fd, control_fd = 3, 4, 5, 6" in source
    assert "for expected_sequence, expected_kind in ((1, \"admission\"), (2, \"selection\"))" in source
    assert "dict(os.environ) != clean" in source
    assert source.count("publisher_child(") == 2


def test_formal_orchestrator_builds_one_actor_admission_and_selection(
    tmp_path: Path,
) -> None:
    fixture = _formal_fixture(tmp_path)
    actor = fixture.admission["publisher"]["actor"]
    admission = formal_orchestrator.build_admission_draft(
        fixture.context,
        actor,
    )
    assert admission["publisher"]["actor"] == actor
    assert admission["guardian_launch_authorized"] is True
    assert admission["outer_launch_authorized"] is False

    selection = formal_orchestrator.build_selection_draft(
        fixture.context,
        actor,
        admission=admission,
        admission_identity=fixture.admission_identity,
        guardian_ready=fixture.guardian_ready,
        guardian_ready_identity=fixture.guardian_ready_identity,
        attempt_consumption=fixture.attempt_consumption,
        attempt_consumption_identity=fixture.attempt_consumption_identity,
    )
    assert selection["publisher"]["actor"] == actor
    assert selection["formal_admission_identity"] == fixture.admission_identity
    assert selection["guardian_ready_identity"] == fixture.guardian_ready_identity
    assert (
        selection["attempt_consumption_identity"]
        == fixture.attempt_consumption_identity
    )
    assert selection["lock_identities"] == fixture.lock_identities


def test_formal_orchestrator_fixed_order_keeps_owner_through_handoff() -> None:
    source = inspect.getsource(formal_orchestrator.orchestrate)
    assert source.index('kind="admission"') < source.index(
        "supervisor_thread.start()"
    )
    assert source.index('"outer guardian ready"') < source.index(
        'kind="selection"'
    )
    assert source.index('"formal attempt consumption"') < source.index(
        'kind="selection"'
    )
    assert source.index("supervisor_thread.join(") < source.index(
        "owner.complete_handoff()"
    )
    assert "role=\"formal-supervisor\"" in source


def test_formal_owner_cleanup_closes_stderr_even_when_kill_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent, child = socket.socketpair()
    stderr_read, stderr_write = os.pipe()
    os.close(stderr_write)
    session = formal_orchestrator.OwnerSession(
        pid=4242,
        control=parent,
        stderr_descriptor=stderr_read,
        actor={"pid": 4242, "starttime": 1},
    )
    monkeypatch.setattr(
        formal_orchestrator.os,
        "kill",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("kill-fault")),
    )
    monkeypatch.setattr(
        formal_orchestrator.os,
        "waitpid",
        lambda *_args: (_ for _ in ()).throw(ChildProcessError()),
    )
    try:
        with pytest.raises(
            formal_orchestrator.FormalOrchestrationError,
            match="kill-fault",
        ):
            session.close()
        assert parent.fileno() == -1
        with pytest.raises(OSError):
            os.fstat(stderr_read)
        assert session.reaped is True
    finally:
        child.close()


def test_formal_owner_spawn_failure_retries_wait_and_closes_all_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver_raw = bootstrap.FORMAL_LAUNCH_OWNER_DRIVER_V1.encode("utf-8")
    publisher_raw = bootstrap.OWNER_OEXCL_PUBLISH_V1.encode("utf-8")
    context = {
        "formal_launch_owner_driver_identity": {
            "sha256": hashlib.sha256(driver_raw).hexdigest(),
            "size_bytes": len(driver_raw),
        },
        "mechanical_oexcl_publisher_identity": {
            "sha256": hashlib.sha256(publisher_raw).hexdigest(),
            "size_bytes": len(publisher_raw),
        },
        "outer_spec": {},
    }
    monkeypatch.setattr(
        formal_orchestrator,
        "_formal_campaign_module",
        lambda: SimpleNamespace(
            _selected_identities=lambda _spec: {  # noqa: SLF001
                "python": {"path": "/fixture/python"},
            },
            _open_selected=lambda *_args: os.open(  # noqa: SLF001
                "/dev/null",
                os.O_RDONLY,
            ),
        ),
    )
    monkeypatch.setattr(
        formal_orchestrator.os,
        "posix_spawn",
        lambda *_args, **_kwargs: 4242,
    )
    monkeypatch.setattr(
        formal_orchestrator,
        "_read_frame",
        lambda *_args: (_ for _ in ()).throw(
            RuntimeError("owner-ready-validation-fault")
        ),
    )
    kill_calls: list[int] = []
    wait_calls: list[int] = []

    def fail_kill(pid: int, _signal: int) -> None:
        kill_calls.append(pid)
        raise RuntimeError("owner-cleanup-kill-fault")

    def interrupted_wait(pid: int, _flags: int) -> tuple[int, int]:
        wait_calls.append(pid)
        if len(wait_calls) == 1:
            raise InterruptedError("owner-cleanup-wait-interrupted")
        return pid, 0

    monkeypatch.setattr(formal_orchestrator.os, "kill", fail_kill)
    monkeypatch.setattr(formal_orchestrator.os, "waitpid", interrupted_wait)
    before = {entry.name for entry in Path("/proc/self/fd").iterdir()}
    with pytest.raises(RuntimeError, match="owner-ready-validation-fault"):
        formal_orchestrator._spawn_owner(context)  # noqa: SLF001
    after = {entry.name for entry in Path("/proc/self/fd").iterdir()}
    assert after == before
    assert kill_calls == [4242]
    assert wait_calls == [4242, 4242]


def test_formal_owner_sealed_memfd_close_fault_preserves_original(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_close = os.close
    real_fcntl = formal_orchestrator.fcntl.fcntl

    def fail_seal(
        descriptor: int,
        command: int,
        argument: int = 0,
    ) -> int:
        if command == formal_orchestrator.F_ADD_SEALS:
            raise RuntimeError("memfd-seal-fault")
        return real_fcntl(descriptor, command, argument)

    def close_then_fail(descriptor: int) -> None:
        real_close(descriptor)
        raise RuntimeError("memfd-close-fault")

    monkeypatch.setattr(formal_orchestrator.fcntl, "fcntl", fail_seal)
    monkeypatch.setattr(formal_orchestrator.os, "close", close_then_fail)
    before = {entry.name for entry in Path("/proc/self/fd").iterdir()}
    with pytest.raises(RuntimeError, match="memfd-seal-fault"):
        formal_orchestrator._sealed_memfd(  # noqa: SLF001
            "fault-fixture",
            b"payload",
        )
    after = {entry.name for entry in Path("/proc/self/fd").iterdir()}
    assert after == before


@pytest.mark.parametrize(
    "fault",
    ("control-close", "wait", "stderr-read-close"),
)
def test_formal_owner_handoff_cleanup_preserves_original_and_closes_once(
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    class Control:
        close_count = 0

        def close(self) -> None:
            self.close_count += 1
            if fault == "control-close":
                raise RuntimeError("handoff-control-close-fault")

    control = Control()
    before = {entry.name for entry in Path("/proc/self/fd").iterdir()}
    stderr_read, stderr_write = os.pipe()
    os.close(stderr_write)
    actor = {"pid": 4242, "starttime": 777}
    session = formal_orchestrator.OwnerSession(
        pid=4242,
        control=control,  # type: ignore[arg-type]
        stderr_descriptor=stderr_read,
        actor=actor,
    )
    monkeypatch.setattr(
        formal_orchestrator,
        "_process_starttime",
        lambda _pid: 777,
    )
    monkeypatch.setattr(
        formal_orchestrator,
        "_send_frame",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        formal_orchestrator,
        "_read_frame",
        lambda *_args: {
            "actor": actor,
            "schema_version": formal_orchestrator.RESPONSE_SCHEMA,
            "sequence": 3,
            "status": "HANDOFF_COMPLETE",
        },
    )
    wait_calls: list[int] = []
    kill_calls: list[int] = []

    def waitpid(pid: int, _flags: int) -> tuple[int, int]:
        wait_calls.append(pid)
        if fault == "wait" and len(wait_calls) == 1:
            raise RuntimeError("handoff-wait-fault")
        return pid, 0

    monkeypatch.setattr(formal_orchestrator.os, "waitpid", waitpid)
    monkeypatch.setattr(
        formal_orchestrator.os,
        "kill",
        lambda pid, _signal: kill_calls.append(pid),
    )
    real_read = os.read
    real_close = os.close
    stderr_close_count = 0

    def read(descriptor: int, size: int) -> bytes:
        if fault == "stderr-read-close":
            raise RuntimeError("handoff-stderr-read-fault")
        return real_read(descriptor, size)

    def close(descriptor: int) -> None:
        nonlocal stderr_close_count
        if descriptor == stderr_read:
            stderr_close_count += 1
            real_close(descriptor)
            if fault == "stderr-read-close":
                raise RuntimeError("handoff-stderr-close-fault")
            return
        real_close(descriptor)

    monkeypatch.setattr(formal_orchestrator.os, "read", read)
    monkeypatch.setattr(formal_orchestrator.os, "close", close)
    expected = {
        "control-close": "handoff-control-close-fault",
        "wait": "handoff-wait-fault",
        "stderr-read-close": "handoff-stderr-read-fault",
    }[fault]
    with pytest.raises(RuntimeError, match=expected):
        session.complete_handoff()
    after = {entry.name for entry in Path("/proc/self/fd").iterdir()}
    assert after == before
    assert control.close_count == 1
    assert stderr_close_count == 1
    assert session.reaped is True
    if fault in {"control-close", "wait"}:
        assert kill_calls == [4242]
    else:
        assert kill_calls == []


@pytest.mark.parametrize(
    ("outcome", "returncode"),
    (("VERIFIED", 0), ("INCOMPLETE", 2)),
)
def test_formal_orchestrator_integrates_persistent_owner_and_supervisor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
    returncode: int,
) -> None:
    fixture = _formal_fixture(tmp_path)
    context = fixture.context
    admission_path = Path(str(context["formal_admission_path"]))
    selection_path = Path(str(context["formal_selection_path"]))
    guardian_path = Path(str(context["guardian_ready_path"]))
    attempt_path = (
        Path(str(context["formal_attempt_dir"])) / "attempt-consumption.json"
    )
    admission_path.parent.mkdir(parents=True)
    attempt_path.parent.mkdir()
    events: list[str] = []
    published: dict[str, dict[str, object]] = {}
    selection_before_readonly = threading.Event()
    supervisor_observed_incomplete = threading.Event()
    actor = {
        "pid": os.getpid(),
        "role": launch_validator.OWNER_PUBLISHER_ROLE,
        "session_id": formal_orchestrator.SESSION_ID,
        "starttime": _process_starttime(os.getpid()),
    }
    real_fchmod = authority.os.fchmod

    def hold_selection_before_readonly(descriptor: int, mode: int) -> None:
        # Keep the final name visible at 0600 until the supervisor has observed
        # that incomplete publication state.  A consumer that waits only for
        # path existence would race the publisher's final chmod/fsync.
        target = Path(os.readlink(f"/proc/self/fd/{descriptor}"))
        if target == selection_path and mode == 0o444:
            selection_before_readonly.set()
            assert supervisor_observed_incomplete.wait(timeout=5.0)
        real_fchmod(descriptor, mode)

    monkeypatch.setattr(authority.os, "fchmod", hold_selection_before_readonly)

    def publish(
        path: Path,
        record: dict[str, object],
    ) -> dict[str, object]:
        return authority._write_exclusive(  # noqa: SLF001
            path,
            authority.canonical_json(record),
            mode=0o444,
        )

    class FakeOwner:
        pid = os.getpid()
        reaped = False

        def __init__(self) -> None:
            self.actor = actor

        def request(
            self,
            *,
            sequence: int,
            kind: str,
            draft: dict[str, object],
        ) -> dict[str, object]:
            events.append(f"owner:{sequence}:{kind}")
            assert draft["publisher"]["actor"] == actor
            path = admission_path if kind == "admission" else selection_path
            identity = publish(path, draft)
            published[kind] = identity
            return {
                "actor": actor,
                "artifact_identity": identity,
                "kind": kind,
                "schema_version": formal_orchestrator.RESPONSE_SCHEMA,
                "sequence": sequence,
                "status": "PUBLISHED",
            }

        def complete_handoff(self) -> None:
            events.append("owner:3:handoff")
            self.reaped = True

        def close(self) -> None:
            events.append("owner:close")
            self.reaped = True

    owner = FakeOwner()
    monkeypatch.setattr(
        formal_orchestrator.launch_validator,
        "replay_formal_launch_context",
        lambda _authority, _campaign: context,
    )
    monkeypatch.setattr(
        formal_orchestrator,
        "_verify_selected_self",
        lambda _context: None,
    )
    monkeypatch.setattr(formal_orchestrator, "_spawn_owner", lambda _context: owner)

    def selected_supervisor(**kwargs: object) -> object:
        events.append("supervisor:start")
        assert kwargs["role"] == "formal-supervisor"
        guardian = deepcopy(fixture.guardian_ready)
        guardian["formal_admission_identity"] = published["admission"]
        publish(guardian_path, guardian)
        publish(attempt_path, fixture.attempt_consumption)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                observed = os.lstat(selection_path)
            except FileNotFoundError:
                time.sleep(0.01)
                continue
            observed_mode = stat.S_IMODE(observed.st_mode)
            if stat.S_ISREG(observed.st_mode) and observed_mode == 0o444:
                break
            if stat.S_ISREG(observed.st_mode) and observed_mode == 0o600:
                supervisor_observed_incomplete.set()
                time.sleep(0.01)
                continue
            pytest.fail("formal selection has an invalid publication surface")
        assert selection_before_readonly.is_set()
        assert supervisor_observed_incomplete.is_set()
        assert selection_path.exists()
        assert stat.S_IMODE(os.lstat(selection_path).st_mode) == 0o444
        selection_identity = authority.detached_identity(
            authority.snapshot_regular(selection_path)
        )
        events.append("supervisor:return")
        return SimpleNamespace(
            returncode=returncode,
            stdout=authority.canonical_json(
                {
                    "formal_selection_identity": selection_identity,
                    "outcome": outcome,
                    "status": outcome,
                }
            ),
            stderr=b"",
        )

    monkeypatch.setattr(
        formal_orchestrator,
        "_formal_campaign_module",
        lambda: SimpleNamespace(run_selected_direct_result=selected_supervisor),
    )

    result = formal_orchestrator.orchestrate(context["campaign_dir"])

    assert result["status"] == outcome
    assert result["owner_handoff_complete"] is True
    assert selection_before_readonly.is_set()
    assert supervisor_observed_incomplete.is_set()
    assert events == [
        "owner:1:admission",
        "supervisor:start",
        "owner:2:selection",
        "supervisor:return",
        "owner:3:handoff",
    ]


def test_formal_orchestrator_wait_uses_one_node_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "attempt-consumption.json"
    authority._write_exclusive(  # noqa: SLF001
        candidate,
        authority.canonical_json({"status": "CONSUMED"}),
        mode=0o444,
    )
    real_is_file = Path.is_file
    stale_observations = 0

    def stale_once(path: Path) -> bool:
        nonlocal stale_observations
        if path == candidate and stale_observations == 0:
            stale_observations += 1
            return False
        return real_is_file(path)

    monkeypatch.setattr(Path, "is_file", stale_once)
    owner = SimpleNamespace(
        pid=os.getpid(),
        actor={"starttime": _process_starttime(os.getpid())},
    )

    record, identity = formal_orchestrator._wait_record(  # noqa: SLF001
        candidate,
        "formal attempt consumption",
        owner=owner,
        supervisor_alive=lambda: True,
    )

    assert record == {"status": "CONSUMED"}
    assert identity["path"] == str(candidate)
    assert stale_observations == 0


def test_formal_orchestrator_waits_for_readonly_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "attempt-consumption.json"
    candidate.write_bytes(authority.canonical_json({"status": "CONSUMED"}))
    candidate.chmod(0o600)
    sleeps: list[float] = []

    def complete_publication(seconds: float) -> None:
        sleeps.append(seconds)
        candidate.chmod(0o444)

    monkeypatch.setattr(formal_orchestrator.time, "sleep", complete_publication)
    owner = SimpleNamespace(
        pid=os.getpid(),
        actor={"starttime": _process_starttime(os.getpid())},
    )

    record, identity = formal_orchestrator._wait_record(  # noqa: SLF001
        candidate,
        "formal attempt consumption",
        owner=owner,
        supervisor_alive=lambda: True,
    )

    assert record == {"status": "CONSUMED"}
    assert identity["path"] == str(candidate)
    assert sleeps == [formal_orchestrator.POLL_SECONDS]


@pytest.mark.parametrize(
    "boundary",
    ("sequence", "admission-actor", "selection-actor", "handoff-sequence"),
)
def test_formal_owner_driver_rejects_sequence_and_actor_drift(
    tmp_path: Path,
    boundary: str,
) -> None:
    probe = _start_owner_driver(tmp_path)
    try:
        assert probe.ready is not None
        actor = dict(probe.ready["actor"])
        if boundary == "sequence":
            probe.control.send(
                _owner_request(actor=actor, sequence=2, kind="selection")
            )
        elif boundary == "admission-actor":
            actor["starttime"] = int(actor["starttime"]) + 1
            probe.control.send(
                _owner_request(actor=actor, sequence=1, kind="admission")
            )
        else:
            probe.control.send(
                _owner_request(actor=actor, sequence=1, kind="admission")
            )
            assert _owner_response(probe.control)["status"] == "PUBLISHED"
            if boundary == "selection-actor":
                actor["pid"] = int(actor["pid"]) + 1
                probe.control.send(
                    _owner_request(actor=actor, sequence=2, kind="selection")
                )
            else:
                probe.control.send(
                    _owner_request(actor=actor, sequence=2, kind="selection")
                )
                assert _owner_response(probe.control)["status"] == "PUBLISHED"
                probe.control.send(
                    authority.canonical_json(
                        {
                            "kind": "handoff-complete",
                            "schema_version": OWNER_REQUEST_SCHEMA,
                            "sequence": 4,
                        }
                    )
                )
        failure = _owner_response(probe.control)
        assert failure is not None
        assert failure["status"] == "FAIL_CLOSED"
        _stdout, stderr = probe.process.communicate(timeout=10)
        assert probe.process.returncode == 125, stderr
        selection_path = Path(str(probe.context["formal_selection_path"]))
        assert selection_path.exists() is (boundary == "handoff-sequence")
    finally:
        if probe.process.poll() is None:
            _finish_owner_probe(probe)
        else:
            probe.control.close()


def test_formal_owner_driver_never_retries_uncertain_publication(
    tmp_path: Path,
) -> None:
    uncertain_publisher = r"""
import os
import sys

basename = sys.argv[1]
fd = os.open(
    basename + ".attempts",
    os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_CLOEXEC | os.O_NOFOLLOW,
    0o600,
    dir_fd=5,
)
os.write(fd, b"x")
os.fsync(fd)
os.close(fd)
raise SystemExit(125)
""".strip()
    probe = _start_owner_driver(
        tmp_path,
        publisher_source=uncertain_publisher,
    )
    try:
        assert probe.ready is not None
        actor = probe.ready["actor"]
        probe.control.send(
            _owner_request(actor=actor, sequence=1, kind="admission")
        )
        failure = _owner_response(probe.control)
        assert failure is not None
        assert failure["status"] == "FAIL_CLOSED"
        _stdout, stderr = probe.process.communicate(timeout=10)
        assert probe.process.returncode == 125, stderr
        admission_path = Path(str(probe.context["formal_admission_path"]))
        attempts = admission_path.with_name(admission_path.name + ".attempts")
        assert attempts.read_bytes() == b"x"
        assert not admission_path.exists()
    finally:
        if probe.process.poll() is None:
            _finish_owner_probe(probe)
        else:
            probe.control.close()


def test_formal_owner_driver_rejects_unsealed_publisher_before_ready(
    tmp_path: Path,
) -> None:
    probe = _start_owner_driver(tmp_path, seal_publisher=False)
    try:
        assert probe.ready is None
        _stdout, stderr = probe.process.communicate(timeout=10)
        assert probe.process.returncode == 125
        assert b"PUBLISHER_METADATA" in stderr
        assert not Path(str(probe.context["formal_admission_path"])).exists()
    finally:
        if probe.process.poll() is None:
            _finish_owner_probe(probe)
        else:
            probe.control.close()


@pytest.mark.parametrize("mutation", ("missing", "extra", "identity-drift"))
def test_admission_strictly_rejects_field_and_upstream_identity_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    fixture = _formal_fixture(tmp_path)
    record = deepcopy(fixture.admission)
    if mutation == "missing":
        record.pop("guardian_ready_path")
    elif mutation == "extra":
        record["unexpected"] = False
    else:
        record["campaign_root_identity"]["sha256"] = "f" * 64

    with pytest.raises(launch_validator.FormalLaunchValidationError):
        launch_validator.validate_admission(record, expected_context=fixture.context)


def test_selection_rejects_duplicate_id_and_runtime_self_authorization(
    tmp_path: Path,
) -> None:
    fixture = _formal_fixture(tmp_path)
    duplicate = deepcopy(fixture.selection)
    duplicate["selection_id"] = fixture.admission["admission_id"]
    with pytest.raises(
        launch_validator.FormalLaunchValidationError,
        match="authority boundary",
    ):
        launch_validator.validate_selection(
            duplicate,
            admission=fixture.admission,
            admission_identity=fixture.admission_identity,
            guardian_ready=fixture.guardian_ready,
            guardian_ready_identity=fixture.guardian_ready_identity,
            attempt_consumption=fixture.attempt_consumption,
            attempt_consumption_identity=fixture.attempt_consumption_identity,
            expected_context=fixture.context,
        )

    context = deepcopy(fixture.context)
    context["launch_renderer_identity"] = deepcopy(context["controller_identity"])
    admission = deepcopy(fixture.admission)
    admission["publisher"]["renderer_identity"] = deepcopy(context["controller_identity"])
    selection = deepcopy(fixture.selection)
    selection["publisher"]["renderer_identity"] = deepcopy(context["controller_identity"])
    with pytest.raises(
        launch_validator.FormalLaunchValidationError,
        match="authority and runtime tool identities collapsed",
    ):
        launch_validator.validate_selection(
            selection,
            admission=admission,
            admission_identity=fixture.admission_identity,
            guardian_ready=fixture.guardian_ready,
            guardian_ready_identity=fixture.guardian_ready_identity,
            attempt_consumption=fixture.attempt_consumption,
            attempt_consumption_identity=fixture.attempt_consumption_identity,
            expected_context=context,
        )


def test_loader_rejects_ambient_and_outside_snapshot_module_origins(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ambient = ModuleType("src.ab16_ambient_injection")
    monkeypatch.setitem(sys.modules, ambient.__name__, ambient)
    with pytest.raises(loader.FormalLoaderError, match="ambient/preloaded"):
        loader._reject_ambient_modules(  # noqa: SLF001
            loader.ROLE_MAP["formal-controller"],
            ModuleType("_selected_authority"),
        )

    snapshot = tmp_path / "snapshot"
    target = ModuleType("outside_role")
    target.__file__ = str(tmp_path / "ambient-checkout" / "role.py")
    with pytest.raises(loader.FormalLoaderError, match="fixed snapshot path"):
        loader._verify_module_origin(  # noqa: SLF001
            target,
            expected=snapshot / "role.py",
            snapshot_root=snapshot,
        )


def test_loader_runtime_prefix_under_git_ancestor_is_platform_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    (home / ".git").mkdir(parents=True)
    base_prefix = home / ".local/python"
    venv_prefix = home / "live-project/.venv"
    stdlib = base_prefix / "lib/python3.13"
    site_packages = venv_prefix / "lib/python3.13/site-packages"
    stdlib.mkdir(parents=True)
    site_packages.mkdir(parents=True)
    monkeypatch.setattr(loader.sys, "base_prefix", str(base_prefix))
    monkeypatch.setattr(loader.sys, "base_exec_prefix", str(base_prefix))
    monkeypatch.setattr(loader.sys, "prefix", str(venv_prefix))
    monkeypatch.setattr(loader.sys, "exec_prefix", str(venv_prefix))

    frozen_origin = stdlib / "importlib/_bootstrap.py"
    package_origin = site_packages / "ortools/__init__.py"
    assert loader._checkout_ancestor(frozen_origin) == home  # noqa: SLF001
    assert loader._checkout_ancestor(package_origin) == home  # noqa: SLF001
    assert loader._live_checkout_origin(frozen_origin) is False  # noqa: SLF001
    assert loader._live_checkout_origin(package_origin) is False  # noqa: SLF001

    live_checkout = home / "live-project"
    (live_checkout / ".git").mkdir(parents=True)
    assert loader._live_checkout_origin(  # noqa: SLF001
        live_checkout / "docs/research/live.py"
    ) is True

    nested_checkout = site_packages / "ambient-plugin"
    (nested_checkout / ".git").mkdir(parents=True)
    assert loader._live_checkout_origin(  # noqa: SLF001
        nested_checkout / "module.py"
    ) is True

    monkeypatch.setattr(loader.sys, "path", [str(stdlib), str(site_packages)])
    assert loader._platform_paths(tmp_path / "snapshot") == [  # noqa: SLF001
        str(stdlib),
        str(site_packages),
    ]
    loader.sys.path.append(str(live_checkout))
    with pytest.raises(loader.FormalLoaderError, match="checkout-shaped import path"):
        loader._platform_paths(tmp_path / "snapshot")  # noqa: SLF001

    loader_path = Path(loader.__file__).resolve()
    command = """
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

loader_path = Path(sys.argv[1])
home = Path(sys.argv[2])
runtime_prefix = home / "runtime-prefix"
runtime_prefix.mkdir()
module_name = "_ab16_loader_runtime_prefix_fixture"
spec = importlib.util.spec_from_file_location(module_name, loader_path)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module
spec.loader.exec_module(module)
sys.modules.pop(module_name)
runtime_prefixes = module._runtime_prefixes()
module._runtime_prefixes = lambda: (*runtime_prefixes, runtime_prefix)
fixture = ModuleType("_frozen_importlib_fixture")
fixture.__file__ = str(runtime_prefix / "lib/python3.13/importlib/_bootstrap.py")
sys.modules[fixture.__name__] = fixture
module._reject_ambient_modules(
    module.ROLE_MAP["formal-controller"],
    ModuleType("_selected_authority"),
)
print("PASS")
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", command, str(loader_path), str(home)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "PASS\n"

    (base_prefix / ".git").mkdir()
    assert loader._live_checkout_origin(frozen_origin) is True  # noqa: SLF001


def test_loader_allows_only_its_executing_main_module() -> None:
    loader_path = Path(loader.__file__).resolve()
    command = """
import contextlib
import hashlib
import io
import os
from pathlib import Path
import stat
import sys
from types import ModuleType

loader_path = Path(sys.argv[1])
descriptor = os.open(loader_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
os.dup2(descriptor, 4)
if descriptor != 4:
    os.close(descriptor)
metadata = os.fstat(4)
raw = os.pread(4, metadata.st_size, 0)
expected = {
    "mode": stat.S_IMODE(metadata.st_mode),
    "path": str(loader_path),
    "sha256": hashlib.sha256(raw).hexdigest(),
    "size_bytes": len(raw),
}

def execute_main(filename):
    module = ModuleType("__main__")
    module.__file__ = filename
    module.__package__ = None
    module.__spec__ = None
    sys.modules["__main__"] = module
    sys.argv = [filename]
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            exec(compile(raw, filename, "exec"), module.__dict__, module.__dict__)
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError("loader script unexpectedly accepted an empty CLI")
    return module

ordinary = execute_main(str(loader_path))
try:
    ordinary._verify_executing_loader(expected)
except ordinary.FormalLoaderError as exc:
    assert "did not execute from fixed FD4" in str(exc)
else:
    raise AssertionError("ordinary-path loader execution was accepted")

module = execute_main("/proc/self/fd/4")
drifted = dict(expected)
drifted["sha256"] = "0" * 64
try:
    module._verify_executing_loader(drifted)
except module.FormalLoaderError as exc:
    assert "FD4 identity drifted" in str(exc)
else:
    raise AssertionError("loader FD4 digest drift was accepted")
verified = module._verify_executing_loader(expected)
assert verified is module
module._reject_ambient_modules(
    module.ROLE_MAP["formal-controller"],
    ModuleType("_selected_authority"),
    executing_loader_module=verified,
)

hijacked = ModuleType("__main__")
hijacked.__file__ = str(loader_path)
sys.modules["__main__"] = hijacked
try:
    module._reject_ambient_modules(
        module.ROLE_MAP["formal-controller"],
        ModuleType("_selected_authority"),
        executing_loader_module=verified,
    )
except module.FormalLoaderError as exc:
    assert "preloaded module __main__ came from a live checkout" in str(exc)
else:
    raise AssertionError("replacement __main__ module was accepted")
print("PASS")
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", command, str(loader_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "PASS\n"
    assert completed.stderr == ""


def test_loader_rejects_duplicate_identity_and_same_fd_digest_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate = (
        '{"mode":292,"path":"/sealed/authority.py","sha256":"'
        + "a" * 64
        + '","sha256":"'
        + "b" * 64
        + '","size_bytes":17}'
    )
    with pytest.raises(loader.FormalLoaderError, match="duplicate key"):
        loader._parse_authority_identity(duplicate)  # noqa: SLF001

    campaign = tmp_path / "campaign"
    payload = (
        campaign
        / "campaign-authority"
        / "package"
        / "payload"
        / "tool.ab16_authority_v2.py"
    )
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"selected_authority = True\n")
    payload.chmod(0o444)
    legacy_descriptor = os.open(
        payload,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        monkeypatch.setattr(loader, "AUTHORITY_FD", legacy_descriptor)
        with pytest.raises(
            loader.FormalLoaderError,
            match="metadata drifted",
        ):
            loader.load_selected_authority_from_fd(
                campaign_dir=campaign,
                descriptor=legacy_descriptor,
                expected_identity={
                    "mode": 0o444,
                    "path": str(payload),
                    "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
                    "size_bytes": payload.stat().st_size,
                },
            )
    finally:
        os.close(legacy_descriptor)

    payload.chmod(loader.PACKAGE_PAYLOAD_MODE)
    descriptor = os.open(payload, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        monkeypatch.setattr(loader, "AUTHORITY_FD", descriptor)
        with pytest.raises(loader.FormalLoaderError, match="digest drifted"):
            loader.load_selected_authority_from_fd(
                campaign_dir=campaign,
                descriptor=descriptor,
                expected_identity={
                    "mode": loader.PACKAGE_PAYLOAD_MODE,
                    "path": str(payload),
                    "sha256": "0" * 64,
                    "size_bytes": payload.stat().st_size,
                },
            )
    finally:
        os.close(descriptor)


def test_formal_selected_package_tools_reject_legacy_read_only_mode(
    tmp_path: Path,
) -> None:
    fixture = _formal_fixture(tmp_path)
    context = deepcopy(fixture.context)
    for spec_name in ("outer_spec", "guardian_spec"):
        argv = context[spec_name]["selected_byte_argv"]
        selected = json.loads(argv[6])
        selected["loader"]["mode"] = 0o444
        selected["authority"]["mode"] = 0o444
        argv[6] = json.dumps(
            selected,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    with pytest.raises(
        launch_validator.FormalLaunchValidationError,
        match="selected-byte open-file identity set drifted",
    ):
        launch_validator.validate_admission(
            fixture.admission,
            expected_context=context,
        )


def test_controller_reuses_authority_owned_order_balanced_arm_sequence() -> None:
    assert controller.ARM_SEQUENCE == tuple(authority.EXPERIMENT_CONTRACT["order"])
    assert controller.ARM_SEQUENCE == closeout_state.ARM_SEQUENCE
    for offset in range(0, len(controller.ARM_SEQUENCE), 4):
        group = controller.ARM_SEQUENCE[offset : offset + 4]
        assert group[0].endswith("-ab-control")
        assert group[1].endswith("-ab-treatment")
        assert group[2].endswith("-ba-treatment")
        assert group[3].endswith("-ba-control")


def test_controller_runs_barrier_gate1_baseline_manifest_and_fixed_arms_in_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    manifest_identity = _identity(tmp_path, "manifest.json", "a")
    suite_identity = _identity(tmp_path, "suite.json", "b")
    barrier_identity = _identity(tmp_path, "barrier.json", "c")
    inputs = controller.FormalInputs(
        context={"campaign_dir": str(tmp_path), "package_id": "d" * 64},
        selection={},
        selection_identity=_identity(tmp_path, "selection.json", "e"),
    )

    class FakePorts:
        def wait_for_barrier(
            self,
            observed: controller.FormalInputs,
        ) -> tuple[dict[str, object], dict[str, object]]:
            assert observed is inputs
            events.append("barrier")
            return {"released": True}, barrier_identity

        def run_gate1(self, observed: controller.FormalInputs) -> dict[str, object]:
            assert observed is inputs
            events.append("gate1")
            return {"status": "PASS"}

        def run_baseline_chain(self, observed: controller.FormalInputs) -> dict[str, object]:
            assert observed is inputs
            events.append("baseline")
            return {"status": "PASS"}

    monkeypatch.setattr(controller, "load_formal_inputs", lambda **_kwargs: inputs)

    def build_manifest(campaign_dir: object) -> dict[str, object]:
        assert campaign_dir == str(tmp_path)
        events.append("manifest")
        return {"manifest_identity": manifest_identity, "status": "PASS"}

    def create_suite(campaign_dir: object) -> dict[str, object]:
        assert campaign_dir == str(tmp_path)
        events.append("suite")
        return {"selection_identity": suite_identity, "status": "PASS"}

    monkeypatch.setattr(controller.authority, "build_manifest", build_manifest)
    monkeypatch.setattr(controller.authority, "create_suite_selection", create_suite)

    def consume_arm(
        observed: controller.FormalInputs,
        *,
        ports: object,
        slot: str,
        ordinal: int,
    ) -> dict[str, object]:
        assert observed is inputs
        assert isinstance(ports, FakePorts)
        assert controller.ARM_SEQUENCE[ordinal - 1] == slot
        events.append(f"arm:{ordinal}:{slot}")
        return {"ordinal": ordinal, "slot": slot}

    monkeypatch.setattr(controller, "_consume_selected_arm", consume_arm)

    def publish_result(
        observed: controller.FormalInputs,
        **kwargs: Any,
    ) -> tuple[dict[str, object], dict[str, object]]:
        assert observed is inputs
        assert kwargs["barrier_identity"] == barrier_identity
        assert kwargs["manifest_identity"] == manifest_identity
        assert kwargs["suite_selection_identity"] == suite_identity
        assert [item["slot"] for item in kwargs["arms"]] == list(controller.ARM_SEQUENCE)
        events.append("publish")
        return {"status": "PASS"}, _identity(tmp_path, "controller-result.json", "f")

    monkeypatch.setattr(controller, "_publish_controller_result", publish_result)
    result = controller.run_controller(
        campaign_dir=tmp_path,
        formal_selection=tmp_path / "formal-selection.json",
        ports=FakePorts(),
    )

    assert result["status"] == "PASS"
    assert events[:5] == ["barrier", "gate1", "baseline", "manifest", "suite"]
    assert events[5:-1] == [
        f"arm:{ordinal}:{slot}"
        for ordinal, slot in enumerate(controller.ARM_SEQUENCE, start=1)
    ]
    assert events[-1] == "publish"


def test_guardian_control_poll_observes_latch_before_receiving_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    left, right = socket.socketpair(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
    )
    termination_records: list[dict[str, int]] = []
    poll_calls: list[tuple[int, int]] = []
    registered: list[tuple[int, int]] = []

    class FakePoll:
        def register(self, descriptor: int, event_mask: int) -> None:
            registered.append((descriptor, event_mask))

        def poll(self, timeout_ms: int) -> list[tuple[int, int]]:
            poll_calls.append((timeout_ms, len(termination_records)))
            termination_records.append(
                {"count": 1, "monotonic_ns": 1, "signal": 15}
            )
            return [(right.fileno(), guardian.select.POLLIN)]

    monkeypatch.setattr(guardian.select, "poll", FakePoll)
    record = {"schema_version": "focused-frame-v1", "status": "OBSERVE_ONLY"}
    identity = guardian.send_frame(left, record)
    try:
        with pytest.raises(
            guardian.GuardianTerminationLatched,
            match="during frame receive",
        ):
            guardian.receive_frame_interruptible(
                right,
                expected_fd_count=0,
                termination_records=termination_records,
                poll_interval_seconds=9.0,
            )
        assert poll_calls == [(1000, 0)]
        assert registered == [
            (
                right.fileno(),
                guardian.select.POLLIN
                | guardian.select.POLLHUP
                | guardian.select.POLLERR
                | guardian.select.POLLNVAL,
            )
        ]
        received = guardian.receive_frame(right, expected_fd_count=0)
    finally:
        left.close()
        right.close()
    assert received.record == record
    assert received.identity == identity
    assert termination_records == [
        {"count": 1, "monotonic_ns": 1, "signal": 15}
    ]
    guardian_source = inspect.getsource(guardian.run_guardian_session)
    assert "receive_frame_interruptible(" in guardian_source
    assert "first_control = receive_frame(" not in guardian_source
    assert "frame = receive_frame(connection" not in guardian_source


def test_guardian_frame_and_failure_state_are_canonical_and_monotone() -> None:
    left, right = socket.socketpair(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
    )
    try:
        record = {"schema_version": "focused-frame-v1", "status": "OBSERVE_ONLY"}
        identity = guardian.send_frame(left, record)
        received = guardian.receive_frame(right, expected_fd_count=0)
    finally:
        left.close()
        right.close()
    assert received.record == record
    assert received.identity == identity
    assert received.file_descriptors == ()
    assert received.peer_pid == os.getpid()

    effects = guardian.GuardianEffects(success_eligible=True)
    first = effects.fail("FOCUSED_FAILURE", "one failure")
    second = effects.fail("FOCUSED_FAILURE", "one failure")
    assert first == second
    assert effects.errors == [first]
    assert effects.irreversible_incomplete is True
    assert effects.success_eligible is False

    read_descriptor, write_descriptor = os.pipe()
    exited = False

    def starttime(pid: int) -> int:
        assert pid == 903
        return 123_458

    def open_pidfd(pid: int, flags: int = 0) -> int:
        assert (pid, flags) == (903, 0)
        return read_descriptor

    def observe_exit(descriptor: int) -> bool:
        assert descriptor == read_descriptor
        return exited

    witness = guardian.SupervisorDeathWitness(
        {"pid": 903, "starttime": 123_458},
        process_starttime_reader=starttime,
        pidfd_opener=open_pidfd,
        exit_observer=observe_exit,
    )
    try:
        assert witness.arm_record()["status"] == "ARMED"
        assert witness.observe() is None
        exited = True
        death = witness.observe()
        assert death is not None
        assert guardian.validate_supervisor_death_observation(
            death,
            expected_process_identity={"pid": 903, "starttime": 123_458},
        )["status"] == "SUPERVISOR_DEATH_PROVED"
        witness.close_once()
        with pytest.raises(guardian.GuardianProtocolError, match="closed twice"):
            witness.close_once()
    finally:
        if not witness.close_attempted:
            witness.close_once()
        os.close(write_descriptor)


def _valid_outer_prelaunch(
    fixture: FormalFixture,
) -> tuple[dict[str, object], dict[str, object]]:
    expected = {
        "campaign_root_identity": fixture.context["campaign_root_identity"],
        "formal_selection_identity": _identity(
            Path(str(fixture.context["campaign_dir"])),
            "formal-selection-observed.json",
            "f",
        ),
        "manager_epoch": fixture.context["manager_epoch"],
        "package_id": fixture.context["package_id"],
    }
    record = {
        "authority_scope": success_verifier.AUTHORITY_SCOPE,
        "authorizations": dict(success_verifier.FALSE_AUTHORIZATIONS),
        "campaign_root_identity": expected["campaign_root_identity"],
        "created_at_utc": "2026-07-28T00:04:00Z",
        "formal_selection_identity": expected["formal_selection_identity"],
        "manager_epoch": expected["manager_epoch"],
        "outer_identity": {
            "control_group": "",
            "invocation_id": "",
            "processes": [],
            "unit_name": fixture.context["outer_spec"]["unit_name"],
        },
        "package_id": expected["package_id"],
        "prelaunch_absence": {
            "cgroup_absent": True,
            "load_state": "not-found",
            "lock_identities": fixture.lock_identities,
            "pid_absent": True,
        },
        "schema_version": success_verifier.PHASE_SCHEMAS["outer_prelaunch"],
        "status": "PASS",
    }
    return record, expected


def _reference_base_record(
    fixture: FormalFixture,
    *,
    status: str,
    unit_name: str,
) -> dict[str, object]:
    return {
        "authorizations": dict(closeout_state.FALSE_AUTHORIZATIONS),
        "campaign_root_identity": fixture.context["campaign_root_identity"],
        "lower_bound": None,
        "package_id": fixture.context["package_id"],
        "production_certified": False,
        "schema_version": closeout_state.REFERENCE_SCHEMA,
        "status": status,
        "unit_name": unit_name,
        "upper_bound": [1188, 18],
    }


def test_success_verifier_uses_state_owned_reference_schemas_and_exact_joins(
    tmp_path: Path,
) -> None:
    fixture = _formal_fixture(tmp_path)
    selection_identity = _identity(tmp_path, "selection.json", "a")
    resource_identity = _identity(tmp_path, "outer-resource.json", "b")
    acquisition_identity = _identity(tmp_path, "reference-acquisition.json", "c")
    observer_identity = _identity(tmp_path, "observer.json", "d")
    cleanup_identity = _identity(tmp_path, "pre-unref-cleanup.json", "e")
    unref_identity = _identity(tmp_path, "unref-call.json", "f")
    unit_name = str(fixture.context["outer_spec"]["unit_name"])
    outer = {
        "control_group": "/user.slice/ab16-formal-outer-a001.service",
        "invocation_id": "4" * 32,
        "processes": [{"pid": 904, "starttime": 123_459}],
        "unit_name": unit_name,
    }
    expected = {
        "campaign_root_identity": fixture.context["campaign_root_identity"],
        "formal_selection_identity": selection_identity,
        "manager_epoch": fixture.context["manager_epoch"],
        "package_id": fixture.context["package_id"],
    }
    call = {
        "client_unique_name": ":1.701",
        "manager_owner_after": ":1.700",
        "manager_owner_before": ":1.700",
        "unit_name": unit_name,
    }

    class EpochValidator:
        calls = 0

        @classmethod
        def validate_manager_epoch_capture_transcript(
            cls,
            transcript: object,
            *,
            expected_epoch: object,
        ) -> None:
            assert transcript == {"capture": "stable"}
            assert expected_epoch == fixture.context["manager_epoch"]
            cls.calls += 1

    acquisition = {
        **_reference_base_record(fixture, status="HELD", unit_name=unit_name),
        "acquire_call": call,
        "connection_verification": {
            "client_unique_name": ":1.701",
            "manager_owner": ":1.700",
            "unit_name": unit_name,
        },
        "lock_evidence": fixture.lock_identities,
        "manager_epoch_capture": {
            "manager_epoch": fixture.context["manager_epoch"],
            "transcript": {"capture": "stable"},
        },
        "resource_identity": resource_identity,
        "selection_identity": selection_identity,
    }
    checked_acquisition = success_verifier.validate_reference_acquisition(
        acquisition,
        expected=expected,
        expected_outer_identity=outer,
        expected_resource_identity=resource_identity,
        expected_lock_identities=fixture.lock_identities,
        transcript_validator=EpochValidator,
    )
    assert checked_acquisition["connection_verification"]["client_unique_name"] == ":1.701"
    assert checked_acquisition["outer_identity"] == outer
    assert EpochValidator.calls == 1

    extra = deepcopy(acquisition)
    extra["outer_identity"] = outer
    with pytest.raises(
        success_verifier.FormalSuccessVerificationError,
        match="field set drifted",
    ):
        success_verifier.validate_reference_acquisition(
            extra,
            expected=expected,
            expected_outer_identity=outer,
        )

    unref = {
        **_reference_base_record(
            fixture,
            status="UNREF_RETURNED",
            unit_name=unit_name,
        ),
        "acquisition_identity": acquisition_identity,
        "call": call,
        "observer_identity": observer_identity,
        "pre_unref_cleanup_identity": cleanup_identity,
    }
    checked_unref = success_verifier.validate_unref_call(
        unref,
        expected=expected,
        expected_outer_identity=outer,
        expected_acquisition_identity=acquisition_identity,
        expected_client_unique_name=":1.701",
        expected_observer_identity=observer_identity,
        expected_pre_unref_cleanup_identity=cleanup_identity,
    )
    assert checked_unref["call"]["manager_owner_before"] == ":1.700"

    drifted_unref = deepcopy(unref)
    drifted_unref["observer_identity"]["sha256"] = "0" * 64
    with pytest.raises(
        success_verifier.FormalSuccessVerificationError,
        match="prerequisite identity join drifted",
    ):
        success_verifier.validate_unref_call(
            drifted_unref,
            expected=expected,
            expected_outer_identity=outer,
            expected_acquisition_identity=acquisition_identity,
            expected_client_unique_name=":1.701",
            expected_observer_identity=observer_identity,
            expected_pre_unref_cleanup_identity=cleanup_identity,
        )

    release = {
        **_reference_base_record(fixture, status="RELEASED", unit_name=unit_name),
        "acquisition_identity": acquisition_identity,
        "connection_close_returned": True,
        "unref_call_identity": unref_identity,
    }
    checked_release = success_verifier.validate_reference_release(
        release,
        expected=expected,
        expected_outer_identity=outer,
        expected_acquisition_identity=acquisition_identity,
        expected_unref_call_identity=unref_identity,
    )
    assert checked_release["connection_close_returned"] is True


def _absence_record(frozen: dict[str, object]) -> dict[str, object]:
    return {
        "cgroup_absent": True,
        "control_group": frozen["control_group"],
        "identity_complete": True,
        "processes": frozen["processes"],
        "processes_absent": True,
        "slot": frozen["slot"],
        "source": frozen["source"],
        "systemctl": dict(closeout_state.ABSENT_SYSTEMD_STATE),
        "unit_absent": True,
        "unit_name": frozen["unit_name"],
    }


def test_success_verifier_binds_guardian_frozen_ledger_and_absence_order(
    tmp_path: Path,
) -> None:
    fixture = _formal_fixture(tmp_path)
    selection_identity = _identity(tmp_path, "selection.json", "a")
    child_audit_identity = _identity(tmp_path, "child-audit.json", "b")
    post_unref_identity = _identity(tmp_path, "post-unref.json", "c")
    guardian_absence_identity = _identity(tmp_path, "guardian-absence.json", "d")
    guardian_close_identity = _identity(tmp_path, "guardian-close.json", "e")
    detached_success_identity = _identity(tmp_path, "detached-closeout.json", "f")
    expected = {
        "campaign_root_identity": fixture.context["campaign_root_identity"],
        "formal_selection_identity": selection_identity,
        "manager_epoch": fixture.context["manager_epoch"],
        "package_id": fixture.context["package_id"],
    }
    children = [
        {
            "control_group": "",
            "identity_complete": True,
            "invocation_id": "",
            "ownership_classification": "SELECTED_NOT_STARTED",
            "processes": [],
            "slot": slot,
            "source": source,
            "unit_name": f"ab16-{source}-{index:02d}.service",
        }
        for index, (source, slot) in enumerate(
            closeout_state.EXPECTED_CHILD_ORDER,
            start=1,
        )
    ]
    outer_identity = {
        "control_group": "/user.slice/ab16-formal-outer-a001.service",
        "invocation_id": "4" * 32,
        "processes": [{"pid": 904, "starttime": 123_459}],
        "unit_name": str(fixture.context["outer_spec"]["unit_name"]),
    }
    frozen_outer = {
        **outer_identity,
        "identity_complete": True,
        "ownership_classification": "OUTER_LIVE_VERIFIED",
        "slot": "formal",
        "source": "outer",
    }
    ledger = {
        "child_audit_identity": child_audit_identity,
        "children": children,
        "outer": frozen_outer,
    }
    ledger_bytes = authority.canonical_json(ledger)
    guardian_close = {
        "absence_observation": {
            "all_absent": True,
            "records": [_absence_record(item) for item in [*children, frozen_outer]],
        },
        "authorizations": dict(launch_validator.FALSE_CLAIMS),
        "campaign_root_identity": fixture.context["campaign_root_identity"],
        "close_effect": {
            "errors": [],
            "guardian_copies_closed": True,
            "lock_identities": fixture.lock_identities,
            "supervisor_copies_must_remain_held": True,
        },
        "errors": [],
        "formal_selection_identity": selection_identity,
        "frozen_ledger": ledger,
        "ledger_message_identity": {
            "sha256": hashlib.sha256(ledger_bytes).hexdigest(),
            "size_bytes": len(ledger_bytes),
        },
        "outcome": "SUCCESS_CANDIDATE",
        "package_id": fixture.context["package_id"],
        "schema_version": success_verifier.GUARDIAN_LOCK_CLOSE_SCHEMA,
        "status": "GUARDIAN_COPIES_CLOSED",
        "success_eligible": True,
    }
    checked_close = success_verifier._validate_guardian_close(  # noqa: SLF001
        guardian_close,
        context=fixture.context,
        selection_identity=selection_identity,
        lock_identities=fixture.lock_identities,
        expected_frozen_children=children,
        expected_outer_identity=outer_identity,
        expected_child_audit_identity=child_audit_identity,
    )
    assert checked_close["frozen_ledger"] == ledger

    drifted = deepcopy(guardian_close)
    drifted["ledger_message_identity"]["sha256"] = "0" * 64
    with pytest.raises(
        success_verifier.FormalSuccessVerificationError,
        match="does not bind frozen_ledger",
    ):
        success_verifier._validate_guardian_close(  # noqa: SLF001
            drifted,
            context=fixture.context,
            selection_identity=selection_identity,
            lock_identities=fixture.lock_identities,
            expected_frozen_children=children,
            expected_outer_identity=outer_identity,
            expected_child_audit_identity=child_audit_identity,
        )

    guardian_identity = fixture.selection["guardian_unit_identity"]
    guardian_absence = {
        "authority_scope": success_verifier.AUTHORITY_SCOPE,
        "authorizations": dict(success_verifier.FALSE_AUTHORIZATIONS),
        "campaign_root_identity": fixture.context["campaign_root_identity"],
        "created_at_utc": "2026-07-28T00:05:00Z",
        "formal_selection_identity": selection_identity,
        "guardian_close_identity": guardian_close_identity,
        "manager_epoch": fixture.context["manager_epoch"],
        "package_id": fixture.context["package_id"],
        "schema_version": success_verifier.PHASE_SCHEMAS["guardian_absence"],
        "status": "PASS",
        "guardian_identity": guardian_identity,
        "post_unref_absence_identity": post_unref_identity,
        "systemctl": dict(success_verifier.ABSENT_SYSTEMD),
        "unit_absent": True,
        "cgroup_absent": True,
        "pid_absent": True,
    }
    success_verifier.validate_guardian_absence(
        guardian_absence,
        expected=expected,
        expected_guardian_identity=guardian_identity,
        expected_guardian_close_identity=guardian_close_identity,
        expected_post_unref_absence_identity=post_unref_identity,
    )
    dual = {
        "authority_scope": success_verifier.AUTHORITY_SCOPE,
        "authorizations": dict(success_verifier.FALSE_AUTHORIZATIONS),
        "campaign_root_identity": fixture.context["campaign_root_identity"],
        "created_at_utc": "2026-07-28T00:06:00Z",
        "formal_selection_identity": selection_identity,
        "detached_success_identity": detached_success_identity,
        "guardian_absence_identity": guardian_absence_identity,
        "guardian_close_identity": guardian_close_identity,
        "lock_identities": fixture.lock_identities,
        "manager_epoch": fixture.context["manager_epoch"],
        "package_id": fixture.context["package_id"],
        "schema_version": success_verifier.PHASE_SCHEMAS["dual_lock_release"],
        "status": "PASS",
        "supervisor_release": {
            "after_guardian_absence": True,
            "attempted": True,
            "recorded": True,
            "returned": True,
        },
        "terminal_join": {
            "detached_success_before_guardian_close": True,
            "guardian_absence_before_supervisor_release": True,
            "locks_released_after_substantive_verification": True,
        },
    }
    success_verifier.validate_dual_lock_release(
        dual,
        expected=expected,
        expected_lock_identities=fixture.lock_identities,
        expected_detached_success_identity=detached_success_identity,
        expected_guardian_absence_identity=guardian_absence_identity,
        expected_guardian_close_identity=guardian_close_identity,
    )
    legacy_dual = deepcopy(dual)
    legacy_dual["schema_version"] = (
        "noncert-cuts-ab16-formal-dual-lock-release-v1"
    )
    with pytest.raises(
        success_verifier.FormalSuccessVerificationError,
        match="dual_lock_release common authority join drifted",
    ):
        success_verifier.validate_dual_lock_release(
            legacy_dual,
            expected=expected,
            expected_lock_identities=fixture.lock_identities,
            expected_detached_success_identity=detached_success_identity,
            expected_guardian_absence_identity=guardian_absence_identity,
            expected_guardian_close_identity=guardian_close_identity,
        )


def test_child_audit_requires_state_owner_authorization_projection() -> None:
    record = {
        "all_children_absent": True,
        "audit_errors": [],
        "authorizations": dict(launch_validator.FALSE_CLAIMS),
        "containment_used": False,
        "final_observation": {},
        "frozen_children": [],
        "mode": "NORMAL_REPLAY",
        "normal_replay": {},
        "records": [],
        "schema_version": success_verifier.CHILD_AUDIT_SCHEMA,
        "status": "PASS",
    }
    with pytest.raises(
        success_verifier.FormalSuccessVerificationError,
        match="not a normal all-absence replay",
    ):
        success_verifier._validate_child_audit(record, controller={})  # noqa: SLF001

    record["authorizations"] = dict(closeout_state.FALSE_AUTHORIZATIONS)
    with pytest.raises(
        success_verifier.FormalSuccessVerificationError,
        match="cardinality drifted",
    ):
        success_verifier._validate_child_audit(record, controller={})  # noqa: SLF001


def _failure_ledger(
    fixture: FormalFixture,
    *,
    child_audit_identity: dict[str, object] | None = None,
) -> dict[str, object]:
    children = [
        {
            "control_group": "",
            "identity_complete": True,
            "invocation_id": "",
            "ownership_classification": "NOT_STARTED",
            "processes": [],
            "slot": slot,
            "source": source,
            "unit_name": "",
        }
        for source, slot in closeout_state.EXPECTED_CHILD_ORDER
    ]
    return {
        "child_audit_identity": (
            {} if child_audit_identity is None else child_audit_identity
        ),
        "children": children,
        "outer": {
            "control_group": "",
            "identity_complete": True,
            "invocation_id": "",
            "ownership_classification": "NOT_STARTED",
            "processes": [],
            "slot": "formal",
            "source": "outer",
            "unit_name": str(fixture.context["outer_spec"]["unit_name"]),
        },
    }


def _failure_observation(ledger: dict[str, object]) -> dict[str, object]:
    return {
        "all_absent": True,
        "records": [
            _absence_record(item)
            for item in [*ledger["children"], ledger["outer"]]
        ],
    }


def _write_record(path: Path, record: dict[str, object]) -> dict[str, object]:
    return authority._write_exclusive(  # noqa: SLF001 - test fixture publication
        path,
        authority.canonical_json(record),
        mode=0o444,
    )


def _pre_release_success_record(
    fixture: FormalFixture,
    *,
    selection_identity: dict[str, object],
) -> dict[str, object]:
    root = Path(str(fixture.context["campaign_dir"]))
    return {
        "authority_scope": success_verifier.AUTHORITY_SCOPE,
        "authorizations": dict(success_verifier.FALSE_AUTHORIZATIONS),
        "b6_changed": False,
        "bounds_changed": False,
        "campaign_root_identity": fixture.context["campaign_root_identity"],
        "child_audit_identity": _identity(root, "child-audit.json", "1"),
        "controller_result_identity": _identity(
            root,
            "controller-result.json",
            "2",
        ),
        "created_at_utc": "2026-07-29T00:00:00Z",
        "formal_selection_identity": selection_identity,
        "lock_identities": fixture.lock_identities,
        "lock_lifecycle": {
            "guardian_close_is_next_required_step": True,
            "supervisor_lock_release_permitted": False,
            "supervisor_locks_must_remain_held": True,
        },
        "lower_bound": "absent",
        "package_id": fixture.context["package_id"],
        "phase_receipt_identities": {
            phase: _identity(root, f"{phase}.json", f"{index:x}")
            for index, phase in enumerate(
                success_verifier.PRE_RELEASE_PHASES,
                start=3,
            )
        },
        "production_authority_changed": False,
        "production_certified": False,
        "repository_head": fixture.context["repository_head"],
        "schema_version": success_verifier.SUCCESS_RECEIPT_SCHEMA,
        "stage_b_changed": False,
        "status": "PRE_RELEASE_VERIFIED",
        "terminal_classification_identity": _identity(
            root,
            "terminal-classification.json",
            "d",
        ),
        "upper_bound": [1188, 18],
        "verdict": (
            "AB16_FORMAL_SUBSTANTIVE_REPLAY_VERIFIED_LOCKS_STILL_REQUIRED"
        ),
    }


def test_pre_release_success_v2_rejects_v1_and_mixed_failure_join(
    tmp_path: Path,
) -> None:
    fixture = _formal_fixture(tmp_path)
    selection_identity = _identity(tmp_path, "selection.json", "e")
    record = _pre_release_success_record(
        fixture,
        selection_identity=selection_identity,
    )
    success_verifier.validate_pre_release_success(
        record,
        context=fixture.context,
        selection_identity=selection_identity,
        expected_lock_identities=fixture.lock_identities,
    )

    legacy = deepcopy(record)
    legacy["schema_version"] = (
        "noncert-cuts-ab16-formal-detached-success-v1"
    )
    with pytest.raises(
        success_verifier.FormalSuccessVerificationError,
        match="crossed its claim or lock-lifecycle boundary",
    ):
        success_verifier.validate_pre_release_success(
            legacy,
            context=fixture.context,
            selection_identity=selection_identity,
            expected_lock_identities=fixture.lock_identities,
        )

    output = Path(
        str(
            fixture.context["outer_spec"]["receipt_paths"][
                "detached_closeout"
            ]
        )
    )
    output.parent.mkdir(parents=True)
    identity = _write_record(output, legacy)
    with pytest.raises(
        success_verifier.FormalSuccessVerificationError,
        match="crossed its claim or lock-lifecycle boundary",
    ):
        success_verifier._validate_prior_success_output(  # noqa: SLF001
            identity,
            context=fixture.context,
            phase="GUARDIAN_CLOSE_NOT_ATTEMPTED",
            selection_identity=selection_identity,
            expected_lock_identities=fixture.lock_identities,
        )


def _failure_guardian_record(
    fixture: FormalFixture,
    *,
    ledger: dict[str, object],
    formal_selection_identity: dict[str, object] | str,
) -> dict[str, object]:
    return {
        "authorizations": dict(success_verifier.FALSE_AUTHORIZATIONS),
        "campaign_root_identity": fixture.context["campaign_root_identity"],
        "errors": [],
        "formal_selection_identity": formal_selection_identity,
        "frozen_ledger_sha256": hashlib.sha256(
            authority.canonical_json(ledger)
        ).hexdigest(),
        "guardian_absence": {
            "cgroup_absent": True,
            "pid_absent": True,
            "systemctl": dict(success_verifier.ABSENT_SYSTEMD),
            "unit_absent": True,
        },
        "guardian_identity": fixture.selection["guardian_unit_identity"],
        "lower_bound": "absent",
        "outcome": "INCOMPLETE",
        "package_id": fixture.context["package_id"],
        "production_certified": False,
        "schema_version": success_verifier.CONTAINMENT_GUARDIAN_ABSENCE_SCHEMA,
        "status": "GUARDIAN_ABSENT",
        "success_eligible": False,
        "upper_bound": [1188, 18],
    }


def _failure_release_record(
    fixture: FormalFixture,
    *,
    cleanup_evidence: dict[str, object],
    formal_selection_identity: dict[str, object] | str,
    guardian_absence_identity: dict[str, object],
    incomplete_identity: dict[str, object],
    marker_identity: dict[str, object] | str,
    phase: str,
) -> dict[str, object]:
    return {
        "attempt_directory_created": True,
        "attempt_marker_identity": marker_identity,
        "authority_scope": success_verifier.AUTHORITY_SCOPE,
        "authorizations": dict(success_verifier.FALSE_AUTHORIZATIONS),
        "b6_changed": False,
        "bounds_changed": False,
        "campaign_root_identity": fixture.context["campaign_root_identity"],
        "cleanup_evidence": cleanup_evidence,
        "created_at_utc": "2026-07-28T03:00:00Z",
        "detached_success_output_identity": "absent",
        "formal_selection_identity": formal_selection_identity,
        "guardian_absence_identity": guardian_absence_identity,
        "heavy_identities_absent": True,
        "incomplete_identity": incomplete_identity,
        "lock_identities": fixture.lock_identities,
        "lock_lifecycle": {
            "detached_incomplete_is_next_required_step": True,
            "supervisor_lock_release_permitted": False,
            "supervisor_locks_must_remain_held": True,
        },
        "lower_bound": "absent",
        "outcome": "INCOMPLETE",
        "package_id": fixture.context["package_id"],
        "phase": phase,
        "production_authority_changed": False,
        "production_certified": False,
        "retry_eligible": False,
        "schema_version": success_verifier.FAILURE_RELEASE_SCHEMA,
        "stage_b_changed": False,
        "status": "INCOMPLETE_PRE_RELEASE",
        "success_eligible": False,
        "upper_bound": [1188, 18],
    }


def test_detached_incomplete_markerless_replay_is_oexcl_and_non_authorizing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _formal_fixture(tmp_path)
    campaign = Path(str(fixture.context["campaign_dir"]))
    attempt = Path(str(fixture.context["formal_attempt_dir"]))
    attempt.mkdir(parents=True)
    directory_identity = success_verifier._directory_identity(attempt)  # noqa: SLF001
    failure = {"code": "ATTEMPT_MARKER_FAILED_OR_UNCERTAIN", "detail": "write failed"}
    markerless = {
        "attempt_consumption_effect": {
            "attempted": True,
            "error": failure,
            "recorded": False,
            "returned": False,
        },
        "authorizations": dict(closeout_state.FALSE_AUTHORIZATIONS),
        "campaign_root_identity": fixture.context["campaign_root_identity"],
        "consumed": True,
        "failure": failure,
        "formal_dir_identity": directory_identity,
        "lower_bound": None,
        "marker_canonical_identity_recorded": False,
        "no_backfill": True,
        "package_id": fixture.context["package_id"],
        "phase": "DIRECTORY_CREATED_MARKER_UNRECORDED",
        "production_certified": False,
        "retry_eligible": False,
        "schema_version": closeout_state.MARKERLESS_SCHEMA,
        "status": "CONSUMED_INCOMPLETE",
        "upper_bound": [1188, 18],
    }
    incomplete_identity = _write_record(
        attempt / "markerless-consumed-incomplete.json",
        markerless,
    )
    ledger = _failure_ledger(fixture)
    observation = _failure_observation(ledger)
    guardian = _failure_guardian_record(
        fixture,
        ledger=ledger,
        formal_selection_identity="absent",
    )
    guardian_identity = _write_record(
        attempt / "containment-guardian-absence.json",
        guardian,
    )
    cleanup = {
        "containment_clearance_identity": "absent",
        "containment_hold_identity": "absent",
        "containment_lock_release_identity": "absent",
        "containment_lock_release_publication": "absent",
        "errors": [failure],
        "final_observation": observation,
        "frozen_ledger": ledger,
        "reference_terminal": {"kind": "NO_REFERENCE_OPENED"},
    }
    release = _failure_release_record(
        fixture,
        cleanup_evidence=cleanup,
        formal_selection_identity="absent",
        guardian_absence_identity=guardian_identity,
        incomplete_identity=incomplete_identity,
        marker_identity="absent",
        phase="DIRECTORY_CREATED_MARKER_UNRECORDED",
    )
    release_path = attempt / "failure-release.json"
    _write_record(release_path, release)
    monkeypatch.setattr(
        launch_validator,
        "replay_formal_launch_context",
        lambda *_args, **_kwargs: fixture.context,
    )
    for name in ("replay_gate_approvals", "replay_repository_snapshot", "replay"):
        monkeypatch.setattr(authority, name, lambda *_args, **_kwargs: {})

    result = success_verifier.verify_incomplete(
        campaign_dir=campaign,
        incomplete_release=release_path,
    )
    output = Path(
        str(
            fixture.context["outer_spec"]["receipt_paths"][
                "detached_incomplete_closeout"
            ]
        )
    )
    assert result["status"] == "PRE_RELEASE_VERIFIED_INCOMPLETE"
    assert result["detached_incomplete"]["schema_version"] == (
        "noncert-cuts-ab16-formal-detached-incomplete-v3"
    )
    assert result["detached_incomplete"]["authorizations"] == dict(
        success_verifier.FALSE_AUTHORIZATIONS
    )
    assert result["detached_incomplete_identity"]["path"] == str(output)
    assert output.name == "detached-incomplete-closeout.json"
    assert not Path(
        str(fixture.context["outer_spec"]["receipt_paths"]["detached_closeout"])
    ).exists()
    with pytest.raises(Exception, match="NO_OVERWRITE_COLLISION"):
        success_verifier.verify_incomplete(
            campaign_dir=campaign,
            incomplete_release=release_path,
        )


def _empty_effect_snapshot(
    marker_identity: dict[str, object],
) -> dict[str, object]:
    return {
        "abort_close_attempted": False,
        "abort_close_return": None,
        "acquire_attempted": False,
        "acquire_return": None,
        "acquire_returned": False,
        "close_attempted": False,
        "close_returned": False,
        "connection_action": "",
        "detached_success_verifier_attempted": False,
        "detached_success_verifier_return": None,
        "guardian_close_attempted": False,
        "guardian_close_return": None,
        "lock_release_attempted": False,
        "lock_release_return": None,
        "outer_launch_attempted": False,
        "outer_launch_return": None,
        "publications": {
            "attempt-consumption": {
                "attempted": True,
                "recorded": True,
                "recorded_identity": marker_identity,
                "returned": True,
                "returned_identity": marker_identity,
            }
        },
        "release_attempted": False,
        "release_return": None,
        "release_returned": False,
    }


def test_detached_incomplete_selected_release_binds_selection_and_cleanup(
    tmp_path: Path,
) -> None:
    fixture = _formal_fixture(tmp_path)
    attempt = Path(str(fixture.context["formal_attempt_dir"]))
    marker_identity = _identity(attempt, "attempt-consumption.json", "8")
    selection_identity = _identity(
        Path(str(fixture.context["campaign_dir"])) / "formal-ab16",
        "formal-selection-a001.json",
        "9",
    )
    phase = "SELECTION_RECORDED_OUTER_NOT_LAUNCHED"
    incomplete_identity = _identity(
        attempt,
        "incomplete-selection-recorded-outer-not-launched.json",
        "a",
    )
    incomplete_raw = {
        "attempt_basis": {"identity": marker_identity, "kind": "RECORDED"},
        "authorizations": dict(closeout_state.FALSE_AUTHORIZATIONS),
        "campaign_root_identity": fixture.context["campaign_root_identity"],
        "consumed": True,
        "effects": _empty_effect_snapshot(marker_identity),
        "failure": {"code": "FORMAL_CAMPAIGN_FAILED", "detail": "prelaunch stop"},
        "formal_dir": str(attempt),
        "joins": {"selection_identity": selection_identity},
        "lower_bound": None,
        "package_id": fixture.context["package_id"],
        "phase": phase,
        "production_certified": False,
        "retry_eligible": False,
        "schema_version": closeout_state.INCOMPLETE_SCHEMA,
        "status": "CONSUMED_INCOMPLETE",
        "upper_bound": [1188, 18],
    }
    incomplete = success_verifier.validate_consumed_incomplete(
        incomplete_raw,
        context=fixture.context,
        expected_identity=incomplete_identity,
        expected_marker_identity=marker_identity,
        expected_phase=phase,
        expected_selection_identity=selection_identity,
    )
    legacy_incomplete = deepcopy(incomplete_raw)
    legacy_incomplete["schema_version"] = (
        "noncert-cuts-ab16-formal-consumed-incomplete-v1"
    )
    with pytest.raises(
        success_verifier.FormalSuccessVerificationError,
        match="marker/path/state join drifted",
    ):
        success_verifier.validate_consumed_incomplete(
            legacy_incomplete,
            context=fixture.context,
            expected_identity=incomplete_identity,
            expected_marker_identity=marker_identity,
            expected_phase=phase,
            expected_selection_identity=selection_identity,
        )
    ledger = _failure_ledger(fixture)
    guardian = _failure_guardian_record(
        fixture,
        ledger=ledger,
        formal_selection_identity=selection_identity,
    )
    guardian_identity = _identity(
        attempt,
        "containment-guardian-absence.json",
        "b",
    )
    cleanup = {
        "containment_clearance_identity": "absent",
        "containment_hold_identity": "absent",
        "containment_lock_release_identity": "absent",
        "containment_lock_release_publication": "absent",
        "errors": [],
        "final_observation": _failure_observation(ledger),
        "frozen_ledger": ledger,
        "reference_terminal": {"kind": "NO_REFERENCE_OPENED"},
    }
    release = _failure_release_record(
        fixture,
        cleanup_evidence=cleanup,
        formal_selection_identity=selection_identity,
        guardian_absence_identity=guardian_identity,
        incomplete_identity=incomplete_identity,
        marker_identity=marker_identity,
        phase=phase,
    )
    checked = success_verifier.validate_failure_release(
        release,
        context=fixture.context,
        expected_identity=_identity(attempt, "failure-release.json", "c"),
        expected_incomplete=incomplete,
        expected_incomplete_identity=incomplete_identity,
        expected_guardian_absence=guardian,
        expected_guardian_absence_identity=guardian_identity,
        expected_marker_identity=marker_identity,
        expected_selection_identity=selection_identity,
        expected_lock_identities=fixture.lock_identities,
    )
    assert checked["formal_selection_identity"] == selection_identity
    legacy_release = deepcopy(release)
    legacy_release["schema_version"] = (
        "noncert-cuts-ab16-formal-failure-release-v2"
    )
    with pytest.raises(
        success_verifier.FormalSuccessVerificationError,
        match="pre-release failure authority/topology/lock join drifted",
    ):
        success_verifier.validate_failure_release(
            legacy_release,
            context=fixture.context,
            expected_identity=_identity(attempt, "failure-release.json", "c"),
            expected_incomplete=incomplete,
            expected_incomplete_identity=incomplete_identity,
            expected_guardian_absence=guardian,
            expected_guardian_absence_identity=guardian_identity,
            expected_marker_identity=marker_identity,
            expected_selection_identity=selection_identity,
            expected_lock_identities=fixture.lock_identities,
        )
    drifted = deepcopy(release)
    drifted["cleanup_evidence"]["final_observation"]["records"][0][
        "unit_absent"
    ] = False
    with pytest.raises(
        success_verifier.FormalSuccessVerificationError,
        match="cleanup evidence replay failed",
    ):
        success_verifier.validate_failure_release(
            drifted,
            context=fixture.context,
            expected_identity=_identity(attempt, "failure-release.json", "c"),
            expected_incomplete=incomplete,
            expected_incomplete_identity=incomplete_identity,
            expected_guardian_absence=guardian,
            expected_guardian_absence_identity=guardian_identity,
            expected_marker_identity=marker_identity,
            expected_selection_identity=selection_identity,
            expected_lock_identities=fixture.lock_identities,
        )


def test_failure_terminal_release_v3_binds_locks_held_detached_replay(
    tmp_path: Path,
) -> None:
    fixture = _formal_fixture(tmp_path)
    attempt = Path(str(fixture.context["formal_attempt_dir"]))
    selection_identity = _identity(tmp_path, "selection.json", "1")
    pre_release_identity = _identity(attempt, "failure-release.json", "2")
    detached_identity = _identity(
        attempt,
        "detached-incomplete-closeout.json",
        "3",
    )
    terminal_identity = _identity(
        attempt,
        "failure-terminal-release.json",
        "4",
    )
    record = {
        "authority_scope": success_verifier.AUTHORITY_SCOPE,
        "authorizations": dict(success_verifier.FALSE_AUTHORIZATIONS),
        "b6_changed": False,
        "bounds_changed": False,
        "campaign_root_identity": fixture.context["campaign_root_identity"],
        "created_at_utc": "2026-07-29T04:00:00Z",
        "detached_substantive_identity": detached_identity,
        "detached_substantive_kind": "detached_incomplete_v3",
        "failure_pre_release_identity": pre_release_identity,
        "formal_selection_identity": selection_identity,
        "lock_identities": fixture.lock_identities,
        "lock_release_effect": {
            "lock_identities": fixture.lock_identities,
            "released": True,
        },
        "lower_bound": "absent",
        "outcome": "INCOMPLETE",
        "package_id": fixture.context["package_id"],
        "phase": "SELECTION_RECORDED_OUTER_NOT_LAUNCHED",
        "production_authority_changed": False,
        "production_certified": False,
        "retry_eligible": False,
        "schema_version": success_verifier.FAILURE_TERMINAL_RELEASE_SCHEMA,
        "stage_b_changed": False,
        "status": "INCOMPLETE_RELEASED",
        "success_eligible": False,
        "terminal_join": {
            "detached_substantive_before_supervisor_release": True,
            "locks_released_after_substantive_verification": True,
            "terminal_predecessor_is_unique": True,
        },
        "terminal_predecessor_identity": "absent",
        "upper_bound": [1188, 18],
    }
    checked = success_verifier.validate_failure_terminal_release(
        record,
        context=fixture.context,
        expected_identity=terminal_identity,
        expected_lock_identities=fixture.lock_identities,
        expected_detached_substantive_identity=detached_identity,
        expected_detached_substantive_kind="detached_incomplete_v3",
        expected_failure_pre_release_identity=pre_release_identity,
        expected_selection_identity=selection_identity,
        expected_terminal_predecessor_identity="absent",
    )
    assert checked["detached_substantive_identity"] == detached_identity

    legacy = deepcopy(record)
    legacy["schema_version"] = (
        "noncert-cuts-ab16-formal-failure-release-v2"
    )
    with pytest.raises(
        success_verifier.FormalSuccessVerificationError,
        match="failure terminal authority/topology/lock join drifted",
    ):
        success_verifier.validate_failure_terminal_release(
            legacy,
            context=fixture.context,
            expected_identity=terminal_identity,
            expected_lock_identities=fixture.lock_identities,
            expected_detached_substantive_identity=detached_identity,
            expected_detached_substantive_kind="detached_incomplete_v3",
            expected_failure_pre_release_identity=pre_release_identity,
            expected_selection_identity=selection_identity,
            expected_terminal_predecessor_identity="absent",
        )

    success_detached = _identity(
        Path(
            str(
                fixture.context["outer_spec"]["receipt_paths"][
                    "detached_closeout"
                ]
            )
        ).parent,
        Path(
            str(
                fixture.context["outer_spec"]["receipt_paths"][
                    "detached_closeout"
                ]
            )
        ).name,
        "5",
    )
    dual_identity = _identity(
        Path(
            str(
                fixture.context["outer_spec"]["receipt_paths"][
                    "dual_lock_release"
                ]
            )
        ).parent,
        Path(
            str(
                fixture.context["outer_spec"]["receipt_paths"][
                    "dual_lock_release"
                ]
            )
        ).name,
        "6",
    )
    post_release = deepcopy(record)
    post_release.update(
        {
            "detached_substantive_identity": success_detached,
            "detached_substantive_kind": "pre_release_success_v2",
            "failure_pre_release_identity": "absent",
            "phase": "FINAL_SUCCESS_RETURN_FAILED_OR_UNCERTAIN",
            "terminal_predecessor_identity": dual_identity,
        }
    )
    checked_post_release = (
        success_verifier.validate_failure_terminal_release(
            post_release,
            context=fixture.context,
            expected_identity=terminal_identity,
            expected_lock_identities=fixture.lock_identities,
            expected_detached_substantive_identity=success_detached,
            expected_detached_substantive_kind="pre_release_success_v2",
            expected_failure_pre_release_identity="absent",
            expected_selection_identity=selection_identity,
            expected_terminal_predecessor_identity=dual_identity,
        )
    )
    assert checked_post_release["terminal_predecessor_identity"] == dual_identity

    early_release = deepcopy(record)
    early_release["terminal_join"][
        "detached_substantive_before_supervisor_release"
    ] = False
    with pytest.raises(
        success_verifier.FormalSuccessVerificationError,
        match="failure terminal authority/topology/lock join drifted",
    ):
        success_verifier.validate_failure_terminal_release(
            early_release,
            context=fixture.context,
            expected_identity=terminal_identity,
            expected_lock_identities=fixture.lock_identities,
            expected_detached_substantive_identity=detached_identity,
            expected_detached_substantive_kind="detached_incomplete_v3",
            expected_failure_pre_release_identity=pre_release_identity,
            expected_selection_identity=selection_identity,
            expected_terminal_predecessor_identity="absent",
        )


def test_containment_pre_release_cleanup_rejects_any_lock_release_effect(
    tmp_path: Path,
) -> None:
    fixture = _formal_fixture(tmp_path)
    ledger = _failure_ledger(
        fixture,
        child_audit_identity=_identity(tmp_path, "child-audit.json", "1"),
    )
    guardian = _failure_guardian_record(
        fixture,
        ledger=ledger,
        formal_selection_identity=_identity(tmp_path, "selection.json", "2"),
    )
    returned = _identity(
        Path(str(fixture.context["formal_attempt_dir"])),
        "lock-release.json",
        "3",
    )
    cleanup = {
        "containment_clearance_identity": _identity(
            tmp_path,
            "containment-cleared-after-hold.json",
            "4",
        ),
        "containment_hold_identity": _identity(
            tmp_path,
            "containment-hold.json",
            "5",
        ),
        "containment_lock_release_identity": "unrecorded",
        "containment_lock_release_publication": {
            "attempted": True,
            "error": {"code": "READBACK_FAILED", "detail": "uncertain readback"},
            "recorded": False,
            "returned": True,
            "returned_identity": returned,
        },
        "errors": [],
        "final_observation": _failure_observation(ledger),
        "frozen_ledger": ledger,
        "reference_terminal": {"kind": "NO_REFERENCE_OPENED"},
    }
    incomplete = {
        "joins": {
            "child_audit_identity": ledger["child_audit_identity"],
            "frozen_outer_identity": ledger["outer"],
        }
    }
    with pytest.raises(
        success_verifier.FormalSuccessVerificationError,
        match="containment pre-release cleanup topology drifted",
    ):
        success_verifier._validate_cleanup_evidence(  # noqa: SLF001
            cleanup,
            context=fixture.context,
            incomplete=incomplete,
            guardian_absence=guardian,
            phase="CONTAINMENT_HOLD",
        )
    clean = deepcopy(cleanup)
    clean["containment_lock_release_identity"] = "absent"
    clean["containment_lock_release_publication"] = "absent"
    checked = success_verifier._validate_cleanup_evidence(  # noqa: SLF001
        clean,
        context=fixture.context,
        incomplete=incomplete,
        guardian_absence=guardian,
        phase="CONTAINMENT_HOLD",
    )
    assert checked["containment_lock_release_identity"] == "absent"
    assert checked["containment_lock_release_publication"] == "absent"
    direct = deepcopy(cleanup)
    direct.update(
        {
            "containment_clearance_identity": "absent",
            "containment_hold_identity": "absent",
            "containment_lock_release_identity": "absent",
            "containment_lock_release_publication": "absent",
        }
    )
    checked_direct = success_verifier._validate_cleanup_evidence(  # noqa: SLF001
        direct,
        context=fixture.context,
        incomplete={"joins": {}},
        guardian_absence=guardian,
        phase="SELECTION_RECORDED_OUTER_NOT_LAUNCHED",
    )
    assert checked_direct["containment_lock_release_publication"] == "absent"


def test_detached_success_verifier_cli_modes_are_mutually_exclusive(
    tmp_path: Path,
) -> None:
    parser = success_verifier._parser()  # noqa: SLF001
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--campaign-dir",
                str(tmp_path),
                "--formal-selection",
                str(tmp_path / "selection.json"),
                "--incomplete-release",
                str(tmp_path / "failure-release.json"),
            ]
        )
    with pytest.raises(SystemExit):
        parser.parse_args(["--campaign-dir", str(tmp_path)])


def test_success_verifier_is_separate_from_producers_and_rejects_receipt_drift(
    tmp_path: Path,
) -> None:
    source = Path(success_verifier.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    forbidden = {
        "docs.research.noncert_cuts_ab16_20260724.ab16_formal_campaign_v1",
        "docs.research.noncert_cuts_ab16_20260724.ab16_formal_controller_v1",
        "docs.research.noncert_cuts_ab16_20260724.ab16_outer_guardian_v1",
        "docs.research.noncert_cuts_ab16_20260724.ab16_outer_refunit_closeout_v1",
    }
    assert imported_modules.isdisjoint(forbidden)
    calls = {_call_name(node) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    forbidden_state_producer_calls = {
        "closeout_state._publish_once",
        "closeout_state._reference_record",
        "closeout_state.acquire_reference_once",
        "closeout_state.finalize_reference_once",
        "closeout_state.publish_attempt_consumption",
        "closeout_state.publish_consumed_incomplete",
        "closeout_state.verify_detached_incomplete_chain",
    }
    assert calls.isdisjoint(forbidden_state_producer_calls)

    writer_owners: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(
            isinstance(child, ast.Attribute) and child.attr == "_write_exclusive"
            for child in ast.walk(node)
        ):
            writer_owners.append(node.name)
    assert writer_owners == ["_publish_final_receipt"]

    fixture = _formal_fixture(tmp_path)
    record, expected = _valid_outer_prelaunch(fixture)
    checked = success_verifier.validate_outer_prelaunch(
        record,
        expected=expected,
        expected_unit_name=str(fixture.context["outer_spec"]["unit_name"]),
        expected_lock_identities=fixture.lock_identities,
    )
    assert checked["prelaunch_absence"]["load_state"] == "not-found"

    extra = deepcopy(record)
    extra["unproved"] = False
    with pytest.raises(
        success_verifier.FormalSuccessVerificationError,
        match="field set drifted",
    ):
        success_verifier.validate_outer_prelaunch(
            extra,
            expected=expected,
            expected_unit_name=str(fixture.context["outer_spec"]["unit_name"]),
            expected_lock_identities=fixture.lock_identities,
        )

    authority_drift = deepcopy(record)
    authority_drift["authorizations"]["upper_bound_update_authorized"] = True
    with pytest.raises(
        success_verifier.FormalSuccessVerificationError,
        match="authority join drifted",
    ):
        success_verifier.validate_outer_prelaunch(
            authority_drift,
            expected=expected,
            expected_unit_name=str(fixture.context["outer_spec"]["unit_name"]),
            expected_lock_identities=fixture.lock_identities,
        )
