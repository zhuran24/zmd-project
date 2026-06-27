from __future__ import annotations

from pathlib import Path

from src.preprocess.material_skeleton import (
    build_material_connection_skeleton,
    material_skeleton_digest,
)
from src.search.topology_binding_guidance import (
    compute_operation_topology_weight,
    compute_topology_binding_order,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _skeleton() -> dict:
    return build_material_connection_skeleton(PROJECT_ROOT)


def _all_known_instance_ids(skeleton: dict) -> list[str]:
    ids: list[str] = []
    for group in skeleton["node_groups"]:
        ids.extend(str(instance_id) for instance_id in group.get("instance_ids", ()))
    return ids


def _first_instance(skeleton: dict, operation_type: str) -> str:
    for group in skeleton["node_groups"]:
        if str(group.get("operation_type")) == operation_type:
            ids = sorted(str(instance_id) for instance_id in group.get("instance_ids", ()))
            if ids:
                return ids[0]
    raise AssertionError(f"no placed instance for operation {operation_type}")


def test_binding_order_is_permutation_of_unique_inputs() -> None:
    skeleton = _skeleton()
    ids = _all_known_instance_ids(skeleton)
    assert ids, "skeleton should expose manufacturing instance ids"

    ordered = compute_topology_binding_order(skeleton, ids)

    assert sorted(ordered) == sorted(set(ids))
    assert len(ordered) == len(set(ids))
    assert len(ordered) == len(set(ordered))


def test_binding_order_is_deterministic() -> None:
    skeleton = _skeleton()
    ids = _all_known_instance_ids(skeleton)
    assert compute_topology_binding_order(skeleton, ids) == compute_topology_binding_order(
        skeleton, ids
    )


def test_binding_order_does_not_mutate_inputs() -> None:
    skeleton = _skeleton()
    digest_before = material_skeleton_digest(skeleton)
    ids = _all_known_instance_ids(skeleton)
    ids_snapshot = list(ids)

    compute_topology_binding_order(skeleton, ids)

    assert ids == ids_snapshot
    assert material_skeleton_digest(skeleton) == digest_before


def test_order_is_monotonically_non_increasing_in_operation_weight() -> None:
    skeleton = _skeleton()
    weights = compute_operation_topology_weight(skeleton)
    instance_to_operation: dict[str, str] = {}
    for group in skeleton["node_groups"]:
        operation_type = str(group["operation_type"])
        for instance_id in group.get("instance_ids", ()):
            instance_to_operation[str(instance_id)] = operation_type

    ordered = compute_topology_binding_order(skeleton, list(instance_to_operation))

    previous: tuple[int, int, int, int] | None = None
    for instance_id in ordered:
        weight = weights[instance_to_operation[instance_id]]
        if previous is not None:
            assert weight <= previous, f"{instance_id} weight {weight} > previous {previous}"
        previous = weight


def test_high_pool_operation_outranks_isolated_operation() -> None:
    skeleton = _skeleton()
    weights = compute_operation_topology_weight(skeleton)
    operations_with_instances = {
        str(group["operation_type"]): [str(i) for i in group.get("instance_ids", ())]
        for group in skeleton["node_groups"]
        if group.get("instance_ids")
    }
    ranked = sorted(
        operations_with_instances,
        key=lambda op: (weights[op], op),
    )
    low_operation = ranked[0]
    high_operation = ranked[-1]

    low_instance = operations_with_instances[low_operation][0]
    high_instance = operations_with_instances[high_operation][0]
    ordered = compute_topology_binding_order(skeleton, [low_instance, high_instance])
    if weights[high_operation] != weights[low_operation]:
        assert ordered.index(high_instance) < ordered.index(low_instance)


def test_unknown_ids_go_last_sorted() -> None:
    skeleton = _skeleton()
    known = _all_known_instance_ids(skeleton)[:3]
    unknown = ["zzz_unknown_b", "aaa_unknown_a"]
    ordered = compute_topology_binding_order(skeleton, known + unknown)

    tail = ordered[-2:]
    assert tail == ["aaa_unknown_a", "zzz_unknown_b"]
    for unknown_id in unknown:
        for known_id in known:
            assert ordered.index(known_id) < ordered.index(unknown_id)


def test_empty_input_returns_empty_output() -> None:
    assert compute_topology_binding_order(_skeleton(), []) == []


def test_operation_weights_reflect_shared_pools() -> None:
    skeleton = _skeleton()
    weights = compute_operation_topology_weight(skeleton)
    assert weights, "skeleton should yield per-operation weights"
    # Every weight is a 4-tuple of non-negative ints.
    for weight in weights.values():
        assert len(weight) == 4
        assert all(isinstance(component, int) and component >= 0 for component in weight)
    # At least one operation touches a shared (pool_exchangeable) commodity.
    assert any(weight[1] >= 1 for weight in weights.values())


def test_duplicate_input_ids_are_collapsed() -> None:
    skeleton = _skeleton()
    one_id = _all_known_instance_ids(skeleton)[0]
    ordered = compute_topology_binding_order(skeleton, [one_id, one_id, one_id])
    assert ordered == [one_id]


def test_real_topology_weight_anchor() -> None:
    skeleton = _skeleton()
    weights = compute_operation_topology_weight(skeleton)
    # Concrete pool_pressure anchors tied to the real canonical topology.  A
    # "pool_pressure always 0" / wrong-field regression breaks these, where the
    # self-referential ordering tests above would stay green.
    assert weights["grinder_dense_blue_iron"][0] == 8  # max-pressure operation
    assert weights["refinery_steel"][0] == 5  # steel_block producer chain
    assert weights["crusher_blue_iron"][0] == 4  # leaf operation
    # The steel_block-chain op and the max-pool grinder both outrank the leaf.
    refinery_id = _first_instance(skeleton, "refinery_steel")
    grinder_id = _first_instance(skeleton, "grinder_dense_blue_iron")
    crusher_id = _first_instance(skeleton, "crusher_blue_iron")
    ordered = compute_topology_binding_order(skeleton, [crusher_id, refinery_id, grinder_id])
    assert ordered.index(grinder_id) < ordered.index(crusher_id)
    assert ordered.index(refinery_id) < ordered.index(crusher_id)


def test_intra_operation_instances_are_ordered_ascending() -> None:
    skeleton = _skeleton()
    multi = next(
        (group for group in skeleton["node_groups"] if len(group.get("instance_ids", ())) >= 2),
        None,
    )
    assert multi is not None, "skeleton should have a multi-instance operation"
    first, second = sorted(str(instance_id) for instance_id in multi["instance_ids"])[:2]
    # Same operation => equal weight => tie-break must be instance_id ascending.
    assert compute_topology_binding_order(skeleton, [second, first]) == [first, second]
