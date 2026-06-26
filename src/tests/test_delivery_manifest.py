from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import src.io.delivery_manifest as delivery_manifest_module
import src.search.certified_surface as certified_surface_module
from src.tests.certified_frontier_helpers import (
    persist_canonical_blueprint_for_test,
    persist_forged_terminal_certified_state,
)
from src.io.delivery_manifest import (
    build_certified_delivery_manifest,
    delivery_manifest_output_path,
    export_certified_delivery_manifest,
    validate_certified_delivery_manifest_matches_campaign,
    write_certified_delivery_manifest,
)
from src.io.output_schema import blueprint_output_path
from src.io.serializer import (
    build_blueprint_payload_from_certified_result,
)
from src.models.cut_manager import RUN_STATUS_CERTIFIED, RUN_STATUS_INFEASIBLE, RUN_STATUS_UNKNOWN
from src.search.exact_campaign import (
    ExactCampaign,
    has_terminal_full_frontier_certified_evidence,
    terminal_certified_final_result_project_precheck_violation,
)
from src.search.certified_surface import verify_certified_delivery_surface
from src.tests.certified_frontier_helpers import attach_terminal_frontier_evidence



# V89: candidate records keep the ghost_pick provenance marker; the public
# final_result placement_solution strips it by protocol.
_V89_GHOST_PICK = {
    "ghost_pick": {
        "pose_idx": 1,
        "pose_id": "ghost_anchor::1,0",
        "anchor": {"x": 1, "y": 0},
        "facility_type": "ghost_rect",
    }
}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _forge_legacy_terminal_certified_stop(campaign: ExactCampaign) -> None:
    campaign.state["last_stop_reason"] = {
        "reason": "search_exhausted_all_candidates",
        "status": RUN_STATUS_CERTIFIED,
        "updated_at": "2026-03-16T00:00:00Z",
    }
    campaign.state["final_status"] = RUN_STATUS_CERTIFIED


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
            "globals": {"grid": {"width": 2, "height": 1}, "empty_rectangle": {"objective": "max_lex_area_min_side", "min_side_admissibility": 1}},
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


def _install_certified_manifest_test_replay(
    monkeypatch: pytest.MonkeyPatch,
    *,
    project_root: Path,
) -> None:
    """Bypass seal/replay validators so forged CERTIFIED states reach artifact checks.

    Patches both delivery_manifest_module (used by build_certified_delivery_manifest and
    validate_certified_delivery_manifest_matches_campaign) and certified_surface_module
    (used by evaluate_certified_delivery_surface / verify_certified_delivery_surface).
    Artifact-level checks are NOT patched and still run normally.
    """
    del project_root  # unused; kept in signature for caller documentation

    def _accept_resume_state(state, current_hashes, *, project_root=None):  # type: ignore[no-untyped-def]
        return None

    def _accept_terminal_violation(  # type: ignore[no-untyped-def]
        state,
        *,
        project_root,
        campaign_path=None,
        serialized_state_bytes=None,
    ):
        if (
            str(state.get("final_status")) == RUN_STATUS_CERTIFIED
            and isinstance(state.get("final_result"), dict)
            and state.get("terminal_frontier_evidence") is not None
        ):
            return None
        return "terminal_certified_authority_checkpoint_missing"

    monkeypatch.setattr(
        delivery_manifest_module,
        "validate_exact_campaign_resume_state",
        _accept_resume_state,
    )
    monkeypatch.setattr(
        delivery_manifest_module,
        "terminal_certified_final_result_violation_for_project",
        _accept_terminal_violation,
    )
    monkeypatch.setattr(
        certified_surface_module,
        "validate_exact_campaign_resume_state",
        _accept_resume_state,
    )
    monkeypatch.setattr(
        certified_surface_module,
        "has_valid_terminal_full_frontier_certified_evidence_for_project",
        lambda state, *, project_root, campaign_path=None, serialized_state_bytes=None: (
            has_terminal_full_frontier_certified_evidence(state)
        ),
    )


def test_delivery_manifest_exports_best_certified_result_and_repo_relative_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, facility_pools = _build_manifest_project(tmp_path / "delivery_manifest_best")
    _install_certified_manifest_test_replay(monkeypatch, project_root=project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={
            "ghost_pick": {"pose_idx": 1, "pose_id": "ghost_anchor::1,0", "anchor": {"x": 1, "y": 0}, "facility_type": "ghost_rect"},
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
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": {
            "tiny_001": {
                "pose_idx": 0,
                "pose_id": "tiny_pose_0",
                "anchor": {"x": 0, "y": 0},
                "facility_type": "tiny_facility",
            }
        },
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    best_result = campaign.state["final_result"]
    assert best_result is not None
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=best_result,
        facility_pools=facility_pools,
    )
    persist_canonical_blueprint_for_test(project_root, blueprint_payload)
    (project_root / "data" / "checkpoints" / "benders_cuts.jsonl").write_text(
        '{"schema_version": 2}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="publish_verified_certified_delivery_surface"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )
    assert not delivery_manifest_output_path(project_root).exists()

    payload = build_certified_delivery_manifest(
        project_root=project_root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
    )
    output_path = delivery_manifest_output_path(project_root)
    _write_json(output_path, payload)

    assert output_path == delivery_manifest_output_path(project_root)
    assert payload["campaign"]["solve_mode"] == "certified_exact"
    assert payload["campaign"]["final_status"] == RUN_STATUS_CERTIFIED
    assert payload["best_certified_result"]["ghost_rect"] == {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0}
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


def test_unchecked_certified_surface_writer_is_not_module_importable() -> None:
    assert not hasattr(
        certified_surface_module,
        "_write_certified_final_solution_and_blueprint_unchecked",
    )


def test_generic_blueprint_writer_rejects_canonical_certified_path(
    tmp_path: Path,
) -> None:
    from src.io.serializer import write_blueprint_payload

    project_root, facility_pools = _build_manifest_project(tmp_path / "blueprint_writer_direct")
    result = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": {
            "tiny_001": {
                "pose_idx": 0,
                "pose_id": "tiny_pose_0",
                "anchor": {"x": 0, "y": 0},
                "facility_type": "tiny_facility",
            }
        },
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=result,
        facility_pools=facility_pools,
    )

    with pytest.raises(ValueError, match="verified certified publisher"):
        write_blueprint_payload(blueprint_output_path(project_root), blueprint_payload)
    assert not blueprint_output_path(project_root).exists()


def test_delivery_manifest_rejects_chameleon_mapping_that_skips_disk_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, facility_pools = _build_manifest_project(tmp_path / "delivery_manifest_chameleon")
    _install_certified_manifest_test_replay(monkeypatch, project_root=project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={
            "ghost_pick": {
                "pose_idx": 1,
                "pose_id": "ghost_anchor::1,0",
                "anchor": {"x": 1, "y": 0},
                "facility_type": "ghost_rect",
            },
            "tiny_001": {
                "pose_idx": 0,
                "pose_id": "tiny_pose_0",
                "anchor": {"x": 0, "y": 0},
                "facility_type": "tiny_facility",
            },
        },
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": {
            "tiny_001": {
                "pose_idx": 0,
                "pose_id": "tiny_pose_0",
                "anchor": {"x": 0, "y": 0},
                "facility_type": "tiny_facility",
            }
        },
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    best_result = campaign.state["final_result"]
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=best_result,
        facility_pools=facility_pools,
    )
    persist_canonical_blueprint_for_test(project_root, blueprint_payload)

    class ChameleonCampaignState(dict):
        def __init__(self) -> None:
            super().__init__(
                {
                    "solve_mode": "certified_exact",
                    "declare_mode": "strict",
                    "final_status": "CANDIDATE_PROPOSED",
                    "last_stop_reason": {
                        "reason": "search_exhausted_all_candidates",
                        "status": "CANDIDATE_PROPOSED",
                    },
                    "final_result": None,
                }
            )
            self._armed = False

        def get(self, key: object, default: object = None) -> object:
            if key == "final_status" and not self._armed:
                self._armed = True
                return "CANDIDATE_PROPOSED"
            if self._armed and isinstance(key, str) and key in campaign.state:
                return campaign.state.get(key, default)
            return super().get(key, default)

    with pytest.raises(ValueError, match="disk checkpoint authority"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=ChameleonCampaignState(),
            campaign_path=campaign.path,
        )
    assert not delivery_manifest_output_path(project_root).exists()


def test_v96_certified_surface_rejects_manifest_under_symlinked_solutions_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, facility_pools = _build_manifest_project(tmp_path / "delivery_manifest_parent_symlink")
    _install_certified_manifest_test_replay(monkeypatch, project_root=project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={
            "ghost_pick": {"pose_idx": 1, "pose_id": "ghost_anchor::1,0", "anchor": {"x": 1, "y": 0}, "facility_type": "ghost_rect"},
            "tiny_001": {
                "pose_idx": 0,
                "pose_id": "tiny_pose_0",
                "anchor": {"x": 0, "y": 0},
                "facility_type": "tiny_facility",
            },
        },
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": {
            "tiny_001": {
                "pose_idx": 0,
                "pose_id": "tiny_pose_0",
                "anchor": {"x": 0, "y": 0},
                "facility_type": "tiny_facility",
            }
        },
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    best_result = campaign.state["final_result"]
    assert best_result is not None
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=best_result,
        facility_pools=facility_pools,
    )
    persist_canonical_blueprint_for_test(project_root, blueprint_payload)
    (project_root / "data" / "checkpoints" / "benders_cuts.jsonl").write_text(
        '{"schema_version": 2}\n',
        encoding="utf-8",
    )
    payload = build_certified_delivery_manifest(
        project_root=project_root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
    )
    _write_json(delivery_manifest_output_path(project_root), payload)

    external_solutions_dir = tmp_path / "external_solutions_authority"
    shutil.move(str(project_root / "data" / "solutions"), str(external_solutions_dir))
    (project_root / "data" / "solutions").symlink_to(
        external_solutions_dir,
        target_is_directory=True,
    )

    verdict = verify_certified_delivery_surface(
        project_root=project_root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
    )

    assert verdict.publishable is False
    assert verdict.delivery_manifest_regular_file is False
    assert verdict.blocked_reason == "delivery_artifacts_not_current:ValueError"


def test_delivery_manifest_rejects_terminal_infeasible_without_replayable_evidence(
    tmp_path: Path,
) -> None:
    project_root, _facility_pools = _build_manifest_project(tmp_path / "delivery_manifest_no_best")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    campaign.mark_campaign_stopped("search_exhausted_all_candidates", status=RUN_STATUS_INFEASIBLE)
    persist_forged_terminal_certified_state(campaign)

    with pytest.raises(ValueError, match="exhausted strict candidate frontier"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )

    assert not delivery_manifest_output_path(project_root).exists()


def test_delivery_manifest_rejects_best_effort_final_result(tmp_path: Path) -> None:
    project_root, _facility_pools = _build_manifest_project(tmp_path / "delivery_manifest_best_effort")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={"tiny_001": {"pose_idx": 0}, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": {"tiny_001": {"pose_idx": 0}},
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    campaign.state["final_status"] = RUN_STATUS_CERTIFIED
    campaign.state["declare_mode"] = "best_effort"

    with pytest.raises(ValueError, match="strict declare_mode"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )

def test_delivery_manifest_rejects_certified_status_without_terminal_frontier_evidence(
    tmp_path: Path,
) -> None:
    project_root, _facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_missing_final_result"
    )
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    _forge_legacy_terminal_certified_stop(campaign)
    persist_forged_terminal_certified_state(campaign)

    with pytest.raises(ValueError, match="terminal final_result evidence"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_delivery_manifest_rejects_stale_certified_final_result_without_terminal_frontier_evidence(
    tmp_path: Path,
) -> None:
    project_root, _facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_stale_final_result"
    )
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={"tiny_001": {"facility_type": "tiny_facility", "pose_idx": 0}, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": {"tiny_001": {"facility_type": "tiny_facility", "pose_idx": 0}},
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    campaign.mark_campaign_stopped("candidate_returned_unknown", status=RUN_STATUS_UNKNOWN)
    campaign.state["final_status"] = RUN_STATUS_CERTIFIED
    persist_forged_terminal_certified_state(campaign)

    with pytest.raises(ValueError, match="exhausted strict candidate frontier"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_v79_delivery_manifest_rejects_non_instance_placement_solution(
    tmp_path: Path,
) -> None:
    # V79: 非 instance 形状的 placement_solution 无法反查回 facility_pools,
    # terminal certified 发布必须 fail-closed 而不是静默跳过深校验。
    project_root, facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_non_instance_solution"
    )
    freeform_solution = {"freeform": {"comment": "not a pose pick"}}
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution=freeform_solution,
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": freeform_solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    # V83: 非 project-bound 的 terminal final_result 在 best_result/export
    # 入口更早 fail-closed；delivery manifest 不应再把它推进到 artifact 比对层。
    assert campaign.best_certified_result() is None

    with pytest.raises(
        ValueError,
        match="terminal_certified_final_result_solution_missing_mandatory_instance",
    ):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_v68_delivery_manifest_rejects_best_result_before_delivery_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, _facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_missing_export_artifacts"
    )
    _install_certified_manifest_test_replay(monkeypatch, project_root=project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**solution, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    with pytest.raises(ValueError, match="exported delivery artifacts"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_v69_delivery_manifest_rejects_stale_final_solution_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_stale_final_solution_artifact"
    )
    _install_certified_manifest_test_replay(monkeypatch, project_root=project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**solution, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    best_result = campaign.state["final_result"]
    assert best_result is not None
    _write_json(
        project_root / "data" / "solutions" / "final_solution.json",
        {
            "ghost_rect": {"w": 2, "h": 1, "area": 2},
            "placement_solution": {},
            "search_status": RUN_STATUS_CERTIFIED,
            "search_stats": {"campaign_resumed": False, "stale": True},
        },
    )
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=best_result,
        facility_pools=facility_pools,
    )
    persist_canonical_blueprint_for_test(project_root, blueprint_payload)

    with pytest.raises(ValueError, match="final_solution artifact to match terminal final_result"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_v69_delivery_manifest_rejects_stale_optimal_blueprint_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_stale_blueprint_artifact"
    )
    _install_certified_manifest_test_replay(monkeypatch, project_root=project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**solution, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    best_result = campaign.state["final_result"]
    assert best_result is not None
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    stale_blueprint_result = dict(best_result)
    stale_blueprint_result["ghost_rect"] = {"w": 2, "h": 1, "area": 2, "anchor_x": 0, "anchor_y": 0}
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=stale_blueprint_result,
        facility_pools=facility_pools,
    )
    persist_canonical_blueprint_for_test(project_root, blueprint_payload)

    with pytest.raises(ValueError, match="optimal_blueprint artifact to match terminal final_result"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_v70_delivery_manifest_accepts_master_solution_metadata_not_in_blueprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_master_metadata_fields"
    )
    _install_certified_manifest_test_replay(monkeypatch, project_root=project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    solution = {
        "tiny_001": {
            "instance_id": "tiny_001",
            "facility_type": "tiny_facility",
            "operation_type": "build",
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_mode": "certified_exact",
        }
    }
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**solution, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    best_result = campaign.state["final_result"]
    assert best_result is not None
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=best_result,
        facility_pools=facility_pools,
    )
    persist_canonical_blueprint_for_test(project_root, blueprint_payload)

    payload = build_certified_delivery_manifest(
        project_root=project_root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
    )

    assert payload["best_certified_result"]["ghost_rect"] == {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0}


def test_v70_delivery_manifest_rejects_non_integer_blueprint_score(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_non_integer_blueprint_score"
    )
    _install_certified_manifest_test_replay(monkeypatch, project_root=project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**solution, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    best_result = campaign.state["final_result"]
    assert best_result is not None
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=best_result,
        facility_pools=facility_pools,
    )
    persist_canonical_blueprint_for_test(project_root, blueprint_payload)
    blueprint_path = blueprint_output_path(project_root)
    blueprint_payload = json.loads(blueprint_path.read_text(encoding="utf-8"))
    blueprint_payload["objective_achieved"]["empty_rect"]["score"] = 1.49
    _write_json(blueprint_path, blueprint_payload)

    with pytest.raises(ValueError, match="optimal_blueprint artifact to match terminal final_result"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )

def test_v71_delivery_manifest_rejects_stale_exact_artifact_hash_before_best_result(
    tmp_path: Path,
) -> None:
    project_root, facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_stale_exact_hash"
    )
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**solution, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    best_result = campaign.state["final_result"]
    assert best_result is not None
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=best_result,
        facility_pools=facility_pools,
    )
    persist_canonical_blueprint_for_test(project_root, blueprint_payload)
    _write_json(
        project_root / "data" / "preprocessed" / "generic_io_requirements.json",
        {
            "required_generic_outputs": {},
            "required_generic_inputs": {},
            "stale_after_campaign_marker": 1,
        },
    )

    with pytest.raises(ValueError, match="resume-compatible with current exact artifacts"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_v71_delivery_manifest_rejects_tampered_blueprint_active_ports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_tampered_blueprint_ports"
    )
    _install_certified_manifest_test_replay(monkeypatch, project_root=project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**solution, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    best_result = campaign.state["final_result"]
    assert best_result is not None
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=best_result,
        facility_pools=facility_pools,
    )
    persist_canonical_blueprint_for_test(project_root, blueprint_payload)
    blueprint_path = blueprint_output_path(project_root)
    blueprint_payload = json.loads(blueprint_path.read_text(encoding="utf-8"))
    blueprint_payload["facilities"][0]["active_ports"] = [
        {"type": "input", "x": 9, "y": 9, "dir": "N", "commodity": "stale"}
    ]
    _write_json(blueprint_path, blueprint_payload)

    with pytest.raises(ValueError, match="optimal_blueprint artifact to match terminal final_result"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_v72_delivery_manifest_rejects_blueprint_with_extra_raw_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_blueprint_extra_raw_fields"
    )
    _install_certified_manifest_test_replay(monkeypatch, project_root=project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**solution, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    best_result = campaign.state["final_result"]
    assert best_result is not None
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=best_result,
        facility_pools=facility_pools,
    )
    persist_canonical_blueprint_for_test(project_root, blueprint_payload)
    blueprint_path = blueprint_output_path(project_root)
    blueprint_payload = json.loads(blueprint_path.read_text(encoding="utf-8"))
    blueprint_payload["stale_certified_shadow"] = {
        "ghost_rect": {"w": 2, "h": 1, "area": 2},
        "search_status": RUN_STATUS_CERTIFIED,
    }
    _write_json(blueprint_path, blueprint_payload)

    with pytest.raises(ValueError, match="optimal_blueprint artifact to match terminal final_result"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_v72_manifest_currentness_rejects_extra_metadata_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_extra_metadata_fields"
    )
    _install_certified_manifest_test_replay(monkeypatch, project_root=project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**solution, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    best_result = campaign.state["final_result"]
    assert best_result is not None
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=best_result,
        facility_pools=facility_pools,
    )
    persist_canonical_blueprint_for_test(project_root, blueprint_payload)
    manifest_payload = build_certified_delivery_manifest(
        project_root=project_root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
    )
    manifest_payload["metadata"]["stale_proof_hash"] = "0" * 64

    with pytest.raises(ValueError, match="metadata does not match current contract"):
        validate_certified_delivery_manifest_matches_campaign(
            project_root=project_root,
            delivery_manifest=manifest_payload,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_v72_delivery_manifest_rejects_blueprint_missing_terminal_routing_solution(
    tmp_path: Path,
) -> None:
    project_root, facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_routing_solution_projection"
    )
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }
    routing_solution = [
        {
            "x": 0,
            "y": 0,
            "layer": 0,
            "component_type": "belt",
            "commodity": "test_item",
            "flow_in": ["N"],
            "flow_out": ["E"],
        }
    ]
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**solution, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "routing_solution": routing_solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    assert (
        terminal_certified_final_result_project_precheck_violation(
            campaign.state,
            project_root=project_root,
        )
        == "terminal_certified_final_result_unknown_field:routing_solution"
    )
    assert campaign.best_certified_result() is None

    with pytest.raises(
        ValueError,
        match="terminal_certified_final_result_unknown_field:routing_solution",
    ):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_v74_delivery_manifest_rejects_duplicate_key_final_solution_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_duplicate_final_solution_key"
    )
    _install_certified_manifest_test_replay(monkeypatch, project_root=project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**solution, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED},
        loaded_exact_safe_cut_count=1,
        generated_exact_safe_cut_count=2,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)
    best_result = campaign.state["final_result"]
    assert best_result is not None
    final_solution_path = project_root / "data" / "solutions" / "final_solution.json"
    _write_json(final_solution_path, best_result)
    final_solution_path.write_text(
        final_solution_path.read_text(encoding="utf-8").replace(
            '  "search_status": "CERTIFIED"',
            '  "search_status": "BAD",\n  "search_status": "CERTIFIED"',
            1,
        ),
        encoding="utf-8",
    )
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=best_result,
        facility_pools=facility_pools,
    )
    persist_canonical_blueprint_for_test(project_root, blueprint_payload)

    with pytest.raises(ValueError, match="strict readable JSON final_solution artifact"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )


def test_v77_delivery_manifest_export_rejects_memory_campaign_when_disk_checkpoint_differs(
    tmp_path: Path,
) -> None:
    project_root, facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_writer_disk_authority"
    )
    disk_campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    disk_campaign.mark_campaign_stopped("search_exhausted_all_candidates", status=RUN_STATUS_INFEASIBLE)
    persist_forged_terminal_certified_state(disk_campaign)

    memory_campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=2.0,
        resume=False,
        filename="memory_exact_campaign_state.json",
    )
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }
    memory_campaign.mark_candidate_started(1, 1)
    memory_campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**solution, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    memory_campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(memory_campaign)
    attach_terminal_frontier_evidence(memory_campaign, project_root)

    best_result = memory_campaign.state["final_result"]
    assert best_result is not None
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=best_result,
        facility_pools=facility_pools,
    )
    persist_canonical_blueprint_for_test(project_root, blueprint_payload)

    with pytest.raises(ValueError, match="disk checkpoint authority"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=memory_campaign.state,
            campaign_path=disk_campaign.path,
        )
    assert not delivery_manifest_output_path(project_root).exists()


def test_v77_delivery_manifest_export_rejects_symlink_campaign_checkpoint_for_best_result(
    tmp_path: Path,
) -> None:
    project_root, facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_writer_symlink_checkpoint"
    )
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**solution, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    best_result = campaign.state["final_result"]
    assert best_result is not None
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=best_result,
        facility_pools=facility_pools,
    )
    persist_canonical_blueprint_for_test(project_root, blueprint_payload)
    symlink_path = campaign.path.with_name("symlink_exact_campaign_state.json")
    symlink_path.symlink_to(campaign.path.name)

    with pytest.raises(ValueError, match="regular campaign checkpoint"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=symlink_path,
        )
    assert not delivery_manifest_output_path(project_root).exists()


def test_v78_delivery_manifest_export_rejects_certified_best_result_to_noncanonical_output_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_writer_noncanonical_output"
    )
    _install_certified_manifest_test_replay(monkeypatch, project_root=project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**solution, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    best_result = campaign.state["final_result"]
    assert best_result is not None
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=best_result,
        facility_pools=facility_pools,
    )
    persist_canonical_blueprint_for_test(project_root, blueprint_payload)
    side_output_path = project_root / "data" / "solutions" / "side_certified_manifest.json"

    with pytest.raises(ValueError, match="canonical output path"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
            output_path=side_output_path,
        )
    assert not side_output_path.exists()
    assert not delivery_manifest_output_path(project_root).exists()


def test_v78_write_certified_delivery_manifest_rejects_direct_best_result_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "certified_delivery_manifest.json"
    write_calls: list[object] = []

    def fail_if_called(*args: object, **kwargs: object) -> None:
        write_calls.append((args, kwargs))
        raise AssertionError("manifest writer should reject CERTIFIED payload before write")

    monkeypatch.setattr(delivery_manifest_module, "atomic_write_json", fail_if_called)
    with pytest.raises(ValueError, match="direct certified delivery manifest writes"):
        write_certified_delivery_manifest(
            output_path,
            {
                "metadata": {"version": "1.0.0"},
                "campaign": {"final_status": RUN_STATUS_CERTIFIED},
                "best_certified_result": {"search_status": RUN_STATUS_CERTIFIED},
                "artifacts": {},
            },
        )
    assert write_calls == []
    assert not output_path.exists()


def test_v78_delivery_manifest_export_rejects_symlink_canonical_output_for_best_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, facility_pools = _build_manifest_project(
        tmp_path / "delivery_manifest_writer_symlink_output"
    )
    _install_certified_manifest_test_replay(monkeypatch, project_root=project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=2.0, resume=False)
    solution = {
        "tiny_001": {
            "pose_idx": 0,
            "pose_id": "tiny_pose_0",
            "anchor": {"x": 0, "y": 0},
            "facility_type": "tiny_facility",
        }
    }
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution={**solution, **_V89_GHOST_PICK},
        proof_summary={"master_status": RUN_STATUS_CERTIFIED, "mode": "certified_exact"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": solution,
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    _forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(campaign, project_root)
    persist_forged_terminal_certified_state(campaign)

    best_result = campaign.state["final_result"]
    assert best_result is not None
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    blueprint_payload = build_blueprint_payload_from_certified_result(
        result=best_result,
        facility_pools=facility_pools,
    )
    persist_canonical_blueprint_for_test(project_root, blueprint_payload)
    canonical_manifest_path = delivery_manifest_output_path(project_root)
    shadow_path = canonical_manifest_path.with_name("shadow_manifest.json")
    shadow_path.write_text("{}", encoding="utf-8")
    canonical_manifest_path.symlink_to(shadow_path.name)

    with pytest.raises(ValueError, match="regular canonical delivery manifest output"):
        export_certified_delivery_manifest(
            project_root=project_root,
            campaign_state=campaign.state,
            campaign_path=campaign.path,
        )
    assert canonical_manifest_path.is_symlink()
