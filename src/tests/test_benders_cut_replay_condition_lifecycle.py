"""Regression for persisted conditioned cut replay (GPT v4 P0 #1).

直接 add_benders_cut(conflict, condition_lits=[u_var]) 在 v3 已修. 但 v4
audit 抓到 persisted cut replay 路径 (benders_loop.py:run_benders_for_ghost_rect)
只重传 conflict_set, 不解析 cut.condition_set 回 u_var → conditioned cut
重放成 unconditional → 过切.

本测试覆盖完整生命周期: BendersCut -> to_dict -> from_dict ->
_resolve_condition_lits_from_condition_set -> master.add_benders_cut(..., condition_lits=)
"""
from __future__ import annotations

from ortools.sat.python import cp_model

from src.models.master_model import MasterPlacementModel
from src.models.cut_manager import BendersCut
from src.search.benders_loop import _resolve_condition_lits_from_condition_set


def _fixture():
    instances = [
        {"instance_id": "miner_001", "facility_type": "miner",
         "operation_type": "mining", "is_mandatory": True, "bound_type": "exact"},
        {"instance_id": "miner_002", "facility_type": "miner",
         "operation_type": "mining", "is_mandatory": True, "bound_type": "exact"},
    ]
    pools = {
        "miner": [
            {"pose_id": "A", "anchor": {"x": 0, "y": 0},
             "occupied_cells": [[0, 0]], "input_port_cells": [],
             "output_port_cells": [], "power_coverage_cells": None},
            {"pose_id": "B", "anchor": {"x": 2, "y": 0},
             "occupied_cells": [[2, 0]], "input_port_cells": [],
             "output_port_cells": [], "power_coverage_cells": None},
            {"pose_id": "C", "anchor": {"x": 3, "y": 0},
             "occupied_cells": [[3, 0]], "input_port_cells": [],
             "output_port_cells": [], "power_coverage_cells": None},
        ]
    }
    rules = {
        "globals": {"grid": {"width": 4, "height": 1}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    return instances, pools, rules


def _build_overlay():
    instances, pools, rules = _fixture()
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules, skip_power_coverage=True,
    )
    return MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))


def _single_pose_overlay():
    instances = [
        {
            "instance_id": "machine_001",
            "facility_type": "machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools = {
        "machine": [
            {
                "pose_id": "M0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ]
    }
    rules = {
        "globals": {"grid": {"width": 2, "height": 1}},
        "facility_templates": {
            "machine": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules, skip_power_coverage=True,
    )
    return MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))


def _ghost_rect_idx_for_anchor(overlay, x, y):
    for idx, dom in enumerate(overlay._ghost_domains):
        a = dom.get("anchor") or {}
        if int(a.get("x", -1)) == x and int(a.get("y", -1)) == y:
            return idx
    raise AssertionError(f"no ghost anchor at ({x},{y})")


def _miner_pose_ids(overlay):
    sol = overlay.extract_solution()
    pool = overlay.facility_pools["miner"]
    return {pool[int(e["pose_idx"])]["pose_id"]
            for iid, e in sol.items() if iid.startswith("miner_")}


def _solve_ok(overlay):
    status = overlay.solve(time_limit_seconds=5.0)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE), f"status={status}"


def _build_persisted_conditioned_cut(overlay, *, ghost_x, ghost_y, miner_combo):
    """Build a BendersCut whose condition is ghost_anchor::(x,y) and whose
    conflict bans the given miner combo. miner_combo is dict instance_id -> pose_idx.
    """
    rect_idx = _ghost_rect_idx_for_anchor(overlay, ghost_x, ghost_y)
    return BendersCut(
        cut_type="probe_conditioned_cut",
        conflict_set=dict(miner_combo),
        iteration=0,
        source_mode="certified_exact",
        exact_safe=True,
        artifact_hashes={},
        condition_set={f"ghost_anchor::({ghost_x},{ghost_y})": int(rect_idx)},
        schema_version=3,
    )


def test_resolver_resolves_ghost_anchor_condition_to_u_var():
    overlay = _build_overlay()
    rect_idx = _ghost_rect_idx_for_anchor(overlay, 1, 0)
    cs = {"ghost_anchor::(1,0)": int(rect_idx)}
    lits, ok = _resolve_condition_lits_from_condition_set(overlay, cs)
    assert ok is True
    assert len(lits) == 1
    assert lits[0] is overlay.u_vars[rect_idx]


def test_resolver_fails_closed_on_unknown_key():
    overlay = _build_overlay()
    lits, ok = _resolve_condition_lits_from_condition_set(
        overlay, {"unknown_kind::foo": 0}
    )
    assert ok is False
    assert lits == []


def test_resolver_fails_closed_on_anchor_mismatch():
    overlay = _build_overlay()
    rect_idx = _ghost_rect_idx_for_anchor(overlay, 1, 0)
    # 故意拿错 anchor coord, rect_idx 指向 (1,0) 但 key 写 (0,0)
    bad_cs = {"ghost_anchor::(0,0)": int(rect_idx)}
    lits, ok = _resolve_condition_lits_from_condition_set(overlay, bad_cs)
    if rect_idx == _ghost_rect_idx_for_anchor(overlay, 0, 0):
        # 边缘: 实际 rect_idx 就是 (0,0), 那应当 ok
        return
    assert ok is False


def test_resolver_fails_closed_on_rect_idx_out_of_range():
    overlay = _build_overlay()
    bad_cs = {"ghost_anchor::(0,0)": 9999}
    lits, ok = _resolve_condition_lits_from_condition_set(overlay, bad_cs)
    assert ok is False


def test_empty_condition_set_resolves_to_no_lits():
    overlay = _build_overlay()
    lits, ok = _resolve_condition_lits_from_condition_set(overlay, {})
    assert ok is True
    assert lits == []


def test_persisted_cut_replay_preserves_condition_does_not_overprune():
    """完整 lifecycle: 在 ghost (1,0) 下抓 combo, persist 成 BendersCut,
    新 overlay 上 from_dict + resolver + add_benders_cut → 切换到挡 pose A
    的 ghost (0,0), 同 combo 因为 condition 不满足 不应被 cut 影响.
    """
    overlay = _build_overlay()
    neutral_idx = _ghost_rect_idx_for_anchor(overlay, 1, 0)
    overlay.model.Add(overlay.u_vars[neutral_idx] == 1)
    _solve_ok(overlay)
    miners_assignment = {
        iid: int(e["pose_idx"]) for iid, e in overlay.extract_solution().items()
        if iid.startswith("miner_")
    }
    combo_under_neutral = _miner_pose_ids(overlay)
    assert len(combo_under_neutral) == 2

    cut = _build_persisted_conditioned_cut(
        overlay, ghost_x=1, ghost_y=0, miner_combo=miners_assignment,
    )
    payload = cut.to_dict()
    assert payload["condition_set"]  # schema 保留

    # 新 overlay 模拟 replay
    overlay2 = _build_overlay()
    cut2 = BendersCut.from_dict(payload)
    assert cut2.condition_set == cut.condition_set
    resolved_lits, ok = _resolve_condition_lits_from_condition_set(
        overlay2, cut2.condition_set
    )
    assert ok is True and len(resolved_lits) == 1

    added = overlay2.add_benders_cut(
        cut2.conflict_set, condition_lits=tuple(resolved_lits)
    )
    assert added is True

    # 切到挡 pose A 的 ghost (0,0), condition 不满足 → cut 不触发, miners 还是
    # {B,C} (因为 ghost 挡住 A), 而不是被原 combo cut 进一步剪.
    other_idx = _ghost_rect_idx_for_anchor(overlay2, 0, 0)
    overlay2.model.Add(overlay2.u_vars[other_idx] == 1)
    _solve_ok(overlay2)
    combo2 = _miner_pose_ids(overlay2)
    assert combo2 == {"B", "C"}, (
        f"replay path 过切了 ghost (0,0) 下的合法 combo: {combo2}. "
        "P0 #1 fix 没真正生效, condition 在 replay 丢了."
    )


def test_persisted_cut_replay_fires_when_condition_active():
    """同 lifecycle, 但切回 ghost (1,0) 让 condition 满足 → cut 该 fire,
    原 combo 不能再出, miners 必须换另一种 combo.
    """
    overlay = _build_overlay()
    neutral_idx = _ghost_rect_idx_for_anchor(overlay, 1, 0)
    overlay.model.Add(overlay.u_vars[neutral_idx] == 1)
    _solve_ok(overlay)
    miners_assignment = {
        iid: int(e["pose_idx"]) for iid, e in overlay.extract_solution().items()
        if iid.startswith("miner_")
    }
    combo1 = _miner_pose_ids(overlay)

    cut = _build_persisted_conditioned_cut(
        overlay, ghost_x=1, ghost_y=0, miner_combo=miners_assignment,
    )
    payload = cut.to_dict()

    overlay2 = _build_overlay()
    cut2 = BendersCut.from_dict(payload)
    resolved_lits, ok = _resolve_condition_lits_from_condition_set(
        overlay2, cut2.condition_set
    )
    assert ok is True
    overlay2.add_benders_cut(cut2.conflict_set, condition_lits=tuple(resolved_lits))

    # 再把 ghost (1,0) 选回去 — cut 该 fire
    neutral_idx2 = _ghost_rect_idx_for_anchor(overlay2, 1, 0)
    overlay2.model.Add(overlay2.u_vars[neutral_idx2] == 1)
    _solve_ok(overlay2)
    combo2 = _miner_pose_ids(overlay2)
    assert combo2 != combo1, "replay cut 没 fire, condition 是不是丢了?"
    assert combo2.issubset({"A", "B", "C"}) and len(combo2) == 2


def test_persisted_cut_replay_fails_closed_on_unresolved_conflict_member():
    """A persisted certified cut must not dilute {valid, missing} into {valid}.

    Before the guard, replay accepted the cut below, silently dropped the missing
    conflict member, and banned the sole valid machine pose. That turns a
    feasible certified candidate into INFEASIBLE.
    """

    overlay = _single_pose_overlay()
    safe_ghost_idx = _ghost_rect_idx_for_anchor(overlay, 1, 0)
    overlay.model.Add(overlay.u_vars[safe_ghost_idx] == 1)
    _solve_ok(overlay)

    cut = BendersCut(
        cut_type="routing_exhausted_nogood",
        conflict_set={"machine_001": 0, "missing_instance": 0},
        iteration=1,
        source_mode="certified_exact",
        exact_safe=True,
        artifact_hashes={},
        proof_stage="routing",
        binding_exhausted=True,
        routing_exhausted=True,
        schema_version=2,
    )
    payload = cut.to_dict()

    overlay2 = _single_pose_overlay()
    cut2 = BendersCut.from_dict(payload)
    added = overlay2.add_benders_cut(cut2.conflict_set)

    assert added is False
    overlay2.model.Add(overlay2.u_vars[safe_ghost_idx] == 1)
    _solve_ok(overlay2)


def _two_pose_two_miner_fixture():
    instances = [
        {
            "instance_id": "miner_001",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "miner_002",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "miner": [
            {
                "pose_id": "A",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "B",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ]
    }
    rules = {
        "globals": {"grid": {"width": 3, "height": 1}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    return instances, pools, rules


def _force_gap_ghost(model):
    if not getattr(model, "u_vars", None):
        return
    rect_idx = _ghost_rect_idx_for_anchor(model, 1, 0)
    model.model.Add(model.u_vars[rect_idx] == 1)


def _build_two_pose_exact_model():
    instances, pools, rules = _two_pose_two_miner_fixture()
    model = MasterPlacementModel(
        instances,
        pools,
        rules,
        ghost_rect=(1, 1),
        solve_mode="certified_exact",
        skip_power_coverage=True,
    )
    model.build()
    _force_gap_ghost(model)
    return model


def test_coordinate_replay_alias_collision_fails_closed_instead_of_one_literal_ban():
    """Two symmetric mandatory members can alias to one presence literal.

    A persisted cut {miner_001@A, miner_002@A} is not representable in the
    coordinate master: both members normalize to mandatory::<group>@pose A.
    Replaying it as a deduped one-literal nogood would ban A entirely and turn
    the only feasible {A, B} layout infeasible.
    """

    baseline = _build_two_pose_exact_model()
    _solve_ok(baseline)
    assert _miner_pose_ids(baseline) == {"A", "B"}

    cut = BendersCut(
        cut_type="routing_exhausted_nogood",
        conflict_set={"miner_001": 0, "miner_002": 0},
        iteration=1,
        source_mode="certified_exact",
        exact_safe=True,
        artifact_hashes={},
        proof_stage="routing",
        binding_exhausted=True,
        routing_exhausted=True,
        schema_version=2,
    )
    replayed = BendersCut.from_dict(cut.to_dict())

    overlay = _build_two_pose_exact_model()
    added = overlay.add_benders_cut(replayed.conflict_set)

    assert added is False
    assert overlay.build_stats.get("coordinate_benders_last_cut") is None
    _solve_ok(overlay)
    assert _miner_pose_ids(overlay) == {"A", "B"}


def test_pose_bool_replay_alias_collision_fails_closed(monkeypatch):
    monkeypatch.setenv("EXACT_USE_POSE_BOOL_MASTER", "1")
    overlay = _build_two_pose_exact_model()
    assert type(overlay._coordinate_delegate).__name__ == "PoseBoolExactMasterDelegate"

    added = overlay.add_benders_cut({"miner_001": 0, "miner_002": 0})

    assert added is False
    assert overlay.build_stats.get("pose_bool_benders_cut_count") is None
    _solve_ok(overlay)
    assert _miner_pose_ids(overlay) == {"A", "B"}


def test_legacy_benders_cut_alias_collision_fails_closed():
    instances, pools, rules = _two_pose_two_miner_fixture()
    model = MasterPlacementModel(
        instances,
        pools,
        rules,
        ghost_rect=(1, 1),
        solve_mode="exploratory",
        skip_power_coverage=True,
    )
    model.build()
    _force_gap_ghost(model)

    added = model.add_benders_cut({"miner_001": 0, "miner_002": 0})

    assert added is False
