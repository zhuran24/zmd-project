from __future__ import annotations

from pathlib import Path

from src.search.phase3b.joined_xy.sat_expansion_audit import (
    build_phase3b_joined_xy_sat_expansion_audit,
    render_phase3b_joined_xy_sat_expansion_audit_markdown,
    render_phase3b_joined_xy_sat_expansion_audit_text,
)


def test_joined_xy_sat_expansion_audit_detects_recovered_scale(
    tmp_path: Path,
) -> None:
    cases = [
        _case(tmp_path, "active_guard_anchor118_45s", "active_guard", 118, 130, 20, 132, 3, 200, 2, 1, status="INFEASIBLE"),
        _case(tmp_path, "active_guard_anchor119_300s", "active_guard", 119, 130, 20, 132, 3, 200, 80, 24),
        _case(tmp_path, "grouped_xy_anchor118_120s", "grouped_xy", 118, 100, 10, 700, 500, 1300, 600, 2),
        _case(tmp_path, "grouped_xy_anchor119_120s", "grouped_xy", 119, 100, 10, 700, 500, 1300, 1000, 1),
        _case(tmp_path, "joined_xy_anchor118_60s", "joined_xy", 118, 134, 22, 134, 3, 205, 2, 1, status="INFEASIBLE"),
        _case(tmp_path, "joined_xy_anchor118_60s_seed2", "joined_xy", 118, 134, 22, 134, 3, 205, 2, 1, status="INFEASIBLE"),
        _case(tmp_path, "joined_xy_anchor119_120s", "joined_xy", 119, 134, 22, 134, 3, 205, 70, 10),
    ]

    report = build_phase3b_joined_xy_sat_expansion_audit(tmp_path, log_cases=cases)

    assert report["metadata"]["solver_invoked"] is False
    assert report["status"]["outcome"] == "joined_xy_sat_expansion_recovered_active_guard_scale"
    assert report["comparison"]["joined_xy_recovered_active_guard_scale"] is True
    assert report["comparison"]["anchor118_terminal_reproduced"] is True
    assert report["comparison"]["anchor118_seed2_terminal_reproduced"] is True
    assert report["comparison"]["joined_anchor119_search_progress"] is True
    assert "Joined-XY SAT Expansion Audit" in render_phase3b_joined_xy_sat_expansion_audit_markdown(report)
    assert "joined_xy_recovered_active_guard_scale=True" in render_phase3b_joined_xy_sat_expansion_audit_text(report)


def _case(
    tmp_path: Path,
    case_id: str,
    family: str,
    anchor_idx: int,
    initial_vars: int,
    elements: int,
    presolved_vars: int,
    new_bool_integer: int,
    sat_booleans: int,
    branches: int,
    conflicts: int,
    *,
    status: str = "UNKNOWN",
) -> dict[str, object]:
    path = tmp_path / f"{case_id}.log"
    path.write_text(
        f"""
Starting CP-SAT solver v9.15.6755
Initial satisfaction model '': (model_fingerprint: 0xabc)
#Variables: {initial_vars}
#kElement: {elements}
#kBoolOr: 7
Presolve summary:
  - rule 'new_bool: integer encoding' was applied {new_bool_integer} times.
  - rule 'variables: add encoding constraint' was applied {new_bool_integer} times.
Presolved satisfaction model '': (model_fingerprint: 0xdef)
#Variables: {presolved_vars}
#kLinear1: 5
PresolvedNumVariables: {presolved_vars}
CpSolverResponse summary:
status: {status}
booleans: {sat_booleans}
conflicts: {conflicts}
branches: {branches}
propagations: 1000
integer_propagations: 900
walltime: 1.0
deterministic_time: 0.5
""".lstrip(),
        encoding="utf-8",
    )
    return {
        "case_id": case_id,
        "family": family,
        "anchor_idx": anchor_idx,
        "log_path": path,
    }
