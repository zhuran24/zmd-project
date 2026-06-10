---
name: goc-phase0-verdict
description: GOC-C2 (Path 16) Phase 0 cheap gate ❌ NO-GO 2026-05-19. RSS 25 GB > 12 GB target 2x+; CP-SAT model 全图 owner-optional + virtual terminal 放宽下 vars ~1.5M 资源直接爆. GPT v5 plan Pre2 估算严重失真. 第 22 lever 死. 3 大类 paradigm framework 都试过死了
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

# GOC-C2 (Path 16) Phase 0 verdict

## 终态

❌ **Pre2 资源前提直接 NO-GO**. paradigm 数学 sound 但 production scale 资源不可达.

GPT v5 plan 选路 2 (新 paradigm), 给出 **GOC-C2 (Global Optional-owner C2 Core)** —
全图 owner-optional relaxation + virtual terminal + assumption core 抽 master
combinatorial nogood cut. paradigm 设计绕开 (2) 无 spatial locality, 全图 core
可跨整张 70×70 grid 分散.

## Trial 两轮

### v1 实施 bug
production routing precheck 在 master OPTIMAL layout 上 detect front_blocked,
触发 `model.Add(0 == 1)` 短路, 没真 build 全 routing vars. routing_status=
INFEASIBLE 但 wall=0s vars=0 — paradigm 想验的"全图 routing CP-SAT 真 INFEASIBLE"
完全没 test. Kill.

### v2 monkey-patch analyze 强返 feasible + active_cells = 全 free_cells
模拟 GOC virtual terminal 最大放宽. anchor 1 跑 30 min 未出数据:
- Python process RSS=**25 GB** (target Pre2 ≤ 12 GB, **2.1x over**)
- VSZ=30 GB, 系统 RAM 剩 14 GB 可用
- 估算 routing vars ~1.5M (10 commodity × 4700 active cells × ~32 state patterns)
- CP-SAT model build 自身在这 scale 30 min 不完成

Kill, RAM 恢复 39 GB. Pre2 资源前提直接 fail.

## GPT plan 估算偏差

| metric | GPT plan target | 实测 | 偏差 |
|---|---|---|---|
| routing_vars_p95 | ≤ 180,000 | ~1,500,000 (estimate) | **8x off** |
| peak RSS | ≤ 12 GB | ≥ 25 GB | **2.1x over** |
| separator_wall_p95 | ≤ 25s | 30 min build 未完成 | TIMEOUT |

paradigm 在 toy data 上 sound, 但 production scale (266 facility + 70×70 grid +
10 commodity) 上资源直接爆.

## 撞的是哪个性质

GPT 声称 "绕开 (2) 无 spatial locality" + "不撞 (1) 全局耦合 因为全图建模是 sound 来源".

实测撞的就是 **GPT 声称不撞的 (1) 全局耦合**. 全图 multicommodity routing CP-SAT
任何 sound encoding 都需 per (cell, layer, commodity, pattern) BoolVar, vars 1.5M
scale 直接撞 47 GB cap.

production routing 之所以能跑 (Path 11/14 实测) 是因为 `analyze_exact_routing_domain`
用 routing-precheck 把 active_cells 缩到 component-consistent 子集 + front_blocked
时直接短路. GOC paradigm **不能用**这种短路 — 它就要绕过 precheck 让全图 routing
真有信息. 这是 paradigm 设计 vs 资源约束的 fundamental 矛盾.

## 5 paradigm 后的 meta-finding

22 lever 全 verdict 死. **3 大类 paradigm framework 都试过死了**:

1. **"局部反馈 + master cut"** (RAB-SEP / SAC-Hull / PCR-CUT)
   - 设计完全不同抽象层 (binding-side / corridor capacity / patch belt CP-SAT)
   - 全 端到端 land ✅, 全 breakthrough ❌
   - root: necessary 不 sufficient

2. **"正向 witness + UB closure"** (PGW-UB)
   - Phase 0 cheap gate 直接 fail (P0.3 0/7 anchor)
   - root: production data 没 spatial locality, LNS 失效

3. **"全图 owner-optional + sufficient infeasibility core"** (GOC-C2)
   - Phase 0 cheap gate 直接 fail (Pre2 资源 2x over)
   - root: production scale 全图 model vars 1.5M scale > 资源 cap

PGW + GOC 都 Phase 0 失败但 different failure mode:
- PGW: production data 不满足 paradigm 数据特性
- GOC: production data 不满足 paradigm 资源约束

## 实测投入

- Trial v1 + v2 总 wall: ~40 min
- 实施 LOC: 1 文件 ~340 LOC
- Claude pace: ~2h (含 bug fix iteration)
- 节约: 整套 GOC plan ~15-25h Claude + Phase 1 850 LOC 浪费
- commit `a4b8341`

## paradigm investigation 现穷尽

真还要 break 必须有以下之一:
- **formal proof** "在 47 GB + 60s + sound + exact + 单机 + 不改 problem definition
  下不可达" — 5 paradigm fail 是 strong engineering evidence 但不是 formal
  reduction / proof system lower bound / resource inequality
- **放松约束** — 用户拒绝 (L11 牺牲严格性 / 分布式 / ε-certified / 不严格 exact)
- **跟之前完全不同 framework 的 paradigm** — GPT 5 次输出 (v1-v5) 已穷尽 paradigm-level 创新

## Related

- [[pgw-phase0-verdict]] — Path 15 PGW Phase 0 NO-GO
- [[pcr-cut-phase5-verdict]] — Path 14 verdict
- [[paradigm-session-2026-05-18-19]] — 整 session 上下文
- [[paradigm-phase0-cheap-gate]] — cheap gate workflow 现已验证 7 次有效
- v5 plan: /home/zhuran24/下载/B1_paradigm_breakthrough_plan_v5.md
- review package: ~/linwin_share/b1_phase6_review_package_v5.zip
