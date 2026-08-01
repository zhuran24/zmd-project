from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
PACKAGE_SOURCE = RESEARCH / "ab16_resource_calibration_package_v1.py"
LOADER_SOURCE = RESEARCH / "ab16_resource_calibration_fd_loader_v1.py"
WORKLOAD_SOURCE = RESEARCH / "ab16_resource_calibration_workloads_v1.py"
RUNNER_SOURCE = RESEARCH / "ab16_resource_calibration_runner_v1.py"
PROTOCOL_SOURCE = RESEARCH / "ab16_resource_calibration_v1.py"
OBSERVER_SOURCE = RESEARCH / "ab16_resource_calibration_harness_v1.py"
REPLAY_A_SOURCE = RESEARCH / "replay_ab16_resource_calibration_v1.py"
REPLAY_B_SOURCE = RESEARCH / "replay_ab16_resource_calibration_alt_v1.py"
AGGREGATOR_SOURCE = RESEARCH / "ab16_resource_calibration_aggregator_v1.py"
GATE_B_SOURCE = RESEARCH / "ab16_gate_b_qualification_v1.py"
PRODUCTION_VERIFIER_SOURCE = RESEARCH / "package_independent_verifier_v1.py"
NATIVE_WRAPPER = RESEARCH / "ab16_native_budget_helper_v1.py"
NATIVE_BINARY = RESEARCH / "ab16_native_budget_helper_x86_64_v1.so"
PINNED_CALIBRATION_PYTHON = ROOT / ".venv-uvbolt-backup/bin/python"


def _load_package() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_test_ab16_resource_calibration_package_v1",
        PACKAGE_SOURCE,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PACKAGE = _load_package()


def _load_source(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PROTOCOL = _load_source(
    "_test_ab16_resource_calibration_protocol_for_package",
    PROTOCOL_SOURCE,
)
RUNNER = _load_source(
    "_test_ab16_resource_calibration_runner_for_package",
    RUNNER_SOURCE,
)
LOADER = _load_source(
    "_test_ab16_resource_calibration_fd_loader_for_package",
    LOADER_SOURCE,
)
WORKLOAD = _load_source(
    "_test_ab16_resource_calibration_workload_for_package",
    WORKLOAD_SOURCE,
)


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _member_identity(relative: str, source: Path) -> dict[str, object]:
    raw = source.read_bytes()
    return {
        "path": relative,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _absolute_identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "path": str(path.absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _content_identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _expected_tools() -> dict[str, dict[str, object]]:
    return {
        "aggregator": _content_identity(AGGREGATOR_SOURCE),
        "alternate_replayer": _content_identity(REPLAY_B_SOURCE),
        "fd_loader": _content_identity(LOADER_SOURCE),
        "observer_harness": _content_identity(OBSERVER_SOURCE),
        "package_verifier": _content_identity(PACKAGE_SOURCE),
        "primary_replayer": _content_identity(REPLAY_A_SOURCE),
        "protocol": _content_identity(PROTOCOL_SOURCE),
        "runner": _content_identity(RUNNER_SOURCE),
        "workload": _content_identity(WORKLOAD_SOURCE),
    }


class _BrokerTestHelper:
    final_seal_mask = 0x3F

    def get_seals(self, _descriptor: int) -> int:
        return self.final_seal_mask

    def has_writable_mapping(self, _descriptor: int) -> bool:
        return False


def _package_surface_closure(package_root: Path) -> dict[str, object]:
    receipt = json.loads((package_root / "receipt.json").read_bytes())
    host_content = {
        label: {
            "sha256": identity["sha256"],
            "size_bytes": identity["size_bytes"],
        }
        for label, identity in sorted(
            receipt["host_runtime_identities"].items()
        )
    }
    return {
        "host_runtime_content_sha256": hashlib.sha256(
            _canonical(host_content)
        ).hexdigest(),
        "layout": receipt["layout"],
        "package_receipt_identity": _receipt_identity(package_root),
        "package_schema_version": receipt["schema_version"],
        "source_sets_sha256": hashlib.sha256(
            _canonical(receipt["source_sets"])
        ).hexdigest(),
    }


def _synthetic_focused_surface_closure(tmp_path: Path) -> dict[str, object]:
    return {
        "host_runtime_content_sha256": hashlib.sha256(_canonical({})).hexdigest(),
        "layout": PACKAGE.FOCUSED_FIXTURE_LAYOUT,
        "package_receipt_identity": {
            "path": str(
                (tmp_path / "synthetic-package/receipt.json").absolute()
            ),
            "sha256": "a" * 64,
            "size_bytes": 1,
        },
        "package_schema_version": PACKAGE.PACKAGE_SCHEMA,
        "source_sets_sha256": hashlib.sha256(_canonical({})).hexdigest(),
    }


def _write_fixtures(tmp_path: Path) -> tuple[Path, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    planned = {
        "gate_b": _member_identity("roles/gate-b.py", GATE_B_SOURCE),
        "native_helper_binary": _member_identity(
            "native/helper.so",
            NATIVE_BINARY,
        ),
        "native_helper_wrapper": _member_identity(
            "roles/native-helper.py",
            NATIVE_WRAPPER,
        ),
        "package_verifier": _member_identity(
            "roles/production-package-verifier.py",
            PRODUCTION_VERIFIER_SOURCE,
        ),
    }
    digest = hashlib.sha256(_canonical(planned)).hexdigest()
    gate_b = {
        "gate_b_module_member": "roles/gate-b.py",
        "native_helper_binary_member": "native/helper.so",
        "native_helper_wrapper_member": "roles/native-helper.py",
        "package_verifier_member": "roles/production-package-verifier.py",
        "planned_source_identities": planned,
        "planned_source_observation": {
            "planned_source_identities": planned,
            "planned_source_set_digest": digest,
        },
        "planned_source_set_digest": digest,
        "schema_version": (
            "noncert-cuts-ab16-resource-calibration-gate-b-fixture-v1"
        ),
        "stage": "GATE_B_QUALIFICATION",
    }
    formal = {
        "aggregate_budget_bytes": 16 * 1024 * 1024,
        "ledger_segment_maximum_bytes": 64 * 1024,
        "model_maximum_bytes": 8 * 1024 * 1024,
        "native_helper_binary_member": "native/helper.so",
        "native_helper_wrapper_member": "roles/native-helper.py",
        "schema_version": (
            "noncert-cuts-ab16-resource-calibration-formal-fixture-v1"
        ),
        "stage": "FORMAL_ORGANIC_ARM",
        "variable_count": 8,
    }
    gate_path = tmp_path / "gate-b-fixture.json"
    formal_path = tmp_path / "formal-fixture.json"
    full_path = tmp_path / "full-fixture.json"
    gate_path.write_bytes(_canonical(gate_b))
    formal_path.write_bytes(_canonical(formal))
    full_path.write_bytes(
        _canonical(
            {
                "schema_version": (
                    "noncert-cuts-ab16-resource-calibration-full-fixture-v1"
                ),
                "stage": "FULL_PREFLIGHT",
            }
        )
    )
    return gate_path, formal_path, full_path


def _build(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    gate_fixture, formal_fixture, full_fixture = _write_fixtures(tmp_path)
    package_root = tmp_path / "calibration-package"
    members = {
        "devtools/research_run_contract.py": ROOT
        / "devtools/research_run_contract.py",
        "fixtures/formal.json": formal_fixture,
        "fixtures/full.json": full_fixture,
        "fixtures/gate-b.json": gate_fixture,
        "native/helper.so": NATIVE_BINARY,
        "roles/calibration-loader.py": LOADER_SOURCE,
        "roles/calibration-aggregator.py": AGGREGATOR_SOURCE,
        "roles/calibration-observer.py": OBSERVER_SOURCE,
        "roles/calibration-package.py": PACKAGE_SOURCE,
        "roles/calibration-protocol.py": PROTOCOL_SOURCE,
        "roles/calibration-replay-alt.py": REPLAY_B_SOURCE,
        "roles/calibration-replay.py": REPLAY_A_SOURCE,
        "roles/calibration-runner.py": RUNNER_SOURCE,
        "roles/calibration-workload.py": WORKLOAD_SOURCE,
        "roles/gate-b.py": GATE_B_SOURCE,
        "roles/native-helper.py": NATIVE_WRAPPER,
        "roles/production-package-verifier.py": PRODUCTION_VERIFIER_SOURCE,
        "src/cuts/__init__.py": ROOT / "src/cuts/__init__.py",
        "src/cuts/ledger.py": ROOT / "src/cuts/ledger.py",
        "src/io/strict_json.py": ROOT / "src/io/strict_json.py",
        "src/models/cut_manager.py": ROOT / "src/models/cut_manager.py",
    }
    receipt = PACKAGE.build_calibration_package(
        package_root,
        members=members,
        roles={
            "calibration-aggregator": "roles/calibration-aggregator.py",
            "calibration-alternate-replay": "roles/calibration-replay-alt.py",
            "calibration-fd-loader": "roles/calibration-loader.py",
            "calibration-observer": "roles/calibration-observer.py",
            "calibration-package-verifier": "roles/calibration-package.py",
            "calibration-primary-replay": "roles/calibration-replay.py",
            "calibration-protocol": "roles/calibration-protocol.py",
            "calibration-runner": "roles/calibration-runner.py",
            "calibration-workload": "roles/calibration-workload.py",
        },
        stage_fixtures={
            "FORMAL_ORGANIC_ARM": "fixtures/formal.json",
            "FULL_PREFLIGHT": "fixtures/full.json",
            "GATE_B_QUALIFICATION": "fixtures/gate-b.json",
        },
    )
    return package_root, receipt


def _receipt_identity(package_root: Path) -> dict[str, object]:
    raw = (package_root / "receipt.json").read_bytes()
    return {
        "path": str(package_root / "receipt.json"),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _package_declaration(
    tmp_path: Path,
    package_root: Path,
    *,
    stage: str,
    workload_identity: dict[str, object] | None = None,
    command_tail: list[str] | None = None,
) -> dict[str, object]:
    profile = tmp_path / "profile.json"
    if not profile.exists():
        profile.write_bytes(b"{}\n")
    receipt_identity = _receipt_identity(package_root)
    receipt = json.loads((package_root / "receipt.json").read_bytes())
    roles = receipt["roles"]
    fixtures = receipt["stage_fixtures"]
    verifier_identity = _absolute_identity(
        package_root / roles["calibration-package-verifier"]
    )
    members = {
        "calibration_fd_loader": _absolute_identity(
            package_root / roles["calibration-fd-loader"]
        ),
        "calibration_observer": _absolute_identity(
            package_root / roles["calibration-observer"]
        ),
        "calibration_package_receipt": receipt_identity,
        "calibration_package_verifier": verifier_identity,
        "calibration_package_verifier_host": _absolute_identity(PACKAGE_SOURCE),
        "calibration_stage_fixture": _absolute_identity(
            package_root / fixtures[stage]
        ),
        "calibration_protocol": _absolute_identity(
            package_root / roles["calibration-protocol"]
        ),
        "calibration_runner": _absolute_identity(
            package_root / roles["calibration-runner"]
        ),
        "calibration_workload": (
            workload_identity
            if workload_identity is not None
            else _absolute_identity(
                package_root / roles["calibration-workload"]
            )
        ),
        "python_interpreter": _absolute_identity(Path(sys.executable).resolve()),
    }
    command = [
        str(Path(sys.executable).resolve()),
        "-I",
        "-B",
        f"/proc/self/fd/{RUNNER.PACKAGE_WORKLOAD_FDS['loader']}",
        "--stage",
        stage,
        "--package-root-fd",
        str(RUNNER.PACKAGE_WORKLOAD_FDS["package_root"]),
        "--package-root-path",
        str(package_root),
        "--package-receipt-sha256",
        str(receipt_identity["sha256"]),
        "--package-receipt-size",
        str(receipt_identity["size_bytes"]),
        "--verifier-fd",
        str(RUNNER.PACKAGE_WORKLOAD_FDS["verifier"]),
        "--verifier-sha256",
        str(verifier_identity["sha256"]),
        "--workload-fd",
        str(RUNNER.PACKAGE_WORKLOAD_FDS["workload"]),
        "--fixture-fd",
        str(RUNNER.PACKAGE_WORKLOAD_FDS["fixture"]),
        "--stage-root-fd",
        str(RUNNER.PACKAGE_WORKLOAD_FDS["stage_root"]),
        "--result-fd",
        str(RUNNER.PACKAGE_WORKLOAD_FDS["result"]),
    ]
    if command_tail is not None:
        command[-1:] = command_tail
    surface = PROTOCOL.build_execution_surface(
        stage=stage,
        command=command,
        working_directory=str(ROOT.absolute()),
        test_inventory_count=0,
        test_inventory_sha256=hashlib.sha256(b"").hexdigest(),
        xdist_available=False,
        worker_mode="single-worker",
        worker_count=1,
        member_identities=members,
        control_plane_identities={
            "code_assets": _absolute_identity(
                ROOT / "data/repository_governance/code_assets.json"
            ),
            "profile": _absolute_identity(profile),
            "project_lock": _absolute_identity(ROOT / "PROJECT_LOCK.md"),
        },
        portable_package=_package_surface_closure(package_root),
        workload_fidelity_class=f"CAPABILITY_E2E_{stage}",
        launch_admissible=False,
    )
    return PROTOCOL.build_declaration(
        declaration_id=f"package-declaration-{stage.lower()}",
        cohort_id="package-calibration-cohort-0001",
        execution_surface=surface,
        harness_identity=members["calibration_runner"],
        observer_identity=members["calibration_observer"],
        installed_profile_identity=surface["control_plane_identities"][
            "profile"
        ],
    )


def _bundle_fixture(tmp_path: Path, stage: str) -> dict[str, object]:
    profile = tmp_path / "bundle-profile.json"
    profile.write_bytes(b"{}\n")
    surface = PROTOCOL.build_execution_surface(
        stage=stage,
        command=(
            [str(Path(sys.executable).resolve()), "scripts/preflight_gate.py", "--full"]
            if stage == "FULL_PREFLIGHT"
            else [str(Path(sys.executable).resolve()), "package-calibration", stage]
        ),
        working_directory=str(ROOT.absolute()),
        test_inventory_count=1 if stage == "FULL_PREFLIGHT" else 0,
        test_inventory_sha256=(
            "1" * 64
            if stage == "FULL_PREFLIGHT"
            else hashlib.sha256(b"").hexdigest()
        ),
        xdist_available=stage == "FULL_PREFLIGHT",
        worker_mode=(
            "pytest-xdist-auto"
            if stage == "FULL_PREFLIGHT"
            else "single-worker"
        ),
        worker_count=2 if stage == "FULL_PREFLIGHT" else 1,
        member_identities={
            "python_interpreter": _absolute_identity(
                Path(sys.executable).resolve()
            ),
            "runner": _absolute_identity(RUNNER_SOURCE),
        },
        control_plane_identities={
            "code_assets": _absolute_identity(
                ROOT / "data/repository_governance/code_assets.json"
            ),
            "profile": _absolute_identity(profile),
            "project_lock": _absolute_identity(ROOT / "PROJECT_LOCK.md"),
        },
        portable_package=_synthetic_focused_surface_closure(tmp_path),
        workload_fidelity_class=f"SYNTHETIC_BUNDLE_FIXTURE_{stage}",
        launch_admissible=False,
    )
    return {
        "aggregate_identity": _absolute_identity(profile),
        "authority_scope": PROTOCOL.AUTHORITY_SCOPE,
        "authorizations": dict(PROTOCOL.FALSE_AUTHORIZATIONS),
        "comparable_samples": [{}, {}, {}],
        "execution_surface": surface,
        "execution_surface_sha256": surface["execution_surface_sha256"],
        "outside_replays": {},
        "profile_candidate_binding": {},
        "profile_identity": _absolute_identity(profile),
        "profile_internal_sha256": "2" * 64,
        "schema_version": PROTOCOL.AUTHORIZATION_BUNDLE_SCHEMA,
        "stage": stage,
        "status": "ACCEPTED",
    }


def _read_exact(descriptor: int, size: int) -> bytes:
    result = b""
    while len(result) < size:
        block = os.read(descriptor, size - len(result))
        assert block
        result += block
    return result


def _run_loader(
    package_root: Path,
    *,
    stage: str,
    stage_root: Path,
) -> tuple[subprocess.CompletedProcess[bytes], dict[str, Any] | None]:
    expected = _receipt_identity(package_root)
    with PACKAGE.RetainedCalibrationPackage.open(
        package_root,
        expected_receipt_identity=expected,
    ) as package:
        loader_fd = package.open_role("calibration-fd-loader")
        verifier_fd = package.open_role("calibration-package-verifier")
        workload_fd = package.open_role("calibration-workload")
        fixture_fd = package.open_fixture(stage)
        stage_fd = os.open(
            stage_root,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        result_read, result_write = os.pipe2(os.O_CLOEXEC)
        verifier_relative = package.receipt["roles"][
            "calibration-package-verifier"
        ]
        verifier_identity = package.receipt["member_identities"][
            verifier_relative
        ]
        command = [
            str(PINNED_CALIBRATION_PYTHON),
            "-I",
            "-B",
            f"/proc/self/fd/{loader_fd}",
            "--stage",
            stage,
            "--package-root-fd",
            str(package.root_fd),
            "--package-root-path",
            str(package_root),
            "--package-receipt-sha256",
            str(expected["sha256"]),
            "--package-receipt-size",
            str(expected["size_bytes"]),
            "--verifier-fd",
            str(verifier_fd),
            "--verifier-sha256",
            str(verifier_identity["sha256"]),
            "--workload-fd",
            str(workload_fd),
            "--fixture-fd",
            str(fixture_fd),
            "--stage-root-fd",
            str(stage_fd),
            "--result-fd",
            str(result_write),
        ]
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                pass_fds=(
                    package.root_fd,
                    loader_fd,
                    verifier_fd,
                    workload_fd,
                    fixture_fd,
                    stage_fd,
                    result_write,
                ),
                check=False,
                timeout=20,
            )
        finally:
            os.close(result_write)
            for descriptor in (
                loader_fd,
                verifier_fd,
                workload_fd,
                fixture_fd,
                stage_fd,
            ):
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        if completed.returncode != 0:
            os.close(result_read)
            return completed, None
        size = int.from_bytes(_read_exact(result_read, 4), "big")
        result = json.loads(_read_exact(result_read, size))
        os.close(result_read)
        return completed, result


def test_package_is_closed_no_overwrite_and_self_excluding(
    tmp_path: Path,
) -> None:
    package_root, receipt = _build(tmp_path)
    assert receipt["schema_version"] == PACKAGE.PACKAGE_SCHEMA
    assert receipt["authorizations"] == PACKAGE.FALSE_AUTHORIZATIONS
    assert receipt["terminal_self_exclusion"] == {
        "excluded_from_manifest": "receipt.json",
        "self_hash_or_size_present": False,
    }
    assert all(
        entry["path"] != "receipt.json"
        for entry in receipt["manifest"]["entries"]
    )
    assert PACKAGE.verify_calibration_package(
        package_root,
        expected_receipt_identity=_receipt_identity(package_root),
    ) == receipt
    with pytest.raises(Exception, match="NO_OVERWRITE_COLLISION"):
        _build(tmp_path)


def test_bundle_publisher_emits_canonical_detached3_closed_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "bundle-set"
    result = RUNNER.publish_calibration_authorization_bundle_set(
        root,
        bundles={
            stage: _bundle_fixture(tmp_path, stage)
            for stage in PROTOCOL.STAGES
        },
    )
    bundle_set = result["bundle_set"]
    assert set(bundle_set["resource_calibration_bundle_identities"]) == (
        PROTOCOL.STAGES
    )
    assert set(bundle_set["resource_calibration_authorization_bundles"]) == (
        PROTOCOL.STAGES
    )
    assert result["receipt"]["terminal_self_exclusion"] == {
        "excluded_from_manifest": "receipt.json",
        "self_hash_or_size_present": False,
    }
    for stage, relative in RUNNER.BUNDLE_PATHS.items():
        raw = (root / relative).read_bytes()
        assert raw == PROTOCOL.canonical_json_bytes(
            bundle_set["resource_calibration_authorization_bundles"][stage][
                "record"
            ]
        )


def test_package_rejects_member_tamper_and_extra_node(tmp_path: Path) -> None:
    package_root, _receipt = _build(tmp_path)
    target = package_root / "roles/calibration-workload.py"
    target.chmod(0o600)
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(PACKAGE.CalibrationPackageError):
        PACKAGE.verify_calibration_package(
            package_root,
            expected_receipt_identity=_receipt_identity(package_root),
        )

    package_root_2, _receipt_2 = _build(tmp_path / "second")
    (package_root_2 / "unknown").write_bytes(b"ambient")
    with pytest.raises(Exception, match="ARTIFACT_ROOT_CLOSURE_MISMATCH"):
        PACKAGE.verify_calibration_package(
            package_root_2,
            expected_receipt_identity=_receipt_identity(package_root_2),
        )


def test_retained_package_rejects_root_swap_before_ownership_transfer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root, _receipt = _build(tmp_path)
    expected = _receipt_identity(package_root)
    moved = tmp_path / "calibration-package-moved"
    original = PACKAGE.verify_retained_calibration_package

    def verify_then_swap(
        root_fd: int,
        root: Path,
        *,
        expected_receipt_identity: dict[str, object],
    ) -> dict[str, object]:
        receipt = original(
            root_fd,
            root,
            expected_receipt_identity=expected_receipt_identity,
        )
        package_root.rename(moved)
        package_root.mkdir()
        return receipt

    monkeypatch.setattr(
        PACKAGE,
        "verify_retained_calibration_package",
        verify_then_swap,
    )
    before_fds = len(os.listdir("/proc/self/fd"))
    with pytest.raises(
        PACKAGE.CalibrationPackageError,
        match="CALIBRATION_PACKAGE_ROOT_REJOIN_FAILED",
    ):
        PACKAGE.RetainedCalibrationPackage.open(
            package_root,
            expected_receipt_identity=expected,
        )
    assert len(os.listdir("/proc/self/fd")) == before_fds
    assert not any(package_root.iterdir())
    assert (moved / "receipt.json").is_file()


def test_retained_package_post_open_baseexception_is_fd_neutral(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root, _receipt = _build(tmp_path)
    expected = _receipt_identity(package_root)
    real_fstat = PACKAGE.os.fstat
    armed = True

    def fail_first_fstat(descriptor: int) -> os.stat_result:
        nonlocal armed
        if armed:
            armed = False
            raise RuntimeError("injected root fstat failure")
        return real_fstat(descriptor)

    before = len(os.listdir("/proc/self/fd"))
    monkeypatch.setattr(PACKAGE.os, "fstat", fail_first_fstat)
    with pytest.raises(RuntimeError, match="injected root fstat failure"):
        PACKAGE.RetainedCalibrationPackage.open(
            package_root,
            expected_receipt_identity=expected,
        )
    assert len(os.listdir("/proc/self/fd")) == before


def test_retained_member_cleanup_preserves_primary_if_close_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root, _receipt = _build(tmp_path)
    expected = _receipt_identity(package_root)
    with PACKAGE.RetainedCalibrationPackage.open(
        package_root,
        expected_receipt_identity=expected,
    ) as package:
        real_fstat = PACKAGE.os.fstat
        real_close = PACKAGE.os.close
        cleanup = False

        def fail_member_fstat(descriptor: int) -> os.stat_result:
            nonlocal cleanup
            cleanup = True
            raise RuntimeError("injected member validation failure")

        def close_then_fail(descriptor: int) -> None:
            real_close(descriptor)
            if cleanup:
                raise OSError("injected cleanup close failure")

        before = len(os.listdir("/proc/self/fd"))
        monkeypatch.setattr(PACKAGE.os, "fstat", fail_member_fstat)
        monkeypatch.setattr(PACKAGE.os, "close", close_then_fail)
        with pytest.raises(
            RuntimeError,
            match="injected member validation failure",
        ) as captured:
            PACKAGE._read_member(  # noqa: SLF001
                package.root_fd,
                "roles/calibration-workload.py",
            )
        assert any(
            "descriptor close failed" in note
            for note in getattr(captured.value, "__notes__", ())
        )
        monkeypatch.setattr(PACKAGE.os, "fstat", real_fstat)
        monkeypatch.setattr(PACKAGE.os, "close", real_close)
        assert len(os.listdir("/proc/self/fd")) == before


def test_focused_gate_b_fixture_is_not_accepted_by_portable_loader(
    tmp_path: Path,
) -> None:
    package_root, _receipt = _build(tmp_path)
    stage_root = tmp_path / "gate-b-stage"
    stage_root.mkdir()
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    completed, result = _run_loader(
        package_root,
        stage="GATE_B_QUALIFICATION",
        stage_root=stage_root,
    )
    assert completed.returncode == 2
    assert result is None
    assert b"requires one portable package-v2 closure" in completed.stderr
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert after == before
    forbidden = {
        "A039",
        "attempt-consumption.json",
        "formal-selection.json",
        "gate-b-approval.json",
    }
    assert not forbidden & {path.name for path in tmp_path.rglob("*")}


@pytest.mark.parametrize(
    "stage",
    ["GATE_B_QUALIFICATION", "FORMAL_ORGANIC_ARM"],
)
def test_runner_binds_exact_retained_package_command_and_members(
    tmp_path: Path,
    stage: str,
) -> None:
    package_root, _receipt = _build(tmp_path)
    workload = RUNNER._validated_package_workload(  # noqa: SLF001
        _package_declaration(tmp_path, package_root, stage=stage),
        expected_calibration_tool_identities=_expected_tools(),
    )
    try:
        assert workload.command[3] == (
            f"/proc/self/fd/{RUNNER.PACKAGE_WORKLOAD_FDS['loader']}"
        )
        assert workload.package.root_path == package_root
    finally:
        workload.close()


def test_runner_rejects_ambient_workload_path_and_command_drift(
    tmp_path: Path,
) -> None:
    package_root, _receipt = _build(tmp_path)
    ambient = tmp_path / "ambient-workload.py"
    ambient.write_bytes(WORKLOAD_SOURCE.read_bytes())
    declaration = _package_declaration(
        tmp_path,
        package_root,
        stage="GATE_B_QUALIFICATION",
        workload_identity=_absolute_identity(ambient),
    )
    with pytest.raises(
        RUNNER.CalibrationPublicationError,
        match="package member path differs",
    ):
        RUNNER._validated_package_workload(  # noqa: SLF001
            declaration,
            expected_calibration_tool_identities=_expected_tools(),
        )

    drifted = _package_declaration(
        tmp_path,
        package_root,
        stage="GATE_B_QUALIFICATION",
        command_tail=["11"],
    )
    with pytest.raises(
        RUNNER.CalibrationPublicationError,
        match="retained-FD command",
    ):
        RUNNER._validated_package_workload(  # noqa: SLF001
            drifted,
            expected_calibration_tool_identities=_expected_tools(),
        )


def test_exact_formal_broker_enforces_label_class_and_fixed_maximum(
    tmp_path: Path,
) -> None:
    root_fd = os.open(
        tmp_path,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    payload_file = tempfile.TemporaryFile(dir=tmp_path)
    payload_fd = payload_file.fileno()
    try:
        raw = b"bounded formal calibration payload\n"
        assert os.write(payload_fd, raw) == len(raw)
        broker = WORKLOAD._CalibrationBroker(  # noqa: SLF001
            root_fd=root_fd,
            helper=_BrokerTestHelper(),
            aggregate_budget=8192,
            exact_organic=True,
            arm_slot="bundle-ab-treatment",
            artifact_maxima={
                "module-origin receipt": {
                    "artifact_class": "metadata",
                    "maximum_bytes": 4096,
                }
            },
        )
        base = {
            "absolute_path": "/ab16-calibration/formal/attempt/"
            "supervisor-module-origin-receipt.json",
            "artifact_class": "metadata",
            "kind": "regular",
            "label": "module-origin receipt",
            "maximum_bytes": 4096,
            "relative_path": "attempt/supervisor-module-origin-receipt.json",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
        for drift in (
            {"label": "unregistered evidence"},
            {"artifact_class": "publication"},
            {"maximum_bytes": 4095},
        ):
            with pytest.raises(
                WORKLOAD.CalibrationWorkloadError,
                match="regular request differs",
            ):
                broker.publish_regular({**base, **drift}, payload_fd)
        receipt = broker.publish_regular(base, payload_fd)
        assert receipt == {
            "path": base["absolute_path"],
            "sha256": base["sha256"],
            "size_bytes": len(raw),
        }
    finally:
        payload_file.close()
        os.close(root_fd)


def test_exact_formal_broker_enforces_append_sequence_and_arm_slot(
    tmp_path: Path,
) -> None:
    root_fd = os.open(
        tmp_path,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    payload_file = tempfile.TemporaryFile(dir=tmp_path)
    payload_fd = payload_file.fileno()
    try:
        raw = b'{"event":"bounded"}\n'
        assert os.write(payload_fd, raw) == len(raw)
        broker = WORKLOAD._CalibrationBroker(  # noqa: SLF001
            root_fd=root_fd,
            helper=_BrokerTestHelper(),
            aggregate_budget=8192,
            exact_organic=True,
            arm_slot="bundle-ab-treatment",
            artifact_maxima={
                "cut ledger segment": {
                    "artifact_class": "ledger",
                    "maximum_bytes": 4096,
                }
            },
        )
        request = {
            "arm_slot": "bundle-ab-treatment",
            "artifact_class": "ledger",
            "channel": "arm-bundle-ab-treatment-cut-ledger",
            "kind": "append",
            "label": "cut ledger segment",
            "maximum_bytes": 4096,
            "sequence": 0,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
        for drift in (
            {"arm_slot": "bundle-ba-treatment"},
            {"sequence": 1},
            {"label": "runtime cut segment"},
        ):
            with pytest.raises(
                WORKLOAD.CalibrationWorkloadError,
                match="fixed aggregate budget",
            ):
                broker.publish({**request, **drift}, payload_fd)
        broker.publish(request, payload_fd)
        with pytest.raises(
            WORKLOAD.CalibrationWorkloadError,
            match="fixed aggregate budget",
        ):
            broker.publish(request, payload_fd)
    finally:
        payload_file.close()
        os.close(root_fd)


def test_focused_formal_fixture_is_not_accepted_by_portable_loader(
    tmp_path: Path,
) -> None:
    assert PINNED_CALIBRATION_PYTHON.is_symlink()
    package_root, _receipt = _build(tmp_path)
    stage_root = tmp_path / "formal-stage"
    stage_root.mkdir()
    completed, result = _run_loader(
        package_root,
        stage="FORMAL_ORGANIC_ARM",
        stage_root=stage_root,
    )
    assert completed.returncode == 2
    assert result is None
    assert b"requires one portable package-v2 closure" in completed.stderr
    assert list(stage_root.iterdir()) == []
    forbidden = {
        "A039",
        "attempt-consumption.json",
        "formal-selection.json",
        "gate-b-approval.json",
    }
    assert not forbidden & {path.name for path in tmp_path.rglob("*")}


def test_portable_retained_fd_import_surface_positive_control_has_zero_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = tmp_path / "portable-positive"
    python_prefix = package_root / "runtime/python-base"
    site_packages = package_root / "runtime/site-packages"
    snapshot = package_root / "materialized/repository"
    stdlib = python_prefix / "lib/python3.13"
    for directory in (site_packages, snapshot, stdlib):
        directory.mkdir(parents=True, exist_ok=True)
    root_fd = os.open(
        package_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    previous_cwd = Path.cwd()
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    try:
        monkeypatch.setattr(
            sys,
            "path",
            [f"/proc/self/fd/{root_fd}/runtime/python-base/lib/python3.13"],
        )
        LOADER._install_portable_import_surface(  # noqa: SLF001
            package_root_fd=root_fd,
            package_root_path=package_root,
            receipt={
                "layout": PACKAGE.PORTABLE_CANDIDATE_LAYOUT,
                "repository_snapshot": {
                    "repository_prefix": "materialized/repository"
                },
                "runtime_layout": {
                    "cpython_version": "3.13.13",
                    "libpython_relative_path": (
                        "runtime/python-base/lib/libpython3.13.so.1.0"
                    ),
                    "ortools_version": "9.15.6755",
                    "python_prefix": "runtime/python-base",
                    "python_relative_path": (
                        "runtime/python-base/bin/python3.13"
                    ),
                    "site_packages_prefix": "runtime/site-packages",
                    "stdlib_prefix": "runtime/python-base/lib/python3.13",
                },
                "schema_version": PACKAGE.PACKAGE_SCHEMA,
            },
        )
        assert sys.path[:2] == [
            f"/proc/self/fd/{root_fd}/materialized/repository",
            f"/proc/self/fd/{root_fd}/runtime/site-packages",
        ]
        assert Path.cwd() == Path(
            f"/proc/self/fd/{root_fd}/materialized/repository"
        ).resolve()
    finally:
        os.chdir(previous_cwd)
        os.close(root_fd)
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert after == before


def test_transient_cgroup_rejects_fake_tmp_parent(tmp_path: Path) -> None:
    with pytest.raises(
        RUNNER.CalibrationPublicationError,
        match="CALIBRATION_CGROUP_PARENT_UNTRUSTED",
    ):
        RUNNER.TransientCalibrationCgroup.create(
            tmp_path,
            name="ab16-calibration-fake",
            stage="GATE_B_QUALIFICATION",
        )


def test_transient_cgroup_name_is_no_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "ab16-calibration-reused").mkdir()
    monkeypatch.setattr(
        RUNNER,
        "_require_cgroup2_delegated_parent",
        lambda _path: None,
    )
    with pytest.raises(
        RUNNER.CalibrationPublicationError,
        match="CALIBRATION_CGROUP_NOT_FRESH",
    ):
        RUNNER.TransientCalibrationCgroup.create(
            tmp_path,
            name="ab16-calibration-reused",
            stage="GATE_B_QUALIFICATION",
        )
