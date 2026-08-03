"""W0 G1: the independent front-viability audit and its negative battery.

research-only.  The audit is the G1 gate's second opinion, so the tests care
about two things: that a legal geometry passes, and that every registered issue
code is actually reachable by a concrete defect.  A checker whose codes cannot
fire is decoration.
"""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
G1_DIR = PROJECT_ROOT / "docs" / "research" / "w0_front_aware_20260803"
AUDIT_PATH = G1_DIR / "front_viability_audit.py"
for _path in (str(PROJECT_ROOT), str(G1_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import front_viability_audit as fva  # noqa: E402

pytestmark = pytest.mark.evidence


def _toy():
    return fva._toy_inputs()


def test_toy_geometry_passes() -> None:
    """[23] A hand-built legal geometry on a toy board audits clean."""
    rules, instances, geometry = _toy()
    report = fva.audit(geometry, rules, instances)
    assert report["verdict"] == "PASS", report["issues"]
    assert report["issues"] == []
    summary = report["summary"]
    assert summary["manufacturing_placements"] == 2
    assert summary["dead_for_any_actual_class"] == 0
    assert summary["class_census"] == {"3L": 1, "3O2": 1}
    assert summary["power"]["irredundant"] is True
    assert summary["hole"]["area"] == 42
    assert summary["hole"]["min_side"] == 6
    assert summary["free_space"]["anchor_components"] == 1
    assert report["authority"] == {
        "is_authoritative": False,
        "carries_bound": False,
        "ledger_effect": "none",
    }


def test_toy_geometry_with_a_core_passes() -> None:
    """[23b] The 24x24 variant makes the 20 core front cells a live reserve."""
    rules, instances, geometry = fva._toy_inputs(with_core=True)
    report = fva.audit(geometry, rules, instances)
    assert report["verdict"] == "PASS", report["issues"]
    assert report["summary"]["reserved_front_cells"] == 7 + 7 + 20


# --------------------------------------------------------------------------
# negative battery -- one concrete defect per issue code
# --------------------------------------------------------------------------


def _mutate_authority(geometry, rules):
    geometry["authority"]["is_authoritative"] = True


def _mutate_body_out_of_grid(geometry, rules):
    geometry["placements"][0]["anchor"] = [18, 18]


def _mutate_body_overlap(geometry, rules):
    geometry["placements"][1]["anchor"] = [4, 3]


def _mutate_fixed_furniture(geometry, rules):
    geometry["fixed_furniture"].pop()


def _mutate_class_census(geometry, rules):
    geometry["placements"][1]["operation_class"] = "3L"


def _mutate_front_offset(geometry, rules):
    # The retired "second cell outside" formula: body top edge is y=5, so the
    # front is y=6 and the retired answer was y=7.
    geometry["placements"][0]["active_input_fronts"] = [[3, 7]]


def _mutate_front_out_of_grid(geometry, rules):
    geometry["placements"][0]["anchor"] = [3, 17]
    geometry["placements"][0]["active_input_fronts"] = [[3, 20]]
    geometry["placements"][0]["active_output_fronts"] = [[3, 16]]


def _mutate_front_blocked(geometry, rules):
    # Park the second machine so its body covers the first machine's output front.
    geometry["placements"][1]["anchor"] = [3, 0]
    geometry["placements"][1]["active_input_fronts"] = [[3, -1]]
    geometry["placements"][1]["active_output_fronts"] = [[3, 3], [4, 3]]


def _mutate_active_port_count(geometry, rules):
    geometry["placements"][1]["active_output_fronts"] = [[8, 6]]


def _mutate_mode_not_offered(geometry, rules):
    geometry["placements"][0]["mode"] = "XX"


def _mutate_dead_body(geometry, rules):
    """Wall the line machine in on three sides; only the south stays open.

    Document 19's fourth hand-checked case: modes put inputs and outputs on
    opposite sides, so one open side can never satisfy both.  The 3x3 at (3,3)
    has fronts at y=6 (top), x=2 (left) and x=6 (right); these six 2x2 poles
    cover exactly those nine cells and nothing else the machines need.
    """
    geometry["power_poles"] = [
        {"anchor": [1, 2]},   # left fronts (2,3)
        {"anchor": [1, 4]},   # left fronts (2,4), (2,5)
        {"anchor": [2, 6]},   # top front (3,6)
        {"anchor": [4, 6]},   # top fronts (4,6), (5,6)
        {"anchor": [6, 3]},   # right fronts (6,3), (6,4)
        {"anchor": [6, 5]},   # right front (6,5)
        {"anchor": [6, 7]},   # the original pole, still powering both machines
    ]


def _mutate_power_missing(geometry, rules):
    geometry["power_poles"] = [{"anchor": [17, 17]}]


def _mutate_unforced_pole(geometry, rules):
    geometry["power_poles"] = [{"anchor": [6, 7]}, {"anchor": [7, 7]}]


def _mutate_hole_on_a_body(geometry, rules):
    geometry["hole"] = {"anchor": [3, 3], "width": 7, "height": 6}


def _mutate_hole_too_thin(geometry, rules):
    geometry["hole"] = {"anchor": [10, 10], "width": 5, "height": 8}


def _mutate_hole_missing(geometry, rules):
    geometry["hole"] = None


def _mutate_reserved_front_blocked(geometry, rules):
    # (2,1) is the front cell of the first bottom boundary port.
    geometry["placements"][0]["anchor"] = [1, 1]
    geometry["placements"][0]["active_input_fronts"] = [[1, 4]]
    geometry["placements"][0]["active_output_fronts"] = [[1, 0]]


def _mutate_free_space_disconnected(geometry, rules):
    """Seal the hole into its own free-space island.

    The hole is pushed into the north-east corner so two of its four sides are
    board edges; the other two (column x=12 for y=14..19, row y=13 for
    x=13..19) are covered exactly by seven 2x2 poles.  Nothing can then reach
    the hole's 42 cells, so the anchors span two components.
    """
    geometry["hole"] = {"anchor": [13, 14], "width": 7, "height": 6}
    geometry["power_poles"] = [
        {"anchor": [6, 7]},                     # still powers both machines
        {"anchor": [11, 14]}, {"anchor": [11, 16]}, {"anchor": [11, 18]},
        {"anchor": [12, 12]}, {"anchor": [14, 12]},
        {"anchor": [16, 12]}, {"anchor": [18, 12]},
    ]


NEGATIVE_CASES = (
    ("authority_flag_violation", _mutate_authority),
    ("body_out_of_grid", _mutate_body_out_of_grid),
    ("body_overlap", _mutate_body_overlap),
    ("fixed_furniture_mismatch", _mutate_fixed_furniture),
    ("class_census_mismatch", _mutate_class_census),
    ("front_offset_violation", _mutate_front_offset),
    ("front_out_of_grid", _mutate_front_out_of_grid),
    ("front_blocked", _mutate_front_blocked),
    ("active_port_count_mismatch", _mutate_active_port_count),
    ("active_port_count_mismatch", _mutate_mode_not_offered),
    ("dead_body_present", _mutate_dead_body),
    ("power_coverage_missing", _mutate_power_missing),
    ("unforced_power_pole", _mutate_unforced_pole),
    ("hole_invalid", _mutate_hole_on_a_body),
    ("hole_invalid", _mutate_hole_too_thin),
    ("hole_invalid", _mutate_hole_missing),
    ("reserved_front_blocked", _mutate_reserved_front_blocked),
    ("free_space_disconnected", _mutate_free_space_disconnected),
)


@pytest.mark.parametrize(
    "expected_code,mutate",
    NEGATIVE_CASES,
    ids=[f"{code}-{fn.__name__[8:]}" for code, fn in NEGATIVE_CASES],
)
def test_negative_battery(expected_code: str, mutate) -> None:
    """[24] Every issue code is reachable by a concrete defect.

    A mutation may well trip more than one code -- moving a body both blocks a
    front and disturbs the census.  The assertion is therefore that the targeted
    code fires, plus that the verdict is FAIL.
    """
    rules, instances, geometry = _toy()
    mutate(geometry, rules)
    report = fva.audit(geometry, rules, instances)
    assert report["verdict"] == "FAIL"
    assert expected_code in report["issue_codes"], report["issue_codes"]


def test_every_registered_issue_code_is_exercised() -> None:
    """[24b] No decorative codes: the battery covers the full registry."""
    assert {code for code, _fn in NEGATIVE_CASES} == set(fva.ISSUE_CODES)


def test_pinned_w0_profile_rejects_a_moved_core() -> None:
    """[24c] The W0 profile id pins the framework spec, not just self-consistency."""
    rules, instances, geometry = fva._toy_inputs(with_core=True)
    geometry["layout_profile"]["profile_id"] = fva.W0_PROFILE_ID
    report = fva.audit(geometry, rules, instances)
    assert "fixed_furniture_mismatch" in report["issue_codes"]
    details = [
        item["detail"]
        for item in report["issues"]
        if item["code"] == "fixed_furniture_mismatch"
    ]
    assert any("pinned to a" in detail for detail in details)
    assert any("differs from the pinned" in detail for detail in details)


# --------------------------------------------------------------------------
# runtime contract
# --------------------------------------------------------------------------


def test_audit_source_never_imports_a_solver() -> None:
    """[25a] Statically: no ortools, no src, no sibling module import."""
    tree = ast.parse(AUDIT_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "ortools" not in imported
    assert "src" not in imported
    assert not {name for name in imported if name.startswith("g1_")}
    allowed = {
        "argparse", "fractions", "hashlib", "json", "os", "pathlib", "sys",
        "tempfile", "typing", "__future__",
    }
    assert imported <= allowed, sorted(imported - allowed)


def test_audit_runs_isolated_and_binds_its_inputs(tmp_path: Path) -> None:
    """[25, 26] Subprocess under ``-I -S -B``; the report binds input digests."""
    rules, instances, geometry = _toy()
    rules_path = tmp_path / "rules.json"
    instances_path = tmp_path / "instances.json"
    geometry_path = tmp_path / "geometry.json"
    output_path = tmp_path / "audit.json"
    rules_path.write_text(json.dumps(rules), encoding="utf-8")
    instances_path.write_text(json.dumps(instances), encoding="utf-8")
    geometry_path.write_text(json.dumps(geometry), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable, "-I", "-S", "-B", str(AUDIT_PATH),
            "--geometry", str(geometry_path),
            "--rules", str(rules_path),
            "--instances", str(instances_path),
            "--output", str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["verdict"] == "PASS"
    assert report["schema"] == fva.AUDIT_SCHEMA

    for key, path in (
        ("geometry", geometry_path),
        ("rules", rules_path),
        ("instances", instances_path),
    ):
        assert report["inputs"][key]["sha256"] == fva.sha256_file(path)

    # A failing geometry must come back as exit code 1 with a matching verdict.
    broken = copy.deepcopy(geometry)
    broken["placements"][0]["active_input_fronts"] = [[3, 7]]
    broken_path = tmp_path / "broken.json"
    broken_output = tmp_path / "broken_audit.json"
    broken_path.write_text(json.dumps(broken), encoding="utf-8")
    failing = subprocess.run(
        [
            sys.executable, "-I", "-S", "-B", str(AUDIT_PATH),
            "--geometry", str(broken_path),
            "--rules", str(rules_path),
            "--instances", str(instances_path),
            "--output", str(broken_output),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert failing.returncode == 1, failing.stderr
    assert json.loads(broken_output.read_text(encoding="utf-8"))["verdict"] == "FAIL"


def test_self_test_exits_zero() -> None:
    """[27] The built-in fixture self-check runs under full isolation."""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-B", str(AUDIT_PATH), "--self-test"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "self-test OK" in result.stdout


def test_unusable_input_is_a_distinct_exit_code(tmp_path: Path) -> None:
    """[27b] Cannot-audit is reported as 2, never silently as PASS or FAIL."""
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema": "something_else"}', encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable, "-I", "-S", "-B", str(AUDIT_PATH),
            "--geometry", str(bad), "--rules", str(bad),
            "--instances", str(bad), "--output", str(tmp_path / "out.json"),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 2
    assert not (tmp_path / "out.json").exists()


def test_class_table_derivation_agrees_with_the_line_module() -> None:
    """[26b] The audit's independent re-derivation reproduces the real table.

    The duplication is deliberate -- an independent checker that imported the
    thing it checks would be checking nothing -- so this test is what keeps the
    two derivations honest about each other.
    """
    import g1_port_semantics as sem

    rules = json.loads(sem.DEFAULT_RULES_PATH.read_text(encoding="utf-8"))
    instances = json.loads(sem.DEFAULT_INSTANCES_PATH.read_text(encoding="utf-8"))
    audit_table = fva.derive_class_table(rules, instances)
    line_table = {
        row.class_id: {
            "template": row.template,
            "r_in": row.r_in,
            "r_out": row.r_out,
            "count": row.count,
        }
        for row in sem.CLASS_TABLE
    }
    assert {
        name: {k: v for k, v in row.items() if k != "operations"}
        for name, row in audit_table.items()
    } == line_table
