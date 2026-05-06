from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

from src.search.exact_campaign import atomic_write_json, compute_exact_artifact_hashes, now_iso
from src.search.phase3b_anchor119_guard_controls import (
    PHASE3B_ANCHOR119_DEFAULT_STATE,
    PHASE3B_ANCHOR119_GUARD_ID,
    build_phase3b_anchor119_guard_locked_boundaries,
    phase3b_anchor119_guard_candidate_scope,
)

ANCHOR119_GUARDED_PRECHECK_SPEC_SOURCE = (
    "phase3b_anchor119_guarded_precheck_spec_v1"
)

DEFAULT_SYNTHESIS_PATH = Path(
    ".artifacts/phase3b_anchor119_pair_x_global_context_synthesis_20260423/"
    "global_context_synthesis.json"
)
DEFAULT_TILING_REPORT_PATH = Path(
    ".artifacts/phase3b_anchor119_mixed_lane_tiling_verifier_module_20260423/"
    "mixed_lane_tiling_verifier.json"
)
DEFAULT_DP_CROSSCHECK_PATH = Path(
    ".artifacts/phase3b_anchor119_mixed_lane_dp_crosscheck_20260423/"
    "mixed_lane_dp_crosscheck.json"
)
DEFAULT_ROW_DOMAIN_GUARD_SPEC_PATH = Path(
    ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_guard_spec_20260424/"
    "anchor119_row_domain_guard_spec.json"
)


def build_phase3b_anchor119_guarded_precheck_spec(
    project_root: Path,
    *,
    synthesis_path: Path | None = None,
    tiling_report_path: Path | None = None,
    dp_crosscheck_path: Path | None = None,
    row_domain_guard_spec_path: Path | None = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    synthesis_path = _resolve(project_root, synthesis_path or DEFAULT_SYNTHESIS_PATH)
    tiling_report_path = _resolve(project_root, tiling_report_path or DEFAULT_TILING_REPORT_PATH)
    dp_crosscheck_path = _resolve(project_root, dp_crosscheck_path or DEFAULT_DP_CROSSCHECK_PATH)
    row_domain_guard_spec_path = _resolve(
        project_root, row_domain_guard_spec_path or DEFAULT_ROW_DOMAIN_GUARD_SPEC_PATH
    )

    synthesis = _load_json(synthesis_path)
    tiling = _load_json(tiling_report_path)
    dp = _load_json(dp_crosscheck_path)
    row_domain_guard_spec = _load_json(row_domain_guard_spec_path)
    current_hashes: Dict[str, Any] = {}
    artifact_hash_error = None
    try:
        current_hashes = compute_exact_artifact_hashes(project_root)
    except Exception as exc:
        artifact_hash_error = f"{type(exc).__name__}: {exc}"

    candidate = {
        "key": _mapping(tiling.get("candidate")).get("key"),
        "anchor_idx": _mapping(tiling.get("candidate")).get("anchor_idx"),
        "ghost_rect": _mapping(tiling.get("candidate")).get("ghost_rect"),
        "safe_strip": _mapping(tiling.get("candidate")).get("safe_strip"),
    }
    evidence = _evidence_summary(
        synthesis=synthesis,
        tiling=tiling,
        dp=dp,
        row_domain_guard_spec=row_domain_guard_spec,
        current_hashes=current_hashes,
    )
    checks = _checks(
        project_root=project_root,
        synthesis=synthesis,
        tiling=tiling,
        dp=dp,
        row_domain_guard_spec=row_domain_guard_spec,
        current_hashes=current_hashes,
        artifact_hash_error=artifact_hash_error,
    )
    gate_pass = all(check["status"] == "pass" for check in checks)
    return {
        "metadata": {
            "source": ANCHOR119_GUARDED_PRECHECK_SPEC_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "guarded_precheck_spec_only_not_runtime_semantics",
            "spec_only": True,
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
            "runtime_precheck_enabled": False,
            "runtime_semantics_changed": False,
            "default_off": True,
        },
        "paths": {
            "project_root": str(project_root),
            "synthesis": _display(project_root, synthesis_path),
            "tiling_report": _display(project_root, tiling_report_path),
            "dp_crosscheck": _display(project_root, dp_crosscheck_path),
            "row_domain_guard_spec": _display(project_root, row_domain_guard_spec_path),
        },
        "candidate": candidate,
        "artifact_hashes": {
            "current_exact_artifact_hashes": current_hashes,
            "tiling_artifact_hashes": _mapping(tiling.get("artifact_hashes")),
            "dp_artifact_hashes": _mapping(dp.get("artifact_hashes")),
            "artifact_hash_error": artifact_hash_error,
        },
        "evidence": evidence,
        "proposed_guard": _proposed_guard(candidate, evidence),
        "status": {
            "completed": True,
            "outcome": (
                "guarded_precheck_spec_ready_for_review"
                if gate_pass
                else "guarded_precheck_spec_blocked"
            ),
            "all_gates_pass": bool(gate_pass),
            "runtime_precheck_enabled": False,
            "runtime_promotion_ready": False,
            "recommendation": (
                "Spec gates pass for a default-off guarded precheck design review; "
                "do not enable runtime behavior without a separate reviewed patch."
                if gate_pass
                else "Spec gates did not all pass; keep diagnostic-only and inspect failed checks."
            ),
        },
        "checks": checks,
    }


def render_phase3b_anchor119_guarded_precheck_spec_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    candidate = _mapping(report.get("candidate"))
    guard = _mapping(report.get("proposed_guard"))
    evidence = _mapping(report.get("evidence"))
    lines = [
        "# Phase3B Anchor119 Guarded Precheck Spec",
        "",
        f"- Outcome: `{status.get('outcome')}`",
        "- Spec only: true",
        "- Runtime precheck enabled: false",
        "- Runtime semantics changed: false",
        "- Proof source: false",
        f"- Candidate: `{candidate.get('key')}` / anchor `{candidate.get('anchor_idx')}`",
        f"- Guard id: `{guard.get('guard_id')}`",
        f"- All gates pass: `{status.get('all_gates_pass')}`",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Evidence",
        "",
        f"- Tiling outcome: `{evidence.get('tiling_outcome')}`",
        f"- DP outcome: `{evidence.get('dp_outcome')}`",
        f"- Domain hash match: `{evidence.get('domain_hash_match')}`",
        f"- Tiling patterns: `{evidence.get('tiling_total_patterns')}`",
        f"- DP final cover states: `{evidence.get('dp_final_cover_states')}`",
        f"- DP P9/P10 pairs checked: `{evidence.get('dp_p9p10_pairs_checked')}`",
        f"- Payload id: `{evidence.get('payload_id')}`",
        f"- Non-trigger max slot count: `{evidence.get('non_trigger_max_slot_count')}`",
        f"- Anchored trigger min slot count: `{evidence.get('anchored_trigger_min_slot_count')}`",
        "",
        "## Proposed Guard",
        "",
        f"- Scope: `{guard.get('scope')}`",
        f"- Default state: `{guard.get('default_state')}`",
        f"- Runtime hook: `{guard.get('runtime_hook')}`",
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


def render_phase3b_anchor119_guarded_precheck_spec_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    evidence = _mapping(report.get("evidence"))
    return "\n".join(
        [
            "Phase3B anchor119 guarded precheck spec",
            f"outcome={status.get('outcome')}",
            f"all_gates_pass={status.get('all_gates_pass')}",
            "spec_only=true",
            "runtime_precheck_enabled=false",
            "runtime_semantics_changed=false",
            "proof_source=false",
            f"tiling_outcome={evidence.get('tiling_outcome')}",
            f"dp_outcome={evidence.get('dp_outcome')}",
            f"domain_hash_match={evidence.get('domain_hash_match')}",
            f"payload_id={evidence.get('payload_id')}",
            f"non_trigger_max_slot_count={evidence.get('non_trigger_max_slot_count')}",
            f"anchored_trigger_min_slot_count={evidence.get('anchored_trigger_min_slot_count')}",
        ]
    ) + "\n"


def write_phase3b_anchor119_guarded_precheck_spec(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "guarded_precheck_spec",
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    md_path.write_text(
        render_phase3b_anchor119_guarded_precheck_spec_markdown(report),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_anchor119_guarded_precheck_spec_text(report),
        encoding="utf-8",
    )
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _evidence_summary(
    *,
    synthesis: Mapping[str, Any],
    tiling: Mapping[str, Any],
    dp: Mapping[str, Any],
    row_domain_guard_spec: Mapping[str, Any],
    current_hashes: Mapping[str, Any],
) -> Dict[str, Any]:
    tiling_status = _mapping(tiling.get("status"))
    tiling_enum = _mapping(tiling.get("enumeration"))
    dp_status = _mapping(dp.get("status"))
    dp_cross = _mapping(dp.get("crosscheck"))
    dp_provenance = _mapping(dp.get("provenance"))
    synthesis_boundaries = _mapping(synthesis.get("boundaries"))
    row_domain_status = _mapping(row_domain_guard_spec.get("status"))
    row_domain_evidence = _mapping(row_domain_guard_spec.get("evidence"))
    row_domain_guard = _mapping(row_domain_guard_spec.get("proposed_guard"))
    return {
        "tiling_outcome": tiling_status.get("outcome"),
        "tiling_exhaustive": bool(tiling_status.get("exhaustive", False)),
        "tiling_witness_found": tiling.get("witness") is not None,
        "tiling_total_patterns": tiling_enum.get("total_patterns"),
        "tiling_p9p10_window_cases": tiling_enum.get("total_p9p10_window_cases"),
        "dp_outcome": dp_status.get("outcome"),
        "dp_exhaustive": bool(dp_status.get("exhaustive", False)),
        "dp_witness_found": dp.get("witness") is not None,
        "dp_final_cover_states": dp_cross.get("total_final_cover_states"),
        "dp_p9p10_pairs_checked": dp_cross.get("total_p9_p10_pairs_checked"),
        "domain_hash": dp_provenance.get("domain_rows_sha256"),
        "reference_domain_hash": dp_provenance.get("reference_domain_rows_sha256"),
        "domain_hash_match": dp_provenance.get("domain_rows_sha256_matches_reference"),
        "tiling_and_dp_parity_observed": synthesis_boundaries.get(
            "tiling_and_dp_parity_observed"
        ),
        "row_domain_guard_outcome": row_domain_status.get("outcome"),
        "row_domain_guard_all_gates_pass": row_domain_status.get("all_gates_pass"),
        "payload_id": row_domain_evidence.get("payload_id") or row_domain_guard.get("payload_id"),
        "non_trigger_max_slot_count": row_domain_evidence.get("non_trigger_max_slot_count"),
        "anchored_trigger_min_slot_count": row_domain_evidence.get(
            "anchored_trigger_min_slot_count"
        ),
        "free_ghost_trigger_min_slot_count": row_domain_evidence.get(
            "free_ghost_trigger_min_slot_count"
        ),
        "current_exact_artifact_hashes": dict(current_hashes),
    }


def _proposed_guard(candidate: Mapping[str, Any], evidence: Mapping[str, Any]) -> Dict[str, Any]:
    locked_boundaries = build_phase3b_anchor119_guard_locked_boundaries()
    return {
        "guard_id": PHASE3B_ANCHOR119_GUARD_ID,
        "scope": phase3b_anchor119_guard_candidate_scope(
            suffix="planter_buckwheat/protocol_core local mixed-lane diagnostic plus row-domain/count bridge"
        ),
        "default_state": PHASE3B_ANCHOR119_DEFAULT_STATE,
        "advisory_only": True,
        "runtime_hook": "none_in_this_patch",
        "requires_explicit_enable_flag": True,
        "payload_id": evidence.get("payload_id"),
        "required_evidence": {
            "tiling_outcome": evidence.get("tiling_outcome"),
            "dp_outcome": evidence.get("dp_outcome"),
            "domain_hash": evidence.get("domain_hash"),
            "candidate": dict(candidate),
        },
        "non_trigger_controls": {
            "non_trigger_max_slot_count": evidence.get("non_trigger_max_slot_count")
            if evidence.get("non_trigger_max_slot_count") is not None
            else locked_boundaries.get("non_trigger_max_slot_count"),
            "anchored_trigger_min_slot_count": evidence.get(
                "anchored_trigger_min_slot_count"
            )
            if evidence.get("anchored_trigger_min_slot_count") is not None
            else locked_boundaries.get("anchored_trigger_min_slot_count"),
            "free_ghost_trigger_min_slot_count": evidence.get(
                "free_ghost_trigger_min_slot_count"
            )
            if evidence.get("free_ghost_trigger_min_slot_count") is not None
            else locked_boundaries.get("free_ghost_trigger_min_slot_count"),
        },
        "non_goals": [
            "No candidate elimination claim in this spec.",
            "No release/viewer/frontdoor status change.",
            "No workspace checkpoint import.",
            "No final 168h long run.",
        ],
    }


def _checks(
    *,
    project_root: Path,
    synthesis: Mapping[str, Any],
    tiling: Mapping[str, Any],
    dp: Mapping[str, Any],
    row_domain_guard_spec: Mapping[str, Any],
    current_hashes: Mapping[str, Any],
    artifact_hash_error: str | None,
) -> list[Dict[str, str]]:
    tiling_meta = _mapping(tiling.get("metadata"))
    tiling_status = _mapping(tiling.get("status"))
    tiling_enum = _mapping(tiling.get("enumeration"))
    dp_meta = _mapping(dp.get("metadata"))
    dp_status = _mapping(dp.get("status"))
    dp_cross = _mapping(dp.get("crosscheck"))
    dp_provenance = _mapping(dp.get("provenance"))
    synthesis_boundaries = _mapping(synthesis.get("boundaries"))
    row_domain_meta = _mapping(row_domain_guard_spec.get("metadata"))
    row_domain_status = _mapping(row_domain_guard_spec.get("status"))
    row_domain_evidence = _mapping(row_domain_guard_spec.get("evidence"))
    tiling_hashes = _mapping(tiling.get("artifact_hashes"))
    dp_hashes = _mapping(dp.get("artifact_hashes"))
    return [
        _check("spec_only", "pass", "report/spec layer only"),
        _check(
            "current_hashes_available",
            "pass" if artifact_hash_error is None and bool(current_hashes) else "fail",
            artifact_hash_error or "computed",
        ),
        _check(
            "tiling_hashes_match_current",
            "pass" if dict(tiling_hashes) == dict(current_hashes) else "fail",
            "tiling artifact hashes vs current exact hashes",
        ),
        _check(
            "dp_hashes_match_current",
            "pass" if dict(dp_hashes) == dict(current_hashes) else "fail",
            "dp artifact hashes vs current exact hashes",
        ),
        _check(
            "tiling_exhaustive_no_witness",
            "pass"
            if tiling_status.get("outcome") == "exact_tiling_exhaustive_no_witness"
            and bool(tiling_status.get("exhaustive", False))
            and tiling.get("witness") is None
            else "fail",
            str(tiling_status.get("outcome")),
        ),
        _check(
            "tiling_patterns_present",
            "pass" if int(tiling_enum.get("total_patterns", 0)) > 0 else "fail",
            str(tiling_enum.get("total_patterns")),
        ),
        _check(
            "dp_exhaustive_no_witness",
            "pass"
            if dp_status.get("outcome") == "dp_crosscheck_exhaustive_no_witness"
            and bool(dp_status.get("exhaustive", False))
            and dp.get("witness") is None
            else "fail",
            str(dp_status.get("outcome")),
        ),
        _check(
            "dp_final_cover_states_present",
            "pass" if int(dp_cross.get("total_final_cover_states", 0)) > 0 else "fail",
            str(dp_cross.get("total_final_cover_states")),
        ),
        _check(
            "domain_hash_parity",
            "pass" if dp_provenance.get("domain_rows_sha256_matches_reference") is True else "fail",
            str(dp_provenance.get("domain_rows_sha256_matches_reference")),
        ),
        _check(
            "tiling_diagnostic_flags",
            "pass"
            if tiling_meta.get("solver_invoked") is False
            and tiling_meta.get("proof_source") is False
            and tiling_meta.get("runtime_promotion_ready") is False
            else "fail",
            "solver/proof/runtime flags",
        ),
        _check(
            "dp_diagnostic_flags",
            "pass"
            if dp_meta.get("solver_invoked") is False
            and dp_meta.get("proof_source") is False
            and dp_meta.get("runtime_promotion_ready") is False
            else "fail",
            "solver/proof/runtime flags",
        ),
        _check(
            "synthesis_parity_observed",
            "pass" if synthesis_boundaries.get("tiling_and_dp_parity_observed") is True else "fail",
            str(synthesis_boundaries.get("tiling_and_dp_parity_observed")),
        ),
        _check(
            "row_domain_guard_spec_present",
            "pass"
            if row_domain_meta.get("source")
            == "phase3b_coordinate_validation_anchor119_row_domain_guard_spec_v1"
            else "fail",
            str(row_domain_meta.get("source")),
        ),
        _check(
            "row_domain_guard_ready_for_review",
            "pass"
            if row_domain_status.get("outcome")
            == "anchor119_row_domain_guard_spec_ready_for_review"
            and row_domain_status.get("all_gates_pass") is True
            else "fail",
            str(row_domain_status.get("outcome")),
        ),
        _check(
            "row_domain_boundaries_locked",
            "pass"
            if int(row_domain_evidence.get("non_trigger_max_slot_count", -1) or -1) == 13
            and int(row_domain_evidence.get("anchored_trigger_min_slot_count", -1) or -1)
            == 14
            and int(row_domain_evidence.get("free_ghost_trigger_min_slot_count", -1) or -1)
            == 15
            else "fail",
            (
                f"non_trigger_max={row_domain_evidence.get('non_trigger_max_slot_count')} "
                f"anchored_trigger_min={row_domain_evidence.get('anchored_trigger_min_slot_count')} "
                f"free_ghost_trigger_min={row_domain_evidence.get('free_ghost_trigger_min_slot_count')}"
            ),
        ),
        _check(
            "checkpoint_absent",
            "pass"
            if not (Path(project_root) / "data/checkpoints/exact_campaign_state.json").exists()
            else "fail",
            "repo checkpoint path must stay absent",
        ),
        _check("runtime_precheck_disabled", "pass", "this spec does not enable runtime behavior"),
    ]


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _resolve(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (Path(project_root) / path).resolve()


def _display(project_root: Path, path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
