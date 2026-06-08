"""Tests for cut provenance（切平面来源追踪测试）."""

from __future__ import annotations

import json
from pathlib import Path

from src.models.cut_manager import BendersCut, CutManager
from src.search.benders_loop import collect_certification_blockers
from src.search.exact_campaign import ExactCampaign

import pytest



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
        solve_mode="certified_exact",
        current_hashes={"candidate_placements": "abc", "mandatory_exact_instances": "def"},
    )
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


def test_exact_campaign_resume_rejects_malformed_exact_safe_cut(tmp_path: Path) -> None:
    project_root = tmp_path / "campaign_malformed_exact_safe"
    (project_root / "data" / "preprocessed").mkdir(parents=True)
    (project_root / "rules").mkdir(parents=True)
    (project_root / "data" / "preprocessed" / "mandatory_exact_instances.json").write_text("[]", encoding="utf-8")
    (project_root / "data" / "preprocessed" / "candidate_placements.json").write_text("{}", encoding="utf-8")
    (project_root / "data" / "preprocessed" / "generic_io_requirements.json").write_text("{}", encoding="utf-8")
    (project_root / "rules" / "canonical_rules.json").write_text("{}", encoding="utf-8")

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
    campaign.save()

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "candidate_invalid_exact_safe_cut:1x1:0"


def test_exact_campaign_resume_rejects_bool_conflict_pose_index(tmp_path: Path) -> None:
    project_root = tmp_path / "campaign_bool_conflict_pose"
    (project_root / "data" / "preprocessed").mkdir(parents=True)
    (project_root / "rules").mkdir(parents=True)
    (project_root / "data" / "preprocessed" / "mandatory_exact_instances.json").write_text("[]", encoding="utf-8")
    (project_root / "data" / "preprocessed" / "candidate_placements.json").write_text("{}", encoding="utf-8")
    (project_root / "data" / "preprocessed" / "generic_io_requirements.json").write_text("{}", encoding="utf-8")
    (project_root / "rules" / "canonical_rules.json").write_text("{}", encoding="utf-8")

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
    campaign.save()

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
        solve_mode="certified_exact",
        current_hashes={"candidate_placements": "abc"},
    )

    with pytest.raises(ValueError, match="duplicate JSON key"):
        manager.load(exact_path)


def test_exact_campaign_resume_rejects_duplicate_json_key(tmp_path: Path) -> None:
    project_root = tmp_path / "campaign_duplicate_exact_safe"
    (project_root / "data" / "preprocessed").mkdir(parents=True)
    (project_root / "rules").mkdir(parents=True)
    (project_root / "data" / "preprocessed" / "mandatory_exact_instances.json").write_text("[]", encoding="utf-8")
    (project_root / "data" / "preprocessed" / "candidate_placements.json").write_text("{}", encoding="utf-8")
    (project_root / "data" / "preprocessed" / "generic_io_requirements.json").write_text("{}", encoding="utf-8")
    (project_root / "rules" / "canonical_rules.json").write_text("{}", encoding="utf-8")

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
    campaign.save()

    path = campaign.path
    raw = path.read_text(encoding="utf-8")
    path.write_text(
        raw.replace('"exact_safe": true', '"exact_safe": false, "exact_safe": true', 1),
        encoding="utf-8",
    )

    resumed = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert resumed.resumed is False
    assert resumed.reset_reason == "state_json_invalid"


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

    manager = CutManager(solve_mode="certified_exact", current_hashes=matching_hashes)
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

    manager = CutManager(solve_mode="certified_exact", current_hashes=matching_hashes)
    stats = manager.load(exact_path)

    assert stats["loaded"] == 2
    assert {cut.cut_type for cut in manager.cuts} == {
        "binding_pose_domain_empty_nogood",
        "routing_front_blocked_nogood",
    }
