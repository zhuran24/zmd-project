"""M4-D2 red tests: F5 query_liftable contract + BindingEmptyDomainAdapter.

Design anchors (orbit-lift design v2 §4 ④ + D2 recon):
- σ-relabel invariance: slot labels must not change the verdict.
- Context-dependence rejection is STRUCTURAL: LiftableScope physically lacks
  the blacklisted fields (selected_poses / cell_owner), so an adapter cannot
  peek at incumbent state even if it wants to.
- The demand-equality INFEASIBLE mode is anti-monotone and must NEVER be
  lifted: generic-hub groups always answer FEASIBLE.
- Routing-aware binding (EXACT_B1_ROUTING_AWARE_BINDING) makes domain
  emptiness incumbent-dependent → adapter refuses to lift entirely.
"""
from __future__ import annotations

import os
from unittest import mock

import pytest

from src.cuts.lifecycle import BState, GroupState
from src.cuts.oracles.pattern_nogood_oracle import (
    LiftableScope,
    build_liftable_scope,
)
from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES
from src.search.f5_binding_empty_domain_adapter import (
    BindingEmptyDomainAdapter,
    build_binding_empty_domain_adapter,
)


def _pick_exact_binding_op() -> str:
    """An operation with no generic hub slots but ≥1 required port slot —
    an empty port-cell pose then has an empty binding domain."""
    for op, profile in sorted(OPERATION_PORT_PROFILES.items()):
        if profile.generic_input_slots or profile.generic_output_slots:
            continue
        if sum(profile.input_slots.values()) + sum(profile.output_slots.values()) > 0:
            return op
    pytest.skip("no exact-binding operation with port slots in profiles")


def _pick_generic_hub_op() -> str:
    for op, profile in sorted(OPERATION_PORT_PROFILES.items()):
        if profile.generic_input_slots or profile.generic_output_slots:
            return op
    pytest.skip("no generic-hub operation in profiles")


def _scope(facility_pools) -> LiftableScope:
    return LiftableScope(
        facility_pools=facility_pools,
        canonical_rules={},
        instance_to_facility_type={"g_exact": "miner", "g_hub": "hub"},
        facility_templates={},
        group_demands={"g_exact": 2, "g_hub": 2},
        group_pose_domains={
            "g_exact": frozenset({"p_dead", "p_live"}),
            "g_hub": frozenset({"p_hub"}),
        },
        artifact_hashes={},
    )


def _dead_pose() -> dict:
    # no port cells at all → any profile requiring ports has an empty domain
    return {
        "pose_id": "p_dead",
        "anchor": {"x": 0, "y": 0},
        "occupied_cells": [[0, 0]],
        "input_port_cells": [],
        "output_port_cells": [],
    }


def _live_pose(op: str) -> dict:
    profile = OPERATION_PORT_PROFILES[op]
    n_in = sum(profile.input_slots.values())
    n_out = sum(profile.output_slots.values())
    return {
        "pose_id": "p_live",
        "anchor": {"x": 5, "y": 5},
        "occupied_cells": [[5, 5]],
        "input_port_cells": [
            {"cell": [4, 5 + i], "direction": "W"} for i in range(n_in)
        ],
        "output_port_cells": [
            {"cell": [6, 5 + i], "direction": "E"} for i in range(n_out)
        ],
    }


def _adapter(op_exact: str, op_hub: str) -> BindingEmptyDomainAdapter:
    return BindingEmptyDomainAdapter(
        group_operation_types={"g_exact": op_exact, "g_hub": op_hub}
    )


def test_empty_domain_literal_is_infeasible_and_sigma_invariant() -> None:
    op = _pick_exact_binding_op()
    hub = _pick_generic_hub_op()
    adapter = _adapter(op, hub)
    scope = _scope({"miner": [_dead_pose(), _live_pose(op)]})

    core_a = (("g_exact", 0, "p_dead"),)
    verdict_a, _ = adapter.query_liftable(core_a, scope, deadline_seconds=5.0)
    assert verdict_a == "INFEASIBLE"

    # σ-relabel invariance: slot label is irrelevant to the verdict.
    core_b = (("g_exact", 1, "p_dead"),)
    verdict_b, _ = adapter.query_liftable(core_b, scope, deadline_seconds=5.0)
    assert verdict_b == verdict_a


def test_live_domain_is_feasible() -> None:
    op = _pick_exact_binding_op()
    hub = _pick_generic_hub_op()
    adapter = _adapter(op, hub)
    scope = _scope({"miner": [_dead_pose(), _live_pose(op)]})
    verdict, _ = adapter.query_liftable(
        (("g_exact", 0, "p_live"),), scope, deadline_seconds=5.0
    )
    assert verdict == "FEASIBLE"


def test_generic_hub_group_never_lifts() -> None:
    """Recon R1: demand-equality INFEASIBLE is anti-monotone — a generic-hub
    literal must never produce a liftable INFEASIBLE, even with no port cells."""
    op = _pick_exact_binding_op()
    hub = _pick_generic_hub_op()
    adapter = _adapter(op, hub)
    scope = _scope({"hub": [dict(_dead_pose(), pose_id="p_hub")]})
    verdict, _ = adapter.query_liftable(
        (("g_hub", 0, "p_hub"),), scope, deadline_seconds=5.0
    )
    assert verdict == "FEASIBLE"


def test_routing_aware_binding_env_refuses_to_lift() -> None:
    """Recon R3: with RAB-SEP on, domain emptiness depends on the incumbent —
    the adapter must refuse to lift anything."""
    op = _pick_exact_binding_op()
    hub = _pick_generic_hub_op()
    adapter = _adapter(op, hub)
    scope = _scope({"miner": [_dead_pose()]})
    with mock.patch.dict(os.environ, {"EXACT_B1_ROUTING_AWARE_BINDING": "1"}):
        verdict, _ = adapter.query_liftable(
            (("g_exact", 0, "p_dead"),), scope, deadline_seconds=5.0
        )
    assert verdict == "FEASIBLE"


def test_unknown_group_contributes_no_verdict() -> None:
    op = _pick_exact_binding_op()
    hub = _pick_generic_hub_op()
    adapter = _adapter(op, hub)
    scope = _scope({"miner": [_dead_pose()]})
    verdict, _ = adapter.query_liftable(
        (("g_mystery", 0, "p_dead"),), scope, deadline_seconds=5.0
    )
    assert verdict == "FEASIBLE"


def test_liftable_scope_structurally_lacks_incumbent_fields() -> None:
    """Red test ⑦ (structural half): the projection object handed to adapters
    has no selected_poses / cell_owner / ghost fields at all — context-
    dependent verdicts are impossible to derive from it."""
    state = BState(
        groups={
            "g": GroupState(
                group_id="g",
                demand=1,
                pose_domain=frozenset({"p"}),
                selected_poses=["p"],  # incumbent — must NOT survive projection
            )
        }
    )
    state.cell_owner = {(1, 1): ("g", 0)}
    scope = build_liftable_scope(state)
    for blacklisted in ("selected_poses", "cell_owner", "ghost_rect", "ghost_cells"):
        assert not hasattr(scope, blacklisted)
    assert scope.group_demands == {"g": 1}
    assert scope.group_pose_domains == {"g": frozenset({"p"})}


def test_build_adapter_from_mandatory_groups() -> None:
    """Recon R4: group_id is the synthetic group::tpl::op::idx string — the
    factory must map it to the operation_type field, not parse the string."""
    groups = [
        {
            "group_id": "group::miner::mining::0",
            "facility_type": "miner",
            "operation_type": "mining",
            "count": 2,
        },
        {"group_id": "", "operation_type": "x"},  # malformed — skipped
    ]
    adapter = build_binding_empty_domain_adapter(groups)
    assert adapter._group_operation_types == {"group::miner::mining::0": "mining"}
