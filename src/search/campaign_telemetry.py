from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from src.models.cut_manager import (
    RUN_STATUS_CERTIFIED,
    RUN_STATUS_INFEASIBLE,
    RUN_STATUS_UNKNOWN,
    RUN_STATUS_UNPROVEN,
)
from src.search.exact_campaign import atomic_write_json, now_iso

CAMPAIGN_TELEMETRY_SCHEMA_VERSION = 1
_AGGREGATE_SAMPLE_LIMIT = 128

_OUTCOME_ORDER = [
    "certified",
    "master_infeasible",
    "binding_empty_domain",
    "binding_timeout",
    "routing_precheck_reject",
    "routing_timeout",
    "all_infeasible",
    "infeasible",
    "unproven",
    "unknown",
    "worker_process_failed",
]

_STATUS_ORDER = [
    RUN_STATUS_CERTIFIED,
    RUN_STATUS_INFEASIBLE,
    RUN_STATUS_UNPROVEN,
    RUN_STATUS_UNKNOWN,
    "RUNNING",
]

_SELECTION_REASON_ORDER = [
    "probe_head",
    "objective_head",
    "prune_head",
    "anchor_head",
    "prune_fill",
]


def campaign_telemetry_output_path(campaign_path: Path) -> Path:
    path = Path(campaign_path)
    if path.name.endswith("_state.json"):
        return path.with_name(path.name.replace("_state.json", "_telemetry.json"))
    return path.with_name(f"{path.stem}_telemetry.json")


def classify_candidate_outcome(
    *,
    status: str,
    proof_summary: Optional[Mapping[str, Any]] = None,
) -> str:
    normalized_status = str(status or "")
    summary = dict(proof_summary or {})
    master_status = str(summary.get("master_status") or "")
    binding_status = str(summary.get("binding_status") or "")
    routing_status = str(summary.get("routing_status") or "")

    if normalized_status == RUN_STATUS_CERTIFIED:
        return "certified"
    if master_status in {"AREA_PRECHECK_FAILED", "INFEASIBLE"}:
        return "master_infeasible"
    if binding_status == "EMPTY_DOMAIN":
        return "binding_empty_domain"
    if binding_status == "TIMEOUT":
        return "binding_timeout"
    if routing_status in {"PRECHECK_FRONT_BLOCKED", "PRECHECK_RELAXED_DISCONNECTED"}:
        return "routing_precheck_reject"
    if routing_status == "TIMEOUT":
        return "routing_timeout"
    if routing_status == "ALL_INFEASIBLE":
        return "all_infeasible"
    if normalized_status == RUN_STATUS_INFEASIBLE:
        return "infeasible"
    if normalized_status == RUN_STATUS_UNPROVEN:
        return "unproven"
    return "unknown"


def _ordered_counter_dict(counter: Mapping[str, int], ordered_keys: Sequence[str]) -> Dict[str, int]:
    payload: Dict[str, int] = {}
    for key in ordered_keys:
        count = int(counter.get(key, 0))
        if count > 0:
            payload[str(key)] = int(count)
    remaining_keys = sorted(str(key) for key, value in counter.items() if int(value) > 0 and key not in payload)
    for key in remaining_keys:
        payload[str(key)] = int(counter[key])
    return payload


def _compact_proof_summary(proof_summary: Mapping[str, Any]) -> Dict[str, Any]:
    compact_keys = [
        "mode",
        "benders_iterations",
        "master_status",
        "binding_status",
        "routing_status",
        "diagnostic_flow_status",
        "routing_precheck_rejections",
        "fine_grained_exact_safe_cut_count",
        "binding_domain_empty_cut_count",
        "routing_front_blocked_cut_count",
        "frontier_selection_policy",
        "selection_reason",
    ]
    compact: Dict[str, Any] = {}
    for key in compact_keys:
        if key in proof_summary and proof_summary.get(key) is not None:
            compact[str(key)] = proof_summary.get(key)
    frontier_candidate_metrics = proof_summary.get("frontier_candidate_metrics")
    if isinstance(frontier_candidate_metrics, Mapping):
        compact["frontier_candidate_metrics"] = {
            str(k): int(v) if isinstance(v, bool | int) else v
            for k, v in frontier_candidate_metrics.items()
        }
    frontier_probe = proof_summary.get("frontier_probe")
    if isinstance(frontier_probe, Mapping):
        compact["frontier_probe"] = {
            "mode": str(frontier_probe.get("mode", "")),
            "probe_candidate": bool(frontier_probe.get("probe_candidate", False)),
            "probe_resume_pending": bool(frontier_probe.get("probe_resume_pending", False)),
            "probe_prune_gain": int(frontier_probe.get("probe_prune_gain", 0)),
        }
    precheck_lookahead = proof_summary.get("precheck_lookahead")
    if isinstance(precheck_lookahead, Mapping):
        compact["precheck_lookahead"] = {
            "enabled": bool(precheck_lookahead.get("enabled", False)),
            "slot_index": int(precheck_lookahead.get("slot_index", 0)),
            "limit": int(precheck_lookahead.get("limit", 0)),
            "is_selected_head": bool(
                precheck_lookahead.get("is_selected_head", False)
            ),
        }
    master_last_solve = proof_summary.get("master_last_solve")
    if isinstance(master_last_solve, Mapping):
        compact["master_last_solve"] = {
            "status": str(master_last_solve.get("status", "")),
            "wall_time": float(master_last_solve.get("wall_time", 0.0)),
            "user_time": float(master_last_solve.get("user_time", 0.0)),
            "deterministic_time": float(master_last_solve.get("deterministic_time", 0.0)),
            "branches": int(master_last_solve.get("branches", 0)),
            "conflicts": int(master_last_solve.get("conflicts", 0)),
            "binary_propagations": int(master_last_solve.get("binary_propagations", 0)),
            "integer_propagations": int(master_last_solve.get("integer_propagations", 0)),
            "hinted_literals": int(master_last_solve.get("hinted_literals", 0)),
            "known_feasible_hint": bool(master_last_solve.get("known_feasible_hint", False)),
            "search_profile": str(master_last_solve.get("search_profile", "")),
            "search_branching": str(master_last_solve.get("search_branching", "")),
        }
    master_warm_start = proof_summary.get("master_warm_start")
    if isinstance(master_warm_start, Mapping):
        compact["master_warm_start"] = {
            "used_greedy_hint": bool(master_warm_start.get("used_greedy_hint", False)),
            "greedy_hint_instances": int(
                master_warm_start.get("greedy_hint_instances", 0)
            ),
            "master_hinted_literals": int(
                master_warm_start.get("master_hinted_literals", 0)
            ),
            "ghost_anchor_hint_applied": bool(
                master_warm_start.get("ghost_anchor_hint_applied", False)
            ),
            "ghost_anchor_hint_idx": master_warm_start.get("ghost_anchor_hint_idx"),
            "ghost_anchor_hint_status": str(
                master_warm_start.get("ghost_anchor_hint_status", "")
            ),
            "residual_optional_zero_hinting_enabled": bool(
                master_warm_start.get(
                    "residual_optional_zero_hinting_enabled",
                    False,
                )
            ),
            "residual_optional_zero_hints": int(
                master_warm_start.get("residual_optional_zero_hints", 0)
            ),
            "warm_start_strategy": str(
                master_warm_start.get("warm_start_strategy", "")
            ),
            "ghost_aware_anchor_attempt_count": int(
                master_warm_start.get("ghost_aware_anchor_attempt_count", 0)
            ),
            "ghost_aware_anchor_selected_idx": master_warm_start.get(
                "ghost_aware_anchor_selected_idx"
            ),
            "ghost_aware_complete_mandatory_hint": bool(
                master_warm_start.get("ghost_aware_complete_mandatory_hint", False)
            ),
            "ghost_aware_hint_instances": int(
                master_warm_start.get("ghost_aware_hint_instances", 0)
            ),
            "ghost_aware_pose_order_portfolio_attempted": bool(
                master_warm_start.get(
                    "ghost_aware_pose_order_portfolio_attempted",
                    False,
                )
            ),
            "ghost_aware_pose_order_portfolio_success": bool(
                master_warm_start.get(
                    "ghost_aware_pose_order_portfolio_success",
                    False,
                )
            ),
            "ghost_aware_pose_order_portfolio_selected_ordering": master_warm_start.get(
                "ghost_aware_pose_order_portfolio_selected_ordering"
            ),
            "ghost_aware_pose_order_portfolio_attempt_count": int(
                master_warm_start.get(
                    "ghost_aware_pose_order_portfolio_attempt_count",
                    0,
                )
            ),
            "ghost_aware_pose_order_portfolio_failed_anchor_count": int(
                master_warm_start.get(
                    "ghost_aware_pose_order_portfolio_failed_anchor_count",
                    0,
                )
            ),
            "ghost_aware_pose_order_portfolio_failure_reason_counts": dict(
                master_warm_start.get(
                    "ghost_aware_pose_order_portfolio_failure_reason_counts",
                    {},
                )
            ),
            "ghost_aware_pose_order_portfolio_failure_samples": [
                dict(entry)
                for entry in list(
                    master_warm_start.get(
                        "ghost_aware_pose_order_portfolio_failure_samples",
                        [],
                    )
                )
                if isinstance(entry, Mapping)
            ],
            "ghost_aware_pose_order_validation_attempt_count": int(
                master_warm_start.get(
                    "ghost_aware_pose_order_validation_attempt_count",
                    0,
                )
            ),
            "ghost_aware_pose_order_validation_rejected_count": int(
                master_warm_start.get(
                    "ghost_aware_pose_order_validation_rejected_count",
                    0,
                )
            ),
            "ghost_aware_pose_order_validation_last_status": master_warm_start.get(
                "ghost_aware_pose_order_validation_last_status"
            ),
            "ghost_aware_pose_order_validation_last_reason": master_warm_start.get(
                "ghost_aware_pose_order_validation_last_reason"
            ),
            "local_repair_attempted": bool(
                master_warm_start.get("local_repair_attempted", False)
            ),
            "local_repair_success": bool(
                master_warm_start.get("local_repair_success", False)
            ),
            "local_repair_trigger_reason": master_warm_start.get(
                "local_repair_trigger_reason"
            ),
            "local_repair_window_size": int(
                master_warm_start.get("local_repair_window_size", 0)
            ),
            "local_repair_anchor_idx": master_warm_start.get(
                "local_repair_anchor_idx"
            ),
            "local_repair_failed_group_id": master_warm_start.get(
                "local_repair_failed_group_id"
            ),
            "local_repair_failed_group_template": master_warm_start.get(
                "local_repair_failed_group_template"
            ),
            "local_repair_portfolio_attempt_count": int(
                master_warm_start.get("local_repair_portfolio_attempt_count", 0)
            ),
            "local_repair_selected_group_orderings": [
                str(token)
                for token in list(
                    master_warm_start.get(
                        "local_repair_selected_group_orderings",
                        [],
                    )
                )[:2]
            ],
        }
    master_start_feasibility = proof_summary.get("master_start_feasibility")
    if isinstance(master_start_feasibility, Mapping):
        compact["master_start_feasibility"] = {
            "ghost_anchor_hint_applied": bool(
                master_start_feasibility.get("ghost_anchor_hint_applied", False)
            ),
            "ghost_anchor_hint_idx": master_start_feasibility.get(
                "ghost_anchor_hint_idx"
            ),
            "ghost_anchor_hint_status": str(
                master_start_feasibility.get("ghost_anchor_hint_status", "")
            ),
            "ghost_anchor_total_count": int(
                master_start_feasibility.get("ghost_anchor_total_count", 0)
            ),
            "ghost_anchor_compatible_count": int(
                master_start_feasibility.get("ghost_anchor_compatible_count", 0)
            ),
            "mandatory_hint_pose_count": int(
                master_start_feasibility.get("mandatory_hint_pose_count", 0)
            ),
            "mandatory_hint_occupied_cell_count": int(
                master_start_feasibility.get(
                    "mandatory_hint_occupied_cell_count",
                    0,
                )
            ),
            "required_optional_positive_hints": int(
                master_start_feasibility.get(
                    "required_optional_positive_hints",
                    0,
                )
            ),
            "residual_optional_positive_hints": int(
                master_start_feasibility.get(
                    "residual_optional_positive_hints",
                    0,
                )
            ),
            "residual_optional_zero_hints": int(
                master_start_feasibility.get("residual_optional_zero_hints", 0)
            ),
            "warm_start_strategy": str(
                master_start_feasibility.get("warm_start_strategy", "")
            ),
            "ghost_aware_anchor_attempt_count": int(
                master_start_feasibility.get("ghost_aware_anchor_attempt_count", 0)
            ),
            "ghost_aware_anchor_selected_idx": master_start_feasibility.get(
                "ghost_aware_anchor_selected_idx"
            ),
            "ghost_aware_complete_mandatory_hint": bool(
                master_start_feasibility.get(
                    "ghost_aware_complete_mandatory_hint",
                    False,
                )
            ),
            "ghost_aware_hint_instances": int(
                master_start_feasibility.get("ghost_aware_hint_instances", 0)
            ),
            "ghost_aware_pose_order_portfolio_attempted": bool(
                master_start_feasibility.get(
                    "ghost_aware_pose_order_portfolio_attempted",
                    False,
                )
            ),
            "ghost_aware_pose_order_portfolio_success": bool(
                master_start_feasibility.get(
                    "ghost_aware_pose_order_portfolio_success",
                    False,
                )
            ),
            "ghost_aware_pose_order_portfolio_selected_ordering": master_start_feasibility.get(
                "ghost_aware_pose_order_portfolio_selected_ordering"
            ),
            "ghost_aware_pose_order_portfolio_attempt_count": int(
                master_start_feasibility.get(
                    "ghost_aware_pose_order_portfolio_attempt_count",
                    0,
                )
            ),
            "ghost_aware_pose_order_portfolio_failed_anchor_count": int(
                master_start_feasibility.get(
                    "ghost_aware_pose_order_portfolio_failed_anchor_count",
                    0,
                )
            ),
            "ghost_aware_pose_order_portfolio_failure_reason_counts": dict(
                master_start_feasibility.get(
                    "ghost_aware_pose_order_portfolio_failure_reason_counts",
                    {},
                )
            ),
            "ghost_aware_pose_order_portfolio_failure_samples": [
                dict(entry)
                for entry in list(
                    master_start_feasibility.get(
                        "ghost_aware_pose_order_portfolio_failure_samples",
                        [],
                    )
                )
                if isinstance(entry, Mapping)
            ],
            "ghost_aware_pose_order_validation_attempt_count": int(
                master_start_feasibility.get(
                    "ghost_aware_pose_order_validation_attempt_count",
                    0,
                )
            ),
            "ghost_aware_pose_order_validation_rejected_count": int(
                master_start_feasibility.get(
                    "ghost_aware_pose_order_validation_rejected_count",
                    0,
                )
            ),
            "ghost_aware_pose_order_validation_last_status": master_start_feasibility.get(
                "ghost_aware_pose_order_validation_last_status"
            ),
            "ghost_aware_pose_order_validation_last_reason": master_start_feasibility.get(
                "ghost_aware_pose_order_validation_last_reason"
            ),
            "local_repair_attempted": bool(
                master_start_feasibility.get("local_repair_attempted", False)
            ),
            "local_repair_success": bool(
                master_start_feasibility.get("local_repair_success", False)
            ),
            "local_repair_trigger_reason": master_start_feasibility.get(
                "local_repair_trigger_reason"
            ),
            "local_repair_window_size": int(
                master_start_feasibility.get("local_repair_window_size", 0)
            ),
            "local_repair_anchor_idx": master_start_feasibility.get(
                "local_repair_anchor_idx"
            ),
            "local_repair_failed_group_id": master_start_feasibility.get(
                "local_repair_failed_group_id"
            ),
            "local_repair_failed_group_template": master_start_feasibility.get(
                "local_repair_failed_group_template"
            ),
            "local_repair_portfolio_attempt_count": int(
                master_start_feasibility.get("local_repair_portfolio_attempt_count", 0)
            ),
            "local_repair_selected_group_orderings": [
                str(token)
                for token in list(
                    master_start_feasibility.get(
                        "local_repair_selected_group_orderings",
                        [],
                    )
                )[:2]
            ],
        }
    master_domain_tightening = proof_summary.get("master_domain_tightening")
    if isinstance(master_domain_tightening, Mapping):
        compact["master_domain_tightening"] = {
            "ghost_power_capacity_screen_enabled": bool(
                master_domain_tightening.get(
                    "ghost_power_capacity_screen_enabled",
                    False,
                )
            ),
            "ghost_disabled_placements": int(
                master_domain_tightening.get("ghost_disabled_placements", 0)
            ),
            "ghost_surviving_placements": int(
                master_domain_tightening.get("ghost_surviving_placements", 0)
            ),
            "ghost_conditioned_family_upper_bound_constraints": int(
                master_domain_tightening.get(
                    "ghost_conditioned_family_upper_bound_constraints",
                    0,
                )
            ),
            "ghost_family_reduction_anchor_count": int(
                master_domain_tightening.get(
                    "ghost_family_reduction_anchor_count",
                    0,
                )
            ),
        }
    master_signature_tightening = proof_summary.get("master_signature_tightening")
    if isinstance(master_signature_tightening, Mapping):
        compact["master_signature_tightening"] = {
            "mandatory_bucket_upper_bound_constraints": int(
                master_signature_tightening.get(
                    "mandatory_bucket_upper_bound_constraints",
                    0,
                )
            ),
            "required_optional_bucket_upper_bound_constraints": int(
                master_signature_tightening.get(
                    "required_optional_bucket_upper_bound_constraints",
                    0,
                )
            ),
            "ghost_conditioned_mandatory_bucket_constraints": int(
                master_signature_tightening.get(
                    "ghost_conditioned_mandatory_bucket_constraints",
                    0,
                )
            ),
            "ghost_conditioned_required_optional_bucket_constraints": int(
                master_signature_tightening.get(
                    "ghost_conditioned_required_optional_bucket_constraints",
                    0,
                )
            ),
            "ghost_signature_reduction_anchor_count": int(
                master_signature_tightening.get(
                    "ghost_signature_reduction_anchor_count",
                    0,
                )
            ),
        }
    master_residual_signature_tightening = proof_summary.get(
        "master_residual_signature_tightening"
    )
    if isinstance(master_residual_signature_tightening, Mapping):
        compact["master_residual_signature_tightening"] = {
            "bucket_upper_bound_constraints": int(
                master_residual_signature_tightening.get(
                    "bucket_upper_bound_constraints",
                    0,
                )
            ),
            "ghost_conditioned_bucket_constraints": int(
                master_residual_signature_tightening.get(
                    "ghost_conditioned_bucket_constraints",
                    0,
                )
            ),
            "ghost_signature_reduction_anchor_count": int(
                master_residual_signature_tightening.get(
                    "ghost_signature_reduction_anchor_count",
                    0,
                )
            ),
        }
    master_coordinate_symmetry = proof_summary.get("master_coordinate_symmetry")
    if isinstance(master_coordinate_symmetry, Mapping):
        compact["master_coordinate_symmetry"] = {
            "enabled": bool(master_coordinate_symmetry.get("enabled", False)),
            "mandatory_signature_monotonic_constraints": int(
                master_coordinate_symmetry.get(
                    "mandatory_signature_monotonic_constraints",
                    0,
                )
            ),
            "required_optional_signature_monotonic_constraints": int(
                master_coordinate_symmetry.get(
                    "required_optional_signature_monotonic_constraints",
                    0,
                )
            ),
            "residual_optional_signature_monotonic_constraints": int(
                master_coordinate_symmetry.get(
                    "residual_optional_signature_monotonic_constraints",
                    0,
                )
            ),
        }
    master_domain_activation = proof_summary.get("master_domain_activation")
    if isinstance(master_domain_activation, Mapping):
        compact["master_domain_activation"] = {
            "ghost_anchor_count": int(
                master_domain_activation.get("ghost_anchor_count", 0)
            ),
            "mandatory_slot_count": int(
                master_domain_activation.get("mandatory_slot_count", 0)
            ),
            "required_optional_slot_count": int(
                master_domain_activation.get("required_optional_slot_count", 0)
            ),
            "residual_optional_slot_count": int(
                master_domain_activation.get("residual_optional_slot_count", 0)
            ),
            "mandatory_pose_literal_count": int(
                master_domain_activation.get("mandatory_pose_literal_count", 0)
            ),
            "required_optional_pose_literal_count": int(
                master_domain_activation.get(
                    "required_optional_pose_literal_count",
                    0,
                )
            ),
            "residual_optional_pose_literal_count": int(
                master_domain_activation.get(
                    "residual_optional_pose_literal_count",
                    0,
                )
            ),
            "required_optional_active_slot_upper_bound_sum": int(
                master_domain_activation.get(
                    "required_optional_active_slot_upper_bound_sum",
                    0,
                )
            ),
            "residual_optional_active_slot_upper_bound_sum": int(
                master_domain_activation.get(
                    "residual_optional_active_slot_upper_bound_sum",
                    0,
                )
            ),
        }
    master_start_failure_attribution = proof_summary.get(
        "master_start_failure_attribution"
    )
    if isinstance(master_start_failure_attribution, Mapping):
        compact["master_start_failure_attribution"] = {
            "attempted_anchor_count": int(
                master_start_failure_attribution.get("attempted_anchor_count", 0)
            ),
            "failed_anchor_count": int(
                master_start_failure_attribution.get("failed_anchor_count", 0)
            ),
            "failure_reason_counts": {
                str(key): int(value)
                for key, value in dict(
                    master_start_failure_attribution.get("failure_reason_counts", {})
                ).items()
                if int(value) > 0
            },
            "first_failed_anchor_idx": master_start_failure_attribution.get(
                "first_failed_anchor_idx"
            ),
            "first_failed_group_id": master_start_failure_attribution.get(
                "first_failed_group_id"
            ),
            "first_failed_group_template": str(
                master_start_failure_attribution.get(
                    "first_failed_group_template",
                    "",
                )
            ),
            "first_failed_group_required_count": int(
                master_start_failure_attribution.get(
                    "first_failed_group_required_count",
                    0,
                )
            ),
            "first_failed_group_candidate_count": int(
                master_start_failure_attribution.get(
                    "first_failed_group_candidate_count",
                    0,
                )
            ),
            "first_failed_group_surviving_after_blocked_count": int(
                master_start_failure_attribution.get(
                    "first_failed_group_surviving_after_blocked_count",
                    0,
                )
            ),
            "first_failed_group_surviving_at_failure_count": int(
                master_start_failure_attribution.get(
                    "first_failed_group_surviving_at_failure_count",
                    0,
                )
            ),
            "first_failed_group_position": master_start_failure_attribution.get(
                "first_failed_group_position"
            ),
            "top_failed_groups": [
                {
                    "group_id": str(entry.get("group_id", "")),
                    "facility_type": str(entry.get("facility_type", "")),
                    "count": int(entry.get("count", 0)),
                }
                for entry in list(
                    master_start_failure_attribution.get("top_failed_groups", [])
                )[:5]
                if int(entry.get("count", 0)) > 0
            ],
            "top_failed_group_failures": [
                {
                    "group_id": str(entry.get("group_id", "")),
                    "facility_type": str(entry.get("facility_type", "")),
                    "failure_reason": str(entry.get("failure_reason", "")),
                    "count": int(entry.get("count", 0)),
                }
                for entry in list(
                    master_start_failure_attribution.get(
                        "top_failed_group_failures",
                        [],
                    )
                )[:8]
                if int(entry.get("count", 0)) > 0
            ],
            "failed_anchor_samples": [
                {
                    "anchor_idx": int(entry.get("anchor_idx", 0)),
                    "failure_reason": str(entry.get("failure_reason", "")),
                    "first_failed_group_id": entry.get("first_failed_group_id"),
                    "first_failed_group_template": entry.get(
                        "first_failed_group_template"
                    ),
                    "first_failed_group_position": entry.get(
                        "first_failed_group_position"
                    ),
                    "first_failed_group_required_count": int(
                        entry.get("first_failed_group_required_count", 0)
                    ),
                    "first_failed_group_candidate_count": int(
                        entry.get("first_failed_group_candidate_count", 0)
                    ),
                    "first_failed_group_surviving_after_blocked_count": int(
                        entry.get(
                            "first_failed_group_surviving_after_blocked_count",
                            0,
                        )
                    ),
                    "first_failed_group_surviving_at_failure_count": int(
                        entry.get(
                            "first_failed_group_surviving_at_failure_count",
                            0,
                        )
                    ),
                    "blocked_cell_count": int(entry.get("blocked_cell_count", 0)),
                    "blocked_bbox": entry.get("blocked_bbox"),
                    "local_repair_attempted": bool(
                        entry.get("local_repair_attempted", False)
                    ),
                    "local_repair_success": bool(
                        entry.get("local_repair_success", False)
                    ),
                    "local_repair_attempt_count": int(
                        entry.get("local_repair_attempt_count", 0)
                    ),
                    **_coordinate_validation_failure_sample_fields(entry),
                }
                for entry in list(
                    master_start_failure_attribution.get("failed_anchor_samples", [])
                )[:8]
                if isinstance(entry, Mapping)
            ],
        }
        if not compact["master_start_failure_attribution"].get(
            "failed_anchor_samples"
        ):
            compact["master_start_failure_attribution"].pop(
                "failed_anchor_samples",
                None,
            )
    master_start_local_repair = proof_summary.get("master_start_local_repair")
    if isinstance(master_start_local_repair, Mapping):
        compact["master_start_local_repair"] = {
            "local_repair_attempted": bool(
                master_start_local_repair.get("local_repair_attempted", False)
            ),
            "local_repair_success": bool(
                master_start_local_repair.get("local_repair_success", False)
            ),
            "local_repair_trigger_reason": master_start_local_repair.get(
                "local_repair_trigger_reason"
            ),
            "local_repair_window_size": int(
                master_start_local_repair.get("local_repair_window_size", 0)
            ),
            "local_repair_anchor_idx": master_start_local_repair.get(
                "local_repair_anchor_idx"
            ),
            "local_repair_failed_group_id": master_start_local_repair.get(
                "local_repair_failed_group_id"
            ),
            "local_repair_failed_group_template": master_start_local_repair.get(
                "local_repair_failed_group_template"
            ),
            "local_repair_portfolio_attempt_count": int(
                master_start_local_repair.get(
                    "local_repair_portfolio_attempt_count",
                    0,
                )
            ),
            "local_repair_selected_group_orderings": [
                str(token)
                for token in list(
                    master_start_local_repair.get(
                        "local_repair_selected_group_orderings",
                        [],
                    )
                )[:2]
            ],
            "local_repair_attempt_count": int(
                master_start_local_repair.get("local_repair_attempt_count", 0)
            ),
            "local_repair_success_count": int(
                master_start_local_repair.get("local_repair_success_count", 0)
            ),
            "local_repair_intra_group_attempted_count": int(
                master_start_local_repair.get(
                    "local_repair_intra_group_attempted_count",
                    0,
                )
            ),
            "local_repair_committed_attempted_count": int(
                master_start_local_repair.get(
                    "local_repair_committed_attempted_count",
                    0,
                )
            ),
            "local_repair_window1_count": int(
                master_start_local_repair.get("local_repair_window1_count", 0)
            ),
            "local_repair_window2_count": int(
                master_start_local_repair.get("local_repair_window2_count", 0)
            ),
        }
    master_boundary_port_feasibility = proof_summary.get(
        "master_boundary_port_feasibility"
    )
    if isinstance(master_boundary_port_feasibility, Mapping):
        compact["master_boundary_port_feasibility"] = {
            "supported": bool(
                master_boundary_port_feasibility.get("supported", False)
            ),
            "required_count": int(
                master_boundary_port_feasibility.get("required_count", 0)
            ),
            "considered_anchor_count": int(
                master_boundary_port_feasibility.get("considered_anchor_count", 0)
            ),
            "screened_infeasible_anchor_count": int(
                master_boundary_port_feasibility.get(
                    "screened_infeasible_anchor_count",
                    0,
                )
            ),
            "screen_pass_anchor_count": int(
                master_boundary_port_feasibility.get(
                    "screen_pass_anchor_count",
                    0,
                )
            ),
            "unsupported_anchor_count": int(
                master_boundary_port_feasibility.get(
                    "unsupported_anchor_count",
                    0,
                )
            ),
            "max_packable_min": master_boundary_port_feasibility.get(
                "max_packable_min"
            ),
            "max_packable_max": master_boundary_port_feasibility.get(
                "max_packable_max"
            ),
            "first_infeasible_anchor_idx": master_boundary_port_feasibility.get(
                "first_infeasible_anchor_idx"
            ),
            "first_infeasible_anchor_max_packable": master_boundary_port_feasibility.get(
                "first_infeasible_anchor_max_packable"
            ),
        }
    master_mandatory_group_prechecks = proof_summary.get(
        "master_mandatory_group_prechecks"
    )
    if isinstance(master_mandatory_group_prechecks, Mapping):
        compact["master_mandatory_group_prechecks"] = {
            "evaluated": bool(
                master_mandatory_group_prechecks.get("evaluated", False)
            ),
            "skipped_due_to_upstream_precheck": bool(
                master_mandatory_group_prechecks.get(
                    "skipped_due_to_upstream_precheck",
                    False,
                )
            ),
            "upstream_anchor_filter_count": int(
                master_mandatory_group_prechecks.get(
                    "upstream_anchor_filter_count",
                    0,
                )
            ),
            "supported_group_count": int(
                master_mandatory_group_prechecks.get("supported_group_count", 0)
            ),
            "groups": [
                {
                    "group_id": str(entry.get("group_id", "")),
                    "facility_type": str(entry.get("facility_type", "")),
                    "operation_type": str(entry.get("operation_type", "")),
                    "required_count": int(entry.get("required_count", 0)),
                    "oracle_class": entry.get("oracle_class"),
                    "oracle_mode": str(entry.get("oracle_mode", "unsupported")),
                    "supported": bool(entry.get("supported", False)),
                    "unsupported_reason": entry.get("unsupported_reason"),
                    "considered_anchor_count": int(
                        entry.get("considered_anchor_count", 0)
                    ),
                    "screened_infeasible_anchor_count": int(
                        entry.get("screened_infeasible_anchor_count", 0)
                    ),
                    "screen_pass_anchor_count": int(
                        entry.get("screen_pass_anchor_count", 0)
                    ),
                    "unsupported_anchor_count": int(
                        entry.get("unsupported_anchor_count", 0)
                    ),
                    "max_packable_min": entry.get("max_packable_min"),
                    "max_packable_max": entry.get("max_packable_max"),
                    "first_infeasible_anchor_idx": entry.get(
                        "first_infeasible_anchor_idx"
                    ),
                    "first_infeasible_anchor_max_packable": entry.get(
                        "first_infeasible_anchor_max_packable"
                    ),
                }
                for entry in list(master_mandatory_group_prechecks.get("groups", []))
            ],
        }
    master_mandatory_support_diagnostics = proof_summary.get(
        "master_mandatory_support_diagnostics"
    )
    if isinstance(master_mandatory_support_diagnostics, Mapping):
        compact["master_mandatory_support_diagnostics"] = {
            "unsupported_group_count": int(
                master_mandatory_support_diagnostics.get(
                    "unsupported_group_count",
                    0,
                )
            ),
            "empty_candidate_pool_group_count": int(
                master_mandatory_support_diagnostics.get(
                    "empty_candidate_pool_group_count",
                    0,
                )
            ),
            "groups": [
                {
                    "group_id": str(entry.get("group_id", "")),
                    "facility_type": str(entry.get("facility_type", "")),
                    "operation_type": str(entry.get("operation_type", "")),
                    "required_count": int(entry.get("required_count", 0)),
                    "candidate_pool_count": int(
                        entry.get("candidate_pool_count", 0)
                    ),
                    "unsupported_reason": entry.get("unsupported_reason"),
                }
                for entry in list(
                    master_mandatory_support_diagnostics.get("groups", [])
                )
            ],
        }
    master_candidate_precheck = proof_summary.get("master_candidate_precheck")
    if isinstance(master_candidate_precheck, Mapping):
        compact["master_candidate_precheck"] = {
            "triggered": bool(master_candidate_precheck.get("triggered", False)),
            "precheck_reason": master_candidate_precheck.get("precheck_reason"),
            "master_solve_skipped": bool(
                master_candidate_precheck.get("master_solve_skipped", False)
            ),
            "supported": bool(master_candidate_precheck.get("supported", False)),
            "considered_anchor_count": int(
                master_candidate_precheck.get("considered_anchor_count", 0)
            ),
            "screened_infeasible_anchor_count": int(
                master_candidate_precheck.get(
                    "screened_infeasible_anchor_count",
                    0,
                )
            ),
            "screen_pass_anchor_count": int(
                master_candidate_precheck.get("screen_pass_anchor_count", 0)
            ),
            "max_packable_min": master_candidate_precheck.get("max_packable_min"),
            "max_packable_max": master_candidate_precheck.get("max_packable_max"),
            "first_infeasible_anchor_idx": master_candidate_precheck.get(
                "first_infeasible_anchor_idx"
            ),
            "first_infeasible_anchor_max_packable": master_candidate_precheck.get(
                "first_infeasible_anchor_max_packable"
            ),
            "triggered_group_id": master_candidate_precheck.get(
                "triggered_group_id"
            ),
            "triggered_group_facility_type": master_candidate_precheck.get(
                "triggered_group_facility_type"
            ),
            "triggered_group_operation_type": master_candidate_precheck.get(
                "triggered_group_operation_type"
            ),
            "triggered_group_required_count": int(
                master_candidate_precheck.get("triggered_group_required_count", 0)
            ),
        }
        anchor119_row_domain_guard_advisory = master_candidate_precheck.get(
            "anchor119_row_domain_guard_advisory"
        )
        if isinstance(anchor119_row_domain_guard_advisory, Mapping):
            compact["master_candidate_precheck"][
                "anchor119_row_domain_guard_advisory"
            ] = {
                "enabled": bool(anchor119_row_domain_guard_advisory.get("enabled", False)),
                "would_trigger": bool(
                    anchor119_row_domain_guard_advisory.get("would_trigger", False)
                ),
                "triggered": bool(
                    anchor119_row_domain_guard_advisory.get("triggered", False)
                ),
                "reason": anchor119_row_domain_guard_advisory.get("reason"),
                "guard_id": anchor119_row_domain_guard_advisory.get("guard_id"),
                "payload_id": anchor119_row_domain_guard_advisory.get("payload_id"),
                "domain_hash": anchor119_row_domain_guard_advisory.get("domain_hash"),
                "tiling_outcome": anchor119_row_domain_guard_advisory.get(
                    "tiling_outcome"
                ),
                "dp_outcome": anchor119_row_domain_guard_advisory.get("dp_outcome"),
                "advisory_only": bool(
                    anchor119_row_domain_guard_advisory.get("advisory_only", False)
                ),
                "requested_state": anchor119_row_domain_guard_advisory.get(
                    "requested_state"
                ),
                "effective_state": anchor119_row_domain_guard_advisory.get(
                    "effective_state"
                ),
                "runtime_precheck_enabled": bool(
                    anchor119_row_domain_guard_advisory.get(
                        "runtime_precheck_enabled",
                        False,
                    )
                ),
                "runtime_activation_allowed": bool(
                    anchor119_row_domain_guard_advisory.get(
                        "runtime_activation_allowed",
                        False,
                    )
                ),
                "runtime_semantics_changed": bool(
                    anchor119_row_domain_guard_advisory.get(
                        "runtime_semantics_changed",
                        False,
                    )
                ),
                "proof_source": bool(
                    anchor119_row_domain_guard_advisory.get("proof_source", False)
                ),
                "candidate_elimination_claim": bool(
                    anchor119_row_domain_guard_advisory.get(
                        "candidate_elimination_claim",
                        False,
                    )
                ),
                "non_trigger_max_slot_count": anchor119_row_domain_guard_advisory.get(
                    "non_trigger_max_slot_count"
                ),
                "anchored_trigger_min_slot_count": anchor119_row_domain_guard_advisory.get(
                    "anchored_trigger_min_slot_count"
                ),
                "free_ghost_trigger_min_slot_count": anchor119_row_domain_guard_advisory.get(
                    "free_ghost_trigger_min_slot_count"
                ),
                "runtime_enablement_blockers": [
                    str(token)
                    for token in list(
                        anchor119_row_domain_guard_advisory.get(
                            "runtime_enablement_blockers",
                            [],
                        )
                    )
                ],
            }
            runtime_decision = anchor119_row_domain_guard_advisory.get("runtime_decision")
            if isinstance(runtime_decision, Mapping):
                compact["master_candidate_precheck"][
                    "anchor119_row_domain_guard_advisory"
                ]["runtime_decision"] = {
                    "decision_id": runtime_decision.get("decision_id"),
                    "requested_state": runtime_decision.get("requested_state"),
                    "effective_state": runtime_decision.get("effective_state"),
                    "would_trigger": bool(runtime_decision.get("would_trigger", False)),
                    "triggered": bool(runtime_decision.get("triggered", False)),
                    "runtime_activation_allowed": bool(
                        runtime_decision.get("runtime_activation_allowed", False)
                    ),
                    "apply_runtime_elimination": bool(
                        runtime_decision.get("apply_runtime_elimination", False)
                    ),
                    "blocked_reason": runtime_decision.get("blocked_reason"),
                    "reason": runtime_decision.get("reason"),
                    "runtime_enablement_blockers": [
                        str(token)
                        for token in list(
                            runtime_decision.get("runtime_enablement_blockers", [])
                        )
                    ],
                }
    coordinate_validation_precheck = proof_summary.get("coordinate_validation_precheck")
    if isinstance(coordinate_validation_precheck, Mapping):
        compact["coordinate_validation_precheck"] = {
            "evaluated": bool(coordinate_validation_precheck.get("evaluated", False)),
            "triggered": bool(coordinate_validation_precheck.get("triggered", False)),
            "skipped_due_to_anchor_limit": bool(
                coordinate_validation_precheck.get("skipped_due_to_anchor_limit", False)
            ),
            "skip_reason": coordinate_validation_precheck.get("skip_reason"),
            "time_limit_seconds": float(
                coordinate_validation_precheck.get("time_limit_seconds", 0.0)
            ),
            "max_anchor_count": int(
                coordinate_validation_precheck.get("max_anchor_count", 0)
            ),
            "considered_anchor_count": int(
                coordinate_validation_precheck.get("considered_anchor_count", 0)
            ),
            "evaluated_anchor_count": int(
                coordinate_validation_precheck.get("evaluated_anchor_count", 0)
            ),
            "infeasible_anchor_count": int(
                coordinate_validation_precheck.get("infeasible_anchor_count", 0)
            ),
            "accepted_anchor_count": int(
                coordinate_validation_precheck.get("accepted_anchor_count", 0)
            ),
            "unknown_anchor_count": int(
                coordinate_validation_precheck.get("unknown_anchor_count", 0)
            ),
            "skipped_anchor_count": int(
                coordinate_validation_precheck.get("skipped_anchor_count", 0)
            ),
            "short_circuited_after_non_triggering_anchor": bool(
                coordinate_validation_precheck.get(
                    "short_circuited_after_non_triggering_anchor",
                    False,
                )
            ),
            "status_counts": {
                str(key): int(value)
                for key, value in dict(
                    coordinate_validation_precheck.get("status_counts", {})
                ).items()
            },
        }
    return compact


def _coordinate_validation_failure_sample_fields(entry: Mapping[str, Any]) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    for key in (
        "coordinate_validation_status",
        "coordinate_validation_reason",
        "coordinate_validation_solver_profile_id",
    ):
        if key in entry:
            fields[key] = str(entry.get(key, ""))
    for key in (
        "coordinate_validation_forced_slot_field_count",
        "coordinate_validation_forced_ghost_anchor",
    ):
        if key in entry:
            fields[key] = entry.get(key)
    for key in (
        "capacity_conflict",
        "same_x_strip_capacity_precheck",
        "ghost_overlap_forced_domain_precheck",
        "ghost_y_overlap_precheck",
        "signature_monotonic_precheck",
    ):
        value = entry.get(key)
        if isinstance(value, Mapping):
            fields[key] = dict(value)
    return fields


def build_wave_summary(
    *,
    wave_index: int,
    candidate_results: Sequence[Mapping[str, Any]],
    completed: bool,
    failure_reason: Optional[str],
    dispatched_candidate_keys: Sequence[str],
    elapsed_seconds: Optional[float] = None,
    peak_rss_bytes_external_total: Optional[int] = None,
    peak_rss_bytes_internal_max_single_process: Optional[int] = None,
) -> Dict[str, Any]:
    normalized_results = []
    status_counts: Counter[str] = Counter()
    outcome_counts: Counter[str] = Counter()
    loaded_cut_count_sum = 0
    generated_cut_count_sum = 0
    probe_candidate_keys: list[str] = []
    probe_prune_gain_sum = 0
    probe_prune_gain_max = 0
    probe_resume_pending_count = 0

    for raw_result in candidate_results:
        proof_summary = dict(raw_result.get("proof_summary", {}))
        status = str(raw_result.get("status", ""))
        outcome = classify_candidate_outcome(status=status, proof_summary=proof_summary)
        probe_candidate = bool(raw_result.get("probe_candidate", False))
        probe_prune_gain = int(raw_result.get("probe_prune_gain", 0))
        probe_resume_pending = bool(raw_result.get("probe_resume_pending", False))
        entry = {
            "candidate_key": str(raw_result.get("candidate_key", "")),
            "dispatch_seq": int(raw_result.get("dispatch_seq", 0)),
            "attempt_index": int(raw_result.get("attempt_index", 0)),
            "wave_slot_index": int(raw_result.get("wave_slot_index", 0)),
            "selection_reason": str(raw_result.get("selection_reason", "")),
            "status": status,
            "outcome_category": outcome,
            "loaded_exact_safe_cut_count": int(raw_result.get("loaded_exact_safe_cut_count", 0)),
            "generated_exact_safe_cut_count": int(raw_result.get("generated_exact_safe_cut_count", 0)),
            "probe_candidate": probe_candidate,
            "probe_prune_gain": probe_prune_gain,
            "probe_resume_pending": probe_resume_pending,
            "frontier_probe_mode": str(raw_result.get("frontier_probe_mode", "")),
            "proof_status_summary": _compact_proof_summary(proof_summary),
        }
        normalized_results.append(entry)
        status_counts[status] += 1
        outcome_counts[outcome] += 1
        loaded_cut_count_sum += int(entry["loaded_exact_safe_cut_count"])
        generated_cut_count_sum += int(entry["generated_exact_safe_cut_count"])
        if probe_candidate:
            probe_candidate_keys.append(str(entry["candidate_key"]))
            probe_prune_gain_sum += int(probe_prune_gain)
            probe_prune_gain_max = max(probe_prune_gain_max, int(probe_prune_gain))
        if probe_resume_pending:
            probe_resume_pending_count += 1

    failure_label = None if failure_reason is None else str(failure_reason)
    if failure_label is not None:
        outcome_counts["worker_process_failed"] += 1

    return {
        "wave_index": int(wave_index),
        "candidate_count": int(len(normalized_results)),
        "completed": bool(completed),
        "failure_reason": failure_label,
        "probe_round_active": bool(probe_candidate_keys),
        "probe_candidate_keys": probe_candidate_keys,
        "probe_prune_gain_sum": int(probe_prune_gain_sum),
        "probe_prune_gain_max": int(probe_prune_gain_max),
        "probe_resume_pending_count": int(probe_resume_pending_count),
        "dispatched_candidate_keys": [str(key) for key in dispatched_candidate_keys],
        "elapsed_seconds": None if elapsed_seconds is None else float(elapsed_seconds),
        "peak_rss_bytes_external_total": None
        if peak_rss_bytes_external_total is None
        else int(peak_rss_bytes_external_total),
        "peak_rss_bytes_internal_max_single_process": None
        if peak_rss_bytes_internal_max_single_process is None
        else int(peak_rss_bytes_internal_max_single_process),
        "status_counts": _ordered_counter_dict(status_counts, _STATUS_ORDER),
        "outcome_counts": _ordered_counter_dict(outcome_counts, _OUTCOME_ORDER),
        "loaded_exact_safe_cut_count_sum": int(loaded_cut_count_sum),
        "generated_exact_safe_cut_count_sum": int(generated_cut_count_sum),
        "candidate_results": normalized_results,
    }


def _aggregate_waves(waves: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    waves = [dict(wave) for wave in waves]
    status_counts: Counter[str] = Counter()
    outcome_counts: Counter[str] = Counter()
    failure_reason_counts: Counter[str] = Counter()
    selection_reason_counts: Counter[str] = Counter()
    probe_mode_counts: Counter[str] = Counter()
    master_status_counts: Counter[str] = Counter()
    master_search_profile_counts: Counter[str] = Counter()
    master_branch_count_sum = 0
    master_branch_count_max = 0
    master_conflict_count_sum = 0
    master_conflict_count_max = 0
    master_deterministic_time_sum = 0.0
    master_binary_propagations_sum = 0
    master_integer_propagations_sum = 0
    master_zero_branch_unknown_count = 0
    master_conflictful_unknown_count = 0
    ghost_anchor_hint_applied_count = 0
    ghost_anchor_hint_none_compatible_count = 0
    ghost_aware_start_applied_count = 0
    ghost_aware_start_fallback_count = 0
    ghost_aware_anchor_attempt_count_sum = 0
    ghost_aware_pose_order_portfolio_attempted_count = 0
    ghost_aware_pose_order_portfolio_success_count = 0
    ghost_aware_pose_order_portfolio_attempt_count_sum = 0
    ghost_aware_pose_order_portfolio_failed_anchor_count_sum = 0
    ghost_aware_pose_order_portfolio_failure_reason_counter: Counter[str] = Counter()
    ghost_aware_pose_order_portfolio_failure_samples: list[Dict[str, Any]] = []
    ghost_aware_pose_order_portfolio_selected_ordering_counter: Counter[str] = Counter()
    ghost_aware_pose_order_validation_attempt_count_sum = 0
    ghost_aware_pose_order_validation_rejected_count_sum = 0
    ghost_aware_pose_order_validation_status_counter: Counter[str] = Counter()
    ghost_aware_pose_order_validation_reason_counter: Counter[str] = Counter()
    master_hinted_literals_sum = 0
    greedy_hint_instances_sum = 0
    residual_optional_zero_hints_sum = 0
    ghost_anchor_compatible_count_sum = 0
    ghost_anchor_compatible_zero_count = 0
    required_optional_positive_hints_sum = 0
    residual_optional_positive_hints_sum = 0
    required_optional_active_slot_upper_bound_sum = 0
    residual_optional_active_slot_upper_bound_sum = 0
    master_start_incompatible_unknown_count = 0
    master_start_compatible_zero_branch_unknown_count = 0
    ghost_aware_failed_anchor_count_sum = 0
    ghost_aware_blocked_cells_exhausted_count_sum = 0
    ghost_aware_committed_cells_exhausted_count_sum = 0
    ghost_aware_intra_group_greedy_exhausted_count_sum = 0
    ghost_aware_top_failed_groups_counter: Counter[tuple[str, str]] = Counter()
    ghost_aware_top_failed_group_failures_counter: Counter[tuple[str, str, str]] = (
        Counter()
    )
    ghost_aware_local_repair_attempted_count = 0
    ghost_aware_local_repair_success_count = 0
    ghost_aware_local_repair_intra_group_attempted_count = 0
    ghost_aware_local_repair_committed_attempted_count = 0
    ghost_aware_local_repair_window1_count = 0
    ghost_aware_local_repair_window2_count = 0
    ghost_aware_local_repair_portfolio_attempt_count_sum = 0
    boundary_port_screen_supported_candidate_count = 0
    boundary_port_screened_infeasible_anchor_count_sum = 0
    boundary_port_screen_pass_anchor_count_sum = 0
    boundary_port_screen_unsupported_anchor_count_sum = 0
    boundary_port_max_packable_min_global: Optional[int] = None
    boundary_port_max_packable_max_global: Optional[int] = None
    candidate_precheck_triggered_count = 0
    candidate_precheck_boundary_port_all_anchors_infeasible_count = 0
    candidate_precheck_empty_pool_count = 0
    candidate_precheck_master_solve_skipped_count = 0
    candidate_precheck_empty_pool_group_counter: Counter[tuple[str, str]] = Counter()
    solve_attempt_count = 0
    precheck_elimination_count = 0
    precheck_elimination_reason_counts: Counter[str] = Counter()
    precheck_head_elimination_count = 0
    precheck_lookahead_elimination_count = 0
    precheck_lookahead_elimination_reason_counts: Counter[str] = Counter()
    mandatory_support_unsupported_group_count_sum = 0
    mandatory_support_empty_candidate_pool_group_count_sum = 0
    mandatory_support_unsupported_reason_counts: Counter[str] = Counter()
    mandatory_group_precheck_evaluated_candidate_count = 0
    mandatory_group_precheck_skipped_due_to_boundary_precheck_count = 0
    mandatory_group_precheck_considered_anchor_count_sum = 0
    mandatory_group_precheck_triggered_count = 0
    mandatory_group_precheck_master_solve_skipped_count = 0
    mandatory_group_precheck_supported_group_count_sum = 0
    mandatory_group_precheck_supported_group_count_by_oracle_mode: Counter[str] = Counter()
    mandatory_group_precheck_unsupported_group_count_sum = 0
    mandatory_group_precheck_unsupported_reason_counts: Counter[str] = Counter()
    mandatory_group_precheck_screened_infeasible_anchor_count_sum = 0
    mandatory_group_precheck_screen_pass_anchor_count_sum = 0
    mandatory_group_precheck_triggered_group_counter: Counter[tuple[str, str]] = Counter()
    ghost_disabled_placements_sum = 0
    ghost_disabled_placements_max = 0
    ghost_conditioned_family_upper_bound_constraints_sum = 0
    ghost_conditioned_signature_bucket_constraints_sum = 0
    ghost_signature_reduction_anchor_count_max = 0
    ghost_conditioned_residual_signature_bucket_constraints_sum = 0
    coordinate_symmetry_constraints_sum = 0
    residual_coordinate_symmetry_constraints_sum = 0
    loaded_cut_count_sum = 0
    generated_cut_count_sum = 0
    peak_rss_external_total = 0
    peak_rss_internal_max_single_process = 0
    probe_round_count = 0
    probe_candidate_count = 0
    probe_prune_gain_sum = 0
    probe_prune_gain_max = 0
    probe_resume_pending_count = 0

    for wave in waves:
        for key, count in dict(wave.get("status_counts", {})).items():
            status_counts[str(key)] += int(count)
        for key, count in dict(wave.get("outcome_counts", {})).items():
            outcome_counts[str(key)] += int(count)
        failure_reason = wave.get("failure_reason")
        if failure_reason:
            failure_reason_counts[str(failure_reason)] += 1
        if bool(wave.get("probe_round_active", False)):
            probe_round_count += 1
        probe_prune_gain_sum += int(wave.get("probe_prune_gain_sum", 0))
        probe_prune_gain_max = max(
            probe_prune_gain_max,
            int(wave.get("probe_prune_gain_max", 0)),
        )
        probe_resume_pending_count += int(wave.get("probe_resume_pending_count", 0))
        for result in list(wave.get("candidate_results", [])):
            if not isinstance(result, Mapping):
                continue
            selection_reason = str(result.get("selection_reason", ""))
            if selection_reason:
                selection_reason_counts[selection_reason] += 1
            if bool(result.get("probe_candidate", False)):
                probe_candidate_count += 1
            probe_mode = str(result.get("frontier_probe_mode", ""))
            if probe_mode:
                probe_mode_counts[probe_mode] += 1
            proof_status_summary = result.get("proof_status_summary")
            if isinstance(proof_status_summary, Mapping):
                master_status = str(proof_status_summary.get("master_status", ""))
                branches_for_result: Optional[int] = None
                if master_status:
                    master_status_counts[master_status] += 1
                master_last_solve = proof_status_summary.get("master_last_solve")
                if isinstance(master_last_solve, Mapping):
                    master_search_profile = str(master_last_solve.get("search_profile", ""))
                    if master_search_profile:
                        master_search_profile_counts[master_search_profile] += 1
                    branches = int(master_last_solve.get("branches", 0))
                    conflicts = int(master_last_solve.get("conflicts", 0))
                    binary_propagations = int(
                        master_last_solve.get("binary_propagations", 0)
                    )
                    integer_propagations = int(
                        master_last_solve.get("integer_propagations", 0)
                    )
                    deterministic_time = float(
                        master_last_solve.get("deterministic_time", 0.0)
                    )
                    branches_for_result = int(branches)
                    master_branch_count_sum += branches
                    master_branch_count_max = max(master_branch_count_max, branches)
                    master_conflict_count_sum += conflicts
                    master_conflict_count_max = max(master_conflict_count_max, conflicts)
                    master_deterministic_time_sum += deterministic_time
                    master_binary_propagations_sum += binary_propagations
                    master_integer_propagations_sum += integer_propagations
                    if master_status == "UNKNOWN" and branches == 0:
                        master_zero_branch_unknown_count += 1
                    if master_status == "UNKNOWN" and conflicts > 0:
                        master_conflictful_unknown_count += 1
                master_warm_start = proof_status_summary.get("master_warm_start")
                if isinstance(master_warm_start, Mapping):
                    warm_start_strategy = str(
                        master_warm_start.get("warm_start_strategy", "")
                    )
                    if bool(master_warm_start.get("ghost_anchor_hint_applied", False)):
                        ghost_anchor_hint_applied_count += 1
                        if warm_start_strategy in {
                            "ghost_aware_mandatory_rebuild",
                            "ghost_aware_pose_order_portfolio",
                        }:
                            ghost_aware_start_applied_count += 1
                    if (
                        str(master_warm_start.get("ghost_anchor_hint_status", ""))
                        == "none_compatible"
                    ):
                        ghost_anchor_hint_none_compatible_count += 1
                    if warm_start_strategy == "global_greedy_fallback":
                        ghost_aware_start_fallback_count += 1
                    ghost_aware_anchor_attempt_count_sum += int(
                        master_warm_start.get("ghost_aware_anchor_attempt_count", 0)
                    )
                    if bool(
                        master_warm_start.get(
                            "ghost_aware_pose_order_portfolio_attempted",
                            False,
                        )
                    ):
                        ghost_aware_pose_order_portfolio_attempted_count += 1
                    if bool(
                        master_warm_start.get(
                            "ghost_aware_pose_order_portfolio_success",
                            False,
                        )
                    ):
                        ghost_aware_pose_order_portfolio_success_count += 1
                    selected_ordering = master_warm_start.get(
                        "ghost_aware_pose_order_portfolio_selected_ordering"
                    )
                    if selected_ordering:
                        ghost_aware_pose_order_portfolio_selected_ordering_counter[
                            str(selected_ordering)
                        ] += 1
                    ghost_aware_pose_order_portfolio_attempt_count_sum += int(
                        master_warm_start.get(
                            "ghost_aware_pose_order_portfolio_attempt_count",
                            0,
                        )
                    )
                    ghost_aware_pose_order_portfolio_failed_anchor_count_sum += int(
                        master_warm_start.get(
                            "ghost_aware_pose_order_portfolio_failed_anchor_count",
                            0,
                        )
                    )
                    for key, count in dict(
                        master_warm_start.get(
                            "ghost_aware_pose_order_portfolio_failure_reason_counts",
                            {},
                        )
                    ).items():
                        ghost_aware_pose_order_portfolio_failure_reason_counter[
                            str(key)
                        ] += int(count)
                    for sample in list(
                        master_warm_start.get(
                            "ghost_aware_pose_order_portfolio_failure_samples",
                            [],
                        )
                    ):
                        if len(ghost_aware_pose_order_portfolio_failure_samples) >= _AGGREGATE_SAMPLE_LIMIT:
                            break
                        if not isinstance(sample, Mapping):
                            continue
                        compact_sample = dict(sample)
                        compact_sample.setdefault("candidate_key", result.get("candidate_key"))
                        ghost_aware_pose_order_portfolio_failure_samples.append(
                            compact_sample
                        )
                    ghost_aware_pose_order_validation_attempt_count_sum += int(
                        master_warm_start.get(
                            "ghost_aware_pose_order_validation_attempt_count",
                            0,
                        )
                    )
                    ghost_aware_pose_order_validation_rejected_count_sum += int(
                        master_warm_start.get(
                            "ghost_aware_pose_order_validation_rejected_count",
                            0,
                        )
                    )
                    validation_status = master_warm_start.get(
                        "ghost_aware_pose_order_validation_last_status"
                    )
                    if validation_status:
                        ghost_aware_pose_order_validation_status_counter[
                            str(validation_status)
                        ] += 1
                    validation_reason = master_warm_start.get(
                        "ghost_aware_pose_order_validation_last_reason"
                    )
                    if validation_reason:
                        ghost_aware_pose_order_validation_reason_counter[
                            str(validation_reason)
                        ] += 1
                    master_hinted_literals_sum += int(
                        master_warm_start.get("master_hinted_literals", 0)
                    )
                    greedy_hint_instances_sum += int(
                        master_warm_start.get("greedy_hint_instances", 0)
                    )
                    residual_optional_zero_hints_sum += int(
                        master_warm_start.get("residual_optional_zero_hints", 0)
                    )
                master_start_feasibility = proof_status_summary.get(
                    "master_start_feasibility"
                )
                if isinstance(master_start_feasibility, Mapping):
                    compatible_anchor_count = int(
                        master_start_feasibility.get(
                            "ghost_anchor_compatible_count",
                            0,
                        )
                    )
                    ghost_anchor_compatible_count_sum += compatible_anchor_count
                    if compatible_anchor_count == 0:
                        ghost_anchor_compatible_zero_count += 1
                    required_optional_positive_hints_sum += int(
                        master_start_feasibility.get(
                            "required_optional_positive_hints",
                            0,
                        )
                    )
                    residual_optional_positive_hints_sum += int(
                        master_start_feasibility.get(
                            "residual_optional_positive_hints",
                            0,
                        )
                    )
                    if master_status == "UNKNOWN" and compatible_anchor_count == 0:
                        master_start_incompatible_unknown_count += 1
                    if (
                        master_status == "UNKNOWN"
                        and branches_for_result == 0
                        and compatible_anchor_count > 0
                    ):
                        master_start_compatible_zero_branch_unknown_count += 1
                master_start_failure_attribution = proof_status_summary.get(
                    "master_start_failure_attribution"
                )
                if isinstance(master_start_failure_attribution, Mapping):
                    ghost_aware_failed_anchor_count_sum += int(
                        master_start_failure_attribution.get(
                            "failed_anchor_count",
                            0,
                        )
                    )
                    failure_reason_counts_for_result = dict(
                        master_start_failure_attribution.get(
                            "failure_reason_counts",
                            {},
                        )
                    )
                    ghost_aware_blocked_cells_exhausted_count_sum += int(
                        failure_reason_counts_for_result.get(
                            "blocked_cells_exhausted",
                            0,
                        )
                    )
                    ghost_aware_committed_cells_exhausted_count_sum += int(
                        failure_reason_counts_for_result.get(
                            "committed_cells_exhausted",
                            0,
                        )
                    )
                    ghost_aware_intra_group_greedy_exhausted_count_sum += int(
                        failure_reason_counts_for_result.get(
                            "intra_group_greedy_exhausted",
                            0,
                        )
                    )
                    for entry in list(
                        master_start_failure_attribution.get("top_failed_groups", [])
                    )[:5]:
                        count = int(entry.get("count", 0))
                        if count <= 0:
                            continue
                        ghost_aware_top_failed_groups_counter[
                            (
                                str(entry.get("group_id", "")),
                                str(entry.get("facility_type", "")),
                            )
                        ] += count
                    for entry in list(
                        master_start_failure_attribution.get(
                            "top_failed_group_failures",
                            [],
                        )
                    )[:8]:
                        count = int(entry.get("count", 0))
                        if count <= 0:
                            continue
                        ghost_aware_top_failed_group_failures_counter[
                            (
                                str(entry.get("group_id", "")),
                                str(entry.get("facility_type", "")),
                                str(entry.get("failure_reason", "")),
                            )
                        ] += count
                master_start_local_repair = proof_status_summary.get(
                    "master_start_local_repair"
                )
                if isinstance(master_start_local_repair, Mapping):
                    if bool(master_start_local_repair.get("local_repair_attempted", False)):
                        ghost_aware_local_repair_attempted_count += int(
                            master_start_local_repair.get(
                                "local_repair_attempt_count",
                                1,
                            )
                        )
                    if bool(master_start_local_repair.get("local_repair_success", False)):
                        ghost_aware_local_repair_success_count += int(
                            master_start_local_repair.get(
                                "local_repair_success_count",
                                1,
                            )
                        )
                    ghost_aware_local_repair_intra_group_attempted_count += int(
                        master_start_local_repair.get(
                            "local_repair_intra_group_attempted_count",
                            0,
                        )
                    )
                    ghost_aware_local_repair_committed_attempted_count += int(
                        master_start_local_repair.get(
                            "local_repair_committed_attempted_count",
                            0,
                        )
                    )
                    ghost_aware_local_repair_window1_count += int(
                        master_start_local_repair.get(
                            "local_repair_window1_count",
                            0,
                        )
                    )
                    ghost_aware_local_repair_window2_count += int(
                        master_start_local_repair.get(
                            "local_repair_window2_count",
                            0,
                        )
                    )
                    ghost_aware_local_repair_portfolio_attempt_count_sum += int(
                        master_start_local_repair.get(
                            "local_repair_portfolio_attempt_count",
                            0,
                        )
                    )
                master_boundary_port_feasibility = proof_status_summary.get(
                    "master_boundary_port_feasibility"
                )
                if isinstance(master_boundary_port_feasibility, Mapping):
                    if bool(master_boundary_port_feasibility.get("supported", False)):
                        boundary_port_screen_supported_candidate_count += 1
                        max_packable_min = master_boundary_port_feasibility.get(
                            "max_packable_min"
                        )
                        max_packable_max = master_boundary_port_feasibility.get(
                            "max_packable_max"
                        )
                        if max_packable_min is not None:
                            min_value = int(max_packable_min)
                            boundary_port_max_packable_min_global = (
                                min_value
                                if boundary_port_max_packable_min_global is None
                                else min(
                                    int(boundary_port_max_packable_min_global),
                                    min_value,
                                )
                            )
                        if max_packable_max is not None:
                            max_value = int(max_packable_max)
                            boundary_port_max_packable_max_global = (
                                max_value
                                if boundary_port_max_packable_max_global is None
                                else max(
                                    int(boundary_port_max_packable_max_global),
                                    max_value,
                                )
                            )
                    boundary_port_screened_infeasible_anchor_count_sum += int(
                        master_boundary_port_feasibility.get(
                            "screened_infeasible_anchor_count",
                            0,
                        )
                    )
                    boundary_port_screen_pass_anchor_count_sum += int(
                        master_boundary_port_feasibility.get(
                            "screen_pass_anchor_count",
                            0,
                        )
                    )
                    boundary_port_screen_unsupported_anchor_count_sum += int(
                        master_boundary_port_feasibility.get(
                            "unsupported_anchor_count",
                            0,
                        )
                    )
                master_candidate_precheck = proof_status_summary.get(
                    "master_candidate_precheck"
                )
                precheck_lookahead = proof_status_summary.get("precheck_lookahead")
                master_mandatory_support_diagnostics = proof_status_summary.get(
                    "master_mandatory_support_diagnostics"
                )
                master_mandatory_group_prechecks = proof_status_summary.get(
                    "master_mandatory_group_prechecks"
                )
                if isinstance(master_mandatory_support_diagnostics, Mapping):
                    mandatory_support_unsupported_group_count_sum += int(
                        master_mandatory_support_diagnostics.get(
                            "unsupported_group_count",
                            0,
                        )
                    )
                    mandatory_support_empty_candidate_pool_group_count_sum += int(
                        master_mandatory_support_diagnostics.get(
                            "empty_candidate_pool_group_count",
                            0,
                        )
                    )
                    for entry in list(
                        master_mandatory_support_diagnostics.get("groups", [])
                    ):
                        if not isinstance(entry, Mapping):
                            continue
                        unsupported_reason = entry.get("unsupported_reason")
                        if unsupported_reason:
                            mandatory_support_unsupported_reason_counts[
                                str(unsupported_reason)
                            ] += 1
                if isinstance(master_mandatory_group_prechecks, Mapping):
                    if bool(master_mandatory_group_prechecks.get("evaluated", False)):
                        mandatory_group_precheck_evaluated_candidate_count += 1
                    if bool(
                        master_mandatory_group_prechecks.get(
                            "skipped_due_to_upstream_precheck",
                            False,
                        )
                    ):
                        mandatory_group_precheck_skipped_due_to_boundary_precheck_count += 1
                    mandatory_group_precheck_supported_group_count_sum += int(
                        master_mandatory_group_prechecks.get(
                            "supported_group_count",
                            0,
                        )
                    )
                    for entry in list(
                        master_mandatory_group_prechecks.get("groups", [])
                    ):
                        if not isinstance(entry, Mapping):
                            continue
                        mandatory_group_precheck_considered_anchor_count_sum += int(
                            entry.get("considered_anchor_count", 0)
                        )
                        mandatory_group_precheck_screened_infeasible_anchor_count_sum += int(
                            entry.get("screened_infeasible_anchor_count", 0)
                        )
                        mandatory_group_precheck_screen_pass_anchor_count_sum += int(
                            entry.get("screen_pass_anchor_count", 0)
                        )
                        if bool(entry.get("supported", False)):
                            oracle_mode = str(entry.get("oracle_mode", "unsupported"))
                            if oracle_mode:
                                mandatory_group_precheck_supported_group_count_by_oracle_mode[
                                    oracle_mode
                                ] += 1
                        else:
                            mandatory_group_precheck_unsupported_group_count_sum += 1
                            unsupported_reason = str(
                                entry.get("unsupported_reason", "")
                            )
                            if unsupported_reason:
                                mandatory_group_precheck_unsupported_reason_counts[
                                    unsupported_reason
                                ] += 1
                if isinstance(master_candidate_precheck, Mapping):
                    precheck_triggered = bool(master_candidate_precheck.get("triggered", False))
                    precheck_reason = str(master_candidate_precheck.get("precheck_reason", ""))
                    master_solve_skipped = bool(
                        master_candidate_precheck.get("master_solve_skipped", False)
                    )
                    if precheck_triggered and master_solve_skipped:
                        precheck_elimination_count += 1
                        if precheck_reason:
                            precheck_elimination_reason_counts[precheck_reason] += 1
                        is_lookahead_elimination = (
                            isinstance(precheck_lookahead, Mapping)
                            and bool(precheck_lookahead.get("enabled", False))
                            and not bool(
                                precheck_lookahead.get("is_selected_head", False)
                            )
                        )
                        is_selected_head_elimination = (
                            not isinstance(precheck_lookahead, Mapping)
                            or bool(precheck_lookahead.get("is_selected_head", False))
                        )
                        if is_lookahead_elimination:
                            precheck_lookahead_elimination_count += 1
                            if precheck_reason:
                                precheck_lookahead_elimination_reason_counts[
                                    precheck_reason
                                ] += 1
                        elif is_selected_head_elimination:
                            precheck_head_elimination_count += 1
                    else:
                        solve_attempt_count += 1
                    if precheck_triggered:
                        candidate_precheck_triggered_count += 1
                    if (
                        precheck_reason
                        == "boundary_port_all_anchors_infeasible"
                    ):
                        candidate_precheck_boundary_port_all_anchors_infeasible_count += 1
                    if (
                        precheck_reason
                        == "mandatory_group_empty_candidate_pool"
                    ):
                        candidate_precheck_empty_pool_count += 1
                        group_id = str(
                            master_candidate_precheck.get("triggered_group_id", "")
                        )
                        facility_type = str(
                            master_candidate_precheck.get(
                                "triggered_group_facility_type",
                                "",
                            )
                        )
                        if group_id:
                            candidate_precheck_empty_pool_group_counter[
                                (group_id, facility_type)
                            ] += 1
                    if master_solve_skipped:
                        candidate_precheck_master_solve_skipped_count += 1
                    if (
                        precheck_reason
                        == "mandatory_rect_group_all_anchors_infeasible"
                    ):
                        mandatory_group_precheck_triggered_count += 1
                        if bool(
                            master_solve_skipped
                        ):
                            mandatory_group_precheck_master_solve_skipped_count += 1
                        group_id = str(
                            master_candidate_precheck.get("triggered_group_id", "")
                        )
                        facility_type = str(
                            master_candidate_precheck.get(
                                "triggered_group_facility_type",
                                "",
                            )
                        )
                        if group_id:
                            mandatory_group_precheck_triggered_group_counter[
                                (group_id, facility_type)
                            ] += 1
                else:
                    solve_attempt_count += 1
                master_domain_tightening = proof_status_summary.get("master_domain_tightening")
                if isinstance(master_domain_tightening, Mapping):
                    ghost_disabled_placements = int(
                        master_domain_tightening.get("ghost_disabled_placements", 0)
                    )
                    ghost_disabled_placements_sum += ghost_disabled_placements
                    ghost_disabled_placements_max = max(
                        ghost_disabled_placements_max,
                        ghost_disabled_placements,
                    )
                    ghost_conditioned_family_upper_bound_constraints_sum += int(
                        master_domain_tightening.get(
                            "ghost_conditioned_family_upper_bound_constraints",
                            0,
                        )
                    )
                master_signature_tightening = proof_status_summary.get(
                    "master_signature_tightening"
                )
                if isinstance(master_signature_tightening, Mapping):
                    ghost_conditioned_signature_bucket_constraints_sum += int(
                        master_signature_tightening.get(
                            "ghost_conditioned_mandatory_bucket_constraints",
                            0,
                        )
                    )
                    ghost_conditioned_signature_bucket_constraints_sum += int(
                        master_signature_tightening.get(
                            "ghost_conditioned_required_optional_bucket_constraints",
                            0,
                        )
                    )
                    ghost_signature_reduction_anchor_count_max = max(
                        ghost_signature_reduction_anchor_count_max,
                        int(
                            master_signature_tightening.get(
                                "ghost_signature_reduction_anchor_count",
                                0,
                            )
                        ),
                    )
                master_residual_signature_tightening = proof_status_summary.get(
                    "master_residual_signature_tightening"
                )
                if isinstance(master_residual_signature_tightening, Mapping):
                    ghost_conditioned_residual_signature_bucket_constraints_sum += int(
                        master_residual_signature_tightening.get(
                            "ghost_conditioned_bucket_constraints",
                            0,
                        )
                    )
                master_coordinate_symmetry = proof_status_summary.get(
                    "master_coordinate_symmetry"
                )
                if isinstance(master_coordinate_symmetry, Mapping):
                    coordinate_symmetry_constraints_sum += int(
                        master_coordinate_symmetry.get(
                            "mandatory_signature_monotonic_constraints",
                            0,
                        )
                    )
                    coordinate_symmetry_constraints_sum += int(
                        master_coordinate_symmetry.get(
                            "required_optional_signature_monotonic_constraints",
                            0,
                        )
                    )
                    residual_coordinate_symmetry_constraints_sum += int(
                        master_coordinate_symmetry.get(
                            "residual_optional_signature_monotonic_constraints",
                            0,
                        )
                    )
                    coordinate_symmetry_constraints_sum += int(
                        master_coordinate_symmetry.get(
                            "residual_optional_signature_monotonic_constraints",
                            0,
                        )
                    )
                master_domain_activation = proof_status_summary.get(
                    "master_domain_activation"
                )
                if isinstance(master_domain_activation, Mapping):
                    required_optional_active_slot_upper_bound_sum += int(
                        master_domain_activation.get(
                            "required_optional_active_slot_upper_bound_sum",
                            0,
                        )
                    )
                    residual_optional_active_slot_upper_bound_sum += int(
                        master_domain_activation.get(
                            "residual_optional_active_slot_upper_bound_sum",
                            0,
                        )
                    )
        loaded_cut_count_sum += int(wave.get("loaded_exact_safe_cut_count_sum", 0))
        generated_cut_count_sum += int(wave.get("generated_exact_safe_cut_count_sum", 0))
        peak_rss_external_total = max(
            peak_rss_external_total,
            int(wave.get("peak_rss_bytes_external_total") or 0),
        )
        peak_rss_internal_max_single_process = max(
            peak_rss_internal_max_single_process,
            int(wave.get("peak_rss_bytes_internal_max_single_process") or 0),
        )

    return {
        "wave_count": int(len(waves)),
        "candidate_result_count": int(sum(int(wave.get("candidate_count", 0)) for wave in waves)),
        "solve_attempt_count": int(solve_attempt_count),
        "precheck_elimination_count": int(precheck_elimination_count),
        "precheck_elimination_reason_counts": _ordered_counter_dict(
            precheck_elimination_reason_counts,
            sorted(str(key) for key in precheck_elimination_reason_counts.keys()),
        ),
        "precheck_head_elimination_count": int(precheck_head_elimination_count),
        "precheck_lookahead_elimination_count": int(
            precheck_lookahead_elimination_count
        ),
        "precheck_lookahead_elimination_reason_counts": _ordered_counter_dict(
            precheck_lookahead_elimination_reason_counts,
            sorted(
                str(key)
                for key in precheck_lookahead_elimination_reason_counts.keys()
            ),
        ),
        "status_counts": _ordered_counter_dict(status_counts, _STATUS_ORDER),
        "outcome_counts": _ordered_counter_dict(outcome_counts, _OUTCOME_ORDER),
        "selection_reason_counts": _ordered_counter_dict(
            selection_reason_counts,
            _SELECTION_REASON_ORDER,
        ),
        "probe_mode_counts": _ordered_counter_dict(
            probe_mode_counts,
            sorted(str(key) for key in probe_mode_counts.keys()),
        ),
        "probe_round_count": int(probe_round_count),
        "probe_candidate_count": int(probe_candidate_count),
        "probe_prune_gain_sum": int(probe_prune_gain_sum),
        "probe_prune_gain_max": int(probe_prune_gain_max),
        "probe_resume_pending_count": int(probe_resume_pending_count),
        "master_status_counts": _ordered_counter_dict(
            master_status_counts,
            sorted(str(key) for key in master_status_counts.keys()),
        ),
        "master_search_profile_counts": _ordered_counter_dict(
            master_search_profile_counts,
            sorted(str(key) for key in master_search_profile_counts.keys()),
        ),
        "master_branch_count_sum": int(master_branch_count_sum),
        "master_branch_count_max": int(master_branch_count_max),
        "master_conflict_count_sum": int(master_conflict_count_sum),
        "master_conflict_count_max": int(master_conflict_count_max),
        "master_deterministic_time_sum": float(master_deterministic_time_sum),
        "master_binary_propagations_sum": int(master_binary_propagations_sum),
        "master_integer_propagations_sum": int(master_integer_propagations_sum),
        "master_zero_branch_unknown_count": int(master_zero_branch_unknown_count),
        "master_conflictful_unknown_count": int(master_conflictful_unknown_count),
        "ghost_anchor_hint_applied_count": int(ghost_anchor_hint_applied_count),
        "ghost_anchor_hint_none_compatible_count": int(
            ghost_anchor_hint_none_compatible_count
        ),
        "ghost_aware_start_applied_count": int(ghost_aware_start_applied_count),
        "ghost_aware_start_fallback_count": int(ghost_aware_start_fallback_count),
        "ghost_aware_anchor_attempt_count_sum": int(
            ghost_aware_anchor_attempt_count_sum
        ),
        "ghost_aware_pose_order_portfolio_attempted_count": int(
            ghost_aware_pose_order_portfolio_attempted_count
        ),
        "ghost_aware_pose_order_portfolio_success_count": int(
            ghost_aware_pose_order_portfolio_success_count
        ),
        "ghost_aware_pose_order_portfolio_attempt_count_sum": int(
            ghost_aware_pose_order_portfolio_attempt_count_sum
        ),
        "ghost_aware_pose_order_portfolio_failed_anchor_count_sum": int(
            ghost_aware_pose_order_portfolio_failed_anchor_count_sum
        ),
        "ghost_aware_pose_order_portfolio_failure_reason_counts": _ordered_counter_dict(
            ghost_aware_pose_order_portfolio_failure_reason_counter,
            sorted(
                str(key)
                for key in ghost_aware_pose_order_portfolio_failure_reason_counter.keys()
            ),
        ),
        "ghost_aware_pose_order_portfolio_failure_sample_count": int(
            len(ghost_aware_pose_order_portfolio_failure_samples)
        ),
        "ghost_aware_pose_order_portfolio_failure_samples": [
            dict(entry) for entry in ghost_aware_pose_order_portfolio_failure_samples
        ],
        "ghost_aware_pose_order_portfolio_selected_ordering_counts": _ordered_counter_dict(
            ghost_aware_pose_order_portfolio_selected_ordering_counter,
            sorted(
                str(key)
                for key in ghost_aware_pose_order_portfolio_selected_ordering_counter.keys()
            ),
        ),
        "ghost_aware_pose_order_validation_attempt_count_sum": int(
            ghost_aware_pose_order_validation_attempt_count_sum
        ),
        "ghost_aware_pose_order_validation_rejected_count_sum": int(
            ghost_aware_pose_order_validation_rejected_count_sum
        ),
        "ghost_aware_pose_order_validation_status_counts": _ordered_counter_dict(
            ghost_aware_pose_order_validation_status_counter,
            sorted(
                str(key)
                for key in ghost_aware_pose_order_validation_status_counter.keys()
            ),
        ),
        "ghost_aware_pose_order_validation_reason_counts": _ordered_counter_dict(
            ghost_aware_pose_order_validation_reason_counter,
            sorted(
                str(key)
                for key in ghost_aware_pose_order_validation_reason_counter.keys()
            ),
        ),
        "master_hinted_literals_sum": int(master_hinted_literals_sum),
        "greedy_hint_instances_sum": int(greedy_hint_instances_sum),
        "residual_optional_zero_hints_sum": int(
            residual_optional_zero_hints_sum
        ),
        "ghost_anchor_compatible_count_sum": int(ghost_anchor_compatible_count_sum),
        "ghost_anchor_compatible_zero_count": int(
            ghost_anchor_compatible_zero_count
        ),
        "required_optional_positive_hints_sum": int(
            required_optional_positive_hints_sum
        ),
        "residual_optional_positive_hints_sum": int(
            residual_optional_positive_hints_sum
        ),
        "required_optional_active_slot_upper_bound_sum": int(
            required_optional_active_slot_upper_bound_sum
        ),
        "residual_optional_active_slot_upper_bound_sum": int(
            residual_optional_active_slot_upper_bound_sum
        ),
        "master_start_incompatible_unknown_count": int(
            master_start_incompatible_unknown_count
        ),
        "master_start_compatible_zero_branch_unknown_count": int(
            master_start_compatible_zero_branch_unknown_count
        ),
        "ghost_aware_failed_anchor_count_sum": int(
            ghost_aware_failed_anchor_count_sum
        ),
        "ghost_aware_blocked_cells_exhausted_count_sum": int(
            ghost_aware_blocked_cells_exhausted_count_sum
        ),
        "ghost_aware_committed_cells_exhausted_count_sum": int(
            ghost_aware_committed_cells_exhausted_count_sum
        ),
        "ghost_aware_intra_group_greedy_exhausted_count_sum": int(
            ghost_aware_intra_group_greedy_exhausted_count_sum
        ),
        "ghost_aware_top_failed_groups": [
            {
                "group_id": str(group_id),
                "facility_type": str(facility_type),
                "count": int(count),
            }
            for (group_id, facility_type), count in ghost_aware_top_failed_groups_counter.most_common(5)
        ],
        "ghost_aware_top_failed_group_failures": [
            {
                "group_id": str(group_id),
                "facility_type": str(facility_type),
                "failure_reason": str(failure_reason),
                "count": int(count),
            }
            for (
                group_id,
                facility_type,
                failure_reason,
            ), count in ghost_aware_top_failed_group_failures_counter.most_common(8)
        ],
        "ghost_aware_local_repair_attempted_count": int(
            ghost_aware_local_repair_attempted_count
        ),
        "ghost_aware_local_repair_success_count": int(
            ghost_aware_local_repair_success_count
        ),
        "ghost_aware_local_repair_intra_group_attempted_count": int(
            ghost_aware_local_repair_intra_group_attempted_count
        ),
        "ghost_aware_local_repair_committed_attempted_count": int(
            ghost_aware_local_repair_committed_attempted_count
        ),
        "ghost_aware_local_repair_window1_count": int(
            ghost_aware_local_repair_window1_count
        ),
        "ghost_aware_local_repair_window2_count": int(
            ghost_aware_local_repair_window2_count
        ),
        "ghost_aware_local_repair_portfolio_attempt_count_sum": int(
            ghost_aware_local_repair_portfolio_attempt_count_sum
        ),
        "boundary_port_screen_supported_candidate_count": int(
            boundary_port_screen_supported_candidate_count
        ),
        "boundary_port_screened_infeasible_anchor_count_sum": int(
            boundary_port_screened_infeasible_anchor_count_sum
        ),
        "boundary_port_screen_pass_anchor_count_sum": int(
            boundary_port_screen_pass_anchor_count_sum
        ),
        "boundary_port_screen_unsupported_anchor_count_sum": int(
            boundary_port_screen_unsupported_anchor_count_sum
        ),
        "boundary_port_max_packable_min_global": 0
        if boundary_port_max_packable_min_global is None
        else int(boundary_port_max_packable_min_global),
        "boundary_port_max_packable_max_global": 0
        if boundary_port_max_packable_max_global is None
        else int(boundary_port_max_packable_max_global),
        "candidate_precheck_triggered_count": int(
            candidate_precheck_triggered_count
        ),
        "candidate_precheck_boundary_port_all_anchors_infeasible_count": int(
            candidate_precheck_boundary_port_all_anchors_infeasible_count
        ),
        "candidate_precheck_empty_pool_count": int(
            candidate_precheck_empty_pool_count
        ),
        "candidate_precheck_empty_pool_group_counts": [
            {
                "group_id": str(group_id),
                "facility_type": str(facility_type),
                "count": int(count),
            }
            for (group_id, facility_type), count in candidate_precheck_empty_pool_group_counter.most_common(5)
        ],
        "candidate_precheck_master_solve_skipped_count": int(
            candidate_precheck_master_solve_skipped_count
        ),
        "mandatory_support_unsupported_group_count_sum": int(
            mandatory_support_unsupported_group_count_sum
        ),
        "mandatory_support_empty_candidate_pool_group_count_sum": int(
            mandatory_support_empty_candidate_pool_group_count_sum
        ),
        "mandatory_support_unsupported_reason_counts": _ordered_counter_dict(
            mandatory_support_unsupported_reason_counts,
            sorted(
                str(key)
                for key in mandatory_support_unsupported_reason_counts.keys()
            ),
        ),
        "mandatory_group_precheck_evaluated_candidate_count": int(
            mandatory_group_precheck_evaluated_candidate_count
        ),
        "mandatory_group_precheck_skipped_due_to_boundary_precheck_count": int(
            mandatory_group_precheck_skipped_due_to_boundary_precheck_count
        ),
        "mandatory_group_precheck_considered_anchor_count_sum": int(
            mandatory_group_precheck_considered_anchor_count_sum
        ),
        "mandatory_group_precheck_triggered_count": int(
            mandatory_group_precheck_triggered_count
        ),
        "mandatory_group_precheck_master_solve_skipped_count": int(
            mandatory_group_precheck_master_solve_skipped_count
        ),
        "mandatory_group_precheck_supported_group_count_sum": int(
            mandatory_group_precheck_supported_group_count_sum
        ),
        "mandatory_group_precheck_supported_group_count_by_oracle_mode": _ordered_counter_dict(
            mandatory_group_precheck_supported_group_count_by_oracle_mode,
            sorted(
                str(key)
                for key in mandatory_group_precheck_supported_group_count_by_oracle_mode.keys()
            ),
        ),
        "mandatory_group_precheck_unsupported_group_count_sum": int(
            mandatory_group_precheck_unsupported_group_count_sum
        ),
        "mandatory_group_precheck_unsupported_reason_counts": _ordered_counter_dict(
            mandatory_group_precheck_unsupported_reason_counts,
            sorted(
                str(key)
                for key in mandatory_group_precheck_unsupported_reason_counts.keys()
            ),
        ),
        "mandatory_group_precheck_screened_infeasible_anchor_count_sum": int(
            mandatory_group_precheck_screened_infeasible_anchor_count_sum
        ),
        "mandatory_group_precheck_screen_pass_anchor_count_sum": int(
            mandatory_group_precheck_screen_pass_anchor_count_sum
        ),
        "mandatory_group_precheck_triggered_group_counts": [
            {
                "group_id": str(group_id),
                "facility_type": str(facility_type),
                "count": int(count),
            }
            for (group_id, facility_type), count in mandatory_group_precheck_triggered_group_counter.most_common(5)
        ],
        "failure_reason_counts": _ordered_counter_dict(
            failure_reason_counts,
            sorted(str(key) for key in failure_reason_counts.keys()),
        ),
        "loaded_exact_safe_cut_count_sum": int(loaded_cut_count_sum),
        "generated_exact_safe_cut_count_sum": int(generated_cut_count_sum),
        "ghost_disabled_placements_sum": int(ghost_disabled_placements_sum),
        "ghost_disabled_placements_max": int(ghost_disabled_placements_max),
        "ghost_conditioned_family_upper_bound_constraints_sum": int(
            ghost_conditioned_family_upper_bound_constraints_sum
        ),
        "ghost_conditioned_signature_bucket_constraints_sum": int(
            ghost_conditioned_signature_bucket_constraints_sum
        ),
        "ghost_signature_reduction_anchor_count_max": int(
            ghost_signature_reduction_anchor_count_max
        ),
        "ghost_conditioned_residual_signature_bucket_constraints_sum": int(
            ghost_conditioned_residual_signature_bucket_constraints_sum
        ),
        "coordinate_symmetry_constraints_sum": int(
            coordinate_symmetry_constraints_sum
        ),
        "residual_coordinate_symmetry_constraints_sum": int(
            residual_coordinate_symmetry_constraints_sum
        ),
        "peak_rss_bytes_external_total": int(peak_rss_external_total),
        "peak_rss_bytes_internal_max_single_process": int(peak_rss_internal_max_single_process),
    }


def load_campaign_telemetry_payload(
    *,
    project_root: Path,
    campaign_path: Path,
) -> Optional[Dict[str, Any]]:
    telemetry_path = campaign_telemetry_output_path(campaign_path)
    if not telemetry_path.exists():
        return None
    payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("campaign telemetry payload must be a JSON object")
    return dict(payload)


def append_campaign_wave_summary(
    *,
    project_root: Path,
    campaign_path: Path,
    wave_summary: Mapping[str, Any],
    reset: bool = False,
) -> Dict[str, Any]:
    telemetry_path = campaign_telemetry_output_path(campaign_path)
    payload = None if reset else load_campaign_telemetry_payload(project_root=project_root, campaign_path=campaign_path)
    timestamp = now_iso()
    if payload is None:
        payload = {
            "schema_version": CAMPAIGN_TELEMETRY_SCHEMA_VERSION,
            "solve_mode": "certified_exact",
            "campaign_state_path": str(Path(campaign_path).relative_to(project_root)),
            "created_at": timestamp,
            "updated_at": timestamp,
            "waves": [],
            "aggregate": {},
        }

    waves = list(payload.get("waves", []))
    waves.append(dict(wave_summary))
    payload["waves"] = waves
    payload["aggregate"] = _aggregate_waves(waves)
    payload["updated_at"] = timestamp
    atomic_write_json(telemetry_path, payload)
    return payload
