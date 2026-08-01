from __future__ import annotations

import base64
import copy
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import ModuleType
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
AB16_RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
NOW = "2026-07-24T13:00:00Z"
BOOT_ID = "11111111-2222-3333-4444-555555555555"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BOOTSTRAP = _load(
    "noncert_cuts_ab16_campaign_bootstrap_v1_tested",
    AB16_RESEARCH / "ab16_campaign_bootstrap_v1.py",
)
AUTH = BOOTSTRAP.authority
CONTRACT = _load(
    "noncert_cuts_ab16_contract_v1_for_bootstrap",
    AB16_RESEARCH / "ab16_contract_v1.py",
)


def test_cli_default_python_uses_the_current_merged_repository() -> None:
    arguments = BOOTSTRAP._parse_args(  # noqa: SLF001
        [
            "candidate",
            "--campaign-dir",
            "campaign",
            "--repository-root",
            "repository",
            "--gate-a-receipt",
            "gate-a.json",
            "--history-freeze-manifest",
            "history.json",
            "--cuts-mandatory-schedule",
            "cuts.json",
            "--legacy-control-a002",
            "legacy.json",
            "--candidate-output",
            "candidate.json",
        ]
    )
    assert arguments.python3_13 == Path("/home/zhuran24/zmd-pj/.venv-uvbolt-backup/bin/python3.13")


def _write(path: Path, raw: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def _json(path: Path, value: object) -> Path:
    return _write(path, AUTH.canonical_json(value))


def _detached(path: Path) -> dict[str, object]:
    return AUTH.detached_identity(AUTH.snapshot_regular(path))


def _full(path: Path) -> dict[str, object]:
    return AUTH.full_identity(AUTH.snapshot_regular(path))


def _git_fixture(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    source = Path(shutil.which("git") or "").resolve(strict=True)
    target = tmp_path / "system" / "git-real"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target, AUTH.snapshot_tool(target)[1]


def test_repository_head_executes_the_same_pinned_git_fd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git_path, identity = _git_fixture(tmp_path)
    real_run = subprocess.run
    observed: dict[str, object] = {}

    def record_run(*args: object, **kwargs: object):
        observed["executable"] = kwargs.get("executable")
        observed["pass_fds"] = kwargs.get("pass_fds")
        return real_run(*args, **kwargs)

    monkeypatch.setattr(BOOTSTRAP.subprocess, "run", record_run)
    assert (
        BOOTSTRAP._observe_repository_head(  # noqa: SLF001
            ROOT,
            git_path,
            expected_identity=identity,
        )
        == HEAD
    )
    assert str(observed["executable"]).startswith("/proc/self/fd/")
    assert type(observed["pass_fds"]) is tuple and len(observed["pass_fds"]) == 1


def test_repository_head_rejects_path_swap_during_fd_exec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git_path, identity = _git_fixture(tmp_path)
    real_run = subprocess.run

    def swap_after_run(*args: object, **kwargs: object):
        completed = real_run(*args, **kwargs)
        replacement = git_path.with_name("replacement-git")
        shutil.copy2(git_path, replacement)
        os.replace(replacement, git_path)
        return completed

    monkeypatch.setattr(BOOTSTRAP.subprocess, "run", swap_after_run)
    with pytest.raises(BOOTSTRAP.BootstrapError, match="path changed"):
        BOOTSTRAP._observe_repository_head(  # noqa: SLF001
            ROOT,
            git_path,
            expected_identity=identity,
        )


def test_repository_head_rejects_same_inode_byte_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git_path, identity = _git_fixture(tmp_path)
    real_run = subprocess.run

    def mutate_after_run(*args: object, **kwargs: object):
        completed = real_run(*args, **kwargs)
        with git_path.open("r+b", buffering=0) as stream:
            first = stream.read(1)
            stream.seek(0)
            stream.write(bytes([first[0] ^ 1]))
            os.fsync(stream.fileno())
        return completed

    monkeypatch.setattr(BOOTSTRAP.subprocess, "run", mutate_after_run)
    with pytest.raises(BOOTSTRAP.BootstrapError, match="bytes changed"):
        BOOTSTRAP._observe_repository_head(  # noqa: SLF001
            ROOT,
            git_path,
            expected_identity=identity,
        )


def _fixture_sources(
    tmp_path: Path,
) -> tuple[dict[str, Path], dict[str, Path]]:
    strict: dict[str, Path] = {}
    for role in sorted(BOOTSTRAP.STRICT_INPUT_ROLES):
        if role in BOOTSTRAP.CANONICAL_JSON_INPUT_ROLES:
            raw = AUTH.canonical_json({"fixture": True, "role": role})
        elif role == "canonical_rules":
            raw = b'{"fixture_float":1.25}\n'
        elif role == "legacy_control_a002":
            raw = b'{"historical_float":0.5}\n'
        else:
            raw = f"fixture {role}\n".encode()
        strict[role] = _write(tmp_path / "inputs" / role, raw)
    system = {
        role: _write(
            tmp_path / "system" / role,
            f"fixture executable {role}\n".encode(),
        )
        for role in sorted(BOOTSTRAP.SYSTEM_TOOL_ROLES)
    }
    return strict, system


def _capture_result(
    tmp_path: Path,
    system: dict[str, Path],
) -> dict[str, object]:
    manager = _write(tmp_path / "system" / "systemd-manager", b"manager\n")
    attestor = BOOTSTRAP.V4_RESEARCH_DIR / "manager_attestor_v4.py"
    state = {
        "boot_id": BOOT_ID,
        "dbus_unique_owner": ":1.77",
        "manager_features": "+PAM +AUDIT",
        "manager_pid": 2118,
        "manager_pid_starttime": 987654,
        "manager_version": "systemd 261.1",
    }
    attestation = {
        "manager_executable": _full(manager),
        "request": {
            "boot_id": state["boot_id"],
            "dbus_unique_owner": state["dbus_unique_owner"],
            "manager_pid": state["manager_pid"],
            "manager_pid_starttime": state["manager_pid_starttime"],
        },
        "schema": AUTH.ATTESTOR_SCHEMA,
        "status": "PASS",
    }
    tools = {
        "attestor": _full(attestor),
        "python": _full(system["attestor_python"]),
        "sudo": _full(system["sudo"]),
    }
    audit = AUTH.audit_attestor_source(attestor.read_bytes())
    invocation = {
        "argv": [
            str(system["sudo"]),
            "-n",
            "--",
            str(system["attestor_python"]),
            "-I",
            "-c",
            AUTH._LOADER,  # noqa: SLF001
            "--pid",
            str(state["manager_pid"]),
            "--expected-starttime",
            str(state["manager_pid_starttime"]),
            "--expected-boot-id",
            str(state["boot_id"]),
            "--dbus-owner",
            str(state["dbus_unique_owner"]),
        ],
        "exit_code": 0,
        "stdin_sha256": tools["attestor"]["sha256"],
        "stdin_size_bytes": tools["attestor"]["size_bytes"],
        "stdout_base64": base64.b64encode(AUTH.canonical_json(attestation)).decode("ascii"),
    }

    def invoke(
        _: dict[str, object],
    ) -> tuple[
        dict[str, object],
        dict[str, object],
        dict[str, object],
    ]:
        return (
            copy.deepcopy(attestation),
            copy.deepcopy(tools),
            {
                "audit": copy.deepcopy(audit),
                "invocation": copy.deepcopy(invocation),
            },
        )

    clock = iter((10, 20, 30, 40))
    return AUTH.capture_manager_epoch_with_transcript(
        attestor_path=attestor,
        busctl_path=system["busctl"],
        python_path=system["attestor_python"],
        sudo_path=system["sudo"],
        probe=lambda _: copy.deepcopy(state),
        invoke=invoke,
        monotonic_ns=lambda: next(clock),
    )


def _gate_a(
    tmp_path: Path,
    *,
    campaign: Path,
    planned_digest: str,
    approval_id: str = "gate-a-fixture-pass",
) -> Path:
    return _json(
        tmp_path / "approvals" / "gate-a.json",
        {
            "approval_id": approval_id,
            "arm_launch_authorized": False,
            "created_at_utc": "2026-07-24T12:55:00Z",
            "decision": "PASS",
            "formal_campaign_creation_authorized": False,
            "gate": "A",
            "offline_candidate_only": True,
            "planned_source_set_digest": planned_digest,
            "purpose": BOOTSTRAP.GATE_A_PURPOSE,
            "repository_head": HEAD,
            "repository_root": str(ROOT),
            "run_nonce": campaign.name,
            "schema_version": BOOTSTRAP.GATE_A_SCHEMA,
            "target_campaign_dir": str(campaign),
        },
    )


def _gate_b(
    tmp_path: Path,
    *,
    campaign: Path,
    gate_a: Path,
    candidate: Path,
    planned_digest: str,
    approval_id: str = "gate-b-fixture-approval",
    formal_authorized: bool = True,
) -> Path:
    return _json(
        tmp_path / "approvals" / "gate-b.json",
        {
            "approval_id": approval_id,
            "arm_launch_authorized": False,
            "candidate_identity": _detached(candidate),
            "created_at_utc": "2026-07-24T12:59:00Z",
            "decision": "APPROVED",
            "formal_campaign_creation_authorized": formal_authorized,
            "gate": "B",
            "gate_a_receipt_identity": _detached(gate_a),
            "planned_source_set_digest": planned_digest,
            "purpose": BOOTSTRAP.GATE_B_PURPOSE,
            "repository_head": HEAD,
            "repository_root": str(ROOT),
            "run_nonce": campaign.name,
            "schema_version": BOOTSTRAP.GATE_B_SCHEMA,
            "target_campaign_dir": str(campaign),
        },
    )


def _offline_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    campaign_parent = tmp_path / "campaigns"
    campaign_parent.mkdir()
    campaign = campaign_parent / "run-fixture-a001"
    strict, system = _fixture_sources(tmp_path)
    monkeypatch.setattr(
        BOOTSTRAP,
        "_observe_repository_head",
        lambda *_, **__: HEAD,
    )
    observed = BOOTSTRAP.observe_planned_sources(
        strict_input_paths=strict,
        system_tool_paths=system,
    )
    gate_a = _gate_a(
        tmp_path,
        campaign=campaign,
        planned_digest=observed["planned_source_set_digest"],
    )
    candidate_path = tmp_path / "offline" / "candidate-a001.json"
    candidate_path.parent.mkdir()
    candidate = BOOTSTRAP.build_gate_a_candidate(
        output_path=candidate_path,
        gate_a_receipt=gate_a,
        repository_root=ROOT,
        target_campaign_dir=campaign,
        strict_input_paths=strict,
        system_tool_paths=system,
        created_at_utc="2026-07-24T12:56:00Z",
    )
    return {
        "campaign": campaign,
        "candidate": candidate,
        "candidate_path": candidate_path,
        "path_preregistration_path": (candidate_path.parent / "ab16-path-preregistration.json"),
        "gate_a": gate_a,
        "planned": observed,
        "strict": strict,
        "system": system,
    }


def _complete_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    gate_b = _gate_b(
        tmp_path,
        campaign=fixture["campaign"],
        gate_a=fixture["gate_a"],
        candidate=fixture["candidate_path"],
        planned_digest=fixture["planned"]["planned_source_set_digest"],
    )
    capture = _capture_result(tmp_path, fixture["system"])
    monkeypatch.setattr(
        BOOTSTRAP,
        "_capture_epoch",
        lambda **_: copy.deepcopy(capture),
    )
    fixture["capture"] = capture
    fixture["gate_b"] = gate_b
    return fixture


def _bootstrap(fixture: dict[str, Any]) -> dict[str, object]:
    return BOOTSTRAP.bootstrap_campaign(
        campaign_dir=fixture["campaign"],
        repository_root=ROOT,
        gate_a_receipt=fixture["gate_a"],
        offline_candidate=fixture["candidate_path"],
        gate_b_approval=fixture["gate_b"],
        strict_input_paths=fixture["strict"],
        system_tool_paths=fixture["system"],
        created_at_utc=NOW,
    )


def test_gate_a_creates_only_nonauthorizing_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    assert fixture["candidate_path"].is_file()
    assert not fixture["campaign"].exists()
    candidate = fixture["candidate"]["candidate"]
    path_preregistration = fixture["candidate"]["path_preregistration"]
    assert candidate["candidate_only"] is True
    assert candidate["formal_campaign_creation_authorized"] is False
    assert candidate["arm_launch_authorized"] is False
    assert fixture["candidate"]["formal_campaign_created"] is False
    assert fixture["path_preregistration_path"].is_file()
    assert path_preregistration == BOOTSTRAP._path_preregistration(  # noqa: SLF001
        fixture["campaign"]
    )
    assert set(path_preregistration) == {
        "arm_sequence",
        "attempt_directory_pattern",
        "baseline_admission_path",
        "baseline_fixed_replay_path",
        "baseline_incumbent_path",
        "baseline_rebuilt_metadata_path",
        "baseline_rebuilt_model_path",
        "binding_paths",
        "campaign_dir",
        "classification_contract_path",
        "common_prestate_path",
        "experiment_contract_sha256",
        "manifest_path",
        "purpose",
        "retry_policy",
        "run_nonce",
        "runtime_max_sec",
        "schema",
        "seed",
        "slot_roots",
        "suite_selection_path",
        "terminal_classification_path",
        "workers",
    }
    assert path_preregistration["schema"] == "noncert-cuts-ab16-scientific-preregistration-v2"
    assert path_preregistration["arm_sequence"] == list(CONTRACT.ARM_SEQUENCE)
    assert path_preregistration["attempt_directory_pattern"] == "attempt-[0-9]{4,}"
    assert len(path_preregistration["slot_roots"]) == 16
    assert set(path_preregistration["slot_roots"]) == set(CONTRACT.ARM_SEQUENCE)
    assert path_preregistration["experiment_contract_sha256"] == (
        "24b45e110952505e6ffa92d3ddfdf33874cc3cb4503397e993898e79174ded9e"
    )
    assert path_preregistration["seed"] == 2026072301
    assert path_preregistration["workers"] == 1
    assert path_preregistration["runtime_max_sec"] == 3600
    assert path_preregistration["retry_policy"] == {
        "credible_terminal_closes_slot": True,
        "failed_attempt_retryable": True,
        "lowest_credible_ordinal_wins": True,
        "no_overwrite_per_attempt": True,
        "retry_limit": None,
    }
    assert Path(path_preregistration["baseline_rebuilt_model_path"]).name == "cut-free-model.bin"
    assert Path(path_preregistration["baseline_rebuilt_metadata_path"]).name == "rebuilt-model-metadata.json"
    assert Path(path_preregistration["baseline_incumbent_path"]).name == ("incumbent.json")


@pytest.mark.parametrize(
    "mutation",
    (
        "arm_sequence",
        "attempt_directory_pattern",
        "experiment_contract_sha256",
        "extra_key",
        "retry_policy",
        "runtime_max_sec",
        "seed",
        "slot_root",
        "workers",
    ),
)
def test_scientific_preregistration_rejects_design_or_topology_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    campaign = tmp_path / "campaigns" / "run-preregistration-a001"
    preregistration = BOOTSTRAP._path_preregistration(campaign)  # noqa: SLF001
    if mutation == "arm_sequence":
        preregistration["arm_sequence"][:2] = reversed(preregistration["arm_sequence"][:2])
    elif mutation == "attempt_directory_pattern":
        preregistration["attempt_directory_pattern"] = "attempt-[0-9]{3}"
    elif mutation == "experiment_contract_sha256":
        preregistration["experiment_contract_sha256"] = "0" * 64
    elif mutation == "extra_key":
        preregistration["attempt_candidate_paths"] = {}
    elif mutation == "retry_policy":
        preregistration["retry_policy"]["failed_attempt_retryable"] = False
    elif mutation == "runtime_max_sec":
        preregistration["runtime_max_sec"] = 3599
    elif mutation == "seed":
        preregistration["seed"] = 2026072302
    elif mutation == "slot_root":
        first = CONTRACT.ARM_SEQUENCE[0]
        preregistration["slot_roots"][first] = str(campaign / "prospective-ab16" / "arms" / "wrong")
    else:
        preregistration["workers"] = 2

    with pytest.raises(BOOTSTRAP.BootstrapError, match="key set drifted|topology drifted"):
        BOOTSTRAP.validate_path_preregistration(
            preregistration,
            campaign_dir=campaign,
        )


def test_bootstrap_source_set_excludes_retired_disposable_drill_modules() -> None:
    assert "disposable_drill_authority_v1" not in BOOTSTRAP.SCRIPT_TOOL_FILES
    assert "disposable_drill_payload_v1" not in BOOTSTRAP.SCRIPT_TOOL_FILES


def test_gate_a_receipt_schema_and_candidate_no_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    gate_a_before = fixture["gate_a"].read_bytes()
    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="already exists",
    ):
        BOOTSTRAP.build_gate_a_candidate(
            output_path=fixture["candidate_path"],
            gate_a_receipt=fixture["gate_a"],
            repository_root=ROOT,
            target_campaign_dir=fixture["campaign"],
            strict_input_paths=fixture["strict"],
            system_tool_paths=fixture["system"],
            created_at_utc="2026-07-24T12:57:00Z",
        )
    assert fixture["gate_a"].read_bytes() == gate_a_before
    assert not fixture["campaign"].exists()

    value = AUTH.strict_loads(gate_a_before, "Gate-A")
    value["unexpected"] = False
    fixture["gate_a"].write_bytes(AUTH.canonical_json(value))
    fresh_candidate = tmp_path / "offline-a002" / "candidate-a002.json"
    fresh_candidate.parent.mkdir()
    with pytest.raises(BOOTSTRAP.BootstrapError, match="key set drifted"):
        BOOTSTRAP.build_gate_a_candidate(
            output_path=fresh_candidate,
            gate_a_receipt=fixture["gate_a"],
            repository_root=ROOT,
            target_campaign_dir=fixture["campaign"],
            strict_input_paths=fixture["strict"],
            system_tool_paths=fixture["system"],
        )
    assert not fresh_candidate.exists()
    assert not fixture["campaign"].exists()


def test_gate_b_creates_complete_v4_root_and_seals_full_source_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _complete_fixture(tmp_path, monkeypatch)
    gate_a_before = fixture["gate_a"].read_bytes()
    gate_b_before = fixture["gate_b"].read_bytes()
    candidate_before = fixture["candidate_path"].read_bytes()
    result = _bootstrap(fixture)
    campaign = fixture["campaign"]
    root_snapshot = AUTH.snapshot_regular(campaign / "campaign-root.json")
    root = AUTH.validate_campaign_root(
        AUTH.strict_loads(root_snapshot.data, "campaign root"),
        campaign_dir=campaign,
    )
    assert result["status"] == ("FORMAL_CAMPAIGN_AUTHORITY_READY_NO_UNIT_LAUNCHED")
    assert result["formal_arm_launch_authorized"] is False
    assert result["organic_ab16_authorized"] is False
    assert fixture["gate_a"].read_bytes() == gate_a_before
    assert fixture["gate_b"].read_bytes() == gate_b_before
    assert fixture["candidate_path"].read_bytes() == candidate_before
    assert set(root["stage_topology"]) == {
        "gate1_v4",
        "prospective_ab16",
    }
    gate = root["stage_topology"]["gate1_v4"]
    assert set(gate["units"]) == set(AUTH.GATE1_SLOTS)
    assert Path(gate["continuation_path"]).parent == campaign / "gate1-v4"
    positive = gate["positive_control"]
    assert Path(positive["common_manifest_path"]).parent.name == ("common-prestate")
    assert set(positive["binding_paths"]) == {"control", "treatment"}
    prospective = root["stage_topology"]["prospective_ab16"]
    assert len(prospective["arms"]) == 16

    selection_path = Path(gate["selection_path"])
    assert selection_path.is_file()
    for reserved in AUTH.reserved_child_paths(root):
        if reserved != selection_path:
            assert not reserved.exists()
            assert not reserved.is_symlink()

    package_dir = Path(root["package"]["package_dir"])
    package_manifest = AUTH.strict_loads(
        (package_dir / "package-manifest.json").read_bytes(),
        "package manifest",
    )
    roles = {record["role"] for record in package_manifest["external_sources"]}
    expected_scripts = {
        "campaign_authority_v4.py",
        *(f"tool.{role}.py" for role in BOOTSTRAP.SCRIPT_TOOL_FILES if role != "campaign_authority_v4"),
    }
    expected_inputs = {
        "input.candidate_placements.json",
        "input.canonical_rules.json",
        "input.cuts_mandatory_schedule.txt",
        "input.history_freeze_manifest.json",
        "input.legacy_control_a002.json",
        "input.mandatory_instances.json",
        "input.project_lock.txt",
        *BOOTSTRAP.GATE_INPUT_ROLES.values(),
        BOOTSTRAP.CAPTURE_PACKAGE_ROLE,
        BOOTSTRAP.PATH_PREREGISTRATION_PACKAGE_ROLE,
    }
    expected_system = {f"system.{role}.bin" for role in BOOTSTRAP.SYSTEM_TOOL_ROLES}
    assert roles == expected_scripts | expected_inputs | expected_system
    assert set(BOOTSTRAP.AB16_SCRIPT_TOOL_FILES) <= set(root["authority_tools"])
    assert {
        *AUTH.REQUIRED_GATE1_INPUT_ROLES,
        "legacy_control_a002",
        *BOOTSTRAP.GATE_INPUT_ROLES,
        BOOTSTRAP.CAPTURE_INPUT_ROLE,
        BOOTSTRAP.PATH_PREREGISTRATION_INPUT_ROLE,
    } <= set(root["strict_inputs"])
    preregistration_copy = Path(root["strict_inputs"][BOOTSTRAP.PATH_PREREGISTRATION_INPUT_ROLE]["path"])
    preregistration = AUTH.strict_loads(
        preregistration_copy.read_bytes(),
        "package-pinned AB16 path preregistration",
    )
    assert preregistration["manifest_path"] == prospective["manifest_path"]
    assert preregistration["suite_selection_path"] == prospective["arm_selection_path"]
    assert preregistration["slot_roots"] == {arm["slot"]: arm["attempt_dir"] for arm in prospective["arms"]}
    assert preregistration["classification_contract_path"] == str(package_dir / "payload" / "tool.ab16_contract_v1.py")
    wrong_root = copy.deepcopy(root)
    wrong_root["stage_topology"]["prospective_ab16"]["arms"][0]["attempt_dir"] += "-wrong"
    with pytest.raises(BOOTSTRAP.BootstrapError, match="differs from v4 root"):
        BOOTSTRAP._validate_path_preregistration_against_root(  # noqa: SLF001
            preregistration,
            wrong_root,
            campaign_dir=fixture["campaign"],
        )
    assert (
        AUTH.verify_package(
            package_dir,
            expected_manager_epoch=root["manager_epoch"],
            replay_external=True,
        )["status"]
        == "PASS"
    )


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        ("not_authorized", "does not authorize"),
        ("same_approval_id", "byte binding"),
        ("wrong_candidate", "byte binding"),
    ),
)
def test_gate_b_mutations_fail_before_campaign_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    match: str,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    gate_b = _gate_b(
        tmp_path,
        campaign=fixture["campaign"],
        gate_a=fixture["gate_a"],
        candidate=fixture["candidate_path"],
        planned_digest=fixture["planned"]["planned_source_set_digest"],
        approval_id=("gate-a-fixture-pass" if mutation == "same_approval_id" else "gate-b-fixture-approval"),
        formal_authorized=mutation != "not_authorized",
    )
    if mutation == "wrong_candidate":
        value = AUTH.strict_loads(gate_b.read_bytes(), "Gate-B")
        wrong = _json(tmp_path / "offline" / "wrong.json", {"wrong": True})
        value["candidate_identity"] = _detached(wrong)
        gate_b.write_bytes(AUTH.canonical_json(value))
    fixture["gate_b"] = gate_b
    monkeypatch.setattr(
        BOOTSTRAP,
        "_capture_epoch",
        lambda **_: pytest.fail("capture must not run before Gate-B admission"),
    )
    with pytest.raises(BOOTSTRAP.BootstrapError, match=match):
        _bootstrap(fixture)
    assert not fixture["campaign"].exists()


def test_source_drift_after_gate_a_fails_before_live_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    gate_b = _gate_b(
        tmp_path,
        campaign=fixture["campaign"],
        gate_a=fixture["gate_a"],
        candidate=fixture["candidate_path"],
        planned_digest=fixture["planned"]["planned_source_set_digest"],
    )
    fixture["gate_b"] = gate_b
    fixture["strict"]["mandatory_instances"].write_bytes(AUTH.canonical_json({"drifted": True}))
    monkeypatch.setattr(
        BOOTSTRAP,
        "_capture_epoch",
        lambda **_: pytest.fail("capture must not run after source drift"),
    )
    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="planned package source bytes drifted",
    ):
        _bootstrap(fixture)
    assert not fixture["campaign"].exists()


def test_path_preregistration_drift_fails_before_live_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    fixture["gate_b"] = _gate_b(
        tmp_path,
        campaign=fixture["campaign"],
        gate_a=fixture["gate_a"],
        candidate=fixture["candidate_path"],
        planned_digest=fixture["planned"]["planned_source_set_digest"],
    )
    preregistration = AUTH.strict_loads(
        fixture["path_preregistration_path"].read_bytes(),
        "AB16 path preregistration",
    )
    preregistration["common_prestate_path"] = str(fixture["campaign"] / "prospective-ab16" / "wrong.json")
    fixture["path_preregistration_path"].write_bytes(AUTH.canonical_json(preregistration))
    monkeypatch.setattr(
        BOOTSTRAP,
        "_capture_epoch",
        lambda **_: pytest.fail("capture must not run after preregistration drift"),
    )
    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="preregistration identity drifted",
    ):
        _bootstrap(fixture)
    assert not fixture["campaign"].exists()


def test_gate_b_extra_field_fails_before_live_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    gate_b = _gate_b(
        tmp_path,
        campaign=fixture["campaign"],
        gate_a=fixture["gate_a"],
        candidate=fixture["candidate_path"],
        planned_digest=fixture["planned"]["planned_source_set_digest"],
    )
    value = AUTH.strict_loads(gate_b.read_bytes(), "Gate-B")
    value["unexpected"] = False
    gate_b.write_bytes(AUTH.canonical_json(value))
    fixture["gate_b"] = gate_b
    monkeypatch.setattr(
        BOOTSTRAP,
        "_capture_epoch",
        lambda **_: pytest.fail("capture must not run after schema drift"),
    )
    with pytest.raises(BOOTSTRAP.BootstrapError, match="key set drifted"):
        _bootstrap(fixture)
    assert not fixture["campaign"].exists()


def test_manager_toolchain_mismatch_fails_before_campaign_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    fixture["gate_b"] = _gate_b(
        tmp_path,
        campaign=fixture["campaign"],
        gate_a=fixture["gate_a"],
        candidate=fixture["candidate_path"],
        planned_digest=fixture["planned"]["planned_source_set_digest"],
    )
    other_system = {
        role: _write(
            tmp_path / "other-system" / role,
            f"other executable {role}\n".encode(),
        )
        for role in sorted(BOOTSTRAP.SYSTEM_TOOL_ROLES)
    }
    mismatched_capture = _capture_result(tmp_path / "other", other_system)
    monkeypatch.setattr(
        BOOTSTRAP,
        "_capture_epoch",
        lambda **_: copy.deepcopy(mismatched_capture),
    )
    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="does not match selected bytes",
    ):
        _bootstrap(fixture)
    assert not fixture["campaign"].exists()


@pytest.mark.parametrize("command", ("candidate", "bootstrap"))
def test_cli_has_distinct_executable_gate_a_and_gate_b_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
    command: str,
) -> None:
    called: dict[str, object] = {}

    def candidate_call(**kwargs: object) -> dict[str, object]:
        called.update(kwargs)
        return {"status": "CANDIDATE_FIXTURE"}

    def bootstrap_call(**kwargs: object) -> dict[str, object]:
        called.update(kwargs)
        return {"status": "BOOTSTRAP_FIXTURE"}

    monkeypatch.setattr(
        BOOTSTRAP,
        "_production_strict_inputs",
        lambda *_: {},
    )
    monkeypatch.setattr(BOOTSTRAP, "_cli_system_tools", lambda *_: {})
    monkeypatch.setattr(
        BOOTSTRAP,
        "build_gate_a_candidate",
        candidate_call,
    )
    monkeypatch.setattr(BOOTSTRAP, "bootstrap_campaign", bootstrap_call)
    base = [
        command,
        "--campaign-dir",
        str(tmp_path / "campaigns" / "run-fixture-cli"),
        "--repository-root",
        str(ROOT),
        "--gate-a-receipt",
        str(tmp_path / "gate-a.json"),
        "--history-freeze-manifest",
        str(tmp_path / "history.json"),
        "--cuts-mandatory-schedule",
        str(tmp_path / "schedule.md"),
        "--legacy-control-a002",
        str(tmp_path / "legacy.json"),
    ]
    if command == "candidate":
        base.extend(
            [
                "--candidate-output",
                str(tmp_path / "candidate.json"),
            ]
        )
    else:
        base.extend(
            [
                "--offline-candidate",
                str(tmp_path / "candidate.json"),
                "--gate-b-approval",
                str(tmp_path / "gate-b.json"),
            ]
        )
    assert BOOTSTRAP.main(base) == 0
    output = AUTH.strict_loads(capsysbinary.readouterr().out, "CLI output")
    if command == "candidate":
        assert output["status"] == "CANDIDATE_FIXTURE"
        assert "gate_b_approval" not in called
        assert called["output_path"] == tmp_path / "candidate.json"
    else:
        assert output["status"] == "BOOTSTRAP_FIXTURE"
        assert called["gate_b_approval"] == tmp_path / "gate-b.json"


def test_source_switch_between_admission_and_package_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _complete_fixture(tmp_path, monkeypatch)
    original_build_package = AUTH.build_package

    def switched_build_package(*args: object, **kwargs: object) -> object:
        fixture["strict"]["mandatory_instances"].write_bytes(AUTH.canonical_json({"late_switch": True}))
        return original_build_package(*args, **kwargs)

    monkeypatch.setattr(AUTH, "build_package", switched_build_package)
    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="package source changed after Gate A",
    ):
        _bootstrap(fixture)
    assert fixture["campaign"].is_dir()
    assert not (fixture["campaign"] / "campaign-root.json").exists()


def test_no_overwrite_fails_before_second_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _complete_fixture(tmp_path, monkeypatch)
    _bootstrap(fixture)
    monkeypatch.setattr(
        BOOTSTRAP,
        "_capture_epoch",
        lambda **_: pytest.fail("no-overwrite must stop before capture"),
    )
    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="already exists",
    ):
        _bootstrap(fixture)


def test_candidate_source_digest_mutation_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    value = AUTH.strict_loads(
        fixture["candidate_path"].read_bytes(),
        "candidate",
    )
    value["planned_source_set_digest"] = "0" * 64
    value["candidate_id"] = BOOTSTRAP._digest_without(  # noqa: SLF001
        value,
        "candidate_id",
    )
    fixture["candidate_path"].write_bytes(AUTH.canonical_json(value))
    fixture["gate_b"] = _gate_b(
        tmp_path,
        campaign=fixture["campaign"],
        gate_a=fixture["gate_a"],
        candidate=fixture["candidate_path"],
        planned_digest=fixture["planned"]["planned_source_set_digest"],
    )
    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="offline candidate semantics drifted",
    ):
        _bootstrap(fixture)
    assert not fixture["campaign"].exists()
