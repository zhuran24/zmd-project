from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs" / "research" / "noncert_cuts_ab_trust_20260723"


def _load(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, RESEARCH / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = _load("noncert_positive_control_runner", "positive_control_runner.py")
ARITHMETIC = _load("noncert_independent_arithmetic", "independent_arithmetic_check.py")
GATE = _load("noncert_positive_control_gate", "positive_control_gate.py")
SHA = "a" * 64


class _Literal:
    def __init__(self, index: int, name: str = "u_0") -> None:
        self._index = index
        self._name = name

    def Index(self) -> int:
        return self._index

    def Name(self) -> str:
        return self._name


def _compiled(
    operation: str,
    parameters: dict[str, object],
    *,
    family: str = "region_capacity",
) -> Any:
    plan = SimpleNamespace(
        operation=operation,
        parameters=parameters,
        family=family,
        digest=SHA,
    )
    return SimpleNamespace(cut_id="cut-1", digest=SHA, plan=plan)


def _master() -> Any:
    return SimpleNamespace(
        _mandatory_groups=[
            {
                "group_id": "g",
                "facility_type": "machine",
                "instance_ids": ["i1", "i2"],
            }
        ],
        facility_pools={
            "machine": [
                {"occupied_cells": [[0, 0], [1, 0]]},
                {"occupied_cells": [[0, 0], [0, 1]]},
            ]
        },
    )


def _solution() -> dict[str, dict[str, object]]:
    return {
        "i1": {"pose_idx": 0, "pose_id": "p0"},
        "i2": {"pose_idx": 1, "pose_id": "p1"},
    }


def test_runner_defaults_lock_single_worker_and_bundle() -> None:
    args = RUNNER._parse_args(
        [
            "--arm",
            "control",
            "--attempt-dir",
            "/unused/attempt",
            "--run-tag",
            "tag",
        ]
    )
    assert args.workers == 1
    assert (args.ghost_w, args.ghost_h) == (6, 6)
    assert RUNNER.ENABLED_FAMILIES == (
        "region_capacity",
        "shape_packing_hall",
        "power_hitting_set",
    )
    with pytest.raises(SystemExit):
        RUNNER._parse_args(
            [
                "--arm",
                "control",
                "--attempt-dir",
                "/unused/attempt",
                "--run-tag",
                "tag",
                "--workers",
                "2",
            ]
        )


def test_attempt_directory_is_exclusive_and_rejects_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "artifacts"
    parent = root / "run" / "positive-control"
    parent.mkdir(parents=True)
    monkeypatch.setattr(RUNNER, "RUN_ROOT", root)
    attempt = RUNNER._prepare_attempt_dir(parent / "arm-a")
    assert (attempt / "checkpoint").is_dir()
    assert (attempt / "ledger").is_dir()
    assert (attempt / "tmp").is_dir()
    with pytest.raises(FileExistsError):
        RUNNER._prepare_attempt_dir(parent / "arm-a")
    target = tmp_path / "real"
    target.mkdir()
    link = parent / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(RuntimeError, match="symlink"):
        RUNNER._prepare_attempt_dir(link / "arm-b")


def test_f1_arithmetic_sample_excludes_incumbent() -> None:
    sample = RUNNER._arithmetic_sample(
        _compiled(
            "region_capacity_le",
            {"group_cell_weights": {"g": 3}, "capacity": 5},
        ),
        _master(),
        SimpleNamespace(condition_lits=()),
        _solution(),
        (),
    )
    assert sample["lhs"] == 6
    assert sample["rhs"] == 5
    assert sample["active"] is True
    assert sample["violated"] is True


def test_f6_and_f7_arithmetic_samples_use_frozen_solution() -> None:
    master = _master()
    solution = _solution()
    f6 = RUNNER._arithmetic_sample(
        _compiled(
            "shape_packing_hall_le",
            {"group_id": "g", "region_kind": "left_baseline", "capacity": 0},
            family="shape_packing_hall",
        ),
        master,
        SimpleNamespace(condition_lits=(_Literal(0),)),
        solution,
        (1,),
    )
    assert f6["lhs"] == 1
    assert f6["violated"] is True
    f7 = RUNNER._arithmetic_sample(
        _compiled(
            "power_pose_exclusion",
            {
                "group_id": "g",
                "pose_id": "p1",
                "blocked_cells_digest": SHA,
            },
            family="power_hitting_set",
        ),
        master,
        SimpleNamespace(condition_lits=(_Literal(0),)),
        solution,
        (1,),
    )
    assert f7["lhs"] == 1
    assert f7["rhs"] == 0
    assert f7["violated"] is True


def _sample_corpus() -> dict[str, object]:
    return {
        "schema_version": 1,
        "authority": {"head": GATE.EXPECTED_HEAD},
        "arm": "treatment",
        "prestate_sha256": SHA,
        "samples": [
            {
                "cut_id": "cut-1",
                "family": "region_capacity",
                "operation": "region_capacity_le",
                "plan_digest": SHA,
                "compiled_digest": SHA,
                "enforcement_values": [1],
                "contributions": [
                    {
                        "label": "g",
                        "selected_count": 2,
                        "weight": 3,
                        "value": 6,
                    }
                ],
                "lhs": 6,
                "rhs": 5,
                "active": True,
                "violated": True,
            }
        ],
    }


def test_independent_arithmetic_pass_and_mutation_canaries() -> None:
    receipt = ARITHMETIC.verify(_sample_corpus())
    assert receipt["status"] == "PASS"
    assert receipt["recomputed_lhs"] == 6
    mutated = json.loads(json.dumps(_sample_corpus()))
    mutated["samples"][0]["contributions"][0]["value"] = 5
    with pytest.raises(ValueError, match="value mismatch"):
        ARITHMETIC.verify(mutated)
    mutated = json.loads(json.dumps(_sample_corpus()))
    mutated["samples"][0]["enforcement_values"] = [0]
    with pytest.raises(ValueError, match="active flag"):
        ARITHMETIC.verify(mutated)
    mutated["samples"][0]["active"] = False
    mutated["samples"][0]["violated"] = False
    with pytest.raises(ValueError, match="no active violated"):
        ARITHMETIC.verify(mutated)


def test_independent_arithmetic_rejects_empty_treatment_corpus() -> None:
    corpus = _sample_corpus()
    corpus["samples"] = []
    with pytest.raises(ValueError, match="must be non-empty"):
        ARITHMETIC.verify(corpus)


def test_independent_checker_output_is_no_overwrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_path = tmp_path / "samples.json"
    input_path.write_text(json.dumps(_sample_corpus()), encoding="utf-8")
    output_path = tmp_path / "receipt.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "independent_arithmetic_check.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    )
    assert ARITHMETIC.main() == 0
    with pytest.raises(FileExistsError):
        ARITHMETIC.main()


def _arm_result(arm: str) -> dict[str, object]:
    generated, compiled, applied = (0, 0, 0) if arm == "control" else (2, 2, 2)
    return {
        "arm": arm,
        "terminal_status": "ARM_COMPLETE",
        "authority": {"repository_head": GATE.EXPECTED_HEAD},
        "config": {"workers": 1, "families": ["f1", "f6", "f7"]},
        "config_digest": SHA,
        "prestate": {
            "incumbent_sha256": SHA,
            "model_proto_sha256": "b" * 64,
            "ghost_pick": {"anchor": [1, 2]},
        },
        "ledger": {
            "status": "complete",
            "generated": generated,
            "applied": applied,
        },
        "injection": {"compiled_observed": compiled},
        "arithmetic_sample_corpus": {
            "sha256": "c" * 64,
            "prestate_sha256": SHA,
        },
    }


def _receipt() -> dict[str, object]:
    return {
        "status": "PASS",
        "active": True,
        "violated": True,
        "selected_cut_id": "cut-1",
        "input_sha256": "c" * 64,
    }


def test_gate_admits_only_the_mechanism_claim() -> None:
    result = GATE.evaluate(_arm_result("control"), _arm_result("treatment"), _receipt())
    assert result["status"] == "INJECTED_MECHANISM_POSITIVE_CONTROL"
    assert result["admitted"] is True
    not_established = result["claim_boundary"]["not_established"]
    assert "organic_runtime_usefulness" in not_established
    assert "single_family_usefulness" in not_established
    assert "witness_or_lower_bound" in not_established


@pytest.mark.parametrize(
    ("mutation", "check_name"),
    [
        ("prestate", "fresh_replica_prestate"),
        ("control_applied", "control_applied_zero"),
        ("treatment_zero", "treatment_chain_positive"),
        ("receipt", "arithmetic_receipt"),
        ("receipt_binding", "receipt_binding"),
    ],
)
def test_gate_joint_mutations_fail_closed(mutation: str, check_name: str) -> None:
    control = _arm_result("control")
    treatment = _arm_result("treatment")
    receipt = _receipt()
    if mutation == "prestate":
        treatment["prestate"]["incumbent_sha256"] = "d" * 64
    elif mutation == "control_applied":
        control["ledger"]["applied"] = 1
    elif mutation == "treatment_zero":
        treatment["injection"]["compiled_observed"] = 0
    elif mutation == "receipt":
        receipt["violated"] = False
    elif mutation == "receipt_binding":
        receipt["input_sha256"] = "e" * 64
    result = GATE.evaluate(control, treatment, receipt)
    assert result["admitted"] is False
    assert any(row["name"] == check_name and row["passed"] is False for row in result["checks"])


def test_gate_rejects_config_drift() -> None:
    treatment = _arm_result("treatment")
    treatment["config"] = {"workers": 2, "families": ["f1", "f6", "f7"]}
    result = GATE.evaluate(_arm_result("control"), treatment, _receipt())
    assert result["admitted"] is False
    assert any(row["name"] == "config_equality" and row["passed"] is False for row in result["checks"])


def test_gate_rejects_tool_identity_drift() -> None:
    treatment = _arm_result("treatment")
    treatment["authority"] = {
        "repository_head": GATE.EXPECTED_HEAD,
        "identities": {"runner": {"sha256": "f" * 64}},
    }
    result = GATE.evaluate(_arm_result("control"), treatment, _receipt())
    assert result["admitted"] is False
    assert any(row["name"] == "authority_identity_equality" and row["passed"] is False for row in result["checks"])


def test_gate_zero_treatment_establishes_no_claims() -> None:
    treatment = _arm_result("treatment")
    treatment["ledger"]["generated"] = 0
    treatment["ledger"]["applied"] = 0
    treatment["injection"]["compiled_observed"] = 0
    result = GATE.evaluate(_arm_result("control"), treatment, _receipt())
    assert result["status"] == "CREDIBILITY_INCOMPLETE"
    assert result["admitted"] is False
    assert result["claim_boundary"]["established"] == []


def test_runner_keeps_attach_absent_until_injection_and_avoids_tempfile() -> None:
    source = (RESEARCH / "positive_control_runner.py").read_text(encoding="utf-8")
    construction = source.index("controller = LBBDController(")
    treatment_attach = source.index('os.environ["EXACT_CUT_FRAMEWORK_ATTACH"] = "1"', construction)
    assert construction < treatment_attach
    assert "tempfile." not in source
    assert "SerializeToString" not in source
    assert 'str(master.model.Proto()).encode("utf-8")' in source
    assert 'os.environ["TMPDIR"] = str(attempt / "tmp")' in source
