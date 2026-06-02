---
name: paradigm-death-timeline-27-lever
description: "27 lever consolidated death timeline (Day 16c-2 补做 prep 清单项 2). 5 类死法分类 + 4 共同 root cause + B 设计 5 unsolved issue + F5 反例不撞已死 paradigm 评估. Phase 0 Gemini/GPT cross-check 必带."
metadata:
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-21 Day 16c-2: 补做上次进 B 方向前 prep 清单项 2 (没做的). 之前 27 lever 散落 17 个 single-memory + 25 paradigm investigation 文件夹, Gemini round 14 cross-check 时只给 framework doc 不给死路历史, Gemini 给的 F5 反例无法判断是否撞已死. 补 consolidated timeline.

完整 doc: `docs/research/p3_b_design_v2_20260521/paradigm_death_timeline.md` (~210 行).

## 5 类死法分类

- **Class A — Cut amplification 不够** (cut 太弱, necessary ≠ sufficient): Path 12/13/14, D2 Path 17, B1 Phase 5/6 path-2. 共 6 paradigm 撞同墙 — pose-bool master 表达力 fundamental 限制
- **Class B — Cut accumulation 不够** (cut 收敛失败): L16 lazy power 134→133 stuck, Lever 25 IHS p50 core size=1 退化
- **Class C — Cut family abstraction 不够** (等价 full no-good): Path 18 LIC m1=2 cell-front 几乎决定 pose, Lever 26 Benders symmetry m5=1.0 trivial orbit
- **Class D — Master augmentation 撞 scale 墙**: Lever 24 augmented master 32 GB RSS, GOC-C2 25 GB > 12 GB cap, PGW-UB 8 anchor locality fail, L23 重写路径全穷尽
- **Class E — Column generation / 几何死结**: cand C Phase 0/1 GO ✅ 但 Phase 2 v3 160/266 INFEASIBLE — 96% utilization + boundary × perimeter trap
- **Class F — 早期/其他**: v8 anchor slicing, v10 witness preflight, L14 weighted occupancy, L15 set-packing prover

## 4 共同 root cause

1. **Pose-bool master 表达力 limits** — master 不知 port direction/pole selection/belt routing, 6 paradigm 撞同墙
2. **96% utilization 几何死结** — 4800/4900 + boundary 138 cells 100% saturation
3. **Cell-front pattern 已 break symmetry** — per-instance 几何 high-resolution, cut lift/symmetry 无 free lunch (LIC m1=2, Benders symm m5=1.0)
4. **Single-machine RAM 不可扩** — 48 GB + 现 solver, augmented master/GOC/PGW 全 25-32 GB 上界

## B 设计 5 unsolved issue (Phase 0 状态)

1. **96% utilization 几何死结** ✅ 已 cover (Family 1 + 6)
2. **Boundary × perimeter 容量** ✅ 已 cover (boundary source-of-truth Day 1-2 + active_assumption)
3. **Manufacturing cluster trap (132 个最大类)** ⚠️ **现 spec 不足** — Family 5 pattern_nogood 退化 full no-good, 跟 v14 review Pattern >50% stop-ship signal 矛盾. Day 18-21 需 dedicated orbit-aware lift
4. **Routing 反馈翻译成强 cut** ⏸ 现 skeleton — Family 2/4 Day 17 详细 spec
5. **m10 sound 性跨 scale 维持** ✅ Validator 每 family 独立重算设计 cover

## F5 全局电力孤岛反例 (Gemini round 14 task B) 评估

撞已死 paradigm 检查:
- vs Path 14 PCR-CUT (belt cutset min-cut): **不撞** — F5 是 power pole network, 不是 belt routing; pole BFS sub-linear, 不是 patch CP-SAT
- vs Path 13 SAC-Hull: **不撞** — spatial capacity, 跟 connectivity 无关
- vs Lever 23 D2 commodity flow: **不撞** — D2 master 端 cell-flow, F5 在 sub-problem oracle 层

**Day 17 推荐加 Family 8 power_grid_reach** (独立 family, 不 generalize Family 4 — power pole 链跟 belt 是不同 graph, schema 字段冲突风险). F5 fixture 跟 Family 8 spec 一起在 Day 17 写.

## Refs

- 完整 doc: `docs/research/p3_b_design_v2_20260521/paradigm_death_timeline.md`
- [[v14-review-findings]] / [[phase0-b-prep-progress]] / [[gemini-review-algorithm-math]]
- `cross_check/gemini_round_14_cut_families.md` — Gemini round 14 答复

## 链 (补连 2026-06-01)
- [[lever25-ihs-dead]] — Lever 25 详情
- [[lever24-augmented-master-dead]] — Lever 24 详情 (body 已点名为死法实例, hub 该出链)
- [[lever26-benders-symmetry-dead]] — Lever 26 详情 (同上)
