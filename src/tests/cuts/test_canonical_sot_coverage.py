# -*- coding: utf-8 -*-
"""Meta-test (forcing function) for shared canonical source-of-truth (SoT) checks.

The v28 GPT pro review found cut-family validators trusting canonical-derivable
scalars (pole radius, footprint dims) without cross-checking canonical_rules
(fail-open). The fix is centralized in ``src/cuts/helpers/canonical_sot.py``.
This meta-test makes that consolidation a contract:

  - every registered family that guards a canonical scalar actually CALLS the
    shared helper (not just imports the name);
  - the canonical pole-radius lookup is NOT re-implemented privately in a
    family (no divergent copy can creep back via a quote/style change); and
  - the per-family behavioral tests named in the registry (which prove a forged
    scalar is rejected) still exist — so deleting one cannot pass silently.

Honest limits (do NOT over-read the coverage):
  - It catches REGRESSION, not a NEW canonical scalar a future family trusts
    without a guard — that still needs human/code review (as v28 itself did).
  - The private-lookup scan is scoped to ``power_coverage_radius``; a
    variable-indirect access (``k = "power_coverage_radius"; t.get(k)``) still
    slips through. The per-family behavioral red-tests are the soundness net;
    this scan is the dedup regression guard.
  - ``get("dimensions")`` is deliberately NOT scanned: F6 (shape_packing_hall)
    ALSO does a genuine fail-closed canonical-dimensions SoT cross-check
    (pose_length vs facility-template dims) but via the ``state.facility_templates``
    alias and a family-specific 1xL / max==pose_length shape, NOT routed through
    canonical_sot. That F6 copy is sound (fail-closed) yet is a known
    un-consolidated dims lookup — see PROJECT_LOCK §3.
"""
import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
FAMILIES_DIR = REPO / "src" / "cuts" / "families"
ASSUMPTIONS_DIR = REPO / "src" / "cuts" / "assumptions"
TESTS_DIR = REPO / "src" / "tests" / "cuts"
HELPER = REPO / "src" / "cuts" / "helpers" / "canonical_sot.py"

# Validator-side dirs whose code must NOT privately re-implement the canonical pole-radius
# lookup. The v28 fresh-pass found a 4th verbatim copy in assumptions/verifiers.py (the certified
# attach-scope path), invisible to a families-only scan. Generators (oracles/) are out of scope
# (they produce cert values that validators then check); canonical_sot.py is the sanctioned home.
_VALIDATOR_SIDE_PY = sorted(
    p for d in (FAMILIES_DIR, ASSUMPTIONS_DIR) for p in d.glob("*.py") if p.name != "__init__.py"
)

# family file -> canonical fields it SoT-guards + the per-family behavioral tests
# that prove a forged value is rejected (the contract this meta-test enforces).
CANONICAL_SOT_REGISTRY = {
    "power_hitting_set.py": {
        "guards": ["power_pole.power_coverage_radius", "power_pole.dimensions"],
        "behavioral_tests": [
            "test_validator_rejects_forged_positive_pole_radius",
            "test_validator_rejects_power_pole_dimension_drift",
        ],
    },
    "power_grid_reach.py": {
        "guards": [
            "power_pole.power_coverage_radius",
            "power_pole.dimensions",
            "protocol_core.dimensions",
        ],
        "behavioral_tests": [
            "test_validator_rejects_power_pole_dimension_drift",
            "test_validator_rejects_protocol_core_dimension_drift",
        ],
    },
}

# Matches get('...')/get("...") and ['...']/["..."] subscript access of the canonical
# pole radius — so a quote/style change cannot bypass the dedup guard.
_PRIVATE_RADIUS_LOOKUP = re.compile(r"""(?:get\(\s*|\[\s*)['"]power_coverage_radius['"]""")
def _find_func(path: Path, name: str):
    """Return the ast.FunctionDef for `name` in `path`, or None."""
    if not path.exists():
        return None
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def test_shared_helper_present() -> None:
    assert HELPER.exists(), "src/cuts/helpers/canonical_sot.py (shared SoT helper) is missing"


@pytest.mark.parametrize("family_file", sorted(CANONICAL_SOT_REGISTRY))
def test_registered_family_calls_shared_canonical_sot(family_file: str) -> None:
    src = (FAMILIES_DIR / family_file).read_text(encoding="utf-8")
    guards = CANONICAL_SOT_REGISTRY[family_file]["guards"]
    # require an actual attribute call (canonical_sot.<fn>), not just the bare name in
    # a comment / dangling import.
    assert "canonical_sot." in src, (
        f"{family_file} guards canonical scalars {guards} but does not call the shared "
        "src/cuts/helpers/canonical_sot — re-wire it (dedup + SoT contract)."
    )


@pytest.mark.parametrize("py_path", _VALIDATOR_SIDE_PY, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_validator_side_does_not_reimplement_canonical_radius_lookup(py_path: Path) -> None:
    src = py_path.read_text(encoding="utf-8")
    assert not _PRIVATE_RADIUS_LOOKUP.search(src), (
        f"{py_path.parent.name}/{py_path.name} accesses canonical power_coverage_radius directly — "
        "that is a private re-implementation of the shared SoT lookup. Use "
        "src/cuts/helpers/canonical_sot instead (the v28 fail-open holes were exactly such "
        "private/missing cross-checks; a 4th verbatim copy was found in assumptions/verifiers.py)."
    )


@pytest.mark.parametrize(
    "family_file,test_name",
    [(fam, t) for fam, meta in sorted(CANONICAL_SOT_REGISTRY.items()) for t in meta["behavioral_tests"]],
)
def test_registered_behavioral_test_exists(family_file: str, test_name: str) -> None:
    """A renamed/deleted/gutted behavioral test must not pass silently — it is the only proof that
    a forged canonical scalar is actually rejected end-to-end. Checked PER-FAMILY (in that family's
    own test_family_*.py), so deleting one family's copy of a name it shares with another family is
    still caught (a global name-set would miss that). Also requires the body to still carry an
    assert (AST), so gutting it to `return`/`pass` while keeping the name — the exact
    'gutted-but-named' degeneration the fresh-pass flagged — is caught here instead of passing green.
    (Residual: a deliberate `assert True` still slips; that is adversarial-deliberate, beyond a
    regression guard.)"""
    fam_test_file = TESTS_DIR / f"test_family_{family_file}"
    fn = _find_func(fam_test_file, test_name)
    assert fn is not None, (
        f"{family_file}: registry names behavioral test {test_name!r} but it is not defined in "
        f"{fam_test_file.name} — restore the test or update CANONICAL_SOT_REGISTRY."
    )
    assert any(isinstance(n, ast.Assert) for n in ast.walk(fn)), (
        f"{family_file}: behavioral test {test_name!r} in {fam_test_file.name} has no assert in its "
        "body (gutted?) — it no longer proves a forged scalar is rejected."
    )
