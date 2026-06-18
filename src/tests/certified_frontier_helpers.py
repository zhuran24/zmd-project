from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.models.cut_manager import RUN_STATUS_INFEASIBLE
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
)
from src.tests.verified_producer_test_support import seal_test_candidate_status


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

    # Test fixtures often construct already-verified candidate records directly so
    # they can exercise downstream terminal/manifest validation without invoking a
    # real solver.  Seal those records explicitly through the private TCB primitive;
    # production callers must use outer_search's verified producer path instead.
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
