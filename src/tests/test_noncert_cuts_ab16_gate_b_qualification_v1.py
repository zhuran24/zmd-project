from __future__ import annotations

import ctypes
from collections.abc import Mapping
from copy import deepcopy
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import time
from types import ModuleType
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
NATIVE_HELPER = RESEARCH / "ab16_native_budget_helper_x86_64_v1.so"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BOOTSTRAP = _load(
    "noncert_cuts_ab16_gate_b_qualification_bootstrap_tested",
    RESEARCH / "ab16_campaign_bootstrap_v2.py",
)
QUALIFICATION = _load(
    "noncert_cuts_ab16_gate_b_qualification_v1_tested",
    RESEARCH / "ab16_gate_b_qualification_v1.py",
)
RESOURCE_ADMISSION = _load(
    "noncert_cuts_ab16_resource_admission_v1_tested",
    RESEARCH / "ab16_resource_admission_v1.py",
)


def _native_helper_full() -> dict[str, object]:
    return BOOTSTRAP.authority.snapshot_tool(NATIVE_HELPER)[1]


_CALIBRATION_TOOL_PLANNED_ROLES = {
    "aggregator": "script.ab16_resource_calibration_aggregator_v1",
    "alternate_replayer": "script.replay_ab16_resource_calibration_alt_v1",
    "fd_loader": "script.ab16_resource_calibration_fd_loader_v1",
    "observer_harness": "script.ab16_resource_calibration_harness_v1",
    "package_verifier": "script.ab16_resource_calibration_package_v1",
    "primary_replayer": "script.replay_ab16_resource_calibration_v1",
    "protocol": "script.ab16_resource_calibration_v1",
    "runner": "script.ab16_resource_calibration_runner_v1",
    "workload": "script.ab16_resource_calibration_workloads_v1",
}


def _calibration_tool_planned_identities(
    tmp_path: Path,
) -> dict[str, dict[str, object]]:
    assert BOOTSTRAP.CALIBRATION_TOOL_PLANNED_ROLES == (
        _CALIBRATION_TOOL_PLANNED_ROLES
    )
    return {
        planned_role: {
            "path": str(tmp_path / f"calibration-tool-{index}.py"),
            "sha256": f"{index:x}" * 64,
            "size_bytes": index,
        }
        for index, planned_role in enumerate(
            _CALIBRATION_TOOL_PLANNED_ROLES.values(),
            start=1,
        )
    }


def test_qualify_cli_requires_explicit_native_helper_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as captured:
        QUALIFICATION._parse_args(  # noqa: SLF001
            [
                "qualify",
                "--repository-root",
                "/fixture/repository",
                "--campaign-dir",
                "/fixture/campaign",
                "--output-dir",
                "/fixture/output",
                "--gate-a-authority-root",
                "/fixture/gate-a-root",
                "--gate-a-receipt",
                "/fixture/gate-a.json",
                "--offline-candidate",
                "/fixture/candidate.json",
                "--planned-source-observation",
                "/fixture/planned.json",
                "--approval-id",
                "gate-b-fixture",
                "--history-freeze-manifest",
                "/fixture/history.json",
                "--cuts-mandatory-schedule",
                "/fixture/schedule.md",
                "--legacy-control-a002",
                "/fixture/control.json",
            ]
        )
    assert captured.value.code == 2
    assert "--native-budget-helper" in capsys.readouterr().err


def _gate_b_lock_identities() -> list[dict[str, object]]:
    return [
        {
            "device": 100 + index,
            "inode": 200 + index,
            "mode": 0o600,
            "nlink": 1,
            "path": path,
            "uid": os.getuid(),
        }
        for index, path in enumerate(RESOURCE_ADMISSION.LOCK_PATHS)
    ]


def _stage_minimums(stage: str) -> dict[str, int]:
    requirements = RESOURCE_ADMISSION.RESOURCE_PROFILES[stage]["requirements"]
    assert isinstance(requirements, dict)
    result: dict[str, int] = {}
    for dimension in ("disk", "memory", "swap"):
        value = requirements[dimension]
        assert isinstance(value, dict)
        minimum = value["minimum_available_bytes"]
        assert type(minimum) is int
        result[dimension] = minimum
    return result


def _observation_context(tmp_path: Path, stage: str) -> dict[str, object]:
    kind = {
        RESOURCE_ADMISSION.FULL_PREFLIGHT: "GATE_A_FULL_PREFLIGHT",
        RESOURCE_ADMISSION.GATE_B_QUALIFICATION: (
            "GATE_B_QUALIFICATION_PUBLICATION"
        ),
        RESOURCE_ADMISSION.FORMAL_ORGANIC_ARM: "FORMAL_INITIAL_POST_LOCK",
    }[stage]
    sequence = 0 if kind == "FORMAL_INITIAL_POST_LOCK" else (
        2 if kind == "GATE_B_QUALIFICATION_PUBLICATION" else 1
    )
    return {
        "authority_id": "a" * 64,
        "disk_path": str(tmp_path.absolute()),
        "kind": kind,
        "ordinal": 0,
        "scope_id": "b" * 64,
        "sequence": sequence,
        "slot": "",
        "target": f"fixture:{stage}",
    }


def _admit_at(
    tmp_path: Path,
    *,
    stage: str,
    disk: int,
    memory: int,
    swap: int,
) -> dict[str, object]:
    return RESOURCE_ADMISSION.evaluate_resource_admission(
        tmp_path,
        stage=stage,
        lock_identities=_gate_b_lock_identities(),
        lock_identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
        observation_context=_observation_context(tmp_path, stage),
        meminfo={"MemAvailable": memory, "SwapFree": swap},
        disk_free=disk,
        conflicts=[],
        observed_at_utc="2026-07-31T00:00:00Z",
    )


def _track_resource_directory_descriptors(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[int], dict[int, int]]:
    real_open = RESOURCE_ADMISSION.os.open
    real_close = RESOURCE_ADMISSION.os.close
    opened: list[int] = []
    close_counts: dict[int, int] = {}

    def tracked_open(*args: object, **kwargs: object) -> int:
        descriptor = real_open(*args, **kwargs)
        flags = args[1]
        assert isinstance(flags, int)
        if flags & os.O_DIRECTORY:
            opened.append(descriptor)
            close_counts[descriptor] = 0
        return descriptor

    def tracked_close(descriptor: int) -> None:
        if descriptor in close_counts:
            close_counts[descriptor] += 1
        real_close(descriptor)

    monkeypatch.setattr(RESOURCE_ADMISSION.os, "open", tracked_open)
    monkeypatch.setattr(RESOURCE_ADMISSION.os, "close", tracked_close)
    return opened, close_counts


def test_disk_measurement_rejects_target_replacement_between_fstatvfs_and_rejoin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "disk-target"
    moved = tmp_path / "disk-target-retained"
    target.mkdir()
    real_fstatvfs = RESOURCE_ADMISSION.os.fstatvfs

    def replace_after_measurement(descriptor: int) -> os.statvfs_result:
        observed = real_fstatvfs(descriptor)
        target.rename(moved)
        target.mkdir()
        (target / "unknown-replacement").write_bytes(b"must remain")
        return observed

    monkeypatch.setattr(
        RESOURCE_ADMISSION.os,
        "fstatvfs",
        replace_after_measurement,
    )
    with pytest.raises(
        RESOURCE_ADMISSION.ResourceAdmissionError,
        match=(
            "RESOURCE_MEASUREMENT_UNTRUSTED: "
            "disk target absolute-path identity changed after measurement"
        ),
    ):
        RESOURCE_ADMISSION._measure_disk_target(  # noqa: SLF001
            target,
            disk_free=1,
        )

    assert moved.is_dir()
    assert (target / "unknown-replacement").read_bytes() == b"must remain"


def test_disk_measurement_closes_each_descriptor_once_on_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "disk-target"
    target.mkdir()
    opened, close_counts = _track_resource_directory_descriptors(monkeypatch)

    disk_free, identity = RESOURCE_ADMISSION._measure_disk_target(  # noqa: SLF001
        target,
        disk_free=123,
    )

    assert disk_free == 123
    assert identity["path"] == str(target.absolute())
    assert opened
    assert len(opened) == len(set(opened))
    assert close_counts == dict.fromkeys(opened, 1)


def test_disk_measurement_preserves_baseexception_and_closes_each_descriptor_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MeasurementAbort(BaseException):
        pass

    target = tmp_path / "disk-target"
    target.mkdir()
    opened, close_counts = _track_resource_directory_descriptors(monkeypatch)

    def abort_measurement(_descriptor: int) -> None:
        raise MeasurementAbort("controlled fstatvfs abort")

    monkeypatch.setattr(RESOURCE_ADMISSION.os, "fstatvfs", abort_measurement)
    with pytest.raises(MeasurementAbort, match="controlled fstatvfs abort"):
        RESOURCE_ADMISSION._measure_disk_target(  # noqa: SLF001
            target,
            disk_free=123,
        )

    assert opened
    assert close_counts == dict.fromkeys(opened, 1)


def test_disk_measurement_converts_oserror_and_closes_each_descriptor_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "disk-target"
    target.mkdir()
    opened, close_counts = _track_resource_directory_descriptors(monkeypatch)

    def fail_measurement(_descriptor: int) -> None:
        raise OSError("controlled fstatvfs failure")

    monkeypatch.setattr(RESOURCE_ADMISSION.os, "fstatvfs", fail_measurement)
    with pytest.raises(
        RESOURCE_ADMISSION.ResourceAdmissionError,
        match=(
            "RESOURCE_MEASUREMENT_UNAVAILABLE: "
            "disk target measurement: controlled fstatvfs failure"
        ),
    ):
        RESOURCE_ADMISSION._measure_disk_target(  # noqa: SLF001
            target,
            disk_free=123,
        )

    assert opened
    assert close_counts == dict.fromkeys(opened, 1)


def test_disk_measurement_close_failure_does_not_mask_primary_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MeasurementAbort(BaseException):
        pass

    target = tmp_path / "disk-target"
    target.mkdir()
    opened, close_counts = _track_resource_directory_descriptors(monkeypatch)
    tracked_close = RESOURCE_ADMISSION.os.close
    injected = False

    def abort_measurement(_descriptor: int) -> None:
        raise MeasurementAbort("controlled primary abort")

    def fail_one_close(descriptor: int) -> None:
        nonlocal injected
        tracked_close(descriptor)
        if descriptor in close_counts and not injected:
            injected = True
            raise RuntimeError("controlled close failure")

    monkeypatch.setattr(RESOURCE_ADMISSION.os, "fstatvfs", abort_measurement)
    monkeypatch.setattr(RESOURCE_ADMISSION.os, "close", fail_one_close)
    with pytest.raises(MeasurementAbort, match="controlled primary abort") as raised:
        RESOURCE_ADMISSION._measure_disk_target(  # noqa: SLF001
            target,
            disk_free=123,
        )

    assert injected is True
    assert opened
    assert close_counts == dict.fromkeys(opened, 1)
    assert any(
        "controlled close failure" in note
        for note in getattr(raised.value, "__notes__", ())
    )


def _renderer(path: Path) -> Path:
    path.write_text(
        """
import json

def _render(request):
    record = dict(request["record"])
    record["publisher"] = dict(globals()["__ab16_gate_b_owner_context__"])
    return (
        json.dumps(
            record,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\\n"
    ).encode("utf-8")

def render_gate_b_epoch_observation(request):
    return _render(request)

def render_gate_b_approval(request):
    return _render(request)
""".lstrip(),
        encoding="utf-8",
    )
    return path


def _identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    metadata = path.stat()
    return {
        "mode": stat.S_IMODE(metadata.st_mode),
        "path": str(path.resolve()),
        "sha256": __import__("hashlib").sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _open_competing_locks(paths: tuple[Path, ...]) -> list[int]:
    descriptors: list[int] = []
    try:
        for path in paths:
            descriptor = os.open(path, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
            descriptors.append(descriptor)
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise
    return descriptors


def _handoff_request(
    owner: object,
    *,
    epoch_identity: dict[str, object],
    approval_identity: dict[str, object],
) -> dict[str, object]:
    return {
        "action": "BOOTSTRAP_HANDOFF",
        "actor": owner.actor,
        "campaign_root_identity": {
            "path": "/fixture/campaign-root.json",
            "sha256": "c" * 64,
            "size_bytes": 1,
        },
        "gate1_selection_identity": {
            "path": "/fixture/gate1-selection.json",
            "sha256": "d" * 64,
            "size_bytes": 1,
        },
        "gate_b_approval_identity": approval_identity,
        "gate_b_epoch_identity": epoch_identity,
        "lock_identities": owner.lock_identities,
        "publisher_sequences": [1, 2],
        "schema": QUALIFICATION.HANDOFF_REQUEST_SCHEMA,
        "session_id": owner.session_id,
    }


def _fd_count() -> int:
    return len(os.listdir("/proc/self/fd"))


def _install_fake_session_bus(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[socket.socket, dict[str, str]]:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    runtime.chmod(0o700)
    bus = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        runtime_descriptor = os.open(runtime, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            bus.bind(f"/proc/self/fd/{runtime_descriptor}/bus")
        finally:
            os.close(runtime_descriptor)
    except BaseException:
        bus.close()
        raise
    uid = os.getuid()
    expected_runtime = f"/run/user/{uid}"
    expected = {
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={expected_runtime}/bus",
        "XDG_RUNTIME_DIR": expected_runtime,
    }
    real_open_directory = QUALIFICATION._open_directory  # noqa: SLF001

    def open_fake_runtime(path: Path | str) -> int:
        assert Path(os.path.abspath(os.fspath(path))) == Path(expected_runtime)
        return real_open_directory(runtime)

    monkeypatch.setattr(QUALIFICATION, "_open_directory", open_fake_runtime)
    for key, value in expected.items():
        monkeypatch.setenv(key, value)
    return bus, expected


def _unstarted_owner(tmp_path: Path) -> object:
    return QUALIFICATION.PersistentGateBOwner(
        python_path=Path(os.path.realpath(sys.executable)),
        owner_source_path=RESEARCH / "ab16_gate_b_qualification_v1.py",
        renderer_source_path=tmp_path / "renderer.py",
        renderer_identity={},
        mechanical_publisher="fixture",
        owner_driver="fixture",
        lock_paths=tuple(tmp_path / f"qualification-{index}.lock" for index in range(3)),
    )


def test_preflight_environment_adds_only_verified_fixed_session_bus(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus, expected = _install_fake_session_bus(tmp_path, monkeypatch)
    try:
        before = _fd_count()
        environment = QUALIFICATION._preflight_environment()  # noqa: SLF001
        assert _fd_count() == before
    finally:
        bus.close()

    assert {key: environment[key] for key in expected} == expected
    assert set(environment) == {
        "DBUS_SESSION_BUS_ADDRESS",
        "LANG",
        "LC_ALL",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONHASHSEED",
        "PYTHONNOUSERSITE",
        "TZ",
        "XDG_RUNTIME_DIR",
    }
    clean = QUALIFICATION._clean_environment()  # noqa: SLF001
    assert "DBUS_SESSION_BUS_ADDRESS" not in clean
    assert "XDG_RUNTIME_DIR" not in clean


def test_preflight_environment_ignores_inherited_session_bus_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus, expected = _install_fake_session_bus(tmp_path, monkeypatch)
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/tmp/untrusted-runtime")
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/tmp/untrusted-bus")
    monkeypatch.setenv("PYTEST_ADDOPTS", "--basetemp=/tmp/untrusted")
    monkeypatch.setenv("PYTEST_PLUGINS", "untrusted_plugin")
    monkeypatch.setenv("PYTHONPATH", "/tmp/untrusted-python")
    try:
        environment = QUALIFICATION._preflight_environment()  # noqa: SLF001
    finally:
        bus.close()
    assert {key: environment[key] for key in expected} == expected
    assert "PYTEST_ADDOPTS" not in environment
    assert "PYTEST_PLUGINS" not in environment
    assert "PYTHONPATH" not in environment


def test_fake_session_bus_fixture_accepts_long_pytest_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_root = tmp_path / ("long-" + ("x" * 100))
    long_root.mkdir()
    assert len(os.fsencode(long_root / "runtime" / "bus")) > 107
    bus, expected = _install_fake_session_bus(long_root, monkeypatch)
    try:
        environment = QUALIFICATION._preflight_environment()  # noqa: SLF001
    finally:
        bus.close()
    assert {key: environment[key] for key in expected} == expected


def test_gate_b_final_preflight_receipt_uses_unterminated_canonical_contract(
    tmp_path: Path,
) -> None:
    receipt = tmp_path / "receipt.json"
    value = {"schema_version": "fixture-v1", "status": "PASS"}
    raw = QUALIFICATION._canonical_json(value)[:-1]  # noqa: SLF001
    receipt.write_bytes(raw)
    receipt.chmod(0o444)
    before = _fd_count()
    observed, identity = BOOTSTRAP._unterminated_canonical_mode_record(  # noqa: SLF001
        receipt,
        "Gate-B final full-preflight receipt",
    )
    assert _fd_count() == before
    assert observed == value
    assert identity == {
        "mode": 0o444,
        "path": str(receipt),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }

    terminated = tmp_path / "terminated.json"
    terminated.write_bytes(QUALIFICATION._canonical_json(value))  # noqa: SLF001
    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="canonical unterminated strict JSON",
    ):
        BOOTSTRAP._unterminated_canonical_mode_record(  # noqa: SLF001
            terminated,
            "Gate-B final full-preflight receipt",
        )
    assert _fd_count() == before


def test_bootstrap_final_preflight_replays_gate_a_with_unterminated_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ParserReached(RuntimeError):
        pass

    record = {key: None for key in BOOTSTRAP.FINAL_FULL_PREFLIGHT_KEYS}
    record["command"] = {
        "argv": [],
        "execution_strategy": "fixture",
        "loader_identity": {"sha256": "a" * 64, "size_bytes": 1},
    }
    gate_a = {
        "full_preflight_receipt_identity": {
            "mode": 0o444,
            "path": "/fixture/gate-a-preflight.json",
            "sha256": "b" * 64,
            "size_bytes": 1,
        }
    }
    planned = {
        "input.preflight_gate": {},
        "script.ab16_preflight_qualification_v1": {},
        "script.ab16_pytest_collection_plugin_v1": {},
        "script.ab16_pytest_collection_protocol_v1": {},
        "script.gate_a_validation_v2": {},
        "system.python3_13": {},
    }
    monkeypatch.setattr(BOOTSTRAP, "_exact_keys", lambda value, *_args: value)
    monkeypatch.setattr(BOOTSTRAP, "_utc", lambda *_args: None)
    monkeypatch.setattr(BOOTSTRAP, "_mode_identity", lambda *_args: {})
    monkeypatch.setattr(
        BOOTSTRAP,
        "_project_mode_identity",
        lambda *_args: {"mode": 0o555, "path": "/fixture/tool", "sha256": "c" * 64, "size_bytes": 1},
    )

    def parser(path: Path | str, label: str) -> tuple[object, dict[str, object]]:
        assert path == "/fixture/gate-a-preflight.json"
        assert label == "Gate-A full-preflight receipt"
        raise ParserReached

    monkeypatch.setattr(BOOTSTRAP, "_unterminated_canonical_mode_record", parser)
    with pytest.raises(ParserReached):
        BOOTSTRAP._validate_final_full_preflight(  # noqa: SLF001
            record,
            gate_a=gate_a,
            planned=planned,
            receipt_identity={
                "mode": 0o444,
                "path": "/fixture/final-preflight.json",
                "sha256": "f" * 64,
                "size_bytes": 1,
            },
        )


def test_bootstrap_campaign_replays_gate_b_preflight_with_unterminated_parser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ParserReached(RuntimeError):
        pass

    campaign = tmp_path / "campaign"
    repository = tmp_path / "repository"
    gate_a_path = tmp_path / "gate-a.json"
    candidate_path = tmp_path / "candidate.json"
    preregistration_path = tmp_path / "preregistration.json"
    gate_b_path = tmp_path / "gate-b.json"
    final_preflight_path = tmp_path / "final-preflight.json"
    source_digest = "a" * 64
    scalar_binding = {
        "planned_source_set_digest": source_digest,
        "repository_head": "b" * 40,
        "repository_root": str(repository),
        "run_nonce": campaign.name,
        "target_campaign_dir": str(campaign),
    }
    gate_a_identity = {
        "path": str(gate_a_path),
        "sha256": "c" * 64,
        "size_bytes": 1,
    }
    candidate_identity = {
        "path": str(candidate_path),
        "sha256": "d" * 64,
        "size_bytes": 1,
    }
    preregistration_identity = {
        "path": str(preregistration_path),
        "sha256": "e" * 64,
        "size_bytes": 1,
    }
    final_preflight_identity = {
        "mode": 0o444,
        "path": str(final_preflight_path),
        "sha256": "f" * 64,
        "size_bytes": 1,
    }
    verifier_identity = {
        "device": 1,
        "inode": 1,
        "mode": 0o644,
        "mode_octal": "0644",
        "path": str(tmp_path / "package_independent_verifier_v1.py"),
        "sha256": "1" * 64,
        "size_bytes": 1,
    }
    native_helper_identity = _native_helper_full()
    resource_profile_path = tmp_path / "resource-budget-profile.json"
    resource_profile_identity = {
        "mode": 0o444,
        "path": str(resource_profile_path),
        "sha256": "6" * 64,
        "size_bytes": 1,
    }
    bootstrap_contract_identity = {
        "path": str(
            campaign
            / "bootstrap-authority/bootstrap-budget-contract.json"
        ),
        "sha256": "7" * 64,
        "size_bytes": 1,
    }
    formal_contract_identity = {
        "path": str(
            campaign
            / "formal-ab16/artifacts/formal-root-budget-contract.json"
        ),
        "sha256": "8" * 64,
        "size_bytes": 1,
    }
    calibration_identities = {
        stage: {
            "path": str(tmp_path / f"calibration-{index}.json"),
            "sha256": f"{index + 8:x}" * 64,
            "size_bytes": index,
        }
        for index, stage in enumerate(
            BOOTSTRAP.RESOURCE_CALIBRATION_STAGES,
            start=1,
        )
    }
    budget_binding = {
        "bootstrap_budget_contract_identity": (
            bootstrap_contract_identity
        ),
        "formal_root_budget_contract_identity": formal_contract_identity,
        "resource_calibration_bundle_identities": (
            calibration_identities
        ),
        "resource_budget_profile_identity": resource_profile_identity,
    }
    planned = {
        "script.package_independent_verifier_v1": verifier_identity,
        "system.native_budget_helper": native_helper_identity,
        **_calibration_tool_planned_identities(tmp_path),
    }
    gate_a = {**scalar_binding, "approval_id": "gate-a"}
    candidate = {
        **scalar_binding,
        "gate_a_receipt_identity": gate_a_identity,
        "native_budget_helper_source_identity": native_helper_identity,
        "package_verifier_source_identity": verifier_identity,
        "path_preregistration_identity": preregistration_identity,
        "planned_source_identities": planned,
        **budget_binding,
    }
    gate_b = {
        **scalar_binding,
        "approval_id": "gate-b",
        "candidate_identity": candidate_identity,
        "final_full_preflight_receipt_identity": final_preflight_identity,
        "gate_a_receipt_identity": gate_a_identity,
        "native_budget_helper_source_identity": native_helper_identity,
        "package_verifier_source_identity": verifier_identity,
        "pre_full_resource_gate_identity": {
            "mode": 0o444,
            "path": str(tmp_path / "resource-gates/before-final-full-preflight.json"),
            "sha256": "3" * 64,
            "size_bytes": 1,
        },
        "pre_publication_resource_gate_identity": {
            "mode": 0o444,
            "path": str(tmp_path / "resource-gates/after-final-full-preflight.json"),
            "sha256": "4" * 64,
            "size_bytes": 1,
        },
        "publisher": {
            "actor": {"pid": 1, "pid_starttime": "1"},
            "qualification_session": {
                "lock_identities": [],
                "session_id": "5" * 64,
            },
        },
        **budget_binding,
    }
    records = {
        "Gate-A receipt": (gate_a, gate_a_identity),
        "offline candidate": (candidate, candidate_identity),
        "AB16 path preregistration": ({}, preregistration_identity),
        "Gate-B approval": (
            gate_b,
            {"path": str(gate_b_path), "sha256": "2" * 64, "size_bytes": 1},
        ),
    }
    monkeypatch.setattr(BOOTSTRAP, "_assert_campaign_absent", lambda *_args: None)
    def canonical_record(
        _path: Path | str,
        label: str,
    ) -> tuple[object, dict[str, object]]:
        if label.endswith("resource calibration authorization bundle"):
            stage = label.split(" ", 1)[0]
            return (
                {"fixture": True, "stage": stage},
                calibration_identities[stage],
            )
        return records[label]

    monkeypatch.setattr(BOOTSTRAP, "_canonical_record", canonical_record)
    monkeypatch.setattr(BOOTSTRAP, "_validate_gate_a", lambda value: value)
    monkeypatch.setattr(BOOTSTRAP, "validate_candidate", lambda value: value)
    monkeypatch.setattr(
        BOOTSTRAP,
        "validate_path_preregistration",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(BOOTSTRAP, "_validate_gate_b", lambda value: value)
    monkeypatch.setattr(
        BOOTSTRAP,
        "_resource_budget_profile",
        lambda *_args, **_kwargs: ({}, resource_profile_identity),
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_resource_calibration_bundle_sources",
        lambda _paths: (
            {
                stage: tmp_path / f"{stage}.json"
                for stage in BOOTSTRAP.RESOURCE_CALIBRATION_STAGES
            },
            calibration_identities,
        ),
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_planned_budget_contracts",
        lambda **_kwargs: {
            "bootstrap_identity": bootstrap_contract_identity,
            "formal_identity": formal_contract_identity,
        },
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_bootstrap_runtime_budget_bindings",
        lambda **_kwargs: {
            "artifact_class": "metadata",
            "maximum_bytes": 4096,
            "relative_path": "formal-root-budget-handoff.json",
        },
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_planned_source_identities",
        lambda **_kwargs: (planned, {}, {}, {}),
    )
    monkeypatch.setattr(BOOTSTRAP, "_source_set_digest", lambda _planned: source_digest)
    monkeypatch.setattr(
        BOOTSTRAP,
        "_read_gate_b_resource_gate",
        lambda identity, **_kwargs: ({}, dict(identity)),
    )
    closure_replays: list[Mapping[str, Mapping[str, object]] | None] = []

    def replay_prepackage_closure(
        *,
        planned: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        closure_replays.append(planned)

    monkeypatch.setattr(
        BOOTSTRAP,
        "_replay_prepackage_closure",
        replay_prepackage_closure,
    )

    def parser(path: Path | str, label: str) -> tuple[object, dict[str, object]]:
        assert path == final_preflight_path
        assert label == "Gate-B final full-preflight receipt"
        raise ParserReached

    monkeypatch.setattr(BOOTSTRAP, "_unterminated_canonical_mode_record", parser)
    with pytest.raises(ParserReached):
        BOOTSTRAP.bootstrap_campaign(
            campaign_dir=campaign,
            repository_root=repository,
            gate_a_receipt=gate_a_path,
            offline_candidate=candidate_path,
            gate_b_approval=gate_b_path,
            resource_budget_profile=resource_profile_path,
            resource_calibration_bundle_paths={
                stage: tmp_path / f"{stage}.json"
                for stage in BOOTSTRAP.RESOURCE_CALIBRATION_STAGES
            },
            strict_input_paths={},
            system_tool_paths={},
        )
    assert closure_replays == [None, None]


def test_bootstrap_fd_execution_resolves_renderer_identity(
    tmp_path: Path,
) -> None:
    source = RESEARCH / "ab16_campaign_bootstrap_v2.py"
    output = tmp_path / "gate-b-record.json"
    driver = """
import os
from pathlib import Path
import sys
import types

source = Path(sys.argv[1])
descriptor = os.open(source, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
try:
    fd_path = f"/proc/self/fd/{descriptor}"
    raw = Path(fd_path).read_bytes()
    module = types.ModuleType("_ab16_bootstrap_from_retained_fd")
    module.__file__ = fd_path
    module.__package__ = None
    sys.modules[module.__name__] = module
    exec(compile(raw, fd_path, "exec", dont_inherit=True), module.__dict__)
    publisher = module._gate_b_publisher_for_parent(Path(sys.argv[2]))
    if publisher["renderer_source"]["path"] != str(source.resolve()):
        raise RuntimeError("renderer source did not resolve to its named source")
finally:
    os.close(descriptor)
""".lstrip()
    completed = subprocess.run(
        [os.path.realpath(sys.executable), "-I", "-B", "-c", driver, str(source), str(output)],
        check=False,
        close_fds=True,
        cwd=ROOT,
        env={
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        },
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert completed.stdout == b""
    assert completed.stderr == b""


def test_preflight_environment_rejects_non_socket_bus_without_fd_leak(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    runtime.chmod(0o700)
    (runtime / "bus").write_bytes(b"not-a-socket")
    uid = os.getuid()
    expected_runtime = f"/run/user/{uid}"
    monkeypatch.setenv("XDG_RUNTIME_DIR", expected_runtime)
    monkeypatch.setenv(
        "DBUS_SESSION_BUS_ADDRESS",
        f"unix:path={expected_runtime}/bus",
    )
    real_open_directory = QUALIFICATION._open_directory  # noqa: SLF001
    monkeypatch.setattr(
        QUALIFICATION,
        "_open_directory",
        lambda _path: real_open_directory(runtime),
    )
    before = _fd_count()
    with pytest.raises(
        QUALIFICATION.QualificationError,
        match="session bus node failed validation",
    ):
        QUALIFICATION._preflight_environment()  # noqa: SLF001
    assert _fd_count() == before


def test_pinned_gate_a_preflight_uses_verified_session_bus_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entrypoint = tmp_path / "entrypoint.py"
    entrypoint.write_bytes(b"raise AssertionError('not executed')\n")
    expected_environment = {
        **QUALIFICATION._clean_environment(),  # noqa: SLF001
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1234/bus",
        "XDG_RUNTIME_DIR": "/run/user/1234",
    }
    captured: dict[str, object] = {}

    def run(_argv: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(
            returncode=0,
            stderr=b"",
            stdout=b'{"status":"PASS"}\n',
        )

    monkeypatch.setattr(
        QUALIFICATION,
        "_preflight_environment",
        lambda: dict(expected_environment),
    )
    monkeypatch.setattr(QUALIFICATION.subprocess, "run", run)
    before = _fd_count()
    inherited = {
        path: os.open("/dev/null", os.O_RDONLY)
        for path in QUALIFICATION.LOCK_PATHS
    }
    try:
        QUALIFICATION._run_pinned_gate_a_preflight(  # noqa: SLF001
            {
                "observation_identity": {
                    "path": str(tmp_path / "observation.json"),
                    "sha256": "a" * 64,
                    "size_bytes": 1,
                },
                "planned_digest": "b" * 64,
                "repository": tmp_path,
                "scripts": {"gate_a_pinned_entrypoint_v2": entrypoint},
                "system_paths": {"python3_13": Path(os.path.realpath(sys.executable))},
            },
            SimpleNamespace(gate_a_authority_root=tmp_path / "authority"),
            tmp_path / "preflight",
            resource_lock_fds=inherited,
        )
    finally:
        for descriptor in inherited.values():
            os.close(descriptor)
    assert captured["env"] == expected_environment
    assert set(inherited.values()) <= set(captured["pass_fds"])
    assert _fd_count() == before


def test_pinned_gate_a_preflight_environment_failure_closes_source_fds_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entrypoint = tmp_path / "entrypoint.py"
    entrypoint.write_bytes(b"raise AssertionError('not executed')\n")
    real_open_regular = QUALIFICATION._open_regular  # noqa: SLF001
    real_close = os.close
    opened: list[int] = []
    close_count: dict[int, int] = {}
    primary = RuntimeError("session-env-fault")

    def open_regular(path: Path | str) -> int:
        descriptor = real_open_regular(path)
        opened.append(descriptor)
        return descriptor

    def counted_close(descriptor: int) -> None:
        if descriptor in opened:
            close_count[descriptor] = close_count.get(descriptor, 0) + 1
        real_close(descriptor)

    monkeypatch.setattr(QUALIFICATION, "_open_regular", open_regular)
    monkeypatch.setattr(QUALIFICATION.os, "close", counted_close)
    monkeypatch.setattr(
        QUALIFICATION,
        "_preflight_environment",
        lambda: (_ for _ in ()).throw(primary),
    )
    monkeypatch.setattr(
        QUALIFICATION.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("subprocess must not start"),
    )
    before = _fd_count()
    inherited = {
        path: os.open("/dev/null", os.O_RDONLY)
        for path in QUALIFICATION.LOCK_PATHS
    }
    try:
        with pytest.raises(RuntimeError, match="session-env-fault") as observed:
            QUALIFICATION._run_pinned_gate_a_preflight(  # noqa: SLF001
                {
                    "observation_identity": {
                        "path": str(tmp_path / "observation.json"),
                        "sha256": "a" * 64,
                        "size_bytes": 1,
                    },
                    "planned_digest": "b" * 64,
                    "repository": tmp_path,
                    "scripts": {"gate_a_pinned_entrypoint_v2": entrypoint},
                    "system_paths": {"python3_13": Path(os.path.realpath(sys.executable))},
                },
                SimpleNamespace(gate_a_authority_root=tmp_path / "authority"),
                tmp_path / "preflight",
                resource_lock_fds=inherited,
            )
    finally:
        for descriptor in inherited.values():
            os.close(descriptor)
    assert observed.value is primary
    assert len(opened) == 2
    assert close_count == {descriptor: 1 for descriptor in opened}
    assert _fd_count() == before


def test_open_regular_runtime_failure_closes_once_without_masking_close_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target.py"
    target.write_bytes(b"fixture\n")
    before = _fd_count()
    real_open = os.open
    real_close = os.close
    real_fstat = os.fstat
    opened: list[int] = []
    close_count: dict[int, int] = {}
    primary = RuntimeError("fstat-fault")

    def injected_open(path: object, *args: object, **kwargs: object) -> int:
        descriptor = real_open(path, *args, **kwargs)
        if os.fspath(path) == target.name and kwargs.get("dir_fd") is not None:
            opened.append(descriptor)
        return descriptor

    def injected_fstat(descriptor: int) -> os.stat_result:
        if opened and descriptor == opened[0]:
            raise primary
        return real_fstat(descriptor)

    def injected_close(descriptor: int) -> None:
        if opened and descriptor == opened[0]:
            close_count[descriptor] = close_count.get(descriptor, 0) + 1
            real_close(descriptor)
            raise OSError("close-fault")
        real_close(descriptor)

    monkeypatch.setattr(QUALIFICATION.os, "open", injected_open)
    monkeypatch.setattr(QUALIFICATION.os, "fstat", injected_fstat)
    monkeypatch.setattr(QUALIFICATION.os, "close", injected_close)
    with pytest.raises(RuntimeError, match="fstat-fault") as observed:
        QUALIFICATION._open_regular(target)  # noqa: SLF001
    assert observed.value is primary
    assert opened and close_count == {opened[0]: 1}
    assert any("close-fault" in note for note in getattr(primary, "__notes__", ()))
    assert _fd_count() == before


def test_component_directory_close_fault_closes_following_descriptor_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    real_open = os.open
    real_close = os.close
    opened: list[int] = []
    close_count: dict[int, int] = {}

    def counted_open(path: object, *args: object, **kwargs: object) -> int:
        descriptor = real_open(path, *args, **kwargs)
        opened.append(descriptor)
        return descriptor

    def injected_close(descriptor: int) -> None:
        close_count[descriptor] = close_count.get(descriptor, 0) + 1
        real_close(descriptor)
        if descriptor == opened[0]:
            raise RuntimeError("ancestor-close-fault")

    monkeypatch.setattr(QUALIFICATION.os, "open", counted_open)
    monkeypatch.setattr(QUALIFICATION.os, "close", injected_close)
    with pytest.raises(RuntimeError, match="ancestor-close-fault") as observed:
        QUALIFICATION._open_directory(tmp_path)  # noqa: SLF001
    assert len(opened) == 2
    assert close_count == {descriptor: 1 for descriptor in opened}
    assert not getattr(observed.value, "__notes__", ())
    assert _fd_count() == before


def test_lock_and_memfd_validation_faults_close_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    real_open = os.open
    real_close = os.close
    libc = ctypes.CDLL(None, use_errno=True)
    real_memfd_create = libc.memfd_create
    real_memfd_create.argtypes = [ctypes.c_char_p, ctypes.c_uint]
    real_memfd_create.restype = ctypes.c_int
    lock_fd: list[int] = []
    memfd: list[int] = []
    close_count: dict[int, int] = {}

    def injected_open(path: object, *args: object, **kwargs: object) -> int:
        descriptor = real_open(path, *args, **kwargs)
        if os.fspath(path) == "qualification.lock" and kwargs.get("dir_fd") is not None:
            lock_fd.append(descriptor)
        return descriptor

    def injected_memfd_create(name: str, flags: int) -> int:
        descriptor = int(real_memfd_create(name.encode("ascii"), flags))
        assert descriptor >= 0
        memfd.append(descriptor)
        return descriptor

    def counted_close(descriptor: int) -> None:
        if descriptor in (*lock_fd, *memfd):
            close_count[descriptor] = close_count.get(descriptor, 0) + 1
        real_close(descriptor)

    monkeypatch.setattr(QUALIFICATION.os, "open", injected_open)
    monkeypatch.setattr(
        QUALIFICATION.os,
        "memfd_create",
        injected_memfd_create,
        raising=False,
    )
    monkeypatch.setattr(QUALIFICATION.os, "close", counted_close)
    monkeypatch.setattr(
        QUALIFICATION,
        "_lock_identity",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("lock-fault")),
    )
    with pytest.raises(RuntimeError, match="lock-fault"):
        QUALIFICATION._acquire_lock(tmp_path / "qualification.lock")  # noqa: SLF001
    assert len(lock_fd) == 1
    assert close_count == {lock_fd[0]: 1}
    close_count.clear()

    monkeypatch.setattr(
        QUALIFICATION.fcntl,
        "fcntl",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("seal-fault")),
    )
    with pytest.raises(RuntimeError, match="seal-fault"):
        QUALIFICATION._sealed_memfd("fixture", b"fixture")  # noqa: SLF001
    assert len(memfd) == 1
    assert close_count == {memfd[0]: 1}
    assert _fd_count() == before


def test_partial_lock_duplication_closes_once_and_preserves_primary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    real_open = os.open
    real_dup = os.dup
    real_close = os.close
    originals = [real_open("/dev/null", os.O_RDONLY | os.O_CLOEXEC) for _ in range(3)]
    duplicated: list[int] = []
    close_count: dict[int, int] = {}
    primary = RuntimeError("dup-fault")
    calls = 0
    owner = _unstarted_owner(tmp_path)
    owner._lock_fds = originals  # noqa: SLF001

    def injected_dup(descriptor: int) -> int:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise primary
        result = real_dup(descriptor)
        duplicated.append(result)
        return result

    def injected_close(descriptor: int) -> None:
        if descriptor in duplicated:
            close_count[descriptor] = close_count.get(descriptor, 0) + 1
            real_close(descriptor)
            raise OSError("dup-close-fault")
        real_close(descriptor)

    monkeypatch.setattr(QUALIFICATION.os, "dup", injected_dup)
    monkeypatch.setattr(QUALIFICATION.os, "close", injected_close)
    with pytest.raises(RuntimeError, match="dup-fault") as observed:
        owner.duplicate_lock_fds()
    assert observed.value is primary
    assert duplicated and close_count == {duplicated[0]: 1}
    assert any("dup-close-fault" in note for note in getattr(primary, "__notes__", ()))
    for descriptor in originals:
        real_close(descriptor)
    assert _fd_count() == before


def test_start_failure_closes_each_acquired_lock_exactly_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    real_open = os.open
    real_close = os.close
    acquired: list[int] = []
    close_count: dict[int, int] = {}

    def acquire(_path: object) -> int:
        descriptor = real_open("/dev/null", os.O_RDWR | os.O_CLOEXEC)
        acquired.append(descriptor)
        return descriptor

    def counted_close(descriptor: int) -> None:
        if descriptor in acquired:
            close_count[descriptor] = close_count.get(descriptor, 0) + 1
        real_close(descriptor)

    monkeypatch.setattr(QUALIFICATION, "_acquire_lock", acquire)
    monkeypatch.setattr(
        QUALIFICATION,
        "_open_regular",
        lambda _path: (_ for _ in ()).throw(RuntimeError("source-open-fault")),
    )
    monkeypatch.setattr(QUALIFICATION.os, "close", counted_close)
    owner = _unstarted_owner(tmp_path)
    with pytest.raises(RuntimeError, match="source-open-fault"):
        owner.start()
    assert len(acquired) == 3
    assert close_count == {descriptor: 1 for descriptor in acquired}
    assert owner._descriptors == []  # noqa: SLF001
    assert owner._lock_fds == []  # noqa: SLF001
    assert _fd_count() == before


def test_retain_registration_failure_closes_unregistered_descriptor_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    real_open = os.open
    real_close = os.close
    descriptor = real_open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
    close_count = 0

    class RejectingList(list[int]):
        def append(self, _value: int) -> None:
            raise RuntimeError("registration-fault")

    def counted_close(observed: int) -> None:
        nonlocal close_count
        if observed == descriptor:
            close_count += 1
        real_close(observed)

    owner = _unstarted_owner(tmp_path)
    owner._descriptors = RejectingList()  # noqa: SLF001
    monkeypatch.setattr(QUALIFICATION.os, "close", counted_close)
    with pytest.raises(RuntimeError, match="registration-fault"):
        owner._retain_descriptor(descriptor)  # noqa: SLF001
    assert close_count == 1
    assert _fd_count() == before


def test_owner_cleanup_retries_interrupted_wait_and_preserves_primary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    real_open = os.open
    real_close = os.close
    retained = real_open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
    stderr = open("/dev/null", "rb")  # noqa: SIM115
    control, peer = socket.socketpair()
    close_count = 0
    primary = RuntimeError("active-fault")

    class FakeProcess:
        def __init__(self) -> None:
            self.stderr = stderr
            self.wait_calls = 0
            self.kill_calls = 0

        def poll(self) -> None:
            return None

        def wait(self, *, timeout: float | None = None) -> int:
            del timeout
            self.wait_calls += 1
            if self.wait_calls == 1:
                raise InterruptedError
            return 2

        def kill(self) -> None:
            self.kill_calls += 1

    process = FakeProcess()
    owner = _unstarted_owner(tmp_path)
    owner._process = process  # type: ignore[assignment]  # noqa: SLF001
    owner._control = control  # noqa: SLF001
    owner._descriptors = [retained]  # noqa: SLF001
    owner._lock_fds = [retained]  # noqa: SLF001

    def injected_close(descriptor: int) -> None:
        nonlocal close_count
        if descriptor == retained:
            close_count += 1
            real_close(descriptor)
            raise OSError("retained-close-fault")
        real_close(descriptor)

    monkeypatch.setattr(QUALIFICATION, "_send_frame", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(QUALIFICATION.os, "close", injected_close)
    owner.__exit__(RuntimeError, primary, None)
    peer.close()
    assert process.wait_calls == 2
    assert process.kill_calls == 0
    assert close_count == 1
    assert any("retained-close-fault" in note for note in getattr(primary, "__notes__", ()))
    assert _fd_count() == before


def test_release_retries_interrupted_wait(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    control, peer = socket.socketpair()

    class FakeProcess:
        stderr = None

        def __init__(self) -> None:
            self.exited = False
            self.wait_timeouts: list[float | None] = []

        def poll(self) -> int | None:
            return 0 if self.exited else None

        def wait(self, *, timeout: float | None = None) -> int:
            self.wait_timeouts.append(timeout)
            if len(self.wait_timeouts) == 1:
                raise InterruptedError
            self.exited = True
            return 0

        def kill(self) -> None:
            self.exited = True

    process = FakeProcess()
    owner = _unstarted_owner(tmp_path)
    owner._process = process  # type: ignore[assignment]  # noqa: SLF001
    owner._control = control  # noqa: SLF001
    monkeypatch.setattr(QUALIFICATION, "_send_frame", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        QUALIFICATION,
        "_recv_frame",
        lambda *_args, **_kwargs: {
            "state": "RELEASE_ACCEPTED",
            "status": "PASS",
        },
    )
    owner.release(bootstrap_result=b"{}\n")
    owner.__exit__(None, None, None)
    peer.close()
    assert process.wait_timeouts[:2] == [5, 5]
    assert _fd_count() == before


def test_bootstrap_attach_send_fault_closes_new_socketpair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _fd_count()
    control, peer = socket.socketpair()
    owner = _unstarted_owner(tmp_path)
    owner._control = control  # noqa: SLF001
    before_attach = _fd_count()
    monkeypatch.setattr(
        QUALIFICATION,
        "_send_frame",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("send-fault")),
    )
    with pytest.raises(RuntimeError, match="send-fault"):
        owner.attach_bootstrap_channel()
    assert _fd_count() == before_attach
    owner.__exit__(None, None, None)
    peer.close()
    assert _fd_count() == baseline


def test_bootstrap_second_source_open_fault_closes_first_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    real_open = os.open
    real_close = os.close
    first = real_open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
    close_count = 0
    calls = 0

    def injected_open(_path: object) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            return first
        raise RuntimeError("bootstrap-open-fault")

    def counted_close(descriptor: int) -> None:
        nonlocal close_count
        if descriptor == first:
            close_count += 1
        real_close(descriptor)

    monkeypatch.setattr(QUALIFICATION, "_open_regular", injected_open)
    monkeypatch.setattr(QUALIFICATION.os, "close", counted_close)
    with pytest.raises(RuntimeError, match="bootstrap-open-fault"):
        QUALIFICATION._run_bootstrap_child(  # noqa: SLF001
            {
                "scripts": {"ab16_campaign_bootstrap_v2": tmp_path / "bootstrap.py"},
                "system_paths": {"python3_13": Path(sys.executable)},
            },
            SimpleNamespace(),
            gate_b_approval=tmp_path / "approval.json",
            qualification_fd=-1,
            qualification_lock_fds={},
        )
    assert close_count == 1
    assert _fd_count() == before


def test_duplicated_descriptor_cleanup_attempts_all_once_and_preserves_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fd_count()
    real_open = os.open
    real_close = os.close
    descriptors = tuple(
        real_open("/dev/null", os.O_RDONLY | os.O_CLOEXEC) for _ in range(3)
    )
    close_count: dict[int, int] = {}
    primary = RuntimeError("bootstrap-fault")

    def injected_close(descriptor: int) -> None:
        close_count[descriptor] = close_count.get(descriptor, 0) + 1
        real_close(descriptor)
        if descriptor == descriptors[-1]:
            raise OSError("duplicate-close-fault")

    monkeypatch.setattr(QUALIFICATION.os, "close", injected_close)
    QUALIFICATION._close_descriptors(descriptors, primary=primary)  # noqa: SLF001
    assert close_count == {descriptor: 1 for descriptor in descriptors}
    assert any("duplicate-close-fault" in note for note in getattr(primary, "__notes__", ()))
    assert _fd_count() == before


def test_persistent_owner_holds_actor_locks_and_fds_until_bootstrap_handoff(
    tmp_path: Path,
) -> None:
    renderer = _renderer(tmp_path / "renderer.py")
    lock_paths = tuple(tmp_path / f"qualification-{index}.lock" for index in range(3))
    epoch_path = tmp_path / "published/gate-b-epoch.json"
    approval_path = tmp_path / "published/gate-b-approval.json"
    epoch_path.parent.mkdir()

    with QUALIFICATION.PersistentGateBOwner(
        python_path=Path(os.path.realpath(sys.executable)),
        owner_source_path=RESEARCH / "ab16_gate_b_qualification_v1.py",
        renderer_source_path=renderer,
        renderer_identity=_identity(renderer),
        mechanical_publisher=BOOTSTRAP.OWNER_OEXCL_PUBLISH_V1,
        owner_driver=BOOTSTRAP.GATE_B_OWNER_DRIVER_V1,
        lock_paths=lock_paths,
    ) as owner:
        epoch = owner.publish(
            kind="epoch",
            output_path=epoch_path,
            record={"kind": "epoch"},
        )
        approval = owner.publish(
            kind="approval",
            output_path=approval_path,
            record={"kind": "approval"},
        )
        assert owner.is_alive()
        assert epoch["publisher"]["actor"] == approval["publisher"]["actor"] == owner.actor
        assert epoch["publisher"]["qualification_session"]["sequence"] == 1
        assert approval["publisher"]["qualification_session"]["sequence"] == 2
        assert (
            epoch["publisher"]["qualification_session"]["session_id"]
            == approval["publisher"]["qualification_session"]["session_id"]
            == owner.session_id
        )

        with pytest.raises(BlockingIOError):
            _open_competing_locks(lock_paths)

        fd_links = {
            path.name: os.readlink(path)
            for path in Path(f"/proc/{owner.actor['pid']}/fd").iterdir()
        }
        assert any("ab16-gate-b-request-1" in target for target in fd_links.values())
        assert any("ab16-gate-b-request-2" in target for target in fd_links.values())
        assert any("ab16-gate-b-rendered-1" in target for target in fd_links.values())
        assert any("ab16-gate-b-rendered-2" in target for target in fd_links.values())
        assert any("ab16-gate-b-renderer" in target for target in fd_links.values())
        assert any("ab16-gate-b-publisher" in target for target in fd_links.values())

        channel = owner.attach_bootstrap_channel()
        duplicated = owner.duplicate_lock_fds()
        lock_fds = {
            str(path): descriptor
            for path, descriptor in zip(lock_paths, duplicated, strict=True)
        }
        _, epoch_identity = BOOTSTRAP._canonical_mode_record(  # noqa: SLF001
            epoch_path,
            "Gate-B epoch observation fixture",
        )
        _, approval_identity = BOOTSTRAP._canonical_record(  # noqa: SLF001
            approval_path,
            "Gate-B approval fixture",
        )
        try:
            handoff = BOOTSTRAP._complete_gate_b_qualification_handoff(  # noqa: SLF001
                qualification_fd=channel.fileno(),
                qualification_lock_fds=lock_fds,
                epoch_publisher=epoch["publisher"],
                approval_publisher=approval["publisher"],
                gate_b_epoch_identity=epoch_identity,
                gate_b_approval_identity=approval_identity,
                campaign_root_identity={
                    "path": "/fixture/campaign-root.json",
                    "sha256": "c" * 64,
                    "size_bytes": 1,
                },
                gate1_selection_identity={
                    "path": "/fixture/gate1-selection.json",
                    "sha256": "d" * 64,
                    "size_bytes": 1,
                },
                expected_lock_paths=tuple(str(path) for path in lock_paths),
            )
        finally:
            for descriptor in duplicated:
                os.close(descriptor)
        assert handoff["status"] == "PASS"
        assert handoff["actor"] == owner.actor
        assert handoff["session_id"] == owner.session_id
        assert handoff["publisher_sequences"] == [1, 2]
        assert handoff["lock_identities"] == owner.lock_identities
        assert set(handoff["retained_fd_roles"]) == {
            "lock",
            "mechanical_publisher",
            "output_directory",
            "rendered_record",
            "renderer_source",
            "request",
        }
        assert owner.is_alive()

        owner.release(bootstrap_result=b'{"status":"PASS"}\n')
        assert not owner.is_alive()

    competing = _open_competing_locks(lock_paths)
    for descriptor in reversed(competing):
        os.close(descriptor)


def test_detached_approval_handoff_still_rejects_mode_drift(
    tmp_path: Path,
) -> None:
    renderer = _renderer(tmp_path / "renderer.py")
    lock_paths = tuple(tmp_path / f"qualification-{index}.lock" for index in range(3))
    epoch_path = tmp_path / "published/gate-b-epoch.json"
    approval_path = tmp_path / "published/gate-b-approval.json"
    epoch_path.parent.mkdir()
    owner = QUALIFICATION.PersistentGateBOwner(
        python_path=Path(os.path.realpath(sys.executable)),
        owner_source_path=RESEARCH / "ab16_gate_b_qualification_v1.py",
        renderer_source_path=renderer,
        renderer_identity=_identity(renderer),
        mechanical_publisher=BOOTSTRAP.OWNER_OEXCL_PUBLISH_V1,
        owner_driver=BOOTSTRAP.GATE_B_OWNER_DRIVER_V1,
        lock_paths=lock_paths,
    )
    primary: BaseException | None = None
    owner.start()
    try:
        owner.publish(kind="epoch", output_path=epoch_path, record={"kind": "epoch"})
        owner.publish(
            kind="approval",
            output_path=approval_path,
            record={"kind": "approval"},
        )
        channel = owner.attach_bootstrap_channel()
        _, approval_identity = BOOTSTRAP._canonical_record(  # noqa: SLF001
            approval_path,
            "Gate-B approval fixture",
        )
        approval_path.chmod(0o600)
        QUALIFICATION._send_frame(  # noqa: SLF001
            channel,
            _handoff_request(
                owner,
                epoch_identity=_identity(epoch_path),
                approval_identity=approval_identity,
            ),
        )
        with pytest.raises(
            QUALIFICATION.QualificationError,
            match="control frame is absent or truncated",
        ) as caught:
            QUALIFICATION._recv_frame(channel)  # noqa: SLF001
        primary = caught.value
        assert owner._process is not None  # noqa: SLF001
        assert owner._process.wait(timeout=5) == 2  # noqa: SLF001
        assert owner._process.stderr is not None  # noqa: SLF001
        assert b"published output identity drifted" in owner._process.stderr.read()  # noqa: SLF001
    finally:
        owner.__exit__(
            type(primary) if primary is not None else None,
            primary,
            primary.__traceback__ if primary is not None else None,
        )

    competing = _open_competing_locks(lock_paths)
    for descriptor in reversed(competing):
        os.close(descriptor)


def test_persistent_owner_rejects_out_of_order_publication(
    tmp_path: Path,
) -> None:
    renderer = _renderer(tmp_path / "renderer.py")
    lock_paths = tuple(tmp_path / f"qualification-{index}.lock" for index in range(3))
    output = tmp_path / "published/gate-b-approval.json"
    output.parent.mkdir()
    with QUALIFICATION.PersistentGateBOwner(
        python_path=Path(os.path.realpath(sys.executable)),
        owner_source_path=RESEARCH / "ab16_gate_b_qualification_v1.py",
        renderer_source_path=renderer,
        renderer_identity=_identity(renderer),
        mechanical_publisher=BOOTSTRAP.OWNER_OEXCL_PUBLISH_V1,
        owner_driver=BOOTSTRAP.GATE_B_OWNER_DRIVER_V1,
        lock_paths=lock_paths,
    ) as owner:
        with pytest.raises(
            QUALIFICATION.QualificationError,
            match="OWNER_REJECTED:PUBLISH_SEQUENCE",
        ):
            owner.publish(kind="approval", output_path=output, record={"kind": "approval"})
        assert not output.exists()


def test_bootstrap_handoff_rejects_session_or_lock_drift_before_return(
    tmp_path: Path,
) -> None:
    renderer = _renderer(tmp_path / "renderer.py")
    lock_paths = tuple(tmp_path / f"qualification-{index}.lock" for index in range(3))
    epoch_path = tmp_path / "published/gate-b-epoch.json"
    approval_path = tmp_path / "published/gate-b-approval.json"
    epoch_path.parent.mkdir()
    with QUALIFICATION.PersistentGateBOwner(
        python_path=Path(os.path.realpath(sys.executable)),
        owner_source_path=RESEARCH / "ab16_gate_b_qualification_v1.py",
        renderer_source_path=renderer,
        renderer_identity=_identity(renderer),
        mechanical_publisher=BOOTSTRAP.OWNER_OEXCL_PUBLISH_V1,
        owner_driver=BOOTSTRAP.GATE_B_OWNER_DRIVER_V1,
        lock_paths=lock_paths,
    ) as owner:
        epoch = owner.publish(kind="epoch", output_path=epoch_path, record={"kind": "epoch"})
        approval = owner.publish(
            kind="approval",
            output_path=approval_path,
            record={"kind": "approval"},
        )
        channel = owner.attach_bootstrap_channel()
        lock_fds = {
            str(path): descriptor
            for path, descriptor in zip(lock_paths, owner.duplicate_lock_fds(), strict=True)
        }
        try:
            with pytest.raises(
                BOOTSTRAP.BootstrapError,
                match="qualification session",
            ):
                BOOTSTRAP._complete_gate_b_qualification_handoff(  # noqa: SLF001
                    qualification_fd=channel.fileno(),
                    qualification_lock_fds=lock_fds,
                    epoch_publisher=epoch["publisher"],
                    approval_publisher={
                        **approval["publisher"],
                        "qualification_session": {
                            **approval["publisher"]["qualification_session"],
                            "session_id": "f" * 64,
                        },
                    },
                    gate_b_epoch_identity=_identity(epoch_path),
                    gate_b_approval_identity=_identity(approval_path),
                    campaign_root_identity={
                        "path": "/fixture/campaign-root.json",
                        "sha256": "c" * 64,
                        "size_bytes": 1,
                    },
                    gate1_selection_identity={
                        "path": "/fixture/gate1-selection.json",
                        "sha256": "d" * 64,
                        "size_bytes": 1,
                    },
                    expected_lock_paths=tuple(str(path) for path in lock_paths),
                )
        finally:
            for descriptor in lock_fds.values():
                os.close(descriptor)


@pytest.mark.parametrize(
    "stage",
    (
        RESOURCE_ADMISSION.FULL_PREFLIGHT,
        RESOURCE_ADMISSION.GATE_B_QUALIFICATION,
        RESOURCE_ADMISSION.FORMAL_ORGANIC_ARM,
    ),
)
def test_stage_resource_admission_accepts_each_exact_minimum(
    tmp_path: Path,
    stage: str,
) -> None:
    minimums = _stage_minimums(stage)
    receipt = _admit_at(
        tmp_path,
        stage=stage,
        disk=minimums["disk"],
        memory=minimums["memory"],
        swap=minimums["swap"],
    )
    assert receipt["status"] == "PASS"
    assert receipt["headroom"] == {
        "disk_bytes_above_minimum": 0,
        "memory_bytes_above_minimum": 0,
        "swap_bytes_above_minimum": 0,
    }
    assert RESOURCE_ADMISSION.validate_resource_admission_receipt(
        receipt,
        expected_stage=stage,
        expected_lock_identities=_gate_b_lock_identities(),
        expected_lock_identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
        expected_observation_context=_observation_context(tmp_path, stage),
    ) == receipt


@pytest.mark.parametrize(
    ("stage", "dimension"),
    tuple(
        (stage, dimension)
        for stage in (
            RESOURCE_ADMISSION.FULL_PREFLIGHT,
            RESOURCE_ADMISSION.GATE_B_QUALIFICATION,
            RESOURCE_ADMISSION.FORMAL_ORGANIC_ARM,
        )
        for dimension in ("disk", "memory", "swap")
    ),
)
def test_stage_resource_admission_rejects_one_byte_below_each_minimum(
    tmp_path: Path,
    stage: str,
    dimension: str,
) -> None:
    minimums = _stage_minimums(stage)
    minimums[dimension] -= 1
    with pytest.raises(
        RESOURCE_ADMISSION.ResourceAdmissionError,
        match=rf"RESOURCE_HEADROOM_INSUFFICIENT: {stage}\.{dimension}:",
    ):
        _admit_at(
            tmp_path,
            stage=stage,
            disk=minimums["disk"],
            memory=minimums["memory"],
            swap=minimums["swap"],
        )


def test_stage_resource_admission_receipt_has_exact_auditable_shape(
    tmp_path: Path,
) -> None:
    stage = RESOURCE_ADMISSION.FULL_PREFLIGHT
    minimums = _stage_minimums(stage)
    receipt = _admit_at(
        tmp_path,
        stage=stage,
        disk=minimums["disk"],
        memory=minimums["memory"],
        swap=minimums["swap"],
    )
    assert set(receipt) == {
        "authority_scope",
        "authorizations",
        "created_at_utc",
        "disk_target",
        "hard_cap_feasibility",
        "headroom",
        "lock_check",
        "measurements",
        "observation_context",
        "observation_context_sha256",
        "profile",
        "schema_version",
        "stage",
        "status",
    }
    assert receipt["authority_scope"] == "AB16_RESEARCH_ONLY"
    assert receipt["authorizations"] == RESOURCE_ADMISSION.FALSE_AUTHORIZATIONS
    assert receipt["measurements"] == {
        "disk_free_bytes": minimums["disk"],
        "mem_available_bytes": minimums["memory"],
        "same_uid_allowed_processes": [],
        "same_uid_conflicts": [],
        "swap_free_bytes": minimums["swap"],
    }
    assert receipt["lock_check"] == {
        "checked_after_acquisition": True,
        "identities": _gate_b_lock_identities(),
        "identity_format": RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
        "paths": list(RESOURCE_ADMISSION.LOCK_PATHS),
    }
    profile = receipt["profile"]
    assert isinstance(profile, dict)
    assert set(profile) == {
        "basis",
        "execution",
        "profile_id",
        "profile_sha256",
        "profile_set_id",
        "requirements",
        "runtime_safety_limits",
        "stage",
    }
    assert isinstance(profile["profile_sha256"], str)
    assert len(profile["profile_sha256"]) == 64
    basis = profile["basis"]
    assert isinstance(basis, dict)
    assert set(basis) == {
        "classification",
        "comparable_to_stage",
        "confidence",
        "evidence_class",
        "historical_observations",
        "prediction_method",
        "stage_peak_receipt_count",
        "stage_peak_receipts",
        "warning",
    }
    assert basis["classification"] == "CONSERVATIVE_TEMPORARY"
    assert basis["comparable_to_stage"] is True
    assert basis["confidence"] == "LOW"
    assert basis["evidence_class"] == "HISTORICAL_EXTERNAL_SAMPLER_SAME_STAGE_PROXY"
    assert basis["stage_peak_receipt_count"] == 0
    assert basis["stage_peak_receipts"] == []
    assert "NOT_A_STAGE_PEAK_MEASUREMENT" in str(basis["warning"])


@pytest.mark.parametrize(
    ("stage", "evidence_class", "comparable_to_stage"),
    (
        (
            RESOURCE_ADMISSION.FULL_PREFLIGHT,
            "HISTORICAL_EXTERNAL_SAMPLER_SAME_STAGE_PROXY",
            True,
        ),
        (
            RESOURCE_ADMISSION.GATE_B_QUALIFICATION,
            "NO_STAGE_PEAK_EVIDENCE",
            False,
        ),
        (
            RESOURCE_ADMISSION.FORMAL_ORGANIC_ARM,
            "HETEROGENEOUS_PLANNING_PROXY",
            False,
        ),
    ),
)
def test_stage_resource_admission_labels_each_temporary_basis_honestly(
    tmp_path: Path,
    stage: str,
    evidence_class: str,
    comparable_to_stage: bool,
) -> None:
    minimums = _stage_minimums(stage)
    receipt = _admit_at(
        tmp_path,
        stage=stage,
        disk=minimums["disk"],
        memory=minimums["memory"],
        swap=minimums["swap"],
    )
    profile = receipt["profile"]
    assert isinstance(profile, dict)
    basis = profile["basis"]
    assert isinstance(basis, dict)
    assert basis["classification"] == "CONSERVATIVE_TEMPORARY"
    assert basis["confidence"] == "LOW"
    assert basis["evidence_class"] == evidence_class
    assert basis["comparable_to_stage"] is comparable_to_stage
    assert basis["stage_peak_receipt_count"] == 0
    assert basis["stage_peak_receipts"] == []


@pytest.mark.parametrize(
    "mutation",
    ("missing-basis-field", "untrusted-classification", "stage-count-bool"),
)
def test_stage_resource_admission_rejects_missing_or_untrusted_basis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    stage = RESOURCE_ADMISSION.GATE_B_QUALIFICATION
    profile = json.loads(json.dumps(RESOURCE_ADMISSION.RESOURCE_PROFILES[stage]))
    basis = profile["basis"]
    assert isinstance(basis, dict)
    if mutation == "missing-basis-field":
        del basis["prediction_method"]
    elif mutation == "untrusted-classification":
        basis["classification"] = "MEASURED"
    else:
        basis["stage_peak_receipt_count"] = False
    unhashed_profile = dict(profile)
    del unhashed_profile["profile_sha256"]
    profile["profile_sha256"] = RESOURCE_ADMISSION._canonical_sha256(  # noqa: SLF001
        unhashed_profile
    )
    monkeypatch.setitem(RESOURCE_ADMISSION.RESOURCE_PROFILES, stage, profile)
    minimums = _stage_minimums(stage)
    with pytest.raises(
        RESOURCE_ADMISSION.ResourceAdmissionError,
        match="RESOURCE_PROFILE_UNTRUSTED",
    ):
        _admit_at(
            tmp_path,
            stage=stage,
            disk=minimums["disk"],
            memory=minimums["memory"],
            swap=minimums["swap"],
        )


@pytest.mark.parametrize(
    ("meminfo", "disk_free"),
    (
        ({"MemAvailable": 1}, 1),
        ({"MemAvailable": "1", "SwapFree": 1}, 1),
        ({"MemAvailable": 1, "SwapFree": -1}, 1),
        ({"MemAvailable": 1, "SwapFree": 1}, True),
    ),
)
def test_stage_resource_admission_rejects_missing_or_malformed_measurement(
    tmp_path: Path,
    meminfo: dict[str, object],
    disk_free: object,
) -> None:
    with pytest.raises(
        RESOURCE_ADMISSION.ResourceAdmissionError,
        match="RESOURCE_MEASUREMENT_UNTRUSTED",
    ):
        RESOURCE_ADMISSION.evaluate_resource_admission(
            tmp_path,
            stage=RESOURCE_ADMISSION.GATE_B_QUALIFICATION,
            lock_identities=_gate_b_lock_identities(),
            lock_identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
            observation_context=_observation_context(
                tmp_path,
                RESOURCE_ADMISSION.GATE_B_QUALIFICATION,
            ),
            meminfo=meminfo,
            disk_free=disk_free,
            conflicts=[],
        )


@pytest.mark.parametrize("mutation", ("missing", "malformed"))
def test_stage_resource_admission_replay_rejects_measurement_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    stage = RESOURCE_ADMISSION.GATE_B_QUALIFICATION
    minimums = _stage_minimums(stage)
    receipt = _admit_at(
        tmp_path,
        stage=stage,
        disk=minimums["disk"],
        memory=minimums["memory"],
        swap=minimums["swap"],
    )
    measurements = receipt["measurements"]
    assert isinstance(measurements, dict)
    if mutation == "missing":
        del measurements["swap_free_bytes"]
    else:
        measurements["mem_available_bytes"] = True
    with pytest.raises(RESOURCE_ADMISSION.ResourceAdmissionError):
        RESOURCE_ADMISSION.validate_resource_admission_receipt(
            receipt,
            expected_stage=stage,
            expected_lock_identities=_gate_b_lock_identities(),
            expected_lock_identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
            expected_observation_context=_observation_context(tmp_path, stage),
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "authorization-false-as-zero",
        "profile-boolean-as-one",
        "profile-stage-count-zero-as-false",
        "lock-check-boolean-as-one",
        "lock-mode-int-as-float",
        "lock-nlink-one-as-true",
        "headroom-zero-as-false",
        "hard-cap-true-as-one",
        "context-zero-as-false",
    ),
)
def test_stage_resource_admission_replay_rejects_python_bool_int_aliases(
    tmp_path: Path,
    mutation: str,
) -> None:
    stage = RESOURCE_ADMISSION.FORMAL_ORGANIC_ARM
    minimums = _stage_minimums(stage)
    receipt = _admit_at(
        tmp_path,
        stage=stage,
        disk=minimums["disk"],
        memory=minimums["memory"],
        swap=minimums["swap"],
    )
    original = deepcopy(receipt)
    if mutation == "authorization-false-as-zero":
        receipt["authorizations"]["solver_run_authorized"] = 0
    elif mutation == "profile-boolean-as-one":
        receipt["profile"]["execution"]["single_worker_required"] = 1
    elif mutation == "profile-stage-count-zero-as-false":
        receipt["profile"]["basis"]["stage_peak_receipt_count"] = False
    elif mutation == "lock-check-boolean-as-one":
        receipt["lock_check"]["checked_after_acquisition"] = 1
    elif mutation == "lock-mode-int-as-float":
        receipt["lock_check"]["identities"][0]["mode"] = float(0o600)
    elif mutation == "lock-nlink-one-as-true":
        receipt["lock_check"]["identities"][0]["nlink"] = True
    elif mutation == "headroom-zero-as-false":
        receipt["headroom"]["disk_bytes_above_minimum"] = False
    elif mutation == "hard-cap-true-as-one":
        receipt["hard_cap_feasibility"]["applies"] = 1
    elif mutation == "context-zero-as-false":
        receipt["observation_context"]["ordinal"] = False
    else:
        raise AssertionError(f"unknown mutation {mutation}")
    assert receipt == original

    with pytest.raises(
        RESOURCE_ADMISSION.ResourceAdmissionError,
        match="RESOURCE_(?:RECEIPT|LOCK_EVIDENCE)_INVALID",
    ):
        RESOURCE_ADMISSION.validate_resource_admission_receipt(
            receipt,
            expected_stage=stage,
            expected_lock_identities=_gate_b_lock_identities(),
            expected_lock_identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
            expected_observation_context=_observation_context(tmp_path, stage),
        )


@pytest.mark.parametrize(
    ("field", "alias"),
    (
        ("mode", float(0o600)),
        ("nlink", True),
    ),
)
def test_gate_b_lock_identity_rejects_equal_but_wrong_numeric_type(
    field: str,
    alias: object,
) -> None:
    identities = _gate_b_lock_identities()
    identities[0][field] = alias
    with pytest.raises(
        RESOURCE_ADMISSION.ResourceAdmissionError,
        match="RESOURCE_LOCK_EVIDENCE_INVALID",
    ):
        RESOURCE_ADMISSION._validate_lock_identities(  # noqa: SLF001
            identities,
            identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
        )


def test_stage_resource_admission_rejects_same_uid_conflict(
    tmp_path: Path,
) -> None:
    minimums = _stage_minimums(RESOURCE_ADMISSION.GATE_B_QUALIFICATION)
    with pytest.raises(
        RESOURCE_ADMISSION.ResourceAdmissionError,
        match="RESOURCE_CONFLICT_DETECTED",
    ):
        RESOURCE_ADMISSION.evaluate_resource_admission(
            tmp_path,
            stage=RESOURCE_ADMISSION.GATE_B_QUALIFICATION,
            lock_identities=_gate_b_lock_identities(),
            lock_identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
            observation_context=_observation_context(
                tmp_path,
                RESOURCE_ADMISSION.GATE_B_QUALIFICATION,
            ),
            meminfo={
                "MemAvailable": minimums["memory"],
                "SwapFree": minimums["swap"],
            },
            disk_free=minimums["disk"],
            conflicts=[{"command": "python scripts/preflight_gate.py --full", "pid": 12345}],
        )


def _controlled_resource_proc(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    command: str,
) -> tuple[Path, dict[str, int], dict[str, object]]:
    proc_root = tmp_path / "controlled-proc"
    process_root = proc_root / "4242"
    process_root.mkdir(parents=True)
    identity = {"pid": 4242, "starttime": 987654}
    observation: dict[str, object] = {
        "command": command,
        **identity,
        "uid": os.getuid(),
    }
    monkeypatch.setattr(
        RESOURCE_ADMISSION,
        "_ancestor_pids",
        lambda _proc_root: set(),
    )
    monkeypatch.setattr(
        RESOURCE_ADMISSION,
        "_process_observation",
        lambda path, *, pid: (
            dict(observation)
            if path == process_root and pid == identity["pid"]
            else None
        ),
    )
    return proc_root, identity, observation


def test_stage_resource_admission_allows_only_the_exact_live_guardian_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    proc_root, identity, observed = _controlled_resource_proc(
        monkeypatch,
        tmp_path,
        command="python -I -B guardian.py --role outer-guardian",
    )
    scan = RESOURCE_ADMISSION._same_uid_conflicts  # noqa: SLF001
    monkeypatch.setattr(
        RESOURCE_ADMISSION,
        "_same_uid_conflicts",
        lambda *, allowed_processes: scan(
            allowed_processes=allowed_processes,
            proc_root=proc_root,
        ),
    )
    minimums = _stage_minimums(RESOURCE_ADMISSION.FORMAL_ORGANIC_ARM)
    receipt = RESOURCE_ADMISSION.evaluate_resource_admission(
        tmp_path,
        stage=RESOURCE_ADMISSION.FORMAL_ORGANIC_ARM,
        lock_identities=_gate_b_lock_identities(),
        lock_identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
        observation_context=_observation_context(
            tmp_path,
            RESOURCE_ADMISSION.FORMAL_ORGANIC_ARM,
        ),
        meminfo={
            "MemAvailable": minimums["memory"],
            "SwapFree": minimums["swap"],
        },
        disk_free=minimums["disk"],
        allowed_same_uid_processes=[identity],
        observed_at_utc="2026-07-30T00:00:00Z",
    )
    assert receipt["measurements"]["same_uid_allowed_processes"] == [
        {
            "command": observed["command"],
            **identity,
        }
    ]
    assert RESOURCE_ADMISSION.validate_resource_admission_receipt(
        receipt,
        expected_stage=RESOURCE_ADMISSION.FORMAL_ORGANIC_ARM,
        expected_lock_identities=_gate_b_lock_identities(),
        expected_lock_identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
        expected_observation_context=_observation_context(
            tmp_path,
            RESOURCE_ADMISSION.FORMAL_ORGANIC_ARM,
        ),
        expected_allowed_same_uid_processes=[identity],
    ) == receipt


def test_stage_resource_admission_allowlist_identity_does_not_require_conflict_pattern(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    proc_root, identity, observed = _controlled_resource_proc(
        monkeypatch,
        tmp_path,
        command="python -I -B helper.py --role retained-resource-helper",
    )
    assert not any(
        pattern in str(observed["command"]).lower()
        for pattern in RESOURCE_ADMISSION.CONFLICT_PATTERNS
    )
    conflicts, allowed = RESOURCE_ADMISSION._same_uid_conflicts(  # noqa: SLF001
        allowed_processes=[identity],
        proc_root=proc_root,
    )
    assert conflicts == []
    assert allowed == [{"command": observed["command"], **identity}]


def test_prospective_same_uid_baseline_is_exact_and_digest_bound(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    proc_root, identity, observed = _controlled_resource_proc(
        monkeypatch,
        tmp_path,
        command="python -I -B helper.py --role retained-resource-helper",
    )
    process_root = proc_root / str(identity["pid"])
    (process_root / "fd").mkdir()
    (process_root / "fdinfo").mkdir()
    conflicts, allowed, baseline = (
        RESOURCE_ADMISSION._same_uid_conflicts_with_baseline(  # noqa: SLF001
            allowed_processes=[identity],
            proc_root=proc_root,
        )
    )
    assert conflicts == []
    assert allowed == [{"command": observed["command"], **identity}]
    assert baseline["mode"] == RESOURCE_ADMISSION.SAME_UID_BASELINE_LIVE_MODE
    assert baseline["processes"] == [
        {
            "classification": "ALLOWED_CAMPAIGN_ACTOR",
            "command_sha256": hashlib.sha256(
                str(observed["command"]).encode("utf-8")
            ).hexdigest(),
            **identity,
        }
    ]
    digest = RESOURCE_ADMISSION._canonical_sha256(baseline)  # noqa: SLF001
    assert RESOURCE_ADMISSION.validate_same_uid_process_baseline(
        baseline,
        expected_sha256=digest,
        require_live=True,
    ) == baseline
    forged = deepcopy(baseline)
    forged["processes"][0]["classification"] = "UNDECLARED_ROLE"
    with pytest.raises(
        RESOURCE_ADMISSION.ResourceAdmissionError,
        match="RESOURCE_SAME_UID_BASELINE_INVALID",
    ):
        RESOURCE_ADMISSION.validate_same_uid_process_baseline(
            forged,
            expected_sha256=digest,
            require_live=True,
        )


def test_prospective_same_uid_baseline_rejects_unclassifiable_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    proc_root, _identity, _observed = _controlled_resource_proc(
        monkeypatch,
        tmp_path,
        command="",
    )
    with pytest.raises(
        RESOURCE_ADMISSION.ResourceAdmissionError,
        match="RESOURCE_CONFLICT_SCAN_UNTRUSTED",
    ):
        RESOURCE_ADMISSION._same_uid_conflicts_with_baseline(  # noqa: SLF001
            allowed_processes=[],
            proc_root=proc_root,
        )


def test_prospective_same_uid_baseline_does_not_require_unrelated_fd_table(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    proc_root, identity, _observed = _controlled_resource_proc(
        monkeypatch,
        tmp_path,
        command="python -I -B helper.py --role retained-resource-helper",
    )
    descriptor_root = proc_root / str(identity["pid"]) / "fd"
    descriptor_root.mkdir()
    original_iterdir = Path.iterdir

    def guarded_iterdir(path: Path) -> object:
        if path == descriptor_root:
            raise PermissionError("deterministic uninspectable FD table")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", guarded_iterdir)
    conflicts, _allowed, baseline = (
        RESOURCE_ADMISSION._same_uid_conflicts_with_baseline(  # noqa: SLF001
            allowed_processes=[],
            proc_root=proc_root,
        )
    )
    assert conflicts == []
    assert baseline["threat_boundary"] == "NONADVERSARIAL_SAME_UID_AMBIENT"


def test_injected_same_uid_baseline_cannot_authorize_launch() -> None:
    baseline = RESOURCE_ADMISSION._same_uid_process_baseline(  # noqa: SLF001
        (),
        mode=RESOURCE_ADMISSION.SAME_UID_BASELINE_TEST_MODE,
    )
    with pytest.raises(
        RESOURCE_ADMISSION.ResourceAdmissionError,
        match="RESOURCE_SAME_UID_BASELINE_NOT_LIVE",
    ):
        RESOURCE_ADMISSION.validate_same_uid_process_baseline(
            baseline,
            expected_sha256=RESOURCE_ADMISSION._canonical_sha256(  # noqa: SLF001
                baseline
            ),
            require_live=True,
        )


def _temporary_resource_lock_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, str, str]:
    paths = tuple(str(tmp_path / f"resource-{index}.lock") for index in range(3))
    monkeypatch.setattr(RESOURCE_ADMISSION, "LOCK_PATHS", paths)
    return paths


def test_held_resource_locks_normal_rechecks_and_release_do_not_leak_fds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _temporary_resource_lock_paths(tmp_path, monkeypatch)
    before = len(os.listdir("/proc/self/fd"))
    for _ in range(3):
        lease = RESOURCE_ADMISSION.HeldResourceLocks.acquire(
            identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
        )
        identities = lease.identities()
        assert [item["path"] for item in identities] == list(paths)
        assert lease.release_once() == identities
        assert lease.released is True
    assert len(os.listdir("/proc/self/fd")) == before


def test_held_resource_locks_rejects_name_replacement_even_when_replacement_is_locked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _temporary_resource_lock_paths(tmp_path, monkeypatch)
    lease = RESOURCE_ADMISSION.HeldResourceLocks.acquire(
        identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
    )
    target = Path(paths[0])
    retained = target.with_suffix(".retained")
    real_open = RESOURCE_ADMISSION.os.open
    holder: subprocess.Popen[str] | None = None
    injected = False

    def replace_before_probe(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal holder, injected
        if (
            os.fspath(path) == paths[0]
            and flags & os.O_NOFOLLOW
            and not flags & os.O_CREAT
            and not injected
        ):
            injected = True
            target.rename(retained)
            target.write_bytes(b"unknown third-party lock")
            target.chmod(0o600)
            holder = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    "-c",
                    (
                        "import fcntl, os, sys, time; "
                        "fd=os.open(sys.argv[1], os.O_RDWR); "
                        "fcntl.flock(fd, fcntl.LOCK_EX); "
                        "print('READY', flush=True); time.sleep(30)"
                    ),
                    paths[0],
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert holder.stdout is not None
            assert holder.stdout.readline() == "READY\n"
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(RESOURCE_ADMISSION.os, "open", replace_before_probe)
    try:
        with pytest.raises(
            RESOURCE_ADMISSION.ResourceAdmissionError,
            match="RESOURCE_LOCK_EVIDENCE_INVALID: .* probe identity drifted",
        ):
            lease.identities()
        assert injected is True
        assert retained.is_file()
        assert target.read_bytes() == b"unknown third-party lock"
        probe = real_open(target, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(probe)
    finally:
        monkeypatch.setattr(RESOURCE_ADMISSION.os, "open", real_open)
        with pytest.raises(
            RESOURCE_ADMISSION.ResourceAdmissionError,
            match="RESOURCE_LOCK_EVIDENCE_INVALID",
        ):
            lease.release_once()
        if holder is not None:
            holder.terminate()
            holder.wait(timeout=10)
    assert lease.released is True
    assert target.read_bytes() == b"unknown third-party lock"


def test_held_resource_locks_rejects_replacement_during_final_name_rejoin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _temporary_resource_lock_paths(tmp_path, monkeypatch)
    lease = RESOURCE_ADMISSION.HeldResourceLocks.acquire(
        identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
    )
    target = Path(paths[0])
    retained = target.with_suffix(".retained")
    real_stat = RESOURCE_ADMISSION.os.stat
    target_stat_calls = 0

    def replace_in_final_rejoin(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *,
        dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        nonlocal target_stat_calls
        if os.fspath(path) == paths[0] and follow_symlinks is False:
            target_stat_calls += 1
            if target_stat_calls == 2:
                target.rename(retained)
                target.write_bytes(b"unknown final-name replacement")
                target.chmod(0o600)
        return real_stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(RESOURCE_ADMISSION.os, "stat", replace_in_final_rejoin)
    try:
        with pytest.raises(
            RESOURCE_ADMISSION.ResourceAdmissionError,
            match="RESOURCE_LOCK_EVIDENCE_INVALID: .* final name identity drifted",
        ):
            lease.identities()
        assert target_stat_calls == 2
        assert retained.is_file()
        assert target.read_bytes() == b"unknown final-name replacement"
    finally:
        monkeypatch.setattr(RESOURCE_ADMISSION.os, "stat", real_stat)
        with pytest.raises(
            RESOURCE_ADMISSION.ResourceAdmissionError,
            match="RESOURCE_LOCK_EVIDENCE_INVALID",
        ):
            lease.release_once()
    assert lease.released is True
    assert target.read_bytes() == b"unknown final-name replacement"


def test_held_resource_locks_adopt_owned_closes_only_passed_duplicates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _temporary_resource_lock_paths(tmp_path, monkeypatch)
    original = RESOURCE_ADMISSION.HeldResourceLocks.acquire(
        identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
    )
    duplicates = {
        path: os.dup(original._descriptors[path])  # noqa: SLF001
        for path in paths
    }
    duplicate_numbers = tuple(duplicates.values())
    adopted = RESOURCE_ADMISSION.HeldResourceLocks.adopt_owned(
        duplicates,
        identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
    )
    assert adopted.identities() == original.identities()
    adopted.release_once()
    for descriptor in duplicate_numbers:
        with pytest.raises(OSError):
            os.fstat(descriptor)
    for descriptor in original._descriptors.values():  # noqa: SLF001
        os.fstat(descriptor)
    original.release_once()


def test_held_resource_locks_adopt_owned_rejects_extra_path_and_closes_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _temporary_resource_lock_paths(tmp_path, monkeypatch)
    original = RESOURCE_ADMISSION.HeldResourceLocks.acquire(
        identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
    )
    duplicates = {
        path: os.dup(original._descriptors[path])  # noqa: SLF001
        for path in paths
    }
    duplicates[str(tmp_path / "extra.lock")] = os.dup(
        original._descriptors[paths[0]],  # noqa: SLF001
    )
    close_counts = {descriptor: 0 for descriptor in duplicates.values()}
    real_close = os.close

    def counted_close(descriptor: int) -> None:
        if descriptor in close_counts:
            close_counts[descriptor] += 1
        real_close(descriptor)

    monkeypatch.setattr(RESOURCE_ADMISSION.os, "close", counted_close)
    with pytest.raises(
        RESOURCE_ADMISSION.ResourceAdmissionError,
        match="RESOURCE_LOCK_EVIDENCE_INVALID",
    ):
        RESOURCE_ADMISSION.HeldResourceLocks.adopt_owned(
            duplicates,
            identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
        )
    assert set(close_counts.values()) == {1}
    for descriptor in original._descriptors.values():  # noqa: SLF001
        os.fstat(descriptor)
    original.release_once()


def test_held_resource_locks_adopt_owned_rejects_missing_path_and_closes_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _temporary_resource_lock_paths(tmp_path, monkeypatch)
    original = RESOURCE_ADMISSION.HeldResourceLocks.acquire(
        identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
    )
    duplicates = {
        path: os.dup(original._descriptors[path])  # noqa: SLF001
        for path in paths[:2]
    }
    close_counts = {descriptor: 0 for descriptor in duplicates.values()}
    real_close = os.close

    def counted_close(descriptor: int) -> None:
        if descriptor in close_counts:
            close_counts[descriptor] += 1
        real_close(descriptor)

    monkeypatch.setattr(RESOURCE_ADMISSION.os, "close", counted_close)
    with pytest.raises(
        RESOURCE_ADMISSION.ResourceAdmissionError,
        match="RESOURCE_LOCK_EVIDENCE_INVALID",
    ):
        RESOURCE_ADMISSION.HeldResourceLocks.adopt_owned(
            duplicates,
            identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
        )
    assert set(close_counts.values()) == {1}
    for descriptor in original._descriptors.values():  # noqa: SLF001
        os.fstat(descriptor)
    original.release_once()


def test_held_resource_locks_acquire_oserror_closes_once_with_stable_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _temporary_resource_lock_paths(tmp_path, monkeypatch)
    real_close = os.close
    close_counts: dict[int, int] = {}

    def counted_close(descriptor: int) -> None:
        close_counts[descriptor] = close_counts.get(descriptor, 0) + 1
        real_close(descriptor)

    def fail_flock(_descriptor: int, _operation: int) -> None:
        raise OSError("injected acquire flock failure")

    monkeypatch.setattr(RESOURCE_ADMISSION.os, "close", counted_close)
    monkeypatch.setattr(RESOURCE_ADMISSION.fcntl, "flock", fail_flock)
    with pytest.raises(
        RESOURCE_ADMISSION.ResourceAdmissionError,
        match="RESOURCE_LOCK_ACQUISITION_FAILED",
    ) as captured:
        RESOURCE_ADMISSION.HeldResourceLocks.acquire(
            identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
        )
    assert captured.value.code == "RESOURCE_LOCK_ACQUISITION_FAILED"
    assert close_counts and set(close_counts.values()) == {1}


def test_held_resource_locks_acquire_cleanup_preserves_non_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _temporary_resource_lock_paths(tmp_path, monkeypatch)
    real_close = os.close
    close_counts: dict[int, int] = {}

    def close_then_fail(descriptor: int) -> None:
        close_counts[descriptor] = close_counts.get(descriptor, 0) + 1
        real_close(descriptor)
        raise OSError("injected acquire cleanup close failure")

    def fail_flock(_descriptor: int, _operation: int) -> None:
        raise RuntimeError("injected acquire validation failure")

    monkeypatch.setattr(RESOURCE_ADMISSION.os, "close", close_then_fail)
    monkeypatch.setattr(RESOURCE_ADMISSION.fcntl, "flock", fail_flock)
    with pytest.raises(RuntimeError, match="injected acquire validation failure") as captured:
        RESOURCE_ADMISSION.HeldResourceLocks.acquire(
            identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
        )
    assert close_counts and set(close_counts.values()) == {1}
    assert any("acquisition cleanup close failed" in note for note in captured.value.__notes__)


def test_held_resource_locks_identity_probe_close_failure_preserves_primary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _temporary_resource_lock_paths(tmp_path, monkeypatch)
    lease = RESOURCE_ADMISSION.HeldResourceLocks.acquire(
        identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
    )
    owned = set(lease._descriptors.values())  # noqa: SLF001
    real_flock = fcntl.flock
    real_close = os.close
    probe_close_counts: dict[int, int] = {}

    def fail_probe_flock(descriptor: int, operation: int) -> None:
        if descriptor not in owned:
            raise RuntimeError("injected identity probe failure")
        real_flock(descriptor, operation)

    def fail_probe_close(descriptor: int) -> None:
        if descriptor not in owned:
            probe_close_counts[descriptor] = probe_close_counts.get(descriptor, 0) + 1
            real_close(descriptor)
            raise OSError("injected probe close failure")
        real_close(descriptor)

    monkeypatch.setattr(RESOURCE_ADMISSION.fcntl, "flock", fail_probe_flock)
    monkeypatch.setattr(RESOURCE_ADMISSION.os, "close", fail_probe_close)
    with pytest.raises(RuntimeError, match="injected identity probe failure") as captured:
        lease.identities()
    assert probe_close_counts and set(probe_close_counts.values()) == {1}
    assert any("probe close failed" in note for note in captured.value.__notes__)
    monkeypatch.setattr(RESOURCE_ADMISSION.fcntl, "flock", real_flock)
    monkeypatch.setattr(RESOURCE_ADMISSION.os, "close", real_close)
    lease.release_once()


def test_held_resource_locks_adopt_and_release_cleanup_preserve_primary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _temporary_resource_lock_paths(tmp_path, monkeypatch)
    original = RESOURCE_ADMISSION.HeldResourceLocks.acquire(
        identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
    )
    duplicates = {
        path: os.dup(original._descriptors[path])  # noqa: SLF001
        for path in paths
    }
    duplicate_numbers = set(duplicates.values())
    real_identities = RESOURCE_ADMISSION.HeldResourceLocks.identities
    real_close = os.close
    close_counts = {descriptor: 0 for descriptor in duplicate_numbers}
    first = min(duplicate_numbers)

    def fail_identities(_lease: object) -> list[dict[str, object]]:
        raise RuntimeError("injected owned validation failure")

    def close_then_fail_once(descriptor: int) -> None:
        if descriptor in close_counts:
            close_counts[descriptor] += 1
            real_close(descriptor)
            if descriptor == first:
                raise OSError("injected owned close failure")
            return
        real_close(descriptor)

    monkeypatch.setattr(
        RESOURCE_ADMISSION.HeldResourceLocks,
        "identities",
        fail_identities,
    )
    monkeypatch.setattr(RESOURCE_ADMISSION.os, "close", close_then_fail_once)
    with pytest.raises(RuntimeError, match="injected owned validation failure") as captured:
        RESOURCE_ADMISSION.HeldResourceLocks.adopt_owned(
            duplicates,
            identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
        )
    assert set(close_counts.values()) == {1}
    assert any("adoption cleanup close failed" in note for note in captured.value.__notes__)

    monkeypatch.setattr(
        RESOURCE_ADMISSION.HeldResourceLocks,
        "identities",
        real_identities,
    )
    monkeypatch.setattr(RESOURCE_ADMISSION.os, "close", real_close)
    adopted = RESOURCE_ADMISSION.HeldResourceLocks.adopt_owned(
        {
            path: os.dup(original._descriptors[path])  # noqa: SLF001
            for path in paths
        },
        identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
    )
    release_numbers = set(adopted._descriptors.values())  # noqa: SLF001
    release_counts = {descriptor: 0 for descriptor in release_numbers}
    first_release = min(release_numbers)

    def fail_release_identities(_lease: object) -> list[dict[str, object]]:
        raise RuntimeError("injected release validation failure")

    def release_close_then_fail_once(descriptor: int) -> None:
        if descriptor in release_counts:
            release_counts[descriptor] += 1
            real_close(descriptor)
            if descriptor == first_release:
                raise OSError("injected release close failure")
            return
        real_close(descriptor)

    monkeypatch.setattr(
        RESOURCE_ADMISSION.HeldResourceLocks,
        "identities",
        fail_release_identities,
    )
    monkeypatch.setattr(
        RESOURCE_ADMISSION.os,
        "close",
        release_close_then_fail_once,
    )
    with pytest.raises(RuntimeError, match="injected release validation failure") as released:
        adopted.release_once()
    assert adopted.released is True
    assert set(release_counts.values()) == {1}
    assert any("resource-lock release close failed" in note for note in released.value.__notes__)

    monkeypatch.setattr(RESOURCE_ADMISSION.os, "close", real_close)
    monkeypatch.setattr(
        RESOURCE_ADMISSION.HeldResourceLocks,
        "identities",
        real_identities,
    )
    original.release_once()


def test_gate_b_resource_gate_wraps_exact_live_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage = RESOURCE_ADMISSION.GATE_B_QUALIFICATION
    minimums = _stage_minimums(stage)
    actor = {"pid": 321, "pid_starttime": "10", "role": "AB16_GATE_B_OWNER"}
    locks = _gate_b_lock_identities()
    calibration = {"fixture": True, "stage": stage}
    calibration_identity = {
        "path": str(tmp_path / "calibration.json"),
        "sha256": "c" * 64,
        "size_bytes": 1,
    }
    captured: dict[str, object] = {}

    def evaluate(path: Path, **kwargs: object) -> dict[str, object]:
        captured["path"] = path
        captured.update(kwargs)
        return {"schema_version": "prospective-fixture"}

    monkeypatch.setattr(
        RESOURCE_ADMISSION,
        "evaluate_prospective_resource_admission",
        evaluate,
    )
    monkeypatch.setattr(
        RESOURCE_ADMISSION,
        "evaluate_resource_admission",
        lambda *_args, **_kwargs: pytest.fail(
            "legacy resource admission must not authorize prospective Gate B"
        ),
    )
    receipt = QUALIFICATION._resource_gate(  # noqa: SLF001
        tmp_path,
        stage="AFTER_FINAL_FULL_PREFLIGHT_BEFORE_GATE_B_APPROVAL",
        profile_stage=stage,
        resource_admission=RESOURCE_ADMISSION,
        calibration_authorization_bundle=calibration,
        calibration_authorization_bundle_identity=calibration_identity,
        actor=actor,
        session_id="a" * 64,
        lock_identities=locks,
        meminfo={
            "MemAvailable": minimums["memory"],
            "SwapFree": minimums["swap"],
        },
        disk_free=minimums["disk"],
        conflicts=[],
    )
    assert set(receipt) == {
        "admission",
        "authorizations",
        "created_at_utc",
        "lock_identities",
        "owner_actor",
        "qualification_session_id",
        "schema_version",
        "stage",
        "status",
    }
    assert receipt["status"] == "PASS"
    assert receipt["lock_identities"] == locks
    assert receipt["owner_actor"] == actor
    assert receipt["admission"] == {
        "schema_version": "prospective-fixture"
    }
    assert captured["calibration_authorization_bundle"] == calibration
    assert (
        captured["calibration_authorization_bundle_identity"]
        == calibration_identity
    )
    assert captured["stage"] == stage


def test_gate_b_resource_calibration_source_recloses_exact_identity(
    tmp_path: Path,
) -> None:
    paths: dict[str, Path] = {}
    identities: dict[str, dict[str, object]] = {}
    for index, stage in enumerate(
        BOOTSTRAP.RESOURCE_CALIBRATION_STAGES,
        start=1,
    ):
        path = tmp_path / f"calibration-{index}.json"
        path.write_bytes(
            QUALIFICATION._canonical_json(  # noqa: SLF001
                {"fixture": index, "stage": stage}
            )
        )
        path.chmod(0o444)
        full_identity = _identity(path)
        paths[stage] = path
        identities[stage] = {
            field: full_identity[field]
            for field in ("path", "sha256", "size_bytes")
        }
    context = {
        "bootstrap": BOOTSTRAP,
        "resource_calibration_bundle_identities": identities,
        "resource_calibration_bundle_paths": paths,
    }
    record, identity = (
        QUALIFICATION._resource_calibration_authorization(  # noqa: SLF001
            context,
            stage=RESOURCE_ADMISSION.GATE_B_QUALIFICATION,
        )
    )
    assert record["stage"] == RESOURCE_ADMISSION.GATE_B_QUALIFICATION
    assert identity == identities[RESOURCE_ADMISSION.GATE_B_QUALIFICATION]

    target = paths[RESOURCE_ADMISSION.GATE_B_QUALIFICATION]
    target.chmod(0o644)
    target.write_bytes(target.read_bytes() + b" ")
    target.chmod(0o444)
    with pytest.raises(
        QUALIFICATION.QualificationError,
        match="identity drifted",
    ):
        QUALIFICATION._resource_calibration_authorization(  # noqa: SLF001
            context,
            stage=RESOURCE_ADMISSION.GATE_B_QUALIFICATION,
        )

    missing = dict(context)
    missing["resource_calibration_bundle_paths"] = {
        stage: path
        for stage, path in paths.items()
        if stage != RESOURCE_ADMISSION.GATE_B_QUALIFICATION
    }
    with pytest.raises(
        QUALIFICATION.QualificationError,
        match="stage set drifted",
    ):
        QUALIFICATION._resource_calibration_authorization(  # noqa: SLF001
            missing,
            stage=RESOURCE_ADMISSION.GATE_B_QUALIFICATION,
        )


def _gate_b_resource_gate_fixture(
    tmp_path: Path,
    *,
    mutation: str | None = None,
) -> tuple[
    Path,
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
    dict[str, dict[str, object]],
]:
    stage = "AFTER_FINAL_FULL_PREFLIGHT_BEFORE_GATE_B_APPROVAL"
    session_id = "a" * 64
    actor = {
        "pid": os.getpid(),
        "pid_starttime": "10",
        "role": "AB16_GATE_B_OWNER",
    }
    locks = _gate_b_lock_identities()
    minimums = _stage_minimums(RESOURCE_ADMISSION.GATE_B_QUALIFICATION)
    admission = RESOURCE_ADMISSION.evaluate_resource_admission(
        tmp_path,
        stage=RESOURCE_ADMISSION.GATE_B_QUALIFICATION,
        lock_identities=locks,
        lock_identity_format=RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT,
        observation_context={
            "authority_id": session_id,
            "disk_path": str(tmp_path.absolute()),
            "kind": "GATE_B_QUALIFICATION_PUBLICATION",
            "ordinal": 0,
            "scope_id": session_id,
            "sequence": 2,
            "slot": "",
            "target": stage,
        },
        meminfo={
            "MemAvailable": minimums["memory"],
            "SwapFree": minimums["swap"],
        },
        disk_free=minimums["disk"],
        conflicts=[],
        observed_at_utc="2026-07-31T00:00:00Z",
    )
    record: dict[str, object] = {
        "admission": admission,
        "authorizations": dict(QUALIFICATION.FALSE_AUTHORIZATIONS),
        "created_at_utc": "2026-07-31T00:00:01Z",
        "lock_identities": locks,
        "owner_actor": actor,
        "qualification_session_id": session_id,
        "schema_version": QUALIFICATION.RESOURCE_GATE_SCHEMA,
        "stage": stage,
        "status": "PASS",
    }
    if mutation == "untrusted-basis":
        changed_admission = deepcopy(admission)
        changed_admission["profile"]["basis"]["confidence"] = "HIGH"
        record["admission"] = changed_admission
    elif mutation == "wrong-session":
        record["qualification_session_id"] = "b" * 64
    elif mutation == "wrong-locks":
        record["lock_identities"] = []
    elif mutation == "extra-field":
        record["unexpected"] = True
    resource_dir = tmp_path / "resource-gates"
    resource_dir.mkdir()
    path = resource_dir / "after-final-full-preflight.json"
    path.write_bytes(QUALIFICATION._canonical_json(record))  # noqa: SLF001
    path.chmod(0o444)
    planned = {
        "script.ab16_resource_admission_v1": _identity(
            RESEARCH / "ab16_resource_admission_v1.py"
        ),
        **_calibration_tool_planned_identities(tmp_path),
    }
    return path, record, actor, locks, planned


def _install_prospective_resource_replayer(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], dict[str, object]]:
    calibration = {
        "fixture": True,
        "stage": RESOURCE_ADMISSION.GATE_B_QUALIFICATION,
    }
    calibration_identity = {
        "path": "/fixture/gate-b-calibration.json",
        "sha256": "c" * 64,
        "size_bytes": 1,
    }

    class ReplayError(RuntimeError):
        pass

    class Replay:
        GATE_B_LOCK_IDENTITY_FORMAT = (
            RESOURCE_ADMISSION.GATE_B_LOCK_IDENTITY_FORMAT
        )
        ResourceAdmissionError = ReplayError

        @staticmethod
        def validate_prospective_resource_admission_receipt(
            value: dict[str, object],
            **kwargs: object,
        ) -> dict[str, object]:
            assert (
                kwargs["calibration_authorization_bundle"]
                == calibration
            )
            assert (
                kwargs["calibration_authorization_bundle_identity"]
                == calibration_identity
            )
            assert kwargs["enforced_budget_profile"] is None
            assert kwargs["enforced_budget_profile_identity"] is None
            if value["profile"]["basis"]["confidence"] == "HIGH":  # type: ignore[index]
                raise ReplayError("untrusted prospective basis")
            return value

    monkeypatch.setattr(
        BOOTSTRAP,
        "_load_resource_admission_replayer",
        lambda *_args, **_kwargs: (Replay, None),
    )
    return calibration, calibration_identity


def test_bootstrap_replays_exact_gate_b_stage_resource_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, record, actor, locks, planned = _gate_b_resource_gate_fixture(tmp_path)
    calibration, calibration_identity = _install_prospective_resource_replayer(
        monkeypatch
    )
    replayed, replayed_identity = BOOTSTRAP._read_gate_b_resource_gate(  # noqa: SLF001
        _identity(path),
        planned=planned,
        calibration_authorization_bundle=calibration,
        calibration_authorization_bundle_identity=calibration_identity,
        expected_actor=actor,
        expected_session_id="a" * 64,
        expected_lock_identities=locks,
        expected_path=path,
        expected_profile_stage=RESOURCE_ADMISSION.GATE_B_QUALIFICATION,
        expected_stage="AFTER_FINAL_FULL_PREFLIGHT_BEFORE_GATE_B_APPROVAL",
        expected_disk_path=tmp_path,
        expected_kind="GATE_B_QUALIFICATION_PUBLICATION",
        expected_sequence=2,
    )
    assert replayed == record
    assert replayed_identity == _identity(path)


@pytest.mark.parametrize(
    "mutation",
    ["untrusted-basis", "wrong-session", "wrong-locks", "extra-field"],
)
def test_bootstrap_rejects_unjoined_gate_b_stage_resource_receipt(
    tmp_path: Path,
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _record, actor, locks, planned = _gate_b_resource_gate_fixture(
        tmp_path,
        mutation=mutation,
    )
    calibration, calibration_identity = _install_prospective_resource_replayer(
        monkeypatch
    )
    with pytest.raises(BOOTSTRAP.BootstrapError):
        BOOTSTRAP._read_gate_b_resource_gate(  # noqa: SLF001
            _identity(path),
            planned=planned,
            calibration_authorization_bundle=calibration,
            calibration_authorization_bundle_identity=calibration_identity,
            expected_actor=actor,
            expected_session_id="a" * 64,
            expected_lock_identities=locks,
            expected_path=path,
            expected_profile_stage=RESOURCE_ADMISSION.GATE_B_QUALIFICATION,
            expected_stage="AFTER_FINAL_FULL_PREFLIGHT_BEFORE_GATE_B_APPROVAL",
            expected_disk_path=tmp_path,
            expected_kind="GATE_B_QUALIFICATION_PUBLICATION",
            expected_sequence=2,
        )


def test_gate_b_owner_recloses_retained_lock_identity_at_each_gate(
    tmp_path: Path,
) -> None:
    lock_paths = tuple(tmp_path / f"live-{index}.lock" for index in range(3))
    descriptors = [QUALIFICATION._acquire_lock(path) for path in lock_paths]  # noqa: SLF001
    try:
        owner = object.__new__(QUALIFICATION.PersistentGateBOwner)
        owner.lock_paths = lock_paths
        owner._lock_fds = descriptors  # noqa: SLF001
        owner._process = SimpleNamespace(poll=lambda: None)  # noqa: SLF001
        owner.lock_identities = [
            QUALIFICATION._lock_identity(descriptor, path)  # noqa: SLF001
            for descriptor, path in zip(descriptors, lock_paths, strict=True)
        ]
        assert owner.current_lock_identities() == owner.lock_identities

        first_path = lock_paths[0]
        first_path.rename(first_path.with_suffix(".retained"))
        first_path.write_bytes(b"replacement")
        first_path.chmod(0o600)
        with pytest.raises(
            QUALIFICATION.QualificationError,
            match="qualification lock identity drifted",
        ):
            owner.current_lock_identities()
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def test_qualify_orders_locks_preflight_epoch_second_gate_bootstrap_and_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    manager_epoch = {
        "boot_id": "b" * 36,
        "manager_pid": 1,
        "manager_starttime": "1",
    }
    campaign = tmp_path / "run-ab16-fixture"
    output = tmp_path / "qualification"
    final_receipt_path = output / "final-full-preflight/receipt.json"
    renderer = _renderer(tmp_path / "bootstrap.py")
    owner_source = RESEARCH / "ab16_gate_b_qualification_v1.py"
    final_receipt = {"status": "PASS"}

    class FakeBootstrap:
        OWNER_OEXCL_PUBLISH_V1 = "publisher"
        GATE_B_OWNER_DRIVER_V1 = "driver"
        GATE_B_EPOCH_PURPOSE = "epoch"
        GATE_B_EPOCH_SCHEMA = "epoch-v3"
        GATE_B_PURPOSE = "approval"
        GATE_B_SCHEMA = "approval-v4"
        RESULT_SCHEMA = "bootstrap-v3"

        @staticmethod
        def _unterminated_canonical_mode_record(
            path: Path | str,
            label: str,
        ) -> tuple[object, dict[str, object]]:
            return BOOTSTRAP._unterminated_canonical_mode_record(path, label)  # noqa: SLF001

        @staticmethod
        def _validate_final_full_preflight(
            value: object,
            *,
            gate_a: object,
            planned: object,
            receipt_identity: object,
        ) -> object:
            del gate_a, planned
            assert value == final_receipt
            assert receipt_identity == _identity(final_receipt_path)
            return value

        @staticmethod
        def _capture_epoch(*, scripts: object, system_paths: object) -> dict[str, object]:
            del scripts, system_paths
            events.append("capture-epoch")
            return {"manager_epoch": manager_epoch, "transcript": {"fixture": True}}

        @staticmethod
        def _validate_gate_b_epoch_observation(value: object, **_kwargs: object) -> object:
            return value

        @staticmethod
        def _validate_gate_b(value: object) -> object:
            return value

    bootstrap = FakeBootstrap()
    prepared = {
        "bootstrap": bootstrap,
        "campaign": campaign,
        "candidate_identity": {"path": "/candidate", "sha256": "c" * 64, "size_bytes": 1},
        "gate_a": {
            "approval_id": "gate-a-fixture",
            "full_preflight_receipt_identity": {
                "mode": 0o444,
                "path": "/old/receipt.json",
                "sha256": "0" * 64,
                "size_bytes": 1,
            },
            "manager_epoch": manager_epoch,
            "planned_source_set_digest": "d" * 64,
            "repository_head": "e" * 40,
            "repository_root": str(ROOT),
            "run_nonce": campaign.name,
            "target_campaign_dir": str(campaign),
        },
        "gate_a_identity": {"path": "/gate-a.json", "sha256": "a" * 64, "size_bytes": 1},
        "output": output,
        "planned": {
            "script.ab16_campaign_bootstrap_v2": _identity(renderer),
            "script.package_independent_verifier_v1": _identity(renderer),
            "system.native_budget_helper": _native_helper_full(),
        },
        "planned_digest": "d" * 64,
        "budget_binding": {
            "bootstrap_budget_contract_identity": {
                "path": str(
                    campaign
                    / "bootstrap-authority/bootstrap-budget-contract.json"
                ),
                "sha256": "1" * 64,
                "size_bytes": 1,
            },
            "formal_root_budget_contract_identity": {
                "path": str(
                    campaign
                    / "formal-ab16/artifacts/formal-root-budget-contract.json"
                ),
                "sha256": "2" * 64,
                "size_bytes": 1,
            },
            "resource_budget_profile_identity": {
                "mode": 0o444,
                "path": str(tmp_path / "resource-budget-profile.json"),
                "sha256": "3" * 64,
                "size_bytes": 1,
            },
        },
        "resource_budget_profile_identity": {
            "mode": 0o444,
            "path": str(tmp_path / "resource-budget-profile.json"),
            "sha256": "3" * 64,
            "size_bytes": 1,
        },
        "resource_calibration_bundle_identities": {
            stage: {
                "path": str(tmp_path / f"calibration-{index}.json"),
                "sha256": f"{index + 3:x}" * 64,
                "size_bytes": index,
            }
            for index, stage in enumerate(
                BOOTSTRAP.RESOURCE_CALIBRATION_STAGES,
                start=1,
            )
        },
        "repository": ROOT,
        "scripts": {
            "ab16_campaign_bootstrap_v2": renderer,
            "ab16_gate_b_qualification_v1": owner_source,
        },
        "system_paths": {"python3_13": Path(os.path.realpath(sys.executable))},
    }
    prepare_count = 0

    def prepare(_args: object, observed_bootstrap: object) -> dict[str, object]:
        nonlocal prepare_count
        assert observed_bootstrap is bootstrap
        prepare_count += 1
        events.append("prepare-before-locks" if prepare_count == 1 else "prepare-under-locks")
        return dict(prepared)

    class FakeOwner:
        def __init__(self, **_kwargs: object) -> None:
            self.actor = {"pid": os.getpid(), "pid_starttime": "1", "role": "AB16_GATE_B_OWNER"}
            self.session_id = "f" * 64
            self.lock_identities = [
                {"path": path, "inode": index}
                for index, path in enumerate(QUALIFICATION.LOCK_PATHS)
            ]
            self._channels: tuple[socket.socket, socket.socket] | None = None

        def __enter__(self) -> FakeOwner:
            events.append("locks-acquired")
            return self

        def __exit__(self, *_args: object) -> None:
            if self._channels is not None:
                for channel in self._channels:
                    channel.close()

        def current_lock_identities(self) -> list[dict[str, object]]:
            events.append("locks-rechecked")
            return [dict(item) for item in self.lock_identities]

        def publish(
            self,
            *,
            kind: str,
            output_path: Path,
            record: dict[str, object],
        ) -> dict[str, object]:
            events.append(f"publish-{kind}")
            sequence = 1 if kind == "epoch" else 2
            rendered = {
                **record,
                "publisher": {
                    "actor": self.actor,
                    "qualification_session": {
                        "lock_identities": self.lock_identities,
                        "sequence": sequence,
                        "session_id": self.session_id,
                    },
                },
            }
            QUALIFICATION._write_exclusive(  # noqa: SLF001
                output_path,
                QUALIFICATION._canonical_json(rendered),  # noqa: SLF001
            )
            return rendered

        def attach_bootstrap_channel(self) -> socket.socket:
            events.append("attach-bootstrap")
            self._channels = socket.socketpair()
            return self._channels[0]

        def duplicate_lock_fds(self) -> tuple[int, ...]:
            return tuple(os.open("/dev/null", os.O_RDONLY) for _ in range(3))

        def release(self, *, bootstrap_result: bytes) -> None:
            assert json.loads(bootstrap_result)["status"] == (
                "FORMAL_CAMPAIGN_AUTHORITY_READY_NO_UNIT_LAUNCHED"
            )
            events.append("release-after-readback")

    def resource_gate(
        _path: Path,
        *,
        stage: str,
        **_kwargs: object,
    ) -> dict[str, object]:
        events.append(f"resource:{stage}")
        return {"stage": stage, "status": "PASS"}

    def preflight(
        _context: object,
        _args: object,
        destination: Path,
        *,
        resource_lock_fds: dict[str, int],
    ) -> None:
        assert set(resource_lock_fds) == set(QUALIFICATION.LOCK_PATHS)
        events.append("pinned-record-preflight")
        destination.mkdir()
        (destination / "receipt.json").write_bytes(
            QUALIFICATION._canonical_json(final_receipt)[:-1]  # noqa: SLF001
        )
        (destination / "receipt.json").chmod(0o444)

    def bootstrap_child(
        context: dict[str, object],
        _args: object,
        **_kwargs: object,
    ) -> tuple[bytes, dict[str, object]]:
        events.append("bootstrap-handoff-readback")
        value = {
            "campaign_dir": str(context["campaign"]),
            "gate_b_qualification_handoff": {"status": "PASS"},
            "schema": bootstrap.RESULT_SCHEMA,
            "status": "FORMAL_CAMPAIGN_AUTHORITY_READY_NO_UNIT_LAUNCHED",
        }
        return QUALIFICATION._canonical_json(value), value  # noqa: SLF001

    monkeypatch.setattr(QUALIFICATION, "_load_bootstrap", lambda _repository: bootstrap)
    monkeypatch.setattr(QUALIFICATION, "_prepare_qualification", prepare)
    monkeypatch.setattr(
        QUALIFICATION,
        "_load_resource_admission",
        lambda _context: RESOURCE_ADMISSION,
    )
    monkeypatch.setattr(
        QUALIFICATION,
        "_resource_calibration_authorization",
        lambda context, *, stage: (
            {"fixture": True, "stage": stage},
            context["resource_calibration_bundle_identities"][stage],
        ),
    )
    monkeypatch.setattr(QUALIFICATION, "PersistentGateBOwner", FakeOwner)
    monkeypatch.setattr(QUALIFICATION, "_resource_gate", resource_gate)
    monkeypatch.setattr(QUALIFICATION, "_run_pinned_gate_a_preflight", preflight)
    monkeypatch.setattr(QUALIFICATION, "_run_bootstrap_child", bootstrap_child)

    result = QUALIFICATION.qualify(
        SimpleNamespace(
            approval_id="gate-b-fixture",
            gate_a_receipt=tmp_path / "gate-a.json",
            offline_candidate=tmp_path / "candidate.json",
            repository_root=ROOT,
        )
    )
    assert result["status"] == "FORMAL_CAMPAIGN_AUTHORITY_READY_NO_UNIT_LAUNCHED"
    assert events == [
        "prepare-before-locks",
        "locks-acquired",
        "prepare-under-locks",
        "locks-rechecked",
        "resource:BEFORE_FINAL_FULL_PREFLIGHT",
        "locks-rechecked",
        "pinned-record-preflight",
        "capture-epoch",
        "publish-epoch",
        "locks-rechecked",
        "resource:AFTER_FINAL_FULL_PREFLIGHT_BEFORE_GATE_B_APPROVAL",
        "locks-rechecked",
        "publish-approval",
        "attach-bootstrap",
        "bootstrap-handoff-readback",
        "release-after-readback",
    ]
