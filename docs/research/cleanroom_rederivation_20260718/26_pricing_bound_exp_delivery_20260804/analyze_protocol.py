#!/usr/bin/env python3
"""Aggregate protocol JSON and apply the stated numeric decision gates."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lagrangian_accounting as la  # noqa: E402

Key = Tuple[str, str, bool]
CRITICAL = (
    ("D0_AREA", "CLEAN", False),
    ("D1_SCARCITY_PRICES", "CLEAN", False),
    ("D2_SLACK_EDGE_SELECTIVE", "CLEAN", True),
    ("D2_SLACK_EDGE_SELECTIVE", "LEFT_J3", True),
)


def _dual_rows(path: Path) -> Dict[str, Mapping[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {row["name"]: row for row in payload["duals"]}


def _iter_results(manifest: Mapping[str, object]):
    stages = manifest.get("stages", {})
    if not isinstance(stages, Mapping):
        return
    for stage, rows in stages.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            task = row.get("task")
            result = row.get("result")
            if isinstance(task, Mapping) and isinstance(result, Mapping):
                yield str(stage), task, result


def _key(task: Mapping[str, object]) -> Key:
    return (str(task["dual"]), str(task["family"]), bool(task["hole"]))


def _bound_at_or_before(result: Mapping[str, object], target: float) -> Optional[float]:
    events = result.get("bound_events", [])
    eligible = []
    if isinstance(events, list):
        for row in events:
            if isinstance(row, Mapping) and float(row.get("t", math.inf)) <= target + 1e-9:
                eligible.append(row)
    if not eligible:
        return None
    eligible.sort(key=lambda row: float(row["t"]))
    return float(eligible[-1]["bound_scaled"])


def metrics(result: Mapping[str, object]) -> Dict[str, float]:
    cap_raw = result.get("objective_cap_scaled")
    bound_raw = result.get("certified_objective_bound_scaled")
    incumbent_raw = result.get("objective_value_scaled")
    if cap_raw is None or bound_raw is None:
        return {"cap": math.nan, "bound": math.nan, "drop": 0.0,
                "closure": 0.0, "late_drop": 0.0}
    scale = float(result.get("scale", 1) or 1)
    cap = float(cap_raw) / scale
    bound = float(bound_raw) / scale
    incumbent = (float(incumbent_raw) / scale) if incumbent_raw is not None else 0.0
    drop = max(0.0, cap - bound)
    closure = drop / max(1.0 / scale, cap - incumbent)
    at60_scaled = _bound_at_or_before(result, 60.0)
    at60 = None if at60_scaled is None else at60_scaled / scale
    late_drop = 0.0 if at60 is None else max(0.0, at60 - bound)
    return {"cap": cap, "bound": bound, "drop": drop,
            "closure": closure, "late_drop": late_drop}


def _best_by_key(
    records, *, strict_only: bool = True, seed: Optional[int] = None,
    min_seconds: float = 0.0,
):
    best: Dict[Key, Mapping[str, object]] = {}
    for _stage, task, result in records:
        if strict_only and (bool(task.get("relaxed")) or bool(task.get("loose"))):
            continue
        if seed is not None and int(task.get("seed", -1)) != seed:
            continue
        if float(result.get("seconds_limit", 0.0)) < min_seconds:
            continue
        key = _key(task)
        bound = result.get("certified_objective_bound_scaled")
        if bound is None:
            continue
        old = best.get(key)
        if old is None or float(bound) < float(old["certified_objective_bound_scaled"]):
            best[key] = result
    return best


def _best_legal_by_key(records):
    """Best legal upper per branch from relaxed or strict no-cap-3 runs.

    Loose calibration and finite max-pole sensitivity runs are excluded because
    they do not match the primary no-fixed-pole-cap pricing scope.
    """
    best: Dict[Key, Mapping[str, object]] = {}
    for _stage, task, result in records:
        if bool(task.get("loose")):
            continue
        if task.get("max_poles") is not None:
            continue
        key = _key(task)
        bound = result.get("certified_objective_bound_scaled")
        if bound is None:
            continue
        old = best.get(key)
        if old is None or float(bound) / float(result.get("scale", 1) or 1) < float(old["certified_objective_bound_scaled"]) / float(old.get("scale", 1) or 1):
            best[key] = result
    return best


def _hybrid_dual_bound(
    dual: Mapping[str, object], best: Mapping[Key, Mapping[str, object]]
) -> Tuple[float, Dict[str, float]]:
    name = str(dual["name"])
    scale = int(dual.get("scale", 1) or 1)
    branch_caps = dual.get("analytic_branch_cap_scaled", {})
    B_scaled: Dict[str, float] = {}
    for family in la.FAMILY_ORDER:
        candidates: List[float] = []
        family_caps = branch_caps.get(family, {}) if isinstance(branch_caps, Mapping) else {}
        for hole in (False, True):
            branch_name = "hole" if hole else "nohole"
            analytic = family_caps.get(branch_name) if isinstance(family_caps, Mapping) else None
            if analytic is None:
                # None means an impossible branch only when explicitly present.
                if isinstance(family_caps, Mapping) and branch_name in family_caps:
                    branch_upper = -math.inf
                else:
                    branch_upper = float(dual["pi_scaled"][family])
            else:
                branch_upper = float(analytic)
            result = best.get((name, family, hole))
            if result is not None:
                result_bound = float(result["certified_objective_bound_scaled"])
                branch_upper = min(branch_upper, result_bound)
            candidates.append(branch_upper)
        combined = max(candidates)
        B_scaled[family] = min(float(dual["pi_scaled"][family]), combined)
    total_scaled = float(la.bound_from_pricing(B_scaled, dual["mu_scaled"], dual["lambda_scaled"]))
    B = {f: value / scale for f, value in B_scaled.items()}
    return total_scaled / scale, B



def _d0_exactly_one_hole_bound(
    best: Mapping[Key, Mapping[str, object]]
) -> Dict[str, object]:
    """Explicit exactly-one-hole area accounting for the supplied cap-3 scope.

    The bundled CLEAN=129 and CORNER=85 hole bounds were obtained with the
    supplied MAX_POLES_PER_REGION=3 model.  A no-cap pricing upper is still a
    legal upper for that smaller scope, so measured no-cap D0 bounds may safely
    tighten these branch inputs, but the resulting certificate must retain the
    cap-3 scope label.
    """
    nohole: Dict[str, float] = {
        "CLEAN": 146.0,
        **{family: 134.0 for family in la.BOUNDARY_FAMILIES},
        "CORNER": 118.0,
    }
    hole: Dict[str, float] = {
        "CLEAN": 129.0,
        **{family: float(value) for family, value in la.BOUNDARY_HOLE_BASE.items()},
        "CORNER": 85.0,
    }
    for family in ("CLEAN", *la.BOUNDARY_FAMILIES, "CORNER"):
        for has_hole, target in ((False, nohole), (True, hole)):
            result = best.get(("D0_AREA", family, has_hole))
            if result is None:
                continue
            raw = result.get("certified_objective_bound_scaled")
            if raw is None:
                continue
            scale = float(result.get("scale", 1) or 1)
            target[family] = min(target[family], float(raw) / scale)
    branches = la.hole_branch_bounds(nohole, hole)
    return {
        "scope": "supplied_MAX_POLES_PER_REGION_3",
        "nohole_upper": nohole,
        "hole_upper": hole,
        "branches": {name: float(value) for name, value in branches.items()},
        "unified_bound": float(branches["unified"]),
        "reduction_from_3388": 3388.0 - float(branches["unified"]),
    }

def _calibration(records) -> Tuple[bool, Optional[float]]:
    values = []
    for _stage, task, result in records:
        if (
            task.get("dual") == "D0_AREA"
            and task.get("family") == "CORNER"
            and bool(task.get("hole"))
            and bool(task.get("loose"))
            and int(task.get("max_poles", -1)) == 3
        ):
            bound = result.get("certified_objective_bound_scaled")
            if bound is not None:
                values.append(float(bound) / float(result.get("scale", 1) or 1))
    if not values:
        return False, None
    best = min(values)
    return best <= 90.0, best


def decide(manifest: Mapping[str, object], duals: Mapping[str, Mapping[str, object]]) -> Dict[str, object]:
    records = list(_iter_results(manifest))
    best = _best_by_key(records)
    best_legal = _best_legal_by_key(records)
    hybrid: Dict[str, object] = {}
    for name, dual in duals.items():
        value, B = _hybrid_dual_bound(dual, best_legal)
        scale = float(dual.get("scale", 1) or 1)
        initial = float(la.bound_from_pricing(dual["pi_scaled"], dual["mu_scaled"], dual["lambda_scaled"])) / scale
        hybrid[name] = {
            "initial_bound": initial,
            "hybrid_bound": value,
            "reduction": initial - value,
            "family_pricing_upper": B,
        }

    d0_hole = _d0_exactly_one_hole_bound(best_legal)
    cal_ok, cal_bound = _calibration(records)
    lagrangian_certificate = any(row["hybrid_bound"] <= 3324.0 for row in hybrid.values())
    cap3_branch_certificate = float(d0_hole["unified_bound"]) <= 3324.0
    certificate = lagrangian_certificate or cap3_branch_certificate
    direct_bound_gate = float(d0_hole["unified_bound"]) <= 3332.0

    by_dual: Dict[str, List[float]] = defaultdict(list)
    clean_drop: Dict[str, float] = defaultdict(float)
    late_by_dual: Dict[str, float] = defaultdict(float)
    for key, result in best.items():
        m = metrics(result)
        by_dual[key[0]].append(m["closure"])
        if key[1] == "CLEAN":
            clean_drop[key[0]] = max(clean_drop[key[0]], m["drop"])
        late_by_dual[key[0]] = max(late_by_dual[key[0]], m["late_drop"])
    shape_hits = 0
    for name in duals:
        median_closure = statistics.median(by_dual[name]) if by_dual[name] else 0.0
        if clean_drop[name] >= 4.0 and median_closure >= 0.25 and late_by_dual[name] >= 1.0:
            shape_hits += 1
    shape_go = shape_hits >= 2
    d0_clean = best.get(("D0_AREA", "CLEAN", False))
    d0_clean_late_drop = metrics(d0_clean)["late_drop"] if d0_clean is not None else 0.0
    direct_go = direct_bound_gate and d0_clean_late_drop >= 1.0

    # NO-GO requires the positive control and paired 240 s seed-0/seed-1 flatness
    # on all four critical tasks.  Stage-1 flatness alone is never enough.
    seed0 = _best_by_key(records, seed=0, min_seconds=239.0)
    seed1 = _best_by_key(records, seed=1, min_seconds=239.0)
    critical_flat = True
    critical_details = {}
    for key in CRITICAL:
        rows = []
        for seed_map in (seed0, seed1):
            result = seed_map.get(key)
            if result is None:
                rows.append(None)
                critical_flat = False
                continue
            m = metrics(result)
            flat = m["drop"] < 1.0 and m["late_drop"] < 1.0
            rows.append({**m, "flat": flat})
            critical_flat = critical_flat and flat
        critical_details[str(key)] = rows
    all_closures = [metrics(result)["closure"] for result in best.values()]
    max_closure = max(all_closures, default=0.0)
    d0_reduction = float(d0_hole["reduction_from_3388"])
    no_go = cal_ok and critical_flat and max_closure < 0.10 and d0_reduction < 16.0

    if certificate:
        verdict = "GO_CERTIFICATE_ALREADY_REACHED"
    elif direct_go or shape_go:
        verdict = "GO"
    elif no_go:
        verdict = "NO_GO"
    elif cal_bound is None:
        verdict = "INCOMPLETE_NO_CALIBRATION"
    elif not cal_ok:
        verdict = "INVALID_CALIBRATION_FAILED"
    else:
        verdict = "INTERMEDIATE"

    return {
        "verdict": verdict,
        "calibration": {"valid": cal_ok, "best_bound": cal_bound, "required": "<= 90"},
        "hybrid_bounds": hybrid,
        "D0_exactly_one_hole_cap3_scope": d0_hole,
        "go_gates": {
            "certificate_any_lagrangian_hybrid_le_3324": lagrangian_certificate,
            "certificate_D0_cap3_hole_branch_le_3324": cap3_branch_certificate,
            "certificate_either": certificate,
            "direct_D0_cap3_hole_branch_le_3332": direct_bound_gate,
            "direct_D0_CLEAN_nohole_late_drop_ge_1": d0_clean_late_drop >= 1.0,
            "direct_GO_combined": direct_go,
            "weighted_shape_hits": shape_hits,
            "weighted_shape_required": 2,
        },
        "no_go_gates": {
            "critical_paired_flat": critical_flat,
            "critical_details": critical_details,
            "max_closure": max_closure,
            "requires_max_closure_lt": 0.10,
            "D0_hybrid_reduction": d0_reduction,
            "requires_D0_reduction_lt": 16.0,
        },
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--duals", type=Path, default=HERE / "duals.json")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = decide(manifest, _dual_rows(args.duals))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
