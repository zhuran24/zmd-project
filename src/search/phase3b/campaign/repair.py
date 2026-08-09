from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

from src.models.cut_manager import RUN_STATUS_UNKNOWN
from src.search.exact_campaign import ExactCampaign, now_iso


def mark_running_exact_campaign_candidates_interrupted(
    project_root: Path,
    *,
    reason: str,
    detail: str,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    campaign_existed = campaign_path.exists()
    campaign = ExactCampaign.load_or_create(
        project_root,
        campaign_hours=1.0,
        resume=True,
    )
    candidates = dict(campaign.state.get("candidates", {}))
    interrupted_keys: list[str] = []
    for key, record in candidates.items():
        if not isinstance(record, Mapping):
            continue
        if str(record.get("status")) != "RUNNING":
            continue
        ghost_rect = record.get("ghost_rect")
        if not isinstance(ghost_rect, Mapping):
            continue
        ghost_w = int(ghost_rect.get("w", 0))
        ghost_h = int(ghost_rect.get("h", 0))
        proof_summary = dict(record.get("proof_summary", {})) if isinstance(record.get("proof_summary"), Mapping) else {}
        proof_summary["operator_interruption"] = {
            "reason": str(reason),
            "detail": str(detail),
            "marked_at": now_iso(),
            "previous_status": "RUNNING",
        }
        campaign.mark_candidate_result(
            ghost_w,
            ghost_h,
            RUN_STATUS_UNKNOWN,
            proof_summary=proof_summary,
            exact_safe_cuts=list(record.get("exact_safe_cuts", []))
            if isinstance(record.get("exact_safe_cuts"), list)
            else [],
            loaded_exact_safe_cut_count=int(record.get("loaded_exact_safe_cut_count", 0)),
            generated_exact_safe_cut_count=int(record.get("generated_exact_safe_cut_count", 0)),
        )
        interrupted_keys.append(str(key))

    campaign_marked_stopped = bool(interrupted_keys or campaign_existed)
    if campaign_marked_stopped:
        campaign.mark_campaign_stopped(str(reason), status=RUN_STATUS_UNKNOWN)
        campaign.save()
    return {
        "project_root": str(project_root),
        "campaign_state_path": str(campaign.path),
        "reason": str(reason),
        "detail": str(detail),
        "interrupted_candidate_keys": interrupted_keys,
        "interrupted_candidate_count": int(len(interrupted_keys)),
        "campaign_marked_stopped": bool(campaign_marked_stopped),
    }
