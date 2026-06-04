# -*- coding: utf-8 -*-
"""Regenerate the authoritative_numbers.json core node (主体).

数字单一来源 (single source of truth) regenerator. The forcing function
src/tests/test_authoritative_numbers_currency.py imports `count_cuts_tests`
and `load_core_node` from here so the test and the generator share one
recompute path.

What this updates:
- cuts_tests_total: always recomputed from the live test tree (master has it).
- sizing 6 ints: recomputed ONLY when the spike fixture is present (package /
  spike-data context); otherwise the frozen values are preserved (master lacks
  data/cuts/spike/, see authoritative_numbers.json _meta.data_location_note).
- remap pair phrase: recomputed only when data/cuts/spike/remap_audit.json present.
- f3 / ortools constants: manual; preserved.

Run:
    python scripts/gen_authoritative_numbers.py            # write + print diff
    python scripts/gen_authoritative_numbers.py --check    # exit 1 if anything stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

REPO = Path(__file__).resolve().parents[1]
CORE_NODE = REPO / "docs" / "research" / "p1_2_spike_sizing_gate_20260601" / "authoritative_numbers.json"
CUTS_TESTS_DIR = REPO / "src" / "tests" / "cuts"
SPIKE_FIXTURE = REPO / "data" / "cuts" / "spike" / "oracle_emit_fixture_45cert.jsonl"
REMAP_AUDIT = REPO / "data" / "cuts" / "spike" / "remap_audit.json"


def count_cuts_tests() -> int:
    """True pytest collection count for src/tests/cuts (matches the 'N passed' docs cite).

    AST `def test_` counting undercounts parametrized tests, so we use pytest's
    own collection (subprocess, ~seconds) as the authoritative number.
    """
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", str(CUTS_TESTS_DIR)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    return sum(1 for line in out.stdout.splitlines() if "::" in line)


def load_core_node() -> Dict:
    return json.loads(CORE_NODE.read_text(encoding="utf-8"))


def current_claims() -> Dict[str, str]:
    """Flat {key: display-string} for build-time injection.

    A package build script should pull current-claim numbers from here instead
    of hard-coding them in its README template, so the package README is a true
    projection of the core node and cannot drift. Historical/changelog literals
    in the template stay as written (the core node only carries current values).
    """
    core = load_core_node()
    out = {key: str(meta["value"]) for key, meta in core["numbers"].items()}
    out["remap_audit"] = core["phrases"]["remap_audit"]["current"]
    return out


def _recompute_sizing() -> Optional[Dict[str, int]]:
    """Sizing 6 ints via sizing_gate.compute_sizing_numbers; None if spike fixture absent."""
    if not SPIKE_FIXTURE.exists():
        return None
    sizing_dir = CORE_NODE.parent
    sys.path.insert(0, str(sizing_dir))
    try:
        import sizing_gate  # type: ignore

        return sizing_gate.compute_sizing_numbers()
    finally:
        sys.path.remove(str(sizing_dir))


def _recompute_remap() -> Optional[str]:
    if not REMAP_AUDIT.exists():
        return None
    audit = json.loads(REMAP_AUDIT.read_text(encoding="utf-8"))
    return f"{audit['n_pairs_remapped']}/{audit['n_pairs_total']}"


def recompute(core: Dict) -> Tuple[Dict, list]:
    """Return (updated_core, list_of_change_strings). Preserves frozen/manual values."""
    changes = []
    nums = core["numbers"]

    live_cuts = count_cuts_tests()
    if nums["cuts_tests_total"]["value"] != live_cuts:
        changes.append(f"cuts_tests_total: {nums['cuts_tests_total']['value']} -> {live_cuts}")
        nums["cuts_tests_total"]["value"] = live_cuts

    sizing = _recompute_sizing()
    if sizing is not None:
        for key, val in sizing.items():
            if key in nums and nums[key]["value"] != val:
                changes.append(f"{key}: {nums[key]['value']} -> {val}")
                nums[key]["value"] = val
    else:
        changes.append("(sizing 6 ints: spike fixture absent -> preserved frozen values)")

    remap = _recompute_remap()
    if remap is not None and core["phrases"]["remap_audit"]["current"] != remap:
        changes.append(f"remap_audit: {core['phrases']['remap_audit']['current']} -> {remap}")
        core["phrases"]["remap_audit"]["current"] = remap

    return core, changes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if regeneration would change anything")
    args = ap.parse_args()

    core = load_core_node()
    updated, changes = recompute(core)
    material = [c for c in changes if not c.startswith("(")]

    if args.check:
        if material:
            print("STALE — core node would change on regenerate:")
            for c in changes:
                print("  " + c)
            return 1
        print("core node up to date")
        return 0

    CORE_NODE.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if material:
        print("regenerated authoritative_numbers.json:")
    else:
        print("authoritative_numbers.json unchanged (no material drift):")
    for c in changes:
        print("  " + c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
