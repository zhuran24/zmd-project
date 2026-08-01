from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
from types import ModuleType, SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
AB16 = ROOT / "docs/research/noncert_cuts_ab16_20260724"
V4 = ROOT / "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BOOTSTRAP = _load(
    "noncert_cuts_ab16_bootstrap_budget_tested",
    AB16 / "ab16_campaign_bootstrap_v2.py",
)
BUDGET = _load(
    "noncert_cuts_ab16_bootstrap_budget_authority_tested",
    AB16 / "ab16_budget_authority_v1.py",
)
BASE = _load(
    "noncert_cuts_ab16_bootstrap_campaign_authority_tested",
    V4 / "campaign_authority_v4.py",
)
PROFILE_BUILDER = _load(
    "noncert_cuts_ab16_resource_budget_profile_builder_test_fixture",
    AB16 / "ab16_resource_budget_profile_builder_v1.py",
)


def _profile(*, launch_ready: bool = True) -> dict[str, object]:
    arm_allocation = dict(
        PROFILE_BUILDER.ARM_AGGREGATE_ALLOCATION
    )
    arm_allocations = {
        slot: dict(arm_allocation)
        for slot in sorted(BOOTSTRAP._AB16_BUDGET_SLOTS)  # noqa: SLF001
    }
    arm_artifact_caps = {
        slot: {
            label: PROFILE_BUILDER._arm_cap_record(  # noqa: SLF001
                artifact_class=artifact_class,
                label=label,
                slot=slot,
            )
            for label, artifact_class in sorted(
                BOOTSTRAP._AB16_ARM_ARTIFACT_CLASS_BY_LABEL.items()  # noqa: SLF001
            )
        }
        for slot in sorted(BOOTSTRAP._AB16_BUDGET_SLOTS)  # noqa: SLF001
    }
    arm_append_channels = {
        slot: sorted(
            [
                    {
                        "artifact_class": "ledger",
                        "channel": f"arm-{slot}-{suffix}",
                        "label": label,
                        "maximum_bytes": 256 * 1024,
                        "maximum_segments": maximum_segments,
                        "multiplicity_derivation": {
                            "formula": derivation,
                            "maximum_attach_hooks": 30,
                            "maximum_generated_cuts": 128,
                            "result_maximum_segments": maximum_segments,
                        },
                        "parent_path": f"prospective/arms/{slot}/{parent}",
                    }
                    for (
                        suffix,
                        label,
                        parent,
                        maximum_segments,
                        derivation,
                    ) in BOOTSTRAP._AB16_ARM_APPEND_CHANNELS  # noqa: SLF001
            ],
            key=lambda item: item["channel"].encode("utf-8"),
        )
        for slot in sorted(BOOTSTRAP._AB16_BUDGET_SLOTS)  # noqa: SLF001
    }
    first_slot = sorted(BOOTSTRAP._AB16_BUDGET_SLOTS)[0]  # noqa: SLF001
    arm_required = PROFILE_BUILDER._arm_required_category_bytes(  # noqa: SLF001
        arm_artifact_caps[first_slot],
        arm_append_channels[first_slot],
    )
    reference_formal = PROFILE_BUILDER.build_profile(
        repository_root=ROOT,
        repository_members={
            PROFILE_BUILDER.BUILDER_SOURCE_RELATIVE_PATH: (
                Path(PROFILE_BUILDER.__file__).stat().st_size
            ),
            PROFILE_BUILDER.PROFILE_RELATIVE_PATH: (
                PROFILE_BUILDER.PROFILE_SELF_MAXIMUM_BYTES
            ),
            "PROJECT_LOCK.md": (ROOT / "PROJECT_LOCK.md").stat().st_size,
            "src/example.py": 17,
        },
        execution_surface_sha256="9" * 64,
        profile_id="bootstrap-parser-directory-fixture-v1",
        launch_ready=False,
    )["formal_root"]
    formal_directories = {
        item["path"] for item in reference_formal["fixed_directories"]
    }
    formal_directory_modes = {
        item["path"]: item["mode_octal"]
        for item in reference_formal["fixed_directories"]
    }
    value: dict[str, object] = {
        "authority": dict(BOOTSTRAP._BUDGET_FALSE_AUTHORITY),  # noqa: SLF001
        "bootstrap": {
            "artifact_maxima": [
                {
                    "artifact_class": "metadata",
                    "label": "bootstrap-contract",
                    "maximum_bytes": 4096,
                    "path": "bootstrap-authority/bootstrap-budget-contract.json",
                    "required_on_success": True,
                },
                {
                    "artifact_class": "normal",
                    "label": "selected-role",
                    "maximum_bytes": 64,
                    "path": "campaign-authority/package/payload/tool.py",
                    "required_on_success": True,
                },
            ],
            "category_limits": {
                "closeout": 2048,
                "metadata": 4096,
                "normal": 64,
            },
            "failure_closeout_reserve": {
                "artifact_class": "closeout",
                "maximum_bytes": 2048,
                "parent_path": "bootstrap-authority",
                "purpose": "bootstrap-failure-closeout",
                "target_name": "bootstrap-failure-closeout.json",
            },
            "fixed_directories": [
                {"mode_octal": "0700", "path": "."},
                {"mode_octal": "0700", "path": "bootstrap-authority"},
                {"mode_octal": "0700", "path": "campaign-authority"},
                {"mode_octal": "0700", "path": "campaign-authority/package"},
                {
                    "mode_octal": "0500",
                    "path": "campaign-authority/package/payload",
                },
                {"mode_octal": "0700", "path": "formal-ab16"},
                {"mode_octal": "0700", "path": "formal-ab16/control"},
            ],
            "root_relative_path": ".",
        },
        "execution_surface_sha256": "1" * 64,
        "formal_root": {
            "append_channels": [
                {
                    "artifact_class": "ledger",
                    "channel": "ab16-baseline-rebuild-cuts",
                    "label": "AB16 baseline cut segment",
                    "maximum_bytes": 1024 * 1024,
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
                        "retained_allocation_bytes": 67_108_864,
                        "result_maximum_segments": 16_384,
                        "segment_cap_basis": (
                            "policy-defined canonical action-record cap "
                            "pending comparable calibration"
                        ),
                        "segment_count_rounding": (
                            "next power of two above derived minimum actions"
                        ),
                        "sufficiency_claim": False,
                    },
                    "parent_path": "channels/budget-journal",
                },
            ],
            "arm_append_channels": arm_append_channels,
            "arm_allocations": arm_allocations,
            "arm_artifact_caps": arm_artifact_caps,
            "arm_workload_contract": {
                **PROFILE_BUILDER._arm_workload_contract(  # noqa: SLF001
                    required_category_bytes=arm_required,
                ),
                "allocation_margin_bytes": {
                    artifact_class: (
                        arm_allocation.get(artifact_class, 0) - amount
                    )
                    for artifact_class, amount in arm_required.items()
                },
                "required_category_bytes": dict(arm_required),
            },
            "artifact_maxima": [
                {
                    "artifact_class": "metadata",
                    "label": "formal-contract",
                    "maximum_bytes": 4096,
                    "path": "formal-root-budget-contract.json",
                    "required_on_success": True,
                }
            ],
            "category_limits": {
                "closeout": (
                    25_231_360 + 16 * arm_allocation["closeout"]
                ),
                "ledger": 128 * 1024 * 1024 + 16 * arm_allocation["ledger"],
                "metadata": (
                    67_186_688 + 16 * arm_allocation["metadata"]
                ),
                "model": 16 * arm_allocation["model"],
                "publication": 16 * arm_allocation["publication"],
            },
            "fixed_purpose_reservations": [
                {
                    "artifact_class": "closeout",
                    "maximum_bytes": 4 * 1024 * 1024,
                    "parent_path": "formal-ab16/final-release",
                    "parent_scope": "campaign-root",
                    "purpose": "failure-terminal-release",
                    "target_name": "failure-terminal-release.json",
                },
                {
                    "artifact_class": "closeout",
                    "maximum_bytes": 64 * 1024,
                    "parent_path": "formal-closure",
                    "parent_scope": "formal-root",
                    "purpose": "formal-budget-terminal",
                    "target_name": "budget-terminal.json",
                },
                {
                    "artifact_class": "metadata",
                    "maximum_bytes": 4096,
                    "parent_path": "locks",
                    "parent_scope": "formal-root",
                    "purpose": "formal-closure-consumption",
                    "target_name": "formal-closure-consumption.json",
                },
                {
                    "artifact_class": "metadata",
                    "maximum_bytes": 64 * 1024,
                    "parent_path": "formal-closure",
                    "parent_scope": "formal-root",
                    "purpose": "formal-manifest",
                    "target_name": "formal-manifest.json",
                },
                {
                    "artifact_class": "closeout",
                    "maximum_bytes": 4 * 1024 * 1024,
                    "parent_path": "formal-ab16/final-release",
                    "parent_scope": "campaign-root",
                    "purpose": "formal-root-replay-alternate-receipt",
                    "target_name": "formal-root-replay-alternate.json",
                },
                {
                    "artifact_class": "closeout",
                    "maximum_bytes": 4 * 1024 * 1024,
                    "parent_path": "formal-ab16/final-release",
                    "parent_scope": "campaign-root",
                    "purpose": "formal-root-replay-primary-receipt",
                    "target_name": "formal-root-replay-primary.json",
                },
                {
                    "artifact_class": "closeout",
                    "maximum_bytes": 4 * 1024 * 1024,
                    "parent_path": "closeout",
                    "parent_scope": "formal-root",
                    "purpose": "recovery-closeout",
                    "target_name": "formal-consumed-incomplete.json",
                },
                {
                    "artifact_class": "closeout",
                    "maximum_bytes": 4 * 1024 * 1024,
                    "parent_path": "formal-closure",
                    "parent_scope": "formal-root",
                    "purpose": "recovery-disarm-terminal",
                    "target_name": "recovery-disarm-terminal.json",
                },
                {
                    "artifact_class": "metadata",
                    "maximum_bytes": 4096,
                    "parent_path": "locks",
                    "parent_scope": "formal-root",
                    "purpose": "recovery-takeover-consumption",
                    "target_name": "recovery-takeover-consumption.json",
                },
                {
                    "artifact_class": "closeout",
                    "maximum_bytes": 4 * 1024 * 1024,
                    "parent_path": "formal-ab16/final-release",
                    "parent_scope": "campaign-root",
                    "purpose": "success-dual-lock-release",
                    "target_name": "dual-lock-release.json",
                },
            ],
            "fixed_directories": [
                {
                    "mode_octal": formal_directory_modes[path],
                    "path": path,
                }
                for path in sorted(formal_directories, key=lambda item: item.encode("utf-8"))
            ],
            "fixed_overhead_category_limits": {
                "closeout": 25_231_360,
                "ledger": 128 * 1024 * 1024,
                "metadata": 67_186_688,
            },
            "root_relative_path": "formal-ab16/artifacts",
        },
        "launch_ready": launch_ready,
        "profile_id": "synthetic-zero-authority-budget-v1",
        "profile_sha256": "",
        "schema_version": BOOTSTRAP.RESOURCE_BUDGET_PROFILE_SCHEMA,
    }
    value["profile_sha256"] = BOOTSTRAP._budget_digest_without(  # noqa: SLF001
        value,
        "profile_sha256",
    )
    return value


def _profile_with_bootstrap_terminal() -> dict[str, object]:
    value = _profile()
    value["bootstrap"]["artifact_maxima"].append(
        {
            "artifact_class": "metadata",
            "label": "bootstrap-budget-terminal",
            "maximum_bytes": 4096,
            "path": "bootstrap-authority/bootstrap-budget-terminal.json",
            "required_on_success": True,
        }
    )
    value["formal_root"]["artifact_maxima"].append(
        {
            "artifact_class": "metadata",
            "label": "formal-budget-handoff",
            "maximum_bytes": 4096,
            "path": "formal-root-budget-handoff.json",
            "required_on_success": True,
        }
    )
    value["formal_root"]["artifact_maxima"].sort(
        key=lambda item: item["label"]
    )
    value["bootstrap"]["artifact_maxima"].sort(
        key=lambda item: item["label"]
    )
    value["bootstrap"]["category_limits"]["metadata"] = 8192
    value["bootstrap"]["failure_closeout_reserve"]["target_name"] = (
        "bootstrap-package-failure-closeout.json"
    )
    value["formal_root"]["category_limits"]["metadata"] += 4096
    value["formal_root"]["fixed_overhead_category_limits"]["metadata"] += 4096
    value["profile_sha256"] = BOOTSTRAP._budget_digest_without(  # noqa: SLF001
        value,
        "profile_sha256",
    )
    return value


def _create_runtime(
    tmp_path: Path,
    *,
    profile: dict[str, object],
) -> tuple[Path, dict[str, object]]:
    profile_path = tmp_path / "resource-budget-profile.json"
    profile_path.write_bytes(BOOTSTRAP._budget_canonical_json(profile))  # noqa: SLF001
    profile_path.chmod(0o444)
    profile_identity = {
        "mode": 0o444,
        **BASE.detached_identity(BASE.snapshot_regular(profile_path)),
    }
    campaign = tmp_path / "campaign"
    contracts = BOOTSTRAP._planned_budget_contracts(  # noqa: SLF001
        campaign_dir=campaign,
        profile=profile,
        profile_identity=profile_identity,
    )
    budget_source = AB16 / "ab16_budget_authority_v1.py"
    runtime = BOOTSTRAP._create_bootstrap_budget_runtime(  # noqa: SLF001
        campaign_dir=campaign,
        base_authority=BASE,
        budget_module=BUDGET,
        budget_module_bytes=budget_source.read_bytes(),
        budget_module_source_identity=BASE.full_identity(
            BASE.snapshot_regular(budget_source)
        ),
        profile=profile,
        contracts=contracts,
    )
    return campaign, runtime


def _packaged_calibration_fixture(
    tmp_path: Path,
    *,
    mixed_stage: str | None = None,
) -> tuple[Path, dict[str, dict[str, object]]]:
    package = tmp_path / "package"
    payload = package / "payload"
    payload.mkdir(parents=True)
    identities: dict[str, dict[str, object]] = {}
    for index, stage in enumerate(
        BOOTSTRAP.RESOURCE_CALIBRATION_STAGES,
        start=1,
    ):
        declared_stage = (
            "FULL_PREFLIGHT"
            if mixed_stage == stage
            else stage
        )
        raw = BASE.canonical_json(
            {
                "fixture": f"{index}-{stage}",
                "stage": declared_stage,
            }
        )
        source = tmp_path / "sources" / f"{stage}.json"
        source.parent.mkdir(exist_ok=True)
        source.write_bytes(raw)
        source.chmod(0o444)
        role = BOOTSTRAP.RESOURCE_CALIBRATION_INPUT_ROLES[stage]
        packaged = payload / f"input.{role}.json"
        packaged.write_bytes(raw)
        packaged.chmod(0o444)
        identities[stage] = BASE.detached_identity(
            BASE.snapshot_regular(source)
        )
    payload.chmod(0o555)
    package.chmod(0o555)
    return package, identities


class _CalibrationAdmissionFixture:
    @staticmethod
    def _validated_prospective_profile(  # noqa: SLF001
        stage: str,
        *,
        enforced_budget_profile: object,
        enforced_budget_profile_identity: object,
    ) -> dict[str, object]:
        if stage == "FORMAL_ORGANIC_ARM":
            assert enforced_budget_profile is not None
            assert enforced_budget_profile_identity is not None
        else:
            assert enforced_budget_profile is None
            assert enforced_budget_profile_identity is None
        return {"stage": stage}

    @staticmethod
    def validate_calibration_authorization_bundle(
        value: object,
        *,
        bundle_identity: object,
        stage: str,
        expected_profile: object,
        expected_calibration_tool_identities: object,
    ) -> dict[str, object]:
        assert isinstance(bundle_identity, dict)
        assert expected_profile == {"stage": stage}
        assert expected_calibration_tool_identities == {
            role: {
                "sha256": hashlib.sha256(role.encode()).hexdigest(),
                "size_bytes": len(role),
            }
            for role in BOOTSTRAP.CALIBRATION_TOOL_PLANNED_ROLES
        }
        if (
            type(value) is not dict
            or value.get("stage") != stage
        ):
            raise ValueError("calibration stage drifted")
        return dict(value)


class _CalibrationAuthorizationFixture:
    @staticmethod
    def load_verified_role(role: str) -> object:
        assert role == "ab16-resource-admission-v1"
        return _CalibrationAdmissionFixture


def _validate_packaged_calibration_fixture(
    package: Path,
    identities: dict[str, dict[str, object]],
    *,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, dict[str, object]]:
    monkeypatch.setattr(BOOTSTRAP, "authority", BASE)
    root_fd = os.open(
        package,
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        return BOOTSTRAP._validate_packaged_resource_calibration_bundles(  # noqa: SLF001
            package_root_fd=root_fd,
            package_authorization=_CalibrationAuthorizationFixture(),
            expected_identities=identities,
            expected_calibration_tool_identities={
                role: {
                    "sha256": hashlib.sha256(role.encode()).hexdigest(),
                    "size_bytes": len(role),
                }
                for role in BOOTSTRAP.CALIBRATION_TOOL_PLANNED_ROLES
            },
            budget_profile=_profile(),
            budget_profile_identity={
                "mode": 0o444,
                "path": str(package.parent / "resource-budget-profile.json"),
                "sha256": "f" * 64,
                "size_bytes": 1,
            },
        )
    finally:
        os.close(root_fd)


def test_packaged_calibration_bundles_are_exact_three_stage_retained_fd_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, identities = _packaged_calibration_fixture(tmp_path)
    result = _validate_packaged_calibration_fixture(
        package,
        identities,
        monkeypatch=monkeypatch,
    )
    assert set(result) == set(BOOTSTRAP.RESOURCE_CALIBRATION_STAGES)
    assert {
        stage: envelope["identity"]
        for stage, envelope in result.items()
    } == identities


@pytest.mark.parametrize("mutation", ("missing", "tampered", "mixed-stage"))
def test_packaged_calibration_bundles_fail_closed_on_identity_or_stage_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    package, identities = _packaged_calibration_fixture(
        tmp_path,
        mixed_stage=(
            "GATE_B_QUALIFICATION"
            if mutation == "mixed-stage"
            else None
        ),
    )
    role = BOOTSTRAP.RESOURCE_CALIBRATION_INPUT_ROLES[
        "GATE_B_QUALIFICATION"
    ]
    target = package / "payload" / f"input.{role}.json"
    if mutation == "missing":
        target.parent.chmod(0o755)
        target.chmod(0o644)
        target.unlink()
        target.parent.chmod(0o555)
    elif mutation == "tampered":
        target.chmod(0o644)
        target.write_bytes(target.read_bytes() + b" ")
        target.chmod(0o444)
    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match=(
            "retained-FD open failed"
            if mutation == "missing"
            else (
                "packaged resource calibration bytes drifted"
                if mutation == "tampered"
                else "package calibration authorization failed closed"
            )
        ),
    ):
        _validate_packaged_calibration_fixture(
            package,
            identities,
            monkeypatch=monkeypatch,
        )


def test_resource_budget_profile_closes_two_accounts_and_sixteen_arms() -> None:
    profile = _profile()
    assert BOOTSTRAP.validate_resource_budget_profile(profile) == profile
    assert len(profile["formal_root"]["arm_allocations"]) == 16

    bad_bootstrap = copy.deepcopy(profile)
    bad_bootstrap["bootstrap"]["category_limits"]["normal"] -= 1
    bad_bootstrap["profile_sha256"] = BOOTSTRAP._budget_digest_without(  # noqa: SLF001
        bad_bootstrap,
        "profile_sha256",
    )
    with pytest.raises(BOOTSTRAP.BootstrapError, match="bootstrap budget arithmetic"):
        BOOTSTRAP.validate_resource_budget_profile(bad_bootstrap)

    bad_formal = copy.deepcopy(profile)
    bad_formal["formal_root"]["category_limits"]["publication"] -= 1
    bad_formal["profile_sha256"] = BOOTSTRAP._budget_digest_without(  # noqa: SLF001
        bad_formal,
        "profile_sha256",
    )
    with pytest.raises(BOOTSTRAP.BootstrapError, match="formal-root budget arithmetic"):
        BOOTSTRAP.validate_resource_budget_profile(bad_formal)


def test_resource_budget_profile_rejects_arm_artifact_cap_contract_drift() -> None:
    profile = _profile()
    slot = sorted(BOOTSTRAP._AB16_BUDGET_SLOTS)[0]  # noqa: SLF001
    profile["formal_root"]["arm_artifact_caps"][slot][
        "attach model evidence"
    ]["artifact_class"] = "publication"
    profile["profile_sha256"] = BOOTSTRAP._budget_digest_without(  # noqa: SLF001
        profile,
        "profile_sha256",
    )

    with pytest.raises(BOOTSTRAP.BootstrapError, match="artifact cap differs"):
        BOOTSTRAP.validate_resource_budget_profile(profile)


def test_resource_budget_profile_rejects_arm_append_channel_path_drift() -> None:
    profile = _profile()
    slot = sorted(BOOTSTRAP._AB16_BUDGET_SLOTS)[0]  # noqa: SLF001
    profile["formal_root"]["arm_append_channels"][slot][0]["parent_path"] = (
        f"arms/{slot}/ledger/compile-attach-journal"
    )
    profile["profile_sha256"] = BOOTSTRAP._budget_digest_without(  # noqa: SLF001
        profile,
        "profile_sha256",
    )

    with pytest.raises(BOOTSTRAP.BootstrapError, match="append-channel contract"):
        BOOTSTRAP.validate_resource_budget_profile(profile)


def test_resource_budget_profile_does_not_sum_per_file_caps_into_arm_budget() -> None:
    profile = _profile()
    slot = sorted(BOOTSTRAP._AB16_BUDGET_SLOTS)[0]  # noqa: SLF001
    publication_caps = [
        cap["maximum_bytes"]
        for cap in profile["formal_root"]["arm_artifact_caps"][slot].values()
        if cap["artifact_class"] == "publication"
    ]
    allocation = profile["formal_root"]["arm_allocations"][slot][
        "publication"
    ]
    required = profile["formal_root"]["arm_workload_contract"][
        "required_category_bytes"
    ]["publication"]
    assert sum(publication_caps) != allocation
    assert required <= allocation
    assert BOOTSTRAP.validate_resource_budget_profile(profile) == profile


def test_profile_category_caps_sum_all_same_class_fixed_artifacts() -> None:
    profile = _profile()
    duplicate_guard = copy.deepcopy(
        profile["bootstrap"]["artifact_maxima"][1]
    )
    duplicate_guard["label"] = "selected-role-second-channel"
    duplicate_guard["path"] = (
        "campaign-authority/package/payload/tool-second.py"
    )
    profile["bootstrap"]["artifact_maxima"].append(duplicate_guard)
    profile["bootstrap"]["artifact_maxima"].sort(key=lambda item: item["label"])
    profile["profile_sha256"] = BOOTSTRAP._budget_digest_without(  # noqa: SLF001
        profile,
        "profile_sha256",
    )

    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="bootstrap budget arithmetic",
    ):
        BOOTSTRAP.validate_resource_budget_profile(profile)


def test_bootstrap_budget_adapter_routes_only_profiled_no_replace_writes(
    tmp_path: Path,
) -> None:
    profile = _profile()
    bootstrap_profile = profile["bootstrap"]
    broker = BUDGET.FormalBudgetBroker.create(
        tmp_path / "campaign",
        category_limits=bootstrap_profile["category_limits"],
        owner_nonce="bootstrap-owner",
    )
    adapter = BOOTSTRAP._BootstrapBudgetAuthority(  # noqa: SLF001
        base=BASE,
        budget_module=BUDGET,
        broker=broker,
        profile=profile,
    )
    try:
        broker.allocate_arm(
            "bootstrap-authority",
            category_limits=bootstrap_profile["category_limits"],
        )
        adapter.mkdir_exclusive(broker.root)
        adapter.mkdir_exclusive(broker.root / "bootstrap-authority")
        adapter.mkdir_exclusive(broker.root / "campaign-authority")
        adapter.mkdir_exclusive(broker.root / "campaign-authority/package")
        adapter.mkdir_exclusive(
            broker.root / "campaign-authority/package/payload"
        )
        closeout = broker.reserve_retained_staging(
            "bootstrap-authority",
                maximum_bytes=2048,
                artifact_class="closeout",
                purpose="bootstrap-failure-closeout",
                arm_slot="bootstrap-authority",
        )
        try:
            adapter.write_exclusive(
                broker.root
                / "bootstrap-authority/bootstrap-budget-contract.json",
                b'{"contract":true}\n',
            )
            adapter.write_exclusive(
                broker.root / "campaign-authority/package/payload/tool.py",
                b"pass\n",
                mode=0o555,
            )
            adapter.assert_success_writes_complete()
            adapter.seal_directories()
            tool = broker.root / "campaign-authority/package/payload/tool.py"
            assert stat.S_IMODE(tool.stat().st_mode) == 0o555
            assert stat.S_IMODE(tool.parent.stat().st_mode) == 0o500
            with pytest.raises(
                BOOTSTRAP.BootstrapError,
                match="absent from fixed budget profile",
            ):
                adapter.write_exclusive(
                    broker.root / "ambient.json",
                    b"{}\n",
                )
        finally:
            closeout.close()
    finally:
        broker.close()


def test_launch_blocked_profile_parses_but_cannot_be_mislabeled() -> None:
    profile = _profile(launch_ready=False)
    assert BOOTSTRAP.validate_resource_budget_profile(profile)["launch_ready"] is False
    forged = copy.deepcopy(profile)
    forged["launch_ready"] = True
    with pytest.raises(BOOTSTRAP.BootstrapError, match="profile identity"):
        BOOTSTRAP.validate_resource_budget_profile(forged)


def test_bootstrap_runtime_paths_join_profile_and_preregistration_exactly(
    tmp_path: Path,
) -> None:
    campaign = tmp_path / "campaign"
    profile = _profile_with_bootstrap_terminal()
    preregistration = {
        "bootstrap_package_failure_closeout_path": str(
            campaign
            / "bootstrap-authority/bootstrap-package-failure-closeout.json"
        ),
        "formal_root_budget_handoff_path": str(
            campaign
            / "formal-ab16/artifacts/formal-root-budget-handoff.json"
        ),
    }
    assert BOOTSTRAP._bootstrap_runtime_budget_bindings(  # noqa: SLF001
        campaign_dir=campaign,
        profile=profile,
        path_preregistration=preregistration,
    ) == {
        "artifact_class": "metadata",
        "maximum_bytes": 4096,
        "relative_path": "formal-root-budget-handoff.json",
    }

    mismatched = copy.deepcopy(profile)
    mismatched["bootstrap"]["failure_closeout_reserve"]["target_name"] = (
        "bootstrap-failure-closeout.json"
    )
    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="failure reserve differs",
    ):
        BOOTSTRAP._bootstrap_runtime_budget_bindings(  # noqa: SLF001
            campaign_dir=campaign,
            profile=mismatched,
            path_preregistration=preregistration,
        )

    missing_handoff = copy.deepcopy(profile)
    missing_handoff["formal_root"]["artifact_maxima"] = [
        item
        for item in missing_handoff["formal_root"]["artifact_maxima"]
        if item["path"] != "formal-root-budget-handoff.json"
    ]
    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="lacks one exact artifact",
    ):
        BOOTSTRAP._bootstrap_runtime_budget_bindings(  # noqa: SLF001
            campaign_dir=campaign,
            profile=missing_handoff,
            path_preregistration=preregistration,
        )


def test_tracked_phase2_profile_is_canonical_and_launch_blocked(
    tmp_path: Path,
) -> None:
    source = (
        AB16 / "ab16_resource_budget_profile_phase2_blocked_v1.json"
    )
    raw = source.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "05490f0cb8e418e1b8217833286f3cc1dbfb6d19c5da082a2f5babcb7db3e20b"
    )
    value = json.loads(raw)
    assert BOOTSTRAP._budget_canonical_json(value) == raw  # noqa: SLF001
    assert BOOTSTRAP.validate_resource_budget_profile(value) == value
    assert value["launch_ready"] is False

    installed = tmp_path / "resource-budget-profile.json"
    installed.write_bytes(raw)
    installed.chmod(0o444)
    parsed, identity = BOOTSTRAP._resource_budget_profile(  # noqa: SLF001
        installed,
        require_launch_ready=False,
    )
    assert parsed == value
    assert identity["mode"] == 0o444
    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="not launch ready",
    ):
        BOOTSTRAP._resource_budget_profile(  # noqa: SLF001
            installed,
            require_launch_ready=True,
        )


def test_real_bootstrap_first_byte_escrow_precedes_package_writes(
    tmp_path: Path,
) -> None:
    profile = _profile()
    profile_path = tmp_path / "resource-budget-profile.json"
    profile_path.write_bytes(BOOTSTRAP._budget_canonical_json(profile))  # noqa: SLF001
    profile_path.chmod(0o444)
    profile_identity = {
        "mode": 0o444,
        **BASE.detached_identity(BASE.snapshot_regular(profile_path)),
    }
    campaign = tmp_path / "campaign"
    contracts = BOOTSTRAP._planned_budget_contracts(  # noqa: SLF001
        campaign_dir=campaign,
        profile=profile,
        profile_identity=profile_identity,
    )
    budget_source = AB16 / "ab16_budget_authority_v1.py"
    budget_raw = budget_source.read_bytes()
    runtime = BOOTSTRAP._create_bootstrap_budget_runtime(  # noqa: SLF001
        campaign_dir=campaign,
        base_authority=BASE,
        budget_module=BUDGET,
        budget_module_bytes=budget_raw,
        budget_module_source_identity=BASE.full_identity(
            BASE.snapshot_regular(budget_source)
        ),
        profile=profile,
        contracts=contracts,
    )
    try:
        bootstrap_broker = runtime["bootstrap_broker"]
        formal_broker = runtime["formal_broker"]
        assert (
            campaign
            / "bootstrap-authority/bootstrap-budget-contract.json"
        ).read_bytes() == BOOTSTRAP._budget_canonical_json(  # noqa: SLF001
            contracts["bootstrap_record"]
        )
        assert (
            campaign
            / "formal-ab16/artifacts/formal-root-budget-contract.json"
        ).read_bytes() == BOOTSTRAP._budget_canonical_json(  # noqa: SLF001
            contracts["formal_record"]
        )
        assert not (campaign / "campaign-authority").exists()
        assert bootstrap_broker.published_artifacts()[0]["path"] == (
            "bootstrap-authority/bootstrap-budget-contract.json"
        )
        assert formal_broker.published_artifacts()[0]["path"] == (
            "formal-root-budget-contract.json"
        )
        control = runtime["control_parent_capability"]
        assert control.record()["directory_path"] == "formal-ab16/control"
        assert control.record()["purpose"] == "formal-control-parent"
        assert stat.S_IMODE(os.fstat(control.fileno()).st_mode) == 0o700
        assert os.fstat(
            runtime["bootstrap_failure_reservation"].fileno()
        ).st_size == 2048
        assert {
            purpose: os.fstat(reservation.fileno()).st_size
            for purpose, reservation in runtime["formal_reservations"].items()
        } == {
            "formal-budget-terminal": 64 * 1024,
            "formal-closure-consumption": 4096,
            "failure-terminal-release": 4 * 1024 * 1024,
            "formal-manifest": 64 * 1024,
            "formal-root-replay-alternate-receipt": 4 * 1024 * 1024,
            "formal-root-replay-primary-receipt": 4 * 1024 * 1024,
            "recovery-closeout": 4 * 1024 * 1024,
            "recovery-disarm-terminal": 4 * 1024 * 1024,
            "recovery-takeover-consumption": 4096,
            "success-dual-lock-release": 4 * 1024 * 1024,
        }
        formal_remaining = {
            artifact_class: (
                formal_broker._limits[artifact_class]  # noqa: SLF001
                - formal_broker._debited[artifact_class]  # noqa: SLF001
            )
            for artifact_class in formal_broker._limits  # noqa: SLF001
        }
        assert formal_remaining["closeout"] == sum(
            allocation["closeout"]
            for allocation in profile["formal_root"][
                "arm_allocations"
            ].values()
        )
        journal_reserve = next(
            channel["maximum_bytes"] * channel["maximum_segments"]
            for channel in profile["formal_root"]["append_channels"]
            if channel["channel"] == "budget-journal"
        )
        assert formal_remaining["metadata"] == (
            journal_reserve
            + sum(
                allocation["metadata"]
                for allocation in profile["formal_root"][
                    "arm_allocations"
                ].values()
            )
        )
    finally:
        runtime["final_release_parent_capability"].close()
        runtime["control_parent_capability"].close()
        runtime["bootstrap_failure_reservation"].close()
        for reservation in runtime["formal_reservations"].values():
            reservation.close()
        runtime["formal_broker"].close()
        runtime["bootstrap_broker"].close()


def test_prepackage_budget_setup_failure_is_markerless_and_closes_fds(
    tmp_path: Path,
) -> None:
    before = len(os.listdir("/proc/self/fd"))
    profile = _profile_with_bootstrap_terminal()
    profile_path = tmp_path / "resource-budget-profile.json"
    profile_path.write_bytes(BOOTSTRAP._budget_canonical_json(profile))  # noqa: SLF001
    profile_path.chmod(0o444)
    profile_identity = {
        "mode": 0o444,
        **BASE.detached_identity(BASE.snapshot_regular(profile_path)),
    }
    campaign = tmp_path / "campaign"
    contracts = BOOTSTRAP._planned_budget_contracts(  # noqa: SLF001
        campaign_dir=campaign,
        profile=profile,
        profile_identity=profile_identity,
    )
    contracts["bootstrap_identity"]["path"] = str(
        campaign / "unprofiled-contract.json"
    )
    budget_source = AB16 / "ab16_budget_authority_v1.py"
    with pytest.raises(
        BOOTSTRAP.BootstrapError,
        match="absent from fixed budget profile",
    ):
        BOOTSTRAP._create_bootstrap_budget_runtime(  # noqa: SLF001
            campaign_dir=campaign,
            base_authority=BASE,
            budget_module=BUDGET,
            budget_module_bytes=budget_source.read_bytes(),
            budget_module_source_identity=BASE.full_identity(
                BASE.snapshot_regular(budget_source)
            ),
            profile=profile,
            contracts=contracts,
        )
    closeout = (
        campaign
        / "bootstrap-authority/bootstrap-package-failure-closeout.json"
    )
    record = json.loads(closeout.read_bytes())
    assert record["state"] == "markerless-incomplete"
    assert record["status"] == "FAIL_CLOSED"
    assert not (campaign / "campaign-authority").exists()
    assert len(os.listdir("/proc/self/fd")) == before


def test_bootstrap_executes_package_verifier_only_from_retained_root_fd() -> None:
    tree = ast.parse(
        (AB16 / "ab16_campaign_bootstrap_v2.py").read_text(
            encoding="utf-8"
        )
    )
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "bootstrap_campaign"
    )
    calls = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
    ]
    retained_open = next(
        node
        for node in calls
        if isinstance(node.func, ast.Name)
        and node.func.id == "_open_directory_fd"
    )
    verifier = next(
        node
        for node in calls
        if isinstance(node.func, ast.Name)
        and node.func.id
        == "_verify_and_publish_package_independent_replay"
    )
    verifier_keywords = {
        keyword.arg: keyword.value
        for keyword in verifier.keywords
    }
    retained_argument = verifier_keywords["retained_package_fd"]
    assert isinstance(retained_argument, ast.Name)
    assert retained_argument.id == "retained_package_fd"
    assert retained_open.lineno < verifier.lineno


def test_persistent_transfer_is_consumed_only_after_spawn_returns() -> None:
    tree = ast.parse(
        (AB16 / "ab16_campaign_bootstrap_v2.py").read_text(
            encoding="utf-8"
        )
    )
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_bootstrap_persistent_budget_runtime"
    )
    spawn_assignment = next(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "process"
            for target in node.targets
        )
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "spawn"
    )
    mark_consumed = next(
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "mark_consumed"
    )
    assert spawn_assignment.lineno < mark_consumed.lineno


@pytest.mark.parametrize(
    "post_spawn_failure",
    (None, "connect", "attach"),
)
def test_post_verifier_bootstrap_handoff_retains_one_owner_until_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    post_spawn_failure: str | None,
) -> None:
    before_fds = len(os.listdir("/proc/self/fd"))
    profile = _profile_with_bootstrap_terminal()
    campaign, budget_runtime = _create_runtime(tmp_path, profile=profile)
    budget_profile_identity = {
        "path": str(tmp_path / "resource-budget-profile.json"),
        "sha256": "0" * 64,
        "size_bytes": 19,
    }
    calibration_identities = {
        stage: {
            "path": str(tmp_path / f"calibration-{index}.json"),
            "sha256": str(index) * 64,
            "size_bytes": index,
        }
        for index, stage in enumerate(
            BOOTSTRAP.RESOURCE_CALIBRATION_STAGES,
            start=1,
        )
    }
    calibration_authorizations = {
        stage: {
            "identity": dict(identity),
            "record": {
                "schema_version": "fixture",
                "stage": stage,
            },
        }
        for stage, identity in calibration_identities.items()
    }
    formal_contract_path = (
        campaign
        / "formal-ab16/artifacts/formal-root-budget-contract.json"
    )
    formal_contract_identity = BASE.detached_identity(
        BASE.snapshot_regular(formal_contract_path)
    )
    failure_path = (
        campaign
        / "bootstrap-authority/bootstrap-package-failure-closeout.json"
    )
    handoff_path = (
        campaign
        / "formal-ab16/artifacts/formal-root-budget-handoff.json"
    )
    replay_result = {
        "schema": BOOTSTRAP.PACKAGE_INDEPENDENT_REPLAY_SCHEMA,
        "status": "PASS",
    }
    replay_raw = BOOTSTRAP._budget_canonical_json(replay_result)  # noqa: SLF001
    replay_path = tmp_path / "package-independent-replay.json"
    replay_path.write_bytes(replay_raw)
    replay_path.chmod(0o444)
    replay_fd = os.open(replay_path, os.O_RDONLY | os.O_CLOEXEC)
    replay_stat = os.fstat(replay_fd)
    replay_authorization = BOOTSTRAP.VerifiedPackageIndependentReplay(
        result=replay_result,
        identity={
            "path": str(replay_path),
            "sha256": hashlib.sha256(replay_raw).hexdigest(),
            "size_bytes": len(replay_raw),
        },
        descriptor=replay_fd,
        signature=BOOTSTRAP._stat_signature(replay_stat),  # noqa: SLF001
        raw=replay_raw,
    )
    recovery_result = {
        "actor": {
            "pid": os.getpid(),
            "pid_starttime": BOOTSTRAP._proc_starttime(os.getpid()),  # noqa: SLF001
            "uid": os.getuid(),
        },
        "broker_actor": {"pid": 9, "pid_starttime": "9", "uid": os.getuid()},
        "control_owner": "persistent-budget-broker",
        "pidfd_method": "fixture",
        "prepared_recovery_identity": {
            "sha256": "2" * 64,
            "size_bytes": 1,
        },
        "role": "ab16-recovery-closeout-v1",
        "role_source_identity": {
            "sha256": "3" * 64,
            "size_bytes": 1,
        },
        "schema_version": "noncert-cuts-ab16-recovery-owner-observation-v2",
        "state": "BROKER_RETAINED_CONTROL",
    }
    formal_owner_actor = {
        "pid": os.getpid(),
        "starttime": BOOTSTRAP._proc_starttime(os.getpid()),  # noqa: SLF001
        "uid": os.getuid(),
    }
    formal_owner_credential = "7" * 64
    formal_owner_peer = {
        "pid": formal_owner_actor["pid"],
        "pid_starttime": formal_owner_actor["starttime"],
        "uid": formal_owner_actor["uid"],
    }
    formal_owner_grant = {
        "credential_sha256": hashlib.sha256(
            formal_owner_credential.encode("ascii")
        ).hexdigest(),
        "expected_peer": formal_owner_peer,
        "role": "formal-launch-owner",
    }
    formal_owner_confirmation = {
        "credential_sha256": formal_owner_grant["credential_sha256"],
        "expected_peer": formal_owner_peer,
        "role": "formal-launch-owner",
        "state": "EXACT_OWNER_SESSION_LIVE",
    }

    class FakeAdmin:
        def __init__(self) -> None:
            self.requests: list[tuple[str, dict[str, object]]] = []
            self.close_count = 0
            self.close_session_count = 0

        def request(
            self,
            action: str,
            payload: dict[str, object],
            **_kwargs: object,
        ) -> SimpleNamespace:
            self.requests.append((action, dict(payload)))
            if action == "PREPARE_RECOVERY":
                return SimpleNamespace(record={"result": recovery_result})
            if action == "PUBLISH_BOOTSTRAP_HANDOFF":
                raw = BOOTSTRAP._budget_canonical_json(payload)  # noqa: SLF001
                return SimpleNamespace(
                    record={
                        "result": {
                            "handoff_identity": {
                                "path": str(handoff_path),
                                "sha256": hashlib.sha256(raw).hexdigest(),
                                "size_bytes": len(raw),
                            },
                            "handoff_message_identity": {
                                "sha256": hashlib.sha256(raw).hexdigest(),
                                "size_bytes": len(raw),
                            },
                        }
                    }
                )
            if action == "START_FORMAL_LAUNCH_OWNER":
                assert payload == {
                    "session_id": "formal-owner-session-a001"
                }
                return SimpleNamespace(
                    record={
                        "result": {
                            "broker_actor": {
                                "schema_version": (
                                    "noncert-cuts-ab16-budget-broker-actor-v1"
                                ),
                                **recovery_result["broker_actor"],
                            },
                            "broker_endpoint_identity": {
                                "path": str(tmp_path / "broker.sock")
                            },
                            "broker_nonce": "4" * 64,
                            "context_state": "AWAITING_DELAYED_CONTEXT",
                            "credential": formal_owner_credential,
                            "grant": formal_owner_grant,
                            "owner_actor": formal_owner_actor,
                            "owner_pidfd_method": "fixture",
                            "owner_role_source_identity": {
                                "sha256": "8" * 64,
                                "size_bytes": 1,
                            },
                            "ready": {"state": "READY"},
                            "registration_confirmation": (
                                formal_owner_confirmation
                            ),
                            "schema_version": (
                                "noncert-cuts-ab16-formal-launch-owner-"
                                "broker-handoff-v1"
                            ),
                            "state": "PREREGISTERED_LIVE_OWNER",
                            "transport_only": True,
                        }
                    }
                )
            assert action == "STATUS"
            return SimpleNamespace(
                record={
                    "result": {
                        "contract": {},
                        "root_closure": {},
                    }
                }
            )

        def close_session(self) -> None:
            self.close_session_count += 1

        def close(self) -> None:
            assert self.close_count == 0
            self.close_count += 1

    class FakeOwned:
        def __init__(
            self,
            descriptors: tuple[int, ...],
            *,
            path: Path | None = None,
        ) -> None:
            self.descriptors = descriptors
            self.path = path
            self.close_count = 0

        def close(self) -> None:
            assert self.close_count == 0
            self.close_count += 1
            for descriptor in self.descriptors:
                os.close(descriptor)

    class FakeAuthorization:
        def __init__(self) -> None:
            self.close_count = 0

        def close(self) -> None:
            assert self.close_count == 0
            self.close_count += 1

    adopted_objects: list[FakeOwned] = []
    inherited_structural_fds: tuple[int, ...] = ()
    duplicated_structural_fds: tuple[int, ...] = ()
    adopted_record: dict[str, object] = {}

    class FakeProcess:
        actor = dict(recovery_result["broker_actor"])
        endpoint_identity = {"path": str(tmp_path / "broker.sock")}
        nonce = "4" * 64
        pidfd_method = "fixture"
        selected_fd_transport = {"schema_version": "fixture"}

        def __init__(self) -> None:
            self.admin = FakeAdmin()
            self.close_count = 0
            self.terminate_unattached_count = 0

        def connect_bootstrap_admin(self) -> FakeAdmin:
            if post_spawn_failure == "connect":
                raise RuntimeError("injected bootstrap-admin connect failure")
            return self.admin

        def _release_owned(self) -> None:
            for owned in adopted_objects:
                owned.close()
            role_authorization.close()
            native_authorization.close()

        def close(self) -> None:
            assert self.close_count == 0
            assert self.terminate_unattached_count == 0
            self.close_count += 1
            self._release_owned()

        def terminate_unattached(self) -> None:
            assert self.terminate_unattached_count == 0
            assert self.close_count == 0
            self.terminate_unattached_count += 1
            self._release_owned()

    process = FakeProcess()
    spawn_keywords: dict[str, object] = {}

    class FakeBrokerModule:
        @staticmethod
        def adopt_bootstrap_structural_handoff(
            structural_handoff: dict[str, object],
            inherited_descriptors: tuple[int, ...],
            *,
            expected_owner_nonce: str,
        ) -> dict[str, object]:
            nonlocal inherited_structural_fds
            nonlocal duplicated_structural_fds
            assert structural_handoff["fd_count"] == 19
            assert len(inherited_descriptors) == 19
            assert len(set(inherited_descriptors)) == 19
            assert structural_handoff["to_owner_nonce_sha256"] == (
                hashlib.sha256(
                    expected_owner_nonce.encode("ascii")
                ).hexdigest()
            )
            inherited_structural_fds = tuple(inherited_descriptors)
            duplicated_structural_fds = tuple(
                os.dup(descriptor)
                for descriptor in inherited_structural_fds
            )
            cursor = 0
            account = FakeOwned((duplicated_structural_fds[cursor],))
            cursor += 1
            reservations: dict[str, FakeOwned] = {}
            reservation_handoffs: dict[str, dict[str, object]] = {}
            internal_purposes = sorted(
                set(BOOTSTRAP._FORMAL_FIXED_RESERVATION_CONTRACT)  # noqa: SLF001
                - set(BOOTSTRAP.OUTSIDE_FINAL_RELEASE_RESERVATIONS)
            )
            for purpose in internal_purposes:
                reservations[purpose] = FakeOwned(
                    duplicated_structural_fds[cursor : cursor + 2]
                )
                reservation_handoffs[purpose] = {
                    "purpose": purpose,
                    "to_owner_nonce": expected_owner_nonce,
                }
                cursor += 2
            final_release_parent = FakeOwned(
                duplicated_structural_fds[cursor : cursor + 5],
                path=Path(
                    structural_handoff[
                        "outside_final_release_parent"
                    ]["path"]
                ),
            )
            cursor += 5
            control_parent = FakeOwned(
                (duplicated_structural_fds[cursor],)
            )
            cursor += 1
            assert cursor == 19
            adopted_objects.extend(
                [
                    account,
                    *reservations.values(),
                    final_release_parent,
                    control_parent,
                ]
            )
            adopted_record.update(
                {
                    "account": account,
                    "account_handoff": {
                        "account": "formal",
                        "to_owner_nonce": expected_owner_nonce,
                    },
                    "control_parent": control_parent,
                    "control_parent_handoff": {
                        "control": "formal",
                        "to_owner_nonce": expected_owner_nonce,
                    },
                    "final_release_parent": final_release_parent,
                    "final_release_parent_handoff": {
                        "parent_scope": "campaign-root",
                        "to_owner_nonce": expected_owner_nonce,
                    },
                    "reservations": reservations,
                    "reservation_handoffs": reservation_handoffs,
                }
            )
            return dict(adopted_record)

        @staticmethod
        def validate_transferred_account(*_args: object, **_kwargs: object) -> None:
            return None

        @staticmethod
        def validate_transferred_reservations(*_args: object, **_kwargs: object) -> None:
            return None

        @staticmethod
        def validate_transferred_control_parent(*_args: object, **_kwargs: object) -> None:
            return None

        @staticmethod
        def validate_transferred_final_release_parent(
            _account: object,
            final_release_parent: FakeOwned,
            _handoff: dict[str, object],
            *,
            expected_owner_nonce: str,
            expected_parent_path: Path,
        ) -> None:
            assert expected_owner_nonce == adopted_record[
                "account_handoff"
            ]["to_owner_nonce"]
            assert expected_parent_path == final_release_parent.path

        @staticmethod
        def spawn_persistent_broker_from_transfer(**kwargs: object) -> FakeProcess:
            assert all(
                _is_closed_fd(descriptor)
                for descriptor in inherited_structural_fds
            )
            assert all(
                not _is_closed_fd(descriptor)
                for descriptor in duplicated_structural_fds
            )
            assert kwargs["account"] is adopted_record["account"]
            assert kwargs["fixed_purpose_reservations"] == adopted_record[
                "reservations"
            ]
            assert kwargs["control_parent_capability"] is adopted_record[
                "control_parent"
            ]
            assert kwargs["final_release_parent_capability"] is adopted_record[
                "final_release_parent"
            ]
            spawn_keywords.update(kwargs)
            return process

    def _is_closed_fd(descriptor: int) -> bool:
        try:
            os.fstat(descriptor)
        except OSError:
            return True
        return False

    role_authorization = FakeAuthorization()
    native_authorization = FakeAuthorization()
    monkeypatch.setattr(
        BOOTSTRAP,
        "_package_budget_runtime_source_identities",
        lambda _planned: ({}, {}),
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "open_verified_package_budget_roles",
        lambda **_kwargs: role_authorization,
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "open_verified_package_native_budget_helper",
        lambda **_kwargs: native_authorization,
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_load_package_budget_broker_role",
        lambda _authorization: FakeBrokerModule,
    )
    monkeypatch.setattr(
        BOOTSTRAP,
        "_validate_packaged_resource_calibration_bundles",
        lambda **_kwargs: calibration_authorizations,
    )
    if post_spawn_failure == "attach":
        def reject_owner_attachment(_owner: object) -> None:
            raise RuntimeError("injected persistent-owner attachment failure")

        monkeypatch.setattr(
            BOOTSTRAP,
            "_attach_persistent_bootstrap_budget_owner",
            reject_owner_attachment,
        )
    BOOTSTRAP._ACTIVE_BOOTSTRAP_BUDGET_RUNTIME = {}  # noqa: SLF001
    try:
        def invoke() -> dict[str, object]:
            return BOOTSTRAP._bootstrap_persistent_budget_runtime(  # noqa: SLF001
            budget_runtime=budget_runtime,
            budget_profile=profile,
            budget_profile_identity=budget_profile_identity,
            resource_calibration_bundle_identities=calibration_identities,
            calibration_tool_content_identities={
                role: {
                    "sha256": hashlib.sha256(role.encode()).hexdigest(),
                    "size_bytes": len(role),
                }
                for role in BOOTSTRAP.CALIBRATION_TOOL_PLANNED_ROLES
            },
            package_root_fd=7,
            replay_authorization=replay_authorization,
            package={"package_id": "5" * 64},
            verifier_source_identity={},
            native_helper_source_identity={},
            planned={
                "script.ab16_native_budget_helper_v1": {},
            },
            repository_head="6" * 40,
            run_nonce="run-bootstrap-owner-fixture",
            manager_epoch={},
            endpoint_path=tmp_path / "campaign/formal-ab16/control/budget-broker.sock",
            bootstrap_handoff_spec={
                "artifact_class": "metadata",
                "maximum_bytes": 4096,
                "relative_path": "formal-root-budget-handoff.json",
            },
            formal_root_budget_contract_identity=formal_contract_identity,
            bootstrap_failure_closeout_path=failure_path,
        )
        if post_spawn_failure is not None:
            with pytest.raises(
                RuntimeError,
                match=(
                    "bootstrap-admin connect failure"
                    if post_spawn_failure == "connect"
                    else "persistent-owner attachment failure"
                ),
            ):
                invoke()
            assert process.terminate_unattached_count == 1
            assert process.close_count == 0
            assert all(owned.close_count == 1 for owned in adopted_objects)
            assert all(
                _is_closed_fd(descriptor)
                for descriptor in duplicated_structural_fds
            )
            assert role_authorization.close_count == 1
            assert native_authorization.close_count == 1
            assert "persistent_owner" not in (
                BOOTSTRAP._ACTIVE_BOOTSTRAP_BUDGET_RUNTIME  # noqa: SLF001
            )
            return
        runtime = invoke()
        assert len(inherited_structural_fds) == 19
        assert len(duplicated_structural_fds) == 19
        assert all(
            _is_closed_fd(descriptor)
            for descriptor in inherited_structural_fds
        )
        assert all(
            not _is_closed_fd(descriptor)
            for descriptor in duplicated_structural_fds
        )
        assert spawn_keywords["campaign_run_nonce"] == (
            "run-bootstrap-owner-fixture"
        )
        assert spawn_keywords["formal_root_budget_contract_identity"] == (
            formal_contract_identity
        )
        assert spawn_keywords["bootstrap_failure_closeout_path"] == failure_path
        assert spawn_keywords[
            "formal_resource_calibration_bundle_identity"
        ] == calibration_identities["FORMAL_ORGANIC_ARM"]
        assert [action for action, _payload in process.admin.requests] == [
            "PREPARE_RECOVERY",
            "PUBLISH_BOOTSTRAP_HANDOFF",
            "STATUS",
            "START_FORMAL_LAUNCH_OWNER",
        ]
        handoff = process.admin.requests[1][1]
        assert handoff["run_nonce"] == "run-bootstrap-owner-fixture"
        assert handoff["package_id"] == "5" * 64
        assert handoff["recovery_owner_observation"] == recovery_result
        assert handoff[
            "resource_calibration_authorization_bundles"
        ] == calibration_authorizations
        assert handoff[
            "formal_resource_calibration_bundle_identity"
        ] == calibration_identities["FORMAL_ORGANIC_ARM"]
        assert runtime["formal_root_budget_handoff_identity"]["path"] == str(
            handoff_path
        )
        assert runtime["formal_final_release_parent_handoff"] == (
            adopted_record["final_release_parent_handoff"]
        )
        assert runtime["formal_launch_owner_observation"]["state"] == (
            "BROKER_HOSTED_OWNER_RETAINED"
        )
        assert process.admin.close_session_count == 0
        assert process.close_count == 0
        assert all(owned.close_count == 0 for owned in adopted_objects)
        assert role_authorization.close_count == 0
        assert native_authorization.close_count == 0
        retained_owner = BOOTSTRAP._ACTIVE_BOOTSTRAP_BUDGET_RUNTIME[  # noqa: SLF001
            "persistent_owner"
        ]
        assert isinstance(
            retained_owner,
            BOOTSTRAP._PersistentBootstrapBudgetOwner,  # noqa: SLF001
        )
        retained_owner.close_success()
        assert process.admin.close_session_count == 1
        assert process.close_count == 1
        assert all(owned.close_count == 1 for owned in adopted_objects)
        assert all(
            _is_closed_fd(descriptor)
            for descriptor in duplicated_structural_fds
        )
        assert role_authorization.close_count == 1
        assert native_authorization.close_count == 1
    finally:
        BOOTSTRAP._ACTIVE_BOOTSTRAP_BUDGET_RUNTIME = None  # noqa: SLF001
        replay_authorization.close()
        budget_runtime["bootstrap_failure_reservation"].close()
        budget_runtime["bootstrap_broker"].close()
        assert len(os.listdir("/proc/self/fd")) == before_fds


def test_formal_budget_transfer_is_one_exact_account_reservation_control_cohort(
    tmp_path: Path,
) -> None:
    before = len(os.listdir("/proc/self/fd"))
    profile = _profile()
    profile_path = tmp_path / "resource-budget-profile.json"
    profile_path.write_bytes(BOOTSTRAP._budget_canonical_json(profile))  # noqa: SLF001
    profile_path.chmod(0o444)
    profile_identity = {
        "mode": 0o444,
        **BASE.detached_identity(BASE.snapshot_regular(profile_path)),
    }
    campaign = tmp_path / "campaign"
    contracts = BOOTSTRAP._planned_budget_contracts(  # noqa: SLF001
        campaign_dir=campaign,
        profile=profile,
        profile_identity=profile_identity,
    )
    budget_source = AB16 / "ab16_budget_authority_v1.py"
    runtime = BOOTSTRAP._create_bootstrap_budget_runtime(  # noqa: SLF001
        campaign_dir=campaign,
        base_authority=BASE,
        budget_module=BUDGET,
        budget_module_bytes=budget_source.read_bytes(),
        budget_module_source_identity=BASE.full_identity(
            BASE.snapshot_regular(budget_source)
        ),
        profile=profile,
        contracts=contracts,
    )

    class BrokerShim:
        @staticmethod
        def _seal_abandoned_reservation(  # noqa: SLF001
            purpose: str,
            reservation: object,
            *,
            reason: str,
        ) -> dict[str, object]:
            assert purpose in BOOTSTRAP._FORMAL_FIXED_RESERVATION_CONTRACT  # noqa: SLF001
            assert reason == "zero-authority transfer test closeout"
            descriptor = reservation.fileno()
            os.fchmod(descriptor, 0o444)
            os.fsync(descriptor)
            reservation.close()
            return {"purpose": purpose, "state": "SEALED_UNPUBLISHED_INCOMPLETE"}

    transferred = BOOTSTRAP._transfer_formal_budget_runtime(  # noqa: SLF001
        budget_runtime=runtime,
        broker_module=BrokerShim,
        owner_nonce="a" * 64,
    )
    try:
        assert transferred.account_handoff["to_owner_nonce"] == "a" * 64
        assert set(transferred.reservations) == set(
            BOOTSTRAP._FORMAL_FIXED_RESERVATION_CONTRACT  # noqa: SLF001
        )
        assert set(transferred.reservation_handoffs) == set(
            BOOTSTRAP._FORMAL_FIXED_RESERVATION_CONTRACT  # noqa: SLF001
        )
        assert all(
            handoff["to_owner_nonce"] == "a" * 64
            for handoff in transferred.reservation_handoffs.values()
        )
        assert transferred.control_parent_handoff["to_owner_nonce"] == "a" * 64
        transferred.close_incomplete(
            reason="zero-authority transfer test closeout"
        )
        with pytest.raises(
            BOOTSTRAP.BootstrapError,
            match="cannot close twice",
        ):
            transferred.close_incomplete(
                reason="zero-authority transfer test closeout"
            )
    finally:
        runtime["bootstrap_failure_reservation"].close()
        runtime["bootstrap_broker"].close()
    assert len(os.listdir("/proc/self/fd")) == before


def test_bootstrap_success_terminal_releases_only_bootstrap_writer(
    tmp_path: Path,
) -> None:
    before = len(os.listdir("/proc/self/fd"))
    profile = _profile_with_bootstrap_terminal()
    campaign, runtime = _create_runtime(tmp_path, profile=profile)
    for relative in (
        "campaign-authority",
        "campaign-authority/package",
        "campaign-authority/package/payload",
    ):
        runtime["adapter"].mkdir_exclusive(campaign / relative)
    runtime["adapter"].write_exclusive(
        campaign / "campaign-authority/package/payload/tool.py",
        b"pass\n",
        mode=0o555,
    )
    terminal_path = (
        campaign
        / "bootstrap-authority/bootstrap-budget-terminal.json"
    )
    BOOTSTRAP._arm_bootstrap_budget_runtime_closeout(  # noqa: SLF001
        budget_runtime=runtime,
        budget_profile=profile,
        campaign_dir=campaign,
        terminal_path=terminal_path,
    )

    class FakeAdmin:
        def __init__(self) -> None:
            self.close_session_count = 0
            self.requests: list[tuple[str, dict[str, object]]] = []

        def request(
            self,
            action: str,
            payload: dict[str, object],
            *,
            expected_fd_counts: frozenset[int],
        ) -> SimpleNamespace:
            assert action == "BUILD_AND_DELIVER_FORMAL_LAUNCH_CONTEXT"
            assert payload == {"campaign_dir": str(campaign)}
            assert expected_fd_counts == frozenset({0})
            self.requests.append((action, dict(payload)))
            return SimpleNamespace(
                record={
                    "result": {
                        "context_identity": {
                            "sha256": "9" * 64,
                            "size_bytes": 1,
                        },
                        "owner_acknowledgement": {
                            "status": "CONTEXT_RETAINED"
                        },
                        "state": (
                            "PACKAGE_CONTEXT_REPLAYED_AND_RETAINED"
                        ),
                    }
                }
            )

        def close_session(self) -> None:
            self.close_session_count += 1

    class FakeProcess:
        def __init__(self) -> None:
            self.close_count = 0

        def close(self) -> None:
            self.close_count += 1

    admin = FakeAdmin()
    process = FakeProcess()
    owner = BOOTSTRAP._PersistentBootstrapBudgetOwner(  # noqa: SLF001
        process=process,
        admin=admin,
    )
    owner._formal_launch_owner_confirmed = True  # noqa: SLF001
    BOOTSTRAP._attach_persistent_bootstrap_budget_owner(owner)  # noqa: SLF001
    actor = {
        "pid": os.getpid(),
        "pid_starttime": BOOTSTRAP._proc_starttime(os.getpid()),  # noqa: SLF001
        "uid": os.getuid(),
    }
    closeout = BOOTSTRAP._publish_bootstrap_budget_success(  # noqa: SLF001
        persistent_runtime={
            "broker_actor": actor,
            "schema_version": BOOTSTRAP.BOOTSTRAP_BROKER_RUNTIME_SCHEMA,
            "state": "PERSISTENT_BROKER_AND_RECOVERY_READY",
        },
        package_id="b" * 64,
    )
    try:
        assert closeout["writer_closed"] is True
        assert closeout["record"]["status"] == "PASS"
        assert terminal_path.read_bytes() == BOOTSTRAP._budget_canonical_json(  # noqa: SLF001
            closeout["record"]
        )
        failure = (
            campaign
            / "bootstrap-authority/bootstrap-package-failure-closeout.json"
        )
        assert json.loads(failure.read_bytes())["state"] == (
            "UNUSED_SUCCESS_RESERVE_SEALED"
        )
        assert BOOTSTRAP._ACTIVE_BOOTSTRAP_BUDGET_RUNTIME is None  # noqa: SLF001
        assert admin.close_session_count == 1
        assert admin.requests == [
            (
                "BUILD_AND_DELIVER_FORMAL_LAUNCH_CONTEXT",
                {"campaign_dir": str(campaign)},
            )
        ]
        assert process.close_count == 1
    finally:
        runtime["final_release_parent_capability"].close()
        runtime["control_parent_capability"].close()
        for reservation in runtime["formal_reservations"].values():
            reservation.close()
        runtime["formal_broker"].close()
    assert len(os.listdir("/proc/self/fd")) == before


def test_bootstrap_failure_closeout_is_retained_and_exactly_closes_fds(
    tmp_path: Path,
) -> None:
    before = len(os.listdir("/proc/self/fd"))
    profile = _profile_with_bootstrap_terminal()
    campaign, runtime = _create_runtime(tmp_path, profile=profile)
    BOOTSTRAP._arm_bootstrap_budget_runtime_closeout(  # noqa: SLF001
        budget_runtime=runtime,
        budget_profile=profile,
        campaign_dir=campaign,
        terminal_path=(
            campaign
            / "bootstrap-authority/bootstrap-budget-terminal.json"
        ),
    )

    class FakeAdmin:
        def __init__(self) -> None:
            self.close_count = 0
            self.request_payload: dict[str, object] | None = None

        def request(
            self,
            action: str,
            payload: dict[str, object],
            *,
            expected_fd_counts: frozenset[int],
        ) -> SimpleNamespace:
            assert action == "ABORT_BOOTSTRAP_INCOMPLETE"
            assert expected_fd_counts == frozenset({0})
            self.request_payload = payload
            return SimpleNamespace(
                record={
                    "result": {
                        "abandoned_fixed_reservations": {
                            purpose: {
                                "state": (
                                    "STAGING_SEALED_WITHOUT_REFUND_OR_REUSE"
                                )
                            }
                            for purpose in BOOTSTRAP._FORMAL_FIXED_RESERVATION_CONTRACT  # noqa: SLF001
                        },
                        "bootstrap_failure_identity": payload[
                            "bootstrap_failure_identity"
                        ],
                        "prior_handoff_state": "PENDING",
                        "recovery_handoff_identity": None,
                        "recovery_lock_release": None,
                        "recovery_terminal": {
                            "state": "MARKERLESS_BOOTSTRAP_ABORTED"
                        },
                        "state": "MARKERLESS_BOOTSTRAP_ABORTED",
                    }
                }
            )

        def close(self) -> None:
            self.close_count += 1

    class FakeProcess:
        pidfd = 99

        def __init__(self) -> None:
            self.close_count = 0
            self.wait_count = 0

        def wait(self) -> int:
            self.wait_count += 1
            return 0

        def close(self) -> None:
            self.close_count += 1

    admin = FakeAdmin()
    process = FakeProcess()
    owner = BOOTSTRAP._PersistentBootstrapBudgetOwner(  # noqa: SLF001
        process=process,
        admin=admin,
    )
    BOOTSTRAP._attach_persistent_bootstrap_budget_owner(owner)  # noqa: SLF001
    primary = RuntimeError("injected post-budget bootstrap failure")
    BOOTSTRAP._fail_active_bootstrap_budget_runtime(primary)  # noqa: SLF001
    closeout = (
        campaign
        / "bootstrap-authority/bootstrap-package-failure-closeout.json"
    )
    record = json.loads(closeout.read_bytes())
    assert record["status"] == "FAIL_CLOSED"
    assert record["state"] == "markerless-incomplete"
    assert record["error_type"] == "RuntimeError"
    assert admin.request_payload is not None
    assert admin.request_payload["state"] == "markerless-incomplete"
    assert Path(
        admin.request_payload["bootstrap_failure_identity"]["path"]
    ) == closeout
    assert admin.close_count == 1
    assert process.wait_count == 1
    assert process.close_count == 1
    assert BOOTSTRAP._ACTIVE_BOOTSTRAP_BUDGET_RUNTIME is None  # noqa: SLF001
    runtime["final_release_parent_capability"].close()
    runtime["control_parent_capability"].close()
    for reservation in runtime["formal_reservations"].values():
        reservation.close()
    runtime["formal_broker"].close()
    assert len(os.listdir("/proc/self/fd")) == before


def test_pre_adoption_failure_closes_outside_release_capability(
    tmp_path: Path,
) -> None:
    before = len(os.listdir("/proc/self/fd"))
    profile = _profile_with_bootstrap_terminal()
    campaign, runtime = _create_runtime(tmp_path, profile=profile)
    retained_descriptors = (
        runtime["final_release_parent_capability"].fileno(),
        runtime["control_parent_capability"].fileno(),
        runtime["formal_broker"]._root_fd,  # noqa: SLF001
        runtime["bootstrap_broker"]._root_fd,  # noqa: SLF001
        *(
            reservation.fileno()
            for reservation in runtime["formal_reservations"].values()
        ),
    )
    BOOTSTRAP._arm_bootstrap_budget_runtime_closeout(  # noqa: SLF001
        budget_runtime=runtime,
        budget_profile=profile,
        campaign_dir=campaign,
        terminal_path=(
            campaign
            / "bootstrap-authority/bootstrap-budget-terminal.json"
        ),
    )
    primary = RuntimeError("injected pre-adoption bootstrap failure")
    BOOTSTRAP._fail_active_bootstrap_budget_runtime(primary)  # noqa: SLF001
    assert BOOTSTRAP._ACTIVE_BOOTSTRAP_BUDGET_RUNTIME is None  # noqa: SLF001
    for descriptor in retained_descriptors:
        with pytest.raises(OSError):
            os.fstat(descriptor)
    record = json.loads(
        (
            campaign
            / "bootstrap-authority/bootstrap-package-failure-closeout.json"
        ).read_bytes()
    )
    assert record["state"] == "markerless-incomplete"
    assert record["status"] == "FAIL_CLOSED"
    assert len(os.listdir("/proc/self/fd")) == before
