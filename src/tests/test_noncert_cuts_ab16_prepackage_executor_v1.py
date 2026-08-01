"""Exact zero-authority guard for the AB16 pre-package executor boundary."""

from __future__ import annotations

import builtins
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
from types import FrameType, ModuleType
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
AB16 = ROOT / "docs/research/noncert_cuts_ab16_20260724"
BOOTSTRAP_PATH = AB16 / "ab16_campaign_bootstrap_v2.py"
PROFILE_PATH = AB16 / "ab16_resource_budget_profile_phase2_blocked_v1.json"
BOOTSTRAP_RELATIVE = BOOTSTRAP_PATH.relative_to(ROOT).as_posix()
V4 = ROOT / "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724"


def _production_source(filename: object) -> str | None:
    if not isinstance(filename, str) or not filename.endswith(".py"):
        return None
    git_object_marker = "/.git-object/"
    if git_object_marker in filename:
        remainder = filename.split(git_object_marker, 1)[1]
        _head, separator, relative = remainder.partition("/")
        if not separator:
            return None
        candidate = relative
    else:
        try:
            candidate = (
                Path(filename).resolve(strict=False).relative_to(ROOT).as_posix()
            )
        except (OSError, ValueError):
            return None
    if candidate.split("/", 1)[0].startswith("."):
        return None
    if candidate.startswith("src/tests/"):
        return None
    return candidate


def _load_source(module_name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _head_source_identity(path: Path, raw: bytes) -> dict[str, object]:
    metadata = os.stat(path, follow_symlinks=False)
    mode = stat.S_IMODE(metadata.st_mode)
    return {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode": mode,
        "mode_octal": f"{mode:04o}",
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _close_runtime(runtime: dict[str, Any]) -> None:
    runtime["control_parent_capability"].close()
    runtime["final_release_parent_capability"].close()
    runtime["bootstrap_failure_reservation"].close()
    for reservation in runtime["formal_reservations"].values():
        reservation.close()
    runtime["formal_broker"].close()
    runtime["bootstrap_broker"].close()


def _retained_role_handle(
    bootstrap: ModuleType,
    tmp_path: Path,
) -> Any:
    role_descriptors: dict[str, int] = {}
    role_bytes: dict[str, bytes] = {}
    descriptors: list[int] = []
    signatures: dict[int, tuple[int, ...]] = {}
    try:
        for role, source_key in (
            bootstrap.PACKAGE_BUDGET_RUNTIME_SOURCE_KEYS.items()
        ):
            source_name = str(source_key).removeprefix("script.")
            source = (
                V4 / f"{source_name}.py"
                if role == "campaign-authority-v4"
                else AB16 / f"{source_name}.py"
            )
            raw = source.read_bytes()
            retained = tmp_path / bootstrap.PACKAGE_BUDGET_RUNTIME_ROLE_PATHS[
                role
            ].removeprefix("payload/")
            retained.parent.mkdir(parents=True, exist_ok=True)
            retained.write_bytes(raw)
            retained.chmod(0o444)
            descriptor = os.open(
                retained,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            descriptors.append(descriptor)
            role_descriptors[role] = descriptor
            role_bytes[role] = raw
            signatures[descriptor] = bootstrap._stat_signature(  # noqa: SLF001
                os.fstat(descriptor)
            )
        return bootstrap.RetainedPackageBudgetRoleAuthorization(
            descriptors=descriptors,
            signatures=signatures,
            role_descriptors=role_descriptors,
            role_bytes=role_bytes,
            selected_descriptors={},
            selected_records={},
        )
    except BaseException:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise


def _current_profile_fixture(
    bootstrap: ModuleType,
    tmp_path: Path,
) -> tuple[dict[str, Any], dict[str, object]]:
    record = json.loads(PROFILE_PATH.read_bytes())
    current_bootstrap_size = BOOTSTRAP_PATH.stat().st_size
    for artifact in record["bootstrap"]["artifact_maxima"]:
        if "ab16_campaign_bootstrap_v2.py" in str(artifact["path"]):
            artifact["maximum_bytes"] = current_bootstrap_size
    bootstrap_limits: dict[str, int] = {}
    for artifact in record["bootstrap"]["artifact_maxima"]:
        artifact_class = str(artifact["artifact_class"])
        bootstrap_limits[artifact_class] = (
            bootstrap_limits.get(artifact_class, 0)
            + int(artifact["maximum_bytes"])
        )
    failure_reserve = record["bootstrap"]["failure_closeout_reserve"]
    failure_class = str(failure_reserve["artifact_class"])
    bootstrap_limits[failure_class] = (
        bootstrap_limits.get(failure_class, 0)
        + int(failure_reserve["maximum_bytes"])
    )
    record["bootstrap"]["category_limits"] = bootstrap_limits
    by_purpose = {
        str(item["purpose"]): item
        for item in record["formal_root"]["fixed_purpose_reservations"]
    }
    prior_totals: dict[str, int] = {}
    for reservation in by_purpose.values():
        artifact_class = str(reservation["artifact_class"])
        prior_totals[artifact_class] = (
            prior_totals.get(artifact_class, 0)
            + int(reservation["maximum_bytes"])
        )
    for purpose, contract in (
        bootstrap._FORMAL_FIXED_RESERVATION_CONTRACT.items()  # noqa: SLF001
    ):
        by_purpose.setdefault(purpose, {"purpose": purpose}).update(contract)
    current_totals: dict[str, int] = {}
    for reservation in by_purpose.values():
        artifact_class = str(reservation["artifact_class"])
        current_totals[artifact_class] = (
            current_totals.get(artifact_class, 0)
            + int(reservation["maximum_bytes"])
        )
    for artifact_class, current_total in current_totals.items():
        delta = current_total - prior_totals.get(artifact_class, 0)
        record["formal_root"]["fixed_overhead_category_limits"][
            artifact_class
        ] += delta
        record["formal_root"]["category_limits"][artifact_class] += delta
    record["formal_root"]["fixed_purpose_reservations"] = sorted(
        by_purpose.values(),
        key=lambda item: str(item["purpose"]).encode("utf-8"),
    )
    record["profile_sha256"] = bootstrap._budget_digest_without(  # noqa: SLF001
        record,
        "profile_sha256",
    )
    raw = bootstrap._budget_canonical_json(record)  # noqa: SLF001
    path = tmp_path / "current-profile-fixture.json"
    path.write_bytes(raw)
    path.chmod(0o444)
    return record, {
        "mode": 0o444,
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def test_only_bootstrap_project_source_executes_before_first_package_byte(
    tmp_path: Path,
) -> None:
    """The first package write may not retroactively authorize another executor."""

    observed: set[str] = set()
    events: list[tuple[str, str]] = []
    real_compile: Any = builtins.compile

    def record(kind: str, filename: object) -> None:
        relative = _production_source(filename)
        if relative is not None:
            observed.add(relative)
            events.append((kind, relative))

    def tracking_compile(
        source: Any,
        filename: str,
        mode: str,
        flags: int = 0,
        dont_inherit: bool = False,
        optimize: int = -1,
        **kwargs: object,
    ) -> Any:
        record("compile", filename)
        return real_compile(
            source,
            filename,
            mode,
            flags,
            dont_inherit,
            optimize,
            **kwargs,
        )

    def profile(frame: FrameType, event: str, _arg: object) -> None:
        if event == "call":
            record("execute", frame.f_code.co_filename)

    module_name = "_ab16_exact_prepackage_executor_guard"
    bootstrap: ModuleType | None = None
    runtime: dict[str, Any] | None = None
    first_package_byte_published = False
    setattr(builtins, "compile", tracking_compile)
    sys.setprofile(profile)
    try:
        bootstrap = _load_source(module_name, BOOTSTRAP_PATH)
        bootstrap._prepackage_state()  # noqa: SLF001
        profile_record, profile_identity = _current_profile_fixture(
            bootstrap,
            tmp_path,
        )
        campaign = tmp_path / "campaign"
        contracts = bootstrap._planned_budget_contracts(  # noqa: SLF001
            campaign_dir=campaign,
            profile=profile_record,
            profile_identity=profile_identity,
        )
        budget_raw = (
            AB16 / "ab16_budget_authority_v1.py"
        ).read_bytes()
        runtime = bootstrap._create_bootstrap_budget_runtime(  # noqa: SLF001
            campaign_dir=campaign,
            budget_source_bytes=budget_raw,
            budget_source_identity=_head_source_identity(
                AB16 / "ab16_budget_authority_v1.py",
                budget_raw,
            ),
            profile=profile_record,
            contracts=contracts,
        )
        writer = runtime["adapter"]
        writer.mkdir_exclusive(campaign)
        writer.mkdir_exclusive(campaign / "campaign-authority")
        executable_path = Path(sys.executable).resolve()
        executable_raw = executable_path.read_bytes()
        executable_metadata = os.stat(
            executable_path,
            follow_symlinks=False,
        )
        executable_mode = stat.S_IMODE(executable_metadata.st_mode)
        tool_identity = {
            "device": executable_metadata.st_dev,
            "inode": executable_metadata.st_ino,
            "mode": executable_mode,
            "mode_octal": f"{executable_mode:04o}",
            "path": str(executable_path),
            "sha256": hashlib.sha256(executable_raw).hexdigest(),
            "size_bytes": len(executable_raw),
        }
        manager_epoch = {
            "attestation_toolchain": {
                role: dict(tool_identity)
                for role in ("attestor", "python", "sudo")
            },
            "attestor_ast_audit": {},
            "boot_id": "00000000-0000-0000-0000-000000000001",
            "capture_protocol": (
                "double-unprivileged-join-plus-read-only-sudo-attestation-v4"
            ),
            "dbus_unique_owner": ":1.1",
            "manager_executable": dict(tool_identity),
            "manager_features": "fixture",
            "manager_pid": os.getpid(),
            "manager_pid_starttime": 1,
            "manager_version": "fixture",
            "observation_toolchain": {"busctl": dict(tool_identity)},
            "schema": "noncert-cuts-manager-boot-epoch-v4",
        }
        with bootstrap._activate_bootstrap_budget_authority(writer):  # noqa: SLF001
            writer.build_package(
                campaign / "campaign-authority/package",
                [
                    writer.SourceSpec(
                        "tool.ab16_campaign_bootstrap_v2.py",
                        BOOTSTRAP_PATH,
                    )
                ],
                repository_head="1" * 40,
                run_nonce="run-prepackage-executor-guard",
                manager_epoch=manager_epoch,
            )
        assert (
            campaign
            / "campaign-authority/package/SHA256SUMS"
        ).is_file()
        assert (
            campaign
            / "campaign-authority/package/package-manifest.json"
        ).is_file()
        first_package_byte_published = True
    finally:
        sys.setprofile(None)
        setattr(builtins, "compile", real_compile)
        if runtime is not None:
            _close_runtime(runtime)
        if bootstrap is not None:
            state = getattr(bootstrap, "_PREPACKAGE_STATE")
            if state is not None:
                bootstrap._close_bootstrap_binding(state[1])  # noqa: SLF001
                setattr(bootstrap, "_PREPACKAGE_STATE", None)
        sys.modules.pop(module_name, None)

    assert first_package_byte_published
    assert observed == {BOOTSTRAP_RELATIVE}, events


def test_structural_budget_adoption_requires_retained_package_verifier_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = _load_source(
        "_ab16_structural_adoption_guard",
        BOOTSTRAP_PATH,
    )
    profile_record, profile_identity = _current_profile_fixture(
        bootstrap,
        tmp_path,
    )
    campaign = tmp_path / "campaign"
    contracts = bootstrap._planned_budget_contracts(  # noqa: SLF001
        campaign_dir=campaign,
        profile=profile_record,
        profile_identity=profile_identity,
    )
    budget_path = AB16 / "ab16_budget_authority_v1.py"
    budget_raw = budget_path.read_bytes()
    runtime = bootstrap._create_bootstrap_budget_runtime(  # noqa: SLF001
        campaign_dir=campaign,
        budget_source_bytes=budget_raw,
        budget_source_identity=_head_source_identity(
            budget_path,
            budget_raw,
        ),
        profile=profile_record,
        contracts=contracts,
    )
    with pytest.raises(
        bootstrap.BootstrapError,
        match="verified package authorization",
    ):
        bootstrap._export_bootstrap_structural_handoff(  # noqa: SLF001
            budget_runtime=runtime,
            replay_authorization=SimpleNamespace(
                result={
                    "schema": bootstrap.PACKAGE_INDEPENDENT_REPLAY_SCHEMA,
                    "status": "PASS",
                }
            ),
            to_owner_nonce="a" * 64,
        )

    replay_result = {
        "schema": bootstrap.PACKAGE_INDEPENDENT_REPLAY_SCHEMA,
        "status": "PASS",
    }
    replay_raw = bootstrap._budget_canonical_json(replay_result)  # noqa: SLF001
    replay_path = tmp_path / "independent-replay.json"
    replay_path.write_bytes(replay_raw)
    replay_path.chmod(0o444)
    descriptor = os.open(
        replay_path,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    replay = bootstrap.VerifiedPackageIndependentReplay(
        result=replay_result,
        identity={
            "path": str(replay_path),
            "sha256": hashlib.sha256(replay_raw).hexdigest(),
            "size_bytes": len(replay_raw),
        },
        descriptor=descriptor,
        signature=bootstrap._stat_signature(os.fstat(descriptor)),  # noqa: SLF001
        raw=replay_raw,
    )
    malformed_descriptors: list[int] = []
    account_type = type(runtime["formal_account"])

    def malformed_account_export(
        _account: object,
        *,
        to_owner_nonce: str,
    ) -> tuple[dict[str, object], tuple[int, ...]]:
        assert to_owner_nonce == "a" * 64
        malformed_descriptors.extend(
            (
                os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC),
                os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC),
            )
        )
        return {}, tuple(malformed_descriptors)

    with monkeypatch.context() as fault:
        fault.setattr(
            account_type,
            "export_structural_handoff",
            malformed_account_export,
        )
        with pytest.raises(
            bootstrap.BootstrapError,
            match="structural handoff FD count drifted",
        ):
            bootstrap._export_bootstrap_structural_handoff(  # noqa: SLF001
                budget_runtime=runtime,
                replay_authorization=replay,
                to_owner_nonce="a" * 64,
            )
    assert len(malformed_descriptors) == 2
    for malformed_descriptor in malformed_descriptors:
        with pytest.raises(OSError):
            os.fstat(malformed_descriptor)

    detached: tuple[int, ...] = ()
    role_handle: Any | None = None
    adopted: dict[str, Any] | None = None
    try:
        handoff, detached = (
            bootstrap._export_bootstrap_structural_handoff(  # noqa: SLF001
                budget_runtime=runtime,
                replay_authorization=replay,
                to_owner_nonce="a" * 64,
            )
        )
        assert handoff["schema_version"] == (
            bootstrap.BOOTSTRAP_STRUCTURAL_HANDOFF_SCHEMA
        )
        assert handoff["fd_count"] == len(detached) == 19
        assert handoff["outside_final_release_parent"]["path"] == str(
            campaign / "formal-ab16/final-release"
        )
        assert handoff["outside_final_release_parent"]["directory_path"] == (
            "formal-ab16/final-release"
        )
        assert (
            campaign / "formal-ab16/final-release"
        ).is_dir()
        assert not (
            campaign
            / "formal-ab16/artifacts/formal-ab16/final-release"
        ).exists()
        for purpose in bootstrap.OUTSIDE_FINAL_RELEASE_RESERVATIONS:
            reservation = handoff["reservations"][purpose]
            assert reservation["shared_parent_fd"] is True
            assert reservation["maximum_bytes"] == 4 * 1024 * 1024
            assert reservation["artifact_class"] == "closeout"
            assert reservation["parent_path"] == str(
                campaign / "formal-ab16/final-release"
            )
        assert not (
            campaign
            / "formal-ab16/artifacts/dual-lock-release.json"
        ).exists()
        for aliases in (
            bootstrap.PACKAGE_BUDGET_RUNTIME_MODULE_ALIASES.values()
        ):
            for alias in aliases:
                monkeypatch.delitem(sys.modules, alias, raising=False)
                parent_name, separator, attribute = alias.rpartition(".")
                parent = (
                    sys.modules.get(parent_name) if separator else None
                )
                if parent is not None:
                    monkeypatch.delattr(
                        parent,
                        attribute,
                        raising=False,
                    )
        role_handle = _retained_role_handle(
            bootstrap,
            tmp_path / "retained-adopter-package",
        )
        loaded: dict[str, ModuleType] = {}
        for role in bootstrap.PACKAGE_BUDGET_RUNTIME_LOAD_ORDER:
            loaded[role] = role_handle.load_verified_role(role)
            if role == "ab16-budget-broker-v1":
                break
        broker = loaded["ab16-budget-broker-v1"]
        adopted = dict(
            broker.adopt_bootstrap_structural_handoff(
                handoff,
                detached,
                expected_owner_nonce="a" * 64,
            )
        )
        assert set(adopted) == {
            "account",
            "account_handoff",
            "control_parent",
            "control_parent_handoff",
            "final_release_parent",
            "final_release_parent_handoff",
            "reservations",
            "reservation_handoffs",
        }
        internal_purposes = (
            set(bootstrap._FORMAL_FIXED_RESERVATION_CONTRACT)  # noqa: SLF001
            - set(bootstrap.OUTSIDE_FINAL_RELEASE_RESERVATIONS)
        )
        assert set(adopted["reservations"]) == internal_purposes
        assert set(adopted["reservation_handoffs"]) == internal_purposes
        for descriptor in detached:
            os.close(descriptor)
        detached = ()

        final_release = adopted["final_release_parent"]
        before_recheck = len(os.listdir("/proc/self/fd"))
        final_release_record = final_release.record()
        assert final_release.record() == final_release_record
        assert len(os.listdir("/proc/self/fd")) == before_recheck
        broker.validate_transferred_final_release_parent(
            adopted["account"],
            final_release,
            adopted["final_release_parent_handoff"],
            expected_owner_nonce="a" * 64,
            expected_parent_path=campaign / "formal-ab16/final-release",
        )
        outside_staging_paths = [
            Path(final_release_record["path"]) / record["staging_name"]
            for record in final_release_record["extent_records"].values()
        ]
        for purpose, reservation in adopted["reservations"].items():
            broker._seal_abandoned_reservation(  # noqa: SLF001
                purpose,
                reservation,
                reason="zero-authority structural adoption closeout",
            )
        adopted["control_parent"].close()
        final_release.close()
        adopted["account"].close()
        adopted = None
        for staging_path in outside_staging_paths:
            assert stat.S_IMODE(staging_path.stat().st_mode) == 0o444
    finally:
        if adopted is not None:
            for purpose, reservation in adopted["reservations"].items():
                broker._seal_abandoned_reservation(  # noqa: SLF001
                    purpose,
                    reservation,
                    reason="zero-authority structural adoption cleanup",
                )
            adopted["control_parent"].close()
            adopted["final_release_parent"].close()
            adopted["account"].close()
        if role_handle is not None:
            role_handle.close()
        for descriptor_index in range(len(detached)):
            os.close(int(detached[descriptor_index]))
        replay.close()
        runtime["bootstrap_failure_reservation"].close()
        runtime["bootstrap_account"].close()
        state = getattr(bootstrap, "_PREPACKAGE_STATE")
        if state is not None:
            bootstrap._close_bootstrap_binding(state[1])  # noqa: SLF001
            setattr(bootstrap, "_PREPACKAGE_STATE", None)
        sys.modules.pop("_ab16_structural_adoption_guard", None)


def test_every_retained_package_role_loads_from_fresh_fd_alias_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bootstrap = _load_source(
        "_ab16_retained_role_dag_guard",
        BOOTSTRAP_PATH,
    )
    aliases = {
        alias
        for role_aliases in (
            bootstrap.PACKAGE_BUDGET_RUNTIME_MODULE_ALIASES.values()
        )
        for alias in role_aliases
    }
    for alias in aliases:
        monkeypatch.delitem(sys.modules, alias, raising=False)
        parent_name, separator, attribute = alias.rpartition(".")
        parent = sys.modules.get(parent_name) if separator else None
        if parent is not None:
            monkeypatch.delattr(parent, attribute, raising=False)

    order = bootstrap.PACKAGE_BUDGET_RUNTIME_LOAD_ORDER
    dependencies = bootstrap.PACKAGE_BUDGET_RUNTIME_ROLE_DEPENDENCIES
    assert set(order) == set(bootstrap.PACKAGE_BUDGET_RUNTIME_ROLE_PATHS)
    completed: set[str] = set()
    for role in order:
        assert set(dependencies[role]) <= completed
        completed.add(role)

    handle = _retained_role_handle(bootstrap, tmp_path / "retained-package")
    loaded: dict[str, ModuleType] = {}
    try:
        ambient = ModuleType("ab16_resource_admission_v1")
        monkeypatch.setitem(
            sys.modules,
            "ab16_resource_admission_v1",
            ambient,
        )
        with pytest.raises(
            bootstrap.BootstrapError,
            match="ambient module blocks retained package role",
        ):
            handle.load_verified_role("ab16-resource-admission-v1")
        monkeypatch.delitem(
            sys.modules,
            "ab16_resource_admission_v1",
            raising=False,
        )

        retained_authority = handle.load_verified_role(
            "ab16-authority-v2"
        )
        handle.load_verified_role("ab16-outer-closeout-state-v1")
        qualified_authority_alias = next(
            alias
            for alias in (
                bootstrap.PACKAGE_BUDGET_RUNTIME_MODULE_ALIASES[
                    "ab16-authority-v2"
                ]
            )
            if "." in alias
        )
        monkeypatch.setitem(
            sys.modules,
            qualified_authority_alias,
            ModuleType(qualified_authority_alias),
        )
        with pytest.raises(
            bootstrap.BootstrapError,
            match="module binding drifted",
        ):
            handle.load_verified_role(
                "ab16-formal-launch-validator-v1"
            )
        monkeypatch.setitem(
            sys.modules,
            qualified_authority_alias,
            retained_authority,
        )

        for role in order:
            loaded[role] = handle.load_verified_role(role)
        assert set(loaded) == set(
            bootstrap.PACKAGE_BUDGET_RUNTIME_ROLE_PATHS
        )
        for role, module in loaded.items():
            assert module.__file__ is not None
            assert module.__file__.startswith("/proc/self/fd/")
            assert all(
                sys.modules.get(alias) is module
                for alias in (
                    bootstrap.PACKAGE_BUDGET_RUNTIME_MODULE_ALIASES[role]
                )
            )

        retained_bootstrap = loaded["ab16-campaign-bootstrap-v2"]
        assert retained_bootstrap is not bootstrap
        assert retained_bootstrap._PREPACKAGE_STATE is None  # noqa: SLF001
        assert (
            loaded["ab16-closure-actor-v1"].resource_admission
            is loaded["ab16-resource-admission-v1"]
        )
        assert (
            loaded["ab16-final-release-actor-v1"].broker
            is loaded["ab16-budget-broker-v1"]
        )
        assert (
            loaded["ab16-outer-refunit-closeout-v1"].resource_admission
            is loaded["ab16-resource-admission-v1"]
        )
        assert (
            loaded["ab16-formal-campaign-v1"].budget_broker
            is loaded["ab16-budget-broker-v1"]
        )
        assert (
            loaded["ab16-formal-campaign-v1"].formal_controller
            is loaded["ab16-formal-controller-v1"]
        )
        assert (
            loaded["ab16-formal-campaign-v1"].closure_actor
            is loaded["ab16-closure-actor-v1"]
        )
        assert (
            loaded["ab16-formal-campaign-v1"].final_release_actor
            is loaded["ab16-final-release-actor-v1"]
        )
        assert (
            loaded["ab16-formal-campaign-v1"].formal_root_replay_alternate
            is loaded["replay-ab16-formal-root-alt-v1"]
        )
        assert (
            loaded["ab16-formal-campaign-v1"].formal_root_replay_primary
            is loaded["replay-ab16-formal-root-v1"]
        )
        assert (
            loaded["ab16-formal-orchestrator-v1"].budget_broker
            is loaded["ab16-budget-broker-v1"]
        )
        assert (
            loaded["ab16-formal-orchestrator-v1"].formal_campaign
            is loaded["ab16-formal-campaign-v1"]
        )
        assert (
            loaded["ab16-formal-orchestrator-v1"].bootstrap
            is retained_bootstrap
        )
        closeout_role = "ab16-outer-refunit-closeout-v1"
        qualified_closeout_alias = next(
            alias
            for alias in bootstrap.PACKAGE_BUDGET_RUNTIME_MODULE_ALIASES[
                closeout_role
            ]
            if "." in alias
        )
        monkeypatch.setitem(
            sys.modules,
            qualified_closeout_alias,
            ModuleType(qualified_closeout_alias),
        )
        assert (
            loaded["ab16-outer-guardian-v1"]._closeout_helper_module()
            is loaded[closeout_role]
        )
        with pytest.raises(
            bootstrap.BootstrapError,
            match="module binding drifted",
        ):
            handle.load_verified_role("ab16-formal-orchestrator-v1")
        monkeypatch.setitem(
            sys.modules,
            qualified_closeout_alias,
            loaded[closeout_role],
        )
    finally:
        handle.close()
        assert aliases.isdisjoint(sys.modules)
        sys.modules.pop("_ab16_retained_role_dag_guard", None)


def test_programmatic_bootstrap_api_replays_closure_and_is_one_shot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_name = "_ab16_programmatic_bootstrap_one_shot_guard"
    bootstrap = _load_source(module_name, BOOTSTRAP_PATH)
    replay_calls: list[str] = []
    unwrap_calls: list[dict[str, object]] = []

    def replay() -> None:
        replay_calls.append("closure")

    def unwrapped(**kwargs: object) -> dict[str, object]:
        unwrap_calls.append(dict(kwargs))
        return {"status": "READY"}

    monkeypatch.setattr(bootstrap, "_replay_prepackage_closure", replay)
    monkeypatch.setattr(bootstrap, "_bootstrap_campaign_unwrapped", unwrapped)
    monkeypatch.setattr(
        bootstrap,
        "_fail_active_bootstrap_budget_runtime",
        lambda _error: None,
    )
    arguments = {
        "campaign_dir": tmp_path / "campaign",
        "repository_root": ROOT,
        "gate_a_receipt": tmp_path / "gate-a.json",
        "offline_candidate": tmp_path / "candidate.json",
        "gate_b_approval": tmp_path / "gate-b.json",
        "resource_budget_profile": tmp_path / "profile.json",
        "resource_calibration_bundle_paths": {},
        "strict_input_paths": {},
        "system_tool_paths": {},
    }
    try:
        assert bootstrap.bootstrap_campaign(**arguments) == {
            "status": "READY"
        }
        assert replay_calls == ["closure", "closure"]
        assert len(unwrap_calls) == 1
        with pytest.raises(
            bootstrap.BootstrapError,
            match="API attempt was already consumed",
        ):
            bootstrap.bootstrap_campaign(**arguments)
        assert replay_calls == ["closure", "closure"]
        assert len(unwrap_calls) == 1
    finally:
        state = getattr(bootstrap, "_PREPACKAGE_STATE")
        if state is not None:
            bootstrap._close_bootstrap_binding(state[1])  # noqa: SLF001
            setattr(bootstrap, "_PREPACKAGE_STATE", None)
        sys.modules.pop(module_name, None)
