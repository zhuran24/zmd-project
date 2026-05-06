from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import atomic_write_json, now_iso
from src.search.phase3b_b5a_coordinate_validation_reason_localization import (
    B5A_COORDINATE_VALIDATION_REASON_LOCALIZATION_SOURCE,
)

B5A_LOCALIZED_EVIDENCE_READINESS_SOURCE = (
    "phase3b_b5a_localized_evidence_readiness_v1"
)

DEFAULT_REASON_LOCALIZATION_PATH = Path(
    ".artifacts/phase3b_b5a_coordinate_validation_reason_localization_20260425/"
    "b5a_coordinate_validation_reason_localization.json"
)
DEFAULT_POST_ACCEPTANCE_PREFLIGHT_PATH = Path(
    ".artifacts/phase3b_long_run_preflight_after_acceptance_refresh_20260425/"
    "preflight_summary.json"
)
DEFAULT_SIGNATURE_RUNTIME_PROBE_PATH = Path(
    ".artifacts/phase3b_signature_monotonic_runtime_probe_anchor119/"
    "signature_monotonic_runtime_probe_anchor119.json"
)
DEFAULT_GHOST_RUNTIME_PROBE_PATH = Path(
    ".artifacts/phase3b_ghost_overlap_forced_domain_runtime_probe_anchor118/"
    "ghost_overlap_forced_domain_runtime_probe_anchor118.json"
)
DEFAULT_SIGNATURE_PRECEDENT_PATH = Path(
    ".artifacts/phase3b_signature_monotonic_precheck_promotion_spec/"
    "promotion_spec.json"
)

EXPECTED_SIGNATURE_ANCHORS = tuple(range(119, 126))
EXPECTED_GHOST_ANCHOR = 118


def build_phase3b_b5a_localized_evidence_readiness(
    project_root: Path,
    *,
    reason_localization_path: Optional[Path] = None,
    post_acceptance_preflight_path: Optional[Path] = None,
    signature_runtime_probe_path: Optional[Path] = None,
    ghost_runtime_probe_path: Optional[Path] = None,
    signature_precedent_path: Optional[Path] = None,
    expected_candidate: str = "67x13",
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    reason_path = _resolve_path(
        project_root,
        reason_localization_path
        if reason_localization_path is not None
        else DEFAULT_REASON_LOCALIZATION_PATH,
    )
    preflight_path = _resolve_path(
        project_root,
        post_acceptance_preflight_path
        if post_acceptance_preflight_path is not None
        else DEFAULT_POST_ACCEPTANCE_PREFLIGHT_PATH,
    )
    signature_probe_path = _resolve_path(
        project_root,
        signature_runtime_probe_path
        if signature_runtime_probe_path is not None
        else DEFAULT_SIGNATURE_RUNTIME_PROBE_PATH,
    )
    ghost_probe_path = _resolve_path(
        project_root,
        ghost_runtime_probe_path
        if ghost_runtime_probe_path is not None
        else DEFAULT_GHOST_RUNTIME_PROBE_PATH,
    )
    precedent_path = _resolve_path(
        project_root,
        signature_precedent_path
        if signature_precedent_path is not None
        else DEFAULT_SIGNATURE_PRECEDENT_PATH,
    )

    reason, reason_error = _load_json_mapping(reason_path)
    preflight, preflight_error = _load_json_mapping(preflight_path)
    signature_probe, signature_probe_error = _load_json_mapping(signature_probe_path)
    ghost_probe, ghost_probe_error = _load_json_mapping(ghost_probe_path)
    precedent, precedent_error = _load_json_mapping(precedent_path)

    reason_meta = _mapping(reason.get("metadata")) if reason else {}
    reason_status = _mapping(reason.get("status")) if reason else {}
    selected_surface = _mapping(reason.get("selected_surface")) if reason else {}
    reason_rows = _anchor_rows(reason)
    candidate_key = str(selected_surface.get("candidate_key", ""))
    failed_checks = _failed_preflight_checks(preflight)
    preflight_only_b5a_failed = failed_checks == ["b5a_anchor_found"]

    reason_source_supported = (
        reason_meta.get("source") == B5A_COORDINATE_VALIDATION_REASON_LOCALIZATION_SOURCE
    )
    reason_safe_flags = (
        reason_meta.get("solver_invoked") is False
        and reason_meta.get("checkpoint_written") is False
        and reason_status.get("proof_source") is False
        and reason_status.get("runtime_semantics_changed") is False
    )
    reason_ready = bool(reason_status.get("reason_localization_ready", False))
    candidate_matches = candidate_key == str(expected_candidate)

    ghost_lane = _ghost_lane(
        reason_rows,
        ghost_probe=ghost_probe,
        ghost_probe_error=ghost_probe_error,
        current_source_ok=bool(
            reason is not None
            and reason_error is None
            and reason_source_supported
            and reason_ready
            and reason_safe_flags
            and candidate_matches
        ),
    )
    signature_lane = _signature_lane(
        reason_rows,
        signature_probe=signature_probe,
        signature_probe_error=signature_probe_error,
        precedent=precedent,
        precedent_error=precedent_error,
        current_source_ok=bool(
            reason is not None
            and reason_error is None
            and reason_source_supported
            and reason_ready
            and reason_safe_flags
            and candidate_matches
        ),
    )

    lanes = [ghost_lane, signature_lane]
    readiness_ready = all(bool(lane.get("current_source_complete")) for lane in lanes)
    readiness_ready = bool(
        readiness_ready
        and reason is not None
        and reason_error is None
        and reason_source_supported
        and reason_safe_flags
        and reason_ready
        and candidate_matches
        and preflight is not None
        and preflight_error is None
        and preflight_only_b5a_failed
    )

    checks = _checks(
        reason_present=reason is not None and reason_error is None,
        reason_error=reason_error,
        reason_source_supported=reason_source_supported,
        reason_ready=reason_ready,
        reason_safe_flags=reason_safe_flags,
        candidate_matches=candidate_matches,
        candidate_key=candidate_key,
        expected_candidate=str(expected_candidate),
        preflight_present=preflight is not None and preflight_error is None,
        preflight_error=preflight_error,
        preflight_only_b5a_failed=preflight_only_b5a_failed,
        failed_checks=failed_checks,
        ghost_lane=ghost_lane,
        signature_lane=signature_lane,
    )

    return {
        "metadata": {
            "source": B5A_LOCALIZED_EVIDENCE_READINESS_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": (
                "localized_evidence_readiness_report_only_not_proof_source"
            ),
            "solver_invoked": False,
            "checkpoint_written": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "candidate_elimination_claim": False,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
            "runtime_elimination_authorized": False,
            "final_168h_authorized": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
            "preflight_gate_mutated": False,
        },
        "paths": {
            "project_root": str(project_root),
            "reason_localization": _display_path(project_root, reason_path),
            "post_acceptance_preflight": _display_path(project_root, preflight_path),
            "signature_runtime_probe": _display_path(project_root, signature_probe_path),
            "ghost_runtime_probe": _display_path(project_root, ghost_probe_path),
            "signature_precedent": _display_path(project_root, precedent_path),
        },
        "inputs": {
            "reason_localization": {
                "present": reason is not None,
                "load_error": reason_error,
                "source_supported": reason_source_supported,
                "reason_localization_ready": reason_ready,
                "safe_flags": reason_safe_flags,
                "candidate_key": candidate_key,
            },
            "post_acceptance_preflight": {
                "present": preflight is not None,
                "load_error": preflight_error,
                "ready_for_final_long_run": bool(
                    _mapping(preflight).get(
                        "ready_for_final_long_run",
                        _mapping(preflight).get("ready", False),
                    )
                ),
                "failed_checks": failed_checks,
                "only_b5a_anchor_found_failed": preflight_only_b5a_failed,
            },
            "signature_runtime_probe": {
                "present": signature_probe is not None,
                "load_error": signature_probe_error,
            },
            "ghost_runtime_probe": {
                "present": ghost_probe is not None,
                "load_error": ghost_probe_error,
            },
            "signature_precedent": {
                "present": precedent is not None,
                "load_error": precedent_error,
                "role": "design_precedent_only_not_current_b5a_evidence",
            },
        },
        "status": {
            "completed": True,
            "readiness_ready": readiness_ready,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
            "checkpoint_written": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "candidate_elimination_claim": False,
            "runtime_elimination_authorized": False,
            "final_168h_authorized": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
            "preflight_gate_mutated": False,
            "outcome": (
                "b5a_localized_evidence_readiness_ready_for_review"
                if readiness_ready
                else "b5a_localized_evidence_readiness_blocked"
            ),
            "recommendation": _recommendation(readiness_ready),
        },
        "candidate": {
            "expected_key": str(expected_candidate),
            "localized_key": candidate_key,
            "matches": candidate_matches,
        },
        "lanes": lanes,
        "old_signature_precedent_policy": {
            "old_m6x4_signature_artifact_present": precedent is not None,
            "old_m6x4_signature_artifact_used_as_current_b5a_evidence": False,
            "required_current_source": (
                "2026-04-25 B5A reason-localization anchors 119-125"
            ),
            "policy": (
                "The older signature promotion spec may guide implementation, but it "
                "cannot satisfy B5A localized evidence without current-source anchor rows."
            ),
        },
        "checks": checks,
    }


def render_phase3b_b5a_localized_evidence_readiness_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    candidate = _mapping(report.get("candidate"))
    lines = [
        "# Phase 3B B5A Localized Evidence Readiness",
        "",
        f"- Outcome: {_markdown_cell(status.get('outcome'))}",
        f"- Readiness ready: {_markdown_cell(status.get('readiness_ready'))}",
        f"- Certified anchor found: {_markdown_cell(status.get('certified_anchor_found'))}",
        f"- Proof source: {_markdown_cell(status.get('proof_source'))}",
        f"- Runtime semantics changed: {_markdown_cell(status.get('runtime_semantics_changed'))}",
        f"- Candidate: {_markdown_cell(candidate.get('localized_key'))}",
        f"- Recommendation: {_markdown_cell(status.get('recommendation'))}",
        "",
        "## Evidence Lanes",
        "",
        "| Lane | Category | Covered anchors | Current-source complete | Probe support | Missing gates |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for lane in list(report.get("lanes", [])):
        if not isinstance(lane, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(lane.get("lane_id")),
                    _markdown_cell(lane.get("category")),
                    _markdown_cell(lane.get("covered_anchors")),
                    _markdown_cell(lane.get("current_source_complete")),
                    _markdown_cell(lane.get("probe_supports_lane")),
                    _markdown_cell(lane.get("missing_gates")),
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


def render_phase3b_b5a_localized_evidence_readiness_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    candidate = _mapping(report.get("candidate"))
    lines = [
        "Phase 3B B5A localized evidence readiness",
        f"outcome={status.get('outcome')}",
        f"readiness_ready={status.get('readiness_ready')}",
        f"certified_anchor_found={status.get('certified_anchor_found')}",
        f"proof_source={status.get('proof_source')}",
        f"runtime_semantics_changed={status.get('runtime_semantics_changed')}",
        f"candidate={candidate.get('localized_key')}",
    ]
    for lane in list(report.get("lanes", [])):
        if isinstance(lane, Mapping):
            lines.append(
                "lane "
                f"id={lane.get('lane_id')} "
                f"category={lane.get('category')} "
                f"covered_anchors={lane.get('covered_anchors')} "
                f"current_source_complete={lane.get('current_source_complete')} "
                f"probe_supports_lane={lane.get('probe_supports_lane')} "
                f"missing_gates={lane.get('missing_gates')}"
            )
    return "\n".join(lines) + "\n"


def write_phase3b_b5a_localized_evidence_readiness(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "b5a_localized_evidence_readiness",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    _atomic_write_text(
        md_path,
        render_phase3b_b5a_localized_evidence_readiness_markdown(report),
    )
    _atomic_write_text(
        txt_path,
        render_phase3b_b5a_localized_evidence_readiness_text(report),
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _ghost_lane(
    anchor_rows: list[Dict[str, Any]],
    *,
    ghost_probe: Optional[Mapping[str, Any]],
    ghost_probe_error: Optional[str],
    current_source_ok: bool,
) -> Dict[str, Any]:
    covered_rows = [
        row
        for row in anchor_rows
        if int(row.get("anchor_idx", -1)) == EXPECTED_GHOST_ANCHOR
        and row.get("category") == "ghost_overlap_forced_domain"
        and bool(row.get("localized", False))
    ]
    validation = _mapping(ghost_probe.get("validation")) if ghost_probe else {}
    precheck = _mapping(validation.get("ghost_overlap_forced_domain_precheck"))
    first_conflict = _mapping(precheck.get("first_conflict"))
    selected_labels = [
        dict(label)
        for label in list(first_conflict.get("selected_labels", []))
        if isinstance(label, Mapping)
    ]
    compatible_rows = [
        dict(row)
        for row in list(first_conflict.get("compatible_rows", []))
        if isinstance(row, Mapping)
    ]
    probe_supports_lane = bool(
        ghost_probe is not None
        and ghost_probe_error is None
        and validation.get("attempted_solver") is False
        and validation.get("reason") == "ghost_overlap_forced_domain_infeasible"
        and precheck.get("reason") == "ghost_overlap_forced_domain_infeasible"
        and first_conflict.get("reason") == "all_compatible_rows_overlap_fixed_ghost"
    )
    current_source_complete = bool(current_source_ok and covered_rows)
    return {
        "lane_id": "anchor118_ghost_overlap_forced_domain",
        "category": "ghost_overlap_forced_domain",
        "required_anchors": [EXPECTED_GHOST_ANCHOR],
        "covered_anchors": [int(row.get("anchor_idx")) for row in covered_rows],
        "current_source_complete": current_source_complete,
        "current_source_anchor_rows": covered_rows,
        "probe_present": ghost_probe is not None,
        "probe_load_error": ghost_probe_error,
        "probe_supports_lane": probe_supports_lane,
        "solver_free_inputs": bool(probe_supports_lane),
        "proof_safe": bool(probe_supports_lane),
        "minimal_evidence": {
            "ghost_rect": dict(_mapping(precheck.get("ghost_rect"))),
            "forced_slot": {
                "group_id": first_conflict.get("group_id"),
                "solution_id": first_conflict.get("solution_id"),
                "slot_index": first_conflict.get("slot_index"),
                "template": first_conflict.get("template"),
            },
            "forced_fields": dict(_mapping(first_conflict.get("forced_fields"))),
            "selected_label_count": len(selected_labels),
            "selected_labels": selected_labels[:8],
            "compatible_rows_all_overlap_fixed_ghost": bool(probe_supports_lane),
            "compatible_tuple_count": first_conflict.get("compatible_tuple_count"),
            "compatible_rows": compatible_rows[:8],
            "forced_anchor_status_counts": (
                dict(_mapping(covered_rows[0].get("forced_anchor_status_counts")))
                if covered_rows
                else {}
            ),
        },
        "missing_gates": _missing_gates(
            current_source_complete=current_source_complete,
            probe_supports_lane=probe_supports_lane,
        ),
    }


def _signature_lane(
    anchor_rows: list[Dict[str, Any]],
    *,
    signature_probe: Optional[Mapping[str, Any]],
    signature_probe_error: Optional[str],
    precedent: Optional[Mapping[str, Any]],
    precedent_error: Optional[str],
    current_source_ok: bool,
) -> Dict[str, Any]:
    expected = set(EXPECTED_SIGNATURE_ANCHORS)
    covered_rows = [
        row
        for row in anchor_rows
        if int(row.get("anchor_idx", -1)) in expected
        and row.get("category") == "signature_monotonic_forced_label"
        and bool(row.get("localized", False))
    ]
    covered = sorted(int(row.get("anchor_idx")) for row in covered_rows)
    validation = _mapping(signature_probe.get("validation")) if signature_probe else {}
    precheck = _mapping(validation.get("signature_monotonic_precheck"))
    failure = _mapping(precheck.get("failure"))
    precedent_status = _mapping(precedent.get("promotion_status")) if precedent else {}
    probe_supports_lane = bool(
        signature_probe is not None
        and signature_probe_error is None
        and validation.get("attempted_solver") is False
        and validation.get("reason") == "signature_monotonic_forced_label_infeasible"
        and precheck.get("reason") == "signature_monotonic_forced_label_infeasible"
    )
    current_source_complete = bool(current_source_ok and set(covered) == expected)
    return {
        "lane_id": "anchors119_125_signature_monotonic_forced_label",
        "category": "signature_monotonic_forced_label",
        "required_anchors": list(EXPECTED_SIGNATURE_ANCHORS),
        "covered_anchors": covered,
        "current_source_complete": current_source_complete,
        "current_source_anchor_rows": covered_rows,
        "probe_present": signature_probe is not None,
        "probe_load_error": signature_probe_error,
        "probe_supports_lane": probe_supports_lane,
        "solver_free_inputs": bool(probe_supports_lane),
        "proof_safe": bool(probe_supports_lane),
        "minimal_evidence": {
            "sample_probe_anchor": _mapping(signature_probe.get("candidate")).get("anchor_idx")
            if signature_probe
            else None,
            "sample_probe_group_id": precheck.get("group_id"),
            "sample_probe_failure": dict(failure),
            "constrained_slots": [
                dict(slot)
                for slot in list(precheck.get("constrained_slots", []))
                if isinstance(slot, Mapping)
            ][:8],
            "forced_label_count": precheck.get("forced_label_count"),
            "forced_anchor_status_counts_by_anchor": {
                str(row.get("anchor_idx")): dict(
                    _mapping(row.get("forced_anchor_status_counts"))
                )
                for row in covered_rows
            },
        },
        "precedent": {
            "present": precedent is not None,
            "load_error": precedent_error,
            "spec_ready_for_runtime_slice": bool(
                precedent_status.get("spec_ready_for_runtime_slice", False)
            ),
            "role": "design_precedent_only_not_current_b5a_evidence",
            "used_as_current_b5a_evidence": False,
        },
        "missing_gates": _missing_gates(
            current_source_complete=current_source_complete,
            probe_supports_lane=probe_supports_lane,
            extra=[
                "current_source_signature_validator_for_anchors119_125",
            ],
        ),
    }


def _missing_gates(
    *,
    current_source_complete: bool,
    probe_supports_lane: bool,
    extra: Optional[list[str]] = None,
) -> list[str]:
    gates: list[str] = []
    if not current_source_complete:
        gates.append("current_source_reason_localization")
    if not probe_supports_lane:
        gates.append("runtime_probe_supporting_details")
    gates.extend(list(extra or []))
    gates.extend(
        [
            "b5a_certified_anchor_validator",
            "b5a_gate_integration",
            "final_168h_authorization_still_forbidden",
        ]
    )
    return gates


def _checks(
    *,
    reason_present: bool,
    reason_error: Optional[str],
    reason_source_supported: bool,
    reason_ready: bool,
    reason_safe_flags: bool,
    candidate_matches: bool,
    candidate_key: str,
    expected_candidate: str,
    preflight_present: bool,
    preflight_error: Optional[str],
    preflight_only_b5a_failed: bool,
    failed_checks: list[str],
    ghost_lane: Mapping[str, Any],
    signature_lane: Mapping[str, Any],
) -> list[Dict[str, str]]:
    return [
        _check(
            "reason_localization_present",
            "pass" if reason_present else "fail",
            "reason localization loaded"
            if reason_present
            else reason_error or "reason localization missing",
        ),
        _check(
            "reason_localization_source_supported",
            "pass" if reason_source_supported else "fail",
            B5A_COORDINATE_VALIDATION_REASON_LOCALIZATION_SOURCE,
        ),
        _check(
            "reason_localization_ready",
            "pass" if reason_ready else "fail",
            f"reason_localization_ready={reason_ready}",
        ),
        _check(
            "reason_localization_safe_flags",
            "pass" if reason_safe_flags else "fail",
            "solver_invoked=false, checkpoint_written=false, proof_source=false, runtime_semantics_changed=false",
        ),
        _check(
            "candidate_matches_expected",
            "pass" if candidate_matches else "fail",
            f"localized={candidate_key}; expected={expected_candidate}",
        ),
        _check(
            "post_acceptance_preflight_present",
            "pass" if preflight_present else "fail",
            "post-acceptance preflight loaded"
            if preflight_present
            else preflight_error or "preflight missing",
        ),
        _check(
            "post_acceptance_only_b5a_failed",
            "pass" if preflight_only_b5a_failed else "fail",
            f"failed_checks={failed_checks}",
        ),
        _check(
            "ghost_lane_anchor118_current_source",
            "pass" if bool(ghost_lane.get("current_source_complete")) else "fail",
            f"covered={ghost_lane.get('covered_anchors')}",
        ),
        _check(
            "signature_lane_anchors119_125_current_source",
            "pass" if bool(signature_lane.get("current_source_complete")) else "fail",
            f"covered={signature_lane.get('covered_anchors')}",
        ),
        _check(
            "old_signature_precedent_not_current_evidence",
            "pass",
            "old m6x4 signature artifacts are precedent only and cannot satisfy current B5A evidence",
        ),
        _check(
            "certified_anchor_not_claimed",
            "pass",
            "readiness report keeps certified_anchor_found=false and proof_source=false",
        ),
    ]


def _recommendation(readiness_ready: bool) -> str:
    if readiness_ready:
        return (
            "Localized evidence lanes are ready for review/validator design: use "
            "signature-monotonic forced-label coverage for anchors119-125 and "
            "ghost-overlap forced-domain coverage for anchor118. Do not treat this "
            "as certified B5A proof yet."
        )
    return (
        "Localized evidence readiness is blocked; inspect failed checks before "
        "designing a B5A certified-anchor validator."
    )


def _anchor_rows(reason: Optional[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    if not reason:
        return []
    rows = list(_mapping(reason.get("reason_localization")).get("anchor_rows", []))
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _failed_preflight_checks(preflight: Optional[Mapping[str, Any]]) -> list[str]:
    if not preflight:
        return []
    direct = preflight.get("failed_checks")
    if isinstance(direct, list):
        return [str(token) for token in direct]
    checks = []
    for check in list(preflight.get("checks", [])):
        if isinstance(check, Mapping) and str(check.get("status")) == "fail":
            checks.append(str(check.get("check_id")))
    return checks


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if isinstance(payload, Mapping):
            return dict(payload), None
        return None, "JSON root is not an object"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _resolve_path(project_root: Path, path: Optional[Path]) -> Path:
    if path is None:
        return project_root
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)
