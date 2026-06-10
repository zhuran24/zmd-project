---
name: d2-path17-verdict
description: Path 17 D2 (Commodity cell-flow + flow conservation) 2026-05-20 完整 verdict. Phase 0b 7/7 INFEASIBLE 第一次 Phase 0 真 GO; Phase 1 5/5 cut_added master OPTIMAL 持续; Phase 2 multi-anchor 0/8 CERTIFIED 跟 Path 12-14 同质死法. 23 lever 全 verdict. paradigm 数学最丰富 但 cut form 被 master pose-bool 卡死同质退化
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

# Path 17 D2 完整 verdict (Phase 0/0b/1/2)

## 终态

🟡 **paradigm 端到端 land ✅ 但 0/8 anchor CERTIFIED**. 跟之前 5 paradigm 同质
死法 (necessary 不 sufficient + cut form 退化).

GPT v7 Candidate D 完整描述 (commodity cell-flow + virtual terminal + flow
conservation). 6 paradigm 撞同墙 strong evidence.

## Phase 历程

| Phase | wall | outcome |
|---|---|---|
| 0 D1 (轻版本: 只 u vars + cell capacity) | 1.5h wall, 1 trial | ❌ 5/7 anchor FEASIBLE, paradigm 太松 |
| 0b D2 (+ e arc + flow conservation) | 30 min wall, 1 trial | ✅ **7/7 INFEASIBLE in 0.05-0.15s**, 资源全 fit cap, 第一次 Phase 0 真 GO |
| 1 production class + LBBD wiring | 5 min wall, 5 iter | ✅ 5/5 iter cut_added=True, master OPTIMAL 持续, core 全 size 1 |
| 2 multi-anchor max_iter=10 | 73 min wall, 8 anchor | 🟡 0/8 CERTIFIED, 7/7 UNPROVEN, 1 corner sound INFEASIBLE |

## 关键 finding

D2 paradigm 数学**最丰富** — 含 production routing precheck + D1 都看不到的:
- multi-port-cell collision (D1 已 detect)
- flow conservation imbalance (source/sink count) — **D2 新**
- bottleneck cell capacity 不够 — **D2 新**
- disconnected commodity components — **D2 新**

但 cut form **退化为 instance-pose conjunction no-good**:

```
sum_{(i,p_i) in core} x_{i,p_i} <= |core| - 1
```

跟 RAB-SEP cert 同形式. core 全 size = 1 — 切单个 (instance, pose) tuple,
切空间 ≪ 1% search space, 不收敛.

**root cause**: D2 sub-problem 真识别的信息 (具体 connectivity / flow 信息)
**不能在 master pose-bool 维度上表达**. 只能翻译成 owner-pose no-good. master
在 pose-bool 维度看到的只是 "禁止这个 (instance, pose_idx)", 没看到 connectivity
specific 信息. 下次 master 给另一个 layout, D2 又 INFEASIBLE 因别的 connectivity
问题. 循环 10 iter cut 累加, paradigm 不收敛.

## 6 paradigm 撞同墙 evidence

| paradigm | sub-problem 抽象层 | cut form |
|---|---|---|
| Path 12 RAB-SEP | binding-side owner+blocker cert | instance-pose no-good |
| Path 13 SAC-Hull | corridor capacity (Menger min-cut) | separator capacity hull |
| Path 14 PCR-CUT | patch belt CP-SAT + signature lifting | sum sig_expr <= K-1 |
| Path 15 PGW-UB | positive witness + LNS | (没 cut, 正向 witness) — Phase 0 fail |
| Path 16 GOC-C2 | 全图 owner-optional + virtual terminal | sum x_{i,p_i} <= K-1 — Phase 0 资源爆 |
| **Path 17 D2** | **全图 commodity flow + conditional terminal balance** | **sum x_{i,p_i} <= K-1 — 同 RAB-SEP** |

6 paradigm 不同 sub-problem 抽象层, 但 cut form 全在 instance-pose 维度. 6/6
同 dead end pattern. **pose-bool master 表达力 limits 是 6 paradigm 全 fail
的隐含原因** 现实测 confirm.

## 进一步 confirm 用户 hypothesis

用户原 hypothesis (2026-05-20 在 paradigm investigation 终态后提出):

> 是不是 Path 01 突破时选的 pose-bool master form 把后续所有 paradigm 路堵了?

D2 实测进一步 confirm: paradigm 数学复杂度 (Path 17 D2 最高) 无关, cut form 必落
master pose-bool 维度, 表达力 collapse 到 instance-pose conjunction no-good. 6
paradigm 全死. 想升 cut 表达力**必须升 master form**, 但升 master form 撞 v7
Proposition 2 的 3 类资源 dead end (实测 Path 16 全图 routing 资源爆 confirm).

## 23 lever 全 verdict

L1-L16 (前 session) + Path 12 RAB-SEP + Path 13 SAC-Hull + Path 14 PCR-CUT +
Path 15 PGW-UB + Path 16 GOC-C2 + **Path 17 D2** = **23 lever**.

## paradigm investigation 现穷尽 (在 pose-bool + cut 框架内)

真 break 候选, 全在已 explored 或 user 拒绝范围内:
- 换 master form → GPT v7 Proposition 2 论证 + Path 16 实测 → 全图 routing 资源爆
- 放松 cap (RAM / wall) → 用户原指示 wall 放 10x 解锁 Candidate D (Path 17), 实测 paradigm 同质死
- 放松严格性 (L11 / ε-certified / 分布式) → 用户明确拒绝
- "未知压缩 proof system" (GPT v7 explicitly) → 算法理论领域级研究, 不在项目范围

## 留下的 infrastructure

- `src/models/d2_commodity_flow_core.py` 281 LOC — D2CommodityFlowCore class
- `src/search/d2_separator.py` 215 LOC — orchestrator
- `src/search/benders_loop.py` env-gated hook (EXACT_B1_D2_COMMODITY_FLOW)
- conditional terminal balance encoding (assumption literal channeling)
- `paths/17_candidate_d_commodity_flow/` 全过程数据 (3 trial scripts + 3 stats jsons + 2 verdict.md)

任何后续 paradigm 想做 "全图 commodity flow + conditional sufficient core" 直接调用.

## commit

- `d638933` Phase 0 D1 + D2 verdict
- `583c9dd` Phase 1 production class + LBBD wiring
- `751e0a6` Phase 2 multi-anchor verdict

## Related

- [[pgw-phase0-verdict]] — Path 15 (positive witness)
- [[goc-phase0-verdict]] — Path 16 (全图 owner-optional)
- [[pcr-cut-phase5-verdict]] — Path 14 (patch belt) 同质死法
- [[paradigm-phase0-cheap-gate]] — workflow 已验证 8 次有效
- v7 plan Proposition 2 — 3 类资源 dead end
- BOTTLENECK_STRUCTURE.md — 3 性质 + framework A/B/C
- MASTER_FORM_BASELINE.md (v7 包) — pose-bool master 隐含表达力 limits
