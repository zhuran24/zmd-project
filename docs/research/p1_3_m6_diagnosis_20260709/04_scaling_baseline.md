# 诊断侦察·scaling_baseline（Fable，2026-07-09）

## Headline

规模阶梯完全可行：build_exact_core 接受任意实例子集（无 266 计数守卫、groups 动态推导），测试套件与生产之间是 6→266 实例的完全空档；已给出可直接执行的三臂设计（子集阶梯 25-266 × 600/1800s + 供电覆盖开关 + 266 全量单 anchor），可区分「纯规模相变 / 编码常数 / anchor 析取放大 / 打包紧度」四种病因。

## 硬事实

- 测试套件里所有真调 master solve 的测试全是玩具规模：test_master.py 的模型构造器用 1-6 个合成实例、每池 1-3 个 pose、格盘最小到 N×1（如 _build_exact_ghost_warm_start_model 的 miner 实例 + grid_width×1 盘），solve 都限 5s 且秒过；被认证链慢测试用的 toy project 只有 1 个 1×1 设施放 2×1 盘。测试与生产之间存在 6→266 实例的完全空档，无任何中等规模数据点
  - 出处: src/tests/test_master.py:171-213,1864,1949,2000; src/tests/test_exact_contract.py:113-153
- build_exact_core 接受任意 instances 序列，无 266 计数守卫；实例校验只查每项 schema（id 唯一/is_mandatory/bound_type），不查数量；mandatory groups 完全由传入实例动态推导——内存构造子集模型合法且结构自洽
  - 出处: src/models/master_model.py:2620-2646（build_exact_core 签名）、2161-2181（_validate_mandatory_exact_instances_payload 无计数检查）、3121-3147（_build_mandatory_groups）
- ExactSearchSession.create = 读冻结工件 + load_project_data_from_texts + load_generic_io_requirements + build_exact_core 的薄封装，本身无过滤钩子；但所有输入都有文件路径版 loader（load_project_data / load_generic_io_requirements / load_wireless_sink_generic_input_slots），可在不碰冻结文件的情况下复刻同一构造路径并在 build 前切片
  - 出处: src/search/benders_loop.py:2201-2280; src/models/master_model.py:2221-2242; src/models/binding_subproblem.py:187-233,97-148
- from_exact_core 暴露 ghost_anchor_filter 参数（None=全 anchor、子集=只建子集、空集=立即 infeasible），源码注释明说是『A 方案 anchor slicing PoC——单 anchor master 量 RAM』，有单测覆盖；certified 会话只封锁其 env 路线（EXACT_MASTER_GHOST_ANCHOR_FILTER 在 unsafe map），直接传参的测量路径与 m5_cell_runner 同性质合法
  - 出处: src/models/master_model.py:2714-2722,2321-2325; src/tests/test_ghost_anchor_filter.py:1-9; src/search/benders_loop.py:2290-2302
- 266 实例构成：46 boundary_storage_port + 132 manufacturing_3x3 + 49 manufacturing_5x5 + 38 manufacturing_6x4 + 1 protocol_core；候选池规模 manufacturing_3x3=17408 / 5x5=16368 / 6x4=16380 / protocol_core=6728 / power_pole=4761 / protocol_storage_box=4624 / boundary_storage_port=136 pose
  - 出处: data/preprocessed/mandatory_exact_instances.json; data/preprocessed/candidate_placements.json
- 必选 optional 下界由全局 generic_io_requirements 推导（required_generic_inputs 总共只有 2 个 slot → protocol_storage_box 需求 ≈1 个），与实例子集无关——子集阶梯中该项恒定且极小，不影响判读
  - 出处: src/models/master_model.py:2014-2039; data/preprocessed/generic_io_requirements.json
- 266 实例冷启动基线已存在且可对表：6×6 ghost、automatic/w12/probing1/symmetry1/无hint/1800s → UNKNOWN、19.35M branches；同配置带 hint 的模型 response 报 booleans=1,549,068 / integers=1,327,462（≈266×4900 量级，提示变量主体随实例数线性）；master overlay 建模 18.0s、session 建 31.3s
  - 出处: docs/research/p1_3_m5_convergence_20260708/results_scan/cell_g6x6_q5d_coldstart.json; cell_g6x6_linux_p4cfg_1800.json（last_solve.response_stats）
- skip_power_coverage 是 build_exact_core 的一等参数（供电覆盖约束整族开关）——可作为约束族归因的合法诊断臂
  - 出处: src/models/master_model.py:2626,2639
- solve() 在 env 未设时强制 probing_level>=3、symmetry_level>=3（presolve 税根源），EXACT_MASTER_SEARCH_BRANCHING/PROBING_LEVEL/SYMMETRY_LEVEL 均为合法 env 旋钮，直接 master.solve() 不经过 benders_loop 的 deny-unknown 扫描但仍按同名 env 生效
  - 出处: src/models/master_model.py:11498-11534,11471-11487

## 实验设计

## 规模阶梯实验（可行，三臂设计；总耗时约 2.5-4h 串行）

### 前提与纪律
- 全程只造内存模型，不碰 frozen 工件文件、不写 data/checkpoints、data/solutions（脚本只写 --out JSON）。
- 严格串行（一次只跑一个 master solve，47.7GB 双并发 OOM 前科）。硅脂期机器建议换硅脂后跑；若提前跑：nohup + 每 rung 间 sleep 120，热重启后先清 `__pycache__`（SOP 已入记忆）。
- 配置对齐既有 266 冷启动基线 cell_g6x6_q5d_coldstart.json（automatic / w12 / probing1 / symmetry1 / 无 hint / mem cap 28000），使 266 档可与现有数据对表。

### 第一步：创建脚本 `docs/research/p1_3_m5_convergence_20260708/m5_scale_ladder_runner.py`

```python
"""M5 scale-ladder runner: in-memory instance-subset master-only solve (诊断用, 非认证路径)."""
from __future__ import annotations
import argparse, collections, json, os, sys, time
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

def stratified_subset(instances, n):
    if n >= len(instances):
        return list(instances)
    groups = collections.defaultdict(list)
    for inst in instances:
        groups[(str(inst["facility_type"]), str(inst.get("operation_type", "")))].append(inst)
    for members in groups.values():
        members.sort(key=lambda i: str(i["instance_id"]))
    total = len(instances)
    quotas, remainders, assigned = {}, [], 0
    for key in sorted(groups):
        exact = len(groups[key]) * n / total
        q = int(exact)
        quotas[key], assigned = q, assigned + q
        remainders.append((-(exact - q), key))
    remainders.sort()
    for _, key in remainders[: n - assigned]:
        quotas[key] += 1
    pc = ("protocol_core", "protocol_core")   # 必保 protocol_core（全局唯一）
    if pc in groups and quotas.get(pc, 0) == 0:
        quotas[pc] = 1
        big = max(quotas, key=lambda k: (quotas[k], k))
        quotas[big] -= 1
    subset = []
    for key in sorted(groups):
        subset.extend(groups[key][: quotas[key]])
    return subset

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-instances", type=int, required=True)
    ap.add_argument("--ghost-w", type=int, default=6)
    ap.add_argument("--ghost-h", type=int, default=6)
    ap.add_argument("--master-seconds", type=float, default=600.0)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--branching", default="automatic")
    ap.add_argument("--probing-level", type=int, default=1)
    ap.add_argument("--symmetry-level", type=int, default=1)
    ap.add_argument("--max-memory-mb", type=int, default=28000)
    ap.add_argument("--skip-power-coverage", action="store_true")  # Arm P
    ap.add_argument("--anchor-filter", default=None, help="'x,y;x,y' -> ghost_anchor_filter")  # Arm A
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
    os.environ["EXACT_CP_SAT_WORKERS"] = str(args.workers)
    os.environ["EXACT_MASTER_SEARCH_BRANCHING"] = args.branching
    os.environ["EXACT_MASTER_CP_MODEL_PROBING_LEVEL"] = str(args.probing_level)
    os.environ["EXACT_MASTER_SYMMETRY_LEVEL"] = str(args.symmetry_level)
    os.environ["EXACT_SUBPROBLEM_MAX_MEMORY_MB"] = str(args.max_memory_mb)

    from src.models.master_model import MasterPlacementModel, load_project_data
    from src.models.binding_subproblem import (
        load_generic_io_requirements, load_wireless_sink_generic_input_slots)

    instances, pools, rules = load_project_data(PROJECT_ROOT, solve_mode="certified_exact")
    gio = load_generic_io_requirements(project_root=PROJECT_ROOT)
    wsl = (load_wireless_sink_generic_input_slots(project_root=PROJECT_ROOT)
           if gio.get("required_generic_inputs") else None)
    subset = stratified_subset(instances, args.n_instances)
    dims = {t: d["dimensions"] for t, d in rules["facility_templates"].items()}
    occ = sum(dims[i["facility_type"]]["w"] * dims[i["facility_type"]]["h"] for i in subset)

    result = {"n_requested": args.n_instances, "n_actual": len(subset),
              "occupied_cells_by_template_dims": occ,
              "group_counts": dict(collections.Counter(
                  f'{i["facility_type"]}::{i.get("operation_type","")}' for i in subset)),
              "ghost_rect": [args.ghost_w, args.ghost_h],
              "config": {k: getattr(args, k) for k in
                         ("master_seconds", "workers", "branching", "probing_level",
                          "symmetry_level", "max_memory_mb", "skip_power_coverage",
                          "anchor_filter")}}

    t0 = time.perf_counter()
    core = MasterPlacementModel.build_exact_core(
        subset, pools, rules,
        generic_io_requirements=gio,
        wireless_sink_generic_input_slots=wsl,
        skip_power_coverage=args.skip_power_coverage)
    result["core_build_seconds"] = round(time.perf_counter() - t0, 3)
    result["packaging_profile"] = {
        k: v for k, v in dict(core.build_stats.get("exact_core_packaging_profile", {})).items()
        if isinstance(v, (str, int, float, bool, type(None)))}  # proto_variable_count / proto_constraint_count

    anchor_filter = None
    if args.anchor_filter:
        anchor_filter = {tuple(int(v) for v in tok.split(","))
                         for tok in args.anchor_filter.split(";") if tok.strip()}
    t1 = time.perf_counter()
    master = MasterPlacementModel.from_exact_core(
        core, ghost_rect=(args.ghost_w, args.ghost_h), ghost_anchor_filter=anchor_filter)
    result["overlay_build_seconds"] = round(time.perf_counter() - t1, 3)

    t2 = time.perf_counter()
    try:
        status = master.solve(time_limit_seconds=args.master_seconds)  # 冷启动, 无 hint
        result["solve_status_int"] = int(status)
    except Exception as exc:  # noqa: BLE001
        result["exception"] = f"{type(exc).__name__}: {exc}"
    result["solve_wall_seconds"] = round(time.perf_counter() - t2, 3)
    ls = (master.build_stats or {}).get("last_solve")
    if isinstance(ls, dict):
        result["last_solve"] = {k: v for k, v in ls.items()
                                if isinstance(v, (str, int, float, bool, type(None)))}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"n": len(subset), "status": (result.get("last_solve") or {}).get("status"),
                      "wall": result["solve_wall_seconds"]}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

### 第二步：Arm S 主阶梯（ghost 6×6, 每档 600s, N≥200 用 1800s）

```bash
cd /home/zhuran24/zmd-pj
D=docs/research/p1_3_m5_convergence_20260708
for N in 25 50 100 150; do
  python $D/m5_scale_ladder_runner.py --n-instances $N --master-seconds 600 \
    --out $D/results_scan/ladder_g6x6_n${N}_600.json \
    >> $D/results_scan/ladder_progress.log 2>&1
  sleep 120
done
for N in 200 233 266; do
  python $D/m5_scale_ladder_runner.py --n-instances $N --master-seconds 1800 \
    --out $D/results_scan/ladder_g6x6_n${N}_1800.json \
    >> $D/results_scan/ladder_progress.log 2>&1
  sleep 120
done
```
预计耗时：4×(600s+build) + 3×(1800s+build) + 冷却 ≈ 2h40m。266 档同时校验「直接 solve 路径 ≈ q5d 控制器路径」（对表 cell_g6x6_q5d_coldstart.json：UNKNOWN / 19.35M branches）。

### 第三步（条件触发）：
- **Arm P（供电覆盖开关）**：在第一个失败档 N* 重跑加 `--skip-power-coverage`（600s）。
- **Arm A（anchor 析取消除, N=266）**：`--anchor-filter "10,10"` 等 4 个分散 anchor 各跑 600s（更优：从 probes/ 里 ghost-aware 重建成功的 161 个 anchor 记录中取 4 个已知可放 6×6 洞的 anchor）。

### 判读标准
1. **先看 last_solve.branches**：branches==0 ⇒ 该档 presolve-stuck，结果不可判读 ⇒ 该档加 `EXACT_MASTER_CP_MODEL_PRESOLVE=0`（脚本可加 --presolve 0 转发）重跑后再判。
2. **N=25/50 就 UNKNOWN（且 branches>0）** ⇒ 病因不是规模而是编码常数/结构 ⇒ 跑 Arm P：若 skip_power_coverage 后秒解 ⇒ 供电覆盖编码是元凶；仍不解 ⇒ 坐标/no_overlap 打包编码本身。
3. **存在 N1 解出、N2 失败**（预期形态）⇒ 规模墙定位在 (N1, N2]；报告 wall-time-to-first-solution 曲线 + proto_variable_count 曲线：变量数随 N 线性但求解时间在墙处爆炸 ⇒ 真组合相变（纯规模病因成立）；随后跑 Arm A：266+单 anchor 若 600s 内解出 ⇒ anchor 析取（4225 选一）是把相变点推过 266 的主放大器，改进方向=anchor 切片/分区（v8 patch 复活）；仍不解 ⇒ 72% 填充率打包本身就是墙，改进方向=warm-start 修复/模型加固。
4. **全档都解出（含 266）** ⇒ 与 q5d 矛盾 ⇒ 逐项 diff last_solve 参数（怀疑 subsolver 过滤/residual hint 差异），先复跑 266 档 1800s 再下结论。

## 风险

- 混淆变量：砍实例同时降低了棋盘填充率（72%→N×~13格/4900），子集档解出不能单独归因『规模小』——设计里靠 Arm A（266 全量+单 anchor）和已有 ghost 尺寸轴数据（6×6~40×40 全 UNKNOWN）做紧度解耦，判读时必须三臂合看
- 直接 master.solve() 与 LBBDController 路径存在细微差异（无控制器 bookkeeping/hint 管线）；266 档必须先对表 q5d 基线（UNKNOWN/19.35M branches），若行为明显不一致则全阶梯数据作废重查
- 高 N 档 600s 可能被 presolve 吃光（Windows p1cfg 前科：probing1 在 600s 内 branches=0）——判读铁律：branches==0 的档不可判读，需按计划的 escalation 规则重跑，别把 presolve-stuck 误读成规模墙
- 本机硅脂期热重启风险（两晚 3 次杀实验前科）：串行+冷却+nohup，热重启后必须清 __pycache__ 再续，否则又出假崩 gremlin
- prod-scale master 一次只能跑一个（47.7GB 双并发 OOM 双杀实测）——阶梯必须严格串行
- 子集模型是诊断用非认证路径：结论只能反哺病因定位与生产复核方向，任何子集结果不得升格为对 266 全量模型可行性/最优性的证明性断言
- stratified 子集只是『代表性混合』的一种取法；若病因对特定设施族敏感（如 46 个边界口挤边界环），比例采样可能低估该族贡献——发现相变后值得补单族消融档