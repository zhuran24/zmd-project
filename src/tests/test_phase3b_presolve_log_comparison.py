from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_phase3b_presolve_log_comparison.py"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "phase3b_presolve_log_comparison_under_test", SCRIPT_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parser_module = _load_module()


def _synthetic_log(
    *,
    variables: int = 1000,
    elements: int = 10,
    tables: int = 2,
    presolved_variables: int = 500,
    booleans: int = 100,
    branches: int = 20,
    conflicts: int = 4,
    propagations: int = 1000,
    deterministic_time: float = 0.5,
    walltime: float = 1.25,
) -> str:
    return f"""
Starting CP-SAT solver v9.15.6755
Parameters: random_seed: 1 max_time_in_seconds: 60 log_search_progress: true cp_model_presolve: true num_search_workers: 1
Initial satisfaction model '': (model_fingerprint: 0xabc)
#Variables: {variables:,} (900 primary variables)
#kElement: {elements}
#kTable: {tables}
#kLinear1: 30
#kLinear2: 40
Presolve summary:
  - rule 'element: expanded' was applied {elements} times.
  - rule 'new_bool: integer encoding' was applied 100 times.
  - rule 'new_bool: table expansion' was applied 4 times.
  - rule 'table: expanded positive constraint' was applied {tables} times.
Presolved satisfaction model '': (model_fingerprint: 0xdef)
#Variables: {presolved_variables:,} (400 primary variables)
#kLinear1: 60
#kLinear2: 80
PresolvedNumVariables: {presolved_variables}
PresolvedNumConstraints: 900
PresolvedNumTerms: 1200
CpSolverResponse summary:
status: UNKNOWN
objective: NA
best_bound: NA
integers: 42
booleans: {booleans}
conflicts: {conflicts}
branches: {branches}
propagations: {propagations}
integer_propagations: 500
restarts: 0
lp_iterations: 0
walltime: {walltime}
usertime: {walltime}
deterministic_time: {deterministic_time}
gap_integral: 0
""".lstrip()


def _write_case_file(path: Path, cases: list[dict[str, str]]) -> None:
    path.write_text(json.dumps({"cases": cases}, indent=2), encoding="utf-8")


def test_parser_reads_utf8_log(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "utf8.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(_synthetic_log(), encoding="utf-8")

    records = parser_module.parse_cp_sat_log(
        log_path, tmp_path, case="utf8_case", group="synthetic"
    )

    assert len(records) == 1
    record = records[0]
    assert record["initial_model"]["variables"] == 1000
    assert record["initial_model"]["elements"] == 10
    assert record["presolved_model"]["reported_terms"] == 1200
    assert record["presolve_rules"]["element: expanded"] == 10
    assert record["solver_response"]["branches"] == 20


def test_parser_reads_utf16le_bom_log(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "utf16.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(_synthetic_log(variables=1200), encoding="utf-16")

    records = parser_module.parse_cp_sat_log(
        log_path, tmp_path, case="utf16_case", group="synthetic"
    )

    assert len(records) == 1
    assert records[0]["initial_model"]["variables"] == 1200
    assert records[0]["solver_response"]["status"] == "UNKNOWN"


def test_build_report_records_missing_input(tmp_path: Path) -> None:
    report = parser_module.build_report(
        tmp_path,
        [{"case": "missing_case", "group": "synthetic", "path": "logs/missing.log"}],
    )

    assert report["parsed_case_count"] == 0
    assert report["missing_inputs"] == [
        {"case": "missing_case", "path": "logs/missing.log"}
    ]
    assert report["metadata"]["solver_invoked"] is False
    assert "Missing inputs" in parser_module.render_text(report)
    assert "missing_case" in parser_module.render_markdown(report)


def test_protocol_vs_all_template_comparison_from_synthetic_logs(tmp_path: Path) -> None:
    protocol_path = tmp_path / "logs" / "protocol.log"
    all_path = tmp_path / "logs" / "all.log"
    protocol_path.parent.mkdir(parents=True)
    protocol_path.write_text(
        _synthetic_log(
            presolved_variables=500,
            booleans=1000,
            branches=200,
            conflicts=10,
            propagations=10000,
            deterministic_time=2.0,
        ),
        encoding="utf-8",
    )
    all_path.write_text(
        _synthetic_log(
            presolved_variables=250,
            booleans=400,
            branches=180,
            conflicts=8,
            propagations=3000,
            deterministic_time=1.0,
        ),
        encoding="utf-8",
    )

    report = parser_module.build_report(
        tmp_path,
        [
            {
                "case": "block64_protocol_only_low_encoding_linearization0_anchor124_60s",
                "group": "protocol_vs_all_templates",
                "path": "logs/protocol.log",
            },
            {
                "case": "block64_all_templates_low_encoding_linearization0_anchor124_60s",
                "group": "protocol_vs_all_templates",
                "path": "logs/all.log",
            },
        ],
    )

    deltas = report["comparisons"]["protocol_vs_all_templates"]["60s"]["deltas"]
    assert deltas["presolved_variables"]["delta_pct"] == -50.0
    assert deltas["booleans"]["delta_pct"] == -60.0
    assert deltas["conflicts"]["delta_pct"] == -20.0
    assert "all_template_block_reduces_work_but_lowers_conflict_signal" not in {
        finding["id"] for finding in report["findings"]
    }


def test_cli_no_write_skips_outputs_and_case_file_works(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    log_path = project_root / "logs" / "case.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(_synthetic_log(), encoding="utf-8")
    case_file = tmp_path / "cases.json"
    _write_case_file(
        case_file,
        [{"case": "custom_case", "group": "synthetic", "path": "logs/case.log"}],
    )
    output_base = tmp_path / "out" / "report"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--project-root",
            str(project_root),
            "--case-file",
            str(case_file),
            "--output-base",
            str(output_base),
            "--no-write",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b parallel C presolve log comparison" in result.stdout
    assert not output_base.with_suffix(".json").exists()
    assert not output_base.with_suffix(".md").exists()
    assert not output_base.with_suffix(".txt").exists()


def test_cli_default_write_creates_json_markdown_and_text(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    log_path = project_root / "logs" / "case.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(_synthetic_log(), encoding="utf-8")
    case_file = tmp_path / "cases.json"
    _write_case_file(
        case_file,
        [{"case": "custom_case", "group": "synthetic", "path": "logs/case.log"}],
    )
    output_base = tmp_path / "out" / "report"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--project-root",
            str(project_root),
            "--case-file",
            str(case_file),
            "--output-base",
            str(output_base),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "presolve_log_comparison_json=" in result.stdout
    payload = json.loads(output_base.with_suffix(".json").read_text(encoding="utf-8"))
    assert payload["metadata"]["source"] == "phase3b_parallel_C_presolve_log_comparison_v1"
    assert payload["metadata"]["diagnostic_semantics"] == (
        "presolve_log_summary_not_proof_source"
    )
    assert payload["metadata"]["solver_invoked"] is False
    assert output_base.with_suffix(".md").exists()
    assert output_base.with_suffix(".txt").exists()


def test_cli_missing_input_is_explicit_and_nonzero(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    case_file = tmp_path / "cases.json"
    _write_case_file(
        case_file,
        [{"case": "missing_case", "group": "synthetic", "path": "logs/missing.log"}],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--project-root",
            str(project_root),
            "--case-file",
            str(case_file),
            "--no-write",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "- missing inputs: 1" in result.stdout
    assert "missing_input case=missing_case path=logs/missing.log" in result.stdout
