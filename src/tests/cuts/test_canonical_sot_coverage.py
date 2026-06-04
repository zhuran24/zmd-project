# -*- coding: utf-8 -*-
"""Meta-test (forcing function) for shared canonical source-of-truth (SoT) checks.

The v28 GPT pro review found cut-family validators trusting canonical-derivable
scalars (pole radius, footprint dims) without cross-checking canonical_rules
(fail-open). The fix is centralized in ``src/cuts/helpers/canonical_sot.py``.
This meta-test makes that consolidation a contract:

  - every family that guards a canonical scalar uses the shared helper, and
  - the canonical lookup logic is NOT re-implemented privately in a family
    (no divergent copy can creep back).

Honest limit: this catches REGRESSION (a refactor dropping the shared call, or
re-introducing a private lookup). It CANNOT auto-discover a NEW canonical scalar
that a FUTURE family trusts without a guard — that still needs human/code review
(as the v28 round itself did). Behavioral proof that each guard actually rejects
a forged scalar lives in the per-family tests named in the registry below.
"""
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
FAMILIES_DIR = REPO / "src" / "cuts" / "families"
HELPER = REPO / "src" / "cuts" / "helpers" / "canonical_sot.py"

# family file -> canonical fields it SoT-guards + the per-family behavioral tests
# that prove a forged value is rejected (the contract this meta-test documents).
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

# Raw canonical access pattern that must live ONLY in canonical_sot.py, never
# re-implemented inside a family (a private copy is how the v28 fail-open crept in).
# Scoped to power_coverage_radius: it is unambiguously a canonical SoT field, whereas
# get("dimensions") is also used legitimately for non-SoT geometry (e.g. F6 pose_length).
_PRIVATE_LOOKUP_PATTERNS = ('get("power_coverage_radius")',)


def test_shared_helper_present() -> None:
    assert HELPER.exists(), "src/cuts/helpers/canonical_sot.py (shared SoT helper) is missing"


@pytest.mark.parametrize("family_file", sorted(CANONICAL_SOT_REGISTRY))
def test_registered_family_uses_shared_canonical_sot(family_file: str) -> None:
    src = (FAMILIES_DIR / family_file).read_text(encoding="utf-8")
    guards = CANONICAL_SOT_REGISTRY[family_file]["guards"]
    assert "canonical_sot" in src, (
        f"{family_file} guards canonical scalars {guards} but does not use the shared "
        "src/cuts/helpers/canonical_sot — re-wire it (dedup + SoT contract)."
    )


@pytest.mark.parametrize("family_file", sorted(p.name for p in FAMILIES_DIR.glob("*.py") if p.name != "__init__.py"))
def test_family_does_not_reimplement_canonical_lookup(family_file: str) -> None:
    src = (FAMILIES_DIR / family_file).read_text(encoding="utf-8")
    found = [pat for pat in _PRIVATE_LOOKUP_PATTERNS if pat in src]
    assert not found, (
        f"{family_file} accesses canonical_rules directly via {found} — that is a private "
        "re-implementation of the shared SoT lookup. Use src/cuts/helpers/canonical_sot instead "
        "(the v28 fail-open holes were exactly such private/missing cross-checks)."
    )
