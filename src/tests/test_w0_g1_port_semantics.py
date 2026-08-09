"""W0 G1: the derived operation-class table is pinned against repository truth.

research-only.  The red line here is test 2: the class table this line computes
must equal ``src.models.port_binding.routing_visible_port_demands`` operation by
operation.  That assertion *is* the port-semantics enforcement clause of the line
charter in executable form -- if it ever fails, the batch stops.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
G1_DIR = PROJECT_ROOT / "docs" / "research" / "w0_front_aware_20260803"
for _path in (str(PROJECT_ROOT), str(G1_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import g1_port_semantics as sem  # noqa: E402
from src.models.port_binding import routing_visible_port_demands  # noqa: E402
from src.preprocess.operation_profiles import get_operation_port_profile  # noqa: E402

pytestmark = pytest.mark.evidence

#: (class_id, template, r_in, r_out, count) -- the nine mandatory classes.
GOLDEN_CLASS_TABLE = (
    ("3L", "manufacturing_3x3", 1, 1, 109),
    ("3O2", "manufacturing_3x3", 1, 2, 6),
    ("3O3", "manufacturing_3x3", 1, 3, 11),
    ("3I2", "manufacturing_3x3", 2, 1, 6),
    ("5L", "manufacturing_5x5", 1, 1, 32),
    ("5O2", "manufacturing_5x5", 1, 2, 17),
    ("6I3", "manufacturing_6x4", 3, 1, 32),
    ("6I4", "manufacturing_6x4", 4, 1, 3),
    ("6I5", "manufacturing_6x4", 5, 1, 3),
)

#: The eight reachable capability buckets and the classes each can serve.
GOLDEN_BUCKETS = {
    "M3_1i1o": ("3L",),
    "M3_1i2o+2i1o": ("3I2", "3L", "3O2"),
    "M3_1i3o+2i1o": ("3I2", "3L", "3O2", "3O3"),
    "M5_1i1o": ("5L",),
    "M5_1i2o": ("5L", "5O2"),
    "M6_3i1o": ("6I3",),
    "M6_4i1o": ("6I3", "6I4"),
    "M6_5i1o": ("6I3", "6I4", "6I5"),
}


def test_class_table_matches_golden_rows() -> None:
    """[1] Nine rows, 109/6/6/11 - 32/17 - 32/3/3, derived not transcribed."""
    actual = tuple(
        (row.class_id, row.template, row.r_in, row.r_out, row.count)
        for row in sem.CLASS_TABLE
    )
    assert actual == GOLDEN_CLASS_TABLE
    assert sum(row.count for row in sem.CLASS_TABLE) == 219


@pytest.mark.parametrize("row", sem.CLASS_TABLE, ids=lambda row: row.class_id)
def test_demands_agree_with_repo_binding_ssot(row: "sem.ClassRow") -> None:
    """[2, RED LINE] Every operation agrees with the repository demand SSOT.

    ``routing_visible_port_demands`` is what the binding subproblem actually
    enforces.  Deriving the same pair from the frozen rules independently and
    comparing is the enforcement clause: no external throughput table, no kind
    counts, no drift.
    """
    for operation in row.operations:
        assert routing_visible_port_demands(operation, frozenset()) == (
            row.r_in,
            row.r_out,
        ), operation
        assert get_operation_port_profile(operation).facility_type == row.template


def test_template_census_matches_frozen_instances() -> None:
    """[3] 132 / 49 / 38 bodies, cross-checked against the instance artifact."""
    summary = sem.summary()
    assert summary["bodies_by_template"] == {
        "manufacturing_3x3": 132,
        "manufacturing_5x5": 49,
        "manufacturing_6x4": 38,
    }
    assert summary["total_bodies"] == 219
    assert summary["body_area_cells"] == 3325
    assert summary["front_demand_cells"] == 574

    instances = json.loads(
        sem.DEFAULT_INSTANCES_PATH.read_text(encoding="utf-8")
    )
    rules = json.loads(sem.DEFAULT_RULES_PATH.read_text(encoding="utf-8"))
    census: dict[str, int] = {}
    for instance in instances:
        recipe = rules["recipes"].get(instance["operation_type"])
        if recipe is None:
            continue
        template = recipe["template"]
        if template in sem.MANUFACTURING_TEMPLATES:
            census[template] = census.get(template, 0) + 1
    assert census == summary["bodies_by_template"]


def test_table_follows_tampered_input_rather_than_a_hardcoded_answer(
    tmp_path: Path,
) -> None:
    """[4, NEGATIVE] Doubling a recipe's ticks halves its slot demand.

    Guards against the table quietly becoming a constant: the derivation must
    track the frozen input, so a mutated copy must produce a different table.
    ``packaging_battery`` is 15+10 units over 5 ticks = 3+2 = 5 input slots; at
    10 ticks it becomes 2+1 = 3 slots, which merges class 6I5 into 6I3.
    """
    rules = json.loads(sem.DEFAULT_RULES_PATH.read_text(encoding="utf-8"))
    assert rules["recipes"]["packaging_battery"]["ticks_per_cycle"] == 5
    rules["recipes"]["packaging_battery"]["ticks_per_cycle"] = 10
    tampered = tmp_path / "tampered_rules.json"
    tampered.write_text(json.dumps(rules), encoding="utf-8")

    table = sem.derive_class_table(tampered, sem.DEFAULT_INSTANCES_PATH)
    ids = {row.class_id: row.count for row in table}
    assert "6I5" not in ids, "tampered ticks must remove the 5-input class"
    assert ids["6I3"] == 35, "its three instances must land in the 3-input class"
    assert sum(ids.values()) == 219
    # And the untouched real table is unaffected.
    assert {row.class_id: row.count for row in sem.CLASS_TABLE}["6I5"] == 3


def test_capability_bucket_matrix_is_pinned() -> None:
    """[5] Eight live buckets, with the exact class set each one can serve.

    Not eleven: for a square the mode set is closed under swapping a pair's two
    sides, so "can fan out to n" and "can fan in from n" are one condition, and
    the blueprint's independent (o, i) parameterisation names three unreachable
    3x3 buckets.
    """
    actual = {
        bucket: tuple(sorted(classes))
        for bucket, classes in sem.BUCKET_SERVABLE.items()
    }
    assert actual == GOLDEN_BUCKETS
    assert len(sem.BUCKET_SERVABLE) == 8
    assert set(sem.EXTERNAL_BUCKET_ALIASES) == set(GOLDEN_BUCKETS)


def test_unreachable_blueprint_buckets_really_are_unreachable() -> None:
    """[5b] The three missing 3x3 buckets cannot be produced by any side profile."""
    reachable = set()
    for n_top in range(4):
        for n_bottom in range(4):
            for n_left in range(4):
                for n_right in range(4):
                    servable = sem.servable_classes_for_side_counts(
                        "manufacturing_3x3",
                        sem.CLASS_TABLE,
                        (
                            (n_top, n_bottom),
                            (n_bottom, n_top),
                            (n_right, n_left),
                            (n_left, n_right),
                        ),
                    )
                    if servable:
                        reachable.add(tuple(sorted(servable)))
    # "serves 3O2 but not 3I2" and "serves 3I2 but not 3O2" are both impossible.
    assert ("3L", "3O2") not in reachable
    assert ("3I2", "3L") not in reachable
    assert len(reachable) == 3


def test_class_ids_map_onto_the_external_document_names() -> None:
    """[5c] Document 17's 6G / 6F / 6B are this line's 6I3 / 6I4 / 6I5."""
    assert sem.EXTERNAL_CLASS_ALIASES["6I3"] == "6G"
    assert sem.EXTERNAL_CLASS_ALIASES["6I4"] == "6F"
    assert sem.EXTERNAL_CLASS_ALIASES["6I5"] == "6B"
    assert set(sem.EXTERNAL_CLASS_ALIASES) == {row.class_id for row in sem.CLASS_TABLE}
