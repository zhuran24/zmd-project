from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from src.search.exact_campaign import now_iso
from src.search.phase3b.forced_anchor.master import _check, _display_path, _mapping

ACTIVE_GUARD_RESIDUAL_SURFACE_SOURCE = "phase3b_active_guard_residual_surface_v1"
DEFAULT_PROTOCOL_AUDIT_PATH = Path(
    ".artifacts/phase3b_active_guard_residual_surface_protocol_audit_119_124_125_20260423_r2/"
    "protocol_target_channel_slot_audit.json"
)
DEFAULT_FAMILY_BOUND_AUDIT_PATH = Path(
    ".artifacts/phase3b_family_bound_audit_67x13_family009_active_guard_anchors119_124_125_20260423/"
    "family_bound_audit_67x13_family009_anchors119_124_125.json"
)
DEFAULT_ACTIVE_GUARD_PROBE_PATHS = (
    Path(
        ".artifacts/phase3b_active_guard_probe_anchor119_300s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
    Path(
        ".artifacts/phase3b_active_guard_probe_anchor119_300s_seed2_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
    Path(
        ".artifacts/phase3b_active_guard_probe_anchor124_300s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
    Path(
        ".artifacts/phase3b_active_guard_anchor125_base_300s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
)


def build_phase3b_active_guard_residual_surface(
    project_root: Path,
    *,
    protocol_audit_path: Optional[Path] = None,
    family_bound_audit_path: Optional[Path] = None,
    active_guard_probe_paths: Optional[Sequence[Path]] = None,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    started = time.perf_counter()
    protocol_path = _resolve(project_root, protocol_audit_path or DEFAULT_PROTOCOL_AUDIT_PATH)
    family_bound_path = _resolve(
        project_root, family_bound_audit_path or DEFAULT_FAMILY_BOUND_AUDIT_PATH
    )
    probe_paths = [
        _resolve(project_root, path)
        for path in (active_guard_probe_paths or DEFAULT_ACTIVE_GUARD_PROBE_PATHS)
    ]

    protocol_audit = _load_json(protocol_path)
    family_bound_audit = _load_json(family_bound_path)
    probe_payloads = [_load_json(path) for path in probe_paths]
    protocol_summary = _protocol_summary(protocol_audit, family_bound_audit)
    probe_summary = _probe_summary(probe_payloads, probe_paths, project_root)
    relationship = _relationship_summary(protocol_summary, probe_summary)
    status = _status(relationship, protocol_audit, probe_payloads)

    report: dict[str, Any] = {
        "metadata": {
            "source": ACTIVE_GUARD_RESIDUAL_SURFACE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_artifact_synthesis",
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
        },
        "paths": {
            "project_root": _display_path(project_root, project_root),
            "protocol_target_channel_slot_audit": _display_path(project_root, protocol_path),
            "family_bound_audit": _display_path(project_root, family_bound_path),
            "active_guard_probe_paths": [
                _display_path(project_root, path) for path in probe_paths
            ],
        },
        "status": status,
        "protocol_surface": protocol_summary,
        "active_guard_probe_summary": probe_summary,
        "relationship": relationship,
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }
    report["checks"] = _checks(report, protocol_audit, family_bound_audit, probe_payloads)
    return report


def render_phase3b_active_guard_residual_surface_markdown(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    protocol = _mapping(report.get("protocol_surface"))
    probes = _mapping(report.get("active_guard_probe_summary"))
    relation = _mapping(report.get("relationship"))
    lines = [
        "# Phase 3B ActiveGuard Residual Surface",
        "",
        "- Diagnostic semantics: no_solve_artifact_synthesis",
        f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
        f"- proof_source: {bool(_mapping(report.get('metadata')).get('proof_source', True))}",
        f"- candidate_elimination_claim: {bool(_mapping(report.get('metadata')).get('candidate_elimination_claim', True))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Probe Stability",
        "",
        f"- Probe count: {probes.get('probe_count')}",
        f"- All probes UNKNOWN with search progress: {probes.get('all_unknown_with_search_progress')}",
        f"- Zero-branch UNKNOWN count: {probes.get('zero_branch_unknown_count')}",
        "",
        "| Anchor | Seed | Status | Branches | Conflicts | Deterministic Time |",
        "| --- | ---: | --- | ---: | ---: | ---: |",
    ]
    for row in list(probes.get("entries", [])):
        if isinstance(row, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(row.get("anchor_idx")),
                        _cell(row.get("random_seed")),
                        _cell(row.get("status")),
                        _cell(row.get("branches")),
                        _cell(row.get("conflicts")),
                        _cell(row.get("deterministic_time")),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Protocol Surface",
            "",
            f"- Mapped protocol slots: {protocol.get('mapped_protocol_slot_count')}",
            f"- Mapping matches artifact counts: {protocol.get('mapping_matches_artifact_counts')}",
            f"- Family bound present: {protocol.get('family_bound_present')}",
            f"- Family bound source: {protocol.get('family_bound_source')}",
            f"- Family bound audit consistent: {protocol.get('family_bound_audit_all_bounds_consistent')}",
            f"- Family bound focus: {protocol.get('family_bound_focus')}",
            f"- Missing family-bound anchors: {relation.get('missing_family_bound_anchors')}",
            f"- Block X constraints: {_mapping(protocol.get('block_xy_surface')).get('block_x_constraint_count')}",
            f"- Block Y constraints: {_mapping(protocol.get('block_xy_surface')).get('block_y_constraint_count')}",
            f"- Block XY constraints: {_mapping(protocol.get('block_xy_surface')).get('block_xy_constraint_count')}",
            "",
            "## Relationship",
            "",
            f"- Classification: {relation.get('classification')}",
            f"- Direct proto edge: {relation.get('direct_proto_edge')}",
            f"- Shared power-pole slot surface: {relation.get('shared_power_pole_slot_surface')}",
            f"- Recommended next action: {relation.get('recommended_next_action')}",
            f"- Safe formulation direction: {relation.get('safe_formulation_direction')}",
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(check.get("check_id")),
                        _cell(check.get("status")),
                        _cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_active_guard_residual_surface_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    protocol = _mapping(report.get("protocol_surface"))
    probes = _mapping(report.get("active_guard_probe_summary"))
    relation = _mapping(report.get("relationship"))
    block_xy = _mapping(protocol.get("block_xy_surface"))
    return "\n".join(
        [
            "phase3b active-guard residual surface",
            "diagnostic_semantics=no_solve_artifact_synthesis",
            f"solver_invoked={bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
            f"proof_source={bool(_mapping(report.get('metadata')).get('proof_source', True))}",
            f"candidate_elimination_claim={bool(_mapping(report.get('metadata')).get('candidate_elimination_claim', True))}",
            f"outcome={status.get('outcome')}",
            f"probe_count={probes.get('probe_count')}",
            f"all_unknown_with_search_progress={probes.get('all_unknown_with_search_progress')}",
            f"zero_branch_unknown_count={probes.get('zero_branch_unknown_count')}",
            f"mapped_protocol_slot_count={protocol.get('mapped_protocol_slot_count')}",
            f"block_x_constraint_count={block_xy.get('block_x_constraint_count')}",
            f"block_y_constraint_count={block_xy.get('block_y_constraint_count')}",
            f"block_xy_constraint_count={block_xy.get('block_xy_constraint_count')}",
            f"family_bound_focus={protocol.get('family_bound_focus')}",
            f"family_bound_source={protocol.get('family_bound_source')}",
            f"family_bound_audit_all_bounds_consistent={protocol.get('family_bound_audit_all_bounds_consistent')}",
            f"missing_family_bound_anchors={relation.get('missing_family_bound_anchors')}",
            f"classification={relation.get('classification')}",
            f"direct_proto_edge={relation.get('direct_proto_edge')}",
            f"shared_power_pole_slot_surface={relation.get('shared_power_pole_slot_surface')}",
            f"recommended_next_action={relation.get('recommended_next_action')}",
        ]
    ) + "\n"


def _protocol_summary(
    protocol_audit: Mapping[str, Any],
    family_bound_audit: Mapping[str, Any],
) -> dict[str, Any]:
    summary = _mapping(protocol_audit.get("summary"))
    target = _mapping(protocol_audit.get("target_channel_map"))
    by_token = _mapping(target.get("by_target_token"))
    family_bounds = _mapping(protocol_audit.get("family_bounds"))
    comparison = _mapping(protocol_audit.get("comparison"))
    protocol_focus = _family_bound_focus(family_bounds)
    audit_focus = _family_bound_focus_from_audit(family_bound_audit)
    focus = audit_focus or protocol_focus
    active_x = _mapping(by_token.get("active_x"))
    active_y = _mapping(by_token.get("active_y"))
    active_xy = _mapping(by_token.get("active_xy"))
    return {
        "evaluated": bool(summary.get("evaluated", False)),
        "diagnostic_signal": summary.get("diagnostic_signal"),
        "next_probe_hint": summary.get("next_probe_hint"),
        "mapped_protocol_slot_count": int(summary.get("mapped_protocol_slot_count", 0) or 0),
        "mapping_matches_artifact_counts": bool(
            summary.get("mapping_matches_artifact_counts", False)
        ),
        "family_bound_present": bool(summary.get("family_bounds_present", False)),
        "family_bound_focus": focus,
        "family_bound_source": (
            "family_bound_audit"
            if audit_focus
            else ("protocol_target_channel_slot_audit" if protocol_focus else "none")
        ),
        "family_bound_audit_status": _mapping(family_bound_audit.get("status")).get("outcome"),
        "family_bound_audit_all_bounds_consistent": _mapping(
            family_bound_audit.get("summary")
        ).get("all_bounds_consistent"),
        "family_bound_anchor_keys": sorted(str(key) for key in focus.keys()),
        "block_xy_surface": {
            "block_x_constraint_count": int(active_x.get("constraint_count", 0) or 0),
            "block_y_constraint_count": int(active_y.get("constraint_count", 0) or 0),
            "block_xy_constraint_count": int(active_xy.get("constraint_count", 0) or 0),
            "block_x_unique_slot_count": int(active_x.get("unique_slot_count", 0) or 0),
            "block_y_unique_slot_count": int(active_y.get("unique_slot_count", 0) or 0),
            "block_xy_unique_slot_count": int(active_xy.get("unique_slot_count", 0) or 0),
        },
        "comparison_interpretation": comparison.get("interpretation"),
        "comparison_mapping_matches_artifact_counts": bool(
            comparison.get("mapping_matches_artifact_counts", False)
        ),
    }


def _probe_summary(
    probe_payloads: Sequence[Mapping[str, Any]],
    probe_paths: Sequence[Path],
    project_root: Path,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    campaign_state_unchanged = True
    for payload, path in zip(probe_payloads, probe_paths):
        campaign_state_unchanged = campaign_state_unchanged and bool(
            payload.get("campaign_state_unchanged", False)
        )
        for entry in list(_mapping(payload.get("reduction")).get("entries", [])):
            if not isinstance(entry, Mapping):
                continue
            profile = _mapping(entry.get("solver_parameter_profile"))
            branches = int(entry.get("branches", 0) or 0)
            conflicts = int(entry.get("conflicts", 0) or 0)
            status = str(entry.get("status", ""))
            entries.append(
                {
                    "source_path": _display_path(project_root, path),
                    "anchor_idx": entry.get("anchor_idx"),
                    "random_seed": profile.get("random_seed"),
                    "status": status,
                    "branches": branches,
                    "conflicts": conflicts,
                    "wall_time": entry.get("wall_time"),
                    "deterministic_time": entry.get("deterministic_time"),
                    "search_progress": bool(branches > 0 or conflicts > 0),
                }
            )
    zero_branch_unknown = [
        row
        for row in entries
        if str(row.get("status")) == "UNKNOWN"
        and int(row.get("branches", 0) or 0) == 0
        and int(row.get("conflicts", 0) or 0) == 0
    ]
    return {
        "probe_count": int(len(entries)),
        "entries": entries,
        "campaign_state_unchanged": bool(campaign_state_unchanged),
        "all_unknown_with_search_progress": bool(
            entries
            and all(
                str(row.get("status")) == "UNKNOWN"
                and bool(row.get("search_progress", False))
                for row in entries
            )
        ),
        "zero_branch_unknown_count": int(len(zero_branch_unknown)),
        "max_conflicts": max([int(row.get("conflicts", 0) or 0) for row in entries] or [0]),
        "max_branches": max([int(row.get("branches", 0) or 0) for row in entries] or [0]),
    }


def _relationship_summary(
    protocol_summary: Mapping[str, Any],
    probe_summary: Mapping[str, Any],
) -> dict[str, Any]:
    block_xy = _mapping(protocol_summary.get("block_xy_surface"))
    has_block_xy = int(block_xy.get("block_xy_constraint_count", 0) or 0) > 0
    has_family_bound = bool(protocol_summary.get("family_bound_present", False))
    stable_search = bool(probe_summary.get("all_unknown_with_search_progress", False))
    no_zero_branch = int(probe_summary.get("zero_branch_unknown_count", 0) or 0) == 0
    mapping_caveat = not bool(protocol_summary.get("mapping_matches_artifact_counts", False))
    probe_anchor_keys = {
        str(row.get("anchor_idx"))
        for row in list(probe_summary.get("entries", []))
        if _mapping(row).get("anchor_idx") is not None
    }
    family_bound_anchor_keys = {
        str(key) for key in list(protocol_summary.get("family_bound_anchor_keys", []))
    }
    missing_family_bound_anchors = sorted(probe_anchor_keys - family_bound_anchor_keys)
    if stable_search and no_zero_branch and has_block_xy and has_family_bound:
        classification = "stable_search_progress_with_family009_bound_and_surviving_block_xy_surface"
        recommended = "inspect_family009_bound_delta_against_protocol_block_xy_channels"
    elif stable_search and no_zero_branch:
        classification = "stable_search_progress_without_terminal"
        recommended = "compare_residual_surfaces_before_more_solver_time"
    else:
        classification = "residual_surface_incomplete_or_stale"
        recommended = "refresh_missing_or_inconsistent_artifacts"
    return {
        "classification": classification,
        "recommended_next_action": recommended,
        "stable_search_progress": bool(stable_search),
        "no_zero_branch_unknown": bool(no_zero_branch),
        "has_protocol_block_xy_surface": bool(has_block_xy),
        "has_family_bound_delta": bool(has_family_bound),
        "direct_proto_edge": False,
        "shared_power_pole_slot_surface": bool(has_block_xy and has_family_bound),
        "missing_family_bound_anchors": missing_family_bound_anchors,
        "mapping_caveat": bool(mapping_caveat),
        "safe_formulation_direction": (
            "Do not delete surviving block x/y channels as a proof-preserving fix. "
            "If formulation work follows, make it default-off and equivalence-tested, "
            "with family lookup/count semantics unchanged."
        ),
        "interpretation": (
            "ActiveGuard converts the prior zero-branch failure into stable search, "
            "but the remaining protocol block x/y channel surface and family_009 "
            "bound delta should be analyzed before more production-facing runs."
        ),
    }


def _status(
    relationship: Mapping[str, Any],
    protocol_audit: Mapping[str, Any],
    probe_payloads: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    present = bool(protocol_audit) and all(bool(payload) for payload in probe_payloads)
    evaluated = present and bool(relationship.get("stable_search_progress", False))
    if evaluated:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "active_guard_residual_surface_synthesized",
            "recommendation": relationship.get("recommended_next_action"),
        }
    return {
        "completed": True,
        "evaluated": False,
        "outcome": "active_guard_residual_surface_incomplete",
        "recommendation": "refresh missing or stale input artifacts before acting.",
    }


def _checks(
    report: Mapping[str, Any],
    protocol_audit: Mapping[str, Any],
    family_bound_audit: Mapping[str, Any],
    probe_payloads: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    metadata = _mapping(report.get("metadata"))
    protocol = _mapping(report.get("protocol_surface"))
    probes = _mapping(report.get("active_guard_probe_summary"))
    relation = _mapping(report.get("relationship"))
    return [
        _check("solver_not_invoked", "pass" if not bool(metadata.get("solver_invoked", True)) else "fail", "solver_invoked=false"),
        _check("proof_source_false", "pass" if not bool(metadata.get("proof_source", True)) else "fail", "proof_source=false"),
        _check("protocol_audit_present", "pass" if bool(protocol_audit) else "fail", f"present={bool(protocol_audit)}"),
        _check("family_bound_audit_present", "pass" if bool(family_bound_audit) else "skipped", f"present={bool(family_bound_audit)}"),
        _check(
            "family_bound_audit_consistent",
            "pass"
            if bool(_mapping(family_bound_audit.get("summary")).get("all_bounds_consistent", False))
            else ("skipped" if not family_bound_audit else "fail"),
            f"all_bounds_consistent={_mapping(family_bound_audit.get('summary')).get('all_bounds_consistent')}",
        ),
        _check("probe_artifacts_present", "pass" if all(bool(payload) for payload in probe_payloads) else "fail", f"count={sum(1 for payload in probe_payloads if bool(payload))}/{len(probe_payloads)}"),
        _check("probes_have_search_progress", "pass" if bool(probes.get("all_unknown_with_search_progress", False)) else "fail", f"zero_branch_unknown_count={probes.get('zero_branch_unknown_count')}"),
        _check("campaign_state_unchanged", "pass" if bool(probes.get("campaign_state_unchanged", False)) else "fail", f"campaign_state_unchanged={probes.get('campaign_state_unchanged')}"),
        _check("protocol_block_xy_surface_present", "pass" if bool(relation.get("has_protocol_block_xy_surface", False)) else "fail", str(_mapping(protocol.get("block_xy_surface")))),
        _check("family_bound_delta_present", "pass" if bool(relation.get("has_family_bound_delta", False)) else "fail", str(protocol.get("family_bound_focus"))),
        _check("mapping_caveat_recorded", "pass" if bool(relation.get("mapping_caveat", False)) else "pass", f"mapping_caveat={relation.get('mapping_caveat')}"),
    ]


def _family_bound_focus(family_bounds: Mapping[str, Any]) -> dict[str, Any]:
    focus: dict[str, Any] = {}
    for anchor_key, families in sorted(_mapping(family_bounds).items()):
        family = _mapping(_mapping(families).get("family_009"))
        if family:
            focus[str(anchor_key)] = {
                "family_name": family.get("family_name"),
                "implied_upper_when_anchor_active": family.get("implied_upper_when_anchor_active"),
                "family_domain_upper": family.get("family_domain_upper"),
                "upper_reduction_when_anchor_active": family.get("upper_reduction_when_anchor_active"),
            }
    return focus


def _family_bound_focus_from_audit(family_bound_audit: Mapping[str, Any]) -> dict[str, Any]:
    focus: dict[str, Any] = {}
    for audit in list(family_bound_audit.get("audits", [])):
        if not isinstance(audit, Mapping):
            continue
        if not bool(audit.get("present", False)):
            continue
        try:
            anchor_key = str(int(audit.get("anchor_idx")))
        except Exception:
            continue
        derivation = _mapping(audit.get("derivation"))
        proto = _mapping(audit.get("proto_constraint"))
        family_name = str(audit.get("target_power_family") or "family_009")
        if family_name != "family_009":
            continue
        global_upper = _number_or_none(derivation.get("global_upper_bound"))
        derived_upper = _number_or_none(derivation.get("derived_conditioned_upper_bound"))
        upper_reduction = None
        if global_upper is not None and derived_upper is not None:
            upper_reduction = float(global_upper) - float(derived_upper)
        focus[anchor_key] = {
            "family_name": family_name,
            "implied_upper_when_anchor_active": derived_upper,
            "family_domain_upper": global_upper,
            "upper_reduction_when_anchor_active": upper_reduction,
            "blocked_family_pose_count": derivation.get("blocked_family_pose_count"),
            "available_family_pose_count": derivation.get("available_family_pose_count"),
            "domain_conditioned_upper_bound": derivation.get("domain_conditioned_upper_bound"),
            "proto_implied_conditioned_upper_bound": proto.get(
                "implied_conditioned_upper_bound"
            ),
            "matching_constraint_count": proto.get("matching_constraint_count"),
            "bounds_consistent": bool(audit.get("bounds_consistent", False)),
            "finding": audit.get("finding"),
        }
    return dict(sorted(focus.items()))


def _number_or_none(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _resolve(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return project_root / path


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        import json

        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
