from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.io.delivery_manifest import export_certified_delivery_manifest
from src.models.master_model import load_project_data
from src.search import benders_loop as bl
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


_MINIMAL_CERTIFIED_BINDING_RULES = {
    "commodity_metadata": {
        "source_ore": {
            "source_kind": "external_boundary",
            "sink_kind": "none",
        },
        "valley_battery": {
            "source_kind": "none",
            "sink_kind": "generic_input",
        },
        "ore": {
            "source_kind": "none",
            "sink_kind": "none",
        },
    },
}


def test_v83_binding_whole_layout_nogood_continues_lbbd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("EXACT_USE_POSE_BOOL_MASTER", raising=False)

    class FakeBindingModel:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def build(self) -> None:
            pass

        def extract_conflict_summary(self) -> dict[str, str]:
            return {"probe": "binding-infeasible-for-one-layout"}

        def extract_empty_binding_domain_instances(self) -> list[object]:
            return []

        def solve(self, *, time_limit_seconds: float) -> str:
            return "INFEASIBLE"

    monkeypatch.setattr(bl, "PortBindingModel", FakeBindingModel)
    master = SimpleNamespace(
        facility_pools={"T": [{"occupied_cells": [[0, 0]]}]},
        source_instances=[{"instance_id": "i", "facility_type": "T"}],
        grid_w=2,
        grid_h=2,
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {},
        },
        rules=_MINIMAL_CERTIFIED_BINDING_RULES,
    )
    controller = bl.LBBDController(
        master=master,
        cut_manager=SimpleNamespace(),
        project_root=tmp_path,
        solve_mode="certified_exact",
        max_iterations=2,
        binding_seconds=0.01,
    )
    monkeypatch.setattr(controller, "_add_exact_whole_layout_nogood", lambda **kwargs: True)

    status, _solution = controller._run_exact_binding_and_routing(
        iteration=1,
        solution={"i": {"facility_type": "T", "pose_idx": 0}},
        diagnostic_flow_status="not_run",
    )

    assert status == bl._EXACT_INTERNAL_STATUS_MASTER_CUT_ADDED_CONTINUE


def test_v83_publishable_surface_rejects_certified_result_without_empty_rect_witness(tmp_path: Path) -> None:
    root = tmp_path / "forged_surface"
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
                "pose_id": "T_center",
                "anchor": {"x": 1, "y": 1},
                "pose_params": {"orientation": 0, "port_mode": "default"},
                "occupied_cells": [[1, 1]],
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
    _write_json(data_dir / "generic_io_requirements.json", {"required_generic_inputs": {}, "required_generic_outputs": {}})

    final_result = {
        "search_status": "CERTIFIED",
        "ghost_rect": {"w": 3, "h": 2, "area": 6, "anchor_x": 0, "anchor_y": 0},
        "placement_solution": {"must_place": {"facility_type": "T", "pose_idx": 0}},
    }
    record = {
        "ghost_rect": {"w": 3, "h": 2, "area": 6, "anchor_x": 0, "anchor_y": 0},
        "attempts": 1,
        "started_at": "2026-06-10T00:00:00Z",
        "updated_at": "2026-06-10T00:00:01Z",
        "finished_at": "2026-06-10T00:00:01Z",
        "status": "CERTIFIED",
        "solution": final_result["placement_solution"],
        "proof_summary": {"probe": "forged"},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
    }
    candidate_records = {"3x2": record}
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
    evidence = build_terminal_frontier_evidence(
        candidates=generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation)),
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
        "master_domain_contract": {"schema_version": 1, "ghost_anchor_domain": "full_unfiltered", "ghost_anchor_filter": None},
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
    save_certified_final_solution_and_blueprint(project_root=root, result=final_result, facility_pools=facility_pools)

    with pytest.raises(ValueError, match="terminal_certified_final_result_ghost_rect_anchor_occupied"):
        export_certified_delivery_manifest(project_root=root, campaign_state=state, campaign_path=checkpoint_path)


def test_v83_certified_loader_rejects_non_mandatory_record_in_mandatory_exact_artifact(tmp_path: Path) -> None:
    root = tmp_path / "malformed_mandatory"
    data_dir = root / "data" / "preprocessed"
    rules_dir = root / "rules"
    data_dir.mkdir(parents=True)
    rules_dir.mkdir(parents=True)
    _write_json(rules_dir / "canonical_rules.json", {"facility_templates": {"T": {"dimensions": {"w": 1, "h": 1}}}})
    _write_json(data_dir / "candidate_placements.json", {"facility_pools": {"T": []}})
    _write_json(
        data_dir / "mandatory_exact_instances.json",
        [
            {"instance_id": "kept", "facility_type": "T", "operation_type": "op", "is_mandatory": True, "bound_type": "exact"},
            {"instance_id": "dropped", "facility_type": "T", "operation_type": "op", "is_mandatory": False, "bound_type": "exact"},
        ],
    )

    with pytest.raises(ValueError, match="is_mandatory must be true"):
        load_project_data(root, solve_mode="certified_exact")
