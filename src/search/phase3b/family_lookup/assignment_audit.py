from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import now_iso
from src.search.phase3b.forced_anchor.master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
    _build_exact_overlay,
    _candidate_ghost_rect,
    _check,
    _display_path,
    _file_hash,
    _mapping,
    _resolve_path,
    _selected_anchor_indices,
)
from src.search.phase3b.forced_anchor.model_slice import (
    _constraint_has_field,
    _constraint_var_indices,
)

FAMILY_LOOKUP_ASSIGNMENT_AUDIT_SOURCE = (
    "phase3b_family_lookup_assignment_audit_v1"
)


def build_phase3b_family_lookup_assignment_audit(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    sample_limit: int = 1,
    anchor_indices: Optional[Sequence[int]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    candidate_key = str(candidate)
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path if campaign_state_path is not None else DEFAULT_CAMPAIGN_STATE_PATH,
    )
    before_hash = _file_hash(campaign_path)
    started = time.perf_counter()
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
    }
    encoding: Dict[str, Any] = {}
    anchors: list[Dict[str, Any]] = []
    model_error: Optional[str] = None

    if state is None or state_error is not None:
        status.update({"completed": True, "outcome": "campaign_state_missing"})
    elif not record:
        status.update({"completed": True, "outcome": "candidate_missing"})
    elif not selected_anchor_indices:
        status.update({"completed": True, "outcome": "anchor_samples_missing"})
    else:
        try:
            model, base_proto = _build_exact_overlay(
                project_root,
                ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                master_search_profile=master_search_profile,
            )
            delegate = getattr(model, "_coordinate_delegate", None)
            encoding = _family_lookup_encoding(model, delegate, base_proto)
            for anchor_idx in selected_anchor_indices:
                anchors.append(_anchor_lookup_report(model, delegate, int(anchor_idx)))
            status.update(_status_from_anchors(anchors))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update({"completed": True, "evaluated": False, "outcome": "diagnostic_error"})

    after_hash = _file_hash(campaign_path)
    recommendation = _recommendation(status.get("outcome"))
    return {
        "metadata": {
            "source": FAMILY_LOOKUP_ASSIGNMENT_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "static_lookup_audit_not_proof_source",
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
        "status": {**status, "recommendation": recommendation},
        "family_lookup_encoding": encoding,
        "anchors": anchors,
        "summary": _summary(anchors),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "campaign_state_unchanged": before_hash == after_hash,
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            encoding=encoding,
            anchors=anchors,
            status=status,
            model_error=model_error,
            campaign_state_unchanged=before_hash == after_hash,
        ),
        "recommendation": recommendation,
    }


def render_phase3b_family_lookup_assignment_audit_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    encoding = _mapping(report.get("family_lookup_encoding"))
    summary = _mapping(report.get("summary"))
    lines = [
        "# Phase 3B Family Lookup Assignment Audit",
        "",
        f"- Candidate: {candidate.get('key')}",
        "- Diagnostic semantics: static_lookup_audit_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Use shell lookup: {encoding.get('use_shell_lookup')}",
        f"- Shell lookup rows: {encoding.get('shell_lookup_row_count')}",
        f"- Family variables: {encoding.get('family_variable_count')}",
        f"- Missing survivor lookup rows: {summary.get('missing_lookup_row_count')}",
        f"- Recommendation: {report.get('recommendation')}",
        "",
        "## Anchors",
        "",
        "| Anchor | Classification | Surviving Poses | Surviving Families | Shell Pairs | Missing Rows |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for anchor in list(report.get("anchors", [])):
        if isinstance(anchor, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(anchor.get("anchor_idx")),
                        _markdown_cell(anchor.get("classification")),
                        _markdown_cell(anchor.get("surviving_pose_count")),
                        _markdown_cell(anchor.get("surviving_family_count")),
                        _markdown_cell(anchor.get("surviving_shell_pair_count")),
                        _markdown_cell(anchor.get("missing_lookup_row_count")),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Top Surviving Families", "", "| Anchor | Family | Family Id | Count |", "| --- | --- | --- | --- |"])
    for anchor in list(report.get("anchors", [])):
        if not isinstance(anchor, Mapping):
            continue
        for row in list(anchor.get("top_surviving_families", [])):
            if isinstance(row, Mapping):
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            _markdown_cell(anchor.get("anchor_idx")),
                            _markdown_cell(row.get("family_name")),
                            _markdown_cell(row.get("family_id")),
                            _markdown_cell(row.get("count")),
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


def render_phase3b_family_lookup_assignment_audit_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    encoding = _mapping(report.get("family_lookup_encoding"))
    summary = _mapping(report.get("summary"))
    lines = [
        "Phase 3B family lookup assignment audit",
        "diagnostic_semantics=static_lookup_audit_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"use_shell_lookup={encoding.get('use_shell_lookup')}",
        f"shell_lookup_row_count={encoding.get('shell_lookup_row_count')}",
        f"family_variable_count={encoding.get('family_variable_count')}",
        f"missing_lookup_row_count={summary.get('missing_lookup_row_count')}",
        f"recommendation={report.get('recommendation')}",
    ]
    for anchor in list(report.get("anchors", [])):
        if isinstance(anchor, Mapping):
            lines.append(
                "anchor "
                f"idx={anchor.get('anchor_idx')} "
                f"classification={anchor.get('classification')} "
                f"surviving_poses={anchor.get('surviving_pose_count')} "
                f"surviving_families={anchor.get('surviving_family_count')} "
                f"shell_pairs={anchor.get('surviving_shell_pair_count')} "
                f"missing_rows={anchor.get('missing_lookup_row_count')}"
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


def _family_lookup_encoding(model: Any, delegate: Any, model_proto: Any) -> Dict[str, Any]:
    family_name_by_int = {
        int(idx): str(name)
        for idx, name in dict(getattr(delegate, "_power_pole_family_name_by_int", {}) or {}).items()
    }
    shell_rows = [
        (int(row[0]), int(row[1]), int(row[2]))
        for row in list(getattr(delegate, "_power_pole_shell_lookup_rows", []) or [])
    ]
    tuple_rows = [
        tuple(int(value) for value in row)
        for row in list(getattr(delegate, "_power_pole_family_tuple_rows", []) or [])
    ]
    proto_payload = _proto_family_lookup_payload(model_proto)
    slot_count = len(list(getattr(delegate, "residual_optional_slots", {}).get("power_pole", [])))
    family_pose_counts = {
        str(name): int(count)
        for name, count in dict(getattr(delegate, "_power_pole_family_pose_counts", {}) or {}).items()
    }
    return {
        "use_shell_lookup": bool(getattr(delegate, "_power_pole_use_shell_lookup", False)),
        "family_count": int(len(family_name_by_int)),
        "family_name_by_int": {str(idx): name for idx, name in sorted(family_name_by_int.items())},
        "sentinel_family_id": int(len(family_name_by_int)),
        "power_pole_slot_count": int(slot_count),
        "family_variable_count": int(proto_payload.get("family_variable_count", 0)),
        "family_variable_domain": proto_payload.get("family_variable_domain"),
        "family_constraint_kind_counts": dict(proto_payload.get("constraint_kind_counts", {})),
        "shell_lookup_row_count": int(len(shell_rows)),
        "shell_lookup_family_count": int(len({int(row[2]) for row in shell_rows})),
        "tuple_lookup_row_count": int(len(tuple_rows)),
        "shell_lookup_rows_sample": [
            {
                "d_lo": int(row[0]),
                "d_hi": int(row[1]),
                "family_id": int(row[2]),
                "family_name": family_name_by_int.get(int(row[2])),
            }
            for row in shell_rows[:25]
        ],
        "family_pose_counts_top": [
            {"family_name": str(name), "count": int(count)}
            for name, count in sorted(
                family_pose_counts.items(),
                key=lambda item: (-int(item[1]), str(item[0])),
            )[:25]
        ],
    }


def _anchor_lookup_report(model: Any, delegate: Any, anchor_idx: int) -> Dict[str, Any]:
    ghost_domains = list(getattr(model, "_ghost_domains", []))
    if int(anchor_idx) < 0 or int(anchor_idx) >= len(ghost_domains):
        return {
            "anchor_idx": int(anchor_idx),
            "present": False,
            "classification": "anchor_missing",
        }
    domain = dict(ghost_domains[int(anchor_idx)])
    blocked_cells = {(int(x), int(y)) for x, y in list(domain.get("cells", []))}
    mode_domains = dict(getattr(delegate, "_template_full_mode_rect_domains", {}).get("power_pole", {}))
    pose_tuples = dict(getattr(delegate, "_template_pose_tuple_by_idx", {}).get("power_pole", {}))
    family_id_by_pose = {
        int(pose_idx): int(family_id)
        for pose_idx, family_id in dict(getattr(delegate, "_power_pole_family_id_by_pose_idx", {}) or {}).items()
    }
    family_name_by_int = {
        int(idx): str(name)
        for idx, name in dict(getattr(delegate, "_power_pole_family_name_by_int", {}) or {}).items()
    }
    shell_lookup_rows = {
        (int(row[0]), int(row[1]), int(row[2]))
        for row in list(getattr(delegate, "_power_pole_shell_lookup_rows", []) or [])
    }
    family_counts: Counter[int] = Counter()
    shell_pair_counts: Counter[tuple[int, int, int]] = Counter()
    missing_rows: Counter[tuple[int, int, int]] = Counter()
    surviving_pose_count = 0
    blocked_pose_count = 0
    for pose_idx, pose_tuple in sorted(pose_tuples.items()):
        if not blocked_cells.isdisjoint(model._pose_cells("power_pole", int(pose_idx))):
            blocked_pose_count += 1
            continue
        surviving_pose_count += 1
        try:
            x_val, y_val, mode_id = pose_tuple
        except Exception:
            continue
        family_id = family_id_by_pose.get(int(pose_idx))
        if family_id is None:
            continue
        family_counts[int(family_id)] += 1
        mode_domain = mode_domains.get(int(mode_id))
        if mode_domain is None:
            continue
        dx, dy = delegate._power_pole_shell_distance(
            mode_domain,
            int(x_val),
            int(y_val),
        )
        d_lo, d_hi = sorted((int(dx), int(dy)))
        shell_key = (int(d_lo), int(d_hi), int(family_id))
        shell_pair_counts[shell_key] += 1
        if shell_key not in shell_lookup_rows:
            missing_rows[shell_key] += 1

    classification = _anchor_classification(
        surviving_pose_count=surviving_pose_count,
        missing_lookup_count=sum(missing_rows.values()),
        shell_lookup_active=bool(getattr(delegate, "_power_pole_use_shell_lookup", False)),
    )
    return {
        "anchor_idx": int(anchor_idx),
        "present": True,
        "anchor": dict(_mapping(domain.get("anchor"))),
        "blocked_cell_count": int(len(blocked_cells)),
        "classification": classification,
        "pose_count": int(len(pose_tuples)),
        "surviving_pose_count": int(surviving_pose_count),
        "blocked_pose_count": int(blocked_pose_count),
        "surviving_family_count": int(len(family_counts)),
        "surviving_shell_pair_count": int(len(shell_pair_counts)),
        "missing_lookup_row_count": int(sum(missing_rows.values())),
        "missing_lookup_rows": [
            {
                "d_lo": int(row[0]),
                "d_hi": int(row[1]),
                "family_id": int(row[2]),
                "family_name": family_name_by_int.get(int(row[2])),
                "count": int(count),
            }
            for row, count in sorted(missing_rows.items())[:25]
        ],
        "top_surviving_families": [
            {
                "family_id": int(family_id),
                "family_name": family_name_by_int.get(int(family_id)),
                "count": int(count),
            }
            for family_id, count in sorted(
                family_counts.items(),
                key=lambda item: (-int(item[1]), int(item[0])),
            )[:25]
        ],
        "top_surviving_shell_rows": [
            {
                "d_lo": int(row[0]),
                "d_hi": int(row[1]),
                "family_id": int(row[2]),
                "family_name": family_name_by_int.get(int(row[2])),
                "count": int(count),
            }
            for row, count in sorted(
                shell_pair_counts.items(),
                key=lambda item: (-int(item[1]), item[0]),
            )[:25]
        ],
    }


def _proto_family_lookup_payload(model_proto: Any) -> Dict[str, Any]:
    variables = list(getattr(model_proto, "variables", []))
    var_names = {
        int(index): str(getattr(var, "name", ""))
        for index, var in enumerate(variables)
    }
    family_var_domains: Counter[tuple[int, ...]] = Counter()
    for index, var in enumerate(variables):
        if var_names[int(index)].startswith("family__"):
            family_var_domains[tuple(int(value) for value in list(getattr(var, "domain", [])))] += 1
    kind_counts: Counter[str] = Counter()
    constraints = list(getattr(model_proto, "constraints", []))
    for constraint in constraints:
        if not any(
            var_names.get(int(var_idx), "").startswith("family__")
            for var_idx in _constraint_var_indices(constraint)
        ):
            continue
        kinds = [
            name
            for name in ("linear", "table", "element", "interval", "no_overlap_2d", "lin_max")
            if _constraint_has_field(constraint, name)
        ]
        kind_counts["+".join(kinds) if kinds else "unknown"] += 1
    most_common_domain = family_var_domains.most_common(1)
    return {
        "family_variable_count": int(sum(family_var_domains.values())),
        "family_variable_domain": list(most_common_domain[0][0]) if most_common_domain else [],
        "family_variable_domain_counts": {
            ",".join(str(value) for value in domain): int(count)
            for domain, count in family_var_domains.items()
        },
        "constraint_kind_counts": dict(sorted(kind_counts.items())),
    }


def _anchor_classification(
    *,
    surviving_pose_count: int,
    missing_lookup_count: int,
    shell_lookup_active: bool,
) -> str:
    if surviving_pose_count <= 0:
        return "power_pole_domain_empty"
    if not shell_lookup_active:
        return "tuple_lookup_active"
    if missing_lookup_count > 0:
        return "shell_lookup_missing_survivor_rows"
    return "shell_lookup_survivor_rows_consistent"


def _status_from_anchors(anchors: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    if not anchors:
        return {"completed": True, "evaluated": False, "outcome": "anchor_samples_missing"}
    classifications = {str(anchor.get("classification")) for anchor in anchors}
    if "shell_lookup_missing_survivor_rows" in classifications:
        outcome = "shell_lookup_missing_survivor_rows"
    elif "power_pole_domain_empty" in classifications:
        outcome = "power_pole_domain_empty"
    elif classifications == {"shell_lookup_survivor_rows_consistent"}:
        outcome = "shell_lookup_survivor_rows_consistent"
    elif classifications == {"tuple_lookup_active"}:
        outcome = "tuple_lookup_active"
    else:
        outcome = "family_lookup_audit_inconclusive"
    return {
        "completed": True,
        "evaluated": True,
        "outcome": outcome,
        "classification_counts": dict(Counter(str(anchor.get("classification")) for anchor in anchors)),
    }


def _summary(anchors: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return {
        "anchor_count": int(len(anchors)),
        "surviving_pose_count": int(sum(int(anchor.get("surviving_pose_count", 0)) for anchor in anchors)),
        "missing_lookup_row_count": int(sum(int(anchor.get("missing_lookup_row_count", 0)) for anchor in anchors)),
        "classification_counts": dict(Counter(str(anchor.get("classification")) for anchor in anchors)),
    }


def _recommendation(outcome: Any) -> str:
    if outcome == "shell_lookup_survivor_rows_consistent":
        return (
            "Anchor surviving power-pole poses are covered by the shell lookup rows. "
            "The current blocker is therefore unlikely to be a missing family__ row; "
            "next inspect table/domain strength and interaction with active coverage."
        )
    if outcome == "shell_lookup_missing_survivor_rows":
        return (
            "At least one surviving power-pole pose maps to a shell/family tuple that "
            "is absent from the lookup table. Inspect missing_lookup_rows before any "
            "runtime or proof promotion."
        )
    if outcome == "tuple_lookup_active":
        return "Tuple lookup is active instead of shell lookup; audit tuple rows directly."
    if outcome == "power_pole_domain_empty":
        return "No surviving power-pole pose remains under the selected anchor."
    if outcome == "campaign_state_missing":
        return "Campaign state is missing; provide a B5A workspace campaign state."
    if outcome == "candidate_missing":
        return "Candidate is missing from campaign state."
    if outcome == "anchor_samples_missing":
        return "No anchor sample was selected; provide --anchor-indices."
    if outcome == "diagnostic_error":
        return "Family lookup audit failed; inspect model_error."
    return "Family lookup assignment audit is inconclusive."


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
    selected_anchor_count: int,
    encoding: Mapping[str, Any],
    anchors: Sequence[Mapping[str, Any]],
    status: Mapping[str, Any],
    model_error: Optional[str],
    campaign_state_unchanged: bool,
) -> list[Dict[str, str]]:
    missing_rows = sum(int(anchor.get("missing_lookup_row_count", 0)) for anchor in anchors)
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
            "anchor_selected",
            "pass" if selected_anchor_count > 0 else "fail",
            f"selected_anchor_count={selected_anchor_count}",
        ),
        _check(
            "shell_lookup_active",
            "pass" if bool(encoding.get("use_shell_lookup", False)) else "skipped",
            f"use_shell_lookup={encoding.get('use_shell_lookup')}",
        ),
        _check(
            "family_variables_match_power_pole_slots",
            "pass"
            if int(encoding.get("family_variable_count", 0))
            == int(encoding.get("power_pole_slot_count", -1))
            and bool(status.get("evaluated"))
            else "fail",
            "family_variable_count="
            f"{encoding.get('family_variable_count')} power_pole_slot_count="
            f"{encoding.get('power_pole_slot_count')}",
        ),
        _check(
            "surviving_shell_rows_present",
            "pass" if missing_rows == 0 and bool(status.get("evaluated")) else "fail",
            f"missing_lookup_row_count={missing_rows}",
        ),
        _check(
            "campaign_state_unchanged",
            "pass" if campaign_state_unchanged else "fail",
            f"campaign_state_unchanged={campaign_state_unchanged}",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _load_json_mapping(path: Path) -> tuple[Optional[Mapping[str, Any]], Optional[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "missing"
    except Exception as exc:
        return None, str(exc)
    if not isinstance(payload, Mapping):
        return None, "json root is not an object"
    return payload, None


def _markdown_cell(value: Any) -> str:
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")
