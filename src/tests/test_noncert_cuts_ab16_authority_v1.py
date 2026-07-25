from __future__ import annotations

import copy
import hashlib
import importlib.util
import inspect
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = PROJECT_ROOT / "docs/research/noncert_cuts_ab16_20260724/ab16_authority_v1.py"


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ab16_authority_v1_tested", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


AUTH = _load_tool()


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _json(path: Path, value: object) -> Path:
    return _write(path, AUTH.canonical_json(value))


def _identity(path: Path) -> dict[str, object]:
    return AUTH.detached_identity(AUTH.snapshot_regular(path))


def _reseal(package: Path) -> None:
    covered = sorted(path for path in package.rglob("*") if path.is_file() and path.name != "SHA256SUMS")
    (package / "SHA256SUMS").write_bytes(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(package).as_posix()}\n"
            for path in covered
        ).encode()
    )


CAMPAIGN_TOOL = b"""
def validate_campaign_root(root, campaign_dir=None):
    assert root["schema_version"] == "fixture-campaign-root"
    assert root["stage_topology"]["gate1_v4"]["order"] == 1
    assert root["stage_topology"]["prospective_ab16"]["order"] == 2
    return root

def verify_package(package_dir, *, expected_manager_epoch, replay_external):
    import hashlib
    from pathlib import Path
    package = Path(package_dir)
    seal = package / "SHA256SUMS"
    manifest = package / "package-manifest.json"
    return {
        "manifest_identity": {
            "path": str(manifest),
            "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "size_bytes": len(manifest.read_bytes()),
        },
        "package_id": hashlib.sha256(seal.read_bytes()).hexdigest(),
        "seal_identity": {
            "path": str(seal),
            "sha256": hashlib.sha256(seal.read_bytes()).hexdigest(),
            "size_bytes": len(seal.read_bytes()),
        },
        "status": "PASS",
    }

def validate_continuation_authorization(value, *, root):
    assert value["schema_version"] == "noncert-cuts-gate1-v4-continuation-authorization-v1"
    assert value["campaign_id"] == root["campaign_id"]
    assert value["manager_epoch"] == root["manager_epoch"]
    return value

def validate_manager_epoch(value):
    assert value["schema"] == "noncert-cuts-manager-boot-epoch-v4"
    return value

def validate_manager_epoch_capture_transcript(value, *, expected_epoch):
    assert value == {
        "fixture_manager_epoch": expected_epoch,
        "schema": "fixture-manager-epoch-transcript-v1",
    }
    return value
"""

BASELINE_TOOL = b"""
import json
from pathlib import Path

def admit_paths(*, legacy_control, rebuilt_model, rebuilt_metadata, fixed_assignment_replay, created_at_utc):
    del legacy_control, rebuilt_model, rebuilt_metadata, created_at_utc
    admission = Path(fixed_assignment_replay).parent.parent / "baseline-admission-a001.json"
    return json.loads(admission.read_text())
"""


def _full_source_identity(path: Path) -> dict[str, object]:
    snapshot = AUTH.snapshot_regular(path)
    return {
        "device": snapshot.device,
        "inode": snapshot.inode,
        "mode": snapshot.mode,
        "mode_octal": f"{snapshot.mode:04o}",
        "path": str(snapshot.path),
        "requested_path": str(snapshot.path),
        "sha256": snapshot.sha256,
        "size_bytes": snapshot.size_bytes,
    }


def _arm_records(campaign: Path, namespace: str) -> list[dict[str, object]]:
    result = []
    for configuration in AUTH.CONFIGURATIONS:
        for order in AUTH.ORDERS:
            for arm in AUTH.ARMS:
                slot = f"{configuration}-{order}-{arm}"
                result.append(
                    {
                        "arm": arm,
                        "attempt_dir": str(campaign / "prospective-ab16/arms" / slot),
                        "configuration": configuration,
                        "order": order,
                        "slot": slot,
                        "unit_name": f"{namespace}-ab16-{slot}.service",
                    }
                )
    return result


def _manager_epoch() -> dict[str, object]:
    return {
        "boot_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "dbus_unique_owner": ":1.44",
        "manager_pid": 123,
        "manager_pid_starttime": 456,
        "manager_executable": {
            "device": 8,
            "inode": 99,
            "mode": 0o755,
            "path": "/usr/lib/systemd/systemd",
            "sha256": "a" * 64,
            "size_bytes": 100,
        },
        "manager_features": "+TEST",
        "manager_version": "fixture",
        "schema": "noncert-cuts-manager-boot-epoch-v4",
    }


def _path_preregistration(campaign: Path) -> dict[str, object]:
    prospective = campaign / "prospective-ab16"
    baseline = prospective / "baseline"
    payload = campaign / "campaign-authority/package/payload"
    slots = [
        f"{configuration}-{order}-{arm}"
        for configuration in AUTH.CONFIGURATIONS
        for order in AUTH.ORDERS
        for arm in AUTH.ARMS
    ]
    attempts = {slot: str(prospective / "arms" / slot) for slot in slots}
    return {
        "arithmetic_replay_paths": {
            slot: str(Path(attempts[slot]) / "replays/independent-arithmetic.json") for slot in slots
        },
        "arm_gate_paths": {slot: str(Path(attempts[slot]) / "replays/arm-credibility.json") for slot in slots},
        "arm_selection_paths": {slot: str(Path(attempts[slot]) / "selection.json") for slot in slots},
        "attempt_dirs": attempts,
        "baseline_admission_path": str(prospective / "baseline-admission-a001.json"),
        "baseline_fixed_replay_path": str(baseline / "fixed-replay-a001.json"),
        "baseline_incumbent_path": str(baseline / "incumbent.json"),
        "baseline_rebuilt_metadata_path": str(baseline / "rebuilt-model-metadata.json"),
        "baseline_rebuilt_model_path": str(baseline / "cut-free-model.bin"),
        "binding_paths": {slot: str(prospective / "bindings" / f"{slot}.json") for slot in slots},
        "campaign_dir": str(campaign),
        "classification_contract_path": str(payload / "tool.ab16_contract_v1.py"),
        "common_prestate_path": str(prospective / "common-prestate-a001.json"),
        "cut_free_replay_paths": {
            slot: str(Path(attempts[slot]) / "replays/cut-free-incumbent.json") for slot in slots
        },
        "immediate_stop_path": str(prospective / "immediate-stop-a001.json"),
        "launch_environment_paths": {
            slot: str(prospective / "pre-run-candidates" / f"{slot}-launch-environment.json") for slot in slots
        },
        "manifest_path": str(prospective / "manifest-a001.json"),
        "preselection_epoch_paths": {
            slot: str(prospective / "pre-run-candidates" / f"{slot}-preselection-epoch.json") for slot in slots
        },
        "preselection_transcript_paths": {
            slot: str(prospective / "pre-run-candidates" / f"{slot}-preselection-transcript.json") for slot in slots
        },
        "pre_run_authority_paths": {slot: str(Path(attempts[slot]) / "pre-run-authority.json") for slot in slots},
        "pre_run_candidate_paths": {slot: str(prospective / "pre-run-candidates" / f"{slot}.json") for slot in slots},
        "resource_replay_paths": {
            slot: str(Path(attempts[slot]) / "replays/independent-resource-terminal.json") for slot in slots
        },
        "purpose": "prospective_noncert_cuts_ab16_path_authority",
        "run_nonce": campaign.name,
        "schema": AUTH.PATH_PREREGISTRATION_SCHEMA,
        "suite_selection_path": str(prospective / "selection-a001.json"),
        "terminal_classification_path": str(prospective / "terminal-classification-a001.json"),
    }


def _gate_approvals(tmp_path: Path, campaign: Path) -> dict[str, Path]:
    gate_a = _json(
        tmp_path / "sources/gate-a.json",
        {
            "approval_id": "fixture-gate-a",
            "arm_launch_authorized": False,
            "created_at_utc": "2026-07-24T00:00:00Z",
            "decision": "PASS",
            "formal_campaign_creation_authorized": False,
            "gate": "A",
            "offline_candidate_only": True,
            "planned_source_set_digest": "a" * 64,
            "purpose": "AB16_OFFLINE_SOURCE_SET_PREFLIGHT",
            "repository_head": "3" * 40,
            "repository_root": str(tmp_path),
            "run_nonce": campaign.name,
            "schema_version": AUTH.GATE_A_SCHEMA,
            "target_campaign_dir": str(campaign),
        },
    )
    gate_b = _json(
        tmp_path / "sources/gate-b.json",
        {
            "approval_id": "fixture-gate-b",
            "arm_launch_authorized": False,
            "candidate_identity": _identity(gate_a),
            "created_at_utc": "2026-07-24T00:00:01Z",
            "decision": "APPROVED",
            "formal_campaign_creation_authorized": True,
            "gate": "B",
            "gate_a_receipt_identity": _identity(gate_a),
            "planned_source_set_digest": "a" * 64,
            "purpose": "AB16_FORMAL_CAMPAIGN_IDENTITY_CREATION",
            "repository_head": "3" * 40,
            "repository_root": str(tmp_path),
            "run_nonce": campaign.name,
            "schema_version": AUTH.GATE_B_SCHEMA,
            "target_campaign_dir": str(campaign),
        },
    )
    return {"gate_a": gate_a, "gate_b": gate_b}


def _package(tmp_path: Path, campaign: Path, epoch: dict[str, object]) -> dict[str, Any]:
    package = campaign / "campaign-authority/package"
    payload = package / "payload"
    payload.mkdir(parents=True)
    gates = _gate_approvals(tmp_path, campaign)
    actual_tools = {
        role: PROJECT_ROOT / "docs/research/noncert_cuts_ab16_20260724" / filename
        for role, filename in {
            "tool.ab16_terminal_gate_v1.py": "ab16_terminal_gate_v1.py",
            "tool.organic_arm_replay_v1.py": "organic_arm_replay_v1.py",
            "tool.organic_arm_runner_v1.py": "organic_arm_runner_v1.py",
            "tool.organic_resource_lifecycle_v1.py": "organic_resource_lifecycle_v1.py",
            "tool.organic_resource_verifier_v1.py": "organic_resource_verifier_v1.py",
        }.items()
    }
    source_paths: dict[str, Path] = {}
    for role in sorted(AUTH.REQUIRED_PACKAGE_ROLES):
        if role == "campaign_authority_v4.py":
            data = CAMPAIGN_TOOL
        elif role == "tool.baseline_admission_v1.py":
            data = BASELINE_TOOL
        elif role == "tool.ab16_authority_v1.py":
            data = TOOL_PATH.read_bytes()
        elif role in actual_tools:
            data = actual_tools[role].read_bytes()
        elif role == "input.ab16_gate_a_receipt.json":
            source_paths[role] = gates["gate_a"]
            continue
        elif role == "input.ab16_gate_b_approval.json":
            source_paths[role] = gates["gate_b"]
            continue
        elif role == "input.ab16_path_preregistration.json":
            source_paths[role] = _json(
                tmp_path / "sources/ab16-path-preregistration.json",
                _path_preregistration(campaign),
            )
            continue
        else:
            data = AUTH.canonical_json({"fixture_role": role})
        source_paths[role] = _write(tmp_path / "sources" / role.replace("/", "_"), data)
    records = []
    members = []
    for role in sorted(source_paths):
        source = source_paths[role]
        package_path = f"payload/{role}"
        packaged = _write(package / package_path, source.read_bytes())
        members.append(
            {
                "path": package_path,
                "sha256": hashlib.sha256(packaged.read_bytes()).hexdigest(),
                "size_bytes": packaged.stat().st_size,
            }
        )
        records.append(
            {
                "package_path": package_path,
                "parse_json": role.startswith("input."),
                "role": role,
                "source_identity": _full_source_identity(source),
            }
        )
    manifest = {
        "authorization_semantics": "fixture",
        "external_sources": records,
        "manager_epoch": epoch,
        "package_members": members,
        "repository_head": "3" * 40,
        "run_nonce": "run-fixture-ab16",
        "schema": "fixture-package",
        "seal_contract": {},
    }
    manifest_path = _json(package / "package-manifest.json", manifest)
    covered = sorted(path for path in package.rglob("*") if path.is_file())
    seal_bytes = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(package).as_posix()}\n" for path in covered
    ).encode()
    seal_path = _write(package / "SHA256SUMS", seal_bytes)
    return {
        "dir": package,
        "gates": gates,
        "manifest": manifest_path,
        "seal": seal_path,
        "sources": source_paths,
    }


def _fixture(tmp_path: Path) -> dict[str, Any]:
    campaign = tmp_path / "run-fixture-ab16"
    campaign.mkdir(parents=True)
    epoch = _manager_epoch()
    package = _package(tmp_path, campaign, epoch)
    source_records = {
        item["role"]: item["source_identity"]
        for item in json.loads(package["manifest"].read_text())["external_sources"]
    }
    tool_role_map = {
        "campaign_authority_v4": "campaign_authority_v4.py",
        "ab16_authority_v1": "tool.ab16_authority_v1.py",
        "ab16_campaign_bootstrap_v1": "tool.ab16_campaign_bootstrap_v1.py",
        "ab16_contract_v1": "tool.ab16_contract_v1.py",
        "ab16_terminal_gate_v1": "tool.ab16_terminal_gate_v1.py",
        "baseline_admission_v1": "tool.baseline_admission_v1.py",
        "baseline_rebuild_v1": "tool.baseline_rebuild_v1.py",
        "cut_free_incumbent_replay_v1": "tool.cut_free_incumbent_replay_v1.py",
        "disposable_drill_authority_v1": "tool.disposable_drill_authority_v1.py",
        "disposable_drill_payload_v1": "tool.disposable_drill_payload_v1.py",
        "organic_arm_runner_v1": "tool.organic_arm_runner_v1.py",
        "organic_arm_replay_v1": "tool.organic_arm_replay_v1.py",
        "organic_resource_lifecycle_v1": "tool.organic_resource_lifecycle_v1.py",
        "organic_resource_verifier_v1": "tool.organic_resource_verifier_v1.py",
        "organic_unit_orchestrator_v1": "tool.organic_unit_orchestrator_v1.py",
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
        "python3_13": "system.python3_13.bin",
        "sudo": "system.sudo.bin",
        "systemctl": "system.systemctl.bin",
        "systemd_run": "system.systemd_run.bin",
    }
    input_role_map = {
        "ab16_bootstrap_manager_epoch_capture": "input.ab16_bootstrap_manager_epoch_capture.json",
        "ab16_gate_a_receipt": "input.ab16_gate_a_receipt.json",
        "ab16_gate_b_approval": "input.ab16_gate_b_approval.json",
        "ab16_offline_candidate": "input.ab16_offline_candidate.json",
        "ab16_path_preregistration": "input.ab16_path_preregistration.json",
        "candidate_placements": "input.candidate_placements.json",
        "canonical_rules": "input.canonical_rules.json",
        "cuts_mandatory_schedule": "input.cuts_mandatory_schedule.txt",
        "history_freeze_manifest": "input.history_freeze_manifest.json",
        "legacy_control_a002": "input.legacy_control_a002.json",
        "mandatory_instances": "input.mandatory_instances.json",
        "project_lock": "input.project_lock.txt",
    }
    authority_tools = {
        key: {field: source_records[role][field] for field in ("path", "sha256", "size_bytes")}
        for key, role in tool_role_map.items()
    }
    strict_inputs = {
        key: {field: source_records[role][field] for field in ("path", "sha256", "size_bytes")}
        for key, role in input_role_map.items()
    }
    namespace = "cuts-g1v4-fixture"
    positive = campaign / "gate1-v4/positive-control-common"
    gate1_units = {
        slot: {
            "attempt_dir": str(campaign / "gate1-v4/units" / slot),
            "slot": slot,
            "unit_name": f"{namespace}-{slot}.service",
        }
        for slot in AUTH.GATE1_SLOTS
    }
    root = {
        "authority_tools": authority_tools,
        "campaign_id": "c" * 64,
        "manager_epoch": epoch,
        "package": {
            "manifest_identity": _identity(package["manifest"]),
            "package_dir": str(package["dir"]),
            "package_id": hashlib.sha256(package["seal"].read_bytes()).hexdigest(),
            "seal_identity": _identity(package["seal"]),
        },
        "repository_head": "3" * 40,
        "run_nonce": "run-fixture-ab16",
        "schema_version": "fixture-campaign-root",
        "stage_topology": {
            "gate1_v4": {
                "continuation_path": str(campaign / "gate1-v4/continuation.json"),
                "order": 1,
                "positive_control": {
                    "binding_paths": {
                        "control": str(positive / "bindings/control.json"),
                        "treatment": str(positive / "bindings/treatment.json"),
                    },
                    "binding_seal_path": str(positive / "bindings/seal.json"),
                    "common_artifact_paths": {
                        "incumbent": str(positive / "common-prestate/incumbent.json"),
                        "response": str(positive / "common-prestate/response.pb"),
                    },
                    "common_manifest_path": str(positive / "common-prestate/manifest.json"),
                },
                "units": gate1_units,
            },
            "prospective_ab16": {
                "arm_selection_path": str(campaign / "prospective-ab16/selection-a001.json"),
                "arms": _arm_records(campaign, namespace),
                "manifest_path": str(campaign / "prospective-ab16/manifest-a001.json"),
                "order": 2,
                "requires_continuation_schema": AUTH.CONTINUATION_SCHEMA,
                "suite": "prospective-ab16",
                "terminal_classification_path": str(campaign / "prospective-ab16/terminal-classification-a001.json"),
            },
        },
        "strict_inputs": strict_inputs,
    }
    root_path = _json(campaign / "campaign-root.json", root)
    replays = {}
    for slot in AUTH.GATE1_SLOTS:
        replay = _json(campaign / f"gate1-v4/replays/{slot}.json", {"slot": slot, "status": "PASS"})
        replays[slot] = _identity(replay)
    continuation = {
        "campaign_closed": False,
        "campaign_id": root["campaign_id"],
        "campaign_root_identity": _identity(root_path),
        "continuation_authorized": True,
        "continuation_eligible": True,
        "created_at_utc": "2026-07-24T00:00:00Z",
        "detached_replay_identities": replays,
        "future_child": {
            "arm_selection_path": root["stage_topology"]["prospective_ab16"]["arm_selection_path"],
            "manifest_path": root["stage_topology"]["prospective_ab16"]["manifest_path"],
            "slots_absent": True,
            "suite": "prospective-ab16",
        },
        "gate1_result_identity": _identity(replays["forced-treatment"]["path"]),
        "gate1_selection_identity": _identity(replays["forced-control"]["path"]),
        "gate_admission_epoch_identity": _identity(replays["q-success"]["path"]),
        "manager_epoch": epoch,
        "organic_arm_launch_authorized": False,
        "run_nonce": root["run_nonce"],
        "schema_version": AUTH.CONTINUATION_SCHEMA,
    }
    continuation_path = _json(Path(root["stage_topology"]["gate1_v4"]["continuation_path"]), continuation)
    return {
        "campaign": campaign,
        "continuation": continuation_path,
        "package": package,
        "root": root,
        "root_path": root_path,
    }


def _baseline(fixture: dict[str, Any]) -> Path:
    campaign = fixture["campaign"]
    prereg = _path_preregistration(campaign)
    model = _write(Path(prereg["baseline_rebuilt_model_path"]), b"model")
    metadata = _write(
        Path(prereg["baseline_rebuilt_metadata_path"]),
        b"{}\n",
    )
    incumbent = _write(
        Path(prereg["baseline_incumbent_path"]),
        b'{"fixture":"incumbent"}\n',
    )
    _write(Path(prereg["baseline_fixed_replay_path"]), b"{}\n")
    receipt_path = Path(prereg["baseline_admission_path"])
    receipt = {
        "admission_tool_identity": fixture["root"]["authority_tools"]["baseline_admission_v1"],
        "authorizations": {
            "baseline_inputs_admitted": True,
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "organic_arm_launch_authorized": False,
            "solver_run_authorized": False,
        },
        "created_at_utc": "2026-07-24T00:01:00Z",
        "expected_baseline": {
            "incumbent_sha256": _identity(incumbent)["sha256"],
        },
        "expectation_profile": "fixture",
        "fixed_assignment_replay": {
            "incumbent_identity": _identity(incumbent),
            "receipt_identity": _identity(Path(prereg["baseline_fixed_replay_path"])),
            "replay_tool_identity": fixture["root"]["authority_tools"]["cut_free_incumbent_replay_v1"],
        },
        "legacy_control": {"identity": fixture["root"]["strict_inputs"]["legacy_control_a002"]},
        "rebuilt_model": {
            "identity": _identity(model),
            "metadata": {
                "builder_identity": fixture["root"]["authority_tools"]["baseline_rebuild_v1"],
                "input_identities": {
                    role: fixture["root"]["strict_inputs"][role]
                    for role in (
                        "candidate_placements",
                        "canonical_rules",
                        "mandatory_instances",
                    )
                },
                "metadata_identity": _identity(metadata),
            },
        },
        "schema_version": AUTH.BASELINE_ADMISSION_SCHEMA,
        "status": "PASS",
        "verdict": "AB16_BASELINE_INPUTS_ADMITTED",
    }
    return _json(receipt_path, receipt)


def _load_research_tool(filename: str, name: str) -> ModuleType:
    path = PROJECT_ROOT / "docs/research/noncert_cuts_ab16_20260724" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _identity_with_mode(path: Path) -> dict[str, object]:
    snapshot = AUTH.snapshot_regular(path)
    return {
        "mode": snapshot.mode,
        **AUTH.detached_identity(snapshot),
    }


def _prepare_manifest_and_suite(fixture: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    _baseline(fixture)
    manifest = AUTH.build_manifest(fixture["campaign"])["manifest"]
    suite = AUTH.create_suite_selection(fixture["campaign"])["selection"]
    return manifest, suite


def _pre_run_candidate(
    fixture: dict[str, Any],
    *,
    slot: str,
) -> tuple[Path, dict[str, Any]]:
    lifecycle = _load_research_tool(
        "organic_resource_lifecycle_v1.py",
        f"resource_lifecycle_fixture_{slot.replace('-', '_')}",
    )
    campaign = fixture["campaign"]
    prereg = _path_preregistration(campaign)
    root = fixture["root"]
    manifest_path = Path(prereg["manifest_path"])
    suite_path = Path(prereg["suite_selection_path"])
    manifest = json.loads(manifest_path.read_text())
    arm = next(item for item in AUTH._launch_plan(root) if item["slot"] == slot)
    epoch_path = Path(prereg["preselection_epoch_paths"][slot])
    epoch_transcript_value = {
        "fixture_manager_epoch": root["manager_epoch"],
        "schema": "fixture-manager-epoch-transcript-v1",
    }
    epoch_transcript = _write(
        Path(prereg["preselection_transcript_paths"][slot]),
        json.dumps(
            epoch_transcript_value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8"),
    )
    epoch = lifecycle.build_epoch_observation(
        phase="preselection",
        slot=slot,
        observed_epoch=root["manager_epoch"],
        observed_at_monotonic_ns=123456,
        capture_transcript_identity=_identity_with_mode(epoch_transcript),
    )
    _write(epoch_path, lifecycle.canonical_json_bytes(epoch))
    environment_record = {
        "clear_ambient": True,
        "schema_version": lifecycle.LAUNCH_ENVIRONMENT_SCHEMA,
        "variables": {
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
            "HOME": "/home/fixture",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": "/usr/local/bin:/usr/bin",
            "PYTHONHASHSEED": "0",
            "TZ": "UTC",
            "XDG_RUNTIME_DIR": "/run/user/1000",
        },
    }
    environment = _write(
        Path(prereg["launch_environment_paths"][slot]),
        lifecycle.canonical_json_bytes(environment_record),
    )
    attempt = Path(prereg["attempt_dirs"][slot])
    output_names = {
        "attempt_result": "result.json",
        "cleanup": "cleanup.json",
        "detached_replay": "detached-replay.json",
        "inner": "inner-lifecycle.json",
        "preterminal": "preterminal-resource.json",
        "release": "release-token.json",
        "resource_verification": "resource-verification.json",
        "terminal": "terminal-envelope.json",
    }
    epoch_names = {
        phase: f"manager-epoch-{phase}.json"
        for phase in (
            "launch",
            "preterminal",
            "release",
            "terminal",
            "cleanup",
            "detached-replay",
        )
    }
    transcript_names = {phase: f"manager-transcript-{phase}.json" for phase in epoch_names}
    tool_sources = {
        "busctl": root["authority_tools"]["busctl"],
        "manager_attestor": root["authority_tools"]["manager_attestor_v4"],
        "manager_epoch_authority": root["authority_tools"]["campaign_authority_v4"],
        "organic_arm_runner": root["authority_tools"]["organic_arm_runner_v1"],
        "organic_resource_lifecycle": root["authority_tools"]["organic_resource_lifecycle_v1"],
        "organic_resource_verifier": root["authority_tools"]["organic_resource_verifier_v1"],
        "organic_unit_orchestrator": root["authority_tools"]["organic_unit_orchestrator_v1"],
        "python3_13": root["authority_tools"]["python3_13"],
        "sudo": root["authority_tools"]["sudo"],
        "systemctl": root["authority_tools"]["systemctl"],
        "systemd_run": root["authority_tools"]["systemd_run"],
    }
    tools = {role: _identity_with_mode(Path(identity["path"])) for role, identity in tool_sources.items()}
    record = {
        "arm": arm["arm"],
        "arm_binding_identity": manifest["arm_binding_identities"][slot],
        "arm_launch_authorized": False,
        "arm_selection_write_authorized": True,
        "attempt_dir": str(attempt),
        "authority_chain": manifest["authority_chain"],
        "baseline_admission_identity": manifest["baseline_admission_identity"],
        "baseline_incumbent_sha256": manifest["baseline_incumbent_identity"]["sha256"],
        "campaign_id": root["campaign_id"],
        "campaign_root_identity": _identity(fixture["root_path"]),
        "common_prestate_identity": manifest["common_prestate_identity"],
        "configuration": arm["configuration"],
        "continuation_identity": _identity(fixture["continuation"]),
        "epoch_observation_paths": {phase: str(attempt / name) for phase, name in epoch_names.items()},
        "epoch_transcript_paths": {phase: str(attempt / name) for phase, name in transcript_names.items()},
        "execution_class": "FORMAL_AB16",
        "expected_payload_status": {
            "exit_code": 0,
            "expectation": "SUCCESS",
            "signal": 0,
        },
        "launch": {
            "cwd": manifest["repository_root"],
            "environment_identity": _identity_with_mode(environment),
            "payload_argv": [
                tools["python3_13"]["path"],
                "-I",
                tools["organic_arm_runner"]["path"],
                "--selection",
                prereg["arm_selection_paths"][slot],
            ],
            "python3_13_path": tools["python3_13"]["path"],
            "systemctl_path": tools["systemctl"]["path"],
            "systemd_run_path": tools["systemd_run"]["path"],
            "supervisor_argv": [
                tools["python3_13"]["path"],
                "-I",
                tools["organic_resource_lifecycle"]["path"],
                "supervise",
                "--pre-run",
                prereg["pre_run_authority_paths"][slot],
                "--selection",
                prereg["arm_selection_paths"][slot],
            ],
        },
        "manager_epoch": root["manager_epoch"],
        "order": arm["order"],
        "output_paths": {role: str(attempt / name) for role, name in output_names.items()},
        "package": {
            "manifest_identity": root["package"]["manifest_identity"],
            "package_id": root["package"]["package_id"],
            "seal_identity": root["package"]["seal_identity"],
        },
        "pre_run_authority_path": prereg["pre_run_authority_paths"][slot],
        "prelaunch_allowlist": ["pre-run-authority.json", "selection.json"],
        "preflight_results": {
            "epoch_identity_pass": True,
            "head_identity_pass": True,
            "package_replay_pass": True,
            "path_preregistration_pass": True,
            "resource_contract_pass": True,
            "slot_order_pass": True,
            "strict_inputs_replay_pass": True,
            "tool_identities_replay_pass": True,
        },
        "preselection_epoch_identity": _identity(epoch_path),
        "preselection_transcript_identity": _identity_with_mode(epoch_transcript),
        "prospective_manifest_identity": _identity(manifest_path),
        "purpose": lifecycle.PRE_RUN_PURPOSE,
        "repository_head": root["repository_head"],
        "repository_git_tool_identity": manifest["repository_git_tool_identity"],
        "repository_root": manifest["repository_root"],
        "resource_contract": lifecycle.RESOURCE_CONTRACTS["FORMAL_AB16"],
        "run_nonce": root["run_nonce"],
        "runner_selection_path": prereg["arm_selection_paths"][slot],
        "schema_version": lifecycle.PRE_RUN_AUTHORITY_SCHEMA,
        "seed": manifest["seed"],
        "slot": slot,
        "solver_run_authorized": False,
        "status": "PASS",
        "strict_input_identities": {
            role: _identity_with_mode(Path(identity["path"])) for role, identity in root["strict_inputs"].items()
        },
        "suite_selection_identity": _identity(suite_path),
        "tool_identities": tools,
        "unit_name": arm["unit_name"],
        "verdict": "AB16_ORGANIC_PRE_RUN_AUTHORITY_PASS",
        "workers": 1,
    }
    path = Path(prereg["pre_run_candidate_paths"][slot])
    _write(path, lifecycle.canonical_json_bytes(record))
    return path, record


def test_manifest_requires_continuation_and_baseline(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    with pytest.raises(AUTH.AuthorityError, match="INPUT_OPEN_FAILED|PATH_MISSING"):
        AUTH.build_manifest(fixture["campaign"])
    _baseline(fixture)
    fixture["continuation"].unlink()
    with pytest.raises(AUTH.AuthorityError, match="INPUT_OPEN_FAILED"):
        AUTH.build_manifest(fixture["campaign"])


def test_runner_exact_manifest_and_nonlaunching_suite(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    manifest, suite = _prepare_manifest_and_suite(fixture)
    runner = _load_research_tool(
        "organic_arm_runner_v1.py",
        "organic_runner_manifest_fixture",
    )
    assert runner.validate_manifest(manifest) == manifest
    assert manifest["schema_version"] == runner.MANIFEST_SCHEMA
    assert manifest["arm_sequence"] == list(runner.ARM_SEQUENCE)
    assert manifest["arithmetic_verifier"]["purpose"] == (runner.FORMAL_ARITHMETIC_PURPOSE)
    assert (
        manifest["arithmetic_verifier"]["tool_identity"]
        != fixture["root"]["authority_tools"]["independent_arithmetic_v4"]
    )
    assert manifest["experiment_contract"]["budget"]["arm_hard_guard_seconds"] == 3600
    assert manifest["experiment_contract"]["resource_contract"]["runtime_max_sec"] == 3600
    assert suite["arm_launch_authorized"] is False
    assert suite["solver_run_authorized"] is False
    assert suite["organic_manifest_validated"] is True
    assert AUTH.replay(fixture["campaign"], selection_required=True)["status"] == "PASS"


def test_package_and_path_preregistration_mutations_fail_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    _baseline(fixture)
    prereg_source = fixture["package"]["sources"]["input.ab16_path_preregistration.json"]
    prereg = json.loads(prereg_source.read_text())
    first = next(iter(prereg["binding_paths"]))
    prereg["binding_paths"][first] += ".drift"
    prereg_source.write_bytes(AUTH.canonical_json(prereg))
    with pytest.raises(
        AUTH.AuthorityError,
        match="PACKAGE_SOURCE_DRIFT|PATH_PREREGISTRATION_INVALID",
    ):
        AUTH.build_manifest(fixture["campaign"])

    second = _fixture(tmp_path / "second")
    _baseline(second)
    _write(second["package"]["dir"] / "payload/__pycache__/bad.pyc", b"bad")
    with pytest.raises(AUTH.AuthorityError, match="PACKAGE_PYCACHE_REJECTED"):
        AUTH.build_manifest(second["campaign"])


def test_manifest_formal_purpose_and_binding_mutations_close_replay(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    _prepare_manifest_and_suite(fixture)
    manifest_path = Path(_path_preregistration(fixture["campaign"])["manifest_path"])
    runner = _load_research_tool(
        "organic_arm_runner_v1.py",
        "organic_runner_mutation_fixture",
    )
    manifest = json.loads(manifest_path.read_text())
    manifest["arithmetic_verifier"]["purpose"] = "gate1_v4_disposable_drill_applied_inequality_replay"
    manifest_path.write_bytes(runner.canonical_json(manifest))
    with pytest.raises(AUTH.AuthorityError, match="MANIFEST_INVALID"):
        AUTH.replay(fixture["campaign"], selection_required=True)


def test_generated_common_prestate_and_binding_mutations_close_replay(
    tmp_path: Path,
) -> None:
    common_fixture = _fixture(tmp_path / "common")
    _prepare_manifest_and_suite(common_fixture)
    prereg = _path_preregistration(common_fixture["campaign"])
    common_path = Path(prereg["common_prestate_path"])
    common = json.loads(common_path.read_text())
    common["seed"] += 1
    common_path.write_bytes(AUTH.canonical_json(common))
    with pytest.raises(
        AUTH.AuthorityError,
        match="COMMON_PRESTATE_INVALID",
    ):
        AUTH.replay(common_fixture["campaign"], selection_required=True)

    binding_fixture = _fixture(tmp_path / "binding")
    manifest, _ = _prepare_manifest_and_suite(binding_fixture)
    prereg = _path_preregistration(binding_fixture["campaign"])
    slot = manifest["arm_sequence"][0]
    binding_path = Path(prereg["binding_paths"][slot])
    binding = json.loads(binding_path.read_text())
    binding["enabled_families"] = ["region_capacity"]
    binding_path.write_bytes(AUTH.canonical_json(binding))
    with pytest.raises(AUTH.AuthorityError, match="ARM_BINDING_INVALID"):
        AUTH.replay(binding_fixture["campaign"], selection_required=True)


def test_baseline_package_tool_and_input_root_joins_fail_closed(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    receipt_path = _baseline(fixture)
    receipt = json.loads(receipt_path.read_text())
    receipt["rebuilt_model"]["metadata"]["builder_identity"] = fixture["root"]["authority_tools"][
        "baseline_admission_v1"
    ]
    receipt_path.write_bytes(AUTH.canonical_json(receipt))
    with pytest.raises(
        AUTH.AuthorityError,
        match="BASELINE_ADMISSION_ROOT_JOIN_FAILED",
    ):
        AUTH.build_manifest(fixture["campaign"])


@pytest.mark.parametrize(
    "mutation",
    (
        "epoch",
        "head",
        "package",
        "resource",
        "strict-input",
        "tool",
        "slot",
    ),
)
def test_pre_run_mutations_fail_before_attempt_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    fixture = _fixture(tmp_path)
    manifest, _ = _prepare_manifest_and_suite(fixture)
    slot = manifest["arm_sequence"][0]
    path, record = _pre_run_candidate(fixture, slot=slot)
    lifecycle = _load_research_tool(
        "organic_resource_lifecycle_v1.py",
        f"resource_lifecycle_mutation_{mutation}",
    )
    if mutation == "epoch":
        record["manager_epoch"]["boot_id"] = "drift"
    elif mutation == "head":
        record["repository_head"] = "f" * 40
    elif mutation == "package":
        record["package"]["package_id"] = "f" * 64
    elif mutation == "resource":
        record["resource_contract"]["runtime_max_seconds"] = 3599
    elif mutation == "strict-input":
        first = next(iter(record["strict_input_identities"].values()))
        first["sha256"] = "f" * 64
    elif mutation == "tool":
        record["tool_identities"]["organic_arm_runner"]["sha256"] = "f" * 64
    else:
        record["slot"] = manifest["arm_sequence"][1]
    path.write_bytes(lifecycle.canonical_json_bytes(record))
    monkeypatch.setattr(
        AUTH,
        "_observe_repository_head",
        lambda _context: fixture["root"]["repository_head"],
    )
    with pytest.raises(AUTH.AuthorityError, match="PRE_RUN_AUTHORITY_INVALID"):
        AUTH.create_arm_selection(
            fixture["campaign"],
            slot=slot,
            selection_nonce="fixture-a001",
        )
    assert not Path(_path_preregistration(fixture["campaign"])["attempt_dirs"][slot]).exists()


def test_arm_selection_is_runner_exact_and_o_excl(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    manifest, _ = _prepare_manifest_and_suite(fixture)
    slot = manifest["arm_sequence"][0]
    _pre_run_candidate(fixture, slot=slot)
    monkeypatch.setattr(
        AUTH,
        "_observe_repository_head",
        lambda _context: fixture["root"]["repository_head"],
    )
    result = AUTH.create_arm_selection(
        fixture["campaign"],
        slot=slot,
        selection_nonce="fixture-a001",
    )
    attempt = Path(manifest["attempt_dirs"][slot])
    assert {path.name for path in attempt.iterdir()} == {
        "pre-run-authority.json",
        "selection.json",
    }
    runner = _load_research_tool(
        "organic_arm_runner_v1.py",
        "organic_runner_selection_fixture",
    )
    selection = json.loads((attempt / "selection.json").read_text())
    assert runner.validate_selection(selection, manifest=manifest) == selection
    assert selection["pre_run_authority_identity"] == result["pre_run_authority_identity"]
    with pytest.raises(
        AUTH.AuthorityError,
        match="ARM_ORDER_OR_NO_OVERWRITE_VIOLATION",
    ):
        AUTH.create_arm_selection(
            fixture["campaign"],
            slot=slot,
            selection_nonce="fixture-a002",
        )


def test_authority_builds_nonlaunching_pre_run_candidate_o_excl(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    manifest, _ = _prepare_manifest_and_suite(fixture)
    slot = manifest["arm_sequence"][0]
    transcript = {
        "fixture_manager_epoch": fixture["root"]["manager_epoch"],
        "schema": "fixture-manager-epoch-transcript-v1",
    }
    monkeypatch.setattr(
        AUTH,
        "_capture_current_manager_epoch",
        lambda _context: {
            "manager_epoch": fixture["root"]["manager_epoch"],
            "transcript": transcript,
        },
    )
    monkeypatch.setattr(
        AUTH,
        "_observe_repository_head",
        lambda _context: fixture["root"]["repository_head"],
    )
    for name, value in {
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
        "HOME": "/home/fixture",
        "PATH": "/usr/local/bin:/usr/bin",
        "XDG_RUNTIME_DIR": "/run/user/1000",
    }.items():
        monkeypatch.setenv(name, value)
    result = AUTH.build_pre_run_candidate(
        fixture["campaign"],
        slot=slot,
    )
    prereg = _path_preregistration(fixture["campaign"])
    assert result["status"] == "PASS"
    assert result["candidate"]["execution_class"] == "FORMAL_AB16"
    assert result["candidate"]["launch"]["payload_argv"][1:3] == [
        "-I",
        result["candidate"]["tool_identities"]["organic_arm_runner"]["path"],
    ]
    assert not Path(prereg["attempt_dirs"][slot]).exists()
    for field in (
        "launch_environment_paths",
        "preselection_epoch_paths",
        "preselection_transcript_paths",
        "pre_run_candidate_paths",
    ):
        assert Path(prereg[field][slot]).is_file()
    with pytest.raises(
        AUTH.AuthorityError,
        match="PRE_RUN_CANDIDATE_ALREADY_EXISTS",
    ):
        AUTH.build_pre_run_candidate(fixture["campaign"], slot=slot)


def test_partial_preselection_failure_stops_without_consuming_arm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    manifest, _ = _prepare_manifest_and_suite(fixture)
    slot = manifest["arm_sequence"][0]
    prereg = _path_preregistration(fixture["campaign"])
    transcript = {
        "fixture_manager_epoch": fixture["root"]["manager_epoch"],
        "schema": "fixture-manager-epoch-transcript-v1",
    }
    monkeypatch.setattr(
        AUTH,
        "_capture_current_manager_epoch",
        lambda _context: {
            "manager_epoch": fixture["root"]["manager_epoch"],
            "transcript": transcript,
        },
    )
    monkeypatch.setattr(
        AUTH,
        "_observe_repository_head",
        lambda _context: fixture["root"]["repository_head"],
    )
    for name, value in {
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
        "HOME": "/home/fixture",
        "PATH": "/usr/local/bin:/usr/bin",
        "XDG_RUNTIME_DIR": "/run/user/1000",
    }.items():
        monkeypatch.setenv(name, value)
    real_write = AUTH._write_exclusive  # noqa: SLF001
    candidate_path = Path(prereg["pre_run_candidate_paths"][slot])

    def fail_candidate(path: Path | str, data: bytes) -> dict[str, object]:
        if Path(path) == candidate_path:
            raise AUTH.AuthorityError(
                "FIXTURE_CANDIDATE_PUBLICATION_FAILED",
                slot,
            )
        return real_write(path, data)

    monkeypatch.setattr(AUTH, "_write_exclusive", fail_candidate)
    with pytest.raises(
        AUTH.AuthorityError,
        match="FIXTURE_CANDIDATE_PUBLICATION_FAILED",
    ):
        AUTH.build_pre_run_candidate(fixture["campaign"], slot=slot)

    assert not Path(prereg["attempt_dirs"][slot]).exists()
    stop = json.loads(Path(prereg["immediate_stop_path"]).read_text(encoding="utf-8"))
    assert stop["code"] == "AB16_PRESELECTION_FAIL_CLOSED"
    assert stop["failure_code"] == "FIXTURE_CANDIDATE_PUBLICATION_FAILED"
    assert stop["selection_created"] is False
    assert stop["arm_slot_consumed"] is False
    assert stop["partial_output_identities"]["candidate"] is None
    assert all(stop["partial_output_identities"][role] is not None for role in ("environment", "epoch", "transcript"))


def _publish_fake_arm_gate_inputs(
    fixture: dict[str, Any],
    *,
    preregistration: dict[str, Any],
    slot: str,
    pre_run: dict[str, Any],
) -> tuple[dict[str, object], None]:
    for path in (
        pre_run["output_paths"]["attempt_result"],
        pre_run["output_paths"]["resource_verification"],
        pre_run["output_paths"]["detached_replay"],
        preregistration["arithmetic_replay_paths"][slot],
        preregistration["resource_replay_paths"][slot],
        preregistration["arm_gate_paths"][slot],
    ):
        output = Path(path)
        if not output.exists():
            _json(output, {"slot": slot, "status": "PASS"})
    return _identity(Path(preregistration["arm_gate_paths"][slot])), None


def test_credible_consumption_allows_next_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    manifest, _ = _prepare_manifest_and_suite(fixture)
    first, second = manifest["arm_sequence"][:2]
    _pre_run_candidate(fixture, slot=first)
    monkeypatch.setattr(
        AUTH,
        "_observe_repository_head",
        lambda _context: fixture["root"]["repository_head"],
    )
    AUTH.create_arm_selection(
        fixture["campaign"],
        slot=first,
        selection_nonce="fixture-first",
    )
    prereg = _path_preregistration(fixture["campaign"])

    def replay_fake(
        _context: dict[str, Any],
        **kwargs: Any,
    ) -> tuple[dict[str, object], None]:
        return _publish_fake_arm_gate_inputs(
            fixture,
            preregistration=prereg,
            slot=kwargs["slot"],
            pre_run=kwargs["pre_run"],
        )

    monkeypatch.setattr(
        AUTH,
        "_replay_selected_arm_evidence",
        replay_fake,
    )
    consumed = AUTH.consume_arm(
        fixture["campaign"],
        slot=first,
    )
    assert consumed["consumption"]["outcome"] == "CREDIBLE_TERMINAL"
    assert consumed["consumption"]["failure_code"] == ""
    assert consumed["consumption"]["arm_gate_identity"] is not None
    _pre_run_candidate(fixture, slot=second)
    result = AUTH.create_arm_selection(
        fixture["campaign"],
        slot=second,
        selection_nonce="fixture-second",
    )
    assert result["launch_ordinal"] == 2


def test_incomplete_consumption_writes_immediate_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    manifest, _ = _prepare_manifest_and_suite(fixture)
    first, second = manifest["arm_sequence"][:2]
    _pre_run_candidate(fixture, slot=first)
    monkeypatch.setattr(
        AUTH,
        "_observe_repository_head",
        lambda _context: fixture["root"]["repository_head"],
    )
    AUTH.create_arm_selection(
        fixture["campaign"],
        slot=first,
        selection_nonce="fixture-first",
    )
    monkeypatch.setattr(
        AUTH,
        "_replay_selected_arm_evidence",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("fixture terminal replay failure")),
    )
    result = AUTH.consume_arm(
        fixture["campaign"],
        slot=first,
    )
    assert result["immediate_stop_identity"] is not None
    assert result["consumption"]["outcome"] == "CREDIBILITY_INCOMPLETE"
    assert result["consumption"]["failure_code"] == "POST_SELECTION_EVIDENCE_REPLAY_FAILED"
    _pre_run_candidate(fixture, slot=second)
    with pytest.raises(AUTH.AuthorityError, match="CAMPAIGN_IMMEDIATE_STOPPED"):
        AUTH.create_arm_selection(
            fixture["campaign"],
            slot=second,
            selection_nonce="fixture-second",
        )


def test_consumption_accepts_no_caller_outcome_or_evidence() -> None:
    assert set(inspect.signature(AUTH.consume_arm).parameters) == {
        "campaign_dir",
        "slot",
    }
    with pytest.raises(SystemExit):
        AUTH._parser().parse_args(  # noqa: SLF001
            [
                "consume-arm",
                "--campaign-dir",
                "/fixture",
                "--slot",
                "region-capacity-ab-control",
                "--outcome",
                "CREDIBLE_TERMINAL",
            ]
        )


def test_prior_consumption_requires_package_gate_semantic_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path)
    manifest, _ = _prepare_manifest_and_suite(fixture)
    first, second = manifest["arm_sequence"][:2]
    _pre_run_candidate(fixture, slot=first)
    monkeypatch.setattr(
        AUTH,
        "_observe_repository_head",
        lambda _context: fixture["root"]["repository_head"],
    )
    AUTH.create_arm_selection(
        fixture["campaign"],
        slot=first,
        selection_nonce="fixture-first",
    )
    prereg = _path_preregistration(fixture["campaign"])

    def replay_fake(
        _context: dict[str, Any],
        **kwargs: Any,
    ) -> tuple[dict[str, object], None]:
        return _publish_fake_arm_gate_inputs(
            fixture,
            preregistration=prereg,
            slot=kwargs["slot"],
            pre_run=kwargs["pre_run"],
        )

    monkeypatch.setattr(
        AUTH,
        "_replay_selected_arm_evidence",
        replay_fake,
    )
    AUTH.consume_arm(fixture["campaign"], slot=first)
    _pre_run_candidate(fixture, slot=second)
    monkeypatch.setattr(
        AUTH,
        "_replay_selected_arm_evidence",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AUTH.AuthorityError("ARM_GATE_REPLAY_FAILED", first)),
    )
    with pytest.raises(AUTH.AuthorityError, match="ARM_GATE_REPLAY_FAILED"):
        AUTH.create_arm_selection(
            fixture["campaign"],
            slot=second,
            selection_nonce="fixture-second",
        )


def test_symlink_continuation_is_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    _baseline(fixture)
    continuation = fixture["continuation"]
    target = continuation.with_name("continuation-target.json")
    continuation.rename(target)
    os.symlink(target, continuation)
    with pytest.raises(AUTH.AuthorityError, match="INPUT_OPEN_FAILED|SYMLINK_REJECTED"):
        AUTH.build_manifest(fixture["campaign"])
