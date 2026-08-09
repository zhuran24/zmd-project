from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from src.models.cut_manager import (
    RUN_STATUS_INFEASIBLE,
    RUN_STATUS_UNKNOWN,
    RUN_STATUS_UNPROVEN,
)
from src.search.campaign_telemetry import campaign_telemetry_output_path
from src.search.exact_campaign import now_iso

TRIAGE_SCHEMA_SOURCE = "phase3b_unknown_triage_inventory_v1"
DEFAULT_CAMPAIGN_STATE_PATH = Path("data/checkpoints/exact_campaign_state.json")

_CLASSIFICATION_ORDER = [
    "pre_master_eliminated",
    "master_unknown",
    "binding_timeout",
    "binding_empty_domain",
    "routing_timeout",
    "routing_precheck_reject",
    "routing_all_infeasible",
    "unproven",
    "orchestration_failure",
    "unknown_unclassified",
]

_SUBTYPE_ORDER = [
    "master_zero_branch_unknown",
    "master_conflictful_unknown",
    "master_start_ghost_overlap_forced_domain_unknown",
    "master_start_signature_monotonic_incompatible_unknown",
    "master_start_incompatible_unknown",
    "master_start_compatible_zero_branch_unknown",
    "ghost_aware_start_failure_unknown",
    "master_unknown_general",
]


def build_phase3b_unknown_triage_inventory(
    project_root: Path,
    campaign_state_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path if campaign_state_path is not None else DEFAULT_CAMPAIGN_STATE_PATH,
    )
    telemetry_path = campaign_telemetry_output_path(campaign_path)

    state, state_error = _load_json_mapping(campaign_path)
    telemetry, telemetry_error = _load_json_mapping(telemetry_path)
    telemetry_results = _collect_telemetry_candidate_results(telemetry)
    telemetry_by_candidate = _telemetry_results_by_candidate(telemetry_results)
    last_stop_reason = (
        dict(state.get("last_stop_reason", {}))
        if isinstance(state, Mapping) and isinstance(state.get("last_stop_reason"), Mapping)
        else {}
    )

    state_candidate_records = _candidate_records_from_state(state)
    candidate_records = dict(state_candidate_records)
    for candidate_key, telemetry_record in telemetry_by_candidate.items():
        candidate_records.setdefault(candidate_key, telemetry_record["record"])

    blockers: list[Dict[str, Any]] = []
    for candidate_key in sorted(
        candidate_records,
        key=lambda key: _candidate_sort_key(key, candidate_records[key]),
    ):
        record = candidate_records[candidate_key]
        telemetry_entries = list(telemetry_by_candidate.get(candidate_key, {}).get("entries", []))
        blocker = _candidate_blocker_entry(
            candidate_key=candidate_key,
            record=record,
            telemetry_entries=telemetry_entries,
            campaign_last_stop_reason=last_stop_reason,
            record_source="campaign_state"
            if candidate_key in state_candidate_records
            else "telemetry",
        )
        if blocker is not None:
            blockers.append(blocker)

    orchestration_blocker = _campaign_orchestration_blocker(
        last_stop_reason=last_stop_reason,
        telemetry=telemetry,
    )
    if orchestration_blocker is not None:
        blockers.append(orchestration_blocker)

    classification_counts = Counter(str(entry["classification"]) for entry in blockers)
    subtype_counts = Counter(
        str(entry["blocker_subtype"])
        for entry in blockers
        if entry.get("blocker_subtype")
    )
    status_counts = Counter(str(entry["status"]) for entry in blockers)

    return {
        "metadata": {
            "source": TRIAGE_SCHEMA_SOURCE,
            "generated_at": now_iso(),
            "project_root": str(project_root),
        },
        "paths": {
            "campaign_state": _display_path(project_root, campaign_path),
            "campaign_telemetry": _display_path(project_root, telemetry_path),
        },
        "summary": {
            "campaign_present": state is not None and state_error is None,
            "campaign_load_error": state_error,
            "telemetry_present": telemetry is not None and telemetry_error is None,
            "telemetry_load_error": telemetry_error,
            "telemetry_wave_count": _telemetry_wave_count(telemetry),
            "blocker_count": int(len(blockers)),
            "status_counts": _ordered_counter_dict(
                status_counts,
                [
                    RUN_STATUS_INFEASIBLE,
                    RUN_STATUS_UNKNOWN,
                    RUN_STATUS_UNPROVEN,
                    "RUNNING",
                    "__CAMPAIGN__",
                ],
            ),
            "classification_counts": _ordered_counter_dict(
                classification_counts,
                _CLASSIFICATION_ORDER,
            ),
            "subtype_counts": _ordered_counter_dict(subtype_counts, _SUBTYPE_ORDER),
            "campaign_final_status": state.get("final_status")
            if isinstance(state, Mapping)
            else None,
            "campaign_last_stop_reason": last_stop_reason or None,
        },
        "telemetry": {
            "present": telemetry is not None and telemetry_error is None,
            "wave_count": _telemetry_wave_count(telemetry),
            "aggregate": telemetry.get("aggregate")
            if isinstance(telemetry, Mapping) and isinstance(telemetry.get("aggregate"), Mapping)
            else None,
        },
        "blockers": blockers,
    }


def render_phase3b_unknown_triage_markdown(inventory: Mapping[str, Any]) -> str:
    summary = _mapping(inventory.get("summary"))
    paths = _mapping(inventory.get("paths"))
    blockers = [entry for entry in list(inventory.get("blockers", [])) if isinstance(entry, Mapping)]

    lines = [
        "# Phase 3B UNKNOWN Triage Blocker Inventory",
        "",
        f"- Campaign state: {paths.get('campaign_state')}",
        f"- Campaign present: {bool(summary.get('campaign_present', False))}",
        f"- Telemetry present: {bool(summary.get('telemetry_present', False))}",
        f"- Telemetry waves: {int(summary.get('telemetry_wave_count', 0))}",
        f"- Blockers: {int(summary.get('blocker_count', 0))}",
        f"- Classification counts: {summary.get('classification_counts', {})}",
        f"- Subtype counts: {summary.get('subtype_counts', {})}",
        "",
    ]
    if not blockers:
        lines.append("No UNKNOWN/UNPROVEN/pre-master/orchestration blockers were found.")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "| Candidate | Status | Classification | Subtype | Disposition | Objective | Stop stage | Stop reason | Start blocker | Repro |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for entry in blockers:
        objective = _mapping(entry.get("objective"))
        objective_text = (
            f"area={objective.get('area')}, min_side={objective.get('min_side')}"
            if objective
            else ""
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("candidate_key")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(entry.get("classification")),
                    _markdown_cell(entry.get("blocker_subtype")),
                    _markdown_cell(entry.get("disposition")),
                    _markdown_cell(objective_text),
                    _markdown_cell(entry.get("stop_stage")),
                    _markdown_cell(entry.get("stop_reason")),
                    _markdown_cell(_start_failure_summary_text(entry.get("start_failure_summary"))),
                    _markdown_cell(_repro_summary(entry.get("repro"))),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def render_phase3b_unknown_triage_text(inventory: Mapping[str, Any]) -> str:
    summary = _mapping(inventory.get("summary"))
    blockers = [entry for entry in list(inventory.get("blockers", [])) if isinstance(entry, Mapping)]
    lines = [
        "Phase 3B UNKNOWN triage blocker inventory",
        f"campaign_present={bool(summary.get('campaign_present', False))}",
        f"telemetry_present={bool(summary.get('telemetry_present', False))}",
        f"telemetry_wave_count={int(summary.get('telemetry_wave_count', 0))}",
        f"blocker_count={int(summary.get('blocker_count', 0))}",
        f"classification_counts={summary.get('classification_counts', {})}",
        f"subtype_counts={summary.get('subtype_counts', {})}",
    ]
    if not blockers:
        lines.append("No UNKNOWN/UNPROVEN/pre-master/orchestration blockers were found.")
        return "\n".join(lines) + "\n"
    for entry in blockers:
        objective = _mapping(entry.get("objective"))
        objective_text = (
            f"area={objective.get('area')},min_side={objective.get('min_side')}"
            if objective
            else "area=None,min_side=None"
        )
        lines.append(
            "blocker "
            f"candidate={entry.get('candidate_key')} "
            f"status={entry.get('status')} "
            f"classification={entry.get('classification')} "
            f"subtype={entry.get('blocker_subtype')} "
            f"disposition={entry.get('disposition')} "
            f"{objective_text} "
            f"stage={entry.get('stop_stage')} "
            f"reason={entry.get('stop_reason')} "
            f"start_failure={_start_failure_summary_text(entry.get('start_failure_summary'))} "
            f"repro={_repro_summary(entry.get('repro'))}"
        )
    return "\n".join(lines) + "\n"


def classify_phase3b_candidate_blocker(
    *,
    status: str,
    proof_summary: Optional[Mapping[str, Any]] = None,
    failure_reason: Optional[str] = None,
) -> Optional[str]:
    summary = dict(proof_summary or {})
    normalized_status = str(status or "")
    normalized_failure = str(failure_reason or "")
    if normalized_failure.startswith("worker_process_failed"):
        return "orchestration_failure"
    if isinstance(summary.get("operator_interruption"), Mapping):
        return "orchestration_failure"
    if _is_pre_master_eliminated(summary):
        return "pre_master_eliminated"
    if normalized_status == RUN_STATUS_UNPROVEN:
        return "unproven"

    binding_status = str(summary.get("binding_status") or "")
    routing_status = str(summary.get("routing_status") or "")
    master_status = str(summary.get("master_status") or "")
    if binding_status == "TIMEOUT":
        return "binding_timeout"
    if binding_status == "EMPTY_DOMAIN":
        return "binding_empty_domain"
    if routing_status == "TIMEOUT":
        return "routing_timeout"
    if routing_status in {"PRECHECK_FRONT_BLOCKED", "PRECHECK_RELAXED_DISCONNECTED"}:
        return "routing_precheck_reject"
    if routing_status == "ALL_INFEASIBLE":
        return "routing_all_infeasible"
    if master_status == "UNKNOWN":
        return "master_unknown"
    if normalized_status == RUN_STATUS_UNKNOWN:
        return "unknown_unclassified"
    return None


def _candidate_records_from_state(state: Optional[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    if not isinstance(state, Mapping) or not isinstance(state.get("candidates"), Mapping):
        return {}
    records: Dict[str, Dict[str, Any]] = {}
    for key, record in dict(state.get("candidates", {})).items():
        if isinstance(record, Mapping):
            records[str(key)] = dict(record)
    return records


def _candidate_blocker_entry(
    *,
    candidate_key: str,
    record: Mapping[str, Any],
    telemetry_entries: Sequence[Mapping[str, Any]],
    campaign_last_stop_reason: Mapping[str, Any],
    record_source: str,
) -> Optional[Dict[str, Any]]:
    proof_summary = _candidate_proof_summary(record, telemetry_entries)
    status = str(record.get("status") or _last_telemetry_value(telemetry_entries, "status") or "")
    failure_reason = _last_failure_reason(telemetry_entries)
    if (
        status == "RUNNING"
        and str(campaign_last_stop_reason.get("reason", "")) == "worker_process_failed"
    ):
        classification = "orchestration_failure"
    else:
        classification = classify_phase3b_candidate_blocker(
            status=status,
            proof_summary=proof_summary,
            failure_reason=failure_reason,
        )
    if classification is None:
        return None

    ghost_rect = _candidate_ghost_rect(candidate_key, record)
    blocker_subtype = _blocker_subtype_for_candidate(
        classification=classification,
        proof_summary=proof_summary,
    )
    stop_reason = _stop_reason_for_blocker(
        classification=classification,
        status=status,
        proof_summary=proof_summary,
        campaign_last_stop_reason=campaign_last_stop_reason,
        failure_reason=failure_reason,
    )
    return {
        "candidate_key": str(candidate_key),
        "ghost_rect": ghost_rect,
        "objective": _objective_from_ghost_rect(ghost_rect),
        "status": status,
        "classification": classification,
        "blocker_subtype": blocker_subtype,
        "stop_stage": _stop_stage_for_classification(classification),
        "stop_reason": stop_reason,
        "disposition": "mitigated"
        if classification == "pre_master_eliminated"
        else "open",
        "started_at": record.get("started_at"),
        "updated_at": record.get("updated_at"),
        "finished_at": record.get("finished_at"),
        "attempts": int(record.get("attempts", 0)),
        "telemetry_wave_indexes": sorted(
            {
                int(entry.get("wave_index", 0))
                for entry in telemetry_entries
                if isinstance(entry, Mapping)
            }
        ),
        "evidence_refs": _candidate_evidence_refs(
            candidate_key=candidate_key,
            record_source=record_source,
            telemetry_entries=telemetry_entries,
            proof_summary=proof_summary,
        ),
        "start_failure_summary": _start_failure_summary(proof_summary),
        "repro_command": _repro_command_for_blocker(),
        "repro": _repro_payload_for_blocker(
            stop_stage=_stop_stage_for_classification(classification),
            expected_stop_reason=stop_reason,
        ),
        "linked_test_name": _linked_test_name_for_blocker(
            classification=classification,
            blocker_subtype=blocker_subtype,
        ),
        "proof_summary": _compact_blocker_proof_summary(proof_summary),
    }


def _campaign_orchestration_blocker(
    *,
    last_stop_reason: Mapping[str, Any],
    telemetry: Optional[Mapping[str, Any]],
) -> Optional[Dict[str, Any]]:
    reason = str(last_stop_reason.get("reason", ""))
    aggregate = (
        dict(telemetry.get("aggregate", {}))
        if isinstance(telemetry, Mapping) and isinstance(telemetry.get("aggregate"), Mapping)
        else {}
    )
    outcome_counts = (
        dict(aggregate.get("outcome_counts", {}))
        if isinstance(aggregate.get("outcome_counts"), Mapping)
        else {}
    )
    failure_reason_counts = (
        dict(aggregate.get("failure_reason_counts", {}))
        if isinstance(aggregate.get("failure_reason_counts"), Mapping)
        else {}
    )
    has_worker_failure = reason == "worker_process_failed" or any(
        str(key).startswith("worker_process_failed")
        for key in failure_reason_counts
    )
    if not has_worker_failure and int(outcome_counts.get("worker_process_failed", 0)) <= 0:
        return None
    failure_reason = next(
        (
            str(key)
            for key in sorted(failure_reason_counts)
            if str(key).startswith("worker_process_failed")
        ),
        reason or "worker_process_failed",
    )
    return {
        "candidate_key": "__campaign__",
        "ghost_rect": None,
        "objective": None,
        "status": "__CAMPAIGN__",
        "classification": "orchestration_failure",
        "blocker_subtype": None,
        "stop_stage": "orchestration",
        "stop_reason": failure_reason,
        "disposition": "open",
        "started_at": None,
        "updated_at": last_stop_reason.get("updated_at"),
        "finished_at": None,
        "attempts": 0,
        "telemetry_wave_indexes": [],
        "evidence_refs": {
            "sources": ["campaign_state", "telemetry"],
            "candidate_key": "__campaign__",
            "telemetry_wave_indexes": [],
            "proof_fields": {"failure_reason": failure_reason},
        },
        "repro_command": _repro_command_for_blocker(),
        "repro": _repro_payload_for_blocker(
            stop_stage="orchestration",
            expected_stop_reason=failure_reason,
        ),
        "linked_test_name": _linked_test_name_for_blocker(
            classification="orchestration_failure",
            blocker_subtype=None,
        ),
        "proof_summary": {"failure_reason": failure_reason},
    }


def _start_failure_summary(proof_summary: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    master_start_failure = proof_summary.get("master_start_failure_attribution")
    if not isinstance(master_start_failure, Mapping):
        return None
    failed_anchor_count = int(master_start_failure.get("failed_anchor_count", 0))
    failure_reason_counts = (
        {
            str(key): int(value)
            for key, value in dict(
                master_start_failure.get("failure_reason_counts", {})
            ).items()
            if int(value) > 0
        }
        if isinstance(master_start_failure.get("failure_reason_counts"), Mapping)
        else {}
    )
    top_failed_group_failures = [
        {
            "group_id": str(entry.get("group_id", "")),
            "facility_type": str(entry.get("facility_type", "")),
            "failure_reason": str(entry.get("failure_reason", "")),
            "count": int(entry.get("count", 0)),
        }
        for entry in list(master_start_failure.get("top_failed_group_failures", []))[:8]
        if isinstance(entry, Mapping) and int(entry.get("count", 0)) > 0
    ]
    failed_anchor_samples = [
        _compact_failed_anchor_sample(entry)
        for entry in list(master_start_failure.get("failed_anchor_samples", []))[:8]
        if isinstance(entry, Mapping)
    ]
    if (
        failed_anchor_count <= 0
        and not failure_reason_counts
        and not top_failed_group_failures
        and not failed_anchor_samples
    ):
        return None
    return {
        "failed_anchor_count": int(failed_anchor_count),
        "failure_reason_counts": failure_reason_counts,
        "first_failed_group": {
            "group_id": master_start_failure.get("first_failed_group_id"),
            "facility_type": master_start_failure.get("first_failed_group_template"),
            "position": master_start_failure.get("first_failed_group_position"),
            "required_count": int(
                master_start_failure.get("first_failed_group_required_count", 0)
            ),
            "candidate_count": int(
                master_start_failure.get("first_failed_group_candidate_count", 0)
            ),
            "surviving_after_blocked_count": int(
                master_start_failure.get(
                    "first_failed_group_surviving_after_blocked_count",
                    0,
                )
            ),
            "surviving_at_failure_count": int(
                master_start_failure.get(
                    "first_failed_group_surviving_at_failure_count",
                    0,
                )
            ),
        },
        "top_failed_group_failures": top_failed_group_failures,
        "failed_anchor_samples": failed_anchor_samples,
    }


def _compact_failed_anchor_sample(entry: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "anchor_idx": int(entry.get("anchor_idx", 0)),
        "failure_reason": str(entry.get("failure_reason", "")),
        "first_failed_group_id": entry.get("first_failed_group_id"),
        "first_failed_group_template": entry.get("first_failed_group_template"),
        "first_failed_group_position": entry.get("first_failed_group_position"),
        "first_failed_group_required_count": int(
            entry.get("first_failed_group_required_count", 0)
        ),
        "first_failed_group_candidate_count": int(
            entry.get("first_failed_group_candidate_count", 0)
        ),
        "first_failed_group_surviving_after_blocked_count": int(
            entry.get("first_failed_group_surviving_after_blocked_count", 0)
        ),
        "first_failed_group_surviving_at_failure_count": int(
            entry.get("first_failed_group_surviving_at_failure_count", 0)
        ),
        "blocked_cell_count": int(entry.get("blocked_cell_count", 0)),
        "blocked_bbox": entry.get("blocked_bbox"),
        "local_repair_attempted": bool(entry.get("local_repair_attempted", False)),
        "local_repair_success": bool(entry.get("local_repair_success", False)),
        "local_repair_attempt_count": int(entry.get("local_repair_attempt_count", 0)),
        **_coordinate_validation_failure_sample_fields(entry),
    }


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


def _collect_telemetry_candidate_results(
    telemetry: Optional[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    if not isinstance(telemetry, Mapping):
        return []
    waves = telemetry.get("waves")
    if not isinstance(waves, Sequence) or isinstance(waves, (str, bytes)):
        return []
    results: list[Dict[str, Any]] = []
    for wave in waves:
        if not isinstance(wave, Mapping):
            continue
        candidate_results = wave.get("candidate_results")
        if not isinstance(candidate_results, Sequence) or isinstance(
            candidate_results,
            (str, bytes),
        ):
            continue
        for entry in candidate_results:
            if not isinstance(entry, Mapping):
                continue
            item = dict(entry)
            item["wave_index"] = int(wave.get("wave_index", 0))
            item["wave_failure_reason"] = wave.get("failure_reason")
            results.append(item)
    return results


def _telemetry_results_by_candidate(
    results: Iterable[Mapping[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for result in results:
        candidate_key = str(result.get("candidate_key") or "")
        if not candidate_key:
            continue
        grouped[candidate_key].append(result)

    payload: Dict[str, Dict[str, Any]] = {}
    for candidate_key, entries in grouped.items():
        last_entry = entries[-1]
        proof_summary = (
            last_entry.get("proof_summary")
            if isinstance(last_entry.get("proof_summary"), Mapping)
            else last_entry.get("proof_status_summary")
        )
        if not isinstance(proof_summary, Mapping):
            proof_summary = {}
        ghost_rect = _ghost_rect_from_candidate_key(candidate_key)
        payload[candidate_key] = {
            "entries": [dict(entry) for entry in entries],
            "record": {
                "ghost_rect": ghost_rect,
                "attempts": int(last_entry.get("attempt_index", 0)),
                "started_at": None,
                "updated_at": None,
                "finished_at": None,
                "status": str(last_entry.get("status", "")),
                "proof_summary": dict(proof_summary or {}),
                "exact_safe_cuts": [],
                "loaded_exact_safe_cut_count": int(
                    last_entry.get("loaded_exact_safe_cut_count", 0)
                ),
                "generated_exact_safe_cut_count": int(
                    last_entry.get("generated_exact_safe_cut_count", 0)
                ),
            },
        }
    return payload


def _candidate_proof_summary(
    record: Mapping[str, Any],
    telemetry_entries: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    proof_summary = record.get("proof_summary")
    if isinstance(proof_summary, Mapping) and proof_summary:
        return dict(proof_summary)
    for entry in reversed(telemetry_entries):
        if isinstance(entry.get("proof_summary"), Mapping):
            return dict(entry.get("proof_summary", {}))
        if isinstance(entry.get("proof_status_summary"), Mapping):
            return dict(entry.get("proof_status_summary", {}))
    return {}


def _compact_blocker_proof_summary(proof_summary: Mapping[str, Any]) -> Dict[str, Any]:
    compact: Dict[str, Any] = {}
    for key in (
        "mode",
        "master_status",
        "binding_status",
        "routing_status",
        "diagnostic_flow_status",
        "selection_reason",
    ):
        if key in proof_summary and proof_summary.get(key) is not None:
            compact[key] = proof_summary.get(key)
    for key in (
        "master_candidate_precheck",
        "precheck_lookahead",
        "master_last_solve",
        "master_warm_start",
        "master_start_feasibility",
        "master_start_failure_attribution",
        "master_start_local_repair",
        "master_mandatory_group_prechecks",
        "campaign_heartbeat",
        "operator_interruption",
    ):
        value = proof_summary.get(key)
        if isinstance(value, Mapping):
            compact[key] = dict(value)
    return compact


def _blocker_subtype_for_candidate(
    *,
    classification: str,
    proof_summary: Mapping[str, Any],
) -> Optional[str]:
    if str(classification) == "orchestration_failure":
        heartbeat = proof_summary.get("campaign_heartbeat")
        if isinstance(heartbeat, Mapping):
            stage = str(heartbeat.get("stage") or "candidate_stage")
            normalized_stage = "".join(
                ch if ch.isalnum() else "_" for ch in stage.lower()
            ).strip("_")
            return f"{normalized_stage or 'candidate_stage'}_interrupted"
        return None
    if str(classification) != "master_unknown":
        return None
    master_status = str(proof_summary.get("master_status") or "")
    if master_status != "UNKNOWN":
        return "master_unknown_general"

    master_last_solve = proof_summary.get("master_last_solve")
    branches: Optional[int] = None
    conflicts: Optional[int] = None
    if isinstance(master_last_solve, Mapping):
        branches = int(master_last_solve.get("branches", 0))
        conflicts = int(master_last_solve.get("conflicts", 0))

    master_start_feasibility = proof_summary.get("master_start_feasibility")
    compatible_anchor_count: Optional[int] = None
    if isinstance(master_start_feasibility, Mapping):
        compatible_anchor_count = int(
            master_start_feasibility.get("ghost_anchor_compatible_count", 0)
        )
        if bool(master_start_feasibility.get("ghost_anchor_compatibility_skipped", False)):
            return "master_start_skipped_unknown"
        if str(master_start_feasibility.get("ghost_anchor_hint_status", "")) == "skipped_anchor_limit":
            return "master_start_skipped_unknown"
    mandatory_prechecks = proof_summary.get("master_mandatory_group_prechecks")
    if isinstance(mandatory_prechecks, Mapping) and bool(
        mandatory_prechecks.get("interrupted_due_to_time_budget", False)
    ):
        return "mandatory_rectangle_precheck_time_budget_unknown"
    dominant_start_failure_subtype = _dominant_start_failure_subtype(proof_summary)
    if dominant_start_failure_subtype:
        return dominant_start_failure_subtype
    if compatible_anchor_count == 0:
        return "master_start_incompatible_unknown"
    if branches == 0 and compatible_anchor_count is not None and compatible_anchor_count > 0:
        return "master_start_compatible_zero_branch_unknown"

    master_start_failure = proof_summary.get("master_start_failure_attribution")
    if isinstance(master_start_failure, Mapping):
        failure_reason_counts = master_start_failure.get("failure_reason_counts")
        if int(master_start_failure.get("failed_anchor_count", 0)) > 0 or (
            isinstance(failure_reason_counts, Mapping) and bool(failure_reason_counts)
        ):
            return "ghost_aware_start_failure_unknown"

    if conflicts is not None and conflicts > 0:
        return "master_conflictful_unknown"
    if branches == 0:
        return "master_zero_branch_unknown"
    return "master_unknown_general"


def _dominant_start_failure_subtype(
    proof_summary: Mapping[str, Any],
) -> Optional[str]:
    ghost_count = _start_failure_reason_count(
        proof_summary,
        "ghost_overlap_forced_domain_infeasible",
    )
    signature_count = _start_failure_reason_count(
        proof_summary,
        "signature_monotonic_forced_label_infeasible",
    )
    if signature_count > 0 and signature_count >= ghost_count:
        return "master_start_signature_monotonic_incompatible_unknown"
    if ghost_count > 0:
        return "master_start_ghost_overlap_forced_domain_unknown"
    return None


def _start_failure_reason_count(
    proof_summary: Mapping[str, Any],
    reason_fragment: str,
) -> int:
    master_start_failure = proof_summary.get("master_start_failure_attribution")
    if not isinstance(master_start_failure, Mapping):
        return 0
    count = 0
    failure_reason_counts = master_start_failure.get("failure_reason_counts")
    if isinstance(failure_reason_counts, Mapping):
        for reason, value in failure_reason_counts.items():
            if reason_fragment in str(reason):
                count += int(value)
    for sample in list(master_start_failure.get("failed_anchor_samples", [])):
        if not isinstance(sample, Mapping):
            continue
        if reason_fragment in str(sample.get("failure_reason", "")):
            # Samples are bounded and may be truncated. Only use them as a fallback
            # when aggregate counts are absent.
            count += 1 if not isinstance(failure_reason_counts, Mapping) else 0
    return count


def _candidate_evidence_refs(
    *,
    candidate_key: str,
    record_source: str,
    telemetry_entries: Sequence[Mapping[str, Any]],
    proof_summary: Mapping[str, Any],
) -> Dict[str, Any]:
    telemetry_wave_indexes = sorted(
        {
            int(entry.get("wave_index", 0))
            for entry in telemetry_entries
            if isinstance(entry, Mapping)
        }
    )
    sources = [str(record_source)]
    if telemetry_wave_indexes and "telemetry" not in sources:
        sources.append("telemetry")
    return {
        "sources": sources,
        "candidate_key": str(candidate_key),
        "telemetry_wave_indexes": telemetry_wave_indexes,
        "proof_fields": _proof_field_refs(proof_summary),
    }


def _proof_field_refs(proof_summary: Mapping[str, Any]) -> Dict[str, Any]:
    refs: Dict[str, Any] = {}
    for key in (
        "master_status",
        "binding_status",
        "routing_status",
        "diagnostic_flow_status",
        "selection_reason",
    ):
        if proof_summary.get(key) is not None:
            refs[key] = proof_summary.get(key)

    master_last_solve = proof_summary.get("master_last_solve")
    if isinstance(master_last_solve, Mapping):
        refs["master_last_solve"] = {
            "status": master_last_solve.get("status"),
            "branches": int(master_last_solve.get("branches", 0)),
            "conflicts": int(master_last_solve.get("conflicts", 0)),
            "search_profile": master_last_solve.get("search_profile"),
        }
    master_start_feasibility = proof_summary.get("master_start_feasibility")
    if isinstance(master_start_feasibility, Mapping):
        refs["master_start_feasibility"] = {
            "ghost_anchor_compatible_count": int(
                master_start_feasibility.get("ghost_anchor_compatible_count", 0)
            ),
            "ghost_anchor_hint_status": master_start_feasibility.get(
                "ghost_anchor_hint_status"
            ),
            "warm_start_strategy": master_start_feasibility.get("warm_start_strategy"),
            "ghost_anchor_compatibility_skipped": bool(
                master_start_feasibility.get("ghost_anchor_compatibility_skipped", False)
            ),
        }
    master_start_failure = proof_summary.get("master_start_failure_attribution")
    if isinstance(master_start_failure, Mapping):
        refs["master_start_failure_attribution"] = {
            "failed_anchor_count": int(master_start_failure.get("failed_anchor_count", 0)),
            "failure_reason_counts": dict(
                master_start_failure.get("failure_reason_counts", {})
            )
            if isinstance(master_start_failure.get("failure_reason_counts"), Mapping)
            else {},
            "first_failed_group_id": master_start_failure.get("first_failed_group_id"),
            "first_failed_group_template": master_start_failure.get(
                "first_failed_group_template"
            ),
            "first_failed_group_position": master_start_failure.get(
                "first_failed_group_position"
            ),
            "first_failed_group_candidate_count": int(
                master_start_failure.get("first_failed_group_candidate_count", 0)
            ),
            "first_failed_group_surviving_after_blocked_count": int(
                master_start_failure.get(
                    "first_failed_group_surviving_after_blocked_count",
                    0,
                )
            ),
            "first_failed_group_surviving_at_failure_count": int(
                master_start_failure.get(
                    "first_failed_group_surviving_at_failure_count",
                    0,
                )
            ),
            "top_failed_group_failures": [
                {
                    "group_id": str(entry.get("group_id", "")),
                    "facility_type": str(entry.get("facility_type", "")),
                    "failure_reason": str(entry.get("failure_reason", "")),
                    "count": int(entry.get("count", 0)),
                }
                for entry in list(
                    master_start_failure.get("top_failed_group_failures", [])
                )[:8]
                if isinstance(entry, Mapping) and int(entry.get("count", 0)) > 0
            ],
            "failed_anchor_samples": [
                _compact_failed_anchor_sample(entry)
                for entry in list(
                    master_start_failure.get("failed_anchor_samples", [])
                )[:8]
                if isinstance(entry, Mapping)
            ],
        }
    precheck = proof_summary.get("master_candidate_precheck")
    if isinstance(precheck, Mapping):
        refs["master_candidate_precheck"] = {
            "triggered": bool(precheck.get("triggered", False)),
            "precheck_reason": precheck.get("precheck_reason"),
            "master_solve_skipped": bool(precheck.get("master_solve_skipped", False)),
        }
    lookahead = proof_summary.get("precheck_lookahead")
    if isinstance(lookahead, Mapping):
        refs["precheck_lookahead"] = {
            "enabled": bool(lookahead.get("enabled", False)),
            "slot_index": int(lookahead.get("slot_index", 0)),
            "limit": int(lookahead.get("limit", 0)),
            "is_selected_head": bool(lookahead.get("is_selected_head", False)),
        }
    heartbeat = proof_summary.get("campaign_heartbeat")
    if isinstance(heartbeat, Mapping):
        refs["campaign_heartbeat"] = {
            "stage": heartbeat.get("stage"),
            "event": heartbeat.get("event"),
            "iteration": heartbeat.get("iteration"),
            "updated_at": heartbeat.get("updated_at"),
            "routing_attempts": heartbeat.get("routing_attempts"),
            "enumerated_bindings": heartbeat.get("enumerated_bindings"),
            "skipped_due_to_anchor_limit": heartbeat.get("skipped_due_to_anchor_limit"),
            "considered_anchor_count": heartbeat.get("considered_anchor_count"),
            "screen_pass_anchor_count": heartbeat.get("screen_pass_anchor_count"),
            "upstream_anchor_filter_count": heartbeat.get("upstream_anchor_filter_count"),
            "supported_group_count": heartbeat.get("supported_group_count"),
        }
    operator_interruption = proof_summary.get("operator_interruption")
    if isinstance(operator_interruption, Mapping):
        refs["operator_interruption"] = {
            "reason": operator_interruption.get("reason"),
            "detail": operator_interruption.get("detail"),
            "marked_at": operator_interruption.get("marked_at"),
            "previous_status": operator_interruption.get("previous_status"),
        }
    return refs


def _repro_command_for_blocker() -> str:
    return "python main.py --mode certified_exact --resume-campaign --frontier-probe-mode auto"


def _repro_payload_for_blocker(
    *,
    stop_stage: str,
    expected_stop_reason: str,
) -> Dict[str, Any]:
    return {
        "command": _repro_command_for_blocker(),
        "env": {"PYTHONPATH": ".", "EXACT_CP_SAT_WORKERS": "1"},
        "expected_stop_stage": str(stop_stage),
        "expected_stop_reason": str(expected_stop_reason),
        "workspace_policy": (
            "Run repro and tuning in a workspace copy; repo main proof paths only "
            "receive final frozen evidence."
        ),
    }


def _linked_test_name_for_blocker(
    *,
    classification: str,
    blocker_subtype: Optional[str],
) -> str:
    if blocker_subtype and str(classification) == "master_unknown":
        return "src/tests/phase3b/campaign/test_triage.py::test_triage_classifies_master_unknown_subtypes"
    if blocker_subtype and str(classification) == "orchestration_failure":
        return "src/tests/phase3b/campaign/test_triage.py::test_triage_records_operator_interruption_heartbeat_subtype"
    return {
        "pre_master_eliminated": "src/tests/phase3b/campaign/test_triage.py::test_triage_classifies_precheck_eliminated_candidate",
        "unproven": "src/tests/phase3b/campaign/test_triage.py::test_triage_classifies_unproven_candidate",
        "orchestration_failure": "src/tests/phase3b/campaign/test_triage.py::test_triage_records_worker_failure_from_campaign_and_telemetry",
    }.get(
        str(classification),
        "src/tests/phase3b/campaign/test_triage.py::test_triage_classifies_unknown_stage_variants",
    )


def _is_pre_master_eliminated(proof_summary: Mapping[str, Any]) -> bool:
    precheck = proof_summary.get("master_candidate_precheck")
    return (
        isinstance(precheck, Mapping)
        and bool(precheck.get("triggered", False))
        and bool(precheck.get("master_solve_skipped", False))
    )


def _stop_reason_for_blocker(
    *,
    classification: str,
    status: str,
    proof_summary: Mapping[str, Any],
    campaign_last_stop_reason: Mapping[str, Any],
    failure_reason: Optional[str],
) -> str:
    if classification == "pre_master_eliminated":
        precheck = proof_summary.get("master_candidate_precheck")
        if isinstance(precheck, Mapping):
            return str(precheck.get("precheck_reason") or "pre_master_precheck")
        return "pre_master_precheck"
    if classification == "orchestration_failure":
        operator_interruption = proof_summary.get("operator_interruption")
        if isinstance(operator_interruption, Mapping):
            return str(operator_interruption.get("reason") or "operator_interrupted")
        return str(
            failure_reason
            or campaign_last_stop_reason.get("reason")
            or "worker_process_failed"
        )
    if classification == "master_unknown":
        return "master_status:UNKNOWN"
    if classification == "binding_timeout":
        return "binding_status:TIMEOUT"
    if classification == "binding_empty_domain":
        return "binding_status:EMPTY_DOMAIN"
    if classification == "routing_timeout":
        return "routing_status:TIMEOUT"
    if classification == "routing_precheck_reject":
        return f"routing_status:{proof_summary.get('routing_status')}"
    if classification == "routing_all_infeasible":
        return "routing_status:ALL_INFEASIBLE"
    if classification == "unproven":
        return str(campaign_last_stop_reason.get("reason") or "candidate_returned_unproven")
    return str(campaign_last_stop_reason.get("reason") or status or "unknown")


def _stop_stage_for_classification(classification: str) -> str:
    return {
        "pre_master_eliminated": "pre_master",
        "master_unknown": "master",
        "binding_timeout": "binding",
        "binding_empty_domain": "binding",
        "routing_timeout": "routing",
        "routing_precheck_reject": "routing",
        "routing_all_infeasible": "routing",
        "unproven": "proof",
        "orchestration_failure": "orchestration",
        "unknown_unclassified": "unknown",
    }.get(str(classification), "unknown")


def _last_failure_reason(telemetry_entries: Sequence[Mapping[str, Any]]) -> Optional[str]:
    for entry in reversed(telemetry_entries):
        failure_reason = entry.get("failure_reason") or entry.get("wave_failure_reason")
        if failure_reason:
            return str(failure_reason)
    return None


def _last_telemetry_value(
    telemetry_entries: Sequence[Mapping[str, Any]],
    key: str,
) -> Optional[Any]:
    for entry in reversed(telemetry_entries):
        if key in entry:
            return entry.get(key)
    return None


def _candidate_ghost_rect(candidate_key: str, record: Mapping[str, Any]) -> Optional[Dict[str, int]]:
    ghost_rect = record.get("ghost_rect")
    if isinstance(ghost_rect, Mapping):
        try:
            w = int(ghost_rect.get("w", 0))
            h = int(ghost_rect.get("h", 0))
            area = int(ghost_rect.get("area", w * h))
        except Exception:
            return _ghost_rect_from_candidate_key(candidate_key)
        return {"w": w, "h": h, "area": area}
    return _ghost_rect_from_candidate_key(candidate_key)


def _ghost_rect_from_candidate_key(candidate_key: str) -> Optional[Dict[str, int]]:
    try:
        raw_w, raw_h = str(candidate_key).split("x", 1)
        w = int(raw_w)
        h = int(raw_h)
    except Exception:
        return None
    return {"w": w, "h": h, "area": w * h}


def _objective_from_ghost_rect(
    ghost_rect: Optional[Mapping[str, Any]],
) -> Optional[Dict[str, int]]:
    if not isinstance(ghost_rect, Mapping):
        return None
    try:
        w = int(ghost_rect.get("w", 0))
        h = int(ghost_rect.get("h", 0))
        area = int(ghost_rect.get("area", w * h))
    except Exception:
        return None
    return {"area": area, "min_side": min(w, h)}


def _candidate_sort_key(candidate_key: str, record: Mapping[str, Any]) -> tuple[int, int, str]:
    ghost_rect = _candidate_ghost_rect(candidate_key, record)
    objective = _objective_from_ghost_rect(ghost_rect) or {"area": 0, "min_side": 0}
    return (-int(objective.get("area", 0)), -int(objective.get("min_side", 0)), str(candidate_key))


def _telemetry_wave_count(telemetry: Optional[Mapping[str, Any]]) -> int:
    if not isinstance(telemetry, Mapping):
        return 0
    waves = telemetry.get("waves")
    if not isinstance(waves, Sequence) or isinstance(waves, (str, bytes)):
        return 0
    return int(len(waves))


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"json_load_error:{type(exc).__name__}:{exc}"
    if not isinstance(payload, Mapping):
        return None, "json_payload_not_object"
    return dict(payload), None


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _ordered_counter_dict(counter: Mapping[str, int], ordered_keys: Sequence[str]) -> Dict[str, int]:
    payload: Dict[str, int] = {}
    for key in ordered_keys:
        count = int(counter.get(key, 0))
        if count > 0:
            payload[str(key)] = count
    for key in sorted(str(key) for key, value in counter.items() if int(value) > 0):
        if key not in payload:
            payload[key] = int(counter[key])
    return payload


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _repro_summary(value: Any) -> str:
    if not isinstance(value, Mapping):
        return ""
    command = str(value.get("command", ""))
    env = value.get("env")
    env_text = ""
    if isinstance(env, Mapping) and env:
        env_text = " ".join(f"{key}={env[key]}" for key in sorted(env))
    if env_text:
        return f"{env_text} {command}".strip()
    return command


def _start_failure_summary_text(value: Any) -> str:
    if not isinstance(value, Mapping):
        return ""
    failed_anchor_count = int(value.get("failed_anchor_count", 0))
    first_group = value.get("first_failed_group")
    first_group_text = ""
    if isinstance(first_group, Mapping):
        group_id = first_group.get("group_id") or ""
        facility_type = first_group.get("facility_type") or ""
        position = first_group.get("position")
        if group_id or facility_type:
            first_group_text = f"first={group_id}/{facility_type}"
            if position is not None:
                first_group_text += f"@{position}"
    top_failures = [
        entry
        for entry in list(value.get("top_failed_group_failures", []))
        if isinstance(entry, Mapping) and int(entry.get("count", 0)) > 0
    ]
    if top_failures:
        first_failure = top_failures[0]
        top_text = (
            f"top={first_failure.get('group_id')}/"
            f"{first_failure.get('facility_type')}:"
            f"{first_failure.get('failure_reason')}x"
            f"{int(first_failure.get('count', 0))}"
        )
    else:
        top_text = ""
    samples = [
        entry
        for entry in list(value.get("failed_anchor_samples", []))
        if isinstance(entry, Mapping)
    ]
    sample_text = ""
    if samples:
        reason_counts = value.get("failure_reason_counts")
        dominant_reason = None
        if isinstance(reason_counts, Mapping) and reason_counts:
            dominant_reason = max(
                ((str(reason), int(count)) for reason, count in reason_counts.items()),
                key=lambda item: item[1],
            )[0]
        sample = next(
            (
                entry
                for entry in samples
                if dominant_reason
                and str(entry.get("failure_reason", "")) == dominant_reason
            ),
            samples[0],
        )
        sample_text = (
            f"sample_anchor={sample.get('anchor_idx')}:"
            f"{sample.get('failure_reason')}"
        )
    parts = [
        part
        for part in [
            f"anchors={failed_anchor_count}",
            first_group_text,
            top_text,
            sample_text,
        ]
        if part
    ]
    return "; ".join(parts)


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
