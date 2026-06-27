from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from src.models.cut_manager import RUN_STATUS_CERTIFIED, RUN_STATUS_INFEASIBLE
from src.search.certified_frontier import (
    TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
    build_terminal_frontier_evidence,
    candidate_key,
    candidate_objective,
    generate_candidate_sizes,
)
from src.search.exact_campaign import (
    ExactCampaign,
    STRONG_CANDIDATE_STATUSES,
    _load_exact_grid_dimensions,
    _load_exact_min_side_admissibility,
    _load_exact_safe_area_upper_bound,
    atomic_write_json,
    now_iso,
)
from src.io.output_schema import blueprint_output_path, normalize_blueprint_payload
from src.tests.verified_producer_test_support import seal_test_candidate_status


def write_closed_phase_review_gate(project_root: Path) -> Path:
    gate_path = Path(project_root) / "data" / "review_gates" / "phase_1_2_spike_close.json"
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    # Clear any prior file/symlink so a shared project root never leaves a symlink
    # in place (writing through a symlink would keep the path non-regular).
    if gate_path.is_symlink() or gate_path.exists():
        gate_path.unlink()
    payload = {
        "schema_version": 2,
        "gate_id": "phase_1_2_spike_close",
        "status": "closed_manual_owner_decision",
        "next_phase_entry": {"allowed": True},
        "owner_manual_decision": {"p1_3b_entry_allowed": True},
    }
    gate_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return gate_path


def accepting_l0_supervisor_seal_for_test(*, project_root: Path):
    """Return a test-only L0 supervisor seal that writes the real CERTIFIED shape.

    This is for publication/plumbing fixtures that need a sealed checkpoint but
    are not testing the true PR2 child verifier.  It still reads the proposal
    checkpoint and marker from disk, then mirrors the production L0
    proposal-to-certified write shape.
    """

    from src.search import pr2_l0_micro_verifier_core as l0

    expected_project_root = Path(project_root).resolve()

    def _run_l0_supervisor_seal(request: Any) -> Any:
        parent_nonce = "test-l0-parent-supervisor-seal"
        child_nonce = "test-l0-domain-supervisor-seal"
        if Path(request.project_root).resolve() != expected_project_root:
            return l0.L0MicroVerdict(
                status=l0.REJECTED,
                nonce=parent_nonce,
                reason="test_project_root_mismatch",
            )

        checkpoint_bytes = Path(request.campaign_path).read_bytes()
        checkpoint_sha256 = hashlib.sha256(checkpoint_bytes).hexdigest()
        marker = l0._parse_mapping(  # type: ignore[attr-defined]
            Path(request.marker_path).read_bytes(),
            "proposal_ready_marker",
        )
        marker_violation = l0._proposal_ready_marker_violation(  # type: ignore[attr-defined]
            marker,
            checkpoint_sha256=checkpoint_sha256,
            expected_campaign_instance_id=str(request.expected_campaign_instance_id),
        )
        if marker_violation is not None:
            return l0.L0MicroVerdict(
                status=l0.REJECTED,
                nonce=parent_nonce,
                reason=marker_violation,
            )

        authority_state = l0._parse_mapping(  # type: ignore[attr-defined]
            checkpoint_bytes,
            "proposal_checkpoint",
        )
        authority_violation = l0._proposal_authority_violation(  # type: ignore[attr-defined]
            authority_state=authority_state,
            marker=marker,
            expected_campaign_instance_id=str(request.expected_campaign_instance_id),
        )
        if authority_violation is not None:
            return l0.L0MicroVerdict(
                status=l0.REJECTED,
                nonce=parent_nonce,
                reason=authority_violation,
            )
        strong_keys = l0._strong_status_keys(authority_state)  # type: ignore[attr-defined]
        proof_binding_violation = l0._strong_proof_binding_violation(  # type: ignore[attr-defined]
            authority_state=authority_state,
            strong_keys=strong_keys,
            project_root=expected_project_root,
            campaign_path=Path(request.campaign_path).resolve(),
        )
        if proof_binding_violation is not None:
            return l0.L0MicroVerdict(
                status=l0.REJECTED,
                nonce=parent_nonce,
                reason=proof_binding_violation,
            )

        proposal_final_result = l0._require_mapping(  # type: ignore[attr-defined]
            authority_state.get("final_result"),
            "proposal final_result invalid",
        )
        certified_final_result = dict(proposal_final_result)
        certified_final_result["search_status"] = RUN_STATUS_CERTIFIED
        proposal_evidence = l0._require_mapping(  # type: ignore[attr-defined]
            authority_state.get("terminal_frontier_evidence"),
            "proposal terminal_frontier_evidence invalid",
        )
        proposal_candidates = l0._require_mapping(  # type: ignore[attr-defined]
            authority_state.get("candidates"),
            "proposal candidate_records invalid",
        )
        certified_candidates = l0._stable_fixed_witness_candidate_records_l0(  # type: ignore[attr-defined]
            proposal_candidates,
        )
        final_result_digest = l0._canonical_digest(certified_final_result)  # type: ignore[attr-defined]
        evidence_digest = l0._canonical_digest(proposal_evidence)  # type: ignore[attr-defined]
        candidate_records_digest = l0._canonical_digest(certified_candidates)  # type: ignore[attr-defined]
        domain = {
            "schema_version": l0.SUPERVISOR_DOMAIN_SCHEMA_VERSION,
            "authority": l0.SUPERVISOR_DOMAIN_AUTHORITY,
            "nonce": child_nonce,
            "verdict": l0.SEALED,
            "reason": "test_accepting_l0_supervisor_seal",
            "strong_keys": [str(key) for key in strong_keys],
            "final_result": certified_final_result,
            "terminal_frontier_evidence": dict(proposal_evidence),
            "candidate_records": certified_candidates,
            "final_result_digest": final_result_digest,
            "terminal_frontier_evidence_digest": evidence_digest,
            "candidate_records_digest": candidate_records_digest,
            "fixed_witness_publishable": True,
            "sink_replay_violations": {},
            "fixed_witness_violations": {},
            "tcb": {"test_fixture": "accepting_l0_supervisor_seal"},
        }
        domain_violation = l0._domain_response_violation(  # type: ignore[attr-defined]
            domain,
            nonce=child_nonce,
            strong_keys=strong_keys,
            proposal_final_result_digest=final_result_digest,
            proposal_evidence_digest=evidence_digest,
            proposal_candidate_records_digest=candidate_records_digest,
        )
        if domain_violation is not None:
            return l0.L0MicroVerdict(
                status=l0.REJECTED,
                nonce=parent_nonce,
                reason=domain_violation,
            )

        commit_timestamp = l0._now_iso()  # type: ignore[attr-defined]
        scratch_state = dict(authority_state)
        scratch_state["final_result"] = certified_final_result
        scratch_state["final_status"] = RUN_STATUS_CERTIFIED
        scratch_state["last_stop_reason"] = {
            "reason": l0.TERMINAL_CERTIFIED_REASON,
            "status": RUN_STATUS_CERTIFIED,
            "updated_at": commit_timestamp,
        }
        scratch_state.pop(l0.SUPERVISOR_PROPOSAL_STATE_KEY, None)
        scratch_state["terminal_frontier_evidence"] = dict(proposal_evidence)
        scratch_state["candidates"] = certified_candidates
        scratch_state["updated_at"] = commit_timestamp
        seal_record = {
            "schema_version": l0.SUPERVISOR_SEAL_SCHEMA_VERSION,
            "authority": l0.SUPERVISOR_SEAL_AUTHORITY,
            "transition": "proposal_to_certified_v1",
            "proposal_run_id": str(marker["run_id"]),
            "proposal_checkpoint_sha256": checkpoint_sha256,
            "proposal_authority_b64": base64.b64encode(checkpoint_bytes).decode("ascii"),
            l0.CAMPAIGN_INSTANCE_ID_KEY: str(marker[l0.CAMPAIGN_INSTANCE_ID_KEY]),
            "certified_state_sha256": l0._certified_state_payload_sha256_l0(  # type: ignore[attr-defined]
                scratch_state,
            ),
            "sealed_at": commit_timestamp,
        }
        scratch_state[l0.SUPERVISOR_SEAL_STATE_KEY] = seal_record
        seal_violation = l0._supervisor_seal_state_violation_l0(  # type: ignore[attr-defined]
            seal_record,
            state=scratch_state,
        )
        if seal_violation is not None:
            return l0.L0MicroVerdict(
                status=l0.REJECTED,
                nonce=parent_nonce,
                reason=seal_violation,
            )

        pending_state_bytes = l0._atomic_json_bytes(scratch_state)  # type: ignore[attr-defined]
        with l0._checkpoint_write_lock_l0(Path(request.campaign_path)):  # type: ignore[attr-defined]
            current_marker = l0._parse_mapping(  # type: ignore[attr-defined]
                Path(request.marker_path).read_bytes(),
                "proposal_ready_marker",
            )
            if dict(current_marker) != dict(marker):
                return l0.L0MicroVerdict(
                    status=l0.REJECTED,
                    nonce=parent_nonce,
                    reason="proposal_ready_marker_changed_before_mint",
                )
            current_checkpoint_bytes = Path(request.campaign_path).read_bytes()
            if hashlib.sha256(current_checkpoint_bytes).hexdigest() != checkpoint_sha256:
                return l0.L0MicroVerdict(
                    status=l0.REJECTED,
                    nonce=parent_nonce,
                    reason="proposal checkpoint changed before mint",
                )
            l0._atomic_replace_bytes(Path(request.campaign_path), pending_state_bytes)  # type: ignore[attr-defined]
            disk_state = l0._parse_mapping(  # type: ignore[attr-defined]
                Path(request.campaign_path).read_bytes(),
                "certified_checkpoint",
            )
            postwrite_violation = l0._postwrite_state_violation(  # type: ignore[attr-defined]
                disk_state,
                expected_domain=domain,
                expected_payload_sha=str(seal_record["certified_state_sha256"]),
            )
            if postwrite_violation is not None:
                l0._atomic_replace_bytes(Path(request.campaign_path), checkpoint_bytes)  # type: ignore[attr-defined]
                return l0.L0MicroVerdict(
                    status=l0.REJECTED,
                    nonce=parent_nonce,
                    reason=f"postwrite_validation_failed:{postwrite_violation}",
                )
            try:
                Path(request.marker_path).unlink()
            except FileNotFoundError:
                pass

        response = {
            "domain": domain,
            "l0_seal": {
                "schema_version": l0.SUPERVISOR_SEAL_SCHEMA_VERSION,
                "authority": l0.SUPERVISOR_SEAL_AUTHORITY,
                "checkpoint_sha256": hashlib.sha256(pending_state_bytes).hexdigest(),
                "strong_key_count": len(strong_keys),
                "write_isolation": "test_fixture_parent_writer_l0_shape",
                "third_party_native": "TEST-FIXTURE",
            },
        }
        return l0.L0MicroVerdict(
            status=l0.SEALED,
            nonce=parent_nonce,
            reason="supervisor_sealed",
            floor_digest="test-fixture",
            response=response,
        )

    return _run_l0_supervisor_seal


def install_accepting_l0_supervisor_seal(
    monkeypatch: Any,
    *,
    project_root: Path,
) -> None:
    from src.search import pr2_l0_micro_verifier_core as l0

    monkeypatch.setattr(
        l0,
        "run_l0_supervisor_seal",
        accepting_l0_supervisor_seal_for_test(project_root=project_root),
    )


def forge_legacy_terminal_certified_stop(campaign: ExactCampaign) -> None:
    campaign.state["last_stop_reason"] = {
        "reason": "search_exhausted_all_candidates",
        "status": RUN_STATUS_CERTIFIED,
        "updated_at": "2026-03-16T00:00:00Z",
    }
    campaign.state["final_status"] = RUN_STATUS_CERTIFIED


def persist_forged_terminal_certified_state(campaign: ExactCampaign) -> None:
    """Test-only: persist ``campaign.state`` to its checkpoint, bypassing
    ``ExactCampaign.save()``'s terminal-CERTIFIED guard.

    Negative/positive fixtures build a terminal CERTIFIED checkpoint directly
    (``forge_legacy_terminal_certified_stop`` + ``attach_terminal_frontier_evidence``)
    to exercise the disk-reading manifest / certified-surface / resume validators.
    Production ``save()`` now refuses to persist terminal CERTIFIED (only
    ``supervisor_seal`` mints it), so these fixtures write the raw checkpoint here.
    This grants no authority: every disk-reading validator still runs the full
    isolated sink replay before accepting the status.
    """

    campaign.state["updated_at"] = now_iso()
    atomic_write_json(campaign.path, campaign.state)


def persist_canonical_blueprint_for_test(project_root: Path, payload: dict) -> None:
    """Test-only canonical blueprint write below the verified publisher boundary."""

    atomic_write_json(blueprint_output_path(project_root), normalize_blueprint_payload(payload))


def attach_terminal_frontier_evidence(
    campaign: ExactCampaign,
    project_root: Path,
    *,
    min_side: int = 1,
    max_aspect_ratio: Optional[float] = None,
    fill_unresolved_better_candidates_as_infeasible: bool = False,
) -> None:
    grid_dimensions = _load_exact_grid_dimensions(project_root)
    if grid_dimensions is None:
        raise AssertionError("test project must define grid dimensions")
    grid_w, grid_h = grid_dimensions
    safe_area_upper_bound = _load_exact_safe_area_upper_bound(project_root)
    if safe_area_upper_bound is None:
        raise AssertionError("test project must define a safe area upper bound")
    min_side_admissibility = _load_exact_min_side_admissibility(project_root)
    if min_side_admissibility is None:
        raise AssertionError("test project must define min_side admissibility")
    candidate_generation = {
        "max_w": grid_w,
        "max_h": grid_h,
        "min_side": min_side,
        "max_aspect_ratio": max_aspect_ratio,
        "area_upper_bound": safe_area_upper_bound,
        "start_area": None,
        "domain_authority": TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
        "safe_area_upper_bound": safe_area_upper_bound,
        "min_side_admissibility": min_side_admissibility,
    }
    candidates = generate_candidate_sizes(
        max_w=grid_w,
        max_h=grid_h,
        min_side=min_side,
        max_aspect_ratio=max_aspect_ratio,
        area_upper_bound=safe_area_upper_bound,
        start_area=None,
    )
    terminal_stop_reason = campaign.state.get("last_stop_reason")
    terminal_final_status = campaign.state.get("final_status")
    terminal_final_result = campaign.state.get("final_result")
    if fill_unresolved_better_candidates_as_infeasible:
        final_result = campaign.state.get("final_result")
        ghost_rect = final_result.get("ghost_rect") if isinstance(final_result, dict) else {}
        final_w = int(ghost_rect.get("w", 0))
        final_h = int(ghost_rect.get("h", 0))
        final_objective = (final_w * final_h, min(final_w, final_h))
        existing = campaign.state.setdefault("candidates", {})
        for candidate in candidates:
            if candidate_objective(candidate) <= final_objective:
                continue
            key = candidate_key(candidate)
            if key in existing:
                continue
            _area, ghost_w, ghost_h = candidate
            campaign.mark_candidate_started(ghost_w, ghost_h)
            campaign.mark_candidate_result(
                ghost_w,
                ghost_h,
                RUN_STATUS_INFEASIBLE,
                proof_summary={"master_status": RUN_STATUS_INFEASIBLE},
            )
        campaign.state["last_stop_reason"] = terminal_stop_reason
        campaign.state["final_status"] = terminal_final_status
        campaign.state["final_result"] = terminal_final_result

    # Attach data-only replay requests to synthetic strong records.  This helper
    # grants no authority: every frontier/terminal/manifest/public sink still runs
    # the isolated certified solver before accepting a status.
    for raw_key, raw_record in campaign.state.get("candidates", {}).items():
        if not isinstance(raw_record, dict):
            continue
        status = str(raw_record.get("status", ""))
        if status in STRONG_CANDIDATE_STATUSES:
            seal_test_candidate_status(
                campaign,
                str(raw_key),
                status,
            )

    campaign.state["terminal_frontier_evidence"] = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=campaign.state.get("candidates", {}),
        final_result=campaign.state.get("final_result") or {},
        candidate_generation=candidate_generation,
    )
