from __future__ import annotations

import base64
import copy
import importlib.util
import inspect
import json
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs" / "research" / "noncert_cuts_ab_trust_gate1_v4_20260724"
HEAD = "3" * 40
NOW = "2026-07-24T00:00:00+00:00"
BOOT = "11111111-2222-3333-4444-555555555555"


def _load(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, RESEARCH / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


AUTH = _load("noncert_cuts_campaign_authority_v4", "campaign_authority_v4.py")
ATTESTOR = _load("noncert_cuts_manager_attestor_v4", "manager_attestor_v4.py")
sys.modules["campaign_authority_v4"] = AUTH
DRIVER = _load("noncert_cuts_gate1_campaign_driver_v4", "gate1_campaign_driver_v4.py")
LIFECYCLE = _load("noncert_cuts_resource_lifecycle_v4", "resource_lifecycle_v4.py")
RESOURCE_VERIFIER = _load("noncert_cuts_resource_verifier_v4", "resource_verifier_v4.py")


def _write(path: Path, raw: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def _full(path: Path) -> dict[str, object]:
    return AUTH.full_identity(AUTH.snapshot_regular(path))


def _detached(path: Path) -> dict[str, object]:
    return AUTH.detached_identity(AUTH.snapshot_regular(path))


def _epoch(tmp_path: Path) -> dict[str, object]:
    manager = _write(tmp_path / "tools/systemd", b"systemd manager bytes\n")
    busctl = _write(tmp_path / "tools/busctl", b"fixture busctl\n")
    sudo = _write(tmp_path / "tools/sudo", b"fixture sudo\n")
    python = _write(tmp_path / "tools/python3.14", b"fixture python\n")
    attestor = RESEARCH / "manager_attestor_v4.py"
    audit = AUTH.audit_attestor_source(attestor.read_bytes())
    return {
        "attestation_toolchain": {
            "attestor": _full(attestor),
            "python": _full(python),
            "sudo": _full(sudo),
        },
        "attestor_ast_audit": audit,
        "boot_id": BOOT,
        "capture_protocol": "double-unprivileged-join-plus-read-only-sudo-attestation-v4",
        "dbus_unique_owner": ":1.77",
        "manager_executable": _full(manager),
        "manager_features": "+PAM +AUDIT",
        "manager_pid": 2118,
        "manager_pid_starttime": 987654,
        "manager_version": "systemd 261.1",
        "observation_toolchain": {"busctl": _full(busctl)},
        "schema": AUTH.MANAGER_EPOCH_SCHEMA,
    }


def _capture_result(
    epoch: dict[str, object],
    *,
    clock_base_ns: int = 0,
) -> dict[str, object]:
    before = {
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
    rounds = []
    for index in (1, 2):
        rounds.append(
            {
                "attestation_toolchain": copy.deepcopy(epoch["attestation_toolchain"]),
                "attestor_ast_audit": copy.deepcopy(epoch["attestor_ast_audit"]),
                "attestor_invocation": copy.deepcopy(invocation),
                "observation_toolchain": copy.deepcopy(epoch["observation_toolchain"]),
                "observation_finished_monotonic_ns": clock_base_ns + index * 20,
                "observation_started_monotonic_ns": clock_base_ns + index * 20 - 10,
                "privileged_attestation": copy.deepcopy(attestation),
                "round_index": index,
                "unprivileged_after": copy.deepcopy(before),
                "unprivileged_before": copy.deepcopy(before),
            }
        )
    return {
        "manager_epoch": copy.deepcopy(epoch),
        "transcript": {
            "capture_protocol": "two-round-before-read-only-attestor-after-transcript-v4",
            "rounds": rounds,
            "schema": AUTH.MANAGER_EPOCH_TRANSCRIPT_SCHEMA,
        },
    }


def _authority(tmp_path: Path) -> dict[str, Any]:
    campaign = tmp_path / "campaign"
    (campaign / "campaign-authority").mkdir(parents=True)
    mandatory = _write(tmp_path / "inputs/mandatory.json", b'{"instances":[]}\n')
    candidates = _write(tmp_path / "inputs/candidates.json", b'{"facility_pools":{}}\n')
    driver = _write(tmp_path / "tools/driver.py", b"# fixture driver\n")
    observer = _write(tmp_path / "tools/observer.py", b"# fixture observer\n")
    epoch = _epoch(tmp_path)
    package = AUTH.build_package(
        campaign / "campaign-authority/package",
        [
            AUTH.SourceSpec("candidates.json", candidates, parse_json=True),
            AUTH.SourceSpec("driver.py", driver),
            AUTH.SourceSpec("mandatory.json", mandatory, parse_json=True),
            AUTH.SourceSpec("observer.py", observer),
        ],
        repository_head=HEAD,
        run_nonce="cuts-gate1-v4-fixture",
        manager_epoch=epoch,
    )
    tools: dict[str, dict[str, object]] = {}
    for role in AUTH.REQUIRED_GATE1_TOOL_ROLES:
        implementation = RESEARCH / f"{role}.py"
        if not implementation.exists():
            implementation = _write(
                tmp_path / f"selected-tools/{role}",
                f"fixture tool role {role}\n".encode(),
            )
        tools[role] = _detached(implementation)
    tools["attestor_python"] = _detached(Path(epoch["attestation_toolchain"]["python"]["path"]))
    tools["busctl"] = _detached(Path(epoch["observation_toolchain"]["busctl"]["path"]))
    tools["manager_attestor_v4"] = _detached(Path(epoch["attestation_toolchain"]["attestor"]["path"]))
    tools["python3_13"] = _detached(Path(epoch["attestation_toolchain"]["python"]["path"]))
    tools["sudo"] = _detached(Path(epoch["attestation_toolchain"]["sudo"]["path"]))
    tools.update({"driver": _detached(driver), "observer": _detached(observer)})
    inputs: dict[str, dict[str, object]] = {}
    for role in AUTH.REQUIRED_GATE1_INPUT_ROLES:
        if role == "candidate_placements":
            source = candidates
        elif role == "mandatory_instances":
            source = mandatory
        else:
            source = _write(
                tmp_path / f"inputs/{role}",
                f"fixture input role {role}\n".encode(),
            )
        inputs[role] = _detached(source)
    root = AUTH.build_campaign_root(
        campaign,
        package=package,
        repository_head=HEAD,
        run_nonce="cuts-gate1-v4-fixture",
        manager_epoch=epoch,
        authority_tools=tools,
        strict_inputs=inputs,
        created_at_utc=NOW,
    )
    root_identity = AUTH.write_campaign_root(campaign, root)
    return {
        "campaign": campaign,
        "epoch": epoch,
        "inputs": inputs,
        "package": package,
        "root": root,
        "root_identity": root_identity,
        "root_path": campaign / "campaign-root.json",
        "tools": tools,
    }


def _selection(authority: dict[str, Any]) -> tuple[dict[str, object], dict[str, object]]:
    selection = AUTH.make_gate1_selection(
        authority["root"],
        campaign_root_identity=authority["root_identity"],
        tools=authority["tools"],
        inputs=authority["inputs"],
        created_at_utc=NOW,
    )
    identity = AUTH.write_gate1_selection(
        authority["root_path"],
        authority["root_identity"],
        selection,
    )
    return selection, identity


def _gate_admission_epoch(
    authority: dict[str, Any],
    selection: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    captured = _capture_result(authority["epoch"], clock_base_ns=10_000)
    transcript = captured["transcript"]
    selected_tools = {role: selection["tools"][role] for role in AUTH.GATE_ADMISSION_CAPTURE_TOOL_ROLES}
    binding = AUTH.sha256_bytes(
        AUTH.canonical_json(
            {
                "campaign_id": authority["root"]["campaign_id"],
                "capture_transcript": transcript,
                "phase": "gate-admission",
                "run_nonce": authority["root"]["run_nonce"],
                "selected_tool_identities": selected_tools,
                "selection_id": selection["selection_id"],
                "unit_slot": "gate-admission",
            }
        )
    )
    checkpoint = {
        "campaign_id": authority["root"]["campaign_id"],
        "capture_transcript": transcript,
        "captured_at_utc": NOW,
        "captured_monotonic_ns": 10_100,
        "manager_epoch": authority["epoch"],
        "manager_epoch_digest": AUTH.sha256_bytes(AUTH.canonical_json(authority["epoch"])),
        "phase": "gate-admission",
        "run_nonce": authority["root"]["run_nonce"],
        "schema_version": AUTH.GATE_ADMISSION_EPOCH_SCHEMA,
        "selected_tool_identities": selected_tools,
        "selection_id": selection["selection_id"],
        "transcript_binding_sha256": binding,
        "unit_name": (f"{authority['root']['unit_namespace']}-gate-admission.authority"),
        "unit_slot": "gate-admission",
    }
    AUTH.validate_gate_admission_epoch_checkpoint(
        checkpoint,
        root=authority["root"],
        selection=selection,
    )
    path = Path(authority["root"]["stage_topology"]["gate1_v4"]["gate_admission_epoch_path"])
    path.parent.mkdir(parents=True)
    identity = AUTH.write_exclusive(path, AUTH.canonical_json(checkpoint))
    return checkpoint, identity


def _gate_result(
    authority: dict[str, Any],
    gate_admission_epoch_identity: dict[str, object],
) -> dict[str, object]:
    return {
        "campaign_id": authority["root"]["campaign_id"],
        "continuation_authorized": False,
        "continuation_eligible": True,
        "gate_admission_epoch_identity": gate_admission_epoch_identity,
        "manager_epoch": authority["epoch"],
        "mechanism_credible": True,
        "organic_arm_launch_authorized": False,
        "status": "CUTS_GATE1_V4_AUTHORITY_COMPLETION_PASS",
    }


def test_same_fd_snapshot_and_exclusive_write_reject_symlink_and_overwrite(tmp_path: Path) -> None:
    source = _write(tmp_path / "source", b"source bytes")
    snapshot = AUTH.snapshot_regular(source)
    assert snapshot.data == b"source bytes"
    output_parent = tmp_path / "output"
    output_parent.mkdir()
    output = output_parent / "receipt.json"
    identity = AUTH.write_exclusive(output, b"{}\n")
    assert identity == _detached(output)
    with pytest.raises(AUTH.AuthorityError, match="overwrite"):
        AUTH.write_exclusive(output, b"changed")
    link = tmp_path / "source-link"
    link.symlink_to(source)
    with pytest.raises(AUTH.AuthorityError, match="symlink"):
        AUTH.snapshot_regular(link)


def test_snapshot_detects_same_fd_to_path_replacement(tmp_path: Path) -> None:
    source = _write(tmp_path / "source", b"first")

    def replace(path: Path) -> None:
        replacement = _write(tmp_path / "replacement", b"first")
        os.replace(replacement, path)

    with pytest.raises(AUTH.AuthorityError, match="changed during read|path identity changed"):
        AUTH.snapshot_regular(source, after_read=replace)


def test_read_only_attestor_ast_policy_and_negative_canaries() -> None:
    raw = (RESEARCH / "manager_attestor_v4.py").read_bytes()
    receipt = AUTH.audit_attestor_source(raw)
    assert receipt["status"] == "PASS"
    for mutation in (
        b"\nimport subprocess\n",
        b"\nBAD = os.O_WRONLY\n",
        b"\ndef forbidden():\n    os.kill(1, 0)\n",
        b"\ndef forbidden():\n    open('/tmp/x', 'w')\n",
    ):
        with pytest.raises(AUTH.AuthorityError):
            AUTH.audit_attestor_source(raw + mutation)


def test_attestor_joins_pid_starttime_boot_and_detects_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ATTESTOR, "_pid_starttime", lambda pid: 99)
    monkeypatch.setattr(ATTESTOR, "_boot_id", lambda: BOOT)
    monkeypatch.setattr(
        ATTESTOR,
        "_manager_executable",
        lambda pid: {
            "device": 1,
            "inode": 2,
            "mode": 0o755,
            "mode_octal": "0755",
            "path": "/usr/lib/systemd/systemd",
            "sha256": "a" * 64,
            "size_bytes": 10,
        },
    )
    argv = [
        "--pid",
        "2118",
        "--expected-starttime",
        "99",
        "--expected-boot-id",
        BOOT,
        "--dbus-owner",
        ":1.77",
    ]
    result = ATTESTOR.attest(argv)
    assert result["status"] == "PASS"
    assert result["request"]["manager_pid"] == 2118
    monkeypatch.setattr(ATTESTOR, "_pid_starttime", lambda pid: 100)
    with pytest.raises(ATTESTOR.AttestorError, match="starttime differs"):
        ATTESTOR.attest(argv)


def test_manager_epoch_assembly_rejects_owner_pid_starttime_and_tool_drift(tmp_path: Path) -> None:
    epoch = _epoch(tmp_path)
    AUTH.validate_manager_epoch(epoch)
    assert AUTH.same_manager_epoch(epoch, copy.deepcopy(epoch))
    for path, value in (
        (("dbus_unique_owner",), ":1.78"),
        (("manager_pid",), 2119),
        (("manager_pid_starttime",), 987655),
        (("manager_executable", "sha256"), "f" * 64),
        (("attestation_toolchain", "sudo", "sha256"), "e" * 64),
    ):
        mutated = copy.deepcopy(epoch)
        target: dict[str, Any] = mutated
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        assert not AUTH.same_manager_epoch(epoch, mutated)

    state = {
        key: epoch[key]
        for key in (
            "boot_id",
            "dbus_unique_owner",
            "manager_features",
            "manager_pid",
            "manager_pid_starttime",
            "manager_version",
        )
    }
    changed = dict(state, manager_pid_starttime=123)
    attestation = {
        "manager_executable": epoch["manager_executable"],
        "request": {
            "boot_id": BOOT,
            "dbus_unique_owner": ":1.77",
            "manager_pid": 2118,
            "manager_pid_starttime": 987654,
        },
        "schema": AUTH.ATTESTOR_SCHEMA,
        "status": "PASS",
    }
    with pytest.raises(AUTH.AuthorityError, match="manager state drifted"):
        AUTH.assemble_manager_epoch(
            unprivileged_before=state,
            attestation=attestation,
            unprivileged_after=changed,
            observation_toolchain=epoch["observation_toolchain"],
            attestation_toolchain=epoch["attestation_toolchain"],
            attestor_ast_audit=epoch["attestor_ast_audit"],
        )


def test_double_capture_preserves_replayable_before_attestor_after_transcript(
    tmp_path: Path,
) -> None:
    epoch = _epoch(tmp_path)
    template = _capture_result(epoch)["transcript"]["rounds"][0]
    state = copy.deepcopy(template["unprivileged_before"])

    def probe(busctl_path: str) -> dict[str, object]:
        assert busctl_path == epoch["observation_toolchain"]["busctl"]["path"]
        return copy.deepcopy(state)

    def invoke(
        expected: dict[str, object],
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        assert expected == state
        return (
            copy.deepcopy(template["privileged_attestation"]),
            copy.deepcopy(template["attestation_toolchain"]),
            {
                "audit": copy.deepcopy(template["attestor_ast_audit"]),
                "invocation": copy.deepcopy(template["attestor_invocation"]),
            },
        )

    ticks = iter((10, 20, 30, 40))
    captured = AUTH.capture_manager_epoch_with_transcript(
        attestor_path=epoch["attestation_toolchain"]["attestor"]["path"],
        busctl_path=epoch["observation_toolchain"]["busctl"]["path"],
        python_path=epoch["attestation_toolchain"]["python"]["path"],
        sudo_path=epoch["attestation_toolchain"]["sudo"]["path"],
        probe=probe,
        invoke=invoke,
        monotonic_ns=lambda: next(ticks),
    )
    AUTH.validate_manager_epoch(captured["manager_epoch"])
    assert captured["manager_epoch"]["manager_pid"] == epoch["manager_pid"]
    transcript = AUTH.validate_manager_epoch_capture_transcript(
        captured["transcript"],
        expected_epoch=captured["manager_epoch"],
    )
    assert [item["round_index"] for item in transcript["rounds"]] == [1, 2]
    assert transcript["rounds"][0]["attestor_invocation"]["stdout_base64"]


def test_busctl_user_probe_uses_uid_derived_runtime_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def run(argv: list[str], **kwargs: object) -> SimpleNamespace:
        observed["argv"] = argv
        observed["env"] = kwargs["env"]
        return SimpleNamespace(
            returncode=0,
            stdout=b'{"type":"s","data":[":1.1"]}\n',
            stderr=b"",
        )

    monkeypatch.setattr(AUTH.subprocess, "run", run)
    result = AUTH._busctl_json("/usr/bin/busctl", "call")  # noqa: SLF001
    assert result == {"type": "s", "data": [":1.1"]}
    assert observed["argv"] == [
        "/usr/bin/busctl",
        "--user",
        "--json=short",
        "call",
    ]
    environment = observed["env"]
    assert isinstance(environment, dict)
    assert environment["XDG_RUNTIME_DIR"] == f"/run/user/{os.getuid()}"
    assert "DBUS_SESSION_BUS_ADDRESS" not in environment


def test_privileged_invocation_fails_closed_on_sudo_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sudo = _write(tmp_path / "sudo", b"sudo fixture")
    python = _write(tmp_path / "python3.14", b"python fixture")
    monkeypatch.setattr(
        AUTH.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stderr=b"sudo denied",
            stdout=b"",
        ),
    )
    with pytest.raises(AUTH.AuthorityError, match="did not return clean"):
        AUTH._invoke_attestor(
            {
                "boot_id": BOOT,
                "dbus_unique_owner": ":1.77",
                "manager_pid": 2118,
                "manager_pid_starttime": 987654,
            },
            attestor_path=RESEARCH / "manager_attestor_v4.py",
            python_path=python,
            sudo_path=sudo,
        )


def test_package_seal_replay_and_source_or_member_mutation_fail_closed(tmp_path: Path) -> None:
    authority = _authority(tmp_path)
    package_dir = Path(authority["package"]["package_dir"])
    replay = AUTH.verify_package(
        package_dir,
        expected_manager_epoch=authority["epoch"],
        replay_external=True,
    )
    assert replay["status"] == "PASS"
    source = tmp_path / "inputs/mandatory.json"
    source.write_bytes(b'{"instances":[1]}\n')
    with pytest.raises(AUTH.AuthorityError, match="external source drifted"):
        AUTH.verify_package(
            package_dir,
            expected_manager_epoch=authority["epoch"],
            replay_external=True,
        )
    source.write_bytes(b'{"instances":[]}\n')
    member = package_dir / "payload/mandatory.json"
    member.write_bytes(b'{"instances":[2]}\n')
    with pytest.raises(AUTH.AuthorityError, match="seal"):
        AUTH.verify_package(
            package_dir,
            expected_manager_epoch=authority["epoch"],
            replay_external=False,
        )


def test_campaign_root_predeclares_gate1_and_reserved_ab16_without_creating_future_child(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path)
    root = authority["root"]
    assert root["campaign_closed"] is False
    assert root["unit_namespace"] == f"cuts-g1v4-{root['campaign_id'][:12]}"
    assert set(root["stage_topology"]) == {"gate1_v4", "prospective_ab16"}
    gate = root["stage_topology"]["gate1_v4"]
    assert tuple(gate["units"]) == AUTH.GATE1_SLOTS
    assert gate["gate_admission_epoch_schema"] == (AUTH.GATE_ADMISSION_EPOCH_SCHEMA)
    assert Path(gate["gate_admission_epoch_path"]) == (
        authority["campaign"] / "gate1-v4" / "authority" / "manager-epoch-gate-admission.json"
    )
    assert not Path(gate["gate_admission_epoch_path"]).exists()
    positive = gate["positive_control"]
    positive_root = Path(gate["positive_common_dir"])
    assert Path(positive["root_dir"]) == positive_root
    assert Path(positive["selection_path"]) == positive_root / "selection.json"
    assert Path(positive["common_manifest_path"]) == positive_root / "common-prestate/manifest.json"
    assert set(positive["common_artifact_paths"]) == {
        "candidates",
        "incumbent",
        "mandatory",
        "pre_model",
        "response",
        "selector_contract",
        "solution",
    }
    assert positive["binding_paths"] == {
        "control": str(positive_root / "bindings/control.json"),
        "treatment": str(positive_root / "bindings/treatment.json"),
    }
    assert Path(positive["binding_seal_path"]) == positive_root / "bindings/bindings-seal.json"
    assert positive["builder_export_dirs"] == {
        arm: str(positive_root / "builder-exports" / arm) for arm in ("common", "control", "treatment")
    }
    assert positive["arm_dirs"] == {
        "control": str(positive_root / "arms/control"),
        "treatment": str(positive_root / "arms/treatment"),
    }
    assert not positive_root.exists()
    prospective = root["stage_topology"]["prospective_ab16"]
    prospective_root = authority["campaign"] / "formal-ab16/artifacts/prospective"
    assert root["schema_version"] == AUTH.CAMPAIGN_ROOT_SCHEMA
    assert Path(prospective["manifest_path"]) == (
        prospective_root / "manifest-a001.json"
    )
    assert Path(prospective["arm_selection_path"]) == (
        prospective_root / "selection-a001.json"
    )
    assert {
        Path(arm["attempt_dir"]).parent for arm in prospective["arms"]
    } == {prospective_root / "arms"}
    assert len(prospective["arms"]) == 16
    assert len({arm["unit_name"] for arm in prospective["arms"]}) == 16
    assert not Path(prospective["manifest_path"]).exists()
    assert not Path(prospective["arm_selection_path"]).exists()
    assert "smm3" not in json.dumps(root).lower()

    missing = copy.deepcopy(root)
    missing["stage_topology"]["prospective_ab16"]["arms"].pop()
    with pytest.raises(AUTH.AuthorityError):
        AUTH.validate_campaign_root(missing)

    drifted = copy.deepcopy(root)
    drifted["stage_topology"]["gate1_v4"]["positive_control"]["binding_seal_path"] = str(tmp_path / "unbound-seal.json")
    with pytest.raises(AUTH.AuthorityError):
        AUTH.validate_campaign_root(drifted)

    drifted_epoch_path = copy.deepcopy(root)
    drifted_epoch_path["stage_topology"]["gate1_v4"]["gate_admission_epoch_path"] = str(
        tmp_path / "unbound-gate-epoch.json"
    )
    with pytest.raises(AUTH.AuthorityError, match="digest|admission"):
        AUTH.validate_campaign_root(drifted_epoch_path)


def _retarget_campaign_root_cohort(
    root: dict[str, Any],
    *,
    schema_version: str,
    prospective_root: Path,
) -> dict[str, Any]:
    result = copy.deepcopy(root)
    result["schema_version"] = schema_version
    prospective = result["stage_topology"]["prospective_ab16"]
    prospective["manifest_path"] = str(prospective_root / "manifest-a001.json")
    prospective["arm_selection_path"] = str(
        prospective_root / "selection-a001.json"
    )
    prospective["terminal_classification_path"] = str(
        prospective_root / "terminal-classification-a001.json"
    )
    for arm in prospective["arms"]:
        arm["attempt_dir"] = str(prospective_root / "arms" / arm["slot"])
    digest = AUTH._campaign_digest(result)  # noqa: SLF001
    old_namespace = result["unit_namespace"]
    new_namespace = f"cuts-g1v4-{digest[:12]}"
    result["unit_namespace"] = new_namespace
    for unit in result["stage_topology"]["gate1_v4"]["units"].values():
        unit["unit_name"] = unit["unit_name"].replace(
            old_namespace,
            new_namespace,
        )
    for arm in prospective["arms"]:
        arm["unit_name"] = arm["unit_name"].replace(
            old_namespace,
            new_namespace,
        )
    result["campaign_id"] = digest
    return result


def test_campaign_root_cohorts_preserve_v4_and_reject_path_mixing(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path)
    current = authority["root"]
    legacy_root = authority["campaign"] / "prospective-ab16"
    legacy = _retarget_campaign_root_cohort(
        current,
        schema_version=AUTH.LEGACY_CAMPAIGN_ROOT_SCHEMA,
        prospective_root=legacy_root,
    )
    assert (
        AUTH.validate_campaign_root(
            legacy,
            campaign_dir=authority["campaign"],
        )["schema_version"]
        == AUTH.LEGACY_CAMPAIGN_ROOT_SCHEMA
    )

    for mixed in (
        _retarget_campaign_root_cohort(
            current,
            schema_version=AUTH.CAMPAIGN_ROOT_SCHEMA,
            prospective_root=legacy_root,
        ),
        _retarget_campaign_root_cohort(
            current,
            schema_version=AUTH.LEGACY_CAMPAIGN_ROOT_SCHEMA,
            prospective_root=(
                authority["campaign"]
                / "formal-ab16/artifacts/prospective"
            ),
        ),
    ):
        with pytest.raises(AUTH.AuthorityError, match="cohort"):
            AUTH.validate_campaign_root(
                mixed,
                campaign_dir=authority["campaign"],
            )

    arm_mixed = copy.deepcopy(legacy)
    arm_mixed["stage_topology"]["prospective_ab16"]["arms"][0][
        "attempt_dir"
    ] = str(
        authority["campaign"]
        / "formal-ab16/artifacts/prospective/arms"
        / arm_mixed["stage_topology"]["prospective_ab16"]["arms"][0]["slot"]
    )
    arm_mixed["campaign_id"] = AUTH._campaign_digest(arm_mixed)  # noqa: SLF001
    old_namespace = arm_mixed["unit_namespace"]
    new_namespace = f"cuts-g1v4-{arm_mixed['campaign_id'][:12]}"
    arm_mixed["unit_namespace"] = new_namespace
    for unit in arm_mixed["stage_topology"]["gate1_v4"]["units"].values():
        unit["unit_name"] = unit["unit_name"].replace(
            old_namespace,
            new_namespace,
        )
    for arm in arm_mixed["stage_topology"]["prospective_ab16"]["arms"]:
        arm["unit_name"] = arm["unit_name"].replace(
            old_namespace,
            new_namespace,
        )
    with pytest.raises(AUTH.AuthorityError, match="slot/name"):
        AUTH.validate_campaign_root(
            arm_mixed,
            campaign_dir=authority["campaign"],
        )


def test_gate1_selection_binds_exact_bytes_epoch_contract_and_reserved_slots(tmp_path: Path) -> None:
    authority = _authority(tmp_path)
    selection, identity = _selection(authority)
    raw = Path(identity["path"]).read_bytes()
    loaded = AUTH.load_gate1_selection_bytes(raw, identity)
    assert loaded["selection_id"] == selection["selection_id"]
    assert loaded["resource_contract"] == AUTH.RESOURCE_CONTRACT
    root, replayed = AUTH.replay_gate1_selection(
        authority["root_path"],
        authority["root_identity"],
        identity,
        current_manager_epoch=authority["epoch"],
    )
    assert root["campaign_id"] == replayed["campaign_id"]

    pretty = json.dumps(selection, indent=2, sort_keys=True).encode() + b"\n"
    Path(identity["path"]).write_bytes(pretty)
    with pytest.raises(AUTH.AuthorityError, match="bytes drifted"):
        AUTH.replay_gate1_selection(
            authority["root_path"],
            authority["root_identity"],
            identity,
            current_manager_epoch=authority["epoch"],
        )


def test_gate1_selection_schema_is_consumable_by_lifecycle_and_resource_verifier(tmp_path: Path) -> None:
    authority = _authority(tmp_path)
    selection = AUTH.make_gate1_selection(
        authority["root"],
        campaign_root_identity=authority["root_identity"],
        tools=authority["tools"],
        inputs=authority["inputs"],
        created_at_utc=NOW,
    )
    assert LIFECYCLE._validate_selection(selection)["selection_id"] == selection["selection_id"]
    raw = AUTH.canonical_json(selection)
    identity = AUTH.identity_from_bytes(
        authority["root"]["stage_topology"]["gate1_v4"]["selection_path"],
        raw,
    )
    assert RESOURCE_VERIFIER._validate_selection(raw, identity)["selection_id"] == selection["selection_id"]


def test_gate1_selection_rejects_missing_mandatory_tool_or_input(tmp_path: Path) -> None:
    authority = _authority(tmp_path)
    selection = AUTH.make_gate1_selection(
        authority["root"],
        campaign_root_identity=authority["root_identity"],
        tools=authority["tools"],
        inputs=authority["inputs"],
        created_at_utc=NOW,
    )
    for group, role in (
        ("tools", "resource_verifier_v4"),
        ("inputs", "candidate_placements"),
    ):
        mutated = copy.deepcopy(selection)
        mutated[group].pop(role)
        mutated["selection_id"] = AUTH._digest_without(mutated, "selection_id")
        with pytest.raises(AUTH.AuthorityError, match="mandatory"):
            AUTH.validate_gate1_selection(mutated)


def test_driver_public_capture_surface_has_no_observer_or_clock_seam() -> None:
    parameters = set(inspect.signature(DRIVER.capture_lifecycle_epoch_checkpoint).parameters)
    assert parameters == {
        "attestor_path",
        "busctl_path",
        "campaign_root_identity",
        "phase",
        "python_path",
        "selection_identity",
        "sudo_path",
        "unit_slot",
    }
    assert {
        "before_write",
        "capture_manager_epoch_transcript",
        "monotonic_ns",
        "now_utc",
    }.isdisjoint(parameters)


def test_driver_captures_each_live_epoch_at_exact_preregistered_path(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path)
    selection, selection_identity = _selection(authority)
    slot = "q-success"
    attempt = Path(selection["units"][slot]["attempt_dir"])
    (attempt / "authority").mkdir(parents=True)
    calls: list[dict[str, object]] = []

    def capture(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return _capture_result(
            authority["epoch"],
            clock_base_ns=(len(calls) - 1) * 100,
        )

    ticks = iter((100, 200, 300, 400, 500))
    for phase in DRIVER.CHECKPOINT_PHASES:
        identity = DRIVER._capture_lifecycle_epoch_checkpoint_with(
            campaign_root_identity=authority["root_identity"],
            selection_identity=selection_identity,
            unit_slot=slot,
            phase=phase,
            attestor_path=tmp_path / "attestor",
            busctl_path=tmp_path / "busctl",
            python_path=tmp_path / "python",
            sudo_path=tmp_path / "sudo",
            capture_manager_epoch_transcript=capture,
            now_utc=lambda: NOW,
            monotonic_ns=lambda: next(ticks),
        )
        expected = attempt / "authority" / f"manager-epoch-{phase}.json"
        assert identity["path"] == str(expected.absolute())
        receipt = json.loads(expected.read_bytes())
        assert receipt["schema_version"] == DRIVER.CHECKPOINT_SCHEMA
        assert receipt["phase"] == phase
        assert receipt["manager_epoch"] == authority["epoch"]
        assert receipt["manager_epoch_digest"] == DRIVER._epoch_digest(authority["epoch"])
        assert len(receipt["capture_transcript"]["rounds"]) == 2
        assert (
            receipt["selected_tool_identities"]["gate1_campaign_driver_v4"]
            == authority["tools"]["gate1_campaign_driver_v4"]
        )
    assert len(calls) == len(DRIVER.CHECKPOINT_PHASES)
    assert calls[0] == {
        "attestor_path": tmp_path / "attestor",
        "busctl_path": tmp_path / "busctl",
        "python_path": tmp_path / "python",
        "sudo_path": tmp_path / "sudo",
    }


def test_driver_rejects_epoch_drift_overwrite_and_out_of_order_phase(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path)
    selection, selection_identity = _selection(authority)
    slot = "q-success"
    attempt = Path(selection["units"][slot]["attempt_dir"])
    (attempt / "authority").mkdir(parents=True)

    def capture(**_kwargs: object) -> dict[str, object]:
        return _capture_result(authority["epoch"])

    common = {
        "campaign_root_identity": authority["root_identity"],
        "selection_identity": selection_identity,
        "unit_slot": slot,
        "attestor_path": tmp_path / "attestor",
        "busctl_path": tmp_path / "busctl",
        "python_path": tmp_path / "python",
        "sudo_path": tmp_path / "sudo",
        "capture_manager_epoch_transcript": capture,
        "now_utc": lambda: NOW,
        "monotonic_ns": lambda: 100,
    }
    with pytest.raises(DRIVER.DriverError, match="predecessor"):
        DRIVER._capture_lifecycle_epoch_checkpoint_with(
            **common,
            phase="preterminal",
        )

    drifted = copy.deepcopy(authority["epoch"])
    drifted["manager_pid_starttime"] += 1
    with pytest.raises((DRIVER.DriverError, AUTH.AuthorityError), match="transcript|does not join"):
        DRIVER._capture_lifecycle_epoch_checkpoint_with(
            **{
                **common,
                "capture_manager_epoch_transcript": lambda **_kwargs: {
                    **_capture_result(authority["epoch"]),
                    "manager_epoch": drifted,
                },
            },
            phase="prelaunch",
        )
    prelaunch = attempt / "authority/manager-epoch-prelaunch.json"
    assert not prelaunch.exists()

    DRIVER._capture_lifecycle_epoch_checkpoint_with(
        **common,
        phase="prelaunch",
    )
    before = prelaunch.read_bytes()
    with pytest.raises(DRIVER.DriverError, match="already exists|not the first"):
        DRIVER._capture_lifecycle_epoch_checkpoint_with(
            **common,
            phase="prelaunch",
        )
    assert prelaunch.read_bytes() == before


def test_driver_rechecks_root_and_selection_after_live_capture(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path)
    selection, selection_identity = _selection(authority)
    slot = "q-success"
    attempt = Path(selection["units"][slot]["attempt_dir"])
    (attempt / "authority").mkdir(parents=True)
    root_path = Path(authority["root_identity"]["path"])

    def replace_root() -> None:
        replacement = root_path.with_name("replacement-root.json")
        replacement.write_bytes(root_path.read_bytes())
        os.replace(replacement, root_path)

    with pytest.raises(DRIVER.DriverError, match="campaign root drifted"):
        DRIVER._capture_lifecycle_epoch_checkpoint_with(
            campaign_root_identity=authority["root_identity"],
            selection_identity=selection_identity,
            unit_slot=slot,
            phase="prelaunch",
            attestor_path=tmp_path / "attestor",
            busctl_path=tmp_path / "busctl",
            python_path=tmp_path / "python",
            sudo_path=tmp_path / "sudo",
            capture_manager_epoch_transcript=lambda **_kwargs: _capture_result(authority["epoch"]),
            now_utc=lambda: NOW,
            monotonic_ns=lambda: 100,
            before_write=replace_root,
        )
    assert not (attempt / "authority/manager-epoch-prelaunch.json").exists()


def test_driver_rejects_symlinked_checkpoint_parent(tmp_path: Path) -> None:
    authority = _authority(tmp_path)
    selection, selection_identity = _selection(authority)
    slot = "q-success"
    attempt = Path(selection["units"][slot]["attempt_dir"])
    attempt.mkdir(parents=True)
    target = tmp_path / "elsewhere"
    target.mkdir()
    (attempt / "authority").symlink_to(target, target_is_directory=True)
    with pytest.raises(AUTH.AuthorityError, match="symlink"):
        DRIVER._capture_lifecycle_epoch_checkpoint_with(
            campaign_root_identity=authority["root_identity"],
            selection_identity=selection_identity,
            unit_slot=slot,
            phase="prelaunch",
            attestor_path=tmp_path / "attestor",
            busctl_path=tmp_path / "busctl",
            python_path=tmp_path / "python",
            sudo_path=tmp_path / "sudo",
            capture_manager_epoch_transcript=lambda **_kwargs: _capture_result(authority["epoch"]),
            now_utc=lambda: NOW,
            monotonic_ns=lambda: 100,
        )


def test_selection_rejects_future_slot_precreation_and_epoch_drift(tmp_path: Path) -> None:
    authority = _authority(tmp_path)
    selection = AUTH.make_gate1_selection(
        authority["root"],
        campaign_root_identity=authority["root_identity"],
        tools=authority["tools"],
        inputs=authority["inputs"],
        created_at_utc=NOW,
    )
    future = Path(authority["root"]["stage_topology"]["prospective_ab16"]["manifest_path"])
    future.parent.mkdir(parents=True)
    future.write_text("{}\n", encoding="utf-8")
    with pytest.raises(AUTH.AuthorityError, match="child path exists"):
        AUTH.write_gate1_selection(
            authority["root_path"],
            authority["root_identity"],
            selection,
        )
    drifted = copy.deepcopy(authority["epoch"])
    drifted["boot_id"] = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert not AUTH.same_manager_epoch(authority["epoch"], drifted)


def test_continuation_keeps_campaign_open_and_cannot_consume_future_slots(tmp_path: Path) -> None:
    authority = _authority(tmp_path)
    selection, selection_identity = _selection(authority)
    _, gate_admission_identity = _gate_admission_epoch(
        authority,
        selection,
    )
    gate_path = Path(authority["root"]["stage_topology"]["gate1_v4"]["gate_path"])
    gate_result = _gate_result(authority, gate_admission_identity)
    gate_identity = AUTH.write_exclusive(gate_path, AUTH.canonical_json(gate_result))
    replay_identities: dict[str, object] = {}
    for slot, unit in authority["root"]["stage_topology"]["gate1_v4"]["units"].items():
        replay = Path(unit["attempt_dir"]) / "detached-replay.json"
        replay.parent.mkdir(parents=True)
        replay_identities[slot] = AUTH.write_exclusive(replay, b'{"status":"PASS"}\n')
    continuation = AUTH.make_continuation_authorization(
        authority["root"],
        campaign_root_identity=authority["root_identity"],
        gate1_selection_identity=selection_identity,
        gate_result=gate_result,
        gate_result_identity=gate_identity,
        gate_admission_epoch_identity=gate_admission_identity,
        detached_replay_identities=replay_identities,
        current_manager_epoch=authority["epoch"],
        created_at_utc=NOW,
    )
    continuation_identity = AUTH.write_continuation_authorization(
        authority["root_path"],
        authority["root_identity"],
        continuation,
    )
    assert continuation["campaign_closed"] is False
    assert continuation["continuation_eligible"] is True
    assert continuation["continuation_authorized"] is True
    assert continuation["gate_admission_epoch_identity"] == gate_admission_identity
    assert continuation["organic_arm_launch_authorized"] is False
    assert Path(continuation_identity["path"]).exists()
    prospective = authority["root"]["stage_topology"]["prospective_ab16"]
    assert not Path(prospective["manifest_path"]).exists()
    assert not Path(prospective["arm_selection_path"]).exists()


def test_continuation_requires_all_replays_exact_pass_gate_and_same_epoch(tmp_path: Path) -> None:
    authority = _authority(tmp_path)
    selection, selection_identity = _selection(authority)
    _, gate_admission_identity = _gate_admission_epoch(
        authority,
        selection,
    )
    gate_result = _gate_result(authority, gate_admission_identity)
    gate_path = Path(authority["root"]["stage_topology"]["gate1_v4"]["gate_path"])
    gate_identity = AUTH.write_exclusive(gate_path, AUTH.canonical_json(gate_result))
    replay_identities = {
        slot: {
            "path": str((tmp_path / f"{slot}.json").absolute()),
            "sha256": "a" * 64,
            "size_bytes": 1,
        }
        for slot in AUTH.GATE1_SLOTS
    }
    incomplete = dict(replay_identities)
    incomplete.pop("q-success")
    with pytest.raises(AUTH.AuthorityError, match="exactly four"):
        AUTH.make_continuation_authorization(
            authority["root"],
            campaign_root_identity=authority["root_identity"],
            gate1_selection_identity=selection_identity,
            gate_result=gate_result,
            gate_result_identity=gate_identity,
            gate_admission_epoch_identity=gate_admission_identity,
            detached_replay_identities=incomplete,
            current_manager_epoch=authority["epoch"],
            created_at_utc=NOW,
        )


def test_gate_admission_epoch_and_eligible_only_gate_are_fail_closed(
    tmp_path: Path,
) -> None:
    authority = _authority(tmp_path)
    selection, selection_identity = _selection(authority)
    checkpoint, checkpoint_identity = _gate_admission_epoch(
        authority,
        selection,
    )
    gate_result = _gate_result(authority, checkpoint_identity)
    gate_path = Path(authority["root"]["stage_topology"]["gate1_v4"]["gate_path"])
    gate_identity = AUTH.write_exclusive(
        gate_path,
        AUTH.canonical_json(gate_result),
    )
    replay_identities: dict[str, object] = {}
    for slot, unit in authority["root"]["stage_topology"]["gate1_v4"]["units"].items():
        replay = Path(unit["attempt_dir"]) / "detached-replay.json"
        replay.parent.mkdir(parents=True)
        replay_identities[slot] = AUTH.write_exclusive(
            replay,
            b'{"status":"PASS"}\n',
        )

    for mutation in (
        dict(gate_result, continuation_eligible=False),
        dict(gate_result, continuation_authorized=True),
        dict(gate_result, gate_admission_epoch_identity=gate_identity),
    ):
        with pytest.raises(AUTH.AuthorityError, match="does not authorize"):
            AUTH.make_continuation_authorization(
                authority["root"],
                campaign_root_identity=authority["root_identity"],
                gate1_selection_identity=selection_identity,
                gate_result=mutation,
                gate_result_identity=gate_identity,
                gate_admission_epoch_identity=checkpoint_identity,
                detached_replay_identities=replay_identities,
                current_manager_epoch=authority["epoch"],
                created_at_utc=NOW,
            )

    for field, value in (
        ("unit_slot", "forced-treatment"),
        ("phase", "detached-replay"),
        ("schema_version", "wrong-schema"),
    ):
        mutated = copy.deepcopy(checkpoint)
        mutated[field] = value
        with pytest.raises(
            AUTH.AuthorityError,
            match="checkpoint semantics|selected|schema|timeline",
        ):
            AUTH.validate_gate_admission_epoch_checkpoint(
                mutated,
                root=authority["root"],
                selection=selection,
            )


def test_continuation_write_rechecks_detached_replay_bytes(tmp_path: Path) -> None:
    authority = _authority(tmp_path)
    selection, selection_identity = _selection(authority)
    _, gate_admission_identity = _gate_admission_epoch(
        authority,
        selection,
    )
    gate_result = _gate_result(authority, gate_admission_identity)
    gate_path = Path(authority["root"]["stage_topology"]["gate1_v4"]["gate_path"])
    gate_identity = AUTH.write_exclusive(gate_path, AUTH.canonical_json(gate_result))
    replay_identities: dict[str, object] = {}
    for slot, unit in authority["root"]["stage_topology"]["gate1_v4"]["units"].items():
        replay = Path(unit["attempt_dir"]) / "detached-replay.json"
        replay.parent.mkdir(parents=True)
        replay_identities[slot] = AUTH.write_exclusive(replay, b'{"status":"PASS"}\n')
    continuation = AUTH.make_continuation_authorization(
        authority["root"],
        campaign_root_identity=authority["root_identity"],
        gate1_selection_identity=selection_identity,
        gate_result=gate_result,
        gate_result_identity=gate_identity,
        gate_admission_epoch_identity=gate_admission_identity,
        detached_replay_identities=replay_identities,
        current_manager_epoch=authority["epoch"],
        created_at_utc=NOW,
    )
    Path(replay_identities["forced-treatment"]["path"]).write_bytes(b'{"status":"PASS","same_semantics":true}\n')
    with pytest.raises(AUTH.AuthorityError, match="current bytes drifted"):
        AUTH.write_continuation_authorization(
            authority["root_path"],
            authority["root_identity"],
            continuation,
        )
    bad_gate = dict(gate_result, mechanism_credible=False)
    with pytest.raises(AUTH.AuthorityError, match="does not authorize"):
        AUTH.make_continuation_authorization(
            authority["root"],
            campaign_root_identity=authority["root_identity"],
            gate1_selection_identity=selection_identity,
            gate_result=bad_gate,
            gate_result_identity=gate_identity,
            gate_admission_epoch_identity=gate_admission_identity,
            detached_replay_identities=replay_identities,
            current_manager_epoch=authority["epoch"],
            created_at_utc=NOW,
        )
    drifted = copy.deepcopy(authority["epoch"])
    drifted["manager_pid_starttime"] += 1
    with pytest.raises(AUTH.AuthorityError, match="epoch"):
        AUTH.make_continuation_authorization(
            authority["root"],
            campaign_root_identity=authority["root_identity"],
            gate1_selection_identity=selection_identity,
            gate_result=gate_result,
            gate_result_identity=gate_identity,
            gate_admission_epoch_identity=gate_admission_identity,
            detached_replay_identities=replay_identities,
            current_manager_epoch=drifted,
            created_at_utc=NOW,
        )
