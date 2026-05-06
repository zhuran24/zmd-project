from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso

JOINED_XY_PROBE_SYNTHESIS_SOURCE = "phase3b_joined_xy_probe_synthesis_v2"

DEFAULT_PROFILE_AUDIT_PATH = Path(
    ".artifacts/phase3b_joined_xy_profile_audit_20260423/"
    "joined_xy_profile_audit.json"
)
DEFAULT_SAT_EXPANSION_AUDIT_PATH = Path(
    ".artifacts/phase3b_joined_xy_sat_expansion_audit_20260423/"
    "joined_xy_sat_expansion_audit.json"
)
DEFAULT_PROBE_PATHS: Dict[str, Path] = {
    "anchor118_seed1": Path(
        ".artifacts/phase3b_joined_xy_probe_anchor118_60s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
    "anchor118_seed2": Path(
        ".artifacts/phase3b_joined_xy_probe_anchor118_60s_seed2_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
    "anchor119_seed1": Path(
        ".artifacts/phase3b_joined_xy_probe_anchor119_120s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
    "anchor119_focus300_seed1": Path(
        ".artifacts/phase3b_joined_xy_probe_anchor119_300s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
    "anchor120_focus300_seed1": Path(
        ".artifacts/phase3b_joined_xy_probe_anchor120_300s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
    "anchor122_focus300_seed1": Path(
        ".artifacts/phase3b_joined_xy_probe_anchor122_300s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
    "anchor124_focus300_seed1": Path(
        ".artifacts/phase3b_joined_xy_probe_anchor124_300s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
    "anchor123_focus300_seed1": Path(
        ".artifacts/phase3b_joined_xy_probe_anchor123_300s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
    "anchor125_focus300_seed1": Path(
        ".artifacts/phase3b_joined_xy_probe_anchor125_300s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
    "anchor125_seed1": Path(
        ".artifacts/phase3b_joined_xy_probe_anchor125_60s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
    "anchor120_124_seed1": Path(
        ".artifacts/phase3b_joined_xy_probe_anchor120_124_60s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
}


def build_phase3b_joined_xy_probe_synthesis(
    project_root: Path,
    *,
    profile_audit_path: Optional[Path] = None,
    sat_expansion_audit_path: Optional[Path] = None,
    probe_paths: Optional[Mapping[str, Path]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    profile_path = _resolve(project_root, profile_audit_path or DEFAULT_PROFILE_AUDIT_PATH)
    sat_path = _resolve(project_root, sat_expansion_audit_path or DEFAULT_SAT_EXPANSION_AUDIT_PATH)
    probes = {
        key: _resolve(project_root, value)
        for key, value in dict(probe_paths or DEFAULT_PROBE_PATHS).items()
    }

    profile_audit = _load_optional_json(profile_path)
    sat_expansion = _load_optional_json(sat_path)
    probe_reports = {
        key: _summarize_probe(project_root, key, path)
        for key, path in probes.items()
    }
    aggregate = _aggregate_probe_summaries(probe_reports)
    checks = _checks(profile_audit, sat_expansion, probe_reports, aggregate)
    ready = all(check["status"] == "pass" for check in checks)
    targeted_complete = bool(aggregate.get("anchor120_124_all_search_progress", False))

    return {
        "metadata": {
            "source": JOINED_XY_PROBE_SYNTHESIS_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "joined_xy_probe_synthesis_not_proof",
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
        },
        "paths": {
            "project_root": str(project_root),
            "profile_audit": _display(project_root, profile_path),
            "sat_expansion_audit": _display(project_root, sat_path),
            "probes": {
                key: _display(project_root, value) for key, value in probes.items()
            },
        },
        "status": {
            "completed": bool(ready),
            "outcome": (
                "joined_xy_targeted_anchor_set_completed"
                if ready and targeted_complete
                else "joined_xy_probe_synthesis_incomplete"
            ),
            "recommendation": _recommendation(aggregate),
        },
        "joined_xy_profile": _profile_summary(profile_audit),
        "sat_expansion": _sat_expansion_summary(sat_expansion),
        "probes": probe_reports,
        "aggregate": aggregate,
        "checks": checks,
    }


def render_phase3b_joined_xy_probe_synthesis_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    aggregate = _mapping(report.get("aggregate"))
    profile = _mapping(report.get("joined_xy_profile"))
    sat = _mapping(report.get("sat_expansion"))
    lines = [
        "# Phase 3B Joined-XY Probe Synthesis",
        "",
        "- Diagnostic semantics: joined_xy_probe_synthesis_not_proof",
        "- proof_source: false",
        f"- Outcome: {status.get('outcome')}",
        f"- Profile valid: {profile.get('profile_valid')}",
        f"- Padded selector removed: {profile.get('padded_selector_removed')}",
        f"- SAT expansion outcome: {sat.get('outcome')}",
        f"- Total anchors covered: {aggregate.get('anchor_count')}",
        f"- Terminal anchors: {aggregate.get('terminal_anchor_indices')}",
        f"- Search-progress UNKNOWN anchors: {aggregate.get('search_progress_unknown_anchor_indices')}",
        f"- Zero-branch UNKNOWN entries: {aggregate.get('zero_branch_unknown_count')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Probe Outcomes",
        "",
        "| Probe | Anchors | Outcome | Status Counts | Zero-Branch UNKNOWN | Campaign unchanged |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for key, probe in _mapping(report.get("probes")).items():
        if not isinstance(probe, Mapping):
            continue
        lines.append(
            f"| {_cell(key)} | {_cell(probe.get('anchor_indices'))} | "
            f"{_cell(probe.get('outcome'))} | "
            f"{_cell(json.dumps(probe.get('status_counts', {}), sort_keys=True))} | "
            f"{_cell(probe.get('zero_branch_unknown_count'))} | "
            f"{_cell(probe.get('campaign_state_unchanged'))} |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                f"| {_cell(check.get('check_id'))} | "
                f"{_cell(check.get('status'))} | "
                f"{_cell(check.get('detail'))} |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_joined_xy_probe_synthesis_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    aggregate = _mapping(report.get("aggregate"))
    return "\n".join(
        [
            "Phase3B joined-XY probe synthesis",
            "diagnostic_semantics=joined_xy_probe_synthesis_not_proof",
            "proof_source=false",
            f"outcome={status.get('outcome')}",
            f"anchor_count={aggregate.get('anchor_count')}",
            f"terminal_anchor_indices={aggregate.get('terminal_anchor_indices')}",
            (
                "search_progress_unknown_anchor_indices="
                f"{aggregate.get('search_progress_unknown_anchor_indices')}"
            ),
            f"zero_branch_unknown_count={aggregate.get('zero_branch_unknown_count')}",
            f"recommendation={status.get('recommendation')}",
        ]
    ) + "\n"


def write_phase3b_joined_xy_probe_synthesis(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "joined_xy_probe_synthesis",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_joined_xy_probe_synthesis_markdown(report),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_joined_xy_probe_synthesis_text(report),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _summarize_probe(project_root: Path, key: str, path: Path) -> Dict[str, Any]:
    payload = _load_optional_json(path)
    if not payload:
        return {
            "present": False,
            "path": _display(project_root, path),
            "outcome": "missing",
            "status_counts": {},
            "anchor_indices": [],
            "entries": [],
            "campaign_state_unchanged": None,
        }
    status = _mapping(payload.get("status"))
    profile = _mapping(payload.get("profile"))
    reduction = _mapping(payload.get("reduction"))
    proto = _mapping(payload.get("proto_profile"))
    entries = [_entry_summary(entry) for entry in list(reduction.get("entries", []))]
    anchors = sorted(
        {
            int(entry["anchor_idx"])
            for entry in entries
            if entry.get("anchor_idx") is not None
        }
    )
    unknown = _mapping(reduction.get("unknown_diagnostics"))
    cover = _mapping(proto.get("cover_choice_profile"))
    return {
        "present": True,
        "path": _display(project_root, path),
        "outcome": status.get("outcome"),
        "status_counts": dict(_mapping(status.get("status_counts"))),
        "campaign_state_unchanged": payload.get("campaign_state_unchanged"),
        "time_limit_seconds": profile.get("time_limit_seconds"),
        "anchor_indices": anchors,
        "entry_count": len(entries),
        "zero_branch_unknown_count": unknown.get("zero_branch_unknown_count", 0),
        "search_progress_unknown_count": unknown.get("search_progress_unknown_count", 0),
        "terminal_statuses": _terminal_statuses(entries),
        "entries": entries,
        "variable_count": proto.get("variable_count"),
        "constraint_count": proto.get("constraint_count"),
        "element_constraints": _mapping(proto.get("constraint_kind_counts")).get("element"),
        "bool_or_constraints": _mapping(proto.get("constraint_kind_counts")).get("bool_or"),
        "cover_choice_prefix_counts": dict(_mapping(cover.get("prefix_counts"))),
        "source_key": key,
    }


def _entry_summary(entry: Any) -> Dict[str, Any]:
    item = _mapping(entry)
    stats = _mapping(item.get("response_stats_parsed"))
    branches = item.get("branches", stats.get("branches"))
    conflicts = item.get("conflicts", stats.get("conflicts"))
    return {
        "anchor_idx": item.get("anchor_idx"),
        "variant": item.get("variant"),
        "status": item.get("status"),
        "branches": branches,
        "conflicts": conflicts,
        "wall_time": item.get("wall_time", stats.get("walltime")),
        "deterministic_time": item.get("deterministic_time", stats.get("deterministic_time")),
        "conflicts_per_1k_branches": _conflicts_per_1k(branches, conflicts),
    }


def _aggregate_probe_summaries(probes: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    all_entries = []
    missing = []
    campaign_unchanged = True
    for key, probe in probes.items():
        if not probe.get("present"):
            missing.append(key)
            continue
        if probe.get("campaign_state_unchanged") is not True:
            campaign_unchanged = False
        all_entries.extend(list(probe.get("entries", [])))

    terminal_entries = [
        entry for entry in all_entries if entry.get("status") in {"INFEASIBLE", "OPTIMAL", "FEASIBLE"}
    ]
    search_progress = [
        entry
        for entry in all_entries
        if entry.get("status") == "UNKNOWN"
        and int(entry.get("branches") or 0) > 0
        and int(entry.get("conflicts") or 0) > 0
    ]
    zero_branch = [
        entry
        for entry in all_entries
        if entry.get("status") == "UNKNOWN" and int(entry.get("branches") or 0) == 0
    ]
    anchors = sorted(
        {
            int(entry["anchor_idx"])
            for entry in all_entries
            if entry.get("anchor_idx") is not None
        }
    )
    anchors_120_124 = {120, 121, 122, 123, 124}
    progress_anchor_set = {
        int(entry["anchor_idx"])
        for entry in search_progress
        if entry.get("anchor_idx") is not None
    }
    return {
        "anchor_count": len(anchors),
        "anchor_indices": anchors,
        "entry_count": len(all_entries),
        "missing_probe_keys": missing,
        "campaign_states_unchanged": campaign_unchanged,
        "terminal_anchor_indices": sorted(
            {int(entry["anchor_idx"]) for entry in terminal_entries if entry.get("anchor_idx") is not None}
        ),
        "terminal_status_counts": _count_by_status(terminal_entries),
        "search_progress_unknown_anchor_indices": sorted(progress_anchor_set),
        "search_progress_unknown_count": len(search_progress),
        "zero_branch_unknown_count": len(zero_branch),
        "anchor120_124_all_search_progress": anchors_120_124.issubset(progress_anchor_set),
        "focus300_unknown_anchor_indices": _focus300_unknown_anchors(probes),
        "best_conflict_density_unknowns": _top_conflict_density(search_progress),
    }


def _checks(
    profile_audit: Mapping[str, Any],
    sat_expansion: Mapping[str, Any],
    probes: Mapping[str, Mapping[str, Any]],
    aggregate: Mapping[str, Any],
) -> list[Dict[str, str]]:
    profile = _profile_summary(profile_audit)
    sat = _sat_expansion_summary(sat_expansion)
    return [
        _check("solver_not_invoked", "pass", "synthesis only"),
        _check("proof_source_false", "pass", "diagnostic report only"),
        _check(
            "profile_valid",
            "pass" if profile.get("profile_valid") is True else "fail",
            str(profile),
        ),
        _check(
            "sat_expansion_recovered",
            "pass" if sat.get("recovered_active_guard_scale") is True else "fail",
            str(sat.get("outcome")),
        ),
        _check(
            "all_probe_inputs_present",
            "pass" if not aggregate.get("missing_probe_keys") else "fail",
            str(aggregate.get("missing_probe_keys")),
        ),
        _check(
            "anchor118_terminal_reproduced",
            "pass" if 118 in set(aggregate.get("terminal_anchor_indices", [])) else "fail",
            str(aggregate.get("terminal_anchor_indices")),
        ),
        _check(
            "anchor120_124_search_progress",
            "pass" if aggregate.get("anchor120_124_all_search_progress") is True else "fail",
            str(aggregate.get("search_progress_unknown_anchor_indices")),
        ),
        _check(
            "no_zero_branch_unknown",
            "pass" if int(aggregate.get("zero_branch_unknown_count", 0)) == 0 else "fail",
            str(aggregate.get("zero_branch_unknown_count")),
        ),
        _check(
            "campaign_states_unchanged",
            "pass" if aggregate.get("campaign_states_unchanged") is True else "fail",
            str(aggregate.get("campaign_states_unchanged")),
        ),
        _check(
            "status_counts_consistent",
            "pass" if _probe_statuses_present(probes) else "fail",
            "all present probes have status_counts",
        ),
    ]


def _profile_summary(profile_audit: Mapping[str, Any]) -> Dict[str, Any]:
    comparison = _mapping(profile_audit.get("comparison"))
    return {
        "profile_valid": comparison.get("joined_xy_profile_valid"),
        "padded_selector_removed": comparison.get("padded_selector_removed"),
        "no_pairwise_cover_literals": comparison.get("no_pairwise_cover_literals"),
        "selected_geometry_delta": comparison.get("selected_geometry_constraint_delta"),
    }


def _sat_expansion_summary(sat_expansion: Mapping[str, Any]) -> Dict[str, Any]:
    status = _mapping(sat_expansion.get("status"))
    comparison = _mapping(sat_expansion.get("comparison"))
    return {
        "outcome": status.get("outcome"),
        "recovered_active_guard_scale": comparison.get("joined_xy_recovered_active_guard_scale"),
        "joined_to_grouped_integer_encoding_ratio": comparison.get(
            "joined_to_grouped_integer_encoding_ratio"
        ),
        "joined_to_grouped_sat_boolean_ratio": comparison.get(
            "joined_to_grouped_sat_boolean_ratio"
        ),
        "joined_anchor119_conflicts_per_1k_branches": comparison.get(
            "joined_anchor119_conflicts_per_1k_branches"
        ),
        "grouped_anchor119_conflicts_per_1k_branches": comparison.get(
            "grouped_anchor119_conflicts_per_1k_branches"
        ),
    }


def _recommendation(aggregate: Mapping[str, Any]) -> str:
    if int(aggregate.get("zero_branch_unknown_count", 0)) > 0:
        return (
            "Joined-XY still has zero-branch UNKNOWN in the targeted set; inspect "
            "that anchor before spending longer solver time."
        )
    focus300 = set(int(item) for item in list(aggregate.get("focus300_unknown_anchor_indices", [])))
    if {119, 120, 122, 123, 124, 125}.issubset(focus300):
        return (
            "Joined-XY 300s focus now covers anchors 119-125 and all remain "
            "conflictful UNKNOWN, while anchor118 stays terminal and the targeted "
            "set has no zero-branch UNKNOWN. Next move to bounded joined-XY "
            "workspace validation; do not launch final 168h."
        )
    if {119, 120, 122, 124}.issubset(focus300):
        return (
            "Joined-XY 300s focus on anchors 119/120/122/124 remains conflictful "
            "UNKNOWN, while anchor118 stays terminal and the targeted set has no "
            "zero-branch UNKNOWN. Next move to bounded joined-XY workspace validation "
            "or run optional 300s completeness checks on anchors 123/125; do not "
            "launch final 168h."
        )
    if {119, 120}.issubset(focus300):
        return (
            "Joined-XY 300s focus on anchors 119 and 120 remains conflictful UNKNOWN, "
            "while anchor118 stays terminal and the targeted set has no zero-branch "
            "UNKNOWN. Next run narrow 300s focus on anchors 122/124 or move to bounded "
            "joined-XY workspace validation; do not launch final 168h."
        )
    if aggregate.get("anchor120_124_all_search_progress") is True:
        return (
            "Joined-XY now covers anchors 120-124 with search-progress UNKNOWN and "
            "keeps anchor118 terminal. Next choose a narrow 300s focus on the "
            "highest-conflict-density UNKNOWN anchors, or run bounded workspace "
            "validation; do not launch final 168h."
        )
    return (
        "Joined-XY remains promising but targeted anchor coverage is incomplete; "
        "finish the missing bounded probes before broader claims."
    )


def _terminal_statuses(entries: list[Mapping[str, Any]]) -> Dict[str, int]:
    return _count_by_status(
        [entry for entry in entries if entry.get("status") in {"INFEASIBLE", "OPTIMAL", "FEASIBLE"}]
    )


def _count_by_status(entries: list[Mapping[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("status"))
        counts[status] = counts.get(status, 0) + 1
    return counts


def _top_conflict_density(entries: list[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    ranked = sorted(
        entries,
        key=lambda entry: float(entry.get("conflicts_per_1k_branches") or 0.0),
        reverse=True,
    )
    return [
        {
            "anchor_idx": entry.get("anchor_idx"),
            "branches": entry.get("branches"),
            "conflicts": entry.get("conflicts"),
            "conflicts_per_1k_branches": entry.get("conflicts_per_1k_branches"),
        }
        for entry in ranked[:5]
    ]


def _focus300_unknown_anchors(probes: Mapping[str, Mapping[str, Any]]) -> list[int]:
    anchors = set()
    for key, probe in probes.items():
        if "focus300" not in str(key):
            continue
        for entry in list(probe.get("entries", [])):
            if (
                entry.get("status") == "UNKNOWN"
                and entry.get("anchor_idx") is not None
                and float(entry.get("wall_time") or 0.0) >= 299.0
            ):
                anchors.add(int(entry["anchor_idx"]))
    return sorted(anchors)


def _conflicts_per_1k(branches: Any, conflicts: Any) -> Optional[float]:
    try:
        branch_count = int(branches)
        conflict_count = int(conflicts)
    except Exception:
        return None
    if branch_count <= 0:
        return None
    return conflict_count * 1000.0 / branch_count


def _probe_statuses_present(probes: Mapping[str, Mapping[str, Any]]) -> bool:
    for probe in probes.values():
        if probe.get("present") and not probe.get("status_counts"):
            return False
    return True


def _load_optional_json(path: Path) -> Dict[str, Any]:
    if not Path(path).exists():
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _resolve(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display(project_root: Path, path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
