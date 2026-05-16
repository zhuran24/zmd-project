from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.search.exact_campaign import now_iso

POWER_COVERAGE_ANCHOR_DELTA_SOURCE = "phase3b_power_coverage_anchor_delta_v1"
ANCHOR_DOMAIN_INVENTORY_SOURCE = "phase3b_anchor_domain_inventory_v1"
DEFAULT_ANCHOR_DOMAIN_INVENTORY_PATH = Path(
    ".artifacts/phase3b_anchor_domain_inventory_67x13_cap112_v3/"
    "anchor_domain_inventory_67x13_anchors118_119.json"
)


def build_phase3b_power_coverage_anchor_delta(
    project_root: Path,
    *,
    anchor_domain_inventory_path: Optional[Path] = None,
    baseline_anchor_idx: int = 118,
    comparison_anchor_idx: int = 119,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    inventory_path = _resolve_path(
        project_root,
        anchor_domain_inventory_path
        if anchor_domain_inventory_path is not None
        else DEFAULT_ANCHOR_DOMAIN_INVENTORY_PATH,
    )
    inventory, load_error = _load_json_mapping(inventory_path)
    metadata = _mapping(inventory.get("metadata")) if inventory else {}
    candidate = _mapping(inventory.get("candidate")) if inventory else {}
    anchors = [
        dict(entry)
        for entry in list(inventory.get("anchors", []) if inventory else [])
        if isinstance(entry, Mapping)
    ]
    baseline = _anchor_by_idx(anchors, baseline_anchor_idx)
    comparison = _anchor_by_idx(anchors, comparison_anchor_idx)
    delta = _delta_payload(baseline, comparison)
    checks = [
        _check(
            "anchor_domain_inventory_present",
            "pass" if inventory is not None and load_error is None else "fail",
            "anchor-domain inventory loaded"
            if inventory is not None and load_error is None
            else load_error or f"missing:{_display_path(project_root, inventory_path)}",
        ),
        _check(
            "anchor_domain_inventory_schema",
            "pass" if metadata.get("source") == ANCHOR_DOMAIN_INVENTORY_SOURCE else "fail",
            "supported anchor-domain inventory schema"
            if metadata.get("source") == ANCHOR_DOMAIN_INVENTORY_SOURCE
            else f"unsupported source:{metadata.get('source')}",
        ),
        _check(
            "baseline_anchor_present",
            "pass" if baseline else "fail",
            f"anchor={int(baseline_anchor_idx)}",
        ),
        _check(
            "comparison_anchor_present",
            "pass" if comparison else "fail",
            f"anchor={int(comparison_anchor_idx)}",
        ),
    ]
    return {
        "metadata": {
            "source": POWER_COVERAGE_ANCHOR_DELTA_SOURCE,
            "generated_at": now_iso(),
        },
        "paths": {
            "project_root": str(project_root),
            "anchor_domain_inventory": _display_path(project_root, inventory_path),
        },
        "candidate": dict(candidate),
        "anchors": {
            "baseline_anchor_idx": int(baseline_anchor_idx),
            "comparison_anchor_idx": int(comparison_anchor_idx),
            "baseline": _anchor_summary(baseline),
            "comparison": _anchor_summary(comparison),
        },
        "delta": delta,
        "recommendation": _recommendation(delta),
        "checks": checks,
    }


def render_phase3b_power_coverage_anchor_delta_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    delta = _mapping(report.get("delta"))
    lines = [
        "# Phase 3B Power-Coverage Anchor Delta",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Baseline anchor: {_mapping(report.get('anchors')).get('baseline_anchor_idx')}",
        f"- Comparison anchor: {_mapping(report.get('anchors')).get('comparison_anchor_idx')}",
        f"- Power family changed count: {delta.get('power_family_changed_count', 0)}",
        f"- Power family positive delta sum: {delta.get('power_family_positive_delta_sum', 0)}",
        f"- Power family negative delta sum: {delta.get('power_family_negative_delta_sum', 0)}",
        f"- Mandatory survivor delta: {delta.get('mandatory_surviving_delta')}",
        f"- Optional survivor delta: {delta.get('optional_surviving_delta')}",
        f"- Diagnostic findings: {delta.get('diagnostic_findings', [])}",
        f"- Recommendation: {report.get('recommendation')}",
        "",
        "## Top Power-Family Deltas",
        "",
        "| Family | Baseline | Comparison | Delta |",
        "| --- | --- | --- | --- |",
    ]
    for entry in list(delta.get("top_power_family_deltas", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("family")),
                        _markdown_cell(entry.get("baseline")),
                        _markdown_cell(entry.get("comparison")),
                        _markdown_cell(entry.get("delta")),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Top Mandatory Group Deltas",
            "",
            "| Group | Facility | Baseline | Comparison | Delta |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for entry in list(delta.get("top_mandatory_group_deltas", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("group_id")),
                        _markdown_cell(entry.get("facility_type")),
                        _markdown_cell(entry.get("baseline_surviving_count")),
                        _markdown_cell(entry.get("comparison_surviving_count")),
                        _markdown_cell(entry.get("surviving_delta")),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Optional Template Deltas",
            "",
            "| Template | Baseline | Comparison | Delta |",
            "| --- | --- | --- | --- |",
        ]
    )
    for entry in list(delta.get("optional_template_deltas", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("template")),
                        _markdown_cell(entry.get("baseline_surviving_count")),
                        _markdown_cell(entry.get("comparison_surviving_count")),
                        _markdown_cell(entry.get("surviving_delta")),
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


def render_phase3b_power_coverage_anchor_delta_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    anchors = _mapping(report.get("anchors"))
    delta = _mapping(report.get("delta"))
    lines = [
        "Phase 3B power-coverage anchor delta",
        f"candidate={candidate.get('key')}",
        f"baseline_anchor={anchors.get('baseline_anchor_idx')}",
        f"comparison_anchor={anchors.get('comparison_anchor_idx')}",
        f"power_family_changed_count={delta.get('power_family_changed_count', 0)}",
        f"power_family_positive_delta_sum={delta.get('power_family_positive_delta_sum', 0)}",
        f"power_family_negative_delta_sum={delta.get('power_family_negative_delta_sum', 0)}",
        f"mandatory_surviving_delta={delta.get('mandatory_surviving_delta')}",
        f"optional_surviving_delta={delta.get('optional_surviving_delta')}",
        f"recommendation={report.get('recommendation')}",
    ]
    for finding in list(delta.get("diagnostic_findings", [])):
        lines.append(f"diagnostic_finding={finding}")
    for entry in list(delta.get("top_power_family_deltas", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "power_family_delta "
                f"family={entry.get('family')} "
                f"baseline={entry.get('baseline')} "
                f"comparison={entry.get('comparison')} "
                f"delta={entry.get('delta')}"
            )
    for entry in list(delta.get("top_mandatory_group_deltas", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "mandatory_group_delta "
                f"group={entry.get('group_id')} "
                f"facility={entry.get('facility_type')} "
                f"baseline={entry.get('baseline_surviving_count')} "
                f"comparison={entry.get('comparison_surviving_count')} "
                f"delta={entry.get('surviving_delta')}"
            )
    for entry in list(delta.get("optional_template_deltas", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "optional_template_delta "
                f"template={entry.get('template')} "
                f"baseline={entry.get('baseline_surviving_count')} "
                f"comparison={entry.get('comparison_surviving_count')} "
                f"delta={entry.get('surviving_delta')}"
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


def _anchor_by_idx(anchors: list[Mapping[str, Any]], anchor_idx: int) -> Mapping[str, Any]:
    for entry in anchors:
        if int(entry.get("anchor_idx", -1)) == int(anchor_idx):
            return entry
    return {}


def _anchor_summary(anchor: Mapping[str, Any]) -> Dict[str, Any]:
    summary = _mapping(anchor.get("summary"))
    power = _mapping(anchor.get("power_pole_family_bounds"))
    return {
        "present": bool(anchor),
        "anchor_idx": anchor.get("anchor_idx"),
        "anchor": anchor.get("anchor"),
        "mandatory_surviving_total": summary.get("mandatory_surviving_total"),
        "optional_surviving_total": summary.get("optional_surviving_total"),
        "power_family_count": power.get("count"),
    }


def _delta_payload(
    baseline: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> Dict[str, Any]:
    if not baseline or not comparison:
        return {
            "present": False,
            "power_family_changed_count": 0,
            "top_power_family_deltas": [],
            "top_mandatory_group_deltas": [],
            "optional_template_deltas": [],
            "diagnostic_findings": [],
        }
    baseline_summary = _mapping(baseline.get("summary"))
    comparison_summary = _mapping(comparison.get("summary"))
    baseline_bounds = _mapping(_mapping(baseline.get("power_pole_family_bounds")).get("bounds"))
    comparison_bounds = _mapping(
        _mapping(comparison.get("power_pole_family_bounds")).get("bounds")
    )
    deltas = []
    for family in sorted(set(baseline_bounds.keys()) | set(comparison_bounds.keys())):
        before = int(baseline_bounds.get(family, 0))
        after = int(comparison_bounds.get(family, 0))
        delta = int(after - before)
        if delta:
            deltas.append(
                {
                    "family": str(family),
                    "baseline": before,
                    "comparison": after,
                    "delta": delta,
                }
            )
    deltas.sort(key=lambda entry: abs(int(entry["delta"])), reverse=True)
    positive_sum = sum(max(0, int(entry["delta"])) for entry in deltas)
    negative_sum = sum(min(0, int(entry["delta"])) for entry in deltas)
    mandatory_group_deltas = _mandatory_group_deltas(
        list(baseline.get("mandatory_groups", [])),
        list(comparison.get("mandatory_groups", [])),
    )
    optional_template_deltas = _optional_template_deltas(
        list(baseline.get("optional_templates", [])),
        list(comparison.get("optional_templates", [])),
    )
    tightest_shifted = _tightest_group_id(baseline) != _tightest_group_id(comparison)
    delta_payload = {
        "present": True,
        "mandatory_surviving_delta": _int_or_none(
            comparison_summary.get("mandatory_surviving_total")
        )
        - _int_or_none(baseline_summary.get("mandatory_surviving_total")),
        "optional_surviving_delta": _int_or_none(
            comparison_summary.get("optional_surviving_total")
        )
        - _int_or_none(baseline_summary.get("optional_surviving_total")),
        "power_family_changed_count": int(len(deltas)),
        "power_family_positive_delta_sum": int(positive_sum),
        "power_family_negative_delta_sum": int(negative_sum),
        "top_power_family_deltas": deltas[:12],
        "top_mandatory_group_deltas": mandatory_group_deltas[:12],
        "optional_template_deltas": optional_template_deltas,
        "tightest_mandatory_group_shifted": bool(tightest_shifted),
    }
    delta_payload["diagnostic_findings"] = _diagnostic_findings(delta_payload)
    return delta_payload


def _mandatory_group_deltas(
    baseline_groups: Sequence[Any],
    comparison_groups: Sequence[Any],
) -> list[Dict[str, Any]]:
    baseline_by_id = {
        str(_mapping(group).get("group_id")): _mapping(group)
        for group in baseline_groups
        if isinstance(group, Mapping) and _mapping(group).get("group_id") is not None
    }
    comparison_by_id = {
        str(_mapping(group).get("group_id")): _mapping(group)
        for group in comparison_groups
        if isinstance(group, Mapping) and _mapping(group).get("group_id") is not None
    }
    deltas: list[Dict[str, Any]] = []
    for group_id in sorted(set(baseline_by_id.keys()) | set(comparison_by_id.keys())):
        before = baseline_by_id.get(group_id, {})
        after = comparison_by_id.get(group_id, {})
        before_surviving = _int_or_none(before.get("surviving_count"))
        after_surviving = _int_or_none(after.get("surviving_count"))
        delta = int(after_surviving - before_surviving)
        if delta == 0:
            continue
        deltas.append(
            {
                "group_id": group_id,
                "facility_type": after.get("facility_type")
                or before.get("facility_type"),
                "required_count": _int_or_none(
                    after.get("required_count") if after else before.get("required_count")
                ),
                "baseline_surviving_count": int(before_surviving),
                "comparison_surviving_count": int(after_surviving),
                "surviving_delta": int(delta),
            }
        )
    deltas.sort(
        key=lambda entry: (
            -abs(int(entry["surviving_delta"])),
            str(entry["group_id"]),
        )
    )
    return deltas


def _optional_template_deltas(
    baseline_templates: Sequence[Any],
    comparison_templates: Sequence[Any],
) -> list[Dict[str, Any]]:
    baseline_by_template = {
        str(_mapping(entry).get("template")): _mapping(entry)
        for entry in baseline_templates
        if isinstance(entry, Mapping) and _mapping(entry).get("template") is not None
    }
    comparison_by_template = {
        str(_mapping(entry).get("template")): _mapping(entry)
        for entry in comparison_templates
        if isinstance(entry, Mapping) and _mapping(entry).get("template") is not None
    }
    deltas: list[Dict[str, Any]] = []
    for template in sorted(
        set(baseline_by_template.keys()) | set(comparison_by_template.keys())
    ):
        before = baseline_by_template.get(template, {})
        after = comparison_by_template.get(template, {})
        before_surviving = _int_or_none(before.get("surviving_count"))
        after_surviving = _int_or_none(after.get("surviving_count"))
        deltas.append(
            {
                "template": template,
                "required_count": _int_or_none(
                    after.get("required_count") if after else before.get("required_count")
                ),
                "residual_slot_count": _int_or_none(
                    after.get("residual_slot_count")
                    if after
                    else before.get("residual_slot_count")
                ),
                "baseline_surviving_count": int(before_surviving),
                "comparison_surviving_count": int(after_surviving),
                "surviving_delta": int(after_surviving - before_surviving),
            }
        )
    deltas.sort(key=lambda entry: str(entry["template"]))
    return deltas


def _tightest_group_id(anchor: Mapping[str, Any]) -> Optional[str]:
    group_id = _mapping(anchor.get("tightest_mandatory_group")).get("group_id")
    return str(group_id) if group_id is not None else None


def _diagnostic_findings(delta: Mapping[str, Any]) -> list[str]:
    findings: list[str] = []
    changed_count = int(delta.get("power_family_changed_count", 0))
    if changed_count > 0:
        findings.append("power_family_bounds_shift")
    if int(delta.get("power_family_positive_delta_sum", 0)) > 0:
        findings.append("some_power_family_bounds_loosen")
    if int(delta.get("power_family_negative_delta_sum", 0)) < 0:
        findings.append("some_power_family_bounds_tighten")
    if int(delta.get("mandatory_surviving_delta", 0)) < 0:
        findings.append("comparison_anchor_prunes_more_mandatory_placements")
    if int(delta.get("optional_surviving_delta", 0)) < 0:
        findings.append("comparison_anchor_prunes_more_optional_placements")
    if not bool(delta.get("tightest_mandatory_group_shifted", False)):
        findings.append("tightest_mandatory_group_stable")
    optional_by_template = {
        str(entry.get("template")): entry
        for entry in list(delta.get("optional_template_deltas", []))
        if isinstance(entry, Mapping)
    }
    power_pole = _mapping(optional_by_template.get("power_pole"))
    if changed_count > 0 and int(power_pole.get("surviving_delta", 0)) == 0:
        findings.append("power_pole_candidate_domain_stable_despite_family_bound_shift")
    protocol_box = _mapping(optional_by_template.get("protocol_storage_box"))
    if int(protocol_box.get("surviving_delta", 0)) < 0:
        findings.append("protocol_storage_box_domain_tightens")
    return findings


def _recommendation(delta: Mapping[str, Any]) -> str:
    if not bool(delta.get("present", False)):
        return "Power-family delta could not be computed; rerun anchor-domain inventory."
    if int(delta.get("power_family_changed_count", 0)) > 0:
        return (
            "Adjacent anchors have different conditioned power-family bounds; compare "
            "power coverage core propagation before changing proof semantics."
        )
    return "Power-family bounds are identical for the compared anchors; inspect other model layers."


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


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _int_or_none(value: Any) -> int:
    return int(value) if value is not None else 0


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
