from __future__ import annotations

import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import atomic_write_json, compute_exact_artifact_hashes, now_iso
from src.search.phase3b_anchor119_mixed_lane_tiling_verifier import (
    DEFAULT_ANCHOR_IDX,
    DEFAULT_CANDIDATE,
    DEFAULT_PLANTER_GROUP_ID,
    DEFAULT_PROTOCOL_GROUP_ID,
    _build_model,
    _find_group,
    _markdown_cell,
    _mapping,
    _parse_candidate,
    _planter_rows_by_xy,
    _protocol_rows_by_y,
    _sha256_file,
    _sha256_json,
)

ANCHOR119_MIXED_LANE_DP_CROSSCHECK_SOURCE = (
    "phase3b_anchor119_mixed_lane_dp_crosscheck_v1"
)


def build_phase3b_anchor119_mixed_lane_dp_crosscheck(
    project_root: Path,
    *,
    candidate: str = DEFAULT_CANDIDATE,
    anchor_idx: int = DEFAULT_ANCHOR_IDX,
    planter_group_id: str = DEFAULT_PLANTER_GROUP_ID,
    protocol_group_id: str = DEFAULT_PROTOCOL_GROUP_ID,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    reference_tiling_report_path: Path | None = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    started = time.perf_counter()
    report: Dict[str, Any] = {
        "metadata": {
            "source": ANCHOR119_MIXED_LANE_DP_CROSSCHECK_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "anchor119_mixed_lane_dp_crosscheck_not_campaign_proof",
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
            "tiling_verifier_module_sha256": _sha256_file(
                project_root / "src/search/phase3b_anchor119_mixed_lane_tiling_verifier.py"
            ),
            "master_model_sha256": _sha256_file(project_root / "src/models/master_model.py"),
            "exact_coordinate_master_sha256": _sha256_file(
                project_root / "src/models/exact_coordinate_master.py"
            ),
            "reference_tiling_report_path": (
                str(Path(reference_tiling_report_path))
                if reference_tiling_report_path is not None
                else None
            ),
            "reference_domain_rows_sha256": None,
            "domain_rows_sha256_matches_reference": None,
        },
        "status": {
            "completed": False,
            "outcome": "running",
            "runtime_promotion_ready": False,
            "exhaustive": False,
            "recommendation": "Mixed-lane DP cross-check is running.",
        },
        "domains": {},
        "crosscheck": {},
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

        audit = audit_anchor119_mixed_lane_dp_crosscheck(
            project_root=project_root,
            candidate=str(candidate),
            anchor_idx=int(anchor_idx),
            planter_group_id=str(planter_group_id),
            protocol_group_id=str(protocol_group_id),
            master_search_profile=str(master_search_profile),
        )
        report["candidate"].update(dict(audit.get("candidate", {})))
        report["domains"] = dict(audit.get("domains", {}))
        report["crosscheck"] = dict(audit.get("crosscheck", {}))
        report["witness"] = audit.get("witness")
        report["provenance"]["dp_domain_rows_sha256"] = _sha256_json(
            {
                "domains": report["domains"],
                "candidate": report["candidate"],
                "derivation": report["crosscheck"].get("derivation", {}),
            }
        )
        report["provenance"]["domain_rows_sha256"] = report["provenance"][
            "dp_domain_rows_sha256"
        ]
        _attach_reference_hash(report, project_root, reference_tiling_report_path)
        report["status"] = _status_from_crosscheck(audit)
    except Exception as exc:
        report["model_error"] = f"{type(exc).__name__}: {exc}"
        report["status"] = {
            "completed": True,
            "outcome": "diagnostic_error",
            "runtime_promotion_ready": False,
            "exhaustive": False,
            "recommendation": "Mixed-lane DP cross-check failed; inspect model_error.",
        }
    report["timing"]["total_seconds"] = float(time.perf_counter() - started)
    report["checks"] = _checks(report)
    return report


def audit_anchor119_mixed_lane_dp_crosscheck(
    *,
    project_root: Path,
    candidate: str,
    anchor_idx: int,
    planter_group_id: str,
    protocol_group_id: str,
    master_search_profile: str,
) -> Dict[str, Any]:
    model, delegate = _build_model(
        Path(project_root),
        candidate=str(candidate),
        master_search_profile=str(master_search_profile),
    )
    if delegate is None:
        raise RuntimeError("coordinate delegate unavailable")
    rect = _parse_candidate(candidate)
    ghost_domains = list(getattr(model, "_ghost_domains", []))
    if not (0 <= int(anchor_idx) < len(ghost_domains)):
        raise ValueError(f"anchor_idx unavailable: {anchor_idx}")
    anchor = dict(ghost_domains[int(anchor_idx)].get("anchor", {}))
    ghost = {
        "x": int(anchor["x"]),
        "y": int(anchor["y"]),
        "w": int(rect["w"]),
        "h": int(rect["h"]),
    }
    safe_y_min = int(ghost["y"] + ghost["h"])
    safe_y_end = int(getattr(model, "grid_h", 70))
    safe_height = int(safe_y_end - safe_y_min)
    safe_mask = (1 << safe_height) - 1

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
    choices_by_x = _lane_choices_by_x(planter_rows_by_xy, safe_y_min, safe_y_end)

    entries: list[Dict[str, Any]] = []
    witness = None
    total_initial_states = 0
    total_final_cover_states = 0
    total_p9_p10_pairs_checked = 0
    for protocol_y in sorted(protocol_rows_by_y):
        protocol_mask = _interval_mask(int(protocol_y), 9, safe_y_min, safe_y_end)
        if protocol_mask is None:
            entries.append(
                {
                    "protocol_y": int(protocol_y),
                    "protocol_modes": [
                        int(row["mode"]) for row in protocol_rows_by_y[int(protocol_y)]
                    ],
                    "status": "protocol_outside_safe_strip",
                    "state_counts": [],
                    "final_cover_states": 0,
                    "p9_p10_pairs_checked": 0,
                }
            )
            continue
        required_mask = int(safe_mask ^ protocol_mask)
        entry = {
            "protocol_y": int(protocol_y),
            "protocol_modes": [
                int(row["mode"]) for row in protocol_rows_by_y[int(protocol_y)]
            ],
            "status": None,
            "state_counts": [],
            "pattern_state_count": 0,
            "final_cover_states": 0,
            "p9_p10_pairs_checked": 0,
        }
        result = _dp_first_nine_slots(
            choices_by_x=choices_by_x,
            protocol_mask=int(protocol_mask),
            required_mask=int(required_mask),
            slot_count=9,
        )
        entry["state_counts"] = result["state_counts"]
        entry["pattern_state_count"] = int(result.get("pattern_state_count", 0))
        entry["final_cover_states"] = int(len(result["final_states"]))
        total_initial_states += int(sum(result["state_counts"]))
        total_final_cover_states += int(len(result["final_states"]))
        if not result["final_states"]:
            entry["status"] = "no_first_nine_exact_cover_states"
            entries.append(entry)
            continue
        p9_p10 = _check_p9_p10_tail(
            final_states=result["final_states"],
            x5_choices=choices_by_x.get(5, []),
        )
        entry["p9_p10_pairs_checked"] = int(p9_p10["pairs_checked"])
        total_p9_p10_pairs_checked += int(p9_p10["pairs_checked"])
        if p9_p10["witness"] is not None:
            entry["status"] = "witness_found"
            witness = {
                "protocol_y": int(protocol_y),
                "protocol": dict(protocol_rows_by_y[int(protocol_y)][0]),
                **dict(p9_p10["witness"]),
            }
            entries.append(entry)
            break
        entry["status"] = "no_p9_p10_tail"
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
            "lane_choice_counts": {
                str(x): int(len(rows)) for x, rows in sorted(choices_by_x.items())
            },
        },
        "crosscheck": {
            "algorithm": "safe_strip_bitmask_order_signature_dp",
            "derivation": {
                "safe_strip_height": int(safe_height),
                "first_nine_slots_height": 45,
                "protocol_height": 9,
                "first_nine_plus_protocol_exact_cover_height": 54,
                "p9_p10_x5_tail_rule": (
                    "P9/P10 at x=5 may only occupy safe-strip bits already occupied "
                    "by x0-prefix rows; this is checked from DP x0 occupancy masks."
                ),
            },
            "entry_count": int(len(entries)),
            "total_state_count_sum": int(total_initial_states),
            "total_final_cover_states": int(total_final_cover_states),
            "total_p9_p10_pairs_checked": int(total_p9_p10_pairs_checked),
            "entries": entries,
        },
        "witness": witness,
    }


def render_phase3b_anchor119_mixed_lane_dp_crosscheck_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    cross = _mapping(report.get("crosscheck"))
    candidate = _mapping(report.get("candidate"))
    domains = _mapping(report.get("domains"))
    provenance = _mapping(report.get("provenance"))
    lines = [
        "# Phase3B Anchor119 Mixed-Lane DP Cross-Check",
        "",
        f"- Outcome: `{status.get('outcome')}`",
        "- Solver invoked: false",
        "- Proof source: false",
        f"- Runtime promotion ready: `{bool(status.get('runtime_promotion_ready', False))}`",
        f"- Ghost rect: `{_mapping(candidate.get('ghost_rect'))}`",
        f"- Protocol row count: `{domains.get('protocol_row_count')}`",
        f"- Lane choice counts: `{_mapping(domains.get('lane_choice_counts'))}`",
        f"- Entry count: `{cross.get('entry_count')}`",
        f"- Final cover states: `{cross.get('total_final_cover_states')}`",
        f"- P9/P10 pairs checked: `{cross.get('total_p9_p10_pairs_checked')}`",
        f"- Domain hash match: `{provenance.get('domain_rows_sha256_matches_reference')}`",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                f"| {_markdown_cell(check.get('check_id'))} | "
                f"{_markdown_cell(check.get('status'))} | "
                f"{_markdown_cell(check.get('detail'))} |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_anchor119_mixed_lane_dp_crosscheck_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    cross = _mapping(report.get("crosscheck"))
    provenance = _mapping(report.get("provenance"))
    return "\n".join(
        [
            "Phase3B anchor119 mixed-lane DP cross-check",
            f"outcome={status.get('outcome')}",
            "solver_invoked=false",
            "proof_source=false",
            f"runtime_promotion_ready={bool(status.get('runtime_promotion_ready', False))}",
            f"entry_count={cross.get('entry_count')}",
            f"final_cover_states={cross.get('total_final_cover_states')}",
            f"p9p10_pairs_checked={cross.get('total_p9_p10_pairs_checked')}",
            f"witness_found={bool(report.get('witness'))}",
            f"domain_hash_match={provenance.get('domain_rows_sha256_matches_reference')}",
        ]
    ) + "\n"


def write_phase3b_anchor119_mixed_lane_dp_crosscheck(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "mixed_lane_dp_crosscheck",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_anchor119_mixed_lane_dp_crosscheck_markdown(report),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_anchor119_mixed_lane_dp_crosscheck_text(report),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _lane_choices_by_x(
    rows_by_xy: Mapping[Tuple[int, int], Sequence[Mapping[str, Any]]],
    safe_y_min: int,
    safe_y_end: int,
) -> Dict[int, list[Dict[str, Any]]]:
    choices: Dict[int, list[Dict[str, Any]]] = defaultdict(list)
    for (x, y), rows in rows_by_xy.items():
        mask = _interval_mask(int(y), 5, int(safe_y_min), int(safe_y_end))
        if mask is None:
            continue
        for row in rows:
            payload = dict(row)
            payload["mask"] = int(mask)
            choices[int(x)].append(payload)
    for x in list(choices):
        choices[x].sort(
            key=lambda row: (
                int(row["order_key"]),
                int(row["signature_id"]),
                int(row["mode"]),
                int(row["pose_index"]),
            )
        )
    return dict(choices)


def _dp_first_nine_slots(
    *,
    choices_by_x: Mapping[int, Sequence[Mapping[str, Any]]],
    protocol_mask: int,
    required_mask: int,
    slot_count: int,
) -> Dict[str, Any]:
    rows_by_xy: Dict[Tuple[int, int], list[Mapping[str, Any]]] = defaultdict(list)
    interval_choices: list[Dict[str, int]] = []
    seen_interval_keys: set[Tuple[int, int, int]] = set()
    for x in (0, 1):
        for row in list(choices_by_x.get(x, [])):
            key_xy = (int(row["x"]), int(row["y"]))
            rows_by_xy[key_xy].append(row)
            row_mask = int(row["mask"])
            if row_mask & int(protocol_mask):
                continue
            if row_mask | int(required_mask) != int(required_mask):
                continue
            key = (int(row["x"]), int(row["y"]), row_mask)
            if key in seen_interval_keys:
                continue
            seen_interval_keys.add(key)
            interval_choices.append({"x": int(row["x"]), "y": int(row["y"]), "mask": row_mask})
    interval_choices.sort(key=lambda item: (int(item["x"]), int(item["y"]), int(item["mask"])))
    choices_by_start: Dict[int, list[Dict[str, int]]] = defaultdict(list)
    for choice in interval_choices:
        choices_by_start[_lowest_set_bit(int(choice["mask"]))].append(choice)
    state_counts = [0 for _ in range(int(slot_count))]
    pattern_states: list[Tuple[int, list[Tuple[int, int, int]]]] = []

    def visit(slot_index: int, remaining_mask: int, mask_x0: int, phase: int, assignments: list[Tuple[int, int, int]]) -> None:
        if slot_index == int(slot_count):
            if int(remaining_mask) == 0:
                pattern_states.append((int(mask_x0), list(assignments)))
            return
        if int(remaining_mask) == 0:
            return
        start_bit = _lowest_set_bit(int(remaining_mask))
        for choice in list(choices_by_start.get(start_bit, [])):
            x = int(choice["x"])
            if x < int(phase):
                continue
            row_mask = int(choice["mask"])
            if row_mask | int(remaining_mask) != int(remaining_mask):
                continue
            state_counts[int(slot_index)] += 1
            next_mask_x0 = int(mask_x0 | row_mask) if x == 0 else int(mask_x0)
            assignments.append((int(slot_index), x, int(choice["y"])))
            visit(
                int(slot_index) + 1,
                int(remaining_mask ^ row_mask),
                next_mask_x0,
                max(int(phase), x),
                assignments,
            )
            assignments.pop()

    visit(0, int(required_mask), 0, 0, [])
    final_states: list[Dict[str, Any]] = []
    for mask_x0, assignments in pattern_states:
        for last_order, last_signature, sequence in _sequence_states_from_assignments(
            rows_by_xy,
            assignments,
        ):
            final_states.append(
                {
                    "mask_all": int(required_mask),
                    "mask_x0": int(mask_x0),
                    "last_order": int(last_order),
                    "last_signature": int(last_signature),
                    "sequence": sequence,
                }
            )
    return {
        "state_counts": state_counts,
        "pattern_state_count": int(len(pattern_states)),
        "final_states": final_states,
    }


def _sequence_states_from_assignments(
    rows_by_xy: Mapping[Tuple[int, int], Sequence[Mapping[str, Any]]],
    assignments: Sequence[Tuple[int, int, int]],
) -> list[Tuple[int, int, list[Dict[str, Any]]]]:
    states: list[Tuple[int, int, list[Dict[str, Any]]]] = [(-1, -1, [])]
    for slot_index, x, y in assignments:
        choices = list(rows_by_xy.get((int(x), int(y)), []))
        new_states: list[Tuple[int, int, list[Dict[str, Any]]]] = []
        for last_order, last_signature, seq in states:
            for row in choices:
                order = int(row["order_key"])
                signature = int(row["signature_id"])
                if order >= int(last_order) and signature >= int(last_signature):
                    new_states.append(
                        (
                            order,
                            signature,
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


def _check_p9_p10_tail(
    *,
    final_states: Sequence[Mapping[str, Any]],
    x5_choices: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    pairs_checked = 0
    for state in final_states:
        mask_x0 = int(state["mask_x0"])
        last_order = int(state["last_order"])
        last_sig = int(state["last_signature"])
        first_tail = [
            row
            for row in x5_choices
            if int(row["mask"]) | mask_x0 == mask_x0
            and int(row["order_key"]) >= last_order
            and int(row["signature_id"]) >= last_sig
        ]
        for p9 in first_tail:
            for p10 in first_tail:
                if int(p9["mask"]) & int(p10["mask"]):
                    continue
                pairs_checked += 1
                if (
                    int(p10["order_key"]) >= int(p9["order_key"])
                    and int(p10["signature_id"]) >= int(p9["signature_id"])
                ):
                    return {
                        "pairs_checked": int(pairs_checked),
                        "witness": {
                            "first_nine_sequence": list(state.get("sequence", [])),
                            "p9": dict(p9),
                            "p10": dict(p10),
                        },
                    }
    return {"pairs_checked": int(pairs_checked), "witness": None}


def _interval_mask(y: int, height: int, safe_y_min: int, safe_y_end: int) -> int | None:
    start = int(y) - int(safe_y_min)
    stop = int(y) + int(height) - int(safe_y_min)
    if start < 0 or stop > int(safe_y_end) - int(safe_y_min):
        return None
    return ((1 << int(height)) - 1) << int(start)


def _lowest_set_bit(value: int) -> int:
    if int(value) <= 0:
        raise ValueError("value must be positive")
    return int((int(value) & -int(value)).bit_length() - 1)


def _status_from_crosscheck(audit: Mapping[str, Any]) -> Dict[str, Any]:
    witness = audit.get("witness")
    if isinstance(witness, Mapping):
        outcome = "dp_crosscheck_witness_found"
        recommendation = (
            "Witness found; this disproves the local no-witness tiling candidate. "
            "Inspect witness and do not promote any precheck."
        )
        exhaustive = False
    else:
        outcome = "dp_crosscheck_exhaustive_no_witness"
        recommendation = (
            "Independent DP cross-check found no witness over the same safe-strip row domain. "
            "Still diagnostic-only until reviewed and tied to a guarded default-off precheck spec."
        )
        exhaustive = True
    return {
        "completed": True,
        "outcome": outcome,
        "runtime_promotion_ready": False,
        "exhaustive": bool(exhaustive),
        "recommendation": recommendation,
    }


def _checks(report: Mapping[str, Any]) -> list[Dict[str, Any]]:
    status = _mapping(report.get("status"))
    metadata = _mapping(report.get("metadata"))
    cross = _mapping(report.get("crosscheck"))
    provenance = _mapping(report.get("provenance"))
    return [
        _check("solver_not_invoked", "pass" if metadata.get("solver_invoked") is False else "fail", "custom DP only"),
        _check("diagnostic_not_proof_source", "pass" if metadata.get("proof_source") is False else "fail", "diagnostic only"),
        _check("runtime_not_promoted", "pass" if not bool(status.get("runtime_promotion_ready", False)) else "fail", "default-off diagnostic"),
        _check("crosscheck_completed", "pass" if bool(status.get("completed", False)) else "fail", str(status.get("outcome"))),
        _check("exhaustive_no_witness", "pass" if status.get("outcome") == "dp_crosscheck_exhaustive_no_witness" else "fail", str(status.get("outcome"))),
        _check("final_cover_states_counted", "pass" if int(cross.get("total_final_cover_states", 0)) > 0 else "fail", str(cross.get("total_final_cover_states"))),
        _check(
            "domain_hash_matches_reference",
            "pass" if provenance.get("domain_rows_sha256_matches_reference") is True else "skipped",
            str(provenance.get("domain_rows_sha256_matches_reference")),
        ),
    ]


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _attach_reference_hash(
    report: Dict[str, Any],
    project_root: Path,
    reference_tiling_report_path: Path | None,
) -> None:
    if reference_tiling_report_path is None:
        reference_tiling_report_path = (
            project_root
            / ".artifacts/phase3b_anchor119_mixed_lane_tiling_verifier_module_20260423"
            / "mixed_lane_tiling_verifier.json"
        )
    path = Path(reference_tiling_report_path)
    if not path.is_absolute():
        path = (project_root / path).resolve()
    report["provenance"]["reference_tiling_report_path"] = str(path)
    if not path.exists():
        return
    import json

    reference = json.loads(path.read_text(encoding="utf-8-sig"))
    ref_hash = _mapping(reference.get("provenance")).get("domain_rows_sha256")
    reference_payload = {
        "domains": _reference_compatible_domains(report.get("domains", {})),
        "candidate": report.get("candidate", {}),
        "derivation": _mapping(reference.get("derivation")),
    }
    compatible_hash = _sha256_json(reference_payload)
    report["provenance"]["reference_domain_rows_sha256"] = ref_hash
    report["provenance"]["reference_compatible_domain_rows_sha256"] = compatible_hash
    report["provenance"]["domain_rows_sha256"] = compatible_hash
    report["provenance"]["domain_rows_sha256_matches_reference"] = (
        ref_hash == compatible_hash
    )


def _reference_compatible_domains(value: Any) -> Dict[str, Any]:
    domains = _mapping(value)
    keys = [
        "planter_group_id",
        "planter_template",
        "planter_counts",
        "protocol_group_id",
        "protocol_template",
        "protocol_y_count",
        "protocol_row_count",
    ]
    return {key: domains.get(key) for key in keys}
