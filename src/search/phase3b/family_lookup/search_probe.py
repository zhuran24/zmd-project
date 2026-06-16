from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import now_iso
from src.search.phase3b.forced_anchor.master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
    _check,
    _display_path,
    _mapping,
    _resolve_path,
)
from src.search.phase3b.forced_anchor.model_slice import (
    build_phase3b_forced_anchor_model_slice_diagnostic,
)

FAMILY_LOOKUP_SEARCH_PROBE_SOURCE = "phase3b_family_lookup_search_probe_v1"

DEFAULT_SEARCH_PROBE_VARIANTS = (
    "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only",
    "power_coverage_dynamic_and_family_lookup_rebuilt_membership_only",
    "power_coverage_dynamic_and_family_lookup_rebuilt_shell_pair_only",
)
DEFAULT_SEARCH_PROBE_PROFILES = (
    {
        "profile_id": "portfolio_probe3_sym3_4w",
        "search_branching": "portfolio",
        "cp_model_probing_level": 3,
        "symmetry_level": 3,
        "worker_count": 4,
    },
    {
        "profile_id": "fixed_probe3_sym3_1w",
        "search_branching": "fixed",
        "cp_model_probing_level": 3,
        "symmetry_level": 3,
        "worker_count": 1,
    },
    {
        "profile_id": "automatic_probe3_sym3_4w",
        "search_branching": "automatic",
        "cp_model_probing_level": 3,
        "symmetry_level": 3,
        "worker_count": 4,
    },
    {
        "profile_id": "portfolio_probe0_sym0_1w",
        "search_branching": "portfolio",
        "cp_model_probing_level": 0,
        "symmetry_level": 0,
        "worker_count": 1,
    },
    {
        "profile_id": "fixed_probe0_sym0_1w",
        "search_branching": "fixed",
        "cp_model_probing_level": 0,
        "symmetry_level": 0,
        "worker_count": 1,
    },
)


def build_phase3b_family_lookup_search_probe(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    sample_limit: int = 1,
    anchor_indices: Optional[Sequence[int]] = None,
    time_limit_seconds: float = 10.0,
    variants: Optional[Sequence[str]] = None,
    profiles: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path if campaign_state_path is not None else DEFAULT_CAMPAIGN_STATE_PATH,
    )
    normalized_variants = _normalize_variants(variants or DEFAULT_SEARCH_PROBE_VARIANTS)
    normalized_profiles = _normalize_profiles(profiles or DEFAULT_SEARCH_PROBE_PROFILES)
    reports: list[Dict[str, Any]] = []
    entries: list[Dict[str, Any]] = []
    for profile in normalized_profiles:
        report = build_phase3b_forced_anchor_model_slice_diagnostic(
            project_root,
            campaign_state_path=campaign_path,
            candidate=str(candidate),
            master_search_profile=str(master_search_profile),
            sample_limit=int(sample_limit),
            anchor_indices=anchor_indices,
            time_limit_seconds=float(time_limit_seconds),
            worker_count=int(profile["worker_count"]),
            variants=normalized_variants,
            solver_parameter_profile=profile,
        )
        status = _mapping(report.get("status"))
        matrix = _mapping(report.get("slice_matrix"))
        profile_entries: list[Dict[str, Any]] = []
        for raw_entry in list(matrix.get("entries", [])):
            if not isinstance(raw_entry, Mapping):
                continue
            entry = dict(raw_entry)
            entry["solver_profile_id"] = str(profile["profile_id"])
            entry["probe_variant"] = str(entry.get("variant"))
            profile_entries.append(entry)
            entries.append(entry)
        reports.append(
            {
                "profile_id": str(profile["profile_id"]),
                "outcome": status.get("outcome"),
                "evaluated": bool(status.get("evaluated", False)),
                "status_counts": dict(_mapping(status.get("status_counts"))),
                "model_error": report.get("model_error"),
                "campaign_state_unchanged": bool(
                    report.get("campaign_state_unchanged", False)
                ),
                "entry_count": int(len(profile_entries)),
            }
        )
    status = _status_from_entries(entries, reports)
    return {
        "metadata": {
            "source": FAMILY_LOOKUP_SEARCH_PROBE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "search_parameter_probe_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "campaign_state": _display_path(project_root, campaign_path),
        },
        "candidate": {"key": str(candidate)},
        "profile": {
            "master_search_profile": str(master_search_profile),
            "sample_limit": int(sample_limit),
            "anchor_indices": [int(idx) for idx in list(anchor_indices or [])],
            "time_limit_seconds": float(time_limit_seconds),
            "variants": list(normalized_variants),
            "profiles": normalized_profiles,
        },
        "status": status,
        "probe": {
            "entries": entries,
            "status_counts": _status_counts(entries),
            "status_counts_by_variant": _status_counts_by_key(entries, "probe_variant"),
            "status_counts_by_profile": _status_counts_by_key(entries, "solver_profile_id"),
            "best_terminal_entry": _best_terminal_entry(entries),
            "unknown_diagnostics": _unknown_diagnostics(entries),
            "profile_reports": reports,
        },
        "campaign_state_unchanged": all(
            bool(report.get("campaign_state_unchanged", False)) for report in reports
        )
        if reports
        else False,
        "checks": _checks(status, reports),
    }


def render_phase3b_family_lookup_search_probe_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    probe = _mapping(report.get("probe"))
    unknowns = _mapping(probe.get("unknown_diagnostics"))
    lines = [
        "# Phase 3B Family Lookup Search Probe",
        "",
        f"- Candidate: {_mapping(report.get('candidate')).get('key')}",
        "- Diagnostic semantics: search_parameter_probe_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Status counts: {probe.get('status_counts', {})}",
        f"- Zero-branch UNKNOWN entries: {unknowns.get('zero_branch_unknown_count', 0)}",
        f"- Search-progress UNKNOWN entries: {unknowns.get('search_progress_unknown_count', 0)}",
        "",
        "## Probe Matrix",
        "",
        "| Variant | Profile | Status | Wall | Branches | Conflicts | Branching | Probe | Sym | Workers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in list(probe.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("probe_variant")),
                    _markdown_cell(entry.get("solver_profile_id")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(entry.get("wall_time")),
                    _markdown_cell(entry.get("branches")),
                    _markdown_cell(entry.get("conflicts")),
                    _markdown_cell(entry.get("search_branching")),
                    _markdown_cell(entry.get("cp_model_probing_level")),
                    _markdown_cell(entry.get("symmetry_level")),
                    _markdown_cell(entry.get("solver_worker_count")),
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


def render_phase3b_family_lookup_search_probe_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    probe = _mapping(report.get("probe"))
    unknowns = _mapping(probe.get("unknown_diagnostics"))
    lines = [
        "Phase 3B family lookup search probe",
        f"candidate={_mapping(report.get('candidate')).get('key')}",
        "diagnostic_semantics=search_parameter_probe_not_proof_source",
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
                f"variant={entry.get('probe_variant')} "
                f"profile={entry.get('solver_profile_id')} "
                f"status={entry.get('status')} "
                f"wall={entry.get('wall_time')} "
                f"branches={entry.get('branches')} "
                f"conflicts={entry.get('conflicts')} "
                f"branching={entry.get('search_branching')}"
            )
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check "
                f"id={check.get('check_id')} "
                f"status={check.get('status')} "
                f"detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _normalize_variants(variants: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in variants:
        token = str(raw).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        result.append(token)
    return tuple(result or DEFAULT_SEARCH_PROBE_VARIANTS)


def _normalize_profiles(profiles: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(profiles):
        profile_id = str(raw.get("profile_id") or f"profile_{index}").strip()
        if not profile_id or profile_id in seen:
            continue
        seen.add(profile_id)
        branching = str(raw.get("search_branching", "portfolio")).strip().lower()
        if branching not in {"fixed", "automatic", "portfolio"}:
            raise ValueError(f"Unsupported search_branching in profile {profile_id}: {branching}")
        normalized: Dict[str, Any] = {
            "profile_id": profile_id,
            "search_branching": branching,
            "cp_model_probing_level": max(0, int(raw.get("cp_model_probing_level", 3))),
            "symmetry_level": max(0, int(raw.get("symmetry_level", 3))),
            "worker_count": max(1, int(raw.get("worker_count", 4))),
        }
        for key in ("hint_conflict_limit", "linearization_level", "random_seed"):
            if key in raw and raw[key] is not None:
                normalized[key] = int(raw[key])
        for key in ("cp_model_presolve", "randomize_search"):
            if key in raw and raw[key] is not None:
                normalized[key] = _bool_value(raw[key])
        result.append(normalized)
    return result or _normalize_profiles(DEFAULT_SEARCH_PROBE_PROFILES)


def _status_from_entries(
    entries: Sequence[Mapping[str, Any]],
    reports: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    evaluated = [entry for entry in entries if bool(entry.get("evaluated", False))]
    counts = _status_counts(evaluated)
    unknowns = _unknown_diagnostics(evaluated)
    if any(str(report.get("model_error") or "") for report in reports):
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "search_probe_error",
            "status_counts": counts,
            "recommendation": "Search probe failed for at least one profile; inspect profile_reports before using this evidence.",
        }
    if not entries:
        outcome = str(reports[0].get("outcome")) if reports else "no_search_probe_entries"
        return {
            "completed": True,
            "evaluated": False,
            "outcome": outcome,
            "status_counts": counts,
            "recommendation": "No family lookup search-probe entries were evaluated.",
        }
    if any(str(entry.get("status")) in {"OPTIMAL", "FEASIBLE"} for entry in evaluated):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "search_probe_terminal_found",
            "status_counts": counts,
            "recommendation": "At least one family lookup search profile reached terminal feasibility; inspect before any runtime promotion.",
        }
    if int(unknowns.get("search_progress_unknown_count", 0)) > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "search_probe_progress_without_terminal",
            "status_counts": counts,
            "recommendation": "Some family lookup search profiles branch or conflict before timeout; compare those profiles before formulation changes.",
        }
    if int(unknowns.get("zero_branch_unknown_count", 0)) > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "search_probe_zero_branch_unknown_remaining",
            "status_counts": counts,
            "recommendation": "All UNKNOWN family lookup search profiles remain zero-branch/zero-conflict; prioritize formulation or assumption-splitting diagnostics.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "search_probe_inconclusive",
        "status_counts": counts,
        "recommendation": "Search probe did not produce terminal or zero-branch evidence; inspect matrix entries.",
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
                str(entry.get("probe_variant")),
                str(entry.get("solver_profile_id")),
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
        "zero_branch_unknown_by_variant": _count_entries_by_key(
            zero_branch,
            "probe_variant",
        ),
        "zero_branch_unknown_by_profile": _count_entries_by_key(
            zero_branch,
            "solver_profile_id",
        ),
        "search_progress_unknown_samples": [
            {
                "variant": entry.get("probe_variant"),
                "profile": entry.get("solver_profile_id"),
                "branches": entry.get("branches"),
                "conflicts": entry.get("conflicts"),
                "wall_time": entry.get("wall_time"),
            }
            for entry in progress[:8]
        ],
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
    status: Mapping[str, Any],
    reports: Sequence[Mapping[str, Any]],
) -> list[Dict[str, str]]:
    return [
        _check(
            "search_probe_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "skipped",
            str(status.get("outcome")),
        ),
        _check(
            "campaign_state_unchanged",
            "pass"
            if reports and all(bool(report.get("campaign_state_unchanged", False)) for report in reports)
            else "fail",
            "campaign state hash unchanged"
            if reports and all(bool(report.get("campaign_state_unchanged", False)) for report in reports)
            else "campaign state changed or was not verified",
        ),
        _check(
            "model_error_absent",
            "pass"
            if all(not str(report.get("model_error") or "") for report in reports)
            else "fail",
            "no model error"
            if all(not str(report.get("model_error") or "") for report in reports)
            else "at least one profile reported model_error",
        ),
    ]


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value: {value!r}")


def _number_or_zero(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")
