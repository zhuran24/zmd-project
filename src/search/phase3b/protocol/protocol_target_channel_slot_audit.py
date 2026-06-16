from __future__ import annotations

import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import now_iso
from src.search.phase3b.forced_anchor.master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    _candidate_ghost_rect,
    _check,
    _display_path,
    _file_hash,
    _load_json_mapping,
    _mapping,
    _resolve_path,
)
from src.search.phase3b.forced_anchor.model_slice import _build_exact_overlay
from src.search.phase3b.forced_anchor.proto_reduction import (
    _constraint_has_field,
    _cover_choice_target_prefixes_from_token,
    _element_target_var_indices,
    _expanded_cover_choice_target_prefixes,
)


PROTOCOL_TARGET_CHANNEL_SLOT_AUDIT_SOURCE = (
    "phase3b_protocol_target_channel_slot_audit_v1"
)
DEFAULT_CANDIDATE = "67x13"
DEFAULT_POWERED_TEMPLATE = "protocol_storage_box"
DEFAULT_TARGET_TOKENS = ("active_x", "active_y", "active_xy")
DEFAULT_ANCHOR_INDICES = (118, 125)
DEFAULT_PROTO_REDUCTION_PATH = Path(
    ".artifacts/"
    "phase3b_proto_reduction_protocol_template_target_channel_split_"
    "anchors118_125_30s_20260423/"
    "forced_anchor_proto_reduction.json"
)
DEFAULT_ANCHOR_DIFFERENTIAL_PATH = Path(
    ".artifacts/"
    "phase3b_anchor_differential_audit_118_125_delta_block64_family_bounds_20260423/"
    "anchor_differential_audit.json"
)
DEFAULT_FAMILY_NAMES = ("family_009",)


def build_phase3b_protocol_target_channel_slot_audit(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    proto_reduction_path: Optional[Path] = None,
    anchor_differential_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    anchor_indices: Optional[Sequence[int]] = DEFAULT_ANCHOR_INDICES,
    powered_template: str = DEFAULT_POWERED_TEMPLATE,
    target_tokens: Sequence[str] = DEFAULT_TARGET_TOKENS,
    family_names: Sequence[str] = DEFAULT_FAMILY_NAMES,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    power_family_lookup_encoding: Optional[str] = "linear_shell_guards",
    power_pole_shell_distance_encoding: Optional[str] = "linear_minmax",
    power_coverage_witness_encoding: Optional[str] = "block_element",
    power_coverage_witness_block_geometry: Optional[str] = "final_target",
    power_coverage_witness_block_size: Optional[int] = 64,
    power_coverage_witness_block_templates: Optional[str] = "",
    power_coverage_selected_interval_encoding: Optional[str] = "delta",
    sample_limit: int = 12,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path if campaign_state_path is not None else DEFAULT_CAMPAIGN_STATE_PATH,
    )
    proto_reduction_resolved = _resolve_path(
        project_root,
        proto_reduction_path
        if proto_reduction_path is not None
        else DEFAULT_PROTO_REDUCTION_PATH,
    )
    anchor_differential_resolved = _resolve_path(
        project_root,
        anchor_differential_path
        if anchor_differential_path is not None
        else DEFAULT_ANCHOR_DIFFERENTIAL_PATH,
    )
    selected_anchor_indices = [int(idx) for idx in (anchor_indices or ())]
    normalized_target_tokens = tuple(_normalize_tokens(target_tokens))
    normalized_family_names = tuple(str(name) for name in family_names if str(name))

    before_hash = _file_hash(campaign_path)
    state, state_error = _load_json_mapping(campaign_path)
    proto_reduction, proto_reduction_error = _load_json_mapping(proto_reduction_resolved)
    anchor_differential, anchor_differential_error = _load_json_mapping(
        anchor_differential_resolved
    )
    candidates = _mapping(state.get("candidates")) if state else {}
    record = _mapping(candidates.get(str(candidate)))

    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Protocol target-channel slot audit has not run.",
    }
    target_channel_map: Dict[str, Any] = {}
    model_error: Optional[str] = None
    timing: Dict[str, float] = {}
    started = time.perf_counter()
    env_overrides = _exact_env_overrides(
        power_family_lookup_encoding=power_family_lookup_encoding,
        power_pole_shell_distance_encoding=power_pole_shell_distance_encoding,
        power_coverage_witness_encoding=power_coverage_witness_encoding,
        power_coverage_witness_block_geometry=power_coverage_witness_block_geometry,
        power_coverage_witness_block_size=power_coverage_witness_block_size,
        power_coverage_witness_block_templates=power_coverage_witness_block_templates,
        power_coverage_selected_interval_encoding=power_coverage_selected_interval_encoding,
    )

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run this audit against a B5A workspace state.",
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
                "outcome": "anchor_indices_missing",
                "recommendation": "Pass --anchor-indices so target-channel deltas can be compared.",
            }
        )
    else:
        try:
            overlay_started = time.perf_counter()
            ghost_rect = _candidate_ghost_rect(str(candidate), record)
            with _temporary_environ(env_overrides):
                _, base_proto = _build_exact_overlay(
                    project_root,
                    ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                    master_search_profile=master_search_profile,
                )
            timing["overlay_build_seconds"] = float(time.perf_counter() - overlay_started)
            target_channel_map = _build_protocol_target_channel_map(
                base_proto,
                powered_template=str(powered_template),
                target_tokens=normalized_target_tokens,
                sample_limit=int(sample_limit),
            )
            status.update(
                {
                    "completed": True,
                    "evaluated": True,
                    "outcome": "protocol_target_channel_slot_audit_completed",
                    "recommendation": "Use this no-solve target-channel map to choose the next bounded proto or formulation probe; do not treat it as proof.",
                }
            )
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Protocol target-channel audit failed; inspect model_error before using this evidence.",
                }
            )

    forced_status = _forced_status_by_anchor_target(
        proto_reduction or {},
        powered_template=str(powered_template),
        target_tokens=normalized_target_tokens,
        anchor_indices=selected_anchor_indices,
    )
    family_bounds = _family_bounds_by_anchor(
        anchor_differential or {},
        family_names=normalized_family_names,
        anchor_indices=selected_anchor_indices,
    )
    comparison = _compare_target_channel_signal(
        forced_status,
        target_channel_map,
        family_bounds,
        target_tokens=normalized_target_tokens,
        family_names=normalized_family_names,
    )
    after_hash = _file_hash(campaign_path)
    campaign_state_unchanged = before_hash == after_hash
    timing["total_seconds"] = float(time.perf_counter() - started)

    report = {
        "metadata": {
            "source": PROTOCOL_TARGET_CHANNEL_SLOT_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "no_solve_proto_mapping_not_proof_source",
            "solver_invoked": False,
        },
        "paths": {
            "project_root": str(project_root),
            "campaign_state": _display_path(project_root, campaign_path),
            "proto_reduction": _display_path(project_root, proto_reduction_resolved),
            "anchor_differential": _display_path(
                project_root,
                anchor_differential_resolved,
            ),
        },
        "candidate": {
            "key": str(candidate),
            "campaign_status": record.get("status") if record else None,
            "ghost_rect": _candidate_ghost_rect(str(candidate), record) if record else {},
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "powered_template": str(powered_template),
            "target_tokens": list(normalized_target_tokens),
            "family_names": list(normalized_family_names),
            "anchor_indices": list(selected_anchor_indices),
            "diagnostic_environment": dict(env_overrides),
            "sample_limit": int(sample_limit),
        },
        "input_evidence": {
            "campaign_present": state is not None and state_error is None,
            "campaign_load_error": state_error,
            "candidate_present": bool(record),
            "proto_reduction_present": proto_reduction is not None
            and proto_reduction_error is None,
            "proto_reduction_load_error": proto_reduction_error,
            "anchor_differential_present": anchor_differential is not None
            and anchor_differential_error is None,
            "anchor_differential_load_error": anchor_differential_error,
        },
        "target_channel_map": target_channel_map,
        "forced_reduction_status": forced_status,
        "family_bounds": family_bounds,
        "comparison": comparison,
        "summary": _summary(status, target_channel_map, forced_status, family_bounds, comparison),
        "status": status,
        "timing": timing,
        "model_error": model_error,
        "campaign_state_unchanged": bool(campaign_state_unchanged),
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            proto_reduction_present=proto_reduction is not None
            and proto_reduction_error is None,
            anchor_differential_present=anchor_differential is not None
            and anchor_differential_error is None,
            selected_anchor_count=len(selected_anchor_indices),
            target_channel_map=target_channel_map,
            comparison=comparison,
            family_bounds=family_bounds,
            family_names=normalized_family_names,
            status=status,
            campaign_state_unchanged=campaign_state_unchanged,
            model_error=model_error,
        ),
    }
    return report


def render_phase3b_protocol_target_channel_slot_audit_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    candidate = _mapping(report.get("candidate"))
    profile = _mapping(report.get("profile"))
    summary = _mapping(report.get("summary"))
    comparison = _mapping(report.get("comparison"))
    lines = [
        "# Phase 3B Protocol Target-Channel Slot Audit",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Powered template: {profile.get('powered_template')}",
        f"- Evaluated: {bool(status.get('evaluated', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Solver invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
        f"- Campaign state unchanged: {bool(report.get('campaign_state_unchanged', False))}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Summary",
        "",
        f"- Diagnostic signal: {summary.get('diagnostic_signal')}",
        f"- Next probe hint: {summary.get('next_probe_hint')}",
        f"- Protocol mapped slot count: {summary.get('mapped_protocol_slot_count')}",
        f"- Mapping matches artifact counts: {summary.get('mapping_matches_artifact_counts')}",
        "",
        "## Target Status Deltas",
        "",
        "| Target | Divergent | Statuses | Removed counts | Branches | Conflicts |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for delta in list(comparison.get("target_status_deltas", [])):
        if not isinstance(delta, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(delta.get("target")),
                    _cell(delta.get("divergent_status")),
                    _cell(delta.get("statuses_by_anchor")),
                    _cell(delta.get("removed_constraint_counts_by_anchor")),
                    _cell(delta.get("branches_by_anchor")),
                    _cell(delta.get("conflicts_by_anchor")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Family Bounds", ""])
    lines.append("| Anchor | Family | Implied upper | Domain upper | Upper reduction |")
    lines.append("| --- | --- | ---: | ---: | ---: |")
    for anchor_key, families in sorted(_mapping(report.get("family_bounds")).items()):
        for family_name, bound in sorted(_mapping(families).items()):
            if not isinstance(bound, Mapping):
                continue
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(anchor_key),
                        _cell(family_name),
                        _cell(bound.get("implied_upper_when_anchor_active")),
                        _cell(bound.get("family_domain_upper")),
                        _cell(bound.get("upper_reduction_when_anchor_active")),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Target Channel Map", ""])
    lines.append("| Target | Constraint count | Unique slots | Prefix counts |")
    lines.append("| --- | ---: | ---: | --- |")
    for target, payload in sorted(
        _mapping(_mapping(report.get("target_channel_map")).get("by_target_token")).items()
    ):
        if not isinstance(payload, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(target),
                    _cell(payload.get("constraint_count")),
                    _cell(payload.get("unique_slot_count")),
                    _cell(payload.get("prefix_counts")),
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
                        _cell(check.get("check_id")),
                        _cell(check.get("status")),
                        _cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Comparison JSON", "", "```json"])
    lines.append(json.dumps(comparison, indent=2, ensure_ascii=False))
    lines.extend(["```"])
    return "\n".join(lines) + "\n"


def render_phase3b_protocol_target_channel_slot_audit_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    summary = _mapping(report.get("summary"))
    lines = [
        "phase3b protocol target-channel slot audit",
        f"candidate: {_mapping(report.get('candidate')).get('key')}",
        f"evaluated: {bool(status.get('evaluated', False))}",
        f"outcome: {status.get('outcome')}",
        f"solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
        f"campaign_state_unchanged: {bool(report.get('campaign_state_unchanged', False))}",
        f"diagnostic_signal: {summary.get('diagnostic_signal')}",
        f"next_probe_hint: {summary.get('next_probe_hint')}",
        "",
        "target_status_deltas:",
    ]
    for delta in list(_mapping(report.get("comparison")).get("target_status_deltas", [])):
        if isinstance(delta, Mapping):
            lines.append(
                "  "
                + str(delta.get("target"))
                + " statuses="
                + json.dumps(delta.get("statuses_by_anchor", {}), ensure_ascii=False)
                + " removed="
                + json.dumps(
                    delta.get("removed_constraint_counts_by_anchor", {}),
                    ensure_ascii=False,
                )
            )
    lines.append("")
    lines.append("checks:")
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                f"  {check.get('check_id')}: {check.get('status')} - {check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _build_protocol_target_channel_map(
    model_proto: Any,
    *,
    powered_template: str,
    target_tokens: Sequence[str],
    sample_limit: int = 12,
) -> Dict[str, Any]:
    token_prefixes = {
        str(token): _expanded_cover_choice_target_prefixes(
            _cover_choice_target_prefixes_from_token(str(token))
        )
        for token in target_tokens
    }
    prefixes = sorted({prefix for values in token_prefixes.values() for prefix in values})
    variables = list(getattr(model_proto, "variables", []))
    var_names = {
        int(index): str(getattr(var, "name", ""))
        for index, var in enumerate(variables)
    }
    by_prefix: Dict[str, Dict[str, Any]] = {
        prefix: {
            "constraint_indices": set(),
            "slot_indices": set(),
            "slot_keys": set(),
            "samples": [],
        }
        for prefix in prefixes
    }
    by_target: Dict[str, Dict[str, Any]] = {
        token: {
            "constraint_indices": set(),
            "slot_indices": set(),
            "prefix_counts": {prefix: 0 for prefix in token_prefixes[token]},
        }
        for token in token_prefixes
    }
    slot_profiles: Dict[int, Dict[str, Any]] = {}
    constraints = list(getattr(model_proto, "constraints", []))
    element_constraint_count = 0
    for constraint_idx, constraint in enumerate(constraints):
        element = (
            getattr(constraint, "element", None)
            if _constraint_has_field(constraint, "element")
            else None
        )
        if element is None:
            continue
        element_constraint_count += 1
        target_names = [
            var_names.get(int(var_idx), "")
            for var_idx in _element_target_var_indices(element)
        ]
        parsed_targets = [
            parsed
            for parsed in (
                _parse_protocol_target_var_name(
                    name,
                    powered_template=powered_template,
                    prefixes=prefixes,
                )
                for name in target_names
            )
            if parsed is not None
        ]
        if not parsed_targets:
            continue
        matched_prefixes = sorted({str(parsed["prefix"]) for parsed in parsed_targets})
        matched_slots = sorted({int(parsed["slot_index"]) for parsed in parsed_targets})
        for parsed in parsed_targets:
            prefix = str(parsed["prefix"])
            slot_idx = int(parsed["slot_index"])
            slot_key = str(parsed["slot_key"])
            prefix_payload = by_prefix[prefix]
            prefix_payload["constraint_indices"].add(int(constraint_idx))
            prefix_payload["slot_indices"].add(slot_idx)
            prefix_payload["slot_keys"].add(slot_key)
            if len(prefix_payload["samples"]) < int(sample_limit):
                prefix_payload["samples"].append(
                    {
                        "constraint_idx": int(constraint_idx),
                        "slot_index": slot_idx,
                        "slot_key": slot_key,
                        "target_var_name": str(parsed["var_name"]),
                    }
                )
            slot_payload = slot_profiles.setdefault(
                slot_idx,
                {
                    "slot_index": slot_idx,
                    "slot_keys": set(),
                    "constraint_indices": set(),
                    "prefix_counts": {prefix: 0 for prefix in prefixes},
                },
            )
            slot_payload["slot_keys"].add(slot_key)
            slot_payload["constraint_indices"].add(int(constraint_idx))
            slot_payload["prefix_counts"][prefix] = int(
                slot_payload["prefix_counts"].get(prefix, 0)
            ) + 1
        for token, token_prefix_values in token_prefixes.items():
            token_matched = [
                prefix for prefix in matched_prefixes if prefix in set(token_prefix_values)
            ]
            if not token_matched:
                continue
            by_target[token]["constraint_indices"].add(int(constraint_idx))
            by_target[token]["slot_indices"].update(matched_slots)
            for prefix in token_matched:
                by_target[token]["prefix_counts"][prefix] = int(
                    by_target[token]["prefix_counts"].get(prefix, 0)
                ) + 1

    prefix_result: Dict[str, Any] = {}
    for prefix, payload in sorted(by_prefix.items()):
        prefix_result[prefix] = {
            "constraint_count": int(len(payload["constraint_indices"])),
            "unique_slot_count": int(len(payload["slot_indices"])),
            "slot_index_sample": sorted(payload["slot_indices"])[: int(sample_limit)],
            "slot_key_sample": sorted(payload["slot_keys"])[: int(sample_limit)],
            "samples": list(payload["samples"]),
        }
    target_result: Dict[str, Any] = {}
    for token, payload in sorted(by_target.items()):
        target_result[token] = {
            "constraint_count": int(len(payload["constraint_indices"])),
            "unique_slot_count": int(len(payload["slot_indices"])),
            "slot_index_sample": sorted(payload["slot_indices"])[: int(sample_limit)],
            "prefix_counts": {
                str(prefix): int(count)
                for prefix, count in sorted(payload["prefix_counts"].items())
                if int(count) > 0
            },
        }
    slot_samples = []
    for slot_idx in sorted(slot_profiles)[: int(sample_limit)]:
        payload = slot_profiles[slot_idx]
        slot_samples.append(
            {
                "slot_index": int(slot_idx),
                "slot_keys": sorted(payload["slot_keys"])[: int(sample_limit)],
                "constraint_count": int(len(payload["constraint_indices"])),
                "prefix_counts": {
                    str(prefix): int(count)
                    for prefix, count in sorted(payload["prefix_counts"].items())
                    if int(count) > 0
                },
            }
        )
    mapped_slots = {
        int(slot_idx)
        for payload in by_target.values()
        for slot_idx in payload["slot_indices"]
    }
    return {
        "powered_template": str(powered_template),
        "target_tokens": list(token_prefixes),
        "target_prefixes": prefixes,
        "element_constraint_count": int(element_constraint_count),
        "mapped_protocol_slot_count": int(len(mapped_slots)),
        "mapped_protocol_slot_index_sample": sorted(mapped_slots)[: int(sample_limit)],
        "by_prefix": prefix_result,
        "by_target_token": target_result,
        "slot_samples": slot_samples,
    }


def _parse_protocol_target_var_name(
    var_name: str,
    *,
    powered_template: str,
    prefixes: Sequence[str],
) -> Optional[Dict[str, Any]]:
    text = str(var_name)
    prefix = next((item for item in prefixes if text.startswith(str(item))), None)
    if prefix is None:
        return None
    body = text[len(str(prefix)) :]
    marker = f"::{str(powered_template)}::slot::"
    marker_idx = body.find(marker)
    if marker_idx < 0:
        return None
    slot_digit_start = marker_idx + len(marker)
    match = re.match(r"(\d+)", body[slot_digit_start:])
    if match is None:
        return None
    slot_index = int(match.group(1))
    slot_key_end = slot_digit_start + len(match.group(1))
    return {
        "prefix": str(prefix),
        "channel": _channel_from_prefix(str(prefix)),
        "slot_key": body[:slot_key_end],
        "slot_index": slot_index,
        "powered_template": str(powered_template),
        "var_name": text,
    }


def _forced_status_by_anchor_target(
    proto_reduction: Mapping[str, Any],
    *,
    powered_template: str,
    target_tokens: Sequence[str],
    anchor_indices: Sequence[int],
) -> Dict[str, Dict[str, Any]]:
    entries = list(_mapping(proto_reduction.get("reduction")).get("entries", []))
    allowed_targets = {"base", *[str(token) for token in target_tokens]}
    selected_anchors = {int(idx) for idx in anchor_indices}
    result: Dict[str, Dict[str, Any]] = {
        str(anchor_idx): {} for anchor_idx in sorted(selected_anchors)
    }
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        try:
            anchor_idx = int(entry.get("anchor_idx"))
        except Exception:
            continue
        if selected_anchors and anchor_idx not in selected_anchors:
            continue
        target = _target_from_variant(
            str(entry.get("variant", "")),
            powered_template=powered_template,
        )
        if target not in allowed_targets:
            continue
        anchor_payload = result.setdefault(str(anchor_idx), {})
        anchor_payload[str(target)] = {
            "variant": str(entry.get("variant", "")),
            "evaluated": bool(entry.get("evaluated", False)),
            "status": entry.get("status"),
            "removed_constraint_count": int(entry.get("removed_constraint_count", 0) or 0),
            "branches": int(entry.get("branches", 0) or 0),
            "conflicts": int(entry.get("conflicts", 0) or 0),
            "wall_time": entry.get("wall_time"),
            "deterministic_time": entry.get("deterministic_time"),
            "family_lookup_table_removed": bool(
                _mapping(entry.get("reduction_payload")).get(
                    "family_lookup_table_removed",
                    False,
                )
            ),
        }
    return result


def _family_bounds_by_anchor(
    anchor_differential: Mapping[str, Any],
    *,
    family_names: Sequence[str],
    anchor_indices: Sequence[int],
) -> Dict[str, Dict[str, Any]]:
    selected_anchors = {int(idx) for idx in anchor_indices}
    wanted = {str(name) for name in family_names}
    result: Dict[str, Dict[str, Any]] = {
        str(anchor_idx): {} for anchor_idx in sorted(selected_anchors)
    }
    for anchor in list(anchor_differential.get("anchors", [])):
        if not isinstance(anchor, Mapping):
            continue
        try:
            anchor_idx = int(anchor.get("anchor_idx"))
        except Exception:
            continue
        if selected_anchors and anchor_idx not in selected_anchors:
            continue
        family_payload = result.setdefault(str(anchor_idx), {})
        for ref in list(anchor.get("family_count_linear_refs", [])):
            if not isinstance(ref, Mapping):
                continue
            for bound in list(ref.get("active_family_count_bounds", [])):
                if not isinstance(bound, Mapping):
                    continue
                family_name = str(bound.get("family_name", ""))
                if family_name not in wanted:
                    continue
                current = _mapping(family_payload.get(family_name))
                if not current or float(
                    bound.get("implied_upper_when_anchor_active", float("inf"))
                ) < float(current.get("implied_upper_when_anchor_active", float("inf"))):
                    family_payload[family_name] = dict(bound)
    return result


def _compare_target_channel_signal(
    forced_status: Mapping[str, Mapping[str, Any]],
    target_channel_map: Mapping[str, Any],
    family_bounds: Mapping[str, Mapping[str, Any]],
    *,
    target_tokens: Sequence[str],
    family_names: Sequence[str],
) -> Dict[str, Any]:
    target_deltas = []
    by_target_token = _mapping(target_channel_map.get("by_target_token"))
    for token in target_tokens:
        statuses: Dict[str, Any] = {}
        removed_counts: Dict[str, int] = {}
        branches: Dict[str, int] = {}
        conflicts: Dict[str, int] = {}
        family_removed: Dict[str, bool] = {}
        for anchor_key, anchor_payload in sorted(forced_status.items()):
            entry = _mapping(_mapping(anchor_payload).get(str(token)))
            if not entry:
                continue
            statuses[str(anchor_key)] = entry.get("status")
            removed_counts[str(anchor_key)] = int(entry.get("removed_constraint_count", 0))
            branches[str(anchor_key)] = int(entry.get("branches", 0))
            conflicts[str(anchor_key)] = int(entry.get("conflicts", 0))
            family_removed[str(anchor_key)] = bool(entry.get("family_lookup_table_removed", False))
        mapped_count = int(_mapping(by_target_token.get(str(token))).get("constraint_count", 0) or 0)
        nonzero_removed = [count for count in removed_counts.values() if count > 0]
        target_deltas.append(
            {
                "target": str(token),
                "statuses_by_anchor": statuses,
                "removed_constraint_counts_by_anchor": removed_counts,
                "branches_by_anchor": branches,
                "conflicts_by_anchor": conflicts,
                "family_lookup_table_removed_by_anchor": family_removed,
                "mapped_constraint_count": mapped_count,
                "same_removed_constraint_count": len(set(nonzero_removed)) <= 1,
                "mapping_matches_artifact_count": (
                    bool(nonzero_removed) and all(count == mapped_count for count in nonzero_removed)
                ),
                "divergent_status": len({str(value) for value in statuses.values()}) > 1,
            }
        )
    family_deltas = []
    sorted_anchor_keys = sorted(str(key) for key in family_bounds.keys())
    for family_name in family_names:
        values: Dict[str, Any] = {}
        for anchor_key in sorted_anchor_keys:
            bound = _mapping(_mapping(family_bounds.get(anchor_key)).get(str(family_name)))
            if bound:
                values[anchor_key] = bound.get("implied_upper_when_anchor_active")
        delta = None
        if len(sorted_anchor_keys) >= 2:
            left = _mapping(_mapping(family_bounds.get(sorted_anchor_keys[0])).get(str(family_name)))
            right = _mapping(_mapping(family_bounds.get(sorted_anchor_keys[1])).get(str(family_name)))
            if left and right:
                delta = float(right.get("implied_upper_when_anchor_active")) - float(
                    left.get("implied_upper_when_anchor_active")
                )
        family_deltas.append(
            {
                "family_name": str(family_name),
                "implied_upper_by_anchor": values,
                "delta_second_minus_first": delta,
            }
        )
    divergent_targets = [
        str(delta.get("target"))
        for delta in target_deltas
        if bool(delta.get("divergent_status"))
    ]
    mapping_matches = all(
        bool(delta.get("mapping_matches_artifact_count"))
        for delta in target_deltas
        if _mapping(delta.get("removed_constraint_counts_by_anchor"))
    )
    return {
        "target_status_deltas": target_deltas,
        "family_bound_deltas": family_deltas,
        "divergent_targets": divergent_targets,
        "mapping_matches_artifact_counts": bool(mapping_matches),
        "interpretation": _interpret_signal(divergent_targets, family_deltas),
    }


def _summary(
    status: Mapping[str, Any],
    target_channel_map: Mapping[str, Any],
    forced_status: Mapping[str, Mapping[str, Any]],
    family_bounds: Mapping[str, Mapping[str, Any]],
    comparison: Mapping[str, Any],
) -> Dict[str, Any]:
    family_lookup_removed = any(
        bool(_mapping(entry).get("family_lookup_table_removed", False))
        for anchor_payload in forced_status.values()
        for entry in _mapping(anchor_payload).values()
    )
    mapped_slot_count = int(target_channel_map.get("mapped_protocol_slot_count", 0) or 0)
    family_bound_present = any(
        bool(_mapping(anchor_payload))
        for anchor_payload in family_bounds.values()
    )
    return {
        "evaluated": bool(status.get("evaluated", False)),
        "diagnostic_signal": comparison.get("interpretation"),
        "next_probe_hint": _next_probe_hint(comparison, family_bound_present),
        "mapped_protocol_slot_count": mapped_slot_count,
        "family_lookup_table_removed_in_target_split": bool(family_lookup_removed),
        "family_bounds_present": bool(family_bound_present),
        "mapping_matches_artifact_counts": bool(
            comparison.get("mapping_matches_artifact_counts", False)
        ),
    }


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
    proto_reduction_present: bool,
    anchor_differential_present: bool,
    selected_anchor_count: int,
    target_channel_map: Mapping[str, Any],
    comparison: Mapping[str, Any],
    family_bounds: Mapping[str, Mapping[str, Any]],
    family_names: Sequence[str],
    status: Mapping[str, Any],
    campaign_state_unchanged: bool,
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    family_bound_count = sum(
        1
        for anchor_payload in family_bounds.values()
        for family_name in family_names
        if family_name in _mapping(anchor_payload)
    )
    return [
        _check("no_solver_invoked", "pass", "audit builds/reads proto only"),
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
            "anchor_indices_present",
            "pass" if int(selected_anchor_count) > 0 else "fail",
            f"selected_anchor_count={int(selected_anchor_count)}",
        ),
        _check(
            "proto_reduction_artifact_present",
            "pass" if proto_reduction_present else "fail",
            "proto reduction artifact loaded"
            if proto_reduction_present
            else "proto reduction artifact missing",
        ),
        _check(
            "anchor_differential_artifact_present",
            "pass" if anchor_differential_present else "fail",
            "anchor differential artifact loaded"
            if anchor_differential_present
            else "anchor differential artifact missing",
        ),
        _check(
            "model_built",
            "pass" if bool(status.get("evaluated", False)) and model_error is None else "fail",
            "overlay proto built" if model_error is None else str(model_error),
        ),
        _check(
            "target_channel_mapping_nonempty",
            "pass" if int(target_channel_map.get("mapped_protocol_slot_count", 0) or 0) > 0 else "fail",
            f"mapped_protocol_slot_count={int(target_channel_map.get('mapped_protocol_slot_count', 0) or 0)}",
        ),
        _check(
            "target_mapping_matches_artifact_counts",
            "pass" if bool(comparison.get("mapping_matches_artifact_counts", False)) else "fail",
            f"mapping_matches_artifact_counts={bool(comparison.get('mapping_matches_artifact_counts', False))}",
        ),
        _check(
            "family_bounds_present",
            "pass" if family_bound_count > 0 else "fail",
            f"family_bound_count={int(family_bound_count)}",
        ),
        _check(
            "campaign_state_unchanged",
            "pass" if campaign_state_unchanged else "fail",
            "campaign state hash unchanged"
            if campaign_state_unchanged
            else "campaign state hash changed",
        ),
        _check(
            "diagnostic_not_proof_source",
            "pass",
            "artifact maps diagnostic deletion signals only; it is not exact proof",
        ),
    ]


def _target_from_variant(variant: str, *, powered_template: str) -> Optional[str]:
    if str(variant) == "base":
        return "base"
    pattern = (
        r"^remove_power_coverage_elements_template_"
        + re.escape(str(powered_template))
        + r"_target_(?P<target>[A-Za-z0-9_]+)"
        + r"(?P<mode>_element_linear)?"
        + r"(?P<suffix>_and_family_lookup_table|_keep_family_lookup_table)$"
    )
    match = re.match(pattern, str(variant))
    if match is None:
        return None
    return str(match.group("target"))


def _exact_env_overrides(
    *,
    power_family_lookup_encoding: Optional[str],
    power_pole_shell_distance_encoding: Optional[str],
    power_coverage_witness_encoding: Optional[str],
    power_coverage_witness_block_geometry: Optional[str],
    power_coverage_witness_block_size: Optional[int],
    power_coverage_witness_block_templates: Optional[str],
    power_coverage_selected_interval_encoding: Optional[str],
) -> Dict[str, str]:
    pairs = {
        "EXACT_POWER_FAMILY_LOOKUP_ENCODING": power_family_lookup_encoding,
        "EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING": power_pole_shell_distance_encoding,
        "EXACT_POWER_COVERAGE_WITNESS_ENCODING": power_coverage_witness_encoding,
        "EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY": power_coverage_witness_block_geometry,
        "EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE": power_coverage_witness_block_size,
        "EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES": power_coverage_witness_block_templates,
        "EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING": power_coverage_selected_interval_encoding,
    }
    return {
        str(key): str(value)
        for key, value in pairs.items()
        if value is not None
    }


@contextmanager
def _temporary_environ(overrides: Mapping[str, str]) -> Iterator[None]:
    previous = {str(key): os.environ.get(str(key)) for key in overrides}
    try:
        for key, value in overrides.items():
            os.environ[str(key)] = str(value)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(str(key), None)
            else:
                os.environ[str(key)] = value


def _normalize_tokens(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    for raw_value in values:
        token = str(raw_value).strip()
        if not token or token in result:
            continue
        _cover_choice_target_prefixes_from_token(token)
        result.append(token)
    return result


def _channel_from_prefix(prefix: str) -> str:
    text = str(prefix)
    if text.startswith("cover_choice_block_active__"):
        return "block_active"
    if text.startswith("cover_choice_block_x__"):
        return "block_x"
    if text.startswith("cover_choice_block_y__"):
        return "block_y"
    if text.startswith("cover_choice_active__"):
        return "active"
    if text.startswith("cover_choice_x__"):
        return "x"
    if text.startswith("cover_choice_y__"):
        return "y"
    return "unknown"


def _interpret_signal(
    divergent_targets: Sequence[str],
    family_deltas: Sequence[Mapping[str, Any]],
) -> str:
    targets = set(str(target) for target in divergent_targets)
    has_family_delta = any(
        item.get("delta_second_minus_first") is not None for item in family_deltas
    )
    if {"active_x", "active_y"}.intersection(targets) and has_family_delta:
        return "protocol_active_coordinate_target_channels_diverge_with_family_bound_delta"
    if targets:
        return "protocol_target_channel_status_divergence"
    if has_family_delta:
        return "family_bound_delta_without_target_status_divergence"
    return "no_new_divergence_detected"


def _next_probe_hint(comparison: Mapping[str, Any], family_bound_present: bool) -> str:
    divergent_targets = set(str(item) for item in list(comparison.get("divergent_targets", [])))
    if {"active_x", "active_y"}.intersection(divergent_targets) and family_bound_present:
        return "bisect protocol_storage_box active+coordinate target slots against family_009 bounds"
    if divergent_targets:
        return "replicate divergent target tokens with longer time/second seed before formulation changes"
    if family_bound_present:
        return "inspect family-bound deltas against surviving cover-choice slots"
    return "refresh missing artifacts before choosing a new probe"


def _cell(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
