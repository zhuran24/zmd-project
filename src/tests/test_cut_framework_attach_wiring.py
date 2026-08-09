"""M3-4 LBBD ↔ cut-framework wiring (P1.3) — B5a typed orchestration cut-over.

Covers the glue only — oracle math has test_family_region_capacity, the typed
master translation has test_step_8_apply_to_master / test_stage_b_contracts:

- env gate: EXACT_CUT_FRAMEWORK_ATTACH default-off → zero framework work.
- typed full chain: real oracle → cut_to_envelope_v1 → validate_and_compile_cut
  → step-7 attest → resolver → typed step_8, on a REAL bound-region master with
  a production-dependency-aligned state.
- three-way telemetry (attached / shadow_validated / rejected-by-stage).
- BState assembly from a real solved coordinate master (field fidelity).
- §6 differential anchors: orchestration ≡ direct chain (byte-equal master
  mutation); ShadowValidated / CutRejection arms cause ZERO master mutation.

The same env is registered in the certified unsafe map, so certified runs with
it enabled fail-close at the run entrance (red tests live in
test_ghost_anchor_filter / test_v62_candidate_frontier_contract patterns).

B5a note: the typed attach requires a real master (the resolver reads
u_vars/_ghost_domains/_coordinate_delegate/pools) and a state whose
artifact_hashes are the 8 production dependencies — the historical _SpyMaster +
synthetic BState are kept only for the env-gate / budget / state-assembly tests
that never reach the typed chain.
"""
from __future__ import annotations

import dataclasses
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Tuple
from unittest import mock

import pytest
from ortools.sat.python import cp_model

from src.models.cut_manager import CutManager
from src.models.master_model import MasterPlacementModel
from src.search.benders_loop import ExactSearchSession, LBBDController


# ---- synthetic fixtures (env-gate / budget / state-assembly only) -----------


INSTANCE_TO_FT = {"boundary_io": "boundary_storage_port"}
FACILITY_TEMPLATES = {
    "boundary_storage_port": {
        "placement_rule": "left_or_bottom_boundary",
        "dimensions": {"w": 1, "h": 3},
    },
}
CANONICAL_RULES = {"facility_templates": FACILITY_TEMPLATES}


def _boundary_overflow_state():
    """Synthetic BState for the env-gate/budget tests that never reach the
    typed chain (its artifact_hashes are NOT the production dependency set)."""
    from src.cuts.lifecycle import BState, GroupState

    poses = [
        {
            "pose_id": f"mock_p_{i}",
            "anchor": {"x": 0, "y": i},
            "occupied_cells": [[0, i % 68], [0, (i + 1) % 68], [0, (i + 2) % 68]],
            "input_port_cells": [],
            "output_port_cells": [],
        }
        for i in range(46)
    ]
    return BState(
        groups={
            "boundary_io": GroupState(
                "boundary_io",
                demand=46,
                pose_domain=frozenset(p["pose_id"] for p in poses),
            ),
        },
        ghost_rect=(10, 0, 2, 2),
        ghost_cells=frozenset({(10, 0), (11, 0), (10, 1), (11, 1)}),
        exterior_blocks=frozenset(),
        artifact_hashes={"canonical_rules.json": "h1"},
        available_oracle_versions=frozenset(
            {"region_capacity_v1", "shape_packing_hall_v1"}
        ),
        canonical_rules=CANONICAL_RULES,
        facility_templates=FACILITY_TEMPLATES,
        instance_to_facility_type=INSTANCE_TO_FT,
        candidate_placements={
            "facility_pools": {"boundary_storage_port": poses}
        },
    )


class _SpyMaster:
    def __init__(self) -> None:
        self.build_stats: Dict[str, Any] = {}


_GHOST_U_VAR_SENTINEL = object()


def _mock_ghost_context():
    """(rect_idx, u_var, anchor, ghost_cells) matching _boundary_overflow_state."""
    return (
        0,
        _GHOST_U_VAR_SENTINEL,
        {"x": 10, "y": 0},
        {(10, 0), (11, 0), (10, 1), (11, 1)},
    )


def _controller(master: Any, *, session: Any = None) -> LBBDController:
    ckpt = Path(tempfile.mkdtemp(prefix="zmd_cfw_"))
    cm = CutManager(checkpoint_dir=ckpt, solve_mode="certified_exact")
    return LBBDController(
        master=master,
        cut_manager=cm,
        project_root=ckpt.parent,
        solve_mode="certified_exact",
        session=session,
    )


def _bare_session(**overrides: Any) -> ExactSearchSession:
    """A minimally-populated ExactSearchSession for exercising the bundle cache
    directly.  Only the bundle accessor + cache slot are touched, so the heavy
    ``create()`` path (which reads 45MB of frozen artifacts) is bypassed and the
    unused core/data fields are left as dummies."""
    fields: Dict[str, Any] = dict(
        project_root=Path("/tmp/zmd_bare_session"),
        solve_mode="certified_exact",
        instances=[],
        facility_pools={},
        rules={},
        artifact_hashes={},
        master_search_profile="test",
        core=None,
        core_build_seconds=0.0,
    )
    fields.update(overrides)
    return ExactSearchSession(**fields)


def _build_miner_master() -> MasterPlacementModel:
    instances = [
        {
            "instance_id": f"miner_{i:03d}",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        }
        for i in (1, 2)
    ]
    pools = {
        "miner": [
            {
                "pose_id": f"pose_{tag}",
                "anchor": {"x": x, "y": 0},
                "occupied_cells": [[x, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
            for tag, x in (("left", 0), ("mid", 2), ("right", 4))
        ]
    }
    rules = {
        "globals": {"grid": {"width": 5, "height": 1}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules, skip_power_coverage=True
    )
    return MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))


# ---- typed bound-region world (real master + production-dep state) -----------


def _bound_region_world(
    ghost_rect: Tuple[int, int, int, int] = (0, 0, 3, 1),
) -> Tuple[Any, Any, str]:
    """Real bound-region master + a consistent, production-dependency-aligned
    BState (source_digest set).  Reuses the proven test_stage_b_contracts
    fixtures so the typed chain compiles + resolves end-to-end."""
    from src.cuts import lifecycle
    from src.tests.cuts import test_stage_b_contracts as contracts

    seed = contracts._bound_region_sources(
        lifecycle.BState, lifecycle.GroupState, ghost_rect=ghost_rect
    )
    master = contracts._build_bound_region_master(MasterPlacementModel, seed)
    group_id = str(master._group_id_by_instance["boundary_000"])
    sources = contracts._bound_region_sources(
        lifecycle.BState, lifecycle.GroupState, ghost_rect=ghost_rect, group_id=group_id
    )
    sources["state"].source_digest = lifecycle.compute_source_digest(sources["state"])
    return master, sources["state"], group_id


def _direct_apply_f1(master: Any, state: Any) -> None:
    """Run the direct typed chain for the single F1 cut of ``state`` onto
    ``master`` (envelope → single entry → step-7 → resolver → typed step_8)."""
    from src.cuts import frozen_artifacts, lifecycle, state_snapshot
    from src.cuts.lifecycle import (
        _resolve_model_scope_binding,
        step_7_evaluate_cut,
        step_8_apply_to_master,
    )
    from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
    from src.cuts.typed_platform import (
        CompiledCut,
        build_production_registry,
        cut_to_envelope_v1,
        validate_and_compile_cut,
    )
    from src.tests.cuts import test_stage_b_contracts as contracts

    sources = {
        "artifact_hashes": state.artifact_hashes,
        "canonical_rules": state.canonical_rules,
        "candidate_placements": state.candidate_placements,
        "facility_templates": state.facility_templates,
        "instance_to_facility_type": state.instance_to_facility_type,
        "state": state,
    }
    bundle = contracts._build_bundle(frozen_artifacts.build_frozen_artifact_bundle, sources)
    snapshot = state_snapshot.build_validated_state_snapshot(state, bundle)
    cut = generate_region_capacity_cuts(state, state.canonical_rules)[0]
    compiled = validate_and_compile_cut(
        cut_to_envelope_v1(cut), snapshot, build_production_registry()
    )
    assert isinstance(compiled, CompiledCut)
    assert step_7_evaluate_cut(compiled, snapshot) is True
    binding = _resolve_model_scope_binding(compiled.plan.model_scope, snapshot, master)
    step_8_apply_to_master(compiled, master, scope_binding=binding)


def _suppress_f6():
    """Context patch: keep the F6 (shape_packing_hall) oracle silent so a
    bound-region attach round processes only the F1 cut."""
    return mock.patch(
        "src.cuts.oracles.shape_packing_hall_oracle.compute_sot_region_demand_overrides",
        return_value={},
    )


# ---- env gate ---------------------------------------------------------------


def test_attach_disabled_by_default_does_no_framework_work() -> None:
    controller = _controller(_SpyMaster())
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
        with mock.patch.object(
            LBBDController,
            "_build_cut_framework_state",
            side_effect=AssertionError("state builder must not run when disabled"),
        ):
            assert (
                controller._maybe_attach_framework_cuts(
                    trigger="binding_infeasible", iteration=1
                )
                == 0
            )


# ---- typed full chain on a real bound-region master -------------------------


def test_full_chain_generates_validates_and_attaches() -> None:
    """Real oracle → typed single entry → resolver → typed step_8 attaches an
    F1 region_capacity cut, with the B5a three-way telemetry taxonomy."""
    master, state, _group_id = _bound_region_world()
    controller = _controller(master)
    with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
        with mock.patch.object(
            LBBDController, "_build_cut_framework_state", return_value=state
        ):
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=7
            )
    assert attached >= 1
    stats = master.build_stats["cut_framework_attach_last"]
    assert stats["trigger"] == "binding_infeasible"
    assert stats["iteration"] == 7
    assert stats["attached"] == attached
    assert stats["attached_by_family"].get("region_capacity") == 1
    # A real region_capacity constraint reached the master.
    assert master.build_stats["coordinate_region_capacity_last_cut"] is not None
    assert master.build_stats.get("coordinate_framework_cut_count", 0) >= 1
    # New telemetry surface: shadow bucket + stage-keyed rejections.
    assert stats["shadow_validated"] == 0
    assert set(stats["rejected"]) >= {
        "adapter",
        "registry",
        "envelope",
        "scope",
        "proof",
        "plan",
        "attach_timing",
    }
    # Old 4-class taxonomy is gone.
    assert "integrity" not in stats["rejected"]
    assert "validator_missing" not in stats["rejected"]


def test_integrity_drift_cut_is_rejected_not_attached() -> None:
    """cert/oracle hash 漂移的 cut 必须被拒（外审 P0 回归）。

    In the typed path integrity is enforced by ``cut_to_envelope_v1`` (which
    calls ``validate_cut_integrity``): an oracle_cert_hash mismatch raises
    ValueError before the single entry, landing in the ``adapter`` bucket.
    """
    master, state, _group_id = _bound_region_world()
    controller = _controller(master)
    from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts

    real_cut = generate_region_capacity_cuts(state, state.canonical_rules)[0]
    tampered = dataclasses.replace(real_cut, oracle_cert_hash="0" * 64)

    with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
        with mock.patch.object(
            LBBDController, "_build_cut_framework_state", return_value=state
        ), mock.patch(
            "src.cuts.oracles.region_capacity_oracle.generate_region_capacity_cuts",
            return_value=[tampered],
        ), _suppress_f6():
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=7
            )
    stats = master.build_stats["cut_framework_attach_last"]
    assert attached == 0
    assert stats["rejected"]["adapter"] == 1
    assert "region_capacity" not in stats["attached_by_family"]
    assert "coordinate_region_capacity_last_cut" not in master.build_stats


def test_full_chain_no_overflow_attaches_nothing() -> None:
    """A disjoint ghost leaves the region capacity intact → the F1 oracle emits
    no cut → the typed chain attaches nothing."""
    master, _state, _group_id = _bound_region_world()
    # Disjoint-ghost state: no region overflow, so generate_region_capacity_cuts
    # returns [] (verified), and no framework cut can attach.
    _m2, disjoint_state, _gid = _bound_region_world(ghost_rect=(60, 60, 3, 1))
    controller = _controller(master)
    with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
        with mock.patch.object(
            LBBDController, "_build_cut_framework_state", return_value=disjoint_state
        ):
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=1
            )
    assert attached == 0
    stats = master.build_stats["cut_framework_attach_last"]
    assert "region_capacity" not in stats["attached_by_family"]
    assert "coordinate_region_capacity_last_cut" not in master.build_stats


# ---- budget -----------------------------------------------------------------


def test_attach_budget_exhausted_stops_emitting(monkeypatch) -> None:
    """M4-A budget gate: at EXACT_CUT_FRAMEWORK_ATTACH_BUDGET attached
    constraints the framework stops before generating anything."""
    from src.search.benders_loop import EXACT_CUT_FRAMEWORK_ATTACH_BUDGET

    # hermetic: 外部 shell 若设了合法 BUDGET 覆盖会假红(双审 codex LOW#1)
    monkeypatch.delenv("EXACT_CUT_FRAMEWORK_ATTACH_BUDGET", raising=False)
    spy = _SpyMaster()
    spy.build_stats["coordinate_framework_cut_count"] = (
        EXACT_CUT_FRAMEWORK_ATTACH_BUDGET
    )
    controller = _controller(spy)
    with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
        with mock.patch.object(
            LBBDController,
            "_build_cut_framework_state",
            side_effect=AssertionError("budget gate must fire before the state build"),
        ):
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=3
            )
    assert attached == 0
    stats = spy.build_stats["cut_framework_attach_last"]
    assert stats["budget_exhausted"] is True
    assert stats["budget"] == EXACT_CUT_FRAMEWORK_ATTACH_BUDGET
    assert stats["attached"] == 0


def test_attach_budget_env_override_stops_at_three_and_reports_budget(
    monkeypatch,
) -> None:
    """count=2 + budget=3 → exactly one F1 cut lands, then the loop breaks
    before the second generated cut; count=3 → budget exhausted pre-state."""
    master, state, _group_id = _bound_region_world()
    controller = _controller(master)
    master.build_stats["coordinate_framework_cut_count"] = 2
    monkeypatch.setenv("EXACT_CUT_FRAMEWORK_ATTACH", "1")
    monkeypatch.setenv("EXACT_CUT_FRAMEWORK_ATTACH_BUDGET", "3")
    with mock.patch.object(
        LBBDController, "_build_cut_framework_state", return_value=state
    ):
        attached = controller._maybe_attach_framework_cuts(
            trigger="binding_infeasible", iteration=4
        )
    assert attached == 1
    assert 2 + attached == 3
    stats = master.build_stats["cut_framework_attach_last"]
    assert stats["attached_by_family"] == {"region_capacity": 1}

    master.build_stats["coordinate_framework_cut_count"] = 3
    with mock.patch.object(
        LBBDController,
        "_build_cut_framework_state",
        side_effect=AssertionError("env budget gate must fire before state build"),
    ):
        assert (
            controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=5
            )
            == 0
        )
    stats = master.build_stats["cut_framework_attach_last"]
    assert stats["budget_exhausted"] is True
    assert stats["budget"] == 3


@pytest.mark.parametrize("raw_value", ["0", "-1", "abc", "5 junk"])
def test_attach_budget_resolver_rejects_invalid_values(
    monkeypatch, raw_value: str
) -> None:
    from src.search.benders_loop import _resolve_cut_framework_attach_budget

    monkeypatch.setenv("EXACT_CUT_FRAMEWORK_ATTACH_BUDGET", raw_value)
    with pytest.raises(
        ValueError,
        match=r"EXACT_CUT_FRAMEWORK_ATTACH_BUDGET.*expected a positive integer",
    ):
        _resolve_cut_framework_attach_budget()


def test_attach_budget_resolver_uses_default_when_env_unset(monkeypatch) -> None:
    from src.search.benders_loop import (
        EXACT_CUT_FRAMEWORK_ATTACH_BUDGET,
        _resolve_cut_framework_attach_budget,
    )

    monkeypatch.delenv("EXACT_CUT_FRAMEWORK_ATTACH_BUDGET", raising=False)
    assert _resolve_cut_framework_attach_budget() == 2000
    assert _resolve_cut_framework_attach_budget() == EXACT_CUT_FRAMEWORK_ATTACH_BUDGET


def test_attach_budget_resolver_empty_and_surrounding_whitespace(monkeypatch) -> None:
    from src.search.benders_loop import (
        EXACT_CUT_FRAMEWORK_ATTACH_BUDGET,
        _resolve_cut_framework_attach_budget,
    )

    monkeypatch.setenv("EXACT_CUT_FRAMEWORK_ATTACH_BUDGET", "")
    assert _resolve_cut_framework_attach_budget() == EXACT_CUT_FRAMEWORK_ATTACH_BUDGET
    monkeypatch.setenv("EXACT_CUT_FRAMEWORK_ATTACH_BUDGET", "   ")
    assert _resolve_cut_framework_attach_budget() == EXACT_CUT_FRAMEWORK_ATTACH_BUDGET
    monkeypatch.setenv("EXACT_CUT_FRAMEWORK_ATTACH_BUDGET", " 5 ")
    assert _resolve_cut_framework_attach_budget() == 5


def test_attach_entrance_propagates_invalid_budget_value(monkeypatch) -> None:
    """ATTACH=1 + 非法 BUDGET 时 ValueError 必须从入口传播(双审 codex LOW#3)。"""
    spy = _SpyMaster()
    controller = _controller(spy)
    monkeypatch.setenv("EXACT_CUT_FRAMEWORK_ATTACH", "1")
    monkeypatch.setenv("EXACT_CUT_FRAMEWORK_ATTACH_BUDGET", "not_an_int")
    with pytest.raises(
        ValueError, match=r"EXACT_CUT_FRAMEWORK_ATTACH_BUDGET"
    ):
        controller._maybe_attach_framework_cuts(
            trigger="binding_infeasible", iteration=1
        )


def test_framework_target_poses_resolves_groups_and_pose_ids() -> None:
    """Solution keys are instance-level; targets must be (group_id, pose_id)."""
    master = _build_miner_master()
    controller = _controller(master)
    group_id = str(master._group_id_by_instance["miner_001"])
    solution = {
        "miner_001": {"facility_type": "miner", "pose_idx": 0},
        "miner_002": {"facility_type": "miner", "pose_idx": 2},
        "ghost_pick": {"rect_idx": 3},
        "unknown_instance": {"facility_type": "miner", "pose_idx": 1},
    }
    targets = controller._framework_target_poses(solution)
    assert targets == sorted(
        [(group_id, "pose_left"), (group_id, "pose_right")]
    )


# ---- BState assembly from a real master --------------------------------------


def test_state_assembly_from_solved_coordinate_master() -> None:
    master = _build_miner_master()
    assert master.solve(time_limit_seconds=5.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )
    controller = _controller(master)
    state = controller._build_cut_framework_state()
    assert state is not None
    group_id = str(master._group_id_by_instance["miner_001"])
    assert set(state.groups) == {group_id}
    group = state.groups[group_id]
    assert group.demand == 2
    assert group.pose_domain == {"pose_left", "pose_mid", "pose_right"}
    assert state.instance_to_facility_type == {group_id: "miner"}
    assert state.facility_templates == master.templates
    assert state.candidate_placements == {"facility_pools": master.facility_pools}
    assert state.exterior_blocks == frozenset()
    assert "region_capacity_v1" in state.available_oracle_versions
    assert len(state.ghost_cells) == 1
    ax, ay, gw, gh = state.ghost_rect
    assert (gw, gh) == (1, 1)
    assert state.ghost_cells == {(ax, ay)}


def test_state_assembly_preserves_rectangular_ghost_axis_order() -> None:
    """A square ghost masks width/height swaps; keep a rectangular red test."""
    master = _build_miner_master()
    master.ghost_rect = (2, 1)  # master convention: (width, height)
    controller = _controller(master)
    context = (
        0,
        _GHOST_U_VAR_SENTINEL,
        {"x": 1, "y": 0},
        {(1, 0), (2, 0)},
    )
    with mock.patch.object(
        LBBDController, "_selected_ghost_context", return_value=context
    ):
        state = controller._build_cut_framework_state()

    assert state is not None
    assert state.ghost_rect == (1, 0, 2, 1)
    assert state.ghost_cells == {(1, 0), (2, 0)}


# ---- typed scope identity: rectangular ghost axis order ---------------------


def test_rectangular_ghost_scope_attaches_only_with_matching_axis_order() -> None:
    """A ghost-bound compiled cut must distinguish (width, height) from its
    transpose: the typed ghost_rect_digest is axis-aware, and the resolver
    refuses to bind a transposed digest onto a master whose ghost is the other
    orientation (fail-closed)."""
    from src.cuts import frozen_artifacts, lifecycle, state_snapshot
    from src.cuts.lifecycle import _resolve_model_scope_binding
    from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
    from src.cuts.typed_platform import (
        CompiledCut,
        build_production_registry,
        cut_to_envelope_v1,
        validate_and_compile_cut,
    )
    from src.tests.cuts import test_stage_b_contracts as contracts

    registry = build_production_registry()

    def _compile(ghost_rect):
        sources = contracts._bound_region_sources(
            lifecycle.BState, lifecycle.GroupState, ghost_rect=ghost_rect
        )
        sources["state"].source_digest = lifecycle.compute_source_digest(sources["state"])
        bundle = contracts._build_bundle(
            frozen_artifacts.build_frozen_artifact_bundle, sources
        )
        snapshot = state_snapshot.build_validated_state_snapshot(sources["state"], bundle)
        cut = generate_region_capacity_cuts(sources["state"], sources["state"].canonical_rules)[0]
        compiled = validate_and_compile_cut(cut_to_envelope_v1(cut), snapshot, registry)
        assert isinstance(compiled, CompiledCut)
        return snapshot, compiled

    # Master ghost is 3×1 (width 3, height 1).
    master, _state, _group_id = _bound_region_world(ghost_rect=(0, 0, 3, 1))
    snap_same, compiled_same = _compile((0, 0, 3, 1))
    snap_trans, compiled_trans = _compile((0, 0, 1, 3))  # transposed

    # Axis-aware identity: transposing width/height changes the ghost digest.
    assert (
        compiled_same.plan.model_scope.ghost_rect_digest
        != compiled_trans.plan.model_scope.ghost_rect_digest
    )
    # The matching orientation resolves; the transpose cannot locate a rect.
    binding = _resolve_model_scope_binding(compiled_same.plan.model_scope, snap_same, master)
    assert binding.ghost_rect_digest == compiled_same.plan.model_scope.ghost_rect_digest
    with pytest.raises(ValueError, match="no live master ghost rect matches"):
        _resolve_model_scope_binding(compiled_trans.plan.model_scope, snap_trans, master)


def test_r10_typed_single_entry_rejects_drifted_snapshot() -> None:
    """R10 (two-state scope soundness): a cut compiled against snapshot A must
    NOT compile against a drifted snapshot B — the typed single entry answers
    CutRejection(stage='scope'), never a CompiledCut.

    (The historical F5 instance is deferred: pattern_nogood → ShadowValidated
    needs the real sub-problem oracle registry wired; the F1 instance exercises
    the same scope-currentness soundness the R10 case guarded — see the B5a
    delivery report.)
    """
    import copy

    from src.cuts import frozen_artifacts, lifecycle, state_snapshot
    from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
    from src.cuts.typed_platform import (
        CompiledCut,
        CutRejection,
        build_production_registry,
        cut_to_envelope_v1,
        validate_and_compile_cut,
    )
    from src.tests.cuts import test_stage_b_contracts as contracts

    registry = build_production_registry()
    sources = contracts._bound_region_sources(
        lifecycle.BState, lifecycle.GroupState, ghost_rect=(0, 0, 3, 1)
    )
    state_a = sources["state"]
    state_a.source_digest = lifecycle.compute_source_digest(state_a)
    bundle_a = contracts._build_bundle(frozen_artifacts.build_frozen_artifact_bundle, sources)
    snapshot_a = state_snapshot.build_validated_state_snapshot(state_a, bundle_a)
    cut = generate_region_capacity_cuts(state_a, state_a.canonical_rules)[0]
    envelope = cut_to_envelope_v1(cut)

    assert isinstance(validate_and_compile_cut(envelope, snapshot_a, registry), CompiledCut)

    # Drift the state (artifact hash → new source_digest) and rebuild snapshot.
    state_b = copy.deepcopy(state_a)
    state_b.artifact_hashes = dict(state_b.artifact_hashes)
    state_b.artifact_hashes["canonical_rules"] = "9" * 64
    state_b.source_digest = lifecycle.compute_source_digest(state_b)
    bundle_b = frozen_artifacts.build_frozen_artifact_bundle(
        canonical_rules=state_b.canonical_rules,
        candidate_placements=state_b.candidate_placements,
        facility_templates=state_b.facility_templates,
        instance_to_facility_type=state_b.instance_to_facility_type,
        artifact_hashes=state_b.artifact_hashes,
    )
    snapshot_b = state_snapshot.build_validated_state_snapshot(state_b, bundle_b)
    result_b = validate_and_compile_cut(envelope, snapshot_b, registry)
    assert isinstance(result_b, CutRejection)
    assert result_b.stage == "scope"


def test_full_chain_f5_binding_empty_domain_end_to_end(tmp_path: Path) -> None:
    """RFC-002 batch D: a real F5 empty-binding-domain cut flows through the
    full orchestration — the wired sub-problem oracle registry, the production
    typed registry, and the independent verifier — landing in the
    shadow_validated bucket with the independently-verified tag and ZERO master
    mutation (F5 never reaches step_8).
    """
    from src.cuts import typed_platform
    from src.cuts.oracles.pattern_nogood_oracle import (
        clear_sub_problem_oracle_registry,
        register_sub_problem_oracle,
    )
    from src.tests.cuts.test_stage_b_contracts import _real_master_mutation_projection
    from src.tests.cuts.test_stage_b_typed_platform import (
        _PRODUCTION_ARTIFACT_HASHES,
        _DifferentialF5Oracle,
        _build_f5_verifiable_world,
        _make_verifiable_pattern_cut,
    )

    # State drives the internally-built snapshot + cut; the master only has to
    # stay untouched (F5 is shadow-only), so any real bound-region master serves.
    f5_state, _snapshot, group_id = _build_f5_verifiable_world(
        artifact_hashes=_PRODUCTION_ARTIFACT_HASHES,
    )
    f5_cut = _make_verifiable_pattern_cut(
        f5_state, group_id, pose_id="p_dead", with_identity_preimage=True
    )

    master, _region_state, _gid = _bound_region_world()
    before = _real_master_mutation_projection(master, proto_path=tmp_path / "b.pb")
    controller = _controller(master)

    # Delegate-spy on the production single entry so the shadow's telemetry tag
    # can be asserted while the REAL validate_and_compile_cut still runs.
    real_validate = typed_platform.validate_and_compile_cut
    captured: list[Any] = []

    def _recording_validate(*args: Any, **kwargs: Any) -> Any:
        result = real_validate(*args, **kwargs)
        captured.append(result)
        return result

    clear_sub_problem_oracle_registry()
    register_sub_problem_oracle(_DifferentialF5Oracle())  # type: ignore[arg-type]
    try:
        with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
            with mock.patch.object(
                LBBDController, "_build_cut_framework_state", return_value=f5_state
            ), mock.patch(
                "src.cuts.oracles.region_capacity_oracle.generate_region_capacity_cuts",
                return_value=[f5_cut],
            ), _suppress_f6(), mock.patch(
                "src.cuts.typed_platform.validate_and_compile_cut",
                side_effect=_recording_validate,
            ):
                attached = controller._maybe_attach_framework_cuts(
                    trigger="binding_infeasible", iteration=1
                )
    finally:
        clear_sub_problem_oracle_registry()

    after = _real_master_mutation_projection(master, proto_path=tmp_path / "a.pb")
    assert attached == 0
    assert after == before
    stats = master.build_stats["cut_framework_attach_last"]
    assert stats["shadow_validated"] == 1
    assert stats["attached_by_family"] == {}
    assert stats["rejected"] == {
        stage: 0 for stage in stats["rejected"]
    }, stats["rejected"]

    shadows = [r for r in captured if isinstance(r, typed_platform.ShadowValidated)]
    assert len(shadows) == 1
    assert shadows[0].telemetry_tag == "independently-verified"


# ---- §6 differential anchors (orchestration vs direct; zero-mutation) --------


def test_maybe_attach_orchestration_equals_direct_chain(tmp_path: Path) -> None:
    """§6 equivalence anchor: the same F1 oracle cut, applied via
    ``_maybe_attach_framework_cuts`` on one real master, produces the
    BYTE-IDENTICAL master mutation as the direct typed chain on a fresh,
    identically-built master."""
    from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
    from src.tests.cuts.test_stage_b_contracts import _real_master_mutation_projection

    master_orch, state, _group_id = _bound_region_world()
    master_direct, _state2, _gid2 = _bound_region_world()
    # The two freshly-built masters are byte-identical before any mutation.
    assert _real_master_mutation_projection(
        master_orch, proto_path=tmp_path / "orch_before.pb"
    ) == _real_master_mutation_projection(
        master_direct, proto_path=tmp_path / "direct_before.pb"
    )

    f1_cut = generate_region_capacity_cuts(state, state.canonical_rules)[0]
    controller = _controller(master_orch)
    with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
        with mock.patch.object(
            LBBDController, "_build_cut_framework_state", return_value=state
        ), mock.patch(
            "src.cuts.oracles.region_capacity_oracle.generate_region_capacity_cuts",
            return_value=[f1_cut],
        ), _suppress_f6():
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=9
            )
    assert attached == 1

    _direct_apply_f1(master_direct, state)

    assert _real_master_mutation_projection(
        master_orch, proto_path=tmp_path / "orch_after.pb"
    ) == _real_master_mutation_projection(
        master_direct, proto_path=tmp_path / "direct_after.pb"
    )


def test_maybe_attach_shadow_result_causes_zero_master_mutation(tmp_path: Path) -> None:
    """§6 zero-mutation: a ShadowValidated (F5) result flows into the shadow
    bucket and never mutates the master (never reaches step_8)."""
    from src.cuts import frozen_artifacts, lifecycle, state_snapshot, typed_platform
    from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
    from src.tests.cuts import test_stage_b_contracts as contracts
    from src.tests.cuts.test_stage_b_contracts import _real_master_mutation_projection

    shadow = contracts._build_shadow_result(
        frozen_artifacts, state_snapshot, typed_platform, lifecycle
    )[4]
    assert isinstance(shadow, typed_platform.ShadowValidated)

    master, state, _group_id = _bound_region_world()
    before = _real_master_mutation_projection(master, proto_path=tmp_path / "b.pb")
    cut = generate_region_capacity_cuts(state, state.canonical_rules)[0]
    controller = _controller(master)
    with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
        with mock.patch.object(
            LBBDController, "_build_cut_framework_state", return_value=state
        ), mock.patch(
            "src.cuts.oracles.region_capacity_oracle.generate_region_capacity_cuts",
            return_value=[cut],
        ), _suppress_f6(), mock.patch(
            "src.cuts.typed_platform.validate_and_compile_cut", return_value=shadow
        ):
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=1
            )
    after = _real_master_mutation_projection(master, proto_path=tmp_path / "a.pb")
    assert attached == 0
    assert after == before
    stats = master.build_stats["cut_framework_attach_last"]
    assert stats["shadow_validated"] == 1
    assert stats["attached_by_family"] == {}


def test_maybe_attach_rejection_causes_zero_master_mutation(tmp_path: Path) -> None:
    """§6 zero-mutation: a CutRejection result is bucketed by stage and never
    mutates the master (never reaches the resolver / step_8)."""
    from src.cuts.oracles.region_capacity_oracle import generate_region_capacity_cuts
    from src.cuts.typed_platform import CutRejection
    from src.tests.cuts.test_stage_b_contracts import _real_master_mutation_projection

    master, state, _group_id = _bound_region_world()
    before = _real_master_mutation_projection(master, proto_path=tmp_path / "b.pb")
    cut = generate_region_capacity_cuts(state, state.canonical_rules)[0]
    controller = _controller(master)
    rejection = CutRejection(stage="scope", reason="synthetic drift", cut_id="c0")
    with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
        with mock.patch.object(
            LBBDController, "_build_cut_framework_state", return_value=state
        ), mock.patch(
            "src.cuts.oracles.region_capacity_oracle.generate_region_capacity_cuts",
            return_value=[cut],
        ), _suppress_f6(), mock.patch(
            "src.cuts.typed_platform.validate_and_compile_cut", return_value=rejection
        ):
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=1
            )
    after = _real_master_mutation_projection(master, proto_path=tmp_path / "a.pb")
    assert attached == 0
    assert after == before
    stats = master.build_stats["cut_framework_attach_last"]
    assert stats["rejected"]["scope"] == 1
    assert stats["attached_by_family"] == {}
    assert stats["shadow_validated"] == 0


# ---- Stage-B §2.1 session bundle ownership (B6-prep) -------------------------


def test_session_bundle_cache_builds_once_per_artifact_digest(monkeypatch) -> None:
    """ExactSearchSession.cut_framework_bundle freezes the static artifacts once
    per artifact-hash digest and reuses the same object; a different digest
    rebuilds.  This is the session-ownership contract (Stage-B spec §2.1)."""
    import src.cuts.frozen_artifacts as fa

    calls: list[Dict[str, str]] = []
    real_build = fa.build_frozen_artifact_bundle

    def _counting_build(**kwargs: Any) -> Any:
        calls.append(dict(kwargs["artifact_hashes"]))
        return real_build(**kwargs)

    monkeypatch.setattr(fa, "build_frozen_artifact_bundle", _counting_build)

    session = _bare_session()
    common = dict(
        canonical_rules={},
        candidate_placements={"facility_pools": {}},
        facility_templates={},
        instance_to_facility_type={},
    )
    b1 = session.cut_framework_bundle(artifact_hashes={"a": "1", "b": "2"}, **common)
    b2 = session.cut_framework_bundle(artifact_hashes={"b": "2", "a": "1"}, **common)
    # Same digest (key order-insensitive) → one build, identical object reused.
    assert b1 is b2
    assert len(calls) == 1
    # Different digest → a distinct build.
    b3 = session.cut_framework_bundle(artifact_hashes={"a": "9"}, **common)
    assert b3 is not b1
    assert len(calls) == 2


def test_maybe_attach_reuses_session_bundle_across_rounds(monkeypatch) -> None:
    """With a session threaded into the controller, two successive attach rounds
    freeze the bundle exactly once (session ownership), not once per round.  The
    per-round path (module-level build_frozen_artifact_bundle) is not taken."""
    import src.cuts.frozen_artifacts as fa

    master, state, _group_id = _bound_region_world()
    session = _bare_session()
    controller = _controller(master, session=session)
    assert controller._session is session

    build_count = {"n": 0}
    real_build = fa.build_frozen_artifact_bundle

    def _counting_build(**kwargs: Any) -> Any:
        build_count["n"] += 1
        return real_build(**kwargs)

    monkeypatch.setattr(fa, "build_frozen_artifact_bundle", _counting_build)

    with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
        with mock.patch.object(
            LBBDController, "_build_cut_framework_state", return_value=state
        ):
            a1 = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=1
            )
            a2 = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=2
            )
    # Round 1 did real attach work; round 2 regenerates the same semantic
    # cut and is (since 批E, spec 08 D-2) deduplicated instead of re-lowered —
    # which is itself proof the round ran against the shared bundle.
    assert a1 >= 1
    assert a2 == 0
    stats_last = master.build_stats["cut_framework_attach_last"]
    assert stats_last["rejected"]["semantic_duplicate"] >= 1
    # Both rounds shared a single frozen bundle (session ownership).
    assert build_count["n"] == 1
    assert len(session._cut_framework_bundle_cache) == 1


def test_maybe_attach_without_session_builds_per_round(monkeypatch) -> None:
    """Without a session (exploratory / legacy harness callers) the bundle is
    built every round — the fallback path is preserved unchanged."""
    import src.cuts.frozen_artifacts as fa

    master, state, _group_id = _bound_region_world()
    controller = _controller(master)  # no session
    assert controller._session is None

    build_count = {"n": 0}
    real_build = fa.build_frozen_artifact_bundle

    def _counting_build(**kwargs: Any) -> Any:
        build_count["n"] += 1
        return real_build(**kwargs)

    monkeypatch.setattr(fa, "build_frozen_artifact_bundle", _counting_build)

    with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
        with mock.patch.object(
            LBBDController, "_build_cut_framework_state", return_value=state
        ):
            controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=1
            )
            controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=2
            )
    assert build_count["n"] == 2
