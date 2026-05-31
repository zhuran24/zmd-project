---
name: pcr-cut-phase5-verdict
description: "PCR-CUT (Path 14) Phase 5 multi-anchor verdict 2026-05-19 — paradigm 端到端 land ✅ 但 0/8 CERTIFIED, 跟 SAC-Hull / RAB-SEP 同 verdict (necessary cut 不 sufficient). 是第 20 个 lever verdict 死"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

# PCR-CUT (Path 14) Phase 5 multi-anchor 终态

## verdict 🟡

**0/8 CERTIFIED**, 7/8 UNPROVEN, 1/8 sound master-INFEASIBLE (corner negative). 跟 SAC-Hull Phase 5
+ RAB-SEP Phase 5 同 pattern.

## Phase 5 全表 (max_iter=10, master_seconds=180)

| anchor | size | status | wall_s |
|---|---|---|---|
| interior_22_28 | 27×15 | UNPROVEN | 594.8 |
| interior_10_10 | 27×15 | UNPROVEN | 611.3 |
| interior_44_30 | 27×15 | UNPROVEN | 591.3 |
| interior_15_40 | 27×15 | UNPROVEN | 613.3 |
| corner_0_0_NEGATIVE | 27×15 | INFEASIBLE | 55.9 (sound, no patch entry) |
| small_10x10 | 10×10 | UNPROVEN | 648.6 |
| small_15x10 | 15×10 | UNPROVEN | 622.6 |
| small_15x15 | 15×15 | UNPROVEN | 657.6 |

## 关键观察

**Paradigm 真接入 production** ✅:
- 7/7 non-corner anchors: PCR-CUT every iter adds cut (10/10 per anchor, 70 cuts total).
- Master.solve sustained OPTIMAL — no UNKNOWN before max_iter=10 cap.
- PCR-CUT separator wall p50 ~0.25s, p95 ~8s, well within 15s budget.
- fail-closed: env off, baseline behavior unchanged byte-for-byte.

**但 paradigm 不破局** ❌:
- 同 Path 13 SAC-Hull L2 同 pattern: master 加 cut 收敛到 layout family
  仍 routing INFEASIBLE. PCR-CUT 给的 patch nogood 是 necessary 不 sufficient.
- signature lifting 实际 lift count 都 = 1 (每 cut 只切 exact pose, 没真 lift
  family). 原因: instance pose pool 每个 pose 都有 unique footprint+ports
  pattern, 没 equivalence 可 lift. Phase 3 设计的 signature 太严.

## paradigm 不 sufficient 的根因

跟 Path 12 RAB-SEP + Path 13 SAC-Hull 同根: **routing INFEASIBLE 由全局
geometry 决定, patch 局部 INFEASIBLE 是 necessary 不 sufficient condition**.

具体: PCR-CUT 切掉 layout L1 后, master 给 layout L2 — patch P1 上 L2 可
routing-feasible (因为 L2 不 violate P1 的 local conflict), 但 patch P2 上
L2 仍 routing-INFEASIBLE → 加 cut continue. 累 10 cut 后, layout 已被切到
极偏角域, 但全图 routing-feasibility 仍未到达.

## paradigm infrastructure 留下的价值

- patch_routing_core.py 983 LOC + replay+QuickXplain — **可复用**任何后续
  paradigm 需 "patch-local CP-SAT certificate" 的场景
- patch_conflict_separator.py 469 LOC — **可复用** orchestration framework
- pose_bool_exact_master signature lifting helpers — **可复用** 任何后续
  需 within-instance pose equivalence lifting 的 cut
- Phase 0 oracle 找压力集中区 — **可复用** future paradigm 选 focus 区

## ROI 评估 (Claude pace)

- 总投入: ~6h (Phase 0 1h + Phase 1 2h + Phase 2 1h + Phase 3 1.5h + Phase 4 0.5h + Phase 5 wait 73 min)
- Phase 0 GO 信号: cost 30 min, 救了直接跳 Phase 1 浪费 2h
- Phase 1 GO 信号: 21/21 patches INFEASIBLE 真信号, 不是空跑
- Phase 4 hook 端到端: 70 cuts added master sustain OPTIMAL — **paradigm 工程
  上 work**, 但单独不破局

## 跟其他 lever 比较

| lever | end-to-end land | breakthrough |
|---|---|---|
| L1-L11 | various | ❌ all |
| L12 RAB-SEP (Path 12) | ✅ | ❌ |
| L13 SAC-Hull (Path 13) | ✅ | ❌ |
| L14 PCR-CUT (Path 14) | ✅ | ❌ |

3 个 paradigm 全 端到端 land ✅ 但全 breakthrough ❌. 模式很明确: **master.solve
当前架构下, 单 paradigm (无论 binding 端 / separator 端 / patch belt 端) 都不
sufficient to bridge from layout 到 routing-feasibility**.

## 下一步候选 (待用户决策)

不主动推: paradigm investigation 已枯竭. 真要 break, 选项:
1. **combo trial** — PCR-CUT + SAC-Hull dynamic + abstract routing L2 同时
   开, 看叠加是否 sufficient. (cheap: 1 anchor 30 min trial)
2. **GPT v4 review** — 把 PCR-CUT 经验加上, GPT 给新 paradigm. (cheap: zip 包
   1h + GPT 1-2 day review)
3. **L11 牺牲严格性** — 接受 PCR-CUT cut 之外 + heuristic / approx algorithm
   补 routing-feasibility. 用户之前明确拒绝.
4. **paradigm shift** — set-packing prover 真 PoC L15 已死, 不重做.

## commits today

- `24ed7d8` Phase 0 GO (oracle 验压力集中, 770 cells cover 98%)
- `a56ab41` Phase 1 GO (patch belt CP-SAT 21/21 INFEASIBLE, p95 metrics 全过)
- `e71879e` Phase 2 land (replay validate + QuickXplain, 8 unit tests pass)
- `f3a7382` Phase 3 land (signature lifting + master cut + separator, +10 tests)
- `2f9bee5` Phase 4 land (benders_loop hook, 5/5 iter cut_added)
- Phase 5 trial: pending commit (just log + memory)

## Related

- [[paradigm-session-2026-05-18-19]] — 整 session 上下文 + 19 lever 死
- [[pcr-cut-phase1-pickup]] — Phase 1 起跑点 (现 obsolete, all phases landed)
- [[paradigm-phase0-cheap-gate]] — paradigm 验证 workflow (验证过 3 次 GO)
