from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
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


def test_repository_head_executes_pinned_git_by_absolute_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git_path, identity = _git_fixture(tmp_path)
    observed: dict[str, object] = {}

    def record_run(arguments: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        observed["arguments"] = arguments
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(arguments, 0, f"{HEAD}\n".encode(), b"")

    monkeypatch.setattr(BOOTSTRAP.subprocess, "run", record_run)
    assert (
        BOOTSTRAP._observe_repository_head(  # noqa: SLF001
            ROOT,
            git_path,
            expected_identity=identity,
        )
        == HEAD
    )
    arguments = observed["arguments"]
    kwargs = observed["kwargs"]
    assert isinstance(arguments, list)
    assert arguments[0] == str(git_path)
    assert isinstance(kwargs, dict)
    assert "executable" not in kwargs
    assert "pass_fds" not in kwargs
    assert kwargs["env"] == {"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin"}
    assert kwargs["timeout"] == 10


def test_repository_head_reports_executable_launch_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git_path, identity = _git_fixture(tmp_path)

    def fail_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        del args, kwargs
        raise OSError("git is unavailable")

    monkeypatch.setattr(BOOTSTRAP.subprocess, "run", fail_run)
    with pytest.raises(BOOTSTRAP.BootstrapError, match="observation failed"):
        BOOTSTRAP._observe_repository_head(  # noqa: SLF001
            ROOT,
            git_path,
            expected_identity=identity,
        )


def test_repository_head_rejects_nonzero_git_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git_path, identity = _git_fixture(tmp_path)

    def fail_run(arguments: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        del kwargs
        return subprocess.CompletedProcess(arguments, 128, b"", b"fatal: not a repository\n")

    monkeypatch.setattr(BOOTSTRAP.subprocess, "run", fail_run)
    with pytest.raises(BOOTSTRAP.BootstrapError, match="not one clean SHA"):
        BOOTSTRAP._observe_repository_head(  # noqa: SLF001
            ROOT,
            git_path,
            expected_identity=identity,
        )


def _fixture_sources(
    tmp_path: Path,
) -> tuple[dict[str, Path], dict[str, Path]]:
    strict: dict[str, Path] = {}
    archive_locators = _json(
        tmp_path / "inputs" / "archive-locators.json",
        {
            "authorizing": False,
            "entries": copy.deepcopy(BOOTSTRAP.ARCHIVE_LOCATOR_ENTRIES),
            "local_bytes_required": False,
            "purpose": BOOTSTRAP.ARCHIVE_LOCATORS_PURPOSE,
            "schema_version": BOOTSTRAP.ARCHIVE_LOCATORS_SCHEMA,
        },
    )
    for role in sorted(BOOTSTRAP.STRICT_INPUT_ROLES):
        if role in BOOTSTRAP.ARCHIVED_SCIENTIFIC_INPUT_ROLES:
            strict[role] = archive_locators
            continue
        if role in BOOTSTRAP.CANONICAL_JSON_INPUT_ROLES:
            raw = AUTH.canonical_json({"fixture": True, "role": role})
        elif role == "canonical_rules":
            raw = b'{"fixture_float":1.25}\n'
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
    # The fixture exercises bootstrap semantics with tiny source bytes.  The
    # unpatched production pin is covered directly below and by the clean-
    # checkout chain sentinel.
    monkeypatch.setattr(
        BOOTSTRAP,
        "_validate_candidate_placements_preregistration",
        lambda *_, **__: {},
    )
    candidate_path = tmp_path / "offline" / "candidate-a001.json"
    candidate_path.parent.mkdir()
    candidate = BOOTSTRAP.build_offline_candidate(
        output_path=candidate_path,
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
        "planned": BOOTSTRAP.observe_planned_sources(
            strict_input_paths=strict,
            system_tool_paths=system,
        ),
        "strict": strict,
        "system": system,
    }


def _complete_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    capture = _capture_result(tmp_path, fixture["system"])
    fixture["capture"] = capture
    return fixture


def test_candidate_placements_preregistration_replays_tracked_manifest_and_bytes() -> None:
    identity = BOOTSTRAP._validate_candidate_placements_preregistration(  # noqa: SLF001
        ROOT,
        ROOT / BOOTSTRAP.CANDIDATE_PLACEMENTS_PIN["path"],
    )
    assert identity["path"] == str(ROOT / BOOTSTRAP.CANDIDATE_PLACEMENTS_PIN["path"])
    assert identity["sha256"] == BOOTSTRAP.CANDIDATE_PLACEMENTS_PIN["sha256"]
    assert identity["size_bytes"] == BOOTSTRAP.CANDIDATE_PLACEMENTS_PIN["size_bytes"]


def test_candidate_placements_preregistration_rejects_wrong_bytes_or_manifest_pin(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    manifest_path = repository / "data/external_artifacts.json"
    candidate_path = repository / BOOTSTRAP.CANDIDATE_PLACEMENTS_PIN["path"]
    manifest_path.parent.mkdir(parents=True)
    candidate_path.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "data/external_artifacts.json", manifest_path)
    candidate_path.write_bytes(b"not the preregistered candidate\n")
    with pytest.raises(BOOTSTRAP.BootstrapError, match="bytes differ"):
        BOOTSTRAP._validate_candidate_placements_preregistration(  # noqa: SLF001
            repository,
            candidate_path,
        )

    manifest = AUTH.strict_loads(manifest_path.read_bytes(), "external artifact fixture")
    assert isinstance(manifest, dict)
    manifest["artifacts"][0]["sha256"] = "0" * 64
    manifest_path.write_bytes(AUTH.canonical_json(manifest))
    with pytest.raises(BOOTSTRAP.BootstrapError, match="pin drifted"):
        BOOTSTRAP._validate_candidate_placements_preregistration(  # noqa: SLF001
            repository,
            candidate_path,
        )


def _bootstrap(fixture: dict[str, Any]) -> dict[str, object]:
    return BOOTSTRAP.bootstrap_campaign(
        campaign_dir=fixture["campaign"],
        repository_root=ROOT,
        offline_candidate=fixture["candidate_path"],
        strict_input_paths=fixture["strict"],
        system_tool_paths=fixture["system"],
        created_at_utc=NOW,
        manager_capture=copy.deepcopy(fixture.get("capture")),
    )


def test_candidate_creation_is_nonauthorizing_and_campaign_free(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    assert fixture["candidate_path"].is_file()
    assert not fixture["campaign"].exists()
    candidate = fixture["candidate"]["candidate"]
    path_preregistration = fixture["candidate"]["path_preregistration"]
    assert candidate["candidate_only"] is True
    assert candidate["schema_version"] == BOOTSTRAP.CANDIDATE_SCHEMA
    assert "gate_a_receipt_identity" not in candidate
    assert candidate["formal_campaign_creation_authorized"] is False
    assert candidate["arm_launch_authorized"] is False
    assert fixture["candidate"]["formal_campaign_created"] is False
    assert fixture["path_preregistration_path"].is_file()
    assert path_preregistration == BOOTSTRAP._path_preregistration(  # noqa: SLF001
        fixture["campaign"],
        scientific_input_set_sha256=path_preregistration["scientific_input_set_sha256"],
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
        "scientific_input_set_sha256",
        "slot_roots",
        "suite_selection_path",
        "terminal_classification_path",
        "workers",
    }
    assert path_preregistration["schema"] == "noncert-cuts-ab16-scientific-preregistration-v3"
    assert path_preregistration["scientific_input_set_sha256"] == BOOTSTRAP._scientific_input_set_digest(  # noqa: SLF001
        candidate["planned_source_identities"]
    )
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


def test_scientific_input_anchor_is_content_only_and_design_scoped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    planned = copy.deepcopy(fixture["candidate"]["candidate"]["planned_source_identities"])
    digest = BOOTSTRAP._scientific_input_set_digest(planned)  # noqa: SLF001
    first_role = f"input.{sorted(BOOTSTRAP.STRICT_INPUT_ROLES)[0]}"

    relocated = copy.deepcopy(planned)
    relocated[first_role]["path"] = "/different/scientific/source"
    relocated[first_role]["mode"] = relocated[first_role]["mode"] ^ 0o111
    assert BOOTSTRAP._scientific_input_set_digest(relocated) == digest  # noqa: SLF001

    changed_bytes = copy.deepcopy(planned)
    changed_bytes[first_role]["sha256"] = "0" * 64
    if changed_bytes[first_role]["sha256"] == planned[first_role]["sha256"]:
        changed_bytes[first_role]["sha256"] = "1" * 64
    assert BOOTSTRAP._scientific_input_set_digest(changed_bytes) != digest  # noqa: SLF001

    wrong_roles = copy.deepcopy(planned)
    wrong_roles["input.unregistered"] = wrong_roles.pop(first_role)
    with pytest.raises(BOOTSTRAP.BootstrapError, match="roles drifted"):
        BOOTSTRAP._scientific_input_set_digest(wrong_roles)  # noqa: SLF001

    design_changes = (
        ("AB16_ARM_SEQUENCE", tuple(reversed(BOOTSTRAP.AB16_ARM_SEQUENCE))),
        ("AB16_EXPERIMENT_CONTRACT_SHA256", "0" * 64),
        ("AB16_SEED", BOOTSTRAP.AB16_SEED + 1),
        ("AB16_WORKERS", BOOTSTRAP.AB16_WORKERS + 1),
    )
    for attribute, value in design_changes:
        with monkeypatch.context() as patch:
            patch.setattr(BOOTSTRAP, attribute, value)
            assert BOOTSTRAP._scientific_input_set_digest(planned) != digest  # noqa: SLF001


def test_archive_locator_bytes_and_archived_scientific_targets_have_distinct_digest_roles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    planned = fixture["candidate"]["candidate"]["planned_source_identities"]
    locator_sha256 = planned["input.history_freeze_manifest"]["sha256"]
    assert locator_sha256 == planned["input.legacy_control_a002"]["sha256"]
    assert locator_sha256 not in {
        entry["sha256"] for entry in BOOTSTRAP.ARCHIVE_LOCATOR_ENTRIES.values()
    }
    members = {
        role: {
            "sha256": planned[f"input.{role}"]["sha256"],
            "size_bytes": planned[f"input.{role}"]["size_bytes"],
        }
        for role in BOOTSTRAP.SCIENTIFIC_INPUT_ROLES - BOOTSTRAP.ARCHIVED_SCIENTIFIC_INPUT_ROLES
    }
    members.update(
        {
            role: {
                "sha256": entry["sha256"],
                "size_bytes": entry["size_bytes"],
            }
            for role, entry in BOOTSTRAP.ARCHIVE_LOCATOR_ENTRIES.items()
        }
    )
    projection = {
        "arm_sequence": list(BOOTSTRAP.AB16_ARM_SEQUENCE),
        "experiment_contract_sha256": BOOTSTRAP.AB16_EXPERIMENT_CONTRACT_SHA256,
        "members": {role: members[role] for role in sorted(members)},
        "schema": BOOTSTRAP.AB16_SCIENTIFIC_INPUT_SET_SCHEMA,
        "seed": BOOTSTRAP.AB16_SEED,
        "workers": BOOTSTRAP.AB16_WORKERS,
    }
    assert BOOTSTRAP._scientific_input_set_digest(planned) == hashlib.sha256(  # noqa: SLF001
        AUTH.canonical_json(projection)
    ).hexdigest()


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
        "scientific_input_set_sha256",
        "slot_root",
        "workers",
    ),
)
def test_scientific_preregistration_rejects_design_or_topology_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    campaign = tmp_path / "campaigns" / "run-preregistration-a001"
    preregistration = BOOTSTRAP._path_preregistration(  # noqa: SLF001
        campaign,
        scientific_input_set_sha256="5" * 64,
    )
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
    elif mutation == "scientific_input_set_sha256":
        preregistration["scientific_input_set_sha256"] = "0" * 63
    elif mutation == "slot_root":
        first = CONTRACT.ARM_SEQUENCE[0]
        preregistration["slot_roots"][first] = str(campaign / "prospective-ab16" / "arms" / "wrong")
    else:
        preregistration["workers"] = 2

    with pytest.raises(BOOTSTRAP.BootstrapError, match="key set drifted|topology drifted|digest is malformed"):
        BOOTSTRAP.validate_path_preregistration(
            preregistration,
            campaign_dir=campaign,
        )


def test_bootstrap_source_set_excludes_retired_disposable_drill_modules() -> None:
    assert "disposable_drill_authority_v1" not in BOOTSTRAP.SCRIPT_TOOL_FILES
    assert "disposable_drill_payload_v1" not in BOOTSTRAP.SCRIPT_TOOL_FILES


def test_candidate_no_overwrite_and_archive_locator_is_exact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    candidate_before = fixture["candidate_path"].read_bytes()
    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="already exists",
    ):
        BOOTSTRAP.build_offline_candidate(
            output_path=fixture["candidate_path"],
            repository_root=ROOT,
            target_campaign_dir=fixture["campaign"],
            strict_input_paths=fixture["strict"],
            system_tool_paths=fixture["system"],
            created_at_utc="2026-07-24T12:57:00Z",
        )
    assert fixture["candidate_path"].read_bytes() == candidate_before
    assert not fixture["campaign"].exists()

    locator = fixture["strict"]["history_freeze_manifest"]
    value = AUTH.strict_loads(locator.read_bytes(), "archive locators")
    value["unexpected"] = False
    locator.write_bytes(AUTH.canonical_json(value))
    fresh_candidate = tmp_path / "offline-a002" / "candidate-a002.json"
    fresh_candidate.parent.mkdir()
    with pytest.raises(BOOTSTRAP.BootstrapError, match="key set drifted"):
        BOOTSTRAP.build_offline_candidate(
            output_path=fresh_candidate,
            repository_root=ROOT,
            target_campaign_dir=fixture["campaign"],
            strict_input_paths=fixture["strict"],
            system_tool_paths=fixture["system"],
        )
    assert not fresh_candidate.exists()
    assert not fixture["campaign"].exists()


def test_bootstrap_creates_complete_v4_root_and_seals_full_source_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _complete_fixture(tmp_path, monkeypatch)
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
    assert fixture["candidate_path"].read_bytes() == candidate_before
    assert result["schema"] == BOOTSTRAP.RESULT_SCHEMA
    assert not {"gate_a_receipt_identity", "gate_b_approval_identity"} & set(result)
    capture = AUTH.strict_loads(
        (campaign / "bootstrap-authority" / "manager-epoch-capture.json").read_bytes(),
        "bootstrap capture",
    )
    assert capture["schema"] == BOOTSTRAP.CAPTURE_SCHEMA
    assert not {"gate_a_receipt_identity", "gate_b_approval_identity"} & set(capture)
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
    packaged_terminal_gate_path = package_dir / "payload" / "tool.ab16_terminal_gate_v1.py"
    canonical_terminal_gate_path = AB16_RESEARCH / "ab16_terminal_gate_v1.py"
    assert packaged_terminal_gate_path.read_bytes() == canonical_terminal_gate_path.read_bytes()
    with monkeypatch.context() as no_bytecode:
        no_bytecode.setattr(sys, "dont_write_bytecode", True)
        packaged_terminal_gate = _load(
            "noncert_cuts_ab16_terminal_gate_v1_from_sealed_package",
            packaged_terminal_gate_path,
        )
    assert packaged_terminal_gate.SUITE_GATE_SCHEMA == (
        "noncert-cuts-ab16-terminal-classification-v2"
    )
    assert not (packaged_terminal_gate_path.parent / "__pycache__").exists()
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
        BOOTSTRAP.CANDIDATE_PACKAGE_ROLE,
        BOOTSTRAP.CAPTURE_PACKAGE_ROLE,
        BOOTSTRAP.PATH_PREREGISTRATION_PACKAGE_ROLE,
    }
    expected_system = {f"system.{role}.bin" for role in BOOTSTRAP.SYSTEM_TOOL_ROLES}
    assert roles == expected_scripts | expected_inputs | expected_system
    assert set(BOOTSTRAP.AB16_SCRIPT_TOOL_FILES) <= set(root["authority_tools"])
    assert {
        *AUTH.REQUIRED_GATE1_INPUT_ROLES,
        "legacy_control_a002",
        BOOTSTRAP.CANDIDATE_INPUT_ROLE,
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
    history_locator = Path(root["strict_inputs"]["history_freeze_manifest"]["path"])
    legacy_locator = Path(root["strict_inputs"]["legacy_control_a002"]["path"])
    assert history_locator.read_bytes() == legacy_locator.read_bytes()
    BOOTSTRAP.load_archive_locators(history_locator)
    assert AUTH.make_gate1_selection(
        root,
        campaign_root_identity=AUTH.detached_identity(root_snapshot),
        tools=root["authority_tools"],
        inputs=root["strict_inputs"],
        created_at_utc=NOW,
    )["schema_version"] == AUTH.GATE1_SELECTION_SCHEMA
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
        ("wrong_campaign", "does not target"),
        ("wrong_repository", "does not target"),
        ("extra_field", "key set drifted"),
    ),
)
def test_candidate_mutations_fail_before_campaign_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    match: str,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    value = AUTH.strict_loads(fixture["candidate_path"].read_bytes(), "candidate")
    if mutation == "wrong_campaign":
        value["target_campaign_dir"] = str(tmp_path / "campaigns" / "run-other")
        value["run_nonce"] = "run-other"
    elif mutation == "wrong_repository":
        value["repository_root"] = str(tmp_path)
    else:
        value["unexpected"] = False
    value["candidate_id"] = BOOTSTRAP._digest_without(value, "candidate_id")  # noqa: SLF001
    fixture["candidate_path"].write_bytes(AUTH.canonical_json(value))
    with pytest.raises(BOOTSTRAP.BootstrapError, match=match):
        _bootstrap(fixture)
    assert not fixture["campaign"].exists()


def test_source_drift_after_candidate_fails_before_live_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
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


def test_well_formed_wrong_scientific_anchor_fails_before_live_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    preregistration = AUTH.strict_loads(
        fixture["path_preregistration_path"].read_bytes(),
        "AB16 path preregistration",
    )
    preregistration["scientific_input_set_sha256"] = "0" * 64
    if preregistration["scientific_input_set_sha256"] == BOOTSTRAP._scientific_input_set_digest(  # noqa: SLF001
        fixture["candidate"]["candidate"]["planned_source_identities"]
    ):
        preregistration["scientific_input_set_sha256"] = "1" * 64
    fixture["path_preregistration_path"].write_bytes(AUTH.canonical_json(preregistration))

    candidate = AUTH.strict_loads(fixture["candidate_path"].read_bytes(), "offline candidate")
    candidate["path_preregistration_identity"] = _detached(fixture["path_preregistration_path"])
    candidate["candidate_id"] = BOOTSTRAP._digest_without(candidate, "candidate_id")  # noqa: SLF001
    fixture["candidate_path"].write_bytes(AUTH.canonical_json(candidate))
    monkeypatch.setattr(
        BOOTSTRAP,
        "_capture_epoch",
        lambda **_: pytest.fail("capture must not run after scientific anchor drift"),
    )
    with pytest.raises(BOOTSTRAP.BootstrapError, match="anchor differs from planned sources"):
        _bootstrap(fixture)
    assert not fixture["campaign"].exists()


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        ("unsafe_path", "safe relative reference"),
        ("wrong_sha", "pinned provenance"),
        ("local_required", "authority boundary"),
        ("authorizing", "authority boundary"),
    ),
)
def test_archive_locator_mutation_fails_before_live_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    match: str,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    locator = fixture["strict"]["history_freeze_manifest"]
    value = AUTH.strict_loads(locator.read_bytes(), "archive locators")
    if mutation == "unsafe_path":
        value["entries"]["history_freeze_manifest"]["archive_locator"] = "archive:/absolute"
    elif mutation == "wrong_sha":
        value["entries"]["legacy_control_a002"]["sha256"] = "0" * 64
    elif mutation == "local_required":
        value["local_bytes_required"] = True
    else:
        value["authorizing"] = True
    locator.write_bytes(AUTH.canonical_json(value))
    with pytest.raises(BOOTSTRAP.BootstrapError, match=match):
        _bootstrap(fixture)
    assert not fixture["campaign"].exists()


def test_manager_toolchain_mismatch_fails_before_campaign_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    other_system = {
        role: _write(
            tmp_path / "other-system" / role,
            f"other executable {role}\n".encode(),
        )
        for role in sorted(BOOTSTRAP.SYSTEM_TOOL_ROLES)
    }
    mismatched_capture = _capture_result(tmp_path / "other", other_system)
    fixture["capture"] = mismatched_capture
    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="does not match selected bytes",
    ):
        _bootstrap(fixture)
    assert not fixture["campaign"].exists()


@pytest.mark.parametrize("command", ("candidate", "bootstrap"))
def test_cli_is_self_contained_and_uses_only_repository_inputs(
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
        "build_offline_candidate",
        candidate_call,
    )
    monkeypatch.setattr(BOOTSTRAP, "bootstrap_campaign", bootstrap_call)
    base = [
        command,
        "--campaign-dir",
        str(tmp_path / "campaigns" / "run-fixture-cli"),
        "--repository-root",
        str(ROOT),
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
            ]
        )
    assert BOOTSTRAP.main(base) == 0
    output = AUTH.strict_loads(capsysbinary.readouterr().out, "CLI output")
    if command == "candidate":
        assert output["status"] == "CANDIDATE_FIXTURE"
        assert called["output_path"] == tmp_path / "candidate.json"
    else:
        assert output["status"] == "BOOTSTRAP_FIXTURE"
        assert called["offline_candidate"] == tmp_path / "candidate.json"
    assert not {
        "gate_a_receipt",
        "gate_b_approval",
        "history_freeze_manifest",
        "legacy_control_a002",
        "cuts_mandatory_schedule",
    } & set(called)


@pytest.mark.parametrize(
    "retired_flag",
    (
        "--gate-a-receipt",
        "--gate-b-approval",
        "--history-freeze-manifest",
        "--legacy-control-a002",
        "--cuts-mandatory-schedule",
    ),
)
def test_cli_rejects_retired_external_input_flags(retired_flag: str) -> None:
    with pytest.raises(SystemExit):
        BOOTSTRAP._parse_args(  # noqa: SLF001
            [
                "candidate",
                "--campaign-dir",
                "campaign",
                "--repository-root",
                "repository",
                "--candidate-output",
                "candidate.json",
                retired_flag,
                "retired.json",
            ]
        )


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
        match="package source changed after candidate capture",
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
    fixture["capture"] = {"invalid": True}
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
    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="offline candidate semantics drifted",
    ):
        _bootstrap(fixture)
    assert not fixture["campaign"].exists()


def test_invalid_injected_manager_capture_fails_before_campaign_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _offline_fixture(tmp_path, monkeypatch)
    fixture["capture"] = {"manager_epoch": {}}
    with pytest.raises(BOOTSTRAP.BootstrapError, match="wrong exact schema"):
        _bootstrap(fixture)
    assert not fixture["campaign"].exists()
