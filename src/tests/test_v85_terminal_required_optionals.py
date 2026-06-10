from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.io.delivery_manifest import export_certified_delivery_manifest
from src.search.certified_frontier import (
    TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
    build_terminal_frontier_evidence,
    candidate_generation_kwargs,
    generate_candidate_sizes,
)
from src.search.certified_surface import save_certified_final_solution_and_blueprint
from src.search.exact_campaign import (
    CAMPAIGN_SCHEMA_VERSION,
    PROOF_SUMMARY_SCHEMA_VERSION,
    compute_exact_artifact_hashes,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def test_v85_terminal_project_validation_rejects_missing_required_pose_optional(
    tmp_path: Path,
) -> None:
    root = tmp_path / "required_optional_omitted"
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
        "facility_templates": {
            "T": {"dimensions": {"w": 1, "h": 1}},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}},
        },
    }
    t_cells = [(2, 0), (2, 1), (0, 2), (1, 2)]
    facility_pools = {
        "T": [
            {
                "pose_id": f"T_{x}_{y}",
                "anchor": {"x": x, "y": y},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[x, y]],
                "input_port_cells": [],
                "output_port_cells": [],
            }
            for x, y in t_cells
        ],
        "protocol_storage_box": [
            {
                "pose_id": "box_forced_inside_claimed_empty_rect",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
            }
        ],
    }
    mandatory_instances = [
        {
            "instance_id": f"must_{i}",
            "facility_type": "T",
            "operation_type": "op",
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_modes": ["certified_exact"],
        }
        for i in range(4)
    ]
    _write_json(rules_dir / "canonical_rules.json", rules)
    _write_json(data_dir / "candidate_placements.json", {"facility_pools": facility_pools})
    _write_json(data_dir / "mandatory_exact_instances.json", mandatory_instances)
    _write_json(
        data_dir / "generic_io_requirements.json",
        {"required_generic_inputs": {"iron_ore": 1}, "required_generic_outputs": {}},
    )

    placement_solution = {
        f"must_{i}": {"facility_type": "T", "pose_idx": i, "pose_id": f"T_{x}_{y}"}
        for i, (x, y) in enumerate(t_cells)
    }
    final_result = {
        "search_status": "CERTIFIED",
        "ghost_rect": {"w": 2, "h": 2, "area": 4, "anchor_x": 0, "anchor_y": 0},
        "placement_solution": placement_solution,
        "search_stats": {"probe": "required_optional_omitted"},
    }
    candidate_generation = {
        "max_w": 3,
        "max_h": 3,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 4,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 4,
        "min_side_admissibility": 1,
    }
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    candidate_records = {}
    for area, ghost_w, ghost_h in candidates:
        status = "CERTIFIED" if (ghost_w, ghost_h) == (2, 2) else "INFEASIBLE"
        record = {
            "ghost_rect": {"w": ghost_w, "h": ghost_h, "area": area},
            "attempts": 1,
            "started_at": "2026-06-10T00:00:00Z",
            "updated_at": "2026-06-10T00:00:01Z",
            "finished_at": "2026-06-10T00:00:01Z",
            "status": status,
            "proof_summary": {"probe": "forged terminal candidate status"},
            "exact_safe_cuts": [],
            "loaded_exact_safe_cut_count": 0,
            "generated_exact_safe_cut_count": 0,
        }
        if status == "CERTIFIED":
            record["solution"] = placement_solution
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
    save_certified_final_solution_and_blueprint(
        project_root=root,
        result=final_result,
        facility_pools=facility_pools,
    )

    with pytest.raises(
        ValueError,
        match="terminal_certified_final_result_solution_missing_required_optional_instance",
    ):
        export_certified_delivery_manifest(
            project_root=root,
            campaign_state=state,
            campaign_path=checkpoint_path,
        )
