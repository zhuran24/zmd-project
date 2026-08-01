from __future__ import annotations

import ast
import base64
import copy
import hashlib
import importlib.util
import json
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
NATIVE_HELPER = AB16_RESEARCH / "ab16_native_budget_helper_x86_64_v1.so"
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
BOOTSTRAP_V2 = _load(
    "noncert_cuts_ab16_campaign_bootstrap_v2_strict_tested",
    AB16_RESEARCH / "ab16_campaign_bootstrap_v2.py",
)
AUTH_V2 = _load(
    "noncert_cuts_ab16_authority_v2_strict_tested",
    AB16_RESEARCH / "ab16_authority_v2.py",
)


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


def _native_helper_full() -> dict[str, object]:
    return BOOTSTRAP_V2.authority.snapshot_tool(NATIVE_HELPER)[1]


def _git_fixture(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    source = Path(shutil.which("git") or "").resolve(strict=True)
    target = tmp_path / "system" / "git-real"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target, AUTH.snapshot_tool(target)[1]


def test_v2_campaign_root_retains_repository_local_external_input_identities(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    internal = _write(repository / "rules/strict.json", b"strict\n")
    history = _write(repository / ".artifacts/history/manifest.json", b"history\n")
    legacy = _write(repository / ".artifacts/legacy/result.json", b"legacy\n")
    packaged_internal = _write(tmp_path / "package/internal.json", internal.read_bytes())
    packaged_history = _write(tmp_path / "package/history.json", history.read_bytes())
    packaged_legacy = _write(tmp_path / "package/legacy.json", legacy.read_bytes())
    materialized_internal = _write(
        tmp_path / "snapshot/rules/strict.json",
        internal.read_bytes(),
    )
    planned = {
        "input.canonical_rules": AUTH_V2.full_identity(
            AUTH_V2.snapshot_regular(internal)
        ),
        "input.history_freeze_manifest": AUTH_V2.full_identity(
            AUTH_V2.snapshot_regular(history)
        ),
        "input.legacy_control_a002": AUTH_V2.full_identity(
            AUTH_V2.snapshot_regular(legacy)
        ),
    }
    packaged = {
        "canonical_rules": AUTH_V2.detached_identity(
            AUTH_V2.snapshot_regular(packaged_internal)
        ),
        "history_freeze_manifest": AUTH_V2.detached_identity(
            AUTH_V2.snapshot_regular(packaged_history)
        ),
        "legacy_control_a002": AUTH_V2.detached_identity(
            AUTH_V2.snapshot_regular(packaged_legacy)
        ),
    }
    snapshot = {
        "rules/strict.json": AUTH_V2.detached_identity(
            AUTH_V2.snapshot_regular(materialized_internal)
        ),
    }

    selected = BOOTSTRAP_V2._select_root_strict_input_identities(  # noqa: SLF001
        repository=repository,
        strict_paths={
            "canonical_rules": internal,
            "history_freeze_manifest": history,
            "legacy_control_a002": legacy,
        },
        planned=planned,
        packaged_inputs=packaged,
        snapshot_identities=snapshot,
    )

    assert selected["canonical_rules"] == snapshot["rules/strict.json"]
    assert selected["history_freeze_manifest"] == (
        BOOTSTRAP_V2._detached_from_full(  # noqa: SLF001
            planned["input.history_freeze_manifest"]
        )
    )
    assert (
        selected["history_freeze_manifest"]["path"] == str(history)
        != packaged["history_freeze_manifest"]["path"]
    )
    assert selected["legacy_control_a002"] == packaged["legacy_control_a002"]

    bad_packaged = copy.deepcopy(packaged)
    bad_packaged["history_freeze_manifest"]["sha256"] = "0" * 64
    with pytest.raises(
        BOOTSTRAP_V2.BootstrapError,
        match="packaged history-freeze manifest differs",
    ):
        BOOTSTRAP_V2._select_root_strict_input_identities(  # noqa: SLF001
            repository=repository,
            strict_paths={"history_freeze_manifest": history},
            planned=planned,
            packaged_inputs=bad_packaged,
            snapshot_identities=snapshot,
        )


def test_v2_repository_snapshot_stages_repository_local_external_inputs_by_role(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert BOOTSTRAP_V2.EXTERNAL_STRICT_INPUT_ROLES == {
        "history_freeze_manifest",
        "legacy_control_a002",
    }
    repository = tmp_path / "repository"
    repository.mkdir()
    candidate = _write(repository / "candidate.json", b"candidate\n")
    history = _write(repository / ".artifacts/history/manifest.json", b"history\n")
    legacy = _write(repository / ".artifacts/legacy/result.json", b"legacy\n")
    strict_paths = {
        "candidate_placements": candidate,
        "history_freeze_manifest": history,
        "legacy_control_a002": legacy,
    }
    planned = {
        f"input.{role}": BOOTSTRAP_V2.authority.full_identity(
            BOOTSTRAP_V2.authority.snapshot_regular(path)
        )
        for role, path in strict_paths.items()
    }
    monkeypatch.setattr(
        BOOTSTRAP_V2,
        "_head_repository_blobs",
        lambda _repository, _head: ("0" * 40, [], {}),
    )
    monkeypatch.setattr(
        BOOTSTRAP_V2,
        "_external_platform_record",
        lambda **_kwargs: {},
    )
    bootstrap_dir = tmp_path / "bootstrap"
    bootstrap_dir.mkdir()

    result = BOOTSTRAP_V2._build_repository_snapshot_sources(  # noqa: SLF001
        bootstrap_dir=bootstrap_dir,
        package_dir=tmp_path / "package",
        repository=repository,
        repository_head="1" * 40,
        planned=planned,
        scripts={},
        strict_paths=strict_paths,
        system_full={
            "native_budget_helper": _native_helper_full(),
            "python3_13": {},
        },
    )

    assert result["staged_inputs"]["history_freeze_manifest"].read_bytes() == b"history\n"
    assert result["staged_inputs"]["legacy_control_a002"].read_bytes() == b"legacy\n"

    escaped = _write(tmp_path / "outside/canonical-rules.json", b"rules\n")
    escaped_strict_paths = {
        "candidate_placements": candidate,
        "canonical_rules": escaped,
    }
    escaped_planned = {
        f"input.{role}": BOOTSTRAP_V2.authority.full_identity(
            BOOTSTRAP_V2.authority.snapshot_regular(path)
        )
        for role, path in escaped_strict_paths.items()
    }
    escaped_bootstrap_dir = tmp_path / "escaped-bootstrap"
    escaped_bootstrap_dir.mkdir()
    with pytest.raises(
        BOOTSTRAP_V2.BootstrapError,
        match="repository strict input escaped the fixed tree: canonical_rules",
    ):
        BOOTSTRAP_V2._build_repository_snapshot_sources(  # noqa: SLF001
            bootstrap_dir=escaped_bootstrap_dir,
            package_dir=tmp_path / "escaped-package",
            repository=repository,
            repository_head="1" * 40,
            planned=escaped_planned,
            scripts={},
            strict_paths=escaped_strict_paths,
            system_full={
                "native_budget_helper": _native_helper_full(),
                "python3_13": {},
            },
        )


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
    assert len(path_preregistration["attempt_dirs"]) == 16
    assert set(path_preregistration["attempt_dirs"]) == {
        f"{configuration}-{order}-{arm}"
        for configuration in AUTH.AB16_CONFIGURATIONS
        for order in AUTH.AB16_ORDERS
        for arm in AUTH.AB16_ARMS
    }
    assert Path(path_preregistration["baseline_rebuilt_model_path"]).name == "cut-free-model.bin"
    assert Path(path_preregistration["baseline_rebuilt_metadata_path"]).name == "rebuilt-model-metadata.json"
    assert Path(path_preregistration["baseline_incumbent_path"]).name == ("incumbent.json")


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
    assert preregistration["attempt_dirs"] == {arm["slot"]: arm["attempt_dir"] for arm in prospective["arms"]}
    assert preregistration["classification_contract_path"] == str(package_dir / "payload" / "tool.ab16_contract_v1.py")
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


def test_v2_path_preregistration_closes_formal_outer_and_arm_paths(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaigns" / "run-path-prereg-v3"
    campaign.parent.mkdir()
    budget_binding = {
        label: {
            "path": str(campaign / f"{label}.json"),
            "sha256": character * 64,
            "size_bytes": 1,
        }
        for label, character in (
            ("bootstrap_budget_contract_identity", "1"),
            ("formal_root_budget_contract_identity", "2"),
            ("resource_budget_profile_identity", "3"),
        )
    }
    budget_binding["resource_calibration_bundle_identities"] = {
        stage: {
            "path": str(campaign / f"resource-calibration-{index}.json"),
            "sha256": str(index + 3) * 64,
            "size_bytes": index,
        }
        for index, stage in enumerate(
            BOOTSTRAP_V2.RESOURCE_CALIBRATION_STAGES,
            start=1,
        )
    }
    record = BOOTSTRAP_V2._path_preregistration(  # noqa: SLF001
        campaign,
        budget_binding=budget_binding,
    )
    assert BOOTSTRAP_V2.validate_path_preregistration(
        record,
        campaign_dir=campaign,
        budget_binding=budget_binding,
    ) == record
    assert record["schema"] == "noncert-cuts-ab16-path-preregistration-v5"
    assert record["package_independent_replay_path"] == str(
        campaign / "bootstrap-authority/package-independent-replay.json"
    )
    assert record["package_independent_replay_staging_path"] == str(
        campaign
        / "bootstrap-authority/.package-independent-replay.json.staged"
    )
    assert record["formal_admission_path"] == str(
        campaign
        / "formal-ab16/artifacts/formal-launch-admission-a001.json"
    )
    assert record["formal_attempt_dir"] == str(
        campaign / "formal-ab16/artifacts/formal-attempt-a001"
    )
    assert record["formal_selection_path"] == str(
        campaign
        / "formal-ab16/artifacts/formal-attempt-a001/selection.json"
    )
    assert record["gate1_prelaunch_ownership_path"] == str(
        campaign
        / "formal-ab16/artifacts/formal-attempt-a001/"
        "gate1-prelaunch-ownership.json"
    )
    assert record["guardian_ready_path"] == str(
        campaign / "formal-ab16/artifacts/outer-guardian-ready-a001.json"
    )
    assert record["guardian_control_retired_socket_path"] == str(
        campaign
        / "formal-ab16/control/guardian-control.sock.retired"
    )
    assert record["outer_barrier_path"] == str(
        campaign
        / "formal-ab16/artifacts/formal-attempt-a001/"
        "outer-barrier-release.json"
    )
    assert set(record["outer_receipt_paths"]) == {
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
        "reference_connection_close",
        "reference_release",
        "reference_terminal",
        "supervisor_raw_lock_release",
    }
    assert len(record["arm_prelaunch_paths"]) == 16
    assert all(
        set(value) == {"receipt", "request"}
        for value in record["arm_prelaunch_paths"].values()
    )

    missing = copy.deepcopy(record)
    missing.pop("formal_selection_path")
    extra = copy.deepcopy(record)
    extra["future_authority_path"] = str(campaign / "forbidden.json")
    drifted = copy.deepcopy(record)
    drifted["outer_barrier_path"] = str(campaign / "wrong.json")
    for changed in (missing, extra, drifted):
        with pytest.raises(BOOTSTRAP_V2.BootstrapError):
            BOOTSTRAP_V2.validate_path_preregistration(
                changed,
                campaign_dir=campaign,
                budget_binding=budget_binding,
            )


def test_v2_package_role_set_is_exact_and_has_one_owner(
    tmp_path: Path,
) -> None:
    scripts = {
        role: tmp_path / "scripts" / filename
        for role, filename in BOOTSTRAP_V2.SCRIPT_TOOL_FILES.items()
    }
    systems = {
        role: tmp_path / "system" / role
        for role in BOOTSTRAP_V2.SYSTEM_TOOL_ROLES
    }
    strict = {
        role: tmp_path / "inputs" / role
        for role in BOOTSTRAP_V2.STRICT_INPUT_ROLES
    }
    resource_calibration_bundle_paths = {
        stage: tmp_path / "resource-calibration" / f"{stage}.json"
        for stage in BOOTSTRAP_V2.RESOURCE_CALIBRATION_STAGES
    }
    specs, script_roles, input_roles = BOOTSTRAP_V2._package_roles(  # noqa: SLF001
        scripts=scripts,
        system_paths=systems,
        strict_paths=strict,
        resource_calibration_bundle_paths=resource_calibration_bundle_paths,
        gate_a_path=tmp_path / "gate-a.json",
        candidate_path=tmp_path / "candidate.json",
        gate_b_path=tmp_path / "gate-b.json",
        gate_b_epoch_path=tmp_path / "gate-b-epoch.json",
        final_full_preflight_path=tmp_path / "final-full.json",
        pre_full_resource_gate_path=tmp_path / "pre-full-resource-gate.json",
        pre_publication_resource_gate_path=(
            tmp_path / "pre-publication-resource-gate.json"
        ),
        capture_path=tmp_path / "manager-capture.json",
        path_preregistration_path=tmp_path / "path-preregistration.json",
        snapshot_archive_path=tmp_path / "repository-snapshot.zip",
        snapshot_manifest_path=tmp_path / "repository-snapshot.json",
        external_platform_path=tmp_path / "external-platform.json",
        resource_budget_profile_path=tmp_path / "resource-budget-profile.json",
    )
    roles = [spec.role for spec in specs]
    assert len(roles) == len(set(roles))
    assert set(roles) == set(AUTH_V2.REQUIRED_PACKAGE_ROLES)
    assert set(script_roles) == set(BOOTSTRAP_V2.SCRIPT_TOOL_FILES)
    assert set(input_roles) == {
        *BOOTSTRAP_V2.STRICT_INPUT_ROLES,
        *BOOTSTRAP_V2.GATE_INPUT_ROLES,
        BOOTSTRAP_V2.CAPTURE_INPUT_ROLE,
        BOOTSTRAP_V2.PATH_PREREGISTRATION_INPUT_ROLE,
        BOOTSTRAP_V2.SNAPSHOT_ARCHIVE_INPUT_ROLE,
        BOOTSTRAP_V2.SNAPSHOT_MANIFEST_INPUT_ROLE,
        BOOTSTRAP_V2.EXTERNAL_PLATFORM_INPUT_ROLE,
        BOOTSTRAP_V2.RESOURCE_BUDGET_PROFILE_INPUT_ROLE,
        *BOOTSTRAP_V2.RESOURCE_CALIBRATION_INPUT_ROLES.values(),
    }


def test_v2_native_helper_path_mode_sha_and_arch_are_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ordinary_tool = Path(os.path.realpath(sys.executable))
    valid_paths = {
        role: ordinary_tool
        for role in BOOTSTRAP_V2.SYSTEM_TOOL_ROLES
    }
    valid_paths["native_budget_helper"] = NATIVE_HELPER
    _resolved, identities = BOOTSTRAP_V2._resolved_system_tools(  # noqa: SLF001
        valid_paths
    )
    assert identities["native_budget_helper"] == _native_helper_full()

    missing = dict(valid_paths)
    missing.pop("native_budget_helper")
    with pytest.raises(
        BOOTSTRAP_V2.BootstrapError,
        match="exact pre-registered roles",
    ):
        BOOTSTRAP_V2._resolved_system_tools(missing)  # noqa: SLF001

    wrong_mode = tmp_path / "native-wrong-mode.so"
    shutil.copy2(NATIVE_HELPER, wrong_mode)
    wrong_mode.chmod(0o444)
    mode_paths = dict(valid_paths)
    mode_paths["native_budget_helper"] = wrong_mode
    with pytest.raises(BOOTSTRAP_V2.BootstrapError):
        BOOTSTRAP_V2._resolved_system_tools(mode_paths)  # noqa: SLF001

    wrong_sha = tmp_path / "native-wrong-sha.so"
    wrong_raw = bytearray(NATIVE_HELPER.read_bytes())
    wrong_raw[-1] ^= 1
    wrong_sha.write_bytes(wrong_raw)
    wrong_sha.chmod(0o555)
    sha_paths = dict(valid_paths)
    sha_paths["native_budget_helper"] = wrong_sha
    with pytest.raises(
        BOOTSTRAP_V2.BootstrapError,
        match="fixed byte identity drifted",
    ):
        BOOTSTRAP_V2._resolved_system_tools(sha_paths)  # noqa: SLF001

    wrong_arch = bytearray(NATIVE_HELPER.read_bytes())
    wrong_arch[18:20] = (183).to_bytes(2, "little")  # EM_AARCH64
    wrong_arch_digest = hashlib.sha256(wrong_arch).hexdigest()
    monkeypatch.setattr(
        BOOTSTRAP_V2,
        "NATIVE_BUDGET_HELPER_SHA256",
        wrong_arch_digest,
    )
    with pytest.raises(
        BOOTSTRAP_V2.BootstrapError,
        match="ELF identity drifted",
    ):
        BOOTSTRAP_V2._native_helper_elf_capability(  # noqa: SLF001
            bytes(wrong_arch),
            source_identity={
                "mode": 0o555,
                "sha256": wrong_arch_digest,
                "size_bytes": len(wrong_arch),
            },
        )


def test_v2_candidate_cli_requires_explicit_native_helper_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as captured:
        BOOTSTRAP_V2._parse_args(  # noqa: SLF001
            [
                "candidate",
                "--campaign-dir",
                "/fixture/campaign",
                "--repository-root",
                "/fixture/repository",
                "--gate-a-receipt",
                "/fixture/gate-a.json",
                "--history-freeze-manifest",
                "/fixture/history.json",
                "--cuts-mandatory-schedule",
                "/fixture/schedule.md",
                "--legacy-control-a002",
                "/fixture/control.json",
                "--candidate-output",
                "/fixture/candidate.json",
            ]
        )
    assert captured.value.code == 2
    assert "--native-budget-helper" in capsys.readouterr().err


def test_v2_authority_loads_resource_replayer_only_from_sealed_package(
    tmp_path: Path,
) -> None:
    raw = (AB16_RESEARCH / "ab16_resource_admission_v1.py").read_bytes()
    packaged_path = _write(tmp_path / "sealed" / "payload" / "resource.py", raw)
    packaged_path.chmod(0o444)
    packaged = AUTH_V2.snapshot_regular(packaged_path)
    absent_live_path = tmp_path / "live-source-must-not-be-opened.py"
    source_identity = {
        "mode": 0o444,
        "path": str(absent_live_path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }
    role = "tool.ab16_resource_admission_v1.py"
    ambient_name = "ab16_resource_admission_v1"
    previous_ambient = sys.modules.get(ambient_name)
    ambient = ModuleType(ambient_name)
    sys.modules[ambient_name] = ambient
    try:
        module, module_name = AUTH_V2._load_packaged_resource_admission_replayer(  # noqa: SLF001
            {"payload/resource.py": packaged},
            {
                role: {
                    "package_path": "payload/resource.py",
                    "parse_json": False,
                    "role": role,
                    "source_identity": source_identity,
                }
            },
            expected_source=source_identity,
        )
        try:
            assert module is not ambient
            assert module.__file__ == str(packaged_path)
            assert module.FULL_PREFLIGHT == "FULL_PREFLIGHT"
            assert not absent_live_path.exists()
        finally:
            assert sys.modules.pop(module_name) is module
    finally:
        if previous_ambient is None:
            assert sys.modules.pop(ambient_name) is ambient
        else:
            sys.modules[ambient_name] = previous_ambient


def test_v2_authority_replays_full_and_gate_b_resource_closure(
    tmp_path: Path,
) -> None:
    raw = (AB16_RESEARCH / "ab16_resource_admission_v1.py").read_bytes()
    packaged_path = _write(tmp_path / "sealed" / "payload" / "resource.py", raw)
    packaged_path.chmod(0o444)
    packaged = AUTH_V2.snapshot_regular(packaged_path)
    source_identity = {
        "mode": 0o444,
        "path": str(tmp_path / "absent-live-resource.py"),
        "sha256": packaged.sha256,
        "size_bytes": packaged.size_bytes,
    }
    role = "tool.ab16_resource_admission_v1.py"
    resource, module_name = AUTH_V2._load_packaged_resource_admission_replayer(  # noqa: SLF001
        {"payload/resource.py": packaged},
        {
            role: {
                "package_path": "payload/resource.py",
                "parse_json": False,
                "role": role,
                "source_identity": source_identity,
            }
        },
        expected_source=source_identity,
    )
    locks = [
        {
            "device": 1,
            "inode": 100 + ordinal,
            "mode": 0o600,
            "nlink": 1,
            "path": path,
            "uid": os.geteuid(),
        }
        for ordinal, path in enumerate(resource.LOCK_PATHS)
    ]
    abundant = {"MemAvailable": 1 << 50, "SwapFree": 1 << 50}
    try:
        repository = tmp_path / "repository"
        repository.mkdir()
        receipt_directory = tmp_path / "gate-a-full"
        receipt_directory.mkdir()
        full_context = {
            "authority_id": "a" * 64,
            "disk_path": str(repository),
            "kind": "GATE_A_FULL_PREFLIGHT",
            "ordinal": 0,
            "scope_id": "b" * 64,
            "sequence": 1,
            "slot": "",
            "target": str(receipt_directory),
        }
        full_admission = resource.evaluate_resource_admission(
            repository,
            stage=resource.FULL_PREFLIGHT,
            lock_identities=locks,
            lock_identity_format=resource.GATE_B_LOCK_IDENTITY_FORMAT,
            observation_context=full_context,
            meminfo=abundant,
            disk_free=1 << 50,
            conflicts=[],
            observed_at_utc="2026-07-31T00:00:00Z",
        )
        AUTH_V2._validate_preflight_resource_admission(  # noqa: SLF001
            {
                "planned_source_set_digest": "b" * 64,
                "pre_run_authority_identity": {"sha256": "a" * 64},
                "repository_root": str(repository),
                "resource_admission": full_admission,
                "resource_admission_source_identity": source_identity,
                "resource_lock_release_identities": locks,
            },
            resource_replayer=resource,
            expected_source=source_identity,
            receipt_directory=receipt_directory,
            label="test full preflight",
        )

        qualification = tmp_path / "qualification"
        gate_b_directory = qualification / "gate-b-output"
        resource_directory = gate_b_directory / "resource-gates"
        resource_directory.mkdir(parents=True)
        session_id = "c" * 64
        actor = {
            "pid": 1234,
            "pid_starttime": "5678",
            "role": "AB16_GATE_B_OWNER",
        }
        stage = "BEFORE_FINAL_FULL_PREFLIGHT"
        gate_context = {
            "authority_id": session_id,
            "disk_path": str(qualification),
            "kind": "GATE_B_FINAL_FULL_PREFLIGHT",
            "ordinal": 0,
            "scope_id": session_id,
            "sequence": 1,
            "slot": "",
            "target": stage,
        }
        gate_admission = resource.evaluate_resource_admission(
            qualification,
            stage=resource.FULL_PREFLIGHT,
            lock_identities=locks,
            lock_identity_format=resource.GATE_B_LOCK_IDENTITY_FORMAT,
            observation_context=gate_context,
            meminfo=abundant,
            disk_free=1 << 50,
            conflicts=[],
            observed_at_utc="2026-07-31T00:00:01Z",
        )
        wrapper_path = resource_directory / "before-final-full-preflight.json"
        _write(
            wrapper_path,
            AUTH_V2.canonical_json(
                {
                    "admission": gate_admission,
                    "authorizations": dict(resource.FALSE_AUTHORIZATIONS),
                    "created_at_utc": "2026-07-31T00:00:02Z",
                    "lock_identities": locks,
                    "owner_actor": actor,
                    "qualification_session_id": session_id,
                    "schema_version": AUTH_V2.GATE_B_RESOURCE_GATE_SCHEMA,
                    "stage": stage,
                    "status": "PASS",
                }
            ),
        ).chmod(0o444)
        wrapper = AUTH_V2.snapshot_regular(wrapper_path)
        record, identity = AUTH_V2._validate_gate_b_resource_gate(  # noqa: SLF001
            wrapper,
            AUTH_V2._mode_identity(wrapper),  # noqa: SLF001
            resource_replayer=resource,
            expected_path=wrapper_path,
            expected_actor=actor,
            expected_session_id=session_id,
            expected_lock_identities=locks,
            expected_stage=stage,
            expected_profile_stage=resource.FULL_PREFLIGHT,
            expected_disk_path=qualification,
            expected_kind="GATE_B_FINAL_FULL_PREFLIGHT",
            expected_sequence=1,
        )
        assert record["admission"] == gate_admission
        assert identity == AUTH_V2._mode_identity(wrapper)  # noqa: SLF001
    finally:
        assert sys.modules.pop(module_name) is resource


def test_v2_bootstrap_seals_before_materializing_without_future_identity() -> None:
    source = (AB16_RESEARCH / "ab16_campaign_bootstrap_v2.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "bootstrap_campaign"
    )
    calls: dict[str, ast.Call] = {}
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        else:
            continue
        if name in {
            "_build_repository_snapshot_sources",
            "build_package",
            "_materialize_repository_snapshot",
            "build_campaign_root",
        }:
            assert name not in calls
            calls[name] = node
    assert set(calls) == {
        "_build_repository_snapshot_sources",
        "build_package",
        "_materialize_repository_snapshot",
        "build_campaign_root",
    }
    assert (
        calls["_build_repository_snapshot_sources"].lineno
        < calls["build_package"].lineno
        < calls["_materialize_repository_snapshot"].lineno
        < calls["build_campaign_root"].lineno
    )
    materialize_keywords = {
        keyword.arg: keyword.value
        for keyword in calls["_materialize_repository_snapshot"].keywords
    }
    package_id = materialize_keywords["package_id"]
    assert (
        isinstance(package_id, ast.Subscript)
        and isinstance(package_id.value, ast.Name)
        and package_id.value.id == "package"
        and isinstance(package_id.slice, ast.Constant)
        and package_id.slice.value == "package_id"
    )
    assert "package_id" not in {
        keyword.arg
        for keyword in calls["_build_repository_snapshot_sources"].keywords
    }
    assert "package_id" not in BOOTSTRAP_V2._build_repository_snapshot_sources.__annotations__  # noqa: SLF001


def test_v2_external_platform_freezes_prospective_fd_cohort_and_dual_holder_literals() -> None:
    python_path = Path(os.path.realpath(sys.executable))
    record = BOOTSTRAP_V2._external_platform_record(  # noqa: SLF001
        native_helper_identity=_native_helper_full(),
        repository_head=HEAD,
        python_identity=AUTH_V2.full_identity(
            AUTH_V2.snapshot_regular(python_path)
        ),
    )
    assert record["schema_version"] == (
        "noncert-cuts-ab16-external-platform-assumptions-v3"
    )
    assert record["dual_holder_survival"] == {
        "assumption_id": "AB16_DUAL_HOLDER_SURVIVAL_V1",
        "reboot_or_power_loss_during_heavy_runtime_excluded": True,
        "simultaneous_guardian_supervisor_death_excluded": True,
        "single_holder_death_must_be_contained": True,
    }
    assert record["selected_byte_launch"] == {
        "direct_fd_map": {
            "authority": 5,
            "budget_broker": 8,
            "loader": 4,
            "native_helper": 7,
            "native_helper_wrapper": 6,
            "python": 3,
        },
        "execution_strategy": "selected-byte-python-loader-budget-fd-v2",
        "literal_identity": BOOTSTRAP_V2._literal_identity(  # noqa: SLF001
            BOOTSTRAP_V2.SELECTED_BYTE_LAUNCH_V2
        ),
        "systemd_fd_map": {
            "authority": 5,
            "budget_broker": 8,
            "loader": 4,
            "native_helper": 7,
            "native_helper_wrapper": 6,
            "python": 3,
        },
        "systemd_fd_names": [
            "ab16-python",
            "ab16-loader",
            "ab16-authority",
            "ab16-native-helper-wrapper",
            "ab16-native-helper",
            "ab16-budget-broker",
        ],
    }
    assert (
        BOOTSTRAP_V2._literal_identity(  # noqa: SLF001
            BOOTSTRAP_V2.SELECTED_BYTE_LAUNCH_V1
        )
        == {
            "sha256": (
                "619b0906281cf0ebd3d9361c6b6468b0"
                "a0cc9cb66a46dc0c98b18c25d89e43ff"
            ),
            "size_bytes": 2531,
        }
    )
    assert record["formal_launch_owner_driver"] == (
        BOOTSTRAP_V2._literal_identity(  # noqa: SLF001
            BOOTSTRAP_V2.FORMAL_LAUNCH_OWNER_DRIVER_V2
        )
    )
    assert record["gate_b_owner_driver"] == (
        BOOTSTRAP_V2._literal_identity(  # noqa: SLF001
            BOOTSTRAP_V2.GATE_B_OWNER_DRIVER_V1
        )
    )
    assert record["mechanical_oexcl_publisher"] == (
        BOOTSTRAP_V2._literal_identity(  # noqa: SLF001
            BOOTSTRAP_V2.OWNER_OEXCL_PUBLISH_V1
        )
    )


def _gate_b_owner_driver_probe(
    tmp_path: Path,
    *,
    python_identity: dict[str, object],
    owner_source_identity: dict[str, object],
    python_fd_path: Path | None = None,
    owner_source_fd_path: Path | None = None,
    expected_argument: str | None = None,
) -> subprocess.CompletedProcess[str]:
    tmp_path.mkdir(parents=True)
    wrapper = """
import os
import sys

paths = sys.argv[2:4]
opened = [os.open(path, os.O_RDONLY) for path in paths]
if opened != [3, 4]:
    raise SystemExit(124)
for descriptor in opened:
    os.set_inheritable(descriptor, True)
clean = {
    "LANG": "C",
    "LC_ALL": "C",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONNOUSERSITE": "1",
    "TZ": "UTC",
}
os.execve(
    sys.argv[1],
    [
        sys.argv[1],
        "-B",
        "-c",
        sys.argv[5],
        sys.argv[4],
        "3",
        "4",
    ],
    clean,
)
"""
    canonical_expected = json.dumps(
        {
            "owner_source": owner_source_identity,
            "python": python_identity,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            wrapper,
            str(Path(os.path.realpath(sys.executable))),
            str(
                python_fd_path
                if python_fd_path is not None
                else Path(os.path.realpath(sys.executable))
            ),
            str(
                owner_source_fd_path
                if owner_source_fd_path is not None
                else AB16_RESEARCH / "ab16_gate_b_qualification_v1.py"
            ),
            expected_argument if expected_argument is not None else canonical_expected,
            BOOTSTRAP_V2.GATE_B_OWNER_DRIVER_V1,
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_gate_b_owner_driver_checks_python_and_owner_source_before_exec(
    tmp_path: Path,
) -> None:
    python_path = Path(os.path.realpath(sys.executable))
    owner_source_path = AB16_RESEARCH / "ab16_gate_b_qualification_v1.py"
    python_identity = BOOTSTRAP_V2._snapshot_mode_identity(python_path)  # noqa: SLF001
    owner_source_identity = BOOTSTRAP_V2._snapshot_mode_identity(owner_source_path)  # noqa: SLF001

    reached_renderer = _gate_b_owner_driver_probe(
        tmp_path / "valid",
        python_identity=python_identity,
        owner_source_identity=owner_source_identity,
    )
    assert reached_renderer.returncode != 125
    assert "usage:" in reached_renderer.stderr

    python_drift = dict(python_identity)
    python_drift["sha256"] = "f" * 64
    rejected_python = _gate_b_owner_driver_probe(
        tmp_path / "python-drift",
        python_identity=python_drift,
        owner_source_identity=owner_source_identity,
    )
    assert rejected_python.returncode == 125

    owner_source_drift = dict(owner_source_identity)
    owner_source_drift["size_bytes"] = int(owner_source_drift["size_bytes"]) + 1
    rejected_owner_source = _gate_b_owner_driver_probe(
        tmp_path / "owner-source-drift",
        python_identity=python_identity,
        owner_source_identity=owner_source_drift,
    )
    assert rejected_owner_source.returncode == 125

    copied_owner_source = tmp_path / "owner-source-path-mismatch/ab16_gate_b_qualification_v1.py"
    copied_owner_source.parent.mkdir(parents=True)
    shutil.copyfile(owner_source_path, copied_owner_source)
    copied_owner_source.chmod(owner_source_path.stat().st_mode & 0o7777)
    copied_owner_source_identity = BOOTSTRAP_V2._snapshot_mode_identity(  # noqa: SLF001
        copied_owner_source
    )
    rejected_owner_source_path = _gate_b_owner_driver_probe(
        tmp_path / "owner-source-path-mismatch-probe",
        python_identity=python_identity,
        owner_source_identity=copied_owner_source_identity,
        owner_source_fd_path=owner_source_path,
    )
    assert rejected_owner_source_path.returncode == 125

    copied_python = tmp_path / "runtime-mismatch/python3.13"
    copied_python.parent.mkdir(parents=True)
    shutil.copyfile(python_path, copied_python)
    copied_python.chmod(python_path.stat().st_mode & 0o7777)
    copied_identity = BOOTSTRAP_V2._snapshot_mode_identity(copied_python)  # noqa: SLF001
    rejected_runtime_mismatch = _gate_b_owner_driver_probe(
        tmp_path / "runtime-mismatch-probe",
        python_identity=copied_identity,
        owner_source_identity=owner_source_identity,
        python_fd_path=copied_python,
    )
    assert rejected_runtime_mismatch.returncode == 125


def test_gate_b_owner_driver_identity_argument_and_environment_are_closed(
    tmp_path: Path,
) -> None:
    python_path = Path(os.path.realpath(sys.executable))
    owner_source_path = AB16_RESEARCH / "ab16_gate_b_qualification_v1.py"
    python_identity = BOOTSTRAP_V2._snapshot_mode_identity(python_path)  # noqa: SLF001
    owner_source_identity = BOOTSTRAP_V2._snapshot_mode_identity(owner_source_path)  # noqa: SLF001
    noncanonical = json.dumps(
        {"owner_source": owner_source_identity, "python": python_identity},
        sort_keys=False,
    )
    assert noncanonical != json.dumps(
        {"owner_source": owner_source_identity, "python": python_identity},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    rejected_noncanonical = _gate_b_owner_driver_probe(
        tmp_path / "noncanonical-identity",
        python_identity=python_identity,
        owner_source_identity=owner_source_identity,
        expected_argument=noncanonical,
    )
    assert rejected_noncanonical.returncode == 125
    source = BOOTSTRAP_V2.GATE_B_OWNER_DRIVER_V1
    assert "dict(os.environ) != clean" in source
    assert 'set(expected) != {"owner_source", "python"}' in source
    assert '"/proc/self/fd/" + str(owner_source_fd)' in source


def _owner_publisher_probe(
    tmp_path: Path,
    *,
    source_kind: str,
) -> subprocess.CompletedProcess[str]:
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True)
    named_source = tmp_path / "named-source.json"
    named_source.write_bytes(b'{"status":"PASS"}')
    wrapper = r"""
import ctypes
import fcntl
import os
import sys

literal, output_dir, named_source, source_kind = sys.argv[1:]
if source_kind == "named":
    source_fd = os.open(named_source, os.O_RDONLY | os.O_CLOEXEC)
else:
    libc = ctypes.CDLL(None, use_errno=True)
    create = libc.memfd_create
    create.argtypes = (ctypes.c_char_p, ctypes.c_uint)
    create.restype = ctypes.c_int
    source_fd = int(create(b"ab16-owner-publisher-focused", 0x0001 | 0x0002))
    if source_fd < 0:
        raise OSError(ctypes.get_errno(), "memfd_create")
    os.write(source_fd, b'{"status":"PASS"}')
    os.lseek(source_fd, 0, os.SEEK_SET)
    if source_kind == "sealed":
        fcntl.fcntl(source_fd, 1033, 0x0001 | 0x0002 | 0x0004 | 0x0008)
directory_fd = os.open(
    output_dir,
    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
)
source_copy = fcntl.fcntl(source_fd, fcntl.F_DUPFD_CLOEXEC, 32)
directory_copy = fcntl.fcntl(directory_fd, fcntl.F_DUPFD_CLOEXEC, 32)
os.dup2(source_copy, 4, inheritable=True)
os.dup2(directory_copy, 5, inheritable=True)
os.dup2(1, 6, inheritable=True)
os.execve(
    sys.executable,
    [sys.executable, "-I", "-B", "-c", literal, "published.json"],
    {
        "LANG": "C",
        "LC_ALL": "C",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "TZ": "UTC",
    },
)
"""
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            wrapper,
            BOOTSTRAP_V2.OWNER_OEXCL_PUBLISH_V1,
            str(output_dir),
            str(named_source),
            source_kind,
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_owner_publisher_accepts_only_fully_sealed_memfd_and_publishes_0444(
    tmp_path: Path,
) -> None:
    accepted = _owner_publisher_probe(tmp_path / "sealed", source_kind="sealed")
    assert accepted.returncode == 0, accepted.stderr
    published = tmp_path / "sealed/output/published.json"
    observed = published.stat()
    assert published.read_bytes() == b'{"status":"PASS"}'
    assert observed.st_nlink == 1
    assert observed.st_mode & 0o7777 == 0o444
    assert accepted.stdout == (
        "OK "
        + hashlib.sha256(published.read_bytes()).hexdigest()
        + f" {published.stat().st_size}\n"
    )
    source = BOOTSTRAP_V2.OWNER_OEXCL_PUBLISH_V1
    assert "    0o600,\n    dir_fd=directory_fd,\n)" in source
    assert source.index("os.fsync(fd)") < source.index("os.fchmod(fd, 0o444)")

    unsealed = _owner_publisher_probe(
        tmp_path / "unsealed",
        source_kind="unsealed",
    )
    assert unsealed.returncode == 125
    assert not (tmp_path / "unsealed/output/published.json").exists()

    named = _owner_publisher_probe(tmp_path / "named", source_kind="named")
    assert named.returncode == 125
    assert not (tmp_path / "named/output/published.json").exists()
