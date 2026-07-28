from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType

from google.protobuf import text_format
from ortools.sat import cp_model_pb2
import pytest

from devtools.research_run_contract import canonical_json_bytes


pytestmark = pytest.mark.evidence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = PROJECT_ROOT / "docs" / "research" / "w0_power_cycle_domino_d6_20260728"
GATE_PATH = RESEARCH_DIR / "d6_joint_completion_gate.py"
RUNNER_PATH = RESEARCH_DIR / "run_d6_research.py"
STRICT_PATH = (
    PROJECT_ROOT
    / "docs"
    / "research"
    / "cleanroom_rederivation_20260718"
    / "strict"
    / "external"
    / "problem_instance.json"
)
FRAMEWORK_PATH = Path("/home/zhuran24/下载/w0回复/1/W0_power_cycle_domino_framework_v1.json")
SEED_PATH = Path("/home/zhuran24/下载/w0回复/1/W0_geometry_only_seed_v1.json")

STRICT_SHA256 = "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
FRAMEWORK_SHA256 = "db6046cf598f9b5738b7f8950c91ea31834e8214e7e07995175b71eb04bdbb89"
SEED_SHA256 = "18c72669105f486bf54a2665bd74d1ff952ce2eeb39b28a7b30d5ce8d5d2f5f1"
LEGACY_UNBOUND_SHA256 = "295bfef9b2681193e3a9cc085c479a960f87de0131abfbdfacb676479bdb2aa5"
PROJECT_LOCK_SHA256 = "e7a43fe0509fe853b18e487d36d230b14a0ba856f0f6c745ac33fd7346ac71b7"
ANTECEDENT_SHA256 = "dab2a3282b4d4c632d4e0260cc364f397b567f108dbf6480db5d1553a41a9221"
SEED_HINTS_SHA256 = "4de8e250dbafcb80b65de3b6443a0800fa7366b0ace826c72087c28452db8ef3"


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _cp_model_proto_bytes(value: object) -> bytes:
    message = cp_model_pb2.CpModelProto()
    text_format.Parse(str(value), message)
    return message.SerializeToString(deterministic=True)


def _solution_hint_proto_bytes(value: object) -> bytes:
    message = cp_model_pb2.PartialVariableAssignment()
    text_format.Parse(str(value), message)
    return message.SerializeToString(deterministic=True)


@pytest.fixture(scope="module")
def gate() -> ModuleType:
    return _load_module("_test_w0_d6_gate", GATE_PATH)


@pytest.fixture(scope="module")
def runner() -> ModuleType:
    return _load_module("_test_w0_d6_runner", RUNNER_PATH)


@pytest.fixture(scope="module")
def pinned_inputs() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    missing = [path for path in (STRICT_PATH, FRAMEWORK_PATH, SEED_PATH) if not path.is_file()]
    if missing:
        pytest.skip(f"external W0 D6 research inputs unavailable: {missing}")
    paths_and_hashes = (
        (STRICT_PATH, STRICT_SHA256),
        (FRAMEWORK_PATH, FRAMEWORK_SHA256),
        (SEED_PATH, SEED_SHA256),
    )
    decoded: list[dict[str, object]] = []
    for path, expected_sha256 in paths_and_hashes:
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected_sha256
        value = json.loads(raw)
        assert type(value) is dict
        decoded.append(value)
    return decoded[0], decoded[1], decoded[2]


def test_exact_inputs_rebuild_one_self_contained_d6_antecedent(
    gate: ModuleType,
    pinned_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    antecedent = gate.build_d6_antecedent(*pinned_inputs)

    assert hashlib.sha256(SEED_PATH.read_bytes()).hexdigest() == SEED_SHA256
    assert antecedent["schema"] == "w0_d6_antecedent_v2"
    assert antecedent["protocol"] == {
        "cohort": "w0_d6_swap_v3",
        "class_allocation_profile": "d6_6b_d9_6g_swap_v1",
        "antecedent_schema": "w0_d6_antecedent_v2",
        "config_payload_schema": "w0_d6_run_config_v3",
        "receipt_payload_schema": "w0_d6_receipt_payload_v3",
        "replay_receipt_schema": "w0_d6_replay_receipt_v3",
        "project_lock_sha256": PROJECT_LOCK_SHA256,
    }
    assert antecedent["class_transfer"] == {
        "profile": "d6_6b_d9_6g_swap_v1",
        "moves": [
            {"from": "D6", "to": "D9", "class": "6B", "count": 1},
            {"from": "D9", "to": "D6", "class": "6G", "count": 1},
        ],
    }
    assert antecedent["attachment_scope"] == "all_legal_d6_slots"
    assert antecedent["local_bounds"] == {"x_min": 14, "x_max": 41, "y_min": 28, "y_max": 41}
    assert antecedent["class_counts"] == {
        "3L": 7,
        "3O3": 3,
        "5L": 2,
        "5O2": 2,
        "6B": 0,
        "6G": 3,
    }
    assert antecedent["expected_totals"] == {
        "bodies": 17,
        "active_inputs": 23,
        "active_outputs": 25,
    }
    assert {
        tuple(tile["tile"]): tile["type_counts"]
        for tile in antecedent["tiles"]
    } == {
        (1, 2): {"3": 5, "5": 3, "6": 1},
        (2, 2): {"3": 5, "5": 1, "6": 2},
    }
    class_ledger = antecedent["class_ledger"]
    assert class_ledger["class_order"] == [
        "3I2",
        "3L",
        "3O2",
        "3O3",
        "5L",
        "5O2",
        "6B",
        "6F",
        "6G",
    ]
    assert class_ledger["d6"]["before"]["totals"] == {
        "bodies": 17,
        "active_inputs": 25,
        "active_outputs": 25,
    }
    assert class_ledger["d6"]["after"]["totals"] == antecedent["expected_totals"]
    assert class_ledger["d6"]["modeled_state"] == "after"
    assert class_ledger["d9"]["before"]["totals"] == {
        "bodies": 24,
        "active_inputs": 30,
        "active_outputs": 24,
    }
    assert class_ledger["d9"]["after"]["totals"] == {
        "bodies": 24,
        "active_inputs": 32,
        "active_outputs": 24,
    }
    assert (
        class_ledger["d9"]["role"]
        == "arithmetic_compensation_only_not_geometrically_modeled"
    )
    expected_global = {
        "3I2": 6,
        "3L": 109,
        "3O2": 6,
        "3O3": 11,
        "5L": 32,
        "5O2": 17,
        "6B": 3,
        "6F": 3,
        "6G": 32,
    }
    assert class_ledger["global"] == {
        "before": expected_global,
        "after": expected_global,
        "conserved": True,
    }
    for class_name in class_ledger["class_order"]:
        assert (
            class_ledger["d6"]["before"]["class_counts"][class_name]
            + class_ledger["d9"]["before"]["class_counts"][class_name]
            == class_ledger["d6"]["after"]["class_counts"][class_name]
            + class_ledger["d9"]["after"]["class_counts"][class_name]
        )
    for macrocell in ("d6", "d9"):
        for state in ("before", "after"):
            class_counts = class_ledger[macrocell][state]["class_counts"]
            assert class_ledger[macrocell][state]["totals"] == {
                "bodies": sum(class_counts.values()),
                "active_inputs": sum(
                    count * antecedent["class_catalog"][class_name]["input_count"]
                    for class_name, count in class_counts.items()
                    if count
                ),
                "active_outputs": sum(
                    count * antecedent["class_catalog"][class_name]["output_count"]
                    for class_name, count in class_counts.items()
                    if count
                ),
            }
    assert len(antecedent["seed_hints"]) == 17
    assert antecedent["seed_hint_policy"] == "add_hint_only_never_constraint"
    assert antecedent["cycle"]["attachment_slots"] == [
        {"cycle": [x, 29], "branch": [x, 30]}
        for x in range(14, 42)
    ]
    assert (
        hashlib.sha256(canonical_json_bytes(antecedent["seed_hints"])).hexdigest()
        == SEED_HINTS_SHA256
    )
    assert "tile_class_counts" not in antecedent
    assert LEGACY_UNBOUND_SHA256 not in canonical_json_bytes(antecedent).decode("utf-8")
    assert hashlib.sha256(canonical_json_bytes(antecedent)).hexdigest() == ANTECEDENT_SHA256


def test_routing_pattern_catalog_matches_strict_directed_incidence(gate: ModuleType) -> None:
    patterns = gate.build_legal_routing_patterns()
    ground = patterns["ground"]
    elevated = patterns["elevated"]

    assert len(ground) == 44
    assert len(elevated) == 4
    assert len({pattern["name"] for pattern in ground + elevated}) == 48
    assert sum(pattern["component"] == "belt" for pattern in ground) == 12
    assert sum(pattern["component"] == "splitter" for pattern in ground) == 16
    assert sum(pattern["component"] == "merger" for pattern in ground) == 16
    for pattern in ground + elevated:
        assert set(pattern["in_dirs"]).isdisjoint(pattern["out_dirs"])
    for pattern in elevated:
        assert pattern["out_dirs"] == [gate.OPPOSITE[pattern["in_dirs"][0]]]
    assert patterns["crossing"] == (
        "perpendicular_ground_and_elevated_straights_without_transfer"
    )


def test_front_geometry_is_recomputed_from_body_cell_and_direction(gate: ModuleType) -> None:
    assert gate.compute_active_front(
        (20, 31),
        {"body_cell": [2, 1], "direction": "E"},
    ) == (23, 32)
    assert gate.compute_active_front(
        (20, 31),
        {"body_cell": [0, 0], "direction": "S"},
    ) == (20, 30)


def test_exact_model_keeps_seed_as_hints_and_allows_cross_layer_edges(
    gate: ModuleType,
    pinned_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    antecedent = gate.build_d6_antecedent(*pinned_inputs)
    state = gate._build_exact_model(antecedent)
    proto = state.model.Proto()

    assert state.model.Validate() == ""
    assert len(state.candidates) == 2_532
    assert len(proto.solution_hint.vars) == 17
    assert list(proto.solution_hint.values) == [1] * 17
    hint_indices = set(proto.solution_hint.vars)
    assert all(proto.variables[index].name.startswith("seed_anchor_hint_") for index in hint_indices)
    candidate_by_index = {
        candidate.select.Index(): candidate
        for candidate in state.candidates
    }
    expected_classes_by_type = {
        3: {"3L", "3O3"},
        5: {"5L", "5O2"},
        6: {"6B", "6G"},
    }
    for hint_index, hint_variable_index in enumerate(proto.solution_hint.vars):
        defining_constraints = [
            constraint
            for constraint in proto.constraints
            if constraint.has_linear() and hint_variable_index in constraint.linear.vars
        ]
        assert len(defining_constraints) == 1
        definition = defining_constraints[0].linear
        assert list(definition.domain) == [0, 0]
        coefficients = dict(zip(definition.vars, definition.coeffs, strict=True))
        hint_coefficient = coefficients[hint_variable_index]
        assert abs(hint_coefficient) == 1
        candidate_indices = set(coefficients) - {hint_variable_index}
        assert candidate_indices
        assert {
            coefficients[index]
            for index in candidate_indices
        } == {-hint_coefficient}
        matching_candidates = [candidate_by_index[index] for index in candidate_indices]
        raw_hint = antecedent["seed_hints"][hint_index]
        assert {candidate.class_name for candidate in matching_candidates} == (
            expected_classes_by_type[raw_hint["type"]]
        )
        assert all(candidate.tile == tuple(raw_hint["tile"]) for candidate in matching_candidates)
        assert all(
            candidate.anchor == tuple(raw_hint["anchor"])
            for candidate in matching_candidates
        )
        assert all(
            tuple(raw_hint["anchor"]) in candidate.body_cells
            for candidate in matching_candidates
        )

    normal_without_hints = type(proto)()
    normal_without_hints.copy_from(proto)
    normal_without_hints.clear_solution_hint()
    with monkeypatch.context() as patch:
        patch.setattr(gate.cp_model.CpModel, "add_hint", lambda _model, _variable, _value: None)
        no_hint_state = gate._build_exact_model(antecedent)
    assert no_hint_state.model.Validate() == ""
    assert (
        _cp_model_proto_bytes(normal_without_hints)
        == _cp_model_proto_bytes(no_hint_state.model.Proto())
    )

    before_swap = copy.deepcopy(antecedent)
    before_swap["class_counts"] = {
        class_name: antecedent["class_ledger"]["d6"]["before"]["class_counts"][class_name]
        for class_name in antecedent["class_counts"]
    }
    before_swap["expected_totals"] = antecedent["class_ledger"]["d6"]["before"]["totals"]
    before_state = gate._build_exact_model(before_swap)
    swap_bytes = canonical_json_bytes(antecedent)
    before_swap_bytes = canonical_json_bytes(before_swap)
    seed_hint_bytes = canonical_json_bytes(antecedent["seed_hints"])
    assert before_swap_bytes != swap_bytes
    assert hashlib.sha256(before_swap_bytes).digest() != hashlib.sha256(swap_bytes).digest()
    assert canonical_json_bytes(before_swap["seed_hints"]) == seed_hint_bytes
    assert hashlib.sha256(seed_hint_bytes).hexdigest() == SEED_HINTS_SHA256
    assert (
        _solution_hint_proto_bytes(before_state.model.Proto().solution_hint)
        == _solution_hint_proto_bytes(proto.solution_hint)
    )

    one_edge = next(
        (source, target)
        for _polarity, _from_layer, _to_layer, source, target in state.flow_vars
    )
    assert {
        (from_layer, to_layer)
        for polarity, from_layer, to_layer, source, target in state.flow_vars
        if polarity == "OUT" and (source, target) == one_edge
    } == {
        ("ground", "ground"),
        ("ground", "elevated"),
        ("elevated", "ground"),
        ("elevated", "elevated"),
    }


def test_framework_or_seed_semantic_drift_fails_before_model_build(
    gate: ModuleType,
    pinned_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    strict, framework, seed = pinned_inputs
    changed_d6 = copy.deepcopy(framework)
    changed_d6["macrocell_class_allocation_seed"]["D6"]["3L"] = 6
    changed_d6["macrocell_class_allocation_seed"]["D9"]["3L"] = 19
    with pytest.raises(gate.D6AntecedentError, match="D6 class allocation drifted"):
        gate.build_d6_antecedent(strict, changed_d6, seed)

    changed_d9 = copy.deepcopy(framework)
    changed_d9["macrocell_class_allocation_seed"]["D9"]["6G"] = 2
    changed_d9["macrocell_class_allocation_seed"]["D8"]["6G"] = 3
    with pytest.raises(gate.D6AntecedentError, match="D9 class allocation drifted"):
        gate.build_d6_antecedent(strict, changed_d9, seed)

    changed_elsewhere = copy.deepcopy(framework)
    changed_elsewhere["macrocell_class_allocation_seed"]["D1"]["3L"] += 1
    with pytest.raises(gate.D6AntecedentError, match="global class allocation drifted"):
        gate.build_d6_antecedent(strict, changed_elsewhere, seed)

    unknown_class = copy.deepcopy(framework)
    unknown_class["macrocell_class_allocation_seed"]["D1"]["unknown"] = 1
    with pytest.raises(gate.D6AntecedentError, match="unknown operation class"):
        gate.build_d6_antecedent(strict, unknown_class, seed)

    changed_global_count = copy.deepcopy(framework)
    changed_global_count["operation_classes"]["3I2"]["count"] = 5
    with pytest.raises(gate.D6AntecedentError, match="3I2 global count drifted"):
        gate.build_d6_antecedent(strict, changed_global_count, seed)

    changed_seed = copy.deepcopy(seed)
    d6_index = next(
        index
        for index, placement in enumerate(changed_seed["manufacturing_placements"])
        if placement["tile"] in ([1, 2], [2, 2])
    )
    changed_seed["manufacturing_placements"][d6_index]["size"] = [1, 1]
    with pytest.raises(gate.D6AntecedentError, match="invalid type/size"):
        gate.build_d6_antecedent(strict, framework, changed_seed)


def test_v2_antecedent_fail_closes_to_all_legal_attachment_scope(
    gate: ModuleType,
    pinned_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    antecedent = gate.build_d6_antecedent(*pinned_inputs)

    assert len(antecedent["cycle"]["attachment_slots"]) == 28
    assert [slot["cycle"][0] for slot in antecedent["cycle"]["attachment_slots"]] == list(
        range(14, 42)
    )
    with pytest.raises(
        gate.D6AntecedentError,
        match="requires attachment_scope=all_legal_d6_slots",
    ):
        gate.build_d6_antecedent(*pinned_inputs, attachment_scope="seed_narrow")


def test_producer_source_claim_is_recorded_as_rejected_not_binding(
    runner: ModuleType,
    pinned_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    seed = pinned_inputs[2]
    records = runner._rejected_producer_claims(seed, actual_seed_sha256=SEED_SHA256)

    assert records == [
        {
            "claim_path": "seed.validation_summary.source_sha256",
            "accepted_as_binding": False,
            "actual_seed_sha256": SEED_SHA256,
            "reason": (
                "producer-reported source identity is not an independent binding "
                "to the snapshotted seed bytes"
            ),
            "claimed_sha256": LEGACY_UNBOUND_SHA256,
            "matches_known_unbound_claim": True,
        }
    ]


def test_gate_source_stays_research_local_and_does_not_implement_h20() -> None:
    source = GATE_PATH.read_text(encoding="utf-8")

    assert "from src.models" not in source
    assert "from src.search" not in source
    assert "H20" not in source
    assert "AddHint" in source
    assert "full graph" not in source.lower()
