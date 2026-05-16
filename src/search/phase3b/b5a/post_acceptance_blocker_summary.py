"""Post-acceptance B5A blocker summary.

This module is intentionally report-only. It consolidates the state after
review-state ingest and production acceptance refresh, then points the next
diagnostic step at the remaining B5A certified-anchor blocker.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_OUTPUT_DIR = Path(
    ".artifacts/phase3b_b5a_post_acceptance_blocker_summary_20260425"
)
DEFAULT_PREFLIGHT_SUMMARY = Path(
    ".artifacts/phase3b_long_run_preflight_after_acceptance_refresh_20260425/"
    "preflight_summary.json"
)
DEFAULT_B5A_OPERATOR_SUMMARY = Path(
    ".artifacts/phase3b_b5_anchor_sprint/operator_summary.json"
)
DEFAULT_ACCEPTANCE_RESULT_VALIDATOR = Path(
    ".artifacts/"
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_after_refresh_20260425/"
    "anchor119_row_domain_acceptance_result_validator.json"
)
DEFAULT_ACCEPTANCE_EXECUTION_GATE = Path(
    ".artifacts/"
    "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_gate_after_acceptance_refresh_20260425/"
    "anchor119_row_domain_acceptance_execution_gate.json"
)
DEFAULT_PRODUCTION_ACCEPTANCE_HANDOFF = Path(
    ".artifacts/phase3b_production_acceptance_refresh_handoff_20260425/"
    "production_acceptance_refresh_handoff.md"
)


class PostAcceptanceB5aSummaryError(RuntimeError):
    """Raised when input files cannot be read."""


@dataclass(frozen=True)
class SummaryPaths:
    preflight_summary: Path = DEFAULT_PREFLIGHT_SUMMARY
    b5a_operator_summary: Path = DEFAULT_B5A_OPERATOR_SUMMARY
    acceptance_result_validator: Path = DEFAULT_ACCEPTANCE_RESULT_VALIDATOR
    acceptance_execution_gate: Path = DEFAULT_ACCEPTANCE_EXECUTION_GATE
    production_acceptance_handoff: Path = DEFAULT_PRODUCTION_ACCEPTANCE_HANDOFF


def build_post_acceptance_b5a_blocker_summary(
    paths: SummaryPaths | None = None,
) -> dict[str, Any]:
    paths = paths or SummaryPaths()
    inputs = _load_inputs(paths)

    preflight = inputs["preflight_summary"]
    b5a = inputs["b5a_operator_summary"]
    acceptance_result = inputs["acceptance_result_validator"]
    acceptance_gate = inputs["acceptance_execution_gate"]

    failed_checks = _failed_preflight_checks(preflight)
    preflight_ready = bool(
        preflight.get("ready_for_final_long_run", preflight.get("ready", False))
    )

    result_status = _mapping(acceptance_result.get("status"))
    gate_status = _mapping(acceptance_gate.get("status"))
    b5a_status = _mapping(b5a.get("status"))

    reviewed_runtime_patch_exists = bool(
        gate_status.get("reviewed_runtime_patch_exists")
    )
    production_acceptance_refresh_completed = bool(
        gate_status.get("production_acceptance_refresh_completed")
    )
    acceptance_result_validation_passed = bool(
        result_status.get("acceptance_result_validation_passed")
    )
    runtime_enablement_allowed = bool(gate_status.get("runtime_enablement_allowed"))
    acceptance_execution_authorized = bool(
        gate_status.get("acceptance_execution_authorized")
    )
    b5a_anchor_found = bool(b5a_status.get("anchor_found"))

    top_blocker = _extract_top_b5a_blocker(b5a)
    reason_localization = _build_reason_localization(top_blocker)

    only_b5a_failed = failed_checks == ["b5a_anchor_found"]
    post_acceptance_state_clean = (
        reviewed_runtime_patch_exists
        and production_acceptance_refresh_completed
        and acceptance_result_validation_passed
        and not runtime_enablement_allowed
        and not acceptance_execution_authorized
    )
    b5a_gate_remaining = (
        post_acceptance_state_clean
        and only_b5a_failed
        and not preflight_ready
        and not b5a_anchor_found
    )

    if b5a_gate_remaining:
        outcome = "post_acceptance_b5a_anchor_gate_remaining"
        recommended_next_step = (
            "localize_coordinate_validation_infeasible_reason_before_bounded_b5a_sprint"
        )
    else:
        outcome = "post_acceptance_inputs_incomplete_or_stale"
        recommended_next_step = "refresh_or_repair_post_acceptance_inputs_first"

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    summary = {
        "metadata": {
            "source": "phase3b_b5a_post_acceptance_blocker_summary_v1",
            "generated_at": generated_at,
            "diagnostic_semantics": "report_only",
            "solver_invoked": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "checkpoint_written": False,
            "candidate_elimination_claim": False,
            "certified_anchor_found": False,
            "b5a_anchor_found": False,
            "preflight_gate_mutated": False,
            "runtime_elimination_authorized": False,
            "final_168h_authorized": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
        },
        "inputs": _input_manifest(paths, inputs),
        "status": {
            "summary_ready": b5a_gate_remaining,
            "outcome": outcome,
            "reviewed_runtime_patch_exists": reviewed_runtime_patch_exists,
            "production_acceptance_refresh_completed": (
                production_acceptance_refresh_completed
            ),
            "acceptance_result_validation_passed": (
                acceptance_result_validation_passed
            ),
            "runtime_enablement_allowed": runtime_enablement_allowed,
            "acceptance_execution_authorized": acceptance_execution_authorized,
            "preflight_ready": preflight_ready,
            "failed_checks": failed_checks,
            "only_b5a_anchor_found_failed": only_b5a_failed,
            "b5a_anchor_found": b5a_anchor_found,
            "certified_anchor_found": False,
            "proof_source": False,
            "runtime_semantics_changed": False,
            "checkpoint_written": False,
            "candidate_elimination_claim": False,
            "preflight_gate_mutated": False,
            "runtime_elimination_authorized": False,
            "final_168h_authorized": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
            "current_gate": "b5a_certified_anchor_evidence",
            "recommended_next_step": recommended_next_step,
        },
        "b5a_blocker": top_blocker,
        "reason_localization": reason_localization,
        "guardrails": {
            "do_not_start_final_168h": True,
            "do_not_enable_runtime_elimination": True,
            "do_not_import_or_write_checkpoint": True,
            "do_not_promote_release_viewer_frontdoor": True,
            "diagnostic_terminal_not_proof_source": True,
        },
        "checks": _build_checks(
            post_acceptance_state_clean=post_acceptance_state_clean,
            only_b5a_failed=only_b5a_failed,
            b5a_anchor_found=b5a_anchor_found,
            reason_taxonomy_complete=reason_localization[
                "reason_taxonomy_complete"
            ],
        ),
    }
    return summary


def write_post_acceptance_b5a_blocker_summary(
    summary: Mapping[str, Any], output_dir: Path
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "b5a_post_acceptance_blocker_summary.json"
    md_path = output_dir / "b5a_post_acceptance_blocker_summary.md"
    txt_path = output_dir / "b5a_post_acceptance_blocker_summary.txt"

    json_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown = render_post_acceptance_b5a_blocker_summary_markdown(summary)
    md_path.write_text(markdown, encoding="utf-8")
    txt_path.write_text(_markdown_to_text(markdown), encoding="utf-8")
    return {"json": json_path, "md": md_path, "txt": txt_path}


def render_post_acceptance_b5a_blocker_summary_markdown(
    summary: Mapping[str, Any],
) -> str:
    status = _mapping(summary.get("status"))
    blocker = _mapping(summary.get("b5a_blocker"))
    localization = _mapping(summary.get("reason_localization"))
    checks = summary.get("checks")
    checks_list = checks if isinstance(checks, list) else []

    lines = [
        "# Phase3B B5A Post-Acceptance Blocker Summary",
        "",
        "## Status",
        "",
        f"- outcome: `{status.get('outcome')}`",
        f"- reviewed_runtime_patch_exists: `{status.get('reviewed_runtime_patch_exists')}`",
        f"- production_acceptance_refresh_completed: `{status.get('production_acceptance_refresh_completed')}`",
        f"- acceptance_result_validation_passed: `{status.get('acceptance_result_validation_passed')}`",
        f"- preflight_ready: `{status.get('preflight_ready')}`",
        f"- failed_checks: `{', '.join(status.get('failed_checks') or [])}`",
        f"- current_gate: `{status.get('current_gate')}`",
        f"- recommended_next_step: `{status.get('recommended_next_step')}`",
        "",
        "## B5A Blocker",
        "",
        f"- candidate_key: `{blocker.get('candidate_key')}`",
        f"- blocker_subtype: `{blocker.get('blocker_subtype')}`",
        f"- solver_status: `{blocker.get('status')}`",
        f"- certified_anchor_found: `{status.get('b5a_anchor_found')}`",
        f"- failed_anchor_range: `{localization.get('failed_anchor_range')}`",
        f"- failure_reason_counts: `{localization.get('failure_reason_counts')}`",
        f"- reason_category_counts: `{localization.get('reason_category_counts')}`",
        f"- reason_taxonomy_complete: `{localization.get('reason_taxonomy_complete')}`",
        "",
        "## Interpretation",
        "",
        (
            "The signoff and production acceptance gates are no longer the active "
            "blocker in this snapshot. The remaining gate is certified B5A anchor "
            "evidence. Current anchors 118-125 still collapse to generic "
            "`coordinate_validation_infeasible`, so the next useful work is "
            "reason localization, not a blind sprint rerun."
        ),
        "",
        "## Checks",
        "",
    ]
    for check in checks_list:
        if not isinstance(check, Mapping):
            continue
        lines.append(
            f"- `{check.get('check_id')}`: `{check.get('status')}` - {check.get('detail')}"
        )
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- no final 168h long run",
            "- no runtime elimination enablement",
            "- no checkpoint import-back or write",
            "- no release/viewer/frontdoor promotion",
            "- diagnostic terminal/progress is not proof source",
            "",
        ]
    )
    return "\n".join(lines)


def _load_inputs(paths: SummaryPaths) -> dict[str, Any]:
    return {
        "preflight_summary": _read_json(paths.preflight_summary),
        "b5a_operator_summary": _read_json(paths.b5a_operator_summary),
        "acceptance_result_validator": _read_json(paths.acceptance_result_validator),
        "acceptance_execution_gate": _read_json(paths.acceptance_execution_gate),
        "production_acceptance_handoff": _read_text_optional(
            paths.production_acceptance_handoff
        ),
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PostAcceptanceB5aSummaryError(f"missing input file: {path}")
    loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(loaded, dict):
        raise PostAcceptanceB5aSummaryError(f"input is not a JSON object: {path}")
    return loaded


def _read_text_optional(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8-sig")


def _input_manifest(paths: SummaryPaths, inputs: Mapping[str, Any]) -> dict[str, Any]:
    manifest: dict[str, Any] = {}
    for field in (
        "preflight_summary",
        "b5a_operator_summary",
        "acceptance_result_validator",
        "acceptance_execution_gate",
        "production_acceptance_handoff",
    ):
        path = getattr(paths, field)
        manifest[field] = {
            "path": str(path),
            "present": path.exists(),
        }
        if field == "production_acceptance_handoff":
            manifest[field]["char_count"] = len(inputs.get(field) or "")
    return manifest


def _failed_preflight_checks(preflight: Mapping[str, Any]) -> list[str]:
    checks = preflight.get("checks")
    failed: list[str] = []
    if isinstance(checks, Sequence) and not isinstance(checks, (str, bytes)):
        for check in checks:
            if not isinstance(check, Mapping):
                continue
            status = str(check.get("status", "")).lower()
            check_id = check.get("check_id") or check.get("id") or check.get("name")
            if status in {"fail", "failed", "false"} and check_id:
                failed.append(str(check_id))
    if failed:
        return failed

    fallback = preflight.get("failed_checks")
    if isinstance(fallback, Sequence) and not isinstance(fallback, (str, bytes)):
        return [str(item) for item in fallback]
    return []


def _extract_top_b5a_blocker(b5a: Mapping[str, Any]) -> dict[str, Any]:
    triage = _mapping(b5a.get("triage"))
    blockers = triage.get("top_blockers")
    top: Mapping[str, Any] = {}
    if isinstance(blockers, Sequence) and not isinstance(blockers, (str, bytes)):
        for candidate in blockers:
            if isinstance(candidate, Mapping):
                top = candidate
                break

    evidence_refs = _mapping(top.get("evidence_refs"))
    proof_fields = _mapping(evidence_refs.get("proof_fields"))
    proof_summary = _mapping(top.get("proof_summary")) or proof_fields
    start_failure = _mapping(
        proof_summary.get("master_start_failure_attribution")
    ) or _mapping(top.get("start_failure_summary"))
    master_last_solve = _mapping(proof_summary.get("master_last_solve"))

    return {
        "candidate_key": top.get("candidate_key"),
        "status": top.get("status") or proof_summary.get("master_status"),
        "blocker_subtype": top.get("blocker_subtype"),
        "master_last_solve": dict(master_last_solve),
        "failed_anchor_count": start_failure.get("failed_anchor_count"),
        "failure_reason_counts": dict(
            _mapping(start_failure.get("failure_reason_counts"))
        ),
        "failed_anchor_samples": _copy_mapping_sequence(
            start_failure.get("failed_anchor_samples")
        ),
    }


def _build_reason_localization(blocker: Mapping[str, Any]) -> dict[str, Any]:
    samples = _copy_mapping_sequence(blocker.get("failed_anchor_samples"))
    localized_samples = []
    category_counter: Counter[str] = Counter()
    anchors: list[int] = []

    for sample in samples:
        reason = str(sample.get("failure_reason") or sample.get("reason") or "")
        category = classify_coordinate_validation_failure_sample(sample)
        localized = category not in {"generic_residual", "unknown"}
        category_counter[category] += 1
        anchor_idx = sample.get("anchor_idx", sample.get("anchor"))
        if isinstance(anchor_idx, int):
            anchors.append(anchor_idx)
        localized_samples.append(
            {
                "anchor_idx": anchor_idx,
                "failure_reason": reason,
                "coordinate_validation_reason": sample.get(
                    "coordinate_validation_reason"
                ),
                "coordinate_validation_solver_profile_id": sample.get(
                    "coordinate_validation_solver_profile_id"
                ),
                "category": category,
                "localized": localized,
                "blocked_cell_count": sample.get("blocked_cell_count"),
            }
        )

    failure_counts = dict(_mapping(blocker.get("failure_reason_counts")))
    count_categories = Counter()
    for reason, count in failure_counts.items():
        count_categories[classify_coordinate_validation_failure_reason(str(reason))] += (
            _int_or_zero(count)
        )

    has_samples = bool(localized_samples)
    sample_categories = set(category_counter)
    count_categories_set = set(count_categories)
    categories_for_completeness = (
        sample_categories if has_samples else count_categories_set
    )
    generic_present = bool({"generic_residual", "unknown"} & categories_for_completeness)
    reason_taxonomy_complete = has_samples and not generic_present

    return {
        "failed_anchor_range": _anchor_range_label(anchors),
        "failure_reason_counts": failure_counts,
        "reason_category_counts": dict(category_counter or count_categories),
        "failure_reason_count_categories": dict(count_categories),
        "failed_anchor_samples": localized_samples,
        "generic_residual_anchor_count": category_counter.get("generic_residual", 0),
        "reason_taxonomy_complete": reason_taxonomy_complete,
        "next_reason_localization_target": (
            "coordinate_validation_infeasible"
            if not reason_taxonomy_complete
            else None
        ),
    }


def classify_coordinate_validation_failure_reason(reason: str) -> str:
    token = reason.strip().lower()
    if not token:
        return "unknown"
    if "signature_monotonic_forced_label" in token:
        return "signature_forced_label"
    if "ghost_overlap_forced_domain" in token:
        return "ghost_overlap_forced_domain"
    if "ghost_y_overlap_forced_label" in token:
        return "ghost_y_overlap_forced_label"
    if "attempt_limit" in token or "attempt limit" in token:
        return "attempt_limit"
    if "coordinate_validation_infeasible" in token or token == "infeasible":
        return "generic_residual"
    return "other_coordinate_validation_reason"


def classify_coordinate_validation_failure_sample(sample: Mapping[str, Any]) -> str:
    for key, category in (
        ("signature_monotonic_precheck", "signature_forced_label"),
        ("ghost_overlap_forced_domain_precheck", "ghost_overlap_forced_domain"),
        ("ghost_y_overlap_precheck", "ghost_y_overlap_forced_label"),
        ("same_x_strip_capacity_precheck", "same_x_strip_capacity"),
        ("capacity_conflict", "same_x_strip_capacity"),
    ):
        value = sample.get(key)
        if isinstance(value, Mapping) and (
            bool(value.get("conflict", False))
            or bool(value.get("triggered", False))
            or key == "capacity_conflict"
        ):
            return category
    primary = classify_coordinate_validation_failure_reason(
        str(sample.get("failure_reason") or "")
    )
    if primary not in {"generic_residual", "unknown"}:
        return primary
    secondary = classify_coordinate_validation_failure_reason(
        str(sample.get("coordinate_validation_reason") or sample.get("reason") or "")
    )
    return secondary if secondary != "unknown" else primary


def _build_checks(
    *,
    post_acceptance_state_clean: bool,
    only_b5a_failed: bool,
    b5a_anchor_found: bool,
    reason_taxonomy_complete: bool,
) -> list[dict[str, Any]]:
    return [
        {
            "check_id": "post_acceptance_state_clean",
            "status": "pass" if post_acceptance_state_clean else "fail",
            "blocking": True,
            "detail": (
                "review-state and production acceptance are validated with runtime "
                "enablement still locked off"
            ),
        },
        {
            "check_id": "only_b5a_anchor_found_failed",
            "status": "pass" if only_b5a_failed else "fail",
            "blocking": True,
            "detail": "final preflight failed checks collapse to b5a_anchor_found",
        },
        {
            "check_id": "b5a_certified_anchor_still_missing",
            "status": "pass" if not b5a_anchor_found else "fail",
            "blocking": True,
            "detail": "B5A summary still has no certified anchor evidence",
        },
        {
            "check_id": "coordinate_validation_reason_taxonomy_complete",
            "status": "pass" if reason_taxonomy_complete else "fail",
            "blocking": False,
            "detail": (
                "generic coordinate_validation_infeasible still needs report-only "
                "reason localization"
            ),
        },
    ]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _copy_mapping_sequence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _int_or_zero(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _anchor_range_label(anchors: Sequence[int]) -> str | None:
    if not anchors:
        return None
    ordered = sorted(set(anchors))
    if len(ordered) == 1:
        return str(ordered[0])
    return f"{ordered[0]}-{ordered[-1]}"


def _markdown_to_text(markdown: str) -> str:
    return markdown.replace("# ", "").replace("## ", "")
