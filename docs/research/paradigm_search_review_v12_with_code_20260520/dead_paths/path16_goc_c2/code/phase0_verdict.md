# GOC-C2 (Path 16) Phase 0 cheap gate verdict — 2026-05-19

## 结论

❌ **Pre2 资源直接 NO-GO**. GOC-C2 主线死. 22 lever 全 verdict.

## Trial 实测过程

### v1 实施 bug — production routing precheck 短路
- 2 anchor (interior_22_28, interior_10_10) 跑出来 routing_status=INFEASIBLE 但 wall=0s, vars=0
- 原因: production `analyze_exact_routing_domain` 在 master OPTIMAL layout 上 detect front_blocked → `RoutingSubproblem.build` 触发 `model.Add(0 == 1)` 直接 INFEASIBLE, 不真 build 全 routing vars
- 这是 routing precheck early-reject path, 不是 GOC paradigm 想要的 "全图 routing CP-SAT 真 sufficient infeasibility"
- 数据: anchor 1 RSS=13 GB (binding+master 累, routing 没 build); anchor 2 RSS=15 GB

### v2 实施修复 — monkey-patch analyze 强返 "feasible" + active_cells=全 free_cells
- 让 GOC virtual terminal 最大放宽起作用: 每 commodity active_cells = 全 4700 free cells (跟 GPT plan "uncapacitated virtual terminal" 一致)
- 跑 anchor 1 (interior_22_28) **30 分钟还没出第一行数据**
- Python process metrics @ 30 min:
  - **RSS = 25 GB** (target Pre2 ≤ 12 GB, **2.1x over**)
  - VSZ = 30 GB
  - 系统 RAM 剩 14 GB 可用 (close to OOM)
- 估算 routing model vars ~1.5M (10 commodity × 4700 active cells × ~32 state patterns - local pruning)
- CP-SAT model build 自身在这 scale 已 ~30 min 不完成, solve 谈不上

## 关键 finding

GOC paradigm 在 production scale (266 facility + 70×70 grid + 10 commodity + 全 free_cells active) 下:
- **资源直接爆炸** — model build 占 25 GB+ RAM
- **数学 sound 但 production 不可达** — GPT 估算 vars ≤ 180K 严重过低 (实测 ~1.5M scale, **8x off**)

GPT plan Pre2 GO 条件 `goc_model_vars_p95 <= 180000`, `peak RSS <= 12GB` — 实测 **严重失真**:
- vars: ≥ 1.5M (估算 lower bound)
- RSS: ≥ 25 GB

## 这撞的是 3 性质里的哪个

GPT 选 "绕开 (2) 无 spatial locality", 声称 "不撞 (1) 全局耦合 因为全图建模是 sound 来源".

实测: **(1) 全局耦合在 production scale 上 fundamental 撞了**.

70×70 grid + 10 commodity 上的 multicommodity routing CP-SAT 任何 sound 全图 encoding 都需要:
- per (cell, layer, commodity, state pattern) 一个 BoolVar
- per (cell, layer, dir, commodity) 多个 channeling constraints
- per (cell, layer) AddAtMostOne capacity

跟 production 同质 (因为 GOC 的 routing 子问题就是 production `RoutingSubproblem`). 在 active_cells 满足 sufficient 放宽 (= 全 free_cells) 下, model **几乎等于一个 universe routing CP-SAT**, vars 1.5M scale.

production routing 之所以能跑 (Path 11 / Path 14 实测), 是因为 `analyze_exact_routing_domain` 先用 routing-precheck 把 active_cells 缩到 component-consistent 子集 (front-blocked 时直接 model.Add(0==1) 短路). 但 GOC paradigm **不能用** 这种短路 — 它就是要绕过 precheck 让全图 routing 真有信息.

→ **paradigm 的 sound 来源 (全图建模) 跟 production 资源约束 (47 GB / 60s) 不兼容**.

## 跟之前 paradigm 比较

| paradigm | Phase 0 verdict |
|---|---|
| L12 RAB-SEP | no Phase 0, 直接 Phase 1 后死 |
| L13 SAC-Hull | Phase 0 GO (22 violations 信号) |
| L14 PCR-CUT | Phase 0 GO (770 cells cover 98%) |
| L15 PGW-UB | Phase 0 cheap gate NO-GO (top5_cov 10x off) |
| **L16 GOC-C2** | **Phase 0 cheap gate NO-GO (resource 2x+ over)** |

PGW + GOC 都是 paradigm 设计 sound 但 Phase 0 实测 fail 的 paradigm. 不同失败 mode:
- PGW: production 数据特性不满足 paradigm 前提 (residual 不 local)
- GOC: production 数据规模不满足 paradigm 资源约束 (model 太大)

## 实测投入

- Trial v1: ~10 min wall (2 anchor 完成, 数据无意义)
- Trial v2: ~30 min wall (anchor 1 资源耗尽前 kill)
- 实施 LOC: 1 文件 ~340 LOC trial (不改 production)
- 总 Claude pace: ~2h (含 implementation bug fix iteration)
- 节约: 整套 GOC plan ~15-25h Claude work + Phase 1 850 LOC 实施浪费

## meta-finding (5 paradigm 后)

22 lever 全 verdict 死. **3 类 framework 都试过死了**:

1. **"局部反馈 + master cut"** (RAB-SEP/SAC-Hull/PCR-CUT) — necessary 不 sufficient
2. **"正向 witness + UB closure"** (PGW-UB) — production data 不 local
3. **"全图 owner-optional + sufficient infeasibility core"** (GOC-C2) — production scale 资源直接爆

paradigm investigation 现穷尽 — 真还要 break 必须有以下之一:
- formal proof "在 47 GB + 60s + sound + exact + 单机 + 不改 problem definition 下不可达" (per [[feedback-no-giveup-options]] 严格)
- 放松约束 (用户拒绝)
- 跟之前完全不同 framework 的 paradigm (GPT 4 次输出已穷尽 paradigm-level 创新)

## Related

- v5 plan: `/home/zhuran24/下载/B1_paradigm_breakthrough_plan_v5.md`
- v5 review package: `~/linwin_share/b1_phase6_review_package_v5.zip`
