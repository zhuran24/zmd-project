from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[2]
AB16 = ROOT / "docs/research/noncert_cuts_ab16_20260724"
BUILDER_PATH = AB16 / "ab16_resource_budget_profile_builder_v1.py"
BOOTSTRAP_PATH = AB16 / "ab16_campaign_bootstrap_v2.py"
PROFILE_PATH = AB16 / "ab16_resource_budget_profile_phase2_blocked_v1.json"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = _load("_ab16_budget_profile_builder_tested", BUILDER_PATH)
BOOTSTRAP = _load("_ab16_budget_profile_bootstrap_tested", BOOTSTRAP_PATH)


def _small_members() -> dict[str, int]:
    return {
        BUILDER.BUILDER_SOURCE_RELATIVE_PATH: BUILDER_PATH.stat().st_size,
        BUILDER.PROFILE_RELATIVE_PATH: (
            BUILDER.PROFILE_SELF_MAXIMUM_BYTES
        ),
        "PROJECT_LOCK.md": (ROOT / "PROJECT_LOCK.md").stat().st_size,
        "src/example.py": 17,
    }


def _small_profile() -> dict[str, object]:
    return BUILDER.build_profile(
        repository_root=ROOT,
        repository_members=_small_members(),
        execution_surface_sha256="a" * 64,
        profile_id="ab16-focused-profile-builder-fixture-v1",
        launch_ready=False,
    )


def test_builder_reads_exact_runner_registry_without_importing_it() -> None:
    registries = BUILDER.fixed_source_registries(ROOT)
    assert registries["ab16_scripts"][
        "ab16_final_release_actor_v1"
    ] == "ab16_final_release_actor_v1.py"
    assert registries["scripts"]["ab16_final_release_actor_v1"] == (
        "ab16_final_release_actor_v1.py"
    )
    package_paths = {
        item["path"]
        for item in _small_profile()["bootstrap"]["artifact_maxima"]
    }
    assert {
        (
            "bootstrap-authority/package-source-staging/"
            "script.ab16_final_release_actor_v1.py"
        ),
        (
            "campaign-authority/package/payload/"
            "tool.ab16_final_release_actor_v1.py"
        ),
    } <= package_paths
    labels = registries["arm_labels"]
    assert labels == {
        "AB16 immediate stop": "closeout",
        "AB16 arm budget terminal": "closeout",
        "AB16 organic attempt artifact manifest": "publication",
        "AB16 organic attempt root replay": "closeout",
        "arm allocation unselected terminal": "closeout",
        "arm consumed incomplete": "closeout",
        "arm credibility gate": "publication",
        "arm launch environment": "metadata",
        "attach model evidence": "model",
        "attach solution-vector evidence": "publication",
        "compile attach journal segment": "ledger",
        "cut ledger segment": "ledger",
        "cut-free incumbent replay receipt": "publication",
        "independent arithmetic replay receipt": "publication",
        "independent resource terminal replay": "publication",
        "module-origin receipt": "metadata",
        "organic arm consumption": "closeout",
        "organic arm failure record": "closeout",
        "organic arm result": "publication",
        "organic arm selection": "metadata",
        "organic pre-run authority": "metadata",
        "organic pre-run candidate": "metadata",
        "preselection manager epoch": "metadata",
        "preselection manager transcript": "metadata",
        "raw incumbent export": "publication",
        "raw solution-vector export": "publication",
        "runtime cut segment": "ledger",
        "terminal classification": "publication",
    }
    assert len(labels) == 28


def test_built_profile_has_exact_authority_and_hash_closure() -> None:
    profile = _small_profile()
    assert profile["authority"] == BUILDER.FALSE_AUTHORITY
    assert profile["launch_ready"] is False
    assert profile["profile_sha256"] == BUILDER.digest_without(
        profile,
        "profile_sha256",
    )
    assert (
        "profile_sha256"
        not in {
            item["path"]
            for item in profile["bootstrap"]["artifact_maxima"]
        }
    )
    assert BOOTSTRAP.validate_resource_budget_profile(profile) == profile


def test_formal_profile_uses_one_root_aggregate_and_exact_arm_tables() -> None:
    profile = _small_profile()
    formal = profile["formal_root"]
    assert set(formal["arm_allocations"]) == set(BUILDER.ARM_SLOTS)
    assert set(formal["arm_artifact_caps"]) == set(BUILDER.ARM_SLOTS)
    assert set(formal["arm_append_channels"]) == set(
        BUILDER.ARM_SLOTS
    )
    reservations = {
        item["purpose"]: item
        for item in formal["fixed_purpose_reservations"]
    }
    assert reservations["formal-budget-terminal"]["maximum_bytes"] == 64 * 1024
    assert reservations["formal-manifest"]["maximum_bytes"] == 64 * 1024
    for purpose in (
        "failure-terminal-release",
        "formal-root-replay-alternate-receipt",
        "formal-root-replay-primary-receipt",
        "success-dual-lock-release",
    ):
        assert reservations[purpose]["maximum_bytes"] == 4 * BUILDER.MIB
        assert reservations[purpose]["parent_scope"] == "campaign-root"
        assert reservations[purpose]["parent_path"] == (
            BUILDER.OUTSIDE_FINAL_RELEASE_PARENT_PATH
        )
    assert all(
        reservation["parent_scope"] == "formal-root"
        for purpose, reservation in reservations.items()
        if purpose
        not in {
            "failure-terminal-release",
            "formal-root-replay-alternate-receipt",
            "formal-root-replay-primary-receipt",
            "success-dual-lock-release",
        }
    )
    for artifact_class in ("closeout", "metadata"):
        assert formal["fixed_overhead_category_limits"][
            artifact_class
        ] == sum(
            item["maximum_bytes"]
            for item in formal["artifact_maxima"]
            if item["artifact_class"] == artifact_class
        ) + sum(
            item["maximum_bytes"]
            for item in formal["fixed_purpose_reservations"]
            if item["artifact_class"] == artifact_class
        ) + sum(
            item["maximum_bytes"] * item["maximum_segments"]
            for item in formal["append_channels"]
            if item["artifact_class"] == artifact_class
        ) + BUILDER.FORMAL_FIXED_HEADROOM.get(artifact_class, 0)

    slot = BUILDER.ARM_SLOTS[0]
    allocation = formal["arm_allocations"][slot]
    caps = formal["arm_artifact_caps"][slot]
    assert allocation == BUILDER.ARM_AGGREGATE_ALLOCATION
    assert len(caps) == 28
    assert caps["organic arm consumption"] == {
        "artifact_class": "closeout",
        "branch": "success",
        "maximum_bytes": 8 * BUILDER.MIB,
        "maximum_publications": 1,
        "multiplicity_source": {
            "kind": "terminal-branch-fixed-path",
            "maximum_fixed_publications": 1,
            "terminal_branch": "success",
        },
        "path_contract": {
            "kind": "fixed",
            "root": "formal-root",
            "root_relative_path": (
                f"prospective/consumptions/{slot}.json"
            ),
        },
    }
    assert caps["organic arm selection"] == {
        "artifact_class": "metadata",
        "branch": "common",
        "maximum_bytes": 4 * BUILDER.MIB,
        "maximum_publications": 1,
        "multiplicity_source": {
            "kind": "single-fixed-path",
            "maximum_fixed_publications": 1,
        },
        "path_contract": {
            "kind": "fixed",
            "root": "formal-root",
            "root_relative_path": (
                f"prospective/arms/{slot}/selection.json"
            ),
        },
    }
    assert caps["arm consumed incomplete"] == {
        "artifact_class": "closeout",
        "branch": "failure",
        "maximum_bytes": 8 * BUILDER.MIB,
        "maximum_publications": 1,
        "multiplicity_source": {
            "kind": "terminal-branch-fixed-path",
            "maximum_fixed_publications": 1,
            "terminal_branch": "failure",
        },
        "path_contract": {
            "kind": "fixed",
            "root": "formal-root",
            "root_relative_path": (
                f"prospective/arms/{slot}/arm-consumed-incomplete.json"
            ),
        },
    }
    assert caps["AB16 immediate stop"] == {
        "artifact_class": "closeout",
        "branch": "failure",
        "maximum_bytes": 8 * BUILDER.MIB,
        "maximum_publications": 1,
        "multiplicity_source": {
            "kind": "terminal-branch-fixed-path",
            "maximum_fixed_publications": 1,
            "terminal_branch": "failure",
        },
        "path_contract": {
            "kind": "fixed",
            "root": "formal-root",
            "root_relative_path": "prospective/immediate-stop-a001.json",
        },
    }
    assert caps["independent arithmetic replay receipt"] == {
        "artifact_class": "publication",
        "branch": "success",
        "maximum_bytes": 4 * BUILDER.MIB,
        "maximum_publications": 1,
        "multiplicity_source": {
            "kind": "terminal-branch-fixed-path",
            "maximum_fixed_publications": 1,
            "terminal_branch": "success",
        },
        "path_contract": {
            "kind": "fixed",
            "root": "formal-root",
            "root_relative_path": (
                f"prospective/arms/{slot}/replays/independent-arithmetic.json"
            ),
        },
    }
    assert formal["arm_append_channels"][slot] == [
        {
            "artifact_class": "ledger",
            "channel": f"arm-{slot}-compile-journal",
            "label": "compile attach journal segment",
            "maximum_bytes": 256 * 1024,
            "maximum_segments": 221,
            "multiplicity_derivation": {
                "formula": (
                    "3 genesis/seal records + 3 records per attach hook + "
                    "at most one compiled-cut record per generated cut"
                ),
                "maximum_attach_hooks": 30,
                "maximum_generated_cuts": 128,
                "result_maximum_segments": 221,
            },
            "parent_path": (
                f"prospective/arms/{slot}/ledger/"
                "compile-attach-journal"
            ),
        },
        {
            "artifact_class": "ledger",
            "channel": f"arm-{slot}-cut-ledger",
            "label": "cut ledger segment",
            "maximum_bytes": 256 * 1024,
            "maximum_segments": 258,
            "multiplicity_derivation": {
                "formula": (
                    "2 genesis/seal records + at most one generated and one "
                    "terminal disposition record per generated cut"
                ),
                "maximum_attach_hooks": 30,
                "maximum_generated_cuts": 128,
                "result_maximum_segments": 258,
            },
            "parent_path": (
                f"prospective/arms/{slot}/ledger/cut-ledger"
            ),
        },
        {
            "artifact_class": "ledger",
            "channel": f"arm-{slot}-runtime-cuts",
            "label": "runtime cut segment",
            "maximum_bytes": 256 * 1024,
            "maximum_segments": 0,
            "multiplicity_derivation": {
                "formula": (
                    "certified_exact AB16 routes cut events through the cut "
                    "ledger; runtime-cut publication is forbidden"
                ),
                "maximum_attach_hooks": 30,
                "maximum_generated_cuts": 128,
                "result_maximum_segments": 0,
            },
            "parent_path": (
                f"prospective/arms/{slot}/checkpoint/runtime-cuts"
            ),
        },
    ]
    assert formal["arm_workload_contract"]["required_category_bytes"] == {
        "closeout": 32 * BUILDER.MIB,
        "ledger": 479 * 256 * 1024,
        "metadata": 28 * BUILDER.MIB,
        "model": 480 * BUILDER.MIB,
        "publication": 192 * BUILDER.MIB,
        "scratch": 0,
    }
    assert formal["arm_workload_contract"]["allocation_margin_bytes"] == {
        "closeout": 32 * BUILDER.MIB,
        "ledger": 128 * BUILDER.MIB - 479 * 256 * 1024,
        "metadata": 4 * BUILDER.MIB,
        "model": 0,
        "publication": 32 * BUILDER.MIB,
        "scratch": 0,
    }
    expected_root = dict(formal["fixed_overhead_category_limits"])
    for arm in formal["arm_allocations"].values():
        for artifact_class, maximum in arm.items():
            expected_root[artifact_class] = (
                expected_root.get(artifact_class, 0) + maximum
            )
    assert formal["category_limits"] == dict(
        sorted(expected_root.items())
    )


def test_formal_profile_preregisters_consumption_and_scratch_boundaries() -> None:
    profile = _small_profile()
    formal = profile["formal_root"]
    directories = {
        item["path"]: item["mode_octal"]
        for item in formal["fixed_directories"]
    }
    assert directories["prospective/consumptions"] == "0700"
    assert directories["budget/arm-terminals"] == "0700"
    assert directories["replays/arm-attempt-roots"] == "0700"
    for slot in BUILDER.ARM_SLOTS:
        assert directories[f"prospective/arms/{slot}/tmp"] == "0500"
        assert "scratch" not in formal["arm_allocations"][slot]
    assert formal["arm_workload_contract"]["scratch_contract"] == {
        "aggregate_allocation_bytes": 0,
        "known_retained_writer_count": 0,
        "tmp_directory_mode_octal": "0500",
        "write_attempt_result": "fail-closed",
    }


def test_profile_binds_attach_and_generated_cut_multiplicity() -> None:
    profile = _small_profile()
    formal = profile["formal_root"]
    workload = formal["arm_workload_contract"]
    assert workload["hard_limits"] == {
        "maximum_attach_hooks": {
            "basis": "formal runtime maximum Benders iterations",
            "exhaustion": "arm-consumed-incomplete",
            "value": 30,
        },
        "maximum_generated_cuts": {
            "basis": (
                "policy-defined bounded workload cap; next power of two "
                "above four generated cuts per maximum attach hook"
            ),
            "evidence_status": "unmeasured-temporary",
            "exhaustion": (
                "fail before the first generated-cut write beyond the cap; "
                "arm-consumed-incomplete"
            ),
            "sufficiency_claim": False,
            "value": 128,
        },
    }
    slot = BUILDER.ARM_SLOTS[0]
    model = formal["arm_artifact_caps"][slot][
        "attach model evidence"
    ]
    vector = formal["arm_artifact_caps"][slot][
        "attach solution-vector evidence"
    ]
    assert model["maximum_bytes"] == 8 * BUILDER.MIB
    assert model["maximum_publications"] == 60
    assert model["multiplicity_source"] == {
        "kind": "attach-hook",
        "maximum_attach_hooks": 30,
        "publications_per_hook": 2,
    }
    assert vector["maximum_bytes"] == 4 * BUILDER.MIB
    assert vector["maximum_publications"] == 30
    model_path = model["path_contract"]
    vector_path = vector["path_contract"]
    assert (model_path["index_minimum"], model_path["index_maximum"]) == (
        0,
        29,
    )
    assert (vector_path["index_minimum"], vector_path["index_maximum"]) == (
        0,
        29,
    )
    assert set(
        range(
            model_path["index_minimum"],
            model_path["index_maximum"] + 1,
        )
    ) == set(range(30))
    assert model_path["root_relative_path_template"].format(
        hook_id=0,
        phase="pre",
    ).endswith("/runtime/hook-0000-pre-model.pb")
    assert model_path["root_relative_path_template"].format(
        hook_id=29,
        phase="post",
    ).endswith("/runtime/hook-0029-post-model.pb")
    assert vector_path["root_relative_path_template"].format(
        hook_id=0,
    ).endswith("/runtime/hook-0000-solution-vector.json")
    assert vector_path["root_relative_path_template"].format(
        hook_id=29,
    ).endswith("/runtime/hook-0029-solution-vector.json")
    assert 30 not in range(
        vector_path["index_minimum"],
        vector_path["index_maximum"] + 1,
    )
    assert workload["per_file_cap_derivation"]["ledger_segment"] == {
        "basis": (
            "policy-defined retained-segment cap pending comparable "
            "calibration"
        ),
        "evidence_status": "unmeasured-temporary",
        "exhaustion": (
            "fail before an oversized append publication; "
            "arm-consumed-incomplete"
        ),
        "result_maximum_bytes": 256 * 1024,
        "sufficiency_claim": False,
    }
    assert workload["model_export_contract"]["rlimit_fsize"] == (
        "set to the current model cap for each export and restore before "
        "any later publication"
    )
    assert formal["append_channels"] == [
        {
            "artifact_class": "ledger",
            "channel": "ab16-baseline-rebuild-cuts",
            "label": "AB16 baseline cut segment",
            "maximum_bytes": BUILDER.MIB,
            "maximum_segments": 128,
            "multiplicity_derivation": {
                "basis": (
                    "temporary unmeasured conservative baseline append cap"
                ),
                "evidence_status": "unmeasured-temporary",
                "exhaustion": "formal-consumed-incomplete",
                "result_maximum_segments": 128,
            },
            "parent_path": (
                "prospective/baseline/checkpoint/benders-cuts"
            ),
        },
        {
            "artifact_class": "metadata",
            "channel": "budget-journal",
            "label": "AB16 formal budget journal segment",
            "maximum_bytes": 4096,
            "maximum_segments": 16_384,
            "multiplicity_derivation": {
                "basis": (
                    "profile-derived data-plane maxima plus explicit "
                    "temporary control-plane allowances"
                ),
                "bootstrap_and_formal_control_allowance": 2048,
                "derived_minimum_actions": 12_480,
                "evidence_status": "unmeasured-temporary",
                "exhaustion": (
                    "fail before the next broker-journal append; "
                    "formal-consumed-incomplete"
                ),
                "formal_arm_count": 16,
                "maximum_segment_bytes": 4096,
                "per_arm_append_maximum": 479,
                "per_arm_control_allowance": 64,
                "per_arm_fixed_publication_branch_maximum": 109,
                "retained_allocation_bytes": 64 * BUILDER.MIB,
                "result_maximum_segments": 16_384,
                "segment_cap_basis": (
                    "policy-defined canonical action-record cap pending "
                    "comparable calibration"
                ),
                "segment_count_rounding": (
                    "next power of two above derived minimum actions"
                ),
                "sufficiency_claim": False,
            },
            "parent_path": "channels/budget-journal",
        },
    ]
    assert (
        formal["fixed_overhead_category_limits"]["metadata"]
        >= 64 * BUILDER.MIB
    )


def test_profile_uses_branch_max_not_branch_sum() -> None:
    profile = _small_profile()
    formal = profile["formal_root"]
    slot = BUILDER.ARM_SLOTS[0]
    caps = formal["arm_artifact_caps"][slot]

    success_closeout = sum(
        item["maximum_bytes"] * item["maximum_publications"]
        for item in caps.values()
        if item["artifact_class"] == "closeout"
        and item["branch"] == "success"
    )
    failure_closeout = sum(
        item["maximum_bytes"] * item["maximum_publications"]
        for item in caps.values()
        if item["artifact_class"] == "closeout"
        and item["branch"] == "failure"
    )
    assert success_closeout == 24 * BUILDER.MIB
    assert failure_closeout == 32 * BUILDER.MIB
    assert formal["arm_workload_contract"]["branch_contract"] == {
        "common": {"mutually_exclusive_with": []},
        "failure": {"mutually_exclusive_with": ["success"]},
        "success": {"mutually_exclusive_with": ["failure"]},
    }
    reserve = formal["arm_workload_contract"][
        "independent_failure_closeout_reserve"
    ]
    assert reserve == {
        "artifact_class": "closeout",
        "label": "organic arm failure record",
        "maximum_bytes": 8 * BUILDER.MIB,
        "physical_accounting_branch": "common",
        "publication_branch": "failure",
        "release_policy": (
            "non-refundable; remains available after any partial or "
            "complete success-branch staging"
        ),
    }
    assert formal["arm_workload_contract"][
        "required_category_bytes"
    ]["closeout"] == 32 * BUILDER.MIB
    assert formal["arm_allocations"][slot]["closeout"] == (
        64 * BUILDER.MIB
    )


def test_failure_closeout_survives_nonrefundable_success_staging() -> None:
    formal = _small_profile()["formal_root"]
    slot = BUILDER.ARM_SLOTS[0]
    allocation = formal["arm_allocations"][slot]["closeout"]
    reserve = formal["arm_workload_contract"][
        "independent_failure_closeout_reserve"
    ]["maximum_bytes"]

    success_extent = 8 * BUILDER.MIB
    after_partial_success = allocation - 2 * success_extent
    after_complete_success_staging = allocation - 3 * success_extent
    assert after_partial_success >= reserve
    assert after_complete_success_staging >= reserve
    assert (
        allocation
        - formal["arm_workload_contract"]["required_category_bytes"][
            "closeout"
        ]
        == formal["arm_workload_contract"]["allocation_margin_bytes"][
            "closeout"
        ]
    )
    assert reserve == 8 * BUILDER.MIB


def test_historical_sizes_are_planning_input_not_runtime_dependency() -> None:
    planning = _small_profile()["formal_root"][
        "arm_workload_contract"
    ]["historical_size_planning_input"]
    assert planning["authority"] == (
        "planning-input-only-not-calibration-authority"
    )
    assert planning["runtime_dependency"] is False
    assert all(
        set(item) == {"label", "sha256", "size_bytes"}
        for item in planning["observations"]
    )
    assert not any(
        "/home/" in json.dumps(item, sort_keys=True)
        for item in planning["observations"]
    )


def _rehash(profile: dict[str, object]) -> None:
    profile["profile_sha256"] = BUILDER.digest_without(
        profile,
        "profile_sha256",
    )


def test_profile_rejects_arm_aggregate_underallocation() -> None:
    profile = copy.deepcopy(_small_profile())
    slot = BUILDER.ARM_SLOTS[0]
    profile["formal_root"]["arm_allocations"][slot]["model"] -= 1
    _rehash(profile)
    labels = BUILDER.fixed_source_registries(ROOT)["arm_labels"]
    with pytest.raises(
        BUILDER.ProfileBuildError,
        match="ARM_AGGREGATE_UNDERALLOCATED",
    ) as caught:
        BUILDER.validate_built_profile(profile, arm_labels=labels)
    assert caught.value.code == "ARM_AGGREGATE_UNDERALLOCATED"


def test_profile_rejects_legacy_cap_without_multiplicity() -> None:
    profile = copy.deepcopy(_small_profile())
    slot = BUILDER.ARM_SLOTS[0]
    profile["formal_root"]["arm_artifact_caps"][slot][
        "attach model evidence"
    ].pop("maximum_publications")
    _rehash(profile)
    labels = BUILDER.fixed_source_registries(ROOT)["arm_labels"]
    with pytest.raises(
        BUILDER.ProfileBuildError,
        match="ARM_CAP_CONTRACT_DRIFT",
    ) as caught:
        BUILDER.validate_built_profile(profile, arm_labels=labels)
    assert caught.value.code == "ARM_CAP_CONTRACT_DRIFT"


def test_profile_rejects_append_count_or_branch_drift() -> None:
    labels = BUILDER.fixed_source_registries(ROOT)["arm_labels"]
    slot = BUILDER.ARM_SLOTS[0]
    profile = copy.deepcopy(_small_profile())
    profile["formal_root"]["arm_append_channels"][slot][0][
        "maximum_segments"
    ] += 1
    _rehash(profile)
    with pytest.raises(
        BUILDER.ProfileBuildError,
        match="ARM_CHANNEL_CONTRACT_DRIFT",
    ):
        BUILDER.validate_built_profile(profile, arm_labels=labels)

    profile = copy.deepcopy(_small_profile())
    profile["formal_root"]["arm_artifact_caps"][slot][
        "organic arm failure record"
    ]["branch"] = "success"
    _rehash(profile)
    with pytest.raises(
        BUILDER.ProfileBuildError,
        match="ARM_CAP_CONTRACT_DRIFT",
    ):
        BUILDER.validate_built_profile(profile, arm_labels=labels)


def test_bootstrap_surface_enumerates_package_and_snapshot_writers() -> None:
    profile = _small_profile()
    paths = {
        item["path"]
        for item in profile["bootstrap"]["artifact_maxima"]
    }
    registries = BUILDER.fixed_source_registries(ROOT)
    for role in registries["scripts"]:
        assert (
            "bootstrap-authority/package-source-staging/"
            f"script.{role}.py"
        ) in paths
        package_role = (
            "campaign_authority_v4.py"
            if role == "campaign_authority_v4"
            else f"tool.{role}.py"
        )
        assert (
            f"campaign-authority/package/payload/{package_role}"
            in paths
        )
    for role in registries["system_roles"]:
        assert (
            f"campaign-authority/package/payload/system.{role}.bin"
            in paths
        )
    for role, package_role in registries["gate_inputs"].items():
        assert role
        assert (
            f"campaign-authority/package/payload/{package_role}"
            in paths
        )
    for relative in _small_members():
        assert (
            "campaign-authority/source-snapshot-a001/repository/"
            f"{relative}"
        ) in paths
    assert {
        "bootstrap-authority/bootstrap-budget-contract.json",
        "bootstrap-authority/bootstrap-budget-terminal.json",
        "bootstrap-authority/manager-epoch-capture.json",
        "bootstrap-authority/package-independent-replay.json",
        "campaign-authority/package/SHA256SUMS",
        "campaign-authority/package/package-manifest.json",
        "campaign-authority/source-snapshot-a001/"
        "materialization-receipt.json",
        "campaign-root.json",
        "gate1-v4/selection-a001.json",
    } <= paths
    reserve = profile["bootstrap"]["failure_closeout_reserve"]
    assert reserve["target_name"] == (
        "bootstrap-package-failure-closeout.json"
    )


def test_launch_ready_generation_requires_explicit_acknowledgement() -> None:
    with pytest.raises(
        BUILDER.ProfileBuildError,
        match="LAUNCH_READY_ACK_REQUIRED",
    ) as caught:
        BUILDER.build_profile(
            repository_root=ROOT,
            repository_members=_small_members(),
            execution_surface_sha256="b" * 64,
            profile_id="not-installed-launch-ready-fixture-v1",
            launch_ready=True,
        )
    assert caught.value.code == "LAUNCH_READY_ACK_REQUIRED"


def test_profile_output_is_canonical_no_overwrite(
    tmp_path: Path,
) -> None:
    output = tmp_path / "profile.json"
    raw = BUILDER.canonical_json(_small_profile())
    identity = BUILDER.write_no_overwrite(output, raw)
    assert output.read_bytes() == raw
    assert output.stat().st_mode & 0o777 == 0o444
    assert identity == {
        "path": str(output.absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }
    with pytest.raises(
        BUILDER.ProfileBuildError,
        match="OUTPUT_NO_OVERWRITE",
    ) as caught:
        BUILDER.write_no_overwrite(output, raw)
    assert caught.value.code == "OUTPUT_NO_OVERWRITE"


def test_profile_output_rejects_symlinked_parent(
    tmp_path: Path,
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real, target_is_directory=True)
    with pytest.raises(
        BUILDER.ProfileBuildError,
        match="OUTPUT_PARENT_OPEN_FAILED",
    ) as caught:
        BUILDER.write_no_overwrite(alias / "profile.json", b"{}\n")
    assert caught.value.code == "OUTPUT_PARENT_OPEN_FAILED"
    assert list(real.iterdir()) == []


def test_tracked_blocked_profile_is_mechanically_rebuilt() -> None:
    expected = BUILDER.canonical_json(
        BUILDER.build_phase2_blocked_profile(ROOT)
    )
    observed = PROFILE_PATH.read_bytes()
    assert observed == expected
    value = json.loads(observed)
    assert value["launch_ready"] is False
    assert value["profile_id"] == BUILDER.PROFILE_ID_PHASE2_BLOCKED
    assert BOOTSTRAP.validate_resource_budget_profile(value) == value
