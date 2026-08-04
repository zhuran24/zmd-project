"""W0 G1 stage B: the six-clause gate verdict.

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

import hashlib
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
        "obligations": {
            "registry_sha256": "f" * 64,
            "obligations": [
                {"id": "O-FRONT-SIMULTANEITY", "discharged": True, "detail": {}}
            ],
            "all_discharged": True,
        },
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
        obligations=bundle["obligations"],
    )


def test_a_clean_bundle_reaches_pass() -> None:
    """[G1] All six clauses green, so the run is PASS."""
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
# clause six: no PASS before the registry's obligations are discharged
# --------------------------------------------------------------------------


def test_pass_is_impossible_while_an_open_obligation_stands() -> None:
    """[G12, RED LINE] The charter's "must close before any G1 PASS", executable.

    Everything else about the run is perfect; only the obligation is open.  The
    verdict has to be ``OBLIGATION_OPEN`` -- a BLOCK/repair terminal -- and never
    ``PASS``.  Asserted twice on purpose, because clause six is enforced twice:
    once as a precondition inside ``_terminal_state`` and once as a member of the
    conjunction, and a single lock is one careless edit from no lock.
    """
    bundle = _bundle()
    bundle["obligations"] = {
        "registry_sha256": "f" * 64,
        "obligations": [
            {"id": "O-FRONT-SIMULTANEITY", "discharged": False, "detail": {}}
        ],
        "all_discharged": False,
    }
    clauses = _verdict(bundle)
    clause = clauses[run_g1.GATE_CLAUSES[5]]
    assert clause["ok"] is False
    assert clause["open_obligation_ids"] == ["O-FRONT-SIMULTANEITY"]
    assert run_g1._terminal_state(bundle["master"], clauses) == run_g1.OBLIGATION_OPEN

    # Lock 2: the conjunction cannot see six greens either.
    for name in run_g1.GATE_CLAUSES[:5]:
        assert clauses[name]["ok"] is True
    assert not all(entry["ok"] for entry in clauses.values())

    # And exhaustively: over every combination of the other five clauses, an open
    # obligation never produces PASS.  There is no arrangement of the rest of the
    # run that buys its way past clause six.
    master = {"status": "FEASIBLE"}
    for bits in range(1 << 5):
        trial = {
            name: {"ok": bool(bits & (1 << index))}
            for index, name in enumerate(run_g1.GATE_CLAUSES[:5])
        }
        trial[run_g1.GATE_CLAUSES[5]] = {"ok": False}
        assert run_g1._terminal_state(master, trial) != "PASS", bits


def test_every_open_obligation_needs_an_implemented_check(tmp_path: Path) -> None:
    """[G13] A newly registered obligation blocks PASS by itself.

    The gate reads the obligation list from the registry rather than keeping its
    own copy, and an id with no entry in ``OBLIGATION_CHECKS`` is reported as not
    discharged.  So the failure direction of "someone added an obligation and
    forgot the check" is closed, not open.
    """
    registry = json.loads(run_g1.REGISTRY_PATH.read_text(encoding="utf-8"))
    registry["open_obligations"].append(
        {
            "id": "O-INVENTED-FOR-THIS-TEST",
            "statement": "a registered obligation nobody implemented a check for",
            "affects": ["R-PAT-CONN"],
            "effect_on_this_batch": "none",
            "must_close_before": "any G1 PASS",
            "closure_options": ["implement it", "prove it"],
        }
    )
    path = tmp_path / "derived_theorems.json"
    path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    report = run_g1.discharge_open_obligations(None, registry_path=path)
    assert report["all_discharged"] is False
    invented = next(
        item for item in report["obligations"] if item["id"] == "O-INVENTED-FOR-THIS-TEST"
    )
    assert invented["checker"] is None
    assert "no discharge check is implemented" in invented["detail"]["reason"]


def test_the_shipped_registry_obligation_is_wired_to_a_check() -> None:
    """[G13b] The other direction: the ids in the registry are the ids we check."""
    registry = json.loads(run_g1.REGISTRY_PATH.read_text(encoding="utf-8"))
    registered = {entry["id"] for entry in registry["open_obligations"]}
    assert registered, "the obligation list must not silently empty out"
    assert registered <= set(run_g1.OBLIGATION_CHECKS), registered
    report = run_g1.discharge_open_obligations(None)
    assert report["all_discharged"] is False, "no geometry, nothing discharged"
    assert report["registry_sha256"]


class _CountingRegistry:
    """A registry path that hands out *different* bytes on every read.

    Stands in for the file changing between two reads.  The gate is allowed
    exactly one read, so only ``payloads[0]`` may ever be seen; a second read is
    the TOCTOU window itself and shows up here as a different obligation list
    behind an already-published digest.
    """

    def __init__(self, *payloads: bytes) -> None:
        self.payloads = list(payloads)
        self.reads = 0

    def _next(self) -> bytes:
        payload = self.payloads[min(self.reads, len(self.payloads) - 1)]
        self.reads += 1
        return payload

    def read_bytes(self) -> bytes:
        return self._next()

    def read_text(self, encoding: str = "utf-8") -> str:
        return self._next().decode(encoding)

    def __str__(self) -> str:  # the report records the path it answered to
        return "<counting registry>"


def test_the_registry_is_read_once_so_the_digest_matches_what_was_parsed() -> None:
    """[G13d] Clause six hashes and parses **one** byte string, not two reads.

    Hashing the file and then parsing the file again is a window: between the two
    reads the registry can change, and the report would then publish a digest of
    bytes it did not decide against -- exactly the evidence-provenance failure
    this line is built to refuse.  The stub below makes the window visible: its
    second read carries an obligation the first does not.
    """
    shipped = run_g1.REGISTRY_PATH.read_bytes()
    swapped = json.loads(shipped.decode("utf-8"))
    swapped["open_obligations"] = [
        {
            "id": "O-SNUCK-IN-BETWEEN-THE-READS",
            "statement": "an obligation that only the second read would see",
            "affects": ["R-PAT-CONN"],
            "effect_on_this_batch": "none",
            "must_close_before": "any G1 PASS",
            "closure_options": ["never appear"],
        }
    ]
    stub = _CountingRegistry(shipped, (json.dumps(swapped) + "\n").encode("utf-8"))

    report = run_g1.discharge_open_obligations(None, registry_path=stub)  # type: ignore[arg-type]

    assert stub.reads == 1, "the registry may be read exactly once"
    assert report["registry_sha256"] == hashlib.sha256(shipped).hexdigest()
    ids = {item["id"] for item in report["obligations"]}
    assert "O-SNUCK-IN-BETWEEN-THE-READS" not in ids
    assert ids == {
        entry["id"] for entry in json.loads(shipped.decode("utf-8"))["open_obligations"]
    }


def test_an_unreadable_obligation_list_is_fatal_not_a_green_clause(
    tmp_path: Path,
) -> None:
    """[G13c] Two ways to lose the list, two fail-closed answers.

    Deleting the key is structural damage and raises; emptying the list is
    reported as "open", because the line's contract test says the list may not
    silently empty out, so an empty one is a lost list rather than a finished
    proof.  Neither one may read as "nothing to discharge, clause six green".
    """
    registry = json.loads(run_g1.REGISTRY_PATH.read_text(encoding="utf-8"))

    del registry["open_obligations"]
    gone = tmp_path / "no_key.json"
    gone.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(run_g1.ObligationOpen, match="open_obligations"):
        run_g1.discharge_open_obligations(None, registry_path=gone)

    registry["open_obligations"] = []
    emptied = tmp_path / "empty_list.json"
    emptied.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    report = run_g1.discharge_open_obligations(None, registry_path=emptied)
    assert report["all_discharged"] is False
    assert report["obligations"] == []


# --- the discharge check itself ------------------------------------------


def _geometry(placements: List[Dict[str, Any]], walls: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "fixed_furniture": walls,
        "placements": placements,
        "power_poles": [],
        "hole": None,
    }


def _placement(anchor: List[int], mode: str, class_id: str, fronts) -> Dict[str, Any]:
    active_in, active_out = fronts
    return {
        "template": "manufacturing_3x3",
        "orientation": 0,
        "anchor": anchor,
        "size": [3, 3],
        "mode": mode,
        "operation_class": class_id,
        "active_input_fronts": active_in,
        "active_output_fronts": active_out,
    }


def test_front_simultaneity_is_discharged_by_an_explicit_witness() -> None:
    """[G14] Two bodies sharing a front row still have distinct representatives.

    The obligation is not "no body may share a candidate cell" -- it is "all
    bodies can take *pairwise distinct* cells at once".  Here both bodies want
    the row y = 13; there are three cells in it and one slot each, so a witness
    exists and the check says so.
    """
    geometry = _geometry(
        [
            _placement([10, 10], "TB", "3L", ([[10, 13]], [[10, 9]])),
            _placement([10, 14], "BT", "3L", ([[10, 13]], [[10, 17]])),
        ],
        [],
    )
    report = run_g1.check_front_simultaneity(geometry)
    assert report["discharged"] is True, report
    assert report["front_slots_demanded"] == 4
    assert report["front_slots_matched"] == 4
    assert report["candidate_cells_wanted_by_several_bodies"] == 3
    chosen = [tuple(cell) for cell in report["witness"].values()]
    assert len(chosen) == len(set(chosen)), "a witness with a repeat is not a witness"


def test_front_simultaneity_blocks_when_the_shared_row_is_oversubscribed() -> None:
    """[G14b] Four input slots, three shared cells: no witness, so PASS is blocked.

    Both bodies face the row ``y = 13`` and both are class ``3I2``, which wants
    two inputs each.  Three cells cannot carry four distinct representatives, so
    the check reports "not discharged" -- and says in as many words that this is
    the absence of a witness, not a proof that the sharing is illegal.  This is
    the shape of the obligation itself: per-body capability is satisfied (each
    body sees three free fronts), and only the simultaneity fails.
    """
    geometry = _geometry(
        [
            _placement([10, 10], "TB", "3I2", ([[10, 13], [11, 13]], [[10, 9]])),
            _placement([10, 14], "BT", "3I2", ([[10, 13], [11, 13]], [[10, 17]])),
        ],
        [],
    )
    report = run_g1.check_front_simultaneity(geometry)
    assert report["discharged"] is False, report
    assert report["front_slots_demanded"] == 6
    assert report["front_slots_matched"] == 5
    assert len(report["unmatched_slots"]) == 1
    assert report["recorded_active_fronts_off_corridor"] == []
    assert "not a proof that the sharing is illegal" in report["reading"]


def test_front_simultaneity_needs_a_geometry_at_all() -> None:
    """[G14c] No geometry, no witness -- and therefore no discharge."""
    report = run_g1.check_front_simultaneity(None)
    assert report["discharged"] is False
    assert "no geometry" in report["reason"]


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
