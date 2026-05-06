from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import now_iso
from src.search.phase3b_forced_anchor_master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
    _check,
    _display_path,
    _file_hash,
    _load_json_mapping,
    _mapping,
    _resolve_path,
    _selected_anchor_indices,
)
from src.search.phase3b_forced_anchor_model_slice import (
    _build_exact_overlay,
    _candidate_ghost_rect,
    _clone_model_proto,
    _power_family_shell_pair_table_payload,
    _solve_slice_clone,
)

FAMILY_LOOKUP_ASSUMPTION_PROBE_SOURCE = "phase3b_family_lookup_assumption_probe_v1"

DEFAULT_ASSUMPTION_VARIANTS = (
    "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only",
    "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only",
)


def build_phase3b_family_lookup_assumption_probe(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    sample_limit: int = 1,
    anchor_indices: Optional[Sequence[int]] = None,
    time_limit_seconds: float = 8.0,
    worker_count: int = 4,
    variants: Optional[Sequence[str]] = None,
    slot_limit: int = 2,
    family_limit_per_slot: int = 2,
    solver_parameter_profile: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path if campaign_state_path is not None else DEFAULT_CAMPAIGN_STATE_PATH,
    )
    before_hash = _file_hash(campaign_path)
    state, state_error = _load_json_mapping(campaign_path)
    candidates = _mapping(state.get("candidates")) if state else {}
    record = _mapping(candidates.get(str(candidate)))
    proof_summary = _mapping(record.get("proof_summary"))
    failure_attribution = _mapping(proof_summary.get("master_start_failure_attribution"))
    failed_anchor_samples = [
        entry
        for entry in list(failure_attribution.get("failed_anchor_samples", []))
        if isinstance(entry, Mapping)
    ]
    selected_anchor_indices = _selected_anchor_indices(
        failed_anchor_samples,
        sample_limit,
        explicit_anchor_indices=anchor_indices,
    )
    variants_to_probe = _normalize_variants(variants or DEFAULT_ASSUMPTION_VARIANTS)
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Family lookup assumption probe has not run.",
    }
    entries: list[Dict[str, Any]] = []
    assumptions: list[Dict[str, Any]] = []
    timing: Dict[str, float] = {}
    model_error: Optional[str] = None
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before assumption probing.",
            }
        )
    elif not record:
        status.update(
            {
                "completed": True,
                "outcome": "candidate_missing",
                "recommendation": "Candidate is not present in campaign state; choose a recorded blocker candidate.",
            }
        )
    elif not selected_anchor_indices:
        status.update(
            {
                "completed": True,
                "outcome": "forced_anchor_samples_missing",
                "recommendation": "No forced anchors selected; rerun B5A with failed-anchor sampling enabled.",
            }
        )
    else:
        try:
            overlay_started = time.perf_counter()
            ghost_rect = _candidate_ghost_rect(str(candidate), record)
            model, base_proto = _build_exact_overlay(
                project_root,
                ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                master_search_profile=str(master_search_profile),
            )
            base_proto = _clone_model_proto(base_proto)
            payload = _power_family_shell_pair_table_payload(model, base_proto)
            assumptions = _selected_literal_assumptions(
                payload,
                slot_limit=max(1, int(slot_limit)),
                family_limit_per_slot=max(1, int(family_limit_per_slot)),
            )
            timing["overlay_build_seconds"] = float(time.perf_counter() - overlay_started)
            solve_started = time.perf_counter()
            for anchor_idx in selected_anchor_indices:
                u_var = model.u_vars.get(int(anchor_idx))
                if u_var is None:
                    for assumption in assumptions:
                        for variant in variants_to_probe:
                            entries.append(
                                {
                                    "anchor_idx": int(anchor_idx),
                                    "variant": str(variant),
                                    "assumption_label": assumption["label"],
                                    "evaluated": False,
                                    "status": "SKIPPED",
                                    "skip_reason": "anchor_not_in_model_u_vars",
                                }
                            )
                    continue
                for assumption in assumptions:
                    for variant in variants_to_probe:
                        entries.append(
                            _solve_slice_clone(
                                base_proto,
                                anchor_idx=int(anchor_idx),
                                u_var_index=int(u_var.Index()),
                                disabled_active_var_indices=[],
                                variant=str(variant),
                                time_limit_seconds=float(time_limit_seconds),
                                worker_count=int(worker_count),
                                power_coverage_dynamic_relaxation_mode=str(variant),
                                power_family_layer_relaxation_mode=(
                                    "power_family_lookup_constraints_relaxed"
                                ),
                                power_family_shell_pair_table_payload=payload,
                                power_family_lookup_rebuild_mode=str(variant),
                                solver_parameter_profile=solver_parameter_profile,
                                forced_bool_true_indices=[
                                    int(assumption["literal_var_index"])
                                ],
                                assumption_label=str(assumption["label"]),
                            )
                        )
            timing["probe_solve_seconds"] = float(time.perf_counter() - solve_started)
            status.update(_status_from_entries(entries))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Family lookup assumption probe failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    after_hash = _file_hash(campaign_path)
    return {
        "metadata": {
            "source": FAMILY_LOOKUP_ASSUMPTION_PROBE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "assumption_split_probe_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "campaign_state": _display_path(project_root, campaign_path),
        },
        "candidate": {
            "key": str(candidate),
            "campaign_status": record.get("status") if record else None,
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "sample_limit": int(sample_limit),
            "selected_anchor_indices": [int(idx) for idx in selected_anchor_indices],
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
            "variants": list(variants_to_probe),
            "slot_limit": int(slot_limit),
            "family_limit_per_slot": int(family_limit_per_slot),
            "assumption_count": int(len(assumptions)),
        },
        "assumptions": assumptions,
        "status": status,
        "probe": {
            "entries": entries,
            "status_counts": _status_counts(entries),
            "status_counts_by_variant": _status_counts_by_key(entries, "variant"),
            "status_counts_by_assumption": _status_counts_by_key(
                entries,
                "assumption_label",
            ),
            "best_terminal_entry": _best_terminal_entry(entries),
            "unknown_diagnostics": _unknown_diagnostics(entries),
        },
        "timing": timing,
        "model_error": model_error,
        "campaign_state_unchanged": bool(before_hash == after_hash),
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            assumption_count=len(assumptions),
            status=status,
            campaign_state_unchanged=before_hash == after_hash,
            model_error=model_error,
        ),
    }


def render_phase3b_family_lookup_assumption_probe_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    probe = _mapping(report.get("probe"))
    unknowns = _mapping(probe.get("unknown_diagnostics"))
    lines = [
        "# Phase 3B Family Lookup Assumption Probe",
        "",
        f"- Candidate: {_mapping(report.get('candidate')).get('key')}",
        "- Diagnostic semantics: assumption_split_probe_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Status counts: {probe.get('status_counts', {})}",
        f"- Zero-branch UNKNOWN entries: {unknowns.get('zero_branch_unknown_count', 0)}",
        f"- Search-progress UNKNOWN entries: {unknowns.get('search_progress_unknown_count', 0)}",
        "",
        "## Assumption Matrix",
        "",
        "| Assumption | Variant | Status | Wall | Branches | Conflicts |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in list(probe.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("assumption_label")),
                    _markdown_cell(entry.get("variant")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(entry.get("wall_time")),
                    _markdown_cell(entry.get("branches")),
                    _markdown_cell(entry.get("conflicts")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(check.get("check_id")),
                        _markdown_cell(check.get("status")),
                        _markdown_cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_family_lookup_assumption_probe_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    probe = _mapping(report.get("probe"))
    unknowns = _mapping(probe.get("unknown_diagnostics"))
    lines = [
        "Phase 3B family lookup assumption probe",
        f"candidate={_mapping(report.get('candidate')).get('key')}",
        "diagnostic_semantics=assumption_split_probe_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"status_counts={probe.get('status_counts', {})}",
        f"zero_branch_unknown_count={unknowns.get('zero_branch_unknown_count', 0)}",
        f"search_progress_unknown_count={unknowns.get('search_progress_unknown_count', 0)}",
    ]
    for entry in list(probe.get("entries", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "entry "
                f"assumption={entry.get('assumption_label')} "
                f"variant={entry.get('variant')} "
                f"status={entry.get('status')} "
                f"wall={entry.get('wall_time')} "
                f"branches={entry.get('branches')} "
                f"conflicts={entry.get('conflicts')}"
            )
    return "\n".join(lines) + "\n"


def _selected_literal_assumptions(
    payload: Mapping[str, Any],
    *,
    slot_limit: int,
    family_limit_per_slot: int,
) -> list[Dict[str, Any]]:
    assumptions: list[Dict[str, Any]] = []
    for slot in list(payload.get("slots", []))[: max(0, int(slot_limit))]:
        if not isinstance(slot, Mapping):
            continue
        slot_key = str(slot.get("slot_key"))
        family_map = _mapping(slot.get("family_lit_indices_by_family_id"))
        for family_id, lit_idx in list(sorted(family_map.items()))[
            : max(0, int(family_limit_per_slot))
        ]:
            assumptions.append(
                {
                    "label": f"{slot_key}:family_{int(family_id):03d}",
                    "slot_key": slot_key,
                    "family_id": int(family_id),
                    "literal_var_index": int(lit_idx),
                }
            )
    return assumptions


def _normalize_variants(variants: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in variants:
        token = str(raw).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        result.append(token)
    return tuple(result or DEFAULT_ASSUMPTION_VARIANTS)


def _status_from_entries(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    evaluated = [entry for entry in entries if bool(entry.get("evaluated", False))]
    counts = _status_counts(evaluated)
    unknowns = _unknown_diagnostics(evaluated)
    if not entries:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_assumption_probe_entries",
            "status_counts": counts,
            "recommendation": "No assumption-probe entries were evaluated.",
        }
    if any(str(entry.get("status")) in {"OPTIMAL", "FEASIBLE"} for entry in evaluated):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "assumption_probe_terminal_found",
            "status_counts": counts,
            "recommendation": "At least one forced family lookup assumption reached terminal feasibility; inspect before runtime changes.",
        }
    if any(str(entry.get("status")) == "INFEASIBLE" for entry in evaluated):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "assumption_probe_infeasible_found",
            "status_counts": counts,
            "recommendation": "At least one forced family lookup assumption is infeasible; use it to shrink the semantic repro.",
        }
    if int(unknowns.get("search_progress_unknown_count", 0)) > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "assumption_probe_progress_without_terminal",
            "status_counts": counts,
            "recommendation": "Forced assumptions trigger search progress without terminal status; compare those assumptions against zero-branch entries.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "assumption_probe_zero_branch_unknown_remaining",
        "status_counts": counts,
        "recommendation": "Forced family lookup assumptions still remain zero-branch UNKNOWN; build a smaller semantic repro.",
    }


def _status_counts(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("status", "UNKNOWN"))
        counts[status] = int(counts.get(status, 0)) + 1
    return counts


def _status_counts_by_key(
    entries: Sequence[Mapping[str, Any]],
    key_name: str,
) -> Dict[str, Dict[str, int]]:
    grouped: Dict[str, Dict[str, int]] = {}
    for entry in entries:
        key = str(entry.get(key_name))
        status = str(entry.get("status", "UNKNOWN"))
        bucket = grouped.setdefault(key, {})
        bucket[status] = int(bucket.get(status, 0)) + 1
    return grouped


def _best_terminal_entry(entries: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    terminal = [
        entry
        for entry in entries
        if str(entry.get("status")) in {"OPTIMAL", "FEASIBLE"}
    ]
    if not terminal:
        return None
    return dict(
        sorted(
            terminal,
            key=lambda entry: (
                float(entry.get("wall_time", 10**9)),
                str(entry.get("assumption_label")),
                str(entry.get("variant")),
            ),
        )[0]
    )


def _unknown_diagnostics(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    unknowns = [entry for entry in entries if str(entry.get("status")) == "UNKNOWN"]
    zero_branch = [
        entry
        for entry in unknowns
        if _number_or_zero(entry.get("branches")) == 0
        and _number_or_zero(entry.get("conflicts")) == 0
    ]
    progress = [entry for entry in unknowns if entry not in zero_branch]
    return {
        "unknown_count": int(len(unknowns)),
        "zero_branch_unknown_count": int(len(zero_branch)),
        "search_progress_unknown_count": int(len(progress)),
        "zero_branch_unknown_by_assumption": _count_entries_by_key(
            zero_branch,
            "assumption_label",
        ),
        "zero_branch_unknown_by_variant": _count_entries_by_key(
            zero_branch,
            "variant",
        ),
    }


def _count_entries_by_key(
    entries: Sequence[Mapping[str, Any]],
    key_name: str,
) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        key = str(entry.get(key_name))
        counts[key] = int(counts.get(key, 0)) + 1
    return counts


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
    selected_anchor_count: int,
    assumption_count: int,
    status: Mapping[str, Any],
    campaign_state_unchanged: bool,
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    return [
        _check(
            "campaign_state_present",
            "pass" if state_present else "fail",
            "campaign state loaded" if state_present else "campaign state missing",
        ),
        _check(
            "candidate_present",
            "pass" if candidate_present else "fail",
            "candidate loaded" if candidate_present else "candidate missing",
        ),
        _check(
            "anchor_samples_present",
            "pass" if selected_anchor_count > 0 else "fail",
            f"selected_anchor_count={int(selected_anchor_count)}",
        ),
        _check(
            "assumptions_selected",
            "pass" if assumption_count > 0 else "fail",
            f"assumption_count={int(assumption_count)}",
        ),
        _check(
            "assumption_probe_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "skipped",
            str(status.get("outcome")),
        ),
        _check(
            "campaign_state_unchanged",
            "pass" if campaign_state_unchanged else "fail",
            "campaign state hash unchanged"
            if campaign_state_unchanged
            else "campaign state changed during diagnostic",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _number_or_zero(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")
