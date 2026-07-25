from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs" / "research" / "noncert_cuts_ab_trust_20260723"
RUN = ROOT / ".artifacts" / "noncert_cuts_ab_trust_20260723" / "run-20260723T113911Z-SrJBE0" / "positive-control"
CLOSEOUT = RUN / "closeout-a001"
HISTORY = CLOSEOUT / "history-v1-manifest-a002.json"
MANDATORY = ROOT / "data" / "preprocessed" / "mandatory_exact_instances.json"
CANDIDATES = ROOT / "data" / "preprocessed" / "candidate_placements.json"
SHA = "a" * 64


def _load(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, RESEARCH / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = _load("noncert_independent_arithmetic_v2", "independent_arithmetic_check_v2.py")
RESOURCE = _load("noncert_independent_resource_v1", "independent_resource_verifier_v1.py")
GATE = _load("noncert_positive_control_gate_v2", "positive_control_gate_v2.py")


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _identity(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {
        "path": str(path.absolute()),
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _canonical_node(value: object) -> object:
    if value is None:
        return ["null"]
    if type(value) is bool:
        return ["bool", value]
    if type(value) is int:
        return ["int", value]
    if type(value) is float:
        return ["float", value]
    if type(value) is str:
        return ["str", value]
    if type(value) is dict:
        return ["mapping", [[key, _canonical_node(value[key])] for key in sorted(value)]]
    if type(value) is list:
        return ["sequence", [_canonical_node(item) for item in value]]
    raise AssertionError(type(value))


def _domain_digest(prefix: bytes, value: object) -> str:
    return hashlib.sha256(prefix + _canonical_bytes(value)).hexdigest()


def _ledger(events: list[dict[str, object]]) -> tuple[bytes, dict[str, object]]:
    previous = "0" * 64
    lines: list[bytes] = []
    for seq, fields in enumerate(events):
        event = {
            **fields,
            "schema_version": "cut-ledger-v1",
            "seq": seq,
            "prev_event_hash": previous,
            "writer_id": "synthetic-writer",
            "scope_id": "synthetic-scope",
            "wallclock_utc": seq,
        }
        line = _canonical_bytes(event)
        lines.append(line)
        previous = hashlib.sha256(line).hexdigest()
    raw = b"\n".join(lines) + b"\n"
    return raw, CHECKER._replay_ledger(raw)


def _checker_case(operation: str) -> dict[str, Any]:
    group = "group::machine::op::0"
    mandatory = [
        {
            "instance_id": "i1",
            "facility_type": "machine",
            "operation_type": "op",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "i2",
            "facility_type": "machine",
            "operation_type": "op",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    candidates = {
        "facility_pools": {
            "machine": [
                {
                    "pose_id": "p0",
                    "anchor": {"x": 0, "y": 0},
                    "occupied_cells": [[0, 0], [1, 0]],
                },
                {
                    "pose_id": "p1",
                    "anchor": {"x": 0, "y": 1},
                    "occupied_cells": [[0, 0], [0, 1]],
                },
            ]
        }
    }
    incumbent = {
        "i1": {
            "instance_id": "i1",
            "facility_type": "machine",
            "operation_type": "op",
            "pose_id": "p0",
            "pose_idx": 0,
            "anchor": {"x": 0, "y": 0},
        },
        "i2": {
            "instance_id": "i2",
            "facility_type": "machine",
            "operation_type": "op",
            "pose_id": "p1",
            "pose_idx": 1,
            "anchor": {"x": 0, "y": 1},
        },
        "ghost_pick": {
            "pose_id": "ghost_anchor::10,11",
            "pose_idx": 7,
            "anchor": {"x": 10, "y": 11},
        },
    }
    prestate_sha = hashlib.sha256(_canonical_bytes(incumbent)).hexdigest()
    ghost_digest = hashlib.sha256(b"zmd.ghost-rect.v1:" + _canonical_bytes([10, 11, 6, 6])).hexdigest()
    if operation == "region_capacity_le":
        family = "region_capacity"
        parameters: dict[str, object] = {
            "capacity": 5,
            "group_cell_weights": {group: 3},
        }
        scope = {
            "domain_fingerprint": "synthetic-domain",
            "ghost_policy": "agnostic",
            "ghost_rect_digest": None,
        }
        contributions = [
            {
                "label": group,
                "selected_count": 2,
                "weight": 3,
                "value": 6,
            }
        ]
        rhs = 5
        condition_lits: list[dict[str, object]] = []
        enforcement: list[dict[str, object]] = []
        assignment_literals: list[dict[str, object]] = []
        rect_idx = None
        receipt_ghost = None
    elif operation == "shape_packing_hall_le":
        family = "shape_packing_hall"
        parameters = {
            "capacity": 0,
            "group_id": group,
            "region_kind": "left_baseline",
        }
        scope = {
            "domain_fingerprint": "synthetic-domain",
            "ghost_policy": "bound",
            "ghost_rect_digest": ghost_digest,
        }
        contributions = [
            {
                "label": group,
                "selected_count": 1,
                "weight": 1,
                "value": 1,
            }
        ]
        rhs = 0
        condition_lits = [{"index": 7, "name": "u_7"}]
        enforcement = [{"index": 7, "name": "u_7", "value": 1}]
        assignment_literals = [{"index": 7, "name": "u_7", "value": 1}]
        rect_idx = 7
        receipt_ghost = ghost_digest
    elif operation == "power_pose_exclusion":
        family = "power_hitting_set"
        parameters = {
            "blocked_cells_digest": "b" * 64,
            "group_id": group,
            "pose_id": "p1",
        }
        scope = {
            "domain_fingerprint": "synthetic-domain",
            "ghost_policy": "bound",
            "ghost_rect_digest": ghost_digest,
        }
        contributions = [
            {
                "label": f"{group}:p1",
                "selected_count": 1,
                "weight": 1,
                "value": 1,
            }
        ]
        rhs = 0
        condition_lits = [{"index": 7, "name": "u_7"}]
        enforcement = [{"index": 7, "name": "u_7", "value": 1}]
        assignment_literals = [{"index": 7, "name": "u_7", "value": 1}]
        rect_idx = 7
        receipt_ghost = ghost_digest
    else:  # pragma: no cover - closed test table
        raise AssertionError(operation)

    semantic_fingerprint = "c" * 64
    scope_projection = {**scope, "schema_version": 1}
    scope_digest = _domain_digest(b"zmd.model-scope.v1:", scope_projection)
    plan_digest = _domain_digest(
        b"zmd.constraint-plan.v1:",
        {
            "family": family,
            "model_scope": _canonical_node(scope_projection),
            "operation": operation,
            "parameters": _canonical_node(parameters),
            "schema_version": 1,
            "semantic_fingerprint": semantic_fingerprint,
        },
    )
    compiled_digest = _domain_digest(
        b"zmd.compiled-cut.v1:",
        {
            "cut_id": "cut-1",
            "plan_digest": plan_digest,
            "proof_digest": "d" * 64,
            "scope_digest": scope_digest,
            "snapshot_digest": "e" * 64,
        },
    )
    compiled = {
        "cut_id": "cut-1",
        "family": family,
        "proof_digest": "d" * 64,
        "scope_digest": scope_digest,
        "snapshot_digest": "e" * 64,
        "compiled_digest": compiled_digest,
        "plan": {
            "family": family,
            "schema_version": 1,
            "semantic_fingerprint": semantic_fingerprint,
            "operation": operation,
            "parameters": parameters,
            "digest": plan_digest,
            "model_scope": scope,
        },
    }
    lhs = sum(int(item["value"]) for item in contributions)
    sample = {
        "cut_id": "cut-1",
        "family": family,
        "operation": operation,
        "plan_digest": plan_digest,
        "compiled_digest": compiled_digest,
        "parameters": parameters,
        "enforcement_literals": enforcement,
        "enforcement_values": [int(item["value"]) for item in enforcement],
        "contributions": contributions,
        "lhs": lhs,
        "rhs": rhs,
        "active": True,
        "violated": True,
    }
    ledger_raw, ledger_replay = _ledger(
        [
            {"event": "GENESIS"},
            {"event": "GENERATED", "cut_id": "cut-1", "family": family},
            {
                "event": "APPLIED",
                "cut_id": "cut-1",
                "family": family,
                "semantic_fingerprint": semantic_fingerprint,
                "plan_digest": plan_digest,
                "receipt": {
                    "rect_idx": rect_idx,
                    "ghost_rect_digest": receipt_ghost,
                    "snapshot_digest": "e" * 64,
                    "master_domain_family": family,
                    "condition_lits": condition_lits,
                    "count_delta": 1,
                    "apply_completed": True,
                },
            },
            {"event": "SEGMENT_SEAL"},
        ]
    )
    arm_result = {
        "schema_version": 1,
        "arm": "treatment",
        "terminal_status": "ARM_COMPLETE",
        "authority": {"repository_head": CHECKER.EXPECTED_HEAD},
        "config": {"ghost_rect": [6, 6]},
        "prestate": {
            "incumbent": incumbent,
            "incumbent_sha256": prestate_sha,
        },
        "injection": {
            "compiled_records": [compiled],
            "compiled_observed": 1,
            "arithmetic_sample_count": 1,
        },
        "ledger": {
            "path": "/synthetic/ledger.jsonl",
            "status": "complete",
            "event_count": ledger_replay["event_count"],
            "event_counts": ledger_replay["event_counts"],
            "tail_hash": ledger_replay["tail_hash"],
            "generated": 1,
            "applied": 1,
        },
    }
    corpus = {
        "schema_version": 1,
        "authority": {"head": CHECKER.EXPECTED_HEAD},
        "arm": "treatment",
        "prestate_sha256": prestate_sha,
        "samples": [sample],
    }
    assignment = {
        "schema_version": 1,
        "prestate_sha256": prestate_sha,
        "literals": assignment_literals,
    }
    return {
        "arm_result": arm_result,
        "sample_corpus": corpus,
        "ledger_raw": ledger_raw,
        "ledger_replay": ledger_replay,
        "mandatory": mandatory,
        "candidates": candidates,
        "assignment": assignment,
    }


def _verify_case(case: dict[str, Any]) -> dict[str, object]:
    return CHECKER.verify(
        arm_result=case["arm_result"],
        sample_corpus=case["sample_corpus"],
        ledger_replay=case["ledger_replay"],
        mandatory_instances=case["mandatory"],
        candidate_placements=case["candidates"],
        frozen_assignment=case["assignment"],
    )


def test_complete_history_manifest_replays_all_v1_bytes() -> None:
    manifest = json.loads(HISTORY.read_bytes())
    _root, members, checks = GATE._replay_manifest(
        manifest,
        _identity(HISTORY),
        expected_sha256=GATE.EXPECTED_HISTORY_MANIFEST_SHA256,
    )
    assert len(members) == 26
    assert all(row["passed"] for row in checks)
    assert members[GATE.V1_TOOL_PATHS["runner"]]["sha256"] == (
        "8f25cbaff596b5fad3208d2b286ebfae602e2a2a97efb24cae2f6a16eea404fb"
    )
    assert members[GATE.V1_TOOL_PATHS["arithmetic_checker"]]["sha256"] == (
        "5ed92c07bd3648f7c3a28f0ee13341b4fe650bb8d1184106b860c5e1797ac746"
    )
    assert members[GATE.V1_TOOL_PATHS["gate"]]["sha256"] == (
        "7d833e92fdae1562890b132d5f9f033c0042534b163302f75156ab883fea5d5e"
    )


@pytest.mark.parametrize(
    ("arm_dir", "arm"),
    [("control-a002", "control"), ("treatment-a001", "treatment")],
)
def test_current_gate_input_arms_replay_no_applied_cut(arm_dir: str, arm: str) -> None:
    attempt = RUN / arm_dir
    ledger = next((attempt / "ledger").glob("*/segment_*.jsonl"))
    receipt = CHECKER.build_receipt(
        arm_result_path=attempt / "result.json",
        sample_corpus_path=attempt / "arithmetic_samples.json",
        ledger_segment_path=ledger,
        mandatory_instances_path=MANDATORY,
        candidate_placements_path=CANDIDATES,
        history_manifest_path=HISTORY,
    )
    assert receipt["arm"] == arm
    assert receipt["status"] == "NO_APPLIED_CUT"
    assert receipt["checked_sample_count"] == 0
    assert receipt["applied_join_count"] == 0


def test_current_gate_a002_remains_fail_closed_on_missing_resource_authority() -> None:
    path = CLOSEOUT / "gate-a002.json"
    assert _identity(path) == {
        "path": str(path.absolute()),
        "size": 38_358,
        "sha256": "de57589e0878f252785de69963dbb3483c02a55db55b8f58024bdb79de040068",
    }
    result = json.loads(path.read_bytes())
    assert result["status"] == "CREDIBILITY_INCOMPLETE"
    assert result["classification_complete"] is False
    assert result["advance_authorized"] is False
    assert result["reason"] == "resource_authority_missing"
    assert result["failed_checks"] == ["resource.authority_present"]
    assert result["claim_boundary"]["established"] == []


@pytest.mark.parametrize(
    "operation",
    [
        "region_capacity_le",
        "shape_packing_hall_le",
        "power_pose_exclusion",
    ],
)
def test_checker_v2_independently_replays_each_applied_family(operation: str) -> None:
    result = _verify_case(_checker_case(operation))
    assert result["status"] == "PASS_APPLIED_VIOLATION"
    assert result["selected"]["lhs"] > result["selected"]["rhs"]
    assert result["selected"]["active"] is True
    assert result["selected"]["violated"] is True


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ("assignment", "stable assignment join"),
        ("plan", "typed plan digest does not rebuild"),
        ("enforcement", "enforcement literal identity mismatch"),
        ("ledger_receipt", "positive completed apply"),
        ("ledger_join", "sample lacks compiled/APPLIED join"),
    ],
)
def test_checker_v2_joint_mutation_canaries(mutation: str, match: str) -> None:
    case = _checker_case("shape_packing_hall_le")
    if mutation == "assignment":
        case["assignment"]["literals"][0]["name"] = "wrong-name"
    elif mutation == "plan":
        case["arm_result"]["injection"]["compiled_records"][0]["plan"]["parameters"]["capacity"] = 1
    elif mutation == "enforcement":
        case["sample_corpus"]["samples"][0]["enforcement_literals"][0]["name"] = "wrong-name"
    elif mutation == "ledger_receipt":
        case["ledger_replay"]["events"][2]["receipt"]["count_delta"] = 0
    elif mutation == "ledger_join":
        case["ledger_replay"]["events"][2]["cut_id"] = "other-cut"
    with pytest.raises(ValueError, match=match):
        _verify_case(case)


def test_checker_v2_rejects_raw_ledger_chain_mutation() -> None:
    case = _checker_case("region_capacity_le")
    mutated = case["ledger_raw"].replace(b'"count_delta":1', b'"count_delta":0', 1)
    with pytest.raises(ValueError, match="hash-chain mismatch"):
        CHECKER._replay_ledger(mutated)


def _gate_arm(
    arm: str,
    *,
    positive: bool,
    sample_identity: dict[str, object],
    ledger_path: Path,
    ledger_summary: dict[str, object],
) -> dict[str, object]:
    count = 1 if arm == "treatment" and positive else 0
    prestate = {
        "incumbent_sha256": SHA,
        "model_proto_sha256": "b" * 64,
        "ghost_pick": {"anchor": {"x": 1, "y": 2}},
    }
    return {
        "schema_version": 1,
        "arm": arm,
        "terminal_status": "ARM_COMPLETE",
        "authority": {
            "repository_head": GATE.EXPECTED_HEAD,
            "project_root": str(ROOT),
            "identities": {
                "runner": _identity(RESEARCH / "positive_control_runner.py"),
            },
        },
        "config": copy.deepcopy(GATE.EXPECTED_CONFIG),
        "config_digest": GATE._digest(GATE.EXPECTED_CONFIG),
        "exact_environment": copy.deepcopy(GATE.EXPECTED_EXACT_ENVIRONMENT),
        "prestate": prestate,
        "ledger": {
            "path": str(ledger_path.absolute()),
            "status": "complete",
            "event_count": ledger_summary["event_count"],
            "event_counts": ledger_summary["event_counts"],
            "tail_hash": ledger_summary["tail_hash"],
            "generated": count,
            "applied": count,
        },
        "injection": {
            "compiled_observed": count,
            "compiled_records": [{"cut_id": "cut-1"}] if count else [],
            "arithmetic_sample_count": count,
        },
        "arithmetic_sample_corpus": sample_identity,
    }


def _gate_fixture(tmp_path: Path, *, positive: bool) -> dict[str, Any]:
    assert ROOT == tmp_path or ROOT in tmp_path.parents
    control_ledger_raw, control_ledger = _ledger([{"event": "GENESIS"}, {"event": "SEGMENT_SEAL"}])
    treatment_events = [{"event": "GENESIS"}]
    if positive:
        treatment_events.extend(
            [
                {"event": "GENERATED", "cut_id": "cut-1", "family": "region_capacity"},
                {
                    "event": "APPLIED",
                    "cut_id": "cut-1",
                    "family": "region_capacity",
                },
            ]
        )
    treatment_events.append({"event": "SEGMENT_SEAL"})
    treatment_ledger_raw, treatment_ledger = _ledger(treatment_events)
    control_ledger_path = tmp_path / "control-ledger.jsonl"
    treatment_ledger_path = tmp_path / "treatment-ledger.jsonl"
    control_ledger_path.write_bytes(control_ledger_raw)
    treatment_ledger_path.write_bytes(treatment_ledger_raw)
    control_sample_path = tmp_path / "control-samples.json"
    treatment_sample_path = tmp_path / "treatment-samples.json"
    _write_json(control_sample_path, {"samples": []})
    _write_json(treatment_sample_path, {"samples": [{}]} if positive else {"samples": []})
    control_sample_identity = _identity(control_sample_path)
    treatment_sample_identity = _identity(treatment_sample_path)
    control = _gate_arm(
        "control",
        positive=False,
        sample_identity=control_sample_identity,
        ledger_path=control_ledger_path,
        ledger_summary=control_ledger,
    )
    treatment = _gate_arm(
        "treatment",
        positive=positive,
        sample_identity=treatment_sample_identity,
        ledger_path=treatment_ledger_path,
        ledger_summary=treatment_ledger,
    )
    control_path = tmp_path / "control.json"
    treatment_path = tmp_path / "treatment.json"
    _write_json(control_path, control)
    _write_json(treatment_path, treatment)
    control_identity = _identity(control_path)
    treatment_identity = _identity(treatment_path)

    old_receipt_path = tmp_path / "old-receipt.json"
    _write_json(old_receipt_path, {"status": "FAIL"})
    old_receipt_identity = _identity(old_receipt_path)
    old_gate = {
        "schema_version": 1,
        "status": "CREDIBILITY_INCOMPLETE",
        "admitted": False,
        "inputs": {
            "control": control_identity,
            "treatment": treatment_identity,
            "arithmetic_receipt": old_receipt_identity,
        },
    }
    old_gate_path = tmp_path / "old-gate.json"
    _write_json(old_gate_path, old_gate)
    old_gate_identity = _identity(old_gate_path)

    history_members = [
        RESEARCH / "positive_control_runner.py",
        RESEARCH / "independent_arithmetic_check.py",
        RESEARCH / "positive_control_gate.py",
        control_path,
        treatment_path,
        old_receipt_path,
        old_gate_path,
    ]
    for index in range(19):
        filler = tmp_path / f"history-filler-{index:02d}.txt"
        filler.write_text(f"{index}\n", encoding="utf-8")
        history_members.append(filler)
    assert len(history_members) == 26
    history = {
        "schema": GATE.EXPECTED_HISTORY_SCHEMA,
        "repository_root": str(ROOT),
        "repository_head": GATE.EXPECTED_HEAD,
        "scope": {
            "allowlisted_history_member_count": 26,
            "closeout_subtree_excluded": (".artifacts/synthetic/positive-control/closeout-a001"),
        },
        "members": [
            {
                "path": str(path.relative_to(ROOT)),
                "size": _identity(path)["size"],
                "sha256": _identity(path)["sha256"],
            }
            for path in history_members
        ],
    }
    history_path = tmp_path / "history.json"
    _write_json(history_path, history)
    history_identity = _identity(history_path)

    checker_tool_identity = _identity(RESEARCH / "independent_arithmetic_check_v2.py")
    common_inputs = {
        "mandatory_instances": _identity(MANDATORY),
        "candidate_placements": _identity(CANDIDATES),
        "history_manifest": history_identity,
    }

    def checker_receipt(
        arm_name: str,
        arm_identity: dict[str, object],
        sample_identity: dict[str, object],
        ledger_path: Path,
        ledger_summary: dict[str, object],
        *,
        applied: bool,
    ) -> dict[str, object]:
        status = "PASS_APPLIED_VIOLATION" if applied else "NO_APPLIED_CUT"
        receipt: dict[str, object] = {
            "schema_version": 2,
            "checker": "independent_arithmetic_check_v2",
            "status": status,
            "arm": arm_name,
            "head": GATE.EXPECTED_HEAD,
            "prestate_sha256": SHA,
            "checker_identity": copy.deepcopy(checker_tool_identity),
            "input_identities": {
                "arm_result": arm_identity,
                "sample_corpus": sample_identity,
                "ledger_segment": _identity(ledger_path),
                **common_inputs,
            },
            "ledger": {
                "status": "complete",
                "event_count": ledger_summary["event_count"],
                "event_counts": ledger_summary["event_counts"],
                "tail_hash": ledger_summary["tail_hash"],
                "applied_count": 1 if applied else 0,
            },
            "checked_sample_count": 1 if applied else 0,
            "applied_join_count": 1 if applied else 0,
            "checks": copy.deepcopy(GATE.EXPECTED_CHECKER_SEMANTIC_CHECKS[status]),
        }
        if applied:
            receipt["selected"] = {
                "cut_id": "cut-1",
                "family": "region_capacity",
                "lhs": 6,
                "rhs": 5,
                "active": True,
                "violated": True,
                "plan_digest": "1" * 64,
                "compiled_digest": "2" * 64,
                "semantic_fingerprint": "3" * 64,
                "ledger_seq": 2,
            }
        return receipt

    control_checker = checker_receipt(
        "control",
        control_identity,
        control_sample_identity,
        control_ledger_path,
        control_ledger,
        applied=False,
    )
    treatment_checker = checker_receipt(
        "treatment",
        treatment_identity,
        treatment_sample_identity,
        treatment_ledger_path,
        treatment_ledger,
        applied=positive,
    )
    control_checker_path = tmp_path / "control-checker.json"
    treatment_checker_path = tmp_path / "treatment-checker.json"
    _write_json(control_checker_path, control_checker)
    _write_json(treatment_checker_path, treatment_checker)

    telemetry_path = tmp_path / "resource-source.json"
    _write_json(telemetry_path, {"immutable": True})
    events_zero = {key: 0 for key in RESOURCE.EXPECTED_MEMORY_EVENT_KEYS}

    def resource_arm(label: str, result_identity: dict[str, object]) -> dict[str, object]:
        return {
            "result_identity": result_identity,
            "unit_name": f"synthetic-{label}",
            "exit_code": 0,
            "termination_reason": "normal_exit",
            "wall_seconds": 10,
            "memory_peak_bytes": 1024,
            "swap_at_completion_bytes": 0,
            "memory_events_delta": events_zero,
            "kill_count": 0,
            "timeout_count": 0,
            "limit_violation_count": 0,
        }

    resource_receipt = {
        "schema_version": 1,
        "schema": "noncert-cuts-positive-control-resource-receipt-v1",
        "repository_head": GATE.EXPECTED_HEAD,
        "contract": copy.deepcopy(RESOURCE.EXPECTED_CONTRACT),
        "arm_results": {
            "control": control_identity,
            "treatment": treatment_identity,
        },
        "source_identities": [_identity(telemetry_path)],
        "arms": {
            "control": resource_arm("control", control_identity),
            "treatment": resource_arm("treatment", treatment_identity),
        },
    }
    resource_path = tmp_path / "resource-receipt.json"
    _write_json(resource_path, resource_receipt)
    resource_identity = _identity(resource_path)
    resource_verifier_tool_identity = _identity(RESEARCH / "independent_resource_verifier_v1.py")
    resource_verifier_receipt = RESOURCE.verify_resource_receipt(
        resource_receipt,
        receipt_identity=resource_identity,
        control_identity=control_identity,
        treatment_identity=treatment_identity,
        verifier_identity=resource_verifier_tool_identity,
    )
    assert resource_verifier_receipt["status"] == "PASS"
    resource_verifier_receipt_path = tmp_path / "resource-verifier.json"
    _write_json(resource_verifier_receipt_path, resource_verifier_receipt)

    return {
        "control": control,
        "control_identity": control_identity,
        "treatment": treatment,
        "treatment_identity": treatment_identity,
        "control_checker": control_checker,
        "control_checker_identity": _identity(control_checker_path),
        "treatment_checker": treatment_checker,
        "treatment_checker_identity": _identity(treatment_checker_path),
        "history_manifest": history,
        "history_identity": history_identity,
        "old_receipt": {"status": "FAIL"},
        "old_receipt_identity": old_receipt_identity,
        "old_gate": old_gate,
        "old_gate_identity": old_gate_identity,
        "checker_tool_identity": checker_tool_identity,
        "verifier_tool_identity": resource_verifier_tool_identity,
        "gate_tool_identity": _identity(RESEARCH / "positive_control_gate_v2.py"),
        "resource_receipt": resource_receipt,
        "resource_identity": resource_identity,
        "resource_verifier_receipt": resource_verifier_receipt,
        "resource_verifier_receipt_identity": _identity(resource_verifier_receipt_path),
        "expected_history_sha256": history_identity["sha256"],
    }


def _evaluate_gate(
    fixture: dict[str, Any],
    *,
    resource_missing: bool = False,
) -> dict[str, object]:
    return GATE.evaluate(
        control=fixture["control"],
        control_identity=fixture["control_identity"],
        treatment=fixture["treatment"],
        treatment_identity=fixture["treatment_identity"],
        control_checker=fixture["control_checker"],
        control_checker_identity=fixture["control_checker_identity"],
        treatment_checker=fixture["treatment_checker"],
        treatment_checker_identity=fixture["treatment_checker_identity"],
        history_manifest=fixture["history_manifest"],
        history_identity=fixture["history_identity"],
        old_receipt=fixture["old_receipt"],
        old_receipt_identity=fixture["old_receipt_identity"],
        old_gate=fixture["old_gate"],
        old_gate_identity=fixture["old_gate_identity"],
        checker_tool_identity=fixture["checker_tool_identity"],
        verifier_tool_identity=fixture["verifier_tool_identity"],
        gate_tool_identity=fixture["gate_tool_identity"],
        resource_authority_missing=resource_missing,
        resource_receipt=None if resource_missing else fixture["resource_receipt"],
        resource_identity=None if resource_missing else fixture["resource_identity"],
        resource_verifier_receipt=(None if resource_missing else fixture["resource_verifier_receipt"]),
        resource_verifier_receipt_identity=(
            None if resource_missing else fixture["resource_verifier_receipt_identity"]
        ),
        expected_history_sha256=str(fixture["expected_history_sha256"]),
    )


@pytest.mark.parametrize(
    ("positive", "expected"),
    [
        (True, "INJECTED_MECHANISM_POSITIVE_CONTROL"),
        (False, "POSITIVE_CONTROL_NEGATIVE"),
    ],
)
def test_resource_pass_is_common_to_both_complete_classifications(
    tmp_path: Path,
    positive: bool,
    expected: str,
) -> None:
    fixture = _gate_fixture(tmp_path, positive=positive)
    result = _evaluate_gate(fixture)
    assert result["status"] == expected
    assert result["classification_complete"] is True
    assert result["advance_authorized"] is positive


@pytest.mark.parametrize("positive", [True, False])
def test_missing_resource_authority_blocks_both_complete_classifications(
    tmp_path: Path,
    positive: bool,
) -> None:
    fixture = _gate_fixture(tmp_path, positive=positive)
    result = _evaluate_gate(fixture, resource_missing=True)
    assert result["status"] == "CREDIBILITY_INCOMPLETE"
    assert result["reason"] == "resource_authority_missing"
    assert result["classification_complete"] is False
    assert result["advance_authorized"] is False


def test_resource_verifier_rejects_incomplete_terminal_fields(tmp_path: Path) -> None:
    fixture = _gate_fixture(tmp_path, positive=False)
    receipt = copy.deepcopy(fixture["resource_receipt"])
    receipt["arms"]["treatment"].pop("swap_at_completion_bytes")
    result = RESOURCE.verify_resource_receipt(
        receipt,
        receipt_identity=fixture["resource_identity"],
        control_identity=fixture["control_identity"],
        treatment_identity=fixture["treatment_identity"],
        verifier_identity=fixture["verifier_tool_identity"],
    )
    assert result["status"] == "FAIL"
    assert any(row["name"] == "treatment.required_fields" and row["passed"] is False for row in result["checks"])


@pytest.mark.parametrize(
    ("mutation", "failed_check"),
    [
        ("oom", "treatment.memory_events_zero"),
        ("kill", "treatment.kill_count"),
        ("limit", "treatment.limit_violation_count"),
    ],
)
def test_resource_verifier_rejects_oom_kill_and_limit_drift(
    tmp_path: Path,
    mutation: str,
    failed_check: str,
) -> None:
    fixture = _gate_fixture(tmp_path, positive=False)
    receipt = copy.deepcopy(fixture["resource_receipt"])
    treatment = receipt["arms"]["treatment"]
    if mutation == "oom":
        treatment["memory_events_delta"]["oom_kill"] = 1
    elif mutation == "kill":
        treatment["kill_count"] = 1
    elif mutation == "limit":
        treatment["limit_violation_count"] = 1
    result = RESOURCE.verify_resource_receipt(
        receipt,
        receipt_identity=fixture["resource_identity"],
        control_identity=fixture["control_identity"],
        treatment_identity=fixture["treatment_identity"],
        verifier_identity=fixture["verifier_tool_identity"],
    )
    assert result["status"] == "FAIL"
    assert any(row["name"] == failed_check and row["passed"] is False for row in result["checks"])


@pytest.mark.parametrize(
    ("mutation", "failed_check"),
    [
        ("environment", "exact_environment"),
        ("resource", "resource.receipt_contract"),
        ("resource_verifier", "resource.verifier_checks"),
        ("checker_tool", "control_checker.checker_identity"),
    ],
)
def test_gate_v2_environment_resource_and_tool_mutations_fail_closed(
    tmp_path: Path,
    mutation: str,
    failed_check: str,
) -> None:
    fixture = _gate_fixture(tmp_path, positive=True)
    if mutation == "environment":
        fixture["treatment"]["exact_environment"]["EXACT_CP_SAT_WORKERS"] = "2"
    elif mutation == "resource":
        fixture["resource_receipt"]["contract"]["memory_high_bytes"] += 1
    elif mutation == "resource_verifier":
        fixture["resource_verifier_receipt"]["checks"][0]["passed"] = False
    elif mutation == "checker_tool":
        fixture["checker_tool_identity"]["sha256"] = "f" * 64
    result = _evaluate_gate(fixture)
    assert result["status"] == "CREDIBILITY_INCOMPLETE"
    assert result["classification_complete"] is False
    assert failed_check in result["failed_checks"]


def test_v2_output_writers_are_no_overwrite_and_reject_symlink_parent(tmp_path: Path) -> None:
    output = tmp_path / "receipt.json"
    CHECKER._write_exclusive(output, {"status": "test"})
    with pytest.raises(FileExistsError):
        CHECKER._write_exclusive(output, {"status": "overwrite"})
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        GATE._write_exclusive(link / "gate.json", {"status": "test"})
