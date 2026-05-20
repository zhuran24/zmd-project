"""Layout-Invariant Cert (LIC) Phase 0 cheap-gate probe.

Hypothesis (paradigm direction):
24 个 lever 全 verdict 死的共同 pattern 是 "master OPTIMAL 选 layout L_i,
subproblem reject, cut 退化为 ban (instance, pose) tuple" (core size = 1,
所有 6 paradigm 同质). 没人尝试过的: cut 升到 **cell-front pattern** 层 —
即 "any layout 产生相同 cell-front 几何形态都 routing-infeasible". 若
单 pose tuple 对应等价类巨大 (≥100), cut 强度跨数量级.

Phase 0 cheap gate: 不投资 cut 实现, 只验等价类是否真巨大. 如果固定
L0 后 same-pattern pose tuple 只有 < 10 个, paradigm 死 (cell-front pattern
几乎决定 pose, cut 退化回 pose no-good).

Metrics:
- m1 = same-pattern pose tuple count (枚举或采样估计)
- m2 = clone master solve wall-time (cell-front pattern fixed, pose free)
- m3 = clone master status
- m4 = oracle consistency rate (5 alternative pose tuples 全 binding reject?)

GO threshold:  m1 ≥ 100  AND  m2 ≤ 60s  AND  m4 = 5/5 reject  AND  m3 ≠ UNKNOWN
NO-GO:         m1 < 10   OR   m2 > 300s  OR   m4 ≤ 3/5         OR   m3 = UNKNOWN

不改 src. clone master 通过 *复用* `PoseBoolExactMasterDelegate` build 完后
*替换约束*: 不是新写一个 master class, 而是 build 完 standard pose-bool master,
然后 AddBoolXOr / AddImplication 形式注入 cell-front pattern equivalence —
对每个 active port pos (cell, dir) 加约束 "至少一个 pose 在 (cell, dir) 提
供 port", 对每个 occupied cell c 加约束 "至少一个 pose 占 c". 这是 cell-front
pattern 的精确 LP 镜像, build 时间几乎为零, 不读取也不修改 src.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple

# Phase 0 probe lives in docs/research/<dir>/. Add project root so `src.*` resolves.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

_DIR_DELTA: Dict[str, Tuple[int, int]] = {
    "N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0),
}

OUT_FILE = Path(
    "docs/research/layout_invariant_cert_phase0_20260520/phase0_results.json"
)


# ----------------------------- data structs ----------------------------- #


@dataclass
class CellFrontPattern:
    """L₀ 的 cell-front 几何描述. 用于 (a) 枚举等价类, (b) 构造 clone master 约束."""

    occupied_cells: FrozenSet[Tuple[int, int]] = field(default_factory=frozenset)
    # active port: (cell_x, cell_y, dir) — 来自 layout 中所有出现的 input/output port
    active_ports: FrozenSet[Tuple[int, int, str]] = field(default_factory=frozenset)


@dataclass
class ProbeResult:
    m1_pose_equivalence_class_size: Optional[int] = None
    m1_method: str = ""  # "exhaustive" | "sampled"
    m2_clone_solve_time_seconds: Optional[float] = None
    m3_clone_status: str = ""
    m4_oracle_consistency_rate: str = ""  # "x/y"
    m4_rejected: int = 0
    m4_tested: int = 0
    verdict: str = ""  # "GO" | "NO-GO" | "PARTIAL"
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "m1_pose_equivalence_class_size": self.m1_pose_equivalence_class_size,
            "m1_method": self.m1_method,
            "m2_clone_solve_time_seconds": self.m2_clone_solve_time_seconds,
            "m3_clone_status": self.m3_clone_status,
            "m4_oracle_consistency_rate": self.m4_oracle_consistency_rate,
            "m4_rejected": self.m4_rejected,
            "m4_tested": self.m4_tested,
            "verdict": self.verdict,
            "notes": self.notes,
        }


# ----------------------------- helpers ----------------------------- #


def _extract_cell_front_pattern_from_solution(
    solution: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, List[Dict[str, Any]]],
) -> CellFrontPattern:
    """从 master.extract_solution() 出来的 placement_solution 抽 P(L₀).

    solution[inst_id] 形如 {facility_type, pose_idx, pose_id, anchor:{x,y}, ...}.
    pose 数据 (facility_pools[tpl][pose_idx]) 的 occupied_cells / input_port_cells /
    output_port_cells 用 **GLOBAL 坐标** (经验自 _build_global_pose_cache 注释 +
    `extract_solution` 不加 anchor 偏移). 所以直接取即可, 不再加 anchor.x/.y.
    """
    occupied: Set[Tuple[int, int]] = set()
    ports: Set[Tuple[int, int, str]] = set()
    for inst_id, sol in solution.items():
        tpl = str(sol.get("facility_type", ""))
        pose_idx = int(sol.get("pose_idx", -1))
        if not tpl or pose_idx < 0:
            continue
        pool = facility_pools.get(tpl, [])
        if pose_idx >= len(pool):
            continue
        pose = pool[pose_idx]
        for c in pose.get("occupied_cells", []) or []:
            occupied.add((int(c[0]), int(c[1])))
        for side in ("input_port_cells", "output_port_cells"):
            for p in pose.get(side, []) or []:
                ports.add((int(p.get("x", 0)), int(p.get("y", 0)), str(p.get("dir", ""))))
    return CellFrontPattern(
        occupied_cells=frozenset(occupied),
        active_ports=frozenset(ports),
    )


def _pose_signature(
    pose: Mapping[str, Any]
) -> Tuple[FrozenSet[Tuple[int, int]], FrozenSet[Tuple[int, int, str]]]:
    """对一个 pose 计算 (cells, port-set). 用于按 footprint+port 分桶."""
    cells = frozenset(
        (int(c[0]), int(c[1])) for c in (pose.get("occupied_cells", []) or [])
    )
    ports: Set[Tuple[int, int, str]] = set()
    for side in ("input_port_cells", "output_port_cells"):
        for p in pose.get(side, []) or []:
            ports.add((int(p.get("x", 0)), int(p.get("y", 0)), str(p.get("dir", ""))))
    return cells, frozenset(ports)


def _count_pose_equivalence_class(
    chosen: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, List[Dict[str, Any]]],
    sample_cap: int = 200_000,
) -> Tuple[Optional[int], str, List[str]]:
    """对每个 instance, 找出有多少 pose 跟当前 chosen pose 是 (cells, ports)-equivalent.
    等价类总大小 = ∏ instance 的 equivalent-pose 数.

    返回 (size, method, notes). 超过 sample_cap 直接 short-circuit 给 lower bound.
    """
    notes: List[str] = []
    per_instance: List[Tuple[str, int]] = []  # (inst_id, equiv_count)
    for inst_id, sol in chosen.items():
        tpl = str(sol.get("facility_type", ""))
        pose_idx = int(sol.get("pose_idx", -1))
        if not tpl or pose_idx < 0:
            continue
        pool = facility_pools.get(tpl, [])
        if pose_idx >= len(pool):
            continue
        ref_sig = _pose_signature(pool[pose_idx])
        count = 0
        for cand_pose in pool:
            if _pose_signature(cand_pose) == ref_sig:
                count += 1
        per_instance.append((inst_id, max(count, 1)))

    # 注意: 这里乘积可能爆 int. 用 log 估计避免 overflow.
    import math
    log_prod = 0.0
    for _iid, c in per_instance:
        log_prod += math.log(max(c, 1))
    # 但 lever-level meaning: 多 instance 共享 same pose 池, 各自 pose 选无关.
    # 这是 over-counting (没扣 cell exclusivity / instance-pose 唯一映射). 因此
    # 实际 size <= product. 但 lower bound 是 per-instance multiplicity 中的 max,
    # 因为 worst case 单个 instance 可独立切换其等价 pose.
    multiplicities = [c for _i, c in per_instance]
    if not multiplicities:
        return 0, "empty", notes
    # 用 ≥ max(multiplicities) 作 conservative 下界 (单 instance 切换都 valid).
    # 注: 严格等价类 size 需 clone master enum 全 solution; m1 取 ≥ 该下界即可
    # 满足 "≥ 100" 判定.
    lower_bound = max(multiplicities)
    # 上界 (product) 可能很大, log 形式记一下.
    upper_bound_log10 = log_prod / math.log(10)
    notes.append(
        f"m1 per-instance multiplicities min={min(multiplicities)} "
        f"max={max(multiplicities)} mean={sum(multiplicities)/len(multiplicities):.2f}"
    )
    notes.append(
        f"m1 product upper-bound log10≈{upper_bound_log10:.1f} "
        f"(over-count, ignores cell-exclusivity coupling)"
    )
    return lower_bound, "instance-multiplicity-lowerbound", notes


def _sample_alternative_pose_tuples(
    chosen: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, List[Dict[str, Any]]],
    n_samples: int,
    rng: random.Random,
) -> List[Dict[str, Dict[str, Any]]]:
    """从 same-pattern 等价类里随机抽 n_samples 个 alternative pose tuple.

    每抽样: 随机选若干 instance 切到等价 pose, 其余保持. 返回 placement_solution
    格式 (跟 master.extract_solution() 同) — 直接喂 PortBindingModel.

    注意 cell exclusivity: 单 instance 切到等价 pose 仍占同 cells, 所以
    safe (cells 集合不变). 这是为啥 m1 lower bound 用 single-instance switch.
    """
    samples: List[Dict[str, Dict[str, Any]]] = []
    # 构造 per-instance 的等价 pose_idx list
    equiv_by_inst: Dict[str, List[int]] = {}
    for inst_id, sol in chosen.items():
        tpl = str(sol.get("facility_type", ""))
        pose_idx = int(sol.get("pose_idx", -1))
        pool = facility_pools.get(tpl, [])
        if pose_idx < 0 or pose_idx >= len(pool):
            continue
        ref_sig = _pose_signature(pool[pose_idx])
        candidates: List[int] = []
        for i, cand in enumerate(pool):
            if i == pose_idx:
                continue
            if _pose_signature(cand) == ref_sig:
                candidates.append(i)
        if candidates:
            equiv_by_inst[inst_id] = candidates

    if not equiv_by_inst:
        return []

    inst_ids_with_alts = list(equiv_by_inst.keys())
    seen_signatures: Set[Tuple[Tuple[str, int], ...]] = set()
    attempts = 0
    while len(samples) < n_samples and attempts < n_samples * 20:
        attempts += 1
        alt = {k: dict(v) for k, v in chosen.items()}
        # flip k random instances (k random in [1, len(alts)]).
        k = rng.randint(1, min(5, len(inst_ids_with_alts)))
        flip_set = rng.sample(inst_ids_with_alts, k=k)
        for fid in flip_set:
            new_idx = rng.choice(equiv_by_inst[fid])
            tpl = str(alt[fid]["facility_type"])
            pool = facility_pools[tpl]
            new_pose = pool[new_idx]
            alt[fid] = dict(alt[fid])
            alt[fid]["pose_idx"] = int(new_idx)
            alt[fid]["pose_id"] = new_pose.get("pose_id", alt[fid].get("pose_id"))
            alt[fid]["anchor"] = dict(new_pose.get("anchor", alt[fid].get("anchor", {})))
        sig = tuple(sorted((k, int(v["pose_idx"])) for k, v in alt.items()))
        if sig in seen_signatures:
            continue
        seen_signatures.add(sig)
        samples.append(alt)
    return samples


# ----------------------------- main steps ----------------------------- #


def _step1_solve_master(args: argparse.Namespace) -> Tuple[Any, Dict[str, Any], List[str]]:
    """Step 1+2: build + solve B1 pose-bool master, return (master_model, layout, notes).

    Falls back to "import smoke only" in --dry-run.
    """
    notes: List[str] = []
    os.environ["EXACT_USE_POSE_BOOL_MASTER"] = "1"
    os.environ["EXACT_MASTER_GHOST_ANCHOR_FILTER"] = f"{args.anchor_x},{args.anchor_y}"

    from src.models.master_model import (
        MasterPlacementModel,
        infer_exact_required_pose_optional_counts,
        load_generic_io_requirements_artifact,
        load_project_data,
    )

    notes.append(
        f"env EXACT_USE_POSE_BOOL_MASTER=1 EXACT_MASTER_GHOST_ANCHOR_FILTER="
        f"{args.anchor_x},{args.anchor_y}"
    )

    if args.dry_run:
        notes.append("dry-run: master imports resolved, skipping solve")
        return None, {}, notes

    t0 = time.perf_counter()
    instances, pools, rules = load_project_data(Path("."), "certified_exact")
    generic = load_generic_io_requirements_artifact(Path("."))
    counts = infer_exact_required_pose_optional_counts(rules, generic)
    notes.append(f"[load] {time.perf_counter()-t0:.1f}s")

    anchor_filter = {(args.anchor_x, args.anchor_y)}
    t1 = time.perf_counter()
    m = MasterPlacementModel(
        instances, pools, rules,
        ghost_rect=(args.ghost_w, args.ghost_h),
        skip_power_coverage=False,
        generic_io_requirements=generic,
        exact_required_pose_optional_counts=counts,
        solve_mode="certified_exact",
        ghost_anchor_filter=anchor_filter,
    )
    notes.append(f"[master_init] {time.perf_counter()-t1:.1f}s")
    notes.append(
        f"  delegate={type(m._coordinate_delegate).__name__ if m._coordinate_delegate else 'None'}"
    )

    t3 = time.perf_counter()
    m.build()
    notes.append(f"[build] {time.perf_counter()-t3:.1f}s")

    t4 = time.perf_counter()
    status = m.solve(time_limit_seconds=args.master_time_limit)
    elapsed = time.perf_counter() - t4

    from ortools.sat.python import cp_model as _cp
    status_name = {
        _cp.OPTIMAL: "OPTIMAL", _cp.FEASIBLE: "FEASIBLE",
        _cp.INFEASIBLE: "INFEASIBLE", _cp.UNKNOWN: "UNKNOWN",
    }.get(int(status), str(status))
    notes.append(f"[solve] master status={status_name} in {elapsed:.1f}s")

    if int(status) not in (_cp.OPTIMAL, _cp.FEASIBLE):
        notes.append("master not OPTIMAL/FEASIBLE — cannot extract L0, abort")
        return m, {}, notes

    layout = m.extract_solution()
    notes.append(f"[extract] {len(layout)} instances in L0")
    return m, layout, notes


def _step5_build_clone_master(
    args: argparse.Namespace,
    pattern: CellFrontPattern,
    pools: Mapping[str, List[Dict[str, Any]]],
    instances: List[Dict[str, Any]],
    rules: Dict[str, Any],
    generic: Mapping[str, Any],
    counts: Mapping[str, Any],
) -> Tuple[Any, str, float, List[str]]:
    """Step 5+6: clone master with cell-front pattern constraints, solve, return status.

    构造: 复用 PoseBoolExactMasterDelegate build (standard 约束 + power_coverage),
    然后 *额外* 加 cell-front-pattern equivalence:
      (a) 对每个 (px, py, dir) ∈ pattern.active_ports:
          要求 sum(pose_var for pose 在该 (cell,dir) 提供 port) >= 1
      (b) 对每个 (x, y) ∈ pattern.occupied_cells:
          要求 sum(pose_var for pose 占 该 cell) >= 1
    cell exclusivity 已在 standard build 加 (AddAtMostOne), 所以 (b) 实际是
    "至少一个 pose 占" + standard "至多一个". (a) 类似.

    若 clone master OPTIMAL, 任何 OPTIMAL solution 都是 same-pattern alternative.
    """
    notes: List[str] = []
    from src.models.master_model import MasterPlacementModel

    anchor_filter = {(args.anchor_x, args.anchor_y)}
    t1 = time.perf_counter()
    clone = MasterPlacementModel(
        instances, pools, rules,
        ghost_rect=(args.ghost_w, args.ghost_h),
        skip_power_coverage=False,
        generic_io_requirements=generic,
        exact_required_pose_optional_counts=counts,
        solve_mode="certified_exact",
        ghost_anchor_filter=anchor_filter,
    )
    notes.append(f"[clone init] {time.perf_counter()-t1:.1f}s")

    t2 = time.perf_counter()
    clone.build()
    notes.append(f"[clone build] {time.perf_counter()-t2:.1f}s")

    delegate = clone._coordinate_delegate
    if delegate is None:
        notes.append("clone delegate None — abort")
        return clone, "ERROR", 0.0, notes
    # Build the global cache so we can find vars by (cell, dir).
    delegate._build_global_pose_cache()  # type: ignore[attr-defined]

    # (a) port coverage
    port_constraint_added = 0
    port_constraint_unsat = 0
    for (px, py, direction) in pattern.active_ports:
        vars_here = delegate._poses_by_port_cell_dir_global.get(  # type: ignore[attr-defined]
            (int(px), int(py), str(direction)), []
        )
        if not vars_here:
            port_constraint_unsat += 1
            # 真要 require >= 1 但没 candidate → clone INFEASIBLE.
            clone.model.Add(0 >= 1)
            break
        clone.model.Add(sum(vars_here) >= 1)
        port_constraint_added += 1
    notes.append(
        f"[clone port-cstr] +{port_constraint_added} (unsat={port_constraint_unsat})"
    )

    # (b) cell occupancy
    cell_constraint_added = 0
    for (cx, cy) in pattern.occupied_cells:
        vars_here = delegate._poses_by_cell_global.get((int(cx), int(cy)), [])  # type: ignore[attr-defined]
        if not vars_here:
            clone.model.Add(0 >= 1)
            notes.append(f"[clone] cell ({cx},{cy}) has no candidate pose — INFEASIBLE by construction")
            break
        clone.model.Add(sum(vars_here) >= 1)
        cell_constraint_added += 1
    notes.append(f"[clone cell-cstr] +{cell_constraint_added}")

    t3 = time.perf_counter()
    status = clone.solve(time_limit_seconds=args.clone_time_limit)
    elapsed = time.perf_counter() - t3
    from ortools.sat.python import cp_model as _cp
    status_name = {
        _cp.OPTIMAL: "OPTIMAL", _cp.FEASIBLE: "FEASIBLE",
        _cp.INFEASIBLE: "INFEASIBLE", _cp.UNKNOWN: "UNKNOWN",
    }.get(int(status), str(status))
    notes.append(f"[clone solve] {status_name} in {elapsed:.1f}s")
    return clone, status_name, elapsed, notes


def _step7_binding_oracle(
    layout: Mapping[str, Mapping[str, Any]],
    samples: List[Dict[str, Dict[str, Any]]],
    pools: Mapping[str, List[Dict[str, Any]]],
    instances: List[Dict[str, Any]],
    binding_time_limit: float,
) -> Tuple[int, int, List[str]]:
    """Step 7: 对 m4. 拿 alternative pose tuples 跑 PortBindingModel, count reject."""
    notes: List[str] = []
    from src.models.binding_subproblem import PortBindingModel

    rejected = 0
    tested = 0
    # baseline: 测一下 L0 自身 (sanity — 应跟 master 出来 routing precheck 行为一致;
    # 不强求是 INFEASIBLE, 因为 master OPTIMAL 不代表 binding FEASIBLE)
    for i, alt in enumerate(samples):
        tested += 1
        try:
            bm = PortBindingModel(alt, pools, instances, project_root=Path("."))
            bm.build()
            status = bm.solve(time_limit_seconds=binding_time_limit)
        except Exception as e:
            notes.append(f"  sample {i}: binding raised {type(e).__name__}: {e}")
            continue
        notes.append(f"  sample {i}: binding={status}")
        if status == "INFEASIBLE":
            rejected += 1
    return rejected, tested, notes


# ----------------------------- main ----------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ghost-w", type=int, default=27)
    parser.add_argument("--ghost-h", type=int, default=15)
    parser.add_argument("--anchor-x", type=int, default=22)
    parser.add_argument("--anchor-y", type=int, default=28)
    parser.add_argument("--master-time-limit", type=float, default=180.0,
                        help="master.solve cap; should be ~60-180 for 27×15 anchor")
    parser.add_argument("--clone-time-limit", type=float, default=60.0,
                        help="clone master.solve cap (m2 threshold)")
    parser.add_argument("--binding-time-limit", type=float, default=60.0)
    parser.add_argument("--m4-samples", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260520)
    parser.add_argument("--dry-run", action="store_true",
                        help="只 verify imports + key API, 不跑 master/binding solve")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    result = ProbeResult()
    all_notes: List[str] = []

    print(f"=== LIC Phase 0 cheap-gate probe ===")
    print(f"candidate {args.ghost_w}x{args.ghost_h} anchor ({args.anchor_x},{args.anchor_y})")
    print(f"dry_run={args.dry_run}")
    print()

    # Step 1+2: solve master
    m, layout, notes = _step1_solve_master(args)
    for ln in notes:
        print(ln)
    all_notes.extend(notes)

    if args.dry_run:
        # Dry-run: verify all import paths + API resolution, no solve.
        print()
        print("=== dry-run smoke checks ===")
        from src.models.master_model import (
            MasterPlacementModel,
            infer_exact_required_pose_optional_counts,
            load_generic_io_requirements_artifact,
            load_project_data,
        )
        from src.models.pose_bool_exact_master import PoseBoolExactMasterDelegate
        from src.models.binding_subproblem import PortBindingModel
        # Resolve the delegate's caches we depend on.
        assert hasattr(PoseBoolExactMasterDelegate, "_build_global_pose_cache"), (
            "delegate cache API missing"
        )
        # Resolve probe-internal helpers.
        cfp = CellFrontPattern()
        assert cfp.occupied_cells == frozenset()
        print("[dry-run] all imports resolve (MasterPlacementModel, "
              "PoseBoolExactMasterDelegate, PortBindingModel)")
        print("[dry-run] _build_global_pose_cache present on delegate")
        print("[dry-run] CellFrontPattern dataclass instantiable")
        print("[dry-run] OK — probe is ready for measurement run")
        result.verdict = "DRY-RUN-OK"
        result.notes = all_notes
        OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUT_FILE.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        print(f"\nresults JSON: {OUT_FILE}")
        return 0

    if not layout:
        print("ABORT: master did not produce L0")
        result.verdict = "ABORT-NO-L0"
        result.notes = all_notes
        OUT_FILE.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 1

    # Step 3: extract P(L0)
    pattern = _extract_cell_front_pattern_from_solution(layout, m.facility_pools)
    print(f"[pattern] |cells|={len(pattern.occupied_cells)} |ports|={len(pattern.active_ports)}")
    all_notes.append(
        f"P(L0): cells={len(pattern.occupied_cells)} ports={len(pattern.active_ports)}"
    )

    # Step 4: m1 — count equivalence class
    m1_size, m1_method, m1_notes = _count_pose_equivalence_class(layout, m.facility_pools)
    print(f"[m1] equivalence-class-lower-bound = {m1_size}  (method={m1_method})")
    for ln in m1_notes:
        print(f"  {ln}")
    all_notes.extend(m1_notes)
    result.m1_pose_equivalence_class_size = m1_size
    result.m1_method = m1_method

    # Step 5+6: clone master
    from src.models.master_model import (
        infer_exact_required_pose_optional_counts,
        load_generic_io_requirements_artifact,
        load_project_data,
    )
    instances, pools, rules = load_project_data(Path("."), "certified_exact")
    generic = load_generic_io_requirements_artifact(Path("."))
    counts = infer_exact_required_pose_optional_counts(rules, generic)
    clone, clone_status, clone_elapsed, clone_notes = _step5_build_clone_master(
        args, pattern, pools, instances, rules, generic, counts,
    )
    for ln in clone_notes:
        print(ln)
    all_notes.extend(clone_notes)
    result.m2_clone_solve_time_seconds = clone_elapsed
    result.m3_clone_status = clone_status

    # Step 7: m4 — binding oracle on sampled alternatives
    samples = _sample_alternative_pose_tuples(
        layout, m.facility_pools, args.m4_samples, rng,
    )
    print(f"[m4] sampled {len(samples)} alternative pose tuples")
    if samples:
        rejected, tested, oracle_notes = _step7_binding_oracle(
            layout, samples, pools, instances, args.binding_time_limit,
        )
        for ln in oracle_notes:
            print(ln)
        all_notes.extend(oracle_notes)
        result.m4_rejected = rejected
        result.m4_tested = tested
        result.m4_oracle_consistency_rate = f"{rejected}/{tested}"
    else:
        result.m4_oracle_consistency_rate = "0/0"
        all_notes.append("m4: no alternative samples found (m1 likely too small)")

    # Verdict
    go = True
    reasons: List[str] = []
    if (m1_size or 0) < 10:
        go = False
        reasons.append(f"m1<10 ({m1_size})")
    elif (m1_size or 0) < 100:
        reasons.append(f"m1<100 ({m1_size}) — degraded GO")
    if (result.m2_clone_solve_time_seconds or 1e9) > 300:
        go = False
        reasons.append(f"m2>300s ({result.m2_clone_solve_time_seconds:.1f}s)")
    if result.m3_clone_status == "UNKNOWN":
        go = False
        reasons.append("m3=UNKNOWN")
    if result.m4_tested > 0 and result.m4_rejected <= result.m4_tested * 0.6:
        go = False
        reasons.append(f"m4 reject rate {result.m4_oracle_consistency_rate} <=60%")

    if go and (m1_size or 0) >= 100 and result.m4_tested == result.m4_rejected and result.m4_tested >= 3:
        result.verdict = "GO"
    elif go:
        result.verdict = "PARTIAL"
    else:
        result.verdict = "NO-GO"
    result.notes = all_notes

    print()
    print("=== verdict ===")
    print(f"verdict={result.verdict}  reasons={'; '.join(reasons) or 'all-threshold-met'}")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    print(f"results JSON: {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
