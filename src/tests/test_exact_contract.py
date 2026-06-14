"""Tests for certified exact contracts（严格精确契约测试）.

文件目录索引 (5666 行, 76 tests + 10 helpers, vintage 2026-05-16):

主要 test cluster 按行号:
- L34-376     helper functions: project builders / campaign IO / precheck mocks
- L377-578    certified_exact / collect_certification_blockers_* (9 tests) — 严格精确模式接入
- L598-660    binding_recognizes_pose_optional_protocol_storage_box (1) — pose 可选 storage box
- L661-680    timeout_returns_unknown (1) — 超时返回 UNKNOWN
- L681-810    candidate_level_boundary_* / mandatory_* (2) — candidate-level precheck
- L811-982    candidate_level_mandatory_support_*  (1) + 其他 — mandatory support 集成
- L983-1299   pre_master_precheck_*  (3 tests) — pre-master precheck
- L1102-1173  pre_master_mandatory_rectangle_precheck (1) — pre-master mandatory rect
- L1174-1882  **pre_master_coordinate_*  (7 tests)** — pre-master coordinate validation
- L1224-1300  anchor119_row_domain_* (1) — anchor119 行域 (Phase 3B)
- L2242-2295  campaign_keeps_best_* (2) — campaign state best 保持
- L2563-2908  exact_mode_uses_* (2) — exact mode artifact usage
- L2633-5063  exact_path_publishes_* (2) — exact path 输出 publish
- L4173-4539  serial_precheck_lookahead_*  (4 tests) — serial precheck lookahead
- L5210-5238  frontier_probe_auto_* (2) — frontier probe auto

测试什么: certified_exact mode 端到端契约 — campaign 持久化 + UNKNOWN 处理 + precheck +
  publish + frontier probe 等横切面.

pre-commit gate: **本文件 在 CORE_TEST_FILES**, 每次 commit 跑 (核心契约文件).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from ortools.sat.python import cp_model

from src.io.delivery_manifest import delivery_manifest_output_path
from src.io.output_schema import normalize_blueprint_payload
from src.models.binding_subproblem import PortBindingModel
from src.models.cut_manager import (
    RUN_STATUS_CERTIFIED,
    RUN_STATUS_INFEASIBLE,
    RUN_STATUS_UNKNOWN,
    RUN_STATUS_UNPROVEN,
)
from src.models.master_model import MasterPlacementModel, load_project_data
import src.search.benders_loop as benders_loop_module
import src.search.exact_campaign as exact_campaign_module
import src.search.outer_search as outer_search_module
from src.search.benders_loop import collect_certification_blockers, run_benders_for_ghost_rect
from src.search.campaign_telemetry import (
    build_wave_summary,
    campaign_telemetry_output_path,
    classify_candidate_outcome,
)
from src.search.exact_campaign import ExactCampaign
from src.search.outer_search import generate_candidate_sizes, run_outer_search



def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")



def _build_toy_exact_project(project_root: Path) -> Path:
    data_dir = project_root / "data" / "preprocessed"
    rules_dir = project_root / "rules"

    _write_json(
        rules_dir / "canonical_rules.json",
        {
            "globals": {"grid": {"width": 2, "height": 1}, "empty_rectangle": {"objective": "max_lex_area_min_side", "min_side_admissibility": 1}},
            "facility_templates": {
                "tiny_facility": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            },
        },
    )
    _write_json(
        data_dir / "candidate_placements.json",
        {
            "facility_pools": {
                "tiny_facility": [
                    {
                        "pose_id": "tiny_left",
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [[0, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    }
                ]
            }
        },
    )
    mandatory_instances = [
        {
            "instance_id": "tiny_001",
            "facility_type": "tiny_facility",
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_modes": ["certified_exact"],
        }
    ]
    _write_json(data_dir / "mandatory_exact_instances.json", mandatory_instances)
    _write_json(data_dir / "all_facility_instances.json", mandatory_instances)
    _write_json(
        data_dir / "generic_io_requirements.json",
        {
            "required_generic_outputs": {},
            "required_generic_inputs": {},
        },
    )
    return project_root


def test_certified_project_loader_rejects_duplicate_keys_in_mandatory_artifact(
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "duplicate_mandatory_keys")
    (project_root / "data" / "preprocessed" / "mandatory_exact_instances.json").write_text(
        '[{"instance_id":"tiny_001",'
        '"instance_id":"tiny_002",'
        '"facility_type":"tiny_facility",'
        '"is_mandatory":true,'
        '"bound_type":"exact"}]',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate JSON key"):
        load_project_data(project_root, solve_mode="certified_exact")


def test_certified_project_loader_rejects_nonstandard_json_constants(
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "nonstandard_candidate_constant")
    (project_root / "data" / "preprocessed" / "candidate_placements.json").write_text(
        '{"facility_pools":{"tiny_facility":[{'
        '"pose_id":"tiny_left",'
        '"anchor":{"x":0,"y":0},'
        '"occupied_cells":[[0,0]],'
        '"input_port_cells":[],'
        '"output_port_cells":[],'
        '"power_coverage_cells":NaN}]}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid JSON constant"):
        load_project_data(project_root, solve_mode="certified_exact")


def test_certified_binding_kwargs_use_master_generic_io_snapshot() -> None:
    controller = benders_loop_module.LBBDController.__new__(
        benders_loop_module.LBBDController
    )
    controller.solve_mode = "certified_exact"
    controller.master = SimpleNamespace(
        generic_io_requirements={
            "required_generic_outputs": {"source_ore": 1},
            "required_generic_inputs": {"valley_battery": 2},
        },
        wireless_sink_generic_input_slots=3,
    )

    assert controller._binding_generic_requirements_kwargs() == {
        "required_generic_outputs": {"source_ore": 1},
        "required_generic_inputs": {"valley_battery": 2},
        "wireless_sink_generic_input_slots": 3,
    }

    controller.solve_mode = "exploratory"
    assert controller._binding_generic_requirements_kwargs() == {}


def test_certified_retry_binding_receives_master_generic_io_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: dict[str, object] = {}

    class CapturingBindingModel:
        def __init__(self, *_args, **kwargs):
            captured_kwargs.update(kwargs)

        def build(self) -> None:
            return None

        def solve(self, **_kwargs) -> str:
            return "FEASIBLE"

        def extract_conflict_summary(self) -> dict:
            return {
                "overload_separation_enabled": False,
                "overload_nogoods_added": 0,
            }

    monkeypatch.setattr(benders_loop_module, "PortBindingModel", CapturingBindingModel)
    controller = benders_loop_module.LBBDController.__new__(
        benders_loop_module.LBBDController
    )
    controller.solve_mode = "certified_exact"
    controller.project_root = tmp_path
    controller.binding_seconds = 1.0
    controller._emit_heartbeat = lambda **_kwargs: None
    controller.master = SimpleNamespace(
        facility_pools={},
        source_instances=[],
        generic_io_requirements={
            "required_generic_outputs": {"source_ore": 1},
            "required_generic_inputs": {"valley_battery": 2},
        },
        wireless_sink_generic_input_slots=3,
    )

    _model, status = benders_loop_module.LBBDController._retry_binding_without_overload_separation(
        controller,
        solution={},
        iteration=0,
    )

    assert status == "FEASIBLE"
    assert captured_kwargs["required_generic_outputs"] == {"source_ore": 1}
    assert captured_kwargs["required_generic_inputs"] == {"valley_battery": 2}
    assert captured_kwargs["wireless_sink_generic_input_slots"] == 3


def test_certified_binding_kwargs_require_wireless_slot_snapshot_for_generic_inputs() -> None:
    controller = benders_loop_module.LBBDController.__new__(
        benders_loop_module.LBBDController
    )
    controller.solve_mode = "certified_exact"
    controller.master = SimpleNamespace(
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {"valley_battery": 1},
        }
    )

    with pytest.raises(RuntimeError, match="wireless_sink_generic_input_slots snapshot"):
        controller._binding_generic_requirements_kwargs()


def test_certified_static_lower_bound_uses_project_wireless_slot_snapshot() -> None:
    rules = {
        "facility_templates": {
            "protocol_storage_box": {"dimensions": {"w": 3, "h": 3}}
        }
    }
    generic_io_requirements = {
        "required_generic_outputs": {},
        "required_generic_inputs": {"valley_battery": 4},
    }

    assert (
        benders_loop_module.compute_exact_static_area_lower_bound(
            [],
            rules,
            generic_io_requirements,
            wireless_sink_generic_input_slots=4,
        )
        == 9
    )
    assert (
        benders_loop_module.compute_exact_static_area_lower_bound(
            [],
            rules,
            generic_io_requirements,
            wireless_sink_generic_input_slots=2,
        )
        == 18
    )


def _build_required_protocol_box_project(project_root: Path) -> Path:
    data_dir = project_root / "data" / "preprocessed"
    rules_dir = project_root / "rules"

    _write_json(
        rules_dir / "canonical_rules.json",
        {
            "globals": {"grid": {"width": 2, "height": 2}, "empty_rectangle": {"objective": "max_lex_area_min_side", "min_side_admissibility": 1}},
            "facility_templates": {
                "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
                "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            },
            "commodity_metadata": {
                "valley_battery": {"sink_kind": "generic_input"},
            },
        },
    )
    _write_json(
        data_dir / "candidate_placements.json",
        {
            "facility_pools": {
                "power_pole": [
                    {
                        "pose_id": "pole_0",
                        "anchor": {"x": 1, "y": 1},
                        "occupied_cells": [[1, 1]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": [[0, 0]],
                    }
                ],
                "protocol_storage_box": [
                    {
                        "pose_id": "box_0",
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [[0, 0]],
                        "input_port_cells": [{"x": 0, "y": 1, "dir": "N"}],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    }
                ],
            }
        },
    )
    _write_json(data_dir / "mandatory_exact_instances.json", [])
    _write_json(data_dir / "all_facility_instances.json", [])
    _write_json(
        data_dir / "generic_io_requirements.json",
        {
            "required_generic_outputs": {},
            "required_generic_inputs": {"valley_battery": 1},
        },
    )
    _write_json(
        rules_dir / "preprocess_plan.json",
        {
            "utility_operations": {
                "wireless_sink": {
                    "facility_type": "protocol_storage_box",
                    "generic_input_slots": 3,
                    "generic_output_slots": 0,
                }
            }
        },
    )
    return project_root


def test_certified_campaign_optional_bounds_delegate_generic_io_loader(tmp_path: Path) -> None:
    project_root = _build_required_protocol_box_project(
        tmp_path / "campaign_generic_io_role_check"
    )
    _write_json(
        project_root / "data" / "preprocessed" / "generic_io_requirements.json",
        {
            "required_generic_outputs": {},
            "required_generic_inputs": {"unregistered_sink": 1},
        },
    )

    with pytest.raises(KeyError, match="generic input commodity"):
        exact_campaign_module._load_exact_required_optional_lower_bounds(project_root)


def _build_multi_pose_exact_project(
    project_root: Path,
    *,
    pose_anchors: list[int],
    include_pole_block: bool = False,
) -> Path:
    data_dir = project_root / "data" / "preprocessed"
    rules_dir = project_root / "rules"
    grid_width = max(pose_anchors + ([1] if include_pole_block else [0])) + 3

    facility_templates = {
        "tiny_facility": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
    }
    pools: dict[str, list[dict]] = {
        "tiny_facility": [
            {
                "pose_id": f"tiny_{anchor}",
                "anchor": {"x": anchor, "y": 0},
                "occupied_cells": [[anchor, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
            for anchor in pose_anchors
        ]
    }
    if include_pole_block:
        facility_templates["power_pole"] = {
            "dimensions": {"w": 1, "h": 1},
            "needs_power": False,
        }
        pools["power_pole"] = [
            {
                "pose_id": "pole_block",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[1, 0]],
            }
        ]
        pools["protocol_storage_box"] = []

    _write_json(
        rules_dir / "canonical_rules.json",
        {
            "globals": {"grid": {"width": grid_width, "height": 1}, "empty_rectangle": {"objective": "max_lex_area_min_side", "min_side_admissibility": 1}},
            "facility_templates": facility_templates,
        },
    )
    _write_json(data_dir / "candidate_placements.json", {"facility_pools": pools})
    mandatory_instances = [
        {
            "instance_id": "tiny_001",
            "facility_type": "tiny_facility",
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_modes": ["certified_exact"],
        }
    ]
    _write_json(data_dir / "mandatory_exact_instances.json", mandatory_instances)
    _write_json(data_dir / "all_facility_instances.json", mandatory_instances)
    _write_json(
        data_dir / "generic_io_requirements.json",
        {
            "required_generic_outputs": {},
            "required_generic_inputs": {},
        },
    )
    return project_root


def _build_frontier_project(
    project_root: Path,
    *,
    width: int = 6,
    height: int = 6,
    min_side_admissibility: int = 1,
) -> Path:
    data_dir = project_root / "data" / "preprocessed"
    rules_dir = project_root / "rules"

    _write_json(
        rules_dir / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": width, "height": height},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": min_side_admissibility,
                },
            },
            "facility_templates": {
                "synthetic": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            },
        },
    )
    # 单个真实 pose 让 terminal CERTIFIED 场景能走通 blueprint 导出/反查校验链
    # (V73+ 的 manifest 校验会把 blueprint facility 反查回 facility_pools)。
    _write_json(
        data_dir / "candidate_placements.json",
        {
            "facility_pools": {
                "synthetic": [
                    {
                        "pose_id": "synthetic_pose_0",
                        "anchor": {"x": 0, "y": 0},
                        "occupied_cells": [[0, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                        "pose_params": {"orientation": 0, "port_mode": "default"},
                    }
                ]
            }
        },
    )
    _write_json(data_dir / "mandatory_exact_instances.json", [])
    _write_json(data_dir / "all_facility_instances.json", [])
    _write_json(
        data_dir / "generic_io_requirements.json",
        {
            "required_generic_outputs": {},
            "required_generic_inputs": {},
        },
    )
    return project_root


def _read_campaign_state(project_root: Path) -> dict:
    return json.loads(
        (project_root / "data" / "checkpoints" / "exact_campaign_state.json").read_text(
            encoding="utf-8"
        )
    )


def _read_campaign_telemetry(project_root: Path) -> dict:
    path = campaign_telemetry_output_path(
        project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _mock_precheck_proof_summary(
    *,
    precheck_reason: str,
    supported: bool = True,
) -> dict:
    return {
        "mode": "certified_exact",
        "master_status": "INFEASIBLE",
        "diagnostic_flow_status": "NOT_RUN",
        "master_boundary_port_feasibility": {
            "supported": bool(supported),
            "required_count": 46 if supported else 0,
            "considered_anchor_count": 1 if supported else 0,
            "screened_infeasible_anchor_count": 1 if supported else 0,
            "screen_pass_anchor_count": 0,
            "unsupported_anchor_count": 0,
            "max_packable_min": 17 if supported else None,
            "max_packable_max": 17 if supported else None,
            "first_infeasible_anchor_idx": 0 if supported else None,
            "first_infeasible_anchor_max_packable": 17 if supported else None,
        },
        "master_mandatory_support_diagnostics": {
            "unsupported_group_count": 0,
            "empty_candidate_pool_group_count": 0,
            "groups": [],
        },
        "master_mandatory_group_prechecks": {
            "evaluated": False,
            "skipped_due_to_upstream_precheck": bool(
                precheck_reason == "boundary_port_all_anchors_infeasible"
            ),
            "upstream_anchor_filter_count": 0,
            "supported_group_count": 0,
            "groups": [],
        },
        "master_candidate_precheck": {
            "triggered": True,
            "precheck_reason": str(precheck_reason),
            "master_solve_skipped": True,
            "supported": bool(supported),
            "considered_anchor_count": 1 if supported else 0,
            "screened_infeasible_anchor_count": 1 if supported else 0,
            "screen_pass_anchor_count": 0,
            "max_packable_min": 17 if supported else None,
            "max_packable_max": 17 if supported else None,
            "first_infeasible_anchor_idx": 0 if supported else None,
            "first_infeasible_anchor_max_packable": 17 if supported else None,
            "triggered_group_id": None,
            "triggered_group_facility_type": None,
            "triggered_group_operation_type": None,
            "triggered_group_required_count": 0,
        },
    }


def _mock_supported_boundary_port_precheck_payload(
    anchor_indices: tuple[int, ...],
) -> dict:
    return {
        "supported": True,
        "required_count": 46,
        "considered_anchor_count": len(anchor_indices),
        "screened_infeasible_anchor_count": 0,
        "screen_pass_anchor_count": len(anchor_indices),
        "unsupported_anchor_count": 0,
        "max_packable_min": 46,
        "max_packable_max": 46,
        "first_infeasible_anchor_idx": None,
        "first_infeasible_anchor_max_packable": None,
        "screen_pass_anchor_indices": tuple(int(idx) for idx in anchor_indices),
        "rebuild_anchor_indices": tuple(int(idx) for idx in anchor_indices),
    }


def _mock_frontier_state_from_sequence(
    sequence: list[tuple[int, int, int]],
    campaign: ExactCampaign | None,
) -> dict[str, object]:
    candidate_records = (
        {}
        if campaign is None
        else dict(campaign.state.get("candidates", {}))
    )
    unresolved: list[tuple[int, int, int]] = []
    for candidate in sequence:
        record = candidate_records.get(outer_search_module._candidate_key(candidate))
        status = "" if not isinstance(record, dict) else str(record.get("status", ""))
        if status in {
            RUN_STATUS_CERTIFIED,
            RUN_STATUS_INFEASIBLE,
            RUN_STATUS_UNKNOWN,
            RUN_STATUS_UNPROVEN,
        }:
            continue
        unresolved.append(candidate)
    metrics_by_key = {
        outer_search_module._candidate_key(candidate): {
            "selection_score_num": 1,
            "selection_score_den": 1,
            "certification_prune_gain": 1,
            "infeasible_prune_gain": 1,
            "anchor_count": 1,
            "frontier_size": len(unresolved),
        }
        for candidate in unresolved
    }
    return {
        "potential_domain": list(unresolved),
        "frontier": list(unresolved),
        "frontier_size": len(unresolved),
        "derived_pruned_candidates": 0,
        "best_certified_candidate": None,
        "best_certified_record": None,
        "selected_candidate": None if not unresolved else unresolved[0],
        "selected_candidate_metrics": None
        if not unresolved
        else dict(metrics_by_key[outer_search_module._candidate_key(unresolved[0])]),
        "frontier_metrics_by_key": metrics_by_key,
    }



def test_certified_exact_rejects_provisional_instances() -> None:
    blockers = collect_certification_blockers(
        instances=[
            {
                "instance_id": "power_pole_001",
                "facility_type": "power_pole",
                "operation_type": "power_supply",
                "is_mandatory": False,
                "bound_type": "provisional",
                "solve_mode": "exploratory",
            }
        ],
        solve_mode="certified_exact",
    )
    codes = {item["code"] for item in blockers}
    assert "provisional_instance_forbidden" in codes
    assert "non_mandatory_instance_forbidden" in codes
    assert "instance_mode_pollution" in codes


def test_collect_certification_blockers_accepts_certified_exact_mode_metadata() -> None:
    blockers = collect_certification_blockers(
        instances=[
            {
                "instance_id": "tiny_001",
                "facility_type": "tiny_facility",
                "operation_type": "processing",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_mode": "certified_exact",
            }
        ],
        solve_mode="certified_exact",
    )

    assert blockers == []


def test_collect_certification_blockers_accepts_certified_exact_in_solve_modes_list() -> None:
    blockers = collect_certification_blockers(
        instances=[
            {
                "instance_id": "tiny_001",
                "facility_type": "tiny_facility",
                "operation_type": "processing",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            }
        ],
        solve_mode="certified_exact",
    )

    assert blockers == []


def test_collect_certification_blockers_accepts_certified_exact_in_mixed_solve_modes_list() -> None:
    blockers = collect_certification_blockers(
        instances=[
            {
                "instance_id": "tiny_001",
                "facility_type": "tiny_facility",
                "operation_type": "processing",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact", "exploratory"],
            }
        ],
        solve_mode="certified_exact",
    )

    assert blockers == []


def test_collect_certification_blockers_rejects_exploratory_only_mode_metadata() -> None:
    blockers = collect_certification_blockers(
        instances=[
            {
                "instance_id": "tiny_001",
                "facility_type": "tiny_facility",
                "operation_type": "processing",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_mode": "exploratory",
            }
        ],
        solve_mode="certified_exact",
    )

    assert [item["code"] for item in blockers] == ["instance_mode_pollution"]

    blockers = collect_certification_blockers(
        instances=[
            {
                "instance_id": "tiny_002",
                "facility_type": "tiny_facility",
                "operation_type": "processing",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["exploratory"],
            }
        ],
        solve_mode="certified_exact",
    )

    assert [item["code"] for item in blockers] == ["instance_mode_pollution"]


def test_collect_certification_blockers_rejects_missing_or_malformed_mode_metadata() -> None:
    missing_blockers = collect_certification_blockers(
        instances=[
            {
                "instance_id": "tiny_missing",
                "facility_type": "tiny_facility",
                "operation_type": "processing",
                "is_mandatory": True,
                "bound_type": "exact",
            }
        ],
        solve_mode="certified_exact",
    )
    malformed_blockers = collect_certification_blockers(
        instances=[
            {
                "instance_id": "tiny_bad",
                "facility_type": "tiny_facility",
                "operation_type": "processing",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact", 7],
            },
            {
                "instance_id": "tiny_unknown",
                "facility_type": "tiny_facility",
                "operation_type": "processing",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["unknown_mode"],
            },
        ],
        solve_mode="certified_exact",
    )

    assert [item["code"] for item in missing_blockers] == ["instance_mode_pollution"]
    assert [item["code"] for item in malformed_blockers] == [
        "instance_mode_pollution",
        "instance_mode_pollution",
    ]


def test_collect_certification_blockers_rejects_conflicting_mode_metadata() -> None:
    blockers = collect_certification_blockers(
        instances=[
            {
                "instance_id": "tiny_conflict_1",
                "facility_type": "tiny_facility",
                "operation_type": "processing",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_mode": "exploratory",
                "solve_modes": ["certified_exact"],
            },
            {
                "instance_id": "tiny_conflict_2",
                "facility_type": "tiny_facility",
                "operation_type": "processing",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_mode": "certified_exact",
                "solve_modes": ["exploratory"],
            },
        ],
        solve_mode="certified_exact",
    )

    assert [item["code"] for item in blockers] == [
        "instance_mode_pollution",
        "instance_mode_pollution",
    ]
    assert all("conflicting_mode_metadata" in str(item["detail"]) for item in blockers)


def test_collect_certification_blockers_accepts_matching_dual_mode_metadata() -> None:
    blockers = collect_certification_blockers(
        instances=[
            {
                "instance_id": "tiny_safe",
                "facility_type": "tiny_facility",
                "operation_type": "processing",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_mode": "certified_exact",
                "solve_modes": ["certified_exact"],
            }
        ],
        solve_mode="certified_exact",
    )

    assert blockers == []


def test_collect_certification_blockers_rejects_matching_exploratory_dual_mode_metadata() -> None:
    blockers = collect_certification_blockers(
        instances=[
            {
                "instance_id": "tiny_exploratory_dual",
                "facility_type": "tiny_facility",
                "operation_type": "processing",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_mode": "exploratory",
                "solve_modes": ["exploratory"],
            }
        ],
        solve_mode="certified_exact",
    )

    assert [item["code"] for item in blockers] == ["instance_mode_pollution"]



def test_binding_recognizes_pose_optional_protocol_storage_box() -> None:
    placement_solution = {
        "boundary_port_001": {
            "pose_idx": 0,
            "pose_id": "boundary_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "boundary_storage_port",
        },
        "pose_optional::protocol_storage_box::box_pose_0": {
            "pose_idx": 0,
            "pose_id": "box_pose_0",
            "anchor": {"x": 2, "y": 0},
            "facility_type": "protocol_storage_box",
        },
    }
    facility_pools = {
        "boundary_storage_port": [
            {
                "pose_id": "boundary_pose_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [{"x": 0, "y": 0, "dir": "E"}],
                "power_coverage_cells": None,
            }
        ],
        "protocol_storage_box": [
            {
                "pose_id": "box_pose_0",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
    }
    instances = [
        {
            "instance_id": "boundary_port_001",
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]

    model = PortBindingModel(
        placement_solution,
        facility_pools,
        instances,
        required_generic_outputs={"source_ore": 1},
        required_generic_inputs={"valley_battery": 1},
    )
    model.build()
    assert model.solve(time_limit_seconds=5.0) == "FEASIBLE"

    selection = model.extract_selection()
    assert (
        selection["generic_inputs"][
            "pose_optional::protocol_storage_box::box_pose_0:in:0"
        ]
        == "valley_battery"
    )

    specs = model.extract_port_specs()
    assert not any(
        spec["instance_id"] == "pose_optional::protocol_storage_box::box_pose_0"
        for spec in specs
    )
    assert not any(spec["commodity"] == "valley_battery" for spec in specs)



def test_timeout_returns_unknown(monkeypatch, tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_timeout")

    def _always_unknown(self, *args, **kwargs):
        return cp_model.UNKNOWN

    monkeypatch.setattr(MasterPlacementModel, "solve", _always_unknown)
    status, _result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        max_iterations=1,
    )
    assert status == RUN_STATUS_UNKNOWN


def test_candidate_level_boundary_port_precheck_can_short_circuit_master(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_boundary_port_precheck")
    session = benders_loop_module.create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
    )
    support_diagnostics_payload = {
        "unsupported_group_count": 0,
        "empty_candidate_pool_group_count": 0,
        "groups": [
            {
                "group_id": "group::tiny_facility::::0",
                "facility_type": "tiny_facility",
                "operation_type": "",
                "required_count": 1,
                "candidate_pool_count": 1,
                "unsupported_reason": None,
            }
        ],
    }
    session.core.candidate_precheck_artifacts = {
        **dict(session.core.candidate_precheck_artifacts),
        "mandatory_support_diagnostics": dict(support_diagnostics_payload),
    }

    def _fake_boundary_port_precheck(cls, *, rules, ghost_rect, screen_spec):
        del cls, rules, ghost_rect, screen_spec
        return {
            "supported": True,
            "required_count": 46,
            "considered_anchor_count": 3,
            "screened_infeasible_anchor_count": 3,
            "screen_pass_anchor_count": 0,
            "unsupported_anchor_count": 0,
            "max_packable_min": 17,
            "max_packable_max": 39,
            "first_infeasible_anchor_idx": 0,
            "first_infeasible_anchor_max_packable": 17,
            "screen_pass_anchor_indices": (),
            "rebuild_anchor_indices": (),
        }

    monkeypatch.setattr(
        MasterPlacementModel,
        "evaluate_boundary_port_feasibility_from_screen_spec",
        classmethod(_fake_boundary_port_precheck),
    )
    monkeypatch.setattr(
        MasterPlacementModel,
        "from_exact_core",
        classmethod(
            lambda cls, *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("from_exact_core should be skipped by boundary precheck")
            )
        ),
    )
    monkeypatch.setattr(
        benders_loop_module,
        "LBBDController",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("LBBDController should be skipped by boundary precheck")
        ),
    )

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        session=session,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        max_iterations=1,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")
    proof_summary = metadata["proof_summary"]

    assert status == RUN_STATUS_INFEASIBLE
    assert result is None
    assert proof_summary["master_status"] == "INFEASIBLE"
    assert proof_summary["benders_iterations"] == 0
    assert proof_summary["master_candidate_precheck"] == {
        "triggered": True,
        "precheck_reason": "boundary_port_all_anchors_infeasible",
        "master_solve_skipped": True,
        "supported": True,
        "considered_anchor_count": 3,
        "screened_infeasible_anchor_count": 3,
        "screen_pass_anchor_count": 0,
        "max_packable_min": 17,
        "max_packable_max": 39,
        "first_infeasible_anchor_idx": 0,
        "first_infeasible_anchor_max_packable": 17,
        "triggered_group_id": None,
        "triggered_group_facility_type": None,
        "triggered_group_operation_type": None,
        "triggered_group_required_count": 0,
    }
    assert proof_summary["master_boundary_port_feasibility"] == {
        "supported": True,
        "required_count": 46,
        "considered_anchor_count": 3,
        "screened_infeasible_anchor_count": 3,
        "screen_pass_anchor_count": 0,
        "unsupported_anchor_count": 0,
        "max_packable_min": 17,
        "max_packable_max": 39,
        "first_infeasible_anchor_idx": 0,
        "first_infeasible_anchor_max_packable": 17,
    }
    assert proof_summary["master_mandatory_group_prechecks"] == {
        "evaluated": False,
        "skipped_due_to_upstream_precheck": True,
        "upstream_anchor_filter_count": 0,
        "supported_group_count": 0,
        "groups": [],
    }
    assert proof_summary["master_mandatory_support_diagnostics"] == (
        support_diagnostics_payload
    )
    assert proof_summary["overlay_build_seconds"] == 0.0
    assert proof_summary["ghost_constraint_seconds"] == 0.0
    assert proof_summary["cut_replay_seconds"] == 0.0
    assert classify_candidate_outcome(status=status, proof_summary=proof_summary) == "master_infeasible"


def test_candidate_level_mandatory_rectangle_precheck_can_short_circuit_master(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_mandatory_rect_precheck")
    session = benders_loop_module.create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
    )
    support_diagnostics_payload = {
        "unsupported_group_count": 0,
        "empty_candidate_pool_group_count": 0,
        "groups": [
            {
                "group_id": "group::manufacturing_6x4::refining::0",
                "facility_type": "manufacturing_6x4",
                "operation_type": "refining",
                "required_count": 2,
                "candidate_pool_count": 2,
                "unsupported_reason": None,
            }
        ],
    }
    session.core.candidate_precheck_artifacts = {
        **dict(session.core.candidate_precheck_artifacts),
        "mandatory_support_diagnostics": dict(support_diagnostics_payload),
    }

    def _fake_boundary_port_precheck(cls, *, rules, ghost_rect, screen_spec):
        del cls, rules, ghost_rect, screen_spec
        return {
            "supported": True,
            "required_count": 46,
            "considered_anchor_count": 1,
            "screened_infeasible_anchor_count": 0,
            "screen_pass_anchor_count": 1,
            "unsupported_anchor_count": 0,
            "max_packable_min": 46,
            "max_packable_max": 46,
            "first_infeasible_anchor_idx": None,
            "first_infeasible_anchor_max_packable": None,
            "screen_pass_anchor_indices": (0,),
            "rebuild_anchor_indices": (0,),
        }

    mandatory_anchor_calls = []

    def _fake_mandatory_group_prechecks(self, anchor_indices=None):
        mandatory_anchor_calls.append(
            None if anchor_indices is None else tuple(int(idx) for idx in anchor_indices)
        )
        payload = {
            "evaluated": True,
            "skipped_due_to_upstream_precheck": False,
            "upstream_anchor_filter_count": 1,
            "supported_group_count": 1,
            "groups": [
                {
                    "group_id": "group::manufacturing_6x4::refining::0",
                    "facility_type": "manufacturing_6x4",
                    "operation_type": "refining",
                    "required_count": 2,
                    "oracle_class": "m6x4_mixed",
                    "oracle_mode": "m6x4_mixed",
                    "supported": True,
                    "unsupported_reason": None,
                    "considered_anchor_count": 1,
                    "screened_infeasible_anchor_count": 1,
                    "screen_pass_anchor_count": 0,
                    "unsupported_anchor_count": 0,
                    "max_packable_min": 1,
                    "max_packable_max": 1,
                    "first_infeasible_anchor_idx": 0,
                    "first_infeasible_anchor_max_packable": 1,
                }
            ],
            "rebuild_anchor_indices": tuple(),
        }
        self.build_stats["exact_candidate_warm_start_mandatory_group_prechecks"] = {
            "evaluated": True,
            "skipped_due_to_upstream_precheck": False,
            "upstream_anchor_filter_count": 1,
            "supported_group_count": 1,
            "groups": list(payload["groups"]),
        }
        return payload

    monkeypatch.setattr(
        MasterPlacementModel,
        "evaluate_boundary_port_feasibility_from_screen_spec",
        classmethod(_fake_boundary_port_precheck),
    )
    monkeypatch.setattr(
        MasterPlacementModel,
        "evaluate_exact_candidate_mandatory_rectangle_prechecks",
        _fake_mandatory_group_prechecks,
    )
    monkeypatch.setattr(
        MasterPlacementModel,
        "solve",
        lambda self, *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("master.solve should be skipped by mandatory rectangle precheck")
        ),
    )

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        session=session,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        max_iterations=1,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")
    proof_summary = metadata["proof_summary"]

    assert status == RUN_STATUS_INFEASIBLE
    assert result is None
    assert proof_summary["master_status"] == "INFEASIBLE"
    assert mandatory_anchor_calls == [(0,)]
    assert proof_summary["master_candidate_precheck"] == {
        "triggered": True,
        "precheck_reason": "mandatory_rect_group_all_anchors_infeasible",
        "master_solve_skipped": True,
        "supported": True,
        "considered_anchor_count": 1,
        "screened_infeasible_anchor_count": 1,
        "screen_pass_anchor_count": 0,
        "max_packable_min": 1,
        "max_packable_max": 1,
        "first_infeasible_anchor_idx": 0,
        "first_infeasible_anchor_max_packable": 1,
        "triggered_group_id": "group::manufacturing_6x4::refining::0",
        "triggered_group_facility_type": "manufacturing_6x4",
        "triggered_group_operation_type": "refining",
        "triggered_group_required_count": 2,
    }
    assert proof_summary["master_mandatory_group_prechecks"] == {
        "evaluated": True,
        "skipped_due_to_upstream_precheck": False,
        "upstream_anchor_filter_count": 1,
        "supported_group_count": 1,
        "groups": [
            {
                "group_id": "group::manufacturing_6x4::refining::0",
                "facility_type": "manufacturing_6x4",
                "operation_type": "refining",
                "required_count": 2,
                "oracle_class": "m6x4_mixed",
                "oracle_mode": "m6x4_mixed",
                "supported": True,
                "unsupported_reason": None,
                "considered_anchor_count": 1,
                "screened_infeasible_anchor_count": 1,
                "screen_pass_anchor_count": 0,
                "unsupported_anchor_count": 0,
                "max_packable_min": 1,
                "max_packable_max": 1,
                "first_infeasible_anchor_idx": 0,
                "first_infeasible_anchor_max_packable": 1,
            }
        ],
    }
    assert proof_summary["master_mandatory_support_diagnostics"] == (
        support_diagnostics_payload
    )
    assert classify_candidate_outcome(status=status, proof_summary=proof_summary) == "master_infeasible"


def test_pre_master_precheck_can_opt_into_mandatory_rectangle_short_circuit(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_pre_master_mandatory_rect")
    session = benders_loop_module.create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
    )
    support_diagnostics_payload = {
        "unsupported_group_count": 0,
        "empty_candidate_pool_group_count": 0,
        "groups": [
            {
                "group_id": "group::tiny_facility::::0",
                "facility_type": "tiny_facility",
                "operation_type": "",
                "required_count": 1,
                "candidate_pool_count": 1,
                "unsupported_reason": None,
            }
        ],
    }
    session.core.candidate_precheck_artifacts = {
        **dict(session.core.candidate_precheck_artifacts),
        "mandatory_support_diagnostics": dict(support_diagnostics_payload),
    }
    mandatory_anchor_calls: list[tuple[int, ...]] = []

    def _fake_boundary_port_precheck(cls, *, rules, ghost_rect, screen_spec):
        del cls, rules, ghost_rect, screen_spec
        return {
            "supported": True,
            "required_count": 46,
            "considered_anchor_count": 1,
            "screened_infeasible_anchor_count": 0,
            "screen_pass_anchor_count": 1,
            "unsupported_anchor_count": 0,
            "max_packable_min": 46,
            "max_packable_max": 46,
            "first_infeasible_anchor_idx": None,
            "first_infeasible_anchor_max_packable": None,
            "screen_pass_anchor_indices": (0,),
            "rebuild_anchor_indices": (0,),
        }

    class FakeMandatoryRectangleModel:
        def evaluate_exact_candidate_mandatory_rectangle_prechecks(self, *, anchor_indices):
            mandatory_anchor_calls.append(tuple(int(idx) for idx in anchor_indices))
            return {
                "evaluated": True,
                "skipped_due_to_upstream_precheck": False,
                "upstream_anchor_filter_count": 1,
                "supported_group_count": 1,
                "groups": [
                    {
                        "group_id": "group::manufacturing_6x4::refining::0",
                        "facility_type": "manufacturing_6x4",
                        "operation_type": "refining",
                        "required_count": 2,
                        "oracle_class": "m6x4_mixed",
                        "oracle_mode": "m6x4_mixed",
                        "supported": True,
                        "unsupported_reason": None,
                        "considered_anchor_count": 1,
                        "screened_infeasible_anchor_count": 1,
                        "screen_pass_anchor_count": 0,
                        "unsupported_anchor_count": 0,
                        "max_packable_min": 1,
                        "max_packable_max": 1,
                        "first_infeasible_anchor_idx": 0,
                        "first_infeasible_anchor_max_packable": 1,
                    }
                ],
                "rebuild_anchor_indices": tuple(),
            }

    monkeypatch.setattr(
        MasterPlacementModel,
        "evaluate_boundary_port_feasibility_from_screen_spec",
        classmethod(_fake_boundary_port_precheck),
    )
    monkeypatch.setattr(
        MasterPlacementModel,
        "from_exact_core",
        classmethod(lambda cls, *args, **kwargs: FakeMandatoryRectangleModel()),
    )

    disabled = benders_loop_module.evaluate_exact_candidate_pre_master_precheck(
        ghost_w=1,
        ghost_h=1,
        exact_session=session,
        master_search_profile="test_profile",
    )
    enabled = benders_loop_module.evaluate_exact_candidate_pre_master_precheck(
        ghost_w=1,
        ghost_h=1,
        exact_session=session,
        master_search_profile="test_profile",
        include_mandatory_rectangle_precheck=True,
    )

    assert disabled["triggered"] is False
    assert mandatory_anchor_calls == [(0,)]
    assert enabled["triggered"] is True
    assert enabled["status"] == RUN_STATUS_INFEASIBLE
    proof_summary = enabled["proof_summary"]
    assert proof_summary["master_candidate_precheck"]["precheck_reason"] == (
        "mandatory_rect_group_all_anchors_infeasible"
    )
    assert proof_summary["master_candidate_precheck"]["triggered_group_id"] == (
        "group::manufacturing_6x4::refining::0"
    )
    assert proof_summary["master_mandatory_group_prechecks"]["evaluated"] is True
    assert proof_summary["master_mandatory_support_diagnostics"] == (
        support_diagnostics_payload
    )


def test_pre_master_mandatory_rectangle_precheck_has_independent_anchor_cap(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_pre_master_rect_cap")
    session = benders_loop_module.create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
    )
    monkeypatch.setenv("EXACT_PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS", "1")

    def _fake_boundary_port_precheck(cls, *, rules, ghost_rect, screen_spec):
        del cls, rules, ghost_rect, screen_spec
        return {
            "supported": True,
            "required_count": 46,
            "considered_anchor_count": 2,
            "screened_infeasible_anchor_count": 0,
            "screen_pass_anchor_count": 2,
            "unsupported_anchor_count": 0,
            "max_packable_min": 46,
            "max_packable_max": 46,
            "first_infeasible_anchor_idx": None,
            "first_infeasible_anchor_max_packable": None,
            "screen_pass_anchor_indices": (0, 1),
            "rebuild_anchor_indices": (0, 1),
        }

    monkeypatch.setattr(
        MasterPlacementModel,
        "evaluate_boundary_port_feasibility_from_screen_spec",
        classmethod(_fake_boundary_port_precheck),
    )
    monkeypatch.setattr(
        MasterPlacementModel,
        "from_exact_core",
        classmethod(
            lambda cls, *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("pre-master mandatory rectangle precheck should be cap-skipped")
            )
        ),
    )

    outcome = benders_loop_module.evaluate_exact_candidate_pre_master_precheck(
        ghost_w=1,
        ghost_h=1,
        exact_session=session,
        master_search_profile="test_profile",
        include_mandatory_rectangle_precheck=True,
    )

    assert outcome == {
        "triggered": False,
        "status": None,
        "proof_summary": {},
        "boundary_port_precheck": {
            "supported": True,
            "required_count": 46,
            "considered_anchor_count": 2,
            "screened_infeasible_anchor_count": 0,
            "screen_pass_anchor_count": 2,
            "unsupported_anchor_count": 0,
            "max_packable_min": 46,
            "max_packable_max": 46,
            "first_infeasible_anchor_idx": None,
            "first_infeasible_anchor_max_packable": None,
            "screen_pass_anchor_indices": (0, 1),
            "rebuild_anchor_indices": (0, 1),
        },
    }


def test_pre_master_coordinate_validation_precheck_defaults_to_disabled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_coordinate_precheck_off")
    session = benders_loop_module.create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
    )
    session.core.candidate_precheck_artifacts = {
        **dict(session.core.candidate_precheck_artifacts),
        "boundary_port_screen_spec": {"supported": True},
    }
    monkeypatch.setenv("EXACT_PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS", "0")

    def _fake_boundary_port_precheck(cls, *, rules, ghost_rect, screen_spec):
        del cls, rules, ghost_rect, screen_spec
        return _mock_supported_boundary_port_precheck_payload((0, 1))

    monkeypatch.setattr(
        MasterPlacementModel,
        "evaluate_boundary_port_feasibility_from_screen_spec",
        classmethod(_fake_boundary_port_precheck),
    )
    monkeypatch.setattr(
        MasterPlacementModel,
        "from_exact_core",
        classmethod(
            lambda cls, *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("coordinate validation precheck should default to disabled")
            )
        ),
    )

    outcome = benders_loop_module.evaluate_exact_candidate_pre_master_precheck(
        ghost_w=1,
        ghost_h=1,
        exact_session=session,
        master_search_profile="test_profile",
        include_mandatory_rectangle_precheck=True,
    )

    assert outcome["triggered"] is False
    assert outcome["status"] is None
    assert outcome["proof_summary"] == {}
    assert outcome["boundary_port_precheck"][
        "screen_pass_anchor_indices"
    ] == (0, 1)


def test_anchor119_row_domain_guard_advisory_helper_skips_when_disabled(
    monkeypatch,
    tmp_path: Path,
) -> None:
    payload: dict[str, object] = {}

    monkeypatch.setattr(
        benders_loop_module,
        "evaluate_phase3b_anchor119_guarded_precheck_advisory",
        lambda **kwargs: {"enabled": False, "proof_summary": {}},
    )

    benders_loop_module._maybe_attach_anchor119_row_domain_guard_advisory(
        payload,
        project_root=tmp_path,
        ghost_w=67,
        ghost_h=13,
    )

    assert payload == {}


def test_pre_master_precheck_can_publish_anchor119_row_domain_guard_advisory_without_trigger(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_anchor119_guard_pre_master")
    session = benders_loop_module.create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
    )

    monkeypatch.setattr(
        benders_loop_module,
        "evaluate_phase3b_anchor119_guarded_precheck_advisory",
        lambda **kwargs: {
            "enabled": True,
            "triggered": False,
            "would_trigger": True,
            "reason": "advisory_guard_would_reject_anchor119",
            "proof_summary": {
                "anchor119_mixed_lane_guarded_precheck": {
                    "advisory_only": True,
                    "runtime_precheck_enabled": False,
                    "runtime_semantics_changed": False,
                    "proof_source": False,
                    "candidate_elimination_claim": False,
                    "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
                    "non_trigger_max_slot_count": 13,
                    "anchored_trigger_min_slot_count": 14,
                    "free_ghost_trigger_min_slot_count": 15,
                }
            },
        },
    )
    outcome = benders_loop_module.evaluate_exact_candidate_pre_master_precheck(
        ghost_w=67,
        ghost_h=13,
        exact_session=session,
        master_search_profile="test_profile",
        include_mandatory_rectangle_precheck=False,
    )

    assert outcome["triggered"] is False
    assert outcome["status"] is None
    advisory = outcome["proof_summary"]["master_candidate_precheck"][
        "anchor119_row_domain_guard_advisory"
    ]
    assert advisory["enabled"] is True
    assert advisory["would_trigger"] is True
    assert advisory["triggered"] is False
    assert advisory["payload_id"] == "anchor119_three_label_overlap_above_strip_count_guard_v0"
    assert advisory["non_trigger_max_slot_count"] == 13


def test_pre_master_precheck_can_short_circuit_when_anchor119_runtime_patch_is_allowed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(
        tmp_path / "toy_anchor119_guard_pre_master_runtime_apply"
    )
    session = benders_loop_module.create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
    )

    monkeypatch.setattr(
        benders_loop_module,
        "evaluate_phase3b_anchor119_guarded_precheck_advisory",
        lambda **kwargs: {
            "enabled": True,
            "triggered": True,
            "would_trigger": True,
            "status": RUN_STATUS_INFEASIBLE,
            "reason": "runtime_guard_reject_anchor119",
            "proof_summary": {
                "anchor119_mixed_lane_guarded_precheck": {
                    "advisory_only": False,
                    "requested_state": "runtime_enabled_reserved",
                    "effective_state": "runtime_enabled_reserved",
                    "runtime_precheck_enabled": True,
                    "runtime_activation_allowed": True,
                    "runtime_enablement_blockers": [],
                    "runtime_semantics_changed": True,
                    "proof_source": True,
                    "candidate_elimination_claim": True,
                    "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
                    "non_trigger_max_slot_count": 13,
                    "anchored_trigger_min_slot_count": 14,
                    "free_ghost_trigger_min_slot_count": 15,
                }
            },
        },
    )
    monkeypatch.setattr(
        benders_loop_module,
        "build_phase3b_anchor119_guard_runtime_state",
        lambda *args, **kwargs: {
            "requested_state": "runtime_enabled_reserved",
            "effective_state": "advisory_enabled",
            "runtime_requested": True,
            "advisory_enabled": True,
            "runtime_precheck_enabled": False,
            "runtime_activation_allowed": False,
            "runtime_enablement_blockers": [
                "reviewed_runtime_patch_missing",
                "production_acceptance_refresh_required",
                "proof_source_promotion_forbidden",
            ],
        },
    )

    outcome = benders_loop_module.evaluate_exact_candidate_pre_master_precheck(
        ghost_w=67,
        ghost_h=13,
        exact_session=session,
        master_search_profile="test_profile",
        include_mandatory_rectangle_precheck=False,
    )

    assert outcome["triggered"] is True
    assert outcome["status"] == RUN_STATUS_INFEASIBLE
    precheck = outcome["proof_summary"]["master_candidate_precheck"]
    assert precheck["triggered"] is True
    assert precheck["precheck_reason"] == "anchor119_row_domain_runtime_guard"
    assert precheck["master_solve_skipped"] is True
    advisory = precheck["anchor119_row_domain_guard_advisory"]
    assert advisory["triggered"] is True
    assert advisory["runtime_decision"]["apply_runtime_elimination"] is True
    assert advisory["runtime_decision"]["blocked_reason"] is None


def test_exact_warm_start_summary_includes_anchor119_row_domain_guard_advisory() -> None:
    controller = object.__new__(benders_loop_module.LBBDController)
    controller._used_greedy_hint = False
    controller._greedy_hint_instances = 0
    controller._master_hinted_literals = 0
    controller._ghost_anchor_hint_applied = False
    controller._ghost_anchor_hint_idx = None
    controller._ghost_anchor_hint_status = "not_used"
    controller._residual_optional_zero_hinting_enabled = True
    controller._residual_optional_zero_hints = 0
    controller._master_start_feasibility = {}
    controller._master_start_local_repair = {}
    controller._master_start_failure_attribution = {}
    controller._master_boundary_port_feasibility = {}
    controller._master_mandatory_support_diagnostics = {}
    controller._master_mandatory_group_prechecks = {}
    controller._master_candidate_precheck = {
        "triggered": False,
        "precheck_reason": None,
        "master_solve_skipped": False,
        "supported": False,
        "considered_anchor_count": 0,
        "screened_infeasible_anchor_count": 0,
        "screen_pass_anchor_count": 0,
        "max_packable_min": None,
        "max_packable_max": None,
        "first_infeasible_anchor_idx": None,
        "first_infeasible_anchor_max_packable": None,
        "triggered_group_id": None,
        "triggered_group_facility_type": None,
        "triggered_group_operation_type": None,
        "triggered_group_required_count": 0,
        "anchor119_row_domain_guard_advisory": {
            "enabled": True,
            "would_trigger": True,
            "triggered": False,
            "reason": "advisory_guard_would_reject_anchor119",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "non_trigger_max_slot_count": 13,
            "anchored_trigger_min_slot_count": 14,
        },
    }
    controller._master_warm_start_disabled = False

    summary = controller._exact_warm_start_summary()

    advisory = summary["master_candidate_precheck"]["anchor119_row_domain_guard_advisory"]
    assert advisory["enabled"] is True
    assert advisory["would_trigger"] is True
    assert advisory["triggered"] is False
    assert advisory["payload_id"] == "anchor119_three_label_overlap_above_strip_count_guard_v0"
    assert advisory["non_trigger_max_slot_count"] == 13


def test_pre_master_coordinate_validation_precheck_short_circuits_all_forced_anchors(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_coordinate_precheck_on")
    session = benders_loop_module.create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
    )
    session.core.candidate_precheck_artifacts = {
        **dict(session.core.candidate_precheck_artifacts),
        "boundary_port_screen_spec": {"supported": True},
    }
    monkeypatch.setenv("EXACT_PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS", "0")
    monkeypatch.setenv("EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS", "2")
    monkeypatch.setenv("EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS", "0.5")
    validation_calls: list[int] = []

    def _fake_boundary_port_precheck(cls, *, rules, ghost_rect, screen_spec):
        del cls, rules, ghost_rect, screen_spec
        return _mock_supported_boundary_port_precheck_payload((0, 1))

    class FakeCoordinateValidationModel:
        def _validate_coordinate_forced_hint(
            self,
            *,
            solution_hint,
            ghost_anchor_hint_idx,
            time_limit_seconds,
            require_complete,
        ):
            assert solution_hint == {}
            assert float(time_limit_seconds) == 0.5
            assert require_complete is False
            validation_calls.append(int(ghost_anchor_hint_idx))
            return {
                "status": "INFEASIBLE",
                "accepted": False,
                "reason": "coordinate_validation_infeasible",
                "forced_slot_field_count": 3,
                "forced_ghost_anchor": True,
                "wall_time": 0.01,
                "branches": 0,
                "conflicts": 0,
            }

    monkeypatch.setattr(
        MasterPlacementModel,
        "evaluate_boundary_port_feasibility_from_screen_spec",
        classmethod(_fake_boundary_port_precheck),
    )
    monkeypatch.setattr(
        MasterPlacementModel,
        "from_exact_core",
        classmethod(lambda cls, *args, **kwargs: FakeCoordinateValidationModel()),
    )
    monkeypatch.setattr(
        benders_loop_module,
        "evaluate_phase3b_anchor119_guarded_precheck_advisory",
        lambda **kwargs: {
            "enabled": True,
            "triggered": False,
            "would_trigger": True,
            "reason": "advisory_guard_would_reject_anchor119",
            "proof_summary": {
                "anchor119_mixed_lane_guarded_precheck": {
                    "advisory_only": True,
                    "runtime_precheck_enabled": False,
                    "runtime_semantics_changed": False,
                    "proof_source": False,
                    "candidate_elimination_claim": False,
                    "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
                    "non_trigger_max_slot_count": 13,
                    "anchored_trigger_min_slot_count": 14,
                    "free_ghost_trigger_min_slot_count": 15,
                }
            },
        },
    )

    outcome = benders_loop_module.evaluate_exact_candidate_pre_master_precheck(
        ghost_w=1,
        ghost_h=1,
        exact_session=session,
        master_search_profile="test_profile",
        include_mandatory_rectangle_precheck=True,
    )

    assert validation_calls == [0, 1]
    assert outcome["triggered"] is True
    assert outcome["status"] == RUN_STATUS_INFEASIBLE
    proof_summary = outcome["proof_summary"]
    assert proof_summary["master_status"] == "INFEASIBLE"
    assert proof_summary["master_candidate_precheck"]["precheck_reason"] == (
        "coordinate_validation_infeasible"
    )
    assert proof_summary["master_candidate_precheck"]["master_solve_skipped"] is True
    assert proof_summary["master_candidate_precheck"][
        "screened_infeasible_anchor_count"
    ] == 2
    assert proof_summary["master_candidate_precheck"]["screen_pass_anchor_count"] == 0
    assert proof_summary["master_candidate_precheck"][
        "first_infeasible_anchor_idx"
    ] == 0
    assert proof_summary["coordinate_validation_precheck"] == {
        "evaluated": True,
        "triggered": True,
        "skipped_due_to_anchor_limit": False,
        "skip_reason": None,
        "time_limit_seconds": 0.5,
        "max_anchor_count": 2,
        "considered_anchor_count": 2,
        "evaluated_anchor_count": 2,
        "infeasible_anchor_count": 2,
        "accepted_anchor_count": 0,
        "unknown_anchor_count": 0,
        "skipped_anchor_count": 0,
        "short_circuited_after_non_triggering_anchor": False,
        "status_counts": {"INFEASIBLE": 2},
        "rejected_anchors": [
            {
                "anchor_idx": 0,
                "status": "INFEASIBLE",
                "accepted": False,
                "reason": "coordinate_validation_infeasible",
                "forced_slot_field_count": 3,
                "forced_ghost_anchor": True,
                "wall_time": 0.01,
                "branches": 0,
                "conflicts": 0,
            },
            {
                "anchor_idx": 1,
                "status": "INFEASIBLE",
                "accepted": False,
                "reason": "coordinate_validation_infeasible",
                "forced_slot_field_count": 3,
                "forced_ghost_anchor": True,
                "wall_time": 0.01,
                "branches": 0,
                "conflicts": 0,
            },
        ],
        "non_triggering_anchors": [],
    }
    advisory = proof_summary["master_candidate_precheck"][
        "anchor119_row_domain_guard_advisory"
    ]
    assert advisory["enabled"] is True
    assert advisory["would_trigger"] is True
    assert advisory["triggered"] is False
    assert advisory["payload_id"] == "anchor119_three_label_overlap_above_strip_count_guard_v0"
    wave_summary = build_wave_summary(
        wave_index=0,
        candidate_results=[
            {
                "candidate_key": "1x1",
                "dispatch_seq": 0,
                "attempt_index": 0,
                "wave_slot_index": 0,
                "selection_reason": "prune_head",
                "status": RUN_STATUS_INFEASIBLE,
                "proof_summary": proof_summary,
            }
        ],
        completed=True,
        failure_reason=None,
        dispatched_candidate_keys=["1x1"],
    )
    compact_coordinate = wave_summary["candidate_results"][0][
        "proof_status_summary"
    ]["coordinate_validation_precheck"]
    assert compact_coordinate == {
        "evaluated": True,
        "triggered": True,
        "skipped_due_to_anchor_limit": False,
        "skip_reason": None,
        "time_limit_seconds": 0.5,
        "max_anchor_count": 2,
        "considered_anchor_count": 2,
        "evaluated_anchor_count": 2,
        "infeasible_anchor_count": 2,
        "accepted_anchor_count": 0,
        "unknown_anchor_count": 0,
        "skipped_anchor_count": 0,
        "short_circuited_after_non_triggering_anchor": False,
        "status_counts": {"INFEASIBLE": 2},
    }


def test_pre_master_coordinate_validation_precheck_falls_back_to_boundary_anchors(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(
        tmp_path / "toy_coordinate_precheck_empty_rebuild"
    )
    session = benders_loop_module.create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
    )
    session.core.candidate_precheck_artifacts = {
        **dict(session.core.candidate_precheck_artifacts),
        "boundary_port_screen_spec": {"supported": True},
    }
    monkeypatch.setenv("EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS", "2")
    validation_calls: list[int] = []
    mandatory_calls: list[tuple[int, ...]] = []

    def _fake_boundary_port_precheck(cls, *, rules, ghost_rect, screen_spec):
        del cls, rules, ghost_rect, screen_spec
        return _mock_supported_boundary_port_precheck_payload((3, 4))

    class FakeCoordinateValidationModel:
        def evaluate_exact_candidate_mandatory_rectangle_prechecks(
            self,
            *,
            anchor_indices,
        ):
            mandatory_calls.append(tuple(int(idx) for idx in anchor_indices))
            return {
                "evaluated": True,
                "skipped_due_to_upstream_precheck": False,
                "upstream_anchor_filter_count": 2,
                "supported_group_count": 0,
                "groups": [],
                "rebuild_anchor_indices": tuple(),
            }

        def _validate_coordinate_forced_hint(
            self,
            *,
            solution_hint,
            ghost_anchor_hint_idx,
            time_limit_seconds,
            require_complete,
        ):
            del solution_hint, time_limit_seconds, require_complete
            validation_calls.append(int(ghost_anchor_hint_idx))
            return {
                "status": "INFEASIBLE",
                "accepted": False,
                "reason": "coordinate_validation_infeasible",
                "forced_ghost_anchor": True,
            }

    monkeypatch.setattr(
        MasterPlacementModel,
        "evaluate_boundary_port_feasibility_from_screen_spec",
        classmethod(_fake_boundary_port_precheck),
    )
    monkeypatch.setattr(
        MasterPlacementModel,
        "from_exact_core",
        classmethod(lambda cls, *args, **kwargs: FakeCoordinateValidationModel()),
    )

    outcome = benders_loop_module.evaluate_exact_candidate_pre_master_precheck(
        ghost_w=1,
        ghost_h=1,
        exact_session=session,
        master_search_profile="test_profile",
        include_mandatory_rectangle_precheck=True,
    )

    assert mandatory_calls == [(3, 4)]
    assert validation_calls == [3, 4]
    assert outcome["triggered"] is True
    assert outcome["proof_summary"]["master_candidate_precheck"]["precheck_reason"] == (
        "coordinate_validation_infeasible"
    )
    assert outcome["proof_summary"]["coordinate_validation_precheck"][
        "considered_anchor_count"
    ] == 2


def test_pre_master_coordinate_validation_precheck_falls_back_to_ghost_domains_when_boundary_unsupported(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(
        tmp_path / "toy_coordinate_precheck_boundary_unsupported"
    )
    session = benders_loop_module.create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
    )
    monkeypatch.setenv("EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS", "2")
    monkeypatch.setenv("EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS", "0.5")
    validation_calls: list[int] = []

    class FakeCoordinateValidationModel:
        _ghost_domains = [{"anchor": {"x": 0, "y": 0}}, {"anchor": {"x": 1, "y": 0}}]

        def _validate_coordinate_forced_hint(
            self,
            *,
            solution_hint,
            ghost_anchor_hint_idx,
            time_limit_seconds,
            require_complete,
        ):
            assert solution_hint == {}
            assert float(time_limit_seconds) == 0.5
            assert require_complete is False
            validation_calls.append(int(ghost_anchor_hint_idx))
            return {
                "status": "INFEASIBLE",
                "accepted": False,
                "reason": "coordinate_validation_infeasible",
                "forced_ghost_anchor": True,
            }

    monkeypatch.setattr(
        MasterPlacementModel,
        "from_exact_core",
        classmethod(lambda cls, *args, **kwargs: FakeCoordinateValidationModel()),
    )

    outcome = benders_loop_module.evaluate_exact_candidate_pre_master_precheck(
        ghost_w=1,
        ghost_h=1,
        exact_session=session,
        master_search_profile="test_profile",
        include_mandatory_rectangle_precheck=True,
    )

    assert validation_calls == [0, 1]
    assert outcome["triggered"] is True
    assert outcome["status"] == RUN_STATUS_INFEASIBLE
    assert outcome["proof_summary"]["master_candidate_precheck"]["precheck_reason"] == (
        "coordinate_validation_infeasible"
    )
    assert outcome["proof_summary"]["coordinate_validation_precheck"][
        "considered_anchor_count"
    ] == 2


def test_pre_master_coordinate_validation_precheck_does_not_trigger_on_unknown_anchor(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_coordinate_precheck_mixed")
    session = benders_loop_module.create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
    )
    session.core.candidate_precheck_artifacts = {
        **dict(session.core.candidate_precheck_artifacts),
        "boundary_port_screen_spec": {"supported": True},
    }
    monkeypatch.setenv("EXACT_PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS", "0")
    monkeypatch.setenv("EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS", "2")
    validation_calls: list[int] = []

    def _fake_boundary_port_precheck(cls, *, rules, ghost_rect, screen_spec):
        del cls, rules, ghost_rect, screen_spec
        return _mock_supported_boundary_port_precheck_payload((0, 1))

    class FakeCoordinateValidationModel:
        def _validate_coordinate_forced_hint(
            self,
            *,
            solution_hint,
            ghost_anchor_hint_idx,
            time_limit_seconds,
            require_complete,
        ):
            del solution_hint, time_limit_seconds, require_complete
            anchor_idx = int(ghost_anchor_hint_idx)
            validation_calls.append(anchor_idx)
            if anchor_idx == 0:
                return {
                    "status": "INFEASIBLE",
                    "accepted": False,
                    "reason": "coordinate_validation_infeasible",
                    "forced_ghost_anchor": True,
                }
            return {
                "status": "UNKNOWN",
                "accepted": False,
                "reason": "time_budget_exhausted",
                "forced_ghost_anchor": True,
            }

    monkeypatch.setattr(
        MasterPlacementModel,
        "evaluate_boundary_port_feasibility_from_screen_spec",
        classmethod(_fake_boundary_port_precheck),
    )
    monkeypatch.setattr(
        MasterPlacementModel,
        "from_exact_core",
        classmethod(lambda cls, *args, **kwargs: FakeCoordinateValidationModel()),
    )

    outcome = benders_loop_module.evaluate_exact_candidate_pre_master_precheck(
        ghost_w=1,
        ghost_h=1,
        exact_session=session,
        master_search_profile="test_profile",
        include_mandatory_rectangle_precheck=True,
    )

    assert validation_calls == [0, 1]
    assert outcome == {
        "triggered": False,
        "status": None,
        "proof_summary": {},
        "boundary_port_precheck": _mock_supported_boundary_port_precheck_payload((0, 1)),
    }


def test_pre_master_coordinate_validation_precheck_stops_after_first_non_trigger() -> None:
    validation_calls: list[int] = []

    class FakeCoordinateValidationModel:
        def _validate_coordinate_forced_hint(
            self,
            *,
            solution_hint,
            ghost_anchor_hint_idx,
            time_limit_seconds,
            require_complete,
        ):
            del solution_hint, time_limit_seconds, require_complete
            validation_calls.append(int(ghost_anchor_hint_idx))
            return {
                "status": "UNKNOWN",
                "accepted": False,
                "reason": "unknown",
                "forced_ghost_anchor": True,
            }

    payload = benders_loop_module._evaluate_coordinate_validation_forced_anchor_precheck(
        FakeCoordinateValidationModel(),
        anchor_indices=(10, 11, 12),
        time_limit_seconds=0.5,
        max_anchor_count=3,
    )

    assert validation_calls == [10]
    assert payload["evaluated"] is True
    assert payload["triggered"] is False
    assert payload["considered_anchor_count"] == 3
    assert payload["evaluated_anchor_count"] == 1
    assert payload["unknown_anchor_count"] == 1
    assert payload["status_counts"] == {"UNKNOWN": 1}
    assert payload["short_circuited_after_non_triggering_anchor"] is True


def test_pre_master_coordinate_validation_precheck_skips_before_overlay_when_cap_exceeded(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_coordinate_precheck_cap")
    session = benders_loop_module.create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
    )
    session.core.candidate_precheck_artifacts = {
        **dict(session.core.candidate_precheck_artifacts),
        "boundary_port_screen_spec": {"supported": True},
    }
    monkeypatch.setenv("EXACT_PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS", "0")
    monkeypatch.setenv("EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS", "2")

    def _fake_boundary_port_precheck(cls, *, rules, ghost_rect, screen_spec):
        del cls, rules, ghost_rect, screen_spec
        return _mock_supported_boundary_port_precheck_payload((0, 1, 2))

    monkeypatch.setattr(
        MasterPlacementModel,
        "evaluate_boundary_port_feasibility_from_screen_spec",
        classmethod(_fake_boundary_port_precheck),
    )
    monkeypatch.setattr(
        MasterPlacementModel,
        "from_exact_core",
        classmethod(
            lambda cls, *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("coordinate validation precheck should skip before overlay")
            )
        ),
    )

    outcome = benders_loop_module.evaluate_exact_candidate_pre_master_precheck(
        ghost_w=1,
        ghost_h=1,
        exact_session=session,
        master_search_profile="test_profile",
        include_mandatory_rectangle_precheck=True,
    )

    assert outcome["triggered"] is False
    assert outcome["status"] is None
    assert outcome["proof_summary"] == {}
    assert outcome["boundary_port_precheck"][
        "screen_pass_anchor_indices"
    ] == (0, 1, 2)


def test_benders_proof_summary_failed_anchor_sample_limit_env(monkeypatch) -> None:
    monkeypatch.setenv("EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT", "64")
    assert benders_loop_module._warm_start_failed_anchor_sample_limit() == 64

    monkeypatch.setenv("EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT", "0")
    assert benders_loop_module._warm_start_failed_anchor_sample_limit() == 0


def test_boundary_port_precheck_keeps_priority_over_mandatory_rectangle_precheck(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_precheck_priority")
    session = benders_loop_module.create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
    )
    support_diagnostics_payload = {
        "unsupported_group_count": 0,
        "empty_candidate_pool_group_count": 0,
        "groups": [
            {
                "group_id": "group::tiny_facility::::0",
                "facility_type": "tiny_facility",
                "operation_type": "",
                "required_count": 1,
                "candidate_pool_count": 1,
                "unsupported_reason": None,
            }
        ],
    }
    session.core.candidate_precheck_artifacts = {
        **dict(session.core.candidate_precheck_artifacts),
        "mandatory_support_diagnostics": dict(support_diagnostics_payload),
    }

    def _fake_boundary_port_precheck(cls, *, rules, ghost_rect, screen_spec):
        del cls, rules, ghost_rect, screen_spec
        return {
            "supported": True,
            "required_count": 46,
            "considered_anchor_count": 3,
            "screened_infeasible_anchor_count": 3,
            "screen_pass_anchor_count": 0,
            "unsupported_anchor_count": 0,
            "max_packable_min": 17,
            "max_packable_max": 39,
            "first_infeasible_anchor_idx": 0,
            "first_infeasible_anchor_max_packable": 17,
            "screen_pass_anchor_indices": (),
            "rebuild_anchor_indices": tuple(),
        }

    monkeypatch.setattr(
        MasterPlacementModel,
        "evaluate_boundary_port_feasibility_from_screen_spec",
        classmethod(_fake_boundary_port_precheck),
    )
    monkeypatch.setattr(
        MasterPlacementModel,
        "from_exact_core",
        classmethod(
            lambda cls, *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("from_exact_core should be skipped when boundary precheck wins")
            )
        ),
    )

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        session=session,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        max_iterations=1,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")
    proof_summary = metadata["proof_summary"]

    assert status == RUN_STATUS_INFEASIBLE
    assert result is None
    assert proof_summary["master_candidate_precheck"]["precheck_reason"] == (
        "boundary_port_all_anchors_infeasible"
    )
    assert proof_summary["master_mandatory_group_prechecks"] == {
        "evaluated": False,
        "skipped_due_to_upstream_precheck": True,
        "upstream_anchor_filter_count": 0,
        "supported_group_count": 0,
        "groups": [],
    }
    assert proof_summary["master_mandatory_support_diagnostics"] == (
        support_diagnostics_payload
    )


def test_empty_pool_precheck_keeps_priority_over_boundary_and_mandatory_rectangle_precheck(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_empty_pool_precheck")
    session = benders_loop_module.create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
    )
    support_diagnostics_payload = {
        "unsupported_group_count": 1,
        "empty_candidate_pool_group_count": 1,
        "groups": [
            {
                "group_id": "group::protocol_core::protocol_core::0",
                "facility_type": "protocol_core",
                "operation_type": "protocol_core",
                "required_count": 1,
                "candidate_pool_count": 0,
                "unsupported_reason": "empty_candidate_pool",
            }
        ],
    }
    session.core.candidate_precheck_artifacts = {
        **dict(session.core.candidate_precheck_artifacts),
        "mandatory_support_diagnostics": dict(support_diagnostics_payload),
    }

    monkeypatch.setattr(
        MasterPlacementModel,
        "evaluate_boundary_port_feasibility_from_screen_spec",
        classmethod(
            lambda cls, *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("boundary precheck should be skipped by empty-pool precheck")
            )
        ),
    )
    monkeypatch.setattr(
        MasterPlacementModel,
        "from_exact_core",
        classmethod(
            lambda cls, *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("from_exact_core should be skipped by empty-pool precheck")
            )
        ),
    )

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        session=session,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        max_iterations=1,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")
    proof_summary = metadata["proof_summary"]

    assert status == RUN_STATUS_INFEASIBLE
    assert result is None
    assert proof_summary["master_candidate_precheck"] == {
        "triggered": True,
        "precheck_reason": "mandatory_group_empty_candidate_pool",
        "master_solve_skipped": True,
        "supported": False,
        "considered_anchor_count": 0,
        "screened_infeasible_anchor_count": 0,
        "screen_pass_anchor_count": 0,
        "max_packable_min": None,
        "max_packable_max": None,
        "first_infeasible_anchor_idx": None,
        "first_infeasible_anchor_max_packable": None,
        "triggered_group_id": "group::protocol_core::protocol_core::0",
        "triggered_group_facility_type": "protocol_core",
        "triggered_group_operation_type": "protocol_core",
        "triggered_group_required_count": 1,
    }
    assert proof_summary["master_mandatory_group_prechecks"] == {
        "evaluated": False,
        "skipped_due_to_upstream_precheck": False,
        "upstream_anchor_filter_count": 0,
        "supported_group_count": 0,
        "groups": [],
    }
    assert proof_summary["master_mandatory_support_diagnostics"] == (
        support_diagnostics_payload
    )
    assert proof_summary["overlay_build_seconds"] == 0.0
    assert proof_summary["ghost_constraint_seconds"] == 0.0
    assert proof_summary["cut_replay_seconds"] == 0.0
    assert classify_candidate_outcome(status=status, proof_summary=proof_summary) == "master_infeasible"



def test_campaign_resume_requires_matching_hashes(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "campaign_hash")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.save()

    _write_json(
        project_root / "data" / "preprocessed" / "generic_io_requirements.json",
        {
            "required_generic_outputs": {"ore": 1},
            "required_generic_inputs": {},
        },
    )
    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)
    assert resumed.resumed is False
    assert resumed.compatible_hashes is False
    assert resumed.reset_reason == "artifact_hash_mismatch"


def test_campaign_resume_resets_on_schema_mismatch(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "campaign_schema_mismatch")
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    campaign_path.parent.mkdir(parents=True, exist_ok=True)
    campaign_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "solve_mode": "certified_exact",
                "campaign_hours": 1.0,
                "created_at": "2026-03-16T00:00:00Z",
                "updated_at": "2026-03-16T00:00:00Z",
                "artifact_hashes": ExactCampaign.load_or_create(
                    project_root,
                    campaign_hours=1.0,
                    resume=False,
                ).artifact_hashes,
                "proof_summary_schema_version": 1,
                "reset_reason": None,
                "final_result": None,
                "final_status": None,
                "last_stop_reason": None,
                "candidates": {},
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)
    assert resumed.resumed is False
    assert resumed.compatible_hashes is False
    assert resumed.reset_reason == "schema_version_mismatch"


def test_campaign_resume_keeps_valid_candidates(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "campaign_keep_valid")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_INFEASIBLE,
        proof_summary={"reason": "toy_infeasible"},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution={"tiny_001": {"pose_idx": 0, "pose_id": "tiny_left", "facility_type": "tiny_facility"}},
        proof_summary={"reason": "toy_certified"},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.save()

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)
    assert resumed.resumed is True
    assert resumed.compatible_hashes is True
    assert resumed.get_candidate_record(1, 1)["status"] == RUN_STATUS_INFEASIBLE
    assert resumed.get_candidate_record(2, 1)["status"] == RUN_STATUS_CERTIFIED
    assert resumed.get_candidate_record(2, 1)["solution"]["tiny_001"]["pose_id"] == "tiny_left"
    assert resumed.best_certified_result() is None


def test_campaign_save_is_atomic_and_resumeable(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "campaign_atomic_save")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_INFEASIBLE,
        proof_summary={"master_status": "INFEASIBLE"},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.save()
    campaign.save()

    checkpoints_dir = project_root / "data" / "checkpoints"
    assert list(checkpoints_dir.glob(".exact_campaign_state.json.tmp-*.json")) == []

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)
    assert resumed.resumed is True
    assert resumed.compatible_hashes is True
    assert resumed.get_candidate_record(1, 1)["status"] == RUN_STATUS_INFEASIBLE


def test_campaign_keeps_certified_candidate_records_without_terminal_final_result(
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "campaign_best_certified_monotone")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)

    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution={
            "big_pick": {
                "pose_idx": 0,
                "pose_id": "big_pick",
                "facility_type": "synthetic",
                "anchor": {"x": 0, "y": 0},
            }
        },
        proof_summary={"master_status": "CERTIFIED"},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={
            "small_pick": {
                "pose_idx": 0,
                "pose_id": "small_pick",
                "facility_type": "synthetic",
                "anchor": {"x": 0, "y": 0},
            }
        },
        proof_summary={"master_status": "CERTIFIED"},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.save()

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)
    assert resumed.resumed is True
    assert resumed.compatible_hashes is True
    assert resumed.state["final_status"] is None
    assert resumed.state.get("final_result") is None
    assert resumed.best_certified_result() is None
    assert resumed.get_candidate_record(1, 1)["status"] == RUN_STATUS_CERTIFIED
    assert resumed.get_candidate_record(2, 1)["status"] == RUN_STATUS_CERTIFIED


def test_campaign_does_not_export_certified_result_when_later_terminal_status_is_unknown(
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "campaign_best_certified_unknown_stop")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)

    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution={
            "big_pick": {
                "pose_idx": 0,
                "pose_id": "big_pick",
                "facility_type": "synthetic",
                "anchor": {"x": 0, "y": 0},
            }
        },
        proof_summary={"master_status": "CERTIFIED"},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.mark_candidate_started(3, 1)
    campaign.mark_candidate_result(
        3,
        1,
        RUN_STATUS_UNKNOWN,
        proof_summary={"master_status": "UNKNOWN"},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.mark_campaign_stopped("candidate_returned_unknown", status=RUN_STATUS_UNKNOWN)
    campaign.save()

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)
    assert resumed.resumed is True
    assert resumed.compatible_hashes is True
    assert resumed.state["final_status"] == RUN_STATUS_UNKNOWN
    assert resumed.state["last_stop_reason"]["reason"] == "candidate_returned_unknown"
    assert resumed.state.get("final_result") is None
    assert resumed.best_certified_result() is None



def test_toy_project_can_be_truly_certified(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_certified")
    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=1,
        min_side=1,
        area_upper_bound=1,
        master_seconds=5.0,
        binding_seconds=5.0,
        routing_seconds=5.0,
        benders_max_iter=5,
        campaign_hours=1.0,
        resume_campaign=False,
    )
    assert status == RUN_STATUS_CERTIFIED
    assert result is not None
    assert result["ghost_rect"] == {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0}
    state = _read_campaign_state(project_root)
    candidate = state["candidates"]["1x1"]
    assert state["final_status"] == RUN_STATUS_CERTIFIED
    assert candidate["status"] == RUN_STATUS_CERTIFIED
    assert candidate["finished_at"] is not None


def test_area_precheck_accounts_for_fixed_required_protocol_storage_box(
    tmp_path: Path,
) -> None:
    project_root = _build_required_protocol_box_project(tmp_path / "required_box_area_precheck")

    status, result = run_benders_for_ghost_rect(
        ghost_w=2,
        ghost_h=2,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=5.0,
        binding_seconds=5.0,
        routing_seconds=5.0,
        max_iterations=1,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")

    assert status == RUN_STATUS_INFEASIBLE
    assert result is None
    assert metadata["proof_summary"]["master_status"] == "AREA_PRECHECK_FAILED"
    assert metadata["generated_exact_safe_cut_count"] == 0


def test_outer_search_safe_area_upper_bound_accounts_for_fixed_required_protocol_storage_box(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_required_protocol_box_project(tmp_path / "required_box_outer_search")
    calls: list[tuple[int, int]] = []

    def fake_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        del session, kwargs
        calls.append((ghost_w, ghost_h))
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {"mode": "certified_exact", "master_status": "INFEASIBLE"},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        return RUN_STATUS_INFEASIBLE, None

    fake_run_benders_for_ghost_rect.last_run_metadata = {
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }

    monkeypatch.setattr(outer_search_module, "run_benders_for_ghost_rect", fake_run_benders_for_ghost_rect)
    monkeypatch.setattr(
        outer_search_module.ExactSearchSession,
        "create",
        staticmethod(lambda project_root, solve_mode="certified_exact": object()),
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=8,
        min_side=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )

    assert status == RUN_STATUS_INFEASIBLE
    assert result is None
    assert (2, 2) not in calls
    assert all((ghost_w * ghost_h) <= 3 for ghost_w, ghost_h in calls)


def test_outer_search_persists_anchor119_row_domain_guard_advisory_in_proof_summary(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(
        tmp_path / "frontier_anchor119_guard_advisory",
        width=2,
        height=1,
    )
    calls: list[tuple[int, int]] = []

    def fake_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        del session, kwargs
        calls.append((ghost_w, ghost_h))
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": RUN_STATUS_UNKNOWN,
                "master_candidate_precheck": {
                    "triggered": False,
                    "precheck_reason": None,
                    "master_solve_skipped": False,
                    "anchor119_row_domain_guard_advisory": {
                        "enabled": True,
                        "would_trigger": True,
                        "triggered": False,
                        "reason": "advisory_guard_would_reject_anchor119",
                        "requested_state": "advisory_enabled",
                        "effective_state": "advisory_enabled",
                        "runtime_activation_allowed": False,
                        "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
                        "non_trigger_max_slot_count": 13,
                        "anchored_trigger_min_slot_count": 14,
                        "free_ghost_trigger_min_slot_count": 15,
                        "runtime_enablement_blockers": [
                            "reviewed_runtime_patch_missing",
                            "production_acceptance_refresh_required",
                            "proof_source_promotion_forbidden",
                        ],
                        "runtime_decision": {
                            "decision_id": "anchor119_row_domain_runtime_decision_v0",
                            "requested_state": "advisory_enabled",
                            "effective_state": "advisory_enabled",
                            "would_trigger": True,
                            "triggered": False,
                            "runtime_activation_allowed": False,
                            "apply_runtime_elimination": False,
                            "blocked_reason": "runtime_activation_not_allowed",
                            "reason": "advisory_guard_would_reject_anchor119",
                            "runtime_enablement_blockers": [
                                "reviewed_runtime_patch_missing",
                                "production_acceptance_refresh_required",
                                "proof_source_promotion_forbidden",
                            ],
                        },
                    },
                },
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        return RUN_STATUS_UNKNOWN, None

    fake_run_benders_for_ghost_rect.last_run_metadata = {
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }

    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        fake_run_benders_for_ghost_rect,
    )
    monkeypatch.setattr(
        outer_search_module.ExactSearchSession,
        "create",
        staticmethod(lambda project_root, solve_mode="certified_exact": object()),
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=1,
        min_side=1,
        area_upper_bound=2,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert calls
    telemetry = _read_campaign_telemetry(project_root)
    candidate_result = telemetry["waves"][0]["candidate_results"][0]
    advisory = candidate_result["proof_status_summary"]["master_candidate_precheck"][
        "anchor119_row_domain_guard_advisory"
    ]
    assert advisory["enabled"] is True
    assert advisory["would_trigger"] is True
    assert advisory["triggered"] is False
    assert advisory["requested_state"] == "advisory_enabled"
    assert advisory["effective_state"] == "advisory_enabled"
    assert advisory["runtime_activation_allowed"] is False
    assert advisory["runtime_decision"]["apply_runtime_elimination"] is False
    assert advisory["runtime_decision"]["blocked_reason"] == "runtime_activation_not_allowed"
    assert advisory["payload_id"] == "anchor119_three_label_overlap_above_strip_count_guard_v0"

    state = _read_campaign_state(project_root)
    candidate_key = f"{calls[0][0]}x{calls[0][1]}"
    state_advisory = state["candidates"][candidate_key]["proof_summary"][
        "master_candidate_precheck"
    ]["anchor119_row_domain_guard_advisory"]
    assert state_advisory["reason"] == "advisory_guard_would_reject_anchor119"
    assert state_advisory["non_trigger_max_slot_count"] == 13


def test_exact_mode_uses_greedy_warm_start(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_greedy_hint")

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=5.0,
        binding_seconds=5.0,
        routing_seconds=5.0,
        max_iterations=2,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")

    assert status == RUN_STATUS_CERTIFIED
    assert result is not None
    assert metadata["proof_summary"]["used_greedy_hint"] is True
    assert metadata["proof_summary"]["greedy_hint_instances"] == 1
    assert metadata["proof_summary"]["master_hinted_literals"] > 0
    assert "master_warm_start" in metadata["proof_summary"]
    assert metadata["proof_summary"]["master_warm_start"]["used_greedy_hint"] is True
    assert metadata["proof_summary"]["master_warm_start"]["greedy_hint_instances"] == 1
    assert metadata["proof_summary"]["master_warm_start"]["ghost_anchor_hint_status"] in {
        "applied",
        "none_compatible",
        "no_ghost_rect",
    }
    assert metadata["proof_summary"]["master_warm_start"]["warm_start_strategy"] in {
        "ghost_aware_mandatory_rebuild",
        "ghost_aware_local_repair",
        "ghost_aware_pose_order_portfolio",
        "global_greedy_fallback",
        "no_ghost_rect",
        "unsupported",
    }
    assert metadata["proof_summary"]["master_warm_start"][
        "residual_optional_zero_hinting_enabled"
    ] is False
    assert metadata["proof_summary"]["master_start_feasibility"]["ghost_anchor_total_count"] >= 0
    assert metadata["proof_summary"]["master_start_feasibility"][
        "mandatory_hint_pose_count"
    ] == 1
    assert (
        metadata["proof_summary"]["master_start_feasibility"][
            "mandatory_hint_occupied_cell_count"
        ]
        >= 1
    )
    assert metadata["proof_summary"]["master_start_feasibility"][
        "warm_start_strategy"
    ] == metadata["proof_summary"]["master_warm_start"]["warm_start_strategy"]
    assert "master_start_failure_attribution" in metadata["proof_summary"]
    assert metadata["proof_summary"]["master_start_failure_attribution"][
        "attempted_anchor_count"
    ] >= 0
    assert "master_start_local_repair" in metadata["proof_summary"]
    assert metadata["proof_summary"]["master_start_local_repair"][
        "local_repair_portfolio_attempt_count"
    ] >= 0
    assert "master_boundary_port_feasibility" in metadata["proof_summary"]
    assert metadata["proof_summary"]["master_boundary_port_feasibility"][
        "considered_anchor_count"
    ] >= 0
    assert "master_domain_activation" in metadata["proof_summary"]
    assert (
        metadata["proof_summary"]["master_domain_activation"]["ghost_anchor_count"] >= 0
    )


def test_exact_path_publishes_anchor119_row_domain_guard_advisory_metadata(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_anchor119_guard_advisory")
    advisory_calls: list[tuple[int, int, int | None]] = []

    def fake_guard_advisory(
        *,
        project_root: Path,
        ghost_w: int,
        ghost_h: int,
        anchor_idx=None,
        spec_path=None,
        enabled=None,
        current_hashes=None,
    ):
        del project_root, spec_path, enabled, current_hashes
        advisory_calls.append((int(ghost_w), int(ghost_h), anchor_idx))
        return {
            "enabled": True,
            "triggered": False,
            "would_trigger": True,
            "reason": "advisory_guard_would_reject_anchor119",
            "proof_summary": {
                "anchor119_mixed_lane_guarded_precheck": {
                    "advisory_only": True,
                    "runtime_precheck_enabled": False,
                    "requested_state": "advisory_enabled",
                    "effective_state": "advisory_enabled",
                    "runtime_activation_allowed": False,
                    "runtime_semantics_changed": False,
                    "proof_source": False,
                    "candidate_elimination_claim": False,
                    "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
                    "non_trigger_max_slot_count": 13,
                    "anchored_trigger_min_slot_count": 14,
                    "free_ghost_trigger_min_slot_count": 15,
                    "runtime_enablement_blockers": [
                        "reviewed_runtime_patch_missing",
                        "production_acceptance_refresh_required",
                        "proof_source_promotion_forbidden",
                    ],
                    "runtime_decision": {
                        "decision_id": "anchor119_row_domain_runtime_decision_v0",
                        "requested_state": "advisory_enabled",
                        "effective_state": "advisory_enabled",
                        "would_trigger": True,
                        "triggered": False,
                        "runtime_activation_allowed": False,
                        "apply_runtime_elimination": False,
                        "blocked_reason": "runtime_activation_not_allowed",
                        "reason": "advisory_guard_would_reject_anchor119",
                        "runtime_enablement_blockers": [
                            "reviewed_runtime_patch_missing",
                            "production_acceptance_refresh_required",
                            "proof_source_promotion_forbidden",
                        ],
                    },
                }
            },
        }

    monkeypatch.setattr(
        benders_loop_module,
        "evaluate_phase3b_anchor119_guarded_precheck_advisory",
        fake_guard_advisory,
    )

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=5.0,
        binding_seconds=5.0,
        routing_seconds=5.0,
        max_iterations=2,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")

    assert status == RUN_STATUS_CERTIFIED
    assert result is not None
    assert advisory_calls == [(1, 1, 119)]
    advisory = metadata["proof_summary"]["master_candidate_precheck"][
        "anchor119_row_domain_guard_advisory"
    ]
    assert advisory["enabled"] is True
    assert advisory["would_trigger"] is True
    assert advisory["triggered"] is False
    assert advisory["reason"] == "advisory_guard_would_reject_anchor119"
    assert advisory["requested_state"] == "advisory_enabled"
    assert advisory["effective_state"] == "advisory_enabled"
    assert advisory["runtime_activation_allowed"] is False
    assert advisory["runtime_decision"]["apply_runtime_elimination"] is False
    assert advisory["runtime_decision"]["blocked_reason"] == "runtime_activation_not_allowed"
    assert advisory["payload_id"] == "anchor119_three_label_overlap_above_strip_count_guard_v0"
    assert advisory["non_trigger_max_slot_count"] == 13
    assert advisory["anchored_trigger_min_slot_count"] == 14
    assert advisory["free_ghost_trigger_min_slot_count"] == 15


def test_ghost_rect_can_screen_high_capacity_pole_in_exact_master() -> None:
    instances = [
        {
            "instance_id": "powered_001",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "powered_002",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "power_pole": [
            {
                "pose_id": "pole_high",
                "anchor": {"x": 0, "y": 1},
                "occupied_cells": [[0, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[0, 0], [1, 0], [3, 0], [4, 0]],
            },
            {
                "pose_id": "pole_low",
                "anchor": {"x": 5, "y": 1},
                "occupied_cells": [[5, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[0, 0], [1, 0], [2, 0]],
            },
        ],
        "protocol_storage_box": [],
        "powered_machine": [
            {
                "pose_id": "machine_a",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0], [1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "machine_b",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0], [2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "machine_c",
                "anchor": {"x": 3, "y": 0},
                "occupied_cells": [[3, 0], [4, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
    }
    rules = {
        "globals": {"grid": {"width": 6, "height": 2}, "empty_rectangle": {"objective": "max_lex_area_min_side", "min_side_admissibility": 1}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "powered_machine": {"dimensions": {"w": 2, "h": 1}, "needs_power": True},
        },
    }

    baseline_model = MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
    )
    baseline_model.build()
    assert baseline_model.solve(time_limit_seconds=5.0) in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    ghost_model = MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
    )
    ghost_model.build()
    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(ghost_model._ghost_domains)
        if domain["anchor"] == {"x": 0, "y": 1}
    )
    ghost_model.model.Add(ghost_model.u_vars[forced_anchor_idx] == 1)
    stats = ghost_model.build_stats["global_valid_inequalities"]

    assert stats["ghost_aware_via_pole_feasibility"]["enabled"] is True
    assert stats["ghost_aware_via_pole_feasibility"]["explicit_u_conditioning"] is True
    assert stats["ghost_aware_via_pole_feasibility"]["disabled_placements"] >= 1
    assert stats["ghost_aware_via_pole_feasibility"]["surviving_placements"] >= 1
    assert stats["ghost_aware_via_pole_feasibility"]["conditioned_family_upper_bound_constraints"] > 0
    assert stats["ghost_aware_via_pole_feasibility"]["family_reduction_anchor_count"] > 0
    assert stats["ghost_aware_via_pole_feasibility"]["template_fail_counts"] == {
        "powered_machine": 1
    }
    assert stats["capacity_coeff_stats"]["powered_machine"]["max_coeff"] == 2
    assert stats["capacity_coeff_stats"]["powered_machine"]["min_nonzero_coeff"] == 1
    assert ghost_model.build_stats["ghost_rect"]["power_capacity_screened_disabled_placements"] >= 1
    assert ghost_model.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_fully_enclosed_ghost_rectangle_is_legal() -> None:
    ring_cells = [
        (0, 0), (1, 0), (2, 0), (3, 0),
        (0, 1),                 (3, 1),
        (0, 2),                 (3, 2),
        (0, 3), (1, 3), (2, 3), (3, 3),
    ]
    instances = [
        {
            "instance_id": f"wall_{idx:03d}",
            "facility_type": "wall",
            "operation_type": "blocking",
            "is_mandatory": True,
            "bound_type": "exact",
        }
        for idx, _cell in enumerate(ring_cells, start=1)
    ]
    pools = {
        "wall": [
            {
                "pose_id": f"wall_{x}_{y}",
                "anchor": {"x": x, "y": y},
                "occupied_cells": [[x, y]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
            for x, y in ring_cells
        ]
    }
    rules = {
        "globals": {"grid": {"width": 4, "height": 4}, "empty_rectangle": {"objective": "max_lex_area_min_side", "min_side_admissibility": 1}},
        "facility_templates": {
            "wall": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }

    model = MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=(2, 2),
        skip_power_coverage=True,
    )
    model.build()

    status = model.solve(time_limit_seconds=5.0)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    selected_anchor = None
    assert model._solver is not None
    for idx, domain in enumerate(model._ghost_domains):
        if model._solver.Value(model.u_vars[idx]) == 1:
            selected_anchor = domain["anchor"]
            break

    assert selected_anchor == {"x": 1, "y": 1}


def test_exact_mode_uses_flow_only_as_diagnostic(monkeypatch, tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_flow_diag")

    monkeypatch.setattr(
        benders_loop_module.FlowSubproblem,
        "build_and_solve",
        lambda self, time_limit_ms=10000: "INFEASIBLE",
    )

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=5.0,
        binding_seconds=5.0,
        routing_seconds=5.0,
        flow_seconds=1.0,
        max_iterations=2,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")

    assert status == RUN_STATUS_CERTIFIED
    assert result is not None
    assert metadata["proof_summary"]["diagnostic_flow_status"] == "INFEASIBLE"
    assert metadata["exact_safe_cuts"] == []
    assert metadata["loaded_exact_safe_cut_count"] == 0
    assert metadata["generated_exact_safe_cut_count"] == 0
    assert metadata["diagnostic_flow_status"] == "INFEASIBLE"


def test_binding_infeasible_generates_exact_safe_whole_layout_cut(monkeypatch, tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_binding_infeasible")

    class FakeBindingModel:
        def __init__(self, *args, **kwargs):
            self._summary = {"fake": "binding_infeasible"}

        def build(self) -> None:
            return None

        def solve(self, time_limit_seconds: float = 30.0) -> str:
            return "INFEASIBLE"

        def extract_conflict_summary(self) -> dict:
            return dict(self._summary)

    monkeypatch.setattr(benders_loop_module, "PortBindingModel", FakeBindingModel)

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=5.0,
        binding_seconds=5.0,
        routing_seconds=5.0,
        max_iterations=2,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")
    cuts = metadata["exact_safe_cuts"]

    assert status == RUN_STATUS_INFEASIBLE
    assert result is None
    assert len(cuts) == 1
    assert cuts[0]["cut_type"] == "binding_infeasible_nogood"
    assert cuts[0]["proof_stage"] == "binding"
    assert cuts[0]["binding_exhausted"] is True
    assert cuts[0]["routing_exhausted"] is False
    assert metadata["loaded_exact_safe_cut_count"] == 0
    assert metadata["generated_exact_safe_cut_count"] == 1


def test_routing_exhaustion_generates_exact_safe_whole_layout_cut(monkeypatch, tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_routing_exhausted")

    selections = [
        {
            "binding_choice": {"tiny_001": 0},
            "generic_inputs": {},
            "generic_outputs": {},
        },
        {
            "binding_choice": {"tiny_001": 1},
            "generic_inputs": {},
            "generic_outputs": {},
        },
    ]

    class FakeBindingModel:
        def __init__(self, *args, **kwargs):
            self.index = 0
            self.binding_vars = {"tiny_001": {0: object(), 1: object()}}
            self.generic_input_vars = {}
            self.generic_output_vars = {}

        def build(self) -> None:
            return None

        def solve(self, time_limit_seconds: float = 30.0) -> str:
            if self.index < len(selections):
                return "FEASIBLE"
            return "INFEASIBLE"

        def extract_selection(self) -> dict:
            return dict(selections[self.index])

        def extract_port_specs(self) -> list[dict]:
            return []

        def add_nogood_cut(self, selection: dict) -> None:
            assert selection == selections[self.index]
            self.index += 1

        def extract_conflict_summary(self) -> dict:
            return {"enumerated": self.index}

    class FakeRoutingGrid:
        def __init__(self, occupied_cells, port_specs):
            self.occupied_cells = occupied_cells
            self.port_specs = port_specs

    class FakeRoutingSubproblem:
        solve_calls = 0

        def __init__(self, grid, commodities):
            self.grid = grid
            self.commodities = commodities
            self.build_stats = {"fake": "routing"}

        def build(self) -> None:
            return None

        def solve(self, time_limit: float = 60.0) -> str:
            FakeRoutingSubproblem.solve_calls += 1
            return "INFEASIBLE"

    monkeypatch.setattr(benders_loop_module, "PortBindingModel", FakeBindingModel)
    monkeypatch.setattr(benders_loop_module, "RoutingGrid", FakeRoutingGrid)
    monkeypatch.setattr(benders_loop_module, "RoutingSubproblem", FakeRoutingSubproblem)

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=5.0,
        binding_seconds=5.0,
        routing_seconds=5.0,
        max_iterations=2,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")
    cuts = metadata["exact_safe_cuts"]

    assert status == RUN_STATUS_INFEASIBLE
    assert result is None
    assert FakeRoutingSubproblem.solve_calls == 2
    assert len(cuts) == 1
    assert cuts[0]["cut_type"] == "routing_exhausted_nogood"
    assert cuts[0]["proof_stage"] == "routing"
    assert cuts[0]["binding_exhausted"] is True
    assert cuts[0]["routing_exhausted"] is True
    # V83: routing exhaustion no longer short-circuits the candidate; the
    # whole-layout nogood is applied and LBBD continues, so the final
    # INFEASIBLE comes from the master proving the cut-augmented model empty.
    # The last-iteration proof summary therefore reports the master round.
    assert metadata["proof_summary"]["master_status"] == "INFEASIBLE"
    assert metadata["loaded_exact_safe_cut_count"] == 0
    assert metadata["generated_exact_safe_cut_count"] == 1


def test_binding_alt_cap_returns_unknown_without_whole_layout_cut(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class MasterStub:
        facility_pools = {"tiny_facility": [{"occupied_cells": []}]}
        source_instances = []
        grid_w = 4
        grid_h = 4
        generic_io_requirements = {
            "required_generic_outputs": {},
            "required_generic_inputs": {},
        }
        _coordinate_delegate = None

        def add_benders_cut(self, *args, **kwargs):
            raise AssertionError("binding-alt cap must not emit a master cut")

    selections = [
        {
            "binding_choice": {"tiny_001": 0},
            "generic_inputs": {},
            "generic_outputs": {},
        },
        {
            "binding_choice": {"tiny_001": 1},
            "generic_inputs": {},
            "generic_outputs": {},
        },
    ]

    class FakeBindingModel:
        instances = []

        def __init__(self, *args, **kwargs):
            self.index = 0
            self.binding_vars = {"tiny_001": {0: object(), 1: object()}}
            self.generic_input_vars = {}
            self.generic_output_vars = {}
            self.nogoods = []
            FakeBindingModel.instances.append(self)

        def build(self) -> None:
            return None

        def solve(self, time_limit_seconds: float = 30.0) -> str:
            if self.index < len(selections):
                return "FEASIBLE"
            return "INFEASIBLE"

        def extract_empty_binding_domain_instances(self) -> list:
            return []

        def extract_selection(self) -> dict:
            return dict(selections[self.index])

        def extract_port_specs(self) -> list[dict]:
            return []

        def add_nogood_cut(self, selection: dict) -> None:
            self.nogoods.append(dict(selection))
            self.index += 1

        def extract_conflict_summary(self) -> dict:
            return {"enumerated": self.index, "nogoods": len(self.nogoods)}

    class FakeRoutingGrid:
        def __init__(self, occupied_cells, port_specs):
            self.occupied_cells = occupied_cells
            self.port_specs = port_specs

    class FakeRoutingSubproblem:
        def __init__(self, grid, commodities):
            self.build_stats = {"fake": "routing_infeasible"}

        def build(self) -> None:
            return None

        def solve(self, time_limit: float = 60.0) -> str:
            return "INFEASIBLE"

    monkeypatch.setenv("EXACT_B1_BINDING_ALT_CAP", "1")
    monkeypatch.setattr(benders_loop_module, "PortBindingModel", FakeBindingModel)
    monkeypatch.setattr(benders_loop_module, "RoutingGrid", FakeRoutingGrid)
    monkeypatch.setattr(benders_loop_module, "RoutingSubproblem", FakeRoutingSubproblem)

    cut_manager = benders_loop_module.CutManager(
        tmp_path / "checkpoints",
        solve_mode="certified_exact",
        current_hashes={},
    )
    controller = benders_loop_module.LBBDController(
        MasterStub(),
        cut_manager,
        tmp_path,
        "certified_exact",
        max_iterations=1,
        binding_seconds=1.0,
        routing_seconds=1.0,
    )

    def fail_whole_layout_nogood(**kwargs):
        raise AssertionError("binding-alt cap must fail closed before whole-layout nogood")

    controller._add_exact_whole_layout_nogood = fail_whole_layout_nogood

    status, result = controller._run_exact_binding_and_routing(
        iteration=1,
        solution={
            "tiny_001": {"pose_idx": 0, "facility_type": "tiny_facility"},
        },
        diagnostic_flow_status="SKIPPED",
    )

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert FakeBindingModel.instances[0].nogoods == []
    assert controller.last_proof_summary["binding_status"] == "ALT_CAP_REACHED"
    assert controller.last_proof_summary["routing_status"] == "INFEASIBLE"
    assert controller.last_proof_summary["binding_alternative_cap"] == 1


def test_unexpected_initial_binding_status_returns_unknown_without_exact_safe_cut(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class MasterStub:
        facility_pools = {"tiny_facility": [{"occupied_cells": []}]}
        source_instances = []
        grid_w = 4
        grid_h = 4
        generic_io_requirements = {
            "required_generic_outputs": {},
            "required_generic_inputs": {},
        }
        _coordinate_delegate = None

        def add_benders_cut(self, *args, **kwargs):
            raise AssertionError("unexpected binding status must not emit a master cut")

    class FakeBindingModel:
        def __init__(self, *args, **kwargs):
            self.binding_vars = {}
            self.generic_input_vars = {}
            self.generic_output_vars = {}

        def build(self) -> None:
            return None

        def solve(self, time_limit_seconds: float = 30.0) -> str:
            return "MODEL_INVALID"

        def extract_empty_binding_domain_instances(self) -> list:
            return []

        def extract_conflict_summary(self) -> dict:
            return {"fake": "unexpected_initial_binding_status"}

    monkeypatch.setattr(benders_loop_module, "PortBindingModel", FakeBindingModel)

    cut_manager = benders_loop_module.CutManager(
        tmp_path / "checkpoints",
        solve_mode="certified_exact",
        current_hashes={},
    )
    controller = benders_loop_module.LBBDController(
        MasterStub(),
        cut_manager,
        tmp_path,
        "certified_exact",
        max_iterations=1,
        binding_seconds=1.0,
        routing_seconds=1.0,
    )

    def fail_whole_layout_nogood(**kwargs):
        raise AssertionError("unexpected binding status must fail closed before whole-layout nogood")

    controller._add_exact_whole_layout_nogood = fail_whole_layout_nogood

    status, result = controller._run_exact_binding_and_routing(
        iteration=1,
        solution={
            "tiny_001": {"pose_idx": 0, "facility_type": "tiny_facility"},
        },
        diagnostic_flow_status="SKIPPED",
    )

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert controller.generated_exact_safe_cuts == []
    assert controller.last_proof_summary["binding_status"] == "MODEL_INVALID"
    assert (
        controller.last_proof_summary["subproblem_status_contract_violation"]
        == "unexpected_binding_status"
    )


def test_unexpected_binding_resolve_status_returns_unknown_without_exhaustion_cut(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class MasterStub:
        facility_pools = {"tiny_facility": [{"occupied_cells": []}]}
        source_instances = []
        grid_w = 4
        grid_h = 4
        generic_io_requirements = {
            "required_generic_outputs": {},
            "required_generic_inputs": {},
        }
        _coordinate_delegate = None

        def add_benders_cut(self, *args, **kwargs):
            raise AssertionError("unexpected binding re-solve must not emit a master cut")

    class FakeBindingModel:
        instances = []

        def __init__(self, *args, **kwargs):
            self.solve_calls = 0
            self.nogoods = []
            self.binding_vars = {"tiny_001": {0: object(), 1: object()}}
            self.generic_input_vars = {}
            self.generic_output_vars = {}
            FakeBindingModel.instances.append(self)

        def build(self) -> None:
            return None

        def solve(self, time_limit_seconds: float = 30.0) -> str:
            self.solve_calls += 1
            if self.solve_calls == 1:
                return "FEASIBLE"
            return "MODEL_INVALID"

        def extract_empty_binding_domain_instances(self) -> list:
            return []

        def extract_selection(self) -> dict:
            return {
                "binding_choice": {"tiny_001": 0},
                "generic_inputs": {},
                "generic_outputs": {},
            }

        def extract_port_specs(self) -> list[dict]:
            return []

        def add_nogood_cut(self, selection: dict) -> None:
            self.nogoods.append(dict(selection))

        def extract_conflict_summary(self) -> dict:
            return {
                "fake": "unexpected_binding_resolve_status",
                "solve_calls": self.solve_calls,
                "nogoods": len(self.nogoods),
            }

    class FakeRoutingGrid:
        def __init__(self, occupied_cells, port_specs, **kwargs):
            self.occupied_cells = occupied_cells
            self.port_specs = port_specs

    class FakeRoutingSubproblem:
        def __init__(self, grid, commodities):
            self.build_stats = {"fake": "routing_infeasible"}

        def build(self) -> None:
            return None

        def solve(self, time_limit: float = 60.0) -> str:
            return "INFEASIBLE"

    monkeypatch.delenv("EXACT_B1_BINDING_ALT_CAP", raising=False)
    monkeypatch.setattr(benders_loop_module, "PortBindingModel", FakeBindingModel)
    monkeypatch.setattr(benders_loop_module, "RoutingGrid", FakeRoutingGrid)
    monkeypatch.setattr(benders_loop_module, "RoutingSubproblem", FakeRoutingSubproblem)
    monkeypatch.setattr(
        benders_loop_module,
        "run_exact_routing_precheck",
        lambda *args, **kwargs: {"status": "feasible", "domain_stats": {}},
    )

    cut_manager = benders_loop_module.CutManager(
        tmp_path / "checkpoints",
        solve_mode="certified_exact",
        current_hashes={},
    )
    controller = benders_loop_module.LBBDController(
        MasterStub(),
        cut_manager,
        tmp_path,
        "certified_exact",
        max_iterations=1,
        binding_seconds=1.0,
        routing_seconds=1.0,
    )

    def fail_whole_layout_nogood(**kwargs):
        raise AssertionError("unexpected binding re-solve must fail closed before exhaustion cut")

    controller._add_exact_whole_layout_nogood = fail_whole_layout_nogood

    status, result = controller._run_exact_binding_and_routing(
        iteration=1,
        solution={
            "tiny_001": {"pose_idx": 0, "facility_type": "tiny_facility"},
        },
        diagnostic_flow_status="SKIPPED",
    )

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert FakeBindingModel.instances[0].nogoods
    assert controller.generated_exact_safe_cuts == []
    assert controller.last_proof_summary["binding_status"] == "MODEL_INVALID"
    assert controller.last_proof_summary["routing_status"] == "INFEASIBLE"
    assert (
        controller.last_proof_summary["subproblem_status_contract_violation"]
        == "unexpected_binding_status"
    )


def test_power_placement_abort_returns_unknown_with_matching_proof_summary(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class MasterStub:
        source_instances = []
        facility_pools = {"tiny_facility": [{"occupied_cells": []}]}
        grid_w = 2
        grid_h = 1
        generic_io_requirements = {
            "required_generic_outputs": {},
            "required_generic_inputs": {},
        }
        wireless_sink_generic_input_slots = 0
        master_search_profile = "default_automatic"
        build_stats = {
            "last_solve": {},
            "search_guidance": {"profile": "default_automatic"},
        }

        def build_exact_candidate_warm_start(self) -> dict:
            return {}

        def solve(self, *args, **kwargs):
            self.build_stats["last_solve"] = {
                "status": "FEASIBLE",
                "wall_time": 0.0,
                "user_time": 0.0,
                "deterministic_time": 0.0,
                "branches": 0,
                "conflicts": 0,
                "hinted_literals": 0,
                "known_feasible_hint": False,
                "search_profile": "default_automatic",
            }
            return cp_model.FEASIBLE

        def extract_solution(self):
            return {
                "tiny_001": {
                    "facility_type": "tiny_facility",
                    "pose_idx": 0,
                    "pose_id": "tiny_left",
                }
            }

    def fake_power_abort(self, *, solution, iteration):
        return "ABORT", None

    monkeypatch.setenv("EXACT_POWER_PLACEMENT_SUBPROBLEM", "1")
    monkeypatch.setattr(
        benders_loop_module.LBBDController,
        "_run_power_placement_subproblem",
        fake_power_abort,
    )

    cut_manager = benders_loop_module.CutManager(
        tmp_path / "checkpoints",
        solve_mode="certified_exact",
        current_hashes={},
    )
    controller = benders_loop_module.LBBDController(
        MasterStub(),
        cut_manager,
        tmp_path,
        "certified_exact",
        max_iterations=1,
        master_seconds=1.0,
        binding_seconds=1.0,
        routing_seconds=1.0,
    )

    status, result = controller.run_with_status()
    proof_summary = controller.last_proof_summary

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert controller.generated_exact_safe_cuts == []
    assert proof_summary["master_status"] == "FEASIBLE"
    assert proof_summary["stage"] == "power_placement_subproblem"
    assert proof_summary["power_placement_status"] == "ABORT"
    assert proof_summary["master_follow_up"] == "fail_closed_unknown"


def test_certified_max_iterations_cap_returns_unknown_without_exact_safe_cut(
    tmp_path: Path,
) -> None:
    class MasterStub:
        master_search_profile = "default_automatic"
        build_stats = {
            "last_solve": {},
            "search_guidance": {"profile": "default_automatic"},
        }

        def build_exact_candidate_warm_start(self) -> dict:
            return {}

    cut_manager = benders_loop_module.CutManager(
        tmp_path / "checkpoints",
        solve_mode="certified_exact",
        current_hashes={},
    )
    controller = benders_loop_module.LBBDController(
        MasterStub(),
        cut_manager,
        tmp_path,
        "certified_exact",
        max_iterations=0,
        master_seconds=1.0,
        binding_seconds=1.0,
        routing_seconds=1.0,
    )

    status, result = controller.run_with_status()
    proof_summary = controller.last_proof_summary

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert controller.generated_exact_safe_cuts == []
    assert proof_summary["master_status"] == "MAX_ITERATIONS"
    assert proof_summary["master_follow_up"] == "fail_closed_unknown"
    assert proof_summary["exact_safe_cut_count"] == 0


def test_unexpected_routing_status_returns_unknown_without_exact_safe_cut(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_routing_unknown_status")

    class FakeBindingModel:
        def __init__(self, *args, **kwargs):
            self.binding_vars = {}
            self.generic_input_vars = {}
            self.generic_output_vars = {}

        def build(self) -> None:
            return None

        def solve(self, time_limit_seconds: float = 30.0) -> str:
            return "FEASIBLE"

        def extract_empty_binding_domain_instances(self) -> list:
            return []

        def extract_selection(self) -> dict:
            return {
                "binding_choice": {"tiny_001": 0},
                "generic_inputs": {},
                "generic_outputs": {},
            }

        def extract_port_specs(self) -> list[dict]:
            return []

        def extract_conflict_summary(self) -> dict:
            return {"fake": "unexpected_routing_status"}

    class FakeRoutingGrid:
        def __init__(self, occupied_cells, port_specs):
            self.occupied_cells = occupied_cells
            self.port_specs = port_specs

    class FakeRoutingSubproblem:
        def __init__(self, grid, commodities):
            self.build_stats = {"fake": "unexpected_status"}

        def build(self) -> None:
            return None

        def solve(self, time_limit: float = 60.0) -> str:
            return "UNKNOWN"

    monkeypatch.setattr(benders_loop_module, "PortBindingModel", FakeBindingModel)
    monkeypatch.setattr(benders_loop_module, "RoutingGrid", FakeRoutingGrid)
    monkeypatch.setattr(benders_loop_module, "RoutingSubproblem", FakeRoutingSubproblem)

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=5.0,
        binding_seconds=5.0,
        routing_seconds=5.0,
        max_iterations=2,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert metadata["exact_safe_cuts"] == []
    assert metadata["loaded_exact_safe_cut_count"] == 0
    assert metadata["generated_exact_safe_cut_count"] == 0
    assert metadata["proof_summary"]["routing_status"] == "UNKNOWN"
    assert (
        metadata["proof_summary"]["subproblem_status_contract_violation"]
        == "unexpected_routing_status"
    )


def test_unexpected_routing_precheck_status_returns_unknown_without_routing_cut(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class MasterStub:
        facility_pools = {"tiny_facility": [{"occupied_cells": []}]}
        source_instances = []
        grid_w = 4
        grid_h = 4
        generic_io_requirements = {
            "required_generic_outputs": {},
            "required_generic_inputs": {},
        }
        _coordinate_delegate = None

        def add_benders_cut(self, *args, **kwargs):
            raise AssertionError(
                "unexpected routing precheck status must not emit a master cut"
            )

    class FakeBindingModel:
        def __init__(self, *args, **kwargs):
            self.binding_vars = {}
            self.generic_input_vars = {}
            self.generic_output_vars = {}

        def build(self) -> None:
            return None

        def solve(self, time_limit_seconds: float = 30.0) -> str:
            return "FEASIBLE"

        def extract_empty_binding_domain_instances(self) -> list:
            return []

        def extract_selection(self) -> dict:
            return {
                "binding_choice": {"tiny_001": 0},
                "generic_inputs": {},
                "generic_outputs": {},
            }

        def extract_port_specs(self) -> list[dict]:
            return []

        def extract_conflict_summary(self) -> dict:
            return {"fake": "unexpected_routing_precheck_status"}

    class FakeRoutingGrid:
        def __init__(self, occupied_cells, port_specs, **kwargs):
            self.occupied_cells = occupied_cells
            self.port_specs = port_specs
            self.free_cells = set()

    class ShouldNotBuildRoutingSubproblem:
        def __init__(self, *args, **kwargs):
            raise AssertionError(
                "unexpected routing precheck status must fail closed before routing build"
            )

    def fake_routing_precheck(*args, **kwargs) -> dict:
        return {
            "status": "TIMEOUT",
            "binding_selection_safe_reject": False,
            "placement_level_conflict_set": [],
            "blocked_ports": [],
            "disconnected_commodities": [],
            "domain_stats": {"source": "regression"},
            "_analysis": {
                "status": "TIMEOUT",
                "domain_stats": {"source": "regression"},
            },
        }

    monkeypatch.setattr(benders_loop_module, "PortBindingModel", FakeBindingModel)
    monkeypatch.setattr(benders_loop_module, "RoutingGrid", FakeRoutingGrid)
    monkeypatch.setattr(
        benders_loop_module,
        "RoutingSubproblem",
        ShouldNotBuildRoutingSubproblem,
    )
    monkeypatch.setattr(
        benders_loop_module,
        "run_exact_routing_precheck",
        fake_routing_precheck,
    )

    cut_manager = benders_loop_module.CutManager(
        tmp_path / "checkpoints",
        solve_mode="certified_exact",
        current_hashes={},
    )
    controller = benders_loop_module.LBBDController(
        MasterStub(),
        cut_manager,
        tmp_path,
        "certified_exact",
        max_iterations=1,
        binding_seconds=1.0,
        routing_seconds=1.0,
    )

    def fail_whole_layout_nogood(**kwargs):
        raise AssertionError(
            "unexpected routing precheck status must fail closed before exhaustion cut"
        )

    controller._add_exact_whole_layout_nogood = fail_whole_layout_nogood

    status, result = controller._run_exact_binding_and_routing(
        iteration=1,
        solution={
            "tiny_001": {"pose_idx": 0, "facility_type": "tiny_facility"},
        },
        diagnostic_flow_status="SKIPPED",
    )

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert controller.generated_exact_safe_cuts == []
    assert controller.last_proof_summary["routing_status"] == "PRECHECK_TIMEOUT"
    assert controller.last_proof_summary["routing_precheck"]["status"] == "TIMEOUT"
    assert (
        controller.last_proof_summary["subproblem_status_contract_violation"]
        == "unexpected_routing_precheck_status"
    )
    assert controller.last_proof_summary["master_follow_up"] == "fail_closed_unknown"


def test_routing_timeout_returns_unknown_without_exact_safe_cut(monkeypatch, tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_routing_timeout")

    class FakeBindingModel:
        def __init__(self, *args, **kwargs):
            self.binding_vars = {}
            self.generic_input_vars = {}
            self.generic_output_vars = {}

        def build(self) -> None:
            return None

        def solve(self, time_limit_seconds: float = 30.0) -> str:
            return "FEASIBLE"

        def extract_selection(self) -> dict:
            return {
                "binding_choice": {"tiny_001": 0},
                "generic_inputs": {},
                "generic_outputs": {},
            }

        def extract_port_specs(self) -> list[dict]:
            return []

        def extract_conflict_summary(self) -> dict:
            return {"fake": "timeout"}

    class FakeRoutingGrid:
        def __init__(self, occupied_cells, port_specs):
            self.occupied_cells = occupied_cells
            self.port_specs = port_specs

    class FakeRoutingSubproblem:
        def __init__(self, grid, commodities):
            self.build_stats = {"fake": "timeout"}

        def build(self) -> None:
            return None

        def solve(self, time_limit: float = 60.0) -> str:
            return "TIMEOUT"

    monkeypatch.setattr(benders_loop_module, "PortBindingModel", FakeBindingModel)
    monkeypatch.setattr(benders_loop_module, "RoutingGrid", FakeRoutingGrid)
    monkeypatch.setattr(benders_loop_module, "RoutingSubproblem", FakeRoutingSubproblem)

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=5.0,
        binding_seconds=5.0,
        routing_seconds=5.0,
        max_iterations=2,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert metadata["exact_safe_cuts"] == []
    assert metadata["loaded_exact_safe_cut_count"] == 0
    assert metadata["generated_exact_safe_cut_count"] == 0


def test_binding_domain_empty_generates_singleton_cut_and_continues_master_loop(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_multi_pose_exact_project(
        tmp_path / "binding_domain_empty_continue",
        pose_anchors=[0, 2],
    )

    def fake_master_solve(
        self,
        time_limit_seconds: float = 60.0,
        solution_hint=None,
        known_feasible_hint: bool = False,
        ghost_anchor_hint_idx=None,
        hint_inactive_residual_optionals: bool = True,
        diagnostic_log_callback=None,
    ):
        solve_calls = int(getattr(self, "_test_solve_calls", 0)) + 1
        self._test_solve_calls = solve_calls
        self.build_stats["last_solve"] = {
            "status": "FEASIBLE",
            "wall_time": 0.0,
            "hinted_literals": 0,
            "known_feasible_hint": bool(known_feasible_hint),
        }
        return cp_model.FEASIBLE

    def fake_extract_solution(self):
        pose_idx = 0 if int(getattr(self, "_test_solve_calls", 0)) <= 1 else 1
        pose = self.facility_pools["tiny_facility"][pose_idx]
        return {
            "tiny_001": {
                "pose_idx": pose_idx,
                "pose_id": pose["pose_id"],
                "anchor": dict(pose["anchor"]),
                "facility_type": "tiny_facility",
            }
        }

    class FakeBindingModel:
        def __init__(self, placement_solution, *args, **kwargs):
            self.pose_idx = int(placement_solution["tiny_001"]["pose_idx"])
            self.binding_vars = {}
            self.generic_input_vars = {}
            self.generic_output_vars = {}

        def build(self) -> None:
            return None

        def extract_empty_binding_domain_instances(self) -> list[dict]:
            if self.pose_idx == 0:
                return [
                    {
                        "instance_id": "tiny_001",
                        "pose_idx": 0,
                        "pose_id": "tiny_0",
                        "facility_type": "tiny_facility",
                    }
                ]
            return []

        def solve(self, time_limit_seconds: float = 30.0) -> str:
            return "FEASIBLE"

        def extract_selection(self) -> dict:
            return {
                "binding_choice": {"tiny_001": 0},
                "generic_inputs": {},
                "generic_outputs": {},
            }

        def extract_port_specs(self) -> list[dict]:
            return []

        def extract_conflict_summary(self) -> dict:
            return {
                "empty_binding_domain_instances": self.extract_empty_binding_domain_instances(),
            }

    class FakeRoutingSubproblem:
        def __init__(self, grid, commodities):
            self.build_stats = {"fake": "routing"}

        def build(self) -> None:
            return None

        def solve(self, time_limit: float = 60.0) -> str:
            return "FEASIBLE"

    monkeypatch.setattr(MasterPlacementModel, "solve", fake_master_solve)
    monkeypatch.setattr(MasterPlacementModel, "extract_solution", fake_extract_solution)
    monkeypatch.setattr(MasterPlacementModel, "build_greedy_solution_hint", lambda self: {})
    monkeypatch.setattr(
        benders_loop_module.LBBDController,
        "_run_flow_diagnostic",
        lambda self, solution: ("FEASIBLE", set()),
    )
    monkeypatch.setattr(benders_loop_module, "PortBindingModel", FakeBindingModel)
    monkeypatch.setattr(benders_loop_module, "RoutingSubproblem", FakeRoutingSubproblem)

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=5.0,
        binding_seconds=5.0,
        routing_seconds=5.0,
        max_iterations=3,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")

    assert status == RUN_STATUS_CERTIFIED
    assert result is not None
    assert result["tiny_001"]["pose_idx"] == 1
    assert metadata["generated_exact_safe_cut_count"] == 1
    assert metadata["fine_grained_exact_safe_cut_count"] == 1
    assert metadata["binding_domain_empty_cut_count"] == 1
    assert metadata["routing_front_blocked_cut_count"] == 0
    assert metadata["exact_safe_cuts"][0]["cut_type"] == "binding_pose_domain_empty_nogood"
    assert metadata["exact_safe_cuts"][0]["conflict_set"] == {"tiny_001": 0}
    assert metadata["exact_safe_cuts"][0]["proof_summary"]["fine_grained_exact_safe_cut_count"] == 1
    assert metadata["exact_safe_cuts"][0]["proof_summary"]["binding_domain_empty_cut_count"] == 1


def test_routing_front_blocked_unencodable_optional_conflict_fails_closed(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_multi_pose_exact_project(
        tmp_path / "routing_front_blocked_continue",
        pose_anchors=[0, 2],
        include_pole_block=True,
    )

    def fake_master_solve(
        self,
        time_limit_seconds: float = 60.0,
        solution_hint=None,
        known_feasible_hint: bool = False,
        ghost_anchor_hint_idx=None,
        hint_inactive_residual_optionals: bool = True,
        diagnostic_log_callback=None,
    ):
        solve_calls = int(getattr(self, "_test_solve_calls", 0)) + 1
        self._test_solve_calls = solve_calls
        self.build_stats["last_solve"] = {
            "status": "FEASIBLE",
            "wall_time": 0.0,
            "hinted_literals": 0,
            "known_feasible_hint": bool(known_feasible_hint),
        }
        return cp_model.FEASIBLE

    def fake_extract_solution(self):
        pose_idx = 0 if int(getattr(self, "_test_solve_calls", 0)) <= 1 else 1
        tiny_pose = self.facility_pools["tiny_facility"][pose_idx]
        solution = {
            "tiny_001": {
                "pose_idx": pose_idx,
                "pose_id": tiny_pose["pose_id"],
                "anchor": dict(tiny_pose["anchor"]),
                "facility_type": "tiny_facility",
            }
        }
        pole_pose = self.facility_pools["power_pole"][0]
        solution["pose_optional::power_pole::pole_block"] = {
            "pose_idx": 0,
            "pose_id": pole_pose["pose_id"],
            "anchor": dict(pole_pose["anchor"]),
            "facility_type": "power_pole",
        }
        return solution

    class FakeBindingModel:
        def __init__(self, placement_solution, *args, **kwargs):
            self.pose_idx = int(placement_solution["tiny_001"]["pose_idx"])
            self.binding_vars = {}
            self.generic_input_vars = {}
            self.generic_output_vars = {}

        def build(self) -> None:
            return None

        def extract_empty_binding_domain_instances(self) -> list[dict]:
            return []

        def solve(self, time_limit_seconds: float = 30.0) -> str:
            return "FEASIBLE"

        def extract_selection(self) -> dict:
            return {
                "binding_choice": {"tiny_001": 0},
                "generic_inputs": {},
                "generic_outputs": {},
            }

        def extract_port_specs(self) -> list[dict]:
            port_x = 0 if self.pose_idx == 0 else 2
            return [
                {
                    "instance_id": "tiny_001",
                    "x": port_x,
                    "y": 0,
                    "dir": "E",
                    "type": "out",
                    "commodity": "ore",
                }
            ]

        def extract_conflict_summary(self) -> dict:
            return {"pose_idx": self.pose_idx}

    class FakeRoutingSubproblem:
        def __init__(self, grid, commodities):
            self.build_stats = {"fake": "routing"}

        def build(self) -> None:
            return None

        def solve(self, time_limit: float = 60.0) -> str:
            return "FEASIBLE"

    monkeypatch.setattr(MasterPlacementModel, "solve", fake_master_solve)
    monkeypatch.setattr(MasterPlacementModel, "extract_solution", fake_extract_solution)
    monkeypatch.setattr(MasterPlacementModel, "build_greedy_solution_hint", lambda self: {})
    monkeypatch.setattr(
        benders_loop_module.LBBDController,
        "_run_flow_diagnostic",
        lambda self, solution: ("FEASIBLE", set()),
    )
    monkeypatch.setattr(benders_loop_module, "PortBindingModel", FakeBindingModel)
    monkeypatch.setattr(benders_loop_module, "RoutingSubproblem", FakeRoutingSubproblem)

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=5.0,
        binding_seconds=5.0,
        routing_seconds=5.0,
        max_iterations=3,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert metadata["generated_exact_safe_cut_count"] == 0
    assert metadata["fine_grained_exact_safe_cut_count"] == 0
    assert metadata["binding_domain_empty_cut_count"] == 0
    assert metadata["routing_front_blocked_cut_count"] == 0
    assert metadata["exact_safe_cuts"] == []
    assert metadata["proof_summary"]["master_follow_up"] == "cut_stall"


def test_relaxed_disconnected_only_rejects_binding_selection_without_persisted_cut(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_multi_pose_exact_project(
        tmp_path / "relaxed_disconnected_binding_reject",
        pose_anchors=[0],
    )

    def fake_master_solve(
        self,
        time_limit_seconds: float = 60.0,
        solution_hint=None,
        known_feasible_hint: bool = False,
        ghost_anchor_hint_idx=None,
        hint_inactive_residual_optionals: bool = True,
        diagnostic_log_callback=None,
    ):
        self.build_stats["last_solve"] = {
            "status": "FEASIBLE",
            "wall_time": 0.0,
            "hinted_literals": 0,
            "known_feasible_hint": bool(known_feasible_hint),
        }
        return cp_model.FEASIBLE

    def fake_extract_solution(self):
        pose = self.facility_pools["tiny_facility"][0]
        return {
            "tiny_001": {
                "pose_idx": 0,
                "pose_id": pose["pose_id"],
                "anchor": dict(pose["anchor"]),
                "facility_type": "tiny_facility",
            }
        }

    class FakeBindingModel:
        def __init__(self, *args, **kwargs):
            self.index = 0
            self.binding_vars = {"tiny_001": {0: object(), 1: object()}}
            self.generic_input_vars = {}
            self.generic_output_vars = {}

        def build(self) -> None:
            return None

        def extract_empty_binding_domain_instances(self) -> list[dict]:
            return []

        def solve(self, time_limit_seconds: float = 30.0) -> str:
            if self.index < 2:
                return "FEASIBLE"
            return "INFEASIBLE"

        def extract_selection(self) -> dict:
            return {
                "binding_choice": {"tiny_001": self.index},
                "generic_inputs": {},
                "generic_outputs": {},
            }

        def extract_port_specs(self) -> list[dict]:
            return []

        def add_nogood_cut(self, selection: dict) -> None:
            assert selection["binding_choice"]["tiny_001"] == self.index
            self.index += 1

        def extract_conflict_summary(self) -> dict:
            return {"binding_index": self.index}

    class FakeRoutingSubproblem:
        def __init__(self, grid, commodities):
            self.build_stats = {"fake": "routing"}

        def build(self) -> None:
            return None

        def solve(self, time_limit: float = 60.0) -> str:
            return "FEASIBLE"

    precheck_calls = {"count": 0}

    def fake_routing_precheck(grid, *, occupied_owner_by_cell=None):
        precheck_calls["count"] += 1
        if precheck_calls["count"] == 1:
            return {
                "status": "relaxed_disconnected",
                "binding_selection_safe_reject": True,
                "placement_level_conflict_set": [],
                "blocked_ports": [],
                "disconnected_commodities": [{"commodity": "ore"}],
            }
        return {
            "status": "feasible",
            "binding_selection_safe_reject": False,
            "placement_level_conflict_set": [],
            "blocked_ports": [],
            "disconnected_commodities": [],
        }

    monkeypatch.setattr(MasterPlacementModel, "solve", fake_master_solve)
    monkeypatch.setattr(MasterPlacementModel, "extract_solution", fake_extract_solution)
    monkeypatch.setattr(MasterPlacementModel, "build_greedy_solution_hint", lambda self: {})
    monkeypatch.setattr(
        benders_loop_module.LBBDController,
        "_run_flow_diagnostic",
        lambda self, solution: ("FEASIBLE", set()),
    )
    monkeypatch.setattr(benders_loop_module, "PortBindingModel", FakeBindingModel)
    monkeypatch.setattr(benders_loop_module, "RoutingSubproblem", FakeRoutingSubproblem)
    monkeypatch.setattr(benders_loop_module, "run_exact_routing_precheck", fake_routing_precheck)

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=5.0,
        binding_seconds=5.0,
        routing_seconds=5.0,
        max_iterations=2,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")

    assert status == RUN_STATUS_CERTIFIED
    assert result is not None
    assert metadata["generated_exact_safe_cut_count"] == 0
    assert metadata["exact_safe_cuts"] == []
    assert metadata["proof_summary"]["enumerated_bindings"] == 2
    assert metadata["proof_summary"]["routing_precheck_rejections"] == 1
    assert metadata["proof_summary"]["routing_precheck_statuses"] == [
        "relaxed_disconnected",
        "feasible",
    ]
    assert metadata["used_routing_core_reuse"] is True
    assert metadata["routing_core_build_seconds"] >= 0.0
    assert metadata["routing_overlay_build_seconds"] >= 0.0


def test_exact_mode_reports_routing_shrink_stats(monkeypatch, tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_routing_shrink")

    def fake_master_solve(
        self,
        time_limit_seconds: float = 60.0,
        solution_hint=None,
        known_feasible_hint: bool = False,
        ghost_anchor_hint_idx=None,
        hint_inactive_residual_optionals: bool = True,
        diagnostic_log_callback=None,
    ):
        self.build_stats["last_solve"] = {
            "status": "FEASIBLE",
            "wall_time": 0.0,
            "hinted_literals": 0,
            "known_feasible_hint": bool(known_feasible_hint),
        }
        return cp_model.FEASIBLE

    def fake_extract_solution(self):
        pose = self.facility_pools["tiny_facility"][0]
        return {
            "tiny_001": {
                "pose_idx": 0,
                "pose_id": pose["pose_id"],
                "anchor": dict(pose["anchor"]),
                "facility_type": "tiny_facility",
            }
        }

    class FakeBindingModel:
        def __init__(self, *args, **kwargs):
            self.binding_vars = {}
            self.generic_input_vars = {}
            self.generic_output_vars = {}

        def build(self) -> None:
            return None

        def extract_empty_binding_domain_instances(self) -> list[dict]:
            return []

        def solve(self, time_limit_seconds: float = 30.0) -> str:
            return "FEASIBLE"

        def extract_selection(self) -> dict:
            return {
                "binding_choice": {"tiny_001": 0},
                "generic_inputs": {},
                "generic_outputs": {},
            }

        def extract_port_specs(self) -> list[dict]:
            return [
                {
                    "instance_id": "tiny_001",
                    "x": 0,
                    "y": 2,
                    "dir": "E",
                    "type": "out",
                    "commodity": "ore",
                },
                {
                    "instance_id": "tiny_001",
                    "x": 8,
                    "y": 3,
                    "dir": "S",
                    "type": "in",
                    "commodity": "ore",
                },
            ]

        def extract_conflict_summary(self) -> dict:
            return {"fake": "routing_shrink"}

    class CorridorRoutingGrid:
        def __init__(self, occupied_cells, port_specs):
            del occupied_cells
            self.port_specs = list(port_specs)
            self.free_cells = {(x, 2) for x in range(1, 9)} | {(4, 3), (4, 4)}
            self.port_cells = {
                (int(port["x"]), int(port["y"]))
                for port in self.port_specs
            }
            self.routable_cells = self.free_cells | self.port_cells

        def neighbors(self, x: int, y: int) -> list[tuple[int, int, str]]:
            result = []
            for direction, (dx, dy) in {
                "N": (0, 1),
                "S": (0, -1),
                "E": (1, 0),
                "W": (-1, 0),
            }.items():
                nx, ny = x + dx, y + dy
                if 0 <= nx < 70 and 0 <= ny < 70 and (nx, ny) in self.routable_cells:
                    result.append((nx, ny, direction))
            return result

    monkeypatch.setattr(MasterPlacementModel, "solve", fake_master_solve)
    monkeypatch.setattr(MasterPlacementModel, "extract_solution", fake_extract_solution)
    monkeypatch.setattr(MasterPlacementModel, "build_greedy_solution_hint", lambda self: {})
    monkeypatch.setattr(
        benders_loop_module.LBBDController,
        "_run_flow_diagnostic",
        lambda self, solution: ("FEASIBLE", set()),
    )
    monkeypatch.setattr(benders_loop_module, "PortBindingModel", FakeBindingModel)
    monkeypatch.setattr(benders_loop_module, "RoutingGrid", CorridorRoutingGrid)

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=5.0,
        binding_seconds=5.0,
        routing_seconds=5.0,
        max_iterations=2,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")
    routing_summary = metadata["proof_summary"]["routing_summary"]["state_space"]

    assert status == RUN_STATUS_CERTIFIED
    assert result is not None
    assert metadata["proof_summary"]["routing_domain_cells"] == 10
    assert metadata["proof_summary"]["routing_terminal_core_cells"] == 8
    assert metadata["proof_summary"]["routing_state_space_vars"] == routing_summary["vars"]
    assert (
        metadata["proof_summary"]["routing_local_pattern_pruned_states"]
        == routing_summary["local_pattern_pruned_states"]
    )
    assert routing_summary["vars"] < routing_summary["naive_full_domain_vars"]
    assert "used_routing_core_reuse" in metadata
    assert metadata["routing_core_build_seconds"] >= 0.0
    assert metadata["routing_overlay_build_seconds"] >= 0.0
    assert metadata["binding_domain_cache_hits"] == 0
    assert metadata["binding_domain_cache_misses"] == 0


def test_unknown_result_is_persisted_to_campaign(monkeypatch, tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "campaign_unknown")

    def _always_unknown(self, *args, **kwargs):
        self.build_stats["last_solve"] = {
            "status": RUN_STATUS_UNKNOWN,
            "wall_time": 0.01,
            "hinted_literals": 0,
            "known_feasible_hint": False,
            "search_profile": "test_unknown_profile",
            "search_branching": "test_branching",
        }
        return cp_model.UNKNOWN

    monkeypatch.setattr(MasterPlacementModel, "solve", _always_unknown)
    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=1,
        min_side=1,
        area_upper_bound=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )
    state = _read_campaign_state(project_root)
    candidate = state["candidates"]["1x1"]

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert state["final_status"] == RUN_STATUS_UNKNOWN
    assert state["last_stop_reason"]["reason"] == "candidate_returned_unknown"
    assert candidate["status"] == RUN_STATUS_UNKNOWN
    assert candidate["finished_at"] is not None
    assert candidate["proof_summary"]["master_status"] == "UNKNOWN"
    telemetry = _read_campaign_telemetry(project_root)
    assert telemetry["aggregate"]["wave_count"] == 1
    assert telemetry["aggregate"]["status_counts"] == {RUN_STATUS_UNKNOWN: 1}
    assert telemetry["aggregate"]["outcome_counts"] == {"unknown": 1}
    assert telemetry["aggregate"]["selection_reason_counts"] == {"prune_head": 1}
    assert telemetry["aggregate"]["master_status_counts"] == {RUN_STATUS_UNKNOWN: 1}
    candidate_result = telemetry["waves"][0]["candidate_results"][0]
    assert candidate_result["outcome_category"] == "unknown"
    assert candidate_result["selection_reason"] == "prune_head"
    assert candidate_result["wave_slot_index"] == 0
    assert candidate_result["proof_status_summary"]["master_last_solve"] == {
        "status": RUN_STATUS_UNKNOWN,
        "wall_time": 0.01,
        "user_time": 0.0,
        "deterministic_time": 0.0,
        "branches": 0,
        "conflicts": 0,
        "binary_propagations": 0,
        "integer_propagations": 0,
        "hinted_literals": 0,
        "known_feasible_hint": False,
        "search_profile": "test_unknown_profile",
        "search_branching": "test_branching",
    }
    assert "master_warm_start" in candidate_result["proof_status_summary"]
    assert "ghost_anchor_hint_status" in candidate_result["proof_status_summary"]["master_warm_start"]
    assert "warm_start_strategy" in candidate_result["proof_status_summary"]["master_warm_start"]
    assert "local_repair_attempted" in candidate_result["proof_status_summary"]["master_warm_start"]
    assert "ghost_aware_pose_order_portfolio_failure_samples" in candidate_result["proof_status_summary"]["master_warm_start"]
    assert "master_start_feasibility" in candidate_result["proof_status_summary"]
    assert "warm_start_strategy" in candidate_result["proof_status_summary"]["master_start_feasibility"]
    assert "local_repair_attempted" in candidate_result["proof_status_summary"]["master_start_feasibility"]
    assert "ghost_aware_pose_order_portfolio_failure_samples" in candidate_result["proof_status_summary"]["master_start_feasibility"]
    assert "master_start_failure_attribution" in candidate_result["proof_status_summary"]
    assert "master_start_local_repair" in candidate_result["proof_status_summary"]
    assert "master_boundary_port_feasibility" in candidate_result["proof_status_summary"]
    assert "master_mandatory_support_diagnostics" in candidate_result["proof_status_summary"]
    assert "master_mandatory_group_prechecks" in candidate_result["proof_status_summary"]
    assert "master_candidate_precheck" in candidate_result["proof_status_summary"]
    assert candidate_result["proof_status_summary"]["master_candidate_precheck"]["triggered"] is False
    assert "master_domain_activation" in candidate_result["proof_status_summary"]


def test_requested_master_search_profile_is_reflected_in_serial_exact_metadata(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "campaign_profile_requested")
    requested_profile = "exact_coordinate_ghost_first_v1"

    def _always_unknown(self, *args, **kwargs):
        self.build_stats["last_solve"] = {
            "status": RUN_STATUS_UNKNOWN,
            "wall_time": 0.02,
            "user_time": 0.01,
            "deterministic_time": 0.0,
            "branches": 0,
            "conflicts": 0,
            "binary_propagations": 0,
            "integer_propagations": 0,
            "hinted_literals": 1,
            "known_feasible_hint": False,
            "search_profile": str(self.build_stats["search_guidance"]["profile"]),
            "search_branching": "SearchBranching.FIXED_SEARCH",
        }
        return cp_model.UNKNOWN

    monkeypatch.setattr(MasterPlacementModel, "solve", _always_unknown)
    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=1,
        min_side=1,
        area_upper_bound=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        master_search_profile=requested_profile,
    )

    telemetry = _read_campaign_telemetry(project_root)
    candidate_result = telemetry["waves"][0]["candidate_results"][0]

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert candidate_result["selection_reason"] == "prune_head"
    assert candidate_result["proof_status_summary"]["master_last_solve"]["search_profile"] == (
        requested_profile
    )
    assert telemetry["aggregate"]["master_search_profile_counts"] == {
        requested_profile: 1
    }


def test_unknown_stop_does_not_persist_incumbent_certified_result_to_outputs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "campaign_unknown_with_best", width=6, height=6)

    def fake_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        del session, kwargs
        if (ghost_w, ghost_h) == (6, 1):
            fake_run_benders_for_ghost_rect.last_run_metadata = {
                "proof_summary": {"mode": "certified_exact", "master_status": "CERTIFIED"},
                "exact_safe_cuts": [],
                "loaded_exact_safe_cut_count": 0,
                "generated_exact_safe_cut_count": 0,
            }
            return RUN_STATUS_CERTIFIED, {
                "ghost_pick": {
                    "pose_idx": 0,
                    "pose_id": "ghost_6x1",
                    "facility_type": "synthetic",
                    "anchor": {"x": 0, "y": 0},
                }
            }
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {"mode": "certified_exact", "master_status": "UNKNOWN"},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        return RUN_STATUS_UNKNOWN, None

    fake_run_benders_for_ghost_rect.last_run_metadata = {
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }

    monkeypatch.setattr(outer_search_module, "run_benders_for_ghost_rect", fake_run_benders_for_ghost_rect)
    monkeypatch.setattr(
        outer_search_module.ExactSearchSession,
        "create",
        staticmethod(lambda project_root, solve_mode="certified_exact": object()),
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=2,
        min_side=1,
        area_upper_bound=9,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )

    state = _read_campaign_state(project_root)
    final_solution_path = project_root / "data" / "solutions" / "final_solution.json"
    blueprint_path = project_root / "data" / "blueprints" / "optimal_blueprint.json"
    manifest_path = delivery_manifest_output_path(project_root)
    manifest_path = delivery_manifest_output_path(project_root)

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert state["final_status"] == RUN_STATUS_UNKNOWN
    assert state.get("final_result") is None
    assert state["last_stop_reason"]["reason"] == "candidate_returned_unknown"
    assert not final_solution_path.exists()
    assert not blueprint_path.exists()
    assert manifest_path.exists()

    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["campaign"]["final_status"] == RUN_STATUS_UNKNOWN
    assert manifest_payload["best_certified_result"] is None
    assert manifest_payload["artifacts"]["final_solution"]["exists"] is False
    assert manifest_payload["artifacts"]["optimal_blueprint"]["exists"] is False


def test_unproven_result_is_persisted_to_campaign(tmp_path: Path) -> None:
    # V83: a malformed mandatory_exact_instances artifact (non-mandatory /
    # non-exact records under the certified filename) now fails closed at the
    # loader instead of silently producing a BLOCKED/UNPROVEN run. The
    # UNPROVEN persistence semantics remain covered by the scheduler and
    # inspector suites.
    project_root = _build_toy_exact_project(tmp_path / "campaign_unproven")
    _write_json(
        project_root / "data" / "preprocessed" / "mandatory_exact_instances.json",
        [
            {
                "instance_id": "tiny_001",
                "facility_type": "tiny_facility",
                "is_mandatory": False,
                "bound_type": "provisional",
                "solve_mode": "exploratory",
            }
        ],
    )

    with pytest.raises(ValueError, match="is_mandatory must be true"):
        run_outer_search(
            project_root=project_root,
            solve_mode="certified_exact",
            max_attempts=1,
            min_side=1,
            area_upper_bound=1,
            master_seconds=0.01,
            binding_seconds=0.01,
            routing_seconds=0.01,
            benders_max_iter=1,
            campaign_hours=1.0,
            resume_campaign=False,
        )


def test_candidate_outcome_taxonomy_covers_certified_terminal_categories() -> None:
    assert classify_candidate_outcome(status=RUN_STATUS_CERTIFIED, proof_summary={}) == "certified"
    assert classify_candidate_outcome(
        status=RUN_STATUS_INFEASIBLE,
        proof_summary={"master_status": "AREA_PRECHECK_FAILED"},
    ) == "master_infeasible"
    assert classify_candidate_outcome(
        status=RUN_STATUS_INFEASIBLE,
        proof_summary={"master_status": "FEASIBLE", "binding_status": "EMPTY_DOMAIN"},
    ) == "binding_empty_domain"
    assert classify_candidate_outcome(
        status=RUN_STATUS_UNKNOWN,
        proof_summary={"master_status": "FEASIBLE", "binding_status": "TIMEOUT"},
    ) == "binding_timeout"
    assert classify_candidate_outcome(
        status=RUN_STATUS_INFEASIBLE,
        proof_summary={"master_status": "FEASIBLE", "routing_status": "PRECHECK_FRONT_BLOCKED"},
    ) == "routing_precheck_reject"
    assert classify_candidate_outcome(
        status=RUN_STATUS_UNKNOWN,
        proof_summary={"master_status": "FEASIBLE", "routing_status": "TIMEOUT"},
    ) == "routing_timeout"
    assert classify_candidate_outcome(
        status=RUN_STATUS_INFEASIBLE,
        proof_summary={"master_status": "FEASIBLE", "routing_status": "ALL_INFEASIBLE"},
    ) == "all_infeasible"


def test_max_attempts_stop_reason_is_persisted(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "campaign_max_attempts")
    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=0,
        min_side=1,
        area_upper_bound=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )
    state = _read_campaign_state(project_root)

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert state["final_status"] == RUN_STATUS_UNKNOWN
    assert state["last_stop_reason"]["reason"] == "max_attempts_exhausted"
    assert state["candidates"] == {}


def test_serial_precheck_sweep_preserves_solve_budget(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "serial_precheck_sweep_budget")
    sequence = [(4, 4, 1), (3, 3, 1), (2, 2, 1)]
    precheck_keys = {"4x1", "3x1"}

    def fake_frontier_state(
        candidates,
        campaign,
        *,
        grid_w,
        grid_h,
        frontier_probe_mode=outer_search_module.FRONTIER_PROBE_MODE_OFF,
    ):
        del candidates, grid_w, grid_h, frontier_probe_mode
        return _mock_frontier_state_from_sequence(sequence, campaign)

    def fake_precheck(*, ghost_w, ghost_h, exact_session, master_search_profile):
        del exact_session, master_search_profile
        if f"{ghost_w}x{ghost_h}" in precheck_keys:
            return {
                "triggered": True,
                "status": RUN_STATUS_INFEASIBLE,
                "proof_summary": _mock_precheck_proof_summary(
                    precheck_reason="boundary_port_all_anchors_infeasible"
                ),
            }
        return {"triggered": False, "status": None, "proof_summary": {}}

    def fake_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        del session, kwargs
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": RUN_STATUS_UNKNOWN,
                "master_boundary_port_feasibility": {
                    "supported": False,
                    "required_count": 0,
                    "considered_anchor_count": 0,
                    "screened_infeasible_anchor_count": 0,
                    "screen_pass_anchor_count": 0,
                    "unsupported_anchor_count": 0,
                    "max_packable_min": None,
                    "max_packable_max": None,
                    "first_infeasible_anchor_idx": None,
                    "first_infeasible_anchor_max_packable": None,
                },
                "master_mandatory_support_diagnostics": {
                    "unsupported_group_count": 0,
                    "empty_candidate_pool_group_count": 0,
                    "groups": [],
                },
                "master_mandatory_group_prechecks": {
                    "evaluated": False,
                    "skipped_due_to_upstream_precheck": False,
                    "upstream_anchor_filter_count": 0,
                    "supported_group_count": 0,
                    "groups": [],
                },
                "master_candidate_precheck": {
                    "triggered": False,
                    "precheck_reason": None,
                    "master_solve_skipped": False,
                    "supported": False,
                    "considered_anchor_count": 0,
                    "screened_infeasible_anchor_count": 0,
                    "screen_pass_anchor_count": 0,
                    "max_packable_min": None,
                    "max_packable_max": None,
                    "first_infeasible_anchor_idx": None,
                    "first_infeasible_anchor_max_packable": None,
                    "triggered_group_id": None,
                    "triggered_group_facility_type": None,
                    "triggered_group_operation_type": None,
                    "triggered_group_required_count": 0,
                },
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        assert (ghost_w, ghost_h) == (2, 1)
        return RUN_STATUS_UNKNOWN, None

    fake_run_benders_for_ghost_rect.last_run_metadata = {
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }

    monkeypatch.setattr(outer_search_module, "_compute_exact_frontier_state", fake_frontier_state)
    monkeypatch.setattr(
        outer_search_module,
        "evaluate_exact_candidate_pre_master_precheck",
        fake_precheck,
    )
    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        fake_run_benders_for_ghost_rect,
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=1,
        min_side=1,
        area_upper_bound=4,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )

    state = _read_campaign_state(project_root)
    telemetry = _read_campaign_telemetry(project_root)

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert state["last_stop_reason"]["reason"] == "candidate_returned_unknown"
    assert state["candidates"]["4x1"]["status"] == RUN_STATUS_INFEASIBLE
    assert state["candidates"]["4x1"]["attempts"] == 0
    assert state["candidates"]["4x1"]["proof_summary"]["precheck_lookahead"] == {
        "enabled": True,
        "slot_index": 0,
        "limit": outer_search_module._PRE_MASTER_PRECHECK_LOOKAHEAD_LIMIT,
        "is_selected_head": True,
    }
    assert state["candidates"]["3x1"]["status"] == RUN_STATUS_INFEASIBLE
    assert state["candidates"]["3x1"]["attempts"] == 0
    assert state["candidates"]["3x1"]["proof_summary"]["precheck_lookahead"] == {
        "enabled": True,
        "slot_index": 1,
        "limit": outer_search_module._PRE_MASTER_PRECHECK_LOOKAHEAD_LIMIT,
        "is_selected_head": False,
    }
    assert state["candidates"]["2x1"]["status"] == RUN_STATUS_UNKNOWN
    assert state["candidates"]["2x1"]["attempts"] == 1
    assert telemetry["aggregate"]["candidate_result_count"] == 3
    assert telemetry["aggregate"]["solve_attempt_count"] == 1
    assert telemetry["aggregate"]["precheck_elimination_count"] == 2
    assert telemetry["aggregate"]["precheck_elimination_reason_counts"] == {
        "boundary_port_all_anchors_infeasible": 2
    }
    assert telemetry["aggregate"]["precheck_head_elimination_count"] == 1
    assert telemetry["aggregate"]["precheck_lookahead_elimination_count"] == 1
    assert telemetry["aggregate"]["precheck_lookahead_elimination_reason_counts"] == {
        "boundary_port_all_anchors_infeasible": 1
    }


def test_serial_precheck_triggered_non_infeasible_does_not_mark_strong_record(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "serial_precheck_invalid_status")
    sequence = [(4, 4, 1)]
    solve_calls: list[tuple[int, int]] = []

    def fake_frontier_state(
        candidates,
        campaign,
        *,
        grid_w,
        grid_h,
        frontier_probe_mode=outer_search_module.FRONTIER_PROBE_MODE_OFF,
    ):
        del candidates, grid_w, grid_h, frontier_probe_mode
        return _mock_frontier_state_from_sequence(sequence, campaign)

    def fake_precheck(*, ghost_w, ghost_h, exact_session, master_search_profile):
        del ghost_w, ghost_h, exact_session, master_search_profile
        return {
            "triggered": True,
            "status": RUN_STATUS_UNKNOWN,
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": RUN_STATUS_UNKNOWN,
            },
        }

    def fake_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        del session, kwargs
        solve_calls.append((int(ghost_w), int(ghost_h)))
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": RUN_STATUS_UNKNOWN,
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        return RUN_STATUS_UNKNOWN, None

    fake_run_benders_for_ghost_rect.last_run_metadata = {
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }

    monkeypatch.setattr(outer_search_module, "_compute_exact_frontier_state", fake_frontier_state)
    monkeypatch.setattr(
        outer_search_module,
        "evaluate_exact_candidate_pre_master_precheck",
        fake_precheck,
    )
    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        fake_run_benders_for_ghost_rect,
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=1,
        min_side=1,
        area_upper_bound=4,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )

    state = _read_campaign_state(project_root)
    telemetry = _read_campaign_telemetry(project_root)

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert solve_calls == [(4, 1)]
    assert state["candidates"]["4x1"]["status"] == RUN_STATUS_UNKNOWN
    assert state["candidates"]["4x1"]["attempts"] == 1
    assert telemetry["aggregate"]["precheck_elimination_count"] == 0


def test_serial_precheck_lookahead_eliminates_non_head_without_writing_non_triggered(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "serial_precheck_lookahead")
    sequence = [(4, 4, 1), (3, 3, 1), (2, 2, 1)]
    precheck_keys = {"3x1"}
    precheck_calls: list[str] = []

    def fake_frontier_state(
        candidates,
        campaign,
        *,
        grid_w,
        grid_h,
        frontier_probe_mode=outer_search_module.FRONTIER_PROBE_MODE_OFF,
    ):
        del candidates, grid_w, grid_h, frontier_probe_mode
        return _mock_frontier_state_from_sequence(sequence, campaign)

    def fake_precheck(*, ghost_w, ghost_h, exact_session, master_search_profile):
        del exact_session, master_search_profile
        key = f"{ghost_w}x{ghost_h}"
        precheck_calls.append(key)
        if key in precheck_keys:
            return {
                "triggered": True,
                "status": RUN_STATUS_INFEASIBLE,
                "proof_summary": _mock_precheck_proof_summary(
                    precheck_reason="boundary_port_all_anchors_infeasible"
                ),
            }
        return {"triggered": False, "status": None, "proof_summary": {}}

    def fake_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        del session, kwargs
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": RUN_STATUS_UNKNOWN,
                "master_candidate_precheck": {
                    "triggered": False,
                    "precheck_reason": None,
                    "master_solve_skipped": False,
                },
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        assert (ghost_w, ghost_h) == (4, 1)
        return RUN_STATUS_UNKNOWN, None

    fake_run_benders_for_ghost_rect.last_run_metadata = {
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }

    monkeypatch.setattr(outer_search_module, "_compute_exact_frontier_state", fake_frontier_state)
    monkeypatch.setattr(
        outer_search_module,
        "evaluate_exact_candidate_pre_master_precheck",
        fake_precheck,
    )
    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        fake_run_benders_for_ghost_rect,
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=1,
        min_side=1,
        area_upper_bound=4,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )

    state = _read_campaign_state(project_root)
    telemetry = _read_campaign_telemetry(project_root)

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert "3x1" in state["candidates"]
    assert state["candidates"]["3x1"]["status"] == RUN_STATUS_INFEASIBLE
    assert state["candidates"]["3x1"]["attempts"] == 0
    assert state["candidates"]["3x1"]["proof_summary"]["precheck_lookahead"] == {
        "enabled": True,
        "slot_index": 1,
        "limit": outer_search_module._PRE_MASTER_PRECHECK_LOOKAHEAD_LIMIT,
        "is_selected_head": False,
    }
    assert state["candidates"]["4x1"]["status"] == RUN_STATUS_UNKNOWN
    assert state["candidates"]["4x1"]["attempts"] == 1
    assert "2x1" not in state["candidates"]
    assert precheck_calls[:3] == ["4x1", "3x1", "2x1"]
    assert telemetry["aggregate"]["candidate_result_count"] == 2
    assert telemetry["aggregate"]["solve_attempt_count"] == 1
    assert telemetry["aggregate"]["precheck_elimination_count"] == 1
    assert telemetry["aggregate"]["precheck_elimination_reason_counts"] == {
        "boundary_port_all_anchors_infeasible": 1
    }
    assert telemetry["waves"][0]["candidate_results"][0]["proof_status_summary"][
        "precheck_lookahead"
    ] == {
        "enabled": True,
        "slot_index": 1,
        "limit": outer_search_module._PRE_MASTER_PRECHECK_LOOKAHEAD_LIMIT,
        "is_selected_head": False,
    }
    assert telemetry["aggregate"]["precheck_head_elimination_count"] == 0
    assert telemetry["aggregate"]["precheck_lookahead_elimination_count"] == 1
    assert telemetry["aggregate"]["precheck_lookahead_elimination_reason_counts"] == {
        "boundary_port_all_anchors_infeasible": 1
    }


def test_max_attempts_zero_still_allows_precheck_sweep(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "serial_precheck_sweep_zero_budget")
    sequence = [(4, 4, 1), (3, 3, 1), (2, 2, 1)]
    precheck_keys = {"4x1", "3x1"}

    def fake_frontier_state(
        candidates,
        campaign,
        *,
        grid_w,
        grid_h,
        frontier_probe_mode=outer_search_module.FRONTIER_PROBE_MODE_OFF,
    ):
        del candidates, grid_w, grid_h, frontier_probe_mode
        return _mock_frontier_state_from_sequence(sequence, campaign)

    def fake_precheck(*, ghost_w, ghost_h, exact_session, master_search_profile):
        del exact_session, master_search_profile
        if f"{ghost_w}x{ghost_h}" in precheck_keys:
            return {
                "triggered": True,
                "status": RUN_STATUS_INFEASIBLE,
                "proof_summary": _mock_precheck_proof_summary(
                    precheck_reason="boundary_port_all_anchors_infeasible"
                ),
            }
        return {"triggered": False, "status": None, "proof_summary": {}}

    monkeypatch.setattr(outer_search_module, "_compute_exact_frontier_state", fake_frontier_state)
    monkeypatch.setattr(
        outer_search_module,
        "evaluate_exact_candidate_pre_master_precheck",
        fake_precheck,
    )
    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("solve path should not be reached when max_attempts=0")
        ),
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=0,
        min_side=1,
        area_upper_bound=4,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )

    state = _read_campaign_state(project_root)
    telemetry = _read_campaign_telemetry(project_root)

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert state["last_stop_reason"]["reason"] == "max_attempts_exhausted"
    assert state["candidates"]["4x1"]["attempts"] == 0
    assert state["candidates"]["3x1"]["attempts"] == 0
    assert "2x1" not in state["candidates"]
    assert telemetry["aggregate"]["candidate_result_count"] == 2
    assert telemetry["aggregate"]["solve_attempt_count"] == 0
    assert telemetry["aggregate"]["precheck_elimination_count"] == 2
    assert telemetry["aggregate"]["precheck_head_elimination_count"] == 1
    assert telemetry["aggregate"]["precheck_lookahead_elimination_count"] == 1


def test_serial_precheck_lookahead_with_zero_budget_does_not_solve_non_triggered_head(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "serial_precheck_lookahead_zero_budget")
    sequence = [(4, 4, 1), (3, 3, 1), (2, 2, 1)]

    def fake_frontier_state(
        candidates,
        campaign,
        *,
        grid_w,
        grid_h,
        frontier_probe_mode=outer_search_module.FRONTIER_PROBE_MODE_OFF,
    ):
        del candidates, grid_w, grid_h, frontier_probe_mode
        return _mock_frontier_state_from_sequence(sequence, campaign)

    def fake_precheck(*, ghost_w, ghost_h, exact_session, master_search_profile):
        del exact_session, master_search_profile
        if (ghost_w, ghost_h) == (3, 1):
            return {
                "triggered": True,
                "status": RUN_STATUS_INFEASIBLE,
                "proof_summary": _mock_precheck_proof_summary(
                    precheck_reason="boundary_port_all_anchors_infeasible"
                ),
            }
        return {"triggered": False, "status": None, "proof_summary": {}}

    monkeypatch.setattr(outer_search_module, "_compute_exact_frontier_state", fake_frontier_state)
    monkeypatch.setattr(
        outer_search_module,
        "evaluate_exact_candidate_pre_master_precheck",
        fake_precheck,
    )
    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("solve path should not be reached when max_attempts=0")
        ),
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=0,
        min_side=1,
        area_upper_bound=4,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )

    state = _read_campaign_state(project_root)
    telemetry = _read_campaign_telemetry(project_root)

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert state["last_stop_reason"]["reason"] == "max_attempts_exhausted"
    assert state["candidates"]["3x1"]["status"] == RUN_STATUS_INFEASIBLE
    assert state["candidates"]["3x1"]["attempts"] == 0
    assert "4x1" not in state["candidates"]
    assert "2x1" not in state["candidates"]
    assert telemetry["aggregate"]["candidate_result_count"] == 1
    assert telemetry["aggregate"]["solve_attempt_count"] == 0
    assert telemetry["aggregate"]["precheck_elimination_count"] == 1
    assert telemetry["aggregate"]["precheck_head_elimination_count"] == 0
    assert telemetry["aggregate"]["precheck_lookahead_elimination_count"] == 1


def test_serial_precheck_lookahead_can_exhaust_domain_without_solving(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "serial_precheck_lookahead_exhausts")
    sequence = [(4, 4, 1), (3, 3, 1), (2, 2, 1)]

    def fake_frontier_state(
        candidates,
        campaign,
        *,
        grid_w,
        grid_h,
        frontier_probe_mode=outer_search_module.FRONTIER_PROBE_MODE_OFF,
    ):
        del candidates, grid_w, grid_h, frontier_probe_mode
        return _mock_frontier_state_from_sequence(sequence, campaign)

    def fake_precheck(*, ghost_w, ghost_h, exact_session, master_search_profile):
        del ghost_w, ghost_h, exact_session, master_search_profile
        return {
            "triggered": True,
            "status": RUN_STATUS_INFEASIBLE,
            "proof_summary": _mock_precheck_proof_summary(
                precheck_reason="boundary_port_all_anchors_infeasible"
            ),
        }

    monkeypatch.setattr(outer_search_module, "_compute_exact_frontier_state", fake_frontier_state)
    monkeypatch.setattr(
        outer_search_module,
        "evaluate_exact_candidate_pre_master_precheck",
        fake_precheck,
    )
    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("solve path should not be reached when lookahead exhausts domain")
        ),
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=0,
        min_side=1,
        area_upper_bound=4,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )

    state = _read_campaign_state(project_root)
    telemetry = _read_campaign_telemetry(project_root)

    assert status == RUN_STATUS_INFEASIBLE
    assert result is None
    assert state["last_stop_reason"]["reason"] == "search_exhausted_all_candidates"
    assert sorted(state["candidates"]) == ["2x1", "3x1", "4x1"]
    assert all(record["attempts"] == 0 for record in state["candidates"].values())
    assert telemetry["aggregate"]["candidate_result_count"] == 3
    assert telemetry["aggregate"]["solve_attempt_count"] == 0
    assert telemetry["aggregate"]["precheck_elimination_count"] == 3
    assert telemetry["aggregate"]["precheck_head_elimination_count"] == 1
    assert telemetry["aggregate"]["precheck_lookahead_elimination_count"] == 2


def test_serial_precheck_lookahead_enables_mandatory_rectangle_precheck(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "serial_precheck_mandatory_rect")
    sequence = [(4, 4, 1), (3, 3, 1), (2, 2, 1)]
    include_flags: list[bool] = []

    def fake_frontier_state(
        candidates,
        campaign,
        *,
        grid_w,
        grid_h,
        frontier_probe_mode=outer_search_module.FRONTIER_PROBE_MODE_OFF,
    ):
        del candidates, grid_w, grid_h, frontier_probe_mode
        return _mock_frontier_state_from_sequence(sequence, campaign)

    def fake_precheck(
        *,
        ghost_w,
        ghost_h,
        exact_session,
        master_search_profile,
        include_mandatory_rectangle_precheck=False,
    ):
        del exact_session, master_search_profile
        include_flags.append(bool(include_mandatory_rectangle_precheck))
        if (
            (ghost_w, ghost_h) == (3, 1)
            and bool(include_mandatory_rectangle_precheck)
        ):
            proof = _mock_precheck_proof_summary(
                precheck_reason="mandatory_rect_group_all_anchors_infeasible"
            )
            proof["master_candidate_precheck"].update(
                {
                    "triggered_group_id": "group::manufacturing_6x4::refining::0",
                    "triggered_group_facility_type": "manufacturing_6x4",
                    "triggered_group_operation_type": "refining",
                    "triggered_group_required_count": 2,
                }
            )
            proof["master_mandatory_group_prechecks"] = {
                "evaluated": True,
                "skipped_due_to_upstream_precheck": False,
                "upstream_anchor_filter_count": 1,
                "supported_group_count": 1,
                "groups": [
                    {
                        "group_id": "group::manufacturing_6x4::refining::0",
                        "facility_type": "manufacturing_6x4",
                        "operation_type": "refining",
                        "required_count": 2,
                        "oracle_class": "m6x4_mixed",
                        "oracle_mode": "m6x4_mixed",
                        "supported": True,
                        "unsupported_reason": None,
                        "considered_anchor_count": 1,
                        "screened_infeasible_anchor_count": 1,
                        "screen_pass_anchor_count": 0,
                        "unsupported_anchor_count": 0,
                        "max_packable_min": 1,
                        "max_packable_max": 1,
                        "first_infeasible_anchor_idx": 0,
                        "first_infeasible_anchor_max_packable": 1,
                    }
                ],
            }
            return {
                "triggered": True,
                "status": RUN_STATUS_INFEASIBLE,
                "proof_summary": proof,
            }
        return {"triggered": False, "status": None, "proof_summary": {}}

    def fake_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        del session, kwargs
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": RUN_STATUS_UNKNOWN,
                "master_candidate_precheck": {
                    "triggered": False,
                    "precheck_reason": None,
                    "master_solve_skipped": False,
                },
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        assert (ghost_w, ghost_h) == (4, 1)
        return RUN_STATUS_UNKNOWN, None

    fake_run_benders_for_ghost_rect.last_run_metadata = {
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }

    monkeypatch.setattr(outer_search_module, "_compute_exact_frontier_state", fake_frontier_state)
    monkeypatch.setattr(
        outer_search_module,
        "evaluate_exact_candidate_pre_master_precheck",
        fake_precheck,
    )
    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        fake_run_benders_for_ghost_rect,
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=1,
        min_side=1,
        area_upper_bound=4,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )

    state = _read_campaign_state(project_root)
    telemetry = _read_campaign_telemetry(project_root)

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert include_flags[:3] == [True, True, True]
    assert state["candidates"]["3x1"]["status"] == RUN_STATUS_INFEASIBLE
    assert state["candidates"]["3x1"]["attempts"] == 0
    proof_summary = state["candidates"]["3x1"]["proof_summary"]
    assert proof_summary["master_candidate_precheck"]["precheck_reason"] == (
        "mandatory_rect_group_all_anchors_infeasible"
    )
    assert proof_summary["precheck_lookahead"] == {
        "enabled": True,
        "slot_index": 1,
        "limit": outer_search_module._PRE_MASTER_PRECHECK_LOOKAHEAD_LIMIT,
        "is_selected_head": False,
    }
    assert state["candidates"]["4x1"]["attempts"] == 1
    assert telemetry["aggregate"]["precheck_elimination_reason_counts"] == {
        "mandatory_rect_group_all_anchors_infeasible": 1
    }
    assert telemetry["aggregate"]["mandatory_group_precheck_triggered_count"] == 1
    assert telemetry["aggregate"]["mandatory_group_precheck_master_solve_skipped_count"] == 1
    assert telemetry["aggregate"]["precheck_lookahead_elimination_reason_counts"] == {
        "mandatory_rect_group_all_anchors_infeasible": 1
    }


def test_parallel_coordinator_does_not_enable_mandatory_rectangle_precheck(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "parallel_mandatory_rect_guard")
    sequence = [(4, 4, 1), (3, 3, 1)]
    include_flags: list[bool] = []
    dispatched_candidate_keys: list[str] = []

    def fake_frontier_state(
        candidates,
        campaign,
        *,
        grid_w,
        grid_h,
        frontier_probe_mode=outer_search_module.FRONTIER_PROBE_MODE_OFF,
    ):
        del candidates, grid_w, grid_h, frontier_probe_mode
        return _mock_frontier_state_from_sequence(sequence, campaign)

    def fake_precheck(
        *,
        ghost_w,
        ghost_h,
        exact_session,
        master_search_profile,
        include_mandatory_rectangle_precheck=False,
    ):
        del ghost_w, ghost_h, exact_session, master_search_profile
        include_flags.append(bool(include_mandatory_rectangle_precheck))
        if bool(include_mandatory_rectangle_precheck):
            return {
                "triggered": True,
                "status": RUN_STATUS_INFEASIBLE,
                "proof_summary": _mock_precheck_proof_summary(
                    precheck_reason="mandatory_rect_group_all_anchors_infeasible"
                ),
            }
        return {"triggered": False, "status": None, "proof_summary": {}}

    def fake_select_parallel_wave_candidate_entries(
        frontier_state,
        *,
        parallel_processes,
        remaining_attempt_budget,
    ):
        del frontier_state, parallel_processes
        assert remaining_attempt_budget == 2
        return [
            {
                "candidate": sequence[0],
                "selection_reason": "objective_head",
                "wave_slot_index": 0,
            },
            {
                "candidate": sequence[1],
                "selection_reason": "prune_head",
                "wave_slot_index": 1,
            },
        ]

    class DummyPool:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def close(self):
            return None

    def fake_run_parallel_exact_campaign_wave(*, pool, tasks):
        del pool
        dispatched_candidate_keys[:] = [
            f"{int(task.candidate[1])}x{int(task.candidate[2])}" for task in tasks
        ]
        results = tuple(
            SimpleNamespace(
                dispatch_seq=int(task.dispatch_seq),
                attempt_index=int(task.attempt_index),
                candidate=tuple(task.candidate),
                candidate_key=f"{int(task.candidate[1])}x{int(task.candidate[2])}",
                status=RUN_STATUS_INFEASIBLE,
                solution=None,
                proof_summary={
                    "mode": "certified_exact",
                    "master_status": "INFEASIBLE",
                    "master_candidate_precheck": {
                        "triggered": False,
                        "precheck_reason": None,
                        "master_solve_skipped": False,
                    },
                },
                exact_safe_cuts=[],
                loaded_exact_safe_cut_count=0,
                generated_exact_safe_cut_count=0,
                error=None,
            )
            for task in tasks
        )
        return SimpleNamespace(
            completed=True,
            failure_reason=None,
            results=results,
            dispatched_candidate_keys=tuple(dispatched_candidate_keys),
            elapsed_seconds=0.01,
            peak_rss_bytes_external_total=0,
            peak_rss_bytes_internal_max_single_process=0,
        )

    monkeypatch.setattr(outer_search_module, "_compute_exact_frontier_state", fake_frontier_state)
    monkeypatch.setattr(
        outer_search_module,
        "evaluate_exact_candidate_pre_master_precheck",
        fake_precheck,
    )
    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "_select_parallel_wave_candidate_entries",
        fake_select_parallel_wave_candidate_entries,
    )
    monkeypatch.setattr(outer_search_module, "ExactParallelWorkerPool", DummyPool)
    monkeypatch.setattr(
        outer_search_module,
        "run_parallel_exact_campaign_wave",
        fake_run_parallel_exact_campaign_wave,
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=2,
        min_side=1,
        area_upper_bound=4,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=2,
    )

    telemetry = _read_campaign_telemetry(project_root)

    assert status == RUN_STATUS_INFEASIBLE
    assert result is None
    assert include_flags == [False, False]
    assert dispatched_candidate_keys == ["4x1", "3x1"]
    assert telemetry["aggregate"]["precheck_elimination_count"] == 0
    assert telemetry["aggregate"]["solve_attempt_count"] == 2


def test_parallel_coordinator_sweeps_precheck_candidates_before_worker_dispatch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "parallel_precheck_sweep")
    sequence = [(4, 4, 1), (3, 3, 1), (2, 2, 1)]
    dispatched_candidate_keys: list[str] = []

    def fake_frontier_state(
        candidates,
        campaign,
        *,
        grid_w,
        grid_h,
        frontier_probe_mode=outer_search_module.FRONTIER_PROBE_MODE_OFF,
    ):
        del candidates, grid_w, grid_h, frontier_probe_mode
        return _mock_frontier_state_from_sequence(sequence, campaign)

    def fake_precheck(*, ghost_w, ghost_h, exact_session, master_search_profile):
        del exact_session, master_search_profile
        if (ghost_w, ghost_h) == (3, 1):
            return {
                "triggered": True,
                "status": RUN_STATUS_INFEASIBLE,
                "proof_summary": _mock_precheck_proof_summary(
                    precheck_reason="boundary_port_all_anchors_infeasible"
                ),
            }
        return {"triggered": False, "status": None, "proof_summary": {}}

    def fake_select_parallel_wave_candidate_entries(
        frontier_state,
        *,
        parallel_processes,
        remaining_attempt_budget,
    ):
        del frontier_state, parallel_processes
        assert remaining_attempt_budget == 2
        return [
            {
                "candidate": sequence[0],
                "selection_reason": "objective_head",
                "wave_slot_index": 0,
            },
            {
                "candidate": sequence[1],
                "selection_reason": "prune_head",
                "wave_slot_index": 1,
            },
            {
                "candidate": sequence[2],
                "selection_reason": "anchor_head",
                "wave_slot_index": 2,
            },
        ]

    class DummyPool:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def close(self):
            return None

    def fake_run_parallel_exact_campaign_wave(*, pool, tasks):
        del pool
        dispatched_candidate_keys[:] = [
            f"{int(task.candidate[1])}x{int(task.candidate[2])}" for task in tasks
        ]
        results = tuple(
            SimpleNamespace(
                dispatch_seq=int(task.dispatch_seq),
                attempt_index=int(task.attempt_index),
                candidate=tuple(task.candidate),
                candidate_key=f"{int(task.candidate[1])}x{int(task.candidate[2])}",
                status=RUN_STATUS_INFEASIBLE,
                solution=None,
                proof_summary={
                    "mode": "certified_exact",
                    "master_status": "INFEASIBLE",
                    "master_candidate_precheck": {
                        "triggered": False,
                        "precheck_reason": None,
                        "master_solve_skipped": False,
                    },
                },
                exact_safe_cuts=[],
                loaded_exact_safe_cut_count=0,
                generated_exact_safe_cut_count=0,
                error=None,
            )
            for task in tasks
        )
        return SimpleNamespace(
            completed=True,
            failure_reason=None,
            results=results,
            dispatched_candidate_keys=tuple(dispatched_candidate_keys),
            elapsed_seconds=0.01,
            peak_rss_bytes_external_total=0,
            peak_rss_bytes_internal_max_single_process=0,
        )

    monkeypatch.setattr(outer_search_module, "_compute_exact_frontier_state", fake_frontier_state)
    monkeypatch.setattr(
        outer_search_module,
        "evaluate_exact_candidate_pre_master_precheck",
        fake_precheck,
    )
    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "_select_parallel_wave_candidate_entries",
        fake_select_parallel_wave_candidate_entries,
    )
    monkeypatch.setattr(outer_search_module, "ExactParallelWorkerPool", DummyPool)
    monkeypatch.setattr(
        outer_search_module,
        "run_parallel_exact_campaign_wave",
        fake_run_parallel_exact_campaign_wave,
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=2,
        min_side=1,
        area_upper_bound=4,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=2,
    )

    state = _read_campaign_state(project_root)
    telemetry = _read_campaign_telemetry(project_root)

    assert status == RUN_STATUS_INFEASIBLE
    assert result is None
    assert dispatched_candidate_keys == ["4x1", "2x1"]
    assert state["candidates"]["4x1"]["attempts"] == 1
    assert state["candidates"]["3x1"]["attempts"] == 0
    assert state["candidates"]["3x1"]["proof_summary"]["precheck_lookahead"] == {
        "enabled": False,
        "slot_index": 1,
        "limit": 0,
        "is_selected_head": False,
    }
    assert state["candidates"]["2x1"]["attempts"] == 1
    assert telemetry["aggregate"]["candidate_result_count"] == 3
    assert telemetry["aggregate"]["solve_attempt_count"] == 2
    assert telemetry["aggregate"]["precheck_elimination_count"] == 1
    assert telemetry["aggregate"]["precheck_lookahead_elimination_count"] == 0


def test_parallel_precheck_triggered_non_infeasible_is_dispatched_to_worker(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "parallel_precheck_invalid_status")
    sequence = [(4, 4, 1), (3, 3, 1)]
    dispatched_candidate_keys: list[str] = []

    def fake_frontier_state(
        candidates,
        campaign,
        *,
        grid_w,
        grid_h,
        frontier_probe_mode=outer_search_module.FRONTIER_PROBE_MODE_OFF,
    ):
        del candidates, grid_w, grid_h, frontier_probe_mode
        return _mock_frontier_state_from_sequence(sequence, campaign)

    def fake_precheck(*, ghost_w, ghost_h, exact_session, master_search_profile):
        del ghost_w, ghost_h, exact_session, master_search_profile
        return {
            "triggered": True,
            "status": RUN_STATUS_UNKNOWN,
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": RUN_STATUS_UNKNOWN,
            },
        }

    def fake_select_parallel_wave_candidate_entries(
        frontier_state,
        *,
        parallel_processes,
        remaining_attempt_budget,
    ):
        del frontier_state, parallel_processes, remaining_attempt_budget
        return [
            {
                "candidate": sequence[0],
                "selection_reason": "objective_head",
                "wave_slot_index": 0,
            },
            {
                "candidate": sequence[1],
                "selection_reason": "prune_head",
                "wave_slot_index": 1,
            },
        ]

    class DummyPool:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def close(self):
            return None

    def fake_run_parallel_exact_campaign_wave(*, pool, tasks):
        del pool
        dispatched_candidate_keys[:] = [
            f"{int(task.candidate[1])}x{int(task.candidate[2])}" for task in tasks
        ]
        return SimpleNamespace(
            completed=True,
            failure_reason=None,
            results=tuple(
                SimpleNamespace(
                    dispatch_seq=int(task.dispatch_seq),
                    attempt_index=int(task.attempt_index),
                    candidate=tuple(task.candidate),
                    candidate_key=f"{int(task.candidate[1])}x{int(task.candidate[2])}",
                    status=RUN_STATUS_INFEASIBLE,
                    solution=None,
                    proof_summary={
                        "mode": "certified_exact",
                        "master_status": RUN_STATUS_INFEASIBLE,
                    },
                    exact_safe_cuts=[],
                    loaded_exact_safe_cut_count=0,
                    generated_exact_safe_cut_count=0,
                    error=None,
                )
                for task in tasks
            ),
            dispatched_candidate_keys=tuple(dispatched_candidate_keys),
            elapsed_seconds=0.01,
            peak_rss_bytes_external_total=0,
            peak_rss_bytes_internal_max_single_process=0,
        )

    monkeypatch.setattr(outer_search_module, "_compute_exact_frontier_state", fake_frontier_state)
    monkeypatch.setattr(
        outer_search_module,
        "evaluate_exact_candidate_pre_master_precheck",
        fake_precheck,
    )
    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        lambda *args, **kwargs: SimpleNamespace(core=object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "_select_parallel_wave_candidate_entries",
        fake_select_parallel_wave_candidate_entries,
    )
    monkeypatch.setattr(outer_search_module, "ExactParallelWorkerPool", DummyPool)
    monkeypatch.setattr(
        outer_search_module,
        "run_parallel_exact_campaign_wave",
        fake_run_parallel_exact_campaign_wave,
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=2,
        min_side=1,
        area_upper_bound=4,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=2,
    )

    state = _read_campaign_state(project_root)
    telemetry = _read_campaign_telemetry(project_root)

    assert status == RUN_STATUS_INFEASIBLE
    assert result is None
    assert dispatched_candidate_keys == ["4x1", "3x1"]
    assert state["candidates"]["4x1"]["attempts"] == 1
    assert state["candidates"]["3x1"]["attempts"] == 1
    assert telemetry["aggregate"]["precheck_elimination_count"] == 0


def test_certified_result_writes_canonical_optimal_blueprint(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "toy_blueprint_export")

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=4,
        min_side=1,
        area_upper_bound=1,
        master_seconds=5.0,
        binding_seconds=5.0,
        routing_seconds=5.0,
        benders_max_iter=2,
        campaign_hours=1.0,
        resume_campaign=False,
    )

    final_solution_path = project_root / "data" / "solutions" / "final_solution.json"
    blueprint_path = project_root / "data" / "blueprints" / "optimal_blueprint.json"
    manifest_path = delivery_manifest_output_path(project_root)

    assert status == RUN_STATUS_CERTIFIED
    assert result is not None
    assert final_solution_path.exists()
    assert blueprint_path.exists()
    assert manifest_path.exists()

    final_solution_payload = json.loads(final_solution_path.read_text(encoding="utf-8"))
    blueprint_payload = normalize_blueprint_payload(
        json.loads(blueprint_path.read_text(encoding="utf-8"))
    )
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert final_solution_payload["ghost_rect"] == {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0}
    assert blueprint_payload["objective_achieved"]["empty_rect"]["w"] == 1
    assert blueprint_payload["objective_achieved"]["empty_rect"]["h"] == 1
    assert blueprint_payload["facilities"][0]["instance_id"] == "tiny_001"
    assert blueprint_payload["facilities"][0]["orientation"] == 0
    assert blueprint_payload["facilities"][0]["port_mode"] == "default"
    assert blueprint_payload["routing_network"] == {"L0_ground": {}, "L1_elevated": {}}
    assert manifest_payload["campaign"]["final_status"] == RUN_STATUS_CERTIFIED
    assert manifest_payload["best_certified_result"]["ghost_rect"] == {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0}
    assert manifest_payload["artifacts"]["final_solution"]["exists"] is True
    assert manifest_payload["artifacts"]["optimal_blueprint"]["exists"] is True


def test_exact_path_publishes_core_reuse_metadata(tmp_path: Path) -> None:
    project_root = _build_toy_exact_project(tmp_path / "core_reuse_metadata")

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=5.0,
        binding_seconds=5.0,
        routing_seconds=5.0,
        max_iterations=2,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")

    assert status == RUN_STATUS_CERTIFIED
    assert result is not None
    assert metadata["used_exact_core_reuse"] is True
    assert metadata["core_build_seconds"] >= 0.0
    assert metadata["overlay_build_seconds"] >= 0.0
    assert metadata["ghost_constraint_seconds"] >= 0.0
    assert metadata["cut_replay_seconds"] >= 0.0
    assert metadata["master_search_profile"] == "exact_coordinate_guided_branching_v4"
    assert "power_pole_family_order" in metadata
    assert "power_pole_family_count_literals" in metadata
    assert "residual_optional_family_guided" in metadata
    assert metadata["binding_search_profile"] == "exact_binding_guided_branching_v1"
    assert metadata["used_routing_core_reuse"] is True
    assert metadata["routing_core_build_seconds"] >= 0.0
    assert metadata["routing_overlay_build_seconds"] >= 0.0
    assert "binding_domain_cache_hits" in metadata
    assert "binding_domain_cache_misses" in metadata
    assert metadata["master_representation"] == "coordinate_exact_v2"
    assert metadata["master_pose_bool_literals"] == 0
    assert metadata["master_domain_encoding"] == "mode_rect_factorized_v1"
    assert metadata["master_domain_table_rows"] == 0
    assert "power_coverage_representation" in metadata
    assert "power_coverage_encoding" in metadata
    assert "power_coverage_cover_literals" in metadata
    assert "power_coverage_witness_indices" in metadata
    assert "power_coverage_element_constraints" in metadata
    assert "power_capacity_shell_pairs" in metadata
    assert "power_capacity_shell_pair_evaluations" in metadata
    assert "power_capacity_signature_classes" in metadata
    assert "power_capacity_signature_class_evaluations" in metadata
    assert "power_capacity_compact_signature_classes" in metadata
    assert "power_capacity_compact_signature_evaluations" in metadata
    assert "power_capacity_compact_signature_cache_hits" in metadata
    assert "power_capacity_compact_signature_cache_misses" in metadata
    assert "power_capacity_compact_rect_cpsat_evaluations" in metadata
    assert "power_capacity_compact_rect_cpsat_cache_hits" in metadata
    assert "power_capacity_compact_rect_cpsat_selected_cases" in metadata
    assert "power_capacity_compact_rect_cpsat_rect_dp_fallbacks" in metadata
    assert "power_capacity_normalized_rect_signature_count" in metadata
    assert "power_capacity_normalized_rect_cache_hits" in metadata
    assert "power_capacity_normalized_rect_cache_misses" in metadata
    assert "power_capacity_legacy_signature_materializations" in metadata
    assert "power_capacity_supported_by_pole_materializations" in metadata
    assert "power_capacity_rect_dp_evaluations" in metadata
    assert "power_capacity_rect_dp_cache_hits" in metadata
    assert "power_capacity_rect_dp_cache_misses" in metadata
    assert "power_capacity_rect_dp_state_merges" in metadata
    assert "power_capacity_rect_dp_peak_line_states" in metadata
    assert "power_capacity_rect_dp_peak_pos_states" in metadata
    assert "power_capacity_rect_dp_compiled_signatures" in metadata
    assert "power_capacity_rect_dp_compiled_start_options" in metadata
    assert "power_capacity_rect_dp_deduped_start_options" in metadata
    assert "power_capacity_rect_dp_compiled_line_subsets" in metadata
    assert "power_capacity_rect_dp_peak_line_subset_options" in metadata
    assert "power_capacity_rect_dp_v3_fallbacks" in metadata
    assert "power_capacity_uniform_3x3_cpsat_evaluations" in metadata
    assert "power_capacity_uniform_3x3_cpsat_cache_hits" in metadata
    assert "power_capacity_uniform_3x3_cpsat_selected_cases" in metadata
    assert "power_capacity_uniform_3x3_cpsat_v3_fallbacks" in metadata
    assert "power_capacity_bitset_oracle_evaluations" in metadata
    assert "power_capacity_bitset_fallbacks" in metadata
    assert "power_capacity_cpsat_fallbacks" in metadata
    assert "power_capacity_oracle" in metadata
    assert "master_domain_tightening" in metadata["proof_summary"]
    assert "ghost_power_capacity_screen_enabled" in metadata["proof_summary"]["master_domain_tightening"]
    assert "ghost_conditioned_family_upper_bound_constraints" in metadata["proof_summary"]["master_domain_tightening"]
    assert "master_signature_tightening" in metadata["proof_summary"]
    assert "mandatory_bucket_upper_bound_constraints" in metadata["proof_summary"]["master_signature_tightening"]
    assert (
        "ghost_conditioned_required_optional_bucket_constraints"
        in metadata["proof_summary"]["master_signature_tightening"]
    )
    assert "master_residual_signature_tightening" in metadata["proof_summary"]
    assert (
        "ghost_conditioned_bucket_constraints"
        in metadata["proof_summary"]["master_residual_signature_tightening"]
    )
    assert "master_coordinate_symmetry" in metadata["proof_summary"]
    assert (
        "mandatory_signature_monotonic_constraints"
        in metadata["proof_summary"]["master_coordinate_symmetry"]
    )
    assert (
        "required_optional_signature_monotonic_constraints"
        in metadata["proof_summary"]["master_coordinate_symmetry"]
    )
    assert (
        "residual_optional_signature_monotonic_constraints"
        in metadata["proof_summary"]["master_coordinate_symmetry"]
    )
    assert "master_last_solve" in metadata["proof_summary"]
    assert "branches" in metadata["proof_summary"]["master_last_solve"]
    assert "conflicts" in metadata["proof_summary"]["master_last_solve"]
    assert "deterministic_time" in metadata["proof_summary"]["master_last_solve"]
    assert "power_capacity_raw_pole_evaluations" in metadata
    assert "signature_bucket_cache_hits" in metadata
    assert "signature_bucket_cache_misses" in metadata
    assert "signature_bucket_distinct_keys" in metadata
    assert "geometry_cache_templates" in metadata
    assert metadata["power_capacity_oracle"] == "compact_rect_cpsat_v2"
    assert metadata["power_coverage_encoding"] == "table_pairwise_witness_v1"
    assert metadata["power_coverage_cover_literals"] == 0
    assert metadata["power_coverage_witness_indices"] == 0


def test_certification_first_frontier_prefers_prune_per_anchor_over_objective_head() -> None:
    candidates = generate_candidate_sizes(
        max_w=6,
        max_h=6,
        min_side=1,
        area_upper_bound=9,
    )

    frontier_state = outer_search_module._compute_exact_frontier_state(
        candidates,
        None,
        grid_w=6,
        grid_h=6,
    )

    assert frontier_state["frontier"][0] == (9, 3, 3)
    assert frontier_state["selected_candidate"] == (6, 6, 1)
    # V82: the candidate domain is oriented, so transposed candidates exist;
    # objective-dominance prune gain and frontier size grow accordingly.
    assert frontier_state["selected_candidate_metrics"] == {
        "selection_score_num": 2,
        "selection_score_den": 1,
        "certification_prune_gain": 12,
        "infeasible_prune_gain": 1,
        "anchor_count": 6,
        "frontier_size": 5,
    }


def test_frontier_probe_auto_selects_non_frontier_mid_domain_candidate() -> None:
    candidates = generate_candidate_sizes(
        max_w=12,
        max_h=12,
        min_side=1,
        area_upper_bound=60,
    )

    frontier_state = outer_search_module._compute_exact_frontier_state(
        candidates,
        None,
        grid_w=12,
        grid_h=12,
        frontier_probe_mode="auto",
    )

    assert frontier_state["probe_round_active"] is True
    assert frontier_state["selected_candidate_reason"] == "probe_head"
    assert frontier_state["selected_candidate"] == (30, 6, 5)
    assert frontier_state["probe_candidate"] == (30, 6, 5)
    assert frontier_state["probe_candidate"] not in frontier_state["frontier"]
    assert frontier_state["frontier_selected_candidate"] in frontier_state["frontier"]
    assert frontier_state["probe_candidate_source"] == outer_search_module.FRONTIER_PROBE_SELECTION_POLICY
    assert frontier_state["probe_candidate_metrics"]["probe_candidate"] == 1
    assert frontier_state["probe_candidate_metrics"]["anchor_count"] == 56
    # V82 oriented domain: the probe's objective-dominance gain covers the
    # transposed candidates as well.
    assert frontier_state["probe_candidate_metrics"]["probe_prune_gain"] == 69


def test_frontier_probe_auto_skips_probe_when_anchor_count_exceeds_cap(monkeypatch) -> None:
    candidates = generate_candidate_sizes(
        max_w=12,
        max_h=12,
        min_side=1,
        area_upper_bound=60,
    )
    monkeypatch.setenv(outer_search_module._FRONTIER_PROBE_MAX_ANCHORS_ENV, "1")

    frontier_state = outer_search_module._compute_exact_frontier_state(
        candidates,
        None,
        grid_w=12,
        grid_h=12,
        frontier_probe_mode="auto",
    )

    assert frontier_state["probe_round_active"] is False
    assert frontier_state["probe_candidate"] is None
    assert frontier_state["selected_candidate_reason"] != "probe_head"
    assert frontier_state["selected_candidate"] == frontier_state["frontier_selected_candidate"]


def test_frontier_selection_tiebreak_falls_back_to_objective_order(monkeypatch) -> None:
    def fake_metrics(candidate, potential_domain, *, grid_w: int, grid_h: int):
        return {
            "selection_score_num": 7,
            "selection_score_den": 5,
            "certification_prune_gain": 7,
            "infeasible_prune_gain": 2,
            "anchor_count": 5,
        }

    monkeypatch.setattr(outer_search_module, "_compute_frontier_candidate_metrics", fake_metrics)

    selected_candidate, selected_metrics, metrics_by_key = outer_search_module._select_frontier_candidate(
        [(12, 6, 2), (12, 4, 3)],
        [(12, 6, 2), (12, 4, 3)],
        grid_w=6,
        grid_h=6,
    )

    assert selected_candidate == (12, 4, 3)
    assert selected_metrics["frontier_size"] == 2
    assert metrics_by_key["6x2"]["frontier_size"] == 2
    assert metrics_by_key["4x3"]["frontier_size"] == 2


def test_generate_candidate_sizes_orders_by_area_then_min_side() -> None:
    candidates = generate_candidate_sizes(
        max_w=40,
        max_h=40,
        min_side=1,
        area_upper_bound=400,
    )

    positions = {candidate: idx for idx, candidate in enumerate(candidates)}

    assert positions[(12, 4, 3)] < positions[(12, 6, 2)]
    assert positions[(400, 20, 20)] < positions[(400, 40, 10)]


def test_campaign_candidate_records_keep_area_then_min_side_incumbents_non_terminal(
    tmp_path: Path,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "campaign_area_min_side_objective")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)

    campaign.mark_candidate_started(6, 2)
    campaign.mark_candidate_result(
        6,
        2,
        RUN_STATUS_CERTIFIED,
        solution={
            "long_corridor": {
                "pose_idx": 0,
                "pose_id": "ghost_6x2",
                "facility_type": "synthetic",
                "anchor": {"x": 0, "y": 0},
            }
        },
        proof_summary={"master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.mark_candidate_started(4, 3)
    campaign.mark_candidate_result(
        4,
        3,
        RUN_STATUS_CERTIFIED,
        solution={
            "better_min_side": {
                "pose_idx": 0,
                "pose_id": "ghost_4x3",
                "facility_type": "synthetic",
                "anchor": {"x": 0, "y": 0},
            }
        },
        proof_summary={"master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.mark_candidate_started(40, 10)
    campaign.mark_candidate_result(
        40,
        10,
        RUN_STATUS_CERTIFIED,
        solution={
            "wide_corridor": {
                "pose_idx": 0,
                "pose_id": "ghost_40x10",
                "facility_type": "synthetic",
                "anchor": {"x": 0, "y": 0},
            }
        },
        proof_summary={"master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.mark_candidate_started(20, 20)
    campaign.mark_candidate_result(
        20,
        20,
        RUN_STATUS_CERTIFIED,
        solution={
            "square_best": {
                "pose_idx": 0,
                "pose_id": "ghost_20x20",
                "facility_type": "synthetic",
                "anchor": {"x": 0, "y": 0},
            }
        },
        proof_summary={"master_status": RUN_STATUS_CERTIFIED},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )

    best_result = campaign.best_certified_result()

    assert best_result is None
    assert campaign.state.get("final_result") is None
    assert campaign.get_candidate_record(20, 20)["status"] == RUN_STATUS_CERTIFIED
    assert campaign.get_candidate_record(20, 20)["solution"]["square_best"]["pose_id"] == "ghost_20x20"


def test_antichain_frontier_matches_bruteforce_and_preserves_tiebreak(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "frontier_bruteforce", width=6, height=6)
    calls: list[tuple[int, int, bool]] = []

    def _is_feasible(ghost_w: int, ghost_h: int) -> bool:
        return (ghost_w <= 4 and ghost_h <= 3) or (ghost_w <= 6 and ghost_h <= 2)

    def fake_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        calls.append((ghost_w, ghost_h, session is not None))
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": "FEASIBLE" if _is_feasible(ghost_w, ghost_h) else "INFEASIBLE",
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        if _is_feasible(ghost_w, ghost_h):
            return RUN_STATUS_CERTIFIED, {
                "ghost_pick": {
                    "pose_idx": 0,
                    "pose_id": "synthetic_pose_0",
                    "anchor": {"x": 0, "y": 0},
                    "facility_type": "synthetic",
                }
            }
        return RUN_STATUS_INFEASIBLE, None

    fake_run_benders_for_ghost_rect.last_run_metadata = {
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }

    monkeypatch.setattr(outer_search_module, "run_benders_for_ghost_rect", fake_run_benders_for_ghost_rect)
    monkeypatch.setattr(
        outer_search_module.ExactSearchSession,
        "create",
        staticmethod(lambda project_root, solve_mode="certified_exact": object()),
    )

    explicit_candidates = generate_candidate_sizes(
        max_w=6,
        max_h=6,
        min_side=1,
    )
    frontier_state = outer_search_module._compute_exact_frontier_state(
        explicit_candidates,
        None,
        grid_w=6,
        grid_h=6,
    )
    expected = max(
        (candidate for candidate in explicit_candidates if _is_feasible(candidate[1], candidate[2])),
        key=lambda item: (item[0], min(item[1], item[2])),
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=64,
        min_side=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )

    assert status == RUN_STATUS_CERTIFIED
    assert result is not None
    # V88: the published ghost_rect carries the proven anchor; the mock pick
    # always anchors at (0,0).
    assert result["ghost_rect"] == {
        "w": expected[1],
        "h": expected[2],
        "area": expected[0],
        "anchor_x": 0,
        "anchor_y": 0,
    }
    assert calls[0][:2] == (
        frontier_state["selected_candidate"][1],
        frontier_state["selected_candidate"][2],
    )
    assert result["search_stats"]["frontier_peak_size"] >= 1
    assert result["search_stats"]["derived_pruned_candidates"] > 0
    assert (
        result["search_stats"]["frontier_selection_policy"]
        == outer_search_module.FRONTIER_SELECTION_POLICY
    )
    assert result["search_stats"]["frontier_candidate_metrics"]
    assert all(item[2] is True for item in calls)

    state = _read_campaign_state(project_root)
    first_candidate_key = f"{calls[0][0]}x{calls[0][1]}"
    assert (
        state["candidates"][first_candidate_key]["proof_summary"]["frontier_selection_policy"]
        == outer_search_module.FRONTIER_SELECTION_POLICY
    )
    assert state["candidates"][first_candidate_key]["proof_summary"]["frontier_candidate_metrics"]


def test_unknown_candidate_is_retried_on_resume_without_monotone_prune(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "frontier_unknown_resume", width=2, height=2)
    call_counts: dict[tuple[int, int], int] = {}

    def fake_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        key = (ghost_w, ghost_h)
        call_counts[key] = call_counts.get(key, 0) + 1
        attempt = call_counts[key]
        if key == (2, 2) and attempt == 1:
            fake_run_benders_for_ghost_rect.last_run_metadata = {
                "proof_summary": {"mode": "certified_exact", "master_status": "UNKNOWN"},
                "exact_safe_cuts": [],
                "loaded_exact_safe_cut_count": 0,
                "generated_exact_safe_cut_count": 0,
            }
            return RUN_STATUS_UNKNOWN, None
        if key == (2, 2):
            fake_run_benders_for_ghost_rect.last_run_metadata = {
                "proof_summary": {"mode": "certified_exact", "master_status": "INFEASIBLE"},
                "exact_safe_cuts": [],
                "loaded_exact_safe_cut_count": 0,
                "generated_exact_safe_cut_count": 0,
            }
            return RUN_STATUS_INFEASIBLE, None

        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {"mode": "certified_exact", "master_status": "FEASIBLE"},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        return RUN_STATUS_CERTIFIED, {
            "ghost_pick": {
                "pose_idx": 0,
                "pose_id": "synthetic_pose_0",
                "anchor": {"x": 0, "y": 0},
                "facility_type": "synthetic",
            }
        }

    fake_run_benders_for_ghost_rect.last_run_metadata = {
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }

    monkeypatch.setattr(outer_search_module, "run_benders_for_ghost_rect", fake_run_benders_for_ghost_rect)
    monkeypatch.setattr(
        outer_search_module.ExactSearchSession,
        "create",
        staticmethod(lambda project_root, solve_mode="certified_exact": object()),
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=2,
        min_side=1,
        area_upper_bound=4,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )
    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert call_counts[(2, 2)] == 1

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=4,
        min_side=1,
        area_upper_bound=4,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=True,
    )

    assert status == RUN_STATUS_CERTIFIED
    assert result is not None
    assert result["ghost_rect"] == {"w": 2, "h": 1, "area": 2, "anchor_x": 0, "anchor_y": 0}
    assert call_counts[(2, 2)] == 2


def test_prune_first_partial_run_can_deviate_from_objective_prefix_and_resume(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_frontier_project(tmp_path / "frontier_prune_first_resume", width=6, height=6)
    calls: list[tuple[int, int]] = []

    def _is_feasible(ghost_w: int, ghost_h: int) -> bool:
        return (ghost_w, ghost_h) == (6, 1)

    def fake_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        calls.append((ghost_w, ghost_h))
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": "FEASIBLE" if _is_feasible(ghost_w, ghost_h) else "INFEASIBLE",
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        if _is_feasible(ghost_w, ghost_h):
            return RUN_STATUS_CERTIFIED, {
                "ghost_pick": {
                    "pose_idx": 0,
                    "pose_id": "synthetic_pose_0",
                    "anchor": {"x": 0, "y": 0},
                    "facility_type": "synthetic",
                }
            }
        return RUN_STATUS_INFEASIBLE, None

    fake_run_benders_for_ghost_rect.last_run_metadata = {
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }

    monkeypatch.setattr(outer_search_module, "run_benders_for_ghost_rect", fake_run_benders_for_ghost_rect)
    monkeypatch.setattr(
        outer_search_module.ExactSearchSession,
        "create",
        staticmethod(lambda project_root, solve_mode="certified_exact": object()),
    )

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=4,
        min_side=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    # V82 oriented domain: objective order is (6,6),(6,5),(5,6),(5,5),(6,4),...
    # prune-first deviates at step 4 by taking (6,4) before objective head (5,5).
    assert calls == [(6, 6), (6, 5), (5, 6), (6, 4)]

    partial_state = _read_campaign_state(project_root)
    assert "6x4" in partial_state["candidates"]
    # prune-first 偏离 objective 前缀: objective 头 (5,5) 还没被解,
    # 部分跑可以偏离 objective 序而 resume 后仍收敛。
    assert "5x5" not in partial_state["candidates"]
    assert partial_state["last_stop_reason"]["reason"] == "max_attempts_exhausted"

    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=32,
        min_side=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=True,
    )

    assert status == RUN_STATUS_CERTIFIED
    assert result is not None
    assert result["ghost_rect"] == {"w": 6, "h": 1, "area": 6, "anchor_x": 0, "anchor_y": 0}


def _clear_exact_env_for_v80_guard(monkeypatch) -> None:
    for key in list(benders_loop_module.os.environ):
        if str(key).startswith("EXACT_"):
            monkeypatch.delenv(str(key), raising=False)


def test_v80_certified_exact_env_guard_blocks_unclassified_exact_knob(monkeypatch) -> None:
    _clear_exact_env_for_v80_guard(monkeypatch)
    future_env = "EX" "ACT_" "FUTURE_UNREVIEWED_KNOB"
    monkeypatch.setenv(future_env, "0")

    blockers = benders_loop_module._collect_forbidden_certified_master_domain_env_overrides()

    assert blockers == [
        {
            "code": "unclassified_exact_env_not_certified",
            "env": future_env,
            "value": "0",
            "detail": "unknown EXACT_* env is not on the certified_exact allowlist",
        }
    ]


def test_v80_certified_exact_env_guard_blocks_known_proof_knob(monkeypatch) -> None:
    _clear_exact_env_for_v80_guard(monkeypatch)
    monkeypatch.setenv("EXACT_B1_SEPARATOR_HULL", "1")

    blockers = benders_loop_module._collect_forbidden_certified_master_domain_env_overrides()

    assert blockers == [
        {
            "code": "proof_semantics_exact_env_not_certified",
            "env": "EXACT_B1_SEPARATOR_HULL",
            "value": "1",
            "detail": (
                "EXACT_* env is classified proof-semantics-affecting and has "
                "no certified canonical non-default override"
            ),
        }
    ]


def test_v80_certified_exact_env_guard_allows_production_wrapper_operational_envs(
    monkeypatch,
) -> None:
    _clear_exact_env_for_v80_guard(monkeypatch)
    monkeypatch.setenv("EXACT_MASTER_CP_SAT_WORKERS", "2")
    monkeypatch.setenv("EX" "ACT_" "GATE_WORKER_PEAK_RSS_GIB", "20.5")
    monkeypatch.setenv("EXACT_OUTER_SKIP_UNKNOWN", "0")
    monkeypatch.setenv("EXACT_COMMUNITY_BLUEPRINT_HINT_PATH", "/tmp/community_hint.json")
    monkeypatch.setenv("EXACT_PARALLEL_PROCESSES", "2")

    blockers = benders_loop_module._collect_forbidden_certified_master_domain_env_overrides()

    assert blockers == []


def test_v81_mandatory_rectangle_partial_time_budget_group_is_not_infeasible() -> None:
    partial_group = {
        "group_id": "g_partial",
        "supported": True,
        "considered_anchor_count": 1,
        "screened_infeasible_anchor_count": 1,
        "screen_pass_anchor_count": 0,
        "unsupported_anchor_count": 0,
        "partial_due_to_time_budget": True,
    }
    triggered = benders_loop_module._triggered_mandatory_rectangle_precheck_group(
        {"groups": [partial_group]}
    )
    assert triggered is None


def test_v81_mandatory_rectangle_complete_group_still_triggers_infeasible() -> None:
    complete_group = {
        "group_id": "g_complete",
        "supported": True,
        "considered_anchor_count": 3,
        "screened_infeasible_anchor_count": 3,
        "screen_pass_anchor_count": 0,
        "unsupported_anchor_count": 0,
    }
    triggered = benders_loop_module._triggered_mandatory_rectangle_precheck_group(
        {"groups": [complete_group]}
    )
    assert triggered is not None
    assert triggered["group_id"] == "g_complete"


def test_outer_search_rejects_wireless_slot_drift_between_frontier_and_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = _build_toy_exact_project(tmp_path / "outer_snapshot_slot_drift")
    generic_io_requirements = {
        "required_generic_outputs": {},
        "required_generic_inputs": {"valley_battery": 1},
    }
    _write_json(
        project_root / "data" / "preprocessed" / "generic_io_requirements.json",
        generic_io_requirements,
    )
    _write_json(
        project_root / "rules" / "preprocess_plan.json",
        {"utility_operations": {"wireless_sink": {"generic_input_slots": 3}}},
    )

    monkeypatch.setattr(
        outer_search_module,
        "load_generic_io_requirements_artifact",
        lambda _project_root: generic_io_requirements,
    )
    monkeypatch.setattr(
        outer_search_module,
        "compute_exact_static_area_lower_bound",
        lambda *_args, **_kwargs: 0,
    )
    monkeypatch.setattr(
        outer_search_module,
        "generate_candidate_sizes",
        lambda **_kwargs: [(1, 1, 1)],
    )
    monkeypatch.setattr(
        outer_search_module,
        "_compute_exact_frontier_state",
        lambda *_args, **_kwargs: {
            "potential_domain": [(1, 1, 1)],
            "frontier_size": 1,
            "frontier": [(1, 1, 1)],
            "best_certified_candidate": None,
            "best_certified_record": None,
            "frontier_metrics_by_key": {"1x1": {}},
            "frontier_probe_mode": outer_search_module.FRONTIER_PROBE_MODE_OFF,
        },
    )
    monkeypatch.setattr(
        outer_search_module,
        "_select_precheck_lookahead_candidate_entries",
        lambda *_args, **_kwargs: [
            {
                "candidate": (1, 1, 1),
                "selection_reason": "head",
                "wave_slot_index": 0,
                "frontier_candidate_metrics": {},
            }
        ],
    )
    monkeypatch.setattr(
        outer_search_module,
        "_evaluate_pre_master_precheck_best_effort",
        lambda **_kwargs: {"triggered": False, "status": None, "proof_summary": {}},
    )

    def create_drifted_session(*_args, **_kwargs):
        return outer_search_module.ExactSearchSession(
            project_root=project_root,
            solve_mode="certified_exact",
            instances=[],
            facility_pools={},
            rules={"globals": {"grid": {"width": 2, "height": 1}}},
            artifact_hashes=exact_campaign_module.compute_exact_artifact_hashes(project_root),
            master_search_profile="test",
            core=SimpleNamespace(
                generic_io_requirements=generic_io_requirements,
                wireless_sink_generic_input_slots=1,
            ),
            core_build_seconds=0.0,
        )

    monkeypatch.setattr(
        outer_search_module,
        "create_exact_search_session",
        create_drifted_session,
    )

    with pytest.raises(RuntimeError, match="wireless sink slot snapshot changed"):
        run_outer_search(
            project_root=project_root,
            solve_mode="certified_exact",
            max_attempts=0,
            min_side=1,
            area_upper_bound=1,
            campaign_hours=1.0,
            resume_campaign=False,
        )
