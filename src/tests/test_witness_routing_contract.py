from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
from pathlib import Path
import random

import pytest

from scripts.cleanroom_strict.validate_layout import _best_empty_rectangle


ROOT = Path(__file__).resolve().parents[2]
OBJECTIVE = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.objective_audit"
)
CONTRACT = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.strict_contract"
)

ObjectiveAuditError = OBJECTIVE.ObjectiveAuditError
audit_witness_objective = OBJECTIVE.audit_witness_objective
extract_body_cells = OBJECTIVE.extract_body_cells
maximum_empty_rectangle = OBJECTIVE.maximum_empty_rectangle

EXPECTED_CANDIDATE_COUNTS = CONTRACT.EXPECTED_CANDIDATE_COUNTS
EXPECTED_RECONCILIATION = CONTRACT.EXPECTED_RECONCILIATION
EXPECTED_SHA256 = CONTRACT.EXPECTED_SHA256
InputContractError = CONTRACT.InputContractError
assert_mode_front_parity = CONTRACT.assert_mode_front_parity
candidate_front_cell = CONTRACT.candidate_front_cell
load_and_reconcile = CONTRACT.load_and_reconcile
load_document = CONTRACT.load_document
strict_json_loads = CONTRACT.strict_json_loads


@pytest.fixture(scope="module")
def reconciled_inputs():
    return load_and_reconcile(ROOT)


def test_real_inputs_reconcile_to_independent_counts(reconciled_inputs) -> None:
    bundle, reconciliation = reconciled_inputs
    assert reconciliation.counts() == EXPECTED_RECONCILIATION
    assert dict(reconciliation.candidate_counts) == EXPECTED_CANDIDATE_COUNTS
    assert dict(reconciliation.hashes) == EXPECTED_SHA256
    assert bundle.hashes == EXPECTED_SHA256


def test_pinned_loader_rejects_hash_drift_before_parsing(tmp_path: Path) -> None:
    path = tmp_path / "input.json"
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(InputContractError, match="SHA-256 mismatch"):
        load_document(path, label="test", expected_sha256="0" * 64)


@pytest.mark.parametrize(
    "payload, message",
    [
        (b'{"a":1,"a":2}', "duplicate JSON object key"),
        (b'{"a":NaN}', "non-finite JSON number"),
        (b"\xff", "not UTF-8"),
    ],
)
def test_strict_json_parser_fails_closed(payload: bytes, message: str) -> None:
    with pytest.raises(InputContractError, match=message):
        strict_json_loads(payload, label="fixture")


def test_mode_front_parity_uses_candidate_identity_semantics(reconciled_inputs) -> None:
    bundle, _ = reconciled_inputs
    strict = bundle.strict_instance.value
    pool = bundle.candidate_poses.value["facility_pools"]["manufacturing_3x3"]
    pose = deepcopy(next(candidate for candidate in pool if candidate["pose_params"]["port_mode"] == "TB"))
    assert_mode_front_parity("manufacturing_3x3", pose, strict)
    first_port = pose["input_port_cells"][0]
    original = candidate_front_cell(first_port)
    assert original == (first_port["x"], first_port["y"])

    # Re-applying the direction step reproduces the historical double-offset bug.
    first_port["y"] += 1
    with pytest.raises(InputContractError, match="fronts differ"):
        assert_mode_front_parity("manufacturing_3x3", pose, strict)


def test_load_document_rejects_duplicate_keys_even_with_matching_hash(tmp_path: Path) -> None:
    payload = b'{"a":1,"a":2}'
    path = tmp_path / "duplicate.json"
    path.write_bytes(payload)
    with pytest.raises(InputContractError, match="duplicate JSON object key"):
        load_document(
            path,
            label="duplicate",
            expected_sha256=hashlib.sha256(payload).hexdigest(),
        )


def test_prefix_sum_exhaustive_matches_strict_histogram() -> None:
    rng = random.Random(20260720)
    for _ in range(12):
        occupied = {
            (x, y)
            for x in range(10)
            for y in range(9)
            if rng.random() < 0.23
        }
        actual = maximum_empty_rectangle(10, 9, occupied, minimum_side=2)
        expected = _best_empty_rectangle(10, 9, occupied, minimum_side=2)
        assert (
            actual.x,
            actual.y,
            actual.width,
            actual.height,
            actual.area,
            actual.min_side,
        ) == (
            expected["x"],
            expected["y"],
            expected["width"],
            expected["height"],
            expected["area"],
            expected["min_side"],
        )


def test_prefix_sum_exhaustive_matches_tiny_complete_oracle() -> None:
    width = 4
    height = 3
    cells = tuple((x, y) for y in range(height) for x in range(width))
    for mask in range(1 << len(cells)):
        occupied = {cell for index, cell in enumerate(cells) if mask & (1 << index)}
        for minimum_side in (1, 2):
            best = (0, 0, 0, 0, 0, 0)
            best_key = (0, 0, 0, 0, 0, 0)
            for y in range(height):
                for x in range(width):
                    for rect_height in range(minimum_side, height - y + 1):
                        for rect_width in range(minimum_side, width - x + 1):
                            rectangle = {
                                (cell_x, cell_y)
                                for cell_y in range(y, y + rect_height)
                                for cell_x in range(x, x + rect_width)
                            }
                            if rectangle & occupied:
                                continue
                            area = rect_width * rect_height
                            min_side = min(rect_width, rect_height)
                            key = (area, min_side, -y, -x, rect_width, rect_height)
                            if key > best_key:
                                best_key = key
                                best = (x, y, rect_width, rect_height, area, min_side)
            actual = maximum_empty_rectangle(width, height, occupied, minimum_side)
            assert (
                actual.x,
                actual.y,
                actual.width,
                actual.height,
                actual.area,
                actual.min_side,
            ) == best


def _tiny_instance() -> dict:
    return {
        "grid": {"width": 8, "height": 8},
        "objective": {"minimum_side": 2, "body_cells_only": True},
        "facility_templates": {
            "machine": {"modes": [{"id": "fixed", "body": {"width": 2, "height": 2}}]},
            "power_pole": {"modes": [{"id": "fixed", "body": {"width": 1, "height": 1}}]},
            "storage_box": {"modes": [{"id": "fixed", "body": {"width": 2, "height": 1}}]},
        },
        "required_instances": [{"id": "machine_001", "template": "machine"}],
        "repeatable_auxiliaries": ["power_pole", "storage_box"],
    }


def _placement(instance_id: str, template: str, x: int, y: int) -> dict:
    return {
        "instance_id": instance_id,
        "template": template,
        "mode": "fixed",
        "anchor": {"x": x, "y": y},
        "port_bindings": {},
    }


def test_objective_counts_mandatory_poles_and_boxes_but_ignores_routes_and_fronts() -> None:
    instance = _tiny_instance()
    witness = {
        "required_placements": [_placement("machine_001", "machine", 0, 0)],
        "optional_placements": [
            _placement("pole_001", "power_pole", 4, 4),
            _placement("box_001", "storage_box", 6, 0),
        ],
        "route_components": [
            {"cell": {"x": 3, "y": 3}, "kind": "straight"},
            {"cell": {"x": 7, "y": 7}, "kind": "turn"},
        ],
    }
    width, height, minimum_side, occupied = extract_body_cells(instance, witness)
    assert occupied == {(0, 0), (0, 1), (1, 0), (1, 1), (4, 4), (6, 0), (7, 0)}
    computed = maximum_empty_rectangle(width, height, occupied, minimum_side)
    witness["claimed_objective"] = {
        "rectangle": {
            "x": computed.x,
            "y": computed.y,
            "width": computed.width,
            "height": computed.height,
        },
        "area": computed.area,
        "min_side": computed.min_side,
    }
    audit = audit_witness_objective(instance, witness)
    assert audit.body_cell_count == 7
    assert audit.score == computed.score

    changed_routes = deepcopy(witness)
    changed_routes["route_components"] = [{"cell": {"x": 2, "y": 2}, "kind": "cross"}]
    assert audit_witness_objective(instance, changed_routes).computed == audit.computed


def test_objective_audit_rejects_false_claim_and_body_overlap() -> None:
    instance = _tiny_instance()
    witness = {
        "required_placements": [_placement("machine_001", "machine", 0, 0)],
        "optional_placements": [],
        "route_components": [],
        "claimed_objective": {
            "rectangle": {"x": 2, "y": 0, "width": 6, "height": 8},
            "area": 47,
            "min_side": 6,
        },
    }
    with pytest.raises(ObjectiveAuditError, match="dimensions"):
        audit_witness_objective(instance, witness)

    witness["claimed_objective"] = {
        "rectangle": {"x": 0, "y": 0, "width": 8, "height": 8},
        "area": 64,
        "min_side": 8,
    }
    with pytest.raises(ObjectiveAuditError, match="contains a facility body"):
        audit_witness_objective(instance, witness)


def test_objective_extractor_fails_closed_on_optional_body_overlap() -> None:
    instance = _tiny_instance()
    witness = {
        "required_placements": [_placement("machine_001", "machine", 0, 0)],
        "optional_placements": [_placement("pole_001", "power_pole", 1, 1)],
    }
    with pytest.raises(ObjectiveAuditError, match="overlaps"):
        extract_body_cells(instance, witness)
