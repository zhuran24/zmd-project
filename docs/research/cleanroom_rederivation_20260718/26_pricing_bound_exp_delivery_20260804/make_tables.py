#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import lagrangian_accounting as la

HERE = Path(__file__).resolve().parent


def load_duals():
    return json.loads((HERE / "duals.json").read_text(encoding="utf-8"))["duals"]


def main() -> int:
    payload: Dict[str, object] = {}
    dual_rows = []
    for row in load_duals():
        weights = {k: int(v) for k, v in la.bucket_weights(row["mu_scaled"]).items()}
        total = int(la.bound_from_pricing(row["pi_scaled"], row["mu_scaled"], row["lambda_scaled"]))
        dual_rows.append({
            "name": row["name"], "weights": weights,
            "mu_d": sum(la.CLASS_DEMAND[c] * row["mu_scaled"][c] for c in la.CLASS_ORDER),
            "pi_term": sum(la.FAMILY_MULTIPLICITY[f] * row["pi_scaled"][f] for f in la.FAMILY_ORDER),
            "lambda": row["lambda_scaled"], "anchor_bound": total,
        })
    payload["dual_summary"] = dual_rows

    clean_leverage = []
    for drop in range(0, 6):
        clean_leverage.append({
            "clean_local_drop": drop,
            "pure_area_bound": 3392 - 16 * drop,
            "hole_aware_unified_bound": 3388 - 16 * drop,
            "remaining_to_3324_from_hole_aware": max(0, 64 - 16 * drop),
        })
    payload["clean_leverage"] = clean_leverage

    uniform = []
    for drop in (0, 1, 2, 3, 4, 5, 8, 10):
        uniform.append({
            "drop_each_of_all_24_noncore_regions": drop,
            "bound": 3392 - 24 * drop,
        })
    payload["uniform_region_drop"] = uniform

    branch_requirements = {
        "hole_at_CLEAN": "15*dC0 + dC1 + sum(dj0) + dR0 >= 51",
        "hole_at_boundary_H129": "16*dC0 + sum_{j!=k}(dj0) + dj1[k] + dR0 >= 63",
        "hole_at_boundary_H130": "16*dC0 + sum_{j!=k}(dj0) + dj1[k] + dR0 >= 64",
        "hole_at_CORNER": "16*dC0 + sum(dj0) + dR1 >= 35",
    }
    payload["branch_requirements"] = branch_requirements

    (HERE / "generated_tables.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    lines = ["# Recomputed threshold tables", ""]
    lines += ["## Synthetic duals", "", "| dual | bucket weights (in bucket order) | Σdμ | Σmπ | λ | anchor bound |", "|---|---:|---:|---:|---:|---:|"]
    for row in dual_rows:
        ws = "/".join(str(row["weights"][b]) for b in la.BUCKET_ORDER)
        lines.append(f"| {row['name']} | {ws} | {row['mu_d']} | {row['pi_term']} | {row['lambda']} | {row['anchor_bound']} |")
    lines += ["", "Bucket order: " + ", ".join(la.BUCKET_ORDER) + ".", ""]

    lines += ["## CLEAN multiplicity", "", "| local CLEAN no-hole drop | pure 3392 baseline | current hole-aware 3388 baseline | remaining to 3324 |", "|---:|---:|---:|---:|"]
    for row in clean_leverage:
        lines.append(f"| {row['clean_local_drop']} | {row['pure_area_bound']} | {row['hole_aware_unified_bound']} | {row['remaining_to_3324_from_hole_aware']} |")
    lines += ["", "## Exact branch inequalities", ""]
    for key, value in branch_requirements.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    (HERE / "generated_tables.md").write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
