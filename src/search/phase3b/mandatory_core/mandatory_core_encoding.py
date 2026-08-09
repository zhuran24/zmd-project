from __future__ import annotations

import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models._cpsat_compat import cp_model_from_proto
from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    _clone_model_proto,
)
from src.search.exact_campaign import now_iso
from src.search.phase3b.anchor_inventory.domain_inventory import _anchor_domain_report
from src.search.phase3b.forced_anchor.master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
    _candidate_ghost_rect,
    _check,
    _display_path,
    _file_hash,
    _load_json_mapping,
    _mapping,
    _resolve_path,
    _selected_anchor_indices,
)
from src.search.phase3b.mandatory_core.mandatory_core_matrix import (
    _build_mandatory_core_overlay,
    _residual_active_indices,
)

MANDATORY_CORE_ENCODING_SOURCE = "phase3b_mandatory_core_encoding_inventory_v1"

_CONSTRAINT_KINDS = (
    "linear",
    "bool_or",
    "bool_and",
    "bool_xor",
    "at_most_one",
    "exactly_one",
    "interval",
    "no_overlap",
    "no_overlap_2d",
    "all_diff",
    "element",
    "table",
    "lin_max",
    "int_prod",
    "int_div",
    "int_mod",
    "cumulative",
    "reservoir",
)


def build_phase3b_mandatory_core_encoding_inventory(
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
        "recommendation": "Mandatory-core encoding inventory has not run.",
    }
    encoding: Dict[str, Any] = {}
    anchors: list[Dict[str, Any]] = []
    timing: Dict[str, float] = {}
    model_error: Optional[str] = None
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before mandatory-core encoding inventory.",
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
            model, base_proto = _build_mandatory_core_overlay(
                project_root,
                ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                master_search_profile=str(master_search_profile),
                enable_symmetry_breaking=True,
            )
            timing["overlay_build_seconds"] = float(time.perf_counter() - overlay_started)
            disabled_residual_indices = _residual_active_indices(model)
            diagnostic_proto = _proto_with_disabled_residuals(
                base_proto,
                disabled_residual_indices,
            )
            encoding = _encoding_payload(
                model,
                base_proto,
                diagnostic_proto,
                disabled_residual_indices,
            )
            anchors = _anchor_payloads(model, selected_anchor_indices)
            status.update(
                {
                    "completed": True,
                    "evaluated": True,
                    "outcome": "mandatory_core_encoding_inventory_built",
                    "recommendation": "Mandatory-core UNKNOWN survived profile and symmetry changes; inspect no-overlap/domain scale and the tightest anchor-conditioned groups before changing proof semantics.",
                }
            )
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Mandatory-core encoding inventory failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    after_hash = _file_hash(campaign_path)
    return {
        "metadata": {
            "source": MANDATORY_CORE_ENCODING_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "mutated_mandatory_core_not_proof_source",
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
            "slice": "skip_power_coverage_no_protocol_lower_bound_residual_all_inactive",
            "enable_symmetry_breaking": True,
        },
        "status": status,
        "encoding": encoding,
        "anchors": anchors,
        "timing": timing,
        "model_error": model_error,
        "campaign_state_unchanged": before_hash == after_hash,
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            status=status,
            campaign_state_unchanged=before_hash == after_hash,
            model_error=model_error,
        ),
    }


def render_phase3b_mandatory_core_encoding_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    encoding = _mapping(report.get("encoding"))
    summary = _mapping(encoding.get("mandatory_core_summary"))
    proto = _mapping(_mapping(encoding.get("proto")).get("diagnostic_residual_all_inactive"))
    residual = _mapping(encoding.get("residual_disabled"))
    lines = [
        "# Phase 3B Mandatory-Core Encoding Inventory",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Evaluated: {bool(status.get('evaluated', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "- Diagnostic semantics: mutated_mandatory_core_not_proof_source",
        f"- Mandatory groups: {summary.get('group_count')}",
        f"- Mandatory slots: {summary.get('slot_count')}",
        f"- Diagnostic proto variables: {proto.get('variable_count')}",
        f"- Diagnostic proto constraints: {proto.get('constraint_count')}",
        f"- Disabled residual actives: {residual.get('active_var_count')}",
        "",
        "## Mandatory Groups",
        "",
        "| Group | Facility | Required | Slots | Candidate Poses | Mode Domains | Buckets | Domain Table | Signature Table |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for group in list(encoding.get("mandatory_groups", [])):
        if not isinstance(group, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(group.get("group_id")),
                    _markdown_cell(group.get("facility_type")),
                    _markdown_cell(group.get("required_count")),
                    _markdown_cell(group.get("slot_count")),
                    _markdown_cell(group.get("candidate_pose_count")),
                    _markdown_cell(group.get("mode_rect_domain_count")),
                    _markdown_cell(group.get("signature_bucket_count")),
                    _markdown_cell(group.get("uses_domain_table")),
                    _markdown_cell(group.get("uses_signature_table")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Anchor Conditioned Domain",
            "",
            "| Anchor | Mandatory Survivors | Tightest Group | Tightest Survivors |",
            "| --- | --- | --- | --- |",
        ]
    )
    for anchor in list(report.get("anchors", [])):
        if not isinstance(anchor, Mapping):
            continue
        summary = _mapping(anchor.get("summary"))
        tightest = _mapping(anchor.get("tightest_mandatory_group"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(anchor.get("anchor_idx")),
                    _markdown_cell(summary.get("mandatory_surviving_total")),
                    _markdown_cell(tightest.get("group_id")),
                    _markdown_cell(tightest.get("surviving_count")),
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


def render_phase3b_mandatory_core_encoding_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    encoding = _mapping(report.get("encoding"))
    summary = _mapping(encoding.get("mandatory_core_summary"))
    proto = _mapping(encoding.get("proto"))
    diagnostic_proto = _mapping(proto.get("diagnostic_residual_all_inactive"))
    residual = _mapping(encoding.get("residual_disabled"))
    lines = [
        "Phase 3B mandatory-core encoding inventory",
        f"candidate={candidate.get('key')}",
        f"evaluated={bool(status.get('evaluated', False))}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        "diagnostic_semantics=mutated_mandatory_core_not_proof_source",
        f"mandatory_core_summary={summary}",
        f"diagnostic_proto={diagnostic_proto}",
        f"residual_disabled={residual}",
        f"search_guidance={encoding.get('search_guidance')}",
        f"coordinate_symmetry={encoding.get('coordinate_symmetry')}",
    ]
    for group in list(encoding.get("mandatory_groups", [])):
        if isinstance(group, Mapping):
            lines.append(
                "mandatory_group "
                f"group={group.get('group_id')} "
                f"facility={group.get('facility_type')} "
                f"required={group.get('required_count')} "
                f"slots={group.get('slot_count')} "
                f"candidate_poses={group.get('candidate_pose_count')} "
                f"mode_domains={group.get('mode_rect_domain_count')} "
                f"signature_buckets={group.get('signature_bucket_count')} "
                f"uses_domain_table={group.get('uses_domain_table')} "
                f"uses_signature_table={group.get('uses_signature_table')}"
            )
    for anchor in list(report.get("anchors", [])):
        if isinstance(anchor, Mapping):
            summary = _mapping(anchor.get("summary"))
            tightest = _mapping(anchor.get("tightest_mandatory_group"))
            lines.append(
                "anchor "
                f"idx={anchor.get('anchor_idx')} "
                f"mandatory_surviving_total={summary.get('mandatory_surviving_total')} "
                f"tightest_group={tightest.get('group_id')} "
                f"tightest_surviving={tightest.get('surviving_count')}"
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


def _encoding_payload(
    model: Any,
    base_proto: Any,
    diagnostic_proto: Any,
    disabled_residual_indices: Sequence[int],
) -> Dict[str, Any]:
    build_stats = _mapping(getattr(model, "build_stats", {}))
    delegate = getattr(model, "_coordinate_delegate", None)
    mandatory_groups = _mandatory_group_entries(model, delegate)
    residual_slots = getattr(delegate, "residual_optional_slots", {}) if delegate else {}
    required_slots = getattr(delegate, "required_optional_slots", {}) if delegate else {}
    return {
        "master_slot_counts": build_stats.get("master_slot_counts", {}),
        "domain_activation": build_stats.get("domain_activation", {}),
        "mandatory_core_summary": _mandatory_core_summary(mandatory_groups),
        "mandatory_groups": mandatory_groups,
        "required_optional_slots": {
            "by_template": {
                str(tpl): int(len(slots)) for tpl, slots in sorted(required_slots.items())
            },
            "total": int(sum(len(slots) for slots in required_slots.values())),
        },
        "residual_disabled": {
            "by_template": {
                str(tpl): int(len(slots)) for tpl, slots in sorted(residual_slots.items())
            },
            "slot_count": int(sum(len(slots) for slots in residual_slots.values())),
            "active_var_count": int(len(disabled_residual_indices)),
            "active_var_indices_sample": [int(idx) for idx in list(disabled_residual_indices)[:20]],
        },
        "search_guidance": build_stats.get("search_guidance", {}),
        "coordinate_symmetry": build_stats.get("coordinate_symmetry", {}),
        "exact_core_reuse": build_stats.get("exact_core_reuse", {}),
        "global_valid_inequalities": {
            "signature_bucket_capacity_bounds": _mapping(
                _mapping(build_stats.get("global_valid_inequalities")).get(
                    "signature_bucket_capacity_bounds"
                )
            ),
            "residual_signature_bucket_capacity_bounds": _mapping(
                _mapping(build_stats.get("global_valid_inequalities")).get(
                    "residual_signature_bucket_capacity_bounds"
                )
            ),
        },
        "proto": {
            "base_overlay": _proto_payload(base_proto),
            "diagnostic_residual_all_inactive": _proto_payload(diagnostic_proto),
        },
    }


def _mandatory_group_entries(model: Any, delegate: Any) -> list[Dict[str, Any]]:
    entries: list[Dict[str, Any]] = []
    groups = list(getattr(model, "_mandatory_groups", []))
    for group in groups:
        group_map = _mapping(group)
        group_id = str(group_map.get("group_id"))
        slots = list(getattr(delegate, "mandatory_slots", {}).get(group_id, [])) if delegate else []
        mode_rect_domains = dict(
            getattr(delegate, "_mandatory_group_mode_rect_domains", {}).get(group_id, {})
        ) if delegate else {}
        bucket_pose_counts = dict(
            getattr(delegate, "_mandatory_group_bucket_pose_counts", {}).get(group_id, {})
        ) if delegate else {}
        bucket_upper_bounds = dict(
            getattr(delegate, "_mandatory_group_bucket_count_upper_bounds", {}).get(group_id, {})
        ) if delegate else {}
        candidate_pose_count = _candidate_pose_count(
            slots,
            getattr(delegate, "_mandatory_group_pose_counts", {}) if delegate else {},
            group_id,
        )
        required_count = int(
            group_map.get("count", len(list(group_map.get("instance_ids", []))))
        )
        entries.append(
            {
                "group_id": group_id,
                "facility_type": str(group_map.get("facility_type")),
                "operation_type": str(group_map.get("operation_type", "")),
                "required_count": int(required_count),
                "slot_count": int(len(slots)),
                "required_count_matches_slot_count": int(required_count) == int(len(slots)),
                "candidate_pose_count": int(candidate_pose_count),
                "slot_candidate_literal_total": int(
                    sum(int(getattr(slot, "candidate_pose_count", 0)) for slot in slots)
                ),
                "mode_rect_domain_count": int(len(mode_rect_domains)),
                "mode_rect_pose_count_total": int(
                    sum(int(getattr(domain, "pose_count", 0)) for domain in mode_rect_domains.values())
                ),
                "mode_rect_bounds": _mode_rect_bounds(mode_rect_domains.values()),
                "uses_domain_table": bool(
                    getattr(delegate, "_mandatory_group_uses_domain_table", {}).get(
                        group_id,
                        False,
                    )
                )
                if delegate
                else False,
                "uses_signature_table": bool(
                    getattr(delegate, "_mandatory_group_uses_signature_table", {}).get(
                        group_id,
                        False,
                    )
                )
                if delegate
                else False,
                "signature_bucket_count": int(len(bucket_pose_counts)),
                "signature_bucket_pose_count_min": _min_or_none(bucket_pose_counts.values()),
                "signature_bucket_pose_count_max": _max_or_none(bucket_pose_counts.values()),
                "signature_bucket_upper_bound_min": _min_or_none(bucket_upper_bounds.values()),
                "signature_bucket_upper_bound_max": _max_or_none(bucket_upper_bounds.values()),
                "signature_count_var_count": int(
                    len(getattr(delegate, "mandatory_signature_count_vars", {}).get(group_id, {}))
                )
                if delegate
                else 0,
                "signature_membership_literal_count": _signature_membership_literal_count(
                    delegate,
                    group_id,
                    slot_count=len(slots),
                    bucket_count=len(bucket_pose_counts),
                    uses_signature_table=bool(
                        getattr(delegate, "_mandatory_group_uses_signature_table", {}).get(
                            group_id,
                            False,
                        )
                    )
                    if delegate
                    else False,
                ),
                "slot_var_presence_counts": _slot_var_presence_counts(slots),
                "mode_rect_domains": _mode_rect_domain_payload(mode_rect_domains),
                "signature_bucket_pose_counts": {
                    str(key): int(value) for key, value in sorted(bucket_pose_counts.items())
                },
                "signature_bucket_upper_bounds": {
                    str(key): int(value) for key, value in sorted(bucket_upper_bounds.items())
                },
            }
        )
    return sorted(entries, key=lambda entry: str(entry.get("group_id")))


def _mandatory_core_summary(groups: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return {
        "group_count": int(len(groups)),
        "slot_count": int(sum(int(group.get("slot_count", 0)) for group in groups)),
        "required_count_total": int(
            sum(int(group.get("required_count", 0)) for group in groups)
        ),
        "candidate_pose_total": int(
            sum(int(group.get("candidate_pose_count", 0)) for group in groups)
        ),
        "slot_candidate_literal_total": int(
            sum(int(group.get("slot_candidate_literal_total", 0)) for group in groups)
        ),
        "mode_rect_domain_total": int(
            sum(int(group.get("mode_rect_domain_count", 0)) for group in groups)
        ),
        "signature_bucket_total": int(
            sum(int(group.get("signature_bucket_count", 0)) for group in groups)
        ),
        "signature_count_var_total": int(
            sum(int(group.get("signature_count_var_count", 0)) for group in groups)
        ),
        "signature_membership_literal_total": int(
            sum(
                int(group.get("signature_membership_literal_count", 0))
                for group in groups
            )
        ),
        "domain_table_group_count": int(
            sum(1 for group in groups if bool(group.get("uses_domain_table", False)))
        ),
        "signature_table_group_count": int(
            sum(1 for group in groups if bool(group.get("uses_signature_table", False)))
        ),
    }


def _anchor_payloads(model: Any, selected_anchor_indices: Sequence[int]) -> list[Dict[str, Any]]:
    anchors: list[Dict[str, Any]] = []
    ghost_domains = list(getattr(model, "_ghost_domains", []))
    for anchor_idx in selected_anchor_indices:
        idx = int(anchor_idx)
        if idx < 0 or idx >= len(ghost_domains):
            anchors.append(
                {
                    "anchor_idx": idx,
                    "present": False,
                    "skip_reason": "anchor_not_in_model_ghost_domains",
                }
            )
            continue
        anchors.append(_anchor_domain_report(model, idx))
    return anchors


def _proto_with_disabled_residuals(
    base_proto: Any,
    disabled_residual_indices: Sequence[int],
) -> Any:
    if not disabled_residual_indices:
        return _clone_model_proto(base_proto)
    local_model = cp_model_from_proto(_clone_model_proto(base_proto))
    for var_idx in disabled_residual_indices:
        local_model.Add(local_model.GetBoolVarFromProtoIndex(int(var_idx)) == 0)
    return _clone_model_proto(local_model.Proto())


def _proto_payload(proto: Any) -> Dict[str, Any]:
    variables = list(getattr(proto, "variables", []))
    constraints = list(getattr(proto, "constraints", []))
    return {
        "variable_count": int(len(variables)),
        "constraint_count": int(len(constraints)),
        "constraint_kind_counts": dict(sorted(_constraint_kind_counts(constraints).items())),
        "constraint_name_prefix_counts": dict(
            sorted(_constraint_name_prefix_counts(constraints).items())
        ),
        "variable_prefix_counts": dict(sorted(_variable_prefix_counts(variables).items())),
        "variable_name_samples": _variable_name_samples(variables),
    }


def _constraint_kind_counts(constraints: Sequence[Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for constraint in constraints:
        counts[_constraint_kind(constraint)] += 1
    return counts


def _constraint_kind(constraint: Any) -> str:
    for kind in _CONSTRAINT_KINDS:
        has_method = getattr(constraint, f"has_{kind}", None)
        try:
            if has_method is not None and bool(has_method()):
                return str(kind)
        except Exception:
            continue
    return "unknown"


def _constraint_name_prefix_counts(constraints: Sequence[Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for constraint in constraints:
        prefix = _name_prefix(str(getattr(constraint, "name", "")))
        if prefix:
            counts[prefix] += 1
    return counts


def _variable_prefix_counts(variables: Sequence[Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for variable in variables:
        prefix = _name_prefix(str(getattr(variable, "name", "")))
        if prefix:
            counts[prefix] += 1
    return counts


def _variable_name_samples(variables: Sequence[Any], limit: int = 24) -> list[str]:
    samples: list[str] = []
    seen: set[str] = set()
    for variable in variables:
        name = str(getattr(variable, "name", ""))
        prefix = _name_prefix(name)
        if not prefix or prefix in seen:
            continue
        seen.add(prefix)
        samples.append(name)
        if len(samples) >= int(limit):
            break
    return samples


def _name_prefix(name: str) -> str:
    if not name:
        return ""
    if "__" in name:
        return name.split("__", 1)[0]
    return name


def _candidate_pose_count(
    slots: Sequence[Any],
    pose_counts: Mapping[str, Any],
    group_id: str,
) -> int:
    if group_id in pose_counts:
        try:
            return int(pose_counts[group_id])
        except Exception:
            pass
    if slots:
        return int(getattr(slots[0], "candidate_pose_count", 0))
    return 0


def _signature_membership_literal_count(
    delegate: Any,
    group_id: str,
    *,
    slot_count: int,
    bucket_count: int,
    uses_signature_table: bool,
) -> int:
    if delegate is None or bool(uses_signature_table):
        return 0
    membership = (
        getattr(delegate, "_mandatory_signature_membership", {})
        .get(str(group_id), {})
    )
    count = int(sum(len(lits) for lits in membership.values()))
    if count > 0:
        return count
    return int(max(0, slot_count) * max(0, bucket_count))


def _slot_var_presence_counts(slots: Sequence[Any]) -> Dict[str, int]:
    counts = {
        "x": 0,
        "y": 0,
        "mode": 0,
        "order_key": 0,
        "signature": 0,
        "active": 0,
        "family": 0,
    }
    for slot in slots:
        for key in list(counts):
            if getattr(slot, key, None) is not None:
                counts[key] += 1
    return {str(key): int(value) for key, value in counts.items()}


def _mode_rect_domain_payload(domains: Mapping[int, Any]) -> list[Dict[str, Any]]:
    return [
        {
            "mode_id": int(getattr(domain, "mode_id", mode_id)),
            "orientation": str(getattr(domain, "orientation", "")),
            "port_mode": str(getattr(domain, "port_mode", "")),
            "x_min": int(getattr(domain, "x_min", 0)),
            "x_max": int(getattr(domain, "x_max", 0)),
            "y_min": int(getattr(domain, "y_min", 0)),
            "y_max": int(getattr(domain, "y_max", 0)),
            "pose_count": int(getattr(domain, "pose_count", 0)),
        }
        for mode_id, domain in sorted(domains.items())
    ]


def _mode_rect_bounds(domains: Sequence[Any]) -> Dict[str, Optional[int]]:
    domain_list = list(domains)
    if not domain_list:
        return {"x_min": None, "x_max": None, "y_min": None, "y_max": None}
    return {
        "x_min": min(int(getattr(domain, "x_min", 0)) for domain in domain_list),
        "x_max": max(int(getattr(domain, "x_max", 0)) for domain in domain_list),
        "y_min": min(int(getattr(domain, "y_min", 0)) for domain in domain_list),
        "y_max": max(int(getattr(domain, "y_max", 0)) for domain in domain_list),
    }


def _min_or_none(values: Sequence[Any]) -> Optional[int]:
    int_values = [int(value) for value in values]
    return min(int_values) if int_values else None


def _max_or_none(values: Sequence[Any]) -> Optional[int]:
    int_values = [int(value) for value in values]
    return max(int_values) if int_values else None


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
    selected_anchor_count: int,
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
            "forced_anchor_samples_present",
            "pass" if selected_anchor_count > 0 else "fail",
            f"selected_anchor_count={int(selected_anchor_count)}",
        ),
        _check(
            "mandatory_core_encoding_evaluated",
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


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
