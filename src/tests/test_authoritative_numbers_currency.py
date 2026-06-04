# -*- coding: utf-8 -*-
"""Forcing function for the authoritative_numbers.json core node (数字单一来源).

This is the part of the core-node + projection architecture that makes the
single source of truth un-stale-able for the most drift-prone number (the cut
test count). It deliberately does NOT scan prose docs for stale integers —
the docs discuss the numbers meta-textually (changelogs cite old counts as
history, build notes warn "don't misread 36/50"), so a stale-integer scan
false-positives everywhere. The robust forcing function is:

  core node value == live recomputation (zero false-positive risk).

The package README projects the current-claim numbers by *reading* this core
node at build time (build-time injection), so it cannot drift either.

If this test is red:  python scripts/gen_authoritative_numbers.py
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_GEN = REPO / "scripts" / "gen_authoritative_numbers.py"


def _load_gen():
    spec = importlib.util.spec_from_file_location("gen_authoritative_numbers", _GEN)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_core_node_cuts_total_matches_live_collection() -> None:
    gen = _load_gen()
    core = gen.load_core_node()
    assert core["numbers"]["cuts_tests_total"]["value"] == gen.count_cuts_tests(), (
        "authoritative_numbers.json cuts_tests_total is stale vs the live cut test "
        "collection — run: python scripts/gen_authoritative_numbers.py"
    )


def test_core_node_has_no_material_drift() -> None:
    """Regenerating the core node must change no computable value (cuts always;
    sizing/remap when the spike fixture is present)."""
    gen = _load_gen()
    core = gen.load_core_node()
    _, changes = gen.recompute(core)
    material = [c for c in changes if not c.startswith("(")]
    assert not material, "core node stale; run scripts/gen_authoritative_numbers.py -> " + "; ".join(material)
