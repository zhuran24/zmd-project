"""W0 G1 stage B: the five-clause gate verdict.

research-only.  Nothing here produces or consumes a bound.

The real runs of this line have so far all stopped at the master, so the PASS
branch of the verdict would otherwise never execute.  These tests drive the
verdict function directly with a PASS-shaped bundle and then break it one clause
at a time, which is the only way to know that a green G1 would actually be
recognised -- and, more importantly, that a nearly-green one would not.

Clause five is different in kind: it is about the run root rather than about the
answer, so it is also tested end to end, by running the real ``gate`` command and
dropping an unmanifested file into its root while it works.  That is the failure
codex reproduced on 2026-08-03, and the property under test is that it leaves
neither a PASS nor a receipt behind.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict, List

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
G1_DIR = PROJECT_ROOT / "docs" / "research" / "w0_front_aware_20260803"
for _path in (str(PROJECT_ROOT), str(G1_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from devtools.research_run_contract import ResearchRunContractError  # noqa: E402
from g1_pattern_schema import (  # noqa: E402
    CATALOG_SCHEMA,
    RESEARCH_AUTHORITY,
    dump_canonical,
    mask_sha256,
)
from g1_region_model import REGION_CLASS_ORDER, REGION_CLASSES  # noqa: E402
import run_g1  # noqa: E402

pytestmark = pytest.mark.evidence

GEOMETRY_SHA = "a" * 64
CATALOG_DIGESTS = {"CLEAN": "c" * 64, "CORE": "d" * 64}

#: The name of the file the fault-injection tests smuggle into a live run root.
STRAY_FILE = "unmanifested-extra.txt"


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
        "pre_gate": {"catalog_class_supply": {"verdict": "NOT_EXCLUDED"}},
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
            "environment": {
                "ortools_importable": False,
                "line_modules_loaded": [],
                "src_modules_loaded": [],
                "flags": {
                    "isolated": True,
                    "no_site": True,
                    "ignore_environment": True,
                    "dont_write_bytecode": True,
                },
            },
        },
        "observation": {
            "argv": ["python", "-I", "-S", "-B", "front_viability_audit.py"],
            "returncode": 0,
        },
        "root_closure_error": None,
    }


def _verdict(bundle: Dict[str, Any]) -> Dict[str, Any]:
    return run_g1._gate_verdict(
        bundle["master"],
        bundle["catalog_digests"],
        bundle["pre_gate"],
        bundle["geometry"],
        bundle["geometry_sha256"],
        bundle["audit"],
        bundle["observation"],
        root_closure_error=bundle["root_closure_error"],
    )


def test_a_clean_bundle_reaches_pass() -> None:
    """[G1] All five clauses green, so the run is PASS."""
    clauses = _verdict(_bundle())
    for name in run_g1.GATE_CLAUSES:
        assert clauses[name]["ok"] is True, (name, clauses[name])
    assert run_g1._terminal_state(_bundle()["master"], clauses) == "PASS"


def test_a_catalog_digest_that_moved_since_the_solve_fails_clause_one() -> None:
    """[G2] The master's answer is only about the catalog it read."""
    bundle = _bundle()
    bundle["catalog_digests"]["CLEAN"] = "b" * 64
    clauses = _verdict(bundle)
    assert clauses[run_g1.GATE_CLAUSES[0]]["ok"] is False
    assert clauses[run_g1.GATE_CLAUSES[0]]["catalog_digests_match"] is False
    assert run_g1._terminal_state(bundle["master"], clauses) == "GATE_FAIL"


def test_a_short_pre_gate_under_a_solved_master_is_a_named_contradiction() -> None:
    """[G2b] The solver-free pre-gate is a certificate, not a side note.

    ``SHORT`` proves no selection covers the census.  A master that nevertheless
    returns a solution means one of the two is wrong, and the gate has to say so
    instead of filing both in the run root as if they were both evidence.
    """
    bundle = _bundle()
    bundle["pre_gate"]["catalog_class_supply"]["verdict"] = "SHORT"
    clauses = _verdict(bundle)
    clause = clauses[run_g1.GATE_CLAUSES[0]]
    assert clause["pre_gate_contradicts_master"] is True
    assert clause["pre_gate_verdict"] == "SHORT"
    assert clause["ok"] is False
    assert run_g1._terminal_state(bundle["master"], clauses) == "GATE_FAIL"

    # ... and a SHORT pre-gate next to an INFEASIBLE master is the ordinary case:
    # the two agree, and nothing is flagged.
    bundle["master"]["status"] = "INFEASIBLE"
    agreeing = _verdict(bundle)
    assert agreeing[run_g1.GATE_CLAUSES[0]]["pre_gate_contradicts_master"] is False
    assert run_g1._terminal_state(bundle["master"], agreeing) == "INFEASIBLE"


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


@pytest.mark.parametrize(
    "mutation",
    [
        {"ortools_importable": True},
        {"line_modules_loaded": ["g1_pattern_evaluator"]},
        {"src_modules_loaded": ["src.placement.placement_generator"]},
        {"flags": {"isolated": False, "no_site": True, "dont_write_bytecode": True}},
        {"flags": {"isolated": True, "no_site": False, "dont_write_bytecode": True}},
        {"flags": {"isolated": True, "no_site": True, "dont_write_bytecode": False}},
    ],
)
def test_clause_four_believes_the_child_not_the_argv(mutation: Dict[str, Any]) -> None:
    """[G6] Independence is decided by what the auditor reported about itself.

    The parent builds the child's argv nine lines before checking it, so an argv
    check passes by construction and can only fail if someone edits the launcher.
    What the clause is *about* -- the child could not reach a solver and had
    loaded nothing from this line -- is stated by the child, and every way of
    breaking that has to break the clause.
    """
    bundle = _bundle()
    bundle["audit"]["environment"].update(mutation)
    clauses = _verdict(bundle)
    assert clauses[run_g1.GATE_CLAUSES[3]]["child_reported_isolation"] is False
    assert clauses[run_g1.GATE_CLAUSES[3]]["ok"] is False
    assert run_g1._terminal_state(bundle["master"], clauses) == "GATE_FAIL"


def test_a_report_without_an_environment_block_fails_clause_four() -> None:
    """[G6b] An audit that says nothing about its own isolation proves nothing."""
    bundle = _bundle()
    del bundle["audit"]["environment"]
    clauses = _verdict(bundle)
    assert clauses[run_g1.GATE_CLAUSES[3]]["ok"] is False
    assert run_g1._terminal_state(bundle["master"], clauses) == "GATE_FAIL"


def test_a_root_that_does_not_close_fails_clause_five() -> None:
    """[G7] Clause five records the closure result instead of deferring it.

    It used to be written as ``ok: null`` with a note that the reader should look
    for the receipt -- which made it fail-open, because the receipt was written
    before the closure check ran.
    """
    bundle = _bundle()
    bundle["root_closure_error"] = (
        "ARTIFACT_ROOT_CLOSURE_MISMATCH: missing=[]; extra=['unmanifested-extra.txt']"
    )
    clauses = _verdict(bundle)
    clause = clauses[run_g1.GATE_CLAUSES[4]]
    assert clause["ok"] is False
    assert "unmanifested-extra.txt" in clause["error"]
    assert clause["checked_before_receipt"] is True
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
    """[G8] Every stopping shape in charter section 9 has its own name, so the
    report cannot round them all off to "not passed"."""
    bundle = _bundle()
    bundle["master"]["status"] = status
    bundle["geometry"] = None
    bundle["audit"] = {}
    bundle["observation"] = {}
    bundle["geometry_sha256"] = None
    clauses = _verdict(bundle)
    assert run_g1._terminal_state(bundle["master"], clauses) == expected


# --------------------------------------------------------------------------
# end to end: the real gate command, with an intruder in its run root
# --------------------------------------------------------------------------


def _empty_catalog(directory: Path) -> Path:
    """A catalog every region class can be covered from, holding no body.

    The master over it is INFEASIBLE (a 219-body census cannot be met by empty
    patterns), which is all these tests need: they are about what the run root
    looks like afterwards, not about the answer.
    """
    catalog = directory / "catalog"
    catalog.mkdir(parents=True, exist_ok=True)
    for name in REGION_CLASS_ORDER:
        region = REGION_CLASSES[name]
        dump_canonical(
            catalog / f"{name}.json",
            {
                "schema": CATALOG_SCHEMA,
                "authority": dict(RESEARCH_AUTHORITY),
                "region_class": name,
                "region_multiplicity": region.multiplicity,
                "fixed_mask_sha256": mask_sha256(region.fixed_local),
                "reserved_mask_sha256": mask_sha256(region.reserved_local),
                "complete": True,
                "patterns": [],
            },
        )
    return catalog


def _gate_argv(catalog: Path, run_root: Path) -> List[str]:
    return [
        "gate",
        "--catalog",
        str(catalog),
        "--run-root",
        str(run_root),
        "--max-seconds",
        "60",
        "--workers",
        "2",
    ]


def test_a_file_appearing_mid_run_fails_clause_five_and_leaves_no_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[G9, RED LINE] Real pipeline, unmanifested file, no receipt, no PASS.

    The root manifest is built from what the run wrote, so a file that nobody
    wrote is visible as an intruder.  Clause five sees it, and the run refuses to
    close.
    """
    catalog = _empty_catalog(tmp_path)
    run_root = tmp_path / "run"
    original_write = run_g1._Run.write

    def write_then_intrude(
        self: Any, relative: str, label: str, value: Any
    ) -> str:
        digest = original_write(self, relative, label, value)
        if relative == "master/master_result.json":
            (self.root.path / STRAY_FILE).write_text("intruder\n", encoding="utf-8")
        return digest

    monkeypatch.setattr(run_g1._Run, "write", write_then_intrude)

    with pytest.raises(ResearchRunContractError) as excinfo:
        run_g1.main(_gate_argv(catalog, run_root))
    assert "ARTIFACT_ROOT_CLOSURE_MISMATCH" in str(excinfo.value)
    assert STRAY_FILE in str(excinfo.value)

    assert not (run_root / "receipt.json").exists(), "a failed closure kept a receipt"
    gate_doc = json.loads((run_root / "gate.json").read_text(encoding="utf-8"))
    assert gate_doc["verdict"] == "NOT_PASSED"
    assert gate_doc["terminal_state"] != "PASS"
    clause = gate_doc["clauses"][run_g1.GATE_CLAUSES[4]]
    assert clause["ok"] is False
    assert STRAY_FILE in clause["error"]


def test_a_file_appearing_while_the_receipt_is_written_removes_that_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[G10, RED LINE] The exact 2026-08-03 fault injection.

    The intruder arrives after the pre-receipt check and before the receipt is
    written, which is the one window in which a receipt can be produced for a root
    that does not close.  Before this batch the receipt survived that window and
    "a receipt exists" was read as "clause five holds"; now the receipt is removed
    again and the failure is fatal.
    """
    catalog = _empty_catalog(tmp_path)
    run_root = tmp_path / "run"
    original_receipt = run_g1.make_research_run_receipt

    def receipt_then_intrude(**kwargs: Any) -> Dict[str, Any]:
        (run_root / STRAY_FILE).write_text("intruder\n", encoding="utf-8")
        return original_receipt(**kwargs)

    monkeypatch.setattr(run_g1, "make_research_run_receipt", receipt_then_intrude)

    with pytest.raises(ResearchRunContractError) as excinfo:
        run_g1.main(_gate_argv(catalog, run_root))
    assert "ARTIFACT_ROOT_CLOSURE_MISMATCH" in str(excinfo.value)

    assert not (run_root / "receipt.json").exists(), "the invalid receipt survived"
    assert (run_root / STRAY_FILE).exists(), "the run must not delete foreign files"
    gate_doc = json.loads((run_root / "gate.json").read_text(encoding="utf-8"))
    assert gate_doc["verdict"] == "NOT_PASSED"
    assert gate_doc["terminal_state"] == "ROOT_CLOSURE_FAILED"
    assert gate_doc["invalidated_by"] == "post_gate_root_closure_failure"
    assert gate_doc["verdict_is_conditional_on_receipt"] is False


def test_an_undisturbed_gate_run_closes_its_root(tmp_path: Path) -> None:
    """[G11] The control case: same command, no intruder, receipt present.

    Without this the two fault-injection tests could pass on a gate command that
    is simply broken, and the generic-IO contract would have no live check either.
    """
    catalog = _empty_catalog(tmp_path)
    run_root = tmp_path / "run"
    assert run_g1.main(_gate_argv(catalog, run_root)) == 1  # INFEASIBLE, not PASS

    receipt = json.loads((run_root / "receipt.json").read_text(encoding="utf-8"))
    gate_doc = json.loads((run_root / "gate.json").read_text(encoding="utf-8"))
    assert gate_doc["terminal_state"] == "INFEASIBLE"
    assert gate_doc["clauses"][run_g1.GATE_CLAUSES[4]]["ok"] is True
    assert gate_doc["registers_lower_bound"] is False

    config = json.loads((run_root / "config.json").read_text(encoding="utf-8"))
    frozen = run_g1._generic_io_contract(run_g1.DEFAULT_GENERIC_IO_PATH)
    assert config["payload"]["generic_io_sha256"] == frozen["sha256"]
    assert receipt["payload"]["run"]["generic_io_sha256"] == frozen["sha256"]

    pre_gate = json.loads(
        (run_root / "master" / "pre_gate.json").read_text(encoding="utf-8")
    )
    assert pre_gate["generic_io_contract"]["covered"] is True
    assert pre_gate["generic_io_contract"]["required_generic_output_slots"] == 52
    assert pre_gate["generic_io_contract"]["fixed_furniture_output_ports"] == 52
    assert pre_gate["generic_io_contract"]["fixed_furniture_input_ports"] == 14
