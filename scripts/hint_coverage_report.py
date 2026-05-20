"""Audit a master-hint JSON: coverage % per facility_type + pose_idx validity.

Usage: python scripts/hint_coverage_report.py [hint.json]

Reports:
  - hinted / total mandatory per facility_type
  - any pose_idx out of range for its pool
  - blueprint instance count vs mandatory count gap
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "hint",
        type=Path,
        nargs="?",
        default=PROJECT_ROOT / "data" / "hints" / "blueprint_2026_05_13_master_hint.json",
    )
    args = ap.parse_args()

    hint = json.loads(args.hint.read_text())
    mandatory = json.loads(
        (PROJECT_ROOT / "data" / "preprocessed" / "mandatory_exact_instances.json").read_text()
    )
    candidate_placements = json.loads(
        (PROJECT_ROOT / "data" / "preprocessed" / "candidate_placements.json").read_text()
    )

    ft_by_id = {m["instance_id"]: m["facility_type"] for m in mandatory}
    hinted_ids = set(hint.keys())
    missing = [m for m in mandatory if m["instance_id"] not in hinted_ids]

    print(f"Hint file: {args.hint}")
    print(f"Mandatory instances: {len(mandatory)}")
    print(f"Hinted: {len(hinted_ids)} ({100 * len(hinted_ids) / len(mandatory):.1f}%)")
    print(f"Missing: {len(missing)}")

    print("\nMissing by facility_type:")
    ft_missing = Counter(m["facility_type"] for m in missing)
    for ft, c in sorted(ft_missing.items()):
        total_ft = sum(1 for m in mandatory if m["facility_type"] == ft)
        print(f"  {ft}: {c}/{total_ft} missing ({100 * c / total_ft:.0f}%)")

    out_of_range = []
    for inst_id, pose_idx in hint.items():
        ft = ft_by_id.get(inst_id)
        if ft is None:
            out_of_range.append((inst_id, pose_idx, "unknown facility_type"))
            continue
        try:
            pose_idx_int = int(pose_idx)
        except (TypeError, ValueError):
            out_of_range.append((inst_id, pose_idx, "non-int"))
            continue
        pool_size = len(candidate_placements["facility_pools"].get(ft, []))
        if not (0 <= pose_idx_int < pool_size):
            out_of_range.append((inst_id, pose_idx, f"out of [0, {pool_size})"))

    if out_of_range:
        print(f"\nINVALID pose_idx: {len(out_of_range)}")
        for x in out_of_range[:10]:
            print(f"  {x}")
        return 1

    print("\nAll pose_idx values are within valid ranges. ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
