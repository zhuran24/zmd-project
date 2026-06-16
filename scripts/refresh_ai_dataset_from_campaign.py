"""Extract AI training dataset from campaign state checkpoint.

Reads exact_campaign_state.json and produces candidate_runs.jsonl
in the same schema as feature_extract.py, but sourced directly from
the campaign checkpoint rather than acceptance test records.

Usage:
    python scripts/refresh_ai_dataset_from_campaign.py
    python scripts/refresh_ai_dataset_from_campaign.py --output-dir .artifacts/phase3b_ai_dataset_latest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ai_accel.schemas import (
    AI_CANDIDATE_RUN_SAMPLE_SCHEMA_ID,
    AI_FEATURE_DATASET_SUMMARY_SCHEMA_ID,
    build_ai_dataset_safety_contract,
)
from src.search.exact_campaign import now_iso


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _number_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def extract_sample_from_candidate(
    candidate_key: str,
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    ghost = _mapping(candidate.get("ghost_rect"))
    proof = _mapping(candidate.get("proof_summary"))
    frontier = _mapping(proof.get("frontier_candidate_metrics"))
    precheck_bp = _mapping(proof.get("master_boundary_port_feasibility"))
    master_solve = _mapping(proof.get("master_last_solve"))

    w = _int_or_none(ghost.get("w")) or 0
    h = _int_or_none(ghost.get("h")) or 0
    status = str(candidate.get("status", "RUNNING"))
    master_status = str(proof.get("master_status", ""))
    precheck_triggered = precheck_bp.get("screen_pass_anchor_count") == 0 and \
        _int_or_none(precheck_bp.get("screened_infeasible_anchor_count", 0)) > 0
    master_solve_skipped = precheck_triggered and proof.get("benders_iterations", -1) == 0

    outcome = "unknown"
    if status == "INFEASIBLE":
        outcome = "master_infeasible" if not precheck_triggered else "precheck_infeasible"
    elif status == "CERTIFIED":
        outcome = "certified"

    classification = "other"
    if precheck_triggered and master_solve_skipped:
        classification = "precheck_eliminated"
    elif status == "UNKNOWN" or status == "RUNNING":
        classification = "master_unknown"
    elif status == "INFEASIBLE":
        classification = "master_infeasible"
    elif status == "CERTIFIED":
        classification = "certified"

    return {
        "schema": AI_CANDIDATE_RUN_SAMPLE_SCHEMA_ID,
        "sample_id": f"campaign_checkpoint:{candidate_key}",
        "candidate_key": candidate_key,
        "source": {
            "evidence_kind": "campaign_checkpoint_extraction",
            "extraction_time": now_iso(),
        },
        "geometry": {
            "w": w,
            "h": h,
            "area": w * h,
            "min_side": min(w, h),
            "max_side": max(w, h),
            "aspect_ratio": round(max(w, h) / max(min(w, h), 1), 3),
        },
        "frontier_candidate_metrics": dict(frontier),
        "precheck": {
            "triggered": precheck_triggered,
            "eliminated": bool(precheck_triggered and master_solve_skipped),
            "anchor_count": _int_or_none(precheck_bp.get("considered_anchor_count")),
            "screened_infeasible": _int_or_none(precheck_bp.get("screened_infeasible_anchor_count")),
            "screen_pass": _int_or_none(precheck_bp.get("screen_pass_anchor_count")),
            "max_packable_min": _int_or_none(precheck_bp.get("max_packable_min")),
            "max_packable_max": _int_or_none(precheck_bp.get("max_packable_max")),
        },
        "solver_metrics": {
            "master_status": master_status,
            "benders_iterations": _int_or_none(proof.get("benders_iterations")),
            "enumerated_bindings": _int_or_none(proof.get("enumerated_bindings")),
            "routing_attempts": _int_or_none(proof.get("routing_attempts")),
            "wall_time": _number_or_none(master_solve.get("wall_time")),
            "branches": _int_or_none(master_solve.get("branches")),
            "conflicts": _int_or_none(master_solve.get("conflicts")),
            "search_profile": proof.get("master_search_profile"),
        },
        "terminal": {
            "status": status,
            "outcome": outcome,
            "classification": classification,
        },
        "labels": {
            "precheck_eliminated": bool(precheck_triggered and master_solve_skipped),
            "high_prune_gain": _high_prune_gain(frontier),
            "unknown_or_running": status in ("UNKNOWN", "RUNNING"),
            "is_terminal": status in ("INFEASIBLE", "CERTIFIED"),
        },
        "timing": {
            "started_at": candidate.get("started_at"),
            "finished_at": candidate.get("finished_at"),
            "attempts": _int_or_none(candidate.get("attempts")),
        },
        "safety": build_ai_dataset_safety_contract(),
    }


def _high_prune_gain(frontier: Mapping[str, Any]) -> bool:
    prune_gain = _int_or_none(frontier.get("certification_prune_gain"))
    anchor_count = _int_or_none(frontier.get("anchor_count"))
    if prune_gain is None:
        return False
    if anchor_count is None or anchor_count <= 0:
        return prune_gain > 0
    return (float(prune_gain) / float(anchor_count)) >= 10.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract AI dataset from campaign state")
    parser.add_argument(
        "--campaign-state",
        type=Path,
        default=PROJECT_ROOT / "data" / "checkpoints" / "exact_campaign_state.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / ".artifacts" / "phase3b_ai_dataset_latest",
    )
    args = parser.parse_args()

    if not args.campaign_state.exists():
        print(f"Campaign state not found: {args.campaign_state}")
        sys.exit(1)

    with open(args.campaign_state, encoding="utf-8") as f:
        state = json.load(f)

    candidates = state.get("candidates", {})
    if not candidates:
        print("No candidates in campaign state")
        sys.exit(1)

    samples = []
    for key, cand in sorted(candidates.items()):
        samples.append(extract_sample_from_candidate(key, cand))

    args.output_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = args.output_dir / "candidate_runs.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")

    status_counts: dict[str, int] = {}
    classification_counts: dict[str, int] = {}
    for s in samples:
        st = s["terminal"]["status"]
        cl = s["terminal"]["classification"]
        status_counts[st] = status_counts.get(st, 0) + 1
        classification_counts[cl] = classification_counts.get(cl, 0) + 1

    summary = {
        "schema": AI_FEATURE_DATASET_SUMMARY_SCHEMA_ID,
        "generated_at": now_iso(),
        "sample_schema": AI_CANDIDATE_RUN_SAMPLE_SCHEMA_ID,
        "sample_count": len(samples),
        "source": "campaign_checkpoint_extraction",
        "campaign_state_path": str(args.campaign_state),
        "status_counts": dict(sorted(status_counts.items())),
        "classification_counts": dict(sorted(classification_counts.items())),
        "safety": build_ai_dataset_safety_contract(),
    }

    summary_path = args.output_dir / "dataset_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"Extracted {len(samples)} samples to {jsonl_path}")
    print(f"Status distribution: {status_counts}")
    print(f"Classification: {classification_counts}")


if __name__ == "__main__":
    main()
