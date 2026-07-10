"""Batch 1C tests for certified power-pole dominance normalization."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple

import pytest

from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    MasterPlacementModel,
)
from src.search import benders_loop as benders_loop_module
from src.search.benders_loop import (
    ExactSearchSession,
    LBBDController,
    normalize_certified_power_pole_dominance,
    run_benders_for_ghost_rect,
)


GRID_W = 6
GRID_H = 2
TEMPLATES = {
    "machine": {"needs_power": True},
    "protocol_storage_box": {"needs_power": True},
    "power_pole": {"needs_power": False},
}


def _pose(
    pose_id: str,
    *,
    occupied: Sequence[Sequence[int]],
    coverage: Sequence[Sequence[int]] | None = None,
) -> Dict[str, Any]:
    return {
        "pose_id": pose_id,
        "anchor": {"x": int(occupied[0][0]), "y": int(occupied[0][1])}
        if occupied
        else {"x": 0, "y": 0},
        "pose_params": {"orientation": "north", "port_mode": "none"},
        "occupied_cells": [list(cell) for cell in occupied],
        "input_port_cells": [],
        "output_port_cells": [],
        "power_coverage_cells": (
            None if coverage is None else [list(cell) for cell in coverage]
        ),
    }


def _entry(
    instance_id: str,
    facility_type: str,
    pose_idx: int,
    pose_id: str,
    *,
    mandatory: bool = False,
) -> Dict[str, Any]:
    return {
        "instance_id": instance_id,
        "facility_type": facility_type,
        "operation_type": (
            "power_supply" if facility_type == "power_pole" else "crafting"
        ),
        "pose_idx": pose_idx,
        "pose_id": pose_id,
        "anchor": {"x": pose_idx, "y": 0},
        "is_mandatory": mandatory,
        "bound_type": "exact" if mandatory else "exact_pose_optional",
        "solve_mode": "certified_exact",
    }


def _normalize(
    solution: Mapping[str, Mapping[str, Any]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    required: int = 0,
    templates: Mapping[str, Mapping[str, Any]] = TEMPLATES,
) -> Tuple[Dict[str, Any] | None, Dict[str, Any]]:
    return normalize_certified_power_pole_dominance(
        solution,
        facility_pools=pools,
        templates=templates,
        grid_w=GRID_W,
        grid_h=GRID_H,
        required_power_pole_count=required,
    )


def _two_redundant_poles_fixture() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    pools = {
        "machine": [_pose("machine_0", occupied=[[0, 0]])],
        "power_pole": [
            _pose("pole_a", occupied=[[1, 0]], coverage=[[0, 0]]),
            _pose("pole_b", occupied=[[2, 0]], coverage=[[0, 0]]),
        ],
    }
    solution = {
        "pole_b": _entry("pole_b", "power_pole", 1, "pole_b"),
        "machine_0": {
            **_entry("machine_0", "machine", 0, "machine_0", mandatory=True),
            "audit_payload": {"keep": [1, 2, 3]},
        },
        "pole_a": _entry("pole_a", "power_pole", 0, "pole_a"),
    }
    return solution, pools


def _terminal_power_rules_accept(
    solution: Mapping[str, Mapping[str, Any]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    grid_w: int = GRID_W,
    grid_h: int = GRID_H,
) -> bool:
    """Independent R1-R3 oracle matching exact_campaign.py:1227-1253."""

    return not _terminal_power_rule_failures(
        solution,
        pools,
        grid_w=grid_w,
        grid_h=grid_h,
    )


def _terminal_power_rule_failures(
    solution: Mapping[str, Mapping[str, Any]],
    pools: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    grid_w: int = GRID_W,
    grid_h: int = GRID_H,
) -> set[str]:
    """Return the independently evaluated terminal R1/R2/R3 failures."""

    poles: Dict[str, set[Tuple[int, int]]] = {}
    powered: Dict[str, set[Tuple[int, int]]] = {}
    for instance_id, entry in solution.items():
        facility_type = str(entry["facility_type"])
        if facility_type == "ghost_rect":
            continue
        pose = pools[facility_type][int(entry["pose_idx"])]
        if facility_type == "power_pole":
            poles[str(instance_id)] = {
                (int(cell[0]), int(cell[1]))
                for cell in pose["power_coverage_cells"]
                if 0 <= int(cell[0]) < grid_w and 0 <= int(cell[1]) < grid_h
            }
        elif bool(TEMPLATES[facility_type].get("needs_power", False)):
            powered[str(instance_id)] = {
                (int(cell[0]), int(cell[1])) for cell in pose["occupied_cells"]
            }

    coverers = {
        powered_id: {
            pole_id
            for pole_id, coverage in poles.items()
            if coverage.intersection(occupied)
        }
        for powered_id, occupied in powered.items()
    }
    failures: set[str] = set()
    if any(not powered_coverers for powered_coverers in coverers.values()):
        failures.add("R1")
    if len(poles) > len(powered):
        failures.add("R2")
    for pole_id in poles:
        targets = {
            powered_id
            for powered_id, powered_coverers in coverers.items()
            if pole_id in powered_coverers
        }
        if not targets or not any(
            coverers[powered_id] == {pole_id} for powered_id in targets
        ):
            failures.add("R3")
            break
    return failures


# T1
def test_t1_redundant_power_pole_is_pruned_and_non_poles_are_unchanged() -> None:
    solution, pools = _two_redundant_poles_fixture()
    input_snapshot = copy.deepcopy(solution)
    non_pole_bytes = json.dumps(solution["machine_0"], sort_keys=True)

    normalized, summary = _normalize(solution, pools)

    assert normalized is not None
    assert set(normalized) == {"machine_0", "pole_b"}
    assert json.dumps(normalized["machine_0"], sort_keys=True) == non_pole_bytes
    assert solution == input_snapshot
    assert summary["verdict"] == "normalized"
    assert summary["pole_count_before"] == 2
    assert summary["pole_count_after"] == 1
    assert summary["pruned_pole_count"] == 1
    assert _terminal_power_rules_accept(normalized, pools)


# T2
def test_t2_minimal_covering_set_is_a_noop() -> None:
    pools = {
        "machine": [
            _pose("machine_0", occupied=[[0, 0]]),
            _pose("machine_1", occupied=[[4, 0]]),
        ],
        "power_pole": [
            _pose("pole_a", occupied=[[1, 0]], coverage=[[0, 0]]),
            _pose("pole_b", occupied=[[3, 0]], coverage=[[4, 0]]),
        ],
    }
    solution = {
        "machine_0": _entry("machine_0", "machine", 0, "machine_0", mandatory=True),
        "machine_1": _entry("machine_1", "machine", 1, "machine_1", mandatory=True),
        "pole_a": _entry("pole_a", "power_pole", 0, "pole_a"),
        "pole_b": _entry("pole_b", "power_pole", 1, "pole_b"),
    }

    normalized, summary = _normalize(solution, pools)

    assert normalized == solution
    assert normalized is not solution
    assert all(normalized[key] is not solution[key] for key in solution)
    assert summary["verdict"] == "noop"
    assert summary["pruned_pole_count"] == 0


# T3
def test_t3_pruning_iterates_to_a_deterministic_fixed_point() -> None:
    pools = {
        "machine": [_pose("machine_0", occupied=[[0, 0]])],
        "power_pole": [
            _pose("pole_a", occupied=[[1, 0]], coverage=[[0, 0]]),
            _pose("pole_b", occupied=[[2, 0]], coverage=[[0, 0]]),
            _pose("pole_c", occupied=[[3, 0]], coverage=[[0, 0]]),
        ],
    }
    solution = {
        "machine_0": _entry("machine_0", "machine", 0, "machine_0", mandatory=True),
        "pole_c": _entry("pole_c", "power_pole", 2, "pole_c"),
        "pole_a": _entry("pole_a", "power_pole", 0, "pole_a"),
        "pole_b": _entry("pole_b", "power_pole", 1, "pole_b"),
    }

    normalized, summary = _normalize(solution, pools)

    assert normalized is not None
    assert set(normalized) == {"machine_0", "pole_c"}
    assert summary["prune_iterations"] >= 2
    assert _terminal_power_rules_accept(normalized, pools)


# T4
def test_t4_all_optional_poles_are_pruned_when_nothing_needs_power() -> None:
    pools = {
        "power_pole": [
            _pose("pole_a", occupied=[[1, 0]], coverage=[]),
            _pose("pole_b", occupied=[[2, 0]], coverage=[]),
        ]
    }
    solution = {
        "pole_a": _entry("pole_a", "power_pole", 0, "pole_a"),
        "pole_b": _entry("pole_b", "power_pole", 1, "pole_b"),
    }

    normalized, summary = _normalize(solution, pools)

    assert normalized == {}
    assert summary["verdict"] == "normalized"
    assert summary["pole_count_after"] == 0
    assert summary["pruned_pole_count"] == 2
    assert summary["powered_instance_count"] == 0


# T5
def test_t5_mandatory_poles_are_never_pruned_but_affect_reverification() -> None:
    pools = {
        "machine": [_pose("machine_0", occupied=[[0, 0]])],
        "power_pole": [
            _pose("pole_a", occupied=[[1, 0]], coverage=[[0, 0]]),
            _pose("pole_b", occupied=[[2, 0]], coverage=[[0, 0]]),
        ],
    }
    two_mandatory = {
        "machine_0": _entry("machine_0", "machine", 0, "machine_0", mandatory=True),
        "pole_a": _entry("pole_a", "power_pole", 0, "pole_a", mandatory=True),
        "pole_b": _entry("pole_b", "power_pole", 1, "pole_b", mandatory=True),
    }

    rejected, rejected_summary = _normalize(two_mandatory, pools)

    assert rejected is None
    assert rejected_summary["verdict"] == "power_pole_dominance_reverify_failed"
    assert rejected_summary["mandatory_pole_count"] == 2
    assert rejected_summary["pruned_pole_count"] == 0

    mandatory_and_optional = copy.deepcopy(two_mandatory)
    mandatory_and_optional["pole_b"] = _entry(
        "pole_b", "power_pole", 1, "pole_b"
    )
    normalized, summary = _normalize(mandatory_and_optional, pools)

    assert normalized is not None
    assert set(normalized) == {"machine_0", "pole_a"}
    assert summary["mandatory_pole_count"] == 1
    assert summary["pruned_pole_count"] == 1


# T6
def test_t6_positive_required_count_skips_pruning_and_reverifies() -> None:
    pools = {
        "machine": [
            _pose("machine_0", occupied=[[0, 0]]),
            _pose("machine_1", occupied=[[5, 0]]),
        ],
        "power_pole": [
            _pose("pole_a", occupied=[[1, 0]], coverage=[[0, 0]]),
            _pose("pole_b", occupied=[[4, 0]], coverage=[[5, 0]]),
        ],
    }
    solution = {
        "machine_0": _entry("machine_0", "machine", 0, "machine_0", mandatory=True),
        "machine_1": _entry("machine_1", "machine", 1, "machine_1", mandatory=True),
        "pole_a": _entry("pole_a", "power_pole", 0, "pole_a"),
        "pole_b": _entry("pole_b", "power_pole", 1, "pole_b"),
    }

    normalized, summary = _normalize(solution, pools, required=2)

    assert normalized == solution
    assert summary["verdict"] == "noop"
    assert summary["required_power_pole_count"] == 2
    assert summary["pruned_pole_count"] == 0
    assert summary["prune_iterations"] == 0


# T7
def test_t7_required_layout_with_unforced_pole_fails_closed() -> None:
    solution, pools = _two_redundant_poles_fixture()

    normalized, summary = _normalize(solution, pools, required=2)

    assert normalized is None
    assert summary["verdict"] == "required_power_pole_reverify_failed"
    assert summary["pruned_pole_count"] == 0

    optional_lower_bound_pools = {
        "machine": [
            _pose("machine_0", occupied=[[0, 0]]),
            _pose("machine_1", occupied=[[5, 0]]),
        ],
        "power_pole": [
            _pose("pole_a", occupied=[[1, 0]], coverage=[[0, 0]]),
            _pose("pole_b", occupied=[[4, 0]], coverage=[[5, 0]]),
        ],
    }
    mandatory_does_not_satisfy_optional_required = {
        "machine_0": _entry("machine_0", "machine", 0, "machine_0", mandatory=True),
        "machine_1": _entry("machine_1", "machine", 1, "machine_1", mandatory=True),
        "pole_a": _entry("pole_a", "power_pole", 0, "pole_a", mandatory=True),
        "pole_b": _entry("pole_b", "power_pole", 1, "pole_b"),
    }

    normalized, summary = _normalize(
        mandatory_does_not_satisfy_optional_required,
        optional_lower_bound_pools,
        required=2,
    )

    assert normalized is None
    assert summary["verdict"] == "required_power_pole_reverify_failed"
    assert _terminal_power_rule_failures(
        mandatory_does_not_satisfy_optional_required,
        optional_lower_bound_pools,
    ) == set()


@pytest.mark.parametrize(
    "malformation",
    [
        "pole_pose_idx_out_of_bounds",
        "pole_pose_id_mismatch",
        "pole_coverage_not_a_pair",
        "powered_occupied_empty",
        "power_pole_template_missing",
    ],
)
# T8
def test_t8_malformed_pose_data_always_fails_closed(malformation: str) -> None:
    pools = {
        "machine": [_pose("machine_0", occupied=[[0, 0]])],
        "power_pole": [_pose("pole_a", occupied=[[1, 0]], coverage=[[0, 0]])],
    }
    solution = {
        "machine_0": _entry("machine_0", "machine", 0, "machine_0", mandatory=True),
        "pole_a": _entry("pole_a", "power_pole", 0, "pole_a"),
    }
    if malformation == "pole_pose_idx_out_of_bounds":
        solution["pole_a"]["pose_idx"] = 99
    elif malformation == "pole_pose_id_mismatch":
        solution["pole_a"]["pose_id"] = "drifted"
    elif malformation == "pole_coverage_not_a_pair":
        pools["power_pole"][0]["power_coverage_cells"] = [[0]]
    elif malformation == "powered_occupied_empty":
        pools["machine"][0]["occupied_cells"] = []

    templates = TEMPLATES
    if malformation == "power_pole_template_missing":
        templates = {"machine": TEMPLATES["machine"]}

    normalized, summary = _normalize(solution, pools, templates=templates)

    assert normalized is None
    assert summary["verdict"] not in {"normalized", "noop"}


# T9
def test_t9_normalization_is_byte_deterministic() -> None:
    solution, pools = _two_redundant_poles_fixture()

    first = _normalize(solution, pools)
    second = _normalize(solution, pools)

    first_bytes = json.dumps(first, sort_keys=True, separators=(",", ":"))
    second_bytes = json.dumps(second, sort_keys=True, separators=(",", ":"))
    assert first_bytes == second_bytes


class _FeasibleBindingModel:
    def __init__(self, *_args, **_kwargs):
        pass

    def build(self) -> None:
        return None

    def solve(self, **_kwargs) -> str:
        return "FEASIBLE"

    def extract_empty_binding_domain_instances(self) -> list[Any]:
        return []

    def extract_conflict_summary(self) -> Dict[str, Any]:
        return {"fixture": "feasible"}

    def extract_selection(self) -> Dict[str, Any]:
        return {}

    def extract_port_specs(self) -> list[Any]:
        return []


class _RoutingGridShell:
    def __init__(self, *_args, **_kwargs):
        pass


class _FeasibleRoutingModel:
    def __init__(self, *_args, **_kwargs):
        self.build_stats: Dict[str, Any] = {}

    def build(self) -> None:
        return None

    def solve(self, **_kwargs) -> str:
        return "FEASIBLE"


def _install_feasible_subproblems(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        benders_loop_module,
        "PortBindingModel",
        _FeasibleBindingModel,
    )
    monkeypatch.setattr(benders_loop_module, "RoutingGrid", _RoutingGridShell)
    monkeypatch.setattr(
        benders_loop_module,
        "RoutingSubproblem",
        _FeasibleRoutingModel,
    )
    monkeypatch.setattr(
        LBBDController,
        "_run_flow_diagnostic",
        lambda self, solution: ("SKIPPED", []),
    )


def _coverage_cells(
    x_val: int,
    y_val: int,
    *,
    width: int,
    height: int,
    radius: int = 1,
) -> list[list[int]]:
    return [
        [x, y]
        for x in range(
            max(0, x_val - radius),
            min(width - 1, x_val + 2 + radius - 1) + 1,
        )
        for y in range(
            max(0, y_val - radius),
            min(height - 1, y_val + 2 + radius - 1) + 1,
        )
    ]


def _endpoint_fixture(
    *,
    c1: bool,
    project_root: Path,
) -> Tuple[ExactSearchSession, Mapping[str, Sequence[Mapping[str, Any]]]]:
    width, height = 4, 2
    pools = {
        "protocol_storage_box": [
            _pose(f"box_{x}_{y}", occupied=[[x, y]])
            for y in range(height)
            for x in range(width)
        ],
        "power_pole": [
            _pose(
                f"pole_{x}_{y}",
                occupied=[[x, y]],
                coverage=_coverage_cells(
                    x,
                    y,
                    width=width,
                    height=height,
                ),
            )
            for y in range(height)
            for x in range(width)
        ],
    }
    rules = {
        "globals": {
            "grid": {"width": width, "height": height},
            "empty_rectangle": {
                "objective": "max_lex_area_min_side",
                "min_side_admissibility": 1,
            },
        },
        "facility_templates": {
            "protocol_storage_box": {
                "dimensions": {"w": 1, "h": 1},
                "needs_power": True,
            },
            "power_pole": {
                "dimensions": {"w": 1, "h": 1},
                "needs_power": False,
                "power_coverage_radius": 1,
            },
        },
        "commodity_metadata": {
            "valley_battery": {
                "source_kind": "none",
                "sink_kind": "generic_input",
            }
        },
    }
    instances: list[Dict[str, Any]] = []
    core = MasterPlacementModel.build_exact_core(
        instances,
        pools,
        rules,
        c1_power_pole_representation=c1,
        generic_io_requirements={
            "required_generic_inputs": {"valley_battery": 1},
            "required_generic_outputs": {},
        },
        wireless_sink_generic_input_slots=3,
        exact_required_pose_optional_counts={"protocol_storage_box": 1},
    )
    session = ExactSearchSession(
        project_root=project_root,
        solve_mode="certified_exact",
        instances=instances,
        facility_pools=pools,
        rules=rules,
        artifact_hashes={},
        master_search_profile=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
        core=core,
        core_build_seconds=0.0,
    )
    return session, pools


def _run_certified_endpoint(
    *,
    c1: bool,
    tmp_path: Path,
) -> Tuple[
    Dict[str, Any],
    Dict[str, Any],
    Mapping[str, Sequence[Mapping[str, Any]]],
    Any,
]:
    session, pools = _endpoint_fixture(c1=c1, project_root=tmp_path)

    status, solution = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=tmp_path,
        solve_mode="certified_exact",
        session=session,
        max_iterations=1,
        master_seconds=5.0,
        binding_seconds=1.0,
        routing_seconds=1.0,
        flow_seconds=1.0,
    )

    assert status == benders_loop_module.RUN_STATUS_CERTIFIED
    assert solution is not None
    proof_summary = dict(
        run_benders_for_ghost_rect.last_run_metadata["proof_summary"]
    )
    return solution, proof_summary, pools, session.core


# T10
def test_t10_c1_certified_endpoint_returns_normalized_power_poles(
    tmp_path: Path,
) -> None:
    solution, proof_summary, pools, core = _run_certified_endpoint(
        c1=True,
        tmp_path=tmp_path,
    )

    assert "ghost_pick" in solution
    assert core.c1_power_pole_representation is True
    assert core.build_stats["power_coverage"]["encoding"] == (
        "c1_pose_bool_cov_channel_v1"
    )
    assert _terminal_power_rules_accept(solution, pools, grid_w=4, grid_h=2)
    assert proof_summary["power_pole_dominance"]["verdict"] in {
        "normalized",
        "noop",
    }


# T11
def test_t11_legacy_witness_certified_endpoint_is_rejected_fail_closed(
    tmp_path: Path,
) -> None:
    session, _pools = _endpoint_fixture(c1=False, project_root=tmp_path)

    status, solution = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=tmp_path,
        solve_mode="certified_exact",
        session=session,
        max_iterations=1,
        master_seconds=5.0,
        binding_seconds=1.0,
        routing_seconds=1.0,
        flow_seconds=1.0,
    )
    proof_summary = dict(
        run_benders_for_ghost_rect.last_run_metadata["proof_summary"]
    )

    assert status == benders_loop_module.RUN_STATUS_UNKNOWN
    assert solution is None
    assert session.core.c1_power_pole_representation is False
    assert session.core.build_stats["power_coverage"]["encoding"] == (
        "geometric_element_witness_v1"
    )
    assert proof_summary["master_status"] == benders_loop_module.RUN_STATUS_UNKNOWN
    assert proof_summary["stage"] == "master_representation_contract"
    assert proof_summary["blocker_code"] == (
        "power_witness_representation_not_certified"
    )


# T12
def test_t12_reverification_matches_terminal_r1_r3_semantics() -> None:
    # Semantic parity anchor: exact_campaign.py terminal verifier lines 1227-1253.
    accepted_pools = {
        "machine": [_pose("machine_0", occupied=[[0, 0]])],
        "power_pole": [_pose("pole_a", occupied=[[1, 0]], coverage=[[0, 0]])],
    }
    accepted_solution = {
        "machine_0": _entry("machine_0", "machine", 0, "machine_0", mandatory=True),
        "pole_a": _entry("pole_a", "power_pole", 0, "pole_a"),
    }
    r1_only_pools = {
        "machine": [
            _pose("machine_0", occupied=[[0, 0]]),
            _pose("machine_1", occupied=[[5, 0]]),
        ],
        "power_pole": [_pose("pole_a", occupied=[[1, 0]], coverage=[[0, 0]])],
    }
    r1_only_solution = {
        "machine_0": _entry("machine_0", "machine", 0, "machine_0", mandatory=True),
        "machine_1": _entry("machine_1", "machine", 1, "machine_1", mandatory=True),
        "pole_a": _entry("pole_a", "power_pole", 0, "pole_a", mandatory=True),
    }
    # 唯一失败的规则：R1（machine_1 无 coverer；R2/R3 均通过）。
    assert _terminal_power_rule_failures(r1_only_solution, r1_only_pools) == {"R1"}

    r3_only_pools = {
        "machine": [
            _pose("machine_0", occupied=[[0, 0]]),
            _pose("machine_1", occupied=[[5, 0]]),
        ],
        "power_pole": [
            _pose("pole_a", occupied=[[1, 0]], coverage=[[0, 0], [5, 0]]),
            _pose("pole_b", occupied=[[2, 0]], coverage=[[0, 0]]),
        ],
    }
    r3_only_solution = {
        "machine_0": _entry("machine_0", "machine", 0, "machine_0", mandatory=True),
        "machine_1": _entry("machine_1", "machine", 1, "machine_1", mandatory=True),
        "pole_a": _entry("pole_a", "power_pole", 0, "pole_a", mandatory=True),
        "pole_b": _entry("pole_b", "power_pole", 1, "pole_b", mandatory=True),
    }
    # 唯一失败的规则：R3（pole_b 从不是唯一 coverer；R1/R2 均通过）。
    assert _terminal_power_rule_failures(r3_only_solution, r3_only_pools) == {"R3"}

    r2_joint_pools = {
        "machine": [_pose("machine_0", occupied=[[0, 0]])],
        "power_pole": [
            _pose("pole_a", occupied=[[1, 0]], coverage=[[0, 0]]),
            _pose("pole_b", occupied=[[2, 0]], coverage=[[0, 0]]),
        ],
    }
    r2_joint_solution = {
        "machine_0": _entry("machine_0", "machine", 0, "machine_0", mandatory=True),
        "pole_a": _entry("pole_a", "power_pole", 0, "pole_a", mandatory=True),
        "pole_b": _entry("pole_b", "power_pole", 1, "pole_b", mandatory=True),
    }
    # R2-only 几何不可构造：R3 要求每根杆各自拥有唯一目标，必然推出杆数不超过
    # powered 数。这里钉住最小 R2 联合拒绝场景及该逻辑蕴含关系。
    assert _terminal_power_rule_failures(r2_joint_solution, r2_joint_pools) == {
        "R2",
        "R3",
    }

    for solution, pools in (
        (accepted_solution, accepted_pools),
        (r1_only_solution, r1_only_pools),
        (r3_only_solution, r3_only_pools),
        (r2_joint_solution, r2_joint_pools),
    ):
        normalized, _summary = _normalize(solution, pools)
        assert (normalized is not None) is _terminal_power_rules_accept(solution, pools)


# T13
def test_t13_normalization_failure_turns_feasible_routing_into_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_feasible_subproblems(monkeypatch)
    pools = {
        "machine": [_pose("machine_0", occupied=[[0, 0]])],
        "power_pole": [_pose("pole_a", occupied=[[1, 0]], coverage=[[0, 0]])],
    }

    class MasterStub:
        facility_pools = pools
        templates = TEMPLATES
        source_instances: list[Any] = []
        grid_w = GRID_W
        grid_h = GRID_H
        generic_io_requirements = {
            "required_generic_inputs": {},
            "required_generic_outputs": {},
        }
        rules = {"facility_templates": TEMPLATES}
        _exact_required_pose_optional_counts = None
        _coordinate_delegate = None

    forced_summary = {
        "verdict": "power_pole_dominance_reverify_failed",
        "pole_count_before": 1,
        "pole_count_after": 1,
        "pruned_pole_count": 0,
        "prune_iterations": 0,
        "powered_instance_count": 1,
        "required_power_pole_count": 0,
        "mandatory_pole_count": 0,
    }
    monkeypatch.setattr(
        benders_loop_module,
        "normalize_certified_power_pole_dominance",
        lambda *args, **kwargs: (None, dict(forced_summary)),
    )
    heartbeats: list[Dict[str, Any]] = []
    cut_manager = benders_loop_module.CutManager(
        tmp_path / "checkpoints",
        solve_mode="certified_exact",
        current_hashes={},
    )
    controller = LBBDController(
        MasterStub(),
        cut_manager,
        tmp_path,
        "certified_exact",
        max_iterations=1,
        binding_seconds=1.0,
        routing_seconds=1.0,
        heartbeat_callback=lambda payload: heartbeats.append(dict(payload)),
    )
    solution = {
        "machine_0": _entry("machine_0", "machine", 0, "machine_0", mandatory=True),
        "pole_a": _entry("pole_a", "power_pole", 0, "pole_a"),
    }

    status, returned_solution = controller._run_exact_binding_and_routing(
        iteration=1,
        solution=solution,
        diagnostic_flow_status="SKIPPED",
    )

    assert status == benders_loop_module.RUN_STATUS_UNKNOWN
    assert returned_solution is None
    assert controller.last_proof_summary["stage"] == (
        "power_pole_dominance_normalization"
    )
    assert controller.last_proof_summary["power_pole_dominance"]["verdict"] == (
        "power_pole_dominance_reverify_failed"
    )
    assert controller.last_proof_summary["power_pole_dominance"][
        "required_source_missing"
    ] is True
    normalization_events = [
        payload["event"]
        for payload in heartbeats
        if payload["stage"] == "power_pole_dominance_normalization"
    ]
    assert normalization_events == ["start", "complete"]

    def _raise_unexpected_normalization_exception(*_args, **_kwargs):
        raise RuntimeError("injected normalization failure")

    monkeypatch.setattr(
        benders_loop_module,
        "normalize_certified_power_pole_dominance",
        _raise_unexpected_normalization_exception,
    )

    status, returned_solution = controller._run_exact_binding_and_routing(
        iteration=2,
        solution=solution,
        diagnostic_flow_status="SKIPPED",
    )

    assert status == benders_loop_module.RUN_STATUS_UNKNOWN
    assert returned_solution is None
    assert controller.last_proof_summary["stage"] == (
        "power_pole_dominance_normalization"
    )
    assert controller.last_proof_summary["power_pole_dominance"] == {
        "verdict": "power_pole_normalization_exception",
        "exception_type": "RuntimeError",
    }


# T14
def test_t14_s3_certified_path_prunes_redundant_pole_without_mutating_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_feasible_subproblems(monkeypatch)
    solution, pools = _two_redundant_poles_fixture()
    input_snapshot = copy.deepcopy(solution)

    class MasterStub:
        facility_pools = pools
        templates = TEMPLATES
        source_instances: list[Any] = []
        grid_w = GRID_W
        grid_h = GRID_H
        generic_io_requirements = {
            "required_generic_inputs": {},
            "required_generic_outputs": {},
        }
        rules = {"facility_templates": TEMPLATES}
        _exact_required_pose_optional_counts = None
        _coordinate_delegate = None

    cut_manager = benders_loop_module.CutManager(
        tmp_path / "checkpoints",
        solve_mode="certified_exact",
        current_hashes={},
    )
    controller = LBBDController(
        MasterStub(),
        cut_manager,
        tmp_path,
        "certified_exact",
        max_iterations=1,
        binding_seconds=1.0,
        routing_seconds=1.0,
    )

    status, normalized = controller._run_exact_binding_and_routing(
        iteration=1,
        solution=solution,
        diagnostic_flow_status="SKIPPED",
    )

    assert status == benders_loop_module.RUN_STATUS_CERTIFIED
    assert normalized is not None
    assert set(normalized) == {"machine_0", "pole_b"}
    assert solution == input_snapshot
    assert controller.last_proof_summary["power_pole_dominance"]["verdict"] == (
        "normalized"
    )
    assert controller.last_proof_summary["power_pole_dominance"][
        "pruned_pole_count"
    ] == 1
    assert controller.last_proof_summary["power_pole_dominance"][
        "required_source_missing"
    ] is True
