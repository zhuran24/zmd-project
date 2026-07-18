from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.io import delivery_manifest as delivery_manifest_module
from src.search import certified_surface as certified_surface_module
from src.search import exact_campaign_inspector as exact_campaign_inspector_module
from src.tests.certified_frontier_helpers import (
    persist_canonical_blueprint_for_test,
    persist_forged_terminal_certified_state,
)
from src.io.delivery_manifest import delivery_manifest_output_path
from src.io.serializer import (
    build_blueprint_payload_from_certified_result,
    load_candidate_placements,
)
from src.models.cut_manager import (
    RUN_STATUS_CERTIFIED,
    RUN_STATUS_INFEASIBLE,
    RUN_STATUS_UNKNOWN,
)
from src.search.campaign_telemetry import append_campaign_wave_summary, build_wave_summary
from src.search.exact_campaign import ExactCampaign, has_terminal_full_frontier_certified_evidence
from src.search.phase3b.campaign.repair import (
    mark_running_exact_campaign_candidates_interrupted,
)
from src.tests.certified_frontier_helpers import (
    attach_terminal_frontier_evidence,
    forge_legacy_terminal_certified_stop,
    write_closed_phase_review_gate,
)
from src.search.phase3b.b5a.b5_anchor_sprint import (
    build_phase3b_b5_anchor_sprint_summary,
    render_phase3b_b5_anchor_sprint_markdown,
    render_phase3b_b5_anchor_sprint_text,
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
# forged checkpoint while still checking artifact-hash compatibility.
# ---------------------------------------------------------------------------


def _accept_resume_for_forged(state: object, current_hashes: object, *, project_root: object = None) -> object:
    """Accept resume state where artifact hashes match; skip supervisor seal check."""
    import collections.abc
    if not isinstance(state, collections.abc.Mapping):
        return "state_invalid"
    if not isinstance(current_hashes, collections.abc.Mapping):
        return "current_hashes_invalid"
    if dict(state.get("artifact_hashes", {})) != dict(current_hashes):  # type: ignore[union-attr]
        return "artifact_hash_mismatch"
    return None


def _accept_terminal_evidence_for_forged_state(
    state: object,
    *,
    project_root: object,
    campaign_path: object = None,
    serialized_state_bytes: object = None,
) -> bool:
    """Accept terminal evidence for forged states that carry frontier evidence."""
    import collections.abc
    if not isinstance(state, collections.abc.Mapping):
        return False
    return has_terminal_full_frontier_certified_evidence(state)


def _accept_terminal_violation_for_forged(
    state: object,
    *,
    project_root: object,
    campaign_path: object = None,
    serialized_state_bytes: object = None,
) -> None:
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
            "globals": {
                "grid": {"width": 5, "height": 1},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 1,
                },
            },
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


def _certified_placement() -> dict[str, object]:
    return {"tiny_001": {"facility_type": "tiny_facility", "pose_idx": 0}}


def _certified_solution() -> dict[str, object]:
    # V89: candidate records carry the ghost_pick provenance marker.
    return {
        "tiny_001": {"facility_type": "tiny_facility", "pose_idx": 0},
        "ghost_pick": {"pose_idx": 1, "pose_id": "ghost_anchor::1,0", "anchor": {"x": 1, "y": 0}, "facility_type": "ghost_rect"},
    }


def test_b5a_prepare_workspace_script_defaults_to_e_and_refuses_overwrite() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script_text = (repo_root / "scripts" / "prepare_phase3b_b5_anchor_workspace.ps1").read_text(
        encoding="utf-8"
    )

    assert "E:\\phase3b_workspaces\\endfield_phase3b_b5_anchor_20260417" in script_text
    assert "Target workspace already exists; refusing to overwrite" in script_text
    assert "Copy-Item" in script_text
    assert "Write-DriveSummary" in script_text


def test_b5a_sprint_runner_locks_short_diagnostic_profile() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script_text = (repo_root / "scripts" / "run_phase3b_b5_anchor_sprint.ps1").read_text(
        encoding="utf-8"
    )

    assert "E:\\phase3b_workspaces\\endfield_phase3b_b5_anchor_20260417" in script_text
    assert "[double]$CampaignHours = 1.0" in script_text
    assert "[int]$MaxAttempts = 2" in script_text
    assert "[double]$MasterSeconds = 30.0" in script_text
    assert "[double]$BindingSeconds = 30.0" in script_text
    assert "[double]$RoutingSeconds = 30.0" in script_text
    assert "[int]$BendersMaxIter = 1" in script_text
    assert "[int]$FrontierProbeMaxAnchors = 256" in script_text
    assert "[int]$BoundaryPortPrecheckMaxAnchors = 256" in script_text
    assert "[int]$MandatoryRectanglePrecheckMaxAnchors = 256" in script_text
    assert "[double]$MandatoryRectanglePrecheckTimeBudgetSeconds = 180.0" in script_text
    assert "[int]$CoordinateValidationPrecheckMaxAnchors = 0" in script_text
    assert "[double]$CoordinateValidationPrecheckSeconds = 2.0" in script_text
    assert "[int]$GhostAwareCoordinateValidationMaxAnchors = 8" in script_text
    assert "[double]$GhostAwareCoordinateValidationSeconds = 10.0" in script_text
    assert "[double]$GhostAwarePoseOrderValidationSeconds = 2.0" in script_text
    assert "[int]$FailedAnchorSampleLimit = 128" in script_text
    assert '[string]$MasterSearchProfile = "exact_coordinate_guided_branching_v4"' in script_text
    assert '[string]$MasterSearchBranching = "fixed"' in script_text
    assert '[string]$FormulationProfile = "default"' in script_text
    assert "[switch]$EnableGhostAwareNoSolvePrechecks" in script_text
    assert 'selected_block_block64_all_templates' in script_text
    assert 'joined_xy_block64_all_templates' in script_text
    assert "[switch]$DisableMasterPresolve" in script_text
    assert "[int]$MasterCpModelProbingLevel = -1" in script_text
    assert "[int]$MasterSymmetryLevel = -1" in script_text
    assert "[int]$MasterHintConflictLimit = -1" in script_text
    assert "[switch]$DisableMasterWarmStart" in script_text
    assert "[int]$WallTimeoutSeconds = 0" in script_text
    assert "[switch]$ValidateWorkspaceOnly" in script_text
    assert '"--max-attempts", ([string]$MaxAttempts)' in script_text
    assert '"--master-seconds", ([string]$MasterSeconds)' in script_text
    assert '"--binding-seconds", ([string]$BindingSeconds)' in script_text
    assert '"--routing-seconds", ([string]$RoutingSeconds)' in script_text
    assert '"--benders-max-iter", ([string]$BendersMaxIter)' in script_text
    assert '"--master-search-profile", $MasterSearchProfile' in script_text
    assert "--disable-master-warm-start" in script_text
    assert '"--parallel-processes", "1"' in script_text
    assert '"--process-priority", "normal"' in script_text
    assert '"--frontier-probe-mode", "auto"' in script_text
    assert '"EXACT_CP_SAT_WORKERS" = "1"' in script_text
    assert '"EXACT_FRONTIER_PROBE_MAX_ANCHORS" = ([string]$FrontierProbeMaxAnchors)' in script_text
    assert '"EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS" = ([string]$BoundaryPortPrecheckMaxAnchors)' in script_text
    assert '"EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS" = ([string]$MandatoryRectanglePrecheckMaxAnchors)' in script_text
    assert '"EXACT_MANDATORY_RECTANGLE_PRECHECK_TIME_BUDGET_SECONDS" = ([string]$MandatoryRectanglePrecheckTimeBudgetSeconds)' in script_text
    assert '"EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS" = ([string]$CoordinateValidationPrecheckMaxAnchors)' in script_text
    assert '"EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS" = ([string]$CoordinateValidationPrecheckSeconds)' in script_text
    assert '"EXACT_GHOST_AWARE_COORDINATE_VALIDATION_MAX_ANCHORS" = ([string]$GhostAwareCoordinateValidationMaxAnchors)' in script_text
    assert '"EXACT_GHOST_AWARE_COORDINATE_VALIDATION_SECONDS" = ([string]$GhostAwareCoordinateValidationSeconds)' in script_text
    assert '"EXACT_GHOST_AWARE_POSE_ORDER_VALIDATION_SECONDS" = ([string]$GhostAwarePoseOrderValidationSeconds)' in script_text
    assert '"EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT" = ([string]$FailedAnchorSampleLimit)' in script_text
    assert '"EXACT_MASTER_SEARCH_BRANCHING" = $MasterSearchBranching' in script_text
    assert 'if ($FormulationProfile -eq "selected_block_block64_all_templates")' in script_text
    assert '$effectiveEnv["EXACT_POWER_FAMILY_LOOKUP_ENCODING"] = "linear_shell_guards"' in script_text
    assert '$effectiveEnv["EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING"] = "linear_minmax"' in script_text
    assert '$effectiveEnv["EXACT_POWER_COVERAGE_WITNESS_ENCODING"] = "block_element"' in script_text
    assert '$effectiveEnv["EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY"] = "selected_block"' in script_text
    assert '$effectiveEnv["EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE"] = "64"' in script_text
    assert '$effectiveEnv["EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES"] = ""' in script_text
    assert 'if ($FormulationProfile -eq "joined_xy_block64_all_templates")' in script_text
    assert '$effectiveEnv["EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY"] = "selected_block_active_guard_joined_xy"' in script_text
    assert 'if ($EnableGhostAwareNoSolvePrechecks)' in script_text
    assert '$effectiveEnv["EXACT_GHOST_OVERLAP_FORCED_DOMAIN_PRECHECK"] = "true"' in script_text
    assert '$effectiveEnv["EXACT_SIGNATURE_MONOTONIC_FORCED_LABEL_PRECHECK"] = "true"' in script_text
    assert '"EXACT_MASTER_CP_MODEL_PRESOLVE"] = "false"' in script_text
    assert '"EXACT_MASTER_CP_MODEL_PROBING_LEVEL"] = ([string]$MasterCpModelProbingLevel)' in script_text
    assert '"EXACT_MASTER_SYMMETRY_LEVEL"] = ([string]$MasterSymmetryLevel)' in script_text
    assert '"EXACT_MASTER_HINT_CONFLICT_LIMIT"] = ([string]$MasterHintConflictLimit)' in script_text
    assert "Stage budgets:" in script_text
    assert "Master params:" in script_text
    assert "Formulation:" in script_text
    assert "Diagnostic semantics: B5A bounded workspace sprint" in script_text
    assert "No-solve prechecks:" in script_text
    assert "Test-FileContainsAll" in script_text
    assert "Requested -FormulationProfile joined_xy_block64_all_templates" in script_text
    assert "cover_choice_joined_x__" in script_text
    assert "joined_xy_target_channel_count" in script_text
    assert "Formulation provenance:" in script_text
    assert "Workspace validation: passed" in script_text
    assert "if ($ValidateWorkspaceOnly)" in script_text
    assert "Requested -EnableGhostAwareNoSolvePrechecks" in script_text
    assert "evaluate_ghost_overlap_forced_domain_conflict" in script_text
    assert "Source provenance:" in script_text
    assert "Precheck caps:" in script_text
    assert "Warm-start caps:" in script_text
    assert "$coordinateValidationBudgetSeconds" in script_text
    assert "$ghostAwareCoordinateValidationBudgetSeconds" in script_text
    assert "$ghostAwarePoseOrderValidationBudgetSeconds" in script_text
    assert "[Math]::Max(0.0, $MandatoryRectanglePrecheckTimeBudgetSeconds)" in script_text
    assert "$stageBudgetSeconds + 300.0" in script_text
    assert "ConvertTo-ProcessArgumentString" in script_text
    assert "System.Diagnostics.ProcessStartInfo" in script_text
    assert "$exitCode = $process.ExitCode" in script_text
    assert "Refusing to run B5A anchor sprint in the repo main path" in script_text
    assert "mark_phase3b_campaign_interrupted.py" in script_text


def test_b5a_presolve_off_runner_delegates_to_short_sprint_profile() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script_text = (
        repo_root / "scripts" / "run_phase3b_b5_anchor_presolve_off_sprint.ps1"
    ).read_text(encoding="utf-8")

    assert "endfield_phase3b_b5_anchor_presolve_off_diagnostic" in script_text
    assert "[double]$CampaignHours = 0.25" in script_text
    assert "[int]$MaxAttempts = 1" in script_text
    assert "[double]$MasterSeconds = 300.0" in script_text
    assert "[switch]$DisableMasterWarmStart" in script_text
    assert "-DisableMasterPresolve" in script_text
    assert '"-MasterCpModelProbingLevel", "0"' in script_text
    assert '"-MasterSymmetryLevel", "0"' in script_text
    assert '"-MasterHintConflictLimit", "0"' in script_text
    assert '"-GhostAwareCoordinateValidationMaxAnchors", "8"' in script_text
    assert '"-GhostAwareCoordinateValidationSeconds", "10"' in script_text
    assert '$runnerArgs += "-DisableMasterWarmStart"' in script_text
    assert '"-MasterSearchBranching", "fixed"' in script_text
    assert '"-DryRun"' in script_text


def test_block64_low_encoding_anchor_probe_runner_locks_best_diagnostic_profile() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script_text = (
        repo_root / "scripts" / "run_phase3b_block64_low_encoding_anchor_probe.ps1"
    ).read_text(encoding="utf-8")

    assert (
        "endfield_phase3b_b5_anchor_presolve_off_1h_no_warm_start_v2_20260419"
        in script_text
    )
    assert '[string]$Candidate = "67x13"' in script_text
    assert '[string]$AnchorIndices = "124"' in script_text
    assert "[double]$TimeLimitSeconds = 300.0" in script_text
    assert "[int]$WorkerCount = 1" in script_text
    assert "[int]$RandomSeed = 1" in script_text
    assert "[int]$LinearizationLevel = 0" in script_text
    assert "[int]$BlockSize = 64" in script_text
    assert '[string]$BlockTemplates = "protocol_storage_box"' in script_text
    assert (
        '[ValidateSet("final_target", "selected_block", "selected_block_active_guard", "selected_block_active_guard_grouped_xy", "selected_block_active_guard_joined_xy")]'
        in script_text
    )
    assert '[string]$BlockGeometry = "final_target"' in script_text
    assert "[switch]$AllBlockTemplates" in script_text
    assert "[switch]$NoWrite" in script_text
    assert "[switch]$DryRun" in script_text

    assert '"EXACT_POWER_FAMILY_LOOKUP_ENCODING" = "linear_shell_guards"' in script_text
    assert '"EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING" = "linear_minmax"' in script_text
    assert '"EXACT_POWER_COVERAGE_WITNESS_ENCODING" = "block_element"' in script_text
    assert '"EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY" = $BlockGeometry' in script_text
    assert '"EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE" = ([string]$BlockSize)' in script_text
    assert '"EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES" = $BlockTemplates' in script_text
    assert 'if ($AllBlockTemplates)' in script_text
    assert '$effectiveEnv["EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES"] = ""' in script_text

    assert "boolean_encoding_level" in script_text
    assert "random_seed = $RandomSeed" in script_text
    assert "max_domain_size_for_linear2_expansion" in script_text
    assert "max_domain_size_when_encoding_eq_neq_constraints" in script_text
    assert "cp_model_use_sat_presolve" in script_text
    assert "find_clauses_that_are_exactly_one" in script_text
    assert "presolve_use_bva" in script_text
    assert '"linearization_level"' in script_text
    assert "$blockTemplateScope = \"all_templates\"" in script_text
    assert (
        'profile_id = "block$($BlockSize)_$($blockTemplateScope)_$($blockGeometryScope)_$($selectedIntervalScope)_low_encoding_fixed_$($WorkerCount)w"'
        in script_text
    )
    assert (
        "block$($BlockSize)_$($blockTemplateScope)_$($blockGeometryScope)_$($selectedIntervalScope)_low_encoding_linearization$($LinearizationLevel)_fixed_$($WorkerCount)w"
        in script_text
    )

    assert "build_proto_reduction.py" in script_text
    assert '"--variants", "base"' in script_text
    assert '"--solver-profile-json", $solverProfileJson' in script_text
    assert '"--no-write"' in script_text
    assert "Diagnostic semantics: forced-anchor probe, not proof source" in script_text
    assert "Phase 3B block-size low-encoding anchor probe" in script_text
    assert "Campaign state does not exist" in script_text
    assert "ConvertTo-ProcessArgumentString" in script_text
    assert "Start-Process" in script_text
    assert "RedirectStandardOutput" in script_text
    assert "RedirectStandardError" in script_text
    assert "WriteAllText" in script_text
    assert "[System.Text.UTF8Encoding]::new($false)" in script_text


def test_b5a_summary_reports_missing_campaign(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "missing_campaign")

    summary = build_phase3b_b5_anchor_sprint_summary(project_root)

    assert summary["metadata"]["source"] == "phase3b_b5_anchor_sprint_summary_v1"
    assert summary["status"]["campaign_present"] is False
    assert summary["status"]["anchor_found"] is False
    assert summary["status"]["outcome"] == "no_campaign_state"
    assert summary["triage"]["blocker_count"] == 0
    assert summary["source_provenance"]["workspace_source_matches_coordinator"] is False
    assert (
        summary["source_provenance"]["precheck_support"]["ghost_overlap_forced_domain"][
            "supported"
        ]
        is False
    )


def test_b5a_summary_reports_source_provenance_and_precheck_support(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "source_provenance")
    master_model = project_root / "src" / "models" / "master_model.py"
    master_model.parent.mkdir(parents=True, exist_ok=True)
    master_model.write_text(
        "\n".join(
            [
                "EXACT_GHOST_OVERLAP_FORCED_DOMAIN_PRECHECK = 'true'",
                "def evaluate_ghost_overlap_forced_domain_conflict(): pass",
                "EXACT_SIGNATURE_MONOTONIC_FORCED_LABEL_PRECHECK = 'true'",
                "def evaluate_signature_monotonic_forced_label_conflict(): pass",
            ]
        ),
        encoding="utf-8",
    )

    summary = build_phase3b_b5_anchor_sprint_summary(project_root)
    provenance = summary["source_provenance"]

    assert provenance["precheck_support"]["ghost_overlap_forced_domain"]["supported"] is True
    assert (
        provenance["precheck_support"]["signature_monotonic_forced_label"]["supported"]
        is True
    )
    assert summary["status"]["source_matches_coordinator"] is False
    assert summary["status"]["attribution_trustworthy_with_current_source"] is False


def test_b5a_summary_reports_certified_anchor_and_telemetry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = _build_exact_project(tmp_path / "certified_anchor")
    write_closed_phase_review_gate(project_root)
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(4, 1)
    campaign.mark_candidate_result(
        4,
        1,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"mode": "certified_exact", "master_status": "CERTIFIED"},
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 4, "h": 1, "area": 4, "anchor_x": 1, "anchor_y": 0},
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
    # best_certified_result() now requires supervisor_seal + publish (PR1 API change #2);
    # this test only needs the fixture data to flow through — read directly from state.
    best_result = campaign.state["final_result"]
    assert best_result is not None
    _write_json(project_root / "data" / "solutions" / "final_solution.json", best_result)
    facility_pools = load_candidate_placements(
        project_root / "data" / "preprocessed" / "candidate_placements.json"
    )
    # For forged-fixture test purposes, persist the canonical blueprint through
    # the explicit test-only helper below the verified publisher boundary.
    persist_canonical_blueprint_for_test(
        project_root,
        build_blueprint_payload_from_certified_result(
            result=best_result,
            facility_pools=facility_pools,
        ),
    )
    # PR1 change: supervisor_seal is now required to pass the resume-state and
    # terminal-evidence validators.  Forged fixtures bypass the seal; patch the
    # five validator names so the manifest export and surface verifier accept the
    # forged state while still enforcing artifact-hash consistency.
    _install_forged_certified_state_acceptance(monkeypatch)
    manifest_payload = delivery_manifest_module.build_certified_delivery_manifest(
        project_root=project_root,
        campaign_state=campaign.state,
        campaign_path=campaign.path,
    )
    _write_json(delivery_manifest_output_path(project_root), manifest_payload)
    append_campaign_wave_summary(
        project_root=project_root,
        campaign_path=campaign.path,
        reset=True,
        wave_summary=build_wave_summary(
            wave_index=1,
            candidate_results=[
                {
                    "candidate_key": "4x1",
                    "status": RUN_STATUS_CERTIFIED,
                    "proof_summary": {
                        "mode": "certified_exact",
                        "master_status": "CERTIFIED",
                    },
                }
            ],
            completed=True,
            failure_reason=None,
            dispatched_candidate_keys=["4x1"],
        ),
    )

    summary = build_phase3b_b5_anchor_sprint_summary(project_root)

    assert summary["status"]["anchor_found"] is True
    assert summary["status"]["outcome"] == "anchor_found"
    assert summary["anchor"]["candidate_key"] == "4x1"
    assert summary["anchor"]["objective"] == {"area": 4, "min_side": 1}
    assert summary["telemetry"]["wave_count"] == 1
    assert "terminal exhaustion" in summary["status"]["recommendation"]


def test_b5a_summary_routes_unknown_to_triage(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "unknown_triage")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(3, 1)
    campaign.mark_candidate_result(
        3,
        1,
        RUN_STATUS_UNKNOWN,
        proof_summary={
            "mode": "certified_exact",
            "master_status": "UNKNOWN",
            "master_last_solve": {"status": "UNKNOWN", "branches": 0, "conflicts": 0},
        },
    )
    campaign.mark_campaign_stopped("candidate_returned_unknown", status=RUN_STATUS_UNKNOWN)
    persist_forged_terminal_certified_state(campaign)

    summary = build_phase3b_b5_anchor_sprint_summary(project_root)

    assert summary["status"]["anchor_found"] is False
    assert summary["status"]["outcome"] == "triage_required"
    assert summary["triage"]["blocker_count"] == 1
    assert summary["triage"]["top_blockers"][0]["classification"] == "master_unknown"
    assert summary["triage"]["top_blockers"][0]["blocker_subtype"] == "master_zero_branch_unknown"

    markdown = render_phase3b_b5_anchor_sprint_markdown(summary)
    text = render_phase3b_b5_anchor_sprint_text(summary)
    assert "master_zero_branch_unknown" in markdown
    assert "triage_required" in text


def test_b5a_summary_includes_runtime_group_packing_diagnostic(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "runtime_group_packing")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(69, 19)
    campaign.mark_candidate_result(
        69,
        19,
        RUN_STATUS_UNKNOWN,
        proof_summary={
            "mode": "certified_exact",
            "master_status": "UNKNOWN",
            "master_start_feasibility": {
                "ghost_anchor_compatible_count": 0,
                "ghost_anchor_hint_status": "none_compatible",
            },
        },
    )
    campaign.mark_campaign_stopped("candidate_returned_unknown", status=RUN_STATUS_UNKNOWN)
    persist_forged_terminal_certified_state(campaign)
    _write_json(
        project_root
        / ".artifacts"
        / "phase3b_runtime_group_packing"
        / "runtime_group_packing_69x19.json",
        {
            "metadata": {
                "source": "phase3b_runtime_group_packing_diagnostic_v1"
            },
            "candidate": {"key": "69x19"},
            "status": {
                "evaluated": True,
                "outcome": "diagnostic_group_packing_infeasible",
            },
            "diagnostics": {"group_packing_blockers": {"blocker_count": 3}},
            "campaign_state_unchanged": True,
        },
    )

    summary = build_phase3b_b5_anchor_sprint_summary(project_root)

    assert summary["runtime_group_packing"]["present"] is True
    assert summary["runtime_group_packing"]["diagnostic_count"] == 1
    assert summary["runtime_group_packing"]["current_candidate_keys"] == ["69x19"]
    assert summary["runtime_group_packing"]["relevant_diagnostic_count"] == 1
    assert summary["runtime_group_packing"]["stale_diagnostic_count"] == 0
    assert summary["runtime_group_packing"]["reports"][0] == {
        "path": ".artifacts/phase3b_runtime_group_packing/runtime_group_packing_69x19.json",
        "candidate_key": "69x19",
        "outcome": "diagnostic_group_packing_infeasible",
        "evaluated": True,
        "blocker_count": 3,
        "campaign_state_unchanged": True,
    }
    assert summary["runtime_group_packing"]["relevant_reports"] == [
        summary["runtime_group_packing"]["reports"][0]
    ]
    assert summary["runtime_group_packing"]["stale_reports"] == []
    assert "Runtime group-packing diagnostics: 1" in render_phase3b_b5_anchor_sprint_markdown(summary)
    assert (
        "Runtime group-packing diagnostics for current candidate: 1"
        in render_phase3b_b5_anchor_sprint_markdown(summary)
    )
    assert "runtime_group_packing_diagnostic_count=1" in render_phase3b_b5_anchor_sprint_text(summary)
    assert "runtime_group_packing_relevant_diagnostic_count=1" in render_phase3b_b5_anchor_sprint_text(summary)


def test_b5a_summary_distinguishes_stale_runtime_group_packing_diagnostics(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "stale_runtime_group_packing")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(67, 13)
    campaign.mark_candidate_result(
        67,
        13,
        RUN_STATUS_UNKNOWN,
        proof_summary={
            "mode": "certified_exact",
            "master_status": "UNKNOWN",
            "master_start_feasibility": {
                "ghost_anchor_compatible_count": 0,
                "ghost_anchor_hint_status": "none_compatible",
            },
        },
    )
    campaign.mark_campaign_stopped("candidate_returned_unknown", status=RUN_STATUS_UNKNOWN)
    persist_forged_terminal_certified_state(campaign)
    _write_json(
        project_root
        / ".artifacts"
        / "phase3b_runtime_group_packing"
        / "runtime_group_packing_69x19.json",
        {
            "metadata": {
                "source": "phase3b_runtime_group_packing_diagnostic_v1"
            },
            "candidate": {"key": "69x19"},
            "status": {
                "evaluated": True,
                "outcome": "diagnostic_group_packing_infeasible",
            },
            "diagnostics": {"group_packing_blockers": {"blocker_count": 3}},
            "campaign_state_unchanged": True,
        },
    )

    summary = build_phase3b_b5_anchor_sprint_summary(project_root)

    assert summary["runtime_group_packing"]["diagnostic_count"] == 1
    assert summary["runtime_group_packing"]["current_candidate_keys"] == ["67x13"]
    assert summary["runtime_group_packing"]["relevant_diagnostic_count"] == 0
    assert summary["runtime_group_packing"]["stale_diagnostic_count"] == 1
    assert summary["runtime_group_packing"]["relevant_reports"] == []
    assert summary["runtime_group_packing"]["stale_reports"][0]["candidate_key"] == "69x19"
    assert "runtime_group_packing_relevant_diagnostic_count=0" in render_phase3b_b5_anchor_sprint_text(summary)


def test_b5a_summary_includes_pose_order_validation_rejections(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "pose_order_validation")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(69, 19)
    proof_summary = {
        "mode": "certified_exact",
        "master_status": "UNKNOWN",
        "master_warm_start": {
            "used_greedy_hint": True,
            "greedy_hint_instances": 266,
            "master_hinted_literals": 0,
            "ghost_anchor_hint_applied": False,
            "ghost_anchor_hint_idx": None,
            "ghost_anchor_hint_status": "none_compatible",
            "warm_start_strategy": "global_greedy_fallback",
            "ghost_aware_anchor_attempt_count": 51,
            "ghost_aware_anchor_selected_idx": None,
            "ghost_aware_complete_mandatory_hint": False,
            "ghost_aware_hint_instances": 0,
            "ghost_aware_pose_order_portfolio_attempted": True,
            "ghost_aware_pose_order_portfolio_success": False,
            "ghost_aware_pose_order_portfolio_attempt_count": 51,
            "ghost_aware_pose_order_portfolio_failed_anchor_count": 51,
            "ghost_aware_pose_order_portfolio_failure_reason_counts": {
                "coordinate_validation_infeasible": 1
            },
            "ghost_aware_pose_order_portfolio_failure_samples": [
                {
                    "anchor_idx": 118,
                    "ordering": "y_then_x",
                    "source": "coordinate_validation",
                    "failure_reason": "coordinate_validation_infeasible",
                    "status": "INFEASIBLE",
                }
            ],
            "ghost_aware_pose_order_validation_attempt_count": 1,
            "ghost_aware_pose_order_validation_rejected_count": 1,
            "ghost_aware_pose_order_validation_last_status": "INFEASIBLE",
            "ghost_aware_pose_order_validation_last_reason": "infeasible",
        },
    }
    campaign.mark_candidate_result(69, 19, RUN_STATUS_UNKNOWN, proof_summary=proof_summary)
    campaign.mark_campaign_stopped("candidate_returned_unknown", status=RUN_STATUS_UNKNOWN)
    persist_forged_terminal_certified_state(campaign)
    append_campaign_wave_summary(
        project_root=project_root,
        campaign_path=campaign.path,
        reset=True,
        wave_summary=build_wave_summary(
            wave_index=1,
            candidate_results=[
                {
                    "candidate_key": "69x19",
                    "status": RUN_STATUS_UNKNOWN,
                    "proof_summary": proof_summary,
                }
            ],
            completed=True,
            failure_reason=None,
            dispatched_candidate_keys=["69x19"],
        ),
    )

    summary = build_phase3b_b5_anchor_sprint_summary(project_root)

    assert summary["pose_order_validation"] == {
        "attempt_count": 1,
        "rejected_count": 1,
        "portfolio_attempted_count": 1,
        "portfolio_success_count": 0,
        "portfolio_attempt_count_sum": 51,
        "portfolio_failure_sample_count": 1,
        "portfolio_failure_samples": [
            {
                "anchor_idx": 118,
                "ordering": "y_then_x",
                "source": "coordinate_validation",
                "failure_reason": "coordinate_validation_infeasible",
                "status": "INFEASIBLE",
                "candidate_key": "69x19",
            }
        ],
        "status_counts": {"INFEASIBLE": 1},
        "reason_counts": {"infeasible": 1},
        "selected_ordering_counts": {},
    }
    assert "Pose-order validation rejected: 1" in render_phase3b_b5_anchor_sprint_markdown(summary)
    assert "Pose-Order Portfolio Failure Samples" in render_phase3b_b5_anchor_sprint_markdown(summary)
    assert "pose_order_validation_rejected_count=1" in render_phase3b_b5_anchor_sprint_text(summary)
    assert "pose_order_portfolio_failure_sample_count=1" in render_phase3b_b5_anchor_sprint_text(summary)


def test_b5a_summary_reports_worker_failure(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "worker_failure")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_campaign_stopped("worker_process_failed", status=RUN_STATUS_UNKNOWN)
    persist_forged_terminal_certified_state(campaign)
    append_campaign_wave_summary(
        project_root=project_root,
        campaign_path=campaign.path,
        reset=True,
        wave_summary=build_wave_summary(
            wave_index=1,
            candidate_results=[],
            completed=False,
            failure_reason="worker_process_failed:pid=1:exitcode=1",
            dispatched_candidate_keys=["3x1"],
        ),
    )

    summary = build_phase3b_b5_anchor_sprint_summary(project_root)

    assert summary["status"]["outcome"] == "orchestration_failure"
    assert summary["telemetry"]["wave_count"] == 1
    assert summary["triage"]["top_blockers"][0]["classification"] == "orchestration_failure"
    assert summary["triage"]["top_blockers"][0]["stop_stage"] == "orchestration"


def test_b5a_summary_reports_interrupted_running_candidate(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "running_candidate")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(3, 1)
    persist_forged_terminal_certified_state(campaign)

    summary = build_phase3b_b5_anchor_sprint_summary(project_root)

    assert summary["status"]["anchor_found"] is False
    assert summary["status"]["outcome"] == "interrupted_running_candidate"
    assert "did not terminate cleanly" in summary["status"]["recommendation"]
    assert summary["campaign"]["candidate_status_counts"] == {"RUNNING": 1}


def test_campaign_repair_marks_running_candidate_as_operator_interrupted_unknown(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "repair_running")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(3, 1)
    persist_forged_terminal_certified_state(campaign)

    result = mark_running_exact_campaign_candidates_interrupted(
        project_root,
        reason="b5a_wall_timeout",
        detail="test timeout",
    )
    repaired = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)
    record = repaired.state["candidates"]["3x1"]

    assert result["interrupted_candidate_keys"] == ["3x1"]
    assert record["status"] == RUN_STATUS_UNKNOWN
    assert record["finished_at"] is not None
    assert record["proof_summary"]["operator_interruption"]["reason"] == "b5a_wall_timeout"
    assert repaired.state["last_stop_reason"]["reason"] == "b5a_wall_timeout"

    summary = build_phase3b_b5_anchor_sprint_summary(project_root)
    assert summary["status"]["outcome"] == "triage_required"
    assert summary["triage"]["top_blockers"][0]["classification"] == "orchestration_failure"
    assert summary["triage"]["top_blockers"][0]["stop_reason"] == "b5a_wall_timeout"


def test_campaign_repair_marks_campaign_stopped_without_running_candidate(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "repair_no_running")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_result(
        3,
        1,
        RUN_STATUS_INFEASIBLE,
        proof_summary={"master_status": "INFEASIBLE"},
        exact_safe_cuts=[],
        loaded_exact_safe_cut_count=0,
        generated_exact_safe_cut_count=0,
    )
    persist_forged_terminal_certified_state(campaign)

    result = mark_running_exact_campaign_candidates_interrupted(
        project_root,
        reason="b5a_wall_timeout",
        detail="precheck timeout",
    )
    repaired = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=True)

    assert result["interrupted_candidate_keys"] == []
    assert result["campaign_marked_stopped"] is True
    assert repaired.state["final_status"] == RUN_STATUS_UNKNOWN
    assert repaired.state["last_stop_reason"]["reason"] == "b5a_wall_timeout"
    record = repaired.state["candidates"]["3x1"]
    assert record["status"] == RUN_STATUS_UNKNOWN
    assert (
        record["proof_summary"]["resume_sanitized_reason"]
        == "infeasible_candidate_requires_fresh_replay_after_checkpoint_resume"
    )


def test_b5a_summary_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = _build_exact_project(tmp_path / "cli")
    script_path = Path(__file__).resolve().parents[4] / "scripts" / "summarize_phase3b_b5_anchor_sprint.py"
    output_dir = tmp_path / "summary_output"
    no_write_dir = tmp_path / "summary_no_write"

    no_write_result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(no_write_dir),
            "--no-write",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert no_write_result.returncode == 0
    assert "phase3b b5a anchor sprint summary" in no_write_result.stdout
    assert not no_write_dir.exists()

    write_result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert write_result.returncode == 0
    assert (output_dir / "operator_summary.json").exists()
    assert (output_dir / "operator_summary.md").exists()
    assert (output_dir / "operator_summary.txt").exists()
    payload = json.loads((output_dir / "operator_summary.json").read_text(encoding="utf-8"))
    assert payload["status"]["outcome"] == "no_campaign_state"

def test_b5a_anchor_sprint_does_not_promote_stale_certified_final_result(
    tmp_path: Path,
) -> None:
    project_root = _build_exact_project(tmp_path / "stale_certified_anchor")
    campaign = ExactCampaign.load_or_create(project_root, campaign_hours=1.0, resume=False)
    campaign.mark_candidate_started(4, 1)
    campaign.mark_candidate_result(
        4,
        1,
        RUN_STATUS_CERTIFIED,
        solution=_certified_solution(),
        proof_summary={"mode": "certified_exact", "master_status": "CERTIFIED"},
    )
    campaign.state["final_result"] = {
        "ghost_rect": {"w": 4, "h": 1, "area": 4, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": _certified_placement(),
        "search_status": RUN_STATUS_CERTIFIED,
    }
    campaign.mark_campaign_stopped("candidate_returned_unknown", status=RUN_STATUS_UNKNOWN)
    campaign.state["final_status"] = RUN_STATUS_CERTIFIED
    persist_forged_terminal_certified_state(campaign)

    summary = build_phase3b_b5_anchor_sprint_summary(project_root)

    assert summary["status"]["anchor_found"] is False
    assert summary["anchor"] is None
