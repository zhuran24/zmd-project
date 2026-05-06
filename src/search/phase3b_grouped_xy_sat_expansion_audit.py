from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from src.search.exact_campaign import now_iso
from src.search.phase3b_forced_anchor_master import _check, _display_path, _mapping

GROUPED_XY_SAT_EXPANSION_AUDIT_SOURCE = "phase3b_grouped_xy_sat_expansion_audit_v1"

DEFAULT_LOG_CASES = (
    {
        "case_id": "grouped_xy_anchor118_120s",
        "family": "grouped_xy",
        "anchor_idx": 118,
        "log_path": Path(".codex_test_logs/phase3b/grouped_xy_probe_anchor118_120s_20260423.log"),
    },
    {
        "case_id": "grouped_xy_anchor119_120s",
        "family": "grouped_xy",
        "anchor_idx": 119,
        "log_path": Path(".codex_test_logs/phase3b/grouped_xy_probe_anchor119_120s_20260423.log"),
    },
    {
        "case_id": "active_guard_anchor118_45s",
        "family": "active_guard",
        "anchor_idx": 118,
        "log_path": Path(".codex_test_logs/phase3b/active_guard_anchor118_base_45s_20260423.log"),
    },
    {
        "case_id": "active_guard_anchor119_300s",
        "family": "active_guard",
        "anchor_idx": 119,
        "log_path": Path(
            ".codex_test_logs/phase3b/block_element_presolve_traces/"
            "active_guard_anchor119_300s_20260423.log"
        ),
    },
)

VARIABLES_RE = re.compile(r"^#Variables:\s*([0-9,'`]+)")
K_RE = re.compile(r"^(#k[A-Za-z0-9_]+):\s*([0-9,'`]+)")
RULE_RE = re.compile(r"rule '([^']+)' was applied ([0-9,'`]+) times")
RESPONSE_RE = re.compile(r"^([A-Za-z_]+):\s*(.+)$")


def build_phase3b_grouped_xy_sat_expansion_audit(
    project_root: Path,
    *,
    log_cases: Optional[Sequence[Mapping[str, Any]]] = None,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    started = time.perf_counter()
    cases = [
        _parse_case(project_root, case)
        for case in (log_cases or DEFAULT_LOG_CASES)
    ]
    comparison = _comparison(cases)
    outcome = (
        "grouped_xy_sat_expansion_blowup_detected"
        if bool(comparison.get("integer_encoding_blowup_detected", False))
        else (
            "grouped_xy_sat_expansion_audit_incomplete"
            if any(not bool(case.get("present", False)) for case in cases)
            else "grouped_xy_sat_expansion_no_blowup_detected"
        )
    )
    report: dict[str, Any] = {
        "metadata": {
            "source": GROUPED_XY_SAT_EXPANSION_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "presolve_sat_expansion_audit_not_proof",
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
        },
        "paths": {"project_root": _display_path(project_root, project_root)},
        "status": {
            "completed": True,
            "evaluated": all(bool(case.get("present", False)) for case in cases),
            "outcome": outcome,
            "recommendation": _recommendation(comparison),
        },
        "cases": cases,
        "comparison": comparison,
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }
    report["checks"] = _checks(report, cases)
    return report


def render_phase3b_grouped_xy_sat_expansion_audit_markdown(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    comparison = _mapping(report.get("comparison"))
    lines = [
        "# Phase 3B Grouped XY SAT Expansion Audit",
        "",
        "- Diagnostic semantics: presolve_sat_expansion_audit_not_proof",
        f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
        f"- proof_source: {bool(_mapping(report.get('metadata')).get('proof_source', True))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Cases",
        "",
        "| Case | Status | Initial Vars | Initial Element | Presolved Vars | New Bool Integer | SAT Booleans | Branches | Conflicts | Conflicts / 1k Branches |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in list(report.get("cases", [])):
        if not isinstance(case, Mapping):
            continue
        metrics = _mapping(case.get("metrics"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(case.get("case_id")),
                    _cell(metrics.get("status")),
                    _cell(metrics.get("initial_variables")),
                    _cell(metrics.get("initial_kElement")),
                    _cell(metrics.get("presolved_variables")),
                    _cell(metrics.get("new_bool_integer_encoding")),
                    _cell(metrics.get("sat_booleans")),
                    _cell(metrics.get("branches")),
                    _cell(metrics.get("conflicts")),
                    _cell(_round(metrics.get("conflicts_per_1k_branches"))),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Comparison",
            "",
            f"- Integer encoding blow-up detected: {comparison.get('integer_encoding_blowup_detected')}",
            f"- Grouped/active integer encoding ratio: {comparison.get('grouped_to_active_integer_encoding_ratio')}",
            f"- Grouped/active SAT booleans ratio: {comparison.get('grouped_to_active_sat_boolean_ratio')}",
            f"- Anchor118 terminal not reproduced: {comparison.get('anchor118_terminal_not_reproduced')}",
            f"- Grouped conflict density below 1 per 1k branches: {comparison.get('grouped_conflict_density_below_one_per_1k')}",
            f"- Recommended next action: {comparison.get('recommended_next_action')}",
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
    return "\n".join(lines) + "\n"


def render_phase3b_grouped_xy_sat_expansion_audit_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    comparison = _mapping(report.get("comparison"))
    return "\n".join(
        [
            "phase3b grouped xy sat expansion audit",
            "diagnostic_semantics=presolve_sat_expansion_audit_not_proof",
            f"solver_invoked={bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
            f"proof_source={bool(_mapping(report.get('metadata')).get('proof_source', True))}",
            f"outcome={status.get('outcome')}",
            f"integer_encoding_blowup_detected={comparison.get('integer_encoding_blowup_detected')}",
            f"grouped_to_active_integer_encoding_ratio={comparison.get('grouped_to_active_integer_encoding_ratio')}",
            f"grouped_to_active_sat_boolean_ratio={comparison.get('grouped_to_active_sat_boolean_ratio')}",
            f"recommended_next_action={comparison.get('recommended_next_action')}",
        ]
    ) + "\n"


def _parse_case(project_root: Path, case: Mapping[str, Any]) -> dict[str, Any]:
    path = _resolve(project_root, Path(case.get("log_path", "")))
    text = _read_text(path)
    parsed = _parse_log_text(text) if text is not None else {}
    return {
        "case_id": str(case.get("case_id")),
        "family": str(case.get("family")),
        "anchor_idx": case.get("anchor_idx"),
        "path": _display_path(project_root, path),
        "present": text is not None,
        "metrics": parsed,
    }


def _parse_log_text(text: str) -> dict[str, Any]:
    section = ""
    initial: dict[str, Any] = {"constraint_types": {}}
    presolved: dict[str, Any] = {"constraint_types": {}}
    rules: dict[str, int] = {}
    response: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("Initial satisfaction model") or line.startswith("Initial optimization model"):
            section = "initial"
            continue
        if line.startswith("Presolve summary:"):
            section = "rules"
            continue
        if line.startswith("Presolved satisfaction model") or line.startswith("Presolved optimization model"):
            section = "presolved"
            continue
        if line.startswith("CpSolverResponse summary:"):
            section = "response"
            continue
        if line.startswith("PresolvedNumVariables:"):
            presolved["reported_variables"] = _parse_scalar(line.split(":", 1)[1].strip())
            continue
        if section == "initial":
            _parse_model_line(initial, line)
        elif section == "presolved":
            _parse_model_line(presolved, line)
        elif section == "rules":
            match = RULE_RE.search(line)
            if match:
                rules[match.group(1)] = _parse_int(match.group(2))
        elif section == "response":
            match = RESPONSE_RE.match(line)
            if match:
                response[match.group(1)] = _parse_scalar(match.group(2).strip())
    branches = _as_float(response.get("branches"))
    conflicts = _as_float(response.get("conflicts"))
    deterministic = _as_float(response.get("deterministic_time"))
    return {
        "status": response.get("status"),
        "initial_variables": initial.get("variables"),
        "initial_kElement": _mapping(initial.get("constraint_types")).get("kElement"),
        "initial_kBoolOr": _mapping(initial.get("constraint_types")).get("kBoolOr"),
        "presolved_variables": presolved.get("reported_variables") or presolved.get("variables"),
        "presolved_kLinear1": _mapping(presolved.get("constraint_types")).get("kLinear1"),
        "presolved_kBoolOr": _mapping(presolved.get("constraint_types")).get("kBoolOr"),
        "new_bool_integer_encoding": rules.get("new_bool: integer encoding"),
        "variables_add_encoding_constraint": rules.get("variables: add encoding constraint"),
        "element_expanded": rules.get("element: expanded"),
        "sat_booleans": response.get("booleans"),
        "branches": response.get("branches"),
        "conflicts": response.get("conflicts"),
        "propagations": response.get("propagations"),
        "integer_propagations": response.get("integer_propagations"),
        "walltime": response.get("walltime"),
        "deterministic_time": response.get("deterministic_time"),
        "conflicts_per_1k_branches": _ratio(conflicts * 1000 if conflicts is not None else None, branches),
        "conflicts_per_deterministic_time": _ratio(conflicts, deterministic),
    }


def _parse_model_line(model: dict[str, Any], line: str) -> None:
    variables_match = VARIABLES_RE.match(line)
    if variables_match:
        model["variables"] = _parse_int(variables_match.group(1))
        return
    constraint_match = K_RE.match(line)
    if constraint_match:
        key = constraint_match.group(1).removeprefix("#")
        model["constraint_types"][key] = _parse_int(constraint_match.group(2))


def _comparison(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_case = {str(case.get("case_id")): case for case in cases}
    grouped119 = _metrics(by_case.get("grouped_xy_anchor119_120s"))
    active119 = _metrics(by_case.get("active_guard_anchor119_300s"))
    grouped118 = _metrics(by_case.get("grouped_xy_anchor118_120s"))
    active118 = _metrics(by_case.get("active_guard_anchor118_45s"))
    integer_ratio = _ratio(
        _as_float(grouped119.get("new_bool_integer_encoding")),
        _as_float(active119.get("new_bool_integer_encoding")),
    )
    boolean_ratio = _ratio(
        _as_float(grouped119.get("sat_booleans")),
        _as_float(active119.get("sat_booleans")),
    )
    density = _as_float(grouped119.get("conflicts_per_1k_branches"))
    anchor118_terminal_not_reproduced = (
        active118.get("status") in {"INFEASIBLE", "OPTIMAL", "FEASIBLE"}
        and grouped118.get("status") == "UNKNOWN"
    )
    blowup = bool((integer_ratio or 0) > 10 and (boolean_ratio or 0) > 2)
    return {
        "integer_encoding_blowup_detected": bool(blowup),
        "grouped_to_active_integer_encoding_ratio": integer_ratio,
        "grouped_to_active_sat_boolean_ratio": boolean_ratio,
        "grouped_conflict_density_below_one_per_1k": bool(density is not None and density < 1.0),
        "anchor118_terminal_not_reproduced": bool(anchor118_terminal_not_reproduced),
        "recommended_next_action": (
            "inspect_grouped_xy_padded_index_integer_encoding"
            if blowup
            else "grouped_xy_sat_expansion_not_explained"
        ),
        "interpretation": (
            "Grouped-XY shrinks initial proto Element/target channels, but CP-SAT "
            "integer encoding expands the flattened selector surface into a much larger SAT model."
        )
        if blowup
        else "No grouped SAT expansion blow-up was detected from the selected logs.",
    }


def _checks(report: Mapping[str, Any], cases: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    metadata = _mapping(report.get("metadata"))
    comparison = _mapping(report.get("comparison"))
    return [
        _check("solver_not_invoked", "pass" if not bool(metadata.get("solver_invoked", True)) else "fail", "solver_invoked=false"),
        _check("proof_source_false", "pass" if not bool(metadata.get("proof_source", True)) else "fail", "proof_source=false"),
        _check("all_logs_present", "pass" if all(bool(case.get("present", False)) for case in cases) else "fail", f"present={sum(1 for case in cases if bool(case.get('present', False)))}/{len(cases)}"),
        _check("integer_encoding_blowup_detected", "pass" if bool(comparison.get("integer_encoding_blowup_detected", False)) else "fail", str(comparison.get("grouped_to_active_integer_encoding_ratio"))),
        _check("conflict_density_low", "pass" if bool(comparison.get("grouped_conflict_density_below_one_per_1k", False)) else "fail", str(comparison.get("grouped_conflict_density_below_one_per_1k"))),
        _check("anchor118_terminal_not_reproduced_recorded", "pass" if bool(comparison.get("anchor118_terminal_not_reproduced", False)) else "skipped", str(comparison.get("anchor118_terminal_not_reproduced"))),
    ]


def _recommendation(comparison: Mapping[str, Any]) -> str:
    if bool(comparison.get("integer_encoding_blowup_detected", False)):
        return (
            "Block more grouped-XY solver time until the flattened selector integer "
            "encoding blow-up is reduced or otherwise explained by a no-solve model-shape audit."
        )
    return "No SAT expansion blow-up detected in the selected logs; inspect missing logs or run a bounded smoke if needed."


def _metrics(case: Optional[Mapping[str, Any]]) -> Mapping[str, Any]:
    return _mapping(_mapping(case).get("metrics"))


def _resolve(project_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    return project_root / path


def _read_text(path: Path) -> Optional[str]:
    try:
        raw = Path(path).read_bytes()
    except Exception:
        return None
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _parse_int(value: Any) -> int:
    return int(str(value).replace(",", "").replace("'", "").replace("`", "").strip())


def _parse_scalar(value: str) -> Any:
    text = str(value).strip()
    if text in {"NA", ""}:
        return text
    try:
        if any(char in text for char in (".", "e", "E")):
            return float(text)
        return _parse_int(text)
    except Exception:
        return text


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _round(value: Any) -> Any:
    try:
        return round(float(value), 4)
    except Exception:
        return value


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
