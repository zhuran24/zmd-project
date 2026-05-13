from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import now_iso
from src.search.phase3b_forced_anchor_master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
    _build_exact_overlay,
    _candidate_ghost_rect,
    _check,
    _display_path,
    _load_json_mapping,
    _mapping,
    _resolve_path,
    _selected_anchor_indices,
)

ANCHOR_DOMAIN_INVENTORY_SOURCE = "phase3b_anchor_domain_inventory_v1"


def build_phase3b_anchor_domain_inventory(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    sample_limit: int = 3,
    anchor_indices: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    candidate_key = str(candidate)
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path if campaign_state_path is not None else DEFAULT_CAMPAIGN_STATE_PATH,
    )
    state, state_error = _load_json_mapping(campaign_path)
    candidates = _mapping(state.get("candidates")) if state else {}
    record = _mapping(candidates.get(candidate_key))
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
    ghost_rect = _candidate_ghost_rect(candidate_key, record)
    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Anchor domain inventory has not run.",
    }
    timing: Dict[str, float] = {}
    model_error: Optional[str] = None
    anchor_reports: list[Dict[str, Any]] = []
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before anchor domain inventory.",
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
                "outcome": "anchor_samples_missing",
                "recommendation": "No anchor samples selected; rerun B5A with failed-anchor sampling enabled.",
            }
        )
    else:
        try:
            overlay_started = time.perf_counter()
            model, _base_proto = _build_exact_overlay(
                project_root,
                ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                master_search_profile=master_search_profile,
            )
            timing["overlay_build_seconds"] = float(time.perf_counter() - overlay_started)
            for anchor_idx in selected_anchor_indices:
                if int(anchor_idx) >= len(getattr(model, "_ghost_domains", [])):
                    anchor_reports.append(
                        {
                            "anchor_idx": int(anchor_idx),
                            "present": False,
                            "skip_reason": "anchor_not_in_model_ghost_domains",
                        }
                    )
                    continue
                anchor_reports.append(_anchor_domain_report(model, int(anchor_idx)))
            status.update(_status_from_anchor_reports(anchor_reports))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Anchor domain inventory failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    return {
        "metadata": {
            "source": ANCHOR_DOMAIN_INVENTORY_SOURCE,
            "generated_at": now_iso(),
        },
        "paths": {
            "project_root": str(project_root),
            "campaign_state": _display_path(project_root, campaign_path),
        },
        "candidate": {
            "key": candidate_key,
            "ghost_rect": ghost_rect,
            "campaign_present": state is not None and state_error is None,
            "campaign_load_error": state_error,
            "candidate_present": bool(record),
            "campaign_status": record.get("status") if record else None,
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "sample_limit": int(sample_limit),
            "selected_anchor_indices": [int(idx) for idx in selected_anchor_indices],
        },
        "status": status,
        "anchors": anchor_reports,
        "timing": timing,
        "model_error": model_error,
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            status=status,
            model_error=model_error,
        ),
    }


def render_phase3b_anchor_domain_inventory_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    lines = [
        "# Phase 3B Anchor Domain Inventory",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Evaluated: {bool(status.get('evaluated', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Anchors",
        "",
        "| Anchor | Mandatory Survivors | Optional Survivors | Tightest Mandatory | Power Families |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in list(report.get("anchors", [])):
        if not isinstance(entry, Mapping):
            continue
        summary = _mapping(entry.get("summary"))
        tightest = _mapping(entry.get("tightest_mandatory_group"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("anchor_idx")),
                    _markdown_cell(summary.get("mandatory_surviving_total")),
                    _markdown_cell(summary.get("optional_surviving_total")),
                    _markdown_cell(
                        f"{tightest.get('group_id')}:{tightest.get('surviving_count')}"
                    ),
                    _markdown_cell(
                        _mapping(entry.get("power_pole_family_bounds")).get("count")
                    ),
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


def render_phase3b_anchor_domain_inventory_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    lines = [
        "Phase 3B anchor domain inventory",
        f"candidate={candidate.get('key')}",
        f"evaluated={bool(status.get('evaluated', False))}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
    ]
    for entry in list(report.get("anchors", [])):
        if not isinstance(entry, Mapping):
            continue
        summary = _mapping(entry.get("summary"))
        tightest = _mapping(entry.get("tightest_mandatory_group"))
        lines.append(
            "anchor "
            f"idx={entry.get('anchor_idx')} "
            f"domain={entry.get('anchor')} "
            f"mandatory_surviving_total={summary.get('mandatory_surviving_total')} "
            f"optional_surviving_total={summary.get('optional_surviving_total')} "
            f"tightest_group={tightest.get('group_id')} "
            f"tightest_surviving={tightest.get('surviving_count')} "
            f"power_family_bound_count={_mapping(entry.get('power_pole_family_bounds')).get('count')}"
        )
        for group in list(entry.get("mandatory_groups", []))[:8]:
            if isinstance(group, Mapping):
                lines.append(
                    "mandatory_group "
                    f"anchor={entry.get('anchor_idx')} "
                    f"group={group.get('group_id')} "
                    f"required={group.get('required_count')} "
                    f"surviving={group.get('surviving_count')} "
                    f"ratio={group.get('survivor_to_required_ratio')}"
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


def _anchor_domain_report(model: Any, anchor_idx: int) -> Dict[str, Any]:
    domain = dict(model._ghost_domains[int(anchor_idx)])
    blocked_cells = {
        (int(cell[0]), int(cell[1]))
        for cell in list(domain.get("cells", []))
    }
    candidates_by_group = {
        str(group["group_id"]): model._candidate_pose_indices_for_group(group)
        for group in list(getattr(model, "_mandatory_groups", []))
    }
    mandatory_groups = [
        _mandatory_group_domain_entry(
            model,
            group,
            candidates_by_group.get(str(group["group_id"]), []),
            blocked_cells,
        )
        for group in list(getattr(model, "_mandatory_groups", []))
    ]
    mandatory_groups = sorted(
        mandatory_groups,
        key=lambda entry: (
            float(entry["survivor_to_required_ratio"]),
            int(entry["surviving_count"]),
            str(entry["group_id"]),
        ),
    )
    optionals = _optional_domain_entries(model, blocked_cells)
    tightest = dict(mandatory_groups[0]) if mandatory_groups else {}
    return {
        "anchor_idx": int(anchor_idx),
        "present": True,
        "anchor": domain.get("anchor"),
        "cell_count": len(blocked_cells),
        "summary": {
            "mandatory_group_count": len(mandatory_groups),
            "mandatory_required_total": sum(
                int(entry.get("required_count", 0)) for entry in mandatory_groups
            ),
            "mandatory_candidate_total": sum(
                int(entry.get("candidate_count", 0)) for entry in mandatory_groups
            ),
            "mandatory_surviving_total": sum(
                int(entry.get("surviving_count", 0)) for entry in mandatory_groups
            ),
            "optional_template_count": len(optionals),
            "optional_candidate_total": sum(
                int(entry.get("candidate_count", 0)) for entry in optionals
            ),
            "optional_surviving_total": sum(
                int(entry.get("surviving_count", 0)) for entry in optionals
            ),
        },
        "tightest_mandatory_group": tightest,
        "mandatory_groups": mandatory_groups,
        "optional_templates": optionals,
        "power_pole_family_bounds": _power_pole_family_bounds(domain),
        "screened_by_power_capacity": list(domain.get("screened_by_power_capacity", [])),
    }


def _mandatory_group_domain_entry(
    model: Any,
    group: Mapping[str, Any],
    candidate_indices: Sequence[int],
    blocked_cells: set[tuple[int, int]],
) -> Dict[str, Any]:
    group_id = str(group.get("group_id"))
    tpl = str(group.get("facility_type"))
    required_count = int(group.get("count", len(group.get("instance_ids", []))))
    candidate_indices = [int(idx) for idx in candidate_indices]
    surviving = [
        int(idx)
        for idx in candidate_indices
        if blocked_cells.isdisjoint(model._pose_cells(tpl, int(idx)))
    ]
    slot_count = len(
        getattr(getattr(model, "_coordinate_delegate", None), "mandatory_slots", {}).get(
            group_id,
            [],
        )
    )
    mode_rect_domain_count = len(
        getattr(
            getattr(model, "_coordinate_delegate", None),
            "_mandatory_group_mode_rect_domains",
            {},
        ).get(group_id, {})
    )
    bucket_count = len(
        getattr(
            getattr(model, "_coordinate_delegate", None),
            "_mandatory_group_bucket_pose_counts",
            {},
        ).get(group_id, {})
    )
    return {
        "group_id": group_id,
        "facility_type": tpl,
        "required_count": int(required_count),
        "slot_count": int(slot_count),
        "candidate_count": len(candidate_indices),
        "surviving_count": len(surviving),
        "blocked_count": len(candidate_indices) - len(surviving),
        "survivor_to_required_ratio": _ratio(len(surviving), required_count),
        "mode_rect_domain_count": int(mode_rect_domain_count),
        "signature_bucket_count": int(bucket_count),
    }


def _optional_domain_entries(
    model: Any,
    blocked_cells: set[tuple[int, int]],
) -> list[Dict[str, Any]]:
    entries: list[Dict[str, Any]] = []
    delegate = getattr(model, "_coordinate_delegate", None)
    required_counts = dict(getattr(model, "_exact_required_pose_optional_counts", {}))
    residual_slots = getattr(delegate, "residual_optional_slots", {}) if delegate else {}
    optional_templates = set(str(tpl) for tpl in required_counts)
    optional_templates.update(str(tpl) for tpl in residual_slots)
    for tpl in sorted(optional_templates):
        pose_indices = list(range(len(getattr(model, "facility_pools", {}).get(tpl, []))))
        surviving = [
            int(idx)
            for idx in pose_indices
            if blocked_cells.isdisjoint(model._pose_cells(str(tpl), int(idx)))
        ]
        required_count = int(required_counts.get(str(tpl), 0))
        residual_slot_count = len(residual_slots.get(str(tpl), []))
        entries.append(
            {
                "template": str(tpl),
                "required_count": int(required_count),
                "residual_slot_count": int(residual_slot_count),
                "candidate_count": len(pose_indices),
                "surviving_count": len(surviving),
                "blocked_count": len(pose_indices) - len(surviving),
                "survivor_to_required_ratio": _ratio(
                    len(surviving),
                    required_count if required_count > 0 else residual_slot_count,
                ),
            }
        )
    return entries


def _power_pole_family_bounds(domain: Mapping[str, Any]) -> Dict[str, Any]:
    bounds = _mapping(domain.get("conditioned_power_pole_family_upper_bounds"))
    values = [int(value) for value in bounds.values()]
    return {
        "count": len(bounds),
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "bounds": dict(bounds),
    }


def _ratio(numerator: int, denominator: int) -> float:
    if int(denominator) <= 0:
        return float("inf")
    return float(int(numerator) / int(denominator))


def _status_from_anchor_reports(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not entries:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_anchors_evaluated",
            "recommendation": "No anchors were evaluated.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "anchor_domain_inventory_built",
        "recommendation": "Compare survivor totals and tightest mandatory groups across easy and hard anchors.",
    }


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
    selected_anchor_count: int,
    status: Mapping[str, Any],
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
            "anchor_domain_inventory_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "skipped",
            str(status.get("outcome")),
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
