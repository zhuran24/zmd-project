from __future__ import annotations

import base64
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import stat
import sys
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "docs/research/noncert_cuts_ab16_20260724"
HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = _load(
    "noncert_cuts_ab16_disposable_drill_authority_tested",
    TOOLS / "disposable_drill_authority_v1.py",
)
PAYLOAD = _load(
    "noncert_cuts_ab16_disposable_drill_payload_tested",
    TOOLS / "disposable_drill_payload_v1.py",
)


def _inputs(tmp_path: Path) -> tuple[dict[str, Path], dict[str, Path]]:
    strict = {}
    for role in sorted(BUILDER.bootstrap.STRICT_INPUT_ROLES):
        path = tmp_path / "inputs" / role
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture {role}\n")
        strict[role] = path
    system = {}
    for role in sorted(BUILDER.bootstrap.SYSTEM_TOOL_ROLES):
        path = tmp_path / "system" / role
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture {role}\n")
        path.chmod(0o755)
        system[role] = path
    return strict, system


def _capture(
    tmp_path: Path,
    system: dict[str, Path],
) -> dict[str, object]:
    authority = BUILDER.bootstrap.authority
    manager = tmp_path / "manager"
    manager.write_bytes(b"fixture manager\n")
    full = lambda path: authority.full_identity(  # noqa: E731
        authority.snapshot_regular(path)
    )
    attestor = BUILDER.bootstrap.V4_RESEARCH_DIR / "manager_attestor_v4.py"
    epoch = {
        "attestation_toolchain": {
            "attestor": full(attestor),
            "python": full(system["attestor_python"]),
            "sudo": full(system["sudo"]),
        },
        "attestor_ast_audit": authority.audit_attestor_source(attestor.read_bytes()),
        "boot_id": "11111111-2222-3333-4444-555555555555",
        "capture_protocol": ("double-unprivileged-join-plus-read-only-sudo-attestation-v4"),
        "dbus_unique_owner": ":1.77",
        "manager_executable": full(manager),
        "manager_features": "+PAM +AUDIT",
        "manager_pid": 2118,
        "manager_pid_starttime": 987654,
        "manager_version": "systemd 261.1",
        "observation_toolchain": {"busctl": full(system["busctl"])},
        "schema": authority.MANAGER_EPOCH_SCHEMA,
    }
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
    attestation = {
        "manager_executable": epoch["manager_executable"],
        "request": {
            "boot_id": epoch["boot_id"],
            "dbus_unique_owner": epoch["dbus_unique_owner"],
            "manager_pid": epoch["manager_pid"],
            "manager_pid_starttime": epoch["manager_pid_starttime"],
        },
        "schema": authority.ATTESTOR_SCHEMA,
        "status": "PASS",
    }
    toolchain = epoch["attestation_toolchain"]
    invocation = {
        "argv": [
            toolchain["sudo"]["path"],
            "-n",
            "--",
            toolchain["python"]["path"],
            "-I",
            "-c",
            authority._LOADER,  # noqa: SLF001
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
        "stdin_sha256": toolchain["attestor"]["sha256"],
        "stdin_size_bytes": toolchain["attestor"]["size_bytes"],
        "stdout_base64": base64.b64encode(authority.canonical_json(attestation)).decode("ascii"),
    }
    rounds = [
        {
            "attestation_toolchain": copy.deepcopy(epoch["attestation_toolchain"]),
            "attestor_ast_audit": copy.deepcopy(epoch["attestor_ast_audit"]),
            "attestor_invocation": copy.deepcopy(invocation),
            "observation_toolchain": copy.deepcopy(epoch["observation_toolchain"]),
            "observation_finished_monotonic_ns": index * 20,
            "observation_started_monotonic_ns": index * 20 - 10,
            "privileged_attestation": copy.deepcopy(attestation),
            "round_index": index,
            "unprivileged_after": copy.deepcopy(state),
            "unprivileged_before": copy.deepcopy(state),
        }
        for index in (1, 2)
    ]
    transcript = {
        "capture_protocol": ("two-round-before-read-only-attestor-after-transcript-v4"),
        "rounds": rounds,
        "schema": authority.MANAGER_EPOCH_TRANSCRIPT_SCHEMA,
    }
    authority.validate_manager_epoch(epoch)
    authority.validate_manager_epoch_capture_transcript(
        transcript,
        expected_epoch=epoch,
    )
    return {"manager_epoch": epoch, "transcript": transcript}


def test_disposable_authority_is_no_overwrite_and_non_authorizing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    strict, system = _inputs(tmp_path)
    observed = BUILDER.bootstrap.observe_planned_sources(
        strict_input_paths=strict,
        system_tool_paths=system,
    )
    capture = _capture(tmp_path, system)
    monkeypatch.setattr(
        BUILDER,
        "_capture_live_manager_epoch",
        lambda _: copy.deepcopy(capture),
    )
    monkeypatch.setattr(
        BUILDER,
        "_observe_repository_head",
        lambda _repository, _planned: HEAD,
    )
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1000/bus")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    destination = tmp_path / "drill-fixture-a001"

    result = BUILDER.build_disposable_drill_authority(
        output_dir=destination,
        repository_root=ROOT,
        repository_head=HEAD,
        run_nonce=destination.name,
        expected_planned_source_set_digest=observed["planned_source_set_digest"],
        strict_input_paths=strict,
        system_tool_paths=system,
    )

    assert result["formal_campaign_created"] is False
    assert sorted(path.name for path in (destination / "attempt").iterdir()) == [
        "pre-run-authority.json",
        "selection.json",
    ]
    pre_run = json.loads((destination / "attempt/pre-run-authority.json").read_text())
    selection = json.loads((destination / "attempt/selection.json").read_text())
    assert pre_run["resource_contract"] == BUILDER.lifecycle.DRILL_RESOURCE_CONTRACT
    assert selection["purpose"] == BUILDER.lifecycle.DRILL_SELECTION_PURPOSE
    assert selection["authorizations"] == {
        "global_claim_authorized": False,
        "mathematical_claim_authorized": False,
        "organic_arm_launch_authorized": False,
        "production_certified_authorized": False,
        "solver_run_authorized": False,
    }
    assert Path(pre_run["common_prestate_identity"]["path"]).is_file()
    assert Path(pre_run["arm_binding_identity"]["path"]).is_file()

    payload_result = PAYLOAD.run(
        destination / "attempt/selection.json",
        destination / "attempt/result.json",
    )
    assert payload_result["status"] == "PASS"
    with pytest.raises(PAYLOAD.DrillPayloadError, match="no-overwrite"):
        PAYLOAD.run(
            destination / "attempt/selection.json",
            destination / "attempt/result.json",
        )
    with pytest.raises(BUILDER.DrillAuthorityError, match="already exists"):
        BUILDER.build_disposable_drill_authority(
            output_dir=destination,
            repository_root=ROOT,
            repository_head=HEAD,
            run_nonce=destination.name,
            expected_planned_source_set_digest=observed["planned_source_set_digest"],
            strict_input_paths=strict,
            system_tool_paths=system,
        )

    mutated = copy.deepcopy(selection)
    mutated["purpose"] = BUILDER.lifecycle.RUNNER_SELECTION_PURPOSE
    formal_path = tmp_path / "formal-purpose.json"
    formal_path.write_bytes(PAYLOAD.canonical_json(mutated))
    formal_path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    with pytest.raises(PAYLOAD.DrillPayloadError, match="not an inert"):
        PAYLOAD.run(formal_path, tmp_path / "should-not-exist.json")


def test_serialized_planned_git_path_replays_real_repository_head(
    tmp_path: Path,
) -> None:
    strict, system = _inputs(tmp_path)
    git_path = shutil.which("git")
    assert git_path is not None
    system["git"] = Path(git_path)
    observed = BUILDER.bootstrap.observe_planned_sources(
        strict_input_paths=strict,
        system_tool_paths=system,
    )
    serialized = BUILDER.lifecycle.canonical_json_bytes(observed)
    reloaded = BUILDER.lifecycle.strict_loads(
        serialized,
        "serialized planned source observation",
    )
    planned = reloaded["planned_source_identities"]

    assert type(planned["system.git"]["path"]) is str
    assert BUILDER._observe_repository_head(ROOT, planned) == HEAD  # noqa: SLF001


def test_disposable_authority_rejects_planned_digest_drift(
    tmp_path: Path,
) -> None:
    strict, system = _inputs(tmp_path)
    destination = tmp_path / "drill-fixture-a002"
    with pytest.raises(BUILDER.DrillAuthorityError, match="digest drifted"):
        BUILDER.build_disposable_drill_authority(
            output_dir=destination,
            repository_root=ROOT,
            repository_head=HEAD,
            run_nonce=destination.name,
            expected_planned_source_set_digest="0" * 64,
            strict_input_paths=strict,
            system_tool_paths=system,
        )
    assert not destination.exists()
