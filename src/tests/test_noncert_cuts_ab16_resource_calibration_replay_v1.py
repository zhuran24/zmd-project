from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
PROTOCOL_PATH = RESEARCH / "ab16_resource_calibration_v1.py"
PUBLISHER_PATH = RESEARCH / "ab16_resource_calibration_runner_v1.py"
REPLAY_A = RESEARCH / "replay_ab16_resource_calibration_v1.py"
REPLAY_B = RESEARCH / "replay_ab16_resource_calibration_alt_v1.py"
ADMISSION_PATH = RESEARCH / "ab16_resource_admission_v1.py"
FD_LOADER_PATH = RESEARCH / "ab16_resource_calibration_fd_loader_v1.py"
OBSERVER_PATH = RESEARCH / "ab16_resource_calibration_harness_v1.py"
PACKAGE_VERIFIER_PATH = RESEARCH / "ab16_resource_calibration_package_v1.py"
WORKLOAD_PATH = RESEARCH / "ab16_resource_calibration_workloads_v1.py"
AGGREGATOR_PATH = RESEARCH / "ab16_resource_calibration_aggregator_v1.py"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAL = _load(PROTOCOL_PATH, "_test_calibration_protocol_replay")
PUBLISHER = _load(PUBLISHER_PATH, "_test_calibration_publisher")
ADMISSION = _load(ADMISSION_PATH, "_test_calibration_actual_admission")
PRIMARY_REPLAYER = _load(REPLAY_A, "_test_calibration_primary_replayer")
ALTERNATE_REPLAYER = _load(REPLAY_B, "_test_calibration_alternate_replayer")
AGGREGATOR = _load(AGGREGATOR_PATH, "_test_calibration_aggregator")


def _identity(path: Path, value: object) -> dict[str, object]:
    raw = CAL.canonical_json_bytes(value)
    return {
        "path": str(path.absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _source_identity(tmp_path: Path, name: str) -> dict[str, object]:
    raw = name.encode("ascii")
    path = (tmp_path / name).absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _portable_package(tmp_path: Path) -> dict[str, object]:
    return {
        "host_runtime_content_sha256": hashlib.sha256(
            b"host-runtime"
        ).hexdigest(),
        "layout": CAL.PORTABLE_PACKAGE_LAYOUT,
        "package_receipt_identity": _source_identity(
            tmp_path,
            "calibration-package/receipt.json",
        ),
        "package_schema_version": CAL.CALIBRATION_PACKAGE_SCHEMA,
        "source_sets_sha256": hashlib.sha256(b"source-sets").hexdigest(),
    }


def _actual_identity(path: Path) -> dict[str, object]:
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
        "aggregator": _content_identity(AGGREGATOR_PATH),
        "alternate_replayer": _content_identity(REPLAY_B),
        "fd_loader": _content_identity(
            RESEARCH / "ab16_resource_calibration_fd_loader_v1.py"
        ),
        "observer_harness": _content_identity(
            RESEARCH / "ab16_resource_calibration_harness_v1.py"
        ),
        "package_verifier": _content_identity(
            RESEARCH / "ab16_resource_calibration_package_v1.py"
        ),
        "primary_replayer": _content_identity(REPLAY_A),
        "protocol": _content_identity(PROTOCOL_PATH),
        "runner": _content_identity(PUBLISHER_PATH),
        "workload": _content_identity(
            RESEARCH / "ab16_resource_calibration_workloads_v1.py"
        ),
    }


def _observer(root: Path, index: int) -> dict[str, object]:
    return {
        "authority_scope": CAL.AUTHORITY_SCOPE,
        "authorizations": dict(CAL.FALSE_AUTHORIZATIONS),
        "cgroup": {
            "disappeared_after_peak_read": True,
            "identity": {
                "device": 10,
                "inode": 1000 + index,
                "mode": 0o40700,
                "path": f"/user.slice/ab16-calibration-{index}.scope",
                "uid": 1000,
            },
            "peak_read_before_disappearance": True,
        },
        "disk": {
            "after_bytes": 1000,
            "before_bytes": 900,
            "cgroup_io": {
                "rows_after": [{"device": "8:0", "wbytes": 200 + index}],
                "wbytes_after": 200 + index,
                "wbytes_before": 0,
                "wbytes_delta": 200 + index,
            },
            "growth_peak_bytes": 200 + index,
            "measurement_rule": (
                "MAX_RETAINED_TREE_POLLING_AND_CGROUP_IO_WBYTES"
            ),
            "peak_bytes": 1100 + index,
            "polling_growth_peak_bytes": 200 + index,
            "target_identity": {
                "device": 11,
                "inode": 2000 + index,
                "mode": 0o40700,
                "path": str((root / f"stage-{index}").absolute()),
                "uid": 1000,
            },
        },
        "cgroup_limits": {
            "memory.high": 28 * 1024**3,
            "memory.max": 35 * 1024**3,
            "memory.swap.max": 8 * 1024**3,
        },
        "memory_peak_bytes": 2000 + index,
        "observer_process_identity": {
            "pid": 3000 + index,
            "starttime": 4000 + index,
        },
        "sample_count": 4,
        "schema_version": CAL.OBSERVER_RESULT_SCHEMA,
        "status": "PEAKS_CAPTURED_BEFORE_CGROUP_DISAPPEARANCE",
        "swap_peak_bytes": 300 + index,
    }


def _records(
    tmp_path: Path,
    root: Path,
) -> dict[str, object]:
    profile = {
        "requirements": {
            dimension: {
                "availability_rule": "INDEPENDENT_MINIMUM",
                "host_reserve_bytes": 10_000,
                "minimum_available_bytes": 30_000,
                "predicted_peak_bytes": 15_000,
                "safety_margin_bytes": 5_000,
            }
            for dimension in ("disk", "memory", "swap")
        },
        "stage": "FULL_PREFLIGHT",
    }
    profile["profile_sha256"] = CAL.canonical_sha256(profile)
    profile_identity = _identity(root / "installed-profile.json", profile)
    surface = CAL.build_execution_surface(
        stage="FULL_PREFLIGHT",
        command=[
            str(Path(sys.executable).resolve()),
            "scripts/preflight_gate.py",
            "--full",
        ],
        working_directory=str(ROOT.absolute()),
        test_inventory_count=7000,
        test_inventory_sha256="a" * 64,
        xdist_available=True,
        worker_mode="pytest-xdist-auto",
        worker_count=8,
        member_identities={
            "calibration_aggregator": _actual_identity(AGGREGATOR_PATH),
            "calibration_fd_loader": _actual_identity(FD_LOADER_PATH),
            "calibration_observer": _actual_identity(OBSERVER_PATH),
            "calibration_package_verifier_host": _actual_identity(
                PACKAGE_VERIFIER_PATH
            ),
            "calibration_protocol": _actual_identity(PROTOCOL_PATH),
            "calibration_runner": _actual_identity(PUBLISHER_PATH),
            "calibration_workload": _actual_identity(WORKLOAD_PATH),
            "python_interpreter": _actual_identity(
                Path(sys.executable).resolve()
            ),
            "runner": _source_identity(tmp_path, "runner.py"),
        },
        control_plane_identities={
            "code_assets": _source_identity(tmp_path, "code_assets.json"),
            "profile": profile_identity,
            "project_lock": _source_identity(tmp_path, "PROJECT_LOCK.md"),
        },
        portable_package=_portable_package(tmp_path),
        workload_fidelity_class="EXACT_FULL_PREFLIGHT",
        launch_admissible=True,
    )
    declaration = CAL.build_declaration(
        declaration_id="calibration-declaration-0001",
        cohort_id="calibration-cohort-0001",
        execution_surface=surface,
        harness_identity=_actual_identity(PUBLISHER_PATH),
        observer_identity=_actual_identity(OBSERVER_PATH),
        installed_profile_identity=profile_identity,
    )
    declaration_identity = _identity(root / "declaration.json", declaration)
    observers = [_observer(root, index) for index in range(1, 4)]
    samples: list[dict[str, object]] = []
    validations: list[dict[str, object]] = []
    accepted: list[
        tuple[
            dict[str, object],
            dict[str, object],
            dict[str, object],
            dict[str, object],
        ]
    ] = []
    for index, observer in enumerate(observers, start=1):
        sample = CAL.build_sample(
            declaration=declaration,
            declaration_identity=declaration_identity,
            sample_id=f"calibration-sample-{index:04d}",
            observer_result=observer,
            observer_result_identity=_identity(
                root / f"observer-results/{index:02d}.json",
                observer,
            ),
            workload_process_identity={
                "pid": 5000 + index,
                "starttime": 6000 + index,
            },
            workload_exit_code=0,
        )
        sample_identity = _identity(
            root / f"samples/{index:02d}.json",
            sample,
        )
        validation = CAL.build_validation(
            sample=sample,
            sample_identity=sample_identity,
            declaration=declaration,
            declaration_identity=declaration_identity,
            validator_identity=_source_identity(
                tmp_path,
                f"validator-{index}.py",
            ),
        )
        validation_identity = _identity(
            root / f"validations/{index:02d}.json",
            validation,
        )
        samples.append(sample)
        validations.append(validation)
        accepted.append(
            (sample, sample_identity, validation, validation_identity)
        )
    aggregate = CAL.aggregate_validations(
        declaration=declaration,
        declaration_identity=declaration_identity,
        accepted=accepted,
        aggregator_identity=_source_identity(tmp_path, "aggregator.py"),
    )
    aggregate_identity = _identity(root / "aggregate.json", aggregate)
    candidate = CAL.build_installed_profile_candidate(
        declaration=declaration,
        declaration_identity=declaration_identity,
        aggregate=aggregate,
        aggregate_identity=aggregate_identity,
        installed_profile=profile,
        candidate_builder_identity=_source_identity(
            tmp_path,
            "candidate-builder.py",
        ),
    )
    return {
        "aggregate": aggregate,
        "declaration": declaration,
        "installed_profile": profile,
        "observer_results": observers,
        "profile_candidate": candidate,
        "samples": samples,
        "validations": validations,
    }


def _accepted_records(
    root: Path,
    records: dict[str, object],
) -> tuple[
    dict[str, object],
    dict[str, object],
    list[
        tuple[
            dict[str, object],
            dict[str, object],
            dict[str, object],
            dict[str, object],
        ]
    ],
]:
    declaration = deepcopy(records["declaration"])
    declaration_identity = _identity(root / "declaration.json", declaration)
    accepted = []
    for index, (sample, validation) in enumerate(
        zip(records["samples"], records["validations"], strict=True),
        start=1,
    ):
        sample_copy = deepcopy(sample)
        validation_copy = deepcopy(validation)
        accepted.append(
            (
                sample_copy,
                _identity(root / f"samples/{index:02d}.json", sample_copy),
                validation_copy,
                _identity(
                    root / f"validations/{index:02d}.json",
                    validation_copy,
                ),
            )
        )
    return declaration, declaration_identity, accepted


def test_independent_validator_binds_declaration_and_sample_canonical_content(
    tmp_path: Path,
) -> None:
    root = (tmp_path / "validator-content-identity").absolute()
    records = _records(tmp_path, root)
    declaration, declaration_identity, accepted = _accepted_records(root, records)
    sample, sample_identity, _validation, _validation_identity = accepted[0]
    validator_identity = _actual_identity(REPLAY_A)

    result = PRIMARY_REPLAYER.build_independent_validation(
        sample=sample,
        sample_identity=sample_identity,
        declaration=declaration,
        declaration_identity=declaration_identity,
        validator_identity=validator_identity,
    )
    assert result["conclusion"] == "ACCEPTED_COMPARABLE_SAMPLE"

    stale_sample = deepcopy(sample)
    stale_sample["measurements"]["memory_peak_bytes"] += 1
    with pytest.raises(PRIMARY_REPLAYER.ReplayError) as sample_error:
        PRIMARY_REPLAYER.build_independent_validation(
            sample=stale_sample,
            sample_identity=sample_identity,
            declaration=declaration,
            declaration_identity=declaration_identity,
            validator_identity=validator_identity,
        )
    assert sample_error.value.code == "CALIBRATION_IDENTITY_MISMATCH"

    stale_declaration = deepcopy(declaration)
    stale_declaration["cohort_id"] = "stale-declaration-content"
    with pytest.raises(PRIMARY_REPLAYER.ReplayError) as declaration_error:
        PRIMARY_REPLAYER.build_independent_validation(
            sample=sample,
            sample_identity=sample_identity,
            declaration=stale_declaration,
            declaration_identity=declaration_identity,
            validator_identity=validator_identity,
        )
    assert declaration_error.value.code == "CALIBRATION_IDENTITY_MISMATCH"


def test_independent_aggregator_binds_all_canonical_content_identities(
    tmp_path: Path,
) -> None:
    root = (tmp_path / "aggregator-content-identity").absolute()
    records = _records(tmp_path, root)
    declaration, declaration_identity, accepted = _accepted_records(root, records)
    aggregator_identity = _actual_identity(AGGREGATOR_PATH)

    result = AGGREGATOR.aggregate_validations_independently(
        declaration=declaration,
        declaration_identity=declaration_identity,
        accepted=accepted,
        aggregator_identity=aggregator_identity,
    )
    assert result["status"] == "AGGREGATED_NO_SELF_AUTHORITY"

    stale_declaration = deepcopy(declaration)
    stale_declaration["cohort_id"] = "stale-declaration-content"
    with pytest.raises(AGGREGATOR.CalibrationAggregatorError) as declaration_error:
        AGGREGATOR.aggregate_validations_independently(
            declaration=stale_declaration,
            declaration_identity=declaration_identity,
            accepted=accepted,
            aggregator_identity=aggregator_identity,
        )
    assert (
        declaration_error.value.code
        == "CALIBRATION_AGGREGATE_CONTENT_IDENTITY_MISMATCH"
    )

    stale_sample_rows = deepcopy(accepted)
    stale_sample_rows[0][0]["measurements"]["memory_peak_bytes"] += 1
    with pytest.raises(AGGREGATOR.CalibrationAggregatorError) as sample_error:
        AGGREGATOR.aggregate_validations_independently(
            declaration=declaration,
            declaration_identity=declaration_identity,
            accepted=stale_sample_rows,
            aggregator_identity=aggregator_identity,
        )
    assert (
        sample_error.value.code
        == "CALIBRATION_AGGREGATE_CONTENT_IDENTITY_MISMATCH"
    )

    stale_validation_rows = deepcopy(accepted)
    stale_validation_rows[0][2]["sample_measurements"]["memory_peak_bytes"] += 1
    with pytest.raises(AGGREGATOR.CalibrationAggregatorError) as validation_error:
        AGGREGATOR.aggregate_validations_independently(
            declaration=declaration,
            declaration_identity=declaration_identity,
            accepted=stale_validation_rows,
            aggregator_identity=aggregator_identity,
        )
    assert (
        validation_error.value.code
        == "CALIBRATION_AGGREGATE_CONTENT_IDENTITY_MISMATCH"
    )


def _publish(tmp_path: Path, name: str = "cohort-a001") -> Path:
    root = (tmp_path / name).absolute()
    records = _records(tmp_path, root)
    PUBLISHER.publish_calibration_cohort(root, **records)
    return root


def _replay(
    script: Path,
    root: Path,
    output: Path,
    slot: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(script),
            "--root",
            str(root),
            "--output",
            str(output.absolute()),
            "--slot",
            slot,
            "--expected-source-sha256",
            hashlib.sha256(script.read_bytes()).hexdigest(),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_closed_root_accepts_two_heterogeneous_stdlib_replays(
    tmp_path: Path,
) -> None:
    root = _publish(tmp_path)
    first = _replay(REPLAY_A, root, tmp_path / "replay-a.json", "replay-a")
    second = _replay(REPLAY_B, root, tmp_path / "replay-b.json", "replay-b")
    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    first_record = json.loads(first.stdout)
    second_record = json.loads(second.stdout)
    assert first_record["profile_candidate_identity"] == second_record[
        "profile_candidate_identity"
    ]
    assert first_record["root_receipt_identity"] == second_record[
        "root_receipt_identity"
    ]
    assert first_record["replay_tool_identity"]["sha256"] != second_record[
        "replay_tool_identity"
    ]["sha256"]
    assert CAL.validate_dual_outside_replay(
        first_record,
        second_record,
    ) == (first_record, second_record)


def test_both_replayers_independently_reject_rehashed_full_command_drift(
    tmp_path: Path,
) -> None:
    records = _records(tmp_path, (tmp_path / "cohort-command-drift").absolute())
    declaration = records["declaration"]
    original = declaration["execution_surface"]
    forged = CAL.build_execution_surface(
        stage="FULL_PREFLIGHT",
        command=[
            original["command"][0],
            "scripts/not-the-full-preflight.py",
        ],
        working_directory=original["working_directory"],
        test_inventory_count=original["test_inventory"]["collection_count"],
        test_inventory_sha256=original["test_inventory"]["collection_sha256"],
        xdist_available=original["worker"]["xdist_available"],
        worker_mode=original["worker"]["mode"],
        worker_count=original["worker"]["count"],
        member_identities=deepcopy(original["execution_member_identities"]),
        control_plane_identities=deepcopy(original["control_plane_identities"]),
        portable_package=deepcopy(original["portable_package"]),
        workload_fidelity_class=original["workload_fidelity"]["class"],
        launch_admissible=True,
    )
    profile_identity = declaration["installed_profile_identity"]
    with pytest.raises(
        PRIMARY_REPLAYER.ReplayError,
        match="full execution command",
    ):
        PRIMARY_REPLAYER._execution_surface_digest(  # noqa: SLF001
            forged,
            stage="FULL_PREFLIGHT",
            profile_identity=profile_identity,
        )
    with pytest.raises(
        ALTERNATE_REPLAYER.AltReplayError,
        match="full command",
    ):
        ALTERNATE_REPLAYER._surface_digest(  # noqa: SLF001
            forged,
            stage="FULL_PREFLIGHT",
            profile_identity=profile_identity,
        )


def test_admission_replays_actual_closed_byte_graph_and_external_tool_pins(
    tmp_path: Path,
) -> None:
    root = _publish(tmp_path)
    primary_path = tmp_path / "outside-primary.json"
    alternate_path = tmp_path / "outside-alternate.json"
    primary_run = _replay(REPLAY_A, root, primary_path, "replay-a")
    alternate_run = _replay(REPLAY_B, root, alternate_path, "replay-b")
    assert primary_run.returncode == alternate_run.returncode == 0
    primary = json.loads(primary_path.read_bytes())
    alternate = json.loads(alternate_path.read_bytes())
    declaration = json.loads((root / "declaration.json").read_bytes())
    profile = json.loads((root / "installed-profile.json").read_bytes())
    aggregate = json.loads((root / "aggregate.json").read_bytes())
    candidate = json.loads((root / "profile-candidate.json").read_bytes())
    samples = [
        json.loads((root / f"samples/{index:02d}.json").read_bytes())
        for index in range(1, 4)
    ]
    bundle = CAL.build_calibration_authorization_bundle(
        declaration=declaration,
        installed_profile=profile,
        aggregate=aggregate,
        aggregate_identity=_actual_identity(root / "aggregate.json"),
        profile_candidate=candidate,
        profile_candidate_identity=_actual_identity(
            root / "profile-candidate.json"
        ),
        samples=samples,
        primary_replay=primary,
        primary_replay_receipt_identity=_actual_identity(primary_path),
        alternate_replay=alternate,
        alternate_replay_receipt_identity=_actual_identity(alternate_path),
    )
    bundle_path = tmp_path / "calibration-authorization-bundle.json"
    bundle_path.write_bytes(CAL.canonical_json_bytes(bundle))
    checked = ADMISSION.validate_calibration_authorization_bundle(
        bundle,
        bundle_identity=_actual_identity(bundle_path),
        stage="FULL_PREFLIGHT",
        expected_profile=profile,
        expected_calibration_tool_identities=_expected_tools(),
    )
    assert checked == bundle
    surface = bundle["execution_surface"]
    for identity, replacement in (
        (
            surface["control_plane_identities"]["code_assets"],
            b"candidate-control-byte-drift",
        ),
        (
            surface["execution_member_identities"]["runner"],
            b"candidate-execution-byte-drift",
        ),
    ):
        site_path = Path(identity["path"])
        original_site_bytes = site_path.read_bytes()
        site_path.write_bytes(replacement)
        with pytest.raises(
            ADMISSION.ResourceAdmissionError,
            match="CALIBRATION_EVIDENCE_IDENTITY_DRIFT",
        ):
            ADMISSION.validate_calibration_authorization_bundle(
                bundle,
                bundle_identity=_actual_identity(bundle_path),
                stage="FULL_PREFLIGHT",
                expected_profile=profile,
                expected_calibration_tool_identities=_expected_tools(),
            )
        site_path.write_bytes(original_site_bytes)
    forged_tools = _expected_tools()
    forged_tools["protocol"] = {
        **forged_tools["protocol"],
        "sha256": "0" * 64,
    }
    with pytest.raises(
        ADMISSION.ResourceAdmissionError,
        match="CALIBRATION_TOOL_IDENTITY_DRIFT",
    ):
        ADMISSION.validate_calibration_authorization_bundle(
            bundle,
            bundle_identity=_actual_identity(bundle_path),
            stage="FULL_PREFLIGHT",
            expected_profile=profile,
            expected_calibration_tool_identities=forged_tools,
        )

    profile_path = root / "installed-profile.json"
    profile_path.chmod(0o600)
    profile_path.write_bytes(CAL.canonical_json_bytes({**profile, "tampered": True}))
    profile_path.chmod(0o400)
    with pytest.raises(
        ADMISSION.ResourceAdmissionError,
        match="CALIBRATION_EVIDENCE_IDENTITY_DRIFT",
    ):
        ADMISSION.validate_calibration_authorization_bundle(
            bundle,
            bundle_identity=_actual_identity(bundle_path),
            stage="FULL_PREFLIGHT",
            expected_profile=profile,
            expected_calibration_tool_identities=_expected_tools(),
        )


def test_replay_output_is_no_overwrite(tmp_path: Path) -> None:
    root = _publish(tmp_path)
    output = tmp_path / "replay.json"
    assert _replay(REPLAY_A, root, output, "replay-a").returncode == 0
    repeated = _replay(REPLAY_A, root, output, "replay-a")
    assert repeated.returncode == 2
    assert json.loads(repeated.stdout)["status"] == "FAIL_CLOSED"


@pytest.mark.parametrize("node_kind", ["file", "directory", "symlink", "fifo"])
def test_both_replayers_reject_post_receipt_extra_member(
    tmp_path: Path,
    node_kind: str,
) -> None:
    root = _publish(tmp_path)
    late = root / "late"
    if node_kind == "file":
        late.write_bytes(b"pollution")
    elif node_kind == "directory":
        late.mkdir()
    elif node_kind == "symlink":
        late.symlink_to("/dev/null")
    else:
        os.mkfifo(late, 0o600)
    for index, script in enumerate((REPLAY_A, REPLAY_B), start=1):
        result = _replay(
            script,
            root,
            tmp_path / f"replay-extra-{index}.json",
            "replay-a" if index == 1 else "replay-b",
        )
        assert result.returncode == 2
        assert json.loads(result.stdout)["conclusion"] is None


def test_both_replayers_reject_semantic_measurement_drift(
    tmp_path: Path,
) -> None:
    root = _publish(tmp_path)
    sample_path = root / "samples/01.json"
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    sample["measurements"]["memory_peak_bytes"] += 1
    sample_path.chmod(0o600)
    sample_path.write_bytes(CAL.canonical_json_bytes(sample))
    sample_path.chmod(0o400)
    for index, script in enumerate((REPLAY_A, REPLAY_B), start=1):
        result = _replay(
            script,
            root,
            tmp_path / f"replay-drift-{index}.json",
            "replay-a" if index == 1 else "replay-b",
        )
        assert result.returncode == 2
        assert json.loads(result.stdout)["conclusion"] is None


def test_zero_authority_full_controller_accepts_only_exact_retained_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_bytes(b"{}\n")
    python_path = Path(sys.executable).resolve()
    preflight_path = ROOT / "scripts/preflight_gate.py"
    observer_path = RESEARCH / "ab16_resource_calibration_harness_v1.py"
    surface = CAL.build_execution_surface(
        stage="FULL_PREFLIGHT",
        command=[str(python_path), "scripts/preflight_gate.py", "--full"],
        working_directory=str(ROOT.absolute()),
        test_inventory_count=7000,
        test_inventory_sha256="d" * 64,
        xdist_available=True,
        worker_mode="pytest-xdist-auto",
        worker_count=8,
        member_identities={
            "calibration_observer": _actual_identity(observer_path),
            "calibration_protocol": _actual_identity(PROTOCOL_PATH),
            "calibration_runner": _actual_identity(PUBLISHER_PATH),
            "preflight_gate": _actual_identity(preflight_path),
            "python_interpreter": _actual_identity(python_path),
        },
        control_plane_identities={
            "code_assets": _actual_identity(
                ROOT / "data/repository_governance/code_assets.json"
            ),
            "profile": _actual_identity(profile_path),
            "project_lock": _actual_identity(ROOT / "PROJECT_LOCK.md"),
        },
        portable_package=_portable_package(tmp_path),
        workload_fidelity_class="EXACT_FULL_PREFLIGHT",
        launch_admissible=True,
    )
    declaration = CAL.build_declaration(
        declaration_id="zero-authority-controller-0001",
        cohort_id="zero-authority-cohort-0001",
        execution_surface=surface,
        harness_identity=_actual_identity(PUBLISHER_PATH),
        observer_identity=_actual_identity(observer_path),
        installed_profile_identity=_actual_identity(profile_path),
    )
    monkeypatch.setattr(
        PUBLISHER,
        "measure_full_execution_fingerprint",
        lambda **_kwargs: {
            "test_inventory": surface["test_inventory"],
            "worker": surface["worker"],
        },
    )
    workload = PUBLISHER._validated_full_workload(  # noqa: SLF001
        declaration,
        expected_calibration_tool_identities=_expected_tools(),
    )
    assert workload.command == [
        str(python_path),
        "scripts/preflight_gate.py",
        "--full",
    ]
    assert workload.working_directory == ROOT
    workload.close()
    monkeypatch.setattr(
        PUBLISHER,
        "measure_full_execution_fingerprint",
        lambda **_kwargs: {
            "test_inventory": {
                "collection_count": 6999,
                "collection_sha256": "e" * 64,
            },
            "worker": surface["worker"],
        },
    )
    with pytest.raises(
        PUBLISHER.CalibrationPublicationError,
        match="CALIBRATION_EXECUTION_FINGERPRINT_DRIFT",
    ):
        PUBLISHER._validated_full_workload(  # noqa: SLF001
            declaration,
            expected_calibration_tool_identities=_expected_tools(),
        )


def test_full_entrypoint_rejects_formal_stage_dispatch(
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_bytes(b"{}\n")
    surface = CAL.build_execution_surface(
        stage="FORMAL_ORGANIC_ARM",
        command=[
            str(Path(sys.executable).resolve()),
            "formal-calibration-missing",
        ],
        working_directory=str(ROOT.absolute()),
        test_inventory_count=0,
        test_inventory_sha256=hashlib.sha256(b"").hexdigest(),
        xdist_available=False,
        worker_mode="single-worker",
        worker_count=1,
        member_identities={
            "calibration_observer": _actual_identity(
                RESEARCH / "ab16_resource_calibration_harness_v1.py"
            ),
            "calibration_protocol": _actual_identity(PROTOCOL_PATH),
            "python_interpreter": _actual_identity(Path(sys.executable).resolve()),
            "calibration_runner": _actual_identity(PUBLISHER_PATH),
        },
        control_plane_identities={
            "code_assets": _actual_identity(
                ROOT / "data/repository_governance/code_assets.json"
            ),
            "profile": _actual_identity(profile_path),
            "project_lock": _actual_identity(ROOT / "PROJECT_LOCK.md"),
        },
        portable_package=_portable_package(tmp_path),
        workload_fidelity_class="FORMAL_DISPATCH_NEGATIVE",
        launch_admissible=False,
    )
    declaration = CAL.build_declaration(
        declaration_id="formal-calibration-blocked-0001",
        cohort_id="formal-calibration-cohort-0001",
        execution_surface=surface,
        harness_identity=_actual_identity(PUBLISHER_PATH),
        observer_identity=_actual_identity(
            RESEARCH / "ab16_resource_calibration_harness_v1.py"
        ),
        installed_profile_identity=_actual_identity(profile_path),
    )
    try:
        PUBLISHER._validated_full_workload(  # noqa: SLF001
            declaration,
            expected_calibration_tool_identities=_expected_tools(),
        )
    except PUBLISHER.CalibrationPublicationError as exc:
        assert exc.code == "CALIBRATION_EXECUTION_SURFACE_STAGE_MISMATCH"
    else:
        raise AssertionError("formal calibration unexpectedly obtained authority")
