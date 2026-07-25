from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724"
HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
NOW = "2026-07-24T00:00:00Z"
BOOT = "11111111-2222-3333-4444-555555555555"


def _load(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, RESEARCH / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


AUTH = _load("cuts_gate1_v4_integration_authority", "campaign_authority_v4.py")
GATE = _load("cuts_gate1_v4_integration_gate", "positive_control_gate_v4.py")


def _load_orchestrator() -> ModuleType:
    aliases = (
        "campaign_authority_v4",
        "gate1_campaign_driver_v4",
        "resource_lifecycle_v4",
        "resource_verifier_v4",
    )
    prior = {name: sys.modules.get(name) for name in aliases}
    try:
        sys.modules["campaign_authority_v4"] = AUTH
        lifecycle = _load(
            "cuts_gate1_v4_integration_lifecycle",
            "resource_lifecycle_v4.py",
        )
        sys.modules["resource_lifecycle_v4"] = lifecycle
        verifier = _load(
            "cuts_gate1_v4_integration_resource_verifier",
            "resource_verifier_v4.py",
        )
        sys.modules["resource_verifier_v4"] = verifier
        driver = _load(
            "cuts_gate1_v4_integration_driver",
            "gate1_campaign_driver_v4.py",
        )
        sys.modules["gate1_campaign_driver_v4"] = driver
        return _load(
            "cuts_gate1_v4_integration_orchestrator",
            "gate1_unit_orchestrator_v4.py",
        )
    finally:
        for name, member in prior.items():
            if member is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = member


ORCHESTRATOR = _load_orchestrator()


def _write(path: Path, raw: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def _detached(path: Path) -> dict[str, object]:
    return AUTH.detached_identity(AUTH.snapshot_regular(path))


def _full(path: Path) -> dict[str, object]:
    return AUTH.full_identity(AUTH.snapshot_regular(path))


def _bound(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {"raw": raw, "identity": _detached(path)}


def _json(path: Path, value: object, *, newline: bool = True) -> dict[str, object]:
    raw = GATE.canonical_json(value) + (b"\n" if newline else b"")
    _write(path, raw)
    return {"raw": raw, "identity": _detached(path)}


def _epoch(tmp_path: Path) -> dict[str, object]:
    manager = _write(tmp_path / "epoch/systemd", b"systemd manager bytes\n")
    busctl = _write(tmp_path / "epoch/busctl", b"fixture busctl\n")
    sudo = _write(tmp_path / "epoch/sudo", b"fixture sudo\n")
    python = _write(tmp_path / "epoch/python3", b"fixture python\n")
    attestor = RESEARCH / "manager_attestor_v4.py"
    return {
        "attestation_toolchain": {
            "attestor": _full(attestor),
            "python": _full(python),
            "sudo": _full(sudo),
        },
        "attestor_ast_audit": AUTH.audit_attestor_source(attestor.read_bytes()),
        "boot_id": BOOT,
        "capture_protocol": ("double-unprivileged-join-plus-read-only-sudo-attestation-v4"),
        "dbus_unique_owner": ":1.77",
        "manager_executable": _full(manager),
        "manager_features": "+PAM +AUDIT",
        "manager_pid": 2118,
        "manager_pid_starttime": 987654,
        "manager_version": "systemd 261.1",
        "observation_toolchain": {"busctl": _full(busctl)},
        "schema": AUTH.MANAGER_EPOCH_SCHEMA,
    }


def _capture_transcript(
    epoch: dict[str, object],
    *,
    clock_base_ns: int,
) -> dict[str, object]:
    state = {
        "boot_id": epoch["boot_id"],
        "dbus_unique_owner": epoch["dbus_unique_owner"],
        "manager_features": epoch["manager_features"],
        "manager_pid": epoch["manager_pid"],
        "manager_pid_starttime": epoch["manager_pid_starttime"],
        "manager_version": epoch["manager_version"],
    }
    attestation = {
        "manager_executable": epoch["manager_executable"],
        "request": {
            "boot_id": epoch["boot_id"],
            "dbus_unique_owner": epoch["dbus_unique_owner"],
            "manager_pid": epoch["manager_pid"],
            "manager_pid_starttime": epoch["manager_pid_starttime"],
        },
        "schema": AUTH.ATTESTOR_SCHEMA,
        "status": "PASS",
    }
    tools = epoch["attestation_toolchain"]
    invocation = {
        "argv": [
            tools["sudo"]["path"],
            "-n",
            "--",
            tools["python"]["path"],
            "-I",
            "-c",
            AUTH._LOADER,  # noqa: SLF001
            "--pid",
            str(epoch["manager_pid"]),
            "--expected-starttime",
            str(epoch["manager_pid_starttime"]),
            "--expected-boot-id",
            epoch["boot_id"],
            "--dbus-owner",
            epoch["dbus_unique_owner"],
        ],
        "exit_code": 0,
        "stdin_sha256": tools["attestor"]["sha256"],
        "stdin_size_bytes": tools["attestor"]["size_bytes"],
        "stdout_base64": base64.b64encode(AUTH.canonical_json(attestation)).decode("ascii"),
    }
    return {
        "capture_protocol": "two-round-before-read-only-attestor-after-transcript-v4",
        "rounds": [
            {
                "attestation_toolchain": copy.deepcopy(epoch["attestation_toolchain"]),
                "attestor_ast_audit": copy.deepcopy(epoch["attestor_ast_audit"]),
                "attestor_invocation": copy.deepcopy(invocation),
                "observation_toolchain": copy.deepcopy(epoch["observation_toolchain"]),
                "observation_finished_monotonic_ns": clock_base_ns + index * 20,
                "observation_started_monotonic_ns": clock_base_ns + index * 20 - 10,
                "privileged_attestation": copy.deepcopy(attestation),
                "round_index": index,
                "unprivileged_after": copy.deepcopy(state),
                "unprivileged_before": copy.deepcopy(state),
            }
            for index in (1, 2)
        ],
        "schema": AUTH.MANAGER_EPOCH_TRANSCRIPT_SCHEMA,
    }


def _fixture(
    tmp_path: Path,
    *,
    campaign_name: str = "run-integration-fixture",
) -> dict[str, Any]:
    campaign = tmp_path / campaign_name
    (campaign / "campaign-authority").mkdir(parents=True)
    mandatory = _write(tmp_path / "inputs/mandatory.json", b'{"instances":[]}\n')
    candidates = _write(
        tmp_path / "inputs/candidates.json",
        b'{"facility_pools":{}}\n',
    )
    fake_resource = _write(
        tmp_path / "tools/resource_verifier_v4.py",
        (
            b"import json\n"
            b"def verify_preterminal_bytes(**kwargs):\n"
            b"    return {'status': 'fixture'}\n"
            b"def build_release_token(*args, **kwargs):\n"
            b"    return {'status': 'fixture'}\n"
            b"def verify_detached_bytes(**kwargs):\n"
            b"    return json.loads(kwargs['resource_raw'].decode('utf-8'))\n"
        ),
    )
    fake_checker = _write(
        tmp_path / "tools/independent_arithmetic_v4.py",
        (b"def verify_formal_bundle(bundle):\n    return bundle['expected_receipt']\n"),
    )
    epoch = _epoch(tmp_path)
    tools: dict[str, object] = {}
    for role in AUTH.REQUIRED_GATE1_TOOL_ROLES:
        path = RESEARCH / f"{role}.py"
        if not path.is_file():
            path = _write(
                tmp_path / f"selected-tools/{role}",
                f"fixture tool role: {role}\n".encode(),
            )
        tools[role] = _detached(path)
    tools["attestor_python"] = _detached(Path(epoch["attestation_toolchain"]["python"]["path"]))
    tools["busctl"] = _detached(Path(epoch["observation_toolchain"]["busctl"]["path"]))
    tools["manager_attestor_v4"] = _detached(Path(epoch["attestation_toolchain"]["attestor"]["path"]))
    tools["python3_13"] = _detached(Path(epoch["attestation_toolchain"]["python"]["path"]))
    tools["sudo"] = _detached(Path(epoch["attestation_toolchain"]["sudo"]["path"]))
    tools["resource_verifier_v4"] = _detached(fake_resource)
    tools["independent_arithmetic_v4"] = _detached(fake_checker)
    tools["positive_control_gate_v4"] = _detached(RESEARCH / "positive_control_gate_v4.py")
    inputs = {
        "candidate_placements": _detached(candidates),
        "mandatory_instances": _detached(mandatory),
    }
    for role in AUTH.REQUIRED_GATE1_INPUT_ROLES:
        if role not in inputs:
            path = (
                _write(
                    tmp_path / "repo/PROJECT_LOCK.md",
                    b"# fixture project lock\n",
                )
                if role == "project_lock"
                else _write(
                    tmp_path / f"inputs/{role}",
                    f"fixture input role: {role}\n".encode(),
                )
            )
            inputs[role] = _detached(path)
    package = AUTH.build_package(
        campaign / "campaign-authority/package",
        [
            AUTH.SourceSpec("candidates.json", candidates, parse_json=True),
            AUTH.SourceSpec("fake-checker.py", fake_checker),
            AUTH.SourceSpec("fake-resource.py", fake_resource),
            AUTH.SourceSpec("mandatory.json", mandatory, parse_json=True),
        ],
        repository_head=HEAD,
        run_nonce="gate1-v4-integration-fixture",
        manager_epoch=epoch,
    )
    root = AUTH.build_campaign_root(
        campaign,
        package=package,
        repository_head=HEAD,
        run_nonce="gate1-v4-integration-fixture",
        manager_epoch=epoch,
        authority_tools=tools,
        strict_inputs=inputs,
        created_at_utc=NOW,
    )
    root_identity = AUTH.write_campaign_root(campaign, root)
    root_path = campaign / "campaign-root.json"
    selection = AUTH.make_gate1_selection(
        root,
        campaign_root_identity=root_identity,
        tools=tools,
        inputs=inputs,
        created_at_utc=NOW,
    )
    selection_identity = AUTH.write_gate1_selection(
        root_path,
        root_identity,
        selection,
    )
    selection_raw = Path(selection_identity["path"]).read_bytes()
    positive_topology = root["stage_topology"]["gate1_v4"]["positive_control"]
    positive_dir = Path(positive_topology["root_dir"])
    positive_manager_epoch_digest = hashlib.sha256(GATE.canonical_json(epoch) + b"\n").hexdigest()
    pair_selection = {
        "schema": "noncert-cuts-gate1-v4-formal-positive-selection-v1",
        "purpose": "gate1_v4_formal_campaign_positive_control",
        "campaign_id": root["campaign_id"],
        "run_nonce": root["run_nonce"],
        "manager_epoch_digest": positive_manager_epoch_digest,
        "gate1_formal_eligible": True,
    }
    pair_member = _json(positive_dir / "selection.json", pair_selection)
    common_artifacts = {
        role: _bound(_write(Path(path), f"{role}\\n".encode()))
        for role, path in positive_topology["common_artifact_paths"].items()
    }
    common_value = {
        "phase": "pre_injection",
        "campaign_id": root["campaign_id"],
        "run_nonce": root["run_nonce"],
        "manager_epoch_digest": positive_manager_epoch_digest,
        "selection_identity": pair_member["identity"],
        "artifacts": {role: member["identity"] for role, member in common_artifacts.items()},
    }
    common_value["common_prestate_id"] = hashlib.sha256(
        GATE.canonical_json(
            {
                "campaign_id": common_value["campaign_id"],
                "run_nonce": common_value["run_nonce"],
                "manager_epoch_digest": common_value["manager_epoch_digest"],
                "selection_identity": pair_member["identity"],
                "artifacts": common_value["artifacts"],
                "phase": "pre_injection",
            }
        )
    ).hexdigest()
    common_prestate_id = common_value["common_prestate_id"]
    common_member = _json(
        positive_dir / "common-prestate/manifest.json",
        common_value,
    )

    checkpoints: dict[str, object] = {}
    launch_evidence: dict[str, object] = {}
    resource_replays: dict[str, object] = {}
    terminal_classes = {
        "q-success": "success",
        "q-postseal-fail": "postseal-failure",
        "forced-control": "success",
        "forced-treatment": "success",
    }
    returncodes = {
        "q-success": 0,
        "q-postseal-fail": 7,
        "forced-control": 0,
        "forced-treatment": 0,
    }
    epoch_digest = hashlib.sha256(GATE.canonical_json(epoch) + b"\n").hexdigest()
    selected_capture_tools = {
        role: selection["tools"][role]
        for role in (
            "attestor_python",
            "busctl",
            "campaign_authority_v4",
            "gate1_campaign_driver_v4",
            "manager_attestor_v4",
            "sudo",
        )
    }
    for slot_index, slot in enumerate(GATE.GATE_SLOTS):
        attempt = Path(selection["units"][slot]["attempt_dir"])
        attempt.mkdir(parents=True)
        checkpoints[slot] = {}
        base_ns = (slot_index + 1) * 1_000_000
        checkpoint_ns = {
            "prelaunch": base_ns + 1_000,
            "preterminal": base_ns + 3_000,
            "terminal": base_ns + 6_000,
            "cleanup": base_ns + 8_000,
            "detached-replay": base_ns + 10_000,
        }
        for phase in GATE.CHECKPOINT_PHASES:
            capture_transcript = _capture_transcript(
                epoch,
                clock_base_ns=checkpoint_ns[phase] - 900,
            )
            checkpoint = {
                "schema_version": GATE.CHECKPOINT_SCHEMA,
                "captured_at_utc": NOW,
                "captured_monotonic_ns": checkpoint_ns[phase],
                "campaign_id": root["campaign_id"],
                "run_nonce": root["run_nonce"],
                "selection_id": selection["selection_id"],
                "unit_slot": slot,
                "unit_name": selection["units"][slot]["unit_name"],
                "phase": phase,
                "manager_epoch": epoch,
                "manager_epoch_digest": epoch_digest,
                "selected_tool_identities": selected_capture_tools,
                "capture_transcript": capture_transcript,
                "transcript_binding_sha256": hashlib.sha256(
                    AUTH.canonical_json(
                        {
                            "campaign_id": root["campaign_id"],
                            "capture_transcript": capture_transcript,
                            "phase": phase,
                            "run_nonce": root["run_nonce"],
                            "selected_tool_identities": selected_capture_tools,
                            "selection_id": selection["selection_id"],
                            "unit_slot": slot,
                        }
                    )
                ).hexdigest(),
            }
            checkpoints[slot][phase] = _json(
                Path(selection["units"][slot]["epoch_checkpoint_paths"][phase]),
                checkpoint,
            )
        launch_argv = ORCHESTRATOR.build_systemd_run_argv(
            root_identity=root_identity,
            selection_identity=selection_identity,
            selection=selection,
            unit_slot=slot,
        )
        launch_value = {
            "schema_version": ORCHESTRATOR.LAUNCH_SCHEMA,
            "created_at_utc": NOW,
            "campaign_root_identity": root_identity,
            "selection_identity": selection_identity,
            "campaign_id": root["campaign_id"],
            "run_nonce": root["run_nonce"],
            "selection_id": selection["selection_id"],
            "manager_epoch_digest": epoch_digest,
            "unit_slot": slot,
            "unit_name": selection["units"][slot]["unit_name"],
            "argv": list(launch_argv),
            "argv_sha256": hashlib.sha256(AUTH.canonical_json(list(launch_argv))).hexdigest(),
            "selected_loader_sha256": hashlib.sha256(
                ORCHESTRATOR.SELECTED_BYTE_ENTRYPOINT_LOADER.encode("utf-8")
            ).hexdigest(),
            "orchestrator_identity": selection["tools"]["gate1_unit_orchestrator_v4"],
            "exit_code": 0,
            "stdout_b64": base64.b64encode(b"fixture launch\n").decode("ascii"),
            "stderr_b64": "",
            "started_monotonic_ns": base_ns + 1_500,
            "finished_monotonic_ns": base_ns + 1_600,
            "systemd_run_identity": selection["tools"]["systemd_run"],
        }
        launch_evidence[slot] = _json(
            Path(selection["units"][slot]["raw_dir"]) / "systemd-run-launch.json",
            launch_value,
        )
        detached = {
            "schema_version": GATE.DETACHED_RESOURCE_SCHEMA,
            "status": "PASS",
            "verdict": "LIFECYCLE_DETACHED_PASS",
            "terminal_class": terminal_classes[slot],
            "created_at_utc": NOW,
            "selection_identity": selection_identity,
            "campaign_id": root["campaign_id"],
            "run_nonce": root["run_nonce"],
            "selection_id": selection["selection_id"],
            "manager_epoch_digest": epoch_digest,
            "unit_slot": slot,
            "unit_name": selection["units"][slot]["unit_name"],
            "inputs": {},
            "verifier_identity": tools["resource_verifier_v4"],
            "derived": {
                "payload_returncode": returncodes[slot],
                "payload_timed_out": False,
                "keeper_only": True,
                "payload_status_preserved": True,
                "unit_absent": True,
                "cgroup_absent": True,
                "remaining_pids": [],
                "systemd_exec_start_monotonic_usec": (base_ns + 2_000) // 1_000,
                "preterminal_monotonic_ns": base_ns + 4_000,
                "released_monotonic_ns": base_ns + 5_000,
                "terminal_monotonic_ns": base_ns + 7_000,
                "cleanup_monotonic_ns": base_ns + 9_000,
            },
            "mechanism_credible_authorized": False,
            "organic_arm_launch_authorized": False,
            "global_claim_authorized": False,
        }
        if slot == "forced-treatment":
            detached["payload_pid"] = 4242
        detached_member = _json(attempt / "detached-replay.json", detached)
        delegated_identity = selection["tools"]["positive_control_formal_v4"] if slot.startswith("forced-") else None
        if slot.startswith("forced-"):
            arm = "control" if slot == "forced-control" else "treatment"
            count = 0 if arm == "control" else 1
            delegated_result: object = {
                "status": "PASS",
                "arm": arm,
                "profile": "formal_campaign",
                "common_prestate_id": common_prestate_id,
                "generated": count,
                "compiled": count,
                "applied": count,
                "support_tool_identity": selection["tools"]["positive_control_v4"],
                "post_solve_performed": False,
                "organic_arm_launch_authorized": False,
                "global_claim_authorized": False,
            }
        else:
            delegated_result = None
        payload_result = {
            "schema_version": GATE.PAYLOAD_RESULT_SCHEMA,
            "created_at_utc": NOW,
            "campaign_root_identity": root_identity,
            "selection_identity": selection_identity,
            "campaign_id": root["campaign_id"],
            "run_nonce": root["run_nonce"],
            "selection_id": selection["selection_id"],
            "unit_slot": slot,
            "unit_name": selection["units"][slot]["unit_name"],
            "payload_kind": ("forced-positive-control" if slot.startswith("forced-") else "synthetic-lifecycle"),
            "expected_returncode": returncodes[slot],
            "delegated_tool_role": ("positive_control_formal_v4" if slot.startswith("forced-") else None),
            "delegated_tool_identity": delegated_identity,
            "delegated_result": delegated_result,
            "sealed_before_exit": True,
            "mechanism_credible_authorized": False,
            "organic_arm_launch_authorized": False,
            "global_claim_authorized": False,
        }
        payload_result_member = _json(
            Path(selection["units"][slot]["result_path"]),
            payload_result,
        )
        payload_seal = {
            "schema_version": GATE.PAYLOAD_SEAL_SCHEMA,
            "created_at_utc": NOW,
            "campaign_id": root["campaign_id"],
            "run_nonce": root["run_nonce"],
            "selection_id": selection["selection_id"],
            "unit_slot": slot,
            "unit_name": selection["units"][slot]["unit_name"],
            "result_identity": payload_result_member["identity"],
            "expected_returncode": returncodes[slot],
            "delegated_tool_identity": delegated_identity,
            "payload_complete": True,
        }
        payload_seal_member = _json(
            Path(selection["units"][slot]["raw_dir"]) / "payload-seal.json",
            payload_seal,
        )
        inner_member = _json(
            Path(selection["units"][slot]["raw_dir"]) / "inner-lifecycle.json",
            {
                "payload_pid": (4242 if slot == "forced-treatment" else 4200 + slot_index),
                "payload_result_identity": payload_result_member["identity"],
                "payload_seal_identity": payload_seal_member["identity"],
            },
        )
        evidence: dict[str, object] = {
            "inner": inner_member,
            "payload_result": payload_result_member,
            "payload_seal": payload_seal_member,
        }
        for name in ("preterminal", "release", "terminal", "cleanup"):
            raw = f"{slot}:{name}".encode()
            evidence[name] = {
                "raw": raw,
                "identity": {
                    "path": str((attempt / f"raw/{name}.bin").absolute()),
                    "size_bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                },
            }
        evidence["resource"] = {
            "raw": detached_member["raw"],
            "identity": {
                **detached_member["identity"],
                "path": str((attempt / "raw/resource.bin").absolute()),
            },
        }
        resource_replays[slot] = {
            "detached_raw": detached_member["raw"],
            "detached_identity": detached_member["identity"],
            "evidence": evidence,
        }

    gate_admission_ns = 5_000_000
    gate_admission_transcript = _capture_transcript(
        epoch,
        clock_base_ns=gate_admission_ns - 900,
    )
    gate_admission_value = {
        "schema_version": GATE.CHECKPOINT_SCHEMA,
        "captured_at_utc": NOW,
        "captured_monotonic_ns": gate_admission_ns,
        "campaign_id": root["campaign_id"],
        "run_nonce": root["run_nonce"],
        "selection_id": selection["selection_id"],
        "unit_slot": "gate-admission",
        "unit_name": f"{root['unit_namespace']}-gate-admission.authority",
        "phase": "gate-admission",
        "manager_epoch": epoch,
        "manager_epoch_digest": epoch_digest,
        "selected_tool_identities": selected_capture_tools,
        "capture_transcript": gate_admission_transcript,
        "transcript_binding_sha256": hashlib.sha256(
            AUTH.canonical_json(
                {
                    "campaign_id": root["campaign_id"],
                    "capture_transcript": gate_admission_transcript,
                    "phase": "gate-admission",
                    "run_nonce": root["run_nonce"],
                    "selected_tool_identities": selected_capture_tools,
                    "selection_id": selection["selection_id"],
                    "unit_slot": "gate-admission",
                }
            )
        ).hexdigest(),
    }
    gate_admission = _json(
        Path(root["stage_topology"]["gate1_v4"]["gate_admission_epoch_path"]),
        gate_admission_value,
    )

    binding_values = {
        arm: {
            "arm": arm,
            "common_prestate_id": common_prestate_id,
        }
        for arm in positive_topology["binding_paths"]
    }
    binding_members = {
        arm: _json(Path(path), binding_values[arm]) for arm, path in positive_topology["binding_paths"].items()
    }
    binding_seal_value = {"status": "SEALED"}
    binding_member = _json(
        positive_dir / "bindings/bindings-seal.json",
        binding_seal_value,
    )
    arm_members: dict[str, object] = {}
    arm_filenames = {
        "post_model": "post-injection-model.pb",
        "assignment": "assignment.json",
        "samples": "arithmetic-samples.json",
        "ledger": "ledger.jsonl",
    }
    for arm, directory in positive_topology["arm_dirs"].items():
        arm_dir = Path(directory)
        evidence_value = {"arm": arm}
        evidence_member = _json(arm_dir / "evidence.json", evidence_value)
        members = {
            role: _bound(
                _write(
                    arm_dir / filename,
                    f"{arm}:{role}\n".encode(),
                )
            )
            for role, filename in arm_filenames.items()
        }
        arm_members[arm] = {
            "evidence": evidence_value,
            "evidence_identity": evidence_member["identity"],
            "members": members,
        }
    arithmetic = {
        "schema": GATE.ARITHMETIC_SCHEMA,
        "checker": "independent_arithmetic_v4.verify_formal_bundle",
        "status": "PASS_FORMAL_MECHANISM_POSITIVE_CONTROL",
        "repository_head": HEAD,
        "selection_identity": pair_member["identity"],
        "common_prestate_id": common_prestate_id,
        "common_prestate": {
            "pre_model_sha256": "1" * 64,
            "response_sha256": "2" * 64,
            "solution_sha256": "3" * 64,
            "incumbent_sha256": "4" * 64,
            "post_solve_performed": False,
        },
        "control": {"generated": 0, "compiled": 0, "applied": 0},
        "treatment": {"generated": 1, "compiled": 1, "applied": 1},
        "selected": {
            "cut_id": "forced-region-capacity-a001",
            "family": "region_capacity",
            "group_id": "group-a001",
            "lhs": 2,
            "rhs": 1,
            "active": True,
            "violated": True,
            "trigger": "binding_infeasible",
            "iteration": 1001,
            "epoch_instance_id": "epoch-4242-fixture",
            "epoch_semantic_digest": "5" * 64,
        },
        "checks": [
            "formal_campaign_selection_and_eligibility",
            "common_pre_model_response_solution_incumbent_sealed",
            "both_arm_bindings_precede_post_clone_dependency",
            "production_typed_attach_chain",
            "no_post_attach_solve_or_response",
            "control_applied_zero",
            "treatment_generated_compiled_applied_one_to_one",
            "binary_assignment_model_constraint_ledger_join",
        ],
        "claim_boundary": {
            "established": ["one forced inequality excluded the incumbent"],
            "not_established": ["organic activation"],
        },
    }
    arithmetic_member = _json(
        positive_dir / "independent-arithmetic-receipt.json",
        arithmetic,
        newline=True,
    )
    bundle = {
        "selection": pair_selection,
        "selection_identity": pair_member["identity"],
        "common": common_value,
        "common_identity": common_member["identity"],
        "common_artifacts": common_artifacts,
        "binding_seal": binding_seal_value,
        "binding_seal_identity": binding_member["identity"],
        "bindings": {
            arm: {
                "value": binding_values[arm],
                "identity": member["identity"],
            }
            for arm, member in binding_members.items()
        },
        "arms": arm_members,
        "expected_receipt": arithmetic,
    }
    positive = {
        "bundle": bundle,
        "pair_selection_identity": pair_member["identity"],
        "common_prestate_identity": common_member["identity"],
        "binding_set_identity": binding_member["identity"],
        "arithmetic_raw": arithmetic_member["raw"],
        "arithmetic_identity": arithmetic_member["identity"],
    }
    return {
        "root": root,
        "root_raw": root_path.read_bytes(),
        "root_identity": root_identity,
        "selection": selection,
        "selection_raw": selection_raw,
        "selection_identity": selection_identity,
        "epoch": epoch,
        "tools": {
            "campaign_authority_v4": _bound(RESEARCH / "campaign_authority_v4.py"),
            "gate1_campaign_driver_v4": _bound(RESEARCH / "gate1_campaign_driver_v4.py"),
            "resource_lifecycle_v4": _bound(RESEARCH / "resource_lifecycle_v4.py"),
            "resource_verifier_v4": _bound(fake_resource),
            "gate1_unit_orchestrator_v4": _bound(RESEARCH / "gate1_unit_orchestrator_v4.py"),
            "independent_arithmetic_v4": _bound(fake_checker),
            "positive_control_gate_v4": _bound(RESEARCH / "positive_control_gate_v4.py"),
        },
        "checkpoints": checkpoints,
        "launches": launch_evidence,
        "resources": resource_replays,
        "positive": positive,
        "gate_admission": gate_admission,
    }


def _evaluate(fixture: dict[str, Any]) -> dict[str, object]:
    return GATE.evaluate_gate(
        campaign_root_raw=fixture["root_raw"],
        campaign_root_identity=fixture["root_identity"],
        selection_raw=fixture["selection_raw"],
        selection_identity=fixture["selection_identity"],
        gate_admission_epoch=fixture["gate_admission"],
        tool_sources=fixture["tools"],
        manager_checkpoints=fixture["checkpoints"],
        launch_evidence=fixture["launches"],
        resource_replays=fixture["resources"],
        positive_control=fixture["positive"],
        created_at_utc=NOW,
    )


def test_driver_and_gate_manager_epoch_digest_are_byte_identical(
    tmp_path: Path,
) -> None:
    epoch = _epoch(tmp_path)
    driver_digest = hashlib.sha256(AUTH.canonical_json(epoch)).hexdigest()
    assert driver_digest == GATE._epoch_digest(epoch)  # noqa: SLF001


def _reidentity(member: dict[str, object]) -> None:
    raw = member["raw"]
    assert isinstance(raw, bytes)
    identity = member["identity"]
    assert isinstance(identity, dict)
    member["identity"] = {
        **identity,
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _reseal_payload_result(
    fixture: dict[str, Any],
    slot: str,
    mutate: Any,
) -> None:
    evidence = fixture["resources"][slot]["evidence"]
    result = json.loads(evidence["payload_result"]["raw"])
    mutate(result)
    evidence["payload_result"]["raw"] = GATE.canonical_json(result) + b"\n"
    _reidentity(evidence["payload_result"])
    result_identity = evidence["payload_result"]["identity"]
    seal = json.loads(evidence["payload_seal"]["raw"])
    seal["result_identity"] = result_identity
    evidence["payload_seal"]["raw"] = GATE.canonical_json(seal) + b"\n"
    _reidentity(evidence["payload_seal"])
    inner = json.loads(evidence["inner"]["raw"])
    inner["payload_result_identity"] = result_identity
    inner["payload_seal_identity"] = evidence["payload_seal"]["identity"]
    evidence["inner"]["raw"] = GATE.canonical_json(inner) + b"\n"
    _reidentity(evidence["inner"])


def test_gate_pass_is_only_mechanism_credible_and_keeps_campaign_open(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    result = _evaluate(fixture)
    assert result["status"] == GATE.GATE_STATUS
    assert result["verdict"] == "MECHANISM_CREDIBLE"
    assert result["mechanism_credible"] is True
    assert result["continuation_eligible"] is True
    assert result["continuation_authorized"] is False
    assert result["campaign_closed"] is False
    assert result["organic_arm_launch_authorized"] is False
    assert result["global_claim_authorized"] is False
    assert result["gate_admission_epoch_identity"] == fixture["gate_admission"]["identity"]
    assert set(result["detached_replay_identities"]) == set(GATE.GATE_SLOTS)
    assert set(result["systemd_run_launch_identities"]) == set(GATE.GATE_SLOTS)
    assert set(result["payload_evidence_identities"]) == set(GATE.GATE_SLOTS)
    assert result["forced_payload_profile"] == "formal_campaign"
    assert all(
        set(phases) == set(GATE.CHECKPOINT_PHASES) for phases in result["manager_checkpoint_identities"].values()
    )
    assert result["positive_control"]["control"]["applied"] == 0
    assert result["positive_control"]["treatment"]["applied"] == 1
    assert result["positive_control"]["selected"]["lhs"] > result["positive_control"]["selected"]["rhs"]


def test_final_gate_refuses_a_generic_or_drill_arithmetic_api(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    with pytest.raises(GATE.GateError, match="formal-only verify_formal_bundle"):
        GATE._arithmetic_replay(  # noqa: SLF001
            fixture["positive"],
            root=fixture["root"],
            selection=fixture["selection"],
            checker={
                "verify_bundle": lambda bundle: bundle["expected_receipt"],
            },
        )


def test_missing_resource_or_manager_checkpoint_fails_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    fixture["resources"].pop("q-success")
    with pytest.raises(GATE.GateError, match="resource detached replay unit set"):
        _evaluate(fixture)

    fixture = _fixture(tmp_path / "second")
    fixture["checkpoints"]["forced-control"].pop("terminal")
    with pytest.raises(GATE.GateError, match="checkpoint phase set"):
        _evaluate(fixture)


def test_manager_epoch_and_checkpoint_timeline_drift_fail_closed(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    admission = json.loads(fixture["gate_admission"]["raw"])
    admission["manager_epoch"]["boot_id"] = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    fixture["gate_admission"]["raw"] = GATE.canonical_json(admission) + b"\n"
    _reidentity(fixture["gate_admission"])
    with pytest.raises(GATE.GateError, match="gate-admission"):
        _evaluate(fixture)

    fixture = _fixture(tmp_path / "second")
    phases = fixture["checkpoints"]["q-success"]
    terminal = json.loads(phases["terminal"]["raw"])
    terminal["captured_monotonic_ns"] = 1
    phases["terminal"]["raw"] = GATE.canonical_json(terminal) + b"\n"
    _reidentity(phases["terminal"])
    with pytest.raises(GATE.GateError, match="timeline"):
        _evaluate(fixture)


def test_gate_admission_epoch_is_mandatory_and_follows_all_units(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    fixture["gate_admission"] = {}
    with pytest.raises(GATE.GateError, match="field set drifted"):
        _evaluate(fixture)

    fixture = _fixture(tmp_path / "timeline")
    admission = json.loads(fixture["gate_admission"]["raw"])
    admission["captured_monotonic_ns"] = 4_000_000
    transcript = admission["capture_transcript"]
    transcript["rounds"][0]["observation_started_monotonic_ns"] = 3_999_000
    admission["transcript_binding_sha256"] = hashlib.sha256(
        AUTH.canonical_json(
            {
                "campaign_id": fixture["root"]["campaign_id"],
                "capture_transcript": transcript,
                "phase": "gate-admission",
                "run_nonce": fixture["root"]["run_nonce"],
                "selected_tool_identities": admission["selected_tool_identities"],
                "selection_id": fixture["selection"]["selection_id"],
                "unit_slot": "gate-admission",
            }
        )
    ).hexdigest()
    fixture["gate_admission"]["raw"] = GATE.canonical_json(admission) + b"\n"
    _reidentity(fixture["gate_admission"])
    with pytest.raises(GATE.GateError, match="gate-admission"):
        _evaluate(fixture)


def test_manager_checkpoint_must_use_exact_preregistered_path(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    member = fixture["checkpoints"]["q-success"]["prelaunch"]
    member["identity"] = {
        **member["identity"],
        "path": str(
            Path(fixture["selection"]["units"]["q-success"]["attempt_dir"])
            / "authority/semantically-equivalent-checkpoint.json"
        ),
    }
    with pytest.raises(GATE.GateError, match="pre.?registered"):
        _evaluate(fixture)


def test_manager_checkpoints_must_bracket_resource_lifecycle(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    member = fixture["checkpoints"]["q-success"]["terminal"]
    value = json.loads(member["raw"])
    value["captured_monotonic_ns"] = 1_007_050
    member["raw"] = GATE.canonical_json(value) + b"\n"
    _reidentity(member)
    with pytest.raises(GATE.GateError, match="bracket lifecycle phases"):
        _evaluate(fixture)


@pytest.mark.parametrize(
    "mutation",
    (
        "epoch-only",
        "attestor-argv",
        "attestor-stdout",
        "selected-tool",
        "phase",
    ),
)
def test_strict_driver_replay_rejects_checkpoint_transcript_mutations(
    tmp_path: Path,
    mutation: str,
) -> None:
    fixture = _fixture(tmp_path)
    slot = "q-success"
    expected_phase = "prelaunch"
    member = fixture["checkpoints"][slot][expected_phase]
    value = json.loads(member["raw"])
    if mutation == "epoch-only":
        value.pop("capture_transcript")
    elif mutation == "attestor-argv":
        value["capture_transcript"]["rounds"][0]["attestor_invocation"]["argv"][-1] = ":1.999"
    elif mutation == "attestor-stdout":
        value["capture_transcript"]["rounds"][0]["attestor_invocation"]["stdout_base64"] = base64.b64encode(
            b'{"schema":"forged"}\n'
        ).decode("ascii")
    elif mutation == "selected-tool":
        value["selected_tool_identities"]["gate1_campaign_driver_v4"]["sha256"] = "0" * 64
    else:
        value["phase"] = "terminal"
    if "capture_transcript" in value:
        value["transcript_binding_sha256"] = hashlib.sha256(
            AUTH.canonical_json(
                {
                    "campaign_id": fixture["root"]["campaign_id"],
                    "capture_transcript": value["capture_transcript"],
                    "phase": value["phase"],
                    "run_nonce": fixture["root"]["run_nonce"],
                    "selected_tool_identities": value["selected_tool_identities"],
                    "selection_id": fixture["selection"]["selection_id"],
                    "unit_slot": slot,
                }
            )
        ).hexdigest()
    member["raw"] = GATE.canonical_json(value) + b"\n"
    _reidentity(member)
    with pytest.raises(GATE.GateError, match="strict checkpoint replay failed"):
        _evaluate(fixture)


def test_resource_receipt_or_tool_byte_drift_fails_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    member = fixture["resources"]["q-postseal-fail"]
    receipt = json.loads(member["detached_raw"])
    receipt["terminal_class"] = "success"
    member["detached_raw"] = GATE.canonical_json(receipt) + b"\n"
    member["detached_identity"] = {
        **member["detached_identity"],
        "size_bytes": len(member["detached_raw"]),
        "sha256": hashlib.sha256(member["detached_raw"]).hexdigest(),
    }
    member["evidence"]["resource"]["raw"] = member["detached_raw"]
    member["evidence"]["resource"]["identity"] = {
        **member["evidence"]["resource"]["identity"],
        "size_bytes": len(member["detached_raw"]),
        "sha256": hashlib.sha256(member["detached_raw"]).hexdigest(),
    }
    with pytest.raises(GATE.GateError, match="resource semantics"):
        _evaluate(fixture)

    fixture = _fixture(tmp_path / "second")
    fixture["tools"]["resource_verifier_v4"]["raw"] += b"# drift\n"
    with pytest.raises(GATE.GateError, match="detached byte identity drifted"):
        _evaluate(fixture)


def test_launch_argv_and_orchestrator_byte_drift_fail_closed(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    member = fixture["launches"]["forced-control"]
    launch = json.loads(member["raw"])
    launch["argv"][-1] = "forced-treatment"
    launch["argv_sha256"] = hashlib.sha256(AUTH.canonical_json(launch["argv"])).hexdigest()
    member["raw"] = GATE.canonical_json(launch) + b"\n"
    _reidentity(member)
    with pytest.raises(GATE.GateError, match="launch argv"):
        _evaluate(fixture)

    fixture = _fixture(tmp_path / "second")
    fixture["tools"]["gate1_unit_orchestrator_v4"]["raw"] += b"# drift\n"
    with pytest.raises(GATE.GateError, match="detached byte identity drifted"):
        _evaluate(fixture)


def test_payload_result_identity_and_profile_mutations_fail_closed(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    evidence = fixture["resources"]["forced-treatment"]["evidence"]
    evidence["payload_result"]["identity"] = {
        **evidence["payload_result"]["identity"],
        "sha256": "0" * 64,
    }
    with pytest.raises(GATE.GateError, match="detached byte identity drifted"):
        _evaluate(fixture)

    fixture = _fixture(tmp_path / "second")
    _reseal_payload_result(
        fixture,
        "forced-treatment",
        lambda result: result["delegated_result"].__setitem__(
            "profile",
            "disposable_drill",
        ),
    )
    with pytest.raises(GATE.GateError, match="forced payload result semantics"):
        _evaluate(fixture)

    fixture = _fixture(tmp_path / "third")
    fixture["tools"]["gate1_campaign_driver_v4"]["raw"] += b"# drift\n"
    with pytest.raises(GATE.GateError, match="detached byte identity drifted"):
        _evaluate(fixture)


def test_formal_gate_rejects_dev_drill_campaign_with_formal_payloads(
    tmp_path: Path,
) -> None:
    fixture = _fixture(
        tmp_path,
        campaign_name="dev-drill-integration-fixture",
    )
    with pytest.raises(GATE.GateError, match=r"requires a nonempty run-\*"):
        _evaluate(fixture)


def test_delegated_extra_field_and_common_id_joint_reseal_fail_closed(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    _reseal_payload_result(
        fixture,
        "forced-control",
        lambda result: result["delegated_result"].__setitem__(
            "unexpected",
            "self-consistent-extra-field",
        ),
    )
    with pytest.raises(GATE.GateError, match="field set drifted"):
        _evaluate(fixture)

    malformed = _fixture(tmp_path / "malformed")
    malformed_common = malformed["positive"]["bundle"]["common"]
    malformed_common["common_prestate_id"] = "NOT-A-SHA256"
    malformed_path = Path(malformed["positive"]["common_prestate_identity"]["path"])
    malformed_path.write_bytes(GATE.canonical_json(malformed_common) + b"\n")
    malformed_identity = _detached(malformed_path)
    malformed["positive"]["bundle"]["common_identity"] = malformed_identity
    malformed["positive"]["common_prestate_identity"] = malformed_identity
    with pytest.raises(GATE.GateError, match="lowercase SHA-256"):
        _evaluate(malformed)

    fixture = _fixture(tmp_path / "joint")
    forged_common_id = "b" * 64
    bundle = fixture["positive"]["bundle"]
    common = bundle["common"]
    common["common_prestate_id"] = forged_common_id
    common_path = Path(fixture["positive"]["common_prestate_identity"]["path"])
    common_path.write_bytes(GATE.canonical_json(common) + b"\n")
    common_identity = _detached(common_path)
    bundle["common_identity"] = common_identity
    fixture["positive"]["common_prestate_identity"] = common_identity
    for arm in ("control", "treatment"):
        binding = bundle["bindings"][arm]
        binding["value"]["common_prestate_id"] = forged_common_id
        binding_path = Path(binding["identity"]["path"])
        binding_path.write_bytes(GATE.canonical_json(binding["value"]) + b"\n")
        binding["identity"] = _detached(binding_path)
        _reseal_payload_result(
            fixture,
            f"forced-{arm}",
            lambda result, common_id=forged_common_id: result["delegated_result"].__setitem__(
                "common_prestate_id", common_id
            ),
        )
    receipt = bundle["expected_receipt"]
    receipt["common_prestate_id"] = forged_common_id
    arithmetic_raw = GATE.canonical_json(receipt) + b"\n"
    fixture["positive"]["arithmetic_raw"] = arithmetic_raw
    fixture["positive"]["arithmetic_identity"] = {
        **fixture["positive"]["arithmetic_identity"],
        "size_bytes": len(arithmetic_raw),
        "sha256": hashlib.sha256(arithmetic_raw).hexdigest(),
    }
    with pytest.raises(GATE.GateError, match="derivation drifted"):
        _evaluate(fixture)


@pytest.mark.parametrize(
    ("path", "value", "match"),
    [
        (("control", "applied"), 1, "PASS semantics"),
        (("treatment", "generated"), 0, "PASS semantics"),
        (("selected", "lhs"), 1, "not active and violated"),
    ],
)
def test_arithmetic_count_and_violation_mutations_fail_closed(
    tmp_path: Path,
    path: tuple[str, str],
    value: int,
    match: str,
) -> None:
    fixture = _fixture(tmp_path)
    receipt = copy.deepcopy(fixture["positive"]["bundle"]["expected_receipt"])
    receipt[path[0]][path[1]] = value
    fixture["positive"]["bundle"]["expected_receipt"] = receipt
    raw = GATE.canonical_json(receipt) + b"\n"
    fixture["positive"]["arithmetic_raw"] = raw
    fixture["positive"]["arithmetic_identity"] = {
        **fixture["positive"]["arithmetic_identity"],
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    with pytest.raises(GATE.GateError, match=match):
        _evaluate(fixture)


def test_formal_campaign_join_and_identity_mutations_fail_closed(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    fixture["positive"]["bundle"]["selection"]["gate1_formal_eligible"] = False
    with pytest.raises(GATE.GateError, match="not formally joined"):
        _evaluate(fixture)

    fixture = _fixture(tmp_path / "second")
    fixture["positive"]["common_prestate_identity"] = {
        **fixture["positive"]["common_prestate_identity"],
        "sha256": "0" * 64,
    }
    with pytest.raises(GATE.GateError, match="identity join"):
        _evaluate(fixture)


def test_prospective_child_precreation_fails_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    future = Path(fixture["root"]["stage_topology"]["prospective_ab16"]["manifest_path"])
    future.parent.mkdir()
    future.write_bytes(b"{}\n")
    with pytest.raises(GATE.GateError, match="prospective AB16 child"):
        _evaluate(fixture)


def test_no_overwrite_and_symlink_output_are_rejected(tmp_path: Path) -> None:
    output = tmp_path / "gate.json"
    identity = GATE.write_exclusive(output, {"status": "PASS"})
    assert output.read_bytes() == GATE.canonical_json({"status": "PASS"}) + b"\n"
    assert identity["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    with pytest.raises(GATE.GateError, match="overwrite"):
        GATE.write_exclusive(output, {"status": "PASS"})

    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    os.symlink(real, link)
    with pytest.raises(GATE.GateError, match="symlink"):
        GATE.write_exclusive(link / "gate.json", {"status": "PASS"})
