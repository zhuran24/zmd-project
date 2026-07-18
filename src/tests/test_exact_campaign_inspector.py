from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from src.tests.certified_frontier_helpers import persist_forged_terminal_certified_state
from src.models.cut_manager import (
    RUN_STATUS_CERTIFIED,
    RUN_STATUS_UNKNOWN,
    RUN_STATUS_UNPROVEN,
)
from src.io import delivery_manifest as delivery_manifest_module
from src.io.delivery_manifest import (
    delivery_manifest_output_path,
    export_certified_delivery_manifest,
)
from src.io.serializer import export_certified_blueprint, load_candidate_placements
from src.search import certified_surface as certified_surface_module
from src.search import exact_campaign_inspector as exact_campaign_inspector_module
from src.search.campaign_telemetry import (
    append_campaign_wave_summary,
    build_wave_summary,
)
from src.search.certified_surface import (
    publish_verified_certified_delivery_surface,
    verify_certified_delivery_surface,
)
from src.search.exact_campaign import (
    ExactCampaign,
    compute_exact_artifact_hashes,
    has_terminal_full_frontier_certified_evidence,
)
from src.search.exact_campaign_inspector import build_exact_campaign_inspection
from src.search.phase3b.b5a import b5_anchor_sprint as b5a_module
from src.search.phase3b.b5a.b5_anchor_sprint import (
    build_phase3b_b5_anchor_sprint_summary,
    build_phase3b_b5_anchor_sprint_summary_from_inspection,
)
from src.tests.certified_frontier_helpers import (
    attach_terminal_frontier_evidence,
    forge_legacy_terminal_certified_stop,
    write_closed_phase_review_gate,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# PR1 supervisor_seal acceptance helpers
# ---------------------------------------------------------------------------
# PR1 added supervisor_seal as a required gate for terminal CERTIFIED
# validation.  Forged states (constructed without going through
# supervisor_seal) need these patches so the surface verifier accepts the
# forged checkpoint for inspection and delivery-artifact write paths while
# still checking artifact-hash compatibility.
# ---------------------------------------------------------------------------


def _accept_resume_for_forged(state, current_hashes, *, project_root=None):
    """Accept resume state where artifact hashes match; skip supervisor seal check."""
    if dict(state.get("artifact_hashes", {})) != dict(current_hashes):
        return "artifact_hash_mismatch"
    return None


def _accept_terminal_evidence_for_forged_state(
    state,
    *,
    project_root,
    campaign_path=None,
    serialized_state_bytes=None,
):
    """Accept terminal evidence for forged states that carry frontier evidence."""
    return has_terminal_full_frontier_certified_evidence(state)


def _accept_terminal_violation_for_forged(
    state,
    *,
    project_root,
    campaign_path=None,
    serialized_state_bytes=None,
):
    """Return None (no violation) for forged terminal CERTIFIED state."""
    return None


def _install_forged_certified_state_acceptance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch PR1 supervisor_seal validators to accept forged terminal CERTIFIED states.

    Patches five names in three modules that gate the certified surface verifier
    and the delivery-manifest export path.  Artifact hash matching is preserved.
    """
    monkeypatch.setattr(
        delivery_manifest_module,
        "validate_exact_campaign_resume_state",
        _accept_resume_for_forged,
    )
    monkeypatch.setattr(
        delivery_manifest_module,
        "terminal_certified_final_result_violation_for_project",
        _accept_terminal_violation_for_forged,
    )
    monkeypatch.setattr(
        certified_surface_module,
        "validate_exact_campaign_resume_state",
        _accept_resume_for_forged,
    )
    monkeypatch.setattr(
        certified_surface_module,
        "has_valid_terminal_full_frontier_certified_evidence_for_project",
        _accept_terminal_evidence_for_forged_state,
    )
    monkeypatch.setattr(
        exact_campaign_inspector_module,
        "validate_exact_campaign_resume_state",
        _accept_resume_for_forged,
    )


def _build_exact_project(project_root: Path) -> Path:
    _write_json(
        project_root / "rules" / "canonical_rules.json",
        {
            # V84: the terminal claim (2x1) must be the layout's true maximum
            # empty rectangle. With tiny_facility on (0,0), a 2x2 grid leaves
            # exactly a 2x1 (and the transposed 1x2) as the best empty area.
            "globals": {"grid": {"width": 2, "height": 2}, "empty_rectangle": {"objective": "max_lex_area_min_side", "min_side_admissibility": 1}},
            "facility_templates": {
                "tiny_facility": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}
            },
        },
    )
    _write_json(
        project_root / "rules" / "preprocess_plan.json",
        {"utility_operations": {}},
    )
    _write_json(
        project_root / "data" / "preprocessed" / "candidate_placements.json",
        {
            "facility_pools": {
                "tiny_facility": [
                    {
                        "pose_id": "tiny_0",
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
    _write_json(
        project_root / "data" / "preprocessed" / "mandatory_exact_instances.json",
        mandatory_instances,
    )
    _write_json(
        project_root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_outputs": {}, "required_generic_inputs": {}},
    )
    return project_root


def _campaign_state_display_path(project_root: Path, campaign_path: Path) -> str:
    try:
        return str(campaign_path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(campaign_path)


def _forged_b5a_inspection(
    project_root: Path,
    *,
    campaign_path: Path | None = None,
    candidate_count: int = 0,
) -> dict[str, object]:
    campaign_path = campaign_path or project_root / "data/checkpoints/exact_campaign_state.json"
    return {
        "metadata": {
            "source": b5a_module.INSPECTION_SCHEMA_SOURCE,
            "generated_at": "2026-01-01T00:00:00Z",
            "project_root": str(project_root),
        },
        "paths": {
            "campaign_state": _campaign_state_display_path(project_root, campaign_path),
            "campaign_telemetry": "data/checkpoints/exact_campaign_telemetry.json",
            "delivery_manifest": "data/solutions/certified_delivery_manifest.json",
            "final_solution": "data/solutions/final_solution.json",
            "optimal_blueprint": "data/blueprints/optimal_blueprint.json",
        },
        "campaign": {
            "present": bool(candidate_count),
            "final_status": None,
            "last_stop_reason": None,
            "candidate_count": candidate_count,
            "candidate_status_counts": {},
            "best_certified_result": None,
        },
        "telemetry": {"present": False, "wave_count": 0, "aggregate": None},
        "delivery_manifest": {
            "present": False,
            "terminal_full_frontier_certified": False,
        },
        "certified_surface": {
            "source": b5a_module.CERTIFIED_SURFACE_VERIFIER_SOURCE,
            "publishable": False,
            "blocked_reason": "unit_fixture_not_publishable",
        },
        "checks": [],
    }


def _install_fast_b5a_side_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        b5a_module,
        "build_phase3b_unknown_triage_inventory",
        lambda **_kwargs: {"summary": {}, "blockers": []},
    )
    monkeypatch.setattr(
        b5a_module,
        "build_phase3b_operating_profile_summary",
        lambda _project_root: {"defaults": {}, "policy": {}},
    )


def test_b5a_from_inspection_reuses_matching_inspection_without_second_inspection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = _build_exact_project(tmp_path / "project").resolve()
    inspection = _forged_b5a_inspection(project_root)
    _install_fast_b5a_side_inputs(monkeypatch)
    calls = 0

    def _fallback_inspection(**_kwargs):
        nonlocal calls
        calls += 1
        return _forged_b5a_inspection(project_root, candidate_count=5)

    monkeypatch.setattr(
        b5a_module,
        "build_exact_campaign_inspection",
        _fallback_inspection,
    )

    summary = build_phase3b_b5_anchor_sprint_summary_from_inspection(
        project_root,
        inspection=inspection,
    )

    assert calls == 0
    assert summary["campaign"]["candidate_count"] == 0
    assert summary["status"]["certified_surface_publishable"] is False
    assert summary["status"]["anchor_found"] is False


@pytest.mark.parametrize(
    "mismatch",
    [
        "inspection_source",
        "project_root",
        "campaign_state_path",
        "certified_surface_source",
    ],
)
def test_b5a_from_inspection_falls_back_when_reuse_guard_mismatches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    project_root = _build_exact_project(tmp_path / "project").resolve()
    campaign_path = project_root / "data/checkpoints/exact_campaign_state.json"
    inspection = _forged_b5a_inspection(project_root, campaign_path=campaign_path)
    invalid_inspection = json.loads(json.dumps(inspection))
    if mismatch == "inspection_source":
        invalid_inspection["metadata"]["source"] = "wrong_inspector"
    elif mismatch == "project_root":
        invalid_inspection["metadata"]["project_root"] = str(project_root / "other")
    elif mismatch == "campaign_state_path":
        invalid_inspection["paths"]["campaign_state"] = "data/checkpoints/other.json"
    elif mismatch == "certified_surface_source":
        invalid_inspection["certified_surface"]["source"] = "wrong_surface"
    else:  # pragma: no cover - parametrization sanity.
        raise AssertionError(mismatch)
    _install_fast_b5a_side_inputs(monkeypatch)
    calls = 0

    def _fallback_inspection(**kwargs):
        nonlocal calls
        calls += 1
        assert kwargs["project_root"] == project_root
        assert kwargs["campaign_state_path"] == campaign_path
        return _forged_b5a_inspection(
            project_root,
            campaign_path=campaign_path,
            candidate_count=5,
        )

    monkeypatch.setattr(
        b5a_module,
        "build_exact_campaign_inspection",
        _fallback_inspection,
    )

    summary = build_phase3b_b5_anchor_sprint_summary_from_inspection(
        project_root,
        inspection=invalid_inspection,
    )

    assert calls == 1
    assert summary["campaign"]["candidate_count"] == 5
    assert summary["status"]["anchor_found"] is False


def _certified_placement() -> dict[str, object]:
    # V89: the public final_result placement strips the ghost_pick marker.
    return {"tiny_001": {"facility_type": "tiny_facility", "pose_idx": 0}}


def _certified_solution() -> dict[str, object]:
    # V89: candidate records carry the ghost_pick provenance marker.
    return {
        "tiny_001": {"facility_type": "tiny_facility", "pose_idx": 0},
        "ghost_pick": {"pose_idx": 1, "pose_id": "ghost_anchor::0,1", "anchor": {"x": 0, "y": 1}, "facility_type": "ghost_rect"},
    }


def test_inspector_reports_missing_campaign_state(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")

    inspection = build_exact_campaign_inspection(project_root)

    assert inspection["campaign"]["present"] is False
    assert inspection["campaign"]["resume_compatible_with_current_hashes"] is False
    assert inspection["campaign"]["resume_validation_reason"] == "campaign_state_missing"
    assert inspection["telemetry"]["present"] is False
    assert inspection["delivery_manifest"]["present"] is False
    failed_checks = {
        check["check_id"]
        for check in inspection["checks"]
        if check["status"] == "fail"
    }
    assert "campaign_state_present" in failed_checks
    assert "campaign_telemetry_present" in failed_checks
    assert "delivery_manifest_present" in failed_checks


def test_inspector_summarizes_valid_resume_state(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": "CERTIFIED", "selection_reason": "objective_head"},
    )
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        "INFEASIBLE",
        proof_summary={"master_status": "INFEASIBLE"},
    )
    persist_forged_terminal_certified_state(campaign)

    inspection = build_exact_campaign_inspection(project_root)

    assert inspection["campaign"]["present"] is True
    assert inspection["campaign"]["resume_compatible_with_current_hashes"] is True
    assert inspection["campaign"]["resume_validation_reason"] is None
    assert inspection["campaign"]["candidate_count"] == 2
    assert inspection["campaign"]["candidate_status_counts"] == {
        "UNKNOWN": 2,
    }
    assert inspection["campaign"]["proof_bearing_candidate_statuses_redacted"] is True
    assert {row["status"] for row in inspection["campaign"]["top_candidates"]} == {"UNKNOWN"}
    assert all(
        not (row.get("last_stop_hint") or {}).get("master_status")
        for row in inspection["campaign"]["top_candidates"]
    )
    assert inspection["campaign"]["terminal_full_frontier_certified"] is False
    assert inspection["campaign"]["best_certified_result"] is None


def test_inspector_summarizes_terminal_full_frontier_certified_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    write_closed_phase_review_gate(project_root)
    _install_forged_certified_state_acceptance(monkeypatch)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": "CERTIFIED", "selection_reason": "objective_head"},
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 2, "h": 1, "area": 2, "anchor_x": 0, "anchor_y": 1},
        "placement_solution": _certified_placement(),
        "search_status": RUN_STATUS_CERTIFIED,
    }
    forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(
        campaign,
        project_root,
        fill_unresolved_better_candidates_as_infeasible=True,
    )
    persist_forged_terminal_certified_state(campaign)
    facility_pools = load_candidate_placements(
        project_root / "data" / "preprocessed" / "candidate_placements.json"
    )
    publish_verified_certified_delivery_surface(
        project_root=project_root,
        campaign_path=campaign.path,
        facility_pools=facility_pools,
    )

    inspection = build_exact_campaign_inspection(project_root)

    assert inspection["campaign"]["terminal_full_frontier_certified"] is True
    assert inspection["campaign"]["best_certified_result"]["ghost_rect"] == {
        "w": 2,
        "h": 1,
        "area": 2,
    }
    assert inspection["campaign"]["best_certified_result"]["objective"] == {
        "area": 2,
        "min_side": 1,
    }


def test_inspector_accepts_resume_state_with_resolver_supported_condition_cut(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(1, 1)
    campaign.mark_candidate_result(
        1,
        1,
        "INFEASIBLE",
        exact_safe_cuts=[
            {
                "schema_version": 3,
                "cut_type": "power_subproblem_infeasible_nogood",
                "conflict_set": {"tiny_001": 0},
                "iteration": 1,
                "metadata": {
                    "kind": "power_subproblem_ghost_conditioned_nogood",
                    "ghost_rect_idx": 2,
                    "ghost_anchor": {"x": 1, "y": 0},
                },
                "source_mode": "certified_exact",
                "exact_safe": True,
                "artifact_hashes": campaign.artifact_hashes,
                "proof_stage": "power_placement_subproblem",
                "binding_exhausted": False,
                "routing_exhausted": False,
                "proof_summary": {},
                "created_at": "2026-03-15T00:00:00Z",
                "condition_set": {"ghost_anchor::(1,0)": 2},
            }
        ],
        proof_summary={"master_status": "INFEASIBLE"},
        generated_exact_safe_cut_count=1,
    )
    persist_forged_terminal_certified_state(campaign)

    inspection = build_exact_campaign_inspection(project_root)

    assert inspection["campaign"]["resume_compatible_with_current_hashes"] is True
    assert inspection["campaign"]["resume_validation_reason"] is None


def test_inspector_reports_artifact_mismatch_without_mutating_state(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": "CERTIFIED"},
    )
    persist_forged_terminal_certified_state(campaign)
    before = campaign.path.read_text(encoding="utf-8")

    rules_path = project_root / "rules" / "canonical_rules.json"
    rules_payload = json.loads(rules_path.read_text(encoding="utf-8"))
    rules_payload["globals"]["grid"]["width"] = 4
    _write_json(rules_path, rules_payload)

    inspection = build_exact_campaign_inspection(project_root)

    assert inspection["campaign"]["resume_compatible_with_current_hashes"] is False
    assert inspection["campaign"]["resume_validation_reason"] == "artifact_hash_mismatch"
    assert campaign.path.read_text(encoding="utf-8") == before


@pytest.mark.parametrize(
    ("stop_reason", "status"),
    [
        ("candidate_returned_unknown", RUN_STATUS_UNKNOWN),
        ("candidate_returned_unproven", RUN_STATUS_UNPROVEN),
        ("worker_process_failed", RUN_STATUS_UNKNOWN),
    ],
)
def test_inspector_keeps_stop_reason_visible_without_nonterminal_best_certified_result(
    tmp_path: Path,
    stop_reason: str,
    status: str,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": "CERTIFIED"},
    )
    campaign.mark_campaign_stopped(stop_reason, status=status)
    persist_forged_terminal_certified_state(campaign)

    inspection = build_exact_campaign_inspection(project_root)

    assert inspection["campaign"]["last_stop_reason"]["reason"] == stop_reason
    assert inspection["campaign"]["final_status"] == status
    assert inspection["campaign"]["terminal_full_frontier_certified"] is False
    assert inspection["campaign"]["best_certified_result"] is None


def test_inspector_summarizes_telemetry(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    persist_forged_terminal_certified_state(campaign)
    append_campaign_wave_summary(
        project_root=project_root,
        campaign_path=campaign.path,
        reset=True,
        wave_summary=build_wave_summary(
            wave_index=1,
            candidate_results=[
                {
                    "candidate_key": "2x1",
                    "status": RUN_STATUS_UNKNOWN,
                    "proof_summary": {"master_status": "UNKNOWN"},
                }
            ],
            completed=True,
            failure_reason=None,
            dispatched_candidate_keys=["2x1"],
        ),
    )

    inspection = build_exact_campaign_inspection(project_root)

    assert inspection["telemetry"]["present"] is True
    assert inspection["telemetry"]["wave_count"] == 1
    assert inspection["telemetry"]["last_wave"]["wave_index"] == 1
    assert inspection["telemetry"]["aggregate"]["status_counts"] == {RUN_STATUS_UNKNOWN: 1}


def test_inspector_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "inspect_exact_campaign_state.py"
    output_path = tmp_path / "inspection.json"
    no_write_path = tmp_path / "no_write.json"

    no_write_result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--output",
            str(no_write_path),
            "--no-write",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert no_write_result.returncode == 0
    assert "exact campaign inspection" in no_write_result.stdout
    assert not no_write_path.exists()

    write_result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert write_result.returncode == 0
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_exact_campaign_inspector_v1"

def test_inspector_hides_stale_final_result_without_terminal_frontier_evidence(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": "CERTIFIED"},
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 2, "h": 1, "area": 2, "anchor_x": 0, "anchor_y": 1},
        "placement_solution": _certified_placement(),
        "search_status": RUN_STATUS_CERTIFIED,
    }
    campaign.mark_campaign_stopped("candidate_returned_unknown", status=RUN_STATUS_UNKNOWN)
    campaign.state["final_status"] = RUN_STATUS_CERTIFIED
    persist_forged_terminal_certified_state(campaign)

    inspection = build_exact_campaign_inspection(project_root)

    assert inspection["campaign"]["resume_compatible_with_current_hashes"] is False
    assert inspection["campaign"]["resume_validation_reason"] == (
        "terminal_certified_frontier_evidence_invalid"
    )
    assert inspection["campaign"]["terminal_full_frontier_certified"] is False
    assert inspection["campaign"]["best_certified_result"] is None


def test_inspector_hides_stale_delivery_manifest_best_result_without_terminal_evidence(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    manifest_path = project_root / "data" / "solutions" / "certified_delivery_manifest.json"
    _write_json(
        manifest_path,
        {
            "metadata": {"source": "test"},
            "campaign": {
                "final_status": RUN_STATUS_CERTIFIED,
                "last_stop_reason": {
                    "reason": "candidate_returned_unknown",
                    "status": RUN_STATUS_UNKNOWN,
                },
                "declare_mode": "strict",
            },
            "best_certified_result": {
                "ghost_rect": {"w": 2, "h": 1, "area": 2, "anchor_x": 0, "anchor_y": 1},
                "search_status": RUN_STATUS_CERTIFIED,
                "placement_solution": _certified_placement(),
            },
        },
    )

    inspection = build_exact_campaign_inspection(project_root)

    assert inspection["delivery_manifest"]["terminal_full_frontier_certified"] is False
    assert inspection["delivery_manifest"]["best_certified_result"] is None



def test_v68_inspector_requires_current_campaign_evidence_for_terminal_manifest(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_campaign_stopped("max_attempts_exhausted", status=RUN_STATUS_UNKNOWN)
    persist_forged_terminal_certified_state(campaign)
    manifest_path = project_root / "data" / "solutions" / "certified_delivery_manifest.json"
    _write_json(
        manifest_path,
        {
            "metadata": {"source": "stale"},
            "campaign": {
                "final_status": RUN_STATUS_CERTIFIED,
                "last_stop_reason": {
                    "reason": "search_exhausted_all_candidates",
                    "status": RUN_STATUS_CERTIFIED,
                },
                "declare_mode": "strict",
            },
            "best_certified_result": {
                "ghost_rect": {"w": 2, "h": 1, "area": 2, "anchor_x": 0, "anchor_y": 1},
                "search_status": RUN_STATUS_CERTIFIED,
                "placement_solution": _certified_placement(),
            },
        },
    )

    inspection = build_exact_campaign_inspection(project_root)

    assert inspection["campaign"]["resume_compatible_with_current_hashes"] is True
    assert inspection["campaign"]["terminal_full_frontier_certified"] is False
    assert inspection["campaign"]["best_certified_result"] is None
    assert inspection["delivery_manifest"]["campaign_final_status"] is None
    assert inspection["delivery_manifest"]["terminal_full_frontier_certified"] is False
    assert inspection["delivery_manifest"]["best_certified_result"] is None


def test_v69_inspector_rejects_manifest_best_result_that_only_partially_matches_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    _install_forged_certified_state_acceptance(monkeypatch)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": "CERTIFIED", "selection_reason": "objective_head"},
        loaded_exact_safe_cut_count=1,
        generated_exact_safe_cut_count=2,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 2, "h": 1, "area": 2, "anchor_x": 0, "anchor_y": 1},
        "placement_solution": _certified_placement(),
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(
        campaign,
        project_root,
        fill_unresolved_better_candidates_as_infeasible=True,
    )
    persist_forged_terminal_certified_state(campaign)

    manifest_path = project_root / "data" / "solutions" / "certified_delivery_manifest.json"
    _write_json(
        manifest_path,
        {
            "metadata": {"source": "stale"},
            "campaign": {
                "final_status": RUN_STATUS_CERTIFIED,
                "last_stop_reason": {
                    "reason": "search_exhausted_all_candidates",
                    "status": RUN_STATUS_CERTIFIED,
                },
                "declare_mode": "strict",
            },
            "best_certified_result": {
                "ghost_rect": {"w": 2, "h": 1, "area": 2, "anchor_x": 0, "anchor_y": 1},
                "search_status": RUN_STATUS_CERTIFIED,
                "search_stats": {"campaign_resumed": False},
                "proof_summary": {"master_status": "STALE"},
                "loaded_exact_safe_cut_count": 1,
                "generated_exact_safe_cut_count": 2,
            },
        },
    )

    inspection = build_exact_campaign_inspection(project_root)

    assert inspection["campaign"]["resume_compatible_with_current_hashes"] is True
    assert inspection["campaign"]["terminal_full_frontier_certified"] is False
    assert inspection["campaign"]["best_certified_result"] is None
    assert inspection["delivery_manifest"]["terminal_full_frontier_certified"] is False
    assert inspection["delivery_manifest"]["best_certified_result"] is None


def test_v70_inspector_and_b5a_reject_stale_terminal_after_artifact_hash_mismatch(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": "CERTIFIED", "selection_reason": "objective_head"},
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 2, "h": 1, "area": 2, "anchor_x": 0, "anchor_y": 1},
        "placement_solution": _certified_placement(),
        "search_status": RUN_STATUS_CERTIFIED,
    }
    forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(
        campaign,
        project_root,
        fill_unresolved_better_candidates_as_infeasible=True,
    )
    persist_forged_terminal_certified_state(campaign)

    rules_path = project_root / "rules" / "canonical_rules.json"
    rules_payload = json.loads(rules_path.read_text(encoding="utf-8"))
    rules_payload["globals"]["grid"]["width"] = 4
    _write_json(rules_path, rules_payload)

    inspection = build_exact_campaign_inspection(project_root)
    b5a_summary = build_phase3b_b5_anchor_sprint_summary_from_inspection(
        project_root,
        inspection=inspection,
    )

    assert inspection["campaign"]["resume_compatible_with_current_hashes"] is False
    assert inspection["campaign"]["resume_validation_reason"] == "artifact_hash_mismatch"
    assert inspection["campaign"]["terminal_full_frontier_certified"] is False
    assert inspection["campaign"]["best_certified_result"] is None
    assert b5a_summary["status"]["anchor_found"] is False
    assert b5a_summary["anchor"] is None


def test_v70_inspector_and_b5a_reject_terminal_manifest_without_current_delivery_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    write_closed_phase_review_gate(project_root)
    _install_forged_certified_state_acceptance(monkeypatch)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": "CERTIFIED", "selection_reason": "objective_head"},
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 2, "h": 1, "area": 2, "anchor_x": 0, "anchor_y": 1},
        "placement_solution": _certified_placement(),
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(
        campaign,
        project_root,
        fill_unresolved_better_candidates_as_infeasible=True,
    )
    persist_forged_terminal_certified_state(campaign)
    facility_pools = load_candidate_placements(
        project_root / "data" / "preprocessed" / "candidate_placements.json"
    )
    publish_verified_certified_delivery_surface(
        project_root=project_root,
        campaign_path=campaign.path,
        facility_pools=facility_pools,
    )

    (project_root / "data" / "solutions" / "final_solution.json").unlink()
    inspection = build_exact_campaign_inspection(project_root)
    b5a_summary = build_phase3b_b5_anchor_sprint_summary_from_inspection(
        project_root,
        inspection=inspection,
    )

    assert inspection["campaign"]["terminal_full_frontier_certified"] is False
    assert inspection["campaign"]["best_certified_result"] is None
    assert inspection["delivery_manifest"]["present"] is True
    assert inspection["delivery_manifest"]["terminal_full_frontier_certified"] is False
    assert inspection["delivery_manifest"]["best_certified_result"] is None
    assert b5a_summary["status"]["anchor_found"] is False
    assert b5a_summary["anchor"] is None


def test_v71_inspector_and_b5a_reject_manifest_with_stale_artifact_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = _build_exact_project(tmp_path / "project")
    write_closed_phase_review_gate(project_root)
    _install_forged_certified_state_acceptance(monkeypatch)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": "CERTIFIED", "selection_reason": "objective_head"},
        loaded_exact_safe_cut_count=1,
        generated_exact_safe_cut_count=2,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 2, "h": 1, "area": 2, "anchor_x": 0, "anchor_y": 1},
        "placement_solution": _certified_placement(),
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(
        campaign,
        project_root,
        fill_unresolved_better_candidates_as_infeasible=True,
    )
    persist_forged_terminal_certified_state(campaign)
    facility_pools = load_candidate_placements(
        project_root / "data" / "preprocessed" / "candidate_placements.json"
    )
    publish_verified_certified_delivery_surface(
        project_root=project_root,
        campaign_path=campaign.path,
        facility_pools=facility_pools,
    )
    manifest_path = project_root / "data" / "solutions" / "certified_delivery_manifest.json"
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_payload["campaign"]["updated_at"] = "2000-01-01T00:00:00Z"
    manifest_payload["artifacts"]["final_solution"]["sha256"] = "0" * 64
    manifest_payload["artifacts"]["final_solution"]["size_bytes"] = 1
    _write_json(manifest_path, manifest_payload)

    inspection = build_exact_campaign_inspection(project_root)
    b5a_summary = build_phase3b_b5_anchor_sprint_summary_from_inspection(
        project_root,
        inspection=inspection,
    )

    assert inspection["campaign"]["terminal_full_frontier_certified"] is False
    assert inspection["campaign"]["best_certified_result"] is None
    assert inspection["delivery_manifest"]["present"] is True
    assert inspection["delivery_manifest"]["terminal_full_frontier_certified"] is False
    assert inspection["delivery_manifest"]["best_certified_result"] is None
    assert b5a_summary["status"]["delivery_manifest_terminal_full_frontier_certified"] is False
    assert b5a_summary["status"]["anchor_found"] is False
    assert b5a_summary["anchor"] is None


def _export_current_certified_surface(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> ExactCampaign:
    if project_root.exists():
        shutil.rmtree(project_root)
    project_root = _build_exact_project(project_root)
    write_closed_phase_review_gate(project_root)
    _install_forged_certified_state_acceptance(monkeypatch)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(2, 1)
    campaign.mark_candidate_result(
        2,
        1,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"master_status": "CERTIFIED", "selection_reason": "objective_head"},
        loaded_exact_safe_cut_count=1,
        generated_exact_safe_cut_count=2,
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 2, "h": 1, "area": 2, "anchor_x": 0, "anchor_y": 1},
        "placement_solution": _certified_placement(),
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {"campaign_resumed": False},
    }
    forge_legacy_terminal_certified_stop(campaign)
    attach_terminal_frontier_evidence(
        campaign,
        project_root,
        fill_unresolved_better_candidates_as_infeasible=True,
    )
    persist_forged_terminal_certified_state(campaign)
    facility_pools = load_candidate_placements(
        project_root / "data" / "preprocessed" / "candidate_placements.json"
    )
    publish_verified_certified_delivery_surface(
        project_root=project_root,
        campaign_path=campaign.path,
        facility_pools=facility_pools,
    )
    return campaign


def _assert_certified_surface_verdict_is_single_gate_for_inspector_and_b5a(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _export_current_certified_surface(project_root, monkeypatch)

    inspection = build_exact_campaign_inspection(project_root)
    b5a_summary = build_phase3b_b5_anchor_sprint_summary_from_inspection(
        project_root,
        inspection=inspection,
    )

    assert inspection["certified_surface"]["source"] == "certified_surface_verifier_v1"
    assert inspection["certified_surface"]["publishable"] is True
    assert inspection["certified_surface"]["terminal_full_frontier_certified"] is True
    assert inspection["campaign"]["terminal_full_frontier_certified"] is True
    assert inspection["delivery_manifest"]["terminal_full_frontier_certified"] is True
    assert b5a_summary["status"]["certified_surface_publishable"] is True
    assert b5a_summary["status"]["anchor_found"] is True

    delivery_manifest_output_path(project_root).unlink()

    stale_inspection = build_exact_campaign_inspection(project_root)
    stale_b5a_summary = build_phase3b_b5_anchor_sprint_summary_from_inspection(
        project_root,
        inspection=stale_inspection,
    )

    assert stale_inspection["certified_surface"]["publishable"] is False
    assert stale_inspection["certified_surface"]["blocked_reason"] == "delivery_manifest_missing"
    assert stale_inspection["campaign"]["terminal_full_frontier_certified"] is False
    assert stale_inspection["campaign"]["best_certified_result"] is None
    assert stale_inspection["delivery_manifest"]["terminal_full_frontier_certified"] is False
    assert stale_b5a_summary["status"]["certified_surface_publishable"] is False
    assert stale_b5a_summary["status"]["anchor_found"] is False
    assert stale_b5a_summary["anchor"] is None


def test_v73_inspector_uses_certified_surface_verifier_for_public_certified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_certified_surface_verdict_is_single_gate_for_inspector_and_b5a(
        tmp_path / "single_certified_surface_gate",
        monkeypatch,
    )


def test_v73_certified_surface_verdict_is_single_gate_for_inspector_and_b5a(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_certified_surface_verdict_is_single_gate_for_inspector_and_b5a(
        tmp_path / "single_certified_surface_verdict",
        monkeypatch,
    )


def test_v73_b5a_uses_certified_surface_verifier_for_anchor_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "b5a_certified_surface_verifier"
    # Sentinel: keep the default B5A entry on a freshly published surface.
    _export_current_certified_surface(project_root, monkeypatch)

    current_summary = build_phase3b_b5_anchor_sprint_summary(project_root)

    assert current_summary["status"]["certified_surface_public"] is True
    assert current_summary["status"]["certified_surface_publishable"] is True
    assert current_summary["status"]["anchor_found"] is True
    assert current_summary["anchor"] is not None

    delivery_manifest_output_path(project_root).unlink()
    stale_summary = build_phase3b_b5_anchor_sprint_summary(project_root)

    assert stale_summary["status"]["certified_surface_public"] is False
    assert stale_summary["status"]["certified_surface_publishable"] is False
    assert stale_summary["status"]["certified_surface_blocked_reason"] == "delivery_manifest_missing"
    assert stale_summary["status"]["anchor_found"] is False
    assert stale_summary["anchor"] is None


def test_v73_certified_surface_rejects_non_regular_manifest_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "non_regular_certified_manifest"
    # Sentinel: keep one real publisher/currentness integration in this file.
    _export_current_certified_surface(project_root, monkeypatch)
    manifest_path = delivery_manifest_output_path(project_root)
    manifest_path.unlink()
    manifest_path.mkdir()

    inspection = build_exact_campaign_inspection(project_root)
    b5a_summary = build_phase3b_b5_anchor_sprint_summary_from_inspection(
        project_root,
        inspection=inspection,
    )

    assert inspection["certified_surface"]["publishable"] is False
    assert inspection["certified_surface"]["delivery_manifest_regular_file"] is False
    assert inspection["certified_surface"]["blocked_reason"] == "delivery_manifest_not_regular_file"
    assert inspection["campaign"]["terminal_full_frontier_certified"] is False
    assert inspection["delivery_manifest"]["present"] is False
    assert b5a_summary["status"]["certified_surface_publishable"] is False
    assert b5a_summary["status"]["anchor_found"] is False


def test_v74_certified_surface_rejects_memory_manifest_when_disk_manifest_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "memory_manifest_not_authoritative"
    campaign = _export_current_certified_surface(project_root, monkeypatch)
    manifest_path = delivery_manifest_output_path(project_root)
    valid_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stale_manifest = dict(valid_manifest)
    stale_manifest["best_certified_result"] = None
    _write_json(manifest_path, stale_manifest)

    verdict = verify_certified_delivery_surface(
        project_root=project_root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
        delivery_manifest=valid_manifest,
    )

    assert verdict.publishable is False
    assert verdict.blocked_reason == "delivery_manifest_payload_mismatch"


def test_v74_certified_surface_rejects_memory_campaign_when_disk_checkpoint_differs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "memory_campaign_not_authoritative"
    campaign = _export_current_certified_surface(project_root, monkeypatch)
    forged_terminal_state = dict(campaign.state)
    stale_checkpoint = dict(campaign.state)
    stale_checkpoint["final_result"] = None
    stale_checkpoint["final_status"] = None
    stale_checkpoint["last_stop_reason"] = None
    manifest_payload = json.loads(
        delivery_manifest_output_path(project_root).read_text(encoding="utf-8")
    )
    _write_json(campaign.path, stale_checkpoint)

    verdict = verify_certified_delivery_surface(
        project_root=project_root,
        campaign_state=forged_terminal_state,
        campaign_path=campaign.path,
        delivery_manifest=manifest_payload,
    )

    assert verdict.publishable is False
    assert verdict.blocked_reason == "campaign_state_payload_mismatch"


def test_v74_certified_surface_recomputes_exact_hashes_even_when_caller_claims_resume_ok(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "caller_hash_claim_not_authoritative"
    campaign = _export_current_certified_surface(project_root, monkeypatch)
    stale_hashes = compute_exact_artifact_hashes(project_root)
    _write_json(
        project_root / "data" / "preprocessed" / "generic_io_requirements.json",
        {"required_generic_outputs": {"tampered": 1}, "required_generic_inputs": {}},
    )

    verdict = verify_certified_delivery_surface(
        project_root=project_root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
        delivery_manifest=json.loads(delivery_manifest_output_path(project_root).read_text()),
        current_hashes=stale_hashes,
        campaign_resume_compatible=True,
    )

    assert verdict.publishable is False
    assert verdict.blocked_reason == "provided_exact_artifact_hashes_stale"


def test_v74_inspector_rejects_duplicate_key_delivery_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "duplicate_key_delivery_manifest"
    _export_current_certified_surface(project_root, monkeypatch)
    manifest_path = delivery_manifest_output_path(project_root)
    manifest_text = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(
        manifest_text.replace(
            '  "best_certified_result": {',
            '  "best_certified_result": null,\n  "best_certified_result": {',
            1,
        ),
        encoding="utf-8",
    )

    inspection = build_exact_campaign_inspection(project_root)
    b5a_summary = build_phase3b_b5_anchor_sprint_summary_from_inspection(
        project_root,
        inspection=inspection,
    )

    assert inspection["certified_surface"]["publishable"] is False
    assert inspection["certified_surface"]["blocked_reason"].startswith(
        "json_load_error:ValueError:duplicate JSON key: best_certified_result"
    )
    assert inspection["campaign"]["terminal_full_frontier_certified"] is False
    assert inspection["delivery_manifest"]["terminal_full_frontier_certified"] is False
    assert b5a_summary["status"]["certified_surface_publishable"] is False
    assert b5a_summary["status"]["anchor_found"] is False
