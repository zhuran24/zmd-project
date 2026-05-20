from __future__ import annotations

import hashlib
import itertools
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple

from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    MasterPlacementModel,
    load_generic_io_requirements_artifact,
    load_project_data,
)
from src.search.exact_campaign import atomic_write_json, compute_exact_artifact_hashes, now_iso

ANCHOR119_MIXED_LANE_TILING_VERIFIER_SOURCE = (
    "phase3b_anchor119_mixed_lane_tiling_verifier_v1"
)
DEFAULT_CANDIDATE = "67x13"
DEFAULT_ANCHOR_IDX = 119
DEFAULT_PLANTER_GROUP_ID = "group::manufacturing_5x5::planter_buckwheat::9"
DEFAULT_PROTOCOL_GROUP_ID = "group::protocol_core::protocol_core::18"


def build_phase3b_anchor119_mixed_lane_tiling_verifier(
    project_root: Path,
    *,
    candidate: str = DEFAULT_CANDIDATE,
    anchor_idx: int = DEFAULT_ANCHOR_IDX,
    planter_group_id: str = DEFAULT_PLANTER_GROUP_ID,
    protocol_group_id: str = DEFAULT_PROTOCOL_GROUP_ID,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    started = time.perf_counter()
    report: Dict[str, Any] = {
        "metadata": {
            "source": ANCHOR119_MIXED_LANE_TILING_VERIFIER_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "anchor119_local_mixed_lane_tiling_not_campaign_proof",
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "runtime_promotion_ready": False,
            "default_off": True,
        },
        "paths": {"project_root": str(project_root)},
        "candidate": {
            "key": str(candidate),
            "anchor_idx": int(anchor_idx),
            "ghost_rect": _parse_candidate(str(candidate)),
        },
        "profile": {
            "planter_group_id": str(planter_group_id),
            "protocol_group_id": str(protocol_group_id),
            "master_search_profile": str(master_search_profile),
            "skip_power_coverage": True,
        },
        "artifact_hashes": {},
        "artifact_hash_error": None,
        "provenance": {
            "module_sha256": _sha256_file(Path(__file__)),
            "master_model_sha256": _sha256_file(project_root / "src/models/master_model.py"),
            "exact_coordinate_master_sha256": _sha256_file(
                project_root / "src/models/exact_coordinate_master.py"
            ),
        },
        "status": {
            "completed": False,
            "outcome": "running",
            "runtime_promotion_ready": False,
            "recommendation": "Mixed-lane tiling verifier is running.",
        },
        "domains": {},
        "derivation": {},
        "enumeration": {},
        "witness": None,
        "timing": {},
        "model_error": None,
        "checks": [],
    }
    try:
        try:
            report["artifact_hashes"] = compute_exact_artifact_hashes(project_root)
        except Exception as exc:
            report["artifact_hash_error"] = f"{type(exc).__name__}: {exc}"

        model, delegate = _build_model(
            project_root,
            candidate=str(candidate),
            master_search_profile=str(master_search_profile),
        )
        if delegate is None:
            raise RuntimeError("coordinate delegate unavailable")
        audit = audit_anchor119_mixed_lane_tiling(
            model=model,
            delegate=delegate,
            candidate=str(candidate),
            anchor_idx=int(anchor_idx),
            planter_group_id=str(planter_group_id),
            protocol_group_id=str(protocol_group_id),
        )
        report["candidate"].update(dict(audit.get("candidate", {})))
        report["domains"] = dict(audit.get("domains", {}))
        report["derivation"] = dict(audit.get("derivation", {}))
        report["enumeration"] = dict(audit.get("enumeration", {}))
        report["witness"] = audit.get("witness")
        report["provenance"]["domain_rows_sha256"] = _sha256_json(
            {
                "domains": report["domains"],
                "candidate": report["candidate"],
                "derivation": report["derivation"],
            }
        )
        report["status"] = _status_from_audit(audit)
    except Exception as exc:
        report["model_error"] = f"{type(exc).__name__}: {exc}"
        report["status"] = {
            "completed": True,
            "outcome": "diagnostic_error",
            "runtime_promotion_ready": False,
            "recommendation": "Mixed-lane tiling verifier failed; inspect model_error.",
        }
    report["timing"]["total_seconds"] = float(time.perf_counter() - started)
    report["checks"] = _checks(report)
    return report


def audit_anchor119_mixed_lane_tiling(
    *,
    model: Any,
    delegate: Any,
    candidate: str,
    anchor_idx: int,
    planter_group_id: str,
    protocol_group_id: str,
) -> Dict[str, Any]:
    ghost_rect = _parse_candidate(candidate)
    ghost_domains = list(getattr(model, "_ghost_domains", []))
    if not (0 <= int(anchor_idx) < len(ghost_domains)):
        raise ValueError(f"anchor_idx unavailable: {anchor_idx}")
    anchor = dict(ghost_domains[int(anchor_idx)].get("anchor", {}))
    ghost = {
        "x": int(anchor["x"]),
        "y": int(anchor["y"]),
        "w": int(ghost_rect["w"]),
        "h": int(ghost_rect["h"]),
    }
    safe_y_min = int(ghost["y"] + ghost["h"])
    safe_y_end = int(getattr(model, "grid_h", 70))

    planter_group = _find_group(model, planter_group_id)
    protocol_group = _find_group(model, protocol_group_id)
    if planter_group is None:
        raise ValueError(f"planter group missing: {planter_group_id}")
    if protocol_group is None:
        raise ValueError(f"protocol group missing: {protocol_group_id}")
    planter_template = str(planter_group.get("facility_type", ""))
    protocol_template = str(protocol_group.get("facility_type", ""))
    planter_rows_by_xy, planter_counts = _planter_rows_by_xy(
        delegate,
        planter_group_id=str(planter_group_id),
        template=planter_template,
        ghost=ghost,
    )
    protocol_rows_by_y = _protocol_rows_by_y(
        delegate,
        template=protocol_template,
        ghost=ghost,
    )

    entries: list[Dict[str, Any]] = []
    witness = None
    total_patterns = 0
    total_p9p10_window_cases = 0
    for protocol_y in sorted(protocol_rows_by_y):
        entry: Dict[str, Any] = {
            "protocol_y": int(protocol_y),
            "protocol_modes": [
                int(row["mode"]) for row in protocol_rows_by_y[int(protocol_y)]
            ],
            "checked_patterns": 0,
            "checked_p9p10_windows": 0,
            "pattern_status_counts": {},
            "status": None,
        }
        if protocol_y < safe_y_min or (protocol_y - safe_y_min) % 5 != 0:
            entry["status"] = "capacity_alignment_impossible"
            entries.append(entry)
            continue
        before = list(range(safe_y_min, protocol_y, 5))
        after = list(range(protocol_y + 9, safe_y_end - 4, 5))
        y_slots = before + after
        if len(y_slots) != 9:
            entry["status"] = "capacity_alignment_impossible"
            entries.append(entry)
            continue
        for x0_prefix_count in range(0, 10):
            if x0_prefix_count > len(y_slots):
                continue
            for x0_ys_raw in itertools.combinations(y_slots, x0_prefix_count):
                x0_ys = tuple(sorted(int(y) for y in x0_ys_raw))
                x1_ys = tuple(int(y) for y in y_slots if int(y) not in set(x0_ys))
                entry["checked_patterns"] += 1
                total_patterns += 1
                assignments = []
                for slot_index, y_value in enumerate(x0_ys):
                    assignments.append((int(slot_index), 0, int(y_value)))
                for offset, y_value in enumerate(sorted(x1_ys)):
                    assignments.append((int(x0_prefix_count + offset), 1, int(y_value)))
                states = _sequence_states(planter_rows_by_xy, assignments)
                if not states:
                    _count(entry, "p0_p8_order_signature_no_rows")
                    continue
                x0_intervals = [(int(y), int(y + 5)) for y in x0_ys]
                p9_p10_windows = _p9_p10_windows(planter_rows_by_xy, x0_intervals)
                if not p9_p10_windows:
                    _count(entry, "no_x5_windows_inside_x0_union")
                    continue
                found = False
                for last_order, last_signature, seq in states:
                    for y9, y10 in p9_p10_windows:
                        entry["checked_p9p10_windows"] += 1
                        total_p9p10_window_cases += 1
                        p9_rows = planter_rows_by_xy.get((5, int(y9)), [])
                        p10_rows = planter_rows_by_xy.get((5, int(y10)), [])
                        for p9 in p9_rows:
                            if (
                                int(p9["order_key"]) < int(last_order)
                                or int(p9["signature_id"]) < int(last_signature)
                            ):
                                continue
                            for p10 in p10_rows:
                                if (
                                    int(p10["order_key"]) >= int(p9["order_key"])
                                    and int(p10["signature_id"]) >= int(p9["signature_id"])
                                ):
                                    witness = {
                                        "protocol": dict(protocol_rows_by_y[int(protocol_y)][0]),
                                        "protocol_y": int(protocol_y),
                                        "x0_prefix_count": int(x0_prefix_count),
                                        "x0_ys": list(x0_ys),
                                        "x1_ys": list(sorted(x1_ys)),
                                        "p9_y": int(y9),
                                        "p10_y": int(y10),
                                        "planter_slots": [
                                            dict(item) for item in seq
                                        ]
                                        + [
                                            {"slot_index": 9, **dict(p9)},
                                            {"slot_index": 10, **dict(p10)},
                                        ],
                                    }
                                    found = True
                                    break
                            if found:
                                break
                        if found:
                            break
                    if found:
                        break
                if found:
                    entry["status"] = "witness_found"
                    entries.append(entry)
                    break
                _count(entry, "p9_p10_order_signature_no_rows")
            if witness is not None:
                break
        if witness is not None:
            break
        if entry["status"] is None:
            entry["status"] = "no_pattern_witness"
        entries.append(entry)

    return {
        "candidate": {
            "anchor_idx": int(anchor_idx),
            "ghost_rect": ghost,
            "safe_strip": {"y_min": int(safe_y_min), "y_end": int(safe_y_end)},
        },
        "domains": {
            "planter_group_id": str(planter_group_id),
            "planter_template": planter_template,
            "planter_counts": planter_counts,
            "protocol_group_id": str(protocol_group_id),
            "protocol_template": protocol_template,
            "protocol_y_count": int(len(protocol_rows_by_y)),
            "protocol_row_count": int(sum(len(rows) for rows in protocol_rows_by_y.values())),
        },
        "derivation": {
            "p0_p8_plus_protocol_height": 54,
            "p0_p8_plus_protocol_exact_tiling": True,
            "p9_x5_necessity": (
                "For x=1..4, P9 overlaps every x0/x1/protocol lane while "
                "P0..P8+C0 exactly tile the safe strip; only x=5 can avoid x0-prefix overlap."
            ),
            "p9_p10_window_rule": (
                "P9/P10 at x=5 must be non-overlapping 5-high intervals contained "
                "in the union of x0-prefix planter intervals."
            ),
        },
        "enumeration": {
            "entry_count": int(len(entries)),
            "total_patterns": int(total_patterns),
            "total_p9p10_window_cases": int(total_p9p10_window_cases),
            "entries": entries,
        },
        "witness": witness,
    }


def render_phase3b_anchor119_mixed_lane_tiling_verifier_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    enum = _mapping(report.get("enumeration"))
    candidate = _mapping(report.get("candidate"))
    domains = _mapping(report.get("domains"))
    lines = [
        "# Phase3B Anchor119 Mixed-Lane Tiling Verifier",
        "",
        f"- Outcome: `{status.get('outcome')}`",
        "- Solver invoked: false",
        "- Proof source: false",
        f"- Runtime promotion ready: `{bool(status.get('runtime_promotion_ready', False))}`",
        f"- Ghost rect: `{_mapping(candidate.get('ghost_rect'))}`",
        f"- Planter counts: `{_mapping(domains.get('planter_counts'))}`",
        f"- Protocol row count: `{domains.get('protocol_row_count')}`",
        f"- Total patterns: `{enum.get('total_patterns')}`",
        f"- P9/P10 window cases: `{enum.get('total_p9p10_window_cases')}`",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Witness",
        "",
    ]
    witness = report.get("witness")
    if isinstance(witness, Mapping):
        lines.extend(
            [
                f"- Protocol y: `{witness.get('protocol_y')}`",
                f"- P9/P10 y: `{witness.get('p9_y')}`, `{witness.get('p10_y')}`",
                "",
                "| Slot | x | y | mode | signature |",
                "| ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in list(witness.get("planter_slots", [])):
            if isinstance(row, Mapping):
                lines.append(
                    f"| {row.get('slot_index')} | {row.get('x')} | {row.get('y')} | "
                    f"{row.get('mode')} | {row.get('signature_id')} |"
                )
    else:
        lines.append("No witness found in exhaustive exact tiling enumeration.")
    lines.extend(
        [
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
                f"| {_markdown_cell(check.get('check_id'))} | "
                f"{_markdown_cell(check.get('status'))} | "
                f"{_markdown_cell(check.get('detail'))} |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_anchor119_mixed_lane_tiling_verifier_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    enum = _mapping(report.get("enumeration"))
    return "\n".join(
        [
            "Phase3B anchor119 mixed-lane tiling verifier",
            f"outcome={status.get('outcome')}",
            "solver_invoked=false",
            "proof_source=false",
            f"runtime_promotion_ready={bool(status.get('runtime_promotion_ready', False))}",
            f"total_patterns={enum.get('total_patterns')}",
            f"p9p10_window_cases={enum.get('total_p9p10_window_cases')}",
            f"witness_found={bool(report.get('witness'))}",
        ]
    ) + "\n"


def write_phase3b_anchor119_mixed_lane_tiling_verifier(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "mixed_lane_tiling_verifier",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_anchor119_mixed_lane_tiling_verifier_markdown(report),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_anchor119_mixed_lane_tiling_verifier_text(report),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _build_model(
    project_root: Path,
    *,
    candidate: str,
    master_search_profile: str,
) -> Tuple[Any, Any]:
    instances, pools, rules = load_project_data(project_root, solve_mode="certified_exact")
    generic = load_generic_io_requirements_artifact(project_root)
    rect = _parse_candidate(candidate)
    core = MasterPlacementModel.build_exact_core(
        instances,
        pools,
        rules,
        skip_power_coverage=True,
        generic_io_requirements=generic,
        master_search_profile=str(master_search_profile),
    )
    model = MasterPlacementModel.from_exact_core(
        core,
        ghost_rect=(int(rect["w"]), int(rect["h"])),
        master_search_profile=str(master_search_profile),
    )
    model.build()
    return model, getattr(model, "_coordinate_delegate", None)


def _planter_rows_by_xy(
    delegate: Any,
    *,
    planter_group_id: str,
    template: str,
    ghost: Mapping[str, int],
) -> Tuple[Dict[Tuple[int, int], list[Dict[str, Any]]], Dict[str, Any]]:
    slots = list(getattr(delegate, "mandatory_slots", {}).get(str(planter_group_id), []))
    if not slots:
        raise ValueError(f"missing planter slots: {planter_group_id}")
    signature_by_bucket = {
        str(bucket_id): int(signature_id)
        for signature_id, bucket_id in dict(slots[0].signature_id_to_bucket_id).items()
    }
    pose_to_signature: Dict[int, int] = {}
    bucket_pose_indices = dict(
        getattr(delegate, "_mandatory_group_bucket_pose_indices", {}).get(
            str(planter_group_id),
            {},
        )
    )
    for bucket_id, pose_indices in bucket_pose_indices.items():
        if str(bucket_id) not in signature_by_bucket:
            continue
        for pose_idx in list(pose_indices):
            pose_to_signature[int(pose_idx)] = int(signature_by_bucket[str(bucket_id)])
    mode_count = len(dict(getattr(delegate, "_template_mode_id_by_token", {}).get(str(template), {})))
    rows_by_xy: Dict[Tuple[int, int], list[Dict[str, Any]]] = defaultdict(list)
    raw_count = 0
    kept_count = 0
    signature_counts: Dict[int, int] = defaultdict(int)
    for pose_idx, row in dict(
        getattr(delegate, "_template_pose_tuple_by_idx", {}).get(str(template), {})
    ).items():
        signature_id = pose_to_signature.get(int(pose_idx))
        if signature_id is None:
            continue
        raw_count += 1
        x, y, mode = (int(row[0]), int(row[1]), int(row[2]))
        if _rect_overlaps_ghost(x, y, 5, 5, ghost):
            continue
        row_payload = {
            "x": int(x),
            "y": int(y),
            "mode": int(mode),
            "signature_id": int(signature_id),
            "pose_index": int(pose_idx),
            "order_key": _order_key(x, y, mode, mode_count),
            "rect": {"x": int(x), "y": int(y), "w": 5, "h": 5},
        }
        rows_by_xy[(int(x), int(y))].append(row_payload)
        kept_count += 1
        signature_counts[int(signature_id)] += 1
    for key in list(rows_by_xy):
        rows_by_xy[key].sort(key=lambda item: (int(item["signature_id"]), int(item["order_key"])))
    counts = {
        "raw_pose_rows": int(raw_count),
        "kept_rows_avoiding_anchor": int(kept_count),
        "xy_cell_count": int(len(rows_by_xy)),
        "signature_counts": {str(k): int(v) for k, v in sorted(signature_counts.items())},
    }
    return dict(rows_by_xy), counts


def _protocol_rows_by_y(
    delegate: Any,
    *,
    template: str,
    ghost: Mapping[str, int],
) -> Dict[int, list[Dict[str, Any]]]:
    mode_count = len(dict(getattr(delegate, "_template_mode_id_by_token", {}).get(str(template), {})))
    rows_by_y: Dict[int, list[Dict[str, Any]]] = defaultdict(list)
    for pose_idx, row in dict(
        getattr(delegate, "_template_pose_tuple_by_idx", {}).get(str(template), {})
    ).items():
        x, y, mode = (int(row[0]), int(row[1]), int(row[2]))
        if int(x) != 1:
            continue
        if _rect_overlaps_ghost(x, y, 9, 9, ghost):
            continue
        rows_by_y[int(y)].append(
            {
                "x": int(x),
                "y": int(y),
                "mode": int(mode),
                "pose_index": int(pose_idx),
                "order_key": _order_key(x, y, mode, mode_count),
                "rect": {"x": int(x), "y": int(y), "w": 9, "h": 9},
            }
        )
    for key in list(rows_by_y):
        rows_by_y[key].sort(key=lambda item: int(item["mode"]))
    return dict(rows_by_y)


def _sequence_states(
    rows_by_xy: Mapping[Tuple[int, int], Sequence[Mapping[str, Any]]],
    assignments: Sequence[Tuple[int, int, int]],
) -> list[Tuple[int, int, list[Dict[str, Any]]]]:
    states: list[Tuple[int, int, list[Dict[str, Any]]]] = [(-1, -1, [])]
    for slot_index, x, y in assignments:
        choices = list(rows_by_xy.get((int(x), int(y)), []))
        new_states: list[Tuple[int, int, list[Dict[str, Any]]]] = []
        for last_order, last_signature, seq in states:
            for row in choices:
                if (
                    int(row["order_key"]) >= int(last_order)
                    and int(row["signature_id"]) >= int(last_signature)
                ):
                    new_states.append(
                        (
                            int(row["order_key"]),
                            int(row["signature_id"]),
                            list(seq) + [{"slot_index": int(slot_index), **dict(row)}],
                        )
                    )
        best_by_signature: Dict[int, Tuple[int, int, list[Dict[str, Any]]]] = {}
        for order, signature, seq in new_states:
            if signature not in best_by_signature or order < best_by_signature[signature][0]:
                best_by_signature[signature] = (order, signature, seq)
        states = list(best_by_signature.values())
        if not states:
            return []
    return states


def _p9_p10_windows(
    rows_by_xy: Mapping[Tuple[int, int], Sequence[Mapping[str, Any]]],
    x0_intervals: Sequence[Tuple[int, int]],
) -> list[Tuple[int, int]]:
    windows: list[Tuple[int, int]] = []
    for y9 in range(16, 66):
        if not _interval_subset_of_union(y9, 5, x0_intervals):
            continue
        if not rows_by_xy.get((5, int(y9))):
            continue
        for y10 in range(int(y9) + 5, 66):
            if not _interval_subset_of_union(y10, 5, x0_intervals):
                continue
            if not rows_by_xy.get((5, int(y10))):
                continue
            windows.append((int(y9), int(y10)))
    return windows


def _interval_subset_of_union(
    y: int,
    height: int,
    intervals: Sequence[Tuple[int, int]],
) -> bool:
    pos = int(y)
    end = int(y) + int(height)
    for start, stop in sorted((int(a), int(b)) for a, b in intervals):
        if stop <= pos:
            continue
        if start > pos:
            return False
        pos = max(pos, stop)
        if pos >= end:
            return True
    return False


def _status_from_audit(audit: Mapping[str, Any]) -> Dict[str, Any]:
    witness = audit.get("witness")
    outcome = (
        "exact_tiling_witness_found"
        if isinstance(witness, Mapping)
        else "exact_tiling_exhaustive_no_witness"
    )
    if isinstance(witness, Mapping):
        recommendation = (
            "Witness found; local planter/protocol no-witness certificate is disproved. "
            "Expand dependency cut before precheck work."
        )
    else:
        recommendation = (
            "Exact tiling verifier found no witness; keep diagnostic until independent "
            "DP/tests and provenance checks agree."
        )
    return {
        "completed": True,
        "outcome": outcome,
        "runtime_promotion_ready": False,
        "exhaustive": True,
        "recommendation": recommendation,
    }


def _checks(report: Mapping[str, Any]) -> list[Dict[str, Any]]:
    status = _mapping(report.get("status"))
    metadata = _mapping(report.get("metadata"))
    enum = _mapping(report.get("enumeration"))
    return [
        _check("solver_not_invoked", "pass" if metadata.get("solver_invoked") is False else "fail", "no CP-SAT solve"),
        _check("diagnostic_not_proof_source", "pass" if metadata.get("proof_source") is False else "fail", "diagnostic only"),
        _check("runtime_not_promoted", "pass" if not bool(status.get("runtime_promotion_ready", False)) else "fail", "default-off diagnostic"),
        _check("enumeration_completed", "pass" if bool(status.get("completed", False)) else "fail", str(status.get("outcome"))),
        _check("patterns_counted", "pass" if int(enum.get("total_patterns", 0)) > 0 else "fail", str(enum.get("total_patterns"))),
    ]


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _parse_candidate(candidate: str) -> Dict[str, int]:
    left, right = str(candidate).lower().split("x", 1)
    w = int(left)
    h = int(right)
    return {"w": int(w), "h": int(h), "area": int(w * h)}


def _find_group(model: Any, group_id: str) -> Mapping[str, Any] | None:
    for group in list(getattr(model, "_mandatory_groups", [])):
        if str(_mapping(group).get("group_id")) == str(group_id):
            return _mapping(group)
    return None


def _overlap(a0: int, a1: int, b0: int, b1: int) -> bool:
    return not (int(a1) <= int(b0) or int(b1) <= int(a0))


def _rect_overlaps_ghost(
    x: int,
    y: int,
    w: int,
    h: int,
    ghost: Mapping[str, int],
) -> bool:
    return _overlap(int(x), int(x) + int(w), int(ghost["x"]), int(ghost["x"]) + int(ghost["w"])) and _overlap(
        int(y),
        int(y) + int(h),
        int(ghost["y"]),
        int(ghost["y"]) + int(ghost["h"]),
    )


def _order_key(x: int, y: int, mode: int, mode_count: int) -> int:
    return int(x) * 70 * int(mode_count) + int(y) * int(mode_count) + int(mode)


def _count(entry: Dict[str, Any], key: str) -> None:
    counts = entry.setdefault("pattern_status_counts", {})
    counts[str(key)] = int(counts.get(str(key), 0)) + 1


def _sha256_file(path: Path) -> str | None:
    path = Path(path)
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_json(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")

