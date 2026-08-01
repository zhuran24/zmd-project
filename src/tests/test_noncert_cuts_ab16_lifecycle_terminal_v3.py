from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "docs/research/noncert_cuts_ab16_20260724"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


LIFECYCLE = _load(
    "noncert_cuts_ab16_lifecycle_v3_test",
    TOOLS / "organic_resource_lifecycle_v2.py",
)
VERIFIER = _load(
    "noncert_cuts_ab16_resource_verifier_v3_test",
    TOOLS / "organic_resource_verifier_v2.py",
)
TERMINAL = _load(
    "noncert_cuts_ab16_terminal_gate_v3_test",
    TOOLS / "ab16_terminal_gate_v3.py",
)
CONTRACT = _load(
    "noncert_cuts_ab16_contract_for_terminal_v3_test",
    TOOLS / "ab16_contract_v1.py",
)
LEGACY_FIXTURE = _load(
    "noncert_cuts_ab16_terminal_gate_fixture_for_v3_test",
    ROOT / "src/tests/test_noncert_cuts_ab16_terminal_gate_v1.py",
)


def _identity(name: str) -> dict[str, object]:
    raw = name.encode("utf-8")
    return {
        "path": f"/fixture/{name}",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _identity_with_mode(name: str) -> dict[str, object]:
    return {"mode": 0o600, **_identity(name)}


def _prospective_budget_handoff(
    slot: str = "region-capacity-ab-control",
) -> dict[str, object]:
    formal_root = Path("/fixture/campaign/formal")
    attempt = formal_root / "prospective" / "arms" / slot
    attempt_relative = attempt.relative_to(formal_root).as_posix()
    channel = f"arm-{slot}-cut-ledger"
    channel_relative = f"{attempt_relative}/ledger/cut-ledger"
    allocation_id = hashlib.sha256(slot.encode()).hexdigest()
    manager_credential = hashlib.sha256(
        f"manager:{slot}".encode()
    ).hexdigest()
    return {
        "arm_allocation_id": allocation_id,
        "broker_actor_identity": {
            "pid": 401,
            "pid_starttime": 402,
            "uid": 1000,
        },
        "broker_nonce": "prospective-broker-nonce",
        "broker_socket_path": "/fixture/campaign/control/budget-broker.sock",
        "calibration_tool_content_identities": {
            role: {
                "sha256": hashlib.sha256(role.encode("ascii")).hexdigest(),
                "size_bytes": len(role),
            }
            for role in LIFECYCLE.CALIBRATION_TOOL_ROLES
        },
        "fixed_directory_layout": {
            "attempt_root": str(attempt),
            "channel_directories": {channel: channel_relative},
            "directories": [
                {"mode": 0o500, "path": "prospective"},
                {"mode": 0o500, "path": "prospective/arms"},
                {"mode": 0o500, "path": attempt_relative},
                {"mode": 0o500, "path": f"{attempt_relative}/ledger"},
                {"mode": 0o500, "path": channel_relative},
            ],
            "formal_root": str(formal_root),
        },
        "fixed_maxima": {
            "terminal envelope": {
                "artifact_class": "closeout",
                "maximum_bytes": 4096,
            },
        },
        "formal_budget_authority_identity": _identity_with_mode(
            "formal-budget-authority",
        ),
        "manager_openfile_arm_grant": {
            "credential": manager_credential,
            "preregistration": {
                "allocation_identity": {
                    "sha256": allocation_id,
                    "size_bytes": 1,
                },
                "arm_slot": slot,
                "attempt_consumption_identity": _identity(
                    "attempt-consumption",
                ),
                "credential_sha256": hashlib.sha256(
                    manager_credential.encode("ascii")
                ).hexdigest(),
                "manager_epoch_identity": {
                    "sha256": hashlib.sha256(b"manager-epoch").hexdigest(),
                    "size_bytes": len(b"manager-epoch"),
                },
                "schema_version": (
                    LIFECYCLE.MANAGER_OPENFILE_ARM_GRANT_SCHEMA
                ),
                "selection_identity": _identity("selection"),
                "state": "UNBOUND",
                "unit_name": "cuts-ab16-formal-fixture.service",
            },
        },
        "native_helper_package_identity": _identity_with_mode(
            "native-helper",
        ),
    }


def _prospective_arm_inputs(
    slot: str = "region-capacity-ab-control",
    **kwargs: object,
) -> dict[str, object]:
    values = copy.deepcopy(
        LEGACY_FIXTURE._arm_inputs(slot, **kwargs),  # noqa: SLF001
    )
    allocation_id = hashlib.sha256(
        f"allocation:{slot}".encode("utf-8"),
    ).hexdigest()
    formal_identity = _identity("formal-budget-authority")
    binding = {
        "arm_allocation_id": allocation_id,
        "arm_slot": slot,
        "broker_nonce": "prospective-broker-nonce",
        "broker_socket_fd": 8,
        "filesystem_write_confinement": "landlock-read-only-worker-v1",
        "formal_budget_authority_identity": formal_identity,
        "next_sequence": 7,
    }
    selection = values["selection"]
    assert isinstance(selection, dict)
    selection["schema_version"] = TERMINAL.SELECTION_SCHEMA
    selection["budget_handoff"] = {
        "arm_allocation_id": allocation_id,
        "broker_actor_identity": {
            "pid": 401,
            "pid_starttime": 402,
            "uid": 1000,
        },
        "broker_nonce": binding["broker_nonce"],
        "broker_socket_path": "/fixture/control/budget-broker.sock",
        "fixed_directory_layout": {
            "attempt_root": f"/fixture/formal/{slot}",
            "channel_directories": {},
            "directories": [],
            "formal_root": "/fixture/formal",
        },
        "fixed_maxima": {
            "terminal envelope": {
                "artifact_class": "closeout",
                "maximum_bytes": 4096,
            },
        },
        "formal_budget_authority_identity": formal_identity,
        "native_helper_package_identity": _identity("native-helper"),
    }
    arm_result = values["arm_result"]
    assert isinstance(arm_result, dict)
    arm_result["schema_version"] = TERMINAL.RESULT_SCHEMA
    arm_result["budget_authority_binding"] = copy.deepcopy(binding)
    arithmetic = values["arithmetic_receipt"]
    assert isinstance(arithmetic, dict)
    arithmetic["schema_version"] = TERMINAL.ARITHMETIC_SCHEMA
    arithmetic["budget_authority_binding"] = copy.deepcopy(binding)
    values["replayed_arithmetic_receipt"] = copy.deepcopy(arithmetic)

    preterminal = values["resource_preterminal_receipt"]
    assert isinstance(preterminal, dict)
    preterminal["schema_version"] = TERMINAL.RESOURCE_PRETERMINAL_SCHEMA
    values["replayed_resource_preterminal_receipt"] = copy.deepcopy(
        preterminal,
    )
    reference_acquisition = _identity(f"reference-acquisition-{slot}")
    reference_release = _identity(f"reference-release-{slot}")
    resource = values["resource_receipt"]
    assert isinstance(resource, dict)
    resource["schema_version"] = TERMINAL.RESOURCE_SCHEMA
    resource["reference_acquisition_identity"] = reference_acquisition
    resource["reference_release_identity"] = reference_release
    values["replayed_resource_receipt"] = copy.deepcopy(resource)
    return values


def test_prospective_systemd_openfile_transport_is_exactly_fds_3_through_8() -> None:
    slot = "region-capacity-ab-control"
    identities = {
        role: _identity_with_mode(role)
        for role in (
            "authority",
            "loader",
            "native_helper",
            "native_helper_wrapper",
            "python",
        )
    }
    identity_argument = json.dumps(
        identities,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    command = [
        str(identities["python"]["path"]),
        "-I",
        "-B",
        "-c",
        "selected-literal",
        "direct",
        identity_argument,
        "--role",
        "organic-supervisor",
    ]
    handoff = _prospective_budget_handoff(slot)
    actual = LIFECYCLE.build_systemd_run_argv(
        systemd_run_path="/usr/bin/systemd-run",
        unit_name="cuts-ab16-formal-fixture.service",
        supervisor_argv=command,
        resource_contract=LIFECYCLE.FORMAL_RESOURCE_CONTRACT,
        execution_class="FORMAL_AB16",
        formal_budget_handoff=handoff,
        formal_arm_slot=slot,
        formal_attempt_root=Path(
            handoff["fixed_directory_layout"]["attempt_root"],
        ),
    )
    separator = actual.index("--")
    assert actual[separator - 9 : separator - 6] == [
        "--property=StandardInput=null",
        "--property=StandardOutput=journal",
        "--property=StandardError=journal",
    ]
    assert actual[separator - 6 : separator] == [
        (
            "--property=OpenFile=/fixture/python:"
            "ab16-python:read-only"
        ),
        (
            "--property=OpenFile=/fixture/loader:"
            "ab16-loader:read-only"
        ),
        (
            "--property=OpenFile=/fixture/authority:"
            "ab16-authority:read-only"
        ),
        (
            "--property=OpenFile=/fixture/native_helper_wrapper:"
            "ab16-native-helper-wrapper:read-only"
        ),
        (
            "--property=OpenFile=/fixture/native_helper:"
            "ab16-native-helper:read-only"
        ),
        (
            "--property=OpenFile=/fixture/campaign/control/"
            "budget-broker.sock:ab16-budget-broker"
        ),
    ]
    assert actual[separator + 1 : 7 + separator] == [
        "/proc/self/fd/3",
        "-I",
        "-B",
        "-c",
        "selected-literal",
        "systemd-openfile",
    ]


def test_selected_openfile_cohorts_reject_missing_or_mixed_budget_handoff() -> None:
    legacy_identities = {
        role: _identity_with_mode(role)
        for role in ("authority", "loader", "python")
    }
    legacy_command = [
        str(legacy_identities["python"]["path"]),
        "-I",
        "-B",
        "-c",
        "selected-literal",
        "direct",
        json.dumps(
            legacy_identities,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
        "--role",
        "organic-supervisor",
    ]
    common = {
        "systemd_run_path": "/usr/bin/systemd-run",
        "unit_name": "cuts-ab16-formal-fixture.service",
        "resource_contract": LIFECYCLE.FORMAL_RESOURCE_CONTRACT,
        "execution_class": "FORMAL_AB16",
    }
    legacy = LIFECYCLE.build_systemd_run_argv(
        supervisor_argv=legacy_command,
        **common,
    )
    separator = legacy.index("--")
    assert len(legacy[separator - 3 : separator]) == 3
    with pytest.raises(
        LIFECYCLE.LifecycleError,
        match="legacy selected-byte transport received a budget handoff",
    ):
        LIFECYCLE.build_systemd_run_argv(
            supervisor_argv=legacy_command,
            formal_budget_handoff=_prospective_budget_handoff(),
            formal_arm_slot="region-capacity-ab-control",
            formal_attempt_root=Path(
                "/fixture/campaign/formal/prospective/arms/"
                "region-capacity-ab-control",
            ),
            **common,
        )

    prospective_identities = {
        role: _identity_with_mode(role)
        for role in (
            "authority",
            "loader",
            "native_helper",
            "native_helper_wrapper",
            "python",
        )
    }
    prospective_command = [
        str(prospective_identities["python"]["path"]),
        *legacy_command[1:6],
        json.dumps(
            prospective_identities,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
        *legacy_command[7:],
    ]
    with pytest.raises(
        LIFECYCLE.LifecycleError,
        match="prospective selected-byte transport lacks its budget handoff",
    ):
        LIFECYCLE.build_systemd_run_argv(
            supervisor_argv=prospective_command,
            **common,
        )


def test_formal_budget_handoff_binds_manager_allocation_to_arm_id() -> None:
    slot = "region-capacity-ab-control"
    handoff = _prospective_budget_handoff(slot)
    manager = handoff["manager_openfile_arm_grant"]
    assert isinstance(manager, dict)
    preregistration = manager["preregistration"]
    assert isinstance(preregistration, dict)
    allocation = preregistration["allocation_identity"]
    assert isinstance(allocation, dict)
    allocation["sha256"] = "f" * 64
    with pytest.raises(
        LIFECYCLE.LifecycleError,
        match="does not bind the selected arm",
    ):
        LIFECYCLE.validate_formal_budget_handoff(
            handoff,
            expected_attempt_root=Path(
                handoff["fixed_directory_layout"]["attempt_root"],
            ),
            expected_arm_slot=slot,
        )


def test_formal_worker_argv_injection_is_exact_and_rejects_role_drift() -> None:
    template = [
        "/proc/self/fd/3",
        "-I",
        "-B",
        "-c",
        "selected-literal",
        "direct",
        "{}",
        "--role",
        "organic-arm",
        "--pre-run",
        "/fixture/pre-run.json",
    ]
    actual = LIFECYCLE._worker_session_argv(  # noqa: SLF001
        template,
        '{"session":"exact"}',
    )
    assert actual[7:9] == [
        "--formal-worker-session-json",
        '{"session":"exact"}',
    ]
    assert actual[9:] == template[7:]
    drifted = list(template)
    drifted[8] = "organic-supervisor"
    with pytest.raises(
        LIFECYCLE.LifecycleError,
        match="selected-byte role drifted",
    ):
        LIFECYCLE._worker_session_argv(  # noqa: SLF001
            drifted,
            '{"session":"exact"}',
        )


def test_arm_supervisor_backend_rejects_selection_binding_drift() -> None:
    handoff = _prospective_budget_handoff()
    manager = handoff["manager_openfile_arm_grant"]
    assert isinstance(manager, dict)
    preregistration = manager["preregistration"]
    assert isinstance(preregistration, dict)

    class Backend:
        authority_binding = {
            "arm_allocation_identity": copy.deepcopy(
                preregistration["allocation_identity"],
            ),
            "arm_slot": "region-capacity-ab-control",
            "filesystem_write_confinement": (
                "not-applicable-persistent-supervisor-v1"
            ),
            "selection_identity": copy.deepcopy(
                preregistration["selection_identity"],
            ),
        }
        formal_budget_runtime = {
            "broker_endpoint_identity": {},
        }

        @staticmethod
        def register_arm_worker_grant(**_kwargs: object) -> None:
            return None

    LIFECYCLE._validate_arm_supervisor_backend(  # noqa: SLF001
        Backend(),
        pre_run={
            "budget_handoff": handoff,
            "slot": "region-capacity-ab-control",
        },
    )
    Backend.authority_binding["selection_identity"] = _identity("other")
    with pytest.raises(
        LIFECYCLE.LifecycleError,
        match="budget binding drifted",
    ):
        LIFECYCLE._validate_arm_supervisor_backend(  # noqa: SLF001
            Backend(),
            pre_run={
                "budget_handoff": handoff,
                "slot": "region-capacity-ab-control",
            },
        )


def test_arm_supervisor_factory_closes_fd8_on_pre_attach_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        saved_fd8: int | None = os.dup(8)
    except OSError:
        saved_fd8 = None
    source_fd = os.open("/dev/null", os.O_RDONLY | os.O_CLOEXEC)
    try:
        if source_fd != 8:
            os.dup2(source_fd, 8)
            os.close(source_fd)
            source_fd = -1

        def fail_before_transfer(*_args: object, **_kwargs: object) -> object:
            raise LIFECYCLE.LifecycleError("fixture pre-attach failure")

        monkeypatch.setattr(
            LIFECYCLE,
            "_formal_arm_supervisor_budget_backend_from_owned_fd",
            fail_before_transfer,
        )
        with pytest.raises(
            LIFECYCLE.LifecycleError,
            match="fixture pre-attach failure",
        ):
            LIFECYCLE.formal_arm_supervisor_budget_backend_from_fd(
                8,
                native_budget_helper=object(),
                campaign_dir=Path("/fixture/campaign"),
                pre_run_path=Path("/fixture/pre-run.json"),
                selection_path=Path("/fixture/selection.json"),
            )
        with pytest.raises(OSError):
            os.fstat(8)
    finally:
        if source_fd >= 0 and source_fd != 8:
            os.close(source_fd)
        if saved_fd8 is not None:
            os.dup2(saved_fd8, 8)
            os.close(saved_fd8)


def test_lifecycle_schema_cohorts_are_exact_and_disjoint() -> None:
    legacy = LIFECYCLE.lifecycle_schema_cohort(
        {"schema_version": LIFECYCLE.PRE_RUN_AUTHORITY_SCHEMA},
    )
    prospective = LIFECYCLE.lifecycle_schema_cohort(
        {"schema_version": LIFECYCLE.FORMAL_PRE_RUN_AUTHORITY_SCHEMA},
    )
    assert legacy == {
        "cleanup": "noncert-cuts-ab16-cleanup-v2",
        "inner": "noncert-cuts-ab16-inner-lifecycle-v2",
        "preterminal": "noncert-cuts-ab16-preterminal-resource-v2",
        "reference_acquisition": (
            "noncert-cuts-ab16-unit-reference-acquisition-v1"
        ),
        "reference_release": "noncert-cuts-ab16-unit-reference-release-v1",
        "release": "noncert-cuts-ab16-release-token-v2",
        "terminal": "noncert-cuts-ab16-terminal-envelope-v2",
    }
    assert prospective == {
        "cleanup": "noncert-cuts-ab16-cleanup-v3",
        "inner": "noncert-cuts-ab16-inner-lifecycle-v3",
        "preterminal": "noncert-cuts-ab16-preterminal-resource-v3",
        "reference_acquisition": (
            "noncert-cuts-ab16-unit-reference-acquisition-v2"
        ),
        "reference_release": "noncert-cuts-ab16-unit-reference-release-v2",
        "release": "noncert-cuts-ab16-release-token-v3",
        "terminal": "noncert-cuts-ab16-terminal-envelope-v3",
    }
    assert set(legacy.values()).isdisjoint(prospective.values())
    verifier_prospective = VERIFIER.lifecycle_schema_cohort(
        {"schema_version": VERIFIER.FORMAL_PRE_RUN_SCHEMA},
    )
    assert verifier_prospective == {
        **prospective,
        "detached": "noncert-cuts-ab16-detached-resource-terminal-v3",
    }
    with pytest.raises(LIFECYCLE.LifecycleError, match="unsupported"):
        LIFECYCLE.lifecycle_schema_cohort({"schema_version": "unknown"})
    with pytest.raises(VERIFIER.VerificationError, match="unsupported"):
        VERIFIER.lifecycle_schema_cohort({"schema_version": "unknown"})


def test_prospective_lifecycle_builders_emit_only_the_v3_cohort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pre_run = {
        "expected_payload_status": {"expectation": "SUCCESS"},
        "schema_version": LIFECYCLE.FORMAL_PRE_RUN_AUTHORITY_SCHEMA,
    }
    identity = _identity("record")

    def joined(
        _pre_run: Mapping[str, Any],
        _pre_run_identity: Mapping[str, Any],
        _selection: Mapping[str, Any],
        _selection_identity: Mapping[str, Any],
        *,
        invocation_id: str,
        observation: Mapping[str, Any],
    ) -> dict[str, object]:
        return {
            "campaign_id": "a" * 64,
            "invocation_id": invocation_id,
            "manager_epoch_observation": dict(observation),
            "pre_run_authority_identity": dict(identity),
            "run_nonce": "run",
            "runner_selection_identity": dict(identity),
            "slot": "region-capacity-ab-control",
            "unit_name": "fixture.service",
        }

    monkeypatch.setattr(LIFECYCLE, "_join", joined)
    monkeypatch.setattr(
        LIFECYCLE,
        "validate_pre_run_authority",
        lambda value: value,
    )
    observation = lambda phase: {"phase": phase}  # noqa: E731
    systemd_preterminal = {
        field: "x" for field in LIFECYCLE.SYSTEMD_PRETERMINAL_FIELDS
    }
    systemd_reference = {
        field: "x" for field in LIFECYCLE.SYSTEMD_REFERENCE_FIELDS
    }
    systemd_terminal = {
        field: "x" for field in LIFECYCLE.SYSTEMD_TERMINAL_FIELDS
    }
    cgroup = {field: "x" for field in LIFECYCLE.CGROUP_FIELDS}
    call = {
        "client_unique_name": ":1.4",
        "manager_owner_after": ":1.2",
        "manager_owner_before": ":1.2",
        "unit_name": "fixture.service",
    }
    inner = LIFECYCLE.build_inner_record(
        pre_run,
        identity,
        {},
        identity,
        invocation_id="1" * 32,
        launch_observation=observation("launch"),
        supervisor_pid=10,
        supervisor_starttime=11,
        payload_pid=12,
        payload_starttime=13,
        payload_seal_monotonic_ns=100,
        payload_exit_monotonic_ns=200,
        payload_exit_code=0,
        payload_signal=0,
        payload_reaped=True,
        payload_result_identity=identity,
        keeper_ready_monotonic_ns=300,
    )
    preterminal = LIFECYCLE.build_preterminal_record(
        pre_run,
        identity,
        {},
        identity,
        identity,
        invocation_id="1" * 32,
        preterminal_observation=observation("preterminal"),
        observed_at_monotonic_ns=400,
        systemd_raw=systemd_preterminal,
        cgroup_raw=cgroup,
        payload_current_starttime=None,
        keeper_current_starttime=11,
    )
    acquisition = LIFECYCLE.build_reference_acquisition_record(
        pre_run,
        identity,
        {},
        identity,
        invocation_id="1" * 32,
        acquisition_observation=observation("reference-acquire"),
        acquired_at_monotonic_ns=500,
        call_evidence=call,
        systemd_raw=systemd_reference,
    )
    release = LIFECYCLE.build_release_record(
        pre_run,
        identity,
        {},
        identity,
        invocation_id="1" * 32,
        release_observation=observation("release"),
        preterminal_identity=identity,
        resource_verification_identity=identity,
        reference_acquisition_identity=identity,
        keeper_pid=10,
        keeper_starttime=11,
        release_monotonic_ns=600,
    )
    terminal = LIFECYCLE.build_terminal_record(
        pre_run,
        identity,
        {},
        identity,
        identity,
        identity,
        invocation_id="1" * 32,
        first_observation=observation("terminal-first"),
        stable_observation=observation("terminal-stable"),
        first_captured_at_monotonic_ns=700,
        stable_captured_at_monotonic_ns=(
            700 + LIFECYCLE.REFERENCE_STABILITY_HOLD_NS
        ),
        first_systemd_raw=systemd_terminal,
        stable_systemd_raw=systemd_terminal,
    )
    reference_release = LIFECYCLE.build_reference_release_record(
        pre_run,
        identity,
        {},
        identity,
        identity,
        identity,
        invocation_id="1" * 32,
        release_observation=observation("reference-release"),
        released_at_monotonic_ns=(
            800 + LIFECYCLE.REFERENCE_STABILITY_HOLD_NS
        ),
        call_evidence=call,
    )
    cleanup = LIFECYCLE.build_cleanup_record(
        pre_run,
        identity,
        {},
        identity,
        identity,
        identity,
        invocation_id="1" * 32,
        cleanup_observation=observation("cleanup"),
        captured_at_monotonic_ns=(
            900 + LIFECYCLE.REFERENCE_STABILITY_HOLD_NS
        ),
        payload_pid=12,
        payload_current_starttime=None,
        keeper_pid=10,
        keeper_current_starttime=None,
        cgroup_path="/fixture/cgroup",
        cgroup_path_exists=False,
        unit_load_state="not-found",
        matching_unit_names=[],
    )
    assert {
        "cleanup": cleanup["schema_version"],
        "inner": inner["schema_version"],
        "preterminal": preterminal["schema_version"],
        "reference_acquisition": acquisition["schema_version"],
        "reference_release": reference_release["schema_version"],
        "release": release["schema_version"],
        "terminal": terminal["schema_version"],
    } == LIFECYCLE.lifecycle_schema_cohort(pre_run)


def test_verifier_preterminal_dispatch_rejects_a_legacy_inner_in_v3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = _identity("verifier")
    result = _identity("result")
    pre_run_value = {
        "expected_payload_status": {
            "exit_code": 0,
            "expectation": "SUCCESS",
            "signal": 0,
        },
        "output_paths": {"attempt_result": result["path"]},
        "schema_version": VERIFIER.FORMAL_PRE_RUN_SCHEMA,
        "slot": "region-capacity-ab-control",
        "tool_identities": {"organic_resource_verifier": tool},
    }
    pre_run = VERIFIER.Snapshot(
        raw=b"",
        value=pre_run_value,
        identity=_identity("pre-run"),
    )
    selection = VERIFIER.Snapshot(
        raw=b"",
        value={},
        identity=_identity("selection"),
    )
    inner_value = {
        "invocation_id": "1" * 32,
        "keeper_ready_monotonic_ns": 30,
        "manager_epoch_observation": {},
        "payload_exit_code": 0,
        "payload_exit_monotonic_ns": 20,
        "payload_result_identity": result,
        "payload_seal_monotonic_ns": 10,
        "payload_signal": 0,
        "schema_version": VERIFIER.PROSPECTIVE_INNER_SCHEMA,
    }
    inner = VERIFIER.Snapshot(
        raw=b"",
        value=inner_value,
        identity=_identity("inner"),
    )
    preterminal = VERIFIER.Snapshot(
        raw=b"",
        value={
            "captured_at_monotonic_ns": 50,
            "inner_identity": inner.identity,
            "manager_epoch_observation": {},
            "schema_version": VERIFIER.PROSPECTIVE_PRETERMINAL_SCHEMA,
        },
        identity=_identity("preterminal"),
    )
    payload = VERIFIER.Snapshot(
        raw=b"",
        value={
            "schema_version": "noncert-cuts-ab16-organic-arm-result-v2",
            "slot": pre_run_value["slot"],
        },
        identity=result,
    )
    monkeypatch.setattr(
        VERIFIER,
        "validate_pre_run_authority",
        lambda value: value,
    )
    monkeypatch.setattr(
        VERIFIER,
        "_validate_supervisor_module_origin_receipt",
        lambda _pre: None,
    )
    monkeypatch.setattr(
        VERIFIER,
        "_validate_selection",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        VERIFIER,
        "_common_join",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        VERIFIER,
        "_replay_epoch_observation_file",
        lambda *, phase, **_kwargs: {
            "observed_at_monotonic_ns": 1 if phase == "launch" else 40,
        },
    )
    monkeypatch.setattr(
        VERIFIER,
        "_verify_preterminal_values",
        lambda **_kwargs: {"verified": True},
    )
    receipt = VERIFIER.verify_preterminal(
        pre_run=pre_run,
        selection=selection,
        inner=inner,
        preterminal=preterminal,
        payload_result=payload,
        verifier_tool_identity=tool,
    )
    assert receipt["status"] == "PASS"
    crossed_inner = VERIFIER.Snapshot(
        raw=b"",
        value={
            **inner_value,
            "schema_version": VERIFIER.LEGACY_INNER_SCHEMA,
        },
        identity=inner.identity,
    )
    with pytest.raises(
        VERIFIER.VerificationError,
        match="inner lifecycle schema drifted",
    ):
        VERIFIER.verify_preterminal(
            pre_run=pre_run,
            selection=selection,
            inner=crossed_inner,
            preterminal=preterminal,
            payload_result=payload,
            verifier_tool_identity=tool,
        )


def test_independent_resource_replay_has_a_distinct_closed_schema() -> None:
    replayed = {
        "schema_version": VERIFIER.PROSPECTIVE_DETACHED_SCHEMA,
        "slot": "region-capacity-ab-control",
        "status": "PASS",
    }
    stored = VERIFIER.Snapshot(
        raw=VERIFIER.canonical_json_bytes(replayed),
        value=replayed,
        identity=_identity("stored-detached-resource-terminal"),
    )
    tool = _identity("resource-verifier")
    receipt = VERIFIER.build_independent_resource_replay(
        stored_detached=stored,
        replayed_detached=replayed,
        verifier_tool_identity=tool,
    )
    assert (
        receipt["schema_version"]
        == VERIFIER.INDEPENDENT_RESOURCE_REPLAY_SCHEMA
    )
    assert receipt["replayed_resource_terminal"] == replayed
    assert VERIFIER.validate_independent_resource_replay(
        receipt,
        stored_detached=stored,
        replayed_detached=replayed,
        verifier_tool_identity=tool,
    ) == receipt
    tampered = copy.deepcopy(receipt)
    tampered["slot"] = "region-capacity-ab-treatment"
    with pytest.raises(
        VERIFIER.VerificationError,
        match="receipt drifted",
    ):
        VERIFIER.validate_independent_resource_replay(
            tampered,
            stored_detached=stored,
            replayed_detached=replayed,
            verifier_tool_identity=tool,
        )


def test_terminal_v3_binds_selection_result_arithmetic_and_resource() -> None:
    values = _prospective_arm_inputs()
    result = TERMINAL.build_arm_gate(**values)
    assert result["schema_version"] == TERMINAL.ARM_GATE_SCHEMA
    assert result["budget_authority_binding"]["arm_slot"] == result["slot"]
    assert all(value is False for value in result["authorizations"].values())

    for field, replacement, message in (
        ("resource_receipt", TERMINAL._legacy.RESOURCE_SCHEMA, "resource replay"),  # noqa: SLF001
        (
            "selection",
            "noncert-cuts-ab16-organic-arm-selection-v1",
            "selection schema",
        ),
        ("arithmetic_receipt", TERMINAL._legacy.ARITHMETIC_SCHEMA, "arithmetic replay"),  # noqa: SLF001
    ):
        crossed = copy.deepcopy(values)
        record = crossed[field]
        assert isinstance(record, dict)
        record["schema_version"] = replacement
        if field == "resource_receipt":
            replayed = crossed["replayed_resource_receipt"]
            assert isinstance(replayed, dict)
            replayed["schema_version"] = replacement
        elif field == "arithmetic_receipt":
            replayed = crossed["replayed_arithmetic_receipt"]
            assert isinstance(replayed, dict)
            replayed["schema_version"] = replacement
        with pytest.raises(TERMINAL.GateError, match=message):
            TERMINAL.build_arm_gate(**crossed)

    drifted = copy.deepcopy(values)
    arm_result = drifted["arm_result"]
    assert isinstance(arm_result, dict)
    binding = arm_result["budget_authority_binding"]
    assert isinstance(binding, dict)
    binding["arm_allocation_id"] = "f" * 64
    arithmetic = drifted["arithmetic_receipt"]
    replayed_arithmetic = drifted["replayed_arithmetic_receipt"]
    assert isinstance(arithmetic, dict)
    assert isinstance(replayed_arithmetic, dict)
    arithmetic["budget_authority_binding"] = copy.deepcopy(binding)
    replayed_arithmetic["budget_authority_binding"] = copy.deepcopy(binding)
    with pytest.raises(TERMINAL.GateError, match="selection/result"):
        TERMINAL.build_arm_gate(**drifted)


def test_terminal_v3_suite_requires_16_unique_allocations_one_authority() -> None:
    arm_gates = []
    for index, slot in enumerate(TERMINAL.ARM_SEQUENCE):
        generated = int(slot.endswith("-treatment"))
        arm_gates.append(
            TERMINAL.build_arm_gate(
                **_prospective_arm_inputs(
                    slot,
                    deterministic_time=10.0 - (index % 2),
                    generated=generated,
                    compiled=generated,
                    applied=generated,
                ),
            ),
        )
    result = TERMINAL.build_suite_gate(
        arm_gates=arm_gates,
        contract=CONTRACT,
    )
    assert result["schema_version"] == TERMINAL.SUITE_GATE_SCHEMA
    assert set(result["arm_allocation_ids"]) == set(TERMINAL.ARM_SEQUENCE)
    assert len(set(result["arm_allocation_ids"].values())) == 16

    mixed = copy.deepcopy(arm_gates)
    mixed[-1]["schema_version"] = TERMINAL._legacy.ARM_GATE_SCHEMA  # noqa: SLF001
    with pytest.raises(TERMINAL.GateError, match="schema/order"):
        TERMINAL.build_suite_gate(arm_gates=mixed, contract=CONTRACT)

    crossed = copy.deepcopy(arm_gates)
    crossed[-1]["budget_authority_binding"][
        "formal_budget_authority_identity"
    ] = _identity("other-formal-budget-authority")
    with pytest.raises(TERMINAL.GateError, match="crosses"):
        TERMINAL.build_suite_gate(arm_gates=crossed, contract=CONTRACT)
