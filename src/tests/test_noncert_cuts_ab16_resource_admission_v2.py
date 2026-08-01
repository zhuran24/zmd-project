from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from docs.research.noncert_cuts_ab16_20260724 import (
    ab16_resource_budget_profile_builder_v1 as PROFILE_BUILDER,
)


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = (
    ROOT
    / "docs/research/noncert_cuts_ab16_20260724"
    / "ab16_resource_admission_v1.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_test_ab16_resource_admission_v2",
        MODULE_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RESOURCE = _load()


def _tool_pins() -> dict[str, dict[str, object]]:
    return {
        role: {"sha256": hashlib.sha256(role.encode()).hexdigest(), "size_bytes": 1}
        for role in RESOURCE.CALIBRATION_TOOL_ROLES
    }


def _locks() -> list[dict[str, object]]:
    return [
        {
            "device": 1,
            "inode": 100 + index,
            "path": path,
            "uid": 1000,
        }
        for index, path in enumerate(RESOURCE.LOCK_PATHS)
    ]


def _context(tmp_path: Path, *, kind: str) -> dict[str, object]:
    return {
        "authority_id": "a" * 64,
        "disk_path": str(tmp_path.absolute()),
        "kind": kind,
        "ordinal": 0,
        "scope_id": "b" * 64,
        "sequence": (
            0
            if kind == "FORMAL_INITIAL_POST_LOCK"
            else 2
            if kind == "GATE_B_QUALIFICATION_PUBLICATION"
            else 1
        ),
        "slot": "",
        "target": "prospective-resource-test",
    }


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


def _legacy_budget_profile_fixture(
    tmp_path: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    slots = [
        f"{family}-{direction}-{treatment}"
        for family in (
            "bundle",
            "power-hitting-set",
            "region-capacity",
            "shape-packing-hall",
        )
        for direction in ("ab", "ba")
        for treatment in ("control", "treatment")
    ]
    arm_allocations = {
        slot: {
            "closeout": 16 * 1024**2,
            "ledger": 32 * 1024**2,
            "metadata": 16 * 1024**2,
            "model": 128 * 1024**2,
            "normal": 768 * 1024**2,
            "publication": 64 * 1024**2,
        }
        for slot in slots
    }
    artifact_registry = RESOURCE._formal_arm_artifact_registry()  # noqa: SLF001
    cap_by_class = {
        "closeout": 8 * 1024**2,
        "ledger": 8 * 1024**2,
        "metadata": 8 * 1024**2,
        "model": 16 * 1024**2,
        "publication": 16 * 1024**2,
    }
    arm_artifact_caps = {
        slot: {
            label: {
                "artifact_class": artifact_class,
                "maximum_bytes": cap_by_class[artifact_class],
            }
            for label, artifact_class in artifact_registry.items()
        }
        for slot in slots
    }
    arm_append_channels = {
        slot: [
            {
                "artifact_class": "ledger",
                "channel": channel,
                "label": label,
                "maximum_bytes": arm_artifact_caps[slot][label][
                    "maximum_bytes"
                ],
                "parent_path": parent,
            }
            for channel, label, parent in sorted(
                (
                    (
                        f"arm-{slot}-compile-journal",
                        "compile attach journal segment",
                        f"prospective/arms/{slot}/ledger/compile-attach-journal",
                    ),
                    (
                        f"arm-{slot}-cut-ledger",
                        "cut ledger segment",
                        f"prospective/arms/{slot}/ledger/cut-ledger",
                    ),
                    (
                        f"arm-{slot}-runtime-cuts",
                        "runtime cut segment",
                        f"prospective/arms/{slot}/checkpoint/runtime-cuts",
                    ),
                )
            )
        ]
        for slot in slots
    }
    profile: dict[str, object] = {
        "authority": {
            "changes_certified_exact": False,
            "changes_cut_state": False,
            "changes_lower_bound": False,
            "changes_production": False,
            "changes_upper_bound": False,
            "research_only": True,
        },
        "bootstrap": {},
        "execution_surface_sha256": "c" * 64,
        "formal_root": {
            "append_channels": [
                {
                    "artifact_class": "ledger",
                    "channel": "ab16-baseline-rebuild-cuts",
                    "label": "AB16 baseline cut segment",
                    "maximum_bytes": 2 * RESOURCE.GIB,
                    "parent_path": (
                        "prospective/baseline/checkpoint/benders-cuts"
                    ),
                }
            ],
            "arm_append_channels": arm_append_channels,
            "arm_allocations": arm_allocations,
            "arm_artifact_caps": arm_artifact_caps,
            "artifact_maxima": [
                {
                    "artifact_class": "metadata",
                    "label": "formal-contract",
                    "maximum_bytes": RESOURCE.GIB,
                    "path": "formal-root-budget-contract.json",
                    "required_on_success": True,
                }
            ],
            "category_limits": {
                "closeout": RESOURCE.GIB + 16 * 16 * 1024**2,
                "ledger": 2 * RESOURCE.GIB + 16 * 32 * 1024**2,
                "metadata": RESOURCE.GIB + 16 * 16 * 1024**2,
                "model": 16 * 128 * 1024**2,
                "normal": 16 * 768 * 1024**2,
                "publication": 16 * 64 * 1024**2,
            },
            "fixed_directories": [
                {"mode_octal": "0700", "path": "."},
                {"mode_octal": "0700", "path": "closeout"},
                {"mode_octal": "0700", "path": "prospective"},
                {"mode_octal": "0700", "path": "prospective/baseline"},
                {
                    "mode_octal": "0700",
                    "path": "prospective/baseline/tmp",
                },
                {
                    "mode_octal": "0700",
                    "path": "prospective/baseline/checkpoint",
                },
                {
                    "mode_octal": "0700",
                    "path": (
                        "prospective/baseline/checkpoint/benders-cuts"
                    ),
                },
                *[
                    {"mode_octal": "0700", "path": path}
                    for slot in slots
                    for path in (
                        "prospective/arms",
                        f"prospective/arms/{slot}",
                        f"prospective/arms/{slot}/checkpoint",
                        f"prospective/arms/{slot}/checkpoint/runtime-cuts",
                        f"prospective/arms/{slot}/ledger",
                        f"prospective/arms/{slot}/ledger/compile-attach-journal",
                        f"prospective/arms/{slot}/ledger/cut-ledger",
                    )
                    if path != "prospective/arms"
                ],
                {"mode_octal": "0700", "path": "prospective/arms"},
            ],
            "fixed_overhead_category_limits": {
                "closeout": RESOURCE.GIB,
                "ledger": 2 * RESOURCE.GIB,
                "metadata": RESOURCE.GIB,
            },
            "fixed_purpose_reservations": [
                {
                    "artifact_class": "closeout",
                    "maximum_bytes": RESOURCE.GIB,
                    "parent_path": "closeout",
                    "purpose": "recovery-closeout",
                    "target_name": "formal-consumed-incomplete.json",
                }
            ],
            "root_relative_path": "formal-ab16/artifacts",
        },
        "launch_ready": True,
        "profile_id": "prospective-budget-profile-0001",
        "schema_version": RESOURCE.BUDGET_PROFILE_SCHEMA,
    }
    profile["profile_sha256"] = RESOURCE._canonical_sha256(profile)  # noqa: SLF001
    raw = _canonical(profile)
    identity = {
        "path": str((tmp_path / "budget-profile.json").absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }
    return profile, identity


def _rebind_profile(
    tmp_path: Path,
    profile: dict[str, object],
) -> dict[str, object]:
    profile["profile_sha256"] = PROFILE_BUILDER.digest_without(
        profile,
        "profile_sha256",
    )
    raw = _canonical(profile)
    return {
        "path": str((tmp_path / "budget-profile.json").absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _budget_profile(
    tmp_path: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    members = {
        PROFILE_BUILDER.BUILDER_SOURCE_RELATIVE_PATH: (
            ROOT
            / "docs/research/noncert_cuts_ab16_20260724"
            / "ab16_resource_budget_profile_builder_v1.py"
        ).stat().st_size,
        PROFILE_BUILDER.PROFILE_RELATIVE_PATH: (
            PROFILE_BUILDER.PROFILE_SELF_MAXIMUM_BYTES
        ),
        "PROJECT_LOCK.md": (ROOT / "PROJECT_LOCK.md").stat().st_size,
        "src/example.py": 17,
    }
    profile = PROFILE_BUILDER.build_profile(
        repository_root=ROOT,
        repository_members=members,
        execution_surface_sha256="c" * 64,
        profile_id="prospective-budget-profile-0001",
        launch_ready=True,
        launch_ready_acknowledgement=(
            PROFILE_BUILDER.LAUNCH_READY_ACKNOWLEDGEMENT
        ),
    )
    raw = _canonical(profile)
    return profile, {
        "path": str((tmp_path / "budget-profile.json").absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _record_identity(
    tmp_path: Path,
    name: str,
    value: object,
) -> dict[str, object]:
    raw = _canonical(value)
    return {
        "path": str((tmp_path / name).absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _calibration_bundle(
    tmp_path: Path,
    *,
    stage: str,
    profile: dict[str, object],
    full_worker_mode: str = "xdist",
) -> tuple[dict[str, object], dict[str, object]]:
    profile_identity = _record_identity(
        tmp_path,
        "installed-resource-profile.json",
        profile,
    )
    surface: dict[str, object] = {
        "command": (
            ["/usr/bin/python3", "scripts/preflight_gate.py", "--full"]
            if stage == RESOURCE.FULL_PREFLIGHT
            else ["/usr/bin/python3", "package-no-authority-calibration"]
        ),
        "control_plane_identities": {
            "code_assets": {
                "path": str((tmp_path / "code_assets.json").absolute()),
                "sha256": "1" * 64,
                "size_bytes": 1,
            },
            "profile": profile_identity,
            "project_lock": {
                "path": str((tmp_path / "PROJECT_LOCK.md").absolute()),
                "sha256": "2" * 64,
                "size_bytes": 1,
            },
        },
        "execution_member_identities": {
            "runner": {
                "path": str((tmp_path / "runner.py").absolute()),
                "sha256": "3" * 64,
                "size_bytes": 1,
            }
        },
        "schema_version": RESOURCE.CALIBRATION_EXECUTION_SURFACE_SCHEMA,
        "stage": stage,
        "test_inventory": (
            {
                "collection_count": 7000,
                "collection_sha256": "4" * 64,
            }
            if stage == RESOURCE.FULL_PREFLIGHT
            else {
                "collection_count": 0,
                "collection_sha256": hashlib.sha256(b"").hexdigest(),
            }
        ),
        "worker": (
            (
                {
                    "count": 8,
                    "mode": "pytest-xdist-auto",
                    "xdist_available": True,
                }
                if full_worker_mode == "xdist"
                else {
                    "count": 1,
                    "mode": "pytest-serial",
                    "xdist_available": False,
                }
            )
            if stage == RESOURCE.FULL_PREFLIGHT
            else {
                "count": 1,
                "mode": "single-worker",
                "xdist_available": False,
            }
        ),
        "working_directory": str(tmp_path.absolute()),
    }
    surface["execution_surface_sha256"] = hashlib.sha256(
        _canonical(surface)
    ).hexdigest()
    aggregate_identity = {
        "path": str((tmp_path / "aggregate.json").absolute()),
        "sha256": "5" * 64,
        "size_bytes": 100,
    }
    candidate_identity = {
        "path": str((tmp_path / "candidate.json").absolute()),
        "sha256": "6" * 64,
        "size_bytes": 100,
    }
    root_receipt_identity = {
        "path": str((tmp_path / "root-receipt.json").absolute()),
        "sha256": "7" * 64,
        "size_bytes": 100,
    }
    outside: dict[str, object] = {}
    for implementation, slot, digit in (
        ("primary", "replay-a", "8"),
        ("alternate", "replay-b", "9"),
    ):
        record = {
            "authority_scope": RESOURCE.AUTHORITY_SCOPE,
            "authorizations": dict(RESOURCE.PROSPECTIVE_FALSE_AUTHORIZATIONS),
            "conclusion": "REPLAY_ACCEPTED_PROFILE_CANDIDATE",
            "execution_surface_sha256": surface["execution_surface_sha256"],
            "profile_candidate_identity": candidate_identity,
            "replay_slot": slot,
            "replay_tool_identity": {
                "path": str((tmp_path / f"{implementation}.py").absolute()),
                "sha256": digit * 64,
                "size_bytes": 100,
            },
            "root_receipt_identity": root_receipt_identity,
            "schema_version": RESOURCE.CALIBRATION_OUTSIDE_REPLAY_SCHEMA,
            "stage": stage,
            "status": "PASS_NO_LAUNCH_AUTHORITY",
        }
        outside[implementation] = {
            "receipt_identity": _record_identity(
                tmp_path,
                f"{implementation}-replay.json",
                record,
            ),
            "record": record,
        }
    bundle = {
        "aggregate_identity": aggregate_identity,
        "authority_scope": RESOURCE.AUTHORITY_SCOPE,
        "authorizations": dict(RESOURCE.PROSPECTIVE_FALSE_AUTHORIZATIONS),
        "comparable_samples": [
            {
                "sample_id": f"sample-{index:08d}",
                "sample_identity": {
                    "path": str((tmp_path / f"sample-{index}.json").absolute()),
                    "sha256": f"{index:x}" * 64,
                    "size_bytes": 100,
                },
                "transient_cgroup": f"/user.slice/calibration-{index}.scope",
                "validation_identity": {
                    "path": str(
                        (tmp_path / f"validation-{index}.json").absolute()
                    ),
                    "sha256": f"{index + 3:x}" * 64,
                    "size_bytes": 100,
                },
            }
            for index in range(1, 4)
        ],
        "execution_surface": surface,
        "execution_surface_sha256": surface["execution_surface_sha256"],
        "outside_replays": outside,
        "profile_candidate_binding": {
            "aggregate_identity": aggregate_identity,
            "execution_surface_sha256": surface["execution_surface_sha256"],
            "identity": candidate_identity,
            "installed_profile_identity": profile_identity,
        },
        "profile_identity": profile_identity,
        "profile_internal_sha256": profile["profile_sha256"],
        "schema_version": RESOURCE.CALIBRATION_AUTHORIZATION_BUNDLE_SCHEMA,
        "stage": stage,
        "status": "ACCEPTED",
    }
    return bundle, _record_identity(
        tmp_path,
        "calibration-authorization-bundle.json",
        bundle,
    )


def _bundle_identity(
    tmp_path: Path,
    bundle: dict[str, object],
) -> dict[str, object]:
    return _record_identity(
        tmp_path,
        "calibration-authorization-bundle.json",
        bundle,
    )


def test_gate_b_profile_is_stage_specific_not_legacy_floor() -> None:
    profile = RESOURCE._validated_prospective_profile(  # noqa: SLF001
        RESOURCE.GATE_B_QUALIFICATION,
        enforced_budget_profile=None,
        enforced_budget_profile_identity=None,
    )
    requirements = profile["requirements"]
    for dimension in ("disk", "memory", "swap"):
        requirement = requirements[dimension]
        assert (
            requirement["minimum_available_bytes"]
            == requirement["predicted_peak_bytes"]
            + requirement["safety_margin_bytes"]
            + requirement["host_reserve_bytes"]
        )
        assert requirement["basis_class"] == (
            "BOUNDED_GATE_B_WORKLOAD_TEMPORARY"
            if dimension != "disk"
            else "BOUNDED_GATE_B_RETAINED_GROWTH_TEMPORARY"
        )
        assert "historical" not in requirement["basis_detail"].lower()
    assert len(
        {
            requirements[dimension]["minimum_available_bytes"]
            for dimension in ("disk", "memory", "swap")
        }
    ) == 3


def test_formal_disk_requirement_comes_from_single_aggregate_budget(
    tmp_path: Path,
) -> None:
    profile, identity = _budget_profile(tmp_path)
    requirement = RESOURCE.derive_formal_disk_requirement(
        enforced_budget_profile=profile,
        enforced_budget_profile_identity=identity,
    )
    formal_root = profile["formal_root"]
    assert isinstance(formal_root, dict)
    category_limits = formal_root["category_limits"]
    assert isinstance(category_limits, dict)
    expected_aggregate = sum(category_limits.values())
    assert requirement["aggregate_budget_bytes"] == expected_aggregate
    assert requirement["filesystem_uncertainty_bytes"] == (
        expected_aggregate + 9
    ) // 10
    assert requirement["minimum_available_bytes"] == (
        requirement["aggregate_budget_bytes"]
        + requirement["filesystem_uncertainty_bytes"]
        + 4 * RESOURCE.GIB
    )


@pytest.mark.parametrize("drift", ["scope", "parent"])
def test_formal_disk_requirement_rejects_campaign_release_domain_drift(
    tmp_path: Path,
    drift: str,
) -> None:
    profile, _identity = _budget_profile(tmp_path)
    reservations = profile["formal_root"]["fixed_purpose_reservations"]
    release = next(
        record
        for record in reservations
        if record["purpose"] == "success-dual-lock-release"
    )
    if drift == "scope":
        release["parent_scope"] = "formal-root"
    else:
        release["parent_path"] = "formal-ab16/not-final-release"
    identity = _rebind_profile(tmp_path, profile)
    with pytest.raises(
        RESOURCE.ResourceAdmissionError,
        match="FORMAL_BUDGET_PROFILE_REQUIRED",
    ):
        RESOURCE.derive_formal_disk_requirement(
            enforced_budget_profile=profile,
            enforced_budget_profile_identity=identity,
        )


def test_formal_high_ram_low_swap_is_valid_compositional_capacity(
    tmp_path: Path,
) -> None:
    profile, identity = _budget_profile(tmp_path)
    resource_profile = RESOURCE._validated_prospective_profile(  # noqa: SLF001
        RESOURCE.FORMAL_ORGANIC_ARM,
        enforced_budget_profile=profile,
        enforced_budget_profile_identity=identity,
    )
    headroom, feasibility = RESOURCE._prospective_arithmetic(  # noqa: SLF001
        stage=RESOURCE.FORMAL_ORGANIC_ARM,
        profile=resource_profile,
        disk_available=64 * RESOURCE.GIB,
        mem_available=64 * RESOURCE.GIB,
        swap_available=0,
        error_code="RESOURCE_HEADROOM_INSUFFICIENT",
    )
    assert headroom["swap_bytes_usable_for_combined_capacity"] == 0
    assert (
        feasibility["total_capacity_for_memory_max_bytes"]
        == 56 * RESOURCE.GIB
    )


def test_formal_insufficient_combined_capacity_fails_closed(
    tmp_path: Path,
) -> None:
    profile, identity = _budget_profile(tmp_path)
    resource_profile = RESOURCE._validated_prospective_profile(  # noqa: SLF001
        RESOURCE.FORMAL_ORGANIC_ARM,
        enforced_budget_profile=profile,
        enforced_budget_profile_identity=identity,
    )
    with pytest.raises(
        RESOURCE.ResourceAdmissionError,
        match="RESOURCE_HARD_CAP_FEASIBILITY_FAILED",
    ):
        RESOURCE._prospective_arithmetic(  # noqa: SLF001
            stage=RESOURCE.FORMAL_ORGANIC_ARM,
            profile=resource_profile,
            disk_available=64 * RESOURCE.GIB,
            mem_available=36 * RESOURCE.GIB,
            swap_available=0,
            error_code="RESOURCE_HEADROOM_INSUFFICIENT",
        )


@pytest.mark.parametrize("failure", ["missing", "blocked", "forged-identity"])
def test_formal_v2_requires_exact_launch_ready_budget_profile(
    tmp_path: Path,
    failure: str,
) -> None:
    profile, identity = _budget_profile(tmp_path)
    if failure == "missing":
        profile_arg = None
        identity_arg = None
    else:
        profile_arg = deepcopy(profile)
        identity_arg = deepcopy(identity)
        if failure == "blocked":
            profile_arg["launch_ready"] = False
        else:
            identity_arg["sha256"] = "f" * 64
    with pytest.raises(
        RESOURCE.ResourceAdmissionError,
        match="FORMAL_BUDGET_PROFILE_REQUIRED",
    ):
        RESOURCE._validated_prospective_profile(  # noqa: SLF001
            RESOURCE.FORMAL_ORGANIC_ARM,
            enforced_budget_profile=profile_arg,
            enforced_budget_profile_identity=identity_arg,
        )


def test_forged_budget_partition_fails_closed(tmp_path: Path) -> None:
    profile, _identity = _budget_profile(tmp_path)
    profile["formal_root"]["arm_allocations"][
        "bundle-ab-control"
    ]["model"] -= 1
    profile["profile_sha256"] = PROFILE_BUILDER.digest_without(
        profile,
        "profile_sha256",
    )
    raw = _canonical(profile)
    identity = {
        "path": str((tmp_path / "budget-profile.json").absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }
    with pytest.raises(
        RESOURCE.ResourceAdmissionError,
        match="do not partition",
    ):
        RESOURCE.derive_formal_disk_requirement(
            enforced_budget_profile=profile,
            enforced_budget_profile_identity=identity,
        )


@pytest.mark.parametrize(
    "drift",
    [
        "cap-label-omitted",
        "cap-class-drift",
        "cap-exceeds-allocation",
        "channel-omitted",
        "channel-order-drift",
        "channel-parent-drift",
        "channel-cap-drift",
    ],
)
def test_arm_writer_registry_caps_and_channels_fail_closed(
    tmp_path: Path,
    drift: str,
) -> None:
    profile, _identity = _budget_profile(tmp_path)
    formal = profile["formal_root"]
    slot = "bundle-ab-control"
    caps = formal["arm_artifact_caps"][slot]
    channels = formal["arm_append_channels"][slot]
    if drift == "cap-label-omitted":
        del caps["module-origin receipt"]
    elif drift == "cap-class-drift":
        caps["module-origin receipt"]["artifact_class"] = "publication"
    elif drift == "cap-exceeds-allocation":
        caps["module-origin receipt"]["maximum_bytes"] = (
            formal["arm_allocations"][slot]["metadata"] + 1
        )
    elif drift == "channel-omitted":
        channels.pop()
    elif drift == "channel-order-drift":
        channels[0], channels[1] = channels[1], channels[0]
    elif drift == "channel-parent-drift":
        channels[0]["parent_path"] = f"prospective/arms/{slot}/ledger"
    else:
        channels[0]["maximum_bytes"] += 1
    identity = _rebind_profile(tmp_path, profile)
    with pytest.raises(
        RESOURCE.ResourceAdmissionError,
        match="FORMAL_BUDGET_PROFILE_REQUIRED",
    ):
        RESOURCE.derive_formal_disk_requirement(
            enforced_budget_profile=profile,
            enforced_budget_profile_identity=identity,
        )


@pytest.mark.parametrize("drift", ["append-omitted", "channel-parent-unregistered"])
def test_budget_profile_requires_exact_writer_path_preregistration(
    tmp_path: Path,
    drift: str,
) -> None:
    profile, _identity = _budget_profile(tmp_path)
    formal = profile["formal_root"]
    if drift == "append-omitted":
        del formal["append_channels"]
    else:
        formal["fixed_directories"] = [
            item
            for item in formal["fixed_directories"]
            if item["path"]
            != "prospective/baseline/checkpoint/benders-cuts"
        ]
    identity = _rebind_profile(tmp_path, profile)
    with pytest.raises(
        RESOURCE.ResourceAdmissionError,
        match="FORMAL_BUDGET_PROFILE_REQUIRED",
    ):
        RESOURCE.derive_formal_disk_requirement(
            enforced_budget_profile=profile,
            enforced_budget_profile_identity=identity,
        )


def test_synthetic_mixed_replay_bundle_cannot_replace_actual_byte_graph(
    tmp_path: Path,
) -> None:
    profile = RESOURCE._validated_prospective_profile(  # noqa: SLF001
        RESOURCE.GATE_B_QUALIFICATION,
        enforced_budget_profile=None,
        enforced_budget_profile_identity=None,
    )
    bundle, _identity = _calibration_bundle(
        tmp_path,
        stage=RESOURCE.GATE_B_QUALIFICATION,
        profile=profile,
    )
    alternate = bundle["outside_replays"]["alternate"]
    alternate["record"]["profile_candidate_identity"] = {
        "path": str((tmp_path / "other-candidate.json").absolute()),
        "sha256": "e" * 64,
        "size_bytes": 100,
    }
    alternate["receipt_identity"] = _record_identity(
        tmp_path,
        "alternate-replay.json",
        alternate["record"],
    )
    with pytest.raises(
        RESOURCE.ResourceAdmissionError,
        match="CALIBRATION_EVIDENCE_OPEN_FAILED",
    ):
        RESOURCE.validate_calibration_authorization_bundle(
            bundle,
            bundle_identity=_bundle_identity(tmp_path, bundle),
            stage=RESOURCE.GATE_B_QUALIFICATION,
            expected_profile=profile,
            expected_calibration_tool_identities=_tool_pins(),
        )


def test_synthetic_reused_sample_bundle_cannot_replace_actual_byte_graph(
    tmp_path: Path,
) -> None:
    profile = RESOURCE._validated_prospective_profile(  # noqa: SLF001
        RESOURCE.GATE_B_QUALIFICATION,
        enforced_budget_profile=None,
        enforced_budget_profile_identity=None,
    )
    bundle, _identity = _calibration_bundle(
        tmp_path,
        stage=RESOURCE.GATE_B_QUALIFICATION,
        profile=profile,
    )
    bundle["comparable_samples"][1]["sample_identity"] = deepcopy(
        bundle["comparable_samples"][0]["sample_identity"]
    )
    with pytest.raises(
        RESOURCE.ResourceAdmissionError,
        match="CALIBRATION_EVIDENCE_OPEN_FAILED",
    ):
        RESOURCE.validate_calibration_authorization_bundle(
            bundle,
            bundle_identity=_bundle_identity(tmp_path, bundle),
            stage=RESOURCE.GATE_B_QUALIFICATION,
            expected_profile=profile,
            expected_calibration_tool_identities=_tool_pins(),
        )


def test_synthetic_serial_surface_cannot_bypass_actual_byte_graph(
    tmp_path: Path,
) -> None:
    profile = RESOURCE._validated_prospective_profile(  # noqa: SLF001
        RESOURCE.FULL_PREFLIGHT,
        enforced_budget_profile=None,
        enforced_budget_profile_identity=None,
    )
    bundle, identity = _calibration_bundle(
        tmp_path,
        stage=RESOURCE.FULL_PREFLIGHT,
        profile=profile,
        full_worker_mode="serial",
    )
    with pytest.raises(
        RESOURCE.ResourceAdmissionError,
        match="CALIBRATION_EVIDENCE_OPEN_FAILED",
    ):
        RESOURCE.validate_calibration_authorization_bundle(
            bundle,
            bundle_identity=identity,
            stage=RESOURCE.FULL_PREFLIGHT,
            expected_profile=profile,
            expected_calibration_tool_identities=_tool_pins(),
        )
