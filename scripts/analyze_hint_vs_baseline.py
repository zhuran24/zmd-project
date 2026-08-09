"""Compare hint-enabled trial state vs baseline state.

Reads two `exact_campaign_state.json` files and prints:
  - histogram of candidate statuses for each
  - per-candidate diff: same status, INFEASIBLE→FEASIBLE upgrades, etc.

Usage:
  python scripts/analyze_hint_vs_baseline.py BASELINE.json HINT.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def load_candidates(path: Path) -> dict:
    return json.loads(path.read_text()).get("candidates", {})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("baseline", type=Path)
    ap.add_argument("hint", type=Path)
    args = ap.parse_args()

    baseline = load_candidates(args.baseline)
    hint = load_candidates(args.hint)

    b_hist = Counter(v.get("status") for v in baseline.values())
    h_hist = Counter(v.get("status") for v in hint.values())

    print(f"BASELINE ({args.baseline}):")
    for st, cnt in sorted(b_hist.items()):
        print(f"  {st}: {cnt}")
    print(f"  total: {len(baseline)}")
    print()
    print(f"HINT ({args.hint}):")
    for st, cnt in sorted(h_hist.items()):
        print(f"  {st}: {cnt}")
    print(f"  total: {len(hint)}")
    print()

    common = set(baseline.keys()) & set(hint.keys())
    transitions = Counter()
    for k in common:
        b_st = baseline[k].get("status")
        h_st = hint[k].get("status")
        transitions[(b_st, h_st)] += 1

    print(f"COMMON CANDIDATES ({len(common)}):")
    for (b_st, h_st), cnt in sorted(transitions.items()):
        marker = ""
        if b_st == "UNKNOWN" and h_st == "FEASIBLE":
            marker = " 🟢 hint WIN"
        elif b_st == "UNKNOWN" and h_st == "INFEASIBLE":
            marker = " ✓ hint DECISIVE (UNKNOWN→INFEASIBLE)"
        elif b_st == "FEASIBLE" and h_st == "UNKNOWN":
            marker = " ⚠ regression (FEASIBLE→UNKNOWN)"
        print(f"  {b_st} -> {h_st}: {cnt}{marker}")

    only_in_hint = set(hint.keys()) - set(baseline.keys())
    if only_in_hint:
        print(f"\nONLY IN HINT ({len(only_in_hint)}):")
        for k in sorted(only_in_hint)[:10]:
            print(f"  {k}: {hint[k].get('status')}")
        if len(only_in_hint) > 10:
            print(f"  ...and {len(only_in_hint) - 10} more")

    only_in_baseline = set(baseline.keys()) - set(hint.keys())
    if only_in_baseline:
        print(f"\nONLY IN BASELINE ({len(only_in_baseline)}):")
        for k in sorted(only_in_baseline)[:10]:
            print(f"  {k}: {baseline[k].get('status')}")
        if len(only_in_baseline) > 10:
            print(f"  ...and {len(only_in_baseline) - 10} more")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
