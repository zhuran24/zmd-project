from __future__ import annotations

import importlib.util
import inspect
import json
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727"
LEGACY_LIFECYCLE_TEST = (
    ROOT / "src/tests/test_b1_sidewise_marked_membrane_authority_recovery_v1.py"
)


def _load(filename: str) -> ModuleType:
    path = RESEARCH / filename
    spec = importlib.util.spec_from_file_location(f"_test_smm4_runner_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_path(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def contract() -> ModuleType:
    return _load("identity_contract_v1.py")


@pytest.fixture(scope="module")
def runner(contract: ModuleType) -> ModuleType:
    module = _load("run_smm4_two_stage_attempt_v1.py")
    module._activate_identity_contract(contract)
    return module


@pytest.fixture(scope="module")
def verifier(contract: ModuleType) -> ModuleType:
    module = _load("verify_smm4_two_stage_v1.py")
    module._activate_identity_contract(contract)
    return module


@pytest.fixture(scope="module")
def lifecycle_builder() -> ModuleType:
    return _load_path(LEGACY_LIFECYCLE_TEST, "_test_smm4_legacy_lifecycle_builder")


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="ascii"))
    assert isinstance(value, dict)
    return value


def _write_executable(path: Path, marker: str) -> Path:
    path.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' '{marker}'\n",
        encoding="ascii",
    )
    path.chmod(0o755)
    return path.resolve()


def _retained_command(
    identity: dict[str, Any],
    logical_argv: list[str],
    *,
    stdout: str = "",
) -> dict[str, Any]:
    return {
        "argv": list(logical_argv),
        "logical_argv": list(logical_argv),
        "executed_argv": ["/proc/self/fd/91", *logical_argv[1:]],
        "executable": identity,
        "transport": "retained_proc_self_fd",
        "executed_from_retained_fd": True,
        "same_fd_stable_before_after": True,
        "exit_code": 0,
        "stdout": stdout,
        "stderr": "",
    }


def _fresh_lifecycle(
    runner: ModuleType,
    verifier: ModuleType,
    lifecycle_builder: ModuleType,
    tmp_path: Path,
) -> dict[str, dict[str, Any]]:
    fixture = lifecycle_builder._lifecycle(verifier)
    systemctl = _write_executable(tmp_path / "systemctl", "SYSTEMCTL")
    identity = runner._identity(systemctl, "lifecycle systemctl")
    fixture["authority"]["binaries"]["systemctl"] = identity
    unit = "b1-smm4-fixture-00000001.service"
    for name in (
        "selection",
        "launch",
        "payload_terminal",
        "preterminal",
        "terminal",
        "cleanup",
    ):
        fixture[name]["unit"] = unit
    preterminal_process_raw = {
        "Result": "success\n",
        "ExecMainCode": "0\n",
        "ExecMainStatus": "0\n",
        "ExecMainStartTimestampMonotonic": "100\n",
    }
    fixture["launch"]["initial_systemd_raw"].update(preterminal_process_raw)
    fixture["preterminal"]["systemd_raw"].update(preterminal_process_raw)
    fixture["terminal"]["systemd_raw"].update(
        {
            "ExecMainStartTimestampMonotonic": "100\n",
            "ExecMainExitTimestampMonotonic": "500\n",
        }
    )
    preterminal_argv = [
        str(systemctl),
        "--user",
        "show",
        unit,
        "--no-pager",
        *[f"--property={field}" for field in runner.SYSTEMD_PRETERMINAL_FIELDS],
    ]
    terminal_argv = [
        str(systemctl),
        "--user",
        "show",
        unit,
        "--no-pager",
        *[f"--property={field}" for field in runner.SYSTEMD_TERMINAL_FIELDS],
    ]
    fixture["preterminal"]["systemctl"] = _retained_command(
        identity,
        preterminal_argv,
        stdout="".join(
            f"{field}={fixture['preterminal']['systemd_raw'][field][:-1]}\n"
            for field in runner.SYSTEMD_PRETERMINAL_FIELDS
        ),
    )
    fixture["terminal"]["systemctl"] = _retained_command(
        identity,
        terminal_argv,
        stdout="".join(
            f"{field}={fixture['terminal']['systemd_raw'][field][:-1]}\n"
            for field in runner.SYSTEMD_TERMINAL_FIELDS
        ),
    )
    fixture["cleanup"]["stop"] = _retained_command(
        identity,
        [str(systemctl), "--user", "stop", unit],
    )
    fixture["cleanup"]["reset_failed"] = _retained_command(
        identity,
        [str(systemctl), "--user", "reset-failed", unit],
    )
    fixture["cleanup"]["load_state"] = _retained_command(
        identity,
        [
            str(systemctl),
            "--user",
            "show",
            unit,
            "--property=LoadState",
            "--value",
        ],
        stdout="not-found\n",
    )
    return fixture


def test_selection_is_first_immutable_canonical_attempt_object(
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o755)
    attempt_dir = run_dir / "synthetic-success-a001"
    authority_file = tmp_path / "authority.json"
    authority_file.write_text("{}\n", encoding="ascii")
    authority_identity = runner._identity(authority_file.resolve(), "fixture authority")
    authority = {
        "run": "run",
        "run_nonce": "fixture-run",
        "manager_epoch": {"epoch": "fixed"},
        "binaries": {"fixed_python": {"target": {"path": "/fixture/python"}}},
        "tools": {"orchestrator": {}},
    }
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(
        runner,
        "_load_authority",
        lambda _path, _package: (authority, authority_identity, ModuleType("orchestrator")),
    )
    monkeypatch.setattr(
        runner,
        "_build_payload",
        lambda **_kwargs: (
            ["/fixture/logical-worker"],
            ["/fixture/executed-worker"],
            attempt_dir / "state/payload-seal.json",
        ),
    )
    monkeypatch.setattr(runner, "_resource_contract", lambda _authority: {"resource": "fixed"})
    monkeypatch.setattr(
        runner,
        "_timing_contract",
        lambda _purpose: {
            "runtime_max_seconds": 1,
            "keeper_timeout_seconds": 1,
        },
    )

    real_write_once = runner._write_once
    observed_at_selection: list[str] = []

    def publish_selection(**kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        assert kwargs["path"] == attempt_dir / "selection.json"
        observed_at_selection.extend(sorted(path.name for path in attempt_dir.iterdir()))
        assert observed_at_selection == []
        payload = {
            "schema_version": runner.SELECTION_SCHEMA,
            "status": "SELECTED_CONSUMED",
            "attempt": "synthetic-success-a001",
            "purpose": "synthetic_success",
            "unit": "b1-smm4-selection-first-12345678.service",
            "upper_bound_update_authorized": False,
        }
        identity = real_write_once(kwargs["path"], runner._json_bytes(payload))
        return payload, identity

    monkeypatch.setattr(runner, "_publish_selection", publish_selection)
    real_mkdir_once = runner._mkdir_once

    def fail_before_state(path: Path) -> None:
        if path == attempt_dir / "state":
            assert sorted(member.name for member in attempt_dir.iterdir()) == [
                "selection.json"
            ]
            raise runner.AttemptError("injected immediately after selection")
        real_mkdir_once(path)

    monkeypatch.setattr(runner, "_mkdir_once", fail_before_state)
    with pytest.raises(runner.AttemptError, match="immediately after selection"):
        runner._launch_attempt(
            authority_path=authority_file.resolve(),
            authority_package_id="a" * 64,
            attempt_dir=attempt_dir.resolve(),
            attempt="synthetic-success-a001",
            purpose="synthetic_success",
            unit="b1-smm4-selection-first-12345678.service",
            formal_admission_path=None,
        )

    assert observed_at_selection == []
    assert sorted(path.name for path in attempt_dir.iterdir()) == ["selection.json"]
    preselection = (
        run_dir
        / runner.PRESELECTION_DIR
        / "synthetic-success-a001-payload-spec.json"
    )
    assert preselection.is_file() and not preselection.is_symlink()
    selection_identity = runner._identity(
        attempt_dir / "selection.json",
        "selection first object",
    )
    with pytest.raises(runner.AttemptError, match="cannot create O_EXCL"):
        real_write_once(
            attempt_dir / "selection.json",
            b'{"status":"replacement"}\n',
        )
    assert runner._identity(
        attempt_dir / "selection.json",
        "selection immutable replay",
    ) == selection_identity


def test_only_exact_empty_unconsumed_attempt_directory_is_resumable(
    runner: ModuleType,
    tmp_path: Path,
) -> None:
    attempt_dir = tmp_path / "formal-attempt-a004"
    runner._prepare_unconsumed_attempt_dir(attempt_dir)
    before = attempt_dir.stat()
    runner._prepare_unconsumed_attempt_dir(attempt_dir)
    after = attempt_dir.stat()
    assert (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)
    assert list(attempt_dir.iterdir()) == []

    (attempt_dir / "state").mkdir()
    with pytest.raises(runner.AttemptError, match="without a reusable empty"):
        runner._prepare_unconsumed_attempt_dir(attempt_dir)


@pytest.mark.parametrize("mutation", ("mode", "hardlink"))
def test_preselection_exact_byte_reuse_rejects_file_topology_drift(
    runner: ModuleType,
    tmp_path: Path,
    mutation: str,
) -> None:
    preselection = tmp_path / runner.PRESELECTION_DIR
    preselection.mkdir(mode=0o755)
    target = preselection / "formal-attempt-a004-payload-spec.json"
    raw = b'{"status":"fixed"}\n'
    runner._write_once(target, raw)
    if mutation == "mode":
        target.chmod(0o600)
    else:
        os.link(target, tmp_path / "payload-spec-hardlink.json")
    with pytest.raises(runner.AttemptError, match="existing immutable bytes differ"):
        runner._write_or_reuse_exact(
            target,
            raw,
            f"preselection {mutation}",
        )


def _failure_topology(
    runner: ModuleType,
    contract: ModuleType,
    tmp_path: Path,
) -> dict[str, Any]:
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o755)
    preselection = run_dir / runner.PRESELECTION_DIR
    preselection.mkdir(mode=0o755)
    attempt_dir = run_dir / runner.FORMAL_ATTEMPT_DIR
    attempt_dir.mkdir(mode=0o755)
    (attempt_dir / "state").mkdir(mode=0o755)
    paths = runner._attempt_paths(attempt_dir)
    authority_dir = run_dir / "authority-a001"
    authority_dir.mkdir(mode=0o755)
    authority_path = authority_dir / "authority.json"
    authority_path.write_text("{}\n", encoding="ascii")
    authority_identity = runner._identity(authority_path.resolve(), "fixture authority")
    systemctl_path = _write_executable(tmp_path / "systemctl", "SYSTEMCTL")
    systemctl_identity = runner._identity(systemctl_path, "fixture systemctl")
    completion_seal = attempt_dir / "state/payload-seal.json"
    payload_spec = {
        "schema_version": "b1_sidewise_smm4_payload_spec_v1",
        "run_nonce": "fixture-run",
        "attempt": runner.FORMAL_ATTEMPT,
        "purpose": "formal",
        "unit": "b1-smm4-preseal-failure-12345678.service",
        "authority": authority_identity,
        "authority_package_id": "b" * 64,
        "manager_epoch": {"epoch": "fixed"},
        "completion_seal": str(completion_seal.resolve(strict=False)),
    }
    payload_spec_identity = runner._write_once(
        paths["payload_spec"],
        runner._json_bytes(payload_spec),
    )
    selection = {
        "schema_version": runner.SELECTION_SCHEMA,
        "status": "SELECTED_CONSUMED",
        "run_nonce": "fixture-run",
        "attempt": runner.FORMAL_ATTEMPT,
        "purpose": "formal",
        "unit": "b1-smm4-preseal-failure-12345678.service",
        "authority_package_id": "b" * 64,
        "manager_epoch": {"epoch": "fixed"},
        "authority": authority_identity,
        "authority_content_identity": contract.canonical_content_projection(
            authority_identity,
            "fixture authority",
        ),
        "payload_spec": payload_spec_identity,
        "upper_bound_update_authorized": False,
    }
    runner._write_once(paths["selection"], runner._json_bytes(selection))
    authority = {
        "run": "run",
        "run_nonce": "fixture-run",
        "manager_epoch": {"epoch": "fixed"},
        "binaries": {"systemctl": systemctl_identity},
        "tools": {},
    }
    return {
        "run_dir": run_dir,
        "attempt_dir": attempt_dir,
        "paths": paths,
        "authority_path": authority_path.resolve(),
        "authority": authority,
        "authority_identity": authority_identity,
        "completion_seal": completion_seal,
        "unit": selection["unit"],
        "systemctl_identity": systemctl_identity,
    }


def _patch_failure_observers(
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    topology: dict[str, Any],
) -> None:
    monkeypatch.setattr(
        runner,
        "_load_authority",
        lambda _path, _package: (
            topology["authority"],
            topology["authority_identity"],
            ModuleType("orchestrator"),
        ),
    )
    monkeypatch.setattr(
        runner,
        "_epoch",
        lambda _authority, _orchestrator, stage: {"epoch": "fixed", "stage": stage},
    )
    systemctl_path = topology["systemctl_identity"]["path"]
    unit = topology["unit"]
    terminal_record = _retained_command(
        topology["systemctl_identity"],
        [
            systemctl_path,
            "--user",
            "show",
            unit,
            "--no-pager",
            "--property=LoadState",
            "--property=ActiveState",
            "--property=SubState",
            "--property=Result",
            "--property=MainPID",
            "--property=InvocationID",
            "--property=ControlGroup",
        ],
        stdout=(
            "LoadState=loaded\n"
            "ActiveState=failed\n"
            "SubState=failed\n"
            "Result=exit-code\n"
            "MainPID=0\n"
            "InvocationID=\n"
            "ControlGroup=/user.slice/fixture.scope\n"
        ),
    )
    stop_record = _retained_command(
        topology["systemctl_identity"],
        [systemctl_path, "--user", "stop", unit],
    )
    reset_record = _retained_command(
        topology["systemctl_identity"],
        [systemctl_path, "--user", "reset-failed", unit],
    )
    load_state_record = _retained_command(
        topology["systemctl_identity"],
        [
            systemctl_path,
            "--user",
            "show",
            unit,
            "--property=LoadState",
            "--value",
        ],
        stdout="not-found\n",
    )
    monkeypatch.setattr(
        runner,
        "_failure_unit_observation",
        lambda _authority, _unit: terminal_record,
    )
    monkeypatch.setattr(
        runner,
        "_failure_process_seed",
        lambda _paths: (
            {"4242": 101},
            "/sys/fs/cgroup/user.slice/fixture.scope",
            {},
        ),
    )
    monkeypatch.setattr(
        runner,
        "_emergency_cleanup",
        lambda _authority, _unit: [stop_record, reset_record],
    )
    monkeypatch.setattr(
        runner,
        "_failure_absence_observation",
        lambda _authority, _unit, pid_starttimes, cgroup_path: {
            "load_state": load_state_record,
            "unit_absent": True,
            "checked_pids": [4242],
            "pid_starttimes": dict(pid_starttimes),
            "remaining_pids": [],
            "cgroup_path": cgroup_path,
            "cgroup_absent": True,
            "absence_verified": True,
        },
    )


def test_preseal_failure_freezes_terminal_cleanup_absence_and_detached(
    runner: ModuleType,
    contract: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    topology = _failure_topology(runner, contract, tmp_path)
    _patch_failure_observers(runner, monkeypatch, topology)
    paths = topology["paths"]

    def detached_verifier(_authority: dict[str, Any], arguments: list[str]) -> dict[str, Any]:
        assert arguments[0] == "detached-failure"
        output = Path(arguments[arguments.index("--output") + 1])
        receipt = {
            "schema_version": runner.DETACHED_FAILURE_SCHEMA,
            "status": "VERIFIED_FAIL_CLOSED",
            "mode": "detached-failure",
            "attempt_consumed": True,
            "retry_authorized": False,
            "completion_seal_absent": True,
            "upper_bound_update_authorized": False,
            "ledger": {"upper": [1188, 22], "lower": "absent"},
            "production_certified": False,
        }
        runner._write_once(output, runner._json_bytes(receipt))
        return {"exit_code": 0}

    monkeypatch.setattr(runner, "_run_verifier", detached_verifier)
    result = runner._close_postselection_failure(
        authority_path=topology["authority_path"],
        authority_package_id="b" * 64,
        attempt_dir=topology["attempt_dir"],
        attempt=runner.FORMAL_ATTEMPT,
        purpose="formal",
        unit=topology["unit"],
        error=runner.AttemptError("injected before SEAL"),
    )
    assert result == paths["failure_detached"]
    assert not topology["completion_seal"].exists()

    terminal = _json(paths["failure_terminal"])
    cleanup = _json(paths["failure_cleanup"])
    failure = _json(paths["attempt_failure"])
    detached = _json(paths["failure_detached"])
    assert terminal["status"] == "FAILURE_TERMINAL_CAPTURED"
    assert terminal["completion_seal_present"] is False
    assert terminal["upper_bound_update_authorized"] is False
    assert terminal["ledger"] == {"upper": [1188, 22], "lower": "absent"}
    assert cleanup["status"] == "FAILURE_CLEANUP_CAPTURED"
    assert cleanup["unit_absent"] is True
    assert cleanup["remaining_pids"] == []
    assert cleanup["cgroup_absent"] is True
    assert cleanup["absence_verified"] is True
    assert cleanup["upper_bound_update_authorized"] is False
    assert failure["status"] == "FORMAL_AUTHORITY_INCOMPLETE"
    assert failure["attempt_consumed"] is True
    assert failure["retry_authorized"] is False
    assert failure["completion_seal_present"] is False
    assert failure["absence_verified"] is True
    assert failure["upper_bound_update_authorized"] is False
    assert detached["status"] == "VERIFIED_FAIL_CLOSED"
    assert detached["completion_seal_absent"] is True
    assert detached["upper_bound_update_authorized"] is False
    assert detached["ledger"] == {"upper": [1188, 22], "lower": "absent"}

    frozen = {
        path: runner._identity(path, path.name)
        for path in (
            paths["failure_terminal"],
            paths["failure_cleanup"],
            paths["attempt_failure"],
            paths["failure_detached"],
        )
    }
    assert all(path.stat().st_nlink == 1 and not path.is_symlink() for path in frozen)
    replay = runner._close_postselection_failure(
        authority_path=topology["authority_path"],
        authority_package_id="b" * 64,
        attempt_dir=topology["attempt_dir"],
        attempt=runner.FORMAL_ATTEMPT,
        purpose="formal",
        unit=topology["unit"],
        error=runner.AttemptError("different retry error must not rewrite"),
    )
    assert replay == paths["failure_detached"]
    assert {
        path: runner._identity(path, path.name)
        for path in frozen
    } == frozen


def test_preseal_failure_without_detached_receipt_pins_explicit_absent_path(
    runner: ModuleType,
    contract: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    topology = _failure_topology(runner, contract, tmp_path)
    _patch_failure_observers(runner, monkeypatch, topology)
    paths = topology["paths"]
    monkeypatch.setattr(
        runner,
        "_run_verifier",
        lambda _authority, _arguments: (_ for _ in ()).throw(
            runner.AttemptError("detached verifier unavailable")
        ),
    )
    result = runner._close_postselection_failure(
        authority_path=topology["authority_path"],
        authority_package_id="b" * 64,
        attempt_dir=topology["attempt_dir"],
        attempt=runner.FORMAL_ATTEMPT,
        purpose="formal",
        unit=topology["unit"],
        error=runner.AttemptError("injected before SEAL"),
    )
    assert result == paths["attempt_failure"]
    assert not paths["failure_detached"].exists()
    failure = _json(paths["attempt_failure"])
    assert failure["detached_failure_expected_path"] == str(
        paths["failure_detached"].absolute()
    )
    assert failure["attempt_consumed"] is True
    assert failure["retry_authorized"] is False
    assert failure["completion_seal_present"] is False
    assert failure["absence_verified"] is True
    assert failure["upper_bound_update_authorized"] is False
    assert failure["ledger"] == {"upper": [1188, 22], "lower": "absent"}
    first_identity = runner._identity(paths["attempt_failure"], "failure fallback")
    assert runner._close_postselection_failure(
        authority_path=topology["authority_path"],
        authority_package_id="b" * 64,
        attempt_dir=topology["attempt_dir"],
        attempt=runner.FORMAL_ATTEMPT,
        purpose="formal",
        unit=topology["unit"],
        error=runner.AttemptError("second closeout"),
    ) == paths["attempt_failure"]
    assert runner._identity(paths["attempt_failure"], "failure fallback replay") == first_identity


def test_detached_failure_requires_independent_live_absence_replay(
    runner: ModuleType,
    verifier: ModuleType,
    contract: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    topology = _failure_topology(runner, contract, tmp_path)
    _patch_failure_observers(runner, monkeypatch, topology)
    paths = topology["paths"]
    monkeypatch.setattr(
        runner,
        "_run_verifier",
        lambda _authority, _arguments: (_ for _ in ()).throw(
            runner.AttemptError("defer detached command to verifier fixture")
        ),
    )
    assert runner._close_postselection_failure(
        authority_path=topology["authority_path"],
        authority_package_id="b" * 64,
        attempt_dir=topology["attempt_dir"],
        attempt=runner.FORMAL_ATTEMPT,
        purpose="formal",
        unit=topology["unit"],
        error=runner.AttemptError("pre-SEAL fixture"),
    ) == paths["attempt_failure"]
    cleanup = _json(paths["failure_cleanup"])
    assert cleanup["unit_absent"] is True
    assert cleanup["remaining_pids"] == []
    assert cleanup["cgroup_absent"] is True
    assert cleanup["absence_verified"] is True

    monkeypatch.setattr(
        verifier,
        "_load_sealed_authority",
        lambda _path, _package: (
            topology["authority"],
            topology["authority_identity"],
            topology["authority_identity"],
            contract,
        ),
    )
    observed: dict[str, Any] = {}

    def reject_forged_recorded_absence(
        _authority: dict[str, Any],
        recorded_cleanup: dict[str, Any],
    ) -> dict[str, Any]:
        observed["recorded_cleanup"] = recorded_cleanup
        raise verifier.VerificationError(
            "independent live absence contradicts recorded booleans"
        )

    monkeypatch.setattr(
        verifier,
        "_live_absence_replay",
        reject_forged_recorded_absence,
    )
    arguments = SimpleNamespace(
        authority=topology["authority_path"],
        authority_package_id="b" * 64,
        selection=paths["selection"],
        payload_spec=paths["payload_spec"],
        failure_terminal=paths["failure_terminal"],
        failure_cleanup=paths["failure_cleanup"],
        attempt_failure=paths["attempt_failure"],
        manager_epoch_tool=tmp_path / "manager-tool.py",
        output=paths["failure_detached"],
    )
    with pytest.raises(
        verifier.VerificationError,
        match="independent live absence contradicts recorded booleans",
    ):
        verifier._detached_failure_command(arguments)
    assert observed["recorded_cleanup"]["absence_verified"] is True
    assert not paths["failure_detached"].exists()


@pytest.mark.parametrize("binary_name", ("systemd_run", "systemctl"))
def test_systemd_clients_record_retained_proc_fd_and_pass_fds(
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    binary_name: str,
) -> None:
    executable = _write_executable(tmp_path / binary_name, f"ORIGINAL-{binary_name}")
    identity = runner._identity(executable, binary_name)
    authority = {"binaries": {binary_name: identity}}
    real_run = runner._run
    observed: dict[str, Any] = {}

    def capture(
        argv: list[str],
        *,
        timeout: int,
        pass_fds: tuple[int, ...] = (),
    ) -> dict[str, Any]:
        observed["argv"] = list(argv)
        observed["pass_fds"] = tuple(pass_fds)
        return real_run(argv, timeout=timeout, pass_fds=pass_fds)

    monkeypatch.setattr(runner, "_run", capture)
    record = runner._run_authority_binary(
        authority,
        binary_name,
        executable,
        ["fixture"],
        timeout=10,
    )
    assert record["stdout"] == f"ORIGINAL-{binary_name}\n"
    assert record["argv"] == [str(executable), "fixture"]
    assert record["logical_argv"] == [str(executable), "fixture"]
    assert record["executed_argv"][0].startswith("/proc/self/fd/")
    assert record["executed_argv"] == observed["argv"]
    assert len(observed["pass_fds"]) == 1
    descriptor = observed["pass_fds"][0]
    assert record["executed_argv"][0] == f"/proc/self/fd/{descriptor}"
    assert record["executable"] == identity
    assert record["transport"] == "retained_proc_self_fd"
    assert record["executed_from_retained_fd"] is True
    assert record["same_fd_stable_before_after"] is True


def test_main_authority_replay_failure_uses_non_authorizing_retained_last_resort_cleanup(
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    systemctl = _write_executable(tmp_path / "last-resort-systemctl", "CLEANUP")
    monkeypatch.setattr(runner, "SYSTEMCTL", systemctl)
    real_fstat = runner.os.fstat

    def root_owned_fstat(descriptor: int) -> SimpleNamespace:
        record = real_fstat(descriptor)
        return SimpleNamespace(
            st_dev=record.st_dev,
            st_ino=record.st_ino,
            st_mode=record.st_mode,
            st_nlink=record.st_nlink,
            st_uid=0,
            st_size=record.st_size,
            st_mtime_ns=record.st_mtime_ns,
            st_ctime_ns=record.st_ctime_ns,
        )

    monkeypatch.setattr(runner.os, "fstat", root_owned_fstat)
    executed: list[tuple[list[str], tuple[int, ...]]] = []

    def fake_run(
        argv: list[str],
        *,
        timeout: int,
        pass_fds: tuple[int, ...] = (),
    ) -> dict[str, Any]:
        assert timeout == 30
        executed.append((list(argv), tuple(pass_fds)))
        return {
            "argv": list(argv),
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
        }

    monkeypatch.setattr(runner, "_run", fake_run)
    monkeypatch.setattr(
        runner,
        "_launch_attempt",
        lambda **_kwargs: (_ for _ in ()).throw(
            runner.AttemptError("primary authority replay failed")
        ),
    )
    monkeypatch.setattr(
        runner,
        "_close_postselection_failure",
        lambda **_kwargs: (_ for _ in ()).throw(
            runner.AttemptError("closeout authority replay failed")
        ),
    )
    authority_path = tmp_path / "authority.json"
    authority_path.write_text("{}\n", encoding="ascii")
    attempt_dir = tmp_path / "synthetic-success-a001"
    exit_code = runner.main(
        [
            "--authority",
            str(authority_path),
            "--authority-package-id",
            "c" * 64,
            "--attempt-dir",
            str(attempt_dir),
            "--attempt",
            "synthetic-success-a001",
            "--purpose",
            "synthetic_success",
            "--unit",
            "b1-smm4-last-resort-12345678.service",
        ]
    )
    assert exit_code == 2
    failure = json.loads(capsys.readouterr().err)
    cleanup = failure["last_resort_cleanup"]
    assert len(cleanup) == 3
    assert len(executed) == 3
    for record, (argv, pass_fds) in zip(cleanup, executed, strict=True):
        assert record["logical_argv"][0] == str(systemctl)
        assert record["executed_argv"] == argv
        assert argv[0].startswith("/proc/self/fd/")
        assert len(pass_fds) == 1
        assert argv[0] == f"/proc/self/fd/{pass_fds[0]}"
        assert record["transport"] == "retained_proc_self_fd_cleanup_only"
        assert record["authority_bound"] is False
        assert record["upper_bound_update_authorized"] is False
    assert failure["upper_bound_update_authorized"] is False
    assert failure["ledger"] == {"upper": [1188, 22], "lower": "absent"}


@pytest.mark.parametrize("mutation", ("missing", "extra", "path_transport"))
def test_detached_verifier_rejects_retained_command_provenance_drift(
    runner: ModuleType,
    verifier: ModuleType,
    tmp_path: Path,
    mutation: str,
) -> None:
    executable = _write_executable(tmp_path / "systemctl", "SYSTEMCTL")
    identity = runner._identity(executable, "fixture systemctl")
    logical = [str(executable), "--user", "show", "fixture.service"]
    command = {
        "argv": logical,
        "exit_code": 0,
        "stdout": "LoadState=not-found\n",
        "stderr": "",
        "logical_argv": logical,
        "executed_argv": [
            "/proc/self/fd/91",
            "--user",
            "show",
            "fixture.service",
        ],
        "executable": identity,
        "transport": "retained_proc_self_fd",
        "executed_from_retained_fd": True,
        "same_fd_stable_before_after": True,
    }
    if mutation == "missing":
        command.pop("transport")
    elif mutation == "extra":
        command["extra"] = "forbidden"
    else:
        command["executed_argv"][0] = str(executable)

    with pytest.raises(
        verifier.VerificationError,
        match="command key set mismatch|retained-FD execution provenance mismatch",
    ):
        verifier._validate_retained_command(
            command,
            identity,
            f"changed {mutation}",
        )


@pytest.mark.parametrize("stage", ("preterminal", "terminal"))
@pytest.mark.parametrize("mutation", ("field", "order"))
def test_success_chain_systemctl_exact_logical_argv_rejects_drift(
    runner: ModuleType,
    verifier: ModuleType,
    lifecycle_builder: ModuleType,
    tmp_path: Path,
    stage: str,
    mutation: str,
) -> None:
    fixture = _fresh_lifecycle(
        runner,
        verifier,
        lifecycle_builder,
        tmp_path,
    )
    verifier.validate_terminal_cleanup(
        fixture["authority"],
        fixture["selection"],
        fixture["launch"],
        fixture["payload_terminal"],
        fixture["preterminal"],
        fixture["terminal"],
        fixture["cleanup"],
        fixture["current_epoch"],
        expected_terminal="success",
    )
    command = fixture[stage]["systemctl"]
    argv = command["argv"]
    logical = command["logical_argv"]
    executed = command["executed_argv"]
    if mutation == "field":
        argv[-1] = "--property=DriftedField"
        logical[-1] = "--property=DriftedField"
        executed[-1] = "--property=DriftedField"
    else:
        argv[-2:] = reversed(argv[-2:])
        logical[-2:] = reversed(logical[-2:])
        executed[-2:] = reversed(executed[-2:])
    with pytest.raises(
        verifier.VerificationError,
        match=(
            "pre-terminal systemctl argv mismatch"
            if stage == "preterminal"
            else "terminal systemctl argv mismatch"
        ),
    ):
        verifier.validate_terminal_cleanup(
            fixture["authority"],
            fixture["selection"],
            fixture["launch"],
            fixture["payload_terminal"],
            fixture["preterminal"],
            fixture["terminal"],
            fixture["cleanup"],
            fixture["current_epoch"],
            expected_terminal="success",
        )


def test_initial_systemctl_validator_has_exact_ordered_logical_argv_gate(
    verifier: ModuleType,
) -> None:
    source = inspect.getsource(verifier._validate_common_artifacts)
    assert "launch initial systemctl" in source
    assert (
        '*[f"--property={field}" for field in SYSTEMD_PRETERMINAL_FIELDS]'
        in source
    )
    assert "launch: initial systemctl logical argv drifted" in source
    assert 'initial_systemctl.get("logical_argv")' in source


@pytest.mark.parametrize("binary_name", ("systemd_run", "systemctl"))
def test_systemd_clients_execute_original_inode_after_path_replacement(
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    binary_name: str,
) -> None:
    executable = _write_executable(tmp_path / binary_name, f"ORIGINAL-{binary_name}")
    identity = runner._identity(executable, binary_name)
    original_inode = identity["inode"]
    authority = {"binaries": {binary_name: identity}}
    backup = tmp_path / f"{binary_name}.retained-original"
    real_run = runner._run
    observed: dict[str, Any] = {}

    def replace_then_execute(
        argv: list[str],
        *,
        timeout: int,
        pass_fds: tuple[int, ...] = (),
    ) -> dict[str, Any]:
        executable.rename(backup)
        _write_executable(executable, f"HOSTILE-{binary_name}")
        observed["replacement_inode"] = executable.stat().st_ino
        observed["pass_fds"] = tuple(pass_fds)
        observed["argv"] = list(argv)
        observed["result"] = real_run(argv, timeout=timeout, pass_fds=pass_fds)
        return observed["result"]

    monkeypatch.setattr(runner, "_run", replace_then_execute)
    try:
        with pytest.raises(runner.AttemptError, match="changed during retained-FD execution"):
            runner._run_authority_binary(
                authority,
                binary_name,
                executable,
                ["fixture"],
                timeout=10,
            )
        assert observed["result"]["stdout"] == f"ORIGINAL-{binary_name}\n"
        assert f"HOSTILE-{binary_name}" not in observed["result"]["stdout"]
        assert observed["replacement_inode"] != original_inode
        assert len(observed["pass_fds"]) == 1
        descriptor = observed["pass_fds"][0]
        assert observed["argv"][0] == f"/proc/self/fd/{descriptor}"
    finally:
        if backup.exists():
            if executable.exists():
                executable.unlink()
            backup.rename(executable)
    assert runner._identity(executable, f"{binary_name} restored") == identity
