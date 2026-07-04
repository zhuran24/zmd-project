"""Replayable terminal-frontier evidence for certified exact campaigns.

A terminal CERTIFIED checkpoint must not rely on a stop-reason string alone.  The
small deterministic candidate-domain core lives in ``pr2_l0_frontier_core`` so
the L0 verifier child can import it without loading this module's sink-replay
wrappers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.search.candidate_proof_replay import project_candidate_records_for_sink
from src.search.pr2_l0_frontier_core import (
    Candidate,
    TERMINAL_FRONTIER_DOMAIN_AUTHORITY as TERMINAL_FRONTIER_DOMAIN_AUTHORITY,
    TERMINAL_FRONTIER_EVIDENCE_SCHEMA_VERSION as TERMINAL_FRONTIER_EVIDENCE_SCHEMA_VERSION,
    TERMINAL_FRONTIER_EVIDENCE_SOURCE as TERMINAL_FRONTIER_EVIDENCE_SOURCE,
    TERMINAL_FRONTIER_EXHAUSTED_REASON as TERMINAL_FRONTIER_EXHAUSTED_REASON,
    TERMINAL_FRONTIER_MIN_SIDE_ADMISSIBILITY as TERMINAL_FRONTIER_MIN_SIDE_ADMISSIBILITY,
    TERMINAL_FRONTIER_OBJECTIVE as TERMINAL_FRONTIER_OBJECTIVE,
    build_terminal_frontier_evidence,
    candidate_generation_kwargs as candidate_generation_kwargs,
    candidate_key as candidate_key,
    candidate_key_from_dimensions as candidate_key_from_dimensions,
    candidate_objective as candidate_objective,
    candidate_sort_key as candidate_sort_key,
    compute_terminal_frontier_projection,
    generate_candidate_sizes as generate_candidate_sizes,
    normalize_candidate_generation_params as normalize_candidate_generation_params,
    normalize_terminal_frontier_domain_contract as normalize_terminal_frontier_domain_contract,
    terminal_frontier_evidence_violation as terminal_frontier_evidence_violation,
)
from src.search.terminal_fixed_witness_capsule import (
    build_terminal_fixed_witness_projection_at_sink,
)


def compute_sink_verified_terminal_frontier_projection(
    *,
    candidates: Sequence[Candidate],
    campaign_state: Mapping[str, Any],
    project_root: Path,
    campaign_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Compute pruning state only from records accepted by sink-side replay."""

    replayed_records, replay_violations = project_candidate_records_for_sink(
        state=campaign_state,
        project_root=project_root,
        campaign_path=campaign_path,
        require_record_solution_match=False,
    )
    projection = compute_terminal_frontier_projection(
        candidates=candidates,
        candidate_records=replayed_records,
    )
    projection["candidate_records"] = replayed_records
    projection["sink_replay_violations"] = replay_violations
    return projection


def build_sink_verified_terminal_frontier_evidence(
    *,
    candidates: Sequence[Candidate],
    campaign_state: Mapping[str, Any],
    project_root: Path,
    campaign_path: Optional[Path],
    final_result: Mapping[str, Any],
    candidate_generation: Mapping[str, Any],
    serialized_state_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """Build terminal evidence from replayed records, never raw strong strings."""

    replayed_records, replay_violations = project_candidate_records_for_sink(
        state=campaign_state,
        project_root=project_root,
        campaign_path=campaign_path,
        # Re-establish every strong status in the isolated child, while keeping
        # the already digest-bound stored witness.  The project-bound terminal
        # validator independently validates that witness; two exact runs need not
        # choose byte-identical feasible placements.
        require_record_solution_match=True,
    )
    authority_state = dict(campaign_state)
    authority_state["candidates"] = replayed_records
    authority_state["final_result"] = dict(final_result)
    fixed_witness_projection = build_terminal_fixed_witness_projection_at_sink(
        state=authority_state,
        project_root=project_root,
        campaign_path=campaign_path,
        candidate_records={
            str(key): dict(value)
            for key, value in replayed_records.items()
            if isinstance(value, Mapping)
        },
        final_result=final_result,
        serialized_state_bytes=serialized_state_bytes,
    )
    replayed_records = fixed_witness_projection.durable_candidate_records
    evidence = build_terminal_frontier_evidence(
        candidates=candidates,
        candidate_records=fixed_witness_projection.candidate_records,
        final_result=final_result,
        candidate_generation=candidate_generation,
    )
    return {
        "evidence": evidence,
        "candidate_records": replayed_records,
        "public_candidate_records": fixed_witness_projection.candidate_records,
        "sink_replay_violations": replay_violations,
        "fixed_witness_verdict": fixed_witness_projection.verdict.to_dict(),
        "fixed_witness_publishable": bool(fixed_witness_projection.publishable),
        "fixed_witness_violations": (
            {}
            if fixed_witness_projection.publishable
            else {
                str(fixed_witness_projection.candidate_key or "*"): str(
                    fixed_witness_projection.rejected_reason
                    or "terminal_fixed_witness_rejected"
                )
            }
        ),
    }
