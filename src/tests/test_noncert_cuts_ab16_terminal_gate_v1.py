from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs" / "research" / "noncert_cuts_ab16_20260724"


def _load_path(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _load(name: str):
    return _load_path(name, RESEARCH / f"{name}.py")


GATE = _load("ab16_terminal_gate_v1")
CONTRACT = _load("ab16_contract_v1")


def _identity(name: str) -> dict[str, object]:
    return {
        "path": f"/fixture/{name}",
        "sha256": (name.encode("utf-8").hex() + "0" * 64)[:64],
        "size_bytes": len(name),
    }


def _file_identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "path": str(path.absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _suite_gate_consumer(
    consumer_kind: str,
    snapshot_paths: list[Path],
    monkeypatch: pytest.MonkeyPatch,
):
    if consumer_kind == "tracked-source":
        return GATE
    assert consumer_kind == "first-attempt-package-snapshot"
    packaged = snapshot_paths[0]
    with monkeypatch.context() as no_bytecode:
        no_bytecode.setattr(sys, "dont_write_bytecode", True)
        module = _load_path("ab16_terminal_gate_v1_sealed_package_test", packaged)
    assert not (packaged.parent / "__pycache__").exists()
    return module


def _arm_inputs(
    slot: str = "region-capacity-ab-control",
    *,
    deterministic_time: float = 10.0,
    generated: int = 0,
    compiled: int = 0,
    applied: int = 0,
    arm_incumbent_present: bool = True,
) -> dict[str, object]:
    configuration, order, arm = slot.rsplit("-", 2)
    selection_identity = _identity(f"selection-{slot}")
    manifest_identity = _identity("manifest")
    result_identity = _identity(f"result-{slot}")
    arithmetic_identity = _identity(f"arithmetic-{slot}")
    arithmetic_tool_identity = _identity("arithmetic-tool")
    resource_identity = _identity(f"resource-{slot}")
    preterminal_identity = _identity(f"preterminal-{slot}")
    inner_identity = _identity(f"inner-{slot}")
    pre_run_identity = _identity(f"pre-run-{slot}")
    raw_preterminal_identity = _identity(f"raw-preterminal-{slot}")
    resource_verifier_identity = _identity("resource-verifier")
    derived_resource = {
        "control_group": f"/fixture/{slot}",
        "invocation_id": "b" * 32,
        "keeper_pid": 110,
        "memory_current_bytes": 1,
        "memory_events": {
            "high": 0,
            "low": 0,
            "max": 0,
            "oom": 0,
            "oom_group_kill": 0,
            "oom_kill": 0,
        },
        "memory_peak_bytes": 2,
        "payload_pid": 109,
        "swap_current_bytes": 0,
    }
    enabled = (
        []
        if arm == "control"
        else {
            "region-capacity": ["region_capacity"],
            "shape-packing-hall": ["shape_packing_hall"],
            "power-hitting-set": ["power_hitting_set"],
            "bundle": [
                "region_capacity",
                "shape_packing_hall",
                "power_hitting_set",
            ],
        }[configuration]
    )
    selection = {
        "arm": arm,
        "campaign_id": "a" * 64,
        "enabled_families": enabled,
        "manifest_identity": manifest_identity,
        "order": order,
        "slot": slot,
    }
    history = {
        "binary_propagations": 12,
        "branches": 3,
        "conflicts": 2,
        "deterministic_time": deterministic_time,
        "integer_propagations": 9,
        "ordinal": 1,
        "requested_time_limit_seconds": 900.0,
        "status": "FEASIBLE",
        "user_time": 1.0,
        "wall_time": 1.0,
    }
    last_solve = {"status": "FEASIBLE"}
    terminal = {
        "budget_censor_evidence": {
            "internal_budget_reached": False,
            "kind": "none",
            "limit": None,
            "observed": {},
        },
        "controller_completed": True,
        "controller_status": "CERTIFIED",
        "cumulative_deterministic_time": deterministic_time,
        "master_last_solve": last_solve,
        "master_solve_history": [history],
        "schema_version": GATE.CONTROLLER_TERMINAL_SCHEMA,
    }
    arm_result = {
        "arm": arm,
        "authority_identities": {
            "manifest": manifest_identity,
            "selection": selection_identity,
        },
        "campaign_id": "a" * 64,
        "controller_terminal": terminal,
        "enabled_families": enabled,
        "incumbent_export": {"present": arm_incumbent_present},
        "raw_proof_summary": {
            "controller_last_proof_summary": {"master_status": "FEASIBLE"},
            "master_last_solve": last_solve,
        },
        "slot": slot,
        "status": "RAW_ARM_OBSERVATION_COMPLETE",
    }
    classification = (
        "ORGANIC_NONACTIVATION" if generated == 0 else ("NO_ORGANIC_APPLIED_CUT" if applied == 0 else "ORGANIC_APPLIED")
    )
    arithmetic = {
        "applied_inequality_evaluations": [{"active": True, "violated": True} for _ in range(applied)],
        "arm_incumbent_present": arm_incumbent_present,
        "arm_result_identity": result_identity,
        "authorizations": {
            "family_global_soundness_authorized": False,
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "production_certified_authorized": False,
            "runtime_effect_authorized": False,
        },
        "classification": classification,
        "cut_activity": {
            "applied": applied,
            "compiled": compiled,
            "generated": generated,
        },
        "cut_free_replay_status": "PASS",
        "cut_free_replay_identity": _identity(f"cut-free-{slot}"),
        "cut_free_replay_subject_identity": _identity(
            (f"arm-incumbent-{slot}" if arm_incumbent_present else "baseline-incumbent")
        ),
        "enabled_families": enabled,
        "journal_identity": _identity(f"journal-{slot}"),
        "ledger_identity": _identity(f"ledger-{slot}"),
        "lineage_summary": {
            "applied_cut_ids": [f"cut-{index}" for index in range(applied)],
            "compiled_cut_ids": [f"cut-{index}" for index in range(compiled)],
            "compiled_unapplied_cut_ids": [f"cut-{index}" for index in range(applied, compiled)],
            "generated_cut_ids": [f"cut-{index}" for index in range(generated)],
            "generated_uncompiled_cut_ids": [f"cut-{index}" for index in range(compiled, generated)],
        },
        "manifest_identity": manifest_identity,
        "purpose": GATE.ARITHMETIC_PURPOSE,
        "replay_tool_identity": arithmetic_tool_identity,
        "schema_version": GATE.ARITHMETIC_SCHEMA,
        "selection_identity": selection_identity,
        "slot": slot,
        "status": "PASS",
    }
    preterminal = {
        "authorizations": {
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "production_certified_authorized": False,
            "release_keeper_authorized": True,
        },
        "derived": derived_resource,
        "inner_identity": inner_identity,
        "pre_run_authority_identity": pre_run_identity,
        "preterminal_identity": raw_preterminal_identity,
        "payload_result_identity": result_identity,
        "purpose": GATE.RESOURCE_PURPOSE,
        "runner_selection_identity": selection_identity,
        "schema_version": GATE.RESOURCE_PRETERMINAL_SCHEMA,
        "slot": slot,
        "status": "PASS",
        "verdict": "RESOURCE_PRETERMINAL_PASS",
        "verifier_tool_identity": resource_verifier_identity,
    }
    resource = {
        "authorizations": {
            "family_global_soundness_authorized": False,
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "production_certified_authorized": False,
            "stage_b_promotion_authorized": False,
        },
        "cleanup_identity": _identity(f"cleanup-{slot}"),
        "derived": derived_resource,
        "detached_epoch_observation_identity": _identity(f"detached-epoch-{slot}"),
        "inner_identity": inner_identity,
        "pre_run_authority_identity": pre_run_identity,
        "preterminal_identity": raw_preterminal_identity,
        "purpose": GATE.RESOURCE_PURPOSE,
        "release_identity": _identity(f"release-{slot}"),
        "resource_verification_identity": preterminal_identity,
        "runner_selection_identity": selection_identity,
        "schema_version": GATE.RESOURCE_SCHEMA,
        "slot": slot,
        "status": "PASS",
        "terminal_identity": _identity(f"terminal-{slot}"),
        "verdict": "RESOURCE_TERMINAL_CLEANUP_REPLAY_PASS",
        "verifier_tool_identity": resource_verifier_identity,
    }
    return {
        "arithmetic_receipt": arithmetic,
        "arithmetic_receipt_identity": arithmetic_identity,
        "arithmetic_tool_identity": arithmetic_tool_identity,
        "arm_result": arm_result,
        "arm_result_identity": result_identity,
        "experiment_contract": {
            "budget": {
                "binding_seconds": 600,
                "master_seconds": 900,
                "max_iterations": 30,
                "routing_seconds": 600,
            },
            "solver_parameters": {"binding_alt_cap": 200},
        },
        "replayed_arithmetic_receipt": dict(arithmetic),
        "replayed_resource_receipt": dict(resource),
        "replayed_resource_preterminal_receipt": dict(preterminal),
        "resource_preterminal_identity": preterminal_identity,
        "resource_preterminal_receipt": preterminal,
        "resource_receipt": resource,
        "resource_receipt_identity": resource_identity,
        "resource_verifier_tool_identity": resource_verifier_identity,
        "selection": selection,
        "selection_identity": selection_identity,
        "gate_tool_identity": _identity("terminal-gate"),
    }


def test_arm_gate_joins_two_independent_replays_and_metrics() -> None:
    result = GATE.build_arm_gate(**_arm_inputs())
    assert result["credibility_status"] == GATE.CREDIBILITY_PASS
    assert result["activation_class"] == "ORGANIC_NONACTIVATION"
    assert result["metrics"]["cumulative_deterministic_time"] == 10.0
    assert result["metrics"]["branches"] == 3
    assert all(value is False for value in result["authorizations"].values())


def test_arm_gate_rejects_joint_receipt_and_terminal_mutations() -> None:
    arithmetic_mutation = _arm_inputs()
    arithmetic_mutation["arithmetic_receipt"] = {
        **arithmetic_mutation["arithmetic_receipt"],
        "classification": "ORGANIC_APPLIED",
    }
    with pytest.raises(GATE.GateError, match="independent replay"):
        GATE.build_arm_gate(**arithmetic_mutation)

    unknown = _arm_inputs()
    terminal = unknown["arm_result"]["controller_terminal"]
    terminal["controller_status"] = "UNKNOWN"
    with pytest.raises(GATE.GateError, match="internal_budget"):
        GATE.build_arm_gate(**unknown)

    resource_mutation = _arm_inputs()
    resource_mutation["resource_preterminal_receipt"]["payload_result_identity"] = _identity("wrong-result")
    with pytest.raises(GATE.GateError, match="independent replay"):
        GATE.build_arm_gate(**resource_mutation)

    joint_resource_mutation = _arm_inputs()
    wrong_result = _identity("joint-wrong-result")
    joint_resource_mutation["resource_preterminal_receipt"]["payload_result_identity"] = wrong_result
    joint_resource_mutation["replayed_resource_preterminal_receipt"]["payload_result_identity"] = wrong_result
    with pytest.raises(GATE.GateError, match="identity chain"):
        GATE.build_arm_gate(**joint_resource_mutation)


def _binding_alt_cap_unknown_inputs() -> dict[str, object]:
    values = _arm_inputs(arm_incumbent_present=False)
    terminal = values["arm_result"]["controller_terminal"]
    terminal["controller_status"] = "UNKNOWN"
    values["arm_result"]["raw_proof_summary"]["controller_last_proof_summary"] = {
        "binding_alternative_cap": 200,
        "binding_status": "ALT_CAP_REACHED",
        "master_status": "FEASIBLE",
        "routing_status": "PRECHECK_FRONT_BLOCKED",
    }
    terminal["budget_censor_evidence"] = {
        "internal_budget_reached": True,
        "kind": "binding_alt_cap",
        "limit": 200,
        "observed": {
            "binding_alternative_cap": 200,
            "binding_status": "ALT_CAP_REACHED",
        },
    }
    return values


def _real_topology_arm_gates(
    tmp_path: Path,
    *,
    primary_incumbent_delta: bool = False,
) -> tuple[list[dict[str, object]], list[Path]]:
    snapshot_bytes = (RESEARCH / "ab16_terminal_gate_v1.py").read_bytes()
    arm_gates: list[dict[str, object]] = []
    snapshot_paths: list[Path] = []
    for index, slot in enumerate(GATE.ARM_SEQUENCE):
        is_treatment = slot.endswith("-treatment")
        snapshot_path = (
            tmp_path
            / slot
            / f"attempt-{index + 1:04d}"
            / "tool-snapshots"
            / "0003.bin"
        )
        snapshot_path.parent.mkdir(parents=True)
        snapshot_path.write_bytes(snapshot_bytes)
        values = _arm_inputs(
            slot,
            deterministic_time=(
                20.0
                if primary_incumbent_delta and is_treatment
                else (10.0 if primary_incumbent_delta else 10.0 - (index % 2))
            ),
            generated=1 if is_treatment else 0,
            compiled=1 if is_treatment else 0,
            applied=1 if is_treatment else 0,
            arm_incumbent_present=(is_treatment if primary_incumbent_delta else True),
        )
        values["gate_tool_identity"] = _file_identity(snapshot_path)
        arm_gates.append(GATE.build_arm_gate(**values))
        snapshot_paths.append(snapshot_path)
    assert len({str(path) for path in snapshot_paths}) == len(GATE.ARM_SEQUENCE)
    return arm_gates, snapshot_paths


def test_exact_binding_alt_cap_unknown_is_credible() -> None:
    result = GATE.build_arm_gate(**_binding_alt_cap_unknown_inputs())

    assert result["solver_terminal_class"] == GATE.BUDGET_CENSORED_UNKNOWN
    assert result["credibility_status"] == GATE.CREDIBILITY_PASS


@pytest.mark.parametrize(
    ("reported_cap", "remove_cap"),
    (
        pytest.param(199, False, id="drifted"),
        pytest.param(200.0, False, id="float"),
        pytest.param("200", False, id="string"),
        pytest.param(True, False, id="boolean"),
        pytest.param(None, True, id="missing"),
    ),
)
def test_binding_alt_cap_unknown_rejects_drifted_or_noninteger_report(
    reported_cap: object,
    remove_cap: bool,
) -> None:
    values = _binding_alt_cap_unknown_inputs()
    proof = values["arm_result"]["raw_proof_summary"]["controller_last_proof_summary"]
    if remove_cap:
        proof.pop("binding_alternative_cap")
    else:
        proof["binding_alternative_cap"] = reported_cap

    with pytest.raises(GATE.GateError, match="binding alternative cap"):
        GATE.build_arm_gate(**values)


@pytest.mark.parametrize(
    "censor_limit",
    (
        pytest.param(199, id="drifted"),
        pytest.param(200.0, id="float"),
        pytest.param("200", id="string"),
        pytest.param(True, id="boolean"),
        pytest.param(None, id="null"),
    ),
)
def test_binding_alt_cap_unknown_rejects_drifted_or_noninteger_censor_limit(
    censor_limit: object,
) -> None:
    values = _binding_alt_cap_unknown_inputs()
    values["arm_result"]["controller_terminal"]["budget_censor_evidence"]["limit"] = censor_limit

    with pytest.raises(GATE.GateError, match="binding alternative cap"):
        GATE.build_arm_gate(**values)


@pytest.mark.parametrize(
    "observed",
    (
        pytest.param(
            {"binding_alternative_cap": 199, "binding_status": "ALT_CAP_REACHED"},
            id="drifted-cap",
        ),
        pytest.param(
            {"binding_alternative_cap": 200.0, "binding_status": "ALT_CAP_REACHED"},
            id="float-cap",
        ),
        pytest.param(
            {"binding_status": "ALT_CAP_REACHED"},
            id="missing-cap",
        ),
        pytest.param(
            {
                "binding_alternative_cap": 200,
                "binding_status": "ALT_CAP_REACHED",
                "extra": True,
            },
            id="extra-key",
        ),
        pytest.param(
            {"binding_alternative_cap": 200, "binding_status": "TIMEOUT"},
            id="forged-status",
        ),
    ),
)
def test_binding_alt_cap_unknown_rejects_forged_observed_evidence(
    observed: dict[str, object],
) -> None:
    values = _binding_alt_cap_unknown_inputs()
    values["arm_result"]["controller_terminal"]["budget_censor_evidence"]["observed"] = observed

    with pytest.raises(GATE.GateError, match="binding alternative cap"):
        GATE.build_arm_gate(**values)


@pytest.mark.parametrize(
    "contract_cap",
    (
        pytest.param(199, id="drifted"),
        pytest.param(200.0, id="float"),
        pytest.param("200", id="string"),
        pytest.param(True, id="boolean"),
        pytest.param(None, id="missing"),
    ),
)
def test_binding_alt_cap_unknown_rejects_contract_drift(contract_cap: object) -> None:
    values = _binding_alt_cap_unknown_inputs()
    if contract_cap is None:
        values["experiment_contract"]["solver_parameters"].pop("binding_alt_cap")
    else:
        values["experiment_contract"]["solver_parameters"]["binding_alt_cap"] = contract_cap

    with pytest.raises(GATE.GateError, match="binding alternative cap"):
        GATE.build_arm_gate(**values)


@pytest.mark.parametrize("controller_status", ("CERTIFIED", "INFEASIBLE"))
def test_binding_alt_cap_report_cannot_accompany_nonunknown_controller(
    controller_status: str,
) -> None:
    values = _binding_alt_cap_unknown_inputs()
    terminal = values["arm_result"]["controller_terminal"]
    terminal["controller_status"] = controller_status
    terminal["budget_censor_evidence"] = {
        "internal_budget_reached": False,
        "kind": "none",
        "limit": None,
        "observed": {},
    }

    with pytest.raises(GATE.GateError, match="binding alternative cap"):
        GATE.build_arm_gate(**values)


def test_generic_unknown_without_censor_evidence_still_fails_closed() -> None:
    values = _arm_inputs()
    values["arm_result"]["controller_terminal"]["controller_status"] = "UNKNOWN"

    with pytest.raises(GATE.GateError, match="controller_unknown_without_internal_budget_censor"):
        GATE.build_arm_gate(**values)


@pytest.mark.parametrize(
    "kind",
    ("binding_seconds", "routing_seconds", "max_iterations", "master_seconds"),
)
def test_existing_terminal_gate_budget_censors_are_unchanged(kind: str) -> None:
    values = _arm_inputs(arm_incumbent_present=False)
    terminal = values["arm_result"]["controller_terminal"]
    terminal["controller_status"] = "UNKNOWN"
    proof: dict[str, object]
    if kind == "binding_seconds":
        proof = {"binding_status": "TIMEOUT", "master_status": "FEASIBLE"}
        evidence = {
            "internal_budget_reached": True,
            "kind": kind,
            "limit": 600,
            "observed": {"binding_status": "TIMEOUT"},
        }
    elif kind == "routing_seconds":
        proof = {"master_status": "FEASIBLE", "routing_status": "TIMEOUT"}
        evidence = {
            "internal_budget_reached": True,
            "kind": kind,
            "limit": 600,
            "observed": {"routing_status": "TIMEOUT"},
        }
    elif kind == "max_iterations":
        proof = {"benders_iterations": 30, "master_status": "MAX_ITERATIONS"}
        evidence = {
            "internal_budget_reached": True,
            "kind": kind,
            "limit": 30,
            "observed": {
                "benders_iterations": 30,
                "master_status": "MAX_ITERATIONS",
            },
        }
    else:
        proof = {"master_status": "UNKNOWN"}
        history = terminal["master_solve_history"][0]
        history["status"] = "UNKNOWN"
        history["wall_time"] = 899.0
        terminal["master_last_solve"] = {"status": "UNKNOWN"}
        values["arm_result"]["raw_proof_summary"]["master_last_solve"] = {
            "status": "UNKNOWN"
        }
        evidence = {
            "internal_budget_reached": True,
            "kind": kind,
            "limit": 900,
            "observed": {
                "master_status": "UNKNOWN",
                "solver_status": "UNKNOWN",
                "wall_time": 899.0,
            },
        }
    values["arm_result"]["raw_proof_summary"]["controller_last_proof_summary"] = proof
    terminal["budget_censor_evidence"] = evidence

    result = GATE.build_arm_gate(**values)

    assert result["solver_terminal_class"] == GATE.BUDGET_CENSORED_UNKNOWN


def test_budget_censored_unknown_is_credible_only_with_rebuilt_evidence() -> None:
    values = _arm_inputs(arm_incumbent_present=False)
    terminal = values["arm_result"]["controller_terminal"]
    history = terminal["master_solve_history"][0]
    history["status"] = "UNKNOWN"
    history["wall_time"] = 899.0
    terminal["controller_status"] = "UNKNOWN"
    terminal["master_last_solve"] = {"status": "UNKNOWN"}
    values["arm_result"]["raw_proof_summary"] = {
        "controller_last_proof_summary": {"master_status": "UNKNOWN"},
        "master_last_solve": {"status": "UNKNOWN"},
    }
    terminal["budget_censor_evidence"] = {
        "internal_budget_reached": True,
        "kind": "master_seconds",
        "limit": 900,
        "observed": {
            "master_status": "UNKNOWN",
            "solver_status": "UNKNOWN",
            "wall_time": 899.0,
        },
    }
    result = GATE.build_arm_gate(**values)
    assert result["solver_terminal_class"] == GATE.BUDGET_CENSORED_UNKNOWN
    assert result["arm_incumbent_present"] is False
    assert result["cut_free_incumbent_verified"] is True

    values["arm_result"]["raw_proof_summary"]["controller_last_proof_summary"]["master_status"] = "MAX_ITERATIONS"
    with pytest.raises(GATE.GateError, match="master-time"):
        GATE.build_arm_gate(**values)


@pytest.mark.parametrize(
    "consumer_kind",
    ("tracked-source", "first-attempt-package-snapshot"),
)
def test_suite_gate_merges_real_attempt_paths_by_verified_content_and_preserves_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    consumer_kind: str,
) -> None:
    arms, snapshot_paths = _real_topology_arm_gates(tmp_path)
    suite_gate_consumer = _suite_gate_consumer(
        consumer_kind,
        snapshot_paths,
        monkeypatch,
    )

    result = suite_gate_consumer.build_suite_gate(
        arm_gates=arms,
        contract=CONTRACT,
    )

    first_identity = _file_identity(snapshot_paths[0])
    assert set(result) == {
        "arm_gate_slots",
        "authorizations",
        "bundle_nonadditivity_diagnostic",
        "configuration_results",
        "credibility_status",
        "gate_tool_content_identity",
        "gate_tool_provenance_by_slot",
        "manifest_identity",
        "schema_version",
        "status",
    }
    assert result["schema_version"] == "noncert-cuts-ab16-terminal-classification-v2"
    assert result["gate_tool_content_identity"] == {
        "sha256": first_identity["sha256"],
        "size_bytes": first_identity["size_bytes"],
    }
    assert result["gate_tool_provenance_by_slot"] == {
        slot: _file_identity(path)
        for slot, path in zip(
            suite_gate_consumer.ARM_SEQUENCE,
            snapshot_paths,
            strict=True,
        )
    }
    assert len(
        {
            identity["path"]
            for identity in result["gate_tool_provenance_by_slot"].values()
        }
    ) == len(suite_gate_consumer.ARM_SEQUENCE)
    assert "gate_tool_identity" not in result


@pytest.mark.parametrize(
    "consumer_kind",
    ("tracked-source", "first-attempt-package-snapshot"),
)
@pytest.mark.parametrize(
    ("drift", "error"),
    (
        pytest.param("bytes", "recorded byte identity", id="bytes"),
        pytest.param("sha256", "recorded byte identity", id="recorded-sha256"),
        pytest.param("size_bytes", "recorded byte identity", id="recorded-size"),
        pytest.param("self_consistent_content", "gate-tool content identity", id="self-consistent-content"),
        pytest.param("nul_path", "detached byte identity", id="nul-path"),
    ),
)
def test_suite_gate_rejects_any_attempt_local_gate_tool_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    consumer_kind: str,
    drift: str,
    error: str,
) -> None:
    arms, snapshot_paths = _real_topology_arm_gates(tmp_path)
    suite_gate_consumer = _suite_gate_consumer(
        consumer_kind,
        snapshot_paths,
        monkeypatch,
    )
    last = dict(arms[-1])
    identity = dict(last["gate_tool_identity"])
    if drift == "bytes":
        raw = snapshot_paths[-1].read_bytes()
        snapshot_paths[-1].write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    elif drift == "sha256":
        identity["sha256"] = "0" * 64
        last["gate_tool_identity"] = identity
        arms[-1] = last
    elif drift == "size_bytes":
        identity["size_bytes"] = int(identity["size_bytes"]) + 1
        last["gate_tool_identity"] = identity
        arms[-1] = last
    elif drift == "nul_path":
        identity["path"] = "/tmp/\x00snapshot"
        last["gate_tool_identity"] = identity
        arms[-1] = last
    else:
        raw = snapshot_paths[-1].read_bytes()
        snapshot_paths[-1].write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        last["gate_tool_identity"] = _file_identity(snapshot_paths[-1])
        arms[-1] = last

    with pytest.raises(suite_gate_consumer.GateError, match=error):
        suite_gate_consumer.build_suite_gate(
            arm_gates=arms,
            contract=CONTRACT,
        )


def test_suite_gate_requires_all_16_ordered_credible_arms(tmp_path: Path) -> None:
    arms, _snapshot_paths = _real_topology_arm_gates(tmp_path)
    result = GATE.build_suite_gate(
        arm_gates=arms,
        contract=CONTRACT,
    )
    assert result["credibility_status"] == GATE.CREDIBILITY_PASS
    assert result["status"] == "AB16_FIXED_CONFIGURATION_SUITE_COMPLETE"
    assert result["arm_gate_slots"] == list(GATE.ARM_SEQUENCE)

    with pytest.raises(GATE.GateError, match="exactly 16"):
        GATE.build_suite_gate(
            arm_gates=arms[:-1],
            contract=CONTRACT,
        )

    crossed_manifest = [dict(arm) for arm in arms]
    crossed_manifest[-1] = {
        **crossed_manifest[-1],
        "manifest_identity": _identity("other-manifest"),
    }
    with pytest.raises(GATE.GateError, match="crosses a manifest"):
        GATE.build_suite_gate(
            arm_gates=crossed_manifest,
            contract=CONTRACT,
        )


def test_suite_gate_uses_primary_incumbent_delta_before_time(tmp_path: Path) -> None:
    arms, _snapshot_paths = _real_topology_arm_gates(
        tmp_path,
        primary_incumbent_delta=True,
    )
    result = GATE.build_suite_gate(
        arm_gates=arms,
        contract=CONTRACT,
    )
    for configuration in CONTRACT.CONFIGURATIONS:
        aggregate = result["configuration_results"][configuration]["pair_aggregate"]
        assert aggregate["primary_delta_by_order"] == {
            "ab": 1,
            "ba": 1,
        }
        assert aggregate["claim_gate_pair_band_by_order"] == {
            "ab": CONTRACT.PAIR_BENEFIT,
            "ba": CONTRACT.PAIR_BENEFIT,
        }
