from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CASES: tuple[dict[str, str], ...] = (
    {
        "case": "default_table_element_anchor119_20s",
        "group": "baseline",
        "path": ".codex_test_logs/phase3b/base_anchor119_presolve_trace.log",
    },
    {
        "case": "wide_linear_family_distance_anchor119_20s",
        "group": "family_distance_encoding",
        "path": ".codex_test_logs/phase3b/base_anchor119_build_linear_family_distance_presolve_on.log",
    },
    {
        "case": "block64_linear_family_distance_anchor119_20s",
        "group": "block_element_shape",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block64_linear_family_distance_base_anchor119_presolve_on_20s.log",
    },
    {
        "case": "block128_linear_family_distance_anchor119_20s",
        "group": "block_element_shape",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block128_linear_family_distance_base_anchor119_presolve_on_20s.log",
    },
    {
        "case": "block64_linear_family_distance_anchor119_60s",
        "group": "block_element_shape",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block64_linear_family_distance_base_anchor119_presolve_on_60s.log",
    },
    {
        "case": "block64_low_encoding_anchor119_60s",
        "group": "low_encoding",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block64_linear_family_distance_base_anchor119_presolve_low_encoding_60s.log",
    },
    {
        "case": "block64_protocol_only_low_encoding_linearization0_anchor124_60s",
        "group": "protocol_vs_all_templates",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block64_low_encoding_linearization0_anchor124_60s.log",
    },
    {
        "case": "block64_all_templates_low_encoding_linearization0_anchor124_60s",
        "group": "protocol_vs_all_templates",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block64_all_templates_low_encoding_linearization0_anchor124_60s.log",
    },
    {
        "case": "block64_protocol_only_low_encoding_linearization0_anchor124_300s",
        "group": "protocol_vs_all_templates",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block64_linear_family_distance_anchor124_presolve_low_encoding_linearization0_300s.log",
    },
    {
        "case": "block64_all_templates_low_encoding_linearization0_anchor124_300s",
        "group": "protocol_vs_all_templates",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block64_all_templates_low_encoding_linearization0_anchor124_300s.log",
    },
    {
        "case": "block32_protocol_only_low_encoding_linearization0_anchor124_60s",
        "group": "block_size_matrix",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block32_low_encoding_linearization0_anchor124_60s.log",
    },
    {
        "case": "block72_protocol_only_low_encoding_linearization0_anchor124_60s",
        "group": "block_size_matrix",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block72_low_encoding_linearization0_anchor124_60s.log",
    },
    {
        "case": "block80_protocol_only_low_encoding_linearization0_anchor124_60s",
        "group": "block_size_matrix",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block80_low_encoding_linearization0_anchor124_60s.log",
    },
    {
        "case": "block88_protocol_only_low_encoding_linearization0_anchor124_60s",
        "group": "block_size_matrix",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block88_low_encoding_linearization0_anchor124_60s.log",
    },
    {
        "case": "block96_protocol_only_low_encoding_linearization0_anchor124_60s",
        "group": "block_size_matrix",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block96_low_encoding_linearization0_anchor124_60s.log",
    },
    {
        "case": "block104_protocol_only_low_encoding_linearization0_anchor124_60s",
        "group": "block_size_matrix",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block104_low_encoding_linearization0_anchor124_60s.log",
    },
    {
        "case": "block112_protocol_only_low_encoding_linearization0_anchor124_60s",
        "group": "block_size_matrix",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block112_low_encoding_linearization0_anchor124_60s.log",
    },
    {
        "case": "block128_protocol_only_low_encoding_linearization0_anchor124_60s",
        "group": "block_size_matrix",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block128_low_encoding_linearization0_anchor124_60s.log",
    },
    {
        "case": "block192_protocol_only_low_encoding_linearization0_anchor124_60s",
        "group": "block_size_matrix",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block192_low_encoding_linearization0_anchor124_60s.log",
    },
    {
        "case": "block256_protocol_only_low_encoding_linearization0_anchor124_60s",
        "group": "block_size_matrix",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block256_low_encoding_linearization0_anchor124_60s.log",
    },
    {
        "case": "block96_protocol_only_low_encoding_linearization0_anchor124_300s",
        "group": "block_size_matrix",
        "path": ".codex_test_logs/phase3b/block_element_presolve_traces/block96_low_encoding_linearization0_anchor124_300s.log",
    },
)

RULE_KEYS: tuple[str, ...] = (
    "element: expanded",
    "element: expanded value element",
    "element: reduce target domain",
    "table: expanded positive constraint",
    "new_bool: integer encoding",
    "new_bool: table expansion",
    "new_bool: complex linear expansion",
    "variables: add encoding constraint",
)

INT_RE = r"[0-9][0-9',]*"
RULE_RE = re.compile(
    rf"^- rule '([^']+)' was applied ({INT_RE}) times?\.?$"
)
K_RE = re.compile(rf"^(#k[A-Za-z0-9]+):\s+({INT_RE})")
VARIABLES_RE = re.compile(rf"^#Variables:\s+({INT_RE})")
FINGERPRINT_RE = re.compile(r"model_fingerprint:\s+(0x[0-9a-fA-F]+)")
PARAM_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^ ]+)")
RESPONSE_RE = re.compile(r"^([A-Za-z_]+):\s+(.+)$")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse Phase 3B CP-SAT presolve logs and compare expansion/search metrics."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--output-base",
        type=Path,
        default=Path(".artifacts/phase3b_presolve_log_comparison"),
        help="Output path without extension. .json, .md, and .txt are written.",
    )
    parser.add_argument(
        "--log",
        action="append",
        default=[],
        help="Optional case=path input. May be repeated. Defaults to curated C-direction logs.",
    )
    parser.add_argument(
        "--case-file",
        type=Path,
        default=None,
        help="Optional JSON case list. Accepts a list of {case, path, group?} objects or {'cases': [...]}",
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    inputs = _resolve_inputs(args.log, case_file=args.case_file, project_root=project_root)
    report = build_report(project_root, inputs)
    _print_summary(report)
    if not args.no_write:
        output_base = _resolve_output_base(project_root, args.output_base)
        _atomic_write_json(output_base.with_suffix(".json"), report)
        _atomic_write_text(output_base.with_suffix(".md"), render_markdown(report))
        _atomic_write_text(output_base.with_suffix(".txt"), render_text(report))
        print(f"presolve_log_comparison_json={_display_path(project_root, output_base.with_suffix('.json'))}")
        print(f"presolve_log_comparison_md={_display_path(project_root, output_base.with_suffix('.md'))}")
        print(f"presolve_log_comparison_txt={_display_path(project_root, output_base.with_suffix('.txt'))}")
    if not report["cases"]:
        return 1
    if report["missing_inputs"]:
        return 2
    return 0


def build_report(project_root: Path, inputs: Iterable[Mapping[str, str]]) -> dict[str, Any]:
    input_specs = tuple(inputs)
    cases: list[dict[str, Any]] = []
    missing_inputs: list[dict[str, str]] = []
    parse_warnings: list[str] = []
    for spec in input_specs:
        case = str(spec["case"])
        group = str(spec.get("group") or "custom")
        rel_path = str(spec["path"]).replace("\\", "/")
        path = _resolve_path(project_root, Path(rel_path))
        if not path.exists():
            missing_inputs.append({"case": case, "path": rel_path})
            continue
        records = parse_cp_sat_log(path, project_root, case=case, group=group)
        if not records:
            parse_warnings.append(f"No CP-SAT records parsed from {rel_path}")
            continue
        if len(records) == 1:
            cases.extend(records)
        else:
            for index, record in enumerate(records, start=1):
                record["case"] = f"{case}#{index}"
                record["segment_index"] = index
                cases.append(record)

    for record in cases:
        record["derived_metrics"] = _derive_metrics(record)
        record["missing_fields"] = _missing_fields(record)

    comparisons = build_comparisons(cases)
    field_coverage = _build_field_coverage(cases)
    findings = build_findings(cases, comparisons)
    generated_at = datetime.now().isoformat(timespec="seconds")
    return {
        "schema": "phase3b_parallel_C_presolve_log_comparison_v1",
        "diagnostic_semantics": "presolve_log_summary_not_proof_source",
        "generated_at": generated_at,
        "metadata": {
            "source": "phase3b_parallel_C_presolve_log_comparison_v1",
            "generated_at": generated_at,
            "diagnostic_semantics": "presolve_log_summary_not_proof_source",
            "solver_invoked": False,
        },
        "project_root": str(project_root),
        "input_count": len(input_specs),
        "parsed_case_count": len(cases),
        "missing_inputs": missing_inputs,
        "parse_warnings": parse_warnings,
        "field_coverage": field_coverage,
        "cases": cases,
        "comparisons": comparisons,
        "findings": findings,
        "recommendation": (
            "Use conflict productivity, presolved-variable pressure, and runtime boolean/propagation "
            "load together when choosing the next sprint. Raw branch count alone is a weak predictor "
            "because all-template block lowers work sharply while also lowering conflict signal. "
            "Next formulation work should preserve exact semantics while reducing the remaining "
            "block64 presolved model and testing whether all-template block can recover conflict density."
        ),
    }


def parse_cp_sat_log(
    path: Path,
    project_root: Path,
    *,
    case: str,
    group: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    section: str | None = None

    def start_record(line_number: int) -> None:
        nonlocal current, section
        if current is not None and _record_has_payload(current):
            records.append(_finalize_record(current))
        current = {
            "case": case,
            "group": group,
            "path": _display_path(project_root, path),
            "start_line": line_number,
            "parameters": {},
            "initial_model": {"constraint_types": {}},
            "presolved_model": {"constraint_types": {}},
            "presolve_rules": {},
            "solver_response": {},
            "metadata": _infer_metadata(case, path),
        }
        section = None

    with path.open("r", encoding=_detect_encoding(path), errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("Starting CP-SAT solver"):
                start_record(line_number)
                assert current is not None
                current["solver_version_line"] = line
                continue
            if current is None and (
                line.startswith("Parameters:")
                or line.startswith("Initial satisfaction model")
                or line.startswith("Initial optimization model")
            ):
                start_record(line_number)
            if current is None:
                continue

            if line.startswith("Parameters:"):
                current["parameters"].update(_parse_parameters(line))
                continue
            if line.startswith("Initial satisfaction model") or line.startswith(
                "Initial optimization model"
            ):
                if _record_has_payload(current) and current["solver_response"]:
                    start_record(line_number)
                    assert current is not None
                section = "initial_model"
                _capture_fingerprint(current[section], line)
                continue
            if line.startswith("Presolved satisfaction model") or line.startswith(
                "Presolved optimization model"
            ):
                section = "presolved_model"
                _capture_fingerprint(current[section], line)
                continue
            if line.startswith("Presolve summary:"):
                section = "presolve_rules"
                continue
            if line.startswith("CpSolverResponse summary:"):
                section = "solver_response"
                continue

            if line.startswith("PresolvedNum"):
                _parse_reported_presolved_count(current["presolved_model"], line)
                continue
            if section in ("initial_model", "presolved_model"):
                _parse_model_line(current[section], line)
                continue
            if section == "presolve_rules":
                _parse_presolve_rule(current["presolve_rules"], line)
                continue
            if section == "solver_response":
                _parse_response_line(current["solver_response"], line)
                continue

    if current is not None and _record_has_payload(current):
        records.append(_finalize_record(current))
    return records


def _parse_model_line(model: dict[str, Any], line: str) -> None:
    variables_match = VARIABLES_RE.match(line)
    if variables_match:
        model["variables"] = _parse_int(variables_match.group(1))
        return
    constraint_match = K_RE.match(line)
    if constraint_match:
        key = constraint_match.group(1).removeprefix("#")
        value = _parse_int(constraint_match.group(2))
        model["constraint_types"][key] = value


def _parse_presolve_rule(rules: dict[str, int], line: str) -> None:
    match = RULE_RE.match(line)
    if not match:
        return
    rules[match.group(1)] = _parse_int(match.group(2))


def _parse_reported_presolved_count(presolved: dict[str, Any], line: str) -> None:
    if line.startswith("PresolvedNumVariables:"):
        presolved["reported_variables"] = _parse_scalar(line.split(":", 1)[1].strip())
    elif line.startswith("PresolvedNumConstraints:"):
        presolved["reported_constraints"] = _parse_scalar(line.split(":", 1)[1].strip())
    elif line.startswith("PresolvedNumTerms:"):
        presolved["reported_terms"] = _parse_scalar(line.split(":", 1)[1].strip())


def _parse_response_line(response: dict[str, Any], line: str) -> None:
    match = RESPONSE_RE.match(line)
    if not match:
        return
    response[match.group(1)] = _parse_scalar(match.group(2).strip())


def _parse_parameters(line: str) -> dict[str, Any]:
    return {match.group(1): _parse_scalar(match.group(2)) for match in PARAM_RE.finditer(line)}


def _capture_fingerprint(model: dict[str, Any], line: str) -> None:
    match = FINGERPRINT_RE.search(line)
    if match:
        model["fingerprint"] = match.group(1)


def _finalize_record(record: dict[str, Any]) -> dict[str, Any]:
    for key in ("initial_model", "presolved_model"):
        constraints = record[key].get("constraint_types", {})
        record[key]["constraints_from_k_sum"] = sum(
            value for value in constraints.values() if isinstance(value, int)
        )
        record[key]["linear1"] = constraints.get("kLinear1")
        record[key]["linear2"] = constraints.get("kLinear2")
        record[key]["elements"] = constraints.get("kElement")
        record[key]["tables"] = constraints.get("kTable")
    for rule in RULE_KEYS:
        record["presolve_rules"].setdefault(rule, 0)
    return record


def build_comparisons(cases: list[dict[str, Any]]) -> dict[str, Any]:
    by_case = {str(record["case"]): record for record in cases}
    comparisons: dict[str, Any] = {
        "encoding_progression": _encoding_progression(by_case),
        "protocol_vs_all_templates": {},
        "rankings": _build_rankings(cases),
    }
    for seconds in (60, 300):
        protocol = by_case.get(
            f"block64_protocol_only_low_encoding_linearization0_anchor124_{seconds}s"
        )
        all_templates = by_case.get(
            f"block64_all_templates_low_encoding_linearization0_anchor124_{seconds}s"
        )
        if protocol and all_templates:
            comparisons["protocol_vs_all_templates"][f"{seconds}s"] = _compare_pair(
                protocol, all_templates
            )
    return comparisons


def _encoding_progression(by_case: Mapping[str, dict[str, Any]]) -> list[dict[str, Any]]:
    labels = (
        "default_table_element_anchor119_20s",
        "wide_linear_family_distance_anchor119_20s",
        "block64_linear_family_distance_anchor119_20s",
        "block128_linear_family_distance_anchor119_20s",
        "block64_linear_family_distance_anchor119_60s",
        "block64_low_encoding_anchor119_60s",
    )
    rows = []
    previous: dict[str, Any] | None = None
    for label in labels:
        record = by_case.get(label)
        if not record:
            continue
        row = {
            "case": label,
            "initial_variables": _get(record, "initial_model", "variables"),
            "initial_elements": _get(record, "initial_model", "elements"),
            "presolved_variables": _presolved_variables(record),
            "new_bool_integer_encoding": _rule(record, "new_bool: integer encoding"),
            "new_bool_table_expansion": _rule(record, "new_bool: table expansion"),
            "element_expanded": _rule(record, "element: expanded"),
            "branches": _response(record, "branches"),
            "conflicts": _response(record, "conflicts"),
        }
        if previous:
            row["presolved_variables_delta_pct_from_previous"] = _pct_delta(
                _presolved_variables(previous), _presolved_variables(record)
            )
        rows.append(row)
        previous = record
    return rows


def _compare_pair(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    fields = (
        ("presolved_variables", _presolved_variables(before), _presolved_variables(after)),
        ("booleans", _response(before, "booleans"), _response(after, "booleans")),
        ("propagations", _response(before, "propagations"), _response(after, "propagations")),
        ("branches", _response(before, "branches"), _response(after, "branches")),
        ("conflicts", _response(before, "conflicts"), _response(after, "conflicts")),
        (
            "deterministic_time",
            _response(before, "deterministic_time"),
            _response(after, "deterministic_time"),
        ),
    )
    deltas = {
        name: {
            "before": before_value,
            "after": after_value,
            "delta": _delta(before_value, after_value),
            "delta_pct": _pct_delta(before_value, after_value),
        }
        for name, before_value, after_value in fields
    }
    return {
        "before_case": before["case"],
        "after_case": after["case"],
        "deltas": deltas,
        "interpretation": (
            "All-template block is a work-size reduction if booleans/propagations/deterministic "
            "time fall; it is not necessarily a proof-speed improvement if conflicts also fall."
        ),
    }


def _build_rankings(cases: list[dict[str, Any]]) -> dict[str, Any]:
    matrix = [record for record in cases if record.get("group") == "block_size_matrix"]
    return {
        "block_size_matrix_highest_conflicts": _top_cases(matrix, ("solver_response", "conflicts"), reverse=True),
        "block_size_matrix_highest_conflicts_per_deterministic": _top_cases(
            matrix, ("derived_metrics", "conflicts_per_deterministic"), reverse=True
        ),
        "block_size_matrix_lowest_presolved_variables": _top_cases(
            matrix, ("presolved_model", "variables"), reverse=False
        ),
        "all_cases_lowest_runtime_booleans": _top_cases(
            cases, ("solver_response", "booleans"), reverse=False
        ),
    }


def build_findings(
    cases: list[dict[str, Any]], comparisons: Mapping[str, Any]
) -> list[dict[str, str]]:
    by_case = {str(record["case"]): record for record in cases}
    findings: list[dict[str, str]] = []
    default = by_case.get("default_table_element_anchor119_20s")
    block64 = by_case.get("block64_linear_family_distance_anchor119_20s")
    if default and block64:
        findings.append(
            {
                "id": "block_element_reduces_presolve_size_not_by_itself_certifying",
                "text": (
                    "Block64 with linear family/distance encoding sharply lowers presolved variables "
                    f"from {_fmt_int(_presolved_variables(default))} to {_fmt_int(_presolved_variables(block64))}, "
                    "but the corresponding 20s run remains UNKNOWN with zero branches/conflicts."
                ),
            }
        )
        findings.append(
            {
                "id": "default_is_dominated_by_integer_and_table_encoding",
                "text": (
                    "Default presolve is dominated by new_bool integer encoding "
                    f"({_fmt_int(_rule(default, 'new_bool: integer encoding'))}) and table expansion "
                    f"({_fmt_int(_rule(default, 'new_bool: table expansion'))}). Block64 cuts integer "
                    f"encoding to {_fmt_int(_rule(block64, 'new_bool: integer encoding'))} and table "
                    f"expansion to {_fmt_int(_rule(block64, 'new_bool: table expansion'))}, while increasing "
                    "raw Element count through block/local decomposition."
                ),
            }
        )
    proto300 = comparisons.get("protocol_vs_all_templates", {}).get("300s", {})
    if proto300:
        deltas = proto300.get("deltas", {})
        findings.append(
            {
                "id": "all_template_block_reduces_work_but_lowers_conflict_signal",
                "text": (
                    "At 300s, all-template block cuts runtime booleans "
                    f"{_fmt_pct(_mapping(deltas.get('booleans')).get('delta_pct'))} and propagations "
                    f"{_fmt_pct(_mapping(deltas.get('propagations')).get('delta_pct'))}, while conflicts move "
                    f"{_fmt_pct(_mapping(deltas.get('conflicts')).get('delta_pct'))}. This explains the mixed signal: "
                    "less solver work, but also less conflict production."
                ),
            }
        )
    findings.append(
        {
            "id": "raw_branch_count_is_not_enough",
            "text": (
                "Use conflicts per deterministic second, conflict density, booleans, and propagation load "
                "alongside branches. Branch count can remain high while conflict signal weakens or plateaus."
            ),
        }
    )
    return findings


def render_markdown(report: Mapping[str, Any]) -> str:
    cases = list(report.get("cases", []))
    metadata = _mapping(report.get("metadata"))
    lines = [
        "# Phase 3B Parallel C Presolve Log Comparison",
        "",
        f"Diagnostic semantics: {report.get('diagnostic_semantics')}.",
        "",
        "## Metadata",
        "",
        f"- Source: `{metadata.get('source', '')}`",
        f"- Generated at: `{metadata.get('generated_at', report.get('generated_at', ''))}`",
        f"- Solver invoked: `{str(metadata.get('solver_invoked', '')).lower()}`",
        "",
        "## Inputs",
        "",
        f"- Parsed cases: {report.get('parsed_case_count')}",
        f"- Missing inputs: {len(report.get('missing_inputs', []))}",
        f"- Cases missing reported presolved terms: {_mapping(report.get('field_coverage')).get('cases_missing_presolved_terms', 0)}",
        "",
        "## Presolve Shape",
        "",
        "| Case | Init vars | Init Elements | Init Tables | Presolved vars | Presolved constraints | Presolved terms | Presolved kLinear1 | Presolved kLinear2 | new_bool integer | new_bool table | element expanded |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for record in cases:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md(record["case"]),
                    _fmt_int(_get(record, "initial_model", "variables")),
                    _fmt_int(_get(record, "initial_model", "elements")),
                    _fmt_int(_get(record, "initial_model", "tables")),
                    _fmt_int(_presolved_variables(record)),
                    _fmt_int(_get(record, "presolved_model", "reported_constraints")),
                    _fmt_int(_get(record, "presolved_model", "reported_terms")),
                    _fmt_int(_get(record, "presolved_model", "linear1")),
                    _fmt_int(_get(record, "presolved_model", "linear2")),
                    _fmt_int(_rule(record, "new_bool: integer encoding")),
                    _fmt_int(_rule(record, "new_bool: table expansion")),
                    _fmt_int(_rule(record, "element: expanded")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Search Shape",
            "",
            "| Case | Status | Wall | Deterministic | Booleans | Branches | Conflicts | Propagations | Conflicts / det | Conflicts / 1k branches |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for record in cases:
        metrics = _mapping(record.get("derived_metrics"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _md(record["case"]),
                    _md(_response(record, "status")),
                    _fmt_float(_response(record, "walltime")),
                    _fmt_float(_response(record, "deterministic_time")),
                    _fmt_int(_response(record, "booleans")),
                    _fmt_int(_response(record, "branches")),
                    _fmt_int(_response(record, "conflicts")),
                    _fmt_int(_response(record, "propagations")),
                    _fmt_float(metrics.get("conflicts_per_deterministic")),
                    _fmt_float(metrics.get("conflicts_per_1k_branches")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Protocol-Only vs All-Template Block", ""])
    protocol = _mapping(_mapping(report.get("comparisons")).get("protocol_vs_all_templates"))
    if protocol:
        lines.extend(
            [
                "| Window | Metric | Protocol-only | All-template | Delta pct |",
                "| --- | --- | ---: | ---: | ---: |",
            ]
        )
        for window, comparison in protocol.items():
            for metric, delta in _mapping(comparison.get("deltas")).items():
                lines.append(
                    f"| {_md(window)} | {_md(metric)} | {_fmt_number(delta.get('before'))} | "
                    f"{_fmt_number(delta.get('after'))} | {_fmt_pct(delta.get('delta_pct'))} |"
                )
    else:
        lines.append("- No protocol/all-template comparison pairs were parsed.")
    lines.extend(["", "## Findings", ""])
    for finding in report.get("findings", []):
        lines.append(f"- `{finding.get('id')}`: {finding.get('text')}")
    lines.extend(["", "## Recommendation", "", str(report.get("recommendation", ""))])
    missing = report.get("missing_inputs", [])
    if missing:
        lines.extend(["", "## Missing Inputs", ""])
        for item in missing:
            lines.append(f"- `{item.get('case')}`: `{item.get('path')}`")
    return "\n".join(lines) + "\n"


def render_text(report: Mapping[str, Any]) -> str:
    metadata = _mapping(report.get("metadata"))
    lines = [
        "Phase 3B Parallel C presolve log comparison",
        f"diagnostic_semantics={report.get('diagnostic_semantics')}",
        f"metadata.source={metadata.get('source')}",
        f"metadata.solver_invoked={metadata.get('solver_invoked')}",
        f"parsed_case_count={report.get('parsed_case_count')}",
        f"missing_input_count={len(report.get('missing_inputs', []))}",
        "",
        "Findings:",
    ]
    for finding in report.get("findings", []):
        lines.append(f"- {finding.get('id')}: {finding.get('text')}")
    missing = report.get("missing_inputs", [])
    if missing:
        lines.extend(["", "Missing inputs:"])
        for item in missing:
            lines.append(f"- {item.get('case')}: {item.get('path')}")
    lines.extend(["", f"Recommendation: {report.get('recommendation')}"])
    return "\n".join(lines) + "\n"


def _derive_metrics(record: Mapping[str, Any]) -> dict[str, Any]:
    branches = _as_float(_response(record, "branches"))
    conflicts = _as_float(_response(record, "conflicts"))
    propagations = _as_float(_response(record, "propagations"))
    deterministic = _as_float(_response(record, "deterministic_time"))
    wall = _as_float(_response(record, "walltime"))
    return {
        "zero_branch_unknown": _response(record, "status") == "UNKNOWN" and branches == 0,
        "search_progress": bool((branches or 0) > 0 or (conflicts or 0) > 0),
        "conflicts_per_1k_branches": _ratio(conflicts * 1000 if conflicts is not None else None, branches),
        "conflicts_per_deterministic": _ratio(conflicts, deterministic),
        "conflicts_per_wall_second": _ratio(conflicts, wall),
        "propagations_per_branch": _ratio(propagations, branches),
        "integer_encoding_per_presolved_variable": _ratio(
            _as_float(_rule(record, "new_bool: integer encoding")),
            _as_float(_presolved_variables(record)),
        ),
    }


def _missing_fields(record: Mapping[str, Any]) -> list[str]:
    checks = {
        "initial_model.variables": _get(record, "initial_model", "variables"),
        "initial_model.elements": _get(record, "initial_model", "elements"),
        "initial_model.tables": _get(record, "initial_model", "tables"),
        "presolved_model.variables": _presolved_variables(record),
        "presolved_model.reported_constraints": _get(record, "presolved_model", "reported_constraints"),
        "presolved_model.reported_terms": _get(record, "presolved_model", "reported_terms"),
        "solver_response.status": _response(record, "status"),
        "solver_response.branches": _response(record, "branches"),
        "solver_response.conflicts": _response(record, "conflicts"),
        "solver_response.deterministic_time": _response(record, "deterministic_time"),
    }
    return [key for key, value in checks.items() if value is None]


def _build_field_coverage(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cases_missing_presolved_constraints": sum(
            "presolved_model.reported_constraints" in record.get("missing_fields", [])
            for record in cases
        ),
        "cases_missing_presolved_terms": sum(
            "presolved_model.reported_terms" in record.get("missing_fields", [])
            for record in cases
        ),
        "note": (
            "Some OR-Tools logs that enter search omit PresolvedNumConstraints/PresolvedNumTerms; "
            "the parser still captures presolved #k constraint types and solver response metrics."
        ),
    }


def _resolve_inputs(
    raw_logs: list[str],
    *,
    case_file: Path | None = None,
    project_root: Path = PROJECT_ROOT,
) -> tuple[dict[str, str], ...]:
    inputs: list[dict[str, str]] = []
    if case_file is not None:
        inputs.extend(_load_case_file(_resolve_path(project_root, case_file)))
    for raw in raw_logs:
        if "=" in raw:
            case, path = raw.split("=", 1)
        else:
            path = raw
            case = Path(path).stem
        inputs.append({"case": case.strip(), "group": "custom", "path": path.strip()})
    if not inputs:
        return DEFAULT_CASES
    return tuple(inputs)


def _load_case_file(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, Mapping) else payload
    if not isinstance(raw_cases, list):
        raise ValueError("--case-file must contain a JSON list or an object with a cases list")
    cases: list[dict[str, str]] = []
    for index, item in enumerate(raw_cases):
        if not isinstance(item, Mapping):
            raise ValueError(f"--case-file case #{index + 1} is not an object")
        case = str(item.get("case") or "").strip()
        path_value = str(item.get("path") or "").strip()
        if not case or not path_value:
            raise ValueError(f"--case-file case #{index + 1} requires case and path")
        cases.append(
            {
                "case": case,
                "group": str(item.get("group") or "custom"),
                "path": path_value,
            }
        )
    return cases


def _resolve_path(project_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _resolve_output_base(project_root: Path, output_base: Path) -> Path:
    if output_base.is_absolute():
        return output_base.resolve()
    return (project_root / output_base).resolve()


def _detect_encoding(path: Path) -> str:
    with path.open("rb") as handle:
        prefix = handle.read(4)
    if prefix.startswith(b"\xff\xfe") or prefix.startswith(b"\xfe\xff"):
        return "utf-16"
    if prefix.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    return "utf-8"


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _parse_int(value: str) -> int:
    return int(value.replace("'", "").replace(",", ""))


def _parse_scalar(value: str) -> Any:
    text = value.strip().rstrip(",")
    if text == "NA":
        return None
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    number_text = text.replace("'", "").replace(",", "")
    if re.fullmatch(r"-?[0-9]+", number_text):
        return int(number_text)
    if re.fullmatch(r"-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:e-?[0-9]+)?", number_text, re.I):
        return float(number_text)
    return text


def _infer_metadata(case: str, path: Path) -> dict[str, Any]:
    text = f"{case} {path.name}"
    block_match = re.search(r"block(\d+)", text)
    anchor_match = re.search(r"anchor(\d+)", text)
    seconds_match = re.search(r"_(\d+)s(?:\.log)?$", text)
    return {
        "anchor": int(anchor_match.group(1)) if anchor_match else None,
        "block_size": int(block_match.group(1)) if block_match else None,
        "all_templates": "all_templates" in text,
        "protocol_only": "protocol_only" in text or "protocol" in text and "all_templates" not in text,
        "low_encoding": "low_encoding" in text,
        "linearization0": "linearization0" in text,
        "time_limit_seconds_from_name": int(seconds_match.group(1)) if seconds_match else None,
    }


def _record_has_payload(record: Mapping[str, Any]) -> bool:
    return bool(
        _mapping(record.get("initial_model")).get("variables")
        or _mapping(record.get("presolved_model")).get("variables")
        or record.get("solver_response")
        or record.get("presolve_rules")
    )


def _get(record: Mapping[str, Any], section: str, field: str) -> Any:
    return _mapping(record.get(section)).get(field)


def _rule(record: Mapping[str, Any], rule: str) -> Any:
    return _mapping(record.get("presolve_rules")).get(rule)


def _response(record: Mapping[str, Any], key: str) -> Any:
    return _mapping(record.get("solver_response")).get(key)


def _presolved_variables(record: Mapping[str, Any]) -> Any:
    presolved = _mapping(record.get("presolved_model"))
    return presolved.get("reported_variables", presolved.get("variables"))


def _top_cases(
    cases: list[dict[str, Any]],
    path: tuple[str, str],
    *,
    reverse: bool,
    limit: int = 5,
) -> list[dict[str, Any]]:
    items = []
    for record in cases:
        value = _get_nested(record, path)
        if value is None:
            continue
        items.append({"case": record["case"], "value": value})
    return sorted(items, key=lambda item: item["value"], reverse=reverse)[:limit]


def _get_nested(record: Mapping[str, Any], path: tuple[str, str]) -> Any:
    section = _mapping(record.get(path[0]))
    return section.get(path[1])


def _delta(before: Any, after: Any) -> Any:
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        return after - before
    return None


def _pct_delta(before: Any, after: Any) -> Any:
    if not isinstance(before, (int, float)) or not isinstance(after, (int, float)):
        return None
    if before == 0:
        return None
    return (after - before) * 100.0 / before


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _fmt_int(value: Any) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float) and value.is_integer():
        return f"{int(value):,}"
    return ""


def _fmt_float(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):.3f}".rstrip("0").rstrip(".")
    return ""


def _fmt_number(value: Any) -> str:
    if isinstance(value, int):
        return _fmt_int(value)
    if isinstance(value, float):
        return _fmt_float(value)
    return ""


def _fmt_pct(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{float(value):+.1f}%"
    return ""


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _print_summary(report: Mapping[str, Any]) -> None:
    comparisons = _mapping(report.get("comparisons"))
    protocol = _mapping(comparisons.get("protocol_vs_all_templates"))
    missing = list(report.get("missing_inputs", []))
    print("phase3b parallel C presolve log comparison")
    print(f"- parsed cases: {report.get('parsed_case_count')}")
    print(f"- missing inputs: {len(missing)}")
    for item in missing:
        print(f"  - missing_input case={item.get('case')} path={item.get('path')}")
    print(f"- protocol/all-template pairs: {len(protocol)}")
    for finding in report.get("findings", []):
        print(f"- {finding.get('id')}: {finding.get('text')}")
    print(f"- recommendation: {report.get('recommendation')}")


if __name__ == "__main__":
    raise SystemExit(main())
