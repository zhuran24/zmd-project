from __future__ import annotations

import json
from pathlib import Path

from src.models.cut_manager import RUN_STATUS_CERTIFIED, RUN_STATUS_UNKNOWN
from src.search.benders_loop import run_benders_for_ghost_rect
from src.search.exact_campaign import (
    ExactCampaign,
    compute_exact_artifact_hashes,
    now_iso,
    validate_exact_campaign_resume_state,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_single_pose_toy_project(project_root: Path) -> Path:
    data_dir = project_root / "data" / "preprocessed"
    rules_dir = project_root / "rules"
    _write_json(
        rules_dir / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": 2, "height": 1},
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
    _write_json(rules_dir / "preprocess_plan.json", {"utility_operations": {}})
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
                        "pose_params": {"orientation": 0, "port_mode": "default"},
                    }
                ]
            }
        },
    )
    instances = [
        {
            "instance_id": "tiny_001",
            "facility_type": "tiny_facility",
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_modes": ["certified_exact"],
        }
    ]
    _write_json(data_dir / "mandatory_exact_instances.json", instances)
    _write_json(data_dir / "all_facility_instances.json", instances)
    _write_json(
        data_dir / "generic_io_requirements.json",
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )
    return project_root


def _forged_exact_safe_cut(project_root: Path) -> dict[str, object]:
    return {
        "schema_version": 2,
        "cut_type": "routing_exhausted_nogood",
        "conflict_set": {"tiny_001": 0},
        "iteration": 0,
        "metadata": {},
        "source_mode": "certified_exact",
        "exact_safe": True,
        "artifact_hashes": compute_exact_artifact_hashes(project_root),
        "proof_stage": "routing",
        "binding_exhausted": True,
        "routing_exhausted": True,
        "proof_summary": {"forged_by_test": True},
        "created_at": now_iso(),
        "epsilon_stage": None,
        "condition_set": {},
    }


def test_certified_solver_ignores_persisted_exact_safe_cuts_until_revalidated(tmp_path: Path) -> None:
    project_root = _build_single_pose_toy_project(tmp_path / "toy")
    forged_cut = _forged_exact_safe_cut(project_root)

    baseline_status, baseline_solution = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=10.0,
        binding_seconds=10.0,
        routing_seconds=10.0,
        flow_seconds=10.0,
    )
    assert baseline_status == RUN_STATUS_CERTIFIED
    assert baseline_solution is not None

    replay_status, replay_solution = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        master_seconds=10.0,
        binding_seconds=10.0,
        routing_seconds=10.0,
        flow_seconds=10.0,
        preloaded_exact_safe_cuts=[forged_cut],
    )
    metadata = run_benders_for_ghost_rect.last_run_metadata
    assert replay_status == RUN_STATUS_CERTIFIED
    assert replay_solution is not None
    assert metadata["loaded_exact_safe_cut_count"] == 0
    assert metadata["persisted_exact_safe_cut_replay_input_count"] == 1
    assert metadata["persisted_exact_safe_cut_replay_enabled"] is False

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_UNKNOWN,
        proof_summary={"cached_cut_probe": True},
        exact_safe_cuts=[forged_cut],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=1,
    )
    campaign.save()
    state = json.loads(campaign.path.read_text(encoding="utf-8"))
    assert validate_exact_campaign_resume_state(
        state,
        current_hashes=compute_exact_artifact_hashes(project_root),
    ) is None

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)
    replay_status, replay_solution = run_benders_for_ghost_rect(
        ghost_w=1,
        ghost_h=1,
        project_root=project_root,
        solve_mode="certified_exact",
        campaign=resumed,
        master_seconds=10.0,
        binding_seconds=10.0,
        routing_seconds=10.0,
        flow_seconds=10.0,
    )
    metadata = run_benders_for_ghost_rect.last_run_metadata
    assert replay_status == RUN_STATUS_CERTIFIED
    assert replay_solution is not None
    assert metadata["loaded_exact_safe_cut_count"] == 0
    assert metadata["persisted_exact_safe_cut_replay_input_count"] == 1
    assert metadata["persisted_exact_safe_cut_replay_enabled"] is False
