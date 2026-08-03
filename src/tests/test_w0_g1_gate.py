"""W0 G1 stage B: the five-clause gate verdict.

research-only.  Nothing here produces or consumes a bound.

The real runs of this line have so far all stopped at the master, so the PASS
branch of the verdict would otherwise never execute.  These tests drive the
verdict function directly with a PASS-shaped bundle and then break it one clause
at a time, which is the only way to know that a green G1 would actually be
recognised -- and, more importantly, that a nearly-green one would not.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Dict

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
G1_DIR = PROJECT_ROOT / "docs" / "research" / "w0_front_aware_20260803"
for _path in (str(PROJECT_ROOT), str(G1_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import run_g1  # noqa: E402

pytestmark = pytest.mark.evidence

GEOMETRY_SHA = "a" * 64
CATALOG_DIGESTS = {"CLEAN": "c" * 64, "CORE": "d" * 64}


def _bundle() -> Dict[str, Any]:
    """Everything a passing G1 would hand the verdict function."""
    return {
        "master": {
            "status": "FEASIBLE",
            "catalogs": {
                "CLEAN": {"sha256": CATALOG_DIGESTS["CLEAN"]},
                "CORE": {"sha256": CATALOG_DIGESTS["CORE"]},
            },
        },
        "catalog_digests": dict(CATALOG_DIGESTS),
        "geometry": {
            "expansion": {
                "poles_before_minimisation": 41,
                "poles_after_minimisation": 38,
            }
        },
        "geometry_sha256": GEOMETRY_SHA,
        "audit": {
            "verdict": "PASS",
            "issues": [],
            "issue_codes": [],
            "summary": {"dead_for_any_actual_class": 0},
            "inputs": {"geometry": {"sha256": GEOMETRY_SHA}},
        },
        "observation": {
            "argv": ["python", "-I", "-S", "-B", "front_viability_audit.py"],
            "returncode": 0,
        },
    }


def _verdict(bundle: Dict[str, Any]) -> Dict[str, Any]:
    return run_g1._gate_verdict(
        bundle["master"],
        bundle["catalog_digests"],
        bundle["geometry"],
        bundle["geometry_sha256"],
        bundle["audit"],
        bundle["observation"],
    )


def test_a_clean_bundle_reaches_pass() -> None:
    """[G1] All four decidable clauses green, so the run is PASS pending the
    receipt -- which is settled by ``receipt.json`` existing, not by a claim."""
    clauses = _verdict(_bundle())
    for name in run_g1.GATE_CLAUSES[:4]:
        assert clauses[name]["ok"] is True, (name, clauses[name])
    assert clauses[run_g1.GATE_CLAUSES[4]]["ok"] is None
    assert run_g1._terminal_state(_bundle()["master"], clauses) == "PASS"


def test_a_catalog_digest_that_moved_since_the_solve_fails_clause_one() -> None:
    """[G2] The master's answer is only about the catalog it read."""
    bundle = _bundle()
    bundle["catalog_digests"]["CLEAN"] = "b" * 64
    clauses = _verdict(bundle)
    assert clauses[run_g1.GATE_CLAUSES[0]]["ok"] is False
    assert clauses[run_g1.GATE_CLAUSES[0]]["catalog_digests_match"] is False
    assert run_g1._terminal_state(bundle["master"], clauses) == "GATE_FAIL"


def test_missing_expansion_fails_clause_two() -> None:
    """[G3] No geometry, no clause two -- and no way to reach PASS."""
    bundle = _bundle()
    bundle["geometry"] = None
    clauses = _verdict(bundle)
    assert clauses[run_g1.GATE_CLAUSES[1]]["ok"] is False
    assert run_g1._terminal_state(bundle["master"], clauses) == "GATE_FAIL"


def test_any_audit_issue_fails_clause_three_and_names_the_state() -> None:
    """[G4] One issue is enough, and the terminal state says AUDIT_FAIL rather
    than the generic gate failure."""
    bundle = _bundle()
    bundle["audit"]["verdict"] = "FAIL"
    bundle["audit"]["issues"] = [{"code": "dead_body_present", "detail": "x"}]
    bundle["audit"]["issue_codes"] = ["dead_body_present"]
    bundle["audit"]["summary"]["dead_for_any_actual_class"] = 1
    clauses = _verdict(bundle)
    assert clauses[run_g1.GATE_CLAUSES[2]]["ok"] is False
    assert run_g1._terminal_state(bundle["master"], clauses) == "AUDIT_FAIL"


def test_an_audit_of_some_other_geometry_fails_clause_four() -> None:
    """[G5, RED LINE] The audit must be bound to the bytes this run produced.

    A clean report about a different file is the most dangerous shape of failure
    available here, so it is checked directly.
    """
    bundle = _bundle()
    bundle["audit"]["inputs"]["geometry"]["sha256"] = "e" * 64
    clauses = _verdict(bundle)
    assert clauses[run_g1.GATE_CLAUSES[3]]["ok"] is False
    assert run_g1._terminal_state(bundle["master"], clauses) == "GATE_FAIL"


def test_an_audit_that_was_not_isolated_fails_clause_four() -> None:
    """[G6] The independent auditor has to have been independent."""
    bundle = _bundle()
    bundle["observation"]["argv"] = ["python", "front_viability_audit.py"]
    clauses = _verdict(bundle)
    assert clauses[run_g1.GATE_CLAUSES[3]]["ok"] is False
    assert run_g1._terminal_state(bundle["master"], clauses) == "GATE_FAIL"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("INFEASIBLE", "INFEASIBLE"),
        ("UNKNOWN", "UNKNOWN"),
        ("SCALE_ABORT", "SCALE_ABORT"),
        ("MODEL_INVALID", "UNKNOWN"),
    ],
)
def test_non_terminal_masters_name_their_own_stopping_state(
    status: str, expected: str
) -> None:
    """[G7] Every stopping shape in charter section 9 has its own name, so the
    report cannot round them all off to "not passed"."""
    bundle = _bundle()
    bundle["master"]["status"] = status
    bundle["geometry"] = None
    bundle["audit"] = {}
    bundle["observation"] = {}
    bundle["geometry_sha256"] = None
    clauses = _verdict(bundle)
    assert run_g1._terminal_state(bundle["master"], clauses) == expected
