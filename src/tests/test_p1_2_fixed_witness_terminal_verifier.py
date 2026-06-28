from __future__ import annotations

import copy
from dataclasses import replace
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

import src.search.certified_frontier as certified_frontier_module
import src.search.exact_campaign as exact_campaign_module
import src.search.terminal_fixed_witness_capsule as fixed_witness_capsule_module
import src.search.terminal_fixed_witness_verifier as fixed_witness_module
from src.models.cut_manager import RUN_STATUS_CERTIFIED
from src.search.candidate_proof_replay import (
    CANDIDATE_PROOF_FIELD,
    build_candidate_replay_proof,
    canonical_digest,
)
from src.search.certified_frontier import (
    TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
    build_sink_verified_terminal_frontier_evidence,
    build_terminal_frontier_evidence,
    candidate_generation_kwargs,
    generate_candidate_sizes,
    terminal_frontier_evidence_violation,
)
from src.search.exact_campaign import (
    CANDIDATE_PROPOSED_STATUS,
    ExactCampaign,
    TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    compute_exact_artifact_hashes,
    terminal_certified_final_result_project_precheck_violation,
    terminal_certified_final_result_violation_for_project,
)
from src.search.terminal_fixed_witness_capsule import (
    TERMINAL_FIXED_WITNESS_CAPSULE_AUTHORITY,
    TERMINAL_FIXED_WITNESS_CAPSULE_RESPONSE_SCHEMA_VERSION,
    build_terminal_fixed_witness_projection_at_sink,
)
from src.search.terminal_fixed_witness_verifier import (
    canonical_state_bytes_for_fixed_witness,
    project_terminal_fixed_witness_records_for_sink,
    verify_terminal_fixed_witness,
)
from src.tests.certified_frontier_helpers import install_accepting_l0_supervisor_seal


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )


def _json_copy(payload: Any) -> Any:
    return json.loads(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    )


def _build_tiny_project(root: Path) -> Path:
    _write_json(
        root / "rules" / "canonical_rules.json",
        {
            "globals": {
                "grid": {"width": 2, "height": 1},
                "empty_rectangle": {
                    "objective": "max_lex_area_min_side",
                    "min_side_admissibility": 1,
                },
            },
            "facility_templates": {
                "tiny_facility": {
                    "dimensions": {"w": 1, "h": 1},
                    "needs_power": False,
                }
            },
            "commodity_metadata": {},
        },
    )
    _write_json(
        root / "data" / "preprocessed" / "candidate_placements.json",
        {
            "facility_pools": {
                "tiny_facility": [
                    {
                        "pose_id": "tiny_x0_y0",
                        "anchor": {"x": 0, "y": 0},
                        "pose_params": {"orientation": 0, "port_mode": "default"},
                        "occupied_cells": [[0, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    },
                    {
                        "pose_id": "tiny_x1_y0",
                        "anchor": {"x": 1, "y": 0},
                        "pose_params": {"orientation": 0, "port_mode": "default"},
                        "occupied_cells": [[1, 0]],
                        "input_port_cells": [],
                        "output_port_cells": [],
                        "power_coverage_cells": None,
                    },
                ]
            }
        },
    )
    instances = [
        {
            "instance_id": "tiny_001",
            "facility_type": "tiny_facility",
            "operation_type": "",
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_modes": ["certified_exact"],
        }
    ]
    _write_json(root / "data" / "preprocessed" / "mandatory_exact_instances.json", instances)
    _write_json(root / "data" / "preprocessed" / "generic_io_requirements.json", {
        "required_generic_inputs": {},
        "required_generic_outputs": {},
    })
    return root


def _solution(*, ghost_anchor_x: int = 1, ghost_pose_idx: int = 1) -> dict[str, Any]:
    return {
        "ghost_pick": {
            "instance_id": "ghost_pick",
            "facility_type": "ghost_rect",
            "pose_idx": ghost_pose_idx,
            "pose_id": f"ghost_anchor::{ghost_anchor_x},0",
            "anchor": {"x": ghost_anchor_x, "y": 0},
            "is_mandatory": False,
            "bound_type": "ghost_rect",
            "solve_mode": "certified_exact",
        },
        "tiny_001": {
            "instance_id": "tiny_001",
            "facility_type": "tiny_facility",
            "operation_type": "",
            "pose_idx": 0,
            "pose_id": "tiny_x0_y0",
            "anchor": {"x": 0, "y": 0},
            "is_mandatory": True,
            "bound_type": "exact",
            "solve_mode": "certified_exact",
        },
    }


def _candidate_generation() -> dict[str, Any]:
    return {
        "max_w": 2,
        "max_h": 1,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 1,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 1,
        "min_side_admissibility": 1,
    }


def _state(solution: Mapping[str, Any] | None = None) -> dict[str, Any]:
    record_solution = _json_copy(solution or _solution())
    final_result = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 1, "anchor_y": 0},
        "placement_solution": {
            "tiny_001": _json_copy(record_solution["tiny_001"]),
        },
        "search_status": RUN_STATUS_CERTIFIED,
        "search_stats": {
            "attempts": 1,
            "explicit_candidate_solves": 1,
            "solve_mode": "certified_exact",
            "campaign_resumed": False,
            "frontier_peak_size": 1,
            "derived_pruned_candidates": 0,
        },
    }
    candidate_record = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1},
        "attempts": 1,
        "status": RUN_STATUS_CERTIFIED,
        "proof_summary": {},
        "exact_safe_cuts": [],
        "loaded_exact_safe_cut_count": 0,
        "generated_exact_safe_cut_count": 0,
        "solution": record_solution,
        CANDIDATE_PROOF_FIELD: {"solution_digest": canonical_digest(record_solution)},
    }
    candidate_generation = _candidate_generation()
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    state = {
        "schema_version": 5,
        "solve_mode": "certified_exact",
        "declare_mode": "strict",
        "artifact_hashes": {},
        "proof_summary_schema_version": 1,
        "final_result": final_result,
        "final_status": RUN_STATUS_CERTIFIED,
        "last_stop_reason": {
            "reason": TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
            "status": RUN_STATUS_CERTIFIED,
            "updated_at": "2026-06-22T00:00:00Z",
        },
        "candidates": {"1x1": candidate_record},
    }
    state["terminal_frontier_evidence"] = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=state["candidates"],
        final_result=final_result,
        candidate_generation=candidate_generation,
    )
    return state


def _refresh_terminal_evidence(state: dict[str, Any]) -> None:
    candidate_generation = _candidate_generation()
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    state["terminal_frontier_evidence"] = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=state["candidates"],
        final_result=state["final_result"],
        candidate_generation=candidate_generation,
    )


def _fresh_failure_verdict(state: Mapping[str, Any], project_root: Path, reason: str):
    verdict = verify_terminal_fixed_witness(
        state=state,
        project_root=project_root,
        serialized_state_bytes=canonical_state_bytes_for_fixed_witness(state),
    )
    return replace(
        verdict,
        publishable=False,
        projected_status="UNPROVEN",
        reason=reason,
    )


def _patch_sink_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_project_candidate_records_for_sink(
        *,
        state: Mapping[str, Any],
        **_kwargs: Any,
    ):
        return _json_copy(state.get("candidates", {})), {}

    monkeypatch.setattr(
        exact_campaign_module,
        "project_candidate_records_for_sink",
        fake_project_candidate_records_for_sink,
    )
    monkeypatch.setattr(
        certified_frontier_module,
        "project_candidate_records_for_sink",
        fake_project_candidate_records_for_sink,
    )


def _patch_capsule_response(
    monkeypatch: pytest.MonkeyPatch,
    *,
    root: Path,
    state: Mapping[str, Any],
    verdict: Any,
) -> None:
    def fake_invoke(
        *,
        project_root: Path,
        authority_state: Mapping[str, Any],
        expected_artifact_hashes: Mapping[str, str],
        expected_source_digest: str,
        nonce: str,
    ) -> Mapping[str, Any]:
        assert project_root == root.resolve()
        assert authority_state["final_result"] == state["final_result"]
        assert expected_artifact_hashes == state["artifact_hashes"]
        assert expected_source_digest == state["artifact_hashes"]["certified_exact_source_tree"]
        return {
            "schema_version": TERMINAL_FIXED_WITNESS_CAPSULE_RESPONSE_SCHEMA_VERSION,
            "authority": TERMINAL_FIXED_WITNESS_CAPSULE_AUTHORITY,
            "nonce": nonce,
            "project_root": str(root.resolve()),
            "artifact_hashes": dict(state["artifact_hashes"]),
            "source_digest": state["artifact_hashes"]["certified_exact_source_tree"],
            "verdict": verdict.to_dict(),
        }

    monkeypatch.setattr(
        fixed_witness_capsule_module,
        "_invoke_isolated_capsule",
        fake_invoke,
    )


def _setup_sealed_campaign(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
    state: dict[str, Any],
) -> ExactCampaign:
    """Create a supervisor-sealed campaign from a CERTIFIED-ready state dict.

    The state must have final_result, candidates, terminal_frontier_evidence, and
    artifact_hashes already populated (as produced by _state() + compute_exact_artifact_hashes).
    This function promotes the state to CANDIDATE_PROPOSED, writes it to disk as a proposal,
    installs the test-only L0 supervisor seal, then calls supervisor_seal() to produce
    a real, checksum-validated seal record on disk.

    The returned campaign has .state (the sealed CERTIFIED state) and .path (the checkpoint
    path). Callers should pass both to terminal_certified_final_result_violation_for_project.
    """
    campaign = ExactCampaign.load_or_create(root, campaign_hours=1.0, resume=False)
    # Inject the test evidence into the fresh campaign state
    proposal_final_result = _json_copy(state.get("final_result") or {})
    proposal_final_result["search_status"] = CANDIDATE_PROPOSED_STATUS
    campaign.state["final_result"] = proposal_final_result
    campaign.state["candidates"] = _json_copy(state.get("candidates", {}))
    campaign.state["artifact_hashes"] = _json_copy(state.get("artifact_hashes", {}))
    # Set supervisor proposal run id before marking stopped (preserves terminal evidence)
    run_id = campaign.set_supervisor_proposal_run_id()
    campaign.mark_campaign_stopped(
        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON, status=CANDIDATE_PROPOSED_STATUS
    )
    # Set terminal_frontier_evidence after mark_campaign_stopped (safe: terminal_proposal stays True)
    campaign.state["terminal_frontier_evidence"] = _json_copy(
        state.get("terminal_frontier_evidence")
    )
    candidate_record = campaign.state["candidates"]["1x1"]
    candidate_record[CANDIDATE_PROOF_FIELD] = build_candidate_replay_proof(
        campaign,
        1,
        1,
        RUN_STATUS_CERTIFIED,
        solution=candidate_record["solution"],
    )
    certified_projection_state = _json_copy(campaign.state)
    certified_projection_state["final_result"]["search_status"] = RUN_STATUS_CERTIFIED
    verdict = verify_terminal_fixed_witness(
        state=certified_projection_state,
        project_root=root,
        serialized_state_bytes=canonical_state_bytes_for_fixed_witness(
            certified_projection_state
        ),
    )
    assert verdict.publishable is True
    durable_candidate_records = _json_copy(campaign.state["candidates"])
    fixed_witness_module._apply_terminal_fixed_witness_audit_fields(
        durable_candidate_records["1x1"],
        verdict=verdict,
        publishable=True,
        projected_status=RUN_STATUS_CERTIFIED,
        rejected_reason=verdict.reason,
    )
    campaign.state["candidates"] = durable_candidate_records
    campaign.save()
    campaign.write_proposal_ready_marker(run_id=run_id, exit_code=0)

    install_accepting_l0_supervisor_seal(monkeypatch, project_root=root)
    # Seal: mints the supervisor_seal block, writes to disk, runs post-commit disk validation
    campaign.supervisor_seal()
    return campaign


def test_fixed_witness_rejects_binding_routing_witness_split(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _state()

    class SplitRoutingSubproblem:
        def __init__(self) -> None:
            self.grid = type(
                "Grid",
                (),
                {
                    "port_specs": [
                        {
                            "instance_id": "different_assignment",
                            "x": 0,
                            "y": 0,
                            "dir": "E",
                            "type": "out",
                            "commodity": "ore",
                        }
                    ],
                    "occupied_owner_by_cell": {(0, 0): "tiny_001"},
                },
            )()
            self.build_stats = {}

        @classmethod
        def from_placement_core(cls, *_args: Any, **_kwargs: Any):
            return cls()

        def build(self) -> None:
            self.build_stats = {}

        def solve(self, *, time_limit: float) -> str:
            return "FEASIBLE"

    monkeypatch.setattr(
        fixed_witness_module,
        "RoutingSubproblem",
        SplitRoutingSubproblem,
    )

    verdict = verify_terminal_fixed_witness(
        state=state,
        project_root=root,
        serialized_state_bytes=canonical_state_bytes_for_fixed_witness(state),
    )
    projection = project_terminal_fixed_witness_records_for_sink(
        candidate_records=_json_copy(state["candidates"]),
        final_result=state["final_result"],
        verdict=verdict,
    )

    assert verdict.publishable is False
    assert verdict.reason == "terminal_fixed_witness_routing_port_specs_mismatch"
    assert projection.candidate_records["1x1"]["status"] == "UNPROVEN"
    assert projection.publishable is False


def test_fixed_witness_rejects_non_r_star_ghost_origin(tmp_path: Path) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _state(_solution(ghost_anchor_x=0, ghost_pose_idx=0))

    verdict = verify_terminal_fixed_witness(
        state=state,
        project_root=root,
        serialized_state_bytes=canonical_state_bytes_for_fixed_witness(state),
    )

    assert verdict.publishable is False
    assert verdict.projected_status == "UNPROVEN"


def test_fixed_witness_timeout_unknown_demotes_unproven(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _state()

    class TimeoutBindingModel:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def build(self) -> None:
            pass

        def solve(self, *, time_limit_seconds: float) -> str:
            return "TIMEOUT"

    monkeypatch.setattr(fixed_witness_module, "PortBindingModel", TimeoutBindingModel)

    verdict = verify_terminal_fixed_witness(
        state=state,
        project_root=root,
        serialized_state_bytes=canonical_state_bytes_for_fixed_witness(state),
    )
    projection = project_terminal_fixed_witness_records_for_sink(
        candidate_records=_json_copy(state["candidates"]),
        final_result=state["final_result"],
        verdict=verdict,
    )

    assert verdict.reason == "terminal_fixed_witness_binding_not_feasible"
    assert verdict.binding_status == "TIMEOUT"
    assert verdict.projected_status == "UNPROVEN"
    assert projection.publishable is False
    assert projection.candidate_records["1x1"]["status"] != "INFEASIBLE"


def test_fixed_witness_binding_infeasible_demotes_unproven_not_infeasible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _state()

    class InfeasibleBindingModel:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def build(self) -> None:
            pass

        def solve(self, *, time_limit_seconds: float) -> str:
            return "INFEASIBLE"

    monkeypatch.setattr(fixed_witness_module, "PortBindingModel", InfeasibleBindingModel)

    verdict = verify_terminal_fixed_witness(
        state=state,
        project_root=root,
        serialized_state_bytes=canonical_state_bytes_for_fixed_witness(state),
    )
    projection = project_terminal_fixed_witness_records_for_sink(
        candidate_records=_json_copy(state["candidates"]),
        final_result=state["final_result"],
        verdict=verdict,
    )

    assert verdict.reason == "terminal_fixed_witness_binding_not_feasible"
    assert verdict.binding_status == "INFEASIBLE"
    assert verdict.projected_status == "UNPROVEN"
    assert projection.publishable is False
    assert projection.candidate_records["1x1"]["status"] == "UNPROVEN"
    assert projection.candidate_records["1x1"]["status"] != "INFEASIBLE"
    assert "solution" not in projection.candidate_records["1x1"]
    assert CANDIDATE_PROOF_FIELD not in projection.candidate_records["1x1"]


def test_fixed_witness_rejects_consistent_tamper_after_precheck_accepts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _state()
    tampered_solution = _solution(ghost_anchor_x=0, ghost_pose_idx=0)
    tampered_solution["tiny_001"].update(
        {
            "pose_idx": 1,
            "pose_id": "tiny_x1_y0",
            "anchor": {"x": 1, "y": 0},
        }
    )
    state["final_result"]["ghost_rect"]["anchor_x"] = 0
    state["final_result"]["placement_solution"]["tiny_001"] = _json_copy(
        tampered_solution["tiny_001"]
    )
    state["candidates"]["1x1"]["solution"] = _json_copy(tampered_solution)
    state["candidates"]["1x1"][CANDIDATE_PROOF_FIELD]["solution_digest"] = (
        canonical_digest(tampered_solution)
    )
    _refresh_terminal_evidence(state)

    class InfeasibleOnTamperedBindingModel:
        def __init__(self, *, placement_solution: Mapping[str, Any], **_kwargs: Any) -> None:
            self.placement_solution = placement_solution

        def build(self) -> None:
            pass

        def solve(self, *, time_limit_seconds: float) -> str:
            assert self.placement_solution["tiny_001"]["pose_idx"] == 1
            return "INFEASIBLE"

    assert (
        terminal_certified_final_result_project_precheck_violation(
            state,
            project_root=root,
        )
        is None
    )

    monkeypatch.setattr(
        fixed_witness_module,
        "PortBindingModel",
        InfeasibleOnTamperedBindingModel,
    )
    verdict = verify_terminal_fixed_witness(
        state=state,
        project_root=root,
        serialized_state_bytes=canonical_state_bytes_for_fixed_witness(state),
    )
    projection = project_terminal_fixed_witness_records_for_sink(
        candidate_records=_json_copy(state["candidates"]),
        final_result=state["final_result"],
        verdict=verdict,
    )

    assert verdict.reason == "terminal_fixed_witness_binding_not_feasible"
    assert verdict.binding_status == "INFEASIBLE"
    assert projection.publishable is False
    assert projection.candidate_records["1x1"]["status"] == "UNPROVEN"


def test_fixed_witness_round_trip_rejects_post_write_tampered_witness_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    memory_state = _state()
    disk_state = _json_copy(memory_state)
    disk_state["candidates"]["1x1"]["solution"]["tiny_001"]["pose_idx"] = 1
    campaign_path = tmp_path / "campaign.json"
    _write_json(campaign_path, disk_state)
    _patch_sink_replay(monkeypatch)

    reason = terminal_certified_final_result_violation_for_project(
        memory_state,
        project_root=root,
        campaign_path=campaign_path,
    )

    assert reason == "terminal_certified_in_memory_disk_divergence"


def test_fixed_witness_projection_copy_failure_demotes_unproven() -> None:
    state = _state()

    projection = project_terminal_fixed_witness_records_for_sink(
        candidate_records={"1x1": {"bad": float("nan")}},
        final_result=state["final_result"],
        verdict=None,
    )

    assert projection.publishable is False
    assert projection.projected_status == "UNPROVEN"
    assert projection.candidate_records == {}
    assert projection.rejected_reason == (
        "terminal_fixed_witness_projection_records_invalid:ValueError"
    )


def test_fixed_witness_does_not_mutate_record_solution_or_solution_digest(
    tmp_path: Path,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _state()
    before_solution = _json_copy(state["candidates"]["1x1"]["solution"])
    before_solution_digest = canonical_digest(before_solution)
    before_proof_digest = state["candidates"]["1x1"][CANDIDATE_PROOF_FIELD]["solution_digest"]

    verdict = verify_terminal_fixed_witness(
        state=state,
        project_root=root,
        serialized_state_bytes=canonical_state_bytes_for_fixed_witness(state),
    )

    assert verdict.publishable is True
    assert state["candidates"]["1x1"]["solution"] == before_solution
    assert canonical_digest(state["candidates"]["1x1"]["solution"]) == before_solution_digest
    assert state["candidates"]["1x1"][CANDIDATE_PROOF_FIELD]["solution_digest"] == before_proof_digest


def test_fixed_witness_accepts_valid_r_star_pi_star(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _state()
    state["artifact_hashes"] = compute_exact_artifact_hashes(root)
    _patch_sink_replay(monkeypatch)

    verdict = verify_terminal_fixed_witness(
        state=state,
        project_root=root,
        serialized_state_bytes=canonical_state_bytes_for_fixed_witness(state),
    )
    projection = build_terminal_fixed_witness_projection_at_sink(
        state=state,
        project_root=root,
        candidate_records=_json_copy(state["candidates"]),
        final_result=state["final_result"],
    )
    # Validator now requires a checkpoint with a real supervisor_seal; set one up
    sealed = _setup_sealed_campaign(monkeypatch, root, state)
    reason = terminal_certified_final_result_violation_for_project(
        sealed.state,
        project_root=root,
        campaign_path=sealed.path,
    )

    assert verdict.publishable is True
    assert projection.candidate_records["1x1"]["status"] == RUN_STATUS_CERTIFIED
    assert projection.publishable is True
    assert reason is None


def test_fixed_witness_rejects_connector_cell_occupied_by_other_body(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _state()

    class PortCollisionBindingModel:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def build(self) -> None:
            pass

        def solve(self, *, time_limit_seconds: float) -> str:
            return "FEASIBLE"

        def extract_selection(self) -> dict[str, Any]:
            return {"binding_choice": {"port_owner": 0}, "generic_inputs": {}, "generic_outputs": {}}

        def extract_port_specs(self) -> list[dict[str, Any]]:
            return [
                {
                    "instance_id": "port_owner",
                    "x": 0,
                    "y": 0,
                    "dir": "E",
                    "type": "out",
                    "commodity": "ore",
                }
            ]

    monkeypatch.setattr(
        fixed_witness_module,
        "PortBindingModel",
        PortCollisionBindingModel,
    )

    verdict = verify_terminal_fixed_witness(
        state=state,
        project_root=root,
        serialized_state_bytes=canonical_state_bytes_for_fixed_witness(state),
    )

    assert verdict.publishable is False
    assert verdict.reason == "terminal_fixed_witness_connector_cell_occupied_by_other_body"


def test_fixed_witness_rejects_forged_publishable_verdict_on_unchanged_bad_witness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _state()
    state["candidates"]["1x1"]["proof_summary"].update(
        {
            "terminal_fixed_witness_publishable": True,
            "terminal_fixed_witness_projected_status": "CERTIFIED",
        }
    )
    _patch_sink_replay(monkeypatch)

    class TimeoutBindingModel:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def build(self) -> None:
            pass

        def solve(self, *, time_limit_seconds: float) -> str:
            return "TIMEOUT"

    monkeypatch.setattr(fixed_witness_module, "PortBindingModel", TimeoutBindingModel)

    reason = terminal_certified_final_result_violation_for_project(
        state,
        project_root=root,
        campaign_path=None,
    )

    assert reason is not None


def test_fixed_witness_verify_time_reruns_and_ignores_stored_verdict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _state()
    state["artifact_hashes"] = compute_exact_artifact_hashes(root)
    state["candidates"]["1x1"]["proof_summary"].update(
        {
            "terminal_fixed_witness_publishable": True,
            "terminal_fixed_witness_projected_status": "CERTIFIED",
        }
    )
    _patch_sink_replay(monkeypatch)
    failure_verdict = _fresh_failure_verdict(state, root, "forced_verify_time_failure")
    _patch_capsule_response(monkeypatch, root=root, state=state, verdict=failure_verdict)

    reason = terminal_certified_final_result_violation_for_project(
        state,
        project_root=root,
        campaign_path=None,
    )

    assert reason is not None


def test_build_then_verify_uses_fresh_projection_without_status_digest_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _state()
    state["artifact_hashes"] = compute_exact_artifact_hashes(root)
    _patch_sink_replay(monkeypatch)
    candidate_generation = _candidate_generation()
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))

    bundle = build_sink_verified_terminal_frontier_evidence(
        candidates=candidates,
        campaign_state=state,
        project_root=root,
        campaign_path=None,
        final_result=state["final_result"],
        candidate_generation=candidate_generation,
    )
    state["candidates"] = bundle["candidate_records"]
    state["terminal_frontier_evidence"] = bundle["evidence"]

    # Validator now requires a checkpoint with a real supervisor_seal; set one up
    sealed = _setup_sealed_campaign(monkeypatch, root, state)
    reason = terminal_certified_final_result_violation_for_project(
        sealed.state,
        project_root=root,
        campaign_path=sealed.path,
    )

    assert bundle["fixed_witness_publishable"] is True
    assert reason is None


def test_fixed_witness_unproven_durable_record_keeps_solution_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _state()
    state["artifact_hashes"] = compute_exact_artifact_hashes(root)
    _patch_sink_replay(monkeypatch)
    candidate_generation = _candidate_generation()
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(candidate_generation))
    before_solution = _json_copy(state["candidates"]["1x1"]["solution"])
    before_digest = canonical_digest(before_solution)
    failure_verdict = _fresh_failure_verdict(state, root, "forced_build_time_failure")
    _patch_capsule_response(monkeypatch, root=root, state=state, verdict=failure_verdict)

    bundle = build_sink_verified_terminal_frontier_evidence(
        candidates=candidates,
        campaign_state=state,
        project_root=root,
        campaign_path=None,
        final_result=state["final_result"],
        candidate_generation=candidate_generation,
    )

    durable_record = bundle["candidate_records"]["1x1"]
    public_record = bundle["public_candidate_records"]["1x1"]
    assert bundle["fixed_witness_publishable"] is False
    assert durable_record["status"] == RUN_STATUS_CERTIFIED
    assert durable_record["solution"] == before_solution
    assert canonical_digest(durable_record["solution"]) == before_digest
    assert CANDIDATE_PROOF_FIELD in durable_record
    assert public_record["status"] == "UNPROVEN"
    assert "solution" not in public_record
    assert CANDIDATE_PROOF_FIELD not in public_record


def _sliced_domain_state() -> dict[str, Any]:
    """A terminal-shaped state whose candidate_generation claims a narrower grid
    (max_w=1) than the canonical 2-wide tiny project, i.e. a sliced candidate
    domain that must be rejected by the canonical anti-slice grid check."""
    state = _state()
    generation = _candidate_generation()
    generation["max_w"] = 1
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(generation))
    state["terminal_frontier_evidence"] = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=state["candidates"],
        final_result=state["final_result"],
        candidate_generation=generation,
    )
    return state


def test_pr2_5_child_elevation_runs_frontier_validation_on_sliced_domain(
    tmp_path: Path,
) -> None:
    """PR2 #5: the L0 true-verifier child elevates a CANDIDATE_PROPOSED proposal to
    the strict terminal labels (declare_mode="strict" +
    last_stop_reason.status=CERTIFIED) before calling
    terminal_certified_final_result_project_precheck_violation, so the
    frontier-exhaustion / canonical candidate-domain check runs UNCONDITIONALLY.

    Without that elevation the gate has_terminal_full_frontier_certified_evidence()
    is False (an honest proposal arrives final_status=CANDIDATE_PROPOSED and -- because
    mark_campaign_stopped forbids a producer-minted CERTIFIED stop --
    last_stop_reason.status=CANDIDATE_PROPOSED), so the precheck SILENTLY skips the
    frontier check and a producer could seal a sliced candidate_generation.  This pins
    both halves: the strict-labelled state rejects the slice; the raw proposal does not.
    """
    root = _build_tiny_project(tmp_path / "project")

    # Honest canonical state already carries the strict terminal labels the child
    # asserts onto its scratch_state -> the full-domain proof passes.
    assert (
        terminal_certified_final_result_project_precheck_violation(_state(), project_root=root)
        is None
    )

    # FIX under test: with the strict terminal labels (what the child elevates to),
    # the sliced candidate_generation fails the canonical anti-slice grid check.
    sliced = _sliced_domain_state()
    reason = terminal_certified_final_result_project_precheck_violation(sliced, project_root=root)
    assert reason is not None
    assert reason.startswith("terminal_frontier"), reason

    # GAP it closes: strip the strict labels back to the raw proposal shape a producer
    # actually ships (final_status=CANDIDATE_PROPOSED, no declare_mode,
    # last_stop_reason.status=CANDIDATE_PROPOSED).  The SAME sliced domain now slips past
    # the frontier check -- which is exactly why the child must elevate before validating.
    raw_proposal = _json_copy(sliced)
    raw_proposal["final_status"] = CANDIDATE_PROPOSED_STATUS
    raw_proposal.pop("declare_mode", None)
    raw_proposal["last_stop_reason"]["status"] = CANDIDATE_PROPOSED_STATUS
    raw_reason = terminal_certified_final_result_project_precheck_violation(
        raw_proposal, project_root=root
    )
    assert raw_reason is None or not raw_reason.startswith("terminal_frontier"), raw_reason


def test_pr2_5_terminal_frontier_evidence_violation_rejects_non_exhausted_domain() -> None:
    """PR2 #5 companion (exhaustion dimension): terminal_frontier_evidence_violation
    -- the validator the child now invokes unconditionally after elevation -- must
    fail closed when the canonical candidate domain is NOT exhausted: a strictly
    more-optimal candidate has no resolved status, even though the candidate_generation
    params match canonical grid/min-side/safe-area exactly.  The integration test above
    covers the anti-slice dimension of the same gate; this pins the exhaustion dimension
    on a function that previously had no direct coverage.
    """
    generation = {
        "max_w": 2,
        "max_h": 2,
        "min_side": 1,
        "max_aspect_ratio": None,
        "area_upper_bound": 3,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": 3,
        "min_side_admissibility": 1,
    }
    candidates = generate_candidate_sizes(**candidate_generation_kwargs(generation))
    # Only the 1x1 winner is resolved; the strictly larger 1x2 / 2x1 candidates carry
    # no status -> they stay in the potential domain -> the frontier is not exhausted.
    candidate_records = {
        "1x1": {
            "ghost_rect": {"w": 1, "h": 1, "area": 1},
            "status": RUN_STATUS_CERTIFIED,
            "solution": {"ghost_pick": {"facility_type": "ghost_rect"}},
        }
    }
    final_result = {
        "ghost_rect": {"w": 1, "h": 1, "area": 1, "anchor_x": 0, "anchor_y": 0},
        "placement_solution": {},
        "search_status": RUN_STATUS_CERTIFIED,
    }
    evidence = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=candidate_records,
        final_result=final_result,
        candidate_generation=generation,
    )
    reason = terminal_frontier_evidence_violation(
        evidence=evidence,
        candidate_records=candidate_records,
        final_result=final_result,
        grid_dimensions=(2, 2),
        safe_area_upper_bound=3,
        min_side_admissibility=1,
    )
    assert reason is not None
    assert "not_exhausted" in reason, reason
