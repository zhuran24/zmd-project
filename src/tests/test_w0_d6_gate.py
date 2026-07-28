from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType

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
ANTECEDENT_SHA256 = "7dd634386b4c27a695a7115bd0dddf1c67556ab58923e9dfe526e5f7ee54e59f"


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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
    antecedent = gate.build_d6_antecedent(*pinned_inputs, attachment_scope="seed_narrow")

    assert antecedent["schema"] == "w0_d6_antecedent_v1"
    assert antecedent["attachment_scope"] == "seed_narrow"
    assert antecedent["local_bounds"] == {"x_min": 14, "x_max": 41, "y_min": 28, "y_max": 41}
    assert antecedent["class_counts"] == {
        "3L": 7,
        "3O3": 3,
        "5L": 2,
        "5O2": 2,
        "6B": 1,
        "6G": 2,
    }
    assert antecedent["expected_totals"] == {
        "bodies": 17,
        "active_inputs": 25,
        "active_outputs": 25,
    }
    assert len(antecedent["seed_hints"]) == 17
    assert antecedent["seed_hint_policy"] == "add_hint_only_never_constraint"
    assert [slot["cycle"][0] for slot in antecedent["cycle"]["attachment_slots"]] == [
        23,
        24,
        25,
        30,
        31,
        32,
        33,
        34,
        35,
        36,
        37,
    ]
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
) -> None:
    antecedent = gate.build_d6_antecedent(*pinned_inputs, attachment_scope="seed_narrow")
    state = gate._build_exact_model(antecedent)
    proto = state.model.Proto()

    assert state.model.Validate() == ""
    assert len(state.candidates) == 2_532
    assert len(proto.solution_hint.vars) == 17
    assert list(proto.solution_hint.values) == [1] * 17
    hint_indices = set(proto.solution_hint.vars)
    assert all(proto.variables[index].name.startswith("seed_anchor_hint_") for index in hint_indices)
    for constraint in proto.constraints:
        if not constraint.has_linear():
            continue
        involved_hints = hint_indices.intersection(constraint.linear.vars)
        if involved_hints:
            assert len(constraint.linear.vars) > 1

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
    changed_framework = copy.deepcopy(framework)
    changed_framework["macrocell_class_allocation_seed"]["D6"]["3L"] = 6
    with pytest.raises(gate.D6AntecedentError, match="class allocation drifted"):
        gate.build_d6_antecedent(strict, changed_framework, seed)

    changed_seed = copy.deepcopy(seed)
    changed_seed["eligible_attachment_slots_by_tile"]["1,2"][0]["cycle"][0] += 1
    with pytest.raises(gate.D6AntecedentError, match="attachment slots drifted"):
        gate.build_d6_antecedent(strict, framework, changed_seed)


def test_all_legal_variant_changes_only_attachment_scope(
    gate: ModuleType,
    pinned_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    narrow = gate.build_d6_antecedent(*pinned_inputs, attachment_scope="seed_narrow")
    widened = gate.build_d6_antecedent(*pinned_inputs, attachment_scope="all_legal_d6_slots")

    assert len(widened["cycle"]["attachment_slots"]) == 28
    assert [slot["cycle"][0] for slot in widened["cycle"]["attachment_slots"]] == list(range(14, 42))
    narrow_without_scope = copy.deepcopy(narrow)
    widened_without_scope = copy.deepcopy(widened)
    narrow_without_scope["attachment_scope"] = None
    widened_without_scope["attachment_scope"] = None
    narrow_without_scope["cycle"]["attachment_slots"] = None
    widened_without_scope["cycle"]["attachment_slots"] = None
    assert narrow_without_scope == widened_without_scope


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
