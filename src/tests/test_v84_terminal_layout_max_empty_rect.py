from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.search.exact_campaign import terminal_certified_final_result_project_precheck_violation
from src.io.delivery_manifest import export_certified_delivery_manifest
from src.search.certified_frontier import (
    TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
    build_terminal_frontier_evidence,
    candidate_generation_kwargs,
    generate_candidate_sizes,
)
from src.search.exact_campaign import (
    CAMPAIGN_SCHEMA_VERSION,
    PROOF_SUMMARY_SCHEMA_VERSION,
    compute_exact_artifact_hashes,
    terminal_certified_final_result_violation_for_project,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

def test_v84_terminal_project_validation_rejects_nonmaximal_empty_grid_layout(
    tmp_path: Path,
) -> None:
    root = tmp_path / "empty_grid_nonmaximal_layout"
    data_dir = root / "data" / "preprocessed"
    rules_dir = root / "rules"
    data_dir.mkdir(parents=True)
    rules_dir.mkdir(parents=True)

    _write_json(
        rules_dir / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": 3, "height": 3},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 1,
                },
            },
            "facility_templates": {},
        },
    )
    _write_json(data_dir / "candidate_placements.json", {"facility_pools": {}})
    _write_json(data_dir / "mandatory_exact_instances.json", [])
    _write_json(
        data_dir / "generic_io_requirements.json",
        {"required_generic_inputs": {}, "required_generic_outputs": {}},
    )

    final_result = {
        "search_status": "CERTIFIED",
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 0, "anchor_y": 0},
        "placement_solution": {},
        "search_stats": {},
    }
    candidate_generation = {
        "max_w": 3,
        "max_h": 3,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 9,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 9,
        "min_side_admissibility": 1,
    }
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    candidate_records = {}
    for area, ghost_w, ghost_h in candidates:
        status = "CERTIFIED" if (ghost_w, ghost_h) == (1, 1) else "INFEASIBLE"
        record = {
            "ghost_rect": {"w": ghost_w, "h": ghost_h, "area": area},
            "attempts": 1,
            "started_at": "2026-06-10T00:00:00Z",
            "updated_at": "2026-06-10T00:00:01Z",
            "finished_at": "2026-06-10T00:00:01Z",
            "status": status,
            "proof_summary": {"probe": "empty-grid-nonmaximal-layout"},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        if status == "CERTIFIED":
            record["solution"] = {
                "ghost_pick": {
                    "facility_type": "ghost_rect",
                    "pose_idx": 0,
                    "pose_id": "ghost_anchor::0,0",
                    "anchor": {"x": 0, "y": 0},
                }
            }
        candidate_records[f"{ghost_w}x{ghost_h}"] = record

    state = {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "solve_mode": "certified_exact",
        "campaign_hours": 168.0,
        "created_at": "2026-06-10T00:00:00Z",
        "updated_at": "2026-06-10T00:00:01Z",
        "artifact_hashes": compute_exact_artifact_hashes(root),
        "master_domain_contract": {
            "schema_version": 1,
            "ghost_anchor_domain": "full_unfiltered",
            "ghost_anchor_filter": None,
        },
        "proof_summary_schema_version": PROOF_SUMMARY_SCHEMA_VERSION,
        "reset_reason": None,
        "final_result": final_result,
        "final_status": "CERTIFIED",
        "last_stop_reason": {
            "status": "CERTIFIED",
            "reason": "search_exhausted_all_candidates",
        },
        "terminal_frontier_evidence": build_terminal_frontier_evidence(
            candidates=candidates,
            candidate_records=candidate_records,
            final_result=final_result,
            candidate_generation=candidate_generation,
        ),
        "declare_mode": "strict",
        "candidates": candidate_records,
    }

    assert (
        terminal_certified_final_result_project_precheck_violation(state, project_root=root)
        == "terminal_certified_final_result_layout_has_better_empty_rect"
    )


def test_v84_terminal_project_validation_rejects_layout_with_better_empty_rectangle(tmp_path: Path) -> None:
    root = tmp_path / "forged_nonmaximal_layout"
    data_dir = root / "data" / "preprocessed"
    checkpoint_dir = root / "data" / "checkpoints"
    rules_dir = root / "rules"
    data_dir.mkdir(parents=True)
    checkpoint_dir.mkdir(parents=True)
    rules_dir.mkdir(parents=True)

    rules = {
        "globals": {
            "grid": {"width": 3, "height": 3},
            "empty_rectangle": {
                "objective": "max_lex_area_min_side",
                "min_side_admissibility": 1,
            },
        },
        "facility_templates": {"T": {"dimensions": {"w": 1, "h": 1}}},
    }
    facility_pools = {
        "T": [
            {
                "pose_id": "T_origin",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
            }
        ]
    }
    _write_json(rules_dir / "canonical_rules.json", rules)
    _write_json(data_dir / "candidate_placements.json", {"facility_pools": facility_pools})
    _write_json(
        data_dir / "mandatory_exact_instances.json",
        [
            {
                "instance_id": "must_place",
                "facility_type": "T",
                "operation_type": "op",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            }
        ],
    )
    _write_json(
        data_dir / "generic_io_requirements.json",
        {"required_generic_inputs": {}, "required_generic_outputs": {}},
    )

    final_result = {
        "search_status": "CERTIFIED",
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": {"must_place": {"facility_type": "T", "pose_idx": 0}},
    }
    candidate_generation = {
        "max_w": 3,
        "max_h": 3,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 8,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 8,
        "min_side_admissibility": 1,
    }
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    candidate_records = {}
    for area, ghost_w, ghost_h in candidates:
        status = "CERTIFIED" if (ghost_w, ghost_h) == (1, 1) else "INFEASIBLE"
        record = {
            "ghost_rect": {"w": ghost_w, "h": ghost_h, "area": area},
            "attempts": 1,
            "started_at": "2026-06-10T00:00:00Z",
            "updated_at": "2026-06-10T00:00:01Z",
            "finished_at": "2026-06-10T00:00:01Z",
            "status": status,
            "proof_summary": {"probe": "forged-infeasible-records"},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        if status == "CERTIFIED":
            record["solution"] = final_result["placement_solution"]
        candidate_records[f"{ghost_w}x{ghost_h}"] = record

    evidence = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=candidate_records,
        final_result=final_result,
        candidate_generation=candidate_generation,
    )
    state = {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "solve_mode": "certified_exact",
        "campaign_hours": 168.0,
        "created_at": "2026-06-10T00:00:00Z",
        "updated_at": "2026-06-10T00:00:01Z",
        "artifact_hashes": compute_exact_artifact_hashes(root),
        "master_domain_contract": {
            "schema_version": 1,
            "ghost_anchor_domain": "full_unfiltered",
            "ghost_anchor_filter": None,
        },
        "proof_summary_schema_version": PROOF_SUMMARY_SCHEMA_VERSION,
        "reset_reason": None,
        "final_result": final_result,
        "final_status": "CERTIFIED",
        "last_stop_reason": {"status": "CERTIFIED", "reason": "search_exhausted_all_candidates"},
        "terminal_frontier_evidence": evidence,
        "declare_mode": "strict",
        "candidates": candidate_records,
    }
    checkpoint_path = checkpoint_dir / "exact_campaign_state.json"
    _write_json(checkpoint_path, state)

    with pytest.raises(
        ValueError,
        match="terminal_certified_final_result_layout_has_better_empty_rect",
    ):
        export_certified_delivery_manifest(
            project_root=root,
            campaign_state=state,
            campaign_path=checkpoint_path,
        )


def test_v84_terminal_project_validation_rejects_nonmaximal_empty_layout_without_mandatory_instances(
    tmp_path: Path,
) -> None:
    root = tmp_path / "forged_nonmaximal_empty_layout"
    data_dir = root / "data" / "preprocessed"
    checkpoint_dir = root / "data" / "checkpoints"
    rules_dir = root / "rules"
    data_dir.mkdir(parents=True)
    checkpoint_dir.mkdir(parents=True)
    rules_dir.mkdir(parents=True)

    _write_json(
        rules_dir / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": 3, "height": 3},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 1,
                },
            },
            "facility_templates": {},
        },
    )
    _write_json(data_dir / "candidate_placements.json", {"facility_pools": {}})
    _write_json(data_dir / "mandatory_exact_instances.json", [])
    _write_json(
        data_dir / "generic_io_requirements.json",
        {"required_generic_inputs": {}, "required_generic_outputs": {}},
    )

    final_result = {
        "search_status": "CERTIFIED",
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 0, "anchor_y": 0},
        "placement_solution": {},
    }
    candidate_generation = {
        "max_w": 3,
        "max_h": 3,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 9,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 9,
        "min_side_admissibility": 1,
    }
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    candidate_records = {}
    for area, ghost_w, ghost_h in candidates:
        status = "CERTIFIED" if (ghost_w, ghost_h) == (1, 1) else "INFEASIBLE"
        record = {
            "ghost_rect": {"w": ghost_w, "h": ghost_h, "area": area},
            "attempts": 1,
            "started_at": "2026-06-10T00:00:00Z",
            "updated_at": "2026-06-10T00:00:01Z",
            "finished_at": "2026-06-10T00:00:01Z",
            "status": status,
            "proof_summary": {"probe": "forged-infeasible-records"},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        if status == "CERTIFIED":
            record["solution"] = {
                "ghost_pick": {
                    "facility_type": "ghost_rect",
                    "pose_idx": 0,
                    "pose_id": "ghost_anchor::0,0",
                    "anchor": {"x": 0, "y": 0},
                }
            }
        candidate_records[f"{ghost_w}x{ghost_h}"] = record

    evidence = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=candidate_records,
        final_result=final_result,
        candidate_generation=candidate_generation,
    )
    state = {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "solve_mode": "certified_exact",
        "campaign_hours": 168.0,
        "created_at": "2026-06-10T00:00:00Z",
        "updated_at": "2026-06-10T00:00:01Z",
        "artifact_hashes": compute_exact_artifact_hashes(root),
        "master_domain_contract": {
            "schema_version": 1,
            "ghost_anchor_domain": "full_unfiltered",
            "ghost_anchor_filter": None,
        },
        "proof_summary_schema_version": PROOF_SUMMARY_SCHEMA_VERSION,
        "reset_reason": None,
        "final_result": final_result,
        "final_status": "CERTIFIED",
        "last_stop_reason": {"status": "CERTIFIED", "reason": "search_exhausted_all_candidates"},
        "terminal_frontier_evidence": evidence,
        "declare_mode": "strict",
        "candidates": candidate_records,
    }

    assert (
        terminal_certified_final_result_project_precheck_violation(state, project_root=root)
        == "terminal_certified_final_result_layout_has_better_empty_rect"
    )


def test_v84_exact_artifact_hashes_reject_symlinked_project_authority(
    tmp_path: Path,
) -> None:
    root = tmp_path / "symlinked_exact_artifact"
    data_dir = root / "data" / "preprocessed"
    rules_dir = root / "rules"
    external_dir = tmp_path / "external_authority"
    data_dir.mkdir(parents=True)
    rules_dir.mkdir(parents=True)
    external_dir.mkdir(parents=True)

    _write_json(
        rules_dir / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": 2, "height": 1},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 1,
                },
            }
        },
    )
    _write_json(
        data_dir / "mandatory_exact_instances.json",
        [
            {
                "instance_id": "must_place",
                "facility_type": "T",
                "operation_type": "op",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            }
        ],
    )
    _write_json(
        data_dir / "generic_io_requirements.json",
        {"required_generic_inputs": {}, "required_generic_outputs": {}},
    )
    external_candidate_path = external_dir / "candidate_placements_external.json"
    _write_json(
        external_candidate_path,
        {
            "facility_pools": {
                "T": [
                    {
                        "pose_id": "T_origin",
                        "anchor": {"x": 0, "y": 0},
                        "pose_params": {"orientation": 0, "port_mode": "default"},
                        "occupied_cells": [[0, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                    }
                ]
            }
        },
    )
    (data_dir / "candidate_placements.json").symlink_to(external_candidate_path)

    with pytest.raises(ValueError, match="exact artifact must be a regular file"):
        compute_exact_artifact_hashes(root)


def test_v96_exact_artifact_hashes_reject_symlinked_parent_project_authority(
    tmp_path: Path,
) -> None:
    root = tmp_path / "symlinked_exact_artifact_parent"
    external_preprocessed_dir = tmp_path / "external_preprocessed_authority"
    (root / "data").mkdir(parents=True)
    (root / "rules").mkdir(parents=True)
    external_preprocessed_dir.mkdir(parents=True)

    _write_json(
        root / "rules" / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": 2, "height": 1},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 1,
                },
            }
        },
    )
    _write_json(
        external_preprocessed_dir / "mandatory_exact_instances.json",
        [],
    )
    _write_json(
        external_preprocessed_dir / "candidate_placements.json",
        {"facility_pools": {}},
    )
    _write_json(
        external_preprocessed_dir / "generic_io_requirements.json",
        {"required_generic_inputs": {}, "required_generic_outputs": {}},
    )
    (root / "data" / "preprocessed").symlink_to(
        external_preprocessed_dir,
        target_is_directory=True,
    )

    with pytest.raises(ValueError, match="exact artifact must be a regular file"):
        compute_exact_artifact_hashes(root)


def test_v84_terminal_project_validation_rejects_unknown_extra_blocker_instance(
    tmp_path: Path,
) -> None:
    root = tmp_path / "unknown_extra_blocker"
    data_dir = root / "data" / "preprocessed"
    checkpoint_dir = root / "data" / "checkpoints"
    rules_dir = root / "rules"
    data_dir.mkdir(parents=True)
    checkpoint_dir.mkdir(parents=True)
    rules_dir.mkdir(parents=True)

    rules = {
        "globals": {
            "grid": {"width": 3, "height": 1},
            "empty_rectangle": {
                "objective": "max_lex_area_min_side",
                "min_side_admissibility": 1,
            },
        },
        "facility_templates": {"T": {"dimensions": {"w": 1, "h": 1}}},
    }
    facility_pools = {
        "T": [
            {
                "pose_id": "T_left",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
            },
            {
                "pose_id": "T_middle_fake",
                "anchor": {"x": 1, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
            },
        ]
    }
    _write_json(rules_dir / "canonical_rules.json", rules)
    _write_json(data_dir / "candidate_placements.json", {"facility_pools": facility_pools})
    _write_json(
        data_dir / "mandatory_exact_instances.json",
        [
            {
                "instance_id": "must_place",
                "facility_type": "T",
                "operation_type": "op",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            }
        ],
    )
    _write_json(
        data_dir / "generic_io_requirements.json",
        {"required_generic_inputs": {}, "required_generic_outputs": {}},
    )

    final_result = {
        "search_status": "CERTIFIED",
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 2, "anchor_y": 0},
        "placement_solution": {
            "must_place": {"facility_type": "T", "pose_idx": 0},
            "forged_extra_blocker": {"facility_type": "T", "pose_idx": 1},
        },
    }
    candidate_generation = {
        "max_w": 3,
        "max_h": 1,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 2,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 2,
        "min_side_admissibility": 1,
    }
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    candidate_records = {}
    for area, ghost_w, ghost_h in candidates:
        status = "CERTIFIED" if (ghost_w, ghost_h) == (1, 1) else "INFEASIBLE"
        record = {
            "ghost_rect": {"w": ghost_w, "h": ghost_h, "area": area},
            "attempts": 1,
            "started_at": "2026-06-10T00:00:00Z",
            "updated_at": "2026-06-10T00:00:01Z",
            "finished_at": "2026-06-10T00:00:01Z",
            "status": status,
            "proof_summary": {"probe": "extra-placement-blocker"},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        if status == "CERTIFIED":
            record["solution"] = final_result["placement_solution"]
        candidate_records[f"{ghost_w}x{ghost_h}"] = record

    evidence = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=candidate_records,
        final_result=final_result,
        candidate_generation=candidate_generation,
    )
    state = {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "solve_mode": "certified_exact",
        "campaign_hours": 168.0,
        "created_at": "2026-06-10T00:00:00Z",
        "updated_at": "2026-06-10T00:00:01Z",
        "artifact_hashes": compute_exact_artifact_hashes(root),
        "master_domain_contract": {
            "schema_version": 1,
            "ghost_anchor_domain": "full_unfiltered",
            "ghost_anchor_filter": None,
        },
        "proof_summary_schema_version": PROOF_SUMMARY_SCHEMA_VERSION,
        "reset_reason": None,
        "final_result": final_result,
        "final_status": "CERTIFIED",
        "last_stop_reason": {"status": "CERTIFIED", "reason": "search_exhausted_all_candidates"},
        "terminal_frontier_evidence": evidence,
        "declare_mode": "strict",
        "candidates": candidate_records,
    }
    checkpoint_path = checkpoint_dir / "exact_campaign_state.json"
    _write_json(checkpoint_path, state)

    with pytest.raises(
        ValueError,
        match="terminal_certified_final_result_solution_unknown_instance",
    ):
        export_certified_delivery_manifest(
            project_root=root,
            campaign_state=state,
            campaign_path=checkpoint_path,
        )
