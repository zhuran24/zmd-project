"""Tests for cut provenance（切平面来源追踪测试）."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from src.tests.certified_frontier_helpers import persist_forged_terminal_certified_state
from src.models.cut_manager import BendersCut, CutManager
from src.search.benders_loop import collect_certification_blockers
from src.search.exact_campaign import ExactCampaign
from src.tests.certified_frontier_helpers import forge_legacy_terminal_certified_stop

import pytest


def _write_minimal_exact_campaign_artifacts(project_root: Path) -> None:
    (project_root / "data" / "preprocessed").mkdir(parents=True)
    (project_root / "rules").mkdir(parents=True)
    (project_root / "data" / "preprocessed" / "mandatory_exact_instances.json").write_text(
        "[]", encoding="utf-8"
    )
    (project_root / "data" / "preprocessed" / "candidate_placements.json").write_text(
        '{"facility_pools": {}}', encoding="utf-8"
    )
    (project_root / "data" / "preprocessed" / "generic_io_requirements.json").write_text(
        '{"required_generic_outputs": {}, "required_generic_inputs": {}}', encoding="utf-8"
    )
    (project_root / "rules" / "canonical_rules.json").write_text(
        json.dumps({"globals": {"grid": {"width": 2, "height": 1}, "empty_rectangle": {"objective": "max_lex_area_min_side", "min_side_admissibility": 1}}}),
        encoding="utf-8",
    )
    (project_root / "rules" / "preprocess_plan.json").write_text(
        '{"utility_operations": {}}', encoding="utf-8"
    )


def _condition_required_power_cut_payload(
    campaign: ExactCampaign,
    *,
    condition_set: Mapping[str, int] | None = None,
    metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 3,
        "cut_type": "power_subproblem_infeasible_nogood",
        "conflict_set": {"machine_001": 0},
        "iteration": 1,
        "metadata": dict(
            metadata
            or {
                "kind": "power_subproblem_ghost_conditioned_nogood",
                "ghost_rect_idx": 0,
                "ghost_anchor": {"x": 0, "y": 0},
            }
        ),
        "source_mode": "certified_exact",
        "exact_safe": True,
        "artifact_hashes": campaign.artifact_hashes,
        "proof_stage": "power_placement_subproblem",
        "binding_exhausted": False,
        "routing_exhausted": False,
        "proof_summary": {},
        "created_at": "2026-03-15T00:00:00Z",
    }
    if condition_set is not None:
        payload["condition_set"] = dict(condition_set)
    return payload


def test_certified_exact_rejects_legacy_cut_file(tmp_path: Path) -> None:
    legacy_path = tmp_path / "cuts_legacy.json"
    legacy_path.write_text(
        json.dumps(
            [
                {
                    "cut_type": "topo",
                    "conflict_set": {"power_pole_599": 599},
                    "iteration": 1,
                    "metadata": {},
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    manager = CutManager(
        checkpoint_dir=tmp_path / "checkpoints",
        solve_mode="certified_exact",
        current_hashes={"candidate_placements": "abc", "mandatory_exact_instances": "def"},
    )
    assert manager.checkpoint_dir == tmp_path / "checkpoints"
    stats = manager.load(legacy_path)
    assert stats["loaded"] == 0
    assert stats["rejected_legacy"] == 1


def test_benders_cut_from_dict_rejects_string_exact_safe_flag() -> None:
    with pytest.raises(ValueError, match="exact_safe"):
        BendersCut.from_dict(
            {
                "schema_version": 2,
                "cut_type": "routing_exhausted_nogood",
                "conflict_set": {"pose_optional::power_pole::pole_1": 1},
                "iteration": 1,
                "source_mode": "certified_exact",
                "exact_safe": "false",
                "artifact_hashes": {"candidate_placements": "abc"},
                "proof_stage": "routing",
                "binding_exhausted": True,
                "routing_exhausted": True,
                "proof_summary": {},
                "created_at": "2026-03-15T00:00:00Z",
            }
        )


def test_benders_cut_from_dict_rejects_string_conflict_pose_index() -> None:
    with pytest.raises(ValueError, match="conflict_set"):
        BendersCut.from_dict(
            {
                "schema_version": 2,
                "cut_type": "routing_exhausted_nogood",
                "conflict_set": {"pose_optional::power_pole::pole_1": "1"},
                "iteration": 1,
                "source_mode": "certified_exact",
                "exact_safe": True,
                "artifact_hashes": {"candidate_placements": "abc"},
                "proof_stage": "routing",
                "binding_exhausted": True,
                "routing_exhausted": True,
                "proof_summary": {},
                "created_at": "2026-03-15T00:00:00Z",
            }
        )


def test_benders_cut_from_dict_rejects_bool_conflict_pose_index() -> None:
    with pytest.raises(ValueError, match="conflict_set"):
        BendersCut.from_dict(
            {
                "schema_version": 2,
                "cut_type": "routing_exhausted_nogood",
                "conflict_set": {"pose_optional::power_pole::pole_1": True},
                "iteration": 1,
                "source_mode": "certified_exact",
                "exact_safe": True,
                "artifact_hashes": {"candidate_placements": "abc"},
                "proof_stage": "routing",
                "binding_exhausted": True,
                "routing_exhausted": True,
                "proof_summary": {},
                "created_at": "2026-03-15T00:00:00Z",
            }
        )


def test_benders_cut_from_dict_rejects_bool_condition_anchor_index() -> None:
    with pytest.raises(ValueError, match="condition_set"):
        BendersCut.from_dict(
            {
                "schema_version": 2,
                "cut_type": "routing_exhausted_nogood",
                "conflict_set": {"pose_optional::power_pole::pole_1": 1},
                "iteration": 1,
                "source_mode": "certified_exact",
                "exact_safe": True,
                "artifact_hashes": {"candidate_placements": "abc"},
                "proof_stage": "routing",
                "binding_exhausted": True,
                "routing_exhausted": True,
                "proof_summary": {},
                "condition_set": {"ghost_anchor::(0,0)": True},
                "created_at": "2026-03-15T00:00:00Z",
            }
        )


def test_benders_cut_from_dict_rejects_condition_required_power_cut_without_condition_set() -> None:
    with pytest.raises(ValueError, match="condition_set is required"):
        BendersCut.from_dict(
            {
                "schema_version": 3,
                "cut_type": "power_subproblem_infeasible_nogood",
                "conflict_set": {"machine_001": 0},
                "iteration": 1,
                "metadata": {"kind": "power_subproblem_ghost_conditioned_nogood"},
                "source_mode": "certified_exact",
                "exact_safe": True,
                "artifact_hashes": {"candidate_placements": "abc"},
                "proof_stage": "power_placement_subproblem",
                "binding_exhausted": False,
                "routing_exhausted": False,
                "proof_summary": {},
                "created_at": "2026-03-15T00:00:00Z",
            }
        )


def test_benders_cut_to_dict_rejects_condition_required_power_cut_without_condition_set() -> None:
    cut = BendersCut(
        schema_version=3,
        cut_type="power_subproblem_infeasible_nogood",
        conflict_set={"machine_001": 0},
        iteration=1,
        metadata={"kind": "power_subproblem_ghost_conditioned_nogood"},
        source_mode="certified_exact",
        exact_safe=True,
        artifact_hashes={"candidate_placements": "abc"},
        proof_stage="power_placement_subproblem",
        binding_exhausted=False,
        routing_exhausted=False,
        proof_summary={},
    )

    with pytest.raises(ValueError, match="condition_set is required"):
        cut.to_dict()


def test_benders_cut_from_dict_rejects_condition_required_power_cut_with_unknown_condition_key() -> None:
    with pytest.raises(ValueError, match="condition_set"):
        BendersCut.from_dict(
            {
                "schema_version": 3,
                "cut_type": "power_subproblem_infeasible_nogood",
                "conflict_set": {"machine_001": 0},
                "iteration": 1,
                "metadata": {
                    "kind": "power_subproblem_ghost_conditioned_nogood",
                    "ghost_rect_idx": 0,
                    "ghost_anchor": {"x": 0, "y": 0},
                },
                "source_mode": "certified_exact",
                "exact_safe": True,
                "artifact_hashes": {"candidate_placements": "abc"},
                "proof_stage": "power_placement_subproblem",
                "binding_exhausted": False,
                "routing_exhausted": False,
                "proof_summary": {},
                "condition_set": {"unknown_condition_kind::(0,0)": 0},
                "created_at": "2026-03-15T00:00:00Z",
            }
        )


def test_benders_cut_from_dict_rejects_condition_required_power_cut_metadata_mismatch() -> None:
    with pytest.raises(ValueError, match="metadata.ghost_anchor"):
        BendersCut.from_dict(
            {
                "schema_version": 3,
                "cut_type": "power_subproblem_infeasible_nogood",
                "conflict_set": {"machine_001": 0},
                "iteration": 1,
                "metadata": {
                    "kind": "power_subproblem_ghost_conditioned_nogood",
                    "ghost_rect_idx": 0,
                    "ghost_anchor": {"x": 1, "y": 0},
                },
                "source_mode": "certified_exact",
                "exact_safe": True,
                "artifact_hashes": {"candidate_placements": "abc"},
                "proof_stage": "power_placement_subproblem",
                "binding_exhausted": False,
                "routing_exhausted": False,
                "proof_summary": {},
                "condition_set": {"ghost_anchor::(0,0)": 0},
                "created_at": "2026-03-15T00:00:00Z",
            }
        )


def test_benders_cut_from_dict_rejects_condition_required_power_cut_rect_idx_mismatch() -> None:
    with pytest.raises(ValueError, match="metadata.ghost_rect_idx"):
        BendersCut.from_dict(
            {
                "schema_version": 3,
                "cut_type": "power_subproblem_infeasible_nogood",
                "conflict_set": {"machine_001": 0},
                "iteration": 1,
                "metadata": {
                    "kind": "power_subproblem_ghost_conditioned_nogood",
                    "ghost_rect_idx": 1,
                    "ghost_anchor": {"x": 0, "y": 0},
                },
                "source_mode": "certified_exact",
                "exact_safe": True,
                "artifact_hashes": {"candidate_placements": "abc"},
                "proof_stage": "power_placement_subproblem",
                "binding_exhausted": False,
                "routing_exhausted": False,
                "proof_summary": {},
                "condition_set": {"ghost_anchor::(0,0)": 0},
                "created_at": "2026-03-15T00:00:00Z",
            }
        )


def test_benders_cut_from_dict_rejects_noncanonical_ghost_anchor_condition_keys() -> None:
    bad_keys = [
        "ghost_anchor::( 0,0)",
        "ghost_anchor::(0,0 )",
        "ghost_anchor::(+0,0)",
        "ghost_anchor::(-1,0)",
        "ghost_anchor::(01,0)",
        "ghost_anchor::(1_000,0)",
        "ghost_anchor::(2147483648,0)",
        "ghost_anchor::(0,0,extra)",
    ]
    for bad_key in bad_keys:
        with pytest.raises(ValueError, match="condition_set"):
            BendersCut.from_dict(
                {
                    "schema_version": 3,
                    "cut_type": "power_subproblem_infeasible_nogood",
                    "conflict_set": {"machine_001": 0},
                    "iteration": 1,
                    "metadata": {
                        "kind": "power_subproblem_ghost_conditioned_nogood",
                        "ghost_rect_idx": 0,
                        "ghost_anchor": {"x": 0, "y": 0},
                    },
                    "source_mode": "certified_exact",
                    "exact_safe": True,
                    "artifact_hashes": {"candidate_placements": "abc"},
                    "proof_stage": "power_placement_subproblem",
                    "binding_exhausted": False,
                    "routing_exhausted": False,
                    "proof_summary": {},
                    "condition_set": {bad_key: 0},
                    "created_at": "2026-03-15T00:00:00Z",
                }
            )


def test_collect_certification_blockers_rejects_non_bool_exact_safe_object() -> None:
    cut = BendersCut(
        cut_type="routing_exhausted_nogood",
        conflict_set={"pose_optional::power_pole::pole_1": 1},
        iteration=1,
        source_mode="certified_exact",
        exact_safe="false",  # type: ignore[arg-type]
        artifact_hashes={"candidate_placements": "abc"},
        proof_stage="routing",
        binding_exhausted=True,
        routing_exhausted=True,
    )
    blockers = collect_certification_blockers(
        solve_mode="certified_exact",
        loaded_cuts=[cut],
        current_hashes={"candidate_placements": "abc"},
    )
    assert any(item["code"] == "cut_not_exact_safe" for item in blockers)


def test_collect_certification_blockers_rejects_bool_conflict_pose_index() -> None:
    cut = BendersCut(
        cut_type="routing_exhausted_nogood",
        conflict_set={"pose_optional::power_pole::pole_1": True},
        iteration=1,
        source_mode="certified_exact",
        exact_safe=True,
        artifact_hashes={"candidate_placements": "abc"},
        proof_stage="routing",
        binding_exhausted=True,
        routing_exhausted=True,
    )
    blockers = collect_certification_blockers(
        solve_mode="certified_exact",
        loaded_cuts=[cut],
        current_hashes={"candidate_placements": "abc"},
    )
    assert any(item["code"] == "cut_conflict_set_malformed" for item in blockers)


def test_exact_campaign_state_persists_full_master_domain_contract(tmp_path: Path) -> None:
    project_root = tmp_path / "campaign_master_domain_contract"
    _write_minimal_exact_campaign_artifacts(project_root)

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)

    assert campaign.state["master_domain_contract"] == {
        "schema_version": 1,
        "ghost_anchor_domain": "full_unfiltered",
        "ghost_anchor_filter": None,
    }


def test_exact_campaign_resume_rejects_filtered_master_domain_contract(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "campaign_filtered_master_domain_contract"
    _write_minimal_exact_campaign_artifacts(project_root)

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.state["master_domain_contract"] = {
        "schema_version": 1,
        "ghost_anchor_domain": "filtered",
        "ghost_anchor_filter": [[0, 0]],
    }
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "master_domain_contract_invalid"


def test_exact_campaign_resume_rejects_float_state_schema_version(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "campaign_float_state_schema_version"
    _write_minimal_exact_campaign_artifacts(project_root)

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.state["schema_version"] = 4.0
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "schema_version_mismatch"


def test_exact_campaign_resume_rejects_float_proof_summary_schema_version(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "campaign_float_proof_summary_schema_version"
    _write_minimal_exact_campaign_artifacts(project_root)

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.state["proof_summary_schema_version"] = 1.0
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "proof_summary_schema_version_mismatch"


def test_exact_campaign_resume_rejects_bool_generated_cut_count(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "campaign_bool_generated_cut_count"
    _write_minimal_exact_campaign_artifacts(project_root)

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        "UNKNOWN",
        exact_safe_cuts=[],
        proof_summary={"master_status": "UNKNOWN"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["candidates"]["1x1"]["generated_exact_safe_cut_count"] = True
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "candidate_invalid_count:1x1"


def test_exact_campaign_resume_rejects_malformed_exact_safe_cut(tmp_path: Path) -> None:
    project_root = tmp_path / "campaign_malformed_exact_safe"
    _write_minimal_exact_campaign_artifacts(project_root)

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        "UNKNOWN",
        exact_safe_cuts=[
            {
                "schema_version": 2,
                "cut_type": "routing_exhausted_nogood",
                "conflict_set": {"pose_optional::power_pole::pole_1": 1},
                "iteration": 1,
                "source_mode": "certified_exact",
                "exact_safe": "false",
                "artifact_hashes": campaign.artifact_hashes,
                "proof_stage": "routing",
                "binding_exhausted": True,
                "routing_exhausted": True,
                "proof_summary": {},
                "created_at": "2026-03-15T00:00:00Z",
            }
        ],
        proof_summary={"master_status": "UNKNOWN"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=1,
    )
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "candidate_invalid_exact_safe_cut:1x1:0"


def test_exact_campaign_resume_rejects_bool_conflict_pose_index(tmp_path: Path) -> None:
    project_root = tmp_path / "campaign_bool_conflict_pose"
    _write_minimal_exact_campaign_artifacts(project_root)

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        "UNKNOWN",
        exact_safe_cuts=[
            {
                "schema_version": 2,
                "cut_type": "routing_exhausted_nogood",
                "conflict_set": {"pose_optional::power_pole::pole_1": True},
                "iteration": 1,
                "source_mode": "certified_exact",
                "exact_safe": True,
                "artifact_hashes": campaign.artifact_hashes,
                "proof_stage": "routing",
                "binding_exhausted": True,
                "routing_exhausted": True,
                "proof_summary": {},
                "created_at": "2026-03-15T00:00:00Z",
            }
        ],
        proof_summary={"master_status": "UNKNOWN"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=1,
    )
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "candidate_invalid_exact_safe_cut:1x1:0"


def test_exact_campaign_resume_rejects_condition_required_power_cut_without_condition_set(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "campaign_missing_condition_power_cut"
    _write_minimal_exact_campaign_artifacts(project_root)

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        "UNKNOWN",
        exact_safe_cuts=[
            {
                "schema_version": 3,
                "cut_type": "power_subproblem_infeasible_nogood",
                "conflict_set": {"machine_001": 0},
                "iteration": 1,
                "metadata": {"kind": "power_subproblem_ghost_conditioned_nogood"},
                "source_mode": "certified_exact",
                "exact_safe": True,
                "artifact_hashes": campaign.artifact_hashes,
                "proof_stage": "power_placement_subproblem",
                "binding_exhausted": False,
                "routing_exhausted": False,
                "proof_summary": {},
                "created_at": "2026-03-15T00:00:00Z",
            }
        ],
        proof_summary={"master_status": "UNKNOWN"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=1,
    )
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "candidate_invalid_exact_safe_cut:1x1:0"


def test_exact_campaign_resume_rejects_condition_required_power_cut_with_unknown_condition_key(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "campaign_unknown_condition_power_cut"
    _write_minimal_exact_campaign_artifacts(project_root)

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        "INFEASIBLE",
        exact_safe_cuts=[
            _condition_required_power_cut_payload(
                campaign,
                condition_set={"unknown_condition_kind::(0,0)": 0},
            )
        ],
        proof_summary={"master_status": "INFEASIBLE"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=1,
    )
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "candidate_invalid_exact_safe_cut:1x1:0"


def test_exact_campaign_resume_rejects_condition_required_power_cut_metadata_mismatch(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "campaign_condition_metadata_mismatch_power_cut"
    _write_minimal_exact_campaign_artifacts(project_root)

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        "INFEASIBLE",
        exact_safe_cuts=[
            _condition_required_power_cut_payload(
                campaign,
                condition_set={"ghost_anchor::(0,0)": 0},
                metadata={
                    "kind": "power_subproblem_ghost_conditioned_nogood",
                    "ghost_rect_idx": 0,
                    "ghost_anchor": {"x": 1, "y": 0},
                },
            )
        ],
        proof_summary={"master_status": "INFEASIBLE"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=1,
    )
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "candidate_invalid_exact_safe_cut:1x1:0"


def test_exact_campaign_resume_rejects_condition_required_power_cut_rect_idx_not_resolver_supported(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "campaign_condition_rect_idx_not_resolver_supported"
    _write_minimal_exact_campaign_artifacts(project_root)

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        "INFEASIBLE",
        exact_safe_cuts=[
            _condition_required_power_cut_payload(
                campaign,
                condition_set={"ghost_anchor::(1,0)": 0},
                metadata={
                    "kind": "power_subproblem_ghost_conditioned_nogood",
                    "ghost_rect_idx": 0,
                    "ghost_anchor": {"x": 1, "y": 0},
                },
            )
        ],
        proof_summary={"master_status": "INFEASIBLE"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=1,
    )
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "candidate_invalid_exact_safe_cut:1x1:0"


def test_exact_campaign_resume_accepts_condition_required_power_cut_with_resolver_supported_anchor(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "campaign_condition_rect_idx_resolver_supported"
    _write_minimal_exact_campaign_artifacts(project_root)

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        "INFEASIBLE",
        exact_safe_cuts=[
            _condition_required_power_cut_payload(
                campaign,
                condition_set={"ghost_anchor::(1,0)": 1},
                metadata={
                    "kind": "power_subproblem_ghost_conditioned_nogood",
                    "ghost_rect_idx": 1,
                    "ghost_anchor": {"x": 1, "y": 0},
                },
            )
        ],
        proof_summary={"master_status": "INFEASIBLE"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=1,
    )
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is True
    assert resumed.reset_reason is None


def test_exact_campaign_resume_rejects_condition_required_power_cut_anchor_outside_domain(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "campaign_condition_anchor_outside_domain"
    _write_minimal_exact_campaign_artifacts(project_root)

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        "INFEASIBLE",
        exact_safe_cuts=[
            _condition_required_power_cut_payload(
                campaign,
                condition_set={"ghost_anchor::(2,0)": 0},
                metadata={
                    "kind": "power_subproblem_ghost_conditioned_nogood",
                    "ghost_rect_idx": 0,
                    "ghost_anchor": {"x": 2, "y": 0},
                },
            )
        ],
        proof_summary={"master_status": "INFEASIBLE"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=1,
    )
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "candidate_invalid_exact_safe_cut:1x1:0"


def test_cut_manager_load_rejects_duplicate_exact_safe_key(tmp_path: Path) -> None:
    exact_path = tmp_path / "cuts_duplicate_key.json"
    exact_path.write_text(
        r'''{
  "schema_version": 2,
  "cuts": [
    {
      "schema_version": 2,
      "cut_type": "routing_exhausted_nogood",
      "conflict_set": {"pose_optional::power_pole::pole_1": 1},
      "iteration": 1,
      "source_mode": "certified_exact",
      "exact_safe": false,
      "exact_safe": true,
      "artifact_hashes": {"candidate_placements": "abc"},
      "proof_stage": "routing",
      "binding_exhausted": true,
      "routing_exhausted": true,
      "proof_summary": {},
      "created_at": "2026-03-15T00:00:00Z"
    }
  ]
}
''',
        encoding="utf-8",
    )

    manager = CutManager(
        checkpoint_dir=tmp_path / "checkpoints",
        solve_mode="certified_exact",
        current_hashes={"candidate_placements": "abc"},
    )
    assert manager.checkpoint_dir == tmp_path / "checkpoints"

    with pytest.raises(ValueError, match="duplicate JSON key"):
        manager.load(exact_path)


def test_cut_manager_load_rejects_json_nan_constant(tmp_path: Path) -> None:
    exact_path = tmp_path / "cuts_nan_constant.json"
    exact_path.write_text(
        '''{
  "schema_version": 2,
  "cuts": [
    {
      "schema_version": 2,
      "cut_type": "routing_exhausted_nogood",
      "conflict_set": {"pose_optional::power_pole::pole_1": 1},
      "iteration": 1,
      "source_mode": "certified_exact",
      "exact_safe": NaN,
      "artifact_hashes": {"candidate_placements": "abc"},
      "proof_stage": "routing",
      "binding_exhausted": true,
      "routing_exhausted": true,
      "proof_summary": {},
      "created_at": "2026-03-15T00:00:00Z"
    }
  ]
}
''',
        encoding="utf-8",
    )

    manager = CutManager(
        checkpoint_dir=tmp_path / "checkpoints",
        solve_mode="certified_exact",
        current_hashes={"candidate_placements": "abc"},
    )
    assert manager.checkpoint_dir == tmp_path / "checkpoints"

    with pytest.raises(ValueError, match="invalid JSON constant"):
        manager.load(exact_path)


def test_exact_campaign_resume_rejects_duplicate_json_key(tmp_path: Path) -> None:
    project_root = tmp_path / "campaign_duplicate_exact_safe"
    (project_root / "data" / "preprocessed").mkdir(parents=True)
    (project_root / "rules").mkdir(parents=True)
    (project_root / "data" / "preprocessed" / "mandatory_exact_instances.json").write_text("[]", encoding="utf-8")
    (project_root / "data" / "preprocessed" / "candidate_placements.json").write_text('{"facility_pools": {}}', encoding="utf-8")
    (project_root / "data" / "preprocessed" / "generic_io_requirements.json").write_text('{"required_generic_outputs": {}, "required_generic_inputs": {}}', encoding="utf-8")
    (project_root / "rules" / "canonical_rules.json").write_text(
        json.dumps({"globals": {"grid": {"width": 2, "height": 1}, "empty_rectangle": {"objective": "max_lex_area_min_side", "min_side_admissibility": 1}}}),
        encoding="utf-8",
    )

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        "UNKNOWN",
        exact_safe_cuts=[
            {
                "schema_version": 2,
                "cut_type": "routing_exhausted_nogood",
                "conflict_set": {"pose_optional::power_pole::pole_1": 1},
                "iteration": 1,
                "source_mode": "certified_exact",
                "exact_safe": True,
                "artifact_hashes": campaign.artifact_hashes,
                "proof_stage": "routing",
                "binding_exhausted": True,
                "routing_exhausted": True,
                "proof_summary": {},
                "created_at": "2026-03-15T00:00:00Z",
            }
        ],
        proof_summary={"master_status": "UNKNOWN"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=1,
    )
    persist_forged_terminal_certified_state(campaign)

    path = campaign.path
    raw = path.read_text(encoding="utf-8")
    path.write_text(
        raw.replace('"exact_safe": true', '"exact_safe": false, "exact_safe": true', 1),
        encoding="utf-8",
    )

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "state_json_invalid"


def test_exact_campaign_resume_rejects_json_nan_constant(tmp_path: Path) -> None:
    project_root = tmp_path / "campaign_nan_exact_safe"
    (project_root / "data" / "preprocessed").mkdir(parents=True)
    (project_root / "rules").mkdir(parents=True)
    (project_root / "data" / "preprocessed" / "mandatory_exact_instances.json").write_text("[]", encoding="utf-8")
    (project_root / "data" / "preprocessed" / "candidate_placements.json").write_text('{"facility_pools": {}}', encoding="utf-8")
    (project_root / "data" / "preprocessed" / "generic_io_requirements.json").write_text('{"required_generic_outputs": {}, "required_generic_inputs": {}}', encoding="utf-8")
    (project_root / "rules" / "canonical_rules.json").write_text(
        json.dumps({"globals": {"grid": {"width": 2, "height": 1}, "empty_rectangle": {"objective": "max_lex_area_min_side", "min_side_admissibility": 1}}}),
        encoding="utf-8",
    )

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        "UNKNOWN",
        exact_safe_cuts=[
            {
                "schema_version": 2,
                "cut_type": "routing_exhausted_nogood",
                "conflict_set": {"pose_optional::power_pole::pole_1": 1},
                "iteration": 1,
                "source_mode": "certified_exact",
                "exact_safe": True,
                "artifact_hashes": campaign.artifact_hashes,
                "proof_stage": "routing",
                "binding_exhausted": True,
                "routing_exhausted": True,
                "proof_summary": {},
                "created_at": "2026-03-15T00:00:00Z",
            }
        ],
        proof_summary={"master_status": "UNKNOWN"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=1,
    )
    persist_forged_terminal_certified_state(campaign)

    path = campaign.path
    raw = path.read_text(encoding="utf-8")
    path.write_text(raw.replace('"exact_safe": true', '"exact_safe": NaN', 1), encoding="utf-8")

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "state_json_invalid"



def test_exact_campaign_resume_rejects_best_effort_final_result(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "campaign_best_effort_final_result"
    _write_minimal_exact_campaign_artifacts(project_root)

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        "CERTIFIED",
        exact_safe_cuts=[],
        solution={"tiny_001": {"pose_idx": 0}},
        proof_summary={"master_status": "CERTIFIED"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    # V63 keeps candidate-level CERTIFIED records as incumbents until the
    # full outer frontier is exhausted.  Exercise the intended invalid state
    # directly: a best-effort campaign must not resume with a final_result
    # that looks like terminal certified export evidence.
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1},
        "placement_solution": {"tiny_001": {"pose_idx": 0}},
        "search_status": "CERTIFIED",
    }
    forge_legacy_terminal_certified_stop(campaign)
    campaign.state["declare_mode"] = "best_effort"
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "final_result_declare_mode_not_strict"


def test_exact_campaign_resume_rejects_missing_declare_mode(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "campaign_missing_declare_mode"
    _write_minimal_exact_campaign_artifacts(project_root)

    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.state.pop("declare_mode")
    persist_forged_terminal_certified_state(campaign)

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "missing_state_field:declare_mode"


def test_certified_exact_loads_only_matching_exact_safe_cuts(tmp_path: Path) -> None:
    exact_path = tmp_path / "cuts_exact.json"
    matching_hashes = {"candidate_placements": "abc", "mandatory_exact_instances": "def"}
    exact_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "cuts": [
                    {
                        "schema_version": 2,
                        "cut_type": "routing_exhausted_nogood",
                        "conflict_set": {"pose_optional::power_pole::pole_1": 1},
                        "iteration": 3,
                        "metadata": {},
                        "source_mode": "certified_exact",
                        "exact_safe": True,
                        "artifact_hashes": matching_hashes,
                        "proof_stage": "routing",
                        "binding_exhausted": True,
                        "routing_exhausted": True,
                        "proof_summary": {"enumerated_bindings": 4},
                        "created_at": "2026-03-15T00:00:00Z",
                    },
                    {
                        "schema_version": 2,
                        "cut_type": "routing_exhausted_nogood",
                        "conflict_set": {"pose_optional::power_pole::pole_2": 2},
                        "iteration": 4,
                        "metadata": {},
                        "source_mode": "certified_exact",
                        "exact_safe": True,
                        "artifact_hashes": {"candidate_placements": "mismatch", "mandatory_exact_instances": "def"},
                        "proof_stage": "routing",
                        "binding_exhausted": True,
                        "routing_exhausted": True,
                        "proof_summary": {},
                        "created_at": "2026-03-15T00:00:00Z",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    manager = CutManager(
        checkpoint_dir=tmp_path / "checkpoints",
        solve_mode="certified_exact",
        current_hashes=matching_hashes,
    )
    assert manager.checkpoint_dir == tmp_path / "checkpoints"
    stats = manager.load(exact_path)
    assert stats["loaded"] == 1
    assert stats["rejected_hash"] == 1
    assert len(manager.cuts) == 1
    assert manager.cuts[0].exact_safe is True


def test_collect_certification_blockers_flags_hash_mismatch_cut() -> None:
    cut = BendersCut(
        cut_type="routing_exhausted_nogood",
        conflict_set={"pose_optional::power_pole::pole_1": 1},
        iteration=1,
        source_mode="certified_exact",
        exact_safe=True,
        artifact_hashes={"candidate_placements": "old"},
        proof_stage="routing",
        binding_exhausted=True,
        routing_exhausted=True,
    )
    blockers = collect_certification_blockers(
        solve_mode="certified_exact",
        loaded_cuts=[cut],
        current_hashes={"candidate_placements": "new"},
    )
    assert any(item["code"] == "cut_hash_mismatch" for item in blockers)


def test_certified_exact_loads_new_fine_grained_exact_safe_cut_types(tmp_path: Path) -> None:
    exact_path = tmp_path / "cuts_fine_grained_exact.json"
    matching_hashes = {"candidate_placements": "abc", "mandatory_exact_instances": "def"}
    exact_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "cuts": [
                    {
                        "schema_version": 2,
                        "cut_type": "binding_pose_domain_empty_nogood",
                        "conflict_set": {"tiny_001": 0},
                        "iteration": 1,
                        "metadata": {"kind": "placement_local_nogood"},
                        "source_mode": "certified_exact",
                        "exact_safe": True,
                        "artifact_hashes": matching_hashes,
                        "proof_stage": "binding",
                        "binding_exhausted": False,
                        "routing_exhausted": False,
                        "proof_summary": {"binding_status": "EMPTY_DOMAIN"},
                        "created_at": "2026-03-16T00:00:00Z",
                    },
                    {
                        "schema_version": 2,
                        "cut_type": "routing_front_blocked_nogood",
                        "conflict_set": {
                            "tiny_001": 0,
                            "pose_optional::power_pole::pole_block": 0,
                        },
                        "iteration": 2,
                        "metadata": {"kind": "placement_local_nogood"},
                        "source_mode": "certified_exact",
                        "exact_safe": True,
                        "artifact_hashes": matching_hashes,
                        "proof_stage": "routing",
                        "binding_exhausted": False,
                        "routing_exhausted": False,
                        "proof_summary": {"routing_status": "PRECHECK_FRONT_BLOCKED"},
                        "created_at": "2026-03-16T00:00:00Z",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    manager = CutManager(
        checkpoint_dir=tmp_path / "checkpoints",
        solve_mode="certified_exact",
        current_hashes=matching_hashes,
    )
    assert manager.checkpoint_dir == tmp_path / "checkpoints"
    stats = manager.load(exact_path)

    assert stats["loaded"] == 2
    assert {cut.cut_type for cut in manager.cuts} == {
        "binding_pose_domain_empty_nogood",
        "routing_front_blocked_nogood",
    }
