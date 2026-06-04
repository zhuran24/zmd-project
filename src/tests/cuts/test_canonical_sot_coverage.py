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
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
FAMILIES_DIR = REPO / "src" / "cuts" / "families"
TESTS_DIR = REPO / "src" / "tests" / "cuts"
HELPER = REPO / "src" / "cuts" / "helpers" / "canonical_sot.py"

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
_DEF_TEST = re.compile(r"^\s*def (test_\w+)\s*\(", re.M)


def _cuts_test_defs() -> set:
    names: set = set()
    for f in TESTS_DIR.glob("test_*.py"):
        names |= set(_DEF_TEST.findall(f.read_text(encoding="utf-8")))
    return names


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


@pytest.mark.parametrize(
    "family_file", sorted(p.name for p in FAMILIES_DIR.glob("*.py") if p.name != "__init__.py")
)
def test_family_does_not_reimplement_canonical_radius_lookup(family_file: str) -> None:
    src = (FAMILIES_DIR / family_file).read_text(encoding="utf-8")
    assert not _PRIVATE_RADIUS_LOOKUP.search(src), (
        f"{family_file} accesses canonical power_coverage_radius directly — that is a private "
        "re-implementation of the shared SoT lookup. Use src/cuts/helpers/canonical_sot instead "
        "(the v28 fail-open holes were exactly such private/missing cross-checks)."
    )


@pytest.mark.parametrize(
    "family_file,test_name",
    [(fam, t) for fam, meta in sorted(CANONICAL_SOT_REGISTRY.items()) for t in meta["behavioral_tests"]],
)
def test_registered_behavioral_test_exists(family_file: str, test_name: str) -> None:
    """A renamed/deleted behavioral test must not pass silently — it is the only proof that a
    forged canonical scalar is actually rejected end-to-end."""
    assert test_name in _cuts_test_defs(), (
        f"{family_file} registry names behavioral test {test_name!r} but it no longer exists in "
        "src/tests/cuts — restore the test or update CANONICAL_SOT_REGISTRY."
    )
