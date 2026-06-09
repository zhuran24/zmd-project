from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.io.delivery_manifest import (
    delivery_manifest_output_path,
    export_certified_delivery_manifest,
)
from src.io.serializer import export_certified_blueprint
from src.models.cut_manager import RUN_STATUS_CERTIFIED, RUN_STATUS_INFEASIBLE
from src.search.exact_campaign import ExactCampaign


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_manifest_project(project_root: Path) -> tuple[Path, dict[str, list[dict[str, object]]]]:
    data_dir = project_root / "data" / "preprocessed"
    rules_dir = project_root / "rules"
    facility_pools = {
        "tiny_facility": [
            {
                "pose_id": "tiny_pose_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
                "pose_params": {"orientation": 0, "port_mode": "default"},
            }
        ]
    }

    _write_json(
        rules_dir / "canonical_rules.json",
        {
            "globals": {"grid": {"width": 2, "height": 1}},
            "facility_templates": {
                "tiny_facility": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            },
        },
    )
    _write_json(data_dir / "candidate_placements.json", {"facility_pools": facility_pools})
    _write_json(
        data_dir / "mandatory_exact_instances.json",
        [
            {
                "instance_id": "tiny_001",
                "facility_type": "tiny_facility",
                "is_mandatory": True,
                "bound_type": "exact",
                "solve_modes": ["certified_exact"],
            }
        ],
    )
    _write_json(data_dir / "all_facility_instances.json", [])
    _write_json(
        data_dir / "generic_io_requirements.json",
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )
    return project_root, facility_pools


def test_delivery_manifest_exports_best_certified_result_and_repo_relative_artifacts(
    tmp_path: Path,
) -> None:
    project_root, facility_pools = _build_manifest_project(tmp_path / "delivery_manifest_best")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={
            "tiny_001": {
                "pose_idx": 0,
                "pose_id": "tiny_pose_0",
                "anchor": {"x": 0, "y": 0},
                "facility_type": "tiny_facility",
            }
        },
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
        loaded_exact_safe_cut_count=1,
        generated_exact_safe_cut_count=2,
    )
    campaign.mark_campaign_stopped("search_exhausted_all_candidates", status=RUN_STATUS_CERTIFIED)
    campaign.save()

    best_result = campaign.best_certified_result()
    assert best_result is not None
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    export_certified_blueprint(
        project_root=project_root,
        result=best_result,
        facility_pools=facility_pools,
    )
    (project_root / "data" / "checkpoints" / "benders_cuts.jsonl").write_text(
        '{"schema_version": 2}\n',
        encoding="utf-8",
    )

    output_path, payload = export_certified_delivery_manifest(
        project_root=project_root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
    )

    assert output_path == delivery_manifest_output_path(project_root)
    assert payload["campaign"]["solve_mode"] == "certified_exact"
    assert payload["campaign"]["final_status"] == RUN_STATUS_CERTIFIED
    assert payload["best_certified_result"]["ghost_rect"] == {"w": 1, "h": 1, "area": 1}
    assert payload["best_certified_result"]["proof_summary"]["master_status"] == RUN_STATUS_CERTIFIED
    assert payload["best_certified_result"]["loaded_exact_safe_cut_count"] == 1
    assert payload["best_certified_result"]["generated_exact_safe_cut_count"] == 2
    assert payload["artifacts"]["campaign_state"]["path"] == "data/checkpoints/exact_campaign_state.json"
    assert payload["artifacts"]["final_solution"]["path"] == "data/solutions/final_solution.json"
    assert payload["artifacts"]["optimal_blueprint"]["path"] == "data/blueprints/optimal_blueprint.json"
    assert payload["artifacts"]["candidate_placements"]["path"] == "data/preprocessed/candidate_placements.json"
    assert payload["artifacts"]["benders_cuts"]["path"] == "data/checkpoints/benders_cuts.jsonl"
    assert payload["artifacts"]["campaign_state"]["exists"] is True
    assert payload["artifacts"]["final_solution"]["exists"] is True
    assert payload["artifacts"]["optimal_blueprint"]["exists"] is True
    assert payload["artifacts"]["candidate_placements"]["exists"] is True
    assert payload["artifacts"]["benders_cuts"]["exists"] is True
    assert all(":" not in entry["path"] for entry in payload["artifacts"].values())
    assert json.loads(output_path.read_text(encoding="utf-8")) == payload


def test_delivery_manifest_allows_terminal_campaign_without_best_certified_result(
    tmp_path: Path,
) -> None:
    project_root, _facility_pools = _build_manifest_project(tmp_path / "delivery_manifest_no_best")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    campaign.mark_campaign_stopped("search_exhausted_all_candidates", status=RUN_STATUS_INFEASIBLE)
    campaign.save()

    output_path, payload = export_certified_delivery_manifest(
        project_root=project_root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
    )

    assert output_path == delivery_manifest_output_path(project_root)
    assert payload["campaign"]["final_status"] == RUN_STATUS_INFEASIBLE
    assert payload["campaign"]["last_stop_reason"]["reason"] == "search_exhausted_all_candidates"
    assert payload["best_certified_result"] is None
    assert payload["artifacts"]["campaign_state"]["exists"] is True
    assert payload["artifacts"]["candidate_placements"]["exists"] is True
    assert payload["artifacts"]["final_solution"]["exists"] is False
    assert payload["artifacts"]["optimal_blueprint"]["exists"] is False


def test_delivery_manifest_rejects_best_effort_final_result(tmp_path: Path) -> None:
    project_root, _facility_pools = _build_manifest_project(tmp_path / "delivery_manifest_best_effort")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={"tiny_001": {"pose_idx": 0}},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["declare_mode"] = "best_effort"

    with pytest.raises(ValueError, match="strict declare_mode"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )
