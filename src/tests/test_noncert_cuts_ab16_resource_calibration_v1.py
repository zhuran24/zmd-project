from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from devtools.research_run_contract import (
    ExclusiveRunRoot,
    ResearchRunContractError,
)


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "docs/research/noncert_cuts_ab16_20260724"
    / "ab16_resource_calibration_v1.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "ab16_resource_calibration_v1_test",
        MODULE_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAL = _load()


def _identity(tmp_path: Path, name: str, seed: str) -> dict[str, object]:
    raw = seed.encode("ascii")
    return {
        "path": str((tmp_path / name).absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _portable_package(tmp_path: Path) -> dict[str, object]:
    return {
        "host_runtime_content_sha256": hashlib.sha256(
            b"host-runtime"
        ).hexdigest(),
        "layout": CAL.PORTABLE_PACKAGE_LAYOUT,
        "package_receipt_identity": _identity(
            tmp_path,
            "calibration-package/receipt.json",
            "portable-package-receipt",
        ),
        "package_schema_version": CAL.CALIBRATION_PACKAGE_SCHEMA,
        "source_sets_sha256": hashlib.sha256(b"source-sets").hexdigest(),
    }


def _surface(
    tmp_path: Path,
    *,
    stage: str = "FULL_PREFLIGHT",
    mode: str = "pytest-xdist-auto",
    xdist: bool = True,
    workers: int = 8,
) -> dict[str, object]:
    if stage == "FULL_PREFLIGHT":
        count = 7000
        inventory = "a" * 64
        command = [
            str((tmp_path / "python").absolute()),
            "scripts/preflight_gate.py",
            "--full",
        ]
    else:
        count = 0
        inventory = hashlib.sha256(b"").hexdigest()
        command = [
            str((tmp_path / "python").absolute()),
            "stage-harness",
            stage,
        ]
    return CAL.build_execution_surface(
        stage=stage,
        command=command,
        working_directory=str(tmp_path.absolute()),
        test_inventory_count=count,
        test_inventory_sha256=inventory,
        xdist_available=xdist,
        worker_mode=mode,
        worker_count=workers,
        member_identities={
            "python_interpreter": _identity(tmp_path, "python", "python"),
            "runner": _identity(tmp_path, "runner.py", "runner"),
        },
        control_plane_identities={
            "code_assets": _identity(
                tmp_path,
                "code_assets.json",
                "assets",
            ),
            "profile": _identity(tmp_path, "profile.json", "profile"),
            "project_lock": _identity(tmp_path, "PROJECT_LOCK.md", "lock"),
        },
        portable_package=_portable_package(tmp_path),
        workload_fidelity_class="EXACT_TEST_WORKLOAD",
        launch_admissible=True,
    )


def _declaration(
    tmp_path: Path,
    *,
    stage: str = "FULL_PREFLIGHT",
) -> tuple[dict[str, object], dict[str, object]]:
    surface = _surface(
        tmp_path,
        stage=stage,
        mode=(
            "pytest-xdist-auto"
            if stage == "FULL_PREFLIGHT"
            else "single-worker"
        ),
        xdist=stage == "FULL_PREFLIGHT",
        workers=8 if stage == "FULL_PREFLIGHT" else 1,
    )
    declaration = CAL.build_declaration(
        declaration_id=f"declaration-{stage.lower().replace('_', '-')}",
        cohort_id="candidate-cohort-0001",
        execution_surface=surface,
        harness_identity=_identity(tmp_path, "harness.py", "harness"),
        observer_identity=_identity(tmp_path, "observer.py", "observer"),
        installed_profile_identity=surface["control_plane_identities"]["profile"],
    )
    raw = CAL.canonical_json_bytes(declaration)
    return declaration, _identity(tmp_path, "declaration.json", raw.hex())


def _replace_profile_identity(
    surface: dict[str, object],
    profile_identity: dict[str, object],
) -> dict[str, object]:
    controls = deepcopy(surface["control_plane_identities"])
    controls["profile"] = profile_identity
    inventory = surface["test_inventory"]
    worker = surface["worker"]
    fidelity = surface["workload_fidelity"]
    return CAL.build_execution_surface(
        stage=surface["stage"],
        command=surface["command"],
        working_directory=surface["working_directory"],
        test_inventory_count=inventory["collection_count"],
        test_inventory_sha256=inventory["collection_sha256"],
        xdist_available=worker["xdist_available"],
        worker_mode=worker["mode"],
        worker_count=worker["count"],
        member_identities=surface["execution_member_identities"],
        control_plane_identities=controls,
        portable_package=surface["portable_package"],
        workload_fidelity_class=fidelity["class"],
        launch_admissible=fidelity["launch_admissible"],
    )


def _authorization_bundle_fixture(
    tmp_path: Path,
    stage: str,
) -> dict[str, object]:
    surface = _surface(
        tmp_path,
        stage=stage,
        mode=(
            "pytest-xdist-auto"
            if stage == "FULL_PREFLIGHT"
            else "single-worker"
        ),
        xdist=stage == "FULL_PREFLIGHT",
        workers=8 if stage == "FULL_PREFLIGHT" else 1,
    )
    return {
        "aggregate_identity": _identity(
            tmp_path,
            f"{stage}-aggregate.json",
            f"{stage}-aggregate",
        ),
        "authority_scope": CAL.AUTHORITY_SCOPE,
        "authorizations": dict(CAL.FALSE_AUTHORIZATIONS),
        "comparable_samples": [{}, {}, {}],
        "execution_surface": surface,
        "execution_surface_sha256": surface["execution_surface_sha256"],
        "outside_replays": {},
        "profile_candidate_binding": {},
        "profile_identity": _identity(
            tmp_path,
            f"{stage}-profile.json",
            f"{stage}-profile",
        ),
        "profile_internal_sha256": "f" * 64,
        "schema_version": CAL.AUTHORIZATION_BUNDLE_SCHEMA,
        "stage": stage,
        "status": "ACCEPTED",
    }


def _sample(
    tmp_path: Path,
    declaration: dict[str, object],
    declaration_identity: dict[str, object],
    index: int,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    observer_result = {
        "authority_scope": CAL.AUTHORITY_SCOPE,
        "authorizations": dict(CAL.FALSE_AUTHORIZATIONS),
        "cgroup": {
            "disappeared_after_peak_read": True,
            "identity": {
                "device": 1,
                "inode": 10_000 + index,
                "mode": 0o40700,
                "path": f"/user.slice/ab16-calibration-{index}.scope",
                "uid": 1000,
            },
            "peak_read_before_disappearance": True,
        },
        "disk": {
            "after_bytes": 1_005_000,
            "before_bytes": 1_000_000,
            "cgroup_io": {
                "rows_after": [{"device": "8:0", "wbytes": 10_000 + index}],
                "wbytes_after": 10_000 + index,
                "wbytes_before": 0,
                "wbytes_delta": 10_000 + index,
            },
            "growth_peak_bytes": 10_000 + index,
            "measurement_rule": (
                "MAX_RETAINED_TREE_POLLING_AND_CGROUP_IO_WBYTES"
            ),
            "peak_bytes": 1_010_000 + index,
            "polling_growth_peak_bytes": 10_000 + index,
            "target_identity": {
                "device": 2,
                "inode": 20_000 + index,
                "mode": 0o40700,
                "path": str((tmp_path / f"stage-root-{index}").absolute()),
                "uid": 1000,
            },
        },
        "cgroup_limits": {
            "memory.high": 30_000,
            "memory.max": 40_000,
            "memory.swap.max": 10_000,
        },
        "memory_peak_bytes": 10_000 + index,
        "observer_process_identity": {
            "pid": 3000 + index,
            "starttime": 4000 + index,
        },
        "sample_count": 3,
        "schema_version": CAL.OBSERVER_RESULT_SCHEMA,
        "status": "PEAKS_CAPTURED_BEFORE_CGROUP_DISAPPEARANCE",
        "swap_peak_bytes": 100 + index,
    }
    observer_raw = CAL.canonical_json_bytes(observer_result)
    sample = CAL.build_sample(
        declaration=declaration,
        declaration_identity=declaration_identity,
        sample_id=f"sample-{index:08d}",
        observer_result=observer_result,
        observer_result_identity=CAL.detached_identity(
            str((tmp_path / f"observer-{index}.json").absolute()),
            observer_raw,
        ),
        workload_process_identity={"pid": 1000 + index, "starttime": 2000 + index},
        workload_exit_code=0,
    )
    sample_identity = _identity(
        tmp_path,
        f"sample-{index}.json",
        CAL.canonical_sha256(sample),
    )
    validation = CAL.build_validation(
        sample=sample,
        sample_identity=sample_identity,
        declaration=declaration,
        declaration_identity=declaration_identity,
        validator_identity=_identity(
            tmp_path,
            f"validator-{index}.py",
            f"validator-{index}",
        ),
    )
    validation_identity = _identity(
        tmp_path,
        f"validation-{index}.json",
        CAL.canonical_sha256(validation),
    )
    return sample, sample_identity, validation, validation_identity


def test_execution_surface_binds_command_inventory_xdist_and_control_bytes(
    tmp_path: Path,
) -> None:
    surface = _surface(tmp_path)
    assert CAL.validate_execution_surface(surface) == surface

    for field, replacement in (
        ("command", ["python", "other.py"]),
        (
            "test_inventory",
            {"collection_count": 6999, "collection_sha256": "a" * 64},
        ),
        (
            "worker",
            {"count": 1, "mode": "pytest-serial", "xdist_available": True},
        ),
        (
            "portable_package",
            {
                **surface["portable_package"],
                "source_sets_sha256": "f" * 64,
            },
        ),
    ):
        forged = deepcopy(surface)
        forged[field] = replacement
        with pytest.raises(
            CAL.CalibrationContractError,
            match="CALIBRATION_FINGERPRINT_INVALID",
        ):
            CAL.validate_execution_surface(forged)


def test_serial_fallback_has_a_distinct_fingerprint(tmp_path: Path) -> None:
    parallel = _surface(tmp_path)
    serial = _surface(
        tmp_path,
        mode="pytest-serial",
        xdist=False,
        workers=1,
    )
    assert (
        parallel["execution_surface_sha256"]
        != serial["execution_surface_sha256"]
    )


def test_execution_surface_excludes_profile_self_reference_but_site_binds_control(
    tmp_path: Path,
) -> None:
    first = _surface(tmp_path)
    changed = _replace_profile_identity(
        first,
        _identity(tmp_path, "profile.json", "changed-profile-bytes"),
    )
    assert changed["execution_surface_sha256"] == first["execution_surface_sha256"]
    assert (
        changed["execution_site_receipt_sha256"]
        != first["execution_site_receipt_sha256"]
    )
    assert CAL.validate_execution_surface(changed) == changed


def test_execution_surface_content_digest_is_cross_site_stable(
    tmp_path: Path,
) -> None:
    first = _surface(tmp_path / "checkout-a")
    second = _surface(tmp_path / "checkout-b")
    assert first["execution_surface_sha256"] == second["execution_surface_sha256"]
    assert (
        first["execution_site_receipt_sha256"]
        != second["execution_site_receipt_sha256"]
    )


def test_xdist_mode_without_plugin_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(
        CAL.CalibrationContractError,
        match="xdist-auto mode was declared while xdist is unavailable",
    ):
        _surface(
            tmp_path,
            mode="pytest-xdist-auto",
            xdist=False,
            workers=8,
        )


def test_bundle_set_is_exact_three_stage_canonical_records_and_detached3(
    tmp_path: Path,
) -> None:
    bundles = {
        stage: _authorization_bundle_fixture(tmp_path, stage)
        for stage in CAL.STAGES
    }
    bundle_set = CAL.build_calibration_authorization_bundle_set(
        bundles=bundles,
        detached_paths={
            stage: str((tmp_path / f"{stage}.json").absolute())
            for stage in CAL.STAGES
        },
    )
    assert CAL.validate_calibration_authorization_bundle_set(bundle_set) == (
        bundle_set
    )
    assert set(bundle_set["resource_calibration_bundle_identities"]) == (
        CAL.STAGES
    )
    assert set(bundle_set["resource_calibration_authorization_bundles"]) == (
        CAL.STAGES
    )
    for stage in CAL.STAGES:
        wrapper = bundle_set["resource_calibration_authorization_bundles"][
            stage
        ]
        assert wrapper["record"] == bundles[stage]
        assert (
            wrapper["identity"]
            == bundle_set["resource_calibration_bundle_identities"][stage]
        )


def test_bundle_set_rejects_missing_stage_and_identity_record_divergence(
    tmp_path: Path,
) -> None:
    bundles = {
        stage: _authorization_bundle_fixture(tmp_path, stage)
        for stage in CAL.STAGES
    }
    paths = {
        stage: str((tmp_path / f"{stage}.json").absolute())
        for stage in CAL.STAGES
    }
    missing = dict(bundles)
    missing.pop("GATE_B_QUALIFICATION")
    with pytest.raises(
        CAL.CalibrationContractError,
        match="exact prospective three-stage set",
    ):
        CAL.build_calibration_authorization_bundle_set(
            bundles=missing,
            detached_paths=paths,
        )
    bundle_set = CAL.build_calibration_authorization_bundle_set(
        bundles=bundles,
        detached_paths=paths,
    )
    forged = deepcopy(bundle_set)
    forged["resource_calibration_bundle_identities"][
        "FORMAL_ORGANIC_ARM"
    ]["sha256"] = "0" * 64
    with pytest.raises(
        CAL.CalibrationContractError,
        match="identities differ",
    ):
        CAL.validate_calibration_authorization_bundle_set(forged)


def test_sample_requires_observer_peak_before_cgroup_disappearance(
    tmp_path: Path,
) -> None:
    declaration, declaration_identity = _declaration(tmp_path)
    sample, *_rest = _sample(
        tmp_path,
        declaration,
        declaration_identity,
        1,
    )
    forged = deepcopy(sample)
    forged["cgroup"]["peak_read_before_disappearance"] = False
    with pytest.raises(
        CAL.CalibrationContractError,
        match="did not read the peak",
    ):
        CAL.validate_sample(
            forged,
            declaration=declaration,
            declaration_identity=declaration_identity,
        )


def test_sample_rejects_execution_surface_drift(tmp_path: Path) -> None:
    declaration, declaration_identity = _declaration(tmp_path)
    sample, *_rest = _sample(
        tmp_path,
        declaration,
        declaration_identity,
        1,
    )
    sample["execution_surface_sha256"] = "f" * 64
    with pytest.raises(
        CAL.CalibrationContractError,
        match="not comparable",
    ):
        CAL.validate_sample(
            sample,
            declaration=declaration,
            declaration_identity=declaration_identity,
        )


def test_executing_harness_cannot_validate_its_own_sample(
    tmp_path: Path,
) -> None:
    declaration, declaration_identity = _declaration(tmp_path)
    sample, sample_identity, _validation, _identity_record = _sample(
        tmp_path,
        declaration,
        declaration_identity,
        1,
    )
    with pytest.raises(
        CAL.CalibrationContractError,
        match="cannot validate its own sample",
    ):
        CAL.build_validation(
            sample=sample,
            sample_identity=sample_identity,
            declaration=declaration,
            declaration_identity=declaration_identity,
            validator_identity=declaration["harness_identity"],
        )


def test_aggregate_requires_three_unique_comparable_samples(
    tmp_path: Path,
) -> None:
    declaration, declaration_identity = _declaration(tmp_path)
    rows = [
        _sample(tmp_path, declaration, declaration_identity, index)
        for index in range(1, 4)
    ]
    aggregate = CAL.aggregate_validations(
        declaration=declaration,
        declaration_identity=declaration_identity,
        accepted=rows,
        aggregator_identity=_identity(
            tmp_path,
            "aggregator.py",
            "aggregator",
        ),
    )
    assert aggregate["sample_count"] == 3
    assert aggregate["maxima"]["memory_peak_bytes"] == 10_003

    with pytest.raises(
        CAL.CalibrationContractError,
        match="expected 3 samples",
    ):
        CAL.aggregate_validations(
            declaration=declaration,
            declaration_identity=declaration_identity,
            accepted=rows[:2],
            aggregator_identity=_identity(
                tmp_path,
                "aggregator.py",
                "aggregator",
            ),
        )
    with pytest.raises(
        CAL.CalibrationContractError,
        match="was reused",
    ):
        CAL.aggregate_validations(
            declaration=declaration,
            declaration_identity=declaration_identity,
            accepted=[rows[0], rows[0], rows[2]],
            aggregator_identity=_identity(
                tmp_path,
                "aggregator.py",
                "aggregator",
            ),
        )


def test_installed_profile_candidate_cannot_retrofit_different_profile(
    tmp_path: Path,
) -> None:
    profile = {
        "requirements": {
            dimension: {
                "host_reserve_bytes": 20_000,
                "minimum_available_bytes": 50_000,
                "predicted_peak_bytes": 20_000,
                "safety_margin_bytes": 10_000,
            }
            for dimension in ("disk", "memory", "swap")
        },
        "stage": "FULL_PREFLIGHT",
        "version": 2,
    }
    profile_raw = CAL.canonical_json_bytes(profile)
    surface = _replace_profile_identity(
        _surface(tmp_path),
        CAL.detached_identity(
            str((tmp_path / "profile.json").absolute()),
            profile_raw,
        ),
    )
    declaration = CAL.build_declaration(
        declaration_id="declaration-profile-0001",
        cohort_id="candidate-cohort-0001",
        execution_surface=surface,
        harness_identity=_identity(tmp_path, "harness.py", "harness"),
        observer_identity=_identity(tmp_path, "observer.py", "observer"),
        installed_profile_identity=surface["control_plane_identities"]["profile"],
    )
    declaration_identity = _identity(
        tmp_path,
        "declaration.json",
        CAL.canonical_sha256(declaration),
    )
    rows = [
        _sample(tmp_path, declaration, declaration_identity, index)
        for index in range(1, 4)
    ]
    aggregate = CAL.aggregate_validations(
        declaration=declaration,
        declaration_identity=declaration_identity,
        accepted=rows,
        aggregator_identity=_identity(
            tmp_path,
            "aggregator.py",
            "aggregator",
        ),
    )
    aggregate_identity = _identity(
        tmp_path,
        "aggregate.json",
        CAL.canonical_sha256(aggregate),
    )
    candidate = CAL.build_installed_profile_candidate(
        declaration=declaration,
        declaration_identity=declaration_identity,
        aggregate=aggregate,
        aggregate_identity=aggregate_identity,
        installed_profile=profile,
        candidate_builder_identity=_identity(
            tmp_path,
            "candidate-builder.py",
            "candidate-builder",
        ),
    )
    assert candidate["status"] == "INSTALLED_PROFILE_CANDIDATE_ONLY"

    with pytest.raises(
        CAL.CalibrationContractError,
        match="content does not match",
    ):
        CAL.build_installed_profile_candidate(
            declaration=declaration,
            declaration_identity=declaration_identity,
            aggregate=aggregate,
            aggregate_identity=aggregate_identity,
            installed_profile={**profile, "version": 3},
            candidate_builder_identity=_identity(
                tmp_path,
                "candidate-builder.py",
                "candidate-builder",
            ),
        )


def test_profile_candidate_rejects_peak_above_preinstalled_allowance(
    tmp_path: Path,
) -> None:
    profile = {
        "requirements": {
            dimension: {
                "host_reserve_bytes": 50_000,
                "minimum_available_bytes": 50_001,
                "predicted_peak_bytes": 1,
                "safety_margin_bytes": 0,
            }
            for dimension in ("disk", "memory", "swap")
        },
        "stage": "FULL_PREFLIGHT",
    }
    profile_raw = CAL.canonical_json_bytes(profile)
    surface = _replace_profile_identity(
        _surface(tmp_path),
        CAL.detached_identity(
            str((tmp_path / "profile.json").absolute()),
            profile_raw,
        ),
    )
    declaration = CAL.build_declaration(
        declaration_id="declaration-undersized-0001",
        cohort_id="candidate-cohort-0001",
        execution_surface=surface,
        harness_identity=_identity(tmp_path, "harness.py", "harness"),
        observer_identity=_identity(tmp_path, "observer.py", "observer"),
        installed_profile_identity=surface["control_plane_identities"]["profile"],
    )
    declaration_identity = _identity(
        tmp_path,
        "declaration.json",
        CAL.canonical_sha256(declaration),
    )
    rows = [
        _sample(tmp_path, declaration, declaration_identity, index)
        for index in range(1, 4)
    ]
    aggregate = CAL.aggregate_validations(
        declaration=declaration,
        declaration_identity=declaration_identity,
        accepted=rows,
        aggregator_identity=_identity(
            tmp_path,
            "aggregator.py",
            "aggregator",
        ),
    )
    with pytest.raises(
        CAL.CalibrationContractError,
        match="CALIBRATION_PROFILE_UNDERSIZED",
    ):
        CAL.build_installed_profile_candidate(
            declaration=declaration,
            declaration_identity=declaration_identity,
            aggregate=aggregate,
            aggregate_identity=_identity(
                tmp_path,
                "aggregate.json",
                CAL.canonical_sha256(aggregate),
            ),
            installed_profile=profile,
            candidate_builder_identity=_identity(
                tmp_path,
                "candidate-builder.py",
                "candidate-builder",
            ),
        )


def test_dual_replay_requires_distinct_tools_and_identical_candidate(
    tmp_path: Path,
) -> None:
    candidate = {
        "aggregate_identity": _identity(tmp_path, "aggregate.json", "aggregate"),
        "authority_scope": CAL.AUTHORITY_SCOPE,
        "authorizations": dict(CAL.FALSE_AUTHORIZATIONS),
        "candidate_builder_identity": _identity(
            tmp_path,
            "builder.py",
            "builder",
        ),
        "coverage": {
            dimension: {
                "host_reserve_bytes": 20_000,
                "observed_peak_bytes": 10_000,
                "predicted_plus_safety_bytes": 30_000,
                "within_preinstalled_workload_allowance": True,
            }
            for dimension in ("disk", "memory", "swap")
        },
        "declaration_identity": _identity(
            tmp_path,
            "declaration.json",
            "declaration",
        ),
        "execution_surface_sha256": "a" * 64,
        "installed_profile_identity": _identity(
            tmp_path,
            "profile.json",
            "profile",
        ),
        "sample_count": 3,
        "schema_version": CAL.PROFILE_CANDIDATE_SCHEMA,
        "stage": "FULL_PREFLIGHT",
        "status": "INSTALLED_PROFILE_CANDIDATE_ONLY",
        "threshold_effect": {
            "may_change_sampled_profile": False,
            "may_lower_current_cohort_threshold": False,
            "profile_was_installed_before_sampling": True,
        },
    }
    candidate_identity = _identity(
        tmp_path,
        "candidate.json",
        "candidate",
    )
    first = CAL.build_outside_replay(
        profile_candidate=candidate,
        profile_candidate_identity=candidate_identity,
        replay_tool_identity=_identity(tmp_path, "replay-a.py", "replay-a"),
        root_receipt_identity=_identity(
            tmp_path,
            "receipt.json",
            "root-receipt",
        ),
        replay_slot="replay-a",
    )
    second = CAL.build_outside_replay(
        profile_candidate=candidate,
        profile_candidate_identity=candidate_identity,
        replay_tool_identity=_identity(tmp_path, "replay-b.py", "replay-b"),
        root_receipt_identity=_identity(
            tmp_path,
            "receipt.json",
            "root-receipt",
        ),
        replay_slot="replay-b",
    )
    CAL.validate_dual_outside_replay(first, second)
    second["replay_tool_identity"] = first["replay_tool_identity"]
    with pytest.raises(
        CAL.CalibrationContractError,
        match="same byte identity",
    ):
        CAL.validate_dual_outside_replay(first, second)


def test_no_overwrite_calibration_roots_and_cohort_evolution(
    tmp_path: Path,
) -> None:
    first = ExclusiveRunRoot.create(tmp_path / "calibration-a001")
    first.write_json("declaration.json", {"cohort": 1}, mode=0o400)
    with pytest.raises(
        ResearchRunContractError,
        match="NO_OVERWRITE_COLLISION",
    ):
        first.write_json("declaration.json", {"cohort": 2}, mode=0o400)
    with pytest.raises(
        ResearchRunContractError,
        match="NO_OVERWRITE_COLLISION",
    ):
        ExclusiveRunRoot.create(tmp_path / "calibration-a001")

    second = ExclusiveRunRoot.create(tmp_path / "calibration-a002")
    second.write_json("declaration.json", {"cohort": 2}, mode=0o400)
    assert (tmp_path / "calibration-a001/declaration.json").read_bytes() != (
        tmp_path / "calibration-a002/declaration.json"
    ).read_bytes()
