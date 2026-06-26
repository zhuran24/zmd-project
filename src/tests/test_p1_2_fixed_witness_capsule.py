from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

import pytest

import src.search.terminal_fixed_witness_capsule as capsule_module
import src.search.terminal_fixed_witness_verifier as fixed_witness_module
from src.models.cut_manager import RUN_STATUS_CERTIFIED
from src.search.candidate_proof_replay import CANDIDATE_PROOF_FIELD
from src.search.certified_frontier import (
    build_sink_verified_terminal_frontier_evidence,
    candidate_generation_kwargs,
    generate_candidate_sizes,
)
from src.search.exact_campaign import (
    CANDIDATE_PROPOSED_STATUS,
    ExactCampaign,
    TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
    compute_exact_artifact_hashes,
    terminal_certified_final_result_violation_for_project,
)
from src.tests.test_exact_contract import _install_accepting_supervisor_seal_replay
from src.search.terminal_fixed_witness_capsule import (
    TERMINAL_FIXED_WITNESS_CAPSULE_AUTHORITY,
    TERMINAL_FIXED_WITNESS_CAPSULE_RESPONSE_SCHEMA_VERSION,
    build_terminal_fixed_witness_projection_at_sink,
)
from src.search.terminal_fixed_witness_verifier import (
    TERMINAL_FIXED_WITNESS_VERIFIER_AUTHORITY,
    TERMINAL_FIXED_WITNESS_VERIFIER_SCHEMA_VERSION,
    TerminalFixedWitnessVerdict,
    project_terminal_fixed_witness_records_for_sink,
    verify_terminal_fixed_witness,
)
from src.tests.test_p1_2_fixed_witness_terminal_verifier import (
    _build_tiny_project,
    _candidate_generation,
    _json_copy,
    _patch_sink_replay,
    _state,
)


def _prepare_state(root: Path) -> dict[str, Any]:
    state = _state()
    state["artifact_hashes"] = compute_exact_artifact_hashes(root)
    return state


def _identity(state: Mapping[str, Any]):
    return fixed_witness_module._identity_from_current_records(
        fixed_witness_module._copy_candidate_records(state["candidates"]),
        state["final_result"],
    )


def _forged_publishable_verdict(state: Mapping[str, Any]) -> TerminalFixedWitnessVerdict:
    identity = _identity(state)
    return TerminalFixedWitnessVerdict(
        schema_version=TERMINAL_FIXED_WITNESS_VERIFIER_SCHEMA_VERSION,
        authority=TERMINAL_FIXED_WITNESS_VERIFIER_AUTHORITY,
        fresh_run_token="caller-controlled-token",
        publishable=True,
        projected_status=RUN_STATUS_CERTIFIED,
        candidate_key=identity.candidate_key,
        solution_digest=identity.solution_digest,
        ghost_rect_digest=identity.ghost_rect_digest,
        ghost_cells_digest=identity.ghost_cells_digest,
        witness_input_digest=identity.witness_input_digest,
        binding_assignment_digest="0" * 64,
        port_specs_digest="0" * 64,
        routing_occupancy_digest="0" * 64,
        binding_status="FEASIBLE",
        routing_status="FEASIBLE",
        reason=None,
        details={"forged": True},
    )


def _failure_verdict(
    state: Mapping[str, Any],
    reason: str = "forced_child_failure",
) -> TerminalFixedWitnessVerdict:
    identity = _identity(state)
    return TerminalFixedWitnessVerdict(
        schema_version=TERMINAL_FIXED_WITNESS_VERIFIER_SCHEMA_VERSION,
        authority=TERMINAL_FIXED_WITNESS_VERIFIER_AUTHORITY,
        fresh_run_token="child-token",
        publishable=False,
        projected_status="UNPROVEN",
        candidate_key=identity.candidate_key,
        solution_digest=identity.solution_digest,
        ghost_rect_digest=identity.ghost_rect_digest,
        ghost_cells_digest=identity.ghost_cells_digest,
        witness_input_digest=identity.witness_input_digest,
        binding_status="TIMEOUT",
        routing_status=None,
        reason=reason,
        details={"forced": True},
    )


def _capsule_response(
    *,
    root: Path,
    state: Mapping[str, Any],
    verdict: TerminalFixedWitnessVerdict,
    nonce: str,
) -> dict[str, Any]:
    hashes = dict(state["artifact_hashes"])
    return {
        "schema_version": TERMINAL_FIXED_WITNESS_CAPSULE_RESPONSE_SCHEMA_VERSION,
        "authority": TERMINAL_FIXED_WITNESS_CAPSULE_AUTHORITY,
        "nonce": nonce,
        "project_root": str(root.resolve()),
        "artifact_hashes": hashes,
        "source_digest": hashes["certified_exact_source_tree"],
        "verdict": verdict.to_dict(),
    }


def _install_capsule_response(
    monkeypatch: pytest.MonkeyPatch,
    *,
    root: Path,
    state: Mapping[str, Any],
    verdict: TerminalFixedWitnessVerdict,
    nonce_override: str | None = None,
    artifact_hash_override: str | None = None,
    source_digest_override: str | None = None,
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
        assert expected_source_digest == state["artifact_hashes"]["certified_exact_source_tree"]
        response = _capsule_response(
            root=root,
            state=state,
            verdict=verdict,
            nonce=nonce_override or nonce,
        )
        if artifact_hash_override is not None:
            response["artifact_hashes"] = dict(response["artifact_hashes"])
            response["artifact_hashes"]["canonical_rules"] = artifact_hash_override
        if source_digest_override is not None:
            response["source_digest"] = source_digest_override
        return response

    monkeypatch.setattr(capsule_module, "_invoke_isolated_capsule", fake_invoke)


def _prepare_sealed_campaign(
    monkeypatch: pytest.MonkeyPatch,
    *,
    root: Path,
    state: dict[str, Any],
) -> ExactCampaign:
    """Build a CANDIDATE_PROPOSED campaign matching *state* content, then seal it.

    Returns the campaign object after supervisor_seal() — its .path points to the
    sealed CERTIFIED checkpoint on disk. The caller should install test-specific
    patches (forged symbols, failure capsule) AFTER this call so they don't
    interfere with the accepting monkeypatches used during sealing.
    """
    # Build a fresh CANDIDATE_PROPOSED campaign with the same content as state.
    proposal = ExactCampaign.load_or_create(root, campaign_hours=1.0, resume=False)
    proposal_final_result = dict(state["final_result"])
    proposal_final_result["search_status"] = CANDIDATE_PROPOSED_STATUS
    proposal.state["final_result"] = proposal_final_result
    proposal.state["candidates"] = _json_copy(state["candidates"])
    run_id = proposal.set_supervisor_proposal_run_id()
    proposal.mark_campaign_stopped(
        TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        status=CANDIDATE_PROPOSED_STATUS,
    )
    proposal.state["terminal_frontier_evidence"] = _json_copy(state["terminal_frontier_evidence"])
    proposal.save()
    proposal.write_proposal_ready_marker(run_id=run_id, exit_code=0)

    # Accepting sink-replay monkeypatches required by supervisor_seal internals.
    _install_accepting_supervisor_seal_replay(monkeypatch, project_root=root)

    # Accepting capsule for the pre-commit validator called inside supervisor_seal.
    # This is replaced by the test-specific capsule (failure/forgery) after sealing.
    def _accepting_capsule(
        *,
        project_root: Path,
        authority_state: Mapping[str, Any],
        expected_artifact_hashes: Mapping[str, str],
        expected_source_digest: str,
        nonce: str,
    ) -> Mapping[str, Any]:
        identity = fixed_witness_module._identity_from_current_records(
            fixed_witness_module._copy_candidate_records(authority_state["candidates"]),
            authority_state["final_result"],
        )
        verdict = TerminalFixedWitnessVerdict(
            schema_version=TERMINAL_FIXED_WITNESS_VERIFIER_SCHEMA_VERSION,
            authority=TERMINAL_FIXED_WITNESS_VERIFIER_AUTHORITY,
            fresh_run_token="seal-accepting-token",
            publishable=True,
            projected_status=RUN_STATUS_CERTIFIED,
            candidate_key=identity.candidate_key,
            solution_digest=identity.solution_digest,
            ghost_rect_digest=identity.ghost_rect_digest,
            ghost_cells_digest=identity.ghost_cells_digest,
            witness_input_digest=identity.witness_input_digest,
            binding_assignment_digest="0" * 64,
            port_specs_digest="0" * 64,
            routing_occupancy_digest="0" * 64,
            binding_status="FEASIBLE",
            routing_status="FEASIBLE",
            reason=None,
            details={"accepting": True},
        )
        return {
            "schema_version": TERMINAL_FIXED_WITNESS_CAPSULE_RESPONSE_SCHEMA_VERSION,
            "authority": TERMINAL_FIXED_WITNESS_CAPSULE_AUTHORITY,
            "nonce": nonce,
            "project_root": str(Path(project_root).resolve()),
            "artifact_hashes": dict(expected_artifact_hashes),
            "source_digest": expected_source_digest,
            "verdict": verdict.to_dict(),
        }

    monkeypatch.setattr(capsule_module, "_invoke_isolated_capsule", _accepting_capsule)

    # Seal — writes the CERTIFIED checkpoint to proposal.path.
    proposal.supervisor_seal()
    return proposal


def test_same_process_constructed_publishable_verdict_cannot_publish(tmp_path: Path) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _prepare_state(root)

    projection = project_terminal_fixed_witness_records_for_sink(
        candidate_records=_json_copy(state["candidates"]),
        final_result=state["final_result"],
        verdict=_forged_publishable_verdict(state),
    )

    assert projection.publishable is False
    assert projection.rejected_reason == "terminal_fixed_witness_capsule_required"
    assert projection.candidate_records["1x1"]["status"] == "UNPROVEN"
    assert "solution" not in projection.candidate_records["1x1"]


def test_verify_symbol_monkeypatch_cannot_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _prepare_state(root)
    # Patch candidate replay first so it is active during sealing as well.
    _patch_sink_replay(monkeypatch)
    # Create a properly sealed checkpoint (needs accepting capsule during seal).
    sealed = _prepare_sealed_campaign(monkeypatch, root=root, state=state)
    # Install test-specific patches AFTER sealing so they don't interfere.
    monkeypatch.setattr(
        fixed_witness_module,
        "verify_terminal_fixed_witness",
        lambda **_kwargs: _forged_publishable_verdict(state),
    )
    # Replace accepting capsule with the failure one for the validator call.
    _install_capsule_response(
        monkeypatch,
        root=root,
        state=state,
        verdict=_failure_verdict(state, "child_rejected"),
    )

    reason = terminal_certified_final_result_violation_for_project(
        state,
        project_root=root,
        campaign_path=sealed.path,
    )

    assert reason == "terminal_certified_candidate_record_not_certified"


def test_projection_symbol_monkeypatch_cannot_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _prepare_state(root)
    # Patch candidate replay first so it is active during sealing as well.
    _patch_sink_replay(monkeypatch)
    # Create a properly sealed checkpoint (needs accepting capsule during seal).
    sealed = _prepare_sealed_campaign(monkeypatch, root=root, state=state)
    # Install test-specific patches AFTER sealing so they don't interfere.

    def forged_projection(**_kwargs: Any):
        return fixed_witness_module.TerminalFixedWitnessProjection(
            candidate_records=_json_copy(state["candidates"]),
            candidate_key="1x1",
            publishable=True,
            projected_status=RUN_STATUS_CERTIFIED,
            rejected_reason=None,
        )

    monkeypatch.setattr(
        fixed_witness_module,
        "project_terminal_fixed_witness_records_for_sink",
        forged_projection,
    )
    # Replace accepting capsule with the failure one for the validator call.
    _install_capsule_response(
        monkeypatch,
        root=root,
        state=state,
        verdict=_failure_verdict(state, "child_rejected"),
    )

    reason = terminal_certified_final_result_violation_for_project(
        state,
        project_root=root,
        campaign_path=sealed.path,
    )

    assert reason == "terminal_certified_candidate_record_not_certified"


def test_child_nonce_mismatch_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _prepare_state(root)
    _install_capsule_response(
        monkeypatch,
        root=root,
        state=state,
        verdict=_forged_publishable_verdict(state),
        nonce_override="wrong-nonce",
    )

    projection = build_terminal_fixed_witness_projection_at_sink(
        state=state,
        project_root=root,
        candidate_records=_json_copy(state["candidates"]),
        final_result=state["final_result"],
    )

    assert projection.publishable is False
    assert projection.rejected_reason == "terminal_fixed_witness_capsule_response_nonce_mismatch"
    assert projection.candidate_records["1x1"]["status"] == "UNPROVEN"


def test_child_source_or_artifact_hash_mismatch_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _prepare_state(root)
    _install_capsule_response(
        monkeypatch,
        root=root,
        state=state,
        verdict=_forged_publishable_verdict(state),
        artifact_hash_override="1" * 64,
    )

    projection = build_terminal_fixed_witness_projection_at_sink(
        state=state,
        project_root=root,
        candidate_records=_json_copy(state["candidates"]),
        final_result=state["final_result"],
    )

    assert projection.publishable is False
    assert projection.rejected_reason == (
        "terminal_fixed_witness_capsule_response_artifact_binding_mismatch"
    )
    assert projection.candidate_records["1x1"]["status"] == "UNPROVEN"


def test_caller_candidate_records_cannot_override_serialized_authority_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    authority_state = _prepare_state(root)
    caller_records = _json_copy(authority_state["candidates"])
    caller_records["1x1"]["solution"]["tiny_001"]["anchor"] = {"x": 1, "y": 0}

    def forbidden_invoke(**_kwargs: Any) -> Mapping[str, Any]:
        raise AssertionError("authority mismatch must fail before child launch")

    monkeypatch.setattr(capsule_module, "_invoke_isolated_capsule", forbidden_invoke)

    projection = build_terminal_fixed_witness_projection_at_sink(
        state=authority_state,
        project_root=root,
        candidate_records=caller_records,
        final_result=authority_state["final_result"],
        serialized_state_bytes=(
            fixed_witness_module.canonical_state_bytes_for_fixed_witness(authority_state)
        ),
    )

    assert projection.publishable is False
    assert projection.rejected_reason == (
        "terminal_fixed_witness_capsule_authority_state_invalid:ValueError"
    )
    assert projection.candidate_records["1x1"]["status"] == "UNPROVEN"


def test_capsule_uses_checkpoint_bytes_when_serialized_state_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    authority_state = _prepare_state(root)
    campaign_path = root / "data" / "checkpoints" / "exact_campaign_state.json"
    campaign_path.parent.mkdir(parents=True, exist_ok=True)
    campaign_path.write_text(
        json.dumps(authority_state, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    tampered_parent_state = _json_copy(authority_state)
    tampered_parent_state["artifact_hashes"] = dict(tampered_parent_state["artifact_hashes"])
    tampered_parent_state["artifact_hashes"]["canonical_rules"] = "0" * 64
    captured_authority_states: list[Mapping[str, Any]] = []

    def fake_invoke(
        *,
        project_root: Path,
        authority_state: Mapping[str, Any],
        expected_artifact_hashes: Mapping[str, str],
        expected_source_digest: str,
        nonce: str,
    ) -> Mapping[str, Any]:
        del project_root, expected_artifact_hashes, expected_source_digest
        captured_authority_states.append(_json_copy(authority_state))
        return _capsule_response(
            root=root,
            state=authority_state,
            verdict=_failure_verdict(authority_state, "forced_child_failure"),
            nonce=nonce,
        )

    monkeypatch.setattr(capsule_module, "_invoke_isolated_capsule", fake_invoke)

    projection = build_terminal_fixed_witness_projection_at_sink(
        state=tampered_parent_state,
        project_root=root,
        campaign_path=campaign_path,
        candidate_records=_json_copy(authority_state["candidates"]),
        final_result=authority_state["final_result"],
    )

    assert projection.publishable is False
    assert captured_authority_states == [authority_state]


def test_child_timeout_or_exception_demotes_unproven_not_infeasible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _prepare_state(root)

    def timeout_invoke(**_kwargs: Any) -> Mapping[str, Any]:
        raise subprocess.TimeoutExpired(cmd=["python", "-I"], timeout=1.0)

    monkeypatch.setattr(capsule_module, "_invoke_isolated_capsule", timeout_invoke)

    projection = build_terminal_fixed_witness_projection_at_sink(
        state=state,
        project_root=root,
        candidate_records=_json_copy(state["candidates"]),
        final_result=state["final_result"],
    )

    assert projection.publishable is False
    assert projection.rejected_reason == (
        "terminal_fixed_witness_capsule_invocation_failed:TimeoutExpired"
    )
    assert projection.candidate_records["1x1"]["status"] == "UNPROVEN"
    assert projection.candidate_records["1x1"]["status"] != "INFEASIBLE"
    assert CANDIDATE_PROOF_FIELD not in projection.candidate_records["1x1"]


def test_same_owner_connector_body_collision_demotes_unproven(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _prepare_state(root)

    class SameOwnerPortCollisionBindingModel:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def build(self) -> None:
            pass

        def solve(self, *, time_limit_seconds: float) -> str:
            return "FEASIBLE"

        def extract_selection(self) -> dict[str, Any]:
            return {"binding_choice": {"tiny_001": 0}, "generic_inputs": {}, "generic_outputs": {}}

        def extract_port_specs(self) -> list[dict[str, Any]]:
            return [
                {
                    "instance_id": "tiny_001",
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
        SameOwnerPortCollisionBindingModel,
    )
    verdict = verify_terminal_fixed_witness(
        state=state,
        project_root=root,
        serialized_state_bytes=fixed_witness_module.canonical_state_bytes_for_fixed_witness(
            state
        ),
    )
    _install_capsule_response(monkeypatch, root=root, state=state, verdict=verdict)

    projection = build_terminal_fixed_witness_projection_at_sink(
        state=state,
        project_root=root,
        candidate_records=_json_copy(state["candidates"]),
        final_result=state["final_result"],
    )

    assert verdict.reason == "terminal_fixed_witness_connector_cell_occupied_by_other_body"
    assert projection.publishable is False
    assert projection.candidate_records["1x1"]["status"] == "UNPROVEN"


def test_valid_r_star_pi_star_capsule_publishable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _build_tiny_project(tmp_path / "project")
    state = _prepare_state(root)
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

    assert bundle["fixed_witness_publishable"] is True
    assert bundle["public_candidate_records"]["1x1"]["status"] == RUN_STATUS_CERTIFIED
