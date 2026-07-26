from __future__ import annotations

import copy
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727"
B0 = Path("/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721")
B1 = Path("/home/zhuran24/zmd-pj-codex-baselines/track-b-b1-sidewise-membrane-20260724")
SMM2_RUN = (
    B1
    / ".artifacts/track_b_b1_sidewise_marked_membrane_strict_20260724"
    / "run-20260723T161302Z-SMM2"
)
SMM3_RUN = (
    B1
    / ".artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724"
    / "run-20260723T192209Z-SMM3-a003"
)


def _load(name: str) -> ModuleType:
    path = RESEARCH / name
    spec = importlib.util.spec_from_file_location(f"_test_smm4_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def contract() -> ModuleType:
    return _load("identity_contract_v1.py")


@pytest.fixture(scope="module")
def orchestrator() -> ModuleType:
    return _load("run_smm4_authority_recovery_v1.py")


@pytest.fixture(scope="module")
def runner() -> ModuleType:
    return _load("run_smm4_two_stage_attempt_v1.py")


@pytest.fixture(scope="module")
def payload() -> ModuleType:
    return _load("run_smm4_formal_payload_v1.py")


@pytest.fixture(scope="module")
def verifier() -> ModuleType:
    return _load("verify_smm4_two_stage_v1.py")


def _authority_identity(runner: ModuleType, tmp_path: Path) -> dict[str, object]:
    path = tmp_path / "authority.json"
    path.write_text('{"status":"fixture"}\n', encoding="utf-8")
    return runner._identity(path.resolve(), "fixture authority")


def test_writer_to_payload_full_identity_join(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    runner: ModuleType,
    payload: ModuleType,
    contract: ModuleType,
) -> None:
    authority_identity = _authority_identity(runner, tmp_path)
    authority = {"run_nonce": "nonce", "resource_contract": {}, "tools": {}}
    monkeypatch.setattr(runner, "_load_identity_contract", lambda _authority: contract)
    monkeypatch.setattr(runner, "_epoch", lambda *_args: {"epoch": "fixed"})
    monkeypatch.setattr(runner, "_resource_contract", lambda _authority: {"memory": "fixed"})
    monkeypatch.setattr(runner, "_timing_contract", lambda _purpose: {"runtime": 1})
    selection_path = (tmp_path / "selection.json").resolve()
    selection, _ = runner._publish_selection(
        authority=authority,
        authority_identity=authority_identity,
        authority_package_id="a" * 64,
        orchestrator=ModuleType("orchestrator"),
        path=selection_path,
        attempt=runner.FORMAL_ATTEMPT,
        purpose="formal",
        unit="b1-smm4-fixture.service",
        worker_argv=["python", "payload"],
        payload_spec_identity=authority_identity,
        formal_admission=authority_identity,
    )

    assert set(selection["authority"]) == set(contract.FULL_IDENTITY_FIELDS)
    assert selection["authority_package_id"] == "a" * 64
    assert set(selection["authority_content_identity"]) == set(contract.PROJECTION_FIELDS)
    assert payload.validate_selection_authority_join(
        contract,
        selection,
        authority_identity,
    ) == selection["authority_content_identity"]


@pytest.mark.parametrize("mutation", ("missing", "extra", "path", "hash", "mode"))
def test_payload_join_rejects_projection_drift(
    mutation: str,
    tmp_path: Path,
    runner: ModuleType,
    payload: ModuleType,
    contract: ModuleType,
) -> None:
    actual = _authority_identity(runner, tmp_path)
    full = contract.validate_full_identity(actual, "full")
    projection = contract.canonical_content_projection(full, "full")
    if mutation == "missing":
        projection.pop("sha256")
    elif mutation == "extra":
        projection["unexpected"] = 1
    elif mutation == "path":
        projection["path"] += ".other"
    elif mutation == "hash":
        projection["sha256"] = "0" * 64
    else:
        projection["mode_octal"] = "0600"
    with pytest.raises(payload.PayloadError):
        payload.validate_selection_authority_join(
            contract,
            {
                "authority": full,
                "authority_content_identity": projection,
            },
            actual,
        )


@pytest.mark.parametrize(
    ("side", "mutation"),
    (
        ("actual", "missing"),
        ("actual", "extra"),
        ("expected", "missing"),
        ("expected", "extra"),
        ("actual", "device"),
        ("actual", "inode"),
        ("actual", "link_count"),
    ),
)
def test_all_lifecycle_identity_consumers_require_exact_full7(
    side: str,
    mutation: str,
    tmp_path: Path,
    runner: ModuleType,
    payload: ModuleType,
    verifier: ModuleType,
    contract: ModuleType,
) -> None:
    runner._activate_identity_contract(contract)
    payload._activate_identity_contract(contract)
    verifier._activate_identity_contract(contract)
    expected = _authority_identity(runner, tmp_path)
    actual = copy.deepcopy(expected)
    target = actual if side == "actual" else expected
    if mutation == "missing":
        target.pop("inode")
    elif mutation == "extra":
        target["unexpected"] = "must fail closed"
    elif mutation == "device":
        target["device"] += 1
    elif mutation == "inode":
        target["inode"] += 1
    else:
        target["link_count"] = 2

    with pytest.raises(runner.AttemptError):
        runner._matches(actual, expected, "runner identity")
    with pytest.raises(payload.PayloadError):
        payload.match_identity(actual, expected, "payload identity")
    with pytest.raises(verifier.VerificationError):
        verifier._identity_matches(expected, actual, "detached identity")


def test_all_lifecycle_identity_consumers_reject_hardlinks(
    tmp_path: Path,
    runner: ModuleType,
    payload: ModuleType,
    verifier: ModuleType,
    contract: ModuleType,
) -> None:
    runner._activate_identity_contract(contract)
    payload._activate_identity_contract(contract)
    verifier._activate_identity_contract(contract)
    target = (tmp_path / "target.json").resolve()
    target.write_text("{}\n", encoding="utf-8")
    expected = runner._identity(target, "target before hardlink")
    os.link(target, tmp_path / "second-link.json")
    actual = runner._identity(target, "target after hardlink")
    assert expected["link_count"] == 1
    assert actual["link_count"] == 2

    with pytest.raises(runner.AttemptError, match="link_count"):
        runner._matches(actual, expected, "runner hardlink")
    with pytest.raises(payload.PayloadError, match="link_count"):
        payload.match_identity(actual, expected, "payload hardlink")
    with pytest.raises(verifier.VerificationError, match="link_count"):
        verifier._identity_matches(expected, actual, "detached hardlink")


@pytest.mark.parametrize("mutation", ("missing", "extra", "link_count", "bool_inode"))
def test_detached_identity_record_and_content_copy_require_exact_full7(
    mutation: str,
    tmp_path: Path,
    runner: ModuleType,
    verifier: ModuleType,
    contract: ModuleType,
) -> None:
    verifier._activate_identity_contract(contract)
    expected = _authority_identity(runner, tmp_path)
    copied = copy.deepcopy(expected)
    copied["path"] = str((tmp_path / "copied-authority.json").resolve())
    copied["device"] += 1
    copied["inode"] += 1
    verifier._identity_content_matches(expected, copied, "content copy")

    changed = copy.deepcopy(copied)
    if mutation == "missing":
        changed.pop("device")
    elif mutation == "extra":
        changed["unexpected"] = True
    elif mutation == "link_count":
        changed["link_count"] = 2
    else:
        changed["inode"] = True
    with pytest.raises(verifier.VerificationError):
        verifier._identity_record(changed, "detached identity record")
    with pytest.raises(verifier.VerificationError):
        verifier._identity_content_matches(expected, changed, "content copy")


def test_write_once_identities_come_from_retained_write_fds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    orchestrator: ModuleType,
    runner: ModuleType,
    payload: ModuleType,
    verifier: ModuleType,
    contract: ModuleType,
) -> None:
    runner._activate_identity_contract(contract)
    payload._activate_identity_contract(contract)
    verifier._activate_identity_contract(contract)

    monkeypatch.setattr(
        runner,
        "_identity",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("post-close reopen")),
    )
    runner_identity = runner._write_once(
        (tmp_path / "runner-output.json").resolve(),
        b"{}\n",
    )

    source = (tmp_path / "source.json").resolve()
    source.write_text('{"source":true}\n', encoding="utf-8")
    source_identity = orchestrator.identity(source, "snapshot source")
    monkeypatch.setattr(
        orchestrator,
        "identity",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("post-close reopen")),
    )
    _, snapshot_binding = orchestrator._snapshot_one(
        source_identity,
        (tmp_path / "snapshot.json").resolve(),
        "snapshot",
    )

    payload_identity = payload.write_once(
        (tmp_path / "payload-output.json").resolve(),
        b"{}\n",
    )
    verifier_identity = verifier._write_exclusive(
        (tmp_path / "verifier-output.json").resolve(),
        b"{}\n",
    )
    for identity in (
        runner_identity,
        snapshot_binding["identity"],
        payload_identity,
        verifier_identity,
    ):
        assert set(identity) == set(contract.FULL_IDENTITY_FIELDS)
        assert identity["link_count"] == 1
        assert contract.validate_full_identity(identity, "write-once identity") == identity


def test_sealed_authority_is_self_verified_with_modes_independent_of_umask(
    tmp_path: Path,
    orchestrator: ModuleType,
) -> None:
    authority_dir = (tmp_path / "authority-a001").resolve()
    prior_umask = os.umask(0o077)
    try:
        orchestrator.mkdir_once(authority_dir)
        payload = {
            "status": "fixture",
            "tools": orchestrator.current_toolchain_snapshot()["tools"],
        }
        result = orchestrator._publish_sealed_authority(authority_dir, payload)
    finally:
        os.umask(prior_umask)
    assert result["package_self_verified"] is True
    assert result["authority"]["mode_octal"] == "0644"
    assert result["seal"]["mode_octal"] == "0644"
    assert stat.S_IMODE(authority_dir.stat().st_mode) == 0o755
    verified, authority_identity, seal_identity = orchestrator.verify_authority_package(
        authority_dir / "authority.json",
        result["package_id"],
    )
    assert verified == payload
    assert authority_identity == result["authority"]
    assert seal_identity == result["seal"]


def test_lifecycle_receipt_modes_are_independent_of_umask(
    tmp_path: Path,
    runner: ModuleType,
    verifier: ModuleType,
    contract: ModuleType,
) -> None:
    runner._activate_identity_contract(contract)
    verifier._activate_identity_contract(contract)
    prior_umask = os.umask(0o077)
    try:
        runner_identity = runner._write_once(
            (tmp_path / "runner.json").resolve(),
            b"{}\n",
        )
        verifier_identity = verifier._write_exclusive(
            (tmp_path / "verifier.json").resolve(),
            b"{}\n",
        )
    finally:
        os.umask(prior_umask)
    assert runner_identity["mode_octal"] == "0644"
    assert verifier_identity["mode_octal"] == "0644"


def test_orchestrator_same_fd_read_rejects_link_count_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    orchestrator: ModuleType,
) -> None:
    target = (tmp_path / "input.json").resolve()
    target.write_text("{}\n", encoding="utf-8")
    real_fstat = os.fstat
    call_count = 0

    def drifting_fstat(descriptor: int):
        nonlocal call_count
        record = real_fstat(descriptor)
        call_count += 1
        if call_count != 2:
            return record
        return SimpleNamespace(
            st_dev=record.st_dev,
            st_ino=record.st_ino,
            st_mode=record.st_mode,
            st_nlink=record.st_nlink + 1,
            st_size=record.st_size,
            st_mtime_ns=record.st_mtime_ns,
            st_ctime_ns=record.st_ctime_ns,
        )

    monkeypatch.setattr(orchestrator.os, "fstat", drifting_fstat)
    with pytest.raises(orchestrator.RecoveryError, match="changed during same-fd read"):
        orchestrator.read_regular(target, "link-count drift")


def test_verifier_can_publish_fail_closed_output_before_contract_activation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    verifier: ModuleType,
    contract: ModuleType,
) -> None:
    monkeypatch.setattr(verifier, "_ACTIVE_IDENTITY_CONTRACT", None)
    identity = verifier._write_exclusive(
        (tmp_path / "early-failure.json").resolve(),
        b'{"status":"FAIL_CLOSED"}\n',
    )
    assert contract.validate_full_identity(identity, "early failure output") == identity


def test_failure_filename_is_canonical_and_preselection_failure_does_not_consume(
    tmp_path: Path,
    runner: ModuleType,
) -> None:
    attempt_dir = tmp_path / runner.FORMAL_ATTEMPT_DIR
    attempt_dir.mkdir()
    paths = runner._attempt_paths(attempt_dir)
    assert paths["attempt_failure"].name == "attempt-failure.json"
    result = runner._close_postselection_failure(
        authority_path=(tmp_path / "authority.json").resolve(),
        authority_package_id="a" * 64,
        attempt_dir=attempt_dir.resolve(),
        attempt=runner.FORMAL_ATTEMPT,
        purpose="formal",
        unit="b1-smm4-preselection-12345678.service",
        error=runner.AttemptError("fixture"),
    )
    assert result is None
    assert list(attempt_dir.iterdir()) == []


def test_busy_lock_prevents_selection_and_does_not_consume(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    runner: ModuleType,
) -> None:
    heavy = tmp_path / "heavy.lock"
    second = tmp_path / "second.lock"
    third = tmp_path / "third.lock"
    blocker = heavy.open("w+")
    fcntl.flock(blocker.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    monkeypatch.setattr(runner, "HEAVY_LOCK", heavy)
    monkeypatch.setattr(runner, "PROD_SCALE_LOCKS", (second, third))
    attempt_dir = tmp_path / runner.FORMAL_ATTEMPT_DIR
    try:
        with pytest.raises(runner.AttemptError, match="busy before selection"):
            runner._acquire_formal_locks()
    finally:
        fcntl.flock(blocker.fileno(), fcntl.LOCK_UN)
        blocker.close()
    assert not attempt_dir.exists()
    assert not (attempt_dir / "selection.json").exists()
    assert not (attempt_dir / runner.ATTEMPT_FAILURE_NAME).exists()


def test_regular_snapshot_rejects_symlink_alias(
    tmp_path: Path,
    runner: ModuleType,
) -> None:
    target = tmp_path / "target.json"
    alias = tmp_path / "alias.json"
    target.write_text("{}\n", encoding="utf-8")
    alias.symlink_to(target)
    with pytest.raises(runner.AttemptError, match="canonical|symlink"):
        runner._read_regular(alias.resolve(strict=False).parent / alias.name, "alias")


def test_detached_verifier_uses_exact_shared_join(verifier: ModuleType) -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    assert "assert_identity_join(" in source
    assert 'payloads["selection"].get("authority_content_identity")' in source
    assert "selection authority identity join failed" in source


def test_manager_epoch_legacy_identity_bridge_is_exact_and_detached_replayable(
    orchestrator: ModuleType,
    verifier: ModuleType,
    contract: ModuleType,
) -> None:
    verifier._activate_identity_contract(contract)
    current = orchestrator.current_toolchain_snapshot()
    epoch, _ = orchestrator.capture_epoch()
    join = orchestrator.validate_manager_epoch_toolchain(epoch, current)
    authority = {
        **current,
        "manager_epoch_toolchain_join": join,
    }

    assert join["status"] == "PASS"
    assert set(join["tools"]) == {"attestor", "sudo", "python", "busctl"}
    assert verifier._manager_epoch_toolchain_join(authority, epoch) == join
    assert orchestrator.replay_manager_epoch_toolchain(authority, epoch) == join

    missing = copy.deepcopy(epoch)
    del missing["attestation_toolchain"]["attestor"]["requested_path"]
    with pytest.raises(orchestrator.RecoveryError, match="missing fields"):
        orchestrator.validate_manager_epoch_toolchain_shape(missing)

    extra = copy.deepcopy(epoch)
    extra["observation_toolchain"]["busctl"]["link_count"] = 1
    with pytest.raises(orchestrator.RecoveryError, match="unexpected fields"):
        orchestrator.validate_manager_epoch_toolchain_shape(extra)

    mode_drift = copy.deepcopy(epoch)
    mode_drift["attestation_toolchain"]["sudo"]["mode_octal"] = "0600"
    with pytest.raises(orchestrator.RecoveryError, match="mode and mode_octal disagree"):
        orchestrator.validate_manager_epoch_toolchain_shape(mode_drift)


def test_orchestrator_authority_load_rejects_manager_bridge_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    orchestrator: ModuleType,
) -> None:
    authority_path = (tmp_path / "authority.json").resolve()
    authority_path.write_text("{}\n", encoding="utf-8")
    authority_identity = orchestrator.identity(authority_path, "fixture authority")
    authority = {
        "schema_version": orchestrator.SCHEMA,
        "status": "PRE_RUN_AUTHORITY_PASS",
        "base_head": orchestrator.BASE_HEAD,
        "implementation_head": "f" * 40,
        "git": {"head": "f" * 40},
        "manager_epoch": {"epoch": "fixed"},
    }
    monkeypatch.setattr(
        orchestrator,
        "verify_authority_package",
        lambda *_args: (authority, authority_identity, {}),
    )
    monkeypatch.setattr(orchestrator, "git_snapshot", lambda _head: authority["git"])
    monkeypatch.setattr(orchestrator, "replay_current_toolchain", lambda _authority: {})
    monkeypatch.setattr(orchestrator, "replay_old_upper", lambda _authority: {})
    monkeypatch.setattr(orchestrator, "replay_composition", lambda _authority: {})
    monkeypatch.setattr(
        orchestrator,
        "capture_epoch",
        lambda: ({"epoch": "fixed"}, {}),
    )
    monkeypatch.setattr(orchestrator, "same_epoch", lambda *_args: True)

    def reject_bridge(*_args: object) -> None:
        raise orchestrator.RecoveryError("fixture manager bridge drift")

    monkeypatch.setattr(
        orchestrator,
        "replay_manager_epoch_toolchain",
        reject_bridge,
    )
    with pytest.raises(orchestrator.RecoveryError, match="manager bridge drift"):
        orchestrator.load_authority(authority_path, "a" * 64)


def test_selection_rechecks_manager_bridge_immediately_before_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    orchestrator: ModuleType,
    contract: ModuleType,
) -> None:
    authority_path = (tmp_path / "authority.json").resolve()
    authority_path.write_text("{}\n", encoding="utf-8")
    authority_identity = orchestrator.identity(authority_path, "fixture authority")
    authority = {
        "run_nonce": "fixture",
        "manager_epoch": {"epoch": "fixed"},
        "resource_contract": {},
    }
    monkeypatch.setattr(
        orchestrator,
        "load_authority",
        lambda *_args: (authority, authority_identity),
    )
    monkeypatch.setattr(orchestrator, "identity_contract", lambda: contract)
    monkeypatch.setattr(
        orchestrator,
        "capture_epoch",
        lambda: ({"epoch": "fixed"}, {}),
    )
    monkeypatch.setattr(orchestrator, "same_epoch", lambda *_args: True)

    def reject_bridge(*_args: object) -> None:
        raise orchestrator.RecoveryError("fixture manager bridge drift")

    monkeypatch.setattr(
        orchestrator,
        "replay_manager_epoch_toolchain",
        reject_bridge,
    )
    with pytest.raises(orchestrator.RecoveryError, match="manager bridge drift"):
        orchestrator.publish_selection(
            (tmp_path / "selection.json").resolve(),
            authority_path=authority_path,
            authority_package_id="a" * 64,
            attempt="synthetic-success-a001",
            purpose="synthetic_success",
            unit="b1-smm4-fixture.service",
            worker_argv=["worker"],
            payload_spec={},
        )
    assert not (tmp_path / "selection.json").exists()


def test_formal_namespace_and_closeout_paths_are_fixed(runner: ModuleType) -> None:
    runner._validate_attempt_name("smm4-formal-a004", "formal")
    with pytest.raises(runner.AttemptError):
        runner._validate_attempt_name("a002", "formal")
    assert runner.FORMAL_ATTEMPT_DIR == "formal-attempt-a004"
    assert runner.FORMAL_OUTPUT_DIR == "formal-a004"


def test_historical_inputs_are_copied_exclusively_and_composed(
    tmp_path: Path,
    orchestrator: ModuleType,
) -> None:
    if not all(path.is_dir() for path in (B0, SMM2_RUN, SMM3_RUN)):
        pytest.skip("immutable SMM2/SMM3 history is unavailable")
    source_inputs = orchestrator.validate_expected_inputs(
        source_root=B0,
        smm2_run=SMM2_RUN,
        smm3_run=SMM3_RUN,
    )
    snapshot_root = (tmp_path / "historical-inputs").resolve()
    inputs, sources, pins = orchestrator.snapshot_expected_inputs(
        source_inputs,
        snapshot_root,
    )
    assert set(pins["inputs"]) == set(orchestrator.COMPOSITION_INPUT_NAMES)
    assert set(orchestrator.OLD_UPPER_INPUT_NAMES) <= set(inputs)
    assert Path(inputs["formula"]["path"]).is_relative_to(snapshot_root)
    assert Path(inputs["old_r4_receipt"]["path"]).is_relative_to(snapshot_root)
    assert sources["formula"]["identity"]["path"] != inputs["formula"]["path"]
    for name in orchestrator.OLD_UPPER_INPUT_NAMES:
        assert Path(inputs[name]["path"]).is_relative_to(snapshot_root)
        assert set(inputs[name]) == {
            "path",
            "size_bytes",
            "sha256",
            "mode_octal",
            "device",
            "inode",
            "link_count",
        }
        assert inputs[name]["link_count"] == 1
    for name in orchestrator.COMPOSITION_INPUT_NAMES:
        assert pins["inputs"][name]["identity"] == inputs[name]
        assert inputs[name]["link_count"] == 1
    tools = orchestrator.current_toolchain_snapshot()["tools"]
    report = orchestrator._replay_composition_from_authority_parts(
        inputs,
        pins,
        tools,
    )
    assert report["status"] == "PASS"
    assert report["formal_attempt_admitted"] is True
    assert report["upper_bound_update_authorized"] is False
    with pytest.raises(orchestrator.RecoveryError, match="already|create"):
        orchestrator.snapshot_expected_inputs(
            source_inputs,
            snapshot_root,
        )


def test_old_upper_is_replayed_only_from_fresh_snapshots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    orchestrator: ModuleType,
) -> None:
    if not all(path.is_dir() for path in (B0, SMM2_RUN, SMM3_RUN)):
        pytest.skip("immutable R4 history is unavailable")
    source_inputs = orchestrator.validate_expected_inputs(
        source_root=B0,
        smm2_run=SMM2_RUN,
        smm3_run=SMM3_RUN,
    )
    snapshot_root = (tmp_path / "old-upper-snapshots").resolve()
    inputs, _, _ = orchestrator.snapshot_expected_inputs(
        source_inputs,
        snapshot_root,
    )
    current = orchestrator.current_toolchain_snapshot()
    module = orchestrator._load_old_upper_verifier(current["tools"])
    observed: dict[str, object] = {}

    def fake_execute(veripb_fd: int, formula_fd: int, proof_fd: int, timeout: int) -> dict[str, object]:
        observed["fds"] = (veripb_fd, formula_fd, proof_fd)
        observed["timeout"] = timeout
        assert all(Path(f"/proc/self/fd/{descriptor}").exists() for descriptor in observed["fds"])
        return {
            "exit_code": 0,
            "stdout": "s VERIFIED UNSATISFIABLE\n",
            "stderr": "",
            "status_lines": ["s VERIFIED UNSATISFIABLE"],
            "proof_status": "VERIFIED UNSATISFIABLE",
            "argv_shape": [
                "retained_veripb_fd",
                "--opb",
                "--stats",
                "retained_formula_fd",
                "retained_proof_fd",
            ],
            "execution": "retained_proc_self_fd_with_pass_fds",
        }

    monkeypatch.setattr(module, "_execute_veripb", fake_execute)
    monkeypatch.setattr(orchestrator, "_load_old_upper_verifier", lambda _tools: module)
    replay = orchestrator._replay_old_upper_from_authority_parts(
        inputs,
        current["tools"],
        current["binaries"],
        verifier_timeout_seconds=17,
    )
    assert replay["status"] == "PASS"
    assert replay["upper_bound_update_authorized"] is False
    assert replay["receipt_and_manifest_graph"]["historical_receipt_upper_bound_update_authorized"] is True
    assert replay["claim_boundary"]["ledger_upper_remains"] == [1188, 22]
    assert replay["claim_boundary"]["lower_remains"] == "absent"
    assert observed["timeout"] == 17
    assert all(
        Path(binding["identity"]["path"]).is_relative_to(snapshot_root)
        for binding in replay["inputs"].values()
    )


def test_old_upper_source_mode_anchor_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    orchestrator: ModuleType,
) -> None:
    if not all(path.is_dir() for path in (B0, SMM2_RUN, SMM3_RUN)):
        pytest.skip("immutable R4 history is unavailable")
    real_identity = orchestrator.identity

    def drifted_identity(path: Path, label: str) -> dict[str, object]:
        record = real_identity(path, label)
        if label == orchestrator.old_r4_member_key("resource_monitor.jsonl"):
            record["mode_octal"] = "0644"
        return record

    monkeypatch.setattr(orchestrator, "identity", drifted_identity)
    with pytest.raises(orchestrator.RecoveryError, match="historical byte identity drifted"):
        orchestrator.validate_expected_inputs(
            source_root=B0,
            smm2_run=SMM2_RUN,
            smm3_run=SMM3_RUN,
        )


@pytest.mark.parametrize(
    "drift_label",
    (
        "resume_authority",
        "build encoder.meta.json",
    ),
)
def test_remaining_historical_mode_anchors_fail_closed(
    drift_label: str,
    monkeypatch: pytest.MonkeyPatch,
    orchestrator: ModuleType,
) -> None:
    if not all(path.is_dir() for path in (B0, SMM2_RUN, SMM3_RUN)):
        pytest.skip("immutable SMM2/SMM3 history is unavailable")
    real_identity = orchestrator.identity

    def drifted_identity(path: Path, label: str) -> dict[str, object]:
        record = real_identity(path, label)
        if label == drift_label:
            record["mode_octal"] = "0600"
        return record

    monkeypatch.setattr(orchestrator, "identity", drifted_identity)
    with pytest.raises(orchestrator.RecoveryError, match="historical byte identity drifted"):
        orchestrator.validate_expected_inputs(
            source_root=B0,
            smm2_run=SMM2_RUN,
            smm3_run=SMM3_RUN,
        )


def test_detached_old_upper_replay_uses_authority_snapshots_and_veripb_pin(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    orchestrator: ModuleType,
    runner: ModuleType,
    verifier: ModuleType,
    contract: ModuleType,
) -> None:
    verifier._activate_identity_contract(contract)
    snapshot_root = (tmp_path / "fresh-history").resolve()
    snapshot_root.mkdir()
    inputs: dict[str, dict[str, object]] = {}
    pins: dict[str, dict[str, object]] = {}
    for index, name in enumerate(orchestrator.OLD_UPPER_INPUT_NAMES):
        path = (snapshot_root / f"{index:02d}-{name}.snapshot").resolve()
        path.write_bytes(f"{name}\n".encode())
        identity = runner._identity(path, name)
        inputs[name] = identity
        pins[name] = {
            "identity": identity,
            "content_projection": contract.canonical_content_projection(identity, name),
        }
    tool_path = (tmp_path / "old-upper-verifier.py").resolve()
    tool_path.write_text("# pinned fixture\n", encoding="utf-8")
    tool_identity = runner._identity(tool_path, "old-upper verifier")
    veripb_path = (tmp_path / "veripb").resolve()
    veripb_path.write_text("#!/bin/sh\n", encoding="utf-8")
    veripb_path.chmod(0o755)
    veripb_identity = runner._identity(veripb_path, "VeriPB")
    replay = {
        "schema_version": "b1_smm4_old_upper_snapshot_verification_v1",
        "status": "PASS",
        "decision": "OLD_R4_COMPLETE_BAND_AUTHORITY_RECOVERED_FROM_FRESH_SNAPSHOTS",
        "inputs": pins,
        "receipt_and_manifest_graph": {
            "historical_receipt_upper_bound_update_authorized": True,
        },
        "claim_boundary": {
            "ledger_upper_remains": [1188, 22],
            "lower_remains": "absent",
            "production_certified": False,
        },
        "upper_bound_update_authorized": False,
    }
    authority = {
        "tools": {"old_upper_verifier": tool_identity},
        "binaries": {"veripb": veripb_identity},
        "inputs": inputs,
        "old_upper_replay": replay,
    }
    module = ModuleType("_fake_old_upper")
    module.REQUIRED_INPUT_KEYS = orchestrator.OLD_UPPER_INPUT_NAMES

    def fake_verify_old_upper(
        snapshot_paths: dict[str, Path],
        pinned_inputs: dict[str, dict[str, object]],
        supplied_veripb_path: Path,
        supplied_veripb_pin: dict[str, object],
        *,
        verifier_timeout_seconds: int,
    ) -> dict[str, object]:
        assert set(snapshot_paths) == set(orchestrator.OLD_UPPER_INPUT_NAMES)
        assert all(path.is_relative_to(snapshot_root) for path in snapshot_paths.values())
        assert pinned_inputs == pins
        assert supplied_veripb_path == veripb_path
        assert supplied_veripb_pin == veripb_identity
        assert verifier_timeout_seconds == verifier.DEFAULT_VERIPB_TIMEOUT_SECONDS
        return replay

    module.verify_old_upper = fake_verify_old_upper
    monkeypatch.setattr(verifier, "_load_pinned_module", lambda *_args, **_kwargs: module)
    result = verifier._independent_replay_old_upper(authority, contract)
    assert result == replay
    assert result["upper_bound_update_authorized"] is False


def test_detached_pinned_loader_executes_actual_dataclass_module(
    orchestrator: ModuleType,
    runner: ModuleType,
    verifier: ModuleType,
    contract: ModuleType,
) -> None:
    verifier._activate_identity_contract(contract)
    path = (RESEARCH / "verify_smm4_old_upper_v1.py").resolve()
    expected = runner._identity(path, "old-upper verifier")
    previous = sys.modules.get("identity_contract_v1")
    sys.modules["identity_contract_v1"] = contract
    try:
        module = verifier._load_pinned_module(
            path,
            expected,
            "old-upper verifier",
        )
    finally:
        if previous is None:
            sys.modules.pop("identity_contract_v1", None)
        else:
            sys.modules["identity_contract_v1"] = previous
    assert module.REQUIRED_INPUT_KEYS == orchestrator.OLD_UPPER_INPUT_NAMES
    assert module.RetainedSnapshot.__module__.startswith("_smm4_verify_smm4_old_upper_v1_")


def test_loader_identity_argument_is_exact_full7(
    tmp_path: Path,
    runner: ModuleType,
    verifier: ModuleType,
    contract: ModuleType,
) -> None:
    verifier._activate_identity_contract(contract)
    path = (tmp_path / "worker.py").resolve()
    path.write_text("raise SystemExit(0)\n", encoding="utf-8")
    identity = runner._identity(path, "worker")
    serialized = verifier._loader_identity_argument(identity, "worker")
    assert json.loads(serialized) == identity
    assert serialized == json.dumps(identity, sort_keys=True, separators=(",", ":"))

    missing = copy.deepcopy(identity)
    missing.pop("inode")
    with pytest.raises(verifier.VerificationError, match="full7"):
        verifier._loader_identity_argument(missing, "worker")


@pytest.mark.parametrize(
    "mutation",
    (
        "authorization",
        "ledger",
        "package_id",
        "status",
    ),
)
def test_runner_never_derives_authorization_from_formal_purpose(
    mutation: str,
    runner: ModuleType,
) -> None:
    package_id = "a" * 64
    detached = {
        "status": "VERIFIED",
        "authority_package_id": package_id,
        "upper_bound_update_authorized": True,
        "ledger": {"upper": [1188, 18], "lower": "absent"},
    }
    valid_update, valid_ledger = runner._detached_authority_result(
        detached,
        "formal",
        package_id,
    )
    assert valid_update is True
    assert valid_ledger == detached["ledger"]

    changed = copy.deepcopy(detached)
    if mutation == "authorization":
        changed["upper_bound_update_authorized"] = False
    elif mutation == "ledger":
        changed["ledger"] = {"upper": [1188, 22], "lower": "absent"}
    elif mutation == "package_id":
        changed["authority_package_id"] = "b" * 64
    else:
        changed["status"] = "PASS"
    with pytest.raises(runner.AttemptError, match="exact expected authority"):
        runner._detached_authority_result(changed, "formal", package_id)


@pytest.mark.parametrize(
    "mutation",
    (
        "top_extra",
        "schema",
        "formula_transport",
        "proof_seed_hash",
        "proof_seed_inode",
        "translation_source",
        "content_reopened",
        "solver_transport",
        "verifier_transport",
    ),
)
def test_detached_retained_fd_provenance_is_exact_and_fail_closed(
    mutation: str,
    tmp_path: Path,
    runner: ModuleType,
    verifier: ModuleType,
    contract: ModuleType,
) -> None:
    verifier._activate_identity_contract(contract)
    formula_path = (tmp_path / "formula.opb").resolve()
    formula_path.write_bytes(b"* formula\n")
    formula_identity = runner._identity(formula_path, "formula")
    proof_path = (tmp_path / "proof.pbp").resolve()
    proof_path.write_bytes(b"")
    proof_seed = runner._identity(proof_path, "proof seed")
    proof_path.write_bytes(b"proof\n")
    proof_identity = runner._identity(proof_path, "proof final")
    translation_path = (tmp_path / "translation.py").resolve()
    translation_path.write_text("raise SystemExit(0)\n", encoding="utf-8")
    translation_identity = runner._identity(translation_path, "translation")
    provenance = {
        "schema_version": verifier.RETAINED_FD_PROVENANCE_SCHEMA,
        "formula": {
            "write_once_identity": formula_identity,
            "retained_open_access": "read_only",
            "validated_after_write_from_retained_fd": True,
            "roundingsat_input_transport": "proc_self_fd",
            "veripb_input_transport": "proc_self_fd",
            "same_parent_fd_retained_through_both_processes": True,
            "final_same_fd_identity": formula_identity,
        },
        "proof": {
            "exclusive_create_identity": proof_seed,
            "retained_open_access": "read_write_output",
            "created_with_o_excl": True,
            "roundingsat_proof_log_transport": "proc_self_fd",
            "size_monitor_source": "same_retained_fd_fstat",
            "post_solver_read_source": "same_retained_fd_pread",
            "veripb_input_transport": "same_retained_fd_proc_self_fd",
            "same_parent_fd_retained_through_both_processes": True,
            "final_same_fd_identity": proof_identity,
        },
        "translation_tool": {
            "source_identity": translation_identity,
            "retained_open_access": "read_only",
            "python_script_transport": "same_retained_fd_bootstrap",
            "child_full7_revalidation": True,
            "self_identity_read_redirected_to_same_retained_fd": True,
            "executed_from_validated_source_fd": True,
            "final_same_fd_identity": translation_identity,
        },
        "content_reopened_by_path_after_retained_validation": False,
    }
    internal = {
        "retained_fd_provenance": provenance,
        "translation_replay": {
            "tool_source_transport": "same_retained_fd_bootstrap",
            "child_full7_revalidation": True,
        },
        "solver": {
            "formula_transport": "retained_fd_procfs",
            "proof_log_transport": "retained_fd_procfs",
            "proof_size_monitor": "same_retained_fd_fstat",
        },
        "verifier": {
            "formula_transport": "same_retained_fd_procfs",
            "proof_transport": "same_retained_fd_procfs",
        },
    }
    authority = {"tools": {"translation_gate": translation_identity}}
    verifier._validate_retained_fd_provenance(
        internal,
        authority,
        formula_identity,
        proof_identity,
    )

    changed = copy.deepcopy(internal)
    if mutation == "top_extra":
        changed["retained_fd_provenance"]["unexpected"] = True
    elif mutation == "schema":
        changed["retained_fd_provenance"]["schema_version"] = "wrong"
    elif mutation == "formula_transport":
        changed["retained_fd_provenance"]["formula"]["veripb_input_transport"] = "path"
    elif mutation == "proof_seed_hash":
        changed["retained_fd_provenance"]["proof"]["exclusive_create_identity"]["sha256"] = "0" * 64
    elif mutation == "proof_seed_inode":
        changed["retained_fd_provenance"]["proof"]["exclusive_create_identity"]["inode"] += 1
    elif mutation == "translation_source":
        changed["retained_fd_provenance"]["translation_tool"]["source_identity"]["sha256"] = "0" * 64
    elif mutation == "content_reopened":
        changed["retained_fd_provenance"]["content_reopened_by_path_after_retained_validation"] = True
    elif mutation == "solver_transport":
        changed["solver"]["proof_log_transport"] = "path"
    else:
        changed["verifier"]["proof_transport"] = "path"
    with pytest.raises(verifier.VerificationError):
        verifier._validate_retained_fd_provenance(
            changed,
            authority,
            formula_identity,
            proof_identity,
        )


def test_formal_payload_and_detached_require_composition_replay(
    payload: ModuleType,
    verifier: ModuleType,
) -> None:
    payload_source = Path(payload.__file__).read_text(encoding="utf-8")
    verifier_source = Path(verifier.__file__).read_text(encoding="utf-8")
    assert "orchestrator.replay_old_upper(authority)" in payload_source
    assert "orchestrator.replay_composition(authority)" in payload_source
    assert "_independent_replay_old_upper(" in verifier_source
    assert "_independent_replay_composition(" in verifier_source
    assert '"old_upper_replay": payloads["_old_upper_replay"]' in verifier_source
    assert '"composition_replay": payloads["_composition_replay"]' in verifier_source
