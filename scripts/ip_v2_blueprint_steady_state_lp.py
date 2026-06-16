#!/usr/bin/env python3
"""Steady-state throughput LP solver for IndustrialPlanner v2 blueprints.

Given a blueprint (1000+ devices is fine) and the IP v2 recipe/device spec,
this solves a linear program that answers:

  "At maximum, how many of each final product can this layout produce per
   minute at steady state?"

Assumptions:
  - Belts have effectively unlimited capacity for steady-state purposes
    (blueprint connectivity is verified separately by the static validator).
  - Each device of a given type can run any of its compatible recipes; LP
    decides the optimal split.
  - Source items (unloader pickupItemId, protocol hub outputs) are supplied
    unlimited from outside.
  - Time per machine is bounded: sum(rate * cycle_seconds) ≤ machine_count.

Runtime: seconds (vs simulation's minutes-to-hours).

Usage:
  python3 scripts/ip_v2_blueprint_steady_state_lp.py <blueprint.json>
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from ortools.linear_solver import pywraplp

DEFAULT_SPEC = str(Path(tempfile.gettempdir()) / "ip_v2_device_specs.json")

FINAL_PRODUCTS = ["item_proc_battery_3", "item_proc_qiaoyu_capsule_3"]
TICK_SECONDS = 2.0  # 1 game tick = 2s (matches user's 18 battery/min for 3 packagers)

CN = {
    "item_port_grinder_1": "粉碎机",
    "item_port_furnance_1": "精炼炉",
    "item_port_thickener_1": "研磨机",
    "item_port_shaper_1": "塑形机",
    "item_port_cmpt_mc_1": "配件机",
    "item_port_filling_pd_mc_1": "灌装机",
    "item_port_tools_asm_mc_1": "封装机",
    "item_port_planter_1": "种植机",
    "item_port_seedcol_1": "采种机",
    "item_port_winder_1": "绕线机",
    "item_port_unloader_1": "出货口",
    "item_port_sp_hub_1": "协议核心",
    "item_port_storager_1": "储存箱",
    "item_port_power_sta_1": "热能池",
    "item_port_power_diffuser_1": "供电桩",
}


def cycle_seconds_of(recipe: Dict[str, Any]) -> float:
    # IP v2 recipes use cycleSeconds directly; ours store ticks_per_cycle.
    # Prefer cycleSeconds when present; otherwise interpret ticks_per_cycle.
    if "cycleSeconds" in recipe:
        return float(recipe["cycleSeconds"])
    if "ticks_per_cycle" in recipe:
        return float(recipe["ticks_per_cycle"]) * TICK_SECONDS
    return 1.0  # safe default


def solve(blueprint_path: str, spec_path: str = DEFAULT_SPEC, target_only: bool = False) -> Dict[str, Any]:
    bp = json.load(open(blueprint_path))
    spec = json.load(open(spec_path))
    devices = bp["devices"]
    recipes_all = spec["recipes"]

    # Aggregate device count by typeId
    type_count: Counter = Counter(d["typeId"] for d in devices)

    # Group recipes by machineType
    recipes_by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in recipes_all:
        recipes_by_type[r["machineType"]].append(r)

    # 只有矿石走外部区域物流, 其他全是内部循环.
    EXTERNAL_SOURCE_ITEMS = {"item_iron_ore", "item_originium_ore"}
    BELT_ITEMS_PER_MIN = 60.0

    source_caps: Dict[str, float] = defaultdict(float)
    for d in devices:
        cfg = d.get("config", {}) or {}
        if d["typeId"] == "item_port_unloader_1":
            pick = cfg.get("pickupItemId")
            if pick in EXTERNAL_SOURCE_ITEMS:
                source_caps[pick] += BELT_ITEMS_PER_MIN
        elif d["typeId"] == "item_port_sp_hub_1":
            for entry in cfg.get("protocolHubOutputs", []) or []:
                itemId = entry.get("itemId")
                if itemId in EXTERNAL_SOURCE_ITEMS:
                    source_caps[itemId] += BELT_ITEMS_PER_MIN
    source_items: Set[str] = set(source_caps.keys())

    # Collect all items appearing in recipes
    all_items: Set[str] = set()
    for r in recipes_all:
        for io in (r.get("inputs", []) or []) + (r.get("outputs", []) or []):
            all_items.add(io["itemId"])

    solver = pywraplp.Solver.CreateSolver("GLOP")
    if solver is None:
        raise RuntimeError("OR-Tools GLOP solver unavailable")

    # Variables: rate[typeId][recipe_idx] = cycles per second across ALL machines of typeId running this recipe
    rate_vars: Dict[Tuple[str, str], Any] = {}
    for typeId, recipes in recipes_by_type.items():
        if type_count.get(typeId, 0) == 0:
            continue
        for r in recipes:
            rid = r["id"]
            rate_vars[(typeId, rid)] = solver.NumVar(
                0.0, solver.infinity(), f"r__{typeId}__{rid}"
            )

    # Variables: supply[item] in [0, cap/60 per second]
    # source_caps are in items/min — convert to items/sec for LP variables.
    supply_vars: Dict[str, Any] = {}
    for item in source_items:
        cap_per_sec = source_caps[item] / 60.0
        supply_vars[item] = solver.NumVar(0.0, cap_per_sec, f"supply__{item}")

    # Variables: drain[item] >= 0 for any item (lets unused product just exit)
    drain_vars: Dict[str, Any] = {}
    for item in all_items | source_items:
        drain_vars[item] = solver.NumVar(0.0, solver.infinity(), f"drain__{item}")

    # Constraint per machine type: total machine-time ≤ count
    for typeId, recipes in recipes_by_type.items():
        n = type_count.get(typeId, 0)
        if n == 0:
            continue
        ct = solver.Constraint(0.0, float(n), f"time__{typeId}")
        for r in recipes:
            v = rate_vars.get((typeId, r["id"]))
            if v is None:
                continue
            ct.SetCoefficient(v, cycle_seconds_of(r))

    # Constraint per item: net production - net consumption + supply - drain = 0
    for item in all_items | source_items:
        ct = solver.Constraint(0.0, 0.0, f"bal__{item}")
        # produced by recipes
        for (typeId, rid), v in rate_vars.items():
            r = next(rec for rec in recipes_all if rec["id"] == rid)
            for outent in r.get("outputs", []) or []:
                if outent["itemId"] == item:
                    ct.SetCoefficient(v, float(outent.get("amount", 1)))
            for inent in r.get("inputs", []) or []:
                if inent["itemId"] == item:
                    ct.SetCoefficient(v, -float(inent.get("amount", 1)))
        # external supply (sources only)
        if item in supply_vars:
            ct.SetCoefficient(supply_vars[item], 1.0)
        # drain
        ct.SetCoefficient(drain_vars[item], -1.0)

    # Objective: maximize drain on final products (battery + capsule)
    obj = solver.Objective()
    obj.SetMaximization()
    # IP v2 item names (NOT zmd canonical names)
    # 电池: item_proc_battery_1/2/3 = 低/中/高容谷地电池
    # 胶囊: item_bottled_rec_hp_1/2/3 = 荞愈胶囊 / 优质 / 精选 (精选 = 项目 final target)
    # 默认只计高级版 (_3), 因为 mandatory_exact_instances 设计的就是 _3 + enr chain.
    # 蓝图 27 台 thickener 只为 _3 chain 服务 (产 enr_powder).
    weights = {
        "item_proc_battery_3": 1.0,
        "item_bottled_rec_hp_3": 1.0,
    }
    for item, w in weights.items():
        if item in drain_vars:
            obj.SetCoefficient(drain_vars[item], w)

    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return {"status": "INFEASIBLE_OR_UNBOUNDED", "rationale": status}

    # Extract solution
    result = {
        "status": "OPTIMAL" if status == pywraplp.Solver.OPTIMAL else "FEASIBLE",
        "objective": obj.Value(),
        "machine_types": {},
        "final_products_per_min": {},
        "source_usage_per_min": {},
        "active_recipes_per_min": [],
    }

    for typeId, n in sorted(type_count.items()):
        used_time = sum(
            rate_vars[(typeId, r["id"])].solution_value() * cycle_seconds_of(r)
            for r in recipes_by_type.get(typeId, [])
            if (typeId, r["id"]) in rate_vars
        )
        result["machine_types"][typeId] = {
            "count": n,
            "time_utilization": (used_time / n) if n > 0 else 0.0,
        }

    for item, v in drain_vars.items():
        rate = v.solution_value()
        if rate > 1e-6:
            result["final_products_per_min"][item] = rate * 60

    for item, v in supply_vars.items():
        rate = v.solution_value()
        if rate > 1e-6:
            result["source_usage_per_min"][item] = rate * 60

    for (typeId, rid), v in rate_vars.items():
        rate = v.solution_value()
        if rate > 1e-6:
            result["active_recipes_per_min"].append({
                "typeId": typeId,
                "machine_cn": CN.get(typeId, typeId),
                "recipe_id": rid,
                "cycles_per_min": rate * 60,
            })
    return result


def pretty_print(result: Dict[str, Any]) -> None:
    if result.get("status") not in ("OPTIMAL", "FEASIBLE"):
        print(f"❌ LP {result.get('status')}")
        return
    print(f"=== LP {result['status']}  obj={result['objective']:.3f}/sec ===\n")

    print("=== 最终产品 (per minute, 稳态) ===")
    fp = result.get("final_products_per_min", {})
    if not fp:
        print("  (无 final product 产出 — 上游 chain 不通)")
    for item, rate in sorted(fp.items(), key=lambda kv: -kv[1]):
        print(f"  {item:>30}: {rate:8.2f} / min")
    print()

    print("=== 原料消耗 (per minute, 稳态) ===")
    for item, rate in sorted(result.get("source_usage_per_min", {}).items(), key=lambda kv: -kv[1]):
        print(f"  {item:>30}: {rate:8.2f} / min")
    print()

    print("=== 机器利用率 ===")
    for typeId, info in sorted(result["machine_types"].items()):
        n = info["count"]
        u = info["time_utilization"]
        cn = CN.get(typeId, typeId)
        if u < 1e-6 and "belt" not in typeId and "log" not in typeId and "power_diffuser" not in typeId:
            continue
        if u > 1e-6:
            bar = "█" * int(u * 20) + "·" * (20 - int(u * 20))
            print(f"  {cn:>8} ({typeId:<32}) n={n:>3}  [{bar}] {u*100:5.1f}%")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("blueprint")
    p.add_argument("--spec", default=DEFAULT_SPEC)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    result = solve(args.blueprint, args.spec)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    pretty_print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
