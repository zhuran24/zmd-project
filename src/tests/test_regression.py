"""Regression tests（回归测试） for project artifacts and exact boundary contracts（严格边界契约）."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.io.delivery_manifest import delivery_manifest_output_path
from ortools.sat.python import cp_model

from src.models.master_model import (
    MasterPlacementModel,
    load_generic_io_requirements_artifact,
    load_project_data,
)
from src.search.benders_loop import (
    compute_exact_static_area_lower_bound,
    compute_mandatory_area_lower_bound,
)
from src.models.cut_manager import RUN_STATUS_INFEASIBLE, RUN_STATUS_UNKNOWN
from src.search.benders_loop import run_benders_for_ghost_rect
from src.search.campaign_telemetry import append_campaign_wave_summary, build_wave_summary
from src.search.exact_campaign import ExactCampaign
from src.search.exact_parallel_scheduler import ParallelWaveExecution, WorkerResult
import src.search.outer_search as outer_search_module
from src.search.outer_search import generate_candidate_sizes, run_outer_search


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_empty_frontier_project(project_root: Path) -> Path:
    _write_json(
        project_root / "rules" / "canonical_rules.json",
        {
            "globals": {"grid": {"width": 6, "height": 6}, "empty_rectangle": {"objective": "max_lex_area_min_side", "min_side_admissibility": 1}},
            "facility_templates": {
                "synthetic": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            },
        },
    )
    # 单个真实 pose 让 terminal CERTIFIED 场景能走通 blueprint 导出/反查校验链
    # (V73+ 的 manifest 校验会把 blueprint facility 反查回 facility_pools)。
    _write_json(
        project_root / "data" / "preprocessed" / "candidate_placements.json",
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
    _write_json(project_root / "data" / "preprocessed" / "mandatory_exact_instances.json", [])
    _write_json(project_root / "data" / "preprocessed" / "all_facility_instances.json", [])
    _write_json(
        project_root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )
    return project_root


def _build_truly_solvable_single_pose_project(
    project_root: Path,
    *,
    width: int,
    height: int,
) -> Path:
    """Build a genuinely-solvable certified_exact fixture.

    P1.2 ④b sink-replay 根治后, 任何 CERTIFIED 候选都必须在隔离 `python -I`
    子进程里被真·重放复现才会被 sink 接受。monkeypatch 出来的假 CERTIFIED 在
    子进程里看不到 → 被降级。所以「serial/parallel 都拿到真 CERTIFIED」这类覆盖
    必须建在真·可解的小工程上: 一个真实的 1x1 facility (operation_type="" 走通
    binding/routing) 锚在原点 (0,0) 当 mandatory blocker, 剩余空间的真·最优空矩形
    由真实求解器解出并复现, 假 status 顺势对齐到这个真值即可存活。
    """

    _write_json(
        project_root / "rules" / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": width, "height": height},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 1,
                },
            },
            "facility_templates": {
                "tiny_facility": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            },
        },
    )
    _write_json(
        project_root / "data" / "preprocessed" / "candidate_placements.json",
        {
            "facility_pools": {
                "tiny_facility": [
                    {
                        "pose_id": "tiny_corner",
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
    instances = [
        {
            "instance_id": "blocker",
            "facility_type": "tiny_facility",
            "operation_type": "",
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_modes": ["certified_exact"],
        }
    ]
    _write_json(
        project_root / "data" / "preprocessed" / "mandatory_exact_instances.json",
        instances,
    )
    _write_json(
        project_root / "data" / "preprocessed" / "all_facility_instances.json",
        instances,
    )
    _write_json(
        project_root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )
    return project_root


def test_parallel_configuration_doc_exists_and_is_linked_from_pipeline_spec() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    doc_text = (project_root / "docs" / "parallel_configuration.md").read_text(encoding="utf-8")
    spec_text = (project_root / "specs" / "11_pipeline_orchestration.md").read_text(encoding="utf-8")

    assert "48GB" in doc_text
    assert "parallel_processes" in doc_text
    assert "docs/parallel_configuration.md" in spec_text


def test_frontier_probe_doc_and_spec_exist_and_are_linked() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    doc_text = (project_root / "docs" / "frontier_probe_strategy.md").read_text(encoding="utf-8")
    spec_text = (project_root / "specs" / "11_pipeline_orchestration.md").read_text(encoding="utf-8")
    file_status = (project_root / "FILE_STATUS.md").read_text(encoding="utf-8")
    probe_spec = (project_root / "specs" / "21_frontier_probe_and_campaign_telemetry.md").read_text(encoding="utf-8")

    assert "--frontier-probe-mode" in doc_text
    assert "selection_reason = probe_head | objective_head | prune_head | anchor_head | prune_fill" in doc_text
    assert "docs/frontier_probe_strategy.md" in spec_text
    assert "specs/21_frontier_probe_and_campaign_telemetry.md" in file_status
    assert "status: CURRENT_CODE_ALIGNED" in probe_spec


def test_phase3_preprocess_context_artifacts_and_examples_exist() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    required = [
        project_root / "rules" / "preprocess_plan.json",
        project_root / "rules" / "preprocess_plan.schema.json",
        project_root / "data" / "solutions" / "current_preprocess_context.json",
        project_root / "data" / "solutions" / "preprocess_context_diff_report.json",
        project_root / "data" / "solutions" / "preprocess_context_diff_report.md",
        project_root / "data" / "examples" / "industrial_planner" / "minimal_canonical_blueprint.json",
        project_root / "data" / "examples" / "industrial_planner" / "minimal.industrial_planner.blueprint.json",
        project_root / "data" / "examples" / "industrial_planner" / "minimal.industrial_planner.compatibility_manifest.json",
    ]
    for path in required:
        assert path.exists(), f"missing Phase-3 artifact: {path.relative_to(project_root)}"
        assert path.stat().st_size > 0

def test_governance_docs_point_to_changelog() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    changelog = project_root / "CHANGELOG.md"
    project_lock = (project_root / "PROJECT_LOCK.md").read_text(encoding="utf-8")
    file_status = (project_root / "FILE_STATUS.md").read_text(encoding="utf-8")
    changelog_text = changelog.read_text(encoding="utf-8")

    assert changelog.exists()
    assert "CHANGELOG.md" in project_lock
    assert "CHANGELOG.md" in file_status
    assert "## 2026-" not in project_lock
    assert "## 2026-" not in file_status
    assert "[PROJECT_LOCK]" in changelog_text
    assert "[FILE_STATUS]" in changelog_text


def test_problem_statement_is_current_code_aligned_and_problem_scoped() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    problem_statement = (project_root / "specs" / "01_problem_statement.md").read_text(encoding="utf-8")
    file_status = (project_root / "FILE_STATUS.md").read_text(encoding="utf-8")

    assert "status: CURRENT_CODE_ALIGNED" in problem_statement
    assert "| `specs/01_problem_statement.md` | CURRENT_CODE_ALIGNED |" in file_status
    assert "\\max_{\\text{lex}} (\\text{area}, \\text{min\\_side})" in problem_statement
    assert "min_side" in problem_statement and "\\min(w, h) \\ge 6" in problem_statement
    assert "与外部存在连通路径" in problem_statement
    assert "完全被包围的合法空矩形依然是允许的" in problem_statement
    assert "EXACT_CP_SAT_WORKERS" not in problem_statement
    assert "resolved_cp_sat_worker_profile" not in problem_statement
    assert "parallel scheduler" not in problem_statement.lower()


def test_preprocessed_artifacts_exist_and_are_nonempty() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    data_dir = project_root / "data" / "preprocessed"
    expected = [
        "commodity_demands.json",
        "machine_counts.json",
        "port_budget.json",
        "candidate_placements.json",
        "all_facility_instances.json",
        "mandatory_exact_instances.json",
        "exploratory_optional_caps.json",
        "generic_io_requirements.json",
    ]
    for filename in expected:
        path = data_dir / filename
        assert path.exists(), f"missing artifact（缺失工件）: {filename}"
        assert path.stat().st_size > 0, f"empty artifact（空工件）: {filename}"



def test_frozen_counts_align_with_new_split() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    data_dir = project_root / "data" / "preprocessed"

    machine_counts = json.loads((data_dir / "machine_counts.json").read_text(encoding="utf-8"))
    assert sum(machine_counts.values()) == 219

    mandatory_exact = json.loads((data_dir / "mandatory_exact_instances.json").read_text(encoding="utf-8"))
    all_instances = json.loads((data_dir / "all_facility_instances.json").read_text(encoding="utf-8"))
    caps = json.loads((data_dir / "exploratory_optional_caps.json").read_text(encoding="utf-8"))
    placements = json.loads((data_dir / "candidate_placements.json").read_text(encoding="utf-8"))
    total_poses = sum(len(pool) for pool in placements["facility_pools"].values())

    assert len(mandatory_exact) == 266
    assert len(all_instances) == 326
    assert caps["power_pole"]["cap"] == 50
    assert caps["protocol_storage_box"]["cap"] == 10
    assert total_poses == 66403



def test_generic_io_requirements_are_generated_from_preprocess() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    payload = json.loads(
        (project_root / "data" / "preprocessed" / "generic_io_requirements.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["required_generic_outputs"] == {"source_ore": 18, "blue_iron_ore": 34}
    assert payload["required_generic_inputs"] == {"valley_battery": 1, "qiaoyu_capsule": 1}



def test_exact_static_area_lower_bound_excludes_power_pole_area_heuristic() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    exact_instances, _pools, rules = load_project_data(project_root, solve_mode="certified_exact")
    exploratory_instances, _pools2, _rules2 = load_project_data(project_root, solve_mode="exploratory")

    lower_bound = compute_mandatory_area_lower_bound(exact_instances, rules)
    manual = 0
    templates = rules["facility_templates"]
    for inst in exact_instances:
        dims = templates[inst["facility_type"]]["dimensions"]
        manual += int(dims["w"]) * int(dims["h"])
    assert lower_bound == manual

    # Adding exploratory optional instances must not change the exact-safe lower bound.
    assert compute_mandatory_area_lower_bound(exploratory_instances, rules) == manual


def test_exact_static_area_lower_bound_includes_protocol_storage_box_minimum_area_lower_bound() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    exact_instances, _pools, rules = load_project_data(project_root, solve_mode="certified_exact")
    generic_io_requirements = load_generic_io_requirements_artifact(project_root)

    mandatory_lower_bound = compute_mandatory_area_lower_bound(exact_instances, rules)
    exact_static_lower_bound = compute_exact_static_area_lower_bound(
        exact_instances,
        rules,
        generic_io_requirements,
    )

    assert mandatory_lower_bound == 3544
    assert exact_static_lower_bound == 3553


def test_exact_master_notes_keep_power_pole_area_lower_bound_disabled() -> None:
    model = MasterPlacementModel(
        instances=[],
        facility_pools={"power_pole": [], "protocol_storage_box": []},
        rules={
            "globals": {"grid": {"width": 2, "height": 2}, "empty_rectangle": {"objective": "max_lex_area_min_side", "min_side_admissibility": 1}},
            "facility_templates": {
                "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
                "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            },
        },
        solve_mode="certified_exact",
    )

    model.build()

    notes = model.build_stats["global_valid_inequalities"]["notes"]
    assert "No power-pole area lower bound is injected into certified exact mode." in notes


def test_exact_core_packaging_profile_uses_owner_transfer_snapshot_modes() -> None:
    core = MasterPlacementModel.build_exact_core(
        instances=[
            {
                "instance_id": "miner_001",
                "facility_type": "miner",
                "operation_type": "mining",
                "is_mandatory": True,
                "bound_type": "exact",
            }
        ],
        facility_pools={
            "miner": [
                {
                    "pose_id": "pose_left",
                    "anchor": {"x": 0, "y": 0},
                    "occupied_cells": [[0, 0]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                }
            ]
        },
        rules={
            "globals": {"grid": {"width": 2, "height": 1}, "empty_rectangle": {"objective": "max_lex_area_min_side", "min_side_admissibility": 1}},
            "facility_templates": {
                "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            },
        },
        skip_power_coverage=True,
    )

    profile = core.build_stats["exact_core_packaging_profile"]
    assert profile["proto_storage_mode"] == "owned_proto"
    assert profile["source_instances_snapshot_mode"] == "owned_model_reference"
    assert profile["facility_pools_snapshot_mode"] == "owned_model_reference"
    assert profile["rules_snapshot_mode"] == "owned_model_reference"
    assert profile["generic_io_requirements_snapshot_mode"] == "owned_model_reference"
    assert profile["build_stats_snapshot_mode"] == "owned_model_reference"
    assert profile["mandatory_groups_snapshot_mode"] == "owned_model_reference"
    assert profile["group_id_by_instance_snapshot_mode"] == "copied_dict"
    assert profile["coordinate_binding_snapshot_mode"] == "fresh_export"
    assert profile["proto_capture_seconds"] >= 0.0
    assert profile["coordinate_binding_export_seconds"] >= 0.0
    assert profile["packaging_seconds"] >= 0.0


def test_exact_optional_cardinality_bounds_align_with_preprocessed_artifacts() -> None:
    # fresh-state stats==0 的 assertion 依赖 cache 清空. conftest autouse
    # fixture 已统一清 6 个 module-level cache (b4c2a03 → conftest centralized).
    project_root = Path(__file__).resolve().parent.parent.parent
    exact_instances, pools, rules = load_project_data(project_root, solve_mode="certified_exact")
    generic_io_requirements = load_generic_io_requirements_artifact(project_root)

    model = MasterPlacementModel(
        exact_instances,
        pools,
        rules,
        solve_mode="certified_exact",
        generic_io_requirements=generic_io_requirements,
    )
    model.build()

    bounds = model.build_stats["global_valid_inequalities"]["optional_cardinality_bounds"]
    guidance = model.build_stats["search_guidance"]
    signature_buckets = model.build_stats["signature_buckets"]["mandatory_groups"]
    family_stats = model.build_stats["global_valid_inequalities"]["power_capacity_families"]
    power_coverage = model.build_stats["power_coverage"]
    exact_core_profile = model.build_stats["exact_core_profile"]
    precompute = model.build_stats["exact_precompute_profile"]
    assert bounds["protocol_storage_box"]["required_generic_input_slots"] == 2
    assert bounds["protocol_storage_box"]["mode"] == "required_lower_bound"
    assert bounds["protocol_storage_box"]["lower"] == 1
    assert bounds["protocol_storage_box"]["upper"] is None
    assert bounds["protocol_storage_box"]["slot_pool_upper_bound"] > 0
    assert bounds["power_pole"]["mandatory_powered_nonpole"] == 219
    assert bounds["power_pole"]["optional_powered_templates"] == ["protocol_storage_box"]
    assert model.build_stats["exact_required_optionals"] == {}
    assert model.build_stats["exact_optional_lower_bounds"] == {"protocol_storage_box": 1}
    assert guidance["profile"] == "exact_coordinate_guided_branching_v4"
    assert guidance["required_optional_templates"] == []
    assert guidance["required_optional_signature_counts"] == {}
    assert guidance["required_optional_signature_count_literals"] == 0
    assert guidance["required_optional_literals"] == {}
    assert guidance["residual_optional_literals"]["protocol_storage_box"] > 0
    assert guidance["power_pole_family_count_literals"] == family_stats["family_count"]
    assert len(guidance["power_pole_family_order"]) == family_stats["family_count"]
    assert guidance["residual_optional_family_guided"] is True
    assert model.build_stats["master_representation"] == "coordinate_exact_v2"
    assert model.build_stats["master_pose_bool_literals"] == 0
    assert model.build_stats["master_domain_encoding"] == "mode_rect_factorized_v1"
    assert model.build_stats["master_domain_table_rows"] == 0
    assert model.build_stats["master_mode_rect_domains"]["required_optionals"] == {}
    assert "protocol_storage_box" in model.build_stats["master_mode_rect_domains"]["residual_optionals"]
    assert model.build_stats["master_slot_counts"]["required_optionals"] == {}
    assert model.build_stats["master_slot_counts"]["residual_optionals"]["protocol_storage_box"] > 0
    assert model.build_stats["power_pole_shell_lookup_pairs"]["pair_count"] > 0
    assert power_coverage["representation"] == "coordinate_geometric"
    assert power_coverage["encoding"] == "geometric_element_witness_v1"
    assert power_coverage["cover_literals"] == 0
    assert power_coverage["witness_indices"] == power_coverage["powered_slots"]
    assert power_coverage["powered_slots"] >= 220
    assert power_coverage["element_constraints"] == power_coverage["powered_slots"] * 3
    assert 2 <= signature_buckets["group::manufacturing_3x3::crusher_blue_iron::1"]["bucket_count"] <= 4
    assert 2 <= signature_buckets["group::manufacturing_5x5::planter_sandleaf::10"]["bucket_count"] <= 4
    assert 2 <= signature_buckets["group::manufacturing_6x4::grinder_dense_blue_iron::14"]["bucket_count"] <= 4
    assert family_stats["applied"] is True
    assert family_stats["family_count"] < family_stats["raw_pole_count"]
    assert family_stats["coefficient_source"] == "exact_compact_rect_cpsat_v14"
    assert family_stats["shell_pair_count"] < family_stats["raw_pole_count"]
    assert family_stats["compact_signature_class_count"] > 0
    assert precompute["power_capacity_shell_pairs"] == family_stats["shell_pair_count"]
    assert precompute["power_capacity_signature_classes"] > 0
    assert precompute["power_capacity_compact_signature_classes"] > 0
    assert precompute["power_capacity_signature_classes"] < precompute["power_capacity_shell_pair_evaluations"]
    assert (
        precompute["power_capacity_signature_class_evaluations"]
        < precompute["power_capacity_shell_pair_evaluations"]
        < precompute["power_capacity_raw_pole_evaluations"]
    )
    assert (
        precompute["power_capacity_compact_signature_evaluations"]
        <= precompute["power_capacity_signature_class_evaluations"]
    )
    assert precompute["power_capacity_compact_rect_cpsat_evaluations"] > 0
    assert (
        precompute["power_capacity_normalized_rect_signature_count"]
        < precompute["power_capacity_compact_signature_classes"]
    )
    assert precompute["power_capacity_compact_rect_cpsat_selected_cases"] == (
        precompute["power_capacity_compact_signature_evaluations"]
    )
    assert precompute["power_capacity_normalized_rect_cache_misses"] == (
        precompute["power_capacity_compact_rect_cpsat_evaluations"]
    )
    assert precompute["power_capacity_normalized_rect_cache_hits"] > 0
    assert (
        precompute["power_capacity_signature_classes"]
        == precompute["power_capacity_compact_signature_classes"]
    )
    assert (
        precompute["power_capacity_signature_class_evaluations"]
        == precompute["power_capacity_compact_signature_evaluations"]
    )
    assert precompute["power_capacity_legacy_signature_materializations"] == 0
    assert precompute["power_capacity_supported_by_pole_materializations"] == 0
    assert precompute["power_capacity_compact_rect_cpsat_rect_dp_fallbacks"] == 0
    assert precompute["power_capacity_rect_dp_evaluations"] == 0
    assert precompute["power_capacity_rect_dp_cache_hits"] == 0
    assert precompute["power_capacity_rect_dp_cache_misses"] == 0
    assert precompute["power_capacity_rect_dp_state_merges"] == 0
    assert precompute["power_capacity_rect_dp_peak_line_states"] == 0
    assert precompute["power_capacity_rect_dp_peak_pos_states"] == 0
    assert precompute["power_capacity_rect_dp_compiled_signatures"] == 0
    assert precompute["power_capacity_rect_dp_compiled_start_options"] == 0
    assert precompute["power_capacity_rect_dp_deduped_start_options"] == 0
    assert precompute["power_capacity_rect_dp_compiled_line_subsets"] == 0
    assert precompute["power_capacity_rect_dp_peak_line_subset_options"] == 0
    assert precompute["power_capacity_rect_dp_v3_fallbacks"] == 0
    assert precompute["power_capacity_m6x4_mixed_cpsat_evaluations"] > 0
    assert precompute["power_capacity_m6x4_mixed_cpsat_selected_cases"] > 0
    assert precompute["power_capacity_m6x4_mixed_cpsat_v3_fallbacks"] == 0
    assert precompute["power_capacity_uniform_3x3_cpsat_evaluations"] > 0
    assert precompute["power_capacity_uniform_3x3_cpsat_selected_cases"] > 0
    assert precompute["power_capacity_uniform_3x3_cpsat_v3_fallbacks"] == 0
    assert precompute["power_capacity_bitset_oracle_evaluations"] == 0
    assert precompute["power_capacity_bitset_fallbacks"] == 0
    assert precompute["power_capacity_cpsat_fallbacks"] == 0
    assert precompute["power_capacity_oracle"] == "compact_rect_cpsat_v2"
    assert precompute["power_capacity_shell_pair_evaluations"] < precompute["power_capacity_raw_pole_evaluations"]
    assert precompute["signature_bucket_cache_hits"] > 0
    assert precompute["signature_bucket_distinct_keys"] > 0
    assert precompute["geometry_cache_templates"] > 0
    rectangle_variants = {
        tpl: {
            (variant.width, variant.height)
            for variant in model._ensure_local_rectangle_variants(tpl).values()
            if variant is not None
        }
        for tpl in ("manufacturing_3x3", "manufacturing_5x5", "manufacturing_6x4", "protocol_storage_box")
    }
    assert rectangle_variants["manufacturing_3x3"] == {(3, 3)}
    assert rectangle_variants["manufacturing_5x5"] == {(5, 5)}
    assert rectangle_variants["manufacturing_6x4"] == {(6, 4), (4, 6)}
    assert rectangle_variants["protocol_storage_box"] == {(3, 3)}
    assert model.build_stats["global_valid_inequalities"]["fixed_required_optional_demands"] == {}
    assert model.build_stats["global_valid_inequalities"]["lower_bound_optional_powered_demands"] == {
        "protocol_storage_box": 1
    }
    assert exact_core_profile["proto_vars"] < 64462
    assert exact_core_profile["proto_constraints"] < 280631


@pytest.mark.xfail(
    reason=(
        "PREMISE-OBSOLETE under P1.2 ④b sink-replay. 本测试断言 resume 不重调 solver "
        "(calls == []), 但 ④b 故意在 resume 时用隔离子进程重验候选强状态。正确的 ④b 契约 "
        "(resume 先 drop 再经 fresh replay 重建) 已由 test_exact_contract::"
        "test_campaign_resume_requires_fresh_replay_for_proof_bearing_candidates 与 "
        "test_exact_campaign_state_soundness::"
        "test_resume_drops_certified_statuses_before_terminal_certified_reuse 覆盖。"
        "待 owner 拍: remove-as-superseded vs rewrite。见 task #13 / cc_memory。"
    ),
)
def test_campaign_resume_reconstructs_frontier_without_reinvoking_solver(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_empty_frontier_project(tmp_path / "resume_frontier")
    calls: list[tuple[int, int]] = []

    def _is_feasible(ghost_w: int, ghost_h: int) -> bool:
        return (ghost_w <= 4 and ghost_h <= 3) or (ghost_w <= 6 and ghost_h <= 2)

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
            return "CERTIFIED", {
                "ghost_pick": {
                    "pose_idx": 0,
                    "pose_id": "synthetic_pose_0",
                    "anchor": {"x": 0, "y": 0},
                    "facility_type": "synthetic",
                }
            }
        return "INFEASIBLE", None

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
        max_attempts=64,
        min_side=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )

    assert status == "CERTIFIED"
    assert result is not None
    first_run_calls = list(calls)
    calls.clear()

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
        resume_campaign=True,
    )

    assert status == "CERTIFIED"
    assert result is not None
    assert first_run_calls
    assert calls == []


def test_frontier_resume_reconstructs_same_next_selected_candidate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_empty_frontier_project(tmp_path / "resume_frontier_next_pick")
    calls: list[tuple[int, int]] = []

    def fake_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        calls.append((ghost_w, ghost_h))
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": "INFEASIBLE",
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        return "INFEASIBLE", None

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
        max_attempts=1,
        min_side=1,
        area_upper_bound=9,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )

    assert status == "UNKNOWN"
    assert result is None
    assert calls == [(6, 1)]

    resumed_campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)
    candidates = generate_candidate_sizes(
        max_w=6,
        max_h=6,
        min_side=1,
        area_upper_bound=9,
    )
    frontier_state = outer_search_module._compute_exact_frontier_state(
        candidates,
        resumed_campaign,
        grid_w=6,
        grid_h=6,
    )
    expected_next = frontier_state["selected_candidate"]
    assert expected_next is not None

    calls.clear()
    status, result = run_outer_search(
        project_root=project_root,
        solve_mode="certified_exact",
        max_attempts=1,
        min_side=1,
        area_upper_bound=9,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=True,
    )

    assert status == "UNKNOWN"
    assert result is None
    assert calls == [(expected_next[1], expected_next[2])]


def test_parallel_outer_search_matches_serial_on_controlled_small_frontier(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # P1.2 ④b sink-replay 根治后, monkeypatch 出来的假 CERTIFIED 在隔离子进程
    # 重放里看不到 → 被降级。所以「serial 与 parallel 收敛到同一 CERTIFIED」这条
    # 覆盖必须建在真·可解的小工程上: 2x1 grid + 锚原点的 1x1 blocker, 真·最优空
    # 矩形是 1x1@(1,0)。两条路径的假 status 都对齐到这个真值, 于是隔离重放复现
    # 出同一 CERTIFIED 而存活。
    serial_root = _build_truly_solvable_single_pose_project(
        tmp_path / "parallel_vs_serial_serial", width=2, height=1
    )
    parallel_root = _build_truly_solvable_single_pose_project(
        tmp_path / "parallel_vs_serial_parallel", width=2, height=1
    )

    def _real_certified_solution() -> dict:
        return {
            "blocker": {"facility_type": "tiny_facility", "pose_idx": 0},
            "ghost_pick": {
                "pose_idx": 1,
                "pose_id": "ghost_anchor::1,0",
                "anchor": {"x": 1, "y": 0},
                "facility_type": "ghost_rect",
            },
        }

    def fake_serial_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        del session, kwargs
        fake_serial_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": "CERTIFIED" if (ghost_w, ghost_h) == (1, 1) else "INFEASIBLE",
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        if (ghost_w, ghost_h) == (1, 1):
            return "CERTIFIED", _real_certified_solution()
        return "INFEASIBLE", None

    fake_serial_run_benders_for_ghost_rect.last_run_metadata = {
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }

    monkeypatch.setattr(
        outer_search_module.ExactSearchSession,
        "create",
        staticmethod(lambda project_root, solve_mode="certified_exact": object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        fake_serial_run_benders_for_ghost_rect,
    )

    serial_status, serial_result = run_outer_search(
        project_root=serial_root,
        solve_mode="certified_exact",
        max_attempts=64,
        min_side=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=1,
    )

    class _DummyParallelWorkerPool:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def close(self) -> None:
            return None

    def fake_parallel_wave(*, pool, tasks):
        assert isinstance(pool, _DummyParallelWorkerPool)
        results = []
        for task in reversed(tasks):
            if (int(task.candidate[1]), int(task.candidate[2])) == (1, 1):
                results.append(
                    WorkerResult(
                        dispatch_seq=task.dispatch_seq,
                        attempt_index=task.attempt_index,
                        candidate=task.candidate,
                        status="CERTIFIED",
                        solution=_real_certified_solution(),
                        proof_summary={"mode": "certified_exact", "master_status": "CERTIFIED"},
                        exact_safe_cuts=[],
                        loaded_exact_safe_cut_count=0,
                        generated_exact_safe_cut_count=0,
                        worker_wall_seconds=0.01,
                        peak_rss_bytes=1,
                        error=None,
                    )
                )
            else:
                results.append(
                    WorkerResult(
                        dispatch_seq=task.dispatch_seq,
                        attempt_index=task.attempt_index,
                        candidate=task.candidate,
                        status="INFEASIBLE",
                        solution=None,
                        proof_summary={"mode": "certified_exact", "master_status": "INFEASIBLE"},
                        exact_safe_cuts=[],
                        loaded_exact_safe_cut_count=0,
                        generated_exact_safe_cut_count=0,
                        worker_wall_seconds=0.01,
                        peak_rss_bytes=1,
                        error=None,
                    )
                )
        return ParallelWaveExecution(
            completed=True,
            failure_reason=None,
            results=tuple(results),
            dispatched_candidate_keys=tuple(f"{int(task.candidate[1])}x{int(task.candidate[2])}" for task in tasks),
            elapsed_seconds=0.02,
            peak_rss_bytes_external_total=2,
            peak_rss_bytes_internal_max_single_process=1,
        )

    monkeypatch.setattr(outer_search_module, "ExactParallelWorkerPool", _DummyParallelWorkerPool)
    monkeypatch.setattr(outer_search_module, "run_parallel_exact_campaign_wave", fake_parallel_wave)

    parallel_status, parallel_result = run_outer_search(
        project_root=parallel_root,
        solve_mode="certified_exact",
        max_attempts=64,
        min_side=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=2,
    )

    assert serial_status == parallel_status == "CERTIFIED"
    assert serial_result is not None and parallel_result is not None
    assert serial_result["ghost_rect"] == parallel_result["ghost_rect"] == {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0}


def test_serial_unknown_head_fails_closed_without_certified_public_surface(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # Split from the obsolete serial+parallel resume test below. The old "strong
    # CERTIFIED survives resume" premise is invalid after P1.2 ④b, but this
    # serial fail-closed contract remains live: certified mode must stop at the
    # first UNKNOWN candidate, must not keep probing toward a best-effort
    # CERTIFIED, and must not publish any certified delivery surface.
    serial_root = _build_empty_frontier_project(tmp_path / "serial_unknown_no_publish")

    def fake_serial_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        del session, kwargs
        status = "CERTIFIED" if (ghost_w, ghost_h) == (6, 4) else "UNKNOWN"
        fake_serial_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": status,
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        if status == "CERTIFIED":
            return "CERTIFIED", {
                "big_pick": {
                    "pose_idx": 0,
                    "pose_id": "synthetic_pose_0",
                    "anchor": {"x": 0, "y": 0},
                    "facility_type": "synthetic",
                }
            }
        return "UNKNOWN", None

    fake_serial_run_benders_for_ghost_rect.last_run_metadata = {
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }

    monkeypatch.setattr(
        outer_search_module.ExactSearchSession,
        "create",
        staticmethod(lambda project_root, solve_mode="certified_exact": object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        fake_serial_run_benders_for_ghost_rect,
    )

    serial_status, serial_result = run_outer_search(
        project_root=serial_root,
        solve_mode="certified_exact",
        max_attempts=64,
        min_side=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=1,
    )

    serial_campaign = ExactCampaign.load_or_create(serial_root, campaign_hours=1.0, resume=True)
    serial_manifest = json.loads(
        delivery_manifest_output_path(serial_root).read_text(encoding="utf-8")
    )

    assert serial_status == "UNKNOWN"
    assert serial_result is None
    assert serial_campaign.state["last_stop_reason"]["reason"] == "candidate_returned_unknown"
    assert all(
        record["status"] != "CERTIFIED"
        for record in serial_campaign.state["candidates"].values()
    )
    assert serial_campaign.best_certified_result() is None
    assert serial_campaign.state["final_status"] == "UNKNOWN"
    assert serial_manifest["campaign"]["final_status"] == "UNKNOWN"
    assert serial_manifest["best_certified_result"] is None
    assert serial_manifest["artifacts"]["final_solution"]["exists"] is False
    assert serial_manifest["artifacts"]["optimal_blueprint"]["exists"] is False


def test_parallel_replayable_certified_record_without_terminal_frontier_does_not_publish(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # Parallel waves may persist a replayable CERTIFIED candidate record before
    # the frontier is terminal. That checkpoint-local record must not leak into
    # the public certified surface while another same-wave candidate is UNKNOWN.
    parallel_root = _build_truly_solvable_single_pose_project(
        tmp_path / "parallel_replayable_certified_no_publish", width=2, height=2
    )

    def _real_certified_solution_for(ghost_w: int, ghost_h: int) -> dict:
        if (ghost_w, ghost_h) == (2, 1):
            anchor = {"x": 0, "y": 1}
        elif (ghost_w, ghost_h) == (1, 2):
            anchor = {"x": 1, "y": 0}
        else:
            raise AssertionError(f"unexpected certified candidate: {(ghost_w, ghost_h)}")
        return {
            "blocker": {"facility_type": "tiny_facility", "pose_idx": 0},
            "ghost_pick": {
                "pose_idx": 1,
                "pose_id": f"ghost_anchor::{anchor['x']},{anchor['y']}",
                "anchor": anchor,
                "facility_type": "ghost_rect",
            },
        }

    class _DummyParallelWorkerPool:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def close(self) -> None:
            return None

    wave_phase = {"certified_emitted": False, "certified_key": None}

    def fake_parallel_wave(*, pool, tasks):
        assert isinstance(pool, _DummyParallelWorkerPool)
        true_certified_candidates = {(2, 1), (1, 2)}
        results = []
        for task in reversed(tasks):
            candidate_wh = (int(task.candidate[1]), int(task.candidate[2]))
            if (
                candidate_wh in true_certified_candidates
                and not wave_phase["certified_emitted"]
            ):
                status = "CERTIFIED"
                solution = _real_certified_solution_for(*candidate_wh)
                wave_phase["certified_emitted"] = True
                wave_phase["certified_key"] = task.candidate_key
            else:
                status = "UNKNOWN"
                solution = None
            results.append(
                WorkerResult(
                    dispatch_seq=task.dispatch_seq,
                    attempt_index=task.attempt_index,
                    candidate=task.candidate,
                    status=status,
                    solution=solution,
                    proof_summary={"mode": "certified_exact", "master_status": status},
                    exact_safe_cuts=[],
                    loaded_exact_safe_cut_count=0,
                    generated_exact_safe_cut_count=0,
                    worker_wall_seconds=0.01,
                    peak_rss_bytes=1,
                    error=None,
                )
            )
        return ParallelWaveExecution(
            completed=True,
            failure_reason=None,
            results=tuple(results),
            dispatched_candidate_keys=tuple(str(task.candidate_key) for task in tasks),
            elapsed_seconds=0.02,
            peak_rss_bytes_external_total=2,
            peak_rss_bytes_internal_max_single_process=1,
        )

    monkeypatch.setattr(
        outer_search_module.ExactSearchSession,
        "create",
        staticmethod(lambda project_root, solve_mode="certified_exact": object()),
    )
    monkeypatch.setattr(outer_search_module, "ExactParallelWorkerPool", _DummyParallelWorkerPool)
    monkeypatch.setattr(outer_search_module, "run_parallel_exact_campaign_wave", fake_parallel_wave)

    parallel_status, parallel_result = run_outer_search(
        project_root=parallel_root,
        solve_mode="certified_exact",
        max_attempts=64,
        min_side=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=2,
    )

    checkpoint_state = json.loads(
        (parallel_root / "data" / "checkpoints" / "exact_campaign_state.json").read_text(
            encoding="utf-8"
        )
    )
    parallel_manifest = json.loads(
        delivery_manifest_output_path(parallel_root).read_text(encoding="utf-8")
    )

    certified_key = wave_phase["certified_key"]
    assert certified_key is not None
    assert parallel_status == "UNKNOWN"
    assert parallel_result is None
    assert checkpoint_state["candidates"][certified_key]["status"] == "CERTIFIED"
    assert checkpoint_state["final_result"] is None
    assert checkpoint_state["final_status"] == "UNKNOWN"
    assert parallel_manifest["campaign"]["final_status"] == "UNKNOWN"
    assert parallel_manifest["best_certified_result"] is None
    assert parallel_manifest["artifacts"]["final_solution"]["exists"] is False
    assert parallel_manifest["artifacts"]["optimal_blueprint"]["exists"] is False


@pytest.mark.xfail(
    reason=(
        "PREMISE-OBSOLETE under P1.2 ④b sink-replay. 并行半边断言 CERTIFIED 候选能熬过一次 "
        "resume-load, 但 ④b 的 resume 把落盘强状态 sanitize 成 UNKNOWN "
        "(_sanitize_resume_state_for_untrusted_candidate_evidence)。该 sanitize 契约已由 "
        "test_exact_campaign_state_soundness::test_resume_drops_certified_statuses_before_"
        "terminal_certified_reuse 覆盖。仍有效的 serial UNKNOWN fail-closed / no-publish "
        "断言已拆到 "
        "test_serial_unknown_head_fails_closed_without_certified_public_surface。另: 真·fixture 重写时还暴露一个 ④b 健壮性疑点 — "
        "隔离 replay 单跑能复现 CERTIFIED 但在 pytest harness 下偶发降级 (SAFE: 只降 UNKNOWN、"
        "绝不假 CERTIFIED)。待 owner 拍: remove-as-superseded vs rewrite + 根因那个 harness "
        "flaky。见 task #13 / cc_memory。"
    ),
)
def test_parallel_and_serial_preserve_same_best_certified_result(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # certified 模式下串行推进撞到第一个 UNKNOWN 头就 fail-closed 退出 (不做
    # best-effort incumbent 积累); 并行 wave 则可能在同一波里乱序拿到 CERTIFIED
    # 与 UNKNOWN。本测试守护同一契约在两条路径的表达:
    # 串行段: 头部 (6,6) UNKNOWN 即停 — mock 世界里 (6,4) 本可 CERTIFIED, 若实现
    #   回归为 best-effort 继续推进就会解出它, 被「无 CERTIFIED 记录」断言抓红;
    # 并行段: 同一波乱序拿到 CERTIFIED 时记录保留在 checkpoint (resume 可用);
    # 两条路径的公开 certified 面 (best_certified_result / manifest / 导出工件)
    #   在非 terminal 状态下都必须为空。
    serial_root = _build_empty_frontier_project(tmp_path / "parallel_best_serial")
    parallel_root = _build_empty_frontier_project(tmp_path / "parallel_best_parallel")

    def fake_serial_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        del session, kwargs
        status = "CERTIFIED" if (ghost_w, ghost_h) == (6, 4) else "UNKNOWN"
        fake_serial_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": status,
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        if status == "CERTIFIED":
            return "CERTIFIED", {
                "big_pick": {
                    "pose_idx": 0,
                    "pose_id": "synthetic_pose_0",
                    "anchor": {"x": 0, "y": 0},
                    "facility_type": "synthetic",
                }
            }
        return "UNKNOWN", None

    fake_serial_run_benders_for_ghost_rect.last_run_metadata = {
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }

    monkeypatch.setattr(
        outer_search_module.ExactSearchSession,
        "create",
        staticmethod(lambda project_root, solve_mode="certified_exact": object()),
    )
    monkeypatch.setattr(
        outer_search_module,
        "run_benders_for_ghost_rect",
        fake_serial_run_benders_for_ghost_rect,
    )

    serial_status, serial_result = run_outer_search(
        project_root=serial_root,
        solve_mode="certified_exact",
        max_attempts=64,
        min_side=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=1,
    )

    class _DummyParallelWorkerPool:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def close(self) -> None:
            return None

    wave_phase = {"certified_emitted": False, "certified_key": None}

    def fake_parallel_wave(*, pool, tasks):
        assert isinstance(pool, _DummyParallelWorkerPool)
        # 权威全域的支配 frontier 从单头 (6,6) 起步: 单头波判 INFEASIBLE 削角,
        # 裂成 ≥2 头的那一波乱序回报一个 CERTIFIED + 其余 UNKNOWN, 之后保持
        # UNKNOWN, 让 run 以非 terminal UNKNOWN 退出但保留 CERTIFIED 记录。
        # V82 有向域下波的具体形状会漂, 所以 certified 目标取该波第一个候选
        # 而不锚定 (6,4) 这类具体尺寸。
        certified_target = None
        if len(tasks) >= 2 and not wave_phase["certified_emitted"]:
            certified_target = (int(tasks[0].candidate[1]), int(tasks[0].candidate[2]))
        results = []
        for task in reversed(tasks):
            candidate_wh = (int(task.candidate[1]), int(task.candidate[2]))
            if len(tasks) < 2 and not wave_phase["certified_emitted"]:
                status = "INFEASIBLE"
                solution = None
            elif candidate_wh == certified_target:
                status = "CERTIFIED"
                solution = {
                    "big_pick": {
                        "pose_idx": 0,
                        "pose_id": "synthetic_pose_0",
                        "anchor": {"x": 0, "y": 0},
                        "facility_type": "synthetic",
                    }
                }
            else:
                status = "UNKNOWN"
                solution = None
            results.append(
                WorkerResult(
                    dispatch_seq=task.dispatch_seq,
                    attempt_index=task.attempt_index,
                    candidate=task.candidate,
                    status=status,
                    solution=solution,
                    proof_summary={"mode": "certified_exact", "master_status": status},
                    exact_safe_cuts=[],
                    loaded_exact_safe_cut_count=0,
                    generated_exact_safe_cut_count=0,
                    worker_wall_seconds=0.01,
                    peak_rss_bytes=1,
                    error=None,
                )
            )
        for result in results:
            if result.status == "CERTIFIED":
                wave_phase["certified_emitted"] = True
                wave_phase["certified_key"] = (
                    f"{int(result.candidate[1])}x{int(result.candidate[2])}"
                )
        return ParallelWaveExecution(
            completed=True,
            failure_reason=None,
            results=tuple(results),
            dispatched_candidate_keys=tuple(f"{int(task.candidate[1])}x{int(task.candidate[2])}" for task in tasks),
            elapsed_seconds=0.02,
            peak_rss_bytes_external_total=2,
            peak_rss_bytes_internal_max_single_process=1,
        )

    monkeypatch.setattr(outer_search_module, "ExactParallelWorkerPool", _DummyParallelWorkerPool)
    monkeypatch.setattr(outer_search_module, "run_parallel_exact_campaign_wave", fake_parallel_wave)

    parallel_status, parallel_result = run_outer_search(
        project_root=parallel_root,
        solve_mode="certified_exact",
        max_attempts=64,
        min_side=1,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=2,
    )

    serial_campaign = ExactCampaign.load_or_create(serial_root, campaign_hours=1.0, resume=True)
    parallel_campaign = ExactCampaign.load_or_create(parallel_root, campaign_hours=1.0, resume=True)
    serial_manifest = json.loads(
        delivery_manifest_output_path(serial_root).read_text(encoding="utf-8")
    )
    parallel_manifest = json.loads(
        delivery_manifest_output_path(parallel_root).read_text(encoding="utf-8")
    )

    assert serial_status == parallel_status == "UNKNOWN"
    assert serial_result is None and parallel_result is None
    # 串行: 第一个 UNKNOWN 头 fail-closed 退出, certified 模式不做 best-effort 积累。
    # mock 世界里 (6,4) 本可 CERTIFIED — best-effort 回归会解出它并把下面的断言变红。
    assert serial_campaign.state["last_stop_reason"]["reason"] == "candidate_returned_unknown"
    assert all(
        record["status"] != "CERTIFIED"
        for record in serial_campaign.state["candidates"].values()
    )
    # 并行: 同一波里乱序拿到的 CERTIFIED 记录保留在 checkpoint (resume 可用)。
    certified_key = wave_phase["certified_key"]
    assert certified_key is not None
    assert parallel_campaign.state["candidates"][certified_key]["status"] == "CERTIFIED"
    assert (
        parallel_campaign.state["candidates"][certified_key]["solution"]["big_pick"]["pose_id"]
        == "synthetic_pose_0"
    )
    # 两条路径的公开 certified 面一致为空: 非 terminal 不发布 (V75/V76 契约)。
    assert serial_campaign.best_certified_result() is None
    assert parallel_campaign.best_certified_result() is None
    assert serial_campaign.state["final_status"] == "UNKNOWN"
    assert parallel_campaign.state["final_status"] == "UNKNOWN"
    assert serial_manifest["campaign"]["final_status"] == "UNKNOWN"
    assert parallel_manifest["campaign"]["final_status"] == "UNKNOWN"
    assert serial_manifest["best_certified_result"] is None
    assert parallel_manifest["best_certified_result"] is None
    assert serial_manifest["artifacts"]["final_solution"]["exists"] is False
    assert parallel_manifest["artifacts"]["optimal_blueprint"]["exists"] is False


def test_exhausted_search_without_terminal_infeasible_evidence_fails_closed_unproven(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = _build_empty_frontier_project(tmp_path / "manifest_infeasible_terminal")

    # min_side=6 在 6x6 grid 的权威全域里只留 (6,6) 一个候选; mock 把它判
    # INFEASIBLE。但 P1.2 ④b sink-replay 根治后, monkeypatch 出来的假
    # INFEASIBLE 在隔离 `python -I` 子进程重放里看不到 → 该强状态被降级,
    # (6,6) 永不被 prune 出 potential_domain, 于是搜索反复重试同一候选直到撞上
    # max_attempts → 以 RUN_STATUS_UNKNOWN / max_attempts_exhausted 退出。
    # 不论退出口径如何, manifest 都不得伪造任何 certified 结果 (本测试的灵魂)。
    def fake_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": "INFEASIBLE",
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        return "INFEASIBLE", None

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
        min_side=6,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=1,
    )

    manifest_payload = json.loads(
        delivery_manifest_output_path(project_root).read_text(encoding="utf-8")
    )

    assert status == "UNKNOWN"
    assert result is None
    assert manifest_payload["campaign"]["final_status"] == "UNKNOWN"
    assert manifest_payload["campaign"]["last_stop_reason"]["reason"] == (
        "max_attempts_exhausted"
    )
    # 灵魂断言: 不论退出口径, 公开 certified 面必须为空、不得伪造交付工件。
    assert manifest_payload["best_certified_result"] is None
    assert manifest_payload["artifacts"]["final_solution"]["exists"] is False
    assert manifest_payload["artifacts"]["optimal_blueprint"]["exists"] is False


def test_aspect_ratio_sliced_search_cannot_claim_terminal_certified(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # V79: max_aspect_ratio 会从候选域里滤掉高长宽比候选 (它们从未被反驳), 所以
    # 带 aspect 过滤的搜索即使耗尽剩余域也不得宣称 terminal full-frontier
    # CERTIFIED。P1.2 ④b sink-replay 根治后, monkeypatch 出来的假 CERTIFIED /
    # INFEASIBLE 在隔离子进程重放里都看不到 → 全被降级, 候选既不被 certify 也不
    # 被 prune, 搜索撞 max_attempts 后以 RUN_STATUS_UNKNOWN / max_attempts_exhausted
    # 退出。无论退出口径如何, 关键不变量不变: 绝不得伪造 terminal CERTIFIED —
    # best_certified_result 为空、final_status 非 CERTIFIED、不落 final_solution。
    project_root = _build_empty_frontier_project(tmp_path / "aspect_sliced_search")

    def fake_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        feasible = (ghost_w <= 4 and ghost_h <= 3) or (ghost_w <= 6 and ghost_h <= 2)
        fake_run_benders_for_ghost_rect.last_run_metadata = {
            "proof_summary": {
                "mode": "certified_exact",
                "master_status": "FEASIBLE" if feasible else "INFEASIBLE",
            },
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        if feasible:
            return "CERTIFIED", {
                "ghost_pick": {
                    "pose_idx": 0,
                    "pose_id": "synthetic_pose_0",
                    "anchor": {"x": 0, "y": 0},
                    "facility_type": "synthetic",
                }
            }
        return "INFEASIBLE", None

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
        max_attempts=64,
        min_side=1,
        max_aspect_ratio=3.0,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
    )

    assert status == "UNKNOWN"
    assert result is None
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)
    # 灵魂断言: 绝不得伪造 terminal CERTIFIED — 这几条是本测试的存在理由, 原样保留。
    assert campaign.best_certified_result() is None
    assert campaign.state["final_status"] != "CERTIFIED"
    assert not (project_root / "data" / "solutions" / "final_solution.json").exists()


def test_min_side_exceeding_grid_fails_closed_with_value_error(tmp_path: Path) -> None:
    # V75 起 min_side 超出 grid 的退化输入不再静默产生空候选域, 而是在
    # candidate_generation 规范化处 fail-closed 抛 ValueError。
    project_root = _build_empty_frontier_project(tmp_path / "min_side_exceeds_grid")

    with pytest.raises(ValueError, match="min_side exceeds grid dimensions"):
        run_outer_search(
            project_root=project_root,
            solve_mode="certified_exact",
            max_attempts=2,
            min_side=7,
            master_seconds=0.01,
            binding_seconds=0.01,
            routing_seconds=0.01,
            benders_max_iter=1,
            campaign_hours=1.0,
            resume_campaign=False,
            parallel_processes=1,
        )

    # 异常退出不得留下任何 certified 公开面工件。
    assert not (project_root / "data" / "solutions" / "final_solution.json").exists()
    assert not delivery_manifest_output_path(project_root).exists()


def test_static_lower_bound_empty_domain_fails_closed_unproven_without_solver_calls(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # 权威全域下空候选域仍可达: mandatory 静态面积下界把 safe_area_upper_bound
    # 压到 min_side^2 以下 (33 格 mandatory → safe=3 < 36)。该路径必须零 solver
    # 调用，但在 terminal-INFEASIBLE evidence contract 尚不存在时只能 UNPROVEN。
    project_root = _build_empty_frontier_project(tmp_path / "empty_domain_infeasible")
    _write_json(
        project_root / "data" / "preprocessed" / "mandatory_exact_instances.json",
        [
            {
                "instance_id": f"synthetic_{idx:03d}",
                "facility_type": "synthetic",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            }
            for idx in range(33)
        ],
    )

    calls: list[tuple[int, int]] = []

    def fake_run_benders_for_ghost_rect(*, ghost_w: int, ghost_h: int, session=None, **kwargs):
        calls.append((ghost_w, ghost_h))
        return "INFEASIBLE", None

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
        min_side=6,
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        benders_max_iter=1,
        campaign_hours=1.0,
        resume_campaign=False,
        parallel_processes=1,
    )

    manifest_payload = json.loads(
        delivery_manifest_output_path(project_root).read_text(encoding="utf-8")
    )

    assert status == "UNPROVEN"
    assert result is None
    assert calls == []
    assert manifest_payload["campaign"]["final_status"] == "UNPROVEN"
    assert manifest_payload["campaign"]["last_stop_reason"]["reason"] == (
        "search_exhausted_without_replayable_infeasible_evidence"
    )
    assert manifest_payload["best_certified_result"] is None
    assert manifest_payload["artifacts"]["final_solution"]["exists"] is False
    assert manifest_payload["artifacts"]["optimal_blueprint"]["exists"] is False


def test_production_campaign_child_reports_selection_and_master_status_breakdown(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import temp_scripts.benchmark_parallelism as benchmark_module

    project_root = _build_empty_frontier_project(tmp_path / "benchmark_project")
    workspace_root = _build_empty_frontier_project(tmp_path / "benchmark_workspace")
    requested_profile = "exact_coordinate_ghost_first_v1"

    def fake_run_outer_search(*, project_root: Path, **kwargs):
        assert kwargs["master_search_profile"] == requested_profile
        campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
        proof_summary = {
            "mode": "certified_exact",
            "master_status": RUN_STATUS_UNKNOWN,
            "master_last_solve": {
                "status": RUN_STATUS_UNKNOWN,
                "wall_time": 0.25,
                "user_time": 0.2,
                "deterministic_time": 1.5,
                "branches": 11,
                "conflicts": 4,
                "binary_propagations": 101,
                "integer_propagations": 17,
                "hinted_literals": 3,
                "known_feasible_hint": True,
                "search_profile": requested_profile,
                "search_branching": "test_branching",
            },
            "master_warm_start": {
                "used_greedy_hint": True,
                "greedy_hint_instances": 2,
                "master_hinted_literals": 3,
                "ghost_anchor_hint_applied": True,
                "ghost_anchor_hint_idx": 5,
                "ghost_anchor_hint_status": "applied",
                "residual_optional_zero_hinting_enabled": False,
                "residual_optional_zero_hints": 0,
                "warm_start_strategy": "ghost_aware_mandatory_rebuild",
                "ghost_aware_anchor_attempt_count": 2,
                "ghost_aware_anchor_selected_idx": 5,
                "ghost_aware_complete_mandatory_hint": True,
                "ghost_aware_hint_instances": 2,
                "local_repair_attempted": True,
                "local_repair_success": True,
                "local_repair_trigger_reason": "committed_cells_exhausted",
                "local_repair_window_size": 2,
                "local_repair_anchor_idx": 5,
                "local_repair_failed_group_id": "group_beta",
                "local_repair_failed_group_template": "beta",
                "local_repair_portfolio_attempt_count": 5,
                "local_repair_selected_group_orderings": [
                    "reverse_canonical",
                    "canonical",
                ],
            },
            "master_start_feasibility": {
                "ghost_anchor_hint_applied": True,
                "ghost_anchor_hint_idx": 5,
                "ghost_anchor_hint_status": "applied",
                "ghost_anchor_total_count": 9,
                "ghost_anchor_compatible_count": 2,
                "mandatory_hint_pose_count": 2,
                "mandatory_hint_occupied_cell_count": 4,
                "required_optional_positive_hints": 1,
                "residual_optional_positive_hints": 0,
                "residual_optional_zero_hints": 0,
                "warm_start_strategy": "ghost_aware_mandatory_rebuild",
                "ghost_aware_anchor_attempt_count": 2,
                "ghost_aware_anchor_selected_idx": 5,
                "ghost_aware_complete_mandatory_hint": True,
                "ghost_aware_hint_instances": 2,
                "local_repair_attempted": True,
                "local_repair_success": True,
                "local_repair_trigger_reason": "committed_cells_exhausted",
                "local_repair_window_size": 2,
                "local_repair_anchor_idx": 5,
                "local_repair_failed_group_id": "group_beta",
                "local_repair_failed_group_template": "beta",
                "local_repair_portfolio_attempt_count": 5,
                "local_repair_selected_group_orderings": [
                    "reverse_canonical",
                    "canonical",
                ],
            },
            "master_start_failure_attribution": {
                "attempted_anchor_count": 2,
                "failed_anchor_count": 1,
                "failure_reason_counts": {
                    "committed_cells_exhausted": 1,
                },
                "first_failed_anchor_idx": 1,
                "first_failed_group_id": "group_beta",
                "first_failed_group_template": "beta",
                "first_failed_group_required_count": 1,
                "first_failed_group_candidate_count": 1,
                "first_failed_group_surviving_after_blocked_count": 1,
                "first_failed_group_surviving_at_failure_count": 0,
                "first_failed_group_position": 1,
                "top_failed_groups": [
                    {
                        "group_id": "group_beta",
                        "facility_type": "beta",
                        "count": 1,
                    }
                ],
                "top_failed_group_failures": [
                    {
                        "group_id": "group_beta",
                        "facility_type": "beta",
                        "failure_reason": "committed_cells_exhausted",
                        "count": 1,
                    }
                ],
            },
            "master_start_local_repair": {
                "local_repair_attempted": True,
                "local_repair_success": True,
                "local_repair_trigger_reason": "committed_cells_exhausted",
                "local_repair_window_size": 2,
                "local_repair_anchor_idx": 5,
                "local_repair_failed_group_id": "group_beta",
                "local_repair_failed_group_template": "beta",
                "local_repair_portfolio_attempt_count": 5,
                "local_repair_selected_group_orderings": [
                    "reverse_canonical",
                    "canonical",
                ],
                "local_repair_attempt_count": 1,
                "local_repair_success_count": 1,
                "local_repair_intra_group_attempted_count": 0,
                "local_repair_committed_attempted_count": 1,
                "local_repair_window1_count": 0,
                "local_repair_window2_count": 1,
            },
            "master_boundary_port_feasibility": {
                "supported": True,
                "required_count": 46,
                "considered_anchor_count": 2,
                "screened_infeasible_anchor_count": 1,
                "screen_pass_anchor_count": 1,
                "unsupported_anchor_count": 0,
                "max_packable_min": 45,
                "max_packable_max": 46,
                "first_infeasible_anchor_idx": 1,
                "first_infeasible_anchor_max_packable": 45,
            },
            "master_mandatory_support_diagnostics": {
                "unsupported_group_count": 1,
                "empty_candidate_pool_group_count": 1,
                "groups": [
                    {
                        "group_id": "group_beta",
                        "facility_type": "manufacturing_3x3",
                        "operation_type": "beta",
                        "required_count": 2,
                        "candidate_pool_count": 2,
                        "unsupported_reason": None,
                    },
                    {
                        "group_id": "group_gamma",
                        "facility_type": "manufacturing_5x5",
                        "operation_type": "gamma",
                        "required_count": 1,
                        "candidate_pool_count": 1,
                        "unsupported_reason": None,
                    },
                    {
                        "group_id": "group_delta",
                        "facility_type": "protocol_core",
                        "operation_type": "delta",
                        "required_count": 1,
                        "candidate_pool_count": 0,
                        "unsupported_reason": "empty_candidate_pool",
                    },
                ],
            },
            "master_mandatory_group_prechecks": {
                "evaluated": True,
                "skipped_due_to_upstream_precheck": False,
                "upstream_anchor_filter_count": 2,
                "supported_group_count": 2,
                "groups": [
                    {
                        "group_id": "group_beta",
                        "facility_type": "manufacturing_3x3",
                        "operation_type": "beta",
                        "required_count": 2,
                        "oracle_class": "uniform_3x3",
                        "oracle_mode": "uniform_3x3",
                        "supported": True,
                        "unsupported_reason": None,
                        "considered_anchor_count": 2,
                        "screened_infeasible_anchor_count": 1,
                        "screen_pass_anchor_count": 1,
                        "unsupported_anchor_count": 0,
                        "max_packable_min": 1,
                        "max_packable_max": 2,
                        "first_infeasible_anchor_idx": 1,
                        "first_infeasible_anchor_max_packable": 1,
                    },
                    {
                        "group_id": "group_gamma",
                        "facility_type": "manufacturing_5x5",
                        "operation_type": "gamma",
                        "required_count": 1,
                        "oracle_class": None,
                        "oracle_mode": "generic_normalized_rect",
                        "supported": True,
                        "unsupported_reason": None,
                        "considered_anchor_count": 2,
                        "screened_infeasible_anchor_count": 0,
                        "screen_pass_anchor_count": 2,
                        "unsupported_anchor_count": 0,
                        "max_packable_min": 1,
                        "max_packable_max": 1,
                        "first_infeasible_anchor_idx": None,
                        "first_infeasible_anchor_max_packable": None,
                    },
                    {
                        "group_id": "group_delta",
                        "facility_type": "protocol_core",
                        "operation_type": "delta",
                        "required_count": 1,
                        "oracle_class": None,
                        "oracle_mode": "unsupported",
                        "supported": False,
                        "unsupported_reason": "non_rectangular_signature",
                        "considered_anchor_count": 2,
                        "screened_infeasible_anchor_count": 0,
                        "screen_pass_anchor_count": 0,
                        "unsupported_anchor_count": 2,
                        "max_packable_min": None,
                        "max_packable_max": None,
                        "first_infeasible_anchor_idx": None,
                        "first_infeasible_anchor_max_packable": None,
                    }
                ],
            },
            "master_candidate_precheck": {
                "triggered": False,
                "precheck_reason": None,
                "master_solve_skipped": False,
                "supported": True,
                "considered_anchor_count": 2,
                "screened_infeasible_anchor_count": 1,
                "screen_pass_anchor_count": 1,
                "max_packable_min": 45,
                "max_packable_max": 46,
                "first_infeasible_anchor_idx": 1,
                "first_infeasible_anchor_max_packable": 45,
                "triggered_group_id": None,
                "triggered_group_facility_type": None,
                "triggered_group_operation_type": None,
                "triggered_group_required_count": 0,
            },
            "master_domain_tightening": {
                "ghost_power_capacity_screen_enabled": True,
                "ghost_disabled_placements": 2,
                "ghost_surviving_placements": 10,
                "ghost_conditioned_family_upper_bound_constraints": 3,
                "ghost_family_reduction_anchor_count": 1,
            },
            "master_domain_activation": {
                "ghost_anchor_count": 9,
                "mandatory_slot_count": 2,
                "required_optional_slot_count": 2,
                "residual_optional_slot_count": 3,
                "mandatory_pose_literal_count": 6,
                "required_optional_pose_literal_count": 4,
                "residual_optional_pose_literal_count": 7,
                "required_optional_active_slot_upper_bound_sum": 2,
                "residual_optional_active_slot_upper_bound_sum": 3,
            },
            "master_signature_tightening": {
                "mandatory_bucket_upper_bound_constraints": 1,
                "required_optional_bucket_upper_bound_constraints": 2,
                "ghost_conditioned_mandatory_bucket_constraints": 4,
                "ghost_conditioned_required_optional_bucket_constraints": 5,
                "ghost_signature_reduction_anchor_count": 2,
            },
            "master_residual_signature_tightening": {
                "bucket_upper_bound_constraints": 2,
                "ghost_conditioned_bucket_constraints": 6,
                "ghost_signature_reduction_anchor_count": 4,
            },
            "master_coordinate_symmetry": {
                "enabled": True,
                "mandatory_signature_monotonic_constraints": 7,
                "required_optional_signature_monotonic_constraints": 3,
                "residual_optional_signature_monotonic_constraints": 5,
            },
        }
        campaign.mark_candidate_started(6, 1)
        campaign.mark_candidate_result(
            6,
            1,
            RUN_STATUS_UNKNOWN,
            proof_summary=proof_summary,
            loaded_exact_safe_cut_count=1,
            generated_exact_safe_cut_count=0,
        )
        campaign.mark_campaign_stopped("candidate_returned_unknown", status=RUN_STATUS_UNKNOWN)
        campaign.save()
        append_campaign_wave_summary(
            project_root=project_root,
            campaign_path=campaign.path,
            reset=True,
            wave_summary=build_wave_summary(
                wave_index=0,
                candidate_results=[
                    {
                        "candidate_key": "6x1",
                        "dispatch_seq": 0,
                        "attempt_index": 0,
                        "wave_slot_index": 0,
                        "selection_reason": "objective_head",
                        "status": RUN_STATUS_UNKNOWN,
                        "proof_summary": proof_summary,
                        "loaded_exact_safe_cut_count": 1,
                        "generated_exact_safe_cut_count": 0,
                    }
                ],
                completed=True,
                failure_reason=None,
                dispatched_candidate_keys=["6x1"],
                elapsed_seconds=0.1,
                peak_rss_bytes_external_total=128,
                peak_rss_bytes_internal_max_single_process=64,
            ),
        )
        return RUN_STATUS_UNKNOWN, None

    monkeypatch.setattr(benchmark_module, "run_outer_search", fake_run_outer_search)

    payload = benchmark_module._production_campaign_child(
        project_root=project_root,
        workspace_root=workspace_root,
        parallel_processes=4,
        master_search_profile=requested_profile,
    )

    assert payload["requested_master_search_profile"] == requested_profile
    assert payload["campaign_selection_reason_counts"] == {"objective_head": 1}
    assert payload["campaign_master_status_counts"] == {RUN_STATUS_UNKNOWN: 1}
    assert payload["campaign_master_search_profile_counts"] == {requested_profile: 1}
    assert payload["campaign_master_branch_count_sum"] == 11
    assert payload["campaign_master_branch_count_max"] == 11
    assert payload["campaign_master_conflict_count_sum"] == 4
    assert payload["campaign_master_conflict_count_max"] == 4
    assert payload["campaign_master_deterministic_time_sum"] == 1.5
    assert payload["campaign_master_binary_propagations_sum"] == 101
    assert payload["campaign_master_integer_propagations_sum"] == 17
    assert payload["campaign_master_zero_branch_unknown_count"] == 0
    assert payload["campaign_master_conflictful_unknown_count"] == 1
    assert payload["campaign_ghost_anchor_hint_applied_count"] == 1
    assert payload["campaign_ghost_anchor_hint_none_compatible_count"] == 0
    assert payload["campaign_ghost_aware_start_applied_count"] == 1
    assert payload["campaign_ghost_aware_start_fallback_count"] == 0
    assert payload["campaign_ghost_aware_anchor_attempt_count_sum"] == 2
    assert payload["campaign_master_hinted_literals_sum"] == 3
    assert payload["campaign_greedy_hint_instances_sum"] == 2
    assert payload["campaign_residual_optional_zero_hints_sum"] == 0
    assert payload["campaign_ghost_anchor_compatible_count_sum"] == 2
    assert payload["campaign_ghost_anchor_compatible_zero_count"] == 0
    assert payload["campaign_required_optional_positive_hints_sum"] == 1
    assert payload["campaign_residual_optional_positive_hints_sum"] == 0
    assert payload["campaign_required_optional_active_slot_upper_bound_sum"] == 2
    assert payload["campaign_residual_optional_active_slot_upper_bound_sum"] == 3
    assert payload["campaign_master_start_incompatible_unknown_count"] == 0
    assert payload["campaign_master_start_compatible_zero_branch_unknown_count"] == 0
    assert payload["campaign_ghost_aware_failed_anchor_count_sum"] == 1
    assert payload["campaign_ghost_aware_blocked_cells_exhausted_count_sum"] == 0
    assert payload["campaign_ghost_aware_committed_cells_exhausted_count_sum"] == 1
    assert payload["campaign_ghost_aware_intra_group_greedy_exhausted_count_sum"] == 0
    assert payload["campaign_ghost_aware_top_failed_groups"] == [
        {
            "group_id": "group_beta",
            "facility_type": "beta",
            "count": 1,
        }
    ]
    assert payload["campaign_ghost_aware_top_failed_group_failures"] == [
        {
            "group_id": "group_beta",
            "facility_type": "beta",
            "failure_reason": "committed_cells_exhausted",
            "count": 1,
        }
    ]
    assert payload["campaign_ghost_aware_local_repair_attempted_count"] == 1
    assert payload["campaign_ghost_aware_local_repair_success_count"] == 1
    assert payload["campaign_ghost_aware_local_repair_intra_group_attempted_count"] == 0
    assert payload["campaign_ghost_aware_local_repair_committed_attempted_count"] == 1
    assert payload["campaign_ghost_aware_local_repair_window1_count"] == 0
    assert payload["campaign_ghost_aware_local_repair_window2_count"] == 1
    assert payload["campaign_ghost_aware_local_repair_portfolio_attempt_count_sum"] == 5
    assert payload["campaign_boundary_port_screen_supported_candidate_count"] == 1
    assert payload["campaign_boundary_port_screened_infeasible_anchor_count_sum"] == 1
    assert payload["campaign_boundary_port_screen_pass_anchor_count_sum"] == 1
    assert payload["campaign_boundary_port_screen_unsupported_anchor_count_sum"] == 0
    assert payload["campaign_boundary_port_max_packable_min_global"] == 45
    assert payload["campaign_boundary_port_max_packable_max_global"] == 46
    assert payload["campaign_candidate_precheck_triggered_count"] == 0
    assert payload["campaign_candidate_precheck_boundary_port_all_anchors_infeasible_count"] == 0
    assert payload["campaign_candidate_precheck_empty_pool_count"] == 0
    assert payload["campaign_candidate_precheck_empty_pool_group_counts"] == []
    assert payload["campaign_candidate_precheck_master_solve_skipped_count"] == 0
    assert payload["campaign_solve_attempt_count"] == 1
    assert payload["campaign_precheck_elimination_count"] == 0
    assert payload["campaign_precheck_elimination_reason_counts"] == {}
    assert payload["campaign_mandatory_support_unsupported_group_count_sum"] == 1
    assert payload["campaign_mandatory_support_empty_candidate_pool_group_count_sum"] == 1
    assert payload["campaign_mandatory_support_unsupported_reason_counts"] == {
        "empty_candidate_pool": 1,
    }
    assert payload["campaign_mandatory_group_precheck_evaluated_candidate_count"] == 1
    assert payload["campaign_mandatory_group_precheck_skipped_due_to_boundary_precheck_count"] == 0
    assert payload["campaign_mandatory_group_precheck_considered_anchor_count_sum"] == 6
    assert payload["campaign_mandatory_group_precheck_triggered_count"] == 0
    assert payload["campaign_mandatory_group_precheck_master_solve_skipped_count"] == 0
    assert payload["campaign_mandatory_group_precheck_supported_group_count_sum"] == 2
    assert payload["campaign_mandatory_group_precheck_supported_group_count_by_oracle_mode"] == {
        "generic_normalized_rect": 1,
        "uniform_3x3": 1,
    }
    assert payload["campaign_mandatory_group_precheck_unsupported_group_count_sum"] == 1
    assert payload["campaign_mandatory_group_precheck_unsupported_reason_counts"] == {
        "non_rectangular_signature": 1,
    }
    assert payload["campaign_mandatory_group_precheck_screened_infeasible_anchor_count_sum"] == 1
    assert payload["campaign_mandatory_group_precheck_screen_pass_anchor_count_sum"] == 3
    assert payload["campaign_mandatory_group_precheck_triggered_group_counts"] == []
    assert payload["campaign_ghost_disabled_placements_sum"] == 2
    assert payload["campaign_ghost_disabled_placements_max"] == 2
    assert payload["campaign_ghost_conditioned_family_upper_bound_constraints_sum"] == 3
    assert payload["campaign_ghost_conditioned_signature_bucket_constraints_sum"] == 9
    assert payload["campaign_ghost_signature_reduction_anchor_count_max"] == 2
    assert payload["campaign_ghost_conditioned_residual_signature_bucket_constraints_sum"] == 6
    assert payload["campaign_coordinate_symmetry_constraints_sum"] == 15
    assert payload["campaign_residual_coordinate_symmetry_constraints_sum"] == 5
    candidate_result = payload["campaign_wave_summaries"][0]["candidate_results"][0]
    assert candidate_result["selection_reason"] == "objective_head"
    assert candidate_result["wave_slot_index"] == 0
    assert candidate_result["proof_status_summary"]["master_last_solve"]["status"] == RUN_STATUS_UNKNOWN
    assert (
        candidate_result["proof_status_summary"]["master_last_solve"]["search_profile"]
        == requested_profile
    )
    assert candidate_result["proof_status_summary"]["master_last_solve"]["branches"] == 11
    assert candidate_result["proof_status_summary"]["master_last_solve"]["conflicts"] == 4
    assert (
        candidate_result["proof_status_summary"]["master_last_solve"]["binary_propagations"]
        == 101
    )
    assert (
        candidate_result["proof_status_summary"]["master_last_solve"]["integer_propagations"]
        == 17
    )
    assert candidate_result["proof_status_summary"]["master_domain_tightening"] == {
        "ghost_power_capacity_screen_enabled": True,
        "ghost_disabled_placements": 2,
        "ghost_surviving_placements": 10,
        "ghost_conditioned_family_upper_bound_constraints": 3,
        "ghost_family_reduction_anchor_count": 1,
    }
    assert candidate_result["proof_status_summary"]["master_signature_tightening"] == {
        "mandatory_bucket_upper_bound_constraints": 1,
        "required_optional_bucket_upper_bound_constraints": 2,
        "ghost_conditioned_mandatory_bucket_constraints": 4,
        "ghost_conditioned_required_optional_bucket_constraints": 5,
        "ghost_signature_reduction_anchor_count": 2,
    }
    assert candidate_result["proof_status_summary"][
        "master_residual_signature_tightening"
    ] == {
        "bucket_upper_bound_constraints": 2,
        "ghost_conditioned_bucket_constraints": 6,
        "ghost_signature_reduction_anchor_count": 4,
    }
    assert candidate_result["proof_status_summary"]["master_coordinate_symmetry"] == {
        "enabled": True,
        "mandatory_signature_monotonic_constraints": 7,
        "required_optional_signature_monotonic_constraints": 3,
        "residual_optional_signature_monotonic_constraints": 5,
    }
    assert candidate_result["proof_status_summary"]["master_warm_start"] == {
        "used_greedy_hint": True,
        "greedy_hint_instances": 2,
        "master_hinted_literals": 3,
        "ghost_anchor_hint_applied": True,
        "ghost_anchor_hint_idx": 5,
        "ghost_anchor_hint_status": "applied",
        "residual_optional_zero_hinting_enabled": False,
        "residual_optional_zero_hints": 0,
        "warm_start_strategy": "ghost_aware_mandatory_rebuild",
        "ghost_aware_anchor_attempt_count": 2,
        "ghost_aware_anchor_selected_idx": 5,
        "ghost_aware_complete_mandatory_hint": True,
        "ghost_aware_hint_instances": 2,
        "ghost_aware_pose_order_portfolio_attempted": False,
        "ghost_aware_pose_order_portfolio_success": False,
        "ghost_aware_pose_order_portfolio_selected_ordering": None,
        "ghost_aware_pose_order_portfolio_attempt_count": 0,
        "ghost_aware_pose_order_portfolio_failed_anchor_count": 0,
        "ghost_aware_pose_order_portfolio_failure_reason_counts": {},
        "ghost_aware_pose_order_portfolio_failure_samples": [],
        "ghost_aware_pose_order_validation_attempt_count": 0,
        "ghost_aware_pose_order_validation_rejected_count": 0,
        "ghost_aware_pose_order_validation_last_status": None,
        "ghost_aware_pose_order_validation_last_reason": None,
        "local_repair_attempted": True,
        "local_repair_success": True,
        "local_repair_trigger_reason": "committed_cells_exhausted",
        "local_repair_window_size": 2,
        "local_repair_anchor_idx": 5,
        "local_repair_failed_group_id": "group_beta",
        "local_repair_failed_group_template": "beta",
        "local_repair_portfolio_attempt_count": 5,
        "local_repair_selected_group_orderings": [
            "reverse_canonical",
            "canonical",
        ],
    }
    assert candidate_result["proof_status_summary"]["master_start_feasibility"] == {
        "ghost_anchor_hint_applied": True,
        "ghost_anchor_hint_idx": 5,
        "ghost_anchor_hint_status": "applied",
        "ghost_anchor_total_count": 9,
        "ghost_anchor_compatible_count": 2,
        "mandatory_hint_pose_count": 2,
        "mandatory_hint_occupied_cell_count": 4,
        "required_optional_positive_hints": 1,
        "residual_optional_positive_hints": 0,
        "residual_optional_zero_hints": 0,
        "warm_start_strategy": "ghost_aware_mandatory_rebuild",
        "ghost_aware_anchor_attempt_count": 2,
        "ghost_aware_anchor_selected_idx": 5,
        "ghost_aware_complete_mandatory_hint": True,
        "ghost_aware_hint_instances": 2,
        "ghost_aware_pose_order_portfolio_attempted": False,
        "ghost_aware_pose_order_portfolio_success": False,
        "ghost_aware_pose_order_portfolio_selected_ordering": None,
        "ghost_aware_pose_order_portfolio_attempt_count": 0,
        "ghost_aware_pose_order_portfolio_failed_anchor_count": 0,
        "ghost_aware_pose_order_portfolio_failure_reason_counts": {},
        "ghost_aware_pose_order_portfolio_failure_samples": [],
        "ghost_aware_pose_order_validation_attempt_count": 0,
        "ghost_aware_pose_order_validation_rejected_count": 0,
        "ghost_aware_pose_order_validation_last_status": None,
        "ghost_aware_pose_order_validation_last_reason": None,
        "local_repair_attempted": True,
        "local_repair_success": True,
        "local_repair_trigger_reason": "committed_cells_exhausted",
        "local_repair_window_size": 2,
        "local_repair_anchor_idx": 5,
        "local_repair_failed_group_id": "group_beta",
        "local_repair_failed_group_template": "beta",
        "local_repair_portfolio_attempt_count": 5,
        "local_repair_selected_group_orderings": [
            "reverse_canonical",
            "canonical",
        ],
    }
    assert candidate_result["proof_status_summary"]["master_start_failure_attribution"] == {
        "attempted_anchor_count": 2,
        "failed_anchor_count": 1,
        "failure_reason_counts": {
            "committed_cells_exhausted": 1,
        },
        "first_failed_anchor_idx": 1,
        "first_failed_group_id": "group_beta",
        "first_failed_group_template": "beta",
        "first_failed_group_required_count": 1,
        "first_failed_group_candidate_count": 1,
        "first_failed_group_surviving_after_blocked_count": 1,
        "first_failed_group_surviving_at_failure_count": 0,
        "first_failed_group_position": 1,
        "top_failed_groups": [
            {
                "group_id": "group_beta",
                "facility_type": "beta",
                "count": 1,
            }
        ],
        "top_failed_group_failures": [
            {
                "group_id": "group_beta",
                "facility_type": "beta",
                "failure_reason": "committed_cells_exhausted",
                "count": 1,
            }
        ],
    }
    assert candidate_result["proof_status_summary"]["master_start_local_repair"] == {
        "local_repair_attempted": True,
        "local_repair_success": True,
        "local_repair_trigger_reason": "committed_cells_exhausted",
        "local_repair_window_size": 2,
        "local_repair_anchor_idx": 5,
        "local_repair_failed_group_id": "group_beta",
        "local_repair_failed_group_template": "beta",
        "local_repair_portfolio_attempt_count": 5,
        "local_repair_selected_group_orderings": [
            "reverse_canonical",
            "canonical",
        ],
        "local_repair_attempt_count": 1,
        "local_repair_success_count": 1,
        "local_repair_intra_group_attempted_count": 0,
        "local_repair_committed_attempted_count": 1,
        "local_repair_window1_count": 0,
        "local_repair_window2_count": 1,
    }
    assert candidate_result["proof_status_summary"]["master_boundary_port_feasibility"] == {
        "supported": True,
        "required_count": 46,
        "considered_anchor_count": 2,
        "screened_infeasible_anchor_count": 1,
        "screen_pass_anchor_count": 1,
        "unsupported_anchor_count": 0,
        "max_packable_min": 45,
        "max_packable_max": 46,
        "first_infeasible_anchor_idx": 1,
        "first_infeasible_anchor_max_packable": 45,
    }
    assert candidate_result["proof_status_summary"]["master_mandatory_support_diagnostics"] == {
        "unsupported_group_count": 1,
        "empty_candidate_pool_group_count": 1,
        "groups": [
            {
                "group_id": "group_beta",
                "facility_type": "manufacturing_3x3",
                "operation_type": "beta",
                "required_count": 2,
                "candidate_pool_count": 2,
                "unsupported_reason": None,
            },
            {
                "group_id": "group_gamma",
                "facility_type": "manufacturing_5x5",
                "operation_type": "gamma",
                "required_count": 1,
                "candidate_pool_count": 1,
                "unsupported_reason": None,
            },
            {
                "group_id": "group_delta",
                "facility_type": "protocol_core",
                "operation_type": "delta",
                "required_count": 1,
                "candidate_pool_count": 0,
                "unsupported_reason": "empty_candidate_pool",
            },
        ],
    }
    assert candidate_result["proof_status_summary"]["master_mandatory_group_prechecks"] == {
        "evaluated": True,
        "skipped_due_to_upstream_precheck": False,
        "upstream_anchor_filter_count": 2,
        "supported_group_count": 2,
        "groups": [
            {
                "group_id": "group_beta",
                "facility_type": "manufacturing_3x3",
                "operation_type": "beta",
                "required_count": 2,
                "oracle_class": "uniform_3x3",
                "oracle_mode": "uniform_3x3",
                "supported": True,
                "unsupported_reason": None,
                "considered_anchor_count": 2,
                "screened_infeasible_anchor_count": 1,
                "screen_pass_anchor_count": 1,
                "unsupported_anchor_count": 0,
                "max_packable_min": 1,
                "max_packable_max": 2,
                "first_infeasible_anchor_idx": 1,
                "first_infeasible_anchor_max_packable": 1,
            },
            {
                "group_id": "group_gamma",
                "facility_type": "manufacturing_5x5",
                "operation_type": "gamma",
                "required_count": 1,
                "oracle_class": None,
                "oracle_mode": "generic_normalized_rect",
                "supported": True,
                "unsupported_reason": None,
                "considered_anchor_count": 2,
                "screened_infeasible_anchor_count": 0,
                "screen_pass_anchor_count": 2,
                "unsupported_anchor_count": 0,
                "max_packable_min": 1,
                "max_packable_max": 1,
                "first_infeasible_anchor_idx": None,
                "first_infeasible_anchor_max_packable": None,
            },
            {
                "group_id": "group_delta",
                "facility_type": "protocol_core",
                "operation_type": "delta",
                "required_count": 1,
                "oracle_class": None,
                "oracle_mode": "unsupported",
                "supported": False,
                "unsupported_reason": "non_rectangular_signature",
                "considered_anchor_count": 2,
                "screened_infeasible_anchor_count": 0,
                "screen_pass_anchor_count": 0,
                "unsupported_anchor_count": 2,
                "max_packable_min": None,
                "max_packable_max": None,
                "first_infeasible_anchor_idx": None,
                "first_infeasible_anchor_max_packable": None,
            },
        ],
    }
    assert candidate_result["proof_status_summary"]["master_candidate_precheck"] == {
        "triggered": False,
        "precheck_reason": None,
        "master_solve_skipped": False,
        "supported": True,
        "considered_anchor_count": 2,
        "screened_infeasible_anchor_count": 1,
        "screen_pass_anchor_count": 1,
        "max_packable_min": 45,
        "max_packable_max": 46,
        "first_infeasible_anchor_idx": 1,
        "first_infeasible_anchor_max_packable": 45,
        "triggered_group_id": None,
        "triggered_group_facility_type": None,
        "triggered_group_operation_type": None,
        "triggered_group_required_count": 0,
    }
    assert candidate_result["proof_status_summary"]["master_domain_activation"] == {
        "ghost_anchor_count": 9,
        "mandatory_slot_count": 2,
        "required_optional_slot_count": 2,
        "residual_optional_slot_count": 3,
        "mandatory_pose_literal_count": 6,
        "required_optional_pose_literal_count": 4,
        "residual_optional_pose_literal_count": 7,
        "required_optional_active_slot_upper_bound_sum": 2,
        "residual_optional_active_slot_upper_bound_sum": 3,
    }


def test_production_campaign_child_reports_candidate_precheck_master_infeasible(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import temp_scripts.benchmark_parallelism as benchmark_module

    project_root = _build_empty_frontier_project(tmp_path / "benchmark_precheck_project")
    workspace_root = _build_empty_frontier_project(tmp_path / "benchmark_precheck_workspace")

    def fake_run_outer_search(*, project_root: Path, **kwargs):
        campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
        proof_summary = {
            "mode": "certified_exact",
            "master_status": RUN_STATUS_INFEASIBLE,
            "used_exact_core_reuse": True,
            "core_build_seconds": 0.01,
            "overlay_build_seconds": 0.0,
            "ghost_constraint_seconds": 0.0,
            "cut_replay_seconds": 0.0,
            "master_candidate_precheck": {
                "triggered": True,
                "precheck_reason": "boundary_port_all_anchors_infeasible",
                "master_solve_skipped": True,
                "supported": True,
                "considered_anchor_count": 52,
                "screened_infeasible_anchor_count": 52,
                "screen_pass_anchor_count": 0,
                "max_packable_min": 17,
                "max_packable_max": 39,
                "first_infeasible_anchor_idx": 0,
                "first_infeasible_anchor_max_packable": 17,
                "triggered_group_id": None,
                "triggered_group_facility_type": None,
                "triggered_group_operation_type": None,
                "triggered_group_required_count": 0,
            },
            "master_boundary_port_feasibility": {
                "supported": True,
                "required_count": 46,
                "considered_anchor_count": 52,
                "screened_infeasible_anchor_count": 52,
                "screen_pass_anchor_count": 0,
                "unsupported_anchor_count": 0,
                "max_packable_min": 17,
                "max_packable_max": 39,
                "first_infeasible_anchor_idx": 0,
                "first_infeasible_anchor_max_packable": 17,
            },
            "master_mandatory_support_diagnostics": {
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
            },
            "master_mandatory_group_prechecks": {
                "evaluated": False,
                "skipped_due_to_upstream_precheck": True,
                "upstream_anchor_filter_count": 0,
                "supported_group_count": 0,
                "groups": [],
            },
        }
        campaign.mark_candidate_started(6, 1)
        campaign.mark_candidate_result(
            6,
            1,
            RUN_STATUS_INFEASIBLE,
            proof_summary=proof_summary,
            loaded_exact_safe_cut_count=0,
            generated_exact_safe_cut_count=0,
        )
        campaign.mark_campaign_stopped("candidate_returned_infeasible", status=RUN_STATUS_INFEASIBLE)
        campaign.save()
        append_campaign_wave_summary(
            project_root=project_root,
            campaign_path=campaign.path,
            reset=True,
            wave_summary=build_wave_summary(
                wave_index=0,
                candidate_results=[
                    {
                        "candidate_key": "6x1",
                        "dispatch_seq": 0,
                        "attempt_index": 0,
                        "wave_slot_index": 0,
                        "selection_reason": "prune_head",
                        "status": RUN_STATUS_INFEASIBLE,
                        "proof_summary": proof_summary,
                        "loaded_exact_safe_cut_count": 0,
                        "generated_exact_safe_cut_count": 0,
                    }
                ],
                completed=True,
                failure_reason=None,
                dispatched_candidate_keys=["6x1"],
                elapsed_seconds=0.1,
                peak_rss_bytes_external_total=0,
                peak_rss_bytes_internal_max_single_process=0,
            ),
        )
        return RUN_STATUS_INFEASIBLE, None

    monkeypatch.setattr(benchmark_module, "run_outer_search", fake_run_outer_search)

    payload = benchmark_module._production_campaign_child(
        project_root=project_root,
        workspace_root=workspace_root,
        parallel_processes=1,
        master_search_profile="exact_coordinate_guided_branching_v4",
    )

    assert payload["status"] == RUN_STATUS_INFEASIBLE
    assert payload["campaign_outcome_counts"] == {"master_infeasible": 1}
    assert payload["campaign_candidate_precheck_triggered_count"] == 1
    assert payload["campaign_candidate_precheck_boundary_port_all_anchors_infeasible_count"] == 1
    assert payload["campaign_candidate_precheck_empty_pool_count"] == 0
    assert payload["campaign_candidate_precheck_empty_pool_group_counts"] == []
    assert payload["campaign_candidate_precheck_master_solve_skipped_count"] == 1
    assert payload["campaign_solve_attempt_count"] == 0
    assert payload["campaign_precheck_elimination_count"] == 1
    assert payload["campaign_precheck_elimination_reason_counts"] == {
        "boundary_port_all_anchors_infeasible": 1
    }
    assert payload["campaign_mandatory_support_unsupported_group_count_sum"] == 1
    assert payload["campaign_mandatory_support_empty_candidate_pool_group_count_sum"] == 1
    assert payload["campaign_mandatory_support_unsupported_reason_counts"] == {
        "empty_candidate_pool": 1,
    }
    assert payload["campaign_mandatory_group_precheck_evaluated_candidate_count"] == 0
    assert payload["campaign_mandatory_group_precheck_skipped_due_to_boundary_precheck_count"] == 1
    assert payload["campaign_mandatory_group_precheck_considered_anchor_count_sum"] == 0
    assert payload["campaign_mandatory_group_precheck_triggered_count"] == 0
    assert payload["campaign_mandatory_group_precheck_master_solve_skipped_count"] == 0
    assert payload["campaign_mandatory_group_precheck_supported_group_count_sum"] == 0
    assert payload["campaign_mandatory_group_precheck_supported_group_count_by_oracle_mode"] == {}
    assert payload["campaign_mandatory_group_precheck_unsupported_group_count_sum"] == 0
    assert payload["campaign_mandatory_group_precheck_unsupported_reason_counts"] == {}
    assert payload["campaign_mandatory_group_precheck_screened_infeasible_anchor_count_sum"] == 0
    assert payload["campaign_mandatory_group_precheck_screen_pass_anchor_count_sum"] == 0
    assert payload["campaign_mandatory_group_precheck_triggered_group_counts"] == []
    candidate_result = payload["campaign_wave_summaries"][0]["candidate_results"][0]
    assert "master_last_solve" not in candidate_result["proof_status_summary"]
    assert candidate_result["proof_status_summary"]["master_candidate_precheck"] == {
        "triggered": True,
        "precheck_reason": "boundary_port_all_anchors_infeasible",
        "master_solve_skipped": True,
        "supported": True,
        "considered_anchor_count": 52,
        "screened_infeasible_anchor_count": 52,
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
    assert candidate_result["proof_status_summary"]["master_mandatory_group_prechecks"] == {
        "evaluated": False,
        "skipped_due_to_upstream_precheck": True,
        "upstream_anchor_filter_count": 0,
        "supported_group_count": 0,
        "groups": [],
    }
    assert candidate_result["proof_status_summary"]["master_mandatory_support_diagnostics"] == {
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


def test_production_campaign_child_reports_empty_pool_candidate_precheck_master_infeasible(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import temp_scripts.benchmark_parallelism as benchmark_module

    project_root = _build_empty_frontier_project(tmp_path / "benchmark_empty_pool_precheck_project")
    workspace_root = _build_empty_frontier_project(tmp_path / "benchmark_empty_pool_precheck_workspace")

    def fake_run_outer_search(*, project_root: Path, **kwargs):
        campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
        proof_summary = {
            "mode": "certified_exact",
            "master_status": RUN_STATUS_INFEASIBLE,
            "used_exact_core_reuse": True,
            "core_build_seconds": 0.01,
            "overlay_build_seconds": 0.0,
            "ghost_constraint_seconds": 0.0,
            "cut_replay_seconds": 0.0,
            "master_candidate_precheck": {
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
            },
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
            },
            "master_mandatory_group_prechecks": {
                "evaluated": False,
                "skipped_due_to_upstream_precheck": False,
                "upstream_anchor_filter_count": 0,
                "supported_group_count": 0,
                "groups": [],
            },
        }
        campaign.mark_candidate_started(6, 1)
        campaign.mark_candidate_result(
            6,
            1,
            RUN_STATUS_INFEASIBLE,
            proof_summary=proof_summary,
            loaded_exact_safe_cut_count=0,
            generated_exact_safe_cut_count=0,
        )
        campaign.mark_campaign_stopped("candidate_returned_infeasible", status=RUN_STATUS_INFEASIBLE)
        campaign.save()
        append_campaign_wave_summary(
            project_root=project_root,
            campaign_path=campaign.path,
            reset=True,
            wave_summary=build_wave_summary(
                wave_index=0,
                candidate_results=[
                    {
                        "candidate_key": "6x1",
                        "dispatch_seq": 0,
                        "attempt_index": 0,
                        "wave_slot_index": 0,
                        "selection_reason": "prune_head",
                        "status": RUN_STATUS_INFEASIBLE,
                        "proof_summary": proof_summary,
                        "loaded_exact_safe_cut_count": 0,
                        "generated_exact_safe_cut_count": 0,
                    }
                ],
                completed=True,
                failure_reason=None,
                dispatched_candidate_keys=["6x1"],
                elapsed_seconds=0.1,
                peak_rss_bytes_external_total=0,
                peak_rss_bytes_internal_max_single_process=0,
            ),
        )
        return RUN_STATUS_INFEASIBLE, None

    monkeypatch.setattr(benchmark_module, "run_outer_search", fake_run_outer_search)

    payload = benchmark_module._production_campaign_child(
        project_root=project_root,
        workspace_root=workspace_root,
        parallel_processes=1,
        master_search_profile="exact_coordinate_guided_branching_v4",
    )

    assert payload["status"] == RUN_STATUS_INFEASIBLE
    assert payload["campaign_outcome_counts"] == {"master_infeasible": 1}
    assert payload["campaign_candidate_precheck_triggered_count"] == 1
    assert payload["campaign_candidate_precheck_boundary_port_all_anchors_infeasible_count"] == 0
    assert payload["campaign_candidate_precheck_empty_pool_count"] == 1
    assert payload["campaign_candidate_precheck_empty_pool_group_counts"] == [
        {
            "group_id": "group::protocol_core::protocol_core::0",
            "facility_type": "protocol_core",
            "count": 1,
        }
    ]
    assert payload["campaign_candidate_precheck_master_solve_skipped_count"] == 1
    assert payload["campaign_solve_attempt_count"] == 0
    assert payload["campaign_precheck_elimination_count"] == 1
    assert payload["campaign_precheck_elimination_reason_counts"] == {
        "mandatory_group_empty_candidate_pool": 1
    }
    assert payload["campaign_mandatory_support_unsupported_group_count_sum"] == 1
    assert payload["campaign_mandatory_support_empty_candidate_pool_group_count_sum"] == 1
    assert payload["campaign_mandatory_support_unsupported_reason_counts"] == {
        "empty_candidate_pool": 1,
    }
    assert payload["campaign_mandatory_group_precheck_evaluated_candidate_count"] == 0
    assert payload["campaign_mandatory_group_precheck_skipped_due_to_boundary_precheck_count"] == 0
    assert payload["campaign_mandatory_group_precheck_considered_anchor_count_sum"] == 0
    candidate_result = payload["campaign_wave_summaries"][0]["candidate_results"][0]
    assert "master_last_solve" not in candidate_result["proof_status_summary"]
    assert candidate_result["proof_status_summary"]["master_candidate_precheck"] == {
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
    assert candidate_result["proof_status_summary"]["master_mandatory_support_diagnostics"] == {
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
    assert candidate_result["proof_status_summary"]["master_mandatory_group_prechecks"] == {
        "evaluated": False,
        "skipped_due_to_upstream_precheck": False,
        "upstream_anchor_filter_count": 0,
        "supported_group_count": 0,
        "groups": [],
    }


def test_resume_does_not_replay_persisted_exact_safe_cuts_into_master(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """V82: persisted exact_safe_cuts are telemetry, not proof objects.

    This test originally asserted that resume replays checkpoint cuts into the
    master. V82 found that path lets a forged JSON cut prune a feasible
    candidate (certified false negative), so the guarded behavior is inverted:
    persisted cuts must be counted but never applied.
    """
    project_root = _build_empty_frontier_project(tmp_path / "resume_fine_grained_cuts")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    exact_cut = {
        "schema_version": 2,
        "cut_type": "routing_front_blocked_nogood",
        "conflict_set": {"pose_optional::power_pole::pole_0": 0},
        "iteration": 1,
        "metadata": {"kind": "placement_local_nogood"},
        "source_mode": "certified_exact",
        "exact_safe": True,
        "artifact_hashes": campaign.artifact_hashes,
        "proof_stage": "routing",
        "binding_exhausted": False,
        "routing_exhausted": False,
        "proof_summary": {"routing_status": "PRECHECK_FRONT_BLOCKED"},
        "created_at": "2026-03-16T00:00:00Z",
    }
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_UNKNOWN,
        exact_safe_cuts=[exact_cut],
        proof_summary={"master_status": "UNKNOWN"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=1,
    )
    campaign.save()

    replayed_cuts: list[dict[str, int]] = []

    def fake_add_benders_cut(self, conflict_set, *, condition_lits=()):
        replayed_cuts.append(dict(conflict_set))
        return True

    def fake_solve(
        self,
        time_limit_seconds: float = 60.0,
        solution_hint=None,
        known_feasible_hint: bool = False,
        ghost_anchor_hint_idx=None,
        hint_inactive_residual_optionals: bool = True,
        **kwargs,
    ):
        self.build_stats["last_solve"] = {
            "status": "UNKNOWN",
            "wall_time": 0.0,
            "hinted_literals": 0,
            "known_feasible_hint": bool(known_feasible_hint),
        }
        return cp_model.UNKNOWN

    monkeypatch.setattr(MasterPlacementModel, "add_benders_cut", fake_add_benders_cut)
    monkeypatch.setattr(MasterPlacementModel, "solve", fake_solve)
    monkeypatch.setattr(MasterPlacementModel, "build_greedy_solution_hint", lambda self: {})

    status, result = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=0.01,
        binding_seconds=0.01,
        routing_seconds=0.01,
        max_iterations=1,
        campaign=campaign,
    )
    metadata = getattr(run_benders_for_ghost_rect, "last_run_metadata")

    assert status == RUN_STATUS_UNKNOWN
    assert result is None
    assert replayed_cuts == []
    assert metadata["loaded_exact_safe_cut_count"] == 0
    assert metadata["persisted_exact_safe_cut_replay_input_count"] == 1
    assert metadata["persisted_exact_safe_cut_replay_enabled"] is False
