from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

GROUP_PACKING_SOUNDNESS_SOURCE = "phase3b_group_packing_soundness_gate_v1"
DEFAULT_RUNTIME_DIAGNOSTIC_PATH = Path(
    ".artifacts/phase3b_runtime_group_packing/runtime_group_packing_69x19_samples51.json"
)


def build_phase3b_group_packing_soundness_gate(
    project_root: Path,
    *,
    runtime_diagnostic_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    runtime_path = _resolve_path(
        project_root,
        runtime_diagnostic_path
        if runtime_diagnostic_path is not None
        else DEFAULT_RUNTIME_DIAGNOSTIC_PATH,
    )
    runtime, load_error = _load_json_mapping(runtime_path)
    candidate = _mapping(runtime.get("candidate")) if runtime else {}
    diagnostics = _mapping(runtime.get("diagnostics")) if runtime else {}
    probe = _mapping(diagnostics.get("group_packing_probe"))
    samples = [
        dict(entry)
        for entry in list(probe.get("samples", []))
        if isinstance(entry, Mapping)
    ]
    sample_assessments = [_assess_sample(entry) for entry in samples]
    terminal_safe_count = sum(
        1 for entry in sample_assessments if bool(entry.get("terminal_safe", False))
    )
    prefix_conditioned_count = sum(
        1
        for entry in sample_assessments
        if entry.get("soundness_class") == "prefix_conditioned_only"
    )
    infeasible_count = int(probe.get("infeasible_count", 0))
    sample_count = int(probe.get("sample_count", len(samples)))
    all_samples_infeasible = bool(
        sample_count > 0
        and infeasible_count == sample_count
        and int(probe.get("feasible_count", 0)) == 0
        and int(probe.get("unknown_count", 0)) == 0
        and int(probe.get("skipped_count", 0)) == 0
    )
    terminal_elimination_sound = bool(
        runtime is not None
        and load_error is None
        and all_samples_infeasible
        and sample_count == len(sample_assessments)
        and terminal_safe_count == sample_count
    )
    soundness_blockers = _soundness_blockers(
        runtime_present=runtime is not None and load_error is None,
        all_samples_infeasible=all_samples_infeasible,
        sample_count=sample_count,
        terminal_safe_count=terminal_safe_count,
        prefix_conditioned_count=prefix_conditioned_count,
    )
    return {
        "metadata": {
            "source": GROUP_PACKING_SOUNDNESS_SOURCE,
            "generated_at": now_iso(),
        },
        "paths": {
            "project_root": str(project_root),
            "runtime_group_packing": _display_path(project_root, runtime_path),
        },
        "candidate": dict(candidate),
        "soundness": {
            "runtime_diagnostic_present": runtime is not None and load_error is None,
            "runtime_diagnostic_load_error": load_error,
            "all_samples_infeasible": bool(all_samples_infeasible),
            "sample_count": int(sample_count),
            "terminal_safe_sample_count": int(terminal_safe_count),
            "prefix_conditioned_sample_count": int(prefix_conditioned_count),
            "terminal_elimination_sound": bool(terminal_elimination_sound),
            "blocked_by": soundness_blockers,
            "recommendation": _recommendation(
                terminal_elimination_sound=terminal_elimination_sound,
                blockers=soundness_blockers,
            ),
        },
        "sample_assessments": sample_assessments,
        "checks": _checks(
            runtime_present=runtime is not None and load_error is None,
            all_samples_infeasible=all_samples_infeasible,
            terminal_elimination_sound=terminal_elimination_sound,
            sample_count=sample_count,
            terminal_safe_count=terminal_safe_count,
            prefix_conditioned_count=prefix_conditioned_count,
        ),
    }


def render_phase3b_group_packing_soundness_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    soundness = _mapping(report.get("soundness"))
    lines = [
        "# Phase 3B Group-Packing Soundness Gate",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- All samples infeasible: {bool(soundness.get('all_samples_infeasible', False))}",
        f"- Terminal elimination sound: {bool(soundness.get('terminal_elimination_sound', False))}",
        f"- Sample count: {soundness.get('sample_count', 0)}",
        f"- Terminal-safe samples: {soundness.get('terminal_safe_sample_count', 0)}",
        f"- Prefix-conditioned samples: {soundness.get('prefix_conditioned_sample_count', 0)}",
        f"- Recommendation: {soundness.get('recommendation')}",
        "",
        "## Blockers",
        "",
    ]
    blockers = [str(item) for item in list(soundness.get("blocked_by", []))]
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")
    sample_assessments = [
        entry
        for entry in list(report.get("sample_assessments", []))
        if isinstance(entry, Mapping)
    ]
    if sample_assessments:
        lines.extend(
            [
                "",
                "## Samples",
                "",
                "| Anchor | Group | Status | Class | Required | After Ghost | At Failure |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in sample_assessments:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("anchor_idx")),
                        _markdown_cell(entry.get("group_id")),
                        _markdown_cell(entry.get("solver_status")),
                        _markdown_cell(entry.get("soundness_class")),
                        _markdown_cell(entry.get("required_count")),
                        _markdown_cell(entry.get("surviving_after_blocked_count")),
                        _markdown_cell(entry.get("surviving_at_failure_count")),
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


def render_phase3b_group_packing_soundness_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    soundness = _mapping(report.get("soundness"))
    lines = [
        "Phase 3B group-packing soundness gate",
        f"candidate={candidate.get('key')}",
        f"all_samples_infeasible={bool(soundness.get('all_samples_infeasible', False))}",
        f"terminal_elimination_sound={bool(soundness.get('terminal_elimination_sound', False))}",
        f"sample_count={soundness.get('sample_count', 0)}",
        f"terminal_safe_sample_count={soundness.get('terminal_safe_sample_count', 0)}",
        f"prefix_conditioned_sample_count={soundness.get('prefix_conditioned_sample_count', 0)}",
        f"blocked_by={','.join(str(item) for item in list(soundness.get('blocked_by', [])))}",
        f"recommendation={soundness.get('recommendation')}",
    ]
    for entry in list(report.get("sample_assessments", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "sample "
                f"anchor={entry.get('anchor_idx')} "
                f"group={entry.get('group_id')} "
                f"status={entry.get('solver_status')} "
                f"class={entry.get('soundness_class')} "
                f"required={entry.get('required_count')} "
                f"after_ghost={entry.get('surviving_after_blocked_count')} "
                f"at_failure={entry.get('surviving_at_failure_count')}"
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


def _assess_sample(sample: Mapping[str, Any]) -> Dict[str, Any]:
    required_count = int(sample.get("required_count", 0))
    surviving_after_blocked = int(sample.get("surviving_after_blocked_count", 0))
    surviving_at_failure = int(sample.get("surviving_at_failure_count", 0))
    exact_feasible = sample.get("exact_feasible")
    solver_status = sample.get("solver_status")
    if exact_feasible is not False:
        soundness_class = "not_infeasible"
        terminal_safe = False
        reason = "sample is not exact-infeasible"
    elif surviving_after_blocked < required_count:
        soundness_class = "ghost_only_candidate_count_below_required"
        terminal_safe = True
        reason = "ghost-only surviving candidates are below required count"
    elif bool(sample.get("unconditional_exact_infeasible", False)):
        soundness_class = "unconditional_exact_infeasible"
        terminal_safe = True
        reason = "sample carries explicit unconditional infeasibility evidence"
    elif surviving_at_failure < surviving_after_blocked:
        soundness_class = "prefix_conditioned_only"
        terminal_safe = False
        reason = "infeasibility depends on committed prefix cells, not only ghost cells"
    else:
        soundness_class = "unclassified_infeasible"
        terminal_safe = False
        reason = "infeasibility has no terminal-safe proof class"
    return {
        "anchor_idx": sample.get("anchor_idx"),
        "group_id": sample.get("group_id"),
        "facility_type": sample.get("facility_type"),
        "solver_status": solver_status,
        "exact_feasible": exact_feasible,
        "required_count": int(required_count),
        "surviving_after_blocked_count": int(surviving_after_blocked),
        "surviving_at_failure_count": int(surviving_at_failure),
        "greedy_selected_count": int(sample.get("greedy_selected_count", 0)),
        "soundness_class": soundness_class,
        "terminal_safe": bool(terminal_safe),
        "reason": reason,
    }


def _soundness_blockers(
    *,
    runtime_present: bool,
    all_samples_infeasible: bool,
    sample_count: int,
    terminal_safe_count: int,
    prefix_conditioned_count: int,
) -> list[str]:
    blockers: list[str] = []
    if not runtime_present:
        blockers.append("runtime_group_packing_missing")
    if sample_count <= 0:
        blockers.append("runtime_group_packing_samples_missing")
    if not all_samples_infeasible:
        blockers.append("runtime_group_packing_not_uniformly_infeasible")
    if prefix_conditioned_count > 0:
        blockers.append("prefix_conditioned_evidence_not_terminal_safe")
    if sample_count > 0 and terminal_safe_count < sample_count:
        blockers.append("terminal_safe_coverage_incomplete")
    return _dedupe(blockers)


def _recommendation(*, terminal_elimination_sound: bool, blockers: list[str]) -> str:
    if terminal_elimination_sound:
        return "Group-packing evidence is terminal-safe for the assessed samples."
    return (
        "Do not promote group-packing to terminal pre-master proof; resolve soundness blockers: "
        + ", ".join(blockers)
    )


def _checks(
    *,
    runtime_present: bool,
    all_samples_infeasible: bool,
    terminal_elimination_sound: bool,
    sample_count: int,
    terminal_safe_count: int,
    prefix_conditioned_count: int,
) -> list[Dict[str, str]]:
    return [
        _check(
            "runtime_group_packing_present",
            "pass" if runtime_present else "fail",
            "runtime diagnostic loaded" if runtime_present else "runtime diagnostic missing",
        ),
        _check(
            "all_samples_infeasible",
            "pass" if all_samples_infeasible else "fail",
            f"sample_count={sample_count}",
        ),
        _check(
            "no_prefix_conditioned_evidence",
            "pass" if prefix_conditioned_count == 0 else "fail",
            f"prefix_conditioned_sample_count={prefix_conditioned_count}",
        ),
        _check(
            "terminal_safe_coverage",
            "pass" if terminal_elimination_sound else "fail",
            f"terminal_safe_sample_count={terminal_safe_count}; sample_count={sample_count}",
        ),
    ]


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


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
