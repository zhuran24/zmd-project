"""牌 D 侦察：front-clear 松弛模型 → OPB（伪布尔）编码器（research-grade）。

目标：把 round-4 的 front_clear-lifted 松弛 M（mandatory 装箱 + ghost +
front-clear 计数）编成 OPB，供带 VeriPB 证明日志的 PB 求解器
（RoundingSat/Exact）跑 UNSAT——若 UNSAT 且证明过校验，即 6×6 锚点
上界证书的机器可查形态（soundness 义务另行对抗审查）。

## 松弛方向纪律（证书 soundness 的命门，与 witness 构造器相反）

模型必须是真问题的**松弛**（可行域 ⊇ 真可行域）——过约束会产假 UNSAT：
- demand 未知（非 profiled op：boundary/core）的件：**不加 front-clear
  约束**（加了=更严=unsound）；
- front 格共享天然允许（occ[f]=0 可同时服务多个 pose 的须）；
- 供电/binding 完整签约/routing 均不编码（松弛方向安全）；
- demand 用 SSOT `routing_visible_port_demands`（与 lift/RAB 同源）。

## 编码

- x[p]∈{0,1}：pose p 被某件占用（同模板件匿名——组计数消对称）；
- occ[c] = Σ_{p covers c} x[p]（等式；occ∈{0,1} 自动蕴含不重叠 ≤1）；
- Σ_{p∈tpl} x[p] = count_tpl（各模板 mandatory 件数）；
- front-clear：demand d>0 的侧：|F| - Σ_{f∈F} occ[f] ≥ d·x[p]
  （F=界内 front 格；|F|<d 时 x[p]=0）；
- ghost one-hot：Σ g[a]=1；g[a]+occ[c] ≤ 1 ∀c∈rect(a)。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.io.strict_json import load_strict_json  # noqa: E402
from src.models.binding_subproblem import load_generic_io_requirements  # noqa: E402
from src.models.port_binding import (  # noqa: E402
    routing_free_sink_commodities_from_generic_inputs,
    routing_visible_port_demands,
    supports_exact_pose_level_binding,
)
from src.models.routing_binding_context import _DIR_DELTA  # noqa: E402
from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES  # noqa: E402

GRID = 70


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ghost-w", type=int, default=6)
    ap.add_argument("--ghost-h", type=int, default=6)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--meta-out", type=Path, default=None)
    args = ap.parse_args()

    t0 = time.perf_counter()
    payload = load_strict_json(
        PROJECT_ROOT / "data/preprocessed/candidate_placements.json")
    pools = dict(payload["facility_pools"])
    instances = load_strict_json(
        PROJECT_ROOT / "data/preprocessed/mandatory_exact_instances.json")
    io_req = load_generic_io_requirements(project_root=PROJECT_ROOT)
    rfsc = routing_free_sink_commodities_from_generic_inputs(
        io_req["required_generic_inputs"])

    # 模板 → mandatory 件数；op → demand（组内 op 必须同 demand 才能用组计数
    # + per-pose front 约束：本编码把 front 约束绑在 pose 上，demand 取
    # 「该模板全部 mandatory 件的 demand 最小值」——更松（sound 方向），
    # 且若模板内 demand 不一致会在 meta 里如实记录。
    count_by_tpl: dict[str, int] = defaultdict(int)
    demands_by_tpl: dict[str, list] = defaultdict(list)
    for inst in instances:
        tpl = str(inst["facility_type"])
        count_by_tpl[tpl] += 1
        op = str(inst["operation_type"])
        dem = None
        try:
            if op in OPERATION_PORT_PROFILES and \
                    supports_exact_pose_level_binding(op):
                dem = routing_visible_port_demands(op, rfsc)
        except ValueError:
            dem = None
        demands_by_tpl[tpl].append(dem)

    tpl_front_demand: dict[str, tuple[int, int] | None] = {}
    for tpl, dems in demands_by_tpl.items():
        known = [d for d in dems if d is not None]
        if not known or len(known) < len(dems):
            # 模板内存在 demand 未知件 → 整模板不加 front 约束（sound：更松）
            tpl_front_demand[tpl] = None
            continue
        tpl_front_demand[tpl] = (min(d[0] for d in known),
                                 min(d[1] for d in known))

    # 变量编号
    var_of: dict[str, int] = {}

    def new_var(name: str) -> int:
        var_of[name] = len(var_of) + 1
        return var_of[name]

    pose_vars: dict[tuple[str, int], int] = {}
    cover: dict[tuple[int, int], list[int]] = defaultdict(list)
    fronts_of_pose: dict[int, tuple[list, list, int, int]] = {}
    forced_zero: list[int] = []

    for tpl, pool in pools.items():
        if count_by_tpl.get(tpl, 0) == 0:
            continue
        dem = tpl_front_demand.get(tpl)
        for idx, pose in enumerate(pool):
            v = new_var(f"x_{tpl}_{idx}")
            pose_vars[(tpl, idx)] = v
            for c in pose.get("occupied_cells") or []:
                cover[(int(c[0]), int(c[1]))].append(v)
            if dem is None:
                continue
            sides = []
            for f in ("input_port_cells", "output_port_cells"):
                fs = []
                for q in pose.get(f) or []:
                    dx, dy = _DIR_DELTA[str(q["dir"])]
                    fx, fy = int(q["x"]) + dx, int(q["y"]) + dy
                    if 0 <= fx < GRID and 0 <= fy < GRID:
                        fs.append((fx, fy))
                sides.append(fs)
            ni, no = dem
            if len(sides[0]) < ni or len(sides[1]) < no:
                forced_zero.append(v)
                continue
            fronts_of_pose[v] = (sides[0], sides[1], ni, no)

    occ_vars: dict[tuple[int, int], int] = {}
    for c in sorted(cover):
        occ_vars[c] = new_var(f"occ_{c[0]}_{c[1]}")

    gw, gh = args.ghost_w, args.ghost_h
    ghost_vars: dict[tuple[int, int], int] = {}
    for ax in range(0, GRID - gw + 1):
        for ay in range(0, GRID - gh + 1):
            ghost_vars[(ax, ay)] = new_var(f"g_{ax}_{ay}")

    # 约束落 OPB
    lines: list[str] = []

    def term(coef: int, var: int) -> str:
        return f"{'+' if coef >= 0 else ''}{coef} x{var}"

    # 1) 组计数
    for tpl, n in sorted(count_by_tpl.items()):
        ts = " ".join(term(1, pose_vars[(tpl, i)])
                      for i in range(len(pools[tpl])))
        lines.append(f"{ts} = {n} ;")

    # 2) occ 通道等式（蕴含不重叠）
    for c, vs in sorted(cover.items()):
        ts = " ".join(term(1, v) for v in vs)
        lines.append(f"{ts} {term(-1, occ_vars[c])} = 0 ;")

    # 3) forced zero
    for v in forced_zero:
        lines.append(f"{term(1, v)} = 0 ;")

    # 4) front-clear：|F| - Σocc[f] ≥ d·x  ⟺  -d·x - Σocc[f] ≥ d - |F|
    n_front = 0
    for v, (fin, fout, ni, no) in fronts_of_pose.items():
        for fs, d in ((fin, ni), (fout, no)):
            if d <= 0:
                continue
            occs = [occ_vars[f] for f in fs if f in occ_vars]
            # 不在 cover 里的 front 格永远无 body（无 pose 覆盖）——恒空，
            # 从计数里当常量 0 处理：有效 |F| 不变，Σocc 只加已建格
            ts = " ".join([term(-d, v)] + [term(-1, o) for o in occs])
            lines.append(f"{ts} >= {d - len(fs)} ;")
            n_front += 1

    # 5) ghost one-hot + 排斥
    ts = " ".join(term(1, g) for g in ghost_vars.values())
    lines.append(f"{ts} = 1 ;")
    n_ghost_excl = 0
    for (ax, ay), g in ghost_vars.items():
        for cx in range(ax, ax + gw):
            for cy in range(ay, ay + gh):
                o = occ_vars.get((cx, cy))
                if o is not None:
                    lines.append(f"{term(-1, g)} {term(-1, o)} >= -1 ;")
                    n_ghost_excl += 1

    # 开 proof 时 RoundingSat 要求完整 PB Competition header：
    # #equal= 等式行数、intsize= 系数/度数最大位宽（64 保守安全）
    n_equal = sum(1 for ln in lines if " = " in ln)
    header = (f"* #variable= {len(var_of)} #constraint= {len(lines)} "
              f"#equal= {n_equal} intsize= 64\n"
              f"* front_clear_relaxation ghost={gw}x{gh} grid={GRID} "
              f"generated_by=pb_encoder_v1\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="ascii") as fh:
        fh.write(header)
        fh.write("\n".join(lines))
        fh.write("\n")

    meta = {
        "harness": "pb_encoder_v1",
        "ghost": [gw, gh],
        "n_vars": len(var_of),
        "n_constraints": len(lines),
        "n_pose_vars": len(pose_vars),
        "n_occ_vars": len(occ_vars),
        "n_ghost_vars": len(ghost_vars),
        "n_front_constraints": n_front,
        "n_ghost_exclusions": n_ghost_excl,
        "n_forced_zero": len(forced_zero),
        "tpl_counts": dict(count_by_tpl),
        "tpl_front_demand": {k: (list(v) if v else None)
                             for k, v in tpl_front_demand.items()},
        "soundness_notes": [
            "demand 未知/不一致模板不加 front 约束（松弛方向安全）",
            "front 共享天然允许（occ 通道）",
            "供电/binding/routing 未编码（松弛）",
            "demand 取模板内最小（更松）",
            "忠实性（不比真问题更严）待对抗审查——今晚仅工具链侦察",
        ],
        "encode_wall_seconds": round(time.perf_counter() - t0, 2),
    }
    meta_path = args.meta_out or args.out.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    print(json.dumps({k: meta[k] for k in
                      ("n_vars", "n_constraints", "n_front_constraints",
                       "n_forced_zero", "encode_wall_seconds")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
